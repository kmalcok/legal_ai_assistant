import { CircleAlert } from 'lucide-react'

export function CreditBanner({
  title = 'Kredi bilgisi',
  message,
  compactMessage,
  tone = 'warning',
  actionLabel,
  onAction,
  contextual = false,
  compact = false,
}) {
  if (!message) return null

  const toneLabel = tone === 'warning' ? 'Kredi durumu' : 'Bilgi'
  const body = compact && compactMessage ? compactMessage : message

  return (
    <div className={`credit-banner ${tone}${compact ? ' compact' : ''}${contextual ? ' contextual' : ''}`} role="status" aria-live="polite">
      <div className="credit-banner-main">
        <div className="credit-banner-icon-wrap" aria-hidden="true">
          <CircleAlert className="credit-banner-icon" />
        </div>
        <div className="credit-banner-copy">
          <div className="credit-banner-meta">{toneLabel}</div>
          <div className="credit-banner-title">{title}</div>
          <div className="credit-banner-text">{body}</div>
        </div>
      </div>
      {actionLabel ? (
        <button className="credit-banner-action" type="button" onClick={onAction}>
          {actionLabel}
        </button>
      ) : null}
    </div>
  )
}
