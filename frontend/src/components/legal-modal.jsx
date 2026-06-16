import React from 'react'
import { X } from 'lucide-react'

export function LegalModal({ isOpen, type, onClose }) {
  if (!isOpen) return null;

  const content = type === 'terms' ? {
    title: "Kullanım Şartları",
    text: "1. Hizmet Kapsamı\nYargucu AI, hukuk profesyonellerine içtihat taraması ve makine öğrenimi destekli dosya analizi aracı sunar. Üretilen hukuki metinler ve sonuçlar kesin hüküm veya hukuki tavsiye niteliği taşımaz; doğrulama sorumluluğu kullanıcıya aittir.\n\n2. Hesap Güvenliği\nKullanıcı, hesap bilgilerinin gizliliğinden bizzat sorumludur. Hesabınız üzerinden yapılan tüm işlemlerin sizin tarafınızdan yapıldığı kabul edilir.\n\n3. Abonelik ve Kotalar\nSistem, seçtiğiniz abonelik planına bağlı AI kullanım kotalarına tabidir. Sistemin otomatik botlar ile veya adil kullanımı aşacak şekilde kötüye kullanılması durumunda hesap askıya alınabilir.\n\n4. Veri İhlali Bildirimi\nOlası bir siber güvenlik olayı yaşanması durumunda Yargucu, yürürlükteki yasal mevzuat kapsamında gerekli bildirimleri zamanında yapmayı taahhüt eder."
  } : {
    title: "Gizlilik Politikası",
    text: "1. Veri Güvenliği ve Şifreleme\nYüklediğiniz dava dosyaları, dilekçeler ve kişisel verileriniz uçtan uca AES-256 standardı ile şifrelenir. Verileriniz, yasal zorunluluklar haricinde hiçbir üçüncü parti kurum ile paylaşılmaz.\n\n2. Yapay Zeka Model Eğitimi (KVKK)\nKullanıcılar tarafından yüklenen özel dokümanlar veya dava klasörleri, genel dil modellerimizin (LLM) eğitiminde kesinlikle KULLANILMAZ. Ajan modellerimiz kapalı devre çalışarak sadece anlık işlem esnasında veriyi okur ve siler.\n\n3. Çerez (Cookie) Kullanımı\nPlatform kalitesini artırmak ve oturum yönetimini sağlamak için zorunlu (oturum) çerezleri kullanılmaktadır. Reklam takibi amacıyla harici çerez kullanılmaz.\n\n4. Veri Silme Hakkı (Unutulma)\nHesabınızı silme talebinde bulunduğunuz an itibarıyla, size ait tüm veriler (yedekler dahil) KVKK'nın gerektirdiği yasal saklama süreleri haricinde kalıcı olarak sistemlerimizden yok edilir."
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm animate-in fade-in duration-200" 
        onClick={onClose} 
      />
      
      {/* Modal Dialog */}
      <div className="relative bg-background border border-border shadow-2xl rounded-2xl w-full max-w-lg overflow-hidden animate-in zoom-in-95 slide-in-from-bottom-4 duration-300">
        
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-border/50 bg-muted/30">
          <h2 className="text-lg font-semibold tracking-tight">{content.title}</h2>
          <button 
            onClick={onClose} 
            className="p-2 -mr-2 text-muted-foreground hover:bg-muted rounded-full transition-colors flex items-center justify-center shrink-0"
          >
            <X size={18} strokeWidth={2.5} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[60vh]">
          <div className="space-y-6">
            {content.text.split('\n\n').map((paragraph, idx) => {
              const [title, ...rest] = paragraph.split('\n');
              return (
                <div key={idx}>
                  <h3 className="text-sm font-semibold text-foreground mb-1.5">{title}</h3>
                  <p className="text-[13px] text-muted-foreground leading-relaxed">
                    {rest.join('\n')}
                  </p>
                </div>
              )
            })}
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 pt-2 border-t border-border/50">
          <button 
            onClick={onClose}
            className="w-full flex items-center justify-center rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors shadow-sm"
          >
            Anladım, Kapat
          </button>
        </div>
      </div>
    </div>
  )
}
