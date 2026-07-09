"""Factory for per-instrument sweep recipes.

Every instrument needs the same recipe shape (venue, bid/ask data, strategy config,
parameter grid, seed + build_run_config). Rather than copy ~90 lines per instrument,
a config module builds a :class:`SweepRecipe` and re-exports its attributes::

    from qplus.backtest.foundation.recipe import SweepRecipe
    from qplus.instruments import eurusd_ttp

    _R = SweepRecipe(eurusd_ttp(), "data/EURUSD_H4.csv", leverage=50.0)
    INSTRUMENT, CATALOG_PATH, CSV_PATH = _R.INSTRUMENT, _R.CATALOG_PATH, _R.CSV_PATH
    VENUE, PARAM_GRID = _R.VENUE, _R.PARAM_GRID
    seed_catalog, build_run_config = _R.seed_catalog, _R.build_run_config
"""

from pathlib import Path
from typing import Any

from nautilus_trader.config import (
    BacktestDataConfig,
    BacktestEngineConfig,
    BacktestRunConfig,
    BacktestVenueConfig,
    ImportableStrategyConfig,
    LoggingConfig,
)
from nautilus_trader.model.data import BarType
from nautilus_trader.model.instruments import Instrument

from qplus.backtest.broker import BrokerProfile
from qplus.data_ingest.mt5_csv import write_mt5_catalog

_REPO_ROOT = Path(__file__).resolve().parents[4]

# Default parameter grid swept for every instrument (4 x 4 x 3 = 48 combinations).
DEFAULT_PARAM_GRID: dict[str, list[Any]] = {
    "stop_loss_pct": [0.5, 1.0, 1.5, 2.0],
    "take_profit_pct": [1.0, 2.0, 3.0, 4.0],
    "buy_rsi_threshold": [35.0, 40.0, 45.0],
}


class SweepRecipe:
    """A parameter-sweep recipe for one instrument on real MT5 H4 data."""

    def __init__(
        self,
        instrument: Instrument,
        csv_path: str,
        *,
        leverage: float,
        bar_spec: str = "4-HOUR",
        trade_size: str = "1",
        param_grid: dict[str, list[Any]] | None = None,
        config_overrides: dict[str, Any] | None = None,
        broker: BrokerProfile | None = None,
    ) -> None:
        self.INSTRUMENT = instrument
        self.BAR_SPEC = bar_spec
        self.CATALOG_PATH = _REPO_ROOT / "catalog"
        self.CSV_PATH = _REPO_ROOT / csv_path
        self.OUT_PATH = _REPO_ROOT / "reports" / f"sweep_{instrument.raw_symbol}.csv"
        self.PARAM_GRID = param_grid if param_grid is not None else DEFAULT_PARAM_GRID
        self.broker = broker  # None -> frictionless baseline (spread + commission only)
        self._bid = BarType.from_str(f"{instrument.id}-{bar_spec}-BID-EXTERNAL")
        self._ask = BarType.from_str(f"{instrument.id}-{bar_spec}-ASK-EXTERNAL")
        self.VENUE = BacktestVenueConfig(
            name=instrument.id.venue.value,
            # HEDGING (not NETTING): the reversal strategy is only ever in one direction at a time,
            # so it is economically identical (account P&L matches to the cent), but each round trip
            # is tracked as its own closed Position. NETTING instead reports one continuously-netted
            # position with cumulative-average prices per snapshot, which blends entry/exit across
            # reversals -> false per-trade R (the -34R "tail" artifact). HEDGING gives clean trades.
            oms_type="HEDGING",
            account_type="MARGIN",
            base_currency="USD",
            starting_balances=["200_000 USD"],
            default_leverage=leverage,
            fill_model=broker.fill_model_config() if broker is not None else None,
        )
        self._base_config: dict[str, Any] = {
            "instrument_id": str(instrument.id),
            "bar_type": str(self._bid),
            "trade_size": trade_size,
            "risk_per_trade_pct": 1.0,
            **(config_overrides or {}),  # e.g. long_only, use_rsi_filter for studies
        }

    def seed_catalog(self, catalog_path: str | Path | None = None) -> int:
        """Import this instrument's CSV (bid + ask bars) into the catalog."""
        return write_mt5_catalog(
            self.CSV_PATH,
            catalog_path or self.CATALOG_PATH,
            instrument=self.INSTRUMENT,
            bar_spec=self.BAR_SPEC,
        )

    def build_run_config(
        self,
        params: dict[str, Any],
        *,
        start: str | None = None,
        end: str | None = None,
    ) -> BacktestRunConfig:
        """Build a run config with ``params`` merged onto the base config."""
        strategy = ImportableStrategyConfig(
            strategy_path="qplus.strategies.rsi_wpr_bb:RsiWprBb",
            config_path="qplus.strategies.rsi_wpr_bb:RsiWprBbConfig",
            config={**self._base_config, **params},
        )
        data = BacktestDataConfig(
            catalog_path=str(self.CATALOG_PATH),
            data_cls="nautilus_trader.model.data:Bar",
            instrument_id=str(self.INSTRUMENT.id),
            bar_types=[str(self._bid), str(self._ask)],
        )
        return BacktestRunConfig(
            venues=[self.VENUE],
            data=[data],
            engine=BacktestEngineConfig(
                strategies=[strategy],
                logging=LoggingConfig(bypass_logging=True),
            ),
            dispose_on_completion=False,
            start=start,
            end=end,
        )
