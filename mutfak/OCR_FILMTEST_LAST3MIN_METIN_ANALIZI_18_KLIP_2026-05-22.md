# OCR Filmtest Son 3 Dakika Metin Analizi - 18 Klip

Bu rapor OCR sayacindan ziyade modelin fiilen okudugu metinleri ve kullanilabilirlik kararini ozetler.
Ground truth yok; kalite yorumu stable tekrar, satir butunlugu, tek-kelime gürültü orani ve motor maliyetine gore yapilmistir.

## Genel Karar

- OneOCR genel olarak en kullanilabilir metni verdi: satir butunlugu iyi, hiz iyi, gürültü Tesseract kadar dagilmiyor.
- Paddle kalite olarak bazi kliplerde OneOCR seviyesine yakin veya iyi; ancak CPU maliyeti cok yuksek. GPU cozulmeden ana hat motoru olmamali.
- Tesseract cok fazla metin yakalasa da cogu zaman satirlari tek kelimelere boluyor. Ana motor degil, yardimci sinyal/gurultu karsilastirma motoru gibi duruyor.
- De-scroll canvas her klipte esit fayda vermedi. Kayan/yoğun jenerikte potansiyel var; fakat canvas OCR ayrica kalite kapisi ve dedupe istiyor.

## Klip Ozet Tablosu

| # | Klip | En kullanilir veri | Neden | Ornek satirlar |
| ---: | --- | --- | --- | --- |
| 1 | evoArcadmin COZUMLEMEV2S17 1925-0009-1-0000-00-1-SON ADAM | oneocr (phase2_fps6_fastmodels) | 59 iyi stable satir, tek-kelime 31.4% | Rarl-Waria Schley, Gerd Weshphal; Gudrun Rabente; Hans Winschel; K.S.Saebich,P.M, Urtel,u.a. |
| 2 | evoArcadmin COZUMLEMEV2S17 1988-0375-1-0000-00-1-KONTES MARIZA | oneocr (phase2_fps6_fastmodels) | 50 iyi stable satir, tek-kelime 32.0% | Dagmar Koller; Kurt Fuemer; Mutluluk saati geldi; Musikalische Bearbeitung |
| 3 | evoArcadmin COZUMLEMEV2S17 1991-0339-1-0000-01-1-K-2 | oneocr (phase2_fps6_fastmodels) | 736 iyi stable satir, tek-kelime 9.7% | Sbenio Carpontor; Location Aooountant; KASHMIR: PAKISTAN andiBRITISH COLUMBIA: CANADA; PAUL BERNSTEIN |
| 4 | evoArcadmin COZUMLEMEV2S17 1991-0377-1-0000-00-1-SİYAH KADİFE ELBİSE | oneocr (phase2_fps6_fastmodels) | 269 iyi stable satir, tek-kelime 3.6% | 2nd Assistant Director; WORLD WIDE INTERNATIONAL TELEVISION; Music Recorded by; The novels of |
| 5 | evoArcadmin SİNEMA FİLM 1950-2118-1-0000-90-1-GÜN BATISI | tesseract (phase1_fps1_allmodels) | 0 iyi stable satir, tek-kelime 0.0% |  |
| 6 | evoArcadmin SİNEMA FİLM 1990-0325-1-0000-90-1-BABA 3 | oneocr (phase2_fps6_fastmodels) | 447 iyi stable satir, tek-kelime 9.1% | production assistant; art department; prop department; chief Ilghting technician |
| 7 | evoArcadmin SİNEMA FİLM 2016-1000-1-0000-90-1-ÖFKE (FURY) | oneocr (phase2_fps6_fastmodels) | 690 iyi stable satir, tek-kelime 6.6% | Crowd 2nd 2nd Assistant Director; Set Production Assistants; Visual Effects Supervisors; CG Supervisor |
| 8 | evoArcadmin SİNEMA FİLM 2017-9031-1-0000-85-1-BEYAZ BALİNA | paddle (phase1_fps1_allmodels) | 169 iyi stable satir, tek-kelime 7.7% | SN. OLCAY KILAVUZ; SN. MURAT KARAMAN; Post Prodüksiyon /Post Production; RAMAZAN MURAT |
| 9 | evoArcadmin ÇÖZÜMLEME5 1941-1147-1-0000-50-1-MALTA ŞAHİNİ | oneocr (phase2_fps6_fastmodels) | 88 iyi stable satir, tek-kelime 7.4% | SYDNEY GREENSTREET; JAMES BURKE; Detective Tom Polbaus. .WARD BOND; MURRAY ALPER |
| 10 | evoArcadmin ÇÖZÜMLEME5 1955-1147-1-0000-90-1-KANLI İNTİKAM | paddle (phase1_fps1_allmodels) | 0 iyi stable satir, tek-kelime 100.0% |  |
| 11 | evoArcadmin ÇÖZÜMLEME5 1983-0176-1-0000-90-1-ÇARIKLI MİLYONER | paddle (phase1_fps1_allmodels) | 0 iyi stable satir, tek-kelime 100.0% |  |
| 12 | evoArcadmin ÇÖZÜMLEME5 1992-1150-1-0000-50-1-FARELER VE İNSANLAR | oneocr (phase2_fps6_fastmodels) | 283 iyi stable satir, tek-kelime 8.4% | PATRICK CASSIDY; First Assistant Director CARA GIALLANZA; Makeup Artist BONITA DeHAVEN; Second Assistant Director MICHELE PANELLI- VENETIS |
| 13 | evoArcadmin ÇÖZÜMLEME5 2016-1223-1-0000-50-0-KESİŞEN HAYATLAR | oneocr (phase2_fps6_fastmodels) | 1821 iyi stable satir, tek-kelime 8.4% | Alen CARSOUX; CINE +; LES FILMS PELLEAS; LES FILMS DU BELIER |
| 14 | evoArcadmin ÇÖZÜMLEME6 1978-1112-1-0000-66-0-MACARLAR | oneocr (phase2_fps6_fastmodels) | 59 iyi stable satir, tek-kelime 11.8% | CSABAVÖLGYI ETA, DOMONKOS SÁNDOR, HÁBETLER; VILLÁNYI TAMÁS, WIND PÁL.; ISTVÁN, UHRIN ZSUZSA, VELEZDY GYÖRGY,; FERENC, HOMONNAY ZOLTÁNNÉ, HURZSÁN JÁNOS, |
| 15 | evoArcadmin ÇÖZÜMLEME6 2013-1002-1-0000-50-1-NEBRASKA | oneocr (phase2_fps6_fastmodels) | 340 iyi stable satir, tek-kelime 9.0% | WRITTEN BY MARK ORTON; ASSISTANT TO MR PAYNE; VISUAL EFFECTS BY; EXECUTIVE VISUAL EFFECTS SUPERVISOR |
| 16 | evoArcadmin ÇÖZÜMLEME6 2014-1090-1-0000-90-1-FIRTINANIN İÇİNDE | oneocr (phase2_fps6_fastmodels) | 560 iyi stable satir, tek-kelime 4.3% | B CAMERA IST ASSISTANT; DIGITAL INTERMEDIATE PRODUCERS; KEY SET COSTUMER; BRIAN TYLER |
| 17 | evoArcadmin ÇÖZÜMLEME6 2024-1208-1-0000-90-1-SON HAVA BÜKÜCÜ | oneocr (phase2_fps6_fastmodels) | 790 iyi stable satir, tek-kelime 4.1% | MICHAEL GILBERT; FILM OFFICE; Digital Model Supervisor; Location Manager |
| 18 | web client CAG1 2024-0007-0-0070-91-1-MEHMED FETİHLER SULTANI | oneocr (phase2_fps6_fastmodels) | 438 iyi stable satir, tek-kelime 21.6% | EYÜP GÖKHAN ÖZEKİN; BERK ÖZEKİN; HALİS CAHİT KURUTLU; SFX TEKNİSYENİ GOKHAN AL |

## Klip Klip Detay

### 1. evoArcadmin COZUMLEMEV2S17 1925-0009-1-0000-00-1-SON ADAM

- En kullanilir veri: **oneocr (phase2_fps6_fastmodels)**
- Karar gerekcesi: 59 iyi stable satir, tek-kelime 31.4%
- Hemen bakilacak ornekler: Rarl-Waria Schley, Gerd Weshphal; Gudrun Rabente; Hans Winschel; K.S.Saebich,P.M, Urtel,u.a.

#### phase1_fps1_allmodels

- frames=180 frame_records=789 stable_groups=121 canvas_records=1 runtime_sec=827.136
- oneocr: frame_records=359, stable=54, iyi_stable=40, tek_kelime%=25.9, mean_conf=0.598
  - Ornek stable satirlar:
    - [11x, conf=0.4535] Rarl-Maria Schley, Gord Deshphal
    - [11x, conf=0.4404] K.S.Saebich,P.M. Urtel,u.a.
    - [9x, conf=0.6694] Güdrün Rabente
    - [9x, conf=0.6023] Hilwa von Boro
    - [9x, conf=0.5011] Frans und Alse Siebert
    - [9x, conf=0.4879] Hans Winschel
    - [8x, conf=0.485] Rober! Herlth
    - [8x, conf=0.4664] AUFNAHMELEITUNG Ridolf Kaey, Maus Hosemann
    - [8x, conf=0.3099] Reimrich Mastker, Peter Nor,
    - [7x, conf=0.7899] DREHBUCH :
- paddle: frame_records=422, stable=67, iyi_stable=39, tek_kelime%=41.8, mean_conf=0.853
  - Ornek stable satirlar:
    - [11x, conf=0.8855] K.S.Saebich.P.M.Urtel, u.a.
    - [10x, conf=0.8908] Karl-Marig Schley, Gerd Pestphal
    - [9x, conf=0.9284] Güdfün Rabente
    - [9x, conf=0.9105] Franz und Hse Sieberk
    - [9x, conf=0.9078] Hans Winschel
    - [9x, conf=0.8912] Hilwa von B3or6
    - [9x, conf=0.7789] Heinrich Hauber, Peter Klorn
    - [8x, conf=0.9062] BREHBUCH :
    - [8x, conf=0.8543] Robert HerCth
    - [7x, conf=0.9215] HANDLUNG UND PERSONEN DHESES FALMES SIND FREI ERFUNDEN
- tesseract: frame_records=8, stable=0, iyi_stable=0, tek_kelime%=0.0, mean_conf=None

#### phase2_fps6_fastmodels

- frames=1080 frame_records=2223 stable_groups=89 canvas_records=0 runtime_sec=472.079
- oneocr: frame_records=2143, stable=86, iyi_stable=59, tek_kelime%=31.4, mean_conf=0.531
  - Ornek stable satirlar:
    - [65x, conf=0.473] Rarl-Waria Schley, Gerd Weshphal
    - [58x, conf=0.6533] Gudrun Rabente
    - [57x, conf=0.494] Hans Winschel
    - [56x, conf=0.4595] K.S.Saebich,P.M, Urtel,u.a.
    - [55x, conf=0.5598] Hilwa von Boro
    - [52x, conf=0.46] AUFNAHMELEITUNG Ridolf Kaey, Maus Hosemann
    - [51x, conf=0.5057] Frans und Alse Siebert
    - [49x, conf=0.2779] Milona vom Eckhardi, Gabine Rlahn
    - [48x, conf=0.2922] Reinrich Mawker, Peter Nome,
    - [46x, conf=0.6785] Der Film würde in den Ateliers der Tsavaria
- tesseract: frame_records=80, stable=3, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.245

#### phase3_fps6_paddle_partial

- frames=1080 frame_records=2504 stable_groups=118 canvas_records=0 runtime_sec=4522.086
- paddle: frame_records=2504, stable=118, iyi_stable=61, tek_kelime%=48.3, mean_conf=0.811
  - Ornek stable satirlar:
    - [64x, conf=0.8894] Karl-Maria Schley, Gerd Pestphal
    - [64x, conf=0.8842] K.S.Saebich.PM. Urtel.u.a.
    - [57x, conf=0.9271] Güdkün Rabente
    - [56x, conf=0.9035] Franz und Hse Sieberk
    - [56x, conf=0.8835] Hilwa von B3or6
    - [45x, conf=0.8829] Der Film wukde in den Ateliers der Bavaria
    - [44x, conf=0.8338] Filmkinst Munchen-Geiselgasteig hergestellt
    - [44x, conf=0.7218] Ursila x Rejbnike Charlome Wimhum
    - [42x, conf=0.7826] Heinrich Hauber, Peter Kom
    - [41x, conf=0.8783] Robert HerCth

### 2. evoArcadmin COZUMLEMEV2S17 1988-0375-1-0000-00-1-KONTES MARIZA

- En kullanilir veri: **oneocr (phase2_fps6_fastmodels)**
- Karar gerekcesi: 50 iyi stable satir, tek-kelime 32.0%
- Hemen bakilacak ornekler: Dagmar Koller; Kurt Fuemer; Mutluluk saati geldi; Musikalische Bearbeitung

#### phase1_fps1_allmodels

- frames=180 frame_records=698 stable_groups=150 canvas_records=55 runtime_sec=783.46
- oneocr: frame_records=213, stable=61, iyi_stable=44, tek_kelime%=27.9, mean_conf=0.892
  - Ornek stable satirlar:
    - [5x, conf=0.985] Dagmar Koller
    - [5x, conf=0.7168] Kurt Fuemer
    - [4x, conf=0.9929] Taşırım seni uzaklara dek
    - [4x, conf=0.991] Musikalische Bearbeitung
    - [4x, conf=0.9887] Mutluluk saati geldi
    - [4x, conf=0.9708] Rene Kollo
    - [4x, conf=0.9614] Fredy Arnold
    - [4x, conf=0.9516] Benno Kusche
    - [4x, conf=0.9341] kjuba Welitsch
    - [4x, conf=0.8889] Brigitta Wehrand
  - Canvas ornekleri:
    - Otto Pischinuerey A
    - Woligang Shoct e
    - se Scnening
    - Evet a
    - Benno Nusa
- paddle: frame_records=234, stable=67, iyi_stable=41, tek_kelime%=38.8, mean_conf=0.964
  - Ornek stable satirlar:
    - [5x, conf=0.991] Dagmar Koller
    - [5x, conf=0.9736] Kurt Huemer
    - [4x, conf=0.9955] Benno Kusche
    - [4x, conf=0.9936] Musikalische Bearbeitung
    - [4x, conf=0.9878] Rene Kollo
    - [4x, conf=0.9862] Mutluluk saati geldi
    - [4x, conf=0.9849] Bert Grund
    - [4x, conf=0.9813] Taşırım seni uzaklara dek
    - [4x, conf=0.977] Fredy Arnold
    - [4x, conf=0.9635] a Welitsch
  - Canvas ornekleri:
    - Ofto Pischirnertue
    - Woligang Ebatt
    - Fritz Bifeanee
    - MuNRul sana'sennclmodor
    - Benno Rusa
- tesseract: frame_records=251, stable=22, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.691

#### phase2_fps6_fastmodels

- frames=1080 frame_records=2440 stable_groups=160 canvas_records=12 runtime_sec=498.442
- oneocr: frame_records=1277, stable=75, iyi_stable=50, tek_kelime%=32.0, mean_conf=0.845
  - Ornek stable satirlar:
    - [27x, conf=0.9871] Dagmar Koller
    - [27x, conf=0.7411] Kurt Fuemer
    - [26x, conf=0.9885] Mutluluk saati geldi
    - [25x, conf=0.9899] Musikalische Bearbeitung
    - [25x, conf=0.9685] Benno Kusche
    - [25x, conf=0.9592] Rene Kollo
    - [25x, conf=0.9155] Antal Fodor
    - [25x, conf=0.9127] kjuba Welitsch
    - [25x, conf=0.8468] Erzsebet Bazy
    - [25x, conf=0.7725] Bert Srund
  - Canvas ornekleri:
    - Kurt Brosskurth
    - Jrma Patkos
    - Olivera IRiliakovic
    - Benno Kusche
    - Ljuba Welitsch
- tesseract: frame_records=1163, stable=85, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.544

#### phase3_fps6_paddle_partial

- frames=None frame_records=None stable_groups=None canvas_records=None runtime_sec=None

### 3. evoArcadmin COZUMLEMEV2S17 1991-0339-1-0000-01-1-K-2

- En kullanilir veri: **oneocr (phase2_fps6_fastmodels)**
- Karar gerekcesi: 736 iyi stable satir, tek-kelime 9.7%
- Hemen bakilacak ornekler: Sbenio Carpontor; Location Aooountant; KASHMIR: PAKISTAN andiBRITISH COLUMBIA: CANADA; PAUL BERNSTEIN

#### phase1_fps1_allmodels

- frames=180 frame_records=7383 stable_groups=1196 canvas_records=336 runtime_sec=1285.298
- oneocr: frame_records=1720, stable=313, iyi_stable=293, tek_kelime%=6.1, mean_conf=0.652
  - Ornek stable satirlar:
    - [14x, conf=0.5004] Sbenio Carpontor
    - [13x, conf=0.4433] Looation Aooountant
    - [9x, conf=0.7085] KASHMIR: PAKISTAN andIBRITISH COLUMBIA, CANADA
    - [9x, conf=0.5247] Carpontor's Holpor
    - [8x, conf=0.4914] Filiodion locationin
    - [7x, conf=0.9847] DOMINIC LESTER
    - [7x, conf=0.9797] PAUL BERNSTEIN
    - [7x, conf=0.9789] PAT MORROW
    - [7x, conf=0.9745] GORDON WISE
    - [7x, conf=0.964] TEDD KUCHERA
- paddle: frame_records=2455, stable=375, iyi_stable=281, tek_kelime%=25.1, mean_conf=0.87
  - Ornek stable satirlar:
    - [11x, conf=0.8618] Lopation Acoduntant
    - [11x, conf=0.8321] Paint Load Hand
    - [11x, conf=0.8173] Assistant Chol
    - [10x, conf=0.7598] Chipontor's Holpor
    - [9x, conf=0.9656] RICK ALLEN
    - [9x, conf=0.929] KASHMIR, PAKISTAN BDDIBRITISH COLUMBIA, CANADA
    - [8x, conf=0.966] NICKO CUMMINS
    - [8x, conf=0.8693] C IS9UTRANS PADILIC INTERNATIONAL PARTNERSHIP
    - [8x, conf=0.7006] SPEX AssistOnI
    - [7x, conf=0.9985] PAUL BERNSTEIN
  - Canvas ornekleri:
    - Pelastan oc
    - SEAR AA
    - A Do
    - A Dop
    - ( Re
- tesseract: frame_records=3208, stable=508, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.506

#### phase2_fps6_fastmodels

- frames=1080 frame_records=29726 stable_groups=2671 canvas_records=58 runtime_sec=676.701
- oneocr: frame_records=10281, stable=815, iyi_stable=736, tek_kelime%=9.7, mean_conf=0.561
  - Ornek stable satirlar:
    - [75x, conf=0.5069] Sbenio Carpontor
    - [64x, conf=0.4752] Location Aooountant
    - [52x, conf=0.7106] KASHMIR: PAKISTAN andiBRITISH COLUMBIA: CANADA
    - [42x, conf=0.9803] PAUL BERNSTEIN
    - [42x, conf=0.9744] PAT MORROW
    - [42x, conf=0.9615] MARK DAVIDSON
    - [42x, conf=0.9548] PAULINE GRIFFITHS
    - [42x, conf=0.944] .JIM LANG
    - [42x, conf=0.9097] HECTOR McKENZIE
    - [42x, conf=0.8855] ABDUL KARIM
- tesseract: frame_records=19445, stable=1856, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.299

### 4. evoArcadmin COZUMLEMEV2S17 1991-0377-1-0000-00-1-SİYAH KADİFE ELBİSE

- En kullanilir veri: **oneocr (phase2_fps6_fastmodels)**
- Karar gerekcesi: 269 iyi stable satir, tek-kelime 3.6%
- Hemen bakilacak ornekler: 2nd Assistant Director; WORLD WIDE INTERNATIONAL TELEVISION; Music Recorded by; The novels of

#### phase1_fps1_allmodels

- frames=180 frame_records=5024 stable_groups=734 canvas_records=376 runtime_sec=1062.573
- oneocr: frame_records=1244, stable=211, iyi_stable=203, tek_kelime%=3.8, mean_conf=0.961
  - Ornek stable satirlar:
    - [15x, conf=0.9787] 2nd Assistant Director
    - [14x, conf=0.9854] WORLD WIDE INTERNATIONAL TELEVISION
    - [11x, conf=0.9648] Music Recorded by
    - [9x, conf=0.992] RAY MARSHALL
    - [9x, conf=0.9763] The novels of
    - [8x, conf=0.9956] & OPTICAL
    - [8x, conf=0.9949] and the Owners and Trustees of
    - [8x, conf=0.9929] MUNICH SYMPHONY
    - [8x, conf=0.9926] DIANNE SHARP
    - [8x, conf=0.9923] LOU COVERLEY
  - Canvas ornekleri:
    - nd at Tyne Tees Studios
    - WORLD WIDE INTERNATIONAL TELEVISION
    - WORLD WIDEOINTERNNIRNAD TELEVISION
    - and atPRODUTetIOStudios
    - or their kind sosegerasep dusing tilming
- paddle: frame_records=1193, stable=193, iyi_stable=185, tek_kelime%=4.1, mean_conf=0.985
  - Ornek stable satirlar:
    - [16x, conf=0.9928] 3rd Assistant Directors
    - [14x, conf=0.9983] WORLD WIDE INTERNATIONAL TELEVISION
    - [14x, conf=0.9924] Music Recorded by
    - [9x, conf=0.993] RAY MARSHALL
    - [9x, conf=0.9813] The novels of
    - [9x, conf=0.968] Parson Weeks JOE GING
    - [8x, conf=0.9992] Accounts Co-ordinator
    - [8x, conf=0.999] NEIL CALDER
    - [8x, conf=0.9989] RANK LABORATORIES
    - [8x, conf=0.9988] HELEN MALLON
  - Canvas ornekleri:
    - Chiefrduetion Kunst
    - An De
    - ChieRraduetiep, Raes
    - Art Debaang
    - Art Deparlm
- tesseract: frame_records=2587, stable=330, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.907

#### phase2_fps6_fastmodels

- frames=1080 frame_records=23438 stable_groups=782 canvas_records=124 runtime_sec=601.853
- oneocr: frame_records=7428, stable=279, iyi_stable=269, tek_kelime%=3.6, mean_conf=0.959
  - Ornek stable satirlar:
    - [91x, conf=0.9754] 2nd Assistant Director
    - [84x, conf=0.9876] WORLD WIDE INTERNATIONAL TELEVISION
    - [61x, conf=0.9769] Music Recorded by
    - [56x, conf=0.979] The novels of
    - [53x, conf=0.9892] RAY MARSHALL
    - [51x, conf=0.9562] CATHERINE COOKSON
    - [50x, conf=0.9869] Executive Producer for World Wide
    - [48x, conf=0.982] NEIL CALDER
    - [48x, conf=0.9778] Boom Operator
    - [48x, conf=0.9777] Wardrobe Assistant
  - Canvas ornekleri:
    - adat ivne Tees Studios
    - Tone ees Studios
    - llmed on locandmtnl w
    - Filmed on locat
    - n wurthuembewdind and Durham
- tesseract: frame_records=16010, stable=503, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.803

### 5. evoArcadmin SİNEMA FİLM 1950-2118-1-0000-90-1-GÜN BATISI

- En kullanilir veri: **tesseract (phase1_fps1_allmodels)**
- Karar gerekcesi: 0 iyi stable satir, tek-kelime 0.0%

#### phase1_fps1_allmodels

- frames=180 frame_records=85 stable_groups=6 canvas_records=0 runtime_sec=420.566
- oneocr: frame_records=30, stable=3, iyi_stable=2, tek_kelime%=33.3, mean_conf=0.684
  - Ornek stable satirlar:
    - [9x, conf=0.9267] The End
    - [9x, conf=0.5862] Le May-Templeton
- paddle: frame_records=30, stable=3, iyi_stable=1, tek_kelime%=66.7, mean_conf=0.968
  - Ornek stable satirlar:
    - [8x, conf=0.9658] The End
- tesseract: frame_records=25, stable=0, iyi_stable=0, tek_kelime%=0.0, mean_conf=None

#### phase2_fps6_fastmodels

- frames=1080 frame_records=411 stable_groups=30 canvas_records=0 runtime_sec=337.111
- oneocr: frame_records=176, stable=4, iyi_stable=3, tek_kelime%=25.0, mean_conf=0.594
  - Ornek stable satirlar:
    - [55x, conf=0.9266] The End
    - [55x, conf=0.6573] Le May Templeton
    - [2x, conf=0.1816] xay empleton
- tesseract: frame_records=235, stable=26, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.373

### 6. evoArcadmin SİNEMA FİLM 1990-0325-1-0000-90-1-BABA 3

- En kullanilir veri: **oneocr (phase2_fps6_fastmodels)**
- Karar gerekcesi: 447 iyi stable satir, tek-kelime 9.1%
- Hemen bakilacak ornekler: production assistant; art department; prop department; chief Ilghting technician

#### phase1_fps1_allmodels

- frames=180 frame_records=14507 stable_groups=1940 canvas_records=195 runtime_sec=1265.434
- oneocr: frame_records=3741, stable=466, iyi_stable=429, tek_kelime%=7.9, mean_conf=0.883
  - Ornek stable satirlar:
    - [21x, conf=0.8311] second assistant director
    - [20x, conf=0.6881] production assistant
    - [16x, conf=0.9232] mask #1
    - [16x, conf=0.8505] prop department
    - [16x, conf=0.7921] art department
    - [16x, conf=0.6536] chief lighting technician
    - [14x, conf=0.8619] dlalogue coach
    - [11x, conf=0.8058] first assistant photographer
    - [9x, conf=0.9878] ANGELO SANTUCCI
    - [9x, conf=0.9671] STEPHANIE ZIEMER
  - Canvas ornekleri:
    - EGLI SCHIRVI
    - FRANCO E GH
    - EGLI SCHIRVI
    - FRANCO E FIANMARL
    - EA BEGLI SCHIAV
- paddle: frame_records=3879, stable=526, iyi_stable=433, tek_kelime%=17.7, mean_conf=0.971
  - Ornek stable satirlar:
    - [18x, conf=0.9599] second assistant director
    - [16x, conf=0.9698] prop depariment
    - [16x, conf=0.9627] mask #1
    - [16x, conf=0.9349] art department
    - [16x, conf=0.9134] chief lighling techniclan
    - [14x, conf=0.9747] dialogue coach
    - [14x, conf=0.9519] production assistants
    - [10x, conf=0.8932] feamster captain
    - [9x, conf=0.9936] JEANNE SAVARINO
    - [9x, conf=0.9845] INGRID PRICE
  - Canvas ornekleri:
    - OR EXHIBITION MAY RESULT IN CIVIL LIABILITY AND
    - CRIMINAL PROSECUTION
    - THIS MOTION PIIUIRE IS PROTECTED
    - FRANCO E GIR
    - DEGLI SCHIAVI
- tesseract: frame_records=6887, stable=948, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.701

#### phase2_fps6_fastmodels

- frames=1080 frame_records=63760 stable_groups=2137 canvas_records=0 runtime_sec=669.889
- oneocr: frame_records=22366, stable=492, iyi_stable=447, tek_kelime%=9.1, mean_conf=0.868
  - Ornek stable satirlar:
    - [130x, conf=0.7389] production assistant
    - [98x, conf=0.7954] art department
    - [97x, conf=0.8775] prop department
    - [97x, conf=0.6494] chief Ilghting technician
    - [95x, conf=0.9225] mask #1
    - [91x, conf=0.818] second assistant director
    - [80x, conf=0.8723] dlalogue coach
    - [52x, conf=0.66] leamster captaln
    - [50x, conf=0.9705] swing gang
    - [50x, conf=0.9316] swing gang supervisor
- tesseract: frame_records=41394, stable=1645, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.585

### 7. evoArcadmin SİNEMA FİLM 2016-1000-1-0000-90-1-ÖFKE (FURY)

- En kullanilir veri: **oneocr (phase2_fps6_fastmodels)**
- Karar gerekcesi: 690 iyi stable satir, tek-kelime 6.6%
- Hemen bakilacak ornekler: Crowd 2nd 2nd Assistant Director; Set Production Assistants; Visual Effects Supervisors; CG Supervisor

#### phase1_fps1_allmodels

- frames=180 frame_records=23124 stable_groups=2697 canvas_records=1138 runtime_sec=1811.901
- oneocr: frame_records=4875, stable=595, iyi_stable=558, tek_kelime%=6.1, mean_conf=0.94
  - Ornek stable satirlar:
    - [38x, conf=0.951] Crowd 2nd 2nd Assistant Director
    - [28x, conf=0.9215] Visual Effects Executive Producer
    - [27x, conf=0.8857] Set Production Assistants
    - [27x, conf=0.6604] By arrangemant with Wastwood Music Group
    - [26x, conf=0.6033] Courtasy of Fortune Records
    - [23x, conf=0.9476] 3rd Assistant Director
    - [21x, conf=0.9108] CG Supervisor
    - [18x, conf=0.9148] US Production Insurance
    - [17x, conf=0.7496] Courtasy of EVH Arts
    - [16x, conf=0.9098] Unit Location Manager
  - Canvas ornekleri:
    - IN CIVIL LABIUEELNP SHGINL PROSECUTION.
    - THIS MOTION PICTURE
    - OF THE UNITE
    - AFOARYL AUTHORIZED
    - THE UNITE RE
- paddle: frame_records=5190, stable=590, iyi_stable=545, tek_kelime%=7.6, mean_conf=0.987
  - Ornek stable satirlar:
    - [42x, conf=0.9923] Crowd 2nd 2nd Assistant Director
    - [34x, conf=0.9942] Visual Effects Supervisor
    - [27x, conf=0.9939] Set Production Assistants
    - [26x, conf=0.9476] By arrangement with Westwood Music Group
    - [26x, conf=0.9318] Courtesy of Fortune Records
    - [23x, conf=0.9834] Supervising Carpenter
    - [21x, conf=0.9988] CG Supervisor
    - [20x, conf=0.992] Crowd 3rd Assistant Directors
    - [18x, conf=0.9918] Background Actors Provided By
    - [18x, conf=0.986] UK Production Insurance
  - Canvas ornekleri:
    - IN CIVIL LIABIL
    - ONS OF THE LAWS
    - OF THE UNIT
    - ARY U
    - THIS MOTION PICTU
- tesseract: frame_records=13059, stable=1512, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.619

#### phase2_fps6_fastmodels

- frames=1080 frame_records=106841 stable_groups=3632 canvas_records=87 runtime_sec=1016.646
- oneocr: frame_records=29209, stable=740, iyi_stable=690, tek_kelime%=6.6, mean_conf=0.924
  - Ornek stable satirlar:
    - [220x, conf=0.9383] Crowd 2nd 2nd Assistant Director
    - [166x, conf=0.8942] Set Production Assistants
    - [134x, conf=0.8737] Visual Effects Supervisors
    - [133x, conf=0.9463] CG Supervisor
    - [130x, conf=0.6111] Courtesy of Fortune Records
    - [108x, conf=0.9536] 2nd Unit 2nd Assistant Director
    - [107x, conf=0.6865] Writen ond Parformed by Eric V. Hachikian
    - [106x, conf=0.7474] Courtasy of EVH Arts
    - [105x, conf=0.9013] US Production Insurance
    - [99x, conf=0.6599] By arrangament with Wastwood Music Group
- tesseract: frame_records=77632, stable=2892, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.503

### 8. evoArcadmin SİNEMA FİLM 2017-9031-1-0000-85-1-BEYAZ BALİNA

- En kullanilir veri: **paddle (phase1_fps1_allmodels)**
- Karar gerekcesi: 169 iyi stable satir, tek-kelime 7.7%
- Hemen bakilacak ornekler: SN. OLCAY KILAVUZ; SN. MURAT KARAMAN; Post Prodüksiyon /Post Production; RAMAZAN MURAT

#### phase1_fps1_allmodels

- frames=180 frame_records=7174 stable_groups=967 canvas_records=127 runtime_sec=1635.036
- oneocr: frame_records=1387, stable=167, iyi_stable=155, tek_kelime%=7.2, mean_conf=0.946
  - Ornek stable satirlar:
    - [16x, conf=0.9697] ILGAZ BELEDİYESİ
    - [9x, conf=0.9849] SN. EMİNE TAŞPINAR
    - [9x, conf=0.9844] ŞİLE SAKİNLERİ
    - [9x, conf=0.9822] RAMAZAN MURAT
    - [9x, conf=0.9815] FİLM SOKAĞI
    - [9x, conf=0.981] MÜNEVVER GÜNEŞ SAYIN
    - [9x, conf=0.9805] DCP Stüdyo Süpervizörü / DCP Studio Supervisor M. MURAT ÖZER
    - [9x, conf=0.9776] SN. FEVZİ YAMANKALE
    - [9x, conf=0.9774] Set Malzemeleri / Set Equipment SET İSTANBUL
    - [9x, conf=0.9774] Post Prodüksiyon / Post Production
  - Canvas ornekleri:
    - bu film
    - KOLTOR VE TURE EARANLGI
    - katkıERK Ezianmıştır
    - …当氣為4顯卡凝草※ 娘
    - 税9编融叫种种常磁縣 囉埘電
- paddle: frame_records=1404, stable=183, iyi_stable=169, tek_kelime%=7.7, mean_conf=0.958
  - Ornek stable satirlar:
    - [9x, conf=0.9896] SN. OLCAY KILAVUZ
    - [9x, conf=0.989] SN. MURAT KARAMAN
    - [9x, conf=0.9873] Post Prodüksiyon /Post Production
    - [9x, conf=0.9872] RAMAZAN MURAT
    - [9x, conf=0.9845] HAKAN HAKSUN
    - [9x, conf=0.9844] SN. ÖMER AHUNBAY
    - [9x, conf=0.9814] SN. HAKAN KASIRGA
    - [9x, conf=0.9802] CENK ERDOĞAN
    - [9x, conf=0.9798] SN. MUSTAFA ŞAFAK
    - [9x, conf=0.9783] Senarist / Written by
  - Canvas ornekleri:
    - bu film
    - KÜLTÜR VE TURIZM BAKANLIĞI
    - SOMuAp SaRo
    - U SOR TIDISORDESIEs
    - Sen Kaizemeieryseabgupna: gpnoanan
- tesseract: frame_records=4383, stable=617, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.583

#### phase2_fps6_fastmodels

- frames=1080 frame_records=33333 stable_groups=1521 canvas_records=4 runtime_sec=732.153
- oneocr: frame_records=8301, stable=174, iyi_stable=158, tek_kelime%=9.2, mean_conf=0.92
  - Ornek stable satirlar:
    - [101x, conf=0.9683] SİLE BELEDİYESİ
    - [51x, conf=0.983] Kurgu / Editor
    - [51x, conf=0.9815] TEŞEKKÜRLER / Thanks to
    - [51x, conf=0.9802] ROL MEDYA
    - [51x, conf=0.9766] Set Fotografları / Still Photographers KADİR SÜREN
    - [51x, conf=0.9764] ŞİLE SAKİNLERİ
    - [51x, conf=0.9758] SN. MESUT CEM ERKUL
    - [51x, conf=0.9757] SN AZiz ALi
    - [51x, conf=0.9755] SN. OMER ONAY
    - [51x, conf=0.9747] SN. EMİNE TAŞPINAR
  - Canvas ornekleri:
    - bu lilm
    - LTÜR VE TURIZM BAKAR
- tesseract: frame_records=25032, stable=1347, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.464

### 9. evoArcadmin ÇÖZÜMLEME5 1941-1147-1-0000-50-1-MALTA ŞAHİNİ

- En kullanilir veri: **oneocr (phase2_fps6_fastmodels)**
- Karar gerekcesi: 88 iyi stable satir, tek-kelime 7.4%
- Hemen bakilacak ornekler: SYDNEY GREENSTREET; JAMES BURKE; Detective Tom Polbaus. .WARD BOND; MURRAY ALPER

#### phase1_fps1_allmodels

- frames=180 frame_records=2590 stable_groups=262 canvas_records=18 runtime_sec=587.141
- oneocr: frame_records=571, stable=66, iyi_stable=63, tek_kelime%=4.5, mean_conf=0.961
  - Ornek stable satirlar:
    - [17x, conf=0.9934] JAMES BURKE
    - [17x, conf=0.9894] JOHN HAMILTON
    - [17x, conf=0.9881] MURRAY ALPER
    - [17x, conf=0.9772] Kasper Gutman
    - [17x, conf=0.9371] Detective Tom Polbaus. .WARD BOND
    - [17x, conf=0.9359] SYDNEY GREENSTREET
    - [17x, conf=0.8954] Miles Archer ,
    - [16x, conf=0.9933] THE PLAYERS
    - [16x, conf=0.9392] JEROME COWAN
    - [16x, conf=0.8592] Frank Richman
  - Canvas ornekleri:
    - THE PLAYERS
    - eggil STon Rolbi WARD BOND
    - Joel Cdito
    - Guzel lysZedk
    - Şu Gyaaheykileıh ıdanzitu t lönlefın
- paddle: frame_records=535, stable=72, iyi_stable=67, tek_kelime%=5.6, mean_conf=0.966
  - Ornek stable satirlar:
    - [18x, conf=0.9683] JAMES BURKE
    - [17x, conf=0.9947] Kasper Gutman
    - [17x, conf=0.9895] SYDNEY GREENSTREET
    - [17x, conf=0.9746] Detective Tom Polbaus. .WARD BOND
    - [17x, conf=0.9632] Wilmer Cook . . . ELISHA COOK, Jr.
    - [17x, conf=0.9449] Miles Archer : JEROME COWAN
    - [16x, conf=0.9967] THE PLAYERS
    - [16x, conf=0.9925] JOHN HAMILTON
    - [15x, conf=0.9916] Samuel Spade
    - [15x, conf=0.9885] BARTON MACLANE
  - Canvas ornekleri:
    - Belki bilryorum.eni gonderd ko „onra.
- tesseract: frame_records=1484, stable=124, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.748

#### phase2_fps6_fastmodels

- frames=1080 frame_records=12670 stable_groups=463 canvas_records=5 runtime_sec=421.202
- oneocr: frame_records=3440, stable=95, iyi_stable=88, tek_kelime%=7.4, mean_conf=0.887
  - Ornek stable satirlar:
    - [105x, conf=0.9368] SYDNEY GREENSTREET
    - [104x, conf=0.9815] JAMES BURKE
    - [104x, conf=0.9294] Detective Tom Polbaus. .WARD BOND
    - [102x, conf=0.9781] MURRAY ALPER
    - [102x, conf=0.975] Kasper Gutman
    - [101x, conf=0.8499] Frank Richman
    - [98x, conf=0.9846] JOHN HAMILTON
    - [98x, conf=0.9827] THE PLAYERS
    - [98x, conf=0.9792] Wilmer Cook
    - [98x, conf=0.9723] ELISHA COOK, Jr.
  - Canvas ornekleri:
    - A THE PLAYERS
    - FolbaksWARD BEND:
    - Belki bi yorum. Seni gondrhen sonra,
- tesseract: frame_records=9230, stable=368, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.567

### 10. evoArcadmin ÇÖZÜMLEME5 1955-1147-1-0000-90-1-KANLI İNTİKAM

- En kullanilir veri: **paddle (phase1_fps1_allmodels)**
- Karar gerekcesi: 0 iyi stable satir, tek-kelime 100.0%

#### phase1_fps1_allmodels

- frames=180 frame_records=67 stable_groups=10 canvas_records=5 runtime_sec=403.906
- oneocr: frame_records=20, stable=5, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.792
- paddle: frame_records=22, stable=4, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.954
- tesseract: frame_records=25, stable=1, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.32

#### phase2_fps6_fastmodels

- frames=1080 frame_records=300 stable_groups=15 canvas_records=2 runtime_sec=351.715
- oneocr: frame_records=123, stable=8, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.785
  - Canvas ornekleri:
    - Pararouni el
- tesseract: frame_records=177, stable=7, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.308

### 11. evoArcadmin ÇÖZÜMLEME5 1983-0176-1-0000-90-1-ÇARIKLI MİLYONER

- En kullanilir veri: **paddle (phase1_fps1_allmodels)**
- Karar gerekcesi: 0 iyi stable satir, tek-kelime 100.0%

#### phase1_fps1_allmodels

- frames=180 frame_records=32 stable_groups=3 canvas_records=0 runtime_sec=425.681
- oneocr: frame_records=11, stable=1, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.996
- paddle: frame_records=7, stable=1, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.999
- tesseract: frame_records=14, stable=1, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.96

#### phase2_fps6_fastmodels

- frames=1080 frame_records=106 stable_groups=3 canvas_records=0 runtime_sec=327.12
- oneocr: frame_records=52, stable=1, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.996
- tesseract: frame_records=54, stable=2, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.702

### 12. evoArcadmin ÇÖZÜMLEME5 1992-1150-1-0000-50-1-FARELER VE İNSANLAR

- En kullanilir veri: **oneocr (phase2_fps6_fastmodels)**
- Karar gerekcesi: 283 iyi stable satir, tek-kelime 8.4%
- Hemen bakilacak ornekler: PATRICK CASSIDY; First Assistant Director CARA GIALLANZA; Makeup Artist BONITA DeHAVEN; Second Assistant Director MICHELE PANELLI- VENETIS

#### phase1_fps1_allmodels

- frames=180 frame_records=9993 stable_groups=1093 canvas_records=786 runtime_sec=1165.148
- oneocr: frame_records=1864, stable=249, iyi_stable=227, tek_kelime%=8.0, mean_conf=0.974
  - Ornek stable satirlar:
    - [10x, conf=0.9916] CHRISTOPHER REDDISH
    - [10x, conf=0.99] Production Sound Mixer DAVID BROWNLOW
    - [10x, conf=0.9899] Assistant Editor NOREEN EVANS
    - [10x, conf=0.9893] Best Boy Grip WILLIAM MANN
    - [10x, conf=0.9893] CHERYL T. SMITH
    - [10x, conf=0.9884] PATRICK CASSIDY
    - [10x, conf=0.9874] Makeup Artist BONITA DeHAVEN
    - [10x, conf=0.9871] Set Designer
    - [10x, conf=0.9831] BILL PHILLIPS
    - [10x, conf=0.9821] First Assistant Director CARA GIALLANZA
  - Canvas ornekleri:
    - Metro goldwyn Mayer
    - MAY RESULT IN
    - ESDER THE LAV
    - THIS MOTION PIC
    - IS MOTION PICTURE N TER
- paddle: frame_records=2271, stable=290, iyi_stable=257, tek_kelime%=11.0, mean_conf=0.987
  - Ornek stable satirlar:
    - [14x, conf=0.9946] First Assistant Editor
    - [10x, conf=0.9997] Set Designer
    - [10x, conf=0.9994] DAN MALTESE
    - [10x, conf=0.9987] Assistant Art Director
    - [10x, conf=0.9982] CHRISTOPHER REDDISH
    - [10x, conf=0.9977] WILLIAM MANN
    - [10x, conf=0.9975] DAVID BROWNLOW
    - [10x, conf=0.9961] Location Manager
    - [10x, conf=0.996] PATRICK CASSIDY
    - [10x, conf=0.9952] KAREN SCHULZ
  - Canvas ornekleri:
    - MAY RESULT IN CIVILAIABILITX AND CRIMINAL PROSECUTION
    - THIS MOTION PI
    - CNDER THE LAWS
    - TROFTHE UNIT
    - THIS MO TION PIC
- tesseract: frame_records=5858, stable=554, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.882

#### phase2_fps6_fastmodels

- frames=1080 frame_records=46163 stable_groups=1018 canvas_records=7 runtime_sec=620.755
- oneocr: frame_records=11209, stable=311, iyi_stable=283, tek_kelime%=8.4, mean_conf=0.965
  - Ornek stable satirlar:
    - [57x, conf=0.9881] PATRICK CASSIDY
    - [57x, conf=0.9815] First Assistant Director CARA GIALLANZA
    - [57x, conf=0.977] Makeup Artist BONITA DeHAVEN
    - [57x, conf=0.9287] Second Assistant Director MICHELE PANELLI- VENETIS
    - [56x, conf=0.9925] PACKY LENNON
    - [56x, conf=0.9901] JOYCE ANNE GILSTRAP
    - [56x, conf=0.9891] Key Hair Stylist FRIDA ARADOTTIR
    - [56x, conf=0.989] CHARLES SMITH
    - [56x, conf=0.9877] Assistant Makeup Artist ANN PALA
    - [56x, conf=0.9866] CHARLES CROUGHWELL
- tesseract: frame_records=34954, stable=707, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.781

### 13. evoArcadmin ÇÖZÜMLEME5 2016-1223-1-0000-50-0-KESİŞEN HAYATLAR

- En kullanilir veri: **oneocr (phase2_fps6_fastmodels)**
- Karar gerekcesi: 1821 iyi stable satir, tek-kelime 8.4%
- Hemen bakilacak ornekler: Alen CARSOUX; CINE +; LES FILMS PELLEAS; LES FILMS DU BELIER

#### phase1_fps1_allmodels

- frames=180 frame_records=7424 stable_groups=1029 canvas_records=194 runtime_sec=1157.622
- oneocr: frame_records=3449, stable=540, iyi_stable=485, tek_kelime%=10.2, mean_conf=0.519
  - Ornek stable satirlar:
    - [8x, conf=0.952] FRAKAS PRODUCTIONS
    - [8x, conf=0.9162] MARS FILMS
    - [8x, conf=0.908] LES FILMS PELLEAS
    - [8x, conf=0.8929] LES FILMS DU BELIER
    - [8x, conf=0.8693] CASA KAFKA PICTURES MOVIE TAX SHELTER EMPOWERED BY BELFIUS
    - [8x, conf=0.865] LA BANQUE POSTALE IMAGE 9
    - [8x, conf=0.853] CASA KAFKA PICTURES
    - [8x, conf=0.8429] CNS PRODUCTIONS
    - [8x, conf=0.8308] FRANCE TELEVISIONS
    - [8x, conf=0.8198] EZEKIEL FILM PROOUCTION
  - Canvas ornekleri:
    - * ile: France NC
    - AACNA-TAYCINE Belfiu
    - CANAL+ TAOCINE +
    - TA Belfit
    - CANAL+ SINE + Beltius
- paddle: frame_records=3068, stable=432, iyi_stable=328, tek_kelime%=23.8, mean_conf=0.863
  - Ornek stable satirlar:
    - [9x, conf=0.9598] MARS FILMS
    - [8x, conf=0.9936] FRAKAS PRODUCTIONS
    - [8x, conf=0.9884] CNS PRODUCTIONS
    - [8x, conf=0.973] FILMS DISTRIBUTION
    - [8x, conf=0.9648] FRANCE TÉLÉVISIONS
    - [8x, conf=0.9616] CASA KAFKA PICTURES
    - [8x, conf=0.9563] LA BRIGADE DU TITRE
    - [8x, conf=0.9529] FRAKAS PRODUCTIONS
    - [8x, conf=0.9518] LES FILMS PELLEAS
    - [8x, conf=0.9517] RTBF(TELEVISON BELGE)
  - Canvas ornekleri:
    - KAS QOILLEVERE
    - I REGION
    - Érie Nahot, Carn
    - BNPAONE BENAL
    - COPAONE BENEA
- tesseract: frame_records=907, stable=57, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.548

#### phase2_fps6_fastmodels

- frames=1080 frame_records=25691 stable_groups=2432 canvas_records=5 runtime_sec=678.363
- oneocr: frame_records=20645, stable=1988, iyi_stable=1821, tek_kelime%=8.4, mean_conf=0.423
  - Ornek stable satirlar:
    - [50x, conf=0.4418] Alen CARSOUX
    - [48x, conf=0.9815] CINE +
    - [48x, conf=0.9068] LES FILMS PELLEAS
    - [48x, conf=0.8749] LES FILMS DU BELIER
    - [48x, conf=0.8688] CASA KAFKA PICTURES MOVIE TAX SHELTER EMPOWERED BY BELFIUS
    - [48x, conf=0.8588] LA BANQUE POSTALE IMAGE 9
    - [48x, conf=0.8153] Emilie LE TROADEC
    - [48x, conf=0.7521] CNS PRODUCTIONS
    - [48x, conf=0.722] Antenis CORREIA
    - [48x, conf=0.6131] DI. SCHAIDA VARNOUS, Chantal MONEAT
  - Canvas ornekleri:
    - e ai lledcFrance
    - CANALE CINE
- tesseract: frame_records=5046, stable=444, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.32

### 14. evoArcadmin ÇÖZÜMLEME6 1978-1112-1-0000-66-0-MACARLAR

- En kullanilir veri: **oneocr (phase2_fps6_fastmodels)**
- Karar gerekcesi: 59 iyi stable satir, tek-kelime 11.8%
- Hemen bakilacak ornekler: CSABAVÖLGYI ETA, DOMONKOS SÁNDOR, HÁBETLER; VILLÁNYI TAMÁS, WIND PÁL.; ISTVÁN, UHRIN ZSUZSA, VELEZDY GYÖRGY,; FERENC, HOMONNAY ZOLTÁNNÉ, HURZSÁN JÁNOS,

#### phase1_fps1_allmodels

- frames=180 frame_records=2286 stable_groups=267 canvas_records=18 runtime_sec=1177.391
- oneocr: frame_records=447, stable=57, iyi_stable=53, tek_kelime%=5.3, mean_conf=0.944
  - Ornek stable satirlar:
    - [13x, conf=0.9853] CSABAVÖLGYI ETA, DOMONKOS SÁNDOR, HÁBETLER
    - [13x, conf=0.9808] IVÁNYI KLÁRI, KERTÉSZ LÁSZLÓ, LITTNER IMRE,
    - [13x, conf=0.9796] SIMON LÁSZLÓ, SZALONTAY ÁRPÁDNÉ, TAKÁCS
    - [13x, conf=0.9721] FERENC, HOMONNAY ZOLTÁNNÉ, HURZSÁN JÁNOS,
    - [13x, conf=0.9269] VILLÁNYI TAMÁS, WIND PÁL.
    - [12x, conf=0.9774] ISTVÁN, UHRIN ZSUZSA, VELEZDY GYÖRGY,
    - [12x, conf=0.9624] MAGYAR GYULÁNÉ, NYAKAS ISTVÁN, P. NAGY JÁNOS,
    - [10x, conf=0.9914] Készült a MAFILM műtermeiben és a
    - [10x, conf=0.9875] Szines technika: BOROS MAGDA
    - [10x, conf=0.9833] Magyarországon forgalomba hozza a MOKÉP
  - Canvas ornekleri:
    - CSABAVÖLGYI EFN DOMONKEM
    - FERENE, HOMAGARROHIN
    - VILLANYI TAMSraMangAUJHELYI JANOS
- paddle: frame_records=454, stable=58, iyi_stable=48, tek_kelime%=15.5, mean_conf=0.975
  - Ornek stable satirlar:
    - [13x, conf=0.9945] VILLÁNYI TAMÁS, WIND PÁL.
    - [13x, conf=0.994] CSABAVÖLGYI ETA, DOMONKOS SÁNDOR, HÁBETLER
    - [13x, conf=0.993] SIMON LÁSZLÓ, SZALONTAY ÁRPÁDNÉ, TAKÁCS
    - [13x, conf=0.9925] IVÁNYI KLÁRI, KERTÉSZ LÁSZLÓ, LITTNER IMRE,
    - [13x, conf=0.9921] FERENC, HOMONNAY ZOLTÁNNÉ, HURZSÁN JÁNOS,
    - [12x, conf=0.992] ISTVÁN, UHRIN ZSUZSA, VELEZDY GYÖRGY,
    - [12x, conf=0.982] MAGYAR GYULÁNÉ, NYAKAS ISTVÁN, P. NAGY JÁNOS,
    - [10x, conf=0.9967] Magyarországon forgalomba hozza a MOKÉP
    - [10x, conf=0.9943] Szines technika: BOROS MAGDA
    - [10x, conf=0.9802] MAGYAR FILMLABORATÓRIUMBAN
  - Canvas ornekleri:
    - SRERY EDEYLO CRCIRNTALAURPADSUSZTAEMRTERZBA/1977
    - VILLANYI TAMASPaMINRgPAUJHELYI JANOS
- tesseract: frame_records=1385, stable=152, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.844

#### phase2_fps6_fastmodels

- frames=1080 frame_records=10954 stable_groups=227 canvas_records=8 runtime_sec=682.441
- oneocr: frame_records=2654, stable=68, iyi_stable=59, tek_kelime%=11.8, mean_conf=0.911
  - Ornek stable satirlar:
    - [77x, conf=0.9856] CSABAVÖLGYI ETA, DOMONKOS SÁNDOR, HÁBETLER
    - [77x, conf=0.9329] VILLÁNYI TAMÁS, WIND PÁL.
    - [76x, conf=0.968] ISTVÁN, UHRIN ZSUZSA, VELEZDY GYÖRGY,
    - [76x, conf=0.9662] FERENC, HOMONNAY ZOLTÁNNÉ, HURZSÁN JÁNOS,
    - [75x, conf=0.9817] IVÁNYI KLÁRI, KERTÉSZ LÁSZLÓ, LITTNER IMRE,
    - [75x, conf=0.9807] SIMON LÁSZLÓ, SZALONTAY ÁRPÁDNÉ, TAKÁCS
    - [75x, conf=0.957] MAGYAR GYULÁNÉ, NYAKAS ISTVÁN, P. NAGY JÁNOS,
    - [62x, conf=0.9901] Készült a MAFILM műtermeiben és a
    - [62x, conf=0.9792] Magyarországon forgalomba hozza a MOKÉP
    - [62x, conf=0.9392] MAGYAR FILMLABORATÓRIUMBAN
  - Canvas ornekleri:
    - KERY EDLT.JURGEN KLAUSS: PUSZTAL PETER
    - CSABAVOLGYI ETA DOMONKOS SÁNDOR, HÁBETLER
    - IVAMMA YARI, RHRISABANTORTONERANRE AJOS
    - VILLANYI TAMASPaMANRJAUJHELYI JANOS
    - Remdeőo: HÁUBRIGZÖRTÁN
- tesseract: frame_records=8300, stable=159, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.832

### 15. evoArcadmin ÇÖZÜMLEME6 2013-1002-1-0000-50-1-NEBRASKA

- En kullanilir veri: **oneocr (phase2_fps6_fastmodels)**
- Karar gerekcesi: 340 iyi stable satir, tek-kelime 9.0%
- Hemen bakilacak ornekler: WRITTEN BY MARK ORTON; ASSISTANT TO MR PAYNE; VISUAL EFFECTS BY; EXECUTIVE VISUAL EFFECTS SUPERVISOR

#### phase1_fps1_allmodels

- frames=180 frame_records=10112 stable_groups=1611 canvas_records=137 runtime_sec=1686.136
- oneocr: frame_records=1971, stable=375, iyi_stable=339, tek_kelime%=9.1, mean_conf=0.98
  - Ornek stable satirlar:
    - [18x, conf=0.9867] ASSISTANT TO MR. PAYNE
    - [15x, conf=0.9905] WRITTEN BY MARK ORTON
    - [11x, conf=0.9911] WRITTEN & PERFORMED BY MARK ORTON
    - [11x, conf=0.9893] COURTESY OF CAMP WATERTOWN MUSIC
    - [10x, conf=0.9928] WRITTEN BY MARK ORTON
    - [10x, conf=0.992] SOUND EDITORIAL
    - [10x, conf=0.9916] MUSIC SCORE RECORDED BY
    - [10x, conf=0.9915] WRITTEN BY MARK ORTON
    - [10x, conf=0.9911] PERFORMED BY TIN HAT TRIO
    - [10x, conf=0.9908] PERFORMED BY MARK ORTON AND CARLA KIHLSTEDT
  - Canvas ornekleri:
    - 'KISS THAT MEMORY GOODBYE"
    - "MAGNA CARTA"
    - WRITTEN BY DAVE ERIC SMITH & LARRY WAYNE PENNY
    - LLY FROM THE MOTION PICTURE SWEET LAND)
    - PERFORMED BY LARRY WAYNE PENN
- paddle: frame_records=1963, stable=372, iyi_stable=333, tek_kelime%=10.2, mean_conf=0.989
  - Ornek stable satirlar:
    - [18x, conf=0.9924] ASSISTANT TO MR. PAYNE
    - [15x, conf=0.9942] WRITTEN BY MARK ORTON
    - [11x, conf=0.9928] COURTESY OF CAMP WATERTOWN MUSIC
    - [11x, conf=0.9874] WRITTEN & PERFORMED BY MARK ORTON
    - [10x, conf=0.9991] COURTESY OF CAMP WATERTOWN MUSIC
    - [10x, conf=0.9988] SOUND EDITORIAL
    - [10x, conf=0.9986] WRITTEN BY MARK ORTON
    - [10x, conf=0.9975] PERFORMED BY TIN HAT TRIO
    - [10x, conf=0.9947] EXECUTIVE VISUAL EFFECTS SUPERVISOR
    - [10x, conf=0.9939] SECOND ASSISTANT ACCOUNTANT
  - Canvas ornekleri:
    - 'KISS THAT MEMORY GOODBYE'
    - MAGNA CARTA
    - WRITTEN BY DAVE ERIC SMITH & LARRY WAYNE PENN
    - LY FROM THE MOTION PICTURE SWEET LAND
    - PERFORMED BY LARRY WAYNE PENN
- tesseract: frame_records=6178, stable=864, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.825

#### phase2_fps6_fastmodels

- frames=1080 frame_records=49421 stable_groups=1335 canvas_records=43 runtime_sec=814.053
- oneocr: frame_records=12024, stable=376, iyi_stable=340, tek_kelime%=9.0, mean_conf=0.978
  - Ornek stable satirlar:
    - [91x, conf=0.9905] WRITTEN BY MARK ORTON
    - [74x, conf=0.9859] ASSISTANT TO MR PAYNE
    - [66x, conf=0.9845] VISUAL EFFECTS BY
    - [66x, conf=0.9788] EXECUTIVE VISUAL EFFECTS SUPERVISOR
    - [64x, conf=0.9912] SOUND EDITORIAL
    - [64x, conf=0.983] MUSIC SCORE RECORDED AT
    - [63x, conf=0.9849] MUSIC SCORE MIXED BY
    - [62x, conf=0.9901] COURTESY OF CAMP WATERTOWN MUSIC
    - [62x, conf=0.9889] SECOND ASSISTANT ACCOUNTANT
    - [61x, conf=0.985] COURTESY OF CAMP WATERTOWN MUSIC
  - Canvas ornekleri:
    - "KISS THAT MEM
    - THE PRODJCERS THANK:
    - DRUMS FOR VICTORY
    - WRITTORIGYDAAYR EROS IT OTARRFIDAHE BPN
    - LAURIE RICHAROSN
- tesseract: frame_records=37397, stable=959, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.779

### 16. evoArcadmin ÇÖZÜMLEME6 2014-1090-1-0000-90-1-FIRTINANIN İÇİNDE

- En kullanilir veri: **oneocr (phase2_fps6_fastmodels)**
- Karar gerekcesi: 560 iyi stable satir, tek-kelime 4.3%
- Hemen bakilacak ornekler: B CAMERA IST ASSISTANT; DIGITAL INTERMEDIATE PRODUCERS; KEY SET COSTUMER; BRIAN TYLER

#### phase1_fps1_allmodels

- frames=180 frame_records=29920 stable_groups=2489 canvas_records=841 runtime_sec=3019.82
- oneocr: frame_records=6363, stable=552, iyi_stable=528, tek_kelime%=4.2, mean_conf=0.98
  - Ornek stable satirlar:
    - [27x, conf=0.988] A CAMERA IST ASSISTANT
    - [24x, conf=0.9896] SUPERVISING SOUND EDITOR
    - [24x, conf=0.9892] KEY SET COSTUMER
    - [24x, conf=0.9886] BRIAN TYLER
    - [24x, conf=0.9787] TRANSPORTATION CAPTAIN - L.A.
    - [23x, conf=0.9883] ASSISTANT SOUND EDITOR
    - [23x, conf=0.9879] VISUAL EFFECTS COORDINATOR
    - [23x, conf=0.9875] ASSISTANT CHIEF LIGHTING TECHNICIAN
    - [23x, conf=0.9855] PROPERTY MASTER
    - [23x, conf=0.9852] DIGITAL INTERMEDIATE EDITORS
  - Canvas ornekleri:
    - ARE FICTITIOUS. NO IDENTIFICATION WITH ACTUAL PERSONS, PLACES, BL
    - OR COPYINNO SRORFU
    - THIS MRTION PICTURE IS PROTECTER
    - OR COPMIM
    - BUIRMRNENCROIT CTED UNDER THE COPYgIOHT LAWCE
- paddle: frame_records=6463, stable=582, iyi_stable=523, tek_kelime%=10.1, mean_conf=0.866
  - Ornek stable satirlar:
    - [27x, conf=0.9871] A CAMERA IST ASSISTANT
    - [24x, conf=0.9984] SUPERVISING SOUND EDITOR
    - [24x, conf=0.994] ASSISTANT CHIEF LIGHTING TECHNICIAN
    - [24x, conf=0.9892] DIGITAL EFFECTS SUPERVISOR
    - [24x, conf=0.9865] TRANSPORTATION CAPTAIN - L.A.
    - [24x, conf=0.9736] ASSISTANT TO MR. GARNER
    - [24x, conf=0.8008] BRIaN TYLER
    - [23x, conf=0.9973] DIGITAL INTERMEDIATE EDITORS
    - [23x, conf=0.9926] ASSISTANT SOUND EDITOR
    - [23x, conf=0.9914] A CAMERA 2ND ASSISTANTS
  - Canvas ornekleri:
    - AND PRODUCTS IS INTENDED OR SHOULD BE INFERRED
    - THE STORY,ALL NAMES_CHARACTERS AND-INCIDENTS PORTRAYED IN THIS PRODUCTION
    - OR COPYINNDPROBUILTS ORIANENARTGREREOFLENBEURFERCNNDTRACK)
    - MAY RESULT IN CIVIL LIABILITY AND CRIMINAL PROSECUTION.
    - THIS MOTION PICTURE IS PROTECTED UNDER THE COPYRIGHT LAWS OF THE UNITED STATES
- tesseract: frame_records=17094, stable=1355, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.766

#### phase2_fps6_fastmodels

- frames=1080 frame_records=140865 stable_groups=2284 canvas_records=104 runtime_sec=1472.557
- oneocr: frame_records=38256, stable=586, iyi_stable=560, tek_kelime%=4.3, mean_conf=0.978
  - Ornek stable satirlar:
    - [154x, conf=0.9872] B CAMERA IST ASSISTANT
    - [143x, conf=0.9777] DIGITAL INTERMEDIATE PRODUCERS
    - [141x, conf=0.9917] KEY SET COSTUMER
    - [141x, conf=0.9894] BRIAN TYLER
    - [141x, conf=0.9892] ASSISTANT EDITORS
    - [141x, conf=0.9875] A CAMERA 2ND ASSISTANTS
    - [141x, conf=0.9853] ASSISTANT CHIEF LIGHTING TECHNICIAN
    - [141x, conf=0.9839] ASST PROPERTY MASTERS
    - [138x, conf=0.9906] 2ND 2ND ASSISTANT DIRECTOR
    - [137x, conf=0.9875] SUPERVISING ADR EDITORS
- tesseract: frame_records=102609, stable=1698, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.678

### 17. evoArcadmin ÇÖZÜMLEME6 2024-1208-1-0000-90-1-SON HAVA BÜKÜCÜ

- En kullanilir veri: **oneocr (phase2_fps6_fastmodels)**
- Karar gerekcesi: 790 iyi stable satir, tek-kelime 4.1%
- Hemen bakilacak ornekler: MICHAEL GILBERT; FILM OFFICE; Digital Model Supervisor; Location Manager

#### phase1_fps1_allmodels

- frames=180 frame_records=30930 stable_groups=3104 canvas_records=1042 runtime_sec=3017.497
- oneocr: frame_records=6653, stable=711, iyi_stable=682, tek_kelime%=3.8, mean_conf=0.963
  - Ornek stable satirlar:
    - [21x, conf=0.986] MICHAEL GILBERT
    - [21x, conf=0.9802] Location Manager
    - [20x, conf=0.949] "B" Second Assistant Photographer
    - [18x, conf=0.9801] Digital Model Supervisor
    - [18x, conf=0.9783] Digital Intermediate by EFILM
    - [18x, conf=0.9644] Stereoscopic Artists
    - [18x, conf=0.951] Scenic Forepersons
    - [17x, conf=0.9491] Visual Effects Art Director
    - [15x, conf=0.9801] FILM OFFICE
    - [15x, conf=0.9696] Location Assistants
  - Canvas ornekleri:
    - LII I ANU LRIMINAL FRUSELUIIUN.
    - OTLAR SAUZURE 1S PROTECTED UNDER LAWS LOT DEURIBUTION OR
    - ND OFREACOUNTRILS. UNAUTHORIZ
    - NSEPEVENTS IN THIS MOTI
    - ON. DEURRUTION OR
- paddle: frame_records=7085, stable=693, iyi_stable=658, tek_kelime%=4.9, mean_conf=0.989
  - Ornek stable satirlar:
    - [22x, conf=0.9922] Digital Intermediate by
    - [22x, conf=0.9914] Construction Grips
    - [22x, conf=0.9893] Stereoscopic Artists
    - [21x, conf=0.997] MICHAEL GILBERT
    - [21x, conf=0.9962] Location Manager
    - [21x, conf=0.996] Chief Construction Electrician
    - [21x, conf=0.9931] Digital Matte Supervisor
    - [21x, conf=0.988] MICHAEL CARROLL, SR.
    - [21x, conf=0.9836] "B" First Assistant Photographer
    - [20x, conf=0.9969] KEVIN GALLAGHER
  - Canvas ornekleri:
    - THIS MOTINTURE IS PRTECTED UNDER LAWSOF
    - THEUUNITED STATES
    - AND OTHER NTRIES UNAUTHORIZED DUPLICATION DISTRBUTION OR
    - EXHENIOREVEN SINI HABMOTYANPICRUMINARPRSECUN
    - ANY SIMILARITY TOACTUAL PERSONS OR EVENTS IS UNINTENTIONAL
- tesseract: frame_records=17192, stable=1700, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.813

#### phase2_fps6_fastmodels

- frames=1080 frame_records=143675 stable_groups=3201 canvas_records=68 runtime_sec=1520.24
- oneocr: frame_records=39892, stable=826, iyi_stable=790, tek_kelime%=4.1, mean_conf=0.954
  - Ornek stable satirlar:
    - [128x, conf=0.9865] MICHAEL GILBERT
    - [128x, conf=0.9815] FILM OFFICE
    - [120x, conf=0.9818] Digital Model Supervisor
    - [120x, conf=0.9808] Location Manager
    - [114x, conf=0.9613] Scenic Forepersons
    - [109x, conf=0.9739] Digital Intermediate by EFILM
    - [99x, conf=0.9568] Stereoscopic Artists
    - [86x, conf=0.9457] Visual Effects Art Director
    - [66x, conf=0.9736] Digital Intermediate Color Assist
    - [65x, conf=0.9865] HAYDEN LANDIS
- tesseract: frame_records=103783, stable=2375, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.716

### 18. web client CAG1 2024-0007-0-0070-91-1-MEHMED FETİHLER SULTANI

- En kullanilir veri: **oneocr (phase2_fps6_fastmodels)**
- Karar gerekcesi: 438 iyi stable satir, tek-kelime 21.6%
- Hemen bakilacak ornekler: EYÜP GÖKHAN ÖZEKİN; BERK ÖZEKİN; HALİS CAHİT KURUTLU; SFX TEKNİSYENİ GOKHAN AL

#### phase1_fps1_allmodels

- frames=180 frame_records=6021 stable_groups=347 canvas_records=2287 runtime_sec=2621.818
- oneocr: frame_records=1151, stable=22, iyi_stable=20, tek_kelime%=9.1, mean_conf=0.942
  - Ornek stable satirlar:
    - [6x, conf=0.968] EYÜP GÖKHAN ÖZEKİN
    - [6x, conf=0.9385] HALİS CAHİT KURUTLU
    - [6x, conf=0.9318] BERK ÖZEKİN
    - [5x, conf=0.7768] MİRAY YAPIM
    - [4x, conf=0.9917] AHMET YILMAZ
    - [4x, conf=0.9805] YILDIRAY YILDIRIM
    - [2x, conf=0.9926] UNIT TALENT
    - [2x, conf=0.9922] UNIT TALENT
    - [2x, conf=0.9839] SFX TEKNİSYENİ SİNAN YÜKSEL
    - [2x, conf=0.9813] SFX TEKNİSYENİ SİNAN YÜKSEL
- paddle: frame_records=1382, stable=38, iyi_stable=22, tek_kelime%=42.1, mean_conf=0.969
  - Ornek stable satirlar:
    - [6x, conf=0.9602] BERK ÖZEKİN
    - [6x, conf=0.9478] SFX TEKNİSYENİ
    - [6x, conf=0.9477] EYÜP GÖKHAN ÖZEKİN
    - [6x, conf=0.9074] S CAHIT
    - [4x, conf=0.998] AHMET YILMAZ
    - [4x, conf=0.9945] YILDIRAY YILDIRIM
    - [3x, conf=0.9391] MİRAY YAPIM
    - [2x, conf=0.9962] UNIT TALENT
    - [2x, conf=0.9898] ICON TALENT
    - [2x, conf=0.9893] TONIC TALENT MANAGEMENT
  - Canvas ornekleri:
    - iSMAiL DURSUN AKBOLA
    - BIEDHIREAIO TGEININ
    - VENTO AJANS CAST SORUMLULARI
    - ULTI AJANS CAST DIREKTORU BAMI
    - MIE RIAMEÇTEBS LANT
- tesseract: frame_records=3488, stable=287, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.824

#### phase2_fps6_fastmodels

- frames=1080 frame_records=28113 stable_groups=2229 canvas_records=707 runtime_sec=1113.511
- oneocr: frame_records=7018, stable=560, iyi_stable=438, tek_kelime%=21.6, mean_conf=0.926
  - Ornek stable satirlar:
    - [38x, conf=0.9639] EYÜP GÖKHAN ÖZEKİN
    - [37x, conf=0.9455] BERK ÖZEKİN
    - [37x, conf=0.9328] HALİS CAHİT KURUTLU
    - [30x, conf=0.9411] SFX TEKNİSYENİ GOKHAN AL
    - [29x, conf=0.9699] SFX TEKNİSYENİ SİNAN YÜKSEL
    - [26x, conf=0.989] AHMET YILMAZ
    - [26x, conf=0.9882] YILDIRAY YILDIRIM
    - [24x, conf=0.819] MİRAY YAPIM
    - [16x, conf=0.9918] AHMET PISIL
    - [16x, conf=0.9877] ICON TALENT
- tesseract: frame_records=21095, stable=1669, iyi_stable=0, tek_kelime%=100.0, mean_conf=0.76

