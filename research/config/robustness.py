"""Robustness study configuration (variation selection via clean walk-forward).

Runs the walk-forward for every (instrument x variation). Ranked by variation averaged across
instruments, so a change only wins if it helps out-of-sample across many markets. Backtests run
NET of costs (spread + commission + slippage in-engine, realized overnight swap at close via the
standard broker snapshot). Add more instruments to the list as their data + specs arrive.

    uv run python -m research.engine.characterize research/config/robustness.py
"""

from typing import Any

from core.instruments import (
    audusd,
    de40,
    eurusd,
    gbpusd,
    us30,
    us500,
    usdcad,
    usdchf,
    usdjpy,
    ustec,
    xagusd,
    xauusd,
)
from research.portfolio.risk import AccountProfile

# The account the portfolio stages size against: our live prop account (100k) and The Trading
# Pit's hard limits. Returns and drawdowns are scale-invariant (everything downstream is booked
# from R-multiples), but the EUR figures in the portfolio/verdict report are not -- they must be the
# money we would actually make or lose. base_risk_frac is the risk the extraction's backtests use.
ACCOUNT = AccountProfile(
    start_balance=100_000.0,
    daily_hard=0.03,  # TTP hard daily loss limit -- a breach kills the account
    trailing_hard=0.06,  # TTP hard trailing max drawdown
    base_risk_frac=0.01,
)

# Leave cores free (old i7-8700, thermals) to keep the machine stable over a long run.
MAX_WORKERS = 5

# Walk-forward sizing. Step = test => NON-OVERLAPPING windows (F4): overlapping windows are
# autocorrelated, so they add no independent information and inflate the Sharpe/DSR
# significance (Lo 2002). The study is repeated across three training-window lengths to test
# whether each variation's edge is robust to the look-back (short vs long history).
TRAIN_MONTHS = [18, 24, 36]
TEST_MONTHS = 6
STEP_MONTHS = 6

# Reserve the last HOLDOUT_MONTHS: no stage (study/selection) ever sees them, and the
# chosen config is scored once on them by the portfolio + verdict stages.
HOLDOUT_MONTHS = 24

# --- Holdout status (#12) -- READ BEFORE QUOTING ANY HOLDOUT NUMBER --------------------------
# The reserved slice is clean for the STUDY and SELECTION stages: characterize/select never see
# it. It is NOT clean for the DEPLOYED configuration, because deploy decisions were made after
# looking at it:
#   - the per-market stop/target that live trades was fit on the most recent 36 months -- a
#     window that OVERLAPS the 24-month holdout;
#   - silver (XAGUSD) was added to the universe as a manual full-history pick;
#   - two configurations were compared on the "untouched" holdout before deployment.
# Stops, universe and risk ARE strategy parameters. That they do not change which entry signals
# fire is beside the point: they determine every exit, hence every R, hence the whole equity
# path. Choosing them with holdout information makes the holdout in-sample for the deployed
# config, so its numbers are an optimistic estimate, NOT out-of-sample evidence.
#
# The honest forward holdout is the LIVE track record from the freeze date onward. Re-fitting any
# deploy decision on live data restarts that clock.
HOLDOUT_CONTAMINATED = True
DEPLOY_FREEZE_DATE = "2026-07-16"  # go-live; live results after this are the clean OOS set

# Manual decisions count as trials: each was a human choosing after seeing results, so they
# enlarge the effective search space that a deflated Sharpe has to deflate for (#13).
MANUAL_TRIALS = (
    "variation picked from the stage-1 ranking",
    "silver (XAGUSD) added to the universe by hand, on full history",
    "per-market stop/target re-fit on the most recent 36 months",
    "risk policy and ceiling chosen at the portfolio stage",
    "two configurations compared on the reserved holdout",
)

# Purge the train/test boundary: a gap so trailing-window indicators / straddling positions
# cannot leak train info into the test (F5, Lopez de Prado purged/embargoed CV).
EMBARGO_DAYS = 7

# (instrument factory, CSV path, leverage). 12 instruments across metals, FX and indices.
INSTRUMENTS: list[tuple[Any, str, float]] = [
    (xauusd, "data/XAUUSD_H4.csv", 10.0),
    (xagusd, "data/XAGUSD_H4.csv", 10.0),
    (eurusd, "data/EURUSD_H4.csv", 50.0),
    (gbpusd, "data/GBPUSD_H4.csv", 50.0),
    (audusd, "data/AUDUSD_H4.csv", 50.0),
    (usdchf, "data/USDCHF_H4.csv", 50.0),
    (usdjpy, "data/USDJPY_H4.csv", 50.0),
    (usdcad, "data/USDCAD_H4.csv", 50.0),
    (us30, "data/US30_H4.csv", 15.0),
    (de40, "data/DE40_H4.csv", 15.0),
    (us500, "data/US500_H4.csv", 15.0),
    (ustec, "data/USTEC_H4.csv", 15.0),
]

# Full inner grid (buy_rsi_threshold is inert, so it is dropped) -> 24 combos/window.
# A wider grid means the per-window optimizer picks from a more realistic parameter set.
#
# The stop grid deliberately reaches BELOW the tail-adjusted optimum (~0.3% measured on XAUUSD): a
# search that pins to the smallest value on offer has not found an optimum, it has hit a wall. R is
# move/stop, so raw R keeps rising as the stop tightens; what turns it around is the tail (a gap
# costs more R against a tighter stop, which lowers the risk ceiling). The tail can only bite if the
# grid is allowed to go there -- so 0.2% is included to keep the optimum interior.
PARAM_GRID: dict[str, list[Any]] = {
    "stop_loss_pct": [0.2, 0.3, 0.5, 1.0, 1.5, 2.0],
    "take_profit_pct": [1.0, 2.0, 3.0, 4.0],
}

# Named strategy variations (config overrides). "baseline" is the current strategy.
# The first eight are the full 2^3 factorial of the three buy-confirmations, so each
# indicator's marginal contribution can be read off cleanly; the rest probe trade
# direction and indicator lengths. Position-sizing risk is NOT a variation here -- it only
# scales PnL (return and drawdown alike), so it is neutral in the risk-adjusted ranking and
# belongs in Stage 4 (sizing), not Stage 1.
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
    "ema20": {"ema_length": 20},  # default 10
    "bb30": {"bb_length": 30},  # default 20
    "wpr21": {"wpr_length": 21},  # default 14
}
