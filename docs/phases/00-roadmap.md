# Phases 00 — Roadmap

**Status:** P0–P4 + P3.5 done (2026-09-04). P5 done. Prompt supervisor added 2026-09-04.

Phases (order per the ADRs; P0–P4 done, P3.5 done, P5 done):

- **P0 — Reckon & lock.** All ADRs frozen (`proposed` → `accepted`).
  Spec rewrites move to `docs/system-spec.md`. `architecture/*.md` stubs
  become content. The **API contract** is the one doc with to-be-
  *discussed* content (see `../architecture/api-contract.md`) and is the
  only stub expected to change shape after the discussion, not before.
  No diagram is drawn without its ADR existing. No feature code lands.
  **DoD:** `docs/decisions/*` all `accepted`; `docs/system-spec.md`
  rewritten coherently; `architecture/api-contract.md` frozen;
  `docs/diagrams/*.excalidraw` exist for every `architecture/*.md` that
  had a matching question discussed; the "no random diagrams" rule is
  verifiable by opening each file and finding its ADR.
- **P1 — Reliable NL→SQL + its proof.** Structured output (ADR-0006)
  live as a real node; SSE streaming per the frozen contract; `core/`
  gates (ADRs 0002/0005) working; `agents/` uses LangGraph
  (ADR-0003); the **eval suite ships** (eval-design.md content), golden
  Q→SQL fixtures, validator unit tests, one E2E. **Is the challenge
  deliverable.**
- **P2 — Rule lifecycle.** The orphaned `compute_backtest` in `db.py` is
  wired in; insight→draft→backtest→state machine→mock deploy; the
  Postgres roles (ADR-0007) actually enforce read-only.
- **P2.5 — Live-mode proof (add-on to P1–P2, done 2026-09-03).** Not a new
  feature — it proves the LLM- and read-side are genuinely live, not faked:
  `scripts/e2e_walktalk.py --live` (repeatable, real Ollama + real
  `reference`, self-evidencing, hard-fails if the fake is detected) and
  `scripts/agent_repl.py` (interactive, watch the model choose). The live
  run surfaced and fixed a real bug: `profile_column()` mis-labelled nulls.
  See `../architecture/e2e-walktalk.md` (P2 addition) and the P2 addendum.
- **P3 — Frontend.** The features from ADR-0009, built *against* the
  frozen API contract. The wireframes from `../ux/wireframes.md` are
  the acceptance, not the description. Chaos report completed: one real
  bug (mid-stream SSE wedge) found and fixed.
- **P3.5 — Frontend infra gaps.** Docker Compose moved to root with
  `api` and `frontend` containers + Dockerfiles. Playwright STREAM_LOST
  regression test. `sql_validator` pg_catalog policy unit test.
- **P4 — Hardening & docs.** `make lint/test/eval` wired; README
  reconciled; ADRs all accepted (0001–0016); missing P2 test files
  (backtest_math, rule_engine, e2e_pattern_recovery); mypy config;
  Python eval harness (replaces promptfoo concept).
- **P5 — Conversational rule proposals + run-terminal robustness.**
  The agent can propose rules in-chat without SQL
  (`agents/output.py` `RuleProposal`, `Grounding.sql` nullable).
  Recursion exhaustion (`GraphRecursionError`) → `RUN_TIMEOUT` (408);
  model failure → `LLM_ERROR` (502).  Five terminal shapes ship:
  grounded SQL, rule proposal, synthesis-from-prior, "data can't answer",
  and plain chat (non-data questions answered conversationally, no SQL forced).
  Prompt-level supervisor: system prompt (`graph.py:36`) branches — data
  questions follow the `run_sql`/`profile_column`/`final_answer` flow;
  non-data questions go straight to `final_answer` with prose only.
  No second graph, no multi-agent split (ADR-0004 unchanged).
  Pin action lives on insights rail (ADR-0009 boundary).
  DB migration `0003` adds `rule_title`, `rule_where_clause`,
  `rule_rationale`, `rule_assumptions` to `insights`.
  `services/rules.draft_rule` prefers stored clause over derivation.
  Frontend renders proposal cards in chat and highlights proposals on
  the insights rail.  All five terminal types verified.

Each phase ends with a *verifiable DoD*, not a mood. "The code compiles"
is not a DoD. "The `test_architecture.py` wall check passes and
`make eval` reports zero promptfoo assertions failing" is.

Dependencies:

```
P0 ──► P1 ──► P2 ──► P3 ──► P4
```

Strictly sequential; each phase's DoD is a gate on the next. P2.5 is an
*add-on* to P1–P2 (it adds live-mode proof, not new features), so it sits
between P2 and P3 and does not gate P3 on its own. P0 is longest by
design: it's the "we don't surprise the next session" phase. Every phase
after it is shorter *because* P0 did its job.

Out of scope (see other docs): the *content* of P1's agent loop →
`../architecture/agent-loop.md`; the *content* of P2's state machine →
`../architecture/rule-lifecycle.md`.
