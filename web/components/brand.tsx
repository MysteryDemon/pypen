import { cn } from "@/lib/utils"

export function PypenMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" className={className}>
      <path d="M12 2 3 7v10l9 5 9-5V7l-9-5Zm0 2.3 6.6 3.7v7.9L12 19.7 5.4 15.9V8Zm-1 4.7h2v7.3h-2V9Zm4 2h2v1.5a2 2 0 0 1-2 2v-3.5Z" />
    </svg>
  )
}

export function BrandBadge({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "grid size-8 shrink-0 place-items-center rounded-lg bg-emerald-400/10 text-emerald-400 ring-1 ring-emerald-400/25",
        className
      )}
    >
      <PypenMark className="size-[60%]" />
    </span>
  )
}

export function Brand() {
  return (
    <a href="/" className="flex items-center gap-2.5">
      <BrandBadge />
      <span className="text-sm font-semibold tracking-[0.22em]">PYPEN</span>
    </a>
  )
}
