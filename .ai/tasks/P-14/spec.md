# P-14: Make dashboard deal reconstruction exact

## Problem

The monitoring path counts a trade's own opening deal in its sizing basis, omits MT5's `fee`
money leg, and can combine deal history with a later account snapshot
(`monitoring/deals.py`, `live/mt5_bridge.py`, and `monitoring/dashboard.py`).

## Goal

Make the dashboard's reconstructed balance, net PnL, equity curve, and per-trade risk basis use
complete deal money legs and one stable broker snapshot, without changing any trading behaviour.

## Non-goals

- Changing order placement, position sizing, risk limits, account guards, runner cycles, or live
  configuration.
- Changing research, backtest, selection, lineage, methodology, or reported research numbers.
- Querying, restarting, or otherwise interacting with a real MT5 terminal or live account.
- Building any new dashboard feature beyond correcting the existing reconstruction.

## Behavioural requirements

- Export each deal's ticket and `fee` from `Mt5Bridge.history_deals`; represent every exported
  money leg as `Decimal` constructed from its string boundary value.
- Include `fee` in both the complete deal ledger and each closed trade's `net_pnl`.
- Carry the opening deal ticket into reconstructed trades and order same-second balance events by
  `(timestamp, ticket)`. A trade's basis includes earlier deals at that timestamp but excludes its
  own opening deal and all later deals.
- Preserve deterministic input order as a fallback sequence only for synthetic/legacy deal
  records without tickets; real bridge records always carry the MT5 ticket.
- Read history, account, then history again. Accept the snapshot only when both deal reads have
  the same ordered identity and money content; otherwise retry up to three attempts and fail
  closed with no dashboard data.
- Exercise the stable-snapshot helper through `_load_live`, not only in isolation.

## Acceptance criteria

- AC-01: A same-second earlier deal affects the trade basis while the trade's own opening
  commission/fee does not.
- AC-02: MT5 `fee` is exported and fee-only events move the ledger/equity curve and reduce
  reconstructed trade `net_pnl`.
- AC-03: A test simulating a deal booked between history/account reads proves `_load_live`
  discards the mixed snapshot and returns the stable ledger/account pair.
- AC-04: Three continuously changing snapshots make `_load_live` fail closed after the bounded
  retry count.
- AC-05: Existing monitoring risk-view tests and all cumulative R3 gates pass without touching
  any trade-execution behaviour.

## Invariants

- INV-01: No order, sizing, risk-limit, runner, strategy, or research decision changes.
- INV-02: Every money, balance, and reconstructed R calculation changed here uses `Decimal`, never
  binary floating-point.
- INV-03: The complete ledger includes every deal, including open-position entry costs and
  balance/credit events.
- INV-04: The current balance and accepted ledger describe the same stable broker observation.
- INV-05: No test or command reaches a real MT5 terminal or account.

## Assumptions

- MT5 deal tickets provide a strict sequence among deals that share the one-second timestamp.
- `history_deals_get` returns a deterministic ticket-ordered history for an unchanged account.

## Open questions

- Whether the deployed prop-firm account currently emits non-zero values in MT5's `fee` field is
  an operator observation; correctness does not depend on it and synthetic fixtures cover the leg.

## Expected artifacts

- Corrected bridge export and monitoring reconstruction, focused red-first tests, updated focused
  mutation policy/baseline, architecture wording if needed, and this five-file task artifact.

## Risk class

R3 — `scripts/quality/classify.py` classifies `live/mt5_bridge.py` as the broker/money path, and
the change also alters monetary reconstruction shown beside a real-money account.

## Human decisions required

- Jan retains all live-money and merge decisions and must approve any deployment or merge.
- Claude performs the independent doubly-rigorous review; this R3 pull request never merges
  autonomously.
