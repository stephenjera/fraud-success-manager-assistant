# Phases 00 — Roadmap

**Status:** P0–P2 done (2026-09-03), P2.5 done (2026-09-03), P3 next.

Phases (order per the ADRs; P0–P2 done, P2.5 done, P3/P4 pending):

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
  the acceptance, not the description.
- **P4 — Hardening & docs.** `make lint/test/eval` wired; README
  reconciled to the real state; ADRs all accepted, none proposed.

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
