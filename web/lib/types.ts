/** One s6 service as reported by `/service/status` and the `status_update` event. */
export type Process = {
  name: string
  /** RUNNING | STOPPED | BACKOFF | FATAL | PENDING | UNKNOWN */
  status: string
  pid: string | number | null
  uptime: string | null
  paused: boolean
  auto_paused?: boolean
  /** Percent of the whole machine, or null when not sampled. */
  cpu: number | null
  cpu_history: number[]
}

export type StatusPayload = {
  status: "success" | "error"
  processes?: Process[]
  message?: string
  timestamp?: string
}

export type ActionResult = {
  status: "success" | "error"
  message?: string
}
