"use client"

import { ArrowUpRight, PanelLeftClose, Search } from "lucide-react"
import { Link } from "react-router-dom"
import { useCallback } from "react"
import { NavDocuments } from "./sidebar-nav-documents"
import { NavMain } from "./sidebar-nav-main"
import { NavProjects } from "./sidebar-nav-projects"
import { NavSecondary } from "./sidebar-nav-secondary"
import { NavUser } from "./sidebar-nav-user"
import yargucuLogoBlack from "../../../logopack/yargucu-logo-siyah.svg"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar"

export function ChatSidebar({
  chats,
  selectedChatId,
  loading,
  error,
  onSelectChat,
  onDeleteChat,
  onNewChat,
  docs,
  docsLoading,
  docsError,
  uploading,
  uploadError,
  uploadAccept,
  onUploadDocuments,
  onDetachDocument,
  generatedDocs,
  generatedDocsLoading,
  generatedDocsError,
  onOpenGeneratedDocPreview,
  onDownloadGeneratedDoc,
  onDownloadGeneratedDocPdf,
  onDownloadGeneratedDocUdf,
  onDeleteGeneratedDoc,
  downloadingGeneratedDocId,
  downloadingGeneratedDocPdfId,
  downloadingGeneratedDocUdfId,
  deletingGeneratedDocId,
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
  user,
  userLabel,
  onOpenSupport,
  onOpenSettings,
  onLogout,
  ...props
}) {
  const formatCredit = useCallback(
    (value) => {
      const num = Number(value)
      if (!Number.isFinite(num)) return undefined
      return num.toLocaleString('tr-TR', { maximumFractionDigits: 2 })
    },
    [],
  )
  const creditSummary = user?.account_type === 'parent'
    ? {
        total: formatCredit(user?.credit_summary?.total_credit),
        available: formatCredit(user?.credit_summary?.available_credit ?? user?.credit),
      }
    : null
  const creditLabel = creditSummary
    ? undefined
    : formatCredit(user?.credit)

  const { isMobile, setOpen, setOpenMobile } = useSidebar()
  const handleCollapseSidebar = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    if (isMobile) {
      setOpenMobile(false)
      return
    }
    setOpen(false)
  }, [isMobile, setOpen, setOpenMobile])

  return (
    <Sidebar collapsible="offcanvas" {...props}>
      <SidebarHeader>
        <div className="flex items-center justify-between px-2 pt-2">
          <Link
            to="/chat"
            className="sidebar-brand-btn sidebar-brand-btn--chat group flex min-w-0 flex-1 items-center overflow-hidden transition-colors"
          >
            <div className="sidebar-brand-icon sidebar-brand-icon--assistant">
              <img src={yargucuLogoBlack} alt="Yargucu logosu" className="sidebar-brand-image" />
            </div>
            <div className="sidebar-brand-copy grid flex-1 text-left leading-tight">
              <div className="flex items-center gap-1.5 min-w-0">
                <span className="sidebar-brand-title truncate">Yargucu</span>
                <span className="brand-badge">Beta</span>
              </div>
              <span className="sidebar-brand-kicker truncate">AI Hukuk Asistanı</span>
            </div>
          </Link>
          <button
            type="button"
            onClick={handleCollapseSidebar}
            className="sidebar-collapse-btn"
            aria-label="Menüyü daralt"
            title="Menüyü daralt"
          >
            <PanelLeftClose className="size-4" />
          </button>
        </div>
      </SidebarHeader>
      
      <SidebarContent>
        <NavMain 
          chats={chats}
          selectedChatId={selectedChatId}
          loading={loading}
          error={error}
          onSelectChat={onSelectChat}
          onDeleteChat={onDeleteChat}
          onNewChat={onNewChat}
        />
        <NavProjects 
          docs={docs}
          docsLoading={docsLoading}
          docsError={docsError}
          uploading={uploading}
          uploadError={uploadError}
          uploadAccept={uploadAccept}
          onUploadDocuments={onUploadDocuments}
          onDetachDocument={onDetachDocument}
        />
        <NavDocuments
          documents={generatedDocs}
          loading={generatedDocsLoading}
          error={generatedDocsError}
          onOpenDocumentPreview={onOpenGeneratedDocPreview}
          onDownloadDocument={onDownloadGeneratedDoc}
          onDownloadPdf={onDownloadGeneratedDocPdf}
          onDownloadUdf={onDownloadGeneratedDocUdf}
          onDeleteDocument={onDeleteGeneratedDoc}
          downloadingDocumentId={downloadingGeneratedDocId}
          downloadingPdfDocumentId={downloadingGeneratedDocPdfId}
          downloadingUdfDocumentId={downloadingGeneratedDocUdfId}
          deletingDocumentId={deletingGeneratedDocId}
          hasChat={hasChat}
        />
        <NavSecondary 
          petitions={petitions}
          petitionsLoading={petitionsLoading}
          petitionsError={petitionsError}
          onOpenPetitionPreview={onOpenPetitionPreview}
          onDeletePetition={onDeletePetition}
          onDownloadPetitionDocx={onDownloadPetitionDocx}
          onDownloadPetitionPdf={onDownloadPetitionPdf}
          onDownloadPetitionUdf={onDownloadPetitionUdf}
          downloadingPetitionKey={downloadingPetitionKey}
          deletingPetitionId={deletingPetitionId}
          hasChat={hasChat}
        />
      </SidebarContent>
      
      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <Link to="/ictihat" className="ictihat-link group">
              <span className="ictihat-link-icon" aria-hidden="true">
                <Search className="size-4" />
              </span>
              <span className="ictihat-link-copy">
                <span className="ictihat-link-title">İçtihat Ara</span>
                <span className="ictihat-link-subtitle">Emsal kararları hızlıca tara</span>
              </span>
              <ArrowUpRight className="ictihat-link-arrow size-4" aria-hidden="true" />
            </Link>
          </SidebarMenuItem>
        </SidebarMenu>
        {userLabel && (
          <NavUser 
            user={user} 
            userLabel={userLabel}
            creditLabel={creditLabel}
            creditSummary={creditSummary}
            onOpenSupport={onOpenSupport}
            onOpenSettings={onOpenSettings}
            onLogout={onLogout}
          />
        )}
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
