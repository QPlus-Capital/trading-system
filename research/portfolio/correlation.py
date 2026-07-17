"""Portfolio-level modelling: are the 9 markets really diversified, and how crowded is the book?

The sizing already works off the *combined* trade stream of all markets, so concurrent drawdowns
and the correlated worst day are implicitly in the tail cap / risk-constrained-Kelly sizing. What
those numbers do not expose is the STRUCTURE behind them -- this adds that:

- **Correlation + effective bets.** Pairwise correlation of the markets' daily (mark-to-market)
  R-returns, and the *effective number of independent bets* N_eff = (Sum lambda)^2 / Sum lambda^2
  over the correlation eigenvalues. N_eff == n means the n markets diversify fully; N_eff -> 1
  means they move as one (hidden concentration). It says whether "9 markets" is really 9 bets.
- **Concurrent exposure.** How many positions are open at once and how directionally crowded the
  book gets (net long minus short) -- the tail where one gap day hits many positions together.

Diagnostic only: it does not change sizing (the feasibility already binds on the realized
concurrent drawdown); it makes the concentration risk behind that number visible.

    uv run python -m research.portfolio.correlation
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from research.portfolio.curves import DAY_NS, align_prices, base_curves  # noqa: E402


def daily_market_returns(
    trades: pd.DataFrame, daily_closes: dict[str, pd.Series], *, value_col: str = "r"
) -> pd.DataFrame:
    """Per-market daily mark-to-market P&L (in R), indexed by day number, one column per market.

    Uses the tested ``base_curves`` machinery per market: each open position is marked to the
    daily close, so a multi-day hold contributes every day (not just on close) -- the honest
    basis for co-movement. The daily change of (realized + unrealized) is that market's daily R.
    """
    t = trades.copy()
    t["od"] = (t["ts_opened"].to_numpy() // DAY_NS).astype(int)
    t["cd"] = (t["ts_closed"].to_numpy() // DAY_NS).astype(int)
    t["pnl_base"] = t[value_col].to_numpy(dtype=float)  # base_curves reads 'pnl_base'
    d0, d1 = int(t["od"].min()), int(t["cd"].max())
    cols: dict[str, np.ndarray] = {}
    for market, group in t.groupby("market"):
        name = str(market)
        prices = {name: align_prices(daily_closes[name], d0, d1)}
        realized, unrealized = base_curves(group, prices, d0, d1)
        cols[name] = realized + unrealized
    equity = pd.DataFrame(cols, index=np.arange(d0, d1 + 1))
    return equity.diff().fillna(0.0)


def correlation_matrix(daily_returns: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlation of the per-market daily R-returns."""
    return daily_returns.corr()


def effective_bets(corr: pd.DataFrame) -> float:
    """Effective number of independent bets: (Sum lambda)^2 / Sum lambda^2 over the eigenvalues.

    n (identity / uncorrelated) down to 1 (all markets move as one). A blunt, standard read on
    how much genuine diversification the correlation structure carries.
    """
    eig = np.linalg.eigvalsh(corr.to_numpy())
    eig = eig[eig > 0]
    return float(eig.sum() ** 2 / (eig**2).sum()) if eig.size else 0.0


def daily_exposure(trades: pd.DataFrame) -> pd.DataFrame:
    """Per-day open-position counts: n_open, n_long, n_short, net (long - short).

    A trade opened on day ``od`` and closed on ``cd`` counts as open on the half-open ``[od, cd)``
    -- excluding the close day, so a same-day reversal (old closes, new opens on the same bar)
    is not double-counted and concurrency never exceeds the number of markets. Direction is
    inferred from the sign of ``r`` versus the price move (as elsewhere). Difference arrays ->
    O(trades + days).
    """
    t = trades.copy()
    od = (t["ts_opened"].to_numpy() // DAY_NS).astype(int)
    cd = (t["ts_closed"].to_numpy() // DAY_NS).astype(int)
    won = t["r"].to_numpy(dtype=float) > 0
    is_long = won == (t["exit"].to_numpy(dtype=float) > t["entry"].to_numpy(dtype=float))
    d0, d1 = int(od.min()), int(cd.max())
    n = d1 - d0 + 1
    opn, lng, sht = np.zeros(n), np.zeros(n), np.zeros(n)
    for o, c, is_l in zip(od, cd, is_long, strict=True):
        opn[o - d0] += 1
        opn[c - d0] -= 1  # -1 on the close day -> open on [od, cd)
        side = lng if is_l else sht
        side[o - d0] += 1
        side[c - d0] -= 1
    open_c = np.cumsum(opn)
    long_c = np.cumsum(lng)
    short_c = np.cumsum(sht)
    return pd.DataFrame(
        {
            "n_open": open_c.astype(int),
            "n_long": long_c.astype(int),
            "n_short": short_c.astype(int),
            "net": (long_c - short_c).astype(int),
        },
        index=np.arange(d0, d1 + 1),
    )


def concurrency_summary(exposure: pd.DataFrame, n_markets: int) -> dict[str, float]:
    """Headline crowding stats: max/mean concurrent positions and worst directional alignment."""
    active = exposure[exposure["n_open"] > 0]
    return {
        "markets": float(n_markets),
        "max_open": float(exposure["n_open"].max()),
        "mean_open_when_active": float(active["n_open"].mean()) if len(active) else 0.0,
        "pct_days_all_open": float((exposure["n_open"] >= n_markets).mean()),
        "max_net_long": float(max(0, exposure["net"].max())),
        "max_net_short": float(max(0, -exposure["net"].min())),
    }


def plot_correlation(corr: pd.DataFrame, exposure: pd.DataFrame, n_eff: float, out: Path) -> None:
    """Correlation heatmap (diverging, centred at 0) + histogram of concurrent open positions."""
    markets = list(corr.columns)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6.2))

    im = ax1.imshow(corr.to_numpy(), cmap="coolwarm", vmin=-1, vmax=1)
    ax1.set_xticks(range(len(markets)), markets, rotation=45, ha="right")
    ax1.set_yticks(range(len(markets)), markets)
    for i in range(len(markets)):
        for j in range(len(markets)):
            ax1.text(
                j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=8, color="0.15"
            )
    ax1.set_title(f"Tages-R-Korrelation je Markt\neffektive unabh. Wetten N_eff = {n_eff:.1f}")
    fig.colorbar(im, ax=ax1, fraction=0.046, pad=0.04)

    counts = exposure["n_open"].value_counts().sort_index()
    ax2.bar(counts.index.to_numpy(), counts.to_numpy(), color="tab:blue")
    ax2.set_title("Verteilung gleichzeitig offener Positionen")
    ax2.set_xlabel("gleichzeitig offene Positionen")
    ax2.set_ylabel("Tage")
    ax2.grid(True, axis="y", alpha=0.25)
    fig.suptitle("Portfolio-Konzentration -- no_bb_wpr, 9 Maerkte, netto", fontsize=12)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120)
    plt.close(fig)


def main() -> None:
    """Re-run the frozen config full-history (net of costs), then report portfolio concentration."""
    from core.broker import MEX_ATLANTIC, load_swap_snapshot, swap_snapshot_path

    from research.engine.config import load_config_module
    from research.portfolio.curves import load_daily_close
    from research.portfolio.equity_report import _REPO_ROOT, _market_trades

    cfg = load_config_module(_REPO_ROOT / "config" / "live" / "paper_rsi_wpr_bb.py")
    switches = dict(cfg.STRATEGY_SWITCHES)
    snap = swap_snapshot_path(MEX_ATLANTIC.name)
    broker = MEX_ATLANTIC.with_swaps(load_swap_snapshot(snap)) if snap.exists() else MEX_ATLANTIC

    frames, daily_closes = [], {}
    for factory, csv, leverage, sl, tp in cfg.MARKETS:
        name = str(factory().raw_symbol)
        print(f"backtesting {name} (full history) ...")
        frames.append(_market_trades(factory, csv, leverage, sl, tp, switches, broker))
        daily_closes[name] = load_daily_close(csv)
    trades = pd.concat(frames, ignore_index=True)

    returns = daily_market_returns(trades, daily_closes)
    corr = correlation_matrix(returns)
    n_eff = effective_bets(corr)
    exposure = daily_exposure(trades)
    summary = concurrency_summary(exposure, len(cfg.MARKETS))

    out_dir = _REPO_ROOT / "reports" / "equity"
    plot_correlation(corr, exposure, n_eff, out_dir / "correlation.png")

    pd.options.display.float_format = lambda v: f"{v:,.2f}"
    print("\n===== daily-R correlation matrix =====")
    print(corr.round(2).to_string())
    mean_off = (corr.to_numpy()[~np.eye(len(corr), dtype=bool)]).mean()
    print(f"\nmean off-diagonal correlation: {mean_off:.3f}")
    print(f"effective independent bets:    {n_eff:.2f} of {len(cfg.MARKETS)} markets")
    print("\n===== concurrency =====")
    for k, v in summary.items():
        print(f"{k:22s} {v:,.2f}")
    print(f"\nchart: {out_dir / 'correlation.png'}")


if __name__ == "__main__":
    main()
