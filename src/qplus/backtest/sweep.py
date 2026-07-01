"""Parameter sweep: run one strategy across many parameter combinations.

A sweep runs the *same* strategy over a grid of parameter values, collecting a
metrics row per run into a table so the combinations can be ranked. Each run is a
separate ``BacktestNode`` (with logging bypassed, so many runs can execute in one
process); results are written incrementally, so a long background sweep can be
interrupted without losing progress.

A sweep config module (under ``config/backtest/``) must define:

- ``INSTRUMENT`` and ``CATALOG_PATH`` (to check/seed data),
- ``seed_catalog()`` (populate the catalog if the instrument is missing),
- ``PARAM_GRID`` -- ``dict[name, list_of_values]`` of parameters to vary,
- ``build_run_config(params: dict) -> BacktestRunConfig``,
- ``OUT_PATH`` -- where to write the results CSV.
"""

import itertools
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd
from nautilus_trader.backtest.results import BacktestResult
from nautilus_trader.config import BacktestRunConfig
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from qplus.backtest.runner import load_config_module, run_backtest

Factory = Callable[[dict[str, Any]], BacktestRunConfig]
Runner = Callable[[BacktestRunConfig], BacktestResult]

_MIN_TRADES = 30  # ignore combinations with too few trades when ranking


def expand_grid(grid: Mapping[str, Sequence[Any]]) -> list[dict[str, Any]]:
    """Return every combination of the grid as a list of parameter dicts."""
    keys = list(grid)
    return [
        dict(zip(keys, values, strict=True))
        for values in itertools.product(*(grid[k] for k in keys))
    ]


def result_row(
    params: dict[str, Any],
    result: BacktestResult,
    currency: str = "USD",
) -> dict[str, Any]:
    """Flatten a backtest result into a metrics row (the swept params plus stats)."""
    pnl = result.stats_pnls.get(currency, {}) if result.stats_pnls else {}
    returns = result.stats_returns or {}
    return {
        **params,
        "trades": result.total_positions,
        "pnl": pnl.get("PnL (total)"),
        "pnl_pct": pnl.get("PnL% (total)"),
        "win_rate": pnl.get("Win Rate"),
        "profit_factor": returns.get("Profit Factor"),
        "sharpe": returns.get("Sharpe Ratio (252 days)"),
    }


def run_sweep(
    factory: Factory,
    grid: Mapping[str, Sequence[Any]],
    *,
    runner: Runner = run_backtest,
    out_path: str | Path | None = None,
) -> pd.DataFrame:
    """Run the strategy for every combination in ``grid`` and collect the metrics."""
    combos = expand_grid(grid)
    rows: list[dict[str, Any]] = []
    for i, params in enumerate(combos, start=1):
        result = runner(factory(params))
        row = result_row(params, result)
        rows.append(row)
        print(f"[{i}/{len(combos)}] {params} -> pnl={row['pnl']} trades={row['trades']}")
        if out_path is not None:
            pd.DataFrame(rows).to_csv(out_path, index=False)
    return pd.DataFrame(rows)


def _rank(df: pd.DataFrame) -> pd.DataFrame:
    """Rank combinations: enough trades first, then by profit factor."""
    eligible = df[df["trades"] >= _MIN_TRADES]
    if eligible.empty:
        return df.sort_values("pnl", ascending=False)
    return eligible.sort_values("profit_factor", ascending=False)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: load a sweep config module, run it, print the ranking."""
    args = sys.argv[1:] if argv is None else argv
    if not args:
        raise SystemExit("usage: python -m qplus.backtest.sweep <sweep_config.py>")
    module = load_config_module(Path(args[0]))

    catalog_dir = Path(module.CATALOG_PATH)
    needed = str(module.INSTRUMENT.id)
    have = (
        {str(i.id) for i in ParquetDataCatalog(str(catalog_dir)).instruments()}
        if catalog_dir.exists()
        else set()
    )
    if needed not in have:
        print(f"Instrument {needed} not in catalog -> seeding ...")
        module.seed_catalog()

    out_path = Path(module.OUT_PATH)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = run_sweep(module.build_run_config, module.PARAM_GRID, out_path=out_path)

    ranked = _rank(df)
    print("\n===== Top 10 (ranked) =====")
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(ranked.head(10).to_string(index=False))
    print(f"\nFull results ({len(df)} runs): {out_path}")


if __name__ == "__main__":
    main()
