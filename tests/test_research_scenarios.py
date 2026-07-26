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
    LossDayScenario,
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
    assert ",0," in artifact.read_text(encoding="utf-8")


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

    with pytest.raises(ValueError, match="contiguous"):
        read_loss_day_scenarios(artifact)


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

    with pytest.raises(ValueError, match="opening balance is discontinuous"):
        build_loss_day_scenarios(
            trades,
            SimpleNamespace(
                trade_pnl=np.array([10.0, -5.0]),
                trade_swap=np.array([1.0, -1.0]),
                daily_diagnostics=diagnostics,
            ),
            start_balance=Decimal("1000"),
        )


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

    with pytest.raises(ValueError, match="not an observed joint bundle"):
        validate_joint_paths(source, tuple(tuple(path) for path in corrupted))


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
    assert first.replications == 40
    assert first.horizon_days == 120
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


def test_production_bootstrap_defaults_are_registered_p04_values() -> None:
    assert DEFAULT_REPLICATIONS == 10_000
    assert DEFAULT_SEED == 20260719


def test_real_stages_persist_and_consume_scenarios_without_trade_slot_bootstrap() -> None:
    from research.stages import portfolio, verdict

    portfolio_source = inspect.getsource(portfolio.main)
    verdict_source = inspect.getsource(verdict.main)

    assert 'st.file("loss_day_scenarios.csv")' in portfolio_source
    assert 'run.require("loss_day_scenarios.csv", "portfolio")' in verdict_source
    assert "summarize_scenario_bootstrap(scenarios)" in verdict_source
    assert "monte_carlo_paths" not in verdict_source
    assert 'seeds={"loss_day_bootstrap": DEFAULT_SEED}' in verdict_source
    assert "prob_profit >= 0.6" in verdict_source
