import React, { useState } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { sql } from "@codemirror/lang-sql";
import { Play, Copy, AlertCircle } from "lucide-react";
import type { DataGridResponse } from "../types/api";
import { DataCanvas } from "./DataCanvas";

interface CodeMirrorPanelProps {
  value: string;
  onChange: (newValue: string) => void;
  onReexecute: (predicateText: string) => void;
  ruleSqlData: DataGridResponse | null;
  ruleLoading: boolean;
  ruleError: any;
  isReexecuting: boolean;
}

const RULE_TEMPLATE = `-- Refine your rule predicate here (WHERE clause only)
-- Available aliases: t (transactions), fl (fraud_labels), c (cards), u (users), m (merchants), mc (mcc_codes)
-- Example: t.amount > 1000 AND mc.name = 'Grocery Stores'
t.amount > 1000`;

export function CodeMirrorPanel({
  value,
  onChange,
  onReexecute,
  ruleSqlData,
  ruleLoading,
  ruleError,
  isReexecuting,
}: CodeMirrorPanelProps) {
  const [copied, setCopied] = useState(false);

  const handleCopyRule = () => {
    navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleReexecute = () => {
    if (value.trim()) {
      onReexecute(value.trim());
    }
  };

  return (
    <div className="flex h-full flex-col space-y-3">
      {/* Editor Header */}
      <div className="flex items-center justify-between space-x-3 rounded-lg border border-slate-800 bg-slate-950 p-3">
        <div className="flex-1">
          <h3 className="font-mono text-xs font-bold tracking-wider text-slate-400 uppercase">
            Rule Predicate Editor
          </h3>
          <p className="mt-0.5 font-mono text-[10px] text-slate-600">
            WHERE clause for backtester
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={handleCopyRule}
            className="rounded-md bg-slate-800 p-2 text-slate-400 transition-all hover:bg-slate-700 hover:text-slate-200"
            title="Copy rule to clipboard"
          >
            <Copy className="h-3.5 w-3.5" />
          </button>
          {copied && (
            <span className="font-mono text-xs text-emerald-400">Copied!</span>
          )}
        </div>
      </div>

      {/* CodeMirror Editor */}
      <div className="flex-shrink-0 overflow-hidden rounded-lg border border-slate-800">
        <CodeMirror
          value={value}
          onChange={onChange}
          extensions={[sql()]}
          theme="dark"
          height="180px"
          basicSetup={{
            lineNumbers: true,
            highlightActiveLineGutter: true,
            foldGutter: false,
            dropCursor: true,
            allowMultipleSelections: true,
            indentOnInput: true,
            bracketMatching: true,
            closeBrackets: true,
            autocompletion: false,
            rectangularSelection: true,
            highlightSelectionMatches: true,
            searchKeymap: true,
          }}
          className="text-xs"
        />
      </div>

      {/* Re-Execute Button & Status */}
      <div className="flex items-center space-x-2">
        <button
          onClick={handleReexecute}
          disabled={!value.trim() || isReexecuting}
          className="flex cursor-pointer items-center space-x-1.5 rounded-md bg-emerald-600 px-3.5 py-1.5 font-sans text-xs font-bold text-slate-950 shadow-sm shadow-emerald-500/10 transition-all hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-600"
        >
          <Play className="h-3 w-3 fill-slate-950 stroke-none" />
          <span>Re-Execute Rule</span>
        </button>

        {isReexecuting && (
          <span className="flex items-center space-x-1.5 font-mono text-xs text-slate-500">
            <div className="h-1.5 w-1.5 animate-spin rounded-full bg-slate-400" />
            <span>Executing...</span>
          </span>
        )}

        {ruleError && (
          <div className="flex items-center space-x-1.5 rounded-md bg-red-950/30 px-3 py-1.5 font-mono text-xs text-red-400">
            <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
            <span>{ruleError.message || "Execution error"}</span>
          </div>
        )}
      </div>

      {/* Results Table */}
      {ruleSqlData && (
        <div className="min-h-0 flex-1 overflow-hidden rounded-lg">
          <div className="mb-2 font-mono text-[10px] font-bold tracking-wider text-slate-400 uppercase">
            Rule Predicate Results:
          </div>
          <DataCanvas
            data={ruleSqlData}
            isLoading={ruleLoading}
            error={ruleError}
          />
        </div>
      )}

      {!ruleSqlData && !ruleLoading && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-slate-800 bg-slate-900/30 p-6 text-center text-slate-500">
          <p className="text-xs">No rule results yet</p>
          <p className="mt-1 font-mono text-[10px] text-slate-600">
            Edit the rule above and click "Re-Execute Rule" to test
          </p>
        </div>
      )}
    </div>
  );
}
