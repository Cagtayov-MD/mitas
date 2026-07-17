# Faz 0 — Giriş-jenerik BİTİŞ ground-truth (18 film)
**Yöntem:** tarafsız montaj (frames/giris ~52 kare, step ~7 ≈ 3.5s, dedektör ipucu YOK) → 6 high-Sonnet ajanı görsel etiketledi.
**Hassasiyet:** ±7 kare (örnekleme adımı). fps=2 → sn = kare/2. END_FRAME = son kredi karesi (frames/giris index uzayı).

| # | Film | Tip | OPENING | END_FRAME | FILM_START | sn | Güven | Not |
|---|------|-----|---------|-----------|-----------|----|----|-----|
| 1 | YAŞAMAK 2020 | none | **NO** | NONE | #0 | — | med | cold-open; ilk kareden sahne |
| 2 | ZİHİN AVI 1953 | **over-footage (DE)** | **YES** | **~#290** | ~#300 | ~145 | DÜZELTİLDİ | ⚠ GT-HATASI düzeltildi: montaj-etiketi "cold" YANLIŞTI. OneOCR teyit: #13 "Die Unbesiegbaren" (Almanca başlık), #195 "Michaela Ehlbeck/Schnitt", #290 "Jakob Schauffelen/Regie" — gerçek Almanca açılış kredisi (footage-üstü, faint → montajda kaçtı). Detektör `found`=DOĞRU. |
| 3 | ALİTA 2025 | logo+title | YES | #42 | #49 | 21 | med | yalnız Fox logo→sahne, cast-süper yok |
| 4 | TARZAN 2016 | logo+title | YES | #44 | #51 | 22 | high | WB/Legendary logo bloğu→savan |
| 5 | X-MEN WOLVERINE 2009 | mixed | YES | #50 | #57 | 25 | high | Fox/Marvel logo + kısa süper→sahne |
| 6 | YERÇEKİMİ 2017 | title-only | YES | #49 | #56 | 24 | high | WB + "372 mil" kartları→uzay; minimal kredi |
| 7 | VENEDİK'TE ÖLÜM 1995 | static-cards | YES | **~#52** | ~#56 | ~26 | DÜZELTİLDİ | ⚠ GT-HATASI: eski #82 fazla-saydı ("ACT ONE" bölüm-kartı). OneOCR-spot: #60/#70/#80 BOŞ (yazı yok) → krediler ~#50'de bitiyor. Detektör #55 ≈ DOĞRU (GOOD). |
| 8 | CEMİLE 1998 | painted-intro | YES | #63 | #77 | 31 | med | Kiril "ДЖАМИЛЯ" başlık→resimli sahne |
| 9 | TOMRİS 2019 | title-only | YES | #105 | #112 | 52 | med | karanlık ön-sekans + "TOMRİS" kartı |
| 10 | SÖZ 2018 | logo+title | YES | #119 | #126 | 59 | med | animasyon + "LAMP" logo tekrarı→aksiyon |
| 11 | YANAN YATAK 1984 | static-cards | YES | #119 | #133 | 59 | high | siyah-zemin cast/crew → "Directed by" |
| 12 | ZOR YILLAR 1956 | mixed | YES | #148 | #155 | 74 | high | Universal + başlık + "MONTANA GEORGE" lokasyon-kartı |
| 13 | DEMİRYOLU SAVAŞI 1946 | static-cards | YES | #281 | #288 | 140 | med | yoğun FR B&W kart + uzun ithaf-metni |
| 14 | TEMEL REİS 1980 (Popeye) | static-cards | YES | #310 | #322 | 155 | high | uzun cast/crew → "ROBERT ALTMAN" yönetmen kartı |
| 15 | TRUMAN SHOW 1998 | over-footage | YES | #317 | #322 | 158 | high | sahte-belgesel konuşan-kafa süperleri → geç başlık kartı |
| 16 | FLASHDANCE 1983 | over-footage | YES | #300 | #307 | 150 | med | gece sahne üstü kırmızı cast-süperleri ~150s'e dek |
| 17 | İYİ KÖTÜ VE ÇİRKİN 1966 | over-footage | YES | #343 | #350 | 171 | med | uzun stilize jenerik; süper ~171s'e dek (pencere sonuna yakın) |

> Not: TERMİNATÖR KARA KADER 2025 (batch 1) ayrıca etiketlendi (over-footage, END≈#119) ama başlık-kartı okunuşu şüpheli → kalibrasyonda DÜŞÜK-ağırlık/ihtiyatlı kullan.

## Tasarım için çıkarımlar (find_offset)
1. **"Kısa kredi" varsayımı YOK.** END dağılımı #42 → #343 (171s); pencere (360 kare) bazı filmlerde krediyi ANCAK kapsıyor. find_offset pencere-sonuna kadar tarayabilmeli.
2. **Cold-open = boş havuz ZORUNLU** (YAŞAMAK, ZİHİN AVI). En kritik FP testi: ilk sahneyi kredi sanma → `no_opening_credits`.
3. **Footage-üstü sınırı** (TRUMAN/FLASHDANCE/İYİ KÖTÜ/X-MEN) = kredi-METNİ sürdürülen şekilde BİTTİĞİ kare; "footage başladı" DEĞİL (footage zaten akıyor). Sinyal = paddle'ın süperlenmiş ismi metin sayması.
4. **Geç-kart** (TEMEL REİS/YANAN YATAK cast→…→yönetmen): gap-bütçesi kart-arası boşlukları köprülemeli; bu sette aşırı-uzun-boşluk geç-kart yok ama tasarımda ele al.
5. **Logo lead-in** (ALİTA/TARZAN/WB/Fox): havuz 0'dan başladığı için doğal dahil; START özel-işlem gerekmez. Ama logo-only→sahne (ALİTA cast-süper yok) = çok-kısa kredi; "title-only/logo-only" geçerli sayılmalı.
6. **Belirsiz/med-güven** (CEMİLE resimli, DEMİRYOLU ithaf-metni, over-footage ±14): bunlar montaj-çözünürlük sınırı; gerekirse sınır-etrafı ZOOM montajıyla yeniden-etiketle.

## Veri (makine-okunur)
```
YAŞAMAK_2020 none NONE
ZİHİN_AVI_1953 over-footage-DE 290
ALİTA_2025 logo+title 42
TARZAN_2016 logo+title 44
X-MEN_2009 mixed 50
YERÇEKİMİ_2017 title-only 49
VENEDİK_1995 static 52
CEMİLE_1998 painted 63
TOMRİS_2019 title-only 105
SÖZ_2018 logo+title 119
YANAN_YATAK_1984 static 119
ZOR_YILLAR_1956 mixed 148
DEMİRYOLU_1946 static 281
TEMEL_REİS_1980 static 310
TRUMAN_1998 over-footage 317
FLASHDANCE_1983 over-footage 300
İYİ_KÖTÜ_1966 over-footage 343
```
