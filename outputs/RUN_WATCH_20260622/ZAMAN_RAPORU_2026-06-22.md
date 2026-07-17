# MITAS 100-Film Koşusu — ZAMAN / PERFORMANS RAPORU
**Tarih:** 2026-06-22 · **Mod:** SALT-OKUNUR (boru hattına/commit'e dokunulmadı) · **Görev:** süreci ZAMAN açısından ölç, darboğazları bul, paralellik + ASR kısaltma kaldıraçlarını çıkar.

Veri kaynağı: `Database/*/_log.jsonl` aşama-süreleri (her aşama `duration_seconds` ile kendini ölçüyor). Örneklem: mevcut koşu + son ~3 günde **57 film** (aggregator: `outputs/RUN_WATCH_20260622/timing_agg.py`).

---

## 0) TEK SAYFA ÖZET

- **Film başına wall-clock ≈ 9–10.5 dk** (temiz Türkçe film, mevcut config). 100 film **seri** → ~**16–18 saat**.
- Filmler **tek-tek (seri)** işleniyor. `mitas_pipeline.py` tek video işler; `asr_server` kuyruğu FIFO besler. **Film-paralelliği YOK.**
- **GPU, her filmin ~%40'ında BOŞTA** (PDF + v4_finalize kuyruğu ~210s CPU/ağ işi; ölçüm anında GPU **%1**, 15 GB VRAM boş). → Paralellik için bedava kapasite var.
- En büyük 3 seri aşama wall'un **%73'ü**: **v4_finalize 150s** + **OCR∥ASR bloğu 141s** + **cozumleme 87s**.
- **ASR kritik yolda** (kod satır 1564 join-bariyeri): boru hattı `credit_text`'e geçmeden ASR'ı bekliyor — oysa ASR çıktısı SADECE özette kullanılıyor, künyeyi etkilemiyor.
- **Türkçe ASR zaten optimal** (turbo+beam1+lean+VAD, ~141s). Asıl ASR derdi **yabancı/müzikli filmler**: ARŞIN MAL ALAN (az, operet) = **1022s = 7×**.

---

## 1) AŞAMA-SÜRE PROFİLİ (57 film, saniye)

| Aşama | Kaynak | Ortalama | Medyan | Maks | Kritik yolda mı? |
|---|---|---:|---:|---:|---|
| cozumleme (decode+credit_detect+frame) | CPU/ffmpeg + CLIP(GPU) | 91 | **87** | 126 | Evet |
| OCR | GPU (OneOCR/Paddle) | 96 | 84 | 212 | ASR ile paralel |
| **ASR** | GPU (Whisper turbo) | 175 | **141** | **1022** | **Evet (join-bariyeri)** |
| credit_text (rol-eşleme) | CPU/GLM | 32 | 24 | 361 | Evet |
| VL-fallback (gemma4, **%60 film**) | GPU (ollama) | 53 | 35 | 296 | Kısmen |
| ozet | **Bulut LLM** (Sonnet→…) | ~20 | — | — | Evet (PDF'ten önce) |
| PDF teslim | CPU render | 66 | 62 | 120 | Evet |
| **v4_finalize** | CPU/IO + duckdb + **web** | 156 | **150** | 251 | **Evet** |
| qwen final-QC | GPU (qwen2.5vl) | ~15 | 15 | — | Evet |

> Not: Bazı filmlerde wall=8-9 saat görünür → bunlar `_2` son-ekli **yeniden-işlenen** filmler (log iki ayrı oturuma yayılıyor). Aşama-süreleri tek-ölçüm olduğu için sağlam; wall-clock'ta bu filmler ayıklandı.

### Tipik Türkçe film kritik yolu (medyan):
```
cozumleme 87 → [OCR 84 ∥ ASR 141]=141 → credit_text 24 → VL ~21(0.6×35)
            → ozet ~20 → PDF 62 → v4_finalize 150 → qwen_qc 15   ≈ 520s (8.7 dk)
```
Wall'un dağılımı: **v4_finalize %29 · OCR∥ASR %27 · cozumleme %17 · PDF %12 · credit_text+VL %9 · ozet %4 · qwen %3.**

---

## 2) "NELER UZUN SÜRÜYOR" — DARBOĞAZLAR

**① v4_finalize — 150s, tek en büyük seri aşama (wall'un %29).**
`scripts/tek_film_kunye.py` ayrı bir GLOBAL-python alt-süreci olarak: (a) OneOCR künye-okuma (venvs/ocr cold-start ~15-20s), (b) duckdb KB cross-check (IMDb/Wikidata), (c) IMDb/afiş **web-fetch**, (d) reportlab PDF render. CPU/IO/ağ-bağımlı, **GPU boşta**. `credit_validate` aşaması zaten IMDb/wiki sorgusu yapıyor → v4_finalize'in cross-check'i ile **muhtemel tekrar**. (kanıt: `tek_film_kunye.py:7-12, 308-393`)

**② OCR∥ASR bloğu — 141s (gated by ASR).** OCR (84s) ve ASR (141s) paralel; ama kod ASR'ı `communicate()` ile bekliyor (`mitas_pipeline.py:1564`) → blok **ASR'ın** süresinde kapanıyor. Türkçe'de ASR ~60-80s OCR'dan uzun → bu fark katıksız bekleme.

**③ cozumleme — 87s.** ffmpeg decode + credit_detect (CLIP) + 2fps kare çıkarımı. İki jenerik dedektörü (`MITAS_CREDIT_DETECT` + `MITAS_JENERIK_DETECT`) aynı anda aktif.

**④ PDF — 62s.** kunye+özet+metadata render + altyazı/kanal-dil + Paddle re-scan.

---

## 3) PARALEL İKİ FİLM ÇALIŞABİLİR Mİ? — EVET, ama "naif 2'li" DEĞİL

**Fizibilite kanıtı:**
- Ölçüm anında **GPU %1, 9.6/24 GB** → **15 GB boş VRAM**. Tek film tepe ~12-13 GB. Donanım iki filmi kaldırır.
- Her film **~210s** (PDF 62 + v4_finalize 150) boyunca **GPU'yu hiç kullanmıyor** (CPU/ağ). Bu pencere bedava.

**Neden naif "aynı anda 2 film başlat" ÇALIŞMAZ** (geçmişte denenip geri alındı — git `5e8bd9b20d` revert): iki filmin GPU-ağır ön-yarısı (cozumleme+OCR+ASR+VL) **çakışır**; eski 19 GB VRAM-guard, ollama-eviction'ı saymadığı için VL'de **stall** yaptı.

**Doğru tasarım = KADEMELİ (staggered) pipelining:**
- Film N+1'in **GPU-ön-yarısını**, Film N'in **CPU/ağ-kuyruğu (PDF+v4_finalize, ~210s)** sırasında başlat. İki film GPU'ya nadiren aynı anda vurur.
- Teorik kazanç: **~1.5–1.8× throughput** (GPU çakışması olmadan), 100 film ~18 saat → **~10-12 saat**.
- Alternatif: kaynak-farkında zamanlayıcı (aynı anda yalnız 1 film "GPU-ağır fazda"). Saf "2 paralel subprocess"ten daha güvenli.

> Bu rapor uygulamıyor — yalnız kaldıracı gösteriyor. Uygulanırsa `asr_server` kuyruk mantığında staggered-dispatch + faz-kilidi gerekir.

---

## 4) ASR KISALTILABİLİR Mİ? — İKİ AYRI DURUM

**Önce güvenlik teyidi:** Transkript **SADECE özet** üretiminde kullanılıyor (`mitas_pipeline.py:1756`); künye OCR/VL yolundan **bağımsız**. → ASR'ı agresif kısaltmak **künyeyi bozmaz** (yalnız özet kalitesi etkilenir). Bu, ASR optimizasyonunu düşük-riskli yapar.

### 4a) Türkçe filmler — zaten optimal (~141s)
`lean-large-v3-turbo`: diarize/align/fallback KAPALI, beam=1, VAD açık, `condition_on_previous_text=False`. Çıkarılacak yağ kalmamış.
**Tek kaldıraç → kritik yoldan ayır:** ASR'ı `credit_text`'ten önce değil, **özetten hemen önce** join et. Böylece ASR'ın ~141s'i credit_text(24)+VL(35)+validate(~20) ile örtüşür → film başına **~60-80s** gizlenir. 100 film × ~70s ≈ **~2 saat** kazanç. Risk düşük (ASR çıktısı zaten geç lazım).

### 4b) Yabancı/müzikli filmler — ASIL SORUN (7× yavaş)
ARŞIN MAL ALAN (1917 operet, dil=`az`): **1022s**; diğer yabancılar 391-500s. Türkçe ~141s. Kök neden (koddan):
1. **tr-dışı dil → large-v3** (turbo değil, ~2×) — `_pipe_asr.py:157-169`.
2. **Whisper temperature-fallback** (varsayılan, override YOK): müzik/sessizlik segmentleri kalite-eşiğini (compression_ratio 2.4, no_speech 0.6) geçemeyince segment **tekrar tekrar** decode edilir (≤6×). ARŞIN'in ilerleme logu sıçramalı: bazı yerlerde 100s'de yalnız 20s ses → klasik fallback-döngüsü kanıtı.

**Kaldıraçlar (özet-only olduğu için güvenli, hepsi kod değişikliği — şu an env-flag YOK):**
- Yabancıda **turbo'da kal** (large-v3 yerine) → ~2× hız.
- **Temperature fallback'i sınırla** (örn. `temperature=[0.0, 0.2]`) → müzikli filmde tekrar-decode patlamasını keser.
- **VAD `min_silence_duration_ms`'i artır** (500→800-1000ms) → müzik aralarında segment-patlamasını azaltır.
- Mevcut env: yalnız `MITAS_ASR_FOREIGN_BEAM` (min=1, faydası sınırlı).

---

## 5) ÖNCELİKLİ KALDIRAÇLAR (etki/risk)

| # | Kaldıraç | Tahmini kazanç | Risk | Tür |
|---|---|---|---|---|
| A | **Kademeli film-pipelining** (GPU-boş tail'i N+1 ile doldur) | **~1.5-1.8× throughput** (~6-8 saat) | Orta (VRAM faz-kilidi gerekir) | Mimari |
| B | **v4_finalize** redundans/cache (cross-check + cold-start) | film başı ~40-80s | Orta (KB-doğrulama yolu) | Kod |
| C | **ASR'ı kritik yoldan ayır** (özetten önce join) | ~60-80s/film (~2 saat) | Düşük | Kod |
| D | **Yabancı/müzik ASR** (turbo + temp-cap + VAD) | en kötü filmlerde 3-7× | Düşük (özet-only) | Kod |
| E | **VL-fallback tetik azalt** (OCR/credit_text recall) | %60 filmde 35-90s | Düşük | Kalite |

---

## 6) MEVCUT KOŞU DURUMU (canlı, 02:20 itibarıyla)
Seri ilerliyor, ~11 dk/film kadansı: RED ROCK (01:46) → HAYATIN DENGESİ (01:57) → SIRILSIKLAM (02:08) → YAĞMUR (02:19) → … Tahmini 100-film tamamı: **~18 saat** (mevcut seri tasarımla).

---
*Aggregator'ı tekrar koşmak için:* `python outputs/RUN_WATCH_20260622/timing_agg.py <epoch_cutoff>`
