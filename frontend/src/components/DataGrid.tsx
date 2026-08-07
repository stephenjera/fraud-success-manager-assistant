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
    <div className="flex flex-col h-full bg-base">
      <div className={`p-4 border-b border-border bg-surface space-y-3 ${isPending ? 'ring-1 ring-inset ring-warning-dim' : ''}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <label className="text-xs font-medium text-text-muted uppercase">
              SQL Query
            </label>
            {isPending && (
              <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium bg-warning-dim/20 text-warning">
                <span className="inline-block h-1 w-1 rounded-full bg-warning animate-pulse" />
                pending review
              </span>
            )}
          </div>
          <button
            onClick={onExecuteRawSQL}
            disabled={isLoading || !sqlValue}
            className="px-4 py-1.5 rounded bg-accent-dim hover:bg-accent disabled:bg-border text-accent disabled:text-text-dim text-xs font-semibold tracking-wide transition hover:text-base shadow-md"
          >
            {isLoading ? 'Running...' : 'Run Query'}
          </button>
        </div>
        <textarea
          value={sqlValue}
          onChange={(e) => onSqlChange(e.target.value)}
          className={`w-full h-24 font-mono-app text-xs p-3 bg-base border rounded-lg text-accent focus:outline-none resize-none leading-relaxed transition ${
            isPending
              ? 'border-warning-dim'
              : 'border-border focus:border-border-highlight'
          }`}
        />
      </div>

      <div className="flex-1 overflow-auto relative">
        {isLoading && (
          <div className="absolute inset-0 bg-base/80 backdrop-blur-sm z-10 flex items-center justify-center">
            <span className="text-xs font-mono-app text-text-muted animate-pulse">Loading results...</span>
          </div>
        )}

        {!data && !isLoading ? (
          <div className="h-full flex items-center justify-center text-text-dim text-sm font-mono-app">
            No results yet. Run a query to explore the data.
          </div>
        ) : (
          data && (
            <div className="w-full flex flex-col min-h-full">
              <div className="px-4 py-2 bg-surface border-b border-border flex justify-end text-[10px] font-mono-app text-text-dim">
                {(data.execution_time_ms).toFixed(1)}ms - {data.rows.length} rows
              </div>

              <div className="flex-1 overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-surface border-b border-border sticky top-0">
                      {data.columns.map((col, idx) => (
                        <th key={idx} className="px-4 py-3 font-mono-app text-[11px] font-semibold text-text-muted tracking-wide">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border font-mono-app text-xs">
                    {data.rows.length === 0 ? (
                      <tr>
                        <td colSpan={data.columns.length} className="px-4 py-8 text-center text-text-dim">
                          Query returned no results
                        </td>
                      </tr>
                    ) : (
                      data.rows.map((row, rowIdx) => (
                        <tr key={rowIdx} className="hover:bg-surface-2/50 transition">
                          {row.map((cell, cellIdx) => (
                            <td key={cellIdx} className="px-4 py-2.5 text-text max-w-xs truncate">
                              {cell === null ? <span className="text-text-dim">null</span> : String(cell)}
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
