"""Backtest execution helpers (high-level NautilusTrader API).

Strategy-agnostic library used across the research pipeline:

- ``run_backtest(run_config)`` executes a ``BacktestRunConfig`` with a ``BacktestNode``;
- ``extract_closed_positions(run_config)`` runs it and retains the closed-position fields needed
  to price realized costs such as swap;
- ``extract_trade_pnls(run_config)`` is the gross-PnL compatibility view of that report;
- ``load_config_module(path)`` loads a config module by path (it defines
  ``build_run_config(...) -> BacktestRunConfig`` and, for the synthetic demo, ``seed_catalog``).

Config modules live under ``research/config/`` (study) and ``live/config/`` (the frozen live
config). There is no CLI here -- the staged framework (``research.stages``) is the entry point.
"""


import importlib.util
from pathlib import Path
from types import ModuleType

import pandas as pd
from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.backtest.results import BacktestResult
from nautilus_trader.config import BacktestRunConfig


def run_backtest(run_config: BacktestRunConfig) -> BacktestResult:
    """Run a single backtest run config and return its result.

    Parameters
    ----------
    run_config : BacktestRunConfig
        The fully composed run recipe (venue, data, strategy).

    Returns
    -------
    BacktestResult
        The result of the run (orders, positions, PnL statistics, ...).
    """
    node = BacktestNode(configs=[run_config])
    try:
        return node.run()[0]
    finally:
        node.dispose()  # type: ignore[no-untyped-call]


def load_config_module(path: Path) -> ModuleType:
    """Load a backtest config module from a Python file at ``path``."""
    spec = importlib.util.spec_from_file_location("loaded_config", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load backtest config from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_money(value: object) -> float:
    """Parse a report or venue-config money string into a float."""
    return float(str(value).split()[0])


def extract_trade_pnls(
    run_config: BacktestRunConfig, *, closed_from: pd.Timestamp | None = None
) -> tuple[list[float], float]:
    """Run the config and return gross ``(realized PnL per trade, starting equity)``.

    Use :func:`extract_closed_positions` when a caller needs timestamps, direction, prices, or
    stop distance to apply a post-engine realized cost. Reducing the report to money here is
    intentionally only the compatibility view.
    """
    closed, start_equity = extract_closed_positions(run_config, closed_from=closed_from)
    pnls = (
        [parse_money(value) for value in closed["realized_pnl"]]
        if "realized_pnl" in closed.columns
        else []
    )
    return pnls, start_equity


def extract_closed_positions(
    run_config: BacktestRunConfig, *, closed_from: pd.Timestamp | None = None
) -> tuple[pd.DataFrame, float]:
    """Run the config and return ``(closed positions report, starting equity)``.

    A window can legitimately produce ZERO trades -- a variation with fewer signals (longer EMA),
    long-only skipping every short, or simply a quiet stretch on one market. NautilusTrader then
    returns an empty positions report with no ``realized_pnl`` column, so an empty report is a
    flat, zero-return window, never a crashed task.

    ``closed_from`` keeps only positions that CLOSED at or after that moment (#14) -- a safety net
    for the READ-ONLY pre-roll, which warms the indicators without placing orders.

    It does NOT make the stream continuous OOS: because the pre-roll cannot open a position, one
    opened just before a boundary is not carried into the next window. That seam gap is deliberate
    (a trading pre-roll would move the balance the reported trades are sized from) and tracked
    separately in #23.
    """
    node = BacktestNode(configs=[run_config])
    try:
        node.run()
        engine = node.get_engines()[0]
        positions = engine.trader.generate_positions_report()
        closed = positions
        if "ts_closed" in positions.columns:  # absent only when nothing ever closed
            closed = closed[closed["ts_closed"].notna()]
            if closed_from is not None:
                closed = closed[pd.to_datetime(closed["ts_closed"], utc=True) >= closed_from]
        closed = closed.copy()
    finally:
        node.dispose()  # type: ignore[no-untyped-call]
    start_equity = parse_money(run_config.venues[0].starting_balances[0])
    return closed, start_equity
