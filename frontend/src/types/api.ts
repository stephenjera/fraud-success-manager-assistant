export type Insight = {
  summary: string;
  risk_level: "low" | "medium" | "high" | "unknown";
  key_findings: string[];
};

export type FraudRule = {
  rule_sql_where: string;
  description: string;
  confidence: number;
};

export type QueryResponse = {
  sql: string | null;
  explanation: string | null;
  confidence: number | null;
  results: Record<string, unknown>[] | null;
  error: string | null;
  insight: Insight | null;
  rule: FraudRule | null;
};

export type InvestigationStep = {
  step_type: string;
  input: string | Record<string, unknown>;
  output: Record<string, unknown>;
};

export type InvestigationSession = {
  session_id: string;
  initial_question: string;
  steps: InvestigationStep[];
  current_sql?: string | null;
  current_results?: Record<string, unknown>[] | null;
  current_insight?: string | null;
  current_rule?: string | null;
  confidence?: number;
  done?: boolean;
};
