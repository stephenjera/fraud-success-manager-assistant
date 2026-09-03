// The workspace feature's API client (Gap H rerun + Gap B pin).
import { api } from "@/lib/http"
import type {
  Envelope,
  RerunResponse,
  Revision,
} from "@/lib/types"

export const workspaceApi = {
  // Synchronous deterministic re-execute of the (possibly edited) SQL (Gap H).
  rerun: (conversationId: string, messageId: string, s: string) =>
    api.post<RerunResponse>(
      `/conversations/${conversationId}/messages/${messageId}/rerun`,
      { sql: s },
    ),

  // The tuning history for a turn (rev-1 agent, rev-2+ reruns), newest first.
  revisions: (conversationId: string, messageId: string) =>
    api.get<Envelope<Revision>>(
      `/conversations/${conversationId}/messages/${messageId}/revisions`,
    ).then((e) => e.items),

  // Gap B — pin requires the revision id AND the exact sql the FSM looked at.
  pinInsight: (
    conversationId: string,
    body: { message_id: string; revision_id: string; sql: string; explanation?: string },
  ) => api.post<unknown>(`/conversations/${conversationId}/insights`, body),
}
