import { useEffect, useMemo, useRef, useState } from 'react'
import { useAuth } from '../../auth/useAuth.js'
import { getApiBaseUrl } from '../../../config/runtime.js'

function wsOriginFromApiBase(apiBase) {
  try {
    const base = (apiBase || '').trim()
    const origin = base ? new URL(base).origin : window.location.origin
    const u = new URL(origin)
    u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:'
    return u.origin
  } catch {
    // fallback: same-origin
    const u = new URL(window.location.origin)
    u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:'
    return u.origin
  }
}

function buildChatWsUrl({ chatId }) {
  const apiBase = getApiBaseUrl()
  const origin = wsOriginFromApiBase(apiBase)
  return `${origin}/v1/ws/chat/${encodeURIComponent(String(chatId))}`
}

/**
 * Connects to backend websocket channel for a chat:
 *   /v1/ws/chat/{chat_id}
 *
 * Server sends JSON messages (e.g. petition_progress / petition_ready / petition_failed).
 */
export function useChatWebSocket(chatId, { onEvent } = {}) {
  const { tokens, refresh } = useAuth()
  const [status, setStatus] = useState('disconnected') // disconnected | connecting | connected | error

  const chatIdNum = useMemo(() => (Number.isFinite(chatId) && chatId > 0 ? Number(chatId) : null), [chatId])

  const wsRef = useRef(null)
  const keepaliveRef = useRef(null)
  const didRetryAuthRef = useRef(false)
  const onEventRef = useRef(onEvent)

  // Avoid reconnecting on every render: keep latest handler in a ref.
  useEffect(() => {
    onEventRef.current = onEvent
  }, [onEvent])

  useEffect(() => {
    didRetryAuthRef.current = false
  }, [chatIdNum])

  useEffect(() => {
    if (!chatIdNum) {
      return
    }
    if (!tokens?.accessToken) {
      return
    }

    let cancelled = false

    const cleanup = () => {
      if (keepaliveRef.current) {
        clearInterval(keepaliveRef.current)
        keepaliveRef.current = null
      }
      try {
        wsRef.current?.close()
      } catch {
        // ignore
      }
      wsRef.current = null
    }

    const connect = async () => {
      cleanup()
      setStatus('connecting')

      const url = buildChatWsUrl({ chatId: chatIdNum })
      const protocols = tokens.accessToken ? ['bearer', tokens.accessToken] : undefined
      const ws = protocols ? new WebSocket(url, protocols) : new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        if (cancelled) return
        setStatus('connected')
        // keepalive (some proxies close idle ws connections)
        keepaliveRef.current = setInterval(() => {
          try {
            if (ws.readyState === WebSocket.OPEN) ws.send('ping')
          } catch {
            // ignore
          }
        }, 25_000)
      }

      ws.onmessage = (ev) => {
        if (cancelled) return
        const raw = ev?.data
        if (typeof raw !== 'string') return
        let msg
        try {
          msg = JSON.parse(raw)
        } catch {
          return
        }
        try {
          onEventRef.current?.(msg)
        } catch {
          // ignore user handler errors
        }
      }

      ws.onerror = () => {
        if (cancelled) return
        setStatus('error')
      }

      ws.onclose = async (ev) => {
        if (cancelled) return
        if (keepaliveRef.current) {
          clearInterval(keepaliveRef.current)
          keepaliveRef.current = null
        }

        // Backend uses 4401 for auth failures.
        if (ev?.code === 4401 && !didRetryAuthRef.current) {
          didRetryAuthRef.current = true
          try {
            await refresh()
            if (!cancelled) connect()
            return
          } catch {
            // fallthrough
          }
        }
        setStatus('disconnected')
      }
    }

    connect()

    return () => {
      cancelled = true
      cleanup()
    }
    // Intentionally depend on chatId + accessToken; refresh handles rotation internally.
  }, [chatIdNum, refresh, tokens?.accessToken])

  return { status: !chatIdNum || !tokens?.accessToken ? 'disconnected' : status }
}

