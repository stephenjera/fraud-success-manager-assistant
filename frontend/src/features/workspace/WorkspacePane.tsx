// The workspace pane — SQL editor + results + grounding cards + Pin.
// Rows come from rerun (Gap H): the grounding DTO is the durable *fact*; the
// result set is re-derived deterministically (data-model.md: no result-rows column).
import * as React from "react"
import { Pin as PinIcon, RotateCcw, RefreshCw } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardTitle } from "@/components/ui/card"
import { ResultsTable } from "@/components/ui/table"
import type { QueryResult, Revision, SelectedQuery } from "@/lib/types"
import { ApiErrorBlock, toContractError, type ContractError } from "@/lib/error-block"
import { workspaceApi } from "./api"

export interface WorkspacePaneProps {
  conversationId: string | null
  selected: SelectedQuery | null
  onPinned: () => void
}

function WorkspacePane({ conversationId, selected, onPinned }: WorkspacePaneProps) {
  const [sql, setSql] = React.useState<string | null>(null)
  const [results, setResults] = React.useState<QueryResult | null>(null)
  const [flags, setFlags] = React.useState<string[]>([])
  const [revisions, setRevisions] = React.useState<Revision[]>([])
  const [revisionId, setRevisionId] = React.useState<string | null>(null)
  const [running, setRunning] = React.useState(false)
  const [pinned, setPinned] = React.useState(false)
  // B9: one structured failure, rendered as a contract block. The message is
  // the server's own message; the offending SQL (and code hint) come from the
  // contract `details`.
  const [error, setError] = React.useState<ContractError | null>(null)
  const [stale, setStale] = React.useState(false)

  const note = React.useCallback((e: unknown, fallback: string) => {
    setError(toContractError(e, fallback, "offending_sql"))
  }, [])
  const clearError = React.useCallback(() => setError(null), [])

  const resetFor = (id: string | null) => {
    if (id) return
    setResults(null)
    setFlags([])
    setRevisions([])
    setRevisionId(null)
    setSql("")
    setError(null)
    setPinned(false)
    setStale(false)
  }

  const materialize = React.useCallback(
    async (cid: string, mid: string, s: string) => {
      setRevisions(
        await workspaceApi.revisions(cid, mid).catch(() => [] as Revision[]),
      )
      const res = await workspaceApi.rerun(cid, mid, s)
      setResults(res.result)
      setFlags(res.flags ?? [])
      setRevisionId(res.revision_id)
    },
    [],
  )

  const execute = React.useCallback(async () => {
    if (!conversationId || !selected || !sql?.trim()) return
    setRunning(true)
    clearError()
    setPinned(false)
    setStale(false) // a fresh attempt is running; we'll mark it stale only if it fails
    try {
      await materialize(conversationId, selected.message_id, sql!)
      setStale(false)
    } catch (e) {
      setStale(true) // keep the last good rows; flag them as stale below
      note(e, "Re-run failed.")
    } finally {
      setRunning(false)
    }
  }, [conversationId, selected, sql, materialize, clearError, note])

  // Materialize the results the first time a grounded query is selected from chat.
  React.useEffect(() => {
    if (!selected) {
      resetFor(null)
      return
    }
    setSql(selected.sql)
    setPinned(false)
    clearError()
    setResults(null)
    setStale(false) // switching turns drops the previous run's rows
    if (conversationId && selected.sql) {
      void materialize(conversationId, selected.message_id, selected.sql).then(
        () => setStale(false),
        () => {
          // non-fatal — the SQL stays editable; rows are absent, so not stale
          setStale(false)
        },
      )
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected?.message_id])

  const canAct = Boolean(conversationId && selected && sql?.trim())
  const dirty = selected ? (sql ?? "").trim() !== (selected.sql ?? "").trim() : false

  const pin = React.useCallback(async () => {
    if (!canAct || !conversationId || !selected || !sql) return
    clearError()
    try {
      await workspaceApi.pinInsight(conversationId, {
        message_id: selected.message_id,
        revision_id: revisionId ?? "",
        sql,
        explanation: selected.explanation ?? undefined,
      })
      setPinned(true)
      onPinned()
    } catch (e) {
      note(e, "Could not pin.")
    }
  }, [canAct, conversationId, selected, revisionId, sql, onPinned, clearError, note])

  if (!selected) {
    return (
      <section aria-label="Workspace" className="flex h-full min-h-0 items-center justify-center p-8">
        <div className="max-w-[30ch] text-center">
          <h2 className="text-sm font-semibold tracking-tight">Workspace</h2>
          <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
            When a turn grounds in the data, its query and results land here. Edit the SQL,
            re-run it, and pin the result into the rail on the right.
          </p>
        </div>
      </section>
    )
  }

  return (
    <section aria-label="Workspace" className="flex h-full min-h-0 flex-col gap-4">
      <header className="flex items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold tracking-tight text-foreground">Workspace</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Edit the query, re-run it, pin the result.
          </p>
        </div>
        {dirty || error || stale ? (
          <Button
            variant="ghost"
            size="xs"
            onClick={() => {
              setSql(selected.sql ?? "")
              clearError()
              setStale(false)
            }}
          >
            <RotateCcw aria-hidden /> Reset to agent query
          </Button>
        ) : null}
      </header>

      <div className="relative">
        <textarea
          value={sql ?? ""}
          onChange={(e) => setSql(e.target.value)}
          spellCheck={false}
          rows={Math.min(9, Math.max(3, (sql ?? "").split("\n").length + 1))}
          className="w-full resize-y rounded-lg border border-input bg-background py-2.5 px-3 font-mono text-[0.8rem] leading-relaxed text-foreground/90 outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/40"
          placeholder="SELECT …"
        />
        <div className="absolute bottom-1.5 right-3 text-[0.65rem] font-medium uppercase tracking-wider text-muted-foreground">
          live · {revisionId ?? "rev-1"}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={() => void execute()} disabled={!canAct || running}>
          <RefreshCw className={running ? "size-3.5 animate-spin" : "size-3.5"} aria-hidden />
          {running ? "Re-running…" : "Re-run"}
        </Button>
        <Button onClick={() => void pin()} variant="secondary" disabled={!canAct || pinned}>
          <PinIcon className="size-3.5" aria-hidden /> {pinned ? "Pinned" : "Pin insight"}
        </Button>
        {flags.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {flags.map((f) => (
              <Badge key={f} variant="outline" className="text-xs">
                {f}
              </Badge>
            ))}
          </div>
        ) : null}
      </div>

      {error ? <ApiErrorBlock error={error} /> : null}

      <div className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-border bg-background/40 p-3">
        {stale && results ? (
          <div className="mb-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-foreground/90">
            <span className="font-medium">Last successful run.</span> Results from the last
            successful run — the query you edited is not what produced these rows.
          </div>
        ) : null}
        {results ? (
          <ResultsTable
            columns={results.columns}
            rows={results.rows}
            truncated={results.truncated}
            rowCap={results.row_cap}
          />
        ) : (
          <p className="py-8 text-center text-sm text-muted-foreground">No results yet — re-run to load rows.</p>
        )}
      </div>

      <div className="grid gap-2">
        <Card className="p-4">
          <CardTitle className="text-xs uppercase tracking-widest text-muted-foreground">
            Explanation
          </CardTitle>
          <CardContent className="mt-1.5 text-sm leading-relaxed text-foreground/90">
            {selected.explanation || "—"}
          </CardContent>
        </Card>
        {revisions.length > 0 ? (
          <Card className="p-4">
            <CardTitle className="text-xs uppercase tracking-widest text-muted-foreground">
              Revisions
            </CardTitle>
            <CardContent>
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                {revisions.map((r) => (
                  <Badge key={r.revision_id} variant={r.revision_id === revisionId ? "default" : "outline"}>
                    {r.revision_id}
                    <span className="ml-1 text-[0.6rem] uppercase tracking-wider opacity-70">
                      {r.source}
                    </span>
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        ) : null}
        {selected.assumptions.length > 0 ? (
          <Card className="p-4">
            <CardTitle className="text-xs uppercase tracking-widest text-muted-foreground">
              Assumptions
            </CardTitle>
            <CardContent>
              <ul className="mt-1.5 list-disc pl-4 text-sm text-foreground/90">
                {selected.assumptions.map((a, i) => (
                  <li key={i} className="leading-relaxed">
                    {a}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        ) : null}
      </div>
    </section>
  )
}

export { WorkspacePane }
