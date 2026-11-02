import type { ReactNode } from "react"
import type { LucideIcon } from "lucide-react"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { Card } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { classify, projectAnchor, STATUS_META } from "@/lib/status"
import type { Process } from "@/lib/types"
import { cn } from "@/lib/utils"

type StatCardProps = {
  label: string
  value: number | null
  icon: LucideIcon
  tone: string
  apps?: Process[]
}

export function StatCard({ label, value, icon: Icon, tone, apps }: StatCardProps) {
  const listed = value !== null && apps?.length ? apps : null

  const header = (trigger?: ReactNode) => (
    <div className="flex items-start justify-between gap-3 p-4 sm:p-5">
      <div className="min-w-0">
        <p className="text-[11px] font-medium tracking-[0.14em] text-muted-foreground uppercase">
          {label}
        </p>
        {value === null ? (
          <Skeleton className="mt-3 h-8 w-10" />
        ) : (
          <div className="mt-2 flex items-center gap-2.5">
            <p className="font-mono text-3xl font-semibold tabular-nums">{value}</p>
            {trigger}
          </div>
        )}
      </div>
      <span className={cn("grid size-9 shrink-0 place-items-center rounded-lg ring-1", tone)}>
        <Icon className="size-4" />
      </span>
    </div>
  )

  if (!listed) {
    return <Card className="gap-0 py-0">{header()}</Card>
  }

  return (
    <Card className="gap-0 py-0">
      <Accordion type="single" collapsible>
        <AccordionItem value="apps">
          {header(
            <AccordionTrigger className="flex-none items-center gap-1 rounded-full border-white/10 bg-white/[0.03] px-2 py-0.5 text-[11px] text-muted-foreground hover:bg-white/[0.06] hover:text-foreground hover:no-underline **:data-[slot=accordion-trigger-icon]:size-3">
              {listed.length === 1 ? "1 app" : `${listed.length} apps`}
            </AccordionTrigger>
          )}
          <AccordionContent className="px-4 pb-4 sm:px-5 sm:pb-5 [&_a]:no-underline">
            <ul className="grid grid-cols-1 gap-0.5 border-t border-white/[0.06] pt-3">
              {listed.map((p) => {
                const meta = STATUS_META[classify(p)]
                return (
                  <li key={p.name}>
                    <a
                      href={`#${projectAnchor(p.name)}`}
                      className="-mx-2 flex items-center gap-2 rounded-md px-2 py-1.5 transition-colors hover:bg-white/[0.04]"
                    >
                      <span className={cn("size-1.5 shrink-0 rounded-full", meta.dot)} />
                      <span className="min-w-0 flex-1 truncate font-mono text-xs" title={p.name}>
                        {p.name}
                      </span>
                      <span className="shrink-0 text-[10px] tracking-wider text-muted-foreground uppercase">
                        {meta.label}
                      </span>
                    </a>
                  </li>
                )
              })}
            </ul>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </Card>
  )
}
