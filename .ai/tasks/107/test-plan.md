# Test plan

The first implementation parsed selected prose back into facts. Four independent reviews showed
that this moved the defect rather than removing it: a parser necessarily ignored extra rules,
duplicate rows, second tables, neighbouring contradictions, and synonyms outside its frozen region.

The authoritative facts now live in `.ai/quality/workflow-contract.toml`.
`scripts/quality/workflow_contract.py` renders their Markdown blocks. The drift guard compares those
blocks with regenerated output and binds every other byte of the four governed documents through a
non-generated skeleton digest. The document is therefore evidence of the data, not a second source.

Red-first proof for this remediation has three parts:

- the seven already committed third-review counterexamples were previously proven **7/7 RED**
  against their pre-fix module and remain versioned;
- the nine fourth-review cases were run against HEAD `5166b22` before the TOML renderer existed:
  **9 failed / 7 passed**. The nine failures mean every new semantic violation was accepted by the
  old parser. They cover the extra Force row, extra AGENTS start rule, duplicate Start row,
  duplicate activation, second transition table, non-terminal Done meaning, neighbouring gate
  ceiling, and both ready-PR role regressions;
- the fifth review executed three contract-record mutations against `f689ee4`: removing
  `Reviewing` â†’ `Implementing` left **1232 tests passing**, removing the board-tooling activation
  left all documentation tests passing, and adding `Backlog` â†’ `Done` left all documentation tests
  passing. The supplied three-test regression was green on the real contract and red on all three
  mutations.

After the fix, all 19 counterexamples are rejected. The three new TOML mutations regenerate their
document views before the oracle assertion, so only the test-owned transition and activation sets
can reject them.

| Requirement | Primary test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `tests/test_workflow_contract.py::test_rendering_emits_every_machine_contract_record` | RED: no machine model or renderer existed | GREEN: every status, transition, guard, activation and approval step is emitted |
| AC-02 | `tests/test_engineering_docs.py::test_load_bearing_rule_is_stated` | GREEN before this remediation | GREEN: constitution §9 remains load-bearing |
| AC-03 | `tests/test_engineering_docs.py::test_load_bearing_rule_is_stated` | GREEN before this remediation | GREEN: constitution §16 remains load-bearing |
| AC-04 | `tests/test_workflow_contract.py::test_contract_rendering_rejects_semantic_counterexample` | RED: missing-permit and duplicate/extra Start rules passed | GREEN: every supplied builder-boundary mutation is document drift |
| AC-05 | `tests/test_workflow_contract.py::test_workflow_contract_toml_is_valid_and_complete` | RED: approval order lived only in prose | GREEN: ordered approval data is contiguous and `approved` is last |
| AC-06 | `tests/test_quality_validate_task.py::test_every_task_plan_test_reference_collects` | RED: bare stale references were ignored | GREEN: full ids collect; bare names resolve or belong to the exact shrinking legacy set |
| AC-07 | `tests/test_workflow_contract.py::test_workflow_contract_toml_is_valid_and_complete` | RED: additional Start/Resume cases could be ignored | GREEN: the model contains exactly the disjoint Start and Resume records |
| AC-08 | `tests/test_workflow_contract.py::test_no_transition_outside_the_authorized_edge_set_exists` | RED: a required review-loop edge could vanish and an unauthorized `Backlog` â†’ `Done` edge could be added | GREEN: the declared graph equals the test-owned authorized graph in both directions; `test_every_required_transition_is_declared` additionally pins required actor/trigger records |
| AC-09 | `tests/test_workflow_contract.py::test_every_registered_activation_is_declared` | RED: the board-tooling activation could vanish | GREEN: the declared capability/issue registry equals the test-owned required registry in both directions |
| AC-10 | `tests/test_workflow_contract.py::test_no_role_document_says_builder_opens_ready_pull_request` | RED: the permanent negative F3 guard had been deleted | GREEN: all three role documents reject the superseded phrase and the positive draft/review order remains in data |
| INV-01 | `tests/test_engineering_docs.py::test_load_bearing_rule_is_stated` | GREEN before the remediation | GREEN: no immutable safety marker is removed |
| INV-02 | `tests/test_workflow_contract.py::test_workflow_documents_match_the_machine_contract` | RED: neighbouring contradictions were outside parser regions | GREEN: generated blocks and non-generated skeletons exactly match the contract snapshot |

The permanent finding-registry protection is separately guarded by
`tests/test_finding_registry.py::test_every_finding_registry_regression_reference_resolves`. It
fails if any `regression` field names a deleted test, test file, or `just` recipe.
