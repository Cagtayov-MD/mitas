# MITAS OCR — Text-First Mimari v1

> **Tarih:** 2026-05-24
> **Yazar:** Opus 4.7 (planlama oturumu)
> **Bağlam:** [mutfak/OCR-OPUS.md §11](../mutfak/OCR-OPUS.md) — 24-film stress test ve `opus_credit_detector` kritik mimari bulgusu.
> **Karar:** B yolu (text-first), 6 faz, KJ-spesifik filtreleme HARİÇ.

---

## 1. Niçin değişiyoruz

### Mevcut "credit-first" mimari yanlış soruyu soruyor
- Pipeline'a verilen görev: **"jenerik penceresi nerede?"**
- Bu görevi yapan eleman: `opus_credit_detector` — yazıyı ayırt etmiyor, sadece "yazımsı dokulu piksel" + "karanlık BG" + "scroll motion" heuristic'leriyle tahmin yürütüyor (`core/pipelines/ocr/credit_detector.py:191-219`).
- PaddleOCR aynı pipeline'da çalışıyor (24 film için 116K+ record üretti, IMDB ile %95+ doğrulukla teyit), ama "yazı nerede?" sorusu **ona değil**, kör tahminciye soruluyor.
- Sonuç: POROROCA + FRANNY gibi filmlerde pencere yanlış daraltılıp jenerik tamamen kaybediliyor.

### Doğru soru
**"Ekranda yazı var mı? Varsa nerede, ne kadar süreyle, ne yazıyor?"**

Yer/süre/hareket → sınıflandırma metası, problem değil. KJ + jenerik kartı + scroll jenerik → tek sorunun alt türleri.

---

## 2. Mimari akış (V1, film modu için)

```
┌──────────────────────────────────────────────────────────────┐
│                      MANIFEST (kind=film_credits)            │
│  opening_window_min: 3 (default) | closing_window_min: 5     │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│  STAGE 1 — DINAMIK PENCERE BULMA (find_dynamic_window)       │
│  • Açılış: t=0..opening_window dk → PaddleOCR detection      │
│  • Sınır frame'de yazı var? → +60sn uzat (maks 8 dk)         │
│  • Kapanış: t=end..end-closing_window dk → aynı kural        │
│  • Çıktı: {opening_segment, closing_segment} time ranges     │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│  STAGE 2 — DENSE OCR (mevcut K-BoxTrack pipeline)            │
│  • Her segment için run_box_track_pipeline çağrılır          │
│  • PaddleOCR detection (stride=3) → box_tracker              │
│  • classify_track_motion → static / scroll                   │
│  • Static → group_static_tracks_into_cards → kart event      │
│  • Scroll → text_layer_row_reconstruct → composite → OCR     │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│  STAGE 3 — TEXT EVENT ADAPTER                                │
│  • Kart/scroll output → events[] formatına maple             │
│  • Her event: type + type_reason + confidence + bbox + text  │
│  • Type-spesifik confidence eşiği uygula (flag low_conf)     │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
                       events.json
                       (text_event schema)
```

### Eski credit-first akışı (legacy, opt-out)
- `USE_LEGACY_CREDIT_PIPELINE=1` ile çağrılır (default OFF)
- `opus_credit_detector` + 8-stage pipeline aynen korunur
- Geri dönüş emniyet + A/B karşılaştırma için 3-6 ay tutulur

---

## 3. Bileşenler ve sorumluluklar

| Bileşen | Sorumluluk | Dosya |
|---|---|---|
| `find_dynamic_window` | Pencere sınırlarını PaddleOCR detection ile bul | `core/pipelines/ocr/dynamic_window.py` (YENİ, Faz 4) |
| `manifest_profiles.dispatch` | `kind` field'ına göre uygun pipeline'a yönlendir | `core/pipelines/ocr/manifest_profiles.py` (YENİ, Faz 2) |
| `run_box_track_pipeline` | Pencere içinde K-BoxTrack koş (DEĞİŞMİYOR) | `core/pipelines/ocr/unified_credit_pipeline.py` (mevcut) |
| `to_text_events` | Pipeline output'unu text_event'e map et | `core/pipelines/ocr/text_event.py` (YENİ, Faz 1) |
| `confidence_thresholds.apply` | Tipe göre eşik uygula, low_conf flag set | `core/pipelines/ocr/confidence_thresholds.py` (YENİ, Faz 5) |

### Değişmeyen bileşenler
- `box_tracker.py` (POC + K-BoxTrack helper'lar)
- `text_layer_row_reconstruct.py` (B-port strict_global + self-correction)
- `image_quality_police.py` (A-fb fallback assessor)
- `paddle_engine` (DI pattern devam)

### Çağrılmayan ama silinmeyen
- `credit_detector.py` (opus_credit_detector) — Faz 6 ile legacy guard'a alınır

---

## 4. Veri formatları

İki ana JSON schema:

1. **`schemas/text_event.schema.json`** — pipeline çıktı formatı (events listesi)
2. **`schemas/manifest_v2.schema.json`** — pipeline girdi formatı (kind + profil)

Ground truth ayrı format:

3. **`tests/data/ocr_ground_truth/*.json`** — manuel etiket (5 film altın referans, Faz 3'te 10'a çıkar)

Detaylar ilgili schema dosyalarında.

---

## 5. Faz sırası

| Faz | İçerik | Madde | Süre | Sahip |
|---|---|---|---|---|
| 0 | Doc + schema dosyaları | — | 0.5 gün | Opus |
| 1 | text_event schema kod + telemetri | 1+8 | 1 gün | Sonnet |
| 2 | Manifest profil sistemi | 6 | 1 gün | Sonnet |
| 3 | Ground truth + regression (10 film) | 4 | 1 gün | Manuel + Sonnet |
| 4 | Dinamik pencere | 2 | 1-2 gün | Sonnet |
| 5 | Type-spesifik confidence | 7 | 0.5 gün | Sonnet |
| 6 | Legacy opt-out | 5 | 1 saat | Sonnet |

Faz 3 ve Faz 4 paralel koşulabilir (farklı Sonnet oturumları).

---

## 6. Kapsam dışı

- **Madde 3 (KJ-spesifik filtreleme):** Çağatay reddetti — film modunda KJ yok, KJ ayrı profilde (`kind: kj_scan`, ileride).
- **`opus_credit_detector` silinmesi:** Faz 6 ile opt-out olarak korunur, 3-6 ay sonra silme kararı.
- **webui değişiklikleri:** Output adapter geriye uyumlu — webui mevcut format'ı okuyorsa çalışmaya devam eder (grep teyit: webui'da `scroll_text_lines.json` veya `unified_credit_pipeline` tüketicisi yok, risk zero).
- **ASR / translate / Tedial:** Bu mimari değişikliğinin onlarla teması yok.

---

## 7. Test ve kabul kriterleri

| Faz | Kabul kriteri |
|---|---|
| 1 | 24-film testi yeniden koş → eski + yeni output yan yana, satır sayısı %100 aynı |
| 2 | Mevcut `kind: end_credits` manifest hiç değişmeden çalışmalı, aynı sonuç |
| 3 | 10 film için ground truth `must_contain_text` assert'leri geçmeli |
| 4 | POROROCA pilot: 0 → en az 100 satır (gerçek scroll kurtarılmalı). FRANNY: 0 → en az 10 satır |
| 5 | Confidence eşiği altı satırlar `low_confidence: true` flag'li, atılmamış |
| 6 | `USE_LEGACY_CREDIT_PIPELINE=1` ile eski 8-stage path koşmalı, çıktı aynı |

---

## 8. Riskler

1. **Faz 4 — has_text() GPU maliyeti:** PaddleEngine detection-only çağrısı saniyede ~50ms. Pencere bulma için 50-100 frame → ~5 sn/film, kabul edilebilir. **Mitigation:** PaddleEngine zaten `unified_credit_pipeline.py:36`'da DI ile alınıyor, mevcut session yeniden kullanılır (yeni init yok).
2. **Faz 1 — output format değişimi:** Tüketici yok (grep teyitli) ama yine de yan yana yazım: `scroll_text_lines.json` (LEGACY) + `events.json` (NEW). Eski silinmez, 2 sürüm sonra silinir.
3. **Faz 3 — ground truth manuel emek:** 10 film × ~30 dk etiketleme = 5 saat. Çağatay tarafından yapılır, opsiyonel olarak Opus IMDB ile öncüsel öneri çıkarır, Çağatay onaylar.

---

## 9. Sonraki adım

[Faz 1 brief'i için ayrı dosya] — Sonnet'e tek tek devredilecek brief'ler içinde.
