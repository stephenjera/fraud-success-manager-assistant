// src/App.tsx
import React, { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { apiService } from "./api/client";
import type {
  ChatMessage,
  DataGridResponse,
  BacktestResponse,
  ExploreResponse,
} from "./types/api";
import {
  MessageSquare,
  Database,
  ShieldAlert,
  Terminal,
  Play,
  Send,
  Sparkles,
  X,
  Filter,
  Sparkle,
} from "lucide-react";
import { DataCanvas } from "./components/DataCanvas";
import { CodeMirrorPanel } from "./components/CodeMirrorPanel";
import { Drawer } from "./components/Drawer";
import { RulePanel } from "./components/RulePanel";

interface RuleCondition {
  id: string;
  field: "transaction_type" | "errors" | "mcc" | "description";
  dbAlias: "t.transaction_type" | "t.errors" | "mc.mcc" | "mc.description";
  operator: "='" | "IS NOT NULL" | "='";
  value: string;
}

// --- Main Core Workspace Layer ---
export default function App() {
  const [sessionId] = useState<string>(
    () => `session-${Math.random().toString(36).substring(2, 11)}`,
  );
  const [prompt, setPrompt] = useState("");
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);

  // Dual-output state management
  const [exploreSqlData, setExploreSqlData] = useState<DataGridResponse | null>(
    null,
  );
  const [ruleSqlData, setRuleSqlData] = useState<DataGridResponse | null>(null);
  const [rulePredicateContent, setRulePredicateContent] = useState("");
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [currentRuleState, setCurrentRuleState] = useState<string | null>(null);

  // Decoupled Workspace State Engines
  const [sqlBuffer, setSqlBuffer] = useState("");
  const [conditions, setConditions] = useState<RuleCondition[]>([]);
  const [backtestData, setBacktestData] = useState<BacktestResponse | null>(
    null,
  );

  // Helper compiler logic
  const compileConditionsToSQL = (
    activeConditions: RuleCondition[],
  ): string => {
    if (activeConditions.length === 0) return "t.errors IS NOT NULL";
    return activeConditions
      .map((c) => {
        if (c.operator === "IS NOT NULL") return `${c.dbAlias} IS NOT NULL`;
        return `${c.dbAlias} ${c.operator}${c.value}'`;
      })
      .join(" AND ");
  };

  const activeRuleString = compileConditionsToSQL(conditions);

  // --- API Mutation Core Rows ---
  const exploreMutation = useMutation({
    mutationFn: apiService.exploreHypothesis,
    onSuccess: (data: ExploreResponse) => {
      const fullQuery = (data.explore_sql || "").trim();
      const rulePredicate = data.rule_predicate || "";
      const isExploratoryOnly = data.is_exploratory_only || false;

      setChatHistory((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          sender: "agent",
          text: `I have compiled the diagnostic view inside the interactive workspace canvas. Inspect the matrices to build out target configurations.`,
          rationale: data.rationale,
          generated_sql: fullQuery,
          timestamp: new Date(),
        },
      ]);

      setSqlBuffer(fullQuery);
      setCurrentRuleState(rulePredicate);
      setRulePredicateContent(rulePredicate || "");

      // Execute the explore query
      if (fullQuery) {
        executeMutation.mutate({ sql_query: fullQuery });
      }

      // Open drawer if we have a rule predicate and it's not exploratory-only
      if (rulePredicate && !isExploratoryOnly) {
        setIsDrawerOpen(true);
      }
    },
    onError: (err: any) => {
      setChatHistory((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          sender: "agent",
          text: `System boundary runtime failure: ${err.message || "Unexpected response block format."}`,
          timestamp: new Date(),
        },
      ]);
    },
  });

  const executeMutation = useMutation({
    mutationFn: apiService.executeSQL,
    onSuccess: (data) => setExploreSqlData(data),
  });

  // NEW: Re-execute rule mutation
  const ruleReexecuteMutation = useMutation({
    mutationFn: apiService.executeSQL,
    onSuccess: (data) => setRuleSqlData(data),
  });

  const backtestMutation = useMutation({
    mutationFn: apiService.runBacktest,
    onSuccess: (data) => setBacktestData(data),
  });

  const removeCondition = (id: string) => {
    setConditions(conditions.filter((c) => c.id !== id));
  };

  // Cell Click: ONLY STAGES the target rule condition tag. Zero tab shifts or network mutations.
  const handleCellClickPivot = (columnName: string, value: any) => {
    if (value === null) return;

    let targetField: "transaction_type" | "errors" | "mcc" | "description" =
      "transaction_type";
    let dbAlias:
      | "t.transaction_type"
      | "t.errors"
      | "mc.mcc"
      | "mc.description" = "t.transaction_type";

    if (columnName === "error" || columnName === "errors") {
      targetField = "errors";
      dbAlias = "t.errors";
    } else if (columnName === "mcc_code" || columnName === "mcc") {
      targetField = "mcc";
      dbAlias = "mc.mcc";
    } else if (columnName === "mcc_description") {
      targetField = "description";
      dbAlias = "mc.description";
    }

    const newCondition: RuleCondition = {
      id: crypto.randomUUID(),
      field: targetField,
      dbAlias,
      operator: "='",
      value: String(value),
    };

    setConditions([...conditions, newCondition]);
  };

  const handleReexecuteRule = (predicateText: string) => {
    ruleReexecuteMutation.mutate({ sql_query: predicateText });
  };

  const triggerSimulationPass = () => {
    backtestMutation.mutate({ where_clause: activeRuleString });
  };

  const handleChatSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || exploreMutation.isPending) return;

    setChatHistory((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        sender: "user",
        text: prompt,
        timestamp: new Date(),
      },
    ]);
    exploreMutation.mutate({
      session_id: sessionId,
      user_prompt: prompt,
      current_rule_state: currentRuleState,
    });
    setPrompt("");
  };

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-slate-950 font-sans text-slate-100 antialiased">
      {/* Structural Header */}
      <header className="flex flex-shrink-0 items-center justify-between border-b border-slate-800 bg-slate-900 px-6 py-4 shadow-md">
        <div className="flex items-center space-x-3">
          <div className="rounded-lg bg-emerald-500 p-1.5 text-slate-950 shadow-sm shadow-emerald-500/20">
            <ShieldAlert className="h-5 w-5 stroke-[2]" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight text-slate-200">
              Fraud Success Manager
            </h1>
            <p className="font-mono text-[10px] tracking-wider text-slate-400 uppercase">
              CoE Core Assistant Node v1.4 - Dual-Canvas
            </p>
          </div>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-1.5 font-mono text-xs text-slate-400">
          Session Token:{" "}
          <span className="font-bold text-emerald-400">{sessionId}</span>
        </div>
      </header>

      {/* Workspace Main Splits */}
      <main className="flex min-h-0 flex-1 overflow-hidden">
        {/* LEFT COLUMN: Conversational Interface */}
        <section className="flex h-full w-1/3 max-w-[500px] min-w-[380px] flex-col border-r border-slate-800/80 bg-slate-900/40 shadow-lg">
          <div className="flex flex-shrink-0 items-center space-x-2 border-b border-slate-800 bg-slate-900 px-4 py-3">
            <MessageSquare className="h-4 w-4 text-slate-400" />
            <h2 className="text-xs font-bold tracking-wider text-slate-400 uppercase">
              Hypothesis Synthesis Stream
            </h2>
          </div>

          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
            {chatHistory.length === 0 && (
              <div className="flex h-full flex-col items-center justify-center space-y-2 p-6 text-center text-slate-500">
                <Sparkles className="h-8 w-8 animate-pulse text-slate-600" />
                <p className="text-sm">
                  Initiate Analytical Investigation Sequence
                </p>
                <p className="max-w-xs font-mono text-xs text-slate-600">
                  Example: "What are the common causes for transaction fraud?"
                </p>
              </div>
            )}
            {chatHistory.map((msg) => (
              <div
                key={msg.id}
                className={`flex max-w-[90%] flex-col ${msg.sender === "user" ? "ml-auto items-end" : "mr-auto items-start"}`}
              >
                <div
                  className={`rounded-xl p-3.5 text-xs leading-relaxed shadow-xs ${msg.sender === "user" ? "rounded-tr-none bg-emerald-600 font-medium text-slate-950" : "rounded-tl-none border border-slate-800 bg-slate-900 text-slate-300"}`}
                >
                  {msg.text}
                </div>
                {msg.rationale && (
                  <div className="mt-1.5 w-full rounded-lg border border-slate-800/40 bg-slate-950/40 p-3 font-mono text-[11px] leading-normal whitespace-pre-wrap text-slate-400">
                    <span className="mb-1 block text-[10px] font-bold tracking-wider text-slate-500 uppercase">
                      Engine Rationale:
                    </span>
                    {msg.rationale}
                  </div>
                )}
              </div>
            ))}
            {exploreMutation.isPending && (
              <div className="mr-auto flex max-w-[80%] items-center space-x-2 rounded-xl rounded-tl-none border border-slate-800 bg-slate-900 p-3">
                <div className="flex space-x-1">
                  <div className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 delay-0"></div>
                  <div className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 delay-150"></div>
                  <div className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 delay-300"></div>
                </div>
                <span className="pl-1.5 font-mono text-[11px] text-slate-400">
                  Orchestrator compiling viewports...
                </span>
              </div>
            )}
          </div>

          <form
            onSubmit={handleChatSubmit}
            className="flex-shrink-0 border-t border-slate-800 bg-slate-900 p-4"
          >
            <div className="group relative flex items-center rounded-xl border border-slate-800 bg-slate-950 shadow-inner transition-all duration-150 focus-within:border-emerald-500/50">
              <input
                type="text"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Formulate prompt hypothesis..."
                className="w-full border-none bg-transparent py-3 pr-12 pl-4 text-xs text-slate-200 placeholder-slate-600 outline-hidden"
                disabled={exploreMutation.isPending}
              />
              <button
                type="submit"
                disabled={exploreMutation.isPending || !prompt.trim()}
                className="absolute right-2 cursor-pointer rounded-lg bg-emerald-600 p-1.5 text-slate-950 transition-colors hover:bg-emerald-500 disabled:bg-slate-900 disabled:text-slate-700"
              >
                <Send className="h-3.5 w-3.5" />
              </button>
            </div>
          </form>
        </section>

        {/* RIGHT COLUMN: Dual-Layer Production Canvas */}
        <section className="flex h-full flex-1 flex-col overflow-hidden bg-slate-950">
          {/* Control Header */}
          <div className="flex flex-shrink-0 flex-col space-y-3.5 border-b border-slate-800 bg-slate-900 p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Database className="h-4 w-4 text-slate-400" />
                <h2 className="text-xs font-bold tracking-wider text-slate-400 uppercase">
                  Data Exploration Canvas
                </h2>
              </div>
              <button
                onClick={triggerSimulationPass}
                disabled={conditions.length === 0 || backtestMutation.isPending}
                className="flex cursor-pointer items-center space-x-1.5 rounded-md bg-emerald-600 px-4 py-1.5 font-sans text-xs font-bold text-slate-950 shadow-sm shadow-emerald-500/10 transition-all hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-600"
              >
                <Play className="h-3 w-3 fill-slate-950 stroke-none" />
                <span>Execute Simulation Pass ({conditions.length})</span>
              </button>
            </div>

            {/* Staged Interventions Filter Strip */}
            <div className="flex scrollbar-thin items-center space-x-2 overflow-x-auto py-0.5">
              <div className="mr-2 flex flex-shrink-0 items-center space-x-1.5 font-mono text-xs font-bold text-slate-500 uppercase">
                <Filter className="h-3.5 w-3.5 text-slate-400" />
                <span>Staged Interventions:</span>
              </div>

              {conditions.length === 0 ? (
                <span className="flex items-center font-mono text-xs text-slate-600 italic">
                  <Sparkle
                    className="mr-1.5 h-3 w-3 animate-spin text-slate-700"
                    style={{ animationDuration: "4s" }}
                  />
                  Workspace staged empty. Click cells inside data matrices below
                  to compose compound filters.
                </span>
              ) : (
                <div className="flex items-center space-x-2">
                  {conditions.map((c) => (
                    <div
                      key={c.id}
                      className="animate-fadeIn flex items-center space-x-1 rounded-lg border border-l-2 border-slate-800 border-l-emerald-500 bg-slate-950 px-2.5 py-1 font-mono text-xs text-slate-300 shadow-inner"
                    >
                      <span className="text-slate-500">{c.field}:</span>
                      <span className="font-semibold text-emerald-400">
                        "{c.value}"
                      </span>
                      <button
                        onClick={() => removeCondition(c.id)}
                        className="ml-1.5 cursor-pointer rounded-sm p-0.5 text-slate-500 transition-colors hover:bg-slate-900/60 hover:text-red-400"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </div>
                  ))}
                  <button
                    onClick={() => setConditions([])}
                    className="cursor-pointer px-1 pl-2 font-mono text-[10px] font-bold tracking-wider text-slate-500 uppercase transition-colors hover:text-red-400"
                  >
                    Clear All
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Main Data Canvas Layer */}
          <div className="min-h-0 flex-1 overflow-hidden p-4">
            <DataCanvas
              data={exploreSqlData}
              isLoading={executeMutation.isPending}
              error={executeMutation.error}
              onCellClick={handleCellClickPivot}
              activeConditions={conditions}
            />
          </div>

          {/* Collapsible Drawer: Rule Editor + Backtest */}
          <Drawer
            isOpen={isDrawerOpen}
            onToggle={() => setIsDrawerOpen(!isDrawerOpen)}
            title="📝 Co-Pilot Rule Editor"
            defaultHeight="h-96"
          >
            <div className="flex h-full flex-col space-y-4">
              {/* CodeMirror Panel */}
              <CodeMirrorPanel
                value={rulePredicateContent}
                onChange={setRulePredicateContent}
                onReexecute={handleReexecuteRule}
                ruleSqlData={ruleSqlData}
                ruleLoading={ruleReexecuteMutation.isPending}
                ruleError={ruleReexecuteMutation.error}
                isReexecuting={ruleReexecuteMutation.isPending}
              />

              {/* Backtest Results Panel */}
              {backtestData && (
                <div className="flex-shrink-0 border-t border-slate-800 pt-4">
                  <h3 className="mb-3 font-mono text-xs font-bold tracking-wider text-slate-400 uppercase">
                    Backtest Results
                  </h3>
                  <RulePanel
                    data={backtestData}
                    isLoading={backtestMutation.isPending}
                    error={backtestMutation.error}
                    activeRuleString={activeRuleString}
                  />
                </div>
              )}
            </div>
          </Drawer>
        </section>
      </main>
    </div>
  );
}
