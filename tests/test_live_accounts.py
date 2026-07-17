"""Tests for the live account identity guard -- the safeguard against trading the wrong account."""

import pytest
from live.accounts import LiveAccount, get_account, guard_account
from live.mt5_bridge import AccountState

_TTP = LiveAccount(
    name="ttp", expected_login=123456, expected_currency="USD", start_balance=50_000.0,
    terminal_path=None,
)
_UNSET = LiveAccount(
    name="new", expected_login=None, expected_currency="USD", start_balance=50_000.0,
    terminal_path=None,
)


def _state(login: int, currency: str) -> AccountState:
    return AccountState(balance=50_000.0, equity=50_000.0, currency=currency, login=login)


def test_guard_passes_on_the_expected_account() -> None:
    guard_account(_state(123456, "USD"), _TTP, execute=True)  # no raise


def test_guard_refuses_wrong_login() -> None:
    with pytest.raises(SystemExit, match="expects 123456"):
        guard_account(_state(999999, "USD"), _TTP, execute=True)


def test_guard_refuses_wrong_currency() -> None:
    with pytest.raises(SystemExit, match="currency"):
        guard_account(_state(123456, "EUR"), _TTP, execute=True)


def test_guard_refuses_execute_without_configured_login() -> None:
    # A profile whose login is not filled in must never place REAL orders (could be any account).
    with pytest.raises(SystemExit, match="no expected_login"):
        guard_account(_state(123456, "USD"), _UNSET, execute=True)


def test_guard_allows_signal_only_without_login() -> None:
    guard_account(_state(123456, "USD"), _UNSET, execute=False)  # dry-run is fine


def test_get_account_rejects_unknown() -> None:
    with pytest.raises(SystemExit):
        get_account("nope")
