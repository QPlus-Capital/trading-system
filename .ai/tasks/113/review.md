# Independent review

## Findings

| ID | Severity | Finding | Disposition | Status |
|---|---|---|---|---|
| F1 | P1 | The production-only filter skipped `mutation-critical` for a test-only change, so weakening an assertion could move an unchanged mutant from killed to survived without measuring it. | Reuse the impact engine and mutation policy to select direct and transitive critical tests; fail closed on unparseable tests, unknown dynamic test imports, and analyser-reported unknown dynamic edges; retain skips for unrelated tests and non-code paths. Register generalized pattern F-056. | resolved |

## Dispositions

- Red-first commit `dc2ca16` proves the old predicate returned false for
  `tests/test_live_risk_control.py`, `tests/test_strategy_sizing_basis.py`, and the unknown-dynamic
  `tests/test_research_stages.py` fixture.
- Implementation commit `fe2a27e` calls `changed_tests_exercise_targets` from the embedded workflow
  predicate. The helper uses `_facts` for direct and fail-closed test analysis and
  `analyze_impact` for the transitive graph and unknown production edges.
- The focused workflow/impact set passes 32 tests. `README.md`, `.ai/`, workflow-only, and
  `tests/test_gate_consistency.py` inputs remain false; direct and transitive critical tests return
  true.
- The review's verified-sound findings remain unchanged: platform split, consolidation, removed
  `edited`, `ready_for_review`, draft condition, cache, production-policy lookup, and evidence
  honesty are retained.
- Native Linux parity remains unobserved. The `parity-where-applicable` gate is still non-zero and
  must not be claimed green before the reviewed ready transition.
