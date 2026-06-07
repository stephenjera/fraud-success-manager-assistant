import React from "react";
import type { BacktestResponse } from "../types/api";
import {
  ShieldCheck,
  TrendingDown,
  AlertTriangle,
  Coins,
  BarChart3,
} from "lucide-react";

interface RulePanelProps {
  data: BacktestResponse | null;
  isLoading: boolean;
  error: Error | null;
}

export const RulePanel: React.FC<RulePanelProps> = ({
  data,
  isLoading,
  error,
}) => {
  if (isLoading) {
    return (
      <div className="flex h-64 flex-col items-center justify-center space-y-3 rounded-xl border border-slate-800 bg-slate-900">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent"></div>
        <p className="font-mono text-sm text-slate-400">
          Running sandbox population simulation...
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-800/60 bg-red-950/40 p-4 font-mono text-xs text-red-400">
        <span className="mb-1 block text-sm font-bold text-red-300">
          Simulation Failure:
        </span>
        {error.message}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex h-64 flex-col items-center justify-center rounded-xl border border-dashed border-slate-800 bg-slate-900/40 text-slate-500">
        <ShieldCheck className="mb-2 h-8 w-8 stroke-[1.5]" />
        <p className="text-sm">Simulation Environment Offline</p>
        <p className="mt-1 text-xs text-slate-600">
          Isolate a rule fragment to backtest historical records
        </p>
      </div>
    );
  }

  const { metrics, timeline_series } = data;
  const fpRatioPercent = (metrics.false_positive_ratio * 100).toFixed(1);

  return (
    <div className="space-y-6">
      {/* Production Analytics Scorecards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="flex items-start space-x-3 rounded-xl border border-slate-800 bg-slate-900 p-4 shadow-xs">
          <div className="rounded-lg border border-emerald-900 bg-emerald-950 p-2 text-emerald-400">
            <Coins className="h-5 w-5" />
          </div>
          <div>
            <p className="text-[11px] font-semibold tracking-wider text-slate-500 uppercase">
              Value Saved
            </p>
            <p className="mt-0.5 font-mono text-xl font-bold text-slate-100">
              $
              {metrics.total_fraud_value_saved_usd.toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </p>
          </div>
        </div>

        <div className="flex items-start space-x-3 rounded-xl border border-slate-800 bg-slate-900 p-4 shadow-xs">
          <div className="rounded-lg border border-blue-900 bg-blue-950 p-2 text-blue-400">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <div>
            <p className="text-[11px] font-semibold tracking-wider text-slate-500 uppercase">
              True Positives
            </p>
            <p className="mt-0.5 font-mono text-xl font-bold text-slate-100">
              {metrics.true_positives.toLocaleString()}{" "}
              <span className="font-sans text-xs font-normal text-slate-500">
                events
              </span>
            </p>
          </div>
        </div>

        <div className="flex items-start space-x-3 rounded-xl border border-slate-800 bg-slate-900 p-4 shadow-xs">
          <div className="rounded-lg border border-rose-900 bg-rose-950 p-2 text-rose-400">
            <AlertTriangle className="h-5 w-5" />
          </div>
          <div>
            <p className="text-[11px] font-semibold tracking-wider text-slate-500 uppercase">
              False Positives
            </p>
            <p className="mt-0.5 font-mono text-xl font-bold text-slate-100">
              {metrics.false_positives.toLocaleString()}{" "}
              <span className="font-sans text-xs font-normal text-slate-500">
                users
              </span>
            </p>
          </div>
        </div>

        <div className="flex items-start space-x-3 rounded-xl border border-slate-800 bg-slate-900 p-4 shadow-xs">
          <div className="rounded-lg border border-amber-900 bg-amber-950 p-2 text-amber-400">
            <TrendingDown className="h-5 w-5" />
          </div>
          <div>
            <p className="text-[11px] font-semibold tracking-wider text-slate-500 uppercase">
              Noise Ratio (FP / Total)
            </p>
            <p className="mt-0.5 font-mono text-xl font-bold text-slate-100">
              {fpRatioPercent}%
            </p>
          </div>
        </div>
      </div>

      {/* Basic Chronological Chart Layout */}
      <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
        <div className="mb-4 flex items-center space-x-2">
          <BarChart3 className="h-4 w-4 text-slate-400" />
          <h4 className="text-xs font-bold tracking-wider text-slate-300 uppercase">
            Chronological Intervention Profile
          </h4>
        </div>

        {/* Simple inline visual representation mapping of series */}
        <div className="flex h-48 items-end justify-between space-x-1.5 border-b border-slate-800 pt-4 font-mono">
          {timeline_series.map((pt, index) => {
            const maxVal = Math.max(
              ...timeline_series.map(
                (p) => p.fraud_blocked + p.legitimate_blocked,
              ),
              1,
            );
            const fraudHeight = (pt.fraud_blocked / maxVal) * 100;
            const legitHeight = (pt.legitimate_blocked / maxVal) * 100;

            return (
              <div
                key={index}
                className="group relative flex h-full flex-1 flex-col items-center"
              >
                <div className="flex h-full w-full items-end justify-center space-x-0.5">
                  <div
                    style={{ height: `${fraudHeight}%` }}
                    className="w-full rounded-t-xs bg-emerald-500/80 transition-all duration-150 hover:bg-emerald-400"
                  ></div>
                  <div
                    style={{ height: `${legitHeight}%` }}
                    className="w-full rounded-t-xs bg-rose-500/80 transition-all duration-150 hover:bg-rose-400"
                  ></div>
                </div>

                {/* Micro Tooltip */}
                <div className="pointer-events-none absolute bottom-full z-20 mb-2 rounded border border-slate-800 bg-slate-950 px-2 py-1 text-[10px] whitespace-nowrap opacity-0 shadow-lg transition-opacity duration-150 group-hover:opacity-100">
                  <p className="mb-0.5 font-bold text-slate-300">{pt.date}</p>
                  <p className="text-emerald-400">Caught: {pt.fraud_blocked}</p>
                  <p className="text-rose-400">
                    Blocked: {pt.legitimate_blocked}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
        <div className="mt-2 flex items-center justify-between font-mono text-[10px] text-slate-500">
          <span>{timeline_series[0]?.date}</span>
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-1">
              <span className="h-2 w-2 rounded-xs bg-emerald-500"></span>
              <span>True Positives</span>
            </div>
            <div className="flex items-center space-x-1">
              <span className="h-2 w-2 rounded-xs bg-rose-500"></span>
              <span>False Positives</span>
            </div>
          </div>
          <span>{timeline_series[timeline_series.length - 1]?.date}</span>
        </div>
      </div>
    </div>
  );
};
