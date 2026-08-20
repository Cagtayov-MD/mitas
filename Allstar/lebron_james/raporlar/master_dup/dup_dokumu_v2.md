# Master-PNG Duplikasyon Kusur Dökümü (Görev M3)

> Kaynak: `harness/master_dup/atlas.py` — `data/master_dup/masters/*/` (metrik.json + manifest.json) taranarak üretildi. Plan: `docs/MITAS_Master_Dup_Kok_Sebep_Plani_v1.md` (Görev M3).

## 1. Genel özet

- Toplam film (havuz): **112**
- Başarılı (OK, metrik hesaplanmış): **112**
- Başarısız/hatalı: **0**

## 2. dup_oran dağılımı

- Medyan: **0.0422**  ·  Ortalama: **0.0818**  ·  Maks: **0.6275**  ·  n=112

| dup_oran aralığı | film sayısı |
|---|---|
| [0.00, 0.01) | 38 |
| [0.01, 0.02) | 4 |
| [0.02, 0.05) | 23 |
| [0.05, 0.10) | 16 |
| [0.10, 0.20) | 17 |
| [0.20, 0.35) | 8 |
| [0.35, 0.50) | 5 |
| [0.50, 1.00] | 1 |

## 3. Kredisiz kontrol grubu vs kredi-var küme

- **Kredisiz** (gercek_onset=-1, son-240s pencere), n=29: dup_oran medyan=0.0511, ortalama=0.0575, maks=0.1525  ·  boy(H) ortalama=17062.0px  ·  kept_blocks ortalama=40.7
- **Kredi-var** (onset-15s pencere), n=83: dup_oran medyan=0.039, ortalama=0.0903, maks=0.6275  ·  boy(H) ortalama=7280.0px  ·  kept_blocks ortalama=13.7
- Not: kredisiz pencere (son 240s, gerçek kredi kartı YOK -- sıradan sahne) boy/blok sayısında kredili kümeden belirgin sapma gösteriyorsa, bu "statik-kart-splitter"ın sıradan sahne kesmelerini kart sanıp aşırı böldüğüne işaret eder (bkz. §6 -- SON_CÜCE örneği tam olarak bu grup içinde).

## 4. Mod x strict_scroll_frac x boy tablosu

(Havuz-çapında referans scroll hızı: **66.02 px/kare** — boy-sağlığı hesabında kullanıldı.)

| mode | film sayısı | strict_scroll_frac min/med/max | boy(H) min/med/max px | ortalama dup_oran | canavar-boy sayısı |
|---|---|---|---|---|---|
| reading_runaware | 80 | 0.00/0.19/0.71 | 628/8144/33151 | 0.1092 | 0 |
| reading_runaware_passthrough | 32 | 0.77/0.90/1.00 | 824/5972/16276 | 0.0133 | 0 |

## 5. En kötü 15 film -- ayrıntı

### 1. 1998-0970-1-0000-00-1_BAŞKAN_VE_MARI

- dup_oran=**0.6275**  ·  blok_sayisi=138  ·  boy=[600, 6474]  ·  mode=reading_runaware  ·  strict_scroll_frac=0.15  ·  doku_kapsami=0.9273  ·  gercek_onset=1004
- **Hipotez(ler): H2** (birincil: H2)
  - blok ofsetleri çoğunlukla uzak (111/138 blok kendi span'inin 3.0x'inden uzak ofsetli, ort=2015.4px, cv=0.657) -> ardışık-olmayan kart tekrarı imzası

### 2. 1990-1068-1-0000-56-0_YAKIN_PLAN

- dup_oran=**0.4332**  ·  blok_sayisi=226  ·  boy=[512, 4663]  ·  mode=reading_runaware  ·  strict_scroll_frac=0.681  ·  doku_kapsami=0.9827  ·  gercek_onset=903
- **Hipotez(ler): H2** (birincil: H2)
  - blok ofsetleri çoğunlukla uzak (207/226 blok kendi span'inin 3.0x'inden uzak ofsetli, ort=1101.3px, cv=0.819) -> ardışık-olmayan kart tekrarı imzası

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

### 7. 1993-0435-1-0000-00-1_SEN_TOM_SAWYER_DEĞİLSİN

- dup_oran=**0.3097**  ·  blok_sayisi=82  ·  boy=[600, 7364]  ·  mode=reading_runaware  ·  strict_scroll_frac=0.6667  ·  doku_kapsami=0.7374  ·  gercek_onset=805
- **Hipotez(ler): H2** (birincil: H2)
  - blok ofsetleri çoğunlukla uzak (75/82 blok kendi span'inin 3.0x'inden uzak ofsetli, ort=939.7px, cv=0.589) -> ardışık-olmayan kart tekrarı imzası

### 8. 1999-0407-1-0000-00-1_KÜÇÜK_KAHRAMAN

- dup_oran=**0.303**  ·  blok_sayisi=183  ·  boy=[600, 22381]  ·  mode=reading_runaware  ·  strict_scroll_frac=0.1053  ·  doku_kapsami=0.7432  ·  gercek_onset=971
- **Hipotez(ler): H2** (birincil: H2)
  - blok ofsetleri çoğunlukla uzak (181/183 blok kendi span'inin 3.0x'inden uzak ofsetli, ort=764.7px, cv=0.481) -> ardışık-olmayan kart tekrarı imzası

### 9. 1960-0021-1-0000-00-1_BÜYÜK_MÜCADELE

- dup_oran=**0.2752**  ·  blok_sayisi=79  ·  boy=[600, 4102]  ·  mode=reading_runaware  ·  strict_scroll_frac=0.0  ·  doku_kapsami=0.7566  ·  gercek_onset=988
- **Hipotez(ler): H2** (birincil: H2)
  - blok ofsetleri çoğunlukla uzak (77/79 blok kendi span'inin 3.0x'inden uzak ofsetli, ort=1368.3px, cv=0.616) -> ardışık-olmayan kart tekrarı imzası

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

### 15. 1999-0403-1-0000-00-1_PRENSESİN_AŞKI

- dup_oran=**0.17**  ·  blok_sayisi=286  ·  boy=[600, 6852]  ·  mode=reading_runaware  ·  strict_scroll_frac=0.0658  ·  doku_kapsami=0.7018  ·  gercek_onset=1046
- **Hipotez(ler): H3, H2** (birincil: H3)
  - 1 run'da strict_runs='R' (dy-kanıtlı scroll) ile runs='S' (fiili kompozisyon statik/sayfa saymış) çakışıyor -- örn strict[28, 32] vs reading[27, 32] (5 kare örtüşme)
  - blok ofsetleri çoğunlukla uzak (286/286 blok kendi span'inin 3.0x'inden uzak ofsetli, ort=1828.1px, cv=0.657) -> ardışık-olmayan kart tekrarı imzası

## 6. Boy (yükseklik) vs dup_oran -- "canavar-boy" tek mekanizma değil

Plan dokümanının kendi örneği ("600x36695 canavarlar") ile havuzdaki en büyük masterlar karşılaştırıldığında önemli bir ayrım ortaya çıkıyor: yüksekliğin (boy) BÜYÜK olması ile dup_oran'ın YÜKSEK olması AYNI ŞEY DEĞİL. Bir master, birbirinden FARKLI çok sayıda statik kart içerdiği için de devasa boyuta ulaşabilir -- özellikle kredisiz kontrol penceresinde (gerçek kredi kartı yerine sıradan sahne kareleri "kart" sanılıp aşırı bölündüğünde). Bu durumda dup_oran DÜŞÜK kalır çünkü kartlar gerçekten birbirinden farklıdır, tekrar değildir -- israf/verimsizlik olabilir ama H1-H4'ün tanımladığı "duplikasyon" değildir. Aşağıdaki tablo havuzdaki en yüksek 5 masterı scroll-kaynaklı / statik-kart-kaynaklı yükseklik payına ayırarak gösterir (örn. `1998-0519-1-0000-00-1_SON_CÜCE`, 600x36356, plan'ın "36695" örneğine neredeyse birebir denk düşüyor -- ama dup_oran'ı yalnız 0.10, çünkü boyun büyük kısmı 70+ FARKLI statik karttan geliyor, scroll'dan değil).

| film | boy(H) px | dup_oran | gercek_onset | scroll-kaynaklı yükseklik | statik-kart-kaynaklı yükseklik |
|---|---|---|---|---|---|
| 1998-0519-1-0000-00-1_SON_CÜCE | 33151 | 0.0771 | -1 | 3054px (6 blok) | 30097px (64 blok) |
| 1999-0489-1-0000-00-1_AMY'NİN_TALİHSİZLİKLERİ | 29226 | 0.0542 | -1 | 7947px (14 blok) | 21279px (51 blok) |
| 1996-0325-1-0000-00-1_KIZIL_HAYAT | 25972 | 0.2504 | 964 | 0px (0 blok) | 25972px (59 blok) |
| 1990-0513-1-0000-00-1_INNISFREE | 25540 | 0.0511 | -1 | 1178px (2 blok) | 24362px (58 blok) |
| 1956-0062-1-0000-00-1_PROFESÖR_HANNIBAL | 23287 | 0.0102 | -1 | 6046px (11 blok) | 17241px (43 blok) |

## 7. Hipotez -> Fix Yönü Özeti

| hipotez | film sayısı | toplam dup_oran katkısı | önerilen fix yönü (M4) |
|---|---|---|---|
| H2 | 58 | 7.856 | global kart-dHash kaydı: yeni kart önceki TÜM kartlarla ham<=eşik+maske-IoU karşılaştırılsın (M4, yalnız kart-modu) |
| belirsiz | 36 | 0.09 | atlas sinyalleri yetersiz -- bu vakalar elle/görsel incelenmeli (kanıt kırpımı varsa oradan başla) |
| H1 | 11 | 0.758 | slit dilim birleştirmede dy-doğrulamalı örtüşme kırpma (M4: bindirmeyi NCC ile hizala-kes) |
| H3 | 6 | 0.46 | koşu sınıflandırma düzeltmesi: dy-kanıtlı koşu sayfa moduna düşemesin (M4) |
| H1/H4-supheli | 1 | 0.0 | sınırda -- ek gözle doğrulama sonrası H1 veya H4 fix'ine yönlendirilebilir |

## 8. Kanıt kırpımları

- `data/master_dup/kanit_v2/1998-0970-1-0000-00-1_BAŞKAN_VE_MARI_blok60.png`
- `data/master_dup/kanit_v2/1998-0970-1-0000-00-1_BAŞKAN_VE_MARI_blok61.png`
- `data/master_dup/kanit_v2/1998-0970-1-0000-00-1_BAŞKAN_VE_MARI_blok62.png`
- `data/master_dup/kanit_v2/1998-0970-1-0000-00-1_BAŞKAN_VE_MARI_blok63.png`
- `data/master_dup/kanit_v2/1998-0970-1-0000-00-1_BAŞKAN_VE_MARI_blok40.png`
- `data/master_dup/kanit_v2/1990-1068-1-0000-56-0_YAKIN_PLAN_blok1.png`
- `data/master_dup/kanit_v2/1990-1068-1-0000-56-0_YAKIN_PLAN_blok20.png`
- `data/master_dup/kanit_v2/1990-1068-1-0000-56-0_YAKIN_PLAN_blok199.png`
- `data/master_dup/kanit_v2/1990-1068-1-0000-56-0_YAKIN_PLAN_blok22.png`
- `data/master_dup/kanit_v2/1990-1068-1-0000-56-0_YAKIN_PLAN_blok201.png`
- `data/master_dup/kanit_v2/2000-0477-1-0000-00-1_FUTBOLCU_PRENSES_blok3.png`
- `data/master_dup/kanit_v2/2000-0477-1-0000-00-1_FUTBOLCU_PRENSES_blok63.png`
- `data/master_dup/kanit_v2/2000-0477-1-0000-00-1_FUTBOLCU_PRENSES_blok138.png`
- `data/master_dup/kanit_v2/2000-0477-1-0000-00-1_FUTBOLCU_PRENSES_blok137.png`
- `data/master_dup/kanit_v2/2000-0477-1-0000-00-1_FUTBOLCU_PRENSES_blok222.png`
- `data/master_dup/kanit_v2/1987-0232-1-0000-00-1_BAYAN_JULIE_blok73.png`
- `data/master_dup/kanit_v2/1987-0232-1-0000-00-1_BAYAN_JULIE_blok0.png`
- `data/master_dup/kanit_v2/1987-0232-1-0000-00-1_BAYAN_JULIE_blok67.png`
- `data/master_dup/kanit_v2/1987-0232-1-0000-00-1_BAYAN_JULIE_blok68.png`
- `data/master_dup/kanit_v2/1987-0232-1-0000-00-1_BAYAN_JULIE_blok19.png`
- `data/master_dup/kanit_v2/2008-9046-1-0000-88-1_MEVLANA_AŞKIN_DANSI_blok66.png`
- `data/master_dup/kanit_v2/2008-9046-1-0000-88-1_MEVLANA_AŞKIN_DANSI_blok4.png`
- `data/master_dup/kanit_v2/2008-9046-1-0000-88-1_MEVLANA_AŞKIN_DANSI_blok44.png`
- `data/master_dup/kanit_v2/2008-9046-1-0000-88-1_MEVLANA_AŞKIN_DANSI_blok58.png`
- `data/master_dup/kanit_v2/2008-9046-1-0000-88-1_MEVLANA_AŞKIN_DANSI_blok6.png`
- `data/master_dup/kanit_v2/1989-0476-1-0000-00-1_VANYA_DAYI_blok320.png`
- `data/master_dup/kanit_v2/1989-0476-1-0000-00-1_VANYA_DAYI_blok165.png`
- `data/master_dup/kanit_v2/1989-0476-1-0000-00-1_VANYA_DAYI_blok168.png`
- `data/master_dup/kanit_v2/1989-0476-1-0000-00-1_VANYA_DAYI_blok169.png`
- `data/master_dup/kanit_v2/1989-0476-1-0000-00-1_VANYA_DAYI_blok171.png`
- `data/master_dup/kanit_v2/1993-0435-1-0000-00-1_SEN_TOM_SAWYER_DEĞİLSİN_blok38.png`
- `data/master_dup/kanit_v2/1993-0435-1-0000-00-1_SEN_TOM_SAWYER_DEĞİLSİN_blok61.png`
- `data/master_dup/kanit_v2/1993-0435-1-0000-00-1_SEN_TOM_SAWYER_DEĞİLSİN_blok13.png`
- `data/master_dup/kanit_v2/1993-0435-1-0000-00-1_SEN_TOM_SAWYER_DEĞİLSİN_blok16.png`
- `data/master_dup/kanit_v2/1993-0435-1-0000-00-1_SEN_TOM_SAWYER_DEĞİLSİN_blok55.png`
- `data/master_dup/kanit_v2/1999-0407-1-0000-00-1_KÜÇÜK_KAHRAMAN_blok107.png`
- `data/master_dup/kanit_v2/1999-0407-1-0000-00-1_KÜÇÜK_KAHRAMAN_blok95.png`
- `data/master_dup/kanit_v2/1999-0407-1-0000-00-1_KÜÇÜK_KAHRAMAN_blok169.png`
- `data/master_dup/kanit_v2/1999-0407-1-0000-00-1_KÜÇÜK_KAHRAMAN_blok140.png`
- `data/master_dup/kanit_v2/1999-0407-1-0000-00-1_KÜÇÜK_KAHRAMAN_blok146.png`
- `data/master_dup/kanit_v2/1960-0021-1-0000-00-1_BÜYÜK_MÜCADELE_blok5.png`
- `data/master_dup/kanit_v2/1960-0021-1-0000-00-1_BÜYÜK_MÜCADELE_blok9.png`
- `data/master_dup/kanit_v2/1960-0021-1-0000-00-1_BÜYÜK_MÜCADELE_blok14.png`
- `data/master_dup/kanit_v2/1960-0021-1-0000-00-1_BÜYÜK_MÜCADELE_blok30.png`
- `data/master_dup/kanit_v2/1960-0021-1-0000-00-1_BÜYÜK_MÜCADELE_blok33.png`
- `data/master_dup/kanit_v2/2010-9139-1-0000-00-1_ROBIN_HOOD_blok0.png`
- `data/master_dup/kanit_v2/2010-9139-1-0000-00-1_ROBIN_HOOD_blok89.png`
- `data/master_dup/kanit_v2/2010-9139-1-0000-00-1_ROBIN_HOOD_blok3.png`
- `data/master_dup/kanit_v2/2010-9139-1-0000-00-1_ROBIN_HOOD_blok29.png`
- `data/master_dup/kanit_v2/2010-9139-1-0000-00-1_ROBIN_HOOD_blok31.png`
