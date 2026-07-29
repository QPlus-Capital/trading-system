# Independent review

## Status

The final independent adversarial and live-money re-review completed on 2026-07-29 with no finding.
All earlier findings are resolved. This file records review evidence only and does not authorize a
ready, merge, or auto-merge action.

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

## Latest re-review dispositions

The next complete independent re-review verified N2-N4 by execution and reported the three
test-guard findings below. These are builder dispositions, not an independent approval; Claude must
review the resulting fix.

| ID | Severity | Finding | Disposition | Status |
|---|---|---|---|---|
| F1 | Suspected defect | The known-login suffix matcher protected only `.ai/**`, so independently written code representations could evade the production scan. | Apply the suffix matcher to normalized text from every tracked path while retaining the assignment-shape matcher; commit all eight supplied code counterexamples. | resolved |
| F2 | Note | Valid Python integer literals containing digit separators evaded both matchers. | Remove only underscores between two digits before applying either matcher; commit all three supplied underscore forms. | resolved |
| F3 | Note | The suffix alternation duplicated the two current profile suffixes and could omit a future account. | Build the deterministic escaped alternation from `ACCOUNTS` and assert every configured profile contributes its suffix. | resolved |

The supplied oracle was run before remediation: 11 cases failed and all three feasibility checks
passed. After remediation all 14 pass, the full account file passes 81 tests, and the tree-wide
scan reports zero hits across the tracked repository. No production, live, monitoring, research, or
runner file changed in this round.

## Final independent re-review — no findings

Claude completed the final R3 adversarial and live-money review on 2026-07-29:
[GitHub review 4807831900](https://github.com/QPlus-Capital/trading-system/pull/123#pullrequestreview-4807831900).
The review is anchored to HEAD `fbbdda8fddb09806bec5dc9c6748be09cae8e368`.

**Verdict: no finding. This is clean.** Every claim was verified by execution against the production
guard:

- all 15 independently chosen login-reintroduction forms were caught by
  `_contains_login_literal`; ten of those forms had evaded the previous guard;
- five unrelated-number probes produced no false positive: property-test seed `20260721`, public
  magic `770077`, `x = 12_345`, `total = 4646`, and an SSRN identifier;
- the actual tracked tree contains 375 files and produces zero login-literal hits;
- `_LOGIN_SUFFIXES` is derived from `ACCOUNTS`, so adding a third configured account extends the
  protection automatically;
- the one removed assertion was replaced by an assertion against the production
  `_contains_login_literal` function, and the independent forms were added to the pre-existing
  guard test's own parameter list.

No production file changed in the reviewed round. No MT5 terminal was initialized, no runner was
contacted, no live account was read, and no order was placed, modified, or closed. No decision
requiring Jan remains in the review.
