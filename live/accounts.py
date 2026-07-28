"""Environment-backed live account profiles and the identity guard.

Two accounts run in parallel, each with its OWN MT5 terminal and fully isolated state
(``reports/live/<name>/``):

- ``mex`` -- MEX Atlantic demo (EUR), the parity shadow, watched only in the MT5 terminal.
- ``ttp`` -- The Trading Pit CFD Prime $50k (USD), the real prop account; all code tooling
  (dashboard, reporting, fact sheet) points here.

Safety model: ``get_account`` first requires the selected profile's login and terminal path from
the process environment. The runner then connects to that path and refuses unless the connected
account's login and currency match. Missing, malformed, or mismatching identity always fails closed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import NoReturn, Protocol

from live.mt5_bridge import AccountState


@dataclass(frozen=True)
class LiveAccount:
    """One account's code-owned metadata and required environment-backed connection identity."""

    name: str  # short id -> reports/live/<name>/ (state, logs)
    expected_login_env: str
    expected_login_suffix: str  # code-owned non-secret witness against profile-block copy/paste
    expected_currency: str  # "EUR" | "USD" -- also asserted against the live connection
    start_balance: float  # daily/trailing reference on the FIRST run (saved state wins afterwards)
    terminal_path_env: str
    # per-account overrides on the base SYMBOL_MAP, for brokers that name a symbol differently
    symbol_overrides: dict[str, str] = field(default_factory=dict)

    @property
    def expected_login(self) -> int:
        """Return the required broker login, refusing absent or malformed configuration."""
        raw = _required_environment(self.expected_login_env, kind="broker login")
        if not raw.isascii() or not raw.isdigit() or int(raw) <= 0:
            _refuse_environment(self.expected_login_env, kind="broker login")
        login = int(raw)
        if f"{login:04d}"[-4:] != self.expected_login_suffix:
            _refuse_environment(self.expected_login_env, kind="broker login")
        return login

    @property
    def terminal_path(self) -> str:
        """Return the required terminal path, refusing absent, padded, or placeholder values."""
        raw = _required_environment(self.terminal_path_env, kind="terminal path")
        if raw != raw.strip() or (raw.startswith("<") and raw.endswith(">")):
            _refuse_environment(self.terminal_path_env, kind="terminal path")
        return raw

    def validate_environment(self) -> None:
        """Resolve every required identity value before a terminal connection is attempted."""
        _ = self.expected_login
        _ = self.terminal_path


def _required_environment(name: str, *, kind: str) -> str:
    """Read one non-empty environment value without disclosing it on refusal."""
    value = os.environ.get(name)
    if value is None or not value:
        _refuse_environment(name, kind=kind)
    return value


def _refuse_environment(name: str, *, kind: str) -> NoReturn:
    """Refuse an unavailable safety input without putting its value in output."""
    raise SystemExit(
        f"REFUSED: required {kind} environment variable '{name}' is missing or malformed. "
        "Not trading."
    )


MEX = LiveAccount(
    name="mex",
    expected_login_env="MT5_MEX_LOGIN",
    expected_login_suffix="0097",
    expected_currency="EUR",
    start_balance=100_000.0,
    terminal_path_env="MT5_MEX_TERMINAL_PATH",
)

TTP = LiveAccount(
    name="ttp",
    expected_login_env="MT5_TTP_LOGIN",
    expected_login_suffix="1681",
    expected_currency="USD",
    start_balance=50_000.0,  # CFD Prime $50k, 1-phase
    terminal_path_env="MT5_TTP_TERMINAL_PATH",
    symbol_overrides={"USTEC": "USTEC"},  # TTP names the Nasdaq USTEC (MEX calls it UT100)
)

ACCOUNTS: dict[str, LiveAccount] = {a.name: a for a in (MEX, TTP)}


class AccountReader(Protocol):
    """Minimal connected-bridge surface needed by the shared identity guard."""

    def account(self) -> AccountState:
        """Return the terminal's current account identity and balances."""


def get_account(name: str) -> LiveAccount:
    """Return a fully configured profile, or refuse before any terminal connection."""
    if name not in ACCOUNTS:
        raise SystemExit(f"unknown account '{name}'; choose from {sorted(ACCOUNTS)}")
    profile = ACCOUNTS[name]
    profile.validate_environment()
    return profile


def guard_account(state: AccountState, profile: LiveAccount, *, execute: bool) -> None:
    """Refuse unless the live connection is the required account in every run mode.

    The single most important safeguard for running two accounts in parallel: it makes it
    impossible for, say, the TTP runner to place orders on the MEX terminal (or vice versa).
    """
    _ = execute  # Public compatibility; identity is mandatory in both execution modes.
    expected_login = profile.expected_login
    if state.login != expected_login:
        raise SystemExit(
            f"REFUSED: connected account does not match profile '{profile.name}' -- "
            "wrong terminal open? Not trading."
        )
    if state.currency != profile.expected_currency:
        raise SystemExit(
            f"REFUSED: account currency {state.currency} != expected {profile.expected_currency} "
            f"for profile '{profile.name}' -- wrong account? Not trading."
        )


def guard_connected_account(bridge: AccountReader, profile: LiveAccount) -> AccountState:
    """Read and verify one connected terminal before any account-specific data is consumed."""
    state = bridge.account()
    guard_account(state, profile, execute=False)
    return state
