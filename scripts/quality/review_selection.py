"""Select Claude's read-only review agents from effective risk and touched paths."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from scripts.quality.classify import changed_paths

_RISK_CLASSES = ("R0", "R1", "R2", "R3")
_BASE_REVIEWERS = ("adversarial-code-reviewer", "test-quality-reviewer")
_LIVE_REVIEWER = "live-money-reviewer"
_METHODOLOGY_REVIEWER = "methodology-reviewer"


def _normalized(path: str) -> str:
    return path.replace("\\", "/").removeprefix("./")


def _is_live_path(path: str) -> bool:
    return _normalized(path).startswith("live/")


def _is_methodology_path(path: str) -> bool:
    normalized = _normalized(path)
    return (
        normalized.startswith("research/")
        or normalized == "docs/methodology.md"
        or normalized.startswith("docs/strategies/")
    )


def select_reviewers(risk_class: str, paths: Sequence[str]) -> tuple[str, ...]:
    """Return the exact ordered reviewer set for an effective risk/path combination."""

    normalized_risk = risk_class.upper()
    if normalized_risk not in _RISK_CLASSES:
        raise ValueError(f"unknown risk class: {risk_class}")
    if normalized_risk in {"R0", "R1"}:
        return ()

    reviewers = list(_BASE_REVIEWERS)
    if normalized_risk == "R3":
        if any(_is_live_path(path) for path in paths):
            reviewers.append(_LIVE_REVIEWER)
        if any(_is_methodology_path(path) for path in paths):
            reviewers.append(_METHODOLOGY_REVIEWER)
    return tuple(reviewers)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("risk_class", choices=_RISK_CLASSES)
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--path", action="append", default=[])
    args = parser.parse_args(argv)
    paths = tuple(args.path) or tuple(changed_paths(args.base))
    for reviewer in select_reviewers(args.risk_class, paths):
        print(reviewer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
