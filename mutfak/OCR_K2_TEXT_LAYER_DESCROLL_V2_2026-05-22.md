# K-2 Text-Layer De-scroll v2 Denemesi

Tarih: 2026-05-22

## Ne Denendi

V1 full-frame panorama yerine mevcut OCR bbox kayıtlarından text-layer de-scroll denendi.

Girdi:

- Item: `E:\MITAS\outputs\ocr_credit_experiments\live_k2_6125_30s_20260522\items\k2_end_credits_live_6125_30s`
- Motor: PaddleOCR GPU
- Kaynak: 30 sn, 2 fps, 60 frame
- Input OCR record: 1143
- Input temporal group: 351

Çıktı:

- Loose track: 91
- Strict track: 43
- Tahmini scroll: yukarı, `-60.167 px/sn`

## Üretilen Dosyalar

- Strict text-layer canvas: `E:\MITAS\outputs\ocr_credit_experiments\live_k2_6125_30s_20260522\items\k2_end_credits_live_6125_30s\text_layer_descroll_v2\text_layer_canvas_strict.png`
- Loose text-layer canvas: `E:\MITAS\outputs\ocr_credit_experiments\live_k2_6125_30s_20260522\items\k2_end_credits_live_6125_30s\text_layer_descroll_v2\text_layer_canvas_loose.png`
- Rendered ordered text: `E:\MITAS\outputs\ocr_credit_experiments\live_k2_6125_30s_20260522\items\k2_end_credits_live_6125_30s\text_layer_descroll_v2\ordered_text_render.png`
- Ordered text: `E:\MITAS\outputs\ocr_credit_experiments\live_k2_6125_30s_20260522\items\k2_end_credits_live_6125_30s\text_layer_descroll_v2\ordered_credits_candidates.txt`
- JSON summary: `E:\MITAS\outputs\ocr_credit_experiments\live_k2_6125_30s_20260522\items\k2_end_credits_live_6125_30s\text_layer_descroll_v2\text_layer_descroll_summary.json`

## Değerlendirme

Bu çıktı v1 canvas'a göre açıkça daha doğru yönde:

- Arka plan artık tam frame olarak taşınmıyor.
- Satırlar track bazında ayrılıyor.
- Aynı isimlerin tekrarları büyük ölçüde tekilleşiyor.
- Okunabilir bir ordered candidate list oluşuyor.
- Scroll yönü ve hızı metin track'lerinden hesaplanıyor.

Ama final başarı değil:

- Crop maskesi hâlâ yer yer arka plan parçaları taşıyor.
- Rol/isim eşleştirme henüz yok.
- OCR hataları hâlâ listede: `DAVID AUEXANDER`, `MEAGAN ROUTUBY`, `MICHAEL UANGUOIS`, `BARRY BUANCHARD`.
- Bazı rol satırları isim listesine karışıyor: örn. `Tony`.
- Bu çıktı temiz ground-truth jenerik değil, v2 tracking/fusion prototipi.

## Strict Aday Liste

```text
MICHAEL BIEHN
MATT CRAVEN
ANNIE GRINDLAY
ELENA STITELER
BLU MANKUMA
CHARLES OBERMAN
Tony
JULIA NICKSON SOUL
CHRISTOPHER BROWN
LESLIE CARLSON
DAVID CUBITT
LUCA BERCOVICI
EDWARD SPATT
ANDREW/SPATT
HIROSHI FUJIOKA
PATRICIA CHARBONNEAU
RAYMOND J. BARRY
ANTONY HOLLAND
KEHLI O'BYRNE
LILLIAN CARUSON
LAURIE BRISCOE
JAMAL SHAH
BADI UZZAMAN
RAJAB SHAH
IBRAHMIM ZAHID
AUIKA
ABDUL KARIM
GHULAM ABBAS
ASGHAR KHAN
MR SHABAN
NAZIR SABIR
SHAH JEHAN
HADUI MEJDI
MICHAEL UANGUOIS
JI JI MAKARO
MARK AISBETT
LOU BOLLO
BRUCE KAY
TOM HERBERT
BARRY BUANCHARD
DAVID AUEXANDER
DAVE DUNAWAY
MEAGAN ROUTUBY
```

## Sonuç

Vaat edilen yöndeki asıl iş bu: full-frame panorama değil, text-layer tracking.

Bu deneme ilk kez "akan jenerikten metin satırlarını ayrı bir uzun şeride alma" işini yaptı. Görsel olarak v1'den çok daha iyi, ama nihai sistem için sıradaki düzeltmeler gerekiyor:

1. Daha temiz text maskesi.
2. Rol/isim çiftlerini birlikte track etme.
3. Paddle + OneOCR voting ile hata düzeltme.
4. Düşük güvenli/şüpheli satırları VLM veya ikinci OCR pass'e gönderme.
5. Ground truth ile CER/F1 ölçme.
