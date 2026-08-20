# MITAS Dizin Sadeleştirme v1 — Tasarım Dokümanı

**Tarih:** 2026-07-29
**Karar mercii:** Çağatay
**Hazırlayan:** Claude (Opus) — kanıt toplama 4 paralel Sonnet ajanı
**Durum:** Kısmen geçersiz — aşağıdaki uyarıya bakın

> ## ⚠️ 2026-07-29 doğrulama turu bu dokümanın sayılarını çürüttü
>
> 53 ajanlık kırmızı-takım turu sonrası şu maddeler **geçersizdir**; güncel hali
> `docs/superpowers/plans/2026-07-29-dizin-sadelestirme.md` içindedir:
>
> | Bu dokümanda yazan | Gerçek |
> |---|---|
> | Kökte 48 giriş (Bölüm 2.1, 3, 9) | **57** (`ls -A`) |
> | ~206 G geri kazanılır (Bölüm 5) | **~38 G anında**; `mv` aynı ext4'te `df`'i değiştirmez |
> | `git prune` risksiz (Bölüm 5.1) | 2 commit'i (düşürülmüş stash) siler; **`git gc` 3 benzersiz test dosyasını yok ederdi** — `kurtarma/*` dalları o yüzden açıldı |
> | `_karantina/` (Bölüm 4) | `.gitignore:112 /_*` ile ignore → `git clean -fdx` siler. Ad `KARANTINA_2026-07-29/` olmalı |
> | `normalize.py` deseni yeterli (Bölüm 6) | Naif `parents[1]` canlı worktree'yi kök yapar; **çapa** gerekir |
> | pytest + smoke = kapı (Bölüm 7) | `tests/` altında taşınacak yollara **0 referans** |
> | Ölü venv'lere tek Windows referansı (5.3) | 8 adayın **5'inde çürütüldü** |
>
> **Ayrıca bu dokümanda hiç olmayan, turda bulunan mayın:** `git clean -fdx`
> bu repoda **1.1 TB** siler (`models/` 587 G, `Mitas_Files/` 157 G,
> `Database/` 119 G, `venvs/` 105 G, `mitas.env`, `CLAUDE.md`) ve
> `mitas_guard.py:96` regex'i onu yakalamıyor.
>
> Bölüm 3'teki **sınıflandırma** ve Bölüm 8'deki **hata bulguları** geçerliliğini korur.

---

## 1. Amaç ve kapsam

`/opt/mitas` 1.2 TB, kökünde 48 giriş var; üretim kodu, aktif iş, deney kalıntısı ve
ölü kütle yan yana duruyor. Bu doküman, **hiçbir üretim yolunu değiştirmeden** kökü
okunabilir hale getirme ve ~206 G yer geri kazanma tasarımını tanımlar.

**Kapsam dışı (ayrı iş):** Veriyi repo dışına çıkarma (Yaklaşım C), Bölüm 8'deki 4 hata
bulgusunun düzeltilmesi.

### 1.1 Çağatay'ın kararları (2026-07-29 oturumu)

| Soru | Karar |
|---|---|
| Asıl dert | **Netlik** — ne nerede belli olsun; disk ikincil ama gerekli |
| Yaklaşım | **A** (karantina + kök sadeleştirme). C sonra ayrıca konuşulacak |
| Silme yetkisi | **Claude taşır ve raporlar, Çağatay siler.** Geri dönüşü olmayan işlem Claude'a yok |
| Kapsam | **Kademe 0-3** (~206 G). Kademe 4 ayrı karar |
| Kök sebep fix'i | **Temizlikten ÖNCE** |
| `git prune` | **Onaylandı** |
| İşbölümü | Plan/karar Opus'ta, uygulama Sonnet ajanlarında |

---

## 2. Yaklaşım seçimi ve reddedilen alternatifler

| | A — Karantina + kök sadeleştirme | B — Rol bazlı yeniden mimari | C — Veriyi repo dışına |
|---|---|---|---|
| Yol değişikliği | **Yok** | Symlink katmanı | Tüm veri kökleri |
| Netlik kazancı | Kök 48 → ~39 + `HARITA.md` etiketlemesi | Yüksek | Yüksek |
| Risk | Düşük | Orta-yüksek | Yüksek |
| **Karar** | **SEÇİLDİ** | Reddedildi | Ertelendi |

**B neden reddedildi:** `scripts/mitas_roots.py:80` `_is_reparse_point()` candidate kökü
altında symlink/junction'ı **reddediyor** (RootSafetyError). B, netlik için symlink'e
dayanıyor; yani izolasyon sözleşmesini korumak için o güvenlik kontrolünün de
gevşetilmesi gerekirdi. Prensip 2 — çalışan bir güvenlik kapısını netlik uğruna bozmak
kabul edilemez.

**C neden ertelendi:** 1 TB fiziksel taşıma + tüm systemd/cron/env güncellemesi. A, C'nin
önünü kapatmaz; aksine ölü kütle temizlenmiş bir ağaç C'yi ucuzlatır.

### 2.1 A'nın dürüst tavanı

A, kök girişini 48 → ~39'a indirir, 18'e değil. 48 girişin çoğu gerçekten canlıdır:
`mitas_roots.py` üzerinden yük taşıyan 8 dizin, canlı kod 12 dizin. Yolları
değiştirmeden fazlası mümkün değildir. Bu yüzden netlik iki koldan alınır:

1. Ölü/arşiv girişleri kökten çekmek (9 giriş → 2 giriş: `arsiv/` + `_karantina/`)
2. **Kalan her girişi `HARITA.md` ile etiketlemek** — sınıf, ne işe yarar, kim kullanır

"Bu klasör neydi ya" sorusunu bitiren şey giriş sayısı değil, etikettir.

---

## 3. Sınıflandırma (kanıta dayalı)

Kanıt yöntemi: `mitas_roots.py` okuma + kod içi referans taraması (`grep`) + `git log`
tarihi. **mtime kullanılmadı** — 2026-07-16 Windows→Linux kopyası tüm mtime'ları sıfırladı.

### 🔒 ÜRETİM — dokunulmaz

| Dizin | Boyut | Kanıt |
|---|---|---|
| `Database/` | 119 G | `mitas_roots.py:118` `DB_ROOT` |
| `Mitas Output/` | 188 M | `mitas_roots.py:113-114` `OUT_ROOT`/`EXPORT_ROOT` |
| `outputs/` (kök dosyaları) | — | `mitas_roots.py:124,127-128` `EVENTS_PATH`, `MANIFEST_DIR` |
| `cache/web` | 54 M | `mitas_roots.py:129` `WEB_CACHE_DIR` |
| `_102_afis_cache/` | 58 M | `mitas_roots.py:130` `AFIS_CACHE_DIR` |
| `export/` | 732 M | `kurulum/26_kapanis_pdf.py:26,28` (bkz. Bölüm 8.4 — mimari risk) |
| `seriler/` | boş | `kurulum/05_env_olustur.sh:8,24` `MITAS_SERILER_ROOT` |
| `config/` | 12 K | `core/pipelines/translate/router.py:13` |

### 🔧 CANLI KOD

`core/` (systemd `mitas-asr`), `scripts/`, `webui/` (systemd `mitas-webui`),
`tests/` (CI koşuyor, 1005 test), `harness/`, `kurulum/`, `council_mcp/` (MCP bağlı),
`references/`, `schemas/`, `tools/`, `docs/`, `locks/`, `benchmark_templates/`

### 🧪 AKTİF DENEY

`data/`, `experiments/`, `OCR-worktree/`, `filmtest/`, `testklipler/`,
`candidate_runs/kunye51_20260714` (harness'in canlı baseline'ı — `harness/env.sh`,
`report_basic.py`, `test_resolution.py`, `test_fullscan.py`, `bench_agreement.py`)

### 📦 ARŞİV → `arsiv/`

| Giriş | Boyut | Gerekçe |
|---|---|---|
| `mutfak/` | 32 M | Windows-dönemi belge sistemi; `00_BURADAN_BASLA.md` hâlâ "Canonical workspace: E:\MITAS" diyor. Yerini `docs/GUNLUK.md` aldı. Son commit 2026-06-03 |
| `linux_backup_wsl2_20260714/` | 5.9 G | WSL2 göç anlık görüntüsü. **Claude oturum geçmişi + hafızası içeriyor — silinmez, arşivlenir** |
| `backups/` | 920 K | 2026-05-22 tek-seferlik merge yedeği, kod referansı yok |
| `Logolar/` | 3.6 M | 51 TRT kanal logosu, kod referansı yok |
| `requirements/` | 32 K | Dondurulmuş taslak; hiçbir script `pip install -r` ile çağırmıyor |
| `model2/` | 32 K | Boş POC iskeleti (6 boş `__init__.py`). `models/` ile isim karışıklığının kaynağı |

### 🗑 KARANTİNA → `_karantina/2026-07-29/`

**Kök seviyesinden taşınanlar (3 giriş):**

| Giriş | Boyut | Gerekçe |
|---|---|---|
| `hf-cache/` | 2.3 M | Boş kabuk (`CACHEDIR.TAG` + `version.txt`). Gerçek HF cache `models/hf_cache` (`mitas.env` `HF_HOME`). Tek referansı Windows-dönemi probe fallback'i `r"E:\MITAS\hf-cache"` |
| `E:\MITAS/` | 148 K | Hata artefaktı — Bölüm 6'daki kök sebebin ürünü. Fix'ten **sonra** taşınır, yoksa geri gelir |
| `mitas.db` | 0 byte | Boş placeholder; hiçbir `.py`/`.sh` okumuyor/yazmıyor, sadece `README.md`'de adı geçiyor |

**Kalmaya devam edenler (küçük ama canlı/belirsiz — dokunulmaz):**
`samples/` (320 K, `torchcodec_smoke.wav` — adı bir kurulum-doğrulama script'ine işaret
ediyor, kazanç sıfır), `ASR_KAPALI.flag` (aktif kill-switch), `locks/` (3 M, meşru
env-freeze çıktısı, `lock_and_check_envs.py` kullanıyor), `.tedial_sessions/` (canlı
oturum çerezi), `.vscode/` (inotify tükenmesini önleyen `data/**` hariç tutması).

**Kademe 2-3'ten taşınanlar:** Bölüm 5.3 ve 5.4.

**Kök giriş muhasebesi:** 48 − 6 (arşiv) − 3 (karantina) − 1 (`.pytest_cache`, silinir)
+ 2 (`arsiv/`, `_karantina/`) = **40**. `HARITA.md` eklenince 41 dosya girişi, ama
etiketlenmiş bir 41, etiketsiz bir 48'den okunabilirdir.

---

## 4. Karantina mekaniği

```
_karantina/2026-07-29/
├── MANIFEST.tsv      # kaynak_yol · boyut · kademe · sınıf · gerekçe · kanıt
├── GERI_AL.sh        # satır başına tek komutluk geri alma
└── <taşınan içerik, orijinal dizin yapısı korunarak>
```

**Sözleşme:**
- Claude `mv` kullanır, `rm` kullanmaz. Aynı dosya sisteminde `mv` anlıktır — 145 G
  taşıma saniyeler sürer, kopyalama yoktur.
- `MANIFEST.tsv` her satırda **kanıt** taşır (hangi grep sıfır döndü, hangi manifest
  satırı "reddedildi" diyor).
- Silme kararı ve komutu Çağatay'a aittir.
- İstisna — Claude'un doğrudan sildiği tek sınıf: yeniden üretilebilir çöp
  (`__pycache__`, `.pytest_cache`, `webui/dist`).

---

## 5. Kademeler

| Kademe | İçerik | Kazanç | Risk |
|---|---|---|---|
| **0** | `git prune` + `__pycache__` + `webui/dist` + `.pytest_cache` | 8.3 G | Yok |
| **1** | `cache/duckdb` → hardlink | 30 G | Düşük |
| **2** | Ölü venv'ler + referanssız modeller | 145 G | Orta |
| **3** | Kapanmış candidate koşuları + `outputs/` deney arşivi | 23 G | Orta |
| **4** | `filmtest/`, `testklipler/`, `Mitas_Files/`, `hf_cache` VLM havuzu | — | **DOKUNMA** |

**Toplam hedef (0-3): ≈ 206 G**

### 5.1 Kademe 0 — risksiz (8.3 G)

`git count-objects -vH`: 8.32 GiB **loose**, 49.39 MiB packed. `git fsck --unreachable
--no-reflog`: **44.160 blob + 12 tree + 5 commit** hiçbir dala, tag'e veya reflog'a bağlı
değil — 8.24 GiB. Tamamı PNG, 44.143'ü 2026-07-28 tarihli (son commit 07-26). Yani
`git add` edilip commit edilmeden bırakılmış.

`git prune --expire=now` commit geçmişini **değiştirmez**, force-push gerektirmez, diğer
branch'leri (`claude/*`, `codex/*`, `origin/main`) etkilemez. Sadece gc'nin varsayılan
2 haftalık bekleme süresini erkene alır.

Ek: `__pycache__` (~10 M), `webui/dist` (4.2 M, servis `vite dev` ile çalışıyor),
`.pytest_cache` (72 K).

### 5.2 Kademe 1 — duckdb kopyası (30 G)

`cache/duckdb/{mitas,imdb}.duckdb` ile `Mitas_Files/` içindeki masterlar **byte-birebir
aynı** (aynı boyut: 19.786.379.264 / 11.815.890.944; aynı mtime). Üretim `cache/duckdb`'yi
okuyor (`mitas.env: MITAS_WIKIDATA_DUCKDB`). Kopya → hardlink dönüşümü hem yolu korur hem
30 G kazandırır.

**Doğrulama şartı:** dönüşümden önce `sha256sum` ile birebirlik teyit edilir; eşleşmezse
kademe iptal.

### 5.3 Kademe 2 — ölü venv ve model (145 G)

**Venv'ler (41.5 G):** `internvl` 6.4G, `nemo` 6.2G, `denoise` 5.8G, `tts` 5.3G,
`locateanything` 5.2G, `vlm` 5.1G, `minicpmv` 5.0G, `ina` 2.5G.
Kanıt: her birine tek referans Windows-dönemi tek-kullanımlık probe script'i
(`E:\MITAS` yollu); `model_manifest.yaml`'da geçmiyor; pipeline çağrısı sıfır.
`denoise` için ek kanıt: `core/pipelines/asr/profiles.py:49` "v0.1 does not invoke
denoise from the main pipeline".

**KORUNACAK venv'ler:** `stt` (5.2 G) — `scripts/inspect_model_envs.py:183`
`"do_not_delete_yet"` açık kararı var. `face`/`visual`/`audio`/`tag` (14.1 G) —
manifest'te "candidate", gelecek özellik iskelesi, BELİRSİZ sınıfında.

**Modeller (103.4 G):** `models/QwenOmni` 49 G (bake-off dönemi, GUNLUK'te kazanan
olarak geçmiyor, pipeline referansı sıfır) + ollama test modelleri: `qwen36-35b-test`
22 G, `qwen36-27b-test` 17 G, `mistral-small3.2` 15 G + `models/tts` 347 M +
`models/denoise` 8.4 M.

### 5.4 Kademe 3 — kapanmış koşular (23 G)

**candidate_runs (18 G):** 29 koşudan `kunye51_20260714` (26 G, harness canlı baseline'ı),
`test_debug/` ve `test_frame_vs_master/` (2026-07-28, en yeni) **HARİÇ**. Kalan 26 koşu
2026-07-11/07-20 arası, `outputs/`'ta karşılık gelen özet raporları mevcut.

**outputs/ (~5 G):** `footage_pano427` 1.5 G, `asr_archive_all_wav_benchmark` 1.3 G,
`closing_credit_onset_vlm` 1.1 G, `RUN_WATCH_20260622` vb. tarihli deney klasörleri.
**`.md` karar kayıtları taşınmaz** — yeniden üretilemez, kökte kalır.

### 5.5 Kademe 4 — DOKUNMA (ayrı karar)

| Dizin | Boyut | Neden dokunulmuyor |
|---|---|---|
| `filmtest/` | 66 G | Kaynak videoların TRT MAM'dan (`evo.int.trt.net.tr:8885`) yeniden çekilebilirliği **doğrulanamadı**. `Database` ham video saklamıyor, `cache/staging` boş |
| `testklipler/` | 9 G | `scripts/real_media_smoke.py:16` aktif kullanıyor; kaynağı belirsiz, tek nüsha olabilir |
| `Mitas_Files/` | 157 G | Wikidata/IMDb kaynak dökümleri; besleyen SMB paylaşımı (`X:\DIGER\...`) artık bağlı değil |
| `models/hf_cache` VLM havuzu | ~296 G | Benchmarklanmamış aday havuzu; hangi adayların hâlâ kıyaslanacağı Çağatay'ın bilgisi |

---

## 6. Kök sebep düzeltmesi (temizlikten ÖNCE)

`scripts/mitas_roots.py:28`:

```python
PROJECT_ROOT = Path(os.environ.get("MITAS_PROJECT_ROOT") or r"E:\MITAS")
```

Linux'ta `:` ve `\` geçerli dosya-adı karakteri olduğu için bu, cwd altında **`E:\MITAS`
adlı gerçek bir dizin** yaratır.

**Kim env'i set etmiyor:**
- Crontab'daki 4 iş → `kurulum/30_kapanis_zincir.sh`, `35_ozet_dongu.sh`,
  `37_kurtarma_zinciri.sh` `mitas.env`'i kaynak almıyor; cron login-shell env'i miras almaz
- `~/.bashrc` / `~/.profile` → elle çalıştırılan her script aynı riske açık
- (systemd 3 servisi **güvenli** — `EnvironmentFile=/opt/mitas/mitas.env`)

**İkinci ve daha ciddi sonuç:** `scripts/mitas_pipeline.py:2394` ASR kill-switch'i
`(PROJECT_ROOT/"ASR_KAPALI.flag").exists()` ile kontrol ediyor. Env'siz koşan bir süreçte
`PROJECT_ROOT` yanlış → **flag görünmez → ASR istemeden açılır.** Çağatay'ın 2026-07-11
"aksi emre kadar kapalı" kararı sessizce delinebilir.

**Düzeltme:** `core/pipelines/asr/normalize.py`'deki güvenli desen — env yoksa `__file__`
üzerinden repo köküne düş. Bu tek merkezi fix, hâlihazırda her çağıranın ayrı ayrı
`setdefault` yapmak zorunda kaldığı yükü kaldırır (`harness/master_dup/uret.py:110-140`
bu tehlikeyi zaten yorumla belgelemiş ama kaynağı düzeltmemiş).

**Test şartı:** düzeltmeden önce kırmızı test yazılır — env silinmiş ortamda
`resolve()["DB_ROOT"]` `/opt/mitas/Database` dönmeli.

---

## 7. Uygulama akışı

Her kademe bir Sonnet ajanı; aralarında **doğrulama kapısı**:

```
Kök sebep fix (TDD) → doğrula → commit
   ↓
Kademe 0 → pytest + pipeline smoke → commit
   ↓
Kademe 1 → sha256 teyidi + duckdb okuma testi → commit
   ↓
Kademe 2 → pytest + pipeline smoke → commit
   ↓
Kademe 3 → harness baseline testi → commit
   ↓
arsiv/ + _karantina/ + HARITA.md → commit
   ↓
MANIFEST.tsv Çağatay'a sunulur → silme kararı Çağatay'da
```

Doğrulama kapısı geçmezse o kademe `GERI_AL.sh` ile geri alınır ve rapor edilir.

---

## 8. Temizlik kapsamı DIŞINDA kalan hata bulguları

Bu 4 madde "dağınıklık" değil, çalışan sistemdeki hatalardır. Temizlikten **sonra**
ayrı iş kalemi olarak ele alınacak (kök sebep — Bölüm 6 — hariç, o önce yapılıyor).

**8.1 — `core/api/asr_server.py:736`:** `Path("E:\\").stat().st_dev` Linux'ta her zaman
`FileNotFoundError` fırlatıyor; L730-756 `except Exception: pass  # FAIL-SAFE` içinde
yutuluyor. Sonuç: **prefetch özelliği Linux'ta sessizce hiç çalışmıyor.** Hata da
görünmüyor. Fonksiyonel regresyon.

**8.2 — `models/lid/speechbrain-lang-id-voxlingua107-ecapa/*.ckpt` kırık symlink:**
hedef `C:/Users/TRT03/.cache/huggingface/...`, bu makinede yok. `os.path.exists()` →
`False`. `core/pipelines/asr/language_intelligence.py` bu modele referans veriyor ama
**model fiilen çalışamıyor.**

**8.3 — `kurulum/26_kapanis_pdf.py:26`:** `KOK = Path("/opt/mitas")` hardcode. Bu script
`mitas_roots.py` sözleşmesine tabi değil → **candidate izolasyonunu deliyor**; bir aday
koşusu üretim `export/`'una yazabilir. `MITAS_RUN_ROOT` bunu yakalamaz.

**8.4 — Ölü kod yoğunluğu:** `scripts/` altında 213 kök `.py`'nin ~70'i (%33) hiçbir
yerden çağrılmıyor (`*_probe.py`, `smoke_*.py`, `*_bench.py` deseni). `core/`'un 17 M'sinin
14 M'si referanssız logo PNG'si (`logo.png`, `logo4x.png`, `logo8x.png`). 5 tracked `.ps1`
Windows kalıntısı. Bunlar kod temizliği, dizin temizliği değil — ayrı tur.

---

## 9. Başarı ölçütü

| Ölçüt | Hedef |
|---|---|
| Kök giriş sayısı | 48 → 41 (bkz. Bölüm 3 muhasebesi), **her biri `HARITA.md`'de etiketli** |
| Geri kazanılan alan | ≥ 200 G (karantina onaylanınca) |
| `.git` boyutu | 8.4 G → < 100 M |
| Üretim davranışı | **Değişmemiş** — pytest yeşil, pipeline smoke bir filmde geçiyor |
| Geri alınabilirlik | `_karantina/` içindeki her öğe `GERI_AL.sh` ile tek komutla dönebilir |
| Kök sebep | Env'siz ortamda `resolve()` doğru kökü dönüyor (test ile kanıtlı) |

---

## 10. Riskler ve karşı önlemler

| Risk | Önlem |
|---|---|
| Karantinaya alınan bir şey aslında lazımmış | `mv` ile taşınır, silinmez; `GERI_AL.sh` hazır; silme kararı Çağatay'da |
| Kademe 2'de "referanssız" sandığımız model aslında kullanılıyor | Her kademe sonrası pipeline smoke; ayrıca BELİRSİZ sınıfı (`face`/`visual`/`audio`/`tag`, 14.1 G) bilinçli olarak kapsam dışı |
| `git prune` geri dönüşsüz | `git fsck --unreachable` ile 3 kez doğrulandı: hiçbir dal/tag/reflog referansı yok. Geçmiş değişmiyor |
| Kök sebep fix'i 5 üretim yolunu birden etkiliyor | Önce kırmızı test; env varken davranış **byte-aynı** kalmalı (mevcut sözleşme: `mitas_roots.py:10`) |
| Temizlik sırasında cron koşup yeni kalıntı üretir | Kök sebep fix'i **ilk** adım; ayrıca temizlik penceresinde cron durumu kontrol edilir |
