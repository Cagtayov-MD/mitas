# OCR Filmtest 18 - Auto ROI v2b OneOCR Gerçek Veri Raporu

Tarih: 2026-05-22

## Koşu

- Output: E:\MITAS\outputs\ocr_credit_experiments\filmtest_last3min_auto_roi_v2b_oneocr_20260522
- Manifest: E:\MITAS\data\ocr_filmtest_last3min_manifest_20260522.json
- Engines: oneocr
- fps override: 1
- max frames: 30
- preprocess: off
- Completed: 18/18
- Failed: 0

## Özet

- Item status: {'partial': 5, 'done': 13}
- Auto ROI stratejileri: {'hint_credit_safe_center_crop': 18}
- Router temporal kararları: {'segment_then_route': 2, 'best_frame_selection': 4, 'temporal_voting': 7, 'row_reconstruct': 5}
- Row crop OCR durumları: {'done': 3, 'skipped': 15}
- Toplam frame OCR record: 5307
- Toplam stable group: 741

## Ana Bulgular

- Auto ROI v2b KJ/lower-third sentetikte yazı bölgesini net buluyor; filmtest son jeneriklerinde ise gerçek görüntü arka planları çok karmaşık olduğu için çoğunlukla güvenli merkez crop fallback kullandı.
- Bu kötü bir çöküş değil: sistem full frame yerine güvenli crop ile devam etti. Ama bu, gerçek film jeneriklerinde text-mask tabanlı nokta ROI’nin henüz üretim kalitesinde olmadığını gösteriyor.
- OneOCR ile bazı filmler çok güçlü metin verdi: FIRTINANIN_İÇİNDE, SON_HAVA_BÜKÜCÜ, FARELER_VE_İNSANLAR, NEBRASKA.
- Row crop OCR çoğu filmde çalışmadı/skipped; sebep router’ın bu segmentleri row_reconstruct yerine temporal_voting/static/mixed dışı görmesi veya row_reconstruct kalite kapısının tetiklenmemesi. Bu bize row pipeline entegrasyonunu daha agresif/opsiyonel hale getirmemiz gerektiğini söylüyor.

## Film Tablosu

| # | Film | Status | ROI strategy | ROI | Frame OCR | Stable | Router | Row OCR | Runtime |
| ---: | --- | --- | --- | --- | ---: | ---: | --- | --- | ---: |
| 1 | 01_evoArcadmin_COZUMLEMEV2S17_1925-0009-1-0000-00-1-SON_ADAM | partial | hint_credit_safe_center_crop | [42, 19, 516, 442] | 0 | 0 | segment_then_route | done:0 | 10.966 |
| 2 | 02_evoArcadmin_COZUMLEMEV2S17_1988-0375-1-0000-00-1-KONTES_MARIZA | done | hint_credit_safe_center_crop | [42, 19, 516, 442] | 24 | 7 | best_frame_selection | done:1 | 11.307 |
| 3 | 03_evoArcadmin_COZUMLEMEV2S17_1991-0339-1-0000-01-1-K-2 | done | hint_credit_safe_center_crop | [42, 19, 516, 442] | 1 | 0 | segment_then_route | done:0 | 10.117 |
| 4 | 04_evoArcadmin_COZUMLEMEV2S17_1991-0377-1-0000-00-1-SİYAH_KADİFE_ELBİSE | partial | hint_credit_safe_center_crop | [42, 19, 516, 442] | 0 | 0 | temporal_voting | skipped:0 | 8.497 |
| 5 | 05_evoArcadmin_SİNEMA_FİLM_1950-2118-1-0000-90-1-GÜN_BATISI | partial | hint_credit_safe_center_crop | [35, 11, 442, 266] | 0 | 0 | temporal_voting | skipped:0 | 4.808 |
| 6 | 06_evoArcadmin_SİNEMA_FİLM_1990-0325-1-0000-90-1-BABA_3 | done | hint_credit_safe_center_crop | [35, 11, 442, 266] | 659 | 95 | row_reconstruct | skipped:0 | 7.787 |
| 7 | 07_evoArcadmin_SİNEMA_FİLM_2016-1000-1-0000-90-1-ÖFKE_(FURY) | done | hint_credit_safe_center_crop | [35, 11, 442, 266] | 1104 | 161 | row_reconstruct | skipped:0 | 10.793 |
| 8 | 08_evoArcadmin_SİNEMA_FİLM_2017-9031-1-0000-85-1-BEYAZ_BALİNA | partial | hint_credit_safe_center_crop | [59, 19, 736, 442] | 0 | 0 | temporal_voting | skipped:0 | 12.707 |
| 9 | 09_evoArcadmin_ÇÖZÜMLEME5_1941-1147-1-0000-50-1-MALTA_ŞAHİNİ | done | hint_credit_safe_center_crop | [35, 11, 442, 266] | 43 | 12 | best_frame_selection | skipped:0 | 6.923 |
| 10 | 10_evoArcadmin_ÇÖZÜMLEME5_1955-1147-1-0000-90-1-KANLI_İNTİKAM | partial | hint_credit_safe_center_crop | [35, 11, 442, 266] | 0 | 0 | temporal_voting | skipped:0 | 6.367 |
| 11 | 11_evoArcadmin_ÇÖZÜMLEME5_1983-0176-1-0000-90-1-ÇARIKLI_MİLYONER | done | hint_credit_safe_center_crop | [35, 11, 442, 266] | 1 | 0 | temporal_voting | skipped:0 | 6.432 |
| 12 | 12_evoArcadmin_ÇÖZÜMLEME5_1992-1150-1-0000-50-1-FARELER_VE_İNSANLAR | done | hint_credit_safe_center_crop | [35, 11, 442, 266] | 306 | 46 | row_reconstruct | skipped:0 | 9.57 |
| 13 | 13_evoArcadmin_ÇÖZÜMLEME5_2016-1223-1-0000-50-0-KESİŞEN_HAYATLAR | done | hint_credit_safe_center_crop | [35, 11, 442, 266] | 110 | 25 | best_frame_selection | skipped:0 | 7.101 |
| 14 | 14_evoArcadmin_ÇÖZÜMLEME6_1978-1112-1-0000-66-0-MACARLAR | done | hint_credit_safe_center_crop | [59, 19, 736, 442] | 18 | 4 | temporal_voting | skipped:0 | 13.184 |
| 15 | 15_evoArcadmin_ÇÖZÜMLEME6_2013-1002-1-0000-50-1-NEBRASKA | done | hint_credit_safe_center_crop | [59, 19, 736, 442] | 238 | 46 | best_frame_selection | skipped:0 | 12.549 |
| 16 | 16_evoArcadmin_ÇÖZÜMLEME6_2014-1090-1-0000-90-1-FIRTINANIN_İÇİNDE | done | hint_credit_safe_center_crop | [59, 19, 736, 442] | 1223 | 146 | row_reconstruct | skipped:0 | 21.878 |
| 17 | 17_evoArcadmin_ÇÖZÜMLEME6_2024-1208-1-0000-90-1-SON_HAVA_BÜKÜCÜ | done | hint_credit_safe_center_crop | [59, 19, 736, 442] | 1576 | 199 | row_reconstruct | skipped:0 | 24.8 |
| 18 | 18_web_client_CAG1_2024-0007-0-0070-91-1-MEHMED_FETİHLER_SULTANI | done | hint_credit_safe_center_crop | [89, 28, 1102, 664] | 4 | 0 | temporal_voting | skipped:0 | 27.063 |

## Örnek OCR Metinleri

### 1. filmtest_01_evoArcadmin_COZUMLEMEV2S17_1925-0009-1-0000-00-1-SON_ADAM

- OCR metni yok veya stabil grup oluşmadı.

### 2. filmtest_02_evoArcadmin_COZUMLEMEV2S17_1988-0375-1-0000-00-1-KONTES_MARIZA

- Taşırım seni uzaklara dek
- Evet de sevgilim evet de
- Kollarımda seni incitmeden
- Mutluluk sana yakın olduğu
- Taşırım seni kollarımda
- sürece
- tuttuğumu hisset
- IER

### 3. filmtest_03_evoArcadmin_COZUMLEMEV2S17_1991-0339-1-0000-01-1-K-2

- 5412

### 4. filmtest_04_evoArcadmin_COZUMLEMEV2S17_1991-0377-1-0000-00-1-SİYAH_KADİFE_ELBİSE

- OCR metni yok veya stabil grup oluşmadı.

### 5. filmtest_05_evoArcadmin_SİNEMA_FİLM_1950-2118-1-0000-90-1-GÜN_BATISI

- OCR metni yok veya stabil grup oluşmadı.

### 6. filmtest_06_evoArcadmin_SİNEMA_FİLM_1990-0325-1-0000-90-1-BABA_3

- production assistant
- prop department
- art department
- first assistant photographer
- second assistant director
- AUGUSTO GRASSI . CRISTIANA RICCERI
- DANIEL ACON
- DANIEL CHARLES HOFFMAN

### 7. filmtest_07_evoArcadmin_SİNEMA_FİLM_2016-1000-1-0000-90-1-ÖFKE_(FURY)

- Crowd 2nd 2nd Assistant Director
- Second Assistant Director
- Base Production Assistant
- Unit Location Manager
- 2nd Unit 2nd Assistant Director
- Background Actors Provided By
- ANTHONY OWEN
- BRUNO CASSONI

### 8. filmtest_08_evoArcadmin_SİNEMA_FİLM_2017-9031-1-0000-85-1-BEYAZ_BALİNA

- OCR metni yok veya stabil grup oluşmadı.

### 9. filmtest_09_evoArcadmin_ÇÖZÜMLEME5_1941-1147-1-0000-50-1-MALTA_ŞAHİNİ

- Belki biliyorum. Seni gönderdikten sonra,
- birkaç gece acı çekerim ama bu geçer.
- Söylediklerim senin için bir anlam ifade
- Yapamam çünkü sonuçları ne olursa olsun
- etmediyse, unut gitsin. şöyle yapacağız.
- içimdeki tüm sesler ...
- bana bunu yapar mıydın?
- Şahin gerçek çıksa ve paranı alsan,

### 10. filmtest_10_evoArcadmin_ÇÖZÜMLEME5_1955-1147-1-0000-90-1-KANLI_İNTİKAM

- OCR metni yok veya stabil grup oluşmadı.

### 11. filmtest_11_evoArcadmin_ÇÖZÜMLEME5_1983-0176-1-0000-90-1-ÇARIKLI_MİLYONER

- OCR metni yok veya stabil grup oluşmadı.

### 12. filmtest_12_evoArcadmin_ÇÖZÜMLEME5_1992-1150-1-0000-50-1-FARELER_VE_İNSANLAR

- Art Director DAN DAVIS
- Assistant Production Coordinator
- Boom Operator LYNN BOPELEY
- First Assistant Director CARA GIALLANZA
- G. STEWART SHAW
- JOYCE ANNE GILSTRAP
- Leadmen
- Second Assistant Director MICHELE PANELLI - VENETIS

### 13. filmtest_13_evoArcadmin_ÇÖZÜMLEME5_2016-1223-1-0000-50-0-KESİŞEN_HAYATLAR

- CHEF ELECTRICIEN
- CHEF MACHINISTE
- COSTUMES
- ISABELLE PANNETIER
- MARC WILHELM
- NICOLAS AMEDEO
- SÉBASTIEN DIDELOT - AFR
- 1"" ASSISTANT RLALISATEUR

### 14. filmtest_14_evoArcadmin_ÇÖZÜMLEME6_1978-1112-1-0000-66-0-MACARLAR

- hilft Dirnicht.
- uche Jesum
- es andere
- ihd sein Licht
- Indere
- Lich
- MdSein
- a

### 15. filmtest_15_evoArcadmin_ÇÖZÜMLEME6_2013-1002-1-0000-50-1-NEBRASKA

- SECOND ASSISTANT ACCOUNTANT
- PRODUCTION ACCOUNTANT
- ACCOUNTING CLERK
- APPRENTICE EDITOR/VFX ARTIST
- ASSISTANT EDITOR
- ASSISTANT PRODUCTION COÖRDINATOR
- ASSISTANT PROPERTY MASTER
- BOOM OPERATOR

### 16. filmtest_16_evoArcadmin_ÇÖZÜMLEME6_2014-1090-1-0000-90-1-FIRTINANIN_İÇİNDE

- A CAMERA IST ASSISTANT
- SET COSTUMERS
- ASSISTANT EDITORS
- B CAMERA 2ND ASSISTANT
- SET DRESSERS
- SUPERVISING SOUND EDITOR
- A CAMERA OPERATOR/STEADICAM
- AARON SCHNEIDER, ASC

### 17. filmtest_17_evoArcadmin_ÇÖZÜMLEME6_2024-1208-1-0000-90-1-SON_HAVA_BÜKÜCÜ

- KEVIN GALLAGHER
- MICHAEL GILBERT
- Construction Grips
- MICHAEL CARROLL, JR.
- ANDRE KERR
- ASIM KHAN
- BENJAMIN HARRIS
- BRIAN ANDREW McCAFFERTY

### 18. filmtest_18_web_client_CAG1_2024-0007-0-0070-91-1-MEHMED_FETİHLER_SULTANI

- O
- O
- O
- e

## Net Karar

Auto ROI v2b gerçek koşuda sistemi bozmadı ve full-frame yükünü azalttı; fakat gerçek film jeneriklerinde text-mask ROI halen fazla temkinli/fallback ağırlıklı. KJ tarafı için doğru yoldayız; jenerik tarafında daha iyi ROI için OCR detection bbox veya Paddle det/OneOCR bbox tabanlı ikinci aşama eklenmeli.

Sıradaki teknik düzeltme: Auto ROI kararını sadece pre-OCR maskeye bırakmamak. İlk 3-5 frame OCR/text detection bbox ile ikinci-pass ROI rafine edilmeli. Bu KJ için de jenerik için de daha güvenilir olur.
