from __future__ import annotations

import inspect
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest
from research.portfolio.path_risk import (
    INTERNAL_DAILY_LIMIT,
    INTERNAL_TRAILING_LIMIT,
    PROP_DAILY_LIMIT,
    PROP_TRAILING_LIMIT,
    PathRiskMetrics,
    PathRiskSensitivity,
    PathRiskSummary,
    _nearest_rank,
    clopper_pearson_upper,
    replay_scenario_path,
    summarize_path_risk,
    summarize_sampled_paths,
)
from research.portfolio.scenarios import (
    LossDayScenario,
    sample_scenario_paths,
    summarize_scenario_bootstrap,
)


def _scenario(
    day_number: int,
    *,
    balance: str = "0",
    equity: str | None = None,
    minimum: str = "0",
    source_opening: str = "1000",
) -> LossDayScenario:
    balance_change = Decimal(balance)
    return LossDayScenario(
        source_date=date(2026, 1, 1) + timedelta(days=day_number),
        source_opening_balance=Decimal(source_opening),
        close_realized_pnl=balance_change,
        close_equity_change=Decimal(equity if equity is not None else balance),
        opening_to_minimum_equity_change=Decimal(minimum),
        closing_balance_change=balance_change,
        trade_count=0 if balance_change == 0 else 1,
        daily_swap=Decimal("0"),
    )


@pytest.mark.parametrize(
    ("events", "trials", "expected"),
    [
        (0, 10, Decimal("0.258865550893052")),
        (1, 10, Decimal("0.394163302436505")),
        (5, 10, Decimal("0.777558898991871")),
    ],
)
def test_clopper_pearson_upper_matches_trusted_exact_binomial_fixture(
    events: int,
    trials: int,
    expected: Decimal,
) -> None:
    actual = clopper_pearson_upper(events, trials)

    assert abs(actual - expected) < Decimal("1e-12")


def test_zero_events_still_have_positive_clopper_pearson_upper_bound() -> None:
    upper = clopper_pearson_upper(0, 10_000)

    assert Decimal("0") < upper < Decimal("0.01")


@pytest.mark.parametrize(
    ("events", "trials", "message"),
    [
        (-1, 10, "between zero"),
        (11, 10, "between zero"),
        (0, 0, "positive"),
    ],
)
def test_clopper_pearson_rejects_invalid_counts(
    events: int,
    trials: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        clopper_pearson_upper(events, trials)


def test_clopper_pearson_all_events_has_unit_upper_bound() -> None:
    assert Decimal("1") == clopper_pearson_upper(10, 10)


@pytest.mark.parametrize(
    ("events", "trials"),
    [
        (Decimal("0"), 10),
        (0, Decimal("10")),
        (False, 10),
        (0, True),
    ],
)
def test_clopper_pearson_rejects_non_integer_and_boolean_counts(
    events: object,
    trials: object,
) -> None:
    with pytest.raises(TypeError, match="event and trial counts must be integers"):
        clopper_pearson_upper(events, trials)  # type: ignore[arg-type]


@pytest.mark.parametrize("confidence", [Decimal("0"), Decimal("1")])
def test_clopper_pearson_rejects_open_interval_confidence_boundaries(
    confidence: Decimal,
) -> None:
    with pytest.raises(ValueError, match="strictly between zero and one"):
        clopper_pearson_upper(0, 10, confidence=confidence)


def test_nearest_rank_uses_ceiling_and_validates_its_domain() -> None:
    values = tuple(Decimal(value) for value in range(1, 11))

    assert _nearest_rank(values, Decimal("0.25")) == Decimal("3")
    assert _nearest_rank(values, Decimal("1")) == Decimal("10")
    with pytest.raises(ValueError, match="non-empty"):
        _nearest_rank((), Decimal("0.5"))
    with pytest.raises(ValueError, match=r"\(0, 1\]"):
        _nearest_rank(values, Decimal("0"))
    with pytest.raises(ValueError, match=r"\(0, 1\]"):
        _nearest_rank(values, Decimal("1.01"))


def test_intraday_internal_breach_survives_profitable_close() -> None:
    replay = replay_scenario_path(
        (_scenario(0, balance="10", equity="10", minimum="-30"),),
        start_balance=Decimal("1000"),
    )

    assert replay.final_return == Decimal("0.01")
    assert replay.internal_daily_breach
    assert replay.internal_any_breach


def test_daily_breach_decision_is_invariant_to_path_balance_scale() -> None:
    source_day = _scenario(0, minimum="-26", source_opening="1000")

    small_path = replay_scenario_path((source_day,), start_balance=Decimal("1000"))
    large_path = replay_scenario_path((source_day,), start_balance=Decimal("100000"))

    assert small_path.internal_daily_breach
    assert large_path.internal_daily_breach
    assert small_path.prop_daily_breach == large_path.prop_daily_breach
    assert small_path.final_return == large_path.final_return


def test_balance_deltas_compound_from_their_source_opening_balances() -> None:
    path = (
        _scenario(0, balance="50", equity="50", source_opening="100"),
        _scenario(1, balance="-100", equity="-100", source_opening="1000"),
    )
    losing_path = (
        _scenario(2, balance="-10", equity="-10", source_opening="1000"),
        _scenario(3),
    )

    replay = replay_scenario_path(path, start_balance=Decimal("1000"))
    metrics = summarize_sampled_paths((path, path, losing_path), start_balance=Decimal("1000"))

    assert replay.final_return == Decimal("0.35")
    assert metrics.prob_profit == Decimal("2") / Decimal("3")
    assert metrics.negative_final_probability == Decimal("1") / Decimal("3")


def test_zero_observed_breach_days_bootstrap_to_zero_raw_breach_frequency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tuple(
        _scenario(
            index,
            balance=str((Decimal("1000") + Decimal(index * 100)) * Decimal("0.01")),
            minimum=str(-(Decimal("1000") + Decimal(index * 100)) * Decimal("0.0227")),
            source_opening=str(Decimal("1000") + Decimal(index * 100)),
        )
        for index in range(20)
    )
    monkeypatch.setattr("research.portfolio.scenarios.select_block_length", lambda _streams: 1)

    summary = summarize_path_risk(
        source,
        start_balance=Decimal("1000"),
        replications=200,
        seed=20260719,
    )

    assert summary.selected.internal_daily_breach_probability == 0
    assert summary.selected.prop_daily_breach_probability == 0
    assert summary.selected.internal_any_breach_probability == 0
    assert summary.internal_breach_upper_95 > 0


def test_daily_limit_breaches_at_the_exact_live_boundary() -> None:
    at_limit = replay_scenario_path(
        (_scenario(0, minimum="-25"),),
        start_balance=Decimal("1000"),
    )
    below_limit = replay_scenario_path(
        (_scenario(0, minimum="-24.99"),),
        start_balance=Decimal("1000"),
    )

    assert at_limit.internal_daily_breach
    assert not below_limit.internal_daily_breach


def test_same_day_balance_high_raises_the_conservative_trailing_floor() -> None:
    replay = replay_scenario_path(
        (_scenario(0, balance="50", equity="50", minimum="0"),),
        start_balance=Decimal("1000"),
    )

    assert replay.internal_trailing_breach
    assert not replay.prop_trailing_breach
    assert not replay.chronological_internal_trailing_breach
    assert not replay.chronological_prop_trailing_breach


def test_path_drawdown_does_not_use_the_same_days_later_close_peak() -> None:
    replay = replay_scenario_path(
        (_scenario(0, balance="100", equity="100", minimum="-10"),),
        start_balance=Decimal("1000"),
    )

    assert replay.max_drawdown == Decimal("0.01")


def test_path_drawdown_uses_a_prior_days_high_for_a_later_minimum() -> None:
    replay = replay_scenario_path(
        (
            _scenario(0, balance="100", equity="100", minimum="0"),
            _scenario(1, balance="0", equity="0", minimum="-10", source_opening="1000"),
        ),
        start_balance=Decimal("1000"),
    )

    assert replay.max_drawdown == Decimal("0.01")


def test_prop_trailing_breach_persists_after_a_recovery_day() -> None:
    replay = replay_scenario_path(
        (
            _scenario(0, minimum="-60"),
            _scenario(1, balance="10", equity="10", minimum="0"),
        ),
        start_balance=Decimal("1000"),
    )

    assert replay.internal_trailing_breach
    assert replay.prop_trailing_breach


def test_prop_trailing_breach_uses_the_exact_live_boundary() -> None:
    at_limit = replay_scenario_path(
        (_scenario(0, minimum="-60"),),
        start_balance=Decimal("1000"),
    )
    below_limit = replay_scenario_path(
        (_scenario(0, minimum="-59.99"),),
        start_balance=Decimal("1000"),
    )

    assert at_limit.prop_trailing_breach
    assert not below_limit.prop_trailing_breach


def test_time_under_water_counts_every_underwater_close() -> None:
    replay = replay_scenario_path(
        (
            _scenario(0, balance="-10", equity="-10", minimum="-10"),
            _scenario(1),
            _scenario(2, balance="20", equity="20"),
        ),
        start_balance=Decimal("1000"),
    )

    assert replay.time_under_water == Decimal("2") / Decimal("3")


@pytest.mark.parametrize("start_balance", [Decimal("0"), Decimal("-1"), Decimal("NaN")])
def test_path_replay_rejects_nonpositive_or_nonfinite_start_balance(
    start_balance: Decimal,
) -> None:
    with pytest.raises(ValueError, match="finite and positive"):
        replay_scenario_path((_scenario(0),), start_balance=start_balance)


def test_unit_start_balance_is_valid() -> None:
    replay = replay_scenario_path((_scenario(0),), start_balance=Decimal("1"))

    assert replay.final_return == 0


def test_path_replay_guards_strict_internal_limit_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("research.portfolio.path_risk.INTERNAL_DAILY_LIMIT", PROP_DAILY_LIMIT)
    with pytest.raises(RuntimeError, match="daily limit must be strictly tighter"):
        replay_scenario_path((_scenario(0),), start_balance=Decimal("1000"))

    monkeypatch.setattr("research.portfolio.path_risk.INTERNAL_DAILY_LIMIT", INTERNAL_DAILY_LIMIT)
    monkeypatch.setattr(
        "research.portfolio.path_risk.INTERNAL_TRAILING_LIMIT",
        PROP_TRAILING_LIMIT,
    )
    with pytest.raises(RuntimeError, match="trailing limit must be strictly tighter"):
        replay_scenario_path((_scenario(0),), start_balance=Decimal("1000"))


def test_nonpositive_opening_balance_fails_both_daily_limits_closed() -> None:
    replay = replay_scenario_path(
        (
            _scenario(0, balance="-1001", equity="-1001"),
            _scenario(1),
        ),
        start_balance=Decimal("1000"),
    )

    assert replay.internal_daily_breach is True
    assert replay.prop_daily_breach is True


def test_small_positive_opening_balance_is_not_itself_a_breach() -> None:
    replay = replay_scenario_path(
        (
            _scenario(0, balance="-999.5", equity="-999.5"),
            _scenario(1),
        ),
        start_balance=Decimal("1000"),
    )

    assert replay.internal_daily_breach is False
    assert replay.prop_daily_breach is False


def test_one_breach_day_among_ten_matches_analytical_path_probability() -> None:
    source = tuple(_scenario(index, minimum="-30" if index == 0 else "0") for index in range(10))
    paths = sample_scenario_paths(
        source,
        mean_block_length=1,
        replications=4_000,
        seed=20260719,
    )

    metrics = summarize_sampled_paths(paths, start_balance=Decimal("1000"))
    expected = Decimal("1") - Decimal("0.9") ** 10

    assert abs(metrics.internal_daily_breach_probability - expected) < Decimal("0.02")
    assert abs(metrics.prop_daily_breach_probability - expected) < Decimal("0.02")


def test_internal_limit_probabilities_dominate_prop_hard_probabilities() -> None:
    paths = (
        (_scenario(0, minimum="-26"),),
        (_scenario(1, balance="-55", equity="-55", minimum="-55"),),
        (_scenario(2, minimum="0"),),
    )

    metrics = summarize_sampled_paths(paths, start_balance=Decimal("1000"))

    assert metrics.internal_daily_breach_probability >= metrics.prop_daily_breach_probability
    assert metrics.internal_trailing_breach_probability >= metrics.prop_trailing_breach_probability
    assert metrics.internal_any_breach_probability >= metrics.prop_any_breach_probability


def test_impossible_internal_prop_order_fails_closed() -> None:
    with pytest.raises(ValueError, match="internal breach probability"):
        PathRiskMetrics(
            prob_profit=Decimal("1"),
            negative_final_probability=Decimal("0"),
            final_return_p05=Decimal("0"),
            final_return_median=Decimal("0"),
            final_return_p95=Decimal("0"),
            expected_shortfall_05=Decimal("0"),
            max_drawdown_p05=Decimal("0"),
            max_drawdown_median=Decimal("0"),
            max_drawdown_p95=Decimal("0"),
            internal_daily_breach_probability=Decimal("0"),
            internal_trailing_breach_probability=Decimal("0"),
            internal_any_breach_probability=Decimal("0"),
            prop_daily_breach_probability=Decimal("0.1"),
            prop_trailing_breach_probability=Decimal("0"),
            prop_any_breach_probability=Decimal("0.1"),
            chronological_internal_trailing_breach_probability=Decimal("0"),
            chronological_internal_any_breach_probability=Decimal("0"),
            chronological_prop_trailing_breach_probability=Decimal("0"),
            chronological_prop_any_breach_probability=Decimal("0.1"),
            time_under_water_p05=Decimal("0"),
            time_under_water_median=Decimal("0"),
            time_under_water_p95=Decimal("0"),
            internal_any_breach_count=0,
            chronological_internal_any_breach_count=0,
            negative_final_count=0,
        )


def test_summary_reports_all_metrics_and_all_p10_block_choices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tuple(_scenario(index, balance=str(index - 2)) for index in range(5))
    monkeypatch.setattr("research.portfolio.scenarios.select_block_length", lambda _streams: 2)

    summary = summarize_path_risk(
        source,
        start_balance=Decimal("1000"),
        replications=120,
        seed=41,
    )
    payload = summary.to_json()
    selected = payload["selected"]
    assert isinstance(selected, dict)

    assert [item.label for item in summary.sensitivity] == [
        "plugin",
        "fixed_5",
        "fixed_10",
        "fixed_20",
        "fixed_60",
    ]
    assert {
        "final_return_p05",
        "final_return_median",
        "final_return_p95",
        "expected_shortfall_05",
        "max_drawdown_p05",
        "max_drawdown_median",
        "max_drawdown_p95",
        "internal_daily_breach_probability",
        "internal_trailing_breach_probability",
        "prop_daily_breach_probability",
        "prop_trailing_breach_probability",
        "chronological_internal_trailing_breach_probability",
        "chronological_internal_any_breach_probability",
        "chronological_internal_breach_upper_95",
        "time_under_water_p05",
        "time_under_water_median",
        "time_under_water_p95",
    }.issubset(selected)


def test_chronological_trailing_diagnostic_does_not_replace_the_gate() -> None:
    paths = tuple(
        (_scenario(index, balance="50", equity="50", minimum="0"),)
        for index in range(20)
    )
    metrics = summarize_sampled_paths(paths, start_balance=Decimal("1000"))

    assert metrics.internal_trailing_breach_probability == 1
    assert metrics.internal_any_breach_probability == 1
    assert metrics.chronological_internal_trailing_breach_probability == 0
    assert metrics.chronological_internal_any_breach_probability == 0


def test_path_risk_uses_the_same_profit_diagnostic_as_p10(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tuple(_scenario(index, balance=str(index - 10)) for index in range(20))
    monkeypatch.setattr("research.portfolio.scenarios.select_block_length", lambda _streams: 2)

    p10 = summarize_scenario_bootstrap(source, replications=120, seed=41)
    p11 = summarize_path_risk(
        source,
        start_balance=Decimal("1000"),
        replications=120,
        seed=41,
    )

    assert p11.prob_profit == p10.prob_profit
    assert [item.metrics.prob_profit for item in p11.sensitivity] == [
        item.prob_profit for item in p10.sensitivity
    ]


def test_zero_raw_events_do_not_automatically_pass_the_bound_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tuple(_scenario(index, balance="1") for index in range(10))
    monkeypatch.setattr("research.portfolio.scenarios.select_block_length", lambda _streams: 1)

    summary = summarize_path_risk(
        source,
        start_balance=Decimal("1000"),
        replications=100,
        seed=41,
    )

    assert summary.selected.internal_any_breach_probability == 0
    assert summary.internal_breach_upper_95 > Decimal("0.01")
    assert not summary.internal_breach_gate_passes


def test_empirical_quantiles_expected_shortfall_and_water_time_are_exact() -> None:
    paths = tuple(
        (
            _scenario(
                index,
                balance=str(value),
                equity=str(value),
                minimum=str(min(value, 0)),
            ),
        )
        for index, value in enumerate((-30, -20, -10, 0, 10, 20, 30, 40, 50, 60))
    )

    metrics = summarize_sampled_paths(paths, start_balance=Decimal("1000"))

    assert metrics.final_return_p05 == Decimal("-0.03")
    assert metrics.final_return_median == Decimal("0.01")
    assert metrics.final_return_p95 == Decimal("0.06")
    assert metrics.expected_shortfall_05 == Decimal("-0.03")
    assert metrics.max_drawdown_p95 == Decimal("0.03")
    assert metrics.time_under_water_p05 == 0
    assert metrics.time_under_water_p95 == 1


def test_expected_shortfall_uses_ceiling_five_percent_tail_count() -> None:
    returns = (-50, -40, -30, *range(47))
    paths = tuple(
        (
            _scenario(
                index,
                balance=str(value),
                equity=str(value),
                minimum=str(min(value, 0)),
            ),
        )
        for index, value in enumerate(returns)
    )

    metrics = summarize_sampled_paths(paths, start_balance=Decimal("1000"))

    assert metrics.expected_shortfall_05 == Decimal("-0.04")


def test_exactly_flat_final_return_is_not_negative_or_profitable() -> None:
    metrics = summarize_sampled_paths(
        ((_scenario(0),),),
        start_balance=Decimal("1000"),
    )

    assert metrics.prob_profit == 0
    assert metrics.negative_final_probability == 0
    assert metrics.negative_final_count == 0


def test_sampled_path_summary_requires_one_complete_common_horizon() -> None:
    with pytest.raises(ValueError, match="positive calendar-day horizon"):
        summarize_sampled_paths(((),), start_balance=Decimal("1000"))
    with pytest.raises(ValueError, match="positive calendar-day horizon"):
        summarize_sampled_paths(
            (
                (_scenario(0),),
                (_scenario(1), _scenario(2)),
            ),
            start_balance=Decimal("1000"),
        )


def test_path_risk_summary_rejects_inconsistent_counts_and_seed() -> None:
    metrics = summarize_sampled_paths(
        ((_scenario(0, balance="1"),),),
        start_balance=Decimal("1000"),
    )
    sensitivity = tuple(
        PathRiskSensitivity(label, block, metrics)
        for label, block in (
            ("plugin", 2),
            ("fixed_5", 5),
            ("fixed_10", 10),
            ("fixed_20", 20),
            ("fixed_60", 60),
        )
    )

    with pytest.raises(TypeError, match="seed and counts must be integers"):
        PathRiskSummary(
            seed=None,  # type: ignore[arg-type]
            replications=1,
            horizon_days=1,
            selected_block_length=2,
            sensitivity=sensitivity,
        )

    inconsistent = PathRiskMetrics(
        **{
            **metrics.__dict__,
            "internal_any_breach_probability": Decimal("1"),
            "internal_any_breach_count": 0,
        }
    )
    with pytest.raises(ValueError, match="count and probability disagree"):
        PathRiskSummary(
            seed=1,
            replications=1,
            horizon_days=1,
            selected_block_length=2,
            sensitivity=(
                PathRiskSensitivity("plugin", 2, inconsistent),
                *sensitivity[1:],
            ),
        )


def test_path_risk_summary_is_bit_deterministic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tuple(_scenario(index, balance=str(index - 2)) for index in range(5))
    monkeypatch.setattr("research.portfolio.scenarios.select_block_length", lambda _streams: 2)

    first = summarize_path_risk(
        source,
        start_balance=Decimal("1000"),
        replications=80,
        seed=31,
    )
    second = summarize_path_risk(
        source,
        start_balance=Decimal("1000"),
        replications=80,
        seed=31,
    )

    assert first == second
    assert first.to_json() == second.to_json()


def test_registered_limit_order_is_strictly_conservative() -> None:
    assert Decimal("0.025") == INTERNAL_DAILY_LIMIT
    assert Decimal("0.03") == PROP_DAILY_LIMIT
    assert Decimal("0.05") == INTERNAL_TRAILING_LIMIT
    assert Decimal("0.06") == PROP_TRAILING_LIMIT
    assert INTERNAL_DAILY_LIMIT < PROP_DAILY_LIMIT
    assert INTERNAL_TRAILING_LIMIT < PROP_TRAILING_LIMIT


def test_stage4_replaces_profit_gate_and_keeps_profit_diagnostic() -> None:
    from research.stages import verdict

    source = inspect.getsource(verdict.main)

    assert "prob_profit >= 0.6" not in source
    assert "internal_breach_upper_95" in source
    assert "negative_return_upper_95" in source
    assert "mc_prob_profit" in source


def test_real_verdict_entrypoint_executes_new_path_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from research.stages import verdict

    run = tmp_path / "run"
    run.mkdir()
    config = tmp_path / "config.py"
    config.write_text("INSTRUMENTS = []\n", encoding="utf-8")
    (run / "run_manifest.json").write_text(
        json.dumps({"config": str(config)}),
        encoding="utf-8",
    )
    (run / "selection.json").write_text(
        json.dumps(
            {
                "variation": "fixture",
                "forced": False,
                "gates": {
                    "automatic_eligible": True,
                    "spa_ok": True,
                    "romano_wolf_ok": True,
                    "mcs_ok": True,
                    "complete": True,
                    "positive_market_ok": True,
                    "return_drawdown_ok": True,
                },
            }
        ),
        encoding="utf-8",
    )
    (run / "portfolio.json").write_text(
        json.dumps(
            {
                "variation": "fixture",
                "train_months": 36,
                "instruments": [],
                "tail_cap_pct": 0.2,
                "ceiling_pct": 0.15,
                "floor_pct": 0.15,
                "risk_policy": "flat:0.15",
                "worst_day_r": -10,
                "stress_mult": 1.5,
                "fixed_config": "fixture.py",
            }
        ),
        encoding="utf-8",
    )
    (run / "portfolio_trades.csv").write_text("market,r\n", encoding="utf-8")
    scenario = _scenario(0)
    (run / "loss_day_scenarios.csv").write_text(
        "schema_version,source_date,source_opening_balance,"
        "close_realized_pnl,close_equity_change,"
        "opening_to_minimum_equity_change,closing_balance_change,trade_count,daily_swap\n"
        f"2,{scenario.source_date},1000,0,0,0,0,0,0\n",
        encoding="utf-8",
    )

    class _Result:
        trade_pnl = np.array([], dtype=np.float64)
        daily_diagnostics = type(
            "_Diagnostics",
            (),
            {
                "days": np.array([], dtype=np.int64),
                "close_equity": np.array([], dtype=np.float64),
                "daily_breach": np.array([], dtype=bool),
                "trailing_breach": np.array([], dtype=bool),
                "h4_upper_bound": "fixture",
            },
        )()
        max_drawdown_pct = 0.0
        max_daily_loss_pct = 0.0
        n_trades = 30
        breached = False
        ann_return_pct = 1.0
        ceiling_pct = 0.15
        floor_pct = 0.15
        label = "flat"

    monkeypatch.setattr(
        verdict,
        "load_config_module",
        lambda _path: type(
            "_Config",
            (),
            {
                "INSTRUMENTS": [],
                "ACCOUNT": type("_Account", (), {"start_balance": 1000.0})(),
                "HOLDOUT_CONTAMINATED": False,
            },
        )(),
    )
    monkeypatch.setattr(
        "research.stages.verdict.lineage.external_inputs",
        lambda *_args: {},
    )
    monkeypatch.setattr(verdict, "evaluate_policy", lambda *_args, **_kwargs: _Result())
    monkeypatch.setattr(
        verdict,
        "edge_stats",
        lambda _pnl: {
            "trades": 30.0,
            "hit_rate": 1.0,
            "profit_factor": 2.0,
            "payoff": 2.0,
            "expectancy": 1.0,
            "sharpe": 1.0,
        },
    )
    monkeypatch.setattr(
        verdict,
        "risk_stats",
        lambda *_args, **_kwargs: {
            "total_return": 0.01,
            "annual_return": 0.01,
            "max_drawdown": 0.0,
        },
    )
    monkeypatch.setattr("research.portfolio.scenarios.select_block_length", lambda _streams: 1)
    real_summary = summarize_path_risk
    monkeypatch.setattr(
        verdict,
        "summarize_path_risk",
        lambda rows, *, start_balance: real_summary(
            rows,
            start_balance=start_balance,
            replications=500,
            seed=20260719,
        ),
    )

    verdict.main(["--run", str(run), "--allow-legacy-unverified"])

    payload = json.loads((run / "verdict.json").read_text(encoding="utf-8"))
    assert payload["mc_prob_profit"] == 0.0
    assert all("Gewinnwahrsch" not in reason for reason in payload["reasons"])
    assert "internal_breach_upper_95" in payload["path_bootstrap"]
    assert any("interne Limitverletzung" in reason for reason in payload["reasons"])
    assert payload["stats"]["max_drawdown"] * 100 == payload["path"]["max_drawdown_pct"]
    selected = payload["path_bootstrap"]
    comparison = payload["path"]["trailing_hwm_comparison"]
    assert comparison["gate_internal_trailing_breach_probability"] == selected[
        "internal_trailing_breach_probability"
    ]
    assert comparison["chronological_internal_trailing_breach_probability"] == selected[
        "chronological_internal_trailing_breach_probability"
    ]
    assert comparison["chronological_diagnostic_only"] is True
