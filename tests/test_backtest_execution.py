"""Tests for trade-PnL extraction, incl. the zero-trade window that must not crash a task."""

from typing import Any

import pandas as pd
import pytest
from research.engine import execution


class _FakeTrader:
    def __init__(self, report: pd.DataFrame) -> None:
        self._report = report

    def generate_positions_report(self) -> pd.DataFrame:
        return self._report


class _FakeEngine:
    def __init__(self, report: pd.DataFrame) -> None:
        self.trader = _FakeTrader(report)


class _FakeNode:
    """Stands in for BacktestNode: yields a canned positions report, records disposal."""

    report: pd.DataFrame = pd.DataFrame()

    def __init__(self, configs: Any) -> None:
        self.disposed = False

    def run(self) -> None:
        pass

    def get_engines(self) -> list[_FakeEngine]:
        return [_FakeEngine(self.report)]

    def dispose(self) -> None:
        self.disposed = True


def _run_config() -> Any:
    class _Venue:
        starting_balances = ["200_000 USD"]

    class _Cfg:
        venues = [_Venue()]

    return _Cfg()


def test_zero_trade_window_yields_empty_pnls_not_a_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    # NautilusTrader returns an EMPTY report (no 'realized_pnl' column) when no position closed --
    # a variation with few signals, long-only skipping shorts, or a quiet market. That is a flat
    # window, not a failed task. (Before the guard this raised KeyError and killed the whole task.)
    _FakeNode.report = pd.DataFrame()
    monkeypatch.setattr(execution, "BacktestNode", _FakeNode)
    pnls, start = execution.extract_trade_pnls(_run_config())
    assert pnls == []
    assert start == 200_000.0


def test_trades_are_parsed_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeNode.report = pd.DataFrame({"realized_pnl": ["1_784.69 USD", "-320.00 USD"]})
    monkeypatch.setattr(execution, "BacktestNode", _FakeNode)
    pnls, start = execution.extract_trade_pnls(_run_config())
    assert pnls == [1784.69, -320.0]
    assert start == 200_000.0
