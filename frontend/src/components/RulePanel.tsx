import React from "react";
import type { FraudRule } from "../types/api";

type Props = {
  rule: FraudRule | null;
  isAccepted?: boolean;
  onAccept?: () => void;
};

export function RulePanel({ rule }: Props) {
  if (!rule || !rule.rule_sql_where) return null;

  return (
    <div className="flex h-full flex-col justify-between rounded-2xl border border-indigo-100 bg-indigo-50/40 p-5">
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          {/* Document / Rule List SVG Icon */}
          <div className="shrink-0 rounded-lg bg-indigo-100 p-1.5 text-indigo-700">
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
          </div>
          <h5 className="text-sm font-bold tracking-wide text-slate-900">
            PROPOSED FRAUD RULE CONDITIONAL
          </h5>
        </div>

        <p className="text-xs leading-relaxed text-slate-600">
          {rule.description ||
            "Suggested transaction filtering logic derived from verified anomaly matches:"}
        </p>

        <div className="max-w-full overflow-x-auto rounded-xl border border-slate-800 bg-slate-950 p-3 font-mono text-[11px] leading-relaxed text-emerald-400 shadow-inner select-all">
          WHERE {rule.rule_sql_where}
        </div>
      </div>
    </div>
  );
}
