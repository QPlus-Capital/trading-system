"""Tests for the regime-robustness analysis (pure classification + aggregation)."""

import numpy as np
import pandas as pd

from qplus.backtest.portfolio.curves import DAY_NS
from qplus.backtest.portfolio.regime import (
    _day_number,
    crisis_table,
    efficiency_ratio,
    label_trades,
    realized_vol,
    regime_edge_table,
    tercile_labels,
)


def test_efficiency_ratio_trend_vs_chop() -> None:
    trend = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    chop = pd.Series([1.0, 2.0, 1.0, 2.0, 1.0, 2.0])
    assert abs(efficiency_ratio(trend, 5).iloc[5] - 1.0) < 1e-9  # clean one-way move
    assert abs(efficiency_ratio(chop, 5).iloc[5] - 0.2) < 1e-9  # lots of motion, no progress


def test_realized_vol_constant_is_zero() -> None:
    flat = pd.Series([100.0] * 10)
    assert realized_vol(flat, 5).iloc[-1] == 0.0


def test_tercile_labels_split_at_own_percentiles() -> None:
    vals = pd.Series([float(i) for i in range(1, 10)])  # 1..9
    labels = tercile_labels(vals, ("lo", "mid", "hi"))
    assert labels.iloc[0] == "lo"  # 1 is low
    assert labels.iloc[-1] == "hi"  # 9 is high
    assert set(labels.unique()) == {"lo", "mid", "hi"}


def test_label_trades_maps_market_regime_at_open() -> None:
    # A market with a warmup then trades; a trade after warmup must get a (non-null) regime.
    # A varied series (range then trend) so both regime terciles are non-degenerate.
    rng = np.random.default_rng(0)
    ranging = 100.0 + np.cumsum(rng.normal(0, 0.5, 40))
    trending = ranging[-1] + np.cumsum(np.full(40, 0.8))
    closes = pd.Series(np.concatenate([ranging, trending]), index=range(80))
    trades = pd.DataFrame({"market": ["X"], "ts_opened": [70 * DAY_NS], "r": [1.0]})
    out = label_trades(trades, {"X": closes}, vol_lb=20, trend_lb=20)
    # The plumbing must assign a concrete regime from each axis (not left null).
    assert out["trend_regime"].iloc[0] in {"seitwaerts", "mittel", "trendig"}
    assert out["vol_regime"].iloc[0] in {"ruhig", "mittel", "stuermisch"}


def test_regime_edge_table_aggregates_in_r() -> None:
    labeled = pd.DataFrame(
        {
            "vol_regime": ["ruhig", "ruhig", "stuermisch"],
            "r": [2.0, -1.0, 3.0],
        }
    )
    tbl = regime_edge_table(labeled, "vol_regime", order=("ruhig", "mittel", "stuermisch"))
    ruhig = tbl[tbl["regime"] == "ruhig"].iloc[0]
    assert ruhig["trades"] == 2
    assert abs(ruhig["expectancy_R"] - 0.5) < 1e-9  # mean(2, -1)
    assert abs(ruhig["total_R"] - 1.0) < 1e-9
    assert "mittel" not in set(tbl["regime"])  # empty buckets are dropped


def test_crisis_table_counts_trades_inside_the_window() -> None:
    inside = _day_number("2020-03-15") * DAY_NS  # within the COVID window
    outside = _day_number("2019-06-01") * DAY_NS
    labeled = pd.DataFrame({"ts_opened": [inside, outside], "r": [-2.0, 1.0]})
    tbl = crisis_table(labeled)
    covid = tbl[tbl["crisis"] == "COVID-Crash 2020"].iloc[0]
    assert covid["trades"] == 1
    assert abs(covid["total_R"] - (-2.0)) < 1e-9
