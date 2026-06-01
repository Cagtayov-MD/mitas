# MODEL 2 — Panorama-First OCR Pipeline (Yeni)

> **Bu klasör MODEL 2'nin tüm kodunu içerir.**
> **MODEL 1 (mevcut frame-first pipeline) `core/pipelines/ocr/` altındadır, dokunulmaz.**

---

## Hızlı yön

- **Felsefe:** Video'dan tek uzun panoramik PNG üret → multi-engine OCR + multimodal LLM → yapılandırılmış JSON → PDF paket
- **Karar tarihi:** 2026-05-26
- **Durum:** POC aşaması (kod yazımı başlamadı)
- **Dokümantasyon:** `docs/MITAS_OCR_MODEL2_PanoramaFirst_Overview.md`
- **Karşılaştırma planı:** `docs/MITAS_OCR_MODELS_Comparison_Plan.md`

## Klasör yapısı (planlı)

```
model2/
├── README.md                          # bu dosya
├── stitching/                         # document mosaicing
│   ├── scroll_panorama.py             # SIFT + RANSAC scroll stitching
│   ├── static_card_selector.py        # best frame per kart
│   ├── cut_dissolve_detector.py       # rejim değişikliği
│   └── master_panorama_assembler.py
├── enhancement/                       # görsel iyileştirme (OCR öncesi)
│   ├── denoise.py
│   ├── sharpen.py
│   └── super_resolution.py
├── ocr/                               # multi-engine OCR
│   ├── multi_engine_runner.py
│   └── consensus_voter.py
├── llm/                               # multimodal LLM fusion
│   ├── qwen_vl_credits_parser.py
│   └── prompts.py
├── packaging/                         # PDF rapor + kanıt
│   └── pdf_builder.py
└── tests/
    └── test_stitching_smoke.py
```

## Venv

`venvs/model2/` — bağımsız venv (kurulacak). Bağımlılıklar:
- opencv-contrib-python (SIFT için)
- Pillow, numpy, scipy
- PaddleOCR (paylaşılan)
- OneOCR (paylaşılan)
- Qwen-VL client (yerel veya API)
- reportlab (PDF)
- tesseract (opsiyonel)

## Output

`outputs/_model2_prototypes/<film_id>/` altına yazılır. `_model2_` prefix'i MODEL 1 output'larıyla karışmasını engeller.

## Geliştirme kuralları

1. **MODEL 1'in koduna dokunma.** `core/pipelines/ocr/` salt-okuma sayılır.
2. **MODEL 1'in venv'lerine dokunma.** `venvs/core/`, `venvs/ocr/` salt-okuma.
3. **Output ayrımı:** sadece `outputs/_model2_*` altına yaz.
4. **Commit etiketleme:** `feat(model2): ...`, `fix(model2): ...` formatında.
5. **Test/POC ayrı:** `model2/tests/` ve `scripts/_m2_*` script konvansiyonu.

## POC ilerlemesi

Detaylar `docs/MITAS_OCR_MODEL2_PanoramaFirst_Overview.md` §6'da.

| Faz | Açıklama | Durum |
|---|---|---|
| M2-1 | Scroll stitching POC (SIFT + RANSAC) | ⬜ pending |
| M2-2 | Multi-engine OCR + consensus | ⬜ pending |
| M2-3 | Multimodal LLM (Qwen-VL) | ⬜ pending |
| M2-4 | PDF builder | ⬜ pending |
| M2-5 | IMDB/TMDB cross-check | ⬜ pending |
| M2-6 | MODEL 1 karşılaştırma | ⬜ pending |

## İlişkili memory

- `feedback_master_no_worktree.md` — master'da çalış, worktree yok
- `feedback_plan_implement_split.md` — plan Opus, uygula Sonnet
- `project_models_split.md` — bu iki-yollu yaklaşımın memory kaydı

---

**Önemli:** POC sonuçları MODEL 1 ile karşılaştırılır, geçiş kararı sonra verilir. Şimdilik iki yol paraleldir.
