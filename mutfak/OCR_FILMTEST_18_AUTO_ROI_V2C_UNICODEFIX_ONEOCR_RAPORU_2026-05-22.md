# OCR Filmtest 18 - Auto ROI v2c Unicode Fix OneOCR Raporu

Tarih: 2026-05-22

## Koşu

- Output: E:\MITAS\outputs\ocr_credit_experiments\filmtest_last3min_auto_roi_v2c_unicodefix_oneocr_20260522
- Manifest: E:\MITAS\data\ocr_filmtest_last3min_manifest_20260522.json
- Engines: oneocr
- fps override: 1
- max frames: 30
- preprocess: off
- Completed: 18/18
- Failed: 0

## Özet

- Item status: {'partial': 5, 'done': 13}
- Auto ROI stratejileri: {'hint_credit_safe_center_crop': 16, 'text_density_credit': 2}
- Router temporal kararları: {'segment_then_route': 9, 'best_frame_selection': 4, 'row_reconstruct': 5}
- Row crop OCR durumları: {'done': 18}
- Row split durumları: {'no_clear_column_gap': 4, 'detected': 11, 'no_balanced_gap': 2, 'detected_low_confidence': 1}
- Row motion durumları: {'static_or_low_scroll': 9, 'ok': 9}
- Toplam frame OCR record: 5308
- Toplam stable group: 741
- Toplam row OCR record: 307
- Toplam nonempty row pair: 92

## Ana Bulgular

- Unicode path problemi düzeltildi. Önceki koşuda Türkçe karakterli item klasörlerinde OpenCV frame okuyamadığı için row pipeline skipped/failed görünüyordu; v2c koşusunda row_reconstruct 18/18 itemda çalıştı.
- Auto ROI v2c gerçek filmtestte 18/18 güvenli merkez crop fallback kullandı. Bu, full-frame yerine daha dar ve güvenli crop demek; fakat henüz gerçek jenerik/KJ metnini nokta atışı bulan güçlü text ROI değil.
- KJ/lower-third sentetik testte text-density ROI başarılı; gerçek filmtest son jenerikleri KJ değil ve arka planlar karmaşık olduğu için pre-OCR mask güvenilir davranmadı.
- Row reconstruct değer üretti: 18/18 itemda row_count çıktı, 9 itemda row OCR’dan nonempty pair geldi.
- En güçlü OCR veren filmler: SON_HAVA_BÜKÜCÜ, FIRTINANIN_İÇİNDE, ÖFKE/FURY, BABA_3, FARELER_VE_İNSANLAR.
- En zayıf/boş kalanlar: SON_ADAM, SİYAH_KADİFE_ELBİSE, GÜN_BATISI, BEYAZ_BALİNA, KANLI_İNTİKAM.

## Film Tablosu

| # | Film | Status | ROI | Frame OCR | Stable | Router | Rows | Split | Row OCR nonempty | dy/frame | Runtime |
| ---: | --- | --- | --- | ---: | ---: | --- | ---: | --- | ---: | ---: | ---: |
| 1 | 01_evoArcadmin_COZUMLEMEV2S17_1925-0009-1-0000-00-1-SON_ADAM | partial | [42, 19, 516, 442] | 0 | 0 | segment_then_route | 12 | no_clear_column_gap | 0 | 0.1929 | 11.318 |
| 2 | 02_evoArcadmin_COZUMLEMEV2S17_1988-0375-1-0000-00-1-KONTES_MARIZA | done | [42, 19, 516, 442] | 24 | 7 | best_frame_selection | 10 | detected | 1 | 0.0 | 11.2 |
| 3 | 03_evoArcadmin_COZUMLEMEV2S17_1991-0339-1-0000-01-1-K-2 | done | [42, 19, 516, 442] | 1 | 0 | segment_then_route | 7 | detected | 0 | 0.7725 | 9.965 |
| 4 | 04_evoArcadmin_COZUMLEMEV2S17_1991-0377-1-0000-00-1-SİYAH_KADİFE_ELBİSE | partial | [42, 19, 516, 442] | 0 | 0 | segment_then_route | 10 | detected | 0 | 0.1376 | 10.893 |
| 5 | 05_evoArcadmin_SİNEMA_FİLM_1950-2118-1-0000-90-1-GÜN_BATISI | partial | [35, 11, 442, 266] | 0 | 0 | segment_then_route | 5 | no_balanced_gap | 0 | 0.033 | 6.139 |
| 6 | 06_evoArcadmin_SİNEMA_FİLM_1990-0325-1-0000-90-1-BABA_3 | done | [35, 11, 442, 266] | 659 | 95 | row_reconstruct | 10 | detected | 4 | 6.6956 | 9.051 |
| 7 | 07_evoArcadmin_SİNEMA_FİLM_2016-1000-1-0000-90-1-ÖFKE_(FURY) | done | [35, 11, 442, 266] | 1104 | 161 | row_reconstruct | 23 | detected | 21 | -16.0426 | 13.884 |
| 8 | 08_evoArcadmin_SİNEMA_FİLM_2017-9031-1-0000-85-1-BEYAZ_BALİNA | partial | [59, 19, 736, 442] | 0 | 0 | segment_then_route | 1 | no_clear_column_gap | 0 | 0.8363 | 14.753 |
| 9 | 09_evoArcadmin_ÇÖZÜMLEME5_1941-1147-1-0000-50-1-MALTA_ŞAHİNİ | done | [35, 11, 442, 266] | 43 | 12 | best_frame_selection | 7 | no_balanced_gap | 1 | 0.0325 | 8.171 |
| 10 | 10_evoArcadmin_ÇÖZÜMLEME5_1955-1147-1-0000-90-1-KANLI_İNTİKAM | partial | [35, 11, 442, 266] | 0 | 0 | segment_then_route | 6 | detected_low_confidence | 0 | 0.0 | 7.647 |
| 11 | 11_evoArcadmin_ÇÖZÜMLEME5_1983-0176-1-0000-90-1-ÇARIKLI_MİLYONER | done | [35, 11, 442, 266] | 1 | 0 | segment_then_route | 4 | detected | 0 | -0.107 | 7.47 |
| 12 | 12_evoArcadmin_ÇÖZÜMLEME5_1992-1150-1-0000-50-1-FARELER_VE_İNSANLAR | done | [35, 11, 442, 266] | 306 | 46 | row_reconstruct | 10 | detected | 10 | -6.7396 | 11.126 |
| 13 | 13_evoArcadmin_ÇÖZÜMLEME5_2016-1223-1-0000-50-0-KESİŞEN_HAYATLAR | done | [122, 82, 269, 186] | 111 | 25 | best_frame_selection | 2 | detected | 2 | 0.0 | 5.959 |
| 14 | 14_evoArcadmin_ÇÖZÜMLEME6_1978-1112-1-0000-66-0-MACARLAR | done | [59, 19, 736, 442] | 18 | 4 | segment_then_route | 5 | detected | 1 | -1.2405 | 16.032 |
| 15 | 15_evoArcadmin_ÇÖZÜMLEME6_2013-1002-1-0000-50-1-NEBRASKA | done | [191, 151, 472, 179] | 238 | 46 | best_frame_selection | 4 | detected | 4 | 0.0 | 8.168 |
| 16 | 16_evoArcadmin_ÇÖZÜMLEME6_2014-1090-1-0000-90-1-FIRTINANIN_İÇİNDE | done | [59, 19, 736, 442] | 1223 | 146 | row_reconstruct | 24 | no_clear_column_gap | 15 | -7.0394 | 24.26 |
| 17 | 17_evoArcadmin_ÇÖZÜMLEME6_2024-1208-1-0000-90-1-SON_HAVA_BÜKÜCÜ | done | [59, 19, 736, 442] | 1576 | 199 | row_reconstruct | 58 | no_clear_column_gap | 33 | -41.6957 | 30.707 |
| 18 | 18_web_client_CAG1_2024-0007-0-0070-91-1-MEHMED_FETİHLER_SULTANI | done | [89, 28, 1102, 664] | 4 | 0 | segment_then_route | 9 | detected | 0 | 5.9227 | 31.829 |

## Örnek OCR Metinleri

### 1. filmtest_01_evoArcadmin_COZUMLEMEV2S17_1925-0009-1-0000-00-1-SON_ADAM

- OCR metni yok veya stabil grup oluşmadı.

### 2. filmtest_02_evoArcadmin_COZUMLEMEV2S17_1988-0375-1-0000-00-1-KONTES_MARIZA

Row crop örnekleri:
- ROLE=[] NAME=[616] CONF=[0.3776]

Temporal örnekleri:
- Taşırım seni uzaklara dek
- Evet de sevgilim evet de
- Kollarımda seni incitmeden
- Mutluluk sana yakın olduğu
- Taşırım seni kollarımda
- sürece
- tuttuğumu hisset
- IER

### 3. filmtest_03_evoArcadmin_COZUMLEMEV2S17_1991-0339-1-0000-01-1-K-2

Temporal örnekleri:
- 5412

### 4. filmtest_04_evoArcadmin_COZUMLEMEV2S17_1991-0377-1-0000-00-1-SİYAH_KADİFE_ELBİSE

- OCR metni yok veya stabil grup oluşmadı.

### 5. filmtest_05_evoArcadmin_SİNEMA_FİLM_1950-2118-1-0000-90-1-GÜN_BATISI

- OCR metni yok veya stabil grup oluşmadı.

### 6. filmtest_06_evoArcadmin_SİNEMA_FİLM_1990-0325-1-0000-90-1-BABA_3

Row crop örnekleri:
- ROLE=["sliverfish" assistant] NAME=[RICCARDO TERLIZZI] CONF=[0.8698]
- ROLE=[producer's assistant] NAME=[ANDREA DAMIANO] CONF=[0.8608]
- ROLE=[produclion secretary] NAME=[CECILIA ALVARENGA] CONF=[0.8729]
- ROLE=[production assistants] NAME=[MATTEO DE LAURENTIIS] CONF=[0.7891]

Temporal örnekleri:
- production assistant
- prop department
- art department
- first assistant photographer
- second assistant director
- AUGUSTO GRASSI . CRISTIANA RICCERI
- DANIEL ACON
- DANIEL CHARLES HOFFMAN

### 7. filmtest_07_evoArcadmin_SİNEMA_FİLM_2016-1000-1-0000-90-1-ÖFKE_(FURY)

Row crop örnekleri:
- ROLE=[Hair & Makeup Designer ALESSANDRO BERTO Key Makeup Artist MARTA ROGGERO] NAME=[LAZZI] CONF=[0.9095]
- ROLE=[Key Hair Stylist LUCA SACCUMAN Makeup Artist to Mr. Pitt JEAN BLACK Hair & Makeup Artists ZOEY STONES RALP VERALPA] NAME=[] CONF=[0.7696]
- ROLE=[Crowd Hair & Makeup Supervisor KATHRYN FA Crowd Hair & Makeup Artists ANNETTE FIELD GXUeEABUARVIA CHIARA LGOUNL] NAME=[] CONF=[0.7382]
- ROLE=[Supervising Location Manager RUSSELL LODGE LEE ROBERTSON] NAME=[] CONF=[0.9809]
- ROLE=[ASHA SHARMA BRUNO CASSONI Unit Location Manager] NAME=[] CONF=[0.9836]
- ROLE=[Location Assistant RACHEL ROSSER Location Scout PHIL LOBBAN] NAME=[] CONF=[0.9493]
- ROLE=[Still Photoarapher GILES KEYTE Second Assistant Director TOM WHITE] NAME=[] CONF=[0.9527]
- ROLE=[Crowd 2nd 2nd Assistant Director TOM MULBERGE JASON RICKWOOD 3rd Assistant Director] NAME=[] CONF=[0.9688]

Temporal örnekleri:
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

Row crop örnekleri:
- ROLE=[] NAME=[Beni sevip sevmediğini biliyorsun.] CONF=[0.9915]

Temporal örnekleri:
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

Row crop örnekleri:
- ROLE=[Unit Production Manager] NAME=[ALAN C. BLOMQUIST] CONF=[0.9888]
- ROLE=[] NAME=[MIOUEY E DAMEE LI VEMETIC] CONF=[0.3799]
- ROLE=[Aut nisaains] NAME=[nAN NAVIC] CONF=[0.6092]
- ROLE=[] NAME=[UVIT ALUVI] CONF=[0.581]
- ROLE=[Acsistant Psoductino Conrdioator] NAME=[TAMABA ALLEN ..] CONF=[0.5867]
- ROLE=[Assistant Costume Designer] NAME=[AUSTIN MYERS] CONF=[0.9905]
- ROLE=[Set Costumer] NAME=[TIMOTHY WEGMAN] CONF=[0.9921]
- ROLE=[Makeup Artist] NAME=[BONITA DeHAVEN] CONF=[0.9904]

Temporal örnekleri:
- Art Director DAN DAVIS
- Assistant Production Coordinator
- Boom Operator LYNN BOPELEY
- First Assistant Director CARA GIALLANZA
- G. STEWART SHAW
- JOYCE ANNE GILSTRAP
- Leadmen
- Second Assistant Director MICHELE PANELLI - VENETIS

### 13. filmtest_13_evoArcadmin_ÇÖZÜMLEME5_2016-1223-1-0000-50-0-KESİŞEN_HAYATLAR

Row crop örnekleri:
- ROLE=[DIRECTEUR DE PRODUCTION MATHIEU VERHAEGHE - A] NAME=[DP] CONF=[0.7715]
- ROLE=[DIRECTRICE DE POST-PRODUCTION CLARA VINC CIENNE] NAME=[] CONF=[0.6597]

Temporal örnekleri:
- CHEF LLECTRICIEN
- CHEF MACHINISTE
- COSTUMES
- ISABELLE PANNETIER
- MARC WILHELM
- NICOLAS AMEDEO
- SÉBASTIEN DIDELOT - AFR
- 1" ASSISTANT RLALISATEUR

### 14. filmtest_14_evoArcadmin_ÇÖZÜMLEME6_1978-1112-1-0000-66-0-MACARLAR

Row crop örnekleri:
- ROLE=[] NAME=[bilft Dirnicht. O] CONF=[0.3316]

Temporal örnekleri:
- hilft Dirnicht.
- uche Jesum
- es andere
- ihd sein Licht
- Indere
- Lich
- MdSein
- a

### 15. filmtest_15_evoArcadmin_ÇÖZÜMLEME6_2013-1002-1-0000-50-1-NEBRASKA

Row crop örnekleri:
- ROLE=[SECOND UNIT CINEMATOGRAPHER PRODUCTION CONSULTANT] NAME=[RADAN POPOVIC, SAS STEPHEN ABARIOTES] CONF=[0.9904]
- ROLE=[LOCATION MANAGER] NAME=[JOHN LATENSER V] CONF=[0.9888]
- ROLE=[ASSISTANT LOCATION MANAGERS] NAME=[JAMIE VESAY TODD FEASER] CONF=[0.9324]
- ROLE=[] NAME=[TODD FEASER ANNE RYAN GAUER KENDDA LIGDLE] CONF=[0.7168]

Temporal örnekleri:
- SECOND ASSISTANT ACCOUNTANT
- PRODUCTION ACCOUNTANT
- ACCOUNTING CLERK
- APPRENTICE EDITOR/VFX ARTIST
- ASSISTANT EDITOR
- ASSISTANT PRODUCTION COÖRDINATOR
- ASSISTANT PROPERTY MASTER
- BOOM OPERATOR

### 16. filmtest_16_evoArcadmin_ÇÖZÜMLEME6_2014-1090-1-0000-90-1-FIRTINANIN_İÇİNDE

Row crop örnekleri:
- ROLE=[] NAME=[NEWS ANCHOR STEVE GARAGIOLA] CONF=[0.9883]
- ROLE=[] NAME=[BOB BROWN STUNT COORDINATORS COTT WORKMAN] CONF=[0.9736]
- ROLE=[] NAME=[STUNTS CHARLIE BREWER JEFF CHASE GAELLE COHEN] CONF=[0.9889]
- ROLE=[] NAME=[DANNY RAY COOK CHAD DASHNAW ZACK DUHAME] CONF=[0.9859]
- ROLE=[] NAME=[AMAER WHELAN RLVIN ZACAMEA NICO WOULARD] CONF=[0.6402]
- ROLE=[] NAME=[DIA'MASK, SANSER RUKKI,SASECINIUS] CONF=[0.1245]
- ROLE=[] NAME=[COSTUME SUPERVISOR PATTY MALKIN] CONF=[0.6847]
- ROLE=[] NAME=[KARRTAULA SALDO AOCICTALIT PAITARO] CONF=[0.3732]

Temporal örnekleri:
- A CAMERA IST ASSISTANT
- SET COSTUMERS
- ASSISTANT EDITORS
- B CAMERA 2ND ASSISTANT
- SET DRESSERS
- SUPERVISING SOUND EDITOR
- A CAMERA OPERATOR/STEADICAM
- AARON SCHNEIDER, ASC

### 17. filmtest_17_evoArcadmin_ÇÖZÜMLEME6_2024-1208-1-0000-90-1-SON_HAVA_BÜKÜCÜ

Row crop örnekleri:
- ROLE=[] NAME=[Pro Tools Operator ERIK SWANSON Aix Assistant MATT WARD] CONF=[0.9484]
- ROLE=[] NAME=[MiX Assistant MAIT WARD Score Recorded at STREISAND SCORING STAGE SONY PICTURES STUDIOS URES STUDIC] CONF=[0.8856]
- ROLE=[] NAME=[SONT PICTURES STUDIOS Score Recordist ADAM MICHALAK] CONF=[0.8749]
- ROLE=[] NAME=[Scoring Crew MARK ESHELMAN . GREG LOSKORN DAVID MARQUETTE . JAY SELVESTER AY SELVE] CONF=[0.9015]
- ROLE=[] NAME=[Construction Coordinators BOB BLACKBURN ERNEST A. DOTTLINGER . FRANK T. STEVER Construction Forepersons CARMEN S SANIUKU .KOBEKU S VANSIUNE] CONF=[0.8228]
- ROLE=[] NAME=[CARMEN S. SANTOKO RODERT S. VANSTONE BENIAMIN R WHITE TALIA 1 A LEONE Consteuction Buver] CONF=[0.5917]
- ROLE=[] NAME=[Construction Buyer IALIA LEONE MICHAEL ADAMS MICHELLE BURNWORTH ADAM BAKER KEITH CLEARY] CONF=[0.9686]
- ROLE=[] NAME=[KSIM KHAN""THEODORE JAY LUBONOVICH "TIMOTHY LYNCH ANDRE KERR] CONF=[0.6946]

Temporal örnekleri:
- KEVIN GALLAGHER
- MICHAEL GILBERT
- Construction Grips
- MICHAEL CARROLL, JR.
- ANDRE KERR
- ASIM KHAN
- BENJAMIN HARRIS
- BRIAN ANDREW McCAFFERTY

### 18. filmtest_18_web_client_CAG1_2024-0007-0-0070-91-1-MEHMED_FETİHLER_SULTANI

Temporal örnekleri:
- O
- O
- O
- e

## Net Karar

Auto ROI v2c, sistemi bozmayacak güvenli crop katmanı olarak çalışıyor ve KJ için doğru zemini kuruyor; fakat gerçek jeneriklerde pre-OCR text-mask tek başına yeterli değil. Sıradaki doğru adım, ilk OCR/detection bbox sonuçlarından ikinci-pass ROI rafine etmek: önce güvenli crop, sonra OCR bbox union ile gerçek text ROI.

Bu rapordaki en önemli kazanım Auto ROI’den çok Unicode fix + row pipeline’ın 18/18 çalışır hale gelmesidir.
