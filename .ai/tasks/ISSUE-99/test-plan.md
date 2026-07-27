# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01, INV-01 | `test_closed_position_uses_entry_side_for_direction` | RED: closed BUY with `side=FLAT` emits `False` | GREEN: BUY emits `True`; SELL emits `False` |
| AC-02, INV-01 | `test_unrecognized_entry_side_fails_closed` | RED: invalid entry silently emits short | GREEN: `ValueError` names the invalid entry side |
| AC-03, AC-04 | real ten-market raw-report/extraction reconciliation | RED: XAU `374/386` becomes `0/760`; all 8,703 become short | GREEN: every per-market BUY/SELL count equals long/short output |
| AC-05, INV-04 | `test_extracted_entry_side_drives_long_low_and_short_high` | RED: BUY is short, so its favorable high hides the adverse low | GREEN: combined synchronized mark is exactly the long-low plus short-high result |
| AC-06, INV-02, INV-05 | row-by-row holdout/full-history comparison | RED: corrected artifacts absent | GREEN: identity/gross columns exact; only declared direction/swap/derived fields move |
| AC-07, INV-03, INV-06 | Stage-3/4 diagnostic rerun and explicit before/after report | RED: current baseline uses all-short direction | GREEN: swap/path/breach/verdict movements recorded without relaxed limits |
| AC-08, INV-07 | cumulative local R3 gates plus infrastructure record | RED: task/evidence incomplete | GREEN: all local gates pass; Linux mutation alone remains blocked |
