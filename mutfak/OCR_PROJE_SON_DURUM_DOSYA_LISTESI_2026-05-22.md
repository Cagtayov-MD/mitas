# OCR Proje Son Durum Dosya Listesi

Tarih: 2026-05-22

Bu paket, ASR/Tedial akışından ayrı duran OCR deney hattının güncel kodlarını ve raporlarını masaüstündeki `gpt-ocr` klasörüne taşımak için hazırlanmıştır.

## Aktif Kod Dosyaları

### Core OCR

- `core/pipelines/ocr/credit_experiment.py`
  - Ana deney hattı.
  - Manifest okur, frame çıkarır, Auto ROI uygular, OCR çalıştırır, temporal voting, router, row reconstruction, canvas ve rapor üretir.
  - Güncel ekleme: ilk OCR bbox sonuçlarından ikinci-pass rafine ROI üretir. Manifest ROI varsa dokunmaz. Bbox güveni yetersizse eski güvenli crop ile devam eder.

- `core/pipelines/ocr/credit_scene_router.py`
  - Multi-label credit scene router.
  - Arka plan, metin hareketi, layout ve zorluk profili çıkarır.

- `core/pipelines/ocr/credit_pipeline_selector.py`
  - Router profilinden önerilen pipeline adımlarını seçer.

- `core/pipelines/ocr/credit_detector.py`
  - Jenerik başlangıcı / scroll segmenti tespiti için video pencerelerini skorlar.

- `core/pipelines/ocr/text_layer_row_reconstruct.py`
  - Akan yazıdan satır odaklı composite/crop üretir.
  - Auto split ile rol/ad bölme dener.

- `core/pipelines/ocr/text_layer_descroll.py`
  - Önceki de-scroll/canvas deney hattı.

- `core/pipelines/ocr/simple.py`
  - Mevcut basit OCR dosyası; Tedial davranışı için korunuyor.

### CLI / Script

- `scripts/ocr_credit_experiment.py`
  - Tek manifest deney çalıştırıcı.

- `scripts/ocr_credit_batch_last_minutes.py`
  - Film klasörü/manifest üzerinden batch son dakika testi.

- `scripts/ocr_credit_detector.py`
  - CreditDetector CLI.

- `scripts/ocr_text_layer_row_reconstruct.py`
  - Row reconstruction CLI.

- `scripts/ocr_text_layer_descroll.py`
  - De-scroll canvas CLI.

- `scripts/ocr_model_healthcheck.py`
  - Paddle/OneOCR/Tesseract sağlık kontrolü.

### Testler

- `tests/test_ocr_credit_experiment.py`
- `tests/test_ocr_credit_detector.py`
- `tests/test_ocr_credit_scene_router.py`
- `tests/test_ocr_text_layer_row_reconstruct.py`

## Güncel Çalışma Durumu

- Paddle bozuk değil; GPU/PP-OCRv5 tarafı çalışıyor.
- OneOCR çalışıyor; sentetik sağlık testinde yüksek güven verdi.
- Auto ROI v2c gerçek jenerikte çoğunlukla güvenli center crop olarak davranıyor.
- KJ/lower-third sentetik testinde yazı bandını doğru buluyor.
- Yeni ikinci-pass ROI: önce güvenli ROI içinde OCR çalıştırır, sonra OCR bbox union ile daha dar ROI üretir. Bu kod eklendi ve unit test geçti; gerçek 18 film üzerinde henüz bu eklemeyle yeniden batch koşulmadı.
- Unicode path fix eklendi; Türkçe karakterli film/kare yollarında OpenCV okuma/yazma sorunu çözülmüştü.
- Row reconstruction 18/18 gerçek film batch’inde çalıştı; 92 nonempty row pair üretti.

## Test Sonucu

Koşulan komut:

```powershell
E:\MITAS\venvs\core\Scripts\python.exe -B -m pytest E:\MITAS\tests\test_ocr_credit_experiment.py E:\MITAS\tests\test_ocr_credit_detector.py E:\MITAS\tests\test_ocr_credit_scene_router.py E:\MITAS\tests\test_ocr_text_layer_row_reconstruct.py -q --basetemp E:\MITAS\outputs\pytest_tmp_second_pass_roi_20260522
```

Sonuç:

```text
10 passed, 12 skipped
```

Not: OCR venv içinde `pytest` kurulu olmadığı için aynı pytest paketi OCR venv’de koşulmadı.

## En Güncel Gerçek Veri Raporu

- `mutfak/OCR_FILMTEST_18_AUTO_ROI_V2C_UNICODEFIX_ONEOCR_RAPORU_2026-05-22.md`

Bu rapor ikinci-pass ROI eklenmeden önceki son geçerli 18 film raporudur. Şu an doğru sonraki adım, ikinci-pass ROI eklenmiş haliyle kısa smoke test ve ardından 18 film batch’i yeniden koşturmaktır.

