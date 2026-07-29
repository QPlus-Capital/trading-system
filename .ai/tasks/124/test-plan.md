# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `tests/test_quality_process_scaling.py::test_pr_ready_scales_task_artifacts_by_risk` | RED: collection failed because the risk-scaled APIs did not exist | GREEN: pending implementation |
| AC-02 | `tests/test_quality_process_scaling.py::test_pr_body_requires_exact_risk_class_sections` | RED: collection failed because the risk-scaled APIs did not exist | GREEN: pending implementation |
| AC-03 | `tests/test_quality_process_scaling.py::test_validate_task_schema_has_no_spec_and_scales_files` | RED: collection failed because the risk-scaled APIs did not exist | GREEN: pending implementation |
| AC-04 | `tests/test_quality_process_scaling.py::test_hook_allows_draft_creation_and_blocks_unready_transition` | RED: `pr_transition_decision` could not be imported | GREEN: pending implementation |
| AC-05 | `tests/test_finding_registry_split.py::test_independent_finding_files_merge_in_either_order` | RED: `scripts.quality.finding_registry` did not exist | GREEN: pending implementation |
| AC-06 | `tests/test_finding_registry_split.py::test_finding_ids_are_derived_and_unclaimable` | RED: `scripts.quality.finding_registry` did not exist | GREEN: pending implementation |
| INV-01 | `tests/test_quality_process_scaling.py::test_r3_gate_list_is_unchanged` | RED: suite could not collect before the process API existed | GREEN: pending implementation |
| INV-02 | `tests/test_finding_registry_split.py::test_migration_preserves_all_legacy_ids_and_content` | RED: split-registry loader did not exist | GREEN: pending implementation |
| INV-03 | `tests/test_quality_process_scaling.py::test_readiness_never_uses_less_than_classifier_gate_set` | RED: suite could not collect before the process API existed | GREEN: pending implementation |

The PR-section oracle follows the ratified workflow table:
R0/R1/R2/R3 = 5/8/14/20. This resolves AC-02's stale “R1/five” wording without
changing a contract fact.
