"""Tests for the high-level backtest runner and the demo run recipe."""

from pathlib import Path

from nautilus_trader.config import BacktestRunConfig

from qplus.backtest.runner import load_config_module, run_backtest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO_CONFIG = _REPO_ROOT / "config" / "backtest" / "ema_cross_demo.py"


def test_demo_build_run_config_returns_run_config() -> None:
    module = load_config_module(_DEMO_CONFIG)
    run_config = module.build_run_config()
    assert isinstance(run_config, BacktestRunConfig)


def test_run_backtest_produces_trades(tmp_path: Path) -> None:
    # Seed a throwaway catalog and run the demo recipe against it end-to-end.
    module = load_config_module(_DEMO_CONFIG)
    module.seed_catalog(tmp_path)
    run_config = module.build_run_config(tmp_path)

    result = run_backtest(run_config)

    assert result.total_orders > 0
    assert result.total_positions > 0
    assert "USD" in result.stats_pnls
