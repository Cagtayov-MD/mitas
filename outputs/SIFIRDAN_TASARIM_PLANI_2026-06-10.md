# "BEN OLSAM NASIL KURARDIM" — SIFIRDAN TASARIM PLANI (2026-06-10)

Üretim süreci: 4 derin uzman (jenerik-OCR, ASR, LLM-zenginleştirme, orkestrasyon; web-araştırmalı, 2026 SOTA teyitli) → 2 bağımsız baş-mimar (doğruluk-öncelikli + operasyon-öncelikli; %85 örtüştüler) → acımasız eleştirmen (aşırı-mühendislik ayıklama + eksik tespiti). Bu doküman üçünün sentezidir.

---

## 0. EN ÖNEMLİ UYARI: BIG-BANG YOK

Elde **çalışan, ~%92 üretim-kabul ölçülmüş** bir sistem var. "Sıfırdan kur" cevabı bunu çöpe atmak değil. Doğru strateji **strangler-fig**: aşağıdaki yeni omurgayı kur, kanıtlı parçaları (OneOCR entegrasyonu, ffprobe/PAL düzeltme, TR-İ/v4 format kuralları, ASR kara-listeleri, MMS-LID) aşama aşama içine taşı, taşınan her aşamayı eski sistemle **aynı filmlerde shadow-diff'le**, eski sistem yenisi 100-film gece koşusunu kill-test'li geçene dek üretimde kalsın.

---

## 1. YEDİ OMURGA KARARI

1. **Eval-first:** Golden-set + dürüstlük-ağırlıklı harness (doğru=+1, eksik=−1, yanlış=−3) HER ŞEYDEN ÖNCE kurulur. Ground-truth'un çekirdeği bedavaya hazır: 102 ONAYLI seti + 43-künye internet-teyit raporları + 12-film QC denetimi. "Daha dolu ama daha yanlış" varyantın kazanması matematiksel olarak engellenir; uydurma-isim oranı = 0 tek başına release-blocker.
2. **Jenerik okuma = TRACK okuma, kare okuma değil:** Aynı isim 10+ karede geçer; satır izlenir, 5-10 örnekten karakter-düzeyi oylama ile tek isim üretilir. Pixel slit-scan/stitch YASAK (hayalet kanıtlı), füzyon metin düzeyinde.
3. **Çift-motor consensus, ikisi de ollama-DIŞI:** PP-OCRv5 (CPU-ONNX, kendi venv) ∥ Windows OneOCR (CPU, OS-native). GLM-doygunluk-stall sınıfı kökten ölür çünkü OCR hattı ollama'ya hiç dokunmaz. Hakem v1'de YOK — anlaşmazlık LOW_CONF/KONTROL'e düşer; hakem ancak anlaşmazlık oranı insan kuyruğunu boğarsa turnuvayla (PaddleOCR-VL-1.5-GGUF vs InternVL3-8B) girer.
4. **LLM asla isim üretemez (closed-set):** Rol eşlemenin %70-80'i deterministik etiket+layout state-machine'de biter (YÖNETMEN/REJİSÖR... etiket sözlüğü + bbox geometrisi). Artıklar qwen3:8b'ye JSON-şemayla gider ama yalnız OCR'dan gelen listeden SEÇER; çıkıştaki her isim OCR satırında birebir doğrulanır, yoksa atılır. Halüsinasyon yapısal olarak imkânsız.
5. **Kimlik-önce + jenerik-OTORİTE:** Film TMDB/Wikidata'da çok-kanıt kilidiyle (başlık + ≥2 bağımsız sinyal: yıl/yönetmen/≥2 cast/süre±%5 PAL-düzeltmeli) LOCKED olmadan web verisi SIFIR. Web/KB yalnız yazım düzeltir/doğrular, ASLA ezmez. Yönetmen kırmızı-çizgi: OCR'dan okunamadıysa KB-fill yok → KONTROL.
6. **"Okunamadı" başarılı terminal durumdur:** Okunabilirlik kapısı (native-res stroke_px<2 VEYA x-height<8px → OCR'a girmez) + deterministik garble katmanı (TR hece çözümleyici + ünlü oranı + çift-KenLM karakter-LM + gazetteer) geçemeyen token PDF'e giremez. EKSİK ≠ hata; retry tetiklemez.
7. **SQLite-WAL + marker-checkpoint + subprocess izolasyonu omurga:** Tek dosya kuyruk+state+events (Redis/RabbitMQ = tek makinede ikinci arıza noktası, ELENDİ). Her GPU işi Job-Object'li ayrı subprocess'te koşar, flush-sonrası os._exit (CTranslate2-crash sınıfı tek aşamayı öldürür, batch'i değil). GPU kesinlikle SERİ; hız film-ARASI CPU/GPU şerit örtüşmesinden gelir (film N ASR'dayken film N+1 decode+OCR-CPU): ~450 → ~300-330 sn/film.

---

## 2. SİSTEM AKIŞI

```
INGEST (robocopy + ffprobe + XML parse)
  → DECODE (ffmpeg; bwdif deinterlace + corrupt-frame toleransı — 1960-90 transferi şart)
  → [CPU şeridi]  OCR HATTI                      → [GPU şeridi]  ASR HATTI
     sınır tespiti → kayan/statik → okunabilirlik    kanal çıkar → VAD → MMS-LID →
     kapısı → track örnekleme → çift-motor           faster-whisper turbo (batched) →
     consensus → rol state-machine                   3-katman halüsinasyon filtresi → SRT
  → KİMLİK KİLİDİ (TMDB+Wikidata çok-kanıt) → GARBLE/DÜZELTME → ROL-LLM (artıklar)
  → KÜNYE MONTAJI (deterministik; kunye.json = TEK doğruluk kaynağı)
  → ÖZET (Gemini Batch zinciri; ayrık şerit, DEFERRED'li)
  → PDF (her zaman ve yalnız kunye.json'dan render — tek yol)
  → KADEME (KESIN/KONTROL/EKSIK) → sabah raporu + ntfy push
```

Veri modeli: `batch.db` (SQLite-WAL: films/events/quotas/cloud_requests) + film-klasöründe aşama marker'ları (tmp→os.replace atomik, STAGE_VERSION'lı). Resume kuralı: marker varsa aşama atlanır; startup'ta "RUNNING ve eski → PENDING" (lease/heartbeat makinesi YOK — tek worker'da 10 satırlık startup-recovery aynı garantiyi verir).

---

## 3. OCR'I DAHA İYİ OKUMA REÇETESİ (sorunun kalbi)

**A0 — Jenerik sınır tespiti (sabit pencere YOK):** Baş+son 12dk @1fps PP-OCRv5 det (DBNet) metin-piksel yoğunluğu → temporal morfoloji (kapama 5sn, min segment 10sn) → jenerik segmentleri. Segment bulunamazsa dürüst "jenerik-yok" işareti, körlemesine OCR koşulmaz. (CLIP+attention sınıflandırıcı SONRAYA: önce v0'ın kaçırma oranı ölçülür.)

**A1 — Kayan/statik ayrımı:** Ardışık kareler arası `cv2.phaseCorrelate`, AMA SADECE metin maskesi üstünde (det kutularından; arka plan hareketi sinyali kirletmesin). Tutarlı |dy|>0.5px/kare ≥2sn → KAYAN (hız v kaydedilir); dy≈0 + frame-diff spike → STATİK kart sınırları. v bilinince öğrenilmiş tracker'a gerek yok — deterministik asosiyasyon.

**A2 — Okunabilirlik kapısı v2 (native çözünürlükte, 512×288'de DEĞİL):** metin maskesinde distance-transform medyanı×2 = stroke_px; satır x-height px; maske içi/dışı kontrast. HARD-FAIL: stroke<2px VEYA x-height<8px → 'okunamadı', OCR'a girmez. SOFT-FAIL bandı (stroke 2-3.5px): iyileştirmeye gider.

**A3 — İyileştirme (yalnız soft-fail bandına):** (1) temporal füzyon: aynı track'in 8-16 crop'u sub-pixel hizala (ECC/phase-corr) → piksel MEDYANI — film grain'i söndürür, sıfır halüsinasyon riski; (2) gerekirse Real-ESRGAN x2 (SR'lı/SR'sız A/B, confidence yüksek kazanır). **Diffusion SR (StableSR/SUPIR) YASAK** — OCR doğruluğunu düşürüp karakter uydurduğu ölçülmüş (%40.6→%34.6). Binarizasyon modern tanıyıcıya verilmez, yalnız ölçüm/maske için.

**A4 — Track örnekleme + oylama:** KAYAN: her satır track'i ekranın orta %50 "altın bölgesinden" geçerken 5-10 örnek; her örnek OCR; NFC-normalize → Levenshtein-medoid + karakter-pozisyonu bazında confidence-ağırlıklı çoğunluk oyu. STATİK: kart penceresinden gradient-enerjisi en yüksek 3 kare + satır oylaması. Çıktı sırası = track'in ekrana giriş zamanı (billing order korunur).

**A5 — Çift-motor consensus (zamanlama-güvenli):** PP-OCRv5 Türkçe (OCRTurk benchmark kazananı NED 0.08 — AMA doküman-seti ölçümü; **1. haftada kendi jenerik-crop'larında yeniden doğrula**) ∥ OneOCR. İkisi de süreç-izole, çağrı başına hard timeout. Satır kararı: normalize-eşit → kabul; Levenshtein≤2 + fark yalnız diakritik → TR isim-KB'ye yakın olan; büyük fark → anlaşmazlık kuyruğu → LOW_CONF/KONTROL. Post-process ZORUNLU: Unicode NFC (motorlar ğ'yi breve+g ayrı yazıyor) + TR-locale İ/ı upper. OneOCR-ölür degrade modu tanımlı: PP-only + eşik sıkılaştırma (OneOCR resmi-olmayan API + Win10 EOL riski).

**A6 — Rol eşleme (katmanlı):** (1) TR etiket sözlüğü (YÖNETMEN/REJİSÖR/YÖNETEN, YAPIMCI/PRODÜKTÖR, SENARYO, OYUNCULAR/BAŞ ROLLERDE... regex+fuzzy≤1) + bbox-layout state-machine (aynı-satır / etiket-üstte / iki-sütun; kayan jenerikte current_role sonraki etikete dek taşınır) — vakaların ~%70-80'i, halüsinasyon imkânsız. (2) Artıklar closed-set qwen3:8b (format=json; "isim üretme yasak, yalnız rol ata, emin değilsen unknown"); çıkan her isim OCR satırlarında doğrulanır. (3) İsim-KB (Wikidata+TMDB TR sinema ~100K, SQLite) RapidFuzz iki-kademe: film-özel-KB ≥88 / genel gazetteer ≥93 + margin ≥5 + OCR-karışıklık ağırlıklı re-rank (İ/I/l/1 maliyeti 0.3) — yalnız YAZIM düzeltir.

**Çıktı veri yapısı (satır başına):** `{text_raw, text_norm, conf_A, conf_B, consensus_status, bbox, track_id, t_start, t_end, role, garble_score, source_frames[]}` — PDF bunun render'ı; makine-okur metadata bedavaya çıkar.

**Süre bütçesi:** OCR yalnız jenerik segmentinde (~2-4dk video); hedef 60-120sn/film, ağırlıkla CPU → GPU'daki ASR ile tam örtüşür.

---

## 4. ASR REÇETESİ

- **Omurga:** faster-whisper **large-v3-turbo** (CT2 float16, ~2GB VRAM) + **BatchedInferencePipeline batch=8** → 2 saatlik film ~2-3dk (mevcut tek-pass'tan da hızlı). `condition_on_previous_text=False` + sıcaklık-fallback (tekrar-döngüsü ~sıfırlanır, tek satır değişiklik).
- **Halüsinasyon savunması 3 katman:** (1) Silero VAD v5 ön-kapısı (müzik bölümü halüsinasyonu kökten kesilir + hız); (2) decode parametreleri; (3) segment-sonrası filtre: no_speech_prob/avg_logprob/compression_ratio üçlü-eşik + 3-gram döngü dedektörü + TR kara-liste ("Altyazı M.K." fosilleri).
- **Dil/dublaj:** kanal-başı çıkarım + VAD konuşma-oranıyla diyalog-kanal seçimi + MMS-LID kanal oylaması + film boyu TEK dil kilidi (segment-bazlı auto kayması halüsinasyon kaynağı). LID çökerse sessiz 'tr' varsayma → 'lid_failed' bayrağı → KONTROL.
- **Hotwords:** XML cast adlarını DEĞİL, **OCR-teyitli ∩ XML** isimleri ver (jenerik-OTORİTE ilkesiyle tutarlı; OCR aşaması zaten ASR'dan önce). A/B kapısıyla ölç (özel-isim recall delta).
- **Güven skoru:** 2-3 sinyalle başla (segment-red-oranı + LID güveni + konuşma-kapsama) → A/B/C notu → özet prompt'una enjekte ("C notu: finali transcript desteklemiyorsa yazma"). Formal Spearman kalibrasyonu sonraya.
- **Dayanıklılık:** subprocess-per-film + segment-bazlı artımlı jsonl flush + flush-sonrası os._exit; kill-test: resume son flush'tan devam, 0 kayıp.
- **Çıktılar:** transcript + **SRT/VTT** (timestamp zaten var — sektörün birincil teslim formu bedavaya) + composite güven notu.
- **Seçici ikinci geçiş:** yalnız C-notu filmlerde large-v3 beam=5 (toplama <%10 ek süre).
- **Elenenler:** NVIDIA Canary/Parakeet (Türkçe YOK), bulut ASR (ses makineden çıkamaz), distil-whisper (İngilizce-odak), TR fine-tune'lar (Common Voice okuma-sesi eğitimli, film sesinde regresyon riski — yalnız golden-set testi). **Qwen3-ASR-1.7B** (Türkçe destekli, açık kaynak, Ocak 2026) challenger: golden-set turnuvasını kazanmadan terfi etmez.

---

## 5. KÜNYE + ÖZET REÇETESİ

- **Kimlik kilidi:** başlık + ≥2 bağımsız kanıt → LOCKED; seri/üçleme: aynı-fold-başlıklı ≥2 aday + yıl yok → AMBIGUOUS → KB-tamamla kapalı + KONTROL. **İlk hafta 100 örnek 1960-90 filminde LOCKED oranını ÖLÇ** — TMDB/Wikidata eski Türk sinemasında zayıfsa SinemaTürk vb. yerli kaynak ek katman olarak değerlendirilir; düşük oran sistemin hatası değil ama beklenti yönetimi şart.
- **Okunamaz-jenerik kurtarma yolu (QC2-b dersinin kurumsallaşması):** OCR boş/çöpken başlık+yıl±1+süre±%5+XML sinyalleriyle LOCKED yolu AÇIKÇA tanımlı; web-TAMAMLAMA otomatik değil, **insan-onaylı KONTROL akışının bir butonu**. (Aksi halde en zor %10 sonsuza dek EKSİK kalır.)
- **Özet:** Gemini Flash **ücretli Batch API** birincil (1M bağlam = tam transkript chunk'sız, %50 indirim; free-tier'a yaslanma ölçülmüş ders) → Claude → DeepSeek; sağlayıcı health-probe + devre-kesici (5dk'da 3 hata → 30dk skip) + 429 HER ZAMAN geçici + quotas sayacı. Zincir ölürse film FAILED değil **DEFERRED** — batch sürer, sabah toplu retry. DEFERRED'li PDF 'taslak' işaretli; kanonik render yalnız özet birleştikten sonra (bayat-PDF tuzağı kapanır).
- **Kanıt-önce spoiler-final protokolü:** önce son 15dk'dan final-kanıt alıntısı çıkarılır; `final_kanit=null` → finalsiz özet MEŞRU çıktıdır, uydurma final yazılamaz (HIRSIZ dersi yapısallaşır). Tam claim-decomposition/NLI-grounding ERTELENDİ — 40-65 kelimelik özette felaket sınıfı uydurma finaldir ve bu protokol onu kapatır.
- **Şema disiplini:** hiçbir LLM çıktısı serbest-metin parse edilmez; JSON-şema + Pydantic, 2 retry sonra alan='bilinmiyor'; çapraz-alan kuralları (ana_dil≠TR + altyazı=yok → KESİN yasak) validator'da.
- **Altyazı tespiti tasarlanacak** (eleştirmenin yakaladığı boşluk): künyenin zorunlu alanı ve en kritik mantık kapısının girdisi — alt-bölge örnekleme + OCR varlık-oranı yaklaşımıyla ayrı mini-modül.

---

## 6. ORKESTRASYON OMURGASI

- SQLite-WAL `batch.db`; startup-recovery (lease/heartbeat YOK — aşırı mühendislik, tek worker var).
- Marker-checkpoint: `decode✓ ocr✓ asr✓ enrich✗` → enrich'ten devam; atomik tmp→os.replace; STAGE_VERSION + kunye.json'a `pipeline_version` (yeniden-işleme politikası: re-run varsayılan yalnız KONTROL/EKSİK; DONE toplu re-run ancak harness kanıtıyla).
- win32job **Job Object** (KILL_ON_JOB_CLOSE) → orphan süreç yapısal sıfır; aşama-başı hard timeout (ASR ≤ max(15dk, süre/25×1.5); film toplam 60dk).
- İki-şerit: GPU-lane seri (tek-sahip ilkesi), CPU-lane paralel prefetch. Mini-dalga/gpu_tasks SONRAYA (swap maliyeti ölçülmeden ikinci zamanlama katmanı kurulmaz).
- Ollama'nın sistemdeki TEK görevi rol-LLM; health-probe + 60s timeout + skip politikası; geçiş tetiği tanımlı: "gecede ≥3 ollama-restart → llama-swap+llama.cpp'ye geç".
- Devre-kesiciler: aynı aşamada ardışık 3 farklı-film hatası → batch PAUSE + ntfy push. Disk kapısı: claim öncesi boş alan eşiği; film-sonu frames/wav temizliği; karantina tavanı.
- VRAM kapısı eviction-DOĞRULAMALI ama 90sn timeout'lu (süresiz stall yasak — 19GB-guard dersi).
- İdempotans gerçekçi: byte-hash determinizmi yalnız CPU aşamalarında (montaj/normalizasyon/PDF); ASR/LLM'de şema-geçerlilik + alan-eşdeğerliği.
- **Yedekleme (eleştirmen boşluğu):** batch.db + kunye.json + golden-set + gazetteer/KenLM her gece ikinci konuma robocopy; tek-disk ölümü tatbikatı bir kez yapılır.
- İzleme: SQLite events + otomatik sabah raporu (DONE/KONTROL/FAILED, aşama medyanları, en yavaş 5, garble taraması, lock oranı) + ntfy.sh push. Kaos tatbikatları: orkestratör-kill, ollama-kill, disk-doldurma, bulut-kesinti — dördü de kabul testidir.

---

## 7. ADIM ADIM İNŞA PLANI (~7-9 hafta, her faz sonunda çalışan+ölçülen dilim)

| Faz | Süre | İçerik | Kabul testi |
|---|---|---|---|
| **0 — İskelet + Eval** | 4-5 gün | batch.db + marker-runner + Job Object + INGEST/PROBE/DECODE (bwdif dahil); golden-set v0: mevcut doğrulanmış verilerden (102 ONAYLI, 43-künye teyit, 12-film QC) 20-film ground-truth devşir + dürüstlük-ağırlıklı harness | 20-film decode-only koşusu; ortasında kill → 0 kayıp, 0 çift-işleme, orphan=0 |
| **1 — ASR şeridi** | 5-7 gün | Bölüm 4 paketi komple (VAD+LID+turbo-batched+filtre+SRT+güven notu) | 10-film kesintisiz; kill-resume son flush'tan; 2sa film ≤8dk; sessiz-klipte kelime=0 |
| **2 — OCR v0** | 8-10 gün (en riskli faz) | Bölüm 3 A0-A6 (hakemsiz, SR'sız); 1. haftada PP-OCRv5'i kendi jenerik-crop'larında doğrula | mini-sette uydurma-isim=0; yönetmen-recall raporlu; OCR ≤120sn/film CPU |
| **3 — Kimlik+garble+künye+PDF + İNSAN ARACI** | 7-9 gün | çok-kanıt kilit + garble katmanı + closed-set rol + montaj + tek-yol PDF; **KONTROL inceleme aracı** (lokal sayfa: kanıt-crop + iki motor çıktısı + alan düzeltme → kunye.json'a yazar, düzeltme gazetteer+golden-set'e geri beslenir) | 20-film uçtan uca; PDF'te garble=0; LOCKED oranı raporlu |
| **4 — Özet + bulut** | 5 gün | Bölüm 5 özet paketi; ÜCRETLİ hesap/kota planı bu fazdan ÖNCE kapatılır | kasıtlı bozuk API key'le gece koşusu: zincir devreder, FAILED=0, sabah DEFERRED=0 |
| **5 — Ölçek + shadow** | 5-7 gün | iki-şerit pipelining + disk yaşam döngüsü + watchdog/ntfy + kaos tatbikatları; **eski sistemle shadow-diff** (aynı filmler iki hatta, alan-bazlı karşılaştırma) | 100-film gece insansız; kayıp=0, orphan=0; medyan ≤330sn/film; shadow-diff'te yeni ≥ eski |
| **6 — Turnuvalar** | sürekli, kalem başı 2-4 gün | SADECE harness'te kanıtlanmış kazançla girer: OCR hakemi (PaddleOCR-VL-1.5-GGUF vs InternVL3-8B), Real-ESRGAN A/B, Qwen3-ASR challenger, CLIP sınır-sınıflandırıcı, llama-swap geçişi, pyannote değişim-sinyali | kazanmayan aday üretime giremez |

Geçiş kuralı: Faz 5 kabulü geçilene dek eski sistem üretimde; sonra trafik yeni hatta, eski sistem 1 ay donmuş yedek.

---

## 8. NE YAPMAM (elenenler + nedenleri)

- **VLM-birincil jenerik okuma** — halüsinasyon kanıtlı; VLM en fazla batch-sonu hakem, o da turnuvayla.
- **Pixel slit-scan/stitch panorama** — hayalet kanıtlı; füzyon metin düzeyinde.
- **Diffusion SR** — OCR doğruluğunu düşürüyor, karakter uyduruyor.
- **Tam pyannote diarization** — film işinde maliyet/fayda tutmuyor; en fazla hafif değişim-sinyali, o da A/B ile.
- **Redis/RabbitMQ/mikroservis** — tek makinede ikinci arıza noktası.
- **Lease+heartbeat, mini-dalga, byte-hash-her-yerde** — tek-worker gerçekliğinde aşırı mühendislik; basit startup-recovery yeter.
- **CLIP sınır-sınıflandırıcı + sentetik fine-tune v1'de** — eğitim yatırımı, tavan ölçülmeden yapılmaz.
- **Free-tier'a yaslanan bulut planı** — ölçülmüş kırılma; ücretli Batch + zincir + DEFERRED.
- **Tam claim-decomposition grounding v1'de** — 5 cümlelik özet için israf; kanıt-önce final protokolü felaket sınıfını zaten kapatıyor.
- **Hotwords'ü saf XML'den besleme** — jenerik-OTORİTE ile çelişir; OCR-teyitli∩XML.

---

## 9. MEVCUT SİSTEME BUGÜN UYARLANABİLECEK EN DEĞERLİ 10 FİKİR

(Tam geçişi beklemeden, mevcut koda tek tek taşınabilir — her biri bağımsız.)

1. `condition_on_previous_text=False` + üçlü-eşik halüsinasyon filtresi → `_pipe_asr.py` (saatlik iş, anında kazanç)
2. BatchedInferencePipeline batch=8 → ASR ~2-3×  hızlanır
3. Okunabilirlik kapısını (stroke_px, hazır `fqc.py`) OCR zincirinin ÖNÜNE bağla
4. Rol eşlemeye etiket+layout state-machine ön-katmanı (LLM'e giden hacim %70-80 düşer, halüsinasyon-yüzeyi daralır)
5. Closed-set doğrulama: qwen çıkışındaki her isim OCR satırında birebir aranır, yoksa at
6. KenLM çift karakter-LM + TR hece çözümleyici garble katmanı (CPU, deterministik) → final kapıya
7. Kanıt-önce spoiler-final protokolü → ozet_film.txt + `_generate_ozet`
8. Gemini 429 = her zaman geçici + retryDelay okuma + DEFERRED kuyruğu
9. SRT/VTT üretici (timestamps zaten var — yarım günlük iş, yeni teslim ürünü)
10. Dürüstlük-ağırlıklı golden-set harness'i (102 ONAYLI + 43-teyit verisinden devşirme) — bundan sonraki HER değişikliğin bekçisi

---

*Kaynak doğrulamaları (eleştirmen web-teyitli): PaddleOCR-VL-1.5 GGUF/llama.cpp desteği gerçek (huggingface.co/PaddlePaddle/PaddleOCR-VL-1.5-GGUF); Qwen3-ASR-1.7B açık kaynak + Türkçe (github.com/QwenLM/Qwen3-ASR); OCRTurk benchmark gerçek ama doküman-tabanlı, jenerik transferi garanti değil (arxiv.org/abs/2602.03693).*
