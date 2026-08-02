"""Self-tests for the boundaries the test suite itself must never cross.

These guard the rule that no test may reach a real broker: the suite must be importable and green
on a machine that has the Windows-only MetaTrader 5 package, without any test being able to call
into it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests import conftest as test_config


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
