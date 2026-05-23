# OCR K-2 Opus Karşılaştırma ve Regresyon Notu

Tarih: 2026-05-22

## Durum

Kullanıcının verdiği Opus çıktısı, K-2 filmi için bizim son `filmtest_10_last3min_candidate_selector_20260522` çıktımızdan belirgin şekilde daha iyi görünüyor.

K-2 dosyası:

- `evoArcadmin_COZUMLEMEV2S17_1991-0339-1-0000-01-1-K-2.mp4`

Bizim son çıktı:

- `E:\MITAS\mutfak\OCR_10_FILM_GERCEK_TEST_GORSELLER_2026-05-22\03_filmtest_03_evoArcadmin_COZUMLEMEV2S17_1991-0339-1-0000-01-1-K-2`

Opus görseli:

- Uzun, siyah zeminli, okunabilir role/name jenerik panosu.
- Metin çizgileri daha düzgün.
- Background/sahne parçaları daha az kirletiyor.

Bizim görseller:

- `01_selected_row_composite.png`: kısmi, sahneyle kirlenmiş, yatay bozulmalar var.
- `03_descroll_canvas.png`: uzun ama ghosting/üst üste binme ağır; pano güvenilir değil.

## Net Yargı

Bu örnekte bizim son yolumuz Opus çıktısına göre gerilemiş durumda.

Sorun OCR motorundan önce geliyor:

- ROI / frame seçim / stitching / row reconstruction yolu doğru pano üretmiyor.
- `descroll_canvas` kalite kapısı yanlış pozitif veriyor.
- `row_candidate_selector` görüntü kalitesini ve row sayısını ödüllendiriyor ama "gerçek uzun jenerik panosu mu?" sorusunu yeterince ölçmüyor.

## Bizim K-2 Metrikleri

`item_summary.json`:

- `text_motion`: `vertical_scroll`
- `roi_strategy`: `auto_refined`
- `frame_ocr_records`: `25009`
- `temporal_stable_groups`: `1930`
- `row_count`: `21`
- `canvas_ocr_records`: `231`

`row_reconstruct.json`:

- selected candidate: `current_displacement`
- score: `0.9372`
- quality: `1.0`
- row_count: `21`
- split_x: `192`
- split confidence: `0.5811`
- motion: `ok`
- displacement range: `605.1212`

Bu metrikler dışarıdan iyi görünüyor ama görsel kalite gerçekte kötü. Demek ki skor formülü eksik.

`descroll_canvas.json`:

- phase quality: `pass`
- mean response: `0.664587`
- peak/second-peak: `4.0798`
- canvas OCR records: `231`

Bu da yanlış pozitif. Phase correlation tek başına pano kalitesini kanıtlamıyor.

## Neden Yanlış Yoldayız?

### 1. Full-frame / geniş ROI stitching hâlâ kirli

Arka plan ve geçişler metin hareketine karışıyor. Pano uzun olsa bile metin üst üste biniyor.

### 2. Row reconstruction kısa/kısmi kalıyor

Bizim row composite, Opus gibi tam uzun jenerik panosu değil. Daha çok seçilmiş kısa bir parça gibi davranıyor.

### 3. Candidate selector yanlış şeyi ödüllendiriyor

Şu an ödül:

- quality score
- row count
- split confidence
- motion status

Eksik ödül/ceza:

- long credit coverage
- duplicate/ghosting penalty
- OCR text uniqueness vs repeated-overlap oranı
- background contamination penalty
- visual dark-column/text-column sanity
- role/name column continuity

### 4. Canvas kalite kapısı anlamsal değil

Phase pass olsa bile görsel pano çöp olabiliyor. OCR output'ta aynı kelime/rol çok fazla tekrarlanıyorsa canvas fail olmalı.

## Hemen Alınacak Karar

10 film batch, bu sorun çözülmeden körlemesine devam ettirilmemeli.

Alınan aksiyon:

- `filmtest_10_last3min_candidate_selector_20260522` batch süreci durduruldu.

## Düzeltme Yönü

### A. Opus/scroll_reconstructor yaklaşımı ayrı aday olarak taşınmalı

`cruise_speed_ema` tek başına yeterli değil. Opus çıktısındaki asıl fark muhtemelen:

- daha dar aktif metin bölgesi,
- daha iyi active frame seçimi,
- sabit hız / scroll band yaklaşımı,
- background/sahne parçalarını dışarıda tutma,
- pano üretiminde daha sıkı maskeleme.

Bu yüzden "Opus-style scroll reconstructor" ayrı bir candidate olmalı:

- `opus_scroll_reconstructor_candidate`

### B. Canvas invalidation eklenmeli

Canvas şu durumlarda ana rapordan düşmeli:

- aşırı ghosting,
- aynı kelimenin yüzlerce tekrarı,
- text density aşırı yüksek,
- canvas OCR unique line / frame temporal unique line oranı çok düşük,
- görselin büyük bölümü beyaz/patlak metin duvarı,
- background contamination yüksek.

### C. Primary output yeniden seçilmeli

K-2 gibi örneklerde primary görsel:

- Opus-style long panel başarılıysa o.
- Değilse temporal voting + row crop.
- `descroll_canvas` sadece kalite kapısından geçerse.

### D. Rapor dili düzelmeli

Debug artefaktları ana çıktı gibi sunulmamalı:

- sharpened threshold görseli debug.
- failed canvas debug.
- primary visual sadece seçilen ve kalite kapısından geçen görsel.

## Sonuç

K-2 örneğinde kullanıcının itirazı doğru.

Bu, "OCR okumuyor" problemi değil. Bu, "doğru görsel/pano üretim hattını seçemiyoruz" problemi.

Bir sonraki iş:

1. Opus/scroll_reconstructor kodunu tekrar incele.
2. Onu ayrı candidate olarak MITAS içine port et.
3. K-2 üzerinde A/B çalıştır.
4. Opus çıktısını geçemiyorsak yeni yol ana hatta alınmayacak.
