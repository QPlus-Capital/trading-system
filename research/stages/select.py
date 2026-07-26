"""Stage 2 — SELECT: which structure (variation + training length) and which markets?

Automatic selection intersects SPA, Romano-Wolf, MCS, completeness, cross-market consistency, and
return/drawdown evidence, then chooses the lowest pre-registered complexity before using return
and deterministic tie-breaks. ``--variation`` preserves the explicit exploratory bypass.

Usage::

    uv run python -m research.stages.select --run reports/research/run_X [--variation X]
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

from research.engine.config import load_config_module
from research.engine.mcs import McsInputError, McsResult
from research.engine.romano_wolf import RomanoWolfAnalysis, RomanoWolfInputError
from research.engine.spa import SpaAnalysis, SpaInputError
from research.stages import _runbook as rb
from research.stages import lineage, universe

_MIN_FRAC_POSITIVE = Decimal("0.90")
_RPD_TOLERANCE = Decimal("0.85")
_TRAIN_PREFERENCE = {36: 0, 24: 1, 18: 2}


class NoAutomaticSelection(RuntimeError):
    """The complete evidence intersection contains no deployable automatic choice."""


@dataclass(frozen=True)
class SelectionEvidence:
    """Decision-relevant family evidence after strict artifact deserialization."""

    family: frozenset[str]
    spa_passes: bool
    romano_wolf_eligible: frozenset[str]
    mcs_members: frozenset[str]


@dataclass(frozen=True)
class AutomaticCandidate:
    """One deterministic complexity-first automatic selection."""

    variation: str
    train_months: int
    candidate_id: str
    complexity: int


def _candidate_id(variation: str, train_months: int) -> str:
    return f"{variation}__train_{train_months}m"


def _decimal(value: object, *, label: str) -> Decimal:
    if isinstance(value, bool):
        raise NoAutomaticSelection(f"{label} must be a finite decimal")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise NoAutomaticSelection(f"{label} must be a finite decimal") from exc
    if not result.is_finite():
        raise NoAutomaticSelection(f"{label} must be finite")
    return result


def _diagnostic_at_most(value: object, threshold: Decimal) -> bool:
    try:
        return _decimal(value, label="diagnostic") <= threshold
    except NoAutomaticSelection:
        return False


def _diagnostic_float(value: object) -> float | None:
    try:
        return float(_decimal(value, label="diagnostic"))
    except NoAutomaticSelection:
        return None


def _validated_complexity_scores(
    raw: Mapping[str, object],
    variations: set[str],
) -> dict[str, int]:
    if set(raw) != variations:
        missing = sorted(variations - set(raw))
        extra = sorted(set(raw) - variations)
        raise NoAutomaticSelection(
            "complexity configuration must match the candidate variations exactly "
            f"(missing={missing}, extra={extra})"
        )
    scores: dict[str, int] = {}
    for variation, value in raw.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise NoAutomaticSelection(
                f"complexity score for {variation!r} must be a non-negative integer"
            )
        scores[variation] = value
    return scores


def _filter_or_fail(
    rows: pd.DataFrame,
    mask: pd.Series,
    criterion: str,
) -> pd.DataFrame:
    selected = rows[mask].copy()
    if selected.empty:
        raise NoAutomaticSelection(f"automatic eligibility is empty after criterion: {criterion}")
    return selected


def choose_automatic_candidate(
    ranking: pd.DataFrame,
    *,
    evidence: SelectionEvidence,
    complexity_scores: Mapping[str, object],
    min_frac_positive: Decimal = _MIN_FRAC_POSITIVE,
    rpd_tolerance: Decimal = _RPD_TOLERANCE,
) -> AutomaticCandidate:
    """Apply the pre-registered fail-closed family-evidence selection rule."""
    if not evidence.spa_passes:
        raise NoAutomaticSelection("SPA family gate failed at p > 0.05")
    required = {
        "variation",
        "train_months",
        "mean_ret",
        "mean_rpd",
        "frac_positive",
        "complete",
    }
    missing_columns = sorted(required - set(ranking.columns))
    if missing_columns:
        raise NoAutomaticSelection(f"ranking is missing columns: {missing_columns}")
    if ranking.empty:
        raise NoAutomaticSelection("ranking contains no candidates")

    rows = ranking.copy()
    try:
        rows["candidate_id"] = [
            _candidate_id(str(row.variation), int(row.train_months))
            for row in rows.itertuples(index=False)
        ]
    except (TypeError, ValueError) as exc:
        raise NoAutomaticSelection("ranking candidate identities are malformed") from exc
    if rows["candidate_id"].duplicated().any():
        raise NoAutomaticSelection("ranking candidate identities must be unique")
    ranking_family = frozenset(str(value) for value in rows["candidate_id"])
    if ranking_family != evidence.family:
        raise NoAutomaticSelection("ranking and statistical evidence candidate families disagree")
    if not evidence.romano_wolf_eligible <= evidence.family:
        raise NoAutomaticSelection("Romano-Wolf evidence contains an unknown candidate")
    if not evidence.mcs_members <= evidence.family:
        raise NoAutomaticSelection("MCS evidence contains an unknown candidate")

    variations = {str(value) for value in rows["variation"]}
    scores = _validated_complexity_scores(complexity_scores, variations)
    rows["complexity"] = rows["variation"].map(scores)

    rows = _filter_or_fail(
        rows,
        rows["candidate_id"].isin(evidence.romano_wolf_eligible),
        "Romano-Wolf adjusted p <= 0.05",
    )
    rows = _filter_or_fail(
        rows,
        rows["candidate_id"].isin(evidence.mcs_members),
        "90% MCS membership",
    )
    complete = rows["complete"]
    if not all(isinstance(value, bool) for value in complete):
        raise NoAutomaticSelection("ranking completeness flags must be boolean")
    rows = _filter_or_fail(rows, complete, "completeness")
    positive_mask = rows["frac_positive"].map(
        lambda value: _decimal(value, label="positive-market fraction") >= min_frac_positive
    )
    rows = _filter_or_fail(rows, positive_mask, "positive-market fraction >= 90%")

    all_rpd = [
        _decimal(value, label="mean return/drawdown") for value in ranking["mean_rpd"].tolist()
    ]
    best_rpd = max(all_rpd)
    rpd_floor = rpd_tolerance * best_rpd
    rpd_mask = rows["mean_rpd"].map(
        lambda value: _decimal(value, label="mean return/drawdown") >= rpd_floor
    )
    rows = _filter_or_fail(rows, rpd_mask, "mean return/drawdown >= 85% of best")

    choices: list[tuple[int, Decimal, int, str, int, str]] = []
    for row in rows.itertuples(index=False):
        train_months = int(row.train_months)
        if train_months not in _TRAIN_PREFERENCE:
            raise NoAutomaticSelection(
                f"unsupported training length {train_months}; expected 36, 24, or 18"
            )
        variation = str(row.variation)
        choices.append(
            (
                int(row.complexity),
                -_decimal(row.mean_ret, label="mean net return"),
                _TRAIN_PREFERENCE[train_months],
                variation,
                train_months,
                str(row.candidate_id),
            )
        )
    complexity, _return_key, _train_key, variation, train_months, candidate_id = min(choices)
    return AutomaticCandidate(variation, train_months, candidate_id, complexity)


def _load_selection_evidence(
    run: rb.RunDir,
) -> tuple[SelectionEvidence, SpaAnalysis, RomanoWolfAnalysis, McsResult]:
    """Strictly load and cross-check the three lineage-bound family artifacts."""
    try:
        spa_payload = json.loads(run.require("spa.json", "edge").read_text(encoding="utf-8"))
        romano_payload = json.loads(
            run.require("romano_wolf.json", "edge").read_text(encoding="utf-8")
        )
        mcs_payload = json.loads(run.require("mcs.json", "edge").read_text(encoding="utf-8"))
        if not isinstance(spa_payload, Mapping):
            raise SpaInputError("SPA evidence must be an object")
        if not isinstance(romano_payload, Mapping):
            raise RomanoWolfInputError("Romano-Wolf evidence must be an object")
        if not isinstance(mcs_payload, Mapping):
            raise McsInputError("MCS evidence must be an object")
        spa = SpaAnalysis.from_dict(spa_payload)
        romano_wolf = RomanoWolfAnalysis.from_dict(romano_payload)
        mcs = McsResult.from_dict(mcs_payload)
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        SpaInputError,
        RomanoWolfInputError,
        McsInputError,
    ) as exc:
        raise NoAutomaticSelection(f"family evidence is invalid: {exc}") from exc

    spa_names = frozenset((spa.selected.candidate_statistics or {}).keys())
    sensitivity_families = {
        frozenset((result.candidate_statistics or {}).keys()) for result in spa.sensitivity.values()
    }
    romano_names = frozenset(candidate.name for candidate in romano_wolf.candidates)
    mcs_names = frozenset(candidate.name for candidate in mcs.candidates)
    if (
        not spa_names
        or len(spa_names) != spa.candidate_count
        or sensitivity_families != {spa_names}
        or spa_names != romano_names
        or spa_names != mcs_names
    ):
        raise NoAutomaticSelection(
            "SPA, Romano-Wolf, and MCS candidate families must be complete and identical"
        )
    shared_shape = (
        spa.selected.block_length,
        spa.replications,
        spa.seed,
        spa.observation_count,
    )
    if shared_shape != (
        romano_wolf.block_length,
        romano_wolf.replications,
        romano_wolf.seed,
        romano_wolf.observation_count,
    ) or shared_shape != (
        mcs.block_length,
        mcs.replications,
        mcs.seed,
        mcs.observation_count,
    ):
        raise NoAutomaticSelection("SPA, Romano-Wolf, and MCS resampling identities must agree")
    evidence = SelectionEvidence(
        family=spa_names,
        spa_passes=spa.passes,
        romano_wolf_eligible=frozenset(romano_wolf.eligible_candidates),
        mcs_members=frozenset(mcs.surviving_candidates),
    )
    return evidence, spa, romano_wolf, mcs


def _best_train(df: pd.DataFrame, variation: str) -> int:
    """The training length with the highest cross-instrument return for a forced variation."""
    sub = df[df["variation"] == variation].dropna(subset=["mean_oos_pct"])
    if sub.empty:
        raise SystemExit(f"variation '{variation}' has no rows in the study")
    per = universe.per_config(sub)
    return int(per["mean_ret"].idxmax()[1])


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Stage 2 (SELECT): structure + market universe.")
    parser.add_argument("--run", type=Path, required=True, help="the framework run directory")
    parser.add_argument("--variation", default=None, help="force this variation (default: auto)")
    parser.add_argument(
        "--allow-legacy-unverified",
        action="store_true",
        help="read a run that predates artifact hashing. Such a run can be inspected but can "
        "NEVER produce a deployable PASS -- its inputs cannot be confirmed.",
    )
    args = parser.parse_args(argv)

    run = rb.RunDir.open(args.run, allow_legacy=bool(args.allow_legacy_unverified))
    rb.banner(2, "SELECT - Struktur & Universum", run)
    # The config anchor is an edge output like any other: if it were swapped, this stage would
    # resolve a different study config than the one the study was computed from.
    run.require("run_manifest.json", "edge")
    # Snapshotted before the selection is computed, like every other stage. This one is fast, but
    # "fast enough that nobody could edit a file mid-run" is a race, not an invariant.
    # Without the catalog: this stage reads only anchored artifacts, never bars. Recording the
    # catalog unscoped would make an unrelated study's reseed mark this selection stale.
    inputs = lineage.external_inputs(run.study_config(), catalog=False)
    cfg = load_config_module(run.study_config())
    df = pd.read_csv(run.require("study.csv", "edge"))
    # #2: the GATED ranking is the only admissible input for an automatic pick. Reading study.csv
    # alone re-derived the choice without the statistical gates the edge stage had applied.
    ranking = pd.read_csv(run.require("edge_ranking.csv", "edge"))
    try:
        evidence, spa, romano_wolf, mcs = _load_selection_evidence(run)
    except NoAutomaticSelection as exc:
        raise SystemExit(f"\n  ABBRUCH: {exc}") from exc

    overfitting: Mapping[str, object] = {}
    if run.file("overfitting.json").exists():
        overfitting_path = run.require("overfitting.json", "edge")
        try:
            raw_overfitting = json.loads(overfitting_path.read_text(encoding="utf-8"))
            if isinstance(raw_overfitting, Mapping):
                overfitting = raw_overfitting
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass
    pbo = _diagnostic_float(overfitting.get("pbo"))

    automatic: AutomaticCandidate | None = None
    if args.variation:
        variation = args.variation
        train_months = _best_train(df, variation)
        instruments = universe.select_universe(df, variation, train_months)
        how = f"erzwungen (--variation {variation})"
    else:
        raw_complexity = getattr(cfg, "COMPLEXITY_SCORES", None)
        if not isinstance(raw_complexity, Mapping):
            raise SystemExit("\n  ABBRUCH: COMPLEXITY_SCORES fehlt oder ist keine Zuordnung.")
        try:
            automatic = choose_automatic_candidate(
                ranking,
                evidence=evidence,
                complexity_scores=raw_complexity,
            )
        except NoAutomaticSelection as exc:
            raise SystemExit(
                f"\n  ABBRUCH: {exc}\n"
                "  Es gibt nichts Handelbares - das ist ein Ergebnis, kein Fehler.\n"
                "  Mit --variation laesst sich eine Wahl erzwingen; der Lauf gilt dann als\n"
                "  explorativ und faellt im Verdict durch."
            ) from exc
        variation, train_months = automatic.variation, automatic.train_months
        instruments = universe.select_universe(df, variation, train_months)
        how = "Auto (SPA + Romano-Wolf + MCS, Komplexitaet-first)"

    # Manifest (#2): carry the gate evidence for the pick forward so the verdict can require it
    # rather than trusting that selection was gated at all. The ranking now holds one row per
    # (variation, train_months), so the manifest must cite the row actually picked.
    row = ranking[(ranking["variation"] == variation) & (ranking["train_months"] == train_months)]
    candidate_id = _candidate_id(variation, train_months)
    romano_by_name = {candidate.name: candidate for candidate in romano_wolf.candidates}
    mcs_by_name = {candidate.name: candidate for candidate in mcs.candidates}
    selected_row = row.iloc[0] if not row.empty else None
    dsr = (
        _diagnostic_float(selected_row["dsr"])
        if selected_row is not None and "dsr" in row.columns and not pd.isna(selected_row["dsr"])
        else None
    )
    dsr_nominal = (
        _diagnostic_float(selected_row["dsr_nominal"])
        if selected_row is not None
        and "dsr_nominal" in row.columns
        and not pd.isna(selected_row["dsr_nominal"])
        else None
    )
    gates: dict[str, object] = {
        "automatic_eligible": automatic is not None,
        "complete": bool(selected_row["complete"]) if selected_row is not None else False,
        "positive_market_ok": (
            _decimal(selected_row["frac_positive"], label="positive-market fraction")
            >= _MIN_FRAC_POSITIVE
            if selected_row is not None
            else False
        ),
        "return_drawdown_ok": (
            _decimal(selected_row["mean_rpd"], label="mean return/drawdown")
            >= _RPD_TOLERANCE
            * max(
                _decimal(value, label="mean return/drawdown")
                for value in ranking["mean_rpd"].tolist()
            )
            if selected_row is not None
            else False
        ),
        "romano_wolf_ok": (
            candidate_id in evidence.romano_wolf_eligible if selected_row is not None else False
        ),
        "romano_wolf_adjusted_p": (
            romano_by_name[candidate_id].adjusted_p_value
            if candidate_id in romano_by_name
            else None
        ),
        "mcs_ok": candidate_id in evidence.mcs_members if selected_row is not None else False,
        "mcs_p_value": (
            mcs_by_name[candidate_id].mcs_p_value if candidate_id in mcs_by_name else None
        ),
        "complexity": automatic.complexity if automatic is not None else None,
        "dsr": dsr,
        "dsr_nominal": dsr_nominal,
        "dsr_diagnostic_ok": dsr is not None and Decimal(str(dsr)) >= Decimal("0.90"),
        "pbo": pbo,
        "pbo_diagnostic_ok": pbo is not None and _diagnostic_at_most(pbo, Decimal("0.20")),
        "frac_positive": (
            float(selected_row["frac_positive"]) if selected_row is not None else None
        ),
        "mean_rpd": float(selected_row["mean_rpd"]) if selected_row is not None else None,
    }
    gates.update(
        {
            "spa_ok": evidence.spa_passes,
            "spa_p_value": spa.selected.p_value,
            "spa_block_length": spa.selected.block_length,
            "spa_sensitivity": {
                str(block_length): result.p_value
                for block_length, result in sorted(spa.sensitivity.items())
            },
        }
    )

    with run.stage(
        "select",
        argv={"run": str(run.path), "variation": str(args.variation or "")},
        inputs=inputs,
        semantics={
            "variation": variation,
            "train_months": train_months,
            "universe": instruments,
            "forced": bool(args.variation),
        },
    ) as st:
        st.save_json(
            "selection.json",
            {
                "variation": variation,
                "train_months": train_months,
                "instruments": instruments,
                "how": how,
                "forced": bool(args.variation),
                "gates": gates,
            },
        )

    print(f"\n  Struktur: {variation} @ {train_months}m Training   [{how}]")
    print(f"  Universum: {len(instruments)} Märkte")
    for m in instruments:
        print(f"    - {m}")
    if not instruments:
        print("    (keine - die Schwellen hat kein Markt geschafft)")

    # --fixed by default (#11): the deployable verdict must trade the frozen live stops. Drop the
    # flag only to explore, and the verdict will mark that run exploratory.
    nxt = rb.cmd("portfolio", "--run", str(run.path), "--fixed", "live/config/rsi_wpr_bb.py")
    rb.next_step(nxt, "Portfolio bauen & Risiko wählen (--risk flat:0.15 oder throttle:0.15,floor)")


if __name__ == "__main__":
    main()
