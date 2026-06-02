# Oturum Özeti — Scroll OCR & Proje Birleşimi
**Tarih:** 2026-05-22  
**Kapsam:** tools/ (mitas2 iskelet) + gpt-ocr (E:\MITAS\core\pipelines\ocr) karşılaştırması ve birleşim planı

---

## 1. Bağlam — İki Proje Neydi?

### tools/ (F:\REPO_GitHub\Cagatay_22.02\tools\)
mitas2 için geliştirilen deneme iskeletiydi. Hiçbir zaman E:\MITAS'a bağlı değildi.  
Tamamen bağımsız bir geliştirme ortamıydı.

**İçindekiler:**
- `credit_detector.py` — Probe tabanlı dedektör (LK optical flow, dark_ratio kapısı)
- `scroll_reconstructor.py` — LK stitching, cruise_speed EMA, quality_score, find_column_split
- `full_pipeline_test.py` — 3 film uçtan uca test

### gpt-ocr (C:\Users\TRT03\Desktop\gpt-ocr → asıl ev: E:\MITAS\core\pipelines\ocr\)
Desktop kopyası. Asıl kod E:\MITAS'ta yaşıyor.

**İçindekiler:**
- `credit_detector.py` — Pencere tabanlı dedektör (phaseCorrelate, row_structure scoring)
- `credit_scene_router.py` — Sahne sınıflandırıcı (background/text_motion/layout)
- `text_layer_row_reconstruct.py` — Satır öncelikli kompozit + statik fallback
- `text_layer_descroll.py` — OCR bbox track tabanlı de-scroll + engine fusion
- `credit_experiment.py` — 18 film batch altyapısı
- `credit_pipeline_selector.py` — Kural tabanlı pipeline seçici

---

## 2. Bu Oturumda Ne Yaptık?

### Adım 1: 6 araç inşası (önceki oturumdan devir)
tools/ altında şu 6 bileşen yazıldı ve doğrulandı:
1. `CreditDetector` — probe tabanlı jenerik tespiti
2. Scroll routing (type=scroll ise ScrollReconstructor)
3. Static routing (type=static → farklı yol)
4. `find_column_split` — otomatik rol/isim sütun ayrımı
5. `cruise_speed` hybrid — EMA bootstrap + deviant streak reset
6. `quality_score` — Laplacian + Otsu kontrast + yoğunluk

### Adım 2: 3 film uçtan uca pipeline testi
**Test komutu:**
```powershell
F:\REPO_GitHub\Cagatay_22.02\venv\Scripts\python.exe tools/full_pipeline_test.py
```

**Filmler:**
- K-2 (`evoArcadmin_COZUMLEMEV2S17_1991-0339-1-0000-01-1-K-2.mp4`)
- FARELER_VE_İNSANLAR (`...-50-1-FARELER_VE_İNSANLAR.mp4`)
- ÇARIKLI_MİLYONER (`...-90-1-ÇARIKLI_MİLYONER.mp4`)

**Sonuçlar:** → bkz. `test_sonuclari/TEST_RAPORU.md`

### Adım 3: Hatalar ve düzeltmeler
→ bkz. `YOL_HARITASI.md` — "Düzeltilen Hatalar" bölümü

### Adım 4: gpt-ocr analizi
18 filmde test edilmiş gpt-ocr kodu incelendi. Karşılaştırma tablosu:
→ bkz. `YOL_HARITASI.md` — "İki Proje Karşılaştırması" bölümü

### Adım 5: Birleşim hedefi belirlendi
**Karar:** tools/ iyileştirmeleri E:\MITAS\core\pipelines\ocr\ içindeki 2 dosyaya port edilecek.  
Desktop gpt-ocr çalışma kopyası, E:\MITAS'ın aynısı — ayrı proje yok.

---

## 3. Kritik Kararlar

| Karar | Detay |
|---|---|
| Model routing | Opus 4.7 → planlama + kod yazımı / Sonnet → testler |
| Ana gövde | gpt-ocr (E:\MITAS\core\pipelines\ocr) — 18 filmde kanıtlanmış |
| tools/ rolü | Sadece iyileştirme kaynağı — 3 şey port edilecek |
| Film label çıkarma | `re.search(r"-\d{1,2}-[01]-(.+)$", stem)` — düz split(-1) yanlış |
| Unicode path | cv2.imwrite değil: `imencode + write_bytes` |

---

## 4. Dosya Haritası

```
E:\MITAS\mutfak\OTURUM_20260522_SCROLL_OCR_BIRLESIM\
├── OZET.md                          ← bu dosya
├── YOL_HARITASI.md                  ← ne bitti, ne kaldı, ne yapılacak
├── kod\
│   ├── credit_detector_tools.py     ← tools/ sürümü (probe tabanlı)
│   ├── scroll_reconstructor.py      ← tam ScrollReconstructor
│   └── full_pipeline_test.py        ← 3 film uçtan uca test
└── test_sonuclari\
    └── TEST_RAPORU.md               ← composite PNG sonuçları + analiz
```

**Asıl prod kodlar:**
```
E:\MITAS\core\pipelines\ocr\
├── credit_detector.py               ← BURAYA port edilecek: dark_ratio kapısı
├── text_layer_row_reconstruct.py    ← BURAYA port edilecek: EMA + quality_score + frame filtresi
├── credit_scene_router.py
├── text_layer_descroll.py
├── credit_experiment.py
└── credit_pipeline_selector.py
```
