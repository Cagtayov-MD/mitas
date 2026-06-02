# 3 Film Pipeline Test Raporu
**Tarih:** 2026-05-22  
**Araçlar:** CreditDetector (probe tabanlı) + ScrollReconstructor (LK stitch) + OneOCR

---

## Özet Tablo

| Film | Tür | Composite | Kalite | Değerlendirme |
|---|---|---|---|---|
| K-2 | scroll | 600×4664px | 1.00 | BAŞARISIZ — orta bölüm bozuk |
| FARELER_VE_İNSANLAR | scroll | 512×8607px | 1.00 | BAŞARILI ama erken başlıyor |
| ÇARIKLI_MİLYONER | scroll | 512×159px | 0.40 | TAM BAŞARISIZ |

---

## K-2 Detayı

**Video:** `evoArcadmin_COZUMLEMEV2S17_1991-0339-1-0000-01-1-K-2.mp4`  
**Tespit edilen segment:** 6140s – 6244s (yaklaşık 104 saniye)  
**Composite çıktı:** `F:\REPO_GitHub\Cagatay_22.02\Project\test_outputs\pipeline_test\K-2\composite.png`  
**Boyut:** 600×4664px  
**quality_score:** 1.00 (Laplacian=yüksek, kontrast=yüksek — yanıltıcı)

**Sorun:**
Composite'in ortasında ciddi bozulma. Kullanıcının ifadesiyle: *"filmin başı yok, ortasında ciddi sorun var."*

**Kök neden:**  
K-2 segmenti iki farklı içerik tipini kapsıyor:
- **6140–6180s:** Film sahnesi üstüne overlay text → `dark_ratio ≈ 0.15-0.33` → BU JENERİK DEĞİL
- **6180–6244s:** Temiz siyah zemin + beyaz metin → `dark_ratio ≈ 0.87-0.94` → gerçek jenerik

Dedektör ikisini tek segment saydı. ScrollReconstructor overlay frame'lerini de stitch etti.

**quality_score neden 1.00 verdi?**  
Laplacian varyansı film sahnesindeki keskin kenarları (insan yüzleri, nesneler) da ölçüyor.  
Yüksek Laplacian ≠ metin kalitesi. Kalite metriği kör nokta.

**Düzeltme yolu:**
1. `credit_detector._score_window()` → `dark_ratio >= 0.35` zorunlu koşul (static_credit)
2. `text_layer_row_reconstruct._center_strip_composite()` → frame başına `dark_ratio < 0.30` olanları at

---

## FARELER_VE_İNSANLAR Detayı

**Video:** `evoArcadmin_ÇÖZÜMLEME5_1992-1150-1-0000-50-1-FARELER_VE_İNSANLAR.mp4`  
**Composite çıktı:** `...pipeline_test\FARELER_VE_İNSANLAR\composite.png`  
**Boyut:** 512×8607px  
**quality_score:** 1.00

**Değerlendirme:** Kompozit kalitesi MÜKEMMEL. Satırlar net, ayrım belirgin.  
Tek sorun: segment biraz erken başlıyor — filmin ilk birkaç saniyesi jenerik değil.

**Düzeltme yolu:** Segment başlangıcında düşük skorlu probe'ları kes (trim logic).

---

## ÇARIKLI_MİLYONER Detayı

**Video:** `evoArcadmin_ÇÖZÜMLEME5_1983-0176-1-0000-90-1-ÇARIKLI_MİLYONER.mp4`  
**Composite çıktı:** `...pipeline_test\ÇARIKLI_MİLYONER\composite.png`  
**Boyut:** 512×159px  
**quality_score:** 0.40

**Değerlendirme:** TAM BAŞARISIZ.

**Kök neden:**  
Dedektör yanlış pozitif buldu: 42 saniyelik bir segment tespit etti ama içerik jenerik değil.  
Scroll hızı çok düşük veya sıfır → ScrollReconstructor 159px'lik bir composit üretti.

**quality_score burada doğru davrandı:** 0.40 → eşiğin altında, kullanılamaz.

**gpt-ocr'da statik fallback var:** `displacement_range < 12px` → en iyi frame seçilir.  
tools/'ta bu fallback yok — ScrollReconstructor anlamsız bir şey üretti.

---

## gpt-ocr 18 Film Batch Referans Sonuçları

**Manifest:** `E:\MITAS\data\ocr_filmtest_last3min_manifest_20260522.json`

| Metrik | Değer |
|---|---|
| Toplam film | 18/18 |
| Başarılı (done) | 13 |
| Kısmi (partial) | 5 |
| Başarısız | 0 |
| Toplam frame OCR records | 5316 |
| Stable groups | 738 |
| Row OCR records | 334 |
| Nonempty row pairs | 97 |
| Toplam süre | ~209.3s |

**En iyi filmler:**
- SON_HAVA_BÜKÜCÜ: 1576 frame OCR records, 33 nonempty row pairs
- FIRTINANIN_İÇİNDE: 1223 records, 15 pairs
- ÖFKE/FURY: 1104 records, 21 pairs

**Sıfır kayıt filmler:**
- SON_ADAM, SİYAH_KADİFE, GÜN_BATISI, BEYAZ_BALİNA, KANLI_İNTİKAM

**Second-pass ROI devreye giren filmler:**
| Film | Auto ROI | Refined ROI | İlk OCR | Final OCR |
|---|---|---|---:|---:|
| BABA_3 | [35,11,442,266] | [27,0,383,266] | 659 | 660 |
| MACARLAR | [59,19,736,442] | [222,0,304,442] | 18 | 16 |
| FIRTINANIN_ICINDE | [59,19,736,442] | [125,0,475,442] | 1223 | 1235 |
| MEHMED_FETIHLER_SULTANI | [89,28,1102,664] | [60,393,914,237] | 4 | 1 |

**Birim test sonucu:** `10 passed, 12 skipped`
