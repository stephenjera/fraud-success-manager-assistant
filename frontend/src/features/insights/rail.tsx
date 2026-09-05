// The pinned-insights section inside the conversation panel (T8 step 4).
//
// Reduced from the old push-expand metric panel: the "Draft rule" and
// "Evaluate" verbs moved to the rule workspace (they are rule lifecycle
// operations, not insight operations — the rail no longer owns backtest
// reports). What stays here is: "which pinned insights exist, and for each,
// do we already have a rule?" A "Draft rule" button creates one (bumping the
// rule workspace's refreshKey); a "View rule" badge tells the FSM a rule already
// exists (same refresh-bump so the workspace shows the latest state).
import * as React from "react"

import { Pin as PinIcon, Wand2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { api } from "@/lib/http"
import type { Insight, RuleStatus } from "@/lib/types"
import { rulesApi } from "../rules/api"
import { ApiErrorBlock, toContractError, type ContractError } from "@/lib/error-block"
import { cn } from "@/lib/utils"

// P5: check if this insight carries a model-proposed rule.
function hasProposal(ins: Insight): boolean {
  return Boolean(ins.rule_title && ins.rule_where_clause)
}

const insightsApi = {
  list: (conversationId: string) =>
    api.get<{ items: Insight[] }>(`/conversations/${conversationId}/insights`).then((e) => e.items),
}

export interface InsightsRailProps {
  conversationId: string | null
  refreshKey?: string
  onRuleAction?: () => void // bumps the rule workspace refreshKey
}

function InsightsRail({ conversationId, refreshKey, onRuleAction }: InsightsRailProps) {
  const [insights, setInsights] = React.useState<Insight[]>([])
  const [ruleFor, setRuleFor] = React.useState<Record<string, { ruleId: string; status: RuleStatus }>>({})
  const [error, setError] = React.useState<ContractError | null>(null)
  const [busyId, setBusyId] = React.useState<string | null>(null)

  const load = React.useCallback(() => {
    if (!conversationId) {
      setInsights([])
      return
    }
    void insightsApi
      .list(conversationId)
      .then((items) => {
        setInsights(items)
        // Seed rule-for map from any insight that already carries a rule.
        const map: Record<string, { ruleId: string; status: RuleStatus }> = {}
        for (const ins of items) {
          if (ins.rule_count && ins.rule_count > 0) {
            map[ins.insight_id] = { ruleId: "", status: "draft" }
          }
        }
        setRuleFor((prev) => ({ ...prev, ...map }))
      })
      .catch((e) => setError(toContractError(e, "Could not load insights.", "offending_sql")))
  }, [conversationId])

  React.useEffect(() => {
    load()
  }, [load, refreshKey])

  const draftRule = React.useCallback(
    async (ins: Insight) => {
      setBusyId(ins.insight_id)
      setError(null)
      try {
        const out = await rulesApi.draftRule(ins.insight_id, undefined)
        setRuleFor((m) => ({ ...m, [ins.insight_id]: { ruleId: out.rule_id, status: out.status } }))
        onRuleAction?.() // workspace list refreshes; FSM opens the new rule from there
      } catch (e) {
        setError(toContractError(e, "Could not draft a rule for this insight.", "offending_sql"))
      } finally {
        setBusyId(null)
      }
    },
    [onRuleAction],
  )

  return (
    <section aria-label="Pinned insights" className="flex h-full min-h-0 flex-col gap-3 p-3">
      <header className="flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold tracking-tight">
          <PinIcon className="size-3.5" aria-hidden /> Pinned insights
        </h2>
      </header>

      {error ? <ApiErrorBlock error={error} /> : null}

      {insights.length === 0 ? (
        <Card className="p-4">
          <CardContent className="text-xs leading-relaxed text-muted-foreground">
            No pinned queries yet. Pin one from the workspace and "Draft rule" turns it into a
            candidate for backtest.
          </CardContent>
        </Card>
      ) : (
        <ul className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto pr-1">
          {insights.map((ins) => {
            const rule = ruleFor[ins.insight_id]
            const proposal = hasProposal(ins)
            const busy = busyId === ins.insight_id
            return (
              <li key={ins.insight_id}>
                <Card className={cn("p-3", rule && "border-primary/40 bg-primary/5")}>
                  <CardContent className="flex flex-col gap-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5">
                        <Badge variant="secondary" className="text-[0.6rem] uppercase tracking-widest">
                          pinned
                        </Badge>
                        {proposal ? (
                          <Badge
                            variant="default"
                            className="text-[0.6rem] uppercase tracking-widest bg-amber-600 text-amber-50"
                          >
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
                        <div className="line-clamp-2 break-words text-xs font-medium" title={ins.rule_title ?? undefined}>
                          {ins.rule_title}
                        </div>
                        {ins.rule_where_clause ? (
                          <div
                            className="line-clamp-1 font-mono text-[0.65rem] text-foreground/70"
                            title={ins.rule_where_clause ?? undefined}
                          >
                            {ins.rule_where_clause}
                          </div>
                        ) : null}
                      </div>
                    ) : ins.sql ? (
                      <div
                        className="line-clamp-2 break-words font-mono text-xs text-foreground/90"
                        title={ins.sql}
                      >
                        {ins.sql}
                      </div>
                    ) : null}

                    <div className="mt-1 flex items-center gap-2">
                      {rule ? (
                        <>
                          <Badge variant="outline" className="text-xs">
                            <span className="mr-1 text-[0.6rem] uppercase tracking-widest opacity-70">
                              {rule.status}
                            </span>
                            rule
                          </Badge>
                          <Button
                            size="xs"
                            variant="ghost"
                            className="text-xs"
                            onClick={() => onRuleAction?.()}
                          >
                            View in workspace
                          </Button>
                        </>
                      ) : (
                        <Button
                          size="xs"
                          onClick={() => void draftRule(ins)}
                          disabled={busy}
                        >
                          <Wand2 className="size-3" aria-hidden /> {busy ? "Drafting…" : "Draft rule"}
                        </Button>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

export { InsightsRail }
