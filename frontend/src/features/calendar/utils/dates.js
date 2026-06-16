export function isoDate(value) {
  if (!value) return ''
  if (value instanceof Date) {
    if (Number.isNaN(value.getTime())) return ''
    const y = value.getFullYear()
    const m = String(value.getMonth() + 1).padStart(2, '0')
    const d = String(value.getDate()).padStart(2, '0')
    return `${y}-${m}-${d}`
  }
  return String(value).slice(0, 10)
}

export function parseIsoDate(value) {
  if (!value) return null
  const text = typeof value === 'string' ? value.slice(0, 10) : ''
  if (!text) return null
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text)
  if (!m) return null
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
  return Number.isNaN(d.getTime()) ? null : d
}

export function todayIso() {
  return isoDate(new Date())
}

export function startOfDay(date) {
  if (!date) return null
  const d = new Date(date)
  d.setHours(0, 0, 0, 0)
  return d
}

export function daysUntil(targetIso) {
  const target = parseIsoDate(targetIso)
  if (!target) return null
  const today = startOfDay(new Date())
  const diffMs = startOfDay(target).getTime() - today.getTime()
  return Math.round(diffMs / (1000 * 60 * 60 * 24))
}

export function urgencyClass(targetIso, status) {
  if (status === 'done' || status === 'dismissed') return 'event-urgency-muted'
  const days = daysUntil(targetIso)
  if (days === null) return 'event-urgency-default'
  if (days < 0) return 'event-urgency-overdue'
  if (days < 3) return 'event-urgency-critical'
  if (days < 7) return 'event-urgency-warning'
  return 'event-urgency-default'
}

const TR_FORMATTER = new Intl.DateTimeFormat('tr-TR', {
  day: '2-digit',
  month: 'long',
  year: 'numeric',
})

export function formatTrDate(value) {
  const d = parseIsoDate(value)
  if (!d) return value || ''
  return TR_FORMATTER.format(d)
}

const TR_SHORT = new Intl.DateTimeFormat('tr-TR', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
})

export function formatTrDateShort(value) {
  const d = parseIsoDate(value)
  if (!d) return value || ''
  return TR_SHORT.format(d)
}

export function formatRemainingLabel(targetIso, status) {
  if (status === 'done') return 'Tamamlandı'
  if (status === 'dismissed') return 'Yoksayıldı'
  const days = daysUntil(targetIso)
  if (days === null) return ''
  if (days < 0) return `${Math.abs(days)} gün gecikti`
  if (days === 0) return 'Bugün'
  if (days === 1) return 'Yarın'
  return `${days} gün kaldı`
}
