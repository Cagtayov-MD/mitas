# MITAS — FINAL_RAPOR Hata-Sınıflarının GÜNCEL-KOD Fix-Durumu

*2026-06-22 · git HEAD `1834b5d693` · Opus orkestratör + 1 Opus ortak-araştırmacı (sentez) + 5 Sonnet köşe-bucak tarayıcı + Opus adversarial-refute · SALT-OKUNUR (kod/pipeline DEĞİŞTİRİLMEDİ, commit yok). Statik kod-izleme + ampirik test/smoke ile ÇİFT-TEYİT.*

> **Amaç:** FINAL_RAPOR'da belgelenen 10 hata-sınıfının **aktif/güncel kodda** düzelip düzelmediğini tespit etmek. Filmlere tek tek bakılmadı — yalnız **pipeline mantığı + bayrak durumu + üretim-yolu** denetlendi.

---

## 0) TEK CÜMLE

RED ROCK'taki **3 kritik bug fix'i uygulanmış ve çalışıyor** (VL-Frankenstein, Latin-dışı translit, KB-yapımcı kaynak-kapısı), ama **FINAL_RAPOR §6'da önerilen diğer tüm fix'ler yalnızca rapor metninde planlanmış — koda hiç bağlanmamış** (7 bayrağın hepsi sıfır-tüketici). Dolayısıyla raporun **10 sınıfından 3'ü FIXED/PARTIAL-fix, 3'ü PARTIAL, 4'ü tamamen AÇIK.**

---

## 1) AMPİRİK TEST SONUÇLARI (ne koşturuldu)

| Test | Kapsam (sınıf) | Sonuç |
|---|---|---|
| `pytest` credit/künye alt-kümesi (qc_block, crew-leak, person-gate, channel-lang, name-normalize, suçlu-fixes, pdf-authoritative, locator) | C1·C2·C3·C5·C6 | **55/55 PASS** (gerçek-DB entegrasyonu dahil: `test_integration_ahlat_real_db`) |
| `pytest` OCR-credit alt-kümesi (dynamic-window, scene-router, detector, temporal-fusion, descroll, row-reconstruct, box-track, fallback, skip-routing, confidence) | C2·C7 tespit-tarafı | **139/139 PASS** |
| `credit_qc_otorite_audit_test.py` (saf-fonksiyon) | C1·C2 OCR-otorite | **TÜMÜ PASS** — KEDİ GÖZÜ ikamesi yakalandı + **e2e'de Parker reclaim / Sarrazin dışlandı** |
| `_smoke_fix1.py` (DB'siz, bu denetim için yazıldı) | C1 / FIX-1 | **5/5 PASS** — invariant tutuyor + **KALINTI ampirik doğrulandı** |
| `credit_crosscheck_goldtest.py` (kaynak-kimlik) | C1 kaynak | **KOŞTURULAMADI** — duckdb-GIL çökmesi (ortam sorunu, mantık değil; bkz. §6) |

**FIX-1 smoke detayları (ampirik):**
- ✅ **A1** boş-OCR (BEKARLIK) → `temiz_yap=[]`, karar KONTROL → uydurma yapımcı **imkânsız**.
- ✅ **A2** OCR-okunan gerçek yapımcı (`JOHN SMITH`) kilitsizken bile **KORUNUYOR** (OCR-otorite — haksız düşürme yok).
- ✅ **A3** junk/rol-kelime (`GERÇEK YAPIMCI`) `_only_persons`'ta düşüyor (beklenen).
- ✅ **B1** `cast_ov==2` → `locked=True`.
- ✅ **B2** `cast_ov==2` sahte-kilitte **OCR-dışı `NORMAN LEAR` `temiz_yap`'e girdi** → qc_block'un gevşek eşiği kaynağın `cast_ov≥3` kapısını **baypas ediyor** (KALINTI).

---

## 2) DURUM MATRİSİ (C1–C10)

Lejant: ✅ **FIXED** = uygulandı + default-ON + baypassız · 🟡 **PARTIAL** = kısmen (kaynak kapalı ama bir kol açık / bayrak-OFF) · 🔴 **OPEN** = uygulanmamış veya kök duruyor.

| # | Sınıf | Hüküm | Üretimde aktif? | Özet |
|---|---|---|---|---|
| **C1** | OCR-otorite ihlali (KB-yapımcı + VL/KB OCR-dışı ekleme) | 🟡 PARTIAL | Evet | Kaynak (`credit_kb_lookup`) + VL-adjacency KAPALI; ama `qc_block` S8 bağımsız yapımcı-fill AÇIK |
| **C2** | LOST-ACTOR (başrol düşmesi) | 🔴 OPEN | Evet | qc_block override + S6 garble/only_persons OCR-düşürme + hard cap=8; `MITAS_CAST_*` flag'leri **kodda yok** |
| **C3** | TR-dublaj seslendiren kaybı | 🔴 OPEN | Evet | Ayrı `SESLENDİRENLER` alanı **hiçbir yerde yok**; tek 8-cap'te orijinal kadro TR-sesi eziyor |
| **C4** | name_close OCR-form ezme + orijinal-ad fabrikasyonu | 🔴 OPEN | Evet | `MITAS_OCR_FORM_KEEP` **kodda yok**; S5 fuzzy-snap OCR-formu hep eziyor |
| **C5** | NON-CAST→CAST sızma (yapımcı/teşekkür/müzisyen/hayvan) | 🔴 OPEN | Evet | `raw_context_lines` qc_block'a **geçmiyor** → S1 filtre ölü; keyword listeleri eksik |
| **C6** | Latin-dışı sıfırlama + LID TR→KU | 🟡 PARTIAL | Evet | Latin-dışı translit DÜZELDİ (test PASS); **LID TR→KU vetosu uygulanmadı** (live) |
| **C7** | garble teslime girdi + Latin kör-nokta | 🔴 OPEN | Evet | stitch FREQVOTE scroll'u çözer; statik/sistematik Latin garble baypas; n-gram route default OFF |
| **C8** | POSTER yanlış-film | 🟡 PARTIAL | Evet | Kaynak/KB poster-kapısı gerçek; `credit_identity` 'KESIN' tmdb_id fallback **vsig/cast çapraz-kontrolünü baypas** |
| **C9** | QC false-positive → gereksiz KONTROL | 🔴 OPEN | Evet | XML-cast kapısı qc_block kimlik-bilgisinden ÖNCE ateşliyor; `MITAS_XMLCAST_GATE_RELAX` **kodda yok** |
| **C10** | Kozmetik/metadata (master footage-bloat, sidecar bayat, " 2" klasör) | 🔴 OPEN | Evet | `split_runs` text-mask'siz; sidecar non-film/dizi'de bayat; " 2" her re-run'da |

---

## 3) DÜZELENLER (uygulandı + testle/smoke ile doğrulandı)

1. **FIX #2 — VL Frankenstein-isim adjacency** (`MITAS_VL_RAW_ADJACENCY`, default-ON, `_pipe_credit_vl.py:96`).
   Ayrı satırlardan birleştirilen hayalet-isim (MANASLU "Hans Ebner") DÜŞER; gerçek tek-satır isimler kalır. **4 test PASS.**
2. **FIX #3 — Latin-dışı erken transliterasyon** (`MITAS_NONLATIN_TRANSLIT` + `MITAS_NONLATIN_LLM_ROMANIZE`, default-ON).
   NAMUS DÜŞMANI Arapça kadro `_fold`'dan sağ çıkar; `nonlatin_source=True` → KONTROL. **5 test PASS.**
   ⚠️ **Sınırlama:** `translit_util` import hatası senaryosunda `nonlatin_source=False` kalır → satır orijinal `_fold`'a girer → **%100 kayıp (sessiz)**. Modül kurulu değilse fix etkisiz.
3. **FIX-1 — KB-yapımcı kimlik-kapısı (kaynak yolu)** (`MITAS_PRODUCER_IDENTITY_GATE`, default-ON; `credit_kb_lookup.py:196-199` + `tek_film_kunye.py:568-570`).
   BEKARLIK→Norman Lear named-bug'ı **KAPALI** (boş-OCR'da uydurma imkânsız). **Smoke A1/A2/A3 + otorite-audit PASS.**
4. **(Bonus) OCR-otorite reclaim/audit** (`MITAS_QC_FLOORFILL_OCRGUARD`, default-ON; `credit_qc_block.py:652`).
   KEDİ GÖZÜ ikamesi tespit + **düşen başrol (Parker) ham-OCR'dan reclaim, OCR-dışı (Sarrazin) dışlandı**. Otorite-audit TÜMÜ PASS. *(C2'nin yalnız "locked + groundtruth-yüklü" dilimini kapatır; geneli değil.)*

---

## 4) HÂLÂ YAŞAYANLAR

### 🟡 Kısmen (kaynak kapalı, bir kol açık)
- **C1 — qc_block S8 yapımcı-fill (`credit_qc_block.py:677`).** Üretim-otoritesi olan qc_block, `_kb_producers(kb, imdb_id)` ile **OCR-dışı IMDb yapımcılarını** yazıyor; tek kapı `locked` — ki `director-anchor-weak` (tek-aday film / yıl±1) ile **cast_ov=0'da bile** kilitlenebiliyor. Kimlik-kapısı YOK; sonuç `tek_film_kunye:645-646`'da `yap`'ı yeniden-kapısız EZİYOR. **Smoke B2 ampirik doğruladı.** *(BEKARLIK değil ama zayıf-kimlik dilimi.)*
- **C6 — LID TR→KU.** Latin-dışı translit düzeldi; ama `_channel_lang.py:188 select_summary` TR-konuşma kanalı yoksa ilk-konuşma-kanalını (ku dahil) TR-oyu kontrolü olmadan seçiyor → ku→ASR atlanıyor→yanlış özet. `MITAS_LID_TR_VETO` **kodda yok.**
- **C8 — POSTER.** `credit_identity.resolve()=='KESIN'` tmdb_id'si `_fetch_tmdb_poster`'a doğrudan girip **vsig (versiyon/sekel) + cast çapraz-kontrolünü atlıyor** (bunlar yalnız `_search` kolunda). `MITAS_POSTER_VER_GATE` **kodda yok.**

### 🔴 Tamamen açık (hiç uygulanmamış)
- **C2 — LOST-ACTOR.** qc_block koşulsuz cast-override + S6 garble/only_persons'ın **KB'de olmayan OCR-okunan oyuncuyu** sessizce düşürmesi (S7 floor yalnız KB-cast'i geri getirir → kalıcı kayıp) + kaldırılamayan 8-cap + tek-blok seçimi + FRAG tek-token atma. `MITAS_CAST_MULTIBLOCK / _OCR_RECLAIM / _NO_HARD_CAP` **yalnız FINAL_RAPOR.md'de, kodda sıfır tüketici.**
- **C3 — TR-dublaj seslendiren.** Ayrı `SESLENDİRENLER` alanı şemada/render'da hiç yok.
- **C4 — name_close OCR-form ezme.** S5 (`credit_qc_block.py:629-638`) her zaman OCR-formu KB-kanonik forma snap'liyor; `MITAS_OCR_FORM_KEEP` okuyan tek satır yok.
- **C5 — NON-CAST sızma.** `tek_film_kunye:636` qc_block'u `raw_context_lines` olmadan çağırıyor → S1 bağlam filtresi no-op; `_CREW_CONTEXT_KW`/`NON_ACTOR_PROFS` listelerinde producer/teşekkür/wrangler/redaktion yok.
- **C7 — garble Latin kör-nokta.** stitch FREQVOTE scroll-çoklu-okumayı çözer ama statik-kare/sistematik-OCR garble'ı (`garble('DAMES DARREN')==0.0`) baypas; downstream detektörler Latin-scramble'a kör; `MITAS_GARBLE_NGRAM_ROUTE` default-OFF.
- **C9 — gereksiz KONTROL.** XML-cast kapısı (`mitas_pipeline.py:1923-1932`) `_v4j` parse'tan ÖNCE çalışıyor → `locked/cast_ov/verdict` henüz yok → kimlik-teyitli filmi bile KONTROL'e atıyor. `MITAS_XMLCAST_GATE_RELAX` **kodda yok.** (742-KONTROL darboğazını besliyor.)
- **C10 — kozmetik.** `db_compose_master.py:333` `split_runs` text-mask'siz phaseCorrelate (siyah-zemin jenerik→cut→eler, footage-bloat); sidecar v4-sonrası non-film/dizi profillerde bayat; `mitas_pipeline.py:1228` " 2"/" 3" klasör her re-run'da.

---

## 5) ÖNERİLER — yeniden-koşu öncesi öncelik (en yüksek getiri / en düşük risk)

Hepsi **additive + flag-kapılı + invariant-koruyan** olmalı (bkz. §7). Opus ortak-araştırmacı sıralaması:

1. **C9 — XML-cast kapısını `_v4j` sonrasına taşı + gevşet** (`MITAS_XMLCAST_GATE_RELAX`, default OFF→A/B→ON). **EN DÜŞÜK risk, YÜKSEK getiri:** yalnız kimlik-teyitli filmden gereksiz KONTROL'ü kaldırır, kötü-veri sızdıramaz; 742-KONTROL darboğazını açar.
2. **C1 — qc_block S8'e kimlik-gücü kapısı** (`credit_qc_block.py:677`'e `verdict=='TEYİT' OR cast_ov>=3` şartı, kaynakla simetrik; `MITAS_PRODUCER_IDENTITY_GATE` yeniden-kullan, default ON). ~3 satır. Son KB-yapımcı uydurma kolunu kapatır. **DÜŞÜK risk.**
3. **C8 — id-tabanlı poster fallback'ine vsig/cast çapraz-kontrolü** (`MITAS_POSTER_VER_GATE` bağla). "afiş-yok > yanlış-afiş" invariant'ı; görünür yanlış-veri.
4. **C6 — `select_summary`'de TR-veto** (`MITAS_LID_TR_VETO`, default ON ama **TR-menşei kapılı** — KB-ülke/XML; gerçek Kürtçe filme dokunma).
5. **C5 — `raw_context_lines`'ı bağla + crew keyword/meslek listelerini genişlet** (default OFF→A/B). Producer/teşekkür/wrangler/redaktion sızıntısını keser.
6. **C7 — Latin garble n-gram → KONTROL'e route** (silme değil; default OFF→gözlem→ON) + statik-kare çapraz-konsensüs.
7. **C2 — garble-gate'e OCR-groundtruth istisnası + cap'i `MITAS_CAST_CAP` ile yapılandırılabilir kıl** (opt-in). KB'de-olmayan OCR-oyuncuyu S6 sessiz-düşürmesinden korur.
8. **C4 — `MITAS_OCR_FORM_KEEP`: fuzzy-snap'i bastır** (exact `name_match` snap'i koru; A/B sonra default).
9. **C3 — additive `SESLENDİRENLER` alanı** (8-cap'le yarışmaz; default OFF, render+doğrulama sonrası). *TRT dublaj-arşivi için teslim-değeri kritik.*
10. **C10 — `split_runs`'a koşullu (parlaklık-kapılı) text-mask + non-film/dizi sidecar + " 2" idempotency.**

---

## 6) SINIRLAMALAR / TEST EDİLEMEYENLER

- **`credit_crosscheck_goldtest.py` koşturulamadı:** her iki yorumlayıcıda (global Python310 + venvs/ocr) `imdb_find` duckdb sorgusunda `PyEval_SaveThread … GIL … NULL` ölümcül hatası. Bu bir **ortam/duckdb-threading uyumsuzluğu**, kredi-mantığı regresyonu DEĞİL — `test_integration_ahlat_real_db` aynı crosscheck'i pytest altında gerçek-DB ile başarıyla koştu. C1 kaynak-kimlik yine de otorite-audit + person-gate + smoke ile kanıtlı.
- **Film-içeriği doğrulanmadı (talep gereği):** bu rapor pipeline-mantığı durumudur; tek tek film çıktısı sen yeniden-koşunca ölçülecek.
- **DeepSeek HTTP 402'ler:** smoke/test loglarındaki ödeme hataları özet-LLM fallback'i; credit/kunye mantığıyla ilgisiz, testler yine de geçti.

---

## 7) KORUNACAK INVARIANT'LAR (fix'ler bunları BOZMAMALI)

1. **FAIL-SAFE:** her QC/credit bloğu try/except ile sarılı kalmalı — hata olunca mevcut cast/yön/yap AYNEN kalır, pipeline çökmez (`_v4j` UnboundLocalError dersi).
2. **OCR-OTORİTE:** OCR-okunan isim otoriterdir; KB yalnız EXACT/güçlü eşleşmede yazım düzeltir ve OCR-boşken **güçlü-kimlik kapısıyla** doldurur — asla okunan ismi SİLMEZ/İKAME etmez, kimlik-kanıtsız OCR-dışı isim EKLEMEZ.
3. **GARBLE → KONTROL (asla sessiz silme):** garble tespiti filmi insana yönlendirir, ismi düşürmez (additive route).
4. **YÖNETMEN = kimlik çapası:** geçerli OCR-yönetmeni KİLİTLİ; kişi-değişimi KIRMIZI BAYRAK→KONTROL (sessiz KB-ezme yok).
5. **"yanlış > boş" / "afiş-yok > yanlış-afiş":** kimlik güçlü-doğrulanmadıkça boş yapımcı/tür/afiş (→KONTROL) tercih edilir; C9 gevşetmesi bunu ters çeviremez (yalnız güçlü-teyitli filmde KONTROL azaltır).
6. **Additive / flag-kapılı:** default-OFF + A/B sonra default-ON; mevcut üretim-yolunu sessiz değiştirme.
7. **Tek otoriter cast→PDF:** `.txt` ve PDF aynı tek-listeden beslenir; fix'ler hizayı bozmamalı (sidecar-bayat ayrışması C10#2 yeniden doğmamalı).

---
*Üretim env teyidi: `MITAS_QC_BLOCK=1`, `MITAS_QC2=1`, `MITAS_QC_DIRECTOR_ANCHOR=1` (`start_mitas.ps1`), `MITAS_PRODUCER_IDENTITY_GATE`/`MITAS_VL_RAW_ADJACENCY`/`MITAS_NONLATIN_*` kod-default ON. Artefaktlar: `outputs/RUN_WATCH_20260622/_smoke_fix1.py`, `_pytest_credit.log`, `_pytest_ocr.log`, `_goldtest*.log`.*
