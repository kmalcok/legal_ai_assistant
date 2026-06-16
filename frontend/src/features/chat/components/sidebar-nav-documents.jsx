"use client"

import { ChevronRight, Download, Eye, FileType2, FolderOpen, MoreHorizontal, ScrollText, Trash2 } from "lucide-react"

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarGroup,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
} from "@/components/ui/sidebar"

export function NavDocuments({
  documents,
  loading,
  error,
  onOpenDocumentPreview,
  onDownloadDocument,
  onDownloadPdf,
  onDownloadUdf,
  onDeleteDocument,
  downloadingDocumentId,
  downloadingPdfDocumentId,
  downloadingUdfDocumentId,
  deletingDocumentId,
  hasChat,
}) {
  const items = Array.isArray(documents) ? documents : []
  const visibleRows = Math.max(
    items.length + Number(Boolean(loading)) + Number(Boolean(error)),
    1,
  )

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
              <SidebarMenuButton tooltip="Dokümanlar">
                <FolderOpen />
                <span className="truncate">Dokümanlar</span>
                <span className="section-badge ml-auto shrink-0">{items.length}</span>
                <ChevronRight className="shrink-0 transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
              </SidebarMenuButton>
            </CollapsibleTrigger>
            <CollapsibleContent className="sidebar-panel-content">
              <SidebarMenuSub className="sidebar-panel-sub">
                <div
                  className="sidebar-panel-scroll sidebar-section-scroll chat-sidebar-scroll"
                  style={{ '--sidebar-list-count': visibleRows, '--sidebar-max-visible-rows': 6 }}
                >
                  {loading && <div className="px-2 py-1.5 text-xs text-muted-foreground">Dokümanlar yükleniyor...</div>}
                  {error && <div className="px-2 py-1.5 text-xs text-destructive">{error}</div>}
                  {items.length === 0 && !loading && (
                    <div className="px-2 py-1.5 text-xs text-muted-foreground">Henüz üretilmiş doküman yok</div>
                  )}

                  {items.map((doc) => {
                    const docId = Number(doc.generated_document_id)
                    const label = String(doc?.filename || `Doküman ${docId}`)
                    const isDownloading = Number(downloadingDocumentId) === docId
                    const isDownloadingPdf = Number(downloadingPdfDocumentId) === docId
                    const isDownloadingUdf = Number(downloadingUdfDocumentId) === docId
                    const isDeleting = Number(deletingDocumentId) === docId

                    return (
                      <SidebarMenuSubItem key={docId} className="relative group/sub-item">
                        <SidebarMenuSubButton asChild>
                          <button
                            type="button"
                            className="sidebar-sub-link text-left"
                            title={label}
                            onClick={() => onOpenDocumentPreview?.({ generatedDocumentId: docId })}
                            disabled={!hasChat || !Number.isFinite(docId) || docId <= 0 || isDeleting}
                          >
                            <span className="truncate">{label}</span>
                          </button>
                        </SidebarMenuSubButton>

                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <button className="sidebar-sub-action" onClick={(e) => e.stopPropagation()}>
                              <MoreHorizontal className="size-3.5" />
                              <span className="sr-only">More</span>
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent className="w-48" side="top" align="end">
                            <DropdownMenuItem
                              disabled={!hasChat || !Number.isFinite(docId) || docId <= 0 || isDeleting}
                              onClick={() => onOpenDocumentPreview?.({ generatedDocumentId: docId })}
                            >
                              <Eye className="text-muted-foreground" />
                              <span>Önizle</span>
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              disabled={!hasChat || !Number.isFinite(docId) || docId <= 0 || isDownloading || isDeleting}
                              onClick={() => onDownloadDocument?.({ generatedDocumentId: docId, fallbackFilename: label })}
                            >
                              <Download className="text-muted-foreground" />
                              <span>{isDownloading ? 'İndiriliyor...' : 'Word İndir'}</span>
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              disabled={!hasChat || !Number.isFinite(docId) || docId <= 0 || isDownloadingPdf || isDeleting}
                              onClick={() => onDownloadPdf?.({ generatedDocumentId: docId, fallbackFilename: label })}
                            >
                              <FileType2 className="text-muted-foreground" />
                              <span>{isDownloadingPdf ? 'PDF hazırlanıyor...' : 'PDF İndir'}</span>
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              disabled={!hasChat || !Number.isFinite(docId) || docId <= 0 || isDownloadingUdf || isDeleting}
                              onClick={() => onDownloadUdf?.({ generatedDocumentId: docId, fallbackFilename: label })}
                            >
                              <ScrollText className="text-muted-foreground" />
                              <span>{isDownloadingUdf ? 'UDF hazırlanıyor...' : 'UDF İndir'}</span>
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              disabled={!hasChat || !Number.isFinite(docId) || docId <= 0 || isDownloading || isDeleting}
                              onClick={() => onDeleteDocument?.(docId, label)}
                              className="text-destructive focus:bg-destructive/10"
                            >
                              <Trash2 className="text-destructive" />
                              <span>{isDeleting ? 'Siliniyor...' : 'Sil'}</span>
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
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
