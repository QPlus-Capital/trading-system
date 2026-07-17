"""Tests for the parameter-sweep logic (no real backtests are run)."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from nautilus_trader.backtest.results import BacktestResult
from research.engine.grid import expand_grid, result_row, run_sweep


def test_expand_grid_cartesian_product() -> None:
    grid: dict[str, list[Any]] = {"a": [1, 2], "b": [3, 4]}
    combos = expand_grid(grid)
    assert combos == [
        {"a": 1, "b": 3},
        {"a": 1, "b": 4},
        {"a": 2, "b": 3},
        {"a": 2, "b": 4},
    ]


def _fake_result(pnl: float, trades: int, pf: float) -> BacktestResult:
    return cast(
        BacktestResult,
        SimpleNamespace(
            total_positions=trades,
            stats_pnls={"USD": {"PnL (total)": pnl, "PnL% (total)": pnl / 1000, "Win Rate": 0.5}},
            stats_returns={"Profit Factor": pf, "Sharpe Ratio (252 days)": 0.9},
        ),
    )


def test_result_row_flattens_metrics() -> None:
    row = result_row({"stop_loss_pct": 1.0}, _fake_result(pnl=250.0, trades=42, pf=1.3))
    assert row["stop_loss_pct"] == 1.0
    assert row["trades"] == 42
    assert row["pnl"] == 250.0
    assert row["profit_factor"] == 1.3
    assert row["win_rate"] == 0.5


def test_run_sweep_collects_rows_and_writes_csv(tmp_path: Path) -> None:
    grid: dict[str, list[Any]] = {"stop_loss_pct": [1.0, 2.0]}
    out = tmp_path / "sweep.csv"

    # Fake factory/runner: no engine is started; PnL is derived from the params.
    def fake_runner(run_config: Any) -> BacktestResult:
        return _fake_result(pnl=run_config["stop_loss_pct"] * 100, trades=50, pf=1.1)

    df = run_sweep(
        factory=lambda params: cast(Any, params),
        grid=grid,
        runner=fake_runner,
        out_path=out,
    )
    assert len(df) == 2
    assert set(df["stop_loss_pct"]) == {1.0, 2.0}
    assert out.exists()  # written incrementally
