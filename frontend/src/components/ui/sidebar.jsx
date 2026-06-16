"use client"
import * as React from "react"
import "./sidebar.css"
import { cn } from "@/lib/utils"
import { PanelLeft } from "lucide-react"

const SIDEBAR_COOKIE_NAME = "sidebar_state"
const SIDEBAR_COOKIE_MAX_AGE = 60 * 60 * 24 * 7
const SIDEBAR_WIDTH = "16rem"
const SIDEBAR_WIDTH_MOBILE = "18rem"
const SIDEBAR_WIDTH_ICON = "3rem"
const SIDEBAR_KEYBOARD_SHORTCUT = "b"

const SidebarContext = React.createContext({ 
  isMobile: false, 
  open: true, 
  setOpen: () => {}, 
  toggleSidebar: () => {},
  state: "expanded",
  openMobile: false,
  setOpenMobile: () => {},
})

export function useSidebar() {
  return React.useContext(SidebarContext)
}

export const SidebarProvider = React.forwardRef(({ 
  defaultOpen = true, 
  open: controlledOpen, 
  onOpenChange, 
  storageKey = SIDEBAR_COOKIE_NAME,
  mobileBreakpoint = 768, 
  children, 
  className, 
  style, 
  ...props 
}, ref) => {
  const [uncontrolledOpen, setUncontrolledOpen] = React.useState(defaultOpen)
  const isControlled = controlledOpen !== undefined
  const open = isControlled ? controlledOpen : uncontrolledOpen
  // Keep latest values in refs so callbacks below always read fresh state
  // (avoids stale closures that can swallow the first toggle on mobile).
  const openRef = React.useRef(open)
  React.useEffect(() => { openRef.current = open }, [open])
  const isControlledRef = React.useRef(isControlled)
  React.useEffect(() => { isControlledRef.current = isControlled }, [isControlled])
  const onOpenChangeRef = React.useRef(onOpenChange)
  React.useEffect(() => { onOpenChangeRef.current = onOpenChange }, [onOpenChange])

  const setOpen = React.useCallback((value) => {
    const current = openRef.current
    const nextValue = typeof value === "function" ? value(current) : value
    if (!isControlledRef.current) setUncontrolledOpen(nextValue)
    onOpenChangeRef.current?.(nextValue)
  }, [])

  const [isMobile, setIsMobile] = React.useState(
    typeof window !== "undefined" ? window.innerWidth <= mobileBreakpoint : false
  )
  const openMobile = isMobile ? open : false
  const setOpenMobile = React.useCallback((value) => {
    setOpen(value)
  }, [setOpen])

  React.useEffect(() => {
    const openState = open
    document.cookie = `${storageKey}=${openState}; path=/; max-age=${SIDEBAR_COOKIE_MAX_AGE}`
  }, [open, storageKey])

  React.useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth <= mobileBreakpoint)
    window.addEventListener("resize", handleResize)
    return () => window.removeEventListener("resize", handleResize)
  }, [mobileBreakpoint])

  const toggleSidebar = React.useCallback(() => {
    setOpen((prev) => !prev)
  }, [setOpen])

  // Keyboard shortcut
  React.useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === SIDEBAR_KEYBOARD_SHORTCUT && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        toggleSidebar()
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [toggleSidebar])

  React.useEffect(() => {
    if (isMobile && openMobile) {
      document.body.style.overflow = "hidden"
    } else {
      document.body.style.overflow = ""
    }
    return () => {
      document.body.style.overflow = ""
    }
  }, [isMobile, openMobile])

  const state = open ? "expanded" : "collapsed"

  return (
    <SidebarContext.Provider value={{ isMobile, open, setOpen, openMobile, setOpenMobile, toggleSidebar, state }}>
      <div 
        ref={ref} 
        style={{
          "--sidebar-width": SIDEBAR_WIDTH,
          "--sidebar-width-icon": SIDEBAR_WIDTH_ICON,
          ...style,
        }}
        data-state={state}
        data-sidebar-state={state}
        className={cn("group/sidebar-wrapper has-[[data-sidebar=sidebar]]:bg-sidebar flex min-h-svh w-full h-full relative", className)} 
        {...props}
      >
        {children}
      </div>
    </SidebarContext.Provider>
  )
})
SidebarProvider.displayName = "SidebarProvider"

export const Sidebar = React.forwardRef(({ className, children, collapsible = "offcanvas", side = "left", variant = "sidebar", ...props }, ref) => {
  const { open, isMobile, openMobile, setOpenMobile, state } = useSidebar()

  // Mobile drawer
  if (isMobile) {
    return (
      <>
        {openMobile && (
           <div 
            className="sidebar-mobile-overlay"
            onClick={() => setOpenMobile(false)}
            aria-hidden="true"
           />
        )}
        <div 
          ref={ref} 
          data-sidebar="sidebar" 
          data-mobile="true"
          data-side={side}
          data-state={openMobile ? "expanded" : "collapsed"}
          className={cn(
            "sidebar-mobile-panel",
            openMobile ? "sidebar-mobile-open" : "sidebar-mobile-closed",
            className
          )} 
          {...props}
        >
          <div className="flex h-full w-full flex-col">
            {children}
          </div>
        </div>
      </>
    )
  }

  // Desktop sidebar with collapsible support
  return (
    <div 
      className="sidebar-desktop-gap" 
      data-state={state}
      data-side={side}
      data-collapsible={state === "collapsed" ? collapsible : ""}
    >
      <div 
        ref={ref} 
        data-sidebar="sidebar"
        data-state={state}
        data-side={side}
        data-collapsible={state === "collapsed" ? collapsible : ""}
        className={cn("sidebar-desktop-panel", className)} 
        {...props}
      >
        <div 
          className="sidebar-desktop-inner"
          data-sidebar="sidebar-inner"
        >
          {children}
        </div>
      </div>
    </div>
  )
})
Sidebar.displayName = "Sidebar"

export const SidebarTrigger = React.forwardRef(({ className, onClick, ...props }, ref) => {
  const { toggleSidebar } = useSidebar()

  return (
    <button
      ref={ref}
      data-sidebar="trigger"
      className={cn("sidebar-trigger-btn", className)}
      onClick={(e) => {
        onClick?.(e)
        toggleSidebar()
      }}
      {...props}
    >
      {props.side === "right" ? <PanelLeft className="size-4 rotate-180" /> : <PanelLeft className="size-4" />}
      <span className="sr-only">Toggle Sidebar</span>
    </button>
  )
})
SidebarTrigger.displayName = "SidebarTrigger"

export const SidebarRail = React.forwardRef(({ className, ...props }, ref) => {
  const { toggleSidebar } = useSidebar()
  
  return (
    <button
      ref={ref}
      data-sidebar="rail"
      aria-label="Toggle Sidebar"
      tabIndex={-1}
      onClick={toggleSidebar}
      title="Toggle Sidebar"
      className={cn("sidebar-rail", className)}
      {...props}
    />
  )
})
SidebarRail.displayName = "SidebarRail"

export const SidebarHeader = React.forwardRef(({ className, ...props }, ref) => (
  <div ref={ref} data-sidebar="header" className={cn("flex flex-col gap-2 p-2", className)} {...props} />
))
SidebarHeader.displayName = "SidebarHeader"

export const SidebarContent = React.forwardRef(({ className, ...props }, ref) => (
  <div ref={ref} data-sidebar="content" className={cn("sidebar-content-area", className)} {...props} />
))
SidebarContent.displayName = "SidebarContent"

export const SidebarFooter = React.forwardRef(({ className, ...props }, ref) => (
  <div ref={ref} data-sidebar="footer" className={cn("sidebar-footer-area", className)} {...props} />
))
SidebarFooter.displayName = "SidebarFooter"

export const SidebarGroup = React.forwardRef(({ className, ...props }, ref) => (
  <div ref={ref} data-sidebar="group" className={cn("sidebar-group", className)} {...props} />
))
SidebarGroup.displayName = "SidebarGroup"

export const SidebarGroupLabel = React.forwardRef(({ className, asChild, ...props }, ref) => (
  <div ref={ref} data-sidebar="group-label" className={cn("sidebar-group-label", className)} {...props} />
))
SidebarGroupLabel.displayName = "SidebarGroupLabel"

export const SidebarGroupContent = React.forwardRef(({ className, ...props }, ref) => (
  <div ref={ref} data-sidebar="group-content" className={cn("w-full text-sm", className)} {...props} />
))
SidebarGroupContent.displayName = "SidebarGroupContent"

export const SidebarMenu = React.forwardRef(({ className, ...props }, ref) => (
  <ul ref={ref} data-sidebar="menu" className={cn("sidebar-menu", className)} {...props} />
))
SidebarMenu.displayName = "SidebarMenu"

export const SidebarMenuItem = React.forwardRef(({ className, ...props }, ref) => (
  <li ref={ref} data-sidebar="menu-item" className={cn("sidebar-menu-item", className)} {...props} />
))
SidebarMenuItem.displayName = "SidebarMenuItem"

export const SidebarMenuButton = React.forwardRef(({ asChild, tooltip, size = "default", isActive, disabled, className, children, ...props }, ref) => {
  const Comp = asChild ? "div" : "button"
  return (
    <Comp
      ref={ref}
      data-sidebar="menu-button"
      data-size={size}
      data-active={isActive}
      title={tooltip}
      disabled={disabled}
      className={cn(
        "sidebar-menu-button",
        isActive && "sidebar-menu-button-active",
        disabled && "pointer-events-none opacity-50",
        className
      )}
      {...props}
    >
      {children}
    </Comp>
  )
})
SidebarMenuButton.displayName = "SidebarMenuButton"

export const SidebarMenuAction = React.forwardRef(({ className, asChild, showOnHover, ...props }, ref) => {
  const Comp = asChild ? "div" : "button"
  return (
    <Comp
      ref={ref}
      data-sidebar="menu-action"
      className={cn("sidebar-menu-action",
        showOnHover && "sidebar-menu-action-hover",
        className
      )}
      {...props}
    />
  )
})
SidebarMenuAction.displayName = "SidebarMenuAction"

export const SidebarInput = React.forwardRef(({ className, ...props }, ref) => (
  <input ref={ref} data-sidebar="input" className={cn("flex h-8 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50", className)} {...props} />
))
SidebarInput.displayName = "SidebarInput"

export const SidebarMenuSub = React.forwardRef(({ className, ...props }, ref) => (
  <ul ref={ref} data-sidebar="menu-sub" className={cn("sidebar-menu-sub", className)} {...props} />
))
SidebarMenuSub.displayName = "SidebarMenuSub"

export const SidebarMenuSubItem = React.forwardRef(({ className, ...props }, ref) => (
  <li ref={ref} data-sidebar="menu-sub-item" className={cn(className)} {...props} />
))
SidebarMenuSubItem.displayName = "SidebarMenuSubItem"

export const SidebarMenuSubButton = React.forwardRef(({ asChild, size = "default", isActive, className, children, ...props }, ref) => {
  const Comp = asChild ? "div" : "button"
  return (
    <Comp
      ref={ref}
      data-sidebar="menu-sub-button"
      data-size={size}
      data-active={isActive}
      className={cn(
        "sidebar-menu-sub-button",
        isActive && "sidebar-menu-sub-button-active",
        className
      )}
      {...props}
    >
      {children}
    </Comp>
  )
})
SidebarMenuSubButton.displayName = "SidebarMenuSubButton"

export const SidebarInset = React.forwardRef(({ className, ...props }, ref) => (
  <main ref={ref} className={cn("sidebar-inset", className)} {...props} />
))
SidebarInset.displayName = "SidebarInset"

export const SidebarSeparator = React.forwardRef(({ className, ...props }, ref) => (
  <div
    ref={ref}
    data-sidebar="separator"
    className={cn("mx-2 w-auto bg-sidebar-border h-px my-2 opacity-50", className)}
    {...props}
  />
))
SidebarSeparator.displayName = "SidebarSeparator"
