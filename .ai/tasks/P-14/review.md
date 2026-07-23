# Adversarial review

## Findings

| ID | Severity | Finding | Disposition | Status |
|---|---|---|---|---|
| R-01 | P1 | One account read bracketed by histories could miss balance churn after the second history read. | Read account twice and require both balance and full ordered deal identity to be stable. | resolved |
| R-02 | P2 | A partially populated legacy fee column could become pandas NaN and poison a trade's Decimal net PnL. | Normalise every money leg before constructing the DataFrame. | resolved |
| R-03 | P2 | The first fee regression fixture mixed commission with fee and did not prove a fee-only movement. | Make the first event fee-only and assert ledger, equity, and trade PnL exactly. | resolved |

## Dispositions

Twelve counterexamples were attempted: earlier/later same-second tickets, own opening commission,
own opening fee, a fee-only event, a still-open entry cost, missing legacy fee keys, mixed legacy
and complete rows, changed newest ticket, changed money content under the same ticket, unchanged
ticket with changed balance, perpetual snapshot churn, and empty history. The three issues above
were corrected in scope. No order, sizing, risk-control, account-guard, runner-cycle, strategy, or
research path changed.
