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
* ``dsr`` -- diagnostic deflated Sharpe at synchronized effective and nominal trial counts,
* ``pbo`` -- diagnostic CSCV probability over the common 36-candidate window matrix.

Everything lands in a single timestamped folder ``reports/research/study_<ts>/`` (which is
git-ignored): the existing study/ranking reports, a variation x instrument heatmap, and the
canonical pre-filter candidate daily/window streams copied into the later ``run_*`` directory.

A study config module must define ``INSTRUMENTS`` (list of ``(factory, csv, leverage)``),
``VARIATIONS`` (``dict[name, config_overrides]``) and ``PARAM_GRID``; it may also set
``MAX_WORKERS`` and the walk-forward sizing ``TRAIN_MONTHS`` / ``TEST_MONTHS`` /
``STEP_MONTHS``.

Usage (append a number to limit windows for a quick test)::

    uv run python -m research.engine.characterize research/config/robustness.py
    uv run python -m research.engine.characterize research/config/robustness.py 1
"""

import json
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
from core.broker import BrokerProfile, standard_broker
from core.data.mt5_csv import seeded_instruments
from core.paths import REPO_ROOT

from research.engine.candidate_returns import (
    CANDIDATE_METADATA,
    CANDIDATE_WINDOW_RETURNS,
    write_candidate_artifacts,
)
from research.engine.config import load_config_module
from research.engine.overfitting import study_trial_budget
from research.engine.recipe import SweepRecipe
from research.engine.walkforward import normalized_wfe, walk_forward_efficiency
from research.engine.walkforward_runner import run_walkforward
from research.portfolio.risk import AccountProfile

_REPO_ROOT = REPO_ROOT

# Per-task payloads kept in memory for reporting but dropped from the scalar study table.
_LIST_KEYS = (
    "window_oos",
    "combo_oos",
    "candidate_windows",
)


def effective_trial_count(rho_bar: Decimal) -> Decimal:
    """Return the pre-registered effective trial count for 36 formal and five manual trials."""
    if not isinstance(rho_bar, Decimal):
        raise TypeError("rho_bar must be Decimal")
    if not rho_bar.is_finite() or not Decimal(0) <= rho_bar <= Decimal(1):
        raise ValueError("rho_bar must be finite and between zero and one")
    return min(
        Decimal(41),
        Decimal(5) + rho_bar + (Decimal(1) - rho_bar) * Decimal(36),
    )


def account_balance_of(cfg: Any) -> float:
    """The account balance the whole pipeline runs on, read from the config's ``ACCOUNT``.

    The portfolio holdout and live already size on ``cfg.ACCOUNT.start_balance``; Stage 1 must use
    the same number, because scoring sizes off a constant basis and that sizing is scale-dependent.
    A config without an ``ACCOUNT`` falls back to :class:`AccountProfile`'s own default -- the
    point of the helper is that the balance comes from the account profile, never from the
    recipe's unrelated 200k default, which is what silently split selection from deployment.
    """
    return float(getattr(cfg, "ACCOUNT", AccountProfile()).start_balance)


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
    start_balance: float,
    broker: BrokerProfile | None = None,
) -> dict[str, Any]:
    """Walk-forward one (instrument, variation) and return its OOS metrics + return series."""
    # Net-of-cost selection: spread, commission, and slippage are in-engine; every closed trade
    # receives the standard broker snapshot's realized swap before any score is calculated.
    #
    # ``start_balance`` is the account the whole pipeline runs on, not the recipe's 200k default.
    # Scoring sizes off this constant (:func:`research.engine.continuous.scoring_params`) and it is
    # scale-dependent, so selecting on a different balance than the portfolio holdout and live run
    # would rank parameters for an account we never trade. Threaded from ``cfg.ACCOUNT``.
    recipe = SweepRecipe(
        factory(),
        csv,
        leverage=leverage,
        param_grid=param_grid,
        config_overrides=overrides,
        broker=broker if broker is not None else standard_broker(),
        start_balance=start_balance,
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
        # Keyed BY WINDOW LABEL, not by position: instruments have different CSV spans, so
        # window 0 of a long gold history is a different calendar period than window 0 of a
        # later-starting index. Averaging by list offset would mix unrelated periods and make the
        # CSCV time slices synthetic rather than chronological.
        "combo_oos": {
            key: {r.window: r.oos_by_combo[key] for r in results}
            for key in (results[0].oos_by_combo if results else {})
        },
        # Additive P-03 evidence: these are the chosen outer walk-forward path's exact P-01 net-R
        # events. Inner grid combinations remain solely in combo_oos and never become formal
        # persisted candidates.
        "candidate_windows": [
            {
                "window": result.window,
                "test_start_ns": result.test_start_ns,
                "test_end_ns": result.test_end_ns,
                "net_r_events": result.oos_net_r_events,
            }
            for result in results
        ],
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
    per_train: dict[int, dict[tuple[str, str], dict[str, dict[str, float]]]] = defaultdict(
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
        # Only the windows every instrument actually has, in chronological label order.
        labels = set.intersection(*(set(cands[c][i].keys()) for c in cands for i in insts))
        if len(labels) < 2:
            continue
        ordered = sorted(labels)
        out[tm] = {
            c: [sum(cands[c][i][w] for i in insts) / len(insts) for w in ordered] for c in cands
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


def synchronized_overfitting_diagnostics(out_dir: Path) -> dict[str, Any]:
    """Compute diagnostic-only DSR and PBO from P-03's synchronized window matrix."""
    import numpy as np

    from research.engine.overfitting import (
        cscv_splits,
        deflated_sharpe_ratio,
        expected_max_sharpe,
        pbo,
        sharpe_ratio,
    )

    base: dict[str, Any] = {
        "role": "diagnostic_only",
        "status": "unavailable",
        "dsr_threshold": 0.90,
        "pbo_threshold": 0.20,
        "source": CANDIDATE_WINDOW_RETURNS,
    }
    try:
        metadata_raw = json.loads((out_dir / CANDIDATE_METADATA).read_text(encoding="utf-8"))
        if not isinstance(metadata_raw, dict):
            raise ValueError("candidate metadata must be an object")
        formal = metadata_raw.get("formal_candidates")
        persisted = metadata_raw.get("persisted_candidates")
        trials = metadata_raw.get("trial_counts")
        if (
            not isinstance(formal, list)
            or not isinstance(persisted, list)
            or not isinstance(trials, dict)
        ):
            raise ValueError("candidate metadata is incomplete")
        formal_names = [str(item["candidate"]) for item in formal if isinstance(item, dict)]
        persisted_names = [str(name) for name in persisted]
        if len(formal_names) != 36 or int(trials.get("manual", -1)) != 5:
            raise ValueError("DSR/PBO diagnostics require 36 formal and five manual trials")
        if persisted_names != formal_names:
            raise ValueError("all 36 formal candidates must share the synchronized window grid")

        frame = pd.read_csv(out_dir / CANDIDATE_WINDOW_RETURNS)
        if list(frame.columns) != ["window", *formal_names]:
            raise ValueError("candidate window columns disagree with the formal family")
        if frame["window"].duplicated().any():
            raise ValueError("candidate window labels must be unique")
        matrix = frame[formal_names].to_numpy(dtype=float)
        if matrix.ndim != 2 or matrix.shape[0] < 4 or not np.isfinite(matrix).all():
            raise ValueError("candidate window matrix is too short or non-finite")

        correlations = np.corrcoef(matrix, rowvar=False)
        upper = correlations[np.triu_indices(len(formal_names), k=1)]
        if not np.isfinite(upper).all():
            raise ValueError("candidate correlations are undefined")
        rho_bar = float(np.clip(upper.mean(), 0.0, 1.0))
        n_eff_decimal = effective_trial_count(Decimal(str(rho_bar)))
        n_eff = float(n_eff_decimal)
        sharpes = np.asarray(
            [sharpe_ratio(matrix[:, index]) for index in range(matrix.shape[1])],
            dtype=float,
        )
        sharpe_variance = float(np.var(sharpes, ddof=1))
        if not np.isfinite(sharpe_variance) or sharpe_variance <= 0.0:
            raise ValueError("candidate Sharpe variance must be positive and finite")

        benchmark_effective = expected_max_sharpe(n_eff, sharpe_variance)
        benchmark_nominal = expected_max_sharpe(41.0, sharpe_variance)
        candidates: dict[str, dict[str, float | int | bool]] = {}
        for index, name in enumerate(formal_names):
            values = matrix[:, index]
            std = float(values.std(ddof=1))
            if std <= 0.0:
                raise ValueError(f"candidate {name} has zero window-return variance")
            standardized = (values - values.mean()) / std
            dsr_effective = deflated_sharpe_ratio(values, n_eff, sharpe_variance)
            dsr_nominal = deflated_sharpe_ratio(values, 41.0, sharpe_variance)
            candidates[name] = {
                "sharpe": float(sharpes[index]),
                "dsr_effective": dsr_effective,
                "dsr_nominal": dsr_nominal,
                "dsr_diagnostic_ok": Decimal(str(dsr_effective)) >= Decimal("0.90"),
                "sample_count": len(values),
                "skew": float((standardized**3).mean()),
                "kurtosis": float((standardized**4).mean()),
            }

        splits = cscv_splits(len(matrix))
        if splits < 2:
            raise ValueError("candidate window matrix has too few windows for PBO")
        pbo_value = pbo(matrix, n_splits=splits)
        return {
            **base,
            "status": "available",
            "candidate_count": len(formal_names),
            "manual_trial_count": 5,
            "nominal_trial_count": 41,
            "effective_trial_count": n_eff,
            "rho_bar": rho_bar,
            "sharpe_variance": sharpe_variance,
            "benchmark_effective": benchmark_effective,
            "benchmark_nominal": benchmark_nominal,
            "sample_count": len(matrix),
            "pbo": pbo_value,
            "pbo_split_count": splits,
            "pbo_diagnostic_ok": Decimal(str(pbo_value)) <= Decimal("0.20"),
            "candidates": candidates,
            "dsr_by_candidate": {
                name: values["dsr_effective"] for name, values in candidates.items()
            },
            "dsr_nominal_by_candidate": {
                name: values["dsr_nominal"] for name, values in candidates.items()
            },
        }
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        return {**base, "reason": str(exc), "pbo": None, "candidates": {}}


def _write_reports(rows: list[dict[str, Any]], out_dir: Path, n_trials: int) -> None:
    """Build the ranking (with DSR + PBO), the heatmap and top-variation Monte-Carlo charts."""
    import json

    from research.engine.overfitting import sharpe_ratio

    df = pd.DataFrame([{k: v for k, v in r.items() if k not in _LIST_KEYS} for r in rows])
    good = [r for r in rows if "mean_oos_pct" in r and "window_oos" in r]
    if "mean_oos_pct" not in df.columns or not good:
        print("no successful tasks -> no ranking report")
        return

    # Keep the pooled variation series only for the descriptive OOS Sharpe. Decision diagnostics
    # come exclusively from P-03's synchronized candidate-window matrix below.
    win_by_var: dict[str, list[float]] = defaultdict(list)
    for r in good:
        win_by_var[r["variation"]].extend(r["window_oos"])

    variation_sharpe = {v: sharpe_ratio(s) for v, s in win_by_var.items()}
    diagnostics = synchronized_overfitting_diagnostics(out_dir)
    diagnostics["searched_configurations"] = n_trials
    (out_dir / "overfitting.json").write_text(
        json.dumps(diagnostics, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    if diagnostics["status"] == "available":
        print(
            "\nDSR/PBO diagnostics only: "
            f"N_eff={diagnostics['effective_trial_count']:.2f}, "
            f"rho={diagnostics['rho_bar']:.3f}, "
            f"PBO={diagnostics['pbo']:.3f}, "
            f"splits={diagnostics['pbo_split_count']}"
        )
    else:
        print(f"\nDSR/PBO diagnostics unavailable: {diagnostics['reason']}")

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
    best_tm = (
        df.dropna(subset=["mean_oos_pct"])
        .groupby(["variation", "train_months"])["mean_oos_pct"]
        .mean()
        .groupby("variation")
        .idxmax()
    )
    agg["train_months"] = agg.index.map(lambda v: int(best_tm[v][1]) if v in best_tm else 0)
    dsr_by_candidate = diagnostics.get("dsr_by_candidate", {})
    dsr_nominal_by_candidate = diagnostics.get("dsr_nominal_by_candidate", {})
    agg["dsr"] = agg.index.map(
        lambda variation: (
            dsr_by_candidate.get(f"{variation}__train_{int(best_tm[variation][1])}m", float("nan"))
            if variation in best_tm
            else float("nan")
        )
    )
    agg["dsr_nominal"] = agg.index.map(
        lambda variation: (
            dsr_nominal_by_candidate.get(
                f"{variation}__train_{int(best_tm[variation][1])}m",
                float("nan"),
            )
            if variation in best_tm
            else float("nan")
        )
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
    # Freeze and hash the cost input before any worker starts. Every task receives this same
    # in-memory profile, so a snapshot refresh during the long study cannot split candidates
    # across different rates.
    from research.stages import lineage

    study_inputs = lineage.external_inputs(Path(args[0]), cfg, catalog=False)
    broker = standard_broker()
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
    # The presence check discards a stale-frame catalog outright, so the per-instrument seeding
    # below re-imports everything through the write funnel (which stamps the new frame).
    # ...and an instrument whose CSV changed since it was seeded is discarded from the set too,
    # so the loop below re-imports it instead of backtesting the previous file's bars.
    sources: dict[str, str | Path] = {
        str(factory().id): _REPO_ROOT / str(csv) for factory, csv, _lev in cfg.INSTRUMENTS
    }
    have = seeded_instruments(catalog, sources)
    for factory, csv, leverage in cfg.INSTRUMENTS:
        recipe = SweepRecipe(factory(), csv, leverage=leverage)
        if str(recipe.INSTRUMENT.id) not in have:
            print(f"seeding {recipe.INSTRUMENT.id} ...")
            recipe.seed_catalog()
            have.add(str(recipe.INSTRUMENT.id))

    # The catalog is complete and the backtests are about to read it. Record its state HERE, not
    # after the sweep: another seeder touching the shared catalog during these hours would make a
    # post-sweep snapshot describe bars this study's tasks never saw.
    catalog_at_seed = lineage.catalog_inputs(sorted(sources))
    (out_dir / "_catalog_at_seed.json").write_text(
        json.dumps(catalog_at_seed, indent=2), encoding="utf-8"
    )
    study_inputs = {**study_inputs, **catalog_at_seed}

    account_balance = account_balance_of(cfg)
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
            account_balance,
            broker,
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
    write_candidate_artifacts(
        rows,
        out_dir,
        variations=cfg.VARIATIONS,
        train_months=train_list,
        markets=tuple(str(factory().raw_symbol) for factory, _csv, _lev in cfg.INSTRUMENTS),
        manual_trials=getattr(cfg, "MANUAL_TRIALS", ()),
        source_inputs=study_inputs,
        hash_paths=lineage.hash_paths,
    )
    _write_reports(rows, out_dir, budget.total)
    # Publish provenance only after every study artifact is final. A partial/interrupted study
    # deliberately has no record that could be mistaken for completed, attributable evidence.
    lineage.write_provenance(out_dir, study_inputs)
    print(f"Done in {(time.time() - started) / 60:.1f} min. Full results: {out_dir}")


if __name__ == "__main__":
    main()
