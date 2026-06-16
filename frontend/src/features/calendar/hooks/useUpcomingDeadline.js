import { useEffect, useRef, useState, useCallback } from 'react'
import { useAuth } from '../../auth/useAuth.js'

const REFRESH_INTERVAL_MS = 5 * 60 * 1000
const URGENT_WINDOW_HOURS = 36

function buildEventInstant(ev) {
  const dateStr = String(ev?.due_date || '').slice(0, 10)
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) return null
  const [y, m, d] = dateStr.split('-').map(Number)
  let hh = 23
  let mm = 59
  const timeStr = String(ev?.due_time || '').trim()
  if (/^\d{1,2}:\d{2}/.test(timeStr)) {
    const parts = timeStr.split(':').map((p) => Number(p))
    if (Number.isFinite(parts[0])) hh = Math.min(23, Math.max(0, parts[0]))
    if (Number.isFinite(parts[1])) mm = Math.min(59, Math.max(0, parts[1]))
  }
  const dt = new Date(y, (m || 1) - 1, d || 1, hh, mm, 0, 0)
  return Number.isNaN(dt.getTime()) ? null : dt
}

/**
 * Lightweight hook for showing a red badge on the calendar shortcut.
 * Polls pending events and exposes whether any of them falls inside the
 * urgent window (default: 36 hours from now). Re-fetches every 5 minutes
 * and when the window/tab regains focus.
 */
export function useUpcomingDeadline({ windowHours = URGENT_WINDOW_HOURS } = {}) {
  const { request, user } = useAuth()
  const [hasUrgent, setHasUrgent] = useState(false)
  const [nextDue, setNextDue] = useState(null)
  const requestIdRef = useRef(0)

  const compute = useCallback(
    (events) => {
      const now = Date.now()
      const windowMs = Number(windowHours) * 60 * 60 * 1000
      let earliestUrgentMs = null
      const list = Array.isArray(events) ? events : []
      for (const ev of list) {
        if (ev?.status && ev.status !== 'pending') continue
        const dt = buildEventInstant(ev)
        if (!dt) continue
        const ms = dt.getTime()
        const diff = ms - now
        if (diff < 0) continue
        if (diff <= windowMs) {
          if (earliestUrgentMs === null || ms < earliestUrgentMs) {
            earliestUrgentMs = ms
          }
        }
      }
      setHasUrgent(earliestUrgentMs !== null)
      setNextDue(earliestUrgentMs !== null ? new Date(earliestUrgentMs) : null)
    },
    [windowHours],
  )

  const fetchOnce = useCallback(
    async (signal) => {
      if (!user) {
        setHasUrgent(false)
        setNextDue(null)
        return
      }
      const requestId = requestIdRef.current + 1
      requestIdRef.current = requestId
      try {
        const data = await request('/v1/calendar/events?status=pending', {
          method: 'GET',
          signal,
        })
        if (requestIdRef.current !== requestId) return
        const events = Array.isArray(data?.events) ? data.events : []
        compute(events)
      } catch (err) {
        if (err?.name === 'AbortError') return
        if (requestIdRef.current !== requestId) return
        setHasUrgent(false)
        setNextDue(null)
      }
    },
    [request, user, compute],
  )

  useEffect(() => {
    const controller = new AbortController()
    fetchOnce(controller.signal)
    const interval = window.setInterval(() => {
      fetchOnce()
    }, REFRESH_INTERVAL_MS)
    const onVisibility = () => {
      if (document.visibilityState === 'visible') fetchOnce()
    }
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('focus', onVisibility)
    return () => {
      controller.abort()
      window.clearInterval(interval)
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('focus', onVisibility)
    }
  }, [fetchOnce])

  return { hasUrgent, nextDue, refresh: () => fetchOnce() }
}
