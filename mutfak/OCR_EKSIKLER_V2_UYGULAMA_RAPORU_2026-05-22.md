# OCR Eksikler v2 Uygulama Raporu - 2026-05-22

## Kapsam

Kullanıcının işaret ettiği 8 eksik başlık için OCR deney hattına ilk çalışan uygulama katmanı eklendi. ASR/Tedial akışına dokunulmadı.

## Uygulananlar

- ROI-first: manifest ROI korunuyor; ROI yoksa jenerik/KJ ipuçlarına göre otomatik geniş ROI uygulanıyor ve `roi_strategy`, `applied_roi`, `auto_roi` item summary içine yazılıyor.
- Preprocess bank: `upscale2x`, gerçek `clahe2x`, `sharpen2x`, `unsharp_glow_reduction2x`, `adaptive_threshold2x`, `light_on_dark2x`, `dark_on_light_inverted2x`, `deinterlace_blend2x`.
- Türkçe correction hook: normalize metin karşılaştırma için diakritik fold ediyor; final display için role phrase map ve `E:\MITAS\data\ocr_text_corrections.json` opsiyonel düzeltme dosyası destekleniyor. Örnek dosya: `E:\MITAS\data\ocr_text_corrections.example.json`.
- Rol/isim ayrıştırma: text-layer çıktısından `structured_credits.json` üretiliyor.
- Bbox layout: role/name bantları ve kolon sayısı rapora yazılıyor; role-name pairing bbox ve column id ile yapılıyor.
- Çok boyutlu skor: OCR confidence + temporal support + bbox consistency + text length + engine agreement birleşik `quality_score`.
- Human review loop: `review_pack.json`, `review_pack.csv`, `review_crops/*.png`, accepted/suggested alanları.
- Credit-line filtresi: tekrar eden karakter, sayı/simge ağırlığı, çok kısa satır ve OCR gürültüsü filtreleri sıkılaştırıldı.

## Doğrulama

Unit:

```text
10 passed, 2 skipped
```

K-2 text-layer smoke:

- Input: `E:\MITAS\outputs\ocr_credit_experiments\live_k2_6125_30s_20260522\items\k2_end_credits_live_6125_30s`
- Output: `E:\MITAS\outputs\ocr_credit_experiments\live_k2_6125_30s_20260522\items\k2_end_credits_live_6125_30s\text_layer_descroll_v2_4`
- Role/name pairs: 42
- Review crops: 43
- Estimated scroll: up, -60.167 px/s
- Not: isim hattı belirgin şekilde kullanılabilir; rol hattı hâlâ çok review istiyor.

Ana deney smoke:

- Output: `E:\MITAS\outputs\ocr_credit_experiments\k2_v2_preprocess_smoke_20260522_b`
- Paddle GPU aktif.
- Auto ROI: `[24, 9, 552, 462]`
- Raw frame OCR: 0 kayıt
- Preprocessed frame OCR: 18 kayıt
- Bu sonuç preprocess bank'ın küçük/kötü kontrastlı jenerikte değer ürettiğini gösterdi.

## Kalan Risk

- Rol okuma hâlâ isim okuma kadar temiz değil; düşük güvenli roller review pack ile insan düzeltmesine bırakılıyor.
- Türkçe karakter restorasyonu genel dil modeli değil, kontrollü correction map. Gerçek isim doğruluğu için ground truth ya da isim sözlüğü gerekir.
- Auto ROI güvenli geniş crop kullanıyor; agresif dar ROI henüz yok, çünkü jenerikte yanlış crop büyük veri kaybı yaratır.
