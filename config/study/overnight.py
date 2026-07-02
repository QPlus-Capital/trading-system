"""Overnight robustness study configuration.

Runs the clean walk-forward for every (instrument x variation). Ranked by variation
averaged across instruments, so a change only wins if it helps out-of-sample across
many markets. Add more instruments to the list as their data + specs arrive.

    uv run python -m qplus.backtest.study config/study/overnight.py
"""

from typing import Any

from qplus.instruments import (
    de40_ttp,
    eurusd_ttp,
    gbpusd_ttp,
    us30_ttp,
    xauusd_ttp,
)

# Leave some cores free (old CPU) to keep the machine stable overnight.
MAX_WORKERS = 5

# (instrument factory, CSV path, leverage).
INSTRUMENTS: list[tuple[Any, str, float]] = [
    (xauusd_ttp, "data/XAUUSD_H4.csv", 10.0),
    (eurusd_ttp, "data/EURUSD_H4.csv", 50.0),
    (gbpusd_ttp, "data/GBPUSD_H4.csv", 50.0),
    (us30_ttp, "data/US30_H4.csv", 15.0),
    (de40_ttp, "data/DE40_H4.csv", 15.0),
]

# Focused inner grid (buy_rsi_threshold is inert, so it is dropped) -> 6 combos/window.
PARAM_GRID: dict[str, list[Any]] = {
    "stop_loss_pct": [0.5, 1.0, 1.5],
    "take_profit_pct": [2.0, 4.0],
}

# Named strategy variations (config overrides). "baseline" is the current strategy.
VARIATIONS: dict[str, dict[str, Any]] = {
    "baseline": {},
    "long_only": {"long_only": True},
    "no_rsi_filter": {"use_rsi_filter": False},
    "no_wpr_confirm": {"use_wpr_confirm": False},
    "no_bb_confirm": {"use_bb_confirm": False},
    "no_confirms": {
        "use_rsi_filter": False,
        "use_wpr_confirm": False,
        "use_bb_confirm": False,
    },
    "long_only_risk0.5": {"long_only": True, "risk_per_trade_pct": 0.5},
    "risk0.5": {"risk_per_trade_pct": 0.5},
    "risk0.25": {"risk_per_trade_pct": 0.25},
    "ema20": {"ema_length": 20},
    "bb30": {"bb_length": 30},
    "wpr21": {"wpr_length": 21},
}
