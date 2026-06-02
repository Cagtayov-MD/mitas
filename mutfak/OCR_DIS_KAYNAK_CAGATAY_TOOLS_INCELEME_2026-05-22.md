# OCR Dış Kaynak İnceleme - Cagatay_22.02/tools - 2026-05-22

## İncelenen Dosyalar

- `F:\REPO_GitHub\Cagatay_22.02\tools\scroll_reconstructor.py`
- `F:\REPO_GitHub\Cagatay_22.02\tools\batch_scroll_test.py`
- `F:\REPO_GitHub\Cagatay_22.02\tools\test_scroll_reconstruct.py`
- `F:\REPO_GitHub\Cagatay_22.02\tools\test_composite_ocr.py`
- `F:\REPO_GitHub\Cagatay_22.02\tools\test_oneocr_composite.py`
- `F:\REPO_GitHub\Cagatay_22.02\tools\test_paddle_composite.py`
- `F:\REPO_GitHub\Cagatay_22.02\tools\test_row_ocr.py`
- `F:\REPO_GitHub\Cagatay_22.02\tools\test_vision_ocr.py`
- `F:\REPO_GitHub\Cagatay_22.02\tools\approve_hatali_txt.py`

## Kısa Test

K-2 videosu üzerinde 10 saniyelik izole smoke:

```text
python test_scroll_reconstruct.py K-2.mp4 --start 6125 --end 6135 --step 2
125 frame yüklendi
kompozit: 600x1132
```

Çıktı:

- `E:\MITAS\outputs\external_scroll_probe\cagatay_tools_k2_10s_step2\composite.png`
- `E:\MITAS\outputs\external_scroll_probe\cagatay_tools_k2_10s_step2\sharpened.png`

Row detector smoke:

```text
rows: 24
```

Paddle composite smoke:

```text
records: 32
örnekler: MICHAEL BIEHN, MATT CRAVEN, ANNIE GRINDLAY, ELENA STITELER,
BLU MANKUMA, CHARLES OBERMAN, JULIA NICKSON..., CHRISTOPHER BROWN
```

## İşe Yarar Fikirler

1. Merkez şerit stitching iyi fikir.
   Full-frame ortalama/warp ghost üretiyor. Bu kod her frame'in merkez bandını alıp kompozit satırını tek kaynak frame'den kuruyor. OCR için daha temiz.

2. Text-mask ile Lucas-Kanade hareket tahmini değerli.
   Hareketli arka planı tamamen çözmüyor ama harf piksellerine kilitlenme fikri bizim phase-correlation yaklaşımından daha kontrollü.

3. Fiziksel row-first OCR en kritik fikir.
   `test_row_ocr.py` kompozit üzerindeki yatay satırları brightness profile ile buluyor, satırı rol ve isim yarısı olarak ayrı okuyor. Bizim v3'te rol/isim pairing için en doğru yön bu.

4. Overlap slice + fuzzy dedupe pratik.
   Kompozit uzun olduğunda dilim OCR gerekli. Overlap ve `SequenceMatcher` ile tekrar atma bizim review/report hattına alınabilir.

5. VLM koşularında resume-able slice mantığı iyi.
   `test_vision_ocr.py` her dilimi RAW dosyasına marker ile yazarak kesilirse devam edebiliyor. Faz 2 VLM fallback için kullanılabilir.

6. Human approval/correction fikri doğru yönde.
   `approve_hatali_txt.py` doğrudan OCR jenerik kodu değil; ama cache, normalize, person filter ve onaylı çıktı mantığı review loop için fikir veriyor.

## Doğrudan Alınmaması Gerekenler

- Hardcoded path çok fazla: `E:\filmtest`, `C:\Program Files\Tesseract-OCR`, repo içi output pathleri.
- `SPLIT = 262` sabit kalmamalı; bbox/kolon analizinden otomatik bulunmalı.
- Tesseract bağımlılığı bizim mevcut kurulumda zayıf; Paddle/OneOCR adapter ile soyutlanmalı.
- LLM düzeltme doğrudan truth gibi yazılmamalı; sadece review önerisi/fallback olarak tutulmalı.
- Full-frame kompozitte arka plan hâlâ ağır bozuluyor; bu görüntüyü final görsel sanmamak gerekir.

## Sonuç

Bu dosyalardan alınacak en iyi v3 yönü:

```text
text-mask LK motion -> center-strip composite -> row detection ->
role/name split -> crop-level Paddle/OneOCR -> temporal/fuzzy dedupe -> review pack
```

Bizim mevcut text-layer yaklaşımımızı çöpe atmadan, bu center-strip + row-first mantığını yeni bir `row_reconstruct` stratejisi olarak eklemek mantıklı.
