"""The dashboard must consume one coherent broker snapshot without touching a terminal."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from live.mt5_bridge import AccountState
from monitoring import dashboard

_TTP_TEST_LOGIN = int("1234" + "1681")


@pytest.fixture(autouse=True)
def _configured_fake_account(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MT5_TTP_LOGIN", str(_TTP_TEST_LOGIN))
    monkeypatch.setenv("MT5_TTP_TERMINAL_PATH", r"C:\MT5\fake\terminal64.exe")


def _deal(ticket: int, profit: str) -> dict[str, Any]:
    return {
        "ticket": ticket,
        "time": 1_700_000_000 + ticket,
        "type": 1,
        "entry": 1,
        "position_id": ticket,
        "symbol": "EURUSD",
        "volume": 0.1,
        "price": 1.1,
        "profit": Decimal(profit),
        "swap": Decimal("0"),
        "commission": Decimal("0"),
        "fee": Decimal("0"),
    }


class _SnapshotBridge:
    histories: list[list[dict[str, Any]]] = []
    accounts: list[AccountState] = []
    position_snapshot_result: SimpleNamespace = SimpleNamespace(positions=(), issues=())
    instances: list[_SnapshotBridge] = []
    history_calls = 0

    def __init__(self, symbol_map: dict[str, str]) -> None:
        self._resolved = {"EURUSD": "EURUSD"}
        self._histories: Iterator[list[dict[str, Any]]] = iter(self.histories)
        self._accounts: Iterator[AccountState] = iter(self.accounts)
        self.shutdown_called = False
        self.instances.append(self)

    def connect(self, *, path: str | None = None) -> None:
        del path

    def history_deals(self, _since: object) -> list[dict[str, Any]]:
        type(self).history_calls += 1
        return next(self._histories)

    def account(self) -> AccountState:
        return next(self._accounts)

    def positions(self) -> list[object]:
        return []

    def position_snapshot(self) -> SimpleNamespace:
        return self.position_snapshot_result

    def shutdown(self) -> None:
        self.shutdown_called = True


@pytest.fixture(autouse=True)
def _reset_position_snapshot() -> Iterator[None]:
    _SnapshotBridge.position_snapshot_result = SimpleNamespace(positions=(), issues=())
    yield


def _account(balance: float, *, login: int = _TTP_TEST_LOGIN) -> AccountState:
    return AccountState(balance=balance, equity=balance, currency="USD", login=login)


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("ticket", 2),
        ("time", 1_800_000_000),
        ("type", 0),
        ("entry", 0),
        ("position_id", 99),
        ("symbol", "GBPUSD"),
        ("volume", 0.2),
        ("price", 1.2),
        ("profit", Decimal("2")),
        ("swap", Decimal("-1")),
        ("commission", Decimal("-2")),
        ("fee", Decimal("-3")),
    ],
)
def test_snapshot_identity_detects_any_deal_change(field: str, changed: object) -> None:
    before = _deal(1, "1")
    after = {**before, field: changed}

    assert dashboard._snapshot_identity([before]) != dashboard._snapshot_identity([after])


def test_load_live_retries_an_interleaved_deal_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old = [_deal(1, "10")]
    updated = [*old, _deal(2, "5")]
    _SnapshotBridge.histories = [old, updated, updated, updated]
    _SnapshotBridge.accounts = [
        _account(115.0),
        _account(110.0),
        _account(115.0),
        _account(115.0),
        _account(115.0),
    ]
    _SnapshotBridge.instances = []
    monkeypatch.setattr(dashboard, "Mt5Bridge", _SnapshotBridge)
    dashboard._load_live.clear()

    live = dashboard._load_live("ttp")

    assert [deal["ticket"] for deal in live["deals"]] == [1, 2]
    assert live["balance"] == 115.0
    assert len(_SnapshotBridge.instances) == 1
    assert _SnapshotBridge.instances[0].shutdown_called


def test_load_live_surfaces_an_undecodable_position_as_unpriceable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = [_deal(1, "1")]
    _SnapshotBridge.histories = [history, history]
    _SnapshotBridge.accounts = [_account(101.0), _account(101.0), _account(101.0)]
    _SnapshotBridge.position_snapshot_result = SimpleNamespace(
        positions=(),
        issues=(
            SimpleNamespace(
                ticket=20,
                symbol="GBPJPY",
                magic=999,
                reason="unsupported synthetic position type",
            ),
        ),
    )
    _SnapshotBridge.instances = []
    monkeypatch.setattr(dashboard, "Mt5Bridge", _SnapshotBridge)
    dashboard._load_live.clear()

    live = dashboard._load_live("ttp")

    assert live["open_risk"].total == 0.0
    assert live["open_risk"].unpriceable == ["GBPJPY"]


def test_load_live_fails_closed_when_history_never_stabilises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _SnapshotBridge.histories = [
        [_deal(1, "1")],
        [_deal(2, "2")],
        [_deal(3, "3")],
        [_deal(4, "4")],
        [_deal(5, "5")],
        [_deal(6, "6")],
    ]
    _SnapshotBridge.accounts = [
        _account(101.0),
        _account(101.0),
        _account(102.0),
        _account(103.0),
        _account(104.0),
        _account(105.0),
        _account(106.0),
    ]
    _SnapshotBridge.instances = []
    monkeypatch.setattr(dashboard, "Mt5Bridge", _SnapshotBridge)
    dashboard._load_live.clear()

    with pytest.raises(RuntimeError, match="stable MT5 deal/account snapshot"):
        dashboard._load_live("ttp")

    assert len(_SnapshotBridge.instances) == 1
    assert _SnapshotBridge.instances[0].shutdown_called


def test_load_live_retries_when_balance_changes_with_the_same_newest_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = [_deal(1, "1")]
    _SnapshotBridge.histories = [history, history, history, history]
    _SnapshotBridge.accounts = [
        _account(101.0),
        _account(100.0),
        _account(101.0),
        _account(101.0),
        _account(101.0),
    ]
    _SnapshotBridge.instances = []
    monkeypatch.setattr(dashboard, "Mt5Bridge", _SnapshotBridge)
    dashboard._load_live.clear()

    live = dashboard._load_live("ttp")

    assert live["balance"] == 101.0


def test_load_live_refuses_the_wrong_terminal_before_reading_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = int("1234" + "1681")
    wrong = int("9876" + "5432")
    monkeypatch.setenv("MT5_TTP_LOGIN", str(expected))
    _SnapshotBridge.histories = [[_deal(1, "1")], [_deal(1, "1")]]
    _SnapshotBridge.accounts = [
        _account(50_000.0, login=wrong),
        _account(50_000.0, login=wrong),
        _account(50_000.0, login=wrong),
    ]
    _SnapshotBridge.instances = []
    _SnapshotBridge.history_calls = 0
    monkeypatch.setattr(dashboard, "Mt5Bridge", _SnapshotBridge)
    dashboard._load_live.clear()

    with pytest.raises(SystemExit, match="does not match profile"):
        dashboard._load_live("ttp")

    assert _SnapshotBridge.history_calls == 0
