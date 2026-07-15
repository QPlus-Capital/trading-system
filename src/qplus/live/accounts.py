"""Live account profiles: which broker terminal each runner attaches to, and the identity guard.

Two accounts run in parallel, each with its OWN MT5 terminal and fully isolated state
(``reports/live/<name>/``):

- ``mex`` -- MEX Atlantic demo (EUR), the parity shadow, watched only in the MT5 terminal.
- ``ttp`` -- The Trading Pit CFD Prime $50k (USD), the real prop account; all code tooling
  (dashboard, reporting, fact sheet) points here.

Safety model: the runner CONNECTS to this profile's ``terminal_path`` and then REFUSES to trade
unless the *connected* account's login number and currency match the profile. So a runner can
never place orders on the wrong account, even if the wrong terminal happens to be open.

Instance layout: managed (prop) instances live under ``C:\\Users\\jancw\\MT5\\<name>\\`` -- each a
copy of a base install, independent because MT5 keys its data folder off the install path. A copy
is a FRESH terminal (login lives in %APPDATA%, not the install folder), so it must be logged into
its account ONCE before a runner can attach. The demo keeps its original install. To add another
account: copy an instance folder to ``MT5\\<new>\\``, log the account into it, enable Algo Trading,
then add a ``LiveAccount`` below with that terminal64.exe path + the login.
"""

from __future__ import annotations

from dataclasses import dataclass

from qplus.live.mt5_bridge import AccountState


@dataclass(frozen=True)
class LiveAccount:
    """One live account: its terminal, its isolated state dir, and the identity to guard on."""

    name: str  # short id -> reports/live/<name>/ (state, logs)
    expected_login: int | None  # broker account number; the runner asserts the connection matches
    expected_currency: str  # "EUR" | "USD" -- also asserted against the live connection
    start_balance: float  # daily/trailing reference on the FIRST run (saved state wins afterwards)
    terminal_path: str | None  # path to this account's terminal64.exe; None = the default terminal


MEX = LiveAccount(
    name="mex",
    expected_login=90480097,  # MEXAtlantic-Demo
    expected_currency="EUR",
    start_balance=100_000.0,
    # The demo keeps its ORIGINAL install (already logged in). A fresh copy under MT5\ would need a
    # one-time manual login -- not worth it for the shadow account. Prop instances go under MT5\.
    terminal_path=r"C:\Program Files\MetaTrader 5\terminal64.exe",
)

TTP = LiveAccount(
    name="ttp",
    expected_login=None,  # TODO: set to the TTP account number after login (guards real orders)
    expected_currency="USD",
    start_balance=50_000.0,  # CFD Prime $50k, 1-phase
    terminal_path=r"C:\Users\jancw\MT5\ttp\terminal64.exe",  # its instance under the MT5\ root
)

ACCOUNTS: dict[str, LiveAccount] = {a.name: a for a in (MEX, TTP)}


def get_account(name: str) -> LiveAccount:
    """Look up an account profile by name, or exit with a clear message."""
    if name not in ACCOUNTS:
        raise SystemExit(f"unknown account '{name}'; choose from {sorted(ACCOUNTS)}")
    return ACCOUNTS[name]


def guard_account(state: AccountState, profile: LiveAccount, *, execute: bool) -> None:
    """Refuse (SystemExit) unless the live connection is really the expected account.

    The single most important safeguard for running two accounts in parallel: it makes it
    impossible for, say, the TTP runner to place orders on the MEX terminal (or vice versa).
    """
    if profile.expected_login is not None and state.login != profile.expected_login:
        raise SystemExit(
            f"REFUSED: connected to account {state.login}, but profile '{profile.name}' expects "
            f"{profile.expected_login} -- wrong terminal open? Not trading."
        )
    if state.currency != profile.expected_currency:
        raise SystemExit(
            f"REFUSED: account currency {state.currency} != expected {profile.expected_currency} "
            f"for profile '{profile.name}' -- wrong account? Not trading."
        )
    if execute and profile.expected_login is None:
        raise SystemExit(
            f"REFUSED: profile '{profile.name}' has no expected_login set. Fill it in "
            "src/qplus/live/accounts.py before placing REAL orders (guard vs. the wrong account)."
        )
