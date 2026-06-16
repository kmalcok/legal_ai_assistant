import { Download, FileText, X } from 'lucide-react'
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

function formatDateTime(value) {
  if (!value) return 'Bilinmiyor'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('tr-TR')
}

function formatBytes(value) {
  const num = Number(value)
  if (!Number.isFinite(num) || num < 0) return 'Bilinmiyor'
  if (num < 1024) return `${num} B`
  if (num < 1024 * 1024) return `${(num / 1024).toFixed(1)} KB`
  return `${(num / (1024 * 1024)).toFixed(1)} MB`
}

export function GeneratedDocumentPreviewPanel({
  document,
  loading,
  error,
  downloadingDocx,
  downloadingPdf,
  downloadingUdf,
  onClose,
  onStartResize,
  onDownloadDocx,
  onDownloadPdf,
  onDownloadUdf,
}) {
  const previewText = String(document?.preview_text || '').trim()

  return (
    <aside className="petition-panel flex flex-col flex-1 min-h-0 overflow-hidden bg-background !p-0 !gap-0 border-l border-border relative isolate h-full z-[1001]" aria-label="Doküman önizleme">
      <div
        className="absolute left-[-3px] top-0 bottom-0 w-[6px] cursor-col-resize z-50 hover:bg-accent transition-colors hidden md:block"
        role="separator"
        aria-orientation="vertical"
        aria-label="Doküman paneli genişliği"
        tabIndex={0}
        onPointerDown={onStartResize}
      />

      <div className="flex flex-row items-center justify-between gap-2 px-3 sm:px-4 py-3 bg-background/85 backdrop-blur-md border-b sticky top-0 z-[60]">
        <div className="flex flex-col min-w-0">
          <h2 className="text-sm font-semibold tracking-tight truncate">Doküman Önizleme</h2>
          <span className="text-xs text-muted-foreground font-medium truncate">
            {document?.filename ? String(document.filename) : 'Üretilen belge içeriği'}
          </span>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" type="button" disabled={loading || !document} className="h-8 text-xs px-2.5 font-semibold">
                <Download className="w-3.5 h-3.5 mr-1" />
                <span>İndir</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-40">
              <DropdownMenuItem disabled={loading || downloadingDocx || !document} onClick={onDownloadDocx}>
                <span>{downloadingDocx ? 'Word indiriliyor...' : 'Word İndir'}</span>
              </DropdownMenuItem>
              <DropdownMenuItem disabled={loading || downloadingPdf || !document} onClick={onDownloadPdf}>
                <span>{downloadingPdf ? 'PDF indiriliyor...' : 'PDF İndir'}</span>
              </DropdownMenuItem>
              <DropdownMenuItem disabled={loading || downloadingUdf || !document} onClick={onDownloadUdf}>
                <span>{downloadingUdf ? 'UDF indiriliyor...' : 'UDF İndir'}</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button variant="ghost" type="button" size="icon" onClick={onClose} className="h-8 w-8 rounded-full ml-0.5" title="Kapat" aria-label="Paneli kapat">
            <X className="w-4 h-4" />
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 md:p-6 flex flex-col gap-6 bg-slate-50/50">
        <div className="bg-card border rounded-xl p-5 shadow-sm flex flex-col gap-4">
          <div className="flex items-center gap-2 text-[11px] font-bold text-muted-foreground uppercase tracking-widest pb-2 border-b">
            <FileText className="w-3.5 h-3.5" />
            <span>Belge Bilgileri</span>
          </div>
          <div className="grid gap-2 text-sm">
            <div><span className="text-muted-foreground">Dosya:</span> {document?.filename || '-'}</div>
            <div><span className="text-muted-foreground">Oluşturulma:</span> {formatDateTime(document?.created_at)}</div>
          </div>
        </div>

        {loading ? <div className="text-muted-foreground text-sm text-center p-8 font-medium">Doküman önizlemesi yükleniyor...</div> : null}
        {error ? <div className="text-destructive text-sm text-center p-8 font-medium">{error}</div> : null}

        {!loading && !error && !document ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center p-10 text-muted-foreground min-h-[300px]">
            <div className="text-base font-semibold text-foreground mb-1">Doküman seçilmedi</div>
            <div className="text-sm">Üretilen dokümanlar burada önizlenir.</div>
          </div>
        ) : null}

        {!loading && !error && document ? (
          <div className="bg-white rounded-lg shadow-sm border p-6 md:p-12 min-h-[600px] ring-1 ring-black/[0.03]">
            <pre className="whitespace-pre-wrap break-words text-[15px] leading-7 text-foreground font-sans">
              {previewText || 'Bu doküman için önizleme içeriği bulunamadı.'}
            </pre>
          </div>
        ) : null}
      </div>
    </aside>
  )
}
