"""QPlus live-vs-backtest monitoring dashboard (roadmap Phase 2, v0).

Run from the repo root with the MT5 terminal open + logged in::

    uv run streamlit run monitoring/dashboard.py

Shows how the live/paper account tracks the backtest expectation: the realized equity curve,
the live edge metrics vs the backtest reference (per market), the cumulative-R path against the
backtest Monte-Carlo band, and the current risk usage. Reads live data from MT5 and the backtest
reference from ``reports/equity/``; changes nothing on the account.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from core.paths import REPO_ROOT
from live.accounts import ACCOUNTS
from live.mt5_bridge import Mt5Bridge
from live.runner import position_risk

from monitoring.live import deals_to_trades, equity_curve, live_stats
from monitoring.reference import load_reference, mc_band
from monitoring.study_explorer import METRICS, latest_study_csv, load_study, variant_ranking

_REPO = REPO_ROOT
_LIVE_RISK_PCT = 0.0018  # 0.18% flat, matches the live config (the gap tail cap)
_BT_RISK = 180.0  # backtest per-trade risk (0.18% of the 100k base), for the R-expectancy check
# Validated data-viz palette (see the dataviz skill's reference palette).
_BLUE, _MUTED, _GRID = "#2a78d6", "#898781", "#e1e0d9"
_GOOD, _WARN, _CRIT = "#0ca30c", "#fab219", "#d03b3b"


@st.cache_data(ttl=60)
def _load_live(days: int, terminal_path: str | None) -> dict[str, Any]:
    """Pull live deals / account / positions / open-risk from the terminal (cached 60s)."""
    bridge = Mt5Bridge()
    bridge.connect(path=terminal_path)
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


def _risk_state(account_name: str) -> dict[str, Any]:
    p = _REPO / "reports" / "live" / account_name / "risk_state.json"
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


def _live_view() -> None:
    st.title("QPlus — Live vs. Backtest Monitor")

    with st.sidebar:
        names = sorted(ACCOUNTS)
        account_name = st.selectbox("Account", names, index=names.index("ttp"))
        days = st.slider("History window (days)", 7, 365, 90)
        if st.button("Refresh now"):
            st.cache_data.clear()
        st.caption("Live data from MT5 (60s cache). Backtest reference from reports/equity/.")

    profile = ACCOUNTS[account_name]
    # -- load --
    try:
        live = _load_live(days, profile.terminal_path)
    except Exception as exc:  # noqa: BLE001 -- surface connection issues in the UI
        st.error(f"Could not read from the MT5 terminal: {exc}\n\nIs it open and logged in?")
        return
    ref_csv = _REPO / "reports" / "equity" / "portfolio_trades.csv"
    if not ref_csv.exists():
        st.warning(
            "No backtest reference yet — run `research.portfolio.equity_report` first."
        )
        return
    ref = load_reference(ref_csv)

    trades = deals_to_trades(live["deals"])
    trades["market"] = trades["symbol"].map(live["term_to_research"]).fillna(trades["symbol"])
    state = _risk_state(profile.name)
    start_balance = float(state.get("start_balance", live["balance"]))
    # Compounding: risk tracks current equity, so normalise per-trade expectancy to R off equity.
    live_risk = _LIVE_RISK_PCT * float(live["equity"])

    # -- account / risk header --
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Equity", f"{live['equity']:,.0f} {live['currency']}")
    c2.metric("Balance", f"{live['balance']:,.0f} {live['currency']}")
    c3.metric("Floating", f"{live['equity'] - live['balance']:+,.0f} {live['currency']}")
    cap = 0.020 * live["equity"]
    c4.metric(
        "Open risk",
        f"{live['open_risk']:,.0f} / {cap:,.0f}",
        help="Total open stop-risk vs the 2.0% cap",
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


def _research_view() -> None:
    st.title("QPlus — Research Explorer")
    csv = latest_study_csv(_REPO / "reports")
    if csv is None:
        st.warning("No study found under reports/study/. Run `research.engine.characterize`.")
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
        f"Study: {csv.parent.name} · {len(df)} rows · frozen live config = no_bb_wpr @ 36m. "
        "Colour: blue = better, red = worse."
    )
    if sub.empty:
        st.info("Select at least one instrument.")
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


main()  # Streamlit executes the module top-to-bottom
