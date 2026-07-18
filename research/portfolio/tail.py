"""The crisis tail measured on the FULL history -- the ceiling no risk policy may cross.

The drawdown feasibility fits risk to the worst path *in the sample it sees*. Fit it to a benign
reserved holdout and a repeat of the worst historical gap kills the account. So the ceiling must be
measured where all the crises are: the full history.

A gap through the stop cannot be tapered by any sizing policy, so the binding number is the worst
single DAY in R (several positions gapping together is what the hard daily limit sees as one loss).
That worst day is driven by the stop distance, not the take-profit, so one representative parameter
set per market is enough -- we do NOT need to replay the walk-forward's per-window optimisation here
(which would cost hours). One full-history backtest per market, ``r`` recovered, worst day taken.

Strategy-agnostic: the parameters come from the study's own grid and the limits from the account.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from core.broker import BrokerProfile, swap_r_per_trade

from research.engine.recipe import SweepRecipe
from research.portfolio.risk import AccountProfile
from research.portfolio.stress import tail_safe_risk, worst_day_r
from research.portfolio.trades import assign_r, timed_trades_from_report


def representative_params(
    param_grid: dict[str, list[Any]], *, stop_loss_pct: float | None = None
) -> dict[str, Any]:
    """The grid's middle setting for each parameter, with the traded stop pinned when known.

    R is a *ratio* -- ``move / stop`` -- so the worst day in R depends almost entirely on the stop
    distance. Measuring the tail at the grid's middle stop while the walk-forward actually trades a
    much tighter one understates the crisis by the same ratio, and hands back a risk ceiling that is
    far too permissive. Always pass the stop the strategy really trades (``stop_loss_pct``); the
    other parameters barely move the tail, so the grid's middle is a fine stand-in for them.
    """
    params = {k: sorted(v)[len(v) // 2] for k, v in param_grid.items()}
    if stop_loss_pct is not None:
        params["stop_loss_pct"] = stop_loss_pct
    return params


def traded_stop_loss_pct(trades: pd.DataFrame) -> float:
    """The stop distance the walk-forward actually traded most often (recorded per trade).

    Raises on an empty stream (#22): there is no traded stop to report, and ``mode().iloc[0]``
    would raise an opaque IndexError several frames deeper.
    """
    if trades.empty or "sl_pct" not in trades.columns:
        raise ValueError("no trades: there is no traded stop-loss to derive a tail cap from")
    return float(trades["sl_pct"].mode().iloc[0])


def full_history_trades(
    instrument_specs: dict[str, tuple[Any, str, float]],
    markets: list[str],
    overrides: dict[str, Any],
    params: dict[str, Any],
    account: AccountProfile,
    *,
    broker: BrokerProfile | None = None,
    fixed_stops: dict[str, dict[str, Any]] | None = None,
) -> pd.DataFrame:
    """One full-history backtest per market -> combined trade stream with R.

    ``params`` is the common parameter set; ``fixed_stops`` overrides it PER MARKET (the fixed
    live SL/TP), so the tail is measured at exactly the stop each market really trades -- R is
    move/stop, so a tail measured at the wrong stop is the wrong number.
    """
    from nautilus_trader.backtest.node import BacktestNode

    frames: list[pd.DataFrame] = []
    for market in markets:
        factory, csv, leverage = instrument_specs[market]
        market_params = {**params, **(fixed_stops or {}).get(market, {})}
        recipe = SweepRecipe(
            factory(),
            csv,
            leverage=leverage,
            config_overrides={**overrides, **market_params},
            broker=broker,
            start_balance=account.start_balance,
            risk_per_trade_pct=account.base_risk_frac * 100.0,
        )
        node = BacktestNode(configs=[recipe.build_run_config({})])  # start/end None -> full history
        try:
            node.run()
            pos = node.get_engines()[0].trader.generate_positions_report()
        finally:
            node.dispose()  # type: ignore[no-untyped-call]
        rows = timed_trades_from_report(pos, market, float(market_params["stop_loss_pct"]))
        # One continuous backtest per market -> a single equity walk is the right one here.
        assign_r(rows, account.start_balance, account.base_risk_frac)
        df = pd.DataFrame(rows)
        # Carry the broker's overnight swap as a SEPARATE column (realized cost, not netted into r),
        # so returns net it while the tail cap + mark-to-market stay on the gross price R.
        df["swap_r"] = 0.0
        if broker is not None and not df.empty and (spec := broker.swap_spec(market)) is not None:
            df["swap_r"] = swap_r_per_trade(df, spec)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def full_history_tail_cap(
    instrument_specs: dict[str, tuple[Any, str, float]],
    markets: list[str],
    overrides: dict[str, Any],
    param_grid: dict[str, list[Any]],
    account: AccountProfile,
    *,
    broker: BrokerProfile | None = None,
    stress_mult: float = 1.5,
    stop_loss_pct: float | None = None,
    fixed_stops: dict[str, dict[str, Any]] | None = None,
) -> tuple[float, float, pd.DataFrame]:
    """``(worst_day_r, cap_frac, full_history_trades)`` -- the crisis-derived risk ceiling + stream.

    Pass ``stop_loss_pct`` -- the stop the strategy really trades -- or the ceiling will be measured
    at a different stop distance than it is spent at, and come out too high. ``fixed_stops`` gives
    the per-market stops when each market trades its own fixed SL/TP. The full-history trade stream
    is returned too so the same all-crises data can drive the risk-constrained-Kelly sizing (its
    drawdown bound must see the crisis tail, not the benign holdout).
    """
    trades = full_history_trades(
        instrument_specs, markets, overrides,
        representative_params(param_grid, stop_loss_pct=stop_loss_pct), account,
        broker=broker, fixed_stops=fixed_stops,
    )
    worst = worst_day_r(trades)
    cap = tail_safe_risk(
        worst,
        stress_mult=stress_mult,
        daily_hard=account.daily_hard,
        trailing_hard=account.trailing_hard,
    )
    return worst, cap, trades
