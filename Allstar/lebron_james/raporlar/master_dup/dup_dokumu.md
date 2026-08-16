# Master-PNG Duplikasyon Kusur Dökümü (Görev M3)

> Kaynak: `harness/master_dup/atlas.py` — `data/master_dup/masters/*/` (metrik.json + manifest.json) taranarak üretildi. Plan: `docs/MITAS_Master_Dup_Kok_Sebep_Plani_v1.md` (Görev M3).

## 1. Genel özet

- Toplam film (havuz): **112**
- Başarılı (OK, metrik hesaplanmış): **112**
- Başarısız/hatalı: **0**

## 2. dup_oran dağılımı

- Medyan: **0.0456**  ·  Ortalama: **0.0886**  ·  Maks: **0.6214**  ·  n=112

| dup_oran aralığı | film sayısı |
|---|---|
| [0.00, 0.01) | 36 |
| [0.01, 0.02) | 5 |
| [0.02, 0.05) | 17 |
| [0.05, 0.10) | 18 |
| [0.10, 0.20) | 22 |
| [0.20, 0.35) | 8 |
| [0.35, 0.50) | 5 |
| [0.50, 1.00] | 1 |

## 3. Kredisiz kontrol grubu vs kredi-var küme

- **Kredisiz** (gercek_onset=-1, son-240s pencere), n=29: dup_oran medyan=0.0735, ortalama=0.0819, maks=0.1803  ·  boy(H) ortalama=18778.0px  ·  kept_blocks ortalama=45.4
- **Kredi-var** (onset-15s pencere), n=83: dup_oran medyan=0.0357, ortalama=0.0909, maks=0.6214  ·  boy(H) ortalama=7327.0px  ·  kept_blocks ortalama=13.9
- Not: kredisiz pencere (son 240s, gerçek kredi kartı YOK -- sıradan sahne) boy/blok sayısında kredili kümeden belirgin sapma gösteriyorsa, bu "statik-kart-splitter"ın sıradan sahne kesmelerini kart sanıp aşırı böldüğüne işaret eder (bkz. §6 -- SON_CÜCE örneği tam olarak bu grup içinde).

## 4. Mod x strict_scroll_frac x boy tablosu

(Havuz-çapında referans scroll hızı: **66.02 px/kare** — boy-sağlığı hesabında kullanıldı.)

| mode | film sayısı | strict_scroll_frac min/med/max | boy(H) min/med/max px | ortalama dup_oran | canavar-boy sayısı |
|---|---|---|---|---|---|
| reading_runaware | 80 | 0.00/0.19/0.71 | 628/8300/36356 | 0.1187 | 0 |
| reading_runaware_passthrough | 32 | 0.77/0.90/1.00 | 824/5972/16276 | 0.0133 | 0 |

## 5. En kötü 15 film -- ayrıntı

### 1. 1998-0970-1-0000-00-1_BAŞKAN_VE_MARI

- dup_oran=**0.6214**  ·  blok_sayisi=138  ·  boy=[600, 6499]  ·  mode=reading_runaware  ·  strict_scroll_frac=0.15  ·  doku_kapsami=0.9279  ·  gercek_onset=1004
- **Hipotez(ler): H2** (birincil: H2)
  - blok ofsetleri çoğunlukla uzak (111/138 blok kendi span'inin 3.0x'inden uzak ofsetli, ort=2013.7px, cv=0.658) -> ardışık-olmayan kart tekrarı imzası

### 2. 1990-1068-1-0000-56-0_YAKIN_PLAN

- dup_oran=**0.4657**  ·  blok_sayisi=271  ·  boy=[512, 4963]  ·  mode=reading_runaware  ·  strict_scroll_frac=0.681  ·  doku_kapsami=0.9837  ·  gercek_onset=903
- **Hipotez(ler): H2** (birincil: H2)
  - blok ofsetleri çoğunlukla uzak (248/271 blok kendi span'inin 3.0x'inden uzak ofsetli, ort=1210.6px, cv=0.847) -> ardışık-olmayan kart tekrarı imzası

### 3. 2000-0477-1-0000-00-1_FUTBOLCU_PRENSES

- dup_oran=**0.4083**  ·  blok_sayisi=470  ·  boy=[600, 10328]  ·  mode=reading_runaware  ·  strict_scroll_frac=0.0899  ·  doku_kapsami=0.8372  ·  gercek_onset=1035
- **Hipotez(ler): H2** (birincil: H2)
  - blok ofsetleri çoğunlukla uzak (461/470 blok kendi span'inin 3.0x'inden uzak ofsetli, ort=3297.1px, cv=0.667) -> ardışık-olmayan kart tekrarı imzası

### 4. 1987-0232-1-0000-00-1_BAYAN_JULIE

- dup_oran=**0.3993**  ·  blok_sayisi=77  ·  boy=[636, 3728]  ·  mode=reading_runaware  ·  strict_scroll_frac=0.0  ·  doku_kapsami=1.0  ·  gercek_onset=997
- **Hipotez(ler): H2** (birincil: H2)
  - blok ofsetleri çoğunlukla uzak (74/77 blok kendi span'inin 3.0x'inden uzak ofsetli, ort=1661.4px, cv=0.529) -> ardışık-olmayan kart tekrarı imzası

### 5. 2008-9046-1-0000-88-1_MEVLANA_AŞKIN_DANSI

- dup_oran=**0.3986**  ·  blok_sayisi=129  ·  boy=[384, 12993]  ·  mode=reading_runaware  ·  strict_scroll_frac=0.0  ·  doku_kapsami=0.9382  ·  gercek_onset=754
- **Hipotez(ler): H2** (birincil: H2)
  - blok ofsetleri çoğunlukla uzak (71/129 blok kendi span'inin 3.0x'inden uzak ofsetli, ort=181.8px, cv=0.668) -> ardışık-olmayan kart tekrarı imzası

### 6. 1989-0476-1-0000-00-1_VANYA_DAYI

- dup_oran=**0.3818**  ·  blok_sayisi=353  ·  boy=[600, 11060]  ·  mode=reading_runaware  ·  strict_scroll_frac=0.0815  ·  doku_kapsami=0.5831  ·  gercek_onset=904
- **Hipotez(ler): H2** (birincil: H2)
  - blok ofsetleri çoğunlukla uzak (352/353 blok kendi span'inin 3.0x'inden uzak ofsetli, ort=3377.5px, cv=0.689) -> ardışık-olmayan kart tekrarı imzası

### 7. 1999-0407-1-0000-00-1_KÜÇÜK_KAHRAMAN

- dup_oran=**0.3293**  ·  blok_sayisi=204  ·  boy=[600, 22924]  ·  mode=reading_runaware  ·  strict_scroll_frac=0.1053  ·  doku_kapsami=0.7377  ·  gercek_onset=971
- **Hipotez(ler): H2** (birincil: H2)
  - blok ofsetleri çoğunlukla uzak (202/204 blok kendi span'inin 3.0x'inden uzak ofsetli, ort=737.3px, cv=0.49) -> ardışık-olmayan kart tekrarı imzası

### 8. 1993-0435-1-0000-00-1_SEN_TOM_SAWYER_DEĞİLSİN

- dup_oran=**0.3097**  ·  blok_sayisi=82  ·  boy=[600, 7364]  ·  mode=reading_runaware  ·  strict_scroll_frac=0.6667  ·  doku_kapsami=0.7374  ·  gercek_onset=805
- **Hipotez(ler): H2** (birincil: H2)
  - blok ofsetleri çoğunlukla uzak (75/82 blok kendi span'inin 3.0x'inden uzak ofsetli, ort=939.7px, cv=0.589) -> ardışık-olmayan kart tekrarı imzası

### 9. 1960-0021-1-0000-00-1_BÜYÜK_MÜCADELE

- dup_oran=**0.2727**  ·  blok_sayisi=91  ·  boy=[600, 4466]  ·  mode=reading_runaware  ·  strict_scroll_frac=0.0  ·  doku_kapsami=0.7392  ·  gercek_onset=988
- **Hipotez(ler): H2** (birincil: H2)
  - blok ofsetleri çoğunlukla uzak (88/91 blok kendi span'inin 3.0x'inden uzak ofsetli, ort=1352.2px, cv=0.6) -> ardışık-olmayan kart tekrarı imzası

### 10. 2010-9139-1-0000-00-1_ROBIN_HOOD

- dup_oran=**0.257**  ·  blok_sayisi=91  ·  boy=[600, 6237]  ·  mode=reading_runaware  ·  strict_scroll_frac=0.048  ·  doku_kapsami=0.8998  ·  gercek_onset=1046
- **Hipotez(ler): H2, H1/H4-supheli** (birincil: H2)
  - blok ofsetleri çoğunlukla uzak (88/91 blok kendi span'inin 3.0x'inden uzak ofsetli, ort=1817.8px, cv=0.608) -> ardışık-olmayan kart tekrarı imzası
  - boy_orani=1.431 sınırda (1.4x-2.5x arası) -- kesin değil, gözle doğrulama önerilir

### 11. 1988-0361-1-0000-00-1_DOĞUM_GÜNÜN_KUTLU_OLSUN_MAR

- dup_oran=**0.2519**  ·  blok_sayisi=55  ·  boy=[600, 7842]  ·  mode=reading_runaware  ·  strict_scroll_frac=0.4324  ·  doku_kapsami=0.8025  ·  gercek_onset=816
- **Hipotez(ler): H2** (birincil: H2)
  - blok ofsetleri çoğunlukla uzak (47/55 blok kendi span'inin 3.0x'inden uzak ofsetli, ort=408.7px, cv=0.611) -> ardışık-olmayan kart tekrarı imzası

### 12. 1996-0325-1-0000-00-1_KIZIL_HAYAT

- dup_oran=**0.2504**  ·  blok_sayisi=122  ·  boy=[600, 25972]  ·  mode=reading_runaware  ·  strict_scroll_frac=0.0  ·  doku_kapsami=0.8918  ·  gercek_onset=964
- **Hipotez(ler): H2** (birincil: H2)
  - blok ofsetleri çoğunlukla uzak (101/122 blok kendi span'inin 3.0x'inden uzak ofsetli, ort=423.1px, cv=0.98) -> ardışık-olmayan kart tekrarı imzası

### 13. 1986-0227-1-0000-00-1_6

- dup_oran=**0.21**  ·  blok_sayisi=58  ·  boy=[600, 8098]  ·  mode=reading_runaware  ·  strict_scroll_frac=0.0  ·  doku_kapsami=0.862  ·  gercek_onset=923
- **Hipotez(ler): H2** (birincil: H2)
  - blok ofsetleri çoğunlukla uzak (37/58 blok kendi span'inin 3.0x'inden uzak ofsetli, ort=467.6px, cv=1.635) -> ardışık-olmayan kart tekrarı imzası

### 14. 1940-0026-1-0000-00-1_KNUTE_ROICKNE

- dup_oran=**0.207**  ·  blok_sayisi=15  ·  boy=[568, 2629]  ·  mode=reading_runaware  ·  strict_scroll_frac=0.0  ·  doku_kapsami=0.9827  ·  gercek_onset=1146
- **Hipotez(ler): H2** (birincil: H2)
  - blok ofsetleri çoğunlukla uzak (14/15 blok kendi span'inin 3.0x'inden uzak ofsetli, ort=799.0px, cv=0.476) -> ardışık-olmayan kart tekrarı imzası

### 15. 1970-0076-1-0000-00-1_ŞAŞKIN_REKLAMCI

- dup_oran=**0.1803**  ·  blok_sayisi=93  ·  boy=[600, 7581]  ·  mode=reading_runaware  ·  strict_scroll_frac=0.5543  ·  doku_kapsami=0.8352  ·  gercek_onset=-1
- **Hipotez(ler): H2** (birincil: H2)
  - blok ofsetleri çoğunlukla uzak (75/93 blok kendi span'inin 3.0x'inden uzak ofsetli, ort=1023.9px, cv=1.034) -> ardışık-olmayan kart tekrarı imzası

## 6. Boy (yükseklik) vs dup_oran -- "canavar-boy" tek mekanizma değil

Plan dokümanının kendi örneği ("600x36695 canavarlar") ile havuzdaki en büyük masterlar karşılaştırıldığında önemli bir ayrım ortaya çıkıyor: yüksekliğin (boy) BÜYÜK olması ile dup_oran'ın YÜKSEK olması AYNI ŞEY DEĞİL. Bir master, birbirinden FARKLI çok sayıda statik kart içerdiği için de devasa boyuta ulaşabilir -- özellikle kredisiz kontrol penceresinde (gerçek kredi kartı yerine sıradan sahne kareleri "kart" sanılıp aşırı bölündüğünde). Bu durumda dup_oran DÜŞÜK kalır çünkü kartlar gerçekten birbirinden farklıdır, tekrar değildir -- israf/verimsizlik olabilir ama H1-H4'ün tanımladığı "duplikasyon" değildir. Aşağıdaki tablo havuzdaki en yüksek 5 masterı scroll-kaynaklı / statik-kart-kaynaklı yükseklik payına ayırarak gösterir (örn. `1998-0519-1-0000-00-1_SON_CÜCE`, 600x36356, plan'ın "36695" örneğine neredeyse birebir denk düşüyor -- ama dup_oran'ı yalnız 0.10, çünkü boyun büyük kısmı 70+ FARKLI statik karttan geliyor, scroll'dan değil).

| film | boy(H) px | dup_oran | gercek_onset | scroll-kaynaklı yükseklik | statik-kart-kaynaklı yükseklik |
|---|---|---|---|---|---|
| 1998-0519-1-0000-00-1_SON_CÜCE | 36356 | 0.1038 | -1 | 3054px (6 blok) | 33302px (72 blok) |
| 1999-0489-1-0000-00-1_AMY'NİN_TALİHSİZLİKLERİ | 29226 | 0.0542 | -1 | 7947px (14 blok) | 21279px (51 blok) |
| 1992-0472-1-0000-00-1_KALP_HIRSIZI | 28754 | 0.1259 | -1 | 7404px (13 blok) | 21350px (55 blok) |
| 1990-0513-1-0000-00-1_INNISFREE | 27186 | 0.0735 | -1 | 1178px (2 blok) | 26008px (62 blok) |
| 1996-0325-1-0000-00-1_KIZIL_HAYAT | 25972 | 0.2504 | 964 | 0px (0 blok) | 25972px (59 blok) |

## 7. Hipotez -> Fix Yönü Özeti

| hipotez | film sayısı | toplam dup_oran katkısı | önerilen fix yönü (M4) |
|---|---|---|---|
| H2 | 60 | 8.375 | global kart-dHash kaydı: yeni kart önceki TÜM kartlarla ham<=eşik+maske-IoU karşılaştırılsın (M4, yalnız kart-modu) |
| belirsiz | 34 | 0.08 | atlas sinyalleri yetersiz -- bu vakalar elle/görsel incelenmeli (kanıt kırpımı varsa oradan başla) |
| H1 | 11 | 0.73 | slit dilim birleştirmede dy-doğrulamalı örtüşme kırpma (M4: bindirmeyi NCC ile hizala-kes) |
| H3 | 6 | 0.734 | koşu sınıflandırma düzeltmesi: dy-kanıtlı koşu sayfa moduna düşemesin (M4) |
| H1/H4-supheli | 1 | 0.0 | sınırda -- ek gözle doğrulama sonrası H1 veya H4 fix'ine yönlendirilebilir |

## 8. Kanıt kırpımları

- `data/master_dup/kanit/1998-0970-1-0000-00-1_BAŞKAN_VE_MARI_blok60.png`
- `data/master_dup/kanit/1998-0970-1-0000-00-1_BAŞKAN_VE_MARI_blok61.png`
- `data/master_dup/kanit/1998-0970-1-0000-00-1_BAŞKAN_VE_MARI_blok62.png`
- `data/master_dup/kanit/1998-0970-1-0000-00-1_BAŞKAN_VE_MARI_blok63.png`
- `data/master_dup/kanit/1998-0970-1-0000-00-1_BAŞKAN_VE_MARI_blok40.png`
- `data/master_dup/kanit/1990-1068-1-0000-56-0_YAKIN_PLAN_blok2.png`
- `data/master_dup/kanit/1990-1068-1-0000-56-0_YAKIN_PLAN_blok27.png`
- `data/master_dup/kanit/1990-1068-1-0000-56-0_YAKIN_PLAN_blok246.png`
- `data/master_dup/kanit/1990-1068-1-0000-56-0_YAKIN_PLAN_blok0.png`
- `data/master_dup/kanit/1990-1068-1-0000-56-0_YAKIN_PLAN_blok29.png`
- `data/master_dup/kanit/2000-0477-1-0000-00-1_FUTBOLCU_PRENSES_blok3.png`
- `data/master_dup/kanit/2000-0477-1-0000-00-1_FUTBOLCU_PRENSES_blok63.png`
- `data/master_dup/kanit/2000-0477-1-0000-00-1_FUTBOLCU_PRENSES_blok138.png`
- `data/master_dup/kanit/2000-0477-1-0000-00-1_FUTBOLCU_PRENSES_blok137.png`
- `data/master_dup/kanit/2000-0477-1-0000-00-1_FUTBOLCU_PRENSES_blok222.png`
- `data/master_dup/kanit/1987-0232-1-0000-00-1_BAYAN_JULIE_blok73.png`
- `data/master_dup/kanit/1987-0232-1-0000-00-1_BAYAN_JULIE_blok0.png`
- `data/master_dup/kanit/1987-0232-1-0000-00-1_BAYAN_JULIE_blok67.png`
- `data/master_dup/kanit/1987-0232-1-0000-00-1_BAYAN_JULIE_blok68.png`
- `data/master_dup/kanit/1987-0232-1-0000-00-1_BAYAN_JULIE_blok19.png`
- `data/master_dup/kanit/2008-9046-1-0000-88-1_MEVLANA_AŞKIN_DANSI_blok66.png`
- `data/master_dup/kanit/2008-9046-1-0000-88-1_MEVLANA_AŞKIN_DANSI_blok4.png`
- `data/master_dup/kanit/2008-9046-1-0000-88-1_MEVLANA_AŞKIN_DANSI_blok44.png`
- `data/master_dup/kanit/2008-9046-1-0000-88-1_MEVLANA_AŞKIN_DANSI_blok58.png`
- `data/master_dup/kanit/2008-9046-1-0000-88-1_MEVLANA_AŞKIN_DANSI_blok6.png`
- `data/master_dup/kanit/1989-0476-1-0000-00-1_VANYA_DAYI_blok320.png`
- `data/master_dup/kanit/1989-0476-1-0000-00-1_VANYA_DAYI_blok165.png`
- `data/master_dup/kanit/1989-0476-1-0000-00-1_VANYA_DAYI_blok168.png`
- `data/master_dup/kanit/1989-0476-1-0000-00-1_VANYA_DAYI_blok169.png`
- `data/master_dup/kanit/1989-0476-1-0000-00-1_VANYA_DAYI_blok171.png`
- `data/master_dup/kanit/1999-0407-1-0000-00-1_KÜÇÜK_KAHRAMAN_blok190.png`
- `data/master_dup/kanit/1999-0407-1-0000-00-1_KÜÇÜK_KAHRAMAN_blok104.png`
- `data/master_dup/kanit/1999-0407-1-0000-00-1_KÜÇÜK_KAHRAMAN_blok161.png`
- `data/master_dup/kanit/1999-0407-1-0000-00-1_KÜÇÜK_KAHRAMAN_blok193.png`
- `data/master_dup/kanit/1999-0407-1-0000-00-1_KÜÇÜK_KAHRAMAN_blok24.png`
- `data/master_dup/kanit/1993-0435-1-0000-00-1_SEN_TOM_SAWYER_DEĞİLSİN_blok38.png`
- `data/master_dup/kanit/1993-0435-1-0000-00-1_SEN_TOM_SAWYER_DEĞİLSİN_blok61.png`
- `data/master_dup/kanit/1993-0435-1-0000-00-1_SEN_TOM_SAWYER_DEĞİLSİN_blok13.png`
- `data/master_dup/kanit/1993-0435-1-0000-00-1_SEN_TOM_SAWYER_DEĞİLSİN_blok16.png`
- `data/master_dup/kanit/1993-0435-1-0000-00-1_SEN_TOM_SAWYER_DEĞİLSİN_blok55.png`
- `data/master_dup/kanit/1960-0021-1-0000-00-1_BÜYÜK_MÜCADELE_blok7.png`
- `data/master_dup/kanit/1960-0021-1-0000-00-1_BÜYÜK_MÜCADELE_blok9.png`
- `data/master_dup/kanit/1960-0021-1-0000-00-1_BÜYÜK_MÜCADELE_blok14.png`
- `data/master_dup/kanit/1960-0021-1-0000-00-1_BÜYÜK_MÜCADELE_blok29.png`
- `data/master_dup/kanit/1960-0021-1-0000-00-1_BÜYÜK_MÜCADELE_blok35.png`
- `data/master_dup/kanit/2010-9139-1-0000-00-1_ROBIN_HOOD_blok0.png`
- `data/master_dup/kanit/2010-9139-1-0000-00-1_ROBIN_HOOD_blok89.png`
- `data/master_dup/kanit/2010-9139-1-0000-00-1_ROBIN_HOOD_blok3.png`
- `data/master_dup/kanit/2010-9139-1-0000-00-1_ROBIN_HOOD_blok29.png`
- `data/master_dup/kanit/2010-9139-1-0000-00-1_ROBIN_HOOD_blok31.png`
