# OCR Beyaz Balina Pilot Raporu - 2026-05-21

## Kisa Durum

- ASR tarafina dokunulmadi; OCR deney hatti ayri CLI/output ile duruyor.
- Deney hatti default motor listesi artik `paddle, oneocr, tesseract`.
- EasyOCR yeni karar setinden cikarildi. Eski 30 saniyelik pilotta EasyOCR da calismisti; o kosu sadece gecmis pilot bulgusu olarak degerlendirilmeli.
- Unit/smoke test: `10 passed, 1 skipped`.
- OneOCR DLL/model dosyalari `E:\MITAS\tools\oneocr` altindan calisiyor.
- Paddle henuz aktif degil: `venvs\ocr` icinde `paddle 3.3.1` CPU-only gorunuyor, `paddleocr` importu `torch\lib\shm.dll` WinError 127 ile kiriliyor. `venvs\core` icinde `paddle` yok.

## 30 Saniyelik Gercek Pilot

- Video: `\\depo01cifs.int.trt.net.tr\sas_h264\testset\filmtest\evoArcadmin_SİNEMA FİLM_2017-9031-1-0000-85-1-BEYAZ_BALİNA.mp4`
- Pencere: `01:22:40` civari baslangic (`4960` saniye), 30 saniye, `6 fps`, `180` frame.
- Output: `E:\MITAS\outputs\ocr_credit_experiments\real_beyaz_balina_pilot_4960_30s`
- Manifest: `E:\MITAS\data\ocr_real_pilot_beyaz_balina_manifest_4960.json`
- Ground truth: yok. Bu yuzden F1/precision/recall yok; sonuc kalite kaniti degil, sistem davranisi ve maliyet gozlemi.

## Pilot Sayilari

- Toplam kosu: `1178.819 sn` yaklasik `19.6 dk`.
- Raw frame OCR kaydi: `13144`
- Preprocess OCR kaydi: `26955`
- Temporal voting unique line: `4395`
- Temporal voting stable group: `1050`
- Preprocess temporal unique line: `4181`
- Preprocess temporal stable group: `1445`
- De-scroll canvas: `861 x 2147`
- Canvas OCR kaydi: `37`
- Preprocess auto tetiklendi: `low_median_confidence`
- Disk kullanimi: `212813157 byte`
- GPU gozlenen peak: `23767 / 24576 MB`

## Motor Bazli Gecmis Pilot Notu

Bu kosu EasyOCR dahilken alinmistir; yeni aday setine EasyOCR dahil degildir.

| Strateji | OneOCR sure/kayit | Tesseract sure/kayit | EasyOCR sure/kayit |
| --- | ---: | ---: | ---: |
| Frame OCR | `45.892 sn / 2427` | `53.269 sn / 5566` | `185.893 sn / 5151` |
| Preprocessed OCR | `128.166 sn / 4865` | `204.123 sn / 13073` | `403.614 sn / 9017` |
| Canvas OCR | `0.312 sn / 2` | yok | `1.347 sn / 27` |

## Hareket ve Canvas Bulgusu

- Text-mask motion ortalama hareketi: `[0.0343, -9.3116]` piksel/frame.
- Global hareket: `[0.004, -9.2948]` piksel/frame.
- Background motion warning: `false`.
- Phase quality: `pass`, mean response `0.535893`, mean peak/second-peak ratio `5.531`.
- Bu pencere pratikte dikey kayan/fade jenerik gibi davraniyor; de-scroll alignment teknik olarak tutmus gorunuyor.

## Kritik Yorum

- Full-frame ROI'siz OCR cok fazla aday uretti. Bu nedenle temporal grouping ve rapor kalabaliklasti.
- Preprocess auto tetiklendi ama ground truth olmadigi icin "daha dogru" diyemeyiz; sadece daha cok OCR adayi uretti.
- Canvas cok az OCR kaydi uretmis; bu muhtemelen motor/kanvas okunabilirligi veya kanvas crop/kontrast kararlarindan kaynaklaniyor. GT olmadan yorum sinirli.
- Paddle bu asamada kosulmadi; once venv/DLL ve tercihen GPU Paddle kurulumu cozulmeli.

## Siradaki Teknik Kilit

1. EasyOCR tamamen disarida kalacak.
2. Paddle icin temiz OCR venv karari verilecek: CPU-only mevcut kurulum onarilacak veya ayri GPU Paddle venv kurulacak.
3. Sonra ayni 30 saniyelik pencere `paddle,oneocr,tesseract` ile tekrar kosulacak.
4. ROI ve en az kisa ground truth eklenmeden bu rapor "dogruluk raporu" sayilmayacak; sadece sistem davranisi/maliyet raporu sayilacak.
