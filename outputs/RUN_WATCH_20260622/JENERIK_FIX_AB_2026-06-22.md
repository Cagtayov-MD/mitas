# JENERİK TESPİT FIX — UYGULAMA + A/B RAPORU
**Tarih:** 2026-06-22 · **Branch:** `fix/jenerik-tespit-cikis-bloat-ocr-gate` · **Yöntem:** kök-neden bağımsız teyit → kod fix → birim test → KN-1 deterministik → OCR-kalkan A/B (pre-registered, env-toggle)

---

## 1) KÖK-NEDEN BAĞIMSIZ TEYİDİ (kendi gözümle, kayan satırlar dahil)

### KN-1 — ÇIKIŞ footage-bloat (TEYİT EDİLDİ)
- `scripts/mitas_pipeline.py:1298` → `_cik_start = max(0.0, dur_sec - args.ocr_tail)` (ocr_tail default **240**) = sabit-kuyruk tabanı.
- `:1376-1377` (orijinal) → `_ds = max(0.0, closing.start_sec - 5.0)` ; `_cik_start = min(_ds, _cik_start)`.
- **Mekanizma DOĞRU:** kapanış jeneriği `dur−240`'tan GEÇ başlayınca (en yaygın durum) `_ds > _cik_start` → `min()` daha-erken sabit-kuyruğu seçer, dedektörün hassas başlangıcını atar → medyan ~157s footage pencere başına girer.
- Pencere SONU (`:1378-1379`) doğruydu; yalnız BAŞ bozuktu. (Rapordaki satır no'ları ±1 kaymıştı, mantık birebir doğrulandı.)

### `_detect_changed` güvenlik-ağı (TEYİT EDİLDİ — DEĞİŞTİRİLMEDİ)
- `:1410-1413`: `_detect_changed = (... or abs(_cik_start - max(0, dur_sec - ocr_tail)) > 0.5 or ...)`.
- `_cik_start = _ds` (sabit-kuyruktan ERKEN) yapınca bu **TRUE** olur → `:1524-1533` sonuç-temelli yedek ARMS olur: daraltılmış pencere `< MITAS_OCR_MIN_LINES` (default 30) OCR satırı verirse sabit `[dur−240, dur]` kuyruğu re-OCR'lanır, çok-satırlı sonuç tutulur. Güvenlik-ağı mantığı bozulmadı.

### KN-2/3/4 — GİRİŞ/ÇIKIŞ footage-FP (KISMEN TEYİT, KISMEN ÇÜRÜK — aşağıda)
- `core/pipelines/ocr/jenerik_detector.py`: heuristik `_build_tophat_mask` + `_row_structure_score`, CLIP yumuşak-kapı (`:276-277`), SHIELD'ler (`:427-435`). OCR-doğrulaması ZATEN vardı ama yalnız `refine_start_ocr`/`refine_end_ocr`'da (sınır-inceltme), kalkan-kapısı olarak DEĞİL. Bu teyit edildi.
- `jenerik_detector.py` modülünde `import os` YOKtu (FIX 2 için eklendi).

---

## 2) YAPILAN DEĞİŞİKLİKLER (diff özeti)

### FIX 1 — `scripts/mitas_pipeline.py` (KN-1, default-ON kill-flag)
- **+`_TIGHT_CLOSE`** flag okuma (`MITAS_CREDIT_DETECT_*` bloğunda, ≈1313): default **ON** (`not in ("0","false","off","no")`).
- Kabul bloğu (`if _cl_has and _cl_ok:`): `_TIGHT_CLOSE` iken `_cik_start = _ds` (min() YOK → hassas tespite güven); değilse eski `min(_ds, _cik_start)`.
- Min-pencere tabanı `_cik_start + 30.0` → **`_cik_start + 60.0`**.
- Güvenlik-ağı (`_detect_changed`, sonuç-temelli yedek) DOKUNULMADI.

### FIX 2 — `core/pipelines/ocr/jenerik_detector.py` (KN-2/3/4 OCR-kalkanı, A/B-kapılı)
- **+`import os`**.
- **+`_ocr_gate_has_credit_text(region, frames_bgr, lines_at)`**: bölgenin `start_frame..end_frame` çekirdeğinden eşit-aralık ≤15 kare örnekle, `lines_at` cache'iyle OCR oku; herhangi bir karede `is_credit_text_line==True` → True. Sınır/boş frame → güvenli taraf True.
- **+`_ocr_gate_enabled()`**: `MITAS_JENERIK_OCR_GATE` (default **OFF**, `in ("1","true","on","yes")`).
- `_apply_ocr_refine`: cache tanımından sonra, refine'den ÖNCE — flag ON + çekirdekte SIFIR kredi-satırı → `region["found"]=False`, `invalid_reason="no_credit_text_in_core"`, dön. Cache refine ile paylaşılır.
- `_apply_ocr_refine_end` (GİRİŞ): `not region.get("found")` ile zaten erken döner → kalkan tek noktadan GİRİŞ+ÇIKIŞ'ı kapsar (TEYİT EDİLDİ). Video yolu (`_opening`/`_closing`) de aynı fonksiyonları çağırır → otomatik kapsanır (TEYİT EDİLDİ).
- Flag OFF iken kod tamamen **inert** (davranış değişmez).

---

## 3) BİRİM TEST (commit ön-koşulu)
| Süit | Baseline | Fix sonrası | Sonuç |
|---|---|---|---|
| `-k credit` | 69 passed, 1 skipped | **69 passed, 1 skipped** | ✅ regresyon yok |
| `-k ocr` | 177 passed, 2 skipped | **177 passed, 2 skipped** | ✅ regresyon yok |

> NOT: Ortamda `fastapi` yok → 7 tedial/asr test dosyası collection-time çöküyor (fix'lerimle ilgisiz). Bunlar `--ignore` edilerek koşuldu. Plandaki "55/139" sayıları eski sayım; bu ortamda credit/ocr -k filtreleriyle eşleşen TÜM testler (69/177) yeşil.

---

## 4) KN-1 DETERMİNİSTİK DOĞRULAMA (PASS)
Senaryo: film 5000s, ocr_tail=240 (sabit-kuyruk tabanı = 4760), kapanış tespiti `det_start=4950` (dur−240'tan GEÇ).

| | `_cik_start` | `_cik_end` | len | `_detect_changed` |
|---|---|---|---|---|
| **Flag ON** (TIGHT) | **4945.0** = det−5 | 5000.0 | 55s | **True** (yedek ARMS) |
| Flag OFF (eski) | 4760.0 (sabit kuyruk) | 5000.0 | 240s | False |

→ Flag ON: hassas tespit seçildi (sabit-kuyruk DEĞİL), **185s footage-bloat çıkış penceresi başından kaldırıldı**, `_detect_changed=True` (güvenlik-ağı silahlandı).
→ Erken-tespit kontrolü (det_start=4600 < 4760): ON ve OFF aynı `_cik_start=4595` → regresyon yok.

---

## 5) OCR-KALKAN A/B (pre-registered, env-toggle `MITAS_JENERIK_OCR_GATE=0` vs `=1`)
Runner: `venvs/ocr/Scripts/python.exe scripts/_jenerik_detect.py --film <dir> --prefer first` (CLIP açık + OCR-refine açık = gerçek pipeline koşulu). İki bağımsız koşu (subprocess + in-process) tutarlı.

### (a) FP-küme — kalkan `opening.found` True→False yapMALI
| Film | before | after | kalkan | not |
|---|---|---|---|---|
| ALTINCI ADAM | — | — | — | Database'de YOK (frames silinmiş) |
| CENGİZ HANIN İKİ ATI | — | — | — | Database'de YOK |
| DOGMATİK | — | — | — | Database'de YOK |
| FIRINCININ KARISI | True | **True** | ✗ tutuldu | OCR çekirdekte GERÇEK oyuncu okuyor (BÜŞRA PEKİN/ALPER KUL/KORHAN HERDURAN/BEYTİ ENGİN/KUBAT) → **aslında gerçek kredi, FP değil** |
| HANNAH'NIN KANUNU | True | **True** | ✗ tutuldu | CLIP-açıkta footage-region (f40-62) seçiliyor; o çekirdekte OneOCR gürültü-metni "kredi" sanıyor (CLIP-kapalıyken f21-30 → kalkan temizliyordu) |
| INNISFREE | True | **False** | ✓ temizlendi | `no_credit_text_in_core` |
| WANDA | True | **True** | ✗ tutuldu | Çekirdekte "Metro Goldwyn Mayer / TRADE MARK" stüdyo-logosu okunuyor (kredi-benzeri) |

**FP temizleme: 1/4 mevcut film** (PASS eşiği ≥5/7 veya ≥3/4 → **FAIL**).

### (b) Temiz-küme (CSV `giris_verdict==CORRECT`, ≥15 film) — kalkan regresyon yapMAMALI
**28 film test edildi** (CSV `giris_verdict==CORRECT` örneklemi, G→Z + İ).
**Sonuç: 27/28 `before=True → after=True`; 1 REGRESYON.**

| Regresyon | before | after | not |
|---|---|---|---|
| ZAMAN MAKİNASI 1985-0235-1-0000-00-1 | True | **False** (`no_credit_text_in_core`) | gerçek/temiz açılış kredisi, kalkan çekirdekte okunabilir kredi-satırı bulamayıp ATTI → **gerçek-kredi kaybı** |

Yani kalkan ON iken temiz-kümede de **gerçek krediyi atabiliyor** (1/28 ≈ %3,6 clean-regresyon). Bu, FP-fail'le birlikte gate'i default **OFF** tutma kararını PEKİŞTİRİR: kalkan hem footage'ı tutarlı elemiyor (FP 1/4) hem de soluk/okunması-zor gerçek krediyi (ZAMAN MAKİNASI) yanlışlıkla atıyor. Sebep: `is_credit_text_line` gevşek olduğundan footage-OCR-gürültüsünü "kredi" sanırken, soluk gerçek krediyi OneOCR çekirdekte okuyamayınca "footage" sanıyor — iki yönlü hata. İleride değer kazanması için `is_credit_text_line` sıkılaştırma + CLIP-rescue koşullama + OCR-okunabilirlik toleransı gerekir (ayrı iş).

### Çıkış spot-kontrol (`--prefer last`, gözlem, bloklamaz)
| Film | before | after | not |
|---|---|---|---|
| INNISFREE | found=True (259.5–305s) | found=True (aynı) | gerçek çıkış kredisi, kalkan etkisiz (doğru) |
| SHALAKO | found=True (207–240s) | **found=False** (`no_credit_text_in_core`) | rapordaki çıkış-FP, kalkan temizledi (olumlu gözlem) |
| ZORUNLU EVLİLİK | — | — | Database'de YOK |

---

## 6) KARAR + GEREKÇE
- **(a) FP kriteri FAIL** (1/4 < 3/4). Sebep iki katmanlı:
  1. **FP-küme kirli:** En az FIRINCININ KARISI'nde OneOCR çekirdekte gerçek oyuncu isimleri okuyor → film gerçekte kredi içeriyor, "FP" etiketi yanlış (QC görsel-ajan OCR yapmadan footage sanmış). Kalkanın bunu tutması DOĞRU (gerçek krediyi atmadı — planın "katı eşik başrol düşürür" uyarısının tam kanıtı).
  2. **CLIP-rescue gediği (KN-3) gerçek footage'ı kurtarıyor:** HANNAH/WANDA'da CLIP-floor footage'ı present yapıp region'ı footage karelerine kaydırıyor; o karelerde OneOCR gürültü/logo metni üretiyor → `is_credit_text_line` (≤5 kelime + ≥%50 harf, çok gevşek) bunu "kredi" sanıyor → kalkan delinir.
- **(b) Temiz-küme regresyon VAR** (1/28 ≈ %3,6): ZAMAN MAKİNASI'nın gerçek açılış kredisi atıldı (`no_credit_text_in_core`). Kalkan iki yönlü hata yapıyor: footage-gürültüsünü kredi sanırken, soluk gerçek krediyi footage sanıyor.
- **→ `MITAS_JENERIK_OCR_GATE` kod-default = OFF (inert).** Plan gereği: FP kriteri sağlanmadığında default OFF + sayılar dürüstçe raporlanır. Temiz-regresyon bu kararı PEKİŞTİRİR. KN-1 + inert-gate güvenli teslimdir.
- Kalkan ileride değer taşıyabilir (INNISFREE giriş + SHALAKO çıkış temizlendi) ama hem footage-OCR-gürültüsünü tutarlı elemiyor (FP 1/4) hem de soluk gerçek krediyi atıyor (temiz 1/28). Gerçek çözüm `is_credit_text_line`'ı sıkılaştırmak (ardışık-kare-tutarlılığı / stüdyo-logo sözlüğü) + CLIP-rescue'yu OCR'la koşullamak + OCR-okunabilirlik toleransı — ayrı iş.

---

## 7) AÇIK RİSKLER / KULLANICININ BİLMESİ GEREKENLER
- **FIX 1 (KN-1) CANLI default-ON:** Her filmde çıkış penceresi artık tespit-başına çekiliyor. Güvenlik-ağı (sonuç-temelli yedek, `_detect_changed`) yanlış-daraltmayı OCR-satır-sayısıyla yakalar; yine de ilk 100-film koşusunda `credit_detect_closing` log'larında pencere-başı ≈ tespit-başı beklenir, izlenmeli. Kill-flag: `MITAS_CREDIT_DETECT_TIGHT_CLOSE=0`.
- **FP-küme kirliliği:** Raporun "7/60 giriş FP" listesi en az bir gerçek-kredi içeriyor (FIRINCININ). Gelecek FP-analizleri görsel-QC + OCR birlikte yapılmalı.
- **OCR-kalkan inert:** Kodda var, default kapalı. `MITAS_JENERIK_OCR_GATE=1` ile denenebilir ama mevcut haliyle FP'leri tutarlı elemiyor (CLIP-region + gevşek `is_credit_text_line`).
- Çalışma-artefaktları (`_ab_*.py`, `_ab_*.log`, `_ab_gate_results.json`) commit'e DAHİL DEĞİL; yalnız kaynak + bu rapor commit'lenir.
