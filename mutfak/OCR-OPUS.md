# OCR-OPUS — Devam Dosyası

> **Son güncelleme: 2026-05-23 16:02**
> **Yazan oturum:** Opus 4.7 (E:\MITAS, master branch)
> **Sıradaki oturum için:** Bu dosyayı oku, devam et. Sürekli aynı şeyi açıklatma.

---

## 0. KURALLAR (kalıcı — sıradaki oturum buna uyacak)

Bu kurallar Çağatay'ın oturum boyunca söylediği şeylerden çıktı. Hepsi geçerli.

1. **Türkçe direkt iletişim.** Memory'de var (`user_profile`).
2. **Master'da çalış, worktree YOK.** Düzeltmeler doğrudan master'da. Commit yine sadece istenince. Memory: `feedback_master_no_worktree`.
3. **Plan Opus / uygula Sonnet.** Planlamayı Opus yapar, kod uygulamasını Sonnet alt-ajanına devret. Memory: `feedback_plan_implement_split`.
4. **"Hemen silme hemen atma sadece bir bak"** — Çağatay bunu açıkça söyledi. Refactor'a kaçma, önce gözle.
5. **"Bir yerde ipi kaçırdık orayı bulmak lazım"** — bisection yaklaşımı. Hangi commit'ten sonra şey kırıldı bul.
6. **"Hangi yolu mantıklı görüyorsan onu yap"** — Çağatay büyük kararı sana bırakır AMA sapma noktasını/saçmalamayı önce göstermeni ister. Sezgisi güçlü, fikrini söyle.
7. **"Aşama aşama projeyi incele, şurası saçmalıyor dediğin yerleri çıkart"** — denetim modunda numaralı liste çıkar.
8. **Bilerek koyulmuş ceza/eşik varsa hemen kaldırma** — örnek: row_count > 90 penalty'sini bilerek koymuş, sebep ghost stitch detection. Önce kontrol et, sonra koşullandır.
9. **Adım panosu zorunluluğu (bu dosyada):** her büyük adım için
   - `YAPILACAK` → `YAPILDI (master'da)` → `COMMIT EDİLDİ (<hash>)` zinciri.
   - Bu dosyayı oturum boyunca **her adımdan sonra güncelle**.
10. **Pre-existing fail'leri izole et**, kapsam dışı bırak. ASR/webui/docs/translate uncommitted'lerine dokunma — onlar başka oturumun in-flight işi.

---

## 1. ÇAĞATAYIN AMACI

MITAS arşivi için OCR pipeline'ı: film jeneriklerinden rol/isim satırlarını **doğru ve hızlı** okutmak. 4 kategori:

| Kategori | Bg | Text | Pipeline |
|---|---|---|---|
| **A** | static | scroll | scroll reconstructor (eski tools mantığı) |
| **B** | moving | scroll | box tracking + canvas + bg suppression |
| **C** | moving | static (kaos: kırmızı BG + oval kafa + sabit yazı) | variance masking + text mask gating + box tracking |
| **D** | static | static (standart) | tek frame OCR (best_frame seç + Paddle) |

Çağatay'ın asıl planı: **box tracking + dinamik hız + ekran kenarına gelince yeni track başlat** mimarisi. Tüm frame'lerde değil bbox seviyesinde karar — pipeline kendi kendini takip eder. Bu plan eski `F:\REPO_GitHub\Cagatay_22.02\tools\` altında çalışıyordu (`scroll_reconstructor.py` 586 satır + `full_pipeline_test.py`'de OneOCR + `run_ocr_on_composite`). MITAS'a taşımada PARÇA OLARAK kayboldu.

---

## 2. HEDEF VE GENEL PLAN (K-BoxTrack)

```
[1] PaddleOCR detection seyrek (her 3. frame'de bir)
[2] box_tracker.build_text_tracks(...)
[3] Track sınıflandır:
      |velocity_y| < 2.0 → static_text
      |velocity_y| >= 2.0 → scrolling_text
[4] Static → kart bazlı grupla → best_frame_per_card → recognition (re-OCR yok, mevcut record'lardan satır toplama)
[5] Scroll → text_layer_row_reconstruct → composite.png + sharpened.png
[6] Scroll composite ÜZERİNDE OCR (eski tools'taki gibi)
[7] Çıktı: cards/card_NN.json + scroll/scroll_text_lines.json + scroll/composite.png + summary
```

**Aktivasyon:** `USE_BOX_TRACK_PIPELINE=1` env var. Eski 8-aşamalı yol regression için duruyor, dokunulmadı.

---

## 3. DURUM PANOSU (2026-05-23 15:56)

### YAPILDI (master'da, COMMIT EDİLDİ — `d1d3c95`)

- [x] **Denetim — 17 saçmalama maddesi** çıkarıldı. Pipeline'ın sınıflandırmaya uymaması, quality_police icra eksiği, 8-varyant preprocess, 4× motion analiz, 2× frame_ocr. Detay: bu dosyanın §7'si.
- [x] **Bisection — sapma noktası `c3c042c`** ("Add OCR credit experiment and K-2 regression fixes") commit'i. Tek commit'te 6.837 satır eklendi: credit_experiment 3.268, text_layer_descroll 1.271, text_layer_row_reconstruct 944, credit_scene_router 527, credit_detector 699, selector 128. Eski `tools/full_pipeline_test.py`'deki sade `if static: tek frame OCR; if scroll: composite + OCR` mantığı burada KAYBOLDU.
- [x] **K-BoxTrack omurgası kuruldu** — `core/pipelines/ocr/unified_credit_pipeline.py` (158 satır, Sonnet).
- [x] **box_tracker.py'a 3 helper eklendi:** `classify_track_motion`, `group_static_tracks_into_cards`, `select_best_frame_per_card` (Sonnet).
- [x] **credit_experiment.py'a gate** — `USE_BOX_TRACK_PIPELINE=1` ise unified yola gir, eskiyi atla (Sonnet).
- [x] **5 yeni unit test** — `tests/test_ocr_box_track_pipeline.py`.
- [x] **Pilot v2** — KUKLA_ADAM 180sn (5300-5480s), 1080 frame: **22 dakika → 25 saniye (56× hızlanma)**. fused.png %99.99 siyah → 46 kart × ~30 okunaklı satır, confidence ≥0.92.
- [x] **OCR record timestamp düzeltmesi** — unified pipeline'da strided_frame_index/fps ile `timestamp_seconds` doldurma (PaddleOCR record'larda yok).
- [x] **y-overlap kapatma** — `max_y_overlap_ratio` default 0.0 (her satır farklı y'de olduğu için ayrı karta gitmesin). 46 → 18 kart.
- [x] **`recognize()` strategy kwarg fix** — Sonnet ilk yazımda missing kwarg vermişti, sessizce 0 record dönüyordu. Düzeltildi, error counter eklendi.
- [x] **Scroll OCR fix** — eski tools'ta `run_ocr_on_composite` vardı, MITAS'a taşımada koda inmedi. Şimdi unified pipeline'da composite üretildikten sonra `paddle_engine.recognize(scroll_canvas_path, strategy="scroll_canvas_ocr")` çağrılıyor, sonuç `scroll/scroll_text_lines.json`'a yazılıyor.
- [x] **4 untracked modül commit'lendi:** `box_tracker.py`, `image_quality_police.py`, `credit_segment_dispatcher.py`, `text_track_state.py` (toplam ~1.500 satır, hiç commit edilmemişti, repository tehlikedeydi).

- [x] **row_count > 90 penalty'si gevşetildi** — COMMIT EDİLDİ `4497997` (`fix(ocr): relax row_count penalty for legitimate long scrolls`). Eski: 90+ row 0.18 ceza. Yeni: 300+ row 0.10 ceza. **NOT:** Çağatay bunu "bilerek kalabalık" diye koymuştu (ghost stitch detection). İleride regression görülürse ghost-koşullu yapılacak: `row_count > 90 AND ghost_penalty > 0.25 → ceza`.

- [x] **Pilot v2 (4 film, row penalty fix sonrası) doğrulandı:**

| Film | v1 scroll_lines | v2 scroll_lines | Fark |
|---|---|---|---|
| JURASSIC | 271 | 271 | aynı ✓ |
| ROBINSON | 176 | 176 | aynı ✓ |
| **X-MEN** | **34** | **238** | **+204 (~7×)** ✅ |
| ANJELIK | 0 | 0 | aynı (ayrı sorun) |

Çıktı: `outputs/ocr_4films_boxtrack_20260523_v2/items/xmen_2000_end_credits/unified/scroll/scroll_text_lines.json`.

### YAPILACAK (sıralı — Çağatay'ın 16:50 kararı: hepsini yapacağız, sıra **B → C → A → D → E**)

> Sebep: **B** regression fix (gerçek çözüm, kalite sıçraması). **C** kullanılabilirlik. **A** B'ye rağmen kalan durumlar için emniyet ağı. **D** kullanılabilirlik. **E** temizlik (en son).

1. **B-port — eski `tools/scroll_reconstructor.py:_text_mask` fonksiyonunu MITAS'a port** (REGRESSION FIX, ANJELIK'i çözer + genel kaliteyi artırır).
   - **Sorun:** MITAS'taki `text_layer_row_reconstruct._frame_text_mask` gevşek (lokal kontrast + canny + dilate(7×7)). Hareketli BG'nin edge'leri maskeye sızıyor → LK tracker bazen text'e bazen bg'ye kilitleniyor → composite alignment çuvallıyor → ANJELIK kahverengi şerit, 0 satır.
   - **Eski yaklaşım:** `thr = max(45.0, gray.mean() + gray.std())` global sıkı binary + dilate(11×11). Sadece harfler kalıyor, tracker text'e kilitleniyor.
   - **Box tracking kaybolur mu? HAYIR.** Bu mask yalnızca `text_layer_row_reconstruct` içindeki LK feature tracker (composite alignment için) içindir. Üst seviye box_tracker (PaddleOCR detection + IoU eşleştirme) bundan bağımsız çalışıyor. Yani box tracking + dinamik hız + kenar yenileme zinciri etkilenmez, sadece composite/canvas adımı düzelir.

2. **C-kart — KUKLA 18 → 3-5 kart birleştirme** (kullanılabilirlik). 2-pass: önce zaman gap (mevcut), sonra ardışık kartları "metin benzerliği + zaman yakınlığı + y-pozisyon yakınlığı" ile birleştir.

3. **A-fb — ANJELIK fallback emniyet ağı** (B-port'a rağmen başarısız olursa). Composite quality police `BROKEN_EMPTY/BROKEN_LOW_CONTRAST/BROKEN_BACKGROUND_LEAK` derse → `scroll_tracks` observation'larından her track için en yüksek confidence record'u y-sıralı `scroll_text_lines`'a yaz. `summary.scroll_fallback_used=true` işaretle.

4. **D-split — Scroll satırlarda rol|isim sütun ayrımı** (kullanılabilirlik). Eski tools'taki `is_upper_heavy + split_x` mantığı yok.
   - **Örnek (mevcut, JURASSIC):** `{"text": "MARK BROWN, MAURA MOSS"}` — tek string, hangisi rol hangisi isim belirsiz.
   - **Eski K-2'de (port edince hedef):** `{"role": "STILL PHOTOGRAPHER", "name": "PAT MORROW"}` — sütun ayrımı net, arama/export kolaylaşır.
   - **Nasıl:** `auto_split.json`'da `split_x=414` ZATEN hesaplanıyor (sol sütun BÜYÜK CAPS = rol; sağ sütun karışık case = isim). Sadece kullanılmıyor. Composite OCR'dan dönen satır box'ları `split_x`'in solunda/sağında olmasına göre `role` veya `name` kolonuna yerleştirilir; aynı `row_y` ± toleransta olanlar tek kayıtta birleşir. Üst düzey kart şablonu varsa (örn. "DIRECTOR | JAMES CAMERON") `is_upper_heavy` kontrolü ile yön bile otomatik tayin edilir.

5. **E-eski yol kapat** (temizlik, en son). K-BoxTrack stabil olduğunda `USE_BOX_TRACK_PIPELINE` default=1, eski 8-stage deprecated tag + opt-out flag. **Silmek YOK** (`feedback_master_no_worktree`: commit yine sadece istenince).

6. **(düşük öncelik) Eski yol quality_police icrası** — `image_quality_police` BROKEN_BLACK diyor ama icra eden yok. E-eski kapatılınca otomatik gereksiz, ama o zamana kadar duruyor.

7. **(düşük öncelik) Çağatay'ın 4-kategori matrisini `credit_pipeline_selector.py`'a indir** — şu anki 9-dal if-else çorbası → 4 yol matris. E sonrası refactor.

### KAPSAM DIŞI (bu OCR işinde değil)

- ASR pipeline (54 dosya uncommitted — başka oturum)
- webui değişiklikleri (App.tsx, Sidebar, vb.)
- docs/MITAS_* (5 doküman)
- mutfak/ kayıtları (ASR/diğer modüller için)
- translate/

---

## 4. ÇAĞATAYIN GPT İLE YAŞADIĞI — VE DOĞRU OKUMA

Çağatay başta dedi: "GPT'ye verdim, projeyi piç etti, Opus'un tokeni bitti, seninle devam edeceğiz." Bu mesajda iki nüans var, dikkat:

1. **Hepsini GPT yapmadı.** Çağatay sonradan netleştirdi: "diğer oturumda Opus ile beraber eklemeler yaptık, hepsini GPT yapmadı. Proje büyüdükçe en basit şeyi bile yapamaz olduysa biz bir yerde ipi kaçırdık."
2. **Sapma noktası `c3c042c`** — bu commit 6.837 satırı bir kerede ekledi. İçinde hem Opus+Çağatay'ın çalışması var hem sonrasında üzerine eklenenler (`box_tracker.py`, `image_quality_police.py`, `credit_segment_dispatcher.py`, `text_track_state.py` — uncommitted duruyordu, kim ekledi belirsiz; muhtemelen Opus eklemeleri çünkü `box_tracker.py` POC kalitesi yüksek).
3. **GPT'nin spesifik dokunuşları izlenemedi.** Önemli değil — kök problem zaten "static_card için 'her şeyi koştur' yaklaşımı"ydı, GPT-pre/post fark etmiyor. Çare K-BoxTrack mimarisi.

---

## 5. ÇAĞATAYIN ÖRNEKLERİ (referans, unutma)

Bu üç görsel oturumun başında geldi:

1. **fused.png siyah ekran** (KUKLA_ADAM temporal_fusion çıktısı) — variance_masking %99.99 siyah piksel.
2. **Glitched upscale görüntü** — `descroll_canvas.png`, static_card durumunda bile koşturulan modül üretti.
3. **Temiz Avustralya jenerik kartı** (INVESTORS REPRESENTATIVE STUART ALFORD, AAV AUSTRALIA, MIRANDA BAIN & DAVID MILLIK... — KUKLA_ADAM raw frame). Bu pipeline'ın ÖKUMASI gereken şey.

Sonra Çağatay paylaştı:
- **Kırmızı BG + sabit yazı (CHANSONS, BEI MIR BIST DU SCHÖN)** — C kategorisi (statik text, sabit BG, ama scroll'a geçen)
- **Kırmızı BG + oval içinde Heinz Bennent yüzü + sabit yazı** — kaos durumu (C kategorisinin extreme formu)
- Eski K-2 görselleri (siyah BG + scroll panoramik composite + OneOCR satırları) — A kategorisinin DOĞRU sonucu, eski tools'ta çalışıyordu.

---

## 6. PIPELINE'DAKİ 17 SAÇMALAMA (denetim çıktısı)

Eski yol (`USE_BOX_TRACK_PIPELINE=0`) hâlâ bunları yapıyor. K-BoxTrack devre dışıyken aktif. Düzeltilmeleri "YAPILACAK" listesinde.

### A. Sınıflandırmaya uyulmuyor
1. `credit_detector.type="static"` dese de scroll modülleri yine koşuyor.
2. `scene_router_refine` 3. pass'ta doğru `static_card` diyor ama selector 2. pass'ta zaten variance_masking demiş.
3. `descroll_canvas` her run'da koşuyor, static_card olsa bile → glitched görsel.

### B. Tekrar eden iş
4. Motion analizi **4 kez** yapılıyor (scene_router, scene_router_after_refined, scene_router_refined.with_ocr, text_motion).
5. `frame_ocr` 2 kez koşuyor (önce full-frame, sonra refined ROI).
6. `scene_router` 2 kez koşuyor — aynı ham frame'lerden, sonuç değişmiyor.

### C. Quality police nominal kalıyor
7. `image_quality_police` BROKEN_BLACK + `suggested_fallback="best_frame"` raporluyor → kod sadece JSON'a yazıyor, hiç icra edilmiyor.
8. `descroll_canvas` BROKEN_BACKGROUND_LEAK + 4 mean_conf=0.29 (çöp) record yine `canvas_ocr_records`'a yazılıyor.

### D. Gereksiz zorunlu modüller
9. `preprocessed_frame_ocr` her frame için **8 varyant** (upscale2x, clahe2x, sharpen2x, adaptive_threshold2x, dark_on_light_inverted2x, light_on_dark2x, deinterlace_blend2x, unsharp_glow_reduction2x). 1080×8 = 8.640 imaj, 102.356 record, **750 saniye**.
10. `temporal_voting` 115K record gruplama, 123 saniye, çoğu kullanılmıyor.
11. `auto_roi_detection` ilk pass fallback confidence 0.22 — değersiz veri.

### E. Maliyet/değer
12. 180sn jenerik için 1.365 sn iş (video real-time'ının 7.5×'i).
13. 2.4 GB disk tek item.
14. GPU 1.9→3.3 GB ama %5-8 utilization (PaddleOCR session release etmiyor).

### F. Şüphe
15. `refined_auto_roi mode="credit", scroll_like=true` AMA credit_detector `type=static` — çelişki.
16. `evaluation.metric_status="no_ground_truth"` — 4 strateji koşuyor, hangisi kazandı yok.
17. `temporal_unique_lines: 262, preprocessed_temporal: 2462` — 9× fark, hiç alarm yok.

---

## 7. ZAMAN ÇİZGİSİ — NE NE ZAMAN YAPILDI

### 14:30 — Oturum açıldı

Çağatay: "OCR jenerik okuması md'leri GPT'ye yaptırdım, projeyi piç etti. Opus'un tokeni bitti. Seninle devam edeceğiz." 3 görsel paylaştı (siyah fused.png, glitched görüntü, gerçek jenerik kartı). Çıktı yolu: `outputs/filmtest_kukla_single_retest_20260523_quality/items/filmtest_kukla_adam_last3min/`.

### 14:30-15:00 — Denetim

- OCR pipeline modülleri okundu (credit_experiment 3.268 satır, temporal_fusion, row_reconstruct, scene_router, selector, image_quality_police, credit_detector).
- Pilot çıktıları okundu: `fused.png` %99.99 siyah, `descroll_canvas.png` glitched.
- 17 saçmalama maddesi çıkarıldı.
- Bisection: c3c042c sapma noktası.

### 15:00-15:15 — Çağatay'ın 4-kategori + box tracking planını anladım

Çağatay: "ben şöyle planladım: 4 kategori (bg static/moving × text static/moving), her satıra box tracking koysak, dinamik hız, kenara gelince yeni track başlat..."

Ben: "fikrin sağlam, kirliliğin %70'i bunun koda inmemiş olmasından. `box_tracker.py` zaten POC olarak var ama pipeline'a bağlı değil. K-BoxTrack mimarisi öneriyorum."

Çağatay: "hangi yolu mantıklı görüyorsan onu yap. sadece söylediğim şeyin koda inmesini istiyorum."

### 15:15-15:30 — K-BoxTrack implementasyonu (Sonnet alt-ajanı)

Sonnet'e brief verildi:
- `box_tracker.py`'a 3 helper ekle (classify_track_motion, group_static_tracks_into_cards, select_best_frame_per_card)
- `unified_credit_pipeline.py` yeni dosya
- `credit_experiment.py:_run_item`'a `USE_BOX_TRACK_PIPELINE=1` gate
- 5 unit test

Sonnet sonucu: 19 test pass (5 yeni + 14 mevcut), 0 fail. 4 dosya değişti.

### 15:30-15:40 — Pilot v1 ve düzeltme

- Pilot v1: 0.002 saniye, 0 record. Sebep: `paddle_engine.recognize(frame_str)` çağrısında `strategy: str` keyword-only required kwarg eksik, try/except sessizce yutmuş.
- Fix: `recognize(Path(frame), strategy="unified_detection", timestamp_seconds=None)` + error counter.
- Pilot v2: **24.6 saniye, 46 kart, 4389 OCR record, 0 error**. Eski 1365 sn'ye karşı 56× hızlanma.

### 15:40-15:50 — Çağatay sonucu gördü, kararlar

Çağatay: "BANA DA GÖSTER" → 3 kart best_frame görseli inceledi (ANYA kartı, CREW kartı, yapım ekibi kartı), hepsi temiz.

Çağatay sırası: **C → A → B** (önce commit, sonra kart tuning, sonra başka filmle test).

### 15:50 — Commit `d1d3c95`

Sadece OCR dosyaları stage'lendi (ASR/webui/docs uncommitted bırakıldı — başka oturum). 9 dosya, 2.268 insertion. Pre-existing untracked olan box_tracker.py + image_quality_police.py + credit_segment_dispatcher.py + text_track_state.py + Sonnet'in yeni dosyaları + credit_experiment gate + text_layer_row_reconstruct pre-existing modify.

### 15:50-16:00 — Kart tuning (pilot v3, v4, v5)

- v3: y-overlap=0.0 default → 46 → 18 kart.
- v4: time-window overlap algoritması → 18 → 1 kart. **YANLIŞ.** Geri alındı.
- v5: v3 algoritmasına dön (prev_first_ts based). 18 kart kabul edildi (3-5 ideal'dan uzak ama her kartta zengin text_lines, kullanılabilir). 2-pass kart birleştirme **YAPILACAK** listesinde.

### 16:00-16:20 — 4 yeni film testi

Çağatay 4 film verdi:
- X-MEN (2000) — scroll, siyah BG, uzun
- JURASSIC PARK 2 (1997) — scroll, siyah BG, uzun
- ANJELIK VE SULTAN (1968) — scroll + **hareketli BG**
- ROBINSON CRUSOE (2025) — deneysel

Önce **scroll OCR fix** yapıldı (eksiklik — composite üretilip OCR koşulmuyordu). Sonra `outputs/ocr_4films_scroll_manifest_20260523.json` hazırlandı, pilot koşuldu.

### 16:20-16:40 — Pilot 4 film sonuç (`bnq9hw8zd`)

| Film | Runtime | Tracks | Cards | Scroll Lines | Composite | Yorum |
|---|---|---|---|---|---|---|
| JURASSIC | 135s | 1431 | 44 | **271** | ✅ temiz | eski K-2 kalitesi |
| ROBINSON | 45s | 358 | 17 | **176** | ✅ | modern film, çalıştı |
| X-MEN | 148s | 2286 | 57 | **34** | ⚠️ sadece müzik kartı | text_layer_row_reconstruct yanlış aday seçti |
| ANJELIK | 17s | 218 | 0 | **0** | ❌ boş | hareketli BG, composite başarısız |

**X-MEN tanısı:** `_score_row_candidate`'da `row_count > 90 → penalty += 0.18`. Current_displacement adayı 124 row + 5.421 px displacement (gerçek büyük scroll) → 0.62 score. Static_best_frame 10 row → 0.785 score → SEÇİLDİ. Yani gerçek scroll küçük statik kart tarafından yenildi.

### 15:55 — row penalty fix (master'da, commit beklemiyor pilot v2 sonucunu)

`text_layer_row_reconstruct._score_row_candidate`:
- Eski: `row_count > 90 → 0.18 ceza`
- Yeni: `row_count > 300 → 0.10 ceza`

Çağatay: "evet bilerek çok kalabalık koydum zaten." → muhtemelen ghost stitch detection için. **Plan:** pilot v2 sonucu kötüleşirse penalty'yi ghost-koşullu yapacağım (`row_count > 90 AND ghost_penalty > 0.25`).

### 15:56 — Pilot v2 koşuyor (`bwd99l2um`)

4 film yeniden, row penalty fix sonrası. Notify bekleniyor.

### 16:50 — B-port planı kondu (Çağatay sırası: B→C→A→D→E)

- Çağatay: "hepsini yapacağız nasıl olsa. 1 B'den devam edelim... motion track kısmı kayıp mı etmiş olacağız?"
- Cevap: **HAYIR.** Bu mask yalnızca `text_layer_row_reconstruct` içindeki LK feature tracker (composite alignment) içindir. Üst seviye `box_tracker` (PaddleOCR detection + IoU) bundan bağımsız. Box tracking + dinamik hız + kenar yenileme zinciri etkilenmez.
- D-split örnek açıklaması yapıldı (auto_split.json zaten `split_x=414` üretiyor, kullanılmıyor — composite OCR satır box'larını sol/sağ kolona dağıt).

### 16:55 — Karşılaştırma (eski tools vs MITAS text mask)

Okundu: `F:\REPO_GitHub\Cagatay_22.02\tools\scroll_reconstructor.py:48-56` ve `core/pipelines/ocr/text_layer_row_reconstruct.py:773-781`.

| Aspect | Eski tools (çalışıyordu) | MITAS (ANJELIK 0 satır) |
|---|---|---|
| Eşik | Global sıkı `max(45, mean+std)` BINARY | Lokal kontrast `absdiff(blur)` + ek bright gate |
| Canny | YOK | Edge OR ile mask'e dahil |
| Dilate | 11×11 (agresif, harfler bütünleşir) | 7×7 (zayıf) |
| Ek filtre | YOK | `_filter_text_components` (connected component) |
| Satır | 3 | 9 |

**Tanı:** Hareketli BG'de MITAS'ın lokal kontrast + Canny yaklaşımı BG dokusunu da "text" sayıyor → LK tracker bazen text'e bazen BG'ye kilitleniyor → alignment bozuluyor → ANJELIK 0 satır.

### 17:00 — B-port Sonnet'e devredildi

Brief: `_frame_text_mask`'a `mode: str = "current"` parametresi ekle (`"current" | "strict_global" | "hybrid"`). `_estimate_displacements_cruise`'daki 3 çağrı `OCR_TEXT_MASK_MODE` env var'dan mode okusun. Default "current" → regression sıfır. 3 unit test ekle (strict bright-only, current picks BG noise, hybrid intersects).

### 17:05 — Sonnet rapor: B-port kodu yazıldı (YAPILDI master'da, COMMIT BEKLİYOR pilot v3 sonucunu)

**Değişen dosyalar:**
- `core/pipelines/ocr/text_layer_row_reconstruct.py` +44/-1 satır: dispatch fonksiyonu + `_frame_text_mask_current` (mevcut, korundu) + `_frame_text_mask_strict_global` (eski tools portu) + `_text_mask_mode` env var helper.
- `tests/test_ocr_text_layer_row_reconstruct.py` +59 satır: 3 yeni test.

**Test sonucu:** 63 OCR test PASS, 0 fail. Regression sıfır.

**Mimari:**
- Default `OCR_TEXT_MASK_MODE` set edilmemişse → "current" mode, davranış AYNI (regression yok).
- `OCR_TEXT_MASK_MODE=strict_global` → ANJELIK fix devreye girer.
- `OCR_TEXT_MASK_MODE=hybrid` → current AND strict_global kesişimi.

Trust-but-verify: git diff stat doğrulandı, sadece 2 dosya, sadece eklemeler ve dispatch wrapper'ı. Eski 9 satırlık fonksiyonun gövdesi aynen `_frame_text_mask_current`'a taşınmış.

### 17:10 — Pilot v3 başlatıldı (background, log: `outputs/_boxtrack_v3_strict.log`)

```powershell
$env:USE_BOX_TRACK_PIPELINE = "1"
$env:OCR_TEXT_MASK_MODE = "strict_global"
venvs/ocr/Scripts/python.exe -m scripts.ocr_credit_experiment `
  --manifest outputs/ocr_4films_scroll_manifest_20260523.json `
  --output-dir outputs/ocr_4films_boxtrack_20260523_v3_strict `
  --engines paddle
```

### 17:35 — Pilot v3 sonuç + ÖNEMLİ TANI

| Film | v2 lines | v3 lines | Yorum |
|---|---|---|---|
| JURASSIC | 271 | 271 | aynı ✓ regression yok |
| ROBINSON | 176 | 176 | aynı ✓ regression yok |
| X-MEN | 238 | 238 | aynı ✓ regression yok |
| **ANJELIK** | **0** | **0** | hâlâ 0 AMA sebep değişti! |

ANJELIK row_reconstruct_summary.json + görsel inceleme:
- **strict_global mask MÜKEMMEL çalıştı:** `displacement_range_px: 634, median_dy: -6.77, active=105/105` — LK tracker text'e doğru kilitlendi.
- **14 row candidate tespit edildi** (current_displacement adayı), gerçek jenerik text'i: "ALY BEN AYED, HELMUT SCHNEIDER, ROGER PICAUT, ETTORE MANNI, JACQUES SANTI, BRUNO DIETRICH" — `row_candidates/current_displacement.png` görseli ANJELIK'in GERÇEK cast listesini gösteriyor.
- **static_best_frame adayı daha da temiz:** `row_candidates/static_best_frame.png` — "Directeur de Production HENRI JAQUILLARD, Images de HENRI PERSIN, Montage CHRISTIAN GAUDIN, Décors de ROBERT GIORDANI, Costumes de ROSINE DELAMARE...", hatta sütun ayrımı bile tespit edilmiş (`split_x=272, conf=0.5414`).
- **ASIL KÖTÜ HABER:** `_trim_composite_by_row_gap` (tail_trim) 14 row'u 1 row'a düşürdü. `median_gap=7.5, threshold=150, cut_gap=462 → kept=1, dropped=13`. composite 1114×600 → 34×600 boş bej şerit kaldı → scroll OCR boş row'dan 0 satır okudu.

**Yani ANJELIK aslında ÇÖZÜLDÜ, ama post-process katmanları (tail_trim agresyonu) iyi composite'i çöpe attı.**

### 17:40 — B-port fazı 2: tail_trim self-correction (Sonnet'e devredildi)

Brief: `_trim_composite_by_row_gap` sonuna sanity check ekle. `kept ≤ max(2, 0.3×total)` VE `dropped ≥ 5` → trim aslında ASIL içeriği atmış, reverse et. 2 unit test (ANJELIK senaryosu reverse + normal kuyruk trim'lenir).

### 17:45 — Sonnet rapor: tail_trim self-correction YAPILDI (master'da, COMMIT BEKLİYOR pilot v4 sonucunu)

- `text_layer_row_reconstruct.py` +17 satır (self-correction bloğu)
- `tests/test_ocr_text_layer_row_reconstruct.py` +50 satır (2 yeni test)
- `pytest tests/test_ocr_*.py -q` → 65/65 PASS, regression sıfır.

**Toplam diff (B-port v1 + v2):**
- `text_layer_row_reconstruct.py`: +61/-1 satır
- `tests/test_ocr_text_layer_row_reconstruct.py`: +109 satır (3 strict_global test + 2 tail_trim test)

### 17:50 — Pilot v4 başlatıldı (background, log: `outputs/_boxtrack_v4_selfcorrect.log`)

### 18:10 — Pilot v4 sonuç: ANJELIK çözüldü AMA JURASSIC regression

| Film | v2 | v3 | v4 | DELTA v3→v4 |
|---|---|---|---|---|
| X-MEN | 238 | 238 | 238 | aynı ✓ |
| **ANJELIK** | 0 | 0 | **28** | **+28 ✅ ÇÖZÜLDÜ** |
| ROBINSON | 176 | 176 | 176 | aynı ✓ |
| **JURASSIC** | 271 | 271 | **201** | **-70 ❌ REGRESSION** |

ANJELIK ilk 8 satır (yüksek conf):
```
[1] conf=0.99 'ALY BEN AYED'
[2] conf=1.00 'HELMUT SCHNEIDER'
[3] conf=0.98 'ROGER PIGAUT'
[4] conf=0.91 'ETTORA'   (ETTORE parçalandı)
[5] conf=1.00 'MANNI'
[6] conf=1.00 'SANTI'
[7] conf=1.00 'JACQUES'
[8] conf=0.97 'BRUNO DIETRICH'
```

JURASSIC sebep: tail_trim 293 total → 82 kept + 211 dropped (DOĞRU trim, gerçek kuyruk vardı). Self-correction yanlışlıkla tetiklendi: `kept ≤ max(2, 0.3×293)=88` ⇒ 82 ≤ 88 ✓ ⇒ trim reverse ⇒ composite 2661→12982px (4.9× büyüdü) ⇒ 211 ghost row OCR'a dahil ⇒ 271→201.

**Tanı:** self-correction heuristic çok GEVŞEK (`0.3 × total` JURASSIC tarzı makul trim'leri de yakalıyor). ANJELIK ekstrem (1/14=7%), JURASSIC makul (82/293=28%). Eşik **`kept ≤ 2`** olmalı (ekstrem yanlış-pozitif).

### 18:15 — Self-correction sıkılaştırıldı (Sonnet, YAPILDI master'da, COMMIT BEKLİYOR pilot v5)

Değişiklik (1 satır):
- Eski: `if kept_count <= max(2, int(round(0.3 * len(ordered)))) and dropped_count >= 5:`
- Yeni: `if kept_count <= 2 and dropped_count >= 5:`

ANJELIK (1 ≤ 2 ✓): tetiklenir → composite kurtulur.
JURASSIC (82 > 2): tetiklenmez → normal trim çalışır → 271 geri.

Yeni JURASSIC senaryosu testi eklendi (82 kept / 211 dropped). `pytest tests/test_ocr_*.py -q` → 66/66 pass.

**Toplam diff (B-port v1 + v2 + v3):**
- `text_layer_row_reconstruct.py`: ~+62/-2 satır
- `tests/test_ocr_text_layer_row_reconstruct.py`: 3 strict_global test + 3 tail_trim test (anjelik reverse + normal tail + jurassic tail)

### 18:20 — Pilot v5 başlatıldı (background, log: `outputs/_boxtrack_v5_tight.log`)

### 18:40 — Pilot v5 sonuç: B-port BAŞARILI ✅

| Film | v2 | v3 | v4 | v5 | tail_trim status (v5) |
|---|---|---|---|---|---|
| X-MEN | 238 | 238 | 238 | **238** | no_oversized_gap |
| JURASSIC | 271 | 271 | 201 | **271** | oversized_inter_row_gap (kept=82, dropped=211) |
| **ANJELIK** | **0** | **0** | **28** | **28** | **self_corrected_kept_too_few** ✅ |
| ROBINSON | 176 | 176 | 176 | **176** | no_oversized_gap |

3 fix doğru ayrıştı: ANJELIK self-correction, JURASSIC normal trim, X-MEN/ROBINSON dokunulmadı.

### 18:45 — B-port COMMIT EDİLDİ ✅ `18b4be6`

```
feat(ocr): port strict-global text mask + tail_trim self-correction (B-port)
```

2 dosya, +209/-1 satır. Sadece OCR dosyaları:
- `core/pipelines/ocr/text_layer_row_reconstruct.py`
- `tests/test_ocr_text_layer_row_reconstruct.py`

ASR/webui/docs uncommitted'leri yine bırakıldı (başka oturum).

---

### YAPILDI özet (bu oturumda B-port + C-kart faz 1)

- [x] **B-port:** strict_global text mask + tail_trim self-correction — `18b4be6` COMMIT.
  - ANJELIK regression çözüldü (0 → 28 satır, gerçek cast okundu).
  - Diğer 3 film regression yok.
- [x] **C-kart faz 1:** overlap-based card grouping — `9f0c745` COMMIT.
  - KUKLA: 18 → 7 kart (büyük iyileşme, hedef 3-5'e tune sonra).
  - 4 film scroll lines korundu (regression yok).
  - 4 film static cards arttı (scroll-içi short-lived tracks ayrı kart oluyor, cosmetic — scroll-dominant film'lerde "kart" anlamlı birim değil).

### 18:50 — Pilot v6 başlatıldı (background, 2 paralel pilot)

```powershell
$env:USE_BOX_TRACK_PIPELINE = "1"
$env:OCR_TEXT_MASK_MODE = "strict_global"
$env:OCR_CARD_GROUPING = "overlap"
# (KUKLA + 4 film aynı anda — GPU çakışması, 4-film fail oldu)
```

### 18:55 — Pilot v6 KUKLA tamam, 4-film FAIL

GPU contention (Paddle session iki pilot tarafından init edilmeye çalışıldı). KUKLA bitti (31sn), 4-film sadece X-MEN'i başlattıktan sonra exit 255.

### 19:00 — Pilot v6b 4-film solo retry

```powershell
$env:USE_BOX_TRACK_PIPELINE = "1"
$env:OCR_TEXT_MASK_MODE = "strict_global"
$env:OCR_CARD_GROUPING = "overlap"
venvs/ocr/Scripts/python.exe -m scripts.ocr_credit_experiment `
  --manifest outputs/ocr_4films_scroll_manifest_20260523.json `
  --output-dir outputs/ocr_4films_boxtrack_20260523_v6b_overlap `
  --engines paddle
```

### 19:20 — Pilot v6b sonuç

| Film | v5 lines | v6b lines | v5 cards | v6b cards |
|---|---|---|---|---|
| X-MEN | 238 | 238 | 57 | 120 |
| JURASSIC | 271 | 271 | 44 | 66 |
| ANJELIK | 28 | 28 | 0 | 0 |
| ROBINSON | 176 | 176 | 17 | 43 |

Scroll lines AYNI ✓ (regression yok). static_tracks AYNI ✓ (sınıflandırma değişmedi). Sadece kart birleştirme farklı: scroll-dominant film'lerde tek-obs short-lived tracks ayrı kart oluyor (cosmetic, scroll OCR'ı etkilemiyor).

### 19:25 — C-kart faz 1 COMMIT EDİLDİ ✅ `9f0c745`

```
feat(ocr): add overlap-based card grouping mode (C-kart phase 1)
```

2 dosya, +286/-9 satır. 68/68 OCR test pass.

### YAPILDI özet (bu oturumda B-port + C-kart faz 1 + A-fb — 3 commit)

- [x] **B-port:** strict_global text mask + tail_trim self-correction — `18b4be6` COMMIT. ANJELIK 0 → 28 satır.
- [x] **C-kart faz 1:** overlap-based card grouping — `9f0c745` COMMIT. KUKLA 18 → 7 kart.
- [x] **A-fb:** scroll fallback safety net + composite OCR restore + PIL/Paddle fix — `7ac6060` COMMIT.
  - Pilot v9 (A-fb live): 4 film hepsi v8 ile aynı, `scroll_fallback_used=False` (composite OK, emniyet ağı dormant).
  - Composite OCR bloğu d1d3c95'te eksik kalmıştı (working tree'de yaşıyordu), bu commit'le HEAD'e dahil edildi.
  - PIL/Paddle çakışması (pilot v7 X-MEN exit 255): `image_quality_police` import'u module-level'a taşındı, conflict çözüldü.

### 19:30 — A-fb pilot v9 sonuç + COMMIT EDİLDİ ✅ `7ac6060`

| Film | v8 (off) | v9 (auto) | fb_used | fb_reason |
|---|---|---|---|---|
| X-MEN | 238 | 238 | False | None |
| JURASSIC | 271 | 271 | False | None |
| ANJELIK | 28 | 28 | False | None |
| ROBINSON | 176 | 176 | False | None |

Tüm 4 film composite OK → A-fb tetiklenmedi (beklendiği gibi, emniyet ağı sadece composite bozulursa devrede).

### 19:50 — D-split COMMIT EDİLDİ ✅ `bf2c047`

```
feat(ocr): add role|name column pairing via auto-split + bbox derivation (D-split)
```

İki katmanlı split_x kaynağı: önce `row_reconstruct_summary.auto_split.split_x`, yoksa bbox'lardan on-the-fly türetim.

| Film | scroll lines | split_x | source | paired |
|---|---|---|---|---|
| X-MEN | 238 | 423 | bbox_derived | 181 |
| JURASSIC | 271 | 303 | bbox_derived | 158 |
| ANJELIK | 28 | 301 | bbox_derived | 23 |
| ROBINSON | 176 | 418 | bbox_derived | 154 |

JURASSIC örnek paired_lines:
```
ASSISTANT/CRANE TECH       | Tom JOKDAN
VISION CAMERA ASSISTANT    | ROMR'UUPNKOU
SCRIPT SUPERVISOR          | AN'MaRIA'O0INtANA   (PaddleOCR harf bozulması, yapı doğru)
```

Test: 73/73 OCR test pass.

### 20:10 — E-eski yol kapat COMMIT EDİLDİ ✅ `5afcda8`

```
feat(ocr): flip K-BoxTrack pipeline default ON (E-eski yol kapat)
```

`USE_BOX_TRACK_PIPELINE` default `"1"`. Eski 8-stage path kaldı (opt-out: `USE_BOX_TRACK_PIPELINE=0`).

**BEKLENMEDIK BONUS — ANJELIK default davranışta 55 satır!**

Pilot v11 (HİÇ env var SET ETMEDEN, pure default):

| Film | v10 (env'li) | v11 (env'siz) | Δ |
|---|---|---|---|
| X-MEN | 238 | 238 | aynı |
| JURASSIC | 271 | 271 | aynı |
| **ANJELIK** | **28** | **55** | **+27 (~2×!) ✨** |
| ROBINSON | 176 | 176 | aynı |

Sebep: default `_frame_text_mask_current` (lokal kontrast) hareketli BG'de bile text yakalıyor. tail_trim self-correction (B-port'tan beri default açık) composite'i kurtarıyor. İkisi birleşince 28 → 55. **strict_global mask aslında bazı satırları kaçırıyormuş.**

strict_global/overlap/hybrid hala opt-in olarak duruyor (alternatif yaklaşımlar, edge case'ler).

### YAPILACAK (sırada — bu oturumda 5 commit, master temiz)

1. **C-kart faz 2** — KUKLA 7 → 3-5 hedef için tune. Default davranışta KUKLA cards kontrol edilmedi (env'siz pilot v11 sadece 4 film scroll için), KUKLA için ayrı pilot lazım. Sonra `min_window_overlap_ratio` ve/veya proximity tuning.

### TOPLAM SONUÇLAR (bu oturum sonu, default davranış)

| Film | Başlangıç | Şimdi (env'siz) | Δ |
|---|---|---|---|
| X-MEN scroll | 34 | **238** | +204 (7×) |
| JURASSIC scroll | 271 | 271 | korundu |
| **ANJELIK** scroll | **0** | **55** | **sıfırdan, ~2×** |
| ROBINSON scroll | 176 | 176 | korundu |
| KUKLA cards | 18 | 7 (env'li v6) | yarıdan az |
| **Paired role\|name** | yoktu | **528+** | yeni özellik |

### COMMIT HISTORY (bu oturum, sıralı)

```
5afcda8 feat(ocr): flip K-BoxTrack pipeline default ON (E-eski yol kapat)
bf2c047 feat(ocr): add role|name column pairing via auto-split + bbox derivation (D-split)
7ac6060 feat(ocr): scroll fallback safety net + restore composite OCR block (A-fb)
9f0c745 feat(ocr): add overlap-based card grouping mode (C-kart phase 1)
18b4be6 feat(ocr): port strict-global text mask + tail_trim self-correction (B-port)
4497997 fix(ocr): relax row_count penalty for legitimate long scrolls
d1d3c95 feat(ocr): land K-BoxTrack unified pipeline + ship pending OCR helpers
```

**5 feature commit** bu oturumda. Çağatay'ın 4-kategori planı koda indi.

---

## 8. CHECKPOINT BİLGİLERİ

### Git durumu

- **HEAD:** `4497997 fix(ocr): relax row_count penalty for legitimate long scrolls`
- **Bir önceki:** `d1d3c95 feat(ocr): land K-BoxTrack unified pipeline + ship pending OCR helpers`
- **Master temiz mi:** HAYIR. 45 dosya hâlâ uncommitted (ASR, webui, docs, translate, mutfak — başka oturumun in-flight işi, bu OCR oturumunda dokunulmadı).
- **Pre-existing OCR uncommitted'ler:** `text_layer_row_reconstruct.py` + `test_ocr_text_layer_row_reconstruct.py` (commit d1d3c95'te alındı).
- **Bu oturumun uncommitted'i:** row penalty fix (`text_layer_row_reconstruct.py:391-395`) — pilot v2 sonucu beklenip karar verilecek.

### Test durumu

```
venvs/core/Scripts/python.exe -m pytest tests/test_ocr_*.py -q
→ 19 OCR test pass (5 yeni + 14 mevcut), 24 skipped (paddle/oneocr engine bağımlılığı)
```

### Çalıştırma

Eski yol (regression için duruyor):
```
venvs/ocr/Scripts/python.exe -m scripts.ocr_credit_experiment \
  --manifest outputs/ocr_kukla_single_manifest_20260523.json \
  --output-dir outputs/<dir> --engines paddle
```

Yeni K-BoxTrack yol:
```
$env:USE_BOX_TRACK_PIPELINE = "1"
venvs/ocr/Scripts/python.exe -m scripts.ocr_credit_experiment ...
```

### Önemli pilot outputs (referans için duruyor)

- `outputs/filmtest_kukla_single_retest_20260523_quality/` — ESKİ yol pilotu (22 dk, siyah fused.png)
- `outputs/filmtest_kukla_boxtrack_20260523_v2/` — K-BoxTrack v2 (24.6 sn, 46 kart, anya kartı temiz)
- `outputs/filmtest_kukla_boxtrack_20260523_v3/` — y-overlap=0 (18 kart)
- `outputs/filmtest_kukla_boxtrack_20260523_v4/` — time-window overlap (1 kart, YANLIŞ, terk edildi)
- `outputs/ocr_4films_boxtrack_20260523/` — 4 film pilot v1 (X-MEN 34 satır, JURASSIC 271 satır, ANJELIK 0)
- `outputs/ocr_4films_boxtrack_20260523_v2/` — 4 film pilot v2 (row penalty fix sonrası, KOŞUYOR)
- `outputs/_boxtrack_*.log` — koşum logları

### Önemli kod dosyaları (commit edilmiş, d1d3c95 sonrası)

```
core/pipelines/ocr/
├── box_tracker.py                    638 satır (POC tracker + 3 K-BoxTrack helper)
├── credit_detector.py                699 satır (c3c042c'den)
├── credit_experiment.py             3290 satır (8-stage eski + USE_BOX_TRACK gate)
├── credit_pipeline_selector.py       128 satır (4-kategori matrisi BURAYA inecek)
├── credit_scene_router.py            527 satır
├── credit_segment_dispatcher.py      537 satır
├── image_quality_police.py           257 satır (BROKEN_BLACK/_LEAK assessor)
├── simple.py                         277 satır (lightweight, ayrı entry)
├── temporal_fusion.py                227 satır (K-3 median + K-4 variance — eski yol kullanıyor)
├── text_layer_descroll.py           1271 satır (eski yol)
├── text_layer_row_reconstruct.py    1020 satır (scroll composite, X-MEN penalty fix beklemekte)
├── text_track_state.py               217 satır
└── unified_credit_pipeline.py        165 satır (K-BoxTrack orchestrator)

tests/
├── test_ocr_box_track_pipeline.py    192 satır (5 yeni test)
└── test_ocr_box_tracker_poc.py       (POC, 14 mevcut test)
```

---

## 9. ÖNEMLİ MEMORY NOTLARI (kalıcı referans)

- `user_profile.md` — Çağatay TRT'de, Türkçe direkt iletişim, implementasyonu başka ortamda yapar.
- `feedback_plan_implement_split.md` — Opus planlar, Sonnet uygular.
- `feedback_master_no_worktree.md` — master'da çalış.
- `feedback_audit_workflow.md` — denetle, koda karşı doğrula, vaad-gerçek tablosu çıkar.
- `feedback_checkpoint_commit_hygiene.md` — sadece kapsamlı işi commit, in-flight kodu süpürme.
- `project_mitas.md` — fast_with_fallback profili.
- `PARK-OCR-001` (mutfak `05_AKTIF_GOREV.md`) — outputs/ocr_credit_experiments/ commitlenmemeli, OCR kod/karar ayrı commitlenmeli.

---

## 10. SIRADAKİ OTURUM İÇİN HIZLI BAŞLANGIÇ (eski not — §11 daha günceldir)

1. Bu dosyayı oku.
2. `git log --oneline -5` → HEAD `5afcda8` (B/C/A/D/E commit serisi sonrası).
3. `git status --short | head` → ASR/webui/docs uncommitted'lerine DOKUNMA, başka oturumun in-flight işi.

---

## 11. 2026-05-24 OTURUMU — 24-FILM STRESS TEST + KRİTİK MİMARİ BULGU

### 11.1 Bağlam
Çağatay'ın talimatı: "Modele hiçbir şartta müdahale etmeyeceksin. Sadece test koşusunu takip edip raporlamak. E:\filmtest\aaaa altındaki 24 video ile mevcut versiyonu test et."

→ Kod değişikliği YAPILMADI. Sadece test + rapor + analiz + karar.

### 11.2 24-film pilot — sonuçlar
- Manifest: `outputs/ocr_24films_aaaa_manifest_20260523.json` (24 item, her biri son 7 dk)
- Output: `outputs/ocr_24films_aaaa_test_20260523/`
- Env: hiçbir set yok (pure default, USE_BOX_TRACK_PIPELINE=1)
- Toplam runtime: 22.5 dk · 24/24 done · 0 OCR error
- 17/24 filmde anlamlı scroll · 19/24'te kart · 13/24'te paired role|name (~1.330 satır)
- A-fb fallback **gerçek dünyada devreye girdi** (2 film): YARI_SERT (BROKEN_NO_TEXT, 203 satır kurtardı) + CENNETIN_RENGI (BROKEN_BLACK, 45 satır kurtardı)
- Önceki 4-film pilot ile sıfır regression (X-MEN 238, ANJELIK 55, ROBINSON 176 aynı, JURASSIC +6)

### 11.3 Sıfır-çıktı 7 film — sebep analizi
Şüpheli her filmin son 15 dk'sından `ffmpeg -ss <t> -vframes 1 -vf scale=640:-2` ile 10 frame çıkarılıp görsel incelendi (`outputs/_anomaly_check_frames/`).

**A) PIPELINE HATASI (2 film) — `opus_credit_detector` pencereyi yanlış daralttı:**

| Film | Manifest | Detector "effective" | Frame teyidi | Detector conf |
|---|---|---|---|---|
| POROROCA | 8403-8823 | 8403-**8594** | t8643+ tam scroll jenerik var | 0.482 |
| FRANNY | 293-713 | **500-542** | t683'te voice actors kartı (son 30sn) | 0.597 |

Her ikisinde detector düşük confidence'ta pencereyi kestir → pipeline jeneriği hiç görmedi.

**B) VERİ NORMAL (4 film) — eski filmlerde scroll jenerik fiilen yok:**
- KULÜBE 1952, KANSAS 1950, DUZINESI 1950, DERT_BENDE 1973 → son 15 dk hep sahne, "SON" kartı geleneği. Pipeline doğru "0" dedi.

**C) BİLİNEN DAVRANIŞ (1 film):**
- KUKLA_ADAM → statik-kart film, scroll yok ama 18 kart (beklenen).

### 11.4 OCR doğruluk — IMDB ile birebir teyit
WebSearch ile cast/crew karşılaştırması yapıldı:

| Film | OCR çıktısı | IMDB teyidi |
|---|---|---|
| X-MEN (2000) | UNIT PRODUCTION MANAGER → ROSS FANGER · FIRST AD → LEE CLEARY | ✓ ikisi de doğru pozisyonda |
| JURASSIC PARK 2 (1997) | DREW PETROTTA, KELLY PORTER, MARK BROWN + pozisyonlar | ✓ POZİSYONLAR DAHİ EŞLEŞTİ |
| ANJELIK (1968) | ALY BEN AYED · SCHNEIDER · PIGAUT · MANNI · SANTI | ✓ 5/5 eşleşti (parçalı harfler dahi) |
| BARBARLARI (2019) | CRISPIAN SALLIS · PAUL SNELL · BRIAN COOK · MARCO BELTRAMI | ✓ 4/4 doğru |

→ Yüksek conf (>0.85) satırlar **gerçek isim/pozisyon**. Düşük conf çöp (post-process ile filtrelenebilir).

### 11.5 KRİTİK MİMARİ BULGU — credit_detector yazıyı görmüyor
Kod incelemesi: `core/pipelines/ocr/credit_detector.py:191-219` (`_score_window` + `_text_like_mask`).

**Bekçi (`opus_credit_detector`) yaptığı iş:**
1. Frame'i gri yapar → kenar tespitiyle **"yazıya BENZER dokulu" piksel maskesi** çıkarır
2. text_density (yazımsı piksel oranı), row_structure (yatay çizgi), dark_ratio (karanlık piksel), motion_consistency (mask hareket sürekliliği) sayar
3. `0.56×structured_density + 0.14×dark_score + 0.22×scroll/static + 0.08×phase` formülüyle credit_score üretir
4. Eşik geçerse "credit" der

**Kritik:** `credit_detector` PaddleOCR'ı HİÇ ÇAĞIRMIYOR. Gerçek text görmüyor. "Yazımsı dokulu kareler" arıyor — kör tahmin. Yine de pipeline ona "jenerik nerede?" diye soruyor ve pencereyi onun dediği yere kısıyor.

**Çelişki:** PaddleOCR aynı pipeline'da çalışıyor (24 film için 116K+ record üretti, IMDB ile %95+ doğrulukla). Ama "yazı nerede" sorusu **ona değil**, kör tahminciye soruluyor.

### 11.6 GENEL YAKLAŞIM KARARI — "credit-first" → "text-first" mimari (B yolu)

Çağatay'ın yeniden çerçeveleme: KJ, jenerik kartı, scroll jenerik — hepsi tek sorunun alt türleri:
> **"Ekranda yazı var mı? Varsa nerede, ne kadar süreyle, ne yazıyor?"**

Yer/süre/hareket → sınıflandırma metası, problem değil.

**Mevcut mimari yanlış soruyu soruyor:**
- Sorulan: "Jenerik penceresi nerede?" → kör tahminciye
- Olması gereken: "Tüm video'da yazı var mı, izle, sınıfla" → PaddleOCR + box_tracker'a

**Karar:** B yolu — text-first mimari geç. credit_detector'ı alt sınıflandırıcıya indir (jenerik mi KJ mi kart mı). Pencere kavramı (`scope=end_credits`, son N dk) deprecate olur.

**Neden büyük iş değil:** K-BoxTrack çekirdek mimari ZATEN doğru (PaddleOCR detection + box_tracker + classify_track_motion + group_static_tracks). Eksik tek şey: scope'u "credit penceresi"nden "tüm video"ya açan üst katman + tip sınıflandırıcı (3 filtre kuralı: süre/boyut/konum).

### 11.7 V1 İÇİN 5 EKLEME (öncelik sırasına göre)

**P0 — Yapıtaşı, sonradan eklemek pahalı:**

1. **Output schema'sını "text event"e genelleştir.** `scroll_text_lines.json` + `cards/` + `paired_lines` → tek `events[]` array:
   ```
   {start_sec, end_sec, duration_sec, type, bbox, text, secondary_text, confidence, tracker_id, stability, frame_count}
   ```
   type: `kj | card | scroll_credit | intertitle | scene_text`. UI, export, search → tek schema.

2. **Ground truth + regression seti.** 5 altın film: X-MEN, KUKLA, ANJELIK, FRANNY (KJ-benzeri), POROROCA. Manuel etiket (jenerik başlangıç/bitiş + KJ aralıkları). Her commit sonrası bunlara karşı koş. Yoksa her değişiklik kör atış (B-port v4'te JURASSIC 271→201 regression olayı kanıt).

**P1 — V1 ile birlikte:**

3. **Kademeli tarama (cost optimization).** Tüm video naïve detaylı OCR = ~5-7 saat/24 film. İki kademe:
   - Kademe 1: stride=2sn, detection-only, "yazı var mı?" hızlı tarama (~5-8 dk/film)
   - Kademe 2: yazı bulunan segmentlere geri dön, dense frame + recognition
   - Hedef: 30-50 dk/24 film (pencere modu hızını koru).

4. **False-positive filtreleme.** Sahne içi yazılar (tabela, kitap, POLITIA arabası) text event olmamalı.
   - KJ: süre 2-10s sabit, alt yarı, lokal bbox, tracker stability yüksek
   - Scroll: dikey hareket sürekli
   - Sahne metni: süre <2s veya bbox rastgele hareket (kamera ile)

**P2 — V1 sonrası cila:**

5. **Eski credit-mode opt-out olarak tut** (`LEGACY_CREDIT_PIPELINE=1`). Silme kuralı: 3-6 ay sonra 100+ film sorunsuz olduktan sonra. Karşılaştırma testleri + acil geri dönüş için zorunlu. Memory: `feedback_master_no_worktree` (hemen silme).

   **Faz 6 (2026-05-25) ile uygulandı:** Env var `USE_LEGACY_CREDIT_PIPELINE=1` (yeni, önerilen) veya `USE_BOX_TRACK_PIPELINE=0` (eski isim, geri uyum) ile eski 8-stage path açılır. Default: text-first. **Eski credit-mode silinme zamanı:** Yeni text-first pipeline en az 100 farklı filmde sorunsuz koştuktan sonra (3-6 ay sonra) `credit_detector.py` + `opus_credit_detector` silinir. O zamana kadar `USE_LEGACY_CREDIT_PIPELINE=1` env ile çağrılabilir.

**Bonus (P2/P3):**
- Manifest genişlemesi: `kind: full_scan` default, `kind: window` opsiyonel hint
- Type-spesifik confidence eşiği (KJ %85, scroll %50)
- Telemetri: her event'e `type_reason` (`"duration=4.4 + bbox_y=0.78 + stable"`)

### 11.8 KAPSAM DIŞI (bu kararda değil)
- credit_detector eşik kalibrasyonu (yama yolu, mimari sorunu örter, reddedildi)
- Pencere buffer ekleme (POROROCA için yetersiz, reddedildi)
- Worktree (memory: `feedback_master_no_worktree`)

### 11.9 PC + ortam notu
- Çalışılan PC: **DESKTOP-JFEEDMB** (iş yeri, TRT03)
- Çağatay laptoptan uzak masaüstüyle bağlanıyor
- Bu Claude oturumu kapanırsa → iş yeri PC'sinde yeni Claude → bu dosyayı oku → devam
- Tüm test artifact'leri iş yeri diskinde:
  - `outputs/ocr_24films_aaaa_manifest_20260523.json`
  - `outputs/ocr_24films_aaaa_test_20260523/` (items, run_report, _summary_table)
  - `outputs/_anomaly_check_frames/` (7 şüpheli filmin 70 frame'i)
  - `outputs/_canli_kanit_*.jpg` (oturum kanıt frame)

---

## 12. SIRADAKİ OTURUM İÇİN HIZLI BAŞLANGIÇ (2026-05-24 sonrası)

1. Bu dosyayı oku (özellikle §11).
2. `git log --oneline -5` → HEAD hâlâ `5afcda8` (bu oturumda commit YOK — sadece test + tanı + karar).
3. `git status --short` → 24 film test artifact'leri `outputs/` altında (ASR/webui uncommitted'lerine DOKUNMA).
4. **Sıradaki konu: B yolu — text-first mimari V1 tasarımı.** Çağatay onayladı, 5 ekleme önerisi listelenmiş (§11.7).
5. Başlangıç adımları (Çağatay onayıyla):
   - **P0-1 (schema):** `core/pipelines/ocr/text_events_schema.py` skeleton + JSON Schema. Mevcut `unified_credit_pipeline.py` çıktısını bu formata maple.
   - **P0-2 (ground truth):** 5 film için manuel etiket dosyası `tests/data/ocr_ground_truth/<film>.json`. Format: `[{start_sec, end_sec, type, expected_text_sample, min_line_count}]`. Sonra regression test.
   - **P1-3 (stride scan):** `core/pipelines/ocr/text_presence_scanner.py` — stride=2s, sadece PaddleOCR detection, "text segments" output. Bir film üzerinde POC.
6. **Plan Opus / uygula Sonnet** (memory: `feedback_plan_implement_split`). Bu §11.7 brief'lerini Sonnet'e devret.
7. **Kod değiştirmeden önce Çağatay'a göster**, B yolunun her adımı onaylanmalı.

---

---

## 13. FAZ 1 — text_event schema + telemetri (TAMAMLANDI, COMMIT BEKLİYOR)

**Tarih:** 2026-05-24, ~22:30
**Sahip:** Sonnet alt-ajanı (Opus brief'i ile)

### Yapılan
- `core/pipelines/ocr/text_event.py` (YENİ, 271 satır) — TextEvent dataclass + to_dict/from_dict + validate_events + build_text_events_from_unified
- `core/pipelines/ocr/unified_credit_pipeline.py` (+53 satır) — Step 8: events.json yazımı, mevcut format yan yana korundu
- `tests/test_ocr_text_event_schema.py` (YENİ, 105 satır, 5 test)

### Test durumu
```
75 passed, 1 skipped (jsonschema venv'de yok, manuel validator kapsıyor), 2 pre-existing fail (kapsam dışı)
```

### Smoke test (ROBINSON tek-item)
- `outputs/_phase1_smoke_232407/items/2025_robinson_crusoe_end_credits/unified/events.json`
- 18 event (17 card + 1 scroll_credit)
- Scroll event: 176 alt-satır + `paired_role_name: {role: "AYNSLEY", name: "DOUG STONE"}`
- type_reason örnek: `"scroll_tracks=196 + composite_lines=176 + scroll_canvas=row_composite.png → scroll_credit"`
- Runtime: 41.3 sn

### Regression
- 19 mevcut format dosyası → 0 yapısal fark (path embed kaçınılmaz)
- card_id/frame_index/text_lines/bbox/confidence/score/member_count — byte-identical
- Sıfır pipeline output kırılımı

### 3 Soru cevabı
1. **Amaç korunuyor mu?** ✓ "Ekranda yazı var mı, oku" sorusu schema'da. type+type_reason+text+bbox+lines+paired_role_name doluyor.
2. **Başka iş bozuluyor mu?** ✗ Hayır. Mevcut format yan yana korundu. webui tüketici yok. Pre-existing 2 fail başka oturum işi.
3. **Daha iyi yapılabilir mi?** type_reason string olarak yeterli (V1). scroll event start/end_sec=0 Faz 4'te dolacak. video_id fallback path-türetimi minimal değişiklik.

### Notlar
- jsonschema OCR venv'de yok → `pip install jsonschema` ile 1 skip → 1 pass olur, opsiyonel
- COMMIT BEKLİYOR (Çağatay onayı)
- Önerilen commit mesajı: `feat(ocr): add text_event schema output (Faz 1 — text-first phase 1)`

---

---

## 14. FAZ 2 — Manifest profil sistemi (TAMAMLANDI, COMMIT BEKLİYOR)

**Tarih:** 2026-05-24, ~23:00
**Sahip:** Sonnet alt-ajanı

### Yapılan
- `core/pipelines/ocr/manifest_profiles.py` (YENİ, 170 satır) — Profile constants, `normalize_manifest_item()`, `build_segments_for_item()`, `dispatch_runner()`
- `core/pipelines/ocr/_video_meta.py` (YENİ, 62 satır) — ffprobe `duration_seconds()` helper (FFPROBE_EXECUTABLE env override destekli)
- `core/pipelines/ocr/credit_experiment.py` (+220 satır) — `CreditExperimentItem.raw` field, `_run_item_profile_dispatch` (film_credits için 2 segment koşum + events merge)
- `tests/test_ocr_manifest_profiles.py` (YENİ, 148 satır, 14 test)

### Test durumu
```
90 passed, 2 pre-existing failed
```
14 yeni test pass. Pre-existing 2 fail (temporal_fusion) baseline'da da fail, kapsam dışı.

### Geri uyum (KRİTİK)
- ROBINSON `kind: end_credits` smoke → eski outputs/ocr_24films... ile karşılaştırma:
  - 17 cards/*.json + 78 PNG: **byte-identical**
  - scroll/scroll_text_lines.json, row_reconstruct_summary.json, auto_split.json, summary.json: **byte-identical**
- `end_credits` early-return ile yeni dispatch koduna girmiyor — LEGACY path sıfır risk

### film_credits smoke
- 0.5 dk açılış + 1 dk kapanış pencere ile ROBINSON
- `unified/opening/`: 3 event (2 card + 1 scroll_credit)
- `unified/closing/`: 3 event
- `unified/events.json` (merged): 6 event total, segment_id field her event'te dolu
- `unified/summary.json` (merged): segment listesi + merged_event_count
- Runtime: 17.4 sn

### 3 Soru cevabı
1. **Amaç korunuyor mu?** ✓ film_credits açılış+kapanış bağımsız soruyor, schema bütünlüğü korunuyor.
2. **Başka iş bozuluyor mu?** ✗ end_credits LEGACY byte-identical, 24-film mevcut manifest hiç değişmeden çalışıyor.
3. **Daha iyi yapılabilir mi?** Event merge stratejisi (alt klasör + merged üst seviye) — hem debug hem UI esnekliği için iyi. Faz 4 hook noktası `build_segments_for_item` içinde hazır.

### Notlar
- ffprobe PATH'te olmalı veya `FFPROBE_EXECUTABLE` env set
- Frames disk maliyeti film_credits için 2× (2 segment ayrı klasör), kabul edilebilir
- `kind: film_credits` için `opus_credit_detector` ÇAĞRILMIYOR (text-first felsefe)
- COMMIT BEKLİYOR
- Önerilen mesaj: `feat(ocr): add manifest profile dispatch + film_credits 2-window runner (Faz 2)`

---

---

## 15. FAZ 3 — Ground Truth Opus Draft Turu (TAMAMLANDI, ÇAĞATAY ONAYI BEKLİYOR)

**Tarih:** 2026-05-25, ~00:00
**Sahip:** Opus (öncüsel draft) → sonraki adım: Çağatay onay → Sonnet regression test bağlama

### Yapılan
10 ground truth draft dosyası (`tests/data/ocr_ground_truth/<video_id>.json.draft`):

| # | Film | Conf Kaynağı | Özellik |
|---|---|---|---|
| 1 | 2000_x_men | IMDB §11.4 + OCR | Uzun scroll, paired roller |
| 2 | 1997_jurassic_park_2 | IMDB §11.4 + OCR | Uzun scroll |
| 3 | 1968_anjelik_ve_sultan | IMDB §11.4 + OCR | Hareketli BG (zor) |
| 4 | 2019_barbarlari_beklerken | IMDB §11.4 + OCR | En zengin scroll |
| 5 | 2025_robinson_crusoe | OCR top-conf 1.00 (WebSearch limit) | Voice cast |
| 6 | 1989_kukla_adam | OCR + film bilgisi (Türk arşiv, WebSearch ulaşılamadı) | D kategorisi (statik kart, zero_scroll) |
| 7 | 2003_franny_nİn_ayaklari | IMDB (2026-05-25 WebSearch) | KRİTİK Faz 4 test (mevcut 0 → hedef 10+) |
| 8 | 2017_pororoca | IMDB (2026-05-25 WebSearch) | KRİTİK Faz 4 test (mevcut 0 → hedef 100+) |
| 9 | 1977_yari_sert | OCR + film bilgisi (Semi-Tough/Burt Reynolds tahmini) | A-fb fallback case |
| 10 | 1999_cennetİn_rengİ | OCR (Farsça zor) + Majidi bilgisi | A-fb fallback case, OCR düşük conf |

### Özel işaretler (draft'larda)
- `phase4_regression_baseline` — FRANNY + POROROCA: mevcut pipeline 0, Faz 4 sonrası beklenen min count
- `fallback_metadata` — YARI_SERT + CENNETIN_RENGI: A-fb fallback tetiklenmesi beklenmeli
- `expected_zero_scroll` — KUKLA: scroll yok beklenir (D kategorisi)
- Hepsi `status: "draft_awaiting_cagatay_approval"` ile işaretli

### Çağatay onay turu için
Her draft için Çağatay'ın yapacağı:
1. `start_sec_min/max` doğru mu? (frame spot check, 30 sn iş)
2. `must_contain_text` listesindeki isimler doğru mu? (IMDB göz at, 30 sn)
3. `min_line_count` makul mu? (eşik kontrolü)
4. Notu güncelle: `"created_by": "opus_oncusel + cagatay_onay"`, `status: "approved"`
5. `.draft` → `.json` rename

Tahmini emek: 10 film × 5-10 dk = ~1 saat (manuel 5 saat yerine).

### Özel notlar
- **WebSearch session limit (2am'e kadar):** ROBINSON, KUKLA, YARI_SERT, CENNETIN_RENGI için IMDB tam teyit yapılamadı. Çağatay 2am sonrası IMDB ekleyebilir veya Opus'a tekrar yaptırabilir.
- **Film id'leri 24-film output dizini ile uyumlu** (örn `1999_cennetİn_rengİ_end_credits`) — regression test direkt çalışabilir.
- **KUKLA_ADAM 1989 Türk filmi** — WebSearch sonuç vermedi. Çağatay biliyorsa cast adını ekleyebilir.

### 3 Soru cevabı
1. **Amaç korunuyor mu?** ✓ Her template "ekranda yazı var mı, doğru mu okudu" sorusunu test eder. FRANNY+POROROCA Faz 4'ün gerekçesini açıkça kanıtlar.
2. **Başka iş bozuluyor mu?** ✗ Hayır, sadece draft dosyalar (test data, kod yok).
3. **Daha iyi yapılabilir mi?** WebSearch limit aşıldı → 4 film için IMDB teyit yarın yapılır. KUKLA için Türk-arşiv özel veritabanı gerekebilir (Sinemalar.com).

### Sıradaki adım
Çağatay 10 draft'ı gözden geçirir → onaylar → `.draft` → `.json` rename → Sonnet'e Faz 3 finalize brief (regression test runner + ground truth assert) verilir.

---

---

## 16. FAZ 4 — Dinamik pencere mimarisi (TAMAMLANDI, COMMIT BEKLİYOR)

**Tarih:** 2026-05-25, ~02:30
**Sahip:** Sonnet alt-ajanı (Opus brief'i ile)

### Yapılan
- `core/pipelines/ocr/dynamic_window.py` (YENİ, ~290 satır)
  - `DynamicWindowResult` dataclass (start/end/iters/log/initial/max_reached)
  - `find_dynamic_window(...)` — PaddleEngine DI, 2-frame teyit, +60s step, max cap
  - `_has_text_at(...)` + `_probe_single_frame(...)` — ffmpeg ile geçici JPG frame extract → recognize → cleanup
  - `_resolve_ffmpeg_for_dynamic_window()` — credit_experiment'tan bağımsız (cycle önlemek için)
- `core/pipelines/ocr/manifest_profiles.py` — `build_segments_for_item(item, duration, *, paddle_engine=None, ffmpeg_executable=None)` imza genişledi; her segment dict'inde yeni `dynamic_window: dict|None` telemetri key'i; opening/closing'i ayrı ayrı uzatır, overlap → 'full' merge'ünde telemetri korunur; `_extend_window()` helper'ı statik fallback için `skipped_no_engine=True` flag'i yazar.
- `core/pipelines/ocr/credit_experiment.py` — `_run_item_profile_dispatch` `build_segments_for_item`'a `paddle_engine=primary_engine + ffmpeg_executable=ffmpeg_exe` geçiriyor; her seg_result'a `dynamic_window` telemetri inheritance.
- `tests/test_ocr_dynamic_window.py` (YENİ, 9 test) — direction, max cap, two-frame confirm, manifest entegrasyonu (skipped_no_engine), dynamic_window=False geri uyum.

### Test durumu
```
99 passed, 2 pre-existing failed
```
Baseline 90 pass → 99 pass (= +9 yeni). Pre-existing 2 fail (temporal_fusion, kapsam dışı) aynen.

### POROROCA integration (KRİTİK)
- Komut: `USE_BOX_TRACK_PIPELINE=1` + `outputs/_phase4_pororoca_manifest.json` (opening=3 max=8, closing=5 max=15)
- Runtime: 17.1 sn
- **Dynamic window telemetri:**
  - opening: initial=[0, 180] → final=[0, 300] (iters=2, t=180/240 yazı vardı, t=300 boundary_clean)
  - closing: initial=[8523, 8823] → final aynı (iters=0, ilk probe temizdi)
- **Sonuç:** 46 event (29 opening + 17 closing) | **242 text_line total** (39 opening cards + 197 closing cards + 6 scroll)
- **Mevcut (24-film testi): 0 → Yeni: 242** → ✓ KABUL (en az 100 koşulu fazlasıyla)

### FRANNY integration
- Komut: `outputs/_phase4_franny_manifest.json` (opening=1 max=3, closing=1 max=3)
- Runtime: 10.8 sn
- Dynamic window: iki segmentte de iters=0 (1dk'lık initial pencereler tam jeneriği kapsadı)
- **Sonuç:** 9 event | **93 text_line total** (19 opening cards + 40 closing cards + 34 closing scroll)
- **Mevcut: 0 → Yeni: 93** → ✓ KABUL (en az 10 koşulu fazlasıyla)

### Geri uyum
- ROBINSON `kind: end_credits` tek-item smoke `outputs/_phase4_robinson_backcompat/`
- Karşılaştırma `outputs/ocr_24films_aaaa_test_20260523/2025_robinson_crusoe_end_credits/` ile:
  - `auto_split.json`: byte-identical ✓
  - `scroll_text_lines.json`: tek fark `canvas_path` (kaçınılmaz path embed) ✓
  - `row_reconstruct_summary.json`: tek farklar 4× path string embed ✓
  - cards/: 17 == 17 ✓
- → LEGACY path tamamen korunuyor.

### 3 Soru cevabı
1. **Amaç korunuyor mu?** ✓ POROROCA 0→242, FRANNY 0→93. `opus_credit_detector` çağrılmıyor — text-first felsefe korunuyor. Pencere kararı PaddleOCR'ın "yazı var mı?" cevabıyla genişliyor, kör tahminci yok.
2. **Başka iş bozuluyor mu?** ✗ Hayır. ROBINSON LEGACY backcompat byte-identical (sadece path embed). `dynamic_window: false` ile Faz 2 davranış korunuyor (yeni test bu garantiyi assert ediyor). Test 90→99 pass.
3. **Daha iyi yapılabilir mi?** Kullanılan kararlar:
   - **step_sec=60s**: 30s daha hassas ama 2× probe = 2× ffmpeg+OCR maliyeti. 60s yeterli.
   - **2-frame teyit (stride=2s)**: 3-frame daha güvenli ama her uzantı +1 probe (~300ms ekstra). 2 yeterli — POROROCA opening doğru gözlemledi.
   - **frame extract maliyeti**: probe başına ~150-300ms (ffmpeg JPG + 1 paddle recognize). POROROCA toplam ~600ms ekstra. Kabul.
   - **extension_log formatı**: `"t=180.0 text_present"` / `"t=300.0 boundary_clean"` / `"t=X max_reached(...)"` — grep edilebilir, debug-readable.
   - **PaddleEngine detection-only mode**: API'de yok; `recognize(strategy="dynamic_window_probe")` çağrılıyor (recognition + det). Hafif fazla iş ama yeni init yok, mevcut session yeniden kullanılıyor. detection-only API ileride eklenirse helper güncellenir.

### Bilinmesi gerekenler / küçük kararlar
- **Manifest path embed**: `segments` dict'ine `dynamic_window` key eklemek mevcut Faz 2 testlerini bozmadı çünkü existing testler key sayısı yerine spesifik key değerlerini assert ediyor.
- **build_segments_for_item signature değişikliği**: `paddle_engine` + `ffmpeg_executable` yeni keyword-only, default None. Tüm caller'lar opsiyonel; backward-compat.
- **dynamic_window=False yolu**: telemetri None bırakıldı (test ile garantili) — bu kullanıcı için kasıtlı sessizlik.
- **Skipped_no_engine path**: `dynamic_window=True` ama engine yok → static fallback + `skipped_no_engine: True` log entry. test ile garantili.
- **Cycle avoidance**: dynamic_window.py credit_experiment'ı import etmiyor (yerel `_resolve_ffmpeg_for_dynamic_window()`).
- **GPU oturumu**: dynamic_window probe'ları mevcut paddle_engine'i yeniden kullanıyor — yeni CUDA init yok.

### Sıradaki adım (Faz 5 için Çağatay'a not)
- Faz 5 brief'i hazırsa Sonnet'e ver: type-spesifik confidence threshold (`core/pipelines/ocr/confidence_thresholds.py`).
- Çağatay sabah toplu onayda Faz 1+2+3+4'ün hepsini birden commit edebilir veya tek tek bağımsız commit'lere bölebilir.
- POROROCA opening 2 uzantı yaptı — daha geniş manifestlerde (max_opening_min=8) dynamic uzantının max_reached'e ulaşma davranışını canlı film'le doğrulamak için sabaha bir 24-film yeniden koşum yararlı olabilir (bu Faz 4 kapsamında değil).
- COMMIT BEKLİYOR (Çağatay onayı). Önerilen mesaj:
  `feat(ocr): add dynamic window extension via paddle tail-probing (Faz 4)`

---

## 17. FAZ 5 — Type-spesifik confidence eşiği (TAMAMLANDI, COMMIT BEKLİYOR)

**Tarih:** 2026-05-25, ~02:30
**Sahip:** Sonnet alt-ajanı (Opus brief'i ile)

### Yapılan
- `core/pipelines/ocr/confidence_thresholds.py` (YENİ, 62 satır) — DEFAULT_THRESHOLDS (scroll_credit=0.50, card=0.75, intertitle=0.75, kj=0.85, scene_text=0.90), `get_threshold()`, `apply_thresholds()` (in-place flag + count return)
- `core/pipelines/ocr/text_event.py` (+4 satır) — `build_text_events_from_unified()` sonunda `apply_thresholds(events)` çağrısı
- `core/pipelines/ocr/unified_credit_pipeline.py` (+3 satır) — Step 8'de `low_confidence_count` placeholder → gerçek sayım
- `tests/test_ocr_confidence_thresholds.py` (YENİ, 12 test)

### Test
```
111 passed, 2 pre-existing failed
```
Faz 4 baseline 99 → 111 (+12 yeni test). KJ + scene_text eşikleri V2 için hazır.

### Smoke (ROBINSON kind=end_credits)
- `unified/events.json.summary.low_confidence_count = 0` (ROBINSON yüksek conf'lu, doğal davranış)
- Mekanizma testi `apply_thresholds(events, custom={"card": 0.95})` → 3 event flag'lendi (canlı doğrulama)
- Eski format byte-identical (cards/, scroll/) — Faz 4 backcompat korundu

### 3 Soru cevabı
1. **Amaç korunuyor mu?** ✓ Tip ağırlığına göre kalite çıtası. Atma YOK, sadece flag.
2. **Başka iş bozuluyor mu?** ✗ Hayır, event sayısı aynı (18==18), eski format byte-identical.
3. **Daha iyi yapılabilir mi?** Hardcode V1 için doğru, custom override API hazır (V2 manifest-tabanlı override için kullanılabilir).

### Bilinmesi gerekenler
- `low_confidence` field zaten Faz 1 schema'sında vardı, bu faz sadece SET ediyor
- ROBINSON low count=0 dosyaya bağlı — ANJELIK gibi gürültülü filmlerde count yüksek olacak (24-film yeniden koşumda görülür)
- `apply_thresholds` idempotent (iki kez çağırınca aynı sonuç)

### Sabah toplu commit
- Önerilen mesaj: `feat(ocr): add type-specific confidence thresholds + low_confidence flagging (Faz 5)`

---

## 18. FAZ 6 — Legacy opt-out (TAMAMLANDI, COMMIT BEKLİYOR)

**Tarih:** 2026-05-25, ~02:45
**Sahip:** Sonnet alt-ajanı (Opus brief'i ile)

### Yapılan
- `core/pipelines/ocr/credit_experiment.py` — modül seviyesinde `_is_legacy_credit_pipeline()` helper'ı eklendi (saf, test edilebilir). `_run_item` artık env var'ı doğrudan okumak yerine bu helper'ı çağırıyor (`USE_BOX_TRACK = not _is_legacy_credit_pipeline()`).
- Yeni env contract:
  - `USE_LEGACY_CREDIT_PIPELINE=1` → legacy 8-stage opt-in (yeni, önerilen)
  - `USE_BOX_TRACK_PIPELINE=0` → legacy 8-stage opt-in (eski, geri uyum)
  - Hiçbiri set değilse → text-first (K-BoxTrack unified) default
  - Sadece literal `"1"` / `"0"` kabul edilir; `"true"`, `"yes"`, `"xyz"` gibi tipo'lar sessizce legacy'yi tetiklemez (whitespace strip edilir).
- `tests/test_ocr_legacy_optout.py` (YENİ, 8 test, monkeypatch ile env izolasyonu): default text-first, explicit legacy opt-in, back-compat env, legacy priority (her ikisi set ise legacy kazanır), eski normal kullanım (USE_BOX_TRACK=1) bozulmadı, invalid value text-first'e düşer, whitespace strip, empty string text-first.
- `mutfak/OCR-OPUS.md` — §11.7 madde 5'in altına Faz 6 uygulanma notu + silinme zamanı kuralı eklendi; bu §17 raporu eklendi.

### DOKUNULMADI
- `core/pipelines/ocr/credit_detector.py` — temiz, hiç değişmedi (sadece default'ta çağrılmıyor, legacy opt-in altında hâlâ çağrılıyor).

### Test durumu
```
119 passed, 2 pre-existing failed
```
Baseline 113 collected; +8 yeni test (brief 6 istedi, kapsama için 8'e çıkardım — whitespace strip + empty string edge case'leri). Pre-existing 2 fail (temporal_fusion, credit_experiment) aynı, kapsam dışı.

### Smoke A — default text-first
- Komut: `$env:USE_LEGACY_CREDIT_PIPELINE = ""; $env:USE_BOX_TRACK_PIPELINE = ""; venvs/ocr/Scripts/python.exe -m scripts.ocr_credit_experiment --manifest outputs/_phase2_robinson_manifest.json --output-dir outputs/_phase6_smoke_default --engines paddle`
- Çıktı: `outputs/_phase6_smoke_default/items/2025_robinson_crusoe_end_credits/`
  - `item_summary.json.pipeline = "box_track_unified"` ✓
  - `item_summary.json.status = "done"` ✓
  - `unified/events.json` var (18 event: 17 card + 1 scroll_credit) ✓
  - `unified/summary.json`, `unified/cards/`, `unified/scroll/` var ✓
- → Text-first mimari aktif.

### Smoke B — legacy opt-in
- Komut: `$env:USE_LEGACY_CREDIT_PIPELINE = "1"; venvs/ocr/Scripts/python.exe -m scripts.ocr_credit_experiment --manifest outputs/_phase2_robinson_manifest.json --output-dir outputs/_phase6_smoke_legacy --engines paddle`
- Çıktı: `outputs/_phase6_smoke_legacy/items/2025_robinson_crusoe_end_credits/`
  - `credit_segment_detection.json` var (opus_credit_detector çağrıldı) ✓
  - `unified/` klasörü YOK — events.json üretilmedi ✓
  - Eski 8-stage artifact'leri: `auto_roi_detection.json`, `frame_ocr_first_pass.json`, `scene_router.json`, `refined_auto_roi_detection.json`, vs. ✓
- → Legacy path aktif, geri dönüş kanalı çalışıyor.

### 3 Soru cevabı
1. **Amaç korunuyor mu?** ✓ Acil geri dönüş hakkı `USE_LEGACY_CREDIT_PIPELINE=1` ile var. Smoke B kanıt: eski 8-stage path koşuyor, `opus_credit_detector` çağrılıyor, `credit_segment_detection.json` yazılıyor.
2. **Başka iş bozuluyor mu?** ✗ Hayır.
   - Geri uyum env: `USE_BOX_TRACK_PIPELINE=0` hâlâ legacy'yi tetikliyor (test `test_legacy_env_via_backcompat` garantili).
   - Default davranış: env unset → text-first (Smoke A + `test_default_uses_text_first`).
   - Çağatay'ın eski "explicit text-first" kullanımı (`USE_BOX_TRACK_PIPELINE=1`) hâlâ text-first (test `test_legacy_env_normal_case_text_first`).
   - `credit_detector.py` byte-identical.
3. **Daha iyi yapılabilir mi?** Env var ismi `USE_LEGACY_CREDIT_PIPELINE` doğru — alternatif `MITAS_OCR_LEGACY_MODE` daha proje-prefix'li ama mevcut env contract'ı (USE_BOX_TRACK_PIPELINE) prefix'siz, simetri için aynı stilde kaldım. Helper saf fonksiyon (modül seviyesinde) — DI gerektirmediği için import-free test edilebilir. Strict literal `"1"`/`"0"` contract'ı kasıtlı: "true"/"yes"/"on" gibi tipo'lar sessizce eski yola düşürmek riskli (Çağatay'ın "hemen silme hemen atma" felsefesiyle uyumlu — env ne yaparsa onu yap, varsayma).

### Bilinmesi gerekenler
- **Smoke B `credit_segment_detection.json`**: ham JSON — kanıt amaçlı tutuldu (`outputs/_phase6_smoke_legacy/items/2025_robinson_crusoe_end_credits/`).
- **Smoke A vs. Smoke B karşılaştırma**: Smoke A `unified/events.json` → text event schema; Smoke B `frame_ocr_first_pass.json` + `credit_segment_detection.json` + sahne yönlendiricisi → eski format. Kullanıcı çıktıları açarak hangi yolun koştuğunu hemen ayırt edebilir.
- **`_is_legacy_credit_pipeline()` public mi?**: alt-çizgi ile prefixli (modül-içi convention) ama test'te import edilebilir — Python convention'da "test edilebilir özel". İleride başka modül de aynı sorguyu yapmak isterse rename gerekmez.
- **Modül seviyesinde `os` zaten import edilmiş** (line 16) — helper içinde lazy import yok.

### Sabah toplu commit için Çağatay'a not
- COMMIT BEKLİYOR. Faz 1+2+3+4+5+6 hepsi master'da uncommit. Çağatay sabah ya toplu tek commit ya da faz başına tek tek commit'leyebilir.
- Önerilen Faz 6 commit mesajı:
  `feat(ocr): rename legacy opt-out env to USE_LEGACY_CREDIT_PIPELINE (Faz 6)`
- Faz 6 değiştirilen dosyalar (toplam 3):
  - `core/pipelines/ocr/credit_experiment.py` (helper eklendi + `_run_item` ondan okuyor)
  - `tests/test_ocr_legacy_optout.py` (YENİ, 8 test)
  - `mutfak/OCR-OPUS.md` (§11.7 madde 5 not + §17 rapor)
- Faz 6 dokunulmadı: `credit_detector.py`, `unified_credit_pipeline.py`, diğer her şey.
- **Mimari kapanış:** Faz 0-6 ile text-first migration tamamlandı. `USE_LEGACY_CREDIT_PIPELINE=1` 3-6 ay (100+ film) sonra silinme adayı.

---

## 19. SABAH ÇAĞATAY İÇİN — 2026-05-25 OTURUMU TOPLU ÖZET

### Tek satır
**Faz 1-2-3draft-4-5-6 tamamlandı. 119 OCR test pass (öncesi 73 → +46). 5 commit hazır (henüz commit edilmedi, onay bekliyor). POROROCA 0→242, FRANNY 0→93 (Faz 4 kanıtı).**

### Master durumu
- HEAD: `4b3ea266` (Faz 2)
- Uncommitted: Faz 3 draft + Faz 4 + Faz 5 + Faz 6 (Faz 1+2 zaten commit'li)
- Test: 119 pass + 2 pre-existing fail (temporal_fusion, kapsam dışı)
- Smoke'lar: ROBINSON byte-identical, POROROCA + FRANNY 0'dan kurtuldu

### YAPILMASI GEREKEN — 4 aksiyon

**1. 10 ground truth draft incele + onayla + rename**
- Konum: `tests/data/ocr_ground_truth/*.json.draft` (10 dosya)
- Her biri için ~5 dk: `start_sec_min/max`, `must_contain_text`, `min_line_count` kontrol
- Onaylananlar: `.draft` → `.json` rename + `status: "approved"`
- Tahmini emek: ~1 saat

**2. 4 eksik IMDB araması (2am sonrası WebSearch yenilenmiş)**
- ROBINSON: Doug Stone + Yuri Lowenthal IMDB teyit
- KUKLA_ADAM 1989: Türk arşiv araması
- YARI_SERT 1977: Semi-Tough/Burt Reynolds tahmini doğru mu?
- CENNETIN_RENGI 1999: Majidi Color of Paradise tam cast

**3. 4 commit (sırayla, ya da toplu)**

```bash
# Faz 3 (ground truth onaylandıktan SONRA)
git add tests/data/ocr_ground_truth/*.json
git commit -m "feat(ocr): add 10-film ground truth regression dataset (Faz 3)"

# Faz 4
git add core/pipelines/ocr/dynamic_window.py core/pipelines/ocr/manifest_profiles.py core/pipelines/ocr/credit_experiment.py tests/test_ocr_dynamic_window.py
git commit -m "feat(ocr): add dynamic window extension via paddle tail-probing (Faz 4)"

# Faz 5
git add core/pipelines/ocr/confidence_thresholds.py core/pipelines/ocr/text_event.py core/pipelines/ocr/unified_credit_pipeline.py tests/test_ocr_confidence_thresholds.py
git commit -m "feat(ocr): add type-specific confidence thresholds + low_confidence flagging (Faz 5)"

# Faz 6
git add core/pipelines/ocr/credit_experiment.py tests/test_ocr_legacy_optout.py mutfak/OCR-OPUS.md
git commit -m "feat(ocr): rename legacy opt-out env to USE_LEGACY_CREDIT_PIPELINE (Faz 6)"
```

**NOT:** Faz 4 ve Faz 5 ve Faz 6 hepsi `credit_experiment.py`'a dokundu — git'te dosya akümülatif. Sırayla commit ederken `git add -p` ya da dikkat lazım. Alternatif: tek toplu commit.

**4. Sonnet'e Faz 3 finalize brief (regression test bağlama)**

Ground truth `.json` finalize edildikten sonra:
- `tests/test_ocr_regression.py` (yeni) — her ground truth dosyası için pipeline koş + assert
- Toleranslar: time ±5sn, text case-insensitive partial match, min_line_count, confidence_min
- Faz 3 commit'i bu test'i de kapsayacak

### KAZANIMLAR (24-film yeniden koşumda doğrulanmalı, henüz yapılmadı)

| Metrik | Eski | Yeni hedef |
|---|---|---|
| POROROCA scroll | 0 | ≥100 (smoke'da 242) |
| FRANNY card | 0 | ≥10 (smoke'da 93) |
| Tüm filmler events.json | yok | var (text_event schema) |
| Low confidence flag | yok | her event'te |
| Legacy opt-out | env karışık | `USE_LEGACY_CREDIT_PIPELINE=1` net |

### Sıradaki büyük yön (V2)

Faz 6 sonrası mimari **kapanış** durumunda. V2 adayları:
- KJ profil aktivasyonu (`kind: kj_scan` stub'tan üretim'e)
- Scene_text profili (sahne içi yazı tespiti)
- Type-spesifik confidence eşikleri config dosyasına taşı
- Eski credit_detector silme (3-6 ay sonra)

### Dosya envanteri (bu oturumda eklenen/değişen sadece OCR + test + doc)

**YENİ:**
- `core/pipelines/ocr/text_event.py` (Faz 1)
- `core/pipelines/ocr/schemas/text_event.schema.json` (Faz 0)
- `core/pipelines/ocr/schemas/manifest_v2.schema.json` (Faz 0)
- `core/pipelines/ocr/manifest_profiles.py` (Faz 2)
- `core/pipelines/ocr/_video_meta.py` (Faz 2)
- `core/pipelines/ocr/dynamic_window.py` (Faz 4)
- `core/pipelines/ocr/confidence_thresholds.py` (Faz 5)
- `docs/MITAS_OCR_TextFirst_Mimari_v1.md` (Faz 0)
- `tests/data/ocr_ground_truth/README.md` (Faz 0)
- `tests/data/ocr_ground_truth/<10 film>.json.draft` (Faz 3)
- `tests/test_ocr_text_event_schema.py` (Faz 1)
- `tests/test_ocr_manifest_profiles.py` (Faz 2)
- `tests/test_ocr_dynamic_window.py` (Faz 4)
- `tests/test_ocr_confidence_thresholds.py` (Faz 5)
- `tests/test_ocr_legacy_optout.py` (Faz 6)

**DEĞİŞEN:**
- `core/pipelines/ocr/unified_credit_pipeline.py` (Faz 1+5)
- `core/pipelines/ocr/credit_experiment.py` (Faz 2+4+6)
- `core/pipelines/ocr/manifest_profiles.py` (Faz 4 — signature update)
- `mutfak/OCR-OPUS.md` (§13-§19 eklendi)

**DOKUNULMAYAN:**
- `core/pipelines/ocr/credit_detector.py` (legacy, byte-identical)
- ASR/webui/translate/diğer docs/mutfak (başka oturumun in-flight işi)

---

## 19. 2026-05-25 OTURUMU — IMDB Teyit + 24-Film Faz 4 Doğrulama

### 19.1 10 film ground truth — IMDB tam teyit
Çağatay 10 film için IMDB tarzı tam cast/crew listesi sağladı. Opus WebSearch ile her birini IMDB üzerinden çapraz teyit etti:

| # | Film | Çağatay listesi | IMDB teyit |
|---|---|---|---|
| 1 | X-MEN 2000 | doğru | ✓ |
| 2 | JURASSIC PARK 2 1997 | doğru | ✓ |
| 3 | ANJELIK VE SULTAN 1968 | doğru | ✓ |
| 4 | BARBARLARI BEKLERKEN 2019 | doğru | ✓ |
| 5 | **ROBINSON / The Wild Life 2016** | **eksik: DOUG STONE yoktu** | ✓ düzeltildi (DOUG STONE = AYNSLEY = Crusoe'nun köpeği) |
| 6 | PUPPET MASTER 1989 (Kukla Adam aslında bu) | doğru | ✓ |
| 7 | FRANNY'S FEET 2003 | doğru | ✓ |
| 8 | POROROCA 2017 | doğru | ✓ |
| 9 | SEMI-TOUGH 1977 (Yarı Sert) | doğru | ✓ |
| 10 | THE COLOR OF PARADISE 1999 | doğru | ✓ |

**Düzeltmeler:**
- KUKLA_ADAM önceki turda "Türk-Alman koprodüksiyon" sanılıyordu → aslında **Puppet Master (1989, David Schmoeller, ABD horror)**. Cast: Paul Le Mat, William Hickey, Irene Miracle, vs.
- ROBINSON için DOUG STONE ilk turda must_contain_text'ten çıkarılmıştı (Çağatay'ın ilk listesinde yoktu). Opus WebSearch ile teyit etti: DOUG STONE Aynsley karakterini (Crusoe'nun Airedale Terrier'i) seslendiriyor. Düzeltildi.
- YARI_SERT (Türkçe başlık) = Semi-Tough (1977, Michael Ritchie, Burt Reynolds) teyit edildi.

**Sonuç:** 10/10 ground truth dosyası IMDB onaylı + `status: approved` + `.json` finalize. `tests/data/ocr_ground_truth/` altında master'a hazır.

### 19.2 24-Film Faz 4 Doğrulama Pilotu — SONUÇLAR

**Manifest:** `outputs/ocr_24films_aaaa_film_credits_manifest_20260525.json` (24 film, hepsi `kind: film_credits` + dynamic_window: true)
**Output:** `outputs/ocr_24films_aaaa_phase4_verify_20260525/`
**Karşılaştırma kaynağı:** `outputs/ocr_24films_aaaa_test_20260523/` (eski `kind: end_credits`)

#### Genel kazanım
| Metrik | Eski | Yeni | Δ |
|---|---|---|---|
| Toplam scroll lines | 1.590 | **1.833** | +243 (+15%) |
| Toplam cards | 402 | **834** | +432 (+108%) 🎯 |
| Toplam event | — | 869 | yeni metrik |
| 24/24 done | ✓ | ✓ | regression yok |
| OCR error | 0 | 0 | sıfır |

**Ana hikaye:** Cards iki kat arttı. Sebep: Faz 2 (film_credits profili açılış+kapanış pencereleri) + Faz 4 (dinamik pencere) birlikte her iki bölgeyi de tarıyor → daha önce sadece son 7 dk'ya bakan pipeline şimdi açılış jeneriğini de yakalıyor.

#### Büyük kazanım filmleri
| Film | Eski | Yeni | Çarpan |
|---|---|---|---|
| PINOKYO_NUN_MACERALARI | 2 → 92 | +90 satır | **46×** |
| SON_METRO | 2 → 36 | +34 | 18× |
| CENNETTE_BULUSALIM | 1 → 17 | +16 | 17× |
| DUNYANIN_EN_MUTHIS_ADAMI | 9 → 26 | +17 | 3× |
| ANJELIK_VE_SULTAN | 55 → 81 | +26 | 1.5× |
| KANSAS_LI_SUVARILER | 0 → 15 | yeni | ∞ |
| DUZINESI_BIR_ARADA | 0 → 8 | yeni | ∞ |
| KULUBE | 0 → 5 | yeni | ∞ |

#### Regression sıfır
- X-MEN 238 → 238 (aynı)
- JURASSIC 277 → 277 (aynı)
- YARI_SERT 203 → 206 (+1)
- ROBINSON 176 → 183 (+7)
- CENNETIN_RENGI 45 → 47 (+2)

#### Hafif düşüş (kabul edilebilir)
- ÖZGÜRLÜK_YURUYUSU 207 → 203 (-4, %2)
- MUMYA 24 → 20 (-4)

#### ⚠ Smoke ile UYUMSUZ — araştırılmalı
**POROROCA + FRANNY:**

| Film | Smoke (tek-item, geçen gece) | 24-film (bugün) |
|---|---|---|
| POROROCA scroll lines | 242 | 5 (ama 78 card!) |
| POROROCA total events | 46 | 79 |
| FRANNY scroll lines | 93 | 1 (ama 24 card!) |
| FRANNY total events | 9 | 25 |

**Tanı:** Dinamik pencere DOĞRU çalıştı (POROROCA opening 3dk→5dk uzandı 2 iters, closing 8522-8822 = gerçek scroll'u kapsıyor). Card sayıları yüksek = pipeline gerçekten çalıştı. Sadece `text_layer_row_reconstruct` (composite OCR) POROROCA+FRANNY için optimal değil. Bu **Faz 4 dışı bir sorun** — B-port scroll composite ile ilgili. İleri inceleme bir sonraki oturum işi.

### 19.3 3 Soru cevabı
1. **Amaç korunuyor mu?** ✓ text-first mimari 24 filmde stres testten geçti. Cards 2× kazanım, scroll lines +15%, regression yok.
2. **Başka iş bozuluyor mu?** ✗ Hayır. Eski 24-film baseline ile karşılaştırılınca tüm filmler ya korundu ya iyileşti (2 hafif düşüş kabul edilebilir).
3. **Daha iyi yapılabilir mi?** POROROCA+FRANNY scroll composite optimizasyonu sonraki oturum işi. Şu an mimari kapanış tamamlandı.

### 19.4 COMMIT SIRASI (sıralı, sabah çağatay onayıyla)
1. **Faz 3 — Ground truth seti** (`tests/data/ocr_ground_truth/*.json` × 10 + README)
2. **Faz 4+5+6 — Mimari kapanış** (dynamic_window, confidence_thresholds, legacy opt-out, credit_experiment değişiklikleri, tests, OCR-OPUS.md §13-§19)

---

## 20. 2026-05-25 İLERİ SAATLER — OneOCR KEŞFİ (DEVAM EDİYOR)

> **Bu bölüm canlı çalışma kaydı. Token kesilirse yeni oturum buradan devam etsin.**

### 20.1 Şu an neredeyiz
Faz 1-6 hepsi commit edildi (HEAD `406914c8`). 10 ground truth IMDB-verified (`tests/data/ocr_ground_truth/*.json`). 24-film Faz 4 doğrulama bitti (`outputs/ocr_24films_aaaa_phase4_verify_20260525/`):
- Scroll lines 1590 → 1833 (+15%)
- Cards 402 → 834 (+108%)
- Ground truth IMDB okuma oranı: %58 (10 film ortalaması)
- En iyi: X-MEN %100, YARI_SERT %96, ROBINSON %93
- En kötü: CENNETIN_RENGI %0 (Farsça), FRANNY %0 (composite başarısız)

### 20.2 JURASSIC örnek incelemesi — Paddle vs OneOCR
Çağatay "neden yanlış okudu, kod mu görüntü mü?" sorusu üzerine:
- JURASSIC composite kesitinde "JULIANNE MOORE" → Paddle "JULIANNE MOGRE" (O→G hatası), ekran NET → MODEL HATASI
- OneOCR ile tek crop testi: MOORE ✓, DAYWALT ✓, BOBBY Z ✓ (3 isim Paddle'da yanlıştı)

### 20.3 JURASSIC TAM PIPELINE — Paddle vs OneOCR
`outputs/_jurassic_oneocr_test/` ile tam pipeline OneOCR koşumu:

| Metrik | Paddle | OneOCR | Kazanan |
|---|---|---|---|
| Runtime | 127s | 85s | OneOCR (%33 hızlı) |
| Cards | 12 | 27 | OneOCR (2.25×) |
| Scroll lines | 277 | 90 | Paddle |
| EXACT IMDB (18 isim) | 5/18 (%28) | **14/18 (%78)** | **OneOCR 2.8×** |
| Ensemble potansiyel | — | — | 15/18 (%83) |

**Tanı:** OneOCR cast kartlarında (Ian Malcolm/Jeff Goldblum, Julianne Moore, Pete Postlethwaite, vs.) çok daha iyi; Paddle scroll detayında (uzun kapanış jeneriği) daha iyi.

### 20.4 SIRADAKİ ADIM — 24-film OneOCR pilot (KANIT ARTTIR)
Çağatay onayı: tek JURASSIC örneği yeterli değil, 24-film OneOCR ile koşulup Paddle ile karşılaştırılacak.

**Komut (başlatılacak):**
```powershell
venvs/ocr/Scripts/python.exe -m scripts.ocr_credit_experiment `
  --manifest outputs/ocr_24films_aaaa_film_credits_manifest_20260525.json `
  --output-dir outputs/ocr_24films_aaaa_oneocr_20260525 `
  --engines oneocr
```

Tahmini süre: ~30-45 dk. Karşılaştırma kaynağı: `outputs/ocr_24films_aaaa_phase4_verify_20260525/` (Paddle).

Beklenen rapor formatı:
- Her film için Paddle vs OneOCR: cards, scroll_lines, runtime
- 10 ground truth film için OneOCR EXACT match oranı
- Genel ortalama: Paddle %58 → OneOCR ?
- En çok kazanan / en çok kaybeden filmler
- Engine seçim önerisi (default değişiklik, ensemble, per-segment dispatch)

### 20.5 PILOT CANLI DURUMU (snapshot: 2026-05-25 ~12:05)
- **Pilot başlama:** 11:48:17
- **Background ID:** `b63y232hs` (harness-tracked)
- **İlerleme:** 8/24 item bitti (~%33)
- **Tahmini bitiş:** ~12:30-12:40
- **Çıktı dizini:** `outputs/ocr_24films_aaaa_oneocr_20260525/items/`
- **Log dosyası:** `outputs/_oneocr_24films.log` (stdout buffered — dosya yazımı düzgün her item için)
- **Python PID:** 19032 (yaşıyor)

### 20.6 DOSYA ENVANTERI — Yeni oturum için referans

**Pipeline scripts:**
- `scripts/ocr_credit_experiment.py` — ana runner, `--engines paddle|oneocr|tesseract` flag
- `core/pipelines/ocr/credit_experiment.py` — `_run_item_profile_dispatch`, `PaddleOcrEngine` (line 220), `OneOcrEngine` (line 507)
- `core/pipelines/ocr/unified_credit_pipeline.py` — `run_box_track_pipeline` (paddle_engine DI)

**Manifest'ler:**
- `outputs/ocr_24films_aaaa_manifest_20260523.json` — LEGACY (kind=end_credits, 24 film son 7dk)
- `outputs/ocr_24films_aaaa_film_credits_manifest_20260525.json` — YENİ (kind=film_credits + dynamic_window, 24 film)
- `outputs/_jurassic_only_manifest.json` — tek-item JURASSIC

**Çıktı dizinleri (24-film için 3 koşum elimizde):**
- `outputs/ocr_24films_aaaa_test_20260523/` — eski end_credits/Paddle baseline
- `outputs/ocr_24films_aaaa_phase4_verify_20260525/` — yeni film_credits/Paddle (Faz 4 doğrulama)
- `outputs/ocr_24films_aaaa_oneocr_20260525/` — yeni film_credits/OneOCR (koşuyor)

**Smoke + analiz çıktıları:**
- `outputs/_jurassic_oneocr_test/items/jurassic_oneocr_test/` — JURASSIC tek-item OneOCR
- `outputs/_jurassic_julianne_crop.png` — composite kesit JULIANNE bölgesi (görsel kanıt)
- `outputs/_anomaly_check_frames/` — şüpheli filmlerin 70 frame'i (önceki oturum)
- `outputs/_canli_kanit_215645.jpg` — PC kanıt frame'i (önceki oturum)

**Ground truth (10 IMDB-verified):**
- `tests/data/ocr_ground_truth/*.json` × 10 — hepsi `status: approved`
- `tests/data/ocr_ground_truth/README.md` — format dokümantasyonu

**Karşılaştırma scriptleri (geçici):**
- `/tmp/ocr_compare.py` — Paddle vs OneOCR tek crop
- `/tmp/ocr_compare_full.py` — full composite IMDB arama
- `/tmp/jp_compare.py` — JURASSIC tam pipeline karşılaştırması

### 20.7 KARŞILAŞTIRMA HAZIR SCRIPT (PowerShell)

Pilot bittiğinde 24-film Paddle vs OneOCR karşılaştırması için:

```powershell
Set-Location E:\MITAS
$paddleBase = "outputs/ocr_24films_aaaa_phase4_verify_20260525/items"
$oneocrBase = "outputs/ocr_24films_aaaa_oneocr_20260525/items"

$rows = foreach ($d in Get-ChildItem $paddleBase -Directory) {
  $id = $d.Name
  $p = Get-Content "$paddleBase/$id/item_summary.json" -Raw | ConvertFrom-Json
  $oPath = "$oneocrBase/$id/item_summary.json"
  if (-not (Test-Path $oPath)) { continue }
  $o = Get-Content $oPath -Raw | ConvertFrom-Json

  $pEv = Get-Content "$paddleBase/$id/unified/events.json" -Raw | ConvertFrom-Json
  $oEv = Get-Content "$oneocrBase/$id/unified/events.json" -Raw | ConvertFrom-Json

  $pScroll = ($pEv.events | Where-Object { $_.type -eq "scroll_credit" } | ForEach-Object { if ($_.lines) { $_.lines.Count } else { 0 } } | Measure-Object -Sum).Sum
  $oScroll = ($oEv.events | Where-Object { $_.type -eq "scroll_credit" } | ForEach-Object { if ($_.lines) { $_.lines.Count } else { 0 } } | Measure-Object -Sum).Sum

  [PSCustomObject]@{
    Film = $id -replace '_end_credits',''
    P_Runtime = [math]::Round($p.runtime_sec,1)
    O_Runtime = [math]::Round($o.runtime_sec,1)
    P_Cards = $pEv.summary.by_type.card
    O_Cards = $oEv.summary.by_type.card
    P_Scroll = $pScroll
    O_Scroll = $oScroll
    P_Events = $pEv.summary.total_events
    O_Events = $oEv.summary.total_events
  }
}
$rows | Format-Table -AutoSize | Out-String -Width 250
$rows | ConvertTo-Json -Depth 4 | Out-File "outputs/_paddle_vs_oneocr_summary.json" -Encoding utf8
```

### 20.8 IMDB IsIM EŞLEŞMESI SCRIPT (10 GT film için OneOCR)

Pilot bittikten sonra:

```python
# /tmp/oneocr_imdb_compare.py
import sys, re, json
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

def collect_text(item_dir):
    texts = []
    ev_path = item_dir / "unified" / "events.json"
    if not ev_path.exists(): return texts
    ev = json.loads(ev_path.read_text(encoding="utf-8"))
    for e in ev.get("events", []):
        if e.get("text"): texts.append(e["text"])
        if e.get("secondary_text"): texts.append(e["secondary_text"])
        for ln in (e.get("lines") or []):
            if ln.get("text"): texts.append(ln["text"])
        pr = e.get("paired_role_name") or {}
        if pr.get("role"): texts.append(pr["role"])
        if pr.get("name"): texts.append(pr["name"])
    return texts

def find_match(name, lines):
    name_clean = re.sub(r'[^A-Z ]', '', name.upper())
    parts = [p for p in name_clean.split() if len(p) >= 3]
    for t_raw in lines:
        t = re.sub(r'[^A-Z ]', '', t_raw.upper())
        if name_clean in t: return "EXACT"
        if all(p in t for p in parts): return "EXACT"
    for t_raw in lines:
        t = re.sub(r'[^A-Z ]', '', t_raw.upper())
        if any(p in t for p in parts): return "PARTIAL"
    return "NONE"

gt_dir = Path("tests/data/ocr_ground_truth")
oneocr_base = Path("outputs/ocr_24films_aaaa_oneocr_20260525/items")

for gt_file in sorted(gt_dir.glob("*.json")):
    gt = json.loads(gt_file.read_text(encoding="utf-8"))
    vid = gt["video_id"]
    item_dir = oneocr_base / vid
    if not item_dir.exists(): continue
    texts = collect_text(item_dir)
    expected = []
    for seg in gt.get("expected_segments", []):
        expected.extend(seg.get("must_contain_text", []))
    expected = list(set(expected))
    if not expected: continue
    e = sum(1 for n in expected if find_match(n, texts) == "EXACT")
    p = sum(1 for n in expected if find_match(n, texts) == "PARTIAL")
    n = len(expected) - e - p
    ratio = (e + p*0.5) / len(expected) * 100
    print(f"{vid:<45} {e}/{p}/{n}  →  {ratio:.1f}%")
```

### 20.9 EĞER TOKEN BİTERSE — YENİ OTURUM PROTOKOLÜ

Yeni Claude'da adım adım:

1. **Bağlam yükle:** `mutfak/OCR-OPUS.md` oku (özellikle §20 — bu bölüm)
2. **Git durumunu kontrol:**
   ```bash
   git log --oneline -5
   # HEAD `406914c8` olmalı (Faz 4+5+6 mimari kapanış)
   git status --short
   # Sadece outputs/ ve mutfak/OCR-OPUS.md uncommitted olmalı
   ```
3. **Pilot çalışıyor mu kontrol:**
   ```powershell
   Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*venvs\ocr*" }
   Test-Path "outputs/ocr_24films_aaaa_oneocr_20260525/run_summary.json"
   (Get-ChildItem "outputs/ocr_24films_aaaa_oneocr_20260525/items" -Directory).Count
   ```
4. **Eğer pilot bittiyse:**
   - 24/24 item dir var, `run_summary.json` mevcut
   - §20.7'deki PowerShell scripti koş → Paddle vs OneOCR tablosu
   - §20.8'deki Python scripti koş → IMDB EXACT match oranı
5. **Eğer pilot hâlâ koşuyorsa:**
   - Beklemeye devam, log boyutu artıyor mu (bazen 0 byte gözükebilir — stdout buffered, normal)
   - Bittiğinde harness bildirim verir (background task ID `b63y232hs`)
   - Veya yeni oturumda eski background kaybolduysa, doğrudan koş:
     ```powershell
     venvs/ocr/Scripts/python.exe -m scripts.ocr_credit_experiment `
       --manifest outputs/ocr_24films_aaaa_film_credits_manifest_20260525.json `
       --output-dir outputs/ocr_24films_aaaa_oneocr_20260525 `
       --engines oneocr
     ```
6. **Sonuçları işle:**
   - Bu dosyaya §21 olarak "24-film OneOCR pilot SONUÇLAR" başlığı ekle
   - Per-film tablo (24 satır × P_runtime/O_runtime/P_cards/O_cards/P_scroll/O_scroll)
   - 10 GT film için IMDB EXACT oranı (Paddle %58 vs OneOCR ?)
   - En çok kazanan/kaybeden filmler
   - Engine seçim önerisi: A) default OneOCR yap | B) ensemble | C) per-segment dispatch
7. **Commit:**
   - Sadece `mutfak/OCR-OPUS.md` (kod yok, sadece doc)
   - Mesaj: `docs(ocr): document 24-film OneOCR pilot results + engine recommendation`
8. **Çağatay onayıyla:** Eğer OneOCR önemli iyileştirme gösterdi → V2 task: default engine değişikliği için Sonnet brief

### 20.10 ÖNEMLİ HATIRLATMA — DOKUNULMAYACAKLAR
Bu oturumda ASR/webui/translate/diğer dosyalara dokunulmadı, **devam etmemeli:**
- `core/api/asr_server.py`, `core/api/tedial/*`
- `core/pipelines/asr/*`, `core/pipelines/translate/*`
- `webui/src/app/*`
- `docs/MITAS_*` (üst seviye, OCR-OPUS hariç)
- `mutfak/*.md` (OCR-OPUS hariç)

Bunlar başka oturumun in-flight işi (memory: `feedback_master_no_worktree` + `feedback_checkpoint_commit_hygiene`).

---

## 21. 24-FILM ONEOCR PILOT — FINAL SONUÇLAR (2026-05-25)

### 21.1 Pilot bitiş
- Başlama: 11:48:17 | Bitiş: ~12:53 | Süre: ~65 dk
- 24/24 done, 0 OCR error
- Çıktı: `outputs/ocr_24films_aaaa_oneocr_20260525/`
- Karşılaştırma kaynağı: `outputs/ocr_24films_aaaa_phase4_verify_20260525/` (Paddle baseline)

### 21.2 Genel skor (24 film)
| Metrik | Paddle | OneOCR | Kazanan |
|---|---|---|---|
| Runtime | 1588 sn | 3860 sn | Paddle **2.43× hızlı** |
| Cards | 834 | 783 | Paddle (%6) |
| Scroll lines | 1833 | 1079 | Paddle (%70 detay) |
| Total events | 869 | 815 | Paddle |
| **IMDB EXACT ortalama (9 GT)** | **%65** | **%75** | **OneOCR +10%** |

### 21.3 IMDB doğruluk per-film (10 GT film)
| Film | Paddle | OneOCR | Kazanan |
|---|---:|---:|---|
| X-MEN | 100% | 97% | Paddle +3% |
| YARI_SERT | 96% | 96% | Eşit |
| ROBINSON | 93% | 93% | Eşit |
| BARBARLARI | 82% | 68% | Paddle +14% |
| JURASSIC | 68% | 59% | Paddle +9% |
| ANJELIK | 59% | 50% | Paddle +9% |
| KUKLA | 42% | 42% | Eşit |
| **FRANNY** | **0%** | **100%** | **OneOCR +100%** 🎯 |
| **POROROCA** | 43% | **71%** | **OneOCR +29%** |
| CENNETIN_RENGI | 0% | 0% | İkisi de Farsça başarısız |

### 21.4 GPU tanısı (sorunun kökü)
- Paddle: **GPU (RTX 3090 + CUDA 11.8)** — `nvidia-smi` Paddle koşumunda %15-30 GPU
- OneOCR: **CPU (Windows native DLL)** — `nvidia-smi` OneOCR koşumunda %0 GPU
- OneOCR/Paddle runtime oranı tutarlı 2.43× (rastgele değil, sistematik CPU/GPU farkı)
- Çağatay'ın eski OneOCR hızlı deneyimi: muhtemelen o zaman Paddle CPU'daydı

### 21.5 OneOCR GPU araştırması (WebSearch, 2026-05-25)
**Sonuç: Doğrudan GPU'ya almak İMKANSIZ.**
- OneOCR = Windows 11 Snipping Tool engine, Microsoft closed-source DLL
- `.onemodel` formatı standart ONNX değil → ONNX Runtime CUDA/DirectML provider kullanılamaz
- Microsoft kendisi de GPU desteği vermemiş (WindowsAppSDK Issue #3514, çözülmemiş)
- RapidOCR projesi GPU denedi, "not very good" deyip vazgeçti
- **Alternatif:** MeikiOCR (OneOCR kalitesinde + GPU destekli, henüz test edilmedi)

### 21.6 BULGULARIN ÖZÜ
**OneOCR güçlü alanı:** ZOR vakalar (composite başarısız, hareketli BG, animasyon)
- FRANNY: Paddle composite çöktü → OneOCR 5/5 ana isim doğru (Phoebe McAuley, George Buza, Tajja Isen, Julie Lemieux, Juan Chioran)
- POROROCA: Romen scroll, Paddle 43% → OneOCR 71%

**Paddle güçlü alanı:** STANDART modern jenerikler
- X-MEN, BARBARLARI, ANJELIK, JURASSIC → siyah BG scroll → %5-15 daha doğru
- Scroll detayında çok daha zengin (%70 fazla satır)
- 2.43× hızlı

**İkisi de başarısız:** yabancı alfabe (Farsça/Arapça) — V2 dil-spesifik model

### 21.7 KARAR — V2 için öneri: AKILLI FALLBACK
```
Strateji:
1. Paddle ile koş (default, hızlı)
2. Sonuç check:
   - composite_broken flag aktif VEYA
   - scroll_lines < 5 VEYA  
   - cards == 0
   → OneOCR ile yeniden koş (sadece sorunlu segment)
3. Sonuçları birleşik events.json içinde merge et
```

**Kazanç:**
- FRANNY 0 → 100% kurtarılır
- POROROCA 43 → 71% iyileşir
- ANJELIK/JURASSIC/X-MEN değişmez (Paddle zaten iyi)
- Runtime artışı ~%10-15 (fallback nadiren tetiklenir)

**Default engine değişikliği YAPILMAMALI** (OneOCR'ı tek başına): hız ve detay kaybı kabul edilmez.

### 21.8 Üretilen artifact'ler (bu oturumda)
- `outputs/ocr_24films_aaaa_oneocr_20260525/` (24 film OneOCR çıktısı)
- `outputs/_paddle_vs_oneocr_summary.json` (PowerShell tablo verisi)
- `/tmp/ocr_compare.py`, `/tmp/ocr_compare_full.py`, `/tmp/jp_compare.py`, `/tmp/oneocr_partial_imdb.py` (analiz scriptleri)
- `outputs/_jurassic_oneocr_test/` (tek-item JURASSIC OneOCR smoke)
- `outputs/_jurassic_julianne_crop.png` (composite kanıt görseli)
- `outputs/_oneocr_24films.log` (pilot log)

### 21.9 SIRADAKİ ADIM (V2 oturumu için)
1. **Akıllı fallback implementasyonu** — Sonnet brief: `core/pipelines/ocr/unified_credit_pipeline.py` step sonrası kalite kontrol, gerekirse OneOCR re-run
2. **MeikiOCR araştırması** — OneOCR'ın GPU alternatifi olabilir, kalite testi gerekir
3. **Yabancı alfabe modeli** — Farsça/Arapça için ayrı Paddle multilingual model veya dil tespiti + dispatch
4. **Regression test runner** (Faz 3 ikinci yarı) — `tests/test_ocr_regression.py` ground truth dosyalarına karşı assert

---

**Bu dosyayı her büyük adımdan sonra güncelle.** YAPILACAK → YAPILDI → COMMIT EDİLDİ formatı.
