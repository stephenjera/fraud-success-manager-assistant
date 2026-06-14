import { useState } from "react";
import { ChatStream } from "./components/ChatStream";
import { DataGrid } from "./components/DataGrid";
import { RuleStudio } from "./components/RuleStudio";
import type {
  Message,
  DataGridResponse,
  RuleMetrics,
  ExploreResponse,
  ExploreRequest,
  ExecuteRequest,
  RuleEvaluationRequest,
  RuleEvaluationResponse,
} from "./types/api";

type TabId = "grid" | "rule_lab";

const API_BASE = "http://localhost:8000/api";

export default function App() {
  const [sessionId] = useState<string>(
    () => `sess_${Math.random().toString(36).substring(2, 11)}`,
  );
  const [activeTab, setActiveTab] = useState<TabId>("grid");

  // Conversational state
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "init",
      sender: "agent",
      text: "System online. Describe the fraud patterns or anomalies you want to investigate.",
      timestamp: new Date().toLocaleTimeString(),
    },
  ]);

  // Synchronized code states
  const [sqlQuery, setSqlQuery] = useState<string>(
    "SELECT * FROM transactions LIMIT 100;",
  );
  const [predicateQuery, setPredicateQuery] = useState<string>("");

  // Data caches
  const [gridData, setGridData] = useState<DataGridResponse | null>(null);
  const [ruleMetrics, setRuleMetrics] = useState<RuleMetrics | null>(null);

  // Status indicators
  const [chatLoading, setChatLoading] = useState(false);
  const [gridLoading, setGridLoading] = useState(false);
  const [ruleLoading, setRuleLoading] = useState(false);

  const handleSendPrompt = async (promptText: string) => {
    setChatLoading(true);
    const userMsg: Message = {
      id: Math.random().toString(),
      sender: "user",
      text: promptText,
      timestamp: new Date().toLocaleTimeString(),
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const payload: ExploreRequest = {
        session_id: sessionId,
        prompt: promptText,
        current_rule_state: predicateQuery || null,
        execution_context: null,
      };

      const res = await fetch(`${API_BASE}/explore`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data: ExploreResponse = await res.json();

      // AUTO-INGESTION: Immediately seed the editing panels with the generated artifacts
      setSqlQuery(data.sql);
      if (data.rule_predicate) {
        setPredicateQuery(data.rule_predicate);
        setActiveTab("rule_lab"); // Auto-focus the rule lab if a predicate dropped
      } else {
        setActiveTab("grid"); // Auto-focus data grid for exploratory queries
      }

      const agentMsg: Message = {
        id: Math.random().toString(),
        sender: "agent",
        text: data.rationale,
        payload: data,
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages((prev) => [...prev, agentMsg]);

      // Fire off the background queries automatically to bring data alive
      if (data.rule_predicate) {
        evaluateRuleMetrics(data.rule_predicate);
      }
      executeGridQuery(data.sql);
    } catch (err) {
      console.error("Failed to parse agent exploration stream:", err);
    } finally {
      setChatLoading(false);
    }
  };

  const executeGridQuery = async (queryToRun: string) => {
    setGridLoading(true);
    try {
      const payload: ExecuteRequest = {
        session_id: sessionId,
        sql: queryToRun,
      };
      const res = await fetch(`${API_BASE}/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data: DataGridResponse = await res.json();
      setGridData(data);
    } catch (err) {
      console.error("Data grid query execution failed:", err);
    } finally {
      setGridLoading(false);
    }
  };

  const evaluateRuleMetrics = async (targetPredicate: string) => {
    setRuleLoading(true);
    try {
      const payload: RuleEvaluationRequest = { where_clause: targetPredicate };
      const res = await fetch(`${API_BASE}/rules/evaluate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data: RuleEvaluationResponse = await res.json();
      setRuleMetrics(data.metrics);
    } catch (err) {
      console.error("Rule evaluation engine failed:", err);
    } finally {
      setRuleLoading(false);
    }
  };

  return (
    <main className="flex h-screen w-screen overflow-hidden bg-slate-950 font-sans text-slate-100 antialiased">
      {/* Left Chat Window */}
      <div className="flex h-full w-[35%] max-w-[480px] min-w-[340px] flex-col">
        <ChatStream
          sessionId={sessionId}
          messages={messages}
          isLoading={chatLoading}
          onSendPrompt={handleSendPrompt}
        />
      </div>

      {/* Right Product Workspace */}
      <div className="flex h-full flex-1 flex-col">
        {/* Workspace Navigation Bar */}
        <div className="flex h-14 items-center justify-between border-b border-slate-800 bg-slate-900 px-6">
          <div className="flex space-x-2">
            <button
              onClick={() => setActiveTab("grid")}
              className={`rounded-lg px-4 py-1.5 font-mono text-xs font-medium transition ${
                activeTab === "grid"
                  ? "border border-slate-700 bg-slate-800 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              DuckDB Explorer Grid
            </button>
            <button
              onClick={() => setActiveTab("rule_lab")}
              className={`rounded-lg px-4 py-1.5 font-mono text-xs font-medium transition ${
                activeTab === "rule_lab"
                  ? "border border-slate-700 bg-slate-800 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Rule Optimization Lab
            </button>
          </div>
          <span className="rounded border border-slate-800 bg-slate-950 px-2 py-1 font-mono text-[10px] tracking-widest text-slate-500 uppercase">
            {activeTab === "grid"
              ? "Relational Data View"
              : "Rule Analytics Studio"}
          </span>
        </div>

        {/* Workspace Active Render Target */}
        <div className="flex-1 overflow-hidden">
          {activeTab === "grid" && (
            <DataGrid
              data={gridData}
              isLoading={gridLoading}
              sqlValue={sqlQuery}
              onSqlChange={setSqlQuery}
              onExecuteRawSQL={() => executeGridQuery(sqlQuery)}
            />
          )}

          {activeTab === "rule_lab" && (
            <RuleStudio
              predicate={predicateQuery}
              metrics={ruleMetrics}
              isLoading={ruleLoading}
              onPredicateChange={setPredicateQuery}
              onEvaluate={() => evaluateRuleMetrics(predicateQuery)}
            />
          )}
        </div>
      </div>
    </main>
  );
}
