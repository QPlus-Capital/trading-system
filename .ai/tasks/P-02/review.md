# Adversarial review

## Findings

No findings; 10 counterexamples attempted.

## Counterexamples attempted

1. Drove `run_walkforward` through its nested optimizer rather than inspecting source text.
2. Drove the independent Stage-3 `_optimize` path directly.
3. Supplied two parameter combinations to catch a one-candidate-only override.
4. Checked every captured training mapping rather than only the last invocation.
5. Considered a stale `flatten_on_stop=True` in composed parameters; the explicit entry is last.
6. Re-ran continuous OOS tests to detect selection/execution boundary drift.
7. Re-ran the real strategy stop test proving `False` leaves the position unflattened.
8. Re-ran portfolio extraction and walk-forward attribution suites for seam regressions.
9. Audited every `build_run_config` caller to find a missed training selector.
10. Audited the diff for Stage-1 artifacts, `research/regression.py`, live paths, and global
    defaults.

## Dispositions

The code-only draft must not claim validation of research-number movement. Claude's independent
review and the later threshold decision remain required.
