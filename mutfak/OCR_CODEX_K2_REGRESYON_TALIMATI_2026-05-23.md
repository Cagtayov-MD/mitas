# Codex İçin K-2 Regresyon Düzeltme Talimatı

Tarih: 2026-05-23
Hedef: K-2 composite çıktısını Opus referansına (600×4664 px, 126 OCR satırı) eşitlemek.
Referans dosya: `F:\REPO_GitHub\Cagatay_22.02\Project\test_outputs\pipeline_test\K-2\composite.png`
Mevcut bozuk çıktı: `E:\MITAS\mutfak\OCR_10_FILM_GERCEK_TEST_GORSELLER_2026-05-22\03_filmtest_03_evoArcadmin_COZUMLEMEV2S17_1991-0339-1-0000-01-1-K-2\01_selected_row_composite.png` (423×1047 px)

---

## 0. Bağlam — Önce Oku

Bu iş bir **regresyon düzeltme** işi. Opus'un `F:\REPO_GitHub\Cagatay_22.02\tools\` altındaki `scroll_reconstructor.py` + `credit_detector.py` ikilisi K-2 için temiz, uzun bir composite üretiyor. Sen bunu MITAS'a port ederken bazı kararlar regresyona yol açtı.

Karşılaştırma tablosu (K-2 son 3 dk için):

| | MITAS port (mevcut) | Opus tools (referans) |
|---|---|---|
| start_sec | 6070.0 (manifest sabit) | 6140.0 (auto-detect) |
| end_sec | 6250.0 | 6244.0 |
| Pencere | 180s | 104s |
| İşlenen kare | 1080 → 180 → 89 (filtered) | ~1300 |
| Composite | 423×1047 | 600×4664 |
| OCR satırı | düşük | 126 |

İlk 70 saniye fark kritik — Opus 6140s'de saf scroll'u yakalıyor, MITAS sabit pencere yüzünden 6070s'de cast+sahne karması bölümünden başlıyor.

---

## 1. Başarı Kriterleri (Ölç ve Karşılaştır)

Her fix sonrası K-2'yi tekrar koş ve şu metrikleri Opus referansı ile karşılaştır:

| Metrik | Mevcut | Hedef | Opus |
|---|---|---|---|
| `composite_size[1]` (yükseklik) | 1047 | **≥ 3500** | 4664 |
| `processed_frame_count` | 89 | **≥ 800** | ~1300 |
| `motion.displacement_range_px` | 605 | **≥ 3500** | bilinmiyor |
| Toplam OCR satırı (`row_count` + descroll) | 21 | **≥ 80** | 126 |
| Visual: arka planda sahne yüzü | var | **yok** | yok |

A/B kontrol scripti yaz: `scripts/k2_regression_smoke.py` — her fix sonrası çalıştır, `outputs/k2_regression_NN/` altına composite.png yaz, Opus referansı ile yan yana karşılaştırma raporu üret.

---

## 2. ASLA Dokunma Bölgesi

Aşağıdaki kod parçaları zaten doğru — kalsın:

- `text_layer_row_reconstruct.py:473-543` (`_center_strip_composite_from_motion`) — center-strip stitching mantığı Opus ile birebir aynı, doğru.
- `text_layer_row_reconstruct.py:546-592` (`_estimate_displacements`) içindeki **LK feature tracking + dx filter + _dominant_dy** kısımları. Bunlar Opus'tan port edilmiş, çalışıyor.
- `text_layer_row_reconstruct.py:118-188` (`detect_auto_split`) — sütun ayrımı. Opus'un `find_column_split`'inden zaten daha iyi.
- `text_layer_row_reconstruct.py:191-223` (`detect_rows`) — satır tespiti. Doğru.
- `text_layer_row_reconstruct.py:859-899` (`_export_rows`) — row crop export. Doğru.
- `text_layer_row_reconstruct.py:709-723` (`_detect_active`) — active frame detection. Doğru.

Bu fonksiyonların **iç mantığını değiştirme**. Sadece çağrı yerleri veya çevresel parametreler değişecek.

---

## 3. Yapılacak İşler (Sırayla)

### TASK 1 — Mevcut Düzeltmeleri Doğrula ve K-2'yi Tekrar Koş

**Durum:** İki fix kodda **görünüyor** ama K-2 son batch'te uygulanmamış. Önce verify et:

Aç ve doğrula:
- `core/pipelines/ocr/credit_experiment.py:894` → `max_frames=None` olmalı (eskiden 180'di).
- `core/pipelines/ocr/text_layer_row_reconstruct.py:416` → `threshold: float = 0.15` olmalı (eskiden 0.30'du).
- `core/pipelines/ocr/text_layer_row_reconstruct.py:421` → `min_keep = max(4, min(len(frames), int(round(len(frames) * 0.65))))` olmalı (eskiden 0.35'di).

Yukarıdakilerin hepsi tamamsa: K-2 üzerinde **smoke run** yap.

```bash
# K-2 üzerinde row_reconstruct çalıştır
# (gerçek komut credit_experiment.py'nin nasıl invoke edildiğine bağlı, repo'da
# scripts/ altındaki K-2 smoke benzeri bir script kullan; yoksa yeni bir tane yaz)
```

**Çıktı kontrol et:** `outputs/k2_smoke_after_existing_fixes/.../row_reconstruct_summary.json`

Beklenen:
- `input_frame_count` artık 180'den büyük olmalı (1080'e yakın)
- `processed_frame_count` artık 89'dan büyük olmalı (700+)
- `composite_size[1]` artık 1047'den büyük olmalı (3000+)
- Composite görsel olarak Görsel 2'den iyi olmalı

Eğer bu sayılar tutmazsa **TASK 1**'i bitirme; benim tahminlerimden bir sapma var, kodda eski değerler kalmış olabilir.

**Eğer tutarsa:** K-2 muhtemelen ana hatlarıyla düzelmiş olur. Yine de devam — sıradaki task'lar kalan ghosting'i ve sahne kontaminasyonunu temizler.

---

### TASK 2 — CreditDetector'ı Aktive Et (Segment Auto-Detect)

**Sorun:** `core/pipelines/ocr/credit_detector.py` mevcut ama `credit_experiment.py` onu **çağırmıyor**. Manifest'in `start_seconds/end_seconds`'i sabit "son 3 dk" pencereye dayanıyor; K-2'de bu pencere cast+sahne karması içeriyor.

**Yap:**

1. Önce `core/pipelines/ocr/credit_detector.py`'deki `detect_credit_segments` ve `detect_credit_segments_from_frames` fonksiyonlarının arayüzünü oku. Scroll segmentini tespit edebiliyor mu?

2. **Eğer ediyorsa:** `credit_experiment.py`'de manifest pencereyi açtıktan sonra ama frame extraction'dan önce şu mantığı ekle:

```python
# Sadece manifest'te 'auto_detect_scroll_segment: true' ise çalışsın
if item.scroll_auto_detect:  # manifest opt-in flag
    detected = detect_credit_segments(video_path, hint_start=item.start_seconds)
    if detected and detected.confidence >= 0.5:
        item.start_seconds = detected.start_seconds
        item.end_seconds = detected.end_seconds
        warnings.append(f"scroll_auto_detect:[{detected.start_seconds:.1f},{detected.end_seconds:.1f}]")
```

3. **Eğer etmiyorsa veya yetersizse:** `F:\REPO_GitHub\Cagatay_22.02\tools\credit_detector.py`'deki `CreditDetector.detect()` metodunu **yeni bir fonksiyon** olarak port et: `core/pipelines/ocr/credit_detector.py` içine `detect_scroll_segment(video_path, search_end_min=15)` ekle. Mevcut `detect_credit_segments`'a dokunma.

**Manifest değişikliği:**

`benchmark_templates/ocr_kj_benchmark.yaml` veya kullanılan manifest'e per-item opt-in flag ekle:

```yaml
- id: filmtest_03_..._K-2
  scroll_auto_detect: true  # ← yeni
  start_seconds: 6070       # fallback, auto_detect başarısızsa
  end_seconds: 6250
```

**ZORUNLU sınır:** Auto-detect başarısız olursa (confidence < 0.5 veya found=False) **manifest pencere kullanılsın**. Sessiz fail olmasın — `warnings`'a `"scroll_auto_detect_failed"` yaz.

**Test:** K-2 üzerinde tekrar smoke koş. `item_summary.json`'da yeni `start_seconds` 6140±10s civarında olmalı.

---

### TASK 3 — ROI Scroll Reconstruction'a Uygulanmasın

**Sorun:** `credit_experiment.py:668-703` arası ROI tespit edilip frames cropping'i yapılıyor. Bu cropped frames row_reconstruct'a gidiyor. K-2'de `applied_roi: [77, 19, 423, 442]` → 256px sağ kenar atılıyor (toplam 600px'den 423px'e). Opus tools full frame işliyor.

**Yap:**

`credit_experiment.py` içinde row_reconstruct'a gönderilen `frames` listesi için **ayrı bir kopya** kullan:

```python
# Mevcut: frames her şeyde aynı (OCR'da da row_reconstruct'ta da)
# Yeni: row_reconstruct için ham frames, OCR için cropped
raw_frames = list(frames)  # ROI uygulanmadan önceki kopya
if item.roi is not None:
    frames = _crop_frames(frames, crops_dir, item.roi)
    # ... mevcut ROI mantığı buradan devam eder

# Sonra row_reconstruct çağrıldığında:
result = run_text_layer_row_reconstruct(
    frame_paths=raw_frames,  # ← cropped frames değil
    output_dir=item_dir / "text_layer_row_reconstruct",
    max_frames=None,
    scale_for_rows=2,
)
```

**Alternatif (daha temiz):** Scroll reconstruction için ROI'yi `auto_roi` (geniş, hint_credit_safe_center_crop fallback'i) ile kısıtla, `refined_auto_roi` ile dar etme. Yani `_compose_roi` çağrısını row_reconstruct path'ine **uygulama**.

**ZORUNLU sınır:** OCR aşamasında ROI normal şekilde uygulanmaya devam etsin. Sadece row_reconstruct girdisi etkilensin.

**Test:** K-2 smoke sonrası `composite_size[0]` (genişlik) artık 423 değil ~600 olmalı.

---

### TASK 4 — `current_displacement` Main Path'e Cruise Speed Ekle

**Sorun:** `text_layer_row_reconstruct.py:546-592` (`_estimate_displacements`) basit global median fallback kullanıyor. Opus'un `tools/scroll_reconstructor.py:125-258` ana path'inde EMA + cruise_speed bootstrap + deviant reset var. Sen bu mantığı sadece `_estimate_displacements_cruise` adayına koymuşsun.

**Yap:**

`_estimate_displacements`'ı, `_estimate_displacements_cruise`'un içindeki cruise speed mantığını **ana path'e** koyacak şekilde refactor et. İki path'i tek path'te birleştir:

1. `_estimate_displacements_cruise`'un içeriğini `_estimate_displacements`'a taşı.
2. Eski `_estimate_displacements`'ı sil.
3. `_select_best_row_candidate` içinde `current_displacement` ve `cruise_speed_ema` artık aynı kodu çağıracak — tek aday olarak tutabilirsin.

**Parametre korunsun:** `BOOT_N=50, EMA_ALPHA=0.95, RESET_DEV=0.35, RESET_MIN=5` (Opus'un değerleri). Mevcut MITAS değerleri (`boot_min=12, reset_min=5, reset_dev=0.35, ema_alpha=0.95`) farklı — `boot_min=12` çok düşük. Opus'taki `BOOT_N=50` kullan.

**ZORUNLU sınır:** Diğer adayları (`static_best_frame`) silme, kalsın. Sadece displacement-based candidate'ları birleştir.

**Test:** K-2 smoke sonrası `motion.estimator: "current_displacement"` olmalı, ama içindeki `displacement_range_px` cruise olmadan vs cruise ile farklı olabilir. Composite görsel olarak ghosting azalmalı.

---

### TASK 5 — Quality Score'a Ghosting Cezası Ekle

**Sorun:** `text_layer_row_reconstruct.py:810-841` (`quality_score`) Laplacian variance'ı keskinlik olarak sayıyor. Ghosting edge'leri de Laplacian varyansını yükseltiyor — kötü composite "1.0 quality" alıyor.

**Yap:**

`quality_score`'a yeni bir metrik ekle: `ghost_penalty`.

Basit yaklaşım — composite'i 4 yatay slice'a böl, ardışık slice'larda text mask similarity hesapla:

```python
def _ghost_penalty(composite, cv2, np):
    """Yatay slice'lar arasında text mask örtüşmesi → ghosting göstergesi."""
    h, w = composite.shape[:2]
    if h < 200:
        return 0.0  # çok kısa, anlamlı değil
    slice_h = h // 8
    masks = []
    for i in range(4):
        y0 = i * slice_h * 2
        y1 = y0 + slice_h
        slice_img = composite[y0:y1]
        mask = _composite_text_mask(slice_img, cv2, np)
        masks.append((mask > 0).astype(np.float32))
    
    # Ardışık slice'lar arasında IoU
    ious = []
    for i in range(len(masks) - 1):
        a, b = masks[i], masks[i+1]
        intersection = (a * b).sum()
        union = ((a + b) > 0).sum()
        if union > 0:
            ious.append(intersection / union)
    
    if not ious:
        return 0.0
    mean_iou = float(np.mean(ious))
    # IoU > 0.3 → şüpheli; 0.5+ → ghost
    return max(0.0, (mean_iou - 0.2) * 2.0)  # [0, 1+] aralığı
```

Sonra `quality_score` formülüne:

```python
ghost = _ghost_penalty(composite, cv2, np) if composite is not None else 0.0
score = (0.45 * sharpness_score) + (0.35 * contrast_score) + (0.20 * density_score) - (0.30 * ghost)
score = max(0.0, min(1.0, score))
```

Ve summary'e `ghost_penalty` alanını ekle (debug için).

**ZORUNLU sınır:** Mevcut `quality_score` interface'ini koru — geri uyumluluk. Sadece yeni alan ekle, eskileri silme.

**Test:** K-2'nin mevcut bozuk composite'i `ghost_penalty > 0.4` üretmeli, score < 0.7 olmalı. Opus referansı `ghost_penalty < 0.1`, score > 0.85 olmalı.

---

### TASK 6 — A/B Karşılaştırma Scripti

**Yaz:** `scripts/k2_regression_compare.py`

İşlevler:
1. K-2 için MITAS row_reconstruct'ı koş, composite üret.
2. Opus referansını `F:\REPO_GitHub\Cagatay_22.02\Project\test_outputs\pipeline_test\K-2\composite.png` üzerinden yükle.
3. Yan yana karşılaştırma görseli üret (PIL ile montaj): sol MITAS, sağ Opus.
4. Metrik tablosu üret: composite_size, displacement_range, row_count, processed_frame_count, OCR line count.
5. JSON rapor: `outputs/k2_compare/report.json`.

**Çıktı:** Her TASK fix'inden sonra bu scripti koş. `outputs/k2_compare/{date}_{task}/` altına kaydet. Önceki run ile diff alabilirsin.

---

## 4. Bütünleşik Validation — Tüm 10 Film Re-run

Sadece K-2 düzelmesin, **diğer 9 filmi de bozma**. TASK 1-5 tamamlandıktan sonra:

1. `benchmark_templates/ocr_kj_benchmark.yaml` veya kullanılan 10-film batch'i tekrar koş.
2. Yeni outputs'u `OCR_10_FILM_GERCEK_TEST_GORSELLER_2026-05-22` ile karşılaştır.
3. Şu metrikler **düşmemeli**:
   - `row_count` her film için
   - `nonempty_role_name_count`
   - `composite_size[1]` (yükseklik)
4. K-2 dışında bir filmde **regresyon görürsen** (örn. SİYAH_KADİFE_ELBİSE şu an 1.0 quality, 7 row üretiyordu), o fix'i geri al ve **K-2 özel branch** olarak ayrı tut.

**ZORUNLU:** Hiçbir filmde mevcut baseline altına düşme. K-2 düzelirken Kontes Mariza'yı kırmak kabul edilemez.

---

## 5. Yapma Listesi (Sıklıkla Yapılan Hatalar)

- **Yapma:** `_center_strip_composite_from_motion` içine yeni bir parametre/flag ekleme. Bu fonksiyon Opus ile birebir aynı, dokunma.
- **Yapma:** `detect_auto_split`'i basitleştirme. Mevcut implementation Opus'un `find_column_split`'inden zaten daha iyi.
- **Yapma:** `static_best_frame` adayını silme. K-2 dışındaki düşük-motion filmlerde fallback olarak gerekli.
- **Yapma:** Yeni bir candidate eklemek. Toplam 2 candidate yeterli: `displacement_with_cruise` (TASK 4 sonrası birleşik) ve `static_best_frame`.
- **Yapma:** Manifest format'ını break edecek değişiklik. `scroll_auto_detect` yeni opt-in flag, default `false`. Mevcut manifest'ler değişmeden çalışmalı.
- **Yapma:** ROI'yi tamamen kaldırma. Sadece scroll reconstruction girdisinde bypass et. OCR aşamasında ROI normal kullanılır.

---

## 6. Onay Akışı

Her TASK'tan sonra:

1. K-2 smoke koş, metrik tablosunu güncelle.
2. `mutfak/OCR_CODEX_K2_REGRESYON_ILERLEME_2026-05-23.md` dosyasını oluştur/güncelle. Her task için:
   - Tarih
   - Yapılan değişiklik özeti
   - Önce/sonra metrikleri
   - Composite görsel yol (k2_compare report'undan)
3. **Hiçbir task'ı commit etmeden önce** kullanıcıya haber ver. Commit yetkisi onun.

---

## 7. Hızlı Başlangıç

Sırayla:

```bash
# 1. Mevcut fix'leri doğrula
grep -n "max_frames=" core/pipelines/ocr/credit_experiment.py
grep -n "threshold: float" core/pipelines/ocr/text_layer_row_reconstruct.py

# 2. K-2 smoke (mevcut kodla)
# (gerçek invoke komutu repo'da; yoksa yaz)

# 3. Sonuç good ise TASK 2'ye geç, değilse TASK 1'i debug et
```

İlk smoke run sonucunu bekliyorum — `composite_size`, `processed_frame_count`, `displacement_range_px` üçünü bana yaz, ona göre TASK 2'ye geçeceğiz.

---

**Sınır özeti:**
- Stitching, auto-split, detect_rows, row export, active frame: **dokunma**.
- max_frames, dark_filter threshold: **doğrula** (zaten fix var).
- CreditDetector wiring, ROI bypass, cruise main, ghost penalty: **yap**.
- Hiçbir manifest break etme, hiçbir filmde regresyon kabul etme, commit etmeden onay al.
