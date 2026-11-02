export type Process = {
  name: string
  status: string
  pid: string | number | null
  uptime: string | null
  paused: boolean
  auto_paused?: boolean
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
