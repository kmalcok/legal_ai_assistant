export function unwrapApiPayload(data) {
  if (!data) return null
  if (typeof data === 'string') {
    try {
      const parsed = JSON.parse(data)
      if (parsed && typeof parsed === 'object') return parsed
    } catch {
      return null
    }
  }
  if (data instanceof Error) {
    if (data.data) {
       return unwrapApiPayload(data.data)
    }
    if (typeof data.message === 'string' && data.message.trim().startsWith('{')) {
      try {
        const parsed = JSON.parse(data.message)
        if (parsed && typeof parsed === 'object') return parsed
      } catch {
        // ignore
      }
    }
    return data
  }
  if (typeof data !== 'object') return null
  return data
}

function getApiStatus(input) {
  const value = Number(input?.status)
  return Number.isFinite(value) ? value : null
}

export function getApiReason(input) {
  const data = input?.data !== undefined ? input.data : input
  const payload = unwrapApiPayload(data)
  const reason = payload?.reason ?? payload?.detail?.reason
  return typeof reason === 'string' && reason.trim() ? reason.trim() : ''
}

export function getApiDetail(input) {
  const data = input?.data !== undefined ? input.data : input
  const payload = unwrapApiPayload(data)
  return payload?.detail ?? null
}

const FIELD_LABELS = {
  identifier: 'Kullanıcı adı veya e-posta',
  username: 'Kullanıcı adı',
  email: 'E-posta adresi',
  full_name: 'Ad soyad',
  password: 'Parola',
  current_password: 'Mevcut parola',
  new_password: 'Yeni parola',
  refresh_token: 'Oturum anahtarı',
  token: 'Doğrulama bağlantısı',
}

function toFieldLabel(name) {
  const key = String(name || '').trim()
  return FIELD_LABELS[key] || key.replace(/_/g, ' ')
}

function getValidationIssues(detail) {
  return Array.isArray(detail) ? detail.filter((item) => item && typeof item === 'object') : []
}

function getIssueField(issue) {
  const loc = Array.isArray(issue?.loc) ? issue.loc : []
  const bodyIndex = loc.indexOf('body')
  if (bodyIndex >= 0 && bodyIndex < loc.length - 1) return String(loc[bodyIndex + 1] || '')
  const last = loc[loc.length - 1]
  return typeof last === 'string' ? last : ''
}

function humanizeValidationIssue(issue) {
  const type = String(issue?.type || '')
  const field = getIssueField(issue)
  const fieldLabel = field ? toFieldLabel(field) : 'Gönderilen bilgi'

  if (type === 'missing') return `${fieldLabel} alanı zorunludur.`
  if (type.includes('string_too_short')) return `${fieldLabel} çok kısa.`
  if (type.includes('string_too_long')) return `${fieldLabel} çok uzun.`
  if (field === 'email') return 'Lütfen geçerli bir e-posta adresi girin.'
  if (field === 'password' || field === 'new_password') return 'Parola en az 8 karakter olmalıdır.'

  const raw = String(issue?.msg || '').trim()
  if (!raw) return `${fieldLabel} alanını kontrol edin.`
  if (raw === 'Field required') return `${fieldLabel} alanı zorunludur.`
  return `${fieldLabel}: ${raw}`
}

function humanizeValidationError(detail) {
  const issues = getValidationIssues(detail)
  if (!issues.length) return 'Gönderilen bilgiler doğrulanamadı. Lütfen alanları kontrol edin.'
  const messages = [...new Set(issues.map(humanizeValidationIssue).filter(Boolean))]
  return messages.join(' ')
}

export function getApiMessage(input, fallback = 'İşlem başarısız') {
  const data = input?.data !== undefined ? input.data : input
  const payload = unwrapApiPayload(data)
  const detail = getApiDetail(payload)
  const candidates = [
    payload?.message,
    typeof detail === 'string' ? detail : '',
    detail?.message,
    detail?.reason,
    payload?.reason,
    input?.message,
    fallback,
  ]
  let message = candidates.find((value) => typeof value === 'string' && value.trim())
  
  if (typeof message === 'string' && message.trim().startsWith('{')) {
    try {
      JSON.parse(message)
      // If it parses successfully, it's a raw JSON string. Fallback.
      message = fallback
    } catch {
      // It's not valid JSON, keep it.
    }
  }

  return String(message || fallback)
}

export function isApiErrorStatus(err, status) {
  return Number(err?.status) === Number(status)
}

export function isApiErrorReason(err, reason) {
  return getApiReason(err) === String(reason || '')
}

export function isInsufficientCreditsError(err) {
  return isApiErrorStatus(err, 402) || isApiErrorReason(err, 'insufficient_credits')
}

export function getRemainingCredit(err) {
  const detail = getApiDetail(err)
  const value = detail?.credit
  const num = Number(value)
  return Number.isFinite(num) ? num : null
}

const ERROR_REASON_MESSAGES = {
  insufficient_credits: 'Krediniz yetersiz. Devam etmek için bakiye yükleyin.',
  invalid_credentials: 'Kullanıcı adı, e-posta veya parola hatalı.',
  invalid_email: 'Geçerli bir e-posta adresi girin.',
  invalid_phone_number: 'Telefon numarasini gecerli formatta girin.',
  invalid_username: 'Kullanıcı adı geçersiz.',
  username_taken: 'Bu kullanıcı adı zaten kullanılıyor.',
  email_taken: 'Bu e-posta adresi zaten kullanılıyor.',
  weak_password: 'Parola en az 8 karakter olmalı.',
  invalid_reset_token: 'Şifre sıfırlama bağlantısı geçersiz veya süresi dolmuş.',
  refresh_reuse_detected: 'Oturum güvenlik nedeniyle sonlandırıldı. Lütfen tekrar giriş yapın.',
  refresh_revoked_or_expired: 'Oturumunuz sona erdi. Lütfen tekrar giriş yapın.',
  refresh_already_rotated: 'Oturum bilgileriniz güncellendi. İstek yeniden denenecek.',
  invalid_access_version: 'Oturumunuz güncel değil. Lütfen tekrar giriş yapın.',
  access_revoked: 'Bu oturum geçersiz kılınmış. Lütfen tekrar giriş yapın.',
  session_revoked: 'Oturumunuz iptal edildi. Lütfen tekrar giriş yapın.',
  user_not_found: 'Kullanıcı bulunamadı.',
  invalid_identifier: 'Kullanıcı adı veya e-posta gerekli.',
  parent_required: 'Bu işlem için üst hesap yetkisi gerekiyor.',
  child_limit_reached: 'Bu plan için açılabilecek alt hesap limitine ulaşıldı.',
  child_not_found: 'Alt hesap bulunamadı.',
  child_account_delete_forbidden: 'Alt hesaplar kendi hesaplarını silemez. Bu işlem üst hesaptan yapılmalıdır.',
  insufficient_parent_credits: 'Üst hesabın kullanılabilir kredisi yetersiz.',
  child_account_email_failed: 'Alt hesap oluşturuldu ancak bilgilendirme e-postası gönderilemediği için işlem geri alındı.',
  invalid_coupon_quantity: 'Kupon adedi en az 1 olmalıdır.',
  invalid_coupon_plan: 'Kupon için seçilen hedef paket geçersiz.',
  invalid_coupon_code: 'Kupon kodunu kontrol edin.',
  invalid_coupon_payload: 'Kupon en az kredi veya paket dönüşümü içermelidir.',
  invalid_coupon_campaign_name: 'Kampanya adı zorunludur.',
  invalid_coupon_distribution_mode: 'Kupon tipi geçersiz.',
  invalid_coupon_selection: 'Silinecek kuponları seçin.',
  coupon_code_exists: 'Bu kampanya kodu zaten kullaniliyor.',
  coupon_not_found: 'Bu kupon kodu bulunamadı.',
  coupon_already_used: 'Bu kupon kodu daha önce kullanılmış.',
  coupon_already_redeemed_by_user: 'Bu kuponu daha once kullandiniz.',
  coupon_plan_change_confirmation_required: 'Bu kupon hesabınızın paketini değiştirecek. Devam etmeden önce onay vermeniz gerekiyor.',
  email_not_deliverable: 'Bu e-posta adresine doğrulama iletisi teslim edilemiyor. Aktif ve ulaşılabilir bir adres girin.',
  mail_verification_error: 'E-posta doğrulaması şu anda tamamlanamadı. Lütfen biraz sonra tekrar deneyin.',
  invalid_refresh: 'Oturum doğrulanamadı. Lütfen tekrar giriş yapın.',
  refresh_unknown: 'Oturumunuz geçersiz. Lütfen tekrar giriş yapın.',
  validation_error: 'Gönderilen bilgiler doğrulanamadı.',
  db_error: 'İşlem şu anda tamamlanamadı. Lütfen biraz sonra tekrar deneyin.',
  internal_error: 'Beklenmeyen bir hata oluştu. Lütfen tekrar deneyin.',
  rate_limited: 'Çok fazla istek gönderdiniz. Lütfen kısa bir süre sonra tekrar deneyin.',
}

const ERROR_REASON_TITLES = {
  invalid_credentials: 'Giriş başarısız',
  invalid_email: 'E-posta adresini kontrol edin',
  invalid_phone_number: 'Telefon numarasini kontrol edin',
  invalid_username: 'Kullanıcı adını kontrol edin',
  username_taken: 'Kullanıcı adı kullanımda',
  email_taken: 'E-posta kullanımda',
  weak_password: 'Parolayı güçlendirin',
  invalid_reset_token: 'Bağlantı geçersiz',
  email_not_deliverable: 'E-posta doğrulanamadı',
  mail_verification_error: 'E-posta servisine ulaşılamadı',
  invalid_refresh: 'Oturum doğrulanamadı',
  refresh_unknown: 'Oturum geçersiz',
  parent_required: 'Üst hesap yetkisi gerekli',
  child_limit_reached: 'Alt hesap limitine ulaşıldı',
  child_not_found: 'Alt hesap bulunamadı',
  child_account_email_failed: 'Bilgilendirme e-postası gönderilemedi',
  invalid_coupon_code: 'Kupon kodunu kontrol edin',
  coupon_code_exists: 'Kampanya kodu kullaniliyor',
  coupon_not_found: 'Kupon bulunamadı',
  coupon_already_used: 'Kupon daha önce kullanılmış',
  coupon_already_redeemed_by_user: 'Kupon zaten kullanılmış',
  coupon_plan_change_confirmation_required: 'Paket değişimi onayı gerekiyor',
  rate_limited: 'Çok fazla istek',
}

export function describeApiError(err, fallback = 'İşlem tamamlanamadı') {
  const reason = getApiReason(err)
  const detail = getApiDetail(err)
  const status = getApiStatus(err)

  if (reason === 'validation_error') {
    return {
      tone: 'error',
      title: 'Bilgileri kontrol edin',
      message: humanizeValidationError(detail),
      reason,
      status,
    }
  }

  if (reason && ERROR_REASON_MESSAGES[reason]) {
    const title = ERROR_REASON_TITLES[reason] || (status && status >= 500 ? 'İşlem şu anda tamamlanamadı' : 'İşlem başarısız')
    return {
      tone: status && status >= 500 ? 'warning' : 'error',
      title,
      message: ERROR_REASON_MESSAGES[reason],
      reason,
      status,
    }
  }

  if (status === 429) {
    return {
      tone: 'warning',
      title: 'Çok fazla istek',
      message: 'Kısa bir süre bekleyip tekrar deneyin.',
      reason,
      status,
    }
  }

  if (status && status >= 500) {
    return {
      tone: 'warning',
      title: 'Sunucu hatası',
      message: 'İşlem şu anda tamamlanamadı. Lütfen biraz sonra tekrar deneyin.',
      reason,
      status,
    }
  }

  return {
    tone: 'error',
    title: 'İşlem başarısız',
    message: getApiMessage(err, fallback),
    reason,
    status,
  }
}

export function humanizeApiError(err, fallback = 'İşlem tamamlanamadı') {
  return describeApiError(err, fallback).message
}
