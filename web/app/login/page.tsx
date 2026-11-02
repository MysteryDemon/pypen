"use client"

import { useState, type FormEvent } from "react"
import { CircleAlert, LoaderCircle, Lock, LogIn, User } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { api } from "@/lib/api"

export default function LoginPage() {
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    setPending(true)
    setError(null)
    try {
      await api.login(String(form.get("username")), String(form.get("password")))
      window.location.replace("/")
    } catch (err) {
      setError((err as Error).message)
      setPending(false)
    }
  }

  return (
    <main className="relative grid min-h-dvh place-items-center overflow-hidden px-4 py-12">
      <title>Login · Pypen</title>
      <div
        aria-hidden="true"
        className="pointer-events-none absolute top-[-12rem] left-1/2 size-[36rem] -translate-x-1/2 rounded-full bg-emerald-500/[0.07] blur-3xl"
      />

      <div className="relative w-full max-w-sm">
        <Card className="gap-0 p-6">
          <h1 className="mb-6 text-center text-xl font-semibold tracking-tight">Login</h1>
          <form onSubmit={onSubmit} className="grid gap-5">
            {error && (
              <Alert variant="destructive" className="border-red-500/25 bg-red-500/[0.06]">
                <CircleAlert />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <div className="grid gap-2">
              <Label htmlFor="username">Username</Label>
              <div className="relative">
                <User className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="username"
                  name="username"
                  autoComplete="username"
                  autoFocus
                  required
                  className="h-10 pl-9"
                />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Lock className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  className="h-10 pl-9"
                />
              </div>
            </div>
            <Button type="submit" size="lg" className="h-10" disabled={pending}>
              {pending ? <LoaderCircle className="animate-spin" /> : <LogIn />}
              {pending ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </Card>
      </div>
    </main>
  )
}
