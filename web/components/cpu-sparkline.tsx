import { useId } from "react"
import { cn } from "@/lib/utils"

const W = 100
const H = 32
const PAD = 2

/**
 * CPU history (0–100 %) as an area chart. The scale follows the recent peak
 * (never below 20 %) so a steady 5–20 % load still has visible shape.
 */
export function CpuSparkline({
  samples,
  tone,
  className,
}: {
  samples: number[]
  /** Text colour class; the chart draws in `currentColor`. */
  tone?: string
  className?: string
}) {
  const gradientId = `spark-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`

  if (samples.length < 2) {
    return (
      <div
        className={cn(
          "grid h-14 place-items-center rounded-lg bg-white/[0.02] text-[11px] text-muted-foreground ring-1 ring-white/[0.06]",
          className
        )}
      >
        no samples yet
      </div>
    )
  }

  const values = samples.map((v) => Math.max(0, Math.min(100, Number(v) || 0)))
  const top = Math.min(100, Math.max(20, Math.max(...values) * 1.25))
  const step = W / (values.length - 1)
  const points = values.map((v, i) => [i * step, PAD + (1 - v / top) * (H - PAD * 2)] as const)
  const line = points
    .map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`)
    .join(" ")
  const area = `${line} L${W},${H} L0,${H} Z`

  return (
    <div
      className={cn(
        "relative h-14 overflow-hidden rounded-lg bg-white/[0.02] ring-1 ring-white/[0.06]",
        tone,
        className
      )}
    >
      <span className="absolute top-1.5 right-2 font-mono text-[10px] text-muted-foreground tabular-nums">
        {Math.round(top)}%
      </span>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="size-full" aria-hidden="true">
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="currentColor" stopOpacity="0.32" />
            <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
          </linearGradient>
        </defs>
        <line
          x1="0" x2={W} y1={H / 2} y2={H / 2}
          stroke="white" strokeOpacity="0.06" strokeDasharray="2 2"
          vectorEffect="non-scaling-stroke"
        />
        <path d={area} fill={`url(#${gradientId})`} />
        <path
          d={line}
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    </div>
  )
}
