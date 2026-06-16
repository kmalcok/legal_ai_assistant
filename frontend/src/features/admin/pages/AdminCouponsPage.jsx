import { useCallback, useEffect, useMemo, useState } from 'react'
import { Coins, Download, RefreshCcw, ShieldCheck, TicketPlus, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { apiRequest } from '@/shared/api/client.js'
import { describeApiError } from '@/shared/api/contracts.js'
import { InlineBanner } from '@/shared/components/InlineBanner.jsx'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import yargucuLogoBlack from '@/logopack/yargucu-logo-siyah.svg'

const ACCOUNT_PLAN_LABELS = {
  free: 'Ucretsiz',
  student: 'Ogrenci',
  starter: 'Baslangic',
  standard: 'Standart',
  advanced: 'Gelismis',
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

function getAccountPlanLabel(plan) {
  if (!plan) return 'Paket degisimi yok'
  return ACCOUNT_PLAN_LABELS[String(plan || '').trim().toLowerCase()] || String(plan || '')
}

function getCouponStatusLabel(coupon) {
  const usedCount = Number(coupon?.redemption_count ?? 0)
  const maxRedemptions = Number(coupon?.max_redemptions ?? 1)
  if (usedCount >= maxRedemptions) return 'Tukendi'
  if (usedCount > 0) return 'Kullanimda'
  return 'Hazir'
}

function getCouponTypeLabel(coupon) {
  return coupon?.distribution_mode === 'counter' ? 'Kampanya kodu' : 'Tek seferlik kupon'
}

export function AdminCouponsPage() {
  const [coupons, setCoupons] = useState([])
  const [generatedCoupons, setGeneratedCoupons] = useState([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [banner, setBanner] = useState(null)
  const [listError, setListError] = useState(null)
  const [reloadTick, setReloadTick] = useState(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const [campaignFilter, setCampaignFilter] = useState('')
  const [usedStatusFilter, setUsedStatusFilter] = useState('all')
  const [selectedCouponIds, setSelectedCouponIds] = useState([])
  const pageSize = 25
  const [form, setForm] = useState({
    campaign_name: '',
    distribution_mode: 'unique',
    campaign_code: '',
    quantity: '10',
    credit_amount: '',
    target_account_plan: '',
  })
  const isCampaignCode = form.distribution_mode === 'counter'

  const loadCoupons = useCallback(async () => {
    setLoading(true)
    setListError(null)
    try {
      const params = new URLSearchParams()
      params.set('limit', String(pageSize))
      params.set('page', String(currentPage))
      if (campaignFilter.trim()) params.set('campaign_name', campaignFilter.trim())
      if (usedStatusFilter !== 'all') params.set('used_status', usedStatusFilter)
      const suffix = params.toString()
      const data = await apiRequest(`/v1/admin/coupons${suffix ? `?${suffix}` : ''}`)
      setCoupons(Array.isArray(data?.coupons) ? data.coupons : [])
      setTotalCount(Number(data?.total_count || 0))
    } catch (err) {
      setListError(describeApiError(err, 'Kuponlar yuklenemedi'))
    } finally {
      setLoading(false)
    }
  }, [campaignFilter, currentPage, pageSize, usedStatusFilter])

  useEffect(() => {
    loadCoupons()
  }, [loadCoupons, reloadTick])

  useEffect(() => {
    setSelectedCouponIds([])
  }, [coupons])

  useEffect(() => {
    setCurrentPage(1)
  }, [campaignFilter, usedStatusFilter])

  const allSelected = useMemo(
    () => coupons.length > 0 && coupons.every((coupon) => selectedCouponIds.includes(Number(coupon.coupon_id))),
    [coupons, selectedCouponIds],
  )
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize))

  async function onCreateCoupons(event) {
    event.preventDefault()
    setCreating(true)
    setBanner(null)
    try {
      const quantity = Number(form.quantity || 0)
      const creditAmount = Number(form.credit_amount || 0)
      const data = await apiRequest('/v1/admin/coupons', {
        method: 'POST',
        body: {
          campaign_name: form.campaign_name,
          distribution_mode: form.distribution_mode,
          campaign_code: isCampaignCode ? form.campaign_code : null,
          quantity: Number.isFinite(quantity) ? quantity : 0,
          credit_amount: Number.isFinite(creditAmount) ? creditAmount : 0,
          target_account_plan: form.target_account_plan || null,
        },
      })
      const nextCoupons = Array.isArray(data?.coupons) ? data.coupons : []
      setGeneratedCoupons(nextCoupons)
      setBanner({
        tone: 'success',
        title: 'Kuponlar olusturuldu',
        message: `${nextCoupons.length} adet kupon uretildi.`,
      })
      setForm({
        campaign_name: '',
        distribution_mode: 'unique',
        campaign_code: '',
        quantity: '10',
        credit_amount: '',
        target_account_plan: '',
      })
      setReloadTick((value) => value + 1)
    } catch (err) {
      setBanner(describeApiError(err, 'Kuponlar olusturulamadi'))
    } finally {
      setCreating(false)
    }
  }

  function toggleCouponSelection(couponId) {
    const normalizedId = Number(couponId)
    if (!Number.isFinite(normalizedId)) return
    setSelectedCouponIds((prev) =>
      prev.includes(normalizedId) ? prev.filter((item) => item !== normalizedId) : [...prev, normalizedId],
    )
  }

  function toggleSelectAll() {
    if (allSelected) {
      setSelectedCouponIds([])
      return
    }
    setSelectedCouponIds(
      coupons
        .map((coupon) => Number(coupon.coupon_id))
        .filter((couponId) => Number.isFinite(couponId)),
    )
  }

  async function onDeleteSelected() {
    if (!selectedCouponIds.length) return
    if (!window.confirm(`${selectedCouponIds.length} kupon silinecek. Devam edilsin mi?`)) return
    setDeleting(true)
    setBanner(null)
    try {
      const data = await apiRequest('/v1/admin/coupons/delete', {
        method: 'POST',
        body: { coupon_ids: selectedCouponIds },
      })
      setBanner({
        tone: 'success',
        title: 'Kuponlar silindi',
        message: `${Number(data?.deleted_count || 0)} kupon silindi.`,
      })
      setSelectedCouponIds([])
      setReloadTick((value) => value + 1)
    } catch (err) {
      setBanner(describeApiError(err, 'Kuponlar silinemedi'))
    } finally {
      setDeleting(false)
    }
  }

  function onExportText() {
    const lines = coupons.map((coupon) => [
      coupon.code,
      coupon.campaign_name || '',
      coupon.is_used ? 'used' : 'unused',
      String(coupon.redemption_count || 0),
      String(coupon.max_redemptions || 1),
      String(coupon.used_by_username || ''),
      String(coupon.used_at || ''),
    ].join('\t'))
    const content = lines.join('\n')
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    const href = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = href
    const filterSuffix = campaignFilter.trim() ? `-${campaignFilter.trim()}` : ''
    link.download = `coupons${filterSuffix}-${usedStatusFilter}.txt`
    link.click()
    URL.revokeObjectURL(href)
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
                Kupon yonetimi
              </h1>
              <p className="mt-1 text-sm leading-6 text-slate-500">
                Tek seferlik kuponlari ve paylasimli kampanya kodlarini buradan yonetebilirsin.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button asChild type="button" variant="outline" size="lg">
              <Link to="/accounts">Hesaplara don</Link>
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

        {banner ? <InlineBanner tone={banner.tone} title={banner.title} message={banner.message} /> : null}
        {listError ? <InlineBanner tone={listError.tone} title={listError.title} message={listError.message} /> : null}

        <div className="grid gap-6 xl:grid-cols-[1.05fr_1.55fr]">
          <Card className="border-slate-200 bg-white shadow-sm shadow-slate-200/70">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TicketPlus className="size-4 text-slate-500" />
                Kupon olustur
              </CardTitle>
              <CardDescription>
                Kampanya adi etiket olarak saklanir. Tek seferlik kuponlarda sistem rastgele kod uretir; kampanya kodlarinda ise kullanicinin girecegi sabit kodu sen belirlersin.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form className="space-y-4" onSubmit={onCreateCoupons}>
                <div className="space-y-2">
                  <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Kampanya adi</label>
                  <Input
                    className={CONTROL}
                    value={form.campaign_name}
                    onChange={(event) => setForm((prev) => ({ ...prev, campaign_name: event.target.value }))}
                    placeholder="Orn: bahar-ogrenci-2026"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Kupon tipi</label>
                  <select
                    className={`${CONTROL} w-full px-3`}
                    value={form.distribution_mode}
                    onChange={(event) => setForm((prev) => ({ ...prev, distribution_mode: event.target.value }))}
                  >
                    <option value="unique">Tek seferlik kupon</option>
                    <option value="counter">Kampanya kodu</option>
                  </select>
                </div>
                {isCampaignCode ? (
                  <div className="space-y-2">
                    <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Kampanya kodu</label>
                    <Input
                      className={CONTROL}
                      value={form.campaign_code}
                      onChange={(event) =>
                        setForm((prev) => ({ ...prev, campaign_code: event.target.value.toUpperCase() }))
                      }
                      placeholder="Orn: HACETTEPEHUKUK25"
                      autoCapitalize="characters"
                      autoCorrect="off"
                      spellCheck={false}
                    />
                  </div>
                ) : null}
                <div className="space-y-2">
                  <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                    {isCampaignCode ? 'Kullanim hakki' : 'Adet'}
                  </label>
                  <Input
                    className={CONTROL}
                    inputMode="numeric"
                    value={form.quantity}
                    onChange={(event) => setForm((prev) => ({ ...prev, quantity: event.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Kredi</label>
                  <Input
                    className={CONTROL}
                    inputMode="decimal"
                    value={form.credit_amount}
                    onChange={(event) => setForm((prev) => ({ ...prev, credit_amount: event.target.value }))}
                    placeholder="0"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Hedef paket</label>
                  <select
                    className={`${CONTROL} w-full px-3`}
                    value={form.target_account_plan}
                    onChange={(event) => setForm((prev) => ({ ...prev, target_account_plan: event.target.value }))}
                  >
                    <option value="">Paket degisimi yok</option>
                    {Object.entries(ACCOUNT_PLAN_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </div>
                <Button type="submit" className="w-full" disabled={creating}>
                  {creating ? 'Olusturuluyor...' : 'Kuponlari olustur'}
                </Button>
              </form>
            </CardContent>
          </Card>

          <div className="space-y-6">
            <Card className="border-slate-200 bg-white shadow-sm shadow-slate-200/70">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Coins className="size-4 text-slate-500" />
                  Son uretilen kuponlar
                </CardTitle>
                <CardDescription>Yeni olusturulan kodlar bir kere daha kopyalayabilmen icin burada tutulur.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {generatedCoupons.length ? generatedCoupons.map((coupon) => (
                  <div
                    key={coupon.coupon_id || coupon.code}
                    className="rounded-2xl border border-emerald-200 bg-emerald-50/80 px-4 py-3"
                  >
                    <div className="font-mono text-sm font-semibold tracking-[0.18em] text-slate-950">{coupon.code}</div>
                    <div className="mt-2 text-sm text-slate-600">
                      {getCouponTypeLabel(coupon)}
                      {' · '}
                      {formatCredit(coupon.credit_amount)} kredi
                      {' · '}
                      {getAccountPlanLabel(coupon.target_account_plan)}
                      {' · '}
                      {coupon.distribution_mode === 'counter'
                        ? `${coupon.redemption_count || 0}/${coupon.max_redemptions || 1} kullanildi`
                        : 'Tek kullanim'}
                    </div>
                  </div>
                )) : (
                  <div className="rounded-2xl border border-dashed border-slate-200 px-4 py-6 text-sm text-slate-500">
                    Henuz yeni kupon uretilmedi.
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="border-slate-200 bg-white shadow-sm shadow-slate-200/70">
              <CardHeader>
                <CardTitle>Mevcut kuponlar</CardTitle>
                <CardDescription>Kampanya ve kullanim durumuna gore filtreleyebilir, export alabilir ve secerek silebilirsin.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid gap-3 md:grid-cols-[1.4fr_0.9fr_auto_auto]">
                  <Input
                    className={CONTROL}
                    value={campaignFilter}
                    onChange={(event) => setCampaignFilter(event.target.value)}
                    placeholder="Kampanya ile filtrele"
                  />
                  <select
                    className={`${CONTROL} w-full px-3`}
                    value={usedStatusFilter}
                    onChange={(event) => setUsedStatusFilter(event.target.value)}
                  >
                    <option value="all">Tum durumlar</option>
                    <option value="unused">Kullanilmamis</option>
                    <option value="used">Kullanilmis</option>
                  </select>
                  <Button type="button" variant="outline" onClick={onExportText} disabled={!coupons.length}>
                    <Download className="size-4" />
                    Text export
                  </Button>
                  <Button
                    type="button"
                    variant="destructive"
                    onClick={onDeleteSelected}
                    disabled={!selectedCouponIds.length || deleting}
                  >
                    <Trash2 className="size-4" />
                    {deleting ? 'Siliniyor...' : 'Secilenleri sil'}
                  </Button>
                </div>
                <div className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                  <label className="inline-flex items-center gap-3">
                    <input type="checkbox" checked={allSelected} onChange={toggleSelectAll} />
                    Bu sayfadaki tum kuponlari sec
                  </label>
                  <span>{selectedCouponIds.length} kupon secili</span>
                </div>
                {loading ? (
                  <div className="rounded-2xl border border-dashed border-slate-200 px-4 py-6 text-sm text-slate-500">
                    Kuponlar yukleniyor...
                  </div>
                ) : coupons.length ? coupons.map((coupon) => (
                  <div
                    key={coupon.coupon_id || coupon.code}
                    className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4"
                  >
                    <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                      <div className="flex items-start gap-3">
                        <input
                          type="checkbox"
                          className="mt-1"
                          checked={selectedCouponIds.includes(Number(coupon.coupon_id))}
                          onChange={() => toggleCouponSelection(coupon.coupon_id)}
                        />
                        <div>
                          <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                            {coupon.campaign_name || 'Kampanya yok'}
                          </div>
                          <div className="font-mono text-sm font-semibold tracking-[0.16em] text-slate-950">{coupon.code}</div>
                          <div className="mt-1 text-sm text-slate-600">
                            {getCouponTypeLabel(coupon)}
                            {' · '}
                            {formatCredit(coupon.credit_amount)} kredi
                            {' · '}
                            {getAccountPlanLabel(coupon.target_account_plan)}
                            {' · '}
                            {coupon.distribution_mode === 'counter'
                              ? `${coupon.redemption_count || 0}/${coupon.max_redemptions || 1} kullanildi`
                              : 'Tek kullanim'}
                          </div>
                        </div>
                      </div>
                      <div className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${coupon.is_used ? 'bg-slate-900 text-white' : 'bg-emerald-100 text-emerald-700'}`}>
                        {getCouponStatusLabel(coupon)}
                      </div>
                    </div>
                    <div className="mt-3 grid gap-2 text-xs text-slate-500 md:grid-cols-4">
                      <div>Kampanya: <span className="font-medium text-slate-700">{coupon.campaign_name || '-'}</span></div>
                      <div>Olusturma: <span className="font-medium text-slate-700">{formatDate(coupon.created_at)}</span></div>
                      <div>Son kullanan: <span className="font-medium text-slate-700">{coupon.used_by_username || '-'}</span></div>
                      <div>Kullanim: <span className="font-medium text-slate-700">{coupon.redemption_count || 0} / {coupon.max_redemptions || 1}</span></div>
                    </div>
                  </div>
                )) : (
                  <div className="rounded-2xl border border-dashed border-slate-200 px-4 py-6 text-sm text-slate-500">
                    Henuz kupon yok.
                  </div>
                )}
                <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="text-sm text-slate-500">
                    Toplam {totalCount} kupon, sayfa {currentPage} / {totalPages}
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      disabled={currentPage <= 1 || loading}
                      onClick={() => setCurrentPage((value) => Math.max(1, value - 1))}
                    >
                      Onceki
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      disabled={currentPage >= totalPages || loading}
                      onClick={() => setCurrentPage((value) => Math.min(totalPages, value + 1))}
                    >
                      Sonraki
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}
