import { cn } from "@/lib/utils"
import type { Connection } from "@/hooks/use-process-feed"

const META: Record<Connection, { label: string; dot: string; text: string }> = {
  live: { label: "Live", dot: "bg-emerald-400", text: "text-emerald-300" },
  polling: { label: "Polling", dot: "bg-amber-400", text: "text-amber-300" },
  connecting: { label: "Connecting…", dot: "bg-zinc-500", text: "text-muted-foreground" },
  offline: { label: "Offline", dot: "bg-red-500", text: "text-red-300" },
}

export function ConnectionPill({ connection }: { connection: Connection }) {
  const meta = META[connection]
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full bg-white/[0.03] px-2.5 py-1 text-xs font-medium ring-1 ring-white/[0.08]",
        meta.text
      )}
      role="status"
    >
      <span className="relative flex size-2">
        {connection === "live" && (
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-60" />
        )}
        <span className={cn("relative inline-flex size-2 rounded-full", meta.dot)} />
      </span>
      {meta.label}
    </span>
  )
}
