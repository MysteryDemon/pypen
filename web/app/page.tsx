"use client"

import { useState } from "react"
import { Activity, Boxes, CircleOff, LogOut, TriangleAlert } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { ConfirmDialog, type ConfirmRequest } from "@/components/confirm-dialog"
import { ProcessCard } from "@/components/process-card"
import { StatCard } from "@/components/stat-card"
import { useProcessFeed } from "@/hooks/use-process-feed"
import { groupByHealth } from "@/lib/status"

export default function DashboardPage() {
  const { processes, refresh } = useProcessFeed()
  const [confirm, setConfirm] = useState<ConfirmRequest | null>(null)

  const sorted = processes ?? []
  const health = groupByHealth(sorted)
  const loading = processes === null

  return (
    <div className="min-h-dvh">
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="outline"
            size="icon"
            className="fixed bottom-5 left-5 z-50 size-12 rounded-full text-muted-foreground shadow-lg shadow-black/80 hover:text-red-300 sm:bottom-6 sm:left-6 dark:border-white/15 dark:bg-black dark:hover:border-red-500/40 dark:hover:bg-red-950"
            asChild
          >
            <a href="/logout" aria-label="Logout">
              <LogOut className="size-5" />
            </a>
          </Button>
        </TooltipTrigger>
        <TooltipContent side="right">Logout</TooltipContent>
      </Tooltip>

      <main className="mx-auto max-w-7xl px-4 pt-6 pb-24 sm:px-6 sm:pt-8 lg:px-8">
        <section className="mb-8 grid grid-cols-2 items-start gap-3 lg:grid-cols-4 lg:gap-4">
          <StatCard
            label="Projects"
            value={loading ? null : sorted.length}
            icon={Boxes}
            tone="bg-white/[0.04] text-zinc-300 ring-white/10"
          />
          <StatCard
            label="Running"
            value={loading ? null : health.running.length}
            icon={Activity}
            tone="bg-emerald-400/10 text-emerald-400 ring-emerald-400/20"
          />
          <StatCard
            label="Offline"
            value={loading ? null : health.offline.length}
            icon={CircleOff}
            tone="bg-white/[0.04] text-zinc-400 ring-white/10"
            apps={health.offline}
          />
          <StatCard
            label="Failed"
            value={loading ? null : health.failed.length}
            icon={TriangleAlert}
            tone="bg-red-500/10 text-red-400 ring-red-500/20"
            apps={health.failed}
          />
        </section>

        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-[23rem] rounded-xl bg-white/[0.04]" />
            ))}
          </div>
        ) : sorted.length === 0 ? (
          <Card className="items-center border border-dashed border-white/10 bg-transparent py-16 text-center ring-0">
            <span className="grid size-12 place-items-center rounded-xl bg-white/[0.04] ring-1 ring-white/10">
              <Boxes className="size-5 text-muted-foreground" />
            </span>
            <div className="space-y-1">
              <p className="font-medium">No projects registered</p>
              <p className="text-sm text-muted-foreground">
                Add a <code className="font-mono text-foreground">[[project]]</code> entry to
                project.toml and it will show up here.
              </p>
            </div>
          </Card>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {sorted.map((p) => (
              <ProcessCard key={p.name} process={p} confirm={setConfirm} onChanged={refresh} />
            ))}
          </div>
        )}
      </main>

      <ConfirmDialog request={confirm} onClose={() => setConfirm(null)} />
    </div>
  )
}
