import { Suspense } from "react"
import { LogViewer } from "@/components/log-viewer"

export default function LogsPage() {
  return (
    <Suspense>
      <LogViewer />
    </Suspense>
  )
}
