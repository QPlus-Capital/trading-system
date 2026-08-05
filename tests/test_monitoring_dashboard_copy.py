"""Behavioral guard for the dashboard's operator-facing German copy."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Any, Self

import numpy as np
import pandas as pd
import pytest
import streamlit
from monitoring.risk_view import HistoryWindow, OpenRisk
from workflow.operator_copy import operator_literal_parts


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
        self.warnings: list[str] = []
        self.metrics: list[dict[str, object]] = []
        self.dataframes: list[object] = []

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

    def warning(self, text: str) -> None:
        self.warnings.append(text)

    def columns(self, count: int) -> list[_Column]:
        return [_Column(self.metrics) for _ in range(count)]

    def subheader(self, _text: str) -> None:
        return None

    def dataframe(self, frame: object, **_kwargs: object) -> None:
        self.dataframes.append(frame)


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


def _scoped_operator_literal_parts(dashboard: ModuleType) -> set[str]:
    """Collect every literal rendered by the copy surface governed by P-15."""
    module_path = dashboard.__file__
    assert module_path is not None
    source = Path(module_path).read_text(encoding="utf-8")
    return _literal_texts(source, filename=str(module_path))


def _literal_texts(source: str, *, filename: str = "dashboard_fixture.py") -> set[str]:
    return {str(part.value) for part in operator_literal_parts(source, filename=filename)}


def test_static_bindings_are_copy_while_interpolated_runtime_values_are_data() -> None:
    source = """MODULE_LABEL = "Historie"

def render(single):
    position_label = "Position wurde" if single else "Positionen wurden"
    st.warning(f"{MODULE_LABEL}: {position_label} {exc} {count} {item.reason} {detail()}")
"""
    assert _literal_texts(source) == {
        "Historie",
        ": ",
        " ",
        "Position wurde",
        "Positionen wurden",
    }


def test_unresolved_operator_copy_fails_with_source_location_and_expression() -> None:
    for expression in ("unknown", "build()", "items[0]"):
        with pytest.raises(ValueError) as error:
            _literal_texts(f"st.warning({expression})\n")
        assert "dashboard_fixture.py:1" in str(error.value)
        assert expression in str(error.value)


def test_every_post_p14_operator_literal_is_the_reviewed_german_copy(monkeypatch: Any) -> None:
    dashboard = _import_dashboard(monkeypatch)
    assert _scoped_operator_literal_parts(dashboard) == {
        " gegenüber BT",
        "Live-Daten aus MT5 (60-Sekunden-Cache). Backtest-Referenz: der neueste Lauf unter "
        "reports/research/.",
        "Das MT5-Terminal konnte nicht gelesen werden: ",
        "\n\nIst es geöffnet und angemeldet?",
        "Noch keine Backtest-Referenz vorhanden — zuerst die Backtest-Pipeline ausführen "
        "(`just backtest`).",
        "Die Trade-Historie konnte nicht rekonstruiert werden: ",
        "Nicht unterstützte MT5-Historie: ",
        "Position wurde",
        "Positionen wurden",
        " aus der Trade-Tabelle ausgeschlossen: ",
        "Die Handelshistorie scheint unvollständig: Ihre Wiedergabe ergibt ",
        " vor dem ersten Eintrag; das ist weder null noch der gespeicherte Startsaldo von ",
        ". Historische R-Werte sind nur Näherungen.",
        "Die Risikobasis je Trade wurde über die vollständige Historie berechnet (",
        " ältere Trades außerhalb dieses Zeitfensters).",
        "Eigenkapital",
        "Kontostand",
        "Unrealisierter P&L",
        " ",
        "Offenes Risiko",
        " / ",
        "Gesamtes offenes Stop-Risiko im Verhältnis zur Obergrenze von 2,0 %",
        "nicht bestimmbar",
        "Mindestens eine offene Position kann nicht bewertet werden — der Runner rechnet sie "
        "als unbegrenztes Risiko und blockiert neue Einstiege.",
        "Offenes Risiko kann nicht bestimmt werden: Für folgende Märkte ist keine Bewertung "
        "möglich: ",
        ". Der Runner behandelt dies als unbegrenztes Risiko und eröffnet keine neuen Positionen; "
        "deshalb zeigt diese Seite keinen verfügbaren Risikospielraum.",
        "Noch keine geschlossenen Trades — der erste wird abgewartet. Der Vergleich füllt sich, "
        "sobald Trades geschlossen werden.",
        "Live-Trades",
        "Trefferquote",
        "Profitfaktor",
        "Erwartungswert je Trade (R)",
        "Live innerhalb des grauen 5–95-%-Bands = im Einklang mit dem Backtest. Darunter = "
        "schwächere Entwicklung.",
        "Keine offenen Positionen.",
        "Nachlaufende Untergrenze (5 %)",
        " Spielraum",
        "Tagesuntergrenze (2,5 %)",
        "Keine Studie unter reports/research/ gefunden. `research.engine.characterize` ausführen.",
        "Studie: ",
        " · ",
        " Zeilen · eingefrorene Live-Konfiguration = no_bb_wpr @ 36m. Farbe: Blau = besser, "
        "Rot = schlechter.",
        "Mindestens ein Instrument auswählen.",
    }


def test_connection_error_is_german_and_preserves_the_english_exception(
    monkeypatch: Any,
) -> None:
    dashboard = _import_dashboard(monkeypatch)
    rendered = _RenderedStreamlit()

    def fail(_account: str) -> None:
        raise RuntimeError("terminal connection refused")

    monkeypatch.setattr(dashboard, "st", rendered)
    monkeypatch.setattr(dashboard, "_load_live", fail)

    dashboard._live_view()

    assert rendered.errors == [
        "Das MT5-Terminal konnte nicht gelesen werden: terminal connection refused\n\n"
        "Ist es geöffnet und angemeldet?"
    ]


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
            start_balance=Decimal("100"),
            hidden=3,
        ),
    )

    dashboard._live_view()

    assert {metric["label"] for metric in rendered.metrics} == {
        "Eigenkapital",
        "Kontostand",
        "Unrealisierter P&L",
        "Offenes Risiko",
        "Nachlaufende Untergrenze (5 %)",
        "Tagesuntergrenze (2,5 %)",
    }
    assert {metric["delta"] for metric in rendered.metrics if metric["delta"] is not None} == {
        "+90 Spielraum",
        "-5 Spielraum",
    }
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


def test_live_dashboard_preserves_safety_view_when_reconstruction_refuses(
    monkeypatch: Any, tmp_path: Path
) -> None:
    dashboard = _import_dashboard(monkeypatch)
    rendered = _RenderedStreamlit()
    run = tmp_path / "reports" / "research" / "run_test"
    run.mkdir(parents=True)
    (run / "full_history_trades.csv").write_text("market,r\n", encoding="utf-8")
    live: dict[str, Any] = {
        "deals": [
            {
                "position_id": 42,
                "symbol": "AAPL",
                "type": 15,
                "entry": 0,
                "time": 10,
                "ticket": 7001,
                "volume": 1.0,
            },
            {
                "position_id": 42,
                "symbol": "AAPL",
                "type": 1,
                "entry": 1,
                "time": 20,
                "ticket": 7002,
                "volume": 1.0,
            },
        ],
        "balance": 200.0,
        "equity": 190.0,
        "currency": "EUR",
        "open_risk": OpenRisk(total=10.0),
        "positions": [{"symbol": "AAPL", "side": "BUY", "risk": 10.0}],
        "term_to_research": {},
    }
    empty_trades = pd.DataFrame(
        {
            "symbol": pd.Series(dtype=str),
            "close_time": pd.Series(dtype="datetime64[ns, UTC]"),
            "net_pnl": pd.Series(dtype=object),
        }
    )

    monkeypatch.setattr(dashboard, "st", rendered)
    monkeypatch.setattr(dashboard, "_REPO", tmp_path)
    monkeypatch.setattr(dashboard, "_load_live", lambda _account: live)
    monkeypatch.setattr(dashboard, "load_reference", lambda _path: {})
    monkeypatch.setattr(
        dashboard,
        "_risk_state",
        lambda _account: {
            "start_balance": 200.0,
            "hwm_balance": 200.0,
            "day_start_balance": 200.0,
        },
    )
    monkeypatch.setattr(
        dashboard,
        "per_trade_risk",
        lambda *_args, **_kwargs: np.array([], dtype=object),
    )
    monkeypatch.setattr(
        dashboard,
        "window_history",
        lambda *_args, **_kwargs: HistoryWindow(
            trades=empty_trades,
            risk=np.array([], dtype=object),
            start_balance=Decimal("200"),
            hidden=0,
        ),
    )

    dashboard._live_view()

    assert rendered.errors == [
        "Die Trade-Historie konnte nicht rekonstruiert werden: unsupported MT5 opening deal "
        "type 15: ticket=7001, entry=0, position_id=42"
    ]
    assert any(
        isinstance(frame, pd.DataFrame) and frame.to_dict(orient="records") == live["positions"]
        for frame in rendered.dataframes
    )
    assert {metric["label"] for metric in rendered.metrics} >= {
        "Nachlaufende Untergrenze (5 %)",
        "Tagesuntergrenze (2,5 %)",
    }


def test_dashboard_names_unsupported_positions(monkeypatch: Any, tmp_path: Path) -> None:
    dashboard = _import_dashboard(monkeypatch)
    rendered = _RenderedStreamlit()
    run = tmp_path / "reports" / "research" / "run_test"
    run.mkdir(parents=True)
    (run / "full_history_trades.csv").write_text("market,r\n", encoding="utf-8")
    live: dict[str, Any] = {
        "deals": [
            {
                "position_id": 42,
                "symbol": "AAPL",
                "type": 0,
                "entry": 0,
                "time": 10,
                "ticket": 7001,
                "volume": 1.0,
            },
            {
                "position_id": 42,
                "symbol": "AAPL",
                "type": 1,
                "entry": 2,
                "time": 20,
                "ticket": 7002,
                "volume": 1.0,
            },
            {
                "position_id": 77,
                "symbol": "MSFT",
                "type": 0,
                "entry": 0,
                "time": 30,
                "ticket": 8001,
                "volume": 1.0,
            },
            {
                "position_id": 77,
                "symbol": "MSFT",
                "type": 13,
                "entry": 0,
                "time": 40,
                "ticket": 8002,
                "volume": 1.0,
            },
        ],
        "balance": 200.0,
        "equity": 200.0,
        "currency": "EUR",
        "open_risk": OpenRisk(total=0.0),
        "positions": [],
        "term_to_research": {},
    }

    monkeypatch.setattr(dashboard, "st", rendered)
    monkeypatch.setattr(dashboard, "_REPO", tmp_path)
    monkeypatch.setattr(dashboard, "_load_live", lambda _account: live)
    monkeypatch.setattr(dashboard, "load_reference", lambda _path: {})
    monkeypatch.setattr(dashboard, "_risk_state", lambda _account: {})
    monkeypatch.setattr(
        dashboard,
        "window_history",
        lambda trades, *_args, **_kwargs: HistoryWindow(
            trades=trades,
            risk=np.array([], dtype=object),
            start_balance=Decimal("200"),
            hidden=0,
        ),
    )

    dashboard._live_view()

    assert rendered.warnings == [
        "Nicht unterstützte MT5-Historie: 2 Positionen wurden aus der Trade-Tabelle "
        "ausgeschlossen: 42 (AAPL: entry INOUT (2) cannot be reconstructed); "
        "77 (MSFT: later IN deal type 13 is unsupported)"
    ]
