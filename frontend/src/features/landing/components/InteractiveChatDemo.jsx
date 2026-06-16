import React, { useState, useEffect, useRef } from 'react';
import {
  Search,
  MessageSquare,
  FileText,
  Scale,
  PanelLeftClose,
  ArrowUpRight,
  Plus,
  ChevronsUpDown,
  Paperclip,
  ArrowUp,
  ChevronRight,
  Copy,
  Check,
  Trash2,
  Download,
  RotateCcw,
  ChevronLeft,
} from 'lucide-react';
import yargucuLogoBlack from "../../../logopack/yargucu-logo-siyah.svg";
import { SamplePetitionDocument } from './SamplePetitionDocument';

/* ── Demo data ────────────────────────────────────────────────────── */

const DEMO_CHATS = [
  { id: 1, label: 'Somut olayda müvekkil...' },
  { id: 2, label: 'Kıdem tazminatı hesaplama' },
  { id: 3, label: 'İşe iade prosedürü' },
];

const EMPTY_CHAT_SUGGESTIONS = [
  {
    label: 'Dilekçe',
    title: 'Taslak metni hızlıca kur',
    description: 'Talep, olay ve hedefinizi yazın; iskeleti doğru sırayla hazırlayayım.',
    prompt: 'Tahliye ihtarnamesi için kısa ve resmi bir taslak hazırla; kiracı iki aydır ödeme yapmıyor.',
  },
  {
    label: 'İçtihat',
    title: 'Emsal kararları karşılaştır',
    description: 'Uyuşmazlığı yazın; ilgili Yargıtay kararlarını özetleyip ayırayım.',
    prompt: 'Haksız fesihte işçilik alacaklarına ilişkin güncel Yargıtay kararlarını karşılaştırmalı özetle.',
  },
  {
    label: 'Analiz',
    title: 'Madde bazlı riskleri çıkar',
    description: 'Sözleşme veya olay örgüsü üzerinden güçlü ve zayıf noktaları netleştireyim.',
    prompt: 'TBK kapsamında kira sözleşmesinin fesih şartlarını madde bazlı ve pratik riskleriyle incele.',
  },
  {
    label: 'Süreç',
    title: 'Başvuru yolunu planla',
    description: 'Süre, görevli merci ve gerekli adımları uygulanabilir sırayla yazayım.',
    prompt: "İİK'da itirazın kaldırılması yolunu süre, şartlar ve içtihat bağlantısıyla açıkla.",
  },
];

const DEMO_AI_RESPONSE = `4857 sayılı İş Kanunu'nun 18. ve 21. maddeleri kapsamında, iş güvencesi koşullarını sağlayan bir işçinin iş sözleşmesinin geçerli bir neden olmaksızın feshedilmesi halinde, işe iade davası açma hakkı bulunmaktadır.

**Fesih bildirimi şekil şartları:**

1. Fesih bildirimi **yazılı** olarak yapılmalıdır
2. Fesih **sebebi açık ve kesin** bir şekilde belirtilmelidir
3. İşçinin **savunması alınmalıdır** (davranış veya verim nedeniyle fesihlerde)

**İlgili Yargıtay kararları:**

Yargıtay 9. Hukuk Dairesi'nin 2023/12456 E., 2024/4567 K. sayılı kararında, fesih bildiriminde sebebin açıkça belirtilmemesinin feshi geçersiz kılacağı vurgulanmıştır.

> "Fesih bildiriminde fesih sebebinin somut olarak gösterilmemesi, feshi başlı başına geçersiz kılar."`;

const ICTIHAT_RESULTS = [
  {
    court: 'Danıştay 8. Daire',
    esas: '2022/422',
    karar: '2024/7819',
    date: '27.12.2024',
    tier: 1,
    why: 'Drift tespitinde MOBESE ve çevre kamera kaydı bulunmadığında yalnız kolluk tutanağıyla yetinilemeyeceğini tartışır.',
    summary:
      "Davacının aracına 2918 sayılı Kanun'un 67/1-d maddesi uyarınca idari para cezası, trafikten men ve sürücü belgesine el koyma işlemi uygulanmıştır. Mahkeme, drift iddiasını destekleyen MOBESE kaydı sunulmadığını ve yalnız tutanakla sonuca gidilemeyeceğini belirterek işlemi iptal etmiştir.",
  },
  {
    court: 'Danıştay 8. Daire',
    esas: '2024/1124',
    karar: '2024/1166',
    date: '06.03.2024',
    tier: 1,
    why: "67/1-d yaptırımlarının kapsamı ve sürücü belgesi geri alma süresi yönünden doğrudan emsaldir.",
    summary:
      "Drift fiili sabit kabul edilerek idari para cezası, aracın trafikten meni ve sürücü belgesinin geri alınması işlemi tesis edilmiştir. İlk derece mahkemesi, geri alma süresindeki kanuni sınırı aşan kısmı iptal etmiş; diğer kısımlar yönünden davayı reddetmiştir.",
  },
  {
    court: 'Danıştay 8. Daire',
    esas: '2023/3146',
    karar: '2023/2979',
    date: '01.06.2023',
    tier: 1,
    why: 'Dönel kavşakta yanlama/drift iddiasında fotoğraf-video delili aranması gerektiğini açıkça söyler.',
    summary:
      "Davacının dönel kavşak içinde aracın yönünü ani değiştirdiği iddiasıyla 2918 sayılı Kanun'un 67/1-d maddesi uygulanmıştır. Mahkeme, fiili her türlü şüpheden uzak biçimde gösteren fotoğraf veya video kaydı bulunmadığını belirterek eksik tespite dayalı işlemi iptal etmiştir.",
  },
  {
    court: 'Uyuşmazlık Mahkemesi',
    esas: '2025/639',
    karar: '2025/795',
    date: '22.12.2025',
    tier: 2,
    why: 'Kaygan yol nedeniyle istem dışı kayma savunmasının 67/1-d yaptırımına karşı nasıl ileri sürüldüğünü gösterir.',
    summary:
      'Davacı, sola dönüş yaparken yolun kaygan olması nedeniyle aracın kaydığını, bu sebeple 67/1-d kapsamında verilen idari para cezası, sürücü belgesi geri alma ve araç men işlemlerine itiraz ettiğini ileri sürmüştür. Uyuşmazlık Mahkemesi, uyuşmazlığın idari yargıda görülmesi gerektiğine karar vermiştir.',
  },
  {
    court: 'Yargıtay 12. Ceza Dairesi',
    esas: '2013/3373',
    karar: '2013/22484',
    date: '03.10.2013',
    tier: 3,
    why: 'Karlı-buzlu zeminde patinaj/kayma sonucu oluşan sonuçları tartışarak istem dışı kayma argümanına arka plan sağlar.',
    summary:
      'Sanık, minibüsüyle karlı ve buzlu zeminde hareket etmek isterken patinaj yapmış; araç kayarak yayaya çarpmıştır. Karar, kaygan zemin ve araç hakimiyeti değerlendirmesini taksir sorumluluğu bağlamında tartışır.',
  },
];

function resultCitation(result) {
  return [result?.esas ? `${result.esas} E.` : '', result?.karar ? `${result.karar} K.` : ''].filter(Boolean).join(' - ');
}

function summaryParagraphs(result) {
  return String(result?.summary || '')
    .split(/\n+/)
    .map((line) => line.replace(/\*\*/g, '').trim())
    .filter(Boolean);
}

export const InteractiveChatDemo = () => {
  const [activeScreen, setActiveScreen] = useState('chat');
  // ── Chat state ──
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [copiedMsgId, setCopiedMsgId] = useState(null);
  const [selectedChatId, setSelectedChatId] = useState(null);
  const [chatsOpen, setChatsOpen] = useState(true);
  const chatEndRef = useRef(null);
  const textareaRef = useRef(null);
  // ── İçtihat state ──
  const [ictihatQuery, setIctihatQuery] = useState('Drift idari para cezasında kamera görüntüsü yoksa 2918 m.67/1-d yaptırımı iptal edilir mi?');
  const [ictihatSearchMode, setIctihatSearchMode] = useState('ai');
  const [selectedResult, setSelectedResult] = useState(0);
  const [mobileDocOpen, setMobileDocOpen] = useState(false);
  const ictihatQueryRef = useRef(null);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, isTyping]);
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
  }, [inputValue]);
  useEffect(() => {
    const ta = ictihatQueryRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
  }, [ictihatQuery, activeScreen]);

  const handleSendMessage = (text) => {
    const msg = text || inputValue.trim();
    if (!msg || isTyping) return;
    setMessages(prev => [...prev, { id: Date.now(), role: 'user', content: msg }]);
    setInputValue('');
    setIsTyping(true);
    if (!selectedChatId) setSelectedChatId('demo');
    setTimeout(() => {
      setMessages(prev => [...prev, { id: Date.now() + 1, role: 'assistant', content: DEMO_AI_RESPONSE }]);
      setIsTyping(false);
    }, 2000);
  };

  const handleKeyDown = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendMessage(); } };
  const handleSuggestionClick = (s) => { setInputValue(s.prompt); setTimeout(() => textareaRef.current?.focus(), 50); };
  const handleCopy = (msg) => { try { navigator.clipboard.writeText(msg.content); } catch { /* */ } setCopiedMsgId(msg.id); setTimeout(() => setCopiedMsgId(p => p === msg.id ? null : p), 2000); };
  const showEmptyState = messages.length === 0;

  const handleResultClick = (i) => {
    setSelectedResult(i);
    setMobileDocOpen(true);
  };

  const selectedIctihatResult = ICTIHAT_RESULTS[selectedResult] || ICTIHAT_RESULTS[0];

  // Document viewer content (shared between desktop and mobile)
  const docViewerContent = (
    <div className="demo-ictihat-doc">
      <div className="demo-ictihat-doc-head">
        <div className="demo-ictihat-doc-head-main">
          {/* Mobile back button */}
          <button className="demo-ictihat-doc-mobile-back" type="button" onClick={() => setMobileDocOpen(false)}>
            <ChevronLeft size={16} /><span>Geri</span>
          </button>
          <div className="demo-ictihat-doc-meta">
            <div className="demo-ictihat-doc-compact-meta">
              <div className="demo-ictihat-doc-compact-line">
                <span className="demo-ictihat-doc-title-inline">Karar metni</span>
                <span className="demo-ictihat-doc-inline-sep">-</span>
                <span className="demo-ictihat-doc-inline-court">{selectedIctihatResult?.court}</span>
              </div>
              <div className="demo-ictihat-doc-compact-line is-secondary">
                <span className="demo-ictihat-doc-inline-kunye">{resultCitation(selectedIctihatResult)} - {selectedIctihatResult?.date}</span>
              </div>
            </div>
          </div>
          <div className="demo-ictihat-doc-actions">
            <button className="demo-ictihat-copy-btn" type="button"><span className="demo-ictihat-copy-glyph" />Kopyala</button>
            <button className="demo-ictihat-doc-control-btn" type="button">Tam ekran</button>
          </div>
        </div>
        <div className="demo-ictihat-doc-searchbar">
          <div className="demo-ictihat-doc-search-input-wrap">
            <span className="demo-ictihat-doc-search-icon" />
            <input className="demo-ictihat-doc-search-input" placeholder="Karar metni içinde ara" />
          </div>
          <div className="demo-ictihat-doc-search-status">0/0</div>
          <div className="demo-ictihat-doc-search-actions">
            <button className="demo-ictihat-doc-search-btn" type="button">↑</button>
            <button className="demo-ictihat-doc-search-btn" type="button">↓</button>
          </div>
        </div>
      </div>
      <div className="demo-ictihat-doc-text">
        <div className="demo-ictihat-doc-section">MAHKEME / DAİRE: {selectedIctihatResult?.court}</div>
        <div className="demo-ictihat-doc-pair"><span className="demo-ictihat-doc-pair-label">ESAS / KARAR:</span><span className="demo-ictihat-doc-pair-value">{resultCitation(selectedIctihatResult)}</span></div>
        <div className="demo-ictihat-doc-pair"><span className="demo-ictihat-doc-pair-label">TARİH:</span><span className="demo-ictihat-doc-pair-value">{selectedIctihatResult?.date}</span></div>
        <div className="demo-ictihat-doc-pair"><span className="demo-ictihat-doc-pair-label">AI SKOR:</span><span className="demo-ictihat-doc-pair-value">Tier {selectedIctihatResult?.tier} - AI Arama sonucu</span></div>
        <div className="demo-ictihat-doc-gap" />
        <div className="demo-ictihat-doc-section-line">AI DEĞERLENDİRMESİ</div>
        <div className="demo-ictihat-doc-line is-lead">{selectedIctihatResult?.why}</div>
        <div className="demo-ictihat-doc-gap" />
        <div className="demo-ictihat-doc-section-line">KARAR ÖZETİ</div>
        {summaryParagraphs(selectedIctihatResult).map((paragraph, index) => (
          <div key={index} className="demo-ictihat-doc-line">
            {paragraph.includes("67/1-d") ? (
              <>
                {paragraph.split("67/1-d")[0]}
                <mark className="demo-ictihat-doc-search-hit">67/1-d</mark>
                {paragraph.split("67/1-d").slice(1).join("67/1-d")}
              </>
            ) : paragraph}
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <section className="demo-section" id="demo-section">
      {/* ── Screen Toggle ── */}
      <div className="demo-screen-tabs">
        <button className={`demo-screen-tab ${activeScreen === 'chat' ? 'demo-screen-tab--active' : ''}`} onClick={() => setActiveScreen('chat')}>
          <MessageSquare size={16} /><span>AI Hukuk Asistanı</span>
        </button>
        <button className={`demo-screen-tab ${activeScreen === 'ictihat' ? 'demo-screen-tab--active' : ''}`} onClick={() => { setActiveScreen('ictihat'); setMobileDocOpen(false); }}>
          <Search size={16} /><span>İçtihat Arama</span>
        </button>
      </div>

      {/* ── Safari Browser Chrome (LIGHT) ── */}
      <div className="demo-browser">
        <div className="demo-browser-chrome">
          <div className="demo-browser-dots"><span className="demo-dot demo-dot--red" /><span className="demo-dot demo-dot--yellow" /><span className="demo-dot demo-dot--green" /></div>
          <div className="demo-browser-bar">
            <div className="demo-browser-url">
              <span className="demo-browser-url-alias">AA</span>
              <div className="demo-browser-url-main">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                <span>{activeScreen === 'chat' ? 'app.yargucu.com/chat' : 'app.yargucu.com/ictihat'}</span>
              </div>
              <RotateCcw size={12} className="demo-browser-url-refresh" />
            </div>
          </div>
          <div className="demo-browser-actions" />
        </div>

        {/* ── App viewport ── */}
        <div className="demo-app">
          {activeScreen === 'chat' ? (
            /* ════ CHAT SCREEN ════ */
            <>
              {/* SIDEBAR */}
              <aside className={`demo-sidebar ${sidebarCollapsed ? 'demo-sidebar--collapsed' : ''}`}>
                <div className="demo-sidebar-header">
                  <div className="demo-sidebar-brand">
                    <div className="demo-sidebar-logo"><img src={yargucuLogoBlack} alt="Logo" className="demo-sidebar-logo-img" /></div>
                    <div className="demo-sidebar-brand-copy">
                      <div className="demo-sidebar-brand-title-row"><span className="demo-sidebar-brand-title">Yargucu</span><span className="demo-sidebar-badge">Beta</span></div>
                      <span className="demo-sidebar-brand-kicker">AI Hukuk Asistanı</span>
                    </div>
                  </div>
                  <button onClick={() => setSidebarCollapsed(true)} className="demo-sidebar-collapse-btn"><PanelLeftClose size={16} /></button>
                </div>
                <div className="demo-sidebar-content">
                  <div className="demo-sidebar-section">
                    <button className="demo-sidebar-section-btn" onClick={() => setChatsOpen(!chatsOpen)}>
                      <MessageSquare size={16} /><span>Sohbetler</span><span className="demo-sidebar-section-count">{DEMO_CHATS.length}</span>
                      <ChevronRight size={16} className={`demo-sidebar-chevron ${chatsOpen ? 'demo-sidebar-chevron--open' : ''}`} />
                    </button>
                    {chatsOpen && (
                      <div className="demo-sidebar-sub">
                        <button className="demo-sidebar-new-chat"><Plus size={16} /><span>Yeni sohbet</span></button>
                        {DEMO_CHATS.map(c => (
                          <div key={c.id} className="demo-sidebar-chat-item">
                            <button className={`demo-sidebar-chat-link ${selectedChatId === c.id ? 'demo-sidebar-chat-link--active' : ''}`}><span className="demo-sidebar-chat-label">{c.label}</span></button>
                            <button className="demo-sidebar-chat-delete" title="Sil"><Trash2 size={14} /></button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="demo-sidebar-section"><button className="demo-sidebar-section-btn"><FileText size={16} /><span>Belgeler</span><span className="demo-sidebar-section-count">0</span><ChevronRight size={16} className="demo-sidebar-chevron" /></button></div>
                  <div className="demo-sidebar-section"><button className="demo-sidebar-section-btn"><Scale size={16} /><span>Dökümanlar</span><span className="demo-sidebar-section-count">0</span><ChevronRight size={16} className="demo-sidebar-chevron" /></button></div>
                  <div className="demo-sidebar-section"><button className="demo-sidebar-section-btn"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg><span>Dilekçeler</span><span className="demo-sidebar-section-count">1</span><ChevronRight size={16} className="demo-sidebar-chevron" /></button></div>
                </div>
                <div className="demo-sidebar-footer">
                  <div className="demo-sidebar-ictihat-link" onClick={() => setActiveScreen('ictihat')}>
                    <span className="demo-sidebar-ictihat-icon"><Search size={16} /></span>
                    <span className="demo-sidebar-ictihat-copy"><span className="demo-sidebar-ictihat-title">İçtihat Ara</span><span className="demo-sidebar-ictihat-subtitle">Emsal kararları hızlıca tara</span></span>
                    <ArrowUpRight size={16} className="demo-sidebar-ictihat-arrow" />
                  </div>
                  <div className="demo-sidebar-user">
                    <div className="demo-sidebar-user-avatar">MK</div>
                    <div className="demo-sidebar-user-info"><span className="demo-sidebar-user-name">Metehan Kılınç</span><span className="demo-sidebar-user-credit">Kredi: 45,40</span></div>
                    <ChevronsUpDown size={16} className="demo-sidebar-user-chevron" />
                  </div>
                </div>
              </aside>

              {/* MAIN CHAT */}
              <main className="demo-main">
                {sidebarCollapsed && (<div className="demo-site-header"><button onClick={() => setSidebarCollapsed(false)} className="demo-site-header-toggle"><PanelLeftClose size={16} style={{ transform: 'scaleX(-1)' }} /></button></div>)}
                <div className="demo-chat-scroll">
                  <div className="demo-chat-stream">
                    {showEmptyState ? (
                      <div className="demo-empty-state">
                        <div className="demo-empty-brand">
                          <div className="demo-empty-logo-shell"><img className="demo-empty-logo" src={yargucuLogoBlack} alt="Yargucu" /></div>
                          <div className="demo-empty-brand-copy"><div className="demo-empty-kicker">AI HUKUK ASİSTANI</div><div className="demo-empty-brand-name">YARGUCU</div><p className="demo-empty-subtitle">Dilekçe taslağı, emsal karar taraması ve hukuki analiz için tek akışta başlayın.</p></div>
                        </div>
                        <div className="demo-empty-suggestions">
                          {EMPTY_CHAT_SUGGESTIONS.map((s) => (<button key={s.title} type="button" className="demo-empty-suggestion" onClick={() => handleSuggestionClick(s)}><span className="demo-empty-suggestion-label">{s.label}</span><span className="demo-empty-suggestion-title">{s.title}</span><span className="demo-empty-suggestion-description">{s.description}</span></button>))}
                        </div>
                      </div>
                    ) : (
                      <>
                        {messages.map((msg, index) => {
                          const isA = msg.role === 'assistant';
                          const isLast = index === messages.length - 1;
                          return (
                            <div key={msg.id} className={`demo-message ${isA ? 'demo-message--assistant' : 'demo-message--user'}`}>
                              {isA ? (
                                <div className="demo-msg-assistant-wrap group">
                                  <div className="demo-msg-assistant-content">{msg.content.split('\n').map((line, i) => { if (line.startsWith('> ')) return <blockquote key={i} className="demo-msg-blockquote">{line.slice(2)}</blockquote>; if (line.trim() === '') return <br key={i} />; const parts = line.split(/(\*\*.*?\*\*)/g); return <p key={i}>{parts.map((p, j) => p.startsWith('**') && p.endsWith('**') ? <strong key={j}>{p.slice(2, -2)}</strong> : <span key={j}>{p}</span>)}</p>; })}</div>
                                  <div className={`demo-msg-actions ${isLast ? 'demo-msg-actions--visible' : ''}`}><button type="button" className="demo-msg-action-btn" onClick={() => handleCopy(msg)}>{copiedMsgId === msg.id ? <Check size={15} /> : <Copy size={15} />}</button></div>
                                </div>
                              ) : (<div className="demo-msg-user-wrap"><div className="demo-msg-user-content">{msg.content}</div></div>)}
                            </div>
                          );
                        })}
                        {isTyping && (<div className="demo-message demo-message--assistant"><div className="demo-msg-assistant-wrap"><div className="demo-typing-dots"><div className="demo-typing-dot" /><div className="demo-typing-dot" style={{ animationDelay: '250ms' }} /><div className="demo-typing-dot" style={{ animationDelay: '500ms' }} /></div></div></div>)}
                      </>
                    )}
                    <div ref={chatEndRef} />
                  </div>
                </div>
                <div className="demo-composer">
                  <div className="demo-composer-inner">
                    <textarea ref={textareaRef} value={inputValue} onChange={(e) => setInputValue(e.target.value)} onKeyDown={handleKeyDown} placeholder="Uyuşmazlığı, belge ihtiyacınızı veya aradığınız içtihadı yazın" className="demo-composer-textarea" rows={1} />
                    <div className="demo-composer-actions">
                      <div className="demo-composer-actions-left"><button className="demo-composer-attach-btn" type="button"><Paperclip size={16} /></button></div>
                      <div className="demo-composer-actions-right"><button className={`demo-composer-send-btn ${inputValue.trim() ? '' : 'demo-composer-send-btn--disabled'}`} onClick={() => handleSendMessage()} disabled={!inputValue.trim() || isTyping} type="button"><ArrowUp size={18} strokeWidth={2.5} /></button></div>
                    </div>
                  </div>
                  <div className="demo-composer-disclaimer">© 2026 Yargucu · Hukuki danışmanlık hizmeti değildir.</div>
                </div>
              </main>

              {/* PETITION PANEL */}
              <aside className="demo-petition-panel">
                <div className="demo-petition-header">
                  <div className="demo-petition-header-copy">
                    <h3 className="demo-petition-title">Dilekçe Önizleme</h3>
                    <span className="demo-petition-subtitle">Destekten Yoksun Kalma Tazminatı Dava Dilekçesi</span>
                  </div>
                  <div className="demo-petition-header-actions">
                    <button className="demo-petition-action-btn"><Download size={14} /> İndir</button>
                    <button className="demo-petition-action-btn"><RotateCcw size={14} /> Yenile</button>
                  </div>
                </div>
                <div className="demo-petition-body p-3">
                  <SamplePetitionDocument compact className="h-full min-h-0 w-full" />
                </div>
              </aside>
            </>
          ) : (
            /* ════ İÇTİHAT ARAMA SCREEN ════ */
            <div className={`demo-ictihat-page${mobileDocOpen ? ' is-doc-open' : ''}`}>
              {/* Show header + filters + results when doc is NOT open on mobile */}
              {!mobileDocOpen ? (
                <>
                  {/* ── Header ── */}
                  <div className="demo-ictihat-header">
                    <div className="demo-ictihat-header-row">
                      <div className="demo-ictihat-brand-stack">
                        <button className="demo-ictihat-brand-home" onClick={() => setActiveScreen('chat')}>
                          <span className="demo-ictihat-brand-chevron"><svg viewBox="0 0 24 24" width="18" height="18"><path d="M15 6l-6 6 6 6" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.9"/></svg></span>
                          <img className="demo-ictihat-brand-logo" src={yargucuLogoBlack} alt="Yargucu" />
                        </button>
                      </div>
                      <div className="demo-ictihat-heading">
                        <div className="demo-ictihat-title-wrap">
                          <div className="demo-ictihat-title">İçtihat Arama</div>
                          <span className="demo-ictihat-title-separator">-</span>
                          <p className="demo-ictihat-subtitle">Yapay zeka destekli içtihat araması</p>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* ── Filters ── */}
                  <div className="demo-ictihat-filters">
                    <div className="demo-ictihat-filter-main">
                      <div className="demo-ictihat-mode-toggle">
                        {[
                          { key: 'ai', label: 'AI Arama' },
                          { key: 'semantic', label: 'Anlamsal' },
                          { key: 'keyword', label: 'Kelime Bazlı' },
                        ].map(m => (
                          <button key={m.key} className={`demo-ictihat-mode-option${ictihatSearchMode === m.key ? ' is-active' : ''}${m.key === 'ai' ? ' is-ai' : ''}${m.key === 'keyword' ? ' is-keyword' : ''}`} onClick={() => setIctihatSearchMode(m.key)}>{m.label}</button>
                        ))}
                      </div>
                      <div className="demo-ictihat-query-wrap">
                        <textarea ref={ictihatQueryRef} className="demo-ictihat-query-input" value={ictihatQuery} onChange={(e) => setIctihatQuery(e.target.value)} placeholder="Nasıl bir emsal karar istediğinizi anlatınız..." rows={1} />
                        <button className="demo-ictihat-query-info-btn" type="button">i</button>
                      </div>
                      <div className="demo-ictihat-select-placeholder"><span>Mahkeme / Daire (opsiyonel)</span><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"/></svg></div>
                      <button className="demo-ictihat-search-btn" disabled={!ictihatQuery.trim()}><span className="demo-ictihat-search-glyph" />Ara</button>
                    </div>
                    <div className="demo-ictihat-filter-secondary">
                      <button className="demo-ictihat-header-link">Geçmiş</button>
                      <div className="demo-ictihat-filter-actions-right"><button className="demo-ictihat-header-link">Gelişmiş filtreler</button><button className="demo-ictihat-header-link">Temizle</button></div>
                    </div>
                  </div>

                  {/* ── Results Overview ── */}
                  <div className="demo-ictihat-results-overview">
                    <span className="demo-ictihat-results-count"><strong>{ICTIHAT_RESULTS.length}</strong> sonuç bulundu</span>
                  </div>

                  {/* ── Results list (mobile-only full screen) ── */}
                  <div className="demo-ictihat-body demo-ictihat-body--mobile-list">
                    <div className="demo-ictihat-results">
                      {ICTIHAT_RESULTS.map((r, i) => (
                        <button key={i} className={`demo-ictihat-card${selectedResult === i ? ' is-active' : ''}`} onClick={() => handleResultClick(i)}>
                          <div className="demo-ictihat-card-court">{r.court}</div>
                          <div className="demo-ictihat-citation">{r.date}</div>
                          <div className="demo-ictihat-snippet">{r.why}</div>
                          <div className="demo-ictihat-card-footer">
                            <div className="demo-ictihat-chip-row"><span className="demo-ictihat-chip">E: {r.esas}</span><span className="demo-ictihat-chip">K: {r.karar}</span></div>
                            <button className="demo-ictihat-select-toggle" type="button" onClick={(e) => e.stopPropagation()}><span className="demo-ictihat-select-box" /><span className="demo-ictihat-select-label">Seç</span></button>
                          </div>
                        </button>
                      ))}
                    </div>

                    {/* Desktop viewer (hidden on mobile) */}
                    <div className="demo-ictihat-viewer demo-ictihat-viewer--desktop">
                      {docViewerContent}
                    </div>
                  </div>
                </>
              ) : (
                /* Mobile: Document viewer full screen */
                <div className="demo-ictihat-viewer demo-ictihat-viewer--mobile-full">
                  {docViewerContent}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
};
