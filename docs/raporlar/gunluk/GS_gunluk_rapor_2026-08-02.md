---
modul: gunluk_rapor
tarih: 2026-08-02
uretim: 2026-08-02T16:13:58
---

# MITAS System Review — 2026-08-02

## Özet

**345 film** işlendi: **142 ONAYLI**, **203 KONTROL**.

## KONTROL Durumu

1. **kunye_okuma** → 133 film (%16.5) — OCR/okuma — metin çıkarılamadı
2. **kunye_kalite_qc1** → 108 film (%13.4) — QC1 — okuma→rol eşleme başarısız
3. **cast_bos** → 88 film (%10.9) — Qwen QC — oyuncu bulunamadı
4. **kimlik_zayif** → 82 film (%10.1) — QC2/qc_block — web çapası kilitlenemedi
5. **yonetmen_yapimci** → 73 film (%9.0) — Qwen QC — yönetmen+yapımcı eksik

### Sistemik Bulgular

- **Yüksek KONTROL oranı:** %58.8 (203/345) — pipeline kalite eşiği gözden geçirilmeli.
- **OCR HATA:** 12 filmde OCR kalitesi HATA seviyesinde — okuma motoru sorunu.
- **Kümülatif kusur:** 136 film (%67) 3+ nedenden KONTROL'e düştü — zincirleme sorun.
- **Tekrar eden hata:** `kunye_okuma` → 133 film aynı sorunu yaşıyor. Kod düzeltmesi ile toplu çözüm mümkün.
- **Tekrar eden hata:** `kunye_kalite_qc1` → 108 film aynı sorunu yaşıyor. Kod düzeltmesi ile toplu çözüm mümkün.
- **Tekrar eden hata:** `cast_bos` → 88 film aynı sorunu yaşıyor. Kod düzeltmesi ile toplu çözüm mümkün.

## ONAYLI QC

Spot-check: 0 film incelendi, **0 şüpheli** (false-positive).

## Performans

- **Film:** 345 | **Ort:** 9.4 dk | **Medyan:** 8.8 dk | **Toplam:** 54.0 saat
- **GPU:** %43.9 VRAM, %88 util
- **Disk:** 462.7 GB boş
- **Koşu:** [74/1825] --- [74/1825] rc=1 evoArcadmin_03072026SAYFA32_198

## Sonraki Adımlar

1. **En kritik:** **Yüksek KONTROL oranı:** %58.8 (203/345) — pipeline kalite eşiği gözden geçirilmeli.
