"""Render a FactSheet to a self-contained ``report.html`` (embedded charts + metric tables).

Charts are matplotlib figures embedded as base64 PNGs, so the file is fully offline / shareable
(no external assets). One file per run, written next to the other run artifacts.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from qplus.backtest.portfolio.factsheet import FactSheet  # noqa: E402

_FLAT = "#2a78d6"  # blue
_COMP = "#1baf7a"  # teal
_POS, _NEG = "#1baf7a", "#e34948"


def _b64(fig: Figure) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _chart_equity(fs: FactSheet) -> str:
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ef, ec = fs.full.equity_flat, fs.full.equity_comp
    ax.plot(ec.index, ec.to_numpy(), color=_COMP, lw=1.8, label="compound (live)")
    ax.plot(ef.index, ef.to_numpy(), color=_FLAT, lw=1.6, ls="--", label="flach (Referenz)")
    ax.axvspan(fs.holdout_start, ec.index[-1], color="0.5", alpha=0.10, label="Holdout (OOS)")
    ax.set_yscale("log")
    ax.set_ylabel("Equity (EUR, log)")
    ax.legend(loc="upper left", fontsize=9, frameon=False)
    ax.grid(True, which="both", color="0.9", lw=0.5)
    return _b64(fig)


def _chart_drawdown(fs: FactSheet) -> str:
    fig, ax = plt.subplots(figsize=(11, 2.6))
    for eq, color, ls, lab in (
        (fs.full.equity_comp, _COMP, "-", "compound"),
        (fs.full.equity_flat, _FLAT, "--", "flach"),
    ):
        dd = (eq / eq.cummax() - 1) * 100
        ax.plot(dd.index, dd.to_numpy(), color=color, lw=1.0, ls=ls, label=lab)
    ax.fill_between(
        fs.full.equity_comp.index,
        (fs.full.equity_comp / fs.full.equity_comp.cummax() - 1).to_numpy() * 100,
        0,
        color=_COMP,
        alpha=0.10,
    )
    ax.set_ylabel("Drawdown (%)")
    ax.legend(loc="lower left", fontsize=9, frameon=False)
    ax.grid(True, color="0.9", lw=0.5)
    return _b64(fig)


def _chart_year(fs: FactSheet) -> str:
    py = fs.per_year
    fig, ax = plt.subplots(figsize=(11, 2.8))
    ax.bar(
        py["year"].astype(str),
        py["ret_pct"],
        color=[_POS if v >= 0 else _NEG for v in py["ret_pct"]],
    )
    ax.axhline(0, color="0.4", lw=0.8)
    ax.set_ylabel("Rendite/Jahr (compound %, auf Kontostand)")
    ax.tick_params(axis="x", labelrotation=45, labelsize=8)
    ax.grid(True, axis="y", color="0.9", lw=0.5)
    return _b64(fig)


def _chart_market(fs: FactSheet) -> str:
    pm = fs.per_market.sort_values("ret_pct")
    fig, ax = plt.subplots(figsize=(11, 3.4))
    ax.barh(pm["market"], pm["ret_pct"], color=[_POS if v >= 0 else _NEG for v in pm["ret_pct"]])
    ax.axvline(0, color="0.4", lw=0.8)
    ax.set_xlabel("Beitrag (flach %, volle Historie)")
    ax.grid(True, axis="x", color="0.9", lw=0.5)
    return _b64(fig)


def _pct(v: float) -> str:
    return f"{v:+.1f}%"


def _table_money(fs: FactSheet) -> str:
    f, h = fs.full, fs.holdout
    rows = [
        (
            "Rendite p.a.",
            _pct(f.flat.ann_return_pct),
            _pct(f.compound.ann_return_pct),
            _pct(h.flat.ann_return_pct),
            _pct(h.compound.ann_return_pct),
        ),
        (
            "Max Drawdown",
            f"{f.flat.max_drawdown_pct:.2f}%",
            f"{f.compound.max_drawdown_pct:.2f}%",
            f"{h.flat.max_drawdown_pct:.2f}%",
            f"{h.compound.max_drawdown_pct:.2f}%",
        ),
    ]
    body = "".join(
        f"<tr><th>{r[0]}</th><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[4]}</td></tr>"
        for r in rows
    )
    return (
        "<table><thead><tr><th></th>"
        "<th>Voll · flach</th><th>Voll · comp</th><th>Hold · flach</th><th>Hold · comp</th>"
        f"</tr></thead><tbody>{body}</tbody></table>"
    )


def _table_edge(fs: FactSheet) -> str:
    f, h = fs.full.edge, fs.holdout.edge
    rows = [
        ("Sharpe (annualisiert)", f"{f.sharpe:.2f}", f"{h.sharpe:.2f}"),
        ("Trefferquote", f"{f.hit_rate * 100:.1f}%", f"{h.hit_rate * 100:.1f}%"),
        ("Profit-Faktor", f"{f.profit_factor:.2f}", f"{h.profit_factor:.2f}"),
        ("Payoff", f"{f.payoff:.2f} : 1", f"{h.payoff:.2f} : 1"),
        ("Erwartung / Trade", f"{f.expectancy_r:+.3f} R", f"{h.expectancy_r:+.3f} R"),
        ("Ø Haltedauer", f"{f.avg_hold_days:.1f} T", f"{h.avg_hold_days:.1f} T"),
        ("Trades", f"{f.trades:,}", f"{h.trades:,}"),
    ]
    body = "".join(f"<tr><th>{r[0]}</th><td>{r[1]}</td><td>{r[2]}</td></tr>" for r in rows)
    return (
        "<table><thead><tr><th></th><th>Volle Historie</th><th>Holdout (OOS)</th>"
        f"</tr></thead><tbody>{body}</tbody></table>"
    )


def _table_regime(df: pd.DataFrame, axis: str) -> str:
    if df.empty:
        return ""
    body = "".join(
        f"<tr><th>{r.regime}</th><td>{int(r.trades)}</td><td>{r.share * 100:.0f}%</td>"
        f"<td>{r.hit_rate * 100:.1f}%</td><td>{r.expectancy_R:+.3f} R</td><td>{r.ret_pct:+.1f}%</td></tr>"
        for r in df.itertuples()
    )
    return (
        f"<table><thead><tr><th>{axis}</th><th>Trades</th><th>Anteil</th><th>Hit</th>"
        f"<th>Erwartung</th><th>Beitrag (flach)</th></tr></thead><tbody>{body}</tbody></table>"
    )


def _img(b64: str, alt: str) -> str:
    return f'<img src="data:image/png;base64,{b64}" alt="{alt}" style="width:100%;height:auto;margin:8px 0 20px;">'


def render(fs: FactSheet, variation: str, run_name: str, out_path: Path) -> Path:
    """Write the self-contained fact-sheet HTML and return its path."""
    span = f"{fs.full.equity_flat.index[0]:%Y-%m-%d} → {fs.full.equity_flat.index[-1]:%Y-%m-%d}"
    html = f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QPlus Faktsheet — {variation}</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#1a1a19;max-width:960px;
  margin:0 auto;padding:32px 24px;line-height:1.5;}}
 h1{{font-size:22px;font-weight:600;margin:0 0 4px;}} h2{{font-size:17px;font-weight:600;margin:28px 0 8px;}}
 .sub{{color:#6b6a66;font-size:14px;margin:0 0 8px;}}
 table{{border-collapse:collapse;width:100%;font-size:14px;margin:6px 0 8px;}}
 th,td{{padding:7px 12px;text-align:right;border-bottom:1px solid #ecebe6;}}
 thead th{{color:#6b6a66;font-weight:500;border-bottom:1px solid #d8d7d0;}}
 tbody th{{text-align:left;font-weight:500;color:#1a1a19;}}
 td{{font-variant-numeric:tabular-nums;}}
 .note{{color:#6b6a66;font-size:12px;margin:4px 0 0;}}
</style></head><body>
<h1>QPlus Faktsheet — {variation}</h1>
<p class="sub">Risiko {fs.risk_pct}% pro Trade · {span} · {fs.full.edge.trades:,} Trades · Lauf {run_name}</p>

<h2>Rendite &amp; Risiko</h2>
{_table_money(fs)}
<p class="note">Flach = festes Risiko off Startkapital (linear). Compound = Risiko skaliert mit der Equity (geometrisch/CAGR). Nur diese zwei Zeilen hängen vom Sizing ab.</p>

<h2>Edge &amp; Charakter <span style="font-weight:400;color:#6b6a66;font-size:13px">(sizing-invariant)</span></h2>
{_table_edge(fs)}

<h2>Equity-Kurve</h2>
{_img(_chart_equity(fs), "Equity flach vs compound, log")}
{_img(_chart_drawdown(fs), "Drawdown flach vs compound")}

<h2>Rendite je Jahr</h2>
{_img(_chart_year(fs), "Rendite je Jahr")}

<h2>Beitrag je Markt</h2>
{_img(_chart_market(fs), "Beitrag je Markt")}

<h2>Robustheit über Marktregime <span style="font-weight:400;color:#6b6a66;font-size:13px">(volle Historie, in R)</span></h2>
{_table_regime(fs.regime_vol, "Volatilität")}
{_table_regime(fs.regime_trend, "Trend")}
<p class="note">Ein echter Edge zahlt in jedem Regime. Steigende Erwartung mit der Vola = eine gesunde Reversal-Charakteristik, kein Überanpassungs-Artefakt.</p>
</body></html>"""
    out_path.write_text(html, encoding="utf-8")
    return out_path
