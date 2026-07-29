"""End-to-end workflow self-tests required by engineering constitution section 18."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from scripts.quality.pr_ready import assess_readiness

from tests import conftest as test_config
from tests.test_quality_validate_task import _task


def _finding_review(severity: str, status: str) -> str:
    return (
        "# Review\n\n## Findings\n"
        "| ID | Severity | Finding | Disposition | Status |\n"
        "|---|---|---|---|---|\n"
        f"| R-01 | {severity} | Counterexample | Recorded | {status} |\n\n"
        "## Dispositions\nRecorded.\n"
    )


def test_a_note_finding_does_not_block_readiness(tmp_path: Path) -> None:
    task = _task(tmp_path)
    (task / "review.md").write_text(_finding_review("Note", "open"), encoding="utf-8")
    assert assess_readiness(task, ["scripts/tool.py"], "abc123").ready


def test_workflow_self_tests_have_no_live_or_network_imports() -> None:
    path = Path(__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not {name for name in imports if name == "live" or name.startswith("live.")}
    assert not imports & {"socket", "requests", "httpx", "urllib"}


def test_pytest_blocks_real_mt5_boundaries() -> None:
    mt5 = test_config._load_mt5_module()
    if mt5 is None:
        pytest.skip("the real MetaTrader5 package is available only on the Windows boundary job")
    assert getattr(mt5.initialize, "__qplus_test_block__", False)
    assert getattr(mt5.order_send, "__qplus_test_block__", False)


def test_pytest_boundary_imports_without_the_windows_only_mt5_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(test_config, "_mt5_available", lambda: False)
    assert test_config._load_mt5_module() is None
