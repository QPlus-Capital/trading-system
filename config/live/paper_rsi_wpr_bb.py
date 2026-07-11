"""Paper/live configuration for the selected strategy (prop-firm phase, via MetaTrader 5).

The research pipeline selected: **RsiWprBb** with the Bollinger and Williams-%R buy-
confirmations OFF (the RSI filter kept), a 36-month parameter fit, **flat** position sizing
(the drawdown-throttle added nothing once the daily limit is enforced), on **9 markets**,
under the prop firm's 6% trailing / 3% daily drawdown limits.

Stop-loss / take-profit are FIXED per market (fit on the most recent 36 months; re-fit
periodically). This module is the single source of truth for those decisions; the live MT5
runner (qplus.live.run) reads it and enforces the drawdown limits -- see the note at the bottom.
"""

from typing import Any

from qplus.instruments import (
    audusd_ttp,
    de40_ttp,
    eurusd_ttp,
    gbpusd_ttp,
    us30_ttp,
    us500_ttp,
    usdjpy_ttp,
    ustec_ttp,
    xauusd_ttp,
)

# Flat risk per trade -- the SINGLE source of truth (the live runner builds RiskLimits from this).
# Sized to the framework's gap tail cap: over the FULL history at these fixed per-market stops the
# worst single day was -11.1R (COVID, 2020-03-16); the cap is 3% daily / (1.5 x 11.1R) = 0.18%,
# i.e. the largest flat risk at which a 1.5x-worse-than-COVID gap day still fits the HARD 3% daily
# limit. Risk-constrained Kelly confirms the trade-sequence drawdown is comfortably safe there
# (full-history max drawdown ~2.5% vs the 6% trailing wall; RCK would even allow 0.4%+). Raised
# from 0.15% to run at that proven ceiling; the internal 2.5%/5% safety halt is the extra net.
# (0.18% = 1.5x-COVID buffer; drop toward 0.15% for a ~2x-COVID buffer.)
RISK_PER_TRADE_PCT = 0.18

# The chosen structure (no_bb_wpr): drop the Bollinger + Williams-%R buy-confirmations, keep
# the RSI filter; long/short reversal (not long-only).
STRATEGY_SWITCHES: dict[str, Any] = {
    "use_bb_confirm": False,
    "use_wpr_confirm": False,
    "use_rsi_filter": True,
    "long_only": False,
}

# (factory, csv, leverage, stop_loss_pct, take_profit_pct). SL/TP fit on the last 36 months.
MARKETS: list[tuple[Any, str, float, float, float]] = [
    (xauusd_ttp, "data/XAUUSD_H4.csv", 10.0, 1.0, 3.0),
    (eurusd_ttp, "data/EURUSD_H4.csv", 50.0, 0.5, 3.0),
    (gbpusd_ttp, "data/GBPUSD_H4.csv", 50.0, 0.5, 1.0),
    (audusd_ttp, "data/AUDUSD_H4.csv", 50.0, 0.5, 2.0),
    (usdjpy_ttp, "data/USDJPY_H4.csv", 50.0, 0.5, 1.0),
    (us30_ttp, "data/US30_H4.csv", 15.0, 0.5, 3.0),
    (de40_ttp, "data/DE40_H4.csv", 15.0, 1.5, 2.0),
    (us500_ttp, "data/US500_H4.csv", 15.0, 1.0, 3.0),
    (ustec_ttp, "data/USTEC_H4.csv", 15.0, 1.0, 4.0),
]


def strategy_config(stop_loss_pct: float, take_profit_pct: float) -> dict[str, Any]:
    """The full RsiWprBbConfig overrides for one market (switches + fixed SL/TP + risk)."""
    return {
        **STRATEGY_SWITCHES,
        "stop_loss_pct": stop_loss_pct,
        "take_profit_pct": take_profit_pct,
        "risk_per_trade_pct": RISK_PER_TRADE_PCT,
    }


# Live wiring: NautilusTrader has no MT5 adapter, so live runs through the MT5 bridge instead
# of a TradingNode. The runner (qplus.live.run) reads MARKETS + STRATEGY_SWITCHES from here,
# reuses the pure signal engine (live == backtest), and enforces the daily/trailing limits via
# qplus.live.risk_control. Start it with: uv run python -m qplus.live.run  (SIGNAL_ONLY dry-run).
