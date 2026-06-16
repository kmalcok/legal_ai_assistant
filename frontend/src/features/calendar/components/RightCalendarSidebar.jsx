"use client"

import * as React from "react"
import { Plus, Calendar as CalendarIcon, List, ChevronRight, X } from "lucide-react"
import { useSidebar } from "@/components/ui/sidebar"
import { useCalendar } from "../hooks/useCalendar.js"
import { daysUntil } from "../utils/dates.js"
import { Calendar } from "@/components/ui/calendar"
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarRail,
  SidebarSeparator,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
} from "@/components/ui/sidebar"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { EventDialog } from "./EventDialog.jsx"
import { AgendaList } from "./AgendaList.jsx"
import { ScrollArea } from "@/components/ui/scroll-area"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { cn } from "@/lib/utils"

const STATUS_TABS = [
  { id: 'pending', label: 'Aktif' },
  { id: 'done', label: 'Tamamlanan' },
  { id: 'dismissed', label: 'Yoksayılan' },
  { id: 'all', label: 'Tümü' },
]

export function RightCalendarSidebar({ ...props }) {
  const {
    events,
    eventsByDate,
    loading,
    error,
    statusFilter,
    setStatusFilter,
    createEvent,
    updateEvent,
    deleteEvent,
  } = useCalendar({ initialStatus: 'pending' })

  const { setOpen } = useSidebar()

  const [viewMode, setViewMode] = React.useState('monthly') // 'monthly' or 'list'
  const [date, setDate] = React.useState(new Date())
  const [actionError, setActionError] = React.useState('')

  const calendarModifiers = React.useMemo(() => {
    const critical = []
    const warning = []
    const normal = []
    
    events.forEach(ev => {
      if (!ev.due_date || ev.status === 'done' || ev.status === 'dismissed') return
      const days = daysUntil(ev.due_date)
      const d = new Date(ev.due_date)
      if (days !== null) {
        if (days < 3) critical.push(d)
        else if (days < 7) warning.push(d)
        else normal.push(d)
      }
    })
    
    return { critical, warning, normal }
  }, [events])

  const selectedDateStr = React.useMemo(() => {
    if (!date) return null
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    return `${year}-${month}-${day}`
  }, [date])

  const displayEvents = React.useMemo(() => {
    if (viewMode === 'list') return events
    if (!selectedDateStr) return events
    return eventsByDate.get(selectedDateStr) || []
  }, [events, eventsByDate, selectedDateStr, viewMode])
  const [dialogOpen, setDialogOpen] = React.useState(false)
  const [dialogMode, setDialogMode] = React.useState('create')
  const [dialogEvent, setDialogEvent] = React.useState(null)

  const openCreateDialog = React.useCallback(() => {
    setDialogMode('create')
    setDialogEvent(null)
    setDialogOpen(true)
  }, [])

  const openEditDialog = React.useCallback((event) => {
    setDialogMode('edit')
    setDialogEvent(event)
    setDialogOpen(true)
  }, [])

  const handleSubmit = React.useCallback(
    async (payload) => {
      setActionError('')
      try {
        if (dialogMode === 'edit' && dialogEvent?.event_id) {
          await updateEvent(Number(dialogEvent.event_id), payload)
        } else {
          await createEvent(payload)
        }
        setDialogOpen(false)
      } catch (err) {
        setActionError(err?.message || 'Kaydedilemedi.')
      }
    },
    [createEvent, dialogEvent, dialogMode, updateEvent],
  )

  const handleStatusChange = React.useCallback(
    async (event, nextStatus) => {
      if (!event?.event_id) return
      setActionError('')
      try {
        await updateEvent(Number(event.event_id), { status: nextStatus })
      } catch (err) {
        setActionError(err?.message || 'İşlem başarısız.')
      }
    },
    [updateEvent],
  )

  const handleDelete = React.useCallback(
    async (event) => {
      if (!event?.event_id) return
      const confirmed = window.confirm(`"${event.title || 'Etkinlik'}" silinsin mi?`)
      if (!confirmed) return
      setActionError('')
      try {
        await deleteEvent(Number(event.event_id))
      } catch (err) {
        setActionError(err?.message || 'Silinemedi.')
      }
    },
    [deleteEvent],
  )

  return (
    <Sidebar side="right" variant="sidebar" collapsible="offcanvas" {...props}>
      <SidebarHeader className="border-b border-sidebar-border p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setOpen(false)}
              className="flex size-6 items-center justify-center rounded-md hover:bg-sidebar-accent text-sidebar-foreground/50 hover:text-sidebar-foreground"
              title="Kapat"
            >
              <X className="size-4" />
            </button>
            <h2 className="text-sm font-semibold">Takvim & Deadline</h2>
          </div>
          <button
            onClick={openCreateDialog}
            className="flex items-center gap-1 text-xs text-primary hover:underline"
          >
            <Plus className="size-3" />
            Yeni
          </button>
        </div>
      </SidebarHeader>
      
      <SidebarContent className="no-scrollbar">
        {/* View Tabs */}
        <div className="flex items-center gap-1 p-2 border-b border-sidebar-border">
          <button
            onClick={() => setViewMode('monthly')}
            className={`flex flex-1 items-center justify-center gap-2 py-2 text-sm font-medium transition-colors border-b-2 ${
              viewMode === 'monthly' ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <CalendarIcon className="size-4" />
            Aylık
          </button>
          <button
            onClick={() => setViewMode('list')}
            className={`flex flex-1 items-center justify-center gap-2 py-2 text-sm font-medium transition-colors border-b-2 ${
              viewMode === 'list' ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <List className="size-4" />
            Liste
          </button>
        </div>

        {/* Mini Calendar (Only in monthly mode) */}
        {viewMode === 'monthly' && (
          <div className="bg-white dark:bg-zinc-950 border-b border-sidebar-border">
            <SidebarGroup className="py-2">
              <SidebarGroupContent className="flex justify-center">
                <Calendar
                  mode="single"
                  selected={date}
                  onSelect={(d) => d && setDate(d)}
                  className="[--cell-size:2.4rem]"
                  modifiers={calendarModifiers}
                  modifiersClassNames={{
                    critical: "has-event-critical",
                    warning: "has-event-warning",
                    normal: "has-event-normal",
                  }}
                />
              </SidebarGroupContent>
            </SidebarGroup>
          </div>
        )}

        {viewMode === 'monthly' && <SidebarSeparator className="mx-0" />}

        {/* Status Filters */}
        <SidebarGroup className="px-2 pt-2 !pb-0">
          <Collapsible defaultOpen className="group/collapsible">
            <SidebarGroupLabel asChild className="w-full text-sm p-0">
              <CollapsibleTrigger className="flex w-full items-center justify-between px-2">
                Durum Filtresi
                <ChevronRight className="size-4 transition-transform group-data-[state=open]/collapsible:rotate-90" />
              </CollapsibleTrigger>
            </SidebarGroupLabel>
            <CollapsibleContent className="pt-1">
              <SidebarGroupContent>
                <ToggleGroup
                  type="single"
                  value={statusFilter}
                  onValueChange={(value) => {
                    if (value) setStatusFilter(value)
                  }}
                  className="takvim-status-filter w-full overflow-x-auto"
                  aria-label="Durum filtresi"
                >
                  {STATUS_TABS.map((tab) => (
                    <ToggleGroupItem
                      key={tab.id}
                      value={tab.id}
                      size="sm"
                      className={cn(
                        "takvim-status-chip h-8 min-w-fit px-2.5",
                        statusFilter === tab.id && "is-active",
                      )}
                    >
                      {tab.label}
                    </ToggleGroupItem>
                  ))}
                </ToggleGroup>
              </SidebarGroupContent>
            </CollapsibleContent>
          </Collapsible>
        </SidebarGroup>

        <SidebarSeparator className="mx-0 !my-0" />

        {/* Action Errors */}
        {(error || actionError) && (
          <div className="px-4 py-2 text-xs text-destructive bg-destructive/10 border-y border-destructive/20">
            {actionError || error}
          </div>
        )}

        {/* Agenda List */}
        <SidebarGroup className="flex-1 min-h-0 !pt-1">
          <SidebarGroupLabel className="flex justify-between items-center">
            <span>{viewMode === 'list' ? 'Tüm Etkinlikler' : `${selectedDateStr || ''} Etkinlikleri`}</span>
            {viewMode === 'monthly' && selectedDateStr && displayEvents.length > 0 && (
              <span className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded-full font-bold">
                {displayEvents.length}
              </span>
            )}
          </SidebarGroupLabel>
          <SidebarGroupContent className="flex-1 min-h-0">
            <ScrollArea className={viewMode === 'list' ? 'h-[calc(100vh-250px)]' : 'h-[calc(100vh-450px)]'}>
              <div className="p-2">
                {loading && displayEvents.length === 0 ? (
                  <div className="p-4 text-center text-xs text-muted-foreground italic">Yükleniyor...</div>
                ) : displayEvents.length === 0 ? (
                  <div className="p-8 text-center flex flex-col items-center gap-2">
                    <div className="size-8 rounded-full bg-muted flex items-center justify-center">
                      <List className="size-4 text-muted-foreground opacity-50" />
                    </div>
                    <span className="text-xs text-muted-foreground">Bu tarihte etkinlik bulunmuyor.</span>
                  </div>
                ) : (
                  <AgendaList
                    events={displayEvents}
                    onEdit={openEditDialog}
                    onDelete={handleDelete}
                    onMarkDone={(ev) => handleStatusChange(ev, 'done')}
                    onDismiss={(ev) => handleStatusChange(ev, 'dismissed')}
                    onReopen={(ev) => handleStatusChange(ev, 'pending')}
                    compact
                  />
                )}
              </div>
            </ScrollArea>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarRail />

      <EventDialog
        open={dialogOpen}
        mode={dialogMode}
        initialEvent={dialogEvent}
        onClose={() => setDialogOpen(false)}
        onSubmit={handleSubmit}
      />
    </Sidebar>
  )
}
