// The shell (B2): four strips, no view switch.
//   Conversations | Chat + Pinned insights | Workspace | Rule workspace
// The insights rail is a section of the conversation column (its metrics and
// lifecycle verbs live in the rule workspace). One refreshKey keeps the
// derived panes (insights, rules list) honest after a pin / draft / verb.
import * as React from "react"

import type { SelectedQuery, Turn } from "@/lib/types"
import { ChatPane } from "@/features/chat/ChatPane"
import { useChat } from "@/features/chat/useChat"
import { WorkspacePane } from "@/features/workspace/WorkspacePane"
import { InsightsRail } from "@/features/insights/rail"
import { RuleWorkspace } from "@/features/rules/workspace"
import { ConversationsRail } from "@/features/conversations/rail"

function App() {
  const [selected, setSelected] = React.useState<SelectedQuery | null>(null)
  const [refreshKey, setRefreshKey] = React.useState(0)
  const bump = React.useCallback(() => setRefreshKey((k) => k + 1), [])

  const { conversationId, turns, busy, error, send, newConversation, selectConversation } =
    useChat(setSelected)

  // B10: a grounded turn clicked in the transcript drives the workspace to
  // that turn's grounding (the "older turn" case; the auto-follow path
  // already resets the workspace when a newer turn grounds).
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
      <header className="flex shrink-0 items-center border-b border-border px-4 py-2">
        <span className="text-sm font-semibold tracking-tight">Fraud Insight &amp; Rule Copilot</span>
      </header>

      <div className="flex min-h-0 flex-1">
        <ConversationsRail
          activeId={conversationId}
          onSelect={selectConversation}
          onNew={newConversation}
          refreshKey={String(refreshKey)}
        />

        <div className="flex h-full w-96 min-h-0 shrink-0 flex-col overflow-hidden border-r border-border">
          <div className="min-h-0 flex-[3] overflow-hidden">
            <ChatPane turns={turns} busy={busy} error={error} onSend={send} onSelect={selectTurn} />
          </div>
          <div className="min-h-0 flex-[2] overflow-hidden border-t border-border bg-background/40">
            <InsightsRail
              conversationId={conversationId}
              refreshKey={String(refreshKey)}
              onRuleAction={bump}
            />
          </div>
        </div>

        <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden border-r border-border bg-background/40">
          <WorkspacePane conversationId={conversationId} selected={selected} onPinned={bump} />
        </div>

        <div className="flex h-full w-[520px] min-h-0 shrink-0 flex-col overflow-hidden bg-background/40">
          <RuleWorkspace refreshKey={String(refreshKey)} />
        </div>
      </div>
    </div>
  )
}

export default App
