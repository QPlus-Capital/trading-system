"""Backtest runner (high-level NautilusTrader API).

This is a thin, strategy-agnostic orchestrator. It loads a run recipe -- a
``BacktestRunConfig`` built by a config module under ``config/backtest/`` -- and
executes it with a ``BacktestNode``. It contains no strategy-specific logic: which
instrument, data, venue and strategy to use all come from the config.

The config module must define ``build_run_config(catalog_path=...) -> BacktestRunConfig``
and may define ``seed_catalog(catalog_path=...) -> int`` to populate the data catalog
if it is empty (used by the synthetic demo).

Run the bundled demo from the repo root::

    uv run python -m research.engine.config

or point it at another config module::

    uv run python -m research.engine.config config/backtest/rsi_wpr_bb_xauusd.py
"""


import importlib.util
from pathlib import Path
from types import ModuleType

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


def _parse_money(value: object) -> float:
    """Parse a NautilusTrader money string like ``'1784.69 USD'`` into a float."""
    return float(str(value).split()[0].replace("_", ""))


def extract_trade_pnls(run_config: BacktestRunConfig) -> tuple[list[float], float]:
    """Run the config and return (realized PnL per trade, starting equity).

    A window can legitimately produce ZERO trades -- a variation with fewer signals (longer EMA),
    long-only skipping every short, or simply a quiet stretch on one market. NautilusTrader then
    returns an empty positions report with no ``realized_pnl`` column, so guard for it: no trades is
    an empty PnL list (a flat, zero-return window), never a crashed task.
    """
    node = BacktestNode(configs=[run_config])
    try:
        node.run()
        engine = node.get_engines()[0]
        positions = engine.trader.generate_positions_report()
        if "realized_pnl" in positions.columns:
            pnls = [_parse_money(v) for v in positions["realized_pnl"]]
        else:
            pnls = []
    finally:
        node.dispose()  # type: ignore[no-untyped-call]
    start_equity = _parse_money(run_config.venues[0].starting_balances[0])
    return pnls, start_equity
