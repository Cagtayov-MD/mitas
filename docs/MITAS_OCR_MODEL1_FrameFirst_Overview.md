# MITAS OCR — MODEL 1: Frame-First Pipeline (Mevcut)

> **Felsefe:** Video frame'lerini tek tek tarayıp text bul, sonra birleştir.
> **Adı:** MITAS1 / Frame-First / "frame-merkezli"
> **Durum:** Olgun, üretimde, 50 filmde test edildi.

---

## 1. Mimari akış

```
Video (.mp4)
   ↓ ffmpeg + fps=6
1800 frame  (her saniyede 6 kare)
   ↓ her frame'e PaddleOCR detection
bbox listesi (frame başına ~5-30 kutu)
   ↓ box_tracker.build_text_tracks
track'ler (IoU eşleştirme ile aynı yazı birleşir)
   ↓ classify_track_motion (velocity_y eşik 2.0)
static_text  |  scrolling_text
   ↓                ↓
group_static    text_layer_row_reconstruct
_tracks         (LK feature tracker + composite)
   ↓                ↓
cards/          scroll/row_composite.png
   ↓                ↓
events.json (merged, type: card | scroll_credit)
   ↓
master PNG compositor (Faz 22, spatial-faithful)
   ↓
credits.png (insan okur)
```

**Karar verici sayısı:** ~8 katman. Her birinde küçük bir hata birikiyor.

## 2. Kod konumu

```
core/pipelines/ocr/
├── unified_credit_pipeline.py        # K-BoxTrack orchestrator
├── box_tracker.py                    # PaddleOCR detection + IoU tracking
├── credit_detector.py                # opus_credit_detector (kör tahminci, deprecate yolda)
├── credit_experiment.py              # 8-stage eski yol + USE_BOX_TRACK_PIPELINE gate
├── credit_pipeline_selector.py       # 4-kategori matrisi
├── credit_scene_router.py
├── credit_segment_dispatcher.py
├── image_quality_police.py           # BROKEN_BLACK/BACKGROUND_LEAK detector
├── manifest_profiles.py              # film_credits / end_credits dispatch (Faz 2)
├── temporal_fusion.py                # K-3 median + K-4 variance (eski yol)
├── text_event.py                     # text_events_schema (Faz 1)
├── text_layer_descroll.py            # eski yol scroll
├── text_layer_row_reconstruct.py     # scroll composite + LK alignment (B-port)
├── text_track_state.py
└── simple.py                         # lightweight entry
```

**Toplam:** ~10.000 satır kod.

## 3. Venv

```
venvs/
├── core/      # genel Python (Pillow yok!)
└── ocr/       # PaddleOCR + Pillow + OpenCV
```

## 4. Output prefix

```
outputs/
├── ocr_24films_*                     # 24-film pilot serisi
├── ocr_50films_*                     # 50-film pilot serisi
├── ocr_diziler_*                     # dizi pilotları
├── filmtest_*                        # tek-film testleri
└── _prototype_credits_png/           # Faz 22 master PNG compositor
```

## 5. Şu anki yetenekleri

| Durum | Sonuç |
|---|---|
| Frame-frame OCR | ✓ |
| Track tabanlı sınıflandırma (static / scroll) | ✓ |
| Scroll composite (row_composite.png) | ✓ (B-port v1+v2+v3 ile stabil) |
| Static kart best_frame seçimi | ✓ |
| Master PNG compositor (Faz 22) | ✓ (4 film + 1 dizide test) |
| OneOCR fallback (V2.1) | ✓ (FRANNY/POROROCA gibi zor vakalarda) |
| 4-kategori router (A/B/C/D) | ✗ (yarı yarıya, BG axis ayrımı yok) |
| Text-type classifier (subtitle/credit ayrımı) | ✗ (Faz 8 planlandı) |
| Track-arası grouping (cast roster, dissolve) | ✗ (Faz 9 planlandı) |
| Türkçe karakter doğruluğu | 🟡 (Paddle latin_PP-OCRv5 zayıf, OneOCR Türkçe daha iyi) |

## 6. Bilinen sınırlar

1. **Frame-frame OCR pahalı** — 1800 frame × Paddle = ~80 saniye/film. Multi-engine cross-check daha pahalı.
2. **Composite kalitesi OCR'a geri besleme yapmıyor** — pipeline frame-frame OCR'lar, sonra composite üretir. Composite bulanıksa, OCR zaten yapılmış olduğu için düzeltilmiyor.
3. **8 katmanda kümülatif hata** — her katmanda %2-5 kayıp, sonuçta %65-78 doğruluk.
4. **Türkçe karakterler sızıntılı** — diakritik (Ş/Ç/Ğ/İ) Paddle latin modelinde tutarsız.
5. **Mimari karmaşık** — credit_detector + scene_router + selector çakışıyor, §6'da 17 saçmalama maddesi listelendi.

## 7. Geçmiş düzeltmeler (chronological)

- `d1d3c95` — K-BoxTrack landed (unified pipeline)
- `4497997` — row_count penalty 90→300 (X-MEN regression fix)
- `18b4be6` — B-port: strict_global text mask + tail_trim self-correction (ANJELIK fix)
- `9f0c745` — C-kart: overlap-based card grouping
- `7ac6060` — A-fb: scroll fallback safety net + composite OCR restore
- `bf2c047` — D-split: paired role|name via auto_split + bbox derivation
- `5afcda8` — E: K-BoxTrack default ON, eski yol opt-out
- (V2.1) — OneOCR fallback for hard scrolls
- Faz 1: text_event schema
- Faz 2: manifest profile dispatch (film_credits opening+closing)
- Faz 4: dynamic_window (scroll genişledikçe pencere uzar)
- Faz 22 (2026-05-26): master PNG compositor (spatial-faithful)

## 8. Sıradaki adımlar (planlı)

- **Faz 8** — Rule-based text-type classifier (Y konumu + süre + dil pattern → subtitle/card/scene_text/scroll_credit ayrımı)
- **Faz 9** — Track-arası temporal grouping (cast roster block, dissolve transition)
- **OneOCR Türkçe** — Diziler için Türkçe scroll satırlarının OneOCR fallback'ı

## 9. Avantaj/Dezavantaj özet

**Avantajları:**
- Olgun, test edilmiş, 50 filmde koştu
- B-port + A-fb + V2.1 düzeltmeleri yapıldı
- Spatial fidelity korunmuş (kart bbox.x → master PNG'de aynı x)
- Mevcut OCR motorları (Paddle/OneOCR) destekli

**Dezavantajları:**
- 8 katman, kümülatif hata
- Composite kalitesi OCR'a geri besleme yapmıyor
- Frame-frame OCR pahalı
- Türkçe karakter zayıflığı
- Mimari karmaşık (10.000 satır)

---

**Karar (2026-05-26):** Bu yol prod'da çalışmaya devam eder. Yan tarafta MODEL 2 (panorama-first) prototype olarak geliştirilir. Karşılaştırma kriterleri için: `MITAS_OCR_MODELS_Comparison_Plan.md`.
