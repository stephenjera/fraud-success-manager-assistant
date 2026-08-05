"""D-1: Hand-written NL→SQL test dataset.

20 pairs: ~10 simple, ~5 moderate, ~5 edge cases.
Grounded in actual schema: users, cards, transactions, fraud_labels, merchants, mcc_codes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class NLSQLPair:
    question: str
    expected_sql: str
    expected_columns: list[str] | None
    min_row_count: int
    max_row_count: int
    category: str
    requires_rule: bool = False
    expected_rule_contains: str | None = None


# ──────────────────────────────────────────────
# Simple aggregation queries (~10)
# ──────────────────────────────────────────────

SIMPLE: list[NLSQLPair] = [
    # 1: Transaction count by type
    NLSQLPair(
        question="How many transactions are there for each transaction type?",
        expected_sql=(
            "SELECT t.transaction_type, COUNT(*) AS cnt "
            "FROM transactions t GROUP BY t.transaction_type"
        ),
        expected_columns=["transaction_type", "cnt"],
        min_row_count=3,
        max_row_count=3,
        category="simple",
    ),
    # 2: Average transaction amount
    NLSQLPair(
        question="What is the average transaction amount across all transactions?",
        expected_sql=(
            "SELECT ROUND(AVG(t.amount_usd_cents) / 100.0, 2) AS avg_amount_usd "
            "FROM transactions t"
        ),
        expected_columns=["avg_amount_usd"],
        min_row_count=1,
        max_row_count=1,
        category="simple",
    ),
    # 3: Top merchant by transaction count
    NLSQLPair(
        question="Which merchant has the most transactions?",
        expected_sql=(
            "SELECT m.name, COUNT(*) AS cnt "
            "FROM transactions t JOIN merchants m ON t.merchant_id = m.id "
            "GROUP BY m.name ORDER BY cnt DESC LIMIT 1"
        ),
        expected_columns=["name", "cnt"],
        min_row_count=1,
        max_row_count=1,
        category="simple",
    ),
    # 4: Fraud count and rate by transaction type
    NLSQLPair(
        question="What is the fraud rate for each transaction type?",
        expected_sql=(
            "SELECT t.transaction_type, "
            "COUNT(*) AS total_tx, "
            "SUM(CASE WHEN fl.is_fraud THEN 1 ELSE 0 END) AS fraud_count, "
            "ROUND(100.0 * SUM(CASE WHEN fl.is_fraud THEN 1 ELSE 0 END) / COUNT(*), 2) AS fraud_rate_pct "
            "FROM transactions t "
            "LEFT JOIN fraud_labels fl ON CAST(t.id AS TEXT) = fl.transaction_id "
            "GROUP BY t.transaction_type"
        ),
        expected_columns=["transaction_type", "total_tx", "fraud_count", "fraud_rate_pct"],
        min_row_count=3,
        max_row_count=3,
        category="simple",
    ),
    # 5: Fraud count by card type
    NLSQLPair(
        question="Which card types have the highest fraud rate?",
        expected_sql=(
            "SELECT c.card_type, "
            "COUNT(*) AS total_tx, "
            "ROUND(100.0 * SUM(CASE WHEN fl.is_fraud THEN 1 ELSE 0 END) / COUNT(*), 2) AS fraud_rate_pct "
            "FROM transactions t "
            "JOIN cards c ON t.card_id = c.id "
            "LEFT JOIN fraud_labels fl ON CAST(t.id AS TEXT) = fl.transaction_id "
            "GROUP BY c.card_type"
        ),
        expected_columns=["card_type", "total_tx", "fraud_rate_pct"],
        min_row_count=3,
        max_row_count=3,
        category="simple",
    ),
    # 6: Count of flagged transactions
    NLSQLPair(
        question="How many transactions have been flagged as fraud?",
        expected_sql=(
            "SELECT COUNT(*) AS fraud_count "
            "FROM fraud_labels WHERE is_fraud = TRUE"
        ),
        expected_columns=["fraud_count"],
        min_row_count=1,
        max_row_count=1,
        category="simple",
    ),
    # 7: Top amounts over a threshold
    NLSQLPair(
        question="Show me the 5 largest transactions by amount.",
        expected_sql=(
            "SELECT t.id, t.amount_usd_cents / 100.0 AS amount_usd "
            "FROM transactions t ORDER BY t.amount_usd_cents DESC LIMIT 5"
        ),
        expected_columns=["id", "amount_usd"],
        min_row_count=5,
        max_row_count=5,
        category="simple",
    ),
    # 8: Transaction volume by merchant category
    NLSQLPair(
        question="What is the transaction count for each merchant category?",
        expected_sql=(
            "SELECT mc.description AS mcc_description, COUNT(*) AS cnt "
            "FROM transactions t "
            "JOIN merchants m ON t.merchant_id = m.id "
            "JOIN mcc_codes mc ON m.mcc = mc.mcc "
            "GROUP BY mc.description"
        ),
        expected_columns=["mcc_description", "cnt"],
        min_row_count=5,
        max_row_count=20,
        category="simple",
    ),
    # 9: Cards on dark web count
    NLSQLPair(
        question="How many card holders have had their card exposed on the dark web?",
        expected_sql=(
            "SELECT COUNT(*) AS dark_web_cards "
            "FROM cards WHERE card_on_dark_web = TRUE"
        ),
        expected_columns=["dark_web_cards"],
        min_row_count=1,
        max_row_count=1,
        category="simple",
    ),
    # 10: Average transaction amount by user income bracket
    NLSQLPair(
        question="What is the average transaction amount for each gender?",
        expected_sql=(
            "SELECT u.gender, ROUND(AVG(t.amount_usd_cents) / 100.0, 2) AS avg_amount_usd "
            "FROM transactions t "
            "JOIN cards c ON t.card_id = c.id "
            "JOIN users u ON c.user_id = u.id "
            "GROUP BY u.gender"
        ),
        expected_columns=["gender", "avg_amount_usd"],
        min_row_count=2,
        max_row_count=2,
        category="simple",
    ),
]

# ──────────────────────────────────────────────
# Moderate queries (~5) — multi-join, subqueries
# ──────────────────────────────────────────────

MODERATE: list[NLSQLPair] = [
    # 11: Online transactions flagged as fraud by merchant category
    NLSQLPair(
        question="What merchant categories have the highest fraud rate for online transactions?",
        expected_sql=(
            "SELECT mc.description AS mcc_description, "
            "COUNT(*) AS total_tx, "
            "ROUND(100.0 * SUM(CASE WHEN fl.is_fraud THEN 1 ELSE 0 END) / COUNT(*), 2) AS fraud_rate_pct "
            "FROM transactions t "
            "JOIN merchants m ON t.merchant_id = m.id "
            "JOIN mcc_codes mc ON m.mcc = mc.mcc "
            "LEFT JOIN fraud_labels fl ON CAST(t.id AS TEXT) = fl.transaction_id "
            "WHERE t.transaction_type = 'Online Transaction' "
            "GROUP BY mc.description "
            "ORDER BY fraud_rate_pct DESC"
        ),
        expected_columns=["mcc_description", "total_tx", "fraud_rate_pct"],
        min_row_count=5,
        max_row_count=50,
        category="moderate",
        requires_rule=True,
        expected_rule_contains="t.transaction_type = 'Online Transaction'",
    ),
    # 12: High-amount transactions with fraud label
    NLSQLPair(
        question="Show me all fraud-flagged transactions over $500.",
        expected_sql=(
            "SELECT t.id, t.amount_usd_cents / 100.0 AS amount_usd, t.date "
            "FROM transactions t "
            "JOIN fraud_labels fl ON CAST(t.id AS TEXT) = fl.transaction_id "
            "WHERE t.amount_usd_cents > 50000 AND fl.is_fraud = TRUE"
        ),
        expected_columns=["id", "amount_usd", "date"],
        min_row_count=1,
        max_row_count=500,
        category="moderate",
        requires_rule=True,
        expected_rule_contains="t.amount_usd_cents > 50000 AND fl.is_fraud = TRUE",
    ),
    # 13: Cards on dark web + fraud correlation
    NLSQLPair(
        question="What is the fraud rate for cards found on the dark web versus those not on the dark web?",
        expected_sql=(
            "SELECT c.card_on_dark_web, "
            "COUNT(*) AS total_tx, "
            "ROUND(100.0 * SUM(CASE WHEN fl.is_fraud THEN 1 ELSE 0 END) / COUNT(*), 2) AS fraud_rate_pct "
            "FROM transactions t "
            "JOIN cards c ON t.card_id = c.id "
            "LEFT JOIN fraud_labels fl ON CAST(t.id AS TEXT) = fl.transaction_id "
            "GROUP BY c.card_on_dark_web"
        ),
        expected_columns=["card_on_dark_web", "total_tx", "fraud_rate_pct"],
        min_row_count=2,
        max_row_count=2,
        category="moderate",
        requires_rule=True,
        expected_rule_contains="c.card_on_dark_web = TRUE",
    ),
    # 14: Users with low credit score and fraud
    NLSQLPair(
        question="What percentage of transactions from users with credit score below 500 are fraudulent?",
        expected_sql=(
            "SELECT COUNT(*) AS total_tx, "
            "SUM(CASE WHEN fl.is_fraud THEN 1 ELSE 0 END) AS fraud_count, "
            "ROUND(100.0 * SUM(CASE WHEN fl.is_fraud THEN 1 ELSE 0 END) / COUNT(*), 2) AS fraud_rate_pct "
            "FROM transactions t "
            "JOIN cards c ON t.card_id = c.id "
            "JOIN users u ON c.user_id = u.id "
            "LEFT JOIN fraud_labels fl ON CAST(t.id AS TEXT) = fl.transaction_id "
            "WHERE u.credit_score < 500"
        ),
        expected_columns=["total_tx", "fraud_count", "fraud_rate_pct"],
        min_row_count=1,
        max_row_count=1,
        category="moderate",
        requires_rule=True,
        expected_rule_contains="u.credit_score < 500",
    ),
    # 15: Prepaid card high-value patterns
    NLSQLPair(
        question="What is the fraud rate for prepaid debit card transactions over $100?",
        expected_sql=(
            "SELECT COUNT(*) AS total_tx, "
            "SUM(CASE WHEN fl.is_fraud THEN 1 ELSE 0 END) AS fraud_count, "
            "ROUND(100.0 * SUM(CASE WHEN fl.is_fraud THEN 1 ELSE 0 END) / COUNT(*), 2) AS fraud_rate_pct "
            "FROM transactions t "
            "JOIN cards c ON t.card_id = c.id "
            "LEFT JOIN fraud_labels fl ON CAST(t.id AS TEXT) = fl.transaction_id "
            "WHERE c.card_type = 'Debit (Prepaid)' AND t.amount_usd_cents > 10000"
        ),
        expected_columns=["total_tx", "fraud_count", "fraud_rate_pct"],
        min_row_count=1,
        max_row_count=1,
        category="moderate",
        requires_rule=True,
        expected_rule_contains="card_type = 'Debit (Prepaid)'",
    ),
]

# ──────────────────────────────────────────────
# Edge case queries (~5) — ambiguous, complex
# ──────────────────────────────────────────────

EDGE_CASES: list[NLSQLPair] = [
    # 16: Ambiguous "cause" — expects fraud rate by transaction type (closest mapping)
    NLSQLPair(
        question="What are the main causes of fraud in our system?",
        expected_sql=(
            "SELECT t.transaction_type, "
            "SUM(CASE WHEN fl.is_fraud THEN 1 ELSE 0 END) AS fraud_count, "
            "ROUND(100.0 * SUM(CASE WHEN fl.is_fraud THEN 1 ELSE 0 END) / COUNT(*), 2) AS fraud_rate_pct "
            "FROM transactions t "
            "LEFT JOIN fraud_labels fl ON CAST(t.id AS TEXT) = fl.transaction_id "
            "GROUP BY t.transaction_type "
            "ORDER BY fraud_rate_pct DESC"
        ),
        expected_columns=["transaction_type", "fraud_count", "fraud_rate_pct"],
        min_row_count=1,
        max_row_count=5,
        category="edge",
    ),
    # 17: Multi-condition overlap — dark web + high amount + online
    NLSQLPair(
        question="Show me fraud patterns for high-value online transactions from cards found on the dark web.",
        expected_sql=(
            "SELECT COUNT(*) AS total_tx, "
            "SUM(CASE WHEN fl.is_fraud THEN 1 ELSE 0 END) AS fraud_count, "
            "ROUND(100.0 * SUM(CASE WHEN fl.is_fraud THEN 1 ELSE 0 END) / COUNT(*), 2) AS fraud_rate_pct "
            "FROM transactions t "
            "JOIN cards c ON t.card_id = c.id "
            "LEFT JOIN fraud_labels fl ON CAST(t.id AS TEXT) = fl.transaction_id "
            "WHERE t.transaction_type = 'Online Transaction' "
            "AND c.card_on_dark_web = TRUE "
            "AND t.amount_usd_cents > 10000"
        ),
        expected_columns=["total_tx", "fraud_count", "fraud_rate_pct"],
        min_row_count=1,
        max_row_count=1,
        category="edge",
        requires_rule=True,
        expected_rule_contains="Online Transaction",
    ),
    # 18: Geographic fraud concentration
    NLSQLPair(
        question="Which states have the highest fraud concentration based on merchant locations?",
        expected_sql=(
            "SELECT ml.state, COUNT(*) AS total_tx, "
            "ROUND(100.0 * SUM(CASE WHEN fl.is_fraud THEN 1 ELSE 0 END) / COUNT(*), 2) AS fraud_rate_pct "
            "FROM transactions t "
            "JOIN merchant_locations ml ON t.merchant_location_id = ml.id "
            "LEFT JOIN fraud_labels fl ON CAST(t.id AS TEXT) = fl.transaction_id "
            "GROUP BY ml.state "
            "ORDER BY fraud_rate_pct DESC LIMIT 10"
        ),
        expected_columns=["state", "total_tx", "fraud_rate_pct"],
        min_row_count=5,
        max_row_count=10,
        category="edge",
    ),
    # 19: Subquery — merchants with above-average fraud rate
    NLSQLPair(
        question="Show merchants whose fraud rate is above the overall fraud rate.",
        expected_sql=(
            "SELECT m.name, COUNT(*) AS cnt, "
            "ROUND(100.0 * SUM(CASE WHEN fl.is_fraud THEN 1 ELSE 0 END) / COUNT(*), 2) AS fraud_rate_pct "
            "FROM transactions t "
            "JOIN merchants m ON t.merchant_id = m.id "
            "LEFT JOIN fraud_labels fl ON CAST(t.id AS TEXT) = fl.transaction_id "
            "GROUP BY m.name "
            "HAVING SUM(CASE WHEN fl.is_fraud THEN 1 ELSE 0 END) * 100.0 / COUNT(*) > "
            "(SELECT SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END) * 100.0 / COUNT(*) FROM fraud_labels) "
            "ORDER BY fraud_rate_pct DESC LIMIT 20"
        ),
        expected_columns=["name", "cnt", "fraud_rate_pct"],
        min_row_count=1,
        max_row_count=100,
        category="edge",
    ),
    # 20: Chip vs swipe fraud ratio per brand
    NLSQLPair(
        question="Compare fraud rates between chip and swipe transactions across card brands.",
        expected_sql=(
            "SELECT c.card_brand, t.transaction_type, "
            "COUNT(*) AS cnt, "
            "ROUND(100.0 * SUM(CASE WHEN fl.is_fraud THEN 1 ELSE 0 END) / COUNT(*), 2) AS fraud_rate_pct "
            "FROM transactions t "
            "JOIN cards c ON t.card_id = c.id "
            "LEFT JOIN fraud_labels fl ON CAST(t.id AS TEXT) = fl.transaction_id "
            "WHERE t.transaction_type IN ('Chip Transaction', 'Swipe Transaction') "
            "GROUP BY c.card_brand, t.transaction_type "
            "ORDER BY c.card_brand, fraud_rate_pct DESC"
        ),
        expected_columns=["card_brand", "transaction_type", "cnt", "fraud_rate_pct"],
        min_row_count=4,
        max_row_count=20,
        category="edge",
    ),
]

ALL_PAIRS: list[NLSQLPair] = SIMPLE + MODERATE + EDGE_CASES
