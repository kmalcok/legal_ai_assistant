import * as React from "react"

import { cn } from "@/lib/utils"

const SelectContext = React.createContext(null)

function walkSelectChildren(children, state) {
  React.Children.forEach(children, (child) => {
    if (!React.isValidElement(child)) return
    const marker = child.type?.displayName
    if (marker === "SelectValue" && typeof child.props?.placeholder !== "undefined") {
      state.placeholder = child.props.placeholder
    }
    if (marker === "SelectItem") {
      state.items.push({
        value: String(child.props?.value ?? ""),
        label: child.props?.children,
        disabled: Boolean(child.props?.disabled),
      })
    }
    if (child.props?.children) {
      walkSelectChildren(child.props.children, state)
    }
  })
}

function Select({
  value,
  onValueChange,
  disabled = false,
  children,
}) {
  const parsed = React.useMemo(() => {
    const state = { items: [], placeholder: undefined }
    walkSelectChildren(children, state)
    return state
  }, [children])

  const contextValue = React.useMemo(
    () => ({
      value,
      onValueChange,
      disabled,
      items: parsed.items,
      placeholder: parsed.placeholder,
    }),
    [disabled, onValueChange, parsed.items, parsed.placeholder, value]
  )

  return <SelectContext.Provider value={contextValue}>{children}</SelectContext.Provider>
}

const SelectTrigger = React.forwardRef(({ className, onChange, disabled, ...props }, ref) => {
  const context = React.useContext(SelectContext)
  const items = context?.items || []
  const value = typeof context?.value === "undefined" || context?.value === null ? "" : String(context.value)
  const placeholder = context?.placeholder

  return (
    <select
      ref={ref}
      data-slot="select-trigger"
      className={cn(className)}
      value={value}
      disabled={context?.disabled || disabled}
      onChange={(event) => {
        context?.onValueChange?.(event.target.value)
        onChange?.(event)
      }}
      {...props}
    >
      {typeof placeholder !== "undefined" ? <option value="">{placeholder}</option> : null}
      {items.map((item) => (
        <option key={`${item.value}-${String(item.label)}`} value={item.value} disabled={item.disabled}>
          {item.label}
        </option>
      ))}
    </select>
  )
})
SelectTrigger.displayName = "SelectTrigger"

function SelectValue() {
  return null
}
SelectValue.displayName = "SelectValue"

function SelectContent() {
  return null
}
SelectContent.displayName = "SelectContent"

function SelectItem() {
  return null
}
SelectItem.displayName = "SelectItem"

export { Select, SelectTrigger, SelectValue, SelectContent, SelectItem }
