import React from "react";
import type { RuleMetrics } from "../types/api";

interface RuleStudioProps {
  predicate: string;
  metrics: RuleMetrics | null;
  isLoading: boolean;
  onPredicateChange: (val: string) => void;
  onEvaluate: () => void;
}

export const RuleStudio: React.FC<RuleStudioProps> = ({
  predicate,
  metrics,
  isLoading,
  onPredicateChange,
  onEvaluate,
}) => {
  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(val);
  };

  return (
    <div className="flex h-full divide-x divide-slate-900 bg-slate-950">
      {/* Code Criteria Editor Block */}
      <div className="flex h-full w-[45%] flex-col space-y-4 p-4">
        <div className="flex flex-col">
          <span className="font-mono text-[10px] font-bold tracking-wider text-slate-500 uppercase">
            Predicate Logic Criteria
          </span>
          <p className="mt-0.5 text-[11px] text-slate-400">
            Refine the isolated WHERE assertion logic for live testing.
          </p>
        </div>

        <div className="relative flex flex-1 flex-col">
          <textarea
            value={predicate}
            onChange={(e) => onPredicateChange(e.target.value)}
            placeholder="No predicate currently loaded. Ask the agent or compose an active WHERE statement filter here..."
            className="w-full flex-1 resize-none rounded-xl border border-slate-800 bg-slate-900 p-4 font-mono text-xs leading-relaxed text-amber-400 focus:border-slate-700 focus:outline-none"
          />
        </div>

        <button
          onClick={onEvaluate}
          disabled={isLoading || !predicate.trim()}
          className="w-full rounded-xl bg-blue-600 py-2.5 font-mono text-xs font-semibold tracking-wider text-white uppercase shadow-md transition hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-500"
        >
          {isLoading
            ? "Recalculating Metrics..."
            : "Re-Run Evaluation Baseline"}
        </button>
      </div>

      {/* Metrics Live Analytics Frame */}
      <div className="h-full flex-1 space-y-5 overflow-y-auto p-4">
        <div className="flex flex-col">
          <span className="font-mono text-[10px] font-bold tracking-wider text-slate-500 uppercase">
            Live Engine Metrics Scorecard
          </span>
          <p className="mt-0.5 text-[11px] text-slate-400">
            Risk profile output derived from current historical limits data.
          </p>
        </div>

        {isLoading ? (
          <div className="flex h-48 animate-pulse items-center justify-center font-mono text-xs text-slate-500">
            Processing dataset rows...
          </div>
        ) : !metrics ? (
          <div className="flex h-48 items-center justify-center rounded-xl border border-dashed border-slate-900 font-mono text-xs text-slate-600">
            No processing metrics parsed. Run calculation above to compile
            statistics.
          </div>
        ) : (
          <div className="animate-fadeIn space-y-4">
            {/* Essential KPI Grid */}
            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
                <span className="block font-mono text-[10px] text-slate-500 uppercase">
                  Precision
                </span>
                <div className="mt-0.5 font-mono text-lg font-bold text-white">
                  {(metrics.precision * 100).toFixed(1)}%
                </div>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
                <span className="block font-mono text-[10px] text-slate-500 uppercase">
                  Recall
                </span>
                <div className="mt-0.5 font-mono text-lg font-bold text-white">
                  {(metrics.recall * 100).toFixed(1)}%
                </div>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
                <span className="block font-mono text-[10px] text-slate-500 uppercase">
                  FPR
                </span>
                <div className="mt-0.5 font-mono text-lg font-bold text-rose-400">
                  {(metrics.false_positive_rate * 100).toFixed(1)}%
                </div>
              </div>
            </div>

            {/* Financial Ledger Impact Rows */}
            <div className="space-y-3 rounded-xl border border-slate-800 bg-slate-900 p-4">
              <span className="block font-mono text-[10px] font-bold tracking-wider text-slate-400 uppercase">
                Financial Performance Sheet
              </span>
              <div className="grid grid-cols-3 gap-2 divide-x divide-slate-800 font-mono text-xs">
                <div>
                  <span className="block text-[9px] text-slate-500 uppercase">
                    Fraud Caught
                  </span>
                  <span className="mt-0.5 block text-sm font-bold text-emerald-400">
                    {formatCurrency(metrics.fraud_value_caught)}
                  </span>
                </div>
                <div className="pl-3">
                  <span className="block text-[9px] text-slate-500 uppercase">
                    Legit Blocked
                  </span>
                  <span className="mt-0.5 block text-sm font-bold text-rose-400">
                    {formatCurrency(metrics.legit_value_blocked)}
                  </span>
                </div>
                <div className="pl-3">
                  <span className="block text-[9px] text-slate-500 uppercase">
                    Net Efficiency
                  </span>
                  <span className="mt-0.5 block text-sm font-bold text-blue-400">
                    {formatCurrency(metrics.net_value)}
                  </span>
                </div>
              </div>
            </div>

            {/* Visual Confusion Matrix Segment */}
            <div className="rounded-xl border border-slate-900 bg-slate-950 p-3">
              <span className="mb-2 block font-mono text-[10px] font-bold tracking-wider text-slate-500 uppercase">
                Matrix Confusion Layout
              </span>
              <div className="grid grid-cols-2 gap-2 text-center font-mono text-xs">
                <div className="rounded border border-slate-800/60 bg-slate-900/40 p-2.5">
                  <div className="text-[9px] text-slate-500 uppercase">
                    True Positives
                  </div>
                  <div className="mt-0.5 text-sm font-bold text-white">
                    {metrics.true_positives}
                  </div>
                </div>
                <div className="rounded border border-slate-800/60 bg-slate-900/40 p-2.5">
                  <div className="text-[9px] text-slate-500 uppercase">
                    False Positives
                  </div>
                  <div className="mt-0.5 text-sm font-bold text-rose-500">
                    {metrics.false_positives}
                  </div>
                </div>
                <div className="rounded border border-slate-800/60 bg-slate-900/40 p-2.5">
                  <div className="text-[9px] text-slate-500 uppercase">
                    False Negatives
                  </div>
                  <div className="mt-0.5 text-sm font-bold text-amber-500">
                    {metrics.false_negatives}
                  </div>
                </div>
                <div className="rounded border border-slate-800/60 bg-slate-900/40 p-2.5">
                  <div className="text-[9px] text-slate-500 uppercase">
                    True Negatives
                  </div>
                  <div className="mt-0.5 text-sm font-bold text-slate-400">
                    {metrics.true_negatives}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
