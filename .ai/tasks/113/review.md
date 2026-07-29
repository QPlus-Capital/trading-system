# Independent review

## Findings

| ID | Severity | Finding | Disposition | Status |
|---|---|---|---|---|
| F1 | P1 | The production-only filter skipped `mutation-critical` for a test-only change, so weakening an assertion could move an unchanged mutant from killed to survived without measuring it. | Reuse the impact engine and mutation policy to select direct and transitive critical tests; fail closed on unparseable tests, unknown dynamic test imports, and analyser-reported unknown dynamic edges; retain skips for unrelated tests and non-code paths. Register generalized pattern F-C585B88406BD37DA0E831614BA1B4FD7C3091876D4D534BE420E31811FEDF70B. | resolved |
| F2 | P1 | The ready Linux job's `UV_NO_SYNC` leaked into the nested dotenv parser probe and produced an unrelated warning, so the first full-quality run failed. | Strip every `UV_*` variable from the test's deliberately clean subprocess environment while retaining the broad no-warning assertion. Register generalized pattern F-93572D2C212D0E4B312F8FD0E922FEE2ADC184F8488E912F65F04CAB70F3296F. | resolved |
| F3 | P1 | The real Mutmut probe skipped by platform rather than by availability of the console script supplied only in the mutation job. | Reuse `mutation_executable` as the availability predicate so full-quality skips without the tool and mutation-self-test executes with it. Register generalized pattern F-77E5BC5E967A83C954858529285468A9CDB1E348B2FF1028B9C57BBDA232815F. | resolved |

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
- Native Linux parity is now observed but not yet green. The `parity-where-applicable` gate remains
  non-zero until a post-fix ready-state run passes.
- Run `30475661794` provided the red proof for F2 and F3: the ready Linux suite failed only on the
  inherited uv flag and the absent Mutmut console script. Locally exporting `UV_NO_SYNC=1`
  reproduced F2 before the fix and passed afterward without narrowing the warning assertion.
- Without Mutmut on the local PATH, F3 now skips with the precise reason `Mutmut console script is
  unavailable`. The mutation workflow remains responsible for executing the same node with
  `mutmut==3.5.0`; no mutation dependency was added to full-quality.
