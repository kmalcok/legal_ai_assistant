import { useMemo } from 'react'
import { EventCard } from './EventCard.jsx'
import { formatRemainingLabel, formatTrDate } from '../utils/dates.js'

export function AgendaList({ events, onEdit, onDelete, onMarkDone, onDismiss, onReopen, compact = false }) {
  const grouped = useMemo(() => {
    const map = new Map()
    for (const ev of events || []) {
      const key = String(ev?.due_date || '').slice(0, 10)
      if (!key) continue
      const arr = map.get(key) || []
      arr.push(ev)
      map.set(key, arr)
    }
    const ordered = Array.from(map.entries()).sort((a, b) => (a[0] < b[0] ? -1 : 1))
    return ordered
  }, [events])

  if (!grouped.length) {
    return <div className="takvim-empty">Şu an için takvimde kayıt yok.</div>
  }

  return (
    <div className={`takvim-agenda ${compact ? 'is-compact' : ''}`}>
      {grouped.map(([date, items]) => (
        <section key={date} className="takvim-agenda-day">
          <div className="takvim-agenda-day-head">
            <div className="takvim-agenda-day-title">{formatTrDate(date)}</div>
            <div className="takvim-agenda-day-rel">{formatRemainingLabel(date, 'pending')}</div>
          </div>
          {items.map((event) => (
            <EventCard
              key={event.event_id}
              event={event}
              onEdit={onEdit}
              onDelete={onDelete}
              onMarkDone={onMarkDone}
              onDismiss={onDismiss}
              onReopen={onReopen}
              compact={compact}
            />
          ))}
        </section>
      ))}
    </div>
  )
}
