// The insights rail (Frame 1) + push-expand metrics panel (Frame 2).
// The seam (wireframes.html, decision (b)): "Draft rule" creates a rule from
// the pin; "Evaluate" then runs a backtest on that rule and push-expands the
// rail into the metrics panel (center narrows, no overlay).
import * as React from "react"
import { PanelRightClose, Pin as PinIcon, Wand2, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardTitle } from "@/components/ui/card"
import { StatCard, type Tone } from "@/components/ui/stat-card"
import { ResultsTable } from "@/components/ui/table"
import { api, ApiError } from "@/lib/http"
import type {
  BacktestResult,
  Insight,
  RuleStatus,
} from "@/lib/types"
import { rulesApi } from "../rules/api"

// P5: check if this insight carries a model-proposed rule.
function hasProposal(ins: Insight): boolean {
  return !!ins.rule_title && !!ins.rule_where_clause
}

// --- this feature's list/detail calls (insights are per-conversation) --------
const insightsApi = {
  list: (conversationId: string) =>
    api.get<{ items: Insight[] }>(`/conversations/${conversationId}/insights`).then((e) => e.items),
}

// --- format helpers -----------------------------------------------------------
const ratio = (x: number | undefined, digits = 3): string =>
  x === undefined || Number.isNaN(x) ? "—" : x.toFixed(digits)
const pct = (x: number | undefined, digits = 1): string =>
  x === undefined || Number.isNaN(x) ? "—" : `${(x * 100).toFixed(digits)}%`
const lift = (x: number | undefined): string =>
  x === undefined || Number.isNaN(x) ? "—" : `${x.toFixed(1)}×`
const metricTone = (precision: number, fpr: number): Tone =>
  precision > 0.8 && fpr < 0.1 ? "good" : precision > 0.4 ? "warn" : "bad"

// --- the expanded metrics panel (Frame 2) ------------------------------------
interface Evaluation {
  insight: Insight
  ruleId: string
  ruleStatus: RuleStatus
  result: BacktestResult
}

interface MetricsPanelProps {
  state: Evaluation
  onClose: () => void
  onVerb: () => void
}

function MetricsPanel({ state, onClose, onVerb }: MetricsPanelProps) {
  const [verbError, setVerbError] = React.useState<string | null>(null)
  const approve = React.useCallback(async () => {
    setVerbError(null)
    try {
      await rulesApi.approve(
        state.ruleId,
        `Backtest: precision ${ratio(state.result.labeled_only?.metrics?.precision)}, lift ${lift(state.result.labeled_only?.metrics?.lift)}.`,
      )
      onVerb()
    } catch (e) {
      setVerbError(e instanceof ApiError ? `${e.code} — ${e.message}` : "Approve failed.")
    }
  }, [state, onVerb])
  const reject = React.useCallback(async () => {
    setVerbError(null)
    try {
      await rulesApi.reject(
        state.ruleId,
        `Precision ${ratio(state.result.labeled_only?.metrics?.precision)} does not clear the bar.`,
      )
      onVerb()
    } catch (e) {
      setVerbError(e instanceof ApiError ? `${e.code} — ${e.message}` : "Reject failed.")
    }
  }, [state, onVerb])

  const lo = state.result.labeled_only
  const fu = state.result.full_universe
  if (!lo || !fu) {
    return <p className="text-sm text-muted-foreground">This backtest did not produce a full report.</p>
  }

  return (
    <div className="flex flex-col gap-4">
      <header className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-[0.65rem] font-medium uppercase tracking-widest text-muted-foreground">
            Metrics — <span className="lowercase">{state.ruleStatus}</span>
          </div>
          <div className="mt-1 line-clamp-2 break-words font-mono text-xs text-foreground/90" title={state.insight.sql ?? undefined}>
            {state.insight.sql}
          </div>
        </div>
        <Button variant="ghost" size="icon-xs" onClick={onClose} aria-label="Close panel">
          <X aria-hidden />
        </Button>
      </header>

      <div className="grid grid-cols-2 gap-2">
        <StatCard label="Precision" value={ratio(lo.metrics.precision)} fraction={lo.metrics.precision} tone={metricTone(lo.metrics.precision, lo.metrics.false_positive_rate)} caption="labeled universe" />
        <StatCard label="Recall" value={ratio(lo.metrics.recall)} fraction={lo.metrics.recall} tone={metricTone(lo.metrics.precision, lo.metrics.false_positive_rate)} caption="labeled universe" />
        <StatCard label="FPR" value={pct(lo.metrics.false_positive_rate)} fraction={lo.metrics.false_positive_rate} tone={lo.metrics.false_positive_rate < 0.1 ? "good" : "warn"} caption="labeled universe" />
        <StatCard label="Lift" value={lift(lo.metrics.lift)} caption="baseline-relative" />
      </div>

      <Card className="p-4">
        <CardTitle className="text-xs uppercase tracking-widest text-muted-foreground">
          Temporal stability
        </CardTitle>
        <CardContent>
          <div className="mt-3 flex items-center justify-between gap-3">
            <div>
              <div className="text-[0.65rem] uppercase tracking-widest text-muted-foreground">earlier slice</div>
              <div className="font-mono text-sm tabular-nums">
                P {ratio(state.result.temporal_stability?.earlier_slice?.precision)} · R {ratio(state.result.temporal_stability?.earlier_slice?.recall)}
              </div>
            </div>
            <div className="h-6 w-px bg-border" />
            <div className="text-right">
              <div className="text-[0.65rem] uppercase tracking-widest text-muted-foreground">later slice</div>
              <div className="font-mono text-sm tabular-nums">
                P {ratio(state.result.temporal_stability?.later_slice?.precision)} · R {ratio(state.result.temporal_stability?.later_slice?.recall)}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="p-4">
        <CardTitle className="text-xs uppercase tracking-widest text-muted-foreground">
          Eyeball the matches
        </CardTitle>
        <CardContent className="mt-2">
          <ResultsTable columns={state.result.sample.columns} rows={state.result.sample.rows} empty="No matched rows in the sample." />
          <div className="mt-2 text-xs text-muted-foreground">
            {lo.coverage.matched_count.toLocaleString()} match · out of {fu.coverage.total_rows.toLocaleString()} rows · {fu.coverage.total_fraud.toLocaleString()} fraud in basis
          </div>
        </CardContent>
      </Card>

      {verbError ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-foreground/90">
          <span className="font-medium text-destructive">Error.</span> {verbError}
        </div>
      ) : null}

      <div className="flex items-center gap-2">
        {state.ruleStatus === "backtested" ? (
          <>
            <Button onClick={() => void approve()}>Approve</Button>
            <Button variant="secondary" onClick={() => void reject()}>Reject</Button>
          </>
        ) : (
          <p className="text-xs text-muted-foreground">
            This rule is <code className="font-mono">{state.ruleStatus}</code> — only "backtested" rules can be approved or rejected.
          </p>
        )}
      </div>
    </div>
  )
}

// --- the rail (Frame 1 cards + Frame 2 expand) --------------------------------
export interface InsightsRailProps {
  conversationId: string | null
  expanded: boolean
  onToggleExpanded: (w: boolean) => void
  refreshKey?: string
}

function InsightsRail({ conversationId, expanded, onToggleExpanded, refreshKey }: InsightsRailProps) {
  const [insights, setInsights] = React.useState<Insight[]>([])
  const [ruleFor, setRuleFor] = React.useState<Record<string, { ruleId: string; status: RuleStatus }>>({})
  const [evaluating, setEvaluating] = React.useState<Evaluation | null>(null)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const load = React.useCallback(() => {
    if (!conversationId) {
      setInsights([])
      return
    }
    void insightsApi
      .list(conversationId)
      .then((items) => setInsights(items))
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load insights."))
  }, [conversationId])

  React.useEffect(() => void load(), [load, refreshKey])

  // Step 1 of (b): turn the insight into a draft rule (spec principle 5).
  const draftRule = React.useCallback(async (ins: Insight) => {
    setError(null)
    setBusy(true)
    try {
      const out = await rulesApi.draftRule(ins.insight_id, undefined)
      setRuleFor((m) => ({ ...m, [ins.insight_id]: { ruleId: out.rule_id, status: out.status } }))
    } catch (e) {
      setError(e instanceof ApiError ? `${e.code} — ${e.message}` : "Draft failed.")
    } finally {
      setBusy(false)
    }
  }, [])

  // Step 2 of (b): run the deterministic backtest and push-expand the rail.
  const evaluate = React.useCallback(async (ins: Insight) => {
    const existing = ruleFor[ins.insight_id]
    if (!existing) return
    setError(null)
    setBusy(true)
    try {
      const res = await rulesApi.backtest(existing.ruleId, "full")
      setEvaluating({ insight: ins, ruleId: existing.ruleId, ruleStatus: "backtested", result: res })
      onToggleExpanded(true)
    } catch (e) {
      setError(e instanceof ApiError ? `${e.code} — ${e.message}` : "Backtest failed.")
    } finally {
      setBusy(false)
    }
  }, [ruleFor, onToggleExpanded])

  const close = React.useCallback(() => {
    setEvaluating(null)
    onToggleExpanded(false)
  }, [onToggleExpanded])

  return (
    <aside
      aria-label="Insights"
      className="flex h-full min-h-0 flex-col gap-3 overflow-y-auto rounded-xl border border-border bg-background/40 p-3"
    >
      <header className="flex items-start justify-between gap-2">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-semibold tracking-tight">
            <PinIcon className="size-3.5" aria-hidden /> Insights
          </h2>
          <p className="mt-0.5 text-xs text-muted-foreground">Pin queries. Draft rules. Evaluate.</p>
        </div>
        <Button variant="ghost" size="icon-xs" onClick={() => onToggleExpanded(!expanded)} aria-label={expanded ? "Shrink rail" : "Expand rail"}>
          <PanelRightClose aria-hidden />
        </Button>
      </header>

      {error ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-foreground/90">
          <span className="font-medium text-destructive">Error.</span> {error}
        </div>
      ) : null}

      <div className="flex flex-col gap-2">
        {insights.length === 0 ? (
          <Card className="p-4">
            <CardContent className="text-xs leading-relaxed text-muted-foreground">
              No pinned queries yet. When you pin a query from the workspace, it shows up here and
              becomes a rule-ready card.
            </CardContent>
          </Card>
        ) : (
          insights.map((ins) => {
            const rule = ruleFor[ins.insight_id]
            const proposal = hasProposal(ins)
            return (
              <Card key={ins.insight_id} className="p-3">
                <CardContent className="flex flex-col gap-2">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex gap-1.5 items-center">
                      <Badge variant="secondary" className="text-[0.6rem] uppercase tracking-widest">
                        pinned
                      </Badge>
                      {proposal ? (
                        <Badge variant="default" className="text-[0.6rem] uppercase tracking-widest bg-amber-600 text-amber-50">
                          proposal
                        </Badge>
                      ) : null}
                    </div>
                    <span className="text-[0.65rem] text-muted-foreground">
                      {ins.created_at?.slice(0, 10) ?? ""}
                    </span>
                  </div>
                  {proposal ? (
                    <div className="flex flex-col gap-1">
                      <div className="text-xs font-medium" title={ins.rule_title ?? undefined}>
                        {ins.rule_title}
                      </div>
                      <div className="line-clamp-1 font-mono text-[0.65rem] text-foreground/70" title={ins.rule_where_clause ?? undefined}>
                        {ins.rule_where_clause}
                      </div>
                      {ins.rule_rationale ? (
                        <div className="line-clamp-2 text-[0.65rem] text-muted-foreground">{ins.rule_rationale}</div>
                      ) : null}
                    </div>
                  ) : ins.sql ? (
                    <div className="line-clamp-2 break-words font-mono text-xs text-foreground/90" title={ins.sql}>
                      {ins.sql}
                    </div>
                  ) : null}
                  <div className="flex gap-1.5">
                    {!rule ? (
                      <Button size="xs" onClick={() => void draftRule(ins)} disabled={busy}>
                        <Wand2 className="size-3" aria-hidden /> {busy ? "Drafting…" : "Draft rule"}
                      </Button>
                    ) : (
                      <>
                        <Badge variant="outline" className="text-xs">
                          <span className="mr-1 text-[0.6rem] uppercase tracking-widest opacity-70">
                            {rule.status}
                          </span>
                          rule
                        </Badge>
                        <Button size="xs" onClick={() => void evaluate(ins)} disabled={busy}>
                          <Wand2 className="size-3" aria-hidden /> {busy ? "Evaluating…" : "Evaluate"}
                        </Button>
                      </>
                    )}
                  </div>
                </CardContent>
              </Card>
            )
          })
        )}
      </div>

      {expanded ? (
        evaluating ? (
          <MetricsPanel state={evaluating} onClose={close} onVerb={() => load()} />
        ) : (
          <Card className="p-4">
            <CardTitle className="text-xs uppercase tracking-widest text-muted-foreground">
              Expand the rail
            </CardTitle>
            <CardContent className="mt-2 text-xs text-muted-foreground">
              Pick a card above: <strong className="font-medium">Draft rule</strong> turns the pinned
              SQL into a rule. <strong className="font-medium">Evaluate</strong> runs a
              deterministic backtest (no LLM — spec §7.4) and shows you the numbers on the right.
            </CardContent>
          </Card>
        )
      ) : null}
    </aside>
  )
}

export { InsightsRail }
