# Adversarial review

## Findings

| ID | Severity | Finding | Disposition | Status |
|---|---|---|---|---|
| F1 | P1 | `AGENTS.md:54-60` and `docs/engineering/workflow.md:133-138` make resumption impossible. A first build consumes `approved` only after moving the card to `Implementing`; the next Codex session is nevertheless told to refuse unless the card is still `Ready to Implement` and `approved` is still present. The adjacent “resume” sentence has no precedence rule that makes it reachable. Concrete failure: a nine-hour build yields or a review sends the card back to `Implementing`; `implement #107` then refuses the exact branch it is required to resume. Specify two disjoint guards: new work requires the unconsumed permit; an existing issue branch/PR resumes only after validating ownership and an allowed in-progress status. Add a state-table test covering new start, interrupted resume, review-fix resume, and an unrelated/stale branch. | Builder must amend the contract and add executable state coverage. | resolved |
| F2 | P1 | `docs/engineering/workflow.md:152-190` declares an operative draft/review/artifact matrix that the repository cannot execute. Today `scripts/quality/hooks/decisions.py:210-221` blocks `gh pr create` whenever `pr_ready` is false, `.ai/quality/task-artifacts.toml:2` still requires all five files for every class, and `.claude/agents/` has no methodology reviewer. Thus a draft cannot carry the missing review, an R0/R1 change cannot follow the “no artifact files” row through readiness, and an R3 research review cannot run the required agent. The evidence acknowledges only the first bootstrap failure; #109/#112 are future work, not current capabilities. Either land the dependencies atomically or state a bounded activation/transition rule that keeps the legacy procedure authoritative until each prerequisite lands. Regression: exercise the real pre-Bash decision, task validator/readiness path for R0-R3, and reviewer selection against the installed agent files. | Builder must remove the impossible immediate contract or land its prerequisites. | resolved |
| F3 | P1 | The highest-precedence contract still says Codex “opens the ready pull request” (`docs/engineering/constitution.md:20-22`), repeated in `AGENTS.md:21-23`, while constitution §11 and the new workflow require Codex to open a draft and mark it ready only after independent review. A literal reader can therefore skip the draft review path while still obeying the constitution, violating INV-02. Replace the stale role summary and add a negative consistency assertion that neither role contract nor the constitution reintroduces “opens … ready pull request.” | Builder must reconcile the load-bearing role summaries. | resolved |
| F4 | P1 | The authoritative issue #107 still requires `arm:implement` in AC-04/AC-05, but `.ai/tasks/107/spec.md:42-45` and all four changed contracts silently replace it with `approved`. The new constitution itself says the issue body is the specification and that any approved-spec change must return through approval; there is no issue comment or updated issue body recording that decision. As written, AC-04 and AC-05 fail even though the repository happens to contain only the new label. Update the issue body, present the changed permit name to Jan, and record reapproval before treating `approved` as the accepted requirement. A validation guard should compare the approved issue AC/INV text used for the build with the task trace instead of letting a local `spec.md` redefine it. | Requires Jan's explicit reapproval of the changed issue specification. | resolved |
| F5 | P2 | `docs/engineering/workflow.md:145-151` says to run the gates of the risk class “no more, no less.” The risk model and constitution define cumulative **mandatory minimums**, while relevant extra checks remain necessary for secrets, platform-specific behaviour, or an unusual dependency edge. Literal execution can suppress a useful safety check merely because it is not listed in the class. Say “at least the mandatory gates, plus any applicable scoped verification”; only process artifacts/required gates should scale down. Add a consistency test that the workflow never describes required gates as a maximum. | Builder must correct the unsafe maximum wording. | resolved |
| F6 | P2 | The new state machine loses its board truth after review remediation. `docs/engineering/workflow.md:200-204` moves a blocking finding to `Implementing`, then commands a complete rereview after the fix without any transition back to `Reviewing`. The card can remain `Implementing` while Claude is reviewing, contradicting the board's declared single-source meaning and leaving AC-01 incomplete. Add the explicit Codex transition to `Reviewing` after pushing review fixes, and include it in the transition table/test. | Builder must close the missing review-loop transition. | resolved |
| F7 | P2 | `.ai/tasks/107/test-plan.md:10-17` maps AC-01 through AC-05 and INV-02 only to manual sentence inspection, despite the new workflow's own rule that every AC/INV maps to exactly one named test and R3 requires a red proof. That is why all focused tests pass while F1-F6 survive. Add red-first behavioural/document-contract tests for the state transitions, permit consumption/resume, draft-vs-ready hook boundary, artifact matrix, installed reviewer selection, and cross-document stale phrases. The changed marker in `tests/test_engineering_docs.py:85-88` is appropriate and does not itself weaken the revised readiness rule; the gap is that it is the only semantic guard added. | Builder must add executable guards that fail on the current contradictions. | resolved |

## Acceptance criteria trace

| Requirement | Result | Evidence |
|---|---|---|
| AC-01 | **Fail** | All six headings exist and usually name actor/place/status, but the resume transition deadlocks (F1) and the blocking-review loop never returns the card to `Reviewing` (F6). The resulting state machine is neither total nor executable. |
| AC-02 | **Text present, operationally fail** | Constitution §9 says risk scales gates, artifacts, PR sections, and reviewers. Current validators and installed reviewers do not implement that table (F2), and “no more” incorrectly turns minimum gates into a maximum (F5). |
| AC-03 | **Pass** | Constitution §16 states one issue branch/worktree, `codex/` or `claude/` naming, and squash-on-merge. |
| AC-04 | **Fail** | `AGENTS.md` contains the intended ordering for `approved`, but issue #107 still specifies `arm:implement`; the approved source requirement was not updated (F4). The resume case also contradicts the permit guard (F1). |
| AC-05 | **Fail** | `CLAUDE.md` correctly says Jan explicitly approves and `approved` is written last, but the authoritative issue still requires `arm:implement` (F4). |
| AC-06 | **Pass in the intended sense** | The focused governance/runtime/language suite passes: 138 tests. `tests/test_engineering_docs.py` changed one marker, so “unchanged” is not literal; the replacement correctly guards the revised ready-for-review boundary and removes no assertion. F7 covers the missing new semantic guards. |

## Invariant trace

| Requirement | Result | Evidence |
|---|---|---|
| INV-01 | **Pass** | The immutable live-trade, risk-limit, numeric-type, holdout, signal-parity, secret, English, authorship, human-authority, and no-autonomous-R3-merge rules remain inline. The focused consistency suite confirms their markers. |
| INV-02 | **Fail** | The constitution/AGENTS ready-PR summary contradicts §11/workflow (F3); the new workflow contradicts current executable tooling and installed reviewers (F2); and its state transitions contradict the board meanings (F1/F6). Constitution precedence does not repair contradictions inside the constitution itself. |

## Counterexamples attempted

1. New issue with valid `Ready to Implement` + `approved` + `risk:Rn`: start ordering is fail-closed.
2. Interrupted build after the permit is consumed: cannot resume under the written guard (F1).
3. Blocking review finding followed by a fix: card never returns to `Reviewing` (F6).
4. Draft creation before review: current pre-Bash hook blocks it because review/readiness are red (F2).
5. R1 issue following the no-artifact row: current task discovery/readiness has no task to validate (F2).
6. R3 research issue: required methodology reviewer is not installed (F2).
7. Extra relevant security/platform check: “no more” forbids it literally (F5).
8. Cross-document search for stale ready-PR wording: found in the constitution and AGENTS (F3).
9. Live GitHub verification: project 1 exists, the token has `project` scope, all seven statuses
   exist, and the five documented labels exist. Board/label existence is sound.
10. Load-bearing marker audit: the single test-marker change correctly follows the intended
    draft/ready boundary and removes no assertion.
11. `uv run pytest -q tests/test_engineering_docs.py tests/test_engineering_workflow_docs.py
    tests/test_docs_language.py tests/test_claude_runtime_files.py`: 138 passed.
12. `uv run python -m scripts.quality.pr_ready 107 --base origin/main`: NOT READY; beyond the
    intentionally missing review, evidence is stale because the final permit-label commit changed
    the contracts/spec/test-plan after the recorded evidence HEAD.

## Dispositions

Every finding was independently verified against the documents before being accepted; none was taken
on trust. All seven are resolved in one change, and each is bound by a named test in
`tests/test_workflow_contract.py` that fails against the pre-fix documents (6 failed / 6 passed,
recorded in `evidence.md`).

| ID | Disposition |
|---|---|
| F1 | Confirmed. The guard is now two disjoint rules. **Start** requires `Ready to Implement`, `approved` and `risk:Rn`. **Resume** requires only an existing branch or pull request for the issue and a card in `Implementing` or `Reviewing`, explicitly **without** a permit. Both `AGENTS.md` and the workflow state it; `test_the_builder_guard_separates_starting_from_resuming` binds the resume rule to a named in-progress status and to the absence of the permit, so a bare "resume it rather than starting again" cannot return. |
| F2 | Confirmed. A **Not yet active** table now names each part of the contract the repository cannot execute, the issue that activates it, and the rule that is authoritative until then — draft-carries-the-review and the artifact matrix (#109), tooling-performed transitions (#110), the methodology reviewer and the plain-language severities (#112). A row leaves the table in the same change that lands its dependency. `test_capabilities_the_repository_lacks_are_marked_as_not_yet_active` binds it. |
| F3 | Confirmed. `constitution.md` and `AGENTS.md` had the builder opening the *ready* pull request while §11 required a draft. Both role summaries now state draft-first and ready-only-after-review. `test_no_role_document_says_the_builder_opens_a_ready_pull_request` is a negative assertion across all three role documents, so the wording cannot be reintroduced. |
| F4 | Confirmed, and it required a human decision, not a fix. The label rename reached the contracts without passing back through the approval that the same change had just made mandatory. Jan was shown the discrepancy and reapproved explicitly. Issue #107 now specifies `approved` in AC-04 and AC-05, and carries AC-07 to AC-10 for the criteria this review exposed as missing. |
| F5 | Confirmed. "those of the risk class — no more, no less" made a mandatory minimum into a ceiling and would have suppressed a relevant secret, platform or dependency check. The step now reads "at least those of the risk class, plus any scoped check that applies". `test_required_gates_are_never_described_as_a_maximum` binds both halves. |
| F6 | Confirmed. The review loop had no way back: a blocking finding moved the card to `Implementing` and nothing returned it. Codex now moves it back to `Reviewing` when it pushes the fix. Bound twice — by `test_the_review_loop_returns_the_card_to_reviewing` and by the totality check on the new transition table. |
| F7 | Confirmed, and it is the root cause of the other six. The test plan mapped AC-01 to AC-05 and INV-02 to manual sentence inspection, which is why every gate was green while six contradictions survived. `tests/test_workflow_contract.py` replaces that with six executable guards, and the transitions are now declared as a table rather than as prose — prose describes one transition at a time, which is exactly how a missing one hides. |

**Root cause and generalised pattern.** All six substantive defects share one mechanism: a procedural
document was verified by reading it, and reading a document one section at a time cannot reveal a
contradiction between two sections, an unreachable state, or a promise the repository cannot keep.
The generalised pattern for the finding registry: *a document that two agents execute literally is
code, and needs executable guards — a totality check over its state machine, negative assertions
against superseded wording, and an explicit register of the capabilities it assumes but does not yet
have.*

The pattern is registered for the review of every future governance change, not only this one.

---

## Complete independent re-review of `c3cbf6a`

This is a whole-change re-review after the material remediation, not a review of the seven fixes in
isolation. The comparison base is `origin/main` at
`8b75ff061c924e2dc415d70ad90700f79a15540c`. The earlier seven defects were reproduced in the prior
review and their textual fixes are present. The changed marker in
`tests/test_engineering_docs.py` follows the intended draft-versus-ready rule and removes or weakens
no assertion.

**Result: NOT READY.** No P0 was found. Two P1 and two P2 findings remain. In particular, the six
new guards do not bind the properties their names and docstrings claim to protect.

### Re-review findings

| ID | Severity | Finding | Concrete failure scenario | Required correction | Status |
|---|---|---|---|---|---|
| RR-F1 | P1 | `docs/engineering/workflow.md:289-304` does not make the draft-before-review contract executable and assigns its two load-bearing dependencies to the wrong issue. Constitution §11 (`docs/engineering/constitution.md:150-156`), `AGENTS.md:79-86`, `CLAUDE.md:40-46`, and workflow phase 4 require review on a draft PR. The active pre-Bash decision still blocks `gh pr create` before readiness, while the fallback says to review a branch. Because the constitution wins, the lower-precedence fallback cannot suspend §11. Moreover, rows 297-298 say #109 will activate draft creation and artifact scaling, but #109 explicitly makes both non-goals; #124 owns both changes. | The current issue is already in `Reviewing`, but `gh pr list --head claude/trading-dev-workflow-b2e46d --state all` returns `[]`. Inline PR review cannot be delivered, and the board definition "`Reviewing` = a pull request is open" is false. Landing #109 would leave both rows unresolved even though line 303 requires a row to leave with its dependency. | Point the first two rows to #124. Until #124 lands, either amend the higher-precedence constitution and both role contracts to state one explicit temporary branch-review procedure, or land #124 atomically with this contract. Add an executable check against `pr_readiness_decision` and the real artifact matrix, not an issue-number search. | resolved |
| RR-F2 | P1 | All six guards in `tests/test_workflow_contract.py:37-149` are phrase-presence checks that pass under semantic violations of the property they claim to enforce. They therefore do not resolve earlier F7 and give false executable assurance for AC-07 through AC-10. | Executed against temporary mutated documents: (1) removing `Reviewing` from the resume rule passed; (2) saying the builder “opens a pull request and immediately marks it ready before independent review” passed; (3) adding “no other check may run” after “at least” passed; (4) saying the card “must never move back to Reviewing” passed; (5) deleting `Ready to Implement → Implementing` passed; and (6) replacing the activation table with only the heading and `#109, #110, #112` passed. All six guards reported success. | Parse and compare exact contract facts: the complete start/resume truth table including ownership; draft-before-review and ready-after-clean-review ordering; class gates as a lower bound with no ceiling; the positive review-fix transition; the exact required edge set plus terminal restrictions; and one activation record per unavailable capability with the correct owner and fallback. Each test must fail on the corresponding counterexample above. | resolved |
| RR-F3 | P2 | The supposedly total transition table is internally inconsistent at `docs/engineering/workflow.md:270-287`. `any → Blocked` includes `Done`, contradicting “Done is terminal”; `Specifying → Backlog` gives Backlog a predecessor, contradicting “Backlog is the only status with no predecessor”; and the only `Implementing → Reviewing` trigger is opening/pushing a PR, although the active fallback performs review before a PR exists. | A literal agent can move a completed item back to `Blocked`, while another literal agent treats `Done` as terminal. During the current fallback, the card has no documented transition into `Reviewing`, yet issue #107 is in `Reviewing` with no PR. The board cannot be the asserted single source of truth. | Replace `any` with the exact allowed non-terminal sources, correct the Backlog statement (or remove `Specifying → Backlog`), and define the temporary branch-review transitions while that fallback exists. Test exact edges and forbidden edges; status-name source/target coverage is insufficient. | resolved |
| RR-F4 | P2 | The resume boundary differs across the two operative documents. `AGENTS.md:62-65` requires a branch or PR created by a builder for this repository; `docs/engineering/workflow.md:136-140` allows any branch or PR “for this issue”. The guard at `tests/test_workflow_contract.py:37-58` tests neither ownership nor branch identity. | A stale, foreign, or manually created branch associated with an `Implementing` card is resumable under the workflow but must be refused under AGENTS. A literal builder has no single answer, and a wrong branch can be modified silently. | Use the same ownership/identity predicate in both documents and encode start, own interrupted branch, own review-fix branch, unrelated branch, stale branch, and mismatched issue/branch cases as a table-driven guard. | resolved |

### Acceptance-criteria trace on re-review

| Requirement | Result | Evidence |
|---|---|---|
| AC-01 | **Fail** | The six phase sections name actors and actions, but the documented `Reviewing` result is false under the active branch-review fallback, and the state table supplies no corresponding transition (RR-F1/RR-F3). |
| AC-02 | **Pass** | Constitution §9 states that risk class scales gates, artifact files, PR sections, and review subagents, not only merge eligibility. |
| AC-03 | **Pass** | Constitution §16 retains one issue per branch/worktree and squash-on-merge. |
| AC-04 | **Pass in current text** | `AGENTS.md` requires `Ready to Implement`, `approved`, and `risk:Rn`, moves the card first, and then removes the permit. |
| AC-05 | **Pass** | `CLAUDE.md` requires Jan's explicit approval and writes `approved` last. |
| AC-06 | **Pass** | The existing marker change is a faithful update from “open PR” to “mark ready”; no assertion was removed or made conditional. The focused suite passes 153 tests. RR-F2 concerns the six newly added guards, not a weakening of this pre-existing marker. |
| AC-07 | **Text present; executable guard fails** | Start and resume are disjoint in the current prose, but the two documents disagree on branch ownership and the named guard passes after removing one allowed resume state (RR-F2/RR-F4). |
| AC-08 | **Fail** | The table is not a coherent total state machine: its terminal/predecessor claims contradict its own edges, and the active branch-review path has no transition (RR-F3). |
| AC-09 | **Fail** | The activation register names #109 for two capabilities that #109 explicitly excludes; #124 is their actual activating change. Its fallback also contradicts the higher-precedence draft-review requirement (RR-F1). |
| AC-10 | **Current prose passes; executable guards fail** | No current role summary says the builder opens a ready PR, and the Gates line uses “at least”. Both guards nevertheless pass semantically opposite wording (RR-F2). |

### Invariant trace on re-review

| Requirement | Result | Evidence |
|---|---|---|
| INV-01 | **Pass** | The immutable live-trade, risk-limit, Decimal/money, holdout, signal-parity, secret, English, authorship, Jan-authority, and no-autonomous-R3-merge rules remain inline. |
| INV-02 | **Fail** | Constitution §11 requires review on a draft PR, while workflow's currently authoritative fallback requires branch review before the PR. The resume predicate also differs between AGENTS and workflow (RR-F1/RR-F4). Constitution precedence exposes rather than resolves the impossible lower-level instruction. |

### Guard counterexamples

The following mutations were applied only to temporary copies and the test module's document-path
globals were redirected to those copies. No repository document was changed.

| Guard | Semantic violation injected | Result |
|---|---|---|
| builder start/resume | Removed `Reviewing` from both resume rules | **Passed incorrectly** |
| draft versus ready | Builder immediately marks the PR ready before review | **Passed incorrectly** |
| gates are a minimum | Added “no other check may run” to the `at least` line | **Passed incorrectly** |
| review loop | Replaced the positive transition with “must never move back to Reviewing” | **Passed incorrectly** |
| total state machine | Removed `Ready to Implement → Implementing` | **Passed incorrectly** |
| activation register | Replaced all rows/fallbacks with the three expected issue numbers | **Passed incorrectly** |

### Independently verified gates

| Check | Result |
|---|---|
| `uv run pytest -q tests/test_engineering_docs.py tests/test_claude_runtime_files.py tests/test_engineering_workflow_docs.py tests/test_github_templates.py tests/test_docs_language.py tests/test_workflow_contract.py` | exit 0; **153 passed** |
| `uvx --from rust-just just check` | The unmodified Windows invocation could not find POSIX `sh`; rerun with `just --shell powershell.exe --shell-arg -NoProfile --shell-arg -Command check`: exit 0; Ruff clean, mypy clean over 182 files, vulture clean, **1215 passed / 1 skipped** |
| `uvx --from rust-just just … check-properties` with the same Windows shell override | exit 0; **21 passed twice** |
| `uvx --from rust-just just … check-invariants` with the same Windows shell override | exit 0; **325 passed** |
| `uvx --from rust-just just … check-security` with the same Windows shell override | exit 0; secret scan clean, pip-audit reports no known vulnerabilities, static security check clean |
| `uv run python -m scripts.quality.validate_task 107` | exit 0; valid (**10 AC, 2 INV**) |
| `uv run python -m scripts.quality.pr_ready 107 --base origin/main` | exit 0; reports **READY** from the pre-re-review artifact state |
| The same validator and readiness commands after recording this re-review | exit 1 as intended; the four open P1/P2 findings are detected and readiness reports **NOT READY** |

The formal readiness result does not override this review. It checks recorded gate rows and resolved
finding syntax; it does not evaluate the semantic counterexamples above. This complete re-review
therefore reopens blocking findings and the branch must remain unready.

### Re-review dispositions

All four findings are confirmed and resolved. Each was reproduced before being accepted.

| ID | Disposition |
|---|---|
| RR-F1 | Confirmed, both halves. The activation register pointed at #109 for draft creation and artifact scaling; #109 makes both explicit non-goals and #124 owns them, an error introduced when #109 was split. Both rows now name #124. The precedence conflict is resolved by moving the transitional rule into `constitution.md` §11 itself, at the same rank as the paragraph it suspends — a lower-ranking document cannot suspend a higher-ranking one, so stating it in `workflow.md` left a literal reader unable to obey both. The board table no longer claims `Reviewing` means a pull request is open; it names both the draft and the branch handover. `test_the_transitional_review_rule_is_stated_at_constitution_precedence` binds it and goes red when the constitution loses the rule while the workflow still relies on it. |
| RR-F2 | Confirmed, and it is the root finding. Every guard was a phrase-presence check. All six now parse the contract into facts — the resume rule as one identifiable unit rather than its neighbourhood, the transition table as an edge set compared against an enumerated required set, the activation register as rows with a capability, an owner and a usable fallback, and the ready-for-review ordering as a qualifier that must appear around every statement that marks a pull request ready. Each of the six counterexamples supplied by the review was executed against a mutated copy: **7 of 7 guards go red, 7 of 7 stay green on the real documents.** The proof is reproducible; it mutates temporary copies and redirects the module's document paths, and touches no repository file. |
| RR-F3 | Confirmed. `any → Blocked` is replaced by the four exact permitted sources, so `Done` stays terminal by construction rather than by a sentence that the table contradicted. The claim that `Backlog` has no predecessor is replaced by naming its two real ones, because `Specifying → Backlog` exists by design. The `Implementing → Reviewing` trigger now covers both the draft pull request and the branch handover that the transitional rule requires, so the card has a documented way into `Reviewing` while that rule applies. `test_the_state_machine_declares_every_required_transition` compares against an enumerated edge set and rejects both `any` and any edge leaving `Done`; deleting one required edge makes it red, which the previous source/target coverage check could not detect. |
| RR-F4 | Confirmed. The resume predicate is now identical in both operative documents: the card is in `Implementing` or `Reviewing`, **and** a branch exists in this repository whose name carries this issue number. Both documents additionally refuse a branch from a fork or from outside the repository. The guard reads the rule itself rather than the surrounding section — scanning the region is precisely what let the earlier version pass when the rule lost a status that happened to appear nearby. |

**Root cause, and why it recurred.** Both this round and the previous one failed the same way: a
protection was added and then verified by reading rather than by making it fire. That pattern is
already registered as `F-040`, from the review of a sibling change, and it was registered **before**
these guards were written. Registering a pattern does not prevent it; only running the counterexample
does. The lasting change is therefore procedural rather than textual: a guard added to protect a
contract is not finished until the counterexample it exists to catch has been executed against it and
observed to fail. That is now recorded as the red-first evidence for every criterion in the test plan,
not as a claim.

---

## Third complete independent review of `102ce55`

This is a whole-change review after the material remediation of RR-F1 through RR-F4. The worktree
was at `39995bca3c7fb755a4c69c310302d18969870461` when reviewed; that commit changes only
`evidence.md` after the requested semantic HEAD
`102ce555a413df0f35bc496dc79652bf2257dcf0`. The implementation, documents, and guards reviewed are
therefore exactly those at `102ce55`.

The four earlier findings have genuine textual fixes:

- constitution §11 and the workflow now state the same temporary pushed-branch review rule and both
  bind its removal to #124;
- the transition table uses four explicit `Blocked` sources, leaves `Done` terminal, and describes
  both the ordinary draft handover and the temporary branch handover;
- AGENTS and the workflow use the same issue-number/repository ownership predicate for resumption;
- the old phrase-presence tests were replaced with parsers over identifiable rules and tables.

**Result: NOT READY.** No P0 was found. One P1 and one P2 remain.

### Third-review findings

| ID | Severity | Finding | Concrete failure scenario | Required correction | Status |
|---|---|---|---|---|---|
| R3-F1 | P1 | The seven replacement guards in `tests/test_workflow_contract.py:140-320` still do not bind the semantic facts they claim to protect. Each guard passed a fresh mutation that made its own contract property false. The state parser checks only `_REQUIRED_EDGES <= found`, collapses two different `Implementing → Reviewing` rows into one pair, and ignores actor/trigger cells; the activation parser accepts any issue number and any 31-character fallback; the remaining guards are finite wording recognizers rather than complete facts. This is the same gate-can-report-green defect class as RR-F2, not a hypothetical weakness. | Executed on temporary document copies: missing `approved` became a valid Start condition; “changes the PR to ready before review” evaded the `mark…ready` regex; “additional checks are forbidden” evaded the ceiling list; changing the review-fix actor from Codex to Claude passed; adding unauthorized `Backlog → Done` passed; changing both #124 activation owners back to #109 passed; and making constitution §11 say the pushed branch must never be reviewed passed while the workflow still required branch review. **All 7 guards passed despite their corresponding semantic violation.** | Parse the complete facts, not selected tokens: exact Start and Resume condition/action tuples in both documents; one canonical ready-order fact; an explicit lower-bound gate fact; transition triples/quadruples including actor and trigger; `found == allowed` rather than subset containment; an exact capability→owner→fallback register (including #124); and normalized equality of the constitution/workflow transitional procedure. Every counterexample above must be a committed parametrized red-first test, not an unversioned one-off claim. | resolved |
| R3-F2 | P2 | The mandatory audit artifacts were not updated after the guard rewrite. `.ai/tasks/107/test-plan.md:8-25` still says six guards and maps AC-01/08/09/10 and INV-02 to five test functions that no longer exist. `.ai/tasks/107/evidence.md:37-42` likewise says “six guards, all six red” although the command table says seven. The artifact validator passes because it checks table shape, not whether named tests resolve. | An engineer executing the acceptance map literally gets pytest “not found” for `test_the_state_machine_is_declared_as_a_table_and_is_total`, `test_the_review_loop_returns_the_card_to_reviewing`, `test_capabilities_the_repository_lacks_are_marked_as_not_yet_active`, `test_no_role_document_says_the_builder_opens_a_ready_pull_request`, and `test_required_gates_are_never_described_as_a_maximum`, while the evidence still presents the obsolete map as green. | Update the test plan to the seven current test names, the actual 7-red/7-green proof, and the current focused count; update the coverage paragraph to seven. Add a validation test that every `tests/path.py::test_name` cited in a task test plan resolves during collection, so this stale-evidence class fails mechanically. | resolved |

### Adversarial guard attacks

Each mutation was applied only to a temporary copy of the four documents. The test module's path
globals were redirected to that copy, and no repository file was changed.

| Guard | Violation injected | Actual result |
|---|---|---|
| `test_the_builder_guard_separates_starting_from_resuming` | Changed both Start rules from `approved` present to `approved` absent | **Passed incorrectly** |
| `test_the_builder_never_reaches_ready_before_the_independent_review` | Workflow said Codex “changes” the draft to ready before review, avoiding the `mark…ready` verb | **Passed incorrectly** |
| `test_required_gates_are_a_minimum_and_never_a_ceiling` | Replaced the scoped-check allowance with “additional scoped checks are forbidden” | **Passed incorrectly** |
| `test_the_review_loop_has_a_declared_way_back_to_reviewing` | Changed the review-fix row's actor from Codex to Claude | **Passed incorrectly** |
| `test_the_state_machine_declares_every_required_transition` | Added an unauthorized `Backlog → Done` shortcut | **Passed incorrectly** |
| `test_every_unavailable_capability_carries_an_owner_and_a_fallback` | Changed both #124 owners back to #109 | **Passed incorrectly** |
| `test_the_transitional_review_rule_is_stated_at_constitution_precedence` | Constitution retained the words “transitional rule” and “pushed branch” but explicitly forbade branch review | **Passed incorrectly** |

The enumerated required edge **pairs** match the current table's unique source/target pairs. They do
not match the full prose contract: two semantically different handovers share the
`Implementing → Reviewing` pair, and the set records neither their actor nor their trigger. It also
permits arbitrary additional known-status edges. That loss of information is why the actor mutation
and the `Backlog → Done` mutation both pass.

### Cross-document result

The current constitution §11 transitional rule and the workflow's first Not-yet-active row agree on
the operative facts: the current hook prevents a pre-review draft; review therefore runs on the
pushed branch; the PR opens afterward; #124 removes the exception when it moves readiness to the
ready-for-review transition. The board meaning and transition table also include that temporary
handover. No remaining contradiction was found in those current facts.

The general draft-first wording in AGENTS and CLAUDE is subordinate to constitution §11's explicit,
time-bounded exception. It is not independently executable without reading the constitution, but
both role documents bind themselves to constitution precedence, so it does not create a second
unresolvable rule.

### Acceptance-criteria trace

| Requirement | Result | Evidence |
|---|---|---|
| AC-01 | **Pass in current text** | All six phases identify the actor, working surface, and resulting board state; the temporary branch handover is reflected in the board and transition table. |
| AC-02 | **Pass** | Constitution §9 says risk class scales gates, artifacts, PR sections, and reviewers. |
| AC-03 | **Pass** | Constitution §16 states the issue branch/worktree convention and squash merge. |
| AC-04 | **Current text passes; guard fails** | AGENTS has the correct fail-closed Start order, but its named guard passes after changing the permit from required to absent (R3-F1). |
| AC-05 | **Pass** | CLAUDE requires Jan's explicit approval and adds `approved` last. |
| AC-06 | **Pass for the pre-existing consistency suite** | The marker change remains faithful and no old assertion was removed or made conditional. Focused documentation tests pass. R3-F2 covers the stale task-level map introduced afterward. |
| AC-07 | **Current text passes; complete guard does not** | Resume predicates are now identical and bounded by status, issue-number branch, and repository origin. The combined Start/Resume guard still ignores all Start facts (R3-F1). |
| AC-08 | **Current table passes; guard does not** | Required transition pairs are present and `Done` is terminal, but the guard ignores actors/triggers and unauthorized extra edges (R3-F1). |
| AC-09 | **Current register passes; guard does not** | Current owners and fallbacks are accurate, including #124. The guard accepts the previously wrong #109 owner (R3-F1). |
| AC-10 | **Current text passes; guards do not** | The builder reaches ready only after clean review and the current Gates line is a lower bound. Semantically opposite wording variants pass both guards (R3-F1). |

### Invariant trace

| Requirement | Result | Evidence |
|---|---|---|
| INV-01 | **Pass** | No immutable live-trade, risk-limit, Decimal/money, holdout, signal-parity, secret, English, authorship, Jan-authority, or no-autonomous-R3-merge rule was removed. |
| INV-02 | **Pass in current documents; regression guard fails** | Constitution and workflow agree on both the ordinary rule and the #124 transition. The guard nevertheless passes when those documents state opposite branch-review behavior (R3-F1). |

### Independently verified gates

| Check | Result |
|---|---|
| Focused documentation suite | exit 0; **154 passed** |
| Full `just check` recipes, invoked with the repository's Windows PowerShell shell override | exit 0; Ruff clean, mypy clean over 182 files, vulture clean, **1216 passed / 1 skipped** |
| `check-properties` | exit 0; **21 passed twice** |
| `check-invariants` | exit 0; **325 passed** |
| `check-security` | exit 0; secret scan clean, no known dependency vulnerabilities, static security check clean |
| `uv run python -m scripts.quality.validate_task 107` before this review | exit 0; valid (**10 AC, 2 INV**) |
| `uv run python -m scripts.quality.pr_ready 107 --base origin/main` before this review | exit 0; formally **READY** because the previous findings are marked resolved and evidence binds `102ce55` |
| The validator and readiness command after recording this review | exit 1 as intended; the open P1/P2 findings are detected and readiness reports **NOT READY** |

The green repository gates confirm that the checked-in documents satisfy the current recognizers;
the seven executed counterexamples prove that those recognizers still do not enforce the claimed
contract. This third review therefore reopens blocking findings.

### Builder dispositions after the third review

The builder did not reinterpret either finding and did not alter the workflow documents.
Independent review is required again because R3-F1 changes the load-bearing guard implementation.

| ID | Disposition |
|---|---|
| R3-F1 | Confirmed and fixed structurally. The seven counterexamples are committed as the seven cases of `test_contract_guard_rejects_semantic_counterexample`; before the fix all seven failed because their guard did not raise. Start and Resume now parse to exact condition/action tuples in both documents. Ready order and gate lower bound are canonical facts. Transitions are exact `(source, target, actor, trigger)` allowlisted facts, preserving both `Implementing → Reviewing` handovers and refusing any extra edge. Activations are an exact capability/issue/fallback map. Constitution and workflow transitional rules normalize to the same four facts. After the fix all seven counterexamples pass because every guard rejects its mutation. |
| R3-F2 | Confirmed and fixed. `test-plan.md` now uses complete current pytest node ids and records the current seven-case oracle. `evidence.md` is updated with the real red/green runs and counts. `test_every_task_plan_test_reference_collects` rejects shorthand and invokes pytest collection for every cited full node id, so a deleted or renamed test makes the suite red. |

**Review status:** implementation complete; a fresh complete Claude review is owed. These
dispositions record builder work, not self-review.
