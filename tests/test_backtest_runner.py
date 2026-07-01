"""Tests for the backtest runner: instrument registry, config loading, and a run."""

from decimal import Decimal
from pathlib import Path

import pytest

from qplus.backtest.config import BacktestConfig
from qplus.backtest.runner import load_config, resolve_instrument, run_backtest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO_CONFIG = _REPO_ROOT / "config" / "backtest" / "ema_cross_demo.py"


def test_resolve_known_instrument() -> None:
    instrument = resolve_instrument("AUDUSD.OANDA")
    assert str(instrument.id) == "AUDUSD.OANDA"


def test_resolve_unknown_instrument_raises() -> None:
    with pytest.raises(ValueError, match="Unknown instrument"):
        resolve_instrument("DOES.NOTEXIST")


def test_load_demo_config() -> None:
    config = load_config(_DEMO_CONFIG)
    assert isinstance(config, BacktestConfig)
    assert config.instrument_id == "AUDUSD.OANDA"


def test_run_backtest_produces_trades() -> None:
    # Small, fast run; the sine wave crosses the EMAs several times so it trades.
    config = BacktestConfig(bar_count=120, trade_size=Decimal("100_000"))
    result = run_backtest(config)
    assert result.total_orders > 0
    assert result.total_positions > 0
    assert "USD" in result.stats_pnls
