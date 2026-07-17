# Giriş Jeneriği OCR Kök-Neden Raporu — "Sistem niye okumuyor da KB doldurmaya gerek kalıyor?"

**Tarih:** 2026-06-29 · **Vaka:** ŞERİF SHAUGNESSY (1996 ABD/CBS, TV filmi), TRT 1996-0177-1-0000-00-1
**Tetikleyen soru:** Sarah Paulson + Michael Jai White OCR'da okunmadı, `kb_floor` (KB) doldurdu. Frame'de varlar mı? Varsa neden okunmadı?

---

## 1. CEVAP (özet)
Oyuncular **frame'de VAR ve nettir** — OCR okuyamadı. Çünkü:
1. ŞERİF jeneriği **sahne-üstü overlay** formatında (isimler ayrı kartta değil, akan film sahnesinin üstünde).
2. **OneOCR bu formatı tek-kareden çözemiyor** (düşük kontrast, sahne baskın).
3. Bunu çözebilecek **master-PNG (slit-scan)** mekanizması ne girişe uygulanıyor ne de ana OCR'a bağlı.

→ OCR doğru okusa `kb_floor`'a (KB doldurma) hiç gerek kalmayacaktı. Kök sorun OCR/jenerik tarafında.

---

## 2. KANIT

### Frame'de var (görsel)
- `frames/giris/g_0082.png` → **"SARAH PAULSON"** altın overlay NET okunuyor (sahne üstünde).
- (Michael Jai White: aynı format, komşu overlay aralığında; OCR onu da okumadı.)

### OCR okumadı (veri)
- `ocr_raw_all.txt` / `kunye.txt` → "PAULSON" / "JAI WHITE" **hiç yok** (ne doğru ne garble).
- `ocr_raw_reads.jsonl` (giriş segmenti): frame 55-75 → MATTHEW SETTLE, LINDA KOZLOWSKI, TOM BOWER okundu; **frame 76-88 hiç okuma yok** (Sarah Paulson tam burada); frame 89+ sahne footage → "N", "Z", "NEW" çöp.

### Sayısal asimetri (`ocr_summary.json`)
| Ölçü | Değer | Yorum |
|---|---|---|
| frame_count | 840 | giriş 360 + çıkış 480, hepsi işlendi |
| credit_frames | 774 | CLIP kareleri kredi saydı (frame 82 elenmedi) |
| OCR okuma — giriş | **67** | sahne-üstü overlay → OneOCR çözemedi |
| OCR okuma — çıkış | **819** | roll-credit (ayrı kart) → kolay okundu |
| master_png | **null** | master ana OCR'a beslenmedi |
| master_lines_count | **0** | master'ın katkısı sıfır |

**Çıkış jeneriği (roll-credit, ayrı kart, yüksek kontrast) tertemiz okundu (crew). Giriş jeneriği (sahne-üstü overlay) okunamadı.** Sorun format + okuma kalitesi.

---

## 3. KÖK-NEDEN (kod seviyesi)

### a) Giriş için jenerik havuzu / master-PNG ÜRETİLMİYOR
`mitas_pipeline.py:1442` → yalnız `cikis_jenerik_frames` tanımlı (`giris_jenerik` yok).
`mitas_pipeline.py:1647` → `_jenerik_pool.py` **sadece `cikis_frames`** ile çağrılıyor. Giriş için çağrı yok.

### b) Üretilen master-PNG ana OCR'a beslenmiyor (debug-only)
`mitas_pipeline.py:1640-1641`:
> "Ana OneOCR akışı bu havuzu KULLANMAZ; normal frames/giris + frames/cikis okumaya devam eder. GLM/VL/master debug işleri bu alt havuzdan beslenecek."

Master-PNG sadece GLM/VL **debug** için. Ana OCR ham karelerden okuyor.

### c) Ana OCR'a master besleyebilecek additive yol KAPALI
`_pipe_ocr.py:761-764` → `MITAS_MASTER_PNG` (compose_hybrid → master.png + additive OCR) **default KAPALI**.

### d) Frame-dedup ELEYEN DEĞİL
`_pipe_ocr.py:57` → `MITAS_FRAME_DEDUP` **default KAPALI**. (Dedup hipotezi çürüdü; sorun okuma kalitesi.)

---

## 4. NEDEN ÖNEMLİ (etki)
Bu **tek film değil, bir SINIF sorunu**: sahne-üstü overlay + giriş-jenerik kullanan tüm filmler (TV yapımları, çok sayıda eski film) etkilenir. Bu filmlerde:
- Oyuncuların bir kısmı OCR'dan kaçar →
- `kb_floor` KB'den doldurur (OCR-teyitsiz) →
- Kimlik yanlış kilitlenirse yanlış oyuncu sızabilir.

Çıkış-jenerikli (roll-credit) Batı filmleri sağlıklı; sorun giriş-jenerikli/overlay filmlerde.

---

## 5. ÇÖZÜM YÖNÜ (uygulanmadı — salt tespit)
1. **Giriş jeneriği için de slit-scan master-PNG üret** (`frames/giris` → `giris_jenerik` → master). Çıkışta kanıtlanmış yöntem; slit-scan sahne-üstü overlay'leri dikey biriktirip kontrastı güçlendirir → okunabilir.
2. **Master-PNG'yi ana OCR'a besle** (additive) — yalnız debug değil. (`MITAS_MASTER_PNG` yolu veya jenerik-havuz master'ını OneOCR'a additive ekle.)
3. Sonuç: sahne-üstü overlay oyuncuları okunur → `kb_floor`'a gerek kalmaz → OCR-otorite korunur.

### İlgili kod noktaları
- `mitas_pipeline.py:1442, 1639-1648` — havuz sadece çıkış
- `mitas_pipeline.py:1640` — master ana-OCR'da değil (debug-only)
- `_pipe_ocr.py:57` — frame-dedup kapalı
- `_pipe_ocr.py:761-764` — MITAS_MASTER_PNG additive kapalı
- `_jenerik_pool.py` — havuz+master motoru (segment-agnostik mi, giriş için çağrılabilir mi: incelenecek)

### Açık nokta (son %5)
`_jenerik_pool.py`'nin giriş için de çağrılabilir (segment-agnostik) olup olmadığı — eğer öyleyse fix "ikinci bir çağrı eklemek" kadar kolay. Bu, uygulama kararı verilince incelenir.
