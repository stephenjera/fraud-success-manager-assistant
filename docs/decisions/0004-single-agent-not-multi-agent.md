# ADR-0004 — One agent + deterministic core, not a multi-agent supervisor

**Status:** accepted (frozen in the 2026-09-02 P0 freeze)
**Date:** 2026-09-02

## Context

The workflow has three cognitive-sounding stages — explore, spot patterns,
draft rules — which invites reflexively splitting them into three specialist
agents behind a supervisor. This is the biggest deviation from a "default"
agentic design, so it is recorded as a decision rather than an assumption.
(Promoted from spec §4.)

## Decision

A **single tool-using agent** handles all NL reasoning. All three stages
share the same tools (`run_sql`, `profile_column`) and the same kind of
reasoning — "find an anomaly" is an aggregate query, not a different task.
Everything safety-critical (SQL validation, result flags, backtesting,
state transitions, deployment packaging) is **deterministic application
code in `core/`**, never an LLM coordination concern.

## Alternatives considered

- **Multi-agent supervisor + specialists.** Rejected: all three subtasks use
  the same schema and the same tools, so a supervisor buys no distinct
  context/expertise. The one safety property it could offer — "backtest
  always happens before a rule shows as validated" — is *better* enforced
  by application code that requires a backtest row to exist before a rule
  reaches `backtested`, than by a routing decision an LLM makes. Multi-agent
  adds latency, per-turn model cost, and a tree of traces for no benefit
  here.

## Consequences

- One trajectory to reason about; one set of tools; one checkpoint store.
- The "guarantee lives in code, not in a prompt" property (ADR-0005 wall +
  ADR-0006 structured output) is what this decision actually delivers;
  without it, there is a path where the model persuades a supervisor to skip
  a step.
- Revisit only if the workflow genuinely splits into subtasks needing
  different schemas, models, or context — a concrete trigger, not a mood.
