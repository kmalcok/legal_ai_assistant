import { useEffect, useState } from 'react'
import {
  applyPwaUpdate,
  PWA_OFFLINE_READY_EVENT,
  PWA_UPDATE_READY_EVENT,
} from './registerPwa.js'

function getInitialOnlineStatus() {
  if (typeof navigator === 'undefined') return true
  return navigator.onLine
}

export function PwaStatus() {
  const [isOnline, setIsOnline] = useState(getInitialOnlineStatus)
  const [isOfflineReady, setIsOfflineReady] = useState(false)
  const [isUpdateReady, setIsUpdateReady] = useState(false)

  useEffect(() => {
    const handleOnline = () => setIsOnline(true)
    const handleOffline = () => setIsOnline(false)
    const handleOfflineReady = () => setIsOfflineReady(true)
    const handleUpdateReady = () => setIsUpdateReady(true)

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    window.addEventListener(PWA_OFFLINE_READY_EVENT, handleOfflineReady)
    window.addEventListener(PWA_UPDATE_READY_EVENT, handleUpdateReady)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
      window.removeEventListener(PWA_OFFLINE_READY_EVENT, handleOfflineReady)
      window.removeEventListener(PWA_UPDATE_READY_EVENT, handleUpdateReady)
    }
  }, [])

  useEffect(() => {
    if (!isOfflineReady) return undefined

    const timeoutId = window.setTimeout(() => {
      setIsOfflineReady(false)
    }, 6000)

    return () => window.clearTimeout(timeoutId)
  }, [isOfflineReady])

  if (!isOnline) {
    return (
      <PwaNotice
        kind="offline"
        title="Bağlantı yok"
        message="Önceden açılan sayfalar kullanılabilir. Yeni işlemler bağlantı geri geldiğinde devam eder."
      />
    )
  }

  if (isUpdateReady) {
    return (
      <PwaNotice
        kind="update"
        title="Yeni sürüm hazır"
        message="En güncel sürüme geçmek için sayfayı yenile."
        primaryActionLabel="Yenile"
        onPrimaryAction={applyPwaUpdate}
        secondaryActionLabel="Sonra"
        onSecondaryAction={() => setIsUpdateReady(false)}
      />
    )
  }

  if (isOfflineReady) {
    return (
      <PwaNotice
        kind="ready"
        title="Çevrimdışı kullanım hazır"
        message="Uygulama kabuğu ve statik varlıklar bu cihazda hazır."
        secondaryActionLabel="Kapat"
        onSecondaryAction={() => setIsOfflineReady(false)}
      />
    )
  }

  return null
}

function PwaNotice({
  kind,
  title,
  message,
  primaryActionLabel,
  onPrimaryAction,
  secondaryActionLabel,
  onSecondaryAction,
}) {
  const isOffline = kind === 'offline'
  const ariaMode = isOffline ? 'assertive' : 'polite'

  return (
    <div className={`pwa-status pwa-status--${kind}`} role={isOffline ? 'alert' : 'status'} aria-live={ariaMode}>
      <div className="pwa-status__panel">
        <div className="pwa-status__text">
          <div className="pwa-status__title">{title}</div>
          <div className="pwa-status__message">{message}</div>
        </div>
        {primaryActionLabel || secondaryActionLabel ? (
          <div className="pwa-status__actions">
            {secondaryActionLabel ? (
              <button className="pwa-status__button pwa-status__button--secondary" type="button" onClick={onSecondaryAction}>
                {secondaryActionLabel}
              </button>
            ) : null}
            {primaryActionLabel ? (
              <button className="pwa-status__button" type="button" onClick={onPrimaryAction}>
                {primaryActionLabel}
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  )
}
