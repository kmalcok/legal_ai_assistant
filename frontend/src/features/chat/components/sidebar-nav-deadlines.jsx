"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { CalendarClock, ChevronRight } from "lucide-react"

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  SidebarGroup,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
} from "@/components/ui/sidebar"

import { useAuth } from "../../auth/useAuth.js"
import {
  formatRemainingLabel,
  formatTrDateShort,
} from "../../calendar/utils/dates.js"

const MAX_VISIBLE = 5

function pillClass(daysRemaining) {
  if (daysRemaining === null || daysRemaining === undefined) return ""
  if (daysRemaining < 0) return "is-overdue"
  if (daysRemaining < 3) return "is-critical"
  if (daysRemaining < 7) return "is-warning"
  return ""
}

function daysUntilLocal(iso) {
  if (!iso) return null
  const target = new Date(`${String(iso).slice(0, 10)}T00:00:00`)
  if (Number.isNaN(target.getTime())) return null
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return Math.round((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))
}

export function NavDeadlines(props) {
  const { request } = useAuth()
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const requestIdRef = useRef(0)

  useEffect(() => {
    let cancelled = false
    const controller = new AbortController()
    const requestId = requestIdRef.current + 1
    requestIdRef.current = requestId

    async function fetchEvents() {
      setLoading(true)
      setError("")
      try {
        const data = await request("/v1/calendar/events?status=pending", {
          method: "GET",
          signal: controller.signal,
        })
        if (cancelled || requestIdRef.current !== requestId) return
        const list = Array.isArray(data?.events) ? data.events : []
        setEvents(list)
      } catch (err) {
        if (err?.name === "AbortError") return
        if (cancelled) return
        setError("Yüklenemedi")
        setEvents([])
      } finally {
        if (!cancelled && requestIdRef.current === requestId) setLoading(false)
      }
    }

    fetchEvents()

    return () => {
      cancelled = true
      controller.abort()
    }
  }, [request])

  const upcoming = useMemo(() => {
    const todayIso = new Date().toISOString().slice(0, 10)
    return events
      .filter((ev) => String(ev?.due_date || "").slice(0, 10) >= todayIso)
      .slice(0, MAX_VISIBLE)
  }, [events])

  const visibleRows = Math.max(
    upcoming.length + Number(Boolean(loading)) + Number(Boolean(error)),
    1,
  )

  return (
    <SidebarGroup className="sidebar-panel-group" {...props}>
      <SidebarMenu className="sidebar-panel-menu">
        <Collapsible asChild defaultOpen className="group/collapsible">
          <SidebarMenuItem className="sidebar-panel-item">
            <CollapsibleTrigger asChild>
              <SidebarMenuButton tooltip="Zaman Takibi">
                <CalendarClock />
                <span className="truncate">Zaman Takibi</span>
                <span className="section-badge ml-auto shrink-0">
                  {upcoming.length}
                </span>
                <ChevronRight className="shrink-0 transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
              </SidebarMenuButton>
            </CollapsibleTrigger>
            <CollapsibleContent className="sidebar-panel-content">
              <SidebarMenuSub className="sidebar-panel-sub">
                <div
                  className="sidebar-panel-scroll sidebar-section-scroll chat-sidebar-scroll"
                  style={{
                    "--sidebar-list-count": visibleRows,
                    "--sidebar-max-visible-rows": 6,
                  }}
                >
                  {loading && (
                    <div className="px-2 py-1.5 text-xs text-muted-foreground">
                      Yükleniyor...
                    </div>
                  )}
                  {error && !loading && (
                    <div className="px-2 py-1.5 text-xs text-destructive">{error}</div>
                  )}
                  {!loading && !error && upcoming.length === 0 && (
                    <div className="px-2 py-1.5 text-xs text-muted-foreground">
                      Yaklaşan kayıt yok
                    </div>
                  )}

                  {upcoming.map((event) => {
                    const eventId = Number(event?.event_id)
                    const days = daysUntilLocal(event?.due_date)
                    const remaining = formatRemainingLabel(event?.due_date, "pending")
                    const dateLabel = formatTrDateShort(event?.due_date)
                    const title = String(event?.title || "Etkinlik")
                    const tooltip = event?.note ? `${title}\n${event.note}` : title

                    return (
                      <SidebarMenuSubItem
                        key={eventId}
                        className="relative group/sub-item"
                      >
                        <SidebarMenuSubButton asChild>
                          <Link
                            to="/takvim"
                            title={tooltip}
                            className="sidebar-sub-link sidebar-deadline-row"
                          >
                            <span className="sidebar-deadline-main">
                              <span className="truncate">{title}</span>
                              <span className="sidebar-deadline-meta">
                                <span className="sidebar-deadline-date">{dateLabel}</span>
                                {remaining ? (
                                  <span
                                    className={`sidebar-deadline-pill ${pillClass(days)}`}
                                  >
                                    {remaining}
                                  </span>
                                ) : null}
                              </span>
                            </span>
                          </Link>
                        </SidebarMenuSubButton>
                      </SidebarMenuSubItem>
                    )
                  })}

                  {!loading && upcoming.length > 0 ? (
                    <SidebarMenuSubItem className="sidebar-deadline-footer">
                      <SidebarMenuSubButton asChild>
                        <Link
                          to="/takvim"
                          className="sidebar-sub-link sidebar-deadline-all"
                        >
                          <span className="truncate">Tümünü gör</span>
                        </Link>
                      </SidebarMenuSubButton>
                    </SidebarMenuSubItem>
                  ) : null}
                </div>
              </SidebarMenuSub>
            </CollapsibleContent>
          </SidebarMenuItem>
        </Collapsible>
      </SidebarMenu>
    </SidebarGroup>
  )
}
