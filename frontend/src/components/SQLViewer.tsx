import React, { useState } from "react";

type Props = {
  sql: string | null;
};

function formatSQL(rawSql: string): string {
  if (!rawSql) return "";
  return rawSql
    .replace(
      /\b(SELECT|FROM|WHERE|LEFT JOIN|INNER JOIN|RIGHT JOIN|JOIN|GROUP BY|ORDER BY|HAVING|LIMIT|AND|OR)\b/gi,
      "\n$1",
    )
    .replace(/,\s*/g, ", ")
    .replace(/\n\s*\n/g, "\n")
    .trim();
}

export function SQLViewer({ sql }: Props) {
  const [copied, setCopied] = useState(false);
  if (!sql) return null;

  const formattedSql = formatSQL(sql);

  const handleCopy = () => {
    navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex h-full min-h-[220px] flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-950 shadow-xl">
      <div className="flex items-center justify-between border-b border-slate-800/80 bg-slate-900/60 px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-slate-700" />
            <span className="h-2.5 w-2.5 rounded-full bg-slate-700" />
            <span className="h-2.5 w-2.5 rounded-full bg-slate-700" />
          </div>
          <span className="ml-2 font-mono text-[11px] font-bold tracking-widest text-slate-400 uppercase">
            Generated Ledger Query Analysis
          </span>
        </div>
        <button
          onClick={handleCopy}
          className="cursor-pointer rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-800 hover:text-white"
        >
          {copied ? (
            <svg
              className="h-3.5 w-3.5 text-emerald-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M5 13l4 4L19 7"
              />
            </svg>
          ) : (
            <svg
              className="h-3.5 w-3.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"
              />
            </svg>
          )}
        </button>
      </div>

      <div className="max-h-[300px] flex-1 overflow-auto bg-slate-950 p-4 font-mono text-xs leading-relaxed">
        <pre className="whitespace-pre text-sky-400 selection:bg-indigo-500/30">
          {formattedSql}
        </pre>
      </div>
    </div>
  );
}
