# ADR-0003 — Native LangGraph StateGraph over create_agent

**Status:** accepted (frozen in the 2026-09-02 P0 freeze)
**Date:** 2026-09-02

## Context

The repo currently builds the agent with
`langchain.agents.create_agent` (`backend/app/agents.py:20`) while `langgraph`
is a declared dependency — the two frameworks are muddled and neither owns
the loop clearly. Spec §5 names LangGraph for "the tool-calling loop,
streaming, and checkpointing."

## Decision

Build the agent as an **explicit LangGraph `StateGraph`**: a declared state,
a model node, tool node(s), and an explicit structured-output terminal node.
We own every node and edge rather than relying on a packaged agent.

## Alternatives considered

- **Keep `langchain.agents.create_agent`.** Rejected: the loop is hidden
  inside the factory; our two load-bearing requirements — an explicit
  structured-output node (ADR-0006) and fine-grained SSE events for the
  workspace (spec §6.5) — both call for the loop to be visible and
  addressable.

## Consequences

- The tool-calling loop, checkpointing, and streaming events are explicit,
  unit-testable graph nodes instead of an opaque invoke.
- One trajectory to debug (consistent with ADR-0004 — no multi-agent tree).
- We take on the responsibility of wiring/checkpointing that the factory
  previously gave us for free; that's the trade we're making deliberately.
