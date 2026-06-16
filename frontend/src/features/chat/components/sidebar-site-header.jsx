"use client"

import { PanelLeftOpen } from "lucide-react"

import { Button } from "@/components/ui/button"

export function SiteHeader({ isSidebarCollapsed, onOpenSidebar, isPanelOpen }) {
  if (!isSidebarCollapsed || isPanelOpen) return null

  const handleOpen = (e) => {
    e?.preventDefault?.()
    e?.stopPropagation?.()
    onOpenSidebar?.()
  }

  return (
    <div
      className="app-safe-top-fab fixed left-4 z-[90]"
      style={{ touchAction: 'manipulation' }}
    >
      <Button
        className="h-11 w-11 rounded-full border border-border/80 bg-background/92 text-foreground shadow-lg backdrop-blur-md hover:bg-muted"
        variant="outline"
        size="icon"
        onClick={handleOpen}
        aria-label="Menüyü aç"
        title="Menüyü aç"
        style={{ touchAction: 'manipulation' }}
      >
        <PanelLeftOpen className="size-5" />
      </Button>
    </div>
  )
}
