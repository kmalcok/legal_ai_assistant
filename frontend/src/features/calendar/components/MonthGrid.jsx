import { useCallback, useMemo, useState } from 'react'
import { DayPicker } from 'react-day-picker'
import { tr } from 'date-fns/locale'
import 'react-day-picker/style.css'
import { EventCard } from './EventCard.jsx'
import {
  daysUntil,
  formatTrDate,
  isoDate,
  parseIsoDate,
  todayIso,
} from '../utils/dates.js'

function urgencyDotClass(events) {
  if (!Array.isArray(events) || events.length === 0) return null
  let level = 'default'
  let allInactive = true
  for (const ev of events) {
    if (ev?.status === 'done' || ev?.status === 'dismissed') continue
    allInactive = false
    const days = daysUntil(ev?.due_date)
    if (days === null) continue
    if (days < 0) {
      level = 'overdue'
      break
    }
    if (days < 3) {
      level = 'critical'
    } else if (days < 7 && level !== 'critical') {
      level = 'warning'
    }
  }
  if (allInactive) return 'is-done'
  if (level === 'overdue') return 'is-overdue'
  if (level === 'critical') return 'is-critical'
  if (level === 'warning') return 'is-warning'
  return ''
}

export function MonthGrid({ eventsByDate, onEdit, onDelete, onMarkDone, onDismiss, onReopen }) {
  const [selectedIso, setSelectedIso] = useState(todayIso())

  const selectedDate = useMemo(() => parseIsoDate(selectedIso), [selectedIso])
  const selectedEvents = useMemo(
    () => (selectedIso ? eventsByDate.get(selectedIso) || [] : []),
    [eventsByDate, selectedIso],
  )

  const DayButton = useCallback(
    ({ day, modifiers, ...buttonProps }) => {
      const date = day?.date
      const key = date ? isoDate(date) : ''
      const events = key ? eventsByDate.get(key) || [] : []
      const dotClass = urgencyDotClass(events)
      const dots = Math.min(events.length, 3)
      const tooltip = events.length
        ? events
            .map((ev) => {
              const title = ev?.title || 'Etkinlik'
              const note = ev?.note ? ` - ${ev.note}` : ''
              return `${title}${note}`
            })
            .join('\n')
        : undefined
      return (
        <button {...buttonProps} type="button" title={tooltip}>
          <span>{date ? date.getDate() : ''}</span>
          {dots > 0 ? (
            <span className="takvim-day-marker" aria-hidden="true">
              {Array.from({ length: dots }).map((_, idx) => (
                <span key={idx} className={`takvim-day-dot ${dotClass || ''}`} />
              ))}
            </span>
          ) : null}
        </button>
      )
    },
    [eventsByDate],
  )

  return (
    <div className="takvim-body is-month">
      <div className="takvim-month-card">
        <DayPicker
          locale={tr}
          mode="single"
          selected={selectedDate || undefined}
          onSelect={(date) => {
            setSelectedIso(date ? isoDate(date) : '')
          }}
          weekStartsOn={1}
          showOutsideDays
          components={{ DayButton }}
        />
      </div>
      <aside className="takvim-side">
        <div className="takvim-side-title">
          {selectedIso ? formatTrDate(selectedIso) : 'Bir gün seçin'}
        </div>
        {!selectedEvents.length ? (
          <div className="takvim-empty">Bu gün için kayıt yok.</div>
        ) : (
          selectedEvents.map((event) => (
            <EventCard
              key={event.event_id}
              event={event}
              onEdit={onEdit}
              onDelete={onDelete}
              onMarkDone={onMarkDone}
              onDismiss={onDismiss}
              onReopen={onReopen}
            />
          ))
        )}
      </aside>
    </div>
  )
}
