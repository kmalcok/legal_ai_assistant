"use client"

import { ChevronRight, MessageSquare, Trash2, Plus } from "lucide-react"

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  SidebarGroup,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubItem,
  SidebarMenuSubButton,
} from "@/components/ui/sidebar"

function trimToWords(text, maxWords) {
  const words = String(text || '').trim().split(/\s+/).filter(Boolean)
  if (words.length <= maxWords) return words.join(' ')
  return `${words.slice(0, maxWords).join(' ')}...`
}

function trimToLength(text, maxChars) {
  const normalized = String(text || '').replace(/\s+/g, ' ').trim()
  if (!normalized || normalized.length <= maxChars) return normalized

  const slice = normalized.slice(0, maxChars).trim()
  const lastSpace = slice.lastIndexOf(' ')
  const safe = lastSpace > Math.floor(maxChars * 0.6) ? slice.slice(0, lastSpace) : slice
  return `${safe.trim()}…`
}

function chatLabel(chat) {
  const t = (chat?.title || '').trim()
  if (t) return trimToLength(trimToWords(t, 5), 34)
  const fm = (chat?.first_message || '').trim()
  if (fm) return trimToLength(trimToWords(fm, 5), 34)
  const s = (chat?.last_sum || '').trim()
  if (s) return trimToLength(trimToWords(s, 5), 34)
  return 'Yeni sohbet'
}

export function NavMain({
  chats,
  selectedChatId,
  loading,
  error,
  onSelectChat,
  onDeleteChat,
  onNewChat,
}) {
  const items = Array.isArray(chats) ? chats : []

  return (
    <SidebarGroup className="sidebar-panel-group">
      <SidebarMenu className="sidebar-panel-menu">
        {/* New chat button as a collapsible parent item */}
        <Collapsible
          asChild
          defaultOpen
          className="group/collapsible"
        >
          <SidebarMenuItem className="sidebar-panel-item">
            <CollapsibleTrigger asChild>
              <SidebarMenuButton tooltip="Sohbetler">
                <MessageSquare />
                <span className="truncate">Sohbetler</span>
                <span className="section-badge ml-auto shrink-0">{items.length}</span>
                <ChevronRight className="shrink-0 transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
              </SidebarMenuButton>
            </CollapsibleTrigger>
            <CollapsibleContent className="sidebar-panel-content">
              <SidebarMenuSub className="sidebar-panel-sub">
                {/* New chat action */}
                <SidebarMenuSubItem>
                  <SidebarMenuSubButton asChild>
                    <button onClick={onNewChat} className="flex items-center gap-2 w-full text-left">
                      <Plus className="h-4 w-4 shrink-0" />
                      <span>Yeni sohbet</span>
                    </button>
                  </SidebarMenuSubButton>
                </SidebarMenuSubItem>

                {loading && (
                  <div className="px-2 py-1.5 text-xs text-muted-foreground">Sohbetler yükleniyor...</div>
                )}
                {error && (
                  <div className="px-2 py-1.5 text-xs text-destructive">{error}</div>
                )}
                {items.length === 0 && !loading && (
                  <div className="px-2 py-1.5 text-xs text-muted-foreground">Henüz sohbet yok</div>
                )}

                <div
                  className="sidebar-panel-scroll sidebar-section-scroll chat-sidebar-scroll"
                  style={{ '--sidebar-list-count': Math.max(items.length, 1), '--sidebar-max-visible-rows': 8 }}
                >
                  {items.map((c) => {
                    const id = Number(c.chat_id)
                    const isActive = selectedChatId === id
                    const label = chatLabel(c)
                    const tooltipLabel = c.title || c.first_message || label

                    return (
                      <SidebarMenuSubItem key={id} className="relative group/sub-item">
                        <SidebarMenuSubButton asChild>
                          <button
                            onClick={(e) => {
                              e.preventDefault()
                              onSelectChat?.(id)
                            }}
                            title={tooltipLabel}
                            className={isActive ? 'sidebar-sub-active sidebar-chat-link' : 'sidebar-chat-link'}
                          >
                            <span className="sidebar-chat-label">{label}</span>
                          </button>
                        </SidebarMenuSubButton>
                        <button
                          className="sidebar-sub-delete"
                          onClick={(e) => {
                            e.preventDefault()
                            e.stopPropagation()
                            onDeleteChat?.(id)
                          }}
                          title="Sohbeti sil"
                        >
                          <Trash2 className="size-3.5" />
                          <span className="sr-only">Sohbeti sil</span>
                        </button>
                      </SidebarMenuSubItem>
                    )
                  })}
                </div>
              </SidebarMenuSub>
            </CollapsibleContent>
          </SidebarMenuItem>
        </Collapsible>
      </SidebarMenu>
    </SidebarGroup>
  )
}
