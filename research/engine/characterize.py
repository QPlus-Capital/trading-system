"""Robustness study: walk-forward every (instrument x variation) in parallel.

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

Everything lands in a single timestamped folder ``reports/research/study_<ts>/`` (which is
git-ignored): ``study.csv`` (full table), ``ranking.csv``, and a variation x instrument
heatmap of the OOS returns.

A study config module must define ``INSTRUMENTS`` (list of ``(factory, csv, leverage)``),
``VARIATIONS`` (``dict[name, config_overrides]``) and ``PARAM_GRID``; it may also set
``MAX_WORKERS`` and the walk-forward sizing ``TRAIN_MONTHS`` / ``TEST_MONTHS`` /
``STEP_MONTHS``.

Usage (append a number to limit windows for a quick test)::

    uv run python -m research.engine.characterize research/config/robustness.py
    uv run python -m research.engine.characterize research/config/robustness.py 1
"""


import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from core.broker import TTP_MARKETS
from core.data.mt5_csv import catalog_frame_is_stale
from core.paths import REPO_ROOT
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from research.engine.config import load_config_module
from research.engine.overfitting import study_trial_budget
from research.engine.recipe import SweepRecipe
from research.engine.walkforward import normalized_wfe, walk_forward_efficiency
from research.engine.walkforward_runner import run_walkforward

_REPO_ROOT = REPO_ROOT

# Per-task list payload kept in memory for reporting but dropped from the CSV.
_LIST_KEYS = ("window_oos", "combo_oos")  # in-memory payloads, never written to the CSV


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
    # Net-of-cost selection: the TTP profile applies slippage in-engine (spread + commission are
    # already in via the bid/ask bars + fees), so the variation ranking + DSR reflect what live
    # nets. Swap (~uniform across variations) is validated net separately in the equity report.
    recipe = SweepRecipe(
        factory(),
        csv,
        leverage=leverage,
        param_grid=param_grid,
        config_overrides=overrides,
        broker=TTP_MARKETS,
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
        collect_matrix=True,  # #13: one aligned OOS stream per grid candidate, for PBO/DSR
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
        # #13: {combo_key: [per-window OOS return]} -- every grid candidate scored on the SAME
        # windows, so candidates are chronologically aligned and PBO/CSCV can run over the real
        # search space instead of over variations.
        "combo_oos": {
            key: [r.oos_by_combo[key] for r in results]
            for key in (results[0].oos_by_combo if results else {})
        },
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


def candidate_streams(good: list[dict[str, Any]]) -> dict[int, dict[tuple[str, str], list[float]]]:
    """Per training length, each candidate's per-window OOS return averaged across instruments.

    A candidate is a (variation, grid-combo) pair -- the thing that could actually be deployed.
    Training lengths are kept apart because they have different window boundaries; within one,
    every candidate is scored on the SAME windows, so the streams are chronologically aligned.

    Instruments are AVERAGED into each window rather than concatenated: concatenating them would
    put instrument blocks on the time axis, which is exactly the flaw that made the old
    variation-level PBO unsound (#13).
    """
    per_train: dict[int, dict[tuple[str, str], dict[str, list[float]]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for r in good:
        for key, series in r.get("combo_oos", {}).items():
            per_train[int(r["train_months"])][(r["variation"], key)][r["instrument"]] = series

    out: dict[int, dict[tuple[str, str], list[float]]] = {}
    for tm, cands in per_train.items():
        if not cands:
            continue
        common = set.intersection(*(set(inst.keys()) for inst in cands.values()))
        if not common:
            continue
        insts = sorted(common)
        n_win = min(len(cands[c][i]) for c in cands for i in insts)
        if n_win < 2:
            continue
        out[tm] = {
            c: [sum(cands[c][i][w] for i in insts) / len(insts) for w in range(n_win)]
            for c in cands
        }
    return out


def candidate_pbo(streams: dict[int, dict[tuple[str, str], list[float]]]) -> float:
    """PBO across the REAL candidate matrix (rows = windows, cols = variation x grid combo).

    Computed per training length and reported as the WORST (highest) value: if any training
    length's search is overfit, the study is. Returns NaN when no training length has enough
    windows for a meaningful CSCV.
    """
    from research.engine.overfitting import cscv_splits, pbo

    values: list[float] = []
    for cands in streams.values():
        if len(cands) < 2:
            continue
        cols = list(cands.values())
        n_time = len(cols[0])
        splits = cscv_splits(n_time)
        if not splits:
            continue
        matrix = [[col[w] for col in cols] for w in range(n_time)]  # rows = windows (real time)
        try:
            values.append(pbo(matrix, n_splits=splits))
        except ValueError:
            continue
    return max(values) if values else float("nan")


def variation_pbo(good: list[dict[str, Any]], n_splits: int = 10) -> float:
    """Probability of backtest overfitting across the variations, via CSCV.

    Treats each variation as a trial and its per-window OOS returns as the performance series. The
    matrix must be *aligned* across variations, so it is built only over the (instrument, training-
    length) cells present for EVERY variation -- a variation that failed on one market (e.g. USDCAD)
    then does not break the alignment. Returns the fraction of IS/OOS splits where the in-sample-
    best variation lands below the OOS median (0 = never overfit, ~0.5 = no better than chance).
    """
    from research.engine.overfitting import pbo

    cells_by_var: dict[str, dict[tuple[Any, Any], list[float]]] = defaultdict(dict)
    for r in good:
        cells_by_var[r["variation"]][(r["instrument"], r["train_months"])] = r["window_oos"]
    variations = list(cells_by_var)
    if len(variations) < 2:
        return float("nan")
    common = set.intersection(*(set(c.keys()) for c in cells_by_var.values()))
    if not common:
        return float("nan")
    order = sorted(common)
    matrix = [[x for cell in order for x in cells_by_var[v][cell]] for v in variations]
    cols = list(zip(*matrix, strict=True))  # rows = pooled windows, cols = variations
    n_time = len(cols)
    splits = min(n_splits, n_time - (n_time % 2))
    if n_time < 2 or splits < 2:
        return float("nan")
    try:
        return pbo(cols, n_splits=splits)
    except ValueError:
        return float("nan")


def _write_reports(rows: list[dict[str, Any]], out_dir: Path, n_trials: int) -> None:
    """Build the ranking (with DSR + PBO), the heatmap and top-variation Monte-Carlo charts."""
    import json

    import numpy as np

    from research.engine.overfitting import deflated_sharpe_ratio, sharpe_ratio

    df = pd.DataFrame([{k: v for k, v in r.items() if k not in _LIST_KEYS} for r in rows])
    good = [r for r in rows if "mean_oos_pct" in r and "window_oos" in r]
    if "mean_oos_pct" not in df.columns or not good:
        print("no successful tasks -> no ranking report")
        return

    # Pool each variation's per-window return series across all instruments.
    win_by_var: dict[str, list[float]] = defaultdict(list)
    # ...and, separately, per CANDIDATE -- a (variation, train_months) pair, which is the unit
    # selection actually chooses among (#13).
    win_by_cand: dict[tuple[str, int], list[float]] = defaultdict(list)
    for r in good:
        win_by_var[r["variation"]].extend(r["window_oos"])
        win_by_cand[(r["variation"], int(r["train_months"]))].extend(r["window_oos"])

    variation_sharpe = {v: sharpe_ratio(s) for v, s in win_by_var.items()}
    # #13: the deflation benchmark needs the Sharpe dispersion ACROSS THE TRIALS being selected
    # among. Measuring it across pooled per-variation streams averaged the train-length dimension
    # away, so the variance came from a handful of numbers while n_trials counted the whole grid.
    # Too little dispersion -> too low an expected-max-Sharpe -> DSR too high: the optimistic
    # direction. Candidate-level Sharpes are the honest population.
    # Best available population: the real (variation x grid-combo) candidates when the matrix was
    # collected, otherwise the coarser (variation, train_months) fallback.
    streams = candidate_streams(good)
    grid_sharpes = [sharpe_ratio(s) for cands in streams.values() for s in cands.values()]
    if len(grid_sharpes) > 1:
        sharpe_variance = float(np.var(grid_sharpes, ddof=1))
        n_candidates = len(grid_sharpes)
    else:
        candidate_sharpe = {c: sharpe_ratio(s) for c, s in win_by_cand.items()}
        sharpe_variance = (
            float(np.var(list(candidate_sharpe.values()), ddof=1))
            if len(candidate_sharpe) > 1
            else 0.0
        )
        n_candidates = len(candidate_sharpe)
    # Study-level overfitting gate. Prefer CSCV over the real candidate matrix; fall back to the
    # variation-level estimate only when the matrix is unavailable (#13).
    pbo_value = candidate_pbo(streams)
    pbo_source = "candidates"
    if np.isnan(pbo_value):
        pbo_value = variation_pbo(good)
        pbo_source = "variations"
    (out_dir / "overfitting.json").write_text(
        json.dumps(
            {
                "pbo": None if np.isnan(pbo_value) else round(pbo_value, 4),
                "pbo_source": pbo_source,  # "candidates" = the real matrix, "variations" = fallback
                "n_trials": n_trials,
                "n_variations": len(win_by_var),
                "n_candidates": n_candidates,
                "sharpe_variance": round(sharpe_variance, 6),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"\nPBO (CSCV over {n_candidates} {pbo_source}): {pbo_value:.3f} | trials: {n_trials}"
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
    # #13: deflate the SELECTED candidate's own sample, not a stream pooled over train lengths the
    # deployment will never use. Each variation is represented by the training length that would
    # actually be picked (its best mean OOS return) -- that is the strategy being judged.
    best_tm = (
        df.dropna(subset=["mean_oos_pct"])
        .groupby(["variation", "train_months"])["mean_oos_pct"]
        .mean()
        .groupby("variation")
        .idxmax()
    )
    agg["train_months"] = agg.index.map(lambda v: int(best_tm[v][1]) if v in best_tm else 0)
    agg["dsr"] = agg.index.map(
        lambda v: deflated_sharpe_ratio(
            win_by_cand.get((v, int(best_tm[v][1])), win_by_var[v]), n_trials, sharpe_variance
        )
        if v in best_tm
        else float("nan")
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


def main(argv: list[str] | None = None) -> None:
    """CLI: run the study defined in a config module across processes."""
    args = sys.argv[1:] if argv is None else argv
    if not args:
        raise SystemExit(
            "usage: python -m research.engine.characterize <study_config.py> [max_windows]"
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

    out_dir = _REPO_ROOT / "reports" / "research" / f"study_{datetime.now():%Y%m%d_%H%M}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Seed every instrument's data once (serially); workers then only read the catalog.
    catalog = _REPO_ROOT / "catalog"
    have = (
        {str(i.id) for i in ParquetDataCatalog(str(catalog)).instruments()}
        if catalog.exists()
        else set()
    )
    # A catalog written under a different timestamp frame must be re-imported, not reused: seeding
    # is skipped per instrument, so stale bars would otherwise be mixed with window/day logic
    # parsed in the current frame and shift everything by the server offset (#18).
    if catalog_frame_is_stale(catalog):
        print("catalog was written in a different timestamp frame -> re-seeding all instruments")
        have = set()
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

    # DSR must deflate by the total configs the winner was selected among (F2): the honest breadth
    # is variations x training-lengths x per-window param-combos, not just one dimension.
    budget = study_trial_budget(cfg)
    print(f"\nmultiple-testing budget: {budget.summary()}")
    _write_reports(rows, out_dir, budget.total)
    print(f"Done in {(time.time() - started) / 60:.1f} min. Full results: {out_dir}")


if __name__ == "__main__":
    main()
