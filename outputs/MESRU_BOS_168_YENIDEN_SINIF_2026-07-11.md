# MESRU-BOS 168-BULGU YENIDEN-SINIFLAMA (İP-9) — 2026-07-11

> Kaynak: KOKNEDEN_MASTER.csv (D_JENERIKTE_YOK + C_OKUNAMAZ = 168 alan-bulgusu).
> Grandfather YOK: hepsi 6-durum kapisindan yeniden gecer. VL cift-tanik ON-KOSUL.
> Benzersiz film: 105 | VL gerektiren bulgu: 168/168

## VL-oncesi on-durum (deterministik kisim)
- SOURCE_ABSENT: 141
- SOURCE_UNREADABLE: 27

## KRITIK KURAL
- C_OKUNAMAZ (27 bulgu) OTOMATIK TEKNIK_ARIZA SAYILMAZ — VL 'metin var mi' teyidi:
  metin VAR -> OCR_MISSED_VISIBLE_TEXT (TEKNIK_ARIZA, retry); YOK -> kaynak-okunamaz (mesru-bos).
- Muhur yalniz insan-onayli + terminal durum; yeni frame/OCR gelince (hash degisir) GECERSIZ.

## SONRAKI ADIM
- 168 bulgu icin VL cift-tanik kosulacak. VL-MALIYETI once olculur (asagida).