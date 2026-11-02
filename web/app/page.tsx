"use client"

import { useState } from "react"
import { Activity, Boxes, CircleOff, LogOut, TriangleAlert } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Brand } from "@/components/brand"
import { ConfirmDialog, type ConfirmRequest } from "@/components/confirm-dialog"
import { ConnectionPill } from "@/components/connection-pill"
import { ProcessCard } from "@/components/process-card"
import { StatCard } from "@/components/stat-card"
import { useProcessFeed } from "@/hooks/use-process-feed"
import { summarize } from "@/lib/status"

export default function DashboardPage() {
  const { processes, connection, refresh } = useProcessFeed()
  const [confirm, setConfirm] = useState<ConfirmRequest | null>(null)

  const sorted = processes ?? []
  const stats = summarize(sorted)
  const loading = processes === null

  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-40 border-b border-white/[0.06] bg-black/75 backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between gap-3 px-4 sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <Brand />
            <ConnectionPill connection={connection} />
          </div>
          <div className="flex items-center gap-2">
            {!loading && (
              <Badge variant="outline" className="hidden font-mono text-muted-foreground sm:inline-flex">
                {stats.total} project{stats.total === 1 ? "" : "s"}
              </Badge>
            )}
            <Button variant="ghost" size="sm" className="text-muted-foreground" asChild>
              <a href="/logout">
                <LogOut /> Logout
              </a>
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
        <section className="mb-8 grid grid-cols-2 gap-3 lg:grid-cols-4 lg:gap-4">
          <StatCard
            label="Projects"
            value={loading ? null : stats.total}
            icon={Boxes}
            tone="bg-white/[0.04] text-zinc-300 ring-white/10"
          />
          <StatCard
            label="Running"
            value={loading ? null : stats.running}
            icon={Activity}
            tone="bg-emerald-400/10 text-emerald-400 ring-emerald-400/20"
          />
          <StatCard
            label="Offline"
            value={loading ? null : stats.offline}
            icon={CircleOff}
            tone="bg-white/[0.04] text-zinc-400 ring-white/10"
          />
          <StatCard
            label="Failed"
            value={loading ? null : stats.failed}
            icon={TriangleAlert}
            tone="bg-red-500/10 text-red-400 ring-red-500/20"
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
