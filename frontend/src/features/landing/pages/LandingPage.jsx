import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  CheckCircle,
  FileText,
  Download,
  BrainCircuit,
  Instagram,
  Linkedin,
  Menu,
  X,
  Search,
  Shield,
  Sparkles,
  ChevronRight,
  Star,
  Gavel,
  BookOpen,
  FileSearch,
  PenTool,
  Clock,
  Zap,
  Users,
  Bot,
  CircleCheck,
  RefreshCcw,
  Play,
  Pause,
  Volume2,
  VolumeX,
  Maximize2,
  ChevronsUpDown,
  Quote,
  ChevronLeft,
  ArrowLeft,
} from 'lucide-react';
import yargucuLogo from '../../../logopack/yargucu-logo-siyah.svg';
import { apiRequest } from '../../../shared/api/client.js';
import { getDemoVideoUrl } from '../../../config/runtime.js';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { InteractiveChatDemo } from '../components/InteractiveChatDemo';
import { SamplePetitionDocument } from '../components/SamplePetitionDocument';

/* ────────────────────────────────────────────────────────────────────
   Inline CSS-in-JS for custom keyframe animations
   (keeps everything self-contained — no extra CSS file needed)
   ──────────────────────────────────────────────────────────────────── */
const inlineStyles = `
  @keyframes landing-fade-up {
    from { opacity: 0; transform: translateY(24px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes landing-fade-in {
    from { opacity: 0; }
    to   { opacity: 1; }
  }
  @keyframes landing-shine {
    from { transform: translateX(-100%); }
    to   { transform: translateX(100%); }
  }
  @keyframes landing-float {
    0%, 100% { transform: translateY(0); }
    50%      { transform: translateY(-8px); }
  }
  @keyframes landing-pulse-ring {
    0%   { transform: scale(1); opacity: 0.5; }
    100% { transform: scale(1.8); opacity: 0; }
  }
  .landing-fade-up   { animation: landing-fade-up 0.7s ease-out both; }
  .landing-fade-up-1 { animation: landing-fade-up 0.7s 0.08s ease-out both; }
  .landing-fade-up-2 { animation: landing-fade-up 0.7s 0.16s ease-out both; }
  .landing-fade-up-3 { animation: landing-fade-up 0.7s 0.24s ease-out both; }
  .landing-fade-up-4 { animation: landing-fade-up 0.7s 0.32s ease-out both; }
  .landing-fade-up-5 { animation: landing-fade-up 0.7s 0.40s ease-out both; }
  .landing-fade-in   { animation: landing-fade-in 1s ease-out both; }
  .landing-float     { animation: landing-float 6s ease-in-out infinite; }
`;

/* ─── Badge ──────────────────────────────────────────────────────── */
function Badge({ children, className = '' }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border border-border bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground ${className}`}
    >
      {children}
    </span>
  );
}

/* ─── Showcase Cards ─────────────────────────────────────────────── */
function ShowcaseCardChat() {
  return (
    <div className="group rounded-xl border border-border bg-card p-4 shadow-sm transition-all duration-300 hover:shadow-md hover:border-foreground/10">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-foreground">
            <Bot size={12} className="text-background" />
          </div>
          <h4 className="text-sm font-semibold text-card-foreground">AI Hukuk Asistanı</h4>
        </div>
        <Badge>Gerçek Zamanlı</Badge>
      </div>
      <div className="space-y-2.5">
        {/* User message */}
        <div className="flex gap-3">
          <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted">
            <Users size={12} className="text-muted-foreground" />
          </div>
          <div className="rounded-lg rounded-tl-sm border border-border bg-muted/50 px-3 py-2">
            <p className="text-[12px] text-foreground">
              Kıdem tazminatı şartları nelerdir?
            </p>
          </div>
        </div>
        {/* AI response */}
        <div className="flex gap-3">
          <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-foreground">
            <Bot size={12} className="text-background" />
          </div>
          <div className="rounded-lg rounded-tl-sm border border-border px-3 py-2">
            <p className="line-clamp-2 text-[12px] text-foreground leading-relaxed">
              En az 1 yıl çalışma, haklı fesih veya işveren feshi ve emsal karar kontrolü birlikte değerlendirilir.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function ShowcaseCardAnalysis() {
  return (
    <div className="group rounded-xl border border-border bg-card p-5 shadow-sm transition-all duration-300 hover:shadow-md hover:border-foreground/10">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-foreground/5">
            <BrainCircuit size={12} className="text-foreground" />
          </div>
          <h4 className="text-sm font-semibold text-card-foreground">Hukuki Analiz</h4>
        </div>
        <Badge>AI Destekli</Badge>
      </div>
      <div className="space-y-3">
        <div className="rounded-lg border border-border bg-muted/40 p-3">
          <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">Olay Özeti</p>
          <p className="text-[13px] text-foreground leading-relaxed">
            İş akdinin feshi sonrası kıdem tazminatı talebi...
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
            <div className="h-full w-[85%] rounded-full bg-foreground" />
          </div>
          <span className="text-[11px] font-semibold tabular-nums text-muted-foreground">%85</span>
        </div>
        <div className="flex items-center gap-1.5 rounded-md bg-foreground/5 px-2.5 py-1.5">
          <CircleCheck size={12} className="text-foreground" />
          <span className="text-xs text-foreground">3 hukuki yol tespit edildi</span>
        </div>
      </div>
    </div>
  );
}

function ShowcaseTierBar({ tier }) {
  const filledSegments = 4 - tier;
  const activeClass =
    tier === 1 ? 'bg-green-600' : tier === 2 ? 'bg-blue-600' : 'bg-slate-400';

  return (
    <div
      className="inline-flex items-center gap-0.5"
      role="img"
      aria-label={`Alaka seviyesi ${filledSegments}/3`}
      title={
        tier === 1
          ? 'Birebir örtüşen karar - en yüksek alaka'
          : tier === 2
            ? 'Yakın emsal - aynı hukuki mesele'
            : 'Aynı konsept - ilke/kıstas paralelliği'
      }
    >
      {[1, 2, 3].map((segment) => (
        <span
          key={segment}
          className={`h-1.5 w-4 rounded-full ${filledSegments >= segment ? activeClass : 'bg-muted'}`}
        />
      ))}
    </div>
  );
}

function ShowcaseCardSearch() {
  const [activeMode, setActiveMode] = React.useState('ai');

  return (
    <div className="group rounded-xl border border-border bg-card p-4 shadow-sm transition-all duration-300 hover:shadow-md hover:border-foreground/10">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-foreground/5">
            <Search size={12} className="text-foreground" />
          </div>
          <h4 className="text-sm font-semibold text-card-foreground">İçtihat Arama</h4>
        </div>
      </div>

      {/* Unified Concept: Search Modes */}
      <div className="mb-3 flex gap-1 rounded-lg border border-border bg-muted/40 p-1">
        {[
          { id: 'ai', label: 'AI Arama' },
          { id: 'keyword', label: 'Kelime' },
          { id: 'semantic', label: 'Semantik' }
        ].map((mode) => (
          <button
            key={mode.id}
            onClick={() => setActiveMode(mode.id)}
            className={`flex-1 rounded-md px-1 py-1 text-[10px] font-bold uppercase tracking-tight transition-all ${
              activeMode === mode.id
                ? 'bg-foreground text-background shadow-sm'
                : 'text-muted-foreground hover:bg-muted'
            }`}
          >
            {mode.label}
          </button>
        ))}
      </div>

      <div className="space-y-2">
        {[
          { court: 'Danıştay 8. Daire', date: '2024', esas: '2022/422', karar: '2024/7819', tier: 1 },
          { court: 'Danıştay 8. Daire', date: '2023', esas: '2023/3146', karar: '2023/2979', tier: 1 },
        ].map((item, i) => (
          <div
            key={i}
            className="rounded-lg border-l-2 border-l-foreground/30 bg-muted/30 p-2 transition-colors hover:bg-muted/50"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate text-[12px] font-medium text-foreground">{item.court}</p>
                <p className="mt-0.5 text-[10px] text-muted-foreground">AI Arama sonucu · {item.date}</p>
              </div>
              <ShowcaseTierBar tier={item.tier} />
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              <span className="rounded-full border border-border bg-background px-2 py-0.5 text-[10px] font-bold text-muted-foreground">
                E: {item.esas}
              </span>
              <span className="rounded-full border border-border bg-background px-2 py-0.5 text-[10px] font-bold text-muted-foreground">
                K: {item.karar}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ShowcaseCardPetition() {
  return (
    <div className="group rounded-xl border border-border bg-card p-4 shadow-sm transition-all duration-300 hover:shadow-md hover:border-foreground/10">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-foreground/5">
            <PenTool size={12} className="text-foreground" />
          </div>
          <h4 className="text-sm font-semibold text-card-foreground">Dilekçe Üretimi</h4>
        </div>
        <Badge>Otomatik</Badge>
      </div>
      <div className="rounded-lg border border-border bg-muted/30 p-3">
        <div className="mb-2.5 flex items-center gap-2 border-b border-border pb-2">
          <FileText size={13} className="text-muted-foreground" />
          <span className="text-xs font-medium text-foreground">Ek Beyan ve Delil Değerlendirme</span>
        </div>
        <div className="mb-2.5 space-y-1.5 rounded-md bg-background/70 p-2.5">
          <p className="text-[10px] font-black uppercase tracking-[0.14em] text-muted-foreground">
            ELBİSTAN SULH CEZA HÂKİMLİĞİNE
          </p>
          <p className="line-clamp-2 text-[11px] leading-relaxed text-foreground">
            2918 sayılı Kanun m.67/1-d kapsamında isnat edilen drift fiilinin, olay anı görüntüsü ve kesintisiz yaka kamerası kaydı olmadan sabit kabul edilemeyeceği yönündeki ek beyanlarımızdır.
          </p>
        </div>
        <div className="flex items-start gap-1.5">
          <CircleCheck size={12} className="text-foreground" />
          <span className="line-clamp-2 text-[11px] leading-relaxed text-muted-foreground">
            Emsaller: Yargıtay 7. CD 2021/15838, Yargıtay 19. CD 2021/3769, Yargıtay 12. CD 2023/694
          </span>
        </div>
      </div>
    </div>
  );
}

/* ─── Feature data ───────────────────────────────────────────────── */
const FEATURES = [
  {
    icon: <BrainCircuit size={18} />,
    title: 'Derinlemesine Hukuki Analiz',
    desc: 'Olayınızı hukuki çerçevede değerlendirir; iddia, savunma ve olası hukuki yollar bakımından kapsamlı analiz sunar.',
  },
  {
    icon: <Search size={18} />,
    title: 'Ai İçtihat Arama',
    desc: 'Yapay zeka yerinizi alamaz; ancak yuzlerce ictihati saniyeler icinde tarayabilir. Yargucu AI Ictihat Arama ozelligiyle zamandan kazanin.',
  },
  {
    icon: <PenTool size={18} />,
    title: 'İçtihat Destekli Dilekçe Yazımı',
    desc: 'Somut olaya uygun dilekçeleri kısa sürede oluşturur; talep ve hukuki dayanakları yapılandırılmış şekilde sunar.',
  },
  {
    icon: <BookOpen size={18} />,
    title: 'Güncel İçtihat ve Mevzuat',
    desc: 'Güncel içtihat ve mevzuatı birlikte tarayarak araştırmalarınızı güncel hukuk zemini üzerinde kurmanızı sağlar.',
  },
  {
    icon: <FileSearch size={18} />,
    title: 'Dosya ve Sözleşme Analizi',
    desc: 'Dava dosyaları ve sözleşmeleri yükleyerek içerikleri hızlıca inceleyin. Kritik noktaları ve risk alanlarını tespit edin.',
  },
  {
    icon: <Sparkles size={18} />,
    title: 'Tek Platform, Tüm Süreçler',
    desc: 'Araştırma, analiz ve üretim süreçlerinizi tek merkezde yönetin. Daha hızlı çalışın, daha isabetli sonuçlara ulaşın.',
  },
];


const PRICING_PLANS = [
  {
    id: 'student',
    name: 'Öğrenci',
    credits: 100,
    priceUsd: 20,
    altUsers: 0,
    description: 'Hukuk öğrencileri için erişilebilir paket.',
    featured: false,
    accent: 'student',
    estimateStr: 'Yaklaşık 40 dilekçe / analiz',
  },
  {
    id: 'starter',
    name: 'Başlangıç',
    credits: 100,
    priceUsd: 30,
    altUsers: 0,
    description: 'Bireysel başlangıç için ideal paket.',
    featured: true,
    accent: 'starter',
    estimateStr: 'Yaklaşık 40 dilekçe / analiz',
  },
  {
    id: 'standard',
    name: 'Standart',
    credits: 200,
    priceUsd: 55,
    altUsers: 0,
    description: 'Düzenli kullanım için dengeli seçenek.',
    featured: false,
    accent: 'standard',
    estimateStr: 'Yaklaşık 85 dilekçe / analiz',
  },
  {
    id: 'advanced',
    name: 'Gelişmiş',
    credits: 300,
    priceUsd: 80,
    altUsers: 0,
    description: 'Yoğun araştırma akışları için güçlü hacim.',
    featured: true,
    accent: 'recommended',
    estimateStr: 'Yaklaşık 135 dilekçe / analiz',
    badge: 'Önerilen',
  },
  {
    id: 'professional',
    name: 'Profesyonel',
    credits: 500,
    priceUsd: 120,
    altUsers: 3,
    description: 'Ofis kullanımı ve ekip paylaşımı için uygun.',
    featured: true,
    accent: 'pro',
    estimateStr: 'Yaklaşık 250 dilekçe / analiz',
    badge: 'En Çok Satan',
  },
  {
    id: 'enterprise',
    name: 'Kurumsal',
    credits: 1000,
    priceUsd: 215,
    altUsers: 10,
    description: 'Ekipler için geniş ölçekli çözüm.',
    featured: false,
    accent: 'enterprise',
    estimateStr: 'Yaklaşık 550 dilekçe / analiz',
  },
];

const FEATURED_PRICING_PLAN_IDS = new Set(['starter', 'advanced', 'professional']);
const FALLBACK_USD_TRY_RATE = 50;
const tryCurrencyFormatter = new Intl.NumberFormat('tr-TR', {
  style: 'currency',
  currency: 'TRY',
  maximumFractionDigits: 0,
});

function formatRoundedTryPrice(priceUsd, usdTryRate) {
  const rate = Number.isFinite(usdTryRate) && usdTryRate > 0 ? usdTryRate : FALLBACK_USD_TRY_RATE;
  const roundedTry = Math.round((priceUsd * rate) / 100) * 100;
  return tryCurrencyFormatter.format(roundedTry);
}

const TESTIMONIALS = [
  {
    quote: "Dilekçe hazırlama sürem 40 dakikadan 5 dakikaya düştü. İşe iade ve tazminat süreçlerimde içtihat bulmak artık inanılmaz hızlı.",
    author: "Av. Yılmaz K.",
    role: "Serbest Avukat, İstanbul",
    initials: "Y",
  },
  {
    quote: "Karmaşık ticaret davalarında emsal bulmak günlerce sürüyordu. Yargucu ile saniyeler içinde Yargıtay'ın en güncel ve lehimize olan kararlarına ulaşıyoruz. Hukuk büromuzun vazgeçilmezi oldu.",
    author: "Av. Meltem S.",
    role: "Hukuk Bürosu Ortağı, Ankara",
    initials: "M",
  },
  {
    quote: "Yapay zeka desteği ile dilekçe taslağı oluşturmak müthiş bir konfor. Sadece anahtar kelimeleri veriyorum, o bana profesyonel ve yasal dayanakları sağlam bir metin hazırlıyor.",
    author: "Av. Serkan T.",
    role: "Kurumsal Hukuk Müşaviri, İzmir",
    initials: "S",
  },
];

const HERO_CONTENT_SETS = [
  {
    title: "Dilekçenizi dakikalar içinde oluşturun ve emsal kararları saniyeler içinde analiz edin",
    subtitle: "Yargucu içtihat taraması yapar madde referansı verir ve otomatik dilekçe taslağı üretir Hukuki süreçlerinizi yapay zekâ ile bir üst seviyeye taşıyın",
  },
  {
    title: "Dosyalarınızı saniyeler içinde özetleyin ve hukuki riskleri anında görün",
    subtitle: "Yüzlerce sayfalık evrakı saniyeler içinde tarayın önemli noktaları ve riskli maddeleri anında yakalayın Vaktinizi stratejiye ayırın",
  },
  {
    title: "Milyonlarca içtihat arasında kaybolmayın ve aradığınız emsali anında bulun",
    subtitle: "Gelişmiş semantik arama ile sadece kelime bazlı değil anlam bazlı arama yaparak en doğru emsale ulaşın Hukukta hız kazanın",
  },
];



/* ═══════════════════════════════════════════════════════════════════
   MAIN PAGE
   ═══════════════════════════════════════════════════════════════════ */
export function LandingPage() {
  const [isScrolled, setIsScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [activeUserCount, setActiveUserCount] = useState(647);
  const [usdTryRate, setUsdTryRate] = useState(null);
  const [isDemoPlaying, setIsDemoPlaying] = useState(false);
  const [demoDuration, setDemoDuration] = useState(0);
  const [demoCurrentTime, setDemoCurrentTime] = useState(0);
  const [showAllPlans, setShowAllPlans] = useState(false);
  const [isDemoMuted, setIsDemoMuted] = useState(false);
  const [testimonialIndex, setTestimonialIndex] = useState(0);
  const [testimonialFade, setTestimonialFade] = useState(false);
  const testimonialTimerRef = useRef(null);
  const videoRef = useRef(null);
  const videoAreaRef = useRef(null);
  const demoVideoUrl = getDemoVideoUrl();
 
  /* scroll to top on mount */
  useEffect(() => {
    window.scrollTo(0, 0);
    // Optional: disable browser scroll restoration to force top on refresh
    if ('scrollRestoration' in window.history) {
      window.history.scrollRestoration = 'manual';
    }
  }, []);

  /* hero rotation */
  const [heroIndex, setHeroIndex] = useState(0);
  const [heroTransition, setHeroTransition] = useState(false);
 
  useEffect(() => {
    const timer = setInterval(() => {
      setHeroTransition(true);
      setTimeout(() => {
        setHeroIndex((prev) => (prev + 1) % HERO_CONTENT_SETS.length);
        setHeroTransition(false);
      }, 500);
    }, 5000);
    return () => clearInterval(timer);
  }, []);

  const nextTestimonial = () => {
    if (testimonialFade) return;
    setTestimonialFade(true);
    setTimeout(() => {
      setTestimonialIndex((prev) => (prev + 1) % TESTIMONIALS.length);
      setTestimonialFade(false);
    }, 400);
  };

  const prevTestimonial = () => {
    if (testimonialFade) return;
    setTestimonialFade(true);
    setTimeout(() => {
      setTestimonialIndex((prev) => (prev - 1 + TESTIMONIALS.length) % TESTIMONIALS.length);
      setTestimonialFade(false);
    }, 400);
  };

  useEffect(() => {
    testimonialTimerRef.current = setInterval(nextTestimonial, 8000);
    return () => clearInterval(testimonialTimerRef.current);
  }, [testimonialFade]);

  const resetTestimonialTimer = () => {
    clearInterval(testimonialTimerRef.current);
    testimonialTimerRef.current = setInterval(nextTestimonial, 8000);
  };
  
  /* scroll listener */
  useEffect(() => {
    const handleScroll = () => setIsScrolled(window.scrollY > 20);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  /* active user count */
  useEffect(() => {
    let cancelled = false;
    async function loadActiveUserCount() {
      try {
        const data = await apiRequest('/v1/public/active-user-count');
        const rawCount =
          data?.active_user_count ??
          data?.count ??
          data?.activeUsers ??
          data?.value;
        const nextCount = Number(rawCount);
        if (!cancelled && Number.isFinite(nextCount) && nextCount >= 0) {
          setActiveUserCount(nextCount);
        }
      } catch {
        // Keep the fallback count on public endpoint failures.
      }
    }
    loadActiveUserCount();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadUsdTryRate() {
      try {
        const data = await apiRequest('/v1/public/usd-try-rate');
        const nextRate = Number(data?.rate);
        if (!cancelled && Number.isFinite(nextRate) && nextRate > 0) {
          setUsdTryRate(nextRate);
        }
      } catch {
        // Use the local fallback rate so public pricing still renders in TRY.
      }
    }

    loadUsdTryRate();
    return () => { cancelled = true; };
  }, []);



  /* smooth scroll */
  const handleSmoothScroll = (e, targetId) => {
    e.preventDefault();
    const element = document.querySelector(targetId);
    if (element) {
      const headerOffset = 72;
      const elementPosition = element.getBoundingClientRect().top;
      const offsetPosition = elementPosition + window.pageYOffset - headerOffset;
      window.scrollTo({ top: offsetPosition, behavior: 'smooth' });
      setMobileMenuOpen(false);
    }
  };

  /* Pilot CTA: scroll so the black "Ücretsiz Başlayın" card is vertically centered in the viewport */
  const handleScrollPilotCtaCentered = (e) => {
    e.preventDefault();
    const element = document.querySelector('#pilot-cta');
    if (!element) return;
    const rect = element.getBoundingClientRect();
    const elTop = rect.top + window.scrollY;
    const elHeight = rect.height;
    const viewportH = window.innerHeight;
    const nextTop = elTop - viewportH / 2 + elHeight / 2;
    window.scrollTo({ top: Math.max(0, nextTop), behavior: 'smooth' });
  };

  /* ── Video Handlers ────────────────────────────────────────────── */
  const handleDemoTogglePlay = async () => {
    const video = videoRef.current;
    if (!video) return;

    if (video.paused) {
      try {
        await video.play();
      } catch {
        setIsDemoPlaying(false);
      }
      return;
    }

    video.pause();
  };

  const handleDemoToggleMute = () => {
    if (!videoRef.current) return;
    videoRef.current.muted = !isDemoMuted;
    setIsDemoMuted(!isDemoMuted);
  };

  const handleDemoFullscreen = () => {
    if (!videoRef.current) return;
    if (videoRef.current.requestFullscreen) {
      videoRef.current.requestFullscreen();
    } else if (videoRef.current.webkitRequestFullscreen) {
      videoRef.current.webkitRequestFullscreen();
    }
  };

  const handleDemoSeek = (e) => {
    const time = parseFloat(e.target.value);
    setDemoCurrentTime(time);
    if (videoRef.current) {
      videoRef.current.currentTime = time;
    }
  };

  const formatVideoTime = (seconds) => {
    if (!seconds) return '0:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleTimeUpdate = () => setDemoCurrentTime(video.currentTime);
    const handleLoadedMetadata = () => setDemoDuration(video.duration);
    const handlePlay = () => setIsDemoPlaying(true);
    const handlePause = () => setIsDemoPlaying(false);
    const handleEnded = () => setIsDemoPlaying(false);

    video.addEventListener('timeupdate', handleTimeUpdate);
    video.addEventListener('loadedmetadata', handleLoadedMetadata);
    video.addEventListener('play', handlePlay);
    video.addEventListener('pause', handlePause);
    video.addEventListener('ended', handleEnded);

    return () => {
      video.removeEventListener('timeupdate', handleTimeUpdate);
      video.removeEventListener('loadedmetadata', handleLoadedMetadata);
      video.removeEventListener('play', handlePlay);
      video.removeEventListener('pause', handlePause);
      video.removeEventListener('ended', handleEnded);
    };
  }, []);

  useEffect(() => {
    const video = videoRef.current;
    const area = videoAreaRef.current;
    if (!video || !area) return undefined;

    // Respect Data Saver: don't fetch the tour video at all unless the user
    // explicitly taps play.
    const conn =
      typeof navigator !== 'undefined' ? navigator.connection || navigator.webkitConnection : null;
    const saveData = Boolean(conn && conn.saveData);

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          if (saveData) {
            // Lift preload just enough to render a poster/metadata, but skip
            // autoplay so the user is in control of the data spend.
            video.preload = 'metadata';
            return;
          }

          // Promote preload now that the area is actually visible; we
          // started with `preload="none"` to keep initial paint cheap.
          video.preload = 'auto';

          // Most mobile browsers will reject `play()` on an unmuted video
          // without a user gesture. Try muted first so autoplay actually
          // works on the tour, then surface the user's mute preference.
          const startedMuted = video.muted;
          video
            .play()
            .then(() => {
              if (!startedMuted) return;
              // If we coerced muted just to satisfy autoplay policy, leave
              // it muted; the explicit mute button stays the source of
              // truth for the user.
            })
            .catch(() => {
              setIsDemoPlaying(false);
            });
          return;
        }

        video.pause();
      },
      { threshold: 0.45 }
    );

    observer.observe(area);
    return () => observer.disconnect();
  }, []);



  /* ── Render ─────────────────────────────────────────────────────── */
  return (
    <div className="landing-page-shell relative min-h-screen bg-background font-sans text-foreground antialiased selection:bg-foreground/10">
      {/* Inject keyframe animations */}
      <style>{inlineStyles}</style>

      {/* ╔══ HEADER ══════════════════════════════════════════════════╗ */}
      <header
        className={`app-safe-top-header fixed inset-x-0 top-0 z-50 transition-all duration-300 ${
          isScrolled
            ? 'border-b border-border/60 bg-background/80 backdrop-blur-xl'
            : 'border-b border-transparent'
        }`}
      >
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

          {/* Desktop Nav */}
          <nav className="hidden items-center gap-1 md:flex">
            {[
              { label: 'Özellikler', href: '#features' },
              { label: 'Fiyatlandırma', href: '#pricing' },
            ].map((item) => (
              <a
                key={item.href}
                href={item.href}
                onClick={(e) => handleSmoothScroll(e, item.href)}
                className="rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                {item.label}
              </a>
            ))}
          </nav>

          {/* Right side */}
          <div className="hidden items-center gap-2 md:flex">
            <Link
              to="/login"
              className="rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              Giriş Yap
            </Link>
            <Link
              to="/register"
              className="inline-flex h-8 items-center justify-center rounded-md bg-foreground px-3.5 text-sm font-medium !text-white shadow-sm transition-all duration-200 hover:bg-foreground/90 active:scale-[0.97]"
            >
              Ücretsiz Başla
            </Link>
          </div>

          {/* Mobile hamburger */}
          <button
            className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted md:hidden"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Menü"
          >
            {mobileMenuOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>

        {/* Mobile dropdown */}
        {mobileMenuOpen && (
          <div className="border-t border-border bg-background px-4 pb-4 pt-3 md:hidden">
            <nav className="flex flex-col gap-1">
              {[
                { label: 'Özellikler', href: '#features' },
                { label: 'Fiyatlandırma', href: '#pricing' },
              ].map((item) => (
                <a
                  key={item.href}
                  href={item.href}
                  className="rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
                  onClick={(e) => handleSmoothScroll(e, item.href)}
                >
                  {item.label}
                </a>
              ))}
              <div className="mt-3 flex flex-col gap-2 border-t border-border pt-3">
                <Link
                  to="/login"
                  className="rounded-md px-3 py-2 text-center text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  Giriş Yap
                </Link>
                <Link
                  to="/register"
                  className="inline-flex h-9 items-center justify-center rounded-md bg-foreground px-4 text-sm font-medium !text-white shadow-sm hover:bg-foreground/90"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  Ücretsiz Başla
                </Link>
              </div>
            </nav>
          </div>
        )}
      </header>

      {/* ╔══ HERO ════════════════════════════════════════════════════╗ */}
      <section className="relative overflow-hidden pt-28 pb-12 md:pt-36 md:pb-16">
        {/* Background Visual Enhancements */}
        <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
          {/* Grid lines with a softer, more precise radial fade */}
          <div
            className="absolute inset-0 bg-[linear-gradient(to_right,#8080800a_1px,transparent_1px),linear-gradient(to_bottom,#8080800a_1px,transparent_1px)] bg-[size:32px_32px]"
            style={{
              maskImage: 'radial-gradient(ellipse 65% 45% at 50% 35%, #000 35%, transparent 100%)',
              WebkitMaskImage: 'radial-gradient(ellipse 65% 45% at 50% 35%, #000 35%, transparent 100%)',
            }}
          />
          
          {/* Multi-layered glow orbs for depth.
              Hidden on phones — three huge `blur-[120px]/[100px]` layers force
              the mobile GPU to paint very large blurred composites on every
              frame, which noticeably delays first paint on mid-tier Android.
              They're purely decorative so md+ is the right floor. */}
          <div className="hidden md:block absolute left-1/2 top-0 h-[600px] w-[1000px] -translate-x-1/2 -translate-y-1/3 rounded-full bg-foreground/[0.025] blur-[120px]" />
          <div className="hidden md:block absolute -left-48 top-40 h-96 w-96 rounded-full bg-foreground/[0.012] blur-[100px]" />
          <div className="hidden md:block absolute -right-48 top-20 h-[500px] w-[500px] rounded-full bg-foreground/[0.012] blur-[120px]" />
          
          {/* Subtle bottom fade transition */}
          <div className="absolute bottom-0 left-0 right-0 h-40 bg-gradient-to-t from-background to-transparent" />
        </div>

        <div className="mx-auto max-w-[1400px] px-4 lg:px-8">
          <div className="flex flex-col items-center text-center">
            {/* Announcement pill */}
            <div className="landing-fade-up mb-8">
              <Link
                to="/register"
                className="group inline-flex items-center gap-2 rounded-full border border-border/80 bg-muted/60 px-4 py-1.5 text-sm backdrop-blur-sm transition-all hover:border-border hover:bg-muted"
              >
                <span className="inline-flex items-center rounded-full bg-foreground px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider !text-white">
                  Yeni
                </span>
                <span className="text-muted-foreground">
                  AI Hukuk Asistanı ile tanışın
                </span>
                <ChevronRight
                  size={14}
                  className="text-muted-foreground/60 transition-transform group-hover:translate-x-0.5"
                />
              </Link>
            </div>

            {/* Heading with depth and gradient - ROTATING */}
            <div className="relative grid grid-cols-1 grid-rows-1">
              {HERO_CONTENT_SETS.map((set, i) => (
                <div 
                  key={i}
                  className={`col-start-1 row-start-1 transition-all duration-600 transform ${
                    i === heroIndex && !heroTransition 
                      ? 'opacity-100 translate-y-0 scale-100 blur-0' 
                      : 'opacity-0 -translate-y-8 scale-95 blur-sm pointer-events-none'
                  }`}
                >
                  <h1 className="landing-fade-up-1 mx-auto max-w-5xl text-center text-[2.25rem] font-bold leading-[1.12] tracking-tight sm:text-5xl md:text-6xl lg:text-[4rem]">
                    <span className="bg-gradient-to-b from-foreground to-foreground/80 bg-clip-text text-transparent">
                      {set.title}
                    </span>
                  </h1>

                  <p className="landing-fade-up-2 mx-auto mt-6 max-w-2xl text-center text-[16px] leading-relaxed text-muted-foreground md:text-lg">
                    {set.subtitle}
                  </p>
                </div>
              ))}
            </div>

            {/* Premium Demo Input (AI Command Bar) — Unified Premium Design */}
            <div className="landing-fade-up-3 group relative mx-auto mt-8 w-full max-w-2xl md:mt-14">
              {/* Outer Glow/Ambient Light */}
              <div className="absolute -inset-2 rounded-[2.5rem] bg-foreground/[0.03] opacity-0 blur-2xl transition-opacity duration-700 group-hover:opacity-100" />
              
              <div className="relative overflow-hidden rounded-2xl border border-border/50 bg-background/40 p-1.5 shadow-[0_32px_64px_-16px_rgba(0,0,0,0.1)] backdrop-blur-3xl transition-all duration-500 group-hover:border-foreground/10 group-hover:shadow-[0_48px_96px_-24px_rgba(0,0,0,0.15)]">
                {/* Internal container with subtle inner shadow */}
                <div className="flex flex-col gap-2 rounded-xl border border-border/20 bg-background/60 p-1 md:bg-background/40 sm:flex-row sm:items-center sm:p-1.5">
                  <div className="flex flex-1 items-center gap-3.5 px-4 py-2.5">
                    <div className="relative flex h-5 w-5 items-center justify-center">
                      <div className="absolute inset-0 animate-pulse rounded-full bg-foreground/5" />
                      <Search size={14} className="relative text-muted-foreground/70" />
                    </div>
                    <input
                      type="text"
                      className="w-full bg-transparent text-[15px] font-medium text-foreground placeholder:text-muted-foreground/50 focus:outline-none sm:text-base"
                      placeholder="Uyuşmazlığınızı buraya yazın..."
                    />
                  </div>
                  <Link
                    to="/login"
                    className="group/btn relative inline-flex h-11 shrink-0 items-center justify-center gap-2 overflow-hidden rounded-lg bg-foreground px-8 text-[13px] font-bold uppercase tracking-wider text-white shadow-lg transition-all hover:bg-foreground/90 active:scale-[0.98] sm:h-12"
                  >
                    <span className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/10 to-transparent transition-transform duration-700 group-hover/btn:translate-x-full" />
                    <div className="relative z-10 flex items-center gap-2 text-white">
                      <Sparkles size={15} className="transition-transform group-hover/btn:scale-110" />
                      Giriş Yap / Kaydol
                      <ArrowRight size={14} className="transition-transform group-hover/btn:translate-x-1" />
                    </div>
                  </Link>
                </div>
                
                {/* Refined Integrated Status Bar */}
                <div className="flex items-center justify-between px-5 pt-3 pb-2">
                  <div className="flex items-center gap-3">
                    <div className="flex -space-x-1.5">
                      {[
                        'bg-slate-200',
                        'bg-slate-300',
                        'bg-slate-400'
                      ].map((bg, i) => (
                        <div key={i} className={`h-4.5 w-4.5 rounded-full border-2 border-background ${bg} ring-1 ring-foreground/5 shadow-sm`} />
                      ))}
                    </div>
                    <div className="flex items-center gap-2 text-[10.5px] font-bold leading-none tracking-widest text-muted-foreground/80">
                      <span className="relative flex h-1.5 w-1.5">
                        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-500/40 opacity-75" />
                        <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-green-500" />
                      </span>
                      {activeUserCount.toLocaleString('tr-TR')}+ AKTİF KULLANICI
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-[10.5px] font-semibold text-muted-foreground/40 sm:gap-1.5">
                    <RefreshCcw size={10} className="animate-spin-slow" />
                    <span className="hidden sm:inline">Real-time analysis</span>
                    <span className="sm:hidden">Aktif Analiz</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Premium Feature Badges — Balanced & Refined */}
            <div className="landing-fade-up-4 mt-16 flex flex-wrap items-center justify-center gap-x-12 gap-y-6">
              {[
                { icon: <Gavel size={14} />, text: 'Yargıtay referanslı analiz' },
                { icon: <FileSearch size={14} />, text: 'Doğrudan kaynak gösterir' },
                { icon: <Shield size={14} />, text: 'KVKK uyumlu & Güvenli' },
                { icon: <Bot size={14} />, text: '7/24 Yapay Zeka Desteği' },
              ].map((t, i) => (
                <div key={i} className="group/badge flex items-center gap-3 transition-transform hover:translate-y-[-1px]">
                  <div className="relative">
                    <div className="absolute inset-0 rounded-full bg-foreground/5 opacity-0 blur-sm transition-opacity group-hover/badge:opacity-100" />
                    <span className="relative flex h-8 w-8 items-center justify-center rounded-full border border-foreground/5 bg-foreground/[0.02] text-foreground/40 transition-all group-hover/badge:border-foreground/10 group-hover/badge:bg-foreground/[0.04] group-hover/badge:text-foreground/70">
                      {t.icon}
                    </span>
                  </div>
                  <span className="text-[13px] font-semibold tracking-tight text-muted-foreground/80 transition-colors group-hover/badge:text-foreground">
                    {t.text}
                  </span>
                </div>
              ))}
            </div>

            <div className="landing-fade-up-5 relative mx-auto mt-8 w-full max-w-4xl px-6 py-5 text-center md:mt-10 md:px-10">
              <div className="pointer-events-none absolute inset-x-8 top-1/2 -z-10 h-24 -translate-y-1/2 rounded-full bg-foreground/[0.035] blur-3xl" />
              <div className="absolute -left-4 top-1/2 hidden -translate-y-1/2 lg:block">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => { prevTestimonial(); resetTestimonialTimer(); }}
                  className="group/arrow h-10 w-10 rounded-full bg-transparent text-muted-foreground transition-all hover:bg-foreground/5 hover:text-foreground active:scale-90"
                >
                  <ArrowLeft size={18} className="transition-transform group-hover/arrow:-translate-x-0.5" />
                </Button>
              </div>
              <div className="absolute -right-4 top-1/2 hidden -translate-y-1/2 lg:block">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => { nextTestimonial(); resetTestimonialTimer(); }}
                  className="group/arrow h-10 w-10 rounded-full bg-transparent text-muted-foreground transition-all hover:bg-foreground/5 hover:text-foreground active:scale-90"
                >
                  <ArrowRight size={18} className="transition-transform group-hover/arrow:translate-x-0.5" />
                </Button>
              </div>

              <div className="mb-4 flex justify-center text-foreground/20">
                <Quote size={28} />
              </div>

              <div className="relative grid grid-cols-1 grid-rows-1">
                {TESTIMONIALS.map((t, i) => (
                  <div
                    key={i}
                    className={`col-start-1 row-start-1 transition-all duration-500 transform ${
                      i === testimonialIndex && !testimonialFade
                        ? 'opacity-100 scale-100 translate-y-0'
                        : 'opacity-0 scale-[0.98] translate-y-2 pointer-events-none'
                    }`}
                  >
                    <p className="mx-auto max-w-3xl text-base font-medium leading-relaxed text-foreground md:text-lg">
                      "{t.quote}"
                    </p>

                    <div className="mt-5 flex items-center justify-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-foreground/10 text-sm font-bold text-foreground ring-4 ring-background">
                        {t.initials}
                      </div>
                      <div className="flex flex-col text-left text-sm">
                        <span className="font-bold text-foreground tracking-tight">{t.author}</span>
                        <span className="text-xs text-muted-foreground">{t.role}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-6 flex justify-center gap-2">
                {TESTIMONIALS.map((_, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      if (i === testimonialIndex || testimonialFade) return;
                      setTestimonialFade(true);
                      setTimeout(() => {
                        setTestimonialIndex(i);
                        setTestimonialFade(false);
                      }, 400);
                      resetTestimonialTimer();
                    }}
                    className={`h-1.5 rounded-full transition-all duration-300 ${i === testimonialIndex ? 'w-8 bg-foreground' : 'w-2 bg-foreground/20 hover:bg-foreground/40'}`}
                    aria-label={`Go to testimonial ${i + 1}`}
                  />
                ))}
              </div>
            </div>
          </div>

        </div>
      </section>

      {/* ╔══ INTERACTIVE DEMO ═══════════════════════════════════════╗ */}
      <section className="bg-background pt-16 pb-8 md:pt-24 md:pb-10 border-t border-border">
        <div className="mx-auto max-w-[1520px] px-4 lg:px-8">
          <div className="mx-auto mb-10 max-w-xl text-center md:mb-14">
            <h2 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
              Web Uygulaması Deneyimi
            </h2>
            <p className="mt-3 text-[15px] text-muted-foreground">
              Yargucu'nun güçlü arayüzünü hemen burada ücretsiz test edin.
            </p>
          </div>
          
          <InteractiveChatDemo />
        </div>
      </section>

      {/* ╔══ VIDEO TOUR ═══════════════════════════════════════════════╗ */}
      <section className="bg-muted/30 py-16 md:py-24 border-t border-border">
        <div className="mx-auto max-w-[1400px] px-4 lg:px-8">
          <div className="mx-auto mb-10 max-w-xl text-center md:mb-14">
            <h2 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
              Uygulama Turu
            </h2>
            <p className="mt-3 text-[15px] text-muted-foreground">
              Yargucu'nun tüm yeteneklerini 5 dakikalık bu videoda izleyin.
            </p>
          </div>

          <div ref={videoAreaRef} className="mx-auto max-w-4xl">
            <div className="group relative aspect-video overflow-hidden rounded-2xl border border-border bg-black shadow-2xl">
              {/* `preload="none"` keeps the demo from touching the network on
                  initial paint. The IntersectionObserver below bumps it to
                  "metadata" (and tries to start playback) once the user has
                  actually scrolled the tour into view. This avoids the
                  cellular tax of an MP4 whose `moov` atom may not be at the
                  head — without it, some mobile browsers fetch a hefty chunk
                  of the file just to satisfy "metadata". */}
              <video
                ref={videoRef}
                className="h-full w-full cursor-pointer object-cover"
                playsInline
                muted={isDemoMuted}
                preload="none"
                onClick={handleDemoTogglePlay}
              >
                <source src={demoVideoUrl} type="video/mp4" />
                Tarayıcınız video oynatmayı desteklemiyor.
              </video>
              
              {/* Central Play Overlay (Only shows when paused) */}
              {!isDemoPlaying && (
                <div 
                  className="absolute inset-0 flex items-center justify-center bg-black/20 backdrop-blur-[2px] cursor-pointer transition-all hover:bg-black/30"
                  onClick={handleDemoTogglePlay}
                >
                  <div className="flex h-20 w-20 items-center justify-center rounded-full bg-white/10 text-white backdrop-blur-md ring-1 ring-white/20 transition-transform hover:scale-110">
                    <Play className="ml-1 size-8 fill-current" />
                  </div>
                </div>
              )}
            </div>

            {/* Video Controls Panel */}
            <div className="mt-6 flex flex-col gap-4 md:flex-row md:items-center bg-background border border-border p-4 rounded-xl shadow-sm">
              <div className="flex items-center gap-3">
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  className="h-9 w-9 shrink-0"
                  onClick={handleDemoTogglePlay}
                  aria-label={isDemoPlaying ? 'Videoyu duraklat' : 'Videoyu oynat'}
                >
                  {isDemoPlaying ? <Pause className="size-4 fill-current" /> : <Play className="size-4 fill-current" />}
                </Button>

                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  className="h-9 w-9 shrink-0"
                  onClick={handleDemoToggleMute}
                  aria-label={isDemoMuted ? 'Videonun sesini aç' : 'Videonun sesini kapat'}
                >
                  {isDemoMuted ? <VolumeX className="size-4" /> : <Volume2 className="size-4" />}
                </Button>

                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  className="h-9 w-9 shrink-0"
                  onClick={handleDemoFullscreen}
                  aria-label="Videoyu tam ekran aç"
                >
                  <Maximize2 className="size-4" />
                </Button>
              </div>

              <div className="flex w-full items-center gap-3">
                <span className="shrink-0 text-xs font-semibold tabular-nums text-muted-foreground min-w-[36px]">
                  {formatVideoTime(demoCurrentTime)}
                </span>

                <input
                  type="range"
                  min="0"
                  max={demoDuration || 0}
                  step="0.1"
                  value={Math.min(demoCurrentTime, demoDuration || 0)}
                  onChange={handleDemoSeek}
                  className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-muted accent-foreground"
                  aria-label="Video ilerleme çubuğu"
                />

                <span className="shrink-0 text-xs font-semibold tabular-nums text-muted-foreground min-w-[36px]">
                  {formatVideoTime(demoDuration)}
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>
      {/* ╔══ FEATURES SHOWCASE (BENTO) ══════════════════════════════╗ */}
      <section className="bg-muted/30 py-16 md:py-24 border-t border-border">
        <div className="mx-auto max-w-6xl px-4 lg:px-8">
          <div className="mx-auto mb-12 max-w-xl text-center">
            <h2 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
              Gelişmiş Özellikler ve Yetenekler
            </h2>
            <p className="mt-4 text-[15px] text-muted-foreground">
              Hukuk süreçlerinizi hızlandırmak için tasarlanmış profesyonel araç setini keşfedin.
            </p>
          </div>

          <div className="landing-fade-up-5 mx-auto max-w-5xl">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <ShowcaseCardChat />
              <ShowcaseCardSearch />
              <ShowcaseCardPetition />
            </div>
          </div>
        </div>
      </section>

      {/* ╔══ SAMPLE PETITION SHOWCASE ════════════════════════════════╗ */}
      <section className="bg-background py-16 md:py-24 border-t border-border">
        <div className="mx-auto max-w-5xl px-4 lg:px-8">
          <div className="flex flex-col items-center gap-12 lg:flex-row lg:items-center">
            {/* Left: Text Content */}
            <div className="flex-1 text-center lg:text-left">
              <Badge variant="outline" className="mb-4 border-foreground/10 bg-foreground/5 text-foreground px-3 py-1 font-semibold tracking-wide">
                GERÇEK ÇIKTI ÖRNEĞİ
              </Badge>
              <h2 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
                Yargucu AI Tarafından Hazırlanmış Dilekçeyi İnceleyin
              </h2>
              <p className="mt-6 text-lg leading-relaxed text-muted-foreground">
                Trafik idari yaptırımına karşı hazırlanmış, içtihat ve delil değerlendirmesi içeren maskeli örnek dilekçeyi inceleyin. Kişisel bilgiler gizlenmiş, kanun ve içtihat dayanakları korunmuştur.
              </p>
              
              <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row lg:justify-start">
                <Button asChild size="lg" className="h-12 px-8 font-bold !text-white shadow-xl hover:scale-105 active:scale-95 transition-all">
                  <a href="/ornek-dilekce-ek-beyan-delil-degerlendirme.docx" download>
                    <Download className="mr-2 h-5 w-5" />
                    Dilekçeyi İndir (.docx)
                  </a>
                </Button>
                <div className="text-xs font-semibold text-muted-foreground uppercase tracking-widest">
                  MASKELİ ÖRNEK • MICROSOFT WORD
                </div>
              </div>
            </div>

            {/* Right: Readable Document Preview */}
            <div className="relative w-full max-w-sm lg:max-w-xl">
              <SamplePetitionDocument className="h-[560px] w-full transition-transform duration-500 hover:scale-[1.01]" />

              {/* Decorative elements */}
              <div className="absolute -right-4 -top-4 -z-10 h-24 w-24 rounded-full bg-foreground/5 blur-2xl" />
              <div className="absolute -bottom-8 -left-8 -z-10 h-32 w-32 rounded-full bg-foreground/3 blur-3xl" />
            </div>
          </div>
        </div>
      </section>

      {/* ╔══ AUDIENCE & PRACTICE AREAS ════════════════════════════════╗ */}
      <section className="relative pt-6 pb-12 md:pt-8 md:pb-16">
        <div className="pointer-events-none absolute inset-x-0 top-1/2 -z-10 h-40 -translate-y-1/2 bg-[radial-gradient(ellipse_at_center,rgba(15,23,42,0.045),transparent_65%)]" />
        <div className="mx-auto max-w-[1400px] px-4 lg:px-8">
          <div className="flex flex-col">
            <h3 className="mb-6 text-center text-2xl font-bold tracking-tight text-foreground">Kimler İçin?</h3>
            <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 lg:gap-6">
              {[
                { label: 'Serbest Avukatlar', desc: 'Bireysel çalışan avukatlar için dijital asistan.' },
                { label: 'Hukuk Büroları', desc: 'Ofis içi verimlilik ve ekip koordinasyonu.' },
                { label: 'Şirket Hukuk Ekipleri', desc: 'Kurumsal uyum ve hızlı risk analizi.' },
                { label: 'Stajyer Avukatlar', desc: 'Hızlı öğrenme ve araştırma desteği.' }
              ].map((item, i) => (
                <li key={i} className="group flex flex-col gap-1 rounded-2xl px-4 py-3 transition-transform hover:-translate-y-0.5">
                  <div className="flex items-center gap-2.5 text-[15px] font-bold text-foreground">
                    <CheckCircle size={18} className="text-foreground/50 shrink-0 transition-colors group-hover:text-foreground" />
                    {item.label}
                  </div>
                  <p className="pl-7 text-xs text-muted-foreground leading-relaxed">
                    {item.desc}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* ╔══ FEATURES ════════════════════════════════════════════════╗ */}
      <section id="features" className="border-t border-border py-20 md:py-28">
        <div className="mx-auto max-w-[1400px] px-4 lg:px-8">
          <div className="mx-auto mb-12 max-w-xl text-center md:mb-16">
            <p className="mb-3 text-sm font-semibold text-muted-foreground">Özellikler</p>
            <h2 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
              Hukuki Araştırmada Sınırları Kaldırın
            </h2>
            <p className="mt-3 text-[15px] text-muted-foreground">
              Yargucu'nun yapay zeka destekli özellikleri ile dava süreçlerinizi kusursuz yönetin.
            </p>
          </div>

          <div className="mx-auto grid max-w-5xl gap-px overflow-hidden rounded-xl border border-border bg-border sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f, i) => (
              <div
                key={i}
                className="group bg-background p-6 transition-colors hover:bg-muted/40 md:p-8"
              >
                <div className="mb-4 flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-background text-foreground shadow-sm transition-colors group-hover:bg-foreground group-hover:text-background">
                  {f.icon}
                </div>
                <h3 className="mb-2 text-[15px] font-semibold text-foreground">{f.title}</h3>
                <p className="text-sm leading-relaxed text-muted-foreground">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>


      {/* ╔══ CTA / PRICING ═══════════════════════════════════════════╗ */}
      <section id="pricing" className="border-t border-border py-20 md:py-28">
        <div className="mx-auto max-w-[1400px] px-4 lg:px-8">
          <div className="mx-auto mb-12 max-w-2xl text-center md:mb-16">
            <p className="mb-3 text-sm font-semibold text-muted-foreground">Fiyatlandırma</p>
            <h2 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl md:text-4xl">
              İhtiyacınıza Uygun Paketi Seçin
            </h2>
            <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground md:text-base">
              Paketler kredi bazlıdır ve fiyatlara KDV dahildir. Kullanım hacminize göre artan
              yapıda ilerleyebilir, ihtiyacınız büyüdükçe bir üst pakete geçebilirsiniz.
            </p>
          </div>

          <div className="mx-auto grid max-w-5xl gap-8 md:grid-cols-3">
            {PRICING_PLANS.filter((plan) => FEATURED_PRICING_PLAN_IDS.has(plan.id)).map((plan) => {
              const isRecommended = plan.accent === 'recommended';
              const isPro = plan.accent === 'pro';
              const priceStr = formatRoundedTryPrice(plan.priceUsd, usdTryRate);

              return (
                <Card
                  key={plan.id}
                  className={`flex flex-col justify-between transition-all duration-300 hover:shadow-md overflow-visible relative group/card ${
                    isRecommended ? 'border-2 border-foreground shadow-lg scale-[1.02] z-10' : 'border border-border'
                  }`}
                >
                  {isRecommended && (
                    <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 z-10 whitespace-nowrap px-4 py-1 text-[10px] font-bold uppercase tracking-[0.15em] rounded-full bg-foreground text-background shadow-md">
                      Önerilen
                    </div>
                  )}
                  {isPro && (
                    <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 z-10 whitespace-nowrap px-4 py-1 text-[10px] font-bold uppercase tracking-[0.15em] rounded-full bg-background text-foreground border border-border shadow-md">
                      En Çok Satan
                    </div>
                  )}

                  <CardHeader className="pb-4">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-xl font-bold">{plan.name}</CardTitle>
                      {isPro && (
                        <div className="flex h-6 w-6 items-center justify-center rounded-full bg-foreground/5 text-foreground">
                          <Zap size={12} className="fill-current" />
                        </div>
                      )}
                    </div>
                    <CardDescription className="pt-2 text-[13px] leading-relaxed">
                      {plan.description}
                    </CardDescription>
                  </CardHeader>

                  <CardContent className="flex flex-1 flex-col space-y-6">
                    <div className="flex items-baseline gap-1.5">
                      <span className="text-4xl font-black tracking-tight">{priceStr}</span>
                      <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">/ Paket</span>
                    </div>

                    <div className="h-px w-full bg-gradient-to-r from-transparent via-border to-transparent" />

                    <ul className="flex-1 space-y-4">
                      <li className="flex items-center gap-3 text-sm">
                        <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-foreground/5">
                          <CheckCircle size={14} className="text-foreground" />
                        </div>
                        <span className="font-bold text-foreground">{plan.credits} Kredi</span>
                      </li>
                      <li className="flex items-center gap-3 text-sm">
                        <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-foreground/5">
                          <CheckCircle size={14} className="text-foreground" />
                        </div>
                        <span className="text-muted-foreground">{plan.estimateStr}</span>
                      </li>
                      <li className="flex items-center gap-3 text-sm">
                        <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-foreground/5">
                          <CheckCircle size={14} className="text-foreground" />
                        </div>
                        <span className="text-muted-foreground font-medium whitespace-nowrap">Tam Yargucu AI Deneyimi</span>
                      </li>
                      {plan.altUsers > 0 && (
                        <li className="flex items-center gap-3 text-sm">
                          <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-foreground/5">
                            <CheckCircle size={14} className="text-foreground" />
                          </div>
                          <span className="text-muted-foreground font-medium">{plan.altUsers} alt kullanıcı dahil</span>
                        </li>
                      )}
                    </ul>
                  </CardContent>

                  <CardFooter className="pt-2">
                    <Button 
                      asChild
                      variant={isRecommended ? 'default' : 'outline'}
                      className={`w-full h-11 font-bold tracking-tight rounded-xl transition-all hover:scale-[1.02] active:scale-[0.98] ${isRecommended ? '!text-white shadow-lg' : ''}`}
                    >
                      <a href="#pilot-cta" onClick={handleScrollPilotCtaCentered}>
                        Paketi Seç
                      </a>
                    </Button>
                  </CardFooter>
                </Card>
              );
            })}
          </div>

          {/* Expandable Section for All Plans */}
          <div className="mx-auto mt-12 max-w-4xl flex flex-col items-center">
            <button
              onClick={() => setShowAllPlans(!showAllPlans)}
              className="group flex items-center gap-2 rounded-full border border-border bg-muted/30 px-6 py-2.5 text-sm font-semibold text-muted-foreground transition-all hover:bg-muted hover:text-foreground"
            >
              <span>{showAllPlans ? 'Daha Az Göster' : 'Tüm Paketleri Gör'}</span>
              <ChevronsUpDown size={14} className={`transition-transform duration-300 ${showAllPlans ? 'rotate-180' : ''}`} />
            </button>

            {showAllPlans && (
              <div className="mt-8 w-full overflow-hidden rounded-2xl border border-border bg-card shadow-sm landing-fade-in">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-border bg-muted/50">
                        <th className="px-6 py-4 font-bold text-foreground">Paket Adı</th>
                        <th className="px-6 py-4 font-bold text-foreground">Kredi</th>
                        <th className="hidden md:table-cell px-6 py-4 font-bold text-foreground">Alt Kullanıcı</th>
                        <th className="hidden sm:table-cell px-6 py-4 font-bold text-foreground">Kullanım Tahmini</th>
                        <th className="px-6 py-4 font-bold text-foreground text-right">Fiyat</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {PRICING_PLANS.map((plan) => (
                        <tr key={plan.id} className="transition-colors hover:bg-muted/30">
                          <td className="px-6 py-4 font-semibold text-foreground">
                            <div className="flex items-center gap-2">
                              {plan.name}
                              {plan.badge && <Badge className="text-[9px] px-1.5 py-0 bg-foreground/10 text-foreground border-none">{plan.badge}</Badge>}
                            </div>
                          </td>
                          <td className="px-6 py-4 text-muted-foreground">{plan.credits}</td>
                          <td className="hidden md:table-cell px-6 py-4 text-muted-foreground">
                            {plan.altUsers > 0 ? plan.altUsers : 'Yok'}
                          </td>
                          <td className="hidden sm:table-cell px-6 py-4 text-muted-foreground">{plan.estimateStr}</td>
                          <td className="px-6 py-4 font-bold text-foreground text-right">
                            {formatRoundedTryPrice(plan.priceUsd, usdTryRate)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          <div
            id="pilot-cta"
            className="relative mx-auto mt-12 max-w-3xl overflow-hidden rounded-2xl border border-foreground/10 bg-foreground p-8 text-center shadow-2xl md:mt-16 md:p-14"
          >
            {/* Glow decorations */}
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(255,255,255,0.12)_0%,transparent_55%)]" />
            <div className="pointer-events-none absolute -top-20 left-1/2 h-40 w-80 -translate-x-1/2 rounded-full bg-white/8 blur-3xl" />

            <div className="relative z-10">
              {/* Status badge */}
              <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-4 py-1.5 text-xs font-semibold text-white/90 backdrop-blur-sm">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-green-400" />
                </span>
                Pilot Süreç Aktif
              </div>

              <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl md:text-4xl">
                Hemen Ücretsiz Başlayın
              </h2>
              <p className="mx-auto mt-4 max-w-lg text-[15px] leading-relaxed text-white/65 md:text-base">
                Yargucu şu anda pilot kullanım aşamasında. Platformu ücretsiz deneyebilir,
                hukuk operasyonlarınıza nasıl katkı sağladığını doğrudan görebilirsiniz.
              </p>

              {/* CTA buttons */}
              <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <Link
                  to="/register"
                  className="group relative inline-flex h-11 items-center justify-center gap-2 overflow-hidden rounded-lg bg-white px-7 text-sm font-semibold !text-black shadow-lg shadow-black/15 transition-all duration-300 hover:shadow-xl hover:scale-[1.02] active:scale-[0.98]"
                >
                  <span className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-foreground/5 to-transparent transition-transform duration-700 group-hover:translate-x-full" />
                  <span className="relative flex items-center gap-2">
                    Ücretsiz Deneyin
                    <ArrowRight size={14} className="transition-transform duration-300 group-hover:translate-x-0.5" />
                  </span>
                </Link>
                <a
                  href="mailto:iletisim@yargucu.com.tr"
                  className="inline-flex h-11 items-center justify-center rounded-lg border border-white/15 bg-white/5 px-7 text-sm font-medium !text-white/90 backdrop-blur-sm transition-all duration-300 hover:bg-white/10 hover:border-white/25 active:scale-[0.98]"
                >
                  Bilgi Alın
                </a>
              </div>

              {/* Trust line */}
              <div className="mt-7 flex flex-wrap items-center justify-center gap-x-5 gap-y-2">
                {[
                  { icon: <CheckCircle size={12} />, text: 'Kredi kartı gerekmez' },
                  { icon: <Clock size={12} />, text: '30 saniyede kurulum' },
                  { icon: <Star size={12} />, text: 'Tüm özellikler dahil' },
                ].map((t, i) => (
                  <div key={i} className="flex items-center gap-1.5 text-xs text-white/40">
                    {t.icon}
                    <span>{t.text}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ╔══ FOOTER ══════════════════════════════════════════════════╗ */}
      <footer className="landing-footer border-t border-border bg-background">
        <div className="mx-auto max-w-[1400px] px-4 lg:px-8">
          {/* Main footer grid */}
          <div className="grid gap-10 py-12 sm:grid-cols-2 md:py-16 lg:grid-cols-5">
            {/* Brand column */}
            <div className="lg:col-span-2">
              <Link to="/" className="mb-4 inline-flex items-center gap-3">
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
              <p className="mt-3 max-w-xs text-sm leading-relaxed text-muted-foreground">
                Yeni nesil yapay zeka destekli hukuk asistanınız ile karmaşık süreçleri basitleştirin ve daima bir adım önde olun.
              </p>
              {/* Social icons */}
              <div className="mt-5 flex items-center gap-1">
                <a
                  href="https://www.instagram.com/yargucu.com.tr/?utm_source=ig_web_button_share_sheet"
                  target="_blank"
                  rel="noreferrer"
                  aria-label="Instagram"
                  className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  <Instagram size={15} />
                </a>
                <a
                  href="https://www.linkedin.com/company/yargucu"
                  target="_blank"
                  rel="noreferrer"
                  aria-label="LinkedIn"
                  className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  <Linkedin size={15} />
                </a>
              </div>
            </div>

            {/* Product links */}
            <div>
              <h4 className="mb-4 text-sm font-semibold text-foreground">Ürün</h4>
              <ul className="space-y-2.5">
                <li>
                  <a href="#features" onClick={(e) => handleSmoothScroll(e, '#features')} className="text-sm text-muted-foreground transition-colors hover:text-foreground">
                    Özellikler
                  </a>
                </li>
                <li>
                  <Link to="/integrations" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
                    Entegrasyonlar
                  </Link>
                </li>
                <li>
                  <a href="#pricing" onClick={(e) => handleSmoothScroll(e, '#pricing')} className="text-sm text-muted-foreground transition-colors hover:text-foreground">
                    Fiyatlandırma
                  </a>
                </li>
              </ul>
            </div>

            {/* Company links */}
            <div>
              <h4 className="mb-4 text-sm font-semibold text-foreground">Şirket</h4>
              <ul className="space-y-2.5">
                <li>
                  <a href="#" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
                    Hakkımızda
                  </a>
                </li>
                <li>
                  <a href="mailto:iletisim@yargucu.com.tr" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
                    İletişim
                  </a>
                </li>
                <li>
                  <a href="#" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
                    Kariyer
                  </a>
                </li>
              </ul>
            </div>

            {/* Legal links */}
            <div>
              <h4 className="mb-4 text-sm font-semibold text-foreground">Yasal</h4>
              <ul className="space-y-2.5">
                <li>
                  <a href="#" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
                    Kullanım Koşulları
                  </a>
                </li>
                <li>
                  <a href="#" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
                    Gizlilik Politikası
                  </a>
                </li>
                <li>
                  <a href="#" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
                    KVKK Aydınlatma Metni
                  </a>
                </li>
              </ul>
            </div>
          </div>

          {/* Bottom bar */}
          <div className="flex flex-col items-center justify-between gap-3 border-t border-border py-6 text-xs text-muted-foreground sm:flex-row">
            <p>© {new Date().getFullYear()} Yargucu Bilişim Teknolojileri A.Ş. Tüm hakları saklıdır.</p>
            <div className="flex items-center gap-4">
              <a href="#" className="transition-colors hover:text-foreground">Gizlilik</a>
              <a href="#" className="transition-colors hover:text-foreground">Koşullar</a>
              <a href="#" className="transition-colors hover:text-foreground">KVKK</a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
