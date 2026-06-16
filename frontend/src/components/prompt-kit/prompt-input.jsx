import { cn } from '@/lib/utils'
import { createContext, useContext, useLayoutEffect, useRef, useState } from 'react'

const PromptInputContext = createContext({
  isLoading: false,
  value: '',
  setValue: () => {},
  maxHeight: 240,
  onSubmit: undefined,
  disabled: false,
  textareaRef: { current: null },
})

function usePromptInput() {
  return useContext(PromptInputContext)
}

function PromptInput({
  className,
  isLoading = false,
  maxHeight = 240,
  value,
  onValueChange,
  onSubmit,
  children,
  disabled = false,
  onClick,
  ...props
}) {
  const [internalValue, setInternalValue] = useState(value || '')
  const textareaRef = useRef(null)

  const handleChange = (newValue) => {
    setInternalValue(newValue)
    onValueChange?.(newValue)
  }

  const handleClick = (e) => {
    // Don't focus textarea if click came from an interactive child (button, input, etc.)
    // — focusing textarea opens the mobile keyboard and can prevent file dialogs from opening.
    const interactive = e.target?.closest?.('button, a, input, label, [role="button"]')
    if (!disabled && !interactive) textareaRef.current?.focus()
    onClick?.(e)
  }

  return (
    <PromptInputContext.Provider
      value={{
        isLoading,
        value: value ?? internalValue,
        setValue: onValueChange ?? handleChange,
        maxHeight,
        onSubmit,
        disabled,
        textareaRef,
      }}
    >
      <div
        onClick={handleClick}
        className={cn(
          'border-input bg-background cursor-text rounded-3xl border p-2 shadow-xs',
          disabled && 'cursor-not-allowed opacity-60',
          className,
        )}
        {...props}
      >
        {children}
      </div>
    </PromptInputContext.Provider>
  )
}

function PromptInputTextarea({ className, onKeyDown, disableAutosize = false, ...props }) {
  const { value, setValue, maxHeight, onSubmit, disabled, textareaRef } = usePromptInput()

  const adjustHeight = (el) => {
    if (!el || disableAutosize) return
    el.style.height = 'auto'
    if (typeof maxHeight === 'number') {
      el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`
    } else {
      el.style.height = `min(${el.scrollHeight}px, ${maxHeight})`
    }
  }

  const handleRef = (el) => {
    textareaRef.current = el
    adjustHeight(el)
  }

  useLayoutEffect(() => {
    if (!textareaRef.current || disableAutosize) return
    const el = textareaRef.current
    el.style.height = 'auto'
    if (typeof maxHeight === 'number') {
      el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`
    } else {
      el.style.height = `min(${el.scrollHeight}px, ${maxHeight})`
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, maxHeight, disableAutosize])

  const handleChange = (e) => {
    adjustHeight(e.target)
    setValue(e.target.value)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onSubmit?.()
    }
    onKeyDown?.(e)
  }

  return (
    <textarea
      ref={handleRef}
      value={value}
      onChange={handleChange}
      onKeyDown={handleKeyDown}
      className={cn(
        'text-primary min-h-[44px] w-full resize-none border-none bg-transparent shadow-none outline-none focus-visible:ring-0 p-3',
        className,
      )}
      rows={1}
      disabled={disabled}
      {...props}
    />
  )
}

function PromptInputActions({ children, className, ...props }) {
  return (
    <div className={cn('flex items-center gap-2', className)} {...props}>
      {children}
    </div>
  )
}

function PromptInputAction({ tooltip, children, className, side = 'top', ...props }) {
  const { disabled } = usePromptInput()
  return (
    <div className={cn(disabled && 'opacity-50 pointer-events-none', className)} role="button" title={tooltip} {...props}>
      {children}
    </div>
  )
}

export { PromptInput, PromptInputTextarea, PromptInputActions, PromptInputAction, usePromptInput }
