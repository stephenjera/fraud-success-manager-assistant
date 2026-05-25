import React, { useState } from "react";

type Props = {
  onSubmit: (q: string) => void;
  loading: boolean;
};

export function QueryBar({ onSubmit, loading }: Props) {
  const [value, setValue] = useState("");

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !loading && value.trim()) {
      onSubmit(value.trim());
    }
  };

  return (
    <div className="flex w-full items-center gap-3 rounded-xl bg-white p-2">
      <div className="flex flex-1 items-center gap-2.5 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 transition-all focus-within:border-indigo-600 focus-within:ring-2 focus-within:ring-indigo-600/10">
        {/* Search / Radar Loop SVG Icon */}
        <svg
          className="h-4 w-4 shrink-0 text-slate-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
        <input
          className="w-full bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400"
          placeholder="Formulate transactional fraud hypothesis... (e.g., Check for elevated chargebacks on electronics MCC)"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
        />
      </div>

      <button
        className="flex shrink-0 cursor-pointer items-center gap-2 rounded-xl bg-slate-950 px-5 py-3 text-xs font-bold tracking-wider text-white uppercase shadow-xs transition-all hover:bg-slate-900 active:bg-black disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
        disabled={loading || !value.trim()}
        onClick={() => onSubmit(value.trim())}
      >
        {loading ? (
          <>
            <svg
              className="h-3.5 w-3.5 animate-spin"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 15H19"
              />
            </svg>
            Analyzing
          </>
        ) : (
          "Run Analysis"
        )}
      </button>
    </div>
  );
}
