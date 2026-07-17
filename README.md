# MITAS — Kök Dizin Haritası

> **Amaç:** Bu dosya, `E:\MITAS` kökündeki her üst-düzey klasör ve dosyanın *ne olduğunu* tek bakışta gösterir.
> Oluşturma: 2026-07-11 (Claude, Çağatay onaylı "harita + hafif toparlama" işi).
>
> 🔒 **UYARI — YAPI KODA GÖMÜLÜDÜR.** `scripts/mitas_roots.py` içinde `PROJECT_ROOT = E:\MITAS` sabittir ve
> bu klasör adları kodda **46+ yerde** hard-code referanslıdır. 🔒 işaretli klasörleri **TAŞIMA/YENİDEN ADLANDIRMA** —
> boru hattı kırılır. Taşıma gerekirse önce tüm referanslar + `mitas_roots.py` güncellenmeli, testlerle doğrulanmalı.

---

## 1) Kod & Boru Hattı  (🔒 hepsi yük-taşıyan)

| Klasör | Ne | Boyut |
|---|---|---|
| 🔒 `core/` | Çekirdek kod: `api/` (asr_server), `jobs/`, `pipelines/`, `observability/` | ~20 MB |
| 🔒 `scripts/` | Pipeline betikleri + **runtime bağımlılıkları** (`_pipe_*.py`, `mitas_roots.py`, `mitas_pipeline.py`) | ~10 MB |
| 🔒 `model2/` | **MODEL 2** kodu (OCR ikiye bölündü): `enhancement/ llm/ ocr/ stitching/ packaging/` | küçük |
| 🔒 `webui/` | Web arayüzü (`src/ dist/ public/ node_modules/`) | ~340 MB |
| 🔒 `config/` | Konfig: `translation_router.yaml`, `.mitas_access_secret` | küçük |
| 🔒 `schemas/` | JSON şemaları (candidate_relation, evidence, job_run, media_item, module_run) | küçük |
| 🔒 `tools/` | İkili araçlar: `ffmpeg-shared/ oneocr/ audfprint/ mitas_launcher/ asr_ab/` | ~450 MB |
| `council_mcp/` | Dış konsey MCP sunucusu (`providers/ .venv/ .env`) | ~60 MB |
| `requirements/` | Alt-sistem `requirements` dosyaları (asr, audio, face, ocr, stt…) | küçük |
| `tests/` | Testler + `fixtures/ data/` | ~10 MB |

## 2) Modeller & Ortamlar

| Klasör | Ne | Boyut |
|---|---|---|
| 🔒 `models/` | Model ağırlıkları: `alignment/ asr/ denoise/ lid/ llm/ …` | **53.8 GB** |
| 🔒 `venvs/` | 18 alt-sistem sanal ortamı (ocr, asr, alignment, vlm, face, nemo…) | **73.5 GB** |
| `hf-cache/` | HuggingFace indirme cache'i (`hub/ modules/ xet/`) — 4 elenmiş VLM modeli (bake-off çöpü) temizlendi | **~0 GB** |

## 3) Üretim Verisi  (🔒 `mitas_roots.py` yazma-kökleri)

| Klasör | Ne | Boyut |
|---|---|---|
| 🔒 `Database/` | **TRT arşivi — film-başına künye/çözümleme DB'leri** (295 kayıt). `DB_ROOT`. | **168.4 GB** |
| 🔒 `Mitas Output/` | Üretim çıktı kökü (`OUT_ROOT`): `export/ muzikal_animasyon_belgesel/` | ~180 MB |
| 🔒 `outputs/` | Pipeline çalışma çıktıları + telemetri + manifests (izlenen raporlar + Temmuz aktif iş; eski scratch koşuları temizlendi) | **2.7 GB** |
| 🔒 `export/` | Export denetim kökü: `ONAYLI_KISI_TEYIT/ GERI_CEK_DENETIM/` | küçük |
| `candidate_runs/` | İP-5 candidate-izolasyon koşuları (frames_rerun, pilot_ip5) | ~1 GB |

## 4) Kaynak & Referans Veri

| Klasör | Ne | Boyut |
|---|---|---|
| `Mitas_Files/` | Kaynak metadata: `IMDB/ MitaData/ MitaData_sample*/` — pipeline okuma kaynağı | **156.4 GB** |
| `testklipler/` | Test video klipleri (`1.mp4 … 18`) | 8.9 GB |
| `Logolar/` | TRT kanal logoları (TRT 1/2/3/Afrika/Arabi…) | küçük |
| `references/` `data/` `samples/` | ASR/OCR benchmark referans & örnek verileri | küçük |
| `benchmark_templates/` | Benchmark YAML şablonları | küçük |
| `linux/` | **Win→Linux göç planı** dokümanları (00..10 + reqs) — yalnız plan | küçük |
| `locks/` | Ortam `freeze/inspect` kilit dosyaları | küçük |

## 5) Cache, Geçici & Deneysel  (üretilebilir / scratch)

| Klasör | Ne | Boyut | Not |
|---|---|---|---|
| 🔒 `cache/` | Uygulama cache'i: `duckdb/ huggingface/ web/ pip/` | 42.9 GB | `WEB_CACHE_DIR` kod-referanslı |
| `OCR-worktree/` | Deneysel OCR "mutfağı" (git'te ignored; izlenen production `.py` + `pdf-mitas/ py/ clip_pipeline100/` korundu; eski deney artıkları temizlendi) | 1.0 GB | — |
| `mutfak/` | OCR görsel/deney çalışma alanı | ~30 MB | scratch |
| `tmp/` · `.tmp/` | Geçici çalışma dosyaları | ~330 MB | `.tmp` bugün aktif |
| `_102_afis_cache/` | 102-film afiş jpg cache'i (aktif) | ~60 MB | scratch-cache |
| `backups/` | Tek yedek: `ocr_before_claude_merge_20260522` | küçük | eski |

## 6) Dokümantasyon & Oturum State

| Öğe | Ne |
|---|---|
| `docs/` | Proje dokümanları (53 öğe; MITAS_*.md planlar, ENV_VARS, FLAGS…) |
| `.git/` | Git deposu (27 GB — geçmişte büyük blob'lar var; ayrı `gc` konusu) |
| `.claude/` | Claude Code oturum durumu (`workflows/ worktrees/ settings*`) |
| `.github/` `.agents/` `.codex/` `.tedial_sessions/` | CI + ajan/oturum state |

---

## 7) Kökteki Gevşek Dosyalar  (kalanlar — hepsi kalması gerekenler)

| Dosya | Ne | Taşınabilir mi |
|---|---|---|
| `ASR_KAPALI.flag` | **ASR kalıcı kill-switch** — kod tam bu yoldan okur | 🔒 HAYIR |
| `model_manifest.yaml` | Model manifesti — ~11 script `ROOT/"model_manifest.yaml"` okur | 🔒 HAYIR |
| `benchmark_registry.yaml` | Benchmark kayıt defteri — `validate_benchmark_yaml.py` okur | 🔒 HAYIR |
| `PROFIL_KONFIG.md` | Profil→ASR aksiyon konfigi — pipeline yorumları "ile SENKRON" | 🔒 kanonik, kökte |
| `MITAS_KUNYE_KURALLARI.md` | Künye kuralları (kanonik referans) | kökte tutuldu |
| `mitas.db` | Yerel SQLite (boş/küçük) | kökte |
| `README.md` | **Bu harita** | — |

---

## 8) 2026-07-11 Temizlik Kaydı

- **Silindi (~3.36 GB):** `_KARANTINA_SIL_20260621/` (20 gün önce senin onayınla karantinaya alınan scratch/çöp) + kökteki 51 dağınık scratch/log dosyası (`_*`, `=`, eski `asr-api.codex.auth.log`) + scratch dot-klasörleri (`.pytest_cache`, `.qc_apply_tmp`, `.pytest_tmp_credit_text_qwen_source`).
- **Taşındı:** 5 planlama dokümanı → `docs/` · 3 tek-seferlik `hatice` ps1 → `scripts/`.
- **Dokunulmadı:** Tüm 🔒 üretim/kod/veri klasörleri, koda-referanslı gevşek dosyalar, `.tmp/`.
- **Kural:** Bu iş git'e commit edilmedi — inceleyip sen commit'lersin.

### 2026-07-12 — outputs/ + OCR-worktree/ derin temizlik (~217.8 GB)

- **Silindi (695 öğe / 217.8 GB):** `outputs/` içinden 524 (Mayıs-Haz. eski OCR/ASR deney koşuları: `ocr_*films_*`, `ocr_credit_experiments`, `filmtest_*`, `clips`, `webui_asr_jobs`…) + `OCR-worktree/` içinden 171 (`tester*`, `out`, `_fix*`…).
- **Ölçüt:** yalnız git-ignored (pipeline yazarı "scratch" ilan etmiş) **VE** izlenmeyen **VE** Temmuz-öncesi **VE** runtime-korumasız.
- **Korundu:** tüm izlenen dosyalar (git kanıtlı: 0 silinen tracked), tüm `.md` raporlar, **Temmuz aktif işi** (golden'lar, `system_events.jsonl`, `api_status.json`, KONTROL/İP logları), `pdf-mitas/ py/ clip_pipeline100/` (784 tracked cache/künye dosyası yerinde), `db_compose_master.py`, `_vlm_*.py`.
- **Sana bırakıldı:** `outputs/` içinde 149 "ne-ignored-ne-tracked" küçük artık (~0.3 GB) — silinmedi, kararı sende.
- **Sonuç:** `outputs/` 186→2.7 GB · `OCR-worktree/` 35→1.0 GB · **E:\MITAS 809→588 GB**. Commit edilmedi.

### 2026-07-12 — cache öksüz-avı (50.3 GB)

- **Silindi:** `hf-cache/hub/` içindeki 4 VLM modeli (MiniCPM-V-2_6, InternVL3-8B, LLaVA-NeXT-Video-7B, LocateAnything-3B) — 2 Haziran bake-off'unda indirilip **elenmiş** (kanıt: yalnız `*_probe.py`/`smoke_*.py`/`poc_*` referansları + `credit_PIPELINE_SPEC.md` "Reddedilenler: InternVL"). Production çağırmıyor, kendiliğinden geri inmez.
- **Korundu (sıcak/referanslı/değerli):** `cache/duckdb` (29 GB, aktif KB), `cache/external_datasets` (7.8 GB, referanslı ASR/MT eval korpusları: MediaSpeech + Common Voice + FLORES), `cache/web` (künye scrape cache), `cache/pip` (yeniden-inecek indirme cache'i — "geri geliyorsa silme" ilkesi).
- **İlke:** Yalnız *üretimde kullanılmayan + kendiliğinden geri gelmeyen* uçuruldu.
