"""Tests for the live account identity guard -- the safeguard against the wrong account."""

from __future__ import annotations

import re
import subprocess

import pytest
from core.paths import REPO_ROOT
from live.accounts import ACCOUNTS, LiveAccount, get_account, guard_account
from live.mt5_bridge import AccountState

_LOGIN_ENV = "TEST_MT5_LOGIN"
_PATH_ENV = "TEST_MT5_TERMINAL_PATH"
_LOGIN = 123456
_PATH = r"C:\MT5\test\terminal64.exe"
_PROFILE = LiveAccount(
    name="test",
    expected_login_env=_LOGIN_ENV,
    expected_currency="USD",
    start_balance=50_000.0,
    terminal_path_env=_PATH_ENV,
)
_ACCOUNT_ENV_KEYS = {
    "MT5_MEX_LOGIN",
    "MT5_MEX_TERMINAL_PATH",
    "MT5_TTP_LOGIN",
    "MT5_TTP_TERMINAL_PATH",
}
_LOGIN_LITERAL = re.compile(
    r"(?i)\b(?:expected_login|account_login|broker_login)\s*=\s*[1-9][0-9]{5,}\b"
)
_USER_HOME = re.compile(
    r"(?i)(?:[A-Z]:[\\/](?:Users|Documents and Settings)[\\/][^\\/ \t\r\n`\"']+"
    r"|/(?:home|Users)/[^/ \t\r\n`\"']+)"
)


def _state(login: int, currency: str) -> AccountState:
    return AccountState(balance=50_000.0, equity=50_000.0, currency=currency, login=login)


def _configure(
    monkeypatch: pytest.MonkeyPatch,
    *,
    login: str = str(_LOGIN),
    terminal_path: str = _PATH,
) -> None:
    monkeypatch.setenv(_LOGIN_ENV, login)
    monkeypatch.setenv(_PATH_ENV, terminal_path)


def _tracked_text() -> dict[str, str]:
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    paths = completed.stdout.decode().split("\0")
    result: dict[str, str] = {}
    for relative in paths:
        if not relative or relative.startswith("tests/"):
            continue
        path = REPO_ROOT / relative
        try:
            result[relative] = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
    return result


def test_guard_refuses_when_the_login_environment_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(_LOGIN_ENV, raising=False)
    monkeypatch.setenv(_PATH_ENV, _PATH)

    with pytest.raises(SystemExit, match=_LOGIN_ENV):
        guard_account(_state(_LOGIN, "USD"), _PROFILE, execute=True)


def test_guard_passes_on_the_expected_environment_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch)

    guard_account(_state(_LOGIN, "USD"), _PROFILE, execute=True)


def test_guard_refuses_wrong_environment_login_without_disclosing_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch)
    connected_login = 654321

    with pytest.raises(SystemExit) as exc_info:
        guard_account(_state(connected_login, "USD"), _PROFILE, execute=True)

    message = str(exc_info.value)
    assert "does not match" in message
    assert str(_LOGIN) not in message
    assert str(connected_login) not in message


def test_guard_refuses_wrong_currency(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch)

    with pytest.raises(SystemExit, match="currency"):
        guard_account(_state(_LOGIN, "EUR"), _PROFILE, execute=True)


def test_guard_refuses_signal_only_without_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_LOGIN_ENV, raising=False)
    monkeypatch.setenv(_PATH_ENV, _PATH)

    with pytest.raises(SystemExit, match=_LOGIN_ENV):
        guard_account(_state(_LOGIN, "USD"), _PROFILE, execute=False)


@pytest.mark.parametrize(
    "malformed",
    ["", " ", "\t", "not-a-login", " 123456", "123456 ", "12 3456", "0", "-1", "<login>"],
)
def test_login_environment_rejects_malformed_values_without_disclosure(
    monkeypatch: pytest.MonkeyPatch,
    malformed: str,
) -> None:
    _configure(monkeypatch, login=malformed)

    with pytest.raises(SystemExit) as exc_info:
        guard_account(_state(_LOGIN, "USD"), _PROFILE, execute=True)

    assert _LOGIN_ENV in str(exc_info.value)
    if malformed.strip():
        assert malformed not in str(exc_info.value)


@pytest.mark.parametrize("malformed", ["", " ", "\t", "<absolute-path-to-terminal64.exe>"])
def test_terminal_path_environment_rejects_missing_or_placeholder_values(
    monkeypatch: pytest.MonkeyPatch,
    malformed: str,
) -> None:
    _configure(monkeypatch, terminal_path=malformed)

    with pytest.raises(SystemExit) as exc_info:
        _PROFILE.validate_environment()

    assert _PATH_ENV in str(exc_info.value)
    if malformed.strip():
        assert malformed not in str(exc_info.value)


def test_terminal_path_environment_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_LOGIN_ENV, str(_LOGIN))
    monkeypatch.delenv(_PATH_ENV, raising=False)

    with pytest.raises(SystemExit, match=_PATH_ENV):
        _PROFILE.validate_environment()


def test_get_account_resolves_required_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MT5_TTP_LOGIN", str(_LOGIN))
    monkeypatch.setenv("MT5_TTP_TERMINAL_PATH", _PATH)

    profile = get_account("ttp")

    assert profile is ACCOUNTS["ttp"]
    assert profile.expected_login == _LOGIN
    assert profile.terminal_path == _PATH


def test_get_account_rejects_unknown() -> None:
    with pytest.raises(SystemExit, match="unknown account"):
        get_account("nope")


def test_tracked_tree_has_no_account_login_literal_or_user_home_path() -> None:
    texts = _tracked_text()
    login_hits = [path for path, text in texts.items() if _LOGIN_LITERAL.search(text)]
    home_hits = [path for path, text in texts.items() if _USER_HOME.search(text)]

    assert login_hits == [], f"tracked account-login literals: {login_hits}"
    assert home_hits == [], f"tracked absolute user-home paths: {home_hits}"


def test_env_example_contains_only_inert_account_placeholders() -> None:
    values = {
        key: value
        for line in (REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
        for key, separator, value in (line.partition("="),)
        if separator
    }

    assert values.keys() >= _ACCOUNT_ENV_KEYS
    for key in _ACCOUNT_ENV_KEYS:
        assert values[key].startswith("<") and values[key].endswith(">")
        if key.endswith("_LOGIN"):
            assert not any(char.isdigit() for char in values[key])
        assert _USER_HOME.search(values[key]) is None


def test_live_just_recipes_load_the_gitignored_environment_file() -> None:
    justfile = (REPO_ROOT / "justfile").read_text(encoding="utf-8")
    required = (
        "uv run --env-file .env python -m live.run --account ttp",
        "uv run --env-file .env python -m live.run --account ttp --mode execute",
        "uv run --env-file .env python -m live.run --account mex",
        "uv run --env-file .env python -m live.preflight --account ttp",
        "uv run --env-file .env streamlit run monitoring/dashboard.py",
    )

    for command in required:
        assert command in justfile
