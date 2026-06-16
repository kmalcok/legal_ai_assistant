import { cn } from '@/lib/utils'

function TypingLoader({ className, size = 'md' }) {
  const dotSizes = {
    sm: 'h-1 w-1',
    md: 'h-1.5 w-1.5',
    lg: 'h-2 w-2',
  }

  return (
    <div className={cn('flex items-center space-x-1.5 py-1', className)}>
      {[...Array(3)].map((_, i) => (
        <div
          key={i}
          className={cn(
            'bg-muted-foreground/60 rounded-full animate-[pk-typing_1s_infinite]',
            dotSizes[size],
          )}
          style={{ animationDelay: `${i * 250}ms` }}
        />
      ))}
      <span className="sr-only">Loading</span>
    </div>
  )
}

function TextShimmerLoader({ text = 'Düşünüyor', className, size = 'md' }) {
  const textSizes = {
    sm: 'text-xs',
    md: 'text-sm',
    lg: 'text-base',
  }

  return (
    <div
      className={cn(
        'bg-[linear-gradient(to_right,var(--muted-foreground)_40%,var(--foreground)_60%,var(--muted-foreground)_80%)]',
        'bg-[length:200%_auto] bg-clip-text font-medium text-transparent',
        'animate-[pk-shimmer_4s_infinite_linear]',
        textSizes[size],
        className,
      )}
    >
      {text}
    </div>
  )
}

function Loader({ variant = 'typing', size = 'md', text, className }) {
  switch (variant) {
    case 'typing':
      return <TypingLoader size={size} className={className} />
    case 'text-shimmer':
      return <TextShimmerLoader text={text} size={size} className={className} />
    default:
      return <TypingLoader size={size} className={className} />
  }
}

export { Loader, TypingLoader, TextShimmerLoader }
