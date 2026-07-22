# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `tests/test_quality_test_support.py` | RED: `tests.support` absent at collection | GREEN: every helper passes a valid case and rejects a counterexample |
| AC-02 | `tests/test_quality_properties.py` plus Windows CI replay | RED: support strategies absent; property module could not collect | GREEN: seven target areas pass twice under seed 20260721 |
| AC-03 | real Mutmut weakened-test probe plus `just mutation-critical` | RED: mutation module absent; no runner or baseline | GREEN: weakening creates a survivor, the ratchet rejects it, and the Linux baseline passes |
| AC-04 | dependency/compatibility guards and `just check` | RED: Hypothesis absent; Mutmut exits on native Windows | GREEN: Hypothesis locked, Linux job documented, all normal gates pass |
| INV-01 | `test_fast_scope_reuses_the_classifier_and_selects_changed_r3_targets` | RED: mutation selection absent | GREEN: production classifier model is injected and used |
| INV-02 | `test_policy_names_every_required_critical_scope` and policy review | RED: no bounded policy | GREEN: exactly eight pure critical files are configured |
| INV-03 | `test_stricter_live_limits_never_admit_a_trade_weaker_limits_block` | RED: no generated monotonicity guard | GREEN: 75 deterministic generated examples pass |
| INV-04 | production-path diff review and regression suite | BASELINE: no production edits | GREEN: production source remains byte-identical and full tests pass |
