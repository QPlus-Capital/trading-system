"""Behavioural guards for the fixed forward-test decision protocol."""

from __future__ import annotations

import ast
import inspect
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, tzinfo
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import UUID

import numpy as np
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
        assert isinstance(candidate_returns, dict)
        assert len(candidate_returns) == 1
        candidate = next(iter(candidate_returns))
        assert candidate.startswith("cohort:")
        UUID(candidate.removeprefix("cohort:"))
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

    with pytest.raises(ValueError) as invalid_trades:
        daily_threshold(Decimal("-1"), Decimal("1"))
    assert str(invalid_trades.value) == (
        "realized_trade_count must be a non-negative integral Decimal"
    )
    with pytest.raises(ValueError) as invalid_days:
        daily_threshold(Decimal("1"), Decimal("0"))
    assert str(invalid_days.value) == ("observation_day_count must be a positive integral Decimal")


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


def test_calendar_and_endpoint_validation_fail_closed_with_exact_diagnostics() -> None:
    with pytest.raises(ValueError) as invalid_start:
        decision_module._calendar_anniversary(cast(datetime, date(2024, 1, 1)), 1)
    assert str(invalid_start.value) == "cohort start_timestamp must be timezone-aware"

    with pytest.raises(ValueError) as naive_start:
        decision_module._calendar_anniversary(datetime(2024, 1, 1), 1)
    assert str(naive_start.value) == "cohort start_timestamp must be timezone-aware"

    class _IndeterminateTimezone(tzinfo):
        def utcoffset(self, value: datetime | None) -> None:
            del value
            return None

        def dst(self, value: datetime | None) -> None:
            del value
            return None

        def tzname(self, value: datetime | None) -> str:
            del value
            return "indeterminate"

    with pytest.raises(ValueError) as indeterminate_start:
        decision_module._calendar_anniversary(
            datetime(2024, 1, 1, tzinfo=_IndeterminateTimezone()),
            1,
        )
    assert str(indeterminate_start.value) == "cohort start_timestamp must be timezone-aware"

    for months in (cast(int, True), -1, cast(int, Decimal("1"))):
        with pytest.raises(ValueError) as invalid_months:
            decision_module._calendar_anniversary(_START, months)
        assert str(invalid_months.value) == "months must be a non-negative integer"

    assert decision_module._calendar_anniversary(_START, 12) == date(2025, 1, 31)

    with pytest.raises(TypeError) as invalid_as_of:
        endpoint_reached(
            _START,
            cast(date, datetime(2026, 7, 31, tzinfo=UTC)),
            EFFICACY_TRADES,
        )
    assert str(invalid_as_of.value) == "as_of_date must be a date"

    with pytest.raises(ValueError) as invalid_endpoint_trades:
        endpoint_reached(_START, date(2026, 7, 31), Decimal("-1"))
    assert str(invalid_endpoint_trades.value) == (
        "realized_trade_count must be a non-negative integral Decimal"
    )


def test_nearest_rank_pins_boundaries_and_ceiling_rule() -> None:
    values = tuple(Decimal(index) for index in range(1, 11))
    assert decision_module._nearest_rank(values, Decimal("0.01")) == Decimal("1")
    assert decision_module._nearest_rank(values, Decimal("0.21")) == Decimal("3")

    with pytest.raises(ValueError) as empty:
        decision_module._nearest_rank((), Decimal("0.5"))
    assert str(empty.value) == "quantile values must be non-empty"

    for probability in (
        Decimal("-0.1"),
        Decimal("0"),
        Decimal("1"),
        Decimal("1.1"),
    ):
        with pytest.raises(ValueError) as invalid:
            decision_module._nearest_rank(values, probability)
        assert str(invalid.value) == "probability must be strictly between zero and one"

    with pytest.raises(TypeError) as non_decimal:
        decision_module._nearest_rank(values, cast(Decimal, 1))
    assert str(non_decimal.value) == "probability must be a finite Decimal"


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

    wrong_cohort = _Registry(_cohort(), _observations())
    wrong_cohort._series = replace(
        wrong_cohort._series,
        cohort_id=UUID("3c203d4d-e505-46c2-a740-ed74f957dd58"),
    )
    with pytest.raises(ValueError, match="different cohort"):
        evaluate_forward_test(
            cast(ForwardTestRegistry, wrong_cohort),
            _COHORT_ID,
            EFFICACY_TRADES,
            _at_month(EFFICACY_MONTHS),
        )

    repeated = (_observations()[0], _observations()[0])
    with pytest.raises(ValueError, match="repeats"):
        evaluate_forward_test(
            cast(ForwardTestRegistry, _Registry(_cohort(), repeated)),
            _COHORT_ID,
            EFFICACY_TRADES,
            _at_month(EFFICACY_MONTHS),
        )

    non_finite = (Observation(_START.date(), Decimal("NaN")),)
    with pytest.raises(TypeError, match="finite Decimal"):
        evaluate_forward_test(
            cast(ForwardTestRegistry, _Registry(_cohort(), non_finite)),
            _COHORT_ID,
            EFFICACY_TRADES,
            _at_month(EFFICACY_MONTHS),
        )

    with pytest.raises(ValueError, match="observation_day_count"):
        evaluate_forward_test(
            cast(ForwardTestRegistry, _Registry(_cohort(), ())),
            _COHORT_ID,
            EFFICACY_TRADES,
            _at_month(EFFICACY_MONTHS),
        )


def test_evaluation_validates_external_inputs_with_exact_diagnostics() -> None:
    with pytest.raises(ValueError) as invalid_trades:
        evaluate_forward_test(
            _registry(),
            _COHORT_ID,
            Decimal("-1"),
            _START.date(),
        )
    assert str(invalid_trades.value) == (
        "realized_trade_count must be a non-negative integral Decimal"
    )

    with pytest.raises(ValueError) as invalid_replications:
        evaluate_forward_test(
            _registry(),
            _COHORT_ID,
            Decimal("0"),
            _START.date(),
            replications=0,
        )
    assert str(invalid_replications.value) == "replications must be a positive integer"

    with pytest.raises(TypeError) as invalid_as_of:
        evaluate_forward_test(
            _registry(),
            _COHORT_ID,
            Decimal("0"),
            cast(date, _START),
        )
    assert str(invalid_as_of.value) == "as_of_date must be a date"

    with pytest.raises(ValueError) as before_start:
        evaluate_forward_test(
            _registry(),
            _COHORT_ID,
            Decimal("0"),
            _START.date() - timedelta(days=1),
        )
    assert str(before_start.value) == "as_of_date is before cohort start"


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


def test_bootstrap_mean_bounds_pins_decimal_arithmetic_and_quantiles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fixed_bootstrap(*args: object, **kwargs: object) -> np.ndarray:
        assert args == (range(0, 2), 1)
        assert kwargs == {"replications": 2, "seed": 91}
        return np.array([[0, 1], [1, 1]], dtype=np.int64)

    monkeypatch.setattr(decision_module, "stationary_bootstrap", fixed_bootstrap)
    bounds = bootstrap_mean_bounds(
        (Decimal("1"), Decimal("3")),
        1,
        Decimal("0.75"),
        replications=2,
        seed=91,
    )
    assert bounds == MeanBounds(
        mean_daily_net_r=Decimal("2"),
        lower=Decimal("2"),
        upper=Decimal("3"),
    )


@pytest.mark.parametrize(
    "indices",
    [
        np.array([[Decimal("-1"), Decimal("0")]], dtype=object),
        np.array([[Decimal("2"), Decimal("0")]], dtype=object),
        np.array([[Decimal("0.5"), Decimal("0")]], dtype=object),
    ],
)
def test_bootstrap_mean_bounds_rejects_invalid_resample_indices(
    monkeypatch: pytest.MonkeyPatch,
    indices: np.ndarray,
) -> None:
    monkeypatch.setattr(
        decision_module,
        "stationary_bootstrap",
        lambda *args, **kwargs: indices,
    )
    with pytest.raises(RuntimeError) as invalid:
        bootstrap_mean_bounds(
            (Decimal("1"), Decimal("3")),
            1,
            Decimal("0.95"),
            replications=1,
        )
    assert str(invalid.value) == "stationary bootstrap returned a non-integral index"


def test_bootstrap_mean_bounds_validates_public_inputs_exactly() -> None:
    values = (Decimal("0"), Decimal("1"))
    for block_length in (0, -1, cast(int, True)):
        with pytest.raises(ValueError) as invalid_block:
            bootstrap_mean_bounds(values, block_length, Decimal("0.95"), replications=1)
        assert str(invalid_block.value) == "mean_block_length must be a positive integer"

    for replications in (0, -1, cast(int, True)):
        with pytest.raises(ValueError) as invalid_replications:
            bootstrap_mean_bounds(values, 1, Decimal("0.95"), replications=replications)
        assert str(invalid_replications.value) == "replications must be a positive integer"

    for confidence in (
        Decimal("-0.1"),
        Decimal("0"),
        Decimal("1"),
        Decimal("1.1"),
    ):
        with pytest.raises(ValueError) as invalid_confidence:
            bootstrap_mean_bounds(values, 1, confidence, replications=1)
        assert str(invalid_confidence.value) == ("confidence must be strictly between zero and one")

    with pytest.raises(TypeError) as non_decimal:
        bootstrap_mean_bounds(values, 1, cast(Decimal, 1), replications=1)
    assert str(non_decimal.value) == "confidence must be a finite Decimal"


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


def test_block_analysis_forwards_values_replications_seed_and_cohort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_inputs: list[object] = []
    calls: list[tuple[int, int, int]] = []

    def fake_select(candidate_returns: object) -> int:
        selected_inputs.append(candidate_returns)
        return 7

    def fake_bounds(
        values: tuple[Decimal, ...],
        mean_block_length: int,
        confidence: Decimal,
        *,
        replications: int = DEFAULT_REPLICATIONS,
        seed: int = DEFAULT_SEED,
    ) -> MeanBounds:
        del values, confidence
        calls.append((mean_block_length, replications, seed))
        return _fixed_bounds("61", "70")

    monkeypatch.setattr(decision_module, "select_block_length", fake_select)
    monkeypatch.setattr(decision_module, "bootstrap_mean_bounds", fake_bounds)

    result = evaluate_forward_test(
        _registry(),
        _COHORT_ID,
        EFFICACY_TRADES,
        _at_month(EFFICACY_MONTHS),
        replications=31,
        seed=91,
    )

    assert selected_inputs == [
        {
            f"cohort:{_COHORT_ID}": (
                "0.20",
                "-0.10",
                "0.30",
                "0",
            )
        }
    ]
    assert {block for block, _, _ in calls} == {7, *SENSITIVITY_BLOCK_LENGTHS}
    assert all(replications == 31 and seed == 91 for _, replications, seed in calls)
    assert result.efficacy is not None
    assert result.efficacy.replications == 31
    assert result.efficacy.seed == 91


def test_every_decision_state_preserves_its_evaluation_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_bounds(monkeypatch, lower="61", upper="70")
    efficacy_as_of = _at_month(EFFICACY_MONTHS)
    efficacy = evaluate_forward_test(
        _registry(),
        _COHORT_ID,
        EFFICACY_TRADES,
        efficacy_as_of,
    )
    assert efficacy.as_of_date == efficacy_as_of
    assert efficacy.realized_trade_count == EFFICACY_TRADES
    assert efficacy.observation_day_count == Decimal("4")
    assert efficacy.efficacy is not None
    assert efficacy.efficacy.replications == DEFAULT_REPLICATIONS
    assert efficacy.efficacy.seed == DEFAULT_SEED

    _patch_bounds(monkeypatch, lower="-2", upper="-1")
    futility_as_of = _at_month(FUTILITY_MONTHS)
    futility = evaluate_forward_test(
        _registry(),
        _COHORT_ID,
        FUTILITY_TRADES,
        futility_as_of,
    )
    assert futility.as_of_date == futility_as_of
    assert futility.realized_trade_count == FUTILITY_TRADES
    assert futility.observation_day_count == Decimal("4")
    assert futility.futility is not None
    assert futility.futility.production.block_length == 7
    assert tuple(item.block_length for item in futility.futility.sensitivity) == (
        SENSITIVITY_BLOCK_LENGTHS
    )
    assert futility.futility.replications == DEFAULT_REPLICATIONS
    assert futility.futility.seed == DEFAULT_SEED

    no_decision_as_of = _at_month(1)
    no_decision = evaluate_forward_test(
        _registry(),
        _COHORT_ID,
        Decimal("0"),
        no_decision_as_of,
    )
    assert no_decision.as_of_date == no_decision_as_of
    assert no_decision.realized_trade_count == Decimal("0")
    assert no_decision.observation_day_count == Decimal("4")
    assert no_decision.efficacy is None
    assert no_decision.futility is None


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
