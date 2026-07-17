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

    if args.variation:
        variation = args.variation
        train_months = _best_train(df, variation)
        instruments = universe.select_universe(df, variation, train_months)
        how = f"erzwungen (--variation {variation})"
    else:
        sel = universe.select(df)
        variation, train_months, instruments = sel.variation, sel.train_months, sel.instruments
        how = "Auto (Rendite-first, Risiko-Gate)"

    run.save_json(
        "selection.json",
        {
            "variation": variation,
            "train_months": train_months,
            "instruments": instruments,
            "how": how,
        },
    )

    print(f"\n  Struktur: {variation} @ {train_months}m Training   [{how}]")
    print(f"  Universum: {len(instruments)} Märkte")
    for m in instruments:
        print(f"    - {m}")
    if not instruments:
        print("    (keine - die Schwellen hat kein Markt geschafft)")

    nxt = rb.cmd("portfolio", "--run", str(run.path))
    rb.next_step(nxt, "Portfolio bauen & Risiko wählen (--risk flat:0.15 oder throttle:0.15,floor)")


if __name__ == "__main__":
    main()
