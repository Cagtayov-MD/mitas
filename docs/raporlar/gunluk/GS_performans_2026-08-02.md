---
modul: performans
tarih: 2026-08-02
uretim: 2026-08-02T16:13:57
---

# Performans Denetimi
*Ölçüm: 2026-08-02T13:13:57.595694+00:00*

## Disk
- **Boş:** 462.7 GB (%71.4 dolu)

## GPU
- **VRAM:** 10781 / 24576 MB (%43.9)
- **Utilization:** %54

## Timing (Sürekli Ölçüm)

- **Film sayısı:** 345
- **Ortalama:** 9.4 dk/film
- **Medyan:** 8.8 dk
- **Min / Max:** 3.5 / 33.4 dk
- **Std Sapma:** 4.1 dk
- **Toplam iş yükü:** 54.0 saat

### Aşama Kırılımı

| Aşama | Ort (sn) | Medyan | Min | Max | N |
|-------|----------|--------|-----|-----|---|
| asr | 191.4 | 160.5 | 9.4 | 1514.4 | 322 |
| track_kunye | 162.6 | 139.4 | 113.3 | 1064.9 | 154 |
| ocr | 147.9 | 146.1 | 9.4 | 477.9 | 345 |
| coz | 94.0 | 87.7 | 0.5 | 331.0 | 345 |
| v4_final | 84.6 | 71.8 | 10.2 | 355.9 | 329 |
| vl_fallback | 65.3 | 54.6 | 9.0 | 505.9 | 179 |
| pdf | 53.9 | 50.7 | 5.2 | 392.4 | 345 |
| video_kunye | 48.2 | 25.1 | 0.1 | 659.4 | 345 |
| qwen_qc | 17.2 | 14.5 | 5.0 | 249.8 | 330 |

### Darboğaz Adayları

- **asr**: ort 191.4sn (%33.9 toplam süre) — en büyük darboğaz adayı
- **asr**: max 1514.4sn vs medyan 160.5sn — aşırı sapma, bazı filmler çok yavaş
- **track_kunye**: ort 162.6sn (%28.8 toplam süre) — en büyük darboğaz adayı
- **track_kunye**: max 1064.9sn vs medyan 139.4sn — aşırı sapma, bazı filmler çok yavaş
- **ocr**: ort 147.9sn (%26.2 toplam süre) — en büyük darboğaz adayı
- **vl_fallback**: max 505.9sn vs medyan 54.6sn — aşırı sapma, bazı filmler çok yavaş
- **pdf**: max 392.4sn vs medyan 50.7sn — aşırı sapma, bazı filmler çok yavaş
- **video_kunye**: max 659.4sn vs medyan 25.1sn — aşırı sapma, bazı filmler çok yavaş
- **qwen_qc**: max 249.8sn vs medyan 14.5sn — aşırı sapma, bazı filmler çok yavaş

### En Yavaş 10 Film

- ÇIKIŞ: 2001sn (33.4 dk)
- AYAK TAKIMI: 1794sn (29.9 dk)
- KANDAHAR: 1693sn (28.2 dk)
- LELAND BİRLEŞİK DEVLETLERİ: 1560sn (26.0 dk)
- MEVLANA AŞKIN DANSI: 1557sn (25.9 dk)
- ATEŞİN IŞIĞI: 1418sn (23.6 dk)
- HASİP İLE NASİP: 1269sn (21.2 dk)
- BEŞ KAFADAR: 1221sn (20.4 dk)
- BAŞKASININ KARISI: 1189sn (19.8 dk)
- NAMUS DÜŞMANI: 1175sn (19.6 dk)

## Toplu Koşu İlerlemesi
- **İşlenen:** 46 film
- **Atlanan:** 28
- **Son:** [74/1825] --- [74/1825] rc=1 evoArcadmin_03072026SAYFA32_1984-0300-1-0
