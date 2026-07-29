# Test plan

| Requirement | Test | RED oracle | Expected GREEN |
|---|---|---|---|
| AC-01 | `tests/test_ci_cost_workflows.py::test_ready_test_node_inventory_is_partitioned_without_loss`; executed Windows/Linux collection diff | Old workflow has no platform partition; Linux collection fails on the unconditional MT5 import | Ready union equals the 1,286-node Windows baseline, with an empty cross-platform diff |
| AC-02 | `tests/test_ci_cost_workflows.py::test_only_the_mt5_boundary_job_uses_windows` | All six CI jobs use Windows | Only the exact MT5 boundary job uses Windows |
| AC-03 | `tests/test_workflow_system_validation.py::test_pytest_blocks_real_mt5_boundaries`; `tests/test_ci_cost_workflows.py::test_mt5_boundary_job_runs_the_exact_windows_node` | No narrow job exists and the module import prevents Linux collection | Exact node remains blocking on Windows and collects safely on Linux |
| AC-04 | `tests/test_ci_cost_workflows.py::test_pull_request_edited_triggers_no_workflow` | Both workflows accept `edited` (CI explicitly, mutation implicitly) | Neither parsed trigger accepts `edited` |
| AC-05, INV-01 | `tests/test_ci_cost_workflows.py::test_mutation_job_runs_for_production_and_direct_critical_test_changes` | Production-only filter rejects `tests/test_live_risk_control.py` | Parsed embedded predicate accepts both a configured production target and a test that imports one directly; docs and `tests/test_gate_consistency.py` still skip |
| AC-05, INV-01 | `tests/test_ci_cost_workflows.py::test_mutation_job_runs_for_a_transitive_critical_test_change`; `tests/test_quality_impact.py::test_changed_tests_are_mapped_to_mutation_targets_transitively` | Production-only and direct-import-only filters reject `tests/test_strategy_sizing_basis.py` | The existing impact graph follows `core.strategies.rsi_wpr_bb` to the configured parameter-schedule target |
| AC-05, INV-01 | `tests/test_ci_cost_workflows.py::test_mutation_job_fails_closed_for_an_unknown_dynamic_test_import`; impact fail-closed fixture tests | Production-only filter rejects an unresolvable changed test | Parse failure, unknown dynamic test import, and an analyser-reported unknown production edge all select mutation |
| AC-06 | `tests/test_ci_cost_workflows.py::test_draft_and_ready_events_select_the_expected_gate_sets` | Draft and ready select the same six jobs | Draft selects fast recipes; ready selects every recipe |
| INV-03 | `tests/test_ci_cost_workflows.py::test_ready_synchronize_runs_the_full_set` | No state split exists | A `synchronize` payload with `draft=false` selects full quality and Windows boundary |
| INV-01, INV-02 | `tests/test_ci_cost_workflows.py::test_full_job_invokes_every_existing_gate_as_a_distinct_step`; `tests/test_gate_consistency.py::test_every_ci_gate_invokes_a_local_just_recipe` | Six jobs rather than one setup; old stable-split assertion | All seven recipes remain exact, separate, and blocking |
| AC-02, AC-07 | `tests/test_ci_cost_workflows.py::test_consolidated_jobs_cache_dependencies_and_preserve_limits` | No cache and six Windows installs | Cache on, one Linux full setup, one Windows platform setup, unchanged ceilings |
| AC-05 | `tests/test_ci_cost_workflows.py::test_mutation_filter_has_no_copied_target_paths` | No filter exists | Parsed Python AST imports and uses the policy/classifier functions; no target path literal exists |
| AC-04, AC-05, AC-06, AC-07 | Real GitHub observations | The first two draft runs exposed Linux resync and mypy/winsound defects | Event/run matrix and billed-minute comparison recorded with run IDs |

## Red-first procedure

1. Commit/record the desired workflow tests against the unchanged workflows.
2. Run the focused file and retain the exact failing assertions in `evidence.md`.
3. Make only workflow and test-boundary changes.
4. Re-run focused, full R3, platform collection, and readiness checks.

The independent-review regression was committed separately at `dc2ca16`. Against the unchanged
filter, the focused workflow file failed exactly three assertions: the direct critical test, named
transitive sizing test, and unknown-dynamic-import test. The implementation starts at `fe2a27e`.
