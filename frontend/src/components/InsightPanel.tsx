import React from "react";
import type { Insight } from "../types/api";

type Props = {
  insight: Insight | null;
};

export function InsightPanel({ insight }: Props) {
  // If there's no insight object or the summary string inside it is empty, hide the panel
  if (!insight || !insight.summary) return null;

  // Now safely look at the summary text inside the object
  const lowerText = insight.summary.toLowerCase();
  const isHigh =
    lowerText.includes("fraud") ||
    lowerText.includes("critical") ||
    lowerText.includes("anomaly") ||
    insight.risk_level === "high";
  const isMedium =
    lowerText.includes("warning") ||
    lowerText.includes("suspicious") ||
    insight.risk_level === "medium";

  return (
    <div
      className={`rounded-xl border p-4 transition-all ${
        isHigh
          ? "border-red-200 bg-red-50/50"
          : isMedium
            ? "border-amber-200 bg-amber-50/50"
            : "border-slate-200 bg-slate-50"
      }`}
    >
      <div className="flex items-start gap-3">
        <div
          className={`shrink-0 rounded-lg p-2 ${
            isHigh
              ? "bg-red-100 text-red-700"
              : isMedium
                ? "bg-amber-100 text-amber-700"
                : "bg-blue-100 text-blue-700"
          }`}
        >
          {isHigh || isMedium ? (
            /* Warning Icon SVG */
            <svg
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          ) : (
            /* Lightbulb Icon SVG */
            <svg
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
              />
            </svg>
          )}
        </div>
        <div className="flex-1 space-y-1">
          <div className="flex items-center justify-between">
            <h5 className="text-sm font-semibold text-slate-900">
              Generated System Insight
            </h5>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-semibold tracking-wider uppercase ${
                isHigh
                  ? "bg-red-100 text-red-800"
                  : isMedium
                    ? "bg-amber-100 text-amber-800"
                    : "bg-slate-200 text-slate-800"
              }`}
            >
              {isHigh
                ? "Flagged Threat"
                : isMedium
                  ? "Review Needed"
                  : "Informational"}
            </span>
          </div>
          {/* Render the summary property of the object */}
          <p className="text-sm leading-relaxed whitespace-pre-wrap text-slate-600">
            {insight.summary}
          </p>
        </div>
      </div>
    </div>
  );
}
