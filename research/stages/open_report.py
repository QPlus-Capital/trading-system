"""Open a run's report, refusing when its lineage no longer holds.

The report is where an operator reads a verdict and acts on it, so it is the last place that may
show a stale PASS. Artifacts are quarantined when an upstream stage is republished, but a config,
raw CSV, swap snapshot or catalog marker can change in place without any rerun -- the files then
sit there looking current while :func:`research.stages.lineage.verify_artifact` would reject them.

Usage::

    uv run python -m research.stages.open_report            # newest run
    uv run python -m research.stages.open_report --run DIR  # a specific one
    uv run python -m research.stages.open_report --no-open  # verify only
"""

from __future__ import annotations

import argparse
import webbrowser
from pathlib import Path

from research.stages import _runbook as rb
from research.stages import lineage


def newest_run() -> Path | None:
    runs = sorted(rb.RESEARCH_ROOT.glob("run_*"))
    return runs[-1] if runs else None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Open a run's report, lineage permitting.")
    parser.add_argument("--run", type=Path, default=None, help="run directory (default: newest)")
    parser.add_argument("--no-open", action="store_true", help="verify only, do not open")
    args = parser.parse_args(argv)

    run_path = args.run or newest_run()
    if run_path is None:
        raise SystemExit("no runs yet under reports/research/")
    report = run_path / "report.html"
    if not report.is_file():
        raise SystemExit(f"no report.html in {run_path}")

    run = rb.RunDir.open(run_path)
    # The WHOLE run, not just the stage that wrote the report: the verdict's own inputs can be
    # untouched while the config Stage 1 selected under was edited in place. An operator opening
    # this file is trusting the entire chain behind it.
    try:
        lineage.verify_run(run_path)
        run.require("report.html", "verdict")
        verdict = lineage.read_manifest(run_path, "verdict")
        passed = bool((verdict.semantics if verdict else {}).get("passed"))
    except SystemExit as exc:
        raise SystemExit(
            f"\n  REPORT NICHT GUELTIG: {run_path.name}\n\n  {exc}\n\n"
            "  Der Report beschreibt nicht mehr den Stand auf der Platte. Stufen neu laufen\n"
            "  lassen, bevor daraus eine Entscheidung abgeleitet wird."
        ) from None

    print(f"\n  Herkunft verifiziert: {run_path.name}   Urteil: "
          f"{'PASS - handelbar' if passed else 'FAIL - nicht handelbar'}")
    if not args.no_open:
        webbrowser.open(report.resolve().as_uri())


if __name__ == "__main__":
    main()
