"""Behavioural guards for the immutable forward-test cohort registry."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from research.forward_test_registry import (
    LOSS_DAY_AXIS,
    CohortIntegrityError,
    CohortMismatchError,
    CohortPlan,
    CohortStatus,
    ForwardTestRegistry,
    HashedInputPaths,
    Observation,
    ObservationSeries,
    ObservationSource,
    OpaqueIdentifierError,
    cohort_identity,
    hash_cohort_inputs,
    pool_observation_series,
)
from research.stages.lineage import sha256_bytes

_PARTICIPANT_ID = "7f506d66-68e0-4a65-a76d-0d31eb174d98"
_GIT_SHA = "01234567" * 5


def _inputs(root: Path, *, suffix: str = "", stop: str = "0.5") -> HashedInputPaths:
    root.mkdir(parents=True, exist_ok=True)
    values = {
        "strategy_config": "variation=no_bb_wpr",
        "universe": "XAUUSD,EURUSD",
        "stops": f"XAUUSD={stop}",
        "targets": "XAUUSD=3.0",
        "risk": "risk=0.0018",
        "broker_cost_snapshot": '{"spread":"broker-bars","commission":"notional"}',
        "signal_logic": "def signal(): return True",
    }
    paths: dict[str, Path] = {}
    for label, content in values.items():
        path = root / f"{label}{suffix}.txt"
        path.write_text(content, encoding="utf-8")
        paths[label] = path
    return HashedInputPaths(**paths)


def _plan(
    paths: HashedInputPaths, *, participant_id: str = _PARTICIPANT_ID
) -> CohortPlan:
    return CohortPlan(
        start_timestamp=datetime(2026, 7, 16, 21, 15, tzinfo=UTC),
        strategy_code_git_sha=_GIT_SHA,
        inputs=paths,
        participant_id=participant_id,
        observation_source=ObservationSource.LIVE,
        primary_hypothesis="Daily net portfolio R has positive expectation.",
        thresholds={"mean_net_r_gt": Decimal("0"), "max_daily_loss_r": Decimal("-11")},
        minimum_calendar_days=Decimal("180"),
        minimum_trade_count=Decimal("450"),
        allowed_safety_stop_reasons=("daily-limit proximity", "lineage drift"),
        status=CohortStatus.REGISTERED,
    )


def test_changing_one_stop_creates_a_new_cohort(tmp_path: Path) -> None:
    registry = ForwardTestRegistry(tmp_path / "registry")
    first = registry.register(_plan(_inputs(tmp_path / "v1", stop="0.5")))
    second = registry.register(_plan(_inputs(tmp_path / "v2", stop="1.0")))

    assert first.cohort_id != second.cohort_id


def test_input_hashes_match_the_shared_lineage_digest(tmp_path: Path) -> None:
    paths = _inputs(tmp_path / "inputs")
    expected = {
        name: sha256_bytes(getattr(paths, name).read_bytes())
        for name in HashedInputPaths.__dataclass_fields__
    }

    assert hash_cohort_inputs(paths) == expected


def test_cohort_identity_matches_the_canonical_known_vector(tmp_path: Path) -> None:
    hashes = {
        name: "sha256:" + str(index) * 64
        for index, name in enumerate(HashedInputPaths.__dataclass_fields__, start=1)
    }
    expected = "sha256:" + "".join(
        (
            "dc5aa673",
            "03e2760b",
            "c5768833",
            "98d9aaf8",
            "a570be5d",
            "93c21664",
            "12acb26b",
            "c354568b",
        )
    )

    assert cohort_identity(_plan(_inputs(tmp_path / "inputs")), hashes) == expected


def test_cohort_identity_pins_unicode_canonicalization(tmp_path: Path) -> None:
    hashes = {
        name: "sha256:" + str(index) * 64
        for index, name in enumerate(HashedInputPaths.__dataclass_fields__, start=1)
    }
    plan = replace(
        _plan(_inputs(tmp_path / "inputs")),
        primary_hypothesis="Positive daily net portfolio R. \N{SNOWMAN}",
    )
    expected = "sha256:" + "".join(
        (
            "b8f6b2ca",
            "23988e37",
            "e5725858",
            "7d435f17",
            "7d0ac7df",
            "5fc6fe4c",
            "c7e243c3",
            "b16ad5af",
        )
    )

    assert cohort_identity(plan, hashes) == expected


def test_non_path_input_fails_closed_and_names_the_input(tmp_path: Path) -> None:
    paths = _inputs(tmp_path / "inputs")
    invalid = replace(paths, strategy_config=cast(Path, "not-a-path"))

    with pytest.raises(
        FileNotFoundError,
        match=r"strategy_config.*not-a-path",
    ):
        hash_cohort_inputs(invalid)


def test_identical_contents_at_different_paths_keep_the_cohort(tmp_path: Path) -> None:
    registry = ForwardTestRegistry(tmp_path / "registry")
    first = registry.register(_plan(_inputs(tmp_path / "original")))
    second = registry.register(_plan(_inputs(tmp_path / "relocated", suffix="-moved")))

    assert first.cohort_id == second.cohort_id
    assert len(list((tmp_path / "registry" / "cohorts").iterdir())) == 1


def test_changing_signal_code_creates_a_new_cohort(tmp_path: Path) -> None:
    first_paths = _inputs(tmp_path / "v1")
    second_paths = _inputs(tmp_path / "v2")
    second_paths.signal_logic.write_text("def signal(): return False", encoding="utf-8")
    registry = ForwardTestRegistry(tmp_path / "registry")

    assert registry.register(_plan(first_paths)).cohort_id != registry.register(
        _plan(second_paths)
    ).cohort_id


def test_two_cohort_result_sets_cannot_be_pooled(tmp_path: Path) -> None:
    registry = ForwardTestRegistry(tmp_path / "registry")
    first = registry.register(_plan(_inputs(tmp_path / "v1", stop="0.5")))
    second = registry.register(_plan(_inputs(tmp_path / "v2", stop="1.0")))
    registry.append_daily_r(
        first.cohort_id, ObservationSource.LIVE, date(2026, 7, 17), Decimal("0.25")
    )
    registry.append_daily_r(
        second.cohort_id, ObservationSource.LIVE, date(2026, 7, 17), Decimal("0.30")
    )

    with pytest.raises(CohortMismatchError, match="different cohorts"):
        pool_observation_series(
            registry.observations(first.cohort_id),
            registry.observations(second.cohort_id),
        )


def test_live_and_paper_observations_cannot_mix(tmp_path: Path) -> None:
    registry = ForwardTestRegistry(tmp_path / "registry")
    cohort = registry.register(_plan(_inputs(tmp_path / "inputs")))

    with pytest.raises(CohortMismatchError, match="source"):
        registry.append_daily_r(
            cohort.cohort_id,
            ObservationSource.PAPER,
            date(2026, 7, 17),
            Decimal("0.25"),
        )

    live = ObservationSeries(
        cohort.cohort_id,
        ObservationSource.LIVE,
        (Observation(date(2026, 7, 17), Decimal("0.25")),),
    )
    paper = ObservationSeries(
        cohort.cohort_id,
        ObservationSource.PAPER,
        (Observation(date(2026, 7, 18), Decimal("0.10")),),
    )
    with pytest.raises(CohortMismatchError, match="live and paper"):
        pool_observation_series(live, paper)


def test_credentials_and_account_numbers_never_reach_disk(tmp_path: Path) -> None:
    root = tmp_path / "registry"
    registry = ForwardTestRegistry(root)
    registry.register(_plan(_inputs(tmp_path / "valid")))
    synthetic_credential = "sk-" + "synthetic_" + ("x" * 32)
    fake_account_number = "812345678"

    for forbidden in (synthetic_credential, fake_account_number):
        with pytest.raises(OpaqueIdentifierError, match="UUID"):
            registry.register(
                _plan(_inputs(tmp_path / forbidden), participant_id=forbidden)
            )

    written = "\n".join(
        path.read_text(encoding="utf-8") for path in root.rglob("*") if path.is_file()
    )
    assert synthetic_credential not in written
    assert fake_account_number not in written


def test_changed_inputs_create_without_rewriting_the_old_cohort(tmp_path: Path) -> None:
    root = tmp_path / "registry"
    registry = ForwardTestRegistry(root)
    paths = _inputs(tmp_path / "inputs", stop="0.5")
    first = registry.register(_plan(paths))
    old_definition = root / "cohorts" / str(first.cohort_id) / "definition.json"
    before = old_definition.read_bytes()

    paths.stops.write_text("XAUUSD=1.0", encoding="utf-8")
    second = registry.register(_plan(paths))

    assert second.cohort_id != first.cohort_id
    assert old_definition.read_bytes() == before


def test_tampered_cohort_definition_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "registry"
    registry = ForwardTestRegistry(root)
    cohort = registry.register(_plan(_inputs(tmp_path / "inputs")))
    definition = root / "cohorts" / str(cohort.cohort_id) / "definition.json"
    payload = json.loads(definition.read_text(encoding="utf-8"))
    payload["input_hashes"]["stops"] = "sha256:" + ("f" * 64)
    definition.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CohortIntegrityError, match="identity"):
        registry.cohort(cohort.cohort_id)


def test_schema_and_decimal_observation_round_trip_exactly(tmp_path: Path) -> None:
    root = tmp_path / "registry"
    registry = ForwardTestRegistry(root)
    cohort = registry.register(_plan(_inputs(tmp_path / "inputs")))
    value = Decimal("-0.123456789012345678901")
    registry.append_daily_r(
        cohort.cohort_id, ObservationSource.LIVE, date(2026, 7, 17), value
    )

    definition_path = root / "cohorts" / str(cohort.cohort_id) / "definition.json"
    definition = json.loads(definition_path.read_text(encoding="utf-8"))
    required = {
        "cohort_id",
        "start_timestamp",
        "strategy_code_git_sha",
        "input_hashes",
        "participant_id",
        "observation_source",
        "primary_hypothesis",
        "thresholds",
        "minimum_calendar_days",
        "minimum_trade_count",
        "allowed_safety_stop_reasons",
        "status",
        "loss_day_axis",
    }
    assert required <= definition.keys()
    assert definition["loss_day_axis"] == LOSS_DAY_AXIS
    assert definition["minimum_trade_count"] == "450"
    assert isinstance(definition["minimum_trade_count"], str)
    assert UUID(definition["participant_id"]) == UUID(_PARTICIPANT_ID)

    observation_path = definition_path.with_name("observations.jsonl")
    written_observation = json.loads(observation_path.read_text(encoding="utf-8"))
    assert written_observation["daily_net_portfolio_r"] == str(value)
    assert isinstance(written_observation["daily_net_portfolio_r"], str)
    assert written_observation["loss_day_axis"] == LOSS_DAY_AXIS
    assert registry.observations(cohort.cohort_id).observations[0].daily_net_portfolio_r == value


def test_json_number_observation_is_rejected_as_non_decimal_storage(
    tmp_path: Path,
) -> None:
    root = tmp_path / "registry"
    registry = ForwardTestRegistry(root)
    cohort = registry.register(_plan(_inputs(tmp_path / "inputs")))
    registry.append_daily_r(
        cohort.cohort_id,
        ObservationSource.LIVE,
        date(2026, 7, 17),
        Decimal("-0.125"),
    )
    observation_path = (
        root / "cohorts" / str(cohort.cohort_id) / "observations.jsonl"
    )
    payload = json.loads(observation_path.read_text(encoding="utf-8"))
    payload["daily_net_portfolio_r"] = -0.125
    observation_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CohortIntegrityError, match="invalid"):
        registry.observations(cohort.cohort_id)
