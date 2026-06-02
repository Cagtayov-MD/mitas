# OCR Güncel Takip ve Aday Seçici Planı

Tarih: 2026-05-22

## İsimlendirme Kararı

Bundan sonra OCR hattı ile ilgili çalışma notları `mutfak` altında `OCR_...` dosyaları olarak tutulacak.

`gpt-ocr` ifadesi rapor başlığı veya takip adı olarak kullanılmayacak. Masaüstündeki klasör sadece kopya/aktarım klasörü kabul edilecek; asıl proje `E:\MITAS` içindedir.

## Neden Candidate Selector Gerekiyor?

Son testlerde gördüğümüz ana ders:

- Tek bir algoritmayı ana hatta koymak riskli.
- Bazı fikirler belirli kliplerde iyi, bazı kliplerde kötü çalışıyor.
- `cruise_speed EMA` bunun örneği oldu: fikir değerli ama direkt ana algoritma yapılınca 18 filmde row çıktısını düşürdü.
- Text-mask ROI de aynı şekilde agresif kullanıldığında bazı filmlerde zarar verdi.

Bu yüzden doğru mimari:

1. Birden fazla aday üret.
2. Her adayı küçük ve ucuz metriklerle puanla.
3. En iyi adayı seç.
4. Hangi adayın neden seçildiğini rapora yaz.

## Adaylar

### ROI Adayları

- `safe_auto_roi`: Mevcut güvenli auto ROI.
- `ocr_bbox_second_pass_roi`: İlk OCR bbox'larından rafine ROI.
- `text_mask_track_roi`: OCR bbox yoksa veya zayıfsa text-mask track fallback.
- `full_frame`: Son çare / karşılaştırma adayı.

### Row Reconstruction Adayları

- `current_displacement`: Şu anki ana displacement yöntemi.
- `static_best_frame`: Displacement range düşükse en iyi frame seçimi.
- `cruise_speed_ema`: Claude/tools'tan gelen EMA + deviant reset yöntemi, ana algoritma değil aday olarak.

## Puanlama

İlk MVP puanı şu sinyallerden oluşacak:

- `quality_score`: Composite keskinlik, kontrast ve text density.
- `row_count`: Bulunan satır sayısı.
- `nonempty_role_name_count`: Role/name crop OCR sonrası boş olmayan çift sayısı.
- `ocr_confidence_mean`: Ortalama OCR güveni.
- `noise_penalty`: Çok kısa, anlamsız veya aşırı parçalı satır cezası.
- `roi_area_penalty`: Çok büyük/tüm frame ROI cezası.

Başlangıçta ground truth olmadığı için bu metrikler "doğru okudu" demeye yetmez; sadece adaylar arasında daha sağlıklı görünen hattı seçer.

## Uygulama Sırası

1. `text_layer_row_reconstruct.py` içinde row reconstruction adaylarını ayrı ayrı çalıştırabilecek küçük bir aday arayüzü ekle.
2. Her aday için `summary`, `quality`, `row_count`, `nonempty_count` üret.
3. En iyi adayı seçen `select_best_row_candidate()` fonksiyonunu ekle.
4. Seçilen aday ve reddedilen adayları JSON/Markdown rapora yaz.
5. Aynı mantığı sonra ROI tarafına genişlet: safe ROI, OCR bbox ROI, mask-track ROI yarışsın.
6. 18 film batch'i tekrar koş ve önceki güvenli birleşim ile karşılaştır.

## Başarı Kriteri

İlk aşamada amaç:

- Mevcut güvenli birleşimi bozmamak.
- Cruise-speed gibi riskli algoritmaları tamamen çöpe atmadan kontrollü aday yapmak.
- Kötü adayın ana çıktıyı bozmasını engellemek.
- Raporlarda "neden bu yol seçildi?" sorusuna cevap vermek.

Minimum kabul:

- 18 film batch'inde `row_records` ve `nonempty` baseline altına düşmemeli.
- `quality_warning` sayısı artmamalı.
- Seçici, cruise-speed'i sadece gerçekten faydalı olduğu kliplerde seçmeli.

## Sonraki Not

Bu iş bir "merge" işi değil; kalite artırma işi. Birleşim tamamlandı, sıradaki faz aday seçici ve gerçek doğruluk ölçümü.

## Uygulama Notu 1 - Row Candidate Selector

Durum: İlk MVP eklendi.

Dosya:

- `E:\MITAS\core\pipelines\ocr\text_layer_row_reconstruct.py`

Eklenen adaylar:

- `current_displacement`
- `static_best_frame`
- `cruise_speed_ema`

Çıktılar:

- Seçilen aday `row_reconstruct_summary.json` içinde `candidate_selector.selected` alanına yazılıyor.
- Tüm adayların `score`, `quality`, `row_count`, `auto_split`, `motion` bilgileri aynı summary içinde tutuluyor.
- Aday composite görselleri `text_layer_row_reconstruct\row_candidates\` altına yazılıyor.

Seçim politikası:

- En yüksek skorlu aday seçilir.
- Ama mevcut güvenli yol olan `current_displacement` lehine küçük bir güvenlik marjı vardır.
- Alternatif aday, current yolunu en az `0.06` puan geçmezse ana çıktıyı devralmaz.

Neden?

- `cruise_speed_ema` daha önce direkt ana algoritma yapılınca 18 filmde çıktıyı düşürmüştü.
- Bu yüzden artık direkt replacement değil, kontrollü aday.

### Sentetik Smoke

Çıktı:

- `E:\MITAS\outputs\row_candidate_selector_smoke_20260522`

Sonuç:

| Candidate | Score | Rows | Quality | Motion |
| --- | ---: | ---: | ---: | --- |
| current_displacement | 0.8536 | 8 | 1.0 | ok |
| static_best_frame | 0.7818 | 8 | 1.0 | static_best_frame |
| cruise_speed_ema | 0.8241 | 8 | 1.0 | ok |

Seçilen:

- `current_displacement`

Yorum:

- Adaylar üretildi.
- Cruise-speed aday olarak çalıştı.
- Ana hattı gereksiz devralmadı.

### Gerçek K-2 30 sn Smoke

Çıktı:

- `E:\MITAS\outputs\ocr_credit_experiments\k2_30s_candidate_selector_smoke_20260522`

Run:

- Engine: `oneocr`
- Segment: K-2, 01:42:05 sonrası 30 sn
- Status: `done`
- Frame OCR records: `688`
- Stable groups: `88`
- Canvas records: `32`

Row candidate sonucu:

| Candidate | Selected | Score | Rows | Quality | Motion |
| --- | --- | ---: | ---: | ---: | --- |
| current_displacement | yes | 0.8151 | 14 | 0.985 | static_or_low_scroll |
| static_best_frame | no | 0.7851 | 14 | 0.985 | static_best_frame |
| cruise_speed_ema | no | 0.7851 | 14 | 0.985 | static_or_low_scroll |

Seçilen:

- `current_displacement`

Yorum:

- Gerçek veri smoke testinde candidate selector beklenen faydayı sağladı: alternatifleri ölçtü ama güvenli hattı bozmadı.
- `cruise_speed_ema` sisteme geri döndü ama ana algoritmayı otomatik ezmiyor.
- Bu ilk sürüm doğruluk artırmaktan çok regresyon riskini azaltan kontrol katmanı olarak başarılı.

## Sonraki Teknik Adım

Sıradaki faz ROI tarafında aynı mantığı kurmak:

- `safe_auto_roi`
- `ocr_bbox_second_pass_roi`
- `text_mask_track_roi`
- `full_frame`

Bu adaylar küçük OCR/quality skorlarıyla yarıştırılacak. Böylece text-mask ROI sadece fallback değil, gerektiğinde ölçülerek seçilebilen aday olacak.
