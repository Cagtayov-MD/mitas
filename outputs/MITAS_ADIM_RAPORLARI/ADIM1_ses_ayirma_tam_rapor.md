# MITAS Adım 1 — Köşesinden Bucağına Tam Tarif

> Belge amacı: Çağatay yarın gece bu rapora bakarsa, başka hiçbir yere bakmadan TÜM Adım 1'i (ffmpeg ile sesi mp4'ten ayırıp wav yapma) anlayabilsin. Hiçbir şey sadeleştirilmedi, hiçbir env/CLI/dal/dosya atlanmadı, skeptiklerin bulduğu eksikler "Açık sorular" bölümünde aynen korundu.

---

## 0. Yönetici özeti (5-7 cümle)

MITAS'ın Adım 1'i tek satırda şudur: bir video dosyasının (mp4/mxf/mkv/avi/mov/ts/wav) ses akışını **`ffmpeg`** çağrısıyla **16 000 Hz, mono, PCM-16 LE** WAV'a indirgemek. Bunun **tek bir** kanonik fonksiyonu yoktur; en az **dört eşdeğer giriş noktası** vardır: `scripts/mitas_pipeline.py::extract_audio` (CLI/film boru hattı), `scripts/_pipe_asr.py::_extract_clip` + `_lean_transcribe` içindeki ffmpeg (ASR subprocess, lean ve max-seconds), `core/pipelines/asr/normalize.py::normalize_audio` (core ASR; WebUI/Tedial yolu), ve `core/api/tedial/job_runner.py::_extract_analysis_clip` (Tedial kuyruk). Tüm bu yollar **aynı bundled ffmpeg ikilisini** (`E:\MITAS\tools\ffmpeg-shared\ffmpeg-8.1.1-full_build-shared\bin\ffmpeg.exe`) hedefler ve aynı altın-format kombinasyonunu üretir: `-vn -ac 1 -ar 16000 -acodec pcm_s16le` (split modunda `-ac 1` yerine `-af pan=mono|c0=c{0|1}`). Adım 1 çıktısı dosya isimleri yola göre değişir: `audio/audio16k.wav` (pipeline), `_asr_16k.wav` veya `_asr_input_clip.wav` (lean), `normalized.wav` / `normalized_L.wav` / `normalized_R.wav` (core), `analysis_clip.wav` (Tedial). Sistem genel olarak **sağlam** ama altı sessiz risk taşır: returncode kontrolünün eksikliği (extract_audio), timeout yokluğu (`normalize.py`, `transcribe.py`, `job_runner.py`, `channel_analysis.py`), `-ss` input-öncesi (fast seek) seçimi, `extract_audio`'nun film/dizi lean profilinde israf olarak koşması, sample_fmt'nin doğrulamada olup ffmpeg komutunda olmaması, ve PROMO/WAV test girdileri için ensure-eşdeğeri olmayan teşhis scriptleri. Bu altı nokta dışında zincir, OCR-worktree dahil hiçbir downstream kullanıcının Adım 1 yarısına dokunmasını gerektirmeyecek kadar tek-noktada toplanmıştır.

---

## 1. Sınır (Adım 1 ne yapar, ne YAPMAZ)

**Adım 1 NEDIR (sıkı tanım):**
- Bir video/medya konteynerinin **ilk ses akışını** (`-map 0:a:0` ya da implisit `a:0`) seçer.
- Video akışını **tamamen düşürür** (`-vn`).
- Mono'ya indirir (`-ac 1`) ya da split modunda L/R'den birini seçer (`-af pan=mono|c0=c0` / `pan=mono|c0=c1`).
- 16 000 Hz'e yeniden örnekler (`-ar 16000`).
- 16-bit little-endian PCM WAV olarak yazar (`-acodec pcm_s16le`).
- Çıktının `is_target_wav` doğrulamasını ikinci bir ffprobe ile yapar (yalnız core yolunda).
- İsteğe bağlı **kırpma** (`-ss <start> -t <dur>`) yapar — test/Tedial/max-seconds.

**Adım 1 NE YAPMAZ (eşit derecede önemli):**
- Kare/PNG **çıkarmaz** — `-vn` zorunludur. OCR-worktree dosyaları da ffmpeg çağırır AMA orada `-vf fps=…,scale=…` ile PNG kareleri çıkarılır; o **Adım 1 değil, Adım 2'dir**.
- ASR/transcript üretmez — sonraki adım yapar.
- Denoise/EQ/loudness **uygulamaz** — pcm_s16le ham çıktı.
- Çok-akışlı ses dosyalarında ikinci akışı (`a:1`, `a:2`) tüketmez — yalnız `a:0` alınır.
- Diarization yapmaz; ama core'da `diarize.py`'nin pyannote'unun yüklediği shared-DLL'leri Adım 1'in ffmpeg ikilisiyle aynı klasörden alır.
- Master-PNG, jenerik tespiti, künye OCR — hiçbirini yapmaz; ama jenerik-detect Adım 1'den **ÖNCE** koşar (mitas_pipeline.py).
- Diller arası yeniden örnekleme kalitesi konusunda anti-alias filter uygulamaz — ffmpeg'in `aresample`'ına bırakır (varsayılan SOXR-değil); `alignment_subprocess.py`'de ise `np.interp` ile dosyayı yeniden yükleyen ayrı bir kod yolu var (DÜŞÜK KALİTE, sadece prototip).

---

## 2. Tetik zincirleri (giriş noktaları — webui worker, CLI, batch, ps1 ayrı ayrı)

Toplam **8 tetik zinciri** mevcut. Hepsi sırayla:

1. **CLI doğrudan film/dizi (Adım 1 = `extract_audio`)**
   `python scripts/mitas_pipeline.py --video <mp4> --profile film`
   → `main()` → BLOK ÇÖZ (satır 1285–1407) → `extract_audio(video, clip_dir/'audio'/'audio16k.wav')` (satır 1397)
   → `ffmpeg -y -hide_banner -loglevel error -i <video> -vn -ac 1 -ar 16000 -acodec pcm_s16le <dst>`

2. **WebUI upload (Adım 1 = `normalize_audio`)**
   Frontend → `core/api/asr_server` (uvicorn 8787) → `run_asr_pipeline()` (core/pipelines/asr/pipeline.py:354)
   → `probe_audio_stream` → `decide_channel_mode` → `normalize_audio()` (core/pipelines/asr/normalize.py:110)
   → `ffmpeg -hide_banner -loglevel error -y -i <src> -map 0:a:0 -vn -ac 1 -ar 16000 -acodec pcm_s16le <normalized.wav>`

3. **Tedial kuyruğu (Adım 1 = `_extract_analysis_clip`)**
   Tedial queue → `core/api/tedial/router.py` → `job_runner.run_job(..., max_seconds=N)` (satır 91, 93)
   → `asyncio.to_thread(_extract_analysis_clip, media_path, run_dir/'analysis_clip.wav', N)` (satır 134–136)
   → `ffmpeg -y -hide_banner -loglevel error -i <input> -t <N> -vn -ac 1 -ar 16000 -acodec pcm_s16le <out>` (satır 321–347)
   → ardından `_run_asr_pipeline(..., content_profile='bulten_haber', channel_mode='auto')` (satır 229)

4. **`start_mitas.ps1` (servis kaldırma)**
   pwsh `scripts\start_mitas.ps1` → User scope env (MITAS_/ANTHROPIC_/OPENAI_) → uvicorn 8787 (`core.api.asr_server:app`) + uvicorn 8765 (`core.api.tedial.app:create_app --factory`)
   → portlar Listen → WebUI/Tedial tetikleyince yukarıdaki 2 veya 3 zinciri açar
   → ffmpeg PATH'e bu scriptte ekleNMEZ — bundled tam yol asr_server içinde kullanılır

5. **Lean film/dizi ASR yolu (Adım 1 = `_lean_transcribe` içindeki ffmpeg)**
   `mitas_pipeline.py` → `subprocess.Popen([PY_ASR, scripts/_pipe_asr.py, --input <video|wav>, --lean, --auto-language, ...])`
   → `_pipe_asr.main()` → `_lean_transcribe()` (satır 92) → src .wav değilse `ffmpeg ... -vn/-map+pan=mono ... -ar 16000 -acodec pcm_s16le → out/_asr_16k.wav` (satır 178–186)

6. **max-seconds test kırpma yolu (Adım 1 = `_extract_clip`)**
   `mitas_pipeline.py --asr-max-seconds N` → `_pipe_asr.py --max-seconds N`
   → `_extract_clip(src, out/'_asr_input_clip.wav', N)` (satır 75–83) → `ffmpeg -y -hide_banner -loglevel error -t <N> -i <src> -vn -ac 1 -ar 16000 -acodec pcm_s16le <dst>`

7. **Tedial doğrudan stream (alternatif yol)**
   `core/api/tedial/router.py::_start_tedial_ffmpeg_mp4_stream()` → ffmpeg HTTP stream → `_post_ffmpeg_stream_to_asr()` → ASR server (3. zincire gider)

8. **mitas_pipeline BLOK ASR parallel başlatma**
   `mitas_pipeline.py` → `subprocess.Popen(asr_cmd)` ile OCR bloğuyla eşzamanlı. `asr_in` seçimi:
   - `--profile film/dizi` + auto-language ⇒ `asr_in = video` (audio_path **kullanılmaz**, extract_audio israftır)
   - Sabit dil profili (haber/belgesel/muzik/stt) ⇒ `asr_in = audio_path if audio_path.exists() else video` (satır 1444)

---

## 3. Mutfak'taki karar/kural/strateji (Adım 1 ile ilişkili belgeler)

8 mutfak belgesi Adım 1'i doğrudan veya dolaylı bağlar. Hepsi:

| Belge | Bağlantı / madde |
|---|---|
| `mutfak/04_YOL_HARITASI.md` (satır 35) | v0.1 ASR dikey dilim kapsamında **"ffmpeg audio extract"** açıkça listelenmiş — roadmap'teki resmi varlık. |
| `mutfak/05_AKTIF_GOREV.md` (satır 211) | `[x] A. ffmpeg audio extract — video → 16khz mono wav. Tek fonksiyon, tek test.` — tamamlandı işaretli görev kaydı. |
| `mutfak/06_KARARLAR_GUNLUGU.md` | **Karar 35/36**: `channel_mode` varsayılanı `mono → auto`. **Karar M3**: ASR ana motoru faster-whisper large-v3. Bu kararlar Adım 1'in `channel_mode='auto'` ve `pcm_s16le` 16 kHz hedef formatını belirler. |
| `mutfak/03_GUNCEL_DURUM.md` | `core/pipelines/asr/` 19 modül, `channel_mode='auto'`, WhisperX hizalama, 5 içerik profili. Ses ayırma zinciri ve `normalize.py`'nin durumu burada yansır. |
| `mutfak/OCR-OPUS.md` (satır 851, 881) | `core/pipelines/ocr/_video_meta.py` `ffprobe duration_seconds()` helper; `FFPROBE_EXECUTABLE` env override BELGELENDI. OCR katmanı ffprobe'u Adım 1'in ikilisinden ayrı bir resolver ile bulabilir. |
| `mutfak/08_TEST_KLIPLER.md` | `channel_mode mono→auto` karar kaydı (DONE-ASR-011/Karar 36). **16 kHz mono PCM16** ses chunk yapısı (satır 447–448). Test klip isimleri `*_16000hz_mono_asr_input.wav` formatında. |
| `mutfak/10_UI_NOTLARI.md` (satır 283, 294) | **16 kHz mono PCM16** audio chunk WebSocket live STT protokolü — aynı ses formatı UI katmanında da referans alınmıştır (live STT'nin Adım 1 ile eş protokol kullandığı belgeli). |
| `mutfak/01_PROJE_VIZYON.md` | ASR modülünün "Türkçe ses → zaman damgalı transcript + diarization" tanımı. Adım 1'in nihai hedefi olan ASR'nin vizyondaki yeri. |

Mutfak kararları arasında **Adım 1'in formatını sabitleyen anahtar karar Karar 35/36'dır** (`channel_mode` default `auto`): mono varsayımı kaldırılıp stereo girişler için Pearson-korelasyon temelli otomatik karar mekanizması (Adım 1.5 sayılabilir) eklendi.

---

## 4. Dosyalar ve fonksiyonlar (kapsamlı tablo)

**Toplam 18 kod dosyası**, 14 anahtar fonksiyon, 10 env flag, 17 CLI arg taranan kapsam:

| # | Dosya | Klasör | Adım 1'deki rol | Anahtar satır |
|---|---|---|---|---|
| 1 | `scripts/mitas_pipeline.py` | scripts | Ana orkestrasyon; `extract_audio` tanım+çağrı | 50–51, 627–674, 1280, 1397, 1438–1444 |
| 2 | `scripts/_pipe_asr.py` | scripts | ASR subprocess; `_extract_clip` + `_lean_transcribe` ffmpeg | 19, 75–83, 178–186 |
| 3 | `core/pipelines/asr/normalize.py` | core | WebUI/Tedial'in resmi normalize'i | 12–14, 77–107, 110–181, 184–242 |
| 4 | `core/pipelines/asr/pipeline.py` | core | `run_asr_pipeline` orkestrasyonu, `_derive_ffprobe` | 354–440, 1065–1080, 1102 |
| 5 | `core/pipelines/asr/transcribe.py` | core | `_BUNDLED_FFMPEG`, `DEFAULT_FFMPEG_EXECUTABLE`, `extract_wav_chunk` (VAD chunk WAV'ı) | 40–41, 1253–1273 |
| 6 | `core/api/tedial/job_runner.py` | core | `_extract_analysis_clip` Tedial kırpma | 28–30, 134–136, 229, 321–347 |
| 7 | `scripts/alignment_subprocess.py` | scripts | WhisperX subprocess; DLL dizinini ekler, WAV'ı `wave`+`np.interp` ile okur | 14–21, 24–57, 95 |
| 8 | `scripts/asr_child_exit_diagnosis.py` | scripts | Tanı scripti; `ensure_input_clip` test girdi üretimi | 17–22, 84–115 |
| 9 | `scripts/real_media_smoke.py` | scripts | Gerçek-medya smoke; `extract_clip` + `probe_media` | 19–21, 108–115, 118–150, 153–197 |
| 10 | `scripts/asr_child_exit_tur3.py` | scripts | FFMPEG_BIN yalnız PATH için; ses ayırma YOK | 17–20, 24–31 |
| 11 | `core/pipelines/asr/channel_analysis.py` | core | L/R korelasyon ölçüm WAV'ları (Adım 1.5) | 63–89, 100–141, 116–138, 158–178, 222–231 |
| 12 | `core/pipelines/asr/diarize.py` | core | Yalnız DLL dizinini yükler; ffmpeg subprocess YOK | 24, 27, 62–138, 171–183 |
| 13 | `core/pipelines/ocr/_video_meta.py` | core | `duration_seconds`, ffprobe-only; FFPROBE_EXECUTABLE override | 1–64 |
| 14 | `scripts/start_mitas.ps1` | scripts | Servis kaldırma; ffmpeg PATH eklemez | 1–89 |
| 15 | `OCR-worktree/py/20260530_1744_full_pipeline.py` | OCR-worktree | Yalnız KARE çıkarır; Adım 1 YOK (kıyaslama amaçlı listeli) | 15, 65–71 |
| 16 | `OCR-worktree/py/20260530_1645_yol_runner.py` | OCR-worktree | Yalnız KARE çıkarır; Adım 1 YOK | 14, 76–83 |
| 17 | `OCR-worktree/py/20260531_0300_full_pipeline_v3.py` | OCR-worktree | ffprobe yükseklik + kare çıkarma; Adım 1 YOK | 39–42, 57–63, 213–223 |
| 18 | `OCR-worktree/py/20260530_1734_bekci_run.py` | OCR-worktree | Tek-kare grab; Adım 1 YOK | 10, 52–55 |

**Anahtar fonksiyonların satır listesi (14 adet):**

| Dosya | Fonksiyon | Rol | Satır |
|---|---|---|---|
| mitas_pipeline.py | `extract_audio` | Adım 1'in TANIM noktası | 669 |
| mitas_pipeline.py | `ffprobe_specs` | BLOK ÇÖZ ilk adım; çözünürlük/fps/süre | 627 |
| mitas_pipeline.py | `extract_window` | OCR kareleri; Adım 1 ile aynı try'da | 655 |
| _pipe_asr.py | `_extract_clip` | max-seconds test kırpımı | 75 |
| _pipe_asr.py | `_lean_transcribe` | Lean ASR yolu; kanal-seçimli WAV | 92 |
| normalize.py | `normalize_audio` | core ASR Adım 1 eşdeğeri | 110 |
| normalize.py | `probe_audio_stream` | ffprobe; codec/sample_rate/channels/sample_fmt | 77 |
| normalize.py | `_normalize_split` | Stereo split L+R | 184 |
| normalize.py | `_split_command` | `-af pan=mono|c0=c<N>` komutu | 223 |
| pipeline.py | `run_asr_pipeline` | core orkestrasyon | 354 |
| pipeline.py | `_derive_ffprobe` | ffmpeg yolundan ffprobe.exe türetme | 1102 |
| job_runner.py | `_extract_analysis_clip` | Tedial kırpma | 321 |
| job_runner.py | `_run_asr_pipeline` | Tedial ASR tetikleyici | 229 |
| channel_analysis.py | `decide_channel_mode` | mono/split/auto karar | 63 |

---

## 5. ffprobe çağrısı (tam komut)

Adım 1 öncesinde **iki ayrı ffprobe çağrısı** mevcuttur, farklı dosyalarda farklı amaçlarla:

**5a. `mitas_pipeline.py::ffprobe_specs` (satır 627–652):**
```
ffprobe -v error \
  -select_streams v:0 \
  -show_entries stream=width,height,r_frame_rate \
  -show_entries format=duration \
  -of json <video>
```
- Timeout: **120 s**.
- Fail-safe: exception ⇒ `('—', '—', '—', 0.0)` döner. Pipeline durmaz.
- ffprobe binary: `FFPROBE = E:\MITAS\tools\ffmpeg-shared\…\bin\ffprobe.exe`; yoksa `'ffprobe'` PATH fallback.

**5b. `core/pipelines/asr/normalize.py::probe_audio_stream` (satır 77–107):**
```
ffprobe -v error \
  -select_streams a:0 \
  -show_entries stream=codec_name,sample_rate,channels,sample_fmt \
  -of json <dosya>
```
- Yalnızca **a:0** (ilk ses akışı) okunur; çok-akışlı dosyada `a:1`, `a:2` görmezden gelinir.
- `_run_command` ile koşar — **timeout YOK**.
- Hata: streams[0] yoksa → `AudioNormalizeError`; OSError → `AudioNormalizeError`.

**5c. `core/pipelines/ocr/_video_meta.py::duration_seconds` (satır 25–64):**
```
ffprobe -v error \
  -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 <path>
```
- Timeout: **30 s** sabit (env ile değiştirilemez).
- `FFPROBE_EXECUTABLE` env override (`_resolve_ffprobe`: env → `shutil.which('ffprobe')` → `'ffprobe'` sabit string).

**5d. `core/pipelines/asr/channel_analysis.py::_probe_duration_seconds` (satır 158–178):**
```
ffprobe -v error \
  -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 <path>
```
- `ffprobe_executable=None` ise dosyada `'ffprobe'` string varsayımı.
- Hata: AudioNormalizeError/ValueError → `None` döner (tek-pencere fallback).

---

## 6. ffmpeg ses ayırma çağrısı (TAM komut, parametre parametre)

**Kanonik komut (mitas_pipeline.py::extract_audio, satır 669–674):**

```
ffmpeg \
  -y                       # üzerine yaz, onay sorma
  -hide_banner             # FFmpeg sürüm/build banner'ı bastır
  -loglevel error          # sadece error logla (uyarılar gizli)
  -i <video>               # girdi: orijinal medya
  -vn                      # video stream yok — KARE çıkmaz
  -ac 1                    # 1 kanal (mono downmix)
  -ar 16000                # 16 000 Hz örnekleme
  -acodec pcm_s16le        # 16-bit little-endian PCM WAV
  <dst>                    # çıktı: clip_dir/audio/audio16k.wav
```

**Çeşitleme — `core/pipelines/asr/normalize.py::normalize_audio` (satır 148–166):**
```
ffmpeg -hide_banner -loglevel error -y \
  -i <kaynak> \
  -map 0:a:0 \        # ilk ses akışı (mitas_pipeline'dan tek fark)
  -vn -ac 1 -ar 16000 -acodec pcm_s16le \
  <çıktı>
```

**Çeşitleme — Stereo split (`_split_command`, satır 223–242):**
```
ffmpeg -hide_banner -loglevel error -y \
  -i <kaynak> \
  -map 0:a:0 \
  -vn \
  -af pan=mono|c0=c{0|1}   # L için c0=c0, R için c0=c1
  -ar 16000 -acodec pcm_s16le \
  <çıktı_L|R.wav>
```
**Önemli fark:** Split komutunda **`-ac 1` YOK**; `pan=mono` filtresi kanal sayısını 1 yapar. İkinci probe ile doğrulanır.

**Çeşitleme — `_pipe_asr._lean_transcribe` (satır 178–186):**
```
# Dal A: kanal-seçimli (sel dict varsa)
ffmpeg -y -hide_banner -loglevel error -i <src> \
  -map 0:a:<stream> \
  -af pan=mono|c0=c<channel> \
  -ar 16000 -acodec pcm_s16le \
  <out/_asr_16k.wav>

# Dal B: kanal seçilmemiş
ffmpeg -y -hide_banner -loglevel error -i <src> \
  -vn -ac 1 -ar 16000 -acodec pcm_s16le \
  <out/_asr_16k.wav>
```

**Çeşitleme — `_pipe_asr._extract_clip` (satır 75–83) — max-seconds:**
```
ffmpeg -y -hide_banner -loglevel error \
  -t <max_seconds> \         # önce -t (input-öncesi)
  -i <src> \
  -vn -ac 1 -ar 16000 -acodec pcm_s16le \
  <dst>
```

**Çeşitleme — `job_runner._extract_analysis_clip` (satır 321–347):**
```
ffmpeg -y -hide_banner -loglevel error \
  -i <input_path> \
  -t <max_seconds> \         # input-sonrası -t (NOT: -ss yok)
  -vn -ac 1 -ar 16000 -acodec pcm_s16le \
  <output_path=run_dir/analysis_clip.wav>
```

**Çeşitleme — `transcribe.py::extract_wav_chunk` (VAD chunk; satır 1253–1273):**
```
ffmpeg -hide_banner -loglevel error -y \
  -ss <vad_segment.start:.3f> \      # float, 3 ondalık
  -t <vad_segment.duration:.3f> \
  -i <audio_path> \                  # normalleştirilmiş wav
  -vn -ac 1 -ar 16000 -acodec pcm_s16le \
  <destination>
```
- `-ss` **input-öncesi** (fast seek, keyframe granularity).
- Bu chunk WAV'ları downstream VAD/transcribe için; Adım 1'in son ürünü değil ama aynı format mühründe.

**Çeşitleme — `channel_analysis.py` korelasyon WAV'ı (satır 116–138):**
```
ffmpeg <ffmpeg_executable> -hide_banner -loglevel error -y \
  -ss <start_time:.3f> -t <window_seconds:.3f> \
  -i <source> \
  -map 0:a:0 -vn \
  -ac 2 -ar 16000 -acodec pcm_s16le \   # STEREO! tek istisna
  <analysis_wav>
```
**Tek yer ki `-ac 2`** — L/R korelasyon ölçmek için kasıtlı stereo.

---

## 7. Env flag listesi (tablo — TÜMÜ)

| # | Env flag | Etki / yer | Varsayılan |
|---|---|---|---|
| 1 | `MITAS_ASR_TIMEOUT` | ASR subprocess timeout — mitas_pipeline.py satır 775. Adım 1'in **kendi** timeout'unu değil, ASR subprocess'inkini etkiler. | 7200 s |
| 2 | `MITAS_FFMPEG_DLL_DIR` | `alignment_subprocess.py` satır 19; Windows `os.add_dll_directory` ile DLL arama yolu. | yoksa `tools/ffmpeg-shared/.../bin` |
| 3 | `MITAS_PROJECT_ROOT` | `normalize.py` satır 19; PROJECT_ROOT tespiti. Yoksa `__file__` üst dizinlerinden `models/asr/faster-whisper` varlığı ile bulur. Bundled ffmpeg yolu buradan türer. | (yok) |
| 4 | `MITAS_ASR_FOREIGN_BEAM` | Yabancı dil large-v3 için beam size — `_pipe_asr.py` satır 166. Adım 1'i etkilemez ama lean yolda ses ayırmadan sonra kullanılır. | 1 |
| 5 | `FFPROBE_EXECUTABLE` | `core/pipelines/ocr/_video_meta.py` — ffprobe override (OCR-OPUS.md satır 881). | (env yoksa `shutil.which('ffprobe')` → `'ffprobe'`) |
| 6 | `MITAS_OCR_PYTHON` | `job_runner.py` satır 307 — OCR subprocess python yolu. Ses ayırmayı dolaylı etkiler. | venvs/ocr/Scripts/python.exe → sys.executable |
| 7 | `MITAS_SKIP_SPECIAL_GENRE` | `mitas_pipeline.py` satır 1244. 1 ise belgesel/müzikal/animasyon pipeline'ı atlanır, **ses ayırma da yapılmaz**. | 0 |
| 8 | `MITAS_JENERIK_DETECT` | Yeni 4-tip jenerik dedektörü; Adım 1 ÖNCESİNDE koşar. | 1 |
| 9 | `MITAS_CREDIT_DETECT` | Eski OpusCreditDetector fallback; Adım 1 ÖNCESİNDE koşar. | 0 (start_mitas.ps1'de override=1) |
| 10 | `USE_TF=0` / `USE_FLAX=0` | `_pipe_asr.py` satır 11–12; MMS-LID için transformers TF/Flax import engeli. Adım 1 öncesinde set edilir. | 0 |

**Mutlak yol/diğer örtük env:**
- `PATH` — `start_mitas.ps1` ffmpeg eklemez ama `real_media_smoke.py::runtime_env` ve `asr_child_exit_diagnosis.py::env_for_subprocess` ekler.
- `PYTHONIOENCODING=utf-8`, `PYTHONUTF8=1` — Windows UTF-8 zorlaması, tanı scriptlerinde.
- `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1` — ASR subprocess'e geçer, Adım 1'i etkilemez.
- `PYANNOTE_TOKEN` — diarize.py satır 26; Adım 1'i etkilemez ama aynı modül DLL'leri yönetir.

**Yok olan env (önemli):**
- `MITAS_AUDIO_TIMEOUT` — yok. `extract_audio` timeout 1800 s sabit.
- `MITAS_FFMPEG_EXECUTABLE` — yok. ffmpeg yolu yalnızca bundled exe veya 'ffmpeg' string.
- `MITAS_TARGET_SAMPLE_RATE` — yok. 16000 sabit kodlu.

---

## 8. CLI args listesi (tablo — TÜMÜ)

| # | Bayrak | Sahip | Adım 1'e etki |
|---|---|---|---|
| 1 | `--video <path>` | mitas_pipeline.py | Adım 1'in girdisi (zorunlu) |
| 2 | `--profile film|dizi|haber|belgesel|muzik|stt` | mitas_pipeline.py | film/dizi ⇒ lean+auto-language; extract_audio yine koşar ama tüketilmez |
| 3 | `--asr-max-seconds N` | mitas_pipeline.py | `_pipe_asr.py` `--max-seconds N` → `_extract_clip` ffmpeg `-t N` |
| 4 | `--no-asr` | mitas_pipeline.py | ASR atlanır; `extract_audio` BLOK ÇÖZ'da yine koşar |
| 5 | `--no-copy-source` | mitas_pipeline.py | Kaynak videoyu hub'a kopyalama (test) |
| 6 | `--input <path>` | _pipe_asr.py | video veya wav giriş (zorunlu) |
| 7 | `--out <path>` | _pipe_asr.py | çıktı dizini (zorunlu) |
| 8 | `--lean` | _pipe_asr.py | Transcript-only; ffmpeg `_lean_transcribe` içinde |
| 9 | `--max-seconds N` | _pipe_asr.py | `_extract_clip` çağrısı; ffmpeg `-t N` |
| 10 | `--auto-language` | _pipe_asr.py | MMS-LID dil tespiti; giriş .wav değilse ffmpeg `_lean_transcribe` içinde |
| 11 | `--model large-v3-turbo|large-v3` | _pipe_asr.py | Model seçimi (Adım 1 sonrası) |
| 12 | `--beam-size N` | _pipe_asr.py | faster-whisper beam (Adım 1 sonrası) |
| 13 | `--vad on|off` | _pipe_asr.py | VAD filtresi (Adım 1 sonrası) |
| 14 | `--language tr|auto|...` | _pipe_asr.py | Dil kodu |
| 15 | `--fps N` | mitas_pipeline.py | OCR kare çıkarım fps (ses ayırma etkisiz) |
| 16 | `--ocr-head N` | mitas_pipeline.py | Açılış OCR penceresi (ses ayırma etkisiz) |
| 17 | `--ocr-tail N` | mitas_pipeline.py | Kapanış OCR penceresi (ses ayırma etkisiz) |

Yardımcı/tanı:
- `real_media_smoke.py --output <path> --asr-worker <PY> <CHILD>` (Adım 1'i koşturur + ASR doğrulama)
- `asr_child_exit_diagnosis.py` (CLI argümanı yok; ensure_input_clip içinde)
- `asr_child_exit_tur3.py` (CLI argümanı yok; ses ayırma YAPMAZ)
- `alignment_subprocess.py --wav --segments --output --language --device --model-dir --local-files-only` (ses ayırma YAPMAZ, hazır WAV okur)

---

## 9. Subprocess detayları (timeout, check, encoding, stdout/stderr)

Adım 1'i koşturan tüm yerlerdeki subprocess ayarları **birbirinden farklı** — kritik bir tutarsızlık alanı:

| Yer | Wrapper | timeout | check | capture | encoding |
|---|---|---|---|---|---|
| `mitas_pipeline.run()` (satır 124–127) | subprocess.run | 3600 s default (extract_audio'da 1800 s) | (kontrol edilmez; returncode bile bakılmaz) | True | utf-8, errors='replace' |
| `_pipe_asr._extract_clip` | subprocess.run | yok | False (manuel returncode kontrolü, sonra RuntimeError) | True | (text=True örtük) |
| `_pipe_asr._lean_transcribe` ffmpeg | subprocess.run | yok | **True** (CalledProcessError) — stderr **YAKALANMAZ** | False | n/a |
| `normalize._run_command` (satır 253–263) | subprocess.run | **yok** | False, manuel AudioNormalizeError | True | utf-8, errors='replace' |
| `transcribe._run_command` (satır 1360–1370) | subprocess.run | **yok** | False, manuel AudioTranscribeError | True | utf-8, errors='replace' |
| `job_runner._extract_analysis_clip` | subprocess.run | **yok** | False, manuel RuntimeError | True | text=True |
| `channel_analysis._run_command` | subprocess.run | **yok** | False, manuel AudioNormalizeError | True | utf-8, errors='replace' |
| `_video_meta.duration_seconds` | subprocess.run | **30 s** | **True** (CalledProcessError → RuntimeError) | True | text=True |
| `mitas_pipeline.ffprobe_specs` | run() | 120 s | False | True | utf-8, errors='replace' |
| `real_media_smoke.run_command` | subprocess.run | parametrik (probe=60, extract=120) | False | True (stderr→STDOUT) | utf-8, errors='replace' |
| `asr_child_exit_diagnosis.run_command` | subprocess.run | 120 s | False | True (stderr→STDOUT) | utf-8, errors='replace' |
| `asr_child_exit_tur3.run_child` | subprocess.run | 420/700/520/240/60 s | False | True (ayrı PIPE) | utf-8, errors='replace' |

**stdout/stderr siyasası tutarsız:**
- `extract_audio`: stderr (`aerr`) `log_event`'e yazılmaz, kaybolur.
- `_lean_transcribe` ffmpeg: `check=True`, `capture_output` **YOK** — `CalledProcessError`'da yalnız "exit status N" görünür, hata gerekçesi gizlenir.
- `_extract_clip`: stderr son 500 karakteri `RuntimeError`'a yazılır (en iyi pratik).
- core modüller: stderr → AudioNormalizeError mesajı; OSError için ayrı sarmalama.

---

## 10. Hata yolları ve fallback (tüm dallar)

**A. ffmpeg binary fallback zinciri:**
1. mitas_pipeline.py: `FFMPEG.exists()` False ⇒ PATH `'ffmpeg'` (satır 671).
2. _pipe_asr.py: `str(FFMPEG) if FFMPEG.exists() else 'ffmpeg'` (satır 77, 180).
3. transcribe.py: `_BUNDLED_FFMPEG.exists()` False ⇒ `DEFAULT_FFMPEG_EXECUTABLE = 'ffmpeg'` (satır 41).
4. _video_meta.py: `FFPROBE_EXECUTABLE` env → `shutil.which('ffprobe')` → `'ffprobe'`.
5. diarize.py: bundled DLL'leri `glob('ffmpeg-*-full_build-shared/bin')` ile bulur; yoksa AudioDiarizeError.

**B. Çıktı doğrulama / cache:**
- `is_target_wav` (normalize.py satır 55–63): codec=`pcm_s16le` AND sr=16000 AND ch=1 AND sample_fmt=`s16`. Hepsi VE bağlı. Biri eksik ⇒ ffmpeg çalışır.
- `is_target_wav=True` ⇒ ffmpeg **HİÇ çağrılmaz**, `reused_input=True` (satır 133–142). Sessiz optimizasyon.
- mitas_pipeline.py `audio_path.exists() AND size>0` ⇒ ok_audio True (returncode'a bakmadan).
- `_extract_clip` cache: yok; her çağrı ezer (`-y`).
- `extract_wav_chunk` finally `chunk_path.unlink(missing_ok=True)` — `_transcribe_chunk` içinde.

**C. ASR girdi seçimi (extract_audio başarısız sonrası):**
- auto-language (film/dizi lean): `asr_in = video` (audio_path zaten kullanılmaz).
- Sabit dil: `audio_path if audio_path.exists() else video` (satır 1444). Pipeline durmaz.

**D. Jenerik detect fail-safe (Adım 1'den ÖNCE):**
- `MITAS_JENERIK_DETECT` veya `MITAS_CREDIT_DETECT` aktifse `_jenerik_detect.py`/`_credit_detect.py` koşar; exception ⇒ `log_event('credit_detect_skip')`. Ses ayırma etkilenmez.

**E. BLOK ÇÖZ genel except (mitas_pipeline.py 1404–1407):**
- `extract_audio` `TimeoutExpired` (1800 s aşımı) BURADA yakalanır; `cozumleme_failed` log'lanır, ok_audio belirsiz.

**F. channel_analysis fail-safe:**
- `_probe_duration_seconds` None ⇒ `_analysis_start_times` (0.0,) tek pencere.
- `measure_lr_correlation` correlations boş ⇒ 1.0 döner ⇒ mono kararı (sessiz `split YAPILMAZ`).
- channels<2 + auto ⇒ doğrudan mono (ffmpeg ÇAĞRISI YOK).

**G. core pipeline override:**
- `analyze_stereo_redundancy(L,R)`: stereo split auto-decided + redundant ⇒ effective_mode mono'ya override. L/R WAV'ları diskte kalır, temizlenmez (satır 469–481).

**H. _pipe_asr fallback:**
- large-v3 yüklenemezse turbo'ya düşer; detect_info['fullv3_error'] yazılır.
- `_channel_lang` import/detect hatası ⇒ language=None, downmix yoluna düşer.
- `_lang_unsupported=True` ⇒ ASR atlanır, chlang.json yazılır, os._exit(0).

**I. start_mitas.ps1 fallback:**
- User scope env yoksa default'lar set edilir (MITAS_QC2=1, MITAS_SES_DIL_KONTROL=0, ...).
- Port boşalma: max 25×200 ms = 5 s; aşılırsa **sessizce devam eder** (port-in-use riski).
- Port DOWN ⇒ uyarı basar, script hata koduyla çıkmaz.

---

## 11. Idempotency / cache (wav reuse?)

**Var:**
1. `normalize.normalize_audio`: `is_target_wav=True` ⇒ ffmpeg atlanır, `reused_input=True` döner.
2. `_normalized_filename`: hash = `sha1(input_path.resolve())[:10]` ile aynı kaynak tekrar verilirse aynı çıktı; ezilmez.
3. OCR-worktree dosyaları (Adım 1 değil): `f_*.png` cache'i; varsa ffmpeg atlanır.

**Yok:**
1. `extract_audio` (mitas_pipeline.py): cache yok; `-y` ile her seferinde ezer.
2. `_extract_clip` ve `_lean_transcribe`: cache yok.
3. `_extract_analysis_clip` (Tedial): `analysis_clip.wav` sabit isim, `-y` ile ezilir. İdempotent görünür ama log yoktur.

**İnce nokta:**
- `_normalized_filename` hash'i `Path.resolve()` üzerinden alınır. Aynı fiziksel dosyaya farklı symlink/UNC yoluyla erişilirse **farklı hash, farklı önbellek** — cache ıskalanır, disk dolar.

---

## 12. Disk yolları (wav nereye?)

| Bağlam | Çıktı yolu | Sabit/değişken |
|---|---|---|
| mitas_pipeline.py | `clip_dir / 'audio' / 'audio16k.wav'` | clip_dir değişken, dosya adı SABIT |
| _pipe_asr._extract_clip | `out / '_asr_input_clip.wav'` | SABIT |
| _pipe_asr._lean_transcribe | `out / '_asr_16k.wav'` | SABIT |
| normalize.normalize_audio (mono) | `run_dir / 'normalized.wav'` | SABIT (pipeline.materialize sonrası) |
| normalize._normalize_split | `run_dir / 'normalized_L.wav'`, `normalized_R.wav` | SABIT |
| pipeline.py 438 satır | (split + ek mono) `run_dir / 'normalized.wav'` | SABIT |
| job_runner._extract_analysis_clip | `run_dir / 'analysis_clip.wav'` | SABIT |
| transcribe.extract_wav_chunk | tempfile veya `chunk_dir / 'chunk_{vad_index:04d}_{start_ms:08d}_{end_ms:08d}.wav'` | Dinamik |
| channel_analysis (korelasyon) | TemporaryDirectory altında | Geçici |
| real_media_smoke | `outputs/real_media_smoke/{name}_20s_16000hz_mono_asr_input.wav` | Şablon |
| asr_child_exit_diagnosis | `outputs/.../{CLIP}/asr_input.wav` | Sabit |
| alignment_subprocess | (üretmez; hazır WAV okur) | n/a |

**run_dir / clip_dir nasıl belirlenir?**
- mitas_pipeline.py: hub klasörü altında film klasörü `{AD} {TRT}` deseninde (database konsolidasyon kurallarına göre).
- core pipeline: `outputs/asr/{job_id}/` altında `run_dir`.
- Tedial: `outputs/tedial/runs/{job_id}/`, media `outputs/tedial/media/`.

**Disk israfı uyarısı:**
- Split modda L+R+mono = 3 WAV diskte kalır (pipeline.py 438'deki ekstra mono).
- `analyze_stereo_redundancy` override edilirse L/R diskte unutulur (cleanup yok).
- `_normalized_filename` hash collision'sız ama symlink uyumsuz.

---

## 13. Downstream (wav'i / mp4'u kim okuyor?)

**A. ASR (transcribe):**
- `core/pipelines/asr/transcribe.py`: `normalized_audio_path`'i okur, VAD chunk'larını ondan keser (`extract_wav_chunk`).
- `_pipe_asr._lean_transcribe`: `_asr_16k.wav`'ı doğrudan faster-whisper'a verir.
- Film/dizi auto-language profilinde: `_pipe_asr` `--input <video>` ile koşar — WAV'ı okumaz, video'yu içselleştirir.

**B. Diarization:**
- `diarize.py::diarize_audio`: `probe_audio_stream` ile WAV'ın normalize olduğunu doğrular; değilse `AudioDiarizeError`. Sonra `vad.read_normalized_wav_tensor` ile `wave` modülü+torch.float32 tensor okur. **ffmpeg çağırmaz** ama bundled klasörden 4 shared DLL'i (`avcodec-*.dll`, `avformat-*.dll`, `avutil-*.dll`, `swresample-*.dll`) `os.add_dll_directory` ile yükler.

**C. WhisperX hizalama:**
- `alignment_subprocess.py::read_wav_as_16k_mono`: WAV'ı `wave` modülü ile parse eder, PCM16 zorunlu (sample_width==2 değilse ValueError). Mono değilse mean alır, 16 kHz değilse `np.interp` ile resample (anti-alias **yok** — risk).
- `whisperx.align(segments, ..., audio_numpy)` çağrısı.

**D. Channel analysis (Adım 1.5):**
- Stereo + auto modunda `decide_channel_mode` ⇒ `measure_lr_correlation` ⇒ ffmpeg ile 5×5 s pencere stereo WAV üretir, `_wav_lr_correlation` ile Pearson hesaplar. Sonuç `mono`/`split` kararı verir.

**E. OCR-worktree referansları:**
- `OCR-worktree/py/20260530_1744_full_pipeline.py`, `20260530_1645_yol_runner.py`, `20260531_0300_full_pipeline_v3.py`, `20260530_1734_bekci_run.py`: hepsi aynı bundled ffmpeg.exe yolunu sabit kullanır ama **kare çıkarır, ses ayırmaz**. OCR-worktree Adım 1'in çıktısını **OKUMAZ**; bağımsız bir prototipler kümesidir. Tek ortak nokta: bundled ffmpeg sürümü (8.1.1-full_build-shared).

**F. Tedial job → ASR:**
- `_extract_analysis_clip` çıktısı `analysis_clip.wav` ⇒ `run_asr_pipeline(input_path=analysis_clip.wav, content_profile='bulten_haber', channel_mode='auto')`. WAV `normalize_audio`'dan tekrar geçer (is_target_wav=True olduğu için aslında reused_input).

---

## 14. mp4 edge cases (no-audio, multi-track, özel codec)

**A. Ses akışı OLMAYAN video:**
- `extract_audio`: ffmpeg `-vn` ile ses arar, bulamaz ⇒ returncode>0, dst oluşmayabilir ⇒ `ok_audio=False`. `aerr` log'a girmez, neden belirsiz.
- `probe_audio_stream`: `streams[0]` yok ⇒ `IndexError` ⇒ `AudioNormalizeError`. Pipeline burada `AudioNormalizeError` re-raise ile çıkar (core); mitas_pipeline'da BLOK ÇÖZ except yakalar.
- `_extract_clip`: returncode!=0 OR dst yok ⇒ `RuntimeError(stderr[-500:])`.

**B. Çok-akışlı (multi-track) ses:**
- Hepsi `a:0` (ilk akış) alır; `a:1`, `a:2` görmezden gelinir.
- TR+orijinal-dil çift-akışlı arşiv materyalinde sessiz veri kaybı riski.
- `_lean_transcribe` kanal-seçimli dalda `-map 0:a:<stream>` parametreli ama varsayılan 0; yine de farklı stream seçilebilir (sel dict üzerinden).

**C. Özel codec (DTS, AC-3, AAC-HE, FLAC, ProRes konteyner):**
- ffmpeg 8.1.1 full-build hepsini decode eder; sorun beklenmez.
- Ancak `probe_audio_stream` `sample_fmt` döndürürse ve `pcm_s16le`'ye decode edilemezse normalize fail.
- Surround (5.1, 7.1): `-ac 1` downmix yapar; ffmpeg `pan_mono = sum/N` formülü kullanır; ortam diyaloğu netleşir ama bass kaybı olur (ASR için sorunsuz).

**D. MXF/MOV konteyner:**
- `MEDIA_FILES` listesi MXF ve TS uzantılarını dahil eder (OCR-worktree). Adım 1 tarafından `extract_audio` da aynı uzantıları kabul eder (uzantı filtresi yok, ffmpeg açabildiği her şeyi açar).

**E. WAV girdi (zaten ses):**
- `_lean_transcribe`: `src.suffix=='.wav'` ⇒ ffmpeg HİÇ çağrılmaz, src doğrudan ASR'a gider.
- `normalize_audio`: `is_target_wav=True` ⇒ reused_input.
- Test girdileri (`erd_test_sound.wav`): `real_media_smoke.extract_clip` yine ffmpeg ile 16 kHz mono PCM'e dönüştürür (lossy değil ama redundant).

**F. Boşluklu/özel-karakterli dosya adı:**
- `asr_child_exit_diagnosis.py`'de `trt_haber (1).mp4` örneği — `shell=False` olduğu için list-of-strings sorunsuz. Shell'e geçilirse tırnak gerekir.

**G. Çok uzun film (>5 saat arşiv):**
- `extract_audio` timeout 1800 s sabit — 30 dk yeterli olmayabilir; BLOK ÇÖZ except yakalar, ses YOK ile devam.
- `normalize._run_command` timeout YOK — sonsuz bloke riski.

**H. Truncated/bozuk dosya:**
- `-loglevel error` uyarıları gizler. ffmpeg success returncode 0 dönebilir ama WAV truncated olabilir. Tek koruma: core'daki ikinci `probe_audio_stream` doğrulaması.

---

## 15. Logging / metrics

**A. mitas_pipeline.py:**
- `log_event('cozumleme_completed', ses='var' if ok_audio else 'YOK', audio_ok=bool)` (satır 1398–1403).
- `log_event('cozumleme_failed', level='error')` exception dalı.
- ffmpeg `aerr` stderr **logged değil** — kaybolur.
- `log_event('credit_detect_skip')` Adım 1 öncesi fail-safe.

**B. core normalize/pipeline:**
- `module_run.json` ve `summary.json` her run_dir altına yazılır.
- AudioNormalizeError exception dalında bunlar yine yazılır, sonra exception re-raise (pipeline.py 630–662).

**C. _pipe_asr.py:**
- stdout'a tek satır JSON: `{status, runtime, detect_info, ...}`.
- detect_info içine `fullv3_error`, `_lang_unsupported`, `chlang.json` referansı yazılır.
- ffmpeg `_lean_transcribe` hatası: yalnız "exit status N" — gerekçe yok.

**D. job_runner.py:**
- queue.json güncellenir: status=failed + retry_count+1.
- exception traceback queue'ya yazılır.
- ffmpeg output: subprocess'in stdout/stderr capture edilir, RuntimeError mesajına gider.

**E. real_media_smoke.py / asr_child_exit_*:**
- JSON raporlar `outputs/real_media_smoke/report.json`, `outputs/.../asr_child_exit_*.json`.
- wav_info() Python wave modülü ile bağımsız doğrulama.
- timestamp_local **sabit kodlanmış '2026-05-11'** (smoke; bug).

**F. start_mitas.ps1:**
- `outputs/svc_8787.log` ASR server stdout (Adım 1 dahil).
- `outputs/svc_8787.err.log` ASR server stderr (ffmpeg stderr buraya gider).
- Konsole değil — başlatma sonrası bu log'a bakılmazsa Adım 1 hataları fark edilmez.

**Eksik metrikler:**
- Adım 1'in süresini ölçen explicit timer yok (sadece BLOK ÇÖZ toplam t0).
- WAV boyutu metric'i yok (`real_media_smoke` ek olarak ekler).
- ffprobe doğrulamadan sonra ham vs. işlenmiş örnekleme oranı diff yok.
- Sample peak/RMS Adım 1 sonrası ölçülmez (denoise ölçer ama ASR girişinde değil).

---

## 16. Paralel film handling

**Tek-film içi paralellik:**
- BLOK ÇÖZ tek try bloğu — `ffprobe_specs → jenerik detect → extract_window → extract_audio` SERİDİR (paralel değil).
- mitas_pipeline.py ASR ve OCR'i `subprocess.Popen` ile **eşzamanlı** başlatır (BLOK ASR parallel). Adım 1 öncesinden hazırlanır.

**Çoklu film paralelliği:**
- Mevcut sistem **seri** (2-paralel iş denemesi geri alındı — MEMORY: `2 paralel iş + VRAM`).
- VRAM hog gemma4 ~18.7 GB; iki film konkurensli denendiğinde 23.5 GB peak, OOM olmadı ama 19 GB eşik guard'ı VL'de stall yaptı (ollama eviction'ı saymıyor).
- İş `cc1f006696` commit'inde dondurulmuş halde duruyor.

**Asyncio uyumu (Tedial):**
- `_extract_analysis_clip` `asyncio.to_thread` içinde çağrılır (`job_runner.py` satır 135).
- subprocess.run timeout=None olduğu için to_thread thread'i sonsuza bloklar; **iptal mekanizması YOK**.

**Paddle asyncio import-yarışı dersi:**
- MEMORY: `project_paddle_asyncio_import_fix_20260614.md` — PaddleOCR'in background-thread `import` ana-thread asyncio import'larıyla yarışıp circular-import üretmişti.
- Adım 1'le ilgisi: `_extract_analysis_clip` lazy import ile `DEFAULT_FFMPEG_EXECUTABLE` alır (`from core.pipelines.asr.transcribe import ...`). Eğer ilk yükleme to_thread içinde olursa benzer yarış riski **teorik** olarak var.

---

## 17. Resume / recovery

**A. extract_audio resume:**
- Mevcut WAV'ın yeniden kullanılması YOK — her seferinde `-y` ile ezilir.
- BLOK ÇÖZ exception sonrası: pipeline devam eder, ASR auto-language video'ya geçer; recovery örtük.

**B. Tedial job resume:**
- `job_runner.run_job` exception ⇒ job.status='failed', retry_count+1. Queue'ya yazılır.
- `analysis_clip.wav` kısmen yazılmış olabilir; bir sonraki retry'da `-y` ile ezilir.

**C. core normalize resume:**
- `is_target_wav=True` cache: girdi zaten normalize ise reused_input ⇒ retry'da boşa iş yok.
- Aksi halde hash'li çıktı dosyası varsa **yine de override edilir** (normalize_audio her zaman koşar; cache yalnız girdi format kontrolünde).

**D. flow-queue dersi (MEMORY):**
- `project_flowqueue_local_upload_fix_20260614.md`: 532 yerel film 'upload' sanılıp `failed` yapılmıştı. Fix `'local'` kaynak tipi + restart auto-silme kaldırıldı + `queue.backup.json` yedek.
- Adım 1 açısından: Tedial job_runner queue retry sonrası `analysis_clip.wav` yeniden üretilir; eski yarım WAV korunmaz.

**E. WebUI restart dersi:**
- `project_asr_server_restart.md`: ASR kodu değişince uvicorn --reload yok, elle restart şart.
- start_mitas.ps1 portları Stop-Process Force ile keser; aktif ffmpeg child orphan kalabilir.

---

## 18. mp4 yer değişikliği (kopya mı orijinal mi?)

**A. mitas_pipeline.py:**
- `--no-copy-source` yoksa kaynak video **hub'a kopyalanır** (database konsolidasyon: `{AD} {TRT}/file_base/...`).
- `--no-copy-source` ile kopya atlanır, orijinal yol kullanılır.
- `extract_audio` her durumda hub'daki video yolunu okur (kopyalandıysa).

**B. core asr_server / WebUI:**
- Upload → temp dir → `normalize_audio` doğrudan oradan okur. Orijinal kopya YOK; user'ın diskindeki dosyaya dokunulmaz.

**C. Tedial:**
- Manifest fetch → `outputs/tedial/media/` altına indir (`_fetch_manifest` + `_download`).
- `_extract_analysis_clip` indirilmiş kopyadan koşar; orijinal Tedial sunucusunda dokunulmaz.

**D. OCR-worktree:**
- Hardcoded `E:\filmtest\aaaa` veya META JSON'ından gelen yol; **kopyalanmaz**, doğrudan okunur.

**E. Test scriptleri (asr_child_exit_diagnosis):**
- `FALLBACK_SOURCE = ROOT / 'testklipler' / 'trt_haber (1).mp4'` — orijinal dosya, kopya yok.
- ensure_input_clip 20 s'lik kırpılmış kopya üretir (`outputs/.../news_trt_haber_1_20s/asr_input.wav`).

**Genel kural:**
- Adım 1 **orijinal dosyaya yazmaz** — her zaman yeni bir WAV üretir. Girdi salt-okunur kabul edilir.
- Kaynak konum sabit kalır; mitas_pipeline hub kopyası dışında hiçbir yol kaynağı taşımaz.

---

## 19. Venv + ffmpeg binary çözümü

**Python venv'leri:**
- `venvs/asr/Scripts/python.exe`: ASR subprocess'leri (faster-whisper, whisperx, pyannote). `start_mitas.ps1`'in `$PY` değişkeni.
- `venvs/ocr/Scripts/python.exe`: OCR subprocess; `MITAS_OCR_PYTHON` env ile override.
- Global Python310: PDF testleri (MEMORY: `project_codex_regresyon_onarim_20260619.md`).
- WebUI: Vite/Node (5173); Adım 1'le ilgisiz.

**ffmpeg binary çözüm zinciri:**
1. **Bundled:** `E:\MITAS\tools\ffmpeg-shared\ffmpeg-8.1.1-full_build-shared\bin\ffmpeg.exe` (Path objesi).
2. **`.exists()` kontrolü:** True ⇒ tam yol kullan, False ⇒ `'ffmpeg'` PATH string.
3. **`DEFAULT_FFMPEG_EXECUTABLE`:** module load time'da bir kez `_BUNDLED_FFMPEG.exists()` kontrolü; runtime'da disk değişikliği yansımaz.
4. **`FFMPEG_EXECUTABLE` env yok** — yalnız parametre olarak `ffmpeg_executable=...` geçirilebilir.
5. **`MITAS_FFMPEG_DLL_DIR`:** alignment_subprocess.py için DLL dizini (Windows `os.add_dll_directory`).
6. **diarize.py:** `DEFAULT_FFMPEG_SHARED_ROOT / 'ffmpeg-*-full_build-shared/bin'` glob ile bulur, 4 DLL varlığını kontrol eder.

**ffprobe binary çözüm zinciri:**
1. **Bundled:** Aynı `bin/` dizininde `ffprobe.exe`.
2. **`_derive_ffprobe(ffmpeg_executable)`:** ffmpeg yolundan `ffmpeg.exe → ffprobe.exe` türetir (pipeline.py 1102–1108).
3. **`FFPROBE_EXECUTABLE` env:** _video_meta.py içinde override (OCR-OPUS.md satır 881).
4. **`shutil.which('ffprobe')`:** PATH fallback (_video_meta.py).
5. **Sabit `'ffprobe'` string:** son çare; FileNotFoundError → RuntimeError.

**Tutarsızlık:**
- `legacy transcribe_vad_segments` default `'ffmpeg'` (PATH); production `transcribe()` bundled. Aynı ortamda iki farklı ffmpeg sürümü çalışabilir (asimetri).

**Sürüm:**
- ffmpeg 8.1.1 — `full_build-shared` (DLL shared). MITAS'ın Windows için seçtiği build.
- diarize.py'nin pyannote'u için ZORUNLU 4 DLL: `avcodec-*.dll`, `avformat-*.dll`, `avutil-*.dll`, `swresample-*.dll`. `ffmpeg.exe`/`ffprobe.exe` shared build'de var ama diarize doğrudan bunlara bakmıyor.

---

## 20. OCR-worktree downstream referansları

OCR-worktree dosyaları **Adım 1 (ses ayırma) yapmaz** ama bundled ffmpeg yolunu sabit referans olarak kullanır:

| Dosya | Kullanım | Adım 1 ile ilişki |
|---|---|---|
| `20260530_1744_full_pipeline.py` (satır 15, 65–71) | `extract(video,s0,s1,fdir)`: `ffmpeg -y -ss ... -t ... -i ... -vf fps=5,scale=-2:480 -q:v 2 f_%05d.png` | YOK — yalnız KARE. `-vn` bile yok ama çıktı .png olduğundan ses encode edilmez. |
| `20260530_1645_yol_runner.py` (satır 14, 76–83) | Aynı kare çıkarma şablonu | YOK |
| `20260531_0300_full_pipeline_v3.py` (satır 39–42, 57–63, 213–223) | `_src_height` ile ffprobe height alır, sonra `extract_native` ile native fps=5 kare çıkarır. Fallback 480p yolu da var. | YOK — yalnız KARE+ffprobe height |
| `20260530_1734_bekci_run.py` (satır 10, 52–55) | `grab(video,t,outp)`: tek-kare PNG. `-frames:v 1 -q:v 2` | YOK |

**Önemli kıyas:**
- Sürüm aynı: `ffmpeg-8.1.1-full_build-shared`. OCR-worktree de bundled ikiliyi paylaşır.
- `-ss` **input-öncesi** (fast seek). Adım 1'deki `extract_wav_chunk` ve `channel_analysis` da input-öncesi. Tutarlı seçim (hız > doğruluk).
- OCR-worktree subprocess timeout YOK + `check=True` veya `check=False` karışık — Adım 1'in tutarsızlığını yansıtır.
- OCR-worktree → Adım 1 zinciri YOKTUR. Adım 1 → OCR de YOKTUR. İki sistem disjoint.

**MEMORY referansları:**
- `project_creditdetect_pencere_fix_20260615.md`: credit_detect'in çıkış 600 s cap'i kuyrukta jenerik kaçırıyordu — bu Adım 1'i etkilemez, OCR penceresini etkiler.
- `project_master_png_session_20260614.md`: master-PNG bayrağı arkasında ÖLÜ; Adım 1'le ilgisiz.

---

## 21. Açık sorular / belirsiz noktalar (skeptiklerin bulduğu)

> Bu liste skeptik ajanların tespit ettiği tüm eksiklikleri içerir; hiçbiri ezilmemiştir.

1. **`extract_audio` returncode kontrolsüz** (mitas_pipeline.py satır 673–674): ffmpeg sıfır-dışı returncode ile çıksa bile `dst.exists() AND size>0` ⇒ `ok_audio=True`. Kısmi/bozuk WAV sessizce kabul edilebilir.
2. **`extract_audio` `aerr` log'lanmaz**: `cozumleme_completed` event'ine girmez. Root-cause forensiği zor.
3. **`extract_audio` timeout 1800 s SABIT** — `MITAS_AUDIO_TIMEOUT` env yok. Uzun arşiv (>5 saat) için yetersiz olabilir.
4. **`extract_audio` film/dizi lean profilinde israf**: ASR auto-language=True ⇒ `asr_in=video`, audio_path tüketilmez. extract_audio yine de 1800 s'ye kadar harcayabilir.
5. **`normalize._run_command` timeout YOK** (satır 255): subprocess sonsuz bloklayabilir.
6. **`transcribe._run_command` timeout YOK**, `extract_wav_chunk` askıda kalabilir.
7. **`job_runner._extract_analysis_clip` timeout YOK** (satır 344): asyncio.to_thread iş parçacığını bloklar, iptal yok.
8. **`channel_analysis._run_command` timeout YOK**.
9. **`-ss` input-öncesi (fast seek)**: keyframe granularity. `extract_wav_chunk` (transcribe.py 1268), `channel_analysis` (116–127), OCR-worktree hepsi input-öncesi. Doğruluk için input-sonrası tercih edilir.
10. **`_lean_transcribe` ffmpeg `capture_output` yok** (satır 186): `check=True` ile `CalledProcessError` "exit status N" döner; hangi hata olduğu bilinemez. Asimetri (`_extract_clip`'te stderr[-500:] var).
11. **`TARGET_SAMPLE_FMT='s16'` ffmpeg komutuna girmez** (normalize.py 15): yalnız doğrulamada. ffmpeg `pcm_s16le=s16` garantili ama belgelenmemiş varsayım.
12. **`_split_command` `-ac 1` YOK** (normalize.py 223–242): `pan=mono` filtresine güvenir. İkinci probe barikat ama ffmpeg pan ciktisinda channels metadata 1 olmayabilir.
13. **Split ffmpeg seri çalışır** (`_normalize_split` 202–203): paralel başlatılsa süre yarıya iner.
14. **`_normalized_filename` hash symlink-uyumsuz**: Path.resolve() üzerinden hash; aynı dosyaya farklı yoldan erişim cache ıskalatır.
15. **`probe_audio_stream` yalnız `a:0`**: çok-akışlı dosyada sessiz veri kaybı.
16. **`measure_lr_correlation` boş listeyi sessizce 1.0'a çevirir**: tüm ffmpeg çağrıları başarısız olursa mono kararı verir, split YAPILMAZ.
17. **`_wav_lr_correlation` AudioNormalizeError yakalanmaz**: tek bozuk WAV tüm korelasyonu patlatır.
18. **`window_seconds=5.0`, `max_windows=5` sabit**: env ile değiştirilemez.
19. **PROMO_INPUT_FILE / WAV_INPUT_FILE için `ensure_input_clip` eşdeğeri YOK** (asr_child_exit_diagnosis.py): test multiclip case'leri sessizce başarısız olur.
20. **`ensure_input_clip` returncode'a bakmaz**: başarısızlık raporda gömülü, build_report durdurmaz.
21. **`real_media_smoke.wav_info()` try-except YOK**: bozuk WAV'da `wave.open()` çöker, tüm build_report ölür.
22. **`real_media_smoke` probe ↔ extract bağımsız**: probe 'failed' olsa da extract denenir.
23. **`real_media_smoke` ASR_SOURCES↔extracted zip()** sıra varsayımı: yeniden sıralamada sessiz yanlış eşleşme.
24. **`real_media_smoke` `timestamp_local='2026-05-11' sabit-kodlu`**: her koşuda aynı tarih.
25. **`real_media_smoke` denoise→ASR zincir testi YOK**: ayrı smoke'lar var.
26. **`alignment_subprocess.np.interp` resample anti-alias yok**: aliasing riski (özellikle 44100→16000).
27. **`alignment_subprocess` PCM16 zorunlu** (satır 32–33): diğer width ValueError.
28. **`alignment_subprocess` DLL bulunamadığında sessiz**: `os.add_dll_directory` atlanır; `import whisperx` sonra patlar.
29. **`alignment_subprocess` her çıkış kodu 0**: whisperx hataları exception olarak çıkar ama anlamlı exit code yok.
30. **`alignment_subprocess` `model_cache_only` parametresinin whisperx API'sinde var olup olmadığı doğrulanmamış**.
31. **`_video_meta.duration_seconds` timeout=30 s SABIT**: 4K/saatlik arşiv aşabilir.
32. **`_video_meta` FFMPEG_EXECUTABLE env yok** (sadece FFPROBE_EXECUTABLE): asimetri.
33. **`_video_meta` video-only dosyada float döner ses YOK uyarısı yok**.
34. **`start_mitas.ps1` ffmpeg PATH'e EKLEMEZ**: sistem PATH'de ffmpeg yoksa asr_server sessiz başarısız.
35. **`start_mitas.ps1` `MITAS_SES_DIL_KONTROL=0` default**: ses/dil/ASR hatası KONTROL etiketini tetiklemez, Adım 1 hatası downstream'de gizlenir.
36. **`start_mitas.ps1` Stop-Process -Force orphan ffmpeg bırakabilir**: tmp dosya/port kilidi riski.
37. **`start_mitas.ps1` Hidden+detached**: ffmpeg hataları yalnız `svc_8787.err.log`; terminale yansımaz.
38. **`-loglevel error` ffmpeg uyarılarını gizler**: stream copy uyumsuzluğu, truncated input sessizce başarılı görünebilir.
39. **`_extract_analysis_clip` `-t` ama `-ss` YOK**: her zaman dosyanın başından kırpar.
40. **`_extract_analysis_clip` lazy import Paddle-asyncio riski tetikleyebilir**: teorik.
41. **diarize.py `_FFMPEG_DLL_DIRECTORY_HANDLES` listesi kapatılmıyor**: handle sızıntısı (kasıtlı görünüyor ama belgesiz).
42. **Sample peak/RMS Adım 1 çıktısında ölçülmez** — sessizlik/dolgun kayıt ayrımı yapılamaz.
43. **`extract_audio` BLOK ÇÖZ'de `extract_window` SONRA çalışır**: jenerik detect uzar ⇒ extract_audio gecikir (seri).
44. **`_lean_transcribe` `lid_src.suffix` kontrolü**: `_extract_clip` çıktısı .wav ama lid_src=orig (orijinal .mkv) olduğu için suffix doğru çalışır — yine de kafa karıştırıcı, dökümante değil.
45. **`fast_with_fallback` profili default ama Tedial'de `content_profile='bulten_haber'` sabit-kodlu** (job_runner.py 234): API'den kontrol edilemiyor.
46. **Adım 1 süresi explicit timer ile ölçülmüyor** — sadece BLOK ÇÖZ toplam t0.
47. **`pipeline.py` `normalized_outputs['mono']` iki kez doldurulabiliyor** (satır 438): split + ekstra-mono; semantik kafa karıştırıcı.
48. **`run_dir/normalized/` alt-dizini + `run_dir/normalized.wav`** çift kopya: geçici disk israfı.
49. **Çoklu film paralelliği geri alındı** (`5e8bd9b20d` revert): mevcut sistem seri, 2-paralel iş hâlâ planda.

---

## 22. Tarafsız göz hükmü (1 cümle)

**Sistem sağlam ve fonksiyonel — Adım 1 dört eşdeğer yoldan da 16 kHz/mono/pcm_s16le hedefini güvenilir biçimde tutturuyor; ancak timeout yokluğu, returncode kontrolsüzlüğü ve `-ss` fast-seek seçimi gibi altı sessiz risk üretim hata mesajlarını gereksiz yere karartıyor.**