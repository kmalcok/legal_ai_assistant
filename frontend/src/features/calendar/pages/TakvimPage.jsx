import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'
import { Calendar, List, Plus } from 'lucide-react'
import { MonthGrid } from '../components/MonthGrid.jsx'
import { AgendaList } from '../components/AgendaList.jsx'
import { EventDialog } from '../components/EventDialog.jsx'
import { useCalendar } from '../hooks/useCalendar.js'
import yargucuLogo from '../../../logopack/yargucu-logo-siyah.svg'

const STATUS_TABS = [
  { id: 'pending', label: 'Aktif' },
  { id: 'done', label: 'Tamamlanan' },
  { id: 'dismissed', label: 'Yoksayılan' },
  { id: 'all', label: 'Tümü' },
]

export function TakvimPage() {
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

  const [view, setView] = useState('month') // 'month' | 'agenda'
  const [dialogOpen, setDialogOpen] = useState(false)
  const [dialogMode, setDialogMode] = useState('create')
  const [dialogEvent, setDialogEvent] = useState(null)
  const [actionError, setActionError] = useState('')

  const openCreateDialog = useCallback(() => {
    setDialogMode('create')
    setDialogEvent(null)
    setDialogOpen(true)
  }, [])

  const openEditDialog = useCallback((event) => {
    setDialogMode('edit')
    setDialogEvent(event)
    setDialogOpen(true)
  }, [])

  const closeDialog = useCallback(() => setDialogOpen(false), [])

  const handleSubmit = useCallback(
    async (payload) => {
      setActionError('')
      if (dialogMode === 'edit' && dialogEvent?.event_id) {
        await updateEvent(Number(dialogEvent.event_id), payload)
      } else {
        await createEvent(payload)
      }
    },
    [createEvent, dialogEvent, dialogMode, updateEvent],
  )

  const handleStatusChange = useCallback(
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

  const handleDelete = useCallback(
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
    <div className="takvim-page">
      <header className="takvim-header">
        <Link to="/chat" className="takvim-back" aria-label="Sohbete dön">
          <span className="takvim-back-glyph" aria-hidden="true">
            ‹
          </span>
          <img src={yargucuLogo} alt="Yargucu" style={{ height: 22 }} />
        </Link>
        <div className="takvim-title-wrap">
          <span className="takvim-title">Takvim</span>
          <span className="takvim-title-separator">-</span>
          <p className="takvim-subtitle">Süre ve deadline takibi</p>
        </div>
        <div className="takvim-actions">
          <button type="button" className="takvim-add-btn" onClick={openCreateDialog}>
            <Plus className="size-4" />
            Yeni etkinlik
          </button>
        </div>
      </header>

      <nav className="takvim-tabs" aria-label="Görünüm">
        <button
          type="button"
          className={`takvim-tab${view === 'month' ? ' is-active' : ''}`}
          onClick={() => setView('month')}
        >
          <Calendar className="size-4" />
          Aylık
        </button>
        <button
          type="button"
          className={`takvim-tab${view === 'agenda' ? ' is-active' : ''}`}
          onClick={() => setView('agenda')}
        >
          <List className="size-4" />
          Liste
        </button>
      </nav>

      <div className="takvim-toolbar">
        <div className="takvim-status-filter" role="group" aria-label="Durum filtresi">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`takvim-status-chip${statusFilter === tab.id ? ' is-active' : ''}`}
              onClick={() => setStatusFilter(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="takvim-toolbar-spacer" />
      </div>

      {error ? <div className="takvim-error" style={{ padding: '0 24px' }}>{error}</div> : null}
      {actionError ? (
        <div className="takvim-error" style={{ padding: '0 24px' }}>{actionError}</div>
      ) : null}

      {loading && events.length === 0 ? (
        <div className="takvim-loading">Yükleniyor...</div>
      ) : view === 'month' ? (
        <MonthGrid
          eventsByDate={eventsByDate}
          onEdit={openEditDialog}
          onDelete={handleDelete}
          onMarkDone={(ev) => handleStatusChange(ev, 'done')}
          onDismiss={(ev) => handleStatusChange(ev, 'dismissed')}
          onReopen={(ev) => handleStatusChange(ev, 'pending')}
        />
      ) : (
        <div className="takvim-body">
          <AgendaList
            events={events}
            onEdit={openEditDialog}
            onDelete={handleDelete}
            onMarkDone={(ev) => handleStatusChange(ev, 'done')}
            onDismiss={(ev) => handleStatusChange(ev, 'dismissed')}
            onReopen={(ev) => handleStatusChange(ev, 'pending')}
          />
        </div>
      )}

      <EventDialog
        open={dialogOpen}
        mode={dialogMode}
        initialEvent={dialogEvent}
        onClose={closeDialog}
        onSubmit={handleSubmit}
      />
    </div>
  )
}
