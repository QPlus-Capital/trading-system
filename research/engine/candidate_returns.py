"""Persist canonical pre-filter Stage-1 candidate return streams.

A formal candidate is one ``(variation, train_months)`` pair. Its returns come from the chosen
outer walk-forward path after the inner parameter search, never from the inner grid combinations.
The input payload carries the exact close-time ``net_r`` events already scored by Stage 1; this
module only aligns and aggregates those events at the fixed statistical risk fraction.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from research.portfolio.curves import to_day

STAT_RISK_FRAC = Decimal("0.0018")
LOSS_DAY_AXIS = "16:15 America/Chicago"
SCHEMA_VERSION = 1

CANDIDATE_DAILY_RETURNS = "candidate_daily_returns.csv"
CANDIDATE_WINDOW_RETURNS = "candidate_window_returns.csv"
CANDIDATE_MARKET_WINDOW_RETURNS = "candidate_market_window_returns.csv"
CANDIDATE_METADATA = "candidate_metadata.json"
CANDIDATE_ARTIFACTS = (
    CANDIDATE_DAILY_RETURNS,
    CANDIDATE_WINDOW_RETURNS,
    CANDIDATE_MARKET_WINDOW_RETURNS,
    CANDIDATE_METADATA,
)
_STREAM_ARTIFACTS = CANDIDATE_ARTIFACTS[:-1]
_EPOCH_DATE = date(1970, 1, 1)

HashPaths = Callable[[dict[str, str | Path]], dict[str, dict[str, str]]]


@dataclass(frozen=True)
class CandidateDefinition:
    """Stable identity of one formal outer-procedure candidate."""

    candidate_id: str
    variation: str
    train_months: int


@dataclass(frozen=True)
class CandidateEvent:
    """One canonical Stage-1 trade outcome at its close timestamp."""

    timestamp_ns: int
    net_r: Decimal

    def __post_init__(self) -> None:
        if isinstance(self.timestamp_ns, bool) or not isinstance(self.timestamp_ns, int):
            raise TypeError("candidate event timestamp_ns must be an integer")
        if not isinstance(self.net_r, Decimal):
            raise TypeError("candidate event net_r must be Decimal")
        if not self.net_r.is_finite():
            raise ValueError("candidate event net_r must be finite")


@dataclass(frozen=True)
class _CandidateWindow:
    label: str
    test_start_ns: int
    test_end_ns: int
    events: tuple[CandidateEvent, ...]

    def __post_init__(self) -> None:
        if not self.label:
            raise ValueError("candidate window label must be non-empty")
        if self.test_end_ns <= self.test_start_ns:
            raise ValueError(f"candidate window {self.label!r} has a non-positive span")


def candidate_definitions(
    variations: Mapping[str, Any] | Iterable[str],
    train_months: Iterable[int],
) -> tuple[CandidateDefinition, ...]:
    """Return ordered, unique formal candidates for the configured outer search."""
    names = list(variations if not isinstance(variations, Mapping) else variations.keys())
    trains = [int(value) for value in train_months]
    if not names or not trains:
        raise ValueError("formal candidates require variations and training lengths")
    if len(names) != len(set(names)):
        raise ValueError("variation names must be unique")
    if len(trains) != len(set(trains)) or any(value <= 0 for value in trains):
        raise ValueError("training lengths must be unique positive integers")
    definitions = tuple(
        CandidateDefinition(
            candidate_id=f"{variation}__train_{train}m",
            variation=str(variation),
            train_months=train,
        )
        for variation in names
        for train in trains
    )
    ids = [definition.candidate_id for definition in definitions]
    if len(ids) != len(set(ids)):
        raise ValueError("configured variation and training-length pairs collide as candidate IDs")
    return definitions


def _decimal(value: object, *, label: str) -> Decimal:
    if isinstance(value, bool):
        raise TypeError(f"{label} must be a finite decimal value")
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except (ValueError, TypeError) as exc:
        raise TypeError(f"{label} must be a finite decimal value") from exc
    if not parsed.is_finite():
        raise ValueError(f"{label} must be finite")
    return parsed


def _integer(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer")
    return value


def _parse_windows(raw: object, *, candidate: str, market: str) -> dict[str, _CandidateWindow]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise TypeError(f"{candidate}/{market} candidate_windows must be a sequence")
    parsed: dict[str, _CandidateWindow] = {}
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise TypeError(f"{candidate}/{market} window {index} must be a mapping")
        label = str(item.get("window", ""))
        raw_events = item.get("net_r_events")
        if not isinstance(raw_events, Sequence) or isinstance(raw_events, (str, bytes)):
            raise TypeError(f"{candidate}/{market}/{label} net_r_events must be a sequence")
        events: list[CandidateEvent] = []
        for event_index, event in enumerate(raw_events):
            if (
                not isinstance(event, Sequence)
                or isinstance(event, (str, bytes))
                or len(event) != 2
            ):
                raise TypeError(
                    f"{candidate}/{market}/{label} event {event_index} must be (timestamp, net_r)"
                )
            events.append(
                CandidateEvent(
                    _integer(event[0], label="candidate event timestamp_ns"),
                    _decimal(event[1], label="candidate event net_r"),
                )
            )
        window = _CandidateWindow(
            label,
            _integer(item.get("test_start_ns"), label=f"{label} test_start_ns"),
            _integer(item.get("test_end_ns"), label=f"{label} test_end_ns"),
            tuple(events),
        )
        if label in parsed:
            raise ValueError(f"{candidate}/{market} repeats window {label!r}")
        parsed[label] = window
    return parsed


def _format_decimal(value: Decimal) -> str:
    if not value:
        return "0"
    return format(value.normalize(), "f")


def _loss_day_iso(day_number: int) -> str:
    return (_EPOCH_DATE + timedelta(days=day_number)).isoformat()


def _write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_candidate_artifacts(
    rows: Sequence[Mapping[str, Any]],
    out_dir: Path,
    *,
    variations: Mapping[str, Any] | Iterable[str],
    train_months: Iterable[int],
    markets: Iterable[str],
    manual_trials: Iterable[str],
    source_inputs: Mapping[str, Any],
    hash_paths: HashPaths,
) -> dict[str, Any]:
    """Write aligned daily/window/market streams and return their metadata.

    Missing task rows exclude the whole formal candidate. A present market with zero events is a
    valid flat stream; absence and zero are deliberately distinct.
    """
    definitions = candidate_definitions(variations, train_months)
    expected_markets = tuple(str(market) for market in markets)
    if not expected_markets or len(expected_markets) != len(set(expected_markets)):
        raise ValueError("configured markets must be a non-empty unique sequence")
    by_key = {(item.variation, item.train_months): item for item in definitions}
    task_windows: dict[str, dict[str, dict[str, _CandidateWindow]]] = {}

    for row in rows:
        try:
            key = (str(row["variation"]), int(row["train_months"]))
            market = str(row["instrument"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("candidate task row has no valid identity") from exc
        definition = by_key.get(key)
        if definition is None:
            raise ValueError(f"unexpected candidate task {key!r}")
        if market not in expected_markets:
            raise ValueError(f"unexpected market {market!r} for {definition.candidate_id}")
        payload = row.get("candidate_windows")
        if payload is None:
            continue
        per_market = task_windows.setdefault(definition.candidate_id, {})
        if market in per_market:
            raise ValueError(f"duplicate task for {definition.candidate_id}/{market}")
        per_market[market] = _parse_windows(
            payload,
            candidate=definition.candidate_id,
            market=market,
        )

    excluded: list[dict[str, object]] = []
    complete: list[CandidateDefinition] = []
    for definition in definitions:
        have = task_windows.get(definition.candidate_id, {})
        missing = [market for market in expected_markets if market not in have]
        if missing:
            excluded.append(
                {
                    "candidate": definition.candidate_id,
                    "missing_markets": missing,
                }
            )
        else:
            complete.append(definition)
    if not complete:
        raise ValueError("no formal candidate is complete across every configured market")

    all_tasks = [
        task_windows[definition.candidate_id][market]
        for definition in complete
        for market in expected_markets
    ]
    common_labels = set.intersection(*(set(windows) for windows in all_tasks))
    if not common_labels:
        raise ValueError("complete candidates and markets share no walk-forward window")
    common_bounds = {
        label: (
            max(windows[label].test_start_ns for windows in all_tasks),
            min(windows[label].test_end_ns for windows in all_tasks),
        )
        for label in common_labels
    }
    for label, (start, end) in common_bounds.items():
        if end <= start:
            raise ValueError(f"common window {label!r} has no positive time intersection")
    labels = tuple(sorted(common_labels, key=lambda label: (common_bounds[label][0], label)))
    common_start_ns = common_bounds[labels[0]][0]
    common_end_ns = common_bounds[labels[-1]][1]
    first_day, last_day = to_day(common_start_ns), to_day(common_end_ns)
    if last_day < first_day:
        raise ValueError("candidate streams share no prop-loss day")
    days = tuple(range(first_day, last_day + 1))

    daily: dict[str, dict[int, Decimal]] = {
        definition.candidate_id: {day: Decimal(0) for day in days}
        for definition in complete
    }
    window_returns: dict[str, dict[str, Decimal]] = {
        definition.candidate_id: {label: Decimal(0) for label in labels}
        for definition in complete
    }
    market_rows: list[dict[str, object]] = []
    trade_counts: dict[str, int] = {definition.candidate_id: 0 for definition in complete}

    for definition in complete:
        candidate = definition.candidate_id
        for market in expected_markets:
            windows = task_windows[candidate][market]
            for label in labels:
                selected = [
                    event
                    for event in windows[label].events
                    if first_day <= to_day(event.timestamp_ns) <= last_day
                ]
                net_r = sum((event.net_r for event in selected), Decimal(0))
                flat_return = net_r * STAT_RISK_FRAC
                window_returns[candidate][label] += flat_return
                trade_counts[candidate] += len(selected)
                for event in selected:
                    daily[candidate][to_day(event.timestamp_ns)] += (
                        event.net_r * STAT_RISK_FRAC
                    )
                market_rows.append(
                    {
                        "candidate": candidate,
                        "variation": definition.variation,
                        "train_months": definition.train_months,
                        "market": market,
                        "window": label,
                        "net_r": _format_decimal(net_r),
                        "return": _format_decimal(flat_return),
                        "trades": len(selected),
                    }
                )

    for definition in complete:
        candidate = definition.candidate_id
        daily_total = sum(daily[candidate].values(), Decimal(0))
        window_total = sum(window_returns[candidate].values(), Decimal(0))
        if daily_total != window_total:
            raise AssertionError(
                f"{candidate} daily total {daily_total} != window total {window_total}"
            )
        for label in labels:
            market_total = sum(
                (
                    _decimal(row["return"], label="market-window return")
                    for row in market_rows
                    if row["candidate"] == candidate and row["window"] == label
                ),
                Decimal(0),
            )
            if market_total != window_returns[candidate][label]:
                raise AssertionError(
                    f"{candidate}/{label} market total {market_total} != "
                    f"candidate total {window_returns[candidate][label]}"
                )

    out_dir.mkdir(parents=True, exist_ok=True)
    candidate_ids = [definition.candidate_id for definition in complete]
    _write_csv(
        out_dir / CANDIDATE_DAILY_RETURNS,
        ("loss_day", *candidate_ids),
        (
            {
                "loss_day": _loss_day_iso(day),
                **{
                    candidate: _format_decimal(daily[candidate][day])
                    for candidate in candidate_ids
                },
            }
            for day in days
        ),
    )
    _write_csv(
        out_dir / CANDIDATE_WINDOW_RETURNS,
        ("window", *candidate_ids),
        (
            {
                "window": label,
                **{
                    candidate: _format_decimal(window_returns[candidate][label])
                    for candidate in candidate_ids
                },
            }
            for label in labels
        ),
    )
    _write_csv(
        out_dir / CANDIDATE_MARKET_WINDOW_RETURNS,
        (
            "candidate",
            "variation",
            "train_months",
            "market",
            "window",
            "net_r",
            "return",
            "trades",
        ),
        market_rows,
    )

    manual = tuple(str(item) for item in manual_trials)
    artifacts = hash_paths(
        {name: out_dir / name for name in _STREAM_ARTIFACTS}
    )
    metadata: dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "candidate_definition": ["variation", "train_months"],
        "formal_candidates": [
            {
                "candidate": definition.candidate_id,
                "variation": definition.variation,
                "train_months": definition.train_months,
            }
            for definition in definitions
        ],
        "persisted_candidates": candidate_ids,
        "persisted_candidate_count": len(candidate_ids),
        "excluded_candidates": excluded,
        "trial_counts": {
            "formal": len(definitions),
            "manual": len(manual),
            "total": len(definitions) + len(manual),
        },
        "manual_trials": list(manual),
        "markets": list(expected_markets),
        "common_dates": {
            "first": _loss_day_iso(first_day),
            "last": _loss_day_iso(last_day),
        },
        "common_windows": list(labels),
        "stat_risk_frac": str(STAT_RISK_FRAC),
        "loss_day_axis": LOSS_DAY_AXIS,
        "costs": {
            "statistical_return": "net_r",
            "engine": ["bid_ask_spread", "commission", "slippage"],
            "swap": "realized_at_close",
        },
        "observation_counts": {
            "days": len(days),
            "windows": len(labels),
            "market_window_rows": len(market_rows),
            "trades_by_candidate": trade_counts,
        },
        "source_inputs": dict(source_inputs),
        "artifacts": artifacts,
    }
    (out_dir / CANDIDATE_METADATA).write_text(
        json.dumps(metadata, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return metadata
