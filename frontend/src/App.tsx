// The shell: a top bar to switch between the three-pane workbench and the
// Rule Catalog (spec §13 keeps the catalog a separate view). The Frame 1 ↔ 2
// swap lives in the rail: when a rule's metrics panel is expanded, the rail
// column widens — the center workspace narrows (center narrows, not overlays).
import * as React from "react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { SelectedQuery, Turn } from "@/lib/types"
import { ChatPane } from "@/features/chat/ChatPane"
import { useChat } from "@/features/chat/useChat"
import { WorkspacePane } from "@/features/workspace/WorkspacePane"
import { InsightsRail } from "@/features/insights/rail"
import { RuleWorkspace } from "@/features/rules/workspace"

type View = "workbench" | "catalog"

function App() {
  const [view, setView] = React.useState<View>("workbench")
  const [selected, setSelected] = React.useState<SelectedQuery | null>(null)
  const [railWide, setRailWide] = React.useState(false) // Frame 2 (metrics panel)
  const [insightsKey, setInsightsKey] = React.useState(0)

  const {
    conversationId,
    turns,
    busy,
    error,
    send,
    newConversation,
  } = useChat(setSelected)

  // B10: a grounded chat turn clicked in the transcript drives the workspace
  // to that turn's grounding. (The auto-follow path already resets the
  // workspace when a newer turn grounds; this is the "older turn" case.)
  const selectTurn = (t: Turn) => {
    if (!t.grounding) return
    setSelected({
      message_id: t.message_id ?? "",
      status: t.status ?? "success",
      sql: t.grounding.sql,
      explanation: t.grounding.explanation ?? null,
      assumptions: t.grounding.assumptions ?? [],
      flags: t.grounding.flags ?? [],
      error: t.error ?? null,
    })
  }

  return (
    <div className="flex h-svh flex-col bg-background text-foreground">
      <header className="flex items-center justify-between gap-3 border-b border-border px-4 py-2.5">
        <span className="text-sm font-semibold tracking-tight">Fraud Insight &amp; Rule Copilot</span>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-0.5 rounded-lg border border-border p-0.5" role="tablist" aria-label="Views">
            {(["workbench", "catalog"] as const).map((v) => (
              <button
                key={v}
                role="tab"
                aria-selected={view === v}
                onClick={() => setView(v)}
                className={cn(
                  "rounded-md px-3 py-1 text-xs font-medium transition-colors",
                  view === v
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                {v === "workbench" ? "Workbench" : "Rules Catalog"}
              </button>
            ))}
          </div>
          {view === "workbench" ? (
            <Button
              variant="ghost"
              size="xs"
              onClick={() => {
                newConversation()
                setSelected(null)
                setRailWide(false)
              }}
            >
              New chat
            </Button>
          ) : null}
        </div>
      </header>

      <div className="min-h-0 flex-1 gap-3 p-3">
        {view === "workbench" ? (
          <main className="flex h-full min-h-0" aria-label="Workbench">
            <section className="flex h-full w-[340px] shrink-0 flex-col overflow-hidden rounded-xl border border-border bg-background/40">
              <ChatPane turns={turns} busy={busy} error={error} onSend={send} onSelect={selectTurn} />
            </section>

            <section className="flex h-full min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-border bg-background/40">
              <WorkspacePane
                conversationId={conversationId}
                selected={selected}
                onPinned={() => setInsightsKey((k) => k + 1)}
              />
            </section>

            <section
              aria-hidden={!railWide}
              className={cn(
                "flex h-full shrink-0 flex-col overflow-hidden rounded-xl border border-border bg-background/40 transition-[width] duration-200",
                railWide ? "w-[520px]" : "w-[320px]",
              )}
            >
              <InsightsRail
                conversationId={conversationId}
                expanded={railWide}
                onToggleExpanded={setRailWide}
                refreshKey={String(insightsKey)}
              />
            </section>
          </main>
        ) : (
          <RuleWorkspace refreshKey={String(insightsKey)} />
        )}
      </div>
    </div>
  )
}

export default App
