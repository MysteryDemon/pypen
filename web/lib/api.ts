import type { ActionResult, StatusPayload } from "@/lib/types"

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number
  ) {
    super(message)
  }
}

function goToLogin() {
  if (window.location.pathname !== "/login") window.location.replace("/login")
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: "same-origin",
    ...init,
    headers: { Accept: "application/json", ...init?.headers },
  })
  if (res.status === 401) {
    goToLogin()
    throw new ApiError("Your session has expired.", 401)
  }
  const data = await res.json().catch(() => null)
  if (!res.ok || data?.status === "error") {
    throw new ApiError(data?.message || `Request failed (HTTP ${res.status})`, res.status)
  }
  return data as T
}

const svc = (name: string) => encodeURIComponent(name)

export type ServiceAction = "start" | "stop" | "restart" | "pause" | "resume"

export const api = {
  status: () => request<StatusPayload>("/service/status"),

  action: (verb: ServiceAction, name: string) =>
    request<ActionResult>(`/service/${verb}/${svc(name)}`, { method: "POST" }),

  clearFailure: (name: string) =>
    request<ActionResult>(`/service/clear_failure/${svc(name)}`, { method: "POST" }),

  redeploy: (name: string) =>
    request<ActionResult>(`/service/redeploy/${svc(name)}`, { method: "POST" }),

  login: async (username: string, password: string) => {
    const res = await fetch("/auth/login", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ username, password }),
    })
    const data: ActionResult | null = await res.json().catch(() => null)
    if (!res.ok || data?.status !== "success") {
      throw new ApiError(data?.message || "Login failed.", res.status)
    }
  },

  /** Fetches the s6 log file and hands it to the browser as a download. */
  downloadLog: async (name: string) => {
    const res = await fetch(`/service/log/${svc(name)}`, { credentials: "same-origin" })
    if (res.status === 401) {
      goToLogin()
      throw new ApiError("Your session has expired.", 401)
    }
    if (!res.ok) {
      const data = await res.json().catch(() => null)
      throw new ApiError(data?.message || `HTTP ${res.status}`, res.status)
    }
    const url = URL.createObjectURL(await res.blob())
    const a = document.createElement("a")
    a.href = url
    a.download = `${name}_log.txt`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },
}

export function openLogStream(name: string) {
  window.open(`/logs?name=${svc(name)}`, `_logs_${name}`, "noopener")
}
