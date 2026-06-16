import { useEffect, useMemo, useState } from 'react'
import { CheckCheckIcon, CircleAlertIcon, TriangleAlertIcon, X } from 'lucide-react'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'

/**
 * Minimal toast host.
 * toast: {
 *   id,
 *   kind: 'dilekce'|'word'|'upload-success'|'upload-format-warning'|'upload-error',
 *   title,
 *   subtitle,
 *   actionLabel,
 *   onAction,
 *   secondaryActionLabel,
 *   onSecondaryAction,
 *   ttlMs
 * }
 */
export function ToastHost({ toasts, onRequestClose }) {
  useEffect(() => {
    // Auto-dismiss only those with ttlMs
    if (!Array.isArray(toasts) || toasts.length === 0) return
    const timers = []
    for (const t of toasts) {
      if (!t?.id || !t?.ttlMs) continue
      timers.push(
        setTimeout(() => {
          onRequestClose?.(t.id)
        }, Number(t.ttlMs)),
      )
    }
    return () => timers.forEach((x) => clearTimeout(x))
  }, [onRequestClose, toasts])

  if (!Array.isArray(toasts) || toasts.length === 0) return null

  return (
    <div className="toast-host" role="region" aria-label="Bildirimler">
      {toasts.map((t) => {
        if (t?.kind === 'hint') {
          return (
            <Alert
              key={t.id}
              className="w-full gap-2 border-amber-200 bg-amber-50/95 pr-11 shadow-lg backdrop-blur supports-[backdrop-filter]:bg-amber-50/90 dark:border-amber-900/60 dark:bg-amber-950/85"
              role="status"
            >
              <Button
                variant="ghost"
                size="icon-xs"
                type="button"
                aria-label="Kapat"
                className="absolute top-2 right-2 text-amber-900/70 hover:bg-amber-100 hover:text-amber-950 dark:text-amber-200/70 dark:hover:bg-amber-900/70 dark:hover:text-amber-50"
                onClick={() => onRequestClose?.(t.id)}
              >
                <X />
              </Button>

              <AlertTitle className="pr-14 text-sm font-semibold text-amber-950 dark:text-amber-100">
                {t.title}
              </AlertTitle>
              {t.subtitle ? (
                <AlertDescription className="pr-1 text-[13px] leading-5 text-amber-900/85 dark:text-amber-200/85">
                  {t.subtitle}
                </AlertDescription>
              ) : null}

              {t.actionLabel ? (
                <AlertAction className="static mt-1">
                  <Button
                    variant="outline"
                    size="sm"
                    type="button"
                    className="border-amber-300 bg-amber-100/90 text-amber-950 hover:bg-amber-100 dark:border-amber-800 dark:bg-amber-900/60 dark:text-amber-100 dark:hover:bg-amber-900"
                    onClick={() => t.onAction?.()}
                  >
                    {t.actionLabel}
                  </Button>
                </AlertAction>
              ) : null}
            </Alert>
          )
        }

        if (t?.kind === 'upload-success') {
          return (
            <Alert
              key={t.id}
              className="w-full border-none bg-green-600/10 pr-10 text-green-600 shadow-lg backdrop-blur dark:bg-green-400/10 dark:text-green-400"
              role="status"
            >
              <CheckCheckIcon />
              <Button
                variant="ghost"
                size="icon-xs"
                type="button"
                aria-label="Kapat"
                className="absolute top-2 right-2 text-green-700/70 hover:bg-green-600/10 hover:text-green-800 dark:text-green-300/70 dark:hover:bg-green-400/10 dark:hover:text-green-200"
                onClick={() => onRequestClose?.(t.id)}
              >
                <X data-icon="inline-start" />
              </Button>
              <AlertTitle>{t.title || 'Belge başarıyla yüklendi'}</AlertTitle>
              <AlertDescription className="text-green-600/80 dark:text-green-400/80">
                {t.subtitle || 'Dokümanınız kaydedildi ve artık dosyalarınızda kullanılabilir.'}
              </AlertDescription>
            </Alert>
          )
        }

        if (t?.kind === 'upload-format-warning') {
          return (
            <Alert
              key={t.id}
              className="w-full border-none bg-primary/10 pr-10 shadow-lg backdrop-blur"
            >
              <CircleAlertIcon />
              <Button
                variant="ghost"
                size="icon-xs"
                type="button"
                aria-label="Kapat"
                className="absolute top-2 right-2 text-foreground/60 hover:bg-primary/10 hover:text-foreground"
                onClick={() => onRequestClose?.(t.id)}
              >
                <X data-icon="inline-start" />
              </Button>
              <AlertTitle>{t.title || 'Dosya PDF, DOCX veya UDF olmalıdır.'}</AlertTitle>
              <AlertDescription>
                {t.subtitle || 'PDF, DOCX veya UDF dosyası yükleyin.'}
              </AlertDescription>
            </Alert>
          )
        }

        if (t?.kind === 'upload-error') {
          return (
            <Alert
              key={t.id}
              className="w-full border-none bg-destructive/10 pr-10 text-destructive shadow-lg backdrop-blur"
            >
              <TriangleAlertIcon />
              <Button
                variant="ghost"
                size="icon-xs"
                type="button"
                aria-label="Kapat"
                className="absolute top-2 right-2 text-destructive/70 hover:bg-destructive/10 hover:text-destructive"
                onClick={() => onRequestClose?.(t.id)}
              >
                <X data-icon="inline-start" />
              </Button>
              <AlertTitle>{t.title || 'Yükleme başarısız'}</AlertTitle>
              <AlertDescription className="text-destructive/80">
                {t.subtitle || 'Bir hata oluştu. Tekrar deneyin veya farklı bir dosya formatı kullanın.'}
              </AlertDescription>
            </Alert>
          )
        }

        return (
          <div key={t.id} className={`toast${t?.kind ? ` toast-${String(t.kind)}` : ''}`} role="status">
            <div className="toast-top">
              <div className="toast-text">
                <div className="toast-title">{t.title}</div>
                {t.subtitle ? <div className="toast-subtitle">{t.subtitle}</div> : null}
              </div>
              <button className="toast-close" type="button" aria-label="Kapat" onClick={() => onRequestClose?.(t.id)}>
                ×
              </button>
            </div>

            {Array.isArray(t.downloadOptions) && t.downloadOptions.length ? (
              <ToastDownloadDropdown toast={t} />
            ) : t.actionLabel || t.secondaryActionLabel ? (
              <div className="toast-actions">
                {t.actionLabel ? (
                  <button className="toast-action" type="button" onClick={() => t.onAction?.()}>
                    {t.actionLabel}
                  </button>
                ) : null}
                {t.secondaryActionLabel ? (
                  <button className="toast-action secondary" type="button" onClick={() => t.onSecondaryAction?.()}>
                    {t.secondaryActionLabel}
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}

function ToastDownloadDropdown({ toast }) {
  const opts = useMemo(() => (Array.isArray(toast.downloadOptions) ? toast.downloadOptions : []), [toast.downloadOptions])
  const [value, setValue] = useState(() => opts[0]?.value || 'original')

  return (
    <div className="toast-actions">
      <select className="toast-select" value={value} onChange={(e) => setValue(e.target.value)} aria-label="Format seç">
        {opts.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <button className="toast-action" type="button" onClick={() => toast.onDownloadOption?.(value)}>
        İndir
      </button>
    </div>
  )
}
