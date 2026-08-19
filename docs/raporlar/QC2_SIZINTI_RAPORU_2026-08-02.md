# QC2 Sızıntı Raporu — 2 Ağustos 2026

## Sorun

QC2'den (credit_qc_block + credit_severity_router) geçen filmler ONAYLI'ya düşüyor
ama bir kısmında eksik/hatalı veri var. 65 ONAYLI filmin **19'unda** (%29) sorun tespit edildi.

## Sızıntı Noktaları

### 1. YAPIMCI Zorunluluğu YOK
- **QC2 kodunda:** `_kb_producers()` fonksiyonu var ama sadece "destek-doldurma" amaçlı
- **Transition tablosunda:** YAPIMCI kodu yok → yapımcı eksikliği bloklamıyor
- **MITAS kuralı:** Yapımcı zorunlu (gerçek kişi, stüdyo değil)
- **Etkilenen film:** 7 film (ŞENDUL ŞABAN, MARCO POLO, KANUNSUZ JOSEY WALES, SÜT, vb.)
- **Fix:** `credit_severity_router.py` transition tablosuna `YAPIMCI` kodu eklenmeli

### 2. AFIS = Warning-Nonblocking
- **QC2 kodunda:** `credit_severity_router.py:52` → `"AFIS": "warning-nonblocking"`
- **Etki:** Afiş yoksa sadece warning, ONAYLI'ya geçişi engellemez
- **MITAS kuralı:** "NEVER wrong poster" ama poster YOK olması da sorun
- **Etkilenen film:** 8 film (SAHİLDE, LANETLİ DÜĞÜN, WİN GERİ DÖNDÜ, vb.)
- **Fix:** AFIS'i `insan-kontrolü` olarak değiştirmek veya opsiyonel bırakmak tartışılmalı

### 3. Özet Boş Kontrolü Yetersiz
- **QC2 kodunda:** `_ozet_gate()` → `ozet_kelime < 20` kontrolü var
- **Ama:** Özet tamamen boşsa `("—", 0)` döner → `ozet_kelime=0` → `< 20` → OZET kodu eklenir
- **Ancak:** `credit_severity_router:131` → `sig.get("ozet_missing")` kontrolü farklı sinyal bekliyor
- **Etkilenen film:** 1 film (BOZGUNCULAR)
- **Fix:** `_ozet_gate` dönüş değeri ile `ozet_missing` sinyali arasındaki kopukluk giderilmeli

### 4. Latin-dışı Transliteration Sızıntısı
- **QC2 kodunda:** `_translit_list()` transliterasyon yapar, başarısızsa `translit_failed` flag
- **Ama:** Başarılı transliterasyon ≠ doğru transliterasyon
- **Örnek:** MARCO POLO — transliterasyon "başarılı" ama gerçekte bozuk karakterler kalmış
- **Etkilenen film:** 2 film (MARCO POLO, KUTSAL HAZİNE)
- **Fix:** Transliteration sonrası doğrulama adımı eklenmeli (tüm karakterler Latin mi?)

## Önerilen Düzeltmeler

### Kısa vadeli (mevcut ONAYLI filmler):
1. `apply_qc_fixes.py` ile 7 yapımcı eksik filmini IMDb'den doldur
2. `credit_kb_lookup.py --afis-out` ile 8 afiş eksik filmini TMDB'den indir
3. `translit_util.py` ile 2 Latin-dışı filmi düzelt
4. `_ozet_kalite.py` + qwen-plus ile 1 özet eksik filmi üret

### Orta vadeli (QC2 açıklarını kapat):
1. `credit_severity_router.py` → `YAPIMCI` kodu ekle (`insan-kontrolü` seviyesinde)
2. `credit_severity_router.py` → `AFIS` kodunu tartış (opsiyonel mi zorunlu mu?)
3. `credit_qc_block.py` → Özet boş/yok sinyalinin `ozet_missing` ile eşleşmesini sağla
4. `credit_qc_block.py` → Transliteration sonrası Latin doğrulama adımı ekle
