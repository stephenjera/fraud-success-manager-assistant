# Evaluation design

**Status:** accepted (frozen with the 2026-09-02 P0 freeze, same pass as the other architecture docs).

Spec §10 gave us the *shape* — "split deliberately by shape of the thing being evaluated, not by tool." This doc answers the two questions the stub left open: **where the proof lives in the repo** and **how the E2E pattern-recovery test gets its synthetic ground truth**, plus a scoping rule neither doc had: **which tests run in which phase.**

## The split, confirmed

| what is being proven | tool | why this one |
|---|---|---|
| SQL validator rejects bad SQL | pytest | pure function, no LLM, assertable in one line |
| `core/flags` produces the right flags | pytest | pure function, no LLM |
| Backtest math (precision/recall/FPR/lift/support) | pytest | arithmetic against a known confusion matrix |
| Rule state machine illegal transitions | pytest | state machine in `core/rule_state.py`, no LLM |
| `core/rule_engine` mock payload assembly | pytest | pure function, fake ID, deterministic |
| **E2E pattern recovery** (pipeline as a whole) | pytest | sequential/stateful, multiple phases, small-n — promptfoo's model doesn't fit (it's one input→output, this is a workflow) |
| NL→SQL execution accuracy | promptfoo | real LLM, real agent, real seeded DB — result-set comparison (not string match) |
| Explanation faithfulness | promptfoo | needs LLM-as-judge with a distinct model from the agent (spec §10.1) |
| Safety / refusal rate | promptfoo | adversarial fixtures + the redteam plugin set (injection/jailbreak), not hand-rolled |

The one row that is deliberately in **pytest** because it is the *pipeline*, not a component: **E2E pattern recovery.** Inject a known synthetic fraud pattern, run an FSM-style prompt, pin the insight, draft the rule, backtest it, assert precision/recall clears a threshold. This is the test that says "the whole thing works together" and it is sequential/stateful, which is exactly why it lives in a test framework that can do multi-step, not a promptfoo case.

## Repo locations

| path | content |
|---|---|
| `backend/eval/golden/` | the golden fixtures — JSON/YAML. `nl2sql/*.json` (question + reference SQL pairs), `adversarial/*.json` (safety/redteam set), `patterns/*.yaml` (the synthetic pattern definition for E2E pattern recovery: which rows to inject into `reference` and what the expected precision/recall threshold is) |
| `backend/eval/promptfoo/` | promptfoo config: `nl2sql.yaml`, `faithfulness.yaml`, `safety.yaml`. The provider is a custom thin HTTP provider pointed at the FastAPI endpoint (see "The provider" below) |
| `backend/tests/` | pytest suite. `test_sql_validator.py`, `test_flags.py`, `test_backtest_math.py`, `test_rule_state.py`, `test_rule_engine.py`, `test_e2e_pattern_recovery.py` (this is the sequential one that has a `conftest.py` fixture that injects the synthetic pattern) |
| `backend/scripts/e2e_walktalk.py` | the headless E2E *shape* walkthrough (P1 DoD #5). Drives the full API and asserts response shapes — a *different* thing from `test_e2e_pattern_recovery.py`; the walkthrough is a contract test, the pattern-recovery is a correctness test |

This is not two E2E suites. The walkthrough (`e2e_walktalk.py`) proves "every endpoint returns the frozen shape." The pattern-recovery test (`test_e2e_pattern_recovery.py`) proves "the pipeline actually works together and the backtest math is correct for a known ground truth." They use the same reference data and the same seeded DB but they assert different things and they fail for different reasons.

## E2E pattern recovery: how the synthetic pattern gets in

This was the stub's open question. Answer, locked:

**The synthetic pattern is N extra rows in `reference.fraud_labels` (and optionally N rows in `reference.transactions`) injected by a superuser connection during the test fixture setup, and deleted during teardown.** This is exactly the pattern `scripts/seed_reference.py` already uses (ADR-0008: the seed "runs as a separate superuser, not as `reference_readonly`"). The test does not need a fourth role, a second schema, or a second database.

Concretely:

1. **Test setup** (conftest or the test's `setup`): open a superuser connection, `INSERT` the N synthetic `transactions` rows (and their corresponding `fraud_labels` rows if the pattern is "fraud by card_type + mcc_code") into `reference`. The `patterns/*.yaml` files in `backend/eval/golden/` define these rows.
2. **Run the FSM workflow** — the agent's `run_sql` tool connects as `reference_readonly` (its normal runtime role) and sees the synthetic rows because they're now in `reference`. It is the same table the production reference reader sees; the only difference is that N extra rows exist during the test.
3. **Assert** — the rule that results (drafted from the insight, back-tested) clears the precision/recall threshold defined in the pattern YAML.
4. **Test teardown**: `DELETE FROM reference.fraud_labels WHERE ...` (the synthetic rows) + `DELETE FROM reference.transactions WHERE ...` — same superuser connection. `reference` is back to its seeded baseline (or the seed script resets it on the next run).

The word "copy" in spec §10.2 was doing work in the SQLite-file world: "a copy of the seed data" = "a second SQLite file with the baseline + the synthetic pattern." In Postgres, the equivalent is "the baseline seed + N test-only rows that are cleaned up in teardown." The production reference is never permanently modified — it is only *temporarily extended* during the test. That is the "copy," expressed in Postgres terms.

## The provider (promptfoo)

The spec is explicit: "the provider under test is the **real chat endpoint** … not a mocked shortcut, since a mock would evaluate a stand-in for the system rather than the system itself." The provider block in the promptfoo YAML is therefore a *thin HTTP provider* — it calls `POST /v1/conversations/{id}/messages` (or the equivalent v1 endpoint for the P1 build), waits for the answer from `GET /v1/conversations/{id}/messages/{mid}`, and returns that as the promptfoo "provider response." No mock, no stand-in, no second implementation of the agent.

The judge model (for faithfulness) is **configured separately** from the agent model via promptfoo's judge config. The two model IDs are distinct — that is the spec §10.1 requirement and it is a config, not a code path. The agent model is the one `app/common/model.py` returns; the judge model is a promptfoo `judge:` block in the config file. If both happen to be the same Ollama model (because it's a local dev environment with one model), the faithfulness assertion is *weaker* but still present — the "distinct model" rule is a *production* requirement (where the two models are different providers), not an enforcement test.

## Phase-gated: which tests run when

The eval suite is built in phase order so that P1's `make eval` does not test a function that doesn't exist yet:

| phase | tests active in `make eval` |
|---|---|
| **P1** | `test_sql_validator.py`, `test_flags.py`, all three promptfoo suites (`nl2sql.yaml`, `faithfulness.yaml`, `safety.yaml`), `e2e_walktalk.py` (shape only). Faithfulness is a P1 suite because its input — the `grounding.explanation` field — is a P1 deliverable (P1 DoD #1: "the grounding payload is a typed object the API emits"; `data-model.md` puts `messages.grounding` in the P1 table set; `agent-loop.md` treats `structured_output` as the P1 terminal node). The backtest-math, state-machine, and pattern-recovery tests do **not** run yet — `core/backtest.py` and `core/rule_state.py` are not implemented. |
| **P2** | Adds: `test_backtest_math.py`, `test_rule_state.py`, `test_rule_engine.py`, `test_e2e_pattern_recovery.py`. No new promptfoo suites — all three already ran in P1 against the same agent; P2 adds deterministic tests for the deterministic P2 code. |
| **P3** | No new eval tests. The catalog/frontend is not an eval surface — it consumes the API, it does not change the agent's output. |

Pragmatically: `make eval` runs whatever is present in `backend/tests/` and `backend/eval/`. The phase-gating is not a feature flag — it is "the file exists when the code it tests exists." P1 developers don't write `pytest.mark.skipif` for P2 functions; they simply don't write those tests yet.

`make lint` / `make test` / `make eval` are the entry points (spec §14: "no separate CI in v1"). There is no CI runner, no GitHub Actions, no `.github/` — the suite is run by hand or from the phase DoD checklist. CI is explicitly out of scope (ADR-0012: "no CI/CD in v1 until it has a customer").

## Online eval (spec §10.4) — documented, not built

The online metrics (efficiency, adoption/trust, quality drift, safety "this was wrong" flag, cost/latency) are **documented but not built** in v1. Two notes:

- **Quality drift** is the most important one and the one to watch. It requires *new* labels arriving after deployment (spec §10.4: "compare actual post-deployment precision/recall once new labels arrive against the backtest estimate"). In this system, "deployed" means "the mock `rule_engine` recorded the payload"; there is no real downstream rule engine producing *new* labels. Quality drift evaluation is therefore aspirational until a real rule engine exists — the shape is documented, the data is not there.
- **Cost/latency p50/p95** is *available in the Langfuse trace* (spec §10.4: "directly available from Langfuse traces when Langfuse is running"). This is a query against Langfuse, not a code change. The shape is documented; the tool to run the query is Langfuse's own UI.

This is the "future of this doc, not the present" line — the *content* of §10.4 is correct and stable, but the *build* is a phase that hasn't happened.

## What this doc is *not* deciding

- **The specific golden fixtures** (the questions, the reference SQL, the adversarial cases, the synthetic pattern definitions). Those are in `backend/eval/golden/` and they are authored when the P1/P2 implementation lands — the doc decides *where* and *what shape*, the content is the data, not the architecture.
- **The promptfoo plugin versions**. Spec says "the redteam plugin set … used directly rather than hand-rolled." The specific promptfoo version and plugin names are a `pyproject.toml` / `package.json` decision, not an architecture decision.
- **The judge model selection.** Spec §10.1 says "config distinct from the agent model" — that's the rule. *Which* model is a runtime/config decision (it will be whatever Ollama or the cloud provider makes available in the dev environment).

## Dependencies

- ADR-0002 (the SQL validator under test; the `validate_sql` function is the subject of `test_sql_validator.py`).
- ADR-0005 (the `core/` functions being tested are the gate functions; the `agents → core` wall means these tests *don't* need the LLM).
- ADR-0006 (the ground-truth for the faithfulness eval is the `grounding` object; the `explanation` + `assumptions` fields are what the judge reads).
- ADR-0007 (the `reference_readonly` role is what the agent uses at *runtime*; the test setup uses a superuser, matching the seed script pattern, to inject the synthetic pattern — the two roles are not in tension, the test is not the agent).
- ADR-0008 (the seed script and the E2E pattern-injection setup share the same "superuser, idempotent, clean up after" discipline).
- spec §10 (the shape of the split confirmed by this doc; the fixture content it does not decide).
- `rule-lifecycle.md` (the `core/rule_state.py` function the state-machine test exercises; the freeze line those tests assert).
- `data-model.md` (the `reference` tables the synthetic pattern injects into; the `backtest_results` table the pattern-recovery test reads its metrics from).
- `api-contract.md` (the E2E shape walkthrough in `e2e_walktalk.py` is the test of the frozen contract's response shapes — the contract is what the shape test holds the server to).
- `e2e-walktalk.md` (the numbered steps the `e2e_walktalk.py` script asserts; a different test from `test_e2e_pattern_recovery.py`).
