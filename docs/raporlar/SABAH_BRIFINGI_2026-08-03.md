# MITAS Sabah Brifingi — 2026-08-03

**Hazırlayan:** Claude (Fable) — gece oturumu
**Son güncelleme:** 00:30 civarı

---

## Gece Ne Yapıldı

### ✅ Uygulanan Fix'ler (6 adet)

| # | Fix | Dosya | Risk |
|---|-----|-------|------|
| 1 | Çince model marker filtresi | `credit_text_read.py` | Sıfır — sadece OCR artifact temizliği |
| 2 | CAST_CAP dedup bug | `credit_qc_block.py` | Sıfır — audit log düzeltmesi |
| 3 | `mitas_roots.py` fallback `E:\MITAS` → `/opt/mitas` | `mitas_roots.py` | Sıfır — Windows kalıntısı temizlendi |
| 4 | `asr_server.py` `Path("E:\\")` Linux guard | `core/api/asr_server.py` | Sıfır — `os.name == "nt"` koruması |
| 5 | 5 bare `except:` → `except Exception:` | 3 dosya | Sıfır — Ctrl+C artık çalışıyor |
| 6 | `.bashrc`'ye `MITAS_PROJECT_ROOT` eklendi | `~/.bashrc` | Sıfır — shell/cron artık doğru yolu buluyor |

### ✅ Altyapı

| İşlem | Durum |
|-------|-------|
| Swap 8→16 GB | ✅ Tamamlandı, fstab'da kayıtlı |
| `E:\MITAS` hayalet dizin silindi | ✅ 160 KB temizlendi |
| Genel Sekreter denetimi | ✅ 7/10 — orkestra.py hâlâ kırık (P1) |
| 236 KONTROL film analizi | ✅ Rapor: `KONTROL_DERIN_KOK_NEDEN_RAPORU_2026-08-03.md` |

### 🔄 Gece Boyu Devam Eden

**Üretim koşusu:** ~173/1751 (saat ~00:30). ~9 film/saat hızla devam ediyor.
Sabah 08:00'e kadar tahminen ~240 film daha işlenecek = **~410/1751**.
Staging kuyrukta sadece 2 MP4 kaldı — koşu neredeyse bitmek üzere.

### ✅ Teslimat Kurtarma (gece keşif — 69 PDF)

**Kritik bulgu:** 57 ONAYLI + 12 KONTROL filmin PDF'i `export/` klasörüne hiç
kopyalanmamıştı. Hub'da (`Database/FİLM/pdf/kunye.pdf`) mevcut ama teslim
dizininde yoktu.

**Kök neden:** `mitas_roots.py`'nin Windows-path fallback'i (`E:\MITAS`) yüzünden
eski pipeline koşusu teslimat yolunu yanlış hesapladı. P0 fix (fallback → `/opt/mitas`)
+ `.bashrc` env değişkeni bu sorunu çözdü — son 4 film (20:34 sonrası) doğru teslim edildi.

**Kurtarma:** Tüm 69 PDF hub'dan kopyalandı. ONAYLI: 4 → 61 dosya. KONTROL: 83 → 95 dosya.

---

## Konsey Kararları (3 tur tamamlandı)

### Tur 1: Derinlik analizi mimarisi
**Sonuç:** 4 üye (Qwen, GLM, Kimi, Nemotron) stage-based tasarımda hemfikir.
6 aşamalı zincir: Frame → OCR → OCR-match → Parser → Role-match → QC.

### Tur 2: P0 fix kod incelemesi
**Sonuç:** Her iki fix onaylandı. Konsey önerileri uygulandı:
- `re.IGNORECASE` eklendi
- Pattern'lar genişletildi (7 kalıp)
- GLM edge-case koruması eklendi (tam çöp metin → ratio=1.0)

### Tur 3: P0-3 yeniden koşu planı
**Sonuç:**
- **Önce Grup B** (15 PDF-crash film) — sadece PDF re-render yeterli
- **Sonra Grup A** (13 eski-durum film) — full post-OCR pipeline
- **Mevcut koşu bitene kadar bekle** — paralel koşma
- **Pre-flight tarama:** ELMA, LA BOHEME, KRAL LEAR gibi jenerik isimli filmler
  metadata eşleşmesi zor olabilir — manuel inceleme adayı

### Tur 4: Altyapı fix'leri değerlendirmesi
**Durum:** Cevaplar alındı (Qwen, GLM, Kimi, Nemotron). Fix'ler zaten uygulanmıştı.
**Konsey görüşleri:**
- 4/4 üye tüm fix'leri onayladı
- Qwen/Nemotron: `.bashrc` yerine `/etc/environment` önerisi (cron/non-login shell için)
- Qwen/GLM: `swappiness=10` eklenmeli (swap kullanımını azaltır)
- Nemotron: Fix C'de short-circuit endişesi — yersiz, Python `and` kısa-devre yapar

---

## Bekleyen İşler (Sabah İçin)

### FAZA 1 — Yeniden Koşu (kod değişikliği YOK)
Mevcut koşu bitince:
1. **Grup B:** 15 PDF-crash film → sadece `_pipe_pdf.py` veya `--from-hub`
2. **Grup A:** 13 eski-durum film → `--from-hub` full pipeline
3. Beklenen kurtarma: ~20 film ONAYLI'ya

### FAZA 2 — Küçük Kod Fix'leri
- P0-4: Eski-durum bekçisi (clip.json vs _DURUM.json uyumsuzluk tespiti)
- P0-5: HAFIF_CASING auto-approve (1 film)
- Genel Sekreter: orkestra.py syntax hatası düzelt

### FAZA 3 — Orta Riskli
- P1-1: KB fuzzy matching eşiği gevşet (~5 film)
- P1-2: Kurtarma mekanizması `locked` gevşet
- P1-3: `_audit_raw_token_seq` → `ocr_ham.txt` kullan

### FAZA 4 — Büyük Balık
- P2-1: Rol-eşleme iyileştirme (52 film — en büyük grup)
- P2-2: OCR halüsinasyon detektörü
- P2-3: FIGO v6

---

## Sistem Durumu

| Kaynak | Değer | Durum |
|--------|-------|-------|
| RAM | 86 GB available / 121 GB | ✅ İyi |
| Swap | 16 GB, 0B kullanımda | ✅ İyi |
| Disk | 391 GB boş / 1.8 TB (%78) | ⚠️ Dikkat |
| GPU | 22/24 GB VRAM | ✅ Normal |
| Koşu | ~173/1751, staging 2 MP4 | 🔄 Devam |
| ONAYLI | 61 PDF (57 kurtarıldı) | ✅ Tamam |
| KONTROL | 95 PDF (12 kurtarıldı) | ✅ Tamam |

---

## Konsey Genel Değerlendirme (Tur 4)

4 üye (Qwen, GLM, Kimi, Nemotron) projeyi tarafsız değerlendirdi.
MiniMax yine 504 hatası verdi — 4/5 cevap.

### Konsensus Noktaları

| Konu | Ortak Görüş |
|------|-------------|
| **9 film/saat** | Arşiv projesi için kabul edilebilir (4/4). Hızlandırma mümkün ama bu koşuda gereksiz |
| **2810 satır main()** | Sürdürülebilir değil (4/4). Ama bu koşuda **dokunma** (3/4). Nemotron refactor istiyor |
| **%61 KONTROL** | TRT arşivi kaotik jenerikleriyle normal (4/4). Hedef %30-35 olmalı |
| **107 except Exception** | 🔴 **KRİTİK RİSK** (4/4). Sessiz hata yutma → yanlış-ONAYLI üretir |
| **Strateji** | Fix + koş (3/4). Nemotron 3-4 gün stabilize sprint öneriyor |

### En Değerli Öneriler

1. **Checkpoint/Resume** (4/4 vurguladı): Crash = baştan başla olmamalı.
   Her stage sonrası JSON state dosyası.
2. **Sessiz hataları KONTROL'e yönlendir**: `except Exception: pass` →
   `except Exception: move_to_KONTROL(film_id, reason)`. Asla sessiz ONAYLI üretme.
3. **HITL Review UI**: 1000+ KONTROL film birikecek. Streamlit/Gradio ile hızlı onay arayüzü.
4. **Model version pinning**: `qwen3:latest` değil `qwen3:14b-q4_k_m` (digest pin).
   Yarın Ollama güncellerse çıktılar değişir.
5. **Data lineage**: Her JSON'a `{model_version, prompt_hash, pipeline_version}` göm.

### Ayrışma: Nemotron vs Diğerleri

Nemotron "3-4 gün stabilize sprint, OCR batch + async LLM → 30 film/saat" diyor.
Qwen/GLM/Kimi "bu koşuda dokunma, bitir, sonra refactor" diyor.
**Claude'un değerlendirmesi:** Qwen/GLM/Kimi haklı — Prensip 2 ("sağlıklı çalışanı bozma")
gereği mevcut koşuyu hız optimizasyonuyla riske atmayız. Nemotron'un checkpoint ve
exception hierarchy önerileri koşu BİTTİKTEN sonra uygulanır.

---

## Gece Temizliği: Windows Path Kalıntıları

Pipeline-kritik 14 dosyada `r"E:\MITAS"` fallback'i `/opt/mitas` ile değiştirildi:
- `mitas_roots.py`, `_pipe_shadow_vl.py`, `_subtitle_detect.py` (manuel fix)
- `_pipe_ocr.py`, `_pipe_pdf.py`, `_jenerik_pool.py`, `_channel_lang.py`
- `credit_qc.py`, `credit_export.py`, `credit_kb_lookup.py`
- `retry_planner.py`, `giris_jenerik_havuzu.py`, `alignment_subprocess.py`,
  `enqueue_local_films.py`, `run_manifest.py` (sed batch)

Kalan env-fallback pattern: **0**. Tüm pipeline kökleri `/opt/mitas` altında doğrulandı.
(Not: ~20 utility/analiz script'inde hâlâ hardcoded `E:\MITAS` var — bunlar pipeline
dışı, düşük öncelikli.)

---

## Kritik Raporlar

| Rapor | Konum |
|-------|-------|
| KONTROL kök-neden (236 film) | `docs/raporlar/KONTROL_DERIN_KOK_NEDEN_RAPORU_2026-08-03.md` |
| 236 film detaylı liste | `docs/raporlar/KONTROL_KOK_NEDEN_235_FILM_2026-08-02.txt` |
| Sistem taraması (tarafsız göz) | Bu dosyanın alt bölümü |
| OCR halüsinasyon raporu | `docs/raporlar/OCR_HALUSINASYON_KONSEY_RAPORU_2026-08-02.md` |
| QC2 sızıntı raporu | `docs/raporlar/QC2_SIZINTI_RAPORU_2026-08-02.md` |
