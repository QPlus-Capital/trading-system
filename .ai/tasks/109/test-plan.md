# Test plan

## Traceability

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `tests/test_quality_classify.py::test_issue_109_classifications` | RED for both `.claude` executable-contract cases | GREEN |
| AC-02 | `tests/test_quality_classify.py::test_issue_109_adds_the_claude_catch_all_without_replacing_settings` | RED: catch-all absent; exact settings rule present | GREEN |
| AC-03 | `tests/test_quality_classify.py::test_issue_109_classifications` | RED: architecture map is R0 | GREEN |
| AC-04 | `tests/test_quality_classify.py::test_issue_109_classifications` | GREEN before change by design: README must remain R0 | GREEN |
| AC-05 | `tests/test_quality_classify.py::test_issue_109_removes_the_dead_workflow_r2_rule` | RED: duplicate R2 rule remains | GREEN |
| INV-01 | `tests/test_engineering_docs.py::test_money_path_classifies_as_R3` | RED for the newly listed executable `.claude` paths | GREEN |
| INV-02 | `tests/test_quality_classify.py::test_issue_109_never_lowers_a_tracked_path_and_only_upgrades_its_scope` | RED: required post-change rules absent | GREEN |
| INV-03 | `tests/test_quality_classify.py::test_removing_the_dead_workflow_r2_rule_changes_no_tracked_path_class` | GREEN: max-wins already makes the dead rule harmless | GREEN |
| INV-04 | scoped production and mutation-baseline diff | GREEN before change | GREEN |

## Red-first interpretation

AC-04 and INV-03 are unchanged-behaviour regressions and therefore correctly pass against the
pre-change model. Claiming that they failed would fabricate evidence. The changing postconditions
AC-01, AC-02, AC-03, AC-05, INV-01, and INV-02 must fail before the TOML edit.

## Adversarial cases

- A catch-all that replaces rather than supplements `.claude/settings.json`.
- A typo broadening `.claude/**` to a repository-wide glob.
- A removed rule that lowers any tracked path despite appearing shadowed.
- A hand-picked inventory that omits a newly tracked executable contract.
- Expected classes derived from the TOML under test instead of literal assertions.
- A missing/empty tracked tree that vacuously passes.

## Repository gates

- `just check`
- `just check-properties`
- `just check-invariants`
- `just check-security`
- task validation, impact, and `pr-ready`
- Linux critical mutation only if the touched-critical policy selects a production mutation target
