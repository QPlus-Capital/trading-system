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
- The earlier F6 deferral for the dead compatibility parameter is superseded by Jan's N4 decision
  below. F7 (dashboard `SystemExit` presentation) remains out of scope; halt/exception presentation
  is not widened in this remediation.
- The complete independent adversarial and live-money review must run again because live,
  monitoring, and research-snapshot entrypoints changed materially.

## Required review focus

- AC-03: missing/malformed environment identity must refuse before terminal connection.
- No profile or caller may retain an optional/fallback expected login.
- Correct environment values must preserve the previous valid connection and guard behavior.
- No tracked or emitted value may disclose account identity or an operator home path.
- Entry commands must actually load `.env`; documentation alone is not evidence.

## Complete re-review dispositions

The complete independent re-review verified F1-F5 by execution and found N1-N4. The following are
builder dispositions, not an independent approval; the material fixes require another complete
adversarial and live-money review.

| ID | Severity | Finding | Disposition | Status |
|---|---|---|---|---|
| N1 | P2 | The anti-recommit guard missed quoted, JSON, annotated, comment/docstring, and `.ai` representations. | Parse 22 committed serialization forms and apply a narrow six-to-ten-digit known-suffix detector only under `.ai/**`; F-050 records the generalized defect. | resolved |
| N2 | P2 | The documented Windows path syntax made uv return success after dropping the path and every later identity/Telegram value; missing remote transport was silent. | Single-quote the canonical dotenv layout, round-trip two Windows paths and both Telegram values through real uv, document exported-variable precedence in both operator guides, and warn when Telegram is unavailable; F-051 records the generalized defect. | resolved |
| N3 | P3 | Zero-padding let a login shorter than the four-digit witness pass. | Require the raw login to be longer than and end with its code-owned suffix before accepting it; F-052 records the boundary. | resolved |
| N4 | P3 / Jan decision | `guard_account(execute=...)` implied mode-dependent strictness while being ignored and retained three equivalent mutants. | Remove the parameter and every caller argument; an 80-case profile/login/currency oracle records zero accept/refuse divergences; F-053 records the misleading-safety-parameter class. | resolved |

The four earlier remediations remain untouched: preflight masking, non-vacuous top-level scanning,
the three guarded terminal consumers, and the independent code-owned suffix are unchanged except
for N3's strictly stronger raw-length precondition. No MT5 terminal or runner was accessed.

The N4 baseline remediation removes all three obsolete `execute`-argument survivors. Expanding the
critical scope to `Notifier.__init__` initially exposed six survivors: five real beep branches are
now killed by platform/opt-in behavioral tests. The remaining default-argument mutant is classified
only because Mutmut's unchanged trampoline binds and passes `beep=False` before the inner mutated
default can be reached; it cannot change observable runtime behavior. This disposition remains
subject to the required fresh independent review.
