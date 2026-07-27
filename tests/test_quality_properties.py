"""Deterministic properties over high-value pure trading and quality logic."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd
import pytest
from core.strategies.param_schedule import ParamSegment, entry_params_at, segment_at
from hypothesis import given
from hypothesis import strategies as st
from live.risk_control import RiskController, RiskLimits, position_volume
from monitoring.deals import deal_ledger, deals_to_trades, per_trade_risk
from research.engine.characterize import effective_trial_count
from research.engine.continuous import window_returns
from research.engine.mcs import mcs_test
from research.engine.romano_wolf import _stepdown_adjusted_p_values
from research.engine.spa import spa_test
from research.engine.walkforward import WalkForwardWindow
from research.forward_decision import EFFICACY_TRADES, daily_threshold, endpoint_reached
from research.forward_test_registry import (
    CohortPlan,
    CohortStatus,
    HashedInputPaths,
    ObservationSource,
    cohort_identity,
    hash_cohort_inputs,
)
from research.portfolio.drawdown import evaluate, trailing_floor
from research.portfolio.path_risk import clopper_pearson_upper, replay_scenario_path
from research.portfolio.scenarios import (
    LossDayScenario,
    sample_scenario_paths,
    validate_joint_paths,
)
from research.portfolio.sizing import flat, simulate
from research.regression import Thresholds, compare
from scripts.quality.classify import classify_paths, load_model

from tests.support.assertions import assert_limit_monotonicity
from tests.support.strategies import (
    SymbolLotMetadata,
    TradeSample,
    finite_decimals,
    schedule_segments,
    symbol_lot_metadata,
    trade_streams,
    valid_windows,
)


@given(
    values=st.lists(st.integers(min_value=-1_000, max_value=1_000), min_size=1, max_size=20),
    block_length=st.integers(min_value=1, max_value=60),
    replications=st.integers(min_value=1, max_value=10),
    seed=st.integers(min_value=0, max_value=2**32 - 1),
)
def test_loss_day_scenarios_remain_joint_and_fixed_horizon(
    values: list[int],
    block_length: int,
    replications: int,
    seed: int,
) -> None:
    scenarios = tuple(
        LossDayScenario(
            source_date=date(2020, 1, 1) + timedelta(days=index),
            source_opening_balance=Decimal("100000"),
            close_realized_pnl=Decimal(value),
            close_equity_change=Decimal(value * 2),
            opening_to_minimum_equity_change=-abs(Decimal(value)),
            closing_balance_change=Decimal(value),
            trade_count=index % 4,
            daily_swap=Decimal("0"),
        )
        for index, value in enumerate(values)
    )

    first = sample_scenario_paths(
        scenarios,
        mean_block_length=block_length,
        replications=replications,
        seed=seed,
    )
    second = sample_scenario_paths(
        scenarios,
        mean_block_length=block_length,
        replications=replications,
        seed=seed,
    )

    assert first == second
    validate_joint_paths(scenarios, first)
    assert all(len(path) == len(scenarios) for path in first)


@given(
    balance_changes=st.lists(
        st.integers(min_value=-500, max_value=500),
        min_size=1,
        max_size=20,
    ),
    adverse_changes=st.lists(
        st.integers(min_value=-700, max_value=0),
        min_size=1,
        max_size=20,
    ),
)
def test_path_replay_preserves_internal_prop_limit_monotonicity(
    balance_changes: list[int],
    adverse_changes: list[int],
) -> None:
    horizon = min(len(balance_changes), len(adverse_changes))
    scenarios = tuple(
        LossDayScenario(
            source_date=date(2026, 1, 1) + timedelta(days=index),
            source_opening_balance=Decimal("100000"),
            close_realized_pnl=Decimal(balance_changes[index]),
            close_equity_change=Decimal(balance_changes[index]),
            opening_to_minimum_equity_change=Decimal(adverse_changes[index]),
            closing_balance_change=Decimal(balance_changes[index]),
            trade_count=1,
            daily_swap=Decimal("0"),
        )
        for index in range(horizon)
    )

    replay = replay_scenario_path(scenarios, start_balance=Decimal("100000"))

    assert not replay.prop_daily_breach or replay.internal_daily_breach
    assert not replay.prop_trailing_breach or replay.internal_trailing_breach
    assert not replay.prop_any_breach or replay.internal_any_breach
    assert (
        not replay.chronological_prop_trailing_breach
        or replay.chronological_internal_trailing_breach
    )
    assert not replay.chronological_prop_any_breach or replay.chronological_internal_any_breach
    assert not replay.chronological_internal_trailing_breach or replay.internal_trailing_breach


@given(
    dip=st.integers(min_value=1, max_value=249),
    later_gain=st.integers(min_value=0, max_value=500),
)
def test_path_drawdown_is_invariant_to_a_later_close_high(dip: int, later_gain: int) -> None:
    scenario = LossDayScenario(
        source_date=date(2026, 1, 1),
        source_opening_balance=Decimal("1000"),
        close_realized_pnl=Decimal(later_gain),
        close_equity_change=Decimal(later_gain),
        opening_to_minimum_equity_change=-Decimal(dip),
        closing_balance_change=Decimal(later_gain),
        trade_count=1,
        daily_swap=Decimal("0"),
    )

    replay = replay_scenario_path((scenario,), start_balance=Decimal("1000"))

    assert replay.max_drawdown == Decimal(dip) / Decimal("1000")


@given(
    trials=st.integers(min_value=1, max_value=100),
    first=st.integers(min_value=0, max_value=100),
    second=st.integers(min_value=0, max_value=100),
)
def test_clopper_pearson_upper_is_positive_and_monotone(
    trials: int,
    first: int,
    second: int,
) -> None:
    low_events, high_events = sorted((min(first, trials), min(second, trials)))

    low = clopper_pearson_upper(low_events, trials)
    high = clopper_pearson_upper(high_events, trials)

    assert Decimal("0") < low <= high <= Decimal("1")


@given(
    left=st.integers(min_value=0, max_value=10_000),
    right=st.integers(min_value=0, max_value=10_000),
)
def test_effective_trial_count_is_bounded_and_decreases_with_correlation(
    left: int,
    right: int,
) -> None:
    low, high = sorted((Decimal(left) / Decimal(10_000), Decimal(right) / Decimal(10_000)))

    low_count = effective_trial_count(low)
    high_count = effective_trial_count(high)

    assert Decimal("6") <= high_count <= low_count <= Decimal("41")


@given(
    start_cents=st.integers(min_value=1_000_000, max_value=100_000_000),
    prior_cents=st.integers(min_value=-100_000, max_value=100_000),
    opening_cost_cents=st.integers(min_value=0, max_value=10_000),
    close_cents=st.integers(min_value=-100_000, max_value=100_000),
)
def test_ticket_ordered_basis_excludes_the_opening_deal(
    start_cents: int,
    prior_cents: int,
    opening_cost_cents: int,
    close_cents: int,
) -> None:
    """Same-second events before the order count; the order's own costs do not."""

    def money(cents: int) -> Decimal:
        return Decimal(cents) / Decimal(100)

    start = money(start_cents)
    prior = money(prior_cents)
    opening_cost = money(opening_cost_cents)
    close = money(close_cents)
    deals = [
        {
            "ticket": 1,
            "time": 1_700_000_000,
            "type": 2,
            "entry": 0,
            "position_id": 0,
            "symbol": "",
            "volume": 0.0,
            "profit": prior,
            "swap": Decimal("0"),
            "commission": Decimal("0"),
            "fee": Decimal("0"),
        },
        {
            "ticket": 2,
            "time": 1_700_000_000,
            "type": 0,
            "entry": 0,
            "position_id": 7,
            "symbol": "EURUSD",
            "volume": 0.1,
            "profit": Decimal("0"),
            "swap": Decimal("0"),
            "commission": Decimal("0"),
            "fee": -opening_cost,
        },
        {
            "ticket": 3,
            "time": 1_700_000_100,
            "type": 1,
            "entry": 1,
            "position_id": 7,
            "symbol": "EURUSD",
            "volume": 0.1,
            "profit": close,
            "swap": Decimal("0"),
            "commission": Decimal("0"),
            "fee": Decimal("0"),
        },
    ]
    current = start + prior - opening_cost + close
    trades = deals_to_trades(deals)
    risk = per_trade_risk(
        trades,
        current,
        Decimal("0.0018"),
        ledger=deal_ledger(deals),
    )

    assert list(risk) == [(start + prior) * Decimal("0.0018")]


@given(
    finite_decimals(min_value=Decimal("0.01"), max_value=Decimal("10000"), places=2),
    finite_decimals(min_value=Decimal("0.0001"), max_value=Decimal("100"), places=4),
    symbol_lot_metadata(),
)
def test_position_volume_never_exceeds_the_requested_risk(
    risk: Decimal, stop: Decimal, metadata: SymbolLotMetadata
) -> None:
    tick_size = float(metadata.tick_size)
    tick_value = float(metadata.tick_value)
    volume = position_volume(
        float(risk),
        float(stop),
        tick_size,
        tick_value,
        min_lot=float(metadata.min_lot),
        lot_step=float(metadata.lot_step),
        max_lot=float(metadata.max_lot),
    )
    actual_risk = volume * (float(stop) / tick_size) * tick_value
    assert actual_risk <= float(risk) + 1e-7
    assert 0.0 <= volume <= float(metadata.max_lot)


@given(
    start=st.floats(min_value=50_000, max_value=500_000, allow_nan=False, allow_infinity=False),
    equity_frac=st.floats(min_value=0.96, max_value=1.04, allow_nan=False, allow_infinity=False),
    open_frac=st.floats(min_value=0.0, max_value=0.018, allow_nan=False, allow_infinity=False),
    trade_frac=st.floats(min_value=0.0, max_value=0.003, allow_nan=False, allow_infinity=False),
)
def test_stricter_live_limits_never_admit_a_trade_weaker_limits_block(
    start: float, equity_frac: float, open_frac: float, trade_frac: float
) -> None:
    strict_limits = RiskLimits()
    weak_limits = replace(
        strict_limits,
        gate_daily_stop=0.029,
        trailing_stop=0.055,
        open_risk_cap=0.025,
        stress_mult=1.25,
    )
    equity = start * equity_frac

    def allowed(limits: RiskLimits) -> bool:
        controller = RiskController(limits, start)
        controller.open_risk = start * open_frac
        return controller.check_open(start * trade_frac, equity).allowed

    assert_limit_monotonicity(
        (strict_limits,),
        weaker=lambda _x: allowed(weak_limits),
        stronger=lambda _x: allowed(strict_limits),
    )


@given(
    balances=st.lists(
        st.floats(min_value=50_000, max_value=250_000, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=25,
    ),
    scale=st.floats(min_value=0.1, max_value=10, allow_nan=False, allow_infinity=False),
)
def test_drawdown_floor_and_breach_are_scale_invariant(balances: list[float], scale: float) -> None:
    start = 100_000.0
    equity = np.asarray(balances)
    realized = np.asarray(list(reversed(balances)))
    floor = trailing_floor(realized, start, 0.06)
    scaled_floor = trailing_floor(realized * scale, start * scale, 0.06)
    assert np.allclose(scaled_floor, floor * scale)
    assert (
        evaluate(equity, realized, start, 0.06).breached
        == evaluate(equity * scale, realized * scale, start * scale, 0.06).breached
    )


@given(schedule_segments(), st.integers(min_value=-(10**15), max_value=10**15))
def test_parameter_schedule_lookup_matches_the_latest_started_segment(
    segments: tuple[ParamSegment, ...], timestamp: int
) -> None:
    expected = next(
        (segment for segment in reversed(segments) if segment.from_ns <= timestamp), None
    )
    assert segment_at(segments, timestamp) == expected
    expected_params = (
        None
        if expected is None
        else (
            expected.stop_loss_pct,
            expected.take_profit_pct,
        )
    )
    assert entry_params_at(segments, timestamp) == expected_params


@given(valid_windows(), st.data())
def test_every_continuous_trade_is_attributed_exactly_once(
    windows: tuple[WalkForwardWindow, ...], data: st.DataObject
) -> None:
    first = int(windows[0].test_start.value)
    last = int(windows[-1].test_end.value)
    closed = data.draw(
        st.lists(
            st.tuples(
                st.integers(min_value=first, max_value=last),
                st.floats(min_value=-5_000, max_value=5_000, allow_nan=False, allow_infinity=False),
            ),
            max_size=30,
        )
    )
    result = window_returns(closed, windows, 100_000.0)
    attributed = [
        trade_return * 100_000.0 for _window_return, trades in result for trade_return in trades
    ]
    assert len(attributed) == len(closed)
    assert sum(attributed) == pytest.approx(sum(pnl for _timestamp, pnl in closed))


@given(trade_streams(), st.sampled_from([0.25, 0.5, 1.0, 1.5]))
def test_flat_sizing_reconciles_to_every_realized_trade(
    trades: tuple[TradeSample, ...], multiple: float
) -> None:
    rows = []
    prices: dict[str, np.ndarray] = {}
    for trade in trades:
        market = trade.market
        close_day = trade.close_day
        entry = float(trade.entry)
        exit_price = float(trade.exit)
        series = np.full(max(close_day + 1, 1), entry)
        series[close_day] = exit_price
        prices[market] = series
        rows.append(
            {
                "market": market,
                "od": trade.open_day,
                "cd": close_day,
                "pnl_base": float(trade.pnl_base),
                "swap_base": float(trade.swap_base),
                "entry": entry,
                "exit": exit_price,
                "is_long": trade.is_long,
            }
        )
    frame = pd.DataFrame(rows)
    final_day = max(trade.close_day for trade in trades)
    realized, _equity, sizes, _minimum = simulate(
        frame, prices, 0, final_day, 100_000.0, 0.06, flat(multiple)
    )
    expected = 100_000.0 + sum(
        (float(trade.pnl_base) + float(trade.swap_base)) * multiple for trade in trades
    )
    assert realized[-1] == pytest.approx(expected)
    assert np.allclose(sizes, multiple)


def _write_run(path: Path, trades: int, annual: float) -> Path:
    path.mkdir(exist_ok=True)
    (path / "portfolio.json").write_text(
        json.dumps({"n_trades": trades, "ann_return_pct": annual}), encoding="utf-8"
    )
    (path / "full_history_trades.csv").write_text("market,r\nX,1\n", encoding="utf-8")
    return path


@given(
    reference=st.integers(min_value=1, max_value=20_000),
    drift=st.integers(min_value=-10_000, max_value=10_000),
)
def test_regression_trade_threshold_is_exact_and_fail_closed(reference: int, drift: int) -> None:
    candidate = max(0, reference + drift)
    with TemporaryDirectory() as directory:
        root = Path(directory)
        ref = _write_run(root / "reference", reference, 40.0)
        cand = _write_run(root / "candidate", candidate, 40.0)
        result = compare(ref, cand, Thresholds(trade_count_pct=1.0, annual_return_pp=2.0))
    observed = abs(candidate - reference) / reference * 100.0
    flagged = any("trade count moved" in issue for issue in result.unexpected)
    assert flagged == (observed > 1.0)


@given(st.sampled_from(["README.md", "scripts/x.py", "core/paths.py", "live/runner.py"]))
def test_classification_is_spelling_invariant_and_change_sets_take_the_maximum(path: str) -> None:
    model = load_model()
    forms = (path, f"./{path}", path.replace("/", "\\"))
    classes = {classify_paths([form], model).risk_class for form in forms}
    assert len(classes) == 1
    assert (
        classify_paths(["README.md", path], model).risk_class
        == classify_paths([path], model).risk_class
    )


@given(st.binary(max_size=128))
def test_forward_cohort_hashing_is_path_invariant(content: bytes) -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        left = root / "left"
        right = root / "right"
        left.mkdir()
        right.mkdir()
        names = tuple(HashedInputPaths.__dataclass_fields__)
        left_paths: dict[str, Path] = {}
        right_paths: dict[str, Path] = {}
        for name in names:
            left_path = left / name
            right_path = right / f"moved-{name}"
            left_path.write_bytes(content + name.encode())
            right_path.write_bytes(content + name.encode())
            left_paths[name] = left_path
            right_paths[name] = right_path
        assert hash_cohort_inputs(HashedInputPaths(**left_paths)) == hash_cohort_inputs(
            HashedInputPaths(**right_paths)
        )


@given(st.sampled_from(tuple(HashedInputPaths.__dataclass_fields__)))
def test_every_hashed_input_participates_in_forward_cohort_identity(changed: str) -> None:
    paths = HashedInputPaths(*(Path(name) for name in HashedInputPaths.__dataclass_fields__))
    plan = CohortPlan(
        start_timestamp=pd.Timestamp("2026-07-16T21:15:00Z").to_pydatetime(),
        strategy_code_git_sha="01234567" * 5,
        inputs=paths,
        participant_id="7f506d66-68e0-4a65-a76d-0d31eb174d98",
        observation_source=ObservationSource.PAPER,
        primary_hypothesis="Positive daily net portfolio R.",
        thresholds={"mean_net_r_gt": Decimal("0")},
        minimum_calendar_days=Decimal("180"),
        minimum_trade_count=Decimal("450"),
        allowed_safety_stop_reasons=("lineage drift",),
        status=CohortStatus.REGISTERED,
    )
    hashes = dict.fromkeys(HashedInputPaths.__dataclass_fields__, "sha256:" + ("0" * 64))
    changed_hashes = {**hashes, changed: "sha256:" + ("1" * 64)}
    assert cohort_identity(plan, hashes) != cohort_identity(plan, changed_hashes)


@given(
    trades=st.integers(min_value=0, max_value=10_000),
    days=st.integers(min_value=1, max_value=5_000),
)
def test_forward_daily_threshold_is_exact_and_monotone(trades: int, days: int) -> None:
    count = Decimal(trades)
    observed_days = Decimal(days)
    threshold = daily_threshold(count, observed_days)
    assert threshold == Decimal("0.10") * count / observed_days
    assert daily_threshold(count + Decimal("1"), observed_days) >= threshold


@given(
    months_short=st.integers(min_value=0, max_value=29),
    trade_shortfall=st.integers(min_value=1, max_value=2_400),
)
def test_forward_endpoint_requires_both_fixed_conditions(
    months_short: int,
    trade_shortfall: int,
) -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    year = start.year + months_short // 12
    month = months_short % 12 + 1
    before_calendar_endpoint = date(year, month, 1)
    calendar_endpoint = date(2026, 7, 1)

    assert not endpoint_reached(start, before_calendar_endpoint, EFFICACY_TRADES)
    assert not endpoint_reached(
        start,
        calendar_endpoint,
        EFFICACY_TRADES - Decimal(trade_shortfall),
    )


@given(st.floats(min_value=0.1, max_value=100.0, allow_nan=False, allow_infinity=False))
def test_spa_studentization_is_invariant_to_positive_units(scale: float) -> None:
    generator = np.random.default_rng(20260725)
    first = generator.normal(0.15, 1.0, 180)
    second = generator.normal(0.0, 1.0, 180)
    original = spa_test(
        {"first": first, "second": second},
        mean_block_length=5,
        replications=99,
        seed=20260719,
    )
    transformed = spa_test(
        {"first": first * scale, "second": second},
        mean_block_length=5,
        replications=99,
        seed=20260719,
    )

    assert transformed.statistic == pytest.approx(original.statistic, rel=1e-12, abs=1e-12)
    assert transformed.p_value == original.p_value


@given(
    statistics=st.lists(
        st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False),
        min_size=5,
        max_size=5,
    ),
    bootstrap=st.lists(
        st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False),
        min_size=20,
        max_size=20,
    ),
)
def test_romano_wolf_stepdown_p_values_are_monotone_by_construction(
    statistics: list[float],
    bootstrap: list[float],
) -> None:
    observed = np.asarray(sorted(statistics, reverse=True), dtype=np.float64)
    scores = np.asarray(bootstrap, dtype=np.float64).reshape(4, 5)

    raw, adjusted = _stepdown_adjusted_p_values(observed, scores)

    assert np.all(adjusted[1:] >= adjusted[:-1])
    assert np.all(adjusted >= raw)


@given(st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False))
def test_mcs_is_invariant_to_a_common_daily_return_offset(offset: float) -> None:
    generator = np.random.default_rng(20260725)
    returns = {
        "first": generator.normal(0.15, 1.0, 120),
        "second": generator.normal(0.05, 1.0, 120),
        "third": generator.normal(0.0, 1.0, 120),
    }
    shifted = {name: values + offset for name, values in returns.items()}

    original = mcs_test(
        returns,
        mean_block_length=5,
        replications=49,
        seed=20260719,
    )
    transformed = mcs_test(
        shifted,
        mean_block_length=5,
        replications=49,
        seed=20260719,
    )

    assert transformed.elimination_order == original.elimination_order
    assert transformed.surviving_candidates == original.surviving_candidates
    assert [candidate.mcs_p_value for candidate in transformed.candidates] == [
        candidate.mcs_p_value for candidate in original.candidates
    ]
