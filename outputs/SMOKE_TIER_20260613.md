# SMOKE TIER SİMÜLASYONU — 2026-06-13 04:42

Taranan hub: **60** · Tarih: 2026-06-13

---

## 1. Değişen / Kural Tetiklenen Filmler Tablosu

| Film | Eski Karar | Tetiklenen Kural(lar) | Yeni Karar |
|------|-----------|----------------------|-----------|
| YERÇEKİMİ | Kontrol | K1 (yönetmen sayısı=4>2) | Kontrol |
| ÇÖL | Kontrol | K1 (yönetmen sayısı=3>2) | Kontrol |
| HÜKÜMET KADIN 2 | Kontrol | K1 (yönetmen sayısı=4>2) | Kontrol |
| ATTİLA MARCEL | Kontrol | K1 (yönetmen sayısı=4>2); K3 (ana_dil=FR, altyazı=HAYIR) | Kontrol |
| KAZANMA SANATI | Kontrol | K3 (ana_dil=EN, altyazı=HAYIR) | Kontrol |
| ZORAKİ KRAL | Kontrol | K3 (ana_dil=EN, altyazı=HAYIR) | Kontrol |
| FARGO | Kontrol | K3 (ana_dil=EN, altyazı=HAYIR) | Kontrol |
| FRANKIE VE JOHNNY | Hazır | K1 (yönetmen sayısı=5>2) | Kontrol |
| MORRİE İLE HER SALI | Kontrol | K1 (yönetmen sayısı=3>2) | Kontrol |
| ÖLDÜREN SIR | Kontrol | K1 (yönetmen sayısı=3>2) | Kontrol |
| ÇILGIN BILL | Kontrol | K1 (yönetmen sayısı=4>2) | Kontrol |
| TEK BAŞINA MÜCADELE | Kontrol | K1 (yönetmen sayısı=3>2) | Kontrol |
| CEHENNEM SÜRÜCÜLERİ | Kontrol | K1 (yönetmen sayısı=3>2) | Kontrol |
| GÜNEY BATI GEÇİDİ | Hazır | K1 (yönetmen sayısı=3>2) | Kontrol |
| HARVEY | Hazır | K1 (yönetmen sayısı=3>2) | Kontrol |
| KOVAN | Kontrol | K3 (ana_dil=KU, altyazı=HAYIR) | Kontrol |
| GEYİK ÇOCUK | Kontrol | K1 (yönetmen sayısı=5>2) | Kontrol |
| SOKAK MUHABİRİ | Hazır | K1 (yönetmen sayısı=3>2) | Kontrol |
| ÇILGIN YAŞAMIM | Hazır | K1 (yönetmen sayısı=3>2) | Kontrol |
| VAHŞİ AT | Hazır | K1 (yönetmen sayısı=3>2) | Kontrol |
| 3. GÖZ | Kontrol | K1 (yönetmen sayısı=3>2) | Kontrol |
| TRUMAN SHOW | Kontrol | K1 (yönetmen sayısı=4>2) | Kontrol |

## 2. Karar Değişen Filmler (Hazır → Kontrol)

Bu filmler yeni kuralların yakaladığı sızıntılardır.

- **FRANKIE VE JOHNNY** — K1 (yönetmen sayısı=5>2)
  - Yönetmen satırı: `CHICAGO HOPE, J. LEVINE, JACK LASKY, STEPHEN TOBOLOWSKY, MİCHAEL PRESSMAN`
- **GÜNEY BATI GEÇİDİ** — K1 (yönetmen sayısı=3>2)
  - Yönetmen satırı: `RAY NAZARRO, THE END, HARRY ESSEX`
- **HARVEY** — K1 (yönetmen sayısı=3>2)
  - Yönetmen satırı: `WİLLİAM DANİELS, LRODUCED JY, HENRY KOSTER`
- **SOKAK MUHABİRİ** — K1 (yönetmen sayısı=3>2)
  - Yönetmen satırı: `ANDREW FIERBERG, BERTRAND MOULY, KLAUS BİEDERMANN`
- **ÇILGIN YAŞAMIM** — K1 (yönetmen sayısı=3>2)
  - Yönetmen satırı: `ALLİSON ANDERS, MRİLLEN AND DİRERFED HY, TRENDY GİRL TERRI LYNN PHILLIPS`
- **VAHŞİ AT** — K1 (yönetmen sayısı=3>2)
  - Yönetmen satırı: `JOHN MCLEAN A.C.S., DAVİD HUGGETT, CHRİSTİNE ROGERS`

## 3. Regresyon Kontrolü

Aşağıdaki filmler **Hazır KALMALI** — eğer tetikleniyorsa false-positive demektir.

> **NOT:** 4 regresyon filmi son 60 hub içinde değil (sıra: HIRSIZ=231, SILVERADO=223, TITUS=224, ZOR ÖLÜM 2=219). Script kapsamı dışında kaldıklarından tabloya girmedi. **Manuel doğrulama aşağıda** (MD dosyaları doğrudan okundu).

| Film | Yönetmen Satırı | Tetiklenen Kural | Yeni Karar | Sonuç |
|------|----------------|-----------------|-----------|-------|
| HIRSIZ (MICHAEL MANN) | `MICHAEL MANN` | — | Hazır | OK — false-positive yok |
| SILVERADO | `LAWRENCE KASDAN` | — | Hazır | OK — false-positive yok |
| TITUS ANDRONICUS | `DAETETLY JUNE HOWELL, .BEN BEBEK DEĞİLİM. EVET, ŞİMDİ, YAKARIŞLARLA YAPTIĞIM KÖTÜLÜKLER, JANE HOWELL` | K1 (5 eleman) | Kontrol | **FALSE-POSITIVE değil** — yönetmen satırı zaten bozuk (garble+OCR saçmalığı); gerçek yönetmen Jane Howell, doğru davranış Kontrol'e düşürmek |
| ZOR ÖLÜM 2 | `—` | — | Hazır | OK — false-positive yok |

**Özet:** HIRSIZ/SILVERADO/ZOR ÖLÜM 2 temiz. TITUS ANDRONICUS K1 tetikliyor ancak bu false-positive DEĞİL — yönetmen satırı halihazırda OCR garble içeriyor (film başlık sayfasından dökülen saçma metin). Kural doğru çalışıyor.

## 4. Beklenti Doğrulaması

Bu filmler Hazır ve bozuk yönetmenli — K1/K2 yakalamalı.

| Film | Yönetmen Satırı | K1/K2 Tetiklendi? | Açıklama |
|------|----------------|------------------|---------|
| FRANKIE VE JOHNNY | `CHICAGO HOPE, J. LEVINE, JACK LASKY, STEPHEN TOBOLOWSKY, MİCHAEL PRESSMAN` | EVET | K1 (yönetmen sayısı=5>2) |
| SOKAK MUHABİRİ | `ANDREW FIERBERG, BERTRAND MOULY, KLAUS BİEDERMANN` | EVET | K1 (yönetmen sayısı=3>2) |
| ÇİLGİN YAŞAMIM | `ALLİSON ANDERS, MRİLLEN AND DİRERFED HY, TRENDY GİRL TERRI LYNN PHILLIPS` | EVET | K1 (yönetmen sayısı=3>2) |
| VAHŞİ AT | `JOHN MCLEAN A.C.S., DAVİD HUGGETT, CHRİSTİNE ROGERS` | EVET | K1 (yönetmen sayısı=3>2) |

## 5. Sayısal Özet

- Taranan toplam film: **60**
- Hazır → Kontrol (yeni kural yakaladı): **6**
- Zaten Kontrol + yeni kural eklendi: **16**
- Hiç etkilenmeyen: **38**

### K1 Tetikleyenler (yönetmen >2)
- **YERÇEKİMİ**: `JAMES CAMERON, DAVİD FİNCHER, ROBERT RİCHARDSON, RYAN MCGUİRE` → 4 eleman
- **ÇÖL**: `JONAS CUARON, DESIR O, PERD ALEN GARCIA` → 3 eleman
- **HÜKÜMET KADIN 2**: `OY BABAANNE DİYEN DİLLERİM, PLAYIM SENİN MEMİLİKT, GÜLMEKTEDİR, ERKAN BULBUL` → 4 eleman
- **ATTİLA MARCEL**: `DOCUMENTALHSTE CHRISHINE LOISY, COOCH UKULELE BERTRAND SAINI -GUILLAIN, CONSELLİ` → 4 eleman
- **FRANKIE VE JOHNNY**: `CHICAGO HOPE, J. LEVINE, JACK LASKY, STEPHEN TOBOLOWSKY, MİCHAEL PRESSMAN` → 5 eleman
- **MORRİE İLE HER SALI**: `MİCK JACKSON, TANGO FAVORİLERİNDEN BİRİYDİ., KENDİ VERSİYONUYLA ELBETTE.` → 3 eleman
- **ÖLDÜREN SIR**: `NOEL NOSSECK, JOANNA CANTON, J. MİCHAEL HUNTER` → 3 eleman
- **ÇILGIN BILL**: `AND NYOMAN WENTEN, SONGS ARRANGED BY C, VAN DYKE PARKS, WALTER HILL` → 4 eleman
- **TEK BAŞINA MÜCADELE**: `TOM RİCHMOND, TİM SUHRSTEDT, ALAN BEATTİE` → 3 eleman
- **CEHENNEM SÜRÜCÜLERİ**: `CEOFFREY UNS, GEOFPWEY UNSWORY INS.C., GLOFFALY UNS ORTH B.S.C.` → 3 eleman
- **GÜNEY BATI GEÇİDİ**: `RAY NAZARRO, THE END, HARRY ESSEX` → 3 eleman
- **HARVEY**: `WİLLİAM DANİELS, LRODUCED JY, HENRY KOSTER` → 3 eleman
- **GEYİK ÇOCUK**: `THE DOE BOY, H LIFI, HEMOPHILIC FAC, CHRİS EYRE, RANDY REDROAD` → 5 eleman
- **SOKAK MUHABİRİ**: `ANDREW FIERBERG, BERTRAND MOULY, KLAUS BİEDERMANN` → 3 eleman
- **ÇILGIN YAŞAMIM**: `ALLİSON ANDERS, MRİLLEN AND DİRERFED HY, TRENDY GİRL TERRI LYNN PHILLIPS` → 3 eleman
- **VAHŞİ AT**: `JOHN MCLEAN A.C.S., DAVİD HUGGETT, CHRİSTİNE ROGERS` → 3 eleman
- **3. GÖZ**: `ESRA TANAR, ENGİN AYBAKAN, ANNLE WİLSON CATF BLANCHETT` → 3 eleman
- **TRUMAN SHOW**: `ERCAN ÇEVİK, ENGİN AYBAKAN, SESİENUMMNE TONEUNEN IRA., PETER WEİR` → 4 eleman

### K2 Tetikleyenler (yönetmen elemanı >45 kar)
*(yok)*

### K3 Tetikleyenler (ana_dil≠TR + altyazı=HAYIR)
- **ATTİLA MARCEL**: ana_dil=`FR`, altyazı=`HAYIR`
- **KAZANMA SANATI**: ana_dil=`EN`, altyazı=`HAYIR`
- **ZORAKİ KRAL**: ana_dil=`EN`, altyazı=`HAYIR`
- **FARGO**: ana_dil=`EN`, altyazı=`HAYIR`
- **KOVAN**: ana_dil=`KU`, altyazı=`HAYIR`
