"""Behavioral guard for the dashboard's operator-facing German copy."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import Any, Self

import numpy as np
import pandas as pd
import streamlit
from monitoring.risk_view import HistoryWindow, OpenRisk


class _Context:
    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class _Column:
    def __init__(self, metrics: list[dict[str, object]]) -> None:
        self._metrics = metrics

    def metric(
        self,
        label: str,
        value: str,
        delta: str | None = None,
        delta_color: str | None = None,
        help: str | None = None,
    ) -> None:
        self._metrics.append(
            {
                "label": label,
                "value": value,
                "delta": delta,
                "delta_color": delta_color,
                "help": help,
            }
        )


class _RenderedStreamlit:
    def __init__(self) -> None:
        self.sidebar = _Context()
        self.captions: list[str] = []
        self.errors: list[str] = []
        self.infos: list[str] = []
        self.metrics: list[dict[str, object]] = []

    def title(self, _text: str) -> None:
        return None

    def selectbox(self, _label: str, _options: Sequence[str], **_kwargs: object) -> str:
        return "ttp"

    def slider(self, _label: str, _minimum: int, _maximum: int, value: int) -> int:
        return value

    def button(self, _label: str) -> bool:
        return False

    def caption(self, text: str) -> None:
        self.captions.append(text)

    def error(self, text: str) -> None:
        self.errors.append(text)

    def info(self, text: str) -> None:
        self.infos.append(text)

    def warning(self, _text: str) -> None:
        return None

    def columns(self, count: int) -> list[_Column]:
        return [_Column(self.metrics) for _ in range(count)]

    def subheader(self, _text: str) -> None:
        return None

    def dataframe(self, _frame: object, **_kwargs: object) -> None:
        return None


class _ImportBridge:
    def __init__(self, **_kwargs: object) -> None:
        pass

    def connect(self, **_kwargs: object) -> None:
        raise RuntimeError("dashboard import must not connect to MT5")


def _import_dashboard(monkeypatch: Any) -> ModuleType:
    """Import the Streamlit script without allowing its top-level main call to reach MT5."""
    import live.mt5_bridge as mt5_bridge

    context = _Context()

    def choose_live(_label: str, _options: Sequence[str]) -> str:
        return "Live Monitor"

    def choose_account(_label: str, _options: Sequence[str], **_kwargs: object) -> str:
        return "ttp"

    monkeypatch.setattr(mt5_bridge, "Mt5Bridge", _ImportBridge)
    monkeypatch.setattr(streamlit, "sidebar", context)
    monkeypatch.setattr(streamlit, "set_page_config", lambda **_kwargs: None)
    monkeypatch.setattr(streamlit, "radio", choose_live)
    monkeypatch.setattr(streamlit, "divider", lambda: None)
    monkeypatch.setattr(streamlit, "title", lambda _text: None)
    monkeypatch.setattr(streamlit, "selectbox", choose_account)
    monkeypatch.setattr(streamlit, "slider", lambda *_args, **_kwargs: 90)
    monkeypatch.setattr(streamlit, "button", lambda _label: False)
    monkeypatch.setattr(streamlit, "caption", lambda _text: None)
    monkeypatch.setattr(streamlit, "error", lambda _text: None)
    sys.modules.pop("monitoring.dashboard", None)
    return importlib.import_module("monitoring.dashboard")


def test_live_dashboard_renders_key_operator_guidance_in_german(
    monkeypatch: Any, tmp_path: Path
) -> None:
    dashboard = _import_dashboard(monkeypatch)
    rendered = _RenderedStreamlit()
    run = tmp_path / "reports" / "research" / "run_test"
    run.mkdir(parents=True)
    (run / "full_history_trades.csv").write_text("market,r\n", encoding="utf-8")
    trades = pd.DataFrame(
        {
            "symbol": pd.Series(dtype=str),
            "close_time": pd.Series(dtype="datetime64[ns, UTC]"),
            "net_pnl": pd.Series(dtype=float),
        }
    )
    ledger = pd.DataFrame(
        {
            "time": pd.Series(dtype="datetime64[ns, UTC]"),
            "amount": pd.Series(dtype=float),
        }
    )
    live: dict[str, Any] = {
        "deals": [],
        "balance": 200.0,
        "equity": 190.0,
        "currency": "EUR",
        "open_risk": OpenRisk(total=0.0, unpriceable=["DE40"]),
        "positions": [],
        "term_to_research": {},
    }

    monkeypatch.setattr(dashboard, "st", rendered)
    monkeypatch.setattr(dashboard, "_REPO", tmp_path)
    monkeypatch.setattr(dashboard, "_load_live", lambda _account: live)
    monkeypatch.setattr(dashboard, "load_reference", lambda _path: {})
    monkeypatch.setattr(dashboard, "deals_to_trades", lambda _deals: trades.copy())
    monkeypatch.setattr(dashboard, "deal_ledger", lambda _deals: ledger.copy())
    monkeypatch.setattr(
        dashboard,
        "per_trade_risk",
        lambda *_args, **_kwargs: np.array([], dtype=np.float64),
    )
    monkeypatch.setattr(
        dashboard,
        "_risk_state",
        lambda _account: {
            "start_balance": 100.0,
            "hwm_balance": 220.0,
            "day_start_balance": 200.0,
        },
    )
    monkeypatch.setattr(
        dashboard,
        "window_history",
        lambda *_args, **_kwargs: HistoryWindow(
            trades=trades.copy(),
            risk=np.array([], dtype=np.float64),
            start_balance=100.0,
            hidden=3,
        ),
    )

    dashboard._live_view()

    risk_metric = next(metric for metric in rendered.metrics if metric["label"] == "Offenes Risiko")
    assert risk_metric["value"] == "nicht bestimmbar"
    assert "unbegrenztes Risiko" in str(risk_metric["help"])
    assert any(
        text.startswith("Offenes Risiko kann nicht bestimmt werden") for text in rendered.errors
    )
    assert any(
        text.startswith("Die Handelshistorie scheint unvollständig") for text in rendered.captions
    )
    assert any(
        "3 ältere Trades außerhalb dieses Zeitfensters" in text for text in rendered.captions
    )
    assert "Keine offenen Positionen." in rendered.captions
    assert any(text.startswith("Noch keine geschlossenen Trades") for text in rendered.infos)

    determinate = _RenderedStreamlit()
    live["open_risk"] = OpenRisk(total=25.0)
    monkeypatch.setattr(dashboard, "st", determinate)
    dashboard._live_view()
    risk_metric = next(
        metric for metric in determinate.metrics if metric["label"] == "Offenes Risiko"
    )
    assert risk_metric["value"] == "25 / 4"
    assert risk_metric["help"] == (
        "Gesamtes offenes Stop-Risiko im Verhältnis zur Obergrenze von 2,0 %"
    )
