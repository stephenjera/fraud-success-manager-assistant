// The API contract's DTOs, mirrored from backend/app/api + core (the frozen wire).
// ADR-0011: JSON everywhere, error is one shape, lists are envelopes.

export interface Envelope<T> {
  items: T[]
  page: number
  page_size: number
  token: string | null
}

export interface ApiErrorShape {
  code: string
  message: string
  details?: unknown | null
}

// ---- meta
export interface VersionInfo {
  version: string
  git_sha: string
  built_at: string
}

// ---- conversations / runs
export interface Conversation {
  conversation_id: string
  created_at: string
  last_active: string
  message_count: number
}
export interface ConversationDetail extends Conversation {
  messages: MessageSummary[]
}
export interface MessageSummary {
  message_id: string
  run_id: string
  status: MessageStatus
  created_at: string
  grounded: boolean
}

export type RunStatus = "running" | "success" | "error" | "timeout"
export interface Run {
  run_id: string
  conversation_id: string
  message_id: string
  status: RunStatus
  created_at: string
}

// ---- message (Gap A union: success | error | timeout)
export interface Grounding {
  sql: string
  explanation: string
  assumptions: string[]
  tables_and_joins_used?: string[]
  flags?: string[]
}

export type MessageStatus = "running" | "success" | "error" | "timeout"
export interface MessageDto {
  message_id: string
  run_id: string
  status: MessageStatus
  created_at: string
  grounding: Grounding | null
  error: ApiErrorShape | null
  revisions: string[]
}

export interface Revision {
  revision_id: string
  created_at: string
  sql_preview: string
  source: "agent" | "rerun"
}

// ---- rerun (Gap H, sync)
export interface QueryResult {
  columns: string[]
  rows: unknown[][]
  row_cap: number
  truncated: boolean
}
export interface RerunResponse {
  message_id: string
  revision_id: string
  result: QueryResult
  flags: string[]
}

// ---- insights
export interface Insight {
  insight_id: string
  message_id: string
  revision_id: string
  sql: string
  created_at: string
  rule_count: number
}
export interface InsightDetail extends Insight {
  explanation: string | null
  message_status: MessageStatus
  run_id: string
  revisions: string[]
}
export interface DraftRuleOut {
  rule_id: string
  source_insight_id: string
  title: string
  where_clause: string
  draft_where: string
  rationale: string
  assumptions: string[]
  status: RuleStatus
  created_at: string
}

// ---- rules
export type RuleStatus = "draft" | "backtested" | "approved" | "deployed" | "rejected"

export interface RuleCard {
  rule_id: string
  source_insight_id: string
  title: string
  status: RuleStatus
  created_by: string
  disabled_at: string | null
  created_at: string
  backtests: number
  deployments: number
}

export interface RuleDetail {
  rule_id: string
  source_insight_id: string
  title: string
  where_clause: string
  status: RuleStatus
  created_by: string
  approved_by: string | null
  approved_at: string | null
  rationale: string | null
  disabled_at: string | null
  created_at: string
  provenance: {
    source_insight_id: string
    message_id: string
    revision_id: string
    sql: string
  } | null
  latest_backtest: {
    backtest_id: string
    where_clause: string
    window: string
    created_at: string
  } | null
  deployment: {
    deployment_id: string
    backtest_id: string
    external_rule_id: string
    deployed_at: string
  } | null
}

export interface BacktestSummary {
  backtest_id: string
  where_clause: string
  window: string
  created_at: string
  labeled_only_precision: number | null
  labeled_only_lift: number | null
}

// ---- BacktestResult (Gap C, ADR-0014 two-universe)
export interface UniverseMetrics {
  precision: number
  recall: number
  false_positive_rate: number
  baseline_fraud_rate: number
  lift: number
}
export interface UniverseCoverage {
  matched_count: number
  total_rows: number
  total_fraud: number
  support: number
}
export interface UniverseBlock {
  universe: string
  confusion_matrix: { tp: number; fp: number; fn: number; tn: number }
  metrics: UniverseMetrics
  coverage: UniverseCoverage
}
export interface TemporalSlice {
  precision: number
  recall: number
}
export interface SampleBlock {
  count: number
  columns: string[]
  rows: unknown[][]
}
export interface BacktestResult {
  rule_id: string
  window: string
  where_clause: string
  backtest_id?: string
  created_at?: string
  labeled_only: UniverseBlock
  full_universe: UniverseBlock
  temporal_stability: { earlier_slice: TemporalSlice; later_slice: TemporalSlice }
  sample: SampleBlock
}

// ---- lifecycle verbs
export interface ApproveOut {
  rule_id: string
  status: RuleStatus
  approved_by: string
  approved_at: string
  rationale: string
}
export interface RejectOut {
  rule_id: string
  status: RuleStatus
  rationale: string
  actor: string
}
export interface DeployOut {
  deployment_id: string
  rule_id: string
  backtest_id: string
  external_rule_id: string
  status: RuleStatus
  deployed_at: string
}

// ---- chat view model (not a DTO — the UI's render shape)
export interface ActivityItem {
  tool: string
  phase: "start" | "done"
  summary?: string
}
export interface Turn {
  key: string
  role: "user" | "assistant"
  text: string
  message_id?: string
  run_id?: string
  status?: MessageStatus
  grounding?: Grounding | null
  error?: ApiErrorShape | null
  activities?: ActivityItem[]
}

// A grounded answer selected into the workspace (the live query). It is the
// message's grounding plus its identity, so the workspace can rerun/pin it.
export interface SelectedQuery {
  message_id: string
  status: MessageStatus
  sql: string
  explanation: string | null
  assumptions: string[]
  flags: string[]
  error: ApiErrorShape | null
}
