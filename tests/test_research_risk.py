"""Tests for the pluggable, tail-capped risk system."""

import math

import numpy as np
import pandas as pd
import pytest
from research.portfolio.curves import DAY_NS
from research.portfolio.risk import (
    AccountProfile,
    FlatRisk,
    KellyRisk,
    ThrottleRisk,
    evaluate_policy,
    flat_base_pnl,
    rck_fraction,
    tail_cap,
)
from research.portfolio.tail import traded_stop_loss_pct
from research.portfolio.trades import assign_r


def _trades() -> pd.DataFrame:
    # Worst day is day 0 (-2R + -3R = -5R); a -4R single trade on day 1.
    return pd.DataFrame(
        {"ts_closed": [0, 0, 1 * DAY_NS], "r": [-2.0, -3.0, -4.0]}
    )


def test_tail_cap_binds_on_the_worst_day_under_stress() -> None:
    acc = AccountProfile()  # 3% daily / 6% trailing
    # worst day -5R, stress 1.5 -> 7.5R; 3% daily / 7.5 = 0.4% max flat risk.
    assert abs(tail_cap(_trades(), acc, stress_mult=1.5) - 0.03 / 7.5) < 1e-12


def test_flat_risk_is_hard_capped_by_the_tail() -> None:
    acc = AccountProfile()
    cap = tail_cap(_trades(), acc, stress_mult=1.5)  # 0.4%
    # Ask for 1.0% but the tail cap is 0.4% -> resolved risk is the cap, never above it.
    r = FlatRisk(1.0).resolve(cap, acc)
    assert abs(r.ceiling_pct - cap * 100) < 1e-9
    assert r.risk_fn(0.0) == r.risk_fn(1.0)  # constant regardless of used budget
    assert abs(r.risk_fn(0.5) - cap / acc.base_risk_frac) < 1e-9  # in base-risk multiples


def test_flat_risk_below_the_cap_passes_through() -> None:
    acc = AccountProfile()
    cap = 0.005  # 0.5%
    r = FlatRisk(0.15).resolve(cap, acc)  # well under the cap
    assert abs(r.ceiling_pct - 0.15) < 1e-9
    assert abs(r.risk_fn(0.0) - 0.0015 / acc.base_risk_frac) < 1e-9


def test_throttle_runs_at_the_ceiling_and_tapers_to_the_floor() -> None:
    acc = AccountProfile()
    cap = 0.006  # 0.6% ceiling
    r = ThrottleRisk(floor_pct=0.15).resolve(cap, acc)
    assert abs(r.ceiling_pct - 0.6) < 1e-9
    assert r.floor_pct == 0.15
    # Fresh buffer (used=0) -> full ceiling risk; at the wall (used=1) -> the floor.
    assert abs(r.risk_fn(0.0) - cap / acc.base_risk_frac) < 1e-9  # 0.6% as a multiple
    assert abs(r.risk_fn(1.0) - 0.0015 / acc.base_risk_frac) < 1e-9  # tapered to 0.15%
    assert r.risk_fn(0.0) > r.risk_fn(1.0)  # runs higher in good times, brakes near the wall


def test_throttle_degenerates_to_flat_when_the_floor_exceeds_the_cap() -> None:
    # A vicious tail can push the cap (0.04%) BELOW the requested floor (0.15%). The throttle then
    # has no room to move -- it must pin to the cap, not report an inverted 0.15% -> 0.04% range.
    acc = AccountProfile()
    r = ThrottleRisk(floor_pct=0.15).resolve(0.0004, acc)  # cap 0.04% < floor 0.15%
    assert r.ceiling_pct == r.floor_pct == pytest.approx(0.04)  # collapsed to the cap
    assert r.risk_fn(0.0) == r.risk_fn(1.0)  # constant -> flat sizing at the cap
    assert "flat" in r.label  # labelled honestly


def test_assign_r_removes_the_backtests_compounding() -> None:
    # Both trades earn the same money, but the second was sized off a LARGER equity, so it risked
    # more -- its R must be smaller. That difference is exactly the compounding we must strip.
    rows = [
        {"ts_closed": 0, "pnl_base": 2_000.0},
        {"ts_closed": 1 * DAY_NS, "pnl_base": 2_000.0},
    ]
    assign_r(rows, start_balance=200_000.0, base_risk_frac=0.01)
    assert math.isclose(rows[0]["r"], 1.0)  # 2000 / (1% of 200,000)
    assert math.isclose(rows[1]["r"], 2_000.0 / (0.01 * 202_000.0))  # equity had grown
    assert rows[1]["r"] < rows[0]["r"]


def _winners() -> tuple[pd.DataFrame, dict[str, pd.Series]]:
    """Three identical +1R winners, each opening one day and closing the next."""
    rows = [
        {"market": "X", "ts_opened": d * DAY_NS, "ts_closed": (d + 1) * DAY_NS,
         "r": 1.0, "entry": 10.0, "exit": 11.0}
        for d in (0, 2, 4)
    ]
    prices = pd.Series({d: 10.0 + 0.2 * d for d in range(6)})
    return pd.DataFrame(rows), {"X": prices}


def test_flat_base_pnl_is_linear_in_r() -> None:
    acc = AccountProfile()
    trades, _ = _winners()
    # 1R at the 1% base risk on a 200k account = 2,000 EUR, regardless of position in the stream.
    assert list(flat_base_pnl(trades, acc)) == [2_000.0] * 3


def test_flat_policy_books_r_times_risk_without_compounding() -> None:
    acc = AccountProfile()
    trades, prices = _winners()
    res = evaluate_policy(trades, prices, acc, FlatRisk(1.0), cap_frac=0.02)
    assert res.label == "flat"
    assert not res.breached
    # 3 x 1R at 1% of 200k = 6,000 EUR = +3.0% of the START balance (never of a grown one).
    assert math.isclose(res.total_return_pct, 3.0, abs_tol=0.05)


def test_throttle_runs_bigger_than_flat_while_the_buffer_is_fresh() -> None:
    acc = AccountProfile()
    trades, prices = _winners()
    cap = 0.02  # 2% ceiling
    flat_res = evaluate_policy(trades, prices, acc, FlatRisk(0.5), cap_frac=cap)
    thr_res = evaluate_policy(trades, prices, acc, ThrottleRisk(floor_pct=0.5), cap_frac=cap)
    # Winners never eat the drawdown budget, so the throttle stays at its 2% ceiling the whole way
    # and out-earns the 0.5% flat policy -- exactly the "don't leave return on the table" case.
    assert thr_res.ceiling_pct == 2.0 and thr_res.floor_pct == 0.5
    assert thr_res.total_return_pct > flat_res.total_return_pct
    assert not thr_res.breached


def _reversal_r(
    seed: int, hit: float = 0.46, win: float = 2.0, loss: float = -1.0, n: int = 8000
) -> list[float]:
    """A reversal-like R distribution: ``hit`` winners of ``win`` R, rest losers of ``loss`` R."""
    rng = np.random.default_rng(seed)
    return list(np.where(rng.random(n) < hit, win, loss))


def test_rck_positive_and_bounded_for_a_profitable_distribution() -> None:
    phi = rck_fraction(_reversal_r(0), alpha=0.94, beta=0.05)
    assert 0.0 < phi <= 0.05  # a real bet, under the sanity cap


def test_rck_tighter_tolerance_shrinks_the_bet() -> None:
    r = _reversal_r(1)
    loose = rck_fraction(r, alpha=0.94, beta=0.10)
    tight = rck_fraction(r, alpha=0.94, beta=0.01)
    assert 0.0 < tight < loose  # a lower tolerance for ruin -> a smaller bet


def test_rck_zero_for_an_unprofitable_distribution() -> None:
    # 40% winners of +2R vs 60% losers of -1.5R -> negative expectancy -> no growth-positive bet.
    assert rck_fraction(_reversal_r(2, hit=0.40, win=2.0, loss=-1.5), alpha=0.94, beta=0.05) == 0.0


def test_rck_respects_the_drawdown_bound_in_simulation() -> None:
    # The correctness check: at the returned fraction, the empirical probability of EVER falling to
    # alpha*W0 over a long trade sequence must stay within beta (the bound is guaranteed-safe).
    import numpy as np

    r_dist = _reversal_r(3)
    alpha, beta = 0.94, 0.05
    phi = rck_fraction(r_dist, alpha=alpha, beta=beta)
    rng = np.random.default_rng(99)
    draws = rng.choice(r_dist, size=(4000, 800))  # 4000 wealth paths of 800 trades
    wealth = np.cumprod(1.0 + phi * draws, axis=1)
    hit_floor = (wealth.min(axis=1) <= alpha).mean()
    assert hit_floor <= beta + 0.01  # the drawdown bound holds empirically


def test_kelly_risk_reads_the_account_wall() -> None:
    acc = AccountProfile()  # trailing_hard 0.06 -> wealth floor alpha = 0.94
    trades = pd.DataFrame({"r": _reversal_r(4)})
    phi = KellyRisk(beta=0.05).fraction(trades, acc)
    assert 0.0 < phi <= 0.05


def test_the_reported_return_and_the_trade_stream_are_both_net_of_swap() -> None:
    """#10: one canonical net return. The headline return already netted swap via simulate();
    trade_pnl (which feeds Monte-Carlo and the edge stats) must net it the same way, or the
    return is net while every risk statistic is gross."""
    acc = AccountProfile()
    trades, prices = _winners()
    gross = evaluate_policy(trades, prices, acc, FlatRisk(1.0), cap_frac=0.02)

    withswap = trades.copy()
    withswap["swap_r"] = [-0.1, -0.1, -0.1]  # carry costs 0.1R per trade
    net = evaluate_policy(withswap, prices, acc, FlatRisk(1.0), cap_frac=0.02)

    # The reported return drops by 3 x 0.1R (= 0.3% of the start balance) ...
    assert math.isclose(net.total_return_pct, gross.total_return_pct - 0.3, abs_tol=0.05)
    # ... and the per-trade stream drops by exactly the same amount, not by zero.
    assert math.isclose(float(net.trade_pnl.sum()), float(gross.trade_pnl.sum()) - 600.0, abs_tol=1)


def test_kelly_sizes_off_the_net_distribution() -> None:
    """#10: a carry cost that eats the edge must shrink the Kelly bet, not be invisible to it."""
    acc = AccountProfile()
    trades, _ = _winners()
    edge = trades.copy()
    edge["r"] = [1.0, -0.5, 1.0]  # a real distribution, not all winners
    gross_f = KellyRisk(beta=0.1).fraction(edge, acc)

    costly = edge.copy()
    costly["swap_r"] = [-0.4, -0.4, -0.4]  # carry eats most of the edge
    assert KellyRisk(beta=0.1).fraction(costly, acc) < gross_f


def test_empty_inputs_fail_closed_with_a_reason() -> None:
    """#22: nothing surviving selection is an auditable result, not an IndexError from deep
    inside a day loop or a mode() on an empty frame."""
    acc = AccountProfile()
    empty = pd.DataFrame(columns=["market", "ts_opened", "ts_closed", "r", "entry", "exit"])
    with pytest.raises(ValueError, match="at least one trade"):
        evaluate_policy(empty, {}, acc, FlatRisk(1.0), cap_frac=0.02)
    with pytest.raises(ValueError, match="no trades"):
        traded_stop_loss_pct(empty)
