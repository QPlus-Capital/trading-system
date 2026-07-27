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
