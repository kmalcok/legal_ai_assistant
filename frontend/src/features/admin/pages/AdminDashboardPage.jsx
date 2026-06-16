import { useCallback, useEffect, useMemo, useState } from 'react'
import { BadgePlus, Coins, KeyRound, RefreshCcw, Search, ShieldCheck, Trash2, UserPlus, Users } from 'lucide-react'
import { Link } from 'react-router-dom'

import { apiRequest } from '@/shared/api/client.js'
import { describeApiError } from '@/shared/api/contracts.js'
import { InlineBanner } from '@/shared/components/InlineBanner.jsx'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
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
  'h-11 rounded-xl border-slate-200 bg-white text-[15px] text-slate-900 shadow-sm shadow-slate-200/60 focus-visible:border-slate-400 focus-visible:ring-4 focus-visible:ring-slate-200/80'

function formatCredit(value) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '-'
  return num.toLocaleString('tr-TR', { maximumFractionDigits: 2 })
}

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

function getAccountTypeLabel(type) {
  return ACCOUNT_TYPE_LABELS[String(type || '').trim().toLowerCase()] || 'Hesap'
}

function getAccountPlanLabel(plan) {
  return ACCOUNT_PLAN_LABELS[String(plan || '').trim().toLowerCase()] || 'Ücretsiz'
}

function buildAccountsPath({ accountType, query }) {
  const params = new URLSearchParams()
  if (accountType && accountType !== 'all') params.set('account_type', accountType)
  if (query) params.set('q', query)
  const suffix = params.toString()
  return suffix ? `/v1/admin/accounts?${suffix}` : '/v1/admin/accounts'
}

export function AdminDashboardPage() {
  const [accounts, setAccounts] = useState([])
  const [loading, setLoading] = useState(true)
  const [listError, setListError] = useState(null)
  const [banner, setBanner] = useState(null)
  const [resetReveal, setResetReveal] = useState(null)
  const [searchDraft, setSearchDraft] = useState('')
  const [query, setQuery] = useState('')
  const [accountTypeFilter, setAccountTypeFilter] = useState('all')
  const [currentPage, setCurrentPage] = useState(1)
  const [reloadTick, setReloadTick] = useState(0)
  const [creating, setCreating] = useState(false)
  const [creditLoadingId, setCreditLoadingId] = useState(null)
  const [passwordResetLoadingId, setPasswordResetLoadingId] = useState(null)
  const [deleteLoadingId, setDeleteLoadingId] = useState(null)
  const [creditInputs, setCreditInputs] = useState({})
  const [accountProfileDrafts, setAccountProfileDrafts] = useState({})
  const [profileSaveLoadingId, setProfileSaveLoadingId] = useState(null)
  const pageSize = 5
  const [form, setForm] = useState({
    username: '',
    email: '',
    full_name: '',
    password: '',
    account_type: 'standalone',
    account_plan: 'free',
    initial_credit: '',
  })

  const loadAccounts = useCallback(
    async ({ silent = false, nextQuery = query, nextType = accountTypeFilter } = {}) => {
      if (!silent) setLoading(true)
      setListError(null)
      try {
        const data = await apiRequest(
          buildAccountsPath({
            accountType: nextType,
            query: String(nextQuery || '').trim(),
          }),
        )
        const items = Array.isArray(data?.accounts) ? data.accounts : []
        setAccounts(items)
        setCreditInputs((prev) => {
          const next = { ...prev }
          for (const account of items) {
            const userId = Number(account?.user_id)
            if (!Number.isFinite(userId)) continue
            next[userId] = String(account?.credit ?? '')
          }
          return next
        })
        setAccountProfileDrafts(() => {
          const next = {}
          for (const account of items) {
            const uid = Number(account?.user_id)
            if (!Number.isFinite(uid) || uid <= 0) continue
            next[uid] = {
              account_type: String(account?.account_type || 'standalone').trim().toLowerCase() || 'standalone',
              account_plan: String(account?.account_plan || 'free').trim().toLowerCase() || 'free',
            }
          }
          return next
        })
      } catch (err) {
        setListError(describeApiError(err, 'Hesaplar yüklenemedi'))
      } finally {
        if (!silent) setLoading(false)
      }
    },
    [accountTypeFilter, query],
  )

  useEffect(() => {
    loadAccounts()
  }, [loadAccounts, reloadTick])

  useEffect(() => {
    setCurrentPage(1)
  }, [query, accountTypeFilter, reloadTick])

  const stats = useMemo(() => {
    let standalone = 0
    let parent = 0
    let child = 0
    let totalAvailable = 0
    for (const account of accounts) {
      if (account?.account_type === 'parent') parent += 1
      else if (account?.account_type === 'child') child += 1
      else standalone += 1
      totalAvailable += Number(account?.credit_summary?.available_credit ?? account?.credit ?? 0) || 0
    }
    return {
      standalone,
      parent,
      child,
      totalAvailable,
    }
  }, [accounts])

  const totalPages = Math.max(1, Math.ceil(accounts.length / pageSize))
  const paginatedAccounts = useMemo(() => {
    const safePage = Math.min(currentPage, totalPages)
    const start = (safePage - 1) * pageSize
    return accounts.slice(start, start + pageSize)
  }, [accounts, currentPage, pageSize, totalPages])

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages)
    }
  }, [currentPage, totalPages])

  async function onSubmitSearch(event) {
    event.preventDefault()
    setQuery(searchDraft.trim())
  }

  async function onCreateAccount(event) {
    event.preventDefault()
    setBanner(null)
    setCreating(true)
    try {
      const initialCredit = Number(form.initial_credit || 0)
      const data = await apiRequest('/v1/admin/accounts', {
        method: 'POST',
        body: {
          username: form.username,
          email: form.email,
          full_name: form.full_name,
          password: form.password,
          account_type: form.account_type,
          account_plan: form.account_plan,
          initial_credit: Number.isFinite(initialCredit) ? initialCredit : 0,
        },
      })
      const created = data?.account || {}
      setBanner({
        tone: 'success',
        title: 'Hesap oluşturuldu',
        message: `${created?.username || 'Yeni hesap'} oluşturuldu.`,
      })
      setForm({
        username: '',
        email: '',
        full_name: '',
        password: '',
        account_type: 'standalone',
        account_plan: 'free',
        initial_credit: '',
      })
      setReloadTick((value) => value + 1)
    } catch (err) {
      setBanner(describeApiError(err, 'Hesap oluşturulamadı'))
    } finally {
      setCreating(false)
    }
  }

  async function onSetCredit(account) {
    const userId = Number(account?.user_id)
    if (!Number.isFinite(userId)) return
    const nextValue = Number(creditInputs[userId] ?? account?.credit ?? 0)
    if (!Number.isFinite(nextValue) || nextValue < 0) {
      setBanner({
        tone: 'error',
        title: 'Kredi değeri geçersiz',
        message: 'Lütfen sıfır veya daha büyük bir kredi değeri girin.',
      })
      return
    }

    setBanner(null)
    setCreditLoadingId(userId)
    try {
      const data = await apiRequest(`/v1/admin/accounts/${userId}/credit`, {
        method: 'PATCH',
        body: { credit: nextValue },
      })
      const updated = data?.account || {}
      setBanner({
        tone: 'success',
        title: 'Kredi güncellendi',
        message: `${updated?.username || 'Hesap'} için kredi ${formatCredit(updated?.credit)} olarak güncellendi.`,
      })
      setReloadTick((value) => value + 1)
    } catch (err) {
      setBanner(describeApiError(err, 'Kredi güncellenemedi'))
    } finally {
      setCreditLoadingId(null)
    }
  }

  async function onDeleteAccount(account) {
    const userId = Number(account?.user_id)
    if (!Number.isFinite(userId)) return
    const ok = window.confirm(
      `${account?.username || 'Bu hesap'} silinsin mi? Bu işlem geri alınamaz.`,
    )
    if (!ok) return

    setBanner(null)
    setDeleteLoadingId(userId)
    try {
      const data = await apiRequest(`/v1/admin/accounts/${userId}`, { method: 'DELETE' })
      const cascadeCount = Number(data?.cascade_count || 0)
      setBanner({
        tone: 'success',
        title: 'Hesap silindi',
        message:
          cascadeCount > 0
            ? `${account?.username || 'Hesap'} ve bağlı ${cascadeCount} alt hesap silindi.`
            : `${account?.username || 'Hesap'} silindi.`,
      })
      setReloadTick((value) => value + 1)
    } catch (err) {
      setBanner(describeApiError(err, 'Hesap silinemedi'))
    } finally {
      setDeleteLoadingId(null)
    }
  }

  async function onSaveAccountProfile(account) {
    const userId = Number(account?.user_id)
    if (!Number.isFinite(userId) || userId <= 0) return
    const draft = accountProfileDrafts[userId]
    if (!draft) return

    setBanner(null)
    setProfileSaveLoadingId(userId)
    try {
      await apiRequest(`/v1/admin/accounts/${userId}/account`, {
        method: 'PATCH',
        body: {
          account_type: draft.account_type,
          account_plan: draft.account_plan,
        },
      })
      setBanner({
        tone: 'success',
        title: 'Hesap tipi ve paket güncellendi',
        message: `${account?.username || 'Hesap'} kaydedildi.`,
      })
      setReloadTick((value) => value + 1)
    } catch (err) {
      setBanner(describeApiError(err, 'Hesap tipi veya paket güncellenemedi'))
    } finally {
      setProfileSaveLoadingId(null)
    }
  }

  async function onResetPassword(account) {
    const userId = Number(account?.user_id)
    if (!Number.isFinite(userId)) return
    const ok = window.confirm(
      `${account?.username || 'Bu hesap'} için yeni geçici parola oluşturulsun mu? Mevcut oturumlar kapanacaktır.`,
    )
    if (!ok) return

    setBanner(null)
    setResetReveal(null)
    setPasswordResetLoadingId(userId)
    try {
      const data = await apiRequest(`/v1/admin/accounts/${userId}/reset-password`, {
        method: 'POST',
      })
      const updated = data?.account || account
      const tempPassword = String(data?.temp_password || '').trim()
      setBanner({
        tone: 'success',
        title: 'Parola sıfırlandı',
        message: `${updated?.username || 'Hesap'} için yeni geçici parola üretildi.`,
      })
      setResetReveal({
        username: updated?.username || account?.username || '-',
        tempPassword,
      })
      setReloadTick((value) => value + 1)
    } catch (err) {
      setBanner(describeApiError(err, 'Parola sıfırlanamadı'))
    } finally {
      setPasswordResetLoadingId(null)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-4 rounded-[28px] border border-slate-200 bg-white px-6 py-6 shadow-sm shadow-slate-200/70 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-slate-200 bg-slate-50">
              <img src={yargucuLogoBlack} alt="Yargucu" className="h-7 w-auto" />
            </div>
            <div>
              <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">
                <ShieldCheck className="size-4" />
                Admin Paneli
              </div>
              <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-950">
                Hesap kontrol merkezi
              </h1>
              <p className="mt-1 text-sm leading-6 text-slate-500">
                Bu alan nginx/basic-auth (siksen giremezler yani) ile korunur. Buradan bağımsız ve üst hesapları yönetebilirsin babayigit.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button asChild type="button" variant="outline" size="lg">
              <Link to="/coupons">Kuponlar</Link>
            </Button>
            <Button
              type="button"
              variant="outline"
              size="lg"
              onClick={() => setReloadTick((value) => value + 1)}
            >
              <RefreshCcw className="size-4" />
              Yenile
            </Button>
          </div>
        </div>

        {banner ? (
          <InlineBanner tone={banner.tone} title={banner.title} message={banner.message} />
        ) : null}
        {resetReveal ? (
          <div className="rounded-[24px] border border-amber-200 bg-amber-50 px-5 py-4 text-amber-950 shadow-sm shadow-amber-100/70">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <div className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-700">
                  Tek seferlik parola gosterimi
                </div>
                <div className="mt-2 text-sm leading-6 text-amber-900">
                  <span className="font-semibold">{resetReveal.username}</span> icin uretilen gecici parola asagidadir. Bu bilgi sadece simdi gosterilir; kapatinca tekrar gorunmez.
                </div>
                <div className="mt-3 inline-flex rounded-xl border border-amber-300 bg-white px-4 py-2 font-mono text-base font-semibold tracking-wide text-slate-950">
                  {resetReveal.tempPassword || '-'}
                </div>
              </div>
              <Button type="button" variant="outline" size="lg" onClick={() => setResetReveal(null)}>
                Kapat
              </Button>
            </div>
          </div>
        ) : null}
        {listError ? (
          <InlineBanner tone={listError.tone} title={listError.title} message={listError.message} />
        ) : null}

        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="border-slate-200 bg-white shadow-sm shadow-slate-200/70">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="size-4 text-slate-500" />
                Toplam hesap
              </CardTitle>
              <CardDescription>Yönetilen bağımsız ve üst hesap sayısı.</CardDescription>
            </CardHeader>
            <CardContent className="text-3xl font-semibold tracking-tight text-slate-950">
              {accounts.length}
            </CardContent>
          </Card>
          <Card className="border-slate-200 bg-white shadow-sm shadow-slate-200/70">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BadgePlus className="size-4 text-slate-500" />
                Tür dağılımı
              </CardTitle>
              <CardDescription>Bağımsız ve üst hesap kırılımı.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-slate-600">
              <div>Bağımsız: <span className="font-semibold text-slate-950">{stats.standalone}</span></div>
              <div>Üst hesap: <span className="font-semibold text-slate-950">{stats.parent}</span></div>
              <div>Alt hesap: <span className="font-semibold text-slate-950">{stats.child}</span></div>
            </CardContent>
          </Card>
          <Card className="border-slate-200 bg-white shadow-sm shadow-slate-200/70">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Coins className="size-4 text-slate-500" />
                Kullanılabilir kredi
              </CardTitle>
              <CardDescription>Listelenen hesapların toplam kullanılabilir bakiyesi.</CardDescription>
            </CardHeader>
            <CardContent className="text-3xl font-semibold tracking-tight text-slate-950">
              {formatCredit(stats.totalAvailable)}
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-6 xl:grid-cols-[1.1fr_1.6fr]">
          <Card className="border-slate-200 bg-white shadow-sm shadow-slate-200/70">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <UserPlus className="size-4 text-slate-500" />
                Yeni hesap oluştur
              </CardTitle>
              <CardDescription>
                İlk sürümde bağımsız veya üst hesap açabilirsiniz. Alt hesap oluşturma bu ekranda yok. Mail dogrulamayi bypass eder !!
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form className="grid gap-4" onSubmit={onCreateAccount}>
                <Input
                  className={CONTROL}
                  placeholder="Kullanıcı adı"
                  value={form.username}
                  onChange={(event) => setForm((prev) => ({ ...prev, username: event.target.value }))}
                  disabled={creating}
                />
                <Input
                  className={CONTROL}
                  placeholder="E-posta adresi"
                  value={form.email}
                  onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))}
                  disabled={creating}
                />
                <Input
                  className={CONTROL}
                  placeholder="Ad soyad"
                  value={form.full_name}
                  onChange={(event) => setForm((prev) => ({ ...prev, full_name: event.target.value }))}
                  disabled={creating}
                />
                <Input
                  className={CONTROL}
                  type="password"
                  placeholder="Geçici parola"
                  value={form.password}
                  onChange={(event) => setForm((prev) => ({ ...prev, password: event.target.value }))}
                  disabled={creating}
                />
                <div className="grid gap-4 sm:grid-cols-2">
                  <select
                    className={`${CONTROL} px-3`}
                    value={form.account_type}
                    onChange={(event) => setForm((prev) => ({ ...prev, account_type: event.target.value }))}
                    disabled={creating}
                  >
                    <option value="standalone">Bağımsız</option>
                    <option value="parent">Üst Hesap</option>
                  </select>
                  <select
                    className={`${CONTROL} px-3`}
                    value={form.account_plan}
                    onChange={(event) => setForm((prev) => ({ ...prev, account_plan: event.target.value }))}
                    disabled={creating}
                  >
                    {Object.entries(ACCOUNT_PLAN_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </div>
                <Input
                  className={CONTROL}
                  inputMode="decimal"
                  placeholder="Başlangıç kredisi"
                  value={form.initial_credit}
                  onChange={(event) => setForm((prev) => ({ ...prev, initial_credit: event.target.value }))}
                  disabled={creating}
                />
                <Button type="submit" size="lg" disabled={creating}>
                  {creating ? 'Oluşturuluyor...' : 'Hesap oluştur'}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card className="border-slate-200 bg-white shadow-sm shadow-slate-200/70">
            <CardHeader className="gap-3">
              <CardTitle>Hesap listesi</CardTitle>
              <CardDescription>
                Bu liste bağımsız, üst ve alt hesapları gösterir. Üst hesaplarda toplam, ayrılmış ve kullanılabilir kredi ayrı görünür.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              <form className="grid gap-3 md:grid-cols-[1fr_180px_auto]" onSubmit={onSubmitSearch}>
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
                  <Input
                    className={`${CONTROL} pl-9`}
                    placeholder="Kullanıcı adı, e-posta veya ad soyad ara"
                    value={searchDraft}
                    onChange={(event) => setSearchDraft(event.target.value)}
                  />
                </div>
                <select
                  className={`${CONTROL} px-3`}
                  value={accountTypeFilter}
                  onChange={(event) => setAccountTypeFilter(event.target.value)}
                >
                  <option value="all">Tüm hesaplar</option>
                  <option value="standalone">Bağımsız</option>
                  <option value="parent">Üst hesap</option>
                  <option value="child">Alt hesap</option>
                </select>
                <Button type="submit" variant="outline" size="lg">
                  Filtrele
                </Button>
              </form>

              {loading ? (
                <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500">
                  Hesaplar yükleniyor...
                </div>
              ) : accounts.length ? (
                <div className="grid gap-4">
                  {paginatedAccounts.map((account) => {
                    const userId = Number(account?.user_id)
                    const isParent = account?.account_type === 'parent'
                    const isChild = account?.account_type === 'child'
                    return (
                      <div key={userId} className="rounded-3xl border border-slate-200 bg-slate-50/80 p-4">
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <div className="text-lg font-semibold tracking-tight text-slate-950">
                                {account?.username || '-'}
                              </div>
                              <span className="rounded-full bg-slate-900 px-2.5 py-1 text-xs font-semibold text-white">
                                {getAccountTypeLabel(account?.account_type)}
                              </span>
                              <span className="rounded-full bg-slate-200 px-2.5 py-1 text-xs font-semibold text-slate-700">
                                {getAccountPlanLabel(account?.account_plan)}
                              </span>
                            </div>
                            <div className="mt-2 text-sm text-slate-600">{account?.email || '-'}</div>
                            <div className="mt-1 text-sm text-slate-500">
                              {account?.full_name || 'Ad soyad belirtilmemiş'}
                            </div>
                            <div className="mt-3 flex flex-wrap gap-4 text-xs font-medium tracking-[0.16em] text-slate-500">
                              <span>ID: {userId || '-'}</span>
                              <span>Oluşturulma: {formatDate(account?.created_at)}</span>
                              {isParent ? (
                                <span>
                                  Alt hesap: {Number(account?.managed_children?.count || 0)} / {Number(account?.managed_children?.limit || 0)}
                                </span>
                              ) : null}
                              {isChild ? (
                                <span>
                                  Üst hesap: {account?.parent_username || '-'}
                                </span>
                              ) : null}
                            </div>
                          </div>

                          <div className="grid gap-2 text-sm text-slate-600 lg:min-w-[260px]">
                            {isParent ? (
                              <>
                                <div>Toplam kredi: <span className="font-semibold text-slate-950">{formatCredit(account?.credit_summary?.total_credit)}</span></div>
                                <div>Ayrılmış kredi: <span className="font-semibold text-slate-950">{formatCredit(account?.credit_summary?.reserved_credit)}</span></div>
                              </>
                            ) : null}
                            <div>Kullanılabilir kredi: <span className="font-semibold text-slate-950">{formatCredit(account?.credit_summary?.available_credit ?? account?.credit)}</span></div>
                          </div>
                        </div>

                        <div className="mt-4 grid gap-3 rounded-2xl border border-slate-200/90 bg-white/70 p-3 sm:grid-cols-2 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] lg:items-end">
                          <div className="flex flex-col gap-1.5">
                            <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                              Hesap tipi
                            </span>
                            <select
                              className={`${CONTROL} px-3`}
                              value={
                                accountProfileDrafts[userId]?.account_type ??
                                String(account?.account_type || 'standalone').toLowerCase()
                              }
                              onChange={(event) =>
                                setAccountProfileDrafts((prev) => ({
                                  ...prev,
                                  [userId]: {
                                    account_type: event.target.value,
                                    account_plan:
                                      prev[userId]?.account_plan ??
                                      String(account?.account_plan || 'free').toLowerCase(),
                                  },
                                }))
                              }
                              disabled={profileSaveLoadingId === userId || loading}
                            >
                              <option value="standalone">Bağımsız</option>
                              <option value="parent">Üst hesap</option>
                              <option value="child">Alt hesap</option>
                            </select>
                          </div>
                          <div className="flex flex-col gap-1.5">
                            <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                              Paket
                            </span>
                            <select
                              className={`${CONTROL} px-3`}
                              value={
                                accountProfileDrafts[userId]?.account_plan ??
                                String(account?.account_plan || 'free').toLowerCase()
                              }
                              onChange={(event) =>
                                setAccountProfileDrafts((prev) => ({
                                  ...prev,
                                  [userId]: {
                                    account_type:
                                      prev[userId]?.account_type ??
                                      String(account?.account_type || 'standalone').toLowerCase(),
                                    account_plan: event.target.value,
                                  },
                                }))
                              }
                              disabled={profileSaveLoadingId === userId || loading}
                            >
                              {Object.entries(ACCOUNT_PLAN_LABELS).map(([value, label]) => (
                                <option key={value} value={value}>
                                  {label}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div className="flex sm:col-span-2 lg:col-span-1 lg:justify-end">
                            <Button
                              type="button"
                              variant="secondary"
                              size="sm"
                              className="w-full lg:w-auto"
                              disabled={profileSaveLoadingId === userId || loading || userId <= 0}
                              onClick={() => onSaveAccountProfile(account)}
                            >
                              {profileSaveLoadingId === userId ? 'Kaydediliyor...' : 'Tip ve paketi kaydet'}
                            </Button>
                          </div>
                        </div>

                        <div className="mt-4 flex flex-col gap-3 2xl:flex-row 2xl:items-center 2xl:justify-between">
                          <div className="flex flex-wrap items-stretch gap-2">
                            {userId > 0 ? (
                              <Button asChild variant="secondary" size="sm" className="w-full sm:w-auto">
                                <Link to={`/accounts/${userId}`}>Kullanımı gör</Link>
                              </Button>
                            ) : null}
                            <Input
                              className={`${CONTROL} w-full sm:w-[180px] md:w-[220px]`}
                              inputMode="decimal"
                              value={creditInputs[userId] ?? ''}
                              onChange={(event) =>
                                setCreditInputs((prev) => ({ ...prev, [userId]: event.target.value }))
                              }
                            />
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              className="w-full sm:w-auto"
                              disabled={creditLoadingId === userId}
                              onClick={() => onSetCredit(account)}
                            >
                              {creditLoadingId === userId ? 'Güncelleniyor...' : 'Krediyi güncelle'}
                            </Button>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              className="w-full sm:w-auto"
                              disabled={passwordResetLoadingId === userId}
                              onClick={() => onResetPassword(account)}
                            >
                              <KeyRound className="size-4" />
                              {passwordResetLoadingId === userId ? 'Sıfırlanıyor...' : 'Şifreyi sıfırla'}
                            </Button>
                          </div>
                          <Button
                            type="button"
                            variant="destructive"
                            size="sm"
                            className="w-full sm:w-auto"
                            disabled={isChild || deleteLoadingId === userId}
                            onClick={() => onDeleteAccount(account)}
                          >
                            <Trash2 className="size-4" />
                            {isChild ? 'Alt hesap silinemez' : deleteLoadingId === userId ? 'Siliniyor...' : 'Hesabı sil'}
                          </Button>
                        </div>
                      </div>
                    )
                  })}
                  <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="text-sm text-slate-500">
                      Toplam {accounts.length} hesap, sayfa {currentPage} / {totalPages}
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        size="lg"
                        disabled={currentPage <= 1}
                        onClick={() => setCurrentPage((value) => Math.max(1, value - 1))}
                      >
                        Önceki
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="lg"
                        disabled={currentPage >= totalPages}
                        onClick={() => setCurrentPage((value) => Math.min(totalPages, value + 1))}
                      >
                        Sonraki
                      </Button>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500">
                  Bu filtrelerle eşleşen hesap bulunamadı.
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
