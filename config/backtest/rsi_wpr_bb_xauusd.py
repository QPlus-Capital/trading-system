"""Backtest recipe: RSI/Williams %R/Bollinger strategy on REAL XAUUSD H4 data.

Uses gold (XAUUSD) H4 bars exported from The Trading Pit's MetaTrader 5 and
imported into the Parquet catalog. Run from the repo root::

    uv run python -m qplus.backtest.runner config/backtest/rsi_wpr_bb_xauusd.py

The CSV lives in the gitignored ``data/`` folder; if the catalog does not yet
contain XAUUSD, the runner imports it via ``seed_catalog()``.
"""

from pathlib import Path

from nautilus_trader.config import (
    BacktestDataConfig,
    BacktestEngineConfig,
    BacktestRunConfig,
    BacktestVenueConfig,
    ImportableStrategyConfig,
)
from nautilus_trader.model.data import BarType

from qplus.data_ingest.mt5_csv import write_mt5_catalog
from qplus.instruments import xauusd_ttp

INSTRUMENT = xauusd_ttp()
BAR_TYPE = BarType.from_str(f"{INSTRUMENT.id}-4-HOUR-LAST-EXTERNAL")

_REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = _REPO_ROOT / "catalog"
CSV_PATH = _REPO_ROOT / "data" / "XAUUSD_H4.csv"

VENUE = BacktestVenueConfig(
    name=INSTRUMENT.id.venue.value,
    oms_type="NETTING",
    account_type="MARGIN",
    base_currency="USD",
    starting_balances=["100_000 USD"],
    default_leverage=20.0,
)

STRATEGY = ImportableStrategyConfig(
    strategy_path="qplus.strategies.rsi_wpr_bb:RsiWprBb",
    config_path="qplus.strategies.rsi_wpr_bb:RsiWprBbConfig",
    config={
        "instrument_id": str(INSTRUMENT.id),
        "bar_type": str(BAR_TYPE),
        "trade_size": "100",  # ounces (fallback if risk sizing is off)
        # Strategy parameters (defaults mirror the Pine script); tune these later.
        "wpr_length": 14,
        "ema_length": 10,
        "rsi_length": 14,
        "bb_length": 20,
        "bb_mult": 2.0,
        # Risk management: 1% stop, 2% target, risk 1% of equity per trade.
        "stop_loss_pct": 1.0,
        "take_profit_pct": 2.0,
        "risk_per_trade_pct": 1.0,
    },
)


def seed_catalog(catalog_path: str | Path = CATALOG_PATH) -> int:
    """Import the XAUUSD H4 CSV into the catalog."""
    return write_mt5_catalog(
        CSV_PATH,
        catalog_path,
        instrument=INSTRUMENT,
        bar_type=BAR_TYPE,
    )


def build_run_config(catalog_path: str | Path = CATALOG_PATH) -> BacktestRunConfig:
    """Compose the XAUUSD backtest run recipe."""
    data = BacktestDataConfig(
        catalog_path=str(catalog_path),
        data_cls="nautilus_trader.model.data:Bar",
        instrument_id=str(INSTRUMENT.id),
        bar_types=[str(BAR_TYPE)],
    )
    return BacktestRunConfig(
        venues=[VENUE],
        data=[data],
        engine=BacktestEngineConfig(strategies=[STRATEGY]),
        dispose_on_completion=False,
    )
