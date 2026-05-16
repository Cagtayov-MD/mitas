# UI LOG sayfası + Klip görünümü — backend brief

> MITAS WebUI'a "LOG" sekmesi/sayfası ekleyecek geliştirici (Figma Make, başka
> editör) için backend brief'i. Backend tarafı hazırdır; bu yazıda sadece
> "neyi nasıl çağıracaksın, ne göstereceksin" anlatılır.

## Mimari özet

Çıktılar **klip-merkezli** klasör yapısında durur. Bir klibin tüm modül
çıktıları (ASR, ileride OCR/face/tag/logo) aynı klip klasörü altında toplanır.
Loglama iki katmanlıdır:

| Katman | Dosya / Endpoint | Amaç |
|---|---|---|
| **Sistem olayları** (kullanıcıya gösterilen) | `outputs/system_events.jsonl` → `GET /api/events` | "ne yapıldı": import, ASR başladı/bitti, çeviri, OCR (ilerde), hata. Modüller arası tek zaman çizgisi. |
| **Job adımları** (detay) | `outputs/clips/<clip_id>/<modül>/<job_id>/job_log.jsonl` → `GET /api/events/{event_id}` yanıtının `job_logs` alanında döner | Bir job'un içindeki adımlar (ASR: normalizasyon, kanal, fallback, dosya yazımı…). |

LOG sayfası **birinci katmanı** ana liste olarak gösterir; satıra tıklanınca
**ikinci katman** detay panelde açılır.

## Klasör yapısı

```
outputs/
├── system_events.jsonl                 ← TÜM modüllerin olayları (append-only)
└── clips/
    └── <clip_id>/                      ← klip-merkezli kök
        ├── clip.json                   ← kimlik + modül durumları özeti
        ├── source/<filename>           ← yüklenen ham dosya
        ├── asr/<job_id>/               ← ASR job
        │   ├── job.json                ← durum (status, progress, paths)
        │   ├── job_log.jsonl           ← ASR içi adımlar
        │   └── run/                    ← pipeline çıktıları
        │       ├── archive.json
        │       ├── summary.json
        │       ├── transcript_review.json
        │       └── timeline_events.json
        ├── translations/               ← çeviri cache
        ├── ocr/<job_id>/               ← ilerde
        ├── face/<job_id>/              ← ilerde
        ├── tag/<job_id>/               ← ilerde
        └── logo/<job_id>/              ← ilerde
```

### `clip_id` nasıl üretilir

- Yüklenen dosya `er_vid.mp4` → `clip_id = "er_vid"` (filename stem)
- Aynı isim daha önce yüklendiyse → `clip_id = "er_vid_2"`, sonra `er_vid_3`, ...
- Üst üste yazma yok; eski klip her zaman korunur
- Yükleme zamanı `clip.json` içinde `imported_at` olarak durur, sıralama gerekirse oradan
- Her olayda hem **`media_id`** (insan-okur stem, hep aynı kalır) hem **`clip_id`** (unique klasör) bulunur

### `clip.json` örneği

```json
{
  "clip_id": "er_vid",
  "media_id": "er_vid",
  "filename": "er_vid.mp4",
  "imported_at": "2026-05-16T13:42:01.118Z",
  "size_bytes": 88412160,
  "source_path": "E:/MITAS/outputs/clips/er_vid/source/er_vid.mp4",
  "modules": {
    "asr":  { "jobs": ["asr-abc123"], "latest_job_id": "asr-abc123", "status": "done",   "updated_at": "..." },
    "ocr":  { "jobs": ["ocr-def456"], "latest_job_id": "ocr-def456", "status": "running","updated_at": "..." }
  }
}
```

## Sistem olayı şeması

`outputs/system_events.jsonl` — append-only JSONL. Her satır:

```json
{
  "event_id": "evt-2a4f1be9c603",
  "ts": "2026-05-16T13:44:06.422Z",
  "kind": "asr_completed",
  "level": "info",
  "summary": "er_vid.mp4 için ASR tamamlandı (124 sn).",
  "module": "asr",
  "media_id": "er_vid",
  "filename": "er_vid.mp4",
  "job_id": "asr-abc123",
  "duration_seconds": 124.0,
  "detail": { "clip_id": "er_vid", "profile": "fast_with_fallback", "fallback_triggered": false }
}
```

`clip_id` her zaman `detail.clip_id` altında durur (alanı her olay için
zorunlu kılmamak için). UI bunu okuyup klip-merkezli görünümlere link
verebilir.

### Olay tipleri

| kind | level | Ne zaman | module |
|---|---|---|---|
| `media_imported` | info | Kullanıcı **yeni** dosya yükledi | upload |
| `media_reused` | info | Yüklenen dosya daha önce işlenmiş, mevcut transkript kullanılıyor | upload |
| `asr_queued` | info | ASR kuyruğa alındı | asr |
| `asr_started` | info | ASR worker iş üzerine geçti | asr |
| `asr_reprocess_started` | info | Aynı klibe `force=full` ile yeniden ASR koşuluyor | asr |
| `asr_completed` | info | ASR başarıyla bitti | asr |
| `asr_partial` | warn | ASR kısmi sonuçla bitti | asr |
| `asr_failed` | error | ASR hata verdi | asr |
| `translate_started` | info | Çeviri başladı | translate |
| `translate_completed` | info | Çeviri bitti | translate |
| `translate_failed` | error | Çeviri başarısız | translate |

İlerde aynı şemada `ocr_*`, `face_*`, `tag_*`, `logo_*` eklenecek.

## API uçları

### `GET /api/events`

Query parametreleri (hepsi opsiyonel):

- `limit` (1..2000, default 200)
- `since` — ISO-8601; bu ts'den sonraki olaylar (polling)
- `kind`, `level` (`info|warn|error`), `module`
- `media_id` — bir klibin olaylarını filtrele
- `job_id` — bir job'un olaylarını filtrele

Yanıt:
```json
{ "events": [ ... newest first ... ], "count": 42 }
```

### `GET /api/events/{event_id}`

Olay + bağlı job'un adım logları:

```json
{
  "event": { ... },
  "job_status": "done",
  "job_logs": [
    { "ts": "...", "level": "info", "stage": "upload",   "message": "Medya yüklendi.",            "progress_percent": 3 },
    { "ts": "...", "level": "info", "stage": "pipeline", "message": "Normalizasyon başladı.",     "progress_percent": 15 },
    { "ts": "...", "level": "info", "stage": "done",     "message": "ASR tamamlandı.",            "progress_percent": 100 }
  ]
}
```

### `GET /api/clips`

```json
{
  "clips": [
    {
      "clip_id": "er_vid",
      "media_id": "er_vid",
      "filename": "er_vid.mp4",
      "imported_at": "...",
      "size_bytes": 88412160,
      "module_summary": {
        "asr": { "status": "done",    "latest_job_id": "asr-abc123", "job_count": 1, "updated_at": "..." },
        "ocr": { "status": "running", "latest_job_id": "ocr-def456", "job_count": 1, "updated_at": "..." }
      }
    }
  ],
  "count": 1
}
```

### `GET /api/clips/{clip_id}`

Bir klipin **her şeyi tek merkezde**: kimlik, modül özeti, tüm jobları
(her modülden), o klibe ait son 500 olay.

```json
{
  "clip_id": "er_vid",
  "media_id": "er_vid",
  "filename": "er_vid.mp4",
  "module_summary": { ... },
  "jobs": [
    { "job_id": "ocr-def456", "module": "ocr", "status": "running", ... },
    { "job_id": "asr-abc123", "module": "asr", "status": "done",
      "transcript": "...", "segments": [...], "logs": [...] }
  ],
  "events": [ ... newest first, only this clip ... ]
}
```

### `POST /api/asr/transcribe` — yeni davranış (dedup + force)

Query parametreleri:
- `filename` (default `"media"`)
- `profile` (default `"fast_with_fallback"`)
- `channel_mode` (`mono | split | auto`, default `auto`)
- `force` (`none | full`, default `none`) — `full` ile aynı klibe yeniden ASR

Sunucu upload sırasında dosyanın **sha256** hash'ini hesaplar. Üç senaryo:

**1. Yeni içerik** (hash hiçbir klipte yok)
```json
{
  "job_id": "asr-abc123",
  "clip_id": "er_vid",
  "content_hash": "8f3a1c...",
  "reused": false,
  "reprocessed": false,
  "status": "queued",
  "progress_percent": 5,
  ...
}
```

**2. Duplicate tespit edildi** (`force=none`) — ASR koşulmaz, mevcut ASR job uyumlu yanıt döner
```json
{
  "reused": true,
  "job_id": "asr-abc123",
  "status": "done",
  "clip_id": "er_vid",
  "content_hash": "8f3a1c...",
  "filename": "er_vid.mp4",
  "imported_at": "2026-05-16T13:42:01Z",
  "latest_asr_job_id": "asr-abc123",
  "asr_status": "done",
  "message": "Bu klip daha önce işlenmiş, mevcut transkript kullanılıyor.",
  "reprocess_url": "/api/asr/transcribe?filename=er_vid.mp4&force=full",
  "module_summary": {
    "asr": { "status": "done", "latest_job_id": "asr-abc123", "job_count": 1 }
  }
}
```

UI bunu görünce iki seçenek sunar:
- **"Mevcut transkripti aç"** → yanıt zaten son job formatını taşır; gerekirse `GET /api/jobs/{latest_asr_job_id}` ile tazele
- **"Tekrar işle"** → aynı dosyayı `reprocess_url`'e POST et (`?force=full`)

**3. Force full** (mevcut klip, yeni ASR)
```json
{
  "job_id": "asr-xyz789",
  "clip_id": "er_vid",
  "content_hash": "8f3a1c...",
  "reused": false,
  "reprocessed": true,
  "previous_job_id": "asr-abc123",
  "status": "queued",
  ...
}
```

Eski transkript silinmez; klibin altına yeni `asr/<job_id>/` eklenir.
`clip.json`'da `modules.asr.latest_job_id` yeni job'a güncellenir, eski
job `modules.asr.jobs[]` listesinde kalır.

### `GET /api/jobs` ve `GET /api/jobs/{job_id}`

Önceden vardı, **path'leri arkada değişti** ama API yanıtı aynı; eski UI kodu
kırılmaz. Yanıta `clip_id`, `media_id`, `module`, `job_dir`, `clip_dir`
alanları eklendi.

## LOG sayfası — tasarım

### Ana liste (her olay tek satır)

```
13:42:11  ●  er_vid.mp4 için ASR tamamlandı (124 sn).        asr    ›
            ↑      ↑                                               ↑
           level   summary (direkt göster)                          modül rozeti
           renk
```

- `level=info` → cyan/yeşil, `warn` → kehribar, `error` → kırmızı
- Üstte filtreler: tümü / modül / seviye / klip (`media_id`)
- Polling: `?since=<en yeni ts>` ile 2-5 sn aralık

### Detay paneli (bir satıra tıklayınca)

`GET /api/events/{event_id}` çağır. Üstte olayın özeti, altında `job_logs`
zaman damgalı dikey liste. `error` varsa üstte kırmızı blok.

### Klip görünümü (ekstra, opsiyonel ama önerilen)

Klipler sekmesi: `GET /api/clips` ile kart/satır listesi.

```
er_vid.mp4    [ASR ✓]  [OCR ⟳]  [Face —]  [Tag —]
              84 MB · 13:42                    ›
```

Karta tıklayınca: `GET /api/clips/er_vid` → tek ekranda klipin **her şeyi**:
- Her modülün son durumu + tüm geçmiş jobları
- Klip-özel olay timeline'ı (`events` zaten filtrelenmiş)
- Bir job kartına tıklanınca o jobun adım logları açılır

Kullanıcının istediği "işlemler bittikten sonra tek merkezden herşey
görünebilir" davranışı budur.

## Frontend implementasyon notları

- CORS `localhost:5173` ve `127.0.0.1:5173` için açık
- Polling yeterli; WebSocket gerekmez (canlı STT preview için zaten ayrı WS var)
- `summary` zaten Türkçe — yeniden formatlama yapma, direkt göster
- `ts` UTC → `new Date(ts).toLocaleTimeString("tr-TR")` ile yerel saat
- `error` 4000 karaktere kadar olabilir; listede ilk satır, detayda tam

## Hatırlatma

- Olayları silme/edit etme endpoint'i yok (append-only)
- Eski (clip-öncesi) dev jobları `outputs/webui_asr_jobs/` altında durmaya
  devam eder; `/api/jobs` onları da listeler ama `/api/clips`'te görünmez.
  Manuel silinebilir.
- `system_events.jsonl` çok büyürse ilerde rotation eklenir, UI dokunmaz.
