"use client"

import { useState, type ReactNode } from "react"
import {
  Download,
  LoaderCircle,
  OctagonX,
  Pause,
  Play,
  RefreshCcw,
  RotateCw,
  SquareTerminal,
} from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { CpuSparkline } from "@/components/cpu-sparkline"
import type { ConfirmRequest } from "@/components/confirm-dialog"
import { api, openLogStream } from "@/lib/api"
import { classify, projectAnchor, STATUS_META } from "@/lib/status"
import type { ActionResult, Process } from "@/lib/types"
import { cn } from "@/lib/utils"

type ProcessCardProps = {
  process: Process
  confirm: (request: ConfirmRequest) => void
  onChanged: () => void
}

export function ProcessCard({ process, confirm, onChanged }: ProcessCardProps) {
  const [busy, setBusy] = useState<string | null>(null)
  const { name } = process
  const kind = classify(process)
  const meta = STATUS_META[kind]

  const isRunning = process.status === "RUNNING"
  const isAutoPaused = !!process.auto_paused
  const isDegraded = isAutoPaused || kind === "warning"

  async function run(key: string, task: () => Promise<ActionResult>, fallback: string) {
    setBusy(key)
    try {
      const result = await task()
      toast.success(result.message || fallback)
    } catch (err) {
      toast.error(`${name}: ${(err as Error).message}`)
    } finally {
      setBusy(null)
      onChanged()
    }
  }

  const start = () => run("start", () => api.action("start", name), `Started ${name}`)
  const pause = () => run("pause", () => api.action("pause", name), `Paused ${name}`)
  const resume = () => run("resume", () => api.action("resume", name), `Resumed ${name}`)
  const restart = () =>
    confirm({
      title: `Restart ${name}?`,
      description:
        "Stops the service, clears its logs, pulls new commits if pull_commits is on, and starts it again.",
      confirmLabel: "Restart",
      onConfirm: () => run("restart", () => api.action("restart", name), `Restarted ${name}`),
    })
  const stop = () =>
    confirm({
      title: `Stop ${name}?`,
      description: "The service will be taken down until you start it again.",
      confirmLabel: "Stop",
      destructive: true,
      onConfirm: () => run("stop", () => api.action("stop", name), `Stopped ${name}`),
    })
  const clearFailure = () =>
    confirm({
      title: `Clear failure state for ${name}?`,
      description: "Resets the failure counter and asks s6 to bring the service back up.",
      confirmLabel: "Clear failure",
      destructive: true,
      onConfirm: () => run("clear", () => api.clearFailure(name), `Cleared failure state for ${name}`),
    })
  const redeploy = () =>
    confirm({
      title: `Redeploy ${name}?`,
      description:
        "This will stop the service, wipe its workdir + venv cache, git-pull the latest commit, " +
        "reinstall dependencies from scratch, and bring the service back up.\n\nThis action cannot be undone.",
      confirmLabel: "Redeploy",
      destructive: true,
      onConfirm: () => {
        openLogStream(name)
        run("redeploy", () => api.redeploy(name), `Redeployed ${name}`)
      },
    })
  const downloadLog = async () => {
    setBusy("log")
    try {
      await api.downloadLog(name)
    } catch (err) {
      toast.error(`${name}: ${(err as Error).message}`)
    } finally {
      setBusy(null)
    }
  }

  const disabled = busy !== null
  const icon = (key: string, idle: ReactNode) =>
    busy === key ? <LoaderCircle className="animate-spin" /> : idle

  let primary: ReactNode
  if (isAutoPaused) {
    primary = (
      <Button variant="destructive" onClick={clearFailure} disabled={disabled}>
        {icon("clear", <OctagonX />)} Critical Stop
      </Button>
    )
  } else if (isRunning && isDegraded) {
    primary = (
      <Button variant="destructive" onClick={stop} disabled={disabled}>
        {icon("stop", <OctagonX />)} Critical Stop
      </Button>
    )
  } else if (isRunning && process.paused) {
    primary = (
      <Button className={START_STYLE} onClick={resume} disabled={disabled}>
        {icon("resume", <Play />)} Resume
      </Button>
    )
  } else if (isRunning) {
    primary = (
      <Button variant="outline" onClick={pause} disabled={disabled}>
        {icon("pause", <Pause />)} Pause
      </Button>
    )
  } else {
    primary = (
      <Button className={START_STYLE} onClick={start} disabled={disabled}>
        {icon("start", <Play />)} Start
      </Button>
    )
  }

  return (
    <Card
      id={projectAnchor(name)}
      className={cn(
        "scroll-mt-6 gap-0 py-0 transition-shadow duration-300 target:ring-2 target:ring-white/40",
        meta.card
      )}
    >
      <div className="p-5">
        <div className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2.5">
            <span className={cn("size-2 shrink-0 rounded-full", meta.dot)} />
            <h3 className="truncate font-semibold tracking-tight" title={name}>
              {name}
            </h3>
          </div>
          <Badge className={cn("text-[10px] tracking-wider uppercase ring-1", meta.badge)}>
            {meta.label}
          </Badge>
        </div>

        <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-4">
          <Field label="Uptime" value={process.uptime} mono />
          <Field label="PID" value={process.pid} mono />
          <Field label="Status" value={process.status} />
          <Field label="CPU" value={process.cpu == null ? null : `${process.cpu.toFixed(1)}%`} mono />
        </dl>

        <CpuSparkline samples={process.cpu_history ?? []} tone={meta.spark} className="mt-4" />
      </div>

      <div className="grid grid-cols-2 gap-2 border-t border-white/[0.06] bg-white/[0.015] p-3">
        {primary}
        <Button variant="outline" onClick={restart} disabled={disabled || (!isRunning && !isAutoPaused)}>
          {icon("restart", <RotateCw />)} Restart
        </Button>
        <Button variant="outline" onClick={redeploy} disabled={disabled}>
          {icon("redeploy", <RefreshCcw />)} Redeploy
        </Button>
        <Button variant="outline" onClick={() => openLogStream(name)}>
          <SquareTerminal /> Stream logs
        </Button>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              className="col-span-2 text-muted-foreground"
              onClick={downloadLog}
              disabled={disabled}
            >
              {icon("log", <Download />)} Debug logs
            </Button>
          </TooltipTrigger>
          <TooltipContent>Download the full s6 log file</TooltipContent>
        </Tooltip>
      </div>
    </Card>
  )
}

const START_STYLE = "bg-emerald-400 text-black hover:bg-emerald-300"

function Field({
  label,
  value,
  mono,
}: {
  label: string
  value: ReactNode
  mono?: boolean
}) {
  return (
    <div className="min-w-0">
      <dt className="text-[10px] font-medium tracking-[0.14em] text-muted-foreground uppercase">
        {label}
      </dt>
      <dd className={cn("mt-1 truncate text-sm font-medium", mono && "font-mono tabular-nums")}>
        {value || "—"}
      </dd>
    </div>
  )
}
