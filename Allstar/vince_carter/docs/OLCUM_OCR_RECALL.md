# Ölçüm — Paddle'ın SATIR bazında recall'ı (konseyin 1 numaralı açık borcu)

**Tarih:** 2026-08-20 · **Betik:** `scratch/kanit/ocr_recall_olcum.py` ·
**Ham sonuç:** `scratch/kanit/ocr_recall.json`

Üç konsey üyesi de aynı uyarıyı verdi: *"Paddle'ın satır-bazında recall'ı hiç
ölçülmedi; düşükse OCR kanıtı gerçek satırları eler."* Kod yazılmadan ölçüldü.

## Yöntem

Klip → reçete kareleri (fps=2, 720px, lanczos+unsharp, q=2) → PaddleOCR
(`PP-OCRv6_medium_det` + **`latin_PP-OCRv5_mobile_rec`**) → her kare için satır
bantları + tekil kutular → GT'nin her satırı için havuzdaki **en iyi benzerlik**
(Türkçe katlamalı, boşluksuz varyant dahil).

> Tanıyıcı seçimi Nash'in ölçümünden geldi: genel `PP-OCRv6_medium_rec`
> Türkçe'de `UČUR/MÜZiK` üretiyor; resmi Latin modeli `ÜMİT/MÜZİK/UĞUR` okuyor
> (üstelik 74 MB yerine 8 MB).

## Sonuç

| film | kare | GT satır | OCR aday | **recall ≥0.90** | **recall ≥0.70** |
|---|---|---|---|---|---|
| marnali (854×480) | 262 | 128 | 1532 | **%96,1** | **%100** |
| pastane (600×480) | 180 | 59 | 765 | **%61,0** | **%91,5** |

## Yorum — mimari AYAKTA, ama eşik düzeltildi

1. **OCR kanıt kanalı geçerli.** GT satırlarının %91,5–100'ü piksellerde
   OCR tarafından gerçekten görülüyor. Konseyin "OCR kör, kanıt olamaz"
   endişesi bu iki filmde **doğrulanmadı**.
2. **Ama `E1 = 0.90` olsaydı pastane'nin gerçek satırlarının %39'unu elerdik.**
   Konseyin uyarısı yanlış yerde değil, yanlış eşikteydi. `E1` ızgarası
   **0.65–0.80** aralığında taranacak, 0.90 civarı değil.
3. **Pastane'nin düşük olmasının sebebi bulundu — ve GLM'in kuralı yüzünden.**
   Kaçan satırlar iki sütunlu: `Sevinç Hanım—AYŞE SELEN` (0.89),
   `Hacer—SERPİL TEZCAN` (0.84), `Kadayıf Erdal—ERHAN TUNA` (0.89).
   Bantta birleşmeleri gerekirdi; birleşmediler çünkü kutulardan biri
   `guven < 0.80` ve konsey kararı 5 zayıf kutuyu birleşimden dışlıyor.

### Karar — konsey kararı 5 düzeltildi (ölçümle)

Zayıf kutuyu birleşimden **dışlamak** yerine **iki varyantı da aday yap**:

| aday | nasıl | kanıt ağırlığı |
|---|---|---|
| `bant_guclu` | yalnız `guven ≥ 0.80` kutular birleşti | tam |
| `bant_tum` | tüm kutular birleşti | **düşük** (`zayif_birlesim: true`) |
| `kutu` | tekil kutu | tam |

GLM'in korkusu (zayıf kutuların birleşimi sahte string üretir) **etiketle**
karşılanır, adayı yok ederek değil. Aday üretmek bedava; hüküm veren skordur.
Nash'in "yok etme, düşür" dersinin aynısı, kanıt katmanında.

## Kalan kayıplar (%8,5 pastane)

`Oynayanlar` (0.74), `Müsteriler` (0.62) — stilize başlıklar; `Işık / ÖZER MOTAN`
(0.82). Bunlar tam olarak **VLM'in güçlü, OCR'ın zayıf olduğu** yer: iki-olumsuz-
sinyal kuralı (OCR yok **VE** faz tutarsız) bunları ana çıktıda tutar.
