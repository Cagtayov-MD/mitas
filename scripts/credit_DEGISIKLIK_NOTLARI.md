# Künye Sistemi — Değişiklik Notları & Yeniden-Doğrulama (re-verify)
_Çağatay: "eklediğin/yaptığın şeyleri not alalım, ileride doğruluğunu tekrar kontrol edebilelim."_

Her satır: NE eklendi + NASIL yeniden doğrulanır (smoke). Bağımsız çalıştırılabilir. GPU gereken testler için akış worker'ını önce durdur.

## A. Okuma çekirdeği
| Değişiklik | Dosya / commit | Yeniden-doğrulama |
|---|---|---|
| Video baş+son + gemma4:26b+qwen2.5vl:7b ensemble + KB | `credit_video_read.py` / 439f7067, 2e255887 | `venvs/ocr/Scripts/python.exe scripts/credit_video_read.py --film-dir <tester/film>` → YÖNETMEN/YAPIMCI/OYUNCULAR+güven |
| production kare globu (g_/c_) | credit_video_read.py / ebf3f286 | `python -c "import credit_video_read as cv; print(len(cv.list_frames(r'Database/3/frames/giris')))"` → >0 |
| prompt-echo filtresi (_is_junk) | credit_video_read.py / ebf3f286 | `cv.split_names('X, <Producer, Yapımcı, ... yanındaki isim')` → ['X'] |
| placeholder (<NAME>/<yok>) → okunamadı | credit_video_read.py / bf470d65 | `cv.is_abstain('<NAME>')` → True |

## B. Çok-dilli rol lexicon + QC
| Değişiklik | Dosya / commit | Yeniden-doğrulama |
|---|---|---|
| Çok-dilli deterministik rol çapalama | `credit_role_lexicon.py` / 4f01a458 | `python scripts/credit_role_lexicon.py` → 5 dil doğru, alt-roller elenir |
| Teslimat QC (deterministik + qwen-VL) | `credit_qc.py` / 6ec320eb | `python scripts/credit_qc.py` → hazir/kontrol + _kontrol_kayit.xlsx + sebep dağılımı |
| XML yönetmen+oyuncu isim eşleşmesi + PDF damga | credit_qc.py / b1977259, f39e940c | XML'i olan clip'te `XML_YON_UYUMSUZ` → dağıtım kopyası PDF'ine "(!) XML" damgası |

## C. Pipeline entegrasyonu (flag MITAS_USE_VIDEO_CREDITS)
| Değişiklik | Dosya / commit | Yeniden-doğrulama |
|---|---|---|
| subprocess runner | `_pipe_credit_video.py` / ebf3f286 | `venvs/ocr/.../python.exe scripts/_pipe_credit_video.py --giris <d> --cikis <d>` → tek-satır JSON |
| _pipe_pdf --video-credits AUGMENT | `_pipe_pdf.py` / bc97d44a | `--video-credits '{"yonetmen":["ZZTEST"],...}'` → çıktıda ZZTEST; arg'sız → birebir eski |
| mitas_pipeline flag + video bloğu | `mitas_pipeline.py` / dbee3453 | flag-ON: `_DURUM.timings_sec.video_kunye` var + `credit_video_completed` olayı; flag-OFF: yok |

**ENTEGRASYON DOĞRULAMASI (4-adım smoke, hepsi geçti):** (1) list_frames 120+240 kare; (2) runner temiz JSON; (3) _pipe_pdf WITH→ZZTEST eklendi/WITHOUT→regresyon temiz; (4) flag-ON uçtan-uca video_kunye=59s+olay+Hazır, flag-OFF regresyon temiz, py_compile OK.

## D. Akış / klasör / süre
| Değişiklik | Yer | Yeniden-doğrulama |
|---|---|---|
| teslimat klasörleri | `teslimat/{export,hazir,kontrol}` | mevcut |
| süre raporu | `pipeline_timing.py` | `python scripts/pipeline_timing.py` → klip başına dk + ort/min/max |
| **teslim akışı** (export→qwen→hazır/kontrol) | `credit_export.py` | `python scripts/credit_export.py [--crosscheck] [--visual]` → teslimat/export + hazır/kontrol + Excel. Smoke: 5 clip → export 5, hazır 2/kontrol 3 |
| çöp/kısa başlık koruması (cross-check) | credit_qc.py crosscheck_check (≥4 harf) | title="3" → cross-check atlanır (yanlış-eşleşme önlenir) |

## E. Idea 2 — otonom çapraz-kontrol (Wikidata + IMDb, birinci-sınıf)
| Değişiklik | Dosya | Yeniden-doğrulama |
|---|---|---|
| Çapraz-kontrol modülü (Wikidata mitas.duckdb + IMDb imdb.duckdb) — kimlik Türkçe-başlık-önce, otoriter yön/cast, TEYİT/ÇELİŞKİ/KAYNAK_YOK, **düzeltmez raporlar** | `credit_crosscheck.py` | `python scripts/credit_crosscheck.py --baslik "AHLAT AĞACI" --yonetmen "Nuri Bilge Ceylan" --yil 2018` → TEYİT |
| Klasik gold testi | `credit_crosscheck_goldtest.py` | `python scripts/credit_crosscheck_goldtest.py` → **16/16** (14 TEYİT + 2 ÇELİŞKİ yakalama) |
| Türkçe-fold (ı→i, ğ→g…) — title-only eşleşme (İ/ı tuzağı) | credit_crosscheck.py `_tfold/_sqlfold` | "AHLAT AĞACI" (sadece Türkçe başlık) → film bulunur (öncesi: original gerekiyordu) |
| **QC'ye flag'li bağlandı** | `credit_qc.py` (`--crosscheck` / `MITAS_USE_CROSSCHECK`) | `--crosscheck` ile ÇELİŞKİ → `CROSSCHECK_CELISKI` flag + PDF damga + kontrol. Flag KAPALI (vars.)=sıfır etki (kb=None). Birim: Murat Cemir/AHLAT→flag, NBC→yok |

**Kaynaklar (kalıcı/birinci-sınıf):** Wikidata `works_master` (label_tr/director/cast_member/imdb_id) + `qid_labels` (Türkçe isim); IMDb `titles/akas/crew/principals/names`. Kimlik = Türkçe başlık (katalog no DEĞİL — Yabandan→Sergio Leone kanıtı). 300 gibi kısa başlıkta **exact-first** retrieval. Çelişki yakalama: Murat Cemir / Jean-Louis Godfroy → ÇELİŞKİ.

## F. Tek-film v4 künye (elle koşma araçları) — 2026-06-04
| Değişiklik | Dosya | Yeniden-doğrulama |
|---|---|---|
| Tek film cross-check + yapımcı + TÜR + afiş (venvs/ocr) | `credit_kb_lookup.py` | `venvs/ocr/.../python.exe scripts/credit_kb_lookup.py --baslik "YABANCI MUHABİR" --orijinal "Foreign Correspondent" --yil 1940 --yonetmen "Alfred Hitchcock" --cast "Joel McCrea,..."` → JSON: verdict=TEYİT, yapimci=["Walter Wanger"], tur="Aksiyon / Dram", cast_ortusme=8 |
| Tek film v4 PDF render (GLOBAL python, reportlab) | `_v4_render_one.py` | `python scripts/_v4_render_one.py --json scripts/_v4_ornek_yabanci.json --out test.pdf` → efekt elenir [TR,TR], TÜR var/KARE yok, özet 50 kel BÜYÜK, crew=sadece Yön+Yap, afiş, cast≤8 |
| Dolu örnek/template | `_v4_ornek_yabanci.json` | kopyala-düzenle; özet final BÜYÜK HARF (yabancı ad I'lı: FISHER) |

**KANIT (2026-06-04, tek film, master KULLANILMADAN):** YABANCI MUHABİR (1940-0034, _102_master'da YOK) sıfırdan işlendi → ESKİ OCR-only "ALFRED NOWS/yapımcı yok/çöp cast" → GÜNCEL "ALFRED HITCHCOCK + WALTER WANGER + 8 gerçek oyuncu + v4 format + afiş". Video-okuma 70sn (mutabakat YÜKSEK), cross-check TEYİT. Çıktı: `Mitas Output\GUNCEL_ORNEK\1940-0034 YABANCI MUHABIR (v4 guncel).pdf`.
**EN AZ FİLM = 1** (batch/eğitim gerekmez; KB dış+hazır, modeller önceden eğitilmiş; _102_* sadece toplu-render kolaylığı).
**HÂLÂ AÇIK ENTEGRASYON:** v4 render canlı pipeline'a (mitas_pipeline→_pipe_pdf→_make_pdf) bağlı değil; bu araçlar elle-zincir. Canlı pipeline flag'lerle (MITAS_USE_VIDEO_CREDITS+CROSSCHECK) temiz VERİ üretir ama pre-v4 FORMAT (KARE/efekt/küçük-harf özet/afişsiz).

## G. CANLI PIPELINE'A v4 BAĞLAMA + bug fix'ler — 2026-06-04 (§F'deki "açık entegrasyon" KAPANDI)
"Başlat / Tedial / kuyruk → tek huni `mitas_pipeline.py` → v4". UI tetikleme zaten bağlıydı; v4 oraya eklendi.
| Değişiklik | Dosya | Yeniden-doğrulama |
|---|---|---|
| video-okuma film/dizi'de VARSAYILAN AÇIK (opt-out `MITAS_NO_VIDEO_CREDITS=1`) | `mitas_pipeline.py` | flag set etmeden film/dizi koş → `_DURUM.timings_sec.video_kunye` var |
| PDF sonrası **v4-final bloğu**: `tek_film_kunye.py` çağırır → `kunye.pdf`'i v4'e çevirir (GÜVENLİ: kunye_v4.pdf'e yaz, başarırsa replace; hata→eski PDF kalır) | `mitas_pipeline.py` | tam koşu → `timings.v4_final` var + kunye.pdf'te TÜR (KARE yok) |
| **TEK KOMUT uçtan uca:** video-okuma→cross-check(yapımcı/yön-dolgu/TÜR/afiş)→özet kısalt→v4 render | `tek_film_kunye.py` (GLOBAL py; venvs/ocr alt-süreç) | `python scripts/tek_film_kunye.py --clip <klip> [--original .. --year ..]` |
| **imdb_find TÜRKÇE-FOLD** (büyük fix): düz ILIKE ı/İ yüzünden yabancı filmi TR adıyla bulamıyordu | `credit_crosscheck.py` | `credit_kb_lookup --baslik "BARBARLARI BEKLERKEN"` (orijinal-adsız) → Ciro Guerra/tt6149154; gold **16/16** korunur |
| **Yönetmen ÇELİŞKİ-düzeltme** (bug fix): kareden okunan yön. otoriteyle çelişir+kimlik cast'le doğruysa → otoriteyi kullan (boşsa doldur, doğruysa koru) | `tek_film_kunye.py` | video-credits yon=["Chris Menges"] besle → çıktı **CIRO GUERRA** (düzeltildi) |
| cast: kimlik doğruysa teyitli otoriter liste; özet kurulum+SON cümle (spoiler) ≤64 kel BÜYÜK | `tek_film_kunye.py` | çıktıda cast temiz + özet sonu spoiler'lı |

**DOĞRULANANLAR (2026-06-04):** UI tetikleme `webui startPipelineJob → /api/pipeline/run`; Tedial `router.py:508 /assets/{id}/pipeline → /api/pipeline/run`; kuyruk `_pipeline_executor max_workers=1` (SIRAYLA). Tam koşu _5: coz6/ocr159/asr192/video_kunye64/pdf69/**v4_final51**/toplam **382sn (~6.4dk)**, karar Hazır.
**TUZAKLAR:** (1) bash Türkçe-İ/boşluk yol mangleme → pipeline'ı Python glob ile çağır (`glob.glob(...BARBARLARI...)`), bash path verme. (2) _generate_ozet ANTHROPIC_API_KEY ister; launcher'da yoksa özet placeholder (gerçek asr_server'da var). (3) IMDb akas Türkçe başlık içerir AMA ı/İ fold şart; Wikidata bu filmde boştu → IMDb-fold kurtardı. (4) "Waiting for the Barbarians" orijinaliyle aranınca tt2299505=2012 belgesel (YANLIŞ); TR başlık tt6149154 (doğru) → TR başlık daha kesin.
**HÂLÂ AÇIK:** kunye_teslim.md v4'e SENKRON DEĞİL (PDF v4, md hâlâ OCR ekibi) → credit_qc bayat md okur; senkron eklenecek. Yabancı-ad özette i→İ (MAGİSTRATE) kozmetik.

## H. WEBUI/SERVER gece-hazırlık (2026-06-04 akşam) — 53-film gece koşusu öncesi
| Değişiklik | Dosya | Yeniden-doğrulama |
|---|---|---|
| **Başlık İ/Ğ/Ş korunur** (upload sanitize bug'ı) | `core/api/asr_server.py` `_safe_filename` (regex'e Türkçe harf+apostrof eklendi) | "BİR_DAHA_DENEYELİM" → başlık "BİR DAHA DENEYELİM" (eski: "B R DAHA DENEYEL M"). **asr_server RESTART şart** (`scripts/start_mitas.ps1`) |
| **Zorla Durdur = sunucu pipeline'ı AĞAÇ-öldür** | asr_server `_pipeline_proc`/`_pipeline_abort` + `_run_pipeline_job` Popen + `POST /api/pipeline/abort` (taskkill /T /F); frontend `requestForceStop` | taskkill /T /F testi: parent+child öldü ✓ |
| **Log sekmesi** (canlı sistem olayları) | webui `LogPanel.tsx` + Header/Sidebar/AnalysisWorkspace (`panelMode 'log'`); backend `/api/events`+`outputs/system_events.jsonl` zaten vardı | Modüller/Akış yanında "Log"; 1.5sn poll |
| **Varsayılan profil stt→film_dizi** | webui FlowQueuePanel (useState + restore) | yeni öğe film_dizi → pipeline+künye (eski stt=ASR-only=künyesiz tuzağı) |
| **Kuyruk SUNUCU-tarafı (tarayıcıdan bağımsız)** | webui FlowQueuePanel: Başlat→`/api/flow-queue/run`, Durdur→`/stop`, Zorla→`/stop`+`/abort`, `pollServerQueue` (mount'ta worker'a yeniden bağlanır); client-loop ölü kod silindi | koşu başlat → **F5 → DURMAZ** (worker sunucuda) |
| **Gece QC/takip** | `scripts/gece_qc.py` (det: başlık-İ/yön/yapımcı/cast/özet/TÜR/afiş/SES + `--visual` gemma görsel) | `python scripts/gece_qc.py --visual --since 2026-06-04` → `outputs/gece_rapor.md` |

**KRİTİK dersler:** (1) webui kuyruğu eskiden TARAYICI-güdümlüydü → yenileme/kapatma durduruyordu (artık sunucu-tarafı, F5-korumalı). (2) stt-default ASR-only künyesiz üretiyordu (artık film_dizi default). (3) Başlık İ kaybı UPLOAD sanitize'ındaydı (parse değil). **webui type-check 0 hata.** Bu değişiklikler RESTART/HMR gerektirdi: asr_server `start_mitas.ps1` ile (key auto-yüklenir), webui Vite HMR.
**HÂLÂ AÇIK (sabah/sonra):** IMDb'de Türkçe-adıyla-olmayan yabancı film → TÜR boş + **dublaj-cast karışması** (Türkçe seslendirme oyuncuları cast'e karışır) → dub-ayırma + orijinal-ad-getirme = bekleyen büyük iş.

## Bilinen sınırlar / tunable
- cast augment OCR-önce (video cast OCR 8 doluysa eleniyor) — video-önce yapılabilir.
- mutabakat bile nadir yanılır (içerik nihai hakem; katalog/XML ~%90).
- QC `--visual` (qwen-VL) GPU testi bekliyor.
- Otonom XML/IMDb çapraz-kontrol (Idea 2) bekliyor.
