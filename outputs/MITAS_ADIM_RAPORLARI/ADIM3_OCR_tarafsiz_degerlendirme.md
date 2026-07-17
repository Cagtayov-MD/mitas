# MITAS OCR Adımı — Tarafsız Değerlendirme Özeti (2026-06-21)

Zincir: CLIP bekçisi → konumlu OneOCR → stitch → clean. Orkestratör `_pipe_ocr.py` → `20260601_pipeline100.py` (clean/stitch/clip_probe'u `load()` ile dinamik yükler).

## Genel hüküm
Mimari sağlam, fail-safe disiplini gerçek (kozmetik değil), OCR-otorite ilkesi koda gömülü (hiçbir katman okunan ismi ezmiyor; KB sadece yazım düzeltir, KB-split/GLM/master-PNG sadece EKLER). İki net boşluk var.

## Boşluk 1 — CLIP iki kez çalışıyor, skor paylaşılmıyor (EN YÜKSEK ÖNCELİK)
- Jenerik tespitinde CLIP bir kez yüklenip kareleri skorluyor (saniye aralığı veriyor).
- OCR bekçisinde CLIP **ikinci kez** yüklenip kareleri **yeniden** skorluyor.
- Skorlar paylaşılmıyor → çift iş + iki çökme noktası + süre kaybı.
- **Altyapı yarı-hazır:** `clip_probe.py:112` skoru zaten `credit_prob.npy`'ye yazıyor. Çağatay'ın "skoru taşı" fikri = ikinci CLIP'i tamamen atla.
- **Tuzak:** iki tarafın frame sırası/indeksi eşleşmeli.

## Boşluk 2 — x (yatay) koordinatı üretim yolunda HİÇ okunmuyor
- `read_pos` (pipeline100.py:43) tuple'ı 4'lü: (fold, raw, y0, y1). x `bounding_rect`'te var ama alınmıyor.
- `line_mosaic`'te `xcenter = ... if len(e)>=6 else 0.0` → tuple 4'lü → `len>=6` hiç True olmaz → çok-sütun mantığı ÖLÜ KOD (üstelik sadece master-PNG yolunda, kapalı).
- **Somut kayıp:** çok-sütunlu jenerik (KARAKTER ... OYUNCU veya 2-kolon liste). OneOCR aynı y'de iki kutu okursa stitch birini eler → sessiz isim kaybı (KEEP-ALL felsefesine aykırı delik). `_kb_suffix_split` kısmen telafi eder ama KB'de olmayan kişide + sol-sağ rol eşlemede yetersiz.
- Scroll'da x sabit (faydası yok), **static** jenerikte anlamlı.

## CLIP çökme — Çağatay'ın 3 fikri (değer sırası)
1. **Skor cache (en yüksek):** tespit aşaması skorunu OCR'a taşı → ikinci CLIP yükü + çökme noktası yok olur, hız kazanır. Altyapı yarı-hazır.
2. **clip_used=False → görünür KONTROL bayrağı (yüksek, ~bedava):** bayrak zaten `ocr_summary.json`'a yazılıyor (`_pipe_ocr.py:716`), sadece bucket'a/KONTROL'e bağlanmamış. Şu an CLIP çökmüş film sessizce GUVENILIR çıkabiliyor.
3. **Heuristik yazı-yoğunluğu yedeği (orta, ucuz sigorta):** çökünce kör "hepsini al" yerine kaba elek. Tuzak: eşik yanlışsa gerçek jeneriği eler (KEEP-ALL ihlali) → "şüpheliyse TUT" tarafında kalmalı.

## Diğer bulgular
- **OneOCR kelime-güveni hiç kullanılmıyor:** `pick_best` en temizi garble-sezgisi + uzunlukla seçiyor, oysa OCR'ın kendi güven skoru elde. Kaçırılmış sinyal.
- **ASR-diyalog eleme:** üretimde `asr_fold=""` → KAPALI (pasif risk). Yan yolda (master-PNG) aktif ve yanlış-pozitif riski var (substring match + isim ASR'de geçerse silinir).
- **stitch KEEP-ALL:** felsefe doğru (kalsın) ama docstring "düşer" diyor, kod atmıyor (yalan docstring, bakım tuzağı). clean garble'a karşı tek+ince kalkan (saf-Latin-garble "credit" geçebilir).
- **GLM consensus:** additive+iki-katman filtre güvenli ama VLM "makul uydurma isim" üretirse iki katman da geçebilir; default açık = canlı risk. A/B ile gözle.

## Öncelik
1. CLIP skor cache + KONTROL bayrağı (kök-neden + bedava güvenlik ağı)
2. x koordinatını geri ekle (read_pos 6'lı + ölü dalı canlandır; stitch sütun-ayrımı 2. faz, kalibrasyon ister)
- ERTELE: KEEP-ALL'a dokunma (sadece docstring düzelt), garble-gate'te acele etme (önce 50-film ölç), GLM'i kapatma (A/B gözle)
