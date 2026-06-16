import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Plus, RotateCcw, Save, X, Info, AlertTriangle, Download } from 'lucide-react'
import { Button } from "@/components/ui/button"
import { Alert, AlertTitle } from "@/components/ui/alert"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { ScrollArea } from "@/components/ui/scroll-area"

function normalizeListDraft(value) {
  return String(value || '')
    .split(/\r?\n/g)
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => item.replace(/^([-*•]|\d+[.)])\s*/, '').trim())
    .filter(Boolean)
    .join('\n')
}

function formatListDraft(value, listStyle) {
  const normalized = normalizeListDraft(value)
  if (!normalized) return ''
  if (listStyle === 'bullet') {
    return normalized
      .split(/\r?\n/g)
      .map((item) => `• ${item}`)
      .join('\n')
  }
  return normalized
}

function fieldValueToDraft(value, isList, listStyle) {
  if (isList) {
    if (Array.isArray(value)) {
      return formatListDraft(value.map((item) => String(item || '').trim()).filter(Boolean).join('\n'), listStyle)
    }
    return formatListDraft(value, listStyle)
  }
  return String(value || '')
}

function draftToPatchValue(draft, isList) {
  if (isList) {
    return normalizeListDraft(draft)
      .split(/\r?\n/g)
      .map((item) => item.trim())
      .filter(Boolean)
  }
  return String(draft || '').trim()
}

function splitParagraphDraft(value) {
  const text = String(value ?? '')
  if (!text.trim()) return ['']
  return text
    .split(/\n\s*\n/g)
    .map((item) => String(item ?? ''))
    .filter((item, index, arr) => item.trim() || arr.length === 1 || index === arr.length - 1)
}

function joinParagraphSegments(segments) {
  const items = Array.isArray(segments) ? segments.map((item) => String(item ?? '')) : []
  if (!items.length) return ''
  return items.join('\n\n')
}

function normalizeSummary(summaryText, fallbackFilename) {
  const lines = String(summaryText || '')
    .split(/\r?\n/g)
    .map((line) => line.trim())
    .filter(Boolean)
  if (!lines.length) {
    const filename = fallbackFilename ? String(fallbackFilename) : ''
    return { breadcrumb: filename, body: '' }
  }

  const first = lines[0]
  const match = first.match(/^D[İI]LEKÇE hazır:\s*dosya=(.+)$/i)
  if (match) {
    lines[0] = String(match[1] || '').trim() || String(fallbackFilename || '').trim()
  }
  const breadcrumb = String(lines.shift() || fallbackFilename || '').trim()
  return {
    breadcrumb,
    body: lines.join('\n').trim(),
  }
}

function parseSummaryLines(summary) {
  const lines = String(summary?.body || '')
    .split(/\r?\n/g)
    .map((line) => line.trim())
    .filter(Boolean)

  const items = []
  let mode = 'default'
  for (const line of lines) {
    if (/^Eksik Bilgiler:/i.test(line)) {
      mode = 'missing'
      items.push({ kind: 'heading', text: 'Eksik Bilgiler', tone: 'missing' })
      continue
    }
    if (/^Varsayımlar:/i.test(line)) {
      mode = 'assumptions'
      items.push({ kind: 'heading', text: 'Varsayımlar', tone: 'muted' })
      continue
    }
    if (/^Taraflar:/i.test(line)) {
      mode = 'parties'
      items.push({ kind: 'heading', text: 'Taraflar', tone: 'default' })
      continue
    }
    if (/^Talepler \(Netice ve Talep\):/i.test(line)) {
      mode = 'requests'
      items.push({ kind: 'heading', text: 'Talepler', tone: 'default' })
      continue
    }
    const isDash = line.startsWith('-')
    const isNumber = /^\d+\)/.test(line)
    let processedText = line
    if (isDash) {
      processedText = line.slice(1).trim()
    }
    items.push({
      kind: isDash ? 'bullet' : 'line',
      text: processedText,
      tone: mode === 'missing' ? 'missing' : mode === 'assumptions' ? 'muted' : 'default',
    })
  }
  return items
}

function isMeaningfulText(value, isList) {
  if (isList) {
    return Array.isArray(value)
      ? value.some((item) => String(item || '').trim())
      : String(value || '')
        .split(/\r?\n/g)
        .some((item) => item.trim())
  }
  return Boolean(String(value || '').trim())
}

function toSectionSlug(value) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function buildDocumentSections(locators) {
  const groups = []
  const headerBlocks = Array.isArray(locators?.header_blocks) ? locators.header_blocks : []
  const sections = Array.isArray(locators?.sections) ? locators.sections : []
  const signature = Array.isArray(locators?.signature) ? locators.signature : []
  const attachments = locators?.attachments && typeof locators.attachments === 'object' ? locators.attachments : null

  const headerItems = headerBlocks
    .filter((item) => item?.field_path && isMeaningfulText(item.text_preview, Boolean(item.is_list)))
    .map((item) => ({
      key: item.node_id || item.field_path,
      field_path: item.field_path,
      label: String(item.label || 'Başlık'),
      text_preview: item.text_preview,
      is_list: Boolean(item.is_list),
      variant: 'meta',
    }))
  if (headerItems.length) {
    groups.push({
      key: 'header-blocks',
      title: 'Üst Bilgiler',
      variant: 'meta',
      items: headerItems,
    })
  }

  for (const item of headerBlocks) {
    void item
  }

  for (const section of sections) {
    const sectionItems = []
    for (const block of Array.isArray(section?.blocks) ? section.blocks : []) {
      if (!block?.field_path || !isMeaningfulText(block.text_preview, Boolean(block.is_list))) continue
      sectionItems.push({
        key: block.node_id || block.field_path,
        field_path: block.field_path,
        text_preview: block.text_preview,
        kind: String(block.kind || ''),
        is_list: Boolean(block.is_list),
        list_style: block.kind === 'numbered' ? 'bullet' : block.kind === 'bullets' ? 'bullet' : null,
        variant: 'body',
      })
    }
    if (!sectionItems.length) continue
    groups.push({
      key: section?.title_node?.node_id || section?.title_node?.field_path || `section-${section?.section_index}`,
      title: String(section?.title || section?.title_node?.text_preview || 'Bölüm'),
      field_path: section?.title_node?.field_path || null,
      title_preview: String(section?.title_node?.text_preview || section?.title || '').trim(),
      variant: 'section',
      items: sectionItems,
    })
  }

  const signatureItems = signature
    .filter((item) => item?.field_path && isMeaningfulText(item.text_preview, false))
    .map((item) => ({
      key: item.node_id || item.field_path,
      field_path: item.field_path,
      label: String(item.label || 'İmza'),
      text_preview: item.text_preview,
      is_list: false,
      variant: 'signature',
    }))
  if (signatureItems.length) {
    groups.push({
      key: 'signature',
      title: 'İmza',
      variant: 'signature',
      items: signatureItems,
    })
  }

  if (attachments?.field_path && isMeaningfulText(attachments.items, true)) {
    groups.push({
      key: attachments.node_id || attachments.field_path,
      title: 'Ekler',
      variant: 'attachments',
      items: [
        {
          key: attachments.node_id || attachments.field_path,
          field_path: attachments.field_path,
          label: 'Ekler',
          text_preview: attachments.items,
          is_list: true,
          list_style: 'bullet',
          variant: 'attachments',
        },
      ],
    })
  }

  return groups
}

export function PetitionPreviewPanel({
  petition,
  loading,
  error,
  saving,
  scrollTop,
  onScrollTopChange,
  onClose,
  onStartResize,
  onSaveAll,
  onInjectContext,
  downloadingDocx,
  onDownloadPdf,
  downloadingPdf,
  onDownloadDocx,
  downloadingUdf,
  onDownloadUdf,
}) {
  const locators = petition?.locators && typeof petition.locators === 'object' ? petition.locators : {}
  const version = petition?.version && typeof petition.version === 'object' ? petition.version : {}
  const documentSections = useMemo(() => buildDocumentSections(locators), [locators])
  const documentRows = useMemo(
    () => documentSections.flatMap((section) => Array.isArray(section.items) ? section.items : []),
    [documentSections],
  )
  const initialDrafts = useMemo(
    () =>
      Object.fromEntries(
        documentRows.map((row) => [row.field_path, fieldValueToDraft(row.text_preview, row.is_list, row.list_style)]),
      ),
    [documentRows],
  )
  const [drafts, setDrafts] = useState(initialDrafts)
  const [selections, setSelections] = useState({})
  const [typingFieldPath, setTypingFieldPath] = useState('')
  const [activeActionFieldPath, setActiveActionFieldPath] = useState('')
  const panelRef = useRef(null)
  const textRefs = useRef({})
  const panelBodyRef = useRef(null)
  const lastChangedEditorKeyRef = useRef('')
  const pendingScrollTopRef = useRef(null)
  const pendingFocusEditorKeyRef = useRef('')

  const appendParagraphToRow = (row, afterIndex = null) => {
    const fieldPath = String(row?.field_path || '').trim()
    if (!fieldPath) return
    const host = panelBodyRef.current
    pendingScrollTopRef.current = host ? host.scrollTop : null
    const segments = splitParagraphDraft(drafts[fieldPath] ?? '')
    const insertAt = Number.isInteger(afterIndex) ? afterIndex + 1 : segments.length
    const nextSegments = [...segments]
    nextSegments.splice(insertAt, 0, '')
    const editorKey = `${fieldPath}::${insertAt}`
    lastChangedEditorKeyRef.current = editorKey
    pendingFocusEditorKeyRef.current = editorKey
    setActiveActionFieldPath(fieldPath)
    setTypingFieldPath(fieldPath)
    setDrafts((prev) => ({
      ...(prev || {}),
      [fieldPath]: joinParagraphSegments(nextSegments),
    }))
  }

  useEffect(() => {
    setDrafts(initialDrafts)
    setSelections({})
    setTypingFieldPath('')
    setActiveActionFieldPath('')
    textRefs.current = {}
  }, [initialDrafts])

  const resizeTextarea = (fieldPath) => {
    const el = textRefs.current[fieldPath]
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }

  const resizeAllTextareas = () => {
    for (const fieldPath of Object.keys(textRefs.current || {})) {
      resizeTextarea(fieldPath)
    }
  }

  useLayoutEffect(() => {
    resizeAllTextareas()
    const rafId = window.requestAnimationFrame(resizeAllTextareas)
    return () => window.cancelAnimationFrame(rafId)
  }, [petition?.petition_id, initialDrafts])

  useLayoutEffect(() => {
    const host = panelBodyRef.current
    if (!host || !Number.isFinite(scrollTop)) return
    // Kullanıcı anlık kaydırdığında oluşan "stuttering" (takılma) efektini önlemek için
    // scrollTop güncellendiğinde zorla tekrar scrollTop set etmiyoruz. Sadece belge değişince set edilsin.
    host.scrollTop = scrollTop
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [petition?.petition_id, petition?.version?.version_id, initialDrafts])

  useLayoutEffect(() => {
    const editorKey = String(lastChangedEditorKeyRef.current || '').trim()
    if (editorKey) resizeTextarea(editorKey)

    const host = panelBodyRef.current
    if (host && Number.isFinite(pendingScrollTopRef.current)) {
      host.scrollTop = pendingScrollTopRef.current
    }

    const focusKey = String(pendingFocusEditorKeyRef.current || '').trim()
    if (focusKey) {
      const el = textRefs.current[focusKey]
      if (el) {
        el.focus()
        const pos = String(el.value || '').length
        el.setSelectionRange?.(pos, pos)
      }
    }

    lastChangedEditorKeyRef.current = ''
    pendingScrollTopRef.current = null
    pendingFocusEditorKeyRef.current = ''
  }, [drafts])

  useEffect(() => {
    const host = panelBodyRef.current
    if (!host || typeof ResizeObserver === 'undefined') return undefined

    const observer = new ResizeObserver(() => {
      window.requestAnimationFrame(resizeAllTextareas)
    })
    observer.observe(host)
    return () => observer.disconnect()
  }, [petition?.petition_id])

  useEffect(() => {
    function handlePointerDown(event) {
      const target = event.target
      if (!(target instanceof Element)) return
      const panelEl = panelRef.current
      const isInsidePanel = panelEl ? panelEl.contains(target) : false
      if (target.closest('.petition-inline-inject-btn')) return
      if (!isInsidePanel) {
        setSelections({})
        setActiveActionFieldPath('')
        return
      }
      setSelections({})
      if (!target.closest('.petition-document-editor')) {
        setActiveActionFieldPath('')
      }
    }

    window.addEventListener('pointerdown', handlePointerDown, true)
    return () => window.removeEventListener('pointerdown', handlePointerDown, true)
  }, [])

  const summary = useMemo(
    () => normalizeSummary(version?.summary_text, version?.docx_filename),
    [version?.docx_filename, version?.summary_text],
  )

  const dirtyRows = useMemo(
    () => documentRows.filter((row) => String(drafts[row.field_path] ?? '') !== String(initialDrafts[row.field_path] ?? '')),
    [documentRows, drafts, initialDrafts],
  )
  const visibleSections = useMemo(
    () =>
      documentSections
        .map((section) => {
          const items = Array.isArray(section.items) ? section.items : []
          if (section.variant === 'section') {
            const titleText = section.field_path
              ? String(drafts[section.field_path] ?? section.title_preview ?? section.title ?? '').trim()
              : String(section.title || '').trim()
            return { ...section, title: titleText || section.title, items }
          }
          return { ...section, items }
        })
        .filter((section) => Array.isArray(section?.items) && section.items.length)
        .filter(Boolean),
    [documentSections, drafts],
  )
  const summaryLines = useMemo(() => parseSummaryLines(summary), [summary])

  const saveAll = async () => {
    const patches = dirtyRows.map((row) => ({
      field_path: row.field_path,
      value: draftToPatchValue(drafts[row.field_path], row.is_list),
    }))
    if (!patches.length) return
    await onSaveAll?.(patches)
  }

  const resetAll = () => {
    if (!dirtyRows.length) return
    setDrafts(initialDrafts)
    setSelections({})
    setTypingFieldPath('')
    setActiveActionFieldPath('')
  }

  const injectRow = (row) => {
    const selectedText = String(selections[row.field_path] || '').trim()
    const text = selectedText || String(drafts[row.field_path] || '').trim()
    if (!text) return
    onInjectContext?.({
      field_path: row.field_path,
      selected_text: text,
      section_title: row.label || undefined,
    })
  }

  return (
    <aside ref={panelRef} className="petition-panel flex flex-col flex-1 min-h-0 overflow-hidden bg-background !p-0 !gap-0 border-l border-border relative isolate h-full z-[1001]" aria-label="Dilekçe önizleme">
      <div
        className="absolute left-[-3px] top-0 bottom-0 w-[6px] cursor-col-resize z-50 hover:bg-accent transition-colors hidden md:block"
        role="separator"
        aria-orientation="vertical"
        aria-label="Dilekçe paneli genişliği"
        tabIndex={0}
        onPointerDown={onStartResize}
      />
      
      <div className="flex flex-row items-center justify-between gap-1 sm:gap-3 px-3 sm:px-4 py-3 bg-background/85 backdrop-blur-md border-b sticky top-0 z-[60]">
        <div className="flex flex-col min-w-0">
          <h2 className="text-sm font-semibold tracking-tight truncate">Dilekçe Hazırlığı</h2>
          <span className="text-xs text-muted-foreground font-medium truncate">
            {dirtyRows.length ? `${dirtyRows.length} değişiklik yapıldı` : 'Taslak belge üzerinde çalışıyorsunuz'}
          </span>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" type="button" disabled={loading || !petition} className="h-8 text-xs px-2.5 font-semibold">
                <Download className="w-3.5 h-3.5 sm:mr-1" />
                <span>İndir</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-40">
              <DropdownMenuItem disabled={loading || downloadingDocx || !petition} onClick={onDownloadDocx}>
                <span>{downloadingDocx ? 'Word indiriliyor...' : 'Word İndir'}</span>
              </DropdownMenuItem>
              <DropdownMenuItem disabled={loading || downloadingPdf || !petition} onClick={onDownloadPdf}>
                <span>{downloadingPdf ? 'PDF indiriliyor...' : 'PDF İndir'}</span>
              </DropdownMenuItem>
              <DropdownMenuItem disabled={loading || downloadingUdf || !petition} onClick={onDownloadUdf}>
                <span>{downloadingUdf ? 'UDF indiriliyor...' : 'UDF İndir'}</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button variant="outline" size="sm" type="button" disabled={saving || !dirtyRows.length} onClick={resetAll} className="h-8 text-xs px-2.5 font-semibold">
            <RotateCcw className="w-3.5 h-3.5 sm:mr-1" />
            <span className="hidden sm:inline">Sıfırla</span>
          </Button>
          <Button size="sm" type="button" disabled={saving || !dirtyRows.length} onClick={saveAll} className="h-8 text-xs px-2.5 shadow-sm font-semibold">
            {saving ? 'Kaydediliyor...' : <><Save className="w-3.5 h-3.5 mr-1" /><span className="hidden sm:inline">Değişiklikleri Uygula</span><span className="sm:hidden">Uygula</span></>}
          </Button>
          <Button variant="ghost" type="button" size="icon" onClick={onClose} className="h-8 w-8 rounded-full ml-0.5" title="Kapat" aria-label="Paneli kapat">
            <X className="w-4 h-4" />
          </Button>
        </div>
      </div>

      <div
        ref={panelBodyRef}
        className="flex-1 overflow-y-auto p-4 md:p-6 flex flex-col gap-6 bg-slate-50/50"
        onScroll={() => {
          const host = panelBodyRef.current
          if (host) onScrollTopChange?.(host.scrollTop)
        }}
      >
        {summary?.breadcrumb || summaryLines.length ? (
          <div className="bg-card border rounded-xl p-5 shadow-sm flex flex-col gap-4">
            <div className="flex items-center gap-2 text-[11px] font-bold text-muted-foreground uppercase tracking-widest pb-2 border-b">
              {summary?.breadcrumb && <span className="text-foreground">{summary.breadcrumb}</span>}
              {summary?.breadcrumb && <span className="text-muted-foreground/50">/</span>}
              <span>İş Akışı Özeti</span>
            </div>
            {summaryLines.length ? (
              <div className="flex flex-col gap-2.5">
                {summaryLines.map((item, index) => {
                  if (item.kind === 'heading') {
                    return (
                      <div key={`${item.kind}-${index}`} className="flex items-center gap-3 mt-3 text-xs font-bold uppercase tracking-wide text-muted-foreground">
                        {item.text}
                        <div className="flex-1 h-px bg-border/60"></div>
                      </div>
                    )
                  }
                  if (item.tone === 'missing') {
                    return (
                      <Alert key={`${item.kind}-${index}`} variant="destructive" className="py-2.5 px-3">
                        <AlertTriangle className="h-4 w-4" />
                        <AlertTitle className="text-xs font-bold ml-1 mb-0 pb-0 flex items-center">{item.text}</AlertTitle>
                      </Alert>
                    )
                  }
                  
                  const isMuted = item.tone === 'muted'
                  return (
                    <div
                      key={`${item.kind}-${index}`}
                      className={`text-[13px] leading-relaxed relative ${item.kind === 'bullet' ? 'pl-4' : ''} ${isMuted ? 'text-muted-foreground italic' : 'text-foreground font-medium'}`}
                    >
                      {item.kind === 'bullet' && <span className="absolute left-1 top-[7px] w-1 h-1 rounded-full bg-muted-foreground/60"></span>}
                      {item.text}
                    </div>
                  )
                })}
              </div>
            ) : null}
          </div>
        ) : null}

        {loading ? <div className="text-muted-foreground text-sm text-center p-8 font-medium">Belge hazırlanıyor...</div> : null}
        {error ? <div className="text-destructive text-sm text-center p-8 font-medium">{error}</div> : null}

        {!loading && !error && !petition ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center p-10 text-muted-foreground min-h-[400px]">
            <div className="w-12 h-12 rounded-full bg-muted/50 flex items-center justify-center mb-4">
              <Info className="w-6 h-6 text-muted-foreground/70" />
            </div>
            <div className="text-base font-semibold text-foreground mb-1">Draft hazır değil</div>
            <div className="text-sm">Oluşturulan dilekçeler bu alanda profesyonel formatta listelenir.</div>
          </div>
        ) : null}

        {visibleSections.length ? (
          <div className="flex flex-col gap-0">
            <div className="bg-white rounded-lg shadow-sm border p-6 md:p-12 min-h-[600px] flex flex-col gap-8 ring-1 ring-black/[0.03]">
              {visibleSections.map((section) => (
                <section
                  key={section.key}
                  className={`flex flex-col gap-4`}
                >
                  <div className="">
                    {section.variant === 'section' ? (
                      <textarea
                        ref={(el) => {
                          if (!section.field_path) return
                          if (el) textRefs.current[section.field_path] = el
                          else delete textRefs.current[section.field_path]
                        }}
                        className="block w-full text-lg font-bold text-foreground py-1 bg-transparent border-none resize-none overflow-hidden focus:outline-none focus:ring-0 leading-tight transition-colors hover:bg-muted/30 focus:bg-muted/10 rounded-sm"
                        rows={Math.max(1, Math.min(String(drafts[section.field_path] ?? section.title_preview ?? section.title ?? '').split(/\r?\n/g).length, 3))}
                        value={String(drafts[section.field_path] ?? section.title_preview ?? section.title ?? '')}
                        onFocus={() => {
                          setSelections({})
                          setActiveActionFieldPath('')
                          if (section.field_path) setTypingFieldPath(section.field_path)
                        }}
                        onChange={(e) => {
                          if (!section.field_path) return
                          const host = panelBodyRef.current
                          pendingScrollTopRef.current = host ? host.scrollTop : null
                          setTypingFieldPath(section.field_path)
                          setDrafts((prev) => ({
                            ...(prev || {}),
                            [section.field_path]: e.target.value,
                          }))
                        }}
                        onBlur={() => {
                          setTypingFieldPath((prev) => (prev === section.field_path ? '' : prev))
                        }}
                      />
                    ) : (
                      <div className="text-xs font-bold text-muted-foreground uppercase tracking-[0.1em] pb-2 border-b mb-2">{section.title}</div>
                    )}

                    <div className="flex flex-col gap-3 mt-2">
                      {section.items.map((row) => {
                        const draft = String(drafts[row.field_path] ?? '')
                        const selectedText = String(selections[row.field_path] || '').trim()
                        const baseLineCount = draft.split(/\r?\n/g).length
                        const rows = row.is_list
                          ? Math.max(2, Math.min(baseLineCount + 1, 10))
                          : Math.max(1, Math.min(baseLineCount, 12))
                        const paragraphSegments = row.variant === 'body' && row.kind === 'paragraph' ? splitParagraphDraft(draft) : []

                        return (
                          <div
                            key={row.key}
                            className={`relative group transition-all duration-200 rounded-lg -mx-3 px-3 py-1 ${typingFieldPath === row.field_path ? 'bg-muted/20 ring-1 ring-border shadow-sm mb-2' : 'hover:bg-muted/30'}`}
                          >
                            <div className="">
                              <div className="flex flex-col gap-2">
                                {section.variant === 'meta' && row.label ? (
                                  <div className="">
                                    <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-widest">{row.label}</span>
                                  </div>
                                ) : null}
                                {paragraphSegments.length ? (
                                  <div className="flex flex-col gap-4">
                                    {paragraphSegments.map((segment, segmentIndex) => {
                                      const editorKey = `${row.field_path}::${segmentIndex}`
                                      const segmentRows = Math.max(1, Math.min(String(segment || '').split(/\r?\n/g).length, 12))
                                      return (
                                        <div key={editorKey} className="relative group/segment">
                                          <textarea
                                            ref={(el) => {
                                              if (el) textRefs.current[editorKey] = el
                                              else delete textRefs.current[editorKey]
                                            }}
                                            className={`block w-full text-[15px] leading-relaxed text-foreground bg-transparent border-none resize-none overflow-hidden focus:outline-none py-1.5 rounded-sm ${row.variant === 'meta' ? 'font-semibold' : ''}`}
                                            rows={segmentRows}
                                            value={segment}
                                            onFocus={() => {
                                              setSelections({})
                                              setActiveActionFieldPath(row.field_path)
                                              setTypingFieldPath(row.field_path)
                                            }}
                                            onClick={() => {
                                              setActiveActionFieldPath(row.field_path)
                                            }}
                                            onChange={(e) => {
                                              const host = panelBodyRef.current
                                              pendingScrollTopRef.current = host ? host.scrollTop : null
                                              lastChangedEditorKeyRef.current = editorKey
                                              setTypingFieldPath(row.field_path)
                                              setDrafts((prev) => {
                                                const nextSegments = splitParagraphDraft(prev?.[row.field_path] ?? '')
                                                nextSegments[segmentIndex] = e.target.value
                                                return {
                                                  ...(prev || {}),
                                                  [row.field_path]: joinParagraphSegments(nextSegments),
                                                }
                                              })
                                            }}
                                            onBlur={() => {
                                              setTypingFieldPath((prev) => (prev === row.field_path ? '' : prev))
                                            }}
                                            onSelect={(e) => {
                                              const el = e.currentTarget
                                              const next = el.selectionStart < el.selectionEnd
                                                ? String(el.value || '').slice(el.selectionStart, el.selectionEnd).trim()
                                                : ''
                                              setSelections((prev) => ({
                                                ...(prev || {}),
                                                [row.field_path]: next,
                                              }))
                                              if (next) setActiveActionFieldPath(row.field_path)
                                            }}
                                          />
                                          <button
                                            className="absolute -bottom-3 left-1/2 -translate-x-1/2 w-5 h-5 rounded-full bg-primary text-primary-foreground border-none flex items-center justify-center cursor-pointer opacity-0 transition-all duration-150 z-10 group-hover/segment:opacity-100 shadow-sm"
                                            type="button"
                                            onClick={() => appendParagraphToRow(row, segmentIndex)}
                                            title="Yeni paragraf ekle"
                                          >
                                            <Plus size={10} />
                                          </button>
                                        </div>
                                      )
                                    })}
                                  </div>
                                ) : (
                                  <textarea
                                    ref={(el) => {
                                      if (el) textRefs.current[row.field_path] = el
                                      else delete textRefs.current[row.field_path]
                                    }}
                                    className={`block w-full text-[15px] leading-relaxed text-foreground bg-transparent border-none resize-none overflow-hidden focus:outline-none py-1.5 rounded-sm ${row.variant === 'meta' ? 'font-semibold' : ''}`}
                                    rows={rows}
                                    value={draft}
                                    onFocus={() => {
                                      setSelections({})
                                      setActiveActionFieldPath(row.field_path)
                                      setTypingFieldPath(row.field_path)
                                    }}
                                    onClick={() => {
                                      setActiveActionFieldPath(row.field_path)
                                    }}
                                    onChange={(e) => {
                                      const host = panelBodyRef.current
                                      pendingScrollTopRef.current = host ? host.scrollTop : null
                                      lastChangedEditorKeyRef.current = row.field_path
                                      setTypingFieldPath(row.field_path)
                                      setDrafts((prev) => ({
                                        ...(prev || {}),
                                        [row.field_path]: e.target.value,
                                      }))
                                    }}
                                    onBlur={() => {
                                      setTypingFieldPath((prev) => (prev === row.field_path ? '' : prev))
                                    }}
                                    onSelect={(e) => {
                                      const el = e.currentTarget
                                      const next = el.selectionStart < el.selectionEnd
                                        ? String(el.value || '').slice(el.selectionStart, el.selectionEnd).trim()
                                        : ''
                                      setSelections((prev) => ({
                                        ...(prev || {}),
                                        [row.field_path]: next,
                                      }))
                                      if (next) setActiveActionFieldPath(row.field_path)
                                    }}
                                  />
                                )}
                                
                                <div className={`absolute right-1 top-2.5 transition-opacity duration-200 z-10 ${typingFieldPath === row.field_path ? 'opacity-0 pointer-events-none' : 'opacity-0 group-hover:opacity-100 pointer-events-auto'}`}>
                                   <Tooltip>
                                     <TooltipTrigger asChild>
                                       <Button size="sm" className="h-7 text-[10px] uppercase font-bold tracking-wider px-2.5 shadow-sm" onClick={() => injectRow({ ...row, label: section.title })}>
                                          {selectedText ? 'Ekle' : 'Chate Ekle'}
                                       </Button>
                                     </TooltipTrigger>
                                     <TooltipContent side="left">
                                        <p>{selectedText ? 'Seçimi chate ekle' : 'Bu kısmı chate ekle'}</p>
                                      </TooltipContent>
                                   </Tooltip>
                                </div>
                                
                              </div>
                              {row.variant === 'body' && !paragraphSegments.length ? (
                                <button
                                  className="absolute -bottom-3 left-1/2 -translate-x-1/2 w-5 h-5 rounded-full bg-primary text-primary-foreground border-none flex items-center justify-center cursor-pointer opacity-0 transition-all duration-150 z-10 group-hover:opacity-100 shadow-sm"
                                  type="button"
                                  onClick={() => appendParagraphToRow(row)}
                                  title="Yeni paragraf ekle"
                                >
                                  <Plus size={10} />
                                </button>
                              ) : null}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                </section>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </aside>
  )
}
