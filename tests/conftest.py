"""Deterministic property settings and a fail-closed real-MT5 test boundary."""

import importlib
import importlib.util
import tempfile
from pathlib import Path
from types import ModuleType
from typing import NoReturn

import pytest
from hypothesis import settings
from hypothesis.configuration import set_hypothesis_home_dir

# Hypothesis caches scraped constants under `.hypothesis/` in the working directory. The example
# database is already off (see the profile below), so nothing here is load-bearing -- it is a cache
# that regenerates. Keeping it out of the repository root is purely so the checkout shows only
# things that belong to the project. Must run before Hypothesis first touches its storage.
set_hypothesis_home_dir(str(Path(tempfile.gettempdir()) / "qplus-hypothesis"))

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


def _mt5_available() -> bool:
    return importlib.util.find_spec("MetaTrader5") is not None


def _load_mt5_module() -> ModuleType | None:
    """Load the Windows-only bridge when available without breaking Linux test collection."""

    if not _mt5_available():
        return None
    return importlib.import_module("MetaTrader5")


@pytest.fixture(autouse=True)
def _block_real_mt5(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make an unmocked terminal/account call fail before it can reach MetaTrader 5."""

    mt5 = _load_mt5_module()
    if mt5 is None:
        return

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
