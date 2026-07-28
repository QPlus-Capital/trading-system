# Independent review

## Status

The complete independent review found F1-F5 below. Builder remediation is complete only after the
recorded gates; the material fixes require another complete independent adversarial and live-money
review. This file does not mark the PR ready.

## Findings

| ID | Severity | Finding | Disposition | Status |
|---|---|---|---|---|
| F1 | P1 | The hard-coded profile ignores a missing login environment variable, so AC-03 cannot bind. | Require environment parsing in both profile selection and direct guard use; pin refusal before fake connection. | resolved |
| F2 | P1 | Preflight prints both secret login values verbatim. | Mask both through one `***NNN` helper and assert full values absent from captured stdout. | resolved |
| F3 | P2 | Anti-recommit scan misses canonical environment syntax and passes over a partial/empty tree. | Match canonical forms, include tests, resolve Git top-level, assert sentinels/count, and scan docs for bare long numbers. | resolved |
| F4 | P2 | Swap, parity, and dashboard consumers use an operator-selected terminal without identity verification. | Delegate all three to the same connected-account guard before their first data read. | resolved |
| F5 | P2 | Login and path from one operator file make a consistent cross-profile copy self-validating. | Jan ratified one non-secret code-owned four-digit suffix per profile. | resolved |

## Dispositions

- F1 is reproduced by the recorded `DID NOT RAISE SystemExit` RED result and fixed by required
  environment parsing in both `get_account()` and `guard_account()`.
- The review's preflight counterexample printed two distinct full fake logins. `_masked_login()`
  now emits only the repository-standard final-three-digit form, and stdout rejects both originals.
- The scan counterexamples produced five failures: all three canonical login forms were missed,
  tests were excluded, and a nested Git subdirectory returned only that partial subtree. The scan
  now proves its population before treating an empty finding list as evidence.
- Wrong-login fakes formerly reached swap pulling, completed parity, and loaded dashboard history.
  Each now exits through `guard_connected_account()` before those counters move.
- A complete MEX-to-TTP environment copy formerly passed. The TTP suffix pin rejects it, while
  synthetic matching-suffix values prove both profiles' accepting path.
- F-043 through F-046 generalize the four confirmed defect classes.
- F6 (dead compatibility parameter) and F7 (dashboard `SystemExit` presentation) were not requested
  and remain unchanged. Halt/exception presentation is not widened in this remediation.
- The complete independent adversarial and live-money review must run again because live,
  monitoring, and research-snapshot entrypoints changed materially.

## Required review focus

- AC-03: missing/malformed environment identity must refuse before terminal connection.
- No profile or caller may retain an optional/fallback expected login.
- Correct environment values must preserve the previous valid connection and guard behavior.
- No tracked or emitted value may disclose account identity or an operator home path.
- Entry commands must actually load `.env`; documentation alone is not evidence.
