# OCR Claude Tools İnceleme ve Birleştirme Kararı

Tarih: 2026-05-22

İncelenen kaynaklar:

- `F:\REPO_GitHub\Cagatay_22.02\tools`
- `F:\REPO_GitHub\Cagatay_22.02\Project\test_outputs`
- `E:\MITAS\core\pipelines\ocr`

## Net Yerleşim Kararı

Asıl proje evi:

- `E:\MITAS\core\pipelines\ocr`

Masaüstündeki `gpt-ocr` sadece çalışma/kopya klasörü.

`F:\REPO_GitHub\Cagatay_22.02\tools` ayrı bir proje evi değil; deney ve fikir deposu. Oradan doğrudan proje taşınmayacak, sadece kanıtlanmış parçalar E:\MITAS içine port edilecek.

## Claude Yorumu Doğru mu?

Kısmen doğru.

Doğru olanlar:

- `tools/credit_detector.py` içinde static credit için `dark_ratio >= 0.35` kapısı gerçekten var.
- `tools/scroll_reconstructor.py` içinde `cruise_speed` / EMA / deviant reset gerçekten var.
- `quality_score` gerçekten var ve test_outputs bunu destekliyor.
- `test_outputs/pipeline_test/report.json` içinde K-2 ve Fareler için yüksek kalite, Çarıklı için düşük kalite örneği var.
- E:\MITAS tarafı ana gövde olarak daha olgun: manifest, batch, router, row crop OCR, second-pass ROI, raporlama var.

Eksik/yanlış veya dikkat gerektiren taraf:

- `cruise_speed` fikri tools içinde mantıklı ama E:\MITAS row reconstruction hattına aynen taşınınca gerçek 18 film batch'inde kaliteyi düşürdü.
- `dark_ratio frame filter` kör uygulanırsa bazı açık zeminli kredileri bozabilir; bu yüzden kontrollü ve fallback'li uygulanmalı.
- `find_column_split` tools tarafında var ama E:\MITAS `detect_auto_split` daha zengin: valley depth, balance, gap score, low confidence status ve row crop export ile daha iyi bağlı.

## Port Edilenler

### 1. CreditDetector dark gate

Dosya:

- `E:\MITAS\core\pipelines\ocr\credit_detector.py`

Eklenen mantık:

```python
if dark_ratio < 0.35:
    static_text_score = 0.0
```

Ayrıca label aşamasında static score yoksa parlak overlay artık `static_credit` olamıyor.

Neden?

- Film sahnesi üstündeki sabit yazı/KJ overlay'leri statik jenerik sanılmasın.

Test:

- Parlak film overlay sentetiği artık `static_credit` üretmiyor.

### 2. Composite quality_score

Dosya:

- `E:\MITAS\core\pipelines\ocr\text_layer_row_reconstruct.py`

Eklenen çıktı:

- `quality.score`
- `quality.sharpness`
- `quality.contrast`
- `quality.text_density`
- `quality_warning`

Eşik:

- `quality_warning = score < 0.45`

Neden?

- Row composite üretilmiş olsa bile gerçekten kullanılabilir mi, bunu rapora koymak gerekiyor.

18 filmde düşük kalite uyarısı alan örnekler:

- `K-2` batch last3min segmentinde `0.243`
- `KANLI_İNTİKAM` `0.280`
- `BEYAZ_BALİNA` `0.288`
- `KONTES_MARIZA` `0.317`
- `ÇARIKLI_MİLYONER` `0.333`

Bu değerler, bazı composite'lerin var olmasına rağmen güvenilir OCR zemini olmadığını açıkça gösteriyor.

### 3. Kontrollü dark-frame filter

Dosya:

- `E:\MITAS\core\pipelines\ocr\text_layer_row_reconstruct.py`

Eklenen mantık:

- Frame dark ratio hesaplanır.
- `dark_ratio >= 0.30` olan kareler aday tutulur.
- Ama yeterli koyu kare kalmıyorsa filtre uygulanmaz.

Neden kontrollü?

- Tools önerisi “dark_ratio < 0.30 olanı at” diyordu.
- Bu bazı filmlerde doğru ama açık zeminli/özel jeneriklerde kör uygulanırsa zarar verebilir.

18 filmde örnek:

- `SİYAH_KADİFE_ELBİSE`: 30 kareden 22 tutuldu.
- `MEHMED_FETİHLER_SULTANI`: 30 kareden 12 tutuldu.
- Çoğu güçlü jenerikte 30/30 tutuldu, yani zarar vermedi.

## Port Edilip Geri Alınan

### Cruise-speed EMA displacement

Dosya:

- `text_layer_row_reconstruct.py`

İlk port:

- `cruise_speed`
- EMA update
- deviant streak reset
- active-only smoothing

Gerçek 18 film sonucu kötüleşti:

| Run | Row Records | Nonempty Pairs |
| --- | ---: | ---: |
| Baseline OCR bbox second-pass | 334 | 97 |
| Cruise-speed port edilmiş hali | 284 | 91 |

Özellikle:

- `FIRTINANIN_İÇİNDE`: row records `-34`, nonempty `-6`
- `ÖFKE`: row records `-20`

Karar:

> Cruise-speed algoritması aynen alınmayacak. Tools içinde fikir olarak değerli ama E:\MITAS hattında A/B selector olmadan ana algoritmanın yerine geçmemeli.

Bu nedenle geri alındı.

## Son Güvenli Birleşim Testi

Koşu:

- `E:\MITAS\outputs\ocr_credit_experiments\filmtest_last3min_tools_merge_no_cruise_oneocr_20260522`

Karşılaştırma:

| Run | Done | Partial | Failed | Frame OCR | Stable | Row Records | Nonempty |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline second-pass ROI | 13 | 5 | 0 | 5316 | 738 | 334 | 97 |
| Tools merge + cruise | 13 | 5 | 0 | 5316 | 738 | 284 | 91 |
| Tools merge no-cruise | 13 | 5 | 0 | 5316 | 738 | 334 | 97 |

Sonuç:

- Cruise çıkarılınca sayılar baseline'a döndü.
- Dark gate ve quality score sistemde kaldı.
- Kontrollü dark-frame filter zarar göstermedi.

## Nihai Karar

E:\MITAS içine alınanlar:

- CreditDetector static dark gate.
- Row reconstruction quality_score.
- quality_warning.
- Kontrollü dark-frame filter.

E:\MITAS içine alınmayan / geri alınan:

- Cruise-speed EMA displacement ana algoritma olarak.

E:\MITAS içinde zaten daha iyi olanlar:

- `detect_auto_split`
- `detect_rows`
- row crop export
- scene router
- batch/manifest/report altyapısı
- second-pass ROI
- text-layer descroll / temporal track mantığı

## Sonraki Doğru Adım

Cruise-speed gibi alternatif displacement algoritmaları tamamen atılmamalı.

Ama ana algoritmanın yerine doğrudan koymak yerine:

1. mevcut displacement,
2. cruise-speed displacement,
3. static/best-frame fallback

aynı kısa örnekte ayrı ayrı çalıştırılmalı.

Sonra quality_score + row OCR count + nonempty pair + temporal stability ile otomatik seçim yapılmalı.

Bunun adı:

> Row Reconstruction Candidate Selector

Bu yapılmadan tek algoritma değişimi riskli.

