"""Behavioural guards for the fixed forward-test decision protocol."""

from __future__ import annotations

import ast
import inspect
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
import research.forward_decision as decision_module
from research.forward_decision import (
    DEFAULT_REPLICATIONS,
    DEFAULT_SEED,
    EFFICACY_MONTHS,
    EFFICACY_TRADES,
    FUTILITY_CONFIDENCE,
    FUTILITY_MONTHS,
    FUTILITY_TRADES,
    DecisionState,
    MeanBounds,
    bootstrap_mean_bounds,
    daily_threshold,
    endpoint_reached,
    evaluate_forward_test,
)
from research.forward_test_registry import (
    Cohort,
    CohortPlan,
    CohortStatus,
    ForwardTestRegistry,
    HashedInputPaths,
    Observation,
    ObservationSeries,
    ObservationSource,
)
from research.portfolio.resample import SENSITIVITY_BLOCK_LENGTHS

_COHORT_ID = UUID("2bb0ced9-ea09-45e2-bdf1-da7478bc7c43")
_START = datetime(2024, 1, 31, 21, 15, tzinfo=UTC)


class _Registry:
    def __init__(self, cohort: Cohort, observations: tuple[Observation, ...]) -> None:
        self._cohort = cohort
        self._series = ObservationSeries(
            cohort.cohort_id,
            cohort.observation_source,
            observations,
        )

    def cohort(self, cohort_id: UUID) -> Cohort:
        assert cohort_id == self._cohort.cohort_id
        return self._cohort

    def observations(self, cohort_id: UUID) -> ObservationSeries:
        assert cohort_id == self._cohort.cohort_id
        return self._series


def _cohort(*, status: CohortStatus = CohortStatus.ACTIVE) -> Cohort:
    return Cohort(
        cohort_id=_COHORT_ID,
        start_timestamp=_START,
        strategy_code_git_sha="01234567" * 5,
        input_hashes={"signal_logic": "sha256:" + ("1" * 64)},
        participant_id=UUID("7f506d66-68e0-4a65-a76d-0d31eb174d98"),
        observation_source=ObservationSource.PAPER,
        primary_hypothesis="Mean net R exceeds the fixed edge threshold.",
        thresholds={"mean_net_r_per_trade": Decimal("0.10")},
        minimum_calendar_days=Decimal("913"),
        minimum_trade_count=EFFICACY_TRADES,
        allowed_safety_stop_reasons=("hard account limit",),
        status=status,
    )


def _observations(
    values: tuple[Decimal, ...] = (
        Decimal("0.20"),
        Decimal("-0.10"),
        Decimal("0.30"),
        Decimal("0"),
    ),
) -> tuple[Observation, ...]:
    return tuple(
        Observation(_START.date() + timedelta(days=index), value)
        for index, value in enumerate(values)
    )


def _registry(
    *,
    values: tuple[Decimal, ...] = (
        Decimal("0.20"),
        Decimal("-0.10"),
        Decimal("0.30"),
        Decimal("0"),
    ),
    status: CohortStatus = CohortStatus.ACTIVE,
) -> ForwardTestRegistry:
    return cast(ForwardTestRegistry, _Registry(_cohort(status=status), _observations(values)))


def _registered_plan(root: Path, status: CohortStatus) -> CohortPlan:
    inputs_root = root / "inputs"
    inputs_root.mkdir(exist_ok=True)
    paths: dict[str, Path] = {}
    for name in HashedInputPaths.__dataclass_fields__:
        path = inputs_root / name
        path.write_text(f"fixed {name}\n", encoding="utf-8")
        paths[name] = path
    return CohortPlan(
        start_timestamp=_START,
        strategy_code_git_sha="01234567" * 5,
        inputs=HashedInputPaths(**paths),
        participant_id="7f506d66-68e0-4a65-a76d-0d31eb174d98",
        observation_source=ObservationSource.PAPER,
        primary_hypothesis="Mean net R exceeds the fixed edge threshold.",
        thresholds={"mean_net_r_per_trade": Decimal("0.10")},
        minimum_calendar_days=Decimal("913"),
        minimum_trade_count=EFFICACY_TRADES,
        allowed_safety_stop_reasons=("hard account limit",),
        status=status,
    )


def _at_month(months: int, *, day_offset: int = 0) -> date:
    year = _START.year + (_START.month - 1 + months) // 12
    month = (_START.month - 1 + months) % 12 + 1
    month_end = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
    return date(year, month, min(_START.day, month_end.day)) + timedelta(days=day_offset)


def _fixed_bounds(lower: str, upper: str) -> MeanBounds:
    return MeanBounds(
        mean_daily_net_r=Decimal("0.20"),
        lower=Decimal(lower),
        upper=Decimal(upper),
    )


def _patch_bounds(
    monkeypatch: pytest.MonkeyPatch,
    *,
    lower: str,
    upper: str,
    selected_block: int = 7,
) -> list[tuple[int, Decimal, tuple[Decimal, ...]]]:
    calls: list[tuple[int, Decimal, tuple[Decimal, ...]]] = []

    def fake_select(candidate_returns: object) -> int:
        assert candidate_returns
        return selected_block

    def fake_bounds(
        values: tuple[Decimal, ...],
        mean_block_length: int,
        confidence: Decimal,
        *,
        replications: int = DEFAULT_REPLICATIONS,
        seed: int = DEFAULT_SEED,
    ) -> MeanBounds:
        assert replications > 0
        assert seed == DEFAULT_SEED
        calls.append((mean_block_length, confidence, values))
        return _fixed_bounds(lower, upper)

    monkeypatch.setattr(decision_module, "select_block_length", fake_select)
    monkeypatch.setattr(decision_module, "bootstrap_mean_bounds", fake_bounds)
    return calls


@pytest.mark.parametrize(
    ("as_of", "trades"),
    [
        (_at_month(EFFICACY_MONTHS, day_offset=-1), EFFICACY_TRADES),
        (_at_month(EFFICACY_MONTHS), EFFICACY_TRADES - Decimal("1")),
        (_at_month(EFFICACY_MONTHS, day_offset=-1), EFFICACY_TRADES - Decimal("1")),
    ],
)
def test_efficacy_is_suppressed_until_both_endpoint_conditions_hold(
    monkeypatch: pytest.MonkeyPatch,
    as_of: date,
    trades: Decimal,
) -> None:
    calls = _patch_bounds(monkeypatch, lower="0.20", upper="0.30")

    result = evaluate_forward_test(_registry(), _COHORT_ID, trades, as_of)

    assert result.state is DecisionState.NO_DECISION
    assert result.efficacy is None
    assert result.futility is None
    assert all(confidence == FUTILITY_CONFIDENCE for _, confidence, _ in calls)


@pytest.mark.parametrize(
    ("lower", "upper", "expected"),
    [
        ("24.001", "25.000", DecisionState.PASS),
        ("-0.500", "23.999", DecisionState.FAIL),
        ("23.000", "25.000", DecisionState.INCONCLUSIVE),
    ],
)
def test_completed_cohort_classifies_pass_fail_and_inconclusive(
    monkeypatch: pytest.MonkeyPatch,
    lower: str,
    upper: str,
    expected: DecisionState,
) -> None:
    _patch_bounds(monkeypatch, lower=lower, upper=upper)

    result = evaluate_forward_test(
        _registry(values=(Decimal("0.20"),) * 10),
        _COHORT_ID,
        EFFICACY_TRADES,
        _at_month(EFFICACY_MONTHS),
    )

    assert result.state is expected
    assert result.efficacy is not None
    assert result.efficacy.daily_threshold == Decimal("24.00")


def test_equality_is_inconclusive(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_bounds(monkeypatch, lower="24.00", upper="24.00")
    result = evaluate_forward_test(
        _registry(values=(Decimal("0.20"),) * 10),
        _COHORT_ID,
        EFFICACY_TRADES,
        _at_month(EFFICACY_MONTHS),
    )
    assert result.state is DecisionState.INCONCLUSIVE


@pytest.mark.parametrize(
    ("as_of", "trades", "upper", "expected"),
    [
        (_at_month(FUTILITY_MONTHS, day_offset=-1), FUTILITY_TRADES, "-0.01", False),
        (_at_month(FUTILITY_MONTHS), FUTILITY_TRADES - Decimal("1"), "-0.01", False),
        (_at_month(FUTILITY_MONTHS), FUTILITY_TRADES, "0.01", False),
        (_at_month(FUTILITY_MONTHS), FUTILITY_TRADES, "-0.01", True),
    ],
)
def test_futility_requires_both_interim_conditions_and_upper_99_below_zero(
    monkeypatch: pytest.MonkeyPatch,
    as_of: date,
    trades: Decimal,
    upper: str,
    expected: bool,
) -> None:
    calls = _patch_bounds(monkeypatch, lower="-0.50", upper=upper)

    result = evaluate_forward_test(_registry(), _COHORT_ID, trades, as_of)

    assert (result.state is DecisionState.FUTILITY_STOP) is expected
    assert (result.futility is not None) is expected
    assert result.efficacy is None
    if calls:
        assert {confidence for _, confidence, _ in calls} == {Decimal("0.99")}


def test_futility_equality_does_not_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_bounds(monkeypatch, lower="-0.50", upper="0")
    result = evaluate_forward_test(
        _registry(),
        _COHORT_ID,
        FUTILITY_TRADES,
        _at_month(FUTILITY_MONTHS),
    )
    assert result.state is DecisionState.NO_DECISION
    assert result.futility is None


def test_daily_threshold_is_exact_decimal_and_rejects_invalid_counts() -> None:
    assert daily_threshold(Decimal("2400"), Decimal("913")) == (
        Decimal("0.10") * Decimal("2400") / Decimal("913")
    )
    with pytest.raises(ValueError, match="observation_day_count"):
        daily_threshold(Decimal("1"), Decimal("0"))
    for invalid in (
        Decimal("-1"),
        Decimal("1.5"),
        Decimal("NaN"),
        Decimal("Infinity"),
    ):
        with pytest.raises((TypeError, ValueError), match="realized_trade_count"):
            daily_threshold(invalid, Decimal("1"))
    with pytest.raises(TypeError, match="finite Decimal"):
        daily_threshold(cast(Decimal, 1), Decimal("1"))


def test_selected_block_and_all_sensitivity_lengths_are_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_bounds(monkeypatch, lower="24.001", upper="25.00", selected_block=7)

    result = evaluate_forward_test(
        _registry(values=(Decimal("0.20"),) * 10),
        _COHORT_ID,
        EFFICACY_TRADES,
        _at_month(EFFICACY_MONTHS),
        replications=31,
    )

    assert result.efficacy is not None
    assert result.efficacy.production.block_length == 7
    assert tuple(item.block_length for item in result.efficacy.sensitivity) == (
        SENSITIVITY_BLOCK_LENGTHS
    )
    assert {block for block, _, _ in calls} == {7, *SENSITIVITY_BLOCK_LENGTHS}
    assert {confidence for _, confidence, _ in calls} == {Decimal("0.95")}


def test_public_defaults_match_p04() -> None:
    parameters = inspect.signature(evaluate_forward_test).parameters
    assert parameters["replications"].default == 10_000
    assert parameters["seed"].default == 20260719
    assert DEFAULT_REPLICATIONS == 10_000
    assert DEFAULT_SEED == 20260719
    assert Decimal("2400") == EFFICACY_TRADES
    assert Decimal("1400") == FUTILITY_TRADES


def test_as_of_cutoff_excludes_later_observations(monkeypatch: pytest.MonkeyPatch) -> None:
    values = (
        Decimal("0.10"),
        Decimal("0.20"),
        Decimal("99.0"),
    )
    calls = _patch_bounds(monkeypatch, lower="0.20", upper="0.30")
    as_of = _START.date() + timedelta(days=1)
    old_cohort = replace(_cohort(), start_timestamp=datetime(2020, 1, 1, tzinfo=UTC))
    old_registry = cast(
        ForwardTestRegistry,
        _Registry(old_cohort, _observations(values)),
    )

    evaluate_forward_test(
        old_registry,
        _COHORT_ID,
        EFFICACY_TRADES,
        as_of,
    )

    assert calls
    assert all(call_values == values[:2] for _, _, call_values in calls)


def test_invalid_temporal_and_series_inputs_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_bounds(monkeypatch, lower="0.10", upper="0.20")
    with pytest.raises(ValueError, match="before cohort start"):
        evaluate_forward_test(
            _registry(),
            _COHORT_ID,
            Decimal("0"),
            _START.date() - timedelta(days=1),
        )

    before_start = Observation(_START.date() - timedelta(days=1), Decimal("0"))
    invalid_registry = cast(
        ForwardTestRegistry,
        _Registry(_cohort(), (before_start,)),
    )
    with pytest.raises(ValueError, match="before cohort start"):
        evaluate_forward_test(
            invalid_registry,
            _COHORT_ID,
            EFFICACY_TRADES,
            _at_month(EFFICACY_MONTHS),
        )

    wrong_source = _Registry(_cohort(), _observations())
    wrong_source._series = replace(wrong_source._series, source=ObservationSource.LIVE)
    with pytest.raises(ValueError, match="source"):
        evaluate_forward_test(
            cast(ForwardTestRegistry, wrong_source),
            _COHORT_ID,
            EFFICACY_TRADES,
            _at_month(EFFICACY_MONTHS),
        )


def test_operational_stop_does_not_change_statistics_or_registry_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_bounds(monkeypatch, lower="61", upper="70")
    registry = ForwardTestRegistry(tmp_path / "registry")
    active_cohort = registry.register(_registered_plan(tmp_path, CohortStatus.ACTIVE))
    stopped_cohort = registry.register(_registered_plan(tmp_path, CohortStatus.STOPPED))
    for cohort in (active_cohort, stopped_cohort):
        for observation in _observations():
            registry.append_daily_r(
                cohort.cohort_id,
                ObservationSource.PAPER,
                observation.loss_day,
                observation.daily_net_portfolio_r,
            )
    before = {
        path.relative_to(registry.root): path.read_bytes()
        for path in registry.root.rglob("*")
        if path.is_file()
    }

    active = evaluate_forward_test(
        registry,
        active_cohort.cohort_id,
        EFFICACY_TRADES,
        _at_month(EFFICACY_MONTHS),
    )
    stopped = evaluate_forward_test(
        registry,
        stopped_cohort.cohort_id,
        EFFICACY_TRADES,
        _at_month(EFFICACY_MONTHS),
    )
    after = {
        path.relative_to(registry.root): path.read_bytes()
        for path in registry.root.rglob("*")
        if path.is_file()
    }

    assert active.state is stopped.state is DecisionState.PASS
    assert active.efficacy == stopped.efficacy
    assert active.cohort_status is CohortStatus.ACTIVE
    assert stopped.cohort_status is CohortStatus.STOPPED
    assert after == before


def test_no_pre_endpoint_return_path_exposes_efficacy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_bounds(monkeypatch, lower="99", upper="100")
    for months in range(EFFICACY_MONTHS):
        result = evaluate_forward_test(
            _registry(),
            _COHORT_ID,
            EFFICACY_TRADES + Decimal("1000"),
            _at_month(months),
        )
        assert result.state not in {DecisionState.PASS, DecisionState.FAIL}
        assert result.efficacy is None


def test_dashboard_has_no_forward_decision_consumer() -> None:
    dashboard = Path("monitoring/dashboard.py")
    tree = ast.parse(dashboard.read_text(encoding="utf-8"), filename=str(dashboard))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert "research.forward_decision" not in imported


def test_decision_statistics_are_decimal_and_source_has_no_float_statistics() -> None:
    bounds = bootstrap_mean_bounds(
        (Decimal("0.10"), Decimal("-0.20"), Decimal("0.30")),
        1,
        Decimal("0.95"),
        replications=31,
        seed=17,
    )
    assert isinstance(bounds.mean_daily_net_r, Decimal)
    assert isinstance(bounds.lower, Decimal)
    assert isinstance(bounds.upper, Decimal)

    source = Path("research/forward_decision.py")
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    assert not any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "float"
        for node in ast.walk(tree)
    )
    assert not any(
        isinstance(node, ast.Constant) and isinstance(node.value, float) for node in ast.walk(tree)
    )


def test_bootstrap_bounds_are_seeded_and_input_is_not_mutated() -> None:
    values = (Decimal("0.10"), Decimal("-0.20"), Decimal("0.30"), Decimal("0"))
    first = bootstrap_mean_bounds(
        values,
        2,
        Decimal("0.95"),
        replications=53,
        seed=91,
    )
    second = bootstrap_mean_bounds(
        values,
        2,
        Decimal("0.95"),
        replications=53,
        seed=91,
    )
    assert first == second
    assert values == (Decimal("0.10"), Decimal("-0.20"), Decimal("0.30"), Decimal("0"))


def test_sensitivity_cannot_change_the_production_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_select(candidate_returns: object) -> int:
        assert candidate_returns
        return 7

    def fake_bounds(
        values: tuple[Decimal, ...],
        mean_block_length: int,
        confidence: Decimal,
        *,
        replications: int = DEFAULT_REPLICATIONS,
        seed: int = DEFAULT_SEED,
    ) -> MeanBounds:
        del values, confidence, replications, seed
        return _fixed_bounds("61", "70") if mean_block_length == 7 else _fixed_bounds("-1", "59")

    monkeypatch.setattr(decision_module, "select_block_length", fake_select)
    monkeypatch.setattr(decision_module, "bootstrap_mean_bounds", fake_bounds)

    result = evaluate_forward_test(
        _registry(),
        _COHORT_ID,
        EFFICACY_TRADES,
        _at_month(EFFICACY_MONTHS),
    )

    assert result.state is DecisionState.PASS
    assert result.efficacy is not None
    assert all(
        item.bounds.upper < result.efficacy.daily_threshold for item in result.efficacy.sensitivity
    )


def test_calendar_month_end_boundaries_are_exact() -> None:
    assert not endpoint_reached(_START, date(2026, 7, 30), EFFICACY_TRADES)
    assert endpoint_reached(_START, date(2026, 7, 31), EFFICACY_TRADES)
    leap_start = datetime(2024, 2, 29, tzinfo=UTC)
    assert not endpoint_reached(leap_start, date(2026, 8, 28), EFFICACY_TRADES)
    assert endpoint_reached(leap_start, date(2026, 8, 29), EFFICACY_TRADES)
