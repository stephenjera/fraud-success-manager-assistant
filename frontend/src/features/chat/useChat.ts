// Chat session state (ADR-0009: owns its API calls + SSE stream + turn state).
// The stream is live activity; the durable fact is the message DTO (ADR-0011).
import { useCallback, useEffect, useRef, useState } from "react"

import type { ActivityItem, MessageStatus, SelectedQuery, Turn } from "@/lib/types"
import { chatApi, openRunEvents } from "./api"

// One query param, one history.replaceState per transition — no router (T8).
const conversationParam = (id: string | null): string =>
  new URLSearchParams(id ? { conversation: id } : {}).toString()
const setConversationUrl = (id: string | null) => {
  const qs = conversationParam(id)
  history.replaceState(null, "", qs ? `?${qs}` : location.pathname)
}

function pushTool(starts: Map<string, ActivityItem>, tool: string) {
  let item = starts.get(tool)
  if (!item) {
    item = { tool, phase: "start" }
    starts.set(tool, item)
  }
}
function sealTool(starts: Map<string, ActivityItem>, tool: string, summary?: string) {
  const item = starts.get(tool)
  if (item) {
    item.phase = "done"
    item.summary = summary
  } else {
    starts.set(tool, { tool, phase: "done", summary })
  }
}

export function useChat(onSelected?: (sel: SelectedQuery | null) => void) {
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [turns, setTurns] = useState<Turn[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const esRef = useRef<EventSource | null>(null)

  const patchTurn = useCallback((key: string, updater: (t: Turn) => Turn) => {
    setTurns((prev) => prev.map((t) => (t.key === key ? updater(t) : t)))
  }, [])

  const adoptMessage = useCallback(
    async (cid: string, messageId: string, key: string) => {
      const msg = await chatApi.getMessage(cid, messageId)
      const g = msg.grounding
      if (g) {
        patchTurn(key, (t) => ({
          ...t,
          message_id: msg.message_id,
          status: "success",
          grounding: g,
          text: g.explanation || t.text,
          error: null,
        }))
        onSelected?.({
          message_id: msg.message_id,
          status: "success",
          sql: g.sql,
          explanation: g.explanation ?? null,
          assumptions: g.assumptions ?? [],
          flags: g.flags ?? [],
          error: null,
        })
      } else {
        patchTurn(key, (t) => ({
          ...t,
          message_id: msg.message_id,
          status: (msg.status ?? "error") as MessageStatus,
          error: msg.error,
          text: t.text || msg.error?.message || "This turn did not ground in the data.",
          grounding: null,
        }))
        onSelected?.(null)
      }
    },
    [onSelected, patchTurn],
  )

  const send = useCallback(
    async (text: string) => {
      const q = text.trim()
      if (!q || busy) return
      setError(null)
      const asstKey = `a-${Date.now()}`
      setBusy(true)
      try {
        const userKey = `u-${Date.now()}`
        // Lazily create the conversation on the first question.
        const cid: string =
          conversationId ?? (await chatApi.createConversation()).conversation_id
        if (!conversationId) {
          setConversationId(cid)
          setConversationUrl(cid) // refresh can restore even a never-switched chat
        }
        setTurns((prev) => [
          ...prev,
          { key: userKey, role: "user", text: q },
          { key: asstKey, role: "assistant", text: "", status: "running" },
        ])

        const { message_id, run_id } = await chatApi.createTurn(cid, q)
        patchTurn(asstKey, (t) => ({ ...t, message_id, run_id }))

        const starts = new Map<string, ActivityItem>()
        const refresh = () =>
          patchTurn(asstKey, (t) => ({ ...t, activities: Array.from(starts.values()) }))

        const es = openRunEvents(run_id, {
          onToolStart: (tool) => {
            pushTool(starts, tool)
            refresh()
          },
          onToolDone: (tool, summary) => {
            sealTool(starts, tool, summary)
            refresh()
          },
          onTerminal: async (terminal) => {
            if (terminal === "error") {
              patchTurn(asstKey, (t) => ({ ...t, status: "error" }))
            }
            if (message_id) {
              try {
                await adoptMessage(cid, message_id, asstKey)
              } catch (e) {
                // Stream died and the durable read failed (e.g. backend gone).
                patchTurn(asstKey, (t) => ({
                  ...t,
                  status: "error",
                  error: {
                    code: "STREAM_LOST",
                    message: e instanceof Error ? e.message : "Connection lost.",
                  },
                  text: t.text || "Connection lost before the turn finished.",
                }))
                setError(e instanceof Error ? e.message : "Something went wrong.")
              }
            }
            setBusy(false)
          },
        })
        esRef.current = es
      } catch (e) {
        setError(e instanceof Error ? e.message : "Something went wrong.")
        patchTurn(asstKey, (t) => ({ ...t, status: "error", text: t.text || "Turn could not start." }))
        setBusy(false)
      }
    },
    [busy, conversationId, adoptMessage, patchTurn],
  )

  const newConversation = useCallback(() => {
    esRef.current?.close()
    setTurns([])
    setConversationId(null)
    setError(null)
    onSelected?.(null)
    setConversationUrl(null) // drop ?conversation= (non-destructive: rail lists it back)
  }, [onSelected])

  const selectConversation = useCallback(
    async (id: string) => {
      esRef.current?.close()
      setConversationId(id)
      setTurns([])
      setError(null)
      onSelected?.(null)
      setConversationUrl(id) // one ?conversation=<id>, refresh restores it
      try {
        const detail = await chatApi.getConversation(id)
        const loaded: Turn[] = []
        let latest: SelectedQuery | null = null
        for (const m of detail.messages ?? []) {
          if (!m.grounded) continue
          const dto = await chatApi.getMessage(id, m.message_id)
          if (!dto.grounding) continue
          loaded.push({
            key: `r-${dto.message_id}`,
            role: "assistant",
            message_id: dto.message_id,
            run_id: dto.run_id,
            status: "success",
            text: dto.grounding.explanation || "",
            grounding: dto.grounding,
          })
          latest = {
            message_id: dto.message_id,
            status: "success",
            sql: dto.grounding.sql,
            explanation: dto.grounding.explanation ?? null,
            assumptions: dto.grounding.assumptions ?? [],
            flags: dto.grounding.flags ?? [],
            error: null,
          }
        }
        setTurns(loaded)
        if (latest) onSelected?.(latest)
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not load this conversation.")
      }
    },
    [onSelected],
  )

  // On first mount, restore the conversation from ?conversation= (refresh /
  // direct link). Runs once; the select above also re-writes the same param.
  const restored = useRef(false)
  useEffect(() => {
    if (restored.current) return
    restored.current = true
    const id = new URLSearchParams(location.search).get("conversation")
    if (id) void selectConversation(id)
  }, [selectConversation])

  return { conversationId, turns, busy, error, send, newConversation, selectConversation }
}
