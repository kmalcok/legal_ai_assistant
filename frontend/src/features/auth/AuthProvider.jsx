import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { apiRequest, ApiError } from '../../shared/api/client.js'
import { getApiBaseUrl } from '../../config/runtime.js'
import { AuthContext } from './AuthContext.js'

const STORAGE_KEY = 'mevzuat.auth.v1'

function loadStored() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed?.accessToken || !parsed?.refreshToken) return null
    return parsed
  } catch {
    return null
  }
}

function storeNext(next) {
  if (!next) {
    localStorage.removeItem(STORAGE_KEY)
    return
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
}

function normalizeTokens(tokens) {
  if (!tokens) return null
  return {
    accessToken: tokens.access_token ?? tokens.accessToken,
    refreshToken: tokens.refresh_token ?? tokens.refreshToken,
    accessExpiresAt: tokens.access_expires_at ?? tokens.accessExpiresAt,
    refreshExpiresAt: tokens.refresh_expires_at ?? tokens.refreshExpiresAt,
    userId: tokens.user_id ?? tokens.userId,
  }
}

function buildAuthedFetchOptions({ method = 'GET', body, headers, signal, token } = {}) {
  const isJsonBody =
    body !== undefined &&
    body !== null &&
    !(body instanceof FormData) &&
    !(body instanceof URLSearchParams) &&
    !(body instanceof Blob) &&
    !(body instanceof ArrayBuffer) &&
    typeof body !== 'string'

  return {
    method,
    headers: {
      ...(isJsonBody ? { 'Content-Type': 'application/json' } : {}),
      ...(headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body === undefined ? undefined : isJsonBody ? JSON.stringify(body) : body,
    signal,
  }
}

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(() => loadStored())
  const [user, setUser] = useState(null)
  const [bootstrapped, setBootstrapped] = useState(false)
  const [authPending, setAuthPending] = useState(false)

  // Keep a ref so refresh logic always has the latest tokens (avoid stale closures)
  const authRef = useRef(auth)
  useEffect(() => {
    authRef.current = auth
  }, [auth])

  // Rotating refresh tokens: ensure only ONE refresh request is in-flight at a time.
  const refreshInFlightRef = useRef(null)

  const setTokens = useCallback((tokens) => {
    const next = normalizeTokens(tokens)
    authRef.current = next
    setAuth(next)
    storeNext(next)
  }, [])

  const refresh = useCallback(async () => {
    const current = authRef.current
    if (!current?.refreshToken) throw new Error('Missing refresh token')

    if (refreshInFlightRef.current) return await refreshInFlightRef.current

    const usedRefreshToken = current.refreshToken
    const p = (async () => {
      try {
        const data = await apiRequest('/v1/auth/refresh', {
          method: 'POST',
          body: { refresh_token: usedRefreshToken },
        })
        const next = normalizeTokens(data)
        setTokens(next)
        return next
      } catch (err) {
        // If another tab already refreshed (rotated), pick up its stored tokens and continue.
        if (err instanceof ApiError && err.status === 401) {
          const reason = err?.data?.detail?.reason || err?.data?.reason
          if (reason === 'refresh_already_rotated') {
            const stored = loadStored()
            if (stored?.accessToken && stored?.refreshToken && stored.refreshToken !== usedRefreshToken) {
              authRef.current = stored
              setAuth(stored)
              return stored
            }
          }
        }
        throw err
      } finally {
        refreshInFlightRef.current = null
      }
    })()

    refreshInFlightRef.current = p
    return await p
  }, [setTokens])

  const authedRequest = useCallback(
    async (path, opts = {}) => {
      try {
        return await apiRequest(path, { ...opts, accessToken: authRef.current?.accessToken })
      } catch (err) {
        if (!(err instanceof ApiError) || err.status !== 401) throw err
        if (!authRef.current?.refreshToken) throw err
        // try refresh once (singleflight), then retry
        const next = await refresh()
        return await apiRequest(path, { ...opts, accessToken: next?.accessToken })
      }
    },
    [refresh],
  )

  const authedStream = useCallback(
    async (path, { method = 'GET', body, headers, signal } = {}) => {
      const doFetch = async (token) => {
        const url = getApiBaseUrl() + (path.startsWith('/') ? path : `/${path}`)
        return await fetch(url, buildAuthedFetchOptions({ method, body, headers, signal, token }))
      }

      let res = await doFetch(authRef.current?.accessToken)
      if (res.status === 401 && authRef.current?.refreshToken) {
        const next = await refresh()
        res = await doFetch(next?.accessToken)
      }
      return res
    },
    [refresh],
  )

  const authedFetch = useCallback(
    async (path, { method = 'GET', body, headers, signal } = {}) => {
      const doFetch = async (token) => {
        const url = getApiBaseUrl() + (path.startsWith('/') ? path : `/${path}`)
        return await fetch(url, buildAuthedFetchOptions({ method, body, headers, signal, token }))
      }

      let res = await doFetch(authRef.current?.accessToken)
      if (res.status === 401 && authRef.current?.refreshToken) {
        const next = await refresh()
        res = await doFetch(next?.accessToken)
      }
      return res
    },
    [refresh],
  )

  const fetchMe = useCallback(async () => {
    const data = await authedRequest('/v1/auth/me')
    setUser(data.user || null)
    return data.user || null
  }, [authedRequest])

  const refreshMe = useCallback(async () => {
    return await fetchMe()
  }, [fetchMe])

  const hydrateSession = useCallback(
    async (tokens) => {
      setAuthPending(true)
      setTokens(tokens)
      try {
        return await fetchMe()
      } catch (err) {
        setUser(null)
        setTokens(null)
        throw err
      } finally {
        setAuthPending(false)
        setBootstrapped(true)
      }
    },
    [fetchMe, setTokens],
  )

  const login = useCallback(
    async ({ identifier, password }) => {
      const data = await apiRequest('/v1/auth/login', {
        method: 'POST',
        body: { identifier, password },
      })
      await hydrateSession(data)
      return data
    },
    [hydrateSession],
  )

  const register = useCallback(
    async ({ username, email, full_name, password }) => {
      const data = await apiRequest('/v1/auth/register', {
        method: 'POST',
        body: { username, email, full_name, password },
      })
      await hydrateSession(data)
      return data
    },
    [hydrateSession],
  )

  const logout = useCallback(async () => {
    const refreshToken = authRef.current?.refreshToken
    const accessToken = authRef.current?.accessToken
    setTokens(null)
    setUser(null)
    if (refreshToken) {
      try {
        await apiRequest('/v1/auth/logout', {
          method: 'POST',
          body: { refresh_token: refreshToken },
          accessToken,
        })
      } catch {
        // ignore
      }
    }
  }, [setTokens])

  // bootstrap user if we already have a token
  useEffect(() => {
    let cancelled = false
    async function run() {
      try {
        if (authRef.current?.accessToken) await fetchMe()
      } catch {
        // token might be stale; clear for safety
        if (!cancelled) setTokens(null)
      } finally {
        if (!cancelled) setBootstrapped(true)
      }
    }
    run()
    return () => {
      cancelled = true
    }
  }, [fetchMe, setTokens])

  // Cross-tab sync: pick up refreshed tokens from other tabs (important with rotating refresh tokens).
  useEffect(() => {
    function onStorage(e) {
      if (e.key !== STORAGE_KEY) return
      const next = loadStored()
      authRef.current = next
      setAuth(next)
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  const value = useMemo(
    () => ({
      bootstrapped: bootstrapped && !authPending,
      user,
      isAuthed: Boolean(auth?.accessToken && user),
      tokens: auth,
      login,
      register,
      logout,
      refresh,
      refreshMe,
      request: authedRequest,
      fetch: authedFetch,
      stream: authedStream,
      setTokens,
    }),
    [auth, authPending, authedFetch, authedRequest, authedStream, bootstrapped, login, logout, refresh, refreshMe, register, setTokens, user],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

