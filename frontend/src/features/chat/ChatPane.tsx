// The chat pane — transcript, live activity, composer.
import * as React from "react"
import { ArrowUp, Sparkles } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { ActivityItem, Turn } from "@/lib/types"

function ProposalCard({ turn }: { turn: Turn }) {
  const p = turn.grounding?.rule_proposal
  if (!p) return null
  return (
    <div className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2.5 text-xs">
      <div className="flex items-center gap-1.5">
        <Badge variant="default" className="text-[0.6rem] uppercase tracking-widest bg-amber-600 text-amber-50">
          rule proposal
        </Badge>
        <span className="font-medium">{p.title}</span>
      </div>
      <div className="mt-1 font-mono text-[0.65rem] text-foreground/70" title={p.where_clause}>{p.where_clause}</div>
      {p.rationale ? <div className="mt-1.5 text-muted-foreground leading-relaxed">{p.rationale}</div> : null}
      {p.assumptions?.length ? (
        <div className="mt-1.5 text-muted-foreground">Assumes: {p.assumptions.join(", ")}</div>
      ) : null}
    </div>
  )
}

function ActivityRow({ item }: { item: ActivityItem }) {
  return (
    <div className="flex items-start gap-2 text-xs leading-tight">
      <span
        className={cn(
          "mt-0.5 inline-block size-1.5 shrink-0 rounded-full",
          item.phase === "start"
            ? "animate-pulse bg-amber-500"
            : "bg-emerald-500",
        )}
      />
      <span className="min-w-0 flex-1">
        <span className="font-mono text-foreground">{item.tool}</span>
        {item.summary ? (
          <span className="block truncate text-muted-foreground">↳ {item.summary}</span>
        ) : null}
      </span>
      <span
        className={cn(
          "shrink-0 text-[0.65rem] uppercase tracking-wider",
          item.phase === "start" ? "text-amber-600" : "text-emerald-600",
        )}
      >
        {item.phase === "start" ? "running" : "done"}
      </span>
    </div>
  )
}

function TurnRow({ turn }: { turn: Turn }) {
  if (turn.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm text-primary-foreground">
          {turn.text}
        </div>
      </div>
    )
  }
  const running = turn.status === "running"
  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-2xl rounded-tl-md border border-border bg-card p-4 shadow-sm">
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-[0.6rem] uppercase tracking-widest">
            assistant
          </Badge>
          {running ? (
            <span className="text-xs text-muted-foreground" aria-live="polite">
              querying database…
            </span>
          ) : null}
        </div>
        {running ? (
          <div className="mt-3 flex flex-col gap-2">
            {(turn.activities ?? []).length === 0 ? (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span className="inline-block size-2 animate-pulse rounded-full bg-amber-500" />
                warming up…
              </div>
            ) : null}
            {(turn.activities ?? []).map((a, i) => (
              <ActivityRow key={i} item={a} />
            ))}
          </div>
        ) : null}
        {turn.error ? (
          <div className="mt-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm">
            <div className="font-medium text-destructive">{turn.error.code}</div>
            <div className="text-foreground/80">{turn.error.message}</div>
          </div>
        ) : null}
        {turn.text ? (
          <div className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">
            {turn.text}
          </div>
        ) : null}
        <ProposalCard turn={turn} />
        {(turn.grounding?.flags ?? []).length > 0 ? (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {(turn.grounding?.flags ?? []).map((f) => (
              <Badge key={f} variant="outline" className="text-xs">
                {f}
              </Badge>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  )
}

export interface ChatPaneProps {
  turns: Turn[]
  busy: boolean
  error: string | null
  onSend: (text: string) => void
}

function ChatPane({ turns, busy, error, onSend }: ChatPaneProps) {
  const [draft, setDraft] = React.useState("")
  const scrollerRef = React.useRef<HTMLDivElement>(null)

  React.useEffect(() => {
    const el = scrollerRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" })
  }, [turns])

  const sendNow = () => {
    const t = draft.trim()
    if (!t || busy) return
    setDraft("")
    onSend(t)
  }

  return (
    <section aria-label="Chat" className="flex h-full min-h-0 flex-col gap-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles className="size-4 text-foreground/60" />
            <h2 className="text-sm font-semibold tracking-tight text-foreground">Chat</h2>
          </div>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Ask, and the query lands in the workspace in the middle.
          </p>
        </div>
      </div>

      <div
        ref={scrollerRef}
        className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-border bg-background/40 p-3 text-sm"
      >
        {turns.length === 0 ? (
          <div className="flex h-full min-h-[150px] items-center justify-center p-6 text-center text-sm leading-relaxed text-muted-foreground">
            <div className="max-w-[26ch]">
              A good starter:
              <div className="mt-2 font-mono text-xs text-foreground/70">
                “How many transactions exceeded $1,000 last 30 days?”
              </div>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {turns.map((t) => (
              <TurnRow key={t.key} turn={t} />
            ))}
          </div>
        )}
      </div>

      {error ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-foreground/90">
          <span className="font-medium text-destructive">Error.</span> {error}
        </div>
      ) : null}

      <form className="flex items-end gap-2" onSubmit={(e) => { e.preventDefault(); sendNow() }}>
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault()
              sendNow()
            }
          }}
          placeholder='Type a question about the reference data…'
          rows={2}
          className="min-h-16 flex-1 resize-none rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/40"
        />
        <Button type="submit" size="icon-lg" disabled={busy || !draft.trim()} aria-label="Send">
          <ArrowUp aria-hidden />
        </Button>
      </form>
    </section>
  )
}

export { ChatPane }
