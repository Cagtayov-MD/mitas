# Hata Atlası — 31 hatanın kanıt-bazlı teşhisi (Görev 3 / T3)

Üretim: `hata_atlasi.py`  GT kaynağı: `veri/dogrulama_sonuc.json` (karar != "dogru", 31 film)

Salt-okunur girdi: `tespit_v5` (credit_onset.py) değiştirilmedi. Bu atlas Görev 4/5/6'nın tasarım kararlarının kanıt tabanıdır.

---

## 1925-1028-1-0000-90-1_POTEMKİN_ZIRHLISI

**GT:** karar=`yanlis_kare`  gercek_onset=`1133`  **v5(şimdi):** tahmin=`1133`  yöntem=`kutu+scroll+içerik`  sapma=`0`

v5 notları: aday=5 seçilen=[1097-1199] kb=1.00 joint=1.80 scroll_oran=0.12 budama=18 genislet=0


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 201 | 243 | False | — | — | — |
| 1 | 713 | 743 | False | — | — | — |
| 2 | 909 | 959 | False | — | — | — |
| 3 | 1013 | 1051 | True | 0.000 | 0.000 | — |
| 4 | 1097 | 1199 | True | 1.000 | 1.800 | — |


**(b) Gerçek-onset (1133) konumu:** aday 4 İÇİNDE [1097-1199] (son_ok=True, kb=1.0)


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 1131 (`c_01131.png`): []

- kare 1133 (`c_01133.png`): ['Regie', 'Sergei M. Eisenstein', '1925', 'YÖNETMEN', 'SERGEY M. AYZENŞTAYN', '1925']

- kare 1137 (`c_01137.png`): ['Regie', 'Sergei M. Eisenstein', '1925', 'YÖNETMEN', 'SERGEY M. AYZENŞTAYN', '1925']


**(d) Scroll istatistiği (gt±10, stride=2):** n=11 örnek-çift, oran(dy>3&corr≥.85)=0.0, dy_medyan=0.0


**(e) Ön-teşhis etiketi:** `DIGER` — pred=1133 gt=1133 — yukarıdaki kalıplara net uymuyor


_(hedef görev: T5; işleme süresi 22.7 sn)_


---

## 1940-0026-1-0000-00-1_KNUTE_ROICKNE

**GT:** karar=`yanlis_kare`  gercek_onset=`1146`  **v5(şimdi):** tahmin=`1131`  yöntem=`kutu+içerik`  sapma=`-15`

v5 notları: aday=5 seçilen=[1117-1201] kb=1.00 joint=1.50 scroll_oran=0.00 budama=7 genislet=0


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 189 | 231 | False | — | — | — |
| 1 | 437 | 495 | False | — | — | — |
| 2 | 593 | 619 | False | — | — | — |
| 3 | 1017 | 1075 | True | 0.000 | 0.000 | — |
| 4 | 1117 | 1201 | True | 1.000 | 1.500 | — |


**(b) Gerçek-onset (1146) konumu:** aday 4 İÇİNDE [1117-1201] (son_ok=True, kb=1.0)


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 1144 (`c_01144.png`): ['KR', 'W', 'The End', 'WARNERBROS.-FIRSTNATIONAL', 'PICTURE']

- kare 1146 (`c_01146.png`): ['The Players', 'KR', 'KnuteRockno.....', 'PAT OBRIEN', 'BennieSkiles Rockne.....', '.GALE PAGE', 'SeergeSipp.', 'RONALD REAGAN']

- kare 1150 (`c_01150.png`): ['mnGo', 'The Players', 'KR', 'KnuteRockno.....', 'PAT OBRIEN', 'Bennie Skiles Rockne.....', '.GALE PAGE', 'SrergeSipp......']


**(d) Scroll istatistiği (gt±10, stride=2):** n=10 örnek-çift, oran(dy>3&corr≥.85)=0.0, dy_medyan=0.0


**(e) Ön-teşhis etiketi:** `ERKEN_METIN` — tahmin=1131 < gt=1146 (koşu başı kredi-dışı metin erken tetiklemiş; gt'yi içeren aday içerik-eşiğini geçmesine rağmen daha erken bir aday kazandı)


_(hedef görev: T5; işleme süresi 9.5 sn)_


---

## 1978-0227-1-0000-00-1_TAKKELİ_MELEK

**GT:** karar=`yanlis_kare`  gercek_onset=`588`  **v5(şimdi):** tahmin=`905`  yöntem=`kutu+scroll+içerik`  sapma=`317`

v5 notları: aday=3 seçilen=[905-1199] kb=1.00 joint=1.80 scroll_oran=0.86


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 345 | 399 | False | — | — | — |
| 1 | 589 | 651 | False | — | — | — |
| 2 | 905 | 1199 | True | 1.000 | 1.800 | assistant, camera, music, written |


**(b) Gerçek-onset (588) konumu:** aday 0 ile aday 1 ARASINDA boşlukta


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 586 (`c_00586.png`): []

- kare 588 (`c_00588.png`): ['i']

- kare 592 (`c_00592.png`): ['i K Y']


**(d) Scroll istatistiği (gt±10, stride=2):** n=10 örnek-çift, oran(dy>3&corr≥.85)=0.0, dy_medyan=0.0


**(e) Ön-teşhis etiketi:** `KUTU_YOK` — gt hiçbir adayın kutu-koşusu içinde değil


_(hedef görev: T4; işleme süresi 8.5 sn)_


---

## 1979-0208-1-0000-00-1_TESS

**GT:** karar=`yanlis_kare`  gercek_onset=`1074`  **v5(şimdi):** tahmin=`1037`  yöntem=`kutu+içerik`  sapma=`-37`

v5 notları: aday=1 seçilen=[1037-1199] kb=1.00 joint=1.50 scroll_oran=0.00 budama=0 genislet=0


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 1037 | 1199 | True | 1.000 | 1.499 | — |


**(b) Gerçek-onset (1074) konumu:** aday 0 İÇİNDE [1037-1199] (son_ok=True, kb=1.0)


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 1072 (`c_01072.png`): []

- kare 1074 (`c_01074.png`): []

- kare 1078 (`c_01078.png`): ["par ondre d'apparition", 'Joba Darbvyfeld', 'JOHNCOLLIN', 'Pastrar Tringhem', 'TONYCHURCH', 'Teu', 'XASTASSIA KINSKI', 'Jeanes filles daas le pré']


**(d) Scroll istatistiği (gt±10, stride=2):** n=10 örnek-çift, oran(dy>3&corr≥.85)=0.0, dy_medyan=0.0


**(e) Ön-teşhis etiketi:** `ERKEN_METIN` — tahmin=1037 < gt=1074 (koşu başı kredi-dışı metin erken tetiklemiş; gt'yi içeren aday içerik-eşiğini geçmesine rağmen daha erken bir aday kazandı)


_(hedef görev: T5; işleme süresi 7.5 sn)_


---

## 1981-0253-1-0000-00-1_YÜREKTEN_SEVMEK

**GT:** karar=`yanlis_kare`  gercek_onset=`722`  **v5(şimdi):** tahmin=`697`  yöntem=`kutu+scroll+içerik`  sapma=`-25`

v5 notları: aday=1 seçilen=[697-1179] kb=1.00 joint=1.79 scroll_oran=0.70


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 697 | 1179 | True | 1.000 | 1.794 | art, assistant, director |


**(b) Gerçek-onset (722) konumu:** aday 0 İÇİNDE [697-1179] (son_ok=True, kb=1.0)


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 720 (`c_00720.png`): []

- kare 722 (`c_00722.png`): []

- kare 726 (`c_00726.png`): ['CASTOFCHARACTERS', 'HANK', 'FREDERIC FORREST', 'FRANNIE', 'TERIGARR']


**(d) Scroll istatistiği (gt±10, stride=2):** n=10 örnek-çift, oran(dy>3&corr≥.85)=0.4, dy_medyan=9.5


**(e) Ön-teşhis etiketi:** `ERKEN_METIN` — tahmin=697 < gt=722 (koşu başı kredi-dışı metin erken tetiklemiş; gt'yi içeren aday içerik-eşiğini geçmesine rağmen daha erken bir aday kazandı)


_(hedef görev: T5; işleme süresi 10.0 sn)_


---

## 1988-0361-1-0000-00-1_DOĞUM_GÜNÜN_KUTLU_OLSUN_MAR

**GT:** karar=`yanlis_kredi_var`  gercek_onset=`816`  **v5(şimdi):** tahmin=`-1`  yöntem=`kredi_yok`  sapma=`None`

v5 notları: tüm adaylar SON_ERISIM'e takıldı


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 821 | 891 | False | — | — | — |


**(b) Gerçek-onset (816) konumu:** İLK adaydan ÖNCE (aday0 başlangıcı=821)


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 814 (`c_00814.png`): []

- kare 816 (`c_00816.png`): []

- kare 820 (`c_00820.png`): ['Saörény Reasó', 'ireai', 'Uámos Miklós', 'dramalurgi', 'Rózsa János', 'nene: Tamássy Zdenkó']


**(d) Scroll istatistiği (gt±10, stride=2):** n=10 örnek-çift, oran(dy>3&corr≥.85)=0.0, dy_medyan=11.0


**(e) Ön-teşhis etiketi:** `KUTU_YOK` — gt hiçbir adayın kutu-koşusu içinde değil


_(hedef görev: T6; işleme süresi 6.0 sn)_


---

## 1988-0780-1-0000-00-1_İKİ_KAFADAR

**GT:** karar=`yanlis_kare`  gercek_onset=`1036`  **v5(şimdi):** tahmin=`969`  yöntem=`kutu+scroll+içerik`  sapma=`-67`

v5 notları: aday=2 seçilen=[969-1195] kb=1.00 joint=1.80 scroll_oran=0.56


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 317 | 347 | False | — | — | — |
| 1 | 969 | 1195 | True | 1.000 | 1.799 | camera, cast |


**(b) Gerçek-onset (1036) konumu:** aday 1 İÇİNDE [969-1195] (son_ok=True, kb=1.0)


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 1034 (`c_01034.png`): ['Rooky Mountain', 'Hellcopters']

- kare 1036 (`c_01036.png`): ['Roky Mountain', 'Hellcopters', 'Film Editor', 'DENNISR.LISONBEE']

- kare 1040 (`c_01040.png`): ['Mountain', 'Hellcopters', 'Film Editor', 'DENNISR.LISONBEE']


**(d) Scroll istatistiği (gt±10, stride=2):** n=10 örnek-çift, oran(dy>3&corr≥.85)=0.0, dy_medyan=0.0


**(e) Ön-teşhis etiketi:** `ERKEN_METIN` — tahmin=969 < gt=1036 (koşu başı kredi-dışı metin erken tetiklemiş; gt'yi içeren aday içerik-eşiğini geçmesine rağmen daha erken bir aday kazandı)


_(hedef görev: T5; işleme süresi 8.7 sn)_


---

## 1989-0476-1-0000-00-1_VANYA_DAYI

**GT:** karar=`yanlis_kredi_var`  gercek_onset=`904`  **v5(şimdi):** tahmin=`-1`  yöntem=`kredi_yok`  sapma=`None`

v5 notları: içerik-eşiği geçilemedi (en iyi kb=0.33)


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 49 | 175 | False | — | — | — |
| 1 | 221 | 299 | False | — | — | — |
| 2 | 913 | 1191 | True | 0.333 | 0.499 | — |


**(b) Gerçek-onset (904) konumu:** aday 1 ile aday 2 ARASINDA boşlukta


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 902 (`c_00902.png`): ['11']

- kare 904 (`c_00904.png`): [':']

- kare 908 (`c_00908.png`): [':']


**(d) Scroll istatistiği (gt±10, stride=2):** n=10 örnek-çift, oran(dy>3&corr≥.85)=0.0, dy_medyan=0.0


**(e) Ön-teşhis etiketi:** `KUTU_YOK` — gt hiçbir adayın kutu-koşusu içinde değil


_(hedef görev: T6; işleme süresi 7.5 sn)_


---

## 1989-0624-1-0000-00-1_DÖNÜŞÜ_OLMAYAN_NEHİR

**GT:** karar=`yanlis_kredi_yok`  gercek_onset=`-1`  **v5(şimdi):** tahmin=`1125`  yöntem=`kutu+scroll+içerik`  sapma=`None`

v5 notları: aday=3 seçilen=[1125-1191] kb=1.00 joint=1.76 scroll_oran=0.12 budama=0 genislet=0


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 29 | 99 | False | — | — | — |
| 1 | 745 | 775 | False | — | — | — |
| 2 | 1125 | 1191 | True | 1.000 | 1.760 | — |


**(b)-(d):** GT kredi_yok(-1) — gerçek-onset yok, konum/içerik/scroll penceresi tanımsız (atlandı).


**(e) Ön-teşhis etiketi:** `DIGER` — GT kredi_yok(-1) ama v5 kredi_var dedi — ters yönlü yanlış-pozitif, 6 etiketten hiçbiri tam uymuyor


_(hedef görev: ?? (ters-yönlü yanlış-pozitif, T4/T5/T6 dışı — ayrı ele alınmalı); işleme süresi 7.8 sn)_


---

## 1989-0955-1-0000-00-1_ÖLDÜRME_ZAMANI

**GT:** karar=`yanlis_kredi_var`  gercek_onset=`1137`  **v5(şimdi):** tahmin=`-1`  yöntem=`kredi_yok`  sapma=`None`

v5 notları: içerik-eşiği geçilemedi (en iyi kb=0.00)


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 1137 | 1179 | True | 0.000 | 0.000 | — |


**(b) Gerçek-onset (1137) konumu:** aday 0 İÇİNDE [1137-1179] (son_ok=True, kb=0.0)


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 1135 (`c_01135.png`): []

- kare 1137 (`c_01137.png`): ['operatore macchina. . gastone di giovanni', 'assistenti operatores', 'sergio martinelli', 'carlo tafani c.s.c.', 'costumista', '. silvano giusti', 'ispettore di produzione . . albino morandin', 'segretari di produzione . . . mario barboni']

- kare 1141 (`c_01141.png`): ['operatore macchina.  gastone di giovanni', 'assintenti operatore.', 'sergio martinelli', 'carlo tafani c.s.c.', 'costuminta', ', silvano ginsti', 'ispettore di produzione, , albino morandin', 'segretari di produzione. . mario barboni']


**(d) Scroll istatistiği (gt±10, stride=2):** n=11 örnek-çift, oran(dy>3&corr≥.85)=0.0, dy_medyan=0.0


**(e) Ön-teşhis etiketi:** `ICERIK_REDDI` — gt aday[1137-1179] içinde ama kb=0.0<0.6 (içerik-eşiği geçilemedi)


_(hedef görev: T6; işleme süresi 8.1 sn)_


---

## 1992-0455-1-0000-00-1_MELEKLERİ_GÖRMEK_İSTEDİM

**GT:** karar=`yanlis_kredi_var`  gercek_onset=`934`  **v5(şimdi):** tahmin=`-1`  yöntem=`kredi_yok`  sapma=`None`

v5 notları: içerik-eşiği geçilemedi (en iyi kb=0.33)


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 917 | 1123 | True | 0.333 | 0.592 | — |


**(b) Gerçek-onset (934) konumu:** aday 0 İÇİNDE [917-1123] (son_ok=True, kb=0.333)


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 932 (`c_00932.png`): []

- kare 934 (`c_00934.png`): []

- kare 938 (`c_00938.png`): ['O', 'o:']


**(d) Scroll istatistiği (gt±10, stride=2):** n=10 örnek-çift, oran(dy>3&corr≥.85)=0.5, dy_medyan=25.0


**(e) Ön-teşhis etiketi:** `ICERIK_REDDI` — gt aday[917-1123] içinde ama kb=0.333<0.6 (içerik-eşiği geçilemedi)


_(hedef görev: T6; işleme süresi 7.8 sn)_


---

## 1993-0435-1-0000-00-1_SEN_TOM_SAWYER_DEĞİLSİN

**GT:** karar=`yanlis_kredi_var`  gercek_onset=`805`  **v5(şimdi):** tahmin=`-1`  yöntem=`kredi_yok`  sapma=`None`

v5 notları: içerik-eşiği geçilemedi (en iyi kb=0.00)


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 809 | 1135 | True | 0.000 | 0.000 | — |


**(b) Gerçek-onset (805) konumu:** İLK adaydan ÖNCE (aday0 başlangıcı=809)


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 803 (`c_00803.png`): ['NT']

- kare 805 (`c_00805.png`): ['Sascha']

- kare 809 (`c_00809.png`): ['Sascha', 'Oliver Engl']


**(d) Scroll istatistiği (gt±10, stride=2):** n=11 örnek-çift, oran(dy>3&corr≥.85)=0.0, dy_medyan=0.0


**(e) Ön-teşhis etiketi:** `KUTU_YOK` — gt hiçbir adayın kutu-koşusu içinde değil


_(hedef görev: T6; işleme süresi 8.2 sn)_


---

## 1995-0363-1-0000-00-1_KÜÇÜK_SİMBA_DÜNYA_KUPASIN

**GT:** karar=`yanlis_kredi_var`  gercek_onset=`1035`  **v5(şimdi):** tahmin=`-1`  yöntem=`kredi_yok`  sapma=`None`

v5 notları: içerik-eşiği geçilemedi (en iyi kb=0.00)


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 817 | 855 | False | — | — | — |
| 1 | 941 | 967 | False | — | — | — |
| 2 | 1037 | 1091 | True | 0.000 | 0.000 | director |
| 3 | 1121 | 1167 | True | 0.000 | 0.000 | music |


**(b) Gerçek-onset (1035) konumu:** aday 1 ile aday 2 ARASINDA boşlukta


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 1033 (`c_01033.png`): []

- kare 1035 (`c_01035.png`): ['Script', 'CHstal', 'L. Peota']

- kare 1039 (`c_01039.png`): ['Scripts', 'L. Peota·C.Castalde']


**(d) Scroll istatistiği (gt±10, stride=2):** n=11 örnek-çift, oran(dy>3&corr≥.85)=0.09, dy_medyan=6.0


**(e) Ön-teşhis etiketi:** `KUTU_YOK` — gt hiçbir adayın kutu-koşusu içinde değil


_(hedef görev: T6; işleme süresi 7.9 sn)_


---

## 1996-0325-1-0000-00-1_KIZIL_HAYAT

**GT:** karar=`yanlis_kare`  gercek_onset=`964`  **v5(şimdi):** tahmin=`901`  yöntem=`kutu+scroll+içerik`  sapma=`-63`

v5 notları: aday=3 seçilen=[901-1183] kb=1.00 joint=1.80 scroll_oran=0.09 budama=0 genislet=0


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 117 | 227 | False | — | — | — |
| 1 | 553 | 595 | False | — | — | — |
| 2 | 901 | 1183 | True | 1.000 | 1.795 | assistant |


**(b) Gerçek-onset (964) konumu:** aday 2 İÇİNDE [901-1183] (son_ok=True, kb=1.0)


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 962 (`c_00962.png`): ['LINROUGE', 'MOULIN ROUGE']

- kare 964 (`c_00964.png`): ['avec', 'Varlim Alevander Raloluev']

- kare 968 (`c_00968.png`): ['avec', 'Vadim', 'Alexander Balouey', 'Uluk', 'Serguei Stepantchenko', 'Jafar', 'Dimitri Pevtsov', 'Ivan']


**(d) Scroll istatistiği (gt±10, stride=2):** n=10 örnek-çift, oran(dy>3&corr≥.85)=0.0, dy_medyan=13.5


**(e) Ön-teşhis etiketi:** `ERKEN_METIN` — tahmin=901 < gt=964 (koşu başı kredi-dışı metin erken tetiklemiş; gt'yi içeren aday içerik-eşiğini geçmesine rağmen daha erken bir aday kazandı)


_(hedef görev: T5; işleme süresi 6.4 sn)_


---

## 1999-0403-1-0000-00-1_PRENSESİN_AŞKI

**GT:** karar=`yanlis_kare`  gercek_onset=`1046`  **v5(şimdi):** tahmin=`1083`  yöntem=`kutu+içerik`  sapma=`37`

v5 notları: aday=3 seçilen=[1085-1179] kb=1.00 joint=1.49 scroll_oran=0.00 budama=0 genislet=1


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 405 | 427 | False | — | — | — |
| 1 | 533 | 559 | False | — | — | — |
| 2 | 1085 | 1179 | True | 1.000 | 1.494 | assistant, design, make-up, sound |


**(b) Gerçek-onset (1046) konumu:** aday 1 ile aday 2 ARASINDA boşlukta


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 1044 (`c_01044.png`): []

- kare 1046 (`c_01046.png`): ['Executive Producers', 'PETER LOCKE', 'DONALD KUSHNER']

- kare 1050 (`c_01050.png`): ['Executive Producers', 'PETER LOCKE', 'DONALD KUSHNER']


**(d) Scroll istatistiği (gt±10, stride=2):** n=10 örnek-çift, oran(dy>3&corr≥.85)=0.0, dy_medyan=0.0


**(e) Ön-teşhis etiketi:** `KUTU_YOK` — gt hiçbir adayın kutu-koşusu içinde değil


_(hedef görev: T4; işleme süresi 6.4 sn)_


---

## 2000-0323-1-0000-00-1_6

**GT:** karar=`yanlis_kare`  gercek_onset=`434`  **v5(şimdi):** tahmin=`589`  yöntem=`kutu+scroll+içerik`  sapma=`155`

v5 notları: aday=3 seçilen=[557-1195] kb=1.00 joint=1.80 scroll_oran=0.21 budama=16 genislet=0


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 113 | 211 | False | — | — | — |
| 1 | 437 | 507 | False | — | — | — |
| 2 | 557 | 1195 | True | 1.000 | 1.799 | director, producer, sound |


**(b) Gerçek-onset (434) konumu:** aday 0 ile aday 1 ARASINDA boşlukta


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 432 (`c_00432.png`): ['O']

- kare 434 (`c_00434.png`): ['Directed by', 'ROGER SPOTTISWOODE']

- kare 438 (`c_00438.png`): ['Directed by', 'ROGER SPOTTISWOODE']


**(d) Scroll istatistiği (gt±10, stride=2):** n=10 örnek-çift, oran(dy>3&corr≥.85)=0.0, dy_medyan=0.0


**(e) Ön-teşhis etiketi:** `KUTU_YOK` — gt hiçbir adayın kutu-koşusu içinde değil


_(hedef görev: T4; işleme süresi 7.4 sn)_


---

## 2000-0491-1-0000-00-1_PARDAYYAN

**GT:** karar=`yanlis_kare`  gercek_onset=`1034`  **v5(şimdi):** tahmin=`1089`  yöntem=`kutu+içerik`  sapma=`55`

v5 notları: aday=1 seçilen=[1089-1159] kb=1.00 joint=1.49 scroll_oran=0.00 budama=0 genislet=0


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 1089 | 1159 | True | 1.000 | 1.488 | assistant |


**(b) Gerçek-onset (1034) konumu:** İLK adaydan ÖNCE (aday0 başlangıcı=1089)


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 1032 (`c_01032.png`): []

- kare 1034 (`c_01034.png`): ['JEAN-LUC BIDEAU']

- kare 1038 (`c_01038.png`): ['SA']


**(d) Scroll istatistiği (gt±10, stride=2):** n=10 örnek-çift, oran(dy>3&corr≥.85)=0.0, dy_medyan=0.0


**(e) Ön-teşhis etiketi:** `KUTU_YOK` — gt hiçbir adayın kutu-koşusu içinde değil


_(hedef görev: T4; işleme süresi 7.8 sn)_


---

## 2002-9173-1-0000-00-1_ROBOCOP_KARA_ADALET

**GT:** karar=`yanlis_kredi_var`  gercek_onset=`1088`  **v5(şimdi):** tahmin=`-1`  yöntem=`kredi_yok`  sapma=`None`

v5 notları: içerik-eşiği geçilemedi (en iyi kb=0.00)


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 105 | 139 | False | — | — | — |
| 1 | 389 | 423 | False | — | — | — |
| 2 | 729 | 859 | False | — | — | — |
| 3 | 1129 | 1175 | True | 0.000 | 0.000 | directed, executive |


**(b) Gerçek-onset (1088) konumu:** aday 2 ile aday 3 ARASINDA boşlukta


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 1086 (`c_01086.png`): ['WWW.ROBOCOP-PD.CA']

- kare 1088 (`c_01088.png`): ['FIREWORKS ENTERTAINMENT', 'presents']

- kare 1092 (`c_01092.png`): ['a JULIAN GRANT production']


**(d) Scroll istatistiği (gt±10, stride=2):** n=10 örnek-çift, oran(dy>3&corr≥.85)=0.1, dy_medyan=0.0


**(e) Ön-teşhis etiketi:** `KUTU_YOK` — gt hiçbir adayın kutu-koşusu içinde değil


_(hedef görev: T6; işleme süresi 6.5 sn)_


---

## 2003-9136-1-0000-00-1_HARİKA_KÖPEK_5

**GT:** karar=`yanlis_kare`  gercek_onset=`737`  **v5(şimdi):** tahmin=`613`  yöntem=`kutu+scroll+içerik`  sapma=`-124`

v5 notları: aday=5 seçilen=[613-1195] kb=1.00 joint=1.80 scroll_oran=0.82


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 5 | 111 | False | — | — | — |
| 1 | 149 | 187 | False | — | — | — |
| 2 | 229 | 271 | False | — | — | — |
| 3 | 421 | 443 | False | — | — | — |
| 4 | 613 | 1195 | True | 1.000 | 1.799 | assistant, camera, costume, director, make-up, sound |


**(b) Gerçek-onset (737) konumu:** aday 4 İÇİNDE [613-1195] (son_ok=True, kb=1.0)


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 735 (`c_00735.png`): []

- kare 737 (`c_00737.png`): ['Cast', '(In Alphabetical Order)']

- kare 741 (`c_00741.png`): ['Cast', '(In Alphabetical Order)', 'Pottery Vendor', 'DARREN J. BIRCH', 'Justin', 'CHRISTOPHER BISHOP', 'Connor', 'TYLER BOISSONNAULT']


**(d) Scroll istatistiği (gt±10, stride=2):** n=11 örnek-çift, oran(dy>3&corr≥.85)=0.55, dy_medyan=22.0


**(e) Ön-teşhis etiketi:** `ERKEN_METIN` — tahmin=613 < gt=737 (koşu başı kredi-dışı metin erken tetiklemiş; gt'yi içeren aday içerik-eşiğini geçmesine rağmen daha erken bir aday kazandı)


_(hedef görev: T5; işleme süresi 8.4 sn)_


---

## 2004-9131-1-0000-00-1_YALNIZ_SAVAŞÇI

**GT:** karar=`yanlis_kare`  gercek_onset=`1097`  **v5(şimdi):** tahmin=`907`  yöntem=`kutu+scroll+içerik`  sapma=`-190`

v5 notları: aday=1 seçilen=[909-1199] kb=1.00 joint=1.80 scroll_oran=0.01 budama=0 genislet=1


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 909 | 1199 | True | 1.000 | 1.800 | executive |


**(b) Gerçek-onset (1097) konumu:** aday 0 İÇİNDE [909-1199] (son_ok=True, kb=1.0)


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 1095 (`c_01095.png`): ['LAURA NEWTON', 'HOMECOMING', 'LATEST']

- kare 1097 (`c_01097.png`): ['WRITTEN AND DIRECTED BY', 'DAVID MAMET']

- kare 1101 (`c_01101.png`): ['AAE', 'R Y']


**(d) Scroll istatistiği (gt±10, stride=2):** n=11 örnek-çift, oran(dy>3&corr≥.85)=0.0, dy_medyan=0.0


**(e) Ön-teşhis etiketi:** `ERKEN_METIN` — tahmin=907 < gt=1097 (koşu başı kredi-dışı metin erken tetiklemiş; gt'yi içeren aday içerik-eşiğini geçmesine rağmen daha erken bir aday kazandı)


_(hedef görev: T5; işleme süresi 7.6 sn)_


---

## 2005-9162-1-0000-00-1_DİPTEKİLER

**GT:** karar=`yanlis_kare`  gercek_onset=`416`  **v5(şimdi):** tahmin=`619`  yöntem=`kutu+scroll+içerik`  sapma=`203`

v5 notları: aday=2 seçilen=[573-1191] kb=1.00 joint=1.80 scroll_oran=0.24 budama=23 genislet=0


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 417 | 515 | False | — | — | — |
| 1 | 573 | 1191 | True | 1.000 | 1.798 | assistant, costume, editor |


**(b) Gerçek-onset (416) konumu:** İLK adaydan ÖNCE (aday0 başlangıcı=417)


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 414 (`c_00414.png`): []

- kare 416 (`c_00416.png`): ['AVIDTWOHY', 'IRE BY']

- kare 420 (`c_00420.png`): ['DAVIDTOHY', 'IE BY']


**(d) Scroll istatistiği (gt±10, stride=2):** n=10 örnek-çift, oran(dy>3&corr≥.85)=0.0, dy_medyan=0.0


**(e) Ön-teşhis etiketi:** `KUTU_YOK` — gt hiçbir adayın kutu-koşusu içinde değil


_(hedef görev: T4; işleme süresi 7.4 sn)_


---

## 2006-9139-1-0000-90-1_TAKTİKLER_SAVAŞI

**GT:** karar=`yanlis_kredi_var`  gercek_onset=`651`  **v5(şimdi):** tahmin=`-1`  yöntem=`kredi_yok`  sapma=`None`

v5 notları: içerik-eşiği geçilemedi (en iyi kb=0.00)


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 617 | 1115 | True | 0.000 | 0.000 | assistant, camera, make-up |


**(b) Gerçek-onset (651) konumu:** aday 0 İÇİNDE [617-1115] (son_ok=True, kb=0.0)


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 649 (`c_00649.png`): []

- kare 651 (`c_00651.png`): ['screenplay, produced and directed by', 'jacob cheung']

- kare 655 (`c_00655.png`): ['screenplay, produced and directed by', 'jacob cheung']


**(d) Scroll istatistiği (gt±10, stride=2):** n=11 örnek-çift, oran(dy>3&corr≥.85)=0.0, dy_medyan=0.0


**(e) Ön-teşhis etiketi:** `ICERIK_REDDI` — gt aday[617-1115] içinde ama kb=0.0<0.6 (içerik-eşiği geçilemedi)


_(hedef görev: T6; işleme süresi 9.7 sn)_


---

## 2008-9046-1-0000-88-1_MEVLANA_AŞKIN_DANSI

**GT:** karar=`yanlis_kare`  gercek_onset=`754`  **v5(şimdi):** tahmin=`755`  yöntem=`kutu+scroll+içerik`  sapma=`1`

v5 notları: aday=4 seçilen=[733-1191] kb=1.00 joint=1.80 scroll_oran=0.27 budama=11 genislet=0


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 145 | 167 | False | — | — | — |
| 1 | 197 | 223 | False | — | — | — |
| 2 | 485 | 543 | False | — | — | — |
| 3 | 733 | 1191 | True | 1.000 | 1.798 | görüntü, müzik, yapim |


**(b) Gerçek-onset (754) konumu:** aday 3 İÇİNDE [733-1191] (son_ok=True, kb=1.0)


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 752 (`c_00752.png`): []

- kare 754 (`c_00754.png`): ['SENARYO - YONETMEN', 'Kürşat Kizbaz']

- kare 758 (`c_00758.png`): ['SENARYO - YONETMEN', 'KürşatKizbaz']


**(d) Scroll istatistiği (gt±10, stride=2):** n=10 örnek-çift, oran(dy>3&corr≥.85)=0.0, dy_medyan=0.0


**(e) Ön-teşhis etiketi:** `DIGER` — pred=755 gt=754 — yukarıdaki kalıplara net uymuyor


_(hedef görev: T4; işleme süresi 4.0 sn)_


---

## 2008-9066-1-0000-00-1_MESLEĞE_DÖNÜŞ

**GT:** karar=`yanlis_kare`  gercek_onset=`373`  **v5(şimdi):** tahmin=`693`  yöntem=`kutu+scroll+içerik`  sapma=`320`

v5 notları: aday=2 seçilen=[693-1199] kb=1.00 joint=1.80 scroll_oran=0.95


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 373 | 659 | False | — | — | — |
| 1 | 693 | 1199 | True | 1.000 | 1.800 | assistant, costume, design, music, producer |


**(b) Gerçek-onset (373) konumu:** aday 0 İÇİNDE [373-659] (son_ok=False, kb=None)


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 371 (`c_00371.png`): []

- kare 373 (`c_00373.png`): ['DIRECTED BY', 'CHRIS MUNRO']

- kare 377 (`c_00377.png`): ['DIRECTED BY', 'CHRIS MUNRO']


**(d) Scroll istatistiği (gt±10, stride=2):** n=11 örnek-çift, oran(dy>3&corr≥.85)=0.09, dy_medyan=0.0


**(e) Ön-teşhis etiketi:** `SON_ERISIM_KURBANI` — gt aday[373-659] içinde ama son_ok=False (SON_ERISIM=0.82'ye takıldı, içerik hiç ölçülmedi)


_(hedef görev: T4; işleme süresi 9.0 sn)_


---

## 2011-9224-1-0000-88-1_KANDAHAR

**GT:** karar=`yanlis_kredi_var`  gercek_onset=`964`  **v5(şimdi):** tahmin=`-1`  yöntem=`kredi_yok`  sapma=`None`

v5 notları: içerik-eşiği geçilemedi (en iyi kb=0.00)


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 969 | 1191 | True | 0.000 | 0.000 | — |


**(b) Gerçek-onset (964) konumu:** İLK adaydan ÖNCE (aday0 başlangıcı=969)


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 962 (`c_00962.png`): []

- kare 964 (`c_00964.png`): []

- kare 968 (`c_00968.png`): []


**(d) Scroll istatistiği (gt±10, stride=2):** n=10 örnek-çift, oran(dy>3&corr≥.85)=0.0, dy_medyan=0.0


**(e) Ön-teşhis etiketi:** `KUTU_YOK` — gt hiçbir adayın kutu-koşusu içinde değil


_(hedef görev: T6; işleme süresi 6.9 sn)_


---

## 2017-1081-1-0000-50-0_KARAVAN

**GT:** karar=`yanlis_kare`  gercek_onset=`577`  **v5(şimdi):** tahmin=`759`  yöntem=`kutu+scroll+içerik`  sapma=`182`

v5 notları: aday=2 seçilen=[753-1199] kb=1.00 joint=1.80 scroll_oran=0.07 budama=3 genislet=0


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 577 | 675 | False | — | — | — |
| 1 | 753 | 1199 | True | 1.000 | 1.799 | — |


**(b) Gerçek-onset (577) konumu:** aday 0 İÇİNDE [577-675] (son_ok=False, kb=None)


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 575 (`c_00575.png`): []

- kare 577 (`c_00577.png`): ['PALO VIRZI', 'dirctd by']

- kare 581 (`c_00581.png`): ['directed by', 'PAOLO VIRZI']


**(d) Scroll istatistiği (gt±10, stride=2):** n=11 örnek-çift, oran(dy>3&corr≥.85)=0.0, dy_medyan=0.0


**(e) Ön-teşhis etiketi:** `SON_ERISIM_KURBANI` — gt aday[577-675] içinde ama son_ok=False (SON_ERISIM=0.82'ye takıldı, içerik hiç ölçülmedi)


_(hedef görev: T4; işleme süresi 5.7 sn)_


---

## 2023-1047-1-0000-90-1_GELECEK_GÜNLER

**GT:** karar=`yanlis_kare`  gercek_onset=`672`  **v5(şimdi):** tahmin=`763`  yöntem=`kutu+içerik`  sapma=`91`

v5 notları: aday=2 seçilen=[741-1199] kb=1.00 joint=1.50 scroll_oran=0.00 budama=11 genislet=0


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 221 | 263 | False | — | — | — |
| 1 | 741 | 1199 | True | 1.000 | 1.500 | music |


**(b) Gerçek-onset (672) konumu:** aday 0 ile aday 1 ARASINDA boşlukta


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 670 (`c_00670.png`): []

- kare 672 (`c_00672.png`): ['ISABELLE HUPPERT']

- kare 676 (`c_00676.png`): ['ISABELLE HUPPERT']


**(d) Scroll istatistiği (gt±10, stride=2):** n=10 örnek-çift, oran(dy>3&corr≥.85)=0.0, dy_medyan=0.0


**(e) Ön-teşhis etiketi:** `KUTU_YOK` — gt hiçbir adayın kutu-koşusu içinde değil


_(hedef görev: T4; işleme süresi 11.2 sn)_


---

## 2023-1224-1-0000-56-1_ARKADAŞIMIN_EVİ_NEREDE

**GT:** karar=`yanlis_kredi_var`  gercek_onset=`925`  **v5(şimdi):** tahmin=`-1`  yöntem=`kredi_yok`  sapma=`None`

v5 notları: içerik-eşiği geçilemedi (en iyi kb=0.00)


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 897 | 1187 | True | 0.000 | 0.000 | — |


**(b) Gerçek-onset (925) konumu:** aday 0 İÇİNDE [897-1187] (son_ok=True, kb=0.0)


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 923 (`c_00923.png`): []

- kare 925 (`c_00925.png`): []

- kare 929 (`c_00929.png`): []


**(d) Scroll istatistiği (gt±10, stride=2):** n=11 örnek-çift, oran(dy>3&corr≥.85)=0.55, dy_medyan=12.0


**(e) Ön-teşhis etiketi:** `ICERIK_REDDI` — gt aday[897-1187] içinde ama kb=0.0<0.6 (içerik-eşiği geçilemedi)


_(hedef görev: T6; işleme süresi 8.9 sn)_


---

## 2025-1112-1-0000-56-1_İNİŞLİ_ÇIKIŞLI_BİR_ÖYK

**GT:** karar=`yanlis_kare`  gercek_onset=`862`  **v5(şimdi):** tahmin=`951`  yöntem=`kutu+scroll+içerik`  sapma=`89`

v5 notları: aday=5 seçilen=[945-1201] kb=1.00 joint=1.80 scroll_oran=0.25 budama=3 genislet=0


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 1 | 155 | False | — | — | — |
| 1 | 185 | 311 | False | — | — | — |
| 2 | 469 | 611 | False | — | — | — |
| 3 | 853 | 915 | False | — | — | — |
| 4 | 945 | 1201 | True | 1.000 | 1.800 | — |


**(b) Gerçek-onset (862) konumu:** aday 3 İÇİNDE [853-915] (son_ok=False, kb=None)


**(c) İçerik örnekleri (gt-2, gt, gt+4) — credit_content.satirlar ilk 8 satır:**

- kare 860 (`c_00860.png`): ['山', 'b', 'シスミ', 'Senden ve benden']

- kare 862 (`c_00862.png`): ['326', 'Senden ve benden']

- kare 866 (`c_00866.png`): ['金ib rye', '2']


**(d) Scroll istatistiği (gt±10, stride=2):** n=10 örnek-çift, oran(dy>3&corr≥.85)=0.0, dy_medyan=0.0


**(e) Ön-teşhis etiketi:** `SON_ERISIM_KURBANI` — gt aday[853-915] içinde ama son_ok=False (SON_ERISIM=0.82'ye takıldı, içerik hiç ölçülmedi)


_(hedef görev: T4; işleme süresi 9.7 sn)_


---


## ÖZET

İşlenen: 29 film   Bekleyen (kare eksik): 2 film   (toplam hata: 31)


| Etiket | Film sayısı | Hedef görev |
|---|---|---|
| SCROLL_GEC_BASLADI | 0 | — |
| SON_ERISIM_KURBANI | 3 | T4 |
| ICERIK_REDDI | 4 | T6 |
| KUTU_YOK | 12 | T4, T6 |
| ERKEN_METIN | 7 | T5 |
| DIGER | 3 | ?? (ters-yönlü yanlış-pozitif, T4/T5/T6 dışı — ayrı ele alınmalı), T4, T5 |

### Film → etiket → hedef görev (ayrıntı)

| Film | karar | gt | pred | sapma | etiket | hedef |
|---|---|---|---|---|---|---|
| 1925-1028-1-0000-90-1_POTEMKİN_ZIRHLISI | yanlis_kare | 1133 | 1133 | 0 | DIGER | T5 |
| 1940-0026-1-0000-00-1_KNUTE_ROICKNE | yanlis_kare | 1146 | 1131 | -15 | ERKEN_METIN | T5 |
| 1978-0227-1-0000-00-1_TAKKELİ_MELEK | yanlis_kare | 588 | 905 | 317 | KUTU_YOK | T4 |
| 1979-0208-1-0000-00-1_TESS | yanlis_kare | 1074 | 1037 | -37 | ERKEN_METIN | T5 |
| 1981-0253-1-0000-00-1_YÜREKTEN_SEVMEK | yanlis_kare | 722 | 697 | -25 | ERKEN_METIN | T5 |
| 1988-0361-1-0000-00-1_DOĞUM_GÜNÜN_KUTLU_OLSUN_MAR | yanlis_kredi_var | 816 | -1 | None | KUTU_YOK | T6 |
| 1988-0780-1-0000-00-1_İKİ_KAFADAR | yanlis_kare | 1036 | 969 | -67 | ERKEN_METIN | T5 |
| 1989-0476-1-0000-00-1_VANYA_DAYI | yanlis_kredi_var | 904 | -1 | None | KUTU_YOK | T6 |
| 1989-0624-1-0000-00-1_DÖNÜŞÜ_OLMAYAN_NEHİR | yanlis_kredi_yok | -1 | 1125 | None | DIGER | ?? (ters-yönlü yanlış-pozitif, T4/T5/T6 dışı — ayrı ele alınmalı) |
| 1989-0955-1-0000-00-1_ÖLDÜRME_ZAMANI | yanlis_kredi_var | 1137 | -1 | None | ICERIK_REDDI | T6 |
| 1992-0455-1-0000-00-1_MELEKLERİ_GÖRMEK_İSTEDİM | yanlis_kredi_var | 934 | -1 | None | ICERIK_REDDI | T6 |
| 1993-0435-1-0000-00-1_SEN_TOM_SAWYER_DEĞİLSİN | yanlis_kredi_var | 805 | -1 | None | KUTU_YOK | T6 |
| 1995-0363-1-0000-00-1_KÜÇÜK_SİMBA_DÜNYA_KUPASIN | yanlis_kredi_var | 1035 | -1 | None | KUTU_YOK | T6 |
| 1996-0325-1-0000-00-1_KIZIL_HAYAT | yanlis_kare | 964 | 901 | -63 | ERKEN_METIN | T5 |
| 1999-0403-1-0000-00-1_PRENSESİN_AŞKI | yanlis_kare | 1046 | 1083 | 37 | KUTU_YOK | T4 |
| 2000-0323-1-0000-00-1_6 | yanlis_kare | 434 | 589 | 155 | KUTU_YOK | T4 |
| 2000-0491-1-0000-00-1_PARDAYYAN | yanlis_kare | 1034 | 1089 | 55 | KUTU_YOK | T4 |
| 2002-9173-1-0000-00-1_ROBOCOP_KARA_ADALET | yanlis_kredi_var | 1088 | -1 | None | KUTU_YOK | T6 |
| 2003-9136-1-0000-00-1_HARİKA_KÖPEK_5 | yanlis_kare | 737 | 613 | -124 | ERKEN_METIN | T5 |
| 2004-9131-1-0000-00-1_YALNIZ_SAVAŞÇI | yanlis_kare | 1097 | 907 | -190 | ERKEN_METIN | T5 |
| 2005-9162-1-0000-00-1_DİPTEKİLER | yanlis_kare | 416 | 619 | 203 | KUTU_YOK | T4 |
| 2006-9139-1-0000-90-1_TAKTİKLER_SAVAŞI | yanlis_kredi_var | 651 | -1 | None | ICERIK_REDDI | T6 |
| 2008-9046-1-0000-88-1_MEVLANA_AŞKIN_DANSI | yanlis_kare | 754 | 755 | 1 | DIGER | T4 |
| 2008-9066-1-0000-00-1_MESLEĞE_DÖNÜŞ | yanlis_kare | 373 | 693 | 320 | SON_ERISIM_KURBANI | T4 |
| 2011-9224-1-0000-88-1_KANDAHAR | yanlis_kredi_var | 964 | -1 | None | KUTU_YOK | T6 |
| 2017-1081-1-0000-50-0_KARAVAN | yanlis_kare | 577 | 759 | 182 | SON_ERISIM_KURBANI | T4 |
| 2023-1047-1-0000-90-1_GELECEK_GÜNLER | yanlis_kare | 672 | 763 | 91 | KUTU_YOK | T4 |
| 2023-1224-1-0000-56-1_ARKADAŞIMIN_EVİ_NEREDE | yanlis_kredi_var | 925 | -1 | None | ICERIK_REDDI | T6 |
| 2025-1112-1-0000-56-1_İNİŞLİ_ÇIKIŞLI_BİR_ÖYK | yanlis_kare | 862 | 951 | 89 | SON_ERISIM_KURBANI | T4 |

### BEKLIYOR (kare klasörü eksik/<50 png)

- 1975-2246-1-0000-72-0_DERSU_UZALA
- 2019-1091-1-0000-70-0_SAKLI_GERÇEKLER

_Toplam işlem süresi: 243 sn_

