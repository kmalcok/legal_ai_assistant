import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowLeft, ChevronDown, ChevronUp, Clock3, Coins, DollarSign, MessageSquare, RefreshCcw } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { apiRequest } from '@/shared/api/client.js'
import { describeApiError } from '@/shared/api/contracts.js'
import { InlineBanner } from '@/shared/components/InlineBanner.jsx'
import yargucuLogoBlack from '@/logopack/yargucu-logo-siyah.svg'

const ACCOUNT_TYPE_LABELS = {
  standalone: 'Bağımsız',
  parent: 'Üst Hesap',
  child: 'Alt Hesap',
}

const ACCOUNT_PLAN_LABELS = {
  free: 'Ücretsiz',
  student: 'Öğrenci',
  starter: 'Başlangıç',
  standard: 'Standart',
  advanced: 'Gelişmiş',
  professional: 'Profesyonel',
  enterprise: 'Kurumsal',
}

const CONTROL =
  'h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-[15px] text-slate-900 shadow-sm shadow-slate-200/60 focus-visible:border-slate-400 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-slate-200/80'

function formatDate(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleString('tr-TR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatNumber(value, options) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '-'
  return num.toLocaleString('tr-TR', options)
}

function formatCredit(value) {
  return formatNumber(value, { maximumFractionDigits: 2 })
}

function formatUsd(value) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '-'
  return num.toLocaleString('tr-TR', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 4,
    maximumFractionDigits: 4,
  })
}

function getAccountTypeLabel(type) {
  return ACCOUNT_TYPE_LABELS[String(type || '').trim().toLowerCase()] || 'Hesap'
}

function getAccountPlanLabel(plan) {
  return ACCOUNT_PLAN_LABELS[String(plan || '').trim().toLowerCase()] || 'Ücretsiz'
}

function getUsageSummary(usage) {
  const data = usage && typeof usage === 'object' ? usage : {}
  return {
    input_tokens: Number(data.input_tokens || 0),
    output_tokens: Number(data.output_tokens || 0),
    reasoning_tokens: Number(data.reasoning_tokens || 0),
    total_tokens: Number(data.total_tokens || 0),
    spent_credit: Number(data.spent_credit || 0),
    spent_usd: Number(data.spent_usd || 0),
    has_cost_data: Boolean(data.has_cost_data),
  }
}

function getChatLabel(chat) {
  const title = String(chat?.title || '').trim()
  if (title) return title
  const firstMessage = String(chat?.first_message || '').trim()
  if (firstMessage) return firstMessage
  const chatId = Number(chat?.chat_id)
  return Number.isFinite(chatId) && chatId > 0 ? `Chat #${chatId}` : 'İsimsiz chat'
}

function getMessagePreview(message) {
  const text = String(message || '').trim()
  if (!text) return '-'
  if (text.length <= 180) return text
  return `${text.slice(0, 180).trim()}...`
}

function SummaryCard({ title, value, hint, icon: Icon }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm shadow-slate-200/60">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-slate-500">{title}</div>
        {Icon ? <Icon className="size-4 text-slate-400" /> : null}
      </div>
      <div className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">{value}</div>
      {hint ? <div className="mt-1 text-xs text-slate-500">{hint}</div> : null}
    </div>
  )
}

function UsageMetric({ label, value }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className="mt-1 text-sm font-semibold text-slate-950">{value}</div>
    </div>
  )
}

function RolePill({ role }) {
  const normalized = String(role || '').trim().toLowerCase()
  const label = normalized === 'assistant' ? 'Asistan' : normalized === 'user' ? 'Kullanıcı' : 'Sistem'
  const className =
    normalized === 'assistant'
      ? 'bg-slate-900 text-white'
      : normalized === 'user'
        ? 'bg-sky-100 text-sky-800'
        : 'bg-slate-200 text-slate-700'
  return <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${className}`}>{label}</span>
}

export function AdminAccountDetailPage() {
  const { userId: rawUserId } = useParams()
  const userId = useMemo(() => Number(rawUserId), [rawUserId])
  const isValidUserId = Number.isFinite(userId) && userId > 0

  const [account, setAccount] = useState(null)
  const [overview, setOverview] = useState(null)
  const [chats, setChats] = useState([])
  const [chatPage, setChatPage] = useState(1)
  const [selectedChatId, setSelectedChatId] = useState(null)
  const [chatDetail, setChatDetail] = useState(null)
  const [expandedMessageIds, setExpandedMessageIds] = useState({})
  const [messagePage, setMessagePage] = useState(1)
  const [loadingPage, setLoadingPage] = useState(true)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [pageError, setPageError] = useState(null)
  const [detailError, setDetailError] = useState(null)
  const [accountSettingsDraft, setAccountSettingsDraft] = useState({
    account_type: 'standalone',
    account_plan: 'free',
  })
  const [accountSettingsSaving, setAccountSettingsSaving] = useState(false)
  const [accountSettingsBanner, setAccountSettingsBanner] = useState(null)
  const chatPageSize = 6
  const messagePageSize = 8

  const loadPage = useCallback(async () => {
    if (!isValidUserId) {
      setPageError({
        tone: 'error',
        title: 'Kullanıcı bulunamadı',
        message: 'Geçersiz kullanıcı kimliği ile detay sayfası açılamadı.',
      })
      setLoadingPage(false)
      setChats([])
      setOverview(null)
      setAccount(null)
      return
    }

    setLoadingPage(true)
    setPageError(null)
    try {
      const [overviewData, chatsData] = await Promise.all([
        apiRequest(`/v1/admin/accounts/${userId}/usage-overview`),
        apiRequest(`/v1/admin/accounts/${userId}/chats`),
      ])
      const nextOverview = overviewData?.usage_overview || null
      const nextAccount = overviewData?.account || chatsData?.account || null
      const nextChats = Array.isArray(chatsData?.chats) ? chatsData.chats : []
      setOverview(nextOverview)
      setAccount(nextAccount)
      setChats(nextChats)
      setChatPage(1)
      setSelectedChatId((prev) => {
        if (nextChats.some((item) => Number(item?.chat_id) === Number(prev))) return prev
        const firstChatId = Number(nextChats[0]?.chat_id)
        return Number.isFinite(firstChatId) && firstChatId > 0 ? firstChatId : null
      })
    } catch (err) {
      setPageError(describeApiError(err, 'Kullanım detayları yüklenemedi'))
      setChats([])
      setOverview(null)
      setChatDetail(null)
    } finally {
      setLoadingPage(false)
    }
  }, [isValidUserId, userId])

  const loadChatDetail = useCallback(
    async (chatId) => {
      const parsedChatId = Number(chatId)
      if (!isValidUserId || !Number.isFinite(parsedChatId) || parsedChatId <= 0) {
        setChatDetail(null)
        return
      }

      setLoadingDetail(true)
      setDetailError(null)
      try {
        const data = await apiRequest(`/v1/admin/accounts/${userId}/chats/${parsedChatId}`)
        setAccount((prev) => data?.account || prev)
        setExpandedMessageIds({})
        setMessagePage(1)
        setChatDetail({
          chat: data?.chat || null,
          history: Array.isArray(data?.history) ? data.history : [],
        })
      } catch (err) {
        setDetailError(describeApiError(err, 'Chat mesajları yüklenemedi'))
        setChatDetail(null)
      } finally {
        setLoadingDetail(false)
      }
    },
    [isValidUserId, userId],
  )

  useEffect(() => {
    loadPage()
  }, [loadPage])

  useEffect(() => {
    if (!isValidUserId || !account) return
    setAccountSettingsDraft({
      account_type: String(account.account_type || 'standalone').trim().toLowerCase() || 'standalone',
      account_plan: String(account.account_plan || 'free').trim().toLowerCase() || 'free',
    })
    setAccountSettingsBanner(null)
  }, [isValidUserId, account?.user_id, account?.account_type, account?.account_plan])

  useEffect(() => {
    if (!selectedChatId) {
      setChatDetail(null)
      setDetailError(null)
      return
    }
    loadChatDetail(selectedChatId)
  }, [loadChatDetail, selectedChatId])

  async function onRefresh() {
    await loadPage()
    if (selectedChatId) {
      await loadChatDetail(selectedChatId)
    }
  }

  async function onSaveAccountSettings(event) {
    event.preventDefault()
    if (!isValidUserId) return
    setAccountSettingsBanner(null)
    setAccountSettingsSaving(true)
    try {
      const data = await apiRequest(`/v1/admin/accounts/${userId}/account`, {
        method: 'PATCH',
        body: {
          account_type: accountSettingsDraft.account_type,
          account_plan: accountSettingsDraft.account_plan,
        },
      })
      const next = data?.account || null
      if (next) {
        setAccount(next)
        setAccountSettingsDraft({
          account_type: String(next.account_type || 'standalone').trim().toLowerCase() || 'standalone',
          account_plan: String(next.account_plan || 'free').trim().toLowerCase() || 'free',
        })
      }
      setAccountSettingsBanner({
        tone: 'success',
        title: 'Hesap güncellendi',
        message: 'Hesap tipi ve paket kaydedildi.',
      })
    } catch (err) {
      setAccountSettingsBanner(describeApiError(err, 'Hesap ayarları kaydedilemedi'))
    } finally {
      setAccountSettingsSaving(false)
    }
  }

  const selectedChat = useMemo(() => {
    if (chatDetail?.chat) return chatDetail.chat
    return chats.find((item) => Number(item?.chat_id) === Number(selectedChatId)) || null
  }, [chatDetail, chats, selectedChatId])

  const history = useMemo(() => {
    return Array.isArray(chatDetail?.history) ? chatDetail.history : []
  }, [chatDetail])
  const totalChatPages = Math.max(1, Math.ceil(chats.length / chatPageSize))
  const paginatedChats = useMemo(() => {
    const safePage = Math.min(chatPage, totalChatPages)
    const start = (safePage - 1) * chatPageSize
    return chats.slice(start, start + chatPageSize)
  }, [chatPage, chatPageSize, chats, totalChatPages])
  const totalMessagePages = Math.max(1, Math.ceil(history.length / messagePageSize))
  const paginatedHistory = useMemo(() => {
    const safePage = Math.min(messagePage, totalMessagePages)
    const start = (safePage - 1) * messagePageSize
    return history.slice(start, start + messagePageSize)
  }, [history, messagePage, messagePageSize, totalMessagePages])
  const overviewUsage = getUsageSummary(overview)
  const selectedChatUsage = getUsageSummary(selectedChat?.usage)

  useEffect(() => {
    if (chatPage > totalChatPages) {
      setChatPage(totalChatPages)
    }
  }, [chatPage, totalChatPages])

  useEffect(() => {
    if (messagePage > totalMessagePages) {
      setMessagePage(totalMessagePages)
    }
  }, [messagePage, totalMessagePages])

  function toggleMessage(messageId) {
    const key = Number(messageId)
    if (!Number.isFinite(key) || key <= 0) return
    setExpandedMessageIds((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-100 via-white to-slate-200 px-4 py-10 text-slate-900 sm:px-6 lg:px-10">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <div className="flex flex-col gap-4 rounded-3xl border border-white/60 bg-white/85 px-6 py-6 shadow-[0_24px_60px_-24px_rgba(15,23,42,0.35)] backdrop-blur">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex min-w-0 items-center gap-4">
              <img src={yargucuLogoBlack} alt="Yargucu" className="h-10 w-auto shrink-0" />
              <div className="min-w-0">
                <div className="text-sm font-semibold uppercase tracking-[0.24em] text-slate-500">Admin / Kullanım Detayı</div>
                <h1 className="mt-1 text-3xl font-semibold tracking-tight text-slate-950">
                  {account?.username || `Kullanıcı #${userId}`}
                </h1>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-slate-600">
                  <span className="rounded-full bg-slate-900 px-2.5 py-1 text-xs font-semibold text-white">
                    {getAccountTypeLabel(account?.account_type)}
                  </span>
                  <span className="rounded-full bg-slate-200 px-2.5 py-1 text-xs font-semibold text-slate-700">
                    {getAccountPlanLabel(account?.account_plan)}
                  </span>
                  <span>{account?.email || '-'}</span>
                </div>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button asChild variant="outline" size="lg">
                <Link to="/accounts">
                  <ArrowLeft className="size-4" />
                  Hesaplara dön
                </Link>
              </Button>
              <Button type="button" variant="outline" size="lg" onClick={onRefresh} disabled={loadingPage || loadingDetail}>
                <RefreshCcw className="size-4" />
                Yenile
              </Button>
            </div>
          </div>

          <InlineBanner {...pageError} />
          <Card className="rounded-2xl border-slate-200 bg-white/90 shadow-sm shadow-slate-200/70">
            <CardHeader className="border-b border-slate-100 pb-4">
              <CardTitle className="text-lg">Hesap tipi ve paket</CardTitle>
              <CardDescription>
                Kullanıcının hesap türünü ve abonelik paketini buradan değiştirebilirsiniz. Üst hesabı bağımsız yapmadan önce alt hesaplarını silin veya taşıyın. Alt hesabı üst veya bağımsız yaparken atanmış kredi üst hesaba iade edilir. Yeni bir kullanıcıyı alt hesap olarak bağlamak bu ekrandan desteklenmez.
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-4">
              <InlineBanner {...accountSettingsBanner} />
              <form className="grid gap-4 sm:grid-cols-2" onSubmit={onSaveAccountSettings}>
                <div className="space-y-2">
                  <Label htmlFor="admin-account-type">Hesap tipi</Label>
                  <select
                    id="admin-account-type"
                    className={CONTROL}
                    value={accountSettingsDraft.account_type}
                    onChange={(e) =>
                      setAccountSettingsDraft((prev) => ({ ...prev, account_type: e.target.value }))
                    }
                    disabled={accountSettingsSaving || loadingPage}
                  >
                    <option value="standalone">Bağımsız</option>
                    <option value="parent">Üst hesap</option>
                    <option value="child">Alt hesap</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="admin-account-plan">Paket</Label>
                  <select
                    id="admin-account-plan"
                    className={CONTROL}
                    value={accountSettingsDraft.account_plan}
                    onChange={(e) =>
                      setAccountSettingsDraft((prev) => ({ ...prev, account_plan: e.target.value }))
                    }
                    disabled={accountSettingsSaving || loadingPage}
                  >
                    {Object.entries(ACCOUNT_PLAN_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="sm:col-span-2">
                  <Button type="submit" disabled={accountSettingsSaving || loadingPage || !account}>
                    {accountSettingsSaving ? 'Kaydediliyor…' : 'Kaydet'}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
          {!overviewUsage.has_cost_data && overviewUsage.total_tokens > 0 ? (
            <InlineBanner
              tone="warning"
              title="Maliyet verisi eksik"
              message="Token kullanımı bulundu ancak bazı kayıtlar için kredi/USD maliyeti eşleşmedi. Bu durumda token toplamları doğru, maliyet alanları eksik olabilir."
            />
          ) : null}

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <SummaryCard
              title="Toplam chat"
              value={formatNumber(overview?.chat_count)}
              hint={`Son aktivite: ${formatDate(overview?.last_activity_at)}`}
              icon={MessageSquare}
            />
            <SummaryCard
              title="Toplam mesaj"
              value={formatNumber(overview?.message_count)}
              hint={`Oluşturulma: ${formatDate(account?.created_at)}`}
              icon={Clock3}
            />
            <SummaryCard
              title="Harcanan kredi"
              value={formatCredit(overviewUsage.spent_credit)}
              hint={`Mevcut bakiye: ${formatCredit(account?.credit_summary?.available_credit ?? account?.credit)}`}
              icon={Coins}
            />
            <SummaryCard
              title="USD maliyet"
              value={formatUsd(overviewUsage.spent_usd)}
              hint={`Toplam token: ${formatNumber(overviewUsage.total_tokens)}`}
              icon={DollarSign}
            />
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
          <Card className="rounded-3xl border-slate-200 bg-white/90 shadow-sm shadow-slate-200/70">
            <CardHeader className="border-b border-slate-100">
              <CardTitle>Chat bazlı kullanım</CardTitle>
              <CardDescription>Kullanıcının aktif chat’leri ve her chat için kullanım özeti.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 pt-4">
              {loadingPage ? (
                <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
                  Chat listesi yükleniyor...
                </div>
              ) : chats.length ? (
                <>
                  {paginatedChats.map((chat) => {
                  const chatUsage = getUsageSummary(chat?.usage)
                  const isActive = Number(chat?.chat_id) === Number(selectedChatId)
                  return (
                    <button
                      key={chat?.chat_id}
                      type="button"
                      onClick={() => setSelectedChatId(Number(chat?.chat_id))}
                      className={`w-full rounded-2xl border px-4 py-4 text-left transition ${
                        isActive
                          ? 'border-slate-900 bg-slate-900 text-white shadow-lg shadow-slate-300/40'
                          : 'border-slate-200 bg-slate-50 hover:border-slate-300 hover:bg-white'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="line-clamp-2 text-sm font-semibold">{getChatLabel(chat)}</div>
                          <div className={`mt-1 text-xs ${isActive ? 'text-slate-200' : 'text-slate-500'}`}>
                            Güncelleme: {formatDate(chat?.updated_at)}
                          </div>
                        </div>
                        <div className={`shrink-0 text-xs font-medium ${isActive ? 'text-slate-200' : 'text-slate-500'}`}>
                          {formatNumber(chat?.message_count)} mesaj
                        </div>
                      </div>

                      <div className="mt-3 grid grid-cols-2 gap-2">
                        <UsageMetric label="Toplam token" value={formatNumber(chatUsage.total_tokens)} />
                        <UsageMetric label="Kredi" value={formatCredit(chatUsage.spent_credit)} />
                        <UsageMetric label="USD" value={formatUsd(chatUsage.spent_usd)} />
                        <UsageMetric label="Reasoning" value={formatNumber(chatUsage.reasoning_tokens)} />
                      </div>

                      {!chatUsage.has_cost_data && chatUsage.total_tokens > 0 ? (
                        <div className={`mt-3 text-xs ${isActive ? 'text-amber-200' : 'text-amber-700'}`}>
                          Bu chat için maliyet verisinin bir kısmı eşleşmedi.
                        </div>
                      ) : null}
                    </button>
                  )
                })}
                  <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="text-sm text-slate-500">
                      Toplam {chats.length} chat, sayfa {chatPage} / {totalChatPages}
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={chatPage <= 1}
                        onClick={() => setChatPage((value) => Math.max(1, value - 1))}
                      >
                        Önceki
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={chatPage >= totalChatPages}
                        onClick={() => setChatPage((value) => Math.min(totalChatPages, value + 1))}
                      >
                        Sonraki
                      </Button>
                    </div>
                  </div>
                </>
              ) : (
                <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
                  Bu kullanıcı için görüntülenecek aktif chat bulunamadı.
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="rounded-3xl border-slate-200 bg-white/90 shadow-sm shadow-slate-200/70">
            <CardHeader className="border-b border-slate-100">
              <CardTitle>Mesaj geçmişi</CardTitle>
              <CardDescription>
                {selectedChat ? `${getChatLabel(selectedChat)} sohbetinin mesajları ve kullanım kırılımı.` : 'Soldan bir chat seçin.'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 pt-4">
              <InlineBanner {...detailError} />

              {selectedChat ? (
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <SummaryCard title="Input token" value={formatNumber(selectedChatUsage.input_tokens)} icon={MessageSquare} />
                  <SummaryCard title="Output token" value={formatNumber(selectedChatUsage.output_tokens)} icon={MessageSquare} />
                  <SummaryCard title="Harcanan kredi" value={formatCredit(selectedChatUsage.spent_credit)} icon={Coins} />
                  <SummaryCard title="USD maliyet" value={formatUsd(selectedChatUsage.spent_usd)} icon={DollarSign} />
                </div>
              ) : null}

              {loadingDetail ? (
                <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500">
                  Mesaj geçmişi yükleniyor...
                </div>
              ) : selectedChat ? (
                history.length ? (
                  <div className="space-y-4">
                    {paginatedHistory.map((item) => {
                      const usage = getUsageSummary(item?.usage)
                      const messageId = Number(item?.id)
                      const isExpanded = Boolean(expandedMessageIds[messageId])
                      return (
                        <div key={item?.id} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                          <button
                            type="button"
                            className="w-full text-left"
                            onClick={() => toggleMessage(messageId)}
                          >
                            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                              <div className="min-w-0">
                                <div className="flex flex-wrap items-center gap-2">
                                  <RolePill role={item?.role} />
                                  <span className="text-xs font-medium tracking-[0.14em] text-slate-500">
                                    #{item?.id || '-'} / {formatDate(item?.created_at)}
                                  </span>
                                  <span className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500">
                                    {isExpanded ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
                                    {isExpanded ? 'Kapat' : 'Aç'}
                                  </span>
                                </div>
                                {!isExpanded ? (
                                  <div className="mt-3 line-clamp-2 text-sm leading-6 text-slate-600">
                                    {getMessagePreview(item?.message)}
                                  </div>
                                ) : null}
                              </div>
                              <div className="grid grid-cols-2 gap-2 sm:min-w-[280px]">
                                <UsageMetric label="Toplam token" value={formatNumber(usage.total_tokens)} />
                                <UsageMetric label="Kredi" value={formatCredit(usage.spent_credit)} />
                                <UsageMetric label="USD" value={formatUsd(usage.spent_usd)} />
                                <UsageMetric label="Reasoning" value={formatNumber(usage.reasoning_tokens)} />
                              </div>
                            </div>
                          </button>
                          {isExpanded ? (
                            <div className="mt-4 whitespace-pre-wrap break-words rounded-2xl bg-white px-4 py-4 text-sm leading-6 text-slate-800">
                              {item?.message || '-'}
                            </div>
                          ) : null}
                        </div>
                      )
                    })}
                    <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
                      <div className="text-sm text-slate-500">
                        Toplam {history.length} mesaj, sayfa {messagePage} / {totalMessagePages}
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          disabled={messagePage <= 1}
                          onClick={() => setMessagePage((value) => Math.max(1, value - 1))}
                        >
                          Önceki
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          disabled={messagePage >= totalMessagePages}
                          onClick={() => setMessagePage((value) => Math.min(totalMessagePages, value + 1))}
                        >
                          Sonraki
                        </Button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500">
                    Bu chat için kayıtlı mesaj bulunamadı.
                  </div>
                )
              ) : (
                <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500">
                  Mesajları görmek için soldaki listeden bir chat seçin.
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
