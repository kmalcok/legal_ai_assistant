import { getApiBaseUrl } from '../../config/runtime.js'
import { getApiMessage } from './contracts.js'

export class ApiError extends Error {
  constructor(message, { status, data } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

async function readBody(res) {
  const ct = (res.headers.get('content-type') || '').toLowerCase()
  if (ct.includes('application/json')) return await res.json()
  return await res.text()
}

export async function apiRequest(path, { method = 'GET', body, headers, accessToken, signal } = {}) {
  const base = getApiBaseUrl()
  const url = `${base}${path.startsWith('/') ? path : `/${path}`}`
  const h = {
    ...(body ? { 'Content-Type': 'application/json' } : {}),
    ...(headers || {}),
    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
  }

  const res = await fetch(url, {
    method,
    headers: h,
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  })

  const data = await readBody(res)
  if (!res.ok) {
    const msg = getApiMessage({ status: res.status, data }, res.statusText || 'Request failed')
    throw new ApiError(String(msg), { status: res.status, data })
  }
  return data
}

