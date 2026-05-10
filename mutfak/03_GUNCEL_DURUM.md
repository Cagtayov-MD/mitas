# 03 — GÜNCEL DURUM

> Son güncelleme: 2026-05-11
> Son değişen bölüm: ASR v0.1 hazırlık checkpoint

Bu dosya **şu an nerede olduğumuzu** anlatır. Yapılmış olanlar, eksik kalanlar, açık kararlar, riskler. Her gelişme ile güncellenir.

---

## 1. Tek paragrafta durum

Sözleşme katmanı (Pydantic + JSON Schema), job runner skeleton (worker / repository / step_runner / errors), modüler venv altyapısı (8 venv kurulu, lock'lanmış), 47 test (schema + smoke), 22 dokümantasyon (sprint / env lock / denetim raporları), 34 JSON output raporu hazır. Master plan v5 ve uygulama planı v1 yazıldı. **Üretim pipeline kodu henüz yok**: ne ASR streaming pipeline, ne face streaming pipeline, ne WebSocket bridge, ne frontend. UI panel iskelet halinde (Figma export, mock data).

Sonraki çekirdek odak: **v0.1 — ASR dikey dilim**. Düzgün şekilde ayağa kaldırılacak.

---

## 2. Hazır altyapı

### 2.1 Sözleşme katmanı (TAMAM)

`core/schemas/`:
- `candidate_relation.py`
- `common.py`
- `evidence.py`
- `job_run.py`
- `media.py`
- `module_run.py`
- `timeline.py`

`schemas/` altında JSON Schema export'ları:
- `candidate_relation.schema.json`
- `evidence.schema.json`
- `job_run.schema.json`
- `media_item.schema.json`
- `module_run.schema.json`
- `timeline_event.schema.json`

### 2.2 Job runner skeleton (TAMAM)

`core/jobs/`:
- `errors.py`
- `repository.py`
- `step_runner.py`
- `worker.py`

### 2.3 Test seti (47 test)

`tests/` altında schema testleri, job retry / partial / repository testleri, smoke testleri.

### 2.4 Dokümantasyon (22 doküman)

`docs/` altında öne çıkanlar:
- `MITAS_Master_Plan_Denetimli_v5.md` (kök dizinde)
- `MITAS_Uygulama_Plani_v1.md` (kök dizinde)
- `MITAS_3_5_Karar_Dokumanlari_Denetim_Raporu.md`
- `MITAS_ASR_Model_Cache_NoInternet_Strategy_v1.md`
- `MITAS_ASR_Torch_Env_Lock_v1.md`
- `MITAS_Benchmark_Plani_v1.md`
- `MITAS_Environment_Lock_Health_Check_v1.md`
- `MITAS_Faster_Whisper_Env_Lock_NoDownload_Guard_v1.md`
- `MITAS_Faster_Whisper_Import_Smoke_v1.md`
- `MITAS_GPU_CUDA_Driver_Kesfi_v1.md`
- `MITAS_Karar_Denetim_Checklist_v1.md`
- `MITAS_Lightweight_Paket_Kurulum_Raporu_v1.md`
- `MITAS_Model_Env_Inventory_v1.md`
- `MITAS_Model_Manifest_ve_Smoke_Test_Plani_v1.md`
- `MITAS_Model_Smoke_Test_Raporlama_v1.md`
- `MITAS_P1_Blocker_ve_Mimari_Duzeltmeler_v1.md`
- `MITAS_Pip_Dryrun_Raporlama_v1.md`
- `MITAS_Profile_Routing_Kaba_Kararlar_v1.md`
- `MITAS_Requirements_Denetim_ve_Kurulum_Sirasi_v1.md`
- `MITAS_Requirements_Taslaklari_v1.md`
- `MITAS_Torch_CUDA_ASR_Smoke_v1.md`
- `SPRINT_1_CORE_SCHEMA_DONE.md`
- `SPRINT_2_JOB_WORKER_DONE.md`
- `SPRINT_3_BENCHMARK_PLAN_DONE.md`

### 2.5 Benchmark şablonları

`benchmark_templates/`:
- `asr_benchmark.yaml`
- `audio_activity_benchmark.yaml`
- `face_benchmark.yaml`
- `ocr_kj_benchmark.yaml`
- `visual_tag_benchmark.yaml`

`benchmark_registry.yaml` kökte.

### 2.6 Output raporları (34 dosya)

`outputs/` altında kurulum / smoke / env lock / pip dryrun JSON raporları. Bunlar her bir setup adımının audit kaydıdır.

### 2.7 Setup scripts (21 script)

`scripts/` altında:
- `asr_emergency_transcribe.py`
- `asr_pyannote_pipeline.py`
- `export_json_schema.py`
- `inspect_gpu_cuda.py`
- `inspect_model_envs.py`
- `install_faster_whisper_smoke.py`
- `install_lightweight_packages.py`
- `install_torch_cuda_asr.py`
- `lock_and_check_envs.py`
- `lock_asr_torch_env.py`
- `lock_faster_whisper_env.py`
- `run_model_smoke_tests.py`
- `run_pip_dryrun_reports.py`
- `validate_benchmark_yaml.py`
- `validate_model_manifest.py`

---

## 3. venv envanteri

9 primary venv ve 1 legacy venv, her biri `venvs/` altında.

| Venv | Yol | Amaç | Ana paketler | Eksik |
|---|---|---|---|---|
| **core** | `venvs/core` | Schema/test | pydantic 2.13.4, pytest 9.0.3, PyYAML 6.0.3 | AI paketleri yok |
| **asr** | `venvs/asr` | Birleşik ASR/STT runtime | faster-whisper 1.2.1, silero-vad 6.2.1, pyannote-audio 4.0.4, librosa 0.11.0, torch+CUDA, fastapi 0.136.1, uvicorn 0.46.0, websockets 16.0, onnxruntime 1.23.2 | whisperx yok; DeepFilterNet artık primary denoise yolu değil |
| **alignment** | `venvs/alignment` | WhisperX word-level alignment sleeve | whisperx 3.8.5, torch/torchaudio 2.8.0+cu126, torchcodec 0.7.0 | torchcodec direct decode FFmpeg 8 ile uyumsuz ama alignment yolunda dormant |
| **denoise** | `venvs/denoise` | DeepFilterNet denoise sleeve | DeepFilterNet 0.5.6, DeepFilterLib 0.5.6, numpy 1.26.4, torch/torchaudio 2.8.0+cu126, soundfile 0.12.1 | Python 3.10 fallback; 3.11 sistemde yok |
| **stt** | `venvs/stt` | Legacy STT venv | legacy_stt_venv, deprecated_as_primary_runtime, do_not_delete_yet | primary runtime değil |
| **ocr** | `venvs/ocr` | OCR | oneocr 1.0.12, paddleocr 3.5.0, paddlepaddle 3.3.1, easyocr 1.7.2, pytesseract 0.3.13, opencv 4.13 | sistem `tesseract.exe` yok |
| **face** | `venvs/face` | Yüz tespit/track | insightface 0.7.3, onnxruntime-gpu 1.23.2, supervision 0.28.0, opencv 4.13, hdbscan 0.8.42, pgvector 0.4.2, torch+CUDA | fastapi yok |
| **visual** | `venvs/visual` | Görsel tag | ultralytics 8.4.48, transformers 5.8.0, scenedetect 0.7, torch+CUDA | GroundingDINO, RAM paket olarak yok |
| **audio** | `venvs/audio` | Ses sınıflandırma | tensorflow 2.21.0, tensorflow-hub 0.16.1, librosa, soundfile, pydub | torch yok (TF tabanlı) |
| **tag** | `venvs/tag` | Türkçe NLP | zeyrek 0.1.3, nltk 3.9.4, rapidfuzz 3.14.5, regex | — |

Her venv için `locks/{venv}.freeze.txt` ve `locks/{venv}.inspect.json` dosyaları mevcut.

---

## 4. Sistem araçları

| Araç | Durum | Not |
|---|---|---|
| ffmpeg | ✅ PATH'te | Gyan 8.1.1 full-shared build; torchcodec için shared DLL'ler erişilebilir |
| ffprobe | ✅ PATH'te | Gyan 8.1.1 full-shared build |
| nvidia-smi | ✅ Erişilebilir | NVIDIA driver mevcut, GPU görünür |
| fpcalc | ✅ PATH'te | Chromaprint binary (Song Recognition için) |
| tesseract | ❌ Binary yok | `pytesseract` Python paketi var ama backend olmadan kullanılamaz |
| chromaprint kütüphane | ❌ Pip paketi yok | `fpcalc` binary mevcut, bu yeterli olabilir |

GPU/CUDA durumu: `docs/MITAS_GPU_CUDA_Driver_Kesfi_v1.md` içinde kayıtlı.

---

## 5. Henüz yazılmamış olanlar

### 5.1 Üretim pipeline kodu

Hiçbir modülün gerçek pipeline kodu yok:

- ❌ ASR pipeline (orchestration: VAD → faster-whisper → WhisperX → diarization → kalite raporu)
- ❌ Face pipeline (orchestration: detector → tracker → clustering → bank lookup)
- ❌ OCR/KJ pipeline (ROI-first → OCR → temporal merge → event)
- ❌ Audio Activity Layer pipeline
- ❌ Song Recognition pipeline
- ❌ Visual Tag pipeline
- ❌ Timeline merge layer
- ❌ Review UI backend

### 5.2 Demo / showcase

- ❌ FastAPI + WebSocket backend skeleton
- ❌ Streaming ASR akışı (chunk → push)
- ❌ Streaming face tracking
- ❌ Tıkla-seç-takip showcase logic'i
- ❌ Frontend (HTML + canvas overlay)

### 5.3 Veri tarafı

- 🟡 Ham test klip havuzu var: `E:\MITAS\testklipler\` (envanter: `mutfak/08_TEST_KLIPLER.md`)
- ❌ Ground truth dosyaları
- ❌ Benchmark sprint'lerinin koşulması

### 5.4 UI

- 🟡 UI panel iskelet halinde — Figma export, mock data
- ❌ Backend bağlantısı yok
- ❌ Sözleşme uyumsuzlukları var (Bkz. `MITAS_Gorsel_Tagleme_Plani.md`'deki notlar ve dün yapılan UI eleştirisi)

---

## 6. Aktif açık kararlar

Detay: `06_KARARLAR_GUNLUGU.md`'de listelenir, burada özet:

1. **Demo backend için venv stratejisi** — canlı transcript `ASR > streaming_transcription` olarak `asr` venv içinde ele alınır; face tarafı ayrı karar bekler.
2. **Sunum hedefi** — axle.ai bağlamı nedeniyle 3-5 günde stream demo planlanmıştı; geliştirici "acele kararları geri çekiyorum, önce ASR'yi düzgün ayağa kaldırmak" dedi. Sunum hâlâ ileride ama bu klasör artık demo değil ana proje takibi.
3. **OCR motoru seçimi** — benchmark gated. OneOCR / PaddleOCR / EasyOCR / Tesseract aday. Sıralama master plan §0.3.3'te. Tesseract binary yok, fallback için kurulması gerekir.
4. **WhisperX / alignment** — karar verildi: `asr` venv'e kurulmaz, `alignment` venv'de subprocess sleeve olarak çalışır. Word-level alignment smoke yeşil.
5. **Pyannote** — `asr` venv'inde var. Torchcodec/FFmpeg hazırlığı tamamlandı; v0.1 smoke'da kullanımı sprint başlangıcında yeniden değerlendirilecek.

---

## 7. Geliştirici durumu (10 Mayıs 2026 akşamı)

- 26 saatlik tek oturum bitti (8-9 Mayıs); 15 saat uyku ile resetlendi.
- 10 Mayıs akşamı 22:00 itibarıyla yeni çalışma dönemine geçildi.
- Bundan sonraki tempo: günde 10-12 saat, gece kesin uyku.
- Bu klasör tam bu dönüm noktasında — "acele 3 günlük demo" çerçevesinden "ana projeye geri dön" çerçevesine geçişte — oluşturuldu.

---

## 8. UI panel durumu

Geliştirici dün bir UI panel iskelet zip'i paylaştı: **Medya_Yapay_Zeka_Kontrol_Paneli.zip**.

İçerik:
- React + Vite + Tailwind + shadcn/ui
- İki ana sekme: Analysis Workstation + FaceBank Builder
- Header, VideoPlayer (yüz overlay'lı), Timeline (6 track), Sidebar (Queue/Transcript/Faces/Tags/OCR/Meta/Evidence)
- Mock data ile besleniyor; backend yok.

Tespit edilen sözleşme/disiplin sapmaları:
- Mock'ta yabancı ünlü face match örnekleri (Michael Jordan) — vizyonla çelişiyor, kaldırılmalı.
- Status vocabulary master plan ile uyumsuz (approved/pending/rejected vs raw/auto/needs_review/confirmed).
- Audio Activity ve Song Performance track'leri yok.
- Speaker / Face cluster / Person ID ayrımı net değil.
- Tag review queue item'ı var (v1.1'de olmalı).
- Türkçe / İngilizce karışıklığı.
- Job status göstergesi yok.
- CandidateRelation kavramı UI'da temsil edilmiyor.

Detay sapma listesi: `06_KARARLAR_GUNLUGU.md` → UI düzeltme görevleri.

---

## 9. Risk notları

- **Tek kişi olmak:** Tüm rol tek kişide — yorgunluk birikimi en büyük risk.
- **Demo baskısı geri çekildi ama sunum gündemi hâlâ var:** Şu an karar verildi, ASR ana odak. Ama sunum geri gelirse hızlı bir batch demo (önceden işlenmiş video + UI panel'de gösterim) yedek plan olarak hazırlanabilir.
- **Lisans kontrolü askıda:** InsightFace / buffalo_l, YOLO-World, OneOCR production lisansları hâlâ doğrulanmadı.
- **KVKK retention sayıları taslak halde:** 30 gün gibi rakamlar avukatla doğrulanmadan production'a sızmamalı.

---

## 10. Şimdiki adım

ASR v0.1 hazırlık altyapısı tamamlandı: FFmpeg shared, torchcodec/asr smoke, alignment dormant teşhisi, denoise sleeve, WhisperX word-level smoke ve large-v3 offline smoke yeşil. Sonraki adım: `05_AKTIF_GOREV.md` içinde v0.1 ASR pipeline kodlamaya geçmeden hedef video ve dosya yapısı kararını kesinleştirmek.
