import type { Process } from "@/lib/types"

export type StatusKind = "running" | "warning" | "failed" | "paused" | "pending" | "offline"

export function classify(p: Process): StatusKind {
  if (p.auto_paused) return "failed"
  if (p.paused) return "paused"
  if (p.status === "RUNNING") return "running"
  if (p.status === "PENDING") return "pending"
  if (p.status === "BACKOFF" || p.status === "FATAL") return "warning"
  return "offline"
}

type StatusMeta = {
  label: string
  dot: string
  badge: string
  card: string
  spark: string
}

export const STATUS_META: Record<StatusKind, StatusMeta> = {
  running: {
    label: "Running",
    dot: "bg-emerald-400 shadow-[0_0_10px_var(--color-emerald-400)]",
    badge: "bg-emerald-400/10 text-emerald-300 ring-emerald-400/25",
    card: "ring-emerald-400/20 hover:ring-emerald-400/35",
    spark: "text-emerald-400",
  },
  warning: {
    label: "Retry",
    dot: "bg-amber-400 shadow-[0_0_10px_var(--color-amber-400)]",
    badge: "bg-amber-400/10 text-amber-300 ring-amber-400/25",
    card: "ring-amber-400/25 hover:ring-amber-400/40",
    spark: "text-amber-400",
  },
  failed: {
    label: "Failed",
    dot: "bg-red-500 shadow-[0_0_10px_var(--color-red-500)]",
    badge: "bg-red-500/10 text-red-300 ring-red-500/30",
    card: "ring-red-500/30 hover:ring-red-500/45",
    spark: "text-red-400",
  },
  paused: {
    label: "Paused",
    dot: "bg-zinc-400",
    badge: "bg-zinc-400/10 text-zinc-300 ring-zinc-400/20",
    card: "ring-white/10 hover:ring-white/20",
    spark: "text-zinc-400",
  },
  pending: {
    label: "Pending",
    dot: "bg-sky-400 animate-pulse",
    badge: "bg-sky-400/10 text-sky-300 ring-sky-400/25",
    card: "ring-sky-400/15 hover:ring-sky-400/30",
    spark: "text-sky-400",
  },
  offline: {
    label: "Offline",
    dot: "bg-zinc-600",
    badge: "bg-zinc-500/10 text-zinc-400 ring-zinc-500/20",
    card: "ring-white/10 hover:ring-white/20",
    spark: "text-zinc-500",
  },
}

export function groupByHealth(processes: Process[]) {
  const running: Process[] = []
  const offline: Process[] = []
  const failed: Process[] = []
  for (const p of processes) {
    const kind = classify(p)
    if (kind === "running") running.push(p)
    else if (kind === "failed" || kind === "warning") failed.push(p)
    else offline.push(p)
  }
  return { running, offline, failed }
}

export function projectAnchor(name: string) {
  return `project-${name.replace(/\s+/g, "_")}`
}
