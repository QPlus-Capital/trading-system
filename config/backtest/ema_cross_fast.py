"""Demo backtest recipe: FASTER EMA crossover on synthetic AUD/USD daily bars.

This is a copy of ``ema_cross_demo.py`` with only the two EMA periods changed
(5/15 instead of 10/20) -- an example of how you experiment: copy a recipe, change
a couple of numbers, run it. Everything else (instrument, data, venue, strategy
code) is identical, so you can compare the two runs directly.

Run it from the repo root::

    uv run python -m qplus.backtest.runner config/backtest/ema_cross_fast.py
"""

from decimal import Decimal
from pathlib import Path

from nautilus_trader.config import (
    BacktestDataConfig,
    BacktestEngineConfig,
    BacktestRunConfig,
    BacktestVenueConfig,
    ImportableStrategyConfig,
)
from nautilus_trader.model.data import BarType
from nautilus_trader.test_kit.providers import TestInstrumentProvider

from qplus.data_ingest.synthetic import write_synthetic_catalog

# Same instrument, bar type and catalog as the demo recipe.
INSTRUMENT = TestInstrumentProvider.audusd_cfd()
BAR_TYPE = BarType.from_str(f"{INSTRUMENT.id}-1-DAY-LAST-EXTERNAL")
CATALOG_PATH = Path(__file__).resolve().parents[2] / "catalog"

_SYNTH: dict[str, object] = {
    "bar_count": 300,
    "start_time": "2020-01-01",
    "start_price": Decimal("0.70000"),
    "wave_amplitude": Decimal("0.03"),
    "wave_period_bars": 40,
    "bar_half_range": Decimal("0.0005"),
}

VENUE = BacktestVenueConfig(
    name=INSTRUMENT.id.venue.value,
    oms_type="NETTING",
    account_type="MARGIN",
    base_currency="USD",
    starting_balances=["1_000_000 USD"],
    default_leverage=30.0,
)

STRATEGY = ImportableStrategyConfig(
    strategy_path="qplus.strategies.ema_cross:EMACross",
    config_path="qplus.strategies.ema_cross:EMACrossConfig",
    config={
        "instrument_id": str(INSTRUMENT.id),
        "bar_type": str(BAR_TYPE),
        "trade_size": "100_000",
        "fast_ema_period": 5,  # <-- changed from 10
        "slow_ema_period": 15,  # <-- changed from 20
    },
)


def seed_catalog(catalog_path: str | Path = CATALOG_PATH) -> int:
    """Write the synthetic instrument + bars into the data catalog."""
    return write_synthetic_catalog(
        catalog_path,
        instrument=INSTRUMENT,
        bar_type=BAR_TYPE,
        **_SYNTH,
    )


def build_run_config(catalog_path: str | Path = CATALOG_PATH) -> BacktestRunConfig:
    """Compose the full backtest run recipe."""
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
