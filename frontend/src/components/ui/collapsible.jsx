"use client"
import * as React from "react"

import { cn } from "@/lib/utils"

const CollapsibleContext = React.createContext({ open: false, onOpenChange: () => {} })

export function Collapsible({ defaultOpen = false, open: controlledOpen, onOpenChange, children, className, asChild }) {
  const [uncontrolled, setUncontrolled] = React.useState(defaultOpen)
  const isControlled = controlledOpen !== undefined
  const open = isControlled ? controlledOpen : uncontrolled
  const handleOpenChange = (v) => {
    if (!isControlled) setUncontrolled(v)
    onOpenChange?.(v)
  }
  
  if (asChild && React.isValidElement(children)) {
    return (
      <CollapsibleContext.Provider value={{ open, onOpenChange: handleOpenChange }}>
        {React.cloneElement(children, {
          "data-state": open ? "open" : "closed",
          className: cn(children.props.className, className),
        })}
      </CollapsibleContext.Provider>
    )
  }
  
  return (
    <div data-state={open ? "open" : "closed"} className={className}>
      <CollapsibleContext.Provider value={{ open, onOpenChange: handleOpenChange }}>
        {children}
      </CollapsibleContext.Provider>
    </div>
  )
}

export const CollapsibleTrigger = React.forwardRef(({ asChild, children, className, onClick, ...props }, ref) => {
  const { open, onOpenChange } = React.useContext(CollapsibleContext)
  const handleClick = (e) => {
    onClick?.(e)
    onOpenChange(!open)
  }
  
  if (asChild && React.isValidElement(children)) {
    return React.cloneElement(children, {
      ...props,
      ref,
      onClick: (e) => { children.props.onClick?.(e); handleClick(e); },
      "data-state": open ? "open" : "closed"
    })
  }

  return (
    <button ref={ref} onClick={handleClick} data-state={open ? "open" : "closed"} className={className} {...props}>
      {children}
    </button>
  )
})
CollapsibleTrigger.displayName = "CollapsibleTrigger"

export const CollapsibleContent = React.forwardRef(({ children, className, forceMount, ...props }, ref) => {
  const { open } = React.useContext(CollapsibleContext)
  if (!open && !forceMount) return null
  return (
    <div ref={ref} data-state={open ? "open" : "closed"} className={className} {...props}>
      {children}
    </div>
  )
})
CollapsibleContent.displayName = "CollapsibleContent"
