# MITAS 100-Film Koşu Denetimi — Canlı Rapor

**Başlangıç:** 2026-06-22 ~01:50 (watchdog baseline)
**Mod:** SALT-OKUNUR denetim. Boru hattına dokunulmaz, commit yok, süreç öldürülmez.
**Watchdog:** `outputs/RUN_WATCH_20260622/watchdog.sh` — yeni `_DURUM.json` çıkınca tetiklenir.

## Koşunun etkin konfigürasyonu (start_mitas.ps1 + default)
- `MITAS_QC2=1`, `MITAS_QC2_WEB=1`, `MITAS_QC_BLOCK=1` (birleşik künye QC bloğu AKTİF)
- `MITAS_CREDIT_DETECT=1` + `MITAS_JENERIK_DETECT=1` (default) → **iki jenerik dedektörü aynı anda aktif**
- `MITAS_MASTER_PNG_AUTO=1` (default), timeout 300s
- `MITAS_GEMMA_FULLCOVER=1` (tam-kapsam video-künye okuma, ~+2.5dk/film)
- `MITAS_KB_CAST_ADD=1`, `MITAS_QC_DIRECTOR_ANCHOR=1`
- `MITAS_SES_DIL_KONTROL=0` (ses/dil sorunu KONTROL'e yollamaz), `MITAS_OCR_GLM_CONSENSUS=0`

## Per-film artefakt haritası (denetim girdileri)
`Database/<AD TRT>/`:
- `frames/giris/`, `frames/cikis/` → jenerik tespit kanıtı (Eksen 1)
- `ocr/ocr-*/kunye.txt`, `ocr_ham.txt`, `ocr_raw_all.txt`, `ocr_summary.json` → isim-kurtarma, OCR (Eksen 2,3,4,9)
- `master/giris.png`, `master/cikis.png`, `master_manifest.json` → master PNG (Eksen 2)
- `pdf/kunye*.pdf`, `kunye_teslim.md` ; `<TRT AD>.pdf` (yüzey teslim) → PDF sadakat (Eksen 9)
- `_DURUM.json` (karar/neden/teslim/qwen_qc) → çıktı yönlendirme + eksik alanlar (Eksen 5,6,7,8)
- `_log.jsonl` → aşama izi (tüm eksenler)

---

## A) ÖN KOD DENETİMİ (10 eksen, köşe-bucak) — `wf_4fd64209-a40` ✅
Tam rapor: [KOD_DENETIMI.md](outputs/RUN_WATCH_20260622/KOD_DENETIMI.md). 10/10 eksen, **6 doğrulanmış CRITICAL/HIGH, 0 çürütüldü** (her biri hem kodda hem canlı çıktıda teyitli).

**Genel hüküm:** Boru hattı doğru-yanlış ayrımında **titiz**; memory'deki 3 "açık kritik" (`_v4j` çökme, `_qc1_failed` ölü-kablo, K2 propagation) **koda göre KAPALI**. Asıl zayıflık **doğruluk değil KAPSAM (recall)** + gözlemlenebilirlik.

| Kod | Şid. | Bulgu | Dosya | Canlı kanıt |
|---|---|---|---|---|
| **H1** | HIGH | Latin-dışı (Kiril/Yunan/Arap) cast+yönetmen `_fold`'da SIFIRLANIR; qc_block translit makinesi boş-listeyle ÖLÜ | credit_text_read.py:34-42; credit_qc_block.py:415-437; tek_film_kunye.py:614 | CEMİLE: OCR Kiril kadroyu mükemmel okumuş → final "oyuncu yok" |
| **H2** | HIGH | Boş OCR cast → web title+year ile YANLIŞ filme kilit → yabancı kadro doldurma (OCR-otorite ihlali, PROPAGATION türü) | credit_qc_block.py:471-489,562-572,611 | ÇILDIRIŞ içerik "THE JACKET" |
| **H3** | HIGH | İnternet-özet fallback YALNIZ Kürtçe'ye bağlı → diğer transcript-yok filmler placeholder | mitas_pipeline.py:1728-1771 | ÇILDIRIŞ (dil=EN, özet=placeholder) |
| **H4** | MED | 25fps video yolunda saniye ~%4 şişiyor → `end_sec` süreyi aşıyor | jenerik_detector.py:769,533 | ANNE BOLEYN 8013>7975; FLASHDANCE 5637>5600 |
| **H5** | MED | Dizi modunda cast 8'e zorla kırpılıyor ("herkesi kapsa" ihlali) | credit_qc_block.py:369,572 | tip-0 etiketi bu sette güvenilir "dizi" değil |
| **A8** | MED | Boş/garble cast → TÜR+orijinal-ad+afiş birlikte düşer (tek kök) | credit_kb_lookup.py:173-203 | — |

**Gözlemlenebilirlik boşlukları:** master-PNG olayları `_log.jsonl`'a yazılmıyor (A2); 20/32 KONTROL filmi etiketsiz (A6, router `_sig` kapsam eksiği).

> NOT: Tümü yalnız RAPOR. Hiçbir kod değiştirilmedi/commit edilmedi (kural: değişiklik yalnız Çağatay talimatıyla).

---

## B) CANLI FİLM DENETİMLERİ (partiler)
_Watchdog tetikledikçe parti parti eklenecek._

Oturum = RED ROCK ile başlayan koşu (W:\ kaynağı), RED ROCK + sonrası.

| # | Film | Karar→Teslim | Master giriş/çıkış | Doğr. kırmızı | Kritik not |
|---|------|--------------|--------------------|----------------|-----------|
| 1 | RED ROCK 9152 | Kontrol→KONTROL | **footage-bloat** / smear | (master) | giriş 17726px footage; final kadro DOĞRU (Caan/Carradine/Gyllenhaal); karar↔route çelişki |
| 2 | HAYATIN DENGESİ 9162 | Hazır→**ONAYLI** | footage-bloat | 2 | KIM BERLIN (KB, ekran=KIMBERLEY, form bozuk); LEFEBVRE→LEFEVRE OCR ezme; **şüpheli ONAYLI** |
| 3 | SIRILSIKLAM 9187 | Kontrol→KONTROL | footage-bloat | 2 | yapımcı alanı kirliliği (BEN SILVERMAN=cast, ROBERT SIMONDS=disclaimer); doğru KONTROL |
| 4 | YAĞMUR 9265 | Kontrol→KONTROL | footage-bloat | 1 | **🔴 başrol SCOTT COOPER kadrodan tamamen düştü** (credit_validate yön düzeltti, cast'e geri eklemedi) |
| 5 | MANASLU 9318 (ORF belgesel) | Kontrol→KONTROL (✓çelişki yok) | footage-bloat (belgesel-doğal) | 1 | **🔴 UYDURMA OYUNCU "HANS EBNER"** (VL halüsinasyonu PDF'e girmiş); özel-tür `belgesel/_KIMLIK_CAST` doğru yönlendirme |
| 6 | DÖRT CENAZE BİR NİKAH 9137 (Plots with a View) | Hazır→**ONAYLI** | footage-bloat / **boş** (çıkış slit çökmüş 900×89) | 2 | **🔴 Christopher Walken + Lee Evans 8-cap'te düştü** (OCR'da net); JOSH→JOSHUA ezme; **şüpheli ONAYLI** |
| 7 | ÖLDÜREN POZ 9172 (Exposure) | Kontrol→KONTROL (✓) | footage-bloat / yok | 2 | ✅ **İçerik TEMİZ** (8 cast OCR-otoriter, ezme/sızıntı YOK, yön doğru). Kusurlar reporting-katmanı: `neden` bayat-şablon (gerçek-olmayan "web kilidi") + afiş fetch edilmiş ama PDF'e gömülmemiş (HAFIF_AFIS) |
| 8 | KULÜP EVİ DEDEKTİFLERİ 9065 (Clubhouse Detectives) | Hazır→**ONAYLI** | footage-bloat / var | 1 | İçerik sağlam (kadro/yön/yapımcı/özet/afiş doğru) ama **v4 isim-ezme**: JAIMEE **LEE** WYSON→JAIMEE WYSON + DELANY→DELANEY (OCR-otorite ihlali, iç .txt doğru formu koruyor) |
| 9 | OLAY YERİ-BÜYÜK AŞK 9084 (Alman Tatort) | Kontrol→KONTROL (✓) | footage-bloat / footage-bloat | 2 | Kimlik DOĞRU çözüldü (doğru KONTROL). **🔴 footage-bloat→başrol kaybı** (Manchen/Held/Broumis master'da görünür, OCR'da yok); **🔴 "Redaktion" (Alman crew) başrol cast'e sızdı** (THOMAS MARTIN, MELANIE WOLBER) |
| 10 | KLEPTOMAN 9127 | Kontrol→KONTROL (route.folder=ONAYLI **bayat**, fiziksel KONTROL ✓) | footage-bloat / **temiz** | 0 | Denetim 529'dan yarım kaldı ama corroborate: içerik temiz (yön THOMAS TRAIL + cast OCR-doğru, ezme yok, giriş footage künyeye sızmadı). 1 sarı: yapımcı ANDY WINDERBAUM KB-eklenti (zaten neden'de flag'li) |
| 11 | KÖŞENİN KRALI 9132 (King of the Corner) | Kontrol→KONTROL (**KIMLIK**) | footage-bloat / **temiz** | 0 | ✅ İçerik TEMİZ (Riegert yön+başrol, cast OCR-doğru, ezme/sızıntı yok). KONTROL sebebi **KIMLIK yanlış-alarmı** (klip'te XML-cast yok→kesişim 0). Ters-vaka: ANTHONV MACTROMAURO garble düzeltilmemiş. Denetim 529'dan degrade |
| 12 | KOMİSER CORDIER 9065 (Commissaire Cordier, Fransız) | Hazır→**ONAYLI** | footage-bloat / var | 1 | İçerik çoğu doğru (yön Vincent Monnet/yapımcı/özet/afiş OK, ezme yok) ama **🔴 senarist "Scénario/MARC-ANTOINE LAURENT" oyuncuya sızdı** (Fransız crew); **şüpheli ONAYLI** → KONTROL olmalı |
| 13 | GEÇMİŞİN GÖLGELERİ 9074 (Back in the Day) | Hazır→**ONAYLI** | footage-bloat / footage-bloat | 1 | İçerik factual doğru, ezme/uydurma yok AMA **kadronun 5/8'i KB-türetilmiş** (OCR sadece 3 okudu, 2'si aslında Co-Exec-Producer); yön imdb/wiki'de doğrulanamadı → **H2-komşusu** (yanlış-film eşleşseydi yanlış kadro dolardı) |
| 14 | HAYALPEREST 9081 (Dreamer) | Kontrol→KONTROL (KIMLIK_CAST) | footage-bloat / footage-bloat | 0 | ✅ **Doğru karar + fail-safe çalıştı**: OCR sadece 1 cast okudu (footage-bloat), kimlik kilitlenemedi → KONTROL. **Uydurma YOK** (poster'daki Dakota Fanning/Freddy Rodriguez OCR-frame'de yok diye cast'e SIZMADI). Meşru-eksik |
| 15 | KARAYİP KORSANLARI 2 9148 (Pirates 2) | Hazır→**ONAYLI** | footage-bloat / **YOK** (tespit edildi conf 0.96 ama üretilmedi) | 2 | ✅ **Kadro/yön TEMİZ** (8 oyuncu+Verbinski OCR-doğru, ezme/sızıntı/uydurma yok; 8-cap yıldız düşürmedi). AMA **🔴 PDF afişi YANLIŞ film** (Pirates 3 "At World's End" basılmış, film Dead Man's Chest); OCR doğru okumuş, poster_fetch yanlış-sekel çekti |
| 16 | SIRDAŞ 9162 (Entrusted, yabancı) | Kontrol→KONTROL (route=ONAYLI bayat) | footage-bloat / footage-bloat | 1 | Doğru KONTROL (fail-safe). **v4 isim-ezme** (Sangster→**Brodie**-Sangster, **Steven**→Stephen Moyer); ayrıca Lhermitte cast'ten düştü + "Dialogue Coach" Dagmar Schwarz cast'e sızdı + "Assistant to" Campana yapımcıya yükseldi — hepsi KONTROL'de insan düzeltir |
| 17 | PRESTİJ 9179 (The Prestige) | Kontrol→KONTROL (route=ONAYLI bayat) | footage-bloat / **YOK** | 0 | ✅ İçerik TEMİZ (8 cast OCR-doğru, ezme/sızıntı/uydurma yok; Nolan+yapımcı OCR-boş alana KB-doldur=doğru kişi). KONTROL meşru (QC1 RED). Çıkış master üretilmemiş (2. vaka) |
| 18 | ŞİRKET ADAMLARI 9157 (The Company Men) | Hazır→**ONAYLI** | footage-bloat / clean | 3 | Kadro/yön/özet TEMİZ+OCR-sadık AMA **🔴 yapımcı alanı "SPECIAL THANKS" bloğundan sızmış** (Nick Kazan vd. yapımcı değil); **orijinal-ad ezme COMPANY MEN→MAN**; sidecar 3≠8 yapımcı; **şüpheli ONAYLI** |
| 19 | NAMUS DÜŞMANI 9262 (Arap-yazısı künye) | Kontrol→KONTROL (✓) | footage-bloat / footage-bloat | 1 | **🔴 H1 CANLI TEYİT:** Arap-yazısı künye MÜKEMMEL okundu (garble_frac=0!) ama extractor parse edemeyince **12 oyuncu + yön Zeki Alasya DÜŞTÜ** → PDF'e sadece 1 yapımcı. Doğru KONTROL (fail-safe, uydurma yok). `neden`="garble okunamadı" YANILTICI (okundu-atıldı, kök-neden gizli) |
| 20 | İNTİKAM ÇOCUKLARI 1041 (Brotherhood of the Rose) | Hazır→**ONAYLI** | footage-bloat / yok | 1(MED) | ✅ **İçerik TEMİZ** (7 cast+yön+yapımcı OCR-sadık, ezme/sızıntı yok; 1 gerçek oyuncu KB-additive=meşru). Tek kusur master footage-bloat (kozmetik, master_png=null→teslime etkisiz). **İlk gerçekten temiz ONAYLI** |
| 21 | SESSİZ ÇOCUK 2151 (The Silent Child, kısa) | Kontrol→KONTROL (✓) | footage-bloat / footage-bloat | 3 | **🔴 EN CİDDİ rol-eşleme çökmesi:** cast alanına **6 YAPIMCI sızmış** (Rebecca Harris vd.), **7 gerçek oyuncu düşmüş** (Rachel Shenton, Maisie Sly...) = neredeyse tam tersine çevirme. OCR temiz okumuş, extractor yanlış-blok seçti. Doğru KONTROL (fail-safe) ama `neden`="yanlış-film şüphesi" YANILTICI (film doğru) |
| 22 | BEYAZ BALİNA 9031 (Kürtçe) | Kontrol→KONTROL (✓) | footage-bloat / clean | 2(MED) | ✅ **İçerik TEMİZ** (8 cast OCR-sadık, ezme/sızıntı yok, rol-öneki temizlendi). KU→TMDB özet çalıştı (H3 mekanizması teyit). Kusurlar: giriş master footage-bloat (kozmetik) + **sidecar _teknik.txt/md HÂLÂ GARBLE** (VAIIAP/BURIIAN) PDF temizken |
| 23 | POTA 2020-0011 (Türk) | Kontrol→KONTROL (OZET) | footage-bloat / yok | 1 | İçerik çoğu OCR-sadık (**ezme YOK, ERDOĞDU korundu**), doğru KONTROL. **🔴 başrol EGEMEN ALMACI atıldı** (OCR'da 38×+afişte 4., extraction/merge sessizce düşürdü) = 4. lost-actor. KU→dürüst placeholder özet (H3 meşru, uydurma yok) |
| 24 | ZORLU ADAM 1957-0023 (The Hard Man, western) | Hazır→**ONAYLI** | footage-bloat / footage-bloat | 1(MED) | ✅ **İçerik TEMİZ** (8 cast+yön+2 yapımcı OCR-sadık, ezme/sızıntı yok; **v4 RUDY BOND+2 yapımcıyı OCR'dan GERİ KAZANDI**=recovery çalıştı). Tek kusur sidecar bayatlığı (PDF doğru). **2. temiz ONAYLI** |
| 25 | KÖPRÜNÜN ÖTESİ 1957-0034 (Across the Bridge) | Hazır→**ONAYLI** | footage-bloat / yok | 1 | İçerik OCR-temelli (ezme/uydurma yok) AMA **🔴 5 gerçek oyuncu DÜŞTÜ** (Gifford/Brook/Deeming/Maxted/Nagy, OCR'da 14-17×) + **🐕 KÖPEK "DOLORES" oyuncu listelendi** ("trained by"=hayvan kredisi). Şüpheli ONAYLI |
| 26 | BEKARLIK SULTANLIKTIR 1958-0046 " 2" (İtalyan, Il Marito) | Kontrol → **MÜZİKAL klasörü** (route=KONTROL ama teslim muzikal!) | footage-bloat / footage-bloat | 3 | **🔴🔴 CRITICAL: OCR BOŞ** (credit-detect footage'ı jenerik sandı→0 satır) iken **KB UYDURMA yapımcı enjekte etti** (NORMAN LEAR/BUD YORKIN=Amerikan sitcom, İtalyan filmle alakasız). **Kök: tek_film_kunye.py:563-564 KB-yapımcı KİMLİK-KAPISIZ dolduruyor.** + özel-tür kapısı KONTROL'ü ezdi (yanlış-sınıf MÜZİKAL) |
| 27 | BEKLENEN BOMBA 1959-0005 (Muharrem Gürses) | Kontrol→KONTROL (**gereksiz**) | clean / footage-bloat | 3 | İçerik TEMİZ+DOĞRU (8 cast OCR-kaynaklı, yön Muharrem Gürses IMDb+XML+Wiki DOĞRULANDI) ama **🔴 FALSE-POSITIVE KIMLIK → gereksiz KONTROL** (cast-kesişim=0 garble-vs-XML, oysa yön doğrulanmış). + çıkış footage-bloat (SON kartı, kapanış yok) + sidecar bayat |
| 28 | BÜLBÜLÜ ÖLDÜRMEK 1962-0033 " 2" (To Kill a Mockingbird) | Hazır→**ONAYLI** | clean / footage-bloat | 2 | **🔴 19 Türkçe SESLENDİREN tamamen düşürüldü** (OCR'da temiz "seslendirenler" bloğu garble=0; 8-cap orijinal kadroyu tutup TR-dublaj kadrosunu attı) = TRT için kritik kayıp + dublaj-ekibi düştü; + GREGORY PECK OCR'sız KB-eklendi (dayanaksız) |
| 29 | MARY POPPINS 1964-0031 (müzikal) | Kontrol→KONTROL (route=ONAYLI bayat) | footage-bloat / footage-bloat | 0 net | ✅ İçerik TEMİZ (8 cast OCR-sadık, ezme/sızıntı yok). Doğru KONTROL (yön R.Stevenson ekranda var ama düşük-kontrast→OCR+VL okuyamadı, KB doğru doldurdu). 2 MEDIUM: route-bayat + yön recall-açığı. **Tür "KOMEDİ/AİLE" etiketlendi (müzikal değil!)** → muzikal-klasöre GİTMEDİ |
| 30 | AYI YOGİ 1964-0032 (animasyon, Yogi Bear) | SORUN → **ANİMASYON klasörü** (özel-tür çalıştı) | footage-bloat / footage-bloat | 5 | **🔴 GARBLE teslim kadrosuna GİRDİ:** stitch temiz OCR'ı (JAMES DARREN 7×) atıp 1× garble'ı seçti (DAMES DARREN), JULIE BENNETT→JEJULIEA BENNETT, çöp "JJAME SBENREET" cast'e, 2 voice-actor düştü. **garble_frac=0.0 Latin-garble KÖR NOKTASI** (memory teyit, ilk canlı) → onaylandı |
| 31 | KEDİ GÖZÜ 1969-0057 " 2" (Eye of the Cat) | Hazır→**ONAYLI (YANLIŞ, KONTROL olmalıydı)** | clean / footage-bloat | 4 | **🔴🔴 OCR-OTORİTE İHLALİ (kurucu kanun):** başrol ELEANOR PARKER (OCR'da 6×) DÜŞTÜ + MICHAEL SARRAZIN (OCR'da 0×) KB ile EKLENDİ = okunanı-çıkar/okunmayanı-ekle. + yapımcı HAZELTON/**HAZLETON** çift-kayıt (uydurma yazım). "kusursuz" damgalı |
| 32 | BABAMIN SİNEMASI 1971-0047 " 2" (Le Cinéma de Papa) | Kontrol→KONTROL (✓) | clean / footage-bloat | 1 | **🔴 GÖMÜLÜ film-içi-film kadrosu sızdı:** "Aux Yeux du Souvenir" sekansı oyuncuları (Michele Morgan, Jean Marais) ASIL kadronun #1-#2'sine, gerçek başrol Barray #3'e düştü. **Yön çelişki-çapasıyla doğru kurtarıldı (Berri)** ama cast'te o koruma yok. + H5 kırpma (20+→7) |
| 33 | DOKTOR POPOL 1972-0107 (Docteur Popaul, Chabrol) | Hazır→**ONAYLI** | clean / footage-bloat | 3(MED) | Yüksek-kalite OCR, içerik çoğu sadık (yeni kalıp yok). Bilinen: billed oyuncu **Daniel Ivernel 8-cap'te düştü** (lost-actor #6) + **Belmondo yapımcı OCR-dışı KB-eklendi** (OCR-otorite, ONAYLI). çıkış master footage-bloat (kozmetik) |
| 34 | ÇELİK MASKE 1974-0173 " 2" (Who?, 1973) | Kontrol→KONTROL (route=ONAYLI bayat) | clean / var | 3 | Doğru KONTROL. **🔴 ORİJİNAL-AD FABRİKASYONU:** "ROBO MAN - WHO MAN IN THE STEEL MASK" — OCR'da "ROBO/STEEL/WHO" 0×, gerçek kart "THE MAN IN THE STEEL MASK/WHO?" → "ROBO" tamamen uydurma. + cast 8-cap (14+→8, lost-actor #7) + sidecar bayat + ana-dil TR yanlış (İngilizce) |
| 35 | HABABAM SINIFI UYANIYOR 1976-0147 | Hazır→**ONAYLI (EN BOZUK ONAYLI)** | footage-bloat / footage-bloat | 6 (1 CRITICAL) | **🔴🔴 Türk klasiği "kusursuz" damgalı ama FELAKET:** ünlü başroller (Halit Akçatepe/Şener Şen/Şevket Altuğ/Sezerel/Gürses) ekranda var ama **OCR açılış yıldız-kartlarını HİÇ okumadı** (sadece kapanış yardımcı-kadro)→başroller YOK. + OCR ezme **Halit→Sıtkı Akçatepe** + yapımcı NAHIT ATAMAN uydurma + **🔴 Türkçe film KU sanıldı→yanlış-film TMDB özeti** + orijinal-ad Kürtçe garble |
| 36 | ANGOLA'DAN KAÇIŞ 1976-0184 (Escape from Angola) | Kontrol→KONTROL (✓) | footage-bloat / footage-bloat | 1(MED) | İçerik TEMİZ + kimlik doğru (afiş teyit), ezme/sızıntı/uydurma yok. Bilinen: **orijinal-ad EZME** "ESCAPE FROM ANGOLA"→"ESCAPING FORM ANGOLA" (3. orijinal-ad bozulması) + **KIMLIK false-positive** (yabancı film XML-cast yok→kesişim 0, 3. vaka) + footage-bloat (kozmetik) |
| 37 | DOSTLUK 1977-0215 (Cody) | Kontrol→KONTROL (✓) | footage-bloat / footage-bloat | 1 | İçerik sağlam (yön/yapımcı/özet/orijinal-ad doğru, ezme/uydurma yok). **🔴 Patricia Kane (OCR'da 38×, rol Rosemary) cast'ten düştü** (blok-segmentasyon, 8-cap DEĞİL = 8 altında kayıp) = lost-actor #8. Doğru KONTROL ama neden-listesi eksik oyuncuyu içermiyor |
| 38 | DELİ KAN 1978-0225 " 2" (Youngblood) | Hazır→**ONAYLI** | footage-bloat / smear | 2(MED) | İçerik doğru, ezme/uydurma yok AMA **🔴 kadronun 5/8'i MÜZİSYEN:** funk grubu WAR üyeleri (Papa Dee Allen/Lonnie Jordan...) "music performed by WAR" bloğundan OYUNCULAR'a atandı (kategori hatası). + v4 REN→RENN reformat + sidecar bayat. ONAYLI ama kadro yanlış |
| 39 | FEDORA 1978-0238 (Billy Wilder) | Kontrol→KONTROL (route=ONAYLI bayat) | footage-bloat / footage-bloat | 2 | Kimlik doğru, ezme/uydurma yok. **🔴 Kapanış "Cast of Characters" tablosu YOK SAYILDI** → başrol William Holden + Henry Fonda/José Ferrer (OCR'da net) düştü, sadece açılış-8 alındı = lost-actor #9. **HABABAM'ın TERSİ** (orada açılış kaçtı/kapanış alındı) → boru hattı tek kredi-bloğu seçip diğerini kaybediyor |
| 40 | KORKULU GECE 1979-0236 " 2" (Night Terror) | Kontrol→KONTROL (route=ONAYLI bayat) | footage-bloat / footage-bloat | 2(MED) | ✅ **İçerik temiz** (8 cast+yön+2 yapımcı OCR-sadık, garble temizlendi "Harper Cone"→Harper, ezme/uydurma/eksik yok). Kusurlar kozmetik: çıkış master-bloat + DAMON+**BRADLEY** KB orta-ad enrichment (doğru kişi). Yeni kalıp yok |
| 41 | ÇOCUKLARIN SAVAŞI 1980-0220 (La guerra de los niños, İspanyol Parchís müzikali) | Hazır→**ONAYLI (yanlış, KONTROL olmalıydı)** | footage-bloat / footage-bloat | 4 | Kimlik+yön doğru (Javier Aguirre OCR'dan) AMA **🔴 AFİŞ TAMAMEN YANLIŞ FİLM:** çocuk müzikaline aynı İng. başlıklı ("The Children's War") **Acholi çocuk-asker BELGESELİ** posteri gömülmüş (H2 afiş-kilidi). + KB OCR-dışı soyad ekledi (Parchís üyeleri ön-adla okundu) + cast-sayısı 4-farklı (sidecar bayat) |
| 42 | MAYMUN AKLI 1981-0270 " 2" (Monkey Business, 1952 Hawks) | Hazır→**ONAYLI** | footage-bloat / footage-bloat | 0 (1 kozmetik) | ✅ **TAM TEMİZ (10/10):** 8 cast (Cary Grant/Marilyn/Hawks) OCR-sadık, ezme/sızıntı/uydurma yok, TR-dublaj doğru dışlandı. Sadece kozmetik master-bloat + sidecar bayat. **3. tam-temiz ONAYLI** |

---
**🛑 KOŞU DENETİMİ DURDURULDU — 42 film tamamlandı (Çağatay talimatı). Watchdog kapatıldı. Final rapor (tarafsız Opus inceleme) hazırlanıyor → [FINAL_RAPOR.md](outputs/RUN_WATCH_20260622/FINAL_RAPOR.md).**

**Master PNG — iki AYRI footage-bloat türü (önemli ayrım):** Master PNG'nin KENDİSİ çıktıyı bozmuyor (OCR master kullanmıyor, `master_png=null`). Ama iki farklı kök var:
- **ÇIKIŞ footage-bloat = master-compose BUG** (kök zaten teşhisli, bkz. memory `master_png_blackbg_cut`): `db_compose_master.py:333 split_runs` siyah-zemin kapanış karelerini phaseCorrelate ile çöp sanıp KESİYOR → master footage gösteriyor AMA kaynak kredi temiz, OCR (credit_frames'ten) okumuş. → **kozmetik, OCR-kaybı DEĞİL** (RED ROCK çıkış %94 footage örneği).
- **GİRİŞ footage-bloat = gerçek diegetik kredi** (yazı hareketli açılış footage'ı üstüne bindirilmiş): burada **per-frame OCR de isimleri kaçırabiliyor** → gerçek kadro kaybı. **Kanıt OLAY YERİ:** başroller (Manchen/Held/Broumis) master'da görünür, OCR'da 0, PDF'te yok. → bu durumda footage-bloat = **kadro-kaybı uyarısı** (kod denetimi A7/S1_FRAME_KAPSAM canlı teyit).

### Film 1 — HAYATIN DENGESİ (LIFE IN THE BALANCE) detay
Teslim tutarlı (ONAYLI'ya gitti, export/ONAYLI'da mevcut). 2 doğrulanmış kırmızı bulgu:

1. **[HIGH] Yapımcı KIM BERLIN — OCR-dışı eklenti + form bozulması** (eksen 2/5/9)
   - OCR ham/raw/kunye.txt'te `kim|berlin|kimber` = **0 eşleşme**. Nihai PDF + yüzey `.txt`'te yapımcı olarak "KIM BERLIN" VAR.
   - Ekrandaki gerçek isim (master/giris.png tile-3, görsel): **"KIMBERLEY BERLIN"** → teslim formu KIMBERLEY→KIM **kısaltılmış/bozulmuş**.
   - Provenance: `_log.jsonl` → `pdf_completed cast=7` → `v4_finalize_completed (148s)` sonrası cast=8 + yapımcı eklendi = **KB/v4-finalize (KB_CAST_ADD=1) ekledi, OCR okumadı**.
   - Hüküm: kişi GERÇEK (boş-doldur meşru) ama ad-formu ekran-otoritesiyle çelişiyor; okunan-yazım olmadığından form tamamen KB'den → gerçek form-bozulması. Felaket değil; ama **KONTROL atlanıp sessizce ONAYLI**.

2. **[MEDIUM] Yüzey-dosyalar arası özet + isim tutarsızlığı** (eksen 9)
   - İsim: PDF + üst `.txt` "RACHELLE **LEFEVRE**" ↔ `_teknik.txt` + `kunye_teslim.md` "RACHELLE **LEFEBVRE**". OCR HAM ground-truth = **LEFEBVRE** (ocr_raw_all 22×) → PDF+.txt'teki LEFEVRE = **web/KB normalizasyonu OCR'ı eziyor** (OCR-otorite endişesi).
   - Özet: root `.txt` tam varyant (okul yıllığı cümlesi) ↔ PDF kısa varyant. Aynı koşuda iki serileştirici tutarsız yazıyor (8 oyuncu+3 yapımcı vs 7+2). QC yakalamadı → ONAYLI.

---

## C) BİRİKMİŞ SİSTEMİK BULGULAR

### ✅ Çok-film teyitli (ilk 4 oturum-filmi)
1. **METADATA/DENETİM-DEFTERİ GÜVENİLMEZ** (geniş tema):
   - `karar` ↔ `route.folder` ÇELİŞKİSİ (4 film: RED ROCK, SIRILSIKLAM, YAĞMUR, KLEPTOMAN). `route.folder` çoğu kayıtta "ONAYLI" sabit kalıyor karar=Kontrol olsa bile. **KLEPTOMAN ile kesinleşti: fiziksel yönlendirmeyi `karar`+`teslim` belirliyor (KONTROL'e doğru gitti), `route.folder` sadece bozuk gösterge → KOZMETİK metadata bug'ı, GERÇEK yanlış-yönlendirme DEĞİL.** Yine de denetim-defterini kirletir.
   - `_DURUM.neden` BAYAT-ŞABLON: ÖLDÜREN POZ'da neden="web title+year kilidi" yazıyor ama gerçekte kilit OLMADI (imdb/wiki boş, cast OCR'dan); gerçek sebep afişti. **İnsan denetçiyi yanlış yönlendirir** — KONTROL'deki kişi neyi düzelteceğini yanlış öğrenir.
   - → kod denetimi A6 (router `_sig` substring kırılgan) ile örtüşür.
2. **YÜZEY SIDECAR BAYATLIĞI** (3/4): final PDF doğru/zengin ama `.txt` BLOK3 / `_teknik.txt` / `kunye_teslim.md` v4-öncesi bayat değer taşıyor — hatta **YANLIŞ yönetmen**: YAĞMUR .txt BLOK3 yön=SCOTT COOPER (PDF=WILSON), RED ROCK .txt BLOK3 yön=PEDRO DAMIAN (PDF=GYLLENHAAL). v4/PDF render güncelliyor, sidecar'lar güncellenmiyor. **Risk: sidecar .txt kullanan downstream yanlış veri alır.**
3. **KB-eklenen isimler OCR-dışı + form-şüpheli** (KIM BERLIN/HAYATIN, PAUL FREEMAN/RED ROCK, ROBERT SIMONDS/SIRILSIKLAM). Kişiler çoğu gerçek (boş-doldur meşru) ama OCR-teyitsiz; form bozulabiliyor (KIMBERLEY→KIM).
4. **Tüm giriş master'ları footage-bloat** — ama çıktıya zarar yok (yukarıda).

### 🔴 Tekil ama ciddi
- **HABABAM SINIFI UYANIYOR: EN BOZUK ONAYLI (Türk klasiği "kusursuz" damgalı)** [CRITICAL] — ünlü başroller (Halit Akçatepe/Şener Şen/Şevket Altuğ/Sezerel/Gürses) açılış jeneriğinde EKRANDA var (master kanıt) ama **OCR açılış yıldız-kartlarını HİÇ okumamış**, yalnız kapanış yardımcı-kadro scroll'unu almış → başroller PDF'te YOK. + OCR ezme Halit→Sıtkı Akçatepe + yapımcı NAHIT ATAMAN uydurma + Türkçe film KU sanıldı→TMDB yanlış-film özeti + orijinal-ad Kürtçe garble. **5+ kusur birleşip "kusursuz/ONAYLI" damgalandı** = ONAYLI false-negative'in en ağırı.
- **AYI YOGİ: GARBLE teslim kadrosuna girdi + QC garble-gate KÖR** [HIGH×2] — (a) **stitch/seçim katmanı temiz OCR'ı atıp garble'ı seçiyor**: JAMES DARREN 7× temiz okundu ama final "DAMES DARREN" (1× garble); JULIE BENNETT 7×→"JEJULIEA BENNETT"; çöp "JJAME SBENREET" cast'e sızdı. Yeni kök-neden: frekans-tabanlı seçim ters/bozuk. (b) **`garble_frac=0.0` Latin-garble KÖR NOKTASI** — 3 bariz Latin-garble varken QC temiz raporlayıp onayladı (memory'deki "garble-gate Latin-çöpü görmüyor" — İLK CANLI TEYİT). İlk kez garble TESLİM kadrosuna ulaştı (önceki filmlerde sadece sidecar'daydı).
- **BEKARLIK SULTANLIKTIR: UYDURMA YAPIMCI (NORMAN LEAR/BUD YORKIN)** [CRITICAL, KOD-KONUMU TEYİTLİ] — OCR BOŞ (credit-detect footage'ı jenerik sandı→0 satır) iken KB yanlış-film yapımcısını enjekte etti (Amerikan sitcom, İtalyan filmle alakasız). **Kök: `tek_film_kunye.py:563-564` — OCR yapımcı boşsa KB-değeri KİMLİK-KAPISI OLMADAN basılıyor** (yorum bunu bilerek yapıyor). H2'nin (yanlış-film kilidi) yapımcı-alanı versiyonu, kesin satırla. **En yüksek-öncelikli + en kesin fix.** Ayrıca özel-tür kapısı KONTROL'ü ezip filmi muzikal klasörüne yolladı (3. hedef yönlendirme).
- **MANASLU: UYDURMA OYUNCU "HANS EBNER"** [CRITICAL] — teslim PDF kadrosunda OCR/ASR/KB hiçbirinde olmayan hayalet 4. oyuncu; gemma4 VL-fallback üretmiş (`cast_supplement=4`, credit_validate'te kare-içi notu YOK — diğer 3'te var). **Kök neden:** anti-halüsinasyon kalkanı `_in_raw` token-seviyesinde → OCR'daki "**Hans**-Peter Stauber" + "Hannelore **Ebner**" token'larından Frankenstein-isim kuruluyor, kalkan **adjacency (bitişik ad-soyad) kontrol etmediği** için geçiyor. (memory: [[feedback_dogrulanmamis_iddia_yasak]] token-eşleşme yanlış-pozitifi). KONTROL'de olduğu için müşteriye gitmez ama düzeltilmeden ONAYLI'ya geçmemeli.
- **YAĞMUR: başrol SCOTT COOPER kaybı** [HIGH] — credit_validate yanlış-okunan yönetmeni düzeltince, yanlış yere konmuş ismi cast'e GERİ EKLEMİYOR → gerçek başrol kalıcı kayıp. **Yeni hata kalıbı**; başka filmlerde "yön düzeltildi ama eski yön cast'te yok" diye izlenecek.
- **HAYATIN: şüpheli ONAYLI** — KB-form-bozuk yapımcı + OCR-ezme olmasına rağmen "kusursuz/ONAYLI" (QC yakalamadı).

### ✅ İyi çalışan (teyit)
- **Özel-tür yönlendirme** (MANASLU): ORF dağcılık belgeseli doğru tespit → `muzikal_animasyon_belgesel/_KIMLIK_CAST`, silinmedi. karar↔route çelişkisi YOK.
- **OCR-otorite kalkanı çoğu sızıntıyı kesiyor**: "TATT TET" garble, rol-etiketi, disclaimer PDF'e GİRMİYOR; `tr_upper` İ-bozması görülmedi (GRUBER korundu).
- **KB-fill emniyeti (fail-safe doğru):** Kimlik KİLİTLENEMEYİNCE KB doldurmuyor → uydurma yapmadan KONTROL'e gidiyor (HAYALPEREST: 1 cast, poster isimleri sızmadı). KB-fill RİSKİ yalnız **"zayıf-kilit" bölgesinde** (GEÇMİŞİN GÖLGELERİ: yön OCR-okundu ama web-doğrulanmadı → KB 5 cast ekledi). Yani tehlike "kilitlenemedi" değil, "zayıf kilitlendi" durumu.

### ⚠️ DÜZELTME (tarafsız Opus inceleme — [FINAL_RAPOR.md](outputs/RUN_WATCH_20260622/FINAL_RAPOR.md))
Bu tablodaki "Hazır→ONAYLI" etiketlerinin bir kısmı **bayat `" 2"` duplikat klasörden** okundu; **canlı koşu (`-1` klasörü) o filmleri AutoFix'e** yolladı (KEDİ GÖZÜ/BÜLBÜL/MAYMUN AKLI/DELİ KAN). Yani "7/8 ONAYLI kusurlu" **şişik** — kusurlar GERÇEK ama QC çoğunu **AutoFix'e bayraklamış** (sessiz-ONAYLI değil). Gerçek kör nokta **AutoFix kovası**. HABABAM gerçekten ONAYLI (vaka geçerli). Ayrıntı + kanıt FINAL_RAPOR §1/§3.

### 🚨 HEADLINE (ham gözlem): ONAYLI/AutoFix kapısı kusur taşıyor
- **HAYATIN** (ONAYLI): KB-form-bozuk yapımcı KIM(BERLEY) BERLIN + LEFEBVRE→LEFEVRE ezme.
- **DÖRT CENAZE** (ONAYLI): Christopher Walken + Lee Evans başrolleri kadrodan düşmüş + JOSH→JOSHUA ezme.
- **KULÜP EVİ** (ONAYLI): JAIMEE LEE WYSON→JAIMEE WYSON + DELANY→DELANEY isim-ezme.
- **KOMİSER CORDIER** (ONAYLI): senarist "Scénario/MARC-ANTOINE LAURENT" oyuncuya sızmış (Fransız crew).
- **GEÇMİŞİN GÖLGELERİ** (ONAYLI): kadronun 5/8'i KB-türetilmiş (OCR sadece 3), yön doğrulanamadı — borderline (factual doğru ama OCR-otorite zayıf, H2-komşusu).
- **KARAYİP KORSANLARI 2** (ONAYLI): kadro/yön TEMİZ ama **PDF afişi YANLIŞ film** (Pirates 3 posteri) — kusur içerikte değil teslim-afişinde.
- **ŞİRKET ADAMLARI** (ONAYLI): kadro/yön/özet temiz ama **yapımcı alanı "SPECIAL THANKS" sızıntısı** + orijinal-ad ezme (MEN→MAN).
- **İNTİKAM ÇOCUKLARI** (ONAYLI): ✅ **gerçekten TEMİZ** — içerik OCR-sadık, tek kusur kozmetik master-bloat (teslime etkisiz). ONAYLI'nın temiz de olabildiğinin kanıtı.
- **Sonuç:** "Hazır/ONAYLI" damgası temizlik garantisi DEĞİL — **7/8 ONAYLI film** en az 1 QC-kaçırdığı kusur taşıyor (5 net içerik + 1 borderline + 1 yanlış-afiş), 1'i (İNTİKAM) temiz. ONAYLI **mutlak kusurlu değil** ama risk yüksek → **insan-denetimi ŞART** (Kontrol zaten insana gidiyor; asıl kör nokta ONAYLI'da). Ortak sebep: kusurlar "kozmetik/IMDb-doğru/factual-doğru" göründüğü için QC kapısından geçiyor.

### Çok-film teyitli yeni kalıplar
5. **GERÇEK BAŞROL/YILDIZ KADRODAN DÜŞÜYOR — EN BASKIN RECALL SORUNU** (~10 film, 5 mekanizma, aynı semptom; mekanizmalar: ①validate-yön-düzeltince-cast'e-geri-eklemiyor ②8-cap appearance-order ③footage-bloat-OCR-kaçırma ④açılış-yıldız-kartları-okunmuyor ⑤blok-segmentasyon-8-altı-kayıp ⑥**tek-blok seçimi** (açılış VEYA kapanış bloğundan biri seçilip diğeri yok sayılıyor: HABABAM açılış kaçtı/kapanış alındı; FEDORA açılış alındı/kapanış-tablosu yok sayıldı→Holden/Fonda düştü)). Örnekler:
   - YAĞMUR: credit_validate yanlış-okunan yönetmeni düzeltip eski ismi cast'e geri eklemiyor → SCOTT COOPER kayıp.
   - DÖRT CENAZE: 8-cap **appearance-order** ile kırpıyor → top-billed CHRISTOPHER WALKEN/LEE EVANS düşüyor (H5 canlı teyit; billing-prominence yerine ortaya-çıkış sırası).
   - SIRDAŞ: Thierry Lhermitte (afiş 4.billing) cast'ten düştü.
   - POTA: EGEMEN ALMACI (OCR 38×, afiş 4.) extraction/merge'de sessizce düştü (9→8).
   - Ortak: OCR'da net okunan başrol-seviyesi oyuncu yüzeye gelmiyor. **En somut izleyici-görünür recall kaybı.**
   - **KARŞIT (recovery VAR ama tutarsız):** ZORLU ADAM'da credit_validate'te geçici düşen RUDY BOND + 2 yapımcıyı v4 OCR'dan GERİ KAZANDI. Yani v4'te recovery mantığı var ama tutarsız çalışıyor (bazı filmde kurtarıyor, bazısında düşürüyor) — düzeltme bu mantığı tutarlı kılmaya odaklanmalı.

9. **🔴 TÜRKÇE FİLM KÜRTÇE (KU) SANILIYOR → CASCADE (yeni kök-neden, TR-kritik)** : HABABAM SINIFI — `mms-lid-1024` Türkçe diyaloğu **ku (conf 0.836)** etiketledi → ASR atlandı (`asr_skipped_kurtce`) → TMDB'den **yanlış-film özeti** ("köylü öğrenci Ahmet"≠Hababam) + orijinal-ad **Kürtçe garble** ("Hışyar Dibe"). Türk klasiği bile etkilendiyse **birçok Türk filmini etkileyebilir** (LID güvenilmez). H3 ailesinin yukarı-akış kökü. ÇOK-FİLMDE İZLE — TR arşivi için potansiyel yaygın.
10. **🔴 AÇILIŞ YILDIZ-KARTLARI OCR'da kaçıyor → başroller komple kayıp** (S1_FRAME_COVERAGE giriş): HABABAM — başroller açılış kartlarında EKRANDA ama OCR yalnız kapanış scroll'unu okudu → en önemli kadro (yıldızlar) PDF'te yok. footage-bloat'tan farklı: burada açılış kartları net ama OCR-pencere/seçim onları almıyor.
8. **🔴 OCR-OTORİTE İHLALİ: OCR-dışı isim teslim kadrosuna giriyor (KB/VL) — 4 film, kurucu kanun** : KB/VL-enrichment OCR'da OLMAYAN ismi cast/yapımcıya yazıyor, bazen OCR-OKUNAN ismi DÜŞÜREREK:
   - BEKARLIK: OCR boş → KB yanlış-film yapımcısı (Norman Lear) fabrike (`tek_film_kunye.py:563-564`).
   - BÜLBÜLÜ: dolu OCR'a Gregory Peck eklendi (OCR'da 0×).
   - **KEDİ GÖZÜ: başrol Parker (OCR 6×) DÜŞTÜ + Sarrazin (OCR 0×) EKLENDİ = İKAME** (en ağır, ONAYLI'ya gitti). **TAM KOD-TRACE forensiği yapıldı** → [FILM31_KEDIGOZU_FORENSIK.md](outputs/RUN_WATCH_20260622/FILM31_KEDIGOZU_FORENSIK.md) + memory: 4-katman zincir — `20260601_clean.py:61` (tek-token yıldız kartları frag→atılır, başrol kökü), `credit_qc_block.py:562-572` (floor-fill 8'de durup Parker'a ulaşmıyor), `:581-593` (yapımcı dedup çok-katı, HAZELTON↔HAZLETON birleşmez), `credit_severity_router.py:91-117`+`tek_film_kunye.py:725-730` (ihlal kanıtı route'a taşınmıyor→AutoFix).
   - MANASLU: VL Hans Ebner fabrike (token-kalkan gediği).
   - İmza: OCR-otorite ("okunan kanun") çiğneniyor; kişi gerçek olsa bile OCR-teyitsiz ekleme/ikame. **En kritik kalite bulgusu** — kurucu kanunu ihlal ediyor ve QC yakalamayıp ONAYLI veriyor.
7. **🇹🇷 TÜRKÇE DUBLAJ KADROSU (SESLENDİRENLER) DÜŞÜRÜLÜYOR — TRT-kritik** (BÜLBÜLÜ ÖLDÜRMEK): OCR "seslendirenler" bloğunu tertemiz okuyor (19 Türkçe ses oyuncusu, garble=0) ama 8-cap orijinal-dil kadroyu tutup **Türkçe dublaj kadrosunu komple atıyor** + dublaj-ekibi (ses kayıt/çeviri/seslendirme yönetmeni) düşüyor. **TRT arşivi ağırlıkla dublajlı → bu, en alakalı kadronun sistematik kaybı olabilir.** Çok-filmde izlenecek; potansiyel en yüksek TRT-değerli kapsam-açığı (H5'in TR-dublaj versiyonu).
6. **v4/render OCR-FORMUNU EZİYOR (isim+başlık IMDb/KB-formuna normalize) — EN GÜÇLÜ KALIP** (8 vaka / 6 film): LEFEBVRE→LEFEVRE, JOSH→JOSHUA, KIMBERLEY→KIM, JAIMEE **LEE** WYSON→JAIMEE WYSON, DELANY→DELANEY, Sangster→**Brodie**-Sangster, **Steven**→Stephen Moyer, **+ orijinal başlık: COMPANY MEN→COMPANY MAN** (ŞİRKET ADAMLARI) **+ TAM FABRİKASYON: "ROBO MAN..." (ÇELİK MASKE, OCR'da 0×, gerçek "The Man in the Steel Mask")**. Yani yalnız kişi-isimleri değil **orijinal-ad da** eziliyor/uyduruluyor. Ortak imza: **credit_validate / iç .txt doğru OCR-formu koruyor, ama nihai v4 render IMDb/web-formuna ezip PDF'e yazıyor** → OCR-otorite ihlali yalnız teslim PDF'inde + yüzeyler-arası tutarsızlık. ONAYLI kusurlarının ana kaynağı bu.

### ✅ Çok-film teyitli: crew/thanks→cast sızması (5 film — FELAKET olabilir)
- **SESSİZ ÇOCUK (kısa film) — EN AĞIR:** cast alanına **6 yapımcı/exec-producer** sızdı + **7 gerçek oyuncu düştü** (Rachel Shenton, Maisie Sly...) = neredeyse tam tersine çevirme. Extractor "PRODUCED BY" bloğunu cast sandı, gerçek CAST bloğunu attı → blok-tanıma çökmesi.
- **OLAY YERİ (Almanca):** "Redaktion" altındaki THOMAS MARTIN + MELANIE WOLBER başrol cast'e sızdı (#1-#2).
- **KOMİSER CORDIER (Fransızca):** "Scénario" senaristi MARC-ANTOINE LAURENT oyuncuya sızdı.
- **SIRDAŞ (yabancı):** "Dialogue Coach" Dagmar Schwarz oyuncuya sızdı. (+ "Assistant to Georges Campana" → yapımcıya yükseltildi.)
- **ŞİRKET ADAMLARI (İngilizce):** "SPECIAL THANKS" bloğundaki 8 isim **yapımcı alanına** sızdı (gerçek yapımcı OCR'da yok).
- **KÖPRÜNÜN ÖTESİ:** filmin KÖPEĞİ "DOLORES" ("trained by" hayvan kredisi) **oyuncu** olarak listelendi + 5 gerçek oyuncu düştü. (insan-olmayan/hayvan kredisi → cast = sınıf-hatası varyantı)
- **DELİ KAN:** funk grubu WAR'ın üyeleri (5 isim) "music written & performed by WAR" bloğundan OYUNCULAR'a (müzik-performers→cast). + **KÖPRÜNÜN ÖTESİ:** köpek "Dolores" oyuncu.
- **Kalıp (7 film, GENİŞ aile):** her tür non-cast kredi cast/yapımcıya sızabiliyor — crew (DE "Redaktion", FR "Scénario", "Dialogue Coach"), teşekkür ("SPECIAL THANKS"), asistan ("Assistant to"), **müzisyen** ("performed by WAR"), **hayvan** ("trained by") → cast. credit_validate "kare-içi normalize" yolundan geçmeyen isimleri sınıf-denetiminden geçirmiyor. Kök: `_CREW_CONTEXT_KW` çok-dilli/eksik. **İngilizce dahil her filmde risk** (özellikle özel-blok etiketleri). ONAYLI'ya da geçiyor (KOMİSER CORDIER, ŞİRKET ADAMLARI).

### Kod denetimiyle bağ
- **A7/S1_FRAME_KAPSAM (footage üstü diegetik kredi kaybı) — CANLI TEYİT** (OLAY YERİ: başroller master'da var, OCR'da yok). Footage-bloat = bu kaybın görsel işareti.
- **H5 (8-cap kayıp) — CANLI TEYİT** (DÖRT CENAZE: Walken/Evans).
- **H1 (Latin-dışı silme) — CANLI TEYİT** 🔴 (NAMUS DÜŞMANI, Arap-yazısı): OCR mükemmel okudu (garble=0) ama extractor parse edemeyince 12 oyuncu+yön komple düştü. Doğru KONTROL'e gitti (fail-safe), ama Arap/Fars/Kiril/Yunan-yazılı TÜM arşiv filmlerinde aynı %100 kadro kaybı bekleniyor. + yan: `_DURUM.neden`="garble okunamadı" kök-nedeni gizliyor (gerçek: extractor Latin-dışı desteklemiyor) → insan-denetçiyi yanlış yönlendirir.
- H2 (yanlış-film kilidi), H3 (özet-Kürtçe) henüz net tetiklenmedi (GEÇMİŞİN GÖLGELERİ H2-komşusuydu). H4 (25fps) birkaç filmde hafif iz, zarar yok.

### İzlenecek yeni adaylar (henüz tek-örnek)
- **Poster YANLIŞ FİLM/sürüm (2 tip, ONAYLI'da görünür teslim hatası):** ① yanlış-installment: KARAYİP2 → Pirates 3 "At World's End" posteri (franchise doğru, sürüm yanlış). ② **yanlış-film-aynı-başlık (daha ciddi):** ÇOCUKLARIN SAVAŞI (İspanyol çocuk müzikali) → aynı İng. başlıklı "The Children's War" Acholi çocuk-asker BELGESELİ posteri. Kök: poster_fetch İngilizce-başlıkla eşleşiyor, OCR-kadro/yön ile DOĞRULAMIYOR (H2 afiş yolu). memory afiş-versiyon işiyle bağ.
- **Çıkış master üretilmemesi (tespit var, PNG yok) — 2 film:** KARAYİP2 (kapanış scroll conf 0.96) + PRESTİJ (cikis.png + manifest yok). db_compose_master defekti (footage-bloat'tan ayrı). Master OCR'a beslenmediği için teslime etki yok ama master arşivi eksik.
- **8-cap yıldız-düşürme KOŞULLU:** KARAYİP2'de düşürmedi (ana-8=başroller) ama DÖRT CENAZE'de düşürdü (appearance-order, ilk-sıra çocuk oyuncular). Risk: >8 kadro VE billing-sırası yıldız-önce değilse.
- **TÜR sınıflandırıcı GÜRÜLTÜLÜ → özel-tür yönlendirmesi tutarsız:** MARY POPPINS (gerçek müzikal) "KOMEDİ/AİLE" etiketlendi→KONTROL'e gitti; BEKARLIK (İtalyan komedi) "MÜZİKAL" etiketlenip muzikal-klasöre gitti. Yanlış-sınıf hem özel-tür yönlendirmesini bozuyor hem PDF tür alanını yanlış yazıyor (+ clip.json provenance çelişkisi yaygın).
- **Yinelenen klasör " 2" (aynı TRT yeniden işlenince) — 4 film:** BEKARLIK + BÜLBÜLÜ + KEDİ GÖZÜ + BABAMIN SİNEMASI — eski Database'de mevcut TRT bu koşuda " 2" klasörü oluşturuyor. Eski+yeni export PDF birlikte kalabilir (hangisi kanonik karışıklığı). İZLE.
- **GÖMÜLÜ film-içi-film kadrosu sızması (yeni):** BABAMIN SİNEMASI — film içindeki başka filmin ("Aux Yeux du Souvenir") oyuncuları (Morgan/Marais) asıl kadroya #1-#2 sızdı. ÖNEMLİ ASİMETRİ: **yönetmen tarafı çelişki-çapasıyla korunuyor** (XML ile Delannoy reddedildi→Berri) ama **cast tarafında o koruma YOK** → embedded/wrong-context isim cast'e geçiyor. Aynı asimetri lost-actor'da da var (yön düzeltilir, cast handling zayıf).
- **✅ KIMLIK FALSE-POSITIVE → gereksiz KONTROL (3 film, ÇOK-FİLM TEYİTLİ):** Temiz/doğru filmler "cast kesişimi 0" alarmıyla gereksiz KONTROL'e düşüyor: KÖŞENİN KRALI (klip'te XML-cast yok) + BEKLENEN BOMBA (garble OCR yazımı↔XML exact-eşleşmiyor, oysa yön IMDb+XML+Wiki DOĞRULANDI) + ANGOLA'DAN KAÇIŞ (yabancı film, TRT-XML'de yabancı kadro yok→kesişim 0). **Yaygın kalıp: yabancı/garble-cast film → cast-kesişim 0 → gereksiz karantina.** **QC kapısı İKİ yönde de yanlış-ayarlı:** ONAYLI'ya kusur sızdırıyor (false-negative) AMA temiz filmleri de gereksiz karantinaya atıyor (false-positive). Fix: cast-kesişim kapısını yön-DOĞRULANDI + fuzzy-eşleşme ile gevşet. Muhafazakâr-güvenli ama throughput/recall kaybı.
- **İsim-işleme TUTARSIZ:** Sistem net isimleri AŞIRI-normalize ediyor (ezme: JOSH→JOSHUA) ama garble isimleri DÜZELTMİYOR (KÖŞENİN KRALI: "ANTHONV MACTROMAURO"→Anthony Mastromauro yapılmadı). v4-render isim-normalizasyonu eşitsiz uygulanıyor.
- **Not (529):** Film #10-11 denetçi ajanı API-529'a takıldı; sentez ajanı artefaktları kendi okuyup toparladı → degrade ama kullanılır. İkisi de temiz çıktı; degrade-denetim kabul edildi. Kuşkulu film 529 yerse yeniden çalıştırılacak.
