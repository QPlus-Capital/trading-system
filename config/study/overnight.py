"""Overnight robustness study configuration.

Runs the clean walk-forward for every (instrument x variation). Ranked by variation
averaged across instruments, so a change only wins if it helps out-of-sample across
many markets. Add more instruments to the list as their data + specs arrive.

    uv run python -m qplus.backtest.edge.characterize config/study/overnight.py
"""

from typing import Any

from qplus.instruments import (
    audusd_ttp,
    de40_ttp,
    eurusd_ttp,
    gbpusd_ttp,
    us30_ttp,
    us500_ttp,
    usdcad_ttp,
    usdchf_ttp,
    usdjpy_ttp,
    ustec_ttp,
    xagusd_ttp,
    xauusd_ttp,
)

# Leave cores free (old i7-8700, thermals) to keep the machine stable over a long run.
MAX_WORKERS = 5

# Walk-forward sizing. A 3-month step (vs the 6-month default) roughly doubles the number
# of out-of-sample windows -> more OOS observations. The whole study is repeated across
# three training-window lengths, which tests whether each variation's edge is robust to the
# look-back (short vs long history) instead of just spending compute on re-testing noise.
TRAIN_MONTHS = [18, 24, 36]
TEST_MONTHS = 6
STEP_MONTHS = 3

# Reserve the last HOLDOUT_MONTHS: no stage (study/selection) ever sees them, and the
# chosen config is scored once on them by the pipeline -- the honest guard against
# selecting on out-of-sample results (F2).
HOLDOUT_MONTHS = 24

# (instrument factory, CSV path, leverage). 12 instruments across metals, FX and indices.
INSTRUMENTS: list[tuple[Any, str, float]] = [
    (xauusd_ttp, "data/XAUUSD_H4.csv", 10.0),
    (xagusd_ttp, "data/XAGUSD_H4.csv", 10.0),
    (eurusd_ttp, "data/EURUSD_H4.csv", 50.0),
    (gbpusd_ttp, "data/GBPUSD_H4.csv", 50.0),
    (audusd_ttp, "data/AUDUSD_H4.csv", 50.0),
    (usdchf_ttp, "data/USDCHF_H4.csv", 50.0),
    (usdjpy_ttp, "data/USDJPY_H4.csv", 50.0),
    (usdcad_ttp, "data/USDCAD_H4.csv", 50.0),
    (us30_ttp, "data/US30_H4.csv", 15.0),
    (de40_ttp, "data/DE40_H4.csv", 15.0),
    (us500_ttp, "data/US500_H4.csv", 15.0),
    (ustec_ttp, "data/USTEC_H4.csv", 15.0),
]

# Full inner grid (buy_rsi_threshold is inert, so it is dropped) -> 16 combos/window.
# A wider grid means the per-window optimizer picks from a more realistic parameter set.
PARAM_GRID: dict[str, list[Any]] = {
    "stop_loss_pct": [0.5, 1.0, 1.5, 2.0],
    "take_profit_pct": [1.0, 2.0, 3.0, 4.0],
}

# Named strategy variations (config overrides). "baseline" is the current strategy.
# The first eight are the full 2^3 factorial of the three buy-confirmations, so each
# indicator's marginal contribution can be read off cleanly; the rest probe trade
# direction, risk level and indicator lengths.
VARIATIONS: dict[str, dict[str, Any]] = {
    "baseline": {},  # all three confirmations on
    "no_bb": {"use_bb_confirm": False},
    "no_wpr": {"use_wpr_confirm": False},
    "no_rsi": {"use_rsi_filter": False},
    "no_bb_wpr": {"use_bb_confirm": False, "use_wpr_confirm": False},
    "no_bb_rsi": {"use_bb_confirm": False, "use_rsi_filter": False},
    "no_wpr_rsi": {"use_wpr_confirm": False, "use_rsi_filter": False},
    "no_confirms": {
        "use_bb_confirm": False,
        "use_wpr_confirm": False,
        "use_rsi_filter": False,
    },
    "long_only": {"long_only": True},
    "risk0.5": {"risk_per_trade_pct": 0.5},  # lower risk -> lower drawdown reference
    "ema20": {"ema_length": 20},  # default 10
    "bb30": {"bb_length": 30},  # default 20
    "wpr21": {"wpr_length": 21},  # default 14
}
