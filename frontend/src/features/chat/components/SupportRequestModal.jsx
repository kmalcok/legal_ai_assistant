"use client"

import { useMemo, useState } from "react"
import { X } from "lucide-react"

const MAX_SUPPORT_MESSAGE_LEN = 4000

export function SupportRequestModal({ isOpen, onClose, onSubmit }) {
  const [message, setMessage] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState("")

  const trimmedMessage = useMemo(() => message.trim(), [message])
  const canSubmit = !submitting && trimmedMessage.length > 0 && trimmedMessage.length <= MAX_SUPPORT_MESSAGE_LEN

  if (!isOpen) return null

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!canSubmit) return
    setSubmitting(true)
    setError("")
    try {
      await onSubmit?.(trimmedMessage)
      setMessage("")
      onClose?.()
    } catch (err) {
      setError(err?.message || "Destek talebi gönderilemedi")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center p-4 sm:p-6">
      <button
        className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm"
        type="button"
        aria-label="Destek penceresini kapat"
        onClick={() => {
          if (submitting) return
          onClose?.()
        }}
      />

      <div className="relative w-full max-w-xl overflow-hidden rounded-2xl border border-border bg-background shadow-2xl">
        <div className="flex items-center justify-between border-b border-border/50 bg-muted/30 p-5">
          <div>
            <h2 className="text-lg font-semibold tracking-tight">Destek Talebi</h2>
            <p className="text-xs text-muted-foreground">Sorununuzu kisa ve net sekilde yazin.</p>
          </div>
          <button
            type="button"
            onClick={() => {
              if (submitting) return
              onClose?.()
            }}
            className="rounded-full p-2 text-muted-foreground transition-colors hover:bg-muted"
            aria-label="Kapat"
            title="Kapat"
          >
            <X size={18} strokeWidth={2.5} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 p-5">
          <textarea
            value={message}
            onChange={(e) => setMessage(String(e.target.value || "").slice(0, MAX_SUPPORT_MESSAGE_LEN))}
            placeholder="Ornek: Dilekce olustururken hata aliyorum, sohbet ID: ..."
            className="min-h-36 w-full resize-y rounded-xl border border-input bg-background px-3 py-2 text-sm outline-none ring-offset-background placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60"
            disabled={submitting}
          />
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">{message.length}/{MAX_SUPPORT_MESSAGE_LEN}</span>
            {error ? <span className="text-destructive">{error}</span> : null}
          </div>

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                if (submitting) return
                onClose?.()
              }}
              className="rounded-xl border border-border px-4 py-2 text-sm font-medium transition-colors hover:bg-muted disabled:opacity-60"
              disabled={submitting}
            >
              Vazgec
            </button>
            <button
              type="submit"
              className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={!canSubmit}
            >
              {submitting ? "Gonderiliyor..." : "Destek Talebi Gonder"}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
