# OCR Kalite Polisi Uygulama Raporu — 2026-05-23

## 1. Ne yapıldı

- `core/pipelines/ocr/image_quality_police.py` eklendi.
  - `assess_output()` PNG çıktıları için `OK`, `BROKEN_BLACK`, `BROKEN_BACKGROUND_LEAK` vb. karar döndürüyor.
  - Ölçülen ana metrikler: black/white ratio, Canny edge density, connected components, OCR record count, mean OCR confidence, text bbox area ratio, non-text edge ratio, row uniformity, aspect ratio.
- `tests/test_image_quality_police.py` eklendi.
  - DÜNYANIN row canvas: `BROKEN_BACKGROUND_LEAK`
  - PILKINGTON row canvas: `OK`
  - KUKLA fused PNG: `BROKEN_BLACK` (eski pilotta fused yoksa mevcut fresh fixture kullanılıyor)
- `core/pipelines/ocr/credit_experiment.py` içine kalite etiketi entegre edildi.
  - `item_summary.json` içine `quality_police` alanı yazılıyor.
  - Üretim karar mantığı değiştirilmedi; otomatik fallback yok.
- `core/pipelines/ocr/credit_segment_dispatcher.py` içine scene-router bridge kuralı eklendi.
  - `vertical_scroll` confidence >= `0.85` ise iki `MOVING_SCROLL` arasında kalan ve 60 sn altı olan `UNKNOWN` segmentler `MOVING_SCROLL_INFERRED` oluyor.
- `scripts/ocr_box_tracker_poc.py` sibling `scene_router_refined.json` okuyup dispatcher'a geçiriyor.
- `scripts/ocr_frame_stride_poc.py` eklendi.
  - Kompozit PNG üretmiyor.
  - Mevcut `frame_ocr.json` cache'ini kullanarak frame-stride row dedup POC JSON'u üretiyor.

## 2. Quality police sonuçları

| Klip | status | reasons | mean_ocr_conf | edge_density | text_area_ratio |
|---|---|---|---:|---:|---:|
| filmtest_dunyanin_en_muthis_adami_last3min | BROKEN_BACKGROUND_LEAK | edges_outside_text_boxes | 0.885461 | 0.108906 | 0.174316 |
| filmtest_pilkingtondan_sonra_last3min | OK | - | 0.972995 | 0.160435 | 0.586150 |
| filmtest_kukla_adam_last3min | BROKEN_BLACK | black_pixel_ratio>1.000 | - | 0.000000 | 0.000000 |

## 3. Frame-stride karşılaştırması

| Klip | RR unique | FS unique | shared | RR-only örnek | FS-only örnek |
|---|---:|---:|---:|---|---|
| filmtest_dunyanin_en_muthis_adami_last3min | 34 | 340 | 6 | GENE HEITZMEN BICKWALTER; HORETON MA CUERVO RUSSELL | X; IMES; ASSOC; HE |
| filmtest_pilkingtondan_sonra_last3min | 26 | 163 | 23 | DAFFOR; PHOTOGRAPHY DUNN ANDREW | L; JAMES; BOR PECK; PENNY |

Not: FS satır sayısı yüksek ama ham dedup çok parçalı. Bu POC, background leak'e bağışık bir yön gösteriyor; mevcut haliyle doğrudan final çıktı seçici olmamalı.

## 4. Bridge etkisi

| Klip | UNKNOWN→INFERRED |
|---|---:|
| filmtest_dunyanin_en_muthis_adami_last3min | 2 |
| filmtest_pilkingtondan_sonra_last3min | 0 |
| filmtest_cennette_bulusalim_last3min | 0 |
| filmtest_son_metro_last3min | 0 |

KUKLA eski pilot klasöründe tamamlanmış `frame_ocr.json` olmadığı için bridge POC bu klasörden koşturulmadı.

## 5. Retest sonucu

Problem klip güncel kodla tek başına yeniden koşuldu:

- Çıktı: `outputs/filmtest_dunyanin_single_retest_20260523_quality/`
- Status: `done`
- `row_reconstruct.row_count`: 54
- `frame_ocr_records`: 3369
- `temporal_unique_lines`: 407
- `quality_police.outputs.row_canvas.status`: `BROKEN_BACKGROUND_LEAK`
- Runtime: 195.604 sn

Bu sonuç eski gözlemi doğruluyor: pipeline teknik olarak satır üretse de row canvas görsel kalite olarak kırık.

## 6. Bilinen sınırlar / regression riski

- Quality police şu an sadece etiketliyor; fallback seçmiyor.
- DÜNYANIN için background leak kararı özellikle `non_text_edge_ratio=0.809849` ile geliyor. Bu metrik, text bbox dışındaki edge yoğunluğunu yakalıyor.
- Frame-stride POC fazla fragment üretiyor. Satır sayısı RR'den yüksek olsa da bu doğrudan daha iyi final metin anlamına gelmiyor.
- Son Metro'daki 88.5 sn UNKNOWN bridge edilmedi; 60 sn sınırı doğru şekilde korundu.

## 7. Karar önerisi

Kompozit yaklaşımı tek başına sürdürülmemeli. En makul yol:

1. Quality police üretim raporlamasında kalsın.
2. Frame-stride POC ikinci aday olarak geliştirilsin ama önce fragment temizleme/dedup iyileştirilsin.
3. Row-reconstruct için tracker-guided masked reconstruction sonraki fazda değerlendirilsin.

Bugünkü sonuç: problem gerçek, kalite polisi yakalıyor, bridge segment boşluğunu azaltıyor, frame-stride umut veriyor ama ham haliyle final çözüm değil.
