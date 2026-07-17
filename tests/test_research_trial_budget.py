"""Tests for the honest multiple-testing budget."""

from types import SimpleNamespace

from research.engine.config import load_config_module
from research.engine.overfitting import TrialBudget, study_trial_budget

_REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]


def test_total_is_the_product_of_dimensions() -> None:
    assert TrialBudget(12, 3, 16).total == 576


def test_study_budget_from_the_real_robustness_config() -> None:
    cfg = load_config_module(_REPO_ROOT / "research" / "config" / "robustness.py")
    budget = study_trial_budget(cfg)
    # 12 variations x 3 train-lengths x 24 param-combos (SL 6 x TP 4). Widening the stop grid buys a
    # search that can find an interior optimum -- and honestly costs DSR deflation for the extra
    # trials, which is exactly what this budget feeds.
    assert budget.variations == 12
    assert budget.train_lengths == 3
    assert budget.param_combos == 24
    assert budget.total == 864


def test_scalar_train_months_counts_as_one_length() -> None:
    cfg = SimpleNamespace(
        VARIATIONS={"a": {}, "b": {}},
        TRAIN_MONTHS=24,  # scalar, not a list
        PARAM_GRID={"stop_loss_pct": [0.5, 1.0]},
    )
    budget = study_trial_budget(cfg)
    assert budget.train_lengths == 1
    assert budget.total == 4  # 2 variations x 1 x 2 combos


def test_missing_fields_fall_back_to_one() -> None:
    budget = study_trial_budget(SimpleNamespace())
    assert budget.total == 1  # 1 variation x 1 train-length x 1 (empty grid)
