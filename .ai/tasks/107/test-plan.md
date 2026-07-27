# Test plan

The first version of this plan mapped AC-01 to AC-05 and INV-02 to manual sentence inspection. That
is why every gate was green while independent review found four P1 contradictions in the same
documents (`review.md`, F7). A document two agents execute literally is code; it needs executable
guards.

`tests/test_workflow_contract.py` is that guard set. Red-first evidence for the whole file: run
against the pre-fix documents it reports **6 failed**; against the fixed documents **6 passed**.
The failing run is reproducible with `git stash` on the document changes.

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `tests/test_workflow_contract.py::test_the_state_machine_is_declared_as_a_table_and_is_total` | RED: no transition table existed, so the phases could not be checked for totality | GREEN: every status has a documented way in and out |
| AC-02 | manual: constitution §9 reviewed | N/A: rule did not exist | GREEN: §9 states the class scales gates, artifacts, PR sections and review agents |
| AC-03 | manual: constitution §16 reviewed | N/A: rule did not exist | GREEN: §16 states `codex/<issue>-<slug>`, one worktree per issue, squash on merge |
| AC-04 | `::test_the_builder_guard_separates_starting_from_resuming` | RED: the resume rule named no status and did not exempt the permit | GREEN: start and resume are disjoint; resume is bound to `Implementing`/`Reviewing` and to the absence of the permit |
| AC-05 | manual: `CLAUDE.md` reviewed; ordering also bound by AC-04's test in `AGENTS.md` | N/A: rule did not exist | GREEN: approval section states the order and that `approved` is written last |
| AC-06 | `tests/test_engineering_docs.py`, `test_engineering_workflow_docs.py`, `test_docs_language.py`, `test_docs_architecture_map.py`, `test_claude_runtime_files.py`, `test_github_templates.py` | GREEN before the change | GREEN after: 147 passed |
| AC-07 | `::test_the_builder_guard_separates_starting_from_resuming` | RED: the builder could not resume its own branch after the permit was consumed | GREEN |
| AC-08 | `::test_the_state_machine_is_declared_as_a_table_and_is_total` and `::test_the_review_loop_returns_the_card_to_reviewing` | RED: no table; `Implementing` had no documented return to `Reviewing` | GREEN: table present and total; the review loop closes |
| AC-09 | `::test_capabilities_the_repository_lacks_are_marked_as_not_yet_active` | RED: the contract described the draft-carries-review ordering, the artifact matrix and the methodology reviewer in the present tense, none of which the repository can execute | GREEN: each is named with its activating issue and the rule authoritative until then |
| AC-10 | `::test_no_role_document_says_the_builder_opens_a_ready_pull_request` and `::test_required_gates_are_never_described_as_a_maximum` | RED: both `constitution.md:22` and `AGENTS.md:23` had the builder opening a ready pull request; the Gates step read "no more, no less" | GREEN |
| INV-01 | `tests/test_engineering_docs.py::test_load_bearing_rule_is_stated`, `::test_role_contracts_preserve_exception_and_human_authority`, `::test_direct_to_main_exception_is_R0_only_everywhere` | GREEN before the change | GREEN after: every load-bearing phrase still present in every document that must state it |
| INV-02 | `::test_no_role_document_says_the_builder_opens_a_ready_pull_request`, `::test_required_gates_are_never_described_as_a_maximum`, `::test_the_state_machine_is_declared_as_a_table_and_is_total` | RED: the constitution contradicted itself (roles paragraph versus §11), and the workflow contradicted both the board semantics and the installed tooling | GREEN: the three contradiction classes are each bound by a test |

The three remaining manual rows are honest about what they are. AC-02, AC-03 and AC-05 assert that a
specific rule is stated somewhere; a test matching those sentences would restate the implementation
rather than protect a behaviour, and the load-bearing-phrase guards in
`tests/test_engineering_docs.py` already cover the case that matters — a rule going missing. What
needed executable guards, and now has them, are the properties no sentence-level check can see: a
state machine that is total, documents that do not contradict one another, and a contract that does
not promise capabilities the repository lacks.
