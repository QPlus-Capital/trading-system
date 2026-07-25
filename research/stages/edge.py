"""Stage 1 — EDGE: does the strategy have an edge, where, and is it robust?

Runs (or ingests) the walk-forward study sweep and prints a per-variation decision table:
cross-instrument OOS return, its risk-adjusted twin, and how consistent it is. The two
structure gates (robust majority positive AND risk within tolerance of the best) mark which
variations are *eligible*. You read this and decide which variation to carry forward.

Usage::

    # run the full sweep (heavy), then show the ranking:
    uv run python -m research.stages.edge research/config/robustness.py
    # or ingest an already-computed study:
    uv run python -m research.stages.edge research/config/robustness.py --from <study_dir>
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import numpy.typing as npt
import pandas as pd

from research.engine.candidate_returns import CANDIDATE_ARTIFACTS, candidate_definitions
from research.engine.config import load_config_module
from research.engine.romano_wolf import (
    ROMANO_WOLF_ARTIFACT,
    RomanoWolfAnalysis,
    RomanoWolfInputError,
    romano_wolf_test,
)
from research.engine.spa import SpaAnalysis, SpaInputError, analyze_spa, load_candidate_family
from research.portfolio.resample import DEFAULT_REPLICATIONS
from research.stages import _runbook as rb
from research.stages import lineage, universe

# Defaults only -- a study config may override via SELECT_MIN_FRAC_POSITIVE / SELECT_RPD_TOLERANCE.
_MIN_FRAC_POSITIVE = 0.9  # structure gate: OOS-positive on a robust majority of instruments
_RPD_TOLERANCE = 0.85  # structure gate: risk-adjusted return within 85% of the best
# Statistical gate (Stage 2, methodology.md): the deflated Sharpe must clear this after correcting
# for the trial budget, and the study-level PBO must stay below its ceiling.
_DSR_MIN = 0.90
PBO_MAX = 0.20
SPA_REPLICATIONS = DEFAULT_REPLICATIONS


def candidate_sidecars(source_dir: Path) -> tuple[str, ...]:
    """Return a complete candidate-artifact set, or fail on a partial publication."""
    present = tuple(name for name in CANDIDATE_ARTIFACTS if (source_dir / name).is_file())
    if present and len(present) != len(CANDIDATE_ARTIFACTS):
        missing = [name for name in CANDIDATE_ARTIFACTS if name not in present]
        raise SystemExit(
            "study has a partial candidate-return publication; missing "
            f"{', '.join(missing)} -- re-run Stage 1"
        )
    return present


def _spa_family(
    source_dir: Path,
    variations: object,
    train_months: object,
) -> dict[str, npt.NDArray[np.float64]]:
    """Load the complete formal family that the study table declares."""
    sidecars = candidate_sidecars(source_dir)
    if not sidecars:
        raise SystemExit(
            "ABBRUCH: candidate_daily_returns.csv fehlt; P-05 kann nicht fail-closed pruefen. "
            "Stage 1 mit P-03-Artefakten neu ausfuehren."
        )
    if not isinstance(variations, dict) or not isinstance(train_months, (list, tuple)):
        raise SystemExit("ABBRUCH: Studienkonfiguration deklariert keine formale SPA-Familie.")
    expected = {
        definition.candidate_id for definition in candidate_definitions(variations, train_months)
    }
    try:
        family = load_candidate_family(
            source_dir,
            expected_candidates=expected,
            hash_paths=lineage.hash_paths,
        )
    except SpaInputError as exc:
        raise SystemExit(f"ABBRUCH: ungueltige SPA-Kandidatenmatrix: {exc}") from exc
    return dict(family.returns)


def _print_spa(analysis: SpaAnalysis) -> None:
    selected = analysis.selected
    verdict = "ok" if analysis.passes else "NICHT BESTANDEN"
    print(
        f"  SPA Familien-Gate: p={selected.p_value:.4f} bei L={selected.block_length}; "
        f"gesamt {verdict}"
    )
    sensitivity = ", ".join(
        f"L={block_length}: {result.p_value:.4f}"
        for block_length, result in sorted(analysis.sensitivity.items())
    )
    print(f"  SPA Abhaengigkeits-Sensitivitaet: {sensitivity}")


def _print_romano_wolf(analysis: RomanoWolfAnalysis) -> None:
    eligible = analysis.eligible_candidates
    print(
        f"  Romano-Wolf Stepdown: {len(eligible)}/{len(analysis.candidates)} Kandidaten "
        f"bei adj. p<=0.05 eligible (L={analysis.block_length})"
    )


def _study_csv_from(source: Path) -> Path:
    """Resolve ``--from`` to a study.csv (accepts the csv itself or a study run directory)."""
    if source.is_dir():
        return source / "study.csv"
    return source


def _run_study(config: Path) -> Path:
    """Run the heavy sweep via the characterize entrypoint and return its study.csv."""
    from research.engine import characterize

    characterize.main([str(config)])
    study_root = rb._REPO_ROOT / "reports" / "research"
    runs = sorted(study_root.glob("study_*"), key=lambda p: p.stat().st_mtime)
    if not runs:
        raise SystemExit("study produced no run directory")
    return runs[-1] / "study.csv"


def load_overfitting(source_dir: Path) -> tuple[dict[str, float], float | None]:
    """Read the study's ``ranking.csv`` (per-variation DSR) + ``overfitting.json`` (study PBO).

    Returns ``(dsr_by_variation, pbo)``. Both are empty/None if the study predates these artifacts
    (the DSR/PBO are computed by the study, which alone holds the per-window return series).
    """
    dsr: dict[str, float] = {}
    ranking_csv = source_dir / "ranking.csv"
    if ranking_csv.exists():
        r = pd.read_csv(ranking_csv)
        if "dsr" in r.columns:
            dsr = {str(v): float(d) for v, d in zip(r["variation"], r["dsr"], strict=True)}
    pbo: float | None = None
    of_json = source_dir / "overfitting.json"
    if of_json.exists():
        pbo = json.loads(of_json.read_text(encoding="utf-8")).get("pbo")
    return dsr, pbo


def ranking(
    df: pd.DataFrame,
    *,
    min_frac_positive: float = _MIN_FRAC_POSITIVE,
    rpd_tolerance: float = _RPD_TOLERANCE,
    dsr_by_variation: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Per-variation decision table: the best training length per variation, return-first, gated.

    ``eligible`` is the *structure* gate (robust majority positive AND risk within tolerance of the
    best). ``dsr_ok`` is the *statistical* gate (deflated Sharpe clears ``_DSR_MIN``); it is only
    applied when the DSR is available. The auto-pick requires both.
    """
    valid = df.dropna(subset=["mean_oos_pct", "return_per_dd"])
    g = universe.per_config(valid).reset_index()
    best_rpd = float(g["mean_rpd"].max()) if not g.empty else 0.0
    gate_pos = g["frac_positive"] >= min_frac_positive
    gate_rpd = g["mean_rpd"] >= rpd_tolerance * best_rpd
    # #17: a task that FAILED leaves a row with no mean_oos_pct, which dropna then removes -- so a
    # config that crashed on its hardest markets would be averaged over the survivors only, and
    # look better for having failed. Require the full instrument set per (variation, train_months);
    # an incomplete cell set is ineligible, not a smaller sample.
    expected_cells = int(df["instrument"].nunique())
    have = valid.groupby(["variation", "train_months"])["instrument"].nunique()
    g["cells"] = [
        int(have.get((r.variation, r.train_months), 0)) for r in g.itertuples(index=False)
    ]
    g["complete"] = g["cells"] >= expected_cells
    g["eligible"] = gate_pos & gate_rpd & g["complete"]
    dsr_map = dsr_by_variation or {}
    g["dsr"] = g["variation"].map(dsr_map)  # NaN where unavailable
    g["dsr_ok"] = g["dsr"].isna() | (g["dsr"] >= _DSR_MIN)  # unknown DSR does not gate out
    # EVERY (variation, train_months) row, gated individually. Reducing to each variation's
    # best-return length dropped eligible candidates: if the best length was incomplete or gated
    # out while a lower-return length passed, selection saw no eligible row at all and failed
    # closed on a deployable candidate (Codex round 6).
    return g.sort_values("mean_ret", ascending=False).reset_index(drop=True)


def _print_table(top: pd.DataFrame) -> str:
    """Print the ranking; return the auto-pick (highest-return, structure- AND DSR-eligible)."""
    print(
        f"\n  {'variation':14s} {'train':>5s} {'Rendite':>9s} {'Rend/DD':>8s} "
        f"{'%pos':>6s} {'DSR':>6s}  Gate"
    )
    auto = ""
    for _, r in top.iterrows():
        ok = bool(r["eligible"]) and bool(r["dsr_ok"])
        # Name the reason: an incomplete cell set is a different problem from a weak result (#17).
        if ok:
            gate = "ok eligible"
        else:
            gate = "unvollstaendig" if not r.get("complete", True) else "   gated out"
        if ok and not auto:
            auto, gate = str(r["variation"]), "<< AUTO-PICK"
        dsr_txt = "  n/a" if pd.isna(r["dsr"]) else f"{r['dsr']:5.2f}"
        print(
            f"  {r['variation']:14s} {int(r['train_months']):>4d}m {r['mean_ret']:>+8.1f}% "
            f"{r['mean_rpd']:>8.2f} {r['frac_positive']:>5.0%} {dsr_txt:>6s}  {gate}"
        )
    return auto


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Stage 1 (EDGE): robustness ranking.")
    parser.add_argument("config", type=Path, help="study config module (strategy + variations)")
    parser.add_argument(
        "--from",
        dest="source",
        type=Path,
        default=None,
        help="ingest an existing study.csv / run dir instead of running the sweep",
    )
    parser.add_argument(
        "--run", type=Path, default=None, help="write into this framework run dir (default: fresh)"
    )
    parser.add_argument(
        "--allow-legacy-unverified",
        action="store_true",
        help="read a run that predates artifact hashing. Such a run can be inspected but can "
        "NEVER produce a deployable PASS -- its inputs cannot be confirmed.",
    )
    args = parser.parse_args(argv)

    legacy = bool(args.allow_legacy_unverified)
    run = (
        rb.RunDir.open(args.run, allow_legacy=legacy)
        if args.run
        else rb.RunDir.create(allow_legacy=legacy)
    )
    rb.banner(1, "EDGE - Kante & Robustheit", run)
    # Gates live in the study config (per strategy), not in this code -- nothing strategy-specific.
    cfg = load_config_module(args.config)

    # Hash the inputs BEFORE the sweep, not after: a config or CSV edited during the hours the
    # study runs would otherwise be recorded as if it had produced these results. The catalog is
    # excluded here because running the sweep SEEDS it -- it is captured once seeding is done.
    inputs = lineage.external_inputs(args.config, cfg, catalog=False)
    producer_git: dict[str, str] | None = None  # set only when ingesting another run's study
    if args.source:
        study_csv = _study_csv_from(args.source)
        # An ingested study was computed at some earlier time, possibly from other content. Only
        # the study's OWN record says what that was; hashes taken here describe the files now.
        # Its recorded catalog entries are kept as-is -- replacing them with the catalog as it
        # stands today would certify bars that study never read.
        recorded = lineage.read_provenance(study_csv.parent)
        provenance = lineage.PROVENANCE_RECORDED if recorded else lineage.PROVENANCE_INGESTED
        # The study's results belong to the code that COMPUTED them, not to the checkout doing
        # the ingest. Recording the producer's state lets the cross-stage git check refuse a
        # study combined with downstream stages run under materially different engine code.
        if recorded:
            inputs, producer_git = recorded
        else:
            inputs, producer_git = {**inputs, **lineage.catalog_inputs()}, None
    else:
        study_csv = _run_study(args.config)
        provenance = lineage.PROVENANCE_COMPUTED
        # The sweep is what SEEDS the catalog, so there was nothing stable to hash up front. It
        # records the catalog the moment seeding finished -- before its own backtests ran -- so
        # a concurrent seeder during those hours cannot be mistaken for what this study read.
        at_seed = study_csv.parent / "_catalog_at_seed.json"
        inputs = {
            **inputs,
            **(
                json.loads(at_seed.read_text(encoding="utf-8"))
                if at_seed.is_file()
                else lineage.catalog_inputs()
            ),
        }
        lineage.write_provenance(study_csv.parent, inputs)  # so a later --from can be trusted
    df = pd.read_csv(study_csv)

    # The study alone holds the per-window return series, so it (not this stage) computes the DSR +
    # PBO; carry those artifacts into the run and surface them. Older studies may lack them.
    source_dir = study_csv.parent
    dsr_by_variation, pbo = load_overfitting(source_dir)
    try:
        family = _spa_family(
            source_dir,
            getattr(cfg, "VARIATIONS", None),
            getattr(cfg, "TRAIN_MONTHS", None),
        )
        spa_analysis = analyze_spa(
            family,
            replications=SPA_REPLICATIONS,
        )
        romano_wolf_analysis = romano_wolf_test(
            family,
            mean_block_length=spa_analysis.selected_block_length,
            replications=spa_analysis.replications,
            seed=spa_analysis.seed,
        )
    except (SpaInputError, RomanoWolfInputError, ValueError) as exc:
        raise SystemExit(
            f"ABBRUCH: Familien-Signifikanz konnte nicht berechnet werden: {exc}"
        ) from exc

    min_pos = float(getattr(cfg, "SELECT_MIN_FRAC_POSITIVE", _MIN_FRAC_POSITIVE))
    rpd_tol = float(getattr(cfg, "SELECT_RPD_TOLERANCE", _RPD_TOLERANCE))

    top = ranking(
        df, min_frac_positive=min_pos, rpd_tolerance=rpd_tol, dsr_by_variation=dsr_by_variation
    )
    # #31: everything this stage produces is published together, with the content hashes of the
    # config and raw data it was computed from. A later edit to any of them invalidates the run.
    with run.stage(
        "edge",
        argv={"config": str(args.config), "source": str(args.source or ""), "run": str(run.path)},
        inputs=inputs,
        semantics={"study_provenance": provenance},
        git=producer_git,  # the code that computed the study, when it was not this process
    ) as st:
        st.save_json("run_manifest.json", {"config": str(args.config)})
        shutil.copyfile(study_csv, st.file("study.csv"))
        for artifact in ("ranking.csv", "overfitting.json", *candidate_sidecars(source_dir)):
            if (source_dir / artifact).exists():
                shutil.copyfile(source_dir / artifact, st.file(artifact))
        top.to_csv(st.file("edge_ranking.csv"), index=False)
        st.save_json("spa.json", spa_analysis.to_dict())
        st.save_json(ROMANO_WOLF_ARTIFACT, romano_wolf_analysis.to_dict())
    auto = _print_table(top)
    print(f"\n  Struktur-Gate: %pos>={min_pos:.0%} und Rend/DD>={rpd_tol:.0%} vom Besten.")
    if dsr_by_variation:
        n = len(dsr_by_variation)
        print(f"  Statistik-Gate: DSR>={_DSR_MIN:.2f} (nach Deflation um {n} Varianten)")
    else:
        print("  Statistik-Gate: DSR n/a - Studie neu laufen lassen fuer DSR/PBO.")
    if pbo is not None:
        verdict = "ok" if pbo <= PBO_MAX else "ZU HOCH"
        print(f"  PBO (Overfitting-Wahrsch. der Auswahl): {pbo:.2f} <= {PBO_MAX:.2f}? {verdict}")
    else:
        print("  PBO: n/a - Studie neu laufen lassen.")
    _print_spa(spa_analysis)
    _print_romano_wolf(romano_wolf_analysis)
    print(f"  Auto-Auswahl (hoechste Rendite unter eligible): {auto or '- (keine eligible)'}")

    select_auto = rb.cmd("select", "--run", str(run.path))
    rb.next_step(select_auto, "Universum waehlen (Auto) - oder --variation <name> anhaengen")


if __name__ == "__main__":
    main()
