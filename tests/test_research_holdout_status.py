"""Guard: the study config must keep declaring how trustworthy its holdout actually is (#12).

The holdout was reserved as the honest out-of-sample check, but deploy decisions (per-market
stops, the manual silver pick, the risk policy) were made after inspecting it, which makes it
in-sample for the deployed config. The codebase previously asserted the opposite. These tests
exist so that disclosure cannot quietly disappear again -- if the holdout is ever genuinely
re-established, flip HOLDOUT_CONTAMINATED and update these expectations deliberately.
"""

from pathlib import Path

from research.engine.config import load_config_module

CFG = load_config_module(Path("research/config/robustness.py"))


def test_the_holdout_declares_its_contamination_status() -> None:
    assert hasattr(CFG, "HOLDOUT_CONTAMINATED"), "the holdout's status must be stated explicitly"
    assert CFG.HOLDOUT_CONTAMINATED is True  # deploy decisions were made after seeing it


def test_a_freeze_date_anchors_the_clean_forward_holdout() -> None:
    # The honest OOS evidence is the live record from here on, so the date must be pinned.
    assert len(str(CFG.DEPLOY_FREEZE_DATE)) == 10  # YYYY-MM-DD


def test_manual_decisions_are_inventoried_as_trials() -> None:
    # Each hand-made choice enlarges the effective search space a deflated Sharpe must account
    # for; an empty ledger would understate it.
    assert len(CFG.MANUAL_TRIALS) >= 3


def test_the_strategy_doc_does_not_claim_the_stop_is_a_free_choice() -> None:
    # The old wording ("These do not change which trades happen") was used to justify treating
    # the holdout as clean despite the stop being fitted over it.
    doc = Path("docs/strategies/rsi_wpr_bb.md").read_text(encoding="utf-8")
    assert "These do not change *which* trades happen." not in doc
    assert "HOLDOUT_CONTAMINATED" in doc  # points the reader at the real status
