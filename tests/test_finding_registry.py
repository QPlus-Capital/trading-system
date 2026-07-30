"""The finding registry required by constitution section 14 exists and is well-formed.

Every confirmed reviewer finding is reproduced, generalized, and recorded as one file under
`.ai/quality/finding-patterns/` so a defect CLASS becomes permanent protection. This validates
the production loader and that the representative defect classes remain present.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from scripts.quality.finding_registry import REGISTRY_PATH, Finding, load_findings

_ROOT = Path(__file__).resolve().parents[1]

_REQUIRED_FIELDS = (
    "source",
    "defect_class",
    "severity",
    "affected",
    "root_cause",
    "why_tests_missed",
    "regression",
    "generalized",
    "workflow_change",
)

#: The four representative classes from the workflow spec that must always be documented.
_REPRESENTATIVE_CLASSES = (
    "lifecycle-side-effect",
    "config-propagation-loss",
    "unclassified-outcome-bucket",
    "numeric-boundary",
)


def _findings() -> tuple[Finding, ...]:
    assert REGISTRY_PATH.is_dir(), "constitution section 14 requires the split finding registry"
    return load_findings()


def test_registry_parses_and_has_findings() -> None:
    assert _findings()


def test_every_finding_is_complete() -> None:
    ids: list[str] = []
    for f in _findings():
        missing = [field for field in _REQUIRED_FIELDS if not str(getattr(f, field)).strip()]
        assert not missing, f"finding {f.id} is missing fields: {missing}"
        assert f.severity in (
            "Blocker",
            "Defect",
            "Suspected defect",
            "Note",
        ), f"bad severity in {f.id}"
        ids.append(f.id)
    assert len(ids) == len(set(ids)), f"duplicate finding ids: {ids}"


def test_old_finding_severity_codes_are_absent_from_active_contracts() -> None:
    active_files = [
        _ROOT / "CLAUDE.md",
        _ROOT / ".ai" / "quality" / "task-artifacts.toml",
        _ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md",
        _ROOT / ".ai" / "tasks" / "_templates" / "review.md",
        *(_ROOT / ".claude").glob("**/*.md"),
        *(_ROOT / "docs" / "engineering").glob("*.md"),
    ]
    stale = {
        path.relative_to(_ROOT).as_posix(): sorted(set(re.findall(r"\bP[0-3]\b", text)))
        for path in active_files
        if (text := path.read_text(encoding="utf-8")) and re.search(r"\bP[0-3]\b", text)
    }
    assert not stale


def test_representative_defect_classes_are_recorded() -> None:
    classes = {f.defect_class for f in _findings()}
    missing = [c for c in _REPRESENTATIVE_CLASSES if c not in classes]
    assert not missing, (
        f"the registry must document the representative defect classes; missing: {missing}"
    )


def test_every_finding_registry_regression_reference_resolves() -> None:
    """A confirmed finding may not outlive the executable protection it names."""
    test_names: set[str] = set()
    for path in (_ROOT / "tests").glob("test_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        test_names.update(
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        )

    justfile = (_ROOT / "justfile").read_text(encoding="utf-8")
    for finding in _findings():
        regression = finding.regression
        file_tokens = re.findall(r"(?:tests/)?(test_[A-Za-z0-9_]+\.py)", regression)
        without_files = re.sub(r"(?:tests/)?test_[A-Za-z0-9_]+\.py", "", regression)
        name_tokens = re.findall(r"\b(test_[A-Za-z0-9_]+)\b", without_files)
        command_tokens = re.findall(r"\bjust ([A-Za-z0-9_-]+)\b", regression)

        missing_files = [token for token in file_tokens if not (_ROOT / "tests" / token).is_file()]
        missing_names = [token for token in name_tokens if token not in test_names]
        missing_commands = [
            token
            for token in command_tokens
            if not re.search(rf"(?m)^{re.escape(token)}(?:\s[^:]*)?:", justfile)
        ]
        assert not (missing_files or missing_names or missing_commands), (
            f"finding {finding.id} names stale regression protection: "
            f"files={missing_files}, tests={missing_names}, commands={missing_commands}"
        )
        assert file_tokens or name_tokens or command_tokens, (
            f"finding {finding.id} regression must name an existing test, test file, or just recipe"
        )
