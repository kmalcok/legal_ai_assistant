import { ApiError } from './client.js'
import { getApiMessage } from './contracts.js'

async function readResponseData(res) {
  const ct = (res.headers.get('content-type') || '').toLowerCase()
  if (ct.includes('application/json')) return await res.json()
  return await res.text()
}

export async function assertResponseOk(res, fallback = 'Request failed') {
  if (res.ok) return res
  const data = await readResponseData(res)
  const message = getApiMessage({ status: res.status, data }, fallback)
  throw new ApiError(message, { status: res.status, data })
}

export function getDownloadFilename(res, fallbackFilename) {
  const cd = res.headers.get('content-disposition') || ''
  const match = cd.match(/filename="([^"]+)"/i)
  return (match && match[1]) || fallbackFilename || 'download.bin'
}

export async function downloadBlobResponse(res, fallbackFilename) {
  const filename = getDownloadFilename(res, fallbackFilename)
  const blob = await res.blob()
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(objectUrl)
}
