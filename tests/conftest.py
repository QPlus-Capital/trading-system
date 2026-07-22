"""Deterministic property settings and a fail-closed real-MT5 test boundary."""

from typing import NoReturn

import MetaTrader5 as mt5
import pytest
from hypothesis import settings

_MT5_BOUNDARIES = (
    "initialize",
    "login",
    "shutdown",
    "account_info",
    "terminal_info",
    "symbols_get",
    "symbol_info",
    "symbol_info_tick",
    "copy_rates_from",
    "copy_rates_from_pos",
    "copy_rates_range",
    "copy_ticks_from",
    "copy_ticks_range",
    "positions_get",
    "orders_get",
    "history_orders_get",
    "history_deals_get",
    "order_check",
    "order_send",
)


@pytest.fixture(autouse=True)
def _block_real_mt5(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make an unmocked terminal/account call fail before it can reach MetaTrader 5."""

    class BlockedMT5Boundary:
        __qplus_test_block__ = True

        def __call__(self, *_args: object, **_kwargs: object) -> NoReturn:
            raise AssertionError("tests must replace MT5 boundaries with explicit fakes")

    blocked = BlockedMT5Boundary()
    for name in _MT5_BOUNDARIES:
        monkeypatch.setattr(mt5, name, blocked)

settings.register_profile(
    "qplus",
    derandomize=True,
    database=None,
    deadline=None,
    max_examples=75,
    print_blob=True,
)
settings.load_profile("qplus")
