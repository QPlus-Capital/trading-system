import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).parents[1] / "pyproject.toml"


def test_pytest_warning_policy_is_fail_closed_and_message_scoped() -> None:
    with PYPROJECT.open("rb") as handle:
        config = tomllib.load(handle)

    assert config["tool"]["pytest"]["ini_options"]["filterwarnings"] == [
        "error",
        "ignore:Timestamp.utcnow is deprecated",
    ]


def test_pytest_warning_exception_documents_upstream_call_sites() -> None:
    pyproject = PYPROJECT.read_text(encoding="utf-8")

    documented_exception = (
        "    # Upstream call sites; nautilus-trader 1.230.0 installed; 1.231.0 verified:\n"
        "    # backtest/engine.pyx:1601 and :1418; backtest/node.py:347.\n"
        '    "ignore:Timestamp.utcnow is deprecated",\n'
    )
    assert documented_exception in pyproject
