// The one HTTP client for all features (ADR-0011: JSON everywhere, one error shape).
// CORS is pinned to this Vite dev origin (backend ORIGINS env), so cross-origin
// fetch is the path — no /api proxy prefix in the backend.

export const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined)
  ?? (import.meta.env.DEV ? "http://127.0.0.1:8000/v1" : `${window.location.origin}/v1`)

export class ApiError extends Error {
  code: string
  details: unknown | null
  status: number
  constructor(status: number, code: string, message: string, details: unknown | null) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.code = code
    this.details = details
  }
}

type Body = Record<string, unknown> | null

async function request<T>(
  path: string,
  options: { method?: string; body?: Body } = {},
): Promise<T> {
  const { method = "GET", body = null } = options
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: body !== null ? { "Content-Type": "application/json" } : undefined,
    body: body !== null ? JSON.stringify(body) : undefined,
  })

  if (!res.ok) {
    let code = "INTERNAL_ERROR"
    let message = res.status === 204 ? "Request failed" : `Request failed (${res.status})`
    let details: unknown | null = null
    try {
      const data = await res.json()
      if (data && typeof data === "object" && "error" in data) {
        const err = (data as { error: Record<string, unknown> }).error
        code = String(err.code ?? code)
        message = String(err.message ?? message)
        details = err.details ?? null
      }
    } catch {
      // non-JSON error body (e.g. 204/304); keep the string defaults
    }
    throw new ApiError(res.status, code, message, details)
  }

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: Body = null) => request<T>(path, { method: "POST", body }),
  patch: <T>(path: string, body: Body = null) => request<T>(path, { method: "PATCH", body }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
}

// SSE event names (frozen set, dotted — EventSource dispatches on these literally).
export type SseEventName =
  | "run.start"
  | "tool_call.start"
  | "tool_call.done"
  | "message.delta"
  | "insight.suggested"
  | "run.done"
  | "run.error"
  | "run.timeout"

export function eventsUrl(runId: string): string {
  return `${API_BASE}/runs/${runId}/events`
}
