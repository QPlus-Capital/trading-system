"""Extraction helper for the portfolio stage.

Builds the per-instrument extractor that produces the timed out-of-sample trade stream for a
universe. The old end-to-end pipeline *runner* and the flat/throttle feasibility *scorecard* were
superseded by the staged CLI (``qplus.backtest.stages``) and the risk system (``portfolio.risk``);
only this injected extractor survives, imported by the portfolio stage.
"""

from collections.abc import Callable
from typing import Any

import pandas as pd

from qplus.backtest.broker import TTP_MARKETS
from qplus.backtest.foundation.recipe import SweepRecipe
from qplus.backtest.portfolio.trades import extract_market_trades

# extract_fn(market, config_overrides, train_months) -> timed trades for that instrument.
ExtractFn = Callable[[str, dict[str, Any], int], pd.DataFrame]


def make_extract_fn(
    instrument_specs: dict[str, tuple[Any, str, float]],
    *,
    test_months: int,
    param_grid: dict[str, list[Any]],
    holdout_months: int = 0,
    phase: str = "holdout",
    embargo_days: int = 0,
    start_balance: float = 200_000.0,
    risk_per_trade_pct: float = 1.0,
    fixed_stops: dict[str, dict[str, Any]] | None = None,
) -> ExtractFn:
    """Default extractor for the portfolio stream.

    Enforces **non-overlapping** windows (``step = test``) so no trade is double-counted
    (F1), and extracts the reserved-**holdout** slice by default so the portfolio is scored
    once on data no stage selected on (F2).

    ``start_balance`` / ``risk_per_trade_pct`` are the account the extraction's backtests size
    against; pass the real account so every stage measures the same thing. The per-trade R that
    comes out is scale-invariant either way, but the position quantities are not, and a small
    enough account silently falls back to the fixed trade size.

    ``fixed_stops`` maps a market to the SL/TP it should trade in EVERY window instead of
    re-optimising the stop per window. This validates the config we actually deploy (fixed stops),
    whose gentle tail permits a tradeable size -- as opposed to the re-optimised path, which chases
    the tightest stop on the grid and is tail-capped to an untradeable one.
    """

    def extract(market: str, overrides: dict[str, Any], train_months: int) -> pd.DataFrame:
        factory, csv, leverage = instrument_specs[market]
        # Net-of-cost portfolio: the broker profile applies slippage in-engine (spread +
        # commission are already in), consistent with the study + live, so the feasibility is
        # not over-optimistic (avoids the gross-of-cost sizing trap).
        recipe = SweepRecipe(
            factory(),
            csv,
            leverage=leverage,
            param_grid=param_grid,
            config_overrides=overrides,
            broker=TTP_MARKETS,
            start_balance=start_balance,
            risk_per_trade_pct=risk_per_trade_pct,
        )
        return extract_market_trades(
            recipe,
            train_months=train_months,
            test_months=test_months,
            step_months=test_months,  # F1: non-overlapping -> no double-counted trades
            param_grid=param_grid,
            holdout_months=holdout_months,
            phase=phase,
            embargo_days=embargo_days,
            fixed_params=(fixed_stops or {}).get(market),
        )

    return extract
