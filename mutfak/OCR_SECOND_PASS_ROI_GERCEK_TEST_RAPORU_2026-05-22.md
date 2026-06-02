# OCR Second-pass ROI Gerçek Test Raporu

Tarih: 2026-05-22

Bu rapor, Auto ROI sonrası OCR bbox'larından ikinci-pass ROI rafine etme denemesinin gerçek video sonuçlarını özetler.

## Neyi Ekledik?

`core/pipelines/ocr/credit_experiment.py` içine ikinci-pass ROI adımı eklendi.

Akış artık şöyle:

1. Manifest ROI varsa onu kullanır.
2. Manifest ROI yoksa önce Auto ROI / güvenli crop uygular.
3. Güvenli crop içinde ilk `frame_ocr` çalışır.
4. OCR bbox'ları analiz edilir.
5. Bbox'lar güvenilir ve anlamlı bir alan gösteriyorsa ikinci crop uygulanır.
6. Router ve frame OCR rafine ROI üzerinde yeniden çalışır.
7. İlk geçiş `frame_ocr_first_pass.json` olarak saklanır.

Yeni dosyalar:

- `refined_auto_roi_detection.json`
- `frame_ocr_first_pass.json`
- `scene_router_after_refined_roi.json`

## İlk Smoke: K-2 30 Saniye

Manifest:

- `E:\MITAS\data\ocr_live_k2_6125_30s_manifest_20260522.json`

Komut:

```powershell
E:\MITAS\venvs\ocr\Scripts\python.exe -B -m scripts.ocr_credit_experiment `
  --manifest E:\MITAS\data\ocr_live_k2_6125_30s_manifest_20260522.json `
  --output-dir E:\MITAS\outputs\ocr_credit_experiments\k2_30s_second_pass_roi_scrollfix_smoke_20260522 `
  --engines oneocr `
  --fps 1 `
  --max-frames 12 `
  --preprocess-mode off
```

### İlk Deneme Ne Gösterdi?

İlk yazdığımız ikinci-pass ROI kalite kapısı K-2'de çalıştı ama ROI uygulamadı.

Sebep:

- `bbox_union_too_broad`

Bunu incelediğimizde şunu gördük:

- Bbox'lar yatayda merkeze yakın.
- Ama dikey kayan jenerikte satırlar doğal olarak tüm yükseklik boyunca görünüyor.
- Eski kalite kapısı "Y ekseni tüm frame'i kapladı" diye bunu kötü sanıyordu.

### Düzeltme

Scroll benzeri jeneriklerde ikinci-pass ROI mantığı değiştirildi:

- Y ekseni geniş kalabilir.
- Asıl rafine edilecek eksen X eksenidir.
- X sınırı min/max yerine robust quantile ile hesaplanır.

Eklenen yardımcı:

- `_quantile`

### Düzeltilmiş K-2 Sonucu

Güvenli Auto ROI:

```json
[42, 19, 516, 442]
```

Second-pass refined ROI:

```json
[44, 0, 447, 442]
```

Final applied ROI:

```json
[86, 19, 447, 442]
```

Yorum:

- Yatayda yaklaşık %13 daralma sağladı.
- İlk OCR kayıt sayısı: `121`
- Rafine ROI sonrası OCR kayıt sayısı: `105`
- Stable groups: `18`
- Row count: `14`
- Nonempty row pairs: `14`

Row OCR örnekleri:

- `CHARLES OBERMAN`
- `JULIA NICKSON- SOUL`
- `CHRISTORHER BROWN`
- `DAVAD CUBITT`
- `LUCA BERCOVICI`
- `PATRICIA CHARBONNEAU`
- `RAYMOND J. BARRY`

Değerlendirme:

- ROI daraltma çalıştı.
- Gürültü bir miktar azaldı.
- İsim okuma hâlâ OCR hataları taşıyor.
- Rol sütunu hâlâ zayıf.
- Fayda var ama dramatik değil; K-2 zaten güvenli crop içinde nispeten temizdi.

## 18 Film Batch

Manifest:

- `E:\MITAS\data\ocr_filmtest_last3min_manifest_20260522.json`

Output:

- `E:\MITAS\outputs\ocr_credit_experiments\filmtest_last3min_second_pass_roi_oneocr_20260522`

Komut:

```powershell
E:\MITAS\venvs\ocr\Scripts\python.exe -B -m scripts.ocr_credit_batch_last_minutes `
  --manifest E:\MITAS\data\ocr_filmtest_last3min_manifest_20260522.json `
  --output-dir E:\MITAS\outputs\ocr_credit_experiments\filmtest_last3min_second_pass_roi_oneocr_20260522 `
  --engines oneocr `
  --fps 1 `
  --max-frames 30 `
  --preprocess-mode off `
  --allow-model-download
```

Batch sonucu:

- Items: `18/18`
- Failed: `0`
- Done: `13`
- Partial: `5`
- Runtime toplam: yaklaşık `209.3 sn`

Toplam metrikler:

- Final frame OCR records: `5316`
- Stable groups: `738`
- Row OCR records: `334`
- Nonempty row pairs: `97`

Önceki geçerli OneOCR v2c batch ile kıyas:

| Metrik | v2c Unicodefix | Second-pass ROI |
| --- | ---: | ---: |
| Frame OCR records | 5308 | 5316 |
| Stable groups | 741 | 738 |
| Row OCR records | 307 | 334 |
| Nonempty row pairs | 92 | 97 |

Yorum:

- Toplam OCR record sayısı hemen hemen aynı.
- Stable group sayısı hemen hemen aynı.
- Row OCR tarafında küçük artış var: `307 -> 334`.
- Nonempty row pair sayısı küçük arttı: `92 -> 97`.
- Bu, ikinci-pass ROI'nin şu haliyle küçük ama ölçülebilir fayda verdiğini gösteriyor.

## Hangi Filmlerde Refined ROI Devreye Girdi?

Second-pass ROI 18 filmden 4'ünde uygulandı:

| Film | Auto ROI | Refined ROI | İlk OCR | Final OCR | Stable | Row | Nonempty |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| BABA_3 | `[35,11,442,266]` | `[27,0,383,266]` | 659 | 660 | 95 | 10 | 4 |
| MACARLAR | `[59,19,736,442]` | `[222,0,304,442]` | 18 | 16 | 4 | 5 | 2 |
| FIRTINANIN_ICINDE | `[59,19,736,442]` | `[125,0,475,442]` | 1223 | 1235 | 143 | 23 | 19 |
| MEHMED_FETIHLER_SULTANI | `[89,28,1102,664]` | `[60,393,914,237]` | 4 | 1 | 0 | 5 | 0 |

Yorum:

- `BABA_3`, `MACARLAR`, `FIRTINANIN_ICINDE` için second-pass ROI mantıklı davrandı.
- `MEHMED_FETIHLER_SULTANI` için ROI daralttı ama OCR açısından fayda üretmedi; bu klip muhtemelen gerçek akan jenerik değil veya text density/scene karmaşası farklı.

## Unicode Path Warning Düzeltmesi

18 film batch sırasında terminalde çok fazla OpenCV uyarısı görüldü.

Sebep:

- Bazı Unicode-safe okuma fonksiyonları önce `cv2.imread` deniyor, sonra fallback'e düşüyordu.
- Türkçe path'lerde `cv2.imread` warning basıyor ama fallback okuyordu.

Düzeltme:

- Önce `np.fromfile + cv2.imdecode`
- En son çare olarak `cv2.imread`

Güncellenen dosyalar:

- `core/pipelines/ocr/credit_experiment.py`
- `core/pipelines/ocr/text_layer_row_reconstruct.py`
- `core/pipelines/ocr/credit_scene_router.py`
- `core/pipelines/ocr/credit_detector.py`

Kontrol:

- `SİYAH_KADİFE_ELBİSE` path'li kısa smoke warning basmadan tamamlandı.

## Testler

Core test:

```powershell
E:\MITAS\venvs\core\Scripts\python.exe -B -m pytest `
  E:\MITAS\tests\test_ocr_credit_experiment.py `
  E:\MITAS\tests\test_ocr_credit_detector.py `
  E:\MITAS\tests\test_ocr_credit_scene_router.py `
  E:\MITAS\tests\test_ocr_text_layer_row_reconstruct.py `
  -q
```

Sonuç:

```text
10 passed, 12 skipped
```

## Dürüst Değerlendirme

Second-pass ROI beklediğimiz vaadi kısmen yerine getirdi:

- Evet, OCR bbox'tan ROI rafine edebiliyor.
- Evet, K-2 smoke'ta güvenli crop'u daralttı.
- Evet, 18 filmde 4 örnekte devreye girdi.
- Evet, row OCR toplamında küçük artış sağladı.

Ama:

- Tüm filmlerde dramatik kalite artışı yok.
- Bazı kliplerde güvenli crop zaten yeterince dar.
- Bazı kliplerde ilk OCR bbox sayısı sıfır veya yetersiz olduğu için rafine edilecek veri yok.
- Rol-isim parser ve OCR karakter doğruluğu hâlâ ana darboğaz.

Net sonuç:

> Bu adım doğru mimari yönde, ama tek başına problemi çözmüyor. Faydası gerçek ama sınırlı. Sıradaki daha etkili adım, OCR bbox ROI'yi sadece frame OCR'dan değil, text detection/text mask track'lerinden de beslemek ve KJ/lower-third gerçek örnekleriyle test etmek.

