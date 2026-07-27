"""Tests for the MT5 bridge without connecting to a terminal."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import cast

import live.mt5_bridge as bridge_module
import pytest
from live.mt5_bridge import (
    MAGIC,
    Mt5Bridge,
    Mt5Error,
    Position,
    Side,
    base_symbol,
    match_terminal_symbol,
)


class _FakeMt5:
    POSITION_TYPE_BUY = 0
    POSITION_TYPE_SELL = 1
    ORDER_TYPE_BUY = 10
    ORDER_TYPE_SELL = 11
    TRADE_ACTION_DEAL = 20
    ORDER_TIME_GTC = 30
    ORDER_FILLING_FOK = 40
    ORDER_FILLING_IOC = 41
    TRADE_RETCODE_DONE = 50

    def __init__(self, positions: list[SimpleNamespace] | None = None) -> None:
        self.raw_positions = positions or []
        self.order_calc_profit_calls: list[tuple[object, ...]] = []
        self.order_send_calls: list[dict[str, object]] = []
        self.tick_calls = 0
        self.symbol_info_calls = 0

    def positions_get(self, **_kwargs: object) -> list[SimpleNamespace]:
        return self.raw_positions

    def order_calc_profit(self, *args: object) -> float:
        self.order_calc_profit_calls.append(args)
        return -25.0

    def symbol_info_tick(self, _symbol: str) -> SimpleNamespace:
        self.tick_calls += 1
        return SimpleNamespace(ask=1.25, bid=1.2)

    def symbol_info(self, _symbol: str) -> SimpleNamespace:
        self.symbol_info_calls += 1
        return SimpleNamespace(filling_mode=2)

    def order_send(self, request: dict[str, object]) -> SimpleNamespace:
        self.order_send_calls.append(request)
        return SimpleNamespace(retcode=self.TRADE_RETCODE_DONE, order=123, comment="done")

    @staticmethod
    def last_error() -> tuple[int, str]:
        return 0, "synthetic"


def _bridge_with_fake(monkeypatch: pytest.MonkeyPatch, fake: _FakeMt5) -> Mt5Bridge:
    monkeypatch.setattr(bridge_module, "mt5", fake)
    bridge = Mt5Bridge({"EURUSD": "EURUSD"})
    bridge._connected = True
    bridge._resolved["EURUSD"] = "EURUSD"
    return bridge


def _raw_position(position_type: object) -> SimpleNamespace:
    return SimpleNamespace(
        ticket=7,
        symbol="EURUSD",
        type=position_type,
        volume=0.1,
        price_open=1.23,
        sl=1.1,
        tp=1.4,
        profit=5.0,
        magic=MAGIC,
    )


def _position(side: Side) -> Position:
    return Position(
        ticket=7,
        symbol="EURUSD",
        side=side,
        volume=0.1,
        price_open=1.23,
        sl=1.1,
        tp=1.4,
        profit=5.0,
        magic=MAGIC,
    )


def _assert_no_order_boundary_call(fake: _FakeMt5) -> None:
    assert fake.order_calc_profit_calls == []
    assert fake.order_send_calls == []
    assert fake.tick_calls == 0
    assert fake.symbol_info_calls == 0


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


@pytest.mark.parametrize("raw_type", [-1, 2, True])
def test_positions_fail_closed_on_unknown_position_type(
    monkeypatch: pytest.MonkeyPatch,
    raw_type: object,
) -> None:
    fake = _FakeMt5([_raw_position(raw_type)])
    bridge = _bridge_with_fake(monkeypatch, fake)

    with pytest.raises(Mt5Error, match="invalid MT5 position type"):
        bridge.positions()

    _assert_no_order_boundary_call(fake)


@pytest.mark.parametrize("invalid_side", ["", "buy", "HOLD", " BUY"])
def test_loss_for_order_fails_before_pricing_invalid_side(
    monkeypatch: pytest.MonkeyPatch,
    invalid_side: str,
) -> None:
    fake = _FakeMt5()
    bridge = _bridge_with_fake(monkeypatch, fake)

    with pytest.raises(Mt5Error, match="invalid order side"):
        bridge.loss_for_order("EURUSD", cast(Side, invalid_side), entry=1.2, sl=1.1, volume=0.1)

    _assert_no_order_boundary_call(fake)


def test_loss_to_stop_fails_before_pricing_invalid_position_side(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeMt5()
    bridge = _bridge_with_fake(monkeypatch, fake)

    with pytest.raises(Mt5Error, match="invalid order side"):
        bridge.loss_to_stop(_position(cast(Side, "HOLD")))

    _assert_no_order_boundary_call(fake)


def test_place_order_fails_before_terminal_calls_for_invalid_side(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeMt5()
    bridge = _bridge_with_fake(monkeypatch, fake)

    with pytest.raises(Mt5Error, match="invalid order side"):
        bridge.place_order("EURUSD", cast(Side, "HOLD"), 0.1)

    _assert_no_order_boundary_call(fake)


def test_close_position_fails_before_terminal_calls_for_invalid_side(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeMt5()
    bridge = _bridge_with_fake(monkeypatch, fake)

    with pytest.raises(Mt5Error, match="invalid order side"):
        bridge.close_position(_position(cast(Side, "HOLD")))

    _assert_no_order_boundary_call(fake)


@pytest.mark.parametrize(
    ("raw_type", "expected"),
    [
        (_FakeMt5.POSITION_TYPE_BUY, "BUY"),
        (_FakeMt5.POSITION_TYPE_SELL, "SELL"),
    ],
)
def test_legal_position_types_preserve_position_sides(
    monkeypatch: pytest.MonkeyPatch,
    raw_type: int,
    expected: Side,
) -> None:
    fake = _FakeMt5([_raw_position(raw_type)])
    bridge = _bridge_with_fake(monkeypatch, fake)

    positions = bridge.positions()

    assert len(positions) == 1
    assert positions[0].side == expected
    _assert_no_order_boundary_call(fake)


@pytest.mark.parametrize(
    ("side", "order_type", "price"),
    [
        ("BUY", _FakeMt5.ORDER_TYPE_BUY, 1.25),
        ("SELL", _FakeMt5.ORDER_TYPE_SELL, 1.2),
    ],
)
def test_legal_order_sides_preserve_pricing_and_entry_requests(
    monkeypatch: pytest.MonkeyPatch,
    side: Side,
    order_type: int,
    price: float,
) -> None:
    fake = _FakeMt5()
    bridge = _bridge_with_fake(monkeypatch, fake)

    loss = bridge.loss_for_order("EURUSD", side, entry=1.2, sl=1.1, volume=0.1)
    stop_loss = bridge.loss_to_stop(_position(side))
    ticket = bridge.place_order(
        "EURUSD", side, 0.1, sl=1.1, tp=1.4, deviation=15, comment="synthetic"
    )

    assert loss == 25.0
    assert stop_loss == 25.0
    assert fake.order_calc_profit_calls == [
        (order_type, "EURUSD", 0.1, 1.2, 1.1),
        (order_type, "EURUSD", 0.1, 1.23, 1.1),
    ]
    assert ticket == 123
    assert fake.order_send_calls == [
        {
            "action": fake.TRADE_ACTION_DEAL,
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": order_type,
            "price": price,
            "sl": 1.1,
            "tp": 1.4,
            "deviation": 15,
            "magic": MAGIC,
            "comment": "synthetic",
            "type_time": fake.ORDER_TIME_GTC,
            "type_filling": fake.ORDER_FILLING_IOC,
        }
    ]


@pytest.mark.parametrize(
    ("side", "order_type", "price"),
    [
        ("BUY", _FakeMt5.ORDER_TYPE_SELL, 1.2),
        ("SELL", _FakeMt5.ORDER_TYPE_BUY, 1.25),
    ],
)
def test_legal_position_sides_preserve_close_requests(
    monkeypatch: pytest.MonkeyPatch,
    side: Side,
    order_type: int,
    price: float,
) -> None:
    fake = _FakeMt5()
    bridge = _bridge_with_fake(monkeypatch, fake)

    bridge.close_position(_position(side), deviation=15)

    assert fake.order_send_calls == [
        {
            "action": fake.TRADE_ACTION_DEAL,
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": order_type,
            "position": 7,
            "price": price,
            "deviation": 15,
            "magic": MAGIC,
            "comment": "qplus-close",
            "type_time": fake.ORDER_TIME_GTC,
            "type_filling": fake.ORDER_FILLING_IOC,
        }
    ]


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
