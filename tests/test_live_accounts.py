"""Tests for the live account identity guard -- the safeguard against the wrong account."""

from __future__ import annotations

import inspect
import json
import os
import re
import shutil
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
_LOGIN_LITERAL = re.compile(
    r"""(?ix)
    (?<![A-Z0-9_])
    (?P<key_quote>["']?)
    [A-Z0-9_]*LOGIN
    (?P=key_quote)
    \s*
    (?:
        :\s*[A-Z_][A-Z0-9_.\[\], |]*\s*=
        |
        [=:]
    )
    \s*
    (?P<value_quote>["']?)
    [1-9][0-9]{5,9}
    (?P=value_quote)
    (?![0-9])
    """
)
_LOGIN_SUFFIXES = "|".join(
    re.escape(suffix)
    for suffix in sorted({profile.expected_login_suffix for profile in ACCOUNTS.values()})
)
_LOGIN_SUFFIX_LITERAL = re.compile(rf"(?<![0-9])[1-9][0-9]{{1,5}}(?:{_LOGIN_SUFFIXES})(?![0-9])")
_DIGIT_SEPARATOR = re.compile(r"(?<=[0-9])_(?=[0-9])")
_BARE_LONG_NUMBER = re.compile(r"(?<![0-9])[1-9][0-9]{5,9}(?![0-9])")
_INDEPENDENT_REINTRODUCTION_TEMPLATES = [
    "logins = [{value}, {other}]",
    "LOGIN_TTP = {value}",
    "TTP_ACCOUNT = {value}",
    'accounts = {{"ttp": {value}}}',
    'EXPECTED_LOGIN = int("{value}")',
    "assert state.login == {value}",
    "return {value}  # ttp login",
    "login=(\n    {value}\n)",
]
_UNDERSCORE_REINTRODUCTION_TEMPLATES = [
    "MT5_TTP_LOGIN={value}",
    "login = {value}",
    "x = {other}",
]
_DOCUMENTATION_PATHS = {".env.example", "README.md", "RUN.md"}
_DOCUMENTATION_NUMBER_ALLOWLIST = {
    ("docs/architecture.md", "770077"),  # public MT5 magic number
    ("workflow/workflow.md", "20260721"),  # deterministic property-test seed
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


def _login_literal_hits(texts: dict[str, str]) -> list[str]:
    """Return tracked paths containing a login assignment or known account login."""
    return [path for path, text in texts.items() if _contains_login_literal(text)]


def _contains_login_literal(text: str) -> bool:
    normalized = _DIGIT_SEPARATOR.sub("", text)
    return bool(_LOGIN_LITERAL.search(normalized) or _LOGIN_SUFFIX_LITERAL.search(normalized))


def test_guard_refuses_when_the_login_environment_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(_LOGIN_ENV, raising=False)
    monkeypatch.setenv(_PATH_ENV, _PATH)

    with pytest.raises(SystemExit) as exc_info:
        guard_account(_state(_LOGIN, "USD"), _PROFILE)

    assert str(exc_info.value) == (
        "REFUSED: required broker login environment variable 'TEST_MT5_LOGIN' is missing or "
        "malformed. Not trading."
    )


def test_guard_passes_on_the_expected_environment_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch)

    guard_account(_state(_LOGIN, "USD"), _PROFILE)


def test_guard_refuses_wrong_environment_login_without_disclosing_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch)
    connected_login = int("654" + "321")

    with pytest.raises(SystemExit) as exc_info:
        guard_account(_state(connected_login, "USD"), _PROFILE)

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
        guard_account(_state(_LOGIN, "EUR"), _PROFILE)

    assert str(exc_info.value) == (
        "REFUSED: account currency EUR != expected USD for profile 'test' -- wrong account? "
        "Not trading."
    )


def test_guard_refuses_signal_only_without_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_LOGIN_ENV, raising=False)
    monkeypatch.setenv(_PATH_ENV, _PATH)

    with pytest.raises(SystemExit, match=_LOGIN_ENV):
        guard_account(_state(_LOGIN, "USD"), _PROFILE)


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
        guard_account(_state(_LOGIN, "USD"), _PROFILE)

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
    login_hits = _login_literal_hits(texts)
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
    "template",
    [
        "MT5_TTP_LOGIN={value}",
        "MT5_TTP_LOGIN = {value}",
        'MT5_TTP_LOGIN="{value}"',
        "MT5_TTP_LOGIN='{value}'",
        "MT5_TTP_LOGIN: {value}",
        'MT5_TTP_LOGIN: "{value}"',
        '"MT5_TTP_LOGIN": {value}',
        '"MT5_TTP_LOGIN": "{value}"',
        "'MT5_TTP_LOGIN': '{value}'",
        "MT5_TTP_LOGIN: int = {value}",
        "EXPECTED_LOGIN: int = {value}",
        "expected_login={value}",
        "account_login: {value}",
        "BROKER_LOGIN = {value}",
        "LOGIN = {value}",
        "# MT5_TTP_LOGIN={value}",
        '"""MT5_TTP_LOGIN={value}"""',
        '{{"MT5_TTP_LOGIN": {value}}}',
        "{{MT5_TTP_LOGIN: {value}}}",
        "export MT5_TTP_LOGIN={value}",
        "set MT5_TTP_LOGIN={value}",
        '$env:MT5_TTP_LOGIN="{value}"',
        *_INDEPENDENT_REINTRODUCTION_TEMPLATES,
    ],
)
def test_login_literal_guard_matches_plausible_reintroduction_forms(template: str) -> None:
    line = template.format(value="504" + "071681", other="904" + "80097")
    assert _contains_login_literal(line)


def test_ai_task_login_suffix_is_detected_without_a_bare_number_scan() -> None:
    path = "docs/fixture/evidence.md"
    texts = {path: "captured account login " + "999" + "001681"}

    assert _login_literal_hits(texts) == [path]


@pytest.mark.parametrize("template", _INDEPENDENT_REINTRODUCTION_TEMPLATES)
def test_a_login_in_tracked_code_is_caught_however_it_is_written(template: str) -> None:
    """The guard must protect code paths, not only the key=value shape it was built around."""
    line = template.format(value="504" + "071681", other="904" + "80097")

    assert _contains_login_literal(line)


@pytest.mark.parametrize("template", _UNDERSCORE_REINTRODUCTION_TEMPLATES)
def test_an_underscore_separated_login_literal_is_caught(template: str) -> None:
    """An underscore-separated Python integer literal must not evade both patterns."""
    line = template.format(value="504_" + "071_" + "681", other="90_" + "480_" + "097")

    assert _contains_login_literal(line)


def test_widening_the_suffix_rule_to_the_whole_tree_is_free() -> None:
    """The stronger suffix rule must produce no false positives in the tracked tree."""
    texts = _tracked_text()
    assert len(texts) >= 100
    hits = [
        (path, match.group())
        for path, text in texts.items()
        for match in _LOGIN_SUFFIX_LITERAL.finditer(text)
    ]

    assert hits == [], f"tree-wide suffix hits: {hits}"


def test_the_suffix_rule_covers_every_configured_account() -> None:
    """A third account must not silently lose suffix protection."""
    for profile in ACCOUNTS.values():
        assert profile.expected_login_suffix in _LOGIN_SUFFIX_LITERAL.pattern, (
            f"account {profile.name!r} suffix {profile.expected_login_suffix!r} is not in the "
            "derived pattern"
        )


def test_normalising_digit_underscores_closes_the_last_gap() -> None:
    """Digit-underscore normalisation must close the gap without tree-wide false positives."""
    for template in _UNDERSCORE_REINTRODUCTION_TEMPLATES:
        line = template.format(value="504_" + "071_" + "681", other="90_" + "480_" + "097")
        assert _LOGIN_SUFFIX_LITERAL.search(_DIGIT_SEPARATOR.sub("", line)), line
    texts = _tracked_text()
    hits = [
        (path, match.group())
        for path, text in texts.items()
        for match in _LOGIN_SUFFIX_LITERAL.finditer(_DIGIT_SEPARATOR.sub("", text))
    ]

    assert hits == [], f"tree-wide hits after normalisation: {hits}"


def test_tracked_text_includes_tests_and_is_non_vacuous() -> None:
    texts = _tracked_text()

    assert "live/accounts.py" in texts
    assert "tests/test_live_accounts.py" in texts
    assert len(texts) >= 100


def test_tracked_text_resolves_the_git_root_from_a_nested_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(_tracked_text.__globals__, "REPO_ROOT", REPO_ROOT / "workflow")

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
        placeholder = values[key].strip("'")
        assert placeholder.startswith("<") and placeholder.endswith(">")
        if key.endswith("_LOGIN"):
            assert not any(char.isdigit() for char in placeholder)
        assert _USER_HOME.search(placeholder) is None


def test_documented_env_layout_round_trips_windows_paths_and_telegram_through_uv(
    tmp_path: Path,
) -> None:
    example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    mex_login = "1234" + "0097"
    ttp_login = "1234" + "1681"
    mex_path = "C:" + r"\Users\Fixture Operator\MT5\MEX\terminal64.exe"
    ttp_path = "C:" + r"\Users\Fixture Operator\MT5\TTP\terminal64.exe"
    token = "12345:" + "fixture-token"
    expected = {
        "MT5_MEX_LOGIN": mex_login,
        "MT5_MEX_TERMINAL_PATH": mex_path,
        "MT5_TTP_LOGIN": ttp_login,
        "MT5_TTP_TERMINAL_PATH": ttp_path,
        "TELEGRAM_BOT_TOKEN": token,
        "TELEGRAM_CHAT_ID": "98765",
    }
    rendered = example
    rendered = rendered.replace("<broker-account-login>", mex_login, 1)
    rendered = rendered.replace("<absolute-path-to-terminal64.exe>", mex_path, 1)
    rendered = rendered.replace("<broker-account-login>", ttp_login, 1)
    rendered = rendered.replace("<absolute-path-to-terminal64.exe>", ttp_path, 1)
    rendered = rendered.replace("TELEGRAM_BOT_TOKEN=", f"TELEGRAM_BOT_TOKEN='{token}'")
    rendered = rendered.replace("TELEGRAM_CHAT_ID=", "TELEGRAM_CHAT_ID='98765'")
    env_file = tmp_path / ".env"
    env_file.write_text(rendered, encoding="utf-8")
    command = (
        "import json, os; "
        f"print(json.dumps({{key: os.environ.get(key) for key in {tuple(expected)!r}}}))"
    )
    clean_environment = {
        key: value
        for key, value in os.environ.items()
        if key not in expected and not key.startswith("UV_")
    }

    completed = subprocess.run(
        [
            shutil.which("uv") or "uv",
            "run",
            "--no-project",
            "--env-file",
            env_file.as_posix(),
            "python",
            "-c",
            command,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=clean_environment,
    )

    assert completed.returncode == 0
    assert "warning:" not in completed.stderr.lower()
    assert json.loads(completed.stdout) == expected


def test_operator_docs_state_windows_env_quoting_and_export_precedence() -> None:
    for path in (REPO_ROOT / "RUN.md", REPO_ROOT / "docs" / "live-runbook.md"):
        text = path.read_text(encoding="utf-8")
        assert "single quotes" in text
        assert "already-exported" in text
        assert "takes precedence" in text


def test_login_must_be_longer_than_its_code_owned_suffix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MT5_MEX_LOGIN", "97")
    monkeypatch.setenv("MT5_MEX_TERMINAL_PATH", _PATH)

    with pytest.raises(SystemExit, match="missing or malformed"):
        get_account("mex")


def test_guard_account_has_no_mode_parameter() -> None:
    assert tuple(inspect.signature(guard_account).parameters) == ("state", "profile")


def test_guard_account_accept_refuse_matrix_matches_the_mode_independent_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    currencies = ("EUR", "USD", "GBP", "")
    comparisons = 0
    divergences: list[tuple[str, int, str, bool, bool]] = []

    for profile in ACCOUNTS.values():
        expected_login = int("1234" + profile.expected_login_suffix)
        monkeypatch.setenv(profile.expected_login_env, str(expected_login))
        monkeypatch.setenv(profile.terminal_path_env, _PATH)
        candidate_logins = (
            expected_login,
            expected_login - 4,
            expected_login - 3,
            expected_login - 2,
            expected_login - 1,
            expected_login + 1,
            expected_login + 2,
            expected_login + 3,
            expected_login + 4,
            expected_login + 5,
        )
        for login in candidate_logins:
            for currency in currencies:
                expected = login == expected_login and currency == profile.expected_currency
                try:
                    guard_account(_state(login, currency), profile)
                except SystemExit:
                    observed = False
                else:
                    observed = True
                comparisons += 1
                if observed != expected:
                    divergences.append((profile.name, login, currency, expected, observed))

    assert comparisons == 80
    assert divergences == []


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
