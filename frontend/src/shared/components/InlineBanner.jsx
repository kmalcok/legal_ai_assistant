import { AlertCircle, CheckCircle2, Info, TriangleAlert } from 'lucide-react'

import { cn } from '@/lib/utils.js'

const TONE_STYLES = {
  error: {
    icon: AlertCircle,
    className: 'border-red-200 bg-red-50 text-red-800',
    iconClassName: 'text-red-600',
    title: 'Hata',
  },
  warning: {
    icon: TriangleAlert,
    className: 'border-amber-200 bg-amber-50 text-amber-900',
    iconClassName: 'text-amber-600',
    title: 'Uyarı',
  },
  info: {
    icon: Info,
    className: 'border-sky-200 bg-sky-50 text-sky-900',
    iconClassName: 'text-sky-600',
    title: 'Bilgi',
  },
  success: {
    icon: CheckCircle2,
    className: 'border-emerald-200 bg-emerald-50 text-emerald-900',
    iconClassName: 'text-emerald-600',
    title: 'Başarılı',
  },
}

export function InlineBanner({
  tone = 'info',
  title,
  message,
  className,
}) {
  if (!message) return null

  const config = TONE_STYLES[tone] || TONE_STYLES.info
  const Icon = config.icon

  return (
    <div
      className={cn(
        'flex items-start gap-3 rounded-md border p-3 text-sm animate-in fade-in slide-in-from-bottom-2',
        config.className,
        className,
      )}
      role={tone === 'error' || tone === 'warning' ? 'alert' : 'status'}
      aria-live="polite"
    >
      <Icon className={cn('mt-0.5 h-4 w-4 shrink-0', config.iconClassName)} />
      <div className="min-w-0">
        <div className="font-semibold">{title || config.title}</div>
        <div className="mt-0.5 leading-5">{message}</div>
      </div>
    </div>
  )
}
