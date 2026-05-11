# 05 — AKTİF GÖREV

> Son güncelleme: 2026-05-11
> Son değişen bölüm: ASR v0.1 Pyannote diarization entegrasyonu

Bu dosya **şu an aktif olarak üzerinde çalışılan sprinttir**. Her sprint biterken arşivlenir veya tamamen yeniden yazılır. Genellikle tek bir sürümün dikey dilimine odaklanır.

---

## 1. Aktif sürüm

**v0.1 — ASR dikey dilim**

Hedef: ASR pipeline'ını dürüstçe, smoke test edilebilir şekilde uçtan uca ayağa kaldırmak. Streaming değil, batch. Tek bir Türkçe TRT örneği üzerinde JSON çıktı üretmek.

---

## 2. Sprint çerçevesi

| Madde | Karar |
|---|---|
| Sürüm | v0.1 |
| Hedef video | 1-2 dakikalık net Türkçe TRT haber kesiti (henüz seçilmedi) |
| Backend cephe | Henüz açılmadı |
| UI cephe | Şu sprintte dokunulmuyor |
| Çalışma venv'i | `asr` — birleşik ASR/STT runtime |
| Ana motor | faster-whisper large-v3 |
| Ek motor (alignment) | WhisperX `alignment` venv'de; subprocess sleeve + word-level smoke yeşil |
| Diarization | pyannote — v1 kapsamında zorunlu bileşen, kalite eşikli uygulanır (Karar 15) |
| Denoise | DeepFilterNet `denoise` venv'de; subprocess sleeve + synthetic smoke yeşil |

---

## 3. Sprint öncesi açık kararlar (önce bunlar)

Sprint kodlamaya başlamadan **çözülmesi gereken** kararlar:

### 3.1 Hangi venv'de koşacak?

- `asr`: faster-whisper + silero-vad + pyannote + FastAPI/uvicorn/websockets var.
- `alignment`: WhisperX word-level alignment sleeve.
- `denoise`: DeepFilterNet denoise sleeve.
- `stt`: legacy; `legacy_stt_venv`, `deprecated_as_primary_runtime`, `do_not_delete_yet`.

Demo cephesi şu an aktif değil. Canlı transcript gerekirse bu artık `ASR > streaming_transcription` alt modu olarak `asr` venv içinde çalışır.

**Karar:** `asr` venv seçildi.

### 3.2 WhisperX kurulsun mu?

faster-whisper segment-level timestamp veriyor. Word-level alignment için WhisperX gerekiyor. Alternatif: stable-ts veya whisper-timestamped.

WhisperX `asr` venv'e kurulmaz; `alignment` venv'de kalır. ASR pipeline ona dosya/JSON tabanlı subprocess sleeve ile konuşur.

**Karar:** WhisperX v0.1 hazırlığında `alignment` venv'de smoke edildi. Word-level timestamp kapsamı v0.1 kalite raporunda `alignment_success` ve `word timestamp coverage` olarak yer alabilir.

### 3.3 Hedef test videosu

Hazırlık smoke'ları için `E:\MITAS\testklipler\erd_test_sound.wav` kullanıldı. v0.1 pipeline smoke için hâlâ 1-2 dakikalık net Türkçe TRT video kesiti seçilmeli.

**Karar:** Hazırlık ses smoke malzemesi var; sprint hedef videosu hâlâ geliştirici seçiminde.

### 3.4 ASR kalite raporu kapsamı

Master plan §2.1'de ASR kalite raporu zorunlu. İçeriği:

- word timestamp coverage
- alignment success
- VAD speech ratio
- diarization durumu
- hata bayrakları

Word timestamp coverage WhisperX yoksa "uygulanmadı" yazılır. Yine de raporlama disiplini sprintin parçasıdır.

**Karar:** Rapor yapısı `core/schemas/` altında zaten var (`module_run.py` ve `evidence.py`). Yeni schema gerekmez. Mevcut sözleşmeye yaslanılır.

---

## 4. Alt görevler

Sıralı çalışma adımları. Her adım sonunda **commit + bu dosyaya işaretleme**.

### 4.1 Sprint öncesi (kodlamadan önce)

- [x] **3.1 venv kararı** — `asr` venv seçildi; STT legacy olarak işaretlendi.
- [x] **3.2 WhisperX kararı** — `alignment` venv'de kalır; subprocess sleeve ile çağrılır.
- [x] **3.3 Hazırlık smoke ses malzemesi** — `E:\MITAS\testklipler\erd_test_sound.wav` kullanıldı. Sprint hedef videosu ayrıca seçilecek.
- [ ] **3.4 Sprint dosya yapısı** — proje ağacının neresinde ASR pipeline kodu duracak? (`core/pipelines/asr/` öneri)

### 4.1A Sprint öncesi runtime hazırlığı

- [x] **FFmpeg full-shared** — Gyan 8.1.1 full-shared PATH'te, shared DLL'ler erişilebilir.
- [x] **Torchcodec smoke** — `asr` decode yeşil; `alignment` torchcodec dormant kabul edildi.
- [x] **Denoise sleeve** — `venvs/denoise` kuruldu, `pip check` temiz, DeepFilterNet3 synthetic smoke yeşil.
- [x] **WhisperX alignment smoke** — word-level alignment JSON üretildi.
- [x] **large-v3 cache/offline smoke** — model lokal cache'e alındı, offline transcribe smoke ağ denemesi olmadan geçti.

### 4.2 Sprint kodlama adımları

- [x] **A. ffmpeg audio extract** — video → 16khz mono wav. Tek fonksiyon, tek test.
- [x] **B. Silero VAD entegrasyonu** — wav → konuşma segmentleri (yine tek fonksiyon).
- [x] **C. faster-whisper transcribe** — VAD segmentleri → segment-level transcript.
- [x] **D. Pyannote diarization** — wav + transcript → speaker_id. v1 kapsamında zorunlu bileşen; güven eşiği altında speaker_id = null yazılır (Karar 15).
- [ ] **E. Schema'ya bağlama** — çıktı `TimelineEvent` ve `ModuleRun` sözleşmesine uyar.
- [ ] **F. Kalite raporu** — `module_run` içine ASR kalite metrikleri yazılır.
- [ ] **G. Smoke test** — `tests/test_asr_v0_1_smoke.py` veya benzeri.
- [ ] **H. Output JSON** — `outputs/asr_v0_1_demo.json` üretilir, gözle doğrulanır.

### 4.3 Sprint sonu (kabul)

- [ ] **I. Master plan §2.1 ile karşılaştırma** — eksik veya sapan kalem var mı?
- [ ] **J. `06_KARARLAR_GUNLUGU.md`'ye sprint sonu özeti** — neyi seçtik, neyi erteledik?
- [ ] **K. `03_GUNCEL_DURUM.md`'i güncelle** — yapılanlar / henüz yapılmayanlar tablosu.
- [ ] **L. v0.1 demo raporu** — `docs/SPRINT_4_ASR_V0_1_DONE.md` veya benzeri.

---

## 5. Bu sprintte dokunulmayacak şeyler

Sıkışırsak kapsamı genişletme cazibesi olur. **Bunlar v0.1 dışındadır:**

- ❌ FastAPI / WebSocket backend
- ❌ Streaming ASR (chunk push)
- ❌ Frontend
- ❌ Face detection
- ❌ OCR
- ❌ Visual tag
- ❌ Timeline merge
- ❌ Review UI
- ❌ UI panel düzeltmeleri

Bu liste **sözleşmedir**. Cazip görünse bile dokunmuyoruz; v0.1'i kirletmemek için.

---

## 6. Riskler ve dikkat noktaları

- **WhisperX kararı kararsız kalırsa sprint uzar.** Erken cevaplanmalı.
- **DeepFilterNet'in eski TRT arşivinde fayda/zarar dengesi belirsiz.** Sprint sırasında raw vs denoised karşılaştırma kısa bir alt görev olabilir; smoke aşamasında dürüst kalmak şart.
- **pyannote yavaş çalışıyor olabilir RTX 3090'da.** İlk koşumda timing ölçülür.
- **faster-whisper Türkçe karakter ı/i karmaşası.** Smoke test çıktısında dikkatlice kontrol edilir; gerekirse post-processing kuralı eklenir.

---

## 7. Bir sonraki adım (şu an, somut)

Aşağıdakiler **sırayla** yapılır:

1. Geliştirici, bu dosyadaki §3 kararlarını okur ve LLM ile konuşmaya başlar.
2. Üç karar verilir: venv, WhisperX, test video.
3. Kararlar `06_KARARLAR_GUNLUGU.md`'ye yazılır.
4. Sprint kodlama §4.2'den başlar — sıralı, tek adım, her adımdan sonra commit.

**Hatırlatma:** Sormadan kod yok. Her kodlama adımı LLM ile "şunu kodlayalım mı?" diye onaylanır.

---

## 8. Aktif sprint bittiğinde

Bu dosya sıfırlanır ve **v0.2 — OCR/KJ + Müzik segment** sprinti için yeniden yazılır. Eski v0.1 içeriği `docs/SPRINT_4_ASR_V0_1_DONE.md` arşiv dosyasına taşınır.
