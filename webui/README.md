# MITAS Web UI

MITAS (Medya Yapay Zeka Tabanlı Analiz Sistemi) operatör arayüzü. ASR / OCR / Yüz / Etiket çıktılarının zaman çizelgesi üzerinde gözden geçirildiği, kanıt zincirinin denetlendiği panel.

> Bu sürüm v0.2 prototipidir — ASR modülü gerçek yerel backend'e bağlıdır, diğer modüller "Yapım Aşamasında" placeholder ile gösterilir.

## Çalıştırma

```bash
cd webui
pnpm install
pnpm dev          # http://localhost:5173
pnpm build        # production bundle
pnpm preview      # bundle'ı önizle
pnpm type-check   # tsc --noEmit
```

> npm değil **pnpm** kullanılıyor — `package.json` içinde pnpm override'ları var.

## Gerçek ASR backend

WebUI, Vite proxy üzerinden `http://127.0.0.1:8787` adresindeki ASR-only FastAPI servisine bağlanır.

Backend başlatma:

```powershell
cd E:\MITAS
.\venvs\asr\Scripts\python.exe -m uvicorn core.api.asr_server:app --host 127.0.0.1 --port 8787
```

WebUI'de `Yükle` butonu ses/video dosyasını raw body olarak `POST /api/asr/transcribe` endpoint'ine yollar. Backend yalnızca ASR çalıştırır:

- `faster-whisper` modeli: `large-v3-turbo` / fallback profiline göre `large-v3`
- VAD: Silero VAD
- Çıktılar: `E:\MITAS\outputs\webui_asr_jobs\{job_id}\run`
- OCR, Face, Tag, Logo: disabled, bu akışta çağrılmaz

## Dosya yapısı

```
webui/
├── src/
│   ├── app/
│   │   ├── App.tsx                    # Top-level shell + Tabs
│   │   ├── mock-data.ts               # Geçici mock — backend gelene kadar
│   │   └── components/
│   │       ├── Header.tsx             # Üst bar + iş durumu + model rozetleri
│   │       ├── Sidebar.tsx            # Sıra/ASR/Meta/Kanıt sekmeleri
│   │       ├── Timeline.tsx           # AI kanıt katmanları (8 track)
│   │       ├── VideoPlayer.tsx        # Oynatıcı
│   │       ├── AnalysisWorkspace.tsx  # Analiz İstasyonu yerleşimi
│   │       ├── FaceBankWorkspace.tsx  # Yüz Bankası (v0.4'te aktif olacak)
│   │       ├── ui.tsx                 # Button / Badge / Tabs variant'ları
│   │       ├── ui/                    # shadcn/ui primitives (Radix tabanlı)
│   │       └── figma/                 # Image fallback yardımcısı
│   ├── styles/
│   │   ├── theme.css                  # Renk + glow + tipografi token'ları
│   │   ├── index.css
│   │   └── tailwind.css
│   ├── imports/                       # Figma brief + ham referanslar
│   └── main.tsx
├── guidelines/                        # Figma çıktısının tasarım notları
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── postcss.config.mjs
```

## Tasarım sistemi

Tüm renkler `src/styles/theme.css` içinde tanımlı **semantik token'lar** üzerinden gider. Bileşenlerde **çıplak Tailwind palet adı kullanılmaz** (`bg-slate-950`, `text-cyan-500`, `bg-amber-500/10` vb. yasak). Token şeması:

| Token | Amaç |
|---|---|
| `bg-app-shell` / `bg-surface` / `bg-surface-elevated` | yüzey hiyerarşisi |
| `border-border-subtle` / `border-border-mitas` | sınır |
| `text-foreground-strong/default/muted/disabled` | metin |
| `text-info` / `bg-info-subtle` / `border-info-border` / `shadow-glow-info` | aktif / in-progress |
| `text-success` / `bg-success-subtle` | onay / done |
| `text-warning` / `bg-warning-subtle` / `border-warning-border` | uyarı |
| `text-danger` / `bg-danger-subtle` | hata / reddedildi |

Yeni bir renk veya glow lazım olduğunda **önce `theme.css` içinde token tanımla**, sonra utility'yi kullan. Raw hex / RGBA inline shadow yasak.

## Backend bağlantısı

ASR için mock veri kaldırıldı ve şu API akışı bağlandı:

- `POST /api/asr/transcribe` → yeni koşum (background task)
- `GET /api/jobs/{id}` → polling + transcript/segment/summary
- `GET /api/jobs` → son ASR işleri
- `GET /api/health` → ASR açık, OCR/Face kapalı sağlık bilgisi

İlgili Pydantic şemaları: `core/schemas/module_run.py`, `core/pipelines/asr/result.py`.

## v0.2 → ileri sürümler

| Sürüm | İçerik |
|---|---|
| v0.2 (şimdi) | ASR aktif, diğer modüller placeholder, mock veri |
| v0.3 | OCR/KJ modülü + Üst Denetim kanıt modalı |
| v0.4 | Yüz Bankası workspace |
| v1.0 | Tüm modüller, FastAPI köprüsü, üretim hazır |
