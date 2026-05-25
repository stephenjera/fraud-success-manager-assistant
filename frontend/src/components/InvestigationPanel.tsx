import React, { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { SQLViewer } from "./SQLViewer";
import { ResultsTable } from "./ResultsTable";

interface WorkspaceSnapshot {
  version: number;
  prompt: string;
  sql: string;
  record_count: number;
  insight: string;
  rule: string | null;
  precision: number;
  recall: number;
  block_rate: number;
  status: string;
  warnings: string[];
}

interface InvestigationSession {
  session_id: string;
  initial_question: string;
  session_name: string;
  current_sql: string | null;
  current_results: any[] | null;
  current_insight: string | { summary: string } | null;
  current_rule: string | null;
  current_precision?: number;
  current_recall?: number;
  current_block_rate?: number;
  current_status?: string;
  current_warnings?: string[];
  confidence?: number;
  done?: boolean;
  history: WorkspaceSnapshot[];
}

type ActiveTab = "table" | "sql" | "insight";

export default function InvestigationPanel() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<ActiveTab>("table");

  const [activeSessionId, setActiveSessionId] = useState<string>(() => {
    const saved = localStorage.getItem("fsm_active_session_id");
    if (saved) return saved;
    const newId = crypto.randomUUID();
    localStorage.setItem("fsm_active_session_id", newId);
    return newId;
  });

  const [inputPrompt, setInputPrompt] = useState("");

  const { data: session, isLoading } = useQuery<InvestigationSession>({
    queryKey: ["investigation", activeSessionId],
    queryFn: async () => {
      const res = await axios.get(
        `http://127.0.0.1:8000/api/investigation/${activeSessionId}`,
      );
      return res.data;
    },
    enabled: !!activeSessionId,
  });

  const runWorkflowMutation = useMutation({
    mutationFn: async (payload: { prompt: string; mode: "new" | "refine" }) => {
      const res = await axios.post(
        `http://127.0.0.1:8000/api/investigation/run?session_id=${activeSessionId}&question=${encodeURIComponent(payload.prompt)}&mode=${payload.mode}`,
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["investigation", activeSessionId],
      });
      setInputPrompt("");
    },
  });

  const rollbackMutation = useMutation({
    mutationFn: async (versionId: number) => {
      const res = await axios.post(
        `http://127.0.0.1:8000/api/investigation/${activeSessionId}/rollback/${versionId}`,
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["investigation", activeSessionId],
      });
    },
  });

  const handleClearWorkspace = () => {
    const newId = crypto.randomUUID();
    localStorage.setItem("fsm_active_session_id", newId);
    setActiveSessionId(newId);
    setInputPrompt("");
  };

  // FIX 1: Ensure local UI operations don't freeze the screen if the initial payload load returns
  const isWorking = runWorkflowMutation.isPending || rollbackMutation.isPending;

  // FIX 2: Explicitly confirm valid query text exists before locking UI to a "Refine" track
  const hasWorkingData = !!(session && session.current_sql);

  const getStatusStyle = (status = "ACCEPTED") => {
    if (status === "REJECTED")
      return "bg-rose-50 text-rose-700 border-rose-200";
    if (status === "REVIEW")
      return "bg-amber-50 text-amber-700 border-amber-200";
    return "bg-emerald-50 text-emerald-700 border-emerald-200";
  };

  const renderInsightText = (insightField: any): string => {
    if (!insightField) return "No insight logged for this transaction segment.";
    if (typeof insightField === "object") {
      return insightField.summary || JSON.stringify(insightField);
    }
    return insightField;
  };

  return (
    <div className="box-border flex h-[calc(100vh-80px)] w-full items-center justify-center bg-slate-50/50 p-4">
      <div className="flex h-full w-full max-w-[1600px] items-stretch gap-4 overflow-hidden">
        {/* ================= LEFT COMMAND COCKPIT PANEL (30% WIDTH) ================= */}
        <div className="flex h-full min-w-0 flex-[3] flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xs">
          <div className="flex shrink-0 items-center justify-between border-b border-slate-100 p-4">
            <div>
              <h3 className="text-xs font-bold tracking-wider text-slate-900 uppercase">
                Session Parameters
              </h3>
              <p className="font-mono text-[10px] text-slate-400">
                ID: {activeSessionId.slice(0, 8)}...
              </p>
            </div>
            <button
              onClick={handleClearWorkspace}
              className="cursor-pointer text-[10px] font-bold tracking-wider text-slate-400 uppercase transition-colors hover:text-rose-600"
            >
              Clear Workspace
            </button>
          </div>

          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
            <div className="space-y-1">
              <label className="text-[10px] font-extrabold tracking-wider text-slate-400 uppercase">
                Lineage History Target
              </label>
              <select
                disabled={isWorking || !session?.history?.length}
                value={
                  session?.history?.length ? session.history.length + 1 : 1
                }
                onChange={(e) => {
                  const targetVer = parseInt(e.target.value);
                  if (targetVer <= (session?.history?.length ?? 0)) {
                    rollbackMutation.mutate(targetVer);
                  }
                }}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700 transition-all outline-none focus:border-indigo-500 disabled:opacity-60"
              >
                <option
                  value={session?.history ? session.history.length + 1 : 1}
                >
                  Version #{(session?.history?.length ?? 0) + 1} (Active
                  Workspace)
                </option>
                {session?.history?.map((snap) => (
                  <option key={snap.version} value={snap.version}>
                    Version #{snap.version} — "{snap.prompt.slice(0, 28)}..."
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-3.5 rounded-xl border border-slate-100 bg-slate-50/60 p-3.5">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-extrabold tracking-wider text-slate-400 uppercase">
                  Live Metric Analytics
                </span>
                <span
                  className={`rounded-md border px-2 py-0.5 text-[9px] font-black uppercase ${getStatusStyle(session?.current_status)}`}
                >
                  {session?.current_status || "ACCEPTED"}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="rounded-lg border border-slate-100 bg-white p-2">
                  <p className="text-[9px] font-bold tracking-wider text-slate-400 uppercase">
                    Precision
                  </p>
                  <p className="mt-0.5 text-xs font-black text-slate-900">
                    {session?.current_precision
                      ? (session.current_precision * 100).toFixed(1)
                      : "0.0"}
                    %
                  </p>
                </div>
                <div className="rounded-lg border border-slate-100 bg-white p-2">
                  <p className="text-[9px] font-bold tracking-wider text-slate-400 uppercase">
                    Recall
                  </p>
                  <p className="mt-0.5 text-xs font-black text-slate-900">
                    {session?.current_recall
                      ? (session.current_recall * 100).toFixed(1)
                      : "0.0"}
                    %
                  </p>
                </div>
                <div className="rounded-lg border border-slate-100 bg-white p-2">
                  <p className="text-[9px] font-bold tracking-wider text-slate-400 uppercase">
                    Block Rate
                  </p>
                  <p className="mt-0.5 text-xs font-black text-slate-900">
                    {session?.current_block_rate
                      ? (session.current_block_rate * 100).toFixed(1)
                      : "0.0"}
                    %
                  </p>
                </div>
              </div>

              {session?.current_warnings &&
                session.current_warnings.length > 0 && (
                  <div className="space-y-1 border-t border-slate-200/50 pt-2">
                    {session.current_warnings.map((warn, index) => (
                      <div
                        key={index}
                        className="flex items-start gap-1.5 text-[10px] leading-tight font-medium text-amber-800"
                      >
                        <span className="shrink-0 text-amber-500">⚠️</span>
                        <span>{warn}</span>
                      </div>
                    ))}
                  </div>
                )}
            </div>
          </div>

          {/* CHAT INPUT CONTAINER */}
          <div className="shrink-0 border-t border-slate-100 bg-white p-4">
            <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-2.5 transition-all focus-within:border-indigo-600 focus-within:bg-white">
              <input
                type="text"
                disabled={isWorking}
                value={inputPrompt}
                onChange={(e) => setInputPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && inputPrompt.trim() && !isWorking) {
                    runWorkflowMutation.mutate({
                      prompt: inputPrompt.trim(),
                      mode: hasWorkingData ? "refine" : "new",
                    });
                  }
                }}
                placeholder={
                  hasWorkingData
                    ? "Tweak parameter metrics rule criteria..."
                    : "Ask a production fraud vector question..."
                }
                className="w-full border-none bg-transparent py-3 text-xs text-slate-800 outline-none placeholder:text-slate-400"
              />
              <button
                disabled={isWorking || !inputPrompt.trim()}
                onClick={() =>
                  runWorkflowMutation.mutate({
                    prompt: inputPrompt.trim(),
                    mode: hasWorkingData ? "refine" : "new",
                  })
                }
                className="shrink-0 cursor-pointer rounded-md bg-slate-900 px-3 py-1.5 text-[9px] font-bold tracking-wider text-white uppercase transition-colors hover:bg-slate-800 disabled:bg-slate-100 disabled:text-slate-400"
              >
                {hasWorkingData ? "Refine" : "Analyze"}
              </button>
            </div>
          </div>
        </div>

        {/* ================= RIGHT-HAND WORKBENCH CANVAS (70% WIDTH) ================= */}
        <div className="flex h-full min-w-0 flex-[7] flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xs">
          <div className="flex shrink-0 items-center justify-between border-b border-slate-200/80 bg-slate-50 px-4">
            <div className="flex gap-4">
              <button
                onClick={() => setActiveTab("table")}
                className={`cursor-pointer border-b-2 py-3 text-xs font-bold tracking-wider uppercase transition-all ${activeTab === "table" ? "border-indigo-600 text-indigo-600" : "border-transparent text-slate-400 hover:text-slate-600"}`}
              >
                Data Record Grid
              </button>
              <button
                onClick={() => setActiveTab("sql")}
                className={`cursor-pointer border-b-2 py-3 text-xs font-bold tracking-wider uppercase transition-all ${activeTab === "sql" ? "border-indigo-600 text-indigo-600" : "border-transparent text-slate-400 hover:text-slate-600"}`}
              >
                Compiled SQL Logic
              </button>
              <button
                onClick={() => setActiveTab("insight")}
                className={`cursor-pointer border-b-2 py-3 text-xs font-bold tracking-wider uppercase transition-all ${activeTab === "insight" ? "border-indigo-600 text-indigo-600" : "border-transparent text-slate-400 hover:text-slate-600"}`}
              >
                Interpretation Logs
              </button>
            </div>

            <div className="max-w-[180px] truncate rounded bg-slate-200 px-2 py-0.5 font-mono text-[10px] font-bold text-slate-600 sm:max-w-[240px]">
              {session?.session_name || "Uninitialized Workbench Workspace"}
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-hidden bg-slate-50/20 p-4">
            {hasWorkingData ? (
              <div className="flex h-full flex-col overflow-hidden">
                {activeTab === "table" && (
                  <div className="min-h-0 flex-1 overflow-auto rounded-xl border border-slate-200 bg-white shadow-xs">
                    <ResultsTable data={session.current_results || []} />
                  </div>
                )}

                {activeTab === "sql" && (
                  <div className="min-h-0 flex-1 overflow-auto rounded-xl border border-slate-950 bg-slate-900 p-4 font-mono text-xs text-indigo-300 shadow-inner">
                    <SQLViewer sql={session.current_sql} />
                  </div>
                )}

                {activeTab === "insight" && (
                  <div className="grid min-h-0 flex-1 grid-rows-2 gap-4 overflow-hidden">
                    <div className="space-y-1.5 overflow-y-auto rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
                      <h4 className="text-[10px] font-bold tracking-wider text-slate-400 uppercase">
                        AI Analytical Deep-Dive
                      </h4>
                      <p className="text-xs leading-relaxed font-medium whitespace-pre-wrap text-slate-600">
                        {renderInsightText(session.current_insight)}
                      </p>
                    </div>
                    <div className="space-y-2 overflow-y-auto rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
                      <h4 className="text-[10px] font-bold tracking-wider text-indigo-600 uppercase">
                        Active Rule Production Conditional Constraint
                      </h4>
                      <div className="overflow-x-auto rounded-lg border border-slate-950 bg-slate-900 p-3 font-mono text-[11px] text-emerald-400">
                        WHERE {session.current_rule || "1=1"}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex h-full flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 bg-white p-6 text-center text-slate-400">
                <div className="mb-2 flex h-8 w-8 items-center justify-center rounded-full border border-slate-100 bg-slate-50 text-slate-300">
                  ⚡
                </div>
                <h4 className="mb-0.5 text-[11px] font-bold tracking-wide text-slate-700 uppercase">
                  Workbench Canvas Ready
                </h4>
                <p className="max-w-xs text-xs leading-normal text-slate-400">
                  Input a context query in the left control panel workspace to
                  activate live data telemetry processing tracking loops.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
