import { useMemo, useState } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { apiRequest } from '../../../shared/api/client.js'
import { describeApiError } from '../../../shared/api/contracts.js'
import { InlineBanner } from '../../../shared/components/InlineBanner.jsx'
import { useAuth } from '../useAuth.js'
import { Scale, Eye, EyeOff, Loader2, KeyRound } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

export function ResetPasswordPage() {
  const { isAuthed } = useAuth()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = useMemo(() => String(searchParams.get('token') || '').trim(), [searchParams])

  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [banner, setBanner] = useState(null)
  const [success, setSuccess] = useState(false)

  async function onSubmit(e) {
    e.preventDefault()
    setBanner(null)
    if (!token) {
      setBanner({
        tone: 'error',
        title: 'Bağlantı geçersiz',
        message: 'Şifre sıfırlama bağlantısı geçersiz veya süresi dolmuş.',
      })
      return
    }
    if (!password || password.length < 8) {
      setBanner({
        tone: 'error',
        title: 'Bilgileri kontrol edin',
        message: 'Parola en az 8 karakter olmalı.',
      })
      return
    }
    if (password !== confirmPassword) {
      setBanner({
        tone: 'error',
        title: 'Bilgileri kontrol edin',
        message: 'Parola tekrar alanı eşleşmiyor.',
      })
      return
    }

    setSubmitting(true)
    try {
      await apiRequest('/v1/auth/reset_password/confirm', {
        method: 'POST',
        body: { token, new_password: password },
      })
      setSuccess(true)
      window.setTimeout(() => navigate('/login', { replace: true }), 1500)
    } catch (err) {
      setBanner(describeApiError(err, 'Şifre sıfırlanamadı'))
    } finally {
      setSubmitting(false)
    }
  }

  if (isAuthed) return <Navigate to="/" replace />

  return (
    <div className="auth-page-shell min-h-[100dvh] w-full flex flex-col items-center justify-center bg-zinc-50 relative p-4 sm:p-8 selection:bg-blue-900 selection:text-white">
      {/* Background Ambience */}
      <div className="fixed inset-0 bg-[radial-gradient(circle_at_top_right,_var(--tw-gradient-stops))] from-blue-100/40 via-zinc-50 to-white/80 -z-10" />
      <div className="fixed inset-0 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] opacity-[0.02] pointer-events-none -z-10" />
      
      {/* Center Blur */}
      <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-zinc-200/40 blur-[120px] pointer-events-none -z-10" />

      {/* Main Card Container */}
      <div className="w-full max-w-[480px] bg-white/80 backdrop-blur-2xl rounded-[2rem] shadow-[0_8px_40px_-12px_rgba(0,0,0,0.12)] border border-zinc-200/60 overflow-hidden relative z-10 animate-in zoom-in-95 fade-in slide-in-from-bottom-4 duration-700">
        
        {/* Header Area */}
        <div className="flex flex-col items-center pt-8 pb-6 px-6 sm:px-8 border-b border-zinc-100 bg-white/50">
          <div className="p-3 bg-blue-700 rounded-2xl shadow-lg border border-zinc-800 mb-6 group transition-transform hover:scale-105 duration-300">
            <Scale className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-2xl font-semibold text-zinc-950 tracking-tight text-center mb-2">
            Yeni Parola Belirleme
          </h1>
          <p className="text-sm text-zinc-500 text-center text-balance font-light">
            Hesabınız için yeni bir güvenli parola tanımlayın ve işleminizi tamamlayın.
          </p>
        </div>

        {/* Form Area */}
        <div className="p-6 sm:p-8">
          <form onSubmit={onSubmit} className="space-y-5">
            
            {/* Password Input */}
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <label className="block text-xs font-medium text-zinc-700 uppercase tracking-widest">
                  Yeni Parola
                </label>
                <span className="text-[10px] text-zinc-400 font-medium tracking-wide">Min. 8 Karakter</span>
              </div>
              <div className="relative group">
                <Input
                  className="w-full h-12 pl-11 pr-12 bg-white/70 border-zinc-200 rounded-xl shadow-[0_2px_10px_-4px_rgba(0,0,0,0.05)] text-zinc-900 text-sm placeholder:text-zinc-400 focus-visible:bg-white focus-visible:ring-[3px] focus-visible:ring-blue-700/5 focus-visible:border-zinc-400 transition-all duration-300 hover:border-zinc-300 disabled:opacity-60 group-focus-within:bg-white"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="En az 8 karakter"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  disabled={submitting || success}
                />
                <KeyRound className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
                <button
                  className="absolute inset-y-0 right-0 pr-4 flex items-center text-zinc-400 hover:text-zinc-600 transition-colors focus:outline-none"
                  type="button"
                  onClick={() => setShowPassword((value) => !value)}
                  aria-label={showPassword ? 'Parolayi gizle' : 'Parolayi goster'}
                  disabled={submitting || success}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Confirm Password Input */}
            <div className="space-y-2">
              <label className="block text-xs font-medium text-zinc-700 uppercase tracking-widest">
                Parola Tekrar
              </label>
              <div className="relative group">
                <Input
                  className="w-full h-12 pl-11 pr-4 bg-white/70 border-zinc-200 rounded-xl shadow-[0_2px_10px_-4px_rgba(0,0,0,0.05)] text-zinc-900 text-sm placeholder:text-zinc-400 focus-visible:bg-white focus-visible:ring-[3px] focus-visible:ring-blue-700/5 focus-visible:border-zinc-400 transition-all duration-300 hover:border-zinc-300 disabled:opacity-60 group-focus-within:bg-white"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Parolanızı tekrar girin"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  disabled={submitting || success}
                />
                <KeyRound className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
              </div>
            </div>

            {/* Alerts */}
            {!token && (
              <InlineBanner
                tone="error"
                title="Bağlantı geçersiz"
                message="Geçersiz veya eksik sıfırlama bağlantısı."
                className="rounded-xl animate-in zoom-in-95"
              />
            )}

            <InlineBanner {...(banner || {})} className="rounded-xl animate-in zoom-in-95" />
            
            {success && (
              <div className="p-4 bg-emerald-50 border border-emerald-100 rounded-xl text-emerald-700 text-sm font-medium flex items-center gap-3 animate-in fade-in zoom-in-95">
                <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center shrink-0">
                  <svg className="w-4 h-4 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <span>Şifreniz başarıyla güncellendi. Giriş ekranına yönlendiriliyorsunuz...</span>
              </div>
            )}

            {/* Submit Button */}
            <Button 
              className="w-full h-12 bg-blue-700 text-white text-[15px] font-medium rounded-xl shadow-[0_4px_14px_0_rgba(0,0,0,0.1)] hover:bg-blue-800 hover:shadow-[0_6px_20px_0_rgba(0,0,0,0.15)] hover:-translate-y-[1px] focus-visible:ring-[3px] focus-visible:ring-blue-700/20 transition-all duration-300 mt-6 disabled:opacity-70 border-0 flex items-center justify-center gap-2" 
              type="submit" 
              disabled={submitting || success || !token || !password || !confirmPassword}
            >
              {submitting ? (
                 <><Loader2 className="w-5 h-5 animate-spin text-zinc-400" /> Güncelleniyor</>
              ) : success ? (
                'Tamamlandı'
              ) : (
                'Şifreyi Güncelle'
              )}
            </Button>

            {/* Go Back Link */}
            <div className="pt-4 text-center">
              <Link to="/login" className="text-sm font-medium text-zinc-500 hover:text-zinc-950 transition-colors">
                Giriş ekranına dön
              </Link>
            </div>
          </form>
        </div>
      </div>
      
      {/* Footer Branding */}
      <div className="mt-8 text-center animate-in fade-in duration-1000 delay-500">
        <p className="text-[11px] font-medium text-zinc-400 uppercase tracking-widest">YARGUCU HUKUK PLATFORMU</p>
      </div>
    </div>
  )
}
