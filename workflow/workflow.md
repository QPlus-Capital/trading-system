# Development Workflow

The single source of truth for how changes are made in this repository — shared by the operator,
Claude, Codex, and the repository tooling. `CLAUDE.md` and `AGENTS.md` are short role documents that
point here. `workflow/workflow.toml` holds the same contract in the form the tooling reads. Where any of
them appears to disagree, **this file wins**.

A rule appears in exactly one place. Nothing here is repeated elsewhere in prose.

---

## 1. This repository trades real money

A defect is a loss, not a bug report. These constraints are immutable and override every other
consideration in this document.

- **Never touch a running live trade.** Do not place, modify, or close an order. Never restart a
  runner as a side effect of another task. Never run two runners against one account.
- **Internal risk limits stay stricter than the prop firm's** and must remain so: 0.18% per trade,
  2.5% daily stop, 5% trailing, 2% open-risk cap — against TTP's 3% / 6% hard limits. A change may
  tighten them; loosening them past the prop limits is prohibited.
- **Fail closed.** When a safety input is missing, ambiguous, or unverifiable, refuse the action
  rather than proceed on a guess.
- **Never use `float` for prices, quantities, or money.** Use `Decimal` or NautilusTrader's `Price`,
  `Quantity`, or `Money`. Convert to `float` only at a boundary that is already float, never for a
  value that sizes a position or books a P&L.
- **Guard every denominator, sign, and boundary.** Zero, empty, NaN, infinity, and near-zero
  divisors are inputs, not impossibilities.
- **Secrets** live in `.env` (gitignored) and the password manager; `.env.example` holds
  placeholders only. Never commit a credential, key, token, or account number, and never put one in
  a log or a URL. A new credential is reported to the operator for the password manager.
- **A live merge needs a quiet window** (section 4, phase 5). The runner holds the old code in
  memory.

## 2. Research methodology

- Parameter changes go through the staged walk-forward (`docs/methodology.md`) and an **untouched
  holdout**. The holdout is evaluated once; retuning and re-scoring against it burns it.
- **Live data is out-of-sample.** Monitor and calibrate from it, never retune parameters from it.
- `r` is gross price R. Swap is a separate realized cost (`swap_r`). **`net_r = r + swap_r` is the
  sole statistical return stream.** No change may quietly flatter a metric.
- **Content-addressed lineage** binds each run to the exact code, config, and data that produced it.
  The stage chain runs on one frozen code state.
- **Stage 1 measures edge on equal footing:** every window is sized and scored off one constant
  basis, never a compounding account. Compounding belongs to the portfolio stage and to live.
- **Selection mirrors execution.** The parameters, sizing basis, and cost model used to *choose* a
  configuration equal those used to *run* it.

## 3. Architecture

- Four flat packages: `core/` (shared strategies, instruments, broker, data), `research/`, `live/`,
  `monitoring/`. No `src/` nesting.
- `core/` depends on no sibling. `research/` and `live/` depend on `core/` and **not on each other's
  domain logic**. `monitoring/` sits on top and may read from all three; nothing imports it.
- The `research/` ↔ `live/` rule has two allowlisted crossings, each an explicit, shrinking entry in
  `tests/test_import_boundaries.py`. A *new* crossing fails the test; a removed one leaves the list.
- A strategy's signal logic is **one pure engine** (`core/strategies/rsi_wpr_bb_signals.py`, no
  Nautilus, no MT5) driven by two thin adapters: the backtest wrapper and the live runner. Both
  instantiate it; neither reimplements a signal.

---

## 4. The process

Three actors and one connector. **The operator** decides and merges. **Claude** specifies and
reviews. **Codex** builds. **The orchestrator** connects them and decides nothing.

Claude never builds. Codex never reviews. There is no exception.

**Sessions.** The operator holds **exactly one chat per ticket per agent**, each named
`Issue #<number>`: one Claude chat that accompanies the ticket from idea to merge, and one Codex
chat that carries the build and every fix round. The operator never opens a second chat for a
ticket — not for a repeat round, not for a fix. Every further process the loop needs (the review,
an automatic fix hand-back) is the orchestrator's, runs headless, and asks the operator to open
nothing. The review always runs in its own fresh process: a reviewer that knows what was intended
does not find what is actually there.

**Numbers.** GitHub draws issue and pull-request numbers from one sequence. Therefore **only issue
numbers are ever spoken**. Pull-request numbers are internal mechanics and appear in no chat, no
agent message, and no notification. The path is unambiguous: the ticket owns branch
`codex/<issue>-<slug>`, that branch owns one pull request, and it carries `Closes #<issue>`.

### The board

GitHub Project *QPlus Capital – Trading System*. Its `Status` field is the single source of truth
for where a change stands — not the branch, not the pull request.

| Status | Meaning |
|---|---|
| `Backlog` | An idea. **Not yet specified.** |
| `Specifying` | Being worked out with the operator. |
| `Ready to Implement` | Fully specified **and released**. May be built; need not be. |
| `Implementing` | Codex is building. |
| `Reviewing` | With the reviewer. |
| `Blocked` | Waiting on something it cannot proceed without: a decision only the operator can make, or another ticket. |
| `Done` | Merged. |

Labels are `risk:R0` … `risk:R3` and nothing else. `Ready to Implement` *is* the release, so no
separate permit label exists. Priority is the vertical order of the `Backlog` column.

Two built-in project automations cost no Actions minutes: *issue opened → `Backlog`*, *issue closed
→ `Done`*.

### Phase 0 — Idea reaches the backlog

A fresh Claude chat — after the issue exists, the operator names it `Issue #<number>`, and it stays
the ticket's one Claude chat until the merge. The operator states the idea in a sentence or two.
Claude opens an issue with a clear title and two or three sentences of body, and records the session
identifier on it so the orchestrator can reach this chat later.

No template, no labels, no questions. **An idea must cost nothing.** Titles are plain sentences
without prefixes; the grown `[P-NN]` package issues keep theirs.

Claude and Codex open issues only for **evidenced** work found outside their current scope — never
speculation, never as an escape from the task at hand, and they return to it immediately.

### The two lanes

The risk class answers *how bad if this is wrong*. It does not answer *how much process checking it
needs* — a one-line fix on the live path is high-risk and cheap to check; a five-hundred-line
tooling change is the reverse. The process therefore has two lanes, and **lean is the default**.

The full program runs only when at least one holds:

- a changed path matches the **carve-out** in `[review.scope]` of the contract — the paths where a
  single line can cost real money: risk limits, sizing, order placement, the broker bridge, account
  identity, holdout and selection, and the classifier itself;
- the diff exceeds the size bound in `[review.scope]` (changed lines, additions plus deletions);
- the operator asks for it.

The lane changes the ceremony, never the safety: **the gates of the risk class run in full in both
lanes**, every change reaches `main` through a pull request, and the operator merges. The lane is
stated in the issue; at review time the *actual* diff decides — a change that grew past the bound or
into the carve-out is reviewed at full strength whatever the issue declared.

### Phase 1 — Specifying

In the same chat, when the operator asks for the idea to be worked out. Claude moves the card to
`Specifying`, then — in both lanes:

1. **Reality check first.** Does the problem still exist? Is it a duplicate? Would the fix violate
   section 1 or 2? If so: stop, cite the evidence, propose closing. This is the cheapest outcome.
2. **Classify** with `workflow.classify`. The result is a minimum; raising it is mandatory
   when the semantic impact is broader than the paths suggest, and the reason is stated.
3. **Ask only questions whose answer changes the outcome.**

**Lean lane:** the issue body is the problem and the goal in a few sentences — essentially the
operator's own words, sharpened. Up to five numbered, testable criteria where they earn their keep;
no invariants section, no impact analysis, no verification plan. Claude reads the named code, not
the transitive closure.

**Full program:** Claude reads the code at the depth the risk class sets — R2 the affected modules
and their direct callers; R3 additionally data flow, lifecycle, and parity paths — searches for
existing functions to reuse, and writes the body as:

```
## Problem
## Goal
## Non-goals
## Acceptance criteria   AC-01 …   behavioural, testable
## Invariants            INV-01 …  R2 and above
## Affected modules
## Risk class            "R2 — reason"
## Open decisions
```

Every `AC-nn` maps to **exactly one named test**. A criterion no test can check is a wish. The
reason for the risk class matters more than the class.

**In both lanes, a specification fits on one page.** If it cannot, the ticket is too big — split it
rather than specify harder. A 280-line specification produced a 1,400-line change and three reviews
longer than the code; the cap exists because ceremony compounds through everything downstream.

If a genuine business, trading, methodology, live-money, architecture, or risk decision stays open,
it is recorded under *Open decisions*, the card moves to `Blocked`, and the phase ends.
**There is no release with an open decision.** Only those categories interrupt the operator;
everything else is decided from this document and the code, and documented.

A ticket that is **fully specified but depends on another ticket** goes to `Blocked` as well, with
the dependency named in the body. `Ready to Implement` means a builder may start *now*; a ticket
that would have to wait does not belong there, because a supply nobody can draw from is not a
supply. When the dependency merges, the card returns to `Specifying` and phase 2 runs — the
specification is presented again, because what it waited for has since changed.

### Phase 2 — Release

Claude presents the **complete issue body** in the chat — not a link, not a summary — with number,
title, risk class and its reason, and the count of criteria and invariants. For R3 it additionally
presents the risk itself: which limits the change touches, what happens in the worst case, and
whether a running runner is affected. The operator releases the risk, not merely the text.

In the full program, the body is checked mechanically first from R2 upward: required sections
present, at least one numbered acceptance criterion, risk class justified, no open decision left
open. In the lean lane the presentation is the summary block and the release can be one word in the
same breath — the authority is identical, only the ceremony differs.

| The operator says | Then |
|---|---|
| **released** | add `risk:Rn`, move the card to `Ready to Implement` |
| **change this** | stays in `Specifying`, phase 1 continues |
| **not now** | card to `Backlog`, the specification is kept |

Claude then reports only `#101 is released (R2).` — **no prompt, no call to action.** When it is
built is the operator's decision; `Ready to Implement` is a supply, not a queue.

Changing a released issue means moving it back to `Specifying`; phase 2 runs again.

### Phase 3 — Building

The ticket's Codex chat — `Issue #101` — opens with: `implement #101`. Nothing more is ever
required, and the same chat carries every later fix round.

**Guard first.** Two cases; anything else is a refusal that reports the actual status.

| Case | Condition | Then |
|---|---|---|
| **Start** | card in `Ready to Implement`, `risk:Rn` present | move the card to `Implementing` |
| **Resume** | card in `Implementing` or `Reviewing` **and** a branch `codex/<issue>-…` for this issue exists in this repository | continue on it |

A card in `Backlog`, `Specifying`, or `Blocked` is never built. A branch whose name does not carry
this issue number, or that comes from a fork or from outside this repository, is never resumed —
ownership is decided by the branch and its origin, because the card cannot know who wrote the code.

**Isolation:** one git worktree per ticket, branch `codex/<issue>-<slug>`. The main checkout stays
clean and a running runner never sees half-finished code.

```
1  Impact       what depends on this, which tests are affected   (full program only)
2  Test plan    every AC-nn and INV-nn → exactly one named test  (full program only)
3  Prove RED    write the test, run it, record the failure
4  Build        the smallest coherent change; the non-goals bound the diff
5  Prove GREEN
6  Gates        those of the risk class (section 5), run locally
7  Self-check   the defect classes below
8  Push         ONCE, open the pull request, body carries "Closes #101"
9  Card         → Reviewing
10 Cycle        uv run python -m workflow.orchestrate run <issue>
```

Step 10 is what makes the review start without the operator: the builder is already a local process
when it pushes, so ending the session by starting the cycle needs no watcher, no daemon, and no
agent credentials in CI. A build session that dies before step 10 leaves the card in `Reviewing`
and the operator starts the cycle by hand — the fallback in phase 4.

In the lean lane, steps 1 and 2 collapse into the work itself: the fix and the test that proves it,
nothing written up separately. Steps 3, 5, 6 and 7 are never skipped in either lane.

Step 3 carries the whole system: a test that was never red proves nothing. Step 8 is one push per
round — commit locally as often as useful, push once. **The pull request is opened ready for
review, never as a draft** — the review starts from the open pull request, and a draft would only
say "not ready" while the checks say otherwise.

**Step 7, the self-check.** Before handover, Codex probes the same defect classes the reviewer
hunts, so the review confirms rather than discovers:

- lifecycle: start, stop, failure, cleanup, retry;
- configuration: does a value silently fall back to a default?
- outcome buckets: is a case dropped from the classification and therefore from the totals?
- boundaries: zero, empty, NaN, infinity, sign, near-zero denominator;
- fail-open: which error path proceeds where it should refuse?
- money path: any `float` where section 1 requires `Decimal`?

If the specification is wrong, incomplete, or unbuildable, Codex does not guess: the card returns
to `Specifying` with `just board move <issue> Specifying --actor codex --reason "<the gap>"` —
the board refuses the move without the reason and posts it on the issue — and phase 2 runs again.
Every board move names its actor; the contract assigns each transition to one, and a card in a
build cannot be pulled backwards by anyone else.

### Phase 4 — Review

The pull request is open. **The builder starts the cycle as the last step of phase 3**; the
operator can always start it by hand — one command
(`uv run python -m workflow.orchestrate run <issue>`) or one sentence in the ticket's Claude
chat — when a
build session ended before step 10, or to repeat a cycle deliberately.

```
pull request open → builder starts the cycle (operator as fallback)
  ↓  gates run against the branch under review
  ↓  the push CI settles — no verdict while any check still runs
  ↓  Claude reviews in a fresh process (the issue number is the only input)
  ↓  review submitted as a real pull-request review
Blocker or Defect? ──yes──→ back to Codex, fix, push ──→ review again  (at most 2 rounds)
  └──no──→ one scoped mutation measurement on the certified head, awaited
              └──green──→ notification in the ticket chat: "#101 ist sauber und bereit zum Mergen"
```

**Evidence never overlaps.** The round is strictly ordered — gates, settled CI, review, then the
mutation measurement — and nothing later starts while anything earlier still runs. "Ready to
merge" therefore means every piece of evidence exists, is green, and describes the one pushed
commit the cycle certified. A red mutation measurement is a blocking finding like any other: it
consumes a fix round, and at the round cap it blocks.

**The cycle narrates as it goes.** Every phase change — round started, review running, verdict,
hand-back, mutation measurement, ready or blocked — reaches the ticket's Claude chat as a
structured event carrying its round, head commit, and counts; the session narrates it in German
for the operator and never acts on it. A decision event is the last event a run sends, so a
decision is never buried under routine progress lines.

**Lean lane: Claude reviews directly, one pass, no subagents.** The full agent panel engages only
in the full program:

| Change | Agents |
|---|---|
| lean lane, any class | none — Claude reviews directly |
| full program, R2 | code, tests |
| full program, R3 | code, tests — **plus one specialist where the paths select one**: live-money for `live/**`, methodology for `research/**`, `docs/methodology.md`, `docs/strategies/**` |

An R3 change outside those paths — the workflow tooling itself, the CI — is reviewed by code and
tests alone. That is deliberate: the mechanical answer for such modules is mutation coverage, which
finds weak tests wholesale where one more reviewer would find them piecemeal.

The agents are read-only and receive the issue contract, the diff, the gate results, and the
executing paths — never the builder's private context. Their counterexamples are reconciled against
every `AC-nn` and `INV-nn`.

**Search effort is proportionate to the diff.** The risk class decides what must be proven; the
size of the change decides how far to search for a disproof. Counterexamples target the behaviours
whose failure costs the most and stop when further ones stop changing the verdict — never a fixed
quota per changed behaviour, which is how a cleanup command once collected seventy-one.

The review is delivered as one pull-request review: an inline comment at each finding's `file:line`
with severity, the concrete failure scenario, and the regression that would prove it; plus a summary
carrying the findings table, the criteria check, and a separated block of decisions that belong to
the operator. **A repeat round reports only its findings table and verdict** — no fresh contract
check, no counterexample appendix, no restatement of what round one already established.

**A review reports; it does not file.** Findings that do not block the change are listed for the
operator, and whether any becomes an issue is the operator's decision — a review that spawns tickets
multiplies process instead of finishing the change in front of it.

| Severity | Meaning | Blocks | Triggers a fix round |
|---|---|---|---|
| **Blocker** | live-money loss, leaked secret, data corruption | yes | yes |
| **Defect** | wrong result, broken invariant, silent failure | yes | yes |
| **Suspected defect** | probable defect, or a missing test for a real edge case | no | no — presented to the operator |
| **Note** | optional improvement or style point | no | no |

Saying "this is correct" when it is, is valuable. Findings are never invented to seem thorough; when
none survives, the number of counterexamples attempted is recorded.

**Codex fixes every blocking finding**, and returns the card to `Reviewing` on pushing the fix —
otherwise the board would report building while a review runs. Claude never edits the branch; if it
did, it would afterwards be reviewing its own code.

**Repeat scope after a fix.** The deterministic gate suite always runs in full. **The review
re-runs on the fix diff and the modules it touches, nothing more.** A complete fresh review runs
only when the fix touches files outside the original diff, or at R3 on the live path. This binds
the reviewer, not just the orchestrator: a repeat round that re-walks the whole change is the
single largest time sink the previous process had.

**Cap.** After two fix rounds without a clean result, the card moves to `Blocked` and the operator
is notified with what remains. A finding that needs an operator decision moves the card to `Blocked`
immediately, regardless of the round count.

**A confirmed defect becomes permanent protection:** reproduced by a test that fails before the fix
and passes after, then root-caused. That test is part of the fix, not a follow-up.

### Phase 5 — Merge

The operator only. No agent merges; auto-merge is never enabled.

Merging requires green CI, no unresolved Blocker or Defect, every acceptance criterion ticked, and
every escalated decision answered.

**Squash merge** — one commit per ticket, message from the issue title and the pull-request summary.
Every commit on `main` is then complete and green, which is what makes `git bisect` trustworthy.

When CI is red for an **infrastructure** reason rather than a code reason, merging is allowed only
with the same checks run locally, their output pasted into the pull request, and the reason stated.
There is never an unevidenced merge.

A change on the live path needs a quiet window:

```
1  is a position open?  → if so, wait
2  stop the runner cleanly
3  merge
4  uv sync
5  start the runner
6  preflight, then observe
```

`Closes #101` closes the issue, which moves the card to `Done`. **Teardown is part of the merge:**
the operator runs `just finish 101`, which first proves the issue is closed, its card is `Done`, and
its branch tip is preserved on GitHub. It then removes the worktree, local branch, remote branch,
and remote-tracking reference. Nothing temporary survives in the repository; the complete history
lives in the issue and the pull request.

Before removing a worktree, `just finish` checks the protected paths named by the contract and
refuses if any exists. The protected list is `.env`, `data/`, `catalog/`, `results/`, `reports/`, and
`workflow/mutation-results/`. These hold credentials, market data, research output, live risk state,
or mutation evidence. Other ignored state — `.venv/`, tool caches, `mutants/`, and the generated
impact map — is regenerable and is removed with the worktree.

**Rollback**, for an R3 change on the live path: stop the runner, restore the last good state,
`uv sync`, start, observe — and only then investigate the cause. Below R3 an ordinary fix is enough.

---

## 5. Risk classes and gates

Every change carries a class. `workflow/workflow.toml` holds the path rules; the classifier takes the
**highest** class over all matched rules. Path matching is a conservative minimum and may never
lower a class. An unmatched path is R2, never R1; R0 and R1 are reached only by an explicit rule or
the docs-only fallback.

| Class | What it is |
|---|---|
| **R0** | Documentation or comments only. No behaviour change. |
| **R1** | Local non-financial code with no methodology or result-integrity impact. |
| **R2** | Shared core, research orchestration, configuration, monitoring semantics, tests. |
| **R3** | Live-money path, sizing, risk control, account identity, orders, signal parity, broker conversion, money calculations, methodology, holdout, selection, result integrity — and the quality tooling and governance documents that decide every other change. |

| | R0 | R1 | R2 | R3 |
|---|---|---|---|---|
| Red proof | – | ✓ | ✓ | ✓ |
| Impact analysis | – | – | in the pull request | in depth |
| Local gates | format | + `just check`, security | + property replay | + invariants, mutation on changed critical modules, parity |
| Review agents | – | – | 2 | 3 |
| Pull-request sections | 3 | 3 | 5 | 7 |
| **Files in the repository** | **none** | **none** | **none** | **none** |

Gates are cumulative. **No task artifacts exist on disk.** Impact, test plan, gate results, and the
review live in the issue and the pull request; GitHub retains them and records their author.

**Never claim correctness without executable evidence.** A narrative description is not a substitute
for a command, its exit status, and its result. Every gate the risk class requires is recorded that
way, and a before/after result is recorded for any regression the change fixes.

**The pull-request body:**

```
## What and why
## Acceptance criteria     AC-01 → test_name  ✓
## Gates                   command | exit | result
## Risk class              R2 — reason
## Open points             non-blocking findings, follow-up tickets
--- R3 adds ---
## Live-money impact       which limits, worst case
## Rollback                concrete steps
```

## 6. Tests

Tests live in `tests/`, run with `pytest`, and are written wherever they add value without being
asked. Prefer **behavioural** assertions: a test that would still pass if the function returned a
plausible wrong answer protects nothing.

Test design considers, where relevant: lifecycle and cleanup; configuration propagation and default
fallbacks; exhaustive classification of outcomes; zero / empty / NaN / infinity / sign / denominator
boundaries; consistency between aggregates and the underlying records; selection/execution and
research/live parity; and temporal seams — before the first segment, at segment start and end,
between segments, embargo and gap, and the final boundary.

**Locally, before every push:**

| Command | Contains | From |
|---|---|---|
| `just check` | ruff, mypy, vulture, pytest | R1 |
| `just check-security` | secret scan, dependency audit, security lint | R1 |
| `just check-properties` | seeded Hypothesis replay | R2 |
| `just check-invariants` | the critical test files | R3 |
| `just mutation` | mutation on **changed** critical modules | R3 |

**In CI, on every push:** one Linux job running `check` and the property replay — the independent
confirmation that green is not merely local. A Windows job runs **only** when the MT5 boundary is
touched. **Mutation is measured once per ticket, not once per push:** the review cycle dispatches
one run (`workflow_dispatch`, `scope=mutation-affected`) on the head the review certified,
restricted to the targets the diff can reach — directly, through a changed test's imports, or
totally, because a changed pytest configuration is copied into every mutant tree and therefore
reaches every target. A weekly scheduled run measures the complete critical set on `main` and
keeps the global baseline honest; within a scoped run the ratchet still fails closed in both
directions, but only over what it measured. Mutation remains a CI job until the development
platform moves to macOS (issue #150).

**No gate may be weakened to make a branch pass.** Prohibited: bypass or skip flags; broad
`# type: ignore`, `# noqa`, or `pytest.mark.skip` introduced to hide a failure; widening a per-file
ignore to cover new code; lowering a threshold or baseline in the change that would otherwise breach
it. A gate that cannot bind is worse than no gate, because the report then says the numbers held.

## 7. Language, documentation, and git

- Everything committed — code, identifiers, comments, docstrings, docs, commit messages — is
  **English**. Conversation with the operator may be in another language; the repository is not.
  Operator-facing *runtime* output (research stage banners, the dashboard, the orchestrator's
  notifications) is German by decision; this is the only exception and is scoped to strings a human
  reads at a terminal.
- **Every session that reports to the operator closes in German, guided by three rules, not a
  template.** First: two to five plain sentences — what happened, what it means, what comes next —
  weighted for the phase (specifying: what the ticket demands and what was decided alone; review:
  what was found and what it means for the merge; after a merge: what landed and what follows).
  Second: **a decision the operator must take is set off visibly** — the question, the options, a
  recommendation, and what happens if nothing is decided — never buried in prose; when the
  operator must run something, the exact command stands on its own line. Third: no heading over
  an empty section — a part with nothing to say is dropped, not answered with "Nichts". The
  closing note is appended to the full output, never substituted for it, and nothing committed
  changes language because of it.
- **Docstrings describe the current state, never history.** No "formerly / previously / ported
  from", no dead code kept just in case.
- Documentation is part of the change. The module map in `docs/architecture.md` must match reality.
- No personal name appears in documentation. The deciding human is **the operator**.
- `data/`, `reports/`, `results/`, and the catalog are generated and gitignored. Code in, data and
  secrets out.
- [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `refactor:`,
  `docs:`, `test:`, `chore:`. **Never add an AI co-author or a `Co-Authored-By` trailer**, in any
  commit, regardless of any default to the contrary.
- Feature branch → pull request → review → the operator merges. Only a trivial R0 change may go
  straight to `main`. Commit and push finished, green work; never push broken or half-done code.

## 8. Definition of done

Callers updated everywhere; docstrings describe the current state; the architecture map matches;
tests added and green; no stale cruft — dead code, orphaned files, paths that no longer resolve; the
pull-request body complete for the risk class; branch and worktree removed after the merge.

## 9. The tooling

Five commands, each doing one thing. None of them decides policy: the class comes from the
classifier, the gates and transitions from the contract, and the findings from the reviewer.

| Command | Does |
|---|---|
| `just classify` | the risk class of this branch, and why |
| `just gates` | runs exactly the gates that class requires, and prints the evidence table for the pull request |
| `just board status <issue>` / `just board move <issue> "<Status>" --actor <who>` | reads or moves one card; refuses any transition the contract does not list, and any actor the contract does not assign to it. The hand-back to `Specifying` additionally requires `--reason`, which lands on the issue as a comment |
| `just finish <issue>` | verifies a merged ticket and removes only that ticket's worktree and branch traces |
| `uv run python -m workflow.orchestrate run <issue>` | the review cycle: gates → review → fix → review, capped, then one notification |

The board tool answers by **issue number in one request**. Listing a whole project to find one card
is what exhausted the GraphQL budget and left the board unreadable for forty minutes.

The orchestrator reads the reviewer's verdict from a structured marker the review comment carries,
never from its prose — otherwise the loop's exit condition would be a matter of phrasing. It never
merges, approves, or marks anything ready.

A gate the platform cannot run is reported **deferred**, never passed. Mutation needs `fork`, which
Windows does not have; until the development platform moves to macOS (issue #150) it runs in CI.

## 10. The machine-readable contract

`workflow/workflow.toml` carries what tooling reads: risk-class path rules, gates per class, review-agent
selection, board statuses and transitions, and the review loop's blocking severities and cap. It is
the same contract, not a second one. **This document explains the rules; it does not restate them in
a form a program could parse.** That is what kept the two from staying in sync before.
