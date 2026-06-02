# Yol Haritası — Scroll OCR Birleşim

**Durum:** 2026-05-22

---

## İki Proje Karşılaştırması

### gpt-ocr'ın getirdikleri (tools/'ta yok)

| Modül | Ne yapar | Olgunluk |
|---|---|---|
| `credit_scene_router.py` | Sahne tipi: background / text_motion / layout / difficulty | Yüksek — 18 filmde test |
| `text_layer_row_reconstruct.py` — statik fallback | displacement_range < 12px ise en iyi frame seç | Kritik — ÇARIKLI bunu eksik yüzünden çöktü |
| `detect_auto_split()` | valley_depth + balance + gap_score konfidans | tools/ find_column_split'ten belirgin üstün |
| `detect_rows() + _export_rows()` | 2x scale row crop'ları kaydeder | tools/'ta hiç yok |
| `text_layer_descroll.py` | OCR bbox track → temporal stability + engine fusion | En olgun parça |
| `credit_experiment.py` | 18 film batch, manifest, second-pass ROI | Production-ready |

### tools/'ın getirdikleri (gpt-ocr'da eksik)

| Bileşen | Nerede | Neden önemli |
|---|---|---|
| `dark_ratio < 0.35 → static_score = 0` | `CreditDetector.ProbeResult.static_score` | K-2'de overlay-on-scene frame'leri "statik jenerik" sayıldı |
| cruise_speed EMA + deviant streak reset | `ScrollReconstructor._estimate_displacements()` | Karanlık frame gap'lerinde displacement ölmez; gpt-ocr sadece median fallback |
| `quality_score` (Laplacian + kontrast + density) | `ScrollReconstructor.quality_score()` | gpt-ocr'da kompozit kalite kapısı hiç yok |

---

## Düzeltilen Hatalar (bu oturumda)

### 1. UnicodeEncodeError — konsol çıktısı
**Hata:** `print(f"OK {len(ocr_lines)} satır → ...")` Windows cp1254'te patlıyordu.  
**Düzeltme:** `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")`  
**Dosya:** `tools/full_pipeline_test.py` — satır 19

### 2. Film label yanlış çıkarma
**Hata:** `video.stem.split("-")[-1]` → `"evoArcadmin_...-1-K-2"` için `"2"` döndürüyordu.  
**Düzeltme:** `re.search(r"-\d{1,2}-[01]-(.+)$", stem)` → doğru `"K-2"` çıkarır.  
**Dosya:** `tools/full_pipeline_test.py` — `film_label()` fonksiyonu

### 3. cv2.imwrite Unicode path sessiz hata
**Hata:** `İ` ve `Ç` içeren Türkçe path'lerde cv2.imwrite sessizce başarısız oluyordu.  
Composite PNG kaydedilmiyor ama hata da vermiyordu.  
**Düzeltme:** `_png_write()` yardımcısı — `cv2.imencode(".png", img)` + `Path.write_bytes()`.  
**Dosya:** `tools/scroll_reconstructor.py` — satır 19-22, `process_video()` ve `process_frames()` içinde

---

## Açık Sorunlar (henüz düzeltilmedi)

### Sorun 1: K-2 composite'in ortası bozuk
**Kök neden:** K-2 jenerik segmenti (6140–6244s) iki tip içeriyor:
- 6140–6180s: film sahnesi üstüne overlay → `dark_ratio ≈ 0.15-0.33`
- 6180–6244s: temiz siyah zemin → `dark_ratio ≈ 0.87-0.94`

Dedektör ikisini tek segment saydı. ScrollReconstructor overlay frame'leri de stitch etti.

**Nereye düzeltme:** `E:\MITAS\core\pipelines\ocr\credit_detector.py`  
`_score_window()` içinde `static_credit` etiketi için `dark_ratio >= 0.35` zorunlu koşul.

### Sorun 2: ScrollReconstructor overlay frame filtresi yok
**Kök neden:** `_estimate_displacements()` tüm frame'leri stitch'e alıyor. `dark_ratio < 0.30` olan (film sahnesi) frame'ler de giriyor.  
**Nereye düzeltme:** `E:\MITAS\core\pipelines\ocr\text_layer_row_reconstruct.py`  
`_center_strip_composite()` öncesinde `dark_ratio` filtresi.

### Sorun 3: Cruise speed EMA eksik
**Kök neden:** `text_layer_row_reconstruct._estimate_displacements()` sadece `fallback = median(valid)` kullanıyor. Uzun karanlık sekanslar (>50 frame) gelirse fallback değeri eskiyor.  
**Nereye düzeltme:** `E:\MITAS\core\pipelines\ocr\text_layer_row_reconstruct.py`  
tools/'ın EMA bootstrap + deviant streak reset mantığını port et.

### Sorun 4: quality_score kapısı yok
**Nereye düzeltme:** `E:\MITAS\core\pipelines\ocr\text_layer_row_reconstruct.py`  
`run_text_layer_row_reconstruct()` sonunda `quality_score()` çalıştır, eğer `< 0.45` → `summary["quality_warning"] = True`.

### Sorun 5: FARELER ve K-2 segmenti erken başlıyor
**Kök neden:** Dedektör segment başlangıcına 1-2 probe fazladan katıyor.  
**Kısa vade düzeltme:** `_group_segments()` içinde segment uçlarındaki düşük skoru kes (trim).

---

## Yapılacaklar — Sıralı

```
[ ] 1. credit_detector.py → dark_ratio >= 0.35 kapısı static_credit için
[ ] 2. text_layer_row_reconstruct.py → per-frame dark_ratio filtresi (< 0.30 at)
[ ] 3. text_layer_row_reconstruct.py → EMA cruise_speed port et
[ ] 4. text_layer_row_reconstruct.py → quality_score kapısı ekle
[ ] 5. Testler: E:\MITAS\tests\test_ocr_credit_detector.py + test_ocr_text_layer_row_reconstruct.py
[ ] 6. K-2 yeniden çalıştır — overlay frame sorunu çözüldü mü kontrol et
```

---

## Test Koşulları (tekrarlanabilir)

### Batch test (18 film)
```powershell
E:\MITAS\venvs\ocr\Scripts\python.exe -B -m scripts.ocr_credit_batch_last_minutes `
  --manifest E:\MITAS\data\ocr_filmtest_last3min_manifest_20260522.json `
  --output-dir E:\MITAS\outputs\ocr_credit_experiments\filmtest_last3min_second_pass_roi_oneocr_20260522 `
  --engines oneocr `
  --fps 1 `
  --max-frames 30 `
  --preprocess-mode off
```

### Birim testler
```powershell
E:\MITAS\venvs\core\Scripts\python.exe -B -m pytest `
  E:\MITAS\tests\test_ocr_credit_experiment.py `
  E:\MITAS\tests\test_ocr_credit_detector.py `
  E:\MITAS\tests\test_ocr_credit_scene_router.py `
  E:\MITAS\tests\test_ocr_text_layer_row_reconstruct.py `
  -q
```
**Beklenen:** `10 passed, 12 skipped`

### 3 film uçtan uca (tools/ tabanlı — artık arşiv)
```powershell
F:\REPO_GitHub\Cagatay_22.02\venv\Scripts\python.exe tools/full_pipeline_test.py
```
