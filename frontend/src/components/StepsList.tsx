import React, { useState } from "react";
import type { InvestigationStep } from "../types/api";

type Props = {
  steps: InvestigationStep[];
};

export default function StepsList({ steps }: Props) {
  const [openIdx, setOpenIdx] = useState<number | null>(null);

  if (!steps || steps.length === 0) {
    return (
      <div className="text-center py-8 text-slate-400 text-sm">
        No active FSM step mutations registered for this investigation stack.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 mb-2">
        <svg className="w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
        </svg>
        <h4 className="font-bold text-slate-900 text-sm uppercase tracking-wide">FSM Step Log Registry Timeline</h4>
      </div>
      
      <div className="relative border-l border-slate-200 pl-5 ml-2.5 space-y-6">
        {steps.map((s, i) => {
          const isOpen = openIdx === i;
          return (
            <div key={i} className="relative group">
              <span className="absolute -left-[26px] top-1 flex h-3.5 w-3.5 rounded-full border-2 border-indigo-600 bg-white ring-4 ring-white transition-transform group-hover:scale-110" />
              
              <div className="bg-slate-50/60 hover:bg-slate-50 border border-slate-200/80 rounded-xl p-4 transition-all">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-1">
                    <span className="inline-block text-[10px] font-bold uppercase tracking-wider text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded">
                      Step {i + 1} — {s.step_type}
                    </span>
                    <div className="text-xs font-mono text-slate-500 font-medium break-all mt-1">
                      <span className="text-slate-400 font-sans font-semibold">Inputs Parsed:</span>{" "}
                      {typeof s.input === "string" ? s.input : JSON.stringify(s.input)}
                    </div>
                  </div>
                  
                  <button
                    onClick={() => setOpenIdx(isOpen ? null : i)}
                    className="flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-all cursor-pointer whitespace-nowrap"
                  >
                    {isOpen ? "Hide JSON" : "View JSON Output"}
                  </button>
                </div>

                {isOpen && (
                  <div className="mt-3 border-t border-slate-200/60 pt-3">
                    <span className="block text-[10px] uppercase font-bold tracking-wider text-slate-400 mb-1.5">Raw JSON Object State Payload Response</span>
                    <div className="bg-slate-900 rounded-lg p-3 border border-slate-800 shadow-inner">
                      <pre className="text-[11px] font-mono text-emerald-400 overflow-x-auto max-h-[200px] leading-relaxed whitespace-pre">
                        {JSON.stringify(s.output, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}