"""Verdict-stage charts: the pictures that make an assembled portfolio legible.

Strategy-agnostic on purpose (framework principle #1): every function takes the account context and
the already-sized PnL, so the same report renders for any strategy, any market set, any risk policy.
Nothing here knows about a particular variation, balance or risk level.

Rendered with matplotlib's Agg backend (no display needed) into a run directory.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

_EUR = FuncFormatter(lambda v, _: f"{v:,.0f}")


def _save(fig: Figure, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)


def plot_equity(equity: pd.Series, start_balance: float, title: str, out: Path) -> None:
    """Account equity over time, marked to market (open positions' floating PnL included)."""
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(equity.index, equity.to_numpy(), color="tab:blue", linewidth=1.6, label="Equity")
    ax.axhline(start_balance, color="0.6", linewidth=0.8, linestyle=":", label="Startkapital")
    peak = equity.cummax()
    ax.fill_between(equity.index, equity, peak, color="tab:red", alpha=0.12, label="Drawdown")
    ax.set_title(title)
    ax.set_xlabel("Zeit")
    ax.set_ylabel("Kontostand (EUR)")
    ax.yaxis.set_major_formatter(_EUR)
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left")
    _save(fig, out)


def plot_drawdown(equity: pd.Series, out: Path) -> None:
    """Underwater curve: how far below the running peak the account was, at every point."""
    dd = (equity - equity.cummax()) / equity.cummax() * 100
    fig, ax = plt.subplots(figsize=(12, 3.5))
    ax.fill_between(dd.index, dd.to_numpy(), 0, color="tab:red", alpha=0.35)
    ax.plot(dd.index, dd.to_numpy(), color="tab:red", linewidth=0.9)
    ax.set_title("Drawdown (Unterwasser-Kurve)")
    ax.set_ylabel("% unter Hoch")
    ax.grid(True, alpha=0.25)
    _save(fig, out)


def plot_monte_carlo(
    trade_pnl: np.ndarray, start_balance: float, out: Path, *, n_sims: int = 2000, seed: int = 7
) -> None:
    """Bootstrap the trade ORDER: how much of the outcome is edge, how much is sequence luck?"""
    rng = np.random.default_rng(seed)
    n = len(trade_pnl)
    paths = np.empty((n_sims, n + 1))
    paths[:, 0] = start_balance
    for i in range(n_sims):
        paths[i, 1:] = start_balance + np.cumsum(rng.choice(trade_pnl, size=n, replace=True))
    x = np.arange(n + 1)
    fig, ax = plt.subplots(figsize=(12, 6))
    for i in range(min(300, n_sims)):
        ax.plot(x, paths[i], color="0.75", linewidth=0.3, alpha=0.15)
    ax.plot(x, np.percentile(paths, 50, axis=0), color="tab:blue", linewidth=1.8, label="Median")
    for q in (5, 95):
        pct = np.percentile(paths, q, axis=0)
        ax.plot(x, pct, color="tab:blue", linewidth=1.0, linestyle="--")
    ax.axhline(start_balance, color="0.6", linewidth=0.8, linestyle=":")
    ax.set_title(f"Monte-Carlo: {n_sims} gemischte Trade-Reihenfolgen (5./50./95. Perzentil)")
    ax.set_xlabel("Trade #")
    ax.set_ylabel("Kontostand (EUR)")
    ax.yaxis.set_major_formatter(_EUR)
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left")
    _save(fig, out)


def plot_contributions(trades: pd.DataFrame, sized_pnl: np.ndarray, out: Path) -> None:
    """Which markets actually paid? Total EUR contribution per market, at the traded size."""
    by_market = pd.Series(sized_pnl, index=trades["market"].to_numpy()).groupby(level=0).sum()
    by_market = by_market.sort_values()
    colors = ["tab:red" if v < 0 else "tab:green" for v in by_market]
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.barh(by_market.index.tolist(), by_market.to_numpy(), color=colors)
    ax.axvline(0, color="0.4", linewidth=0.8)
    ax.set_title("Gewinnbeitrag je Markt (in der gehandelten Groesse)")
    ax.set_xlabel("Gesamt-PnL (EUR)")
    ax.xaxis.set_major_formatter(_EUR)
    ax.grid(True, axis="x", alpha=0.25)
    _save(fig, out)


def plot_stats_table(rows: list[tuple[str, str]], title: str, out: Path) -> None:
    """The metric table as an image: one ``(label, value)`` per row."""
    fig, ax = plt.subplots(figsize=(8, 0.5 * len(rows) + 2.0))
    ax.axis("off")
    ax.set_title(title, fontsize=11, pad=16)
    table = ax.table(
        cellText=[[v] for _, v in rows],
        rowLabels=[k for k, _ in rows],
        colLabels=["Wert"],
        cellLoc="center",
        rowLoc="left",
        loc="upper center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 1.6)
    for (row, _col), cell in table.get_celld().items():
        if row == 0:
            cell.set_facecolor("#2b5c8a")
            cell.set_text_props(color="white", fontweight="bold")
    fig.savefig(out, dpi=120, bbox_inches="tight")
    plt.close(fig)
