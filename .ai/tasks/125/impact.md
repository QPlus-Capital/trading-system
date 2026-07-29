# Impact

## Direct impact

`scripts/quality/mutation.py`

- `check_baseline` loses the total comparison. Its four remaining comparisons and the health checks
  are untouched; a specific complete-policy fingerprint comparison replaces the incidental coverage
  protection formerly supplied by the total.
- `summary_lines` is new: the operator-facing summary of one run, extracted from `run` unchanged and
  then extended with the observed and baseline totals for critical scope.
- `run` prints through `summary_lines` instead of an inline f-string. Its verdict, its exit codes and
  its report file now carry the fingerprint of the complete policy independently of selected scope.
- `policy_fingerprint` canonically sorts target and pattern order only, then hashes every target's
  exact ID, policy path spelling, and complete pattern multiset. Paths are normalized only where
  execution compares them with repository paths, not in the policy identity.
- `load_baseline` requires a valid SHA-256 policy fingerprint, and `check_baseline` fails when the
  report and baseline fingerprints differ.

`tests/test_quality_mutation.py`

- Fingerprint behaviour, required-field, persistence, full-policy fast-scope, and policy-substitution
  regressions supplement the existing behavioural tests and 128-case differential oracle.
- `test_a_weakened_test_creates_a_survivor_and_the_ratchet_rejects_it` keeps its subject and gains a
  correct fixture; see `test-plan.md`.

## Transitive impact

- `just mutation-critical` and `just mutation-self-test` invoke `run`; both keep their exit
  semantics. A run that previously failed only on the total now exits 0.
- `.github/workflows/mutation.yml` invokes the recipe verbatim and is unchanged.
- `scripts/quality/pr_ready.py` and `scripts/quality/hooks/decisions.py` consume the mutation gate's
  exit status, not its messages. `baseline_evidence_decision` still requires passing mutation
  evidence when a committed quality baseline changes; the baseline now gains one computed key.
- No consumer parses the summary text. Searching `justfile`, `scripts`, `.github`, `tests`, `core`,
  `research`, `live` and `monitoring` for `mutation total`, `Mutant total` and `Mutation critical:`
  returns exactly one hit, the definition site at `scripts/quality/mutation.py:329`. The tests assert
  on the reported numbers, not on the wording.

## Critical dependencies

`.ai/quality/critical-dependencies.toml` names no edge into `scripts/quality/mutation.py`. The
module's own dependency on `scripts.quality.classify` is unchanged; no classification path is
touched.

## Unknown or dynamic edges

`load_baseline` and `load_policy` read TOML by path at call time. Both keep their signatures;
baseline validation additionally refuses a missing or malformed fingerprint while preserving the
internal count-sum check. The mutant names in the report are supplied by Mutmut at run time and are
matched against the baseline by exact name, which this change does not alter.
