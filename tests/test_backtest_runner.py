"""Tests for the high-level backtest runner and the demo run recipe.

The end-to-end run bypasses logging: NautilusTrader's global logger cannot be set
up twice in one process, so running more than one backtest per pytest session
crashes unless logging is bypassed.
"""

from pathlib import Path

from nautilus_trader.config import (
    BacktestDataConfig,
    BacktestEngineConfig,
    BacktestRunConfig,
    BacktestVenueConfig,
    ImportableStrategyConfig,
    LoggingConfig,
)
from nautilus_trader.model.data import BarType
from nautilus_trader.test_kit.providers import TestInstrumentProvider

from qplus.backtest.runner import load_config_module, run_backtest
from qplus.data_ingest.synthetic import write_synthetic_catalog

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO_CONFIG = _REPO_ROOT / "config" / "backtest" / "ema_cross_demo.py"

_INSTRUMENT = TestInstrumentProvider.audusd_cfd()
_BAR_TYPE = BarType.from_str("AUDUSD.OANDA-1-DAY-LAST-EXTERNAL")


def test_demo_build_run_config_returns_run_config() -> None:
    module = load_config_module(_DEMO_CONFIG)
    assert isinstance(module.build_run_config(), BacktestRunConfig)


def test_run_backtest_produces_trades(tmp_path: Path) -> None:
    write_synthetic_catalog(tmp_path, instrument=_INSTRUMENT, bar_type=_BAR_TYPE, bar_count=200)
    run_config = BacktestRunConfig(
        venues=[
            BacktestVenueConfig(
                name=_INSTRUMENT.id.venue.value,
                oms_type="NETTING",
                account_type="MARGIN",
                base_currency="USD",
                starting_balances=["1_000_000 USD"],
                default_leverage=30.0,
            )
        ],
        data=[
            BacktestDataConfig(
                catalog_path=str(tmp_path),
                data_cls="nautilus_trader.model.data:Bar",
                instrument_id=str(_INSTRUMENT.id),
                bar_types=[str(_BAR_TYPE)],
            )
        ],
        engine=BacktestEngineConfig(
            strategies=[
                ImportableStrategyConfig(
                    strategy_path="qplus.strategies.ema_cross:EMACross",
                    config_path="qplus.strategies.ema_cross:EMACrossConfig",
                    config={
                        "instrument_id": str(_INSTRUMENT.id),
                        "bar_type": str(_BAR_TYPE),
                        "trade_size": "100_000",
                    },
                )
            ],
            logging=LoggingConfig(bypass_logging=True),
        ),
        dispose_on_completion=False,
    )

    result = run_backtest(run_config)

    assert result.total_orders > 0
    assert result.total_positions > 0
    assert "USD" in result.stats_pnls
