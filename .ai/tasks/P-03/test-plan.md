# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `test_production_candidate_definitions_are_formal_trials_only` | RED: candidate artifact module absent | GREEN: 36 unique formal IDs and metadata records 36 formal plus 5 manual trials |
| AC-02 | `test_daily_artifact_uses_prop_day_and_includes_zero_trade_days` | RED: no daily artifact writer | GREEN: Chicago-boundary events and the missing middle day map to the complete loss-day grid |
| AC-03 | `test_exact_daily_window_and_market_window_invariants` | RED: no shared Decimal aggregator | GREEN: exact daily and candidate-window totals match |
| AC-04 | `test_exact_daily_window_and_market_window_invariants` | RED: no market-window artifact | GREEN: market net R, return, and trade counts sum exactly to each candidate-window cell |
| AC-05 | `test_exact_daily_window_and_market_window_invariants` | RED: no common grid | GREEN: all candidates share one sorted date grid and window grid |
| AC-06 | `test_candidate_missing_one_market_is_absent_everywhere` | RED: no fail-closed candidate completeness rule | GREEN: the incomplete candidate is absent from all streams and named in metadata |
| AC-07 | `test_daily_artifact_feeds_p04_block_selector_directly` | RED: no candidate-to-daily-array artifact | GREEN: every persisted candidate array is accepted directly by `select_block_length` |
| AC-08 | `test_artifact_hashes_use_lineage_convention_and_detect_drift` | RED: no candidate metadata hashes | GREEN: hashes equal `lineage.hash_paths` and mutation is detected |
| AC-09 | `test_candidate_streams_are_copied_byte_exactly_and_selection_cannot_rewrite_them` | RED: edge stage does not publish sidecars | GREEN: all four bytes remain unchanged through downstream selection |
| AC-10 | `test_persistence_cannot_rewrite_existing_study_metrics` | RED: persistence hook absent | GREEN: existing study, ranking, and overfitting bytes remain identical |
| AC-11 | zero-threshold `research.regression` self-comparison of `run_20260724_1146` | N/A: workflow proof over an unchanged completed run | GREEN: every bounded metric has zero drift and `full_history_trades.csv` is byte-identical |
| AC-12 | `uvx --from rust-just just check` plus all evidence-table R3 gates | N/A: cumulative workflow exit criterion | GREEN: local full check and readiness pass |
| INV-01 | `test_continuous_payload_reuses_stage1_net_trade_rows` and Stage-1 swap tests | RED: chosen-path canonical event payload absent | GREEN: gross `r`, separate `swap_r`, and canonical `net_r` are carried without cost recomputation |
| INV-02 | `test_persistence_cannot_rewrite_existing_study_metrics` plus unchanged-run regression | RED: no no-drift guard around the new hook | GREEN: existing reports and completed-run metrics remain unchanged |
| INV-03 | `test_production_candidate_definitions_are_formal_trials_only` | RED: no formal candidate identity API | GREEN: identity is variation x train length; inner combinations remain internal |
| INV-04 | `test_candidate_missing_one_market_is_absent_everywhere` | RED: no completeness guard | GREEN: incomplete candidates are omitted rather than zero-filled |
| INV-05 | `test_exact_daily_window_and_market_window_invariants` | RED: three exact views do not exist | GREEN: every view derives from one event set with exact Decimal equality |
| INV-06 | `test_candidate_streams_are_copied_byte_exactly_and_selection_cannot_rewrite_them` | RED: no immutable pre-filter sidecars | GREEN: downstream selection cannot rewrite copied evidence |
| INV-07 | `test_generated_candidate_artifacts_remain_gitignored` | RED: no explicit guard for generated paths | GREEN: generated run artifacts remain ignored and uncommitted |
| INV-08 | `git diff --quiet origin/main -- live core/strategies core/broker.py core/instruments.py` | N/A: scope invariant | GREEN: no live, signal, broker, sizing, risk, or account path changed |

Every new guard is run before implementation and its failing output is recorded in
`evidence.md`. Focused tests remain synthetic and fast; no live system is invoked.
