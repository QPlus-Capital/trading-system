"""Immutable forward-test cohort registry.

The registry records, but never judges, a forward test. Cohort definitions are content-addressed
and create-only; observations are daily net portfolio R values appended on the prop firm's
16:15 America/Chicago loss-day axis. The P-13 decision protocol is the consumer of this data.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from research.stages.lineage import sha256_bytes, sha256_file

LOSS_DAY_AXIS = "16:15 America/Chicago"
SCHEMA_VERSION = 1
_COHORT_NAMESPACE = UUID("8c79809c-f838-4b50-8b99-1b266b23ab39")
_HASHED_INPUT_NAMES = (
    "strategy_config",
    "universe",
    "stops",
    "targets",
    "risk",
    "broker_cost_snapshot",
    "signal_logic",
)
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_GIT_SHA = re.compile(r"[0-9a-f]{40,64}")


class CohortIntegrityError(ValueError):
    """A persisted cohort definition no longer matches its immutable identity."""


class CohortMismatchError(ValueError):
    """Observations do not belong to one cohort and source."""


class OpaqueIdentifierError(ValueError):
    """A participant identifier is not an opaque UUID."""


class ObservationSource(StrEnum):
    """The mutually exclusive source of a cohort's observations."""

    LIVE = "live"
    PAPER = "paper"


class CohortStatus(StrEnum):
    """Recorded lifecycle state; interpretation belongs to the decision protocol."""

    REGISTERED = "registered"
    ACTIVE = "active"
    COMPLETE = "complete"
    STOPPED = "stopped"


@dataclass(frozen=True)
class HashedInputPaths:
    """Files whose contents define the deployed forward-test configuration."""

    strategy_config: Path
    universe: Path
    stops: Path
    targets: Path
    risk: Path
    broker_cost_snapshot: Path
    signal_logic: Path


@dataclass(frozen=True)
class CohortPlan:
    """Human-approved immutable design used to register one cohort."""

    start_timestamp: datetime
    strategy_code_git_sha: str
    inputs: HashedInputPaths
    participant_id: str
    observation_source: ObservationSource
    primary_hypothesis: str
    thresholds: Mapping[str, Decimal]
    minimum_calendar_days: Decimal
    minimum_trade_count: Decimal
    allowed_safety_stop_reasons: tuple[str, ...]
    status: CohortStatus


@dataclass(frozen=True)
class Cohort:
    """One registered immutable cohort."""

    cohort_id: UUID
    start_timestamp: datetime
    strategy_code_git_sha: str
    input_hashes: dict[str, str]
    participant_id: UUID
    observation_source: ObservationSource
    primary_hypothesis: str
    thresholds: dict[str, Decimal]
    minimum_calendar_days: Decimal
    minimum_trade_count: Decimal
    allowed_safety_stop_reasons: tuple[str, ...]
    status: CohortStatus


@dataclass(frozen=True)
class Observation:
    """One daily net portfolio-R observation."""

    loss_day: date
    daily_net_portfolio_r: Decimal


@dataclass(frozen=True)
class ObservationSeries:
    """Daily observations bound to one cohort and one source."""

    cohort_id: UUID
    source: ObservationSource
    observations: tuple[Observation, ...]


def hash_cohort_inputs(paths: HashedInputPaths) -> dict[str, str]:
    """Hash every cohort input by content through the shared lineage convention."""
    result: dict[str, str] = {}
    for name in _HASHED_INPUT_NAMES:
        path = getattr(paths, name)
        if not isinstance(path, Path) or not path.is_file():
            raise FileNotFoundError(f"cohort input {name!r} is not a file: {path}")
        result[name] = sha256_file(path)
    return result


def cohort_identity(plan: CohortPlan, input_hashes: Mapping[str, str]) -> str:
    """Return a shared-lineage digest of the immutable plan, excluding all file paths."""
    return _digest_canonical(_canonical_plan(plan, input_hashes))


def _digest_canonical(canonical: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        canonical, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode()
    return sha256_bytes(encoded)


class ForwardTestRegistry:
    """Append-only persistence for forward-test cohorts and daily observations."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def register(self, plan: CohortPlan) -> Cohort:
        """Create a cohort once, or return the identical already-registered cohort."""
        hashes = hash_cohort_inputs(plan.inputs)
        identity = cohort_identity(plan, hashes)
        canonical = _canonical_plan(plan, hashes)
        cohort = _cohort_from_canonical(uuid5(_COHORT_NAMESPACE, identity), canonical)
        payload = _serialize_cohort(cohort)
        encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        definition = self._definition_path(cohort.cohort_id)
        definition.parent.mkdir(parents=True, exist_ok=True)
        try:
            with definition.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(encoded)
        except FileExistsError:
            existing = self.cohort(cohort.cohort_id)
            if _serialize_cohort(existing) != payload:
                raise CohortIntegrityError(
                    f"cohort {cohort.cohort_id} already exists with a different definition"
                ) from None
            return existing
        return cohort

    def cohort(self, cohort_id: UUID) -> Cohort:
        """Read and revalidate an immutable cohort definition."""
        definition = self._definition_path(cohort_id)
        try:
            raw = json.loads(definition.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CohortIntegrityError(
                f"cohort {cohort_id} has no readable definition"
            ) from exc
        try:
            cohort = _parse_cohort(raw)
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise CohortIntegrityError(f"cohort {cohort_id} definition is invalid") from exc
        if cohort.cohort_id != cohort_id:
            raise CohortIntegrityError(
                f"cohort directory {cohort_id} contains definition for {cohort.cohort_id}"
            )
        expected = uuid5(_COHORT_NAMESPACE, _identity_from_cohort(cohort))
        if cohort.cohort_id != expected:
            raise CohortIntegrityError(
                f"cohort {cohort_id} identity no longer matches its immutable inputs"
            )
        return cohort

    def append_daily_r(
        self,
        cohort_id: UUID,
        source: ObservationSource,
        loss_day: date,
        daily_net_portfolio_r: Decimal,
    ) -> None:
        """Append one exact daily net-R observation after revalidating its cohort."""
        cohort = self.cohort(cohort_id)
        if not isinstance(source, ObservationSource) or source is not cohort.observation_source:
            raise CohortMismatchError(
                "observation source does not match the cohort's registered source"
            )
        _validate_loss_day(loss_day)
        value = _finite_decimal(daily_net_portfolio_r, "daily_net_portfolio_r")
        existing = self.observations(cohort_id)
        if any(item.loss_day == loss_day for item in existing.observations):
            raise CohortIntegrityError(
                f"cohort {cohort_id} already has an observation for {loss_day.isoformat()}"
            )
        payload = {
            "schema": SCHEMA_VERSION,
            "cohort_id": str(cohort_id),
            "source": source.value,
            "loss_day": loss_day.isoformat(),
            "loss_day_axis": LOSS_DAY_AXIS,
            "daily_net_portfolio_r": str(value),
        }
        observations = self._observation_path(cohort_id)
        with observations.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

    def observations(self, cohort_id: UUID) -> ObservationSeries:
        """Read daily observations only after definition and event identity checks pass."""
        cohort = self.cohort(cohort_id)
        path = self._observation_path(cohort_id)
        if not path.exists():
            return ObservationSeries(cohort_id, cohort.observation_source, ())
        parsed: list[Observation] = []
        seen_days: set[date] = set()
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise CohortIntegrityError(
                f"cohort {cohort_id} observations are not readable"
            ) from exc
        for line_number, line in enumerate(lines, start=1):
            try:
                raw = json.loads(line)
                if int(raw["schema"]) != SCHEMA_VERSION:
                    raise ValueError("unsupported observation schema")
                if UUID(str(raw["cohort_id"])) != cohort_id:
                    raise CohortMismatchError(
                        f"observation line {line_number} belongs to a different cohort"
                    )
                source = ObservationSource(str(raw["source"]))
                if source is not cohort.observation_source:
                    raise CohortMismatchError(
                        f"observation line {line_number} mixes live and paper sources"
                    )
                if raw["loss_day_axis"] != LOSS_DAY_AXIS:
                    raise CohortIntegrityError(
                        f"observation line {line_number} uses a different loss-day axis"
                    )
                loss_day = date.fromisoformat(str(raw["loss_day"]))
                if not isinstance(raw["daily_net_portfolio_r"], str):
                    raise TypeError("daily net portfolio R must be stored as Decimal text")
                value = _finite_decimal(
                    Decimal(raw["daily_net_portfolio_r"]),
                    "daily_net_portfolio_r",
                )
            except CohortMismatchError:
                raise
            except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
                raise CohortIntegrityError(
                    f"cohort {cohort_id} observation line {line_number} is invalid"
                ) from exc
            if loss_day in seen_days:
                raise CohortIntegrityError(
                    f"cohort {cohort_id} repeats loss day {loss_day.isoformat()}"
                )
            seen_days.add(loss_day)
            parsed.append(Observation(loss_day, value))
        return ObservationSeries(
            cohort_id,
            cohort.observation_source,
            tuple(sorted(parsed, key=lambda item: item.loss_day)),
        )

    def _definition_path(self, cohort_id: UUID) -> Path:
        return self.root / "cohorts" / str(cohort_id) / "definition.json"

    def _observation_path(self, cohort_id: UUID) -> Path:
        return self._definition_path(cohort_id).with_name("observations.jsonl")


def pool_observation_series(*series: ObservationSeries) -> ObservationSeries:
    """Combine result fragments only when cohort and source are identical."""
    if not series:
        raise ValueError("at least one observation series is required")
    cohort_ids = {item.cohort_id for item in series}
    if len(cohort_ids) != 1:
        raise CohortMismatchError("results from different cohorts cannot be pooled")
    sources = {item.source for item in series}
    if len(sources) != 1:
        raise CohortMismatchError("live and paper observations cannot be pooled")
    observations = tuple(
        observation for fragment in series for observation in fragment.observations
    )
    days = [item.loss_day for item in observations]
    if len(days) != len(set(days)):
        raise CohortIntegrityError("pooled observation series repeat a loss day")
    return ObservationSeries(
        series[0].cohort_id,
        series[0].source,
        tuple(sorted(observations, key=lambda item: item.loss_day)),
    )


def _finite_decimal(value: Decimal, label: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise TypeError(f"{label} must be a finite Decimal")
    return value


def _positive_integral_decimal(value: Decimal, label: str) -> Decimal:
    checked = _finite_decimal(value, label)
    if checked <= 0 or checked != checked.to_integral_value():
        raise ValueError(f"{label} must be a positive integral Decimal")
    return checked


def _opaque_uuid(value: str) -> UUID:
    if not isinstance(value, str):
        raise OpaqueIdentifierError("participant identifier must be a canonical UUID")
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise OpaqueIdentifierError("participant identifier must be a canonical UUID") from exc
    if parsed.int == 0 or str(parsed) != value.lower():
        raise OpaqueIdentifierError("participant identifier must be a canonical non-zero UUID")
    return parsed


def _aware_timestamp(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("cohort start_timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _timestamp_text(value: datetime) -> str:
    return _aware_timestamp(value).isoformat().replace("+00:00", "Z")


def _validate_loss_day(value: date) -> None:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise TypeError("loss_day must be a date")


def _validated_hashes(input_hashes: Mapping[str, str]) -> dict[str, str]:
    if set(input_hashes) != set(_HASHED_INPUT_NAMES):
        raise ValueError(f"input hashes must contain exactly {_HASHED_INPUT_NAMES!r}")
    result = {name: str(input_hashes[name]) for name in _HASHED_INPUT_NAMES}
    if any(_SHA256.fullmatch(value) is None for value in result.values()):
        raise ValueError("every cohort input must use the shared sha256:<hex> format")
    return result


def _validated_thresholds(thresholds: Mapping[str, Decimal]) -> dict[str, str]:
    if not thresholds:
        raise ValueError("primary hypothesis thresholds cannot be empty")
    result: dict[str, str] = {}
    for name, value in sorted(thresholds.items()):
        cleaned = str(name).strip()
        if not cleaned or cleaned in result:
            raise ValueError("threshold names must be non-empty and unique")
        result[cleaned] = str(_finite_decimal(value, f"threshold {cleaned!r}"))
    return result


def _validated_reasons(reasons: tuple[str, ...]) -> list[str]:
    cleaned = sorted({reason.strip() for reason in reasons if reason.strip()})
    if len(cleaned) != len(reasons):
        raise ValueError("allowed safety-stop reasons must be non-empty and unique")
    return cleaned


def _canonical_plan(plan: CohortPlan, input_hashes: Mapping[str, str]) -> dict[str, Any]:
    if _GIT_SHA.fullmatch(plan.strategy_code_git_sha) is None:
        raise ValueError("strategy_code_git_sha must be a full hexadecimal git SHA")
    hypothesis = plan.primary_hypothesis.strip()
    if not hypothesis:
        raise ValueError("primary_hypothesis cannot be empty")
    if not isinstance(plan.observation_source, ObservationSource):
        raise TypeError("observation_source must be live or paper")
    if not isinstance(plan.status, CohortStatus):
        raise TypeError("status must be a CohortStatus")
    return {
        "start_timestamp": _timestamp_text(plan.start_timestamp),
        "strategy_code_git_sha": plan.strategy_code_git_sha,
        "input_hashes": _validated_hashes(input_hashes),
        "participant_id": str(_opaque_uuid(plan.participant_id)),
        "observation_source": plan.observation_source.value,
        "primary_hypothesis": hypothesis,
        "thresholds": _validated_thresholds(plan.thresholds),
        "minimum_calendar_days": str(
            _positive_integral_decimal(plan.minimum_calendar_days, "minimum_calendar_days")
        ),
        "minimum_trade_count": str(
            _positive_integral_decimal(plan.minimum_trade_count, "minimum_trade_count")
        ),
        "allowed_safety_stop_reasons": _validated_reasons(
            plan.allowed_safety_stop_reasons
        ),
        "status": plan.status.value,
        "loss_day_axis": LOSS_DAY_AXIS,
    }


def _cohort_from_canonical(cohort_id: UUID, canonical: Mapping[str, Any]) -> Cohort:
    return Cohort(
        cohort_id=cohort_id,
        start_timestamp=datetime.fromisoformat(
            str(canonical["start_timestamp"]).replace("Z", "+00:00")
        ),
        strategy_code_git_sha=str(canonical["strategy_code_git_sha"]),
        input_hashes=dict(canonical["input_hashes"]),
        participant_id=UUID(str(canonical["participant_id"])),
        observation_source=ObservationSource(str(canonical["observation_source"])),
        primary_hypothesis=str(canonical["primary_hypothesis"]),
        thresholds={
            str(name): Decimal(str(value))
            for name, value in dict(canonical["thresholds"]).items()
        },
        minimum_calendar_days=Decimal(str(canonical["minimum_calendar_days"])),
        minimum_trade_count=Decimal(str(canonical["minimum_trade_count"])),
        allowed_safety_stop_reasons=tuple(canonical["allowed_safety_stop_reasons"]),
        status=CohortStatus(str(canonical["status"])),
    )


def _serialize_cohort(cohort: Cohort) -> dict[str, Any]:
    return {
        "schema": SCHEMA_VERSION,
        "cohort_id": str(cohort.cohort_id),
        **_canonical_from_cohort(cohort),
    }


def _canonical_from_cohort(cohort: Cohort) -> dict[str, Any]:
    return {
        "start_timestamp": _timestamp_text(cohort.start_timestamp),
        "strategy_code_git_sha": cohort.strategy_code_git_sha,
        "input_hashes": _validated_hashes(cohort.input_hashes),
        "participant_id": str(cohort.participant_id),
        "observation_source": cohort.observation_source.value,
        "primary_hypothesis": cohort.primary_hypothesis,
        "thresholds": {
            name: str(value) for name, value in sorted(cohort.thresholds.items())
        },
        "minimum_calendar_days": str(cohort.minimum_calendar_days),
        "minimum_trade_count": str(cohort.minimum_trade_count),
        "allowed_safety_stop_reasons": list(cohort.allowed_safety_stop_reasons),
        "status": cohort.status.value,
        "loss_day_axis": LOSS_DAY_AXIS,
    }


def _identity_from_cohort(cohort: Cohort) -> str:
    return _digest_canonical(_canonical_from_cohort(cohort))


def _parse_cohort(raw: object) -> Cohort:
    if not isinstance(raw, dict) or int(raw["schema"]) != SCHEMA_VERSION:
        raise ValueError("unsupported cohort schema")
    if raw["loss_day_axis"] != LOSS_DAY_AXIS:
        raise ValueError("unsupported loss-day axis")
    cohort = Cohort(
        cohort_id=UUID(str(raw["cohort_id"])),
        start_timestamp=datetime.fromisoformat(
            str(raw["start_timestamp"]).replace("Z", "+00:00")
        ),
        strategy_code_git_sha=str(raw["strategy_code_git_sha"]),
        input_hashes=_validated_hashes(dict(raw["input_hashes"])),
        participant_id=_opaque_uuid(str(raw["participant_id"])),
        observation_source=ObservationSource(str(raw["observation_source"])),
        primary_hypothesis=str(raw["primary_hypothesis"]),
        thresholds={
            str(name): _finite_decimal(Decimal(str(value)), f"threshold {name!r}")
            for name, value in dict(raw["thresholds"]).items()
        },
        minimum_calendar_days=_positive_integral_decimal(
            Decimal(str(raw["minimum_calendar_days"])), "minimum_calendar_days"
        ),
        minimum_trade_count=_positive_integral_decimal(
            Decimal(str(raw["minimum_trade_count"])), "minimum_trade_count"
        ),
        allowed_safety_stop_reasons=tuple(
            str(reason) for reason in raw["allowed_safety_stop_reasons"]
        ),
        status=CohortStatus(str(raw["status"])),
    )
    if _canonical_from_cohort(cohort) != {
        key: value for key, value in raw.items() if key not in {"schema", "cohort_id"}
    }:
        raise ValueError("cohort definition is not canonical")
    return cohort
