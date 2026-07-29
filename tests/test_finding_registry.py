"""The finding registry required by constitution section 14 exists and is well-formed.

Every confirmed reviewer finding is reproduced, generalized, and recorded in
`.ai/quality/finding-patterns.toml` so a defect CLASS becomes permanent protection. This validates
the file's existence and schema, and that the four representative defect classes the workflow is
calibrated against are present -- so the registry cannot silently become empty or malformed.
"""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_REGISTRY = _ROOT / ".ai" / "quality" / "finding-patterns.toml"

_REQUIRED_FIELDS = (
    "id",
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


def _registry() -> dict[str, Any]:
    assert _REGISTRY.is_file(), (
        "the finding registry .ai/quality/finding-patterns.toml is missing; constitution "
        "section 14 requires it."
    )
    return tomllib.loads(_REGISTRY.read_text(encoding="utf-8"))


def _findings() -> list[dict[str, Any]]:
    findings = _registry().get("finding", [])
    assert isinstance(findings, list) and findings, "the registry needs at least the seed findings"
    return findings


def test_registry_parses_and_has_findings() -> None:
    assert _registry().get("version") == 1
    assert _findings()


def test_every_finding_is_complete() -> None:
    ids: list[str] = []
    for f in _findings():
        missing = [k for k in _REQUIRED_FIELDS if not str(f.get(k, "")).strip()]
        assert not missing, f"finding {f.get('id', '?')} is missing fields: {missing}"
        assert f["severity"] in ("P0", "P1", "P2", "P3"), f"bad severity in {f['id']}"
        ids.append(str(f["id"]))
    assert len(ids) == len(set(ids)), f"duplicate finding ids: {ids}"


def test_representative_defect_classes_are_recorded() -> None:
    classes = {str(f["defect_class"]) for f in _findings()}
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
        regression = str(finding["regression"])
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
            f"finding {finding['id']} names stale regression protection: "
            f"files={missing_files}, tests={missing_names}, commands={missing_commands}"
        )
        assert file_tokens or name_tokens or command_tokens, (
            f"finding {finding['id']} regression must name an existing test, test file, or just "
            "recipe"
        )
