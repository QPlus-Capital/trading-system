# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `test_walkforward_training_configs_do_not_flatten_on_stop` | RED: captured Stage-1 training params omit the key and inherit `True` | GREEN: every captured config contains `False` |
| AC-02 | `test_portfolio_training_configs_do_not_flatten_on_stop` | RED: captured Stage-3 optimizer params omit the key and inherit `True` | GREEN: every captured config contains `False` |
| AC-03 | focused continuous-window, portfolio-trade, and strategy-stop suites | Existing behavior | GREEN without production changes outside the two selectors |
| AC-04 | `just check` plus forbidden-artifact diff | N/A | GREEN; no Stage-1 or regression artifact exists |
| INV-01 | production diff audit | N/A | Exactly two production files changed |
| INV-02 | `git diff --quiet origin/main -- research/engine/continuous.py` | N/A | GREEN |
| INV-03 | forbidden-path and generated-artifact audit | N/A | GREEN |
| INV-04 | live/monitoring/core diff plus full suite | N/A | GREEN |
| INV-05 | production diff audit | N/A | No money or numeric representation changed |
