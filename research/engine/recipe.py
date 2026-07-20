"""Factory for per-instrument sweep recipes.

Every instrument needs the same recipe shape (venue, bid/ask data, strategy config,
parameter grid, seed + build_run_config). Rather than copy ~90 lines per instrument,
a config module builds a :class:`SweepRecipe` and re-exports its attributes::

    from research.engine.recipe import SweepRecipe
    from core.instruments import eurusd

    _R = SweepRecipe(eurusd(), "data/EURUSD_H4.csv", leverage=50.0)
    INSTRUMENT, CATALOG_PATH, CSV_PATH = _R.INSTRUMENT, _R.CATALOG_PATH, _R.CSV_PATH
    VENUE, PARAM_GRID = _R.VENUE, _R.PARAM_GRID
    seed_catalog, build_run_config = _R.seed_catalog, _R.build_run_config
"""


from pathlib import Path
from typing import Any

import pandas as pd
from core.broker import BrokerProfile
from core.data.mt5_csv import require_current_frame, require_current_sources, write_mt5_catalog
from core.paths import REPO_ROOT
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

_REPO_ROOT = REPO_ROOT

# Default parameter grid swept for every instrument (4 x 4 = 16 combinations).
# Risk parameters only. ``buy_rsi_threshold`` used to be searched here and is inert for this
# strategy -- research/config/robustness.py already drops it for that reason. Searching a signal
# parameter is also not schedulable: a continuous out-of-sample run cannot re-parameterise a
# rolling indicator mid-flight without trading the next segment on a cold engine.
DEFAULT_PARAM_GRID: dict[str, list[Any]] = {
    "stop_loss_pct": [0.5, 1.0, 1.5, 2.0],
    "take_profit_pct": [1.0, 2.0, 3.0, 4.0],
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
        start_balance: float = 200_000.0,
        risk_per_trade_pct: float = 1.0,
    ) -> None:
        self.INSTRUMENT = instrument
        self.BAR_SPEC = bar_spec
        self.CATALOG_PATH = _REPO_ROOT / "catalog"
        self.CSV_PATH = _REPO_ROOT / csv_path
        self.OUT_PATH = _REPO_ROOT / "reports" / f"sweep_{instrument.raw_symbol}.csv"
        self.PARAM_GRID = param_grid if param_grid is not None else DEFAULT_PARAM_GRID
        self.broker = broker  # None -> frictionless baseline (spread + commission only)
        # The account context the backtest sizes against -- attributes, not constants, so the trade
        # stream can recover each trade's R-multiple = pnl / (base_risk * equity_at_open).
        self.start_balance = start_balance
        self.base_risk_frac = risk_per_trade_pct / 100.0
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
            starting_balances=[f"{start_balance:.0f} USD"],
            default_leverage=leverage,
            fill_model=broker.fill_model_config() if broker is not None else None,
        )
        self._frame_checked = False  # build_run_config verifies the catalog frame once
        self._base_config: dict[str, Any] = {
            "instrument_id": str(instrument.id),
            "bar_type": str(self._bid),
            "trade_size": trade_size,
            "risk_per_trade_pct": risk_per_trade_pct,
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
        trade_from: str | None = None,
    ) -> BacktestRunConfig:
        """Build a run config with ``params`` merged onto the base config.

        ``trade_from`` marks where the READ-ONLY pre-roll ends: bars before it warm the indicators
        but place no orders, so a pre-roll trade can never move the balance that later, reported
        trades are sized from.
        """
        # Fail closed on a stale-frame catalog (checked once per recipe): every engine run goes
        # through this builder, including the stage-3 read paths that never seed and therefore
        # never pass the write funnel's own check.
        if not self._frame_checked:
            require_current_frame(self.CATALOG_PATH)
            # Same funnel, same reasoning, applied to content: these bars must have been imported
            # from the CSV that is on disk now, or the results describe data nobody can point to.
            require_current_sources(self.CATALOG_PATH, {str(self.INSTRUMENT.id): self.CSV_PATH})
            self._frame_checked = True
        gate = {"trade_from_ns": pd.Timestamp(trade_from).value} if trade_from else {}
        strategy = ImportableStrategyConfig(
            strategy_path="core.strategies.rsi_wpr_bb:RsiWprBb",
            config_path="core.strategies.rsi_wpr_bb:RsiWprBbConfig",
            config={**self._base_config, **params, **gate},
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
