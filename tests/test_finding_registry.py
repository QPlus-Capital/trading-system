"""The finding registry required by constitution section 14 exists and is well-formed.

Every confirmed reviewer finding is reproduced, generalized, and recorded in
`.ai/quality/finding-patterns.toml` so a defect CLASS becomes permanent protection. This validates
the file's existence and schema, and that the four representative defect classes the workflow is
calibrated against are present -- so the registry cannot silently become empty or malformed.
"""

from __future__ import annotations

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
