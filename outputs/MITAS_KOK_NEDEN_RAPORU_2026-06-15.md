# MITAS KÖK-NEDEN RAPORU — 14-15 Haziran Batch

_Forensic analiz: 149 problemli film, OneOCR→qwen35b pipeline'ı aşama-aşama izlendi (kanıtlı)._

## 1. MANŞET — Suçlu kim?

Her filmin **baskın** kök-nedenine göre sorumlu aşama:

| Suçlu aşama | Film | Oran |
|---|---|---|
| **qwen 35b** (yorum/rol/temizlik) | **96** | %64 |
| **OneOCR / Frame** (okuma/kare) | 33 | %22 |
| **Kaynak/Dil** (Latin-dışı, künye yok) | 20 | %13 |

**Sonuç:** Sorunların **%64'inde veri OCR'da DOĞRU okunmuş, suçlu qwen 35b** (yanlış role attı / çöpü temizleyemedi / fazla aldı). Bu filmler **yeniden işlemeden**, sadece qwen düzeltilerek kurtarılır.

> **En önemli sayı:** 91 filmde yönetmen verisi zaten OCR'da mevcut (`FROM_EXISTING_OCR`) — qwen düzeltilince re-OCR'sız düzelir.

## 2. BASKIN KÖK-NEDEN DAĞILIMI (her film 1 oy)

| Kod | Açıklama | Suçlu | Film | Oran |
|---|---|---|---|---|
| S2_ROLE_OVERREACH | qwen fazla aldı (doğru+çöp birlikte) | qwen 35b | 63 | %42 |
| S2_ROLE_UNMATCHED | qwen okudu ama role atayamadı | qwen 35b | 26 | %17 |
| S6_NON_LATIN | Latin-dışı alfabe (CJK/Kiril/Arap…) | Kaynak/Dil | 17 | %11 |
| S0_FRAME_MISSING | Frame seçimi kartı kaçırdı (CLIP) | OneOCR/Frame | 13 | %9 |
| S1_OCR_GARBLE | OneOCR okudu ama garble (okuma hatası) | OneOCR/Frame | 11 | %7 |
| S1_STITCH_DROP | Stitch/temizlik satırı düşürdü | OneOCR/Frame | 9 | %6 |
| S4_NOISE_FILTER_MISS | qwen çöpü temizleyemedi | qwen 35b | 6 | %4 |
| S7_SOURCE_MISSING | Kaynakta künye yok | Kaynak/Dil | 3 | %2 |
| S5_LLM_HALLUCINATION | qwen uydurdu (halüsinasyon) | qwen 35b | 1 | %1 |

## 3. ALAN BAZLI KÖK-NEDEN

### 3a. YÖNETMEN

| Kod | Açıklama | Suçlu | Film | Oran |
|---|---|---|---|---|
| S2_ROLE_OVERREACH | qwen fazla aldı (doğru+çöp birlikte) | qwen 35b | 63 | %42 |
| S2_ROLE_UNMATCHED | qwen okudu ama role atayamadı | qwen 35b | 26 | %17 |
| S6_NON_LATIN | Latin-dışı alfabe (CJK/Kiril/Arap…) | Kaynak/Dil | 13 | %9 |
| S0_FRAME_MISSING | Frame seçimi kartı kaçırdı (CLIP) | OneOCR/Frame | 13 | %9 |
| NONE | Sorun yok / doğru | — | 11 | %7 |
| S1_OCR_GARBLE | OneOCR okudu ama garble (okuma hatası) | OneOCR/Frame | 10 | %7 |
| S1_STITCH_DROP | Stitch/temizlik satırı düşürdü | OneOCR/Frame | 9 | %6 |
| S7_SOURCE_MISSING | Kaynakta künye yok | Kaynak/Dil | 2 | %1 |
| S5_LLM_HALLUCINATION | qwen uydurdu (halüsinasyon) | qwen 35b | 2 | %1 |

### 3b. YAPIMCI

| Kod | Açıklama | Suçlu | Film | Oran |
|---|---|---|---|---|
| S2_ROLE_OVERREACH | qwen fazla aldı (doğru+çöp birlikte) | qwen 35b | 41 | %28 |
| S2_ROLE_UNMATCHED | qwen okudu ama role atayamadı | qwen 35b | 31 | %21 |
| NONE | Sorun yok / doğru | — | 25 | %17 |
| S4_NOISE_FILTER_MISS | qwen çöpü temizleyemedi | qwen 35b | 16 | %11 |
| S6_NON_LATIN | Latin-dışı alfabe (CJK/Kiril/Arap…) | Kaynak/Dil | 14 | %9 |
| S1_OCR_GARBLE | OneOCR okudu ama garble (okuma hatası) | OneOCR/Frame | 9 | %6 |
| S0_FRAME_MISSING | Frame seçimi kartı kaçırdı (CLIP) | OneOCR/Frame | 7 | %5 |
| S7_SOURCE_MISSING | Kaynakta künye yok | Kaynak/Dil | 4 | %3 |
| S1_STITCH_DROP | Stitch/temizlik satırı düşürdü | OneOCR/Frame | 2 | %1 |

### 3c. OYUNCULAR (cast)

| Kod | Açıklama | Suçlu | Film | Oran |
|---|---|---|---|---|
| S4_NOISE_FILTER_MISS | qwen çöpü temizleyemedi | qwen 35b | 95 | %64 |
| NONE | Sorun yok / doğru | — | 22 | %15 |
| S6_NON_LATIN | Latin-dışı alfabe (CJK/Kiril/Arap…) | Kaynak/Dil | 11 | %7 |
| S1_OCR_GARBLE | OneOCR okudu ama garble (okuma hatası) | OneOCR/Frame | 9 | %6 |
| S2_ROLE_UNMATCHED | qwen okudu ama role atayamadı | qwen 35b | 5 | %3 |
| S2_ROLE_OVERREACH | qwen fazla aldı (doğru+çöp birlikte) | qwen 35b | 5 | %3 |
| S0_FRAME_MISSING | Frame seçimi kartı kaçırdı (CLIP) | OneOCR/Frame | 2 | %1 |

**Cast gürültü token tipleri** (qwen'in temizlemesi gereken): GARBLE=111, CHARACTER=65, ROLE_LABEL=64, COMPANY=64, FUNDING=35, DISCLAIMER=34, TITLE=31, OTHER=31

## 4. SİSTEMİK KUSUR — QC garble kapısı kör

**25 filmde** `garble_frac≈0` / `bucket=GUVENILIR` raporlandı AMA OCR fiilen garble/Latin-dışı. Garble dedektörü Latin-çöpe ve CJK'ye **kör** → çöp 'güvenilir' damgası alıp pipeline'a giriyor. Bu, qwen'e kirli girdi veren **üst-akış kök-neden**.

Etkilenen (örnek): 1951-1119-1-0000-75-0, 2006-2153-1-0000-70-1, 2008-1004-1-0000-50-1, 2014-1001-1-0000-80-1, 2015-9072-1-0000-90-1, 2017-1138-1-0000-58-0, 2017-9028-1-0000-90-1, 2018-1030-1-0000-90-1, 2018-1046-1-0000-80-1, 2018-1083-1-0000-88-1, 2018-1171-1-0000-90-1, 2018-1199-1-0000-90-1, 2018-1225-1-0000-50-0, 2021-1268-1-0000-50-0, 2022-1006-1-0000-73-0, 2022-1192-1-0000-71-0, 2022-1196-1-0000-80-0, 2023-1018-1-0000-90-1, 2023-1119-1-0000-70-0, 2023-1119-1-0000-70-1…

## 5. DİL/SCRIPT DAĞILIMI

| Script | Film |
|---|---|
| LATIN | 124 |
| MIXED | 10 |
| CJK | 4 |
| ARABIC | 4 |
| CYRILLIC | 4 |
| KOREAN | 3 |

## 6. ÖNCELİKLİ OPTİMİZASYON YOL HARİTASI

| # | Hedef kök-neden | Etki (film) | Düzeltme |
|---|---|---|---|
| 1 | S2_ROLE_OVERREACH | 63 | qwen 'fazla alma' frenli prompt: bir rol etiketinden ('UN FILM DE', 'DIRECTED BY') sonra GELEN satırları otomatik aynı role ekleme; etiket+TEK isim kuralı + sonraki satırı oyuncu/teknik say. |
| 2 | S4_NOISE_FILTER_MISS | 95 | qwen çöp-filtre sözlüğü: COMPANY/FUNDING/DISCLAIMER/ROLE_LABEL kalıpları (FILMS, PICTURES, ASSOCIATION, AVEC, LOTTERY, ©, COURTESY…) cast'tan zorunlu çıkar. |
| 3 | S2_ROLE_UNMATCHED | 26 | qwen rol-eşleme: kunye'de TEMİZ isim var ama atanmadı — etiket tanıma sözlüğünü çok-dilli genişlet (REALISE/REGIA/監督/감독 → yönetmen). |
| 4 | S0_FRAME_MISSING | 13 | CLIP frame seçimi: açılış/kapanış yönetmen kartını kaçırıyor — kredi-kartı kapsamını genişlet (ilk/son N saniye yoğun örnekleme). |
| 5 | S6_NON_LATIN+QC | 17 | Garble kapısını CJK/Kiril/Arap farkındalığıyla güçlendir + Latin-dışı filmde transliterasyon/harici-kimlik yolu; garble_frac'ı script-aware yap. |
| 6 | S1_OCR_GARBLE | 11 | OneOCR okuma: düşük çözünürlük/stilize Latin'de garble — paddle yan-kanal konsensüsü + üst-örnekleme. |

**İlk iki madde (qwen overreach + cast çöp-filtre) ~158 alan-hatasını** tek qwen-prompt revizyonuyla kapatır — en yüksek getiri, sıfır re-OCR.


## 7. FİLM BAZLI DETAY

Tam tablo Excel'de: `QC_KOK_NEDEN.xlsx`. Aşağıda her film tek satır özet:

| Film | Dil | Primary | Suçlu | Yön | Yapımcı | Cast | Tek cümle |
|---|---|---|---|---|---|---|---|
| PUMPKIN 2002-9261-1-0000-00-1 | LATI | S0_FRAME_MISSING | OneOCR/Frame | S0_FRAME_MISSING | S0_FRAME_MISSING | S4_NOISE_FILTER_MISS | Yönetmen ve yapımcı kart(lar)ı hiç yakalanmamış; 596 credit_frames mevcut ama ha |
| BAKIŞ AÇISI 2008-1004-1-0000-50-1 | LATI | S0_FRAME_MISSING | OneOCR/Frame | S0_FRAME_MISSING | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | Yönetmen Pete Travis'in kartı CLIP tarafından seçilmemiş; tüm cast listesi açılı |
| ADAB-I MUAŞERET 2009-9115-1-0000-90-1 | LATI | S0_FRAME_MISSING | OneOCR/Frame | S0_FRAME_MISSING | S2_ROLE_UNMATCHED | S4_NOISE_FILTER_MISS | Yönetmen kartı CLIP tarafından seçilmemiş (53 kreditkare var ama yönetmen sahnes |
| DÜNYANIN MERKEZİNE YOLCULUK - TRT ÇOCU | LATI | S0_FRAME_MISSING | OneOCR/Frame | S0_FRAME_MISSING | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | Yönetmen kartı (Eric Brevig) CLIP tarafından hiç yakalanmamış; teknik ekip isiml |
| SEN ŞARKILARINI SÖYLE 2013-1135-1-0000 | LATI | S0_FRAME_MISSING | OneOCR/Frame | S0_FRAME_MISSING | S0_FRAME_MISSING | S0_FRAME_MISSING | CLIP konser mekan logosu kartını (The Gaslight Cafe 1961) sürekli seçmiş, jeneri |
| AŞK ŞİMDİ 2013-1174-1-0000-50-1 | LATI | S0_FRAME_MISSING | OneOCR/Frame | S0_FRAME_MISSING | S4_NOISE_FILTER_MISS | S4_NOISE_FILTER_MISS | Yönetmen Ol Parker'ın 'DIRECTED BY' çerçevesi kart seçiminde yakalanmamış; yapım |
| UNUTMA BENİ 2014-1009-1-0000-50-1 | LATI | S0_FRAME_MISSING | OneOCR/Frame | S0_FRAME_MISSING | NONE | NONE | Yönetmen kartı (Richard Glatzer & Wash Westmoreland) CLIP tarafından hiç seçilme |
| SESSİZ KIZ 2022-1058-1-0000-80-0 / SES | LATI | S0_FRAME_MISSING | OneOCR/Frame | S0_FRAME_MISSING | NONE | S4_NOISE_FILTER_MISS | İrlanda filmi: yönetmen Colm Bairéad'ın 'Written and directed by' kartı CLIP tar |
| RADYOAKTİF 2022-1194-1-0000-50-0 | LATI | S0_FRAME_MISSING | OneOCR/Frame | S0_FRAME_MISSING | S0_FRAME_MISSING | S2_ROLE_UNMATCHED | Yönetmen (Marjane Satrapi) ve yapımcı açılış kartları hiç yakalanmamış; 589 kare |
| BAŞKA BİR DÜNYA 2023-1054-1-0000-70-0 | LATI | S0_FRAME_MISSING | OneOCR/Frame | S0_FRAME_MISSING | S4_NOISE_FILTER_MISS | S4_NOISE_FILTER_MISS | Fransız filmi; 'UN FILM DE STÉPHANE BRIZÉ' açılış kartı CLIP tarafından seçilmem |
| KOCA SEVİMLİ DEV 2024-1219-1-0000-50-1 | LATI | S0_FRAME_MISSING | OneOCR/Frame | S0_FRAME_MISSING | NONE | NONE | İngilizce film (BFG / Spielberg): 560 kare yakalandı fakat 'DIRECTED BY STEVEN S |
| KAPTAN FANTASTİK 2025-1156-1-0000-50-1 | LATI | S0_FRAME_MISSING | OneOCR/Frame | S0_FRAME_MISSING | S0_FRAME_MISSING | S2_ROLE_OVERREACH | Yönetmen (Matt Ross) ve yapımcı kartı CLIP tarafından hiç seçilmemiş; 528 kare y |
| TERMİNATÖR KARA KADER 2025-1247-1-0000 | LATI | S0_FRAME_MISSING | OneOCR/Frame | S0_FRAME_MISSING | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | CLIP yalnızca filmin VFX sonu kreditlerini seçti; ana jenerik (director/cast/pro |
| ÖZEL BİR ANNE 2001-9022-1-0000-00-1 | LATI | S1_OCR_GARBLE | OneOCR/Frame | S1_OCR_GARBLE | NONE | S4_NOISE_FILTER_MISS | Yönetmen Abbas-Mustan raw OCR'da 'Directed By Abbas-Mustan' olarak okunuyor anca |
| GİZLİ SİLAH 2001-9264-1-0000-00-1 | LATI | S1_OCR_GARBLE | OneOCR/Frame | S1_OCR_GARBLE | S2_ROLE_UNMATCHED | NONE | Yönetmen kartı OCR'da garble ('Hdired By / Daniel Duncan' — editör okunmuş); yap |
| TURİST 2014-1001-1-0000-80-1 | LATI | S1_OCR_GARBLE | OneOCR/Frame | S1_OCR_GARBLE | S1_OCR_GARBLE | S1_OCR_GARBLE | İsveç filmi (Force Majeure) tüm jenerik OCR'ı %39 garble oranıyla anlamsız çıktı |
| KEFERNAHUM 2018-1083-1-0000-88-1 (ocr- | ARAB | S1_OCR_GARBLE | OneOCR/Frame | S1_OCR_GARBLE | S1_OCR_GARBLE | S4_NOISE_FILTER_MISS | Arapça/Fransızca Kefernahum jeneriği Latin harfli OCR'da sistematik garble yaşıy |
| İÇİMDEKİ MİLYONLARCA SEVGİ 2018-1171-1 | MIXE | S1_OCR_GARBLE | OneOCR/Frame | S5_LLM_HALLUCINATION | S1_OCR_GARBLE | S1_OCR_GARBLE | Muhtemelen Çince/Malezya filmi; OCR tüm kredi kartlarını garble okudu, yönetmen  |
| GÖREVİMİZ TEHLİKE 6 YANSIMALAR 2018-11 | LATI | S1_OCR_GARBLE | OneOCR/Frame | S1_OCR_GARBLE | S1_OCR_GARBLE | S4_NOISE_FILTER_MISS | Yönetmen/yapımcı etiketi kartları OCR tarafından hiç okunamamış; oyuncu listesi  |
| ARAMIZDAKİ SÖZLER 2022-1137-1-0000-90- | LATI | S1_OCR_GARBLE | OneOCR/Frame | S1_OCR_GARBLE | NONE | S4_NOISE_FILTER_MISS | Yönetmen Hany Abu-Assad'ın director credit kartı OCR'da 'AKI DIREUIUR UHE!YI IUF |
| YALNIZ ADAM 2023-1018-1-0000-90-1 | LATI | S1_OCR_GARBLE | OneOCR/Frame | S1_OCR_GARBLE | S7_SOURCE_MISSING | S1_OCR_GARBLE | 1955 arsiv filmi: OCR garble sarji hem yonetmen hem oyuncu alanina sizdi; sirket |
| APAÇİ 2023-1019-1-0000-90-1 5 | LATI | S1_OCR_GARBLE | OneOCR/Frame | S1_OCR_GARBLE | S1_OCR_GARBLE | NONE | 1954 yapımı Apache: OCR arşiv yazı tipini kısmen garble okudu; 'DIRECTED BY ROBE |
| BEBEK FİRARDA 2023-1158-1-0000-90-1 | LATI | S1_OCR_GARBLE | OneOCR/Frame | S1_OCR_GARBLE | S1_OCR_GARBLE | NONE | Yönetmen kartı garble zinciri ('DUCTED BY → E AC → WİLLİAM S. BEASLEY') ROLE_MAT |
| AMELIA 2024-1273-1-0000-50-0 | LATI | S1_OCR_GARBLE | OneOCR/Frame | S1_OCR_GARBLE | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | Yönetmen alanına Mira Nair doğru eklendi ancak başlık kartından garble okunan 'M |
| SERPİCO 1973-1008-1-0000-50-0 | LATI | S1_STITCH_DROP | OneOCR/Frame | S1_STITCH_DROP | NONE | S4_NOISE_FILTER_MISS | Yönetmen SIDNEY LUMET ham OCR'da 8+ kez açık görünüyor ancak stitch aşaması ismi |
| PAN'IN LABİRENTİ 2006-1058-1-0000-73-0 | LATI | S1_STITCH_DROP | OneOCR/Frame | S1_STITCH_DROP | S2_ROLE_OVERREACH | S2_ROLE_UNMATCHED | GUILLERMO DEL TORO yönetmen kredisi stitch'te düşürüldü; üretim departman roller |
| PARALEL EVREN 2014-1063-1-0000-50-0 | LATI | S1_STITCH_DROP | OneOCR/Frame | S1_STITCH_DROP | S2_ROLE_OVERREACH | NONE | Ham OCR'da 'directed by JAMES WARD BYRKIT' net okunuyor; stitch/clean aşamasında |
| BEYAZ SAYFA 2015-2233-1-0000-50-0 | LATI | S1_STITCH_DROP | OneOCR/Frame | S1_STITCH_DROP | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | Polonya filmi BEYAZ SAYFA'da asıl yönetmen kartı ('Producent Leszek Bodzak' gibi |
| MUTLU LAZZARO 2018-1133-1-0000-71-0 2 | LATI | S1_STITCH_DROP | OneOCR/Frame | S1_STITCH_DROP | NONE | S4_NOISE_FILTER_MISS | Gerçek yönetmen ALICE ROHRWACHER ('SCRITTO E DIRETTO DA' etiketiyle raw'da 8 kez |
| EVSİZ 2018-2157-1-0000-71-1 | LATI | S1_STITCH_DROP | OneOCR/Frame | S1_STITCH_DROP | S2_ROLE_UNMATCHED | S4_NOISE_FILTER_MISS | Gerçek yönetmen Gian Marco Pezzoli (raw'da 'REGIA/GIAN MARCO PEZZOLI' olarak açı |
| FIRINCININ KARISI 2019-1241-1-0000-91- | LATI | S1_STITCH_DROP | OneOCR/Frame | S1_STITCH_DROP | S2_ROLE_UNMATCHED | S4_NOISE_FILTER_MISS | Üç yönetmenden biri (MURAT ONBUL) stitch aşamasında düşürülmüş; yapımcı alanına  |
| NİNNİ 2022-1006-1-0000-73-0 2 | LATI | S1_STITCH_DROP | OneOCR/Frame | S1_STITCH_DROP | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | Yönetmen kredisi 'Escrita y dirigida por ALAUDA RUIZ DE AZÚA' stitch'te düşürüld |
| SON KELİME 2023-1139-1-0000-50-1 | LATI | S1_STITCH_DROP | OneOCR/Frame | S1_STITCH_DROP | S4_NOISE_FILTER_MISS | S4_NOISE_FILTER_MISS | Gerçek yönetmen MARK PELLINGTON ocr_raw_all.txt'de 17 kez geçmesine karşın kunye |
| KORKUNÇ ŞÜPHE 1981-0312-1-0000-90-1 /  | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | Yönetmen kartında 'RÉALISATION' etiketi OCR'da görünmüyor; role_match 'ADAPTATIO |
| HAYDUT 2001-9241-1-0000-00-1 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S1_OCR_GARBLE | S1_OCR_GARBLE | Yönetmen alanına gerçek yönetmen (BARRY LEVİNSON) doğru okunmuş ancak altındaki  |
| YANLIS NUMARA 2001-9244-1-0000-00-1 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_UNMATCHED | NONE | Yonetmen RICHARD MIDDLETON dogru bulundu ancak 'A FILM BY' blogu kunye'de CAS AN |
| HAVADA İNTİKAM 2001-9284-1-0000-00-1 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | NONE | S4_NOISE_FILTER_MISS | Yönetmen alanına CAST bloğundan BARRY JENNER + JACK MCGEE + 'AS SİMPSON' hatalı  |
| TAKIMADA 2010-1069-1-0000-50-0 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | ART DIRECTOR garble-okunması (AMT DIRECTOR) role_match'i 3 ek kişiyi yönetmen sa |
| MOZART'IN KIZ KARDEŞİ 2010-2184-1-0000 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_UNMATCHED | S4_NOISE_FILTER_MISS | Yönetmen RENE FERET 'UN FILM DE' etiketiyle doğru okundu; ROLE_MATCH karakter ad |
| AZRAİL'İ BEKLERKEN 2011-1068-1-0000-70 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | Fransiz filmi: Marjane Satrapi & Paronnaud kunye.txt satir 5'te temiz var; ROLE_ |
| DEMİR LEYDİ 2011-1127-1-0000-50-1 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S7_SOURCE_MISSING | S4_NOISE_FILTER_MISS | Yönetmen PHYLLIDA LLOYD kunye'de temiz okunmuş ama role_match garble satırlarını |
| YANARDAĞ 2011-2161-1-0000-80-1 (both i | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_UNMATCHED | S4_NOISE_FILTER_MISS | Yönetmen kartı 'WRITTEN AND DIRECTED BY RUNAR RUNARSSON' OCR'da ve kunye'de net  |
| JADOO 2013-1016-1-0000-50-0 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S1_OCR_GARBLE | S4_NOISE_FILTER_MISS | Gerçek yönetmen Amit Gupta hiçbir OCR katmanında yok; 'EPK DİRECTOR' (electronic |
| AŞK BALIK KOKAR 2013-1062-1-0000-50-0 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | NONE | S4_NOISE_FILTER_MISS | Kanada/Ispanya filmi: gercek yonetmen 'A FİLM BY / ANALEİNE CAL Y MAYOR' kunye.t |
| BELLE VE SEBASTIEN 2013-1126-1-0000-90 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_UNMATCHED | S2_ROLE_OVERREACH | Fransiz filminde 'UN FİLM DE NİCALİS VANİER' etiketinin ardindan gelen oyuncu sa |
| SONA DOĞRU 2013-1165-1-0000-50-1 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | Gerçek yönetmen J.C. CHANDOR OCR'ın hiçbir yerinde yok; DIRECTED BY etiketi yok; |
| BABAMIN KAMYONU 2013-2130-1-0000-80-0 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | S4_NOISE_FILTER_MISS | Yönetmen Mauricio Osaki OCR'da doğru okunmuş ancak 'WRITTEN AND DIRECTED BY' eti |
| KELEBEĞİN RÜYASI 2013-9098-1-0000-90-1 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | Yönetmen Çağan Irmak OCR'da hiç yok (başlık karesi yakalanmamış); role_match fra |
| DAĞLARIN KRALİÇESİ 2014-1071-1-0000-80 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_UNMATCHED | S2_ROLE_OVERREACH | Yönetmen SADYK SHER-NIYAZ raw ve kunye'de 'DIRECTED BY' etiketiyle var; ancak ro |
| İNTİKAMIN ÖTESİ 2015-1078-1-0000-90-1 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S1_OCR_GARBLE | S4_NOISE_FILTER_MISS | Yönetmen bloğu fazladan 2 satır çekti (S2_ROLE_OVERREACH); yapımcı garble OCR'da |
| ANNEM 2015-1082-1-0000-50-1 (her iki k | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | İtalyan film Mia Madre: 'un film di' etiketinden sonraki 'con' oyuncu bloğu yöne |
| ARKADAŞIM ÖRDEK 2015-1087-1-0000-91-1 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_UNMATCHED | S4_NOISE_FILTER_MISS | Yönetmen alanına 'UN FILM DE OLİVİER RİNGER' sonrasındaki karakter rolü (LE PERE |
| KARAYİP KORSANLARI-2-ÖLÜ ADAMIN SANDIĞ | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S0_FRAME_MISSING | S4_NOISE_FILTER_MISS | Gerçek yönetmen Gore Verbinski OCR'da hiç yok; role-match ikincil birim teknik k |
| ARAMA MOTORU 2015-9069-1-0000-90-1 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | NONE | S4_NOISE_FILTER_MISS | Yönetmen alanı gerçek yönetmen BARAN SEYHAN'ı doğru içeriyor ancak altında 'UYGU |
| MAUDIE 2016-1002-1-0000-50-0 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | NONE | S4_NOISE_FILTER_MISS | Yönetmen AISLING WALSH doğru okundu; ancak 'EXECUTIVE DIRECTOR / FILM COMMISSION |
| FRANTZ 2016-1188-1-0000-70-0 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | Yönetmen alanına oyuncu ve tekstil şirketi karıştı; yapımcı alanına onlarca tekn |
| İZ-SPOOR 2017-1043-1-0000-80-1 | LATI | S2_ROLE_OVERREACH | qwen 35b | NONE | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | Yönetmen (Zanussi) doğru; PISF jüri üyeleri yapımcı listesine eklendi (S2_ROLE_O |
| AKIL OYUNLARI 2017-1043-1-0000-90-1 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S0_FRAME_MISSING | S4_NOISE_FILTER_MISS | Gerçek yönetmen (Ron Howard) ve yapımcı (Brian Grazer) OCR'a hiç girmedi; ROLE_M |
| JOHNY GUİTAR 2017-1082-1-0000-90-1 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_UNMATCHED | S1_OCR_GARBLE | DIRECTED BY etiketi dogru yakalandi ve Nicholas Ray temiz okundu; ancak ROLE_MAT |
| ESKİ KOCAM(IZ) 2017-1219-1-0000-50-1 2 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | S4_NOISE_FILTER_MISS | DoP etiketi (DIRECTOR OF PHOTOGRAPHY) altındaki sıralı isimler yönetmen olarak a |
| BEYAZ BALİNA 2017-9028-1-0000-90-1 6 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_OVERREACH | S2_ROLE_OVERREACH | TR film BEYAZ BALİNA'da garble-yoğun jenerik okunmuş ancak rol-etiket satırları  |
| KULE 2018-1016-1-0000-50-1 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_OVERREACH | NONE | Gerçek yönetmen Mats Grorud ('A film by' / 'Director and scriptwriter') OCR'da a |
| SİNEK KUŞU 2018-1130-1-0000-76-0 | KORE | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | Kore filmi künye kart başlığı altına dizen role_match, PRODUCED BY altındaki ZOE |
| KRAL LEAR 2018-1225-1-0000-50-0 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | Asistan yönetmen (Juan Miquel Arias) ve casting direktörü (Nina Gold) yönetmen a |
| ÜZGÜNÜZ SİZE ULAŞAMADIK 2019-1092-1-00 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | NONE | S4_NOISE_FILTER_MISS | Yönetmen Ken Loach raw ve kunye OCR'da hiç geçmiyor; 'DIRECTORS' CUT' şirket adı |
| TOMRİS 2019-1096-1-0000-22-0 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S1_STITCH_DROP | NONE | Yönetmen alanına 2. ünite yönetmenleri yazıldı (role overreach); gerçek yönetmen |
| İTALYAN YAZI 2020-1001-1-0000-50-0 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | Yönetmen ve yapımcı alanları Hanway Films satış ekibi ile müzik personelini çekt |
| İTALYAN YAZI 2020-1001-1-0000-50-1 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | Yönetmen alanı Lipsync post-prodüksiyon renklendiricisi ve Hanway satış direktör |
| VAHSI DOSTUM 2020-1183-1-0000-50-0 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_UNMATCHED | S1_OCR_GARBLE | Yonetmen GILLES DE MAISTRE dogru okunmus ama role_match yanina oyuncu ve etiket  |
| LOUIS WAIN'IN RENKLİ DÜNYASI | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | S2_ROLE_UNMATCHED | Yönetmen olarak 'Producers' Assistant' (Ruth Sweeney) atanmış, yapımcı alanına S |
| BUZ YOLU 2021-9033-1-0000-85-1 2 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | NONE | S4_NOISE_FILTER_MISS | Yönetmen kartında 'A FILM BYJONATHAN HENSLEIGH' garble nedeniyle etiket ayrıştır |
| VURGUN 2022-1007-1-0000-78-1 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S1_STITCH_DROP | S4_NOISE_FILTER_MISS | Gercek yonetmen Martijn de Jong stitch surecinde dusuruldu; asistan yonetmenler  |
| SEKİZ DAĞ 2022-1192-1-0000-71-0 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | İtalyanca yabancı dil: 'FINANCE DIRECTORS' etiketi yönetmen, 'VFX PRODUCER' ise  |
| ANILAR 2022-1196-1-0000-80-0 | MIXE | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | S4_NOISE_FILTER_MISS | MEMORIA filmi: İspanyolca 'DIRECTORA GENERAL' post-prodüksiyon etiketi yönetmen  |
| YAŞAMIN KIYISINDA 2023-1045-1-0000-90- | LATI | S2_ROLE_OVERREACH | qwen 35b | NONE | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | Yonetmen (KENNETH LONERGAN) dogru; ancak rol-esleme VFX post-produksiyon yonetic |
| KOVAN 2023-1100-1-0000-80-0 5 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_UNMATCHED | S4_NOISE_FILTER_MISS | Stitch, 'Written and directed by' etiketini mixed-case BLERTA BASHOLLI ile değil |
| GÜL BAHÇESİ 2023-1119-1-0000-70-0 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | Pierre Pinaud OCR'da temiz var ama role_match yönetmen bloğunu 'SCRIPTE' unvanı  |
| GÜL BAHÇESİ 2023-1119-1-0000-70-1 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | Pierre Pinaud OCR'da net mevcut; role_match yönetmen/yapımcıyı yardımcı ekip unv |
| JULIA AND JULIE 2023-1126-1-0000-90-1 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_OVERREACH | NONE | 'A FİLM BY NORA EPHRON' satirini takip eden oyuncu/lokasyon adlari (LE HAVRE, ST |
| KAPTAN BENİM 2023-1128-1-0000-70-1 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | NONE | NONE | Yönetmen MATTEO GARRONE hem ham OCR'da hem kunye.txt'de açıkça var; ancak role-m |
| ÇÖZÜMLER KİTABI 2023-1189-1-0000-70-1 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | NONE | S4_NOISE_FILTER_MISS | Yönetmen MICHEL GONDRY raw ve kunye'de 'UN FILM DE' etiketiyle açık; ancak ROLE_ |
| SANAT OKULU 1994 2023-1219-1-0000-77-1 | MIXE | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | S4_NOISE_FILTER_MISS | Yönetmen yanlış: 'ART ADVISER / LAI BAOER' sanat danışmanı etiketleri yönetmen o |
| MİNARİ 2023-1233-1-0000-76-1 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_UNMATCHED | S4_NOISE_FILTER_MISS | Yönetmen alanına LEE ISAAC CHUNG doğru girdi ama 'ASSISTANT TO DIRECTOR' satırı  |
| BARS 2023-9018-1-0000-85-1 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | NONE | Yönetmen alanına 'Senarist ve Yönetmen' kartındaki ORÇUN KÖKSAL'ın yanı sıra 'Ya |
| AŞKIN GÖZÜ 2024-1061-1-0000-75-0 | MIXE | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | NONE | S6_NON_LATIN | Yönetmen Naomi Kawase doğru yakalanmış ancak 'A FILM BY' bloğunun ardındaki loka |
| MUHAFIZLAR 2024-1186-1-0000-70-1 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | Yönetmen XAVIER BEAUVOIS ve yapımcı SYLVIE PIALAT raw'da temiz okundu; 'SCÉNARİO |
| KOR 2024-1248-1-0000-90-1 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_OVERREACH | NONE | Türkçe film: yönetmen ZEKİ DEMİRKUBUZ OCR'da temiz var ('SENARYO VE YÖNETMEN / W |
| SHERLOCK HOLMES GÖLGE OYUNLARI 2024-12 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_OVERREACH | NONE | Yönetmen alanı GUY RITCHIE yerine kunye.txt'deki garble metin satırlarıyla (ZANP |
| DADI GLORİA 2024-1285-1-0000-70-1 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | NONE | Yönetmen doğru tespit edildi (MARİE AMACHOUKELİ) ancak rol eşleştirici 'ASSISTÉE |
| KÖTÜ ÇOCUK | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_OVERREACH | S2_ROLE_OVERREACH | Yönetmen alanına Pazarlama Direktörü (OZAN GÜLER), yapımcı alanına rol etiketi m |
| SAĞ SAĞLİM 2 SİL BAŞTAN 2024-1312-1-00 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_UNMATCHED | NONE | Stitch hatası: 'YAPIMCI VE YÖNETMEN' etiketi sonraki kart oyuncusu JBURÇİN BİLDİ |
| İNCE SARI ÇİZGİLER 2025-1020-1-0000-80 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | Gerçek film yönetmeni OCR'da etiketsiz; 'Director de Fotografía / Arte' satırlar |
| AİLE GİBİ 2025-1105-1-0000-73-0 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | NONE | S4_NOISE_FILTER_MISS | Arjantin filmi: filmin gercek yonetmen kredi karti (Dirigida por) CLIP tarafinda |
| JACKIE 2025-1143-1-0000-50-0 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_UNMATCHED | S2_ROLE_UNMATCHED | Gerçek yönetmen Pablo Larraín tüm OCR katmanlarında hiç geçmiyor; yönetmen alanı |
| TUNUS' TA BİR DİVAN 2025-1152-1-0000-8 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | NONE | S4_NOISE_FILTER_MISS | Yönetmen kartındaki 'UN FİLM ÉCRİT ET RÉALİSÉ PAR' etiketinin altındaki 3 satır  |
| ASİ KABADAYI 2025-1397-1-0000-90-0 | LATI | S2_ROLE_OVERREACH | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | Yönetmen ve yapımcı kunye'de vardı; ancak rol atama 'THE END' bitiş kartını yöne |
| KÜHEYLAN | LATI | S2_ROLE_UNMATCHED | qwen 35b | S2_ROLE_UNMATCHED | S2_ROLE_UNMATCHED | NONE | Film yönetmeni crediti hiç yakalanmamış (DIRECTED BY etiketi OCR'ın hiçbir yerin |
| CASANOVA 2001-9313-1-0000-00-1 | LATI | S2_ROLE_UNMATCHED | qwen 35b | S2_ROLE_UNMATCHED | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | Yönetmen MARY DİCKİNSON hem stitch hem raw'da 'Produced and Directed by' etiketi |
| RÜZGARA KONUŞANLAR 2002-9260-1-0000-00 | LATI | S2_ROLE_UNMATCHED | qwen 35b | S2_ROLE_UNMATCHED | NONE | S4_NOISE_FILTER_MISS | Yönetmen eksik: John Woo sadece 'Assistants to John Woo' bağlamında OCR'a girdi, |
| YANGIN VAR 2003-9121-1-0000-00-1 | LATI | S2_ROLE_UNMATCHED | qwen 35b | S2_ROLE_UNMATCHED | S2_ROLE_UNMATCHED | S4_NOISE_FILTER_MISS | Bosnian filmde yönetmen Jasna ŽALICA OCR'da oyuncu olarak onlarca kez geçiyor an |
| KAR 2008-2022-1-0000-61-0 | LATI | S2_ROLE_UNMATCHED | qwen 35b | S2_ROLE_UNMATCHED | S2_ROLE_OVERREACH | S0_FRAME_MISSING | Boşnakça jenerik: yönetmen Aida Begić adı OCR'ın hiçbir yerinde yok; yapımcı ala |
| GÜZEL AİLELER 2015-2158-1-0000-70-0 | LATI | S2_ROLE_UNMATCHED | qwen 35b | S2_ROLE_UNMATCHED | S2_ROLE_UNMATCHED | S4_NOISE_FILTER_MISS | Fransız filmin 'Produit par' yapımcısı (Michele et Laurent Petin) OCR'da net oku |
| YENI HAYAT 2015-9072-1-0000-90-1 | LATI | S2_ROLE_UNMATCHED | qwen 35b | S2_ROLE_UNMATCHED | NONE | S4_NOISE_FILTER_MISS | Yonetmen F. SERKAN ACAR raw OCR'da net okunuyor ancak etiket 'Y TM N' (garble) o |
| HANNAH'NIN KANUNU 2017-1052-1-0000-90- | LATI | S2_ROLE_UNMATCHED | qwen 35b | S2_ROLE_UNMATCHED | S4_NOISE_FILTER_MISS | S4_NOISE_FILTER_MISS | Yönetmen kartı (Lucy Talalay) hiç yakalanmamış — raw ve kunye'de yönetmen etiket |
| NAR BAĞI 2017-1109-1-0000-50-0 | LATI | S2_ROLE_UNMATCHED | qwen 35b | S2_ROLE_UNMATCHED | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | Ham OCR Azerbaycan dilinde lowercase: 'Quruluşçu rejissor / Ilgar Necef' (=yönet |
| ZAVALLI 2018-1193-1-0000-74-1 | MIXE | S2_ROLE_UNMATCHED | qwen 35b | S2_ROLE_UNMATCHED | S2_ROLE_UNMATCHED | S4_NOISE_FILTER_MISS | Yunan filmi: yönetmen ΜΠΑΜΠΗΣ ΜΑΚΡΙΔΗΣ kunye.txt'de Yunanca etiketle mevcut ama  |
| HÜCRE BLOĞU 99'DA KATLİAM 2019-1241-1- | LATI | S2_ROLE_UNMATCHED | qwen 35b | S2_ROLE_UNMATCHED | S2_ROLE_UNMATCHED | NONE | Yönetmen S. Craig Zahler kunye.txt'de yalnız 'WRITTEN BY' etiketi altında geçiyo |
| ARAKÇILAR 2019-1260-1-0000-75-0 | LATI | S2_ROLE_UNMATCHED | qwen 35b | S2_ROLE_UNMATCHED | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | Yönetmen 'Kore-eda Hirokazu' kunye.txt satır 190'da 'ORIGINAL STORY...DIRECTED B |
| GAGARİN 2020-1090-1-0000-70-1 | LATI | S2_ROLE_UNMATCHED | qwen 35b | S2_ROLE_UNMATCHED | S2_ROLE_UNMATCHED | S4_NOISE_FILTER_MISS | Gerçek yönetmenler 'UN FILM DE' bloğundan alınmadı, yanlış 'MISE EN SCENE' asist |
| NEREYE GİDİYORSUN AIDA 2020-1157-1-000 | LATI | S2_ROLE_UNMATCHED | qwen 35b | NONE | S2_ROLE_UNMATCHED | NONE | Yapımcı DAMIR IBRAHIMOVIC hem ham OCR'da ('PROOUCERS / PRODUCENTI' etiketi altın |
| BELFAST 2021-1268-1-0000-50-0 | LATI | S2_ROLE_UNMATCHED | qwen 35b | S2_ROLE_UNMATCHED | S2_ROLE_UNMATCHED | S4_NOISE_FILTER_MISS | Belfast'ta yonetmen 'A KENNETH BRANAGH Film' cok-satirli formatiyla geldi; ROLE_ |
| ÇİT 2023-1000-1-0000-80-1 | LATI | S2_ROLE_UNMATCHED | qwen 35b | S2_ROLE_UNMATCHED | S2_ROLE_OVERREACH | NONE | Yönetmen Phillip Noyce raw OCR'da sadece 'Assistant to Phillip Noyce' rol-etiket |
| KORO 2023-1141-1-0000-50-1 | LATI | S2_ROLE_UNMATCHED | qwen 35b | S2_ROLE_UNMATCHED | NONE | S4_NOISE_FILTER_MISS | Yönetmen FRANÇOISE GIRARD hem raw OCR'da hem kunye.txt'de mevcut ama 'directed b |
| EJDER KILICI 2023-1146-1-0000-90-1 | LATI | S2_ROLE_UNMATCHED | qwen 35b | S2_ROLE_UNMATCHED | S4_NOISE_FILTER_MISS | S4_NOISE_FILTER_MISS | Yönetmen DANIEL LEE raw'da 'Written and Directed by' etiketiyle açıkça var ama r |
| DEVE GÖZÜ - ATEŞ 2024-1004-1-0000-70-1 | MIXE | S2_ROLE_UNMATCHED | qwen 35b | S2_ROLE_UNMATCHED | S7_SOURCE_MISSING | S4_NOISE_FILTER_MISS | Yönetmen L. ŞEPİTKO kunye'de etiketli olarak okunmuş ama role_match final'e taşı |
| ADEM OĞLU ABU 2024-1033-1-0000-79-0 | LATI | S2_ROLE_UNMATCHED | qwen 35b | S2_ROLE_UNMATCHED | NONE | NONE | Yönetmen ABU SALİM KUMAR hem ham OCR'da hem kunye.txt'de 'STORY,SCREENPLAY,DIALO |
| KAOS 2024-1349-1-0000-90-1 3 + 4 (ayni | LATI | S2_ROLE_UNMATCHED | qwen 35b | S2_ROLE_UNMATCHED | S2_ROLE_UNMATCHED | NONE | 'A TONY GIGLIO FILM' kalibini ROLE_MATCH yonetmen etiketi olarak taniyamadi; fil |
| BÜYÜK BABAMLA ODA SAVAŞI 2025-1036-1-0 | LATI | S2_ROLE_UNMATCHED | qwen 35b | S2_ROLE_UNMATCHED | S2_ROLE_UNMATCHED | S4_NOISE_FILTER_MISS | Yönetmen ve yapımcı alanları boş çünkü 'DIRECTED BY' etiketi raw OCR'da yok; cas |
| KURALLAR BUNLAR 2025-1110-1-0000-63-0 | LATI | S2_ROLE_UNMATCHED | qwen 35b | S2_ROLE_UNMATCHED | S2_ROLE_UNMATCHED | S4_NOISE_FILTER_MISS | Hırvatça yapım (Takva su Pravila): 'scenarist i redatelj'=yönetmen ve 'producent |
| GELECEĞİN SAVAŞI 2025-1215-1-0000-90-1 | LATI | S2_ROLE_UNMATCHED | qwen 35b | S2_ROLE_UNMATCHED | NONE | S2_ROLE_UNMATCHED | Film başlığı THE TOMORROW WAR yönetmen alanına atandı; gerçek yönetmen CHRIS McK |
| ROCKY 4 2025-1427-1-0000-50-1 | LATI | S2_ROLE_UNMATCHED | qwen 35b | S2_ROLE_UNMATCHED | S4_NOISE_FILTER_MISS | S4_NOISE_FILTER_MISS | Stallone raw OCR'da sadece oyuncu olarak görünüyor, yönetmen etiket kartı yok; m |
| BUCKLEY'İN ŞANSI 2025-1439-1-0000-50-1 | LATI | S2_ROLE_UNMATCHED | qwen 35b | S2_ROLE_UNMATCHED | S2_ROLE_UNMATCHED | S4_NOISE_FILTER_MISS | Yönetmen ve yapımcı alanlarına SPECIAL THANKS / teknik ekip isimleri atandı; ger |
| YANKESİCİLERİN MOZART'I 2006-2153-1-00 | LATI | S4_NOISE_FILTER_MISS | qwen 35b | NONE | NONE | S4_NOISE_FILTER_MISS | Yonetmen ve yapimci dogru cozuldu; ancak Fransizca finansman etiketleri (CANAL+, |
| İNATÇILAR 2015-1083-1-0000-80-1 | LATI | S4_NOISE_FILTER_MISS | qwen 35b | NONE | S4_NOISE_FILTER_MISS | S1_OCR_GARBLE | Yönetmen doğru (GRIMUR HAKONARSON raw+kunye'de açık); yapımcı alanına co-product |
| DUNKIRK 2017-1058-1-0000-50-1 | LATI | S4_NOISE_FILTER_MISS | qwen 35b | S2_ROLE_OVERREACH | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | Yönetmen ve yapımcı kunye'de doğru okunmuş ama role_match adanma yazısı ve exec  |
| ÇALIŞMAK İÇİN GÜZEL BİR GÜN 2018-1111- | LATI | S4_NOISE_FILTER_MISS | qwen 35b | NONE | S0_FRAME_MISSING | S4_NOISE_FILTER_MISS | Boşnak filmi: yönetmen doğru çıkmış; ancak yapımcı karesi yakalanmamış (S0) ve o |
| PARALEL YAŞAMLAR 2021-2195-1-0000-70-1 | LATI | S4_NOISE_FILTER_MISS | qwen 35b | NONE | NONE | S4_NOISE_FILTER_MISS | Restorasyon bildirimi satırları (CINE-TAMARIS, VARDA SUPERVISED THE GRADING, ELL |
| GÖLGE SAVAŞÇI 2022-1150-1-0000-75-1 2 | LATI | S4_NOISE_FILTER_MISS | qwen 35b | NONE | S2_ROLE_UNMATCHED | S4_NOISE_FILTER_MISS | Yönetmen Kurosawa doğru; yapımcı TOMOYUKI TANAKA ham OCR'da executive producer o |
| ÇILDIRIŞ 2025-1142-1-0000-50-1 | LATI | S5_LLM_HALLUCINATION | qwen 35b | S5_LLM_HALLUCINATION | S2_ROLE_UNMATCHED | S1_OCR_GARBLE | İngiliz filmi (The Jacket): 'DIRECTED BY JOHN MAYBURY' kartı OCR'a girmediğinden |
| ERKEN GELEN YAZ 1951-1119-1-0000-75-0 | CJK | S6_NON_LATIN | Kaynak/Dil | S6_NON_LATIN | S6_NON_LATIN | S6_NON_LATIN | 1951 Japon filmi (Ozu), jenerik tamamen CJK; garble_frac=0.0 çünkü Latin-garble  |
| İÇ İŞLERİ 2 2003-9101-1-0000-00-1 | CJK | S6_NON_LATIN | Kaynak/Dil | S6_NON_LATIN | S6_NON_LATIN | S1_OCR_GARBLE | Hong Kong Kantonca filmi; CJK kredi kartları OneOCR tarafından okunamamış, Latin |
| AMİRAL 2008-1074-1-0000-72-1 | MIXE | S6_NON_LATIN | Kaynak/Dil | S2_ROLE_UNMATCHED | S6_NON_LATIN | S6_NON_LATIN | Rusça film: yönetmen 'IN A TILM BY' (FILM→TILM OCR hatası) nedeniyle ROLE_MATCH  |
| KEŞKE 2011-1043-1-0000-75-0 | CJK | S6_NON_LATIN | Kaynak/Dil | S6_NON_LATIN | S6_NON_LATIN | S4_NOISE_FILTER_MISS | Hirokazu Kore-eda'nın Japonca jeneriği (監督·脚本·編集 是枝裕和) OCR'da CJK olarak doğru o |
| TARİHSİZ İMZASIZ 2017-1098-1-0000-56-1 | ARAB | S6_NON_LATIN | Kaynak/Dil | S6_NON_LATIN | S6_NON_LATIN | S4_NOISE_FILTER_MISS | İran filmi; tüm künye Farsça/Arapça alfabeyle yazılmış; OCR Farsça metni okudu a |
| SÖZ 2018-1030-1-0000-90-1 | KORE | S6_NON_LATIN | Kaynak/Dil | S6_NON_LATIN | S6_NON_LATIN | S6_NON_LATIN | Korece film (감독 박홍수 / 최승현 TOP); tüm künye Kore alfabesiyle yazılı, Latin-OCR bun |
| İLK VEDA 2018-1046-1-0000-80-1 2 | MIXE | S6_NON_LATIN | Kaynak/Dil | S6_NON_LATIN | S6_NON_LATIN | S6_NON_LATIN | Tamil filminin kredi kartları Çince script içeriyor; garble_frac 0.57 ile ZOR bu |
| 3 HAYAT 2018-1051-1-0000-56-0 | MIXE | S6_NON_LATIN | Kaynak/Dil | NONE | S2_ROLE_OVERREACH | S6_NON_LATIN | Yönetmen 'A Film By' etiketiyle doğru OCR edildi; yapımcı set-tasarımcısı ve pos |
| 6,5 METRE 2019-1039-1-0000-56-1 | MIXE | S6_NON_LATIN | Kaynak/Dil | NONE | S2_ROLE_UNMATCHED | S4_NOISE_FILTER_MISS | Yönetmen Türkçe 'YAZAN VE YÖNETEN' etiketiyle doğru okundu; yapımcı Farsça satır |
| DOLUNAY ZAMANI 2019-1055-1-0000-50-0 | ARAB | S6_NON_LATIN | Kaynak/Dil | S6_NON_LATIN | S6_NON_LATIN | S6_NON_LATIN | İran filmi; jenerik kredileri tamamıyla Arapça/Farsça harflerle; 395 kare yakala |
| BEYAZ BALON 2021-2164-1-0000-56-0 | ARAB | S6_NON_LATIN | Kaynak/Dil | S6_NON_LATIN | S6_NON_LATIN | S6_NON_LATIN | İran filmi 'Bādkonake Sefid' jenerik yazıları tamamen Arapça/Farsça alfabeyle ol |
| BEBEK KUTUSU 2022-1066-1-0000-76-1 | KORE | S6_NON_LATIN | Kaynak/Dil | S6_NON_LATIN | S4_NOISE_FILTER_MISS | S6_NON_LATIN | Korece film: yonetmen ve ana kadronun buyuk kismi Hangul kredilerinde kaldi, OCR |
| CEVİZ AĞACI 2022-1119-1-0000-22-0 | CYRI | S6_NON_LATIN | Kaynak/Dil | S6_NON_LATIN | S6_NON_LATIN | S6_NON_LATIN | Tüm künye Kiril Kazakçasıyla yazılı; 'Коюшы режиссер = Ерлан Нурмухамбетов' ve o |
| KLONDİKE 2023-1161-1-0000-90-1 | CYRI | S6_NON_LATIN | Kaynak/Dil | S2_ROLE_OVERREACH | S6_NON_LATIN | S4_NOISE_FILTER_MISS | Ukraynaca film (Maryna Er Gorbach yönetmen): künye baskın Kiril alfabesinde; yön |
| ŞAMBALA 2024-1028-1-0000-23-0 | CYRI | S6_NON_LATIN | Kaynak/Dil | S6_NON_LATIN | S6_NON_LATIN | S6_NON_LATIN | Kırgız filmi (Kiril alfabesi); OCR tüm metni doğru okudu ancak ROLE_MATCH Latin  |
| GEÇ GELEN BAHAR 2024-1124-1-0000-75-0 | CJK | S6_NON_LATIN | Kaynak/Dil | S6_NON_LATIN | S6_NON_LATIN | S4_NOISE_FILTER_MISS | 1949 Japon filmi; künye CJK karakterle yazılı, yönetmen Yasujiro Ozu ve yapımcı  |
| BEYAZ GEMİ 2025-1026-1-0000-23-1 | CYRI | S6_NON_LATIN | Kaynak/Dil | S6_NON_LATIN | S6_NON_LATIN | S4_NOISE_FILTER_MISS | Kırgız-Sovyet filmi BEYAZ GEMİ'nin jenerik yazıları Kiril alfabesiyle; yönetmen  |
| PAKET KAHVE 2014-2132-1-0000-73-0 | LATI | S7_SOURCE_MISSING | Kaynak/Dil | S7_SOURCE_MISSING | S2_ROLE_OVERREACH | S4_NOISE_FILTER_MISS | ESCAC kısa filminde yönetmen kartı OCR'a hiç girmedi; yapımcı yanlış ('THE TREES |
| REHİNELER 2017-1138-1-0000-58-0 [insta | LATI | S7_SOURCE_MISSING | Kaynak/Dil | S7_SOURCE_MISSING | S4_NOISE_FILTER_MISS | S4_NOISE_FILTER_MISS | Yönetmen kartı tüm üç OCR çalışmasında sıfır — kaynak filmde Latince yönetmen et |
| DÜNYANIN PARASI 2024-1083-1-0000-50-1 | LATI | S7_SOURCE_MISSING | Kaynak/Dil | NONE | S7_SOURCE_MISSING | S4_NOISE_FILTER_MISS | Yönetmen doğru (RİDLEY SCOTT); yapımcı kişi kredisi kapanış jeneriğinde yer alma |