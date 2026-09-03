# System boundary

**Status:** accepted (frozen in the 2026-09-02 P0 freeze, same pass as the
other architecture docs).

Where does *this system* end and the world begin? The answer drives
everything downstream (which things are services, which are configs,
which are mocks) and was the one question the ADRs never directly
settled. It's settled here with one rule applied to each candidate:

> **Inside:** code that runs in this process and whose determinism we
> rely on. **Outside:** a separate process we point at over HTTP via
> env config. **Past the v1 line:** explicitly not built, recorded as a
> boundary, not deferred silently.

## Inside

| Thing | Why inside |
|---|---|
| The single FSM user | local, one session, no auth (spec §2); the actor the system is *for*, so the boundary is defined against them |
| The FastAPI app (`routers/` + `services/` + `agents/` + `core/` + `data/`) | the product (ADR-0011); every layer is in-process code we own and test (ADR-0005 wall applies *within* this boundary) |
| The LangGraph agent loop (single agent, `model` ⇄ `tools` → `structured_output`) | the in-process reasoning engine; the graph, the state channels, and the checkpoint writes all live here (ADR-0003/0004) |
| The Postgres cluster **with both roles** | one process, one cluster, but two *views* of it (`reference` read-only floor for the agent, `appstate` writable for the app) — this split *is* the internal boundary (ADR-0007) |
| The mock rule-engine client (`core/rule_engine.py`) | an in-process Python function that assembles the deployment payload (spec §9); not a service, not a container, not a network call — the "client" it mocks is *outside*, what we ship is a typed, deterministic payload assembler inside the app |
| The reference dataset itself (100 MB of cards/transactions/…) | external *origin* (it's a real, fixed dataset), but loaded by a one-shot idempotent seed and thereafter read by `reference_readonly` only — from the system's view it's a fixed input, not an upstream service (ADR-0008) |

## Outside

| Thing | Why outside |
|---|---|
| The real downstream rule engine | never in a repo (spec §9); the mock client (above) is the in-process stand-in for the *integration*, the *engine itself* is a future boundary, not a v1 component |
| **Langfuse** | external; the app reads `LANGFUSE_BASE_URL` + keys from env and no-ops the entire tracing path if they're unset (the backend is fully demoable with Langfuse entirely absent). The boundary call the stub left as TBD, resolved: **it's outside.** Reason: it's a *separate process we point at over HTTP via env config* — not code in this process, not owned here, and the system's correctness does not depend on it being up. The "ours to point at" framing (per the stub) is a fair point, but the test is *does the system's behavior change when it's absent* — and it doesn't (tracing just ceases to be observable), so "outside" is the honest call |
| Any LLM provider (Ollama, OpenAI, Anthropic, …) | a separate process on a URL in `LLM_API_BASE`; the agent loop talks to it over HTTP, the provider is a config not a component (spec §2 scope, §5 stack note) |
| The reference *origin* of the dataset | the cards/transactions come from an external fixed source (not generated here); only the loaded copy is inside — see `deploy.md` for the one-shot seed, and `eval-design.md` for the synthetic-pattern injection (which is a test fixture, reusing the seed's superuser path, not a runtime dependency) |
| The browser (Vite dev server, TanStack Query, shadcn/ui) | a separate process; talks to the API over HTTP (the API is the product — ADR-0011 — and the UI is its *first consumer*, not part of the deterministic core) |

## Past the v1 line (recorded, not silent)

| Thing | Record |
|---|---|
| CI pipeline | ADR-0012 skip row; `make lint/test/eval` are the manually-run equivalent, CI-ready in shape but not running |
| Real deployment target / Terraform | ADR-0008 consequences; no such customer exists |
| Auth / RBAC / multi-tenant | spec §2 scope; `created_by`/`approved_by` placeholders exist so the data model doesn't need a rewrite |
| Real rule-engine integration | spec §9 / spec §15; the payload *contract* is the v1 deliverable, the engine is not |
| Column-level sensitive-data masking | spec §2 scope; the reference dataset is public, masking only matters once real PII enters scope |
| Post-deployment drift monitoring | spec §15; the backtest-vs-actuals comparison in the eval suite covers the *pre*-deployment case |
| Feedback-loop learning from FSM actions | spec §15; the eval suite's golden datasets are the v1 analogue |

## Depends on

- ADR-0005 (the `core`/`agents`/`services` wall is an *intra*-
  boundary concern; this doc only says the whole app is inside)
- ADR-0007 (the one-cluster/two-roles split; the *internal* line is
  where the two roles meet)
- ADR-0008 (the seed script is the one-shot bridge from "outside
  origin" to "inside fixed input")
- ADR-0012 (the "past the v1 line" column is its record, not this doc's)
- ADR-0011 (the API is the product, which is what makes the UI an
  outside consumer and not a co-boundary)

## Out of scope (see other docs)

- The internal *layers* (`routers`/`services`/`agents`/`core`) →
  [components.md](components.md).
- The agent loop specifically → [agent-loop.md](agent-loop.md).
- The two roles and the reference/appstate schemas →
  [data-model.md](data-model.md).
- What actually boots and in what order → [deploy.md](deploy.md).
