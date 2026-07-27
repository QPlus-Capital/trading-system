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
