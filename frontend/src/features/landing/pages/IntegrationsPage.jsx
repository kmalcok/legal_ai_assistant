import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Mail, Puzzle, ShieldCheck, Instagram, Linkedin } from 'lucide-react';
import yargucuLogo from '../../../logopack/yargucu-logo-siyah.svg';

export function IntegrationsPage() {
  return (
    <div className="landing-page-shell relative min-h-screen bg-background font-sans text-foreground antialiased selection:bg-foreground/10">
      {/* ── Header ──────────────────────────────────────────────── */}
      <header className="app-safe-top-header sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-[1400px] items-center justify-between px-4 lg:px-8">
          <Link to="/" className="flex items-center gap-3 transition-opacity hover:opacity-80">
            <img src={yargucuLogo} alt="Yargucu" className="h-7 w-auto" />
            <div className="flex flex-col">
              <span className="text-sm font-extrabold uppercase tracking-[0.2em] text-foreground leading-none">
                YARGUCU
              </span>
              <span className="text-[10px] font-medium tracking-wider text-muted-foreground leading-none mt-0.5">
                AI Hukuk Asistanı
              </span>
            </div>
          </Link>

          <Link
            to="/"
            className="inline-flex h-8 items-center justify-center gap-2 rounded-md border border-border bg-background px-3 text-sm font-medium text-foreground shadow-sm transition-all hover:bg-muted active:scale-[0.97]"
          >
            <ArrowLeft size={14} />
            Ana Sayfa
          </Link>
        </div>
      </header>

      {/* ── Main Content ────────────────────────────────────────── */}
      <main>
        <section className="relative py-20 md:py-28">
          {/* Grid pattern background */}
          <div className="pointer-events-none absolute inset-0 -z-10">
            <div
              className="absolute inset-0 bg-[linear-gradient(to_right,#80808008_1px,transparent_1px),linear-gradient(to_bottom,#80808008_1px,transparent_1px)] bg-[size:28px_28px]"
              style={{
                maskImage: 'radial-gradient(ellipse 60% 50% at 50% 30%, #000 40%, transparent 100%)',
                WebkitMaskImage: 'radial-gradient(ellipse 60% 50% at 50% 30%, #000 40%, transparent 100%)',
              }}
            />
          </div>

          <div className="mx-auto max-w-[1400px] px-4 lg:px-8">
            {/* Hero */}
            <div className="mx-auto max-w-2xl text-center">
              <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-border bg-muted/50 px-4 py-1.5 text-sm font-medium text-muted-foreground">
                <Puzzle size={14} />
                Entegrasyonlar
              </div>

              <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl md:text-5xl">
                Entegrasyon talepleriniz için{' '}
                <span className="text-muted-foreground">
                  teknik birimle iletişime geçin
                </span>
              </h1>

              <p className="mx-auto mt-5 max-w-xl text-[15px] leading-relaxed text-muted-foreground">
                Kullanmak istediğiniz sistemleri, beklediğiniz akışı ve teknik ihtiyaçlarınızı
                bizimle paylaşın; ekibimiz size en uygun yönlendirmeyi sağlasın.
              </p>
            </div>

            {/* Contact Card */}
            <div className="mx-auto mt-14 max-w-3xl overflow-hidden rounded-xl border border-border bg-card shadow-sm">
              <div className="grid gap-0 md:grid-cols-[1fr_1fr]">
                {/* Left: Info */}
                <div className="p-6 md:p-8">
                  <div className="mb-4 inline-flex items-center gap-1.5 rounded-md border border-border bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
                    <ShieldCheck size={12} />
                    Teknik değerlendirme
                  </div>
                  <h2 className="text-xl font-bold tracking-tight text-foreground md:text-2xl">
                    Kurumunuza uygun entegrasyon akışını birlikte planlayalım.
                  </h2>
                  <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                    API bağlantıları, veri akışları, iç sistem entegrasyonları veya özel kurumsal
                    ihtiyaçlar için doğrudan teknik ekiple temas kurabilirsiniz.
                  </p>
                </div>

                {/* Right: Contact */}
                <div className="border-t border-border bg-muted/30 p-6 md:border-l md:border-t-0 md:p-8">
                  <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.15em] text-muted-foreground">
                    İletişim
                  </p>
                  <p className="mb-1 text-base font-bold text-foreground md:text-lg">
                    iletisim@yargucu.com.tr
                  </p>
                  <p className="mb-6 text-sm leading-relaxed text-muted-foreground">
                    Entegrasyon konusu ve teknik detayları mailinize eklerseniz süreç daha hızlı ilerler.
                  </p>
                  <a
                    href="mailto:iletisim@yargucu.com.tr"
                    className="group relative inline-flex h-10 w-full items-center justify-center gap-2 overflow-hidden rounded-lg bg-foreground px-6 text-sm font-semibold !text-white shadow-md shadow-foreground/15 transition-all duration-300 hover:shadow-lg hover:scale-[1.01] active:scale-[0.98]"
                  >
                    <span className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/15 to-transparent transition-transform duration-700 group-hover:translate-x-full" />
                    <span className="relative flex items-center gap-2">
                      <Mail size={15} />
                      Mail Gönder
                    </span>
                  </a>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* ── Footer ──────────────────────────────────────────────── */}
      <footer className="landing-footer border-t border-border">
        <div className="mx-auto flex max-w-[1400px] flex-col items-center justify-between gap-4 px-4 py-6 text-sm text-muted-foreground md:flex-row lg:px-8">
          <div className="flex items-center gap-3">
            <img src={yargucuLogo} alt="Yargucu" className="h-4 w-auto opacity-50" />
            <span>© {new Date().getFullYear()} Yargucu Bilişim Teknolojileri A.Ş.</span>
          </div>
          <div className="flex items-center gap-1">
            <Link
              to="/"
              className="rounded-md px-2.5 py-1 transition-colors hover:bg-muted hover:text-foreground"
            >
              Ana Sayfa
            </Link>
            <a
              href="mailto:iletisim@yargucu.com.tr"
              className="rounded-md px-2.5 py-1 transition-colors hover:bg-muted hover:text-foreground"
            >
              İletişim
            </a>
            <span className="mx-1 h-3 w-px bg-border" />
            <a
              href="https://www.instagram.com/yargucu.com.tr/?utm_source=ig_web_button_share_sheet"
              target="_blank"
              rel="noreferrer"
              aria-label="Instagram"
              className="flex h-7 w-7 items-center justify-center rounded-md transition-colors hover:bg-muted hover:text-foreground"
            >
              <Instagram size={13} />
            </a>
            <button
              type="button"
              aria-label="LinkedIn"
              title="LinkedIn yakında"
              className="flex h-7 w-7 items-center justify-center rounded-md transition-colors hover:bg-muted hover:text-foreground"
            >
              <Linkedin size={13} />
            </button>
          </div>
        </div>
      </footer>
    </div>
  );
}
