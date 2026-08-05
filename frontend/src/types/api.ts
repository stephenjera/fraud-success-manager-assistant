// =========================================================
// EXPLORATION LAYER TYPES
// =========================================================

export interface ExploreRequest {
  session_id: string;
  prompt: string;
  current_rule_state: string | null;
  execution_context: Record<string, any> | null;
}

export interface ExploreResponse {
  session_id: string;
  rationale: string;
  sql: string;
  rule_predicate: string | null;
  is_exploratory_only: boolean;
  confidence_score: number;
  needs_clarification: boolean;
  clarification_request: string | null;
}

export interface RuleMetrics {
  true_positives: number;
  false_positives: number;
  false_negatives: number;
  true_negatives: number;
  precision: number;
  recall: number;
  false_positive_rate: number;
  fraud_value_caught: number;
  legit_value_blocked: number;
  net_value: number;
  p_value: number;
  statistically_significant: boolean;
  odds_ratio: number;
}

// =========================================================
// RULE EVALUATION TYPES
// =========================================================

export interface RuleEvaluationRequest {
  where_clause: string;
}

export interface RuleEvaluationResponse {
  metrics: RuleMetrics;
}

// =========================================================
// RAW EXECUTION LAYER TYPES
// =========================================================

export interface ExecuteRequest {
  session_id: string | null;
  sql: string;
}

export interface DataGridResponse {
  columns: string[];
  rows: any[][]; // Positional array layout matching backend optimization
  execution_time_ms: number;
}

// =========================================================
// SESSION MANAGEMENT TYPES
// =========================================================

export interface SessionItem {
  id: string;
  created_at: string;
  updated_at: string;
}

export interface SessionListResponse {
  sessions: SessionItem[];
}

export interface SessionHistoryItem {
  role: string;
  content: string;
}

export interface SessionHistoryResponse {
  session_id: string;
  history: SessionHistoryItem[];
}

// =========================================================
// APPLICATION COMPONENT STATE INTERFACES
// =========================================================

export interface Message {
  id: string;
  sender: 'user' | 'agent';
  text: string;
  payload?: ExploreResponse;
  confidence?: number;
  timestamp: string;
}