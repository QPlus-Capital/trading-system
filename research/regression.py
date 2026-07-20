"""Compare a candidate run against an immutable reference run, against stated expectations.

A numerical change is only reviewable if what SHOULD move, and by how much, was written down
before the numbers were seen. This turns that statement into a check: metrics expected to shift a
little are bounded, artifacts expected not to shift at all are compared by content, and anything
outside either lands in ``unexpected_changes``.

A non-empty ``unexpected_changes`` is a stop, not a note. The point is to make "the numbers moved
more than we said they would" impossible to skim past.

Usage::

    uv run python -m research.regression --issue 32 \\
        --pair run_20260718_2310=reports/research/run_NEW \\
        --out reports/research/regression/32-comparison.json
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.paths import REPO_ROOT

from research.stages.lineage import sha256_file

#: Artifacts a change must leave byte-identical. ``full_history_trades.csv`` is produced by
#: full-history backtests at one constant parameter set (:func:`research.portfolio.tail
#: .full_history_trades`), so nothing about the walk-forward can reach it -- if it moved, the
#: change did something other than what it claimed.
INVARIANT_ARTIFACTS: tuple[str, ...] = ("full_history_trades.csv",)

REFERENCE_ROOT = REPO_ROOT / "reports" / "research"


@dataclass(frozen=True)
class Thresholds:
    """How far each metric may move before it stops being an expected effect."""

    trade_count_pct: float = 1.0  # trade-count change, percent of the reference count
    annual_return_pp: float = 2.0  # annual return, percentage POINTS


@dataclass
class Comparison:
    """One reference/candidate pair, and every way it left the stated expectation."""

    reference: str
    candidate: str
    metrics: dict[str, Any] = field(default_factory=dict)
    unexpected: list[str] = field(default_factory=list)


def _spec(run: Path) -> dict[str, Any]:
    f = run / "portfolio.json"
    if not f.is_file():
        raise SystemExit(f"{run} has no portfolio.json -- it did not reach the portfolio stage")
    return dict(json.loads(f.read_text(encoding="utf-8")))


def _delta(label: str, before: float, after: float) -> dict[str, float]:
    return {f"{label}_before": before, f"{label}_after": after, f"{label}_delta": after - before}


def compare(reference: Path, candidate: Path, thresholds: Thresholds) -> Comparison:
    """Measure one pair and record every departure from the stated expectation."""
    ref, cand = _spec(reference), _spec(candidate)
    out = Comparison(reference=reference.name, candidate=candidate.name)

    ref_trades, cand_trades = float(ref["n_trades"]), float(cand["n_trades"])
    out.metrics |= _delta("n_trades", ref_trades, cand_trades)
    # A comparison against NaN is False, so a non-finite metric would slip past every bound
    # below and be reported as within expectation. It is missing evidence, not a passing value.
    for label, value in (
        ("n_trades", ref_trades), ("n_trades", cand_trades),
        ("ann_return_pct", float(ref["ann_return_pct"])),
        ("ann_return_pct", float(cand["ann_return_pct"])),
    ):
        if not math.isfinite(value):
            out.unexpected.append(
                f"{label} is not a finite number ({value}); it cannot be compared, and a "
                "non-finite value silently satisfies every threshold."
            )
    if not ref_trades:
        # A percentage of zero is not zero drift, it is undefined. Reporting 0% would let a
        # candidate that invented trades out of an empty reference pass the bound silently.
        out.metrics["n_trades_drift_pct"] = None
        if cand_trades:
            out.unexpected.append(
                f"the reference traded nothing, the candidate traded {cand_trades:.0f} -- "
                "there is no baseline to bound this against."
            )
        drift_pct = 0.0
    else:
        drift_pct = abs(cand_trades - ref_trades) / ref_trades * 100.0
        out.metrics["n_trades_drift_pct"] = round(drift_pct, 3)
    if ref_trades and drift_pct > thresholds.trade_count_pct:
        out.unexpected.append(
            f"trade count moved {drift_pct:.2f}% (limit {thresholds.trade_count_pct:.2f}%): "
            f"{ref_trades:.0f} -> {cand_trades:.0f}. Expected changes sit at window seams only, "
            "so a larger shift means something other than seam handling changed."
        )

    ref_ann, cand_ann = float(ref["ann_return_pct"]), float(cand["ann_return_pct"])
    out.metrics |= _delta("ann_return_pct", ref_ann, cand_ann)
    if abs(cand_ann - ref_ann) > thresholds.annual_return_pp:
        out.unexpected.append(
            f"annual return moved {cand_ann - ref_ann:+.2f} percentage points "
            f"(limit {thresholds.annual_return_pp:.2f}): {ref_ann:.2f}% -> {cand_ann:.2f}%."
        )

    # Reported for judgement, deliberately not thresholded: the issue states an expectation for
    # trade count and annual return only, and inventing a bound here would be a number nobody
    # agreed to.
    for label in ("max_drawdown_pct", "total_return_pct"):
        if label in ref and label in cand:
            out.metrics |= _delta(label, float(ref[label]), float(cand[label]))

    for name in INVARIANT_ARTIFACTS:
        before, after = reference / name, candidate / name
        if not before.is_file() or not after.is_file():
            out.unexpected.append(f"{name} is missing from one side; it cannot be compared")
            continue
        if sha256_file(before) != sha256_file(after):
            out.unexpected.append(
                f"{name} changed, but nothing in this change can reach it -- it comes from "
                "full-history backtests at one constant parameter set, never from the "
                "walk-forward."
            )
    return out


def build_report(
    issue: str, pairs: list[tuple[Path, Path]], thresholds: Thresholds
) -> dict[str, Any]:
    comparisons = [compare(ref, cand, thresholds) for ref, cand in pairs]
    return {
        "issue": issue,
        "generated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "thresholds": asdict(thresholds),
        "invariant_artifacts": list(INVARIANT_ARTIFACTS),
        "comparisons": [asdict(c) for c in comparisons],
        "unexpected_changes": [
            f"{c.reference} -> {c.candidate}: {reason}"
            for c in comparisons
            for reason in c.unexpected
        ],
    }


def _resolve(spec: str) -> tuple[Path, Path]:
    if "=" not in spec:
        raise SystemExit(f"--pair needs REFERENCE=CANDIDATE, got {spec!r}")
    ref, cand = spec.split("=", 1)
    ref_path = Path(ref) if "/" in ref or "\\" in ref else REFERENCE_ROOT / ref
    cand_path = Path(cand) if "/" in cand or "\\" in cand else REFERENCE_ROOT / cand
    for p in (ref_path, cand_path):
        if not p.is_dir():
            raise SystemExit(f"run directory not found: {p}")
    return ref_path, cand_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Compare candidate runs against references.")
    parser.add_argument("--issue", required=True, help="the issue this change belongs to")
    parser.add_argument(
        "--pair", action="append", required=True, metavar="REFERENCE=CANDIDATE",
        help="a reference run and the candidate that replaces it (repeatable)",
    )
    parser.add_argument("--out", type=Path, required=True, help="where to write the report")
    parser.add_argument("--trade-count-pct", type=float, default=Thresholds.trade_count_pct)
    parser.add_argument("--annual-return-pp", type=float, default=Thresholds.annual_return_pp)
    args = parser.parse_args(argv)

    thresholds = Thresholds(
        trade_count_pct=args.trade_count_pct, annual_return_pp=args.annual_return_pp
    )
    report = build_report(args.issue, [_resolve(s) for s in args.pair], thresholds)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"\n  Regressionsbericht: {args.out}")
    for c in report["comparisons"]:
        m = c["metrics"]
        drift = m["n_trades_drift_pct"]
        drift_txt = "n/a" if drift is None else f"{drift:+.2f}%"
        print(
            f"    {c['reference']:24s} -> {c['candidate']:24s} "
            f"trades {m['n_trades_before']:.0f}->{m['n_trades_after']:.0f} ({drift_txt})  "
            f"annual {m['ann_return_pct_before']:.1f}%->{m['ann_return_pct_after']:.1f}%"
        )
    if report["unexpected_changes"]:
        detail = "\n    - ".join(report["unexpected_changes"])
        raise SystemExit(
            f"\n  UNERWARTETE AENDERUNGEN ({len(report['unexpected_changes'])}):\n    - {detail}\n"
            "\n  Diese Zahlen bewegen sich staerker als angekuendigt. Ursache klaeren, bevor\n"
            "  daraus eine Entscheidung wird -- der Bericht allein rechtfertigt sie nicht."
        )
    print("  Alle Aenderungen liegen im angekuendigten Rahmen.\n")


if __name__ == "__main__":
    main()
