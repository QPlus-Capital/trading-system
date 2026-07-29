"""QPlus live-vs-backtest monitoring dashboard.

Run from the repo root with the MT5 terminal open + logged in::

    uv run streamlit run monitoring/dashboard.py

Shows how the live account tracks the backtest expectation: the realized equity curve,
the live edge metrics vs the backtest reference (per market), the cumulative-R path against the
backtest Monte-Carlo band, and the current risk usage. Reads live data from MT5 and the backtest
reference from the latest ``reports/research/`` run; changes nothing on the account.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from core.paths import REPO_ROOT
from live.accounts import ACCOUNTS
from live.mt5_bridge import SYMBOL_MAP, AccountState, Mt5Bridge
from live.runner import position_risk, risk_per_trade_from_live_config

from monitoring.deals import (
    deal_ledger,
    deals_to_trades,
    equity_curve,
    live_stats,
    per_trade_risk,
)
from monitoring.reference import load_reference, mc_band
from monitoring.risk_view import summarize_open_risk, window_history
from monitoring.study_explorer import METRICS, latest_study_csv, load_study, variant_ranking

_REPO = REPO_ROOT
# Far enough back to cover any account this monitor is pointed at; MT5 simply returns what exists.
_ACCOUNT_INCEPTION = datetime(2000, 1, 1, tzinfo=UTC)
# #20: read the risk fraction from the live config rather than restating it here -- a hardcoded
# copy silently goes stale the moment the deployed value changes, and every R on this page is
# measured against it.
_LIVE_RISK_PCT = risk_per_trade_from_live_config()
# Validated data-viz palette (see the dataviz skill's reference palette).
_BLUE, _MUTED, _GRID = "#2a78d6", "#898781", "#e1e0d9"
_GOOD, _WARN, _CRIT = "#0ca30c", "#fab219", "#d03b3b"
_SNAPSHOT_ATTEMPTS = 3


def _snapshot_identity(deals: list[dict[str, Any]]) -> tuple[tuple[object, ...], ...]:
    """Identity and money content of an ordered MT5 deal snapshot."""
    fields = (
        "ticket",
        "time",
        "type",
        "entry",
        "position_id",
        "symbol",
        "volume",
        "price",
        "profit",
        "swap",
        "commission",
        "fee",
    )
    return tuple(tuple(deal.get(field) for field in fields) for deal in deals)


def _stable_history_account(bridge: Mt5Bridge) -> tuple[list[dict[str, Any]], AccountState]:
    """Read an account snapshot bracketed by identical deal histories, or fail closed."""
    for _attempt in range(_SNAPSHOT_ATTEMPTS):
        before = bridge.history_deals(_ACCOUNT_INCEPTION)
        before_account = bridge.account()
        after = bridge.history_deals(_ACCOUNT_INCEPTION)
        after_account = bridge.account()
        if (
            _snapshot_identity(before) == _snapshot_identity(after)
            and before_account.balance == after_account.balance
        ):
            return after, after_account
    raise RuntimeError(
        f"could not obtain a stable MT5 deal/account snapshot after {_SNAPSHOT_ATTEMPTS} attempts"
    )


@st.cache_data(ttl=60)
def _load_live(account_name: str) -> dict[str, Any]:
    """Pull live deals / account / positions / open-risk from the terminal (cached 60s).

    Builds the bridge with THIS account's symbol overrides (e.g. TTP names Nasdaq ``USTEC``,
    the base map names it ``UT100``), so symbols resolve on whichever terminal we attach to.
    """
    profile = ACCOUNTS[account_name]
    bridge = Mt5Bridge(symbol_map={**SYMBOL_MAP, **profile.symbol_overrides})
    bridge.connect(path=profile.terminal_path)
    try:
        # #29: the FULL history, always. Each trade's risk basis is the balance as it stood at
        # that trade's open, reconstructed backwards from the current balance -- so the ledger
        # has to reach back past the display window, whose only job is what gets drawn.
        deals, acct = _stable_history_account(bridge)
        term_to_research = {v: k for k, v in bridge._resolved.items()}
        pricing: list[tuple[str, float | None]] = []
        positions = []
        position_snapshot = bridge.position_snapshot()
        for issue in position_snapshot.issues:
            research = term_to_research.get(issue.symbol, issue.symbol)
            pricing.append((research, None))
        for p in position_snapshot.positions:
            research = term_to_research.get(p.symbol, p.symbol)
            info = bridge.symbol_info(research) if research in bridge._resolved else None
            # Price it the way the RUNNER does (#19): the tick_value arithmetic understates
            # converted symbols -- DE40 by a measured 14.4% -- so showing the arithmetic here
            # would report more headroom under the 2% cap than the risk controller is charging.
            priced = bridge.loss_to_stop(p)
            # #30: None means the runner treats this position as infinite risk and blocks new
            # entries; it must not be softened into an estimate or a zero on the way to the UI.
            risk = priced if priced is not None else (position_risk(p, info) if info else None)
            pricing.append((research, risk))
            positions.append(
                {
                    "symbol": research,
                    "side": p.side,
                    "volume": p.volume,
                    "profit": p.profit,
                    "sl": p.sl,
                    "tp": p.tp,
                    "risk": risk,
                }
            )
        return {
            "deals": deals,
            "balance": acct.balance,
            "equity": acct.equity,
            "currency": acct.currency,
            "open_risk": summarize_open_risk(pricing),
            "positions": positions,
            "term_to_research": term_to_research,
        }
    finally:
        bridge.shutdown()


def _risk_state(account_name: str) -> dict[str, Any]:
    p = _REPO / "reports" / "live" / account_name / "risk_state.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _stat_row(label: str, live: float, ref: float, fmt: str, higher_better: bool = True) -> None:
    delta = live - ref
    ok = (delta >= 0) == higher_better
    st.metric(
        label,
        format(live, fmt),
        delta=f"{'+' if delta >= 0 else ''}{format(delta, fmt)} gegenüber BT",
        delta_color="normal" if ok else "inverse",
    )


def _live_view() -> None:
    st.title("QPlus — Live vs. Backtest Monitor")

    with st.sidebar:
        names = sorted(ACCOUNTS)
        account_name = st.selectbox("Account", names, index=names.index("ttp"))
        days = st.slider("History window (days)", 7, 365, 90)
        if st.button("Refresh now"):
            st.cache_data.clear()
        st.caption(
            "Live-Daten aus MT5 (60-Sekunden-Cache). Backtest-Referenz: der neueste Lauf unter "
            "reports/research/."
        )

    profile = ACCOUNTS[account_name]
    # -- load --
    try:
        live = _load_live(account_name)
    except Exception as exc:  # noqa: BLE001 -- surface connection issues in the UI
        st.error(
            f"Das MT5-Terminal konnte nicht gelesen werden: {exc}\n\n"
            "Ist es geöffnet und angemeldet?"
        )
        return
    # Newest framework run that actually carries the reference stream (a run dir may be partial).
    runs = [
        d
        for d in (_REPO / "reports" / "research").glob("run_*")
        if (d / "full_history_trades.csv").is_file()
    ]
    if not runs:
        st.warning(
            "Noch keine Backtest-Referenz vorhanden — zuerst die Backtest-Pipeline ausführen "
            "(`just backtest`)."
        )
        return
    ref = load_reference(max(runs, key=lambda d: d.stat().st_mtime) / "full_history_trades.csv")

    all_trades = deals_to_trades(live["deals"])
    all_trades["market"] = (
        all_trades["symbol"].map(live["term_to_research"]).fillna(all_trades["symbol"])
    )
    state = _risk_state(profile.name)
    # Every booked movement, not just completed trades: an open position's entry commission/fee is
    # already in the broker's balance and would otherwise be inherited into every earlier basis.
    ledger = deal_ledger(live["deals"])
    current_balance = Decimal(str(live["balance"]))
    # #20: normalise EACH trade off the balance it was actually sized against, not off today's.
    # Sizing compounds, so one risk figure from current balance shrinks the early trades' R as the
    # account grows -- which would read as performance drift that never happened.
    # #29: computed over the FULL history, then windowed; the window is a display choice and must
    # not move any trade's basis. Reconstructed BACKWARDS from the current balance (balance_at),
    # so no opening figure has to be guessed and a truncated prefix cannot corrupt what we see.
    all_risk = per_trade_risk(all_trades, current_balance, _LIVE_RISK_PCT, ledger=ledger)

    # A saved start balance does not make the deal ledger complete. If replaying everything the
    # broker returned does not land on the balance it reports, history is missing and every basis
    # before the gap is approximate -- say so rather than presenting exact-looking numbers.
    if "start_balance" in state:
        ledger_anchor = Decimal(str(state["start_balance"]))
        moved = sum(ledger["amount"], start=Decimal("0")) if not ledger.empty else Decimal("0")
        before = current_balance - moved  # the balance the ledger implies before its first entry
        # Exactly two outcomes are legitimate. A ledger that reaches back past the account being
        # funded implies a pre-funding balance of zero; one that starts after funding implies the
        # funded balance itself. Anything else means booked events are missing from between.
        if min(abs(before), abs(before - ledger_anchor)) > Decimal("1"):
            st.caption(
                f"Die Handelshistorie scheint unvollständig: Ihre Wiedergabe ergibt "
                f"{before:,.0f} vor dem ersten Eintrag; das ist weder null noch der gespeicherte "
                f"Startsaldo von {ledger_anchor:,.0f}. Historische R-Werte sind nur Näherungen."
            )

    window_start = pd.Timestamp(datetime.now(tz=UTC) - timedelta(days=days))
    view = window_history(
        all_trades,
        all_risk,
        window_start=window_start,
        current_balance=current_balance,
        ledger=ledger,
    )
    trades, trade_risk, start_balance = view.trades, view.risk, view.start_balance
    if view.hidden:
        st.caption(
            f"Die Risikobasis je Trade wurde über die vollständige Historie berechnet "
            f"({view.hidden} ältere Trades außerhalb dieses Zeitfensters)."
        )

    # -- account / risk header --
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Eigenkapital", f"{live['equity']:,.0f} {live['currency']}")
    c2.metric("Kontostand", f"{live['balance']:,.0f} {live['currency']}")
    c3.metric(
        "Unrealisierter P&L",
        f"{live['equity'] - live['balance']:+,.0f} {live['currency']}",
    )
    cap = 0.020 * live["equity"]
    risk = live["open_risk"]
    if risk.determinate:
        c4.metric(
            "Offenes Risiko",
            f"{risk.total:,.0f} / {cap:,.0f}",
            help="Gesamtes offenes Stop-Risiko im Verhältnis zur Obergrenze von 2,0 %",
        )
    else:
        # Match the runner exactly: it treats unpriceable exposure as infinite and opens nothing.
        # A number here would invite acting on headroom the account does not have.
        c4.metric(
            "Offenes Risiko",
            "nicht bestimmbar",
            help="Mindestens eine offene Position kann nicht bewertet werden — der Runner "
            "rechnet sie als unbegrenztes Risiko und blockiert neue Einstiege.",
        )
        st.error(
            "Offenes Risiko kann nicht bestimmt werden: Für folgende Märkte ist keine Bewertung "
            f"möglich: {', '.join(risk.unpriceable)}. Der Runner behandelt dies als unbegrenztes "
            "Risiko und eröffnet keine neuen Positionen; deshalb zeigt diese Seite keinen "
            "verfügbaren Risikospielraum."
        )

    if trades.empty:
        st.info(
            "Noch keine geschlossenen Trades — der erste wird abgewartet. Der Vergleich füllt "
            "sich, sobald Trades geschlossen werden."
        )
    else:
        net = trades["net_pnl"].to_numpy(dtype=object)
        r_values = np.array(
            [pnl / risk_amount for pnl, risk_amount in zip(net, trade_risk, strict=True)],
            dtype=object,
        )
        ls, ro = live_stats(net), ref["overall"]
        st.subheader("Edge — live vs. backtest expectation")
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.metric("Live-Trades", f"{len(trades):,}")
        with k2:
            _stat_row("Trefferquote", ls["hit_rate"], ro["hit_rate"], ".1%")
        with k3:
            _stat_row("Profitfaktor", ls["profit_factor"], ro["profit_factor"], ".2f")
        with k4:
            _stat_row(
                "Erwartungswert je Trade (R)",
                float(sum(r_values, start=Decimal("0")) / len(r_values)) if len(r_values) else 0.0,
                ro["expectancy"],
                "+.2f",
            )

        # -- equity curve --
        st.subheader("Realized equity (live)")
        # Cut the ledger at the WINDOW boundary, not at the first displayed close: a payout in
        # between belongs to the window's balance path, and start_balance is measured there.
        window_ledger = ledger[ledger["time"] >= window_start] if not ledger.empty else ledger
        eq = equity_curve(start_balance, window_ledger)
        chart_eq = eq.assign(equity=eq["equity"].map(float))
        st.altair_chart(
            alt.Chart(chart_eq)
            .mark_line(color=_BLUE, strokeWidth=2)
            .encode(
                x=alt.X("close_time:T", title="date"),
                y=alt.Y(
                    "equity:Q", title=f"equity ({live['currency']})", scale=alt.Scale(zero=False)
                ),
                tooltip=["close_time:T", alt.Tooltip("equity:Q", format=",.0f")],
            )
            .properties(height=300),
            use_container_width=True,
        )

        # -- live cumulative R vs backtest Monte-Carlo band --
        st.subheader("Cumulative R — live vs. backtest expectation band")
        st.caption(
            "Live innerhalb des grauen 5–95-%-Bands = im Einklang mit dem Backtest. Darunter = "
            "schwächere Entwicklung."
        )
        band = mc_band(ref["r_multiples"], len(trades))
        running_r = Decimal("0")
        cumulative_r: list[float] = []
        for value in r_values:
            running_r += value
            cumulative_r.append(float(running_r))
        live_r = pd.DataFrame({"trade": np.arange(1, len(trades) + 1), "cum_r": cumulative_r})
        area = (
            alt.Chart(band)
            .mark_area(color=_MUTED, opacity=0.18)
            .encode(x=alt.X("trade:Q", title="trade #"), y="p5:Q", y2="p95:Q")
        )
        median = (
            alt.Chart(band)
            .mark_line(color=_MUTED, strokeDash=[4, 3])
            .encode(x="trade:Q", y=alt.Y("p50:Q", title="cumulative R"))
        )
        live_line = (
            alt.Chart(live_r)
            .mark_line(color=_BLUE, strokeWidth=2.5)
            .encode(x="trade:Q", y="cum_r:Q", tooltip=[alt.Tooltip("cum_r:Q", format="+.2f")])
        )
        st.altair_chart(
            (area + median + live_line).properties(height=320), use_container_width=True
        )

        # -- per-market table --
        st.subheader("Per market — live vs. backtest")
        rows = []
        for m, g in trades.groupby("market"):
            n = g["net_pnl"].to_numpy(dtype=object)
            s = live_stats(n)
            bt = ref["per_market"].get(m, {})
            rows.append(
                {
                    "market": m,
                    "live trades": len(g),
                    "live hit": f"{s['hit_rate']:.0%}",
                    "BT hit": f"{bt.get('hit_rate', float('nan')):.0%}",
                    "live PF": f"{s['profit_factor']:.2f}",
                    "BT PF": f"{bt.get('profit_factor', float('nan')):.2f}",
                    "live net": f"{sum(n, start=Decimal('0')):+,.0f}",
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # -- open positions + floors --
    st.subheader("Open positions & safety floors")
    if live["positions"]:
        st.dataframe(pd.DataFrame(live["positions"]), use_container_width=True, hide_index=True)
    else:
        st.caption("Keine offenen Positionen.")
    if state:
        hwm, day_start = float(state["hwm_balance"]), float(state["day_start_balance"])
        # The prop-firm floor is anchored to the ACCOUNT's start balance as the runner recorded
        # it -- never to today's balance or to whatever the display window begins at. Shortening
        # the window must not move a hard limit.
        anchor = float(state["start_balance"])
        trailing = min(anchor, hwm - 0.05 * anchor)
        daily = day_start - 0.025 * day_start
        f1, f2 = st.columns(2)
        f1.metric(
            "Nachlaufende Untergrenze (5 %)",
            f"{trailing:,.0f}",
            delta=f"{live['equity'] - trailing:+,.0f} Spielraum",
        )
        f2.metric(
            "Tagesuntergrenze (2,5 %)",
            f"{daily:,.0f}",
            delta=f"{live['equity'] - daily:+,.0f} Spielraum",
        )


def _research_view() -> None:
    st.title("QPlus — Research Explorer")
    csv = latest_study_csv(_REPO / "reports")
    if csv is None:
        st.warning(
            "Keine Studie unter reports/research/ gefunden. `research.engine.characterize` "
            "ausführen."
        )
        return
    df = load_study(csv)

    with st.sidebar:
        trains = sorted(df["train_months"].unique())
        train = int(st.selectbox("Training length (months)", trains, index=len(trains) - 1))
        metric_label = st.selectbox("Metric", list(METRICS.keys()))
        instruments = sorted(df["instrument"].unique())
        picked = st.multiselect("Instruments", instruments, default=instruments)

    col, mid, higher = METRICS[metric_label]
    sub = df[(df["train_months"] == train) & (df["instrument"].isin(picked))]
    st.caption(
        f"Studie: {csv.parent.name} · {len(df)} Zeilen · eingefrorene Live-Konfiguration = "
        "no_bb_wpr @ 36m. Farbe: Blau = besser, Rot = schlechter."
    )
    if sub.empty:
        st.info("Mindestens ein Instrument auswählen.")
        return

    # -- heatmap: variation x instrument --
    st.subheader(f"{metric_label} — variation × instrument (train {train}m)")
    lo, hi = ("#d03b3b", "#2a78d6") if higher else ("#2a78d6", "#d03b3b")
    scale = (
        alt.Scale(range=[lo, "#f0efec", hi], domainMid=mid)
        if mid is not None
        else alt.Scale(range=[lo, hi])
    )
    heat = (
        alt.Chart(sub)
        .mark_rect(stroke="#fcfcfb", strokeWidth=2)
        .encode(
            x=alt.X("instrument:N", title=None, sort=picked),
            y=alt.Y("variation:N", title=None),
            color=alt.Color(f"{col}:Q", title=metric_label, scale=scale),
            tooltip=["instrument", "variation", alt.Tooltip(f"{col}:Q", format=".2f")],
        )
        .properties(height=28 * sub["variation"].nunique() + 40)
    )
    st.altair_chart(heat, use_container_width=True)

    # -- variation ranking (mean across markets) --
    st.subheader(f"Variation ranking — mean {metric_label} across markets (train {train}m)")
    rank = variant_ranking(sub, train, col)
    bars = (
        alt.Chart(rank)
        .mark_bar(color="#2a78d6", cornerRadius=3)
        .encode(
            x=alt.X(f"{col}:Q", title=metric_label),
            y=alt.Y("variation:N", sort="-x", title=None),
            tooltip=["variation", alt.Tooltip(f"{col}:Q", format=".2f")],
        )
        .properties(height=28 * len(rank) + 40)
    )
    st.altair_chart(bars, use_container_width=True)

    st.subheader("Data")
    st.dataframe(sub.round(3), use_container_width=True, hide_index=True)


def main() -> None:
    st.set_page_config(page_title="QPlus Monitor", layout="wide")
    with st.sidebar:
        view = st.radio("View", ["Live Monitor", "Research Explorer"])
        st.divider()
    if view == "Live Monitor":
        _live_view()
    else:
        _research_view()


if __name__ == "__main__":
    main()  # Streamlit executes the module top-to-bottom
