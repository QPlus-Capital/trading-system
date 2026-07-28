# Impact analysis

## Direct impact

- `.ai/quality/mutation-baseline.toml` changes the exact expected Linux critical-mutation result.
- `scripts/quality/mutation.py::load_baseline` reads the file and validates count consistency,
  exact survivor identity, classifications, and reasons.
- `scripts/quality/mutation.py::check_baseline` compares future critical reports against the exact
  total, target list, survivor set, health statuses, and derived score.
- `scripts/quality/hooks/decisions.py::baseline_evidence_decision` prevents a baseline-changing
  commit or push without successful mutation evidence.
- `.github/workflows/mutation.yml` runs the Linux-only mutation gate and retains
  `.ai/mutation/critical.toml`.

## Transitive impact

- Future critical mutation runs compare their complete report with the regenerated total, target
  list, status counts, and exact survivor identities.
- `scripts/quality/pr_ready.py` consumes the mutation-gate evidence for R3 readiness.
- The baseline hook decision prevents a baseline-changing commit or push without recorded
  mutation evidence.
- No trading, research, live, monitoring, result, or open-PR branch is reached transitively.

## Critical dependencies

- `.ai/quality/mutation.toml` defines the unchanged critical targets and test selection.
- `scripts/quality/mutation.py` defines the unchanged fail-closed comparator.
- `.github/workflows/mutation.yml` supplies the required Linux/fork execution environment.
- `tests/test_quality_mutation.py`, `tests/test_quality_hooks.py`, and
  `tests/test_quality_pr_ready.py` guard parsing, enforcement, and readiness integration.

## Measured source

GitHub Actions run `30333581031` executed the critical workflow on
`main@494eafc5404bb9148c1df0887f7260b189cc36d6`. Its mutation self-test passed. Its retained
`critical.toml` contains the complete `4,568`-mutant result and is the sole measurement used for
regeneration.

## Coupled quantities

The baseline total, status counts, target sequence, survivor identities, classifications, reasons,
and derived score form one coupled artifact. They are regenerated together from the same retained
report. No single count or survivor list is patched independently.

## Merge attribution

- #96 changed chronological HWM logic in `research/portfolio/sizing.py` and
  `research/portfolio/path_risk.py`. All 29 now-killed names and all 53 newly observed survivor
  names are confined to those functions.
- #97 changed `research/portfolio/stats.py`; it contributes to the larger mutant surface but
  produces no newly unexplained survivor in the retained report.
- #98 changed `research/engine/continuous.py`; it contributes to the larger mutant surface but
  produces no newly unexplained survivor in the retained report.

## Behaviour and result impact

No trading, research, live, monitoring, sizing, risk, signal, artifact, or reported numerical
behavior changes. Only the expected mutation evidence changes. Future Linux runs pass only when
they reproduce the exact 417 classified survivors and introduce no additional one.

## Workflow finding

Mutmut 3.5 requires `fork` and therefore cannot execute on the operator's native Windows machine.
The dedicated Linux Actions job is the sole supported critical-mutation environment. The
infrastructure-red merge exception used while the organisation's Actions allowance was exhausted
until 2026-08-01 had no local substitute for this gate, allowing #96/#97/#98 to merge while the
baseline remained stale.

## Unknown or dynamic edges

None. The consumer paths are repository tooling, and the binding Linux report is retained and
content-complete.
