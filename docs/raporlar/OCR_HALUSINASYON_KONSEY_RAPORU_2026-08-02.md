# OCR Halüsinasyon Krizi — Konsey Raporu

**Tarih:** 2 Ağustos 2026
**Konu:** 53 KONTROL filmde DeepSeek-OCR halüsinasyonu
**Aciliyet:** YÜKSEK — KONTROL filmlerin %84'ü bu sorundan etkileniyor

---

## 1. Sorun Özeti

MITAS pipeline'da **53 film** (KONTROL'ün %84'ü), jenerik karelerinde gerçek metin olmasına rağmen OCR modelinin **halüsinasyon** üretmesi sebebiyle KONTROL'e düşmüştür.

### Somut Kanıt

**Film:** AK ALTIN (1957-0067-1-0000-00-1)
- **Jenerik kareleri:** 52 adet PNG (70-99KB her biri) — `giris_jenerik/g_0005.png` ... `g_0052.png`
- **Master PNG:** `giris_reading_master_runaware.png` mevcut
- **Beklenen OCR çıktısı:** "Yönetmen: Lütfi Ö. Akad, Oyuncular: Çolpan İlhan, Fikret Hakan..."
- **Gerçek OCR çıktısı:**
```
Image by: [Untitled]
Date: 1960s
Byline: [Untitled]
Description: This black and white photograph captures a poignant moment
of three individuals in the water, likely from the 1960s...
[图片中没有可识别的文字内容]
image[[4, 0, 999, 1005]]
Person[[49, 204, 440, 999], [87, 103, 661, 997]]
No visible text in the image
```

Model metin okumak yerine **görsel analiz** yapıyor: sahneyi tarif ediyor, bounding box çiziyor, metadata uyduruyor, Çince "metin yok" diyor.

---

## 2. Kök Neden Analizi

### Teknik Zincir

```
Video → ffprobe/ffmpeg → frames/giris_jenerik/*.png (52 kare) ✅
  ↓
MESSİ (frame-havuz + deepseek-ocr) → kunye3.txt ❌ HALÜSİNASYON
  ↓
credit_text_read.py → roller eşleşmedi → QC1 RED
  ↓
KONTROL
```

### Sorunun Kaynağı: `_pipe_hibrit_okuma.py`

```python
# Satır 54-55
MODEL = os.environ.get("MITAS_HIBRIT_MODEL", "deepseek-ocr:latest")
ISTEM = "Free OCR."   # ← SADECE 2 KELİME PROMPT!
```

**Problem 1: Yetersiz prompt.** "Free OCR." talimatı modele "sadece ekrandaki metni çıkar, başka hiçbir şey üretme" demiyor. Frame net olduğunda çalışıyor olabilir, ama gürültülü/bulanık/eski film karesiyle karşılaştığında model **genel VL (Vision-Language) moduna** geçiyor.

**Problem 2: Filtre yetersiz.** `_model_gevezeligi()` fonksiyonu (satır 193) bazı halüsinasyon satırlarını filtreliyor ama 53 filmde halüsinasyon süzülüp `kunye.txt`'ye girmiş. Filtre kapsamı dar.

**Problem 3: Model davranışı.** Kod zaten bu sorunu tespit etmiş:
- Satır 95: *"Kutu sayısı 0 iken satır üretilmişse o satırlar UYDURMADIR"*
- Satır 216: *"model sahneyi ANLATIYOR"*
- Satır 479: *"deepseek boş/gürültülü karede Çince konuşuyor"*
- Satır 492: *"1042 Latin-dışı satırın 1038'i kutu_n=0"*

---

## 3. Etki Ölçeği

| Kategori | Sayı | Açıklama |
|---|---|---|
| Jenerik kare VAR + OCR halüsinasyon | **52** | Kareler mevcut ama model çöp üretti |
| Jenerik kare YOK | **6** | FIGO onset bulamadı |
| Gerçek OCR (temiz) | **5** | Model doğru çalıştı |
| **TOPLAM KONTROL** | **63** | |

### En Sık Halüsinasyon Marker'ları (58 filmde)

| Marker | Frekans | Anlam |
|---|---|---|
| `[图片中没有可识别的文字内容]` | 49 | Çince "tanınabilir metin yok" |
| `No visible text` | 41 | "Görünür metin yok" |
| `Person[[...]]` | 40 | Kişi tespit bounding box |
| `cup of / tablespoon` | 31 | Yemek tarifi halüsinasyonu |
| `Image by:` | 29 | Metadata uydurma |
| `[Image]` | 25 | Görsel referans |
| `image[[...]]` | 20 | Bounding box |
| `\int_ / \frac{` | 19 | Matematik formülü |
| `Caption:` | 18 | Resim açıklaması |

---

## 4. Konseye Sorular

### Soru 1: Prompt İyileştirmesi

Mevcut prompt `"Free OCR."` yerine aşağıdaki gibi bir prompt halüsinasyonu azaltır mı?

```
Read ONLY the visible text on this film credit frame.
Do NOT describe the image. Do NOT generate metadata.
Do NOT add any commentary.
If no text is visible, respond with exactly: [EMPTY]
Output the text exactly as it appears, preserving line breaks.
```

**Alt soru:** DeepSeek-OCR modelinin bu tür bir "strict OCR" modu var mı? Yoksa model doğası gereği VL (vision-language) davranışına mı yatkın?

### Soru 2: Model Alternatifleri

DeepSeek-OCR halüsinasyon üretiyorsa, alternatif OCR motorları:

| Model | Avantaj | Dezavantaj |
|---|---|---|
| PaddleOCR (mevcut) | Deterministik, halüsinasyon yok | Düşük doğruluk (eski filmlerde) |
| OneOCR | İyi doğruluk | Yavaş |
| Qwen2.5-VL (7B/32B) | Yüksek doğruluk | VL modu → aynı halüsinasyon riski |
| Gemini Flash (API) | İyi OCR | API maliyeti, 53 film × ? |
| Tesseract | Deterministik | Düşük doğruluk |

**Soru:** Hangi model/strateji 52 film için en güvenilir sonuç verir?

### Soru 3: Filtre Güçlendirme

Mevcut `_model_gevezeligi()` filtresi hangi ek pattern'leri yakalamalı?

Önerilen ek filtreler:
- `[图片` → Çince halüsinasyon
- `Image by:` / `Caption:` / `Date:` → metadata
- `Person[[` / `image[[` → bounding box
- `cup of` / `tablespoon` → recipe
- `\int_` / `\frac{` → matematik
- `No visible text` → explicit ret
- Satır uzunluğu > 200 karakter → model gevezeliği

**Soru:** Bu filtreler yeterli mi? Yoksa model çıktısı tamamen güvenilmez mi?

### Soru 4: Strateji Değişikliği

Mevcut yaklaşım: Frame → VL model (DeepSeek-OCR) → metin çıkar

Alternatif yaklaşım:
1. **PaddleOCR önce** → sadece Paddle'ın bulduğu text box'ları DeepSeek'e gönder
2. **Hybrid: Paddle kutu + DeepSeek okuma** → DeepSeek sadece Paddle'ın tespit ettiği bölgeleri okusun
3. **Master PNG stratejisi** → Tek tek frame yerine stitched master PNG'yi okut (daha az gürültü)

**Soru:** Hangi yaklaşım halüsinasyonu minimuma indirir?

---

## 5. Önerilen Aksiyonlar

1. **Kısa vade:** Prompt'u güçlendir + filtreyi genişlet → 52 filmden kaçı kurtulur?
2. **Orta vade:** PaddleOCR kutu + DeepSeek okuma hybrid stratejisi
3. **Uzun vade:** OCR modelini değiştir veya fine-tune et

---

*Rapor Genel Sekreter sistemi tarafından hazırlanmıştır.*
*Veri kaynağı: 63 KONTROL film analizi, 2 Ağustos 2026.*
