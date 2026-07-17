# MITAS — Fix Oturumu Raporu (2026-06-20)

**Commit:** `85f9a40984` (master) · 5 dosya, +173/−20
**Önceki bağlam:** [Son 250 Çıktı Forensik Raporu](SON_250_FORENSIK_RAPORU_2026-06-20.md)

---

## 0. Bağlam — neden bu işler?

Database'deki son 250 çıktının forensik denetimi (50-ajan, log-kanıtlı) **248/250 bozuk** olduğunu gösterdi. Hata 5 üst-üste binmiş kök-nedenden geliyordu. Bu oturumda bunların **4'ü kodda düzeltildi**; 5. ve 6. (QC1_NOISE + PERSON_GATE) zaten `ac04db26a2` (06-19 codex-fix) ile kapanmıştı.

> **Kritik ayrım:** Kod düzeltmeleri **gelecekteki** (ve yeniden-işlenen) çıktıları düzeltir. Mevcut 250 çıktı, düzeltmeden ÖNCE üretildiği için **hâlâ bozuk** — re-render gerekir (Bölüm 5).

---

## 1. Yönetici Özeti

| # | Düzeltme | Etkilenen | Dosya | Durum |
|---|---|---|---|---|
| 1 | ASR_LANG — eksik dil-kodu çökmesi | 25 film | `_channel_lang.py`, `_pipe_asr.py` | ✅ kod + smoke |
| 2 | PROPAGATION — PDF≠txt sapması | 189 film | `mitas_pipeline.py`, `tek_film_kunye.py` | ✅ kod + smoke |
| 3 | VL-halüsinasyon — uydurma isim | 25 film | `_pipe_credit_vl.py` | ✅ kod + smoke |
| 4 | FUZZY-DBQC default-on — karakter+garble | ~tahmini 30-60 film | `tek_film_kunye.py` | ✅ kod + 11-film ölçüm |

Tüm dosyalar `py_compile` geçti. Hiçbir fix mevcut yapıyı bozmuyor (her biri fail-safe + geriye-uyumlu).

---

## 2. Yapılan Düzeltmeler (detay)

### 2.1 ASR_LANG — eksik ISO-639-3 dil-kodu → ASR çökmesi → özet boş

**Sorun:** 25 yabancı film özeti `(ÖZET AYRI BİR ADIMDA ÜRETİLECEKTİR.)` placeholder; Ses & Altyazı eksik.

**Kök-neden (koda karşı doğrulandı):** `_channel_lang.py:45` `_map_lang` eşlenemeyen 3-harf kodu **ham** döndürüyordu (`_LANG_MAP.get(c, c)`); whisper'a `swe`/`cmn`/`vie` gibi geçersiz kod gidip `ValueError` fırlatıyordu → 0 segment → transcript yok.

**Değişiklik:**
- `_channel_lang.py:35` — `_LANG_MAP` ~70 dille genişletildi (swe→sv, est→et, isl→is, cmn→zh, yue→yue, jav→jw, vie→vi, mon→mn, nor→no, dan→da, fin→fi, slk/slv/lit/lav, tha/ind/msa/tgl/ben/tam/te/mr/gu/kn/ml/pa/si/ne, swa/amh/hau/yor/som/afr, vs.).
- `_pipe_asr.py` — `_WHISPER_OK` (whisper'ın desteklediği 100 dil frozenset) + `_lang_unsupported()` saf-fonksiyon; mevcut `if language == "ku"` atlama-bloğu **genelleştirildi**: whisper-dışı/eşlenemeyen herhangi bir kod artık çökmek yerine `skipped_unsupported_lang` ile dürüstçe atlanıyor (çöp-tr transkripti üretmez; özet internetten gelir).

**Smoke-test:** ✅ 25 filmin tüm dilleri doğru eşlendi (swe→sv...); kapı supported/unsupported'ı doğru ayırdı; whisper-seti 100 dil.

---

### 2.2 PROPAGATION — PDF temiz ama .txt çöp (PDF≠txt sapması)

**Sorun:** Oyuncular alanında şoför/craft/müzik-kredi/şirket çöpü (`SCOTTY BRATTON`, `CRAFT SERVICES DORA CSUPORT`), yönetmen/yapımcı yanlış.

**RAPORDAKİ ÇERÇEVE DÜZELTİLDİ (ampirik):** Forensik rapor "credit_validate ADDITIVE, doğru-değer çöpe gidiyor" demişti. UMUTSUZ SAAT'i uçtan-uca izleyince gerçek farklı çıktı:
- **V4 PDF (`kunye.pdf`) ZATEN TEMİZ** üretiliyor — NAOMI WATTS, PHILIP NOYCE, doğru afiş (görsel olarak doğrulandı). `tek_film_kunye` `video_credits`'i doğru kullanıyor.
- Asıl bug bir **PDF≠TXT sapması:** yüzey `.txt`, `surface_deliverables`'in `kunye_teslim.md`'den ürettiği. O `.md`'yi `_pipe_pdf` **ham `cp.parse_credits`** çöpüyle yazmış (kanıt: `parse_credits` ham OCR'dan birebir `SCOTTY BRATTON...` üretiyor) ve **V4 `.md`'yi güncellemiyor.**

**Değişiklik (mevcut `tur_override` deseninin aynısı):**
- `tek_film_kunye.py` `rapor["v4"]` — otoriter `cast_list` / `yonetmen_list` / `yapimci_list` / `keywords` (= PDF'e basılan `d` değerleri) eklendi.
- `mitas_pipeline.py` — `_patch_md_credits()` yardımcısı + `surface_deliverables(..., v4_credits=)` parametresi; V4-kabul anında (PDF os.replace noktasında) `v4_credits` yakalanıp `.md`'nin 3 bölümü (Oyuncular / Anahtar Sözcükler / Yapım Ekibi) V4 değerleriyle yamalanıyor → `.txt` = PDF.

**Smoke-test (gerçek fonksiyonlar, gerçek veri):** ✅ Üretici: `tek_film_kunye` temiz `cast_list` yayıyor (NAOMI WATTS, PHILIP NOYCE, gerçek yapımcılar). ✅ Tüketici: gerçek çöp `.md` → `.txt` = temiz; SCOTTY/CRAFT gitti; Ses/Özet/specs korundu.

---

### 2.3 VL-halüsinasyon — gemma4-VL pikselden isim uyduruyor

**Sorun:** FOTOĞRAF final yönetmen `JEFF TOWLES` (gerçek Ritesh Batra) — filmde hiç olmayan uydurma isim. VL ayrıca filmde olmayan oyuncu ekliyordu.

**Kök-neden:** `_pipe_credit_vl.py` VL çıktısını sadece cross-cast + `_only_persons` ile filtreliyordu; **OCR'a karşı doğrulama yoktu**. VL pikselden (afiş/bağlam) isim uydurabiliyor.

**Değişiklik (`credit_validate._recover_raw` deseni):** `_load_raw_ocr()` (jenerik karelerinin ham OCR'ı: `ocr_raw_all`+`ocr_ham`+`kunye`) + `_in_raw()` (≥4-harf token'ların tümü ham OCR'da olmalı). VL-eklenen yönetmen+cast bu kalkandan geçer; ham OCR'da yoksa = uydurma → düşürülür → boş/KONTROL. FAIL-SAFE (ham OCR yoksa kalkan atlanır).

**Smoke-test (gerçek FOTOĞRAF):** ✅ `JEFF TOWLES` (ham OCR'da yok) → düşer → yönetmen boş → KONTROL. ✅ Ham OCR'da geçen isimler korunur. Mantık: VL aynı kareleri okur, OneOCR de o kareleri ham metne döker → gerçek isim ham OCR'da bulunur.

---

### 2.4 FUZZY-DBQC default-on — karakter-kontaminasyonu + KB-kapsamlı garble

**Sorun:** Cast'te karakter-adı+aktör karışık (`MAURA SALLY HAWKINS` = karakter Maura + aktör Sally Hawkins) ve garble (`JONM ARCYER`). Düz `name_match` token-sayısı farkından fire ediyor.

**Çözüm zaten kodda vardı ama KAPALIYDI:** `credit_crosscheck.name_close_window` (kayan-pencere KB eşleştirme) + `cast_overlap_fuzzy`, flag `MITAS_FUZZY_DBQC` (varsayılan kapalı).

**Karar veriyle alındı — 11-film ölçümü** (`tek_film_kunye` FUZZY kapalı vs açık, girdi = validate-log cast, tek değişken FUZZY):

| Film | FUZZY OFF | FUZZY ON | Hüküm |
|---|---|---|---|
| SONSUZA KADAR MUTLULAR | MAURA SALLY HAWKINS, MOLLY SINEAD MAGUIRE, KAREN TINA KELLEGHER | **SALLY HAWKINS, SINEAD MAGUIRE, TINA KELLEGHER** | ✅ karakter-prefiks temizlendi |
| SUNDOWN'DA KARAR GÜNÜ | NOAH BEERY CO-STARRING, JONM ARCYER | **NOAH BEERY JR., JOHN ARCHER** | ✅ garble→kanonik |
| Diğer 9 film | — | (değişmedi) | ✅ yanlış-snap YOK |

**Sonuç: 11 filmde 0 yanlış-snap, 2 film doğru temizlik.** Temiz yabancı/Türkçe filmlere, KB'nin tanımadığı filmlere hiç dokunmadı (kimlik-kilidi `cast_ov≥2` same-title'ı koruyor).

**Değişiklik:** `tek_film_kunye.py:382` — `MITAS_FUZZY_DBQC` **varsayılan AÇIK** (opt-out `=0`).

**Smoke-test (default-on, env'siz):** ✅ SONSUZA KADAR MUTLULAR → SALLY HAWKINS... (temizlendi); ✅ KİRALIK SİLAH (temiz) → değişmedi (regresyon yok).

---

## 3. Zaten kapanmış kök-nedenler (codex regresyonu)

| Kök-neden | Film | Durum |
|---|---|---|
| QC1_NOISE (disclaimer/müzik-kredi sızması) | 149 | `ac04db26a2` (06-19) `_prefilter` geri → **kodda DÜZELDİ** |
| PERSON_GATE (gerçek oyuncu düşürme) | 27 | `ac04db26a2` kişi-kapısı varsayılan OFF → **kodda DÜZELDİ** |

> Bu ikisi de codex `0fbca67535` regresyonuydu; kodda düzeldi ama **bu 250 çıktı düzelmeden önce üretildi** → re-render'da düzelir.

---

## 4. Değişen dosyalar

```
scripts/_channel_lang.py    +30   (ASR dil-kod haritası)
scripts/_pipe_asr.py        +43   (whisper-geçerli dil kapısı)
scripts/_pipe_credit_vl.py  +39   (VL hayalet-kalkanı)
scripts/mitas_pipeline.py   +59   (PDF≠txt propagation patch)
scripts/tek_film_kunye.py   +22   (V4 otoriter yüzey-değerler + FUZZY default-on)
```
Commit: `85f9a40984` — master.

---

## 5. EKSİKLER ve YAPILMASI GEREKENLER

### 🔴 5.1 — KRİTİK: 250 mevcut çıktı henüz BOZUK (re-render şart)
Kod düzeldi ama **mevcut 250 .txt/.pdf, düzeltmeden önce üretildi.** Veri ancak yeniden-işlenince düzelir.
- **Engel:** `video_credits` diske kaydedilmiyor → re-render'da `tek_film_kunye` else-dalı OCR'dan `read_credits_auto` ile yeniden okur (ollama 35B gerekir).
- **Yapılacak:** Bir **re-render batch tool'u** — OCR/ASR'yi yeniden koşmadan (mevcut `ocr/` ve `asr/` kullanarak) sadece credit-finalize → PDF → surface zincirini her klipte tekrar koşsun. Önce codex-penceresi 115 + bu fix'lerden etkilenen filmler.
- **Doğrulama:** Re-render sonrası 10-15 filmde önce/sonra .txt diff + görsel PDF kontrolü.

### 🟠 5.2 — garble→KONTROL yönlendirmesi (KB-kapsamsız artıklar)
KB'nin tanımadığı artık-garble FUZZY ile düzelmiyor: `UMUTSUZ SAAT` MEKENZIE EVELYN WIEBE, `MANDIRA` GIVENLIIK BURAK ORHAN, `SUNDOWN` GRICHAAD OEACON. Bunlar düzeltilemez → doğru cevap **KONTROL'e yönlendirme** ("okunamadı>yanlış").
- **Kanıt:** Forensik'te 82 garble filmin **71'i `GUVENILIR` damgalıydı** = OCR garble'ı "güvenilir" sanıp KONTROL'e göndermemiş.
- **Yapılacak:** QC2 router'a deterministik denetim: cast/yön'de KB-doğrulanamayan + olabilirlik-düşük token varsa → tier'i AĞIR'a yükselt, **ONAYLI/AUTOFIX'e asla düşürme.**

### 🟠 5.3 — false-positive ONAYLI durdurma
`TAKIM` gibi filmler cast garble doluyken `ONAYLI` damgalanmış (QC2 router cast-içeriğine bakmıyor). 5.2 ile aynı router-fix kapsamında çözülür. **MITAS1 felaketi riski** (yanlış ONAYLI).

### 🟡 5.4 — FUZZY-DBQC geniş validasyon
11 film küçük örneklem (0 yanlış-snap umut verici). Same-title teorik riski kimlik-kilidiyle azaltılmış ama **50+ filmlik batch** ile teyit önerilir; yanlış-snap çıkarsa eşik (0.80) yükseltilir veya kimlik-kilidi sıkılaştırılır.

### 🟡 5.5 — Perplexity garble-gate: KURMA
Veri gösterdi ki FUZZY-DBQC (KB-pencere) garble'ı doğru çözüyor; ayrı bir perplexity/dil-modeli **gereksiz ve riskli** (memory: naive gate ZARARLI). KB-kapsamsız artıklar için doğru cevap salvage değil, 5.2'deki KONTROL yönlendirmesi.

### 🟢 5.6 — Yapısal / uzun vade
- **OCR recall tavanı (~%47):** İsimlerin yarısı OCR çıktısında hiç yok (arşiv/düşük-kontrast/diegetik). Frame-seçimi iyileştirme + PaddleOCR-GPU fallback (codex `a0c28be589` kapattı) ayrı büyük iş.
- **Latin-dışı kaynak (~9-15 film):** Kaynakta Latin künye yok (Arapça/Çince/Kiril/Moğol jenerik) → düzeltilemez; KONTROL'e gitmeli (5.2).
- **`kunye_teslim.md` disk-üstü hâlâ ham:** Sadece `.txt` (deliverable) yamalandı. `.md` ara-dosya; istenirse senkronlanır (minor).
- **VL kalkanı ağır-garble karede over-drop edebilir:** Kasıtlı ("okunamadı>yanlış"); ölçülmedi, izlenebilir.
- **Manuel `kunye_fixed.pdf` batch (codex, ayrı sorun):** Memory'ye göre codex'in elle batch'i OCR-garble'da KB-uydurma kadro yazıp ONAYLI damgalamış (~574 dosya, `HELEN'E NE OLDU` kanıt). Bu AYRI bir temizlik işi — bu oturumda dokunulmadı, ele alınmalı.

---

## 6. Doğrulama / nasıl test edilir

- **ASR_LANG:** `python scripts/_channel_lang.py` import + `_map_lang('swe')=='sv'`. Gerçek veri: bir İsveççe filmde ASR yeniden koş → transcript üretilmeli (placeholder değil).
- **PROPAGATION:** Re-render sonrası `.txt` Oyuncular bölümü = PDF Oyuncular bölümü (birebir).
- **VL:** FOTOĞRAF re-render → yönetmen `JEFF TOWLES` DEĞİL (boş/KONTROL).
- **FUZZY:** Re-render → SONSUZA KADAR MUTLULAR cast = SALLY HAWKINS... (karakter-prefiks yok).

---

## 7. Önerilen sıradaki adımlar (öncelik sırası)

1. **Re-render batch tool** + 250 çıktıyı yeniden işle (5.1) — *kod fix'leri veriye yansımazsa hiçbiri görünmez.* EN KRİTİK.
2. **QC2 router fix** — garble→KONTROL + false-positive-ONAYLI durdurma (5.2 + 5.3). Tek değişiklikte ikisi.
3. **FUZZY-DBQC 50+ film validasyonu** (5.4) — default-on'a tam güven.
4. **Uzun vade** (5.6): OCR recall, Latin-dışı, manuel-fixed-pdf temizliği.

---
*Bu rapor, 2026-06-20 fix oturumunun tam kaydıdır. Tüm kök-neden iddiaları koda ve gerçek film verisine karşı doğrulanmıştır.*
