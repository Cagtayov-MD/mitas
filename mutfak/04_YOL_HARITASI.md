# 04 — YOL HARİTASI

> Son güncelleme: 2026-05-18
> Son değişen bölüm: v0.2 kapsamına Repertuvar Bankası + ASR Anons Parser + composition/performance ayrımı eklendi (Karar 37); fingerprint doğrulayıcı olarak netleşti

Bu dosya MITAS'ın sürüm bazında **nereye gittiğini** anlatır. Tarih hedefleri **bilinçli olarak yazılmaz**; tek kişilik geliştirmede tarih baskısı kararları çarpıtır. Sürüm sırası ve kabul kriteri sabittir; takvim esnektir.

---

## 1. Sürüm felsefesi

- **Her sürüm bir dikey dilimdir.** Bir modülün uçtan uca çalışan halini hedefler: input → işleme → JSON çıktı → smoke test.
- **Sırayla ilerlenir, paralel açılmaz.** Bir dikey dilim oturmadan bir sonrakine geçilmez. Bu disiplin tek kişilik geliştirmede zorunludur.
- **Her sürümün benchmark eşiği vardır.** Eşik geçilmeden bir sonraki sürüme geçmek "kâğıt üzerinde yapıldı" durumudur.
- **Showcase ≠ Final analiz.** Sunum/demo amaçlı çıktılar production pipeline'a karışmaz.

---

## 2. Sürüm sırası ve gerekçesi

### v0.1 — ASR dikey dilim (TAMAMLANDI)

**Sprint kapanış raporu:** [docs/SPRINT_4_ASR_V0_1_DONE.md](../docs/SPRINT_4_ASR_V0_1_DONE.md). Sözleşme katmanı (ModuleRun + TimelineEvent), kalite raporu (summary.quality_report §2.1 5 alan), smoke test (10 madde) ve gerçek demo output (`outputs/asr_v0_1_demo/`, klip: 001_h1 TRT haber kameramanları, 101.7 sn) yeşil. Toplam 166 test geçiyor.

**Neden ilk:** ASR tüm timeline'ın zaman ekseni omurgasıdır. Face Recognition, OCR'ın temporal merge'i, Visual Tag'in sahne timing'i, hepsi ASR timeline'ı üstüne oturur. ASR çürükse her şey kayar.

**Kapsam:**
- VAD (Silero)
- faster-whisper `large-v3-turbo` default decode motoru (`multilingual=True`, Karar 14, Karar 23)
- faster-whisper `large-v3` selective fallback / üst-denetim modeli (tail-gap, safety failure, coverage selector; Karar 24)
- WhisperX word-level alignment (`alignment` venv'de opsiyonel; v0.1 ana pipeline dışında)
- pyannote diarization (v1 zorunlu bileşen; eşik geçilmezse `speaker_id = null`, Karar 15)
- diarization fail graceful degradation (`partial_success`, Karar 16)
- DeepFilterNet denoise (koşullu)
- ffmpeg audio extract
- JSON primary çıktı (segments + words)
- ASR kalite raporu (word timestamp coverage, alignment success, VAD speech ratio)
- fallback audit log (`fallback_reason`, `selection_reason`, safety diagnostics)

**Kabul kriteri:**
- 1 dakikalık Türkçe TRT haber kesitinde:
  - %95+ kelime doğruluğu (CER veya WER hedef şu an konulmadı, mini benchmark sonrası belirlenecek)
  - segment timestamp drift < 0.5 saniye
  - VAD speech ratio % cinsinden raporlanır
  - JSON master plan §1.2 timeline event sözleşmesine uyar

**Çıktı dosyası:** `outputs/asr_v0_1_demo/` (5 artifact: archive, summary, module_run, transcript_review, timeline_events).

**v0.1 sonrası bilinen açıklar:** v0.1 dilimi *çalışan ASR + kalite raporu sözleşmesi* kapsadı. WhisperX entegrasyonu, diarization profil bazlı çağrı, profile dispatch, persistent worker ve TRT eşik kalibrasyonu **v0.1.x patch'leri** olarak ayrı sprint başlığında ilerleyecek (aşağıda).

---

### v0.1.x — ASR Olgunlaşma Paketleri (DEVRED)

v0.1 dikey dilim kapandı; aşağıdaki 5 iş ASR'yi production v1'e hazırlar. Detaylı içerik, mevcut kod hazırlığı, ne yapılacak, niye önemli ve maliyet için: **[docs/ASR_V0_2_DEVRED_ISLER_DETAYLI.md](../docs/ASR_V0_2_DEVRED_ISLER_DETAYLI.md)**.

| # | Paket | Şu an ne var | Eksik | Maliyet | Engelleyen |
|---|---|---|---|---|---|
| 1 | **WhisperX entegrasyonu** | `scripts/alignment_subprocess.py` subprocess sleeve smoke yeşil; `venvs/alignment/` kurulu | `core/pipelines/asr/align.py` + pipeline kancası; `quality_report.word_timestamp_coverage` + `alignment_success` doldur | 1-2 gün | — |
| 2 | **Diarization profil bazlı çağrı** | `core/pipelines/asr/diarize.py` 214 satır gerçek kod; `tests/test_asr_diarize.py` yeşil; pyannote-audio 4.0.4 `asr` venv'de kurulu | `pipeline.py` diarize'ı import etmiyor; segment-speaker merge yok; Karar 15 graceful degradation eşiği uygulanmamış | 2-3 gün | Paket 3 |
| 3 | **Profile dispatch (5 içerik profili)** | Karar 15 davranış matrisi dokümante (`bulten_haber`, `studio_panel`, `muzik_programi`, `film`, `belgesel`) | `profiles.py` yok; `run_asr_pipeline()` sadece MODEL profili (`fast_with_fallback`) alıyor; içerik profili parametresi yok | 1 gün | — |
| 4 | **Persistent worker** | `_MODEL_CACHE` in-process cache; `core/jobs/worker.py` DummyWorker iskelet; `core/jobs/repository.py + step_runner.py` altyapı var | ASR-spesifik persistent worker yok; job queue gerçek değil; model cache thread-safe değil (HIGH-4) | 2-4 gün | — |
| 5 | **TRT verisi eşik kalibrasyonu** | `scripts/asr_mediaspeech_benchmark.py` parametrik; `outputs/asr_archive_all_wav_benchmark/` (14 TRT WAV) fast/quality karşılaştırması var ama reference transcript yok | TRT iç gold transcripts (WAV+TXT çiftleri); fallback trigger rate analizi; eşik tuning | 2-3 gün (data sonrası) | **TRT veri** |

**Pratik sıralama önerisi:** 3 → 2 → 1 → 5 (veri gelince) → 4. Paket 3 hızlı ve diğer her şeyin önkoşulu; paket 4 production-grade ihtiyaç, dev sırasında one-shot çağrı yeterli.

**Kabul kriteri (her paket için):** 
- Paket 1: `quality_report.word_timestamp_coverage > 0.95` ve `alignment_success = true` smoke test'te
- Paket 2: TRT haber klibinde en az 2 farklı `speaker_id` üretilir; düşük güvende `null` graceful degrades
- Paket 3: 5 içerik profili pipeline çağrısında tanınır; override mekanizması çalışır
- Paket 4: 10 ardışık klip tek model yüklemesiyle işlenir; cache thread-safe
- Paket 5: Karar 24 eşikleri (`max_uncovered_tail_seconds`, `max_uncovered_tail_ratio`, coverage tolerance) TRT verisinde sayısal gerekçeyle güncellenir

---

### v0.2 — OCR/KJ + Müzik Segment dikey dilim

**Neden ikinci:** Müzik programı analizi MITAS'ın yüksek değer üreten parçası; KJ + ASR + audio activity birleşimi axle.ai'de yok. Ayrıca KJ okuma metadata için kişi kimliği önerisinin ana kanalı (Face Recognition'dan önce).

**Kapsam:**
- PaddleOCR / PP-OCRv5 multilingual aday (benchmark sonrası kesinleşir)
- ROI-first OCR akışı (bottom_band → center_lower → full_frame_fallback)
- Temporal merge (frame-frame aynı KJ'yi tek event'e birleştirme)
- `screen_text` event üretimi
- YAMNet veya benzeri Audio Activity Layer (speech / music / applause / silence)
- Chromaprint + AcoustID veya local fingerprint DB (**doğrulayıcı katman**, primary değil — Karar 37)
- `song_performance` event üretimi (Karar 37 karar matrisi; KJ güveni `f(ocr_conf)`)
- **Repertuvar Bankası** (eser/sanatçı varlık sözlüğü, dosya-tabanlı: SQLite/CSV/JSONL) — KJ/anons çıktısını doğrulayan entity DB (Karar 37)
- **ASR Anons Parser** (bağımsız modül: "şimdi X'ten Y'yi dinleyeceğiz" → entity extraction) (Karar 37)
- **composition (eser) entity ≠ song_performance (icra) event** ayrımı; `song_performance` `composition_id` FK taşır (Karar 37)
- Sinyal hiyerarşisi: KJ/OCR + ASR Anons **primary**, Chromaprint/AcoustID **doğrulayıcı** (Karar 37) — birleşim değil, açık güven sırası
- Vocal isolation + lyric match v0.2 **çekirdeği dışı**; v0.2.x/v0.3 opsiyonel

**Kabul kriteri:**
- 1 saatlik müzik programı örneğinde:
  - en az 80% KJ kişi/şarkı adı doğru çıkarımı
  - audio activity speech/music ayrımı insan yargısıyla %90+ uyum
  - song_performance segmentlerinin start/end ±2 saniye toleransla doğru
  - Repertuvar resolve unit testi: "Selâhattin Pınar" → besteci entity, "ne güzel güldün" → composition entity döner

**Bağımlılıklar:** ASR JSON çıktısına yaslanır. **Sert önkoşul:** v0.1.x Paket 3 (profile dispatch / `muzik_programi`) kapanmış olmalı — ASR Anons Parser ve lyric ASR bu profili gerektirir (bkz. §v0.1.x; Karar 37). Detaylı analiz: `mutfak/14_MUZIK_TANIMA_PLANI.md`.

---

### v0.3 — Görsel Tagleme dikey dilim

**Neden üçüncü:** Sahne / nesne / atmosfer tagleri arşiv arama için temel. Logo / marka da bu modülün altında (alt başlık olarak).

**Kapsam:**
- PySceneDetect sahne bölme (CPU)
- YOLO-World ana motor (lisans kontrolü askıda — lisans geçmezse alternatif)
- SigLIP atmosfer / sahne skorlama
- Sahne başına 2-5 keyframe + ek sampling kuralları (motion-spike, OCR değişim anı)
- Kontrollü tag sözlüğü v0.1 (environment / event / object / people / action / visual_condition)
- Logo: referans logo kütüphanesi + SigLIP similarity + sabit watermark ROI

**Kabul kriteri:**
- TRT domain tagleri (camii, minare, kürsü, bayrak, mikrofon vb.) için %80+ precision
- Action tag güvenilirlik notu (single keyframe yetersizse motion analysis adayı)
- Logo TRT watermark için %99+ detection
- Sahne tag voting kuralı sözleşmeye uygun (frame skorları evidence içinde)

**Bağımlılıklar:** Tag sözlüğü v0.1 onayı (ayrı karar gerekir).

---

### v0.4 — Face Recognition dikey dilim

**Neden dördüncü:** Face Recognition önem skoru ASR speaker overlap + KJ etiketi sinyallerine yaslanır. ASR ve OCR/KJ olmadan önem sıralaması gevşek olur.

**Kapsam:**
- SCRFD detector (InsightFace `buffalo_l`)
- ArcFace embedding
- ByteTrack tracker (yedek BoT-SORT)
- HDBSCAN clustering
- pgvector kişi bankası
- Önem kovaları: yüksek / orta / düşük (override toggle ile)
- Face quality gate (min height, blur, pose, occlusion, track duration)
- Banka seed + review akışı

**Kabul kriteri:**
- Test setinde önemli kişi kaçırma oranı < %5
- Önemsiz kişi review gürültüsü < %20
- Face match false positive < %2 (lisans / KVKK koşullarına bağlı)

**Bağımlılıklar:**
- InsightFace / buffalo_l lisans doğrulaması (henüz yapılmadı).
- KVKK biometric retention politikası taslağı.
- Audit log altyapısı.

**Film özel kuralı:** Filmde face identification kapalı. Yalnızca "yüz var" event'i tutulur.

---

### v0.5 — Timeline birleşimi

**Neden son dikey dilim:** Modüllerin ayrı ayrı çalışmasından, ortak omurgaya bağlanmasına geçiş. Master plan'ın temel iddialarından biri (timeline her şeyin merkezi); bu dilim olmadan modüller "ayrı evrenlerde" kalır.

**Kapsam:**
- Tüm modül çıktılarının `media_id` altında birleşmesi
- Cross-module candidate relation üretimi (face_matches_kj_name, speaker_overlaps_face vb.)
- Cross-module confidence ve evidence görünümü
- Search backend: transcript + tag + kişi + zaman cross-modal arama
- Review task üretimi

**Kabul kriteri:**
- 1 saatlik test videosunda en az 3 farklı modülün çıktısı timeline'da birleşik görünür
- Cross-modal arama sözleşmesi tutarlı çalışır

---

### v1.0 — MVP release

**Kapsam:**
- Tek video üzerinde **uçtan uca** analiz: ASR + OCR/KJ + Audio Activity + Song Recognition + Görsel Tag + Face + Timeline
- Review UI v1 (3 alan: Face / OCR-KJ / Song Performance)
- Face Bank yönetimi (manuel ekleme + seed)
- Basit arama: transcript + tag + kişi + zaman
- JSON primary export
- Gerçek TRT/arşiv test setiyle benchmark koşmuş ve geçmiş

**MVP'ye girmeyen (ertelendi):**
- canlı RTMP/kamera capture
- full production queue orchestration
- cross-session voice identification
- VLM tabanlı production metadata
- çoklu performans modları (Hızlı/Dengeli/Detaylı)
- gelişmiş semantic search

---

### v1.x — FilmCreditsParser

**Neden ayrı:** Master plan v5 kararı — FilmCreditsParser sistem dışı değil ama v1 production hedefi değil. v1 oturduktan sonra ayrı oturumda detaylandırılıp eklenir.

**Kapsam:**
- Akan jenerik
- Durağan jenerik
- Giriş / kapanış jeneriği
- Role dictionary TR/EN
- Cast explosion hardening
- IMDb / TMDB doğrulama
- Evidence-based JSON
- Review / quarantine

---

## 3. Paralel cepheler (sürüm değil, taşıyıcı sütun)

Bazı işler sürüme bağlanmadan paralel ilerler. Onları "cephe" olarak görüyoruz:

### Cephe A — Test set ve ground truth

- Smoke set (1 saat) → v0.1 öncesi gerekli.
- Mini set (5 saat) → v0.2-v0.5 sprintlerinde gerekli.
- v1 release set (20 saat) → v1 release öncesi gerekli.
- Sahip: geliştirici (Ç.) tek başına; aşamalı kurulur.
- 2026-05-14: MediaSpeech TR geçici ASR probu, Common Voice TR 25 yardımcı korpus olarak indirildi. Final model/eşik kararı için TRT iç transcript havuzu esas alınacak.

### Cephe B — Hukuk / lisans / KVKK

- Production aday her model benchmark'a girmeden önce lisans ön kontrolü.
- KVKK biometric retention / audit / silme taslağı v0.4 öncesi netleşmeli.
- Bu cephe avukat veya hukuk danışmanlığı gerektirir; geliştirici tek başına karar veremez.

### Cephe C — UI panel

- Güncel takip dosyası: `mutfak/10_UI_NOTLARI.md`.
- Şu an React/Vite WebUI çalışma dizini mevcut: `E:\MITAS\.claude\worktrees\wonderful-vaughan-884d20\webui\`.
- ASR WebUI ilk bağlantısı yapıldı: upload ayrı, `ASR Başlat` ayrı; `/api` proxy `localhost:8787` backend'e bağlı.
- UI, ASR modelinin kendisi değil; ASR sonucunun görsel kabuğu. API sözleşmesi değişmedikçe model/pipeline değişiklikleri UI değişikliği gerektirmez.
- Kalan sözleşme uyumsuzlukları (ID kavramları, CandidateRelation, ileri review akışları) v0.5 timeline birleşimi öncesi düzeltilmeli.

### Cephe D — Sunum / vitrin

- Şu an aktif değil (geliştirici acele kararı geri çekti).
- Geri gelirse batch demo (pre-processed video + UI gösterim) en güvenli seçenek.
- Stream demo riski yüksek; v0.4 sonrası daha gerçekçi.

### Cephe E — Üst Denetim / Evidence-Seeking Semantic Review

- ASR/OCR/metadata çıktılarının üstünde çalışan LLM/VLM destekli kontrol katmanıdır.
- Amaç otomatik "her şeyi düzeltmek" değil; özel isim, tarihsel anakronizm, OCR/ASR çelişkisi, quoted evidence ve bağlam kırığı yakalamaktır.
- Model izinli aksiyon üretir: `canonical_link_only`, `replace_suggestion`, `review_only`, `fetch_frame`, `fetch_frame_crop`, `re_ocr_crop`, `re_asr_window`, `reference_check`, `red_flag`.
- MITAS bu aksiyonlara göre kanıt toplar; model ikinci turda frame/crop/OCR/ASR/metadata paketini değerlendirir.
- İlk MVP text-only çalışır: transcript blokları → findings JSON → deterministik kapı → `normalized_entities` + `red_flags`.
- Görsel döngü sonraki adımda eklenir: timestamp → frame/crop → VLM/OCR → üst-denetim final kararı.
- Model adayları ve güncel benchmark notları: `mutfak/09_UST_DENETIM_KATMANI.md`.

---

## 4. Aday-yedek (benchmark sonucu kalır veya çıkar)

Master plan §7.4'teki "benchmark adayı / yedekte tutulan" parçalar:

- Grounding DINO (Görsel Tag yedek motor)
- RAM / Recognize Anything (sözlük genişletme aracı)
- Cross-session voice identification (v2 koşullu)
- YAMNet alternatifleri (PANNs, Essentia)
- Song Recognition ticari alternatifleri

Bunlar sürüm hedefi değil, benchmark sonrası karar verilecek parçalar.

---

## 5. Yol haritası dışı (v1'e girmeyenler — net)

Aşağıdakiler **net olarak** v1 dışıdır:

- Canlı RTMP / kamera capture
- Live stream analiz
- Speaker / Voice Enrollment / Voice Profile (master plan §2.6 ile kapatıldı)
- VLM tabanlı production metadata motoru
- Cross-session voice identification
- Filmde face identification (jenerik OCR + IMDb/TMDB ile çözülür)
- Hızlı / Dengeli / Detaylı / Deep çoklu modlar
- Burned-in subtitle extraction

---

## 6. Sıralama nasıl revize edilir

Eğer bir sürümde takılırsak ve diğer sürüme geçmek mantıklı görünüyorsa **otomatik geçilmez**:

1. Takılan noktanın gerekçesi yazılır (`06_KARARLAR_GUNLUGU.md`).
2. Alternatif yollar tartışılır (Fırtına Alanı).
3. Karar yazılır.
4. Yol haritası bu dosyada güncellenir (eski sürüm hedefi üstü çizili, yeni satır eklenir).

Sürüm sırasını sallamak büyük karardır.

---

## 7. Sunum konusu

Sunum (GMY) için baskı zamanlı olarak geri çekildi. axle.ai bağlamı hâlâ var ama "demo yetiştir" kararı geri alındı.

Sunum geri gelirse: v0.1 ASR dikey dilim hazırsa, UI panel ile birlikte "ASR çalışıyor + UI vizyonu" sunumu doğal seçenektir. Stream + face takip showcase'i ayrıca yedek demo cephesi (Cephe D) altında durur.

---

## 8. Bir cümle ile

ASR → OCR/Müzik → Görsel Tag → Face → Timeline → MVP. Her dilim oturmadan diğerine geçmem.
