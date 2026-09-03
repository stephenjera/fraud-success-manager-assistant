import { cn } from "@/lib/utils"

// A stat-card is the instrument cluster the design lives on: an eyebrow label,
// a big tabular number, and a thin baseline bar whose *width is the value*
// (0–1). That encodes the metric's magnitude instead of decorating it.
type Tone = "neutral" | "good" | "warn" | "bad"

const barTone: Record<Tone, string> = {
  neutral: "bg-primary/60",
  good: "bg-[oklch(0.62_0.13_160)]",
  warn: "bg-[oklch(0.72_0.16_70)]",
  bad: "bg-destructive",
}

interface StatCardProps {
  label: string
  value: string | number
  unit?: string
  // 0..1 (clamped) — the share the bar fills. Omit for non-ratio metrics.
  fraction?: number
  tone?: Tone
  caption?: string
  className?: string
}

function StatCard({
  label,
  value,
  unit,
  fraction,
  tone = "neutral",
  caption,
  className,
}: StatCardProps) {
  const pct = fraction === undefined ? 0 : Math.max(0, Math.min(1, fraction)) * 100
  return (
    <div className={cn("flex flex-col justify-between gap-2 rounded-xl border border-border bg-card px-4 py-3", className)}>
      <div>
        <div className="text-[0.65rem] font-medium uppercase tracking-[0.14em] text-muted-foreground">
          {label}
        </div>
        <div className="mt-1 flex items-baseline gap-1">
          <span className="font-mono text-3xl font-semibold leading-none tabular-nums tracking-tight">
            {value}
          </span>
          {unit ? <span className="text-sm text-muted-foreground">{unit}</span> : null}
        </div>
      </div>
      {caption ? (
        <div className="text-xs text-muted-foreground">{caption}</div>
      ) : fraction !== undefined ? (
        <div className="h-[3px] w-full overflow-hidden rounded-full bg-muted">
          <div
            className={cn("h-full rounded-full transition-[width] duration-300", barTone[tone])}
            style={{ width: `${pct}%` }}
          />
        </div>
      ) : null}
    </div>
  )
}

export { StatCard, type Tone }
