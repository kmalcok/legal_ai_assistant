import * as React from "react"
import { createPortal } from "react-dom"

import { cn } from "@/lib/utils"

const DialogContext = React.createContext(null)

function Dialog({
  open = false,
  onOpenChange,
  children,
}) {
  const contextValue = React.useMemo(
    () => ({ open, onOpenChange }),
    [onOpenChange, open]
  )

  return <DialogContext.Provider value={contextValue}>{children}</DialogContext.Provider>
}

function DialogPortal({ children }) {
  if (typeof document === "undefined") return null
  return createPortal(children, document.body)
}

function DialogOverlay({
  className,
  onClick,
  ...props
}) {
  const context = React.useContext(DialogContext)
  if (!context?.open) return null

  return (
    <DialogPortal>
      <div
        data-slot="dialog-overlay"
        className={cn(
          "fixed inset-0 z-50 bg-black/40 backdrop-blur-sm transition-all duration-200 animate-in fade-in-0",
          className
        )}
        onClick={(event) => {
          onClick?.(event)
          if (!event.defaultPrevented) {
            context.onOpenChange?.(false)
          }
        }}
        {...props}
      />
    </DialogPortal>
  )
}

function DialogContent({
  className,
  children,
  ...props
}) {
  const context = React.useContext(DialogContext)
  if (!context?.open) return null

  return (
    <DialogPortal>
      <div
        role="dialog"
        aria-modal="true"
        data-slot="dialog-content"
        className={cn(
          "fixed left-[50%] top-[50%] z-50 grid w-[calc(100%-2rem)] max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-lg duration-200 animate-in fade-in-0 zoom-in-95 sm:rounded-xl md:w-full",
          className
        )}
        {...props}
      >
        {children}
      </div>
    </DialogPortal>
  )
}

export { Dialog, DialogOverlay, DialogContent, DialogPortal }
