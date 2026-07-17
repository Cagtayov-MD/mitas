# MITAS 100-Film Koşusu — VERİMLİLİK / KAYNAK-BOŞLUĞU ANALİZİ
**Oturum:** RED ROCK (UTC 2026-06-21 22:36) ve sonrası — yalnız bu koşu izleniyor.
**Mod:** SALT-OKUNUR. Soru: *İki film paralel çalışır mı? CPU/GPU ne zaman boşta? O boşlukta en verimli ne yapılır?*

> Durum: **ÖN-ANALİZ + canlı telemetri birikiyor.** Aşama-bazlı ölçülen CPU/GPU sayıları, parti tamamlanınca `res_correlate.py` ile bu belgeye işlenecek.

---

## 0) ENSTRÜMANTASYON (kurulan ölçüm düzeneği)
| Araç | Çıktı | Ne ölçüyor | Temizlik |
|---|---|---|---|
| `sampler.ps1` (bg) | `res_samples.csv` (3s) | sistem CPU%, **GPU SM%**, **VRAM**, **GPU güç(W)**, disk%, ağ KB/s | GPU **temiz**; sysCPU/disk **kirli** |
| `proc_sampler.ps1` (bg) | `proc_samples.csv` (5s) | **pipeline süreç-ağacı CPU%** + süreç sayısı + RSS | **temiz** (QC işinden izole) |
| `res_correlate.py` | aşama×kaynak tablosu | `_log.jsonl` aşama aralıklarını telemetriyle çakıştırır | per-stage GPU/pipeCPU |
| `batch_watch.sh` (bg) | uyandırma | her ~4 film / ~45 dk | — |

**ÖLÇÜM UYARISI (önemli):** Kutu bu koşuya **adanmış değil**. Eş-zamanlı çalışanlar tespit edildi: `cozumleme_fix.py --apply`, `strip_channels.py --apply` (COZUMLEME_QC düzeltmeleri), `search_server` (ATLAS), `master`-PNG. Bunlar sistem-CPU/disk/ağı şişiriyor → GPU SM% ve pipeline-ağacı CPU'su gerçek sinyal olarak kullanılıyor.

---

## 1) ERKEN ÖLÇÜLEN SİNYAL (ilk birkaç dk, doğrulama)
- **GPU boşta penceresi gerçek:** CPU/IO aşamasında GPU **SM %0-1, güç 31W** (rölanti tabanı; tam yük ~200-350W) iken VRAM 20GB (modeller yüklü, hesaplamıyor).
- **Pipeline aktifken CPU:** süreç-ağacı **makine CPU'sunun %52-74'ü** (tek film bile çok-çekirdek kullanıyor → 2-film CPU çakışması olasılığı GERÇEK, GPU'dan farklı olarak).
- **Film-arası boşluk küçük:** YAĞMUR bitti 02:19:30 → sonraki film başladı 02:20:38 = **~1 dk** (kuyruk gecikmesi sorun değil).

---

## 2) KAYNAK-PROFİLİ MODELİ (kod-doğrulanmış; sayılar ölçümle gelecek)
Her aşamanın baskın kaynağı (önceki kod-denetiminden):

| Aşama | Süre (medyan) | Baskın kaynak | GPU | pipe-CPU | Boşluk fırsatı |
|---|---:|---|:--:|:--:|---|
| cozumleme (decode+detect+frame) | 87s | **CPU** (ffmpeg) + CLIP kısa | düşük | **yüksek** | GPU boş → N+1 OCR/ASR sığar |
| OCR ∥ ASR | 141s | **GPU** (whisper+OneOCR) | **yüksek** | orta | CPU kısmen boş → N+1 decode sığar |
| credit_text | 24s | CPU/GLM | orta | orta | — |
| VL-fallback (%60) | 35s | **GPU** (gemma4) | **yüksek** | düşük | — |
| ozet | ~20s | **bulut LLM** (ağ-bekleme) | boş | düşük | GPU+CPU boş → N+1 işine ver |
| PDF | 62s | **CPU** render | boş | yüksek | GPU boş → N+1 OCR/ASR |
| v4_finalize | 150s | **CPU/IO + ağ** (duckdb+web+reportlab) | **boş** | orta | **EN BÜYÜK GPU-boş pencere** |
| qwen_qc | 15s | GPU (qwen2.5vl) | yüksek | düşük | — |

**Tamamlayıcılık (pipelining'in özü):** Film N'in **GPU-boş kuyruğu** (ozet+PDF+v4_finalize ≈ **230s**) ile Film N+1'in **GPU-ağır başı** (cozumleme+OCR∥ASR+VL ≈ **260s**) örtüşür. İki film GPU'ya nadiren aynı anda vurur.

---

## 3) "BOŞLUKTA EN VERİMLİ NE YAPILIR" — TASARIM SEÇENEKLERİ

**A) Kademeli (staggered) 2-film pipelining — en yüksek getiri**
Film N v4_finalize/PDF'e (GPU-boş) girince, Film N+1'in cozumleme+OCR+ASR'ını (GPU) başlat.
- Beklenen: ~1.5-1.8× throughput. 100 film ~18 saat → **~10-12 saat**.
- Gerekli: `asr_server` kuyruğunda "Film N GPU-fazını bitirince N+1'i sal" faz-kilidi. VRAM tavanı: tek film tepe ~12-13GB, 24GB kartta 2 film GPU-fazı **çakışırsa** ~24GB sınırına yaklaşır → faz-kilidi şart (naif 2-paralel değil).

**B) GPU-boş pencerede HARİCİ GPU işi (koşuyu hiç değiştirmeden)**
v4_finalize+PDF'in ~230s GPU-boşu, koşunun KENDİSİNE dokunmadan başka GPU işine verilebilir: örn. biriken **VL-fallback/qwen-QC kuyruğunu** ayrı bir worker'a, ya da Çağatay'ın master-PNG/COZUMLEME_QC GPU işlerini bu pencereye sıkıştırmak. Risk düşük (koşu kodu değişmez), ama orkestrasyon gerekir.

**C) CPU-boş pencerede iş**
OCR∥ASR (GPU-ağır, ~141s) sırasında pipeline-CPU orta → N+1'in **ffmpeg decode**'u (saf CPU) buraya sığar. Ama (Bölüm 1) tek film zaten CPU'nun %52-74'ünü yiyor → CPU başı dar; bu yüzden **A** (GPU-eksenli) **C**'den daha güvenli kazanç.

**D) "En verimli kullanım" — koşuyu hızlandıran ek kaldıraçlar (ZAMAN_RAPORU'ndan)**
- v4_finalize redundansını kes (credit_validate zaten IMDb sorguluyor; v4 tekrar yapıyor).
- ASR'ı kritik yoldan ayır (özetten önce join) → ~60-80s/film.
- Yabancı/müzik ASR'ı kısalt (turbo+temp-cap) → ARŞIN gibi 7× filmler.
- **Kutuyu koşuya ada:** eş-zamanlı COZUMLEME_QC/ATLAS işleri CPU/disk çalıyor; koşu boyunca durdurulursa film-CPU darboğazı azalır.

---

## 4) ÖLÇÜLEN AŞAMA×KAYNAK TABLOSU — 8 film (Parti 1+2, ~78 dk telemetri)
Kaynaklar: `res_samples.csv` (GPU temiz) + `proc_samples.csv` (pipe-CPU temiz). sysCPU/disk kirli (QC/ATLAS).
**Yakınsama:** GPU-boş oranı Parti 1'de %68, Parti 2 sonrası (8 film) yine **%68** → sağlam.

| Aşama | süre(s) | **GPU SM%** | GPU güç(W) | **pipe-CPU%** | VRAM(MB) | Baskın kaynak | GPU-boş sn |
|---|---:|---:|---:|---:|---:|---|---:|
| cozumleme | 86 | 4 | ~50 | 25 | 10.4k | **IO + orta CPU** (ffmpeg/frame) | 74 |
| OCR ∥ ASR | 169 | **24** | 140-149 | 18 | 12-15k | GPU (doymamış) + CPU | 70 |
| credit_text | 29 | 18 | ~120 | 5 | 18k | hafif GPU/CPU | 11 |
| VL-fallback (%60) | 92 | **34** | **210** | 0 | 17k | GPU (en ağır) | 29 |
| ozet | 25 | 5 | ~100 | 0.5 | 20-24k | **bulut LLM bekleme** | 20 |
| PDF | 64 | 6 | ~45 | 3 | 20-24k | **IO/alt-süreç bekleme** | 51 |
| v4_finalize | 201 | **0** | 31-34 | 10 | 15-23k | **AĞ/IO bekleme** (web+duckdb) | 200 |
| qwen_qc | 14 | 17 | 95-179 | 0 | 5k | GPU | 6 |
| **TOPLAM/film** | **~679** | — | — | — | tepe **24k** | — | **460 (%68)** · CPU-boş 273 (%40) |

### ÖLÇÜLEN ÇIKARIMLAR (kanıtlı)
1. **GPU compute atıl: film başına ~480s (%68) boşta; "GPU-ağır" aşamada bile SM yalnız %24-33.** whisper-turbo/OneOCR/gemma GPU'yu doyurmuyor (güç yükselir ama SM düşük) → compute tarafında 2. filme bol yer var.
2. **Gerçek kısıt = VRAM rezidensi.** ozet/PDF/v4 (GPU-compute boş) sırasında VRAM **~24GB'a dayanıyor**; modeller atıl rezident. 2-film paralelliğinin OOM sebebi bu; çözüm: atıl-faz model-eviction (ollama keep_alive=0 / whisper unload).
3. **v4_finalize (217s, ÖLDÜREN POZ'da 312s) ağ/IO-bekleme bağımlı** (GPU %0, pipe-CPU %10, disk %2). Pipeline ağacı çoğunlukla bekliyor → en verimli "doldurulacak" pencere.
4. **PDF (65s) de %80+ atıl** (GPU 5%, pipe-CPU 3%) — alt-süreç/IO beklemesi.
5. **Pipeline CPU'su düşük** (en yüksek cozumleme %27): ne CPU ne GPU doygun → darboğaz **seri bağımlılık + ağ-bekleme + VRAM**, ham işlem gücü değil.
6. **Paylaşımlı kutu cezası:** v4_finalize bu pencerede 150s→280-312s'e uzadı (eş-zamanlı `cozumleme_fix --apply` / ATLAS / master-PNG). 100 filmde ~saatlerce kayıp.

### "BOŞLUKTA EN VERİMLİ NE YAPILIR" — ölçümle güncel
- **GPU-boş büyük pencere = ozet+PDF+v4_finalize ≈ 315s/film** (GPU %0-11, pipe-CPU <%12). Buraya **Film N+1'in GPU-ağır başı** (cozumleme→OCR→ASR→VL ≈ 350s) gelir → kademeli pipelining. Ölçülen 480s GPU-boş, neredeyse tam bir 2. filmin GPU işini alır.
- **Etkinleştirici = VRAM yönetimi:** N+1'in modelleri için N'in atıl modelleri evict edilmeli (aksi hâlde 24GB sınırı).
- **Bedava kazanç (kod değişmeden):** kutuyu koşuya ada → v4_finalize'i ~2× hızlandırır (ölçülen contention cezası).

## 5) PARTİ 3-4 EK BULGULAR (17 film, ~183 dk telemetri)
Aggregate sabit: **GPU-boş %66-69, CPU-boş %46-48** (17 filmde yakınsama korundu).

**(a) Yabancı/dublajsız film profili — ÖLÇÜLDÜ (NAMUS DÜŞMANI, Arapça):**
- ASR 451s (Türkçe ~150-240s'in 2-3×). OCR∥ASR bloğu boyunca GPU **%33** + GPU-boş bu blokta **%10**'a düştü; AMA pipe-**CPU %4 (CPU %92 boş)**.
- Çıkarım: yabancı filmde uzun ASR **GPU'yu meşgul + CPU'yu bomboş** bırakır → o pencerede en verimli iş = **başka filmin CPU/IO kuyruğu** (v4_finalize/PDF). Pipelining argümanı CPU-eksenli olarak da geçerli. GPU-boş tail (ozet+PDF+v4 ≈ 190s) yine duruyor.
- **Önemli:** katalog çoğunlukla TRT **Türkçe-dublaj** (KARAYİP 2 bile `dil=tr`); gerçek yabancı-ses (ar/az) **nadir** → ASR-kısaltma kaldıracı düşük öncelik.

**(b) Paylaşımlı-kutu cezası — BEFORE/AFTER ÖLÇÜLDÜ:**
- Çekişme sırasında (cozumleme_fix/ATLAS/master eş-zamanlı): v4_finalize **280-312s** (MANASLU 280, ÖLDÜREN POZ 312).
- Çekişme bitince (05:00 sonrası, süreçler kapandı): v4_finalize **114-217s** (çoğu 130-150s).
- Ceza ~80-160s/film (en kötü hâlde). v4 kalan varyans = filmin web-arama hacmi (cast sayısı/afiş). **Doğrulama: kutuyu koşuya adamak gerçek, ölçülmüş kazanç.**
