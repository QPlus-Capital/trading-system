# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `test_changing_one_stop_creates_a_new_cohort` | RED: `register` raised `NotImplementedError` | GREEN: changed stop bytes produce a different UUID |
| AC-02 | `test_identical_contents_at_different_paths_keep_the_cohort` | RED: `register` raised `NotImplementedError` | GREEN: identical bytes at different paths produce the same UUID |
| AC-03 | `test_changing_signal_code_creates_a_new_cohort` | RED: `register` raised `NotImplementedError` | GREEN: changed signal bytes produce a different UUID |
| AC-04 | `test_two_cohort_result_sets_cannot_be_pooled` | RED: `register` raised `NotImplementedError` | GREEN: pooling raises `CohortMismatchError` |
| AC-05 | `test_live_and_paper_observations_cannot_mix` | RED: `register` raised `NotImplementedError` | GREEN: append and pool both raise `CohortMismatchError` |
| AC-06 | `test_credentials_and_account_numbers_never_reach_disk` | RED: `register` raised `NotImplementedError` | GREEN: rejected values never occur in any written file |
| AC-07 | `test_changed_inputs_create_without_rewriting_the_old_cohort`; `test_tampered_cohort_definition_fails_closed` | RED: `register` raised `NotImplementedError` | GREEN: old bytes stay unchanged and tampering raises |
| AC-08 | `test_schema_and_decimal_observation_round_trip_exactly`; `test_json_number_observation_is_rejected_as_non_decimal_storage` | RED: implementation absent, then numeric JSON was accepted | GREEN: required fields/exact Decimal text round-trip and JSON numbers fail closed |
| AC-09 | `test_forward_cohort_hashing_is_path_invariant`; `test_every_hashed_input_participates_in_forward_cohort_identity`; Linux mutation workflow | RED: hash/identity functions raised `NotImplementedError`; mutation target has no baseline | GREEN: properties pass and mutation ratchet records the measured target |
| INV-01 | `test_identical_contents_at_different_paths_keep_the_cohort`; `test_forward_cohort_hashing_is_path_invariant` | RED: hashing absent | GREEN: path relocation is identity-neutral |
| INV-02 | `test_changed_inputs_create_without_rewriting_the_old_cohort`; `test_tampered_cohort_definition_fails_closed` | RED: persistence absent | GREEN: definition bytes are create-only and tampering is refused |
| INV-03 | `test_two_cohort_result_sets_cannot_be_pooled`; `test_live_and_paper_observations_cannot_mix` | RED: pooling guard absent | GREEN: both mismatches raise |
| INV-04 | `test_schema_and_decimal_observation_round_trip_exactly`; `test_json_number_observation_is_rejected_as_non_decimal_storage` | RED: numeric JSON was accepted | GREEN: Decimal strings are exact and numeric JSON is refused |
| INV-05 | `test_credentials_and_account_numbers_never_reach_disk` | RED: identifier guard absent | GREEN: only canonical non-zero UUID identifiers reach disk |
| INV-06 | full regression suite and changed-path audit | N/A: scope invariant | GREEN: no stage/live/report consumer changed and historical figures are untouched |

The focused tests are first run while `research.forward_test_registry` does not exist. Every
acceptance test must fail at collection before implementation, establishing one shared RED state.
The hashing and identity properties are also added to the deterministic property suite and are
expected to fail at collection before the module exists.
