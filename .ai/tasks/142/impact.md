# Impact analysis

## Direct impact

- `.ai/quality/mutation.toml` gains one `board-build-permit` target bounded to the BoardService
  methods that validate statuses, permits, risk labels, write ordering, and read-back verification.
- `pyproject.toml` mirrors the new mutation path and adds `tests/test_quality_board.py` to Mutmut's
  selected test suite.
- `.ai/quality/mutation-baseline.toml` will append the target, recompute the policy fingerprint and
  totals, and record every native Linux board survivor by exact name and reason.
- `tests/test_quality_mutation.py` and `tests/test_ci_cost_workflows.py` bind target selection,
  workflow applicability, policy/config parity, survivor explanations, and unexpected-survivor
  rejection.

## Transitive impact

- A pull request changing only `scripts/quality/board.py` now starts `mutation-critical`.
- The critical Linux mutation run executes the existing Board behavioral suite against the new
  target alongside every previously configured target.
- Future changes to BoardService permit guards cannot silently add an unnamed survivor.

## Critical dependencies

- `scripts/quality/mutation.py` remains the unchanged selector, fingerprint, report, and exact-set
  ratchet implementation.
- `.github/workflows/mutation.yml` remains configuration-driven and reads the production policy.
- `scripts/quality/board.py` is the immutable production subject; its focused fake-gateway tests
  exercise status, label, boundary, interleaving, and write/read-back behavior.
- Native Mutmut 3.5.0 execution requires Linux and Python 3.13.

## Unknown or dynamic edges

- Mutmut assigns generated exact names only during native generation. The baseline cannot be
  inferred from the earlier hand-built approximation and must come from the Linux report artifact.
- GitHub Actions is the available native Linux executor; Windows must continue to refuse Mutmut
  before claiming a result.
- Equivalent or unobservable survivors require source inspection against the generated mutant and
  a stated reason; aggregate counts are insufficient.
