import { useState, useEffect, useCallback } from "react";
import { ChatStream } from "./components/ChatStream";
import { DataGrid } from "./components/DataGrid";
import { RuleStudio } from "./components/RuleStudio";
import { ApprovalBanner } from "./components/ApprovalBanner";
import type {
  Message,
  DataGridResponse,
  RuleMetrics,
  ExploreResponse,
  ExploreRequest,
  ExecuteRequest,
  RuleEvaluationRequest,
  RuleEvaluationResponse,
  SessionItem,
  SessionHistoryResponse,
} from "./types/api";

type TabId = "grid" | "rule_lab";

const API_BASE = "http://localhost:8000/api";

const generateSessionId = () =>
  `sess_${Math.random().toString(36).substring(2, 11)}`;

export default function App() {
  const [sessionId, setSessionId] = useState<string>(generateSessionId);
  const [activeTab, setActiveTab] = useState<TabId>("grid");

  const [sessions, setSessions] = useState<SessionItem[]>([]);

  const fetchSessions = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/sessions`);
      const data = await res.json();
      setSessions(data.sessions || []);
    } catch {
      // Non-critical — session list will just be empty
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const loadSession = async (targetId: string) => {
    try {
      const res = await fetch(`${API_BASE}/sessions/${targetId}/history`);
      if (!res.ok) return;
      const data: SessionHistoryResponse = await res.json();
      setSessionId(targetId);

      const restored: Message[] = data.history.map((item, i) => ({
        id: `loaded_${i}_${Math.random().toString(36).substring(2, 6)}`,
        sender: item.role === "user" ? "user" : "agent",
        text: item.content,
        timestamp: new Date().toLocaleTimeString(),
      }));

      setMessages(
        restored.length
          ? restored
          : [
              {
                id: "init",
                sender: "agent",
                text: "System online. Describe the fraud patterns or anomalies you want to investigate.",
                timestamp: new Date().toLocaleTimeString(),
              },
            ],
      );
      setPendingApproval(false);
      setPendingSql("");
      setPendingPredicate("");
    } catch {
      console.error("Failed to load session:", targetId);
    }
  };

  const [messages, setMessages] = useState<Message[]>([
    {
      id: "init",
      sender: "agent",
      text: "System online. Describe the fraud patterns or anomalies you want to investigate.",
      timestamp: new Date().toLocaleTimeString(),
    },
  ]);

  // B-4: Synchronized code states — generated artifacts sit here pending approval
  const [sqlQuery, setSqlQuery] = useState<string>(
    "SELECT * FROM transactions LIMIT 100;",
  );
  const [predicateQuery, setPredicateQuery] = useState<string>("");

  // B-4: Pending flag — true when LLM has generated SQL awaiting user approval
  const [pendingApproval, setPendingApproval] = useState<boolean>(false);
  const [pendingSql, setPendingSql] = useState<string>("");
  const [pendingPredicate, setPendingPredicate] = useState<string>("");

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

      // A-6: Handle clarification — if LLM needs clarification, show the question
      if (data.needs_clarification) {
        const agentMsg: Message = {
          id: Math.random().toString(),
          sender: "agent",
          text: data.clarification_request || data.rationale,
          confidence: data.confidence_score,
          timestamp: new Date().toLocaleTimeString(),
        };
        setMessages((prev) => [...prev, agentMsg]);
        // Do NOT seed panels or execute — waiting for user clarification
        return;
      }

      // B-4: Auto-seed panels with generated artifacts as PENDING
      setSqlQuery(data.sql);
      setPendingSql(data.sql);
      setPendingPredicate(data.rule_predicate || "");
      setPendingApproval(true);

      if (data.rule_predicate) {
        setPredicateQuery(data.rule_predicate);
        setActiveTab("rule_lab");
      } else {
        setActiveTab("grid");
      }

      const agentMsg: Message = {
        id: Math.random().toString(),
        sender: "agent",
        text: data.rationale,
        payload: data,
        confidence: data.confidence_score,
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages((prev) => [...prev, agentMsg]);

      // Refresh session list after successful explore
      fetchSessions();
    } catch (err) {
      console.error("Failed to parse agent exploration stream:", err);
    } finally {
      setChatLoading(false);
    }
  };

  const handleNewSession = () => {
    const newId = generateSessionId();
    setSessionId(newId);
    setMessages([
      {
        id: "init",
        sender: "agent",
        text: "System online. Describe the fraud patterns or anomalies you want to investigate.",
        timestamp: new Date().toLocaleTimeString(),
      },
    ]);
    setPendingApproval(false);
    setPendingSql("");
    setPendingPredicate("");
    setSqlQuery("SELECT * FROM transactions LIMIT 100;");
    setPredicateQuery("");
    setGridData(null);
    setRuleMetrics(null);
    fetchSessions();
  };

  const handleSelectSession = async (targetId: string) => {
    if (targetId === sessionId) return;
    await loadSession(targetId);
    fetchSessions();
  };

  // B-4: User explicitly approves pending SQL — executes + evaluates
  const handleApproveAndRun = () => {
    if (pendingSql) {
      executeGridQuery(pendingSql);
    }
    if (pendingPredicate) {
      evaluateRuleMetrics(pendingPredicate);
      setPredicateQuery(pendingPredicate);
    }
    setPendingApproval(false);
  };

  // B-4: User discards pending — keeps current state, clears pending
  const handleDiscardPending = () => {
    setPendingSql("");
    setPendingPredicate("");
    setPendingApproval(false);
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
    <main className="flex h-screen w-screen overflow-hidden bg-base font-sans-app text-text antialiased">
      {/* Left Chat Window */}
      <div className="flex h-full w-[35%] max-w-[480px] min-w-[340px] flex-col">
        <ChatStream
          sessionId={sessionId}
          messages={messages}
          isLoading={chatLoading}
          onSendPrompt={handleSendPrompt}
          sessions={sessions}
          onSelectSession={handleSelectSession}
          onNewSession={handleNewSession}
        />
      </div>

      {/* Right Product Workspace */}
      <div className="flex h-full flex-1 flex-col">
        {/* B-4: Approval Banner */}
        {pendingApproval && (
          <ApprovalBanner
            onApprove={handleApproveAndRun}
            onDiscard={handleDiscardPending}
          />
        )}

        {/* Workspace Navigation Bar */}
        <div className="flex h-14 items-center justify-between border-b border-border bg-surface px-6">
          <div className="flex space-x-2">
            <button
              onClick={() => setActiveTab("grid")}
              className={`rounded-lg px-4 py-1.5 text-sm font-medium transition ${
                activeTab === "grid"
                  ? "border border-border-highlight bg-surface-2 text-text shadow-sm"
                  : "text-text-muted hover:text-text"
              }`}
            >
              Query Results
            </button>
            <button
              onClick={() => setActiveTab("rule_lab")}
              className={`rounded-lg px-4 py-1.5 text-sm font-medium transition ${
                activeTab === "rule_lab"
                  ? "border border-border-highlight bg-surface-2 text-text shadow-sm"
                  : "text-text-muted hover:text-text"
              }`}
            >
              Rule Testing
            </button>
          </div>
          <span className="rounded border border-border bg-base px-2 py-1 font-mono-app text-[10px] tracking-widest text-text-dim uppercase">
            {activeTab === "grid"
              ? "Data Explorer"
              : "Rule Analytics"}
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
              isPending={pendingApproval}
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
