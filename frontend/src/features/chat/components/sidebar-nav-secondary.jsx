"use client"

import * as React from "react"
import { ChevronRight, Download, Eye, FileBadge, FileType2, MoreHorizontal, Trash2 } from "lucide-react"

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
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
  SidebarMenuSubItem,
  SidebarMenuSubButton,
  useSidebar,
} from "@/components/ui/sidebar"

export function NavSecondary({
  petitions,
  petitionsLoading,
  petitionsError,
  onOpenPetitionPreview,
  onDeletePetition,
  onDownloadPetitionDocx,
  onDownloadPetitionPdf,
  onDownloadPetitionUdf,
  downloadingPetitionKey,
  deletingPetitionId,
  hasChat,
  ...props
}) {
  const { isMobile } = useSidebar()
  const items = Array.isArray(petitions) ? petitions : []
  const visibleRows = Math.max(
    items.length + Number(Boolean(petitionsLoading)) + Number(Boolean(petitionsError)),
    1,
  )

  return (
    <SidebarGroup className="sidebar-panel-group" {...props}>
      <SidebarMenu className="sidebar-panel-menu">
        <Collapsible
          asChild
          defaultOpen
          className="group/collapsible"
        >
          <SidebarMenuItem className="sidebar-panel-item">
            <CollapsibleTrigger asChild>
              <SidebarMenuButton tooltip="Dilekçeler">
                <FileBadge />
                <span className="truncate">Dilekçeler</span>
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
                  {petitionsLoading && <div className="px-2 py-1.5 text-xs text-muted-foreground">Dilekçeler yükleniyor...</div>}
                  {petitionsError && <div className="px-2 py-1.5 text-xs text-destructive">{petitionsError}</div>}
                  {items.length === 0 && !petitionsLoading && <div className="px-2 py-1.5 text-xs text-muted-foreground">Henüz dilekçe yok</div>}

                  {items.map((p) => {
                    const petitionId = Number(p.petition_id)
                    const versionId = Number(p.latest_version_id)
                    const filename = String(p.latest_filename || '')
                    const keyDocx = `docx:${petitionId}:${versionId}`
                    const keyPdf = `pdf:${petitionId}:${versionId}`
                    const keyUdf = `udf:${petitionId}:${versionId}`
                    const canDownload = Number.isFinite(petitionId) && Number.isFinite(versionId) && versionId > 0
                    const label = String(p.title || p.document_type || `Dilekçe #${petitionId}`)
                    const isDownloading = downloadingPetitionKey === keyDocx || downloadingPetitionKey === keyUdf
                    const isDeleting = Number(deletingPetitionId) === petitionId

                    return (
                      <SidebarMenuSubItem key={petitionId} className="relative group/sub-item">
                        <SidebarMenuSubButton asChild>
                          <button
                            onClick={() => onOpenPetitionPreview?.({ petitionId, versionId })}
                            title={label}
                            className="sidebar-sub-link"
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
                          <DropdownMenuContent
                            className="w-48"
                            side="top"
                            align="end"
                          >
                            <DropdownMenuItem
                              disabled={!hasChat || !Number.isFinite(petitionId) || petitionId <= 0}
                              onClick={() => onOpenPetitionPreview?.({ petitionId, versionId })}
                            >
                              <Eye className="text-muted-foreground" />
                              <span>Önizle</span>
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              disabled={!hasChat || !canDownload || isDownloading || isDeleting}
                              onClick={() => {
                                onDownloadPetitionDocx?.({
                                  petitionId,
                                  versionId,
                                  fallbackFilename: filename || undefined,
                                })
                              }}
                            >
                              <Download className="text-muted-foreground" />
                              <span>{isDownloading ? "İndiriliyor..." : "Word İndir"}</span>
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              disabled={!hasChat || !canDownload || isDownloading || isDeleting}
                              onClick={() => {
                                const pdfName = filename?.toLowerCase().endsWith('.docx') ? filename.slice(0, -5) + '.pdf' : (filename ? filename + '.pdf' : undefined)
                                onDownloadPetitionPdf?.({
                                  petitionId,
                                  versionId,
                                  fallbackFilename: pdfName,
                                  downloadKey: keyPdf,
                                })
                              }}
                            >
                              <FileType2 className="text-muted-foreground" />
                              <span>{isDownloading ? "İndiriliyor..." : "PDF İndir"}</span>
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              disabled={!hasChat || !canDownload || isDownloading || isDeleting}
                              onClick={() => {
                                const udfName = filename?.toLowerCase().endsWith('.docx') ? filename.slice(0, -5) + '.udf' : (filename ? filename + '.udf' : undefined)
                                onDownloadPetitionUdf?.({
                                  petitionId,
                                  versionId,
                                  fallbackFilename: udfName,
                                })
                              }}
                            >
                              <Download className="text-muted-foreground" />
                              <span>{isDownloading ? "İndiriliyor..." : "UDF İndir"}</span>
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              disabled={!hasChat || !canDownload || isDownloading || isDeleting}
                              onClick={() => onDeletePetition?.(petitionId, label)}
                              className="text-destructive focus:bg-destructive/10"
                            >
                              <Trash2 className="text-destructive" />
                              <span>{isDeleting ? "Siliniyor..." : "Sil"}</span>
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
