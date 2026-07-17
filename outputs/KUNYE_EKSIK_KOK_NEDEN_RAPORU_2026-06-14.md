# MİTAS — Eksik Künye Kök-Neden Raporu
*Üretim: 2026-06-14 · Kaynak: E:\MITAS\Database · Orijinal pipeline çıktısı (kunye_teslim.md = kunye.pdf)*

## 1. Özet
- **Taranan film/klasör:** 438
- **Eksik (flagli):** 250  ·  **Temiz:** 188
  - Yönetmen boş: 133  ·  Yapımcı boş: 131  ·  Cast ≤ 6: 107  ·  Hiç çıktı yok: 13
- **Kök-neden teşhisi:** 243 eksik film, her biri ham OCR'a inilerek pipeline adımına bağlandı; 162'i bağımsız 2. ajanla çapraz-doğrulandı.
- **Düzeltilebilirlik katmanı:**
  - 🟢 **Katman A — Mevcut OCR'dan kurtarılabilir (yeniden-işleme YOK): 116 film.** Veri zaten kunye.txt/ham OCR'da; sadece seçim/atama/filtre yanlış.
  - 🟡 **Katman B — Yeniden-işleme gerek: 77 film.** İsim mevcut OCR'da yok; daha sık kare / daha iyi kare-seçim / OCR yeniden koşmalı (veya yarım işlem tamamlanmalı).
  - ⚪ **Katman C — Dış-veri/gerçek-eksik (pipeline kusuru değil): 50 film.** Yabancı jenerik veya alan gerçekten yok → web/KB ile doldurulur ya da olduğu gibi doğrudur.

> **Yöntem notu & düzeltme (şeffaflık):** Tespit deterministik yapıldı (438 klasörde hiçbir film atlanmasın + cast sayımı birebir doğru olsun diye, 4 LLM ajanı yerine). Sebep teşhisi 50+ Sonnet ajanı + çapraz-doğrulama ile yapıldı. İlk turda isim-OCR eşleştirmesini ad/soyadı **ayrı token** arayarak yaptım; bu **yanlış-pozitif** üretti (ör. "Yılmaz Erdoğan" → grip "Erdoğan Gündoğdu"). Kusur bulununca matcher **ad+soyad bitişik** şartına çevrildi (yönetmen isimlerinin %17'si düzeldi), ajan prompt'u sertleştirildi ve tüm teşhis **temiz veriyle baştan** koşuldu. Bu rapor düzeltilmiş veriye dayanır.

## 2. Kök-Neden Dağılımı (pipeline adımına göre)

| Adım kodu | Katman | Pipeline yeri | Film | Anlamı |
|---|:--:|---|---:|---|
| **S2_ROL_ESLEME** | A | Aşama 2 (credit_text_read/rol) | 90 | İsim filtreli kunye.txt'de VAR ama rol-eşleme adımı final'e yanlış aldı/atladı (cast↔yönetmen↔yapımcı takası, üst-billing'i tanıyamama) |
| **S1_FRAME_KAPSAM** | B | Aşama 1 (kare-seçim/CLIP) | 52 | Kare var ama yönetmen/cast kartı yakalanan karelerin dışında / düşük-kontrast diegetik (canlı sahne üstü yazı) jenerik sayılmamış → isim OCR'a hiç girmemiş |
| **S1_OCR_OKUYAMADI** | B | Aşama 1 (OCR motoru) | 18 | Karede yazı var ama OCR motoru okuyamadı/çöp okudu (arşiv/düşük kalite/yabancı alfabe) |
| **GARBLE_KONTAMINASYON** | A | Aşama 1-2 | 14 | Final alanı garble/şirket-adı/başlık ile dolmuş (filtre+rol garble'ı geçirdi) |
| **S1_FILTRE_DUSURDU** | A | Aşama 1 (stitch/clean) | 11 | İsim ham OCR'da bitişik VAR ama temizleme/garble filtresi kunye.txt'ye geçirmeden düşürdü |
| **S5_6_QC_DUSURDU** | A | Aşama 5-6 (QC) | 1 | Değer vardı ama QC kapısı (garble/çelişki/charset) boşa/Kontrol'e düşürdü |
| **S0_CIKTI_YOK** | B | Aşama 0/sonrası | 7 | Çıktı yok — pipeline künye/PDF adımına gelmeden kesilmiş (yarım işlem) |
| **GERCEKTEN_YABANCI** | C | — | 39 | Film gerçekten yabancı; jenerik yabancı-dilde, Türkçe rol etiketi yok → pipeline yabancı şirket metni okudu. Pipeline kusuru DEĞİL; dış-veri/web gerekir |
| **GERCEKTEN_YOK** | C | — | 11 | İlgili alan jenerikte gerçekten yok (eski film, ayrı yapımcı yok vb.) → gerçek eksiklik, hata değil |
| **TOPLAM** | | | **243** | A=116 · B=77 · C=50 |

## 3. En Kritik İki Pipeline Hatası

**① S2_ROL_ESLEME (90 film) — en büyük tek hata sınıfı.** İsim OCR'da okunmuş, filtreyi geçip `kunye.txt`'ye girmiş, ama final künyeye yanlış alınmış: ya rol takası (oyuncu→yönetmen yazılmış, gerçek yönetmen düşmüş), ya üst-billing oyuncu bloğu (rol-etiketsiz, yabancı-dil karma) tanınmayıp sadece "ADDITIONAL CAST" bloğu alınmış. **Kurtarılabilir — veri elimizde, sadece seçim/atama yanlış.**

**② S1_FRAME_KAPSAM (52 film) — ikinci büyük, mimari kör nokta.** Jenerik siyah-karta değil canlı sahne üstüne düşük-kontrastlı biniyor (diegetik) ya da yönetmen kartı yakalanan karelerin dışında kalıyor. Pipeline'ın CLIP kare-seçimi bunları "jenerik değil" sayıp atlıyor → isim OCR'a **hiç girmiyor**. KELEBEĞİN RÜYASI tam bu sınıf.

## 4. Elle Doğrulanmış Vaka Çalışmaları

**KELEBEĞİN RÜYASI (2013-9098)** — *senin örneğin.* Kareler tam (360 giriş + 480 çıkış). Yönetmen **Yılmaz Erdoğan pipeline OCR'ında YOK**; ama kareyi taze OCR'layıp gözle bakınca **g_0103–g_0109'da net** ("...and YILMAZ ERDOĞAN", tren penceresi üstü düşük-kontrast diegetik). Cast (Belçim Bilgin, Mert Fırat→"MO JIRAT", Farah Zeynep→Yunan-glyph) okunmuş ama final'e ekip-ünvanları yazılmış. → **S1_FRAME_KAPSAM (yönetmen) + S2_ROL_ESLEME (cast).**

**GÖZEMLİ GÖZ / The Touch (1973-0220)** — Gerçek yönetmen "Peter Pau" hem ham OCR'da hem `kunye.txt`'de **bitişik var**, ama final yönetmen alanına oyuncular (Michelle Yeoh, Ben Chaplin) yazılmış, Peter Pau düşmüş. → **S2_ROL_ESLEME (saf rol-takası).**

**ANILAR / Memoria (2022-1196)** — Gerçekten yabancı (İspanyolca/İngilizce jenerik, Tilda Swinton). Pipeline şirket adlarını cast/yönetmen sanmış. → **GERCEKTEN_YABANCI (pipeline-bug değil; web/KB gerek).**

**DİNLE NEYDEN (2010-9274)** — Orijinal çıktı: 1 cast, yönetmen/yapımcı boş. Düzeltme verisi gerçek 8 cast + yönetmen Jacques Deschamps + yapımcı Özkul Eren içeriyor → veri kurtarılabilirdi.

**13 → 7 ÇIKTI-YOK** — Hepsi son 1-3 günde içe alınmış (bazıları `_2/_3` kopya); OCR var ama künye→PDF adımı henüz koşmamış. **Künye hatası değil, işlem yarım** (canlı batch + Database konsolidasyonu sürüyordu). Batch bitince yeniden bakılmalı.

## 5. Film Listeleri (adım bazlı)

### 5A. PIPELINE HATALARI (kurtarılabilir)

### S2_ROL_ESLEME — okundu, filtreyi geçti, final'de yanlış/atlandı  (90 film)

| Başlık | TRT | Eksik | Güven | Kanıt (özet) |
|---|---|---|---|---|
| 3. GÖZ | 2000-0286-1-0000-40-1 | yapimci | yuksek | grep 'SAM +RAIMI' ocr_raw_all.txt → 0. grep 'TOM +ROSENBERG' → 0; 'Assistants to Mr. Rosenberg' ocr_ham satır 228. grep 'JAMES +JACKS' → 0. ocr_ham satır 26-29… |
| 9.BÖLÜK | 2011-9195-1-0000-90-1 | yonetmen, cast | yuksek | kunye.txt satır 59='РЕЖИССЕР-ПОСТАНОВЩИК ФЕДОР БОНДАРЧУК' bitişik. ocr_ham.txt satır 59='Режиссер-постановщик Федор Бондарчук' bitişik. kunye.txt satır 1-28 Ki… |
| ADEM OĞLU ABU | 2024-1033-1-0000-79-0 | yonetmen | yuksek | ocr_ham satır 86-91 (okundu): 'Produced byur / Salim Ahamed / Ashraf Bedi / Story,Screenplay,dialogues & Direction / 10 / cast'. kunye.txt satır 53-56: 'PRODUC… |
| AMİRAL | 2008-1074-1-0000-72-1 | yonetmen, cast | yuksek | andrei +kravchuk bitişik grep: kunye.txt satır 43 'ANDREİ KRAVCHUK' eşleşti; ocr_ham.txt satır 43 'ANDREI KRAVCHUK' eşleşti. kunye.txt satır 42: 'IN A TILM BY'… |
| ANLAŞMA | 2004-9096-1-0000-00-1 | yonetmen | yuksek | ocr_raw_all.txt satır 32-34: 'A', 'K.C. BASCOMBE', 'FILM' — üç ayrı satır; tek satırda bitişik değil. kunye.txt satır 10: 'K.C. BASCOMBE', satır 1: '1ST ASSİST… |
| ARAKÇILAR | 2019-1260-1-0000-75-0 | yonetmen | yuksek | kunye.txt satır 190: 'ORİGİNAL STORY, SCREENPLAY, EDİTED AND DİRECTED BY KORE-EDA HİROKAZU' (bitişik ad+soyad DOĞRULANDI). ocr_ham.txt satır 245: 'Original Sto… |
| ARAMA MOTORU | 2015-9069-1-0000-90-1 | cast | yuksek | ocr_ham satır 6: 'written & directed by', satır 7: 'ATALAY TAŞDİKEN', satır 8: 'yazan / yoneten', satır 9: 'ATALAY TAŞDİKEN', satır 10: 'BARAN SEYHAN'. kunye.t… |
| ARKA SOKAKLAR | 1963-0004-1-000-00-1 | yonetmen, yapimci | yuksek | Grep 'ÜLKÜ.{0,5}ERAKALIN' → ocr_raw_all.txt satır 582-608 (14 hit), kunye.txt satır 44 (1 hit), kunye_teslim.md sıfır. Grep 'NEVZAT.{0,5}PESEN' → ocr_raw_all.t… |
| ARKADAŞIM ÖRDEK | 2015-1087-1-0000-91-1 | yapimci | yuksek | grep 'yves +ringer' ocr_ham.txt → satır 56: 'YVES RINGER & ANTOINE SIMKINE' (satır 55: 'PRODIICTE UR ASSOOE'), satır 218: 'YVES RINGER'. grep 'antoine +simkine… |
| ATEŞ KAPANI | 2001-9282-1-0000-00-1 | cast | yuksek | grep MEL HARRİS kunye.txt → satır 20 (bitişik). grep LORİ PETTY kunye.txt → satır 25. grep VANESSA ANGEL kunye.txt → satır 12. grep RİCHARD TYSON kunye.txt → s… |
| ATTİLA MARCEL | 2013-1015-1-0000-70-0 | cast, yapimci, yonetm… | yuksek | kunye.txt satır 41='POUİ /ALLİKİ MOREEL GUILLAUME GOUİX', satır 42='MADOME FROUST ANNE LE NT', satır 43='TOAEDE ARNİE BERMADETTE LAFONT', satır 44='TANTE ANNA … |
| AY PİLOTU | 1962-0038-1-0000-00-1 | yonetmen_temiz, yapim… | yuksek | kunye.txt sat.63: 'DİRECTED BY'; sat.64: 'JAMES NEİLSON'; sat.65: 'THE END'; final yönetmen='JAMES NEİLSON, THE END'; kunye.txt sat.32: 'RON MİLLER'; sat.33: '… |
| AŞKIN GÖZÜ | 2024-1061-1-0000-75-0 | cast | yuksek | ocr_ham satır 26-27: 'a film by / NAOMI KAWASE'; satır 96-97: 'MUSIC BY / IBRAHIM MAALOUF'. kunye.txt satır 13-16: 'A FİLM BY / NAOMİ KAWASE / NARA STATİO / GU… |
| AŞKIN GÜCÜ | 1999-0484-1-0000-00-1 | yonetmen, yapimci | yuksek | kunye.txt son satır (53): bytes b'M\xc4\xb0CH\xc4\xb0 R\xc4\xb0EBL\r\n' — Python utf-8 okuma: 'MİCHİ RİEBL'. ocr_raw_all satır 500: 'REOTE', 501: 'Michi Riebl'… |
| BAXTER | 1989-0347-1-0000-00-1 | cast_az | yuksek | kunye.txt satır 16 = 'ET JEROME BOIVIN', satır 37 = 'JACQUES AUDIARD ET JEROME BOIVIN'; ocr_ham.txt satır 67-68 = 'un film de / JEROME BOIVIN'; dir_presence in… |
| BAŞARININ SIRRI | 1987-0374-1-0000-00-1 | yonetmen | yuksek | ocr_raw_all.txt satır 1938/1964/...: 'Assistant to Herbert Ross'; ocr_ham.txt satır 67: 'First Assistant Director ROBERT V. GIROLAMI'; 'DIRECTED BY' grep ocr_h… |
| BELLE VE SEBASTIEN | 2013-1126-1-0000-90-1 | yapimci | yuksek | ocr_ham.txt satır 64: 'Phiippe Gautier', satır 65: 'Wassia Kaial' — bitişik, etiket yok. kunye.txt satır 43: 'UUT NATİONS DE L'AUDOVİSUEL D 1965', satır 44: 'P… |
| BEYAZ SARAYDA CİNAYET | 1997-0284-1-0000-00-1 | yonetmen, yapimci | yuksek | kunye.txt satır 1: 'WASHINGTON, D.C. UNIT'; satır 2: 'AN ARNOLD KOPELSON PRODUCTION'; satır 3: 'A DWIGHT LITTLE FILM'. ocr_ham.txt satır 7: 'AN ARNOLD KOPELSON… |
| BUCKLEY'İN ŞANSI | 2025-1439-1-0000-50-1 | yonetmen, cast | yuksek | ocr_raw_all.txt 6.864 satırda 'DIRECTED' sıfır hit, 'MULCAHY' 13 hit — hepsi SPECIAL THANKS bölümünde (PowerShell satır 6091 örnek: 'SPECIAL THANKS / ... / RUS… |
| BİR MİLYONERLE NASIL EVLENİLİR (How to … | 1953-0038-1-0000-00-1 | yapimci, gercek_cast,… | yuksek | ocr_ham.txt satır 44: 'ses lendirme yönetmeni', satır 45: 'BİRKAN AKAY' (bitişik bağlam); ocr_ham.txt grep 'jean negulesco|negulesco|marilyn monroe|monroe mari… |
| BİR SEVGİ İSTİYORUM | 1988-0384-1-0000-00-1 | yapimci | yuksek | kunye.txt satır 1 = 'EDİE LANDAU'; final yapimci = ''; dir_presence in_raw=false (David Jones ham OCR'da yok — bitişik grep: 0 sonuç); cast_presence 8/8 in_raw… |
| CEHENNEM SÜRÜCÜLERİ | 1957-0024-1-0000-00-1 | yonetmen_dogru, yapim… | yuksek | ocr_raw_all satır 1439-1461: 'Directed / C.RAKER ENDFIELD' çifti 10 kez tekrar (satır 1440, 1442, 1445, 1447, 1449, 1451, 1455, 1458, 1461). ocr_ham satır 316-… |
| CİMRİ | 1980-0219-1-0000-00-1 | yonetmen | yuksek | kunye.txt satır 2: 'LOUIS DE FUNES' var (cast olarak); satır 4: 'ET JEAN GIRAULT' var (cast olarak); ocr_ham.txt satır 3: 'LOUIS DE FUNES' bitişik; satır 8: 'E… |
| DANTELCİ KIZ | 1995-0386-1-0000-00-1 | yonetmen | yuksek | ocr_raw_all.txt satır 72: 'claude goretta' (bağlam satır 71: 'adaptation et dialogues'); satır 77, 81, 85, 89, 93, 98, 103, 108 aynı bağlam. kunye.txt satır 4:… |
| DAĞDAKİ ŞEYTAN | 2006-9095-1-0000-40-1 | CAST_AZ | yuksek | kunye.txt satır 15-17: 'A FİLM BY / CRAİG WASSON / RAFFAELLO DEGRUTTOLA'. kunye.txt satır 40: 'CHASE JACKSON LANCE HENRİKSEN'. kunye.txt satır 41: 'ERİN PRİCE … |
| DAĞLAR FEDAİSİ | 1990-0498-1-0000-00-1 | cast | yuksek | kunye.txt satır 10-18: STACY HARRİS, YVES DRAINVILLE, WİLLİAM DEMAREST, HARRY TOWNES, BARBARA DARROW hepsi mevcut. ocr_raw_all.txt satır 154-316 aralığı: WILLI… |
| DERS | 2014-1008-1-0000-65-1 | yapimci | yuksek | ocr_ham.txt satır 63: 'PRODUCERS BULGARIA', satır 64: 'MAGDELENA ILIEVA' — bitişik. kunye.txt satır 1: 'MAGDELENA ILIEVA', satır 2: 'IVANKA BRATOEVA' (etiket y… |
| DOĞUM GÜNÜ 4 TEMMUZ | 1989-0514-1-0000-00-1 | yapimci, cast | yuksek | ocr_ham.txt:2 'AN A. KITMAN HO & IXTLAN PRODUCTION'; :3 'AN OLIVER STONE PICTURE'. kunye.txt:2 'AN A. KITMAN HO & IXTLAN PRODUCTION' (var). grep 'oliver|OLIVER… |
| DUMAS'IN MASKESİ | 1998-0436-1-0000-00-1 | yapimci, cast | yuksek | kunye.txt satır 1: 'WİLLİAM RİCHERT'; satır 33: 'PRODUCED, WRİTTEN AND DİRECTED BY' (aralarında 32 satır boşluk). ocr_ham.txt satır 5: 'William Richert', satır… |
| DÜŞMAN KAZANMAK | 1991-0500-1-0000-00-1 | yonetmen | yuksek | kunye.txt satır 53-54: 'PRODUCED & DİRECTED / GENE MCPHERSON' bitişik mevcut. ocr_raw_all.txt satır 435-437: 'produced & directed / by / Gene McPherson' bitişi… |
| EJDER KILICI | 2023-1146-1-0000-90-1 | yonetmen, cast | yuksek | ocr_ham.txt satır 29: 'A DANIEL LEE Film' (adjacent). kunye.txt satır 41: 'A DANIEL LEE FİLM' (adjacent). kunye_teslim.md Yapım Ekibi'nde Yönetmen alanı YOK. k… |
| ESKİ KOCAM(IZ) | 2017-1219-1-0000-50-1 | cast | yuksek | ocr_summary.json (ocr-ded9ffe5): frame_count=840, credit_frames=601, raw_line_count=9438, garble_frac=0.0 — ocr-bbdc8851 ile birebir aynı (her iki ocr_summary.… |
| GAGARİN | 2020-1090-1-0000-70-1 | yonetmen, yapimci | yuksek | kunye.txt satır 4: 'FANNY LIATARD ET JERÉMY TROUILH' (bitişik DOĞRULANDI); kunye.txt satır 63-66: 'MISE EN SCENE / MARINE BENOIT / FARES BEN NAOUYA / VALENTIN … |
| GEÇ GELEN BAHAR | 2024-1124-1-0000-75-0 | yonetmen, yapimci | yuksek | ocr_ham.txt satır 4: '(Directed by Yasujiro Ozu / Produced by Shochiku Co., Ltd. / 1949)' — ad+soyad bitişik grep doğrulandı; kunye.txt satır 4: '(DİRECTED BY … |
| GIGI | 1958-0021-1-0000-00-1 | yapimci | yuksek | ocr_ham.txt satır 17-19: 'PR ODUCTION / AN / ARTHUR FREED'. ocr_ham.txt satır 183: 'VINCENTE MINNEITI', satır 189: 'DIRECTED BY'. kunye.txt satır 2: 'ARTHUR FR… |
| GOBY (GABY: A TRUE STORY) | 1992-0464-1-0000-00-1 | yonetmen, yapimci, ca… | yuksek | ocr_ham.txt satır 12: 'PINCHAS PERRY-LUIS MANDOKI' — bitişik, rol etiketi yok. ocr_ham.txt satır 61: 'Ist Assistant Director ALFONSO CUARON' — DIRECTOR etiketi… |
| GÖRÜNMEZ HEDEF | 2007-9108-1-0000-90-1 | yonetmen | yuksek | kunye.txt satır 23: 'A BENNY CHAN FİL M'. ocr_raw_all.txt satır 81-91: 'A Benny Chan Fil m' / 'A Benny Chan Film' tekrarlı — hem ham hem filtreli OCR'da var. f… |
| GÜNEY BATI GEÇİDİ | 1954-0054-1-0000-90-1 | yapimci | yuksek | ocr_ham.txt satır 10: 'EDWARD SMALL', satır 11: 'Presents'. ocr_ham.txt satır 54: 'Directed by', satır 55: 'RAY NAZARRO'. kunye.txt satır 2: 'EDWARD SMALL' (ba… |
| GİZEMLİ GÜÇ | 1973-0220-1-0000-00-1 | YAPIMCI | yuksek | kunye.txt satır 298: 'PETER PAU' (bitişik, doğrulanmış). ocr_raw_all.txt satır 8027+: 'Peter Pau' — bitişik eşleşme onaylandı. kunye.txt'de 'COSTİNG DİRECTOR' … |
| HAYATTA KAYBETMEK DE VAR | 1993-0478-1-0000-00-1 | cast | yuksek | Kunye.txt line 16-22: PAULA HUTTEROVÁ, SEPP PAUR, STEPÁNKA SRÁMKOVÁ, KUSENA MACHALOVÁ, MIROSL AV SEDI AR, ALOIS PAUR, VLADIMIR KUNDRÁT — hepsi mevcut. Final oy… |
| JAMES DEAN'İN HİKAYESİ | 1957-0047-1-0000-00-1 | yonetmen, yapimci, ca… | yuksek | kunye.txt sat.9: 'GORGE W.GENGE UND ROBERT ALTMON PRESENT'; sat.10: 'V. GEORGE AND ROBERT ALTMAN PRESENT'; sat.104: 'MARTİN GABEL' (naratör); final yönetmen='—… |
| KAPI ÇALINCA | 1979-0237-1-0000-00-1 | yonetmen, yapimci | yuksek | kunye.txt satır 22: 'FRANKD GILROY' var; kunye.txt satır 3: 'EMMET G. LAVERY, JR.' var; ocr_ham.txt satır 39: 'FRANKD GILROY' bitişik; ocr_ham.txt satır 27+169… |
| KAPTAN BENİM | 2023-1128-1-0000-70-1 | yonetmen, cast | yuksek | ocr_ham.txt satır 29-31: 'KAPTAN BENİM / MATTEG GARRONE / un film di' — bitişik satırlar, yönetmen kartı. kunye.txt satır 22-25: 'KAPTAN BENİM / UN CİLN Dİ / M… |
| KAĞITTAN UÇAKLAR | 2014-1120-1-0000-90-1 | yonetmen, cast | yuksek | grep -niE 'robert +connolly' ocr_ham.txt → satır 51: 'ROBERT CONNOLLY' (THE END / satır 50'nin hemen sonrası), satır 55: 'ROBERT CONNOLLY' (produced by bloğu).… |
| KELEBEĞİN RÜYASI | 2013-9098-1-0000-90-1 | yonetmen, yapimci, ca… | yuksek | grep -niE 'YILMAZ.*ERDO|ERDO.*YILMAZ' kunye.txt + ocr_raw_all.txt + ocr_ham.txt → sıfır eşleşme (yalnızca grip operatörü 'Erdoğan Gündoğdu' çıktı, farklı kişi)… |
| KLONDİKE | 2023-1161-1-0000-90-1 | yonetmen, yapimci, ca… | yuksek | ocr_raw_all.txt: 'МАРИНА ЕР ГОРБАЧ' 13 eşleşme (PowerShell doğrulandı — satır 960: 'Візуальна концепція / МАРИНА ЕР ГОРБАЧ' ardışık). kunye.txt satır 85: 'ВІЗУ… |
| KOVAN | 2018-0059-1-0000-85-1 | yonetmen, yapimci_can… | yuksek | kunye.txt satır 10: 'EYLEM KAFTAN' — bitişik grep 'eylem +kaftan' eşleşti (hem ocr_ham hem kunye.txt). Final kunye_teslim.md: Yönetmen alanı boş, Yapımcı=MUSTA… |
| KÜÇÜK GAZETECİLER | 1996-0230-1-0000-00-1 | yonetmen, yapimci | yuksek | Grep 'BLAIR.*TREU|BLAIR TREU' → sıfır eşleşme (in_raw=false doğrulandı). Grep 'STEVE OLPIN' → ocr_raw_all.txt satır 1426: 'ADDITIONAL ELECTRICIAN STEVE OLPIN';… |
| LESS VE BESS SİZLERLE | 1991-0359-1-0000-00-1 | cast | yuksek | kunye.txt satır 11-18: CLORİS LEACHMAN, DİCK VAN DYKE, MARK HUMPHREY, WENDEL MELDRUM, SHAUN CASSİDY, KEN JAMES, TOM HARVEY, BİLL KEMP — hepsi mevcut. Final cas… |
| LOUIS WAIN'IN RENKLİ DÜNYASI | 2021-1090-1-0000-50-1 | yonetmen, yapimci, ca… | yuksek | ocr_raw_all.txt 11.591 satırda 'SHARP' ve 'DIRECTED BY' sıfır hit (PowerShell Select-String doğrulandı). kunye.txt satır 185: 'DİRECTOR'S ASSİSTANT', satır 186… |
| LİSEDE PANİK | 1991-0393-1-0000-00-1 | yonetmen | yuksek | kunye.txt satır 1: 'DANIEL PETRIE, JR.' — satır 7: 'DİRECTED BY' (aralarında 5 başka satır var). Final cast satır 12: 'DANIEL PETRIE, JR.' (oyuncu olarak atanm… |
| MADALYON | 2003-9135-1-0000-00-1 | yonetmen, yapimci | yuksek | Grep 'GORDON CHAN' ocr_raw_all.txt → satır 1412 (kamera bloğu içinde), satır 3009 (production coordinator satırları içinde). kunye.txt satır 7: 'GORDON CHAN', … |
| MATADOR VE HANIMEFENDİ | 1951-0039-1-0000-00-1 | yapimci | yuksek | ocr_ham.txt satır 137: 'BUDD BOETTICHER' — bitişik, tek satır. kunye.txt satır 3: 'BUDD BOETTİCHER'. ocr_ham.txt satır 50: 'HERBERTVA YATES', satır 51: 'Presen… |
| MATHIAS KNEISSEL | 1974-0215-1-0000-00-1 | yapimci | yuksek | kunye.txt satır 78: 'PHİLİPPE PİLLİOD' var; ocr_ham.txt satır 112-113: 'Produzent : / Philippe Pilliod' var; final kunye_teslim.md 'Yapımcı:' alanı boş (sadece… |
| MENEKŞE GÖZLER | 2010-9266-1-0000-88-1 | yonetmen | yuksek | ocr_ham.txt satır 138: 'rejisor' + satır 139: 'ATIF YILMAZ' — yönetmen etiketi + bitişik ad doğrulandı. kunye.txt satır 62: 'ATIF YILMAZ' mevcut. kunye.txt sat… |
| MIAMI MACERASI | 1959-0020-1-0000-00-1 | yapimci | yuksek | ocr_ham.txt:169 'Producedd and Otrected'; :171 'FRANK CAPRAL'; :172 'ANK CAFRA'. kunye.txt:111-113 aynı üç satır. kunye.txt'de 'FRANK CAPRA' (temiz, L-siz) SIF… |
| MOOCHİE BÜYÜK OYUNCU | 1959-0041-1-0000-00-1 | cast_tam, yapimci_dog… | yuksek | kunye.txt sat.5: 'EOUES IDEBNEY'; sat.7: 'LOUİS DEBNEY' (Production Coordinator, not cast); sat.12: 'STUART ERWİN'; sat.13: 'JİM L. BROWN'; sat.14: 'DOROTHY GR… |
| MORRİE İLE HER SALI | 1999-1127-1-0000-50-1 | cast, yonetmen | yuksek | ocr_ham.txt satır 43: 'caroline aaron' (bitişik); satır 44: 'bonnie bartlett' (bitişik); satır 48: 'john carroll lynch' (bitişik). kunye.txt satır 28: 'CAROLİN… |
| MOZART'IN KIZ KARDEŞİ | 2010-2184-1-0000-70-0 | yapimci, yonetmen_tem… | yuksek | kunye.txt satır 22='RENE FEREL', satır 23='IVANNERİ MOZART', satır 24='LE DAUPHİN' — final yönetmen='RENE FEREL, IVANNERİ MOZART, LE DAUPHİN, RENE FERET' bire … |
| MOĞOL CENGİZ HAN'IN YÜKSELİŞİ | 2007-9089-1-0000-00-1 | cast | yuksek | ocr_raw_all.txt satır 56: 'DIRECTED BY', satır 57: 'SERGEI BODROV' (6 tekrar). kunye.txt Select-String 'DIRECTED BY' → 0 eşleşme. kunye.txt satır 30: 'TRMUBGIN… |
| MÜFETTİŞ REVİZÖR | 2002-9206-1-0000-00-1 | yonetmen, yapimci, ca… | yuksek | ocr_ham.txt satır 65: 'Режиссер-постановщик', satır 66: 'ЛЕОНИД ГАЙДАЙ'. kunye.txt satır 28: 'В.БАХНОВ, Л.ГАЙДАЙ' (senaryo), satır 29: 'ЛЕОНИД ГАЙДАЙ' (ROL ETİ… |
| OZZIE SEVİMLİ KOALA | 2005-9062-1-0000-00-1 | CAST_AZ | yuksek | kunye.txt satır 27: 'A BILL TANNEN FILM'; satır 118: 'BILL TANNEN' (EXECUTIVE PRODUCER bloğu altında); satır 379: 'ANTMATED SEQUENCES PROOUCED BY / HAHN FILM A… |
| PAN'IN LABİRENTİ | 2006-1058-1-0000-73-0 | yonetmen_dogru_rol, c… | yuksek | ocr_ham.txt satır 48: 'GUILLERMO DEL TORO' (bitişik, cast bloğu içinde, ANCIANO karakteriyle). kunye.txt satır 42: 'GUİLLERMO DEL TORO' (bitişik, cast bloğu sa… |
| ROB ROY | 1953-0049-1-0000-00-1 | yapimci | yuksek | Bitişik grep 'HAROLD FRENCH' kunye.txt satır 47: eşleşti. 'PERCE PEARCE' satır 46: eşleşti. in_raw=true teyitli. Final yönetmen: 'ALEX BRYCE, MADE AT, SOUND RC… |
| SEVDAM GÖZLERİNDE KALDI | 2014-0091-1-0000-85-1 | yapimci | yuksek | mustafa +y[iı]lmaz grep: ocr_ham.txt satır 16 'MUSTAFA YILMAZ' bitişik eşleşti; kunye.txt satır 10 'MUSTAFA YILMAZ' eşleşti. ahmet +yenilmez bitişik grep: tüm … |
| SEVGİLİ ANGELO | 1983-0258-1-0000-00-1 | yapimci | yuksek | ocr_ham.txt:2 'presents'; :3 'Robert Duvall presents'. kunye.txt'de 'presents|PRESENTS' grep → SIFIR eşleşme. kunye.txt:3 yalnızca 'ROBERT DUVALL' (etiket yok)… |
| SIRLAR OTELİ | 2000-0521-1-0000-00-1 | yapimci, yonetmen | yuksek | grep -i 'WENDERS' kunye.txt → satır 195 'ASSİSTANT TO WİM WENDERS', satır 201 'INTERN TO WİM WENDERS', satır 310 'DONATA WENDERS' — 'DIRECTED BY' + 'WIM WENDER… |
| SÖZ | 2018-1030-1-0000-90-1 | yonetmen, cast | yuksek | ocr_ham.txt satır 86: '감독 박홍수' (감독=yönetmen Korece, 박홍수=Park Hong-su — bitişik, tek satır); satır 87: '최승현 (TOP)', satır 88: '한예리', satır 90: '윤제문', satır 91: … |
| TERESA VENERDİ | 1941-0036-1-0000-00-1 | yapimci | yuksek | Bitişik grep 'VITTORIO DE SICA' kunye.txt satır 4/14/65: eşleşti. 'ADRIANA BENETTI' satır 35: eşleşti. 'ANNA MAGNANI' satır 41,44: eşleşti. in_raw=true, in_kun… |
| TOPLU GÖSTERİLER | 1935-0011-1-0000-00-1 | yonetmen, yapimci, ca… | yuksek | ocr_ham satır 3-4: 'EN FILMBERATTLLSE AV / GUSTAF FDGREN'; satır 25-28: 'GUSTAF EDCR / CUSTAF EDGR / REGI / RECI:'. ocr_raw_all grep 'GUSTAF EDGREN' -> 17 eşle… |
| UZAYLI | 1984-0213-1-0000-00-1 | yonetmen | yuksek | ocr_ham satır 24: 'DIRECTED BY', satır 25: 'JOHN CARPENTER' (bitişik). kunye.txt satır 26: 'DIRECTED BY', satır 27: 'JOHN CARPENTER' (filtreden geçti). kunye_t… |
| UZAYLI DEDEKTİF (ALIEN PRIVATE EYE) | 1993-0235-1-0000-40-1 | yapimci | yuksek | kunye.txt satır 7-9: 'PRODUCED, WRİTTEN & / DİRECTED BY / NIKKI FASTINETTI' — isim bitişik mevcut. Final yönetmen: 'NIKKI FASTINETTI, CLIFF ADUDDELL, LIDITH BU… |
| VADİLER HAYDUDU | 1961-0041-1-0000-00-1 | yapimci | yuksek | ocr_ham.txt sat.134: 'Produced and Directed Iby'; sat.135: 'ROY BAKER'; kunye.txt sat.1: 'ROY BAKER'; sat.5: 'PRODACEDCİAND DİREOTED BY'; sat.87: 'PRODUEND AND… |
| YALNIZ ADAM | 2023-1018-1-0000-90-1 | yapimci, yonetmen | yuksek | ocr_ham.txt satır 1-9: 'A/REPUBLIC/PRODUCTION/HERBERT YAL/PRESENTS/HERBERTIJ.LYATES/RABEMILLAND/IN/RAY MILLAND' — 'HERBERTIJ.LYATES' producerın garble hali, ad… |
| YANKESİCİLERİN MOZART'I | 2006-2153-1-0000-70-1 | yonetmen | yuksek | kunye.txt satır 2: 'PHİLİPPE POLLET-VİLLARD' (bitişik, mevcut). kunye.txt satır 91: 'UN FİLM DE' — satır 92 boş (isim yok). ocr_ham.txt satır 128: 'un film de'… |
| YAŞAMA GÜCÜ | 1994-0312-1-0000-00-1 | yapimci | yuksek | ocr_ham.txt satır 50-53: 'Produced by / PIERRE DAVID / Directed by / MARK ROSMAN' — her biri ayrı satırda, bitişik çift tespit için 'pierre.*david' grep eşleşi… |
| YEDİ KADIN YEDİ ZAMAN | 1967-0061-1-0000-00-1 | YAPIMCI | yuksek | kunye.txt satır 2: 'JOSEPH E. LEVİNE'; satır 9: 'ARTHUR COHN' — her ikisi de final cast dizisinde görünüyor (cast[1]='JOSEPH E. LEVİNE'). ocr_ham.txt satır 1: … |
| YENİ HAYAT | 2015-9072-1-0000-90-1 | yonetmen | yuksek | ocr_ham satır 50: 'YÖNETMEN', satır 51: 'F. SERKAN ACAR' — bitişik, aynı bağlam. kunye.txt grep 'YÖNETMEN': yalnızca satır 24 'GÖRÜNTÜ YÖNETMENİ' eşleşiyor, 'Y… |
| YOLCULUK | 1986-0197-1-0000-00-1 | cast | yuksek | grep -niE 'ein film von' ocr_raw_all.txt → satır 135: 'ein Film von', satır 136: 'MARKUS IMHOOF' (bitişik çift). grep 'corinna' ocr_ham.txt → satır 22: 'CORINN… |
| ZAMAN MAKİNASI | 1985-0235-1-0000-00-1 | yonetmen | yuksek | grep -niE 'mark.*rosman|rosman.*mark' ocr_ham.txt → satır 12: 'A MARK ROSMAN FILM' (bitişik). grep 'mark.*rosman' ocr_raw_all.txt → satır 81-90: 10× 'A MARK RO… |
| ZORAKİ KRAL | 2010-1023-1-0000-50-0 | yonetmen, cast | yuksek | ocr_raw_all.txt satır 250: 'Director's Assistant', satır 251: 'STEFANO MARGARITELLI' — direktörün asistanı, yönetmen değil. kunye.txt satır 34: 'STEFANO MARGAR… |
| ÇILDIRIŞ | 2025-1142-1-0000-50-1 | yapimci, cast | yuksek | ocr_ham satır 198-199 (okundu): 'Cast Assistant Director Trainee Luciana Burcheri / Nicolas Marion'. kunye.txt satır 154-155: 'CAST ASSİSTANT DİRECTOR TRAİNEE … |
| ÇILGIN YAŞAMIM | 1993-0441-1-0000-00-1 | cast | yuksek | kunye.txt satır 25: 'ANGEL AVİLES', satır 33: 'SALMA HAYEK', satır 38: 'JESSE BORREGO' — grep -niE 'ANGEL +AV|SALMA +HAYEK|JESSE +BORREGO' → 3 bitişik eşleşme.… |
| ÇİFTE SADAKATSİZLİK | 1983-0219-1-0000-00-1 | cast | yuksek | ocr_raw_all.txt satır 177:'Robin Askwith', 193:'Leonie Mellinger', 260:'Christopher Biggins' bitişik. kunye.txt satır 8:'ROBİN ASKWİTH', satır 10:'LEONİE MELLİ… |
| ÖLDÜREN SIR | 1997-0270-1-0000-00-1 | cast, yapimci | yuksek | ocr_ham.txt satır 3: 'Ari Meyers' (bitişik); satır 36: 'Noel Nosseck' (bitişik, 'Directed by' sonrası). kunye.txt satır 5: 'ARİ MEYERS' — başrol kitlesi başlık… |
| İHANET BURNU | 1995-0354-1-0000-40-1 | yapimci | yuksek | ocr_ham.txt satır 2: 'JONATHAN D. KRANE'; kunye.txt satır 5: 'JONATHAN D. KRANE' — bitişik rol etiketi yok. kunye.txt satır 103: 'JACK MCCLELLAN' — cast sırası… |
| İŞARETLER VE MUCİZELER | 2000-0370-1-0000-00-1 | yonetmen, yapimci | yuksek | ocr_raw_all.txt satır 60: 'In a film directed by' / satır 61: 'JONATHAN NOSSITER' (14 eşleşme, satır 61,63,65,67,69,71,75,80,...). Satır 112: 'Produced by' / s… |
| İŞTE BURDAYIZ | 2023-1120-1-0000-59-0 | cast | yuksek | kunye.txt satır 35: 'NOAM IMBER' (adjacent — bitişik isim, satırın tamamı). kunye.txt satır 63: 'GUY SHOVAL', satır 65: 'RONI LEVY' (adjacent). kunye.txt satır… |
| ŞİRİN | 2008-1143-1-0000-56-0 | cast, yonetmen_yanlis | yuksek | kunye.txt satır 174-175: 'OPENİNG CREDİTS / BAHMAN KİAROSTAMİ' → pipeline bunu yönetmen sandı. kunye.txt satır 196: 'DİRECTED AND PRODUCED BY' etiketi mevcut (… |

### S1_FRAME_KAPSAM — düşük-kontrast/diegetik jenerik kareden alınamadı  (52 film)

| Başlık | TRT | Eksik | Güven | Kanıt (özet) |
|---|---|---|---|---|
| AFRİKALI | 1983-0290-1-0000-00-1 | yapimci | yuksek | grep 'MNOUCHKINE|ALEXANDRE|produit|produced|producteur' ocr_raw_all.txt = No matches. ocr_raw_all.txt satir 1-14 = 'RENN PRODUCTIONS / prEsente' tekrarlari (si… |
| ARAMIZDAKİ SÖZLER | 2022-1137-1-0000-90-1 | yonetmen | yuksek | grep 'hany' ocr_ham.txt=0; grep 'hany' ocr_raw_all.txt=0; grep 'abu.{0,5}ass' ocr_raw_all.txt — yalnız 'ASSISTANTS TO MR. ABU-ASSAD' (satır 4930, 4957, 4984...… |
| ATEŞ ARABALARI | 1981-0252-1-0000-00-1 | yonetmen | yuksek | ocr_ham.txt grep 'hugh hudson|ben cross|ian charleson': eşleşme yok. satır 6: 'CHARIOTS OF FIRE', satır 8: 'ROGER HALL', satır 72: 'BY VANGELIS PAPATHANASSIOU'… |
| AŞK ZENGİNİ (RICH IN LOVE) | 1992-0475-1-0000-00-1 | yonetmen, yapimci | yuksek | ocr_ham.txt 'bruce beresford' bitişik grep: sıfır eşleşme. ocr_ham.txt 'beresford' grep: yalnız satır 117 'Praductinn Aseislant CORDELIA BERESFORD'. ocr_ham.tx… |
| AŞK ŞİMDİ | 2013-1174-1-0000-50-1 | yonetmen | yuksek | ocr_raw_all.txt grep 'directed by': eşleşme yok. grep 'ol parker': yalnızca 'Astistank/Ashstare/Assistare to Ol Parker' satırları (satır 1528, 1569, 1608, 1650… |
| BAKIŞ AÇISI | 2008-1004-1-0000-50-1 | yonetmen | yuksek | grep -i 'pete' ocr_ham.txt → yalnız 'PETER CAVACIUTI', 'PETER BURGIS' vb. — farklı kişiler. grep -i 'travis' ocr_raw_all.txt → 'ASSISTANT TO MR. TRAVIS BARBARA… |
| BAŞKA BİR DÜNYA | 2023-1054-1-0000-70-0 | yonetmen | yuksek | frames/giris/ = 360 dosya, frames/cikis/ = 480 dosya. ocr_summary.json: credit_frames=496, diegetik_frac=0.19. ocr_ham.txt satır 1: 'Produit par NORD-OUEST FIL… |
| BETHANY'DEKİ SESSİZLİK | 1988-0399-1-0000-00-1 | yonetmen | yuksek | dir_presence: Joel Oliansky in_raw=false, in_kunye=false; ocr_ham.txt'de 'oliansky' için bitişik grep: 0 sonuç. kunye.txt'de 'LINDSAY LAW' (satır 126) var, 'JO… |
| BOWERY'DEN BROADWAY'E (From Broadway to… | 1944-0022-1-0000-00-1 | yonetmen, yapimci, ge… | yuksek | ocr_ham.txt grep 'charles lamont|lamont charles|maria montez|montez maria|jack oakie|oakie jack' → No matches; kunye.txt: 46 satırın tamamı tiyatro panosu/gaze… |
| BİR KASABANIN HİKAYESİ | 1989-0348-1-0000-00-1 | yonetmen | yuksek | grep 'tewkesbury|TEWKESBURY|joan|JOAN|directed|DIRECTED' ocr_ham.txt → yalnızca 'JOANNE TORNGREN' (satır 79) ve 'JOANI YARBROUGH' (satır 113) — farklı kişiler,… |
| BİR SOKAK ÇOCUĞUNUN PORTRESİ | 1977-0200-1-0000-00-1 | yonetmen | yuksek | ocr_ham.txt grep 'steve gethers|levar burton|ossie davis': eşleşme yok. satır 55: '2nd Asst Direstor WILLIAM MORRISCK', satır 72-77: 'COPYRIGHT MCMLKVI BY MARK… |
| BİR YABANCIYLA DOSTLUK | 1990-0445-1-0000-00-1 | yonetmen | yuksek | dir_presence: Cynthia Scott in_raw=false, in_kunye=false; ocr_ham.txt'de 'cynthia'/'scott' bitişik grep: 0 sonuç. cast_presence 8/8 in_raw=true. ocr_ham.txt sa… |
| CHARLİE'NİN ÇİKOLATA FABRİKASI | 2005-9118-1-0000-00-1 | YAPIMCI_BOS | yuksek | ocr_raw_all.txt: 'PRODUCED BY' → yalnız 'MUSIC PRODUCED BY DANNY ELFMAN' (15 kez). 'ZANUCK' → 'ASSISTANT TO MR. ZANUCK BRENDA BERRISFORD' (satır 848+). 'BRAD G… |
| DAVA | 1996-0252-1-0000-00-1 | yapimci | yuksek | grep 'JAMES +FOLEY' ocr_raw_all.txt → 0 eşleşme (3596-3987 arasında yalnızca 'Mr. Foley' dolaylı). grep 'BRIAN +GRAZER|JOHN +DAVIS|PRODUCED BY' ocr_raw_all.txt… |
| FİLİ ÇALAN ÇOCUK | 1970-0067-1-0000-00-1 | yonetmen, yapimci, ca… | yuksek | frames/giris/ = 360 PNG, frames/cikis/ = 480 PNG (PowerShell Measure-Object ile sayıldı). ocr_raw_all.txt 8 satır: satır 1-8 = 'GEORGE TOWN 29M/29ML' ve 'HANCO… |
| GENÇLİK | 1962-0023-1-0000-00-1 | yonetmen, yapimci | yuksek | ocr_ham.txt + ocr_raw_all.txt grep 'directed|richard|brooks' -> sıfır sonuç. ocr_ham.txt satır 1-30: MGM logosu + 'Sweet Bird of Youth' başlık kartları ve oyun… |
| GÖLGE YÜREK | 2009-9145-1-0000-00-1 | yonetmen | yuksek | ocr_raw_all.txt 9484 satır: 'DIRECTED BY' → 0, 'WRITTEN AND DIRECTED' → 0, 'A DEAN ALIOTO FILM' → 0. 'DEAN ALIOTO' bitişik: satır 162 bağlamı 'Charlie [karakte… |
| HANNAH'NIN KANUNU | 2017-1052-1-0000-90-1 | yonetmen | yuksek | ocr_raw_all.txt (414 satır) grep -niE 'directed by|rachel talalay|a film by|produced by' → sadece 'First/Second Assistant Director' eşleşmesi, Rachel Talalay s… |
| HAPİSHANE MÜDÜRÜ | 2003-9067-1-0000-00-1 | yonetmen | yuksek | Select-String ocr_raw_all.txt 'GYLLENHAAL' → 0 eşleşme. 'STEPHEN' → 0 eşleşme. 'DIRECTED' → 0 eşleşme. (Get-Content ocr_raw_all.txt).Count = 3247. kunye.txt sa… |
| HESAPLAŞMA | 1986-0245-1-0000-00-1 | yonetmen, yapimci | yuksek | grep -niE 'directed by|fred olen ray.*directed' ocr_raw_all.txt → 0 eşleşme. grep -niE 'fred.*olen.*ray' ocr_ham.txt → satır 31: '2nd Soldier FRED OLEN RAY' (o… |
| I ROBOT | 2004-9161-1-0000-90-1 | yonetmen, yapimci, ca… | yuksek | grep 'alex proyas|proyas|directed by' ocr_raw_all → eşleşme YOK. grep 'will smith' → satır 18164 (ve 16 tekrar) yalnızca 'SELECTED WARDROBE FOR WILL SMITH PROV… |
| KANLI TEPELER | 2009-9136-1-0000-00-1 | yonetmen, yapimci, ca… | yuksek | ocr_ham.txt 3 satır: 'THE END / Released thru United Artists' (sadece). ocr_raw_all.txt 29 satır: aynı 2 satır 14 kez tekrar. kunye.txt: 'THE END' (1 satır, 7 … |
| KARAYİP KORSANLARI-2-ÖLÜ ADAMIN SANDIĞI | 2015-1088-1-0000-90-1 | yonetmen, yapimci, ca… | yuksek | grep -niE 'gore +verbinski|verbinski +gore' ocr_ham.txt → eşleşme yok. grep 'jerry +bruckheimer' ocr_ham.txt → yalnızca satır 545 (trademark). ocr_ham.txt satı… |
| KARDEŞLİK | 1968-0019-1-0000-00-1 | yonetmen, yapimci | yuksek | kunye.txt: yalnızca 12 satır, THE END + Cast of Characters + oyuncu isimleri. ocr_ham.txt grep 'directed|produced|martin|ritt|bryna' -> sıfır eşleşme. ocr_raw_… |
| KEHANET | 2009-9156-1-0000-90-1 | yapimci, cast | yuksek | Grep 'ALEX.{0,5}PROYAS' → satır 124-131 (7 hit). Grep 'NICOLAS.{0,5}CAGE' → satır 137-151 (8 hit). Grep 'ROSE.{0,5}BYRNE|CHANDLER|MENDELSOHN|LARA.{0,5}ROBINSON… |
| KOCA SEVİMLİ DEV (The BFG, 2016, Steven… | 2024-1219-1-0000-50-1 | yonetmen, gercek_cast | yuksek | ocr_raw_all.txt grep 'steven +spielberg|spielberg +steven' → eşleşme yok; grep 'spielberg' → yalnızca 'DRIVER FOR MR. SPIELBERG' (satır 2978–3763) ve 'ASSISTAN… |
| KURŞUNU ISIR | 1975-0215-1-0000-90-1 | yonetmen, yapimci | yuksek | ocr_raw_all.txt'de 'RICHARD BROOKS', 'GENE HACKMAN', 'CANDICE BERGEN' için bitişik grep: sıfır eşleşme. ocr_ham.txt satır 1-31 doğrudan James Coburn ile başlıy… |
| KUSURSUZ DÜNYA | 1993-0519-1-0000-00-1 | yonetmen | yuksek | Ham OCR grep 'directed by' → 0 eşleşme. Ham OCR grep 'a film by' → 0 eşleşme. Grep 'clint eastwood' → line 113: 'Red Garnett CLINT EASTWOOD', line 225: 'Compus… |
| KUZEYDEKİ GÖLGE | 2006-9062-1-0000-00-1 | YONETMEN_BOS | yuksek | ocr_raw_all.txt 'JOHN ALEXANDER' grep: eşleşme yok. ocr_raw_all.txt 'DIRECTED BY' grep: eşleşme yok. kunye.txt satır 117: 'DIRECTOR OF PHOTOGRAPHY ADAM SUSCHIT… |
| KÜHEYLAN | 1976-1018-1-0000-22-1 | yonetmen | yuksek | ocr_raw_all.txt satır 960-982: 'TUGULDUR MUNKH-OCHIR / PRODUCTION TEAM: / 1ST ASSISANT DIRECTOR KHUUBAATAR.U / ASSISTANT DIRECTORS ENKHSAIKHAN.U / EXECUTIVE PR… |
| MADAME X | 1981-0310-1-0000-00-1 | yonetmen | yuksek | ocr_raw_all.txt grep 'robert ellis miller|robert.ellis|ellis miller|directed|tuesday weld|weld' → 0 eşleşme (yalnızca 'Pola Miller' satır 172-236 ve 'Burton Mi… |
| MENEKŞELER VE AŞK | 1987-0252-1-0000-00-1 | yonetmen, yapimci | yuksek | ocr_ham.txt: 'DIRECTED' grep → sıfır sonuç; 'KATSELAS' grep → sıfır sonuç; 'MILTON' grep → sıfır sonuç. Satır 41: 'I'nit Production Manager uike Frankovictso' … |
| MEZUNİYET PROJESİ | 1985-0208-1-0000-00-1 | yonetmen, yapimci | yuksek | grep -niE 'jonathan.*betuel|betuel.*jonathan' ocr_raw_all.txt → 0 eşleşme. grep 'taplin' ocr_raw_all.txt → 0 eşleşme. ocr_raw_all.txt satır 786: 'ASSISTANT TO … |
| NARNİA GÜNLÜKLERİ ŞAFAK YILDIZI'NIN YOL… | 2010-9158-1-0000-90-1 | yonetmen, yapimci | yuksek | ocr_ham.txt grep 'michael apted|georgie henley|skandar keynes|ben barnes': eşleşme yok. satır 559: 'PETER APTED 1943-2010' (memorial plak, yönetmen değil). sat… |
| ROBIN HOOD | 1973-0219-1-0000-00-1 | YONETMEN, YAPIMCI, CA… | yuksek | ocr_raw_all.txt grep 'reitherman|directed by|wolfgang' → 0 eşleşme. ocr_summary.json: frame_count=840, credit_frames=342. ocr_raw_all.txt satır 1-380: Disney l… |
| SESSİZ KIZ | 2022-1058-1-0000-80-0 | yonetmen | yuksek | grep 'colm.*bair|bair.*colm' ocr_raw_all.txt=0 eşleşme; grep 'colm' ocr_ham.txt=0 eşleşme; 'Colm' yalnız 'Colm O hAodha' (Prod.Asst.) satırlarında; 'Bairéad' y… |
| SHERLOCK HOLMES | 2009-9165-1-0000-90-1 | yonetmen | yuksek | ocr_ham.txt grep 'guy ritchie|robert downey|jude law|mark strong': eşleşme yok. grep 'directed by|ritchie|mr.*downey': eşleşme yok. kunye.txt satır 338: 'C 200… |
| SONA DOĞRU | 2013-1165-1-0000-50-1 | yonetmen, cast | yuksek | ocr_raw_all.txt grep 'chandor': yalnız Frances/Jeff/Mary/Miles/Heather Chandor (Special Thanks, satır 10008+). 'written and directed' grep: eşleşme yok. 'Rober… |
| SİRK | 2005-9061-1-0000-00-1 | YONETMEN | yuksek | Select-String 'DIRECTED BY' → 0 eşleşme (6942 satır). 'ROB WALKER' bitişik: satır 887 'Rob Walker / Old Tramp' (oyuncu bağlamı), satır 960 'Rob Walker' aynı ca… |
| TİTANLARIN SAVAŞI | 2010-9173-1-0000-90-1 | yonetmen, yapimci, ca… | yuksek | Grep 'LOUIS.{0,5}LETERRIER|SAM.{0,5}WORTHINGTON|LIAM.{0,5}NEESON|RALPH.{0,5}FIENNES|GEMMA.{0,5}ARTERTON|MADS.{0,5}MIKKELSEN|BASIL.{0,5}IWANYK' → sıfır eşleşme.… |
| U-571 | 2000-0373-1-0000-00-1 | yonetmen, yapimci, ca… | yuksek | ocr_ham.txt 14 satır: satır 1='U-57', satır 2='U-671', satır 3-11 TR diyalog, satır 12-13 sayı/koordinat. ocr_raw_all.txt 115 satır: satır 1-16 'U-571' tekrarl… |
| UNUTMA BENİ | 2014-1009-1-0000-50-1 | yonetmen, cast | yuksek | ocr_raw_all.txt grep 'glatzer|westmoreland': yalnız 'Assistant to Mr. Glatzer and Mr. Westmoreland' (satır 5993+). 'directed by' grep: eşleşme yok. kunye.txt s… |
| UZAY YOLU | 1984-0260-1-0000-00-1 | yonetmen, yapimci, yo… | yuksek | ocr_raw_all.txt grep 'directed|produced by' → 0 eşleşme. satır 3563:'LEONARD NIMOY / Spock' (cast). satır 5063:'HARVE BENNETT / Flight Recorder' (cast voice). … |
| YARGISIZ İNFAZ | 2007-9097-1-0000-00-1 | yonetmen | yuksek | grep 'gavin|hood|directed' ocr_ham.txt → 0 eşleşme. grep 'gavin|hood|directed' ocr_raw_all.txt → 0 eşleşme. ocr_raw_all.txt başlangıcı: LEVEL1 ENTERTAINMENT / … |
| YAŞAMAK İSTİYORUM | 1983-0276-1-0000-00-1 | yonetmen, yapimci | yuksek | ocr_raw_all.txt grep 'david lowell rich|directed|lindsay|wagner|paul pump' → 0 eşleşme. ocr_raw_all.txt satır 1194-1233: 'The Producer Wishes to Thank / Warden… |
| ZOR ÖLÜM 2 | 1990-0470-1-0000-90-1 | yonetmen, yapimci | yuksek | ocr_raw_all.txt grep 'directed by' → sıfır; grep 'produced by' → sıfır. grep 'renny harlin' → satırlar 3291/3324/3354/… 'Assistants to Renny Harlin' (asistan k… |
| ÇAYLAK | 2003-9119-1-0000-00-1 | yonetmen, yapimci | yuksek | Select-String ocr_raw_all.txt 'HANCOCK' → 0. 'JOHN LEE' → 0. 'DIRECTED BY' → 0. 'GORDON GRAY' → 0. 'PRODUCED BY' → 0. 'MARK CIARDI' → satır 711: 'MARK CIARDI' … |
| ÇILGIN BILL | 1995-0375-1-0000-90-1 | yapimci, yonetmen, ca… | yuksek | ocr_ham tüm arama: 'DIRECTED BY WALTER HILL' yok; 'ASSISTANTS TO WALTER HILL' satır 150+ arası tekrarlı. ocr_ham satır 221: 'DIRECTED BY DJOKO WALUJO' (gamelan… |
| ÇİT | 2023-1000-1-0000-80-1 | yonetmen | yuksek | ocr_raw_all.txt satır 3320: 'Assistant to Phillip Noyce' (bitişik VAR ama yanlış bağlam — asistan atfı); satır 3382: 'Attachments to Phillip Noyce'; grep 'dire… |
| ÖLDÜREN ALTINLAR | 1969-0031-1-0000-00-1 | yonetmen, yapimci, ca… | yuksek | ocr_ham.txt 10 satır toplam (wc -l=10, wc -c=79). ocr_raw_all.txt 52 satır: 'GEORGE NADER as JERRY COTTON in' x9 + 'THE END' x11 + 'IADER/OTTON' garble. ocr_su… |
| İSTENMEYENLER | 1977-0203-1-0000-00-1 | yonetmen | yuksek | grep 'LOSEY|directed|JOSEPH' ocr_ham.txt = No matches; grep 'LOSEY|directed|JOSEPH' ocr_raw_all.txt = No matches. raw_all satir 1-50 = COLUMBIA PICTURES/A HAMM… |
| ŞİRKET | 1993-0384-1-0000-90-1 | yapimci | yuksek | Ham OCR grep 'scott rudin' → 0 eşleşme. Grep 'produced by' → 0 eşleşme. Grep 'rudin' → tek sonuç line 271: 'Assistant to Mr. Rudin' (birinci ad yok). Kunye.txt… |

### S1_OCR_OKUYAMADI — OCR motoru okuyamadı  (18 film)

| Başlık | TRT | Eksik | Güven | Kanıt (özet) |
|---|---|---|---|---|
| BAŞKANA SUİKAST | 1991-0444-1-0000-00-1 | yonetmen, yapimci, ca… | yuksek | E:\MITAS\Database\...\ocr\ocr-dbd1a8fb\kunye.txt = 0 byte; ocr_summary.json raw_chars=0; dir_presence[0].in_raw=false, tüm cast_presence[*].in_raw=false; batch… |
| BILL | 1981-0301-1-0000-00-1 | yonetmen, yapimci | yuksek | ocr_summary.json: frame_count=840, credit_frames=10, stitched_lines=0, raw_line_count=0, bucket=BOS; kunye.txt=0 bytes; ocr_ham.txt=NOT FOUND; frames/ dir coun… |
| BILLY KİD | 1941-0035-1-0000-00-1 | yonetmen, yapimci | yuksek | ocr_summary.json: frame_count=840, credit_frames=24, raw_line_count=0, stitched_lines=0, bucket=BOS. kunye.txt: boş (1 satır, içerik yok). batch: raw_chars=0. … |
| BÜYÜK YARIŞ | 1982-0013-1-0000-00-1 | yapimci, yonetmen_yan… | yuksek | ocr_raw_all.txt satır 293:'PANDRO S. BENMWN', 294:'PANDRO S. DET'; kunye.txt satır 22-23:'PANDRO S. BENMWN / PANDRO S. DET'. Bitişik 'PANDRO S. BERMAN' ocr_raw… |
| BİR GARİP ADAM | 1965-0010-1-0000-00-1 | yonetmen, yapimci, ca… | yuksek | ocr_summary.json: frame_count=840, credit_frames=44, raw_line_count=1, stitched_lines=1, bucket=BOS. ocr_ham.txt: 'SON\n' (tek satır). kunye.txt: boş. ground_t… |
| BİR YAZ KOMEDİSİ | 1989-0065-1-0000-00-1 | yonetmen, yapimci, ca… | yuksek | ocr_summary.json: frame_count=840, credit_frames=7, stitched_lines=0, raw_line_count=0, bucket=BOS; kunye.txt=0 bytes; ocr_ham.txt=NOT FOUND; frames/ dir count… |
| EVELYN | 2002-9084-1-0000-00-1 | yonetmen | yuksek | grep 'bruce beresford|beresford' ocr_raw_all → eşleşme YOK. grep 'sophie|vavasseur|aidan quinn|julianna|stephen rea|alan bates' ocr_raw_all → eşleşme YOK. grep… |
| HER DEVRİN ADAMI | 1966-0023-1-0000-00-1 | yonetmen, yapimci, ca… | yuksek | ocr_summary.json: credit_frames=1, raw_line_count=0, stitched_lines=0, kunye_line_count=0, bucket=BOS. kunye.txt: boş (1 satır). ground_truth dir_presence[Fred… |
| MANAOS | 1979-0230-1-0000-00-1 | yapimci | yuksek | kunye.txt satir 35='PRODUCED BY', satir 36='DİRECTED BY', satir 37='ASSİSTANT DİRECTOR' — aralarinda isim yok. ocr_ham.txt satir 39='Produced by', satir 40='Di… |
| MAVİ CİNAYET | 1985-0259-1-0000-00-1 | yonetmen, yapimci, ca… | yuksek | ocr_summary.json: frame_count=840, credit_frames=12, stitched_lines=0, raw_line_count=0, bucket=BOS; kunye.txt=0 bytes; ocr_ham.txt=NOT FOUND; frames/ dir coun… |
| MÜFETTİŞ LAVARDIN | 1986-0248-1-0000-00-1 | yonetmen, yapimci | yuksek | grep -niE 'claude.*chabrol|chabrol.*claude' ocr_raw_all.txt → 0 eşleşme. grep -niE 'marin.*karmitz|karmitz.*marin' ocr_raw_all.txt → 0 eşleşme. grep -niE 'chab… |
| PİR OSMANİ | 1969-0042-1-0000-00-1 | yonetmen, yapimci, ca… | yuksek | ocr_summary.json: credit_frames=4, raw_line_count=0, stitched_lines=0, kunye_line_count=0, bucket=BOS. kunye.txt: boş. ground_truth dir_presence[Giorgi Shengel… |
| ROMUALD VE JULIETTE | 1989-0495-1-0000-00-1 | yonetmen, yapimci, ca… | yuksek | ocr_summary.json: frame_count=840, credit_frames=29, stitched_lines=0, raw_line_count=0, bucket=BOS; kunye.txt=0 bytes; ocr_ham.txt=NOT FOUND; frames/ dir coun… |
| TOPLU GÖSTERİLER | 1971-0059-1-0000-00-1 | yonetmen, yapimci, ca… | yuksek | ocr_summary.json: credit_frames=34, raw_line_count=0, stitched_lines=0, kunye_line_count=0, bucket=BOS, diegetik_frac=0.0. kunye.txt: boş. ground_truth dir_pre… |
| ZORUNLU EVLİLİK | 1989-0282-1-0000-00-1 | yonetmen, yapimci, ca… | yuksek | ocr_summary.json: frame_count=840, credit_frames=15, stitched_lines=0, raw_line_count=0, bucket=BOS; kunye.txt=0 bytes; ocr_ham.txt=NOT FOUND; frames/ dir coun… |
| ÇOK ÖZEL HABER | 2001-9367-1-0000-00-1 | yonetmen, yapimci, ca… | yuksek | E:\MITAS\Database\...\ocr\ocr-3b7ff45e\kunye.txt = 0 byte; raw_chars=0; tüm dir_presence ve cast_presence in_raw=false; batch bucket=BOS |
| ÖLÜM HAVUZU | 1975-0195-1-0000-00-1 | yonetmen, yapimci, ca… | yuksek | ocr_summary.json: credit_frames=16, raw_line_count=0, stitched_lines=0, kunye_line_count=0, bucket=BOS. kunye.txt: boş. ground_truth dir_presence[STUART ROSENB… |
| İÇİMDEKİ MİLYONLARCA SEVGİ | 2018-1171-1-0000-90-1 | yonetmen, yapımci, oy… | yuksek | ocr_ham.txt satır 0-11: '不科專龍物', '工养龍物', '不料春龍物', '公高内', '不得養寵物', '0ス', 'のス' — CJK + Japonca. Satır 12+: tamamen garble Latin (OMEVGION OLOBAL IHC, DHEVICH BBI… |

### GARBLE_KONTAMINASYON — final garble/şirket-adı ile dolu  (14 film)

| Başlık | TRT | Eksik | Güven | Kanıt (özet) |
|---|---|---|---|---|
| AKIL OYUNLARI | 2017-1043-1-0000-90-1 | yonetmen, yapimci, ca… | yuksek | ocr_raw_all.txt'de grep -niE 'ron +howard|howard +ron|directed by ron|russell +crowe|jennifer +connelly' → sıfır eşleşme. ocr_ham.txt'de aynı arama → sıfır eşl… |
| AŞKTAN DA ÜSTÜN | 1946-0026-1-0000-00-1 | yapimci | yuksek | ocr_ham.txt satır 6: 'ALFRED HITCHCOCKS' (bitişik, eşleşme VAR). satır 69-81: 'irected / Dy / rebetio / Directed by / JOHN E. TT / Miami. Flofids ThrbebFwenty … |
| BÖYLE ÇIPLAK NEREYE | 1968-0024-1-0000-00-1 | YONETMEN, YAPIMCI, CA… | yuksek | ocr_raw_all.txt grep 'jerry paris|belson|garry marshall' → 0 eşleşme; 'jerry' → yalnızca satır 345,353,360...431 'JERRY RIGGIO' (role: 2nd Policeman). kunye.tx… |
| BÜTÜN SUÇ BOSSA NOVA'DAYDI | 1992-0444-1-0000-00-1 | cast, yonetmen_alan_k… | yuksek | ocr_ham.txt satır 20-21: 'Ein Film von / Bernd Schadewald' bitişik (in_raw=TRUE teyitli). ocr_ham.txt satır 109-110: 'Buch und Regie / Bernd Schadewald' bitişi… |
| DADI GLORİA (Gloria Mundi / Baby Gloria… | 2024-1285-1-0000-70-1 | yonetmen | yuksek | ocr_ham.txt grep 'marie amachoukeli|amachoukeli marie' → satır 24 'UN FILM DE MARIE AMACHOUKELI', satır 66 'MARIE AMACHOUKELI', satır 140 'MARIE AMACHOUKELI' (… |
| GEYİK ÇOCUK | 2001-9274-1-0000-00-1 | cast | yuksek | ocr_raw_all satır 143: 'Written & Directed by', satır 144: 'RANDY REDROAD' (8 tekrar satır 143-155). kunye.txt satır 2: 'RANDY REDROAD'. kunye_teslim.md Yönetm… |
| JACKIE | 2025-1143-1-0000-50-0 | yonetmen, yapimci, ca… | yuksek | ocr_ham satır 395-396 (okundu): 'Managing Director Gilles GAILLARD / SOUND CREDITS'. kunye.txt satır 302-303: 'MANAGİNG DİRECTOR GİLLES GAILLARD / SOUND CREDIT… |
| JOE LOUIS'İN HAYATI | 1984-0211-1-0000-00-1 | yonetmen_garble, cast… | yuksek | ocr_ham satır 19: 'Directed by', satır 20: 'PETER TATUM' (bitişik). ocr_ham satır 14: 'Produced by', satır 15: 'JACK HEALY', satır 16: 'PETER TATUM'. kunye.txt… |
| KAN VE SİLAH (Tepepa / Blood and Guns, … | 1969-0077-1-0000-00-1 | yonetmen, yapimci, ca… | yuksek | ocr_summary: credit_frames=5, raw_line_count=0, stitched_lines=0, bucket=BOS; ocr klasöründe yalnızca kunye.txt (1 boş satır) ve ocr_summary.json mevcut, ocr_h… |
| PATLARSAM YANARSIN 2 | 1980-0213-1-0000-00-1 | yapimci, yonetmen_gar… | yuksek | ocr_ham.txt satır 13: 'PRODUCTION MARCEL DASSAULT 1982 All rights reserved' (bitişik). kunye.txt: DASSAULT/PRODUCTION yok. ocr_ham satır 14: 'un film de', satı… |
| SAMİMİ KONUŞMALAR | 1989-0504-1-0000-00-1 | yonetmen_garble, yapi… | yuksek | ocr_ham satır 6-9: 'produced by / shaun sutton / directed by / michael simpson'. kunye.txt satır 4-9: 'DİRECTED BY / MİCHAEL SİMPSON / PRODUCED BY / SHAUN SUTT… |
| TASIO | 1984-0212-1-0000-00-1 | yonetmen, cast | yuksek | ocr_summary.json credit_frames=414 (sıfır değil). ocr_raw_all.txt satır 22-60: 'This videocassette / including its soundtrack / is protected by copyright...' —… |
| YABANCILAR İÇİN AĞLA | 1982-0282-1-0000-00-1 | yonetmen, yapimci, ca… | orta | ocr_ham.txt: 'Sound Mixer', 'BILL CLARK, S.o.c.', 'Camera Operator', 'BUDDY BOWLES', 'Key Grip', 'JOHN FRAZIER', 'Special Effects', 'Metro Goldwyn Mayer' — oyu… |
| YERÇEKİMİ | 2017-1019-1-0000-90-1 | yonetmen, yapimci, ca… | yuksek | grep -niE 'alfonso +cu[aá]r[oó]n' ocr_ham.txt+kunye.txt → eşleşme yok. grep 'cu[aá]r[oó]n' ocr_raw_all.txt → satır 8977: 'SUPPORT STAFF TO MR. CUARON' (soyadı … |

### S1_FILTRE_DUSURDU — ham OCR'da vardı, temizleme filtresi düşürdü  (11 film)

| Başlık | TRT | Eksik | Güven | Kanıt (özet) |
|---|---|---|---|---|
| ANESTEZİ | 2007-9111-1-0000-90-1 | cast | yuksek | Grep 'HAYDEN.{0,5}CHRISTENSEN' → ocr_raw_all.txt satır 329-335 (7 satır). Grep 'JESSICA.{0,5}ALBA' → satır 338-345 (8 satır). Grep 'JESSICA|HAYDEN|CHRISTENSEN|… |
| BABA | 1988-0342-1-0000-00-1 | yapimci | yuksek | ocr_ham.txt satır 69: 'Producer', satır 70: 'LOUIS MARKS', satır 71: 'Directed by', satır 72: 'KENNETH IVES' — rol etiketleri ve isimler bitişik ve net. kunye.… |
| EMMA VE DANIEL | 2003-9128-1-0000-00-1 | yonetmen | yuksek | Grep 'INGELA MAGNER' ocr_raw_all.txt → satır 571 'REGISSÖR INGELA MAGNER', satır 710 'INGELA MAGNER' ve 100+ eşleşme. Grep 'INGELA MAGNER' kunye.txt → sıfır eş… |
| MUTLU LAZZARO | 2018-1133-1-0000-71-0 | yonetmen | yuksek | ocr_raw_all.txt satır 520: 'ALICE ROHRWACHER', satır 521: 'SCRITTO E DIRETTO DA' — 7 ayrı karedeki tekrar Grep ile doğrulandı. ocr_ham.txt grep 'ALICE ROHRWACH… |
| PARALEL EVREN | 2014-1063-1-0000-50-0 | yonetmen | yuksek | ocr_ham.txt satır 31: 'directed by', satır 32: 'JAMES WARD BYRKIT' — bitişik doğrulandı. kunye.txt satır 23: 'DİRECTED BY', satır 24: 'UNİT PRODUCTİON MANAGER'… |
| SERPİCO | 1973-1008-1-0000-50-0 | yonetmen | yuksek | ocr_ham.txt satır 31: 'MARTIN' (tek token), satır 32: 'BREGMAN' (tek token), satır 34: 'SIDNEY' (tek token), satır 35: 'LUMET' (tek token). grep -niE 'martin +… |
| SHAMUS | 1990-0324-1-0000-00-1 | yapimci | yuksek | ocr_ham.txt satır 100: 'PRODUCED', satır 101: 'NEGUS-FANCEY' (rol etiketi var + isim var; 'Olive' baş adı OCR'da yok). kunye.txt grep 'negus' → sıfır; grep 'fa… |
| SONBAHAR ÇANLARI | 1979-0107-1-0000-40-1 | yonetmen, cast | yuksek | 'ГОРИКК' grep ocr_ham.txt: satır 141 'ГОРИККЕРА' eşleşti. 'горикк' grep kunye.txt (case-insensitive): eşleşme YOK. 'ПОСТАНОВКА' grep kunye.txt: eşleşme YOK. 'А… |
| ÇALIŞMAK İÇİN GÜZEL BİR GÜN | 2018-1111-1-0000-85-1 | yapımci | yuksek | ocr_raw_all.txt satır 205-208: 'Producenti / JOVAN MARJANOVIĆ / AMRA BAKŠIĆ - ČAMO / MIRSAD PURIVATRA', satır 209-212 ve 213-216 ve 217-220 aynı blok 3 kez dah… |
| İTALYA SAVAŞ İÇİNDE | 1970-0038-1-0000-40-1 | YAPIMCI | yuksek | ocr_raw_all.txt grep 'luciano perugia' (bitişik) → 0 eşleşme. satır 929-933: 'A film produced by / FRANCESCO / LUCIANO / PERUGIA / ROSI' (4 ayrı satır). kunye.… |
| İŞARETLER VE MUCİZELER | 2000-0370-1-0000-40-1 | yapimci | yuksek | ocr_raw_all satır 121: 'Produced by' / satır 122: 'MARIN KARMITZ' (6 eşleşme: satır 122,124,126,128,130,132). Select-String kunye.txt 'MARIN KARMITZ' → eşleşme… |

### S5_6_QC_DUSURDU — QC kapısı düşürdü  (1 film)

| Başlık | TRT | Eksik | Güven | Kanıt (özet) |
|---|---|---|---|---|
| BİR AŞK HİKAYESİ | 1996-0299-1-0000-00-1 | yonetmen, cast | yuksek | 'ВОЙТЕЦК' grep kunye.txt: eşleşme YOK. 'И ПОСТАНОВКА' grep kunye.txt: satır 2 eşleşti (ad kopyalanmadı). 'ЛЕОНИД БАКШТАЕВ' grep kunye.txt: satır 43 eşleşti. 'В… |

### S0_CIKTI_YOK — pipeline künye/PDF adımına gelmeden kesildi  (7 film)

| Başlık | TRT | Eksik | Güven | Kanıt (özet) |
|---|---|---|---|---|
| Aile Gibi | 2025-1105-1-0000-73-0 | yonetmen, yapimci, ca… | yuksek | ls pdf/ → boş (0 dosya). ocr_summary: credit_frames=648, kunye_line_count=528, bucket=GUVENILIR. batch: no_output=true, auto_cause=S0_CIKTI_YOK. |
| Büyük Babamla Oda Savaşı | 2025-1036-1-0000-90-1 | yonetmen, yapimci, ca… | yuksek | ls pdf/ → boş (0 dosya). ocr_summary: credit_frames=599, kunye_line_count=412, bucket=GUVENILIR. batch: no_output=true, auto_cause=S0_CIKTI_YOK. |
| JULIA AND JULIE | 2023-1126-1-0000-90-1 | yonetmen, yapimci, ca… | yuksek | system_events.jsonl clip_id=JULIA_AND_JULIE: sadece 3 event, son event ocr_started (ocr_completed yok). clip.json modules:{} (boş — hiç OCR job kaydedilmedi). … |
| JULIA AND JULIE (Julie & Julia, 2009, N… | 2023-1126-1-0000-90-1 | yonetmen, yapimci, ca… | yuksek | clip.json modules={ocr:{status:done}}, pdf/ altında kunye_teslim.md yok; kunye.txt'de 'A FİLM BY / NORA EPHRON' (satır 17-18) ve 'MERYL STREEP / AMY ADAMS' mev… |
| KEFERNAHUM | 2018-1083-1-0000-88-0 | yonetmen, yapimci, ca… | yuksek | system_events.jsonl clip_id=KEFERNAHUM için son event ozet_atlandi. pdf dizini boş (ls doğrulandı). Gerçek yönetmen 'NADINE LABAKI' ham OCR'da garble: 'NADINE … |
| THE POST (2017, Steven Spielberg) | 2024-1081-1-0000-50-1 | yonetmen, yapimci, ca… | yuksek | clip.json modules={ocr:{status:done}}, pdf/ dizini tamamen boş; kunye.txt'de 'SASHA SPİELBERG', 'SAWYER SPİELBERG', 'ASSİSTANTS TO MR. SPİELBERG' var ama 'STEV… |
| ZAFERE KAÇIŞ (Victory / Escape to Victo… | 2024-1155-1-0000-90-1 | yonetmen, yapimci, ca… | yuksek | clip.json modules={ocr:{status:done}}, pdf/ dizini tamamen boş; kunye.txt satır 4 'A JOHN HUSTON FİLM', satır 5 'SYLVESTER STALLONE', satır 2 'MAX VON SYDOW', … |

### 5B. PIPELINE HATASI DEĞİL (dış-veri gerek / gerçek eksiklik)

### GERCEKTEN_YABANCI — yabancı film, yabancı-dil jenerik  (39 film)

| Başlık | TRT | Eksik | Güven | Kanıt (özet) |
|---|---|---|---|---|
| 3 HAYAT | 2018-1051-1-0000-56-0 | cast | yuksek | ocr_ham.txt line 10-11: 'A Film By : / Jafar Panahi' — bitişik ad+soyad teyit. kunye.txt line 11: 'JAFAR PANAHİ'. ocr_ham.txt line 58: 'بهناز جمفرى' (Farsça, L… |
| 6,5 METRE | 2019-1039-1-0000-56-1 | yapımci, oyuncular | yuksek | ocr_ham.txt satır 15: 'YAZAN ve YÖNETEN', satır 16: 'SAID RUSTAI' — bitişik, net. kunye_teslim.md: Yönetmen=SAID RUSTAI (doğru), Oyuncular=IRA NIA N + boşlar, … |
| AMERİKAN MENEKŞESİ | 2008-9113-1-0000-90-1 | YONETMEN_BOS, YAPIMCI… | yuksek | grep 'DIRECTED|produced by|TIM DISNEY|A FILM BY' ocr_ham.txt → 0 eşleşme. grep 'DIRECTED|produced by' kunye.txt → 0 eşleşme. ocr_ham.txt satır 298-299: 'CIARAN… |
| ANILAR | 2022-1196-1-0000-80-0 | yonetmen, yapimci, ca… | yuksek | ocr_raw_all.txt 15.493 satır — 'APICHATPONG' sıfır hit (doğrulandı). 'WEERASETHAKUL' yalnızca satır 12522'de Agradecimientos bölümünde 'Suaraya Weerasethakul' … |
| AŞK MEKTUBU | 1999-0500-1-0000-00-1 | yonetmen | yuksek | grep 'LUIS +MANDOKI|MANDOKI +LUIS' ocr_raw_all.txt → 0. 'Assistant to Mr. Mandoki MEAGAN RILEY-GRANT' satır 1543-1692 (11 eşleşme, soyad dolaylı). 'DIRECTED BY… |
| BEBEK KUTUSU | 2022-1066-1-0000-76-1 | yonetmen, cast | yuksek | ocr_ham.txt grep 'hirokazu|kore.eda|감독' → 0 bitişik eşleşme; ocr_raw_all.txt grep '감독' → yalnız '감독과 제작자는 다음 분들에게...' teşekkür cümlesi (isim yok); raw_foreign_… |
| BEYAZ BALON | 2021-2164-1-0000-56-0 | yonetmen, yapimci, ca… | yuksek | ocr_ham.txt satır 6: 'عباس كيارستمى' (senaryo); satır 9: 'جعفريناهى' (Panahi fused token); ocr_ham.txt satır 26: 'طراح صحنه تدوينكر، كاركردان:' (yönetmen etike… |
| BÜYÜK BABAMLA ODA SAVAŞI | 2025-1036-1-0000-90-1 | yonetmen, yapimci | yuksek | grep 'tim hill' ocr_ham.txt -> eşleşme yok. grep 'directed' ocr_ham.txt -> yalnızca 'First Assistant Director' + 'Second Assistant Director' satırları. 'PRODUC… |
| BİTMEYEN YÜRÜYÜŞ | 2008-1071-1-0000-75-1 | yonetmen, yapimci, ca… | yuksek | ocr_ham.txt satır 193: '原作·脚本·編集·監督' (director credit Japonca, bitişik Latin ad yok). grep 'kore|hirokazu|directed' → 0 eşleşme. kunye.txt satır 0-5: 'CİNCO UA… |
| CEVİZ AĞACI | 2022-1119-1-0000-22-0 | yonetmen, yapimci, ca… | yuksek | ocr_ham.txt satır 25: 'Коюшы режиссер'; satır 26: 'Ерлан Нурмухамбетов' (ad+soyad bitişik iki ayrı satırda, etiket+isim pattern); kunye.txt satır 24: 'КОЮШЫ РЕ… |
| DOLUNAY ZAMANI | 2019-1055-1-0000-50-0 | yonetmen, yapimci, ca… | yuksek | kunye.txt satır 8: 'نركس آبيار' (bitişik grep doğrulandı: ocr_ham satır 11 + kunye satır 8); ocr_summary: garble_frac=0.1064, bucket=GUVENILIR, kunye_line_coun… |
| DÜNYANIN MERKEZİNE YOLCULUK - TRT ÇOCUK… | 2012-0233-1-0000-91-1 | yonetmen | yuksek | Grep 'eric brevig|brevig eric' ocr_raw_all.txt → 0 eşleşme. Grep 'directed by' ocr_raw_all.txt → 0 eşleşme. ocr_raw_all.txt satır 4867='Assistants to Mr. Brevi… |
| DİNLE NEYDEN | 2010-9274-1-0000-88-1 | yonetmen, yapimci, ca… | yuksek | Read ocr_raw_all.txt satır 1-60: tümü Arapça. Grep 'JACQUES|DESCHAMPS|METIN HARA|AHU|TURKPENCE|ALICAN|LALE MANSUR|JEAN' → sıfır eşleşme. kunye.txt satır 8: 'Mİ… |
| ELVEDA HAYAT | 1960-0035-1-0000-00-1 | yonetmen, yapimci, ca… | yuksek | ocr_ham.txt satır 10: 'انسيه شاه مسينى', satır 31: 'انسيه شاه حسينى' — bitişik ad+soyad (Farsça yön. iki varyant). satır 33: 'سيدسعيد سيدزاده' — bitişik yapımc… |
| ERKEN GELEN YAZ | 1951-1119-1-0000-75-0 | yonetmen, yapimci, ca… | yuksek | kunye.txt satır 1-40: tamamı Japonca karakter. Satır 41: 'EARLY SUMMER DİGİTALLY RESTORED VERSİON', Satır 42: 'C1951/2016 SHOCHİKU CO., LTD.' Final kunye_tesli… |
| GÖREVİMİZ TEHLİKE 6 YANSIMALAR | 2018-1199-1-0000-90-1 | yonetmen, yapimci | yuksek | ocr_ham.txt grep: 'mcquarrie|written and directed|directed by|a film by' → sıfır eşleşme. ocr_raw_all.txt aynı grep → sıfır eşleşme. kunye.txt: yönetmen/yapımc… |
| GÜNÜNÜ GÖRECEKSİN | 1999-0466-1-0000-00-1 | yonetmen, yapimci | yuksek | grep 'BRIAN +HELGELAND|HELGELAND +BRIAN' ocr_raw_all.txt → 0. grep 'BRUCE +DAVEY|DAVEY +BRUCE' → 0. grep 'DIRECTED BY|PRODUCED BY' ocr_ham.txt → 0. 'BRIAN HEIN… |
| GÜZEL AİLELER | 2015-2158-1-0000-70-0 | yonetmen, yapimci | orta | grep -niE 'réalisé|un film de|réalisateur' ocr_ham.txt → eşleşme yok. grep -niE 'jean.paul +rappeneau' ocr_raw_all.txt → satır 167-176: hepsi 'Scénario' başlığ… |
| HÜCRE BLOĞU 99'DA KATLİAM | 2019-1241-1-0000-50-1 | yonetmen, yapimci | yuksek | ocr_ham.txt grep 'direct': 'Director of Photography' + 'Underwater Director of Photography' satırları var; 'Directed by' veya 'Written and Directed by' → sıfır… |
| IVAN'IN ÇOCUKLUĞU | 1962-1124-1-0000-72-1 | yonetmen, yapimci, ca… | yuksek | 'andrei tarkovsky' bitişik grep ocr_ham.txt: eşleşme yok. kunye.txt satır 4: 'DEVAM ET.', satır 5: 'PARTİZAN PİSLİĞİ!', satır 6: '-ACELE ET!' — TR altyazı satı… |
| KANDAHAR AYIN ALTINDAKİ GÜNEŞ | 2001-9288-1-0000-00-1 | yonetmen, yapimci, ca… | yuksek | ocr_ham.txt satır 3: 'محممن مخلبافى' (yönetmen Farsça). kunye.txt satır 3: 'محممن مخلبافى' (filtreyi geçmiş). kunye.txt satır 84: 'فيلمنامه، كاركردانى وتدوين:'… |
| KAR | 2008-2022-1-0000-61-0 | yonetmen, cast | yuksek | grep -niE 'REŽI|JASMILA|ZBANIC|DIRECTED BY|SCENARIJ|REŽIJA' ocr_raw_all.txt + ocr_ham.txt → sıfır eşleşme. kunye.txt satır 173: 'U PRODUKCİJİ / PRODUCED BY', s… |
| KAZANMA SANATI | 2011-1010-1-0000-50-0 | YONETMEN_BOS | yuksek | grep 'BENNETT MILLER|BRAD PITT|JONAH HILL|DIRECTED BY|A FILM BY' ocr_ham.txt → 0 eşleşme. ocr_ham.txt satır 57-60: 'EXECUTINE PRODUCER FOR MAJJOR LEAGUE BASEBA… |
| KAZANMA SANATI | 2011-1010-1-0000-50-1 | yonetmen | yuksek | Grep 'bennett miller|miller bennett' ocr_raw_all.txt → 0 eşleşme. Grep 'directed by' ocr_raw_all.txt → 0 eşleşme. kunye.txt satır 85='FIRST ASSESTANT DIRECTOR … |
| KEŞKE | 2011-1043-1-0000-75-0 | yonetmen, yapimci, ca… | yuksek | kunye.txt satır 101: '監督·脚本·編集 是枝裕和' (Japonca yönetmen etiketi + Koreeda adı). kunye.txt satır 3: 'ANIMATION X VISUAL EFFECT'. Final kunye_teslim.md satır 13: … |
| KLİNİK | 2004-9104-1-0000-00-1 | yonetmen | yuksek | ocr_raw_all.txt 1949 satır tarandı: 'FEARNLEY' → 0 eşleşme, 'NEILL' → 0 eşleşme, 'DIRECTED BY' → 0 eşleşme. credit_frames=173, garble_frac=0.0089. kunye.txt'de… |
| KORKULU DAKİKALAR | 1985-0195-1-0000-00-1 | yonetmen | yuksek | ocr_ham.txt'de 'directed' pattern grep: sadece 'Art Direttor' (satır 23) + 'Direttor of Photography' (satır 25) eşleşti; 'DIRECTED BY' veya 'Directed by' YOK; … |
| PAKET KAHVE | 2014-2132-1-0000-73-0 | yonetmen | yuksek | ocr_ham.txt 103 satır — yalnızca İspanyolca metin. 'director'/'dirigido'/'réalisé' için grep: 'TALLER DE DIRECCION ERCENOICA DE LA FIUTY' (satır 71) kurumu. Bi… |
| RADYOAKTİF | 2022-1194-1-0000-50-0 | yonetmen, yapimci, ca… | yuksek | Grep 'directed by marjane|a film by marjane|marjane satrapi$' → ocr_ham.txt 0 hit; ocr_raw_all.txt satır 8287+: 'Driver to Marjane Satrapi' (servis kredisi, yö… |
| REHİNELER | 2017-1138-1-0000-58-0 | yonetmen | yuksek | ocr_ham grep 'DIRECTED|REZO.*GIGINE' → 0 eşleşme. ocr_ham satır 86: 'REZO BORCHADZE' (farklı kişi). satır 332: 'GEORGE GIGINEISHVILI' Special Thanks içinde. oc… |
| SEVGİLİ AMERİKA | 1987-0342-1-0000-00-1 | yonetmen, yapimci_gar… | yuksek | ocr_ham.txt grep 'directed|DIRECTED': eşleşme yok; Bill Couturie satır 61'de 'SUPERVISOR' etiketiyle görünüyor; kunye.txt satır 21-23: 'ACTORS FOR BRİNGİNG THE… |
| SİHİRLİ DAKİKALAR | 1989-0492-1-0000-00-1 | yonetmen | orta | ocr_ham.txt grep 'irect': 'Television Direetor TONY CAUNTER' (satır 42), 'Ist Assistant Direetor GERRY GAVIGAN' (satır 54), 'Ist Assistant Dirextor (Spain) MIS… |
| TARZAN EFSANESİ | 2016-1196-1-0000-90-1 | yonetmen | yuksek | ocr_ham grep 'YATES|DIRECTED' → 0 eşleşme. ocr_ham grep 'DAVID': satırlar 46,78,102,151,207,211,284 — hepsi 'DAVID WOLFE', 'DAVID HIGGINS' vs. farklı kişi, 'DA… |
| TARİHSİZ İMZASIZ | 2017-1098-1-0000-56-1 | yonetmen, yapimci, ca… | yuksek | E:\MITAS\Database\TARİHSİZ İMZASIZ 2017-1098-1-0000-56-1\ocr\ocr-294bf86a\kunye.txt satır 3: 'رضا موذن', satır 4: 'احسان عباسى' — Farsça bitişik; ocr_ham.txt s… |
| ÇOCUKLUK ÇAĞIMIN GÖKYÜZÜ | 2011-9145-1-0000-90-1 | yonetmen, yapimci, ca… | yuksek | ocr_ham.txt satır 1-20: 'ШЭКЕН АЙМАНОВ АТЫНДАРЫ «КАЗАКФИЛЬМ»', 'РУСТЕМ ЭБДІРАШТЫН ФИЛЬМІН УСЫНАДЫ' (Kiril), 'Наталия Орынбасарова', 'Нуржуман Ыктимбарт'. Latin… |
| ÖN CEPHE | 2011-9205-1-0000-90-1 | yonetmen, yapimci, ca… | yuksek | ocr_ham.txt JANG HOON / GO SOO / SHIN HA-KYU / LEE JE-HOON / KO CHANG bitişik grep: sıfır eşleşme. raw_foreign_hits=767, raw_tr_credit_hits=0. kunye_chars=5560… |
| İLK VEDA | 2018-1046-1-0000-80-1 | yonetmen, yapimci, ca… | yuksek | E:\MITAS\Database\İLK VEDA 2018-1046-1-0000-80-1 2\ocr\ocr-e4e8ceac\kunye.txt: birinci kopya ile birebir aynı 52 satır içerik; kunye_teslim.md (Üretim 14.06.20… |
| İNTİKAM PEŞİNDE | 2003-9120-1-0000-00-1 | yonetmen, yapimci | yuksek | Select-String ocr_raw_all.txt 'OBLOWITZ' → 0 eşleşme. 'DIRECTED' → 0 eşleşme. (Get-Content ocr_raw_all.txt).Count = 2978. Satır 1-26: 'M / M / MILLE / MILLENNI… |
| ŞAMBALA | 2024-1028-1-0000-23-0 | yonetmen, yapimci, ca… | yuksek | ocr_ham.txt satır 45: 'Артыкпай Сүйүндуковдун'; satır 46: 'тасмасын тартуулайт' (= 'presents the film of', SUNAN/YAPIMCI rolü); ocr_ham.txt satır 68: 'Сценарий… |

### GERCEKTEN_YOK — alan jenerikte gerçekten yok  (11 film)

| Başlık | TRT | Eksik | Güven | Kanıt (özet) |
|---|---|---|---|---|
| BAŞARININ BEDELİ | 1981-0240-1-0000-00-1 | yapimci | yuksek | ocr_raw_all.txt grep 'gus trikonis|trikonis' → 0 eşleşme. grep 'greg blackwell|blackwell' → satır 3253,3258,3264,3271,3278,3284,3287,3291,3299,3303,3318 — tama… |
| DEMİR LEYDİ | 2011-1127-1-0000-50-1 | yapimci | yuksek | grep -niE 'PRODUCED BY|EXECUTIVE PRODUC|DAMIAN JONES' kunye.txt + ocr_raw_all.txt → sıfır eşleşme. grep -niE 'Producer' ocr_raw_all.txt → satır 2451: 'Producer… |
| FIRINCININ KARISI | 2019-1241-1-0000-91-1 | cast | yuksek | kunye.txt satır 21-29 bizzat okundu: YONETMEN // DIRECTOR → MAHMUT KAYIMTU, ERTUĞRUL FINDIK; ardından OYUNCULAR / CAST → 5 isim. ocr_summary.json: garble_frac=… |
| MORRİE İLE HER SALI | 1999-1127-1-0000-50-0 |  | yuksek | grep 'MICK +JACKSON|DIRECTED BY' ocr_ham.txt → 0 eşleşme. ocr_raw_all.txt aynı → 0. kunye_teslim.md satır 20: 'Yönetmen: MICK JACKSON' (KB-fill). ocr_ham.txt s… |
| NÜKLEER KABUS-JAPONYADAKİ KRİZ | 2011-9191-1-0000-90-1 | yonetmen, yapimci | yuksek | ocr_ham.txt satır 1-20: haber lower-thirds ('JAPAN FAR', 'TSUNAMI HITS JAPAN', 'LIVE', 'BREAKING NEWS', 'FUKUSHIMA 2:54PM PST MAR 11 2011'). raw_chars=4090 (ço… |
| PARA VE ÖLÜM (BINGO: SCENES OF MONEY AN… | 1993-0280-1-0000-00-1 | yapimci | yuksek | ocr_ham.txt satır 1-75 tam okundu — 'produced' veya 'producer' grep: sıfır eşleşme. 'ironside' grep: sıfır eşleşme. ocr_ham.txt satır 39-40: 'Production Manage… |
| TEHLİKELİ SULAR | 1994-0322-1-0000-00-1 | yapimci | yuksek | ocr_ham.txt 'produced' veya 'producer' grep: sıfır eşleşme. ocr_ham.txt satır 1: 'PAN ASIA AMERICA ENTERTAINMENT' — şirket adı, kişi değil. ocr_ham.txt 132 sat… |
| TOMRİS | 2019-1096-1-0000-22-0 | yapımci | yuksek | ocr_ham.txt satır 161-164: 'Aidar ESPENBETOV / Nazıra BAKAEVA / Keńesshiler / Krym ALI YNBEKUV' — bitişik; kunye.txt satır 112-114: 'AİDAR ESPENBETOV / NAZIRA … |
| YENİ BİR HAYAT | 1996-0258-1-0000-00-1 | yapimci | yuksek | grep -niE 'PRODUCED BY|EXECUTIVE PRODUC' ocr_raw_all.txt → yalnızca 'Music Produced by SAVAGE FRUITARIAN PRODUCTIONS' (18+ satır). grep -niE 'DIRECTED BY|WRITT… |
| YETİMHANE GÜNLERİ | 2001-9206-1-0000-00-1 | yapimci | yuksek | grep 'produced by|executive producer' ocr_ham.txt -> 0 eşleşme; grep 'line producer' -> 'Line Producer' (satır 59). ocr_ham.txt satır 6: 'THOMAS ELLIOTT' (biti… |
| ÖLÜM BÖLGESİ | 1999-0473-1-0000-00-1 | yapimci | yuksek | grep 'produced by|executive producer' ocr_ham.txt -> 0 eşleşme. Satır 4: 'IAN DAVID DIAZ' (bitişik, 'AN' öneki ile An Ian David Diaz film bağlamı). Satır 86: '… |

## 6. Öncelik (en çok film kurtaran düzeltme — bilgi amaçlı, düzeltme istenmedi)

1. **Aşama 2 rol-eşleme** → ~90 film: üst-billing oyuncu bloğunu tanı, rol-takasını engelle (gerçek yönetmen kunye.txt'de mevcutken oyuncu yazılmasın).
2. **Aşama 1 diegetik kare-seçimi** → ~52 film: düşük-kontrast/canlı-sahne-üstü jeneriği CLIP eşiğinde jenerik say.
3. **Aşama 1 garble/temizleme** → ~25 film: okunan ismi düşürme + garble'ı final'e geçirme.
4. **Yabancı film yolu** → ~39 film: web/KB ile doldur (OCR-otorite korunarak).
5. **Yarım işlemler** → 7 film + 13 ham no-output: batch tamamlanınca künye→PDF adımını koştur.

## 7. Uyarılar

- Snapshot: tarama sırasında Database **konsolidasyon + canlı gece-batch** altındaydı; `_2/_3` kopyalar ve birkaç in-flight klasör bu yüzden. Bulguların gövdesi (eski/stabil filmler) sağlam; in-flight/no-output set batch bitince yeniden bakılmalı.
- Detay JSON: `outputs/kunye_rootcause_final.json` (film-film, kanıt+güven), `outputs/kunye_eksik_evidence.json` (deterministik kanıt), `outputs/kunye_eksik_audit.json` (ham tespit).