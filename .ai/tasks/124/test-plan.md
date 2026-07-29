# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `tests/test_quality_process_scaling.py::test_pr_ready_scales_task_artifacts_by_risk` | RED: collection failed because the risk-scaled APIs did not exist | GREEN: R1 needs no task files; an R3 task missing `impact.md` is rejected |
| AC-02 | `tests/test_quality_process_scaling.py::test_pr_body_requires_exact_risk_class_sections` | RED: collection failed because the risk-scaled APIs did not exist | GREEN: exact R0/R1/R2/R3 counts are 5/8/14/20 and an omitted required section fails |
| AC-03 | `tests/test_quality_process_scaling.py::test_validate_task_schema_has_no_spec_and_scales_files` | RED: collection failed because the risk-scaled APIs did not exist | GREEN: `spec.md` is absent; R2 and R3 have their exact required file sets |
| AC-04 | `tests/test_quality_process_scaling.py::test_hook_allows_draft_creation_and_blocks_unready_transition` | RED: `pr_transition_decision` could not be imported | GREEN: draft creation and pushes pass; non-draft creation and unready `gh pr ready` fail |
| AC-05 | `tests/test_finding_registry_split.py::test_independent_finding_files_merge_in_either_order` | RED: `scripts.quality.finding_registry` did not exist | GREEN: real Git merges succeed A→B and B→A with both findings present |
| AC-06 | `tests/test_finding_registry_split.py::test_finding_ids_are_derived_and_unclaimable` | RED: `scripts.quality.finding_registry` did not exist | GREEN: content digest derives file and ID; a stored `id` field fails closed |
| INV-01 | `tests/test_quality_process_scaling.py::test_r3_gate_list_is_unchanged` | RED: suite could not collect before the process API existed | GREEN: all 14 pre-change R3 gate names match literally and in order |
| INV-02 | `tests/test_finding_registry_split.py::test_migration_preserves_all_legacy_ids_and_content` | RED: split-registry loader did not exist | GREEN: all 55 V1 IDs resolve to field-for-field identical content |
| INV-03 | `tests/test_quality_process_scaling.py::test_readiness_never_uses_less_than_classifier_gate_set` | RED: suite could not collect before the process API existed | GREEN: R0–R3 readiness returns exactly the production classifier's cumulative gates |

The PR-section oracle follows the ratified workflow table:
R0/R1/R2/R3 = 5/8/14/20. This resolves AC-02's stale “R1/five” wording without
changing a contract fact.
