# Adversarial review

## Findings

Written by the independent reviewer, not transcribed by the builder.

Five rounds, each in a fresh Claude session with the read-only subagents selected by
`review_selection R3 --base origin/main`:

| Round | Review | Head | Result |
|---|---|---|---|
| 1 | [4818275329](https://github.com/QPlus-Capital/trading-system/pull/140#pullrequestreview-4818275329) | `1c0b10b` | 2 Defects, 7 Suspected defects |
| 2 | [4819183725](https://github.com/QPlus-Capital/trading-system/pull/140#pullrequestreview-4819183725) | `54c340f` | 1 Defect, 6 Suspected defects |
| 3 | [4823058968](https://github.com/QPlus-Capital/trading-system/pull/140#pullrequestreview-4823058968) | `1e46fda` | 5 Suspected defects |
| 4 | [4823428302](https://github.com/QPlus-Capital/trading-system/pull/140#pullrequestreview-4823428302) | `4e32005` | 1 Defect, 1 Suspected defect |
| 5 | [4826126351](https://github.com/QPlus-Capital/trading-system/pull/140#pullrequestreview-4826126351) | `abc7593` | **no blocking finding** |

Production code has been unchanged since `54c340f`. Rounds three to five closed test-strength and
artifact-truthfulness gaps only.

| ID | Severity | Finding | Disposition | Status |
|---|---|---|---|---|
| R1-01 | Defect | `move` removed the permit before the status write on the build-start edge, against the constitution's ordering rule and the edge's own trigger | `move` refuses that edge exclusively; only `start` performs it | resolved |
| R1-02 | Defect | `move` ignored the transition actor, performing the Codex build-start edge with no permit; consuming the permit then erased the trace that exposed the bypass | Same refusal closes both | resolved |
| R1-03 | Suspected defect | Zero risk labels on `start` untested; only the greater-than-one half of the boundary was pinned | Exhaustive matrix plus an explicit zero-label case | resolved |
| R1-04 | Suspected defect | The three concurrent-modification defences were unreachable by any test | One-shot `on_write` hook; each guard is the sole killer of its mutant | resolved |
| R1-05 | Suspected defect | `arm`'s body-approvability and risk-class preconditions were unpinned repository-wide | Refusal cases with zero-write assertions | resolved |
| R1-06 | Suspected defect | A `move` whose removal succeeded but whose status write failed refused without saying the permit was gone | `had_permit` threaded into the refusal | resolved |
| R1-07 | Suspected defect | The ordering that makes a refused `move` preserve the permit was unpinned | Pinning test over three non-contract targets | resolved |
| R1-08 | Suspected defect | The registry guard lost the property that no two findings share severity-independent content | Cardinality assertion restored; duplicate injection reproduced | resolved |
| R1-09 | Suspected defect | AC-12 and AC-13 excluded `move`, which reported absence in different words | Parametrisation extended to five operations | resolved |
| R2-01 | Defect | Two committed artifacts asserted coverage of the three lost-write read-backs that did not exist | Operation-specific sticky faults reach all three; the sentences are now true | resolved |
| R2-02 | Suspected defect | `arm`'s status precondition pinned at two of eight values | Parametrised over every non-Ready contract status with zero-write assertions | resolved |
| R2-03 | Suspected defect | `arm` and `_write_approved` exercised only at R3, indistinguishable from constants | Approval parametrised across R0 to R3 | resolved |
| R2-04 | Suspected defect | `had_permit`'s false branch untested, so a message could claim a withdrawal that never happened | Unarmed failed-move test requiring the original error verbatim | resolved |
| R2-05 | Suspected defect | No test proved a refused approval write adds no permit | Absent-label and absent-call assertions | resolved |
| R2-06 | Suspected defect | The registry record promised missing-item diagnostics the test did not deliver | Missing digest mapping computed and printed | resolved |
| R3-01 | Suspected defect | The lookalike label could not discriminate the anchored regex from a prefix match. **The reviewer named `risk:high`, which discriminates nothing** | Replaced with `risk:R4` | resolved |
| R3-02 | Suspected defect | The exhaustive matrix asserted a bare exception type, so three condition-set widenings survived, masked by a later contract error | Anchored refusal-prefix match | resolved |
| R3-03 | Suspected defect | `_write_approved`'s status guard proven at one status through a private call | Production-`arm` interleaving test | resolved |
| R3-04 | Suspected defect | The refusal exit code was a declared non-goal with no pin | CLI refusal exit code and prefix pinned | resolved |
| R3-05 | Suspected defect | Four artifacts and one permanent registry record asserted the lookalike coverage existed | Narrowed to the Start predicate, then made true in round five | resolved |
| R4-01 | Defect | `risk:R4` reached `start` only; the `arm` and `_write_approved` prefix mutants survived while three artifacts said all three were dead. **The reviewer's instruction claimed one word would bind all three** | Two production-`arm` tests bind both remaining sites | resolved |
| R4-02 | Suspected defect | `arm`'s conflicting-risk-label branch exercised only at R3 | Parametrised over R0 to R3 | resolved |
| R4-03 | Note | `start`'s permit short-circuit keyed on the stale pre-write state | Keyed on the moved state, pinned | resolved |
| R4-04 | Note | AC-03's second clause was never executed | The clause now runs | resolved |
| R5-01 | Note | A double-encoded literal at `tests/test_quality_board.py:864` makes the body substitution a dead statement | Graded Note: the conflict guard precedes body validation, so the substitution cannot affect the assertion, and the parametrisation varies the condition under test. The encoding violation is still worth fixing | open |
| R5-02 | Note | `_write_approved`'s observed-risk list is only ever exercised empty, so an always-empty implementation is indistinguishable | Graded Note: no acceptance criterion requires it. AC-11 scopes the approval write to the status clause | open |
| R3-06 | Note | `_verify_status_options` unpinned in four commands, `BoardService.add`'s read-back untested, and the `Done` refusal mutually masked | Pre-existing code this change does not touch; recorded by the reviewer, not requested, and claimed by no artifact | not-applicable |

## Dispositions

No finding was rejected. Both open rows are Notes and are Jan's to take or leave. The round-five
recommendation is to take R5-01, because it is one character and the constitution requires everything
committed to be English, and to leave R5-02 until `board.py` is next touched.

**Two of the five rounds trace to reviewer error, and that belongs in this record.** R3-01 named a
label that cannot discriminate the anchored regex from a prefix match, and R4-01 asserted that adding
one label to the exhaustive matrix would bind three call sites when the matrix reaches only `start`.
The builder implemented both instructions exactly as given. The round count is not a measure of the
builder's work on this change.

Round five is also the first in which no recorded coverage claim outran the executable evidence.
Rounds two, three and four were each blocked on precisely that, so the resolution of the pattern is
worth recording separately from the individual findings.

## Counterexamples attempted

Round five ran 83 source-level mutants over `scripts/quality/board.py` and 41 comparison and
membership flips across `BoardService`; the flips produced zero survivors, and every mutant survivor
is equivalent, hash-order dependent, or a declared out-of-scope pre-existing item. Earlier rounds
added a 2392-case differential of `start`'s accept/refuse decision against `origin/main` — identical
in every case, including the resulting state and the gateway call sequence — and an exhaustive model
check of 49 768 successful operation sequences with zero INV-01 or INV-02 violations.

Attempted without a finding: the reserved edge widened by source and by target; permit ordering
reversed in both `move` and `start`; removal against a card with no permit; a status change failing
after a removal; a gateway raising mid-sequence; a third party withdrawing the permit between the
guard read and the status write; `arm` re-armed, armed from every non-Ready status, and armed with an
unknown class; the conflict set ignoring the requested class in three forms; every aggregated refusal
reduced to its first reason; the zero, one and many risk-label boundaries; `status=None` on all five
state-dependent operations; a label outside the contract vocabulary in every operation; an unknown
project status; the CLI exit code and refusal prefix; and both secret-leak surfaces.

The design question behind R3-01 was answered rather than assumed: treating `risk:R4` as "not a risk
label" is the system-wide contract, because `scripts/quality/issue_body.py` uses the byte-identical
regex, `risk_class_from_labels` resolves `{risk:R3, risk:R4}` to `R3`, and no workflow parses risk
labels at all. A card carrying only `risk:R4` and a permit is refused by `start` — fail-closed.

## Decisions recorded elsewhere

Jan's decisions on re-arming without a board trace, the constitution and contract wording on permit
ordering, adding `board.py` to the mutation policy, and the review-observation gate are outside this
change and live in issues #141, #142 and #134.
