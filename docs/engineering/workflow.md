# Development Workflow

How a change travels from an idea to `main`. The [constitution](constitution.md) states *what* must
hold; this document states *who does what, where, and in which order*. Where they appear to differ,
the constitution wins.

Three actors: **Jan** decides and merges. **Claude** designs the specification and reviews the
finished change. **Codex** builds. The builder never reviews its own work.

---

## The board

GitHub Project [QPlus Capital – Trading System](https://github.com/orgs/QPlus-Capital/projects/1).
Its `Status` field is the single source of truth for where a change stands.

<!-- workflow-contract:statuses:start -->
| Status | Meaning | Who sets it |
|---|---|---|
| `Backlog` | A raw idea. One sentence is enough. | Project automation (auto-add) |
| `Specifying` | Claude is working the idea into a specification with Jan. | Claude |
| `Ready to Implement` | Approved by Jan. Codex **may** build it — not "build it now". | Claude, after Jan's explicit approval |
| `Implementing` | Codex is building. | Codex |
| `Reviewing` | The change is with the independent reviewer on the draft pull request. | Codex, at handover |
| `Blocked` | Waiting on a decision only Jan can make (constitution §13). | Any agent |
| `Done` | Merged. | Project automation (item closed) |
<!-- workflow-contract:statuses:end -->

Agents move cards through `uv run python -m scripts.quality.board`; the tool uses `gh` but owns the
contract checks and mutation ordering. Two built-in project automations do the rest and cost no
Actions minutes: *item added → `Backlog`*, and *item closed → `Done`*.

## The labels

Five labels, each with a mechanical function. A label that only decorates is not maintained, so
none exist.

| Label | Function | Set by | Removed by |
|---|---|---|---|
| `approved` | The build permit. Without it Codex refuses to build. | Claude, at approval | **Codex, at build start** |
| `risk:R0` … `risk:R3` | Selects gates, artifacts, PR scope, and review agents. | Claude, from the classifier | — |

Priority is the vertical order of the `Backlog` column, not a label.

---

## Phase 0 — Idea reaches the backlog

An idea must cost nothing to record. A backlog issue needs only a clear title; one sentence of body
is enough. No template, no required fields, no labels.

Titles are plain sentences without prefixes — GitHub already numbers issues. The existing `[P-NN]`
package issues are a grown roadmap structure and keep their prefix.

Jan files ideas directly. Claude and Codex file issues only for **evidenced** work found outside
their current scope — never speculation, and never as an escape from the task at hand; the agent
returns to its original work immediately afterwards.

## Phase 1 — Specifying (Claude, plan mode)

Jan says *"let's work out #101"*, or explains a new idea. Claude moves the card to `Specifying`.

1. **Reality check first.** Does the problem still exist? Is it a duplicate? Would it violate the
   constitution — for example by loosening a risk limit? If so, stop, cite the evidence, and propose
   closing the issue. This is the cheapest possible outcome.
2. **Read the code**, at a depth set by the risk class: R0/R1 the named file; R2 the affected modules
   and their direct callers; R3 additionally the data flow, lifecycle, and parity paths. Search for
   existing functions to reuse before proposing new ones.
3. **Classify.** `scripts.quality.classify` gives the minimum from the expected paths. Raise it when
   the semantic impact is broader, and say so explicitly — raising it raises the process cost.
4. **Ask only questions whose answer changes the outcome.**
5. **Write the issue body**, replacing the original sentence.

The issue body is **English** (constitution §1) and describes **what**, never **how** — Codex derives
the approach and the review judges it.

```markdown
## Problem
## Goal
## Scope
## Non-goals
## Acceptance criteria     - [ ] AC-01 …   behavioural, testable
## Invariants              - [ ] INV-01 …  R2 and above
## Affected modules
## Risk class              "R2 — reason"
## Verification plan
## Open decisions (Jan)
```

Non-goals keep the pull request small. Every `AC-nn` maps to exactly one named test and is ticked in
the PR; an acceptance criterion no test could check is a wish, not a criterion. The reason for the
risk class matters more than the class itself.

If a genuine business, trading, methodology, live-money, architecture, or risk decision stays open,
it is recorded under **Open decisions** with its options and consequences, the card moves to
`Blocked`, and the phase ends. **There is no approval with an open decision.**

## Phase 2 — Approval (Jan)

Claude presents the complete issue body in the conversation — not a link, not a summary — with the
number, title, risk class and its reason, the open decisions, and the count of criteria and
invariants.

For **R3** Claude additionally presents the risk itself: which limits the change touches, what
happens in the worst case if it is wrong, and whether a running runner would be affected. Jan then
approves the risk, not merely the text.

From R2 upward the body is checked mechanically before approval: required sections present, at least
one acceptance criterion, criteria numbered, risk class justified, no open decision left open.

Jan answers in one of three ways: approval; a change request, which returns to phase 1 as often as
needed; or *"later"*, which returns the card to `Backlog` with the specification preserved.

On approval, in this order:

<!-- workflow-contract:approval-order:start -->
```
1  write the final issue body
2  add risk:Rn
3  move the card to Ready to Implement
4  add approved          ← last
```
<!-- workflow-contract:approval-order:end -->

`approved` is added last on purpose. If any earlier step fails, the issue is **not** approved and
Codex will not build it — the constitution's fail-closed rule (§3) applied to the workflow itself.

Claude then reports only `#101 is approved (R2).` — **no prompt and no call to action.** When the
change is built is Jan's decision. `Ready to Implement` is a supply, not a queue.

A change to an approved issue requires moving it back to `Specifying` and removing `approved`;
phase 2 then runs again, including Jan's approval.

## Phase 3 — Building (Codex)

Jan says `implement #101`. Nothing more is ever required.

**Guard first — two disjoint rules**, because starting consumes the permit and resuming therefore
cannot require it.

<!-- workflow-contract:builder-guard:start -->
| Case | Condition | Then |
|---|---|---|
| **Start** | card in `Ready to Implement`, `approved` present, `risk:Rn` present | move the card to `Implementing`, **then** remove `approved` |
| **Resume** | the card is in `Implementing` or `Reviewing`, **and** a branch exists in this repository whose name is `codex/<issue>-…` or `claude/<issue>-…` for **this** issue number | continue on it **without** a permit — the first start already consumed it |
<!-- workflow-contract:builder-guard:end -->

Anything else is a refusal, reporting the actual status. In particular: a card in `Backlog`,
`Specifying` or `Blocked` is never built, branch or no branch; a branch whose name does not carry
this issue number is never resumed; and a branch from a fork or from outside this repository is
never resumed, whatever the card says. Ownership is decided by the branch name and its origin, not
by the card alone — the card cannot tell you who wrote the code.

The order in the start case matters: removing the permit before the status move would destroy it if
the move then failed. The resume case exists because it is the normal state after an interruption or
after a review sent the change back — a guard that demanded the consumed permit there would lock the
builder out of its own branch.

**Isolation:** one git worktree per issue, branch `codex/<issue>-<slug>` (or `claude/<issue>-<slug>`
when Claude builds under the exception). Several issues can run in parallel, the main checkout stays
clean, and a running live runner never sees half-finished code.

<!-- workflow-contract:build-sequence:start -->
```
1  Impact          what depends on this? which tests are affected?
2  Test plan       every AC-nn and INV-nn → exactly one named test
3  Prove RED       write the test, run it, record the failure
4  Build           the smallest coherent change; clean up nothing on the side
5  Prove GREEN
6  Gates           at least those of the risk class, plus any scoped check that applies
7  Evidence        command, exit code, result
8  Handover        open the draft PR and hand it to the independent reviewer
9  Card            → Reviewing
```
<!-- workflow-contract:build-sequence:end -->

The review surface and pull-request timing are stated in phase 4. Their generated rule incorporates
the temporary branch handover, so this phase does not restate a second ordering.

Step 3 carries the whole system: a test that was never red proves nothing.

| | R0 | R1 | R2 | R3 |
|---|---|---|---|---|
| Impact analysis | – | – | ✓ | ✓ in depth |
| Red proof | – | ✓ | ✓ | ✓ |
| Gates | format, docs | + `just check` | + property, integration | + invariants, mutation, parity |
| Artifact files | – | – | `review.md`, `evidence.md` | all four |
| PR sections | 5 | 8 | 14 | 20 |

At R2 the impact analysis and test plan live in the pull-request body; only `review.md` and
`evidence.md` stay on disk. R3 adds `impact.md` and `test-plan.md`. R0 and R1 require no task
directory. There is no `spec.md` — the specification is the issue.

If the specification turns out to be wrong, incomplete, or unbuildable, Codex does not guess
(constitution §13). The card goes back, the gap is stated in an issue comment, and phase 2 runs
again.

## Phase 4 — Review (Claude, fresh session)

Jan says `review PR #102`. **A fresh session is mandatory**: a reviewer who knows what was intended
does not find what is actually there.

The read-only subagents run according to the risk class *and* the paths touched:

| Change | Agents |
|---|---|
| R0 / R1 | none — Claude reviews directly |
| R2 | code, tests |
| R3 touching `live/**` | + live-money |
| R3 touching `research/**` or methodology | + methodology |
| R3 touching both | all four |

Claude delivers the result as a real pull-request review: one inline comment per finding at its
`file:line` with the severity, the concrete failure scenario, and the regression that would prove it;
plus a summary comment carrying the findings table, the acceptance-criteria and invariant check, an
assessment of the **chosen approach**, and a clearly separated block of decisions that require Jan.
Changes are requested for any blocking finding. At R2 and above the same findings are recorded in
`.ai/tasks/<id>/review.md` as a versioned audit trail.

A blocking finding returns the card to `Implementing`. Codex fixes it and, on pushing the fix, moves
the card **back to `Reviewing`** — otherwise the board would report building while a review is
running, and the status field would stop being the truth it is declared to be. The **entire** review
then runs again, not only the changed place: a fix can break something elsewhere.

<!-- workflow-contract:ready-order:start -->
Codex opens the pull request as a **draft** at the initial review handover. Once the independent review is clean and the readiness check passes for current HEAD, Codex marks it **ready for review**. That transition is the signal that the change is Jan's to judge.
<!-- workflow-contract:ready-order:end -->

**Codex fixes every finding**, including trivial ones. If Claude fixed them it would afterwards be
reviewing its own code, and the separation between builder and reviewer would no longer hold.

Confirmed findings become permanent protection (constitution §14): reproduced, fixed, root-caused,
and recorded **generalised** in the finding registry. The same defect twice is a workflow failure,
not merely a code failure.

Jan reviews the three things no agent may judge: whether this is what he wanted, whether the
non-goals held, and whether the non-blocking findings should be fixed.

## Phase 5 — Merge (Jan only)

No agent merges. Auto-merge is never enabled.

Merging requires green CI, no unresolved blocking findings, every acceptance criterion ticked, every
escalated decision answered, and — at R3 — the live-money or methodology review completed.

**Squash merge**: one commit per issue, message from the issue title and the PR summary. Every commit
on `main` is then complete and green, which is what makes `git bisect` trustworthy. The individual
build steps remain visible in the pull request.

When CI is red for an **infrastructure** reason rather than a code reason, merging is allowed only
with the same checks run locally, their output pasted into the pull request, and the reason stated
explicitly. There is never an unevidenced merge.

A change on the live path needs a quiet window, because the running runner holds the old code in
memory:

```
1  is a position open?  → if so, wait
2  stop the runner cleanly
3  merge
4  uv sync
5  start the runner
6  preflight, then observe
```

Constitution §3 is absolute: never touch a running trade, and never restart a runner as a side
effect of something else.

`Closes #101` closes the issue, which moves the card to `Done`. The branch is deleted and the
worktree removed.

**Rollback**, for an R3 change on the live path only: stop the runner, restore the last good state,
`uv sync`, start, observe — and only then investigate the cause. Below R3 an ordinary fix is enough.

---

## State transitions

Prose describes one transition at a time, which is how a missing one hides. The table is the
contract; the phases above explain it.

<!-- workflow-contract:transitions:start -->
| From → To | Who | When |
|---|---|---|
| — → `Backlog` | project automation | an issue is opened |
| `Backlog` → `Specifying` | Claude | Jan asks for the idea to be worked out |
| `Blocked` → `Specifying` | Claude | Jan decided |
| `Specifying` → `Backlog` | Claude | Jan defers the idea; the specification is kept |
| `Specifying` → `Ready to Implement` | Claude | Jan approves; `approved` is written last |
| `Ready to Implement` → `Specifying` | Claude | an approved issue must change; `approved` is removed first |
| `Ready to Implement` → `Implementing` | Codex | build starts; `approved` is removed afterwards |
| `Implementing` → `Reviewing` | Codex | the draft pull request is opened and handed over for review |
| `Reviewing` → `Implementing` | Claude | a blocking finding |
| `Implementing` → `Reviewing` | Codex | the review fix is pushed |
| `Implementing` → `Specifying` | Codex | the specification is wrong, incomplete or unbuildable |
| `Specifying` → `Blocked` | Claude | a decision only Jan can make is open |
| `Ready to Implement` → `Blocked` | any agent | a decision only Jan can make is open |
| `Implementing` → `Blocked` | any agent | a decision only Jan can make is open |
| `Reviewing` → `Blocked` | any agent | a decision only Jan can make is open |
| `Reviewing` → `Done` | project automation | the pull request merged and closed the issue |
<!-- workflow-contract:transitions:end -->

`Done` is terminal: no transition leaves it, and none enters `Blocked` from it. Every other status
has at least one exit, and every status except `Backlog` has at least one predecessor listed above.
`Backlog` is entered from issue creation and from a deferred specification.

## Not yet active

Two parts of this contract describe tooling the repository does not have yet. Until each lands,
the rule in the right-hand column is authoritative — so the procedure above is always executable as
written.

<!-- workflow-contract:activations:start -->
| Part of this contract | Lands with | Until then |
|---|---|---|
| The `methodology-reviewer` subagent | [#112](https://github.com/QPlus-Capital/trading-system/issues/112) | The general code reviewer carries the constitution §4 methodology invariants, as it does today. |
| Findings named `Blocker` / `Defect` / `Suspected defect` / `Note` | [#112](https://github.com/QPlus-Capital/trading-system/issues/112) | Severities are `P0`–`P3`, as the constitution §12 states. |
<!-- workflow-contract:activations:end -->

A row leaves this table in the same change that lands its dependency. An empty table means the
contract and the repository have converged.

## Handover points

The workflow has exactly three places where control changes hands. Each is guarded.

| Handover | Guard |
|---|---|
| Claude → Jan (approval) | Jan's explicit approval; `approved` is written last |
| Jan → Codex (build) | Status, `approved`, and `risk:Rn` are all verified before any work |
| Codex → Claude (review) | A fresh session; the reviewer never carries the builder's context |

Everything else is a status transition an agent performs on itself.
