"use client"

import { useState } from "react"
import { CircleHelp, TriangleAlert } from "lucide-react"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogMedia,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { cn } from "@/lib/utils"

export type ConfirmRequest = {
  title: string
  description: string
  confirmLabel?: string
  destructive?: boolean
  onConfirm: () => void
}

export function ConfirmDialog({
  request,
  onClose,
}: {
  request: ConfirmRequest | null
  onClose: () => void
}) {
  const [shown, setShown] = useState(request)
  if (request && request !== shown) setShown(request)

  const destructive = shown?.destructive ?? false
  return (
    <AlertDialog open={request !== null} onOpenChange={(open) => !open && onClose()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogMedia
            className={cn(destructive ? "bg-red-500/10 text-red-400" : "bg-white/[0.06] text-foreground")}
          >
            {destructive ? <TriangleAlert /> : <CircleHelp />}
          </AlertDialogMedia>
          <AlertDialogTitle>{shown?.title}</AlertDialogTitle>
          <AlertDialogDescription className="whitespace-pre-line">
            {shown?.description}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter className="bg-white/[0.02]">
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            variant={destructive ? "destructive" : "default"}
            onClick={() => shown?.onConfirm()}
          >
            {shown?.confirmLabel ?? "Confirm"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
