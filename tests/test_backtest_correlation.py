"""Tests for the portfolio concentration analysis (correlation + concurrency)."""

import numpy as np
import pandas as pd

from qplus.backtest.portfolio.correlation import (
    concurrency_summary,
    daily_exposure,
    effective_bets,
)
from qplus.backtest.portfolio.curves import DAY_NS


def test_effective_bets_uncorrelated_equals_n() -> None:
    corr = pd.DataFrame(np.eye(3))
    assert abs(effective_bets(corr) - 3.0) < 1e-9  # identity -> fully diversified


def test_effective_bets_all_correlated_approaches_one() -> None:
    corr = pd.DataFrame(np.full((4, 4), 0.999) + np.eye(4) * 0.001)
    assert effective_bets(corr) < 1.05  # near rank-1 -> one bet


def test_daily_exposure_counts_overlap_and_direction() -> None:
    # Two trades overlapping on day 5-6: one long (up), one short (down).
    trades = pd.DataFrame(
        {
            "ts_opened": [4 * DAY_NS, 5 * DAY_NS],
            "ts_closed": [6 * DAY_NS, 7 * DAY_NS],
            "entry": [100.0, 100.0],
            "exit": [110.0, 90.0],  # long winner, short winner
            "r": [1.0, 1.0],
        }
    )
    exp = daily_exposure(trades)  # [od, cd): t1 open days 4-5, t2 open days 5-6
    assert exp.loc[4, "n_open"] == 1  # only the first trade
    assert exp.loc[5, "n_open"] == 2  # both open
    assert exp.loc[5, "n_long"] == 1
    assert exp.loc[5, "n_short"] == 1
    assert exp.loc[5, "net"] == 0
    assert exp.loc[6, "n_open"] == 1  # t1 closed on day 6; only t2 open
    assert exp.loc[7, "n_open"] == 0  # both closed


def test_concurrency_summary_headline_stats() -> None:
    trades = pd.DataFrame(
        {
            "ts_opened": [4 * DAY_NS, 5 * DAY_NS],
            "ts_closed": [6 * DAY_NS, 7 * DAY_NS],
            "entry": [100.0, 100.0],
            "exit": [110.0, 120.0],  # both long winners
            "r": [1.0, 1.0],
        }
    )
    s = concurrency_summary(daily_exposure(trades), n_markets=2)
    assert s["max_open"] == 2
    assert s["max_net_long"] == 2  # both long at once
    assert s["max_net_short"] == 0
