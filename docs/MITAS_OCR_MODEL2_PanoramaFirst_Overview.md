# MITAS OCR — MODEL 2: Panorama-First Pipeline (Yeni)

> **Felsefe:** Video'dan tek bir uzun panoramik PNG üret, sonra OCR + multimodal LLM ile yapılandır.
> **Adı:** MITAS2 / Panorama-First / "panorama-merkezli"
> **Durum:** POC aşaması (2026-05-26). Henüz kod yok, sadece tasarım.

---

## 1. Mimari akış

```
Video (.mp4)
   ↓ ffmpeg
ham frame'ler (varsa zaten pilot output'unda)
   ↓ scene segmentation (cut/dissolve tespiti)
segment'ler (opening_static / opening_scroll / closing_static / closing_scroll)
   ↓ her segment için:
      • static kart → best_frame seçimi
      • scroll → SIFT + RANSAC ile panorama stitching (motion estimation)
      • cut'lı serial kart → ardarda yığma
   ↓
panorama parçalar (her segment için 1)
   ↓ master assembler
TEK uzun panoramic credits.png  (örn. 1920×15000)
   ↓ görsel iyileştirme (denoise, sharpen, contrast, opsiyonel super-resolution)
temizlenmiş panorama
   ↓ paralel OCR (Paddle + OneOCR + opsiyonel Tesseract)
multi-engine OCR sonuçları
   ↓ multimodal LLM (Qwen-VL veya Claude Vision)
   "Yönetmen kim? Yapımcı kim? Cast listesi? Konuk oyuncu?"
   ↓
yapılandırılmış JSON (cast, crew, songs, etc.)
   ↓ external knowledge cross-check (IMDB/TMDB)
   ↓ PDF builder
[Sayfa 1: yapılandırılmış künye] + [Sayfa 2+: panorama PNG kanıt]
   ↓
credits.pdf (tek paket, hem rapor hem kanıt)
```

**Karar verici sayısı:** ~3 katman. Sade.

## 2. Kod konumu (planlanan)

```
model2/
├── README.md
├── stitching/
│   ├── __init__.py
│   ├── scroll_panorama.py            # SIFT + RANSAC scroll stitching
│   ├── static_card_selector.py       # best frame per kart
│   ├── cut_dissolve_detector.py      # rejim değişikliği tespiti
│   └── master_panorama_assembler.py  # tüm parçaları birleştir
├── enhancement/
│   ├── __init__.py
│   ├── denoise.py
│   ├── sharpen.py
│   └── super_resolution.py           # opsiyonel
├── ocr/
│   ├── __init__.py
│   ├── multi_engine_runner.py        # Paddle + OneOCR paralel
│   └── consensus_voter.py            # 3 motor oyu
├── llm/
│   ├── __init__.py
│   ├── qwen_vl_credits_parser.py     # multimodal LLM ile yapılandır
│   └── prompts.py
├── packaging/
│   ├── __init__.py
│   └── pdf_builder.py                # PDF rapor + kanıt PNG
└── tests/
    └── test_stitching_smoke.py
```

## 3. Venv

```
venvs/
└── model2/    # MODEL 2'ye özel bağımlılıklar
    # Üzerindekiler (planlı):
    #   - opencv-python (SIFT + RANSAC için contrib gerek)
    #   - opencv-contrib-python
    #   - Pillow, numpy, scipy
    #   - paddleocr (paylaşılan, ama kendi venv'inden)
    #   - oneocr (paylaşılan)
    #   - qwen-vl client (yerel veya API)
    #   - reportlab (PDF üretimi)
    #   - tesseract opsiyonel
```

**Not:** Şu an `venvs/model2/` yok. POC'ye geçince kurulur.

## 4. Output prefix

```
outputs/
└── _model2_prototypes/
    ├── 1989_kukla_adam/
    │   ├── panorama.png              # üretilmiş tek panorama
    │   ├── enhanced.png              # iyileştirilmiş
    │   ├── ocr_paddle.json
    │   ├── ocr_oneocr.json
    │   ├── llm_response.json         # multimodal LLM yapılandırılmış cevap
    │   ├── stitching_report.json     # hangi frame'ler birleşti, kalite metrikleri
    │   ├── credits.pdf               # ANA ÜRÜN (rapor + kanıt)
    │   └── debug/
    │       ├── segments/             # her segment'in ayrı panorama'sı
    │       └── frame_matches/        # SIFT match görselleri
    └── 1980_son_metro/
        └── ...
```

`_model2_` prefix'i Model 1 ile karışmasını engeller.

## 5. Akademik temel

| Adım | Bilinen yöntem / referans |
|---|---|
| Scene segmentation | PySceneDetect (cut + dissolve) |
| Scroll stitching | Document Mosaicing (Zappalá, Gee, Taylor 1999), SIFT + RANSAC |
| Pedestal shot mosaicing | [academia.edu — Mosaicing of Text Contents from Consecutive Frames](https://www.academia.edu/25378996/) |
| Multi-engine OCR | Standard ensemble voting |
| Multimodal LLM | Qwen2.5-VL / Claude 3.5 Vision / GPT-4V |
| Knowledge sync | IMDB/TMDB API |
| PDF report builder | reportlab + PIL |

## 6. POC adımları (planlı)

### Faz M2-1 — Scroll stitching POC (1-2 gün)
- 1 film seç (KUKLA test için fazla statik, **JURASSIC scroll için ideal**)
- Closing 30 saniyelik scroll segment'i al
- SIFT + RANSAC ile panorama üret
- Mevcut `row_composite.png` ile karşılaştır:
  - Görsel kalite (göz)
  - OCR doğruluğu (Paddle)
  - Stitch hatası (ghost, kayma)

### Faz M2-2 — Multi-engine OCR (1 gün)
- POC panorama'ya Paddle + OneOCR paralel ver
- Consensus voting basit kural: confidence > 0.7'lik birinden al, çelişkide higher conf kazanır
- Mevcut MITAS1 ile aynı film için karşılaştırma

### Faz M2-3 — Multimodal LLM (1-2 gün)
- Yerel Qwen-VL veya Claude API
- Panorama PNG → "yönetmen, cast, crew yapılandır" prompt
- JSON çıktı

### Faz M2-4 — PDF builder (1 gün)
- 1. sayfa yapılandırılmış künye
- 2-N. sayfa panorama PNG (tam çözünürlük)
- Tek PDF/film

### Faz M2-5 — IMDB/TMDB cross-check (1-2 gün)
- LLM cevabını IMDB API ile doğrula
- Eşleşmeyen isimler için warning

### Faz M2-6 — Karşılaştırma (1 gün)
- 5 film seç (her kategoriden + Türkçe dizi)
- MODEL 1 ve MODEL 2 paralel koş
- `MITAS_OCR_MODELS_Comparison_Plan.md`'deki kriterlerle skor

**Toplam POC süresi:** ~8-12 iş günü (1 buçuk hafta).

## 7. Avantaj/Dezavantaj özet

**Avantajları:**
- Mimari sadelik (3 katman vs 8 katman)
- OCR tek seferde, multi-engine kolay
- Görsel iyileştirme OCR'dan ÖNCE (kritik)
- Akademik temeli güçlü (document mosaicing 1990'dan beri)
- Multimodal LLM ile uyumlu (2024-2026 trend)
- Çağatay'ın asıl tasarımına doğal uyum

**Dezavantajları:**
- Henüz kod yok, POC riski
- Stitching trivial değil (özellikle hareketli BG)
- Multimodal LLM kurulum maliyeti
- Mevcut MITAS1'in olgunluğunu kaybetme riski

## 8. Hangi durumlar için daha iyi olabilir

- Türkçe diziler (OCR motoru zayıf, multimodal LLM Türkçe iyi)
- Hareketli BG'li jenerikler (composite kalitesi geri besleme yapacak)
- Çok katmanlı scroll'lar (CHANSONS gibi multi-block)
- TRT arşivinin niş içerikleri (IMDB'de eksik filmler)

## 9. Hangi durumlar için MODEL 1 hâlâ üstün olabilir

- Klasik Hollywood scroll (JURASSIC, X-MEN) — frame-frame Paddle yeterli
- Düşük confidence durumda kalite kontrolü — MODEL 1'in 8 katmanı debug için zengin
- Hız (kısa segmentler) — MODEL 1 daha hızlı tek-frame'lerde

---

**Karar (2026-05-26):** POC'ye başlanır. Sonuçlar MODEL 1 ile karşılaştırılır. Geçiş kararı POC sonrası verilir.
