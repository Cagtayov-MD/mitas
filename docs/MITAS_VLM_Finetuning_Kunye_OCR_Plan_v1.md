# MITAS — Türkçe Künye-OCR için Yerel VLM Fine-Tune Yol Haritası (v1, taslak)

> Durum: ONAYLANDI (mimari yaklaşım) — 2 turlu konsey süreciyle netleşti.
> Gerçek ölçek (~2.000 film + 8-10.000 dizi bölümü + belgesel + müzik
> programı, sürekli büyüyen) netleşince GLM ilk turdaki "fine-tune'a girme"
> önerisini tersine çevirdi. Bkz. `docs/KONSEY_KARARLARI.md` 2026-07-20
> (iki kayıt). Aşağıdaki plan artık "damıtma için ayrı veri toplama projesi"
> değil, **hibrit üretim hattının doğal yan-ürünü** olarak revize edildi.

## 0. Güncel mimari (2026-07-20 sonrası — asıl plan bu)

Sıfırdan-Claude-okuma DEĞİL, tam-otonom-fine-tune-model DEĞİL — hibrit:

```
[görsel] → yerel/ucuz motor (Qwen-VL zero-shot veya OneOCR/PaddleOCR)
         → TASLAK metin
         → Claude: taslağı GÖRSELLE KARŞILAŞTIRIR, hedefli düzeltir
           (sıfırdan üretim değil — "hata ayıklama", çok daha ucuz)
           [text-comparison-validator + ocr-quality-assurance agent'ları]
         → düzeltilmiş final metin → üretime gider
         → YAN ÜRÜN: (taslak, düzeltilmiş) çifti birikir
```

**Fine-tune kararı ERTELENDİ, iptal değil.** ~5.000-10.000 çift birikince
(GLM'in önerisi), gerçek maliyet/hata verisiyle yeniden değerlendirilecek —
o zaman spekülasyon değil, ölçülmüş karar olur.

**Sonraki somut adım:** Küçük bir pilot parti (örn. 10-20 film) ile hibrit
hattı deneyip gerçek maliyet/kalite rakamı çıkarmak.

---

## Aşağısı — orijinal (1. tur, artık ikincil) taslak, referans olarak kalıyor

## 1. Problem

Mevcut üretim OCR (OneOCR/PaddleOCR/Tesseract) Türkçe film jeneriklerinde
sistematik hatalar üretiyor: diakritik bozulması (ş/s, ğ/g, ı/i, ö/o, ç/c),
kelime birleşme/ayrılma hataları, rol-isim eşleşmesinin tamamen kaybı (düz
isim listesi çıkıyor, "Sanat Yönetmeni — Meral Aktan" gibi yapı yok).

`Claude-Vision-OCR` (bkz. manifest) bu hataların çoğunu düzeltiyor ama
**üretim motoru olarak kullanılamaz**: ~108K token / ~6 dk / görsel — 400
dosyalık arşivde toptan uygulama maliyeti kabul edilemez.

## 2. Hedef

Yerel, hızlı, çevrimdışı çalışan, Türk film jeneriği okumada
Claude-Vision-OCR'a yakın kalitede küçük bir VLM. Zaten yerelde kurulu
adaylar var (Ollama): `qwen3-vl:8b`, `qwen3-vl:32b`, `qwen3-vl:30b`.

## 3. Yaklaşım — damıtma (distillation)

Claude-Vision-OCR'ın ürettiği yüksek-kaliteli okumaları **altın-standart
eğitim verisi** olarak kullanıp yerel bir Qwen-VL modelini fine-tune etmek.

```
[N film panoraması] → Claude-Vision-OCR (altın-standart okuma)
                    → [insan spot-check / güven filtresi]
                    → eğitim seti (görsel + doğru metin çifti)
                    → LoRA fine-tune (qwen3-vl:8b, yerel)
                    → eval-harness ile mevcut motorlarla + Claude-Vision-OCR ile kıyas
                    → benchmark raporu → karar (no_engine_selection_before_benchmark)
```

## 4. Fazlar (taslak — konsey sonrası netleşecek)

1. **Eval-harness kurulumu** (`eval-harness-first`) — karşılaştırma öncesi
   ölçüm çerçevesi: hangi metrik (karakter doğruluğu, kelime doğruluğu, rol-
   isim eşleşme oranı), hangi eval seti (kaç film, nasıl seçilecek).
2. **Altın-standart veri toplama** — Claude-Vision-OCR ile N film panoraması
   okunur. N'in büyüklüğü AÇIK SORU (konseye sorulacak). Kalite kontrolü:
   spot-check örneklem.
3. **Fine-tune** — `llm-finetuning-architect` (yöntem/model seçimi) →
   `llm-finetuning-training-engineer` (LoRA config, eğitim) →
   `llm-finetuning-eval-engineer` (golden-set değerlendirme, checkpoint onayı).
4. **Benchmark** — yeni model vs OneOCR/PaddleOCR/Tesseract/Claude-Vision-OCR,
   aynı eval setinde. Rapor: `docs/MITAS_OCR_Finetune_Benchmark_v1.md`.
5. **Karar** — `model_manifest.yaml`'da `selected_as_engine` değişikliği
   SADECE bu benchmark sonrası, Çağatay onayıyla.

## 5. Açık sorular (dış konseye sorulacak)

- Golden-standart veri için kaç film/panorama yeterli (N)?
- LoRA mı, tam fine-tune mi — bu ölçekte hangisi mantıklı?
- Claude-Vision-OCR çıktısını "ground truth" kabul etmenin riski nedir
  (döngüsel hata — damıtılan model, kaynağın hatalarını da öğrenir)?
- Az-kaynaklı dil (Türkçe) + niş domain (film jeneriği formatı) kombinasyonu
  için bilinen bir tuzak var mı?
- Bu proje gerçekten değer mi, yoksa Claude-Vision-OCR'ı hedefli-ikinci-görüş
  olarak kullanmaya devam etmek yeterli mi (maliyet/fayda)?

## 6. Kaynaklar

- `model_manifest.yaml` → Claude-Vision-OCR adayı, OCR bölümü
- `.claude/skills/mitas-benchmark/SKILL.md` → benchmark prosedürü
- Agent'lar: `llm-finetuning-architect`, `llm-finetuning-training-engineer`,
  `llm-finetuning-eval-engineer`, `data-scientist`
- Yerel modeller: Ollama `qwen3-vl:8b` / `qwen3-vl:32b` / `qwen3-vl:30b`

## 7. Tahmini kapsam

Dürüst tahmin: birkaç haftalık gerçek mühendislik işi (veri toplama +
eğitim + değerlendirme döngüsü). "Yarın biter" değil.
