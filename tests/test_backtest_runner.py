"""Tests for the high-level backtest runner and loading a run recipe."""

from pathlib import Path

from nautilus_trader.config import BacktestRunConfig

from qplus.backtest.runner import load_config_module

_REPO_ROOT = Path(__file__).resolve().parents[1]
_RECIPE = _REPO_ROOT / "config" / "backtest" / "rsi_wpr_bb_xauusd.py"


def test_recipe_build_run_config_returns_run_config() -> None:
    # Building the recipe's run config does not require any data on disk.
    module = load_config_module(_RECIPE)
    assert isinstance(module.build_run_config(), BacktestRunConfig)
