# JENERİK TESPİT SİSTEMİ — "NEREDE SORUN VAR" KÖK-NEDEN RAPORU
**Tarih:** 2026-06-22 · **Yöntem:** 35-ajan workflow (5 boyut × adversarial doğrulama) · **SALT-OKUNUR, commit YOK**
Artefakt: `outputs/RUN_WATCH_20260622/wmdh3w0fl` workflow çıktısı · 25 doğrulanmış bulgu

> **ÖNEMLİ DÜZELTME:** İlk ön-teşhiste GİRİŞ false-pozitiflerini "CLIP sorunu" sandım. Adversarial doğrulama bunu **çürüttü**: CLIP KAPALIYKEN bile aynı footage FALSE_POSITIVE çıkıyor. Asıl kök sezgisel primitif (`_build_tophat_mask`); CLIP yalnız ikincil amplifikatör.

---

## 1) TEK-PARAGRAF TEŞHİS

Jenerik tespiti "bulamıyor" değil — neredeyse **her filmde yüksek güvenle bir şey buluyor** (giriş kabul 51/53, çıkış 49/53, conf medyanı giriş 0.873 / çıkış 0.956, skip≈0). "İyi çalışmıyor" hissinin gerçek kaynağı iki ayrı kök ve onları gizleyen üçüncü bir mimari kusur:

- **(A) ÇIKIŞ footage-bloat (dominant, mekanik):** `mitas_pipeline.py:1377` `_cik_start=min(tespit−5, dur−240)` "geri-gitme" kuralı, gerçek kapanış jeneriği `dur−240`'tan sonra başladığında (en yaygın durum) sabit-240-kuyruğu seçip dedektörün doğru-okuduğu hassas başlangıcı **kasten çöpe atıyor** → medyan ~157s saf footage pencere başına enjekte ediliyor (45/49 pinned, 27/49 ≥150s).
- **(B) GİRİŞ footage-FP (dokusal):** Heuristik primitif footage dokusunu sahte "metin satırı" sanıyor; dört FP-kalkanı ya bypass ediliyor ya da aynı sahte sinyale bakıyor → 7/60 saf-footage giriş FALSE_POSITIVE.
- **(C) Gizleyici mimari:** `confidence=med_cs` CLIP-floor'la şişiyor → conf≥0.60 kapısını anlamsızlaştırıyor; güven correctness'i öngörmüyor.

**Tek gerçek savunma boşluğu:** OCR-tabanlı metin-doğrulaması (kodda mevcut) yalnız sınır-inceltmede kullanılıp **KALKAN olarak geçerlilik-kapısına bağlanmamış.**

---

## 2) KÖK-NEDENLER (öncelik sırasıyla)

### KN-1 — ÇIKIŞ footage-bloat: `min(tespit, dur−240)` hassas tespiti atıyor `[CRITICAL — dominant]`
- **NE:** Kabul edilen çıkış tespitlerinin ~%92'sinde hassas kredi-başı atılıyor; pencere `[dur−240, dur]`'a çöküyor, medyan ~157s footage pencere BAŞINA giriyor.
- **NEREDE:** `scripts/mitas_pipeline.py:1298` (`_cik_start=max(0, dur−ocr_tail)`, ocr_tail=240) + `:1376-1377` (`_ds=closing.start−5; _cik_start=min(_ds,_cik_start)`). Pencere SONU `:1378-1379` doğru — yalnız BAŞ bozuk.
- **MEKANİZMA:** Kapanış tipik son ~120s'de başlar → `_ds > dur−240` → `min()` daha-erken sabit-kuyruğu seçer, tespiti atar. fps=2 ile ~314 footage karesi OCR/stitch/master/credit_text'e besleniyor.
- **KANIT:** `system_events.jsonl` — 49 kabul-çıkıştan 45'i pinned; bloat medyan 157s / max 261s; 45/49 pencere TAM 240s. BEKARLIK win=4689 det=4950 (261s); BÜLBÜLÜ ÖLDÜRMEK win=7180 det=7417 (237s).
- **FIX-YÖNÜ:** No-regress'i yön-koşullu yap — `_cl_ok` (yüksek-güven) iken `min()` yerine doğrudan `_cik_start=_ds` + alt-sınır (~60-90s). Fail-safe ön-yükleme kalsın. **Risk düşük** (dokunulan yer kanıtlı-footage).

### KN-2 — GİRİŞ footage-FP: heuristik primitif footage dokusunu "metin satırı" sanıyor `[CRITICAL]`
- **NE:** 7/60 saf-footage giriş FALSE_POSITIVE: ALTINCI ADAM, CENGİZ HANIN İKİ ATI, DOĞMATİK, FIRINCININ KARISI, HANNAH'NIN KANUNU, INNISFREE, WANDA — hiçbirinde okunabilir yazı yok.
- **NEREDE:** `dynamic_credit_mosaic.py:219-272` (`_build_tophat_mask`, CC filtresi) → `jenerik_detector.py:247-260` (heur) ve `:427-435` (kalkanlar).
- **MEKANİZMA:** Top-hat + CC filtresi yatay-uzun doku-kenarlarını (wisteria sıraları, su dalgaları, hava-çekim bina kenarları) sahte-blob/satır sayıyor → `_row_structure_score` 0.55-0.83 verir → heur≥0.50 → present. SHIELD2 (`med_row<0.15`) ve SHIELD3 (`med_nblob<3`) footage'ta tutmaz; SHIELD1 (`no_text_structure`, ≥3 metin-karesi) footage yüzlerce sahte-kare ürettiği için delinir; SHIELD4 uzun-footage'a uygulanmaz. (`dense_count` denenip GERİ ALINMIŞ — `:116-119`.)
- **KANIT:** **CLIP KAPALI** ampirik koşu: FIRINCININ conf=0.7447, INNISFREE 0.8685, WANDA 0.7754 — TÜM kalkanlar fire=False. `jenerik_qc_FINAL.csv` bağımsız doğruluyor.
- **FIX-YÖNÜ:** Bir koşuyu "valid" saymadan çekirdek karelerinde **OCR ile ≥N okunabilir kredi-satırı (`is_credit_text_line`) ARANSIN**; yoksa footage. Altyapı (`refine_start_ocr`, motor `_jenerik_detect.py:31`) zaten kurulu ama KALKAN değil. Blob-eşiği yükseltmek başrol düşürür.

### KN-3 — CLIP iki bağımsız FP yolu: yumuşak-kapı (present) + CLIP-rescue (kalkan bypass) `[HIGH]`
- **NEREDE:** `jenerik_detector.py:276-277` (`cp≥0.65 → cs=max(cs,0.55)`) + `:430` ve `:433-434` (SHIELD2/3 `and not (med_clip≥0.50)` escape).
- **MEKANİZMA:** (1) `cp≥0.65` → cs≥0.55 floor → yazı-yapısı OLMAYAN footage present. (2) `med_clip≥0.50` → iki dokusal kalkan da bypass; geriye yalnız SHIELD1 backstop.
- **KANIT:** INNISFREE med_clip=0.718; run[339..350] med_row=0 & med_nblob=0 (her iki kalkan fire etmeli) ama clip_rescue devirdi.
- **FIX-YÖNÜ:** CLIP-rescue'yu OCR-teyidiyle koşulla (CLIP yüksek + OCR boş → footage).

### KN-4 — `confidence=med_cs` güvenilir değil; conf≥0.60 kapısı pratikte no-op `[HIGH]`
- **NEREDE:** `jenerik_detector.py:465` + `:276-277` (CLIP floor) + `mitas_pipeline.py:1310/1330`. `low_conf` bayrağı (LOW_CONF=0.55) **pipeline'da SIFIR tüketici** (grep-doğrulandı).
- **MEKANİZMA:** conf = CLIP-ağırlıklı yapısal sinyalin medyanı; OCR-anlamı yok. `valid` bayrağı med_cs'e bakmaz → footage kalkanlardan geçtiyse 0.60 onu durduran kapı değil.
- **KANIT:** çıkış conf medyan 0.956, 0 kabul conf<0.60; QC'de buna rağmen 7 giriş + 6 çıkış FP. Eşik yükseltmek FP'yi elemez (zaten 0.86+).

### KN-5 — quad "static" aileler tüm FP'lerin kaynağı; scroll SIFIR FP; çıkış-kenarı siyah/fade `[HIGH]`
- **NE:** `bg_static_text_static` %17 FP (8/46), `bg_moving_text_static` %13 FP (4/30); scroll 0/31 FP. Çıkış son-kenar uniform-siyah/fade kareler yüksek conf alıyor.
- **KANIT:** SHALAKO çıkış frame442-479 conf0.926; ZORUNLU EVLİLİK frame472-479 (son 8 siyah kare) conf0.942; montaj kareleri saf-siyah ama clip0.95-0.99.
- **ETKİ:** **`project_master_png_blackbg_cut` ile AYNI KÖK** — full-frame uniform-siyah analizi yanıltıyor.
- **FIX-YÖNÜ:** Statik çıkış için uniform/siyah-fade guard'ı + min_clip + gerçek-OCR-satırı zorunluluğu.

### KN-6 — Sonuç-temelli yedek (`_detect_changed`) bloat'ı yapısal yakalayamaz `[MEDIUM]`
- Bloat tam olarak `_cik_start` dur−240'a PINNED kalınca oluşur → kapanış-terimi FALSE → yedek hiç çalışmaz (koşuda 0 fallback). Tetiklese bile aynı kuyruğu üretir. **Çözüm KN-1'de.** (`:1411-1413`, `:1530-1540`)

### KN-7 — OCR-refine kenar riskleri ve sessiz fail-safe `[MEDIUM/LOW — ikincil]`
- **`is_credit_text_line` 6-kelime/nokta kuralı** (`:573-588`): gerçek uzun kredi satırlarını ("Written and directed by…", şirket-künye) refine'de footage sayar; docstring kendi örneğinde yanlış. Yalnız refine'i etkiler, final kadroyu DÜŞÜRMEZ.
- **GİRİŞ refine ileri-yürüme** (`:614-635`): 2 filmde OCR_BACK_CAP=120 tavanına dayandı (+61s film-içine taşma).
- **Sessiz OCR-fail-safe** (`_jenerik_detect.py:37-53`): `build_engine()=None` → refine sessizce no-op, log'a düşmez; paralel modda 2. motor VRAM-çakışmasında sessizce None olabilir.

---

## 3) NET OLMAYAN / DOĞRULANMAMIŞ ALANLAR (dürüst kapsam notu)
- **HANNAH conf sapması:** bağımsız iki ölçüm 0.7227 vs 0.8651 — mutlak conf rakamına değil, FP olgusuna güvenin (frame-seçimine duyarlı).
- **GİRİŞ büyük `_giris_start` kaybı kanıtlanmadı:** 19/53 filmde giris_start>0; iki büyük vaka (KEDİ GÖZÜ @268s, SIRDAŞ @188s) disk-doğrulamada DOĞRU (gerçek geç-açılış). Mid-film static-card riski teorik, bu batch'te materyalleşmedi.
- **QC-CSV vs canlı-log farklı batch'ler:** FP listesi CSV'den (60 film), bloat istatistiği log'dan (53 film); çapraz-kontrol için kullanıldı, bire-bir aynı küme değil.
- **KEDİ GÖZÜ (Film#31):** Pencere DOĞRU, künye bozuk — hata downstream'de (`clean.py:61` frag-gate başrolleri siliyor + qc_block floor-fill). **Jenerik-tespit KAPSAMI DIŞI;** tespit-fix bu vakayı kurtarmaz.
- **Master-PNG `split_runs` kusuru** (`db_compose_master.py` full-frame phaseCorrelate, text-mask'siz) ayrı kök (KN-5 ile aynı siyah-zemin teması) ama dedektör orada SUÇSUZ; KN-1 kapanırsa master'a giren footage azalır.

---

## 4) ÖNERİLEN MÜDAHALE SIRASI (UYGULAMA YOK — Çağatay karar verir; değişiklik yalnız talimatla)

1. **KN-1 (ÇIKIŞ bloat) — `mitas_pipeline.py:1377`.** En yüksek getiri / en düşük risk; tek-yön, mekanik, fail-safe korunur. Tek değişiklik medyan ~157s footage'ı çıkış pencerelerinden kaldırır.
2. **KN-2 + KN-3 + KN-4 birlikte (tek kaldıraç: OCR-kalkanı) — `jenerik_detector.py` geçerlilik-kapısı.** Mevcut OCR-refine altyapısını KALKAN moduna taşı + CLIP-rescue'yu OCR-teyidiyle koşulla. Üç HIGH bulguyu tek noktadan kapatır. **A/B ŞART** (clean-regresyon riski — katı eşik başrol düşürür).
3. **KN-5 (statik çıkış siyah-fade guard).** KN-1 sonrası kalan çıkış-kenar FP'leri için; master-PNG siyah-zemin fix'i ile birlikte planlanabilir.
4. **KN-7 (refine kenar/log iyileştirmeleri) — düşük öncelik.**
5. **KN-6 — gerek yok** (KN-1 çözülünce kapanır).

**Çapraz uyarı:** Dedektör-tarafı fix'leri (madde 2-3) footage-FP kümesi üzerinde A/B ölçülmeden bağlanmamalı. KN-1 (madde 1) bu riski taşımaz.

**İlgili artefaktlar:** `scripts/mitas_pipeline.py:1290-1418`, `core/pipelines/ocr/jenerik_detector.py:270-470/573-672`, `core/pipelines/ocr/slitscan/dynamic_credit_mosaic.py:219-272`, `scripts/_jenerik_detect.py:31-53`, `outputs/system_events.jsonl`, `OCR-worktree/jenerik_qc_FINAL.csv`.
