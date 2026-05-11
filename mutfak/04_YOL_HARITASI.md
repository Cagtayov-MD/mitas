# 04 — YOL HARİTASI

> Son güncelleme: 2026-05-11
> Son değişen bölüm: ASR v0.1 multilingual + diarization kararları

Bu dosya MITAS'ın sürüm bazında **nereye gittiğini** anlatır. Tarih hedefleri **bilinçli olarak yazılmaz**; tek kişilik geliştirmede tarih baskısı kararları çarpıtır. Sürüm sırası ve kabul kriteri sabittir; takvim esnektir.

---

## 1. Sürüm felsefesi

- **Her sürüm bir dikey dilimdir.** Bir modülün uçtan uca çalışan halini hedefler: input → işleme → JSON çıktı → smoke test.
- **Sırayla ilerlenir, paralel açılmaz.** Bir dikey dilim oturmadan bir sonrakine geçilmez. Bu disiplin tek kişilik geliştirmede zorunludur.
- **Her sürümün benchmark eşiği vardır.** Eşik geçilmeden bir sonraki sürüme geçmek "kâğıt üzerinde yapıldı" durumudur.
- **Showcase ≠ Final analiz.** Sunum/demo amaçlı çıktılar production pipeline'a karışmaz.

---

## 2. Sürüm sırası ve gerekçesi

### v0.1 — ASR dikey dilim (AKTİF)

**Neden ilk:** ASR tüm timeline'ın zaman ekseni omurgasıdır. Face Recognition, OCR'ın temporal merge'i, Visual Tag'in sahne timing'i, hepsi ASR timeline'ı üstüne oturur. ASR çürükse her şey kayar.

**Kapsam:**
- VAD (Silero)
- faster-whisper large-v3 ana motor (`multilingual=True`, Karar 14)
- WhisperX word-level alignment (`alignment` venv'de opsiyonel; v0.1 ana pipeline dışında)
- pyannote diarization (v1 zorunlu bileşen; eşik geçilmezse `speaker_id = null`, Karar 15)
- diarization fail graceful degradation (`partial_success`, Karar 16)
- DeepFilterNet denoise (koşullu)
- ffmpeg audio extract
- JSON primary çıktı (segments + words)
- ASR kalite raporu (word timestamp coverage, alignment success, VAD speech ratio)

**Kabul kriteri:**
- 1 dakikalık Türkçe TRT haber kesitinde:
  - %95+ kelime doğruluğu (CER veya WER hedef şu an konulmadı, mini benchmark sonrası belirlenecek)
  - segment timestamp drift < 0.5 saniye
  - VAD speech ratio % cinsinden raporlanır
  - JSON master plan §1.2 timeline event sözleşmesine uyar

**Çıktı dosyası:** `outputs/asr_v0_1_demo.json` (örnek).

**Eksiklikler / risk noktaları:**
- WhisperX kurulu değil; karar verilecek (kursak mı, fallback'e gidelim mi).
- ASR pipeline `venvs/asr` içinde koşacak; canlı transcript `ASR > streaming_transcription` alt modudur.
- DeepFilterNet'in eski TRT arşivinde faydalı mı zararlı mı bilinmiyor; benchmark gerekir.

---

### v0.2 — OCR/KJ + Müzik Segment dikey dilim

**Neden ikinci:** Müzik programı analizi MITAS'ın yüksek değer üreten parçası; KJ + ASR + audio activity birleşimi axle.ai'de yok. Ayrıca KJ okuma metadata için kişi kimliği önerisinin ana kanalı (Face Recognition'dan önce).

**Kapsam:**
- PaddleOCR / PP-OCRv5 multilingual aday (benchmark sonrası kesinleşir)
- ROI-first OCR akışı (bottom_band → center_lower → full_frame_fallback)
- Temporal merge (frame-frame aynı KJ'yi tek event'e birleştirme)
- `screen_text` event üretimi
- YAMNet veya benzeri Audio Activity Layer (speech / music / applause / silence)
- Chromaprint + AcoustID veya local fingerprint DB
- `song_performance` event üretimi (KJ + ASR + audio_activity + fingerprint birleşimi)

**Kabul kriteri:**
- 1 saatlik müzik programı örneğinde:
  - en az 80% KJ kişi/şarkı adı doğru çıkarımı
  - audio activity speech/music ayrımı insan yargısıyla %90+ uyum
  - song_performance segmentlerinin start/end ±2 saniye toleransla doğru

**Bağımlılıklar:** ASR JSON'u çıktısına yaslanır (song announcement detection için).

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

### Cephe B — Hukuk / lisans / KVKK

- Production aday her model benchmark'a girmeden önce lisans ön kontrolü.
- KVKK biometric retention / audit / silme taslağı v0.4 öncesi netleşmeli.
- Bu cephe avukat veya hukuk danışmanlığı gerektirir; geliştirici tek başına karar veremez.

### Cephe C — UI panel

- Şu an Figma export iskelet + mock data.
- v1.0 ile birlikte backend bağlanır.
- Sözleşme uyumsuzlukları (status vocabulary, ID kavramları, eksik track'ler) v0.5 timeline birleşimi öncesi düzeltilmeli.

### Cephe D — Sunum / vitrin

- Şu an aktif değil (geliştirici acele kararı geri çekti).
- Geri gelirse batch demo (pre-processed video + UI gösterim) en güvenli seçenek.
- Stream demo riski yüksek; v0.4 sonrası daha gerçekçi.

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
