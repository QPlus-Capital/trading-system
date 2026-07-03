"""Overnight robustness study: walk-forward every (instrument x variation) in parallel.

For each instrument and each named strategy variation (e.g. a component switched off,
a different risk level), this runs the full clean walk-forward and records the
out-of-sample metrics. Tasks run across several processes; the catalog is seeded once
up front (workers then only read it).

The result is ranked by variation **risk-adjusted** (out-of-sample return per unit of
drawdown, ``return_per_dd``) and *averaged across instruments* -- so a change only "wins"
if it improves the risk-adjusted OOS across many markets (the framework's risk lens; raw
return is never the ranking key). It also reports, per variation:

* ``oos_maxdd_pct`` -- mean out-of-sample max drawdown per window,
* ``worst_market_pct`` -- the weakest instrument (robustness floor),
* ``wfe_norm`` -- length-normalized walk-forward efficiency (~0.5+ generalizes),
* ``oos_sharpe`` -- Sharpe of the pooled per-window OOS returns,
* ``dsr`` -- deflated Sharpe, correcting for how many variations were tried, so an
  edge that is really just multiple-testing noise shows up as a low DSR.

Everything lands in a single timestamped folder ``reports/study/run_<ts>/`` (which is
git-ignored): ``study.csv`` (full table), ``ranking.csv``, a variation x instrument
heatmap and Monte-Carlo charts for the top few variations only -- so the reports
folder does not fill up with one chart per variation.

A study config module must define ``INSTRUMENTS`` (list of ``(factory, csv, leverage)``),
``VARIATIONS`` (``dict[name, config_overrides]``) and ``PARAM_GRID``; it may also set
``MAX_WORKERS`` and the walk-forward sizing ``TRAIN_MONTHS`` / ``TEST_MONTHS`` /
``STEP_MONTHS``.

Usage (append a number to limit windows for a quick test)::

    uv run python -m qplus.backtest.edge.characterize config/study/overnight.py
    uv run python -m qplus.backtest.edge.characterize config/study/overnight.py 1
"""

import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from qplus.backtest.config import load_config_module
from qplus.backtest.edge.engine import run_walkforward
from qplus.backtest.edge.walkforward import normalized_wfe, walk_forward_efficiency
from qplus.backtest.foundation.recipe import SweepRecipe

_REPO_ROOT = Path(__file__).resolve().parents[4]
_START_EQUITY = 200_000.0  # matches SweepRecipe.VENUE starting balance

# Per-task list payloads kept in memory for reporting but dropped from the CSV.
_LIST_KEYS = ("window_oos", "trade_oos")


def _run_task(
    factory: Any,
    csv: str,
    leverage: float,
    param_grid: dict[str, list[Any]],
    variation: str,
    overrides: dict[str, Any],
    symbol: str,
    train_months: int,
    test_months: int,
    step_months: int,
    max_windows: int | None,
    holdout_months: int,
    embargo_days: int,
) -> dict[str, Any]:
    """Walk-forward one (instrument, variation) and return its OOS metrics + return series."""
    recipe = SweepRecipe(
        factory(), csv, leverage=leverage, param_grid=param_grid, config_overrides=overrides
    )
    # Selection runs on the pre-holdout data only, so the reserved slice stays untouched (F2).
    results = run_walkforward(
        recipe,
        train_months=train_months,
        test_months=test_months,
        step_months=step_months,
        max_windows=max_windows,
        holdout_months=holdout_months,
        phase="select",
        embargo_days=embargo_days,
    )
    oos = [r.oos_return for r in results]
    mean_oos = sum(oos) / len(oos) if oos else 0.0
    pct = sum(1 for x in oos if x > 0) / len(oos) if oos else 0.0
    mean_dd = sum(r.oos_max_dd for r in results) / len(results) if results else 0.0
    # Risk-adjusted ranking key (the "risk lens"): OOS return per unit of OOS drawdown.
    # Floor the denominator at a realistic minimum (0.5%) so a tiny-drawdown config cannot
    # produce an exploding, unstable ratio (F7). It is a per-window proxy for account Calmar.
    ret_per_dd = mean_oos / max(mean_dd, 0.005) if results else 0.0
    return {
        "instrument": symbol,
        "variation": variation,
        "train_months": train_months,
        "windows": len(results),
        "mean_oos_pct": round(mean_oos * 100, 2),
        "oos_maxdd_pct": round(mean_dd * 100, 2),
        "return_per_dd": round(ret_per_dd, 3),
        "pct_profitable": round(pct * 100, 0),
        "wfe": round(walk_forward_efficiency(results), 3),
        "wfe_norm": round(normalized_wfe(results, train_months, test_months), 3),
        "oos_trades": sum(r.oos_trades for r in results),
        "window_oos": oos,  # per-window OOS returns (for Sharpe / DSR)
        "trade_oos": [x for r in results for x in r.oos_returns],  # per-trade (for Monte-Carlo)
    }


def _save_csv(rows: list[dict[str, Any]], path: Path) -> None:
    """Persist the running results, dropping the in-memory list payloads."""
    clean = [{k: v for k, v in row.items() if k not in _LIST_KEYS} for row in rows]
    pd.DataFrame(clean).to_csv(path, index=False)


def _plot_heatmap(pivot: pd.DataFrame, path: Path, title: str) -> None:
    """Save a green/red heatmap of a variation-indexed pivot (mean OOS %)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    vals = pivot.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(1.0 * vals.shape[1] + 3, 0.5 * vals.shape[0] + 2))
    im = ax.imshow(vals, cmap="RdYlGn", aspect="auto")
    ax.set_xticks(range(vals.shape[1]))
    ax.set_xticklabels([str(c) for c in pivot.columns], rotation=45, ha="right")
    ax.set_yticks(range(vals.shape[0]))
    ax.set_yticklabels(list(pivot.index))
    for i in range(vals.shape[0]):
        for j in range(vals.shape[1]):
            if not np.isnan(vals[i, j]):
                ax.text(j, i, f"{vals[i, j]:.0f}", ha="center", va="center", fontsize=7)
    ax.set_title(title)
    fig.colorbar(im, ax=ax, shrink=0.7, label="OOS %")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _top_charts(
    top_variations: list[str], trades_by_var: dict[str, list[float]], out_dir: Path
) -> None:
    """Save an OOS Monte-Carlo fan chart for the top few variations only."""
    from qplus.backtest.foundation.execution import plot_monte_carlo
    from qplus.backtest.foundation.montecarlo import equity_curve, monte_carlo_paths

    for variation in top_variations:
        trades = trades_by_var.get(variation, [])
        if len(trades) < 20:
            continue
        dollar_pnls = [r * _START_EQUITY for r in trades]
        paths = monte_carlo_paths(dollar_pnls, n_sims=500, start_equity=_START_EQUITY)
        actual = equity_curve(dollar_pnls, _START_EQUITY)
        plot_monte_carlo(
            paths,
            actual,
            _START_EQUITY,
            out_dir / f"montecarlo_{variation}.png",
            f"pooled OOS trades -- {variation}",
        )


def _write_reports(rows: list[dict[str, Any]], out_dir: Path, n_trials: int) -> None:
    """Build the ranking (with DSR), the heatmap and top-variation Monte-Carlo charts."""
    import numpy as np

    from qplus.backtest.foundation.overfitting import deflated_sharpe_ratio, sharpe_ratio

    df = pd.DataFrame([{k: v for k, v in r.items() if k not in _LIST_KEYS} for r in rows])
    good = [r for r in rows if "mean_oos_pct" in r and "window_oos" in r]
    if "mean_oos_pct" not in df.columns or not good:
        print("no successful tasks -> no ranking report")
        return

    # Pool each variation's return series across all instruments.
    win_by_var: dict[str, list[float]] = defaultdict(list)
    trades_by_var: dict[str, list[float]] = defaultdict(list)
    for r in good:
        win_by_var[r["variation"]].extend(r["window_oos"])
        trades_by_var[r["variation"]].extend(r["trade_oos"])

    variation_sharpe = {v: sharpe_ratio(s) for v, s in win_by_var.items()}
    sharpe_variance = (
        float(np.var(list(variation_sharpe.values()), ddof=1)) if len(variation_sharpe) > 1 else 0.0
    )

    agg = (
        df.dropna(subset=["mean_oos_pct"])
        .groupby("variation")
        .agg(
            return_per_dd=("return_per_dd", "mean"),
            mean_oos_pct=("mean_oos_pct", "mean"),
            oos_maxdd_pct=("oos_maxdd_pct", "mean"),
            worst_market_pct=("mean_oos_pct", "min"),
            pct_profitable=("pct_profitable", "mean"),
            wfe_norm=("wfe_norm", "mean"),
            trades=("oos_trades", "sum"),
        )
    )
    agg["oos_sharpe"] = agg.index.map(variation_sharpe)
    agg["dsr"] = agg.index.map(
        lambda v: deflated_sharpe_ratio(win_by_var[v], n_trials, sharpe_variance)
    )
    # Risk lens: rank by risk-adjusted return-per-drawdown, NOT raw return.
    agg = agg.sort_values("return_per_dd", ascending=False)
    agg.round(4).to_csv(out_dir / "ranking.csv")

    print(
        "\n===== Variation ranking (risk-adjusted: return per drawdown, across instruments) ====="
    )
    print(agg.round(3).to_string())

    valid = df.dropna(subset=["mean_oos_pct"])
    order = list(agg.index)  # best variations first

    by_instrument = valid.pivot_table(
        index="variation", columns="instrument", values="mean_oos_pct"
    ).reindex(order)
    _plot_heatmap(
        by_instrument, out_dir / "heatmap.png", "Mean OOS return % -- variation x instrument"
    )

    # If several training lengths were run, show how each variation holds up across them.
    if "train_months" in valid.columns and valid["train_months"].nunique() > 1:
        by_train = valid.pivot_table(
            index="variation", columns="train_months", values="mean_oos_pct"
        ).reindex(order)
        by_train.round(2).to_csv(out_dir / "ranking_by_train.csv")
        print("\n===== Mean OOS % by training length (months) =====")
        print(by_train.round(2).to_string())
        _plot_heatmap(
            by_train,
            out_dir / "heatmap_by_train.png",
            "Mean OOS return % -- variation x train length",
        )

    _top_charts(order[:3], trades_by_var, out_dir)


def main(argv: list[str] | None = None) -> None:
    """CLI: run the study defined in a config module across processes."""
    args = sys.argv[1:] if argv is None else argv
    if not args:
        raise SystemExit(
            "usage: python -m qplus.backtest.edge.characterize <study_config.py> [max_windows]"
        )
    cfg = load_config_module(Path(args[0]))
    max_windows = int(args[1]) if len(args) > 1 else None
    workers = int(getattr(cfg, "MAX_WORKERS", 4))
    train_cfg = getattr(cfg, "TRAIN_MONTHS", 24)
    train_list = [int(train_cfg)] if isinstance(train_cfg, int) else [int(t) for t in train_cfg]
    test_m = int(getattr(cfg, "TEST_MONTHS", 6))
    step_m = int(getattr(cfg, "STEP_MONTHS", 6))
    holdout_m = int(getattr(cfg, "HOLDOUT_MONTHS", 0))  # reserved final slice, never selected on
    embargo_d = int(getattr(cfg, "EMBARGO_DAYS", 0))  # purge the train/test boundary (F5)

    out_dir = _REPO_ROOT / "reports" / "study" / f"run_{datetime.now():%Y%m%d_%H%M}"
    out_dir.mkdir(parents=True, exist_ok=True)

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
            train_m,
            test_m,
            step_m,
            max_windows,
            holdout_m,
            embargo_d,
        )
        for factory, csv, leverage in cfg.INSTRUMENTS
        for name, overrides in cfg.VARIATIONS.items()
        for train_m in train_list
    ]
    n_inst, n_var = len(cfg.INSTRUMENTS), len(cfg.VARIATIONS)
    trains = "/".join(str(t) for t in train_list)
    print(
        f"{len(tasks)} tasks ({n_inst} instruments x {n_var} variations x "
        f"{len(train_list)} train lengths) on {workers} workers"
    )
    print(f"walk-forward: train {trains}m / test {test_m}m / step {step_m}m")
    print(f"output -> {out_dir}\n")

    rows: list[dict[str, Any]] = []
    out_csv = out_dir / "study.csv"
    started = time.time()
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_run_task, *task): (task[6], task[4], task[7]) for task in tasks}
        for i, future in enumerate(as_completed(futures), start=1):
            symbol, variation, train_m = futures[future]
            try:
                row = future.result()
            except Exception as exc:  # record the failure and continue the batch
                row = {
                    "instrument": symbol,
                    "variation": variation,
                    "train_months": train_m,
                    "error": str(exc)[:120],
                }
            rows.append(row)
            _save_csv(rows, out_csv)  # save after every task -> partial results survive a Ctrl-C
            elapsed = time.time() - started
            eta_h = (elapsed / i) * (len(tasks) - i) / 3600
            oos = row.get("mean_oos_pct")
            print(
                f"[{i}/{len(tasks)}] {symbol}/{variation}@tr{train_m}: {oos}% "
                f"| elapsed {elapsed / 60:.1f}m | ETA ~{eta_h:.1f}h"
            )

    # DSR must deflate by the total configs the winner was selected among, not just the
    # variation count: variations x training lengths (F2). The per-window grid adds further
    # degrees of freedom, so this is still a floor on the true trial count.
    _write_reports(rows, out_dir, n_var * len(train_list))
    print(f"\nDone in {(time.time() - started) / 60:.1f} min. Full results: {out_dir}")


if __name__ == "__main__":
    main()
