// The Rule Workspace (Frame 3) — the rules list and the detail live in one
// component. The lifecycle is this feature's domain (ADR-0009); the detail
// drives the lifecycle verbs against the shared rulesApi.
//
// B5 (findings #1 + #14): a single `openId` state replaces the old
// `open` + `showDetail` pair — closing sets it to null, so re-clicking the
// same rule re-fetches and re-opens. A Backtest keeps the detail open on the
// updated rule (no view reset).
import * as React from "react"
import { ArrowLeft, Rocket, Search } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardTitle } from "@/components/ui/card"
import { ResultsTable } from "@/components/ui/table"
import { ApiError } from "@/lib/http"
import type { BacktestResult, RuleCard, RuleDetail, RuleStatus } from "@/lib/types"
import { rulesApi } from "./api"
import { cn } from "@/lib/utils"

const STATUS: (RuleStatus | "all")[] = ["all", "draft", "backtested", "approved", "deployed", "rejected"]

const ratio = (x: number | null | undefined): string =>
  x === null || x === undefined || Number.isNaN(x) ? "—" : x.toFixed(3)
const lift = (x: number | null | undefined): string =>
  x === null || x === undefined || Number.isNaN(x) ? "—" : `${x.toFixed(1)}×`

interface RuleWorkspaceProps {
  refreshKey?: string
}

function RuleDetailPane({
  rule,
  onClose,
  onUpdated,
}: {
  rule: RuleDetail
  onClose: () => void
  onUpdated: () => void
}) {
  const [verb, setVerb] = React.useState<{ running: string; error: string | null }>({
    running: "",
    error: null,
  })
  const [result, setResult] = React.useState<BacktestResult | null>(null)
  const [clause, setClause] = React.useState(rule.where_clause)
  const [savingClause, setSavingClause] = React.useState(false)
  const [clauseError, setClauseError] = React.useState<string | null>(null)
  const [clauseOffending, setClauseOffending] = React.useState<string | null>(null)

  // Keep the editor in sync with the server's clause: a fresh detail (after a
  // verb or a save) carries the canonical where_clause, so re-seed the draft.
  React.useEffect(() => {
    setClause(rule.where_clause)
    setClauseError(null)
    setClauseOffending(null)
  }, [rule.rule_id, rule.status, rule.where_clause])

  const saveClause = React.useCallback(async () => {
    setSavingClause(true)
    setClauseError(null)
    setClauseOffending(null)
    try {
      await rulesApi.patchWhereClause(rule.rule_id, clause)
      void onUpdated() // refetch detail in place; the re-seed effect syncs clause
    } catch (e) {
      if (e instanceof ApiError) {
        setClauseError(e.message)
        setClauseOffending((e.details as { offending_clause?: string } | null)?.offending_clause ?? null)
      } else {
        setClauseError("Could not save the clause.")
      }
    } finally {
      setSavingClause(false)
    }
  }, [rule.rule_id, clause, onUpdated])

  // Re-fetch the full two-universe report for a rule that has a backtest.
  const loadBacktest = React.useCallback(() => {
    const lb = rule.latest_backtest
    if (!lb) return
    let live = true
    rulesApi
      .getBacktest(rule.rule_id, lb.backtest_id)
      .then((r) => live && setResult(r))
      .catch(() => undefined)
    return () => {
      live = false
    }
    // ponytail: keyed on rule identity; the report refetches from `rule`
  }, [rule.rule_id, rule.latest_backtest])

  React.useEffect(() => {
    setResult(null)
    return loadBacktest()
  }, [loadBacktest])

  // A verb that moves the rule forward. Keep the detail open on the updated
  // rule: refetch the detail in place and refresh the list's statuses.
  const act = React.useCallback(
    async (label: string, fn: () => Promise<unknown>) => {
      setVerb({ running: label, error: null })
      try {
        // The verb has moved the rule; the parent refetches the detail in
        // place (keeping this open) and refreshes the list. The next effect
        // for the fresh `latest_backtest` refires to pull the report.
        await fn()
        setVerb({ running: "", error: null })
        void onUpdated()
      } catch (e) {
        setVerb({ running: "", error: e instanceof ApiError ? `${e.code} — ${e.message}` : `${label} failed.` })
      }
    },
    [onUpdated],
  )

  const lo = result?.labeled_only
  const fu = result?.full_universe

  return (
    <section aria-label="Rule detail" className="flex h-full min-h-0 flex-col gap-4 overflow-y-auto">
      <header className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[0.65rem] font-medium uppercase tracking-widest text-muted-foreground">
            <span>Rule</span>
            <Badge variant="secondary" className="text-[0.6rem]">{rule.status}</Badge>
          </div>
          <h2 className="mt-1 break-words text-base font-semibold tracking-tight">{rule.title}</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {rule.created_by} · {rule.created_at?.slice(0, 10) ?? ""}
          </p>
        </div>
        <Button variant="ghost" size="icon-xs" onClick={onClose} aria-label="Back to list">
          <ArrowLeft aria-hidden />
        </Button>
      </header>

      {rule.rationale ? (
        <Card className="p-4">
          <CardTitle className="text-xs uppercase tracking-widest text-muted-foreground">Why this rule</CardTitle>
          <CardContent className="mt-1.5 text-sm leading-relaxed text-foreground/90">{rule.rationale}</CardContent>
        </Card>
      ) : null}

      <Card className="p-4">
        <CardTitle className="text-xs uppercase tracking-widest text-muted-foreground">
          Detection rule
        </CardTitle>
        <CardContent className="mt-1.5 space-y-2">
          {/* B6: the clause is the rule. Editable while no backtest row
              exists (the freeze line, rule-lifecycle.md). Once any backtest
              is run the backend rejects a re-clause with 409, and we don't
              even send it. */}
          {rule.latest_backtest ? (
            <>
              <code className="block whitespace-pre-wrap break-words rounded-lg border border-border bg-background p-3 font-mono text-xs text-foreground/90">
                {clause}
              </code>
              <p className="text-xs text-muted-foreground">
                A backtest already exists against this clause. Re-draft from the insight to
                change it — the clause and the report that justified it travel together.
              </p>
            </>
          ) : (
            <>
              <textarea
                value={clause}
                onChange={(e) => setClause(e.target.value)}
                spellCheck={false}
                rows={Math.min(9, Math.max(3, clause.split("\n").length + 1))}
                className="w-full resize-y rounded-lg border border-input bg-background py-2.5 px-3 font-mono text-[0.8rem] leading-relaxed text-foreground/90 outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/40"
                placeholder="… WHERE …"
              />
              <div className="flex items-center gap-2">
                <Button size="sm" onClick={() => void saveClause()} disabled={savingClause}>
                  {savingClause ? "Saving…" : "Save clause"}
                </Button>
                <span className="text-[0.65rem] text-muted-foreground">
                  Editable while this rule is in <span className="font-mono">draft</span> with no
                  backtest. After a backtest, re-draft from the insight.
                </span>
              </div>
            </>
          )}

          {clauseError ? (
            <div className="space-y-1 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-foreground/90">
              <div>
                <span className="font-medium text-destructive">Clause rejected.</span> {clauseError}
              </div>
              {clauseOffending ? (
                <div className="font-mono break-words">
                  <span className="text-[0.65rem] uppercase tracking-wider text-muted-foreground">
                    offending clause:{" "}
                  </span>
                  {clauseOffending}
                </div>
              ) : null}
            </div>
          ) : null}
        </CardContent>
      </Card>

      {rule.provenance ? (
        <Card className="p-4">
          <CardTitle className="text-xs uppercase tracking-widest text-muted-foreground">
            Pinned from
          </CardTitle>
          <CardContent className="mt-1.5 overflow-x-auto rounded-lg border border-border bg-background p-3">
            <code className="whitespace-pre-wrap break-words font-mono text-xs text-foreground/90">
              {rule.provenance.sql}
            </code>
            <div className="mt-2 text-[0.65rem] text-muted-foreground">
              insight <span className="font-mono">{rule.provenance.source_insight_id}</span>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {rule.latest_backtest ? (
        <Card className="p-4">
          <CardTitle className="text-xs uppercase tracking-widest text-muted-foreground">
            Latest backtest · {rule.latest_backtest.window}
          </CardTitle>
          <CardContent className="mt-1.5">
            {lo && fu ? (
              <div className="grid grid-cols-4 gap-2">
                {[
                  ["Precision", ratio(lo.metrics.precision), "Share of flagged transactions that are actually fraud"],
                  ["Recall", ratio(lo.metrics.recall), "Share of real fraud the rule catches"],
                  ["FPR", ratio(lo.metrics.false_positive_rate), "Share of clean transactions the rule flags by mistake"],
                  ["Lift", lift(lo.metrics.lift), "How much better than the base fraud rate (1.0× = no signal)"],
                ].map(([k, v, cap]) => (
                  <div key={k} className="flex flex-col rounded-lg border border-border bg-background p-2 text-center">
                    <div className="text-[0.6rem] uppercase tracking-widest text-muted-foreground">{k}</div>
                    <div className="font-mono text-sm tabular-nums">{v}</div>
                    <div className="mt-1 leading-snug text-[0.6rem] text-muted-foreground">{cap}</div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                {rule.latest_backtest?.window ?? "full"} window · loading full report…
              </p>
            )}
            {lo && fu ? (
              <div className="mt-3">
                <div className="text-[0.6rem] uppercase tracking-widest text-muted-foreground">
                  Temporal stability
                </div>
                <div className="mt-1 grid grid-cols-2 gap-2">
                  <div className="rounded-lg border border-border bg-background px-3 py-2">
                    <div className="text-[0.6rem] text-muted-foreground">earlier slice</div>
                    <div className="font-mono text-sm tabular-nums">
                      P {ratio(result?.temporal_stability.earlier_slice.precision)} · R{" "}
                      {ratio(result?.temporal_stability.earlier_slice.recall)}
                    </div>
                  </div>
                  <div className="rounded-lg border border-border bg-background px-3 py-2">
                    <div className="text-[0.6rem] text-muted-foreground">later slice</div>
                    <div className="font-mono text-sm tabular-nums">
                      P {ratio(result?.temporal_stability.later_slice.precision)} · R{" "}
                      {ratio(result?.temporal_stability.later_slice.recall)}
                    </div>
                  </div>
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {result ? (
        <Card className="p-4">
          <CardTitle className="text-xs uppercase tracking-widest text-muted-foreground">
            Eyeball the matches
          </CardTitle>
          <CardContent className="mt-2">
            <ResultsTable
              columns={result.sample.columns}
              rows={result.sample.rows}
              empty="No matched rows in the sample."
            />
            {lo && fu ? (
              <div className="mt-2 text-xs text-muted-foreground">
                {lo.coverage.matched_count.toLocaleString()} match · out of{" "}
                {fu.coverage.total_rows.toLocaleString()} rows ·{" "}
                {fu.coverage.total_fraud.toLocaleString()} fraud in basis
              </div>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {verb.error ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-foreground/90">
          <span className="font-medium text-destructive">Error.</span> {verb.error}
        </div>
      ) : null}

      <div className="flex items-center gap-2">
        {rule.status === "draft" && (
          <Button onClick={() => void act("Backtest", () => rulesApi.backtest(rule.rule_id, "full"))} disabled={Boolean(verb.running)}>
            {verb.running === "Backtest" ? "Backtesting…" : "Backtest"}
          </Button>
        )}
        {rule.status === "backtested" && (
          <>
            <Button onClick={() => void act("Approve", () => rulesApi.approve(rule.rule_id, "Approved from the catalog."))} disabled={Boolean(verb.running)}>
              {verb.running === "Approve" ? "Approving…" : "Approve"}
            </Button>
            <Button variant="destructive" onClick={() => void act("Reject", () => rulesApi.reject(rule.rule_id, "Rejected from the catalog."))} disabled={Boolean(verb.running)}>
              {verb.running === "Reject" ? "Rejecting…" : "Reject"}
            </Button>
          </>
        )}
        {rule.status === "approved" && (
          <Button onClick={() => void act("Deploy", () => rulesApi.deploy(rule.rule_id))} disabled={Boolean(verb.running)}>
            <Rocket className="size-3.5" aria-hidden /> {verb.running === "Deploy" ? "Deploying…" : "Deploy"}
          </Button>
        )}
        {rule.status === "deployed" && (
          <p className="text-xs text-muted-foreground">
            Deployed at{" "}
            <time className="font-medium">
              {rule.deployment?.deployed_at
                ? new Date(rule.deployment.deployed_at).toLocaleString()
                : ""}
            </time>{" "}
            — external rule <code className="font-mono">{rule.deployment?.external_rule_id ?? "—"}</code>.
          </p>
        )}
        {rule.status === "rejected" && (
          <p className="text-xs text-muted-foreground">This rule was rejected{rule.rationale ? ` — ${rule.rationale}` : "."}</p>
        )}
      </div>
    </section>
  )
}

function RuleWorkspace({ refreshKey }: RuleWorkspaceProps) {
  const [status, setStatus] = React.useState<RuleStatus | "all">("all")
  const [rules, setRules] = React.useState<RuleCard[]>([])
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [openId, setOpenId] = React.useState<string | null>(null)
  const [detail, setDetail] = React.useState<RuleDetail | null>(null)

  const load = React.useCallback((s: RuleStatus | "all") => {
    setLoading(true)
    setError(null)
    rulesApi
      .list(s === "all" ? undefined : s)
      .then((items) => setRules(items))
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load rules."))
      .finally(() => setLoading(false))
  }, [])

  React.useEffect(() => {
    load(status)
  }, [status, load, refreshKey])

  // Single source of truth for "which rule is open". Closing sets it null;
  // re-clicking the same card sets it back, so the effect re-fetches.
  React.useEffect(() => {
    if (!openId) {
      setDetail(null)
      return
    }
    let live = true
    rulesApi
      .get(openId)
      .then((d) => live && setDetail(d))
      .catch((e) => {
        if (!live) return
        setError(e instanceof ApiError ? e.message : "Could not open this rule.")
        setOpenId(null)
      })
    return () => {
      live = false
    }
  }, [openId])

  if (openId && detail) {
    return (
      <RuleDetailPane
        rule={detail}
        onClose={() => setOpenId(null)}
        onUpdated={() => {
          // A lifecycle verb moved the rule. Refetch the detail in place (not
          // the whole view) so the new status and latest_backtest show; the
          // drawer's backtest effect refires for the fresh report. The list
          // refreshes so the card reflects the verb.
          rulesApi
            .get(openId)
            .then(setDetail)
            .catch((e) => setError(e instanceof ApiError ? e.message : "Could not reload this rule."))
          load(status)
        }}
      />
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-sm font-semibold tracking-tight text-foreground">Rule Catalog</h1>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Every rule, its state, and the verb that moves it forward.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1" role="tablist" aria-label="Filter by status">
          {STATUS.map((s) => (
            <button
              key={s}
              role="tab"
              aria-selected={status === s}
              onClick={() => setStatus(s)}
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-medium capitalize transition-colors",
                status === s
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-background text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              {s}
            </button>
          ))}
        </div>
      </header>

      {error ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-foreground/90">
          <span className="font-medium text-destructive">Error.</span> {error}
        </div>
      ) : null}

      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading && rules.length === 0 ? (
          <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
            <span className="size-3.5 animate-spin rounded-full border-2 border-muted-foreground/30 border-t-muted-foreground" />
            Loading rules…
          </div>
        ) : rules.length === 0 ? (
          <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
            <Search className="size-4" aria-hidden />
            No {status === "all" ? "" : `${status} `}rules yet.
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {rules.map((r) => (
              <button
                key={r.rule_id}
                onClick={() => setOpenId(r.rule_id)}
                className="group text-left"
              >
                <Card className="p-4 transition-shadow group-hover:shadow-md">
                  <div className="flex items-center justify-between gap-2">
                    <Badge variant="secondary" className="text-[0.6rem] uppercase tracking-widest">
                      {r.status}
                    </Badge>
                    <span className="text-[0.65rem] text-muted-foreground">{r.created_at?.slice(0, 10) ?? ""}</span>
                  </div>
                  <CardTitle className="line-clamp-2 text-sm">{r.title}</CardTitle>
                  <CardContent className="flex items-center gap-3 text-[0.7rem] text-muted-foreground">
                    <span>{r.backtests} backtest{r.backtests === 1 ? "" : "s"}</span>
                    <span>{r.deployments} deploy{r.deployments === 1 ? "" : "s"}</span>
                  </CardContent>
                </Card>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export { RuleWorkspace }
export type { RuleWorkspaceProps }
