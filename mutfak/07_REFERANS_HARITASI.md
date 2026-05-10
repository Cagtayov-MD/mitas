# 07 — REFERANS HARİTASI

> Son güncelleme: 2026-05-11
> Son değişen bölüm: test klip envanteri ve lokal git

Bu dosya MITAS projesindeki **tüm önemli dosyaların ve klasörlerin haritasıdır**. Hangi soruya hangi dosyada cevap aranır, hangi karar nereye yazılır. LLM oturumu açan bir asistanın "şu dosyaya bak" diyebilmesi için gerekli rehber.

---

## 1. Kök dizin haritası

E:\MITAS altında ana yerleşim:

```
E:\MITAS\
├── mutfak/                ← Bu klasör (operasyonel beyin)
├── core/                  ← Python core kodu
│   ├── jobs/              ← Job runner skeleton
│   └── schemas/           ← Pydantic schemas
├── schemas/               ← JSON Schema export'ları
├── tests/                 ← 47 test dosyası
├── docs/                  ← 22 sprint/denetim raporu
├── outputs/               ← 34 JSON output raporu
├── scripts/               ← 21 setup/inspect script
├── requirements/          ← Modül başı requirements.txt
├── locks/                 ← Her venv için freeze + inspect
├── benchmark_templates/   ← Benchmark YAML şablonları
├── models/                ← Model cache (asr/faster-whisper)
├── cache/                 ← Genel cache (1302 öğe)
├── venvs/                 ← modüler venv'ler
├── testklipler/           ← Ham test video/ses havuzu (gitignore)
├── tmp/                   ← Kurulum geçici dosyaları
├── MITAS_Master_Plan_Denetimli_v5.md
├── MITAS_Uygulama_Plani_v1.md
├── model_manifest.yaml
└── benchmark_registry.yaml
```

---

## 2. Hangi soruya hangi dosya cevap verir

### "MITAS nedir?"

→ `mutfak/01_PROJE_VIZYON.md`

### "Şu an ne yapıyoruz?"

→ `mutfak/05_AKTIF_GOREV.md`

### "Geçen sefer ne karara varmıştık?"

→ `mutfak/06_KARARLAR_GUNLUGU.md`

### "Sırada ne var?"

→ `mutfak/04_YOL_HARITASI.md`

### "Şu an hazır olan kod nedir?"

→ `mutfak/03_GUNCEL_DURUM.md` → §2 Hazır altyapı bölümü.
→ Detaylı: `core/` klasörü direkt okunur.

### "ASR kullanımı nasıl olacak?"

→ `MITAS_Master_Plan_Denetimli_v5.md` §2.1
→ `docs/MITAS_ASR_Torch_Env_Lock_v1.md`
→ `docs/MITAS_Faster_Whisper_Env_Lock_NoDownload_Guard_v1.md`

### "Hangi venv'de hangi paket var?"

→ `mutfak/03_GUNCEL_DURUM.md` §3 venv envanteri tablosu.
→ Detaylı: `locks/{venv}.inspect.json`

### "Schema şu alan nasıl?"

→ `core/schemas/{modul}.py` (Pydantic kaynak)
→ `schemas/{modul}.schema.json` (JSON Schema export)

### "Bu modülü test eden yer neresi?"

→ `tests/test_{modul}.py`

### "Bu işin lisans durumu ne?"

→ `_proje_takip/06_KARARLAR_GUNLUGU.md` → Açık konular O7
→ `MITAS_Master_Plan_Denetimli_v5.md` §0.3.15

### "UI panel nerede, durumu ne?"

→ Ayrı zip dosyası: **Medya_Yapay_Zeka_Kontrol_Paneli.zip** (geliştirici dağıtımı)
→ Durum + sapma listesi: `mutfak/03_GUNCEL_DURUM.md` §8

### "Test klipleri nerede, hangisi ne için?"

→ `mutfak/08_TEST_KLIPLER.md`
→ Ham dosyalar: `E:\MITAS\testklipler\`

### "LLM ile çalışırken nasıl davranılır?"

→ `_proje_takip/02_CALISMA_DISIPLINI.md` §5

---

## 3. Ana doküman dosyaları (kök dizinde)

### `MITAS_Master_Plan_Denetimli_v5.md`

**Ne içerir:** Tüm teknik kararların kaynağı. Modüller, motorlar, kuralları, sözleşmeleri.
**Hangi durumda bakılır:** Teknik bir kararın gerekçesi soruşturulurken. Bu klasör bir karar verirken çelişki tespit ederse master plan kazanır (teknik tarafta).
**Güncelleme:** Büyük değişiklikler için yeni sürüm (v6 vb.). Küçük değişiklikler için `_proje_takip/06_KARARLAR_GUNLUGU.md`'ye notlanır.

### `MITAS_Uygulama_Plani_v1.md`

**Ne içerir:** Sprint detayları ve uygulama sıralaması.
**Hangi durumda bakılır:** Bir sprint kapsamı netleştirilirken.

### `model_manifest.yaml`

**Ne içerir:** Tüm modeller için manifest. Her modül için hangi model, hangi versiyon, hangi cache yolu.
**Hangi durumda bakılır:** Model değişikliği veya kurulum check'i yapılırken.

### `benchmark_registry.yaml`

**Ne içerir:** Benchmark sıralaması, sahibi, eşikleri (taslak).
**Hangi durumda bakılır:** Benchmark sprintine geçilirken.

---

## 4. `core/` klasörü

```
core/
├── jobs/
│   ├── __init__.py
│   ├── errors.py          ← Job hata tipleri
│   ├── repository.py      ← DB job kayıt katmanı
│   ├── step_runner.py     ← Pipeline adımları
│   └── worker.py          ← Background worker
└── schemas/
    ├── __init__.py
    ├── candidate_relation.py   ← Modüller arası aday ilişki
    ├── common.py               ← Ortak alan tipleri
    ├── evidence.py             ← Evidence sözleşmesi
    ├── job_run.py              ← job_runs DB tablosu modeli
    ├── media.py                ← MediaItem
    ├── module_run.py           ← Modül çalışma kaydı (ASR rapor vb.)
    └── timeline.py             ← TimelineEvent
```

**Pipeline kodu nereye gelecek?** Henüz yok. Öneri: `core/pipelines/asr/`, `core/pipelines/face/` gibi alt klasörler. Sprint başında karar verilir.

---

## 5. `schemas/` klasörü (JSON Schema)

`core/schemas/` Pydantic kaynağının JSON Schema export'larıdır. Frontend / external entegrasyon için tüketilir.

- `candidate_relation.schema.json`
- `evidence.schema.json`
- `job_run.schema.json`
- `media_item.schema.json`
- `module_run.schema.json`
- `timeline_event.schema.json`

Pydantic modeli değişince `scripts/export_json_schema.py` ile yeniden export edilir.

---

## 6. `tests/` klasörü

47 test dosyası. Ana kategoriler:

- `test_schema_*.py` — Pydantic + JSON Schema testleri
- `test_job_*.py` — Job runner testleri (retry, partial, repository)
- `test_*_smoke_report.py` — kurulum sonrası smoke raporları
- `test_*_dry.py` — dry run validasyon testleri

Yeni test yazılırken aynı naming convention sürdürülür.

---

## 7. `docs/` klasörü — 22 doküman

Sıralı liste (alfabetik):

| Dosya | Ne için |
|---|---|
| `MITAS_3_5_Karar_Dokumanlari_Denetim_Raporu.md` | 3. ve 5. denetim raporu birleşimi |
| `MITAS_ASR_Model_Cache_NoInternet_Strategy_v1.md` | İnternetsiz ASR model cache stratejisi |
| `MITAS_ASR_Torch_Env_Lock_v1.md` | ASR torch env lock raporu |
| `MITAS_Benchmark_Plani_v1.md` | Benchmark planı v1 |
| `MITAS_Environment_Lock_Health_Check_v1.md` | Env lock sağlık check'i |
| `MITAS_Faster_Whisper_Env_Lock_NoDownload_Guard_v1.md` | faster-whisper download guard |
| `MITAS_Faster_Whisper_Import_Smoke_v1.md` | faster-whisper smoke test raporu |
| `MITAS_GPU_CUDA_Driver_Kesfi_v1.md` | GPU/CUDA driver keşfi |
| `MITAS_Karar_Denetim_Checklist_v1.md` | Karar denetim checklist |
| `MITAS_Lightweight_Paket_Kurulum_Raporu_v1.md` | Hafif paket kurulum raporu |
| `MITAS_Model_Env_Inventory_v1.md` | Model env envanteri |
| `MITAS_Model_Manifest_ve_Smoke_Test_Plani_v1.md` | Model manifest + smoke plan |
| `MITAS_Model_Smoke_Test_Raporlama_v1.md` | Smoke test raporlama |
| `MITAS_P1_Blocker_ve_Mimari_Duzeltmeler_v1.md` | P1 blocker'lar ve mimari düzeltmeler |
| `MITAS_Pip_Dryrun_Raporlama_v1.md` | Pip dry run raporlama |
| `MITAS_Profile_Routing_Kaba_Kararlar_v1.md` | Profil routing kaba kararlar |
| `MITAS_Requirements_Denetim_ve_Kurulum_Sirasi_v1.md` | Requirements denetim + kurulum sırası |
| `MITAS_Requirements_Taslaklari_v1.md` | Requirements taslakları |
| `MITAS_Torch_CUDA_ASR_Smoke_v1.md` | Torch CUDA ASR smoke |
| `SPRINT_1_CORE_SCHEMA_DONE.md` | Sprint 1 raporu (schema) |
| `SPRINT_2_JOB_WORKER_DONE.md` | Sprint 2 raporu (job worker) |
| `SPRINT_3_BENCHMARK_PLAN_DONE.md` | Sprint 3 raporu (benchmark plan) |

Yeni sprint biterken `SPRINT_N_{baslik}_DONE.md` formatında dosya eklenir.

---

## 8. `outputs/` klasörü — 34 JSON raporu

Kurulum / smoke / env lock / pip dryrun çıktıları. Her doküman karşılığında bir JSON. Audit ve geri dönüş için.

Önemli olanlar:

- `asr_emergency_*` — acil ASR transcribe çıktıları
- `pip_dryrun_*` — paket kurulum dry run'ları
- `model_*_report` — model smoke test raporları
- `gpu_cuda_inventory_report.json` — GPU/CUDA envanteri
- `env_lock_health_report.json` — env lock sağlık raporu

---

## 9. `scripts/` klasörü — 21 setup script

Geliştirme / kurulum / inspect script'leri. Çalıştırılabilir.

Kategori:

| Kategori | Script |
|---|---|
| Smoke/Emergency | `asr_emergency_transcribe.py`, `asr_pyannote_pipeline.py` |
| Schema export | `export_json_schema.py` |
| Inventory | `inspect_gpu_cuda.py`, `inspect_model_envs.py` |
| Install | `install_faster_whisper_smoke.py`, `install_lightweight_packages.py`, `install_torch_cuda_asr.py` |
| Lock | `lock_and_check_envs.py`, `lock_asr_torch_env.py`, `lock_faster_whisper_env.py` |
| Run | `run_model_smoke_tests.py`, `run_pip_dryrun_reports.py` |
| Validate | `validate_benchmark_yaml.py`, `validate_model_manifest.py` |

---

## 10. `requirements/` klasörü

Modül başı requirements.txt:

- `asr.txt`
- `audio.txt`
- `face.txt`
- `ocr.txt`
- `stt.txt` (legacy)
- `tag.txt`
- `visual.txt`

Her venv kendi requirements'ından kurulur. Lock dosyaları `locks/{venv}.freeze.txt` altında.

---

## 11. `locks/` klasörü

Her venv için iki dosya:

- `{venv}.freeze.txt` — `pip freeze` çıktısı
- `{venv}.inspect.json` — yapılandırılmış envanter (paket isimleri + versiyonlar JSON formatında)

8 venv × 2 = 16 dosya. Şu an mevcut olanlar:

- `asr.faster_whisper.freeze.txt` / `.inspect.json`
- `asr.freeze.txt` / `.inspect.json`
- `asr.torch.freeze.txt` / `.inspect.json`
- `audio.freeze.txt` / `.inspect.json`
- `core.freeze.txt` / `.inspect.json`
- `face.freeze.txt` / `.inspect.json`
- `ocr.freeze.txt` / `.inspect.json`
- `stt.freeze.txt` / `.inspect.json` (legacy)
- `tag.freeze.txt` / `.inspect.json`
- `visual.freeze.txt` / `.inspect.json`

---

## 12. `benchmark_templates/` klasörü

5 YAML şablon:

- `asr_benchmark.yaml`
- `audio_activity_benchmark.yaml`
- `face_benchmark.yaml`
- `ocr_kj_benchmark.yaml`
- `visual_tag_benchmark.yaml`

Her sprint kabul kriterini bu şablonlar tutar.

---

## 13. `models/` klasörü

Model cache. Şu an sadece:

```
models/
└── asr/
    └── faster-whisper/
```

Diğer modüllerin modelleri ilk kullanımda buraya cache'lenir (face/buffalo_l, ocr/PaddleOCR, vb.).

---

## 14. `cache/` klasörü

Genel cache (1302 öğe). HuggingFace cache, torch hub cache, vb. Bu klasör versiyon kontrolüne **alınmaz** (.gitignore).

---

## 15. `venvs/` klasörü

7 primary venv + 1 legacy venv (258114 öğe — ağır klasör). Primary ASR/STT runtime `venvs/asr`:

- `venvs/core`
- `venvs/stt` (legacy_stt_venv / deprecated_as_primary_runtime / do_not_delete_yet)
- `venvs/asr`
- `venvs/ocr`
- `venvs/face`
- `venvs/visual`
- `venvs/audio`
- `venvs/tag`

Versiyon kontrolüne **alınmaz**.

---

## 16. UI Panel (ayrı dizin)

`Medya_Yapay_Zeka_Kontrol_Paneli/` — geliştiricinin Figma export ile oluşturduğu UI iskelet. Henüz proje dizinine entegre değil, ayrı durur.

İçindekiler:
- React + Vite + Tailwind + shadcn/ui
- `src/app/components/` — UI bileşenleri
- `src/app/mock-data.ts` — mock veri
- `guidelines/Guidelines.md` — UI guideline'ı

Düzeltme listesi: `mutfak/06_KARARLAR_GUNLUGU.md` → Açık konular O5.

---

## 16A. `testklipler/` klasörü

Ham test video/ses havuzu. Dosyalar büyük olduğu için Git'e alınmaz; envanteri `mutfak/08_TEST_KLIPLER.md` dosyasında tutulur.

İlk ASR v0.1 smoke için kısa haber adayları:
- `trt_haber (1).mp4`
- `trt_haber (2).mp4`
- `trt_haber (3).mp4`

Uzun ve zorlayıcı benchmark adayları:
- `1.mp4` — TRT tanıtımı, müzik + hızlı plan geçişleri
- `2.mp4`, `3.mp4` — Türkçe film + jenerik
- `4.mp4` — atletizm şampiyonası, İngilizce KJ ve çok branş
- `5.mp4` — belgesel

---

## 17. Dosyalar arası ilişkiler (özet diyagram)

```
PROJE VİZYONU (01)
        ↓
ÇALIŞMA DİSİPLİNİ (02) ←→ Master Plan v5
        ↓
GÜNCEL DURUM (03) ←→ docs/, outputs/, locks/, venvs/
        ↓
AKTİF GÖREV (05) ←→ core/, tests/
        ↓
YOL HARİTASI (04) ←→ Uygulama Planı v1
        ↓
KARARLAR GÜNLÜĞÜ (06) ← Master Plan §9
        ↓
REFERANS HARİTASI (07) ← Bu dosya, tüm yapı haritası
```

---

## 18. Bu dosya nasıl güncellenir

Yeni dosya / klasör / önemli artefakt eklendiğinde:

1. Hangi soruyu cevaplıyor? → §2'ye satır eklenir.
2. Hangi ana klasörde? → İlgili §'a satır eklenir.
3. Diğer dosyalarla ilişkisi nedir? → §17 diyagramına eklenir (gerekirse).

Bu dosya **proje haritasıdır**, sık güncellenmesi gerekmez. Ama eklenen her yeni dosya buraya bir kayıtla yansıtılmalıdır.
