# Adversarial review

## Findings

Claude completed round-two review
[4819183725](https://github.com/QPlus-Capital/trading-system/pull/140#pullrequestreview-4819183725)
against `54c340f`, then completed round-three review
[4823058968](https://github.com/QPlus-Capital/trading-system/pull/140#pullrequestreview-4823058968)
against `1e46fda`, both in fresh sessions. The builder resolved the actionable findings below; a
complete independent re-review of the resulting head remains required.

| ID | Severity | Finding | Disposition | Status |
|---|---|---|---|---|
| D-01 | Defect | Three lost-write read-backs had no executable evidence while two artifacts claimed complete coverage | Added operation-specific sticky status and label-addition faults plus behavioral tests for `move`, `start`, and final approval; strengthened and rehashed the permanent finding | resolved |
| S-01 | Suspected defect | `arm` rejected only two observed non-Ready values in tests | Parameterized over every contract status except `Ready to Implement`, with zero-write assertions | resolved |
| S-02 | Suspected defect | `arm` and `_write_approved` were indistinguishable from R3 constants | Parameterized successful approval across R0, R1, R2, and R3 with class-specific bodies and exact labels | resolved |
| S-03 | Suspected defect | The `had_permit=False` failure branch could discard the real write error | Added an unarmed failed-move test that requires the original gateway error verbatim | resolved |
| S-04 | Suspected defect | Refused approval writes did not prove that no permit was added | Approval-refusal cases now assert both absent label state and absent `add approved` call | resolved |
| S-05 | Suspected defect | The Start matrix did not distinguish the anchored risk regex from a prefix match | Added the discriminating lookalike `risk:R4` to the exhaustive universe while deriving expected risk labels from the four exact contract labels | resolved |
| S-06 | Suspected defect | Registry migration failures no longer named missing digests | Compute the missing digest/severity mapping explicitly and print its sorted digest keys | resolved |
| N-01 | Note | AC-01's parameterized test name contradicted its `Implementing` refusal case | Removed `Implementing` from the demotion parameterization and kept the dedicated reserved-edge refusal test | resolved |
| N-02 | Note | Workflow prose under-described permit removal as Ready-only | Documented every successful generic `move`, whatever its source status | resolved |
| N-03 | Note | Manual command documentation used unowned generated-block markers | Removed the markers and bound the test to the ordinary `Board command surface` section | resolved |
| N-04 | Note | Red evidence did not identify the test revision or separate defects from coverage gaps | Bound the original run to test commit `a91eed6` and recorded seven reproduced defects separately from nine mutant-killing coverage guards | resolved |
| N-05 | Note | The replacement transition finding dropped predecessor regression names | Restored all three predecessor test names and the new failure-propagation guard in the rehashed finding | resolved |
| R3-S-01/S-05 | Suspected defect | The reviewer-requested `risk:high` lookalike could not distinguish the anchored regex from a `risk:R` prefix implementation, leaving three mutants and five claims unbound | Replaced it with `risk:R4`; the 448-case matrix now kills the `start`, `arm`, and `_write_approved` prefix mutants, making the existing registry and task-artifact claims true | resolved |
| R3-S-02 | Suspected defect | The exhaustive Start matrix accepted any `BoardError`, so widened status conditions were masked by a later contract error | Required every refused matrix case to start with the exact aggregate `Start requirements not met:` prefix | resolved |
| R3-S-03 | Suspected defect | `_write_approved`'s status guard was reached only through a private call at one status, not through the production `arm` interleaving | Drove `arm` through a post-status-write change to `Implementing` and proved the approval write is refused before `add approved` | resolved |
| R3-S-04 | Suspected defect | No test pinned refusal exit code 2 and the stable `Board operation refused:` prefix | Added a CLI refusal test asserting both exact exit code and stderr | resolved |
| R3-N-01 | Note | Removing the unarmed-card short circuit caused a spurious label-removal write | The existing failed unarmed-move test now asserts that no remove call occurs | resolved |
| R3-N-02 | Note | Status-option verification in four commands and `add` read-back remain unpinned | Explicitly recorded by the reviewer as pre-existing and not requested; no claim in this remediation treats them as newly protected | not-applicable |
| R3-N-03 | Note | The defence-in-depth `Done` refusal remains mutually masked | Explicitly recorded by the reviewer as pre-existing and correctly unclaimed; no production or contract change was made | not-applicable |
| R3-N-04 | Note | Evidence named the prior tested head | Rebind the final evidence to this remediation's tested implementation commit; the later evidence-only commit is accepted by the repository currency rule | resolved |

## Dispositions

No blocking finding was rejected or deferred. Production behavior remains unchanged because the
review confirmed the existing guards are correct; round three strengthens executable evidence and
restores the truthfulness of the exact-label claims. The two explicitly pre-existing Notes remain
recorded without expanding the remediation scope.

The pull request remains draft. The earlier Jan decisions about re-arming without a board trace,
constitution/contract wording, adding `board.py` to mutation policy, and issue #134 remain outside
this remediation exactly as recorded in the issue and evidence.
