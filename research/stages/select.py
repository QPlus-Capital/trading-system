"""Stage 2 — SELECT: which structure (variation + training length) and which markets?

Reads the study anchored by Stage 1 and applies the return-first, risk-gated selection: the
single (variation, training length) with the highest cross-instrument OOS return among the
risk-tolerable ones, then the markets whose own edge clears the thresholds. You can override the
auto-variation with ``--variation`` to carry forward the one you decided on in Stage 1.

Usage::

    uv run python -m research.stages.select --run reports/research/run_X [--variation X]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from research.stages import _runbook as rb
from research.stages import universe


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
    args = parser.parse_args(argv)

    run = rb.RunDir.open(args.run)
    rb.banner(2, "SELECT - Struktur & Universum", run)
    df = pd.read_csv(run.require("study.csv", "edge"))
    # #2: the GATED ranking is the only admissible input for an automatic pick. Reading study.csv
    # alone re-derived the choice without the statistical gates the edge stage had applied.
    ranking = pd.read_csv(run.require("edge_ranking.csv", "edge"))

    if args.variation:
        variation = args.variation
        train_months = _best_train(df, variation)
        instruments = universe.select_universe(df, variation, train_months)
        how = f"erzwungen (--variation {variation})"
    else:
        gated = ranking[ranking["eligible"].astype(bool) & ranking["dsr_ok"].astype(bool)]
        if gated.empty:
            raise SystemExit(
                "\n  ABBRUCH: keine Variation besteht die Gates (eligible + DSR).\n"
                "  Es gibt nichts Handelbares - das ist ein Ergebnis, kein Fehler.\n"
                "  Mit --variation laesst sich eine Wahl erzwingen; der Lauf gilt dann als\n"
                "  explorativ und faellt im Verdict durch."
            )
        top = gated.sort_values("mean_ret", ascending=False).iloc[0]
        variation, train_months = str(top["variation"]), int(top["train_months"])
        instruments = universe.select_universe(df, variation, train_months)
        how = "Auto (Rendite-first, Risiko- + DSR-Gate)"

    # Manifest (#2): carry the gate evidence for the pick forward so the verdict can require it
    # rather than trusting that selection was gated at all.
    row = ranking[ranking["variation"] == variation]
    gates = (
        {
            "eligible": bool(row.iloc[0]["eligible"]),
            "dsr_ok": bool(row.iloc[0]["dsr_ok"]),
            "dsr": None if pd.isna(row.iloc[0]["dsr"]) else float(row.iloc[0]["dsr"]),
            "frac_positive": float(row.iloc[0]["frac_positive"]),
            "mean_rpd": float(row.iloc[0]["mean_rpd"]),
        }
        if not row.empty
        else {"eligible": False, "dsr_ok": False, "dsr": None}
    )

    run.save_json(
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
