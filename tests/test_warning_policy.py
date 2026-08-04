"""Keep pytest warnings fail closed while documenting the one verified upstream exception."""

import ast
import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).parents[1] / "pyproject.toml"


def test_warning_policy_test_module_explains_why_warnings_fail_closed() -> None:
    module = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    docstring = ast.get_docstring(module)

    assert docstring is not None
    assert "fail closed" in docstring.lower()


def test_pytest_warning_policy_is_fail_closed_and_message_scoped() -> None:
    with PYPROJECT.open("rb") as handle:
        config = tomllib.load(handle)

    assert config["tool"]["pytest"]["ini_options"]["filterwarnings"] == [
        "error",
        "ignore:Timestamp.utcnow is deprecated",
    ]


def test_pytest_warning_exception_documents_call_sites_and_versions() -> None:
    pyproject = PYPROJECT.read_text(encoding="utf-8")

    for call_site in (
        "backtest/engine.pyx:1601",
        "backtest/engine.pyx:1418",
        "backtest/node.py:347",
    ):
        assert call_site in pyproject
    for version in ("1.230.0", "1.231.0"):
        assert version in pyproject
