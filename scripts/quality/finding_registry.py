"""Load the conflict-free, content-addressed reviewer-finding registry."""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from scripts.quality.classify import REPO_ROOT

REGISTRY_PATH = REPO_ROOT / ".ai" / "quality" / "finding-patterns"
_LEGACY_MANIFEST = "legacy-manifest.toml"
_LEGACY_ID = re.compile(r"F-\d{3}")
_CONTENT_NAME = re.compile(r"[0-9a-f]{64}")
_FIELDS = (
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
_SEVERITIES = frozenset({"P0", "P1", "P2", "P3"})


@dataclass(frozen=True)
class Finding:
    """One complete reviewer finding; ``id`` is assigned by the registry loader."""

    id: str
    source: str
    defect_class: str
    severity: str
    affected: str
    root_cause: str
    why_tests_missed: str
    regression: str
    generalized: str
    workflow_change: str

    @property
    def content(self) -> dict[str, str]:
        """Return the ID-independent content used for hashing and persistence."""

        return {field: str(getattr(self, field)) for field in _FIELDS}


def _canonical_content(content: dict[str, str]) -> bytes:
    return json.dumps(
        {field: content[field] for field in _FIELDS},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_content_hash(finding: Finding) -> str:
    """Return the stable content digest from which a new finding ID is derived."""

    return hashlib.sha256(_canonical_content(finding.content)).hexdigest()


def _finding_from_file(path: Path) -> Finding:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    if raw.get("version") != 1:
        raise ValueError(f"{path.name}: finding file version must be 1")
    table = raw.get("finding")
    if not isinstance(table, dict):
        raise ValueError(f"{path.name}: finding must be a TOML table")
    keys = set(table)
    if keys != set(_FIELDS):
        extra = sorted(keys - set(_FIELDS))
        missing = sorted(set(_FIELDS) - keys)
        reason = "finding IDs are derived and may not be claimed" if "id" in extra else "bad schema"
        raise ValueError(f"{path.name}: {reason}; missing={missing}, extra={extra}")
    content = {field: str(table[field]).strip() for field in _FIELDS}
    empty = [field for field, value in content.items() if not value]
    if empty:
        raise ValueError(f"{path.name}: empty finding fields: {empty}")
    if content["severity"] not in _SEVERITIES:
        raise ValueError(f"{path.name}: unsupported severity {content['severity']!r}")
    return Finding(id="", **content)


def _legacy_hashes(registry: Path) -> dict[str, str]:
    manifest = registry / _LEGACY_MANIFEST
    if not manifest.is_file():
        return {}
    raw = tomllib.loads(manifest.read_text(encoding="utf-8"))
    if raw.get("version") != 1 or not isinstance(raw.get("content_sha256"), dict):
        raise ValueError("legacy finding manifest must contain version 1 content_sha256")
    hashes = cast(dict[object, object], raw["content_sha256"])
    result = {str(key): str(value) for key, value in hashes.items()}
    if any(_LEGACY_ID.fullmatch(key) is None for key in result):
        raise ValueError("legacy finding manifest contains an invalid ID")
    if any(_CONTENT_NAME.fullmatch(value) is None for value in result.values()):
        raise ValueError("legacy finding manifest contains an invalid content digest")
    return result


def load_findings(registry: Path = REGISTRY_PATH) -> tuple[Finding, ...]:
    """Load every finding and fail closed on hand-picked, duplicate, or altered IDs."""

    legacy_hashes = _legacy_hashes(registry)
    findings: list[Finding] = []
    ids: set[str] = set()
    seen_legacy: set[str] = set()
    for path in sorted(registry.glob("*.toml")):
        if path.name == _LEGACY_MANIFEST:
            continue
        finding = _finding_from_file(path)
        digest = canonical_content_hash(finding)
        if _LEGACY_ID.fullmatch(path.stem):
            finding_id = path.stem
            expected = legacy_hashes.get(finding_id)
            if expected is None:
                raise ValueError(f"{path.name}: numeric IDs are reserved for the migrated registry")
            if digest != expected:
                raise ValueError(f"{path.name}: migrated finding content changed")
            seen_legacy.add(finding_id)
        elif _CONTENT_NAME.fullmatch(path.stem):
            if path.stem != digest:
                raise ValueError(
                    f"{path.name}: content-addressed filename does not match its finding"
                )
            finding_id = f"F-{digest.upper()}"
        else:
            raise ValueError(
                f"{path.name}: finding filename must be a migrated ID or its content digest"
            )
        if finding_id in ids:
            raise ValueError(f"duplicate derived finding ID: {finding_id}")
        ids.add(finding_id)
        findings.append(Finding(id=finding_id, **finding.content))
    missing_legacy = sorted(set(legacy_hashes) - seen_legacy)
    if missing_legacy:
        raise ValueError(f"migrated finding files are missing: {missing_legacy}")
    if not findings:
        raise ValueError("finding registry must not be empty")
    return tuple(sorted(findings, key=lambda item: item.id))


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def write_finding(registry: Path, finding: Finding) -> Path:
    """Write one new content-addressed finding without choosing or sharing an ID."""

    if finding.id:
        raise ValueError("finding IDs are derived and may not be claimed")
    digest = canonical_content_hash(finding)
    path = registry / f"{digest}.toml"
    registry.mkdir(parents=True, exist_ok=True)
    lines = ["version = 1", "", "[finding]"]
    lines.extend(f"{field} = {_toml_string(finding.content[field])}" for field in _FIELDS)
    content = f"{'\n'.join(lines)}\n"
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise ValueError("content-addressed finding path contains different content")
    path.write_text(content, encoding="utf-8")
    return path
