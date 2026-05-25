import React from "react";
import { useMutation } from "@tanstack/react-query";
import { runQuery } from "../api/client";
import { QueryBar } from "../components/QueryBar";
import { SQLViewer } from "../components/SQLViewer";
import { ResultsTable } from "../components/ResultsTable";
import { InsightPanel } from "../components/InsightPanel";
import { RulePanel } from "../components/RulePanel";
import { ExplanationBox } from "../components/ExplanationBox";

export default function QueryPage() {
  const mutation = useMutation({ mutationFn: (q: string) => runQuery(q) });
  const data = mutation.data;
  const hasData = !!data;

  const score = data?.confidence ?? null;
  const isHighConf = score !== null && score > 0.8;
  const isMedConf = score !== null && score <= 0.8 && score > 0.5;

  return (
    <div className="mx-auto w-full max-w-[1600px] space-y-6">
      {/* 1. Command Bar Workspace Row */}
      <div className="rounded-2xl border border-slate-200 bg-white p-2 shadow-xs">
        <QueryBar onSubmit={mutation.mutate} loading={mutation.isPending} />
      </div>

      {mutation.isError && (
        <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm font-medium text-rose-700">
          <svg
            className="h-5 w-5 shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          Error retrieving analytical schema logs. Verify SQLite local
          connection endpoints.
        </div>
      )}

      {hasData && (
        <div className="animate-in fade-in space-y-6 duration-200">
          {/* 2. Transaction Telemetry Assessment Status Tracker Header */}
          <div className="flex items-center justify-between rounded-2xl border border-slate-800 bg-slate-900 px-5 py-3.5 text-white shadow-sm">
            <div className="flex items-center gap-3">
              <span className="flex h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
              <div className="text-xs">
                <span className="block text-[9px] font-bold tracking-widest text-slate-400 uppercase">
                  Data Sync Lifecycle
                </span>
                <span className="font-semibold text-slate-200">
                  Checkout.com Transaction Dataset Evaluated
                </span>
              </div>
            </div>

            {score !== null && (
              <div className="flex items-center gap-2.5 rounded-xl border border-slate-800/80 bg-slate-950/60 px-3.5 py-1.5">
                <span className="text-[10px] font-medium tracking-wider text-slate-400 uppercase">
                  FSM Assistant Accuracy Confidence
                </span>
                <span
                  className={`font-mono text-sm font-black ${
                    isHighConf
                      ? "text-emerald-400"
                      : isMedConf
                        ? "text-amber-400"
                        : "text-rose-400"
                  }`}
                >
                  {(score * 100).toFixed(1)}%
                </span>
              </div>
            )}
          </div>

          {/* 3. Data Visualization Deck Area Split Layout */}
          <div className="grid grid-cols-1 items-stretch gap-6 xl:grid-cols-12">
            <div className="flex flex-col xl:col-span-5">
              <SQLViewer sql={data.sql ?? null} />
            </div>
            <div className="flex flex-col xl:col-span-7">
              <ResultsTable data={data.results ?? null} />
            </div>
          </div>

          {/* 4. Bottom Row: Intelligence Analysis Modular Grid */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
              <ExplanationBox explanation={data.explanation ?? null} />
            </div>
            <div className="flex flex-col">
              <InsightPanel insight={data.insight ?? null} />
            </div>
            <div className="flex flex-col">
              <RulePanel rule={data.rule ?? null} />
            </div>
          </div>
        </div>
      )}

      {/* 5. Safe Sandbox Initial Setup Greeting Panel */}
      {!hasData && !mutation.isPending && (
        <div className="flex min-h-[400px] flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white/50 p-16 text-center text-slate-400">
          <svg
            className="mb-3 h-10 w-10 text-slate-300"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.57-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z"
            />
          </svg>
          <h3 className="text-sm font-bold tracking-wide text-slate-700 uppercase">
            FSM Assistant Terminal
          </h3>
          <p className="mt-1 max-w-sm text-xs leading-relaxed text-slate-400">
            Formulate natural language risk hypotheses above. GuardRail will
            generate valid transaction queries against local database schemas to
            map matching anomalous records.
          </p>
        </div>
      )}
    </div>
  );
}
