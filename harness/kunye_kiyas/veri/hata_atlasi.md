# Hata Atlası — 31 hatanın kanıt-bazlı teşhisi (Görev 3 / T3)

Üretim: `hata_atlasi.py`  GT kaynağı: `veri/dogrulama_sonuc.json` (karar != "dogru", 31 film)

Salt-okunur girdi: `tespit_v5` (credit_onset.py) değiştirilmedi. Bu atlas Görev 4/5/6'nın tasarım kararlarının kanıt tabanıdır.

---

## 1940-0026-1-0000-00-1_KNUTE_ROICKNE

**GT:** karar=`yanlis_kare`  gercek_onset=`1146`  **v5(şimdi):** tahmin=`1117`  yöntem=`kutu+içerik`  sapma=`-29`

v5 notları: aday=5 seçilen=[1117-1201] kb=1.00 joint=1.50


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


**(e) Ön-teşhis etiketi:** `ERKEN_METIN` — tahmin=1117 < gt=1146 (koşu başı kredi-dışı metin erken tetiklemiş; gt'yi içeren aday içerik-eşiğini geçmesine rağmen daha erken bir aday kazandı)


_(hedef görev: T5; işleme süresi 28.1 sn)_


---

## 1979-0208-1-0000-00-1_TESS

**GT:** karar=`yanlis_kare`  gercek_onset=`1074`  **v5(şimdi):** tahmin=`1037`  yöntem=`kutu+içerik`  sapma=`-37`

v5 notları: aday=1 seçilen=[1037-1199] kb=1.00 joint=1.50


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


_(hedef görev: T5; işleme süresi 13.3 sn)_


---

## 1981-0253-1-0000-00-1_YÜREKTEN_SEVMEK

**GT:** karar=`yanlis_kare`  gercek_onset=`722`  **v5(şimdi):** tahmin=`697`  yöntem=`kutu+scroll+içerik`  sapma=`-25`

v5 notları: aday=1 seçilen=[697-1179] kb=1.00 joint=1.79


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


_(hedef görev: T5; işleme süresi 16.2 sn)_


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


_(hedef görev: T6; işleme süresi 12.9 sn)_


---

## 1989-0624-1-0000-00-1_DÖNÜŞÜ_OLMAYAN_NEHİR

**GT:** karar=`yanlis_kredi_yok`  gercek_onset=`-1`  **v5(şimdi):** tahmin=`1125`  yöntem=`kutu+scroll+içerik`  sapma=`None`

v5 notları: aday=3 seçilen=[1125-1191] kb=1.00 joint=1.76


**(a) Aday listesi (seri["adaylar"]):**

| # | kare_a | kare_b | son_ok | kb | joint | roller |
|---|---|---|---|---|---|---|
| 0 | 29 | 99 | False | — | — | — |
| 1 | 745 | 775 | False | — | — | — |
| 2 | 1125 | 1191 | True | 1.000 | 1.760 | — |


**(b)-(d):** GT kredi_yok(-1) — gerçek-onset yok, konum/içerik/scroll penceresi tanımsız (atlandı).


**(e) Ön-teşhis etiketi:** `DIGER` — GT kredi_yok(-1) ama v5 kredi_var dedi — ters yönlü yanlış-pozitif, 6 etiketten hiçbiri tam uymuyor


_(hedef görev: ?? (ters-yönlü yanlış-pozitif, T4/T5/T6 dışı — ayrı ele alınmalı); işleme süresi 15.3 sn)_


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


_(hedef görev: T6; işleme süresi 16.0 sn)_


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


_(hedef görev: T6; işleme süresi 15.6 sn)_


---

## 1996-0325-1-0000-00-1_KIZIL_HAYAT

**GT:** karar=`yanlis_kare`  gercek_onset=`964`  **v5(şimdi):** tahmin=`901`  yöntem=`kutu+scroll+içerik`  sapma=`-63`

v5 notları: aday=3 seçilen=[901-1183] kb=1.00 joint=1.80


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


_(hedef görev: T5; işleme süresi 15.8 sn)_


---

## 2000-0323-1-0000-00-1_6

**GT:** karar=`yanlis_kare`  gercek_onset=`434`  **v5(şimdi):** tahmin=`557`  yöntem=`kutu+scroll+içerik`  sapma=`123`

v5 notları: aday=3 seçilen=[557-1195] kb=1.00 joint=1.80


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


_(hedef görev: T4; işleme süresi 14.4 sn)_


---

## 2003-9136-1-0000-00-1_HARİKA_KÖPEK_5

**GT:** karar=`yanlis_kare`  gercek_onset=`737`  **v5(şimdi):** tahmin=`613`  yöntem=`kutu+scroll+içerik`  sapma=`-124`

v5 notları: aday=5 seçilen=[613-1195] kb=1.00 joint=1.80


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


_(hedef görev: T5; işleme süresi 16.3 sn)_


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


_(hedef görev: T6; işleme süresi 16.8 sn)_


---

## 2008-9046-1-0000-88-1_MEVLANA_AŞKIN_DANSI

**GT:** karar=`yanlis_kare`  gercek_onset=`754`  **v5(şimdi):** tahmin=`733`  yöntem=`kutu+scroll+içerik`  sapma=`-21`

v5 notları: aday=4 seçilen=[733-1191] kb=1.00 joint=1.80


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


**(e) Ön-teşhis etiketi:** `ERKEN_METIN` — tahmin=733 < gt=754 (koşu başı kredi-dışı metin erken tetiklemiş; gt'yi içeren aday içerik-eşiğini geçmesine rağmen daha erken bir aday kazandı)


_(hedef görev: T5; işleme süresi 9.6 sn)_


---

## 2008-9066-1-0000-00-1_MESLEĞE_DÖNÜŞ

**GT:** karar=`yanlis_kare`  gercek_onset=`373`  **v5(şimdi):** tahmin=`693`  yöntem=`kutu+scroll+içerik`  sapma=`320`

v5 notları: aday=2 seçilen=[693-1199] kb=1.00 joint=1.80


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


_(hedef görev: T4; işleme süresi 16.4 sn)_


---

## 2023-1047-1-0000-90-1_GELECEK_GÜNLER

**GT:** karar=`yanlis_kare`  gercek_onset=`672`  **v5(şimdi):** tahmin=`741`  yöntem=`kutu+içerik`  sapma=`69`

v5 notları: aday=2 seçilen=[741-1199] kb=1.00 joint=1.50


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


_(hedef görev: T4; işleme süresi 19.9 sn)_


---


## ÖZET

İşlenen: 14 film   Bekleyen (kare eksik): 17 film   (toplam hata: 31)


| Etiket | Film sayısı | Hedef görev |
|---|---|---|
| SCROLL_GEC_BASLADI | 0 | — |
| SON_ERISIM_KURBANI | 1 | T4 |
| ICERIK_REDDI | 2 | T6 |
| KUTU_YOK | 4 | T4, T6 |
| ERKEN_METIN | 6 | T5 |
| DIGER | 1 | ?? (ters-yönlü yanlış-pozitif, T4/T5/T6 dışı — ayrı ele alınmalı) |

### Film → etiket → hedef görev (ayrıntı)

| Film | karar | gt | pred | sapma | etiket | hedef |
|---|---|---|---|---|---|---|
| 1940-0026-1-0000-00-1_KNUTE_ROICKNE | yanlis_kare | 1146 | 1117 | -29 | ERKEN_METIN | T5 |
| 1979-0208-1-0000-00-1_TESS | yanlis_kare | 1074 | 1037 | -37 | ERKEN_METIN | T5 |
| 1981-0253-1-0000-00-1_YÜREKTEN_SEVMEK | yanlis_kare | 722 | 697 | -25 | ERKEN_METIN | T5 |
| 1988-0361-1-0000-00-1_DOĞUM_GÜNÜN_KUTLU_OLSUN_MAR | yanlis_kredi_var | 816 | -1 | None | KUTU_YOK | T6 |
| 1989-0624-1-0000-00-1_DÖNÜŞÜ_OLMAYAN_NEHİR | yanlis_kredi_yok | -1 | 1125 | None | DIGER | ?? (ters-yönlü yanlış-pozitif, T4/T5/T6 dışı — ayrı ele alınmalı) |
| 1989-0955-1-0000-00-1_ÖLDÜRME_ZAMANI | yanlis_kredi_var | 1137 | -1 | None | ICERIK_REDDI | T6 |
| 1995-0363-1-0000-00-1_KÜÇÜK_SİMBA_DÜNYA_KUPASIN | yanlis_kredi_var | 1035 | -1 | None | KUTU_YOK | T6 |
| 1996-0325-1-0000-00-1_KIZIL_HAYAT | yanlis_kare | 964 | 901 | -63 | ERKEN_METIN | T5 |
| 2000-0323-1-0000-00-1_6 | yanlis_kare | 434 | 557 | 123 | KUTU_YOK | T4 |
| 2003-9136-1-0000-00-1_HARİKA_KÖPEK_5 | yanlis_kare | 737 | 613 | -124 | ERKEN_METIN | T5 |
| 2006-9139-1-0000-90-1_TAKTİKLER_SAVAŞI | yanlis_kredi_var | 651 | -1 | None | ICERIK_REDDI | T6 |
| 2008-9046-1-0000-88-1_MEVLANA_AŞKIN_DANSI | yanlis_kare | 754 | 733 | -21 | ERKEN_METIN | T5 |
| 2008-9066-1-0000-00-1_MESLEĞE_DÖNÜŞ | yanlis_kare | 373 | 693 | 320 | SON_ERISIM_KURBANI | T4 |
| 2023-1047-1-0000-90-1_GELECEK_GÜNLER | yanlis_kare | 672 | 741 | 69 | KUTU_YOK | T4 |

### BEKLIYOR (kare klasörü eksik/<50 png)

- 1925-1028-1-0000-90-1_POTEMKİN_ZIRHLISI
- 1975-2246-1-0000-72-0_DERSU_UZALA
- 1978-0227-1-0000-00-1_TAKKELİ_MELEK
- 1988-0780-1-0000-00-1_İKİ_KAFADAR
- 1989-0476-1-0000-00-1_VANYA_DAYI
- 1992-0455-1-0000-00-1_MELEKLERİ_GÖRMEK_İSTEDİM
- 1993-0435-1-0000-00-1_SEN_TOM_SAWYER_DEĞİLSİN
- 1999-0403-1-0000-00-1_PRENSESİN_AŞKI
- 2000-0491-1-0000-00-1_PARDAYYAN
- 2002-9173-1-0000-00-1_ROBOCOP_KARA_ADALET
- 2004-9131-1-0000-00-1_YALNIZ_SAVAŞÇI
- 2005-9162-1-0000-00-1_DİPTEKİLER
- 2011-9224-1-0000-88-1_KANDAHAR
- 2017-1081-1-0000-50-0_KARAVAN
- 2019-1091-1-0000-70-0_SAKLI_GERÇEKLER
- 2023-1224-1-0000-56-1_ARKADAŞIMIN_EVİ_NEREDE
- 2025-1112-1-0000-56-1_İNİŞLİ_ÇIKIŞLI_BİR_ÖYK

_Toplam işlem süresi: 226 sn_

