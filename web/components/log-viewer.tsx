"use client"

import { useEffect, useLayoutEffect, useRef, useState } from "react"
import { useSearchParams } from "next/navigation"
import { ArrowDownToLine, ArrowLeft, Download, Eraser, LoaderCircle, WrapText } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Toggle } from "@/components/ui/toggle"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"

const MAX_LINES = 5000
const FLUSH_MS = 60

type LineKind = "sys" | "err" | "warn" | "out"
type Line = { id: number; text: string; kind: LineKind }
type StreamState = "connecting" | "streaming" | "retrying" | "closed"

const LINE_STYLE: Record<LineKind, string> = {
  sys: "text-zinc-500 italic",
  err: "text-red-400",
  warn: "text-amber-300",
  out: "text-zinc-300",
}

const STREAM_META: Record<StreamState, { label: string; dot: string }> = {
  connecting: { label: "connecting…", dot: "bg-zinc-500" },
  streaming: { label: "streaming", dot: "bg-emerald-400 shadow-[0_0_8px_var(--color-emerald-400)] animate-pulse" },
  retrying: { label: "disconnected — retrying…", dot: "bg-amber-400" },
  closed: { label: "stream closed", dot: "bg-red-500" },
}

function kindOf(text: string): LineKind {
  if (text.startsWith("[stream]")) return "sys"
  if (/\b(error|exception|traceback|critical|fatal)\b/i.test(text)) return "err"
  if (/\bwarn(ing)?\b/i.test(text)) return "warn"
  return "out"
}

export function LogViewer() {
  const name = useSearchParams().get("name") ?? ""
  const [lines, setLines] = useState<Line[]>([])
  const [stream, setStream] = useState<StreamState>("connecting")
  const [follow, setFollow] = useState(true)
  const [wrap, setWrap] = useState(true)
  const [downloading, setDownloading] = useState(false)
  const bodyRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!name) return
    let nextId = 0
    let buffer: Line[] = []
    let timer: ReturnType<typeof setTimeout> | null = null

    const flush = () => {
      timer = null
      const batch = buffer
      buffer = []
      setLines((prev) => {
        const next = prev.concat(batch)
        return next.length > MAX_LINES ? next.slice(-MAX_LINES) : next
      })
    }
    const push = (text: string, kind: LineKind = kindOf(text)) => {
      buffer.push({ id: nextId++, text, kind })
      if (buffer.length > MAX_LINES) buffer = buffer.slice(-MAX_LINES)
      timer ??= setTimeout(flush, FLUSH_MS)
    }

    push(`$ tail -f /var/log/s6/${name.replace(/ /g, "_")}/current`, "sys")
    const source = new EventSource(`/service/stream/${encodeURIComponent(name)}`)
    source.onopen = () => setStream("streaming")
    source.onmessage = (event) => push(event.data)
    source.onerror = () => {
      if (source.readyState === EventSource.CLOSED) {
        setStream("closed")
        api.status().catch(() => {})
      } else {
        setStream("retrying")
      }
    }

    return () => {
      source.close()
      if (timer) clearTimeout(timer)
      setLines([])
      setStream("connecting")
    }
  }, [name])

  useLayoutEffect(() => {
    const el = bodyRef.current
    if (follow && el) el.scrollTop = el.scrollHeight
  }, [lines, follow, wrap])

  const onScroll = () => {
    const el = bodyRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 24
    if (atBottom !== follow) setFollow(atBottom)
  }

  const download = async () => {
    setDownloading(true)
    try {
      await api.downloadLog(name)
    } catch (err) {
      toast.error((err as Error).message)
    } finally {
      setDownloading(false)
    }
  }

  if (!name) {
    return (
      <main className="grid min-h-dvh place-items-center px-4 text-center">
        <title>Live logs · Pypen</title>
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">No process selected.</p>
          <Button variant="outline" asChild>
            <a href="/">
              <ArrowLeft /> Back to dashboard
            </a>
          </Button>
        </div>
      </main>
    )
  }

  const meta = STREAM_META[stream]
  return (
    <div className="relative flex h-dvh flex-col bg-black font-mono text-[13px]">
      <title>{`${name} · live logs`}</title>
      <header className="flex shrink-0 flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-white/[0.08] px-3 py-2 sm:px-4">
        <div className="flex min-w-0 items-center gap-2.5">
          <Button variant="ghost" size="icon-sm" className="text-muted-foreground" asChild>
            <a href="/" aria-label="Back to dashboard">
              <ArrowLeft />
            </a>
          </Button>
          <span className={cn("size-2 shrink-0 rounded-full", meta.dot)} />
          <span className="truncate font-sans font-semibold">{name}</span>
          <Badge className="bg-emerald-400/10 text-[10px] tracking-wider text-emerald-300 uppercase ring-1 ring-emerald-400/25">
            live
          </Badge>
        </div>
        <div className="flex items-center gap-1 font-sans">
          <Toggle
            size="sm"
            pressed={follow}
            onPressedChange={setFollow}
            aria-label="Follow new lines"
            className="data-[state=on]:bg-emerald-400/10 data-[state=on]:text-emerald-300"
          >
            <ArrowDownToLine /> <span className="hidden sm:inline">Follow</span>
          </Toggle>
          <Toggle
            size="sm"
            pressed={wrap}
            onPressedChange={setWrap}
            aria-label="Wrap long lines"
            className="data-[state=on]:bg-emerald-400/10 data-[state=on]:text-emerald-300"
          >
            <WrapText /> <span className="hidden sm:inline">Wrap</span>
          </Toggle>
          <Button variant="ghost" size="sm" onClick={() => setLines([])}>
            <Eraser /> <span className="hidden sm:inline">Clear</span>
          </Button>
          <Button variant="ghost" size="sm" onClick={download} disabled={downloading}>
            {downloading ? <LoaderCircle className="animate-spin" /> : <Download />}
            <span className="hidden sm:inline">Download</span>
          </Button>
        </div>
      </header>

      <div
        ref={bodyRef}
        onScroll={onScroll}
        aria-live="polite"
        className={cn(
          "min-h-0 flex-1 overflow-auto px-4 py-3 leading-relaxed",
          wrap ? "break-words whitespace-pre-wrap" : "whitespace-pre"
        )}
      >
        {lines.map((line) => (
          <div key={line.id} className={LINE_STYLE[line.kind]}>
            {line.text || " "}
          </div>
        ))}
      </div>

      {!follow && (
        <Button
          size="sm"
          className="absolute right-4 bottom-12 font-sans shadow-lg"
          onClick={() => setFollow(true)}
        >
          <ArrowDownToLine /> Jump to latest
        </Button>
      )}

      <footer className="flex shrink-0 items-center justify-between gap-2 border-t border-white/[0.08] px-4 py-1.5 text-[11px] text-muted-foreground">
        <span>
          {lines.length.toLocaleString()} line{lines.length === 1 ? "" : "s"}
          {lines.length >= MAX_LINES && ` · showing last ${MAX_LINES.toLocaleString()}`}
        </span>
        <span>{meta.label}</span>
      </footer>
    </div>
  )
}
