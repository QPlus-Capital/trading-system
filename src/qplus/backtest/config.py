"""Backtest runner (high-level NautilusTrader API).

This is a thin, strategy-agnostic orchestrator. It loads a run recipe -- a
``BacktestRunConfig`` built by a config module under ``config/backtest/`` -- and
executes it with a ``BacktestNode``. It contains no strategy-specific logic: which
instrument, data, venue and strategy to use all come from the config.

The config module must define ``build_run_config(catalog_path=...) -> BacktestRunConfig``
and may define ``seed_catalog(catalog_path=...) -> int`` to populate the data catalog
if it is empty (used by the synthetic demo).

Run the bundled demo from the repo root::

    uv run python -m qplus.backtest.config

or point it at another config module::

    uv run python -m qplus.backtest.config config/backtest/ema_cross_demo.py
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.backtest.results import BacktestResult
from nautilus_trader.config import BacktestRunConfig
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

# Repo root: src/qplus/backtest/runner.py -> parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
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
    spec = importlib.util.spec_from_file_location("qplus_backtest_config", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load backtest config from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
