# MITAS — Son 250 Çıktı Forensik Raporu (2026-06-20)

## 1. Yönetici Özeti

Son 250 künye çıktısının **248'i bozuk** (yalnızca 2 temiz). Bu yüksek oran tek bir kötü modülden değil, **üst üste binmiş üç ayrı kök-nedenden** kaynaklanıyor; en zararlısı codex regresyonu DEĞİL, codex'ten tamamen bağımsız bir mimari kusur.

**En büyük kök-neden — PROPAGATION (189 film):** `credit_validate` (IMDb + Wikidata + XML ile doğrulanmış TEMİZ cast/yönetmen) **ADDITIVE** tasarlanmış. `mitas_pipeline.py:1608` açıkça "yönetmen/PDF AKIŞINI DEĞİŞTİRMEZ" diyor. Yani sistem doğru ismi okuyup doğruluyor (NAOMI WATTS, BILL PAXTON, KIRK DOUGLAS, SERGIO CORBUCCI...), sonra bu doğru değeri **çöpe atıp** final'e OCR ham gürültüsünü (şoför bloğu, craft-services, müzik-kredi, şirket satırları) yazıyor. Bu **codex'ten bağımsız** ve `ac04db26a2` fix'i ile **DÜZELMEDİ**.

**Codex'in etkisi (115 film):** 115 çıktı (`during` penceresi) codex'in iki regresyonu altında üretildi — QC1 ön-eleme kaldırma (`0fbca67535`) + agresif kişi-kapısı varsayılan AÇIK. Bunlar `ac04db26a2` (06-19) ile **kodda düzeldi** ama **bu 250 çıktı hâlâ bozuk** — yeniden işlenmeli.

**En kritik bug:** Doğru-üretilip-atılma. Sistem gerçek cast'i okuyup doğrulamış olmasına rağmen final'e gürültü yazıyor; üstüne bazıları yanlışlıkla **ONAYLI** damgalanmış (TAKIM = false-positive ONAYLI).

| Gösterge | Değer |
|---|---|
| Toplam çıktı | 250 |
| Bozuk | 248 (%99.2) |
| Temiz | 2 |
| Codex penceresinde üretilen | 115 (%46) |
| Codex öncesi üretilen | 135 (%54) |
| Yeniden işlenmesi gereken (rerun zaten) | 36 |
| En büyük tek kök-neden | PROPAGATION — 189 film |

---

## 2. Rakamlarla Durum

### 2.1 Hata Tipi Dağılımı

| Hata Tipi | Sayı | Açıklama |
|---|---|---|
| E3_CAST_GURULTU | 236 | Oyuncu alanında kişi-olmayan satır (şoför/craft/müzik-kredi/şirket) |
| E10_KEYWORD_GURULTU | 133 | Anahtar sözcükler cast'tan türediği için aynı gürültüyü taşıyor |
| E5_YONETMEN_YANLIS | 120 | Yönetmen alanında fazla/yanlış kişi (oyuncu, DoP, crew) |
| E2_YAPIMCI_BOS | 116 | Yapımcı yok veya crew/şirket gürültüsü |
| E7_GARBLE | 84 | Harf-harf bozulmuş OCR token'ı |
| E1_YONETMEN_BOS | 71 | Yönetmen alanı boş |
| E4_CAST_AZ | 62 | Gerçek oyuncu sayısı < eşik |
| E9_CASING | 49 | Büyük-harf değil (tr_upper uygulanmamış) |
| E12_META_EKSIK | 47 | Ses & Altyazı / Tür eksik |
| E6_OZET_YANLIS | 30 | Özet placeholder veya yanlış film |
| E11_TUR_YANLIS | 24 | Tür boş veya yanlış sınıf |
| E8_LATIN_DISI | 6 | Latin-dışı alfabe kalıntısı |
| E2_YAPIMCI_YANLIS | 1 | Yapımcıya sponsor/şirket |

### 2.2 Kök-Neden Aşama Dağılımı

| Aşama | Sayı | Codex ile ilişkisi |
|---|---|---|
| PROPAGATION | 189 | **Bağımsız — NOT_FIXED** |
| QC1_NOISE | 149 | Codex regresyonu — kodda DÜZELDİ |
| CREDIT_TEXT | 101 | Kısmi (rol-overreach) |
| OCR_GARBLE | 66 | NOT_FIXED |
| VALIDATE | 61 | Çoğu DOĞRU davranış (uydurma yok) |
| OCR_RECALL | 36 | Kısmi |
| PERSON_GATE | 27 | Codex regresyonu — kodda DÜZELDİ |
| ASR_LANG | 25 | **Bağımsız — NOT_FIXED (tek satır fix)** |
| VL_FALLBACK | 25 | Kısmi |
| KAYNAK | 15 | Sistem-dışı |
| DETECT | 13 | Kısmi |
| OZET | 7 | DÜZELDİ |
| PDF (route) | 5 | NOT_FIXED |
| ENRICH | 3 | — |
| CASING | 2 | — |

> Not: Bir film birden çok aşamada hata barındırabilir; toplam 250'yi aşar.

### 2.3 Karar Dağılımı

| Karar | Sayı |
|---|---|
| Kontrol | 201 |
| AutoFix | 31 |
| Kontrol (AutoFix/route varyantları) | 8 |
| TürAyrı (BELGESEL/ANİMASYON) | 4 |
| Hazır / ONAYLI | 4 |
| Kontrol — SADECE KİMLİK | 2 |

Çoğu çıktı doğru biçimde **Kontrol**'e yönlendirilmiş — bu iyi. Ama **4 çıktı Hazır/ONAYLI** damgalanmış, en az biri (TAKIM) ağır bozukken. Bu **false-positive ONAYLI** = router güveni yanlış.

### 2.4 Rerun & Codex Penceresi

| Gösterge | Değer |
|---|---|
| Rerun edilmiş çıktı | 36 |
| Codex öncesi (before, ≤06-16T17:00Z) | 135 |
| Codex penceresi (during, 06-16→06-19 fix) | 115 |
| Bilinmeyen | 0 |

---

## 3. Hata Sınıfı → Sebep → Git Durumu

### 3.1 E3_CAST_GURULTU — Oyuncuya reklam/şoför/müzik-kredi çıktı (236 film)

**Ne oldu:** Oyuncular alanına kişi-olmayan satırlar yazıldı — şoför blokları (CAST DRIVERS), craft-services (CRAFT SERVICES DORA CSUPORT), müzik-kredi (PERFORMED BY JONSI, MIXED BY TOM EIMHIRST), şirket/telif (COURTESY OF SIRE RECORDS, WALT DISNEY).

**Sebebi iki ayrı mekanizma:**

1. **PROPAGATION (asıl sebep):** Oyuncuya çöp çıktı **çünkü** `credit_validate` gerçek oyuncuyu okuyup doğruladı ama final bu değeri kullanmadı, OCR ham metnin yanlış satırlarını yazdı.
   - **UMUTSUZ SAAT:** validate `[NAOMI WATTS, JASON CLARKE, WOODROW SCHRIEBER...]` üretti (evt-3af0d8100932), final cast `[SCOTTY BRATTON, CRAFT SERVICES DORA CSUPORT, KEY CRAFT SERVER LIAM BRADFORD]` — OCR satır 151-158 şoför+craft bloğu. v4_finalize (391s) validate değerini taşımadı.
   - **HAYATIMIN MAÇI:** validate `[BILL PAXTON, SHIA LEBEOUF, STEPHEN DILLANE, ELIAS KOTEAS]` (evt-88d9092a27f8), final cast `[NICK CARASOULIS LUC PARADIS, MICHEL PELLETIER...]` — OCR satır 318-324 "CAST DRIVERS" şoför bloğu.
   - **OYUN (Play, 2011):** validate filmin gerçek oyuncularını birebir çıkardı `[ANAS ABDIRAHMAN, SEBASTIAN BLYCKERT, YANNICK DIAKITE...]`, final açılış-kartı gürültüsünü yazdı.

2. **QC1_NOISE (codex regresyonu):** QC1 ön-eleme kaldırıldığı için müzik-kredi/şirket satırları LLM'e ve final'e sızdı.
   - **DÜŞLER BAHÇESİ:** final cast `PERFORMED BY JONSI / MIXED BY TOM EIMHIRST / COURTESY OF SIRE RECORDS / TV LICENSING` — OCR satır 1-8 müzik bloğu.

**Hangi commit hedefledi:** PROPAGATION için **hiçbiri** (`96beec1ade`/`0448afae70` validate'i ADDITIVE ekledi, final'e bağlamadı). QC1_NOISE için `ac04db26a2` (06-19, prefilter geri).

**Durum:**
- PROPAGATION → **DÜZELMEDİ** (kod hâlâ ADDITIVE)
- QC1_NOISE → **CODEX-REGRESYONU, kodda DÜZELDİ** ama bu 250 çıktı hâlâ bozuk

---

### 3.2 E5_YONETMEN_YANLIS — Yönetmene oyuncu/DoP/crew karıştı (120 film)

**Ne oldu:** Yönetmen alanına gerçek yönetmenin yanında oyuncular, görüntü yönetmeni (DoP), ortak-yapımcılar veya crew sızdı.

**Sebebi:** `credit_text` rol-eşlemesi "DIRECTED BY / A FILM BY / GÖRÜNTÜ YÖNETMENİ" etiketinden **SONRAKİ satırları** yönetmen alanına dolduruyor (S2_ROLE_OVERREACH). Yönetmene oyuncu çıktı **çünkü** etiket-sonrası kuyruk taşması durmuyor; validate doğru tek-yönetmeni üretse bile final taşımıyor (PROPAGATION boyutu).

- **KİRALIK SİLAH:** final yön `[FRANCO GIACOBINI, EDUARDO FAJARDO, FRANCO RESSEL, SERGIO CORBUCCI]`. İlk 3'ü OYUNCU (OCR satır 5-7, "A FILM BY" sonrası cast bloğu). validate temiz `[SERGIO CORBUCCI]` DOGRULANDI. Web teyit: tek yönetmen Sergio Corbucci.
- **YAŞAMAK:** final yön `GORÜNTÜ GÖNETMENİ JULIEN LANDWEER, UĞUR KAPLAN` — DoP etiketi yönetmene kondu. Gerçek yön Talip Karamahmutoğlu (OCR satır 51, garble) validate'te vardı, gelmedi. Web teyit: Talip Karamahmutoğlu.
- **SONSUZA KADAR MUTLULAR:** final yön `STEPHEN BURKE, HELGA BINDER, CHRISTINE RUPPERT`. Web teyit: Binder/Ruppert Alman ortak-YAPIMCILARI, yönetmen değil.
- **DÜŞMANIN YOLU:** final yön `BRENDA BLETHYN, ELLEN BURSTYN, HARVEY KEITEL, RACHID BOUCHAREB` — ilk üçü oyuncu. Web teyit: tek yönetmen Rachid Bouchareb.

**Hangi commit hedefledi:** `feddbf12a2` (parse çöp-sertleştirme) + `8ea6caf91b` (yönetmen müzik/crew kalıbı) — **kısmi kapsama**.

**Durum:** **KISMEN düzeldi.** Kalıp filtresi rol-etiketlerinin tümünü kapsamıyor; kuyruk-taşması ve DoP=yönetmen karışımı sürüyor. PROPAGATION fix'i bunu kökten çözer (validate'in tek-doğru yönetmeni final'i ezer).

---

### 3.3 E1_YONETMEN_BOS — Yönetmen eksik kaldı (71 film)

**Ne oldu:** Yönetmen alanı boş veya hiç yok.

**Sebebi iki ayrı mekanizma:**

1. **OCR_RECALL/DETECT (kaynak eksik):** Yönetmen eksik kaldı **çünkü** jenerik pencere lead yönetmen karesini hiç yakalamadı.
   - **GÖREVİMİZ TEHLİKE 4:** GİRİŞ conf=0.525 → sabit head=180s, ÇIKIŞ conf=0.548 → sabit pencere; 526 satır okundu, hepsi alt-crew, Brad Bird hiç okunmadı.
   - **HAVANA:** OCR sadece 8 satır okudu, hepsi MCA logo garble; gerçek jenerik karesine girilmedi.

2. **VALIDATE (DOĞRU muhafazakâr davranış):** OCR boş + VL boş → validate OCR-otorite gereği boş bıraktı (uydurma yok). Bu **doğru** ama sonuç boş yönetmen.
   - **FOTOĞRAF, MOBY DICK 2, FIRTINADAN SONRA, BEYAZ SAYFA:** validate `status=OKUNAMADI notes='OCR boş → doldurma yok'`. Sistem uydurmadı = OCR-otorite KANUNU'na uygun.

**Hangi commit hedefledi:** OCR_RECALL için `b50331d8ca` (CREDIT_DETECT) + `efe3514e33` (güven-kapısı) — kısmi. VALIDATE davranışı için `03e0fa8c0a` (kimlik kilidi) — doğru, değiştirilmemeli.

**Durum:**
- VALIDATE muhafazakârlığı → **DOĞRU, değiştirme.**
- OCR_RECALL → **KISMEN düzeldi**, düşük-güven köşe-vakaları kaldı (çoklu-pencere tarama gerek).

---

### 3.4 E2_YAPIMCI_BOS — Yapımcı boş veya crew/şirket (116 film)

**Ne oldu:** Yapımcı alanı ya yok ya da post-prodüksiyon/VFX/yerel-birim crew veya şirket-telif satırları içeriyor.

**Sebebi:** Çoğu PROPAGATION (validate temizi atıldı) + bir kısmı CREDIT_TEXT rol-eşleme:
- **GÖREVİMİZ TEHLİKE 4:** yapımcı `LEIGH CLARKE, MICHAEL TURNER, MARK STEPHEN` — OCR "DUBAI UNIT / UAE FACILITATING PRODUCER" bloğu (yerel-birim crew). Rol-etiketi "PRODUCER" yanılttı.
- **GENÇ KADIN VE DENİZ:** yapımcı `COURTESY OF COLUMBIA RECORDS, SOUNDTRACK AVAILABLE ON, WALT DISNEY` — şarkı-telif/stüdyo bloğu (QC1_NOISE).
- **MOBY DICK 2:** yapımcı `SCANLINE VEX, MICHAEL MIELKE, KAY WOYTKE` — VFX şirketi + VFX crew.

**Durum:** PROPAGATION boyutu **DÜZELMEDİ**; QC1_NOISE boyutu **kodda DÜZELDİ**; CREDIT_TEXT rol-eşleme **kısmi**.

---

### 3.5 E6_OZET_YANLIS / E12_META_EKSIK — Özet placeholder, Ses-dil eksik (30 + 47 film)

**Ne oldu:** Özet `(ÖZET AYRI BİR ADIMDA ÜRETİLECEKTİR.)` placeholder; bazı filmlerde Ses & Altyazı bölümü hiç yok.

**Sebebi — ASR_LANG (commit-dışı, PRE_EXISTING bug):** `_channel_lang.py:35 _LANG_MAP` yalnız bir alt-küme 3-harf ISO-639-3 kodu kapsıyor. `swe/est/isl/cmn/jav/vie/mon` EKSİK. `_map_lang` eksik kodda ham 3-harfi whisper'a verip `ValueError` fırlatıyor → 0 segment → transcript yok → özet placeholder + ses-dil eksik.

| Film | Dil | Hata | Doğru kod |
|---|---|---|---|
| SONSUZLUK ÜZERİNE | İsveççe | `'swe' is not a valid language code` | sv |
| HAKİKAT VE ADALET | Estonca | `'est'...` | et |
| İNATÇILAR | İzlandaca | `'isl'...` | is |
| SINIRI GEÇMEK | Çince | `'cmn'...` | zh/yue |
| NİLLAS'IN ÖYKÜSÜ | Cava | `'jav'...` | jw |
| BABAMIN KAMYONU | Vietnamca | `'vie'...` | vi |
| CENGİZ HANIN İKİ ATI | Moğolca | `'mon'...` | mn |

Bu filmlerin çoğunda ASR-dışı alanlar (yönetmen, cast, web özet potansiyeli) zaten doğru; tek eksik dil-kodu çökmesi.

**Hangi commit hedefledi:** **HİÇBİRİ.** Hiçbir commit `_LANG_MAP`'e dokunmadı.

**Durum:** **DÜZELMEDİ.** Bu **tek satır fix, en yüksek ROI** (aşağıda Öneri 2).

> Ayrı bir alt-küme (Kürtçe: DÜŞLER BAHÇESİ, YAŞAMAK): `skipped_unsupported_lang` = kasıtlı atlama. Burada özetin boş kalması DÜRÜST davranış; `8f429bbb33` ile internet-özeti kimlik-doğrulamalı yapıldı (DÜZELDİ). Kalan placeholder'ların çoğu ASR_LANG kaynaklı.

---

### 3.6 E7_GARBLE / E8_LATIN_DISI — Harf-harf bozulma, Latin-dışı kalıntı (84 + 6 film)

**Ne oldu:** Cast/keyword'de anlamsız token (LISE TREDVCER, POETIV LILANSE, MORK WU, A CCP).

**Sebebi:** Düşük çözünürlük (512×288) + Latin-dışı alfabe (Hint/Çince/Kiril/Arapça) → OneOCR anlamsız token üretiyor; garble-gate naif (memory: SLY STALLONE→garble=True silinir, RDGER MQSTEY→0.00 kaçar) → gerçek-ismi düşürür, garble'ı tutar.
- **FOTOĞRAF (512×288 Hint):** cast `LISE TREDVCER, TAN NAWAZUDDIN`; OCR boyunca yoğun garble.
- **GEÇ GELEN AŞK (Kiril):** cast/keyword `A CCP` (= СССР kalıntısı).

**Durum:** **DÜZELMEDİ.** Memory'deki "okunamadı > yanlış oku" kanunu (blur metriği stroke_px<3) ile düşük-çözünürlük karesi OCR'a sokulmamalı; garble-gate perplexity/sözlük-oranı tabanlı olmalı.

---

## 4. Codex (GPT) Regresyon Analizi

### 4.1 Codex ne kırdı?

| Commit | Tarih | Etki | Onaran |
|---|---|---|---|
| `0fbca67535` | 06-16 20:13 | QC1 `_prefilter` ön-elemeyi KALDIRDI → disclaimer/müzik-kredi/şirket geri sızdı | `ac04db26a2` (prefilter GERİ) |
| `0fbca67535` | 06-16 20:13 | Agresif kişi-kapısını varsayılan AÇTI → gerçek (KB-imzasız) yabancı oyuncu düşürüldü | `ac04db26a2` (varsayılan OFF) |
| `a0c28be589` | 06-16 | Paddle OCR sidecar'ı kapattı | — (OCR recall'a küçük negatif) |

Kod kanıtı:
- `credit_text_read.py:909`: "_prefilter_lines ... codex bunu kaldırmıştı (regresyon)"
- `tek_film_kunye.py:31-32`: "_GLOBAL_PERSON_GATE_ON ... codex 1 yapmıştı = regresyon", artık varsayılan `0`

### 4.2 Bu 250 çıktıya etkisi

**115 film** `during` penceresinde (06-16T17:00Z → 06-19 15:55 fix arası) üretildi → codex regresyonları altında. Semptomlar:
- **PERSON_GATE düşürmeleri:** ARKADAŞIM ÖRDEK (`cast:Yves Ringer, cast:Margaux Warny`), SONSUZLUK (`cast:Frida Elinström`), UMUT LİMANI (`cast:CHANG QUOC DUNG NGUYEN`) — gerçek yabancı oyuncular KB'de yok diye elendi.
- **QC1 gürültü sızması:** CASUS ELLER YUKARI (Möbel Pfister sponsor), GENÇ KADIN VE DENİZ (WALT DISNEY).

### 4.3 06-19 fix ne geri aldı?

`ac04db26a2`: QC1 prefilter geri + kişi-kapısı varsayılan OFF + cast cap 260→500. Bu **kodda** PERSON_GATE ve QC1_NOISE'i düzeltti.

### 4.4 Bu 250 çıktı yeniden koşulmalı mı?

**Evet — `during` penceresindeki 115 film yeniden işlenmeli.** Gerekçe:
- PERSON_GATE (27) + QC1_NOISE (149) semptomları kodda düzeldi ama bu çıktılar düzelmeden ÖNCE üretildi; kod düzeldi diye çıktı düzelmez.
- **AMA tek başına yeniden-koşma yetmez:** PROPAGATION (189) ve ASR_LANG (25) codex'ten bağımsız ve hâlâ açık. Bunlar düzeltilmeden yeniden koşmak gürültünün bir kısmını ama kök-hasarı (doğru-değer atılması) gidermez. **Doğru sıra: önce PROPAGATION + ASR_LANG fix → sonra toplu yeniden-işleme.**

**Kritik ayrım:** Codex regresyonu yüzeyi (gürültü/kişi-kapısı) ağırlaştırdı, ama ana yapısal hasar (doğru-değer-üretilip-atılması) **codex-dışı** ve hâlâ açık. Codex'i tek suçlu görmek yanıltıcı olur.

---

## 5. En Kritik Buglar

### 5.1 PROPAGATION — Doğru üretildi, final'e gitmedi (EN KRİTİK, 189 film)

`credit_validate` doğru değeri üretip log'a/reasons'a yazıyor ama `v4_finalize` bunu PDF'e taşımıyor. Final ham OCR gürültüsünü kullanıyor.

**En çarpıcı kanıtlar:**

| Film | validate üretti | final yazdı |
|---|---|---|
| TAKIM (Posse, 1975) | 8 temiz isim: KIRK DOUGLAS, BRUCE DERN, DAVID CANARY, ALFONSO ARAU... | HOWARD NIGHTINGALE (karakter), JACK STRAWHORN (karakter), T.IKF. ASKEW (garble) |
| UMUTSUZ SAAT | NAOMI WATTS, JASON CLARKE, WOODROW SCHRIEBER | SCOTTY BRATTON, CRAFT SERVICES DORA CSUPORT |
| OYUN (Play) | ANAS ABDIRAHMAN, SEBASTIAN BLYCKERT, YANNICK DIAKITE | açılış-kartı gürültüsü |
| FEDAKAR POSTACI | CHARLTON HESTON, RHONDA FLEMING, FORREST TUCKER | ALL RIQHIS, COPYRIONT MCMETD, JENAT HOPRER |
| MONTE KRİSTO KONTU | Jim Caviezel, Henry Cavill, Richard Harris (yazım-teyitli) | MANSION OWNER GUY CARLETON, OLD DANTEC RARRY CASCIN |

> Soruda sorulan **SHERLOCK / GUY RITCHIE** örneği bu 250'lik veri kümesinde yer almıyor; ancak aynı bug ailesinin tıpatıp eşleri yukarıda. Mekanizma birebir aynı: validate doğru üretir, final ham OCR'ı yazar.

**Hâlâ kodda mı?** **EVET.** `mitas_pipeline.py:1606-1625` — `cv_result` yalnız log + reasons'a gidiyor; `1627` sonrası PDF üretimi ham `video_credits`'i kullanıyor. `credit_validate` hâlâ `MITAS_CREDIT_VALIDATE` flag'inde ve ADDITIVE.

### 5.2 ROUTE false-positive ONAYLI (5 film)

QC2 router cast-garble'ı "yalnız CASING" hafif kusur sanıp ONAYLI/AUTOFIX'e yönlendiriyor.
- **TAKIM:** `route.tier='TEMIZ', folder='ONAYLI', açıklama='kusursuz'` — ama cast karakter-adı + garble dolu. **Bozuk çıktı ONAYLI damgalandı.**
- **FEDAKAR POSTACI, FIRTINADAN SONRA:** tier=AUTOFIX yalnız CASING ama cast disclaimer/garble ağır.

Bu, MEMORY'deki MITAS1 felaketi riskinin (yanlış ONAYLI) tekrarı.

### 5.3 VL_FALLBACK halüsinasyonu (25 film)

gemma4 VL OCR'da olmayan ismi türetip QC1-PASS veriyor.
- **FOTOĞRAF:** VL yön `[JEFF TOWLES]` (gerçek Ritesh Batra), validate ÇELİŞKİ bayrakladı (RİTESH BATRA) ama final JEFF TOWLES kaldı. Web teyit: bu isim hiçbir yerde yok = uydurma.
- **GENÇ KADIN VE DENİZ:** VL cast'e Natalie Portman/Benedict Cumberbatch/Tom Hiddleston ekledi (filmde yok).

---

## 6. Kaynak-Kaynaklı vs Sistem-Kaynaklı Ayrımı

| Tür | Açıklama | Örnekler | Sorumluluk |
|---|---|---|---|
| **Saf kaynak** | Latin-dışı jenerik (Arapça/Çince/Kiril/Moğol), oyuncu künyesi Latin OCR ile okunamaz | BÜYÜK GELEN PALTO (Arapça), TANRI'NIN ZIRHI 2 (Çince HK), GEÇ GELEN AŞK (Kiril), CENGİZ HANIN İKİ ATI (Moğol) | Kaynak — düzeltilemez |
| **Kaynak + sistem** | Kaynak zor AMA gürültü-token'ın cast'e yazılması sistem hatası | BÜYÜK GELEN PALTO ("TINLAN SELF GOVERNMENT" cast'e), HAVANA (8 logo garble "GUVENILIR" sayıldı) | Karma — boş bırakılmalıydı |
| **Görünüşte kaynak, aslında sistem** | Künye OCR'da MEVCUT ama rol-eşleme/propagation kaçırdı | NİLLAS (gerçek yön "A FILM BY MEIKEMINNE CLINCKSPOOR" OCR'da var, final'e gitmedi), YAŞAMAK (Türkçe künye temiz okundu, leadler atlandı) | **Sistem** |
| **ASR dil-kodu (sistem)** | Yabancı film AMA dil-kodu eşlemesi eksik (`hun`/`swe`/`vie` gibi) → ASR çöküyor | SONSUZLUK ÜZERİNE, İNATÇILAR, BABAMIN KAMYONU | **Sistem — tek satır fix** |

**Anahtar bulgu:** Yabancı/arşiv film olması tek başına mazeret değil. Birçok yabancı filmde künye OCR'da net okunmuş veya validate doğru üretmiş; hasar sistem-içi (PROPAGATION / rol-eşleme / dil-kodu) kaynaklı. Saf kaynak suçu yalnızca ~15 filmde (Latin-dışı jenerik), o filmlerde bile cast boş **bırakılmalıyken** gürültü yazılması sistem hatasıdır.

---

## 7. Öncelikli Optimizasyon Önerileri

Etki × efor sırasıyla:

### Öneri 1 — PROPAGATION: credit_validate'i ADDITIVE'den AUTHORITATIVE'e çevir
**Etki: ÇOK YÜKSEK (189 film) · Efor: ORTA**

`mitas_pipeline.py:1618` sonrası: `cv_result.cast/yonetmen` status DOĞRULANDI veya KB-imzalı ise PDF'e giden `video_credits['cast']/['yonetmen']`'i validate değeriyle **DEĞİŞTİR**. OCR-otorite KANUNU'na uygun yöntem:
- Validate'in cast'i ile ham cast arasında fuzzy-kesişim al.
- Validate'in ismi OCR ham metninde **ad+soyad bitişik substring** olarak GEÇİYORSA güvenle ez (uydurma değil, OCR'da okunanın doğrulanmışı).
- Ham-only gürültü satırlarını (şoför/craft/müzik-kredi/şirket) DÜŞÜR.
- Flag arkasında kademeli aç. Golden-diff testi: TAKIM / OYUN / UMUTSUZ SAAT / HAYATIMIN MAÇI.

Bu tek değişiklik E3, E5, E10, E2, E9'un büyük kısmını aynı anda çözer.

### Öneri 2 — ASR_LANG: _LANG_MAP'i tamamla (tek satır, en yüksek ROI)
**Etki: YÜKSEK (25 film, özet+ses-dil) · Efor: ÇOK DÜŞÜK**

`_channel_lang.py:35 _LANG_MAP`'e ekle:
```
'swe':'sv','est':'et','isl':'is','cmn':'zh','yue':'yue','jav':'jw',
'vie':'vi','mon':'mn','nor':'no','dan':'da','fin':'fi','slk':'sk',
'slv':'sl','lit':'lt','lav':'lv'
```
Daha sağlam: `_map_lang`'a bilinmeyen 3-harf kodu için iso639/pycountry ile 2-harf'e çevirme fallback'i; çevrilemezse whisper'a dil VERME (auto-detect). Bu 25 film yeniden işlenince özetler üretilir.

### Öneri 3 — Codex penceresi 115 filmi yeniden işle (fix'lerden SONRA)
**Etki: YÜKSEK (115 film) · Efor: DÜŞÜK (batch) — bağımlı**

Önce Öneri 1 + 2 canlı olmalı; sonra `during` penceresindeki 115 filmi (prefilter aktif + kişi-kapısı OFF + propagation authoritative + dil-kodu tam) yeniden koş. Tek başına yeniden-koşma yapma — kök hasar düzelmeden gürültünün yarısı kalır.

### Öneri 4 — QC2 router'a cast-içerik denetimi ekle (false-positive ONAYLI durdur)
**Etki: ORTA-YÜKSEK (route güvenliği) · Efor: DÜŞÜK**

QC2 blok'una deterministik denetim: cast'ta rol-etiketi token (DRIVER/CRAFT/PERFORMED/VFX/PRODUCER/COURTESY) veya garble-oranı > 0 ise tier'i AĞIR'a yükselt, ONAYLI/AUTOFIX'e **asla** düşürme. qwen_qc'ye güvenme. Bu, TAKIM gibi bozuk-ONAYLI vakalarını engeller (MITAS1 riskine karşı).

### Öneri 5 — VL_FALLBACK halüsinasyonunu kökten kes
**Etki: ORTA (25 film) · Efor: DÜŞÜK**

VL-fallback'in döndürdüğü her isim OCR ham metninde ad+soyad bitişik substring olarak DOĞRULANMALI; doğrulanmayan VL ismi REDDEDİLİR. validate ÇELİŞKİ durumunda VL-ismi yerine OCR-okunanı veya boş bırak. JEFF TOWLES tipi uydurma kökten kesilir.

### Öneri 6 — Garble-gate'i lexical'den perplexity/sözlük-oranına çevir
**Etki: ORTA (66 film) · Efor: ORTA**

Memory'deki "okunamadı > yanlış oku" kanununu uygula: `_blur_metric` (stroke_px<~3 + bright%) ile düşük-çözünürlük karesini OCR'a SOKMA → KONTROL. Latin-dışı satırları final cast'tan KES, boş "—" bırak (PROPAGATION+QC1 ile birleşince anlamsız token yerine temiz "—" kalır). PaddleOCR-GPU fallback'ini (codex `a0c28be589` kapattı, memory benchmark: cast %96) yeniden değerlendir.

### Öneri 7 — CREDIT_TEXT rol-overreach kuyruğunu sıkılaştır
**Etki: ORTA (101 film) · Efor: DÜŞÜK**

`credit_text_read.py` rol-eşlemede "DIRECTED BY / A FILM BY" kalıbında yalnız AYNI satır veya HEMEN sonraki TEK satırı al; çoklu-satır kuyruk-taşmasını durdur. Rol-etiketli satırın (GÖRÜNTÜ/IŞIK YÖNETMENİ, ASSISTANT TO, CO-PRODUCER) yönetmen olarak alınmasını etiket-token blacklist ile kesin engelle. Öneri 1 devreye girince validate çift-koruma sağlar.

---

### Özet Yol Haritası

| Sıra | İş | Film | Efor | Bağımlılık |
|---|---|---|---|---|
| 1 | ASR_LANG tek-satır fix (Öneri 2) | 25 | Çok düşük | Yok |
| 2 | PROPAGATION authoritative (Öneri 1) | 189 | Orta | Yok |
| 3 | QC2 router + VL doğrulama (Öneri 4, 5) | 30 | Düşük | Yok |
| 4 | Codex penceresi yeniden-işleme (Öneri 3) | 115 | Düşük | 1+2 |
| 5 | Garble-gate + rol-overreach (Öneri 6, 7) | ~150 | Orta | Yok |

**Tek cümle:** En büyük kazanım codex'i suçlamak değil, doğru-üretilip-atılan değeri (PROPAGATION, 189 film) final'e taşımak ve eksik dil-kodlarını (25 film) eklemektir; bunlar codex-dışı, hâlâ açık ve en yüksek ROI'li işlerdir.