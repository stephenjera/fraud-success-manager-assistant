// The shared rules client — the rule lifecycle is this feature's domain
// (spec §7 state machine). The insights rail reuses this for draft/
// backtest/approve/reject rather than duplicating the one-liner calls
// (ADR-0009: one folder per work area owns its calls; a rules client is
// singular, so it lives here and is imported, not re-written).
import { api } from "@/lib/http"
import type {
  ApproveOut,
  BacktestResult,
  BacktestSummary,
  DeployOut,
  DraftRuleOut,
  Envelope,
  RejectOut,
  RuleCard,
  RuleDetail,
} from "@/lib/types"

const ACTOR = "fsm" // spec §2 single-user placeholder identity

export const rulesApi = {
  list: (status?: string) =>
    api
      .get<Envelope<RuleCard>>(
        `/rules${status ? `?status=${encodeURIComponent(status)}` : ""}`,
      )
      .then((e) => e.items),

  get: (ruleId: string) => api.get<RuleDetail>(`/rules/${ruleId}`),

  // Edit-and-own the clause. The freeze line (a backtest row already exists)
  // is enforced by the backend with 409 RULE_ILLEGAL_TRANSITION; the UI also
  // refuses to send it once `latest_backtest` is set.
  patchWhereClause: (ruleId: string, where_clause: string) =>
    api.patch<RuleDetail>(`/rules/${ruleId}`, { where_clause }),

  // The command — deterministic, never the LLM (spec §7.4). Returns the report.
  backtest: (ruleId: string, window?: "full" | "custom") =>
    api.post<BacktestResult>(`/rules/${ruleId}/backtest`, window ? { window } : null),

  backtests: (ruleId: string) =>
    api.get<Envelope<BacktestSummary>>(`/rules/${ruleId}/backtests`).then((e) => e.items),

  getBacktest: (ruleId: string, backtestId: string) =>
    api.get<BacktestResult>(`/rules/${ruleId}/backtests/${backtestId}`),

  approve: (ruleId: string, rationale: string) =>
    api.post<ApproveOut>(`/rules/${ruleId}/approve`, { rationale, actor: ACTOR }),

  reject: (ruleId: string, rationale: string) =>
    api.post<RejectOut>(`/rules/${ruleId}/reject`, { rationale, actor: ACTOR }),

  deploy: (ruleId: string) => api.post<DeployOut>(`/rules/${ruleId}/deploy`, null),

  deployStatus: (ruleId: string) =>
    api.get<{ rule_id: string; deployment: unknown | null; status: string }>(
      `/rules/${ruleId}/deployment`,
    ),

  // Bridge the insight → draft rule (spec principle 5: a rule only comes
  // from a pinned insight).
  draftRule: (insightId: string, title?: string) =>
    api.post<DraftRuleOut>(`/insights/${insightId}/draft-rule`, title ? { title } : null),
}
