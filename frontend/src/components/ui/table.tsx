import { cn } from "@/lib/utils"
import type { QueryResult, SampleBlock } from "@/lib/types"

// A dumb data grid. Feeds: the rerun result (QueryResult) and the backtest
// sample (SampleBlock) — both are {columns, rows} with an optional cap marker.
interface ResultsTableProps {
  columns: string[]
  rows: unknown[][]
  truncated?: boolean
  rowCap?: number
  empty?: string
  className?: string
}

function ResultsTable({
  columns,
  rows,
  truncated = false,
  rowCap,
  empty = "No rows",
  className,
}: ResultsTableProps) {
  if (columns.length === 0) {
    return <p className="py-6 text-center text-sm text-muted-foreground">{empty}</p>
  }
  return (
    <div className={cn("overflow-auto rounded-lg border border-border", className)}>
      <table className="w-full border-collapse text-sm">
        <thead className="sticky top-0 z-10">
          <tr className="bg-muted text-left">
            {columns.map((c) => (
              <th
                key={c}
                className="border-b border-border px-3 py-2 font-mono text-xs font-medium tracking-tight text-foreground"
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="py-6 text-center text-sm text-muted-foreground"
              >
                {empty}
              </td>
            </tr>
          ) : (
            rows.map((row, i) => (
              <tr key={i} className="odd:bg-background even:bg-muted/30 hover:bg-accent/60">
                {row.map((cell, j) => (
                  <td
                    key={j}
                    className="whitespace-nowrap border-b border-border/50 px-3 py-1.5 font-mono text-xs tabular-nums"
                  >
                    {renderCell(cell)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
      {truncated && (
        <div className="border-t border-border bg-muted/50 px-3 py-1.5 text-xs text-muted-foreground">
          Capped at {rowCap} rows — results are truncated in the source.
        </div>
      )}
    </div>
  )
}

// Cells render as text nodes only — no dangerouslySetInnerHTML (api-contract
// "data, never HTML" rule). Numbers stay numbers, nulls show as null.
function renderCell(cell: unknown): string {
  if (cell === null || cell === undefined) return ""
  if (typeof cell === "number") return String(cell)
  if (typeof cell === "boolean") return String(cell)
  return String(cell)
}

// Tiny convenience for the two DTO shapes that are both {columns, rows, …}.
function toGrid(r: QueryResult | SampleBlock) {
  return { columns: r.columns, rows: r.rows }
}

export { ResultsTable, toGrid }
