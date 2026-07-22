# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `tests/test_github_templates.py` PR template and validator cases | RED: templates and validator absent | GREEN: required native metadata, body fields, completed checklists, task readiness, and evidence binding pass |
| AC-02 | `tests/test_gate_consistency.py` split, recipe, pin, concurrency, and R3-trigger cases | RED: monolithic commands, unpinned actions, no split | GREEN: seven stable checks, local recipes, SHA pins, edited-body trigger, cancellation, and no path filters pass |
| AC-03 | `tests/test_quality_security.py` real fake-secret/clean scans and recipe wiring | RED: security module and tools absent; recipe is a stub | GREEN: fake AWS key blocks without disclosure, clean content passes, and all security classes bind |
| AC-04 | `tests/test_workflow_system_validation.py` plus readiness/validator severity and evidence matrix | RED: P3/system orchestration coverage absent | GREEN: severity, manual R3 upgrade, missing/failed/stale evidence, and fail-closed MT5 boundary pass |
| AC-05 | `tests/test_engineering_workflow_docs.py` exact branch-protection and policy contracts | RED: all three documents absent | GREEN: exact status contexts and reviewer/session policies pass; full repository gate green |
| INV-01 | classifier/readiness delegation and `discover_task_id` tests | RED: split and validator absent | GREEN: one classifier and existing task/readiness paths are invoked |
| INV-02 | `test_every_ci_gate_invokes_a_local_just_recipe` and no-hidden-logic test | RED: CI duplicates commands directly | GREEN: every quality decision invokes a named local recipe |
| INV-03 | no-live/network import test plus autouse MT5 boundary | RED: real MT5 functions were unguarded in pytest | GREEN: unmocked terminal/account operations raise before external interaction |
| INV-04 | `test_r3_governance_changes_cannot_be_path_filtered_out` | RED: mutation workflow had an incomplete path filter | GREEN: full CI and Linux mutation run for every PR, so R3 cannot be omitted |
| INV-05 | redacted result and CLI tests | RED: scanner absent | GREEN: only path, line, and detector render; credential content never does |
