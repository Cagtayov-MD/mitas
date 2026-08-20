# 📋 Sandbox Log — Model Test Kayıtları

---

## 2026-08-12 — Oturum 1: Nemotron Nano 12B V2 VL Testi
- **Model:** `nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-FP8` (15GB)
- **Framework:** `vLLM 0.27.1` (nightly)
- **Kazanım:** `video-pruning-rate=0.0` ile %100 jenerik okuma doğruluğu sağlandı.
- **Rapor:** `results/NEMOTRON_NANO_VL_RAPOR.md`

---

## 2026-08-12 — Oturum 2: Qwen Modellerinin Hazırlanması
- **İndirilen Modeller:**
  1. `Qwen/Qwen3.5-9B` (19GB) → `scratch/model_sandbox/models_local/qwen3.5-9b`
  2. `Qwen/Qwen3-VL-8B-Instruct` (17GB) → `scratch/model_sandbox/models_local/qwen3-vl-8b-instruct`
- **Durum:** ✅ Tamamlandı.

---

## 2026-08-12 — Oturum 3: MiniCPM ve InternVL Modelleri
- **İndirilen Modeller:**
  1. `openbmb/MiniCPM-V-4.6` (2.5GB) → `scratch/model_sandbox/models_local/minicpm-v-4.5`
  2. `OpenGVLab/InternVL3-8B` (15GB) → `scratch/model_sandbox/models_local/internvl3-8b`
- **Durum:** ✅ Tamamlandı.

---

## 2026-08-13 — SANDBOX KAPATILDI

Sandbox'ın ürettiği bilgi **Allstar/jordan** kulesine devredildi; bu alanda
yeni deney yapılmıyor.

**Taşınan.** `models_local/qwen3.5-9b` (bf16, 19 GB) →
`Allstar/jordan/model/bf16`. Kulenin ikinci checkpoint'i (INT8 w8a8, 14 GB)
ayrıca indirildi; varsayılan odur.

**Jordan'a geçen kanıtlar (buradaki koşulardan):**
- `results_39_films_9b_ffmpeg/` → **39/39 CUDA OOM**, 36 kare/çağrı @720p.
  Jordan'ın parçalama zorunluluğunun ve `parca.kare_tavani` freninin gerekçesi.
- `user_9b_chunk_pipeline_results/` → 15 sn parça + 2 sn bindirme, fps=2,
  30 kare/çağrı ÇALIŞTI. Jordan'ın `config.yaml` varsayılanları buradan.
- Aynı koşunun ham çıktısında **düşünme sızıntısı** (`</think>` iki kez, cevap
  mükerrer) → Jordan'da `dusunme: false` + sızıntı ayıklayıcı + sayaç.
- `run_39_films_qwen9b_ffmpeg.py` → keskinleştirme reçetesi
  (`lanczos + hqdn3d + unsharp`, 720p). Jordan'ın `video.suzgec`'i bu.

**SİLİNMEDİ.** Script'ler, sonuç klasörleri ve loglar duruyor — yukarıdaki
ayarların kanıt kaynağı burası. Silinecekse ayrı bir karar gerekir.
