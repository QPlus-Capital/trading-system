# Test plan

## Traceability

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | Retained-report summary equality assertion | RED: total is `4,406`, not `4,568` | GREEN: summary is exactly `4,568/4,151/417/0` |
| AC-02 | Report/baseline/policy target-sequence equality assertion | RED: stale artifact has not been reconciled with the measured report | GREEN: all 22 targets match report and policy exactly |
| AC-03 | Old/new survivor-set difference assertion and evidence list | RED: 29 killed names remain allowed | GREEN: all 29 are absent and listed explicitly |
| AC-04 | Exact survivor-classification set assertion | RED: 53 measured survivors are unexplained | GREEN: all 417 are classified exactly once and no unobserved name is admitted |
| AC-05 | New-survivor namespace attribution assertion | RED: new names are unexplained | GREEN: all 53 are confined to #96 path-risk/sizing functions; #97/#98 add none |
| AC-06 | `check_baseline` against retained `critical.toml` | RED: returns four comparison issues | GREEN: returns an empty issue list |
| AC-07 | Scoped `git diff --exit-code` over policy, tooling, tests, and production | RED: no scoped proof recorded | GREEN: no out-of-scope diff |
| AC-08 | Local R3 commands plus retained Linux report verification | RED: stale comparison fails | GREEN: every local gate passes and the Linux limitation is documented |
| AC-09 | GitHub PR-state inspection | RED: no delivery exists | GREEN: separate PR is draft, with auto-merge disabled |
| INV-01 | Add an unclassified sentinel survivor to the comparator | RED: stale baseline mismatch obscures the invariant | GREEN: the sentinel is reported unexplained and fails closed |
| INV-02 | Total and policy-diff assertions | RED: total remains `4,406` | GREEN: total is `4,568` and no configured threshold changes |
| INV-03 | Now-killed survivor absence assertion | RED: 29 killed names remain allowed | GREEN: all 29 are removed |
| INV-04 | Old/new derived-score calculation and comparator-diff audit | RED: score change is only an uncontextualized failure | GREEN: both scores are recorded and no score rule is edited |
| INV-05 | Byte-scope audit over mutation policy, project config, tests, and production | RED: not yet demonstrated | GREEN: all named paths are unchanged |
| INV-06 | Live/MT5 process boundary audit | RED: not yet recorded | GREEN: no live process or terminal command occurs |

## Red-first proof

Compare retained run `30333581031`'s `critical.toml` against the current committed baseline with
`load_baseline`, a parsed `MutationReport`, and `check_baseline`.

Expected RED before regeneration:

- total mismatch: expected `4,406`, observed `4,568`;
- exactly 29 baseline survivors reported newly killed;
- exactly 53 observed survivors reported unexplained.

## Green proof

Run the identical comparison after wholesale regeneration. It must return an empty issue list.

## Ratchet assertions

- New total is `4,568 > 4,406`.
- Summary fields exactly equal the retained report and sum to the total.
- Target sequence exactly equals the report and policy.
- Baseline survivor set exactly equals the report's survived set.
- The 29 newly killed names are absent.
- The 53 added exact names are confined to #96's path-risk/sizing functions.
- No status threshold, comparison implementation, target policy, or test selection changes.

## Repository gates

- `just check`
- `just check-properties`
- `just check-invariants`
- `just check-security`
- focused mutation parser/baseline tests
- task validation, impact, and readiness

## Safety

No live process or MT5 API is invoked.
