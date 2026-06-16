import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  Bot,
  CreditCard,
  LogOut,
  Settings2,
  SlidersHorizontal,
  UserRound,
  WalletCards,
  ArrowRight,
  ShieldAlert,
  Save,
  RotateCcw,
  UserPlus,
  Trash2,
  History,
  Info
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogOverlay } from '@/components/ui/dialog'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'
import { useAuth } from '../../auth/useAuth.js'
import { getApiDetail, getApiReason, humanizeApiError } from '../../../shared/api/contracts.js'
import yargucuLogoBlack from '../../../logopack/yargucu-logo-siyah.svg'

const BASE_SECTIONS = [
  { key: 'account', label: 'Hesap', icon: UserRound },
  { key: 'credit', label: 'Kredi', icon: WalletCards },
  { key: 'payment', label: 'Ödeme', icon: CreditCard },
  { key: 'ai', label: 'Yapay Zeka', icon: Bot },
  { key: 'prefs', label: 'Tercihler', icon: SlidersHorizontal },
  { key: 'general', label: 'Genel', icon: Settings2 },
  { key: 'subaccounts', label: 'Alt Hesaplar', icon: UserPlus },
]

const SECTION_CONTENT = {
  account: {
    title: 'Hesap Bilgileri',
    description: 'Profil bilgilerinizi ve giriş ayarlarınızı buradan yönetin.',
  },
  credit: {
    title: 'Kredi ve Kullanım',
    description: 'Mevcut kredi bakiyenizi ve tahmini kullanım sürenizi görüntüleyin.',
  },
  payment: {
    title: 'Ödeme Ayarları',
    description: 'Paket ve faturalandırma süreçlerini buradan takip edin.',
  },
  ai: {
    title: 'Yapay Zeka Tercihleri',
    description: 'AI asistanınızın yanıt seviyesini ve çalışma derinliğini özelleştirin.',
  },
  prefs: {
    title: 'Kişisel Tercihler',
    description: 'Kullanıcı deneyimi ve uygulama tercihlerini yönetin.',
  },
  general: {
    title: 'Genel Ayarlar',
    description: 'Uygulama genelindeki varsayılan davranışlar ve sistem ayarları.',
  },
  subaccounts: {
    title: 'Alt Hesap Yönetimi',
    description: 'Kurumsal hesaplar için alt kullanıcı tanımlama ve kredi atama.',
  },
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

const CONTACT_PHONE_NUMBER = '+90 552 202 2089'
const CONTACT_PHONE_HREF = 'tel:+905522022089'

function getAccountPlanLabel(plan) {
  const key = String(plan || '').trim().toLowerCase()
  return ACCOUNT_PLAN_LABELS[key] || 'Ücretsiz'
}

function InlineFeedback({ tone = 'success', children }) {
  return (
    <div
      className={cn(
        'inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium',
        tone === 'success' && 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400',
        tone === 'error' && 'bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-400',
      )}
    >
      <div className={cn('h-1.5 w-1.5 rounded-full', tone === 'success' ? 'bg-emerald-500' : 'bg-rose-500')} />
      {children}
    </div>
  )
}

export function SettingsPage() {
  const { user, request, refreshMe, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window === 'undefined') return false
    return window.innerWidth <= 1024
  })
  const [isPaymentContactOpen, setIsPaymentContactOpen] = useState(false)

  // --- State Hooks ---
  const initial = useMemo(
    () => ({
      full_name: String(user?.full_name || ''),
      username: String(user?.username || ''),
      email: String(user?.email || ''),
    }),
    [user?.email, user?.full_name, user?.username],
  )

  const [fullName, setFullName] = useState(initial.full_name)
  const [username, setUsername] = useState(initial.username)
  const [email, setEmail] = useState(initial.email)

  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  const [aiConfig, setAiConfig] = useState({
    main_agent_verbosity: 'medium',
    main_agent_reasoning_effort: '',
    ictihat_agent_reasoning_effort: '',
    extra_instructions: '',
  })
  const [aiLoading, setAiLoading] = useState(false)
  const [aiSaving, setAiSaving] = useState(false)
  const [aiLoaded, setAiLoaded] = useState(false)
  const [aiError, setAiError] = useState('')
  const [aiSaved, setAiSaved] = useState(false)

  const [activeKey, setActiveKey] = useState('account')

  const [wipeLoading, setWipeLoading] = useState(false)
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [dangerError, setDangerError] = useState('')
  const [dangerSuccess, setDangerSuccess] = useState('')

  const [children, setChildren] = useState([])
  const [childrenLoading, setChildrenLoading] = useState(false)
  const [childrenError, setChildrenError] = useState('')
  const [childrenSuccess, setChildrenSuccess] = useState('')
  const [childCreateLoading, setChildCreateLoading] = useState(false)
  const [childCreditLoadingId, setChildCreditLoadingId] = useState(null)
  const [childDeleteLoadingId, setChildDeleteLoadingId] = useState(null)
  const [childrenReloadTick, setChildrenReloadTick] = useState(0)
  const [childCreditInputs, setChildCreditInputs] = useState({})

  const [multiAccountRequestLoading, setMultiAccountRequestLoading] = useState(false)
  const [multiAccountRequestError, setMultiAccountRequestError] = useState('')
  const [multiAccountRequestSuccess, setMultiAccountRequestSuccess] = useState('')

  const [usageSummary, setUsageSummary] = useState(null)
  const [usageSummaryLoading, setUsageSummaryLoading] = useState(false)
  const [usageSummaryError, setUsageSummaryError] = useState('')
  const [usageSummaryReloadTick, setUsageSummaryReloadTick] = useState(0)
  const [couponCode, setCouponCode] = useState('')
  const [couponRedeeming, setCouponRedeeming] = useState(false)
  const [couponRedeemError, setCouponRedeemError] = useState('')
  const [couponRedeemSuccess, setCouponRedeemSuccess] = useState('')
  const [couponConfirmDialogOpen, setCouponConfirmDialogOpen] = useState(false)
  const [pendingCouponConfirmation, setPendingCouponConfirmation] = useState(null)

  const [childForm, setChildForm] = useState({
    full_name: '',
    username: '',
    email: '',
    password: '',
    allocated_credit: '',
  })

  // --- Computed ---
  const isParentAccount = user?.account_type === 'parent'
  const isChildAccount = user?.account_type === 'child'
  const isStandaloneAccount = !isParentAccount && !isChildAccount
  const canDeleteAccount = user?.permissions?.can_delete_account !== false
  const canWipeData = user?.permissions?.can_wipe_data !== false

  const sections = useMemo(() => {
    if (isChildAccount) return BASE_SECTIONS.filter((section) => section.key !== 'subaccounts')
    return BASE_SECTIONS
  }, [isChildAccount])

  // --- Effects ---
  useEffect(() => {
    setFullName(initial.full_name)
    setUsername(initial.username)
    setEmail(initial.email)
  }, [initial])

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth <= 1024)
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  useEffect(() => {
    if (!isPaymentContactOpen) return undefined
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') setIsPaymentContactOpen(false)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isPaymentContactOpen])

  useEffect(() => {
    const nextKey = location.state?.activeKey || 'account'
    if (sections.some(s => s.key === nextKey)) {
      setActiveKey(nextKey)
    }
  }, [location.state, sections])

  useEffect(() => {
    if (saved) {
      const t = setTimeout(() => setSaved(false), 2000)
      return () => clearTimeout(t)
    }
  }, [saved])

  useEffect(() => {
    if (aiSaved) {
      const t = setTimeout(() => setAiSaved(false), 2000)
      return () => clearTimeout(t)
    }
  }, [aiSaved])

  // AI Config Loader
  useEffect(() => {
    if (activeKey !== 'ai' || aiLoaded) return
    let cancelled = false
    const loadAiConfig = async () => {
      setAiLoading(true)
      try {
        const data = await request('/v1/user/app-config', { method: 'GET' })
        if (!cancelled) {
          const next = data?.config || {}
          setAiConfig({
            main_agent_verbosity: String(next?.main_agent_verbosity || 'medium'),
            main_agent_reasoning_effort: String(next?.main_agent_reasoning_effort || ''),
            ictihat_agent_reasoning_effort: String(next?.ictihat_agent_reasoning_effort || ''),
            extra_instructions: String(next?.extra_instructions || ''),
          })
          setAiLoaded(true)
        }
      } catch (err) {
        if (!cancelled) setAiError(humanizeApiError(err, 'Yapay zeka ayarları yüklenemedi'))
      } finally {
        if (!cancelled) setAiLoading(false)
      }
    }
    loadAiConfig()
    return () => { cancelled = true }
  }, [activeKey, aiLoaded, request])

  // Subaccounts Loader
  useEffect(() => {
    if (!isParentAccount) return
    let cancelled = false
    const loadChildren = async () => {
      setChildrenLoading(true)
      try {
        const data = await request('/v1/accounts/children', { method: 'GET' })
        if (!cancelled) {
          const nextChildren = Array.isArray(data?.children) ? data.children : []
          setChildren(nextChildren)
          setChildCreditInputs(Object.fromEntries(nextChildren.map(c => [String(c.user_id), String(c.credit || 0)])))
        }
      } catch (err) {
        if (!cancelled) setChildrenError(humanizeApiError(err, 'Alt hesaplar yüklenemedi'))
      } finally {
        if (!cancelled) setChildrenLoading(false)
      }
    }
    loadChildren()
    return () => { cancelled = true }
  }, [isParentAccount, childrenReloadTick, request])

  // Credit Usage Loader
  useEffect(() => {
    if (activeKey !== 'credit') return
    let cancelled = false
    const loadUsage = async () => {
      setUsageSummaryLoading(true)
      setUsageSummaryError('')
      try {
        const data = await request('/v1/user/credit-usage-summary', { method: 'GET' })
        if (!cancelled) setUsageSummary(data?.summary || null)
      } catch (err) {
        if (!cancelled) setUsageSummaryError(humanizeApiError(err, 'Kullanım özeti yüklenemedi'))
      } finally {
        if (!cancelled) setUsageSummaryLoading(false)
      }
    }
    loadUsage()
    return () => { cancelled = true }
  }, [activeKey, request, usageSummaryReloadTick])

  // --- Handlers ---
  const onSubmitAccount = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      await request('/v1/auth/me', {
        method: 'PATCH',
        body: { full_name: fullName.trim(), username: username.trim(), email: email.trim() }
      })
      await refreshMe?.()
      setSaved(true)
    } catch (err) {
      setError(humanizeApiError(err, 'Kaydedilemedi'))
    } finally {
      setSaving(false)
    }
  }

  const onAiSubmit = async (e) => {
    e.preventDefault()
    setAiSaving(true)
    setAiError('')
    try {
      const data = await request('/v1/user/app-config', {
        method: 'PATCH',
        body: {
          main_agent_verbosity: aiConfig.main_agent_verbosity || null,
          main_agent_reasoning_effort: aiConfig.main_agent_reasoning_effort || null,
          ictihat_agent_reasoning_effort: aiConfig.ictihat_agent_reasoning_effort || null,
          extra_instructions: aiConfig.extra_instructions || null,
        }
      })
      const next = data?.config || {}
      setAiConfig({
        main_agent_verbosity: String(next?.main_agent_verbosity || 'medium'),
        main_agent_reasoning_effort: String(next?.main_agent_reasoning_effort || ''),
        ictihat_agent_reasoning_effort: String(next?.ictihat_agent_reasoning_effort || ''),
        extra_instructions: String(next?.extra_instructions || ''),
      })
      setAiSaved(true)
    } catch (err) {
      setAiError(humanizeApiError(err, 'Yapay zeka ayarları kaydedilemedi'))
    } finally {
      setAiSaving(false)
    }
  }

  const onLogoutClick = async () => {
    await logout?.()
    navigate('/login', { replace: true })
  }

  const applyRedeemSuccess = async (data) => {
    const grantedCredit = Number(data?.credit_amount ?? 0)
    const nextPlanLabel = getAccountPlanLabel(data?.current_account_plan)
    setCouponCode('')
    if (grantedCredit > 0 && data?.current_account_plan) {
      setCouponRedeemSuccess(
        `${formatCredit(grantedCredit)} kredi tanımlandı. Aktif paketin ${nextPlanLabel} oldu.`,
      )
    } else if (grantedCredit > 0) {
      setCouponRedeemSuccess(`${formatCredit(grantedCredit)} kredi tanımlandı.`)
    } else {
      setCouponRedeemSuccess(`Kod uygulandı. Aktif paketin ${nextPlanLabel} oldu.`)
    }
    await refreshMe?.()
    setUsageSummaryReloadTick((value) => value + 1)
  }

  const onConfirmCouponRedeem = async () => {
    if (!pendingCouponConfirmation?.code) return
    setCouponRedeeming(true)
    setCouponRedeemError('')
    try {
      const data = await request('/v1/coupons/redeem', {
        method: 'POST',
        body: { code: pendingCouponConfirmation.code, confirm_account_plan_change: true },
      })
      setCouponConfirmDialogOpen(false)
      setPendingCouponConfirmation(null)
      await applyRedeemSuccess(data)
    } catch (err) {
      setCouponRedeemError(humanizeApiError(err, 'Kod kullanilamadi'))
    } finally {
      setCouponRedeeming(false)
    }
  }

  const onRedeemCoupon = async (event) => {
    event.preventDefault()
    setCouponRedeeming(true)
    setCouponRedeemError('')
    setCouponRedeemSuccess('')
    try {
      const data = await request('/v1/coupons/redeem', {
        method: 'POST',
        body: { code: couponCode.trim(), confirm_account_plan_change: false },
      })
      await applyRedeemSuccess(data)
    } catch (err) {
      if (getApiReason(err) === 'coupon_plan_change_confirmation_required') {
        const detail = getApiDetail(err) || {}
        setPendingCouponConfirmation({
          code: couponCode.trim(),
          currentPlan: getAccountPlanLabel(detail?.current_account_plan),
          targetPlan: getAccountPlanLabel(detail?.target_account_plan),
          coupon: detail?.coupon || null,
        })
        setCouponConfirmDialogOpen(true)
      } else {
        setCouponRedeemError(humanizeApiError(err, 'Kod kullanilamadi'))
      }
    } finally {
      setCouponRedeeming(false)
    }
  }

  const onWipeData = async () => {
    if (!canWipeData || !window.confirm('Tüm verileriniz kalıcı olarak silinecek. Emin misiniz?')) return
    setWipeLoading(true)
    setDangerError('')
    try {
      await request('/v1/accounts/me/wipe-data', { method: 'POST' })
      setDangerSuccess('Tüm veriler temizlendi.')
    } catch (err) {
      setDangerError(humanizeApiError(err, 'Veriler silinemedi'))
    } finally {
      setWipeLoading(false)
    }
  }

  const onDeleteAccount = async () => {
    if (!canDeleteAccount || !window.confirm('Hesabınız kalıcı olarak kapatılacak. Verileriniz geri getirilemez. Devam?')) return
    setDeleteLoading(true)
    try {
      await request('/v1/accounts/me', { method: 'DELETE' })
      await logout?.()
    } catch (err) {
      setDangerError(humanizeApiError(err, 'Hesap silinemedi'))
      setDeleteLoading(false)
    }
  }

  const onCreateChild = async (e) => {
    e.preventDefault()
    setChildCreateLoading(true)
    setChildrenError('')
    try {
      await request('/v1/accounts/children', {
        method: 'POST',
        body: {
          ...childForm,
          allocated_credit: Number(childForm.allocated_credit || 0)
        }
      })
      setChildForm({ full_name: '', username: '', email: '', password: '', allocated_credit: '' })
      setChildrenSuccess('Alt hesap oluşturuldu.')
      setChildrenReloadTick(v => v + 1)
      await refreshMe?.()
    } catch (err) {
      setChildrenError(humanizeApiError(err, 'Alt hesap oluşturulamadı'))
    } finally {
      setChildCreateLoading(false)
    }
  }

  const onSaveChildCredit = async (childUserId) => {
    const draft = childCreditInputs[String(childUserId)] ?? '0'
    setChildCreditLoadingId(childUserId)
    try {
      await request(`/v1/accounts/children/${childUserId}/credit`, {
        method: 'PATCH',
        body: { credit: Number(draft || 0) }
      })
      setChildrenSuccess('Kredi güncellendi.')
      setChildrenReloadTick(v => v + 1)
      await refreshMe?.()
    } catch (err) {
      setChildrenError(humanizeApiError(err, 'Kredi güncellenemedi'))
    } finally {
      setChildCreditLoadingId(null)
    }
  }

  const onDeleteChild = async (childUserId) => {
    if (!window.confirm('Bu alt hesap silinecek. Krediler iade edilecektir. Emin misiniz?')) return
    setChildDeleteLoadingId(childUserId)
    try {
      await request(`/v1/accounts/children/${childUserId}`, { method: 'DELETE' })
      setChildrenSuccess('Alt hesap silindi.')
      setChildrenReloadTick(v => v + 1)
      await refreshMe?.()
    } catch (err) {
      setChildrenError(humanizeApiError(err, 'Alt hesap silinemedi'))
    } finally {
      setChildDeleteLoadingId(null)
    }
  }

  const onRequestMultiAccount = async (source) => {
    setMultiAccountRequestLoading(true)
    setMultiAccountRequestError('')
    try {
      const message = `Kullanıcı Çoklu Hesap Talebi (${source})\nUser: ${user?.username} (${user?.email})\nPlan: ${user?.account_plan}`
      await request('/v1/support/mail', { method: 'POST', body: { message } })
      setMultiAccountRequestSuccess('Talebiniz alındı. Size en kısa sürede dönüş yapacağız.')
    } catch (err) {
      setMultiAccountRequestError(humanizeApiError(err, 'Talep gönderilemedi'))
    } finally {
      setMultiAccountRequestLoading(false)
    }
  }

  const onPaymentContactClick = () => {
    if (isMobile) {
      window.location.href = CONTACT_PHONE_HREF
      return
    }
    setIsPaymentContactOpen(true)
  }

  function formatCredit(value) {
    const num = Number(value)
    if (!Number.isFinite(num)) return '0'
    return num.toLocaleString('tr-TR', { maximumFractionDigits: 2 })
  }

  const availableCredit = Number(user?.credit_summary?.available_credit ?? user?.credit ?? 0)
  const totalCredit = Number(user?.credit_summary?.total_credit ?? availableCredit)
  const reservedCredit = Number(user?.credit_summary?.reserved_credit ?? 0)
  const accountPlanLabel = getAccountPlanLabel(user?.account_plan)
  const accountTypeLabel = isParentAccount ? 'Üst Hesap' : isChildAccount ? 'Alt Hesap' : 'Bağımsız'
  const dailyAvg = Number(usageSummary?.daily_average_credit ?? 0)
  const estDays = dailyAvg > 0 ? Math.floor(availableCredit / dailyAvg) : null

  return (
    <div className="relative min-h-screen bg-background font-sans text-foreground antialiased selection:bg-foreground/10">
      {/* --- Sticky Header --- */}
      <header className="app-safe-top-header sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-[1400px] items-center justify-between px-4 lg:px-8">
          <div className="flex items-center gap-6">
            <Link to="/chat" className="group flex items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground">
              <ArrowLeft size={14} className="transition-transform group-hover:-translate-x-0.5" />
              <span>Sohbete Dön</span>
            </Link>
            <Separator orientation="vertical" className="h-4" />
            <div className="flex items-center gap-2">
              <Settings2 size={16} className="text-muted-foreground" />
              <h1 className="text-sm font-semibold tracking-tight">Ayarlar</h1>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <img src={yargucuLogoBlack} alt="Yargucu" className="hidden h-5 w-auto opacity-90 sm:block" />
          </div>
        </div>
      </header>

      {/* --- Main Content Layout --- */}
      <main className="mx-auto max-w-[1400px] px-4 py-8 lg:px-8 lg:py-12">
        <Tabs value={activeKey} onValueChange={setActiveKey} orientation={isMobile ? "horizontal" : "vertical"}>
          <div className="flex flex-col gap-8 lg:flex-row lg:gap-12">
            
            {/* --- Navigation Sidebar --- */}
            <aside className="w-full shrink-0 lg:w-[260px] lg:space-y-6">
              <div className="space-y-1 overflow-x-auto pb-2 scrollbar-hide lg:overflow-visible lg:pb-0">
                <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground/60 hidden lg:block">
                  MENÜ
                </div>
                <TabsList className="flex h-auto w-max min-w-full flex-row justify-start gap-1 bg-transparent p-0 lg:w-full lg:flex-col lg:items-stretch lg:justify-start">
                  {sections.map(section => (
                    <TabsTrigger
                      key={section.key}
                      value={section.key}
                      className="relative justify-start gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors data-[state=active]:bg-muted data-[state=active]:text-foreground data-[state=inactive]:text-muted-foreground hover:bg-muted/50 data-[state=active]:shadow-none lg:w-full"
                    >
                      <section.icon size={16} className={cn("shrink-0", activeKey === section.key ? "text-foreground" : "text-muted-foreground/70")} />
                      <span className="hidden lg:inline-block">{section.label}</span>
                      {activeKey === section.key && (
                        <div className="absolute right-2 hidden h-1.5 w-1.5 rounded-full bg-foreground lg:block" />
                      )}
                    </TabsTrigger>
                  ))}
                </TabsList>
              </div>

              <div className="hidden lg:block">
                <Separator className="my-6" />
                <div className="space-y-4 px-1">
                  <div className="rounded-xl border border-border bg-card p-4 transition-all hover:bg-accent/5">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted text-xs font-bold uppercase ring-1 ring-border">
                        {user?.full_name?.charAt(0) || user?.username?.charAt(0) || 'U'}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-foreground">{user?.full_name || user?.username}</p>
                        <p className="truncate text-[10px] text-muted-foreground uppercase tracking-widest">{accountPlanLabel}</p>
                      </div>
                    </div>
                  </div>

                  <Button
                    variant="outline"
                    className="w-full justify-start gap-3 border-border bg-background text-muted-foreground transition-all hover:bg-rose-50 hover:text-rose-700 dark:hover:bg-rose-500/10 dark:hover:text-rose-400"
                    onClick={onLogoutClick}
                  >
                    <LogOut size={16} />
                    <span className="font-semibold">Oturumu Kapat</span>
                  </Button>
                </div>
              </div>
            </aside>

            {/* --- Content Area --- */}
            <div className="flex-1 min-w-0 space-y-10">
              {/* --- ACCOUNT SECTION --- */}
              <TabsContent value="account" className="mt-0 space-y-8 animate-in fade-in slide-in-from-bottom-2">
              <div className="border-b border-border pb-6">
                <h2 className="text-3xl font-bold tracking-tight text-foreground">{SECTION_CONTENT.account.title}</h2>
                <p className="mt-1.5 text-[15px] text-muted-foreground">{SECTION_CONTENT.account.description}</p>
              </div>

              <div className="grid gap-8 lg:grid-cols-3">
                <Card className="lg:col-span-2 border-border shadow-sm">
                  <CardHeader>
                    <CardTitle className="text-lg">Profil Ayarları</CardTitle>
                    <CardDescription>Bilgileriniz uygulama genelinde görünür olacaktır.</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <form onSubmit={onSubmitAccount} className="space-y-6">
                      <div className="grid gap-4 sm:grid-cols-2">
                        <div className="space-y-2">
                          <Label htmlFor="full_name">Ad Soyad</Label>
                          <Input
                            id="full_name"
                            value={fullName}
                            onChange={e => setFullName(e.target.value)}
                            placeholder="Ad Soyad"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="username">Kullanıcı Adı</Label>
                          <Input
                            id="username"
                            value={username}
                            onChange={e => setUsername(e.target.value)}
                            placeholder="@kullanici_adi"
                          />
                        </div>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="email">E-posta Adresi</Label>
                        <Input
                          id="email"
                          type="email"
                          value={email}
                          onChange={e => setEmail(e.target.value)}
                          placeholder="mail@ornek.com"
                        />
                      </div>
                      
                      <div className="flex flex-wrap items-center gap-4">
                        <Button type="submit" disabled={saving} className="min-w-[120px]">
                          {saving ? 'Kaydediliyor...' : 'Güncelle'}
                          {!saving && <Save size={14} className="ml-2" />}
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          onClick={() => { setFullName(initial.full_name); setUsername(initial.username); setEmail(initial.email); }}
                          className="text-muted-foreground"
                        >
                          İptal
                        </Button>
                        {error && <InlineFeedback tone="error">{error}</InlineFeedback>}
                        {saved && <InlineFeedback tone="success">Kaydedildi</InlineFeedback>}
                      </div>
                    </form>
                  </CardContent>
                </Card>

                <div className="space-y-6">
                  <Card className="border-border shadow-sm bg-muted/30">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Hesap Durumu</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-foreground">Tür</span>
                        <Badge variant="secondary" className="font-semibold">{accountTypeLabel}</Badge>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-foreground">Plan</span>
                        <Badge variant="outline" className="border-emerald-500/50 text-emerald-700 bg-emerald-500/5">{accountPlanLabel}</Badge>
                      </div>
                    </CardContent>
                  </Card>

                  {isStandaloneAccount && (
                    <Card className="border-dashed border-border bg-transparent shadow-none">
                      <CardContent className="pt-6">
                        <p className="text-xs leading-relaxed text-muted-foreground mb-4">
                          Çoklu hesap yönetimi için hesabınızı yükseltmek ister misiniz?
                        </p>
                        <Button
                          variant="outline"
                          size="sm"
                          className="w-full text-[11px] font-bold uppercase tracking-wider"
                          onClick={() => onRequestMultiAccount('account_sidebar')}
                          disabled={multiAccountRequestLoading}
                        >
                          Üst Hesap Talebi
                          <ArrowRight size={12} className="ml-2" />
                        </Button>
                        {multiAccountRequestSuccess && (
                          <p className="mt-3 text-[10px] text-emerald-600 font-medium">Talep iletildi.</p>
                        )}
                      </CardContent>
                    </Card>
                  )}
                </div>
              </div>

              {/* Danger Zone */}
              <Card className="border-rose-200 dark:border-rose-900/50 bg-rose-500/5 overflow-hidden">
                <div className="bg-rose-600/10 px-6 py-3 border-b border-rose-200 dark:border-rose-900/50 flex items-center gap-2">
                  <ShieldAlert size={16} className="text-rose-700" />
                  <span className="text-xs font-bold uppercase tracking-widest text-rose-700">Tehlikeli Bölge</span>
                </div>
                <CardContent className="pt-1 grid gap-6 md:grid-cols-2">
                  <div className="space-y-4">
                    <div>
                      <h4 className="text-sm font-bold text-foreground">Verileri Temizle</h4>
                      <p className="text-xs text-muted-foreground mt-1">Sohbet geçmişiniz, dosyalarınız ve tüm içerikler silinir. Hesap korunur.</p>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={onWipeData}
                      disabled={wipeLoading || !canWipeData}
                      className="border-rose-200 text-rose-700 hover:bg-rose-100 hover:text-rose-800"
                    >
                      {wipeLoading ? 'Siliniyor...' : 'Tüm Veriyi Sil'}
                    </Button>
                  </div>
                  <div className="space-y-4">
                    <div>
                      <h4 className="text-sm font-bold text-foreground font-sans">Hesabı Kapat</h4>
                      <p className="text-xs text-muted-foreground mt-1">Erişiminiz sonlandırılır ve tüm verileriniz kalıcı olarak imha edilir.</p>
                    </div>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={onDeleteAccount}
                      disabled={deleteLoading || !canDeleteAccount}
                    >
                      {deleteLoading ? 'Kapatılıyor...' : 'Hesabı Kalıcı Olarak Sil'}
                    </Button>
                  </div>
                </CardContent>
                {dangerError && <div className="px-6 pb-4"><InlineFeedback tone="error">{dangerError}</InlineFeedback></div>}
                {dangerSuccess && <div className="px-6 pb-4"><InlineFeedback tone="success">{dangerSuccess}</InlineFeedback></div>}
              </Card>

              {/* --- Mobile Profile/Logout Footer --- */}
              <div className="lg:hidden pt-4">
                <Separator className="mb-6" />
                <div className="rounded-2xl border border-border bg-card shadow-sm overflow-hidden">
                  <div className="p-5 flex items-center gap-4 bg-muted/30 border-b border-border/50">
                    <div className="flex h-12 w-12 items-center justify-center rounded-full bg-background text-sm font-bold uppercase ring-1 ring-border shadow-sm">
                      {user?.full_name?.charAt(0) || user?.username?.charAt(0) || 'U'}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-base font-bold text-foreground">{user?.full_name || user?.username}</p>
                      <p className="truncate text-xs text-muted-foreground font-semibold uppercase tracking-widest">{accountPlanLabel}</p>
                    </div>
                  </div>
                  <div className="p-3">
                    <Button
                      variant="ghost"
                      className="w-full justify-start gap-3 text-rose-600 hover:bg-rose-50 hover:text-rose-700 dark:hover:bg-rose-500/10 dark:hover:text-rose-400 font-bold"
                      onClick={onLogoutClick}
                    >
                      <LogOut size={18} />
                      Oturumu Kapat
                    </Button>
                  </div>
                </div>
              </div>
            </TabsContent>

            {/* --- CREDIT SECTION --- */}
            <TabsContent value="credit" className="mt-0 space-y-8 animate-in fade-in slide-in-from-bottom-2">
              <div className="border-b border-border pb-6">
                <h2 className="text-3xl font-bold tracking-tight text-foreground">{SECTION_CONTENT.credit.title}</h2>
                <p className="mt-1.5 text-[15px] text-muted-foreground">{SECTION_CONTENT.credit.description}</p>
              </div>

              <div className="grid gap-6 md:grid-cols-3">
                <Card className="border-border shadow-sm">
                  <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                    <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Kullanılabilir</CardTitle>
                    <WalletCards size={16} className="text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-3xl font-bold text-emerald-600">{formatCredit(availableCredit)}</div>
                    <p className="text-[10px] text-muted-foreground mt-1 font-medium italic">Kullanıma hazır bakiye</p>
                  </CardContent>
                </Card>
                <Card className="border-border shadow-sm">
                  <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                    <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Toplam</CardTitle>
                    <History size={16} className="text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-3xl font-bold">{formatCredit(totalCredit)}</div>
                    <p className="text-[10px] text-muted-foreground mt-1 font-medium">Tanımlı toplam tutar</p>
                  </CardContent>
                </Card>
                {isParentAccount && (
                  <Card className="border-border shadow-sm">
                    <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                      <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Ayrılan</CardTitle>
                      <UserPlus size={16} className="text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                      <div className="text-3xl font-bold text-amber-600">{formatCredit(reservedCredit)}</div>
                      <p className="text-[10px] text-muted-foreground mt-1 font-medium">Alt hesaplardaki bakiye</p>
                    </CardContent>
                  </Card>
                )}
              </div>

              <Card className="border-border shadow-sm">
                <CardHeader>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <WalletCards size={18} className="text-muted-foreground" />
                    Kod Kullan
                  </CardTitle>
                  <CardDescription>
                    Elindeki kupon veya kampanya kodunu girerek kredi yukleyebilir ya da hesabini yeni bir pakete gecirebilirsin.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <form className="flex flex-col gap-3 md:flex-row" onSubmit={onRedeemCoupon}>
                    <Input
                      value={couponCode}
                      onChange={(event) => setCouponCode(event.target.value.toUpperCase())}
                      placeholder="Kupon veya kampanya kodu"
                      className="md:flex-1"
                      autoCapitalize="characters"
                      autoCorrect="off"
                      spellCheck={false}
                      disabled={couponRedeeming}
                    />
                    <Button type="submit" disabled={couponRedeeming || !couponCode.trim()}>
                      {couponRedeeming ? 'Uygulaniyor...' : 'Kodu kullan'}
                    </Button>
                  </form>
                  {couponRedeemError ? (
                    <InlineFeedback tone="error">{couponRedeemError}</InlineFeedback>
                  ) : null}
                  {couponRedeemSuccess ? (
                    <InlineFeedback tone="success">{couponRedeemSuccess}</InlineFeedback>
                  ) : null}
                </CardContent>
              </Card>

              <Dialog
                open={couponConfirmDialogOpen}
                onOpenChange={(open) => {
                  setCouponConfirmDialogOpen(open)
                  if (!open) setPendingCouponConfirmation(null)
                }}
              >
                <DialogOverlay className="fixed inset-0 z-40 bg-slate-950/45 backdrop-blur-sm" />
                <DialogContent className="fixed left-1/2 top-1/2 z-50 w-[calc(100vw-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-3xl border border-border bg-background p-0 shadow-2xl">
                  <div className="p-6 sm:p-7">
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 flex h-10 w-10 items-center justify-center rounded-full bg-amber-100 text-amber-700">
                        <ShieldAlert size={18} />
                      </div>
                      <div className="min-w-0">
                        <h3 className="text-lg font-bold text-foreground">Paket Degisimi Onayi</h3>
                        <p className="mt-2 text-sm leading-6 text-muted-foreground">
                          Bu kod hesap paketini <span className="font-semibold text-foreground">{pendingCouponConfirmation?.currentPlan || '-'}</span> paketinden{' '}
                          <span className="font-semibold text-foreground">{pendingCouponConfirmation?.targetPlan || '-'}</span> paketine gecirecek.
                        </p>
                        <p className="mt-2 text-sm leading-6 text-muted-foreground">
                          Devam edersen kod uygulanir ve yeni paketin hemen aktif olur.
                        </p>
                        {pendingCouponConfirmation?.coupon ? (
                          <div className="mt-4 rounded-2xl border border-border bg-muted/40 px-4 py-3 text-sm text-muted-foreground">
                            <div>
                              Kampanya: <span className="font-medium text-foreground">{pendingCouponConfirmation.coupon.campaign_name || '-'}</span>
                            </div>
                            <div>
                              Kod: <span className="font-mono font-medium text-foreground">{pendingCouponConfirmation.coupon.code || '-'}</span>
                            </div>
                          </div>
                        ) : null}
                      </div>
                    </div>
                    <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => {
                          setCouponConfirmDialogOpen(false)
                          setPendingCouponConfirmation(null)
                          setCouponRedeemError('Kod kullanimi iptal edildi.')
                        }}
                        disabled={couponRedeeming}
                      >
                        Vazgec
                      </Button>
                      <Button type="button" onClick={onConfirmCouponRedeem} disabled={couponRedeeming}>
                        {couponRedeeming ? 'Uygulaniyor...' : 'Onayla ve Uygula'}
                      </Button>
                    </div>
                  </div>
                </DialogContent>
              </Dialog>

              <Card className="border-border shadow-sm bg-accent/10">
                <CardHeader>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <Info size={18} className="text-blue-500" />
                    Kullanım Analizi
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  {usageSummaryLoading ? (
                    <div className="flex items-center gap-3 py-4 text-muted-foreground italic">
                      <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                      Analiz ediliyor...
                    </div>
                  ) : usageSummaryError ? (
                    <p className="text-rose-600 font-medium">{usageSummaryError}</p>
                  ) : usageSummary?.has_enough_data && estDays != null ? (
                    <div className="grid gap-6 md:grid-cols-2">
                       <div className="space-y-2">
                          <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground italic">Tahmini Kalan Süre</p>
                          <div className="text-4xl font-black tracking-tighter">~{estDays} GÜN</div>
                       </div>
                       <div className="text-sm leading-relaxed text-muted-foreground border-l border-border pl-6">
                         Son <span className="font-bold text-foreground">{Number(usageSummary?.window_days || 14)}</span> günlük kullanım verilerinize göre günlük ortalama tüketiminiz <span className="font-bold text-foreground">{formatCredit(dailyAvg)} kredi</span>. Mevcut bakiyeniz bu tempoyla <span className="font-bold text-foreground text-emerald-600">yaklaşık {estDays} gün</span> daha yeterli görünüyor.
                       </div>
                    </div>
                  ) : (
                    <div className="bg-muted/40 p-4 rounded-lg flex items-start gap-4">
                      <History size={20} className="text-muted-foreground mt-0.5" />
                      <div className="text-sm text-muted-foreground leading-relaxed">
                        Analiz verisi oluşturuluyor. Daha isabetli tahminler sunabilmemiz için birkaç günlük kullanım verisine daha ihtiyacımız var.
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* --- PAYMENT SECTION --- */}
            <TabsContent value="payment" className="mt-0 space-y-8 animate-in fade-in slide-in-from-bottom-2">
              <div className="border-b border-border pb-6">
                <h2 className="text-3xl font-bold tracking-tight text-foreground">{SECTION_CONTENT.payment.title}</h2>
                <p className="mt-1.5 text-[15px] text-muted-foreground">{SECTION_CONTENT.payment.description}</p>
              </div>
              <Card className="border-border">
                <CardContent className="pt-10 pb-12 flex flex-col items-center text-center">
                  <div className="h-16 w-16 bg-muted rounded-full flex items-center justify-center mb-6">
                    <CreditCard size={32} className="text-muted-foreground opacity-40" />
                  </div>
                  <h3 className="text-lg font-bold">Ödeme ve Paketler</h3>
                  <p className="max-w-md text-sm text-muted-foreground mt-2">
                    Mevcut planınız <span className="font-bold text-foreground">{accountPlanLabel}</span>. Ödeme sistemi pilot süreç sonrasında aktif hale getirilecektir.
                  </p>
                  <p className="mt-4 max-w-md text-sm text-muted-foreground">
                    Erken erişim sürecinde kullanmak mı istiyorsunuz? İletişime geçin.
                  </p>
                  <Button className="mt-5 !text-white hover:!text-white" type="button" onClick={onPaymentContactClick}>
                    Hemen Ara
                  </Button>
                </CardContent>
              </Card>
            </TabsContent>

            {/* --- AI SECTION --- */}
            <TabsContent value="ai" className="mt-0 space-y-8 animate-in fade-in slide-in-from-bottom-2">
              <div className="border-b border-border pb-6">
                <h2 className="text-3xl font-bold tracking-tight text-foreground">{SECTION_CONTENT.ai.title}</h2>
                <p className="mt-1.5 text-[15px] text-muted-foreground">{SECTION_CONTENT.ai.description}</p>
              </div>

              <Card className="border-border">
                <CardHeader>
                  <CardTitle className="text-lg">Agent Davranışları</CardTitle>
                </CardHeader>
                <CardContent>
                  <form onSubmit={onAiSubmit} className="space-y-8">
                    {aiLoading && <div className="text-xs italic text-muted-foreground animate-pulse">Konfigürasyon yükleniyor...</div>}
                    
                    <div className="grid gap-8 md:grid-cols-2">
                      <div className="space-y-3">
                        <Label className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Yanıt Detay Seviyesi</Label>
                        <select
                          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                          value={aiConfig.main_agent_verbosity}
                          onChange={e => { setAiSaved(false); setAiConfig(p => ({ ...p, main_agent_verbosity: e.target.value })); }}
                          disabled={aiSaving}
                        >
                          <option value="low">Özet (Düşük)</option>
                          <option value="medium">Dengeli (Orta)</option>
                          <option value="high">Kapsamlı (Yüksek)</option>
                        </select>
                        <p className="text-[11px] text-muted-foreground leading-relaxed">Yanıtların uzunluğunu ve detay miktarını ayarlar.</p>
                      </div>

                      <div className="space-y-3">
                        <Label className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Düşünme Seviyesi (Reasoning)</Label>
                        <select
                          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                          value={aiConfig.main_agent_reasoning_effort}
                          onChange={e => { setAiSaved(false); setAiConfig(p => ({ ...p, main_agent_reasoning_effort: e.target.value })); }}
                          disabled={aiSaving}
                        >
                          <option value="">Sistem Varsayılanı</option>
                          <option value="none">Hızlı Yanıt (Kapalı)</option>
                          <option value="low">Hafif Analiz</option>
                          <option value="medium">Derin Analiz</option>
                          <option value="high">Gelişmiş Analiz</option>
                          <option value="xhigh">Maksimum Analiz</option>
                        </select>
                        <p className="text-[11px] text-gray-500 leading-relaxed">Yüksek seviyeler daha fazla kredi tüketebilir ve yanıt süresini uzatabilir.</p>
                      </div>

                      <div className="space-y-3">
                        <Label className="text-xs font-bold uppercase tracking-widest text-muted-foreground">İçtihat Tarama Derinliği</Label>
                        <select
                          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                          value={aiConfig.ictihat_agent_reasoning_effort}
                          onChange={e => { setAiSaved(false); setAiConfig(p => ({ ...p, ictihat_agent_reasoning_effort: e.target.value })); }}
                          disabled={aiSaving}
                        >
                          <option value="">Sistem Varsayılanı</option>
                          <option value="none">Hızlı Yanıt (Kapalı)</option>
                          <option value="low">Hafif Analiz</option>
                          <option value="medium">Derin Analiz</option>
                          <option value="high">Gelişmiş Analiz</option>
                          <option value="xhigh">Maksimum Analiz</option>
                        </select>
                         <p className="text-[11px] text-gray-500 leading-relaxed">İçtihat taramasında kullanılacak reasoning seviyesini belirler.</p>
                      </div>
                    </div>

                    <div className="space-y-3">
                      <Label className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Kalıcı Yönergeler</Label>
                      <Textarea
                        value={aiConfig.extra_instructions}
                        onChange={e => { setAiSaved(false); setAiConfig(p => ({ ...p, extra_instructions: e.target.value })); }}
                        placeholder="Örn: Daima maddeler halinde cevap ver / Hukuki dili sadeleştir."
                        className="min-h-[120px] bg-muted/20"
                        disabled={aiSaving}
                      />
                    </div>

                    <div className="flex flex-wrap items-center gap-4 pt-4">
                       <Button type="submit" disabled={aiSaving}>
                         {aiSaving ? 'Kaydediliyor...' : 'Tercihleri Uygula'}
                       </Button>
                       <Button type="button" variant="ghost" className="text-muted-foreground" onClick={() => setAiLoaded(false)}> Yenile </Button>
                       {aiError && <InlineFeedback tone="error">{aiError}</InlineFeedback>}
                       {aiSaved && <InlineFeedback tone="success">Ayarlar Uygulandı</InlineFeedback>}
                    </div>
                  </form>
                </CardContent>
              </Card>
            </TabsContent>

            {/* --- SUBACCOUNTS SECTION --- */}
            <TabsContent value="subaccounts" className="mt-0 space-y-8 animate-in fade-in slide-in-from-bottom-2">
              <div className="border-b border-border pb-6">
                <h2 className="text-3xl font-bold tracking-tight text-foreground">{SECTION_CONTENT.subaccounts.title}</h2>
                <p className="mt-1.5 text-[15px] text-muted-foreground">{SECTION_CONTENT.subaccounts.description}</p>
              </div>

              {isParentAccount ? (
                <div className="space-y-12">
                  <Card className="border-border bg-muted/20">
                    <CardHeader>
                      <CardTitle className="text-lg">Yeni Alt Hesap Tanımla</CardTitle>
                      <CardDescription>Oluşturulan kullanıcılar kendi şifreleriyle sisteme giriş yapabilir.</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <form onSubmit={onCreateChild} className="grid gap-6 md:grid-cols-2">
                        <div className="space-y-2">
                          <Label>Ad Soyad</Label>
                          <Input value={childForm.full_name} onChange={e => setChildForm(p=>({...p, full_name: e.target.value}))} placeholder="..." />
                        </div>
                        <div className="space-y-2">
                          <Label>Kullanıcı Adı</Label>
                          <Input value={childForm.username} onChange={e => setChildForm(p=>({...p, username: e.target.value}))} placeholder="..." />
                        </div>
                        <div className="space-y-2">
                          <Label>E-posta</Label>
                          <Input type="email" value={childForm.email} onChange={e => setChildForm(p=>({...p, email: e.target.value}))} placeholder="..." />
                        </div>
                        <div className="space-y-2">
                          <Label>Geçici Parola</Label>
                          <Input type="password" value={childForm.password} onChange={e => setChildForm(p=>({...p, password: e.target.value}))} placeholder="..." />
                        </div>
                        <div className="space-y-2 md:col-span-2">
                          <Label>Başlangıç Kredisi</Label>
                          <Input type="number" value={childForm.allocated_credit} onChange={e => setChildForm(p=>({...p, allocated_credit: e.target.value}))} placeholder="0" className="max-w-[200px]" />
                        </div>
                        <div className="md:col-span-2 flex items-center gap-4">
                           <Button type="submit" disabled={childCreateLoading}> {childCreateLoading ? 'Oluşturuluyor...' : 'Hesabı Tanımla'} </Button>
                           {childrenError && <InlineFeedback tone="error">{childrenError}</InlineFeedback>}
                           {childrenSuccess && <InlineFeedback tone="success">{childrenSuccess}</InlineFeedback>}
                        </div>
                      </form>
                    </CardContent>
                  </Card>

                  <div className="space-y-4">
                    <h3 className="text-sm font-bold uppercase tracking-widest text-muted-foreground">Kayıtlı Alt Hesaplar</h3>
                    <div className="grid gap-4">
                      {childrenLoading ? (
                        <div className="text-xs italic text-muted-foreground">Yükleniyor...</div>
                      ) : children.length ? (
                        children.map(child => (
                           <Card key={child.user_id} className="border-border hover:shadow-md transition-shadow">
                             <CardContent className="p-6 flex flex-col md:flex-row md:items-center justify-between gap-6">
                               <div className="flex items-center gap-4">
                                 <div className="h-10 w-10 rounded-full bg-accent flex items-center justify-center font-bold text-accent-foreground">{child.full_name?.charAt(0) || 'A'}</div>
                                 <div>
                                   <p className="font-bold">{child.full_name || child.username}</p>
                                   <p className="text-xs text-muted-foreground">{child.email || child.username}</p>
                                 </div>
                               </div>
                               <div className="flex flex-wrap items-center gap-4">
                                 <div className="flex items-center gap-2 border border-border rounded-lg px-3 py-1 bg-muted/30">
                                   <span className="text-[10px] uppercase font-bold text-muted-foreground">KREDİ:</span>
                                   <span className="font-mono font-bold">{formatCredit(child.credit)}</span>
                                 </div>
                                 <Input
                                    className="w-24 h-9"
                                    type="number"
                                    value={childCreditInputs[String(child.user_id)] || ''}
                                    onChange={e => setChildCreditInputs(p => ({...p, [String(child.user_id)]: e.target.value}))}
                                 />
                                 <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => onSaveChildCredit(child.user_id)}
                                    disabled={childCreditLoadingId === child.user_id}
                                 >
                                    {childCreditLoadingId === child.user_id ? '...' : 'Güncelle'}
                                 </Button>
                                 <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => onDeleteChild(child.user_id)}
                                    className="text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                                    disabled={childDeleteLoadingId === child.user_id}
                                 >
                                    <Trash2 size={16} />
                                 </Button>
                               </div>
                             </CardContent>
                           </Card>
                        ))
                      ) : (
                        <div className="text-sm text-muted-foreground bg-muted/20 p-8 text-center rounded-xl border border-dashed border-border">Henüz tanımlı alt hesap bulunmuyor.</div>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                 <Card className="border-border">
                   <CardContent className="pt-10 pb-12 flex flex-col items-center text-center">
                     <div className="h-16 w-16 bg-muted rounded-full flex items-center justify-center mb-6">
                       <UserPlus size={32} className="text-muted-foreground opacity-40" />
                     </div>
                     <h3 className="text-lg font-bold">Çoklu Hesap Özelliği</h3>
                     <p className="max-w-md text-sm text-muted-foreground mt-2">
                       Bu özellik yalnızca 'Üst Hesap' yetkisine sahip kullanıcılar tarafından kullanılabilir. Geçiş için talep oluşturabilirsiniz.
                     </p>
                     <Button
                       className="mt-6"
                       variant="outline"
                       onClick={() => onRequestMultiAccount('subaccounts_main')}
                       disabled={multiAccountRequestLoading}
                     >
                       Geçiş Talebi Oluştur
                     </Button>
                     {multiAccountRequestSuccess && <p className="mt-4 text-emerald-600 text-xs font-semibold">{multiAccountRequestSuccess}</p>}
                   </CardContent>
                 </Card>
              )}
            </TabsContent>

             {/* --- PLACEHOLDER SECTIONS --- */}
             <TabsContent value="prefs" className="mt-0 space-y-8 animate-in fade-in slide-in-from-bottom-2">
                <div className="border-b border-border pb-6">
                  <h2 className="text-3xl font-bold tracking-tight text-foreground">{SECTION_CONTENT.prefs.title}</h2>
                  <p className="mt-1.5 text-[15px] text-muted-foreground">{SECTION_CONTENT.prefs.description}</p>
                </div>
                <Card className="border-border">
                  <CardContent className="py-20 text-center text-muted-foreground italic">Yakında eklenecek...</CardContent>
                </Card>
             </TabsContent>

             <TabsContent value="general" className="mt-0 space-y-8 animate-in fade-in slide-in-from-bottom-2">
                <div className="border-b border-border pb-6">
                  <h2 className="text-3xl font-bold tracking-tight text-foreground">{SECTION_CONTENT.general.title}</h2>
                  <p className="mt-1.5 text-[15px] text-muted-foreground">{SECTION_CONTENT.general.description}</p>
                </div>
                <Card className="border-border">
                  <CardContent className="py-20 text-center text-muted-foreground italic">Yakında eklenecek...</CardContent>
                </Card>
             </TabsContent>
             </div>
           </div>
         </Tabs>
       </main>

      {isPaymentContactOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4" onClick={() => setIsPaymentContactOpen(false)}>
          <div
            className="w-full max-w-sm rounded-2xl border border-border bg-background p-6 text-center shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <h3 className="text-lg font-bold text-foreground">İletişim Numarası</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Erken erişim süreci için bize bu numaradan ulaşabilirsiniz.
            </p>
            <p className="mt-5 text-2xl font-bold tracking-wide text-foreground">{CONTACT_PHONE_NUMBER}</p>
            <Button className="mt-6 w-full !text-white hover:!text-white" type="button" onClick={() => setIsPaymentContactOpen(false)}>
              Kapat
            </Button>
          </div>
        </div>
      )}

      {/* --- Footer Spacing --- */}
      <div className="h-20" />
    </div>
  )
}
