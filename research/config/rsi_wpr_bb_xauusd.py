"""Backtest recipe: RSI/Williams %R/Bollinger strategy on REAL XAUUSD H4 data.

Uses gold (XAUUSD) H4 bars exported from The Trading Pit's MetaTrader 5. The import
writes BID and ASK bars into the catalog, so the simulated exchange fills buys at the
ask and sells at the bid -- the real per-bar spread is a cost. Commission (0.0007%
per side) comes from the instrument definition. Run from the repo root::

    uv run python -m research.engine.config config/backtest/rsi_wpr_bb_xauusd.py

The CSV lives in the gitignored ``data/`` folder; if the catalog does not yet
contain XAUUSD, the runner imports it via ``seed_catalog()``.
"""

from pathlib import Path

from core.data.mt5_csv import write_mt5_catalog
from core.instruments import xauusd_ttp
from nautilus_trader.config import (
    BacktestDataConfig,
    BacktestEngineConfig,
    BacktestRunConfig,
    BacktestVenueConfig,
    ImportableStrategyConfig,
    LoggingConfig,
)
from nautilus_trader.model.data import BarType

INSTRUMENT = xauusd_ttp()
BAR_SPEC = "4-HOUR"
# The strategy trades on the BID series; the ASK series only feeds realistic fills.
BID_BAR_TYPE = BarType.from_str(f"{INSTRUMENT.id}-{BAR_SPEC}-BID-EXTERNAL")
ASK_BAR_TYPE = BarType.from_str(f"{INSTRUMENT.id}-{BAR_SPEC}-ASK-EXTERNAL")

_REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = _REPO_ROOT / "catalog"
CSV_PATH = _REPO_ROOT / "data" / "XAUUSD_H4.csv"

VENUE = BacktestVenueConfig(
    name=INSTRUMENT.id.venue.value,
    oms_type="NETTING",
    account_type="MARGIN",
    base_currency="USD",
    starting_balances=["200_000 USD"],
    default_leverage=10.0,  # ~10:1, from the broker's margin (~10% of notional)
)

STRATEGY = ImportableStrategyConfig(
    strategy_path="core.strategies.rsi_wpr_bb:RsiWprBb",
    config_path="core.strategies.rsi_wpr_bb:RsiWprBbConfig",
    config={
        "instrument_id": str(INSTRUMENT.id),
        "bar_type": str(BID_BAR_TYPE),
        "trade_size": "100",  # ounces (fallback if risk sizing is off)
        # Strategy parameters (defaults mirror the Pine script); tune these later.
        "wpr_length": 14,
        "ema_length": 10,
        "rsi_length": 14,
        "bb_length": 20,
        "bb_mult": 2.0,
        # Risk management. These SL/TP values are the in-sample best from the
        # parameter sweep (see sweep_rsi_wpr_bb_xauusd.py) -- promising but NOT yet
        # out-of-sample validated, so treat with caution.
        "stop_loss_pct": 0.5,
        "take_profit_pct": 4.0,
        "risk_per_trade_pct": 1.0,
    },
)


def seed_catalog(catalog_path: str | Path = CATALOG_PATH) -> int:
    """Import the XAUUSD H4 CSV (bid + ask bars) into the catalog."""
    return write_mt5_catalog(
        CSV_PATH,
        catalog_path,
        instrument=INSTRUMENT,
        bar_spec=BAR_SPEC,
    )


def build_run_config(
    catalog_path: str | Path = CATALOG_PATH,
    *,
    bypass_logging: bool = False,
    start: str | None = None,
    end: str | None = None,
) -> BacktestRunConfig:
    """Compose the XAUUSD backtest run recipe.

    ``start`` / ``end`` (ISO datetime strings) restrict the run to a time window --
    used by the stress runner to isolate crisis periods.
    """
    data = BacktestDataConfig(
        catalog_path=str(catalog_path),
        data_cls="nautilus_trader.model.data:Bar",
        instrument_id=str(INSTRUMENT.id),
        bar_types=[str(BID_BAR_TYPE), str(ASK_BAR_TYPE)],
    )
    return BacktestRunConfig(
        venues=[VENUE],
        data=[data],
        engine=BacktestEngineConfig(
            strategies=[STRATEGY],
            logging=LoggingConfig(bypass_logging=bypass_logging),
        ),
        dispose_on_completion=False,
        start=start,
        end=end,
    )
