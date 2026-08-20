# Nash / LeBron / Jordan — 29 video birebir karşılaştırma

> Bu rapor ground truth değildir. Motorlar arası ortaklık güçlü bir tanıdır; tek motordaki satır hem gerçek ek içerik hem hata olabilir.

## Yönetici kararı

Bu 29 filmlik yatakta **Nash her zaman çalışan ana okuyucu olmaya en uygun
motor**. Tek başına kusursuz değil; fakat başarı oranı, süre, bellek ve benzersiz
satır kapsaması birlikte değerlendirildiğinde en iyi tabanı veriyor.

- Nash: 29/29 tamamlandı, 2.531 benzersiz satır, 372,4 sn.
- Güvenli LeBron: 26/29 tamamlandı, 1.931 benzersiz satır, 1.870,4 sn;
  üç Magic master `COKME` kapısında açık ARIZA oldu.
- Jordan: 28/29 tamamlandı, 2.356 benzersiz satır, 4.745,7 sn; bir filmde
  27B CUDA OOM (`cag_output16`).
- Nash, film süre toplamında LeBron’dan **5,02×**, Jordan’dan **12,74×** hızlı.
- En az bir başka motorun desteklediği satır/saniye: Nash **4,33**,
  LeBron **0,69**, Jordan **0,33**.

Önerilen görev ayrımı:

1. Nash/Paddle 2 fps ana havuzda her zaman çalışır.
2. Magic master bağımsız ikinci tanık olarak korunur; fakat metinsiz sahneler
   ağır okuyucuya verilmeden önce elenir.
3. Ağır okuyucu her filme zorunlu ana yol değil, düşük güven/yazı sistemi ve
   gerçek içerik farkı için hedefli tanık olur.
4. Jordan yazım/çok-alfabe hakemi olarak değerlidir; mevcut 27B maliyeti ve
   tekrar üretimi nedeniyle ana okuyucu olmamalı.

## “İyi DeepSeek kayboldu mu?” denetimi

**Hayır; model diskte duruyor. Taşıma sırasında runtime sözleşmesi eksik
taşınmış.** Eski üretim ve kule yolu arasındaki gerçek fark:

| Özellik | Eski Ollama üretimi | Kule içi Transformers |
|---|---|---|
| Model | `deepseek-ocr:latest`, F16 GGUF 3.3B, 6.687 GB | DeepSeek-OCR BF16 ağırlık, 6.3 GB |
| Prompt | `Free OCR.` | `<image>\nFree OCR.` (eşdeğer model konvansiyonu) |
| Bant | 1100 px / 120 px bindirme | aynı |
| Üretim tavanı | `num_predict=2048` | indirilen model kodunda `max_new_tokens=8192` |
| Bağlam | `num_ctx=8192` | uzak model kodunun davranışı |
| Çağrı zaman aşımı | 300 sn | yok |
| Gözlenen VRAM | yaklaşık 8,6 GiB | yaklaşık 16,4 GiB |

Sınırsız yerel koşu iki büyük master’da 8192-token üretimine uzadı; biri
450 saniyede kontrollü durduruldu. Kaynak koduna dokunmadan uygulanan
1024-token/EOS/pad güvenlik sarmalayıcısı ilk beş başarılı filmde sınırsız
çıktıyla **5/5 satır satır aynı** sonuç verdi ve 29 filmi tamamladı.

Eski Ollama ağırlığı ayrıca aynı sorunlu `cag_output07` Magic master’ının 18
bandında doğrudan çalıştırıldı:

- soğuk toplam 53,8 sn; ilk bant 44,4 sn ve bunun 26,0 sn’si model yükleme;
- sonraki 17 sıcak bant toplam 9,34 sn;
- sıcak medyan 0,50 sn/bant, en yüksek 0,77 sn/bant;
- 18/18 çağrı `stop` nedeniyle normal bitti.

Bu ölçüm, geçmişteki hızın yanlış hatırlanmadığını doğruluyor. Eski model boş
bantlarda `1/2/3` ve HTML uydurabildiği için Paddle piksel kalkanı ve yapısal
süzgeç yine zorunlu. Doğru onarım yeni model aramak değil: eski
`2048/8192/timeout/stop` sözleşmesini kuleye taşımak veya aynı GGUF/llama
çalıştırıcısını kulenin sahip olduğu bir alt süreç haline getirmek.
Ham 18 bant yanıtları ve süreleri:
[`DEEPSEEK_OLLAMA_ESKI_OUTPUT07_PROBE_20260818.json`](DEEPSEEK_OLLAMA_ESKI_OUTPUT07_PROBE_20260818.json).

## Elle/görselle doğrulanan kalite vakaları

- **Türkçe — `cag_output14`:** Jordan 15 satırla isim yazımında en temiz.
  Nash 18 satır ve LeBron 20 satır; ikisi de Jordan’ın kaçırdığı gerçek üç
  satırlık `15 Temmuz...` kapanış açıklamasını yakaladı. Nash’te iki aksan
  kaybı, LeBron’da iki kısa gürültü satırı ve birkaç Türkçe karakter hatası var.
- **Azerbaycanca — `cag_output15`:** Jordan 25 satırla yazımı en iyi; Nash 24
  satırla içeriğin çoğunu buluyor ama aksan kaybediyor. Magic master çok sayıda
  metinsiz film sahnesi taşıdığı için LeBron 184 sn harcayıp yalnız 2 satır buldu.
- **Kiril — `cag_output20`:** LeBron ve Jordan arasında 37 satır eşleşiyor.
  Nash 50 satır üretmiş görünse de tamamı Kiril görüntünün Latin tanıyıcıyla
  okunmuş bozuk transliterasyonları; gerçek başarı sayılmamalı.
- **Farsça — `cag_output23`:** Magic gerçek kredi akışını taşıyor; LeBron/Jordan
  sırasıyla 278/254 benzersiz satır üretiyor. Nash’in 22 satırı Latin-model
  gürültüsü. Arapça fallback, `8 satırdan azsa çalış` kapısı yüzünden yanlış
  biçimde tetiklenmemiş.
- **Yoğun Türkçe scroll — `cag_output26`:** Nash 280 ham/275 benzersiz,
  LeBron 242/242, Jordan 308 ham/241 benzersiz. Jordan’ın 67 tekrarı yüksek ham
  sayının ek kapsama olmadığını gösteriyor. Nash 26,7 sn ile en hızlı.
- **Temiz ortak kontrol — `ks_klip01`:** N/L/J benzersiz sayıları 52/48/51;
  Nash↔Jordan kapsaması %88,5/%90,2, LeBron↔Jordan %97,9/%92,2. Üç motor
  basit/temiz içerikte birbirini güçlü biçimde doğruluyor.

## Açık kusurlar ve doğrudan düzeltme sırası

1. Nash script fallback kapısı yalnız satır sayısına bakmamalı. Düşük medyan
   tanıma güveni de tetik olmalı; mevcut yerel `eslav_PP-OCRv5_mobile_rec`
   Kiril için, Arabic model Farsça/Arapça için hedefli çalışmalı.
2. LeBron yerel adaptörü 8192 ve sınırsız süreden çıkarılmalı; üretim adayı
   2048 tavan + doğru EOS/pad + ayrı yükleme/çağrı zaman sınırıdır. 1024 kalite
   alt sınırı ilk beş filmde kayıpsız olsa da tüm alfabelerde etiketli kapı
   olmadan üretim varsayılanı yapılmamalı.
3. Magic’in gerçek kazanımları nedeniyle legacy LeBron’a dönülmemeli. Bunun
   yerine master içindeki metinsiz footage ağır modele gitmeden elenmeli.
4. Jordan’ın 27B OOM’u ve 207 tekrar satırı kapanmadan ana yol yapılmamalı.

Legacy LeBron/Magic tam çözünürlüklü PNG’ler, yan yana önizlemeler ve ayrı
yorum: [`../../lebron_james/out/master_kiyas_20260818/RAPOR.md`](../../lebron_james/out/master_kiyas_20260818/RAPOR.md).

## Kapsam ve yöntem

- Film: **29**, fuzzy eşik: **0.9**
- `raw_exact`: yalnız boşlukları toparlanmış karakter dizisi birebir.
- `normalized_exact`: case/aksan/noktalama farkı kaldırıldıktan sonra birebir.
- `fuzzy`: kalan benzersiz satırlarda film içi maksimum eşleme.
- Tüm satırlar, eşleşmeler ve yalnız-motor listeleri: `NASH_LEBRON_JORDAN_KIYAS_20260818.json`

## Genel çıktı ve maliyet

| Motor | Durum | Ham satır | Benzersiz | Tekrar | Film süre toplamı | Medyan | En yüksek |
|---|---|---:|---:|---:|---:|---:|---:|
| Nash | OKUNDU:29 | 2583 | 2531 | 52 | 372.4 sn | 11.1 sn | 26.7 sn |
| Lebron | ARIZA:3, OKUNDU:26 | 1931 | 1931 | 0 | 1870.4 sn | 45.4 sn | 191.5 sn |
| Jordan | ARIZA:1, OKUNDU:28 | 2564 | 2356 | 207 | 4745.7 sn | 147.8 sn | 400.5 sn |

## İkili örtüşme

| Çift | Normalize birebir | Ek fuzzy | Toplam eşleşme | İlk motor kapsama | İkinci motor kapsama |
|---|---:|---:|---:|---:|---:|
| Nash ↔ Lebron | 978 | 109 | 1087 | %42.9 | %56.3 |
| Nash ↔ Jordan | 1184 | 183 | 1367 | %54.0 | %58.0 |
| Lebron ↔ Jordan | 955 | 97 | 1052 | %54.5 | %44.7 |

## En az bir başka motor tarafından desteklenen satırlar

Bu ölçüm doğruluk değildir; iki farklı mimarinin aynı satırı okumasını destek sinyali sayar. İzole satır gerçek ek içerik de OCR hatası da olabilir.

| Motor | Desteklenen | İzole | Destek oranı |
|---|---:|---:|---:|
| Nash | 1613 | 918 | %63.7 |
| Lebron | 1299 | 632 | %67.3 |
| Jordan | 1576 | 780 | %66.9 |

## Film bazında

| Film | N/L/J benzersiz | N↔L | N↔J | L↔J | N/L/J süre (sn) |
|---|---:|---:|---:|---:|---:|
| cag_output01 | 73/18/45 | 12 (%16.4/%66.7) | 31 (%42.5/%68.9) | 10 (%55.6/%22.2) | 9.8/35.0/73.9 |
| cag_output02 | 93/0/60 | 0 (%0.0/—) | 26 (%28.0/%43.3) | 0 (—/%0.0) | 9.6/23.1/109.7 |
| cag_output03 | 57/15/29 | 10 (%17.5/%66.7) | 25 (%43.9/%86.2) | 0 (%0.0/%0.0) | 8.9/26.4/153.0 |
| cag_output04 | 97/50/81 | 33 (%34.0/%66.0) | 63 (%64.9/%77.8) | 24 (%48.0/%29.6) | 9.4/27.1/118.2 |
| cag_output05 | 101/95/81 | 52 (%51.5/%54.7) | 39 (%38.6/%48.1) | 50 (%52.6/%61.7) | 10.9/42.1/115.4 |
| cag_output06 | 138/49/104 | 24 (%17.4/%49.0) | 58 (%42.0/%55.8) | 20 (%40.8/%19.2) | 11.1/41.7/157.8 |
| cag_output07 | 37/27/25 | 21 (%56.8/%77.8) | 23 (%62.2/%92.0) | 22 (%81.5/%88.0) | 13.8/169.6/249.6 |
| cag_output08 | 32/33/30 | 27 (%84.4/%81.8) | 30 (%93.8/%100.0) | 27 (%81.8/%90.0) | 14.4/150.9/243.6 |
| cag_output09 | 127/57/117 | 43 (%33.9/%75.4) | 110 (%86.6/%94.0) | 41 (%71.9/%35.0) | 16.8/49.5/280.2 |
| cag_output10 | 74/70/73 | 57 (%77.0/%81.4) | 63 (%85.1/%86.3) | 61 (%87.1/%83.6) | 13.7/69.1/257.0 |
| cag_output11 | 27/14/13 | 11 (%40.7/%78.6) | 13 (%48.1/%100.0) | 11 (%78.6/%84.6) | 8.2/45.4/104.2 |
| cag_output12 | 61/47/55 | 36 (%59.0/%76.6) | 48 (%78.7/%87.3) | 35 (%74.5/%63.6) | 14.2/56.0/255.4 |
| cag_output13 | 51/82/54 | 14 (%27.5/%17.1) | 18 (%35.3/%33.3) | 41 (%50.0/%75.9) | 26.1/69.2/251.5 |
| cag_output14 | 18/20/15 | 18 (%100.0/%90.0) | 15 (%83.3/%100.0) | 15 (%75.0/%100.0) | 5.9/17.4/35.6 |
| cag_output15 | 24/2/25 | 1 (%4.2/%50.0) | 21 (%87.5/%84.0) | 1 (%50.0/%4.0) | 15.3/184.0/214.0 |
| cag_output16 | 33/43/0 | 17 (%51.5/%39.5) | 0 (%0.0/—) | 0 (%0.0/—) | 12.6/37.9/150.0 |
| cag_output17 | 88/0/53 | 0 (%0.0/—) | 39 (%44.3/%73.6) | 0 (—/%0.0) | 9.6/16.9/94.8 |
| cag_output18 | 47/0/48 | 0 (%0.0/—) | 36 (%76.6/%75.0) | 0 (—/%0.0) | 11.5/23.8/130.6 |
| cag_output19 | 74/46/92 | 4 (%5.4/%8.7) | 32 (%43.2/%34.8) | 2 (%4.3/%2.2) | 16.5/94.3/90.4 |
| cag_output20 | 50/69/78 | 0 (%0.0/%0.0) | 0 (%0.0/%0.0) | 37 (%53.6/%47.4) | 9.2/48.6/147.8 |
| cag_output21 | 136/67/98 | 43 (%31.6/%64.2) | 79 (%58.1/%80.6) | 45 (%67.2/%45.9) | 10.2/28.3/96.9 |
| cag_output22 | 68/65/65 | 61 (%89.7/%93.8) | 59 (%86.8/%90.8) | 56 (%86.2/%86.2) | 6.2/16.1/57.5 |
| cag_output23 | 22/278/254 | 0 (%0.0/%0.0) | 0 (%0.0/%0.0) | 23 (%8.3/%9.1) | 19.1/191.5/400.5 |
| cag_output24 | 57/25/49 | 16 (%28.1/%64.0) | 44 (%77.2/%89.8) | 20 (%80.0/%40.8) | 10.0/64.3/97.2 |
| cag_output25 | 250/220/232 | 197 (%78.8/%89.5) | 176 (%70.4/%75.9) | 155 (%70.5/%66.8) | 12.8/82.6/163.3 |
| cag_output26 | 275/242/241 | 174 (%63.3/%71.9) | 73 (%26.5/%30.3) | 94 (%38.8/%39.0) | 26.7/123.0/294.5 |
| cag_output27 | 58/65/68 | 39 (%67.2/%60.0) | 39 (%67.2/%57.4) | 64 (%98.5/%94.1) | 9.4/26.8/95.4 |
| cag_output28 | 311/184/220 | 133 (%42.8/%72.3) | 161 (%51.8/%73.2) | 151 (%82.1/%68.6) | 23.5/94.4/248.7 |
| ks_klip01 | 52/48/51 | 44 (%84.6/%91.7) | 46 (%88.5/%90.2) | 47 (%97.9/%92.2) | 6.7/15.4/59.0 |

## Film bazında yalnız-motor örnekleri

### cag_output01

- Yalnız Nash (Lebron kıyası, 61): AHORM · Wichits · PLATTE · XASE · Scott BRADY · MIS · … (+55)
- Yalnız Lebron (Nash kıyası, 6): Universal · Belmont · Kansas City · TOWN CMDTNG · ROB · LAHOMA
- Yalnız Nash (Jordan kıyası, 42): AHORM · Wichits · PLATTE · XASE · MIS · Marguerite · … (+36)
- Yalnız Jordan (Nash kıyası, 14): Universal · Marguerite CHAPMAN · in · KANSAS RAIDERS · COLOR BY TECHNICOLOR · Story and Screenplay by ROBERT L. RICHARDS · … (+8)
- Yalnız Lebron (Jordan kıyası, 8): Wichita · Belmont · Kansas City · TOWN CMDTNG · ROB · Canadian · … (+2)
- Yalnız Jordan (Lebron kıyası, 35): Audie MURPHY · Brian DONLEVY · Marguerite CHAPMAN · Scott BRADY · in · KANSAS RAIDERS · … (+29)

### cag_output02

- Yalnız Nash (Lebron kıyası, 93): CENTUR · Clifton Webb · Myrna Loy · Twentieth Centuy-Fex Presents · Jeanne Crain · aLoy · … (+87)
- Yalnız Lebron (Nash kıyası, 0): —
- Yalnız Nash (Jordan kıyası, 67): aLoy · oraJoy · Tebb · the · Crain · resents · … (+61)
- Yalnız Jordan (Nash kıyası, 34): 20th · FOX · in · Cheaper by the Dozen · in in · eaper by · … (+28)
- Yalnız Lebron (Jordan kıyası, 0): —
- Yalnız Jordan (Lebron kıyası, 60): 20th · CENTURY · FOX · Twentieth Century-Fox Presents · Clifton Webb · Jeanne Crain · … (+54)

### cag_output03

- Yalnız Nash (Lebron kıyası, 47): COLMEIA · COLNBIA · COUNIDIA PIP · GUNFURY · COLUMBIA PICTURES CORPORATION · COPPOIONTOMGMLIN TY COLUMBIA PICTUPES-SORPOPATION · … (+41)
- Yalnız Lebron (Nash kıyası, 5): JEROME THOMAS AND · JAMES SWEENEY AND · JACK SORRICE · MICHAEL MARGARET · Film Editor
- Yalnız Nash (Jordan kıyası, 32): COLMEIA · COLNBIA · COUNIDIA PIP · COPPOIONTOMGMLIN TY COLUMBIA PICTUPES-SORPOPATION · NTEPNATLONAL CODYRIGHT SEOUREO - JLL RISHITS RESERVED · WUTH · … (+26)
- Yalnız Jordan (Nash kıyası, 4): COLUMBIA · PRESENTS · COPYRIGHT MCMXLIII BY COLUMBIA PICTURES CORPORATION · INTERNATIONAL COPYRIGHT SECURED • ALL RIGHTS RESERVED
- Yalnız Lebron (Jordan kıyası, 15): Art Director · Film Editors · Set Decorator · Assistant Director · Sound Engineer · Musical Director · … (+9)
- Yalnız Jordan (Lebron kıyası, 29): COLUMBIA · COLUMBIA PICTURES CORPORATION · PRESENTS · GUN FURY · COPYRIGHT MCMXLIII BY COLUMBIA PICTURES CORPORATION · INTERNATIONAL COPYRIGHT SECURED • ALL RIGHTS RESERVED · … (+23)

### cag_output04

- Yalnız Nash (Lebron kıyası, 64): pour l'Echafaud · Dialogue de · Ascenseur pour LEchafaud · A pré- adaptation de l'auteur ) · d' après le roman de · Noël Calef · … (+58)
- Yalnız Lebron (Nash kıyası, 17): Louis Malle · sur l'Edda faud · Veran Vannu · Charles Deimer · François Jouve · of · … (+11)
- Yalnız Nash (Jordan kıyası, 34): 1Assistant réalisateur. · Alain Fraissé · Accessoiriste · Jean Rabier · Jacques Martin · Régisseur général · … (+28)
- Yalnız Jordan (Nash kıyası, 18): Louis Malle · et · 1er Assistant réalisateur . . Alain Fraissé · Cameraman . . . . . André Villard · 1erAssistant opérateur. . . . . Jean Rabier · Photographe . . . . . Jean-Louis Castelli · … (+12)
- Yalnız Lebron (Jordan kıyası, 26): sur l'Edda faud · Veran Vannu · Charles Deimer · François Jouve · of · Caméraman · … (+20)
- Yalnız Jordan (Lebron kıyası, 57): pour l’Echafaud · Dialogue de · d’ après le roman de · Noël Calef · Ascenseur pour l’Echafaud · ( pré- adaptation de l’auteur ) · … (+51)

### cag_output05

- Yalnız Nash (Lebron kıyası, 49): Uaersal · Uawveral · PERER · HANWERRLM · MINULC · PEVER. · … (+43)
- Yalnız Lebron (Nash kıyası, 43): IN · THE · BRIDES · OF · available · PEELON · … (+37)
- Yalnız Nash (Jordan kıyası, 62): Uaersal · Uawveral · Universal · International · PERER · HANWERRLM · … (+56)
- Yalnız Jordan (Nash kıyası, 42): Universal International · A HAMMER FILM PRODUCTION · A · IN · OF · THE BRIDES OF DRACULA · … (+36)
- Yalnız Lebron (Jordan kıyası, 45): Universal · International · THE · BRIDES · Also · available · … (+39)
- Yalnız Jordan (Lebron kıyası, 31): Universal International · A HAMMER FILM PRODUCTION · A · THE BRIDES · are fictitious and any similarity to the names character or history of · any person is entirely accidental and unintentional · … (+25)

### cag_output06

- Yalnız Nash (Lebron kıyası, 114): DEE · SANDRa · GOULET · ROBCRF · ROBERT · WILLIaMS · … (+108)
- Yalnız Lebron (Nash kıyası, 25): ALEX JENKINS · HAYDEN ROSE · JUL JACKSON · YILMAZ · 73. Philip Unlaine · Russell Herty · … (+19)
- Yalnız Nash (Jordan kıyası, 80): ROBCRF · Parayla mutlu olunmaz · Yine de zengin olmak isterdim · iğneyle kuyu kazmaktansa · Çalışıp çabalamaktansa · oturmak isterdim · … (+74)
- Yalnız Jordan (Nash kıyası, 46): A · IN CHARGE OF PRODUCTION · I'D · HERMIONE · JILL JACKSON · Art Directors · … (+40)
- Yalnız Lebron (Jordan kıyası, 29): ALEX JENKINS · HAYDEN ROSE · JUL JACKSON · Ama tercih edersin eminim · YILMAZ · 73. Philip Unlaine · … (+23)
- Yalnız Jordan (Lebron kıyası, 84): A · IN CHARGE OF PRODUCTION · SANDRA · DEE · ROBERT · GOULET · … (+78)

### cag_output07

- Yalnız Nash (Lebron kıyası, 16): cruelles, Angélique avait enin retrouvé son · Méditerranée. · "le Rescator", l'homme le plus redouté en · Après des aventures dramatiques et · mari devant Dieu: Joffrey de Peyrac devenu · urama · … (+10)
- Yalnız Lebron (Nash kıyası, 6): Un bonheur tant espéré semblait alors possible, mais le corsaire renégat Escramville réussit à enlever Angélique et à mettre le feu au navire de Peyrac. · MICHIBIRE · DAMY AND DANDY · COPYRIGHT © MCMLVI-MCMXLVII BY OPÉRA MONTAGNE · Copyright © MCMLVI - MCMLVIII © Orpheus · ET
- Yalnız Nash (Jordan kıyası, 14): cruelles, Angélique avait enin retrouvé son · Méditerranée. · "le Rescator", l'homme le plus redouté en · Après des aventures dramatiques et · mari devant Dieu: Joffrey de Peyrac devenu · urama · … (+8)
- Yalnız Jordan (Nash kıyası, 2): COPYRIGHT © MCMLVI-MCMLVIII BY OPERA MOBILE · ET
- Yalnız Lebron (Jordan kıyası, 5): Un bonheur tant espéré semblait alors possible, mais le corsaire renégat Escramville réussit à enlever Angélique et à mettre le feu au navire de Peyrac. · MICHIBIRE · DAMY AND DANDY · COPYRIGHT © MCMLVI-MCMXLVII BY OPÉRA MONTAGNE · Copyright © MCMLVI - MCMLVIII © Orpheus
- Yalnız Jordan (Lebron kıyası, 3): COPYRIGHT © MCMLVI-MCMLVIII BY OPERA MOBILE · PRODUIT PAR · FRANÇOIS CHAVANE

### cag_output08

- Yalnız Nash (Lebron kıyası, 5): COPYRIGHT DDINO DE LAURENTIS CORPORATION MCMLXXVY ALL RIGHTS RESERVED · COPYRIGMT COINO DE LAURENTIIS · CORPORATION MCMLIEVIL ALL RIGHTS RESERVEL · as Poker Jenny · PANCHO KOHNER
- Yalnız Lebron (Nash kıyası, 6): Also stunning · CLIMBING WALLS · KING RICHARD · as Robert Lenny · PUNCHO KOHLER · image
- Yalnız Nash (Jordan kıyası, 2): COPYRIGMT COINO DE LAURENTIIS · CORPORATION MCMLIEVIL ALL RIGHTS RESERVEL
- Yalnız Jordan (Nash kıyası, 0): —
- Yalnız Lebron (Jordan kıyası, 6): Also stunning · CLIMBING WALLS · KING RICHARD · as Robert Lenny · PUNCHO KOHLER · image
- Yalnız Jordan (Lebron kıyası, 3): COPYRIGHT ©DINO DE LAURENTIIS CORPORATION MCMLXXVII. ALL RIGHTS RESERVED · as Poker Jenny · PANCHO KOHNER

### cag_output09

- Yalnız Nash (Lebron kıyası, 84): UNE PRODUCTION · SOCIÉTÉ FRANÇAISE DE PRODUCTION · LES FILMS DU CARROSSE · SEDIF S.A. - T.F.1 · CATHERINE DENEUVE · GÉRARD DEPARDIEU · … (+78)
- Yalnız Lebron (Nash kıyası, 14): beim: M. Berth. in Frankreich · 39ᵉ Rue de Dantzig · WH-TAONSTELLE · GL/Paris · 39ᵉ Rue des Champs-Elysées · Lw. Lazareff Paris · … (+8)
- Yalnız Nash (Jordan kıyası, 17): CHAMBRE DES DEPUTES · Vanves · Nachste · zan · sta · Lw.Lazarell Paris · … (+11)
- Yalnız Jordan (Nash kıyası, 7): ET · 38 Rue de Dantzig · GL/Paris · Lw.Lazarett Paris · Nächste GFP Dienststelle · PRÉSIDENT KRÜGER · … (+1)
- Yalnız Lebron (Jordan kıyası, 16): WH-TAONSTELLE · 39ᵉ Rue des Champs-Elysées · Lw. Lazareff Paris · Nächste · GFP · Dienststelle · … (+10)
- Yalnız Jordan (Lebron kıyası, 76): UNE PRODUCTION · LES FILMS DU CARROSSE · SEDIF S.A. - T.F.1 · SOCIÉTÉ FRANÇAISE DE PRODUCTION · CATHERINE DENEUVE · GÉRARD DEPARDIEU · … (+70)

### cag_output10

- Yalnız Nash (Lebron kıyası, 17): VITTORIO GASSMAN · RUGGERO RAIMONDI · GERALDINE · CHAPLIN · FANNY ARDANT · PIERRE ARDITI · … (+11)
- Yalnız Lebron (Nash kıyası, 13): ROBERT MANUEL · MARTINE KELLY · et · À monte ni c’est ni tôt · donnî oue cruaure · bonne ou cruaure · … (+7)
- Yalnız Nash (Jordan kıyası, 11): GERALDINE · CHAPLIN · UN ROMAN · LA VIE EST · ROBERT · MANUEL · … (+5)
- Yalnız Jordan (Nash kıyası, 10): GERALDINE CHAPLIN · LA VIE EST UN ROMAN · ROBERT MANUEL · MARTINE KELLY · et · [ Edition A.R.T. Music France .Disques TREMA ] · … (+4)
- Yalnız Lebron (Jordan kıyası, 9): À monte ni c’est ni tôt · donnî oue cruaure · bonne ou cruaure · CATHY DEDREDIAN · À L'ILLUSTRATION BRUNO-MICHAEL · BURGUNDE LENOUD · … (+3)
- Yalnız Jordan (Lebron kıyası, 12): VITTORIO GASSMAN · RUGGERO RAIMONDI · GERALDINE CHAPLIN · FANNY ARDANT · PIERRE ARDITI · dans · … (+6)

### cag_output11

- Yalnız Nash (Lebron kıyası, 16): LioT · BicTek · TTT · Tek · Big · BLOTEL · … (+10)
- Yalnız Lebron (Nash kıyası, 3): RICHARD MYCART · THIS CHIPPED AND FURNISHED BY · THE CHOPPED UP FARMED UP
- Yalnız Nash (Jordan kıyası, 14): LioT · BicTek · TTT · Tek · Big · BLOTEL · … (+8)
- Yalnız Jordan (Nash kıyası, 0): —
- Yalnız Lebron (Jordan kıyası, 3): RICHARD MYCART · THIS CHIPPED AND FURNISHED BY · THE CHOPPED UP FARMED UP
- Yalnız Jordan (Lebron kıyası, 2): G.W. BAILEY · MUSIC COMPOSED AND PERFORMED BY

### cag_output12

- Yalnız Nash (Lebron kıyası, 25): MICHEL GALABRU · JEAN LEFEBVRE · PERRIN · DANS · FRANCIS · YVES MIRANDE · … (+19)
- Yalnız Lebron (Nash kıyası, 11): YVES MIRANDE ET · ÉDITIONS POUR ENSEIGNE · ET · MAHINE · MASTER · HMS · … (+5)
- Yalnız Nash (Jordan kıyası, 13): BREILLAT · MARIE.HELENE · YVES MIRANDE · 13IS RC · 1815R · MAXin'S · … (+7)
- Yalnız Jordan (Nash kıyası, 7): MARIE.HELENE BREILLAT · YVES MIRANDE ET · ET · IRENNE LERICHE · 1815 RC · M M · … (+1)
- Yalnız Lebron (Jordan kıyası, 12): MARIE. HELENE · BREILLAT · ÉDITIONS POUR ENSEIGNE · MAHINE · MASTER · HMS · … (+6)
- Yalnız Jordan (Lebron kıyası, 20): MICHEL GALABRU · JEAN LEFEBVRE · MARIE.HELENE BREILLAT · FRANCIS · PERRIN · DANS · … (+14)

### cag_output13

- Yalnız Nash (Lebron kıyası, 37): حسين محجوب · محسن رمضانى · سلمه فيضى · الهام شريفى · مصطفى بافرونى · بهزادرفيعي · … (+31)
- Yalnız Lebron (Nash kıyası, 68): شی · سلمه فیضی · الهام شریفی · مصطفی بافرونی · بهزاد فریمی · عکس · … (+62)
- Yalnız Nash (Jordan kıyası, 33): سلمه فيضى · الهام شريفى · مصطفى بافرونى · بهزادرفيعي · سعيد عراقى · مكس · … (+27)
- Yalnız Jordan (Nash kıyası, 36): نجم خفا · محمسن رمضانی · سلمه فیضی · الهام شریفی · بهداد فیعی · مصطفی بافرونی · … (+30)
- Yalnız Lebron (Jordan kıyası, 41): شی · بهزاد فریمی · ماجد نهل کاشتی · طراح جیره بردازی · طراح صدا، صداگذاری و نزکریب صدا · طراح صدا، صداگذاری و ترکيب صدا · … (+35)
- Yalnız Jordan (Lebron kıyası, 13): نجم خفا · حسین محجوب · محسن رمضانی · محمسن رمضانی · بهداد فیعی · متنی صحیح · … (+7)

### cag_output14

- Yalnız Nash (Lebron kıyası, 0): —
- Yalnız Lebron (Nash kıyası, 2): es · EMI
- Yalnız Nash (Jordan kıyası, 3): BU FİLMDE GEÇEN OLAYLAR · 15 TEMMUZ ŞEHİTLERİMİZ VE GAZİLERİMİZİN · KAHRAMANLIKLARINDAN ESİNLENEREK KURGULANMIŞTIR.
- Yalnız Jordan (Nash kıyası, 0): —
- Yalnız Lebron (Jordan kıyası, 5): es · EMI · BU FİLMDE GEÇEN OLAYLAR · 15 TEMMUZ ŞEHİTLERİMİZ VE GAZİLERİMİZİN · KAHRAMANLIKLARINDAN ESİNLENEREK KURGULANMIŞTIR.
- Yalnız Jordan (Lebron kıyası, 0): —

### cag_output15

- Yalnız Nash (Lebron kıyası, 23): Azarbaa · Madanvya · Mdniyyt v Turizm Nazirliyi · Azrbaycan Respublikası · ZƏRBAYCANFİLM · Azrbaycan Respublikası Mdniyyt v Turizm Nazirliyi · … (+17)
- Yalnız Lebron (Nash kıyası, 1): İGOR SOHOR
- Yalnız Nash (Jordan kıyası, 3): Azarbaa · Madanvya · Thmin Rafaella
- Yalnız Jordan (Nash kıyası, 4): Təhminə Rafaela · İlqar Səfət · İlqar Səfərov filmində · İÇƏRİ ŞƏHƏR
- Yalnız Lebron (Jordan kıyası, 1): İGOR SOHOR
- Yalnız Jordan (Lebron kıyası, 24): Azərbaycan Respublikası · Mədəniyyət və Turizm Nazirliyi · AZƏRBAYCANFİLM · Azərbaycan Respublikası Mədəniyyət və Turizm Nazirliyi · C.Cabbarlı adına "Azərbaycanfilm" kinostudiyası · İdeya müəllifi · … (+18)

### cag_output16

- Yalnız Nash (Lebron kıyası, 16): FOX SEARCHLIGHT PICTURES Presents · Association with · In Association with EVEREST ENTERTAINMENT · EVEREST ENTERTAINMENT · /NEXT WEDNESDA · A GROUNDSWELL / NEXT WEDNESDAY Production · … (+10)
- Yalnız Lebron (Nash kıyası, 26): Babam nerede? · Hani ve whiskers · MELANIE LYNSKEY · İyi. · İyiydi. · -Beğnemdim. · … (+20)
- Yalnız Nash (Jordan kıyası, 33): FOX SEARCHLIGHT PICTURES Presents · Association with · In Association with EVEREST ENTERTAINMENT · EVEREST ENTERTAINMENT · /NEXT WEDNESDA · A GROUNDSWELL / NEXT WEDNESDAY Production · … (+27)
- Yalnız Jordan (Nash kıyası, 0): —
- Yalnız Lebron (Jordan kıyası, 43): BOBBY CANNAVALE · JEFFREY TAMBOR · Anne bugün kriket oynayabilir miyiz? · Babam nerede? · kitty · Hani ve whiskers · … (+37)
- Yalnız Jordan (Lebron kıyası, 0): —

### cag_output17

- Yalnız Nash (Lebron kıyası, 88): ANPÜFE · CHSALONU · Cevit Evl · KACeub · WEDYELIK ESYA · ZEYNEP TUĞÇE BAYAT · … (+82)
- Yalnız Lebron (Nash kıyası, 0): —
- Yalnız Nash (Jordan kıyası, 49): ANPÜFE · CHSALONU · Cevit Evl · KACeub · WEDYELIK ESYA · KA Çeyiz Evi · … (+43)
- Yalnız Jordan (Nash kıyası, 14): CEM GELİNOĞLU · GÖKHAN KIRAÇ · YÖN. ZERRİN SÜMER · YAPIMCISI · DİLEK APARTMANI · YAPIM · … (+8)
- Yalnız Lebron (Jordan kıyası, 0): —
- Yalnız Jordan (Lebron kıyası, 53): CEM GELİNOĞLU · GÖKHAN KIRAÇ · ZEYNEP TUĞÇE BAYAT · GÜLSÜM ALKAN · ÜMİT YESİN · METİN YILDIZ · … (+47)

### cag_output18

- Yalnız Nash (Lebron kıyası, 47): Cenin · HiKAYEN · AC341 · A0341 · Selma ERGEÇ · Timuçin ESEN · … (+41)
- Yalnız Lebron (Nash kıyası, 0): —
- Yalnız Nash (Jordan kıyası, 11): Cenin · HiKAYEN · AC341 · A0341 · SEN · Ömer ÇALIKOĞLU · … (+5)
- Yalnız Jordan (Nash kıyası, 12): Senin HİKAYEN · Nevin SEREZLİ · İdil FIRAT · ve · Sanat Yönetmeni · Erkan ÖZDEM · … (+6)
- Yalnız Lebron (Jordan kıyası, 0): —
- Yalnız Jordan (Lebron kıyası, 48): Senin HİKAYEN · Timuçin ESEN · Selma ERGEÇ · Nevin SEREZLİ · Sait GENAY · Nevra SEREZLİ · … (+42)

### cag_output19

- Yalnız Nash (Lebron kıyası, 70): من لاشين · مساعد والاخراج · آمالى بمنسى · إيناس بكر · مصطفى ابو خشب · ٠مصود · … (+64)
- Yalnız Lebron (Nash kıyası, 42): إيـانـيـن كـرـتـر · مصطفى الـو كـتـب · عـمـر الـدونـي · فـنـكـي كـرـتـر · مـصـادـقـات مـنـتـاج · أحـمـد داوـد · … (+36)
- Yalnız Nash (Jordan kıyası, 42): من لاشين · آمالى بمنسى · مصطفى ابو خشب · ٠مصود · م،مصبود · فتحى عزت · … (+36)
- Yalnız Jordan (Nash kıyası, 60): إخراج · هان لاشين · أمالي بهنسي · إيتان بكر · مصطفى أبو حشيش · اماني بهنسي · … (+54)
- Yalnız Lebron (Jordan kıyası, 44): إيـانـيـن كـرـتـر · مصطفى الـو كـتـب · عـمـر الـدونـي · فـنـكـي كـرـتـر · مـصـادـقـات مـنـتـاج · أحـمـد داوـد · … (+38)
- Yalnız Jordan (Lebron kıyası, 90): إخراج · هان لاشين · مساعد الإخراج · أمالي بهنسي · إيتان بكر · مصطفى أبو حشيش · … (+84)

### cag_output20

- Yalnız Nash (Lebron kıyası, 50): ANEKEAHAP LALbIKNR · TAKOH DAHUIPEEKOK · KPAEM MUPA · METHA THEL, · 4HHTH3A ANTMATHRA · HHHTHA AHTMATORA · … (+44)
- Yalnız Lebron (Nash kıyası, 69): КИНОСТУДИЯ · имени АЛЕКСАНДРА ДОВЖЕНКО · При участии фирм: · «АЛЬЯНС ФИЛЬМОПРОДУКЦИОН» · «РЕГИНА ЦИГЛЕР ФИЛЬМОПРОДУКЦИОН» · «ЦДФ» (ФРГ) · … (+63)
- Yalnız Nash (Jordan kıyası, 50): ANEKEAHAP LALbIKNR · TAKOH DAHUIPEEKOK · KPAEM MUPA · METHA THEL, · 4HHTH3A ANTMATHRA · HHHTHA AHTMATORA · … (+44)
- Yalnız Jordan (Nash kıyası, 78): КИНОСТУДИЯ · имени АЛЕКСАНДРА ДОВЖЕНКО · При участии фирм: · «АЛЬЯНС ФИЛЬМОПРОДУКЦИОН» · «РЕГИНА ЦИГЛЕР ФИЛЬМОПРОДУКЦИОН» · (Западный Берлин) · … (+72)
- Yalnız Lebron (Jordan kıyası, 32): ДИЛЕХАН ЖД/ЖАНКЛЕНДЖ · ТДКОН ДАЙМЕБЕКДЖ · В СИЛАМЕ · КАРЕНА ГЕБИДЖАНА · ПЕСТИЙ ПЕСТ · ПЕТИК ПЕТ, · … (+26)
- Yalnız Jordan (Lebron kıyası, 41): (Западный Берлин) · Творческое объединение · «ТАЛИСМАН» · БАЯРТО ДАМБАЕВ · АЛЕКСАНДР САСЫКОВ · ДОСХАН ЖОЛЖАКСЫНОВ · … (+35)

### cag_output21

- Yalnız Nash (Lebron kıyası, 93): ETUDIOS · RPO · councidyr · jkoly conodencal · Lcareiy cdinodental · coancdrneal · … (+87)
- Yalnız Lebron (Nash kıyası, 24): ASSOCIATED BRITISH FILM CORPORATION LTD · HIRIS ENGLAND · - SAND · - ANGLE · - MARGARET · - A CLIFF RICHARD · … (+18)
- Yalnız Nash (Jordan kıyası, 57): ETUDIOS · RPO · councidyr · jkoly conodencal · Lcareiy cdinodental · coancdrneal · … (+51)
- Yalnız Jordan (Nash kıyası, 19): OF · LAURIE PETERS · All characters and events in this film are fictitious, and any similarity to persons either living or dead is purely coincidental. · RHESIE · AND NICHOLAS PHIPPS · RICHARD EARLEY · … (+13)
- Yalnız Lebron (Jordan kıyası, 22): ASSOCIATED BRITISH FILM CORPORATION LTD · HIRIS ENGLAND · - SAND · - ANGLE · - MARGARET · - A CLIFF RICHARD · … (+16)
- Yalnız Jordan (Lebron kıyası, 53): OF · ASSOCIATED BRITISH PICTURE CORPORATION LTD. · HERTS. ENGLAND · LAURIE PETERS · All characters and events in this film are fictitious, and any similarity to persons either living or dead is purely coincidental. · SANDY · … (+47)

### cag_output22

- Yalnız Nash (Lebron kıyası, 7): APPEARANCE · OTHERS IN ORDER OF · DIRECTOR OF · CINEMATOGRAPHY · EDITOR & · WRITTEN, PRODUCED & · … (+1)
- Yalnız Lebron (Nash kıyası, 4): OTHERS IN ORDER OF APPEARANCE: · Marllee Porter · EDITOR & DIRECTOR OF CINEMATOGRAPHY · WRITTEN, PRODUCED & DIRECTED BY
- Yalnız Nash (Jordan kıyası, 9): Young Edison: · George Brengel · Marty Schaljo · APPEARANCE · Old Edison: · OTHERS IN ORDER OF · … (+3)
- Yalnız Jordan (Nash kıyası, 6): Young Edison: Marty Schaljo · Old Edison: George Brengel · OTHERS IN ORDER OF APPEARANCE: · Brad Adnen · Jim Loisen · Craig Marston
- Yalnız Lebron (Jordan kıyası, 9): Young Edison: · Marty Schaljo · Old Edison: · George Brengel · Brad Adrien · Jim Loisell · … (+3)
- Yalnız Jordan (Lebron kıyası, 9): Young Edison: Marty Schaljo · Old Edison: George Brengel · Brad Adnen · Jim Loisen · Craig Marston · EDITOR & · … (+3)

### cag_output23

- Yalnız Nash (Lebron kıyası, 22): eigilag · lagl9a · lag19aw · gil · S1901 · lapil · … (+16)
- Yalnız Lebron (Nash kıyası, 278): طراحی کتاب · رضا رجبی عبد · روح حسین دبلی · طال عیب نازل · طے جیہن اپنے۔ · غورڈ ڈیٹل · … (+272)
- Yalnız Nash (Jordan kıyası, 22): eigilag · lagl9a · lag19aw · gil · S1901 · lapil · … (+16)
- Yalnız Jordan (Nash kıyası, 254): داستان · هیس! آیدل · با · آرزو محمد پور وند · کارگردان · مهدی برزگر · … (+248)
- Yalnız Lebron (Jordan kıyası, 255): طراحی کتاب · رضا رجبی عبد · روح حسین دبلی · طال عیب نازل · طے جیہن اپنے۔ · غورڈ ڈیٹل · … (+249)
- Yalnız Jordan (Lebron kıyası, 231): داستان · هیس! آیدل · با · آرزو محمد پور وند · کارگردان · مهدی برزگر · … (+225)

### cag_output24

- Yalnız Nash (Lebron kıyası, 41): Bölümün · I. Bölümün sonu · CI26 · müzik daruşmanı · MURAT TUNCAY · C126 · … (+35)
- Yalnız Lebron (Nash kıyası, 9): CJ 32 · CJ26 · İŞİK · makvaj · مقابل جيش · RABIA ERAY · … (+3)
- Yalnız Nash (Jordan kıyası, 13): Bölümün · I. Bölümün sonu · CI26 · müzik daruşmanı · C126 · ARİ ÖNGCNSEN · … (+7)
- Yalnız Jordan (Nash kıyası, 5): müzik danışmanı · ışık · negatif kesim · RABİA ERAT · HİLMI MAKAV
- Yalnız Lebron (Jordan kıyası, 5): CJ 32 · CJ26 · makvaj · مقابل جيش · RABIA ERAY
- Yalnız Jordan (Lebron kıyası, 29): müzik danışmanı · MURAT TUNCAY · prodüksiyon amiri · RAGIP TARANÇ · yönetim yardımcısı · YÜCEL ÖZGÜR · … (+23)

### cag_output25

- Yalnız Nash (Lebron kıyası, 53): KiğIL · igs · Enyso · SLéeN · excLusive · DESIGN · … (+47)
- Yalnız Lebron (Nash kıyası, 23): YÖNETMEN · SONER CANER · YAPIMCI · HASAN KARUL · KiQIL · göztük · … (+17)
- Yalnız Nash (Jordan kıyası, 74): Cennetin çocuklarına... · Dünyanın, çocukluğu habersizce çalınan bütün çocuklarına, · igs · BLACK · FASHION · GULL-AY · … (+68)
- Yalnız Jordan (Nash kıyası, 56): YÖNETMEN · SONER CANER · YAPIMCI · HASAN KARUL · ips · 1938 · … (+50)
- Yalnız Lebron (Jordan kıyası, 65): Dünyanın, çocukluğu habersizce çalınan bütün çocuklarına, · Cennetin çocuklarına... · KiQIL · göztük · Üstası · BLACK · … (+59)
- Yalnız Jordan (Lebron kıyası, 77): ips · KİĞİLİ · 1938 · imzae · gözlük ustası · BLACK FASHION · … (+71)

### cag_output26

- Yalnız Nash (Lebron kıyası, 101): Idari Yapimci · Görüntü Yönetmeni · Senaryo · Finans Koordinatörü · CESUR TAŞ · HANDE CANPOLAT · … (+95)
- Yalnız Lebron (Nash kıyası, 68): SADİ CANPOLAT · \| Yönetmen \| DOĞAN ÖMİT KARACA \| · \| Yapımcı \| MEHMET CANPOLAT · \| Senaryo \| YUSUF REHA ALP \| · \| Genel Koordinatör \| HANDE CANPOLAT \| · \| İdari Yapımcı \| CESUR TAŞ \| · … (+62)
- Yalnız Nash (Jordan kıyası, 202): Idari Yapimci · Görüntü Yönetmeni · Senaryo · Finans Koordinatörü · CESUR TAŞ · HANDE CANPOLAT · … (+196)
- Yalnız Jordan (Nash kıyası, 168): SADİ CANPOLAT · Yönetmen DOĞAN ÜMİT KARACA · Yapımcı MEHMET CANPOLAT · Senaryo YUSUF REHA ALP · Genel Koordinatör HANDE CANPOLAT · İdari Yapımcı CESUR TAŞ · … (+162)
- Yalnız Lebron (Jordan kıyası, 148): \| Müziğin \| SEÇİL AKIN \| · KEMALETTİN OSMANLI \| · \| Derin \| MELİKE İPEK YALOVA \| · \| Faruk Bedir \| ENGİN BENLI \| · \| Mohd Piyami \| OSMAN ALBAYRAK \| · \| Turan \| MERT DOĞAN \| · … (+142)
- Yalnız Jordan (Lebron kıyası, 147): Görsel Yönetmen VEYSEL TEKŞAHİN · Yönetmen Yapımcısı DOĞAN ÜMİT KARACA · Yapımcı SADI CANPOLAT · Müziyen SEÇİL AKIN · Kurgu Yönetmeni KEMALETTİN OSMANLI · Berin MELİKE TEK YALOVA · … (+141)

### cag_output27

- Yalnız Nash (Lebron kıyası, 19): John Rourke · SAM DOBBINS · Captain Mallory · Captain Chavez · Assassin · CHRIS NIELSEN · … (+13)
- Yalnız Lebron (Nash kıyası, 26): Produced by · John Rourke JAMES RUSSO · Laurence McCoy WILLIAM McNAMARA · Dickerson JEFFREY H. WINCOTT · Leesu NICOLE BILDERBACK · Yang FRANCOIS CHAU · … (+20)
- Yalnız Nash (Jordan kıyası, 19): John Rourke · SAM DOBBINS · Captain Mallory · Captain Chavez · Assassin · CHRIS NIELSEN · … (+13)
- Yalnız Jordan (Nash kıyası, 29): Produced by · Jefferson · ERNE HUDSON · John Rourke JAMES RUSSO · Laurence McCoy WILLIAM McNAMARA · Dickerson JEFFREY H. WINCOTT · … (+23)
- Yalnız Lebron (Jordan kıyası, 1): Nurse CHA RIESSE LAVELLE
- Yalnız Jordan (Lebron kıyası, 4): Jefferson · ERNE HUDSON · Muse CHARLESSE LAVELLE · College Student ALEX JEE

### cag_output28

- Yalnız Nash (Lebron kıyası, 178): Elisabeth · SOPHIE MARCEAU · Charles · Constance · LIA WILLIAMS · DOMINIQUE BELCOURT · … (+172)
- Yalnız Lebron (Nash kıyası, 51): Elizabeth SOPHIE MARCEAU · Louisa DOMINIQUE BELCOURT · Lori Clare JOSS ACKLAND · Susannah WOLF KAHLER · Amy ANNABEL GILES · Robert Ames JOHN FLANAGAN · … (+45)
- Yalnız Nash (Jordan kıyası, 150): Elisabeth · SOPHIE MARCEAU · Charles · Constance · John Taylbr · Louisa · … (+144)
- Yalnız Jordan (Nash kıyası, 59): Elizabeth SOPHIE MARCEAU · Louisa DOMINIQUE BELCOURT · Lord Clare JOSS ACKLAND · Susannah WOLF KAHLER · Amy ANNABEL GILES · Robert Ames JOHN FLANAGAN · … (+53)
- Yalnız Lebron (Jordan kıyası, 33): Hannah VALERIE MINIFIE · Mrs Maidment DIANA PAYAN · Carlo JOHN HODGKINSON · Dodds ANTHONY DUTTON · Dr Giddes HUGH WALTERS · Danceraster FRANK ROZELAAR-GREEN · … (+27)
- Yalnız Jordan (Lebron kıyası, 69): Stephen Dillane · Kevin Anderson · Lia Williams · Dominique Belcourt · Joss Ackland · Sally Dexter · … (+63)

### ks_klip01

- Yalnız Nash (Lebron kıyası, 8): executive producer · BET DECONATIOND · CASTING BY · GOUND · CAGTINO DY · OND ASBIBTANT DIRECTORB · … (+2)
- Yalnız Lebron (Nash kıyası, 4): CAPTION BY · 1ST ASSISTANT DIRECTOR · 2ND ASSISTANT DIRECTOR · SOUND EFFECT EDITOR
- Yalnız Nash (Jordan kıyası, 6): BET DECONATIOND · GOUND · CAGTINO DY · OND ASBIBTANT DIRECTORB · 16T AGBIBTANT DIREGTOR · OND AGGIGTANT DIRECTORG
- Yalnız Jordan (Nash kıyası, 5): 1ST ASSISTANT DIRECTOR · 2ND ASSISTANT DIRECTORS · SOUND EFFECTS EDITOR · COSTUME SUPERVISORS · DON SNYDER
- Yalnız Lebron (Jordan kıyası, 1): CAPTION BY
- Yalnız Jordan (Lebron kıyası, 4): executive producer · CASTING BY · COSTUME SUPERVISORS · DON SNYDER
