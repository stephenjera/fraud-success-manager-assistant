import React from "react";
import type { DataGridResponse } from "../types/api";
import { Table, Zap } from "lucide-react";

interface ResultsTableProps {
  data: DataGridResponse | null;
  isLoading: boolean;
  error: Error | null;
}

export const ResultsTable: React.FC<ResultsTableProps> = ({
  data,
  isLoading,
  error,
}) => {
  if (isLoading) {
    return (
      <div className="flex h-64 flex-col items-center justify-center space-y-3 rounded-xl border border-slate-800 bg-slate-900">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-emerald-500 border-t-transparent"></div>
        <p className="font-mono text-sm text-slate-400">
          Running compiler execution pass...
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-h-64 overflow-auto rounded-xl border border-red-800/60 bg-red-950/40 p-4 font-mono text-xs whitespace-pre-wrap text-red-400">
        <span className="mb-1 block text-sm font-bold text-red-300">
          Sandbox Compile Error:
        </span>
        {error.message}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex h-64 flex-col items-center justify-center rounded-xl border border-dashed border-slate-800 bg-slate-900/40 text-slate-500">
        <Table className="mb-2 h-8 w-8 stroke-[1.5]" />
        <p className="text-sm">No data in workspace matrix</p>
        <p className="mt-1 text-xs text-slate-600">
          Execute an engine query to render records
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-xl border border-slate-800 bg-slate-900">
      {/* Telemetry Header Strip */}
      <div className="flex items-center justify-between border-b border-slate-800 bg-slate-950/60 px-4 py-2.5">
        <div className="flex items-center space-x-2 font-mono text-xs text-slate-400">
          <Zap className="h-3.5 w-3.5 fill-amber-400/20 text-amber-400" />
          <span>Execution Matrix Accepted</span>
        </div>
        <span className="rounded-md border border-emerald-900/60 bg-emerald-950/60 px-2 py-0.5 font-mono text-xs text-emerald-400">
          Telemetry: {data.execution_time_ms.toFixed(1)}ms
        </span>
      </div>

      {/* Main Grid View */}
      <div className="flex-1 overflow-auto">
        <table className="w-full border-collapse text-left font-mono text-xs">
          <thead className="sticky top-0 z-10 border-b border-slate-800 bg-slate-950 shadow-sm">
            <tr>
              {data.columns.map((col) => (
                <th
                  key={col}
                  className="px-4 py-3 text-[10px] font-semibold tracking-wider text-slate-300 uppercase"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {data.rows.length === 0 ? (
              <tr>
                <td
                  colSpan={data.columns.length}
                  className="px-4 py-8 text-center text-slate-500 italic"
                >
                  Query returned an empty dataset
                </td>
              </tr>
            ) : (
              data.rows.map((row, rIdx) => (
                <tr
                  key={rIdx}
                  className="transition-colors duration-150 hover:bg-slate-800/30"
                >
                  {row.map((val, cIdx) => (
                    <td
                      key={cIdx}
                      className="max-w-xs truncate px-4 py-2.5 text-slate-400"
                    >
                      {val === null ? (
                        <span className="text-slate-600 italic">NULL</span>
                      ) : (
                        String(val)
                      )}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
