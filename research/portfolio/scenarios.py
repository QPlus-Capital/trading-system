"""Calendar loss-day scenarios and joint stationary-bootstrap path summaries.

Stage 3 builds one row per P-09 :class:`~research.portfolio.sizing.DailyDiagnostics` day. Stage 4
resamples those rows as indivisible bundles with the P-04 stationary bootstrap. The H4 minimum is
never reconstructed here: it is copied from the shared diagnostic object already used by sizing,
the verdict, and the fact sheet.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Protocol

import numpy as np
import numpy.typing as npt
import pandas as pd

from research.portfolio.curves import to_day
from research.portfolio.resample import (
    DEFAULT_REPLICATIONS,
    DEFAULT_SEED,
    SENSITIVITY_BLOCK_LENGTHS,
    select_block_length,
    stationary_bootstrap,
)
from research.portfolio.sizing import DailyDiagnostics

_EPOCH_DATE = date(1970, 1, 1)
_CSV_COLUMNS = (
    "source_date",
    "close_realized_pnl",
    "close_equity_change",
    "opening_to_minimum_equity_change",
    "closing_balance_change",
    "trade_count",
    "daily_swap",
)
_ACCOUNTING_TOLERANCE = Decimal("1e-8")
IntArray = npt.NDArray[np.int64]


class _PolicyScenarioInput(Protocol):
    """The bounded `PolicyResult` surface needed to construct scenarios."""

    @property
    def trade_pnl(self) -> np.ndarray: ...

    @property
    def trade_swap(self) -> np.ndarray: ...

    @property
    def daily_diagnostics(self) -> DailyDiagnostics: ...


def _decimal(value: object) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


@dataclass(frozen=True)
class LossDayScenario:
    """One indivisible observed loss-day bundle, with exact monetary accounting."""

    source_date: date
    close_realized_pnl: Decimal
    close_equity_change: Decimal
    opening_to_minimum_equity_change: Decimal
    closing_balance_change: Decimal
    trade_count: int
    daily_swap: Decimal

    def __post_init__(self) -> None:
        money = (
            self.close_realized_pnl,
            self.close_equity_change,
            self.opening_to_minimum_equity_change,
            self.closing_balance_change,
            self.daily_swap,
        )
        if any(not value.is_finite() for value in money):
            raise ValueError(f"scenario {self.source_date} contains non-finite money")
        if isinstance(self.trade_count, bool) or self.trade_count < 0:
            raise ValueError(f"scenario {self.source_date} has an invalid trade count")
        if self.close_realized_pnl + self.daily_swap != self.closing_balance_change:
            raise ValueError(
                f"scenario {self.source_date} violates realized P&L + swap = balance change"
            )


@dataclass(frozen=True)
class BootstrapSensitivity:
    """One named block-length probability result."""

    label: str
    block_length: int
    prob_profit: Decimal

    def to_json(self) -> dict[str, str | int]:
        return {
            "label": self.label,
            "block_length": self.block_length,
            "prob_profit": str(self.prob_profit),
        }


@dataclass(frozen=True)
class ScenarioBootstrapSummary:
    """Calendar-day bootstrap result and pre-registered block-length sensitivity."""

    seed: int
    replications: int
    horizon_days: int
    selected_block_length: int
    sensitivity: tuple[BootstrapSensitivity, ...]

    @property
    def prob_profit(self) -> Decimal:
        """The plug-in block-length probability used by the existing Stage-4 check."""
        return self.sensitivity[0].prob_profit

    def to_json(self) -> dict[str, object]:
        return {
            "method": "Politis-Romano stationary bootstrap of complete loss-day scenarios",
            "seed": self.seed,
            "replications": self.replications,
            "horizon_days": self.horizon_days,
            "selected_block_length": self.selected_block_length,
            "prob_profit": str(self.prob_profit),
            "sensitivity": [item.to_json() for item in self.sensitivity],
        }


def _validated_diagnostics(diagnostics: DailyDiagnostics) -> int:
    arrays = (
        diagnostics.days,
        diagnostics.opening_balance,
        diagnostics.close_balance,
        diagnostics.close_equity,
        diagnostics.minimum_equity,
        diagnostics.daily_loss,
        diagnostics.trailing_floor,
        diagnostics.daily_breach,
        diagnostics.trailing_breach,
    )
    lengths = {len(values) for values in arrays}
    if len(lengths) != 1 or not lengths or 0 in lengths:
        raise ValueError("daily diagnostics must contain equal, non-empty arrays")
    days = np.asarray(diagnostics.days, dtype=np.int64)
    if np.any(np.diff(days) != 1):
        raise ValueError("daily diagnostics must use one contiguous loss-day grid")
    for values in arrays[1:6]:
        if not np.isfinite(np.asarray(values, dtype=np.float64)).all():
            raise ValueError("daily diagnostics contain non-finite values")
    return len(days)


def build_loss_day_scenarios(
    trades: pd.DataFrame,
    result: _PolicyScenarioInput,
    *,
    start_balance: Decimal,
) -> tuple[LossDayScenario, ...]:
    """Build one exact scenario row per P-09 diagnostic day.

    Closing-balance movement is authoritative for realized net P&L. The separately sized swap leg
    is subtracted from that movement to expose price P&L without reconstructing balance through a
    second accumulation order.
    """
    diagnostics = result.daily_diagnostics
    sample_size = _validated_diagnostics(diagnostics)
    if "ts_closed" not in trades.columns:
        raise ValueError("scenario trades require ts_closed")
    if len(trades) != len(result.trade_pnl) or len(trades) != len(result.trade_swap):
        raise ValueError("trade rows, policy P&L, and policy swap must have equal lengths")
    if not np.isfinite(np.asarray(result.trade_pnl, dtype=np.float64)).all():
        raise ValueError("policy trade P&L must be finite")
    if not np.isfinite(np.asarray(result.trade_swap, dtype=np.float64)).all():
        raise ValueError("policy trade swap must be finite")

    days = np.asarray(diagnostics.days, dtype=np.int64)
    day_to_index = {int(day): index for index, day in enumerate(days)}
    expected_opening = start_balance
    for index, opening in enumerate(diagnostics.opening_balance):
        actual_opening = _decimal(opening)
        if abs(actual_opening - expected_opening) > _ACCOUNTING_TOLERANCE:
            raise ValueError(
                f"diagnostic opening balance is discontinuous on "
                f"{_EPOCH_DATE + timedelta(days=int(days[index]))}"
            )
        expected_opening = _decimal(diagnostics.close_balance[index])
    trade_counts = [0] * sample_size
    daily_swap = [Decimal("0") for _ in range(sample_size)]
    daily_net = [Decimal("0") for _ in range(sample_size)]
    for trade_index, timestamp in enumerate(trades["ts_closed"]):
        loss_day = to_day(int(timestamp))
        if loss_day not in day_to_index:
            raise ValueError(f"trade closes outside daily diagnostics: loss day {loss_day}")
        day_index = day_to_index[loss_day]
        trade_counts[day_index] += 1
        daily_swap[day_index] += _decimal(result.trade_swap[trade_index])
        daily_net[day_index] += _decimal(result.trade_pnl[trade_index])

    prior_close_balance = start_balance
    prior_close_equity = start_balance
    scenarios: list[LossDayScenario] = []
    for index, day_number in enumerate(days):
        close_balance = _decimal(diagnostics.close_balance[index])
        close_equity = _decimal(diagnostics.close_equity[index])
        opening_balance = _decimal(diagnostics.opening_balance[index])
        minimum_equity = _decimal(diagnostics.minimum_equity[index])
        balance_change = close_balance - prior_close_balance
        if abs(balance_change - daily_net[index]) > _ACCOUNTING_TOLERANCE:
            raise ValueError(
                f"policy P&L disagrees with diagnostic balance on "
                f"{_EPOCH_DATE + timedelta(days=int(day_number))}"
            )
        swap = daily_swap[index]
        scenarios.append(
            LossDayScenario(
                source_date=_EPOCH_DATE + timedelta(days=int(day_number)),
                close_realized_pnl=balance_change - swap,
                close_equity_change=close_equity - prior_close_equity,
                opening_to_minimum_equity_change=minimum_equity - opening_balance,
                closing_balance_change=balance_change,
                trade_count=trade_counts[index],
                daily_swap=swap,
            )
        )
        prior_close_balance = close_balance
        prior_close_equity = close_equity
    return tuple(scenarios)


def write_loss_day_scenarios(path: Path, scenarios: Sequence[LossDayScenario]) -> None:
    """Persist canonical Decimal scenario rows without a float serialization round-trip."""
    if not scenarios:
        raise ValueError("loss-day scenarios must be non-empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(_CSV_COLUMNS)
        for row in scenarios:
            writer.writerow(
                (
                    row.source_date.isoformat(),
                    str(row.close_realized_pnl),
                    str(row.close_equity_change),
                    str(row.opening_to_minimum_equity_change),
                    str(row.closing_balance_change),
                    row.trade_count,
                    str(row.daily_swap),
                )
            )


def read_loss_day_scenarios(path: Path) -> tuple[LossDayScenario, ...]:
    """Read and validate the exact Stage-3 scenario artifact."""
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != _CSV_COLUMNS:
                raise ValueError("loss-day scenario CSV has an invalid schema")
            scenarios = tuple(
                LossDayScenario(
                    source_date=date.fromisoformat(row["source_date"]),
                    close_realized_pnl=Decimal(row["close_realized_pnl"]),
                    close_equity_change=Decimal(row["close_equity_change"]),
                    opening_to_minimum_equity_change=Decimal(
                        row["opening_to_minimum_equity_change"]
                    ),
                    closing_balance_change=Decimal(row["closing_balance_change"]),
                    trade_count=int(row["trade_count"]),
                    daily_swap=Decimal(row["daily_swap"]),
                )
                for row in reader
            )
    except (OSError, UnicodeError, KeyError, ArithmeticError) as exc:
        raise ValueError(f"cannot read loss-day scenarios from {path}") from exc
    if not scenarios:
        raise ValueError("loss-day scenario CSV must be non-empty")
    if any(
        current.source_date != previous.source_date + timedelta(days=1)
        for previous, current in zip(scenarios, scenarios[1:], strict=False)
    ):
        raise ValueError("loss-day scenario dates must be contiguous and strictly increasing")
    return scenarios


def _stationary_source_indices(
    sample_size: int,
    mean_block_length: int,
    *,
    replications: int,
    seed: int,
) -> IntArray:
    if sample_size <= 0:
        raise ValueError("loss-day scenarios must be non-empty")
    sampled = stationary_bootstrap(
        np.arange(sample_size, dtype=np.float64),
        mean_block_length,
        replications=replications,
        seed=seed,
    )
    indices = sampled.astype(np.int64)
    if not np.array_equal(sampled, indices):
        raise ValueError("stationary bootstrap returned invalid source indices")
    return indices


def sample_scenario_paths(
    scenarios: Sequence[LossDayScenario],
    *,
    mean_block_length: int,
    replications: int = DEFAULT_REPLICATIONS,
    seed: int = DEFAULT_SEED,
) -> tuple[tuple[LossDayScenario, ...], ...]:
    """Resample complete scenario rows with one shared source-index draw."""
    source = tuple(scenarios)
    indices = _stationary_source_indices(
        len(source),
        mean_block_length,
        replications=replications,
        seed=seed,
    )
    return tuple(tuple(source[int(index)] for index in path) for path in indices)


def validate_joint_paths(
    source: Sequence[LossDayScenario],
    paths: Sequence[Sequence[LossDayScenario]],
) -> None:
    """Fail when a sampled row is not one complete observed source-day bundle."""
    observed = set(source)
    horizon = len(source)
    if horizon == 0:
        raise ValueError("loss-day scenarios must be non-empty")
    for path in paths:
        if len(path) != horizon:
            raise ValueError(f"scenario path has {len(path)} days, expected {horizon}")
        if any(row not in observed for row in path):
            raise ValueError("scenario path contains a row that is not an observed joint bundle")


def _probability_of_profit(
    scenarios: tuple[LossDayScenario, ...],
    block_length: int,
    *,
    replications: int,
    seed: int,
) -> Decimal:
    paths = sample_scenario_paths(
        scenarios,
        mean_block_length=block_length,
        replications=replications,
        seed=seed,
    )
    profitable = sum(
        sum((row.closing_balance_change for row in path), start=Decimal("0")) > 0 for path in paths
    )
    return Decimal(profitable) / Decimal(replications)


def summarize_scenario_bootstrap(
    scenarios: Sequence[LossDayScenario],
    *,
    replications: int = DEFAULT_REPLICATIONS,
    seed: int = DEFAULT_SEED,
) -> ScenarioBootstrapSummary:
    """Report plug-in and fixed-block calendar-path `P(profit)` without changing any gate."""
    source = tuple(scenarios)
    if not source:
        raise ValueError("loss-day scenarios must be non-empty")
    returns = np.asarray(
        [float(row.closing_balance_change) for row in source],
        dtype=np.float64,
    )
    selected = select_block_length({"closing_balance_change": returns})
    choices = (("plugin", selected),) + tuple(
        (f"fixed_{block_length}", block_length) for block_length in SENSITIVITY_BLOCK_LENGTHS
    )
    sensitivity = tuple(
        BootstrapSensitivity(
            label=label,
            block_length=block_length,
            prob_profit=_probability_of_profit(
                source,
                block_length,
                replications=replications,
                seed=seed,
            ),
        )
        for label, block_length in choices
    )
    return ScenarioBootstrapSummary(
        seed=seed,
        replications=replications,
        horizon_days=len(source),
        selected_block_length=selected,
        sensitivity=sensitivity,
    )
