# OCR K-2 Ek Düzeltmeler

Tarih: 2026-05-23

## Uygulananlar

1. Main displacement estimator cruise speed'e bağlandı.
   - Dosya: `E:\MITAS\core\pipelines\ocr\text_layer_row_reconstruct.py`
   - `_estimate_displacements()` artık cruise-speed EMA yolunu kullanıyor.
   - `boot_min = 50`, `reset_min = 5`, `reset_dev = 0.35`, `ema_alpha = 0.95`.
   - Sıfır hıza erken kilitlenme guard'ı eklendi: cruise speed sıfıra yakın ama ölçülen dy medyanı scroll gösteriyorsa cruise medyana çekiliyor.

2. `quality_score` içine ghost penalty eklendi.
   - Composite yatay dilimlerde text-mask örtüşmesiyle tekrar/ghost sinyali ölçülüyor.
   - Skor formülü ghosting'i cezalandırıyor.
   - Debug alanı: `ghost_penalty`.

3. K-2 regression manifest doğrulandı.
   - Dosya: `E:\MITAS\data\ocr_k2_regression_last3min_20260523.json`
   - `scroll_auto_detect: true` mevcut.

4. Composite component filtresi düzeltildi.
   - Eski `width * height * 0.035` uzun composite'lerde aşırı büyük component'leri geçiriyordu.
   - Yeni hesap efektif yüksekliği sınırlandırıyor, böylece sahne/gürültü blokları text component sanılmıyor.

5. Scene router text mask'i güçlendirildi.
   - `credit_scene_router.py` artık row reconstruct tarafındaki daha güçlü local-contrast + edge + component-filter mantığına yakın maske kullanıyor.

6. `text_layer_descroll.py` pixel loop'u NumPy'a alındı.
   - Eski Python piksel döngüsü büyük canvas'larda gereksiz yavaştı.
   - Yeni HSV/gray maskeleme vektörel çalışıyor.

7. Scene router ROI uyumsuzluğu düzeltildi.
   - İlk scene router analizi artık ROI uygulanmış frame değil, pre-ROI full-frame `scroll_reconstruct_frames` üstünden yapılıyor.
   - Refined ROI analizi ayrı JSON'a yazılıyor ama row reconstruction kararını ezmiyor.

8. User correction cache dosya mtime kontrollü yapıldı.
   - `ocr_text_corrections.json` değişirse process restart gerekmeden tekrar yüklenir.

9. Küçük temizlikler.
   - `credit_detector.py` içinde `sorted(...)[-1]` yerine `max(..., key=abs)`.
   - `_best_role_for_name` içindeki 14 px sabit ayrım frame genişliğine göre normalize edildi.

## Smoke Sonucu

K-2 mevcut frame'leriyle hızlı row reconstruct:

```json
{
  "composite_size": [600, 4481],
  "processed_frame_count": 605,
  "row_count": 121,
  "median_dy_per_frame": -9.4896,
  "displacement_range_px": 4001.1618,
  "quality_score": 1.0,
  "ghost_penalty": 0.0,
  "selected": "current_displacement"
}
```

Composite:

`E:\MITAS\outputs\ocr_credit_experiments\k2_row_smoke_after_mask_cache_fixes_20260523\row_composite.png`

## Not

10-film tam regresyonu bu ek düzeltmelerden sonra yeniden koşulmalı. Önceki turda Beyaz Balina için cruise speed'in sıfır hıza kilitlenmesi yakalanmıştı; bu yüzden guard eklendi ve hedefli Beyaz Balina smoke'unda uzun pano rejimi geri gelmişti.
