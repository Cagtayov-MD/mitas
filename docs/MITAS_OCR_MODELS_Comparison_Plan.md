# MITAS OCR — MODEL 1 vs MODEL 2 Karşılaştırma Planı

> **Amaç:** İki yolu paralel geliştirip aynı kriterlerle karşılaştırmak.
> **Karar tarihi:** 2026-05-26
> **Karşılaştırma hedef tarihi:** MODEL 2 POC tamamlandığında (~2 hafta sonra).

---

## 1. Karşılaştırma filmleri

Her iki model **aynı 5 filmde** koşturulur:

| Film | Kategori | Neden |
|---|---|---|
| **1989 KUKLA_ADAM** (Humpty Dumpty Man) | D — statik+statik | Baseline, en kolay durum |
| **1997 JURASSIC_PARK_2** | A — statik BG + scroll | Klasik Hollywood scroll |
| **1968 ANJELIK_VE_SULTAN** | B — hareketli BG + scroll | Zor case (Truffaut tarzı) |
| **1980 SON_METRO** | Karma — multi-segment | Cut'lı serial cards + scroll |
| **2012 BENİ_BÖYLE_SEV** | Türkçe dizi | Diakritik + dense layout |

## 2. Karşılaştırma kriterleri

### A. Görsel kalite (subjektif + objektif)

| Kriter | Ölçüm | Hedef |
|---|---|---|
| Master PNG/panorama keskinlik | gözle 1-5 ölçek | ≥ 4 |
| Bulanıklık / ghost stitch | gözle 1-5 ölçek | ≥ 4 |
| Spatial fidelity (ekrandaki konum korunmuş) | gözle YES/NO | YES |
| Renk doğruluğu | gözle YES/NO | YES |

### B. OCR doğruluğu (objektif)

| Kriter | Ölçüm | Hedef |
|---|---|---|
| Cast doğruluğu (IMDB ile match) | %match | ≥ 90% |
| Crew rol/isim doğruluğu | %match | ≥ 85% |
| Türkçe karakter doğruluğu | diakritikli kelime / toplam | ≥ 95% |
| Tek-PNG OCR confidence ortalaması | avg | ≥ 0.85 |
| Yanlış pozitif (sahne metni "cast" sayılmış) | sayı / toplam | ≤ 5% |

### C. Yapısal çıktı (multimodal LLM tarafı)

| Kriter | Ölçüm | Hedef |
|---|---|---|
| Yönetmen doğru tespit | YES/NO | YES |
| Yapımcı doğru tespit | YES/NO | YES |
| Senarist doğru tespit | YES/NO | YES |
| Görüntü Yönetmeni doğru | YES/NO | YES |
| Cast top 5 doğruluk | %match | ≥ 80% |
| Hayali isim (halüsinasyon) | sayı | 0 |

### D. Performans (objektif)

| Kriter | Ölçüm | Karşılaştırma |
|---|---|---|
| Tek film işleme süresi | saniye | M2 < M1 hedefi |
| GPU kullanımı | GB peak | düşük tercih |
| Disk çıktı boyutu | MB | düşük tercih |
| Pipeline kod satırı | LOC | düşük tercih |

### E. Sağlamlık

| Kriter | Ölçüm |
|---|---|
| Hard case'lerde (FRANNY, POROROCA) sonuç | YES/NO |
| Kısa scroll'lu film | YES/NO |
| Çok yoğun jenerik (250+ satır) | YES/NO |
| Diziler | YES/NO |

## 3. Skorlama yöntemi

Her kriter 0-5 puan. Toplam:
- **A (görsel)**: 4 kriter × 5 = 20
- **B (OCR)**: 5 kriter × 5 = 25
- **C (yapısal)**: 6 kriter × 5 = 30
- **D (performans)**: 4 kriter × 5 = 20
- **E (sağlamlık)**: 4 kriter × 5 = 20

**Toplam:** 115 puan üzerinden.

Eşik:
- **≥ 90:** "MODEL 2'ye geçişe değer"
- **70-89:** "Hibrit yaklaşım, ikisini birleştir"
- **< 70:** "MODEL 1 yeterli, MODEL 2'yi shelf"

## 4. Karşılaştırma süreci

```
1. Her 5 film için MODEL 1 koşar  →  M1 sonuç klasörü
2. Her 5 film için MODEL 2 koşar  →  M2 sonuç klasörü
3. 23 kriter üzerinden ayrı ayrı skor (toplam 115)
4. Tek bir karşılaştırma raporu (MD + tablo)
5. Çağatay nihai karar verir
```

## 5. Hibrit ihtimaller

Eğer karşılaştırma "ne biri ne öteki tek başına yeterli" çıkarsa, hibrit yaklaşımlar:

**Hibrit A — M1 ana + M2 doğrulama:**
- MODEL 1 ile pipeline koş
- MODEL 2 paralel panorama üret
- İki sonuç çeliştiğinde MODEL 2'nin LLM cevabı kazanır

**Hibrit B — M2 ana + M1 fallback:**
- MODEL 2 ile başla
- M2 düşük confidence verdiğinde MODEL 1'in track verisini fallback olarak kullan

**Hibrit C — Segment-bazlı:**
- Statik kartlar için MODEL 1 (best_frame)
- Scroll için MODEL 2 (panorama)
- Birleştir

## 6. POC sırasında risk yönetimi

- **MODEL 1'i kırma:** mevcut prod yol dokunulmaz, yeni kod sadece `model2/` altında
- **Output ayrımı:** `_model2_` prefix'i ile MODEL 1 output'ları korunur
- **Venv ayrımı:** `venvs/model2/` ayrı, MODEL 1'in core/ocr venv'leri etkilenmez
- **Commit hijyeni:** MODEL 2 değişiklikleri ayrı commit'lerde, scope etiketli (`feat(model2): ...`)

## 7. Tarihler

| Adım | Tarih |
|---|---|
| MODEL 2 skeleton + dokümanlar | 2026-05-26 |
| Faz M2-1 (scroll stitching POC) | ~2026-05-28 |
| Faz M2-2 (multi-engine OCR) | ~2026-05-30 |
| Faz M2-3 (multimodal LLM) | ~2026-06-02 |
| Faz M2-4 (PDF builder) | ~2026-06-03 |
| Faz M2-5 (IMDB cross-check) | ~2026-06-05 |
| Faz M2-6 (Karşılaştırma) | ~2026-06-07 |
| **Nihai karar** | ~2026-06-10 |

---

**Önemli prensip:** İki yol kendi içinde tamam olsun, sonra karşılaştır. Karşılaştırma öncesi kıyaslama yapılmaz, "şu daha iyi olur sanırım" yargısı yasaktır.
