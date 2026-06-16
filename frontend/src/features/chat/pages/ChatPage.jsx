import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../../auth/useAuth.js'
import { ChatSidebar } from '../components/ChatSidebar.jsx'
import { ChatView } from '../components/ChatView.jsx'
import { GeneratedDocumentPreviewPanel } from '../components/GeneratedDocumentPreviewPanel.jsx'
import { PetitionPreviewPanel } from '../components/PetitionPreviewPanel.jsx'
import { SupportRequestModal } from '../components/SupportRequestModal.jsx'
import { useChatWebSocket } from '../hooks/useChatWebSocket.js'
import { normalizeIctihatDocumentText, normalizeRealtimeEvent } from '../chatContracts.js'
import { buildCourtLabel } from '../../ictihat/utils/courtLabel.js'
import { assertResponseOk, downloadBlobResponse } from '../../../shared/api/binary.js'
import { getApiReason, getRemainingCredit, humanizeApiError, isInsufficientCreditsError } from '../../../shared/api/contracts.js'
import { ToastHost } from '../../../shared/components/ToastHost.jsx'
import { SidebarProvider, SidebarInset, SidebarTrigger } from '../../../components/ui/sidebar.jsx'
import { Button } from '../../../components/ui/button.jsx'
import { SiteHeader } from '../components/sidebar-site-header.jsx'
import { RightCalendarSidebar } from '../../calendar/components/RightCalendarSidebar.jsx'
import { useUpcomingDeadline } from '../../calendar/hooks/useUpcomingDeadline.js'
import { Calendar as CalendarIcon } from 'lucide-react'

const ICTIHAT_PANEL_MIN_W = 280
const ICTIHAT_PANEL_DEFAULT_W = 360
const GENERATED_DOC_PANEL_DEFAULT_W = 560
const PETITION_PANEL_DEFAULT_W = 620
const ICTIHAT_PANEL_MAX_W = 960
const ICTIHAT_PANEL_AUTO_CLOSE_SIDEBAR_W = 1200
const MOBILE_SIDEBAR_BREAKPOINT = 720
const AI_ICTIHAT_HINT_TOAST_ID = 'hint:ai-ictihat-search'
const AI_ICTIHAT_HINT_STORAGE_KEY = 'yargucu.ai-ictihat-hint.lastShownAt'
const AI_ICTIHAT_HINT_INITIAL_DELAY_MS = 10 * 60 * 1000
const AI_ICTIHAT_HINT_COOLDOWN_MS = 7 * 24 * 60 * 60 * 1000
const UPLOAD_SUCCESS_TOAST_KIND = 'upload-success'
const UPLOAD_FORMAT_TOAST_KIND = 'upload-format-warning'
const UPLOAD_ERROR_TOAST_KIND = 'upload-error'
const ALLOWED_UPLOAD_EXTENSIONS = ['pdf', 'docx', 'udf']
const UPLOAD_ACCEPT = ALLOWED_UPLOAD_EXTENSIONS.map((ext) => `.${ext}`).join(',')
const UPLOAD_ALLOWED_LABEL = 'PDF, DOCX veya UDF'

function getUploadFileExtension(file) {
  const name = String(file?.name || '').trim()
  const dotIndex = name.lastIndexOf('.')
  return dotIndex >= 0 ? name.slice(dotIndex + 1).trim().toLowerCase() : ''
}

function formatUnsupportedUploadMessage(files) {
  const names = files
    .map((file) => String(file?.name || '').trim())
    .filter(Boolean)
    .slice(0, 3)
  if (!names.length) return `${UPLOAD_ALLOWED_LABEL} dosyası yükleyin.`

  const suffix = files.length > names.length ? ` ve ${files.length - names.length} dosya daha` : ''
  return `${names.join(', ')}${suffix} desteklenmiyor. ${UPLOAD_ALLOWED_LABEL} dosyası yükleyin.`
}

function formatIctihatCitation(it) {
  if (!it || typeof it !== 'object') return 'Karar'
  if (it.citation) return String(it.citation)
  const kurum = String(it.kurum || it.court || '').trim()
  const daire = String(it.daire_label ?? it.daire ?? it.yargitay_daire ?? '').trim()
  const court = buildCourtLabel({ kurum, daire })

  const eY = it.esas_yil ?? it.esas?.yil
  const eS = it.esas_sira ?? it.esas?.sira
  const kY = it.karar_yil ?? it.karar?.yil
  const kS = it.karar_sira ?? it.karar?.sira
  const tarih = it.karar_tarihi ?? it.karar?.tarih

  const parts = []
  if (court) parts.push(court)
  if (eY != null && eS != null) parts.push(`${eY}/${eS} E.`)
  if (kY != null && kS != null) parts.push(`${kY}/${kS} K.`)
  if (tarih) parts.push(String(tarih))
  const base = parts.filter(Boolean).join(' › ').trim()
  return base || 'Karar'
}

function normalizeSelectedIctihatsFromState(state) {
  const raw = state && typeof state === 'object' ? state.selectedIctihats : null
  const arr = Array.isArray(raw) ? raw : []
  const out = []
  const seen = new Set()
  for (const it of arr) {
    if (!it || typeof it !== 'object') continue
    const documentId = Number(it.document_id ?? it.documentId ?? it.id)
    if (!Number.isFinite(documentId) || documentId <= 0) continue
    if (seen.has(documentId)) continue
    seen.add(documentId)
    out.push({
      document_id: documentId,
      emsal_no: it.emsal_no != null ? String(it.emsal_no || '') : null,
      karar_no: it.karar_no != null ? String(it.karar_no || '') : null,
      daire: it.daire != null ? String(it.daire || '') : null,
      kurum: it.kurum != null ? String(it.kurum || '') : null,
    })
    if (out.length >= 50) break
  }
  return out
}

export function ChatPage() {
  const { chatId: chatIdParam } = useParams()
  const chatId = useMemo(() => (chatIdParam ? Number(chatIdParam) : null), [chatIdParam])
  const navigate = useNavigate()
  const location = useLocation()
  const { request, user, logout, refreshMe, fetch: authFetch } = useAuth()
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    if (typeof window === 'undefined') return false
    return window.innerWidth <= MOBILE_SIDEBAR_BREAKPOINT
  })
  const [isMobileViewport, setIsMobileViewport] = useState(() => {
    if (typeof window === 'undefined') return false
    return window.innerWidth <= MOBILE_SIDEBAR_BREAKPOINT
  })
  const [rightSidebarOpen, setRightSidebarOpen] = useState(false)
  const [suppressSidebarAutoClose, setSuppressSidebarAutoClose] = useState(false)
  const [draftChatKey, setDraftChatKey] = useState(0)

  const [pendingSelectedIctihats, setPendingSelectedIctihats] = useState(() => normalizeSelectedIctihatsFromState(location.state))
  const [pendingSelectedPetitionContexts, setPendingSelectedPetitionContexts] = useState([])

  useEffect(() => {
    setPendingSelectedIctihats(normalizeSelectedIctihatsFromState(location.state))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.key])

  const [chats, setChats] = useState([])
  const [loadingChats, setLoadingChats] = useState(false)
  const [chatListError, setChatListError] = useState('')
  const [docs, setDocs] = useState([])
  const [docsLoading, setDocsLoading] = useState(false)
  const [docsError, setDocsError] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [generatedDocs, setGeneratedDocs] = useState([])
  const [generatedDocsLoading, setGeneratedDocsLoading] = useState(false)
  const [generatedDocsError, setGeneratedDocsError] = useState('')
  const [downloadingGeneratedDocId, setDownloadingGeneratedDocId] = useState(null)
  const [downloadingGeneratedDocPdfId, setDownloadingGeneratedDocPdfId] = useState(null)
  const [downloadingGeneratedDocUdfId, setDownloadingGeneratedDocUdfId] = useState(null)
  const [deletingGeneratedDocId, setDeletingGeneratedDocId] = useState(null)
  const [petitions, setPetitions] = useState([])
  const [petitionsLoading, setPetitionsLoading] = useState(false)
  const [petitionsError, setPetitionsError] = useState('')
  const [downloadingPetitionKey, setDownloadingPetitionKey] = useState('')
  const [deletingPetitionId, setDeletingPetitionId] = useState(null)
  const [_downloadingWordToken, setDownloadingWordToken] = useState('') // `${format}:${token}`
  const [toasts, setToasts] = useState([])
  const [featureHint, setFeatureHint] = useState(null)
  const [supportModalOpen, setSupportModalOpen] = useState(false)
  const [creditBanner, setCreditBanner] = useState(null)
  const [preparing, setPreparing] = useState(null) // { kind: 'dilekce'|'word', op?: 'generate'|'revise' }
  const [ictihatPanelOpen, setIctihatPanelOpen] = useState(false)
  const [ictihatPanelItem, setIctihatPanelItem] = useState(null)
  const [ictihatPanelLoading, setIctihatPanelLoading] = useState(false)
  const [ictihatPanelError, setIctihatPanelError] = useState('')
  const [ictihatPanelText, setIctihatPanelText] = useState('')
  const [ictihatPanelHighlights, setIctihatPanelHighlights] = useState([]) // atif blocks to highlight in text
  const [ictihatPanelWidth, setIctihatPanelWidth] = useState(ICTIHAT_PANEL_DEFAULT_W)
  const [petitionPanelOpen, setPetitionPanelOpen] = useState(false)
  const [petitionPanelLoading, setPetitionPanelLoading] = useState(false)
  const [petitionPanelError, setPetitionPanelError] = useState('')
  const [petitionPanelData, setPetitionPanelData] = useState(null)
  const [petitionPanelSavingFieldPath, setPetitionPanelSavingFieldPath] = useState('')
  const [petitionPanelScrollTop, setPetitionPanelScrollTop] = useState(0)
  const [generatedDocPanelOpen, setGeneratedDocPanelOpen] = useState(false)
  const [generatedDocPanelLoading, setGeneratedDocPanelLoading] = useState(false)
  const [generatedDocPanelError, setGeneratedDocPanelError] = useState('')
  const [generatedDocPanelData, setGeneratedDocPanelData] = useState(null)
  const dragRef = useRef({ active: false })
  const ictihatTextRef = useRef(null)
  const lastIctihatAutoScrollKeyRef = useRef('')
  const [ictihatScrollTick, setIctihatScrollTick] = useState(0)
  useEffect(() => {
    // Reset per-chat transient download hints when switching chats
    setDownloadingWordToken('')
    setToasts([])
    setPreparing(null)
    setCreditBanner(null)
    setIctihatPanelOpen(false)
    setIctihatPanelItem(null)
    setIctihatPanelLoading(false)
    setIctihatPanelError('')
    setIctihatPanelText('')
    setIctihatPanelHighlights([])
    setIctihatPanelWidth(ICTIHAT_PANEL_DEFAULT_W)
    setPetitionPanelOpen(false)
    setPetitionPanelLoading(false)
    setPetitionPanelError('')
    setPetitionPanelData(null)
    setPetitionPanelSavingFieldPath('')
    setDeletingPetitionId(null)
    setDeletingGeneratedDocId(null)
    setDownloadingGeneratedDocId(null)
    setDownloadingGeneratedDocPdfId(null)
    setDownloadingGeneratedDocUdfId(null)
    setGeneratedDocPanelOpen(false)
    setGeneratedDocPanelLoading(false)
    setGeneratedDocPanelError('')
    setGeneratedDocPanelData(null)
    setPendingSelectedPetitionContexts([])
    setSuppressSidebarAutoClose(false)
  }, [chatId])

  useEffect(() => {
    const currentCredit = Number(user?.credit)
    if (Number.isFinite(currentCredit) && currentCredit <= 0) {
      setCreditBanner({
        title: 'Kredi bakiyesi gerekli',
        message: 'Mesaj gönderimi ve içtihat taraması için hesabınızda kullanılabilir kredi bulunmuyor. Devam etmek için kredi yükleyin.',
        compactMessage: 'Mesaj ve içtihat araması için kredi yükleyin.',
      })
      return
    }
    setCreditBanner((prev) => (prev?.sticky ? prev : null))
  }, [user?.credit])

  useEffect(() => {
    const getIsMobile = () => window.innerWidth <= MOBILE_SIDEBAR_BREAKPOINT
    let prevMobile = getIsMobile()

    const applyViewportMode = () => {
      const nextMobile = getIsMobile()
      if (prevMobile === nextMobile) return
      prevMobile = nextMobile
      setIsMobileViewport(nextMobile)
      if (nextMobile) {
        setSidebarCollapsed(true)
      }
    }

    window.addEventListener('resize', applyViewportMode)
    return () => window.removeEventListener('resize', applyViewportMode)
  }, [])

  // Exclusive sidebars on mobile (opening one closes the other)
  useEffect(() => {
    if (!isMobileViewport) return
    if (rightSidebarOpen && !sidebarCollapsed) {
      setSidebarCollapsed(true)
    }
  }, [rightSidebarOpen, isMobileViewport, sidebarCollapsed])

  useEffect(() => {
    if (!isMobileViewport) return
    if (!sidebarCollapsed && rightSidebarOpen) {
      setRightSidebarOpen(false)
    }
  }, [sidebarCollapsed, isMobileViewport, rightSidebarOpen])


  const closeIctihatPanel = useCallback(() => {
    setIctihatPanelOpen(false)
    setIctihatPanelItem(null)
    setIctihatPanelLoading(false)
    setIctihatPanelError('')
    setIctihatPanelText('')
    setIctihatPanelHighlights([])
    setSuppressSidebarAutoClose(false)
  }, [])

  const closePetitionPanel = useCallback(() => {
    setPetitionPanelOpen(false)
    setPetitionPanelLoading(false)
    setPetitionPanelError('')
    setPetitionPanelData(null)
    setPetitionPanelSavingFieldPath('')
    setPetitionPanelScrollTop(0)
    setSuppressSidebarAutoClose(false)
  }, [])

  const closeGeneratedDocPanel = useCallback(() => {
    setGeneratedDocPanelOpen(false)
    setGeneratedDocPanelLoading(false)
    setGeneratedDocPanelError('')
    setGeneratedDocPanelData(null)
    setSuppressSidebarAutoClose(false)
  }, [])

  const openSettings = useCallback((activeKey = 'account') => {
    navigate('/settings', { state: { activeKey } })
  }, [navigate])

  const openIctihatSearchRecommendation = useCallback(
    (recommendation) => {
      const payload = recommendation && typeof recommendation === 'object' ? recommendation : {}
      const queryText = String(payload?.query_text ?? payload?.queryText ?? '').trim()
      const searchMode = String(payload?.search_mode ?? payload?.searchMode ?? 'ai').trim() || 'ai'
      navigate('/ictihat', {
        state: {
          ictihatRecommendation: {
            queryText,
            searchMode,
          },
        },
      })
    },
    [navigate],
  )

  const dismissToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const showAiIctihatHintToast = useCallback(() => {
    try {
      window.localStorage.setItem(AI_ICTIHAT_HINT_STORAGE_KEY, String(Date.now()))
    } catch {
      // Best effort only; the hint should still be dismissible if storage is unavailable.
    }

    setFeatureHint({
      title: 'AI İçtihat Arama önerisi',
      subtitle: "İçtihat üzerine yoğunlaşan çalışmalarınızda Yargucu'nun AI İçtihat Arama özelliğini kullanmanızı tavsiye ederiz.",
      actionLabel: 'AI İçtihat Arama',
      onAction: () => {
        setFeatureHint(null)
        navigate('/ictihat')
      },
    })
  }, [navigate])

  const submitSupportRequest = useCallback(
    async (message) => {
      const safeMessage = String(message || '').trim()
      if (!safeMessage) throw new Error('Mesaj bos olamaz')
      await request('/v1/support/mail', {
        method: 'POST',
        body: { message: safeMessage },
      })
      const toastId = `support:${Date.now()}`
      setToasts((prev) => [
        {
          id: toastId,
          kind: 'support',
          title: 'Destek talebiniz gonderildi',
          subtitle: 'En kisa surede sizinle iletisime gececegiz.',
          ttlMs: 3500,
        },
        ...prev.filter((x) => x.id !== toastId),
      ])
    },
    [request],
  )

  const showCreditBanner = useCallback((err) => {
    const remainingCredit = getRemainingCredit(err)
    const remainingText =
      remainingCredit == null ? '' : ` Kalan kredi: ${remainingCredit.toLocaleString('tr-TR', { maximumFractionDigits: 2 })}.`

    setCreditBanner({
      title: 'Kredi bakiyesi yetersiz',
      message: `Bu işlem için kullanılabilir krediniz yetersiz.${remainingText}`,
      compactMessage:
        remainingCredit == null
          ? 'Bu işlem için ek kredi yükleyin.'
          : `Kalan kredi: ${remainingCredit.toLocaleString('tr-TR', { maximumFractionDigits: 2 })}. Ek kredi yükleyin.`,
      sticky: true,
    })
  }, [])

  const handleUnavailableChat = useCallback(() => {
    closeIctihatPanel()
    closePetitionPanel()
    closeGeneratedDocPanel()
    setDocs([])
    setGeneratedDocs([])
    setPetitions([])
    setDocsError('')
    setGeneratedDocsError('')
    setPetitionsError('')
    setChatListError('')
    navigate('/chat', { replace: true })
  }, [closeGeneratedDocPanel, closeIctihatPanel, closePetitionPanel, navigate])

  useEffect(() => {
    let initialTimer = 0
    let intervalId = 0

    const canShowHint = () => {
      if (document.visibilityState !== 'visible') return false
      if (creditBanner?.message) return false
      if (preparing?.kind) return false
      if (featureHint) return false
      if (Array.isArray(toasts) && toasts.some((t) => t.id === AI_ICTIHAT_HINT_TOAST_ID)) return false

      try {
        const raw = window.localStorage.getItem(AI_ICTIHAT_HINT_STORAGE_KEY)
        const lastShownAt = Number(raw)
        if (!Number.isFinite(lastShownAt) || lastShownAt <= 0) return true
        return Date.now() - lastShownAt >= AI_ICTIHAT_HINT_COOLDOWN_MS
      } catch {
        return true
      }
    }

    const maybeShowHint = () => {
      if (!canShowHint()) return
      showAiIctihatHintToast()
    }

    initialTimer = window.setTimeout(() => {
      maybeShowHint()
    }, AI_ICTIHAT_HINT_INITIAL_DELAY_MS)

    intervalId = window.setInterval(() => {
      maybeShowHint()
    }, 10 * 60 * 1000)

    return () => {
      window.clearTimeout(initialTimer)
      window.clearInterval(intervalId)
    }
  }, [creditBanner?.message, featureHint, preparing?.kind, showAiIctihatHintToast, toasts])

  useEffect(() => {
    // We intentionally removed the sidebar auto-collapse logic to allow
    // both sidebar and panels to coexist regardless of width.
  }, [generatedDocPanelOpen, ictihatPanelOpen, ictihatPanelWidth, petitionPanelOpen, sidebarCollapsed, suppressSidebarAutoClose])

  useEffect(() => {
    // If user shrinks the panel back, re-enable auto-close behavior.
    if (!ictihatPanelOpen && !petitionPanelOpen && !generatedDocPanelOpen) return
    if (ictihatPanelWidth < ICTIHAT_PANEL_AUTO_CLOSE_SIDEBAR_W) {
      setSuppressSidebarAutoClose(false)
    }
  }, [generatedDocPanelOpen, ictihatPanelOpen, ictihatPanelWidth, petitionPanelOpen])

  const clampPanelWidth = useCallback((w, fallback = ICTIHAT_PANEL_DEFAULT_W) => {
    const max = Math.min(ICTIHAT_PANEL_MAX_W, Math.max(ICTIHAT_PANEL_MIN_W, window.innerWidth - 80))
    const val = Number(w) || fallback
    return Math.max(ICTIHAT_PANEL_MIN_W, Math.min(val, max))
  }, [])

  const startResize = useCallback(
    (e) => {
      if (!ictihatPanelOpen && !petitionPanelOpen && !generatedDocPanelOpen) return
      if (e?.button != null && e.button !== 0) return

      dragRef.current.active = true
      try {
        e.currentTarget?.setPointerCapture?.(e.pointerId)
      } catch {
        // ignore
      }
      const prevCursor = document.body.style.cursor
      const prevSelect = document.body.style.userSelect
      document.body.style.cursor = 'col-resize'
      document.body.style.userSelect = 'none'

      const onMove = (ev) => {
        if (!dragRef.current.active) return
        const nextW = window.innerWidth - Number(ev.clientX || 0)
        setIctihatPanelWidth(clampPanelWidth(nextW, petitionPanelOpen ? PETITION_PANEL_DEFAULT_W : GENERATED_DOC_PANEL_DEFAULT_W))
      }
      const stop = () => {
        dragRef.current.active = false
        window.removeEventListener('pointermove', onMove)
        window.removeEventListener('pointerup', stop)
        document.body.style.cursor = prevCursor
        document.body.style.userSelect = prevSelect
      }
      window.addEventListener('pointermove', onMove)
      window.addEventListener('pointerup', stop, { once: true })
    },
    [clampPanelWidth, generatedDocPanelOpen, ictihatPanelOpen, petitionPanelOpen],
  )

  const computeHighlightRanges = useCallback((text, phrases) => {
    const original = String(text || '')
    const arr = Array.isArray(phrases) ? phrases : []
    if (!original || !arr.length) return []

    const normalizeWithMap = (input) => {
      const s = String(input || '')
      let norm = ''
      const map = []
      let lastWasSpace = false
      for (let i = 0; i < s.length; i++) {
        let ch = s[i]
        // unify quotes/apostrophes
        if (ch === '’' || ch === '‘' || ch === '´' || ch === '`') ch = "'"
        if (ch === '“' || ch === '”' || ch === '«' || ch === '»') ch = '"'

        const isWs = /\s/.test(ch)
        if (isWs) ch = ' '

        // lowercase (TR friendly)
        ch = ch.toLocaleLowerCase('tr-TR')

        // keep only letters/digits/spaces (drop punctuation)
        const keep = /[0-9a-zçğıöşü ]/i.test(ch)
        if (!keep) continue

        if (ch === ' ') {
          if (lastWasSpace) continue
          lastWasSpace = true
          norm += ' '
          map.push(i)
          continue
        }
        lastWasSpace = false
        norm += ch
        map.push(i)
      }
      norm = norm.trim()
      // trim map to match
      while (norm.startsWith(' ') && map.length) map.shift()
      while (norm.endsWith(' ') && map.length) map.pop()
      return { norm, map }
    }

    const normalize = (input) => normalizeWithMap(input).norm

    const buildCandidates = (phrase) => {
      const rawPhrase = String(phrase || '')
      const n = normalize(rawPhrase)
      if (!n) return []
      const out = []
      out.push(n)

      // Also try smaller segments (line/sentence-ish splits) to be robust when the quote is paraphrased or truncated.
      const segs = rawPhrase
        .split(/[\r\n]+|[.;:!?]+/g)
        .map((s) => String(s || '').trim())
        .filter((s) => s.length >= 30)
        .sort((a, b) => b.length - a.length)
        .slice(0, 3)
      for (const s of segs) {
        const sn = normalize(s)
        if (sn) out.push(sn)
      }

      // helpful shorter anchors (character windows)
      const maxLen = 220
      if (n.length > maxLen + 20) {
        out.push(n.slice(0, maxLen).trim())
        out.push(n.slice(-maxLen).trim())
        const mid = Math.floor((n.length - maxLen) / 2)
        out.push(n.slice(mid, mid + maxLen).trim())
      }

      // word-based anchors (smaller windows catch minor diffs better than 18/28-word prefixes)
      const words = n.split(' ').filter(Boolean)
      if (words.length > 12) out.push(words.slice(0, 12).join(' '))
      if (words.length > 14) out.push(words.slice(0, 14).join(' '))
      if (words.length > 18) out.push(words.slice(0, 18).join(' '))
      if (words.length > 28) out.push(words.slice(0, 28).join(' '))
      if (words.length > 16) out.push(words.slice(-12).join(' '))
      if (words.length > 20) {
        const midW = Math.floor((words.length - 12) / 2)
        out.push(words.slice(midW, midW + 12).join(' '))
      }

      // de-dup, keep meaningful
      return Array.from(new Set(out)).filter((x) => x.length >= 40)
    }

    const { norm: normText, map } = normalizeWithMap(original)
    if (!normText) return []

    const ranges = []
    for (const p of arr.slice(0, 20)) {
      const raw = String(p || '').trim()
      if (!raw) continue

      const candidates = buildCandidates(raw)
      let matchedThisPhrase = false
      for (const cand of candidates) {
        let from = 0
        let guard = 0
        while (true) {
          const idx = normText.indexOf(cand, from)
          if (idx === -1) break
          const startOrig = map[idx] ?? 0
          const endOrig = (map[idx + cand.length - 1] ?? startOrig) + 1
          ranges.push([startOrig, endOrig])
          matchedThisPhrase = true
          from = idx + Math.max(1, Math.floor(cand.length / 3))
          if (++guard >= 20) break
        }
        if (matchedThisPhrase) break // don't overmatch; one anchor is enough per phrase
      }
    }

    if (!ranges.length) return []
    ranges.sort((a, b) => a[0] - b[0] || a[1] - b[1])
    const merged = []
    for (const [st, en] of ranges) {
      const last = merged[merged.length - 1]
      if (!last) {
        merged.push([st, en])
        continue
      }
      if (st <= last[1]) {
        last[1] = Math.max(last[1], en)
      } else {
        merged.push([st, en])
      }
    }
    return merged.slice(0, 80)
  }, [])

  const renderHighlightedText = useCallback((text, ranges) => {
    const s = String(text || '')
    const rs = Array.isArray(ranges) ? ranges : []
    if (!rs.length) return s
    const out = []
    let cur = 0
    for (let i = 0; i < rs.length; i++) {
      const [st, en] = rs[i]
      if (st > cur) out.push(s.slice(cur, st))
      out.push(
        <mark key={`m-${i}-${st}-${en}`} className="ictihat-mark">
          {s.slice(st, en)}
        </mark>,
      )
      cur = en
    }
    if (cur < s.length) out.push(s.slice(cur))
    return out
  }, [])

  const highlightRanges = useMemo(
    () => computeHighlightRanges(ictihatPanelText, ictihatPanelHighlights),
    [computeHighlightRanges, ictihatPanelHighlights, ictihatPanelText],
  )

  useEffect(() => {
    if (!ictihatPanelOpen) return
    if (!ictihatPanelItem?.document_id) return
    if (!ictihatPanelText) return
    if (!highlightRanges?.length) return
    const key = `${String(ictihatPanelItem.document_id)}:${String(highlightRanges?.[0]?.[0] ?? '')}:${String(
      highlightRanges?.[0]?.[1] ?? '',
    )}`
    if (lastIctihatAutoScrollKeyRef.current === key) return
    lastIctihatAutoScrollKeyRef.current = key

    // Wait for marks to render, then scroll to first highlight.
    const t = window.setTimeout(() => {
      const root = ictihatTextRef.current
      if (!root) return
      const el = root.querySelector?.('mark.ictihat-mark')
      if (!el?.scrollIntoView) return
      try {
        el.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' })
      } catch {
        // ignore
      }
    }, 0)
    return () => window.clearTimeout(t)
  }, [highlightRanges, ictihatPanelItem?.document_id, ictihatPanelOpen, ictihatPanelText, ictihatScrollTick])

  const openIctihatPanel = useCallback(
    async (item, opts = {}) => {
      const did = item?.document_id
      if (did == null) return

      // If the same document is already open, don't refetch/reopen.
      // Just update highlights (if provided) and re-run autoscroll.
      if (ictihatPanelOpen && Number(ictihatPanelItem?.document_id) === Number(did)) {
        const nextHighlights = Array.isArray(opts?.atifBlocks) ? opts.atifBlocks : []
        setIctihatPanelHighlights(nextHighlights)
        // Force autoscroll even if the key didn't change.
        lastIctihatAutoScrollKeyRef.current = ''
        setIctihatScrollTick((x) => x + 1)
        return
      }

      setIctihatPanelOpen(true)
      setGeneratedDocPanelOpen(false)
      setGeneratedDocPanelLoading(false)
      setGeneratedDocPanelError('')
      setGeneratedDocPanelData(null)
      setPetitionPanelOpen(false)
      setPetitionPanelLoading(false)
      setPetitionPanelError('')
      setPetitionPanelData(null)
      setPetitionPanelSavingFieldPath('')
      setIctihatPanelItem(item)
      setIctihatPanelError('')
      setIctihatPanelText('')
      setIctihatPanelHighlights(Array.isArray(opts?.atifBlocks) ? opts.atifBlocks : [])
      setIctihatPanelLoading(true)
      setIctihatPanelWidth((w) => clampPanelWidth(w, ICTIHAT_PANEL_DEFAULT_W))
      if (isMobileViewport) setSidebarCollapsed(true)
      // Ensure the first autoscroll runs for new docs too.
      lastIctihatAutoScrollKeyRef.current = ''
      setIctihatScrollTick((x) => x + 1)
      try {
        const qs = new URLSearchParams()
        if (chatId) qs.set('chat_id', String(chatId))
        const suffix = qs.toString()
        const url = suffix
          ? `/v1/ictihat/document/${encodeURIComponent(String(did))}?${suffix}`
          : `/v1/ictihat/document/${encodeURIComponent(String(did))}`
        const data = await request(url, { method: 'GET' })
        setIctihatPanelText(normalizeIctihatDocumentText(data))
      } catch (err) {
        if (isInsufficientCreditsError(err)) showCreditBanner(err)
        setIctihatPanelError(humanizeApiError(err, 'Ictihat metni yuklenemedi'))
      } finally {
        setIctihatPanelLoading(false)
      }
    },
    [chatId, clampPanelWidth, ictihatPanelItem?.document_id, ictihatPanelOpen, isMobileViewport, request, showCreditBanner],
  )

  const refreshGeneratedDocs = useCallback(async () => {
    setGeneratedDocsError('')
    if (!chatId) {
      setGeneratedDocs([])
      return
    }
    setGeneratedDocsLoading(true)
    try {
      const data = await request('/v1/generated-documents/list', { method: 'POST', body: { chat_id: chatId } })
      setGeneratedDocs(Array.isArray(data.documents) ? data.documents : [])
    } catch (err) {
      if (getApiReason(err) === 'not_found') {
        handleUnavailableChat()
        return
      }
      setGeneratedDocsError(err?.message || 'Dokümanlar yüklenemedi')
    } finally {
      setGeneratedDocsLoading(false)
    }
  }, [chatId, handleUnavailableChat, request])

  const openGeneratedDocPreview = useCallback(
    async ({ generatedDocumentId } = {}) => {
      const docId = Number(generatedDocumentId)
      if (!chatId || !Number.isFinite(docId) || docId <= 0) return

      setGeneratedDocPanelOpen(true)
      setGeneratedDocPanelLoading(true)
      setGeneratedDocPanelError('')
      setGeneratedDocPanelData(null)
      setIctihatPanelOpen(false)
      setIctihatPanelItem(null)
      setIctihatPanelLoading(false)
      setIctihatPanelError('')
      setIctihatPanelText('')
      setIctihatPanelHighlights([])
      closePetitionPanel()
      setIctihatPanelWidth((w) => {
        const current = Number(w) || 0
        if (current >= GENERATED_DOC_PANEL_DEFAULT_W) return clampPanelWidth(current, GENERATED_DOC_PANEL_DEFAULT_W)
        return clampPanelWidth(GENERATED_DOC_PANEL_DEFAULT_W, GENERATED_DOC_PANEL_DEFAULT_W)
      })
      if (isMobileViewport) setSidebarCollapsed(true)

      try {
        const data = await request('/v1/generated-documents/preview', {
          method: 'POST',
          body: { chat_id: chatId, generated_document_id: docId },
        })
        setGeneratedDocPanelData(data?.document || null)
      } catch (err) {
        if (isInsufficientCreditsError(err)) showCreditBanner(err)
        setGeneratedDocPanelError(humanizeApiError(err, 'Doküman önizlemesi yüklenemedi'))
      } finally {
        setGeneratedDocPanelLoading(false)
      }
    },
    [chatId, clampPanelWidth, closePetitionPanel, isMobileViewport, request, showCreditBanner],
  )

  const refreshPetitions = useCallback(async () => {
    setPetitionsError('')
    if (!chatId) {
      setPetitions([])
      return
    }
    setPetitionsLoading(true)
    try {
      const data = await request('/v1/petitions/list', { method: 'POST', body: { chat_id: chatId } })
      setPetitions(Array.isArray(data.petitions) ? data.petitions : [])
    } catch (err) {
      if (getApiReason(err) === 'not_found') {
        handleUnavailableChat()
        return
      }
      setPetitionsError(err?.message || 'Dilekçeler yüklenemedi')
    } finally {
      setPetitionsLoading(false)
    }
  }, [chatId, handleUnavailableChat, request])

  const openPetitionPreview = useCallback(
    async ({ petitionId, versionId } = {}) => {
      const petitionIdNum = Number(petitionId)
      const versionIdNum = Number(versionId)
      if (!chatId || !Number.isFinite(petitionIdNum) || petitionIdNum <= 0) return

      setPetitionPanelScrollTop(0)
      setPetitionPanelOpen(true)
      setPetitionPanelLoading(true)
      setPetitionPanelError('')
      setPetitionPanelData(null)
      setGeneratedDocPanelOpen(false)
      setGeneratedDocPanelLoading(false)
      setGeneratedDocPanelError('')
      setGeneratedDocPanelData(null)
      setIctihatPanelWidth((w) => {
        // If it's already wider than or equal to the petition default, keep current width.
        // Otherwise, force it to expand to PETITION_PANEL_DEFAULT_W.
        const current = Number(w) || 0
        if (current >= PETITION_PANEL_DEFAULT_W) return clampPanelWidth(current, PETITION_PANEL_DEFAULT_W)
        return clampPanelWidth(PETITION_PANEL_DEFAULT_W, PETITION_PANEL_DEFAULT_W)
      })
      setIctihatPanelOpen(false)
      setIctihatPanelItem(null)
      setIctihatPanelLoading(false)
      setIctihatPanelError('')
      setIctihatPanelText('')
      setIctihatPanelHighlights([])
      if (isMobileViewport) setSidebarCollapsed(true)

      try {
        const body = {
          chat_id: chatId,
          petition_id: petitionIdNum,
          ...(Number.isFinite(versionIdNum) && versionIdNum > 0 ? { version_id: versionIdNum } : {}),
        }
        const data = await request('/v1/petitions/preview', { method: 'POST', body })
        setPetitionPanelData(data?.petition || null)
      } catch (err) {
        if (isInsufficientCreditsError(err)) showCreditBanner(err)
        setPetitionPanelError(humanizeApiError(err, 'Dilekçe önizlemesi yüklenemedi'))
      } finally {
        setPetitionPanelLoading(false)
      }
    },
    [chatId, clampPanelWidth, isMobileViewport, request, showCreditBanner],
  )

  const patchPetitionFields = useCallback(
    async (patches) => {
      const petitionId = Number(petitionPanelData?.petition_id)
      const versionId = Number(petitionPanelData?.version?.version_id)
      const safePatches = Array.isArray(patches) ? patches.filter((item) => item?.field_path) : []
      if (!chatId || !Number.isFinite(petitionId) || petitionId <= 0 || !safePatches.length) return

      setPetitionPanelSavingFieldPath('__all__')
      setPetitionsError('')
      try {
        const body = {
          chat_id: chatId,
          petition_id: petitionId,
          ...(Number.isFinite(versionId) && versionId > 0 ? { version_id: versionId } : {}),
          patches: safePatches.map((item) => ({
            field_path: String(item.field_path),
            value: item.value,
          })),
        }
        const data = await request('/v1/petitions/patch', { method: 'POST', body })
        setPetitionPanelData(data?.petition || null)
        await refreshPetitions()
      } catch (err) {
        if (isInsufficientCreditsError(err)) showCreditBanner(err)
        setPetitionPanelError(humanizeApiError(err, 'Dilekçe alanı güncellenemedi'))
        throw err
      } finally {
        setPetitionPanelSavingFieldPath('')
      }
    },
    [chatId, petitionPanelData?.petition_id, petitionPanelData?.version?.version_id, refreshPetitions, request, showCreditBanner],
  )

  const injectPetitionContextToChat = useCallback((payload) => {
    const petitionId = Number(petitionPanelData?.petition_id)
    const versionId = Number(petitionPanelData?.version?.version_id)
    const fieldPath = String(payload?.field_path || '').trim()
    const selectedText = String(payload?.selected_text || '').trim()
    if (!Number.isFinite(petitionId) || petitionId <= 0 || !fieldPath || !selectedText) return

    const nextItem = {
      petition_id: petitionId,
      version_id: Number.isFinite(versionId) && versionId > 0 ? versionId : null,
      field_path: fieldPath,
      selected_text: selectedText,
      section_title: payload?.section_title ? String(payload.section_title) : null,
    }

    setPendingSelectedPetitionContexts((prev) => {
      const items = Array.isArray(prev) ? [...prev] : []
      const key = [nextItem.petition_id, nextItem.version_id, nextItem.field_path, nextItem.selected_text]
        .map((v) => String(v || ''))
        .join(':')
      const seen = new Set(
        items.map((item) => [item?.petition_id, item?.version_id, item?.field_path, item?.selected_text].map((v) => String(v || '')).join(':')),
      )
      if (seen.has(key)) return items
      items.push(nextItem)
      return items.slice(-20)
    })
    if (isMobileViewport) {
      closePetitionPanel()
    }
  }, [closePetitionPanel, isMobileViewport, petitionPanelData?.petition_id, petitionPanelData?.version?.version_id])

  useChatWebSocket(chatId, {
    onEvent: (evt) => {
      const normalized = normalizeRealtimeEvent(evt)
      const type = normalized?.type

      if (type === 'dilekce_preparing') {
        setPreparing({ kind: 'dilekce', op: String(normalized?.op || 'generate') })
      } else if (type === 'word_preparing') {
        setPreparing({ kind: 'word' })
      } else if (type === 'ictihat_searching') {
        setPreparing({ kind: 'ictihat', op: 'search' })
      } else if (type === 'ictihat_search_done') {
        setPreparing(null)
      }

      if (type === 'petition_ready') {
        const petitionId = Number(normalized?.petition_id)
        const versionId = Number(normalized?.version_id)
        setPreparing(null)
        refreshPetitions()
        openPetitionPreview({ petitionId, versionId })
      } else if (type === 'petition_failed') {
        setPreparing(null)
        refreshPetitions()
      } else if (type === 'petition_updated') {
        const petitionId = Number(normalized?.petition_id)
        const versionId = Number(normalized?.version_id)
        refreshPetitions()
        if (petitionPanelOpen && Number(petitionPanelData?.petition_id) === petitionId) {
          openPetitionPreview({ petitionId, versionId })
        }
      }

      // Ephemeral Word output (docx over token)
      if (type === 'word_ready') {
        const token = String(normalized?.token || '')
        if (!token) return
        const filename = String(normalized?.filename || 'document.docx')
        const toastId = `word:${token}`
        setPreparing(null)
        refreshGeneratedDocs()
        setToasts((prev) => [
          {
            id: toastId,
            kind: 'word',
            title: 'Word dosyası hazır',
            subtitle: filename,
            actionLabel: 'DOCX indir',
            onAction: () => {
              setToasts((p) => p.filter((x) => x.id !== toastId))
              downloadWordDocx({ token, fallbackFilename: filename })
            },
          },
          ...prev.filter((x) => x.id !== toastId),
        ])
      } else if (type === 'word_failed') {
        setPreparing(null)
        setGeneratedDocsError(String(normalized?.error || 'DOCX olusturulamadi'))
      }
    },
  })
  const refreshChats = useCallback(
    async ({ silent = false } = {}) => {
      if (!silent) setChatListError('')
      if (!silent) setLoadingChats(true)
      try {
        const data = await request('/v1/chat/list', { method: 'POST', body: { limit: 50, offset: 0 } })
        setChats(data.chats || [])
      } catch (err) {
        if (!silent) setChatListError(err?.message || 'Sohbetler yüklenemedi')
      } finally {
        if (!silent) setLoadingChats(false)
      }
    },
    [request],
  )

  useEffect(() => {
    refreshChats({ silent: false })
  }, [refreshChats])

  useEffect(() => {
    let cancelled = false
    async function loadDocs() {
      setDocsError('')
      if (!chatId) {
        setDocs([])
        return
      }
      setDocsLoading(true)
      try {
        const data = await request('/v1/documents/list', {
          method: 'POST',
          body: { chat_id: chatId },
        })
        if (!cancelled) setDocs(Array.isArray(data.documents) ? data.documents : [])
      } catch (err) {
        if (getApiReason(err) === 'not_found') {
          if (!cancelled) handleUnavailableChat()
          return
        }
        if (!cancelled) setDocsError(err?.message || 'Belgeler yüklenemedi')
      } finally {
        if (!cancelled) setDocsLoading(false)
      }
    }
    loadDocs()
    return () => {
      cancelled = true
    }
  }, [chatId, handleUnavailableChat, request])

  useEffect(() => {
    refreshPetitions()
  }, [refreshPetitions])

  useEffect(() => {
    refreshGeneratedDocs()
  }, [refreshGeneratedDocs])

  const downloadPetitionDocx = useCallback(
    async ({ petitionId, versionId, fallbackFilename }) => {
      if (!chatId || !petitionId || !versionId) return
      const key = `docx:${petitionId}:${versionId}`
      setDownloadingPetitionKey(key)
      try {
        const res = await authFetch(
          `/v1/petitions/${encodeURIComponent(String(petitionId))}/versions/${encodeURIComponent(String(versionId))}/download?chat_id=${encodeURIComponent(String(chatId))}`,
          {
            method: 'GET',
          },
        )
        await assertResponseOk(res, 'Dilekce indirilemedi')
        await downloadBlobResponse(res, fallbackFilename || `petition-${petitionId}-v${versionId}.docx`)
      } catch (err) {
        if (isInsufficientCreditsError(err)) showCreditBanner(err)
        setPetitionsError(humanizeApiError(err, 'Dilekce indirilemedi'))
      } finally {
        setDownloadingPetitionKey('')
      }
    },
    [authFetch, chatId, showCreditBanner],
  )

  const downloadPetitionPdf = useCallback(
    async ({ petitionId, versionId, fallbackFilename, downloadKey } = {}) => {
      if (!chatId || !petitionId || !versionId) return
      const key = downloadKey || `pdf:${petitionId}:${versionId}`
      setDownloadingPetitionKey(key)
      try {
        const res = await authFetch(
          `/v1/petitions/${encodeURIComponent(String(petitionId))}/versions/${encodeURIComponent(String(versionId))}/download_pdf?chat_id=${encodeURIComponent(String(chatId))}`,
          {
            method: 'GET',
          },
        )
        await assertResponseOk(res, 'PDF indirilemedi')
        await downloadBlobResponse(res, fallbackFilename || `petition-${petitionId}-v${versionId}.pdf`)
      } catch (err) {
        if (isInsufficientCreditsError(err)) showCreditBanner(err)
        setPetitionsError(humanizeApiError(err, 'PDF indirilemedi'))
      } finally {
        setDownloadingPetitionKey('')
      }
    },
    [authFetch, chatId, showCreditBanner],
  )

  const downloadPetitionUdf = useCallback(
    async ({ petitionId, versionId, fallbackFilename }) => {
      if (!chatId || !petitionId || !versionId) return
      const key = `udf:${petitionId}:${versionId}`
      setDownloadingPetitionKey(key)
      try {
        const res = await authFetch(
          `/v1/petitions/${encodeURIComponent(String(petitionId))}/versions/${encodeURIComponent(String(versionId))}/download_udf?chat_id=${encodeURIComponent(String(chatId))}`,
          {
            method: 'GET',
          },
        )
        await assertResponseOk(res, 'UDF indirilemedi')
        await downloadBlobResponse(res, fallbackFilename || `petition-${petitionId}-v${versionId}.udf`)
      } catch (err) {
        if (isInsufficientCreditsError(err)) showCreditBanner(err)
        setPetitionsError(humanizeApiError(err, 'UDF indirilemedi'))
      } finally {
        setDownloadingPetitionKey('')
      }
    },
    [authFetch, chatId, showCreditBanner],
  )

  const downloadWordDocx = useCallback(
    async ({ token, fallbackFilename }) => {
      if (!token) return
      const key = `original:${String(token)}`
      setDownloadingWordToken(key)
      try {
        const res = await authFetch(`/v1/files/ephemeral/${encodeURIComponent(String(token))}/download`, {
          method: 'GET',
        })
        await assertResponseOk(res, 'DOCX indirilemedi')
        await downloadBlobResponse(res, fallbackFilename || 'document.docx')
      } catch (err) {
        if (isInsufficientCreditsError(err)) showCreditBanner(err)
        setPetitionsError(humanizeApiError(err, 'DOCX indirilemedi'))
      } finally {
        setDownloadingWordToken('')
      }
    },
    [authFetch, showCreditBanner],
  )

  const downloadGeneratedDoc = useCallback(
    async ({ generatedDocumentId, fallbackFilename }) => {
      const docId = Number(generatedDocumentId)
      if (!chatId || !Number.isFinite(docId) || docId <= 0) return
      setDownloadingGeneratedDocId(docId)
      try {
        const res = await authFetch(
          `/v1/generated-documents/${encodeURIComponent(String(docId))}/download?chat_id=${encodeURIComponent(String(chatId))}`,
          { method: 'GET' },
        )
        await assertResponseOk(res, 'Doküman indirilemedi')
        await downloadBlobResponse(res, fallbackFilename || `document-${docId}.docx`)
      } catch (err) {
        if (isInsufficientCreditsError(err)) showCreditBanner(err)
        setGeneratedDocsError(humanizeApiError(err, 'Doküman indirilemedi'))
      } finally {
        setDownloadingGeneratedDocId(null)
      }
    },
    [authFetch, chatId, showCreditBanner],
  )

  const downloadGeneratedDocPdf = useCallback(
    async ({ generatedDocumentId, fallbackFilename }) => {
      const docId = Number(generatedDocumentId)
      if (!chatId || !Number.isFinite(docId) || docId <= 0) return
      setDownloadingGeneratedDocPdfId(docId)
      try {
        const res = await authFetch(
          `/v1/generated-documents/${encodeURIComponent(String(docId))}/download_pdf?chat_id=${encodeURIComponent(String(chatId))}`,
          { method: 'GET' },
        )
        await assertResponseOk(res, 'PDF indirilemedi')
        const safeBase = String(fallbackFilename || `document-${docId}.docx`)
        const pdfFilename = safeBase.toLowerCase().endsWith('.docx') ? `${safeBase.slice(0, -5)}.pdf` : `${safeBase}.pdf`
        await downloadBlobResponse(res, pdfFilename)
      } catch (err) {
        if (isInsufficientCreditsError(err)) showCreditBanner(err)
        setGeneratedDocsError(humanizeApiError(err, 'PDF indirilemedi'))
      } finally {
        setDownloadingGeneratedDocPdfId(null)
      }
    },
    [authFetch, chatId, showCreditBanner],
  )

  const downloadGeneratedDocUdf = useCallback(
    async ({ generatedDocumentId, fallbackFilename }) => {
      const docId = Number(generatedDocumentId)
      if (!chatId || !Number.isFinite(docId) || docId <= 0) return
      setDownloadingGeneratedDocUdfId(docId)
      try {
        const res = await authFetch(
          `/v1/generated-documents/${encodeURIComponent(String(docId))}/download_udf?chat_id=${encodeURIComponent(String(chatId))}`,
          { method: 'GET' },
        )
        await assertResponseOk(res, 'UDF indirilemedi')
        const safeBase = String(fallbackFilename || `document-${docId}.docx`)
        const udfFilename = safeBase.toLowerCase().endsWith('.docx') ? `${safeBase.slice(0, -5)}.udf` : `${safeBase}.udf`
        await downloadBlobResponse(res, udfFilename)
      } catch (err) {
        if (isInsufficientCreditsError(err)) showCreditBanner(err)
        setGeneratedDocsError(humanizeApiError(err, 'UDF indirilemedi'))
      } finally {
        setDownloadingGeneratedDocUdfId(null)
      }
    },
    [authFetch, chatId, showCreditBanner],
  )

  const deleteGeneratedDoc = useCallback(
    async (generatedDocumentId, label) => {
      const docId = Number(generatedDocumentId)
      if (!chatId || !Number.isFinite(docId) || docId <= 0) return
      const ok = window.confirm(`"${String(label || 'Bu doküman')}" silinsin mi? Bu işlem geri alınamaz.`)
      if (!ok) return

      setDeletingGeneratedDocId(docId)
      setGeneratedDocsError('')
      try {
        await request(
          `/v1/generated-documents/${encodeURIComponent(String(docId))}?chat_id=${encodeURIComponent(String(chatId))}`,
          { method: 'DELETE' },
        )
        if (Number(generatedDocPanelData?.generated_document_id) === docId) {
          closeGeneratedDocPanel()
        }
        setGeneratedDocs((prev) => prev.filter((item) => Number(item.generated_document_id) !== docId))
      } catch (err) {
        if (isInsufficientCreditsError(err)) showCreditBanner(err)
        setGeneratedDocsError(humanizeApiError(err, 'Doküman silinemedi'))
      } finally {
        setDeletingGeneratedDocId(null)
      }
    },
    [chatId, closeGeneratedDocPanel, generatedDocPanelData?.generated_document_id, request, showCreditBanner],
  )

  const deletePetition = useCallback(
    async (petitionId, label) => {
      const petitionIdNum = Number(petitionId)
      if (!chatId || !Number.isFinite(petitionIdNum) || petitionIdNum <= 0) return
      const ok = window.confirm(`"${String(label || 'Bu dilekçe')}" silinsin mi? Bu işlem geri alınamaz.`)
      if (!ok) return

      setDeletingPetitionId(petitionIdNum)
      setPetitionsError('')
      try {
        await request(
          `/v1/petitions/${encodeURIComponent(String(petitionIdNum))}?chat_id=${encodeURIComponent(String(chatId))}`,
          { method: 'DELETE' },
        )
        if (Number(petitionPanelData?.petition_id) === petitionIdNum) {
          closePetitionPanel()
        }
        setPendingSelectedPetitionContexts((prev) =>
          Array.isArray(prev) ? prev.filter((item) => Number(item?.petition_id) !== petitionIdNum) : [],
        )
        await refreshPetitions()
      } catch (err) {
        if (isInsufficientCreditsError(err)) showCreditBanner(err)
        setPetitionsError(humanizeApiError(err, 'Dilekçe silinemedi'))
      } finally {
        setDeletingPetitionId(null)
      }
    },
    [chatId, closePetitionPanel, petitionPanelData?.petition_id, refreshPetitions, request, showCreditBanner],
  )

  const onSelectChat = useCallback(
    (id) => {
      if (isMobileViewport) setSidebarCollapsed(true)
      navigate(`/chat/${id}`)
    },
    [isMobileViewport, navigate],
  )

  const onDeleteChat = useCallback(
    async (id) => {
      const chatIdNum = Number(id)
      if (!Number.isFinite(chatIdNum)) return
      const ok = window.confirm('Bu sohbet silinsin mi? Bu işlem geri alınamaz.')
      if (!ok) return
      try {
        await request(`/v1/chat/${chatIdNum}`, { method: 'DELETE' })
        // If we deleted the active chat, return to the blank chat view.
        if (Number(chatId) === chatIdNum) {
          navigate('/chat', { replace: true })
        }
        await refreshChats()
      } catch (err) {
        setChatListError(err?.message || 'Sohbet silinemedi')
      }
    },
    [chatId, navigate, refreshChats, request],
  )

  const onNewChat = useCallback(() => {
    // Do NOT create a chat record yet.
    // Navigate to blank chat view; the first message will create the chat via /chat/stream (chat_id=null).
    setChatListError('')
    setDraftChatKey(Date.now())
    if (isMobileViewport) setSidebarCollapsed(true)
    navigate('/chat', { replace: false })
  }, [isMobileViewport, navigate])

  const onResolvedChatId = useCallback(
    async (id) => {
      if (!id) return
      navigate(`/chat/${id}`, { replace: true })
      // Refresh sidebar chat list silently; keep main view stable.
      refreshChats({ silent: true })
    },
    [navigate, refreshChats],
  )

  const refreshSidebarUser = useCallback(async () => {
    await refreshChats({ silent: true })
    try {
      await refreshMe?.()
    } catch {
      // Keep the chat flow stable even if the lightweight profile refresh fails.
    }
  }, [refreshChats, refreshMe])

  const uploadDocuments = useCallback(
    async (files) => {
      const selectedFiles = Array.from(files || [])
      if (!selectedFiles.length) return

      const unsupportedFiles = selectedFiles.filter((file) => !ALLOWED_UPLOAD_EXTENSIONS.includes(getUploadFileExtension(file)))
      if (unsupportedFiles.length) {
        setUploadError('')
        setToasts((prev) => [
          {
            id: `upload-format:${Date.now()}`,
            kind: UPLOAD_FORMAT_TOAST_KIND,
            title: `Dosya ${UPLOAD_ALLOWED_LABEL} olmalıdır.`,
            subtitle: formatUnsupportedUploadMessage(unsupportedFiles),
            ttlMs: 5500,
          },
          ...prev.filter((x) => x?.kind !== UPLOAD_FORMAT_TOAST_KIND),
        ])
        return
      }

      setUploadError('')
      setUploading(true)
      try {
        let targetChatId = chatId
        if (!targetChatId) {
          const created = await request('/v1/chat/create', { method: 'POST', body: { title: null } })
          targetChatId = Number(created.chat_id)
          if (!Number.isFinite(targetChatId)) throw new Error('Sohbet olusturulamadi')
          await refreshChats()
          navigate(`/chat/${targetChatId}`)
        }

        const form = new FormData()
        form.append('chat_id', String(targetChatId))
        selectedFiles.forEach((f) => form.append('files', f))
        const res = await authFetch('/v1/documents/upload', {
          method: 'POST',
          body: form,
        })
        await assertResponseOk(res, 'Belgeler yuklenemedi')
        const data = await res.json()
        const newDocs = Array.isArray(data.documents) ? data.documents : []
        setDocs((prev) => {
          const existing = Array.isArray(prev) ? prev : []
          const newIds = new Set(newDocs.map((d) => Number(d.document_id)))
          return [...existing.filter((d) => !newIds.has(Number(d.document_id))), ...newDocs]
        })
        const uploadedCount = newDocs.length || selectedFiles.length
        const isMultipleUpload = uploadedCount > 1
        setToasts((prev) => [
          {
            id: `upload:${Date.now()}`,
            kind: UPLOAD_SUCCESS_TOAST_KIND,
            title: isMultipleUpload ? 'Belgeler başarıyla yüklendi' : 'Belge başarıyla yüklendi',
            subtitle: isMultipleUpload
              ? 'Dokümanlarınız kaydedildi ve artık dosyalarınızda kullanılabilir.'
              : 'Dokümanınız kaydedildi ve artık dosyalarınızda kullanılabilir.',
            ttlMs: 4500,
          },
          ...prev.filter((x) => x?.kind !== UPLOAD_SUCCESS_TOAST_KIND),
        ])
      } catch (err) {
        if (isInsufficientCreditsError(err)) showCreditBanner(err)
        const uploadMessage = humanizeApiError(err, 'Belgeler yüklenemedi')
        setUploadError(uploadMessage)
        setToasts((prev) => [
          {
            id: `upload-error:${Date.now()}`,
            kind: UPLOAD_ERROR_TOAST_KIND,
            title: 'Yükleme başarısız',
            subtitle: uploadMessage,
            ttlMs: 6500,
          },
          ...prev.filter((x) => x?.kind !== UPLOAD_ERROR_TOAST_KIND),
        ])
      } finally {
        setUploading(false)
      }
    },
    [authFetch, chatId, request, refreshChats, navigate, showCreditBanner],
  )

  const detachDocument = useCallback(
    async (documentId) => {
      if (!chatId || !documentId) return
      try {
        await request('/v1/documents/detach', {
          method: 'POST',
          body: { chat_id: chatId, document_id: documentId },
        })
        setDocs((prev) => prev.filter((d) => Number(d.document_id) !== Number(documentId)))
      } catch (err) {
        setDocsError(humanizeApiError(err, 'Belge kaldirilamadi'))
      }
    },
    [chatId, request],
  )

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed((prev) => {
      const next = !prev
      // If user is opening the sidebar while the panel is wide, respect that choice.
      if (prev === true && next === false) {
        setSuppressSidebarAutoClose(true)
      }
      return next
    })
  }, [])

  const userLabel = useMemo(() => {
    const raw = String(user?.full_name || '').trim()
    if (raw) {
      // Basic title-case for TR names; keep it simple (split on whitespace)
      return raw
        .split(/\s+/)
        .filter(Boolean)
        .map((w) => w.charAt(0).toLocaleUpperCase('tr-TR') + w.slice(1).toLocaleLowerCase('tr-TR'))
        .join(' ')
    }
    return user?.username || user?.email || (user?.user_id ? `User ${user.user_id}` : 'User')
  }, [user?.email, user?.full_name, user?.user_id, user?.username])

  const rightPanelOpen = ictihatPanelOpen || petitionPanelOpen || generatedDocPanelOpen
  const { hasUrgent: hasUrgentDeadline } = useUpcomingDeadline({ windowHours: 36 })
  return (
    <SidebarProvider
      open={!sidebarCollapsed}
      onOpenChange={(v) => setSidebarCollapsed(!v)}
      mobileBreakpoint={MOBILE_SIDEBAR_BREAKPOINT}
      className="flex h-[100dvh] overflow-hidden"
    >
      <ChatSidebar
        chats={chats}
        selectedChatId={chatId}
        loading={loadingChats}
        error={chatListError}
        onSelectChat={onSelectChat}
        onDeleteChat={onDeleteChat}
        onNewChat={onNewChat}
        docs={docs}
        docsLoading={docsLoading}
        docsError={docsError}
        uploading={uploading}
        uploadError={uploadError}
        uploadAccept={UPLOAD_ACCEPT}
        onUploadDocuments={uploadDocuments}
        onDetachDocument={detachDocument}
        generatedDocs={generatedDocs}
        generatedDocsLoading={generatedDocsLoading}
        generatedDocsError={generatedDocsError}
        onOpenGeneratedDocPreview={openGeneratedDocPreview}
        onDownloadGeneratedDoc={downloadGeneratedDoc}
        onDownloadGeneratedDocPdf={downloadGeneratedDocPdf}
        onDownloadGeneratedDocUdf={downloadGeneratedDocUdf}
        onDeleteGeneratedDoc={deleteGeneratedDoc}
        downloadingGeneratedDocId={downloadingGeneratedDocId}
        downloadingGeneratedDocPdfId={downloadingGeneratedDocPdfId}
        downloadingGeneratedDocUdfId={downloadingGeneratedDocUdfId}
        deletingGeneratedDocId={deletingGeneratedDocId}
        petitions={petitions}
        petitionsLoading={petitionsLoading}
        petitionsError={petitionsError}
        onRefreshPetitions={refreshPetitions}
        onOpenPetitionPreview={openPetitionPreview}
        onDeletePetition={deletePetition}
        onDownloadPetitionDocx={downloadPetitionDocx}
        onDownloadPetitionPdf={downloadPetitionPdf}
        onDownloadPetitionUdf={downloadPetitionUdf}
        downloadingPetitionKey={downloadingPetitionKey}
        deletingPetitionId={deletingPetitionId}
        hasChat={Boolean(chatId)}
        user={user}
        userLabel={userLabel}
        onOpenSupport={() => setSupportModalOpen(true)}
        onOpenSettings={() => openSettings('account')}
        onLogout={logout}
      />
      <SidebarInset>
        <SiteHeader
          isSidebarCollapsed={sidebarCollapsed}
          onOpenSidebar={toggleSidebar}
          isPanelOpen={rightPanelOpen}
        />
        {!rightSidebarOpen && !rightPanelOpen && (
          <div className="app-safe-top-fab fixed right-4 z-[90]">
            <div className="relative">
              <Button
                className="h-11 w-11 rounded-full border border-border/80 bg-background/92 text-foreground shadow-lg backdrop-blur-md hover:bg-muted"
                variant="outline"
                size="icon"
                onClick={() => setRightSidebarOpen(true)}
                aria-label={hasUrgentDeadline ? 'Takvimi aç (yaklaşan etkinlik var)' : 'Takvimi aç'}
                title={hasUrgentDeadline ? 'Takvimi aç — 36 saat içinde etkinlik var' : 'Takvimi aç'}
              >
                <CalendarIcon className="size-5" />
              </Button>
              {hasUrgentDeadline && (
                <span
                  className="pointer-events-none absolute top-1 right-1 inline-flex h-2.5 w-2.5 rounded-full bg-red-500 ring-2 ring-background"
                  aria-hidden="true"
                />
              )}
            </div>
          </div>
        )}
        <div className="flex flex-1 overflow-hidden relative main">
          <div
            className={`chat-layout w-full ${rightPanelOpen ? 'has-right' : ''}`}
            style={rightPanelOpen ? { '--ictihat-panel-width': `${ictihatPanelWidth}px`, '--right-panel-width': `${ictihatPanelWidth}px` } : undefined}
          >
            <div className="chat-main-column">
              <ChatView
                chatId={chatId}
                onResolvedChatId={onResolvedChatId}
                onUnavailableChat={handleUnavailableChat}
                onAfterSend={refreshSidebarUser}
                onUploadDocuments={uploadDocuments}
                hasChat={Boolean(chatId)}
                uploading={uploading}
                uploadAccept={UPLOAD_ACCEPT}
                preparing={preparing}
                onOpenIctihat={openIctihatPanel}
                onOpenIctihatSearch={openIctihatSearchRecommendation}
                onShowAiIctihatHint={showAiIctihatHintToast}
                onCreditIssue={showCreditBanner}
                creditBanner={creditBanner}
                 onOpenSettings={() => openSettings('payment')}
                draftChatKey={draftChatKey}
                featureHint={featureHint}
                onDismissHint={() => setFeatureHint(null)}
                pendingSelectedIctihats={pendingSelectedIctihats}
                onConsumePendingSelectedIctihats={() => setPendingSelectedIctihats([])}
                pendingSelectedPetitionContexts={pendingSelectedPetitionContexts}
                onConsumePendingSelectedPetitionContexts={() => setPendingSelectedPetitionContexts([])}
              />
            </div>
            {ictihatPanelOpen ? (
              <>
                {isMobileViewport ? (
                  <button className="ictihat-panel-backdrop" type="button" aria-label="İçtihat panelini kapat" onClick={closeIctihatPanel} />
                ) : null}
                <aside className="ictihat-panel" aria-label="İçtihatlar">
                  <div
                    className="ictihat-panel-resizer"
                    role="separator"
                    aria-orientation="vertical"
                    aria-label="İçtihat paneli genişliği"
                    tabIndex={0}
                    onPointerDown={startResize}
                  />
                  <div className="ictihat-panel-header">
                    <div className="ictihat-panel-title">İçtihat Metni</div>
                    <button
                      className="ictihat-panel-close"
                      type="button"
                      onClick={closeIctihatPanel}
                      aria-label="İçtihatları kapat"
                      title="Kapat"
                    >
                      ×
                    </button>
                  </div>
                  <div className="ictihat-panel-body">
                    {!ictihatPanelItem ? <div className="muted small">Seçiniz.</div> : null}
                    {ictihatPanelItem ? (
                      <div className="ictihat-panel-meta">
                        <div className="ictihat-panel-citation">{formatIctihatCitation(ictihatPanelItem)}</div>
                      </div>
                    ) : null}
                    {ictihatPanelLoading ? <div className="muted small">Yükleniyor...</div> : null}
                    {ictihatPanelError ? <div className="error small">{ictihatPanelError}</div> : null}
                    {ictihatPanelText ? (
                      <pre ref={ictihatTextRef} className="ictihat-text">
                        {renderHighlightedText(ictihatPanelText, highlightRanges)}
                      </pre>
                    ) : null}
                  </div>
                </aside>
              </>
            ) : null}
            {petitionPanelOpen ? (
              <>
                {isMobileViewport ? (
                  <button className="petition-panel-backdrop" type="button" aria-label="Dilekçe panelini kapat" onClick={closePetitionPanel} />
                ) : null}
                <PetitionPreviewPanel
                  petition={petitionPanelData}
                  loading={petitionPanelLoading}
                  error={petitionPanelError}
                  saving={Boolean(petitionPanelSavingFieldPath)}
                  scrollTop={petitionPanelScrollTop}
                  onScrollTopChange={setPetitionPanelScrollTop}
                  onClose={closePetitionPanel}
                  onStartResize={startResize}
                  onSaveAll={patchPetitionFields}
                  onInjectContext={injectPetitionContextToChat}
                  downloadingDocx={Boolean(
                    downloadingPetitionKey
                    && petitionPanelData?.petition_id
                    && petitionPanelData?.version?.version_id
                    && downloadingPetitionKey === `docx:${petitionPanelData.petition_id}:${petitionPanelData.version.version_id}`,
                  )}
                  downloadingPdf={Boolean(
                    downloadingPetitionKey
                    && petitionPanelData?.petition_id
                    && petitionPanelData?.version?.version_id
                    && downloadingPetitionKey === `pdf:${petitionPanelData.petition_id}:${petitionPanelData.version.version_id}`,
                  )}
                  downloadingUdf={Boolean(
                    downloadingPetitionKey
                    && petitionPanelData?.petition_id
                    && petitionPanelData?.version?.version_id
                    && downloadingPetitionKey === `udf:${petitionPanelData.petition_id}:${petitionPanelData.version.version_id}`,
                  )}
                  onDownloadDocx={() => downloadPetitionDocx({
                    petitionId: petitionPanelData?.petition_id,
                    versionId: petitionPanelData?.version?.version_id,
                    fallbackFilename: petitionPanelData?.version?.docx_filename,
                  })}
                  onDownloadPdf={() => downloadPetitionPdf({
                    petitionId: petitionPanelData?.petition_id,
                    versionId: petitionPanelData?.version?.version_id,
                    fallbackFilename: petitionPanelData?.version?.docx_filename
                      ? String(petitionPanelData.version.docx_filename).replace(/\.docx$/i, '.pdf')
                      : undefined,
                  })}
                  onDownloadUdf={() => downloadPetitionUdf({
                    petitionId: petitionPanelData?.petition_id,
                    versionId: petitionPanelData?.version?.version_id,
                    fallbackFilename: petitionPanelData?.version?.docx_filename
                      ? String(petitionPanelData.version.docx_filename).replace(/\.docx$/i, '.udf')
                      : undefined,
                  })}
                />
              </>
            ) : null}
            {generatedDocPanelOpen ? (
              <>
                {isMobileViewport ? (
                  <button className="petition-panel-backdrop" type="button" aria-label="Doküman panelini kapat" onClick={closeGeneratedDocPanel} />
                ) : null}
                <GeneratedDocumentPreviewPanel
                  document={generatedDocPanelData}
                  loading={generatedDocPanelLoading}
                  error={generatedDocPanelError}
                  downloadingDocx={Boolean(downloadingGeneratedDocId && Number(generatedDocPanelData?.generated_document_id) === Number(downloadingGeneratedDocId))}
                  downloadingPdf={Boolean(downloadingGeneratedDocPdfId && Number(generatedDocPanelData?.generated_document_id) === Number(downloadingGeneratedDocPdfId))}
                  downloadingUdf={Boolean(downloadingGeneratedDocUdfId && Number(generatedDocPanelData?.generated_document_id) === Number(downloadingGeneratedDocUdfId))}
                  onClose={closeGeneratedDocPanel}
                  onStartResize={startResize}
                  onDownloadDocx={() => downloadGeneratedDoc({
                    generatedDocumentId: generatedDocPanelData?.generated_document_id,
                    fallbackFilename: generatedDocPanelData?.filename,
                  })}
                  onDownloadPdf={() => downloadGeneratedDocPdf({
                    generatedDocumentId: generatedDocPanelData?.generated_document_id,
                    fallbackFilename: generatedDocPanelData?.filename,
                  })}
                  onDownloadUdf={() => downloadGeneratedDocUdf({
                    generatedDocumentId: generatedDocPanelData?.generated_document_id,
                    fallbackFilename: generatedDocPanelData?.filename,
                  })}
                />
              </>
            ) : null}
          </div>
          <ToastHost
            toasts={toasts}
            onRequestClose={dismissToast}
          />
          <SupportRequestModal
            isOpen={supportModalOpen}
            onClose={() => setSupportModalOpen(false)}
            onSubmit={submitSupportRequest}
          />
        </div>
      </SidebarInset>
      <SidebarProvider 
        storageKey="right_sidebar_state" 
        open={rightSidebarOpen} 
        onOpenChange={setRightSidebarOpen}
        className="flex h-full w-auto"
        style={{ "--sidebar-width": "min(21rem, 95vw)" }}
      >
        <RightCalendarSidebar />
      </SidebarProvider>
    </SidebarProvider>
  )
}
