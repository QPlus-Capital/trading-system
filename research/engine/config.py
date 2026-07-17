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
import sys
from pathlib import Path
from types import ModuleType

from core.paths import REPO_ROOT
from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.backtest.results import BacktestResult
from nautilus_trader.config import BacktestRunConfig
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

_REPO_ROOT = REPO_ROOT
_DEFAULT_CONFIG = _REPO_ROOT / "config" / "backtest" / "rsi_wpr_bb_xauusd.py"


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


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: load a config module, ensure data exists, run the backtest."""
    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0]) if args else _DEFAULT_CONFIG

    module = load_config_module(path)
    run_config = module.build_run_config()
    data_config = run_config.data[0]
    catalog_dir = Path(data_config.catalog_path)

    # Seed only if this run's instrument is missing (catalogs may hold several).
    needed = str(data_config.instrument_id)
    have = (
        {str(i.id) for i in ParquetDataCatalog(str(catalog_dir)).instruments()}
        if catalog_dir.exists()
        else set()
    )
    if needed not in have:
        print(f"Instrument {needed} not in catalog {catalog_dir} -> seeding ...")
        count = module.seed_catalog()
        print(f"Wrote {count} bars.")

    result = run_backtest(run_config)

    print("\n===== Backtest result =====")
    print(f"config:          {path}")
    print(f"total orders:    {result.total_orders}")
    print(f"total positions: {result.total_positions}")
    for ccy, stats in result.stats_pnls.items():
        print(f"PnL [{ccy}]:      {stats.get('PnL (total)')}  ({stats.get('PnL% (total)')}%)")


if __name__ == "__main__":
    main()
