# Test plan

## Red-first guards

- A symbol-bearing `BUY_CANCELED`/unknown deal type must raise with its identifiers instead of
  becoming SELL.
- A boolean deal type must raise rather than passing through integer coercion.
- An empty-symbol balance/credit record must remain ledger-only.
- One long-to-short INOUT sequence must produce two closed segments with directions BUY then SELL,
  volumes `1.0` then `0.5`, the reversal ticket as the second opening boundary, and exact aggregate
  money conservation.
- Paired OUT_BY closes must produce one correctly attributed trade per position identifier.
- Scale-ins plus partial exits must produce one closed segment whose total volume and money match
  the complete deal sequence.
- The reversal segment's P-14 risk basis must be the ledger balance before its own INOUT ticket.

The focused test module will be run before implementation and its real failure recorded in
`evidence.md`.

## Traceability

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `test_symbol_bearing_non_trade_deal_type_fails_closed` | RED: type 13 silently became SELL | GREEN: contextual ValueError before a row |
| AC-02 | the boolean case of the same parametrized test | RED: `True` silently became BUY | GREEN: exact-type guard rejects bool |
| AC-03 | `test_empty_symbol_cash_deal_stays_ledger_only` | RED: no independent ledger/trade guard | GREEN: absent from trades, exact in ledger |
| AC-04 | both INOUT behavioural tests | RED: one stale-direction trade | GREEN: two coherent segments and exact residual |
| AC-05 | `test_out_by_deals_close_their_own_position_ids` | RED: no trades emitted | GREEN: long and short close by their own IDs |
| AC-06 | scale-in/partial-exit test and INOUT partial-exit test | RED: only first entry volume survived | GREEN: volume and all money legs conserved |
| AC-07 | existing monitoring deal, risk, fee, and dashboard suites | RED: new cases failed before implementation | GREEN: focused/integration suites pass |
| AC-08 | `test_reversal_segment_uses_the_balance_before_its_inout_deal` | RED: reversal boundary absent | GREEN: basis is balance before INOUT ticket |
| AC-09 | source diff and focused synthetic fixtures | RED: no package scope proof | GREEN: no live/research/core production diff |
| AC-10 | SHA-256 comparison of both reference trade CSVs | RED: no package parity record | GREEN: hashes remain the recorded baseline |
| AC-11 | cumulative local R3 commands and blocked mutation record | RED: implementation absent | GREEN: all executable local gates pass; Linux mutation explicitly blocked |
| AC-12 | branch/PR state checks | RED: no package branch or draft | GREEN: feature branch and draft-only publication |
| INV-01 | source diff plus test import audit | RED: no package boundary proof | GREEN: no runner/bridge call or live import added |
| INV-02 | ledger regression suite | RED: new reconstruction unguarded | GREEN: complete Decimal ledger unchanged |
| INV-03 | BUY/SELL, INOUT, OUT_BY, and contradictory-side tests | RED: direction defaulted from else branch | GREEN: only explicit deal type supplies direction |
| INV-04 | invalid type and bool cases | RED: unknown symbol deal emitted SELL | GREEN: every unsupported value raises |
| INV-05 | INOUT and partial-flow money sums | RED: reversal modes disappeared | GREEN: each amount enters at most one segment |
| INV-06 | equality against complete `deal_ledger` | RED: no reversal conservation oracle | GREEN: closed-segment sums reconcile exactly |
| INV-07 | paired OUT_BY fixture | RED: entry mode ignored | GREEN: each deal uses its own position ID |
| INV-08 | research diff plus artifact hashes | RED: no package parity record | GREEN: no research producer or artifact moves |
| INV-09 | Decimal type assertions and money-leg tests | RED: no new-path proof | GREEN: every money accumulator remains Decimal |

## Regression guards

- Run all monitoring deal and risk-view tests, including existing fee and same-timestamp basis
  fixtures.
- Run dashboard tests to prove the production consumer accepts normal reconstructed rows.
- Run `just check`, `check-invariants`, properties, security, and the task validator locally.
- Compare the existing reference research trade-CSV hashes without rerunning Stage 1-4.

## Mutation focus

Mutations must be killed for:

- strict `type(value) is int`;
- BUY/SELL constants and direction output;
- IN/OUT/INOUT/OUT_BY entry branches;
- reversal residual-volume arithmetic;
- position attribution;
- exact-once money accumulation;
- close/open ticket ordering.

The Linux Critical mutation workflow cannot execute until the GitHub Actions quota resets on
2026-08-01. It remains a readiness blocker and is not represented as a pass.

## Safety

All fixtures are in-memory dictionaries/DataFrames. No test imports a runner, initializes MT5,
calls `history_deals`, or can place, modify, or close an order.
