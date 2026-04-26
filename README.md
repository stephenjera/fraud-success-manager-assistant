# Fraud Success Manager Assistant

## What is a Fraud Success Manager?

A Fraud Success Manager (FSM) analyses transaction data to identify fraud patterns and deploy rules to block fraudulent payments.

Their core workflow involves:

- **Exploring data** to form hypotheses about potential fraud signals.
- **Validating these hypotheses** against historical data to find anomalous patterns.
- **Translating these patterns** into **fraud rules** that can be deployed into our production systems to block fraudulent payments.

## Design Decisions

### User Interface

| Decision | Rationale |
|--------|----------|
| **Web-based UI** | Closely reflects how internal tools are used and allows interactive exploration |
| **Vanilla HTML/CSS/JS** | Keeps implementation lightweight and focused on functionality |
| **FastAPI backend** | Simple API layer that separates logic from UI and supports future scalability |

### Data Exploration (NL to SQL)

| Decision | Rationale |
|--------|----------|
| **LLM for SQL generation** | Enables FSMs to query data without writing SQL |
| **Schema-aware prompting** | Reduces hallucination and ensures valid queries |
| **Single-step queries only** | Keeps scope manageable and improves reliability |

### Hypothesis Validation

| Decision | Rationale |
|--------|----------|
| **Deterministic analytics layer** | Ensures metrics (fraud rate, counts) are accurate and reproducible |
| **SQLite execution** | Fast, simple, and sufficient for MVP-scale analysis |
| **Baseline comparison** | Provides context for evaluating whether a pattern is meaningful |

### Translating Patterns to Fraud Rules

| Decision | Rationale |
|--------|----------|
| **Rules defined as SQL WHERE clauses** | Directly executable and easy to evaluate |
| **LLM-assisted rule generation** | Converts insights into candidate rules quickly |
| **Rule validation layer** | Prevents invalid or hallucinated rules from being used |

### Rule Evaluation

| Decision | Rationale |
|--------|----------|
| **Precision / Recall / Block Rate** | Core metrics for assessing fraud rule quality |
| **Evaluation before acceptance** | Prevents unsafe or overly broad rules |
| **Warning system** | Flags low precision or high customer impact |

### LLM Strategy

| Decision | Rationale |
|--------|----------|
| **LLM as a helper, not source of truth** | Reduces risk of incorrect outputs |
| **Strict output constraints (JSON)** | Improves reliability and parsing |
| **Failure handling (retries + validation)** | Ensures system robustness |

### Model Choice

| Decision | Rationale |
|--------|----------|
| **Ollama (local LLM)** | Enables free, offline development and reproducibility |
| **Swappable LLM interface** | Allows future upgrade to stronger models |

### Software Architecture

| Decision | Rationale |
|--------|----------|
| **Pipeline-based design** | Clear flow from question → insight → rule → evaluation |
| **Modular components** | Separates LLM, analytics, validation, and execution |
| **Abstracted LLM interface** | Decouples system from specific model provider |
| **Logging** | Provides traceability and debugging across pipeline |

### Scope & Trade-offs

| Decision | Rationale |
|--------|----------|
| **Focus on NL to SQL MVP** | Core requirement of the task |
| **Stopped prompt tuning early** | Avoided diminishing returns with weaker local model |
| **Prioritised evaluation over generation quality** | Ensures system usefulness even with imperfect outputs |
| **Limited deployment features** | Focused on core functionality rather than production readiness |

## Running the Project

### Setup

```bash
uv sync
```

Now actiavate the virtual environment:

```bash
source .venv/bin/activate
```

### Start the server

change to app directory

```bash
cd app
```

then run:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Example query

Once loaded, you can access the UI at `http://localhost:8000` and try asking questions like:

Which transaction type has the most fraud?

This will trigger the LLM to generate a SQL query, execute it against the SQLite database, and return the results in the UI. You can then explore the insights and try generating fraud rules based on the patterns you find!
