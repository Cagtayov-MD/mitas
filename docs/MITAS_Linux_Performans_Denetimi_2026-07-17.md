# MITAS Linux Performans Denetimi — Rapor (2026-07-17)

**Yöntem:** 7 paralel denetim agent'ı (core, scripts×2, harness, model2+council_mcp, webui,
tools+kurulum+systemd) + sistem mikro-ölçümleri + tüm bulguların ana oturumda dosya açılarak
doğrulanması. Koşu yapılmadı (statik denetim). Tasarım: `docs/superpowers/specs/2026-07-17-linux-perf-denetim-design.md`.

---

## 1) Sistem/ortam ölçümleri

| Ölçüm | Durum |
|---|---|
| CPU governor | `performance` × 64 çekirdek ✓, boost açık ✓ |
| venv python başlatma | 10–20 ms ✓ |
| `import torch` (sıcak) | ~2,0–2,5 sn |
| `PaddleOCR` import (sıcak) | **7,7 sn** — süreç-başına-item deseninin taban maliyeti |
| `faster_whisper` import | 2,5–3,6 sn |
| GPU persistence mode | **KAPALI** (öneri: `nvidia-smi -pm 1`) |
| Kök disk (ext4, NVMe) | %85 dolu — izlenmeli |
| `/mnt/e` (eski E:) | ntfs3, %99 dolu — MİTAS kodu/env referans vermiyor ✓ |
| Swap | 8 GB, swappiness=10 ✓ |
| Paylaşım | ATLAS için ikinci ollama instance'ı aynı GPU'da (`ollama-atlas`, :11435) |

Not: ölçümler başka bir projenin (~43 çekirdeklik) aktif işi altında alındı.

---

## 2) UYGULANAN düşük riskli düzeltmeler (bu commit)

Ana tema: **Windows/WSL kalıntıları** — çoğu "yavaşlatma" değil, Linux'ta sessiz kırılma.
Hepsi `py_compile` temiz; canlı doğrulama: alignment python artık `venvs/alignment/bin/python`
olarak çözülüyor (`exists: True`).

### core/ (canlı sunucu — etkinleşmesi için servis restart gerekir, onay kartı A)
1. **`core/pipelines/asr/align.py`** — `DEFAULT_ALIGNMENT_PYTHON` `Scripts/python.exe` sabitiydi →
   **WhisperX hizalaması Linux'ta hiçbir zaman çalışmıyordu**, her ASR koşusu sessizce
   `interpolated` fallback'e düşüyordu (kalite regresyonu). Env+platform-farkında yapıldı.
2. **`core/api/asr_server.py`** — `TRANSLATE_PYTHON` aynı hastalık → **çeviri özelliği tamamen
   ölüydü** (`translate_venv_missing`). Düzeltildi.
3. **`core/api/asr_server.py` `_kill_proc_tree`** — Linux'ta `taskkill` yok → force-stop yalnız
   doğrudan çocuğu öldürüyor, venv-python + ffmpeg torunları **VRAM tutan yetimler** olarak
   kalıyordu → sonraki iş OOM. POSIX dalı eklendi: `ps --ppid` ile alt-ağaç toplanıp yapraktan
   köke SIGKILL. (`killpg` bilinçli KULLANILMADI — çocuklar ayrı session'da değil, sunucu
   kendini öldürürdü.)
4. **`core/api/asr_server.py` `_ram_percent`/`_cpu_percent`** — `ctypes.windll` Linux'ta yok →
   sysinfo hep −1 (UI'da CPU/RAM göstergesi kör). `/proc/meminfo` + `/proc/stat` dalları eklendi.
5. **`core/api/tedial/job_runner.py`** — OCR venv adayları Windows-only → `sys.executable`'a
   (yanlış venv) düşüyordu. Platform-farkında aday eklendi.

### scripts/ sıcak yol
6. **`scripts/mitas_pipeline.py` (mklink)** — `--from-hub` kurtarma yolu `cmd /c mklink` çağırıyordu
   → Linux'ta yakalanmayan `FileNotFoundError`, **retry/kurtarma mekanizması her seferinde çöküyordu**.
   POSIX'te `os.symlink` (+copytree fallback).
7. **`scripts/mitas_pipeline.py` (ASR-ön-sübap)** — `ctypes.windll` → sübap Linux'ta hiç
   çalışmıyordu (VRAM/commit çakışma koruması devre dışı). `/proc/meminfo`
   (MemAvailable+SwapFree) dalı eklendi; Windows davranışı birebir korundu.
8. **`scripts/mitas_pipeline.py` (ollama-bekçisi)** — powershell + `ollama.exe` +
   `creationflags` üçlüsü POSIX'te ilk satırda patlayıp bekçiyi öldürüyordu. Linux'ta
   Windows adımları atlanır; probe-bekleme döngüsü çalışır (ollama systemd `Restart=always` —
   diriltmeyi systemd yapar).
9. **`scripts/_pipe_asr.py`** — `MITAS_FFMPEG` env önceliği eklendi (mitas_pipeline ile tutarlı).

### scripts/ operasyonel aile (gece-batch/QC — Linux'ta sessiz no-op'tu)
10-16. **`gece_batch.py`, `gece_monitor.py`, `gece_qc.py`, `master_saglik_olcum.py`,
`_morning_audit.py`, `consolidate_database.py`, `frames_rerun.py`, `credit_severity_router.py`**
— hard-coded `E:\MITAS` / `C:\Users\TRT03...` yolları → glob'lar boş dönüyor, betikler
**hata vermeden hiçbir şey yapmıyordu**. Hepsi env-aware köke geçirildi. Fallback bilinçli
olarak `E:\MITAS` değil **betiğin kendi konumu** yapıldı: `MITAS_PROJECT_ROOT` yalnız
systemd/harness ortamına yükleniyor, elle koşuşta yok (bkz. kart M).

### tools/asr_ab (A/B test hattı — fiilen çalışamaz durumdaydı)
17. **`common.py`** — ffmpeg.exe sabiti → `MITAS_FFMPEG`/`/usr/bin/ffmpeg`.
18. **`run_all.py`** — `Scripts/python.exe` → `bin/python` (v9'da tüm 12-varyant koşusu çöküyordu).
19. **`compare_variants.py`** — `C:\Users\...\beyaz2 08 11.txt` referansı; **dosya eski Windows
    C: diskinde bulunup `references/asr_model_final/beyaz2_08_11.txt` olarak kurtarıldı**,
    default oraya çevrildi.

---

## 3) ONAY BEKLEYEN kartlar (sorun → sebep → çözüm)

### A. Servis restart — core düzeltmelerinin etkinleşmesi (ÖNKOŞUL)
Çalışan `mitas-asr`/`mitas-tedial` süreçleri hâlâ eski kodu koşuyor. Uygun bir anda (aktif iş yokken):
`sudo systemctl restart mitas-asr mitas-tedial`. Risk: düşük (idempotent); zamanlama kararı sizde.

### B. Gölge-VL sıradaki filmi 1–4 dk blokluyor — P1, kazanım BÜYÜK
- **Sorun:** `mitas_pipeline.py:3999-4041` — teslim bittikten sonra `_pipe_shadow_vl.py`
  `communicate(timeout=900)` ile senkron bekleniyor; flow-worker seri olduğundan sıradaki film
  1–4 dk (kötüde 15 dk) gecikiyor. Yorumdaki niyet ("teslimi geciktirmez") ile davranış çelişiyor.
- **Sebep:** Popen + hemen communicate; fire-and-forget değil.
- **Çözüm seçenekleri:** (1) fire-and-forget Popen (DEVNULL) + tamamlanma logunu
  `_pipe_shadow_vl.py`'nin kendisine taşı (telemetri/modül-durumu muhasebesi değişir — bu yüzden
  onay istiyorum); (2) `MITAS_SHADOW_VL=0` ile tamamen kapat (debug çıktısından vazgeçilir).
- **Kazanım:** arşiv ölçeğinde saatler. **Risk:** düşük-orta (telemetri).

### C. Aşama-1: PaddleOCR 51 filmde 102 kez yükleniyor — P0, kazanım BÜYÜK
- **Sorun:** `run_all.sh` → `kunye_stages.py stage1` her film için `_jenerik_pool.py`'yi 2 kez ayrı
  süreç olarak açıyor; paddle her seferinde sıfırdan (yalnız import 7,7 sn + model yükleme).
  Log kanıtı: Aşama-1 ≈ 2,5 saat.
- **Sebep:** Süreç-başına-item deseni; doğru desen (`asama1_v2.py` — "tek process, paddle 1 kez")
  repoda YAZILMIŞ ama master orkestrasyona bağlanmamış.
- **Çözüm:** `run_all.sh stage=1`'i `asama1_v2`/`repool_all_hybrid` desenine taşı (state-birleştirme
  mantığı korunarak). Tahmin: 2,5 saat → 15–30 dk.
- **Risk:** orta (üretim orkestrasyon yolu; testli geçiş ister).

### D. 51 film katı-seri + dalga mimarisi (GPU↔CPU nöbetleşe boşta) — P1
- **Sorun:** `run_all.sh` film başına seri süreç; log kanıtı stage2'de paralellik sıfır
  (duvar-saati = tek-tek sürelerin toplamı, 21 dk). `master_run.sh` dalga-dalga: GPU ~3 saat boşta,
  sonra CPU saatlerce boşta.
- **Çözüm (kademeli):** (1) stage2/slice'a `xargs -P 8-16` worker havuzu (OMP_NUM_THREADS sınırlı);
  (2) uzun vadede film-bazlı üretici-tüketici kuyruğu (film A VL'deyken film B stage1'de).
- **Risk:** orta (1) / yüksek (2 — mimari, resumability yeniden tasarım).

### E. WebUI: prod'da vite DEV sunucusu — P1
- **Sorun:** `mitas-webui.service` `vite dev` koşuyor (minify yok, HMR açık); hazır 1,5 MB build
  (`dist/`) hiç kullanılmıyor.
- **Çözüm:** `pnpm build` + `vite preview` (veya nginx statik + `/api` proxy). Unit değişikliği
  gerektirdiği için onaya. **Risk:** orta (proxy/base-URL testi).

### F. WebUI "Gözat" özelliği Linux'ta tamamen kırık — P1 (işlevsellik)
- **Sorun:** Frontend `joinPath` sabit `'\\'` ayracı (`FlowQueuePanel.tsx:632`); backend kök listesi
  Windows sürücü harfleri (`asr_server.py:403-444`) → özellik ölü.
- **Çözüm:** Frontend `/` ayracı; backend'de izinli-dizin listesi (örn. `FILMS_DIR`, `Database`).
- **Risk:** orta (UI+API birlikte değişmeli).

### G. Çeviri: cache O(n²) + GPU'da batch=1 — P1
- **Sorun:** Her segment için `TranslationCache` yeniden kurulup TÜM cache.jsonl parse ediliyor
  (`translate/service.py:81`); CTranslate2'ye `max_batch_size=1` + tek elemanlı liste veriliyor
  (`runtime.py:61,78`).
- **Çözüm:** Batch başına tek cache nesnesi; miss'leri gruplandırıp gerçek
  `translate_batch(..., max_batch_size=16-32)`.
- **Risk:** orta (sıralama/hata yönetimi korunmalı). Kazanım: arşiv büyüdükçe artan, orta-büyük.

### H. Linux OCR motorunda kare başına temp-PNG round-trip — P2
- **Sorun:** `_pipe_ocr.py:347-373` `recognize_pil` her karede PNG'yi TEKRAR diske yazıp okutuyor;
  engine API'si yol-tabanlı olduğu için dosyalar-arası API değişikliği gerekiyor.
- **Çözüm:** `recognize_path(path)` varyantı; kaynak yolu bilinen çağıranlarda temp'i atla.
- **Risk:** orta. Kazanım: film başına sn'ler, arşivde birikimli.

### I. Ufak sistem ayarları (tek komutluk)
- GPU persistence: `sudo nvidia-smi -pm 1` (+ kalıcılık için servis/udev).
- `mitas-asr`/`mitas-tedial` unit'lerine `Requires=ollama.service` (boot yarışı retry'ını keser).
- `MITAS_OLLAMA_KEEP_ALIVE=15m` → gerçek desene göre gözden geçir (ikili-ollama VRAM marjı dar).

### M. Ortam hijyeni: `MITAS_PROJECT_ROOT` elle koşuşlarda yüklü değil
`/etc/profile.d/mitas.sh` (veya direnv) ile `mitas.env`'in interaktif shell'e de yüklenmesi —
"portlanmış" 19 dosyanın env-fallback'i elle koşuşta E:\'ye düşmesin. Risk: düşük.

---

## 4) Bilgi notları (aksiyon istemez / düşük öncelik)
- `model2/` boş iskelet (POC başlamamış) — denetlenecek kod yok.
- ASR modelinin film başına yeniden yüklenmesi (~56 sn) **bilinçli** süreç-izolasyonu
  (CT2/CUDA çökme sınıfı); resident-worker ancak o riski de çözen mimariyle değişmeli.
- `council_mcp`: tek yavaş üye cevabı ~9 dk'ya kadar bloklayabilir; retry kuralı "kilitli karar"
  olduğundan dokunulmadı. Provider'larda çağrı başına httpx client — ihmal edilebilir.
- `asr_archive_batch_runner.py` doğru worker-havuzu deseni; `dizi_isle.py`/`gece_batch.py`
  paralelleştirilecekse model alınmalı.
- Sidebar'da gizli paneller poll'a devam ediyor + LogPanel koşulsuz re-render + satır-başına
  poller (webui) — E kartıyla birlikte ele alınabilir nokta düzeltmeleri.
- `sync_duckdb_local.py` `_SRC` env'leri tanımsız (kaynak NAS yolu belli olunca eklenmeli).
- Eski Windows diskleri hâlâ bağlı (`/mnt/e` %99, eski C:) — arşiv/yedek amaçlıysa sorun değil;
  pipeline referansı yok.
- ~45 tek-seferlik probe/smoke/benchmark betiğinde Windows yolları var — koşulursa görünür şekilde
  patlar, dokunulmadı (düşük öncelik).
