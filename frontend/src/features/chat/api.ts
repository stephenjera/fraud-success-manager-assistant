// The chat feature's API client (ADR-0009: owns its area's calls).
import { api, eventsUrl } from "@/lib/http"
import type {
  Conversation,
  ConversationDetail,
  Envelope,
  MessageDto,
  Revision,
} from "@/lib/types"

export const chatApi = {
  listConversations: () =>
    api.get<Envelope<Conversation>>("/conversations").then((e) => e.items),

  getConversation: (id: string) =>
    api.get<ConversationDetail>(`/conversations/${id}`),

  createConversation: () =>
    api.post<{ conversation_id: string; created_at: string }>("/conversations"),

  deleteConversation: (id: string) => api.del<void>(`/conversations/${id}`),

  createTurn: (conversationId: string, text: string) =>
    api.post<{ message_id: string; run_id: string; status: string }>(
      `/conversations/${conversationId}/messages`,
      { text },
    ),

  getMessage: (conversationId: string, messageId: string) =>
    api.get<MessageDto>(`/conversations/${conversationId}/messages/${messageId}`),

  listRevisions: (conversationId: string, messageId: string) =>
    api.get<Envelope<Revision>>(
      `/conversations/${conversationId}/messages/${messageId}/revisions`,
    ).then((e) => e.items),
}

// The frozen SSE event set, as EventSource listeners. Returns the EventSource
// so the caller can close it. A terminal event (run.done / run.error /
// run.timeout) fires onTerminal — the stream is not "keep-alive", it ends.
export function openRunEvents(
  runId: string,
  handlers: {
    onToolStart?: (tool: string) => void
    onToolDone?: (tool: string, summary: string) => void
    onDelta?: (delta: string) => void
    onTerminal?: (terminal: "done" | "error" | "timeout", detail?: unknown) => void
  },
): EventSource {
  const es = new EventSource(eventsUrl(runId))

  const json = (e: MessageEvent): Record<string, unknown> => {
    try {
      return JSON.parse(e.data as string) as Record<string, unknown>
    } catch {
      return {}
    }
  }

  es.addEventListener("tool_call.start", (raw) => {
    const p = json(raw as MessageEvent)
    handlers.onToolStart?.(String(p.tool ?? "tool"))
  })
  es.addEventListener("tool_call.done", (raw) => {
    const p = json(raw as MessageEvent)
    handlers.onToolDone?.(String(p.tool ?? "tool"), String(p.result_summary ?? ""))
  })
  es.addEventListener("message.delta", (raw) => {
    const p = json(raw as MessageEvent)
    handlers.onDelta?.(String(p.delta ?? ""))
  })
  let settled = false
  const fireTerminal = (t: "done" | "error" | "timeout", detail?: unknown) => {
    if (settled) return
    settled = true
    es.close()
    handlers.onTerminal?.(t, detail)
  }
  es.addEventListener("run.done", (raw) => fireTerminal("done", json(raw as MessageEvent)))
  es.addEventListener("run.error", (raw) => fireTerminal("error", json(raw as MessageEvent)))
  es.addEventListener("run.timeout", (raw) => fireTerminal("timeout", json(raw as MessageEvent)))
  es.onerror = () => {
    // Stream ended without a terminal frame — treat as an error so the UI settles.
    fireTerminal("error", { reason: "stream closed" })
  }

  return es
}
