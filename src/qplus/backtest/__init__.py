"""Backtest runners and wiring."""

from qplus.backtest.config import BacktestConfig
from qplus.backtest.runner import run_backtest

__all__ = ["BacktestConfig", "run_backtest"]
