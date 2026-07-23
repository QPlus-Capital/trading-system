# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `test_efficacy_is_suppressed_until_both_endpoint_conditions_hold` | RED: decision module is absent | GREEN: every calendar/trade shortfall returns bound-free `NO_DECISION` |
| AC-02 | `test_completed_cohort_classifies_pass_fail_and_inconclusive`; `test_equality_is_inconclusive` | RED: decision module is absent | GREEN: strict lower/upper comparisons exhaust the endpoint states |
| AC-03 | `test_futility_requires_both_interim_conditions_and_upper_99_below_zero`; `test_futility_equality_does_not_stop` | RED: decision module is absent | GREEN: only the exact early-stop rule yields `FUTILITY_STOP` |
| AC-04 | `test_daily_threshold_is_exact_decimal_and_rejects_invalid_counts` | RED: threshold function is absent | GREEN: exact Decimal formula and denominator guards pass |
| AC-05 | `test_selected_block_and_all_sensitivity_lengths_are_reported`; `test_public_defaults_match_p04` | RED: decision module is absent | GREEN: selected production and 5/10/20/60 diagnostics use fixed defaults |
| AC-06 | `test_as_of_cutoff_excludes_later_observations`; signature/default introspection | RED: decision module is absent | GREEN: future observations are excluded and both external inputs are mandatory |
| AC-07 | `test_operational_stop_does_not_change_statistics_or_registry_bytes` | RED: decision module is absent | GREEN: status differs but result/data do not |
| AC-08 | `test_no_pre_endpoint_return_path_exposes_efficacy`; `test_dashboard_has_no_forward_decision_consumer` | RED: decision module is absent | GREEN: public state space and absent dashboard wiring preserve suppression |
| AC-09 | `test_clustered_power_fixture_reproduces_detection_horizons` | RED: power fixture has no decision bound to exercise | GREEN: seeded clustered fixture stays within both year ranges |
| AC-10 | full R3 gates and Linux mutation workflow | RED: new decision target is absent from the ratchet | GREEN: every required gate and measured target passes |
| INV-01 | `git diff --exit-code origin/main -- research/forward_test_registry.py research/portfolio/resample.py` | N/A: scope invariant | GREEN: both reviewed dependencies are byte-unchanged |
| INV-02 | `test_efficacy_is_suppressed_until_both_endpoint_conditions_hold`; endpoint property | RED: decision module is absent | GREEN: conjunction holds at all tested boundaries |
| INV-03 | `test_no_pre_endpoint_return_path_exposes_efficacy` | RED: decision module is absent | GREEN: no early result contains efficacy analysis |
| INV-04 | `test_decision_statistics_are_decimal_and_source_has_no_float_statistics`; Decimal property | RED: decision module is absent | GREEN: exact values and source-level guard pass |
| INV-05 | `test_futility_requires_both_interim_conditions_and_upper_99_below_zero` | RED: decision module is absent | GREEN: futility remains a distinct enum state |
| INV-06 | `test_sensitivity_cannot_change_the_production_verdict` | RED: decision module is absent | GREEN: only selected-block bounds drive classification |
| INV-07 | `test_operational_stop_does_not_change_statistics_or_registry_bytes` | RED: decision module is absent | GREEN: registry bytes and live/trading paths remain untouched |
