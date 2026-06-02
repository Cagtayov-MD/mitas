# OCR Credit Pipeline — Kalite Polisi + Frame-Stride POC + Bridge + Retest

**Tarih:** 2026-05-23
**Hedef klip:** `filmtest_dunyanin_en_muthis_adami_last3min`
**Pilot:** `data/ocr_filmtest_6clip_pilot_20260523.json`
**Mevcut çıktı klasörü:** `outputs/filmtest_6clip_pilot_20260523/`

---

## 0. Bu MD'nin Kuralları

Bu görev tanımı bağlayıcıdır. **Onaylamayı bırak, uygula.** "Çok iyi fikir", "haklısın", "ek olarak şunu da öneriyorum" tarzı genişletme yok. Eklemek istediğin her şey için **önce sor**, kendi başına scope büyütme.

Aşağıdaki "YAPMA" listesi, kapsamı dar tutmak için var. Her bir maddeyi "ama düzeltirken zaten temizlerim" diye atlatma. Atlatırsan rollback yiyeceksin.

---

## 1. Bağlam (kısa)

`DÜNYANIN_EN_MÜTHİŞ_ADAMI` klibinde `row_composite_sharpened.png` çıktısı gürültülü: arka plan ve sahne dokusu canvas'a sızıyor. Pipeline teknik olarak başarılı sayıyor (54 row), ama görüntü kullanılamaz.

Kök neden teşhisi:

1. `box_tracker` MOVING_SCROLL segmentleri arasında 27 sn ve 46 sn UNKNOWN bırakıyor; mevcut smoothing bu kadar uzun boşluğu birleştirmiyor.
2. `text_layer_row_reconstruct` segment bilgisini umursamadan full frame'i kompozit yapıyor; hareketli arka plan canvas'a taşınıyor.
3. Sistemde "üretilen PNG kırık mı?" sorusunu soran hiçbir gate yok. Pipeline çalıştıysa başarılı sayılıyor.

Ayrıca: kompozit PNG üretmek bu problem için zorunlu bir yaklaşım **değil**. Frame-stride sampling + OCR + row dedup, sektörde rolling credits için daha yaygın ve background-leak'e immün bir çözüm. Bunu POC olarak yan branch'te denemek istiyoruz; karar **POC sonucundan sonra** verilecek.

---

## 2. Yapılacaklar (zorunlu sıra)

### Adım 1 — Kalite Polisi (regression detector)

**Yeni dosya:** `core/pipelines/ocr/image_quality_police.py`

**Sözleşme:**

```python
def assess_output(
    png_path: Path,
    ocr_json_path: Path | None = None,  # row_crop_ocr.json veya frame_ocr.json
    expected_kind: Literal["row_canvas", "frame", "fused"] = "row_canvas",
) -> dict:
    """
    Returns:
    {
        "status": "OK" | "BROKEN_EMPTY" | "BROKEN_BLACK" | "BROKEN_NO_TEXT"
                | "BROKEN_BACKGROUND_LEAK" | "BROKEN_SMEAR"
                | "BROKEN_LOW_CONTRAST" | "SUSPICIOUS_NEEDS_REVIEW",
        "reasons": [str, ...],          # hangi metrikler tetikledi
        "metrics": {...},                # tüm ölçülen değerler
        "suggested_fallback": str | None # önerilen alternatif (frame_stride, best_frame, vb.)
    }
    """
```

**Ölçülecek metrikler (hepsi `metrics` altına ham değer olarak yazılsın):**

- `black_pixel_ratio` — `< 0.005` veya `> 0.95` → BROKEN_BLACK/BROKEN_EMPTY
- `white_pixel_ratio`
- `edge_density` — Canny edge piksellerinin toplam piksele oranı
- `connected_component_count` — binarize sonrası
- `ocr_record_count` — JSON'dan okunan toplam text record
- `mean_ocr_confidence` — OCR JSON'dan
- `text_bbox_area_ratio` — OCR bbox'larının toplam alanı / canvas alanı
- `non_text_edge_ratio` — edge_density yüksek ama text_bbox_area_ratio düşük → background leak
- `row_uniformity_score` — y eksenindeki text bbox merkezlerinin spacing variance'ı (düşük = düzenli satır, yüksek = dağınık)
- `aspect_ratio` — canvas çok uzun ve dar mı

**Karar kuralları (sade tut, threshold'ları sabit kodla, configurable değil):**

| Status | Tetik |
|---|---|
| `BROKEN_BLACK` | `black_pixel_ratio > 0.95` |
| `BROKEN_EMPTY` | `white_pixel_ratio > 0.95` veya `ocr_record_count == 0 AND edge_density < 0.01` |
| `BROKEN_NO_TEXT` | `ocr_record_count == 0` (ama yukarıdakilere uymuyor) |
| `BROKEN_BACKGROUND_LEAK` | `edge_density > 0.15 AND text_bbox_area_ratio < 0.10` |
| `BROKEN_SMEAR` | `connected_component_count < 5 AND ocr_record_count < 3 AND edge_density > 0.05` |
| `BROKEN_LOW_CONTRAST` | std(grayscale) < 15 ve OK değil |
| `SUSPICIOUS_NEEDS_REVIEW` | mean_ocr_confidence < 0.4 ve diğerlerinden hiçbiri tetiklemedi |
| `OK` | hiçbir kural tetiklemedi |

**Bağımlılık:** Sadece `numpy`, `cv2` (OpenCV), `PIL`. Yeni paket **ekleme**.

**Test:** `tests/test_image_quality_police.py`

Test fixtureları için **gerçek pilot çıktılarını** kullan:
- `outputs/filmtest_6clip_pilot_20260523/items/filmtest_dunyanin_en_muthis_adami_last3min/` → `BROKEN_BACKGROUND_LEAK` bekleniyor
- `outputs/filmtest_6clip_pilot_20260523/items/filmtest_kukla_adam_last3min/` → `BROKEN_BLACK` bekleniyor (eğer fused PNG siyahsa)
- `outputs/filmtest_6clip_pilot_20260523/items/filmtest_pilkingtondan_sonra_last3min/` → `OK` bekleniyor

Bu üç beklenti pas geçmiyorsa threshold'ları **bana sor**, kendi başına gevşetme.

---

### Adım 2 — Polis Entegrasyonu (sadece etiket, karar değiştirme)

**Düzenlenecek dosya:** `core/pipelines/ocr/credit_experiment.py`

Pipeline her PNG ürettikten sonra:
1. `assess_output()` çağrılsın
2. Sonuç `item_summary.json` içine `quality_police: {...}` alanı olarak yazılsın
3. **Production karar mantığı değişmesin.** Polis sadece raporlasın. Hangi pipeline'ın kazandığını, hangi PNG'nin seçildiğini polis **belirlemiyor.**

**YAPMA:** `if quality_status == "BROKEN_*": fallback_to(...)` gibi otomatik yönlendirme yok. Şu an sadece etiketliyoruz. Production değişikliği ayrı adım, ayrı PR.

---

### Adım 3 — Frame-Stride OCR POC (kompozitsiz alternatif)

**Yeni dosya:** `scripts/ocr_frame_stride_poc.py`

**Mantık:**

```
1. scene_router_refined.json'dan vertical_scroll_confidence ve dy_per_frame al
2. Eğer vertical_scroll_confidence < 0.85: bu klibi atla, log et
3. target_row_height_px = 30 (sabit, ilk POC için)
4. stride_frames = max(1, round(target_row_height_px / abs(dy_per_frame)))
5. Klipten her stride_frames'de bir frame örnekle
6. Her frame'i mevcut OCR engine ile OCR'la (credit_experiment'te hangisi kullanılıyorsa aynısı)
7. Row-level dedup:
   - aynı text + y_position farkı < 10px → aynı satır
   - veya Levenshtein ratio > 0.85 → aynı satır
8. Çıktı: rows[] = [{text, first_seen_t, last_seen_t, mean_confidence, frame_count}]
```

**Kompozit PNG ÜRETME.** Sadece JSON üret.

**Hedef klipler:** Sadece bu ikisi (POC, ölçek değil):
- `filmtest_dunyanin_en_muthis_adami_last3min`
- `filmtest_pilkingtondan_sonra_last3min`

**Çıktı klasörü:** `outputs/ocr_frame_stride_poc_20260523/`

**Kıyas için:** Her klip için `comparison.json` üret:
```json
{
  "row_reconstruct_unique_rows": <int>,        // mevcut pipeline
  "frame_stride_unique_rows": <int>,           // bu POC
  "shared_rows": <int>,                        // ortak satır sayısı
  "row_reconstruct_only": [str, ...],          // sample 10 tane
  "frame_stride_only": [str, ...]              // sample 10 tane
}
```

**YAPMA:**
- Tracker'ı çağırma. Sadece scene_router'a güven.
- Görüntü iyileştirme/preprocessing ekleme. Frame'i ham haliyle OCR'a ver.
- "Daha iyi olsun" diye motion model, Kalman, RANSAC katma.

---

### Adım 4 — Scene_router + Tracker UNKNOWN Bridge

**Düzenlenecek dosya:** `core/pipelines/ocr/credit_segment_dispatcher.py`

**Yeni kural:**

```
if scene_router.vertical_scroll_confidence >= 0.85:
    for each UNKNOWN segment U between two MOVING_SCROLL segments:
        if U.duration <= 60.0:
            U.label = "MOVING_SCROLL_INFERRED"
            U.bridged_from = "scene_router_confidence"
```

**Kısıtlar:**
- 60 saniyeden uzun UNKNOWN'ları **bridge etme**. Bu fade-out veya sahne değişikliği olabilir.
- Sadece iki MOVING_SCROLL **arasında** kalan UNKNOWN'lar (kenarlarda olan UNKNOWN'lara dokunma).
- STATIC_CARD veya MIXED komşulu UNKNOWN'lara dokunma.

**Test güncellemesi:** `tests/test_ocr_box_tracker_poc.py` veya dispatcher'ın kendi test dosyası varsa oraya:
- DÜNYANIN segmentleri üzerinden UNKNOWN→MOVING_SCROLL_INFERRED dönüşümü olduğunu doğrula
- KUKLA_ADAM (static card baskın) için bridge tetiklenmediğini doğrula

---

### Adım 5 — Aynı Klip Retest

Adım 1–4 bittikten **sonra** pilot'u yeniden koş:

```powershell
python scripts/ocr_pilot_summary.py `
  --pilot data/ocr_filmtest_6clip_pilot_20260523.json `
  --output outputs/filmtest_6clip_retest_20260523/
```

Eğer `ocr_pilot_summary.py` parametre kabul etmiyorsa, **mevcut çalıştırma komutunu** runner.log'dan oku, aynısını farklı output ile koş. **Komutu uydurma.**

**Sonra Adım 3 POC'sini çalıştır:**

```powershell
python scripts/ocr_frame_stride_poc.py `
  --items filmtest_dunyanin_en_muthis_adami_last3min,filmtest_pilkingtondan_sonra_last3min `
  --pilot-output outputs/filmtest_6clip_retest_20260523/ `
  --output outputs/ocr_frame_stride_poc_20260523/
```

---

## 3. Acceptance Criteria

Aşağıdakilerin **hepsi** sağlanmadan "tamam" deme:

- [ ] `core/pipelines/ocr/image_quality_police.py` var, `assess_output()` exported
- [ ] `tests/test_image_quality_police.py` geçiyor (DÜNYANIN=BROKEN_BACKGROUND_LEAK, PILKINGTON=OK)
- [ ] `credit_experiment.py` her PNG için `item_summary.json` içine `quality_police` alanı yazıyor
- [ ] Production karar mantığı **değişmedi** (mevcut testler kırılmadı: `pytest tests/test_ocr_*.py` yeşil)
- [ ] `scripts/ocr_frame_stride_poc.py` var ve iki hedef klip için `comparison.json` üretiyor
- [ ] `credit_segment_dispatcher.py` UNKNOWN bridge kuralı eklendi, dispatcher testi geçiyor
- [ ] `outputs/filmtest_6clip_retest_20260523/` klasörü dolu, mevcut çıktı klasörüyle aynı dosya seti var
- [ ] DÜNYANIN için retest çıktısında `quality_police.status == "BROKEN_BACKGROUND_LEAK"` görünüyor
- [ ] KUKLA_ADAM ve PILKINGTON için quality_police etiketi mevcut çıktıyla **tutarlı** (regression yok)
- [ ] Frame-stride POC, DÜNYANIN için en az `row_reconstruct_unique_rows` kadar satır üretti (eşit veya fazla; az olursa raporla, sebep yaz)

---

## 4. Rapor Şablonu (görev sonu teslim)

Görev bitince `mutfak/OCR_KALITE_POLISI_UYGULAMA_RAPORU_2026-05-23.md` oluştur. İçerik:

1. **Ne yapıldı** — adım adım, hangi dosya değişti
2. **Quality police sonuçları tablosu:**
   | Klip | status | reasons | mean_ocr_conf | edge_density | text_area_ratio |
3. **Frame-stride karşılaştırması:**
   | Klip | RR unique | FS unique | shared | RR-only örnek | FS-only örnek |
4. **Bridge etkisi:** her klipte UNKNOWN→INFERRED dönüşüm sayısı
5. **Bilinen sınırlar / regression riski:** hangi klipte hangi metrik sınırda
6. **Karar önerisi:** kompozit yaklaşımına devam mı, frame-stride'a geçiş mi, ikisi de mi — **gerekçeli**

---

## 5. YAPMA Listesi (yalakalık & scope creep tuzakları)

- ❌ Polis'i otomatik fallback router yapma. Sadece etiket.
- ❌ RANSAC, Kalman, optical flow ekleme.
- ❌ `row_reconstruct`'a "masked ROI" parametresi eklemeden önce frame-stride POC sonucunu bekle.
- ❌ Yeni paket dependency (paddleocr-extras, opencv-contrib gibi) ekleme.
- ❌ "Hazır kod görmüşken şunu da temizleyeyim" tarzı sürpriz refactor.
- ❌ Threshold'ları config dosyasına taşıma. İlk versiyonda kod içi sabit kalsın.
- ❌ VLM (Qwen-VL, GPT-4V) entegrasyonu. Bu sonraki faz, **bu görevde değil.**
- ❌ "credit_experiment.py'ı baştan yazsak daha temiz olur" — hayır, dokunma.
- ❌ `box_tracker.py` algoritmasını değiştirme. UNKNOWN üretmesi sorun değil, bridge'le çözüyoruz.

---

## 6. Şüpheye Düşersen

- Threshold tetiklenmiyor → **sor**, kendi başına gevşetme
- POC karşılaştırması RR lehine çıkıyor → bu OK, raporla, kararı bana bırak
- `scripts/ocr_pilot_summary.py` parametre kabul etmiyor → runner.log'dan komutu oku, sor
- KUKLA_ADAM regression riski varsa → durdur, raporla, **devam etme**

---

## 7. Sonraki Fazlar (bu görevde DEĞİL — bilgi için)

- VLM cross-check ("üretilen satırlar gerçekten frame'lerde var mı?")
- Tracker-guided masked row_reconstruct (eğer frame-stride POC'si kaybederse)
- Quality police production gating (etiketten kararvericiye terfi)
- Line harvesting (her satırın en net frame'inden ayrı crop)

Bunlar şimdi yok. Şimdi sadece yukarıdaki 5 adım.
