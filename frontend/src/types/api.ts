export interface ChatMessage {
  id: string;
  sender: "user" | "agent";
  text: string;
  rationale?: string;
  explore_sql?: string;
  rule_predicate?: string;
  timestamp: Date;
}

export interface ExploreRequest {
  session_id: string;
  user_prompt: string;
  current_rule_state?: string | null;
}

export interface ExploreResponse {
  session_id: string;
  rationale: string;
  explore_sql: string;
  rule_predicate: string | null;
  is_exploratory_only: boolean;
}

export interface ExecuteRequest {
  session_id?: string;
  sql_query: string;
}

export interface DataGridResponse {
  columns: string[];
  rows: any[][];
  execution_time_ms: number;
}

export interface BacktestRequest {
  where_clause: string;
}

export interface BacktestMetrics {
  true_positives: number;
  false_positives: number;
  false_positive_ratio: number;
  total_fraud_value_saved_usd: number;
}

export interface TimelineDataPoint {
  date: string;
  fraud_blocked: number;
  legitimate_blocked: number;
}

export interface BacktestResponse {
  metrics: BacktestMetrics;
  timeline_series: TimelineDataPoint[];
}
