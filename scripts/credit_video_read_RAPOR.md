# Jenerik (Künye) Okuma — Video baş+son + Ensemble + KB Stratejisi

_2026-06-04 · `E:\filmtest\aaaa` (53-film zor benchmark) üzerinde doğrulandı · modül: `scripts/credit_video_read.py`_

## Problem
Film künyesinden **yönetmen + yapımcı + cast** güvenilir çıkarmak. Ölçüt: **okuyamadıysa "okunamadı"** (yanlış çıktı ASLA) + okuduğunda **kontrol gerektirmeyen güven**. Özet/afiş zaten otomasyonda; tek açık sorun künye OKUMA.

## Eski yol ve sorunu
Üretim hattı jenerik karelerini tek **master PNG**'ye **dikiyordu** (BEKÇİ → slit-scan stitch). Bu katman **kayıplı**: XMEN'de yönetmen kartı düşüyor, AHLAT'ta scroll smear oluyor → master tek başına yönetmende ~4/9.

## Yeni yol (bu modül)
Kareleri **dikmeden**, doğrudan VLM'e **ardışık dizi (video semantiği)** olarak ver:
1. **BAŞ+SON örnekleme:** uzun jenerikte (kare > 1500) **ilk 900 + son 900** kareye yoğun örnek (≤36 kare), ortadaki dev crew scroll atlanır. Yönetmen/cast "billing"i jeneriğin başında (JURASSIC) veya sonunda (XMEN) → iki uç ikisini de yakalar.
2. **2-model ensemble:** `qwen3-vl:30b` (precision, 0 yanlış ama bazen boş/düşük kapsam) + `qwen2.5vl:7b` (yüksek kapsam + bol cast ama gürültülü). Tamamlayıcılar.
3. **KB-fusion (`imdb.duckdb`):** NET rol-uyumsuzluğunu REDDET (senaristi "yapımcı" sanmayı keser). 0-kayıtta reddetme (Türkçe/varyant olabilir).
4. **Çelişki çözümü:** iki model farklı yönetmen derse KB-onaylıyı seç; hiçbiri onaysız/çelişkili → **"okunamadı"** (dürüst çekimserlik).

## Doğrulama (12 film, yönetmen)
| Yöntem | Doğru | Yanlış | Not |
|---|---|---|---|
| Master PNG (30b) | 4/9 | 0 | stitch kayıplı |
| Video baş+son (30b) | 4/9 | 0 | master'la farklı 4 (tamamlayıcı) |
| Video baş+son (7b) | 8/12 | 1 | hızlı, bol cast, gürültülü |
| **Video ENSEMBLE (30b+7b+KB)** | **9/12** | **0** | 3 dürüst abstain (SONMETRO/ROBINSON/BARBARLAR) |

- **Cast:** video master'dan belirgin zengin (full kadro). 7b daha çok ama gürültülü → dedup + ≥2-token + KB-oyuncu filtresi.
- **Abstain'ler** = yönetmen karesi örneklemede yok/stilize → production'da **XML `V_ROLE_TYPE`** doldurur (cast yine elde).

## Operasyon dersleri
- Video çoklu-kare `/api/chat`'te **`think=False` ŞART** (think=True yoğun karede over-think→boş). (Tek master `/api/generate`'de tersi: think=True gerekiyordu.)
- VRAM: 30b ~19-23GB (24GB'de sınırda, bazen boş döner); 7b ~6GB (rahat, akış worker'ıyla paralel çalışabilir).
- Yönetmen/yapımcı çoğu prodüksiyon filminde **XML'de zaten otoriter** (`role_reconcile`); bu modül onun **tamamlayıcısı** + XML'siz/yabancı filmler ve **cast** için birincil.

## Mimari karar
Master'ı çöpe atmadan: **video baş+son ensemble = ana motor**, master/XML = çelişki/abstain'de **yedek sinyal**. En yüksek isabet + sıfır yanlış bu kombinasyondan.

## Kullanım
```
python scripts/credit_video_read.py --film-dir <.../film>      # altinda giris/cikis/frames
python scripts/credit_video_read.py --giris <dir> --cikis <dir>
# ortam: MITAS_CREDIT_MODELS, MITAS_IMDB_DUCKDB, MITAS_OLLAMA
```

## Sıradaki iyileştirmeler (açık)
- **OCR-çapalı hedefli okuma:** ucuz per-frame OCR (OneOCR/glm-ocr) ile "Yönetmen/Directed by" kartını LOKALİZE et, sadece o kareleri VLM'e ver → abstain'leri düşürür, daha verimli, halüsinasyonu azaltır.
- **Kare dedup:** ardışık aynı kartları ele, yalnız benzersiz kartları gönder.
- **Cast güven-kapısı:** KB-oyuncu doğrulama + kare-tekrarı (recurrence) ile halüsinasyon ele.
