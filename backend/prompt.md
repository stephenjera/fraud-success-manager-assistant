# Build Task: Fraud Success Manager (FSM) Assistant — Production System

## Role

You are a senior engineer on an AI Centre of Excellence team. Your task is to design and build a **production-grade, GenAI-powered application** that assists a Fraud Success Manager (FSM) in their core workflow of analysing transaction data, discovering fraud patterns, and translating those patterns into deployable fraud rules.

This is not a prototype or a timed exercise — treat it as a real system that will be handed to engineering and risk teams to run in production. Prioritise correctness, safety, maintainability, and clear documentation over speed of delivery.

## Background: The FSM Role and Workflow

A Fraud Success Manager protects merchants and their customers by analysing large volumes of transaction data to identify emerging fraud patterns. Their core workflow is:

1. **Explore** transaction data to form hypotheses about potential fraud signals.
2. **Validate** those hypotheses against historical data to find statistically meaningful, anomalous patterns.
3. **Translate** validated patterns into fraud rules that can be deployed into production systems to block fraudulent payments.

This is an iterative, knowledge-intensive process requiring both data analysis skill and domain expertise. Your job is to design a system that meaningfully accelerates this workflow without introducing new risks (e.g., false confidence in hallucinated patterns, unsafe or unauthorised database access, rules that overfit to noise).

## Provided Assets

- A SQLite database (`data.db`) containing transaction data.
- A schema definition file (`schema.sql`) describing table structures, columns, and relationships. Core tables:
  - `cards` — credit and debit card details
  - `fraud_labels` — binary fraud classification labels for transactions
  - `mcc_codes` — Merchant Category Codes and descriptions
  - `transactions` — transaction records
  - `users` — customer information

If these assets are not present in the working environment, generate a realistic synthetic dataset and schema that matches this structure, clearly documenting any assumptions made about cardinality, distributions, and fraud base rates.

## Core Design Questions to Answer

1. How does the application empower an FSM to explore data and uncover suspicious patterns using natural language?
2. How does the system help an FSM move from a general **insight** (a pattern observed in data) to a concrete, deployable **rule**?
   - A "rule" is defined as a valid SQL `WHERE` clause that can be used to filter the `transactions` table.
   - Example: `amount > 1000 AND card_id IN (SELECT id FROM cards WHERE card_type = 'debit')`

## Required Core Capability (MVP, must be solid before anything else)

A system that **reliably translates an FSM's natural language questions into accurate, safe SQL queries** for data exploration against the schema above. This is the foundation everything else builds on — it must be:

- Accurate against the actual schema (correct joins, column names, types).
- Safe: read-only, scoped to permitted tables/columns, protected against injection and destructive statements, with sensible query limits/timeouts.
- Transparent: the FSM should be able to see and, where sensible, edit the generated SQL before it runs.
- Resilient to ambiguous or underspecified questions — the system should ask for clarification or state its assumptions rather than silently guessing.

## Beyond the MVP (build as time/scope allows, otherwise design and document)

- **Insight-to-rule workflow**: helping the FSM formalise an observed pattern into a candidate `WHERE` clause rule, including estimating the rule's impact (e.g., precision/recall against `fraud_labels`, transaction volume affected, false-positive rate on legitimate transactions).
- **Rule validation tooling**: backtesting a candidate rule against historical data, surfacing edge cases, and flagging overly broad or overly narrow rules.
- **Session/history management**: allowing an FSM to iterate across a multi-turn investigation, building on prior queries and findings.
- **Explainability**: every generated query and every proposed rule should be traceable back to the natural language reasoning that produced it.

## Explicit Requirements

### 1. Architecture and Design Rationale

Document why you chose your specific architecture and interaction model (e.g., agent framework, RAG over schema, tool-calling vs. fine-tuning, single LLM call vs. multi-step pipeline) and how it addresses the FSM's actual workflow rather than a generic "chat with your database" pattern.

### 2. GenAI Risk Mitigation

Demonstrate practical understanding of LLM risks and concrete mitigations, including at minimum:

- **Hallucination** of columns, tables, relationships, or numeric results.
- **SQL injection / unsafe query execution** and how the system enforces read-only, scoped access.
- **Overfitting / spurious patterns** — rules that fit historical noise rather than real fraud signal.
- **Silent failure modes** — the system producing a plausible-looking but wrong query or rule with no indication of uncertainty.
- Include guardrails such as query validation layers, schema-grounding, confidence signalling, human-in-the-loop confirmation before any rule is treated as "ready," and logging/audit trails.

### 3. Evaluation Framework

Design (and implement an initial version of) an evaluation suite that could convince a non-technical stakeholder (e.g., Head of Fraud) that the tool is effective and safe. Address both:

- **Offline metrics**: e.g., NL→SQL exact-match/execution-accuracy against a labelled test set of question/query pairs, rule precision/recall/F1 against `fraud_labels`, query validity rate, latency.
- **Online metrics**: e.g., FSM adoption/usage rate, query edit rate (proxy for trust/accuracy), time-to-rule, rule deployment rate, post-deployment rule performance drift, false-positive complaint rate.
- Include a small but real test set of natural language questions with expected SQL/results, and a script that runs and scores it.

### 4. Interface

Any interface is acceptable — terminal, API, or a minimal frontend — but it should closely resemble how an FSM would actually use the tool day-to-day (e.g., ability to see generated SQL, ability to see/edit before execution, ability to save an insight as a candidate rule). Prioritise the underlying system quality and evaluation over polish of the UI.

## Deliverables

1. A working codebase in a Git repository, structured for production use (clear module boundaries, tests, config management, no hardcoded secrets).
2. A comprehensive `README.md` including:
   - Setup and installation instructions (reproducible via a stated tool choice — uv, poetry, pip, Docker, etc.).
   - A detailed explanation of the solution architecture and the reasoning behind key design choices.
   - A description of known limitations, unimplemented scope, and suggested next steps.
   - An explanation of the evaluation approach and how to run the evaluation suite.
3. Automated tests covering the NL→SQL pipeline, query safety guardrails, and the evaluation suite itself.
4. A short design note on how this system would be productionised further: monitoring, access control, rate limiting, and how rule outputs would be reviewed before deployment into a real fraud-rules engine.

## Success Criteria

4444

- **Problem decomposition & product sense**: the solution reflects real understanding of the FSM's workflow, not a generic text-to-SQL demo.
- **Justification of approach**: architecture and design choices are clearly reasoned, not just described.
- **Risk awareness**: concrete, implemented mitigations for LLM failure modes, not just a bullet list of caveats.
- **Technical execution**: the system is reproducible, well-tested, and cleanly engineered.
- **Evaluation mindset**: the evaluation suite is credible enough to justify a production rollout decision to a non-technical stakeholder.

Proceed by first proposing an architecture and evaluation plan, then implementing iteratively, validating the NL→SQL core before layering on the insight-to-rule workflow.
