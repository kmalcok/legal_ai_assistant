import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useAuth } from '../../auth/useAuth.js'
import { humanizeApiError } from '../../../shared/api/contracts.js'

function buildListPath({ from, to, status }) {
  const params = new URLSearchParams()
  if (from) params.set('from', from)
  if (to) params.set('to', to)
  if (status) params.set('status', status)
  const qs = params.toString()
  return qs ? `/v1/calendar/events?${qs}` : '/v1/calendar/events'
}

export function useCalendar({ initialStatus = 'pending' } = {}) {
  const { request } = useAuth()
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [statusFilter, setStatusFilter] = useState(initialStatus)
  const requestIdRef = useRef(0)

  const fetchEvents = useCallback(
    async ({ from, to, status, signal } = {}) => {
      const requestId = requestIdRef.current + 1
      requestIdRef.current = requestId
      setLoading(true)
      setError('')
      try {
        const path = buildListPath({ from, to, status })
        const data = await request(path, { method: 'GET', signal })
        if (requestIdRef.current !== requestId) return null
        const list = Array.isArray(data?.events) ? data.events : []
        setEvents(list)
        return list
      } catch (err) {
        if (err?.name === 'AbortError') return null
        if (requestIdRef.current !== requestId) return null
        setError(humanizeApiError(err, 'Takvim yüklenemedi'))
        setEvents([])
        return null
      } finally {
        if (requestIdRef.current === requestId) setLoading(false)
      }
    },
    [request],
  )

  useEffect(() => {
    const controller = new AbortController()
    fetchEvents({
      status: statusFilter && statusFilter !== 'all' ? statusFilter : undefined,
      signal: controller.signal,
    })
    return () => controller.abort()
  }, [fetchEvents, statusFilter])

  const reload = useCallback(
    () =>
      fetchEvents({
        status: statusFilter && statusFilter !== 'all' ? statusFilter : undefined,
      }),
    [fetchEvents, statusFilter],
  )

  const createEvent = useCallback(
    async (payload) => {
      const data = await request('/v1/calendar/events', {
        method: 'POST',
        body: payload,
      })
      const ev = data?.event
      if (ev) {
        setEvents((prev) => [...prev, ev].sort(sortByDateThenTime))
      }
      return ev
    },
    [request],
  )

  const updateEvent = useCallback(
    async (eventId, patch) => {
      const data = await request(`/v1/calendar/events/${Number(eventId)}`, {
        method: 'PATCH',
        body: patch,
      })
      const ev = data?.event
      if (ev) {
        setEvents((prev) => {
          // If the updated event's status no longer matches the active
          // status filter (e.g. user just marked a "pending" event as
          // "done" while the list is showing only pending items), drop it
          // from the local list so it visibly "closes" without waiting
          // for a manual refresh.
          const filter = statusFilter
          const evStatus = String(ev?.status || '')
          const filterIsAll = !filter || filter === 'all'
          const matchesFilter = filterIsAll || evStatus === filter

          if (!matchesFilter) {
            return prev.filter((item) => Number(item.event_id) !== Number(eventId))
          }

          // Replace in place; if for some reason it isn't there yet (edge
          // case after a refetch race), append it so the user always sees
          // the latest state.
          let found = false
          const next = prev.map((item) => {
            if (Number(item.event_id) === Number(eventId)) {
              found = true
              return ev
            }
            return item
          })
          if (!found) next.push(ev)
          return next.sort(sortByDateThenTime)
        })
      }
      return ev
    },
    [request, statusFilter],
  )

  const deleteEvent = useCallback(
    async (eventId) => {
      await request(`/v1/calendar/events/${Number(eventId)}`, { method: 'DELETE' })
      setEvents((prev) => prev.filter((item) => Number(item.event_id) !== Number(eventId)))
    },
    [request],
  )

  const eventsByDate = useMemo(() => {
    const map = new Map()
    for (const ev of events) {
      const key = String(ev?.due_date || '').slice(0, 10)
      if (!key) continue
      const arr = map.get(key) || []
      arr.push(ev)
      map.set(key, arr)
    }
    return map
  }, [events])

  return {
    events,
    eventsByDate,
    loading,
    error,
    statusFilter,
    setStatusFilter,
    reload,
    createEvent,
    updateEvent,
    deleteEvent,
  }
}

function sortByDateThenTime(a, b) {
  const da = String(a?.due_date || '')
  const db = String(b?.due_date || '')
  if (da !== db) return da < db ? -1 : 1
  const ta = String(a?.due_time || '')
  const tb = String(b?.due_time || '')
  if (ta !== tb) return ta < tb ? -1 : 1
  return Number(a?.event_id || 0) - Number(b?.event_id || 0)
}
