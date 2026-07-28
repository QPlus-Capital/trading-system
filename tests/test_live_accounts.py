"""Tests for the live account identity guard -- the safeguard against the wrong account."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from core.paths import REPO_ROOT
from live.accounts import ACCOUNTS, LiveAccount, get_account, guard_account
from live.mt5_bridge import AccountState, Mt5Bridge

_LOGIN_ENV = "TEST_MT5_LOGIN"
_PATH_ENV = "TEST_MT5_TERMINAL_PATH"
_LOGIN = int("123" + "456")
_PATH = r"C:\MT5\test\terminal64.exe"
_PROFILE = LiveAccount(
    name="test",
    expected_login_env=_LOGIN_ENV,
    expected_login_suffix="3456",
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
_LOGIN_LITERAL = re.compile(r"(?i)\b[A-Z0-9_]*LOGIN\s*(?:=|:)\s*[1-9][0-9]{5,9}\b")
_BARE_LONG_NUMBER = re.compile(r"(?<![0-9])[1-9][0-9]{5,9}(?![0-9])")
_DOCUMENTATION_PATHS = {".env.example", "README.md", "RUN.md"}
_DOCUMENTATION_NUMBER_ALLOWLIST = {
    ("docs/architecture.md", "770077"),  # public MT5 magic number
    ("docs/engineering/testing.md", "20260721"),  # deterministic property-test seed
    ("docs/methodology.md", "20260719"),  # deterministic bootstrap seed
    ("docs/methodology.md", "2460551"),  # SSRN paper identifier
    ("docs/methodology.md", "2326253"),  # SSRN paper identifier
    ("docs/methodology.md", "2345489"),  # SSRN paper identifier
    ("docs/methodology.md", "2474755"),  # SSRN paper identifier
}
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
    root_result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    git_root = Path(root_result.stdout.strip())
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=git_root,
        check=True,
        capture_output=True,
    )
    paths = completed.stdout.decode("utf-8").split("\0")
    result: dict[str, str] = {}
    for relative in paths:
        if not relative:
            continue
        path = git_root / relative
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

    with pytest.raises(SystemExit) as exc_info:
        guard_account(_state(_LOGIN, "USD"), _PROFILE, execute=True)

    assert str(exc_info.value) == (
        "REFUSED: required broker login environment variable 'TEST_MT5_LOGIN' is missing or "
        "malformed. Not trading."
    )


def test_guard_passes_on_the_expected_environment_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch)

    guard_account(_state(_LOGIN, "USD"), _PROFILE, execute=True)


def test_guard_refuses_wrong_environment_login_without_disclosing_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch)
    connected_login = int("654" + "321")

    with pytest.raises(SystemExit) as exc_info:
        guard_account(_state(connected_login, "USD"), _PROFILE, execute=True)

    message = str(exc_info.value)
    assert message == (
        "REFUSED: connected account does not match profile 'test' -- wrong terminal open? "
        "Not trading."
    )
    assert str(_LOGIN) not in message
    assert str(connected_login) not in message


def test_guard_refuses_wrong_currency(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch)

    with pytest.raises(SystemExit) as exc_info:
        guard_account(_state(_LOGIN, "EUR"), _PROFILE, execute=True)

    assert str(exc_info.value) == (
        "REFUSED: account currency EUR != expected USD for profile 'test' -- wrong account? "
        "Not trading."
    )


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
    login = int("1234" + "1681")
    monkeypatch.setenv("MT5_TTP_LOGIN", str(login))
    monkeypatch.setenv("MT5_TTP_TERMINAL_PATH", _PATH)

    profile = get_account("ttp")

    assert profile is ACCOUNTS["ttp"]
    assert profile.expected_login == login
    assert profile.terminal_path == _PATH


@pytest.mark.parametrize(
    ("account_name", "suffix"),
    [("mex", "0097"), ("ttp", "1681")],
)
def test_code_owned_login_suffix_accepts_its_profile(
    monkeypatch: pytest.MonkeyPatch,
    account_name: str,
    suffix: str,
) -> None:
    profile = ACCOUNTS[account_name]
    login = int("1234" + suffix)
    monkeypatch.setenv(profile.expected_login_env, str(login))
    monkeypatch.setenv(profile.terminal_path_env, _PATH)

    assert get_account(account_name).expected_login == login


def test_code_owned_login_suffix_rejects_a_consistent_other_profile_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mex_login = int("90" + "480" + "097")
    monkeypatch.setenv("MT5_TTP_LOGIN", str(mex_login))
    monkeypatch.setenv("MT5_TTP_TERMINAL_PATH", _PATH)

    with pytest.raises(SystemExit, match="missing or malformed"):
        get_account("ttp")


def test_get_account_rejects_unknown() -> None:
    with pytest.raises(SystemExit, match="unknown account"):
        get_account("nope")


def test_tracked_tree_has_no_account_login_literal_or_user_home_path() -> None:
    texts = _tracked_text()
    assert "live/accounts.py" in texts
    assert len(texts) >= 100
    login_hits = [path for path, text in texts.items() if _LOGIN_LITERAL.search(text)]
    home_hits = [path for path, text in texts.items() if _USER_HOME.search(text)]
    bare_documentation_hits = [
        (path, match.group())
        for path, text in texts.items()
        if path in _DOCUMENTATION_PATHS or path.startswith("docs/")
        for match in _BARE_LONG_NUMBER.finditer(text)
        if (path, match.group()) not in _DOCUMENTATION_NUMBER_ALLOWLIST
    ]

    assert login_hits == [], f"tracked account-login literals: {login_hits}"
    assert home_hits == [], f"tracked absolute user-home paths: {home_hits}"
    assert bare_documentation_hits == [], (
        f"unclassified long numbers in tracked documentation: {bare_documentation_hits}"
    )


@pytest.mark.parametrize(
    "line",
    [
        "MT5_TTP_LOGIN=" + "504" + "071681",
        "account_login: " + "123" + "456",
        "LOGIN = " + "987" + "654",
    ],
)
def test_login_literal_guard_matches_canonical_assignment_forms(line: str) -> None:
    assert _LOGIN_LITERAL.search(line)


def test_tracked_text_includes_tests_and_is_non_vacuous() -> None:
    texts = _tracked_text()

    assert "live/accounts.py" in texts
    assert "tests/test_live_accounts.py" in texts
    assert len(texts) >= 100


def test_tracked_text_resolves_the_git_root_from_a_nested_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(_tracked_text.__globals__, "REPO_ROOT", REPO_ROOT / ".ai")

    texts = _tracked_text()

    assert "live/accounts.py" in texts
    assert "tests/test_live_accounts.py" in texts
    assert len(texts) >= 100


def test_preflight_masks_connected_and_expected_login_values(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from live import preflight

    expected = int("1234" + "1681")
    connected = int("9876" + "4321")
    monkeypatch.setenv("MT5_TTP_LOGIN", str(expected))
    monkeypatch.setenv("MT5_TTP_TERMINAL_PATH", _PATH)

    class FakeBridge:
        def __init__(self, symbol_map: dict[str, str]) -> None:
            del symbol_map

        def connect(self, *, path: str | None = None) -> None:
            assert path == _PATH

        def account(self) -> AccountState:
            return _state(connected, "USD")

        def shutdown(self) -> None:
            pass

    monkeypatch.setattr(preflight, "Mt5Bridge", cast(type[Mt5Bridge], FakeBridge))
    monkeypatch.setattr(preflight, "markets_from_live_config", lambda: [])
    monkeypatch.setattr(preflight, "risk_per_trade_from_live_config", lambda: 0.0018)
    monkeypatch.setattr(
        preflight,
        "mt5",
        SimpleNamespace(terminal_info=lambda: SimpleNamespace(trade_allowed=True)),
    )

    preflight.main(["--account", "ttp"])

    output = capsys.readouterr().out
    assert str(connected) not in output
    assert str(expected) not in output
    assert f"***{connected % 1000:03d}" in output
    assert f"***{expected % 1000:03d}" in output


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
