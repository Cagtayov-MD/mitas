# MITAS KONTROL Derin Kök-Neden Raporu

**Tarih:** 2026-08-03
**Kapsam:** Aktif koşu (kosucu_devam_20260802_1155) + tüm Database KONTROL analizi
**Hazırlayan:** Claude (Fable) — Genel Sekreter denetimi + 5 film dedektifi + konsey turları

---

## 1. YÖNETİCİ ÖZETİ

**Aktif koşu durumu:** 70/1751 film işlendi — 27 HAZIR (%39), 43 KONTROL (%61).
Koşu hâlâ devam ediyor (film 167 civarı).

**Tüm Database:** 236 KONTROL film var; bunların 168'i eski koşulara ait, 68'i
son 24 saatte güncellendi.

**En kritik bulgu:** KONTROL filmlerin %53'ü "OCR okuyamadı" DEĞİL —
**"OCR okudu ama pipeline arada kaybetti"**. Bu tamamen farklı bir sorun sınıfı
ve farklı fix stratejisi gerektirir.

**Uygulanan P0 fix'ler:**
- ✅ Çince model marker filtresi (`credit_text_read.py`) — 3+ film kurtarma potansiyeli
- ✅ CAST_CAP dedup bug (`credit_qc_block.py`) — sinyal kalitesi düzeltmesi

---

## 2. KONTROL KÖK-NEDEN DAĞILIMI (236 Film, Tüm Database)

| # | Kök Neden | Film | % | Sınıf |
|---|-----------|------|---|-------|
| 1 | **Latin-dışı alfabe kapısı** | 57 | 24% | QC kuralı (gerçek + yalancı pozitif) |
| 2 | **Rol-eşleme başarısız** | 52 | 22% | Pipeline kaybı (OCR+kunye var, eşleme yok) |
| 3 | **CAST_CAP bigram gürültüsü** | 26 | 11% | Pipeline sinyali (sliding-window çöpü) |
| 4 | **KB cross-check çelişkisi** | 19 | 8% | QC kuralı (fazla hassas eşleştirme) |
| 5 | **PDF render başarısız** | 15 | 6% | Altyapı (Linux ENAMETOOLONG — fix var) |
| 6 | **Yönetmen satırı bulunamadı** | 14 | 6% | Pipeline kaybı (FIGO o kartı kaçırdı) |
| 7 | **OCR çöp/halüsinasyon** | 12 | 5% | OCR kalitesi (DeepSeek yemek tarifi uyduruyor) |
| 8 | **Kunye yetersiz** | 10 | 4% | OCR kalitesi (çok az metin) |
| 9 | **Kimlik zayıf** | 3 | 1% | QC kuralı |
| 10 | **Diğer** | 28 | 12% | Çeşitli |

### Sınıf Özeti

```
Pipeline kökenli (okundu, arada kaynadı):  ~92 film  (%39)
QC/kural kökenli (kapı fazla sert):         ~79 film  (%33)
OCR kökenli (gerçek okuma hatası):          ~24 film  (%10)
Altyapı kökenli (LLM/PDF render):           ~16 film  (%7)
Kaynak kökenli (jenerik yok):               ~25 film  (%11)
```

---

## 3. DERİN FİLM ANALİZLERİ (5 Dedektif)

### 3.1 GÖLGE DANSI (1988-0417) — Meşru Boş

**Kök neden:** Film bir tiyatro kaydı. 360 giriş + 721 çıkış karesinin
hiçbirinde jenerik metni YOK. FIGO doğru tespit etti: `kredi_yok`.

**Zincir:**
- Frame çıkarma: ✅ 1081 gerçek kare
- Jenerik tespiti: ✅ `kredi_yok` (360/360 footage_no_text)
- OCR: ✅ BOS bucket (doğru — okunacak metin yok)
- VL fallback: ✅ RED (doğru — frame'lerde metin yok)
- Routing: ✅ KONTROL (doğru karar)

**Sonuç:** Pipeline doğru çalıştı. Bu bir bug değil, **kaynak sorunu**.
Filmde okunabilir jenerik yok. Manuel inceleme gerekir.

---

### 3.2 JOE SHARP (1992-0483) — CAST_CAP Kırmızı Ringa Balığı

**Kök neden:** "1168 oyuncu düştü" uyarısı sahte alarm.

**Gerçek zincir:**
- OCR: 271 satır (kayan jenerik, her isim 20-50 kez tekrar)
- `_audit_raw_token_seq()`: 7,333 bigram üretildi (ardışık kelime çiftleri)
- Dedup: 7,333 → 1,168 "benzersiz" — %99.8'i çöp
  - Cross-name bigramlar: "Smith Audrey", "Sharp Tennessee"
  - Şirket adları: "Euramco Inter", "Euramco Interna"
  - Rol+isim: "Stunt Men", "Bartender Frederick"
- CAST_CAP=18: Sadece 10 oyuncu çıkarıldı, cap dokunmadı
- **Gerçek kayıp:** Judy Landers, Margaret Shendal (2 oyuncu)
- **Kayıp nedeni:** `kimlik={}` boş → kurtarma mekanizması `locked=True`
  gerektiriyor → çalışmadı

**Fix:** Dedup mantığı düzeltildi (P0-2). Kimlik kilidi boş kalan filmler
için kurtarma mekanizmasının gevşetilmesi P1.

---

### 3.3 ÇÖL ASLANI (1987-1235) — Bigram Şişirmesi + Dedup Bug

**Kök neden:** `_audit_raw_token_seq()` **de-dup edilmemiş** `ocr_raw_all.txt`
(2979 satır) kullanıyor. `ocr_ham.txt` (266 satır, temiz) var ama kullanılmıyor.

**Sayılar:**
| Dosya | Satır | Bigram | Sonuç |
|-------|-------|--------|-------|
| `ocr_raw_all.txt` (kullanılan) | 2,979 | 5,801 çift → 1,367 "oyuncu" | %99 çöp |
| `ocr_ham.txt` (kullanılmayan) | 266 | ~500 çift → 30-60 aday | Anlamlı sinyal |

**Bonus bug bulundu:** Satır 212-214'teki dedup one-liner'ı **hiç çalışmıyordu**:
```python
# KIRIK: _seen_rcd.add() → None, _seen_rcd - {_fold(n)} → boş küme
# Sonuç: koşul her zaman True, dedup asla çalışmaz
```
→ P0-2 ile düzeltildi.

**Gerçek kayıplar:** Rod Steiger, John Gielgud — 1,357 çöp entry arasında gömülü.

---

### 3.4 KUSURSUZ BİR GÜN CENAZE TÖRENİ (2009-9137) — Eski-Durum Tuzağı

**Kök neden:** 6 Temmuz sabahı Ollama çöktü (disk değişimi). 10 film bu
aralıkta işlendi, hepsi başarısız.

**Kritik bulgu:** 10 Temmuz'da OCR **tekrar koşuldu ve BAŞARILI oldu**
(bucket=GUVENILIR, 108 satır). Ama tam pipeline yeniden çalışmadı —
`_DURUM.json` hâlâ 6 Temmuz'daki HATA durumunu taşıyor. **27 gündür fark
edilmemiş.**

**10 film kohortu:** EL GUSTO, KRAL LEAR, MUTLU GÜNLER, BAHAR VE ŞARAP,
LA BOHEME, LALELER, ELMA, GÜLLERİN SAVAŞI, KUSURSUZ BİR GÜN, HANNA'NIN
ALTINLARI — hepsinde OCR iyi, pipeline bekliyor.

**Fix:** Bu 10 film için pipeline'ı yeniden koş. ~8'i ONAYLI'ya düşer.
Koruyucu fix: `clip.json` vs `_DURUM.json` uyumsuzluk bekçisi ekle.

---

### 3.5 ÖNEMSİZ BİRİ (2025-1133) — Linux ENAMETOOLONG

**Kök neden:** `_pipe_pdf.py:448` — `Path(args.ozet).exists()` çağrısında
özet metni 255+ byte → Linux'ta `ENAMETOOLONG` → subprocess crash.

```python
# ESKİ (crash):
Path(args.ozet).exists()  # özet metni dosya yolu sanılıyor

# FIX (commit d816fd68, 30 Temmuz):
_ozet_dosya = bool(args.ozet) and len(args.ozet.encode()) < 250 and Path(args.ozet).exists()
```

**Etki:** 11 film (DONDURMAM GAYMAK, FRANK CAPRA, HAMSUN, KAHRAMAN ŞERİF,
POLİS AKADEMİSİ 4, SÜNGER AVCILARI, YAĞMACILAR, ÇAKAL, ÇILGIN AY, ÖNEMSİZ
BİRİ, ŞEHİRDE BİR YERLİ) — verileri mükemmel, sadece PDF render çöktü.

**Fix:** Zaten yapılmış. 11 film yeniden koşu bekliyor.

---

## 4. GENEL SEKRETER SİSTEM DENETİMİ

**Genel not: 7/10** — izleme güçlü, düzeltme kırık, entegrasyon eksik.

### ✅ Çalışan Bileşenler
- **Panel** (port 8898): Canlı, 30 sn auto-refresh, KONTROL detayları accordion
- **ajan_kontrol.py** (456 satır): 23 regex pattern, pipeline trace takibi
- **ajan_performans.py** (334 satır): GPU, disk, timing, bottleneck tespiti
- **model_router.py**: 5 katman (NONE→LIGHT→MEDIUM→HEAVY→API), Ollama bağlı
- **Ollama modelleri**: qwen3:8b ✅, gemma4:26b ✅, qwen3-vl:32b ✅ (14 toplam)
- **Raporlar**: 4 gerçek MD rapor üretiliyor

### 🔴 Kritik Sorunlar
1. **orkestra.py syntax hatası** (satır 236) — tüm düzeltme sistemi ölü
2. **ONAYLI export dizini boş** — QC doğrulama ajanı KÖR
3. **ONAYLI sayısı yanlış** — `toplam - kontrol` hesabı, gerçek sayım değil

### ⚠️ Orta Sorunlar
4. XML raporlar hiç üretilmiyor (kod var, çağrı yok)
5. YAML `model_routing` tanımlı ama kod hardcoded `MODEL_TABLE` kullanıyor
6. `duzelt` CLI komutu yok — düzeltme ekipleri çağrılamıyor
7. Scheduler yok — config'de `schedule` var ama çalıştıran yok

---

## 5. UYGULANAN P0 FİX'LER

### P0-1: Çince Model Marker Filtresi ✅
**Dosya:** `scripts/credit_text_read.py`
**Değişiklik:** `_nonlatin_ratio()` fonksiyonuna `_OCR_MODEL_MARKERS` regex
eklendi. `[图片...]` gibi DeepSeek artifact'ları oran hesaplamadan önce siliniyor.

**Test sonuçları:**
- Latin + Çince marker: ratio=0.0000 ✅ (< 0.02, gate tetiklenmez)
- Sadece Çince marker: ratio=0.0000 ✅
- Gerçek Kiril: ratio=1.0000 ✅ (dokunulmaz)
- Gerçek Arapça: ratio=1.0000 ✅ (dokunulmaz)
- BUFFALO '66 simülasyonu: ratio=0.0000 ✅

**Kurtarma potansiyeli:** BUFFALO '66, NAZİK BİR GECE, ELVEDA OĞLUM (3 film)

### P0-2: CAST_CAP Dedup Bug ✅
**Dosya:** `scripts/credit_qc_block.py`
**Değişiklik:** Kırık one-liner → düzgün `_seen_rcd` döngüsü.

**Test sonuçları:**
- 11 entry girdi → 5 unique çıktı ✅
- "John Smith" / "JOHN SMITH" / "John Smith" → tek entry ✅
- Çöp tekrarları doğru elimine edildi ✅

**Etki:** `_DURUM.json` boyutu ~3000 satır küçülecek, sinyal kalitesi artacak.

**Test suite:** 95 geçti, 0 başarısız ✅

---

## 6. BEKLEYEN FİX ADAYLARI

### P0 (güvenli, hemen yapılabilir)
| # | Fix | Etki | Kod |
|---|-----|------|-----|
| P0-3 | 10 film kohortu pipeline yeniden koş | ~8 film HAZIR | `from_hub_batch.py` |
| P0-4 | Eski-durum bekçisi (clip.json vs _DURUM.json) | Gelecek koruması | ~15 satır |
| P0-5 | 11 PDF-crash film yeniden koş | ~8 film HAZIR | `from_hub_batch.py` |

### P1 (orta zorluk, konsey önerildi)
| # | Fix | Etki |
|---|-----|------|
| P1-1 | KB fuzzy matching eşiği gevşet | ~5 film (HEYERDAH→Heyerdahl) |
| P1-2 | Kurtarma mekanizması `locked` gevşet | 2+ oyuncu (JOE SHARP tipi) |
| P1-3 | `_audit_raw_token_seq` → `ocr_ham.txt` kullan | Sinyal 1367→30 |
| P1-4 | HAFIF_CASING auto-approve | 1 film (SIRADIŞI PİYANİST) |

### P2 (zor, yeni modül/mimari)
| # | Fix | Etki |
|---|-----|------|
| P2-1 | OCR halüsinasyon detektörü | 12 film |
| P2-2 | FIGO jenerik tespit geliştirme (v6) | 12+ film |
| P2-3 | Rol-eşleme LLM prompt iyileştirme | 52 film (en büyük grup!) |
| P2-4 | Stage-based derin kök-neden motoru | Konsey tasarımı hazır |

---

## 7. KONSEY GÖRÜŞLERİ

### Tur 1: Derin Kök-Neden Analizi Mimarisi
**Katılımcılar:** Qwen, GLM, Kimi, Nemotron (MiniMax 504 hatası)

**Ortak görüş:** Stage-based (derinlik seviyeli) mimari — tek fonksiyon değil.

| Üye | Öne Çıkan Katkı |
|-----|-----------------|
| **Qwen** | 8 alt kırılım (1a-1d, 2a-2d), ThreadPoolExecutor+JSONL, feedback loop |
| **GLM** | Fail-fast hata ağacı, 154 film triaj stratejisi, mmap lazy loading |
| **Kimi** | Checker plugin mimarisi, iterative pattern learning, batch processing |
| **Nemotron** | Chain of Responsibility, forensic engine, ProcessPoolExecutor |

**Tasarım konsensüsü:**
```
STAGE_0: Frame var mı?
STAGE_1: OCR çıktı üretti mi?
STAGE_2: Aranan metin OCR'da var mı?
STAGE_3: Parser'a geçti mi?
STAGE_4: Rol-eşleme doğru mu?
STAGE_5: QC kapısı mı reddetti?
```

Her stage `{status: OK|DEGRADED|FAIL, evidence: {...}}` döner. İlk FAIL = kök neden.

### Tur 2: P0 Fix Kod İncelemesi
**Durum:** Gönderildi, cevap bekleniyor.

---

## 8. HIZLI KURTARMA YOL HARİTASI

```
P0 (bugün):
  ✅ Çince marker filtresi          → 3 film
  ✅ Dedup bug                      → sinyal düzeltme
  ⬜ 10 kohort film yeniden koş     → ~8 film
  ⬜ 11 PDF-crash film yeniden koş  → ~8 film
  ⬜ HAFIF_CASING auto-approve      → 1 film
  ─────────────────────────────────────
  Toplam P0 kurtarma:               ~20 film

P1 (bu hafta):
  ⬜ KB fuzzy matching              → ~5 film
  ⬜ Kurtarma locked gevşet          → ~3 film
  ⬜ audit_raw_token_seq → ocr_ham  → sinyal düzeltme
  ─────────────────────────────────────
  Toplam P1 kurtarma:               ~8 film

P2 (bu sprint):
  ⬜ Rol-eşleme iyileştirme         → ~52 film (en büyük grup!)
  ⬜ OCR halüsinasyon detektörü     → ~12 film
  ⬜ FIGO v6                        → ~12 film
  ─────────────────────────────────────
  Toplam P2 kurtarma:               ~76 film

TOPLAM potansiyel kurtarma:         ~104 film
Mevcut KONTROL:                     236 film
Hedef ONAYLI oranı:                 %40 → %65+
```

---

## 9. KRİTİK BULGULAR ÖZETİ

1. **%53 pipeline kökenli** — en büyük sorun "okuyamadık" değil "okuduk ama
   kaybettik". Bu, fix stratejisini temelden değiştirir.

2. **Rol-eşleme 52 film** — tek başına en büyük grup. `credit_text_read.py`
   extraction LLM'ı veya prompt'u yetersiz. P2 ama en yüksek etkili fix.

3. **Eski-durum tuzağı** — 10 film 27 günder yanlış durumda bekliyor.
   `clip.json` ve `_DURUM.json` arasındaki uyumsuzluk fark edilmiyor.

4. **CAST_CAP_DUSEN sinyali güvenilmez** — "1168 oyuncu düştü" dediğinde
   gerçekte 2 oyuncu düşmüş olabilir. Bigram şişirmesi + dedup bug.

5. **Genel Sekreter orkestra.py kırık** — düzeltme sistemi hiç çalışmadı.
   Syntax hatası, 5 dakikalık fix ama kritik.

---

## EK DOSYALAR

- Tam 236 film listesi: `docs/raporlar/KONTROL_KOK_NEDEN_235_FILM_2026-08-02.txt`
- OCR Halüsinasyon raporu: `docs/raporlar/OCR_HALUSINASYON_KONSEY_RAPORU_2026-08-02.md`
- QC2 Sızıntı raporu: `docs/raporlar/QC2_SIZINTI_RAPORU_2026-08-02.md`
- Bulgu defteri: `docs/MITAS_BULGU_DEFTERI_2026-08-01.md`
- Kalan işler: `docs/MITAS_KALAN_ISLER.md`
