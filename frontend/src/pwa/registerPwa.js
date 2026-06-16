import { registerSW } from 'virtual:pwa-register'

export const PWA_OFFLINE_READY_EVENT = 'yargucu:pwa-offline-ready'
export const PWA_UPDATE_READY_EVENT = 'yargucu:pwa-update-ready'

const SW_UPDATE_INTERVAL_MS = 60 * 60 * 1000

let updateServiceWorker = null

function isStandaloneDisplayMode() {
  if (typeof window === 'undefined') return false

  return (
    window.matchMedia?.('(display-mode: standalone)')?.matches ||
    window.matchMedia?.('(display-mode: fullscreen)')?.matches ||
    window.navigator?.standalone === true
  )
}

function syncStandaloneClass() {
  if (typeof document === 'undefined') return
  document.documentElement.classList.toggle('is-pwa-standalone', isStandaloneDisplayMode())
}

export function registerPwa() {
  syncStandaloneClass()

  if (typeof window === 'undefined') return

  window.matchMedia?.('(display-mode: standalone)')?.addEventListener?.('change', syncStandaloneClass)
  window.matchMedia?.('(display-mode: fullscreen)')?.addEventListener?.('change', syncStandaloneClass)

  if (import.meta.env.DEV || !('serviceWorker' in navigator)) return

  const updateSW = registerSW({
    immediate: true,
    onNeedRefresh() {
      updateServiceWorker = updateSW
      window.dispatchEvent(new CustomEvent(PWA_UPDATE_READY_EVENT))
    },
    onOfflineReady() {
      window.dispatchEvent(new CustomEvent(PWA_OFFLINE_READY_EVENT))
    },
    onRegisteredSW(_swUrl, registration) {
      if (!registration) return

      window.setInterval(() => {
        registration.update().catch(() => {})
      }, SW_UPDATE_INTERVAL_MS)
    },
    onRegisterError(error) {
      console.error('PWA service worker registration failed', error)
    },
  })

  updateServiceWorker = updateSW
}

export function applyPwaUpdate() {
  updateServiceWorker?.(true)
}
