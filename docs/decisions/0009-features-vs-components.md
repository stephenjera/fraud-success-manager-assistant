# ADR-0009 — `features/` for app slices, `components/` for primitives

**Status:** accepted (frozen in the 2026-09-02 P0 freeze)
**Date:** 2026-09-02

## Context

The frontend has four work areas — **chat**, **workspace** (live SQL /
results / edit-and-own), **insights** (rail + push-expand metrics panel),
and **catalog** (cross-conversation rules, filterable). A "just put things
in `components/`" structure was the lazy default I proposed before you
pushed back.

## Decision

Two frontend directories:

- **`frontend/src/components/ui/`** — dumb reusable primitives: Button,
  Badge, Card, the shared results table, the stat-card, etc. No app logic,
  no API calls. Reused wherever.
- **`frontend/src/features/{chat,workspace,insights,catalog}/`** — one
  folder per work area, holding that area's API client + hooks + its own
  components + local state.

The rule: if it *does things* (fires a request, holds transient state
beyond props, owns interaction state) → `features/`. If it just renders and
forwards events → `components/`.

## Alternatives considered

- **Everything under `components/{chat,workspace,insights,catalog}/`.**
  Rejected: it's the same shape, but the word `components` signals "dumb,
  reusable." Areas that carry their own SSE streams, edit-and-own state,
  and feature-scoped TanStack Query keys are *not* dumb, and folding them
  into `components/` turns the folder into a junk drawer by Phase 3.

## Consequences

- `frontend/src/features/chat/` owns the SSE consumer, the streaming
  indicator state, and the composer state — not spread across a
  `components/chat/` tree and a separate `hooks/useChat` and an
  `api/conversations.ts`.
- `components/ui/` stays stable across phases; the areas above it can
  reshape freely without breaking each other.
- The two directories are a rule of thumb for where a new file lands, not
  an enforcement boundary (it's a frontend, no test enforces it — and it
  shouldn't; the rule exists to keep the first pass tidy, Phase 3 not to be
  blocked by structure).
