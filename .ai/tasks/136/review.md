# Adversarial review

## Findings

Claude completed round-two review
[4819183725](https://github.com/QPlus-Capital/trading-system/pull/140#pullrequestreview-4819183725)
against `54c340f` in a fresh session. The builder resolved every finding below; a complete
independent re-review of the resulting head remains required.

| ID | Severity | Finding | Disposition | Status |
|---|---|---|---|---|
| D-01 | Defect | Three lost-write read-backs had no executable evidence while two artifacts claimed complete coverage | Added operation-specific sticky status and label-addition faults plus behavioral tests for `move`, `start`, and final approval; strengthened and rehashed the permanent finding | resolved |
| S-01 | Suspected defect | `arm` rejected only two observed non-Ready values in tests | Parameterized over every contract status except `Ready to Implement`, with zero-write assertions | resolved |
| S-02 | Suspected defect | `arm` and `_write_approved` were indistinguishable from R3 constants | Parameterized successful approval across R0, R1, R2, and R3 with class-specific bodies and exact labels | resolved |
| S-03 | Suspected defect | The `had_permit=False` failure branch could discard the real write error | Added an unarmed failed-move test that requires the original gateway error verbatim | resolved |
| S-04 | Suspected defect | Refused approval writes did not prove that no permit was added | Approval-refusal cases now assert both absent label state and absent `add approved` call | resolved |
| S-05 | Suspected defect | The Start matrix did not distinguish the anchored risk regex from a prefix match | Added `risk:high` to the exhaustive universe while deriving expected risk labels from the four exact contract labels | resolved |
| S-06 | Suspected defect | Registry migration failures no longer named missing digests | Compute the missing digest/severity mapping explicitly and print its sorted digest keys | resolved |
| N-01 | Note | AC-01's parameterized test name contradicted its `Implementing` refusal case | Removed `Implementing` from the demotion parameterization and kept the dedicated reserved-edge refusal test | resolved |
| N-02 | Note | Workflow prose under-described permit removal as Ready-only | Documented every successful generic `move`, whatever its source status | resolved |
| N-03 | Note | Manual command documentation used unowned generated-block markers | Removed the markers and bound the test to the ordinary `Board command surface` section | resolved |
| N-04 | Note | Red evidence did not identify the test revision or separate defects from coverage gaps | Bound the original run to test commit `a91eed6` and recorded seven reproduced defects separately from nine mutant-killing coverage guards | resolved |
| N-05 | Note | The replacement transition finding dropped predecessor regression names | Restored all three predecessor test names and the new failure-propagation guard in the rehashed finding | resolved |

## Dispositions

No finding was rejected or deferred. Production behavior remains unchanged because the review
confirmed the existing guards are correct; this round strengthens executable evidence,
documentation, and permanent registry truthfulness.

The pull request remains draft. The earlier Jan decisions about re-arming without a board trace,
constitution/contract wording, adding `board.py` to mutation policy, and issue #134 remain outside
this remediation exactly as recorded in the issue and evidence.
