# OCR Model Kurulum ve Sağlık Raporu

Tarih: 2026-05-22

## Sonuç

Aktif OCR adayları proje içinde sabit model klasörleriyle çalışır duruma getirildi.

- PaddleOCR: çalışıyor, CPU build
- OneOCR: çalışıyor
- Tesseract: çalışıyor, `eng+tur`
- EasyOCR: aktif aday setinden çıkarıldı
- VLM fallback envanteri: Ollama tarafında mevcut

## Kurulan/Sabitlenen Model Yerleşimi

PaddleOCR:

- Det: `E:\MITAS\models\ocr\paddle\official_models\PP-OCRv5_server_det`
- Rec: `E:\MITAS\models\ocr\paddle\official_models\latin_PP-OCRv5_mobile_rec`
- Ek rec: `E:\MITAS\models\ocr\paddle\official_models\en_PP-OCRv5_mobile_rec`

OneOCR:

- Runtime/model: `E:\MITAS\tools\oneocr`
- Ana dosyalar: `oneocr.dll`, `oneocr.onemodel`, `onnxruntime.dll`

Tesseract:

- Binary: `C:\Program Files\Tesseract-OCR\tesseract.exe`
- Tessdata: `E:\MITAS\models\ocr\tesseract\tessdata`
- Diller: `eng`, `osd`, `tur`

VLM/Ollama envanteri:

- `qwen2.5vl:7b`
- `llama3.2-vision:11b`
- `minicpm-v:latest`
- `moondream:latest`
- `qwen3.6:35b-a3b`
- `gemma4:e4b`
- `qwen3:8b`

## Kod Tarafı

Güncellenen/eklenen dosyalar:

- `E:\MITAS\core\pipelines\ocr\credit_experiment.py`
- `E:\MITAS\scripts\ocr_model_healthcheck.py`
- `E:\MITAS\requirements\ocr.txt`

Yapılanlar:

- Paddle adapter varsayılan olarak proje içindeki PP-OCRv5 modellerini kullanıyor.
- Paddle model isimleri açık şekilde sabitlendi: `PP-OCRv5_server_det` + `latin_PP-OCRv5_mobile_rec`.
- Paddle venv içindeki eksik paket dosyaları aynı venv'deki `~addle` yedeğinden tamamlandı.
- Tesseract adapter proje içindeki tessdata klasörünü kullanıyor.
- Tesseract varsayılan dil seçimi `eng+tur` oldu.
- OneOCR engine status raporuna model/config yolu eklendi.
- Sağlık kontrol script'i eklendi.

## Sağlık Testi

Komut:

```powershell
E:\MITAS\venvs\ocr\Scripts\python.exe -m scripts.ocr_model_healthcheck --output-dir E:\MITAS\outputs\ocr_model_healthcheck\active_20260522_v3 --engines paddle,oneocr,tesseract --include-vlm
```

Rapor:

- `E:\MITAS\outputs\ocr_model_healthcheck\active_20260522_v3\ocr_model_healthcheck.md`
- `E:\MITAS\outputs\ocr_model_healthcheck\active_20260522_v3\ocr_model_healthcheck.json`

Sentetik Türkçe/Latin OCR sonucu:

| Motor | Durum | Kayıt | Ortalama Güven | Örnek çıktı |
| --- | --- | ---: | ---: | --- |
| PaddleOCR | OK | 4 | 0.9947 | `ÇAĞATAY İŞLER`, `MICHAEL DANTE`, `GÖRÜNTÜ YÖNETMENİ`, `DIGITAL INTERMEDIATE BY EFILM` |
| OneOCR | OK | 4 | 0.9922 | `ÇAĞATAY İŞLER`, `MICHAEL DANTE`, `GÖRÜNTÜ YÖNETMENİ`, `DIGITAL INTERMEDIATE BY EFILM` |
| Tesseract | OK | 10 | 0.9430 | Kelime bazlı çıktı: `ÇAĞATAY`, `İŞLER`, `MICHAEL`, `DANTE`, ... |

## Unit Test

İlk deneme Windows temp klasörü doluluğu nedeniyle başarısız oldu. Temiz `--basetemp` ile tekrar koşuldu.

```powershell
E:\MITAS\venvs\core\Scripts\python.exe -m pytest E:\MITAS\tests\test_ocr_simple_pipeline.py E:\MITAS\tests\test_ocr_credit_experiment.py -q --basetemp E:\MITAS\outputs\pytest_tmp_ocr_health_20260522_1411
```

Sonuç:

```text
10 passed, 1 skipped
```

OCR venv bağımlılık kontrolü:

```text
No broken requirements found.
```

## Gerçek Video Smoke

Kalite testi değil; sadece gerçek video erişimi, ffmpeg frame çıkarma, üç OCR motoru ve rapor zinciri doğrulandı.

Komut:

```powershell
E:\MITAS\venvs\ocr\Scripts\python.exe -m scripts.ocr_credit_experiment --manifest E:\MITAS\data\ocr_real_pilot_beyaz_balina_manifest_4960.json --output-dir E:\MITAS\outputs\ocr_credit_experiments\model_health_real_smoke_20260522 --engines paddle,oneocr,tesseract --fps 1 --max-frames 1 --preprocess-mode off
```

Sonuç:

- Runtime: 17.695 sn
- Engines: PaddleOCR OK, OneOCR OK, Tesseract OK
- Frames: 1
- Frame OCR records: 3
- Canvas OCR records: 3
- Rapor: `E:\MITAS\outputs\ocr_credit_experiments\model_health_real_smoke_20260522\run_report.md`

Motor süreleri, tek kare:

| Motor | Süre | Kayıt |
| --- | ---: | ---: |
| PaddleOCR | 5.749 sn | 1 |
| OneOCR | 0.189 sn | 2 |
| Tesseract | 0.344 sn | 0 |

## Notlar

- Paddle şu anda CPU build olarak çalışıyor: `cuda False`.
- GPU Paddle kurulumuna dokunulmadı; çalışan CPU OCR venv'i bozulmasın diye ayrı ele alınmalı.
- Bu rapor model/engine sağlık raporudur. Jenerik okuma kalitesini ölçecek gerçek video v2 tracking testi ayrı koşulmalıdır.
