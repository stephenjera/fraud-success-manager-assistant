import React from "react";
import { Database } from "lucide-react";
import type { DataGridResponse } from "../types/api";

interface DataCanvasProps {
  data: DataGridResponse | null;
  isLoading: boolean;
  error: any;
  onCellClick?: (columnName: string, value: any) => void;
  activeConditions?: any[];
}

export function DataCanvas({
  data,
  isLoading,
  error,
  onCellClick = () => {},
  activeConditions = [],
}: DataCanvasProps) {
  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center rounded-xl border border-slate-800 bg-slate-900/50">
        <div className="flex items-center space-x-2 text-center font-mono text-xs text-slate-500">
          <div className="h-2 w-2 animate-ping rounded-full bg-emerald-500" />
          <span>Streaming analytical matrix partitions...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-900/50 bg-red-950/30 p-4 font-mono text-xs text-red-400">
        <span className="mb-1 block font-bold uppercase">Matrix Error:</span>
        {error.message || "Relational execution failure."}
      </div>
    );
  }

  if (!data || !data.rows || data.rows.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center rounded-xl border border-dashed border-slate-800 bg-slate-900/30 p-6 text-center text-slate-500">
        <Database className="mb-2 h-6 w-6 text-slate-700" />
        <p className="text-xs">No active data in workspace</p>
        <p className="mt-1 font-mono text-[10px] text-slate-600">
          Submit an investigation prompt to load records
        </p>
      </div>
    );
  }

  const columns = Object.keys(data.rows[0]);

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-xl border border-slate-800 bg-slate-900">
      <div className="flex-1 overflow-x-auto overflow-y-auto">
        <table className="w-full min-w-max border-collapse text-left">
          <thead>
            <tr className="sticky top-0 z-10 border-b border-slate-800 bg-slate-950/80">
              {columns.map((col) => (
                <th
                  key={col}
                  className="px-4 py-2.5 font-mono text-[10px] font-bold tracking-wider text-slate-400 uppercase"
                >
                  {col.replace(/_/g, " ")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-mono text-xs">
            {data.rows.map((row: any, i: number) => (
              <tr key={i} className="transition-colors hover:bg-slate-950/40">
                {columns.map((col) => {
                  const isStaged = activeConditions.some(
                    (c) => c.value === String(row[col]),
                  );
                  return (
                    <td
                      key={`${i}-${col}`}
                      onClick={() => onCellClick(col, row[col])}
                      className={`cursor-pointer border-slate-800/20 px-4 py-2.5 transition-all ${
                        isStaged
                          ? "border-l-2 border-l-emerald-500 bg-emerald-950/20 text-emerald-300"
                          : "hover:bg-slate-800/30 hover:text-slate-50"
                      }`}
                    >
                      {String(row[col] ?? "—").substring(0, 50)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex-shrink-0 border-t border-slate-800 bg-slate-950 px-4 py-2 font-mono text-xs text-slate-500">
        Showing {data.rows.length} records
      </div>
    </div>
  );
}
