"""Tests for the sweep heatmap pivot logic."""

import pandas as pd

from qplus.backtest.validation.heatmap import pivot_metric


def test_pivot_metric_averages_over_other_columns() -> None:
    df = pd.DataFrame(
        {
            "stop_loss_pct": [0.5, 0.5, 1.0, 1.0],
            "take_profit_pct": [2.0, 2.0, 2.0, 2.0],
            "buy_rsi_threshold": [35.0, 40.0, 35.0, 40.0],  # averaged out
            "profit_factor": [1.0, 1.2, 0.8, 1.0],
        }
    )
    pivot = pivot_metric(df, "stop_loss_pct", "take_profit_pct", "profit_factor")

    # One row (tp=2.0), two columns (sl=0.5, 1.0); values averaged over buy_rsi.
    assert list(pivot.columns) == [0.5, 1.0]
    assert pivot.loc[2.0, 0.5] == 1.1  # mean(1.0, 1.2)
    assert pivot.loc[2.0, 1.0] == 0.9  # mean(0.8, 1.0)
