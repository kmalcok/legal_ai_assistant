import { useNavigate } from 'react-router-dom'
import { Check, Edit2, Trash2, X, RotateCcw, MessageSquare } from 'lucide-react'
import {
  daysUntil,
  formatRemainingLabel,
  urgencyClass,
} from '../utils/dates.js'

const SOURCE_LABELS = {
  petition_tool: 'Dilekçe',
  petition_auto: 'Dilekçe',
  manual: 'Manuel',
}

function urgencyPillClass(targetIso, status) {
  if (status === 'done') return 'is-status-done'
  if (status === 'dismissed') return 'is-status-dismissed'
  const days = daysUntil(targetIso)
  if (days === null) return ''
  if (days < 0) return 'is-overdue'
  if (days < 3) return 'is-critical'
  if (days < 7) return 'is-warning'
  return ''
}

export function EventCard({ event, onEdit, onDelete, onMarkDone, onDismiss, onReopen, compact = false }) {
  const navigate = useNavigate()
  const due = event?.due_date
  const status = event?.status || 'pending'
  const remaining = formatRemainingLabel(due, status)
  const sourceLabel = SOURCE_LABELS[event?.source] || 'Manuel'
  const isPetition = event?.source === 'petition_tool' || event?.source === 'petition_auto'
  const cardClass = `takvim-event-card ${urgencyClass(due, status)}`

  const handleOpenChat = () => {
    if (!event?.chat_id) return
    navigate(`/chat/${Number(event.chat_id)}`)
  }

  return (
    <div className={cardClass}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
             {remaining ? (
              <span className={`takvim-event-pill text-[10px] uppercase tracking-wider font-bold ${urgencyPillClass(due, status)}`}>
                {remaining}
              </span>
            ) : null}
            {event?.due_time ? <span className="text-[11px] font-medium text-muted-foreground">{String(event.due_time).slice(0, 5)}</span> : null}
          </div>
          <h4 className="text-sm font-semibold leading-tight text-foreground truncate">{event?.title || 'Etkinlik'}</h4>
        </div>
        
        {status === 'pending' ? (
          <button
            onClick={() => onMarkDone?.(event)}
            className="flex size-8 items-center justify-center rounded-full bg-primary/10 text-primary hover:bg-primary hover:text-white transition-all shadow-sm shrink-0"
            title="Tamamla"
          >
            <Check className="size-4" />
          </button>
        ) : (
          <button
            onClick={() => onReopen?.(event)}
            className="flex size-8 items-center justify-center rounded-full bg-muted text-muted-foreground hover:bg-foreground hover:text-background transition-all shrink-0"
            title="Tekrar Aç"
          >
            <RotateCcw className="size-4" />
          </button>
        )}
      </div>

      {event?.note && (
        <p className="text-[12px] text-muted-foreground/80 line-clamp-2 mt-1 leading-normal">
          {event.note}
        </p>
      )}

      <div className="flex items-center justify-between mt-3 pt-3 border-t border-dashed border-sidebar-border/50">
        <div className="flex items-center gap-2">
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded bg-sidebar-accent text-sidebar-foreground/70 uppercase tracking-tight`}>
            {sourceLabel}
          </span>
          {status !== 'pending' && (
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${status === 'done' ? 'bg-green-500/10 text-green-600' : 'bg-muted text-muted-foreground'} uppercase tracking-tight`}>
              {status === 'done' ? 'BİTTİ' : 'YOKSAYILDI'}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1">
          {isPetition && event?.chat_id && (
            <button
              onClick={handleOpenChat}
              className="p-1.5 rounded-md hover:bg-sidebar-accent text-sidebar-foreground/40 hover:text-primary transition-colors"
              title="Sohbeti Aç"
            >
              <MessageSquare className="size-3.5" />
            </button>
          )}
          <button
            onClick={() => onEdit?.(event)}
            className="p-1.5 rounded-md hover:bg-sidebar-accent text-sidebar-foreground/40 hover:text-foreground transition-colors"
            title="Düzenle"
          >
            <Edit2 className="size-3.5" />
          </button>
          {status === 'pending' && (
            <button
              onClick={() => onDismiss?.(event)}
              className="p-1.5 rounded-md hover:bg-sidebar-accent text-sidebar-foreground/40 hover:text-foreground transition-colors"
              title="Yoksay"
            >
              <X className="size-3.5" />
            </button>
          )}
          <button
            onClick={() => onDelete?.(event)}
            className="p-1.5 rounded-md hover:bg-sidebar-accent text-sidebar-foreground/40 hover:text-destructive transition-colors"
            title="Sil"
          >
            <Trash2 className="size-3.5" />
          </button>
        </div>
      </div>
    </div>
  )
}
