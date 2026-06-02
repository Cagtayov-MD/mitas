# De-scroll Canvas ve Tek Jenerik Raporu - 18 Klip

## Net Cevap

- Panoramik/de-scroll pano **uretildi**: Phase 2 icin 18/18 klipte `descroll_canvas.png` var.
- Phase 2 kalite kapisi: 18/18 `pass`. Bu, hizalama sinyalinin teknik olarak tutarli oldugunu gosterir.
- Ama bu henuz “nihai temiz jenerik JSON/TXT” degil. Pano goruntusu uretildi; final jenerik metni icin stable-line siralama + dedupe ile aday `.txt` dosyalari ayrica uretildi.
- Kayan jeneriklerde pano mantigi calisti; statik/yatay veya az metinli kliplerde pano gereksiz ya da dusuk faydali.

- Canvas contact sheet: `E:\MITAS\outputs\ocr_credit_experiments\filmtest_last3min_overnight_20260522_v2\phase2_canvas_contact_sheet.jpg`
- Aday jenerik metinleri: `E:\MITAS\outputs\ocr_credit_experiments\filmtest_last3min_overnight_20260522_v2\candidate_credits_best_stable`

## Klip Bazinda Canvas Karari

| # | Klip | Pano var mi | Canvas karari | Boyut | Yon | dy/frame | Canvas OCR | Stable | Aday metin |
| ---: | --- | --- | --- | ---: | --- | ---: | ---: | ---: | --- |
| 1 | evoArcadmin COZUMLEMEV2S17 1925-0009-1-0000-00-1-SON ADAM | evet | GEREK YOK / statik-yatay gibi | [2859, 1440] | horizontal | 0.803 | 0 | 89 | `01_evoArcadmin_COZUMLEMEV2S17_1925-0009-1-0000-00-1-SON_ADAM__oneocr__phase2_fps6_fastmodels.txt` |
| 2 | evoArcadmin COZUMLEMEV2S17 1988-0375-1-0000-00-1-KONTES MARIZA | evet | GEREK YOK / statik-yatay gibi | [3525, 1769] | horizontal | -0.25 | 12 | 160 | `02_evoArcadmin_COZUMLEMEV2S17_1988-0375-1-0000-00-1-KONTES_MARIZA__oneocr__phase2_fps6_fastmodels.txt` |
| 3 | evoArcadmin COZUMLEMEV2S17 1991-0339-1-0000-01-1-K-2 | evet | EVET - pano mantigi calismis | [1073, 7048] | vertical | -6.0 | 58 | 2671 | `03_evoArcadmin_COZUMLEMEV2S17_1991-0339-1-0000-01-1-K-2__oneocr__phase2_fps6_fastmodels.txt` |
| 4 | evoArcadmin COZUMLEMEV2S17 1991-0377-1-0000-00-1-SİYAH KADİFE ELBİSE | evet | EVET - pano mantigi calismis | [1238, 4218] | vertical | -3.245 | 124 | 782 | `04_evoArcadmin_COZUMLEMEV2S17_1991-0377-1-0000-00-1-SİYAH_KADİFE_ELBİSE__oneocr__phase2_fps6_fastmodels.txt` |
| 5 | evoArcadmin SİNEMA FİLM 1950-2118-1-0000-90-1-GÜN BATISI | evet | GEREK YOK / statik-yatay gibi | [1926, 887] | horizontal | -0.035 | 0 | 30 | `05_evoArcadmin_SİNEMA_FİLM_1950-2118-1-0000-90-1-GÜN_BATISI__oneocr__phase2_fps6_fastmodels.txt` |
| 6 | evoArcadmin SİNEMA FİLM 1990-0325-1-0000-90-1-BABA 3 | evet | EVET - pano mantigi calismis | [530, 6540] | vertical | -5.794 | 0 | 2137 | `06_evoArcadmin_SİNEMA_FİLM_1990-0325-1-0000-90-1-BABA_3__oneocr__phase2_fps6_fastmodels.txt` |
| 7 | evoArcadmin SİNEMA FİLM 2016-1000-1-0000-90-1-ÖFKE (FURY) | evet | EVET - pano mantigi calismis | [514, 5842] | vertical | -5.146 | 87 | 3632 | `07_evoArcadmin_SİNEMA_FİLM_2016-1000-1-0000-90-1-ÖFKE__FURY___oneocr__phase2_fps6_fastmodels.txt` |
| 8 | evoArcadmin SİNEMA FİLM 2017-9031-1-0000-85-1-BEYAZ BALİNA | evet | EVET - pano mantigi calismis | [949, 5744] | vertical | -4.743 | 4 | 1521 | `08_evoArcadmin_SİNEMA_FİLM_2017-9031-1-0000-85-1-BEYAZ_BALİNA__paddle__phase1_fps1_allmodels.txt` |
| 9 | evoArcadmin ÇÖZÜMLEME5 1941-1147-1-0000-50-1-MALTA ŞAHİNİ | evet | GEREK YOK / statik-yatay gibi | [1090, 603] | horizontal | 0.11 | 5 | 463 | `09_evoArcadmin_ÇÖZÜMLEME5_1941-1147-1-0000-50-1-MALTA_ŞAHİNİ__oneocr__phase2_fps6_fastmodels.txt` |
| 10 | evoArcadmin ÇÖZÜMLEME5 1955-1147-1-0000-90-1-KANLI İNTİKAM | evet | GEREK YOK / statik-yatay gibi | [1860, 1077] | horizontal | -0.62 | 2 | 15 | `10_evoArcadmin_ÇÖZÜMLEME5_1955-1147-1-0000-90-1-KANLI_İNTİKAM__NO_RELIABLE_TEXT.txt` |
| 11 | evoArcadmin ÇÖZÜMLEME5 1983-0176-1-0000-90-1-ÇARIKLI MİLYONER | evet | GEREK YOK / statik-yatay gibi | [1199, 801] | mixed_or_static | 0.375 | 0 | 3 | `11_evoArcadmin_ÇÖZÜMLEME5_1983-0176-1-0000-90-1-ÇARIKLI_MİLYONER__NO_RELIABLE_TEXT.txt` |
| 12 | evoArcadmin ÇÖZÜMLEME5 1992-1150-1-0000-50-1-FARELER VE İNSANLAR | evet | EVET - pano mantigi calismis | [517, 5544] | vertical | -4.87 | 7 | 1018 | `12_evoArcadmin_ÇÖZÜMLEME5_1992-1150-1-0000-50-1-FARELER_VE_İNSANLAR__oneocr__phase2_fps6_fastmodels.txt` |
| 13 | evoArcadmin ÇÖZÜMLEME5 2016-1223-1-0000-50-0-KESİŞEN HAYATLAR | evet | EVET - pano mantigi calismis | [547, 4332] | vertical | -3.746 | 5 | 2432 | `13_evoArcadmin_ÇÖZÜMLEME5_2016-1223-1-0000-50-0-KESİŞEN_HAYATLAR__oneocr__phase2_fps6_fastmodels.txt` |
| 14 | evoArcadmin ÇÖZÜMLEME6 1978-1112-1-0000-66-0-MACARLAR | evet | GEREK YOK / statik-yatay gibi | [1464, 1318] | mixed_or_static | 0.351 | 8 | 227 | `14_evoArcadmin_ÇÖZÜMLEME6_1978-1112-1-0000-66-0-MACARLAR__oneocr__phase2_fps6_fastmodels.txt` |
| 15 | evoArcadmin ÇÖZÜMLEME6 2013-1002-1-0000-50-1-NEBRASKA | evet | GEREK YOK / statik-yatay gibi | [857, 484] | vertical | -0.003 | 43 | 1335 | `15_evoArcadmin_ÇÖZÜMLEME6_2013-1002-1-0000-50-1-NEBRASKA__oneocr__phase2_fps6_fastmodels.txt` |
| 16 | evoArcadmin ÇÖZÜMLEME6 2014-1090-1-0000-90-1-FIRTINANIN İÇİNDE | evet | EVET - pano mantigi calismis | [862, 7336] | vertical | -6.354 | 104 | 2284 | `16_evoArcadmin_ÇÖZÜMLEME6_2014-1090-1-0000-90-1-FIRTINANIN_İÇİNDE__oneocr__phase2_fps6_fastmodels.txt` |
| 17 | evoArcadmin ÇÖZÜMLEME6 2024-1208-1-0000-90-1-SON HAVA BÜKÜCÜ | evet | EVET - pano mantigi calismis | [1432, 8561] | vertical | -7.15 | 68 | 3201 | `17_evoArcadmin_ÇÖZÜMLEME6_2024-1208-1-0000-90-1-SON_HAVA_BÜKÜCÜ__oneocr__phase2_fps6_fastmodels.txt` |
| 18 | web client CAG1 2024-0007-0-0070-91-1-MEHMED FETİHLER SULTANI | evet | EVET - pano mantigi calismis | [5305, 19106] | vertical | -16.666 | 707 | 2229 | `18_web_client_CAG1_2024-0007-0-0070-91-1-MEHMED_FETİHLER_SULTANI__oneocr__phase2_fps6_fastmodels.txt` |

## Yorum

- “Pano uretildi mi?” sorusunun cevabi evet: her klipte fiziksel `descroll_canvas.png` var.
- “Kayan yaziyi tek jenerik haline getirdi mi?” sorusunda cevap ikiye ayriliyor: goruntu panosu evet; temiz final metin kismi kismen. Aday metin dosyalari stable OCR gruplarindan uretildi, ama henuz insan onayi/ground truth/dedupe kalite kapisi gecmedi.
- En net kayan/pano basarisi verenler: K-2, SIYAH KADIFE ELBISE, BABA 3, FURY, BEYAZ BALINA, FARELER VE INSANLAR, KESISEN HAYATLAR, FIRTINANIN ICINDE, SON HAVA BUKUCU, MEHMED FETIHLER SULTANI.
- Az metinli veya statik/yatay gorunenler: SON ADAM, KONTES MARIZA, GUN BATISI, KANLI INTIKAM, CARIKLI MILYONER, MALTA SAHINI, MACARLAR, NEBRASKA. Bunlarda frame-temporal OCR daha anlamli; canvas ekstra kazanc vermiyor.
- Canvas OCR sayisi bazi kayan kliplerde dusuk kaldi. Bu, pano uretiminin basarisiz oldugu anlamina tek basina gelmez; uzun panoda font kucuk/kontrast dusuk kaldigi icin OCR-on-canvas ayrica iyilestirme istiyor.
