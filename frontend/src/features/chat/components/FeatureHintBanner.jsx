import { CircleAlertIcon, XIcon } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'

export function FeatureHintBanner({ hint, onDismiss }) {
  if (!hint) return null

  return (
    <div className="w-full flex justify-center px-4 py-2 animate-in fade-in slide-in-from-bottom-2 duration-500">
      <Alert className="flex w-full max-w-xl justify-between gap-3 border-none bg-primary text-primary-foreground shadow-2xl">
        <CircleAlertIcon />
        <div className="flex min-w-0 flex-1 flex-col gap-4">
          <div className="flex flex-col justify-center gap-1">
            <AlertTitle>{hint.title}</AlertTitle>
            <AlertDescription className="text-primary-foreground/80">
              {hint.subtitle}
            </AlertDescription>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              type="button"
              className="h-7 cursor-pointer rounded-md bg-secondary/10 px-2 text-primary-foreground hover:bg-secondary/20 focus-visible:bg-secondary/20"
              onClick={onDismiss}
            >
              Şimdilik geç
            </Button>
            <Button
              type="button"
              variant="secondary"
              className="h-7 cursor-pointer rounded-md px-2"
              onClick={hint.onAction}
            >
              {hint.actionLabel || 'AI İçtihat Arama'}
            </Button>
          </div>
        </div>
        <button
          type="button"
          onClick={onDismiss}
          className="size-5 shrink-0 cursor-pointer text-primary-foreground/80 hover:text-primary-foreground"
          aria-label="Kapat"
        >
          <XIcon />
        </button>
      </Alert>
    </div>
  )
}
