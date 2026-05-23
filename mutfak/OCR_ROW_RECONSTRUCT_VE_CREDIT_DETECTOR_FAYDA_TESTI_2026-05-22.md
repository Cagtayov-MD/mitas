# OCR Row Reconstruct + CreditDetector Fayda Testi

Tarih: 2026-05-22

## Eklenenler

1. `core/pipelines/ocr/text_layer_row_reconstruct.py`
   - Center-strip composite üretir.
   - Scroll yoksa bozuk pano üretmek yerine en iyi frame'e düşer.
   - Satır crop'ları çıkarır.
   - Otomatik rol/isim split dener.

2. `scripts/ocr_text_layer_row_reconstruct.py`
   - Row reconstruct CLI.

3. `tests/test_ocr_text_layer_row_reconstruct.py`
   - Sentetik scroll, auto-split ve row crop testleri.

4. `core/pipelines/ocr/credit_detector.py`
   - Video pencerelerini credit skoru ile tarar.
   - Text density, row-structure, dark ratio ve phase/scroll motion sinyallerini raporlar.
   - Jenerik başlangıcı ve scroll/static segment etiketi üretir.

5. `scripts/ocr_credit_detector.py`
   - CreditDetector CLI.

6. `tests/test_ocr_credit_detector.py`
   - Sentetik geç başlayan scroll ve static credit ayrımı.

## Testler

Core venv:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
E:\MITAS\venvs\core\Scripts\python.exe -B -m pytest `
  E:\MITAS\tests\test_ocr_credit_detector.py `
  E:\MITAS\tests\test_ocr_credit_scene_router.py `
  E:\MITAS\tests\test_ocr_text_layer_row_reconstruct.py `
  -q --basetemp E:\MITAS\outputs\pytest_tmp_credit_detector_core_20260522_c
```

Sonuç: `2 passed, 8 skipped`

Not: Skip'ler beklenen durum; core venv'de OpenCV/Numpy görüntü testleri çalıştırılmıyor. OCR venv'de pytest yok, bu yüzden gerçek CV smoke'ları doğrudan Python/CLI ile koşuldu.

## Sentetik Row Reconstruct Smoke

Çıktı:

`E:\MITAS\outputs\row_reconstruct_manual_smoke_20260522_b\out`

Sonuç:

- Composite size: `[640, 736]`
- Motion: `ok`
- Median dy/frame: `-8.0`
- Displacement range: `376 px`
- Auto split: `x=265`, confidence `0.8972`
- Row count: `8`
- Role crop: `8`

Değerlendirme:

Bu testte modül vaat ettiği şeyi yaptı: scroll hareketini ölçtü, frame'den uzun composite üretti, rol/isim boşluğunu buldu ve ayrı crop'lara böldü.

## Gerçek K-2 Row Reconstruct Smoke

Kaynak item:

`E:\MITAS\outputs\ocr_credit_experiments\live_k2_6125_30s_20260522\items\k2_end_credits_live_6125_30s`

Çıktı:

`E:\MITAS\outputs\ocr_credit_experiments\live_k2_6125_30s_20260522\items\k2_end_credits_live_6125_30s\text_layer_row_reconstruct_v1_2`

Sonuç:

- Composite size: `[600, 480]`
- Motion: `static_or_low_scroll`
- Best frame index: `18`
- Displacement range: `4.2993 px`
- Row count: `14`
- Auto split: `x=266`, confidence `0.5037`, status `detected_low_confidence`
- Role/name crop: `14`

Değerlendirme:

Bu testte modül doğru şekilde "scroll pano" üretmedi. Çünkü seçilen 30 sn K-2 aralığında yakalanan frame, dikey akan pano değil, rol solda isim sağda duran cast kartıydı. Eski mantık burada bozuk panorama üretirdi; yeni mantık static/best-frame moduna düştü. Bu beklenen faydayı sağladı.

Kısıt:

Auto-split doğru yere yakın ama düşük güvenli. Bunun sebebi rol sütununun çok dar, isim sütununun çok baskın olması. Bu crop üretmek için işe yarıyor, fakat production kararında insan/ikinci skor kontrolü gerektirir.

## CreditDetector Sentetik Smoke

Çıktı:

`E:\MITAS\outputs\credit_detector_manual_smoke_20260522_b`

Geç başlayan scroll:

- İlk iki pencere: `non_credit`
- Scroll segment: `15.0 - 25.0`
- Label: `scrolling_credit`

Not: Scroll aslında 10. saniyede başlatıldı; ilk 10-15 penceresinde yazı yoğunluğu çok az olduğu için threshold altında kaldı. Bu, detector'ın daha sonra overlapped/shorter window ile iyileştirilmesi gereken doğal zayıflığı.

Static credit:

- Segment: `10.0 - 25.0`
- Label: `static_or_mixed_credit`

Değerlendirme:

Sentetikte scroll/static ayrımı çalıştı. Başlangıç hassasiyeti için bindirmeli pencere şart.

## K-2 CreditDetector Gerçek Smoke

Komut:

```powershell
E:\MITAS\venvs\ocr\Scripts\python.exe -B -m scripts.ocr_credit_detector `
  --video C:\Users\TRT03\Desktop\evoArcadmin_COZUMLEMEV2S17_1991-0339-1-0000-01-1-K-2.mp4 `
  --output-dir E:\MITAS\outputs\ocr_credit_experiments\k2_credit_detector_6080_6165_20260522_d `
  --start-seconds 6080 `
  --end-seconds 6165 `
  --window-seconds 10 `
  --stride-seconds 5 `
  --sample-fps 2 `
  --score-threshold 0.38
```

Sonuç:

- Bulunan ilk credit başlangıcı: `6125.0`
- Kullanıcının verdiği gerçek başlangıç: `6125.0`
- Segment: `6125.0 - 6165.0`
- Label: `scrolling_credit`
- Confidence: `0.4918`

Değerlendirme:

Bu haliyle CreditDetector K-2 örneğinde vaat ettiği şeyi yaptı: başlangıcı doğru saniyede buldu ve segmenti scrolling credit olarak etiketledi.

## Önemli Öğrenme

İlk detector sürümü fazla false-positive verdi; arka plan edge'lerini metin sandı ve 6080'den itibaren credit dedi.

İkinci sürüm row-structure eklenince false-positive azaldı ama başlangıcı geç yakaladı.

Üçüncü sürümde:

- row-structure kaldı,
- güçlü vertical scroll bonusu eklendi,
- 10 sn pencere 5 sn stride ile bindirmeli tarandı.

Böylece K-2 başlangıcı tam `6125.0` olarak yakalandı.

## Net Durum

Bu iki ekleme projeye alınmaya değer:

- Row reconstruct artık kör panorama değil, scroll kalite kapısı olan satır/crop üretici.
- CreditDetector artık başlangıç tespiti ve scroll/static router için gerçek bir ön kapı.

Henüz tamam olmayan taraf:

- Row crop'lara doğrudan Paddle OCR çalıştırıp rol/isim JSON üretme adımı eklenmedi.
- CreditDetector threshold'ları daha fazla gerçek video ile kalibre edilmeli.
- Detector pencereleri için overlap artık CLI'da var, ama batch deney hattına otomatik bağlanmadı.

## Deney Hattı Hook Smoke

Son ekleme:

`credit_experiment.py` artık router `row_reconstruct`, `best_frame_selection` veya `segment_then_route` önerirse otomatik olarak `row_reconstruct.json` ve `text_layer_row_reconstruct/` üretir.

Smoke komutu:

```powershell
E:\MITAS\venvs\ocr\Scripts\python.exe -B -m scripts.ocr_credit_experiment `
  --manifest E:\MITAS\data\ocr_live_k2_6125_30s_manifest_20260522.json `
  --output-dir E:\MITAS\outputs\ocr_credit_experiments\k2_row_hook_smoke_20260522 `
  --engines tesseract `
  --fps 1 `
  --max-frames 10 `
  --preprocess-mode off
```

Sonuç:

- `row_reconstruct.status`: `done`
- `row_count`: `14`
- `composite_size`: `[552, 462]`
- `auto_split_status`: `detected_low_confidence`
- `auto_split_x`: `242`
- `motion_status`: `static_or_low_scroll`
- `row_reconstruct_sec`: `0.407`

Değerlendirme:

Hook çalıştı ve deney hattı içinde beklenen dosyaları üretti. Ayrıca burada önemli bir kontrol sinyali çıktı: router `vertical_scroll` önermiş olsa bile row-reconstruct kendi kalite kapısında `static_or_low_scroll` dedi. Yani yeni katman sadece üretim yapmıyor, router kararını çapraz kontrol eden ikinci bir sinyal de üretiyor.

## Row Crop OCR Smoke

Son ekleme:

`credit_experiment.py` artık row reconstruct sonrası `role_crops` ve `name_crops` üzerinde OCR çalıştırıp şunları üretir:

- `row_crop_ocr.json`
- `row_crop_ocr.md`

Paddle smoke:

```powershell
E:\MITAS\venvs\ocr\Scripts\python.exe -B -m scripts.ocr_credit_experiment `
  --manifest E:\MITAS\data\ocr_live_k2_6125_30s_manifest_20260522.json `
  --output-dir E:\MITAS\outputs\ocr_credit_experiments\k2_row_crop_ocr_paddle_smoke_20260522_b `
  --engines paddle `
  --fps 1 `
  --max-frames 10 `
  --preprocess-mode off `
  --allow-model-download
```

Sonuç:

- `row_crop_ocr.status`: `done`
- `rows_processed`: `14`
- `pair_count`: `14`
- `record_count`: `28`
- `nonempty_pair_count`: `14`
- `row_crop_ocr_sec`: `0.865`
- `total_item_sec`: `4.385`

İlk satır çıktıları:

| row | role | name |
| ---: | --- | --- |
| 1 | Uisai | ANNIE GRINDUAY |
| 2 | Toooy/ | EUENA STITEUER |
| 3 | ManonWhoelbhiai | BLU MANKUMA |
| 4 | Tony/ | CHARLES OBERMAN |
| 5 | Oindy | JULIA NICKSON-SOUL |
| 6 | Obil | CHRISTOPHER BROWN |
| 7 | Ouxiol | VÉSLIE CARUSON |
| 8 | Roton | DAVID CUBITIT |
| 9 | Duillas | LUCA BERCOVICI |
| 10 |  | EDWARD SRATT |
| 11 | Todd | ANDREW/ SPATT |
| 12 | Tekeno | HIROSHI RUUIOKA |
| 13 | Jboki | PATRICIA CHARBONNEAU |
| 14 | Clbiboino | RAYMOND JI BARRY |

Değerlendirme:

Paddle ile isim sütunu belirgin biçimde okunabilir hale geldi. Roller hala zayıf; sebep rol sütununun küçük, düşük kontrastlı ve bazen split sınırına fazla yakın olması. Yani row-crop OCR katmanı beklenen faydayı isim tarafında sağladı, rol tarafında ek iyileştirme gerekiyor.

Bir sonraki teknik ihtiyaç:

- Role/name split'i bbox/projection ile daha kararlı hale getirmek.
- Name crop için ayrı, role crop için ayrı preprocess uygulamak.
- İsimler için fuzzy dictionary veya external validation eklemek.

## OneOCR Durumu

Paddle tarafında problem/şüphe olduğu için OneOCR ayrıca kontrol edildi.

Healthcheck:

```powershell
E:\MITAS\venvs\ocr\Scripts\python.exe -B -m scripts.ocr_model_healthcheck `
  --engines oneocr `
  --output-dir E:\MITAS\outputs\ocr_model_healthcheck\oneocr_check_20260522
```

Sonuç:

- OneOCR config: `E:\MITAS\tools\oneocr`
- Gerekli dosyalar mevcut:
  - `oneocr.dll`
  - `oneocr.onemodel`
  - `onnxruntime.dll`
- Healthcheck status: `ok`
- Synthetic TR/Latin okuma:
  - `ÇAĞATAY İŞLER`
  - `MICHAEL DANTE`
  - `GÖRÜNTÜ YÖNETMENİ`
  - `DIGITAL INTERMEDIATE BY EFILM`
- Mean confidence: `0.9922`

K-2 OneOCR smoke:

```powershell
E:\MITAS\venvs\ocr\Scripts\python.exe -B -m scripts.ocr_credit_experiment `
  --manifest E:\MITAS\data\ocr_live_k2_6125_30s_manifest_20260522.json `
  --output-dir E:\MITAS\outputs\ocr_credit_experiments\k2_row_crop_ocr_oneocr_smoke_20260522 `
  --engines oneocr `
  --fps 1 `
  --max-frames 10 `
  --preprocess-mode off
```

Sonuç:

- `status`: `done`
- `frame_ocr_records`: `77`
- `row_crop_ocr.status`: `done`
- `rows_processed`: `14`
- `pair_count`: `14`
- `record_count`: `23`
- `nonempty_pair_count`: `14`
- `row_crop_ocr_sec`: `1.136`
- `total_item_sec`: `5.173`

OneOCR row çıktılarından örnekler:

| row | role | name |
| ---: | --- | --- |
| 1 | UISRI | AWNIE GRINDUAY |
| 2 | TreoDy | ELENA STITEUBR |
| 3 | Manion Wheolblinin | BLU MANKUMA |
| 4 | Tony/ | CHARLES OBERMAN |
| 5 | Cindy | JULIA NICKSON.SOUL |
| 6 |  | CHRISTORHER BROWN |
| 7 |  | UESLIE CARLSON |
| 8 |  | DAVID CUBITT |
| 9 | Dalles: | LUCA BERCOVICI |
| 10 | Mike | EDWARD SRATT |
| 13 | Jaokil | PATRICIA CHARBONNEAU |
| 14 | Claiboine | RAYMOND J BARRY |

Değerlendirme:

OneOCR teknik olarak sağlam çalışıyor. Türkçe/Latin healthcheck'te çok iyi. K-2 gerçek videoda ise tek başına Paddle'ı tamamen geçmedi; isim sütununda bazı satırlarda daha iyi, bazı satırlarda daha kötü. En değerli tarafı tamamlayıcı olması:

- OneOCR daha iyi: `DAVID CUBITT`, `Cindy`, `Mike`, `RAYMOND J BARRY`
- Paddle daha iyi: `CHRISTOPHER BROWN`, `ANNIE...`, bazı confidence değerleri

Net karar:

Paddle sorun çıkarırsa OneOCR-only koşu yapılabilir. Ama nihai mimari için en sağlıklı yol `Paddle + OneOCR row fusion`: aynı row için iki motorun name output'unu confidence ve string-benzerlik ile birleştirmek.
