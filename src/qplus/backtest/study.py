"""Overnight robustness study: walk-forward every (instrument x variation) in parallel.

For each instrument and each named strategy variation (e.g. a component switched off,
a different risk level), this runs the full clean walk-forward and records the
out-of-sample metrics. Tasks run across several processes; the catalog is seeded once
up front (workers then only read it).

The result is ranked by variation *averaged across instruments* -- so a change only
"wins" if it helps out-of-sample across many markets, which guards against picking a
per-instrument fluke.

A study config module must define ``INSTRUMENTS`` (list of ``(factory, csv, leverage)``),
``VARIATIONS`` (``dict[name, config_overrides]``), ``PARAM_GRID`` and optionally
``MAX_WORKERS``.

Usage (append a number to limit windows for a quick test)::

    uv run python -m qplus.backtest.study config/study/overnight.py
    uv run python -m qplus.backtest.study config/study/overnight.py 1
"""

import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pandas as pd
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from qplus.backtest.recipe_factory import SweepRecipe
from qplus.backtest.runner import load_config_module
from qplus.backtest.walkforward import walk_forward_efficiency
from qplus.backtest.walkforward_run import run_walkforward

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _run_task(
    factory: Any,
    csv: str,
    leverage: float,
    param_grid: dict[str, list[Any]],
    variation: str,
    overrides: dict[str, Any],
    symbol: str,
    max_windows: int | None,
) -> dict[str, Any]:
    """Walk-forward one (instrument, variation) and return its OOS metrics."""
    recipe = SweepRecipe(
        factory(), csv, leverage=leverage, param_grid=param_grid, config_overrides=overrides
    )
    results = run_walkforward(recipe, max_windows=max_windows)
    oos = [r.oos_return for r in results]
    mean_oos = sum(oos) / len(oos) if oos else 0.0
    pct = sum(1 for x in oos if x > 0) / len(oos) if oos else 0.0
    return {
        "instrument": symbol,
        "variation": variation,
        "windows": len(results),
        "mean_oos_pct": round(mean_oos * 100, 2),
        "pct_profitable": round(pct * 100, 0),
        "wfe": round(walk_forward_efficiency(results), 3),
        "oos_trades": sum(r.oos_trades for r in results),
    }


def main(argv: list[str] | None = None) -> None:
    """CLI: run the study defined in a config module across processes."""
    args = sys.argv[1:] if argv is None else argv
    if not args:
        raise SystemExit("usage: python -m qplus.backtest.study <study_config.py> [max_windows]")
    cfg = load_config_module(Path(args[0]))
    max_windows = int(args[1]) if len(args) > 1 else None
    workers = int(getattr(cfg, "MAX_WORKERS", 4))

    # Seed every instrument's data once (serially); workers then only read the catalog.
    catalog = _REPO_ROOT / "catalog"
    have = (
        {str(i.id) for i in ParquetDataCatalog(str(catalog)).instruments()}
        if catalog.exists()
        else set()
    )
    for factory, csv, leverage in cfg.INSTRUMENTS:
        recipe = SweepRecipe(factory(), csv, leverage=leverage)
        if str(recipe.INSTRUMENT.id) not in have:
            print(f"seeding {recipe.INSTRUMENT.id} ...")
            recipe.seed_catalog()
            have.add(str(recipe.INSTRUMENT.id))

    tasks = [
        (
            factory,
            csv,
            leverage,
            cfg.PARAM_GRID,
            name,
            overrides,
            str(factory().raw_symbol),
            max_windows,
        )
        for factory, csv, leverage in cfg.INSTRUMENTS
        for name, overrides in cfg.VARIATIONS.items()
    ]
    n_inst, n_var = len(cfg.INSTRUMENTS), len(cfg.VARIATIONS)
    print(f"{len(tasks)} tasks ({n_inst} instruments x {n_var} variations) on {workers} workers")

    rows: list[dict[str, Any]] = []
    out = _REPO_ROOT / "reports" / "study.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_run_task, *task): (task[6], task[4]) for task in tasks}
        for i, future in enumerate(as_completed(futures), start=1):
            symbol, variation = futures[future]
            try:
                row = future.result()
            except Exception as exc:  # record the failure and continue the batch
                row = {"instrument": symbol, "variation": variation, "error": str(exc)[:100]}
            rows.append(row)
            pd.DataFrame(rows).to_csv(out, index=False)  # save after every task
            mins = (time.time() - started) / 60
            oos = row.get("mean_oos_pct")
            print(f"[{i}/{len(tasks)}] {symbol}/{variation}: {oos}% ({mins:.1f} min)")

    df = pd.DataFrame(rows)
    if "mean_oos_pct" in df.columns:
        agg = (
            df.dropna(subset=["mean_oos_pct"])
            .groupby("variation")
            .agg(
                mean_oos_pct=("mean_oos_pct", "mean"),
                mean_profitable=("pct_profitable", "mean"),
                mean_wfe=("wfe", "mean"),
            )
            .sort_values("mean_oos_pct", ascending=False)
        )
        print("\n===== Variation ranking (mean across instruments) =====")
        print(agg.round(2).to_string())
    print(f"\nFull results: {out}")


if __name__ == "__main__":
    main()
