"""Tests for the MT5 bridge without connecting to a terminal."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import live.mt5_bridge as bridge_module
import pytest
from live.mt5_bridge import Mt5Bridge, base_symbol, match_terminal_symbol


def test_base_symbol_maps_ustec_to_broker_name() -> None:
    assert base_symbol("USTEC") == "UT100"


def test_base_symbol_passthrough_for_matching_names() -> None:
    assert base_symbol("EURUSD") == "EURUSD"
    assert base_symbol("XAUUSD") == "XAUUSD"


def test_match_terminal_symbol_exact() -> None:
    assert match_terminal_symbol("EURUSD", ["EURUSD", "GBPUSD"]) == "EURUSD"


def test_match_terminal_symbol_suffix() -> None:
    # Broker adds a suffix -> pick the shortest symbol that starts with the base.
    assert match_terminal_symbol("EURUSD", ["EURUSD.r", "EURUSD.raw", "GBPUSD.r"]) == "EURUSD.r"


def test_match_terminal_symbol_rejects_contains_only() -> None:
    # M1: "merely contains the base" no longer resolves (could pick the wrong instrument).
    assert match_terminal_symbol("US30", ["mUS30", "US500"]) is None


def test_match_terminal_symbol_none_when_absent() -> None:
    assert match_terminal_symbol("UT100", ["EURUSD", "US30"]) is None


def test_history_deals_exports_ticket_and_fee(monkeypatch: pytest.MonkeyPatch) -> None:
    deal = SimpleNamespace(
        ticket=42,
        time=1_700_000_000,
        type=0,
        entry=0,
        position_id=7,
        symbol="EURUSD",
        volume=0.1,
        price=1.1,
        profit=12.34,
        swap=-0.5,
        commission=-1.25,
        fee=-2.75,
    )
    fake_mt5 = SimpleNamespace(history_deals_get=lambda _since, _until: [deal])
    monkeypatch.setattr(bridge_module, "mt5", fake_mt5)
    bridge = Mt5Bridge()
    bridge._connected = True

    result = bridge.history_deals(datetime(2026, 1, 1, tzinfo=UTC))

    assert result == [
        {
            "ticket": 42,
            "time": 1_700_000_000,
            "type": 0,
            "entry": 0,
            "position_id": 7,
            "symbol": "EURUSD",
            "volume": 0.1,
            "price": 1.1,
            "profit": Decimal("12.34"),
            "swap": Decimal("-0.5"),
            "commission": Decimal("-1.25"),
            "fee": Decimal("-2.75"),
        }
    ]


@pytest.mark.parametrize("raw", [None, []])
def test_history_deals_handles_no_records(
    monkeypatch: pytest.MonkeyPatch,
    raw: object,
) -> None:
    fake_mt5 = SimpleNamespace(history_deals_get=lambda _since, _until: raw)
    monkeypatch.setattr(bridge_module, "mt5", fake_mt5)
    bridge = Mt5Bridge()
    bridge._connected = True

    assert bridge.history_deals(datetime(2026, 1, 1, tzinfo=UTC)) == []
