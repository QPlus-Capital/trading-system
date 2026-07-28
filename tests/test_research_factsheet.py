"""Tests for the end-of-run fact sheet: consistency of the R backbone + flat/compound split."""

from decimal import Decimal

import numpy as np
import pandas as pd
from research.portfolio.factsheet import compute_factsheet, render_terminal
from research.portfolio.risk import AccountProfile, FlatRisk, evaluate_policy

_DAY = 86_400_000_000_000  # ns per day
_BASE = 20_000  # day number ~ 2024-10


def _ts(d: int) -> int:
    return (_BASE + d) * _DAY


def _fixture() -> tuple[
    pd.DataFrame, dict[str, pd.Series], dict[str, pd.DataFrame], AccountProfile
]:
    trades = pd.DataFrame(
        {
            "market": ["A", "A", "B", "B", "A", "B"],
            "ts_opened": [_ts(0), _ts(3), _ts(1), _ts(5), _ts(7), _ts(9)],
            "ts_closed": [_ts(2), _ts(5), _ts(4), _ts(7), _ts(9), _ts(11)],
            "entry": [100.0, 100.0, 50.0, 50.0, 100.0, 50.0],
            "exit": [102.0, 99.0, 51.0, 49.0, 103.0, 52.0],
            "is_long": [True, True, True, True, True, True],
            "r": [2.0, -1.0, 1.5, -1.0, 3.0, 2.0],
        }
    )
    days = list(range(_BASE, _BASE + 12))
    daily_close = {
        "A": pd.Series([100, 101, 99, 100, 102, 101, 100, 103, 102, 101, 100, 101.0], index=days),
        "B": pd.Series([50, 50.5, 49, 50, 51, 50, 49, 52, 51, 50, 49, 50.0], index=days),
    }
    timestamps = [_ts(day) for day in range(12)]
    h4_prices = {
        market: pd.DataFrame(
            {
                "timestamp_ns": timestamps,
                "low": [Decimal(str(value)) for value in values],
                "high": [Decimal(str(value)) for value in values],
                "close": [Decimal(str(value)) for value in values],
            }
        )
        for market, values in (
            ("A", daily_close["A"].to_numpy()),
            ("B", daily_close["B"].to_numpy()),
        )
    }
    account = AccountProfile(start_balance=100_000.0, base_risk_frac=0.002)
    return trades, daily_close, h4_prices, account


def test_edge_is_the_r_backbone_and_sizing_invariant() -> None:
    trades, daily_close, h4_prices, account = _fixture()
    fs = compute_factsheet(trades, trades, daily_close, h4_prices, account)
    assert fs.risk_pct == 0.2
    # Edge comes straight from the R stream and is identical for both windows (same trades).
    assert fs.full.edge.trades == 6
    assert fs.full.edge.hit_rate == 4 / 6  # r>0 for 2, 1.5, 3, 2
    assert np.isclose(fs.full.edge.expectancy_r, np.mean([2, -1, 1.5, -1, 3, 2]), atol=1e-3)
    assert fs.full.edge == fs.holdout.edge  # deterministic, no sizing leak into the edge


def test_per_market_uses_the_flat_percent_lens() -> None:
    trades, daily_close, h4_prices, account = _fixture()
    fs = compute_factsheet(trades, trades, daily_close, h4_prices, account)
    pm = fs.per_market.set_index("market")
    # flat %: sum(R) * risk_frac * 100. A: 4 R -> 0.8%, B: 2.5 R -> 0.5%.
    assert np.isclose(pm.loc["A", "ret_pct"], 0.8)
    assert np.isclose(pm.loc["B", "ret_pct"], 0.5)
    assert np.isclose(pm["share_pct"].sum(), 100.0)  # shares of total R


def test_per_year_is_compound_return_on_the_running_balance() -> None:
    trades, daily_close, h4_prices, account = _fixture()
    fs = compute_factsheet(trades, trades, daily_close, h4_prices, account)
    # all trades close in 2024 -> the single year equals the full-window COMPOUND total return
    # (growth of the compounding equity), NOT the flat sum(R)*risk figure.
    assert list(fs.per_year["year"]) == [2024]
    eq = fs.full.equity_comp
    expected = (float(eq.iloc[-1]) / float(eq.iloc[0]) - 1) * 100
    assert np.isclose(fs.per_year["ret_pct"].iloc[0], expected)


def test_compound_and_flat_money_both_present_and_terminal_renders() -> None:
    trades, daily_close, h4_prices, account = _fixture()
    fs = compute_factsheet(trades, trades, daily_close, h4_prices, account)
    for m in (fs.full.flat, fs.full.compound):
        assert m.max_drawdown_pct <= 0.0  # drawdown is non-positive
    text = render_terminal(fs)
    assert "Rendite p.a." in text and "Volle Historie" in text


def test_fact_sheet_reuses_the_verdict_flat_daily_diagnostics() -> None:
    trades, daily_close, h4_prices, account = _fixture()
    result = evaluate_policy(
        trades,
        daily_close,
        account,
        FlatRisk(account.base_risk_frac * 100.0),
        account.base_risk_frac,
        h4_prices=h4_prices,
    )

    fs = compute_factsheet(
        trades,
        trades,
        daily_close,
        h4_prices,
        account,
        holdout_flat=result,
    )

    assert fs.holdout.flat.max_drawdown_pct == result.max_drawdown_pct
