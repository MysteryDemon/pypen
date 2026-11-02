"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { io, type Socket } from "socket.io-client"
import { api, ApiError } from "@/lib/api"
import type { Process, StatusPayload } from "@/lib/types"

const POLL_MS = 3000

export type Connection = "connecting" | "live" | "polling" | "offline"

export function useProcessFeed() {
  const [processes, setProcesses] = useState<Process[] | null>(null)
  const [connection, setConnection] = useState<Connection>("connecting")
  const socketRef = useRef<Socket | null>(null)

  const apply = useCallback((data: StatusPayload) => {
    if (data?.status === "success" && Array.isArray(data.processes)) {
      setProcesses(data.processes)
    } else {
      setProcesses((prev) => prev ?? [])
    }
  }, [])

  const refresh = useCallback(async () => {
    const socket = socketRef.current
    if (socket?.connected) {
      socket.emit("request_status")
      return
    }
    try {
      apply(await api.status())
      if (!socketRef.current?.connected) setConnection("polling")
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return
      if (!socketRef.current?.connected) setConnection("offline")
    }
  }, [apply])

  useEffect(() => {
    const socket = io({
      transports: ["websocket", "polling"],
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
    })
    socketRef.current = socket
    socket.on("connect", () => {
      setConnection("live")
      socket.emit("request_status")
    })
    socket.on("disconnect", () => setConnection("polling"))
    socket.on("status_update", apply)

    refresh()
    const timer = setInterval(() => {
      if (!document.hidden) refresh()
    }, POLL_MS)
    const onVisibility = () => {
      if (!document.hidden) refresh()
    }
    document.addEventListener("visibilitychange", onVisibility)

    return () => {
      clearInterval(timer)
      document.removeEventListener("visibilitychange", onVisibility)
      socket.disconnect()
      socketRef.current = null
    }
  }, [apply, refresh])

  return { processes, connection, refresh }
}
