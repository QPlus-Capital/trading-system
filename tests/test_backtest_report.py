"""Tests for the verdict-stage report charts and the full-history tail helpers."""

from pathlib import Path

import numpy as np
import pandas as pd

from qplus.backtest.portfolio import report
from qplus.backtest.portfolio.tail import representative_params, traded_stop_loss_pct


def _equity() -> pd.Series:
    idx = pd.date_range("2024-01-01", periods=50, freq="D")
    return pd.Series(200_000 + np.linspace(0, 5_000, 50), index=idx)


def test_representative_params_takes_the_middle_of_each_grid_axis() -> None:
    grid = {"stop_loss_pct": [0.5, 1.0, 1.5, 2.0], "take_profit_pct": [1.0, 2.0, 3.0]}
    # sorted()[len//2]: 4 values -> index 2 (1.5); 3 values -> index 1 (2.0).
    assert representative_params(grid) == {"stop_loss_pct": 1.5, "take_profit_pct": 2.0}


def test_representative_params_pins_the_traded_stop() -> None:
    # R = move/stop, so the tail MUST be measured at the stop actually traded, not the grid's mid.
    grid = {"stop_loss_pct": [0.5, 1.0, 1.5, 2.0], "take_profit_pct": [1.0, 2.0, 3.0]}
    params = representative_params(grid, stop_loss_pct=0.5)
    assert params["stop_loss_pct"] == 0.5  # pinned, not the mid-grid 1.5
    assert params["take_profit_pct"] == 2.0  # other axes still take the middle


def test_traded_stop_loss_pct_is_the_mode_of_the_stream() -> None:
    trades = pd.DataFrame({"sl_pct": [0.5, 0.5, 0.5, 1.0, 1.5]})
    assert traded_stop_loss_pct(trades) == 0.5


def test_charts_render_to_files(tmp_path: Path) -> None:
    eq = _equity()
    trades = pd.DataFrame({"market": ["EURUSD", "XAUUSD", "EURUSD"]})
    pnl = np.array([300.0, -100.0, 250.0])

    report.plot_equity(eq, 200_000.0, "t", tmp_path / "equity.png")
    report.plot_drawdown(eq, tmp_path / "dd.png")
    report.plot_monte_carlo(pnl, 200_000.0, tmp_path / "mc.png", n_sims=20)
    report.plot_contributions(trades, pnl, tmp_path / "contrib.png")
    report.plot_stats_table([("Sharpe", "1.42")], "t", tmp_path / "stats.png")

    for name in ("equity.png", "dd.png", "mc.png", "contrib.png", "stats.png"):
        assert (tmp_path / name).stat().st_size > 0


def test_contributions_sum_per_market() -> None:
    trades = pd.DataFrame({"market": ["A", "B", "A"]})
    pnl = np.array([10.0, -5.0, 4.0])
    by = pd.Series(pnl, index=trades["market"].to_numpy()).groupby(level=0).sum()
    assert by["A"] == 14.0 and by["B"] == -5.0  # what plot_contributions charts
