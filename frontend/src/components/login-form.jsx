import { useMemo, useState } from 'react'
import { Navigate, useLocation, useNavigate, Link } from 'react-router-dom'
import { useAuth } from '@/features/auth/useAuth.js'
import { apiRequest } from '@/shared/api/client.js'
import { describeApiError, humanizeApiError } from '@/shared/api/contracts.js'
import { InlineBanner } from '@/shared/components/InlineBanner.jsx'
import { Eye, EyeOff, Loader2, Sparkles, Lock, Zap, GalleryVerticalEnd } from 'lucide-react'
import yargucuLogoWhite from '../logopack/yargucu-logo-beyaz.svg'
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

export function LoginForm({
  className,
  ...props
}) {
  const { login, isAuthed } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = useMemo(() => location.state?.from || '/chat', [location.state])

  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isSubmitting, setSubmitting] = useState(false)
  const [banner, setBanner] = useState(null)
  const [shake, setShake] = useState(false)

  const [forgotOpen, setForgotOpen] = useState(false)
  const [forgotIdentifier, setForgotIdentifier] = useState('')
  const [forgotSubmitting, setForgotSubmitting] = useState(false)
  const [forgotError, setForgotError] = useState('')
  const [forgotSent, setForgotSent] = useState(false)

  const [legalType, setLegalType] = useState(null)

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
    setSubmitting(true)
    try {
      await login({ identifier, password })
      navigate(from, { replace: true })
    } catch (err) {
      triggerError(err, 'Giriş işlemi başarısız oldu')
    } finally {
      setSubmitting(false)
    }
  }

  async function onForgotPassword(e) {
    e.preventDefault()
    const ident = (forgotIdentifier || identifier || '').trim()
    setForgotError('')
    setForgotSent(false)
    if (!ident) {
      setForgotError('E-posta adresi gerekli')
      return
    }
    setForgotSubmitting(true)
    try {
      await apiRequest('/v1/auth/forgot_password', {
        method: 'POST',
        body: { identifier: ident },
      })
      setForgotSent(true)
    } catch (err) {
      setForgotError(humanizeApiError(err, 'İşlem şu anda tamamlanamadı'))
    } finally {
      setForgotSubmitting(false)
    }
  }

  if (isAuthed) {
    return <Navigate to={from} replace />
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
          {/* Promotional Left Panel */}
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
                  Hukuki süreçlerde <br className="hidden xl:block" /><span className="text-blue-400">yapay zeka</span> dönüşümü.
                </h2>
                <p className="text-slate-400 text-[13px] lg:text-[14px] xl:text-[16px] 2xl:text-lg leading-relaxed mt-3 xl:mt-5 max-w-[320px] xl:max-w-[420px] 2xl:max-w-[500px] transition-all duration-300">
                  Yargucu ile dosya analizi ve içtihat arama süreçlerini saniyeler içinde tamamlayarak ofisinize zaman kazandırın.
                </p>

                {/* Features */}
                <div className="flex flex-col gap-3 xl:gap-4 mt-6 xl:mt-10 transition-all duration-300">
                  <div className="flex items-start gap-3 p-3 rounded-xl bg-white/[0.02] border border-white/[0.05] hover:bg-white/[0.04] transition-colors">
                    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-blue-500/10 text-blue-400 shrink-0">
                      <Sparkles size={16} strokeWidth={2.5} />
                    </div>
                    <div>
                      <h4 className="font-semibold text-white text-[13px] lg:text-[14px]">Akıllı İçtihat Taraması</h4>
                      <p className="text-[12px] text-slate-400 mt-0.5 leading-snug">Milyonlarca emsal karar arasından en alakalı olanı anında bulun.</p>
                    </div>
                  </div>
                  
                  <div className="flex items-start gap-3 p-3 rounded-xl bg-white/[0.02] border border-white/[0.05] hover:bg-white/[0.04] transition-colors">
                    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-blue-500/10 text-blue-400 shrink-0">
                      <Lock size={16} strokeWidth={2.5} />
                    </div>
                    <div>
                      <h4 className="font-semibold text-white text-[13px] lg:text-[14px]">%100 Veri Egemenliği</h4>
                      <p className="text-[12px] text-slate-400 mt-0.5 leading-snug">Verileriniz uçtan uca şifreleme ile tam güvence altında.</p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 p-3 rounded-xl bg-white/[0.02] border border-white/[0.05] hover:bg-white/[0.04] transition-colors">
                    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-blue-500/10 text-blue-400 shrink-0">
                      <Zap size={16} strokeWidth={2.5} />
                    </div>
                    <div>
                      <h4 className="font-semibold text-white text-[13px] lg:text-[14px]">UYAP Entegrasyonu</h4>
                      <p className="text-[12px] text-slate-400 mt-0.5 leading-snug">Hazırlanan dilekçeleri doğrudan UYAP formatında dışa aktarın.</p>
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
                  <h1 className="text-2xl font-bold">Tekrar Hoş Geldiniz</h1>
                  <p className="text-sm text-balance text-muted-foreground">
                    Yargucu hesabınıza giriş yapın
                  </p>
                </div>
              <Field>
                <FieldLabel htmlFor="identifier">Kullanıcı Adı veya E-Posta</FieldLabel>
                <Input
                  id="identifier"
                  type="text"
                  placeholder="avukat@hukuk.com"
                  value={identifier}
                  onChange={(e) => { setIdentifier(e.target.value); setBanner(null) }}
                  disabled={isSubmitting}
                  required
                />
              </Field>
              <Field>
                <div className="flex items-center">
                  <FieldLabel htmlFor="password">Şifre</FieldLabel>
                  <button
                    type="button"
                    onClick={() => setForgotOpen(!forgotOpen)}
                    className="ml-auto text-sm underline-offset-2 hover:underline"
                  >
                    Şifremi unuttum?
                  </button>
                </div>
                <div className="relative">
                  <Input 
                    id="password" 
                    type={showPassword ? 'text' : 'password'} 
                    value={password}
                    onChange={(e) => { setPassword(e.target.value); setBanner(null) }}
                    disabled={isSubmitting}
                    required
                    placeholder="••••••••"
                    className="pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((value) => !value)}
                    className="absolute inset-y-0 right-0 flex items-center px-3 text-slate-500 transition hover:text-slate-700"
                    aria-label={showPassword ? 'Şifreyi gizle' : 'Şifreyi göster'}
                    title={showPassword ? 'Şifreyi gizle' : 'Şifreyi göster'}
                    disabled={isSubmitting}
                  >
                    {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                  </button>
                </div>
              </Field>
              
              {forgotOpen && (
                <div className="flex flex-col gap-2 p-4 bg-muted/50 rounded-lg animate-in fade-in slide-in-from-top-2 duration-300">
                  <p className="text-sm font-medium">Sıfırlama bağlantısı gönder</p>
                  <div className="flex gap-2">
                    <Input
                      placeholder="E-Posta adresi"
                      value={forgotIdentifier}
                      onChange={(e) => setForgotIdentifier(e.target.value)}
                    />
                    <Button
                      type="button"
                      onClick={onForgotPassword}
                      disabled={forgotSubmitting || !forgotIdentifier}
                    >
                      {forgotSubmitting ? <Loader2 className="animate-spin h-4 w-4" /> : "Gönder"}
                    </Button>
                  </div>
                  {forgotSent && <p className="text-xs text-green-600 font-medium mt-1">Bağlantı Gönderildi</p>}
                  {forgotError && <p className="text-xs text-destructive font-medium mt-1">{forgotError}</p>}
                </div>
              )}

              <InlineBanner {...(banner || {})} />

              <Field>
                <Button type="submit" disabled={isSubmitting || !identifier || !password}>
                  {isSubmitting ? <Loader2 className="animate-spin mr-2 h-4 w-4" /> : null}
                  Sisteme Giriş Yap
                </Button>
              </Field>
              <FieldSeparator className="*:data-[slot=field-separator-content]:bg-card">
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
              <FieldDescription className="text-center mt-4">
                Henüz katılmadınız mı? <Link to="/register" className="text-primary hover:underline">Ücretsiz Başlayın</Link>
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
