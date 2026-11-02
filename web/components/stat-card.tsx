import type { LucideIcon } from "lucide-react"
import { Card } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

type StatCardProps = {
  label: string
  value: number | null
  icon: LucideIcon
  /** Icon chip colours. */
  tone: string
}

export function StatCard({ label, value, icon: Icon, tone }: StatCardProps) {
  return (
    <Card className="gap-0 py-0">
      <div className="flex items-start justify-between gap-3 p-4 sm:p-5">
        <div className="min-w-0">
          <p className="text-[11px] font-medium tracking-[0.14em] text-muted-foreground uppercase">
            {label}
          </p>
          {value === null ? (
            <Skeleton className="mt-3 h-8 w-10" />
          ) : (
            <p className="mt-2 font-mono text-3xl font-semibold tabular-nums">{value}</p>
          )}
        </div>
        <span className={cn("grid size-9 shrink-0 place-items-center rounded-lg ring-1", tone)}>
          <Icon className="size-4" />
        </span>
      </div>
    </Card>
  )
}
