"""Parameter sweep for RsiWprBb on real XAUUSD H4 data.

Varies the risk-management exits and the buy RSI threshold -- the highest-impact
knobs -- and records a metrics row per combination. Run from the repo root::

    uv run python -m research.engine.grid config/backtest/sweep_rsi_wpr_bb_xauusd.py

Results are written to ``reports/`` (gitignored). Edit ``PARAM_GRID`` to explore
different ranges; the grid size is the product of the list lengths.
"""

from pathlib import Path
from typing import Any

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
BID_BAR_TYPE = BarType.from_str(f"{INSTRUMENT.id}-{BAR_SPEC}-BID-EXTERNAL")
ASK_BAR_TYPE = BarType.from_str(f"{INSTRUMENT.id}-{BAR_SPEC}-ASK-EXTERNAL")

_REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = _REPO_ROOT / "catalog"
CSV_PATH = _REPO_ROOT / "data" / "XAUUSD_H4.csv"
OUT_PATH = _REPO_ROOT / "reports" / "sweep_rsi_wpr_bb_xauusd.csv"

VENUE = BacktestVenueConfig(
    name=INSTRUMENT.id.venue.value,
    oms_type="NETTING",
    account_type="MARGIN",
    base_currency="USD",
    starting_balances=["200_000 USD"],
    default_leverage=10.0,
)

# Parameters held constant across the sweep.
BASE_CONFIG: dict[str, Any] = {
    "instrument_id": str(INSTRUMENT.id),
    "bar_type": str(BID_BAR_TYPE),
    "trade_size": "100",
    "risk_per_trade_pct": 1.0,
}

# Parameters to vary (4 x 4 x 3 = 48 combinations).
PARAM_GRID: dict[str, list[Any]] = {
    "stop_loss_pct": [0.5, 1.0, 1.5, 2.0],
    "take_profit_pct": [1.0, 2.0, 3.0, 4.0],
    "buy_rsi_threshold": [35.0, 40.0, 45.0],
}


def seed_catalog(catalog_path: str | Path = CATALOG_PATH) -> int:
    """Import the XAUUSD H4 CSV (bid + ask bars) into the catalog."""
    return write_mt5_catalog(CSV_PATH, catalog_path, instrument=INSTRUMENT, bar_spec=BAR_SPEC)


def build_run_config(
    params: dict[str, Any],
    *,
    start: str | None = None,
    end: str | None = None,
) -> BacktestRunConfig:
    """Build a run config with the swept ``params`` merged onto the base config.

    ``start`` / ``end`` (ISO datetime strings) restrict the run to a time window --
    used by the walk-forward runner to isolate train and test periods.
    """
    strategy = ImportableStrategyConfig(
        strategy_path="core.strategies.rsi_wpr_bb:RsiWprBb",
        config_path="core.strategies.rsi_wpr_bb:RsiWprBbConfig",
        config={**BASE_CONFIG, **params},
    )
    data = BacktestDataConfig(
        catalog_path=str(CATALOG_PATH),
        data_cls="nautilus_trader.model.data:Bar",
        instrument_id=str(INSTRUMENT.id),
        bar_types=[str(BID_BAR_TYPE), str(ASK_BAR_TYPE)],
    )
    return BacktestRunConfig(
        venues=[VENUE],
        data=[data],
        engine=BacktestEngineConfig(
            strategies=[strategy],
            logging=LoggingConfig(bypass_logging=True),
        ),
        dispose_on_completion=False,
        start=start,
        end=end,
    )
