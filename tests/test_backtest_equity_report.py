"""Tests for the flat-portfolio equity report's pure logic (R-multiples + accumulation)."""

import pandas as pd

from qplus.backtest.portfolio.equity_report import _START_BALANCE, flat_portfolio, r_multiples


def test_r_multiples_recover_size_invariant_return() -> None:
    # First trade risks 1% of 200k = 2000; a +2000 PnL is exactly +1R.
    rs = r_multiples([2000.0], start=200_000.0)
    assert abs(rs[0] - 1.0) < 1e-9


def test_r_multiples_walk_the_equity_forward() -> None:
    # After a +2000 win, equity is 202k -> next trade risks 2020; a -2020 loss is -1R.
    rs = r_multiples([2000.0, -2020.0], start=200_000.0)
    assert abs(rs[0] - 1.0) < 1e-9
    assert abs(rs[1] + 1.0) < 1e-9


def test_flat_portfolio_books_risk_times_r_in_close_order() -> None:
    # Two markets; flat risk 300/trade. Ordered by close time, equity = 200k + 300*sum(R).
    trades = pd.DataFrame(
        {
            "market": ["A", "B", "A"],
            "ts_closed": [30, 10, 20],  # deliberately unordered
            "r": [2.0, -1.0, 0.5],
        }
    )
    curve = flat_portfolio(trades, risk_amount=300.0)
    assert list(curve["market"]) == ["B", "A", "A"]  # sorted by close time
    # cumulative: -1R, then +0.5R, then +2R -> 300*[-1, -0.5, 1.5]
    assert list(curve["equity"]) == [
        _START_BALANCE - 300.0,
        _START_BALANCE - 150.0,
        _START_BALANCE + 450.0,
    ]
