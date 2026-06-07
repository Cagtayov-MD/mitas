# MITAS — KAPSAMLI DENETİM RAPORU (Tur 3)
**Tarih:** 2026-06-06 · **Yöntem:** 14 paralel doğrulama ajanı (koda karşı doğrula + BUGÜN taze koş + bayat-artefakt tuzağından kaçın) + merkezi basit-hata düzeltmesi + uçtan-uca capstone koşusu.
**Kapsam:** Çağatay'ın 12 başlıkta sıraladığı tüm iddialar, üretim yoluna bağlılık (ölü-kod değil) ve canlı kanıt ile sınandı.

---

## 1. VAAD–GERÇEK TABLOSU (özet)

| # | İddia | Verdikt | Not |
|---|-------|---------|-----|
| 1 | PDF tümü TR-büyük harf, yabancı ASCII, Latin-dışı yok | **KISMEN** | Kasa+Latin-dışı eleme tam; yabancı-ASCII yalnız cast/crew+altyazıda — başlık/özet prozasında aksan kalabilir (tasarım tavizi) |
| 2 | OneOCR + GLM iki ana okuyucu, aktif | **ÇALIŞIYOR** | İkisi de bağlı, GLM default açık; canlı koşuda ikisi de okudu (asimetrik: OneOCR omurga, GLM additive) |
| 3 | Afiş eksiksiz PDF'e, isim algoritması düzgün | **DÜZELTİLDİ** | Yerli-film YANLIŞ afiş bug'ı bulundu → fix uygulandı + canlı doğrulandı |
| 4 | Yön/yapımcı her dilde bulunur, sıfat sızmaz | **ÇALIŞIYOR** | Çok-dilli sözlük + sızıntı-eleme tam; 2 recall açığı (yalnız XML'siz) |
| 5 | Dili dinle→algıla→uygun ASR→Sonnet; köprü | **ÇALIŞIYOR** | 4 parçanın hepsi bağlı+canlı doğrulandı |
| 6 | En önemli oyuncular doğru algoritmayla PDF'e | **ÇALIŞIYOR** | IMDb billing sırası; iki kaynak (OCR+KB) birleşiyor |
| 7 | IMDb/Wikipedia dataset ile isim teyidi aktif | **ÇALIŞIYOR** | Yerel duckDB (13M kişi); "filmi tanı→kanonik kadro" stratejisi |
| 8 | qwen ile final QC → hazır/kontrol → klasör | **BOZUKTU → DÜZELTİLDİ** | `mitas_pipeline`'da `import sys` eksikti → qwen_qc HER koşuda NameError ile sessizce ölüyordu (capstone yakaladı); fix + canlı verdict doğrulandı (bkz. §5) |
| 9 | XML↔PDF karşılaştırma yapısı aktif | **KISMEN → DÜZELTİLDİ** | B-4 cast-kesişim kapısı AYNI `import sys` eksiğinden (satır 806) XML'li klipte sessizce atlanıyordu; fix ile onarıldı. Helper mantığı (cast_overlap) sağlam |
| 10a | UI + kuyruk sistemi | **ÇALIŞIYOR** | 37 route eşleşiyor, kuyruk disk-kalıcı, canlı doğrulandı |
| 10b | UI tek-dosya yükleme | **ÇALIŞIYOR** | İki upload yolu tam, canlı smoke geçti |
| 10c | UI Tedial bağlantısı | **ÇALIŞIYOR** | b192610f fix diskte, 13 test geçti, rotation+auto-login canlı |
| 11 | Genel performans sorunu + bug | **SORUN VAR** | Somut perf bulguları (büyüyen-DB) + D3 idempotency bug'ı bulundu; kritikleri düzeltildi |
| 12 | Tüm alanlar smoke | **YEŞİL** | 474 pytest pass + tüm validator/smoke; tek gerçek defekt: pyannote/protobuf (varsayılan profili etkilemez) |

---

## 2. UYGULANAN BASİT DÜZELTMELER (hepsi doğrulandı)

| # | Dosya:satır | Değişiklik | Doğrulama |
|---|-------------|-----------|-----------|
| **F11★** | `scripts/mitas_pipeline.py:17` | **KRİTİK:** eksik `import sys` eklendi → `sys.path.insert` satır 776 (qwen_qc) + 806 (B-4 cast kapısı) NameError'ı giderildi | **CANLI:** `mp_has_sys=True` + qwen_qc gerçek verdict |
| F1 | `scripts/_pipe_pdf.py:348` | Fallback PDF'te ham `ozet` → `ozet_norm` (normalize edilmiş) | py_compile OK |
| F2 | `OCR-worktree/pdf-mitas/credit_parse.py:137` | `_ROLE_DISQUALIFY` `"art "` → `"art direct"` (gerçek "Art Malik" adını elemesin) | py_compile OK |
| F3 | `OCR-worktree/pdf-mitas/poster_fetch.py:322` | **Yabancı-başlık tuzağı:** kadro biliniyor + exact aday `s` dolu ama kadro tutmuyorsa → havuzda kadrosu tutan adayı seç, yoksa afiş YOK | **CANLI:** Ahlat→doğru film (tt6628102); Inception/Black Beauty regresyon yok |
| F4 | `scripts/_pipe_ocr.py:35` | Ölü `CONSENSUS_GLM` referansı kaldırıldı (fonksiyonlar inline) | py_compile OK |
| F5 | `scripts/_pipe_ocr.py:614` | Log yazım hatası `ATLAINDI`→`ATLANDI` | py_compile OK |
| F6 | `core/pipelines/asr/version.py:10` | `get_code_version` `@lru_cache` — her çağrıda 2 git subprocess (~94ms) elendi | **cache_info hits=1** doğrulandı |
| F7 | `core/api/asr_server.py:3342` | `_write_json` ATOMİK (temp+os.replace) — flow-queue worker'ı bozuk okumayla ölmesin (D3 idempotency) | import OK, 37 route |
| F8 | `scripts/mitas_pipeline.py:565,607` | OCR/ASR Popen `.kill()` sonrası `.communicate(timeout=10)` — pipe drenajı/reaping | py_compile OK |
| F9 | `scripts/run_model_smoke_tests.py:64` | `disabled:` adayını çalıştırmayı bırak (FileNotFoundError yerine skip) | mantık doğrulandı |
| F10 | `tests/test_ocr_box_track_pipeline.py`, `test_image_quality_police.py`, `test_ocr_text_layer_row_reconstruct.py` | `pytest.importorskip("cv2")` — asr venv'de OCR testleri sahte-fail yerine temiz SKIP | **12 passed, 11 skipped** doğrulandı |

**Geri alınan:** `core/api/tedial/session.py:325` (`_load_persisted` `connected`→`connecting`) denendi → **2 test kırıldı** (`cookie_header_for` restart-dayanıklılığı için `connected` bekliyor). Geri alındı, 13 test tekrar yeşil. Ders: ajanın "trivial" dediği değişiklik test koşulunca güvensiz çıktı — bayat-artefakt değil, gerçek-test disiplini kazandı.

---

## 3. BAŞLIK BAŞLIK DETAYLI BULGULAR

### Görev 1 — PDF büyük harf / ASCII / Latin-only (KISMEN)
- **Çekirdek:** `OCR-worktree/pdf-mitas/name_normalize.py` — `tr_upper` (TR-kasa i→İ, ı→I + Latin-dışı eleme), `upper_names`/`upper_crew` (köken-duyarlı: Türk→TR-kasa, yabancı→ASCII-fold).
- **Üretim:** `tek_film_kunye.py` (v4) `kunye.pdf`'i üretir; başlık+özet `tr_upper`, cast/crew `upper_names`, altyazı `up_o`.
- **CANLI:** `istanbul→İSTANBUL`, `ışık→IŞIK` ✓; `François→FRANCOIS` (cast yolu) ✓; Kiril/Yunan/Arap/CJK her yolda elenir ✓.
- **AÇIK (tasarım tavizi):** Başlık/özet PROZASINDA yabancı aksanlı ad (FRANÇOİS, JOSÉ, MÜLLER) ASCII'ye katlanmıyor — `tek_film_kunye.py:84` yazarı "prozada token ayırt edilemez" diye bilerek kabul etmiş. Latin-DIŞI yine her yerde eleniyor (iddianın "başka alfabe gelmez" kısmı TAM tutuyor). **Karar Çağatay'a:** kural harfiyen mi (yabancı başlık/özette aksan düşsün) yoksa mevcut taviz mi.

### Görev 2 — OneOCR + GLM çift-motor (ÇALIŞIYOR)
- `scripts/_pipe_ocr.py`: Motor-1 OneOCR (`read_pos`→`stitch`→`clean`, omurga); Motor-2 GLM (`glm-ocr:latest` ollama, additive). Default AÇIK (`MITAS_OCR_GLM_CONSENSUS=1`).
- **CANLI (14 kare):** GLM AÇIK → `engine:pipeline100+glm`, stitch 7 + GLM 11 satır, agree_count 9, GLM-only 2 eklendi, 42.5s GLM inferansı. GLM KAPALI → `engine:pipeline100`, 9.5s, graceful. Telemetri (`glm_status/attempted/skip_reason`) her yolda yazılıyor.
- **Nüans:** "iki eşit-peer oy" değil; OneOCR omurga, GLM additive-takviye + çapraz-doğrulama (agree_count). GLM düşse künye yine tam üretilir (regresyon-güvenli).

### Görev 3 — Afiş import + isim algoritması (DÜZELTİLDİ)
- Gömme `_make_pdf.py:98-116` sağlam (en-boy korur, afiş yoksa graceful). Yabancı yol doğru.
- **BUG (bulundu+düzeltildi):** `poster_fetch._search` tam-başlık tek-aday'ı kadro teyidi YAPMADAN dönüyordu. Yerli film (Ahlat) IMDb'de İngilizce başlıkla ("The Wild Pear Tree") kayıtlı → aynı adlı alakasız yapım kazanıyor, **yanlış afiş sessizce "Hazır"a gidiyordu** (gerçek üretim PDF'inde AKM görseli bulundu). F3 ile kadro-teyitli seçim eklendi; canlı testte Ahlat→doğru film döndü, yabancılar regresyona uğramadı.

### Görev 4 — Yönetmen/Yapımcı çok-dilli + sıfat sızıntısı (ÇALIŞIYOR)
- `credit_parse.py:69-101` çok-dilli rol sözlüğü (TR/EN/FR/DE/IT/ES + RU/AZ/GR/AR/ZH translit). `_ROLE_DISQUALIFY`/`is_company`/tek-kelime filtresi sızıntıyı eler ("Diğer"e düşürür, uydurmaz).
- **CANLI:** 8-dil etiketli liste doğru yönlendi; `EXECUTIVE PRODUCER`/`CASTING DIRECTOR`/şirket adı bare Yönetmen/Yapımcı'ya GİRMEDİ. Gerçek XML (Ahlat) `V_ROLE_TYPE`→yönetmen doğru.
- **AÇIK (recall, yalnız XML'siz):** Birleşik "ETİKET İSİM" tek satırı (`PRODUCED BY X`) ve çok-boşluklu karakter+oyuncu kolonu — isim kaçabilir. XML ankrajı bunu üretimde düzeltiyor.

### Görev 5 — Dil tespiti → ASR → Sonnet → köprü (ÇALIŞIYOR, 4/4)
- **Çok-parça LID:** `_channel_lang.py` 6-11 segment örnekler (`SAMPLES`), MMS-LID oylar; kontaminasyon fix (returncode+unlink) diskte. **CANLI:** Azerice klip → 5 segment, `az` 0.999.
- **Model seçimi:** TR→large-v3-turbo (beam=1), yabancı→large-v3 (beam≥5, tespit dilinde), `ku`→ASR atla (dürüst).
- **Sonnet:** PDF özeti `_generate_ozet`→`prompts/ozet_film.txt` (85 satır tavizsiz kural), claude-sonnet-4-6.
- **Köprü:** `ku` → `_fetch_internet_ozet` (TMDB overview) → **AYNI `_generate_ozet` prompt'u** → PDF. ASR-fail değil, `ku` özelinde.

### Görev 6 — En önemli oyuncular (ÇALIŞIYOR)
- Sıralama gerçek kriter: KB yolunda IMDb `principals ORDER BY ordering` (billing), OCR yolunda VLM başrol sırası. Film→[:8], dizi→tüm kadro.
- İki kaynak: jenerik-OCR + bağımsız KB; kimlik teyitliyse (`verdict=TEYİT` veya `cast_ov≥2`) OCR cast KB otoriter listesiyle DEĞİŞTİRİLİR. **CANLI:** Barbarları klibi 3→8 isme genişledi (billing sırası).

### Görev 7 — IMDb/Wikipedia isim teyidi (ÇALIŞIYOR)
- Yerel duckDB: Wikidata (13M kişi, ~91k Q43-Türkiye) + IMDb (15M isim, 98M principals). `credit_crosscheck.name_match` TR-fold+ASCII+token eşleşme.
- Mekanizma: "yanlış ismi harf-harf düzelt" DEĞİL; **filmi tanı → kanonik kadroyu yerine koy**. **CANLI:** garbled `Bennu Yýldýrýmlar`→`Bennu Yıldırımlar`, yanlış yönetmen→ÇELİŞKİ+doğrusu sunuldu.
- **AÇIK:** Kimlik-bağımlı (film tanınmazsa düzeltme yok); IMDb-only eşleşme Türkçe harf kaybedebilir (Wikidata korur).

### Görev 8 — qwen final QC (BOZUKTU → DÜZELTİLDİ — bkz §5)
- **Doğru araç `scripts/_kunye_qwen_check.py`** (qwen2.5vl:7b vision, PNG). `qwen_kunye_probe/schema/batch` ise ORPHAN deney araçları (metin, qwen3:8b).
- Bağlanış: `mitas_pipeline.py:773-776` `_kqc.check(qc_png)` → verdict reasons'a → `:848` Hazır/Kontrol → klasör. Afiş+büyük-harf sinyalleri (kırılgan) Kontrol değil yalnız uyarı (iyi kalibrasyon).
- **CANLI:** gerçek PNG → qwen JSON verdict (`ozet_var:false`→Kontrol, doğru). 
- **KRİTİK (capstone yakaladı):** qwen_qc üretimde `mitas_pipeline.py` `import sys` eksiğinden NameError ile **HİÇ çalışmamış** (yalnız standalone test ediliyordu); F11 ile düzeltildi + canlı verdict doğrulandı (bkz. §5).

### Görev 9 — XML↔PDF karşılaştırma (KISMEN → DÜZELTİLDİ — bkz §5)
- **B-4 kapısı (üretimde aktif):** `mitas_pipeline.py:796-809` XML oyuncu ∩ PDF cast == 0 → "yanlış-film şüphesi" → Kontrol. Ek: KB verdict ÇELİŞKİ → Kontrol.
- **CANLI:** 300 Spartalı gerçek XML — doğru film flag yok, kasıtlı yanlış film flag FIRES.
- **AÇIK:** Daha zengin `credit_qc.xml_check()` (yönetmen + PDF damgası) ORPHAN — yalnız `credit_export.py` batch'inde, canlı pipeline'dan çağrılmıyor. Yönetmen-isim uyumsuzluğu tek-klip akışında otomatik yakalanmıyor (yalnız oyuncu kesişim).

### Görev 10 — UI / kuyruk / tek-yükleme / Tedial (ÇALIŞIYOR ×3)
- **Kuyruk (10a):** Gerçek UI kuyruğu = `asr_server` `_flow_queue_worker_loop` + `/api/flow-queue/*` (NOT `core/jobs/*` — o Dummy/test scaffold). Disk-kalıcı (`queue.json` + `job.json`), restart-survival. 37 route eşleşiyor, tsc EXIT 0. **CANLI:** running iş + done flow item gözlendi.
- **Tek-yükleme (10b):** Header (tek) + FlowQueue (çoklu) iki yol; `/api/asr/transcribe` & `/api/pipeline/run` → `mitas_pipeline` subprocess. **CANLI:** upload→kaydet→stored_media_path; boş gövde→400.
- **Tedial (10c):** b192610f fix (`session.py:162-180` start()→connecting) diskte; auto-login + JSESSIONIDVERSION rotation + tedial→pipeline zinciri tam. **CANLI:** 13 pytest pass, rotation canlı, 8765 401 (gate aktif).

### Görev 11 — Performans + bug (SORUN VAR; kritikleri düzeltildi)
- **Perf (ölçülü, büyüyen-DB'de doğrusal kötüleşir):**
  - P1 `/api/jobs?q` TÜM job.json okur (no-match 258ms@72job → prod ~1sn/tuş). **Flag (orta).**
  - P2 `system_events.read_events()` tüm jsonl okur, rotasyon yok (970KB→büyür). **Flag (orta).**
  - P3 `/version` 2 git subprocess/çağrı (~94ms). **DÜZELTİLDİ (F6 cache).**
- **Bug:**
  - B1 (D3 idempotency, en sinsi) flow-queue kilitsiz + `_write_json` atomik değil → worker bozuk-okumayla ölebilir/`done` geri sarılır. **Atomik yazma DÜZELTİLDİ (F7);** sunucu-tarafı kilit/409-reddi flag (orta).
  - B2 Popen kill sonrası communicate yok. **DÜZELTİLDİ (F8).**
  - B3 `xml_roles` istisna yutuyor (gerçek veride cp1254 bug'ı YOK — UTF-8 doğrulandı); bozuk XML'de sessiz kayıp → warn log öner (flag, düşük).
  - B4 flow-queue subprocess `/abort` ile öldürülemiyor. **Flag (orta).**
  - B5 3 pipeline yürütme yolu GPU'da paralel koşabilir → VRAM contention. **Flag (orta).**

### Görev 12 — Smoke (YEŞİL)
- pytest 474 pass / asr venv (10 "fail" yanlış-venv → ocr venv'de 50/50 pass, **F10 ile temizlendi**); manifest/benchmark-yaml/json-schema/tedial/translate/lid_validate/real_media hepsi PASS.
- **Tek gerçek defekt:** pyannote diarization import kırık (asr venv protobuf 3.19.6 ↔ opentelemetry). **Varsayılan `fast_with_fallback` özet profili diarize KULLANMAZ → üretim özetleri etkilenmez.** Düzeltme protobuf yükseltmesi gerektirir (pin riski) → trivial DEĞİL, flag.

---

## 4. AÇIK / ÖNERİLEN (trivial-olmayan, UYGULANMADI — Çağatay kararı)

1. **PDF başlık/özet yabancı-ASCII katlama** (G1) — kural harfiyen mi, taviz mi?
2. **pyannote/protobuf** çakışması (G12) — protobuf≥3.20 izole denenmeli (ctranslate2/tf pin riski).
3. **flow-queue kilit + GPU tek-semafor** (B1-kalan/B4/B5) — eşzamanlılık sağlamlaştırma.
4. **Perf P1/P2** — `/api/jobs?q` erken-kes + `system_events` tail/rotasyon (prod'da hissedilir).
5. **credit_qc orphan** (G9) — yönetmen-uyumsuzluğu + PDF damgası canlı pipeline'a bağlanmamış.
6. **Tedial bayat "Bağlı" rozeti** (G10c) — `_load_persisted` durumu düzgün çözüm: görüntü-durumu ile cookie-kullanılabilirliğini ayır (tek-satır yetmedi, test kırdı).
7. **8765 global Python310'da koşuyor** (memory'deki venvs\asr disiplini ihlali olabilir) — Çağatay kontrol etsin.
8. **Tedial UI tam künye(PDF) pipeline'ı tetiklemiyor** (yalnız ASR/OCR `/jobs/run`).
9. **Köprü dar** (`ku` özelinde) + TMDB başlık-eşleşme riski (kadro-teyit bağlı değil).

---

## 5. CAPSTONE — UÇTAN UCA KOŞU (Ahlat kısa klip) + KRİTİK BULGU

`mitas_pipeline.py --video AHLAT_AGACI_son4dk.mp4 --profile film_dizi` (API anahtarı enjekte) BUGÜN koştu (240sn, exit 0, profil=film). Zincir baştan sona çalıştı; **iki gerçek bug yalnız burada yüzeye çıktı** (bileşen testleri kaçırmıştı).

### ✅ Doğrulananlar (PDF AÇILIP GÖRÜLDÜ — `Database/AHLAT_AGACI_son4dk_4/pdf/kunye_onizleme.png`)
- **AFİŞ DOĞRU (F3 fix canlı):** Önizlemedeki afiş = **"THE WILD PEAR TREE"** (gerçek Ahlat Ağacı / tt6628102). Fix ÖNCESİ bu klip yanlış "AKM" afişi alıyordu. Düzeltme tam üretim pipeline'ında çalıştı.
- **Kadro/ekip doğru:** OYUNCULAR 8 isim billing sırası (DOĞU DEMİRKOL, MURAT CEMCİR…), Yönetmen **NURİ BİLGE CEYLAN**, Yapımcı **ZEYNEP OZBATUR ATAKAN** — yalnız Yönetmen+Yapımcı (v4). Büyük harf ✓, alt-başlık orijinal ad ✓, TÜR=DRAM ✓.
- **OCR çift-motor tam koşuda:** `engine=pipeline100+glm`, glm_used=true, glm_status=succeeded, 360 kare, 278 künye satırı, agree_count=24 (G2 sağlam, canlı).
- ⚠️ Bazı Türkçe adlar ASCII-katlanmış (ERGÜÇLÜ→ERGUCLU, ÖZBATUR→OZBATUR) — A5'in IMDb-vs-Wikidata yazım açığı (doğru kişiler, diakritik kaybı).

### 🔴 KRİTİK BULGU (capstone yakaladı, fix uygulandı+doğrulandı): `mitas_pipeline.py` `import sys` eksikti
- _DURUM.json: `"qwen_qc": {"error": "NameError: name 'sys' is not defined"}`.
- Kök sebep: `mitas_pipeline.py:776` (qwen_qc) ve `:806` (B-4 XML↔PDF cast kapısı) `sys.path.insert(...)` çağırıyor ama dosya `sys` import etmemişti → ikisi de `NameError` → `except` ile SESSİZCE yutuluyordu.
- Etki: **qwen final-QC (G8) wiring'inden (cd63c7c, 06-05) beri ÜRETİMDE HİÇ ÇALIŞMAMIŞ** — her koşuda hata, hiç verdict yok. **B-4 cast-kesişim kapısı (G9) AYNI sebeple XML'li kliplerde sessizce atlanıyordu.** Üç önceki denetim + A6/A12 ajanları kaçırdı (helper/standalone test ettiler, gerçek imported-path'i değil).
- **Fix (F11):** `import sys` eklendi. **Doğrulama:** `mp_has_sys=True`; aynı PNG'de qwen_qc artık gerçek verdict döndü (`ozet_var:false, yapimci_var:true, yonetmen_var:true, afis_var:true...`). B-4 kapısı da aynı mekanizmayla onarıldı.

### ASR=failed — kök sebep: klipte SES AKIŞI YOK
- ffprobe: `AHLAT_AGACI_son4dk.mp4` = SADECE video (h264), **ses akışı YOK**. ASR'ın ffmpeg ses çıkarımı (`_asr_16k.wav`) bu yüzden exit -22 ile patladı → ASR=failed → ANA DİL "—" → ÖZET placeholder → karar=Kontrol (DOĞRU sonuç).
- Bu KLİBE özgü (sessiz jenerik klibi); ASR pipeline'ı konuşmalı kliplerde A11 + real_media_smoke (3/3 TR) ile DOĞRULANDI. **Minör öneri (flag):** ses akışı yoksa ham `CalledProcessError` yerine ffprobe-ön-kontrol + temiz "ses yok" statüsü (zarif).

**Sonuç:** Capstone, e2e koşunun değerini kanıtladı — F3 (afiş) fix'ini canlı doğruladı VE bileşen testlerinin kaçırdığı kritik `import sys` bug'ını (G8+G9) yakalattı.

---
*Tüm düzeltmeler py_compile + hedefli canlı testle doğrulandı. Test artefaktları: `Database/AHLAT_AGACI_son4dk_4/` (künye PDF dahil) + `Mitas Output/Kontrol/AHLAT_AGACI_son4dk_4/`.*

---

## 6. TAKİP TURU (Çağatay onayı sonrası — 2026-06-07)

### 6.1 İsim Latinleştirme (ASCII sorunu) — DERİN ARAŞTIRMA + DÜZELTME (deterministik)
**Araştırma:** Wikipedia/IMDb verisi + DeepSeek/qwen/gemma karşılaştırıldı. Sonuç → **DATA-odaklı (deterministik) en iyi**: qwen3:8b/gemma yapısal-JSON çıktısı BOZUK (kullanılamaz); DeepSeek 10/10 ama sözleşmeyle-deterministik değil (künye kuralına aykırı). **IMDb `akas` kişi-adı tutmuyor (yalnız film başlığı) → Wikidata tek güvenilir Türkçe-yazım kaynağı.**

**Kök nedenler + uygulanan fix (`name_normalize.py`):**
1. Q43-only ülke filtresi → `{Q43, Q23681}` (KKTC dahil) — Hazar Ergüçlü Q23681'di, yabancı sanılıp ASCII oluyordu.
2. `ascii_fold` Türkçe `ı`'yı siliyordu (NFKD: "Tarık"→"TARK" ≠ DB "TARIK") → Türkçe-duyarlı fold (`_tr_fold_key`/`_sql_tr_fold`; `credit_crosscheck._sqlfold` deseni).
3. Gevşek fuzzy KALDIRILDI — isim TAMAMLAMA (Nuri Bilge→Ceylan, orta-token) içerik değişimi + 13M-satır LIKE (perf); tamamlama KB cross-check'in işi, kasa fonksiyonunun değil.

**Canlı test (deterministik, model yok):** Hazar Ergüçlü→HAZAR ERGÜÇLÜ (ASCII OCR'dan bile diakritik kurtarıldı), Türk isimler korundu, yabancılar ASCII (**0 regresyon**), Özbatur Atakan güvenli ASCII (yanlış kişi YOK).

**Açık (flag):** özet PROZASINDA yabancı isim (François→FRANÇOİS) — ç/ö/ü Türkçe ile paylaşıldığı için karakter-düzeyi ayrım imkânsız → DOKUNULMADI. Çözüm yolu: özete ham yabancı yerine zaten-normalize cast/crew formunu enjekte (özet-üretimi dokunuşu, follow-up).

### 6.2 Diğer onaylı fixler
- **Startup-reconcile** (`asr_server.py`): başlangıçta diskteki queued/running TEKİL işler → `interrupted` (hayalet "%92 running" biter; 2 gerçek hayalet vardı: asr-c53209523a4c, asr-5fa4474e2e63). `interrupted` first-class statü + frontend uyarlaması (asr-api.ts / JobLogWorkspace / Header).
- **Perf P2** (`system_events.py`): `read_events` artık tail-okuma (tüm dosyayı parse etmiyor) — byte-identik oracle testi geçti.
- **Perf P1**: zaten optimizeymiş (early-cut `break` mevcut, commit 5c394c99); no-match araması doğası gereği tam-tarama (index kapsam dışı). A13 burada kısmen yanılmış.
- **#5 (8765 global Python)**: `start_mitas.ps1` restart ile venvs\asr'ye taşındı — **ÇÖZÜLDÜ**.

### 6.3 Açık kalan (Çağatay kararı bekliyor)
- **pyannote/protobuf**: TF2.11 (`protobuf<3.20`) ↔ pyannote4/opentelemetry (`≥3.20`) çatışması; varsayılan özet profilini ETKİLEMEZ → ayrı venv veya TF-upgrade (büyük karar).
- **flow-queue sunucu-kilit + GPU tek-semafor** (eşzamanlılık sağlamlaştırma).
- **özet-proza yabancı-ASCII** (6.1 flag).
- **DeepSeek+cache hibrit (C)**: istenirse opsiyonel flag arkasında, yalnız DB-miss isimler için (determinizm cache ile korunur).
