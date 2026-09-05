// One error block, both panes. B9: the banner always speaks the contract —
// the server's own message, the offending SQL/clause it echoed, and a
// per-code "what next" hint. We never invent our own copy like "Re-run failed."
// (the message comes from e.message; we only add the offending echo + hint).
export interface ContractError {
  message: string
  code?: string | null
  offending?: string | null
}

const RETRY_HINT: Record<string, string> = {
  SQL_REJECTED: "Fix the SQL and re-run, or reset to the agent's query.",
  INTERNAL_ERROR: "The server failed. Try again.",
}

function ApiErrorBlock({ label = "Error.", error }: { label?: string; error: ContractError }) {
  return (
    <div className="space-y-1 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-foreground/90">
      <div>
        <span className="font-medium text-destructive">{label}</span> {error.message}
      </div>
      {error.offending ? (
        <div className="font-mono break-words text-foreground/80">
          <span className="text-[0.6rem] uppercase tracking-wider text-muted-foreground">
            offending:{" "}
          </span>
          {error.offending}
        </div>
      ) : null}
      {error.code ? (
        <div className="text-muted-foreground">{RETRY_HINT[error.code] ?? "The server returned an error. Try again."}</div>
      ) : null}
    </div>
  )
}

// Lift a thrown value into the block's shape. ApiError carries the
// {code, message, details}; anything else is a flat message.
export function toContractError(e: unknown, fallback: string, offendingKey: "offending_sql" | "offending_clause"): ContractError {
  if (e instanceof Error) {
    const err = e as Error & { code?: string; details?: unknown }
    const offending =
      ((err.details as Record<string, unknown> | null)?.[offendingKey] as string | undefined) ?? null
    if (err.code) {
      return { message: err.message || fallback, code: err.code, offending }
    }
  }
  return { message: fallback, code: null, offending: null }
}

export { ApiErrorBlock }
