"use client"

import { ChevronRight, FileText, UploadCloud, X } from "lucide-react"

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
import { useRef } from "react"

export function NavProjects({
  docs,
  docsLoading,
  docsError,
  uploading,
  uploadError,
  uploadAccept,
  onUploadDocuments,
  onDetachDocument,
}) {
  const fileInputRef = useRef(null)
  const items = Array.isArray(docs) ? docs : []
  const visibleRows = Math.max(
    items.length + Number(Boolean(docsLoading)) + Number(Boolean(docsError)) + Number(Boolean(uploadError)),
    1,
  )

  const handleUploadClick = () => {
    if (uploading) return
    fileInputRef.current?.click()
  }

  const handleFileChange = (e) => {
    const files = e.target.files
    if (files?.length) onUploadDocuments?.(files)
    e.target.value = ''
  }

  const getStatusLabel = (doc) => {
    const status = String(doc?.status || '').trim().toLowerCase()
    if (status === 'processing') return 'Isleniyor'
    if (status === 'ready') return 'Hazir'
    if (status === 'failed') return 'Basarisiz'
    if (status === 'uploaded') return 'Sirada'
    return ''
  }

  return (
    <SidebarGroup className="sidebar-panel-group">
      <SidebarMenu className="sidebar-panel-menu">
        <Collapsible
          asChild
          defaultOpen
          className="group/collapsible"
        >
          <SidebarMenuItem className="sidebar-panel-item">
            <CollapsibleTrigger asChild>
              <SidebarMenuButton tooltip="Belgeler">
                <FileText />
                <span className="truncate">Belgeler</span>
                <span className="section-badge ml-auto shrink-0">{items.length}</span>
                <ChevronRight className="shrink-0 transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
              </SidebarMenuButton>
            </CollapsibleTrigger>
            <CollapsibleContent className="sidebar-panel-content">
              <SidebarMenuSub className="sidebar-panel-sub">
                {/* Upload action */}
                <SidebarMenuSubItem>
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    hidden
                    accept={uploadAccept}
                    onChange={handleFileChange}
                    disabled={uploading}
                  />
                  <SidebarMenuSubButton asChild>
                    <button onClick={handleUploadClick} disabled={uploading} className="flex items-center gap-2 w-full text-left">
                      <UploadCloud className="h-4 w-4 shrink-0" />
                      <span>{uploading ? 'Belge yükleniyor...' : 'Belge yükle'}</span>
                    </button>
                  </SidebarMenuSubButton>
                </SidebarMenuSubItem>

                <div
                  className="sidebar-panel-scroll sidebar-section-scroll chat-sidebar-scroll"
                  style={{ '--sidebar-list-count': visibleRows, '--sidebar-max-visible-rows': 6, '--sidebar-row-height': '44px' }}
                >
                  {docsLoading && <div className="px-2 py-1.5 text-xs text-muted-foreground">Belgeler yükleniyor...</div>}
                  {docsError && <div className="px-2 py-1.5 text-xs text-destructive">{docsError}</div>}
                  {uploadError && <div className="px-2 py-1.5 text-xs text-destructive">{uploadError}</div>}
                  {items.length === 0 && !docsLoading && <div className="px-2 py-1.5 text-xs text-muted-foreground">Henüz belge yok</div>}

                  {items.map((doc) => {
                    const docId = doc.document_id
                    const label = doc.filename || `Belge ${docId}`
                    const statusLabel = getStatusLabel(doc)
                    const errorMessage = String(doc?.error_message || '').trim()

                    return (
                      <SidebarMenuSubItem key={docId} className="relative group/sub-item">
                        <SidebarMenuSubButton asChild>
                          <a href="#" title={label} className="sidebar-sub-link">
                            <span className="min-w-0">
                              <span className="block truncate">{label}</span>
                              {statusLabel ? (
                                <span className={`mt-0.5 block text-[11px] ${doc?.status === 'failed' ? 'text-destructive' : 'text-muted-foreground'}`}>
                                  {statusLabel}
                                  {errorMessage ? ` - ${errorMessage}` : ''}
                                </span>
                              ) : null}
                            </span>
                          </a>
                        </SidebarMenuSubButton>
                        <button
                          className="sidebar-sub-delete"
                          onClick={() => onDetachDocument?.(docId)}
                          title="Kaldır"
                        >
                          <X className="size-3.5" />
                          <span className="sr-only">Kaldır</span>
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
