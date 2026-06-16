import { cn } from '@/lib/utils'

function Message({ children, className, ...props }) {
  return (
    <div className={cn('flex gap-3', className)} {...props}>
      {children}
    </div>
  )
}

function MessageAvatar({ src, alt, fallback, className }) {
  return (
    <div
      className={cn(
        'h-8 w-8 shrink-0 rounded-full bg-muted flex items-center justify-center overflow-hidden text-xs font-semibold text-muted-foreground select-none',
        className,
      )}
    >
      {src ? (
        <img src={src} alt={alt} className="h-full w-full object-cover" />
      ) : (
        <span>{fallback || alt?.charAt(0)?.toUpperCase() || '?'}</span>
      )}
    </div>
  )
}

function MessageContent({ children, className, ...props }) {
  return (
    <div
      className={cn('rounded-2xl p-3 text-foreground break-words whitespace-normal min-w-0', className)}
      {...props}
    >
      {children}
    </div>
  )
}

function MessageActions({ children, className, ...props }) {
  return (
    <div className={cn('text-muted-foreground flex items-center gap-2', className)} {...props}>
      {children}
    </div>
  )
}

export { Message, MessageAvatar, MessageContent, MessageActions }
