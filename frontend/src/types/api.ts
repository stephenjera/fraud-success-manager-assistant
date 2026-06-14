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
}

// =========================================================
// RULE EVALUATION TYPES
// =========================================================

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
}

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
// APPLICATION COMPONENT STATE INTERFACES
// =========================================================

export interface Message {
  id: string;
  sender: 'user' | 'agent';
  text: string;
  payload?: ExploreResponse;
  timestamp: string;
}