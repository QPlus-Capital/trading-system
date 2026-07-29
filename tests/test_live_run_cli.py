"""CLI wiring of live.run: the two balance references must never share one flag.

Codex round-5 P1: ``--start-balance`` (the loss day's opening balance) also initialised the
RiskController's ``start_balance`` -- the ACCOUNT/trailing reference. Passing the true day-start
of 49k on a 50k profile then lowered the trailing floor from 47,500 to 46,550, loosening the very
limit the flag exists to protect.
"""

from pathlib import Path
from typing import Any

import live.run as runmod
import pytest
from live.accounts import ACCOUNTS
from live.mt5_bridge import AccountState


class _SpyRunner:
    """Captures what live.run.main wires together; never trades."""

    captured: dict[str, Any] = {}

    def __init__(self, bridge: Any, markets: Any, params: Any, risk: Any, **kw: Any) -> None:
        _SpyRunner.captured = {"risk": risk, **kw}

    def run_once(self) -> None:
        pass


class _StubBridge:
    def __init__(self, **kw: Any) -> None:
        pass

    def connect(self, path: str | None = None) -> None:
        pass

    def account(self) -> AccountState:
        return AccountState(balance=49_000.0, equity=49_000.0, currency="USD", login=1)

    def shutdown(self) -> None:
        pass


def test_start_balance_feeds_the_day_start_not_the_trailing_reference(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MT5_TTP_LOGIN", str(int("1234" + "1681")))
    monkeypatch.setenv("MT5_TTP_TERMINAL_PATH", r"C:\MT5\test\terminal64.exe")
    monkeypatch.setattr(runmod, "Mt5Bridge", _StubBridge)
    monkeypatch.setattr(runmod, "LiveRunner", _SpyRunner)
    monkeypatch.setattr(runmod, "guard_account", lambda *a, **k: None)
    monkeypatch.setattr(runmod, "_LIVE_ROOT", tmp_path)

    runmod.main(["--account", "ttp", "--once", "--start-balance", "49000"])

    cap = _SpyRunner.captured
    # The trailing/account reference comes from the PROFILE, whatever the operator typed:
    assert cap["risk"].start_balance == ACCOUNTS["ttp"].start_balance
    # ...and the CLI value reaches the runner only as the loss day's opening balance.
    assert cap["day_start_balance"] == 49_000.0


def test_missing_account_environment_refuses_before_bridge_connection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class _ConnectionSpy(_StubBridge):
        connected = False

        def connect(self, path: str | None = None) -> None:
            _ConnectionSpy.connected = True

    monkeypatch.delenv("MT5_TTP_LOGIN", raising=False)
    monkeypatch.setenv("MT5_TTP_TERMINAL_PATH", r"C:\MT5\test\terminal64.exe")
    monkeypatch.setattr(runmod, "Mt5Bridge", _ConnectionSpy)
    monkeypatch.setattr(runmod, "_LIVE_ROOT", tmp_path)

    with pytest.raises(SystemExit, match="MT5_TTP_LOGIN"):
        runmod.main(["--account", "ttp", "--once", "--start-balance", "49000"])

    assert _ConnectionSpy.connected is False
