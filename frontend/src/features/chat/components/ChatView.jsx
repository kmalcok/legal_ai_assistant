import { Children, isValidElement, useEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useAuth } from '../../auth/useAuth.js'
import { Paperclip, ArrowUp, Copy, Check } from 'lucide-react'
import { getApiReason, humanizeApiError, isInsufficientCreditsError } from '../../../shared/api/contracts.js'
import {
  PromptInput,
  PromptInputTextarea,
  PromptInputActions,
  PromptInputAction,
} from '../../../components/prompt-kit/prompt-input.jsx'
import { Message, MessageContent } from '../../../components/prompt-kit/message.jsx'
import { Loader } from '../../../components/prompt-kit/loader.jsx'
import { CreditBanner } from '../../../shared/components/CreditBanner.jsx'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { buildCourtLabel, stripKurumPrefixFromDaire } from '../../ictihat/utils/courtLabel.js'
import yargucuLogo from '../../../logopack/yargucu-logo-siyah.svg'
import { FeatureHintBanner } from './FeatureHintBanner.jsx'

const EMPTY_CHAT_SUGGESTIONS = [
  {
    label: 'Dilekçe',
    title: 'Taslak metni hızlıca kur',
    description: 'Talep, olay ve hedefinizi yazın; iskeleti doğru sırayla hazırlayayım.',
    prompt: 'Tahliye ihtarnamesi için kısa ve resmi bir taslak hazırla; kiracı iki aydır ödeme yapmıyor.',
  },
  {
    label: 'İçtihat',
    title: 'Emsal kararları karşılaştır',
    description: 'Uyuşmazlığı yazın; ilgili Yargıtay kararlarını özetleyip ayırayım.',
    prompt: 'Haksız fesihte işçilik alacaklarına ilişkin güncel Yargıtay kararlarını karşılaştırmalı özetle.',
    action: 'show-ictihat-hint',
  },
  {
    label: 'Analiz',
    title: 'Madde bazlı riskleri çıkar',
    description: 'Sözleşme veya olay örgüsü üzerinden güçlü ve zayıf noktaları netleştireyim.',
    prompt: 'TBK kapsamında kira sözleşmesinin fesih şartlarını madde bazlı ve pratik riskleriyle incele.',
  },
  {
    label: 'Süreç',
    title: 'Başvuru yolunu planla',
    description: 'Süre, görevli merci ve gerekli adımları uygulanabilir sırayla yazayım.',
    prompt: "İİK'da itirazın kaldırılması yolunu süre, şartlar ve içtihat bağlantısıyla açıkla.",
  },
]

function nowIso() {
  return new Date().toISOString()
}

function extractAtifBlocks(markdownText) {
  const s = String(markdownText || '')
  const re = /```atif\s*([\s\S]*?)```/gi
  const out = []
  let m
  while ((m = re.exec(s)) !== null) {
    const body = String(m[1] || '').trim()
    if (body) out.push(body)
    if (out.length >= 20) break
  }
  return out
}

export function ChatView({
  chatId,
  onResolvedChatId,
  onUnavailableChat,
  onAfterSend,
  onUploadDocuments,
  uploading,
  uploadAccept,
  preparing,
  onOpenIctihat,
  onOpenIctihatSearch,
  onCreditIssue,
  creditBanner,
  onOpenSettings,
  onShowAiIctihatHint,
  featureHint,
  onDismissHint,
  draftChatKey,
  pendingSelectedIctihats,
  onConsumePendingSelectedIctihats,
  pendingSelectedPetitionContexts,
  onConsumePendingSelectedPetitionContexts,
}) {
  const { request, stream } = useAuth()

  const [messages, setMessages] = useState([])
  const [ictihatSortByMsgId, setIctihatSortByMsgId] = useState({}) // { [msgId]: 'relevance'|'date' }
  const [copiedMsgId, setCopiedMsgId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [composerIctihats, setComposerIctihats] = useState([])
  const [composerPetitionContexts, setComposerPetitionContexts] = useState([])
  const [expandedPetitionContextKeys, setExpandedPetitionContextKeys] = useState({})
  const bottomRef = useRef(null)
  const streamTextRef = useRef('')
  const fileInputRef = useRef(null)
  const composerRef = useRef(null)
  const [isDragging, setDragging] = useState(false)
  const scrollRef = useRef(null)
  const userScrolledUp = useRef(false)
  const isAutoScrolling = useRef(false)
  const lastAutoScrollTs = useRef(0)
  const lastScrollTop = useRef(0)

  const hasChat = useMemo(() => Number.isFinite(chatId) && chatId > 0, [chatId])
  const activeChatIdRef = useRef(chatId)
  const skipNextHistoryLoadRef = useRef(false)
  const visibleFeatureRecommendationMessageId = useMemo(() => {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      const message = messages[index]
      if (message?.role !== 'assistant') continue
      const recommendationItem = Array.isArray(message?.context_items)
        ? message.context_items.find((entry) => String(entry?.kind || '').trim() === 'feature_recommendation')
        : null
      const recommendation =
        recommendationItem?.payload && typeof recommendationItem.payload === 'object' ? recommendationItem.payload : null
      if (recommendation?.feature === 'ictihat_search') return message.id
    }
    return null
  }, [messages])

  const pendingKey = useMemo(() => {
    if (!Array.isArray(pendingSelectedIctihats) || !pendingSelectedIctihats.length) return ''
    return pendingSelectedIctihats
      .map((x) => Number(x?.document_id))
      .filter((x) => Number.isFinite(x) && x > 0)
      .slice(0, 80)
      .join(',')
  }, [pendingSelectedIctihats])

  const pendingPetitionKey = useMemo(() => {
    if (!Array.isArray(pendingSelectedPetitionContexts) || !pendingSelectedPetitionContexts.length) return ''
    return pendingSelectedPetitionContexts
      .map((x) => [x?.petition_id, x?.version_id, x?.field_path, x?.selected_text].map((y) => String(y || '')).join(':'))
      .slice(0, 80)
      .join('|')
  }, [pendingSelectedPetitionContexts])

  useEffect(() => {
    if (!pendingKey) return
    const incoming = Array.isArray(pendingSelectedIctihats) ? pendingSelectedIctihats.filter(Boolean) : []
    if (!incoming.length) return
    setComposerIctihats(incoming)
    onConsumePendingSelectedIctihats?.()
  }, [onConsumePendingSelectedIctihats, pendingKey, pendingSelectedIctihats])

  useEffect(() => {
    if (!pendingPetitionKey) return
    const incoming = Array.isArray(pendingSelectedPetitionContexts)
      ? pendingSelectedPetitionContexts.filter(Boolean)
      : []
    if (!incoming.length) return
    setComposerPetitionContexts((prev) => {
      const merged = Array.isArray(prev) ? [...prev] : []
      const seen = new Set(
        merged.map((item) =>
          [item?.petition_id, item?.version_id, item?.field_path, item?.selected_text].map((v) => String(v || '')).join(':'),
        ),
      )
      for (const item of incoming) {
        const key = [item?.petition_id, item?.version_id, item?.field_path, item?.selected_text]
          .map((v) => String(v || ''))
          .join(':')
        if (seen.has(key)) continue
        seen.add(key)
        merged.push(item)
      }
      return merged
    })
    onConsumePendingSelectedPetitionContexts?.()
  }, [onConsumePendingSelectedPetitionContexts, pendingPetitionKey, pendingSelectedPetitionContexts])

  useEffect(() => {
    activeChatIdRef.current = chatId
  }, [chatId])

  useEffect(() => {
    // When user explicitly starts a new (blank) chat, clear local UI state even if route stays "/".
    if (hasChat) return
    if (!draftChatKey) return
    setMessages([])
    setIctihatSortByMsgId({})
    setError('')
    setInput('')
    setComposerIctihats([])
    setComposerPetitionContexts([])
    setExpandedPetitionContextKeys({})
    // keep sending state as-is; stream may still be in flight from previous view
  }, [draftChatKey, hasChat])

  const smoothScrollToBottom = ({ behavior = 'smooth', force = false } = {}) => {
    const el = scrollRef.current
    if (!el) return

    // Lock: if user scrolled up (beyond threshold), stop auto-scroll completely
    if (!force && userScrolledUp.current) return

    const now = performance.now()
    // ~30fps throttle while streaming/pending
    if (sending && now - lastAutoScrollTs.current < 33) return

    const distance = el.scrollHeight - el.scrollTop - el.clientHeight
    // already at bottom
    if (distance <= 2) return

    lastAutoScrollTs.current = now
    const targetScroll = el.scrollHeight - el.clientHeight

    isAutoScrolling.current = true
    try {
      if (distance < 200) {
        // small increments during streaming: jump to keep it stable
        el.scrollTop = targetScroll
      } else {
        el.scrollTo({ top: targetScroll, behavior })
      }
      lastScrollTop.current = targetScroll
    } finally {
      requestAnimationFrame(() => {
        isAutoScrolling.current = false
      })
    }
  }

  useEffect(() => {
    // Auto-scroll trigger on any chat content update (throttled inside)
    requestAnimationFrame(() => smoothScrollToBottom({ behavior: 'smooth', force: false }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages])

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return

    const onScroll = () => {
      // Ignore scroll events caused by our own auto-scroll
      if (isAutoScrolling.current) return

      const prevTop = lastScrollTop.current
      const curTop = el.scrollTop
      lastScrollTop.current = curTop

      const distance = el.scrollHeight - curTop - el.clientHeight
      const isNearBottom = distance < 96
      const movedUpBy = prevTop - curTop
      const scrolledUp = movedUpBy > 24

      // On mobile, browser chrome / keyboard / layout shifts can move scrollTop a few px.
      // Only lock auto-scroll when the user moves meaningfully away from the bottom.
      if (scrolledUp && !isNearBottom) {
        userScrolledUp.current = true
        return
      }

      // Only unlock when the user scrolls back down into the near-bottom zone.
      if (isNearBottom) {
        userScrolledUp.current = false
      }
    }

    el.addEventListener('scroll', onScroll, { passive: true })
    // initialize
    lastScrollTop.current = el.scrollTop
    onScroll()
    return () => el.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    const scroller = scrollRef.current
    if (!scroller || typeof ResizeObserver === 'undefined') return undefined

    let frameOne = 0
    let frameTwo = 0
    const scheduleFollowBottom = () => {
      if (userScrolledUp.current) return
      cancelAnimationFrame(frameOne)
      cancelAnimationFrame(frameTwo)
      frameOne = requestAnimationFrame(() => {
        frameTwo = requestAnimationFrame(() => {
          smoothScrollToBottom({ behavior: sending ? 'auto' : 'smooth', force: false })
        })
      })
    }

    const observer = new ResizeObserver(() => {
      scheduleFollowBottom()
    })

    observer.observe(scroller)
    if (composerRef.current) observer.observe(composerRef.current)

    return () => {
      cancelAnimationFrame(frameOne)
      cancelAnimationFrame(frameTwo)
      observer.disconnect()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sending])

  useEffect(() => {
    let cancelled = false
    async function load() {
      setError('')
      if (!hasChat) {
        setMessages([])
        return
      }
      // When we create a chat on first message, ChatPage navigates immediately to /chat/:id.
      // That would normally trigger a history fetch that can overwrite our optimistic, in-flight stream UI.
      // Skip exactly once in that scenario; we'll sync after the stream completes.
      if (skipNextHistoryLoadRef.current) {
        skipNextHistoryLoadRef.current = false
        return
      }
      setLoading(true)
      try {
        const data = await request(`/v1/chat/history/${chatId}`, { method: 'GET' })
        if (!cancelled) {
          setMessages(Array.isArray(data.history) ? data.history : [])
          setExpandedPetitionContextKeys({})
        }
      } catch (err) {
        if (getApiReason(err) === 'not_found') {
          if (!cancelled) onUnavailableChat?.()
          return
        }
        if (!cancelled) setError(err?.message || 'Sohbet gecmisi yuklenemedi')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [chatId, hasChat, onUnavailableChat, request])

  const normalizeMarkdownText = (text) => String(text || '').replace(/\r\n/g, '\n')

  const formatComposerIctihatChip = (it) => {
    const emsal = String(it?.emsal_no || '').trim()
    const karar = String(it?.karar_no || '').trim()
    if (emsal && karar) return `E: ${emsal} · K: ${karar}`
    if (emsal) return `E: ${emsal}`
    if (karar) return `K: ${karar}`
    const did = Number(it?.document_id)
    return Number.isFinite(did) ? `#${did}` : 'İçtihat'
  }

  const formatComposerPetitionChip = (item) => {
    const section = String(item?.section_title || '').trim()
    const text = String(item?.selected_text || '').trim().replace(/\s+/g, ' ')
    if (section && text) return `${section}: ${text.slice(0, 84)}${text.length > 84 ? '...' : ''}`
    if (section) return section
    if (text) return text.slice(0, 84) + (text.length > 84 ? '...' : '')
    const petitionId = Number(item?.petition_id)
    return Number.isFinite(petitionId) ? `Dilekçe #${petitionId}` : 'Dilekçe içeriği'
  }

  const formatInjectedPetitionContextLabel = (item) => {
    const section = String(item?.section_title || '').trim()
    const docType = String(item?.document_type || '').trim()
    if (section && docType) return `${docType} · ${section}`
    if (section) return section
    if (docType) return docType
    const petitionId = Number(item?.petition_id)
    return Number.isFinite(petitionId) ? `Dilekçe #${petitionId}` : 'Dilekçe bağlamı'
  }

  const formatInjectedPetitionContextText = (item) => {
    const text = String(item?.resolved_text || item?.selected_text || '').trim().replace(/\s+/g, ' ')
    if (!text) return ''
    return text
  }

  const buildPetitionContextKey = (item, idx = 0) =>
    [item?.petition_id, item?.version_id, item?.field_path, item?.selected_text, item?.resolved_text]
      .map((v) => String(v || ''))
      .join(':') || `petition-${idx}`

  const formatIctihatCitation = (it) => {
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
    else if (it.emsal_no) parts.push(`${String(it.emsal_no).trim()} E.`)
    if (kY != null && kS != null) parts.push(`${kY}/${kS} K.`)
    else if (it.karar_no) parts.push(`${String(it.karar_no).trim()} K.`)
    if (tarih) parts.push(String(tarih))
    const base = parts.filter(Boolean).join(' › ').trim()
    return base || 'Karar'
  }

  const getIctihatExcerpt = (it) => {
    if (!it || typeof it !== 'object') return ''
    const raw =
      it.excerpt ??
      it.snippet ??
      it.ictihat_text ??
      it.text
    const s = typeof raw === 'string' ? raw.trim() : ''
    return s
  }

  const getMessageIctihatItems = (m) => {
    if (!m || typeof m !== 'object') return []
    if (Array.isArray(m.ictihat_items) && m.ictihat_items.length) return m.ictihat_items
    if (Array.isArray(m.ictihat_document_ids) && m.ictihat_document_ids.length) {
      return m.ictihat_document_ids
        .map((did) => {
          try {
            const n = Number(did)
            if (!Number.isFinite(n)) return null
            return { document_id: n }
          } catch {
            return null
          }
        })
        .filter(Boolean)
    }
    return []
  }

  const getMessageContextItems = (m) => {
    if (!m || typeof m !== 'object' || !Array.isArray(m.context_items)) return []
    return m.context_items
      .filter((item) => item && typeof item === 'object')
      .slice()
      .sort((left, right) => {
        const leftOrder = Number(left?.sort_order)
        const rightOrder = Number(right?.sort_order)
        const safeLeft = Number.isFinite(leftOrder) ? leftOrder : Number.MAX_SAFE_INTEGER
        const safeRight = Number.isFinite(rightOrder) ? rightOrder : Number.MAX_SAFE_INTEGER
        return safeLeft - safeRight
      })
  }

  const getMessageInjectedIctihatItems = (m) =>
    getMessageContextItems(m)
      .filter((item) => String(item?.kind || '').trim() === 'injected_ictihat')
      .map((item) => (item?.payload && typeof item.payload === 'object' ? item.payload : null))
      .filter(Boolean)

  const getMessageInjectedPetitionContexts = (m) =>
    getMessageContextItems(m)
      .filter((item) => String(item?.kind || '').trim() === 'injected_petition_context')
      .map((item) => (item?.payload && typeof item.payload === 'object' ? item.payload : null))
      .filter(Boolean)

  function getMessageFeatureRecommendation(m) {
    const item = getMessageContextItems(m).find((entry) => String(entry?.kind || '').trim() === 'feature_recommendation')
    return item?.payload && typeof item.payload === 'object' ? item.payload : null
  }

  const parseIctihatDecisionDateMs = (it) => {
    if (!it || typeof it !== 'object') return null
    const raw = it.karar_tarihi ?? it.kararTarihi ?? it.karar?.tarih
    if (!raw) return null
    const d = new Date(String(raw))
    const ms = d.getTime()
    return Number.isFinite(ms) ? ms : null
  }

  const formatIctihatDecisionDate = (it) => {
    const ms = parseIctihatDecisionDateMs(it)
    if (ms == null) return ''
    try {
      const d = new Date(ms)
      const dd = String(d.getDate()).padStart(2, '0')
      const mm = String(d.getMonth() + 1).padStart(2, '0')
      const yy = String(d.getFullYear())
      return `${dd}.${mm}.${yy}`
    } catch {
      return ''
    }
  }

  const sortIctihatItems = (items, mode) => {
    if (!Array.isArray(items) || items.length < 2) return items || []
    if (mode !== 'date') return items
    const keyed = items.map((it, idx) => ({ it, idx, ms: parseIctihatDecisionDateMs(it) }))
    keyed.sort((a, b) => {
      const am = a.ms == null ? -Infinity : a.ms
      const bm = b.ms == null ? -Infinity : b.ms
      if (bm !== am) return bm - am // newest first
      return a.idx - b.idx // stable
    })
    return keyed.map((x) => x.it)
  }

  const parseKunyeJson = (raw) => {
    const s = String(raw || '').trim()
    if (!s) return null
    try {
      const obj = JSON.parse(s)
      return obj && typeof obj === 'object' ? obj : null
    } catch {
      return null
    }
  }

  const toFiniteIntOrNull = (v) => {
    const n = Number(v)
    return Number.isFinite(n) ? n : null
  }

  const buildKunyeLabel = (k, fallbackRaw) => {
    if (!k || typeof k !== 'object') return String(fallbackRaw || '').trim() || 'Künye'
    const daire = String(k?.daire ?? k?.yargitay_daire ?? '').trim()
    const kurum = String(k?.kurum || k?.court || '').trim()
    const court = buildCourtLabel({ kurum, daire })
    const ey = k?.esas_yil
    const es = k?.esas_sira
    const ky = k?.karar_yil
    const ks = k?.karar_sira
    const tarih = String(k?.karar_tarihi || '').trim()
    const parts = []
    if (court) parts.push(court)
    if (ey != null && es != null) parts.push(`${ey}/${es} E.`)
    if (ky != null && ks != null) parts.push(`${ky}/${ks} K.`)
    if (tarih) parts.push(tarih)
    return parts.filter(Boolean).join(' › ').trim() || 'Künye'
  }

  const buildKunyeFilters = (k, daireOverride) => {
    const filters = {}
    const daireLabelOrRaw = String(daireOverride ?? k?.daire_label ?? k?.daire ?? '').trim()
    const kurum = String(k?.kurum || k?.court || '').trim()
    const daire = stripKurumPrefixFromDaire(daireLabelOrRaw, kurum)
    const ey = toFiniteIntOrNull(k?.esas_yil)
    const es = toFiniteIntOrNull(k?.esas_sira)
    const ky = toFiniteIntOrNull(k?.karar_yil)
    const ks = toFiniteIntOrNull(k?.karar_sira)
    if (kurum) filters.kurum = kurum
    if (daire) filters.daire = daire
    if (ey != null) filters.esas_yil = ey
    if (es != null) filters.esas_sira = es
    if (ky != null) filters.karar_yil = ky
    if (ks != null) filters.karar_sira = ks
    return filters
  }

  const buildKunyeQueryCandidates = (k) => {
    const ey = toFiniteIntOrNull(k?.esas_yil)
    const es = toFiniteIntOrNull(k?.esas_sira)
    const ky = toFiniteIntOrNull(k?.karar_yil)
    const ks = toFiniteIntOrNull(k?.karar_sira)
    const out = []
    if (ey != null && es != null && ky != null && ks != null) {
      out.push(`E.${ey}/${es} K.${ky}/${ks}`)
      out.push(`${ey}/${es} ${ky}/${ks}`)
    }
    return out
  }

  const normalizeSearchDocToPanelItem = (doc, fallbackKunye) => {
    const d = doc && typeof doc === 'object' ? doc : {}
    const f = fallbackKunye && typeof fallbackKunye === 'object' ? fallbackKunye : {}
    const document_id = toFiniteIntOrNull(d.document_id) ?? toFiniteIntOrNull(d.documentId)
    const kurum = String(d.kurum || f.kurum || '').trim() || undefined
    const daire = String(d.daire || d.yargitay_daire || f.daire || f.yargitay_daire || '').trim()
    const daire_label = String(d.daire_label || f.daire_label || '').trim() || undefined
    const esas_yil = toFiniteIntOrNull(d.esas_yil ?? d.esas?.yil ?? f.esas_yil)
    const esas_sira = toFiniteIntOrNull(d.esas_sira ?? d.esas?.sira ?? f.esas_sira)
    const karar_yil = toFiniteIntOrNull(d.karar_yil ?? d.karar?.yil ?? f.karar_yil)
    const karar_sira = toFiniteIntOrNull(d.karar_sira ?? d.karar?.sira ?? f.karar_sira)
    const karar_tarihi = String(d.karar_tarihi ?? d.karar?.tarih ?? f.karar_tarihi ?? '').trim() || undefined
    return {
      document_id,
      kurum,
      daire,
      daire_label,
      // backward-compatible alias: older UI/DB may still use `yargitay_daire`
      yargitay_daire: daire,
      esas_yil,
      esas_sira,
      karar_yil,
      karar_sira,
      karar_tarihi,
      citation: String(d.citation || '').trim() || undefined,
    }
  }

  const MarkdownLink = ({ href, children, ...props }) => {
    const safeHref = typeof href === 'string' ? href : ''
    const isExternal = /^https?:\/\//i.test(safeHref)
    return (
      <a
        href={safeHref}
        target={isExternal ? '_blank' : undefined}
        rel={isExternal ? 'noopener noreferrer' : undefined}
        {...props}
      >
        {children}
      </a>
    )
  }

  const MarkdownPre = ({ children, ...props }) => {
    const arr = Children.toArray(children)
    // react-markdown may include "\n" nodes around the rendered child.
    const meaningful = arr.filter((n) => {
      if (typeof n === 'string') return n.trim().length > 0
      return Boolean(n)
    })

    // For fenced blocks like ```atif``` / ```kunye```, react-markdown normally renders:
    // <pre><code class="language-kunye">...</code></pre>
    // But because we override `code` and return custom elements,
    // the <pre> may end up containing the button directly.
    // Remove the gray <pre> box for legal citation blocks so they do not look like code.
    if (meaningful.length === 1) {
      const only = meaningful[0]
      if (isValidElement(only)) {
        const cn = String(only.props?.className || '')
        // Case 1: default code node still present (no override)
        if (cn.includes('language-kunye') || cn.includes('language-atif')) {
          return <div className="md-pre-unwrap">{only}</div>
        }
        // Case 2: our `code` override returned the actual breadcrumb button
        if (cn.includes('kunye-breadcrumb') || cn.includes('atif-inline')) {
          return <div className="md-pre-unwrap">{only}</div>
        }
      }
    }

    return <pre {...props}>{children}</pre>
  }

  const MarkdownCode = ({ inline, className, children, __kunyeContext }) => {
    const raw = (Array.isArray(children) ? children.join('') : String(children ?? '')).replace(/\n$/, '')
    const lang = typeof className === 'string' ? (className.match(/language-([^\s]+)/)?.[1] || '') : ''

    if (!inline && String(lang).toLowerCase() === 'atif') {
      return (
        <div className="atif-inline">
          {raw}
        </div>
      )
    }

    if (!inline && String(lang).toLowerCase() === 'kunye') {
      const k = parseKunyeJson(raw)
      const label = buildKunyeLabel(k, raw)

      const canOpen = Boolean(onOpenIctihat && k && typeof k === 'object')
      return (
        <button
          type="button"
          className="kunye-breadcrumb"
          disabled={!canOpen}
          title={canOpen ? 'İçtihadı aç' : 'Künye'}
          onClick={async () => {
            if (!canOpen) return
            try {
              // New backend format: if document_id is present, open directly.
              const directDocId = toFiniteIntOrNull(k?.document_id)
              if (directDocId != null && directDocId > 0) {
                const directItem = normalizeSearchDocToPanelItem({ ...(k || {}), document_id: directDocId }, k)
                await onOpenIctihat?.(directItem, {
                  atifBlocks: Array.isArray(__kunyeContext?.atifBlocks) ? __kunyeContext.atifBlocks : [],
                  messageId: __kunyeContext?.messageId,
                })
                return
              }

              const rawDaire = String(k?.daire || '').trim()
              const rawDaireStripped = stripKurumPrefixFromDaire(rawDaire, k?.kurum || k?.court || '')
              const daireCandidates = Array.from(
                new Set(
                  [rawDaireStripped, rawDaireStripped.replace(/^yargıtay\s+/i, ''), rawDaireStripped.replace(/^yargitay\s+/i, '')]
                    .map((x) => String(x || '').trim())
                    .filter(Boolean),
                ),
              )
              const queryCandidates = buildKunyeQueryCandidates(k)

              let foundDoc = null

              const combos = []
              for (const d of daireCandidates.slice(0, 2)) {
                const filters = buildKunyeFilters(k, d)
                combos.push({ query: null, filters })
                for (const q of queryCandidates.slice(0, 2)) combos.push({ query: q, filters })
              }
              for (const q of queryCandidates.slice(0, 1)) combos.push({ query: q, filters: null })

              for (const c of combos) {
                try {
                  const data = await request('/v1/ictihat/search', {
                    method: 'POST',
                    body: {
                      query: c.query || null,
                      filters: c.filters && Object.keys(c.filters).length ? c.filters : null,
                      top_k: 5,
                      mode: 'decisions',
                    },
                  })
                  const groups = Array.isArray(data?.groups) ? data.groups : []
                  const doc = groups.find((g) => g?.doc && g.doc.document_id != null)?.doc || null
                  if (doc) {
                    foundDoc = doc
                    break
                  }
                } catch (err) {
                  if (isInsufficientCreditsError(err)) onCreditIssue?.(err)
                  throw err
                }
              }

              const item = foundDoc ? normalizeSearchDocToPanelItem(foundDoc, k) : null
              if (!item?.document_id) return

              await onOpenIctihat?.(item, {
                atifBlocks: Array.isArray(__kunyeContext?.atifBlocks) ? __kunyeContext.atifBlocks : [],
                messageId: __kunyeContext?.messageId,
              })
            } catch {
              // ignore: keep UI quiet on small lookup failures
            }
          }}
        >
          {label}
        </button>
      )
    }

    if (inline) {
      return <code className={className}>{raw}</code>
    }

    return <code className={className}>{children}</code>
  }

  async function send() {
    const text = input.trim()
    if (!text || sending) return
    const injectedIctihatsSnapshot = composerIctihats.length ? composerIctihats : null
    const injectedPetitionContextsSnapshot = composerPetitionContexts.length ? composerPetitionContexts : null
    setInput('')
    setError('')

    const userTempId = `tmp-u-${Date.now()}`
    const asstTempId = `tmp-a-${Date.now()}`
    streamTextRef.current = ''
    const optimisticContextItems = [
      ...(Array.isArray(injectedIctihatsSnapshot)
        ? injectedIctihatsSnapshot.map((item, index) => ({
            kind: 'injected_ictihat',
            sort_order: index,
            payload: item,
          }))
        : []),
      ...(Array.isArray(injectedPetitionContextsSnapshot)
        ? injectedPetitionContextsSnapshot.map((item, index) => ({
            kind: 'injected_petition_context',
            sort_order: (Array.isArray(injectedIctihatsSnapshot) ? injectedIctihatsSnapshot.length : 0) + index,
            payload: {
              ...item,
              resolved_text: item?.selected_text || null,
            },
          }))
        : []),
    ]
    setMessages((prev) => [
      ...prev,
      {
        id: userTempId,
        role: 'user',
        message: text,
        reasoning: '',
        created_at: nowIso(),
        context_items: optimisticContextItems,
      },
    ])

    setSending(true)
    userScrolledUp.current = false
    // Clear pinned ictihat chips immediately after sending (keep a snapshot for request + error recovery).
    setComposerIctihats([])
    setComposerPetitionContexts([])
    setMessages((prev) => [
      ...prev,
      { id: asstTempId, role: 'assistant', message: '', reasoning: '', created_at: nowIso(), pending: true },
    ])

    let didComplete = false
    try {
      let targetChatId = hasChat ? chatId : null
      let didCreateChat = false

      if (!targetChatId) {
        const created = await request('/v1/chat/create', { method: 'POST', body: { title: null } })
        targetChatId = Number(created?.chat_id)
        if (!Number.isFinite(targetChatId) || targetChatId <= 0) throw new Error('Sohbet olusturulamadi')
        didCreateChat = true
        // Prevent immediate history load from wiping optimistic messages while streaming.
        skipNextHistoryLoadRef.current = true
        await onResolvedChatId?.(targetChatId)
      }

      const res = await stream('/v1/chat/stream', {
        method: 'POST',
        body: {
          chat_id: targetChatId,
          message: text,
          injected_ictihats: injectedIctihatsSnapshot,
          injected_petition_contexts: injectedPetitionContextsSnapshot,
        },
      })
      if (!res.ok) {
        let detail = ''
        let parsed = null
        try {
          detail = await res.text()
          parsed = detail ? JSON.parse(detail) : null
        } catch {
          parsed = null
        }
        const error = new Error(
          humanizeApiError(
            { status: res.status, data: parsed || detail },
            res.status === 402 ? 'Kredi bakiyesi yetersiz' : `Request failed (${res.status})`,
          ),
        )
        error.status = res.status
        error.data = parsed || detail
        throw error
      }
      if (!res.body) throw new Error('Streaming not supported by this browser/response')

      const reader = res.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''

      const applyDelta = (chunk) => {
        if (!chunk) return
        streamTextRef.current += chunk
        const nextText = streamTextRef.current
        setMessages((prev) => prev.map((m) => (m.id === asstTempId ? { ...m, message: nextText } : m)))
        // keep it feeling live, but respect scroll lock + throttle
        requestAnimationFrame(() => smoothScrollToBottom({ behavior: 'smooth', force: false }))
      }

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed) continue
          let evt
          try {
            evt = JSON.parse(trimmed)
          } catch {
            continue
          }

          if (evt?.type === 'text_delta') {
            applyDelta(String(evt.chunk || ''))
          } else if (evt?.type === 'done') {
            didComplete = true
            const resolvedId = Number(evt.chat_id)
            const ictihatItems = Array.isArray(evt?.ictihat_items) ? evt.ictihat_items : []
            const featureRecommendation =
              evt?.feature_recommendation && typeof evt.feature_recommendation === 'object' ? evt.feature_recommendation : null
            const streamedText = String(streamTextRef.current ?? '')
            const finalText = String(evt.final_text ?? streamedText)
            if (import.meta.env.DEV) {
              console.debug('[chat-stream:done]', {
                chatId: resolvedId || targetChatId,
                assistantMessageId: evt?.assistant_message_id ?? null,
                sameAsStream: finalText === streamedText,
                streamLength: streamedText.length,
                finalLength: finalText.length,
                streamTail: streamedText.slice(-240),
                finalTail: finalText.slice(-240),
              })
            }
            setMessages((prev) =>
              prev.map((m) =>
                m.id === asstTempId
                  ? {
                      ...m,
                      message: finalText,
                      reasoning: '',
                      pending: false,
                      context_items: featureRecommendation
                        ? [
                            ...((Array.isArray(m.context_items) ? m.context_items : []).filter(
                              (item) => String(item?.kind || '').trim() !== 'feature_recommendation',
                            )),
                            {
                              kind: 'feature_recommendation',
                              source: 'agent',
                              sort_order: 0,
                              payload: featureRecommendation,
                            },
                          ]
                        : m.context_items,
                      ictihat_items: ictihatItems,
                      server_message_id: evt?.assistant_message_id ?? null,
                    }
                  : m,
              ),
            )
            if (resolvedId && resolvedId !== targetChatId) {
              // Extremely defensive: if backend resolves to a different id, follow it.
              skipNextHistoryLoadRef.current = true
              targetChatId = resolvedId
              await onResolvedChatId?.(resolvedId)
            }
            await onAfterSend?.()

            // If we created a chat just to start this conversation, sync messages once
            // the backend has persisted them (so temp ids are replaced with server history).
            if (didCreateChat && resolvedId) {
              try {
                const current = Number(activeChatIdRef.current)
                if (Number.isFinite(current) && current === Number(targetChatId)) {
                  const data = await request(`/v1/chat/history/${targetChatId}`, { method: 'GET' })
                  setMessages(Array.isArray(data.history) ? data.history : [])
                }
              } catch {
                // ignore; optimistic UI is already correct enough
              }
            }
          } else if (evt?.type === 'error') {
            throw new Error(String(evt.message || 'Stream error'))
          }
        }
      }
    } catch (err) {
      if (isInsufficientCreditsError(err)) {
        onCreditIssue?.(err)
        setError('')
      } else {
        setError(humanizeApiError(err, 'Mesaj gonderilemedi'))
      }
      setMessages((prev) => prev.filter((m) => m.id !== asstTempId))
      if (!didComplete && Array.isArray(injectedIctihatsSnapshot) && injectedIctihatsSnapshot.length) {
        setComposerIctihats(injectedIctihatsSnapshot)
      }
      if (!didComplete && Array.isArray(injectedPetitionContextsSnapshot) && injectedPetitionContextsSnapshot.length) {
        setComposerPetitionContexts(injectedPetitionContextsSnapshot)
      }
    } finally {
      setSending(false)
    }
  }

  function onPickFiles() {
    if (uploading) return
    fileInputRef.current?.click()
  }

  function onFileChange(e) {
    const files = e.target.files
    if (files?.length) {
      onUploadDocuments?.(files)
    }
    e.target.value = ''
  }

  function onDragEnter(e) {
    e.preventDefault()
    e.stopPropagation()
    setDragging(true)
  }

  function onDragOver(e) {
    e.preventDefault()
    e.stopPropagation()
    setDragging(true)
  }

  function onDragLeave(e) {
    e.preventDefault()
    e.stopPropagation()
    // only hide when leaving the container (not when moving over children)
    if (e.currentTarget === e.target) setDragging(false)
  }

  function onDrop(e) {
    e.preventDefault()
    e.stopPropagation()
    setDragging(false)
    const files = e.dataTransfer?.files
    if (files?.length) onUploadDocuments?.(files)
  }

  function applySuggestion(text) {
    const nextValue = String(text || '')
    setInput(nextValue)
    requestAnimationFrame(() => {
      const textarea = composerRef.current?.querySelector('textarea')
      textarea?.focus()
      const pos = nextValue.length
      textarea?.setSelectionRange?.(pos, pos)
    })
  }

  function handleSuggestionClick(suggestion) {
    if (suggestion?.action === 'show-ictihat-hint') {
      onShowAiIctihatHint?.()
      return
    }
    applySuggestion(suggestion?.prompt)
  }

  return (
    <div className="chat-view-shell flex h-full flex-col overflow-hidden">
      <div
        ref={scrollRef}
        className="relative flex-1 overflow-x-hidden overflow-y-auto px-3 sm:px-4"
        onDragEnter={onDragEnter}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
      >
        {isDragging ? (
          <div className="drop-overlay" aria-hidden="true">
            <div className="drop-card">Dosyaları buraya bırak</div>
          </div>
        ) : null}

        <div className="chat-stream mx-auto w-full max-w-3xl space-y-4 px-1 py-6 sm:px-0">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader variant="text-shimmer" text="Yükleniyor..." size="md" />
            </div>
          ) : null}
          {error ? <div className="error">{error}</div> : null}
          {!loading && !error && messages.length === 0 ? (
            <div className="chat-empty-state">
              <div className="chat-empty-brand">
                <div className="chat-empty-logo-shell">
                  <img className="chat-empty-logo" src={yargucuLogo} alt="Yargucu" />
                </div>
                <div className="chat-empty-brand-copy">
                  <div className="chat-empty-kicker">AI HUKUK ASİSTANI</div>
                  <div className="sidebar-brand-name chat-empty-brand-name">YARGUCU</div>
                  <p className="chat-empty-subtitle">
                    Dilekçe taslağı, emsal karar taraması ve hukuki analiz için tek akışta başlayın.
                  </p>
                </div>
              </div>
              <div className="chat-empty-suggestions" role="list" aria-label="Ornek baslangiclar">
                {EMPTY_CHAT_SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion.title}
                    type="button"
                    className="chat-empty-suggestion"
                    onClick={() => handleSuggestionClick(suggestion)}
                  >
                    <span className="chat-empty-suggestion-label">{suggestion.label}</span>
                    <span className="chat-empty-suggestion-title">{suggestion.title}</span>
                    <span className="chat-empty-suggestion-description">{suggestion.description}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {messages.map((m, index) => {
            const isUser = m.role === 'user'
            const isAssistant = !isUser
            const isLastMessage = index === messages.length - 1
            const displayText = m.message || ''
            const showPreparing = Boolean(m.pending && !displayText && preparing?.kind)
            const prepLabel =
              preparing?.kind === 'dilekce'
                ? 'Dilekçe'
                : preparing?.kind === 'word'
                  ? 'Word Dosyası'
                  : preparing?.kind === 'ictihat'
                    ? 'İçtihatlar'
                  : ''
            const prepVerb = preparing?.kind === 'ictihat' ? 'Aranıyor' : 'Hazırlanıyor'
            const ictihatItems = isAssistant ? getMessageIctihatItems(m) : []
            const injectedIctihatItems = isUser ? getMessageInjectedIctihatItems(m) : []
            const injectedPetitionContexts = isUser ? getMessageInjectedPetitionContexts(m) : []
            const featureRecommendation = isAssistant ? getMessageFeatureRecommendation(m) : null
            const sortMode = ictihatSortByMsgId?.[m.id] || 'relevance'
            const sortedIctihatItems = sortIctihatItems(ictihatItems, sortMode)
            const sortLabel = sortMode === 'date' ? 'Sıra: karar tarihi' : 'Sıra: alaka düzeyi'
            const atifBlocksForMsg = isAssistant ? extractAtifBlocks(displayText) : []
            const markdownText = normalizeMarkdownText(displayText)
            const CodeWithContext = (codeProps) => (
              <MarkdownCode {...codeProps} __kunyeContext={{ atifBlocks: atifBlocksForMsg, messageId: m.id }} />
            )
            const markdownComponents = { a: MarkdownLink, pre: MarkdownPre, code: CodeWithContext }

            return (
              <Message
                key={m.id}
                className={`mx-auto flex w-full max-w-3xl flex-col gap-2 px-0 md:px-6 ${isAssistant ? 'items-start' : 'items-end'}`}
              >
                {isAssistant ? (
                  <div className="group flex w-full flex-col gap-0">
                    <MessageContent className="text-foreground w-full flex-1 rounded-lg bg-transparent p-0">
                      {m.pending && !displayText ? (
                        showPreparing ? (
                          <span className="prep-line" aria-label={`${prepLabel} ${prepVerb.toLowerCase()}...`}>
                            <span className="prep-label">{prepLabel}</span>{' '}
                            <span className="typewriter" aria-hidden="true">
                              {prepVerb} ...
                            </span>
                          </span>
                        ) : (
                          <Loader variant="typing" size="md" />
                        )
                      ) : (
                        <>
                          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                            {markdownText || '...'}
                          </ReactMarkdown>
                          {m.pending ? <span className="streaming-markdown-caret" aria-hidden="true" /> : null}
                          {featureRecommendation?.feature === 'ictihat_search' && m.id === visibleFeatureRecommendationMessageId ? (
                            <Alert className="msg-feature-recommendation">
                              <div className="msg-feature-recommendation-copy">
                                <AlertTitle className="msg-feature-recommendation-title">
                                  {String(featureRecommendation?.title || 'AI İçtihat Arama ile derinleştirin')}
                                </AlertTitle>
                                <AlertDescription className="msg-feature-recommendation-text">
                                  {String(
                                    featureRecommendation?.message ||
                                      'Bu konu için daha kapsamlı emsal taraması AI İçtihat Arama tarafında daha verimli olacaktır.',
                                  )}
                                </AlertDescription>
                              </div>
                              <AlertAction className="static mt-0 shrink-0 self-start">
                                <Button
                                  type="button"
                                  variant="outline"
                                  size="sm"
                                  className="msg-feature-recommendation-btn"
                                  onClick={() => onOpenIctihatSearch?.(featureRecommendation)}
                                >
                                  {String(featureRecommendation?.action_label || 'AI İçtihat Arama')}
                                </Button>
                              </AlertAction>
                            </Alert>
                          ) : null}
                          {ictihatItems.length ? (
                            <div className="msg-ictihat">
                              <div className="msg-ictihat-title-row">
                                <div className="msg-ictihat-title">İçtihatlar</div>
                                <button
                                  type="button"
                                  className="msg-ictihat-sort"
                                  onClick={() =>
                                    setIctihatSortByMsgId((prev) => ({
                                      ...(prev || {}),
                                      [m.id]: (prev?.[m.id] || 'relevance') === 'date' ? 'relevance' : 'date',
                                    }))
                                  }
                                  title="Sıralamayı değiştir"
                                >
                                  {sortLabel}
                                </button>
                              </div>
                              <div className="msg-ictihat-list" role="list">
                                {sortedIctihatItems.map((it, idx) => {
                                  const did = it?.document_id
                                  const citation = formatIctihatCitation(it)
                                  const excerpt = getIctihatExcerpt(it)
                                  const hasInlineDate = Boolean(it?.karar_tarihi ?? it?.kararTarihi ?? it?.karar?.tarih)
                                  const kararTarihi = hasInlineDate ? '' : formatIctihatDecisionDate(it)
                                  const atifBlocks = atifBlocksForMsg
                                  return (
                                    <button
                                      key={String(did ?? idx)}
                                      type="button"
                                      className="msg-ictihat-btn"
                                      onClick={() => onOpenIctihat?.(it, { atifBlocks, messageId: m.id })}
                                      title={citation}
                                    >
                                      <span className="msg-ictihat-toprow">
                                        <span className="msg-ictihat-citation">{citation}</span>
                                        {kararTarihi ? <span className="msg-ictihat-date">{kararTarihi}</span> : null}
                                      </span>
                                      {excerpt ? <span className="msg-ictihat-excerpt">{excerpt}</span> : null}
                                    </button>
                                  )
                                })}
                              </div>
                            </div>
                          ) : null}
                        </>
                      )}
                    </MessageContent>
                    {/* Assistant hover actions */}
                    {!m.pending && displayText ? (
                      <div className={`msg-actions -ml-2 ${isLastMessage ? 'msg-actions-visible' : ''}`}>
                        <button
                          type="button"
                          className="msg-action-btn"
                          title={copiedMsgId === m.id ? 'Kopyalandı!' : 'Kopyala'}
                          onClick={() => {
                            try {
                              navigator.clipboard.writeText(displayText)
                            } catch {
                              const ta = document.createElement('textarea')
                              ta.value = displayText
                              ta.style.position = 'fixed'
                              ta.style.opacity = '0'
                              document.body.appendChild(ta)
                              ta.select()
                              document.execCommand('copy')
                              document.body.removeChild(ta)
                            }
                            setCopiedMsgId(m.id)
                            setTimeout(() => setCopiedMsgId((prev) => (prev === m.id ? null : prev)), 2000)
                          }}
                        >
                          {copiedMsgId === m.id
                            ? <Check size={15} className="text-black dark:text-white" />
                            : <Copy size={15} />
                          }
                        </button>
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <div className="group flex w-full flex-col items-end gap-1">
                    <MessageContent className="bg-muted text-foreground max-w-[85%] min-w-0 break-words rounded-3xl px-5 py-2.5 sm:max-w-[75%]">
                      {displayText}
                    </MessageContent>
                    {injectedIctihatItems.length || injectedPetitionContexts.length ? (
                      <div className="msg-context w-full max-w-[85%] sm:max-w-[75%]">
                        {injectedIctihatItems.length ? (
                          <div className="msg-context-block">
                            <div className="msg-context-title">Eklenen içtihatlar</div>
                            <div className="msg-context-chip-list" role="list">
                              {injectedIctihatItems.map((it, idx) => {
                                const did = Number(it?.document_id)
                                const key = Number.isFinite(did) ? `ictihat-${did}` : `ictihat-${idx}`
                                return (
                                  <button
                                    key={key}
                                    type="button"
                                    className="msg-context-chip msg-context-chip-clickable"
                                    onClick={() => onOpenIctihat?.(it, { atifBlocks: [], messageId: m.id })}
                                    title={formatIctihatCitation(it)}
                                  >
                                    <span className="msg-context-chip-text">{formatIctihatCitation(it)}</span>
                                  </button>
                                )
                              })}
                            </div>
                          </div>
                        ) : null}
                        {injectedPetitionContexts.length ? (
                          <div className="msg-context-block">
                            <div className="msg-context-title">Eklenen dilekçe bağlamı</div>
                            <div className="msg-context-petition-list">
                              {injectedPetitionContexts.map((item, idx) => {
                                const key = buildPetitionContextKey(item, idx)
                                const bodyText = formatInjectedPetitionContextText(item)
                                const previewText =
                                  bodyText.length > 120 ? `${bodyText.slice(0, 120).trim()}...` : bodyText
                                const isExpanded = Boolean(expandedPetitionContextKeys?.[key])
                                return (
                                  <button
                                    key={key}
                                    type="button"
                                    className={`msg-context-petition-card msg-context-petition-toggle${isExpanded ? ' is-expanded' : ''}`}
                                    onClick={() =>
                                      setExpandedPetitionContextKeys((prev) => ({
                                        ...(prev || {}),
                                        [key]: !prev?.[key],
                                      }))
                                    }
                                    title={isExpanded ? 'Daralt' : 'Genişlet'}
                                  >
                                    <div className="msg-context-petition-toprow">
                                      <div className="msg-context-petition-label">{formatInjectedPetitionContextLabel(item)}</div>
                                      <div className="msg-context-petition-action">{isExpanded ? 'Daralt' : 'Aç'}</div>
                                    </div>
                                    {previewText ? <div className="msg-context-petition-preview">{previewText}</div> : null}
                                    {isExpanded && bodyText ? <div className="msg-context-petition-text">{bodyText}</div> : null}
                                  </button>
                                )
                              })}
                            </div>
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                )}
              </Message>
            )
          })}

          <div ref={bottomRef} />
        </div>
      </div>

      <div ref={composerRef} className="chat-composer inset-x-0 bottom-0 mx-auto w-full max-w-3xl shrink-0 px-3 pb-3 md:px-5 md:pb-5">
        {creditBanner?.message ? (
          <div className="mb-3">
            <CreditBanner
              title={creditBanner?.title}
              message={creditBanner?.message}
              compactMessage={creditBanner?.compactMessage}
              actionLabel="Kredi yükle"
              onAction={onOpenSettings}
              contextual
            />
          </div>
        ) : null}
        {composerPetitionContexts.length ? (
          <div className="composer-petition-wrap">
            <div className="composer-petition-head">
              <div className="composer-petition-title">Dilekçe bağlamı</div>
              <button className="composer-petition-clear" type="button" onClick={() => setComposerPetitionContexts([])} disabled={sending}>
                Temizle
              </button>
            </div>
            <div className="composer-petition-chips">
              {composerPetitionContexts.map((item, idx) => {
                const key = [item?.petition_id, item?.version_id, item?.field_path, item?.selected_text]
                  .map((v) => String(v || ''))
                  .join(':') || `petition-${idx}`
                return (
                  <span key={key} className="composer-petition-chip" title={formatComposerPetitionChip(item)}>
                    <span className="composer-petition-chip-text">{formatComposerPetitionChip(item)}</span>
                    <button
                      className="composer-petition-chip-remove"
                      type="button"
                      aria-label="Kaldır"
                      title="Kaldır"
                      disabled={sending}
                      onClick={() => setComposerPetitionContexts((prev) => (prev || []).filter((_, ix) => ix !== idx))}
                    >
                      ×
                    </button>
                  </span>
                )
              })}
            </div>
          </div>
        ) : null}
        {composerIctihats.length ? (
          <div className="composer-ictihat-wrap">
            <div className="composer-ictihat-head">
              <div className="composer-ictihat-title">İçtihatlar</div>
              <button className="composer-ictihat-clear" type="button" onClick={() => setComposerIctihats([])} disabled={sending}>
                Temizle
              </button>
            </div>
            <div className="composer-ictihat-chips">
              {composerIctihats.map((it, idx) => {
                const did = Number(it?.document_id)
                const key = Number.isFinite(did) ? String(did) : `idx-${idx}`
                return (
                  <span key={key} className="composer-ictihat-chip" title={formatComposerIctihatChip(it)}>
                    <span className="composer-ictihat-chip-text">{formatComposerIctihatChip(it)}</span>
                    <button
                      className="composer-ictihat-chip-remove"
                      type="button"
                      aria-label="Kaldır"
                      title="Kaldır"
                      disabled={sending}
                      onClick={() =>
                        setComposerIctihats((prev) => (prev || []).filter((x, ix) => (Number.isFinite(did) ? Number(x?.document_id) !== did : ix !== idx)))
                      }
                    >
                      ×
                    </button>
                  </span>
                )
              })}
            </div>
          </div>
        ) : null}
        {featureHint ? (
          <div className="mb-4">
            <FeatureHintBanner hint={featureHint} onDismiss={onDismissHint} />
          </div>
        ) : null}
        <PromptInput
          value={input}
          onValueChange={setInput}
          onSubmit={send}
          isLoading={sending}
          disabled={sending}
          className="border-input bg-popover relative z-10 w-full rounded-3xl border p-0 shadow-xs"
        >
          <div className="flex flex-col">
            <PromptInputTextarea
              placeholder="Uyuşmazlığı, belge ihtiyacınızı veya aradığınız içtihadı yazın"
              className="min-h-[32px] pt-2 pl-4 text-base leading-[1.3]"
            />
            <PromptInputActions className="mt-2 flex w-full items-center justify-between gap-2 px-3 pb-2">
              <div className="flex items-center gap-2">
                <PromptInputAction tooltip="Dosya ekle">
                  <button
                    className="msg-action-btn border border-input rounded-full size-9"
                    type="button"
                    aria-label="Dosya ekle"
                    title="Dosya ekle"
                    onClick={onPickFiles}
                    disabled={uploading}
                  >
                    <Paperclip size={16} />
                  </button>
                </PromptInputAction>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  hidden
                  accept={uploadAccept}
                  onChange={onFileChange}
                  disabled={uploading}
                />
              </div>
              <div className="flex items-center gap-2">
                <button
                  className="pk-send-btn"
                  onClick={send}
                  disabled={sending || !input.trim()}
                  type="button"
                  aria-label="Gönder"
                  title="Gönder"
                >
                  {!sending ? (
                    <ArrowUp size={18} strokeWidth={2.5} />
                  ) : (
                    <span className="size-3 rounded-sm bg-white" />
                  )}
                </button>
              </div>
            </PromptInputActions>
          </div>
        </PromptInput>
        <div className="chat-composer-disclaimer mt-3 flex justify-center text-center text-[10px] text-muted-foreground select-none sm:text-xs">
          <span className="inline-block max-w-full whitespace-normal break-words">© 2026 Yargucu bir hukuki danışmanlık hizmeti değildir. Üretilen içeriklerin doğruluğunu teyit ediniz.  Version 0.5</span>
        </div>
      </div>
    </div>
  )
}
