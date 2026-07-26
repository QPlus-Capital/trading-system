"""Behavioural guards for synchronized H4 portfolio-risk reconstruction."""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd
import pytest
from research.portfolio.curves import to_day
from research.portfolio.risk import AccountProfile, FlatRisk, evaluate_policy
from research.portfolio.sizing import DailyDiagnostics, flat, simulate

_HOUR_NS = 3_600_000_000_000


def _ts(value: str) -> int:
    return int(pd.Timestamp(value, tz="UTC").value)


def _h4(*rows: tuple[int, str, str, str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp_ns": [row[0] for row in rows],
            "low": [Decimal(row[1]) for row in rows],
            "high": [Decimal(row[2]) for row in rows],
            "close": [Decimal(row[3]) for row in rows],
        }
    )


def _run(
    trades: pd.DataFrame,
    h4_prices: dict[str, pd.DataFrame],
    *,
    d0: int | None = None,
    d1: int | None = None,
    risk_multiple: float = 1.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, DailyDiagnostics]:
    opened = trades["ts_opened"].to_numpy(dtype=np.int64)
    closed = trades["ts_closed"].to_numpy(dtype=np.int64)
    t = trades.copy()
    t["od"] = [to_day(int(value)) for value in opened]
    t["cd"] = [to_day(int(value)) for value in closed]
    first = min(t["od"]) if d0 is None else d0
    last = max(t["cd"]) if d1 is None else d1
    closes = {
        market: np.full(last - first + 1, float(rows["close"].iloc[-1]))
        for market, rows in h4_prices.items()
    }
    return simulate(
        t,
        closes,
        first,
        last,
        100_000.0,
        0.06,
        flat(risk_multiple),
        h4_prices=h4_prices,
        daily_limit_frac=0.03,
    )


def _trade(
    market: str,
    opened: int,
    closed: int,
    *,
    pnl_base: float = 1_000.0,
    entry: float = 100.0,
    exit_: float = 99.0,
    swap_base: float = 0.0,
) -> dict[str, object]:
    return {
        "market": market,
        "ts_opened": opened,
        "ts_closed": closed,
        "pnl_base": pnl_base,
        "entry": entry,
        "exit": exit_,
        "is_long": False,
        "swap_base": swap_base,
    }


def test_trade_uses_only_h4_observations_inside_its_lifetime() -> None:
    opened = _ts("2025-04-10 13:00")
    closed = _ts("2025-04-10 17:00")
    trades = pd.DataFrame([_trade("X", opened, closed)])
    bars = {
        "X": _h4(
            (_ts("2025-04-10 01:00"), "99", "120", "100"),
            (opened, "98.8", "100.2", "99"),
            (closed, "90", "140", "95"),
        )
    }

    _realized, _equity, _sizes, diagnostics = _run(trades, bars)

    assert diagnostics.minimum_equity[0] == pytest.approx(99_800.0)
    assert diagnostics.h4_upper_bound


def test_same_observation_short_never_consumes_a_later_high() -> None:
    bar_start = _ts("2025-04-10 13:00")
    opened = bar_start + _HOUR_NS // 2
    closed = bar_start + 7 * _HOUR_NS // 2
    trades = pd.DataFrame([_trade("X", opened, closed)])
    bars = {
        "X": _h4(
            (bar_start, "98.8", "100.2", "99"),
            (bar_start + 4 * _HOUR_NS, "90", "140", "95"),
        )
    }

    _realized, _equity, _sizes, diagnostics = _run(trades, bars)

    assert diagnostics.minimum_equity[0] == pytest.approx(99_800.0)
    assert diagnostics.daily_loss[0] == pytest.approx(0.002)


def test_different_h4_intervals_do_not_sum_adverse_extremes() -> None:
    t05 = _ts("2025-04-10 05:00")
    t09 = _ts("2025-04-10 09:00")
    t13 = _ts("2025-04-10 13:00")
    trades = pd.DataFrame(
        [
            _trade("A", t05, t09),
            _trade("B", t09, t13),
        ]
    )
    bars = {
        "A": _h4((t05, "99", "100.2", "99")),
        "B": _h4((t09, "99", "100.2", "99")),
    }

    _realized, _equity, _sizes, diagnostics = _run(trades, bars)

    assert diagnostics.minimum_equity[0] == pytest.approx(99_800.0)


def test_same_h4_interval_sums_contemporaneous_adverse_marks() -> None:
    t05 = _ts("2025-04-10 05:00")
    t09 = _ts("2025-04-10 09:00")
    trades = pd.DataFrame(
        [
            _trade("A", t05, t09),
            _trade("B", t05, t09),
        ]
    )
    bars = {
        "A": _h4((t05, "99", "100.2", "99")),
        "B": _h4((t05, "99", "100.2", "99")),
    }

    _realized, _equity, _sizes, diagnostics = _run(trades, bars)

    assert diagnostics.minimum_equity[0] == pytest.approx(99_600.0)
    assert diagnostics.h4_upper_bound == (
        "H4 upper bound: contemporaneous positions may hit their direction-adverse "
        "extremes within the same H4 interval"
    )


def test_disjoint_lifetimes_inside_one_h4_bar_are_not_summed() -> None:
    bar_start = _ts("2025-04-10 05:00")
    boundary = bar_start + 2 * _HOUR_NS
    bar_end = bar_start + 4 * _HOUR_NS
    trades = pd.DataFrame(
        [
            _trade("A", bar_start, boundary),
            _trade("B", boundary, bar_end),
        ]
    )
    bars = {
        "A": _h4((bar_start, "99", "100.2", "99")),
        "B": _h4((bar_start, "99", "100.2", "99")),
    }

    _realized, _equity, _sizes, diagnostics = _run(trades, bars)

    assert diagnostics.minimum_equity[0] == pytest.approx(99_800.0)


def test_reset_straddling_bar_is_charged_only_for_an_overlapping_position() -> None:
    bar = _ts("2026-07-01 21:00")
    before = to_day(bar)
    after = to_day(bar + 4 * _HOUR_NS)
    assert after == before + 1
    overlapping = pd.DataFrame([_trade("X", bar, bar + 4 * _HOUR_NS)])
    non_overlapping = pd.DataFrame([_trade("X", bar, bar)])
    bars = {"X": _h4((bar, "99", "100.2", "99"))}

    *_unused, overlap_diagnostics = _run(overlapping, bars, d0=before, d1=after)
    *_unused2, no_overlap_diagnostics = _run(non_overlapping, bars, d0=before, d1=after)

    assert list(overlap_diagnostics.minimum_equity) == pytest.approx([99_800.0, 99_800.0])
    assert list(no_overlap_diagnostics.minimum_equity) == pytest.approx([100_000.0, 101_000.0])


def test_swap_is_realized_once_at_close_and_never_in_an_h4_mark() -> None:
    opened = _ts("2025-04-09 13:00")
    observed = _ts("2025-04-10 09:00")
    closed = _ts("2025-04-10 13:00")
    trades = pd.DataFrame([_trade("X", opened, closed, pnl_base=1_000.0, swap_base=-50.0)])
    bars = {"X": _h4((observed, "99", "100.2", "99"))}

    realized, _equity, _sizes, diagnostics = _run(trades, bars)

    assert diagnostics.minimum_equity[-1] == pytest.approx(99_800.0)
    assert realized[-1] == pytest.approx(100_950.0)
    assert diagnostics.close_balance[-1] == pytest.approx(100_950.0)


def test_daily_and_trailing_flags_share_the_minimum_equity_path() -> None:
    opened = _ts("2025-04-10 05:00")
    closed = _ts("2025-04-10 09:00")
    trades = pd.DataFrame([_trade("X", opened, closed)])
    bars = {"X": _h4((opened, "99", "104", "99"))}

    _realized, _equity, _sizes, diagnostics = _run(trades, bars)

    assert diagnostics.opening_balance[0] == pytest.approx(100_000.0)
    assert diagnostics.close_balance[0] == pytest.approx(101_000.0)
    assert diagnostics.close_equity[0] == pytest.approx(101_000.0)
    assert diagnostics.minimum_equity[0] == pytest.approx(96_000.0)
    assert diagnostics.daily_loss[0] == pytest.approx(0.04)
    assert diagnostics.trailing_floor[0] == pytest.approx(95_000.0)
    assert diagnostics.daily_breach[0]
    assert not diagnostics.trailing_breach[0]
    assert diagnostics.breached


def test_closed_market_carries_last_close_without_borrowing_an_extreme() -> None:
    t05 = _ts("2025-04-10 05:00")
    t09 = _ts("2025-04-10 09:00")
    t13 = _ts("2025-04-10 13:00")
    trades = pd.DataFrame(
        [
            _trade("A", t05, t13),
            _trade("B", t05, t13),
        ]
    )
    bars = {
        "A": _h4((t05, "99", "100.2", "99"), (t09, "99", "100.2", "99")),
        "B": _h4((t05, "99", "100", "99.5")),
    }

    _realized, _equity, _sizes, diagnostics = _run(trades, bars)

    assert diagnostics.minimum_equity[0] == pytest.approx(99_800.0)


def test_wholly_missing_h4_lifetime_evidence_fails_closed() -> None:
    t05 = _ts("2025-04-10 05:00")
    t09 = _ts("2025-04-10 09:00")
    trades = pd.DataFrame(
        [
            _trade("A", t05, t09),
            _trade("B", t05, t09),
        ]
    )
    bars = {
        "A": _h4((t05, "99", "100.2", "99")),
        "B": _h4((_ts("2025-04-10 13:00"), "99", "100.2", "99")),
    }

    with pytest.raises(ValueError, match="no H4 observation overlaps B trade 1"):
        _run(trades, bars)


def test_synthetic_retired_structure_replaces_impossible_whole_day_breach() -> None:
    stamps = [
        _ts("2025-04-10 05:00"),
        _ts("2025-04-10 09:00"),
        _ts("2025-04-10 13:00"),
    ]
    returns = [6.14, 4.11, 3.08, 2.00, -1.00, -1.00]
    rows: list[dict[str, object]] = []
    bars: dict[str, pd.DataFrame] = {}
    legacy_worst = Decimal("0")
    risk_multiple = Decimal("0.15")
    per_trade_legacy_loss = Decimal("3200") / Decimal(6)
    for index, result_r in enumerate(returns):
        market = f"M{index}"
        observed = stamps[index // 2]
        opened = observed - 4 * _HOUR_NS
        pnl_base = Decimal(str(result_r)) * Decimal("1000")
        exit_price = Decimal("99") if result_r > 0 else Decimal("101")
        span = exit_price - Decimal("100")
        actual_loss = Decimal("185")
        actual_high = Decimal("100") + actual_loss * abs(span) / (abs(pnl_base) * risk_multiple)
        later_high = Decimal("100") + per_trade_legacy_loss * abs(span) / (
            abs(pnl_base) * risk_multiple
        )
        rows.append(
            _trade(
                market,
                opened,
                observed,
                pnl_base=float(pnl_base),
                exit_=float(exit_price),
            )
        )
        bars[market] = _h4(
            (opened, "99", str(actual_high), str(exit_price)),
            (_ts("2025-04-10 17:00"), "99", str(later_high), str(exit_price)),
        )
        fraction = (later_high - Decimal("100")) / span
        legacy_worst += pnl_base * risk_multiple * fraction
    trades = pd.DataFrame(rows)

    _realized, equity, _sizes, diagnostics = _run(trades, bars, risk_multiple=0.15)
    whole_day_loss = float(-legacy_worst / Decimal("100000"))

    assert whole_day_loss == pytest.approx(0.032)
    assert equity[-1] > 100_000.0
    assert 0.0030 <= diagnostics.daily_loss.max() <= 0.0045
    assert not diagnostics.daily_breach.any()


def test_h4_path_changes_leave_every_non_path_policy_statistic_exact() -> None:
    opened = _ts("2025-04-10 05:00")
    closed = _ts("2025-04-10 09:00")
    day = to_day(opened)
    trades = pd.DataFrame(
        {
            "market": ["X"],
            "ts_opened": [opened],
            "ts_closed": [closed],
            "entry": [100.0],
            "exit": [99.0],
            "is_long": [False],
            "r": [2.0],
            "swap_r": [-0.1],
        }
    )
    daily_close = {"X": pd.Series([99.0], index=[day])}
    mild = {"X": _h4((opened, "98.9", "100.2", "99"))}
    severe = {"X": _h4((opened, "98.9", "104", "99"))}
    account = AccountProfile(start_balance=100_000.0, base_risk_frac=0.01)

    mild_result = evaluate_policy(
        trades, daily_close, account, FlatRisk(0.15), 0.02, h4_prices=mild
    )
    severe_result = evaluate_policy(
        trades, daily_close, account, FlatRisk(0.15), 0.02, h4_prices=severe
    )

    for field in (
        "label",
        "ceiling_pct",
        "floor_pct",
        "n_trades",
        "years",
        "total_return_pct",
        "ann_return_pct",
        "ann_return_eur",
    ):
        assert getattr(mild_result, field) == getattr(severe_result, field)
    np.testing.assert_array_equal(mild_result.trade_pnl, severe_result.trade_pnl)
    np.testing.assert_array_equal(mild_result.trade_swap, severe_result.trade_swap)
    np.testing.assert_array_equal(
        mild_result.daily_diagnostics.close_balance,
        severe_result.daily_diagnostics.close_balance,
    )
    np.testing.assert_array_equal(
        mild_result.daily_diagnostics.close_equity,
        severe_result.daily_diagnostics.close_equity,
    )
    assert mild_result.max_drawdown_pct != severe_result.max_drawdown_pct
