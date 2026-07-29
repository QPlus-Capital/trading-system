# Test plan

The first version of this plan mapped AC-01 to AC-05 and INV-02 to manual sentence inspection. That
is why every gate was green while independent review found four P1 contradictions in the same
documents (`review.md`, F7). A document two agents execute literally is code; it needs executable
guards.

`tests/test_workflow_contract.py` contains seven primary guards and one parametrized oracle that
applies seven independently supplied semantic counterexamples to temporary document copies.
Red-first for the third-review remediation: all **7 counterexample cases failed** because the old
guards did not raise; after the structural fact parsers landed, all **7 passed**. The separate
stale-node-id guard also failed before this map was corrected and passes afterward.

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `tests/test_workflow_contract.py::test_the_state_machine_declares_every_required_transition` | RED: no transition table existed, so the phases could not be checked for totality | GREEN: the complete source/target/actor/trigger set equals the allowlist |
| AC-02 | manual: constitution §9 reviewed | N/A: rule did not exist | GREEN: §9 states the class scales gates, artifacts, PR sections and review agents |
| AC-03 | manual: constitution §16 reviewed | N/A: rule did not exist | GREEN: §16 states `codex/<issue>-<slug>`, one worktree per issue, squash on merge |
| AC-04 | `tests/test_workflow_contract.py::test_the_builder_guard_separates_starting_from_resuming` | RED: the resume rule named no status and did not exempt the permit | GREEN: exact Start and Resume condition/action tuples match in both documents |
| AC-05 | manual: `CLAUDE.md` reviewed; ordering also bound by AC-04's test in `AGENTS.md` | N/A: rule did not exist | GREEN: approval section states the order and that `approved` is written last |
| AC-06 | `tests/test_engineering_docs.py::test_load_bearing_rule_is_stated` and `tests/test_quality_validate_task.py::test_every_task_plan_test_reference_collects` | GREEN before the contract change; RED after stale test names were introduced | GREEN: load-bearing markers remain and every versioned pytest node id collects |
| AC-07 | `tests/test_workflow_contract.py::test_the_builder_guard_separates_starting_from_resuming` and `tests/test_workflow_contract.py::test_contract_guard_rejects_semantic_counterexample` | RED: the builder could not resume its own branch; later, changing Start to permit `approved` absent was not detected | GREEN: exact Start/Resume facts plus the committed counterexample |
| AC-08 | `tests/test_workflow_contract.py::test_the_state_machine_declares_every_required_transition` and `tests/test_workflow_contract.py::test_the_review_loop_has_a_declared_way_back_to_reviewing` | RED: no table; later, a wrong actor and an unauthorized edge were accepted | GREEN: exact transition quadruples; the two review handovers remain distinct |
| AC-09 | `tests/test_workflow_contract.py::test_every_unavailable_capability_carries_an_owner_and_a_fallback` and `tests/test_workflow_contract.py::test_the_transitional_review_rule_is_stated_at_constitution_precedence` | RED: wrong activation owners and inverted branch-review semantics were accepted | GREEN: exact capability/owner/fallback map and equal normalized transitional facts |
| AC-10 | `tests/test_workflow_contract.py::test_the_builder_never_reaches_ready_before_the_independent_review` and `tests/test_workflow_contract.py::test_required_gates_are_a_minimum_and_never_a_ceiling` | RED: ready-order synonyms and an unlisted ceiling phrase evaded the old recognizers | GREEN: one canonical ready fact and one exact lower-bound gate fact |
| INV-01 | `tests/test_engineering_docs.py::test_load_bearing_rule_is_stated`, `tests/test_engineering_docs.py::test_role_contracts_preserve_exception_and_human_authority`, and `tests/test_engineering_docs.py::test_direct_to_main_exception_is_R0_only_everywhere` | GREEN before the change | GREEN after: every load-bearing phrase still present in every document that must state it |
| INV-02 | `tests/test_workflow_contract.py::test_the_transitional_review_rule_is_stated_at_constitution_precedence`, `tests/test_workflow_contract.py::test_the_state_machine_declares_every_required_transition`, and `tests/test_workflow_contract.py::test_contract_guard_rejects_semantic_counterexample` | RED: constitution/workflow contradictions and incomplete transition facts were accepted | GREEN: both documents normalize to the same procedure and every supplied inversion is rejected |

The three remaining manual rows are honest about what they are. AC-02, AC-03 and AC-05 assert that a
specific rule is stated somewhere; a test matching those sentences would restate the implementation
rather than protect a behaviour, and the load-bearing-phrase guards in
`tests/test_engineering_docs.py` already cover the case that matters — a rule going missing. What
needed executable guards, and now has them, are the properties no sentence-level check can see: a
state machine that is total, documents that do not contradict one another, and a contract that does
not promise capabilities the repository lacks.
