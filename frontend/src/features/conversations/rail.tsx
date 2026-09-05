// The conversations rail (left pane of the three-pane shell, B3). One entry
// per conversation, "New chat" on top, the active one highlighted. "New chat"
// is non-destructive because every previous conversation stays reachable by
// clicking it (B4). No per-conversation peek: the title is count + date, which
// is all the rail needs and keeps the list cheap on every refresh.
import * as React from "react"

import { MessageSquare, PanelLeftClose, Plus } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { Conversation } from "@/lib/types"
import { chatApi } from "../chat/api"

export interface ConversationsRailProps {
  activeId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  refreshKey?: string
}

const fmtDay = (iso: string | undefined): string => {
  if (!iso) return ""
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" })
  } catch {
    return ""
  }
}

function ConversationsRail({ activeId, onSelect, onNew, refreshKey }: ConversationsRailProps) {
  const [items, setItems] = React.useState<Conversation[]>([])
  const [loading, setLoading] = React.useState(false)

  React.useEffect(() => {
    let live = true
    setLoading(true)
    chatApi
      .listConversations()
      .then((cs) => {
        if (live)
          setItems(
            [...cs].sort((a, b) =>
              (b.last_active || b.created_at || "").localeCompare(a.last_active || a.created_at || ""),
            ),
          )
      })
      .catch(() => {
        if (live) setItems([])
      })
      .finally(() => live && setLoading(false))
    return () => {
      live = false
    }
  }, [refreshKey])

  return (
    <section
      aria-label="Conversations"
      className="flex h-full w-60 shrink-0 flex-col gap-3 border-r border-border bg-background/40 p-3"
    >
      <header className="flex items-center justify-between gap-2">
        <div>
          <h1 className="text-sm font-semibold tracking-tight">Conversations</h1>
          <p className="mt-0.5 text-xs text-muted-foreground">Previous chats stay reachable.</p>
        </div>
        <Button variant="ghost" size="icon-xs" aria-label="New chat" onClick={onNew}>
          <Plus aria-hidden />
        </Button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading && items.length === 0 ? (
          <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
            <span className="size-3.5 animate-spin rounded-full border-2 border-muted-foreground/30 border-t-muted-foreground" />
            Loading…
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-16 text-center text-sm text-muted-foreground">
            <PanelLeftClose className="size-4" aria-hidden />
            No conversations yet.
          </div>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {items.map((c) => {
              const active = c.conversation_id === activeId
              return (
                <li key={c.conversation_id}>
                  <button
                    type="button"
                    onClick={() => onSelect(c.conversation_id)}
                    aria-current={active ? "true" : undefined}
                    className={cn(
                      "flex w-full flex-col gap-1 rounded-lg border px-3 py-2 text-left transition-colors",
                      active
                        ? "border-primary bg-primary/10 text-foreground"
                        : "border-border bg-background text-muted-foreground hover:bg-muted hover:text-foreground",
                    )}
                  >
                    <span className="flex items-center gap-1.5 text-sm font-medium">
                      <MessageSquare className="size-3.5 shrink-0" aria-hidden />
                      <span className="min-w-0 flex-1 truncate">{c.message_count} message{c.message_count === 1 ? "" : "s"}</span>
                    </span>
                    <span className="flex items-center gap-1.5 pl-5 text-[0.65rem]">
                      <Badge
                        variant={active ? "default" : "outline"}
                        className="h-4 px-1.5 text-[0.55rem] uppercase tracking-widest"
                      >
                        {active ? "active" : fmtDay(c.last_active) || fmtDay(c.created_at)}
                      </Badge>
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </section>
  )
}

export { ConversationsRail }
