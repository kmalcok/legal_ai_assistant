# Reasoning Mimari Dokümanı

Bu döküman, Yargucu'daki reasoning (düşünme efor seviyesi) ve verbosity (yanıt detay seviyesi) ayarlarının **nasıl kurgulandığını**, **hangi agent'ı etkilediğini**, **kullanıcının neyi kontrol edebildiğini** ve **kontrol edemediğini** anlatır.

---

## 1. Kısa Özet

| Agent / İşlem | Model (varsayılan) | Reasoning Nereden? | Kullanıcı Etkisi |
|---|---|---|---|
| **Main Law Agent** (sohbet) | `gpt-5.4` (base_model) | User config + per-request override | ✅ Tam kontrol |
| **Ictihat Internal Search Agent** (law agent'ın `ictihat_search` tool'u) | `gpt-5-mini` | User config (`ictihat_agent_reasoning_effort`) → fallback `ai_config.json` → `ictihat_search_agent_default_reasoning_effort` (varsayılan `"medium"`) | ✅ Kontrol |
| **Ictihat API Search Agent** (UI → `/ictihat/agent_search`) | `gpt-5-mini` | Aynı user config → fallback `ictihat_api_search_agent_default_reasoning_effort` | ✅ Kontrol |
| **Ictihat Summarizer** (uzun karar metnini kısaltan) | `gpt-5-nano` | `ai_config.json` → `ictihat_summarizer_reasoning_effort` | ❌ Sabit (dev/prod json) |
| **Memory Summarizer** (chat geçmişi) | `gpt-5-nano` | Yok (reasoning param verilmez) | ❌ N/A |

Verbosity (yanıt uzunluğu):

| Agent | Kaynak | Kullanıcı Etkisi |
|---|---|---|
| Main Law Agent | `main_agent_verbosity` user config | ✅ `low` / `medium` / `high` |
| Ictihat agent'lar | Ayarlanmaz | ❌ |
| Summarizer | Ayarlanmaz | ❌ |

---

## 2. Mimari ve Akış

### 2.1 Tek Giriş Noktası: `build_model_settings`

Tüm agent'lar `openai-agents` SDK üzerinden çalışır ve OpenAI Responses API'sine giden `reasoning`/`verbosity` parametrelerini tek bir fonksiyondan türetir:

`backend/src/services/user_app_config_service.py` → `build_model_settings(model, reasoning_effort, verbosity, reasoning_summary)`

Bu fonksiyon:
1. `sanitize_verbosity(model, verbosity)` → modelin desteklediği verbosity ise kullan, değilse `None`.
2. `sanitize_reasoning_effort(model, reasoning_effort)` → modelin desteklediği reasoning_effort ise kullan, değilse `None`.
3. Effort boşsa `ModelSettings(verbosity=...)` döner (reasoning parametresi yok).
4. Effort SDK'nın tanıdığı bir değerse (`none|minimal|low|medium|high`) → `ModelSettings(reasoning=Reasoning(effort=..., summary=...), verbosity=...)`.
5. Effort `xhigh` ise SDK henüz type'lamadığı için `extra_args={"reasoning": {"effort": "xhigh", ...}}` şeklinde geçer.

**`reasoning_summary` parametresi** (aynı fonksiyonda sabitlenir):
- Main law agent → `"auto"`
- Ictihat search agent'ları → `"concise"` (hızlı ve az token)

### 2.2 Model Aileleri ve Desteklenen Değerler

`allowed_reasoning_efforts(model)` modele göre kümeyi sınırlar:

| Model ailesi | Desteklenen reasoning_effort |
|---|---|
| `gpt-5.4` | `none`, `low`, `medium`, `high`, `xhigh` |
| `gpt-5.2` | `none`, `low`, `medium`, `high`, `xhigh` |
| `gpt-5` | `none`, `minimal`, `low`, `medium`, `high` |
| `gpt-5-mini` | `minimal`, `low`, `medium`, `high` |
| `gpt-5-nano` | `minimal`, `low`, `medium`, `high` |

Bu yüzden örneğin kullanıcı `xhigh` seçse bile ictihat agent'ı `gpt-5-mini`'de çalıştığı için sanitize sonucunda `None` dönüp `"low"` fallback'ine düşer.

`supports_verbosity(model)` → tüm `gpt-5*` ailesi `low|medium|high` verbosity destekler.

---

## 3. Main Law Agent (Sohbet Asistanı)

**Dosya:** `backend/src/ai/agent/law_agent.py` → `LawAssistantAgent`

### 3.1 Model

`agent_config().base_model` — varsayılan `gpt-5.4`.
Kullanıcı modeli değiştiremez (tek model). Reasoning ailesi bu modele bağlı olarak seçilir.

### 3.2 Reasoning Çözümleme Sırası

`UserAppConfigService.resolve_main_agent_config(user_id, request_reasoning_effort, ...)`

1. **Per-request override:** `request_reasoning_effort` geldiyse (ör. `/chat/send` payload'unda `reasoning: "high"`) ve modele uyumluysa → bunu kullan.
2. **User config:** DB'de `user_app_config.main_agent_reasoning_effort` varsa → bunu kullan.
3. **Yoksa `None`** (model varsayılanıyla çalışır; Responses API kendi default'unu uygular).

**Not:** Per-request override DB'ye yazılmaz. Sadece o turn için geçerlidir. Kullanıcı Settings'te değiştirdiği sürece her turda aynı kalır.

### 3.3 Verbosity

1. User config `main_agent_verbosity` varsa (default kurulumda `"medium"`) → kullan.
2. Yoksa `"medium"` fallback.

### 3.4 API Akışı

`POST /chat/send` → `AgentService.stream_turn` → `resolve_main_agent_config` → `LawAssistantAgent(model, reasoning_pref=..., verbosity=...)` → `Runner.run`.

`routes_chat.py`:
```python
reasoning_pref=payload.reasoning   # per-request override
```

Frontend chat view'da şu anda per-request reasoning gönderilmiyor (sadece user config DB'den okunuyor); ancak API sözleşmesi açık — ileride UI'a "bu mesaj için Derin Analiz" butonu eklemek mümkün.

---

## 4. İçtihat Arama Agent'ları (İki Adet)

Aynı prompt family ama iki farklı yerden tetikleniyor. **Model her ikisinde de `gpt-5-mini`** (ai_config.json).

### 4.1 Internal: `IctihatSearchAgent`

**Dosya:** `backend/src/ai/agent/ictihat_search_agent.py`
**Tetikleyici:** Law agent içinden `ictihat_search(intent_text)` tool'u çağrıldığında.
**Wrapper:** `backend/src/ai/tool_wrappers/ictihat_semantic_agent.py` → `ictihat_semantic_search(...)`.

Reasoning çözümleme:
```python
resolved_effort = UserAppConfigService().resolve_ictihat_reasoning_effort(
    user_id=...,
    model="gpt-5-mini",
    default_effort=cfg.ictihat_search_agent_default_reasoning_effort,   # ai_config.json'dan
)
```

API agent'ında fallback `cfg.ictihat_api_search_agent_default_reasoning_effort`.

`resolve_ictihat_reasoning_effort`:
1. User config `ictihat_agent_reasoning_effort` varsa & modele uyumluysa → kullan.
2. Yoksa `default_effort` (config'ten gelen system default).
3. O da sanitize olmazsa hard fallback `"medium"`.

**İki ayrı config anahtarı** var, böylece internal (law agent → ictihat_search) ve API (UI) agent'ları ayrı reasoning default'u alabilir:
- `ictihat_search_agent_default_reasoning_effort` (internal)
- `ictihat_api_search_agent_default_reasoning_effort` (UI)

Env bazında (`config-dev` / `config-prod`) override edilebilir.

### 4.2 API: `IctihatApiSearchAgent`

**Dosya:** `backend/src/ai/agent/ictihat_api_search_agent.py`
**Tetikleyici:** UI'daki "AI İçtihat Ara" akışı → `POST /ictihat/agent_search` → `ictihat_api_semantic_search(...)`.

Reasoning çözümleme **aynıdır** (`resolve_ictihat_reasoning_effort`, default `"low"`).

### 4.3 Paylaşılan Tek User Config Alanı

**Kritik:** Her iki agent için **aynı** user config alanı kullanılır:

```
user_app_config.ictihat_agent_reasoning_effort
```

Yani kullanıcı Settings'ten "İçtihat Tarama Derinliği" değerini yükseltince **hem sohbetteki otomatik ictihat araması hem de UI'dan elle yapılan AI araması** birlikte yükselir.

### 4.4 Model Ailesi Sınırı

`gpt-5-mini` için `allowed_reasoning_efforts = {minimal, low, medium, high}`.

Kullanıcı UI'da `xhigh` seçerse `update_user_config` aşamasında `sanitize_reasoning_effort("gpt-5-mini", "xhigh")` `None` dönüp `ValueError("invalid_ictihat_agent_reasoning_effort")` atar (HTTP 400). Pratikte UI bu yüzden `none|low|medium|high` seçeneklerini göstermeli (aşağıya bkz. "6. Bilinen Uyuşmazlıklar").

---

## 5. Kullanıcının Konfigüre Edebildikleri

### 5.1 Settings Sayfası (`/settings` → AI sekmesi)

Kullanıcıya 4 alan gösterilir (`frontend/src/features/settings/pages/SettingsPage.jsx`):

| UI Alanı | Config Key | Değerler | Varsayılan | Etki |
|---|---|---|---|---|
| **Yanıt Detay Seviyesi** | `main_agent_verbosity` | `low` / `medium` / `high` | `medium` | Main agent'ın cevaplarının uzunluğu / detay miktarı. |
| **Düşünme Seviyesi (Reasoning)** | `main_agent_reasoning_effort` | `""` (sistem) / `none` / `low` / `medium` / `high` / `xhigh` | `None` | Main agent'ın reasoning effort'u. `xhigh` şu an sadece `gpt-5.4`/`gpt-5.2`'de geçerli (zaten base_model). |
| **İçtihat Tarama Derinliği** | `ictihat_agent_reasoning_effort` | `""` / `none` / `low` / `medium` / `high` / `xhigh` | `None` → fallback `low` | Her iki içtihat agent'ını etkiler. |
| **Kalıcı Yönergeler** | `extra_instructions` | Serbest metin, max 4000 char | boş | User-level prompt ek yönergesi. |

### 5.2 API Endpoint'leri

- `GET /user/app-config` → aktif konfigi döner.
- `PATCH /user/app-config` → kısmi güncelleme. Her alan bağımsız gönderilebilir. Model ailesiyle uyumsuz bir değer (ör. `gpt-5-mini` için `xhigh`) HTTP 400 ile reddedilir.
- `null` göndermek → "sistem varsayılanına dön" anlamına gelir.

### 5.3 Per-request Override (Sadece Main Agent)

`POST /chat/send`, `POST /chat/message` payload'unda `reasoning` alanı:

- Varsa → o turn için main agent'ın reasoning'ini **tek seferlik** değiştirir.
- DB'ye yazılmaz.
- İçtihat agent'larını etkilemez.
- Frontend şu an bu alanı **kullanmıyor**; arka kapı olarak açık.

---

## 6. Kullanıcının Konfigüre Edemedikleri (Sabitler)

### 6.1 Modeller

`base_model`, `ictihat_search_agent_model`, `ictihat_api_search_agent_model`, `ictihat_summarizer_model`, `memory_summarizer_model` hepsi `ai_config.json` dosyalarından gelir (`backend/config/config-dev/ai_config.json`, `config-prod/ai_config.json`). User bu modellerin hiçbirini değiştiremez.

### 6.2 Ictihat Summarizer Reasoning

`ictihat_summarizer_reasoning_effort` → `ai_config.json` → prod'da genelde `"minimal"`, dev'de `"none"`. Bu, uzun içtihat metinlerini kısaltan nano model için geçerlidir ve **user config ile override edilemez**. Saf token tasarruf amaçlı; yüksek reasoning açmanın buraya pratik faydası yok.

### 6.3 Memory Summarizer

Chat geçmişi özetleyicisine reasoning parametresi **hiç verilmez** — openai client çağrısı düz yapılır. Model `gpt-5-nano` varsayılan ile çalışır.

### 6.4 `max_turns` ve `top_k`

Agent bütçesiyle ilgili parametreler de `ai_config.json`'da sabittir:
- `ictihat_search_agent_max_turns` (default 50)
- `ictihat_api_search_agent_max_turns` (default 50)
- `*_top_k` (her `ictihat_db_search` çağrısının limit'i)

User bunlara dokunamaz.

### 6.5 `reasoning_summary`

Main agent'ta `"auto"`, ictihat agent'larında `"concise"`. Kod içi sabit, config dışı.

---

## 7. Default Davranış (Yeni Kullanıcı İçin)

Yeni bir kullanıcı hiçbir ayar yapmadığında:

```
main_agent_verbosity            = "medium"
main_agent_reasoning_effort     = None  → model default (Responses API kendi seçer)
ictihat_agent_reasoning_effort  = None  → kodda "medium" fallback
extra_instructions              = None
```

Ictihat summarizer: `"minimal"` (prod) / `"none"` (dev).

---

## 8. Kredi ve Maliyet Etkisi

- Daha yüksek `reasoning_effort` = daha çok **reasoning tokens** = daha çok kredi. Usage kayıtları `reasoning_tokens` usage_type ile ayrı tutulur (`UsageService.record_token_usage`).
- `verbosity` doğrudan kredi değil, output_tokens'ı etkiler (daha uzun cevap = daha çok output_tokens).
- Settings UI'daki uyarı: "Yüksek seviyeler daha fazla kredi tüketebilir ve yanıt süresini uzatabilir."

---

## 9. Bilinen Uyuşmazlıklar / Dikkat Noktaları

1. **UI `xhigh` opsiyonu içtihat reasoning için:** `gpt-5-mini` `xhigh`'ı desteklemiyor. Bu opsiyon UI'da listeli ama backend patch'te 400 dönecek. İdeal olarak UI model ailesine göre filtrelemeli veya tek liste kullanıp backend "unsupported_value" mesajıyla reddetmeli (şu an generic `invalid_ictihat_agent_reasoning_effort` gidiyor).

2. **Per-request reasoning UI'da yok:** `/chat/send` payload'u destekliyor ama frontend bunu göndermiyor. İleride "şu mesaj için derin analiz" butonu eklenebilir.

3. **`main_agent_reasoning_effort=None` anlamı:** "Sistem varsayılanı" = reasoning parametresi hiç gönderilmez. Bu, Responses API'nin modelin kendi default'unu kullanması demektir; "kapalı" ile karıştırılmamalı. "Kapalı" istemek için açıkça `none` seçilmeli.

4. **`gpt-5-mini` + `xhigh` durumu:** Kod `build_model_settings` içinde `xhigh`'ı `extra_args` ile geçirecek bir fallback'e sahip, ama öncesinde `sanitize_reasoning_effort` süzgecinde `gpt-5-mini` için `xhigh` olmadığı için `None` dönecek → pratikte `xhigh` asla `gpt-5-mini`'ye ulaşmaz.

5. **Ictihat summarizer sabit:** Kullanıcı "İçtihat Tarama Derinliği"ni `high` yaparsa bu sadece arama **agent'ını** etkiler; summarizer yine `"minimal"`/`"none"` ile çalışır. Uzun kararların sıkıştırma kalitesi user-config ile değişmez.

---

## 10. İlgili Dosyalar (Hızlı Erişim)

- `backend/src/services/user_app_config_service.py` — tüm reasoning/verbosity sanitizer ve `build_model_settings`.
- `backend/src/data/db_user_app_config_repository.py` — DB şeması + varsayılanlar.
- `backend/src/api/routes/routes_user_config.py` — `GET`/`PATCH /user/app-config`.
- `backend/src/ai/agent/law_agent.py` — main agent inşası.
- `backend/src/ai/agent/ictihat_search_agent.py` — internal ictihat agent.
- `backend/src/ai/agent/ictihat_api_search_agent.py` — UI ictihat agent.
- `backend/src/ai/tool_wrappers/ictihat_semantic_agent.py` — internal wrapper.
- `backend/src/ai/tool_wrappers/ictihat_api_semantic_agent.py` — API wrapper.
- `backend/src/ai/util/ictihat_agent_summarizer.py` — summarizer (user config'e tabi değil).
- `backend/config/config-{dev,prod}/ai_config.json` — model/model-bütçe sabitleri.
- `frontend/src/features/settings/pages/SettingsPage.jsx` — UI formu.
