"""QPlus live-vs-backtest monitoring dashboard (roadmap Phase 2, v0).

Run from the repo root with the MT5 terminal open + logged in::

    uv run streamlit run src/qplus/monitoring/dashboard.py

Shows how the live/paper account tracks the backtest expectation: the realized equity curve,
the live edge metrics vs the backtest reference (per market), the cumulative-R path against the
backtest Monte-Carlo band, and the current risk usage. Reads live data from MT5 and the backtest
reference from ``reports/equity/``; changes nothing on the account.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from qplus.live.mt5_bridge import Mt5Bridge
from qplus.live.runner import position_risk
from qplus.monitoring.live import deals_to_trades, equity_curve, live_stats
from qplus.monitoring.reference import load_reference, mc_band

_REPO = Path(__file__).resolve().parents[3]
_LIVE_RISK_PCT = 0.0015  # 0.15% flat, matches the live config
_BT_RISK = 300.0  # backtest per-trade risk (0.15% of 200k), for the R-expectancy comparison
# Validated data-viz palette (see the dataviz skill's reference palette).
_BLUE, _MUTED, _GRID = "#2a78d6", "#898781", "#e1e0d9"
_GOOD, _WARN, _CRIT = "#0ca30c", "#fab219", "#d03b3b"


@st.cache_data(ttl=60)
def _load_live(days: int) -> dict[str, Any]:
    """Pull live deals / account / positions / open-risk from the terminal (cached 60s)."""
    bridge = Mt5Bridge()
    bridge.connect()
    try:
        since = datetime.now(tz=UTC) - timedelta(days=days)
        deals = bridge.history_deals(since)
        acct = bridge.account()
        term_to_research = {v: k for k, v in bridge._resolved.items()}
        open_risk, positions = 0.0, []
        for p in bridge.positions():
            research = term_to_research.get(p.symbol, p.symbol)
            info = bridge.symbol_info(research) if research in bridge._resolved else None
            risk = position_risk(p, info) if info else 0.0
            open_risk += risk
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
            "open_risk": open_risk,
            "positions": positions,
            "term_to_research": term_to_research,
        }
    finally:
        bridge.shutdown()


def _risk_state() -> dict[str, Any]:
    p = _REPO / "reports" / "live" / "risk_state.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _stat_row(label: str, live: float, ref: float, fmt: str, higher_better: bool = True) -> None:
    delta = live - ref
    ok = (delta >= 0) == higher_better
    st.metric(
        label,
        format(live, fmt),
        delta=f"{'+' if delta >= 0 else ''}{format(delta, fmt)} vs BT",
        delta_color="normal" if ok else "inverse",
    )


def main() -> None:
    st.set_page_config(page_title="QPlus Monitor", layout="wide")
    st.title("QPlus — Live vs. Backtest Monitor")

    with st.sidebar:
        st.header("Controls")
        days = st.slider("History window (days)", 7, 365, 90)
        if st.button("Refresh now"):
            st.cache_data.clear()
        st.caption("Live data from MT5 (60s cache). Backtest reference from reports/equity/.")

    # -- load --
    try:
        live = _load_live(days)
    except Exception as exc:  # noqa: BLE001 -- surface connection issues in the UI
        st.error(f"Could not read from the MT5 terminal: {exc}\n\nIs it open and logged in?")
        return
    ref_csv = _REPO / "reports" / "equity" / "portfolio_trades.csv"
    if not ref_csv.exists():
        st.warning(
            "No backtest reference yet — run `qplus.backtest.portfolio.equity_report` first."
        )
        return
    ref = load_reference(ref_csv)

    trades = deals_to_trades(live["deals"])
    trades["market"] = trades["symbol"].map(live["term_to_research"]).fillna(trades["symbol"])
    state = _risk_state()
    start_balance = float(state.get("start_balance", live["balance"]))
    live_risk = _LIVE_RISK_PCT * start_balance

    # -- account / risk header --
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Equity", f"{live['equity']:,.0f} {live['currency']}")
    c2.metric("Balance", f"{live['balance']:,.0f} {live['currency']}")
    c3.metric("Floating", f"{live['equity'] - live['balance']:+,.0f} {live['currency']}")
    cap = 0.015 * live["equity"]
    c4.metric(
        "Open risk",
        f"{live['open_risk']:,.0f} / {cap:,.0f}",
        help="Total open stop-risk vs the 1.5% cap",
    )

    if trades.empty:
        st.info(
            "No closed trades yet — waiting for the first. The comparison fills in as trades close."
        )
    else:
        net = trades["net_pnl"].to_numpy()
        ls, ro = live_stats(net), ref["overall"]
        st.subheader("Edge — live vs. backtest expectation")
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.metric("Live trades", f"{len(trades):,}")
        with k2:
            _stat_row("Hit rate", ls["hit_rate"], ro["hit_rate"], ".1%")
        with k3:
            _stat_row("Profit factor", ls["profit_factor"], ro["profit_factor"], ".2f")
        with k4:
            _stat_row(
                "Expectancy / trade (R)",
                ls["expectancy"] / live_risk,
                ro["expectancy"] / _BT_RISK,
                "+.2f",
            )

        # -- equity curve --
        st.subheader("Realized equity (live)")
        eq = equity_curve(trades, start_balance)
        st.altair_chart(
            alt.Chart(eq)
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
            "Live in the grey 5–95% band = tracking the backtest. Below it = under-performing."
        )
        band = mc_band(ref["r_multiples"], len(trades))
        live_r = pd.DataFrame(
            {"trade": np.arange(1, len(trades) + 1), "cum_r": np.cumsum(net / live_risk)}
        )
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
            n = g["net_pnl"].to_numpy()
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
                    "live net": f"{n.sum():+,.0f}",
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # -- open positions + floors --
    st.subheader("Open positions & safety floors")
    if live["positions"]:
        st.dataframe(pd.DataFrame(live["positions"]), use_container_width=True, hide_index=True)
    else:
        st.caption("No open positions.")
    if state:
        hwm, day_start = float(state["hwm_balance"]), float(state["day_start_balance"])
        trailing = min(start_balance, hwm - 0.05 * start_balance)
        daily = day_start - 0.025 * day_start
        f1, f2 = st.columns(2)
        f1.metric(
            "Trailing floor (5%)",
            f"{trailing:,.0f}",
            delta=f"{live['equity'] - trailing:+,.0f} headroom",
        )
        f2.metric(
            "Daily floor (2.5%)", f"{daily:,.0f}", delta=f"{live['equity'] - daily:+,.0f} headroom"
        )


main()  # Streamlit executes the module top-to-bottom
