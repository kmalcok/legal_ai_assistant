export function getApiBaseUrl() {
  // Prefer Vite env so local/project `.env` is the primary source of truth.
  // Fall back to runtime-injected config only when the env is empty.
  const fromEnv = import.meta.env.VITE_API_BASE_URL
  const fromWindow = window?.__APP_CONFIG__?.API_BASE_URL
  const raw = (typeof fromEnv === 'string' && fromEnv.trim() ? fromEnv : fromWindow) || ''
  return String(raw).replace(/\/+$/, '')
}

export function getDemoVideoUrl() {
  const fromEnv = import.meta.env.VITE_DEMO_VIDEO_URL
  const fromWindow = window?.__APP_CONFIG__?.DEMO_VIDEO_URL
  const raw =
    (typeof fromEnv === 'string' && fromEnv.trim() ? fromEnv : fromWindow) ||
    '/videos/yargucu-demo.mp4'

  return String(raw).trim() || '/videos/yargucu-demo.mp4'
}

