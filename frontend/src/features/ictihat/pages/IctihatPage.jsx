import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { History, RotateCcw, Star, Trash2, X } from 'lucide-react'
import { DotLottieReact } from '@lottiefiles/dotlottie-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Dialog, DialogContent, DialogOverlay } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { useAuth } from '../../auth/useAuth.js'
import { normalizeIctihatDocumentText } from '../../chat/chatContracts.js'
import { buildCourtLabel, getCourtDisplayName, normalizeKurum, stripKurumPrefixFromDaire } from '../utils/courtLabel.js'
import { humanizeApiError, isInsufficientCreditsError } from '../../../shared/api/contracts.js'
import { CreditBanner } from '../../../shared/components/CreditBanner.jsx'
import ictihatSearchAnimation from '../../../animations/searching.lottie?url'
import yargucuLogo from '../../../logopack/yargucu-logo-siyah.svg'

function trimToWords(text, maxWords) {
  const words = String(text || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
  if (words.length <= maxWords) return words.join(' ')
  return `${words.slice(0, maxWords).join(' ')}...`
}

function chatLabel(chat) {
  const t = (chat?.title || '').trim()
  if (t) return trimToWords(t, 6)
  const fm = (chat?.first_message || '').trim()
  if (fm) return trimToWords(fm, 6)
  const s = (chat?.last_sum || '').trim()
  if (s) return trimToWords(s, 6)
  return 'Yeni sohbet'
}

function buildReferenceTail(doc) {
  const ey = doc?.esas?.yil
  const es = doc?.esas?.sira
  const ky = doc?.karar?.yil
  const ks = doc?.karar?.sira
  const parts = []
  if (ey && es) parts.push(`${ey}/${es} E.`)
  if (ky && ks) parts.push(`${ky}/${ks} K.`)
  return parts.join(' › ').trim()
}

function buildEmsalKararLine(doc) {
  const ey = doc?.esas?.yil
  const es = doc?.esas?.sira
  const ky = doc?.karar?.yil
  const ks = doc?.karar?.sira
  const left = ey && es ? `${ey}/${es} E.` : ''
  const right = ky && ks ? `${ky}/${ks} K.` : ''
  if (left && right) return `${left} -- ${right}`
  return left || right || ''
}

function buildSelectedIctihatPayload(doc) {
  const d = doc && typeof doc === 'object' ? doc : {}
  const documentId = Number(d?.document_id ?? d?.documentId ?? d?.id)
  if (!Number.isFinite(documentId) || documentId <= 0) return null

  const ey = d?.esas?.yil ?? d?.esas_yil
  const es = d?.esas?.sira ?? d?.esas_sira
  const ky = d?.karar?.yil ?? d?.karar_yil
  const ks = d?.karar?.sira ?? d?.karar_sira
  const emsalNo = ey && es ? `${ey}/${es}` : null
  const kararNo = ky && ks ? `${ky}/${ks}` : null

  const kurum = normalizeKurum(d?.kurum, d?.daire ?? d?.yargitay_daire) || null
  const daire = String(d?.daire ?? d?.yargitay_daire ?? '').trim() || null

  return {
    document_id: documentId,
    emsal_no: emsalNo,
    karar_no: kararNo,
    daire,
    kurum,
  }
}

function getDecisionDateIso(doc) {
  const t = doc?.karar?.tarih
  return t ? String(t) : ''
}

function buildReferenceString(doc) {
  const daire = String(doc?.daire_label ?? doc?.daire ?? doc?.yargitay_daire ?? '').trim()
  const kurum = String(doc?.kurum ?? '').trim()
  const court = buildCourtLabel({ kurum, daire })
  const tail = buildReferenceTail(doc)
  const parts = []
  if (court) parts.push(court)
  if (tail) parts.push(tail)
  return parts.join(' › ').trim()
}

function buildCitation(doc) {
  return buildReferenceString(doc) || 'Karar'
}

function formatDecisionDate(value) {
  if (!value) return ''
  const text = String(value)
  const date = new Date(text)
  if (Number.isNaN(date.getTime())) return text
  return new Intl.DateTimeFormat('tr-TR', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
  }).format(date)
}

function formatDecisionDateWithMonth(value) {
  if (!value) return ''
  const text = String(value)
  const date = new Date(text)
  if (Number.isNaN(date.getTime())) return text
  return new Intl.DateTimeFormat('tr-TR', {
    day: '2-digit',
    month: 'long',
    year: '2-digit',
  }).format(date)
}

function isAbortError(error) {
  return error?.name === 'AbortError'
}

function buildDecisionMetaLine(doc, date) {
  const ey = doc?.esas?.yil
  const es = doc?.esas?.sira
  const ky = doc?.karar?.yil
  const ks = doc?.karar?.sira
  const formattedDate = formatDecisionDateWithMonth(date || getDecisionDateIso(doc))
  const parts = []
  if (ey && es) parts.push(`${ey}/${es} E.`)
  if (ky && ks) parts.push(`${ky}/${ks} K.`)
  if (formattedDate) parts.push(formattedDate)
  return parts.join(' - ')
}

function buildDecisionKunyeLine(doc, court, citation, date) {
  const courtLabel = String(court || citation || '')
    .split('›')[0]
    .trim()
  const metaLine = buildDecisionMetaLine(doc, date)
  return [courtLabel, metaLine].filter(Boolean).join(' - ')
}

function buildMobileDecisionHeading(court, citation, date) {
  const base = String(court || citation || '')
    .split('›')[0]
    .split(' - ')[0]
    .trim()
  const formattedDate = formatDecisionDate(date)
  return [base, formattedDate].filter(Boolean).join(' - ')
}

const SEARCH_MODE_LABELS = {
  ai: 'AI Arama',
  semantic: 'Anlamsal',
  keyword: 'Kelime Bazlı',
}

const HISTORY_PAGE_SIZE = 10

function getFilterValidationError({ esasYil, esasSira, kararYil, kararSira }) {
  if (esasYil && !esasSira) return 'Esas yılı girdiniz; Esas No da gerekli.'
  if (!esasYil && esasSira) return 'Esas No girdiniz; Esas yılı da gerekli.'
  if (kararYil && !kararSira) return 'Karar yılı girdiniz; Karar No da gerekli.'
  if (!kararYil && kararSira) return 'Karar No girdiniz; Karar yılı da gerekli.'
  return ''
}

function buildHistoryFilterSummary(filters) {
  const f = filters && typeof filters === 'object' ? filters : {}
  const parts = []
  const daire = String(f?.daire || '').trim()
  const esasYil = f?.esas_yil
  const esasSira = f?.esas_sira
  const kararYil = f?.karar_yil
  const kararSira = f?.karar_sira
  if (daire) parts.push(daire)
  if (esasYil && esasSira) parts.push(`${esasYil}/${esasSira} E.`)
  if (kararYil && kararSira) parts.push(`${kararYil}/${kararSira} K.`)
  return parts.join(' - ')
}

function formatHistoryTimestamp(value) {
  if (!value) return ''
  const date = new Date(String(value))
  if (Number.isNaN(date.getTime())) return String(value)
  return new Intl.DateTimeFormat('tr-TR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function buildHistoryTitle(item) {
  const queryText = trimToWords(item?.query_text || '', 12)
  if (queryText) return queryText
  return buildHistoryFilterSummary(item?.filters) || 'Filtre araması'
}

const DOC_SECTION_MARKERS = ['MAHKEMESİ', 'DAVA TÜRÜ', 'GEREĞİ GÖRÜŞÜLDÜ', 'GEREGI GORUSULDU']
const SEARCH_MODE_UI = {
  ai: {
    placeholder: 'Nasıl bir emsal karar istediğinizi anlatınız...',
    info:
      'Kararlar yapay zeka tarafından aranır ve filtrelenir. Olayı, durumu veya istediğiniz emsal kararı detaylı ve net bir şekilde anlatmanız, en iyi sonucu almanıza yardımcı olur.',
    example:
      'Örn: "İşyerimden performans yetersizliği nedeniyle çıkarıldım. Kıdem tazminatı hakkım doğar mı? Bu sonuca ilişkin kararları bul."',
  },
  semantic: {
    placeholder: 'Anlam benzerliği ile arama...',
    info:
      'Bu modda, kararlar üzerinde anlam benzerliğine göre arama yapılır. Verimli kullanım için, aradığınız içtihat metnine anlam olarak yakın bir hukuki durum, olay örgüsü veya uyuşmazlık tanımı yazmanız faydalı olur.',
    example:
      'Örn: "İşverenin performans düşüklüğü gerekçesiyle yaptığı fesihte kıdem ve ihbar tazminatı koşullarının tartışıldığı kararlar."',
  },
  keyword: {
    placeholder: 'Kelime eşleşmesi ile arama...',
    info:
      'Bu modda, içtihat metinlerinin içindeki kelimeler sorgunuzla eşleştirilerek arama yapılır. Verimli kullanım için, karar metninde geçmesi muhtemel kelime, ibare ve hukuki terimleri yazmanız önerilir.',
    example:
      'Örn: "performans düşüklüğü fesih geçerli neden kıdem tazminatı iş kanunu 18"',
  },
}

function escapeRegExp(value) {
  return String(value || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function extractHighlightTerms(value) {
  const text = String(value || '').trim()
  if (!text) return []
  const terms = []
  const seen = new Set()
  const quoted = text.match(/"([^"]+)"|“([^”]+)”/g) || []
  quoted.forEach((item) => {
    const cleaned = item.replace(/^["“]|["”]$/g, '').trim()
    if (!cleaned) return
    const key = cleaned.toLocaleLowerCase('tr-TR')
    if (seen.has(key)) return
    seen.add(key)
    terms.push(cleaned)
  })
  const remainder = text.replace(/"([^"]+)"|“([^”]+)”/g, ' ')
  remainder
    .split(/\s+/)
    .map((item) => item.trim())
    .filter((item) => item.length >= 2)
    .forEach((item) => {
      const key = item.toLocaleLowerCase('tr-TR')
      if (seen.has(key)) return
      seen.add(key)
      terms.push(item)
    })
  return terms.sort((a, b) => b.length - a.length)
}

function buildHighlightedFragments(text, keywordTerms = [], searchTerms = []) {
  const content = String(text || '')
  if (!content) return []
  const markers = new Array(content.length).fill(0)
  const applyTerms = (terms, markerValue) => {
    terms.forEach((term) => {
      const source = String(term || '').trim()
      if (!source) return
      const regex = new RegExp(escapeRegExp(source), 'gi')
      let match = regex.exec(content)
      while (match) {
        const start = match.index
        const end = start + match[0].length
        for (let index = start; index < end; index += 1) {
          if (markerValue === 2 || markers[index] === 0) {
            markers[index] = markerValue
          }
        }
        match = regex.exec(content)
      }
    })
  }
  applyTerms(keywordTerms, 1)
  applyTerms(searchTerms, 2)
  const parts = []
  let start = 0
  while (start < content.length) {
    const marker = markers[start]
    let end = start + 1
    while (end < content.length && markers[end] === marker) end += 1
    parts.push({
      text: content.slice(start, end),
      type: marker === 2 ? 'search' : marker === 1 ? 'keyword' : 'plain',
    })
    start = end
  }
  return parts
}

function renderHighlightedText(text, keywordTerms, searchTerms, keyPrefix) {
  const fragments = buildHighlightedFragments(text, keywordTerms, searchTerms)
  if (!fragments.length) return text
  return fragments.map((fragment, index) => {
    if (fragment.type === 'plain') return <span key={`${keyPrefix}-p-${index}`}>{fragment.text}</span>
    return (
      <mark
        key={`${keyPrefix}-${fragment.type}-${index}`}
        className={fragment.type === 'search' ? 'ictihat-doc-search-hit' : 'ictihat-doc-keyword-hit'}
      >
        {fragment.text}
      </mark>
    )
  })
}

function getSortableDecisionTime(value) {
  if (!value) return Number.NEGATIVE_INFINITY
  const timestamp = new Date(String(value)).getTime()
  return Number.isNaN(timestamp) ? Number.NEGATIVE_INFINITY : timestamp
}

function defaultTopKForMode(searchMode, isMobile) {
  if (!isMobile) return 20
  return searchMode === 'ai' ? 50 : 20
}

function renderDocumentContent(text, keywordTerms = [], searchTerms = [], options = {}) {
  const structured = options?.structured !== false
  const lines = String(text || '').split('\n')
  let firstBodyLineSeen = false
  return lines.map((line, index) => {
    const trimmed = line.trim()
    if (!trimmed) {
      return <div key={`gap-${index}`} className="ictihat-doc-gap" />
    }
    if (!structured) {
      const isLead = !firstBodyLineSeen
      firstBodyLineSeen = true
      return (
        <div key={`line-${index}`} className={`ictihat-doc-line${isLead ? ' is-lead' : ''}`}>
          {renderHighlightedText(line, keywordTerms, searchTerms, `line-${index}`)}
        </div>
      )
    }
    const isSection = DOC_SECTION_MARKERS.some((marker) => trimmed.startsWith(marker))
    if (isSection) {
      return (
        <div key={`section-${index}`} className="ictihat-doc-section">
          {renderHighlightedText(line, keywordTerms, searchTerms, `section-${index}`)}
        </div>
      )
    }
    const pairMatch = trimmed.match(/^([A-ZÇĞİÖŞÜ0-9\s./-]+):\s*(.+)$/)
    if (pairMatch) {
      return (
        <div key={`pair-${index}`} className="ictihat-doc-pair">
          <span className="ictihat-doc-pair-label">{renderHighlightedText(pairMatch[1], keywordTerms, searchTerms, `pair-label-${index}`)}</span>
          <span className="ictihat-doc-pair-value">{renderHighlightedText(pairMatch[2], keywordTerms, searchTerms, `pair-value-${index}`)}</span>
        </div>
      )
    }
    const isLead = !firstBodyLineSeen
    firstBodyLineSeen = true
    return (
      <div key={`line-${index}`} className={`ictihat-doc-line${isLead ? ' is-lead' : ''}`}>
        {renderHighlightedText(line, keywordTerms, searchTerms, `line-${index}`)}
      </div>
    )
  })
}

function shouldSkipStructuredDocumentParsing(doc, fallbackCourt = '') {
  const kurum = normalizeKurum(doc?.kurum || fallbackCourt, doc?.daire ?? doc?.yargitay_daire ?? '')
  return kurum === 'UYUSMAZLIK MAHKEMESI'
}

export function IctihatPage() {
  const { request } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const searchRequestIdRef = useRef(0)
  const activeSearchControllerRef = useRef(null)
  const docTextRef = useRef(null)
  const searchInfoRef = useRef(null)
  const queryInputRef = useRef(null)

  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window === 'undefined') return false
    return window.innerWidth <= 720
  })

  const [searchMode, setSearchMode] = useState('ai') // 'semantic' | 'ai' | 'keyword'
  const [query, setQuery] = useState('')
  const [topK, setTopK] = useState(20)
  // AI mode "effort hint" — null = user hasn't picked a tier, agent runs default exhaustive
  // protocol. When set (5/10/15/20) it's sent as `top_k` to /agent_search, which injects an
  // effort instruction block into the LLM's system prompt.
  const [aiTopK, setAiTopK] = useState(null)

  useEffect(() => {
    if (queryInputRef.current) {
      queryInputRef.current.style.height = 'auto'
      queryInputRef.current.style.height = `${Math.min(queryInputRef.current.scrollHeight, 200)}px`
    }
  }, [query])

  useEffect(() => {
    const recommendation = location.state?.ictihatRecommendation
    if (!recommendation || typeof recommendation !== 'object') return

    const nextQuery = String(recommendation?.queryText || '').trim()
    const nextMode = String(recommendation?.searchMode || 'ai').trim() || 'ai'

    if (nextQuery) setQuery(nextQuery)
    if (nextMode) setSearchMode(nextMode)

    requestAnimationFrame(() => {
      queryInputRef.current?.focus()
    })
  }, [location.key, location.state])
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [daireOptions, setDaireOptions] = useState([]) // [{ key, kurum, daire, daire_label, display }]
  const [kurum, setKurum] = useState('')
  const [daire, setDaire] = useState('')
  const [esasYil, setEsasYil] = useState('')
  const [esasSira, setEsasSira] = useState('')
  const [kararYil, setKararYil] = useState('')
  const [kararSira, setKararSira] = useState('')

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [creditBanner, setCreditBanner] = useState(null)
  const [groups, setGroups] = useState([])
  const [items, setItems] = useState([])
  const [truncated, setTruncated] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)

  const [openDoc, setOpenDoc] = useState(null) // { document_id, citation, page }
  const [, setDocLoading] = useState(false)
  const [docError, setDocError] = useState('')
  const [activeIndex, setActiveIndex] = useState(-1)
  const [copyFeedback, setCopyFeedback] = useState(false)
  const [showScrollTop, setShowScrollTop] = useState(false)
  const [isDocCondensed, setIsDocCondensed] = useState(false)
  const [isDocFullscreen, setIsDocFullscreen] = useState(false)
  const [docSearchQuery, setDocSearchQuery] = useState('')
  const [docSearchMatchCount, setDocSearchMatchCount] = useState(0)
  const [docSearchActiveIndex, setDocSearchActiveIndex] = useState(0)
  const [searchInfoOpen, setSearchInfoOpen] = useState(false)
  const [historyItems, setHistoryItems] = useState([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyBusyId, setHistoryBusyId] = useState(null)
  const [showHistoryView, setShowHistoryView] = useState(false)
  const [historyPage, setHistoryPage] = useState(1)

  const [selectedById, setSelectedById] = useState({}) // { [documentId]: {document_id, emsal_no?, karar_no?, daire?, kurum?} }
  const selectedList = useMemo(() => Object.values(selectedById || {}), [selectedById])
  const selectedCount = selectedList.length
  const [attachOpen, setAttachOpen] = useState(false)
  const [attachChats, setAttachChats] = useState([])
  const [attachLoading, setAttachLoading] = useState(false)
  const [attachError, setAttachError] = useState('')
  const [summaryOpen, setSummaryOpen] = useState(false)
  const [summaryData, setSummaryData] = useState(null)

  const validationError = useMemo(() => {
    return getFilterValidationError({ esasYil, esasSira, kararYil, kararSira })
  }, [esasSira, esasYil, kararSira, kararYil])
  const activeFilterCount = useMemo(() => {
    let count = 0
    if (daire) count += 1
    if (esasYil && esasSira) count += 1
    if (kararYil && kararSira) count += 1
    return count
  }, [daire, esasSira, esasYil, kararSira, kararYil])

  const canSearch = Boolean(query.trim() || daire || (esasYil && esasSira) || (kararYil && kararSira))
  const hasAnyFilters = Boolean(daire || esasYil || esasSira || kararYil || kararSira)
  const usesGroupedResults = searchMode === 'semantic' || searchMode === 'keyword'
  const historyPageCount = Math.max(1, Math.ceil(historyItems.length / HISTORY_PAGE_SIZE))
  const paginatedHistoryItems = useMemo(() => {
    const start = (Math.max(1, historyPage) - 1) * HISTORY_PAGE_SIZE
    return historyItems.slice(start, start + HISTORY_PAGE_SIZE)
  }, [historyItems, historyPage])
  const results = useMemo(() => {
    if (usesGroupedResults) {
      return groups
        .map((g, index) => {
        const doc = g?.doc || {}
        const normalizedDoc = { ...doc, kurum: doc?.kurum ?? kurum }
        const referenceFull = buildReferenceString(normalizedDoc)
        const emsalKarar = buildEmsalKararLine(normalizedDoc)
        const decisionDateIso = getDecisionDateIso(normalizedDoc)
        const court = buildCourtLabel({ kurum: normalizedDoc?.kurum, daire: normalizedDoc?.daire ?? normalizedDoc?.yargitay_daire })
        return {
          documentId: doc?.document_id,
          citation: buildCitation(normalizedDoc),
          court: court || 'Karar',
          reference: decisionDateIso || 'Tarih yok',
          referenceFull,
          emsalKarar,
          decisionDateIso,
          snippet: Array.isArray(g?.matched_chunks) ? String(g.matched_chunks[0]?.snippet || '').trim() : '',
          why: '',
          summary: '',
          tier: null,
          doc,
          sortIndex: index,
        }
      })
        .sort((left, right) => {
          const timeDiff = getSortableDecisionTime(right.decisionDateIso) - getSortableDecisionTime(left.decisionDateIso)
          if (timeDiff !== 0) return timeDiff
          return left.sortIndex - right.sortIndex
        })
    }
    return items
      .map((it, index) => {
      const doc = it || {}
      const normalizedDoc = { ...doc, kurum: doc?.kurum ?? kurum }
      const referenceFull = buildReferenceString(normalizedDoc)
      const emsalKarar = buildEmsalKararLine(normalizedDoc)
      const decisionDateIso = getDecisionDateIso(normalizedDoc)
      const court = buildCourtLabel({ kurum: normalizedDoc?.kurum, daire: normalizedDoc?.daire ?? normalizedDoc?.yargitay_daire })
      return {
        documentId: doc?.document_id,
        citation: buildCitation(normalizedDoc),
        court: court || 'Karar',
        reference: decisionDateIso || 'Tarih yok',
        referenceFull,
        emsalKarar,
        decisionDateIso,
        snippet: String(doc?.snippet || '').trim(),
        why: String(doc?.why || '').trim(),
        summary: String(doc?.summary || '').trim(),
        tier: (() => {
          const t = Number(doc?.tier)
          return t >= 1 && t <= 5 && Number.isInteger(t) ? t : null
        })(),
        doc,
        sortIndex: index,
      }
    })
      .sort((left, right) => {
        if (searchMode === 'ai') {
          return left.sortIndex - right.sortIndex
        }
        const timeDiff = getSortableDecisionTime(right.decisionDateIso) - getSortableDecisionTime(left.decisionDateIso)
        if (timeDiff !== 0) return timeDiff
        return left.sortIndex - right.sortIndex
      })
  }, [groups, items, kurum, searchMode, usesGroupedResults])
  const isInitialState = !hasSearched && !loading && !error
  const isLoadingState = hasSearched && loading
  const isEmptyState = hasSearched && !loading && !error && results.length === 0
  const isResultsState = hasSearched && !loading && results.length > 0
  const isCompactMobileSearch = isMobile && !isInitialState
  const effectiveTopK = Number(topK) || defaultTopKForMode(searchMode, isMobile)
  const currentSearchModeUi = SEARCH_MODE_UI[searchMode] || SEARCH_MODE_UI.ai
  const keywordHighlightTerms = useMemo(
    () => (searchMode === 'keyword' && hasSearched ? extractHighlightTerms(query) : []),
    [hasSearched, query, searchMode],
  )
  const docSearchTerms = useMemo(() => {
    const text = String(docSearchQuery || '').trim()
    return text ? [text] : []
  }, [docSearchQuery])

  useEffect(() => {
    let cancelled = false
    async function loadNames() {
      try {
        const data = await request('/v1/ictihat/get_unique_daire_names', { method: 'GET' })
        const items = Array.isArray(data?.items) ? data.items : []
        const next = items
          .filter((x) => x && typeof x === 'object')
          .map((x) => {
            const k = normalizeKurum(x.kurum)
            const d = String(x.daire || '').trim() || ''
            const dl = String(x.daire_label || '').trim()
            if (!k) return null
            const display = buildCourtLabel({ kurum: k, daire: dl || d })
            return {
              key: `${k}::${d || '__NONE__'}`,
              kurum: k,
              daire: d,
              daire_label: dl || undefined,
              display,
            }
          })
          .filter(Boolean)
        if (!cancelled) setDaireOptions(next)
      } catch {
        if (!cancelled) setDaireOptions([])
      }
    }
    loadNames()
    return () => {
      cancelled = true
    }
  }, [request])

  // Distinct kurum (institution) list — first step of the cascading court filter.
  const kurumOptions = useMemo(() => {
    const seen = new Set()
    const out = []
    for (const o of daireOptions) {
      const k = o?.kurum
      if (!k || seen.has(k)) continue
      seen.add(k)
      out.push(k)
    }
    return out
  }, [daireOptions])

  // Daire options scoped to the currently selected kurum (institution).
  // Empty-daire entries (e.g. single-chamber institutions) are filtered out:
  // for those, selecting the kurum alone is the correct query.
  const filteredDaireOptions = useMemo(() => {
    if (!kurum) return []
    return daireOptions.filter((o) => o?.kurum === kurum && String(o?.daire || '').trim())
  }, [daireOptions, kurum])

  const showCreditBanner = useCallback((err) => {
    const detail = err?.data?.detail
    const remaining = Number(detail?.credit)
    const remainingText = Number.isFinite(remaining)
      ? ` Kalan kredi: ${remaining.toLocaleString('tr-TR', { maximumFractionDigits: 2 })}.`
      : ''
    setCreditBanner({
      title: 'Kredi bakiyesi yetersiz',
      message: `İçtihat araması için kullanılabilir krediniz yetersiz.${remainingText}`,
      compactMessage: 'İçtihat araması için kredi yükleyin.',
    })
  }, [])

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true)
    try {
      const data = await request('/v1/ictihat/history?limit=50', { method: 'GET' })
      setHistoryItems(Array.isArray(data?.items) ? data.items : [])
    } catch {
      setHistoryItems([])
    } finally {
      setHistoryLoading(false)
    }
  }, [request])

  useEffect(() => {
    if (typeof window === 'undefined') return undefined
    function handleResize() {
      setIsMobile(window.innerWidth <= 720)
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  useEffect(() => {
    loadHistory()
  }, [loadHistory])

  useEffect(() => {
    setHistoryPage((prev) => Math.min(Math.max(1, prev), historyPageCount))
  }, [historyItems.length, historyPageCount])

  useEffect(() => {
    function handlePointerDown(event) {
      if (!searchInfoRef.current?.contains(event.target)) {
        setSearchInfoOpen(false)
      }
    }
    function handleEscape(event) {
      if (event.key === 'Escape') setSearchInfoOpen(false)
    }
    window.addEventListener('mousedown', handlePointerDown)
    window.addEventListener('keydown', handleEscape)
    return () => {
      window.removeEventListener('mousedown', handlePointerDown)
      window.removeEventListener('keydown', handleEscape)
    }
  }, [])

  const filters = useMemo(() => {
    const f = {}
    if (kurum) f.kurum = normalizeKurum(kurum)
    if (daire) f.daire = daire
    if (esasYil) f.esas_yil = Number(esasYil)
    if (esasSira) f.esas_sira = Number(esasSira)
    if (kararYil) f.karar_yil = Number(kararYil)
    if (kararSira) f.karar_sira = Number(kararSira)
    return Object.keys(f).length ? f : null
  }, [daire, esasSira, esasYil, kararSira, kararYil, kurum])

  useEffect(() => {
    setActiveIndex(results.length ? 0 : -1)
  }, [results])

  useEffect(() => {
    if (!copyFeedback) return undefined
    const timer = window.setTimeout(() => setCopyFeedback(false), 1400)
    return () => window.clearTimeout(timer)
  }, [copyFeedback])

  useEffect(() => {
    if (!openDoc) {
      setShowScrollTop(false)
      setIsDocCondensed(false)
      setIsDocFullscreen(false)
      setDocSearchQuery('')
      setDocSearchMatchCount(0)
      setDocSearchActiveIndex(0)
      return
    }
    if (docTextRef.current) {
      docTextRef.current.scrollTop = 0
    }
    setShowScrollTop(false)
    setIsDocCondensed(false)
    setIsDocFullscreen(false)
    setDocSearchQuery('')
    setDocSearchMatchCount(0)
    setDocSearchActiveIndex(0)
  }, [openDoc])

  useEffect(() => {
    setDocSearchActiveIndex(0)
  }, [docSearchQuery])

  useEffect(() => {
    if (!isDocFullscreen) return undefined
    function handleFullscreenEscape(event) {
      if (event.key === 'Escape') setIsDocFullscreen(false)
    }
    window.addEventListener('keydown', handleFullscreenEscape)
    return () => window.removeEventListener('keydown', handleFullscreenEscape)
  }, [isDocFullscreen])

  useEffect(() => {
    const root = docTextRef.current
    if (!root || !openDoc) {
      setDocSearchMatchCount(0)
      return
    }
    const matches = Array.from(root.querySelectorAll('mark.ictihat-doc-search-hit'))
    matches.forEach((element) => element.classList.remove('is-active'))
    setDocSearchMatchCount(matches.length)
    if (!matches.length) return
    const safeIndex = Math.min(docSearchActiveIndex, matches.length - 1)
    const activeElement = matches[safeIndex]
    activeElement.classList.add('is-active')
    const rootRect = root.getBoundingClientRect()
    const activeRect = activeElement.getBoundingClientRect()
    const targetScrollTop =
      root.scrollTop + (activeRect.top - rootRect.top) - root.clientHeight / 2 + activeRect.height / 2
    const maxScrollTop = Math.max(0, root.scrollHeight - root.clientHeight)
    root.scrollTo({
      top: Math.max(0, Math.min(targetScrollTop, maxScrollTop)),
      behavior: 'smooth',
    })
    if (safeIndex !== docSearchActiveIndex) {
      setDocSearchActiveIndex(safeIndex)
    }
  }, [docSearchActiveIndex, docSearchTerms, isDocFullscreen, openDoc, openDoc?.page])

  const clearFilters = useCallback(() => {
    activeSearchControllerRef.current?.abort()
    activeSearchControllerRef.current = null
    searchRequestIdRef.current += 1
    setQuery('')
    setDaire('')
    setKurum('')
    setEsasYil('')
    setEsasSira('')
    setKararYil('')
    setKararSira('')
    setTopK(20)
    setAiTopK(null)
    setError('')
    setGroups([])
    setItems([])
    setTruncated(false)
    setOpenDoc(null)
    setLoading(false)
    setHasSearched(false)
    setShowHistoryView(false)
  }, [])

  const cancelActiveSearch = useCallback(() => {
    activeSearchControllerRef.current?.abort()
    activeSearchControllerRef.current = null
    searchRequestIdRef.current += 1
    setLoading(false)
    setError('')
    setHasSearched(results.length > 0)
  }, [results.length])

  useEffect(() => {
    return () => {
      activeSearchControllerRef.current?.abort()
      activeSearchControllerRef.current = null
    }
  }, [])

  const executeSearch = useCallback(
    async ({ searchMode: nextSearchMode, query: nextQuery, topK: nextTopK, aiEffortTopK: nextAiEffortTopK, filters: nextFilters }) => {
      const filtersObj = nextFilters && typeof nextFilters === 'object' ? nextFilters : null
      const queryText = String(nextQuery || '')
      const resolvedTopK = Number(nextTopK) || 20
      // AI mode effort hint is OPTIONAL — only sent if user actively picked a chip.
      const resolvedAiEffortTopK = [5, 10, 15, 20].includes(Number(nextAiEffortTopK)) ? Number(nextAiEffortTopK) : null
      const currentValidationError = getFilterValidationError({
        esasYil: filtersObj?.esas_yil,
        esasSira: filtersObj?.esas_sira,
        kararYil: filtersObj?.karar_yil,
        kararSira: filtersObj?.karar_sira,
      })
      const canSearchNow = Boolean(
        queryText.trim() ||
          filtersObj?.daire ||
          (filtersObj?.esas_yil && filtersObj?.esas_sira) ||
          (filtersObj?.karar_yil && filtersObj?.karar_sira),
      )
      if (currentValidationError) {
        setError(currentValidationError)
        return
      }
      if (!canSearchNow) {
        setError('Arama için en az bir kriter girin.')
        return
      }
      activeSearchControllerRef.current?.abort()
      const controller = new AbortController()
      activeSearchControllerRef.current = controller
      const requestId = searchRequestIdRef.current + 1
      searchRequestIdRef.current = requestId
      setShowHistoryView(false)
      setHasSearched(true)
      setError('')
      setLoading(true)
      try {
        if (nextSearchMode === 'semantic' || nextSearchMode === 'keyword') {
          const endpoint = nextSearchMode === 'keyword' ? '/v1/ictihat/keyword_search' : '/v1/ictihat/search'
          const data = await request(endpoint, {
            method: 'POST',
            body: {
              query: queryText || null,
              filters: filtersObj,
              top_k: resolvedTopK,
              mode: 'decisions',
            },
            signal: controller.signal,
          })
          if (searchRequestIdRef.current !== requestId) return
          setGroups(Array.isArray(data.groups) ? data.groups : [])
          setItems([])
          setTruncated(false)
        } else {
          // AI / agent search — backend treats `top_k` as an OPTIONAL effort hint.
          // Omit it entirely when the user hasn't picked a chip so the agent runs
          // its default exhaustive protocol.
          const agentBody = {
            query: queryText || null,
            filters: filtersObj,
          }
          if (resolvedAiEffortTopK !== null) {
            agentBody.top_k = resolvedAiEffortTopK
          }
          const data = await request('/v1/ictihat/agent_search', {
            method: 'POST',
            body: agentBody,
            signal: controller.signal,
          })
          if (searchRequestIdRef.current !== requestId) return
          setItems(Array.isArray(data.items) ? data.items : [])
          setTruncated(Boolean(data?.truncated))
          setGroups([])
        }
        await loadHistory()
      } catch (e) {
        if (isAbortError(e)) return
        if (isInsufficientCreditsError(e)) {
          showCreditBanner(e)
          if (searchRequestIdRef.current !== requestId) return
          setError('')
          setGroups([])
          setItems([])
          setTruncated(false)
          return
        }
        if (searchRequestIdRef.current !== requestId) return
        setError(humanizeApiError(e, 'Arama başarısız'))
        setGroups([])
        setItems([])
        setTruncated(false)
      } finally {
        if (activeSearchControllerRef.current === controller) {
          activeSearchControllerRef.current = null
        }
        if (searchRequestIdRef.current === requestId) {
          setLoading(false)
        }
      }
    },
    [loadHistory, request, showCreditBanner],
  )

  const runSearch = useCallback(async () => {
    if (validationError) {
      setError(validationError)
      return
    }
    await executeSearch({
      searchMode,
      query,
      topK: effectiveTopK,
      aiEffortTopK: aiTopK,
      filters,
    })
  }, [aiTopK, effectiveTopK, executeSearch, filters, query, searchMode, validationError])

  const applyHistoryItem = useCallback(
    async (item) => {
      if (!item || typeof item !== 'object') return
      const nextSearchMode = ['ai', 'semantic', 'keyword'].includes(item.search_type) ? item.search_type : 'semantic'
      const nextFilters = item.filters && typeof item.filters === 'object' ? item.filters : null
      const nextQuery = String(item.query_text || '')
      const persistedTopK = Number(item.top_k)
      // For AI history, only tier values (5/10/15/20) are treated as a saved effort hint.
      // Anything else (e.g. an actual result count like 23) means "no hint was saved".
      const nextAiTopK =
        nextSearchMode === 'ai' && [5, 10, 15, 20].includes(persistedTopK) ? persistedTopK : null
      const nextTopK = nextSearchMode === 'ai'
        ? defaultTopKForMode(nextSearchMode, false)
        : persistedTopK || defaultTopKForMode(nextSearchMode, false)
      const nextKurum = normalizeKurum(nextFilters?.kurum)
      const nextDaire = String(nextFilters?.daire || '')

      setSearchMode(nextSearchMode)
      setQuery(nextQuery)
      setTopK(nextTopK)
      setAiTopK(nextAiTopK)
      setKurum(nextKurum)
      setDaire(nextDaire)
      setEsasYil(nextFilters?.esas_yil ? String(nextFilters.esas_yil) : '')
      setEsasSira(nextFilters?.esas_sira ? String(nextFilters.esas_sira) : '')
      setKararYil(nextFilters?.karar_yil ? String(nextFilters.karar_yil) : '')
      setKararSira(nextFilters?.karar_sira ? String(nextFilters.karar_sira) : '')
      setShowAdvanced(false)
      setOpenDoc(null)
      setDocError('')
      setShowHistoryView(false)

      await executeSearch({
        searchMode: nextSearchMode,
        query: nextQuery,
        topK: nextTopK,
        aiEffortTopK: nextAiTopK,
        filters: nextFilters,
      })
    },
    [executeSearch],
  )

  const deleteHistoryItem = useCallback(
    async (historyId) => {
      if (!historyId) return
      setHistoryBusyId(historyId)
      try {
        await request(`/v1/ictihat/history/${Number(historyId)}`, { method: 'DELETE' })
        setHistoryItems((prev) => prev.filter((item) => Number(item?.history_id) !== Number(historyId)))
      } catch {
        // Ignore: deleting history is best-effort for UI.
      } finally {
        setHistoryBusyId(null)
      }
    },
    [request],
  )

  const openDocument = useCallback(
    async (result) => {
      if (!result?.documentId) return
      setDocError('')
      setDocLoading(true)
      setOpenDoc({
        document_id: Number(result.documentId),
        citation: result.citation || 'Karar',
        court: result.court || '',
        reference: result.emsalKarar || '',
        date: result.decisionDateIso || result.doc?.karar?.tarih || '',
        doc: result.doc || null,
        page: '',
      })
      try {
        const data = await request(`/v1/ictihat/document/${Number(result.documentId)}`, {
          method: 'GET',
        })
        const page = normalizeIctihatDocumentText(data)
        const resolvedDoc = data?.doc && typeof data.doc === 'object' ? data.doc : result.doc || null
        setOpenDoc({
          document_id: Number(result.documentId),
          citation: result.citation || 'Karar',
          court: result.court || '',
          reference: result.emsalKarar || '',
          date: result.decisionDateIso || result.doc?.karar?.tarih || '',
          doc: resolvedDoc,
          page,
        })
      } catch (e) {
        if (isInsufficientCreditsError(e)) {
          showCreditBanner(e)
          setDocError('')
        } else {
          setDocError(humanizeApiError(e, 'Karar yüklenemedi'))
        }
      } finally {
        setDocLoading(false)
      }
    },
    [request, showCreditBanner],
  )

  useEffect(() => {
    function handleKeyDown(e) {
      if (!results.length) return
      const tag = String(e.target?.tagName || '').toLowerCase()
      if (tag === 'input' || tag === 'select' || tag === 'textarea') return
      if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp' && e.key !== 'Enter') return
      e.preventDefault()
      if (e.key === 'ArrowDown') {
        const nextIndex = Math.min(activeIndex + 1, results.length - 1)
        setActiveIndex(nextIndex)
        const next = results[nextIndex]
        if (next?.documentId) openDocument(next)
        return
      }
      if (e.key === 'ArrowUp') {
        const nextIndex = Math.max(activeIndex - 1, 0)
        setActiveIndex(nextIndex)
        const next = results[nextIndex]
        if (next?.documentId) openDocument(next)
        return
      }
      const current = results[Math.max(activeIndex, 0)]
      if (current?.documentId) openDocument(current)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [activeIndex, openDocument, results])

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard?.writeText(openDoc?.page || '')
      setCopyFeedback(true)
    } catch {
      setCopyFeedback(false)
    }
  }, [openDoc?.page])

  const handleDocScroll = useCallback((event) => {
    const scrollTop = event.currentTarget.scrollTop
    setShowScrollTop(scrollTop > 360)
  }, [])

  const scrollDocToTop = useCallback(() => {
    docTextRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  const jumpDocSearchMatch = useCallback(
    (direction) => {
      if (!docSearchMatchCount) return
      setDocSearchActiveIndex((prev) => {
        const base = Number.isFinite(prev) ? prev : 0
        return (base + direction + docSearchMatchCount) % docSearchMatchCount
      })
    },
    [docSearchMatchCount],
  )

  const toggleSelected = useCallback((result) => {
    const did = Number(result?.documentId)
    if (!Number.isFinite(did) || did <= 0) return
    const payload = buildSelectedIctihatPayload(result?.doc)
    if (!payload) return
    setSelectedById((prev) => {
      const next = { ...(prev || {}) }
      if (next[did]) {
        delete next[did]
      } else {
        next[did] = payload
      }
      return next
    })
  }, [])

  const clearSelected = useCallback(() => setSelectedById({}), [])

  const docViewerContent = openDoc ? (
    <div className={`ictihat-doc${isDocFullscreen ? ' is-fullscreen' : ''}`}>
      {(() => {
        const metaLine = buildDecisionMetaLine(openDoc.doc, openDoc.date)
        const desktopKunyeLine = buildDecisionKunyeLine(openDoc.doc, openDoc.court, openDoc.citation, openDoc.date)
        const mobileHeading = buildMobileDecisionHeading(openDoc.court, openDoc.citation, openDoc.date)
        return (
      <div className={`ictihat-doc-head${isDocCondensed && !isDocFullscreen ? ' is-condensed' : ''}`}>
        <div className="ictihat-doc-head-main">
          {isMobile && !isDocFullscreen ? (
            <Button variant="unstyled" size="unstyled" className="ictihat-doc-mobile-back" type="button" onClick={() => setOpenDoc(null)} aria-label="Sonuçlara dön">
              <span className="ictihat-viewer-back-glyph" aria-hidden="true">
                ‹
              </span>
              <span>Geri</span>
            </Button>
          ) : null}
          <div className="ictihat-doc-meta">
            {isDocFullscreen ? (
              <div className="ictihat-doc-inline-head">
                <span className="ictihat-doc-label">Karar metni</span>
                <span className="ictihat-doc-inline-meta is-kunye">
                  {desktopKunyeLine}
                </span>
              </div>
            ) : (
              <>
                {!isMobile ? (
                  <div className="ictihat-doc-compact-meta">
                    <div className="ictihat-doc-compact-line">
                      <span className="ictihat-doc-title-inline">Karar metni</span>
                      <span className="ictihat-doc-inline-separator">-</span>
                      <span className="ictihat-doc-inline-meta">
                        {openDoc.court || String(openDoc.citation || '').split('›')[0].trim() || openDoc.citation}
                      </span>
                    </div>
                    {metaLine ? (
                      <div className="ictihat-doc-compact-line is-secondary">
                        <span className="ictihat-doc-inline-meta is-kunye">
                          {metaLine}
                        </span>
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <>
                    <div className="ictihat-doc-title ictihat-doc-title-mobile">{mobileHeading}</div>
                  </>
                )}
                {!isMobile && openDoc.citation && !openDoc.reference && openDoc.citation !== openDoc.court ? (
                  <div className="ictihat-doc-subtitle">{openDoc.citation}</div>
                ) : null}
              </>
            )}
          </div>
          <div className="ictihat-doc-actions">
            <Button
              variant="unstyled"
              size="unstyled"
              className={`ictihat-copy-btn${copyFeedback ? ' is-success' : ''}${isMobile && !isDocFullscreen ? ' is-icon-only' : ''}`}
              type="button"
              onClick={handleCopy}
              aria-label={copyFeedback ? 'Kopyalandı' : 'Kopyala'}
            >
              <span className="ictihat-copy-glyph" aria-hidden="true" />
              {!isMobile || isDocFullscreen ? (copyFeedback ? 'Kopyalandı' : 'Kopyala') : null}
            </Button>
            {!isDocFullscreen && !isMobile ? (
              <Button variant="unstyled" size="unstyled" className="ictihat-doc-control-btn" type="button" onClick={() => setIsDocFullscreen(true)}>
                Tam ekran
              </Button>
            ) : null}
            {isDocFullscreen ? (
              <Button variant="unstyled" size="unstyled" className="ictihat-doc-close-btn" type="button" onClick={() => setIsDocFullscreen(false)} aria-label="Tam ekrandan çık">
                <span aria-hidden="true">×</span>
              </Button>
            ) : null}
          </div>
        </div>
        <div className="ictihat-doc-searchbar">
          <div className="ictihat-doc-search-input-wrap">
            <span className="ictihat-doc-search-icon" aria-hidden="true" />
            <Input
              unstyled
              className="ictihat-doc-search-input"
              type="text"
              value={docSearchQuery}
              onChange={(event) => setDocSearchQuery(event.target.value)}
              placeholder="Karar metni içinde ara"
            />
          </div>
          <div className="ictihat-doc-search-status">{docSearchQuery ? `${docSearchMatchCount ? docSearchActiveIndex + 1 : 0}/${docSearchMatchCount}` : '0/0'}</div>
          <div className="ictihat-doc-search-actions">
            <Button variant="unstyled" size="unstyled" className="ictihat-doc-search-btn" type="button" onClick={() => jumpDocSearchMatch(-1)} disabled={!docSearchMatchCount}>
              ↑
            </Button>
            <Button variant="unstyled" size="unstyled" className="ictihat-doc-search-btn" type="button" onClick={() => jumpDocSearchMatch(1)} disabled={!docSearchMatchCount}>
              ↓
            </Button>
          </div>
        </div>
      </div>
        )
      })()}
      {docError ? <div className="error small">{docError}</div> : null}
      <div ref={docTextRef} className="ictihat-doc-text" onScroll={handleDocScroll}>
        {renderDocumentContent(openDoc.page, keywordHighlightTerms, docSearchTerms, {
          structured: !shouldSkipStructuredDocumentParsing(openDoc.doc, openDoc.court),
        })}
      </div>
      {copyFeedback ? <div className="ictihat-copy-toast">Karar metni kopyalandı</div> : null}
      {isMobile && showScrollTop && !isDocFullscreen ? (
        <Button variant="unstyled" size="unstyled" className="ictihat-scroll-top" type="button" onClick={scrollDocToTop}>
          ↑ Yukarı çık
        </Button>
      ) : null}
    </div>
  ) : null

  const openAttachModal = useCallback(async () => {
    if (!selectedCount) return
    setAttachOpen(true)
    setAttachError('')
    setAttachLoading(true)
    try {
      const data = await request('/v1/chat/list', { method: 'POST', body: { limit: 50, offset: 0 } })
      setAttachChats(Array.isArray(data?.chats) ? data.chats : [])
    } catch (e) {
      if (isInsufficientCreditsError(e)) {
        showCreditBanner(e)
        setAttachError('')
      } else {
        setAttachError(humanizeApiError(e, 'Sohbetler yüklenemedi'))
      }
      setAttachChats([])
    } finally {
      setAttachLoading(false)
    }
  }, [request, selectedCount, showCreditBanner])

  const attachToChatAndOpen = useCallback(
    (chatId) => {
      const payload = selectedList.filter((x) => x && typeof x === 'object')
      if (!payload.length) return
      setAttachOpen(false)
      setAttachError('')
      const state = { selectedIctihats: payload }
      if (chatId) {
        navigate(`/chat/${chatId}`, { state })
      } else {
        navigate('/chat', { state })
      }
    },
    [navigate, selectedList],
  )

  useEffect(() => {
    if (!attachOpen) return undefined
    function onKeyDown(e) {
      if (e.key === 'Escape') setAttachOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [attachOpen])

  const advancedFields = (
    <div className="ictihat-ek">
      {isMobile ? (
        <div className="ictihat-field-group">
          <div className="ictihat-group-title">Mahkeme & Daire</div>
          <div className="ictihat-court-filters is-stack">
            <Select
              value={kurum}
              onValueChange={(value) => {
                setKurum(String(value || ''))
                setDaire('')
              }}
            >
              <SelectTrigger className="input">
                <SelectValue placeholder="Mahkeme" />
              </SelectTrigger>
              <SelectContent>
                {kurumOptions.map((k) => (
                  <SelectItem key={k} value={k}>
                    {getCourtDisplayName(k) || k}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={daire}
              onValueChange={(value) => setDaire(String(value || ''))}
              disabled={!kurum || filteredDaireOptions.length === 0}
            >
              <SelectTrigger className="input">
                <SelectValue placeholder="Daire" />
              </SelectTrigger>
              <SelectContent>
                {filteredDaireOptions.map((o) => {
                  const stripped = stripKurumPrefixFromDaire(o.daire_label || o.daire, o.kurum)
                  return (
                    <SelectItem key={o.key} value={o.daire}>
                      {stripped || o.daire}
                    </SelectItem>
                  )
                })}
              </SelectContent>
            </Select>
          </div>
        </div>
      ) : null}
      {isMobile && searchMode !== 'ai' ? (
        <div className="ictihat-field-group">
          <div className="ictihat-group-title">Göster</div>
          <div className="ictihat-display-controls">
            <div className="ictihat-topk-chips" role="group" aria-label="Sonuç sayısı">
              {[5, 10, 20, 50, 100].map((value) => (
                <Button
                  variant="unstyled"
                  size="unstyled"
                  key={value}
                  className={`ictihat-chip-button${Number(topK) === value ? ' is-active' : ''}`}
                  type="button"
                  onClick={() => setTopK(value)}
                >
                  {value}
                </Button>
              ))}
            </div>
          </div>
        </div>
      ) : null}
      {isMobile && searchMode === 'ai' ? (
        <div className="ictihat-field-group">
          <div className="ictihat-group-title">AI Efor (opsiyonel)</div>
          <div className="ictihat-display-controls">
            <div className="ictihat-topk-chips" role="group" aria-label="AI hedef sonuç sayısı">
              {[5, 10, 15, 20].map((value) => (
                <Button
                  variant="unstyled"
                  size="unstyled"
                  key={value}
                  className={`ictihat-chip-button${Number(aiTopK) === value ? ' is-active' : ''}`}
                  type="button"
                  title={
                    value === 5
                      ? 'Hızlı — 2–3 tool çağrısı, sadece en güçlü 5 karar'
                      : value === 10
                        ? 'Standart — ~10 karar, ağırlıklı 5★/4★'
                        : value === 15
                          ? 'Geniş — ~15 karar, 5★→2★ karışım'
                          : 'Kapsamlı — tam protokol, ~20 karar'
                  }
                  onClick={() => setAiTopK((prev) => (prev === value ? null : value))}
                >
                  {value}
                </Button>
              ))}
            </div>
          </div>
          <div className="muted small ictihat-ai-effort-hint">
            Seçim yapmazsanız yapay zeka kendisi karar verecektir.
          </div>
        </div>
      ) : null}
      <div className="ictihat-field-group">
        <div className="ictihat-group-title">Esas Bilgileri</div>
        <div className="ictihat-group-grid">
          <div className="ictihat-field">
            <Label unstyled className="ictihat-field-label" htmlFor="esas-yil">
              Yıl
            </Label>
            <Input unstyled id="esas-yil" className="input" value={esasYil} onChange={(e) => setEsasYil(e.target.value)} placeholder="2014" />
          </div>
          <div className="ictihat-field">
            <Label unstyled className="ictihat-field-label" htmlFor="esas-no">
              No
            </Label>
            <Input unstyled id="esas-no" className="input" value={esasSira} onChange={(e) => setEsasSira(e.target.value)} placeholder="1089" />
          </div>
        </div>
      </div>
      <div className="ictihat-field-group">
        <div className="ictihat-group-title">Karar Bilgileri</div>
        <div className="ictihat-group-grid">
          <div className="ictihat-field">
            <Label unstyled className="ictihat-field-label" htmlFor="karar-yil">
              Yıl
            </Label>
            <Input unstyled id="karar-yil" className="input" value={kararYil} onChange={(e) => setKararYil(e.target.value)} placeholder="2014" />
          </div>
          <div className="ictihat-field">
            <Label unstyled className="ictihat-field-label" htmlFor="karar-no">
              No
            </Label>
            <Input unstyled id="karar-no" className="input" value={kararSira} onChange={(e) => setKararSira(e.target.value)} placeholder="1089" />
          </div>
        </div>
      </div>
    </div>
  )

  return (
    <div className={`ictihat-page${isCompactMobileSearch ? ' is-mobile-results' : ''}`}>
      {!isMobile || !openDoc ? (
        <>
          <div className={`ictihat-header${isCompactMobileSearch ? ' is-compact' : ''}`}>
            <div className="ictihat-header-row">
              <div className="ictihat-brand-stack">
                <Link className="ictihat-brand ictihat-brand-home" to="/chat" aria-label="Sohbete dön">
                  <span className="ictihat-brand-chevron" aria-hidden="true">
                    <svg viewBox="0 0 24 24" focusable="false">
                      <path
                        d="M15 6l-6 6 6 6"
                        fill="none"
                        stroke="currentColor"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="1.9"
                      />
                    </svg>
                  </span>
                  <img className="ictihat-brand-logo" src={yargucuLogo} alt="Yargucu" />
                </Link>
              </div>
              <div className="ictihat-heading">
                <div className="ictihat-title-wrap">
                  <div className="ictihat-title">İçtihat Arama</div>
                  {!isCompactMobileSearch ? <span className="ictihat-title-separator">-</span> : null}
                  {!isCompactMobileSearch ? <p className="ictihat-subtitle">Yapay zeka destekli içtihat araması</p> : null}
                </div>
              </div>
            </div>
          </div>

          <form
            className={`ictihat-filters${isCompactMobileSearch ? ' is-compact' : ''}`}
            onSubmit={(e) => {
              e.preventDefault()
              if (loading) {
                cancelActiveSearch()
                return
              }
              runSearch()
            }}
          >
            <div className="ictihat-filter-main">
              {isCompactMobileSearch ? (
                <Button
                  variant="unstyled"
                  size="unstyled"
                  className="ictihat-mobile-filter-trigger is-inline is-icon"
                  type="button"
                  aria-label="İçtihat ana ekrana dön"
                  onClick={clearFilters}
                >
                  <span className="ictihat-back-glyph" aria-hidden="true">
                    ‹
                  </span>
                </Button>
              ) : null}
              {!isCompactMobileSearch ? (
                <Tabs unstyled value={searchMode} className="ictihat-mode-toggle-wrap">
                  <TabsList unstyled className="ictihat-mode-toggle" aria-label="Arama türü">
                  <TabsTrigger
                    unstyled
                    value="ai"
                    className={`ictihat-mode-option${searchMode === 'ai' ? ' is-active' : ''}`}
                    onClick={() => {
                      activeSearchControllerRef.current?.abort()
                      activeSearchControllerRef.current = null
                      searchRequestIdRef.current += 1
                      setSearchMode('ai')
                      setError('')
                      setGroups([])
                      setItems([])
                      setTruncated(false)
                      setOpenDoc(null)
                      setDocError('')
                      setLoading(false)
                      setHasSearched(false)
                    }}
                  >
                    AI Arama
                  </TabsTrigger>
                  <TabsTrigger
                    unstyled
                    value="semantic"
                    className={`ictihat-mode-option${searchMode === 'semantic' ? ' is-active' : ''}`}
                    onClick={() => {
                      activeSearchControllerRef.current?.abort()
                      activeSearchControllerRef.current = null
                      searchRequestIdRef.current += 1
                      setSearchMode('semantic')
                      setError('')
                      setGroups([])
                      setItems([])
                      setTruncated(false)
                      setOpenDoc(null)
                      setDocError('')
                      setLoading(false)
                      setHasSearched(false)
                    }}
                  >
                    Anlamsal
                  </TabsTrigger>
                  <TabsTrigger
                    unstyled
                    value="keyword"
                    className={`ictihat-mode-option ictihat-mode-option-keyword${searchMode === 'keyword' ? ' is-active' : ''}`}
                    onClick={() => {
                      activeSearchControllerRef.current?.abort()
                      activeSearchControllerRef.current = null
                      searchRequestIdRef.current += 1
                      setSearchMode('keyword')
                      setError('')
                      setGroups([])
                      setItems([])
                      setTruncated(false)
                      setOpenDoc(null)
                      setDocError('')
                      setLoading(false)
                      setHasSearched(false)
                    }}
                  >
                    Kelime Bazlı
                  </TabsTrigger>
                  </TabsList>
                </Tabs>
              ) : null}
              <div ref={searchInfoRef} className={`ictihat-query-wrap${searchInfoOpen ? ' is-info-open' : ''}`}>
                <Textarea
                  unstyled
                  ref={queryInputRef}
                  className="input ictihat-query-input"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey && !isMobile) {
                      e.preventDefault()
                      if (loading) {
                        cancelActiveSearch()
                        return
                      }
                      const form = e.target.closest('form')
                      if (form) {
                        if (typeof form.requestSubmit === 'function') {
                          form.requestSubmit()
                        } else {
                          form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }))
                        }
                      }
                    }
                  }}
                  placeholder={currentSearchModeUi.placeholder}
                  rows={1}
                  style={{
                    resize: 'none',
                    overflowY: 'auto',
                    minHeight: '52px',
                    paddingTop: '16px',
                    paddingBottom: '16px',
                    lineHeight: '20px'
                  }}
                />
                <Button
                  variant="unstyled"
                  size="unstyled"
                  className={`ictihat-query-info-btn${searchInfoOpen ? ' is-active' : ''}`}
                  type="button"
                  aria-label="Arama yardımı"
                  aria-expanded={searchInfoOpen}
                  onClick={() => setSearchInfoOpen((prev) => !prev)}
                  style={{ top: '12px', transform: 'none' }}
                >
                  i
                </Button>
                {searchInfoOpen ? (
                  <div className="ictihat-query-info-popover" role="dialog" aria-label="Arama bilgisi">
                    <div className="ictihat-query-info-title">
                      {searchMode === 'ai' ? 'AI Arama' : searchMode === 'semantic' ? 'Anlamsal Arama' : 'Kelime Bazlı Arama'}
                    </div>
                    <div className="ictihat-query-info-text">{currentSearchModeUi.info}</div>
                    <div className="ictihat-query-info-example">{currentSearchModeUi.example}</div>
                  </div>
                ) : null}
              </div>
              {!isMobile ? (
                <div className="ictihat-court-filters">
                  <Select
                    value={kurum}
                    onValueChange={(value) => {
                      setKurum(String(value || ''))
                      setDaire('')
                    }}
                  >
                    <SelectTrigger className="input">
                      <SelectValue placeholder="Mahkeme" />
                    </SelectTrigger>
                    <SelectContent>
                      {kurumOptions.map((k) => (
                        <SelectItem key={k} value={k}>
                          {getCourtDisplayName(k) || k}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Select
                    value={daire}
                    onValueChange={(value) => setDaire(String(value || ''))}
                    disabled={!kurum || filteredDaireOptions.length === 0}
                  >
                    <SelectTrigger className="input">
                      <SelectValue placeholder="Daire" />
                    </SelectTrigger>
                    <SelectContent>
                      {filteredDaireOptions.map((o) => {
                        const stripped = stripKurumPrefixFromDaire(o.daire_label || o.daire, o.kurum)
                        return (
                          <SelectItem key={o.key} value={o.daire}>
                            {stripped || o.daire}
                          </SelectItem>
                        )
                      })}
                    </SelectContent>
                  </Select>
                </div>
              ) : null}
              {isMobile ? (
                <Button
                  variant="unstyled"
                  size="unstyled"
                  className="ictihat-mobile-filter-trigger is-inline is-icon"
                  type="button"
                  aria-label={activeFilterCount ? `Filtreler, ${activeFilterCount} aktif filtre` : 'Filtreler'}
                  onClick={() => {
                    setShowHistoryView(false)
                    setShowAdvanced((prev) => !prev)
                  }}
                >
                  <span className="ictihat-filter-glyph" aria-hidden="true" />
                  {activeFilterCount ? <span className="ictihat-filter-badge">{activeFilterCount}</span> : null}
                </Button>
              ) : null}
              {isMobile ? (
                <Button
                  variant="unstyled"
                  size="unstyled"
                  className={`ictihat-mobile-filter-trigger ictihat-mobile-history-trigger is-inline is-icon${showHistoryView ? ' is-active' : ''}`}
                  type="button"
                  aria-label="Geçmiş"
                  title="Geçmiş"
                  onClick={() => {
                    setShowAdvanced(false)
                    setOpenDoc(null)
                    setShowHistoryView((prev) => {
                      const next = !prev
                      if (next) setHistoryPage(1)
                      return next
                    })
                  }}
                >
                  <History size={16} />
                </Button>
              ) : null}
              <Button
                variant="unstyled"
                size="unstyled"
                className={`btn ictihat-search-btn${loading ? ' is-loading' : ''}`}
                type="submit"
                disabled={!loading && !canSearch}
                aria-label={loading ? 'Aramayı iptal et' : isCompactMobileSearch ? 'Ara' : undefined}
                title={loading ? 'Aramayı iptal et' : 'Ara'}
              >
                {loading ? (
                  <>
                    <span className="ictihat-search-cancel-indicator" aria-hidden="true">
                      <span className="ictihat-search-cancel-pulse" />
                      <span className="ictihat-search-cancel-core">
                        <X size={12} strokeWidth={2.4} />
                      </span>
                    </span>
                    {isCompactMobileSearch ? '' : 'Durdur'}
                  </>
                ) : (
                  <>
                    <span className="ictihat-search-glyph" aria-hidden="true" />
                    {isCompactMobileSearch ? '' : 'Ara'}
                  </>
                )}
              </Button>
            </div>
            {!isCompactMobileSearch ? (
              <div className="ictihat-filter-secondary">
                {isMobile ? (
                  (hasAnyFilters || query.trim()) ? (
                    <div className="ictihat-mobile-actions">
                      <Button variant="unstyled" size="unstyled" className="ictihat-header-link" type="button" onClick={clearFilters}>
                        Temizle
                      </Button>
                    </div>
                  ) : null
                ) : (
                  <div className="ictihat-filter-actions">
                    <Button
                      variant="unstyled"
                      size="unstyled"
                      className={`ictihat-header-link ictihat-history-link${showHistoryView ? ' is-active' : ''}`}
                      type="button"
                      onClick={() => {
                        setShowAdvanced(false)
                        setOpenDoc(null)
                        setShowHistoryView((prev) => {
                          const next = !prev
                          if (next) setHistoryPage(1)
                          return next
                        })
                      }}
                    >
                      Geçmiş
                    </Button>
                    <div className="ictihat-filter-actions-right">
                      {searchMode !== 'ai' ? (
                        <div className="ictihat-display-controls">
                          <span className="ictihat-results-label">Göster:</span>
                          <div className="ictihat-topk-chips" role="group" aria-label="Sonuç sayısı">
                            {[5, 10, 20, 50, 100].map((value) => (
                              <Button
                                variant="unstyled"
                                size="unstyled"
                                key={value}
                                className={`ictihat-chip-button${Number(topK) === value ? ' is-active' : ''}`}
                                type="button"
                                onClick={() => setTopK(value)}
                              >
                                {value}
                              </Button>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <div
                          className="ictihat-display-controls"
                          title="Seçim yapmazsanız yapay zeka kendisi karar verecektir."
                        >
                          <span className="ictihat-results-label">AI Efor:</span>
                          <div className="ictihat-topk-chips" role="group" aria-label="AI hedef sonuç sayısı">
                            {[5, 10, 15, 20].map((value) => (
                              <Button
                                variant="unstyled"
                                size="unstyled"
                                key={value}
                                className={`ictihat-chip-button${Number(aiTopK) === value ? ' is-active' : ''}`}
                                type="button"
                                title={
                                  value === 5
                                    ? 'Hızlı — 2–3 tool çağrısı, sadece en güçlü 5 karar'
                                    : value === 10
                                      ? 'Standart — ~10 karar, ağırlıklı 5★/4★'
                                      : value === 15
                                        ? 'Geniş — ~15 karar, 5★→2★ karışım'
                                        : 'Kapsamlı — tam protokol, ~20 karar'
                                }
                                onClick={() => setAiTopK((prev) => (prev === value ? null : value))}
                              >
                                {value}
                              </Button>
                            ))}
                          </div>
                        </div>
                      )}
                      <Button variant="unstyled" size="unstyled" className="ictihat-header-link" type="button" onClick={() => setShowAdvanced((prev) => !prev)}>
                        {showAdvanced ? 'Gelişmiş filtreleri gizle' : 'Gelişmiş filtreler'}
                      </Button>
                      {(hasAnyFilters || query.trim()) && (
                        <Button variant="unstyled" size="unstyled" className="ictihat-header-link" type="button" onClick={clearFilters}>
                          Temizle
                        </Button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ) : null}
            {showAdvanced && !isMobile ? <div className="ictihat-ek-wrap">{advancedFields}</div> : null}
            {validationError ? <div className="error small">{validationError}</div> : null}
            {error ? <div className="error small">{error}</div> : null}
            {creditBanner?.message ? (
              <div className="mt-3">
                <CreditBanner
                  title={creditBanner?.title}
                  message={creditBanner?.message}
                  compactMessage={creditBanner?.compactMessage}
                  actionLabel="Kredi yükle"
                  onAction={() => navigate('/settings', { state: { activeKey: 'payment' } })}
                  contextual
                />
              </div>
            ) : null}
          </form>
        </>
      ) : null}

      {showAdvanced && isMobile ? (
        <Dialog open={showAdvanced && isMobile} onOpenChange={setShowAdvanced}>
          <DialogOverlay className="ictihat-mobile-sheet-backdrop" aria-label="Filtreleri kapat" />
          <DialogContent className="ictihat-mobile-sheet" aria-label="Filtreler">
            <div className="ictihat-mobile-sheet-handle" />
            <div className="ictihat-mobile-sheet-header">
              <Button variant="unstyled" size="unstyled" className="ictihat-mobile-sheet-back" type="button" onClick={() => setShowAdvanced(false)}>
                ← Geri
              </Button>
              <div className="ictihat-empty-title">Filtreler</div>
              <Button variant="unstyled" size="unstyled" className="ictihat-header-link" type="button" onClick={clearFilters}>
                Temizle
              </Button>
            </div>
            {advancedFields}
            <Button variant="unstyled" size="unstyled" className="btn ictihat-mobile-apply" type="button" onClick={() => setShowAdvanced(false)}>
              Uygula
            </Button>
          </DialogContent>
        </Dialog>
      ) : null}

      {!showHistoryView && !isInitialState && (!isMobile || !openDoc) ? (
        <div className="ictihat-results-overview">
          <span className="ictihat-results-count">
            {isLoadingState ? (
              'Aranıyor...'
            ) : (
              <>
                <strong>{results.length}</strong> sonuç bulundu
              </>
            )}
            {truncated ? ' (kısaltılmış)' : ''}
          </span>
          {selectedCount ? (
            <div className="ictihat-selection-actions">
              <span className="muted small">{selectedCount} seçili</span>
              <Button variant="unstyled" size="unstyled" className="btn ictihat-attach-btn" type="button" onClick={openAttachModal}>
                Chate ekle
              </Button>
              <Button variant="unstyled" size="unstyled" className="ictihat-header-link" type="button" onClick={clearSelected}>
                Temizle
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}

      {showHistoryView ? (
        <div className="ictihat-history-page">
          <div className="ictihat-history-head">
            <div>
              <div className="ictihat-history-title">Arama Geçmişi</div>
              <div className="ictihat-history-meta">
                {historyLoading ? 'Yükleniyor...' : `${historyItems.length} kayıt`}
              </div>
            </div>
            <div className="ictihat-history-head-actions">
              <Button variant="unstyled" size="unstyled" className="ictihat-header-link" type="button" onClick={() => setShowHistoryView(false)}>
                Aramaya dön
              </Button>
            </div>
          </div>
          {!historyLoading && !historyItems.length ? (
            <div className="ictihat-empty">
              <div className="ictihat-empty-title">Geçmiş bulunamadı</div>
              <div className="muted small">Yaptığınız içtihat aramaları burada listelenecek.</div>
            </div>
          ) : null}
          {historyLoading ? (
            <div className="ictihat-history-loading muted small">Geçmiş yükleniyor...</div>
          ) : null}
          {!historyLoading && paginatedHistoryItems.length ? (
            <>
              <div className="ictihat-history-list is-page">
                {paginatedHistoryItems.map((item) => {
                  const historyId = Number(item?.history_id)
                  const filterSummary = buildHistoryFilterSummary(item?.filters)
                  const searchTypeLabel = SEARCH_MODE_LABELS[item?.search_type] || 'Arama'
                  const createdAtLabel = formatHistoryTimestamp(item?.created_at)
                  return (
                    <Card
                      unstyled
                      key={historyId}
                      className="ictihat-history-item"
                      role="button"
                      tabIndex={0}
                      onClick={() => applyHistoryItem(item)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault()
                          applyHistoryItem(item)
                        }
                      }}
                    >
                      <div className="ictihat-history-item-top">
                        <span className={`ictihat-history-type is-${item?.search_type || 'semantic'}`}>{searchTypeLabel}</span>
                        <span className="ictihat-history-meta">
                          {item?.result_count || 0} sonuç{createdAtLabel ? ` · ${createdAtLabel}` : ''}
                        </span>
                      </div>
                      <div className="ictihat-history-query">{buildHistoryTitle(item)}</div>
                      {filterSummary && filterSummary !== buildHistoryTitle(item) ? (
                        <div className="ictihat-history-filters">{filterSummary}</div>
                      ) : null}
                      <div className="ictihat-history-actions">
                        <Button
                          variant="unstyled"
                          size="unstyled"
                          className="ictihat-history-replay ictihat-history-action-btn"
                          type="button"
                          aria-label="Tekrar ara"
                          title="Tekrar ara"
                          onClick={(event) => {
                            event.preventDefault()
                            event.stopPropagation()
                            applyHistoryItem(item)
                          }}
                        >
                          <RotateCcw size={14} />
                        </Button>
                        <Button
                          variant="unstyled"
                          size="unstyled"
                          className="ictihat-history-delete"
                          type="button"
                          disabled={historyBusyId === historyId}
                          aria-label="Sil"
                          title="Sil"
                          onClick={(event) => {
                            event.preventDefault()
                            event.stopPropagation()
                            deleteHistoryItem(historyId)
                          }}
                        >
                          <Trash2 size={14} />
                        </Button>
                      </div>
                    </Card>
                  )
                })}
              </div>
              <div className="ictihat-history-pagination">
                <Button
                  variant="unstyled"
                  size="unstyled"
                  className="ictihat-history-page-btn"
                  type="button"
                  disabled={historyPage <= 1}
                  onClick={() => setHistoryPage((prev) => Math.max(1, prev - 1))}
                >
                  Önceki
                </Button>
                <div className="ictihat-history-page-meta">
                  Sayfa {historyPage} / {historyPageCount}
                </div>
                <Button
                  variant="unstyled"
                  size="unstyled"
                  className="ictihat-history-page-btn"
                  type="button"
                  disabled={historyPage >= historyPageCount}
                  onClick={() => setHistoryPage((prev) => Math.min(historyPageCount, prev + 1))}
                >
                  Sonraki
                </Button>
              </div>
            </>
          ) : null}
        </div>
      ) : null}

      {!showHistoryView ? <div className="ictihat-body">
        {(!isMobile || !openDoc) ? (
        <div className={`ictihat-results${isLoadingState && searchMode === 'ai' ? ' is-loading-ai' : ''}`}>
          {isInitialState ? (
            <div className="ictihat-panel-note">Sonuçlar burada listelenecek.</div>
          ) : null}
          {isLoadingState ? (
            searchMode === 'ai' ? (
              <div className="ictihat-results-animation-shell">
                <DotLottieReact
                  src={ictihatSearchAnimation}
                  loop
                  autoplay
                  className="ictihat-results-animation"
                />
              </div>
            ) : (
              <div className="ictihat-loading-list" aria-live="polite" aria-label="Arama sonuçları yükleniyor">
                {[0, 1, 2].map((item) => (
                  <div key={item} className="ictihat-skeleton-card">
                    <div className="ictihat-skeleton-line is-short" />
                    <div className="ictihat-skeleton-line is-medium" />
                    <div className="ictihat-skeleton-line" />
                    <div className="ictihat-skeleton-line is-fade" />
                    <div className="ictihat-skeleton-chip-row">
                      <span className="ictihat-skeleton-chip" />
                      <span className="ictihat-skeleton-chip" />
                    </div>
                  </div>
                ))}
              </div>
            )
          ) : null}
          {isEmptyState ? (
            <div className="ictihat-empty">
              <div className="ictihat-empty-title">Sonuç bulunamadı</div>
              <div className="muted small">Daha genel bir anahtar kelime deneyin veya filtreleri temizleyin.</div>
              <Button variant="unstyled" size="unstyled" className="ictihat-empty-action" type="button" onClick={clearFilters}>
                Filtreleri temizle
              </Button>
            </div>
          ) : null}
          {truncated && isResultsState ? <div className="muted small">Daha fazla sonuç var; liste kısaltıldı.</div> : null}
          {isResultsState
            ? results.map((result, index) => {
                const active = openDoc?.document_id === Number(result.documentId)
                const highlighted = activeIndex === index
                const did = Number(result.documentId)
                const isSelected = Boolean(did && selectedById?.[did])
                return (
                  <Card
                    unstyled
                    key={String(result.documentId)}
                    className={`ictihat-card${active ? ' is-active' : ''}${highlighted ? ' is-keyboard' : ''}`}
                    onMouseEnter={() => setActiveIndex(index)}
                    onFocus={() => setActiveIndex(index)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        openDocument(result)
                      }
                    }}
                    onClick={() => openDocument(result)}
                  >
                    {result.tier ? (() => {
                      const filledStars = result.tier
                      const tierLabel =
                        filledStars === 5
                          ? 'Birebir örtüşen karar — en yüksek alaka'
                          : filledStars === 4
                            ? 'Güçlü emsal — aynı madde + aynı olay deseni'
                            : filledStars === 3
                              ? 'Yakın emsal — aynı hukuki mesele'
                              : filledStars === 2
                                ? 'Konsept paraleli — ilke/kıstas yakınlığı'
                                : 'Marjinal ilinti — arka plan / perspektif'
                      return (
                        <div
                          className={`ictihat-tier-bar is-tier-${filledStars}`}
                          role="img"
                          aria-label={`Alaka seviyesi ${filledStars}/5 yıldız — ${tierLabel}`}
                          title={tierLabel}
                        >
                          {[1, 2, 3, 4, 5].map((idx) => (
                            <Star
                              key={idx}
                              className={`ictihat-tier-star${idx <= filledStars ? ' is-on' : ''}`}
                              aria-hidden="true"
                            />
                          ))}
                        </div>
                      )
                    })() : null}
                    <div className="ictihat-card-court">{result.court}</div>
                    <div className="ictihat-citation" title={result.referenceFull || result.reference}>
                      {result.reference}
                    </div>
                    {result.snippet ? <div className="ictihat-snippet">{result.snippet}</div> : null}
                    {result.why ? <div className="muted small">{result.why}</div> : null}
                    <div className="ictihat-card-footer">
                      <div className="ictihat-chip-row">
                        {result.doc?.esas?.yil && result.doc?.esas?.sira ? (
                          <span className="ictihat-chip">
                            E: {result.doc.esas.yil}/{result.doc.esas.sira}
                          </span>
                        ) : null}
                        {result.doc?.karar?.yil && result.doc?.karar?.sira ? (
                          <span className="ictihat-chip">
                            K: {result.doc.karar.yil}/{result.doc.karar.sira}
                          </span>
                        ) : null}
                      </div>
                      {result.summary ? (
                        <Button
                          variant="unstyled"
                          size="unstyled"
                          className="ictihat-summary-pill"
                          type="button"
                          aria-label="Özeti göster"
                          title="Özeti göster"
                          onClick={(e) => {
                            e.preventDefault()
                            e.stopPropagation()
                            setSummaryData({
                              summary: result.summary,
                              why: result.why,
                              court: result.court,
                              reference: result.referenceFull || result.reference,
                              emsalKarar: result.emsalKarar,
                            })
                            setSummaryOpen(true)
                          }}
                        >
                          <span className="ictihat-summary-pill-dot" aria-hidden="true" />
                          <span>Özet</span>
                        </Button>
                      ) : null}
                      <Button
                        variant="unstyled"
                        size="unstyled"
                        className={`ictihat-select-toggle${isSelected ? ' is-on' : ''}`}
                        type="button"
                        aria-label={isSelected ? 'Seçimi kaldır' : 'Seç'}
                        title={isSelected ? 'Seçimi kaldır' : 'Seç'}
                        onClick={(e) => {
                          e.preventDefault()
                          e.stopPropagation()
                          toggleSelected(result)
                        }}
                      >
                        <span className="ictihat-select-box" aria-hidden="true" />
                        <span className="ictihat-select-label">{isSelected ? 'Seçildi' : 'Seç'}</span>
                      </Button>
                    </div>
                  </Card>
                )
              })
            : null}
        </div>
        ) : null}

        {(!isMobile || openDoc) ? (
        <div className="ictihat-viewer">
          {isInitialState && !isMobile ? (
            <div className="ictihat-panel-note">Karar metni burada görünecek.</div>
          ) : null}
          {isLoadingState && !openDoc ? (
            <div className="ictihat-empty">
              <div className="ictihat-empty-title">Karar metinleri aranıyor</div>
              <div className="muted small">Sonuçlardan bir karar seçtiğinizde detaylar burada görünecek.</div>
            </div>
          ) : null}
          {!isInitialState && !isLoadingState && !openDoc ? (
            <div className="ictihat-empty">
              <div className="muted small">Detayları görmek için soldan bir karar seçin.</div>
            </div>
          ) : null}
          {openDoc && !isDocFullscreen ? docViewerContent : null}
        </div>
        ) : null}
      </div> : null}

      {openDoc && isDocFullscreen ? (
        <Dialog open={Boolean(openDoc && isDocFullscreen)} onOpenChange={setIsDocFullscreen}>
          <DialogOverlay className="ictihat-doc-modal-backdrop" aria-label="Tam ekranı kapat" />
          <DialogContent className="ictihat-doc-modal" aria-label="Karar metni tam ekran">
            {docViewerContent}
          </DialogContent>
        </Dialog>
      ) : null}

      {summaryOpen ? (
        <Dialog open={summaryOpen} onOpenChange={setSummaryOpen}>
          <DialogOverlay className="ictihat-summary-backdrop" aria-label="Kapat" />
          <DialogContent className="ictihat-summary-modal" aria-label="Karar özeti">
            <div className="ictihat-summary-head">
              <div className="ictihat-summary-head-main">
                <div className="ictihat-summary-head-court">{summaryData?.court || 'Karar'}</div>
                {summaryData?.reference ? (
                  <div className="ictihat-summary-head-ref muted small">{summaryData.reference}</div>
                ) : null}
                {summaryData?.emsalKarar ? (
                  <div className="ictihat-summary-head-emsal muted small">{summaryData.emsalKarar}</div>
                ) : null}
              </div>
              <Button
                variant="unstyled"
                size="unstyled"
                className="ictihat-attach-close"
                type="button"
                onClick={() => setSummaryOpen(false)}
                aria-label="Kapat"
              >
                ×
              </Button>
            </div>
            <div className="ictihat-summary-body">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {String(summaryData?.summary || '')}
              </ReactMarkdown>
            </div>
          </DialogContent>
        </Dialog>
      ) : null}

      {attachOpen ? (
        <Dialog open={attachOpen} onOpenChange={setAttachOpen}>
          <DialogOverlay className="ictihat-attach-backdrop" aria-label="Kapat" />
          <DialogContent className="ictihat-attach-modal" aria-label="Sohbet seç">
            <div className="ictihat-attach-head">
              <div className="ictihat-attach-title">Sohbet seç</div>
              <Button variant="unstyled" size="unstyled" className="ictihat-attach-close" type="button" onClick={() => setAttachOpen(false)} aria-label="Kapat">
                ×
              </Button>
            </div>
            <div className="ictihat-attach-sub muted small">{selectedCount} içtihat seçili. Hangi sohbete ekleyelim?</div>
            {attachError ? <div className="error small">{attachError}</div> : null}
            <div className="ictihat-attach-actions">
              <Button variant="unstyled" size="unstyled" className="btn" type="button" onClick={() => attachToChatAndOpen(null)}>
                Yeni sohbet
              </Button>
            </div>
            <div className="ictihat-attach-list" role="list">
              {attachLoading ? <div className="muted small">Sohbetler yükleniyor...</div> : null}
              {!attachLoading && attachChats.length === 0 ? <div className="muted small">Sohbet bulunamadı</div> : null}
              {attachChats.map((c) => {
                const id = Number(c?.chat_id)
                if (!Number.isFinite(id) || id <= 0) return null
                return (
                  <Button
                    variant="unstyled"
                    size="unstyled"
                    key={id}
                    className="ictihat-attach-item"
                    type="button"
                    onClick={() => attachToChatAndOpen(id)}
                    title={String(c?.title || c?.first_message || '')}
                  >
                    {chatLabel(c)}
                  </Button>
                )
              })}
            </div>
          </DialogContent>
        </Dialog>
      ) : null}
    </div>
  )
}
