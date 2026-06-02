# OCR Router İlk Ekleme ve Fayda Testi - 2026-05-22

## Eklenen Parça

- `E:\MITAS\core\pipelines\ocr\credit_scene_router.py`
- `E:\MITAS\core\pipelines\ocr\credit_pipeline_selector.py`
- `E:\MITAS\tests\test_ocr_credit_scene_router.py`

Ana OCR deney hattına `scene_router.json` ve `scene_router_refined.json` üretimi eklendi. Bu aşamada router mevcut pipeline'ı otomatik değiştirmiyor; kararını raporluyor.

## Vaat

Router'ın ilk vaadi:

- scroll / static ayrımı
- lower-third / center layout ayrımı
- low contrast için preprocess önerisi
- hareketli arka plan için text mask / background suppression önerisi
- OCR bbox geldikten sonra visual-only hatayı düzeltebilme

## Sentetik Test Sonucu

```text
10 passed, 4 skipped
```

Sentetik fayda kontrolü:

- Dikey kayan yazı -> `vertical_scroll`, temporal=`row_reconstruct`
- Sabit alt bant -> `static_card`, layout=`lower_third`, temporal=`best_frame_selection`
- Düşük kontrast -> `low_contrast`, preprocess=`clahe`, `upscale2x`, `sharpen`
- Visual-only `mixed` kararını OCR bbox hareketiyle `vertical_scroll` olarak refine etme testi geçti

## K-2 Gerçek Smoke

Komut:

```powershell
E:\MITAS\venvs\ocr\Scripts\python.exe -m scripts.ocr_credit_experiment `
  --manifest E:\MITAS\data\ocr_live_k2_6125_30s_manifest_20260522.json `
  --output-dir E:\MITAS\outputs\ocr_credit_experiments\k2_router_refined_smoke_20260522 `
  --engines paddle `
  --max-frames 8 `
  --preprocess-mode off
```

Çıktılar:

- `E:\MITAS\outputs\ocr_credit_experiments\k2_router_refined_smoke_20260522\items\k2_end_credits_live_6125_30s\scene_router.json`
- `E:\MITAS\outputs\ocr_credit_experiments\k2_router_refined_smoke_20260522\items\k2_end_credits_live_6125_30s\scene_router_refined.json`

İlk visual-only router sonucu:

```json
{
  "background": "moving_scene",
  "text_motion": "mixed",
  "difficulty": ["low_contrast"]
}
```

Bu kısmi başarıdır: hareketli arka plan ve düşük kontrast doğru, ama scroll kararı visual-only aşamada net çıkmadı.

OCR-bbox refinement sonrası:

```json
{
  "background": "moving_scene",
  "text_motion": "vertical_scroll",
  "difficulty": ["low_contrast"],
  "recommended_temporal": "row_reconstruct",
  "recommended_preprocess": ["text_mask", "background_suppression", "clahe", "contrast_boost"]
}
```

Bu beklenen faydayı sağladı: gerçek K-2 segmentinde router artık doğru şekilde row reconstruction yönünü öneriyor.

## Dürüst Değerlendirme

Başarılı:

- Router ana hatta kırmadan eklendi.
- Karar JSON'u üretildi.
- Visual-only kararın zayıf kaldığı gerçek örnekte OCR-bbox refinement işe yaradı.
- K-2 için öneri artık doğru aileye düşüyor: moving background + vertical scroll -> row reconstruct.

Zayıf:

- Layout hâlâ `unknown`; visual mask hareketli arka planda fazla genişliyor.
- OCR refinement şu smoke'ta sadece 1 track ile karar verdi; daha uzun/fps yüksek koşuda track sayısı artmalı.
- Router kararı henüz pipeline'ı otomatik değiştirmiyor; güvenli olması için sadece rapor modunda.

Sonuç:

Bu ekleme vaat ettiği ilk faydayı kısmen değil, refine aşamasıyla birlikte gerçek örnekte sağladı. Bir sonraki mantıklı adım `text_layer_row_reconstruct.py` ve `auto_split` eklemek.
