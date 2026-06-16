export function normalizeRealtimeEvent(evt) {
  const event = evt && typeof evt === 'object' ? evt : {}
  const type = String(event.type || '').trim()
  if (!type) return event

  if (type === 'dilekce_ready') return { ...event, type: 'petition_ready' }
  if (type === 'dilekce_failed') return { ...event, type: 'petition_failed' }

  return event
}

export function normalizeIctihatDocumentText(data) {
  if (!data || typeof data !== 'object') return ''
  if (typeof data.text === 'string' && data.text.trim()) return data.text
  if (typeof data.page?.text === 'string') return data.page.text
  return ''
}
