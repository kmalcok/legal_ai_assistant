"use client"
import * as React from "react"
import { createPortal } from "react-dom"
import { cn } from "@/lib/utils"

const DropdownContext = React.createContext({ 
  open: false, 
  setOpen: () => {},
  triggerRect: null,
  setTriggerRect: () => {},
  id: ""
})

export function DropdownMenu({ children, onOpenChange }) {
  const [open, setOpen] = React.useState(false)
  const [triggerRect, setTriggerRect] = React.useState(null)
  const id = React.useId()
  
  const handleOpenChange = (v) => {
    setOpen(v)
    onOpenChange?.(v)
  }

  React.useEffect(() => {
    if (!open) return
    const listener = (e) => {
      // Find if the click was inside THIS dropdown (trigger or content)
      const closestDropdown = e.target.closest(`[data-dropdown-id="${id}"]`)
      if (closestDropdown) return

      // If clicked anywhere else (including another dropdown's trigger), close this one
      handleOpenChange(false)
    }
    
    // Close on scroll or resize to prevent misaligned portal
    const handleScroll = () => handleOpenChange(false)
    
    document.addEventListener('click', listener, true)
    window.addEventListener('scroll', handleScroll, true)
    window.addEventListener('resize', handleScroll)
    
    return () => {
      document.removeEventListener('click', listener, true)
      window.removeEventListener('scroll', handleScroll, true)
      window.removeEventListener('resize', handleScroll)
    }
  }, [open, id])

  return (
    <DropdownContext.Provider value={{ open, setOpen: handleOpenChange, triggerRect, setTriggerRect, id }}>
      {children}
    </DropdownContext.Provider>
  )
}

export const DropdownMenuTrigger = React.forwardRef(({ asChild, children, className, onClick, ...props }, ref) => {
  const { open, setOpen, setTriggerRect, id } = React.useContext(DropdownContext)
  
  const handleClick = (e) => {
    const rect = e.currentTarget.getBoundingClientRect()
    setTriggerRect(rect)
    onClick?.(e)
    setOpen(!open)
  }

  const triggerProps = {
    ...props,
    ref,
    "data-dropdown-id": id,
    "data-state": open ? "open" : "closed",
    onClick: handleClick
  }

  if (asChild && React.isValidElement(children)) {
    return React.cloneElement(children, {
      ...triggerProps,
      className: cn("dropdown-trigger-wrap", children.props.className),
      onClick: (e) => { 
        children.props.onClick?.(e); 
        handleClick(e); 
      }
    })
  }
  return (
    <button 
      {...triggerProps}
      className={cn("dropdown-trigger-wrap", className)} 
    >
      {children}
    </button>
  )
})
DropdownMenuTrigger.displayName = "DropdownMenuTrigger"

export const DropdownMenuContent = React.forwardRef(({ children, className, align = "center", side = "bottom", ...props }, ref) => {
  const { open, triggerRect, id } = React.useContext(DropdownContext)
  const [style, setStyle] = React.useState({})
  const [mounted, setMounted] = React.useState(false)

  React.useLayoutEffect(() => {
    if (!open || !triggerRect) {
      setMounted(false)
      return
    }
    
    const newStyle = {
      position: "fixed",
      zIndex: 1100,
      "--radix-dropdown-menu-trigger-width": `${triggerRect.width}px`
    }

    // Determine side with collision detection
    let finalSide = side
    const vh = window.innerHeight
    const vw = window.innerWidth
    
    // Estimate content size (rough but effective for flip logic)
    const estHeight = 220
    const estWidth = 160

    if (side === "bottom" && triggerRect.bottom + estHeight > vh) {
      finalSide = "top"
    } else if (side === "top" && triggerRect.top - estHeight < 0) {
      finalSide = "bottom"
    } else if (side === "right" && triggerRect.right + estWidth > vw) {
      finalSide = "left"
    } else if (side === "left" && triggerRect.left - estWidth < 0) {
      finalSide = "right"
    }

    // Primary axis
    if (finalSide === "top") {
      newStyle.bottom = vh - triggerRect.top + 8
    } else if (finalSide === "right") {
      newStyle.left = triggerRect.right + 8
    } else if (finalSide === "left") {
      newStyle.right = vw - triggerRect.left + 8
    } else {
      // bottom
      newStyle.top = triggerRect.bottom + 8
    }

    // Secondary axis (alignment)
    if (finalSide === "top" || finalSide === "bottom") {
      if (align === "start") {
        newStyle.left = triggerRect.left
      } else if (align === "end") {
        newStyle.right = vw - triggerRect.right
      } else {
        newStyle.left = triggerRect.left + (triggerRect.width / 2) - 80
      }
      
      // Horizontal overflow prevention
      if (newStyle.left !== undefined && newStyle.left + estWidth > vw) {
        delete newStyle.left
        newStyle.right = 8
      }
      if (newStyle.right !== undefined && vw - newStyle.right - estWidth < 0) {
        delete newStyle.right
        newStyle.left = 8
      }
    } else {
      // side is left or right
      if (align === "start") {
        newStyle.top = triggerRect.top
      } else if (align === "end") {
        newStyle.bottom = vh - triggerRect.bottom
      } else {
        newStyle.top = triggerRect.top + (triggerRect.height / 2) - 40
      }

      // Vertical overflow prevention
      if (newStyle.top !== undefined && newStyle.top + estHeight > vh) {
        delete newStyle.top
        newStyle.bottom = 8
      }
      if (newStyle.bottom !== undefined && vh - newStyle.bottom - estHeight < 0) {
        delete newStyle.bottom
        newStyle.top = 8
      }
    }

    setStyle(newStyle)
    setMounted(true)
  }, [open, triggerRect, side, align])

  if (!open || !triggerRect || !mounted) return null
  
  return createPortal(
    <div 
      ref={ref} 
      style={style}
      data-dropdown-id={id}
      className={cn(
        "dropdown-content-wrap fixed z-50 min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md animate-in fade-in-80",
        className
      )} 
      {...props}
    >
      {children}
    </div>,
    document.body
  )
})
DropdownMenuContent.displayName = "DropdownMenuContent"

export const DropdownMenuItem = React.forwardRef(({ className, inset, onClick, ...props }, ref) => {
  const { setOpen } = React.useContext(DropdownContext)
  return (
    <div
      ref={ref}
      className={cn("relative flex cursor-default select-none items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none transition-colors hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50", inset && "pl-8", className)}
      onClick={(e) => { 
        onClick?.(e)
        setTimeout(() => setOpen(false), 50)
      }}
      {...props}
    />
  )
})
DropdownMenuItem.displayName = "DropdownMenuItem"

export const DropdownMenuSeparator = React.forwardRef(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("-mx-1 my-1 h-px bg-muted", className)} {...props} />
))
DropdownMenuSeparator.displayName = "DropdownMenuSeparator"

export const DropdownMenuLabel = React.forwardRef(({ className, inset, ...props }, ref) => (
  <div ref={ref} className={cn("px-2 py-1.5 text-sm font-semibold", inset && "pl-8", className)} {...props} />
))
DropdownMenuLabel.displayName = "DropdownMenuLabel"

export const DropdownMenuGroup = ({ children }) => <>{children}</>
