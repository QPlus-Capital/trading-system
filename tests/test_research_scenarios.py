from __future__ import annotations

import inspect
import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from research.portfolio.resample import DEFAULT_REPLICATIONS, DEFAULT_SEED
from research.portfolio.scenarios import (
    LOSS_DAY_SCENARIO_SCHEMA_VERSION,
    LossDayScenario,
    _probability_of_profit,
    _stationary_source_indices,
    _validated_diagnostics,
    build_loss_day_scenarios,
    read_loss_day_scenarios,
    sample_scenario_paths,
    summarize_scenario_bootstrap,
    validate_joint_paths,
    write_loss_day_scenarios,
)
from research.portfolio.sizing import DailyDiagnostics


def _timestamp_for_loss_day(day_number: int) -> int:
    observed = datetime(1970, 1, 1, 12, tzinfo=UTC) + timedelta(days=day_number)
    return int(observed.timestamp() * 1_000_000_000)


def _diagnostics() -> DailyDiagnostics:
    return DailyDiagnostics(
        days=np.array([20_000, 20_001, 20_002], dtype=np.int64),
        opening_balance=np.array([1_000.0, 1_010.0, 1_010.0]),
        close_balance=np.array([1_010.0, 1_010.0, 1_005.0]),
        close_equity=np.array([1_012.0, 1_015.0, 1_005.0]),
        minimum_equity=np.array([995.0, 1_008.0, 1_004.0]),
        daily_loss=np.array([0.005, 2 / 1_010, 6 / 1_010]),
        trailing_floor=np.array([940.0, 949.4, 949.4]),
        daily_breach=np.array([False, False, False]),
        trailing_breach=np.array([False, False, False]),
    )


def _policy_result() -> SimpleNamespace:
    return SimpleNamespace(
        trade_pnl=np.array([10.0, -5.0]),
        trade_swap=np.array([1.0, -1.0]),
        daily_diagnostics=_diagnostics(),
    )


def _scenario(day_number: int, amount: str, *, trades: int = 1) -> LossDayScenario:
    value = Decimal(amount)
    return LossDayScenario(
        source_date=date(1970, 1, 1) + timedelta(days=day_number),
        source_opening_balance=Decimal("1000"),
        close_realized_pnl=value,
        close_equity_change=value,
        opening_to_minimum_equity_change=min(value, Decimal("0")),
        closing_balance_change=value,
        trade_count=trades,
        daily_swap=Decimal("0"),
    )


def test_scenario_set_uses_every_diagnostic_day_and_exact_accounting(tmp_path: Path) -> None:
    trades = pd.DataFrame(
        {
            "ts_closed": [_timestamp_for_loss_day(20_000), _timestamp_for_loss_day(20_002)],
        }
    )

    scenarios = build_loss_day_scenarios(trades, _policy_result(), start_balance=Decimal("1000"))

    assert [row.source_date.isoformat() for row in scenarios] == [
        "2024-10-04",
        "2024-10-05",
        "2024-10-06",
    ]
    assert [row.trade_count for row in scenarios] == [1, 0, 1]
    assert [row.source_opening_balance for row in scenarios] == [
        Decimal("1000.0"),
        Decimal("1010.0"),
        Decimal("1010.0"),
    ]
    assert [row.closing_balance_change for row in scenarios] == [
        Decimal("10.0"),
        Decimal("0.0"),
        Decimal("-5.0"),
    ]
    assert [row.daily_swap for row in scenarios] == [
        Decimal("1.0"),
        Decimal("0"),
        Decimal("-1.0"),
    ]
    assert [row.close_realized_pnl for row in scenarios] == [
        Decimal("9.0"),
        Decimal("0.0"),
        Decimal("-4.0"),
    ]
    assert [row.close_equity_change for row in scenarios] == [
        Decimal("12.0"),
        Decimal("3.0"),
        Decimal("-10.0"),
    ]
    assert [row.opening_to_minimum_equity_change for row in scenarios] == [
        Decimal("-5.0"),
        Decimal("-2.0"),
        Decimal("-6.0"),
    ]
    assert all(
        row.close_realized_pnl + row.daily_swap == row.closing_balance_change for row in scenarios
    )

    artifact = tmp_path / "loss_day_scenarios.csv"
    write_loss_day_scenarios(artifact, scenarios)
    assert read_loss_day_scenarios(artifact) == scenarios
    artifact_text = artifact.read_text(encoding="utf-8")
    assert artifact_text.startswith(
        "schema_version,source_date,source_opening_balance,close_realized_pnl,"
    )
    assert f"\n{LOSS_DAY_SCENARIO_SCHEMA_VERSION},2024-10-04,1000.0," in artifact_text
    assert ",0," in artifact_text


def test_opening_to_minimum_is_copied_from_the_supplied_diagnostics() -> None:
    trades = pd.DataFrame(
        {
            "ts_closed": [_timestamp_for_loss_day(20_000), _timestamp_for_loss_day(20_002)],
        }
    )
    baseline = build_loss_day_scenarios(trades, _policy_result(), start_balance=Decimal("1000"))
    changed_diagnostics = replace(
        _diagnostics(),
        minimum_equity=np.array([994.25, 1_008.0, 1_004.0]),
    )
    changed = build_loss_day_scenarios(
        trades,
        SimpleNamespace(
            trade_pnl=np.array([10.0, -5.0]),
            trade_swap=np.array([1.0, -1.0]),
            daily_diagnostics=changed_diagnostics,
        ),
        start_balance=Decimal("1000"),
    )

    assert baseline[0].opening_to_minimum_equity_change == Decimal("-5.0")
    assert changed[0].opening_to_minimum_equity_change == Decimal("-5.75")
    assert changed[1:] == baseline[1:]


def test_reader_fails_closed_when_a_zero_trade_calendar_day_is_dropped(tmp_path: Path) -> None:
    artifact = tmp_path / "loss_day_scenarios.csv"
    write_loss_day_scenarios(
        artifact,
        (
            _scenario(1, "1"),
            _scenario(2, "0", trades=0),
            _scenario(3, "-1"),
        ),
    )
    lines = artifact.read_text(encoding="utf-8").splitlines()
    artifact.write_text("\n".join((lines[0], lines[1], lines[3])) + "\n", encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        read_loss_day_scenarios(artifact)

    assert (
        str(exc_info.value) == "loss-day scenario dates must be contiguous and strictly increasing"
    )


def test_builder_rejects_a_discontinuous_diagnostic_balance() -> None:
    trades = pd.DataFrame(
        {
            "ts_closed": [_timestamp_for_loss_day(20_000), _timestamp_for_loss_day(20_002)],
        }
    )
    diagnostics = replace(
        _diagnostics(),
        opening_balance=np.array([1_000.0, 1_009.0, 1_010.0]),
    )

    with pytest.raises(ValueError) as exc_info:
        build_loss_day_scenarios(
            trades,
            SimpleNamespace(
                trade_pnl=np.array([10.0, -5.0]),
                trade_swap=np.array([1.0, -1.0]),
                daily_diagnostics=diagnostics,
            ),
            start_balance=Decimal("1000"),
        )

    assert str(exc_info.value) == "diagnostic opening balance is discontinuous on 2024-10-05"


def test_diagnostic_validation_rejects_empty_and_unequal_arrays() -> None:
    empty = np.array([], dtype=np.float64)
    empty_bool = np.array([], dtype=np.bool_)
    empty_diagnostics = DailyDiagnostics(
        days=empty.astype(np.int64),
        opening_balance=empty,
        close_balance=empty,
        close_equity=empty,
        minimum_equity=empty,
        daily_loss=empty,
        trailing_floor=empty,
        daily_breach=empty_bool,
        trailing_breach=empty_bool,
    )
    unequal = replace(_diagnostics(), close_equity=np.array([1_000.0]))

    for diagnostics in (empty_diagnostics, unequal):
        with pytest.raises(ValueError) as exc_info:
            _validated_diagnostics(diagnostics)
        assert str(exc_info.value) == "daily diagnostics must contain equal, non-empty arrays"


def test_diagnostic_validation_returns_integer_days_and_checks_each_money_field() -> None:
    integral_float_days = replace(
        _diagnostics(),
        days=np.array([20_000.0, 20_001.0, 20_002.0]),
    )

    days = _validated_diagnostics(integral_float_days)

    assert days.dtype == np.int64
    for invalid_diagnostics in (
        replace(_diagnostics(), opening_balance=np.array([np.nan, 1.0, 1.0])),
        replace(_diagnostics(), close_balance=np.array([np.nan, 1.0, 1.0])),
        replace(_diagnostics(), close_equity=np.array([np.nan, 1.0, 1.0])),
        replace(_diagnostics(), minimum_equity=np.array([np.nan, 1.0, 1.0])),
        replace(_diagnostics(), daily_loss=np.array([np.nan, 1.0, 1.0])),
    ):
        with pytest.raises(ValueError) as exc_info:
            _validated_diagnostics(invalid_diagnostics)
        assert str(exc_info.value) == "daily diagnostics contain non-finite values"


def test_diagnostic_validation_converts_decimal_object_arrays_before_finite_check() -> None:
    diagnostics = replace(
        _diagnostics(),
        opening_balance=np.array(
            [Decimal("1000"), Decimal("1010"), Decimal("1010")],
            dtype=object,
        ),
    )

    days = _validated_diagnostics(diagnostics)

    assert np.array_equal(days, np.array([20_000, 20_001, 20_002], dtype=np.int64))


def test_diagnostic_validation_reports_the_exact_grid_failure() -> None:
    diagnostics = replace(_diagnostics(), days=np.array([20_000, 20_002, 20_003]))

    with pytest.raises(ValueError) as exc_info:
        _validated_diagnostics(diagnostics)

    assert str(exc_info.value) == "daily diagnostics must use one contiguous loss-day grid"


def test_builder_requires_close_timestamps() -> None:
    with pytest.raises(ValueError) as exc_info:
        build_loss_day_scenarios(
            pd.DataFrame({"not_closed": [1, 2]}),
            _policy_result(),
            start_balance=Decimal("1000"),
        )

    assert str(exc_info.value) == "scenario trades require ts_closed"


def test_builder_names_a_close_outside_the_diagnostic_grid() -> None:
    trades = pd.DataFrame(
        {
            "ts_closed": [_timestamp_for_loss_day(19_999), _timestamp_for_loss_day(20_002)],
        }
    )

    with pytest.raises(ValueError) as exc_info:
        build_loss_day_scenarios(trades, _policy_result(), start_balance=Decimal("1000"))

    assert str(exc_info.value) == "trade closes outside daily diagnostics: loss day 19999"


def test_builder_names_the_day_of_a_policy_balance_disagreement() -> None:
    trades = pd.DataFrame(
        {
            "ts_closed": [_timestamp_for_loss_day(20_000), _timestamp_for_loss_day(20_002)],
        }
    )
    result = _policy_result()
    result.trade_pnl = np.array([9.0, -5.0])

    with pytest.raises(ValueError) as exc_info:
        build_loss_day_scenarios(trades, result, start_balance=Decimal("1000"))

    assert str(exc_info.value) == "policy P&L disagrees with diagnostic balance on 2024-10-04"


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("trade_pnl", "trade rows, policy P&L, and policy swap must have equal lengths"),
        ("trade_swap", "trade rows, policy P&L, and policy swap must have equal lengths"),
    ],
)
def test_builder_rejects_each_one_sided_trade_array_mismatch(field: str, expected: str) -> None:
    trades = pd.DataFrame(
        {
            "ts_closed": [_timestamp_for_loss_day(20_000), _timestamp_for_loss_day(20_002)],
        }
    )
    result = _policy_result()
    setattr(result, field, np.array([10.0]))

    with pytest.raises(ValueError) as exc_info:
        build_loss_day_scenarios(trades, result, start_balance=Decimal("1000"))

    assert str(exc_info.value) == expected


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("trade_pnl", "policy trade P&L must be finite"),
        ("trade_swap", "policy trade swap must be finite"),
    ],
)
def test_builder_rejects_each_non_finite_trade_array(field: str, expected: str) -> None:
    trades = pd.DataFrame(
        {
            "ts_closed": [_timestamp_for_loss_day(20_000), _timestamp_for_loss_day(20_002)],
        }
    )
    result = _policy_result()
    setattr(result, field, np.array([np.nan, -5.0]))

    with pytest.raises(ValueError) as exc_info:
        build_loss_day_scenarios(trades, result, start_balance=Decimal("1000"))

    assert str(exc_info.value) == expected


def test_builder_counts_and_sums_multiple_closes_on_one_day() -> None:
    trades = pd.DataFrame(
        {
            "ts_closed": [
                _timestamp_for_loss_day(20_000),
                _timestamp_for_loss_day(20_000),
                _timestamp_for_loss_day(20_002),
            ],
        }
    )
    result = SimpleNamespace(
        trade_pnl=np.array([4.0, 6.0, -5.0]),
        trade_swap=np.array([0.25, 0.75, -1.0]),
        daily_diagnostics=_diagnostics(),
    )

    scenarios = build_loss_day_scenarios(trades, result, start_balance=Decimal("1000"))

    assert scenarios[0].trade_count == 2
    assert scenarios[0].daily_swap == Decimal("1.00")
    assert scenarios[0].closing_balance_change == Decimal("10.0")
    assert scenarios[0].close_realized_pnl == Decimal("9.00")


def test_builder_accepts_exact_accounting_tolerance_boundary() -> None:
    trades = pd.DataFrame({"ts_closed": [_timestamp_for_loss_day(20_000)]})
    diagnostics = DailyDiagnostics(
        days=np.array([20_000], dtype=np.int64),
        opening_balance=np.array([1_000.00000001]),
        close_balance=np.array([1_010.00000001]),
        close_equity=np.array([1_010.00000001]),
        minimum_equity=np.array([999.0]),
        daily_loss=np.array([0.001]),
        trailing_floor=np.array([940.0]),
        daily_breach=np.array([False]),
        trailing_breach=np.array([False]),
    )
    result = SimpleNamespace(
        trade_pnl=np.array([10.0]),
        trade_swap=np.array([0.0]),
        daily_diagnostics=diagnostics,
    )

    scenarios = build_loss_day_scenarios(trades, result, start_balance=Decimal("1000"))

    assert scenarios[0].closing_balance_change == Decimal("10.00000001")


@pytest.mark.parametrize("invalid_day", [np.nan, 20_000.5])
def test_builder_rejects_non_integer_diagnostic_day_identifiers(invalid_day: float) -> None:
    diagnostics = replace(_diagnostics(), days=np.array([invalid_day, 20_001, 20_002]))
    trades = pd.DataFrame(
        {
            "ts_closed": [_timestamp_for_loss_day(20_000), _timestamp_for_loss_day(20_002)],
        }
    )

    with pytest.raises(ValueError) as exc_info:
        build_loss_day_scenarios(
            trades,
            SimpleNamespace(
                trade_pnl=np.array([10.0, -5.0]),
                trade_swap=np.array([1.0, -1.0]),
                daily_diagnostics=diagnostics,
            ),
            start_balance=Decimal("1000"),
        )

    assert str(exc_info.value) == "daily diagnostic day identifiers must be finite integers"


def test_stationary_source_indices_forward_seed_and_require_integer_indices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def fake_bootstrap(
        values: np.ndarray,
        mean_block_length: int,
        *,
        replications: int,
        seed: int,
    ) -> np.ndarray:
        observed.update(
            values=values.copy(),
            mean_block_length=mean_block_length,
            replications=replications,
            seed=seed,
        )
        return np.tile(np.arange(len(values), dtype=np.float64), (replications, 1))

    monkeypatch.setattr("research.portfolio.scenarios.stationary_bootstrap", fake_bootstrap)

    indices = _stationary_source_indices(3, 2, replications=4, seed=31)

    assert observed["mean_block_length"] == 2
    assert observed["replications"] == 4
    assert observed["seed"] == 31
    sampled_values = observed["values"]
    assert isinstance(sampled_values, np.ndarray)
    assert np.array_equal(sampled_values, np.arange(3))
    assert indices.dtype == np.int64
    assert indices.shape == (4, 3)


def test_stationary_source_indices_reject_empty_input_with_exact_diagnostic() -> None:
    with pytest.raises(ValueError) as exc_info:
        _stationary_source_indices(0, 1, replications=1, seed=1)

    assert str(exc_info.value) == "loss-day scenarios must be non-empty"


def test_stationary_source_indices_reject_non_integral_bootstrap_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "research.portfolio.scenarios.stationary_bootstrap",
        lambda *_args, **_kwargs: np.array([[0.5]]),
    )

    with pytest.raises(ValueError) as exc_info:
        _stationary_source_indices(1, 1, replications=1, seed=1)

    assert str(exc_info.value) == "stationary bootstrap returned invalid source indices"


def test_probability_of_profit_is_strictly_positive_and_forwards_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = (_scenario(1, "0"),)
    observed: dict[str, int] = {}

    def fake_paths(
        scenarios: tuple[LossDayScenario, ...],
        *,
        mean_block_length: int,
        replications: int,
        seed: int,
    ) -> tuple[tuple[LossDayScenario, ...], ...]:
        observed.update(
            block_length=mean_block_length,
            replications=replications,
            seed=seed,
        )
        zero = replace(scenarios[0], closing_balance_change=Decimal("0"))
        positive = replace(
            scenarios[0],
            close_realized_pnl=Decimal("1"),
            closing_balance_change=Decimal("1"),
        )
        return ((zero,), (positive,))

    monkeypatch.setattr("research.portfolio.scenarios.sample_scenario_paths", fake_paths)

    probability = _probability_of_profit(source, 7, replications=2, seed=37)

    assert probability == Decimal("0.5")
    assert observed == {"block_length": 7, "replications": 2, "seed": 37}


def test_scenario_bootstrap_has_fixed_calendar_horizon_and_joint_rows() -> None:
    source = tuple(_scenario(index, str(index + 1), trades=index % 3) for index in range(12))

    paths = sample_scenario_paths(
        source,
        mean_block_length=3,
        replications=30,
        seed=17,
    )

    assert len(paths) == 30
    assert {len(path) for path in paths} == {len(source)}
    validate_joint_paths(source, paths)
    assert all(row in source for path in paths for row in path)


def test_joint_validation_rejects_one_independently_shuffled_field() -> None:
    source = tuple(_scenario(index, str(index + 1)) for index in range(8))
    paths = sample_scenario_paths(source, mean_block_length=2, replications=2, seed=5)
    corrupted = [list(path) for path in paths]
    shuffled = [row.close_equity_change for row in corrupted[0]]
    corrupted[0] = [
        replace(row, close_equity_change=shuffled[(index + 1) % len(shuffled)])
        for index, row in enumerate(corrupted[0])
    ]

    with pytest.raises(ValueError) as exc_info:
        validate_joint_paths(source, tuple(tuple(path) for path in corrupted))

    assert str(exc_info.value) == (
        "scenario path contains a row that is not an observed joint bundle"
    )


def test_joint_validation_rejects_empty_source_and_wrong_horizon() -> None:
    with pytest.raises(ValueError) as empty_exc:
        validate_joint_paths((), ())
    assert str(empty_exc.value) == "loss-day scenarios must be non-empty"

    source = (_scenario(1, "1"), _scenario(2, "-1"))
    with pytest.raises(ValueError) as horizon_exc:
        validate_joint_paths(source, ((source[0],),))
    assert str(horizon_exc.value) == "scenario path has 1 days, expected 2"


def test_bootstrap_preserves_observed_zero_trade_rows_without_padding() -> None:
    source = (
        _scenario(1, "3", trades=1),
        _scenario(2, "0", trades=0),
        _scenario(3, "-2", trades=2),
        _scenario(4, "0", trades=0),
    )

    paths = sample_scenario_paths(source, mean_block_length=1, replications=40, seed=19)

    validate_joint_paths(source, paths)
    observed_zero_dates = {row.source_date for row in source if row.trade_count == 0}
    sampled_zero_rows = [row for path in paths for row in path if row.trade_count == 0]
    assert sampled_zero_rows
    assert {row.source_date for row in sampled_zero_rows}.issubset(observed_zero_dates)
    assert all(len(path) == 4 for path in paths)


def test_scenario_bootstrap_is_deterministic_and_reports_all_sensitivities() -> None:
    generator = np.random.default_rng(20260719)
    source = tuple(
        _scenario(index, str(value), trades=index % 2)
        for index, value in enumerate(generator.normal(0.1, 1.0, size=120))
    )

    first = summarize_scenario_bootstrap(source, replications=40, seed=29)
    second = summarize_scenario_bootstrap(source, replications=40, seed=29)

    assert first == second
    assert first.seed == 29
    assert first.replications == 40
    assert first.horizon_days == 120
    assert first.selected_block_length == first.sensitivity[0].block_length
    assert [item.label for item in first.sensitivity] == [
        "plugin",
        "fixed_5",
        "fixed_10",
        "fixed_20",
        "fixed_60",
    ]
    assert [item.block_length for item in first.sensitivity[1:]] == [5, 10, 20, 60]
    assert all(Decimal("0") <= item.prob_profit <= Decimal("1") for item in first.sensitivity)
    assert json.dumps(first.to_json(), sort_keys=True) == json.dumps(
        second.to_json(), sort_keys=True
    )


def test_summary_passes_the_named_return_stream_to_block_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tuple(_scenario(index, str(index - 2)) for index in range(5))
    observed: dict[str, np.ndarray] = {}

    def fake_select(streams: dict[str, np.ndarray]) -> int:
        observed.update(streams)
        return 2

    monkeypatch.setattr("research.portfolio.scenarios.select_block_length", fake_select)
    monkeypatch.setattr(
        "research.portfolio.scenarios._probability_of_profit",
        lambda *_args, **_kwargs: Decimal("0.25"),
    )

    summary = summarize_scenario_bootstrap(source, replications=3, seed=41)

    assert set(observed) == {"closing_balance_change"}
    assert np.array_equal(observed["closing_balance_change"], np.array([-2, -1, 0, 1, 2]))
    assert summary.selected_block_length == 2


def test_summary_rejects_empty_input_with_exact_diagnostic() -> None:
    with pytest.raises(ValueError) as exc_info:
        summarize_scenario_bootstrap(())

    assert str(exc_info.value) == "loss-day scenarios must be non-empty"


def test_reader_reports_exact_schema_empty_and_parse_failures(tmp_path: Path) -> None:
    invalid_schema = tmp_path / "invalid-schema.csv"
    invalid_schema.write_text("wrong\nvalue\n", encoding="utf-8")
    with pytest.raises(ValueError) as schema_exc:
        read_loss_day_scenarios(invalid_schema)
    assert str(schema_exc.value) == "loss-day scenario CSV has an invalid schema"

    empty = tmp_path / "empty.csv"
    empty.write_text(
        ",".join(
            (
                "schema_version",
                "source_date",
                "source_opening_balance",
                "close_realized_pnl",
                "close_equity_change",
                "opening_to_minimum_equity_change",
                "closing_balance_change",
                "trade_count",
                "daily_swap",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as empty_exc:
        read_loss_day_scenarios(empty)
    assert str(empty_exc.value) == "loss-day scenario CSV must be non-empty"

    missing = tmp_path / "missing.csv"
    with pytest.raises(ValueError) as missing_exc:
        read_loss_day_scenarios(missing)
    assert str(missing_exc.value) == f"cannot read loss-day scenarios from {missing}"


def test_reader_fails_closed_on_the_unversioned_scenario_schema(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy.csv"
    legacy.write_text(
        "source_date,close_realized_pnl,close_equity_change,"
        "opening_to_minimum_equity_change,closing_balance_change,trade_count,daily_swap\n"
        "2026-01-01,0,0,0,0,0,0\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="schema"):
        read_loss_day_scenarios(legacy)


def test_reader_fails_closed_on_an_old_explicit_schema_version(tmp_path: Path) -> None:
    old = tmp_path / "old.csv"
    old.write_text(
        "schema_version,source_date,source_opening_balance,close_realized_pnl,"
        "close_equity_change,opening_to_minimum_equity_change,"
        "closing_balance_change,trade_count,daily_swap\n"
        "1,2026-01-01,1000,0,0,0,0,0,0\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported loss-day scenario schema '1'"):
        read_loss_day_scenarios(old)


@pytest.mark.parametrize("source_opening", ["0", "-1", "NaN"])
def test_scenarios_require_a_positive_finite_source_opening_balance(
    source_opening: str,
) -> None:
    with pytest.raises(ValueError, match="source opening balance|non-finite money"):
        LossDayScenario(
            source_date=date(2026, 1, 1),
            source_opening_balance=Decimal(source_opening),
            close_realized_pnl=Decimal("0"),
            close_equity_change=Decimal("0"),
            opening_to_minimum_equity_change=Decimal("0"),
            closing_balance_change=Decimal("0"),
            trade_count=0,
            daily_swap=Decimal("0"),
        )


def test_production_bootstrap_defaults_are_registered_p04_values() -> None:
    assert DEFAULT_REPLICATIONS == 10_000
    assert DEFAULT_SEED == 20260719


def test_real_stages_persist_and_consume_scenarios_without_trade_slot_bootstrap() -> None:
    from research.stages import portfolio, verdict

    portfolio_source = inspect.getsource(portfolio.main)
    verdict_source = inspect.getsource(verdict.main)

    assert 'st.file("loss_day_scenarios.csv")' in portfolio_source
    assert 'run.require("loss_day_scenarios.csv", "portfolio")' in verdict_source
    assert "summarize_path_risk(" in verdict_source
    assert "monte_carlo_paths" not in verdict_source
    assert 'seeds={"loss_day_bootstrap": DEFAULT_SEED}' in verdict_source
    assert "prob_profit >= 0.6" not in verdict_source
    assert "internal_breach_gate_passes" in verdict_source
    assert "negative_return_gate_passes" in verdict_source
