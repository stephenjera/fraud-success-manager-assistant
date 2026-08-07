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
    <div className="flex h-full divide-x divide-border bg-base">
      <div className="flex h-full w-[45%] flex-col space-y-4 p-4">
        <div className="flex flex-col">
          <span className="font-mono text-[10px] font-bold tracking-wider text-text-dim uppercase">
            Rule Conditions
          </span>
          <p className="mt-0.5 text-[11px] text-text-muted">
            Edit the WHERE clause to test different rule logic
          </p>
        </div>

        <div className="relative flex flex-1 flex-col">
          <textarea
            value={predicate}
            onChange={(e) => onPredicateChange(e.target.value)}
            placeholder="No rule loaded. Ask the agent or type a WHERE clause..."
            className="w-full flex-1 resize-none rounded-xl border border-border bg-surface p-4 font-mono text-xs leading-relaxed text-text focus:border-border-highlight focus:outline-none"
          />
        </div>

        <button
          onClick={onEvaluate}
          disabled={isLoading || !predicate.trim()}
          className="w-full rounded-xl bg-accent-dim py-2.5 font-mono text-xs font-semibold tracking-wider text-accent uppercase shadow-md transition hover:bg-accent hover:text-base disabled:bg-surface-2 disabled:text-text-dim"
        >
          {isLoading
            ? "Evaluating..."
            : "Evaluate Rule"}
        </button>
      </div>

      <div className="h-full flex-1 space-y-5 overflow-y-auto p-4">
        <div className="flex flex-col">
          <span className="font-mono text-[10px] font-bold tracking-wider text-text-dim uppercase">
            Rule Metrics
          </span>
          <p className="mt-0.5 text-[11px] text-text-muted">
            Backtest results based on historical data
          </p>
        </div>

        {isLoading ? (
          <div className="flex h-48 animate-pulse items-center justify-center font-mono text-xs text-text-dim">
            Processing dataset rows...
          </div>
        ) : !metrics ? (
          <div className="flex h-48 items-center justify-center rounded-xl border border-dashed border-border font-mono text-xs text-text-dim">
            Run evaluation to see results
          </div>
        ) : (
          <div className="animate-fadeIn space-y-4">
            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-xl border border-border bg-surface-2 p-3">
                <span className="block font-mono text-[10px] text-text-dim uppercase">
                  Precision
                </span>
                <div className="mt-0.5 font-mono text-lg font-bold text-text">
                  {(metrics.precision * 100).toFixed(1)}%
                </div>
              </div>
              <div className="rounded-xl border border-border bg-surface-2 p-3">
                <span className="block font-mono text-[10px] text-text-dim uppercase">
                  Recall
                </span>
                <div className="mt-0.5 font-mono text-lg font-bold text-text">
                  {(metrics.recall * 100).toFixed(1)}%
                </div>
              </div>
              <div className="rounded-xl border border-border bg-surface-2 p-3">
                <span className="block font-mono text-[10px] text-text-dim uppercase">
                  FPR
                </span>
                <div className="mt-0.5 font-mono text-lg font-bold text-critical">
                  {(metrics.false_positive_rate * 100).toFixed(1)}%
                </div>
              </div>
            </div>

            <div className={`rounded-xl border p-3 ${metrics.statistically_significant ? 'border-accent-dim bg-accent/5' : 'border-critical-dim bg-critical/5'}`}>
              <span className="block font-mono text-[10px] font-bold tracking-wider text-text-muted uppercase">
                Statistical Significance
              </span>
              <div className="mt-1 flex items-center justify-between">
                <span className={`font-mono text-xs font-bold ${metrics.statistically_significant ? 'text-accent' : 'text-critical'}`}>
                  {metrics.statistically_significant ? 'SIG — Signal is reliable' : 'NOT SIG — May be noise'}
                </span>
                <span className="font-mono text-[10px] text-text-dim">
                  p={metrics.p_value < 0.001 ? '<0.001' : metrics.p_value.toFixed(4)} | OR={metrics.odds_ratio.toFixed(2)}
                </span>
              </div>
            </div>

            <div className="space-y-3 rounded-xl border border-border bg-surface-2 p-4">
              <span className="block font-mono text-[10px] font-bold tracking-wider text-text-muted uppercase">
                Financial Impact
              </span>
              <div className="grid grid-cols-3 gap-2 divide-x divide-border font-mono text-xs">
                <div>
                  <span className="block text-[9px] text-text-dim uppercase">
                    Fraud Caught
                  </span>
                  <span className="mt-0.5 block text-sm font-bold text-accent">
                    {formatCurrency(metrics.fraud_value_caught)}
                  </span>
                </div>
                <div className="pl-3">
                  <span className="block text-[9px] text-text-dim uppercase">
                    Legit Blocked
                  </span>
                  <span className="mt-0.5 block text-sm font-bold text-critical">
                    {formatCurrency(metrics.legit_value_blocked)}
                  </span>
                </div>
                <div className="pl-3">
                  <span className="block text-[9px] text-text-dim uppercase">
                    Net Efficiency
                  </span>
                  <span className="mt-0.5 block text-sm font-bold text-text-muted">
                    {formatCurrency(metrics.net_value)}
                  </span>
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-border bg-surface-2 p-4">
              <span className="mb-3 block text-xs font-semibold text-text-muted uppercase">
                Confusion Matrix
              </span>

              <div className="overflow-x-auto">
                <table className="w-full text-center border-collapse min-w-[280px]">
                  <thead>
                    <tr>
                      <th className="p-2"></th>
                      <th colSpan={2} className="pb-2 text-[10px] font-semibold text-text-dim uppercase border-b border-border">
                        Actual
                      </th>
                    </tr>
                    <tr>
                      <th></th>
                      <th className="pb-2 text-[10px] text-text-muted border-b border-border">Fraud</th>
                      <th className="pb-2 text-[10px] text-text-muted border-b border-border">Legitimate</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <th className="pr-2 text-[10px] font-semibold text-text-dim uppercase text-right align-middle border-r border-border">Predicted fraud</th>
                      <td className="p-3 border-b border-border">
                        <div className="text-[10px] text-text-muted">True Positives</div>
                        <div className="mt-0.5 text-lg font-bold text-text">{metrics.true_positives}</div>
                      </td>
                      <td className="p-3 border-b border-border">
                        <div className="text-[10px] text-text-muted">False Positives</div>
                        <div className="mt-0.5 text-lg font-bold text-critical">{metrics.false_positives}</div>
                      </td>
                    </tr>
                    <tr>
                      <th className="pr-2 text-[10px] font-semibold text-text-dim uppercase text-right align-middle border-r border-border">Predicted legit</th>
                      <td className="p-3">
                        <div className="text-[10px] text-text-muted">False Negatives</div>
                        <div className="mt-0.5 text-lg font-bold text-warning">{metrics.false_negatives}</div>
                      </td>
                      <td className="p-3">
                        <div className="text-[10px] text-text-muted">True Negatives</div>
                        <div className="mt-0.5 text-lg font-bold text-text-muted">{metrics.true_negatives}</div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
