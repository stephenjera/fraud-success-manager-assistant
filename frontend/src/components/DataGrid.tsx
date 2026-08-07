import React from 'react';
import type { DataGridResponse } from '../types/api';

interface DataGridProps {
  data: DataGridResponse | null;
  isLoading: boolean;
  onExecuteRawSQL: () => void;
  sqlValue: string;
  onSqlChange: (val: string) => void;
  isPending?: boolean;
}

export const DataGrid: React.FC<DataGridProps> = ({
  data,
  isLoading,
  onExecuteRawSQL,
  sqlValue,
  onSqlChange,
  isPending = false,
}) => {
  return (
    <div className="flex flex-col h-full bg-slate-950" data-pending={String(isPending)}>
      {/* SQL Execution Console area */}
      <div className="p-4 border-b border-slate-950 bg-slate-900 space-y-3">
        <div className="flex items-center justify-between">
          <label className="text-xs font-mono font-bold tracking-wider text-slate-400 uppercase">
            Active Analytics Query (Read-Only Target)
          </label>
          <button
            onClick={onExecuteRawSQL}
            disabled={isLoading || !sqlValue}
            className="px-4 py-1.5 rounded bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 text-white disabled:text-slate-500 text-xs font-semibold tracking-wide transition shadow-md"
          >
            {isLoading ? 'Executing Against DuckDB...' : 'Run Statement'}
          </button>
        </div>
        <textarea
          value={sqlValue}
          onChange={(e) => onSqlChange(e.target.value)}
          className="w-full h-24 font-mono text-xs p-3 bg-slate-950 border border-slate-800 rounded-lg text-emerald-400 focus:outline-none focus:border-slate-700 resize-none leading-relaxed"
        />
      </div>

      {/* Grid Canvas Execution Space */}
      <div className="flex-1 overflow-auto relative">
        {isLoading && (
          <div className="absolute inset-0 bg-slate-950/70 backdrop-blur-sm z-10 flex items-center justify-center">
            <span className="text-xs font-mono text-slate-400 animate-pulse">Running data frame calculations...</span>
          </div>
        )}

        {!data && !isLoading ? (
          <div className="h-full flex items-center justify-center text-slate-600 text-xs font-mono">
            No dataset loaded. Run a prompt query to execute relational state analysis.
          </div>
        ) : (
          data && (
            <div className="w-full flex flex-col min-h-full">
              {/* Performance Indicator */}
              <div className="px-4 py-2 bg-slate-900 border-b border-slate-800 flex justify-end text-[10px] font-mono text-slate-500">
                Data compilation footprint: {data.execution_time_ms.toFixed(1)}ms | Rows returned: {data.rows.length}
              </div>

              {/* Data Table Matrix */}
              <div className="flex-1 overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-900 border-b border-slate-800 sticky top-0">
                      {data.columns.map((col, idx) => (
                        <th key={idx} className="px-4 py-3 font-mono text-xs font-bold text-slate-400 tracking-wider">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-900 font-mono text-xs">
                    {data.rows.length === 0 ? (
                      <tr>
                        <td colSpan={data.columns.length} className="px-4 py-8 text-center text-slate-500 italic">
                          Query returned empty set. Zero validation rows found.
                        </td>
                      </tr>
                    ) : (
                      data.rows.map((row, rowIdx) => (
                        <tr key={rowIdx} className="hover:bg-slate-900/50 transition">
                          {row.map((cell, cellIdx) => (
                            <td key={cellIdx} className="px-4 py-2.5 text-slate-300 max-w-xs truncate">
                              {cell === null ? <span className="text-slate-600 italic">null</span> : String(cell)}
                            </td>
                          ))}
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )
        )}
      </div>
    </div>
  );
};