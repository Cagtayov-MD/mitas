# OCR Text-mask Track Second-pass ROI Raporu

Tarih: 2026-05-22

Bu rapor, OCR bbox tabanlı second-pass ROI'ye eklenen text-mask/track fallback denemesinin sonucunu özetler.

## Amaç

Önceki second-pass ROI sadece OCR bbox'larına dayanıyordu.

Bu iyi çalışıyor ama bir açığı var:

- OCR hiç okuyamazsa bbox oluşmaz.
- Bbox oluşmazsa second-pass ROI de oluşmaz.

Bu yüzden şu ek katman denendi:

> OCR bbox yetersizse, güvenli crop içindeki yazı benzeri piksellerin zaman içi yoğunluğundan ROI çıkar.

## Eklenen Mantık

Dosya:

- `core/pipelines/ocr/credit_experiment.py`

Yeni fonksiyonlar:

- `_infer_mask_track_second_pass_roi_info`
- `_mask_track_skip`

Davranış:

1. Önce OCR bbox second-pass denenir.
2. OCR bbox sayısı yetersizse text-mask/track fallback devreye girer.
3. Text-like mask frame'ler boyunca toplanır.
4. Dikey scroll için Y ekseni geniş bırakılır, X ekseni rafine edilir.
5. ROI çok geniş, çok küçük veya mask density aşırı ise uygulanmaz.

## İlk Agresif Deneme

İlk sürümde mask-track fallback, OCR bbox union çok geniş olduğunda da devreye giriyordu.

Bu sentetik testte iyi göründü ama gerçek 18 film batch'inde zarar verdi.

Özellikle:

| Film | Eski Row Records | Agresif Mask Row Records | Eski Nonempty | Agresif Nonempty |
| --- | ---: | ---: | ---: | ---: |
| ÖFKE (FURY) | 104 | 20 | 21 | 4 |

Sonuç:

> Text-mask fallback, OCR zaten bol veri üretiyorken onun yerine geçmemeli.

Bu önemli bir bulguydu. Modülün varlığı doğru, ama kapısı fazla gevşekti.

## Yapılan Düzeltme

Kapı konservatif hale getirildi.

Yeni kural:

- OCR bbox gerçekten yetersizse text-mask fallback çalışabilir.
- OCR bbox çok geniş ama bbox sayısı ve frame sayısı yeterliyse text-mask override yapmaz.

Kod mantığı:

```python
if bbox_union_too_broad:
    if len(boxes) < 16 or frame_count < 4:
        try_text_mask_track()
    else:
        skip_text_mask_track("ocr_boxes_sufficient_do_not_override")
```

Yani text-mask artık ana yol değil, güvenli fallback.

## Testler

Core test:

```text
10 passed, 13 skipped
```

OCR venv inline smoke:

- OCR bbox sıfır verildi.
- Sentetik kayan yazı frame'leri üretildi.
- Text-mask fallback ROI üretti.

Sonuç:

```json
{
  "status": "detected",
  "strategy": "text_mask_track_second_pass",
  "roi": [190, 0, 235, 360],
  "confidence": 0.7268
}
```

Bu, OCR hiç okuyamasa bile fallback'in teknik olarak çalıştığını gösterdi.

## K-2 Smoke

Manifest:

- `E:\MITAS\data\ocr_live_k2_6125_30s_manifest_20260522.json`

Output:

- `E:\MITAS\outputs\ocr_credit_experiments\k2_30s_mask_track_conservative_smoke_20260522`

Sonuç:

- K-2'de OCR bbox yolu yeterli olduğu için text-mask fallback devreye girmedi.
- Seçilen strateji: `ocr_bbox_second_pass`
- Applied ROI: `[86,19,447,442]`
- First-pass OCR records: `121`
- Final OCR records: `105`
- Stable groups: `18`
- Row count: `14`
- Nonempty row pairs: `14`

Yorum:

- K-2 sonucu bozulmadı.
- Doğru davranış bu: OCR bbox yeterliyse mask-track zorla üstüne binmiyor.

## 18 Film Karşılaştırması

Üç koşu karşılaştırıldı:

| Run | Auto Refined | OCR Bbox | Mask Track | Frame OCR | Stable | Row Records | Nonempty Pairs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| OCR bbox second-pass | 4 | 4 | 0 | 5316 | 738 | 334 | 97 |
| Agresif mask-track | 8 | 4 | 4 | 5270 | 728 | 251 | 79 |
| Konservatif mask-track | 4 | 4 | 0 | 5316 | 738 | 334 | 97 |

Sonuç:

- Agresif mask-track gerçek veride zararlıydı.
- Konservatif kapı zararı sıfırladı.
- Bu 18 film setinde mask-track aktif katkı üretmedi çünkü OCR bbox zaten yeterli olan yerlerde override etmedi, OCR'ın tamamen boş olduğu yerlerde ise text-mask de güvenilir ROI bulacak kadar kuvvetli değildi.

## Dürüst Değerlendirme

Bu adımın sonucu:

- Mimari olarak doğru.
- Sentetik ve kontrollü durumda çalışıyor.
- Gerçek batch'te agresif kullanımı zararlı.
- Konservatif fallback olarak güvenli.
- 18 film setinde ölçülebilir artış üretmedi.

Bu yüzden nihai karar:

> Text-mask track second-pass ROI sistemde kalmalı ama sadece düşük OCR/bbox durumunda fallback olarak çalışmalı. Ana ROI kararını OCR bbox bozacak şekilde override etmemeli.

## Sıradaki Daha Doğru Hamle

Bu sonuç bize şunu gösterdi:

Text-mask tek başına fazla kaba. Daha iyi yol:

1. OCR bbox yeterliyse OCR bbox ROI.
2. OCR bbox yoksa text-mask ROI.
3. İkisi çelişirse hemen crop uygulamak yerine A/B mini-run:
   - güvenli ROI'de OCR
   - mask ROI'de OCR
   - hangisi daha çok stabil satır / daha yüksek güven / daha düşük gürültü veriyorsa onu seç.

Buna `ROI candidate A/B selector` diyebiliriz.

Bu, körlemesine ROI seçmekten daha sağlam olur.

