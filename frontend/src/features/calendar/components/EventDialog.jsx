import { useEffect, useState } from 'react'
import { Dialog, DialogContent, DialogOverlay } from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { X } from 'lucide-react'
import { humanizeApiError } from '../../../shared/api/contracts.js'
import { isoDate } from '../utils/dates.js'

const EMPTY_FORM = {
  title: '',
  due_date: '',
  due_time: '',
  note: '',
}

const HOURS = Array.from({ length: 24 }).map((_, i) => i.toString().padStart(2, '0'))
const MINUTES = ['00', '15', '30', '45']

function isoFromInput(value) {
  if (!value) return ''
  const text = String(value).trim()
  if (!text) return ''
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text
  const m = /^(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})$/.exec(text)
  if (m) {
    const day = m[1].padStart(2, '0')
    const mo = m[2].padStart(2, '0')
    return `${m[3]}-${mo}-${day}`
  }
  return text
}

export function EventDialog({ open, mode = 'create', initialEvent, onClose, onSubmit }) {
  const [form, setForm] = useState(EMPTY_FORM)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    if (initialEvent) {
      setForm({
        title: initialEvent.title || '',
        due_date: isoDate(initialEvent.due_date) || '',
        due_time: initialEvent.due_time ? String(initialEvent.due_time).slice(0, 5) : '',
        note: initialEvent.note || '',
      })
    } else {
      setForm(EMPTY_FORM)
    }
    setError('')
  }, [open, initialEvent])

  const handleChange = (field) => (event) => {
    const value = event?.target?.value ?? ''
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    const title = form.title.trim()
    const due = isoFromInput(form.due_date)
    if (!title) {
      setError('Başlık zorunludur.')
      return
    }
    if (!due) {
      setError('Geçerli bir tarih girin.')
      return
    }
    const payload = {
      title,
      due_date: due,
      note: form.note?.trim() || null,
      due_time: (form.due_time === 'none' || !form.due_time) ? null : form.due_time.trim(),
    }
    setSubmitting(true)
    try {
      await onSubmit?.(payload)
      onClose?.()
    } catch (err) {
      setError(humanizeApiError(err, 'Kayıt başarısız.'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose?.()}>
      <DialogOverlay />
      <DialogContent>
        <div className="flex flex-col space-y-1.5 text-center sm:text-left relative">
          <h2 className="text-lg font-semibold leading-none tracking-tight">
            {mode === 'edit' ? 'Etkinliği düzenle' : 'Yeni etkinlik ekle'}
          </h2>
          <button
            onClick={() => onClose?.()}
            className="absolute right-[-8px] top-[-8px] rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none disabled:pointer-events-none"
          >
            <X className="h-4 w-4" />
            <span className="sr-only">Kapat</span>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="title">Başlık</Label>
            <Input
              id="title"
              placeholder="Örn. İtiraz süresi"
              value={form.title}
              onChange={handleChange('title')}
              required
              className="h-10"
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="date">Tarih</Label>
              <Input
                id="date"
                type="date"
                value={form.due_date}
                onChange={handleChange('due_date')}
                required
                className="h-10"
              />
            </div>
            <div className="space-y-2">
              <Label>Saat (opsiyonel)</Label>
              <div className="flex items-center gap-2">
                <Select
                  value={form.due_time ? form.due_time.split(':')[0] : ""}
                  onValueChange={(h) => {
                    const m = form.due_time ? form.due_time.split(':')[1] || '00' : '00'
                    setForm(prev => ({ ...prev, due_time: `${h}:${m}` }))
                  }}
                >
                  <SelectTrigger className="h-10 w-full">
                    <SelectValue placeholder="--" />
                  </SelectTrigger>
                  <SelectContent>
                    {HOURS.map((h) => (
                      <SelectItem key={h} value={h}>{h}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <span className="text-muted-foreground font-medium">:</span>
                <Select
                  value={form.due_time ? form.due_time.split(':')[1] : ""}
                  onValueChange={(m) => {
                    const h = form.due_time ? form.due_time.split(':')[0] || '09' : '09'
                    setForm(prev => ({ ...prev, due_time: `${h}:${m}` }))
                  }}
                >
                  <SelectTrigger className="h-10 w-full">
                    <SelectValue placeholder="--" />
                  </SelectTrigger>
                  <SelectContent>
                    {MINUTES.map((m) => (
                      <SelectItem key={m} value={m}>{m}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="note">Not</Label>
            <Textarea
              id="note"
              placeholder="Tarih hakkında kısa açıklama (opsiyonel)"
              value={form.note}
              onChange={handleChange('note')}
              rows={3}
              className="resize-none"
            />
          </div>

          {error && <p className="text-sm font-medium text-destructive">{error}</p>}

          <div className="flex flex-col-reverse gap-2 pt-4 sm:flex-row sm:justify-end">
            <Button
              type="button"
              variant="outline"
              onClick={() => onClose?.()}
              disabled={submitting}
              className="h-10 sm:w-24"
            >
              Vazgeç
            </Button>
            <Button
              type="submit"
              disabled={submitting}
              className="h-10 sm:w-24"
            >
              {submitting ? 'Kaydediliyor...' : mode === 'edit' ? 'Güncelle' : 'Kaydet'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
