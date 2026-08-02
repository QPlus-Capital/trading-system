"""Change-risk classifier: map changed paths to their R0-R3 class from the authoritative model.

Reads the ``[risk]`` table of ``.ai/workflow.toml`` (safe-by-default) and reports the highest class
over a change set, with the reason for each contributing path. Path matching is a **conservative
minimum**: the author must upgrade when the semantic impact is broader than the paths suggest
(``docs/engineering/workflow.md`` section 5). This module is the single implementation of the
matcher -- the guard test imports it, so the model, the tests and the tooling cannot disagree.

CLI::

    uv run python -m scripts.quality.classify              # branch vs origin/main
    uv run python -m scripts.quality.classify --base HEAD~1
    uv run python -m scripts.quality.classify a/b.py c/d.md # explicit paths
"""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
import tomllib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = REPO_ROOT / ".ai" / "workflow.toml"

CLASSES = ("R0", "R1", "R2", "R3")
_RANK = {c: i for i, c in enumerate(CLASSES)}


@dataclass(frozen=True)
class Rule:
    glob: str
    min_class: str
    reason: str


@dataclass(frozen=True)
class Model:
    default_min_class: str
    docs_only_globs: tuple[str, ...]
    rules: tuple[Rule, ...]
    gates: dict[str, tuple[str, ...]]  # class -> the gate identifiers it requires

    def required_gates(self, risk_class: str) -> tuple[str, ...]:
        """The gates a change of this class must pass, cumulative through the lower classes."""
        ordered = [c for c in CLASSES if _RANK[c] <= _RANK[risk_class]]
        seen: dict[str, None] = {}
        for c in ordered:
            for gate in self.gates.get(c, ()):
                seen.setdefault(gate, None)
        return tuple(seen)


def load_model(path: Path = MODEL_PATH) -> Model:
    """Load the risk model from the ``[risk]`` table of the workflow contract."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))["risk"]
    default = str(data["default_min_class"])
    if default not in CLASSES:
        raise ValueError(f"default_min_class {default!r} is not one of {CLASSES}")
    rules = tuple(
        Rule(str(r["glob"]), str(r["min_class"]), str(r["reason"])) for r in data["rules"]
    )
    for rule in rules:
        if rule.min_class not in CLASSES:
            raise ValueError(f"rule {rule.glob!r} has unknown class {rule.min_class!r}")
    gates = {
        cid: tuple(str(g) for g in spec.get("gates", []))
        for cid, spec in data.get("classes", {}).items()
    }
    return Model(default, tuple(str(g) for g in data["docs_only_globs"]), rules, gates)


@dataclass(frozen=True)
class PathClass:
    path: str
    risk_class: str
    reason: str


def normalize(path: str) -> str:
    """Repository-relative, forward-slash form -- so ``./live/runner.py``, a backslash spelling, and
    an absolute path under the repo all match the same rule as ``live/runner.py``.

    Without this, an ordinary spelling would miss ``live/**`` and be reported as the safe default
    (R2) instead of R3, silently dropping the live-money gates. A path outside the repo is returned
    unchanged (it cannot match a repo rule anyway).
    """
    raw = Path(path)
    if raw.is_absolute():
        try:
            return raw.resolve().relative_to(REPO_ROOT).as_posix()
        except ValueError:
            return raw.as_posix()
    slashed = path.replace("\\", "/")
    while slashed.startswith("./"):
        slashed = slashed[2:]
    return slashed


def classify_path(path: str, model: Model) -> PathClass:
    """The class of one path: the highest matching rule (explicit rules win over the docs-only
    fallback), else R0 for a plain non-governance document, else the safe default.

    ``fnmatchcase`` is deterministic across platforms and its ``*`` spans ``/``, so ``core/**``
    matches a nested file. Among equal-class matches the first in file order wins, and the rules are
    ordered most-specific first, so the reason is the specific one.
    """
    path = normalize(path)
    matched = [r for r in model.rules if fnmatch.fnmatchcase(path, r.glob)]
    if matched:
        best = max(matched, key=lambda r: _RANK[r.min_class])
        return PathClass(path, best.min_class, best.reason)
    if any(fnmatch.fnmatchcase(path, g) for g in model.docs_only_globs):
        return PathClass(path, "R0", "plain documentation")
    return PathClass(path, model.default_min_class, "unmatched path (safe default)")


@dataclass(frozen=True)
class Classification:
    risk_class: str
    per_path: tuple[PathClass, ...]

    @property
    def reasons(self) -> tuple[str, ...]:
        """The distinct reasons of the paths that set the overall (top) class."""
        seen: dict[str, None] = {}
        for pc in self.per_path:
            if pc.risk_class == self.risk_class:
                seen.setdefault(pc.reason, None)
        return tuple(seen)


def classify_paths(paths: Iterable[str], model: Model) -> Classification:
    per = tuple(classify_path(p, model) for p in paths)
    if not per:
        return Classification("R0", ())
    top = max((pc.risk_class for pc in per), key=lambda c: _RANK[c])
    return Classification(top, per)


def changed_paths(base: str, root: Path = REPO_ROOT) -> list[str]:
    """Repo-relative paths changed on this branch vs ``base`` (committed), forward slashes.

    Uses the three-dot form so only the branch's own commits count, not changes ``base`` gained
    since it diverged. ``--no-renames`` is essential: with rename detection a ``git mv`` of a
    live-money file to a document would report only the destination, hiding the R3 source and its
    gates; without it a rename shows as a delete + add, so both sides are classified. Raises if git
    fails, so a broken invocation cannot silently classify nothing.
    """
    result = subprocess.run(
        ["git", "diff", "--no-renames", "--name-only", f"{base}...HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify a change set's risk (R0-R3).")
    parser.add_argument("paths", nargs="*", help="explicit paths; default: git diff vs --base")
    parser.add_argument("--base", default="origin/main", help="base ref for the diff")
    args = parser.parse_args(argv)

    model = load_model()
    paths = list(args.paths) or changed_paths(args.base)
    result = classify_paths(paths, model)

    if not paths:
        print("No changed paths.")
        return 0
    print(f"Risk class: {result.risk_class}")
    for reason in result.reasons:
        print(f"  - {reason}")
    print("\n  Required gates:")
    for gate in model.required_gates(result.risk_class):
        print(f"    - {gate}")
    print(f"\n  {len(paths)} path(s):")
    for pc in result.per_path:
        print(f"    {pc.risk_class}  {pc.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
