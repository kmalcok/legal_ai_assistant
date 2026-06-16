import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { apiRequest } from '@/shared/api/client.js'
import { describeApiError } from '@/shared/api/contracts.js'
import { InlineBanner } from '@/shared/components/InlineBanner.jsx'
import { Loader2, CheckCircle2, Sparkles, Eye, EyeOff, GalleryVerticalEnd } from 'lucide-react'
import yargucuLogoWhite from '@/logopack/yargucu-logo-beyaz.svg'
import { LegalModal } from './legal-modal.jsx'

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldSeparator,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"

export function SignupForm({
  className,
  ...props
}) {
  const navigate = useNavigate()

  const [formData, setFormData] = useState({
    username: '',
    email: '',
    full_name: '',
    phone: '',
    coupon_code: '',
    entry_code: '',
    password: '',
  })
  
  const [showPassword, setShowPassword] = useState(false)
  const [banner, setBanner] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [shake, setShake] = useState(false)
  const [legalType, setLegalType] = useState(null)

  const handleChange = (e) => {
    setFormData(prev => ({ ...prev, [e.target.name]: e.target.value }))
    setBanner(null)
    setShake(false)
  }

  const triggerError = (err, fallback) => {
    setBanner(describeApiError(err, fallback))
    setShake(true)
    setTimeout(() => setShake(false), 500)
  }

  const showOauthNotice = () => {
    setBanner({
      tone: 'info',
      title: 'Yakında aktif olacak',
      message: 'Google ile devam et özelliği henüz aktif değil.',
    })
  }

  async function onSubmit(e) {
    if (e) e.preventDefault()
    setBanner(null)
    setIsSubmitting(true)

    try {
      await apiRequest('/v1/auth/register', {
        method: 'POST',
        body: formData,
      })
      navigate('/login', { state: { message: 'Kayıt başarılı! Lütfen giriş yapın.' } })
    } catch (err) {
      triggerError(err, 'Kayıt işlemi başarısız oldu.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className={cn("flex flex-col gap-6", className)} {...props}>
      <Link to="/" className="flex items-center gap-2 self-center font-medium md:hidden">
        <div className="flex size-6 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <img src={yargucuLogoWhite} alt="Yargucu" className="size-4 object-contain" />
        </div>
        <div className="flex flex-col">
          <span className="leading-tight">Yargucu</span>
          <span className="text-[10px] text-muted-foreground leading-tight font-normal">AI Hukuk Asistanı</span>
        </div>
      </Link>
      <Card className="overflow-hidden p-0">
        <CardContent className="grid p-0 md:grid-cols-2">
          {/* Promotional Left Panel (Identical to login-form.jsx) */}
          <div className="relative hidden bg-slate-950 md:flex flex-col p-8 lg:p-10 xl:px-14 xl:py-12 2xl:px-16 2xl:py-14 text-white overflow-hidden rounded-l-xl border-r border-slate-800/50 transition-all duration-300">
            {/* Grid Pattern */}
            <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px]" />
            
            {/* Radial Gradients */}
            <div className="absolute inset-0 bg-gradient-to-br from-slate-950 via-transparent to-blue-950/30" />
            <div className="absolute -top-32 -left-32 w-[400px] h-[400px] bg-blue-600/10 rounded-full blur-[80px]" />
            <div className="absolute -bottom-32 -right-32 w-[300px] h-[300px] bg-slate-800/40 rounded-full blur-[80px]" />
            
            <div className="relative z-10 flex flex-col h-full justify-center gap-6">
              {/* Brand Header */}
              <div className="flex items-center gap-2">
                <div className="flex items-center justify-center p-1.5 bg-white/5 border border-white/10 rounded-lg shadow-inner">
                  <img src={yargucuLogoWhite} alt="" className="h-4 w-auto object-contain shrink-0" aria-hidden="true" />
                </div>
                <span className="text-[12px] font-bold tracking-[0.2em] text-slate-200">YARGUCU</span>
              </div>
              
              {/* Main Copy */}
              <div className="flex flex-col justify-center">
                <h2 className="text-2xl lg:text-3xl xl:text-4xl 2xl:text-[2.75rem] font-bold leading-[1.12] text-white tracking-tight transition-all duration-300">
                  Kurumsal <br className="hidden xl:block" /><span className="text-blue-400">çalışma alanınızı</span> saniyeler içinde kurun.
                </h2>
                <p className="text-slate-400 text-[13px] lg:text-[14px] xl:text-[16px] 2xl:text-lg leading-relaxed mt-3 xl:mt-5 max-w-[320px] xl:max-w-[420px] 2xl:max-w-[500px] transition-all duration-300">
                  Yargucu'nun yapay zekâ gücüyle tanışın, ücretsiz kullanım kredisiyle hemen başlayın.
                </p>

                {/* Features */}
                <div className="flex flex-col gap-3 xl:gap-4 mt-6 xl:mt-10 transition-all duration-300">
                  <div className="flex items-start gap-3 p-3 rounded-xl bg-white/[0.02] border border-white/[0.05] hover:bg-white/[0.04] transition-colors">
                    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-blue-500/10 text-blue-400 shrink-0">
                      <CheckCircle2 size={16} strokeWidth={2.5} />
                    </div>
                    <div>
                      <h4 className="font-semibold text-white text-[13px] lg:text-[14px]">Ücretsiz Deneyim</h4>
                      <p className="text-[12px] text-slate-400 mt-0.5 leading-snug">Tüm özellikleri ücretsiz test edin.</p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 p-3 rounded-xl bg-white/[0.02] border border-white/[0.05] hover:bg-white/[0.04] transition-colors">
                    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-blue-500/10 text-blue-400 shrink-0">
                      <Sparkles size={16} strokeWidth={2.5} />
                    </div>
                    <div>
                      <h4 className="font-semibold text-white text-[13px] lg:text-[14px]">Akıllı İçtihat Taraması</h4>
                      <p className="text-[12px] text-slate-400 mt-0.5 leading-snug">10M+ karar içinden en alakalı emsalleri bulun.</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <form className="flex flex-col items-center justify-center h-full p-6 md:p-10 xl:px-14 xl:py-10 transition-all duration-300" onSubmit={onSubmit}>
            <div className="w-full max-w-xs transition-all duration-300">
              <FieldGroup className={shake ? "animate-shake" : ""}>

                <div className="flex flex-col items-center gap-1 text-center mb-6">
                  <h1 className="text-2xl font-bold">Kayıt Ol</h1>
                  <p className="text-sm text-balance text-muted-foreground">
                    Profesyonel hukuk asistanınızı kullanmaya bugün başlayın.
                  </p>
                </div>

              <div className="grid grid-cols-1 gap-4">
                <Field>
                  <FieldLabel htmlFor="full_name">Ad Soyad</FieldLabel>
                  <Input
                    id="full_name"
                    name="full_name"
                    type="text"
                    required
                    placeholder="Av. Ali Yılmaz"
                    value={formData.full_name}
                    onChange={handleChange}
                    disabled={isSubmitting}
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="username">Kullanıcı Adı</FieldLabel>
                  <Input
                    id="username"
                    name="username"
                    type="text"
                    required
                    placeholder="avukat_ali"
                    value={formData.username}
                    onChange={handleChange}
                    disabled={isSubmitting}
                  />
                </Field>
              </div>

              <Field>
                <FieldLabel htmlFor="email">Kurumsal E-Posta</FieldLabel>
                <Input
                  id="email"
                  name="email"
                  type="email"
                  placeholder="avukat@kurum.com"
                  required
                  value={formData.email}
                  onChange={handleChange}
                  disabled={isSubmitting}
                />
              </Field>

              <Field>
                <FieldLabel htmlFor="phone">Telefon Numarası</FieldLabel>
                <Input
                  id="phone"
                  name="phone"
                  type="tel"
                  placeholder="Opsiyonel"
                  value={formData.phone}
                  onChange={handleChange}
                  disabled={isSubmitting}
                />
              </Field>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
                <Field>
                  <FieldLabel htmlFor="coupon_code">Kupon / Kampanya Kodu</FieldLabel>
                  <Input
                    id="coupon_code"
                    name="coupon_code"
                    type="text"
                    placeholder="Opsiyonel"
                    value={formData.coupon_code}
                    onChange={handleChange}
                    disabled={isSubmitting}
                    autoCapitalize="characters"
                    autoCorrect="off"
                    spellCheck={false}
                  />
                </Field>

                <Field>
                  <label className="flex h-10 w-full items-center gap-3 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background whitespace-nowrap">
                    <input
                      id="entry_code"
                      type="checkbox"
                      checked={formData.entry_code === 'st1'}
                      onChange={(event) => {
                        setFormData((prev) => ({ ...prev, entry_code: event.target.checked ? 'st1' : '' }))
                        setBanner(null)
                        setShake(false)
                      }}
                      disabled={isSubmitting}
                    />
                    <span>Öğrenciyim</span>
                  </label>
                </Field>
              </div>

              <Field>
                <div className="flex items-center justify-between">
                  <FieldLabel htmlFor="password">Güçlü Bir Şifre</FieldLabel>
                  <span className="text-[10px] sm:text-[11px] font-bold text-muted-foreground uppercase tracking-wider">
                    MİN. 8 KARAKTER
                  </span>
                </div>
                <div className="relative">
                  <Input
                    id="password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    required
                    placeholder="••••••••"
                    value={formData.password}
                    onChange={handleChange}
                    disabled={isSubmitting}
                    className="pr-12"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                    tabIndex="-1"
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
                <FieldDescription>
                  En az 8 karakter uzunluğunda olmalıdır.
                </FieldDescription>
              </Field>

              <InlineBanner {...(banner || {})} />

              <Field>
                <Button type="submit" className="w-full mt-2" disabled={isSubmitting || !formData.username || !formData.email || !formData.password}>
                  {isSubmitting ? <Loader2 className="animate-spin mr-2 h-4 w-4" /> : null}
                  Hesap Oluştur
                </Button>
              </Field>
              <FieldSeparator className="*:data-[slot=field-separator-content]:bg-card mt-1">
                Alternatif
              </FieldSeparator>
              <Field>
                <Button variant="outline" type="button" className="w-full" onClick={showOauthNotice}>
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" className="mr-2 h-4 w-4">
                    <path
                      d="M12.48 10.92v3.28h7.84c-.24 1.84-.853 3.187-1.787 4.133-1.147 1.147-2.933 2.4-6.053 2.4-4.827 0-8.6-3.893-8.6-8.72s3.773-8.72 8.6-8.72c2.6 0 4.507 1.027 5.907 2.347l2.307-2.307C18.747 1.44 16.133 0 12.48 0 5.867 0 .307 5.387.307 12s5.56 12 12.173 12c3.573 0 6.267-1.173 8.373-3.36 2.16-2.16 2.84-5.213 2.84-7.667 0-.76-.053-1.467-.173-2.053H12.48z"
                      fill="currentColor"
                    />
                  </svg>
                  Google ile devam et
                </Button>
              </Field>
              <FieldDescription className="text-center mt-5 xl:mt-6">
                Zaten hesabınız var mı? <Link to="/login" className="text-primary font-medium hover:underline">Giriş Yapın</Link>
              </FieldDescription>
            </FieldGroup>
            </div>
          </form>
        </CardContent>
      </Card>
      <FieldDescription className="px-6 text-center">
        Devam ederek <button onClick={() => setLegalType('terms')} className="text-primary font-medium hover:underline hover:text-primary/90 transition-colors">Kullanım Şartları</button>{" "}
        ve <button onClick={() => setLegalType('privacy')} className="text-primary font-medium hover:underline hover:text-primary/90 transition-colors">Gizlilik Politikası</button>'nı kabul etmiş olursunuz.
      </FieldDescription>

      <LegalModal 
        isOpen={!!legalType} 
        type={legalType} 
        onClose={() => setLegalType(null)} 
      />
    </div>
  )
}
