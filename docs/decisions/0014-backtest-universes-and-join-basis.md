# ADR-0014 — Backtest universes, join scope, and the join basis for `where_clause`

**Status:** accepted (2026-09-03, after P2 implementation)
**Date:** 2026-09-03

## Context

The P2 backtest (`core/backtest.py`) needs two things pinned before code starts,
because they are not derivable from spec or data:

**Label coverage.** `fraud_labels` covers only 67 % of `transactions`
(777,339 labeled out of 1,159,966). A matched transaction with no label cannot
be scored as fraud or not-fraud. Spec §8 lists the metrics without naming the
eval universe. A single universe silently chosen will either understate
precision (unlabeled counted as legit) or hide the coverage gap
(labeled-only).

**Rule scope.** Spec §1 says a rule is "a SQL `WHERE` clause over `transactions`."
Read literally, a rule cannot reference `cards.has_chip`, `merchants.mcc`, or
`users.per_capita_income` — yet those are the attributes most fraud rules
depend on. The spec never states whether a join basis is in scope for P2.

**Temporal stability.** Spec §8 calls for "earlier vs later slice" precision
and recall but does not define the split point.

## Decision

**Two evaluation universes, both reported, both labelled in the DTO.**

Every backtest computes and stores two full result blocks:

| Universe key | Universe | Rationale |
|---|---|---|
| `labeled_only` | 777,339 label-bearing txns (775,979 legit + 1,360 fraud). A matched txn with no label → excluded from both precision and recall. | The "clean" universe: the denominators use only rows with a known ground truth. |
| `full_universe` | All 1,159,966 txns; unlabeled = not-fraud. | The "operational" universe: how the rule would behave in the wild where every transaction is scored. |

Each block carries its own `confusion_matrix` and derived `metrics`
(precision, recall, false_positive_rate, baseline_fraud_rate, lift) and its
own `coverage` (`total_rows`, `total_fraud`, `support`, `matched_count`).
`temporal_stability` is computed per-universe the same way.

The **sample** (5 matched rows) is shared — it is the same set of `transaction_id`s
regardless of universe (the `WHERE` matches the same rows either way).

**Rationale for both:** a single universe makes the numbers look better than
they are (or worse than they are) depending on which one was picked. Reporting
both lets the FSM — and eventually a human approver — see the gap and decide
whether the rule is strong enough in the universe that actually matters.

---

**`where_clause` is join-capable.**

The effective FROM basis for the backtest is:

```sql
FROM transactions t
LEFT JOIN fraud_labels fl ON fl.transaction_id = t.id
LEFT JOIN cards        c  ON c.id  = t.card_id
LEFT JOIN merchants    m  ON m.id  = t.merchant_id
```

`WHERE <clause>` is evaluated against this basis. `transactions.*` columns are
unqualified. `cards.*` and `merchants.*` are also addressable. `fraud_labels`
is only used for the label join and should not appear in the `WHERE` clause
(it is the ground truth, not a filter).

`users` and `merchant_locations` are reachable through `cards.user_id` and
`merchants.merchant_id` if the FSM needs them; they are not part of the
default basis but are addressable in the clause.

**Rationale:** a fraud rule that cannot reference `has_chip`, `card_brand`,
`mcc`, or `card_on_dark_web` is a much weaker rule than one that can.
The P1 agent (which explores over all reference tables) will propose patterns
that reference these columns; if the rule engine can't express them, the FSM
is forced to abandon useful patterns it can see in the data.

---

**Temporal stability split.** Median `transactions.date` within the eval
universe. Compute precision/recall separately on the earlier half and the
later half. No date boundary is passed in; the split is derived from the data.

## Consequences

- **`BacktestResult` DTO shape changes** relative to the frozen Gap C in
  `api-contract.md`. The `metrics`, `confusion_matrix`, `coverage`, and
  `temporal_stability` blocks are now nested under `labeled_only` and
  `full_universe` keys. `sample` and `window` remain top-level. The contract
  is updated in the P2 PR; this ADR is the record of why.
- **`data-model.md` `backtest_results` JSONB columns** store the same shape
  (`metrics`, `confusion_matrix`, `coverage`, `temporal_stability` each
  become per-universe objects, or a flat pair is stored and the API layers
  split it — decision at implementation time).
- **`core/backtest.py`** must run two SQL passes (one per universe) or one
  pass with a `CASE WHEN` that captures both label conditions. The LLM still
  has no path into the result.
- **`draft-rule` (the LLM-generated `WHERE`)** is now allowed to reference
  `cards`/`merchants` columns. The `sql_validator` allow-list may need to be
  extended (or scoped to this specific FROM basis) so that a `WHERE` clause
  referencing `c.has_chip` is not rejected as an unknown column.
- **`e2e-walktalk.md` Phases 4-7** (the backtest assertion) will assert on
  both universes.
