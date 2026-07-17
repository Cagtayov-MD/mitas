# MITAS Sistem Sağlık Denetimi (2026-06-28)

# Yönetici Özeti

MITAS boru hattı çekirdek mantığı (ASR transkripsiyon, OCR künye-okuma, jenerik tespiti, master-PNG derleme, özet motoru, orkestrasyon) **statik olarak sağlam ve fail-safe örülmüştür**; tüm 327 üretim modülü temiz derlenir, doğru venv ile 623 test toplanır ve doğruluğu bozan bir çekirdek mantık hatası bulunmamıştır. Genel hüküm: **DİKKAT** — sistem üretimde çalışır durumda ancak iki sistemik tema kalite güvencesini ve teslim güvenilirliğini risk altına atıyor. SALT-OKUNUR denetim sonucu hiçbir değişiklik veya commit yapılmamıştır.

En kritik 5 madde:

1. **Config-drift (sistemik kök-tema):** `_PROD_DEFAULTS` (kod) ile `start_mitas.ps1` (shell) "ayna" setleri senkron değil. CAST-etkileyen 3 flag (CAST_CAP 10 vs 8, CAST_OCR_KEEP, QC_NONCAST_FILTER) üretimde AÇIK ama kod-default KAPALI; kod yorumu yanlışlıkla "üretimde de kapalı" diyor. Aynı film, nasıl başlatıldığına göre **farklı oyuncu listesi** üretir → A/B kıyasları ve regresyon ölçümleri güvenilmez.
2. **`rerender_pdf_only.py` üretim flag setini uygulamıyor:** yalnız `MITAS_QC_BLOCK=1` set edip `tek_film_kunye.py`'yi çağırıyor; QC2 ve OTORİTE_ROUTE KAPALI kalıyor → "bugünkü pipeline mantığıyla yeniden üret" iddiasına rağmen daha bozuk künye/PDF teslim riski.
3. **Flow-queue worker exit-kodunu yutuyor (false-success):** `asr_server.py:751` yalnız `result is None` kontrol ediyor, `proc.returncode`'a bakmıyor (kardeş `_run_pipeline_job:1544` doğru yapıyor). Pipeline JSON bastıktan sonra non-zero çökerse iş SESSİZCE "done" işaretlenir → 100-film batch'te bozuk teslimler görünmez.
4. **Deferans koruması kısmen baypas:** üretimde CANLI olan `credit_qc_block`, `MITAS_CREDIT_DEFERENCE` flag'ini hiç tanımıyor ve KB-fill ettiği yönetmen/yapımcı değerleri `tek_film_kunye`'nin deferansla boş bıraktığı alanları nihai PDF'te eziyor → 2f4a2b53 commit'inin yasakladığı KB-doldurma deferans-açıkken bile gerçekleşiyor.
5. **no-copy-source medya 403:** flow-queue işleri (baskın üretim yolu) `--no-copy-source` ile koşuyor; UI medya önizleme/oynatma çağrısı `clip_dir` dışı kaynağa 403 dönüyor → çoğu üretim işinde UI medya akışı bozuk.

## Alt-sistem Sağlık Tablosu

| Alt-sistem | Durum | Özet | Bulgu sayısı |
|---|---|---|---|
| Jenerik başlangıç tespiti | dikkat | Çekirdek tespit sağlam; iki detektör arası Fix-E sapması (A/B yanıltır) + OCR-kelime-eşiği recall riski | 7 |
| Künye/OCR okuma + ayıklama | dikkat | 6-katmanlı çöp/garble savunması sağlam; risk konfigürasyonda (VL-model sapması, romanizasyon guard delinmesi) | 4 |
| Künye → PDF + deferans | dikkat | Deferans inline dallarda doğru; CANLI qc_block KB-fill ile baypas oluyor | 4 |
| Master-PNG (slit-scan/mozaik) | dikkat | Slit/mozaik bütünlük-güvenli; yön-körlüğü (ters roll smear) + min_hold kart kaybı | 6 |
| Özet motoru | dikkat | gemini→Sonnet→gemma zinciri sağlam; bayat dok./log atıfları, ölü DeepSeek yolu, UI ayrı zincir | 5 |
| ASR HTTP API sunucusu | dikkat | Çekirdek sağlam; returncode-yutma, timeout process-ağacı sızıntısı, no-copy 403 | 6 |
| ASR çekirdek boru hattı | dikkat | LID/VAD/transcribe sağlam; log karışması, çekirdek↔lean VAD sapması (A/B yanıltır) | 6 |
| Boru hattı orkestrasyonu | dikkat | Try/except fail-safe; _PROD_DEFAULTS↔ps1 senkron değil, OCR/ASR Popen korumasız | 5 |
| Config-drift (çapraz-kesen) | dikkat | Üretim config-to-code katmanı sağlam ama iki ayna sapıyor; rerender flag-set atlıyor | 5 |
| Web arayüzü (UI) | dikkat | tsc temiz; ölü-bagaj (~15 npm + shadcn iskele) + kapalı-tel canlı-STT | 5 |
| Bütünlük + test + verimlilik | dikkat | 327+96 modül temiz derleniyor, 623 test; returncode-yutma + CAST config-drift | 5 |

## Doğrulanmış Bulgular

### Flow-queue worker returncode YUTUYOR — false-success / sessiz başarısızlık
**Severity:** high | **Kategori:** bug | **Konum:** core/api/asr_server.py:751 (vs 1544) | **Etki:** mitas_pipeline final JSON satırını bastıktan SONRA non-zero çıkarsa (downstream/cleanup hatası, çocuk-süreç patlaması) toplu (flow) iş SESSİZCE "done"/"partial" işaretlenir; kullanıcı bozuk/eksik teslimi "tamamlandı" sanar, 100-film batch'te kaçaklar görünmez. **Önerilen düzeltme:** Flow-worker'ı tek-upload yoluyla eşitle: `if proc.returncode != 0 or result is None:`. Daha iyisi iki ~30-satırlık tekrar bloğunu (705-755 ve 1507-1546) tek yardımcı fonksiyona çıkar.
> Flow-worker: `if result is None: ... raise RuntimeError(tail)` — `proc.returncode` HİÇ kontrol edilmiyor (720-808 arasında yok). Kardeş `_run_pipeline_job`: `if proc.returncode != 0 or result is None:` (1544).

*(Not: ASR_SERVER-1 ve HEALTH_INTEGRITY-1 aynı kök-bulgudur — tek high-severity sorun olarak birleştirilmiştir.)*

### _PROD_DEFAULTS ↔ start_mitas.ps1 aynası kırık: CAST/dedup flag'leri üretimde AÇIK, bare-CLI'da KAPALI/farklı
**Severity:** high | **Kategori:** config-drift | **Konum:** scripts/mitas_pipeline.py:1250-1283 (vs start_mitas.ps1:50,79,81,83) | **Etki:** start_mitas.ps1 ile başlatılan üretim cast'i cap=10 + OCR-keep + noncast-filtre ile üretir; bare `python mitas_pipeline.py` ise cap=8 + filtreler KAPALI üretir (asr_server pipeline'ı doğrudan `subprocess.Popen` ile spawn ediyor, ps1 seed'i yok). Aynı filme iki koşu FARKLI oyuncu listesi verir → A/B kıyasları ve regresyon ölçümü güvenilmez. **Önerilen düzeltme:** 4 eksik flag'i (`MITAS_FRAME_DEDUP`, `MITAS_CAST_OCR_KEEP`, `MITAS_CAST_CAP=10`, `MITAS_QC_NONCAST_FILTER`) _PROD_DEFAULTS'a ekle (veya ps1'den kaldır) ve `MITAS_PDF_RENDER_AUDIT`'i ps1'e ekle; 1250-1252 yorumunu gerçekle hizala. Sağlamı: ps1 flag bloklarını _PROD_DEFAULTS'tan üret (tek kaynak) ya da CI testi iki seti diff'leyip drift'te kırsın.
> mitas_pipeline.py:1250 yorumu: "CAST_OCR_KEEP/QC_NONCAST_FILTER/CAST_CAP BİLEREK YOK: üretimde de kapalı" — AMA ps1:79 `MITAS_CAST_OCR_KEEP=1`, :81 `MITAS_CAST_CAP=10`, :83 `MITAS_QC_NONCAST_FILTER=1` (hepsi AÇIK). Kod-default: CAST_CAP=8, diğerleri OFF. Yorum bayat/yanlış.

*(Not: ORCHESTRATION-1, CONFIG_DRIFT-1 ve HEALTH_INTEGRITY-2 aynı kök-bulgudur — tek high-severity sorun olarak birleştirilmiştir.)*

### rerender_pdf_only.py üretim flag setini uygulamadan tek_film_kunye'yi çağırıyor
**Severity:** high | **Kategori:** config-drift | **Konum:** scripts/rerender_pdf_only.py:213-219 | **Etki:** rerender "künye PDF'ini BUGÜNKÜ pipeline mantığıyla yeniden üret" iddia ediyor ama yalnız `MITAS_QC_BLOCK=1` set edip `tek_film_kunye.py`'yi çağırıyor; `_apply_production_defaults()` yalnız `mitas_pipeline.main()`'de çağrılıyor, rerender onu import etmiyor. Sonuç: MITAS_QC2 (KAPALI), MITAS_QC_OTORITE_ROUTE (KAPALI), C-serisi cast flag'leri üretim-OFF değerlerinde kalır → ps1 ile seed edilmemiş shell'de daha bozuk künye kararı/PDF üretir, sessizce yanlış teslim. **Önerilen düzeltme:** rerender'da subprocess env'ine tüm _PROD_DEFAULTS'u uygula (env.setdefault döngüsü ya da `_apply_production_defaults()`'u env-doldurucu olarak yeniden kullanılabilir kıl); en azından MITAS_QC2 ve QC_OTORITE_ROUTE'u QC_BLOCK ile birlikte set et.
> :213 `env = dict(os.environ)`; :214 `env['MITAS_QC_BLOCK']='1'`; :219 `subprocess.run(cmd, ..., env=env)`. tek_film_kunye.py'de setdefault/_PROD_DEFAULTS YOK; QC2 default-OFF, OTORITE_ROUTE default-OFF.

*(Düzeltme: doğrulamada MITAS_CAST_CAP'in _PROD_DEFAULTS'ta olmadığı, credit_qc_block default'unun zaten 8 olduğu saptandı; çekirdek sorun QC2+OTORITE_ROUTE KAPALI kalması — high korunur.)*

### credit_qc_block KB-fill, deferanslı yönetmen/yapımcı alanlarını üretimde eziyor (deferans baypas)
**Severity:** high | **Kategori:** bug | **Konum:** scripts/credit_qc_block.py:662,746-761 + scripts/tek_film_kunye.py:679-681 | **Etki:** Üretimde `MITAS_QC_BLOCK=1` CANLI. Kimlik kilitli (verdict=TEYİT veya cast_ov≥2) filmlerde OCR yönetmen/yapımcı boşsa qc_block KB'den isim doldurup nihai PDF'e yazar; `tek_film_kunye.py:679-681` qc_block çıktısını koşulsuz otorite alıyor (deferans kontrolü YOK). 2f4a2b53 commit'inin yasakladığı KB/web-doldurma deferans-açıkken bile gerçekleşir → deferans koruması üretimde kısmen etkisiz. **Önerilen düzeltme:** credit_qc_block.qc_credit_block içine `MITAS_CREDIT_DEFERENCE` kapısı ekle (deferans açıkken yönetmen KB-fill :662, cast floor-fill :715-730, yapımcı KB-tamamla :746-761 yapılmasın; yalnız yazım-düzeltme/garble-eleme korunsun). Alt.: tek_film_kunye.py:679-681'de deferans açıkken qc_block KB-fill izlerini arındır.
> credit_qc_block.py'de `MITAS_CREDIT_DEFERENCE` SIFIR eşleşme. :662 `yon = [otoriter_yon[0]]` (KB-fill); :746-761 KB yapımcı ekleme. tek_film_kunye.py:679 `yon = list(_qcb_res.get('temiz_yon') or yon)` koşulsuz.

### no-copy-source işler /api/clips/{id}/media'da 403 döndürür (medya oynatılamaz)
**Severity:** medium | **Kategori:** bug | **Konum:** core/api/asr_server.py:3770 (ve 1748) | **Etki:** Pipeline/flow işleri `--no-copy-source` (713) ile koşar; kaynak orijinal ağ yolunda (W:\...) kalır, clip kaydının source_path'i clip_dir DIŞINDA. `_clip_source_media_path` `_is_path_under(media_path, clip_dir)` False → 403 `media_path_not_allowed`. no-copy-source flow-queue işlerinin tamamını (baskın üretim yolu) etkiler; UI oynatma+range/reprocess kaynak okuma kırılır (çıktı-üretim etkilenmez). **Önerilen düzeltme:** Medya servisinde clip kaydındaki doğrulanmış source_path'i ayrı bir whitelist olarak kabul et (yalnız o tam yola FileResponse) ya da medya için clip-dir dışı-kaynak desteğini açıkça ele al.
> `if not _is_path_under(media_path, clip_dir): raise HTTPException(status_code=403, ...)`. `_is_path_under` `relative_to` ile W:\... dışı yolda ValueError→403. no-copy-source `source_path=video` (W:\...) yazıyor (mitas_pipeline.py:1391-1399).

### Zaman-aşımı (4sa) yol-killeri process-AĞACINI öldürmüyor → VRAM sızıntısı
**Severity:** medium | **Kategori:** efficiency | **Konum:** core/api/asr_server.py:730 (ve 1525) | **Etki:** 4 saatlik cap dolunca mitas_pipeline ölür ama torunları (PY_OCR/PY_ASR/PY_PDF venv python'ları + ffmpeg) yetim kalıp RTX 3090 VRAM'ini tutmaya devam eder; `_gpu_lock` ile serileştirilen sonraki işler OOM yer. Tek-GPU mimaride sonuç ağır. **Önerilen düzeltme:** Timeout dalında da abort yolundaki `taskkill /PID <pid> /T /F` tree-kill desenini (856, 1473) kullan; ardından `proc.communicate()` ile pipe'ları kapat.
> TimeoutExpired: `proc.kill(); proc.communicate(); raise`. Windows'ta `proc.kill()` yalnız doğrudan çocuğu öldürür; Popen `creationflags` kullanmıyor (job object/process group yok).

### _pipe_pdf deferans, video_credits None olduğunda tümüyle atlanır → mekanik credit_parse çöpü PDF'e sızabilir
**Severity:** medium | **Kategori:** bug | **Konum:** scripts/_pipe_pdf.py:340 + scripts/mitas_pipeline.py:1850,2014,2052 | **Etki:** _pipe_credit_text çökerse/timeout olursa (VC_TIMEOUT=1800s) `last_json` None döner → `if USE_VIDEO_CREDITS and video_credits:` False → --video-credits geçilmez → _pipe_pdf deferans atlanır → credit_parse'ın "directed by/produced by" substring eşlemesiyle kazıdığı çöp yönetmen/yapımcı PDF'e girer. Kısmi telafi: V4 final (tek_film_kunye) kunye.pdf'i ezer; ama V4 final de çökerse (rc≠0 veya PDF<10KB) credit_parse PDF'i teslim edilir. **Önerilen düzeltme:** _pipe_pdf'te video_credits boşken de deferans-güvenli davran (credit_parse crew'ünden yönetmen/yapımcı'yı koşulsuz temizle) ya da mitas_pipeline'da last_json None'da boş bir video_credits dict geçirerek deferans kolunu tetikle.
> _pipe_pdf.py:340 `if args.video_credits:` — yalnız flag doluyken `_apply_video_credits_authoritative` çağrılır; "DEFERANS KURALI" fonksiyon İÇİNDE, None senaryosunda hiç ulaşılmıyor.

### VL-okuma model defaultları sapıyor: credit_video_read 2-model ensemble, üretim VL-fallback tek-model → fuse() mutabakat yolu üretimde ölü
**Severity:** medium | **Kategori:** config-drift | **Konum:** scripts/credit_video_read.py:52,309-312 + scripts/_pipe_credit_vl.py:39,169 | **Etki:** credit_video_read.py'yi default MODELS ile standalone test eden biri 2-model mutabakat davranışı görür (üretimde yok); fuse()'un "YÜKSEK (mutabakat)" kademesi üretim VL-fallback'inde erişilemez kod → testte yanlış güven, A/B'de farklı yönetmen kararları. **Önerilen düzeltme:** credit_video_read.MODELS default'unu üretimle hizala (tek-model) ya da fuse()'a tek-model-uyarısı ekle; mutabakat kademesinin üretimde aktif olmadığını docstring'e işle; A/B'de AYNI model setini kullan.
> credit_video_read.py:52 default `"gemma4:26b,qwen2.5vl:7b"` (2-model); _pipe_credit_vl.py:39 `VL_MODELS=["gemma4:26b"]` (tek), :169 tek model geçiyor → `sum(...)>=2` asla sağlanmaz.

### Latin-dışı LLM romanizasyon yolu anti-halüsinasyon guard'ını etkisizleştiriyor
**Severity:** medium | **Kategori:** quality | **Konum:** scripts/credit_text_read.py:1056-1074,364-384,406-418 | **Etki:** Arap/Kiril/Yunan künyede romanizasyon-LLM yanlış-isim ikame ederse (satır-sayısı korunsa bile) anti-halüsinasyon kalkanı yakalamaz — guard token'ları LLM-romanize satırlardan üretildiği için extraction-LLM'in uydurduğu isim guard'da da bulunur, kalkan delinir; yanlış kişi adı extraction'a geçebilir. Sınırlanma: nonlatin_source→credit_qc_block:811 RENDER/KONTROL route'u insan teyidine yollar; ama QC_BLOCK kapalıysa bu güvenlik ağı da düşer. **Önerilen düzeltme:** Romanizasyon-LLM çıktısını ham OCR'a karşı çapraz-doğrula (token-hizalama sapması zaten stderr'e yazılıyor → bunu nonlatin_source bayrağına bağla, her zaman KONTROL).
> :1057 `_rom=_romanize_lines_llm(...)` → :1059 `lines=_rom`; :1071 `guard_lines=list(lines)`; :1074 ocr_tokens LLM-romanize satırlardan. Docstring (:368-369) bunu açıkça kabul ediyor: "Romanizasyon halüsinasyonu içsel guard'larca SÜZÜLMEZ".

### slitscan() scroll yönünü yok sayar (abs(dy) + sabit pencere) → ters/aşağı roll'da smear/tekrar
**Severity:** medium | **Kategori:** bug | **Konum:** OCR-worktree/db_compose_master.py:441-445 | **Etki:** Krediler yukarı kayan normal roll'da doğru çalışır; ancak aşağı-kayan/ters roll'da yeni içerik slitin ÜSTÜNDE belirir, kod ise altından örnekler → zaten yakalanmış içeriği tekrar yapıştırır (smear/çift okuma) ve gerçek yeni içeriği kaçırır. **Önerilen düzeltme:** estimate_offsets'teki gibi domineren scroll işaretini çöz (satır 628-636); dy<0 (aşağı scroll) ise stripi `image[ref-velocity:ref]` olarak örnekle ya da domineren yönü tespit edip ters roll'da slit yerine mozaiğe yönlendir.
> :441 `velocity = int(round(abs(dy)))` — işaret atılıyor; :445 `strip = image[ref: ref + velocity, :]` — HER ZAMAN slit altından örneklenir. estimate_offsets sign çözüyor (631-636) ama slitscan'a hiç geçmiyor.

### Kısa-ömürlü kartlar split_runs min_hold süzgeci tarafından tamamen düşürülüyor (kart kaybı)
**Severity:** medium | **Kategori:** bug | **Konum:** OCR-worktree/db_compose_master.py:402-405 | **Etki:** Hızlı geçen/kısa gösterilen tek bir kredi kartı (3-4 kare) slit kanonik çıktıda tamamen kaybolur; içeriği `_sharpest_with_text`/`split_static_cards`'a hiç ulaşmaz. **Önerilen düzeltme:** min_hold süzgecini metinli kısa-run'lar için gevşet (has_text geçiyorsa min_hold=2) ya da kısa-S-run'ları tek-kart adayı olarak yine de `_sharpest_with_text` ile değerlendir.
> :402-405 `return [run for run in runs if run[2] != 'C' and (int(run[1]) - int(run[0]) + 1) >= p.min_hold]` (min_hold default 5). Metin-istisnası yok.

### Paylaşılan 'mitas.asr' logger'ına koşu-başı FileHandler ekleniyor — eşzamanlı koşularda log karışır
**Severity:** medium | **Kategori:** bug | **Konum:** core/pipelines/asr/pipeline.py:400-404 (ayrıca transcribe.py:30) | **Etki:** İki ASR işi paralel koşunca (belgelenen 2-paralel-iş + ~18.7GB VRAM senaryosu) her koşunun FileHandler'ı AYNI paylaşılan logger'a eklenir; A koşusunun fallback/stereo logları B'nin asr.log'una da yazılır. Transkript doğru kalır ama koşu-başı tanı/forensic logları çapraz-bulaşır, kök-neden takibi güvenilmez olur. **Önerilen düzeltme:** Koşuya özel benzersiz isimli child logger (`f"mitas.asr.{module_id}"`) kullan ve handler'ı ona ekle; ya da handler'a yalnız bu run_dir'e ait kayıtları geçiren filtre ekle. transcribe.py de aynı child logger'ı kullanmalı.
> `asr_logger = logging.getLogger("mitas.asr")` (singleton); :402-404 her çağrıda yeni FileHandler ekleniyor. transcribe.py:30 aynı modül-seviyeli logger.

### Çekirdek ASR hattı (vad_filter=False + harici silero) ile üretim 'lean' yolu (faster-whisper iç VAD) ayrı VAD stratejisi kullanıyor
**Severity:** medium | **Kategori:** config-drift | **Konum:** core/pipelines/asr/models.py:57 (vs scripts/_pipe_asr.py:204-208,280) | **Etki:** Üretimde özet-transkript çoğunlukla LEAN yoldan üretiliyor (run_asr_pipeline atlanıyor, _pipe_asr.py:298-301); çekirdek hattın VAD/chunk/fallback/safety kapılarının HİÇBİRİ bu çıktıya uygulanmaz. Çekirdek hat üstünde yapılan A/B veya kalite ölçümleri üretim lean çıktısını temsil etmez; aynı film iki yolda farklı segment sınırları verebilir. **Önerilen düzeltme:** Hangi yolun üretim-kanonik olduğu netleştirilip ölçümler o yol üzerinden yapılmalı; lean ile çekirdek hattın VAD/segmentasyon parametreleri (vad_filter, min_silence) bilinçle hizalanmalı ya da fark belgelenip A/B raporlarında etiketlenmeli.
> Çekirdek: `vad_filter=False` + `run_silero_vad` (transcribe.py:127). Lean: `vad_filter=(args.vad != "off")` + `min_silence_duration_ms=500` (--vad default "on").

### core.api.tedial __init__ 'dependency-light' iddia ediyor ama import-anında fastapi'yi zorunlu kılıyor
**Severity:** medium | **Kategori:** health | **Konum:** core/api/tedial/__init__.py:1-7 (docstring) vs 35 | **Etki:** Sadece TedialConfig isteyen tüketici bile fastapi'yi yüklemiş olmak zorunda; docstring'in söz verdiği hafif import yüzeyi ihlal. fastapi'siz ortamlarda (ocr venv) tüm tedial alt-paketi import-edilemez hale geliyor; testler yanlış venv'de yanıltıcı collection hatası veriyor. **Önerilen düzeltme:** `create_tedial_router` import'unu __init__'ten çıkar (lazy: çağrı-anında import) ya da docstring'i gerçek bağımlılık durumuyla güncelle.
> :35 `from core.api.tedial.router import create_tedial_router` → router.py:16 `from core.api.access import ...` → access.py:15 `from fastapi import ...`. router.py içi try/except lazy-guard etkisiz (fastapi zaten modül-seviyesinde import edilmiş).

### Canlı STT Preview runtime'da kalıcı kapalı — ölü-tel özellik
**Severity:** medium | **Kategori:** health | **Konum:** webui/src/app/App.tsx:1123 | **Etki:** `isSttPreviewEnabled={false}` sabit kodlanmış; AnalysisWorkspace.tsx:88 `isLivePreviewEnabled` her zaman false. `useLiveSttPreview` (live-stt-preview.ts ~627 satır WebSocket/AudioContext) `enabled:false` ile çağrılıyor; Sidebar/VideoPlayer'daki tüm koşullu dallar erişilemez. Geniş bir özellik production'da hiç çalışmıyor, bundle'da ama ölü. **Önerilen düzeltme:** Ya özelliği gerçek koşula bağla ya da `useLiveSttPreview` + live-stt-preview.ts + isSttPreviewEnabled dallarını kaldır/feature-flag arkasına al. Şu an "yarım bağlı", niyet belirsiz.
> App.tsx:1123 `isSttPreviewEnabled={false}` — hiçbir koşul/env/flag ile değiştirilemiyor. Kaynak kodunda `MITAS_STT_PREVIEW`/`STT_PREVIEW`/toggle yok.

### OneOCR detektörü Fix-E'yi SERT-AÇIK gömüyor; paddle'da aynı kural flag-gated default-OFF → A/B yanıltır
**Severity:** high | **Kategori:** config-drift | **Konum:** core/pipelines/ocr/jenerik_oneocr_detector.py:160 (vs jenerik_frame_pool_detector.py:565-570) | **Etki:** İki detektör AYNI find_onset/postprocess'i paylaşıp SADECE skoru farklı üretiyor; OneOCR iki-sütun+yüksek-semantic düzyazı-benzeri kareleri prose-cezasından muaf tutuyor, paddle (default config) tutmuyor. paddle↔OneOCR A/B karşılaştırması motor-swap ile davranış-değişimini birbirine karıştırır; OneOCR canlıya alınırsa paddle'ın valide edilmediği bir kredi-kabul davranışı sessizce devreye girer. **Önerilen düzeltme:** OneOCR'daki muafiyeti de aynı flag'e bağla (paddle ile birebir) ya da ayrı flag tanımla; en azından yorumu "paddle-default'tan SAPAR" diye işaretle. Karar verilene kadar A/B'de iki taraf da aynı Fix-E durumunda koşsun.
> OneOCR (koşulsuz): `if prose_like and not (features["two_column_layout"] and features["semantic_score"] >= 0.45): score *= 0.08`. Paddle: aynı koşul `_credit_prose_exempt_enabled() and ...` ile sarılı; `MITAS_JENERIK_PROSE_CREDIT_EXEMPT` DEFAULT OFF (başka hiçbir dosyada tanımlı değil).

### OCR/ASR alt-süreç Popen çağrıları try/except dışında — venv python yoksa pipeline _DURUM/KONTROL üretmeden çöker
**Severity:** medium | **Kategori:** bug | **Konum:** scripts/mitas_pipeline.py:1673 (OCR), 1710 (ASR) | **Etki:** PY_OCR (venvs/ocr/Scripts/python.exe) veya PY_ASR yok/taşınmışsa Popen FileNotFoundError fırlatır; yakalanmadığı için main() çöker. Film için _DURUM.json yazılmaz, KONTROL'e yönlenmez, routed_* olayı loglanmaz — sessiz yarım-çökme; diğer tüm bloklar fail-safe iken bu iki nokta modül sözleşmesini ihlal eder. **Önerilen düzeltme:** Popen çağrılarını try/except ile sar; başarısızlıkta ilgili modülü "failed" işaretle, reason ekle, proc=None bırakarak akışın KONTROL'e devam etmesini sağla (mevcut toplama blokları proc None'da zaten atlar).
> :1673 `ocr_proc = subprocess.Popen(...)` ve :1710 `asr_proc = subprocess.Popen(...)` — ikisi de toplama try/except'inden (1716, 1792) ÖNCE ve KORUMASIZ. Sözleşme (dosya başı 9-10): "Her blok try/except, modül failed işaretlenir, teslim KONTROL'e yönlenir".

### OCR-refine/gate kredi-satırı testi 6+ kelimeli gerçek kredi satırlarını düşürüyor (off-by-threshold recall riski)
**Severity:** medium | **Kategori:** bug | **Konum:** core/pipelines/ocr/jenerik_detector.py:606-608 (ayrıca 607 = HEALTH_INTEGRITY-5) | **Etki:** `is_credit_text_line` 6+ kelimeli satırları reddeder; "Director of Photography John Mathieson BSC" (6 kelime) → False, hatta docstring'in "tutuluyor" dediği örnek ("Written and directed by Blerta Basholli") bizzat 6 kelime → düşürülür (içsel tutarsızlık). `refine_start_ocr`/`refine_end_ocr` (OCR_GATE'e bağlı DEĞİL, ocr_read_fn sağlandığında her zaman çalışır) bu fonksiyona bağlı → 6+ kelimeli kredi kartı taşıyan boşluk-bölgesi köprülenemez, start/end yeterince yürümez (geç-başlama/erken-bitiş = krediyi kaçır). **Önerilen düzeltme:** Kelime-üst-sınırını yükselt (≥8) ya da kredi-rol anahtar kelimesi (director/photography/producer/yönetmen...) içeren satırları uzunluktan muaf tut; nokta-bitiş kuralı 'A.S.C.'/'B.S.C.' unvan-kısaltmalarını da vurabilir.
> :606-608 `w = t.split(); if len(w) >= 6 or t.rstrip().endswith("."): return False`.

*(Not: JENERIK-2 ve HEALTH_INTEGRITY-5 aynı bulgudur — birleştirilmiştir.)*

### _update_job / _append_job_log atomik-olmayan read-modify-write (lost-update yarışı)
**Severity:** low | **Kategori:** quality | **Konum:** core/api/asr_server.py:3858 | **Etki:** Aynı job'a eşzamanlı iki güncelleme tam-dict last-write-wins ile birbirini ezebilir (ör. status güncellemesi ile log/progress güncellemesi). Executor'lar tek-worker olduğu için pratik risk düşük; yine de durum/ilerleme bilgisi anlık kaybolabilir. **Önerilen düzeltme:** Tek bir _jobs_lock altında read-modify-write yap (in-memory `_jobs[job_id].update(updates)` + disk yazımı) ya da alan-bazlı merge ile tam-dict ezmesini önle.
> `_update_job`: `_load_job` (kilit al/bırak) → `job.update` → `_save_job` (kilit al/bırak); arada kilit YOK.

### Statik-koşu FP-kalkanı koyu-zeminli tek-kart kredileri 'altyazı/tabela' sanıp düşürebilir (CLIP yoksa)
**Severity:** medium | **Kategori:** quality | **Konum:** core/pipelines/ocr/jenerik_detector.py:453-456 | **Etki:** CLIP yüklenemeyen ortamda (open_clip/torch yok → med_clip=None) hareketsiz, az-bloblu ama GERÇEK statik kredi kartları (yönetmen kartı, "A FILM BY ...", kısa kapanış) RESCUE alamaz ve med_nblob<3 ise sessizce düşer; too_short kurtarması (462) ve recoverable (530) min_clip None'da tümüyle kapanır → CLIP'siz hiçbir kısa-kart kurtarılamaz/insan-denetimine işaretlenemez. **Önerilen düzeltme:** CLIP=None iken statik-kart kalkanını gevşet (dark_ratio yüksek + row_struct yeterliyse muaf) ya da near_miss ile insan-denetimine işaretlemeyi garanti et.
> :454-456 guard `med_nblob < STATIC_NBLOB_MIN (=3) and not (med_clip is not None and med_clip >= RUN_CLIP_RESCUE)`; CLIP yoksa rescue koşulu daima False → koşulsuz düşer.

### split_static_cards debounce'u (card_min_hold=5) kısa-tutulan distinct kartı önceki karta eritir
**Severity:** low | **Kategori:** quality | **Konum:** OCR-worktree/db_compose_master.py:318-327 | **Etki:** Statik-run içinde 5 kareden kısa gösterilen ayrı bir kart birleştirilip çıktıdan düşebilir; `_sharpest_with_text` yalnız tek (en keskin) kareyi seçtiğinden kısa kartın metni kaybolur. Belgelenmiş bilinçli debounce tradeoff'u ama kayıp-yönlü. **Önerilen düzeltme:** Eşik bilinçli; gerekirse kısa-distinct-layout için min_hold'u düşür ya da birleşmiş dilimde >1 distinct layout varsa ikinci kartın en-keskin karesini de blok olarak ekle.
> :318-327 `if persist >= min_hold: ... bounds.append(idx)`; aksi `k+=1` ile sessizce önceki karta erir.

### Master-PNG çoklu kırılganlık (scroll dedup muafiyeti, DEDUP_TDIFF kalibrasyon, estimate_offsets cut-komşusu)
**Severity:** low | **Kategori:** quality/config-drift | **Konum:** OCR-worktree/db_compose_master.py:491-507, 67-68, 637-639 | **Etki:** (MASTER_PNG-5) Scroll blokları seen_hi/seen_hashes setlerine eklenmediğinden aynı roll iki kez stack edilebilir; (MASTER_PNG-4) DEDUP_TDIFF=40 bit-sayısına (DEDUP_HI_SIZE) bağlı değil → HI_SIZE override edilirse veto ya hiç tetiklenmez ya hep tetiklenir (standalone CLI A/B yanıltır); (MASTER_PNG-7) medyan-smooth cut'ları sıfırladıktan SONRA uygulandığından cut-komşusu küçük gerçek offset sıfırlanabilir (sub-piksel yanlış-yerleşim). **Önerilen düzeltme:** Scroll bloklarının en-keskin dhash'ini seen_* setlerine ekle; DEDUP_TDIFF'i bit-oranına bağla (≈0.156·HI_SIZE²) ya da override'da uyar; medyanı cut'ları maskeleyerek uygula.

### dynamic_window: probe metni 'iki ardışık kare' şartı gerçek kredi sonunu erken kesebilir
**Severity:** low | **Kategori:** quality | **Konum:** core/pipelines/ocr/dynamic_window.py:249-253 | **Etki:** Kredi kuyruğunda kart-arası kısa siyah/boş kareler (fade) varsa boundary tam boşluğa denk gelince ikinci kare boş çıkar → pencere erken kapanır, sonraki gerçek kredi kartı pencere DIŞINDA kalır. step_sec=60s büyük olduğundan olasılık sınırlı ama mevcut. **Önerilen düzeltme:** İki-kare onayını 'her ikisi' yerine '≥1' + komşu doğrulama yap ya da boundary boşsa stride dahilinde küçük bir boşluk-toleransı taraması ekle.
> :249-253 `for probe_t in (t, t+stride): if not _probe_single_frame(...): return False` — ikisi de ≥1 OCR kaydı vermeli.

### ASR VAD-gap onarımı gap kenarlarında fast+quality çift segment üretebilir
**Severity:** low | **Kategori:** quality | **Konum:** core/pipelines/asr/transcribe.py:294,703-738,800-814 | **Etki:** `preserve_fast_selected_chunks=gap_repair_fallback` iken tüm fast korunur + quality eklenir; preroll=1.0s/postroll=0.5s genişletilmiş kenar bölgeler fast'in zaten kapsadığı yerlerdir, kanal-dışı yolda çapraz-dedup YOK → gap kenarındaki ≤1.5s bölgede aynı konuşma iki kez clean_segments'e girip transcript'te tekrarlı satır oluşabilir. Nadir (yalnız vad_gap_uncovered fallback). **Önerilen düzeltme:** Additive merge sonrası zaman-örtüşmeli (aynı dil, yüksek IoU+token-jaccard) segmentler için kanal-içi dedup ya da repair quality'yi yalnız gerçek gap aralığına kırparak ekle (preroll/postroll yalnız decode bağlamı).

### _valid_person_name iki tek-harf baş-harfli adları reddediyor (J K Simmons → sessiz isim kaybı)
**Severity:** low | **Kategori:** quality | **Konum:** scripts/credit_text_read.py:843-846 | **Etki:** İki baş-harfle yazılan oyuncu/yönetmen adları (J.K. Simmons, T.E. Lawrence) `_only_persons` son-süzgecinde sessizce düşer → cast/yön kaybı; docstring "orta-harf serbest" iddiasıyla çelişiyor. Gerçek-dünya sıklığı düşük (TRT arşivi çoğu Türkçe, tam ad). **Önerilen düzeltme:** real-token şartını gevşet: `len(real)>=2 OR (len(toks)>=2 ve son token len>=2)` gibi soyad-merkezli kural ya da ardışık tek-harf baş-harfleri tek "gerçek token" say.
> :843-845 `real=[t for t in toks if len(t)>=2]; if len(real)<2 ... return False`. "j k simmons" → real=['simmons'] → reddedilir.

### Live-preview WS bozuk JSON frame'inde komple çöküyor (yalnız WebSocketDisconnect yakalanıyor)
**Severity:** low | **Kategori:** bug | **Konum:** core/api/asr_server.py:2229/2319 | **Etki:** İstemci tek bir bozuk (binary/non-JSON) frame gönderirse `receive_json` JSONDecodeError fırlatır, yakalanmaz → handler çöker, soket 1011 ile kapanır; hazır `_send_live_error('bad_chunk')` yolu yerine oturum sessizce düşer. Robustluk/UX düşüşü, veri kaybı yok. **Önerilen düzeltme:** `receive_json`'u kendi try/except'ine al; JSONDecodeError'da `_send_live_error` ile uyar ve döngüye devam et.

### _write_json sabit '.tmp' eki → aynı yola eşzamanlı yazımlarda temp-dosya yarışı
**Severity:** low | **Kategori:** quality | **Konum:** core/api/asr_server.py:3971 | **Etki:** Temp adı hedef yola göre SABİT; aynı job.json'a eşzamanlı iki yazıcı (`_save_job` _jobs_lock dışında disk yazıyor) aynı .tmp'yi paylaşır → Windows'ta `os.replace` FileNotFoundError/PermissionError verebilir/kaydı kaybedebilir. queue.json korunaklı (_flow_worker_lock); job.json değil. **Önerilen düzeltme:** Temp adına benzersizlik ekle (`.{uuid4().hex}.tmp` ya da aynı dizinde `tempfile.mkstemp`).

### _ozet_deepseek + _deepseek import özet zincirinde hiç çağrılmıyor (ölü kod) + bayat docstring/log atıfları
**Severity:** low | **Kategori:** health/quality | **Konum:** scripts/mitas_pipeline.py:823,1042-1051,1086-1112 (ayrıca 1116,1953,1989,1994) | **Etki:** (OZET-1) `_ozet_deepseek` tanımlı + `_deepseek` her başlangıçta yüklenir ama zincirde sıfır referans → DeepSeek hiç denenmez, yetim yol/bakım yükü; (OZET-2) docstring "Gemini→Sonnet→DeepSeek" (gerçek: Gemini→Sonnet→gemma-local), log her zaman "Sonnet özeti üretildi" der (üretici gemini/gemma olsa bile) → telemetri/A-B yanıltır. **Önerilen düzeltme:** _ozet_deepseek'i ya zincire opt-in ekle ya kaldır; docstring'i gerçek zincire güncelle; log mesajına kazanan sağlayıcı adını (_ad) ekle, sabit "Sonnet" ifadesini kaldır.

### asr_server UI transkript-özeti ayrı/eski zincir: gemini, timestamp-strip ve BLOCK_NONE iyileştirmelerini almıyor
**Severity:** low | **Kategori:** config-drift | **Konum:** core/api/asr_server.py:3078-3099,3346-3353 | **Etki:** UI "içerik özeti" ucu (summarize_job_transcript) pipeline'daki gemini ucuz+sağlıklı motor, ham-CoT timestamp temizleme ve kurgu-güvenlik blok-aşımı iyileştirmelerinden faydalanamaz; ANTHROPIC_API_KEY yoksa doğrudan local-extractive'e düşer. İki kod yolu el-senkron tutulmalı (drift birikir). **Önerilen düzeltme:** asr_server transkript-özet yolunu `mitas_pipeline._generate_ozet`/_ozet_source_text mantığıyla paylaştır (ortak modül) veya en azından timestamp-strip ve gemini-öncelikli zinciri buraya taşı; bilerek ayrıysa docstring'e "kalite-paritesi beklenmez" notu ekle.

### MITAS_GEMINI_MODEL iki yerde farklı kod-default: _gemini.py=gemma-4-31b-it vs üretim özet yolu=gemini-2.5-flash
**Severity:** medium | **Kategori:** config-drift | **Konum:** scripts/_gemini.py:83 (vs mitas_pipeline.py:965, _health_probe.py:86) | **Etki:** Üretim özet yolu model'i açık geçtiği için ŞU AN doğru; ama MITAS_GEMINI_MODEL set EDİLMEDEN `_gemini.gemini_text()`'i model arg'sız çağıran gelecek/standalone kullanım sessizce gemma-4-31b-it'e düşer — health-probe'un test ettiği model (gemini-2.5-flash) ile farklı olabilir, A/B ve sağlık kontrolü yanıltır. **Önerilen düzeltme:** Tek kaynak: _gemini.py:83 default'unu gemini-2.5-flash yap (ya da ortak DEFAULT_GEMINI_MODEL sabiti tanımla, üç yer de onu kullansın).

### MITAS_CREDIT_DEFERENCE üretim env-set listesinde yok — ayna kuralı ihlali / config-drift
**Severity:** low | **Kategori:** config-drift | **Konum:** scripts/mitas_pipeline.py:1256-1276 + start_mitas.ps1 (eşleşme yok) | **Etki:** Kod-default '1' (açık) olduğu için şu an deferans aktif; ancak flag görünür/denetlenebilir env setinde olmadığından (a) operatör/standalone koşu farklı default'la çalışırsa fark edilmez, (b) davranış-değiştiren kritik flag belgelenmemiş kalır; KB-fill'i hâlâ yapan QC_BLOCK ile birlikte yanıltıcı "deferans açık" algısı yaratır. **Önerilen düzeltme:** `MITAS_CREDIT_DEFERENCE='1'`i _PROD_DEFAULTS'a ve start_mitas.ps1 env-set bloğuna ekle (ayna senkron); docs/MITAS_FLAGS.md'ye işle.

### Verdict-flip reprocess: aynı film hem ONAYLI hem KONTROL kovasında kalabilir (export iki-uç tek-kaynak ihlali)
**Severity:** low | **Kategori:** quality | **Konum:** scripts/mitas_pipeline.py:2417-2433 | **Etki:** Bir film önce ONAYLI'ya gidip sonra yeniden işlenip KONTROL'e düştüğünde (veya tersi) eski kopya diğerinde ORTA kalır → aynı film iki kovada birden görünür; "export'ta SADECE ONAYLI + KONTROL, tek gerçek" kuralını reprocess'te bozar. Yalnız verdict-flip reprocess'te; veri kaybı yok, mükerrer. **Önerilen düzeltme:** dest yazmadan önce diğer kova + aynı-TRT eski etiketli kopyaları sil (`credit_severity_router.strip_label`/with_label mevcut) ya da export'a yazmayı TRT-bazlı idempotent yap.

### content_profile eşleme boşluğu: spor/studio_panel ASR profilleri pipeline'dan asla erişilemez
**Severity:** low | **Kategori:** quality | **Konum:** scripts/mitas_pipeline.py:1349-1352 | **Etki:** `--profile spor` veya `studio` ile gelen içerik tanımlı özel ASR davranışını (spor anlatım prompt'u, panel diarizasyon/denoise) ALMAZ, sessizce film profiliyle işlenir; CONTENT_PROFILES'taki spor/studio_panel ölü-kod gibi durur. Pratik etki sınırlı (PROFILE_ASR'de de tanımsız). **Önerilen düzeltme:** Mapping'e 'spor'→'spor', studio→'studio_panel' dallarını ekle ya da desteklenmiyorsa CONTENT_PROFILES'tan kaldırıp kapsamı netleştir.

### Kullanılmayan üst-düzey npm bağımlılıkları + shadcn ui/* iskelesi (ölü-bagaj)
**Severity:** low | **Kategori:** health | **Konum:** webui/package.json:12-81 + webui/src/app/components/ui/ | **Etki:** (WEBUI-1) ~15 üst-düzey paket (canvas-confetti, date-fns, react-slick, react-router, react-dnd, @mui/*, @emotion/*, motion, playwright-core...) src'de sıfır import; @mui/@emotion önceki denetimde de tespit edilmiş ama hâlâ duruyor. (WEBUI-3) ui/* shadcn iskele (~20 dosya: calendar, carousel, command, chart, drawer, form...) ui/ dışından import edilmiyor, yalnız onların çektiği ağır bağımlılıklar (recharts, embla, cmdk, vaul, react-day-picker, react-resizable-panels, next-themes, input-otp, sonner) tutuluyor. Build'e girmez (tree-shake) ama bakım gürültüsü + güvenlik denetim yüzeyi + sürüm-yükseltme yükü gerçek. **Önerilen düzeltme:** İmport edilmeyen paketleri ve kullanılmayan ui/* dosyalarını (yalnız onların çektiği bağımlılıklarla birlikte) tek temizlik turunda kaldır; önce gerçek kullanımı doğrula.

### Düşük-öncelikli hijyen bulguları (info/low — davranışsal etki yok)
**Severity:** low/info | **Kategori:** health/quality/efficiency | **Konum:** çoklu | **Etki/Özet:**
- **CONFIG_DRIFT-4** (low) — tek_film_kunye.py:460 yorumu `MITAS_KB_CAST_ADD` için "default KAPALI" diyor ama kod default-AÇIK (:29) ve :26 yorumu da AÇIK diyor → dosya-içi çelişki, yanlış A/B varsayımı riski. Fix: :460 yorumunu "default AÇIK" yap.
- **CONFIG_DRIFT-5** (low) — docs/MITAS_FLAGS.md:62 `MITAS_OCR_GLM_CONSENSUS` için `_pipe_ocr.py:565` veriyor; gerçek :821 (~256 satır kaymış); mitas_pipeline.py:1253 drift-notu :623 (~198 satır kaymış). Birincil flag-referans dokümanı güvenilmez. Fix: satır-no yerine fonksiyon/sembol adı referansla.
- **KUNYE_PDF-4** (low) — credit_trace.py:157-158 ADIM 5 (v4 dolgu/deferans kararı) loglanmıyor (KÖR NOKTA); sızıntı dedektörü qc_block-KB-fill kaynağını ayırt edemez. Fix: v4_finalize_completed detail'ine yon_kaynak+kaynak_izi yaz.
- **KUNYE_OCR-5** (low) — credit_video_read.py:96 `_is_junk` substring eşleşmesi ("veya"/" yok") "Veyasettin"/"Yokuş" gibi Türkçe adları düşürebilir (:101 zaten token-bazlı, tutarsızlık). Fix: token-eşitlik kullan.
- **ASR_PIPELINE-2** (low) — quality.py:251-258 `hard_drop_signals` 4. öğesi (dil) hesaplanıp `[:3]` ile hiç değerlendirilmiyor; slice kaldırılırsa sessiz regresyon. Fix: 4. öğeyi çıkar.
- **ASR_PIPELINE-6** (low) — `_build_clean_paragraphs`/`_build_verbatim` channel_merge.py:207-222 ile transcribe.py:1030-1046'da birebir kopya (2.0s eşiği dahil); drift riski. Fix: paylaşılan yardımcıya taşı.
- **WEBUI-4** (low) — auth.ts:1-18 istemci-yan sabit-kodlu kimlik deseni (user='mitas', PW son-eki '_61'); gerçek auth sunucuda (bypass değil) ama desen bundle'da açıkta. Fix: istemci pre-validation'ı kaldır.
- **JENERIK-6** (low) — credit_detector.py:581-607 detect_both çıkış fallback tam-taraması sonrası giriş için baştan tekrar tarar (gereksiz çift geçiş + ağır geri-seek); yorum typo "en erkek"→"en erken". Fix: fallback probe'larından giriş segmentini türet, typo düzelt.
- **JENERIK-7** typo + **JENERIK-5** (info) — jenerik_detector.py:257 `S_LO` hesaplanıp hiç kullanılmıyor (ölü değişken). **HEALTH_INTEGRITY-4** (info) — model2/ paketi 6 boş __init__.py (README mevcut, planlı iskelet). **WEBUI-5** (info) — App.tsx:442 handleStartAsr deps'inde fazlalık analysisProfile. **OZET-5** (info) — _ozet_source_text timestamp-strip ana yolda no-op (transcript_plain.txt zaten damgasız; savunma kemeri, zararsız).

## Verimlilik Notları

| Bulgu | Konum | Verimlilik etkisi | Düzeltme |
|---|---|---|---|
| ASR_SERVER-2 | asr_server.py:730,1525 | Timeout'ta yetim torun süreçler (venv python + ffmpeg) RTX 3090 VRAM tutar → sonraki iş OOM (tek-GPU ağır) | taskkill /T /F tree-kill |
| ASR_PIPELINE-4 | transcribe.py:427-430,451-454 | Her single-pass'te raw_segments iki kez sort+reindex; uzun filmde binlerce segmentte gereksiz O(n log n)+replace kopyası | Sıralamayı tek yerde (_evaluate_run_segments girişi) yap |
| ORCHESTRATION-5 | mitas_pipeline.py:550-574 | Aynı sidecar XML film başına 4-5 kez parse (xml_original/xml_roles/xml_genre/genre_class×2); 100+ film batch'te tekrarlı IO | Root'u bir kez parse edip cache'le / değerleri parametre geç |
| JENERIK-4 | jenerik_detector.py:196-207 | preprocess+`.to(dev)` lock dışında; parallel'de iki 64'lük batch eşzamanlı VRAM'de → büyük kare/sınırlı VRAM'de OOM riski | `.to(dev)`+stack'i lock kapsamına al ya da parallel'de batch düşür |
| JENERIK-6 | credit_detector.py:556-584 | Çıkış fallback tam-tarama sonrası giriş için baştan tekrar tam-geçiş + ağır geri-seek (uzun video) | Fallback probe'larından giriş segmentini türet |

## Sonuç ve Öncelik Sırası

Bu denetim **SALT-OKUNUR** yürütülmüştür: **hiçbir kod değişikliği, dosya düzenlemesi veya commit yapılmamıştır.** Tüm bulgular güncel üretim kodu üzerinde bağımsız olarak (dosya:satır + kanıt-alıntı) doğrulanmıştır; bayat artefakt değildir. Sistemin statik bütünlüğü sağlamdır (327+96 modül temiz derlenir, doğru `asr` venv'inde 623 test toplanır; `ocr` venv'deki 7 hata fastapi/pyannote eksikliğinden = ortam, kod değil) ve **doğruluğu bozan çekirdek mantık hatası yoktur.** Baskın tema **konfigürasyon-drift'tir**: kalite-kontrol davranışı env-flag'lere bağlı, flag'ler kaynak-kodda default-OFF ve "ayna" setleri (kod ↔ ps1 ↔ standalone giriş noktaları) sapmış; bu, üretimden ayrışan koşuları ve yanıltıcı A/B'leri besliyor.

Önceliklendirilmiş yol haritası:

**P0 — Teslim güvenilirliğini ve doğruluğu doğrudan etkileyen (high):**
1. **Flow-worker returncode kontrolü** (asr_server.py:751) — false-success'i kapat; iki tekrar bloğunu tek yardımcıya çıkar. *(En yüksek etki: sessiz bozuk teslim.)*
2. **credit_qc_block deferans kapısı** (credit_qc_block.py:662/746-761) — deferans-açıkken KB-fill durdur; deferans ihlalini üretimde gerçekten kapat.
3. **Config-drift senkronu** (mitas_pipeline.py _PROD_DEFAULTS ↔ start_mitas.ps1) — CAST/dedup flag'lerini tek kaynaktan yönet + yanlış yorumu düzelt; CI diff-testi ekle. Bu, OneOCR Fix-E ve diğer A/B-yanıltıcı drift'lerin de şemsiyesi.
4. **rerender_pdf_only.py flag-set** (rerender_pdf_only.py:213-219) — tüm _PROD_DEFAULTS'u (en az QC2+QC_OTORITE_ROUTE) subprocess env'ine uygula.
5. **OneOCR Fix-E flag-hizalaması** (jenerik_oneocr_detector.py:160) — paddle ile aynı flag'e bağla; A/B'de iki taraf aynı durumda koşsun.

**P1 — Üretim davranışını/UI'yi etkileyen (medium):**
6. no-copy-source medya 403 (asr_server.py:3770) — UI medya akışını çoğu üretim işi için onar.
7. Timeout tree-kill (asr_server.py:730,1525) — VRAM sızıntısı/OOM zincirini kes.
8. _pipe_pdf video_credits=None deferans-güvenliği (mitas_pipeline.py:2014) — credit_parse çöp-sızıntısını kapat.
9. ASR logger child-isolation (pipeline.py:400) + tedial lazy-import (__init__.py:35) + Canlı-STT niyet kararı (App.tsx:1123).
10. Master-PNG slit yön-körlüğü + min_hold kart-kaybı (db_compose_master.py:441,402) — ters roll smear ve kısa-kart kaybını gider.
11. OCR-refine 6-kelime eşiği (jenerik_detector.py:606) + statik-kart CLIP-yok recall (453) + VL-model/romanizasyon-guard config-drift'leri.

**P2 — Hijyen/dokümantasyon/verimlilik (low/info):** XML tek-parse cache, ASR çift-sort, bayat yorumlar (CONFIG_DRIFT-4/5, OZET-2 log), ölü kod (_ozet_deepseek, S_LO, model2/), npm/shadcn ölü-bagaj temizliği, credit_trace ADIM 5 instrumentasyonu ve diğer info-seviye notlar.

**Çapraz öneri:** P0.3 ve P0.4'ün ortak kökü "iki ayna/üç giriş noktası elle senkron" varsayımıdır; flag setini **tek kaynaktan türetmek** (ps1'i _PROD_DEFAULTS'tan üretmek veya drift'i CI'da kıran bir diff-testi) bu sınıfın (en az 6 doğrulanmış config-drift bulgusunun) tamamını kalıcı kapatır ve gelecekteki yanıltıcı A/B'leri önler.