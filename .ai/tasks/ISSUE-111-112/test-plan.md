# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 (#111 AC-01) | `test_exactly_five_workflow_skills_remain` | RED: eight legacy skill names exist | GREEN: exactly the five approved workflow moments exist |
| AC-02 (#111 AC-02) | `test_build_change_is_limited_to_the_explicit_builder_exception` | RED: `build-change` is absent | GREEN: the merged skill grants building only under Jan's explicit exception and grants no review role |
| AC-03 (#111 AC-03) | `test_specify_change_drives_the_issue_and_stops_before_arming` | RED: the skill writes task specs and has no board/approval stop | GREEN: it writes the issue body, drives pre-approval status, and stops until Jan approves |
| AC-04 (#111 AC-04) | `test_review_change_is_fresh_read_only_and_uses_executable_selection` | RED: `review-change` and its executable selector are absent | GREEN: fresh read-only review invokes the production selection command |
| AC-05 (#111 AC-05) | `test_claude_runtime_files_match_the_primary_review_role` | RED: assertions name the retired review and builder skills | GREEN: consistency assertions bind the five new names and four agents |
| AC-06 (#112 AC-01) | `test_methodology_reviewer_is_read_only_and_names_all_five_invariants` | RED: the agent is absent | GREEN: all five section-4 invariants and selection/execution agreement are explicit |
| AC-07 (#112 AC-02) | `test_reviewer_selection_matrix` | RED: no executable selector exists | GREEN: R2 selects exactly code and test reviewers |
| AC-08 (#112 AC-03) | `test_reviewer_selection_matrix` | RED: no executable selector exists | GREEN: R3 research/methodology paths add methodology but not live-money |
| AC-09 (#112 AC-04) | `test_reviewer_selection_matrix` | RED: no executable selector exists | GREEN: R3 live paths add live-money, and mixed paths select all four |
| AC-10 (#112 AC-05) | `test_old_finding_severity_codes_are_absent_from_active_contracts` | RED: active contracts and all 58 patterns use old codes | GREEN: active finding-severity surfaces use only descriptive names |
| AC-11 (#112 AC-06) | `test_task_validator_accepts_new_severities_and_rejects_old_codes` | RED: the validator accepts old codes and rejects new names | GREEN: only the new four-name vocabulary parses |
| INV-01 (#111 INV-01) | `test_build_change_is_limited_to_the_explicit_builder_exception` | RED: four builder skills can drift and no merged-role guard exists | GREEN: the one builder path explicitly prohibits self-review |
| INV-02 (#111 INV-02) | `test_every_review_skill_and_agent_is_read_only` | RED: renamed review surfaces are absent | GREEN: both review skills and all four agents prohibit edits |
| INV-03 (#112 INV-01) | `test_blocking_severity_set_is_unchanged_by_the_migration` | RED: production uses the old vocabulary | GREEN: the first three descriptive severities block exactly as before |
| INV-04 (#112 INV-02) | `test_methodology_reviewer_is_read_only_and_names_all_five_invariants` | RED: the fourth reviewer does not exist | GREEN: every agent keeps the same read-only tool set |

Additional migration and workflow-shape guards:

- `test_severity_migration_changes_only_severity_across_all_58_patterns` compares every record
  against a committed pre-migration fingerprint and requires the exact severity mapping.
- `test_every_finding_registry_regression_reference_resolves` proves every migrated record still
  names executable permanent protection.
- `test_empty_activation_register_renders_and_validates` proves the state reached after #110 and
  this change land in either order.
