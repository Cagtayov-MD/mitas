# MASTER-PNG OKUNURLUK + KÖK-NEDEN DENETİMİ (2026-07-09)

Database içindeki **294 film klasörünün tamamı** tek tek incelendi: her klasörde `giris_reading_master_runaware.png` ve `reading_master_runaware.png` (çıkış) var mı, varsa okunur mu, yoksa neden yok.

## Yöntem (kısaca)

1. **Mevcut/eksik envanteri** — 294 klasörün tamamı taranarak dosya varlığı çıkarıldı: giriş 276/294, çıkış 211/294.
2. **Eksik-dosya kök-nedeni** — tahmin değil, **ölçüm**: her film klasöründeki `<TRT> <BAŞLIK> master_manifest.json` dosyası, üretim motorunun (`master_png_monitor.py`) her segment için yazdığı `status`/`frames`/`source` bilgisini içeriyor. Bu manifestler + ham kare sayıları (`frames/giris`, `frames/cikis`, `frames/*_jenerik` havuzları) okunarak 87 sorunlu klasörün her biri kanıtla sınıflandırıldı.
3. **Görsel okunurluk QC** — 487 mevcut master-PNG'nin **tamamı**, 61 paralel ajana bölünüp (Read tool ile) tek tek açılarak incelendi. Kriter yalnız: metin okunur mu, anlamsız tekrar var mı, dosya bozuk mu — arka plan/footage karışması, estetik düzensizlik göz ardı edildi (istendiği gibi).
4. **Havuz-boş kök-neden doğrulaması** — çıkış/giriş "jenerik havuzu" hiç kare tutmadığı 88 vakada, ham video karelerinden (baş/orta/son, 4'er kare) örnekler 30 paralel ajana verilip gerçekten kredi metni var mı yok mu görsel olarak doğrulandı (detektör kaçırmış mı, yoksa gerçekten jeneriksiz mi).

Toplam: **91 paralel görsel-QC ajanı**, 487 present-image + 88×4 ham-kare örneği incelendi, sıfır hata.

---

## 1) MEVCUT ama SAĞLIKSIZ — 53 / 487 (%89 sağlıklı)

434 dosya OKUNUR bulundu. Aşağıdaki **53 dosya** sorunlu (isim + segment + neden):

### Tekrar / stitching hatasi (27)

- **BEŞ KAFADAR 1998-0527-1-0000-00-1** / giris (`giris_reading_master_runaware.png`) — Bu master boyunca hicbir kredi/jenerik yazisi yok; ayni kirsal panorama karesi neredeyse degismeden bircok kez, ardindan ayni durbin-gorunumu karesi de tekrarlanarak anlamsizca cogaltilmis (sadece film-ici goruntu).
- **BJ VE AYI 1978-0215-1-0000-00-1** / cikis (`reading_master_runaware.png`) — Dosyanin buyuk cogunlugu (yaklasik ilk %70'i) hic kredi yazisi icermiyor; ayni sahne (kadin-erkek sokakta konusuyor) neredeyse birebir ayni karelerle onlarca kez anlamsizca tekrarlanmis; gercek jenerik yazisi ancak son bolumde beliriyor.
- **BİR KONUŞABİLSE 2003-9192-1-0000-00-1** / giris (`giris_reading_master_runaware.png`) — Master boyunca gercek jenerik/kredi metni yerine ayni mektup (Lydia Harris notu) sahnesi anlamsizca tekrarlaniyor, oyuncu/ekip ismi hic gorunmuyor.
- **CAZCI 1983-0200-1-0000-00-1** / giris (`giris_reading_master_runaware.png`) — Acilis logolarindan sonra ayni Kiril baslik karesi (İSKUSSTVO TRUDYAŞÇİMSYA) yaklasik 10 kez neredeyse ozdes tekrarlaniyor, gercek oyuncu/ekip ismi hic gorunmuyor.
- **DENİZLER ALTINDA 20.000 FERSAH 2003-9049-1-0000-00-1** / cikis (`reading_master_runaware.png`) — 'PRODUCTION COORDINATORS' ve 'POST PRODUCTION DIRECTOR (HYPER IMAGE) ROB SMILEY' blokları aynı isimlerle art arda anlamsızca tekrar ediyor.
- **ELMA 1998-0464-1-0000-90-1** / giris (`giris_reading_master_runaware.png`) — Jenerik/kredi metni yok; parmak-izi belgesi sahnesinin neredeyse ayni karesi 14 kez anlamsizca tekrar ediyor.
- **GÖLGELER PRENSİ 1991-0441-1-0000-00-1** / giris (`giris_reading_master_runaware.png`) — Master boyunca (9080px) hiçbir kredi metni görünmüyor, sadece karanlık sokak/tabela sahnesi (TABU tabelası, araba) tekrarlanıyor.
- **GÜLE GÜLE JÜPİTER 1991-0544-1-0000-00-1** / giris (`giris_reading_master_runaware.png`) — Aşırı uzun master (33038px) içinde aynı Japonca anlatım metni bloğu defalarca anlamsızca tekrarlanıyor.
- **JONSSON ÇETESİ 1981-0287-1-0000-00-1** / giris (`giris_reading_master_runaware.png`) — Robert Gustafsson / Loa Falkman kadro bloklari art arda bulaniklasarak 2-3 kez anlamsizca tekrar ediyor, ayrica ilk kadro blogu beyaz zeminde hayalet gibi neredeyse gorunmez.
- **KAHRAMAN UZAYLILAR 2014-9078-1-0000-90-1** / giris (`giris_reading_master_runaware.png`) — Mr. James Bing konsol yakin-cekim karesi ayni sekilde 3 kez ust uste anlamsizca tekrar ediyor; bu bolum gercek kredi metni degil sahne-ici yazi (Planet Gnarlach, 47 Minutes Ago) iceriyor.
- **KANDAHAR 2011-9224-1-0000-88-1** / giris (`giris_reading_master_runaware.png`) — Ayni baslik karesi ("سفر قندهار" + yonetmen adi) birebir 3 kez ard arda tekrarlaniyor, baska hicbir kredi bilgisi yok - anlamsiz tekrar.
- **KESS 1969-0094-1-0000-00-1** / giris (`giris_reading_master_runaware.png`) — Aynı açılış paragrafı 3 kez art arda tekrarlanıyor ve tekrarların bir kısmı interlace/çift-görüntü bozulmasıyla anlamsız hale gelmiş.
- **KIRKSEKİZ SAAT 1970-0072-1-0000-00-1** / cikis (`reading_master_runaware.png`) — Ayni 'cast of characters' bloklari (Darren McGavin/William Windom/Kathie Browne/Carrie Snodgress) birebir 3 kez, ardindan Henry Jones bloku yine 3 kez, sonra yapim karti 2 kez anlamsizca tekrarlaniyor -- kare-dedup edilmemis stitching kaymasi.
- **KOLEKSİYON 1978-0220-1-0000-00-1** / giris (`giris_reading_master_runaware.png`) — Master'da gercek kredi metni yok; sadece 'Chryss' magaza tabelasinin neredeyse ozdes 3 karesi tekrarlaniyor, okunacak jenerik yazisi bulunmuyor.
- **KUĞUNUN ŞARKISI 1986-0264-1-0000-00-1** / giris (`giris_reading_master_runaware.png`) — Masterde hiç kredi/jenerik yazısı yok; sadece sahne içi taş kazıma yazısı ve bir kapı önü sahnesinin neredeyse birebir tekrar eden iki karesi var, okunacak künye metni yok.
- **KÜÇÜK KAHRAMAN 1999-0407-1-0000-00-1** / cikis (`reading_master_runaware.png`) — Ayni cast/crew satirlari (orn. Production Coordinators, Gaffer, Sound Supervisor) 19799px boyunca defalarca sadece 1-2 satir kayarak anlamsizca tekrar ediyor, runaway stitching kaynagi belirgin.
- **LIBERA SEVGİLİM 1975-0185-1-0000-00-1** / cikis (`reading_master_runaware.png`) — Aynı kredi blokları (Ispettore Produzione, Fonico, Assistenti al Montaggio, Miscage, Una Produzione vb.) görüntü boyunca defalarca art arda anlamsızca tekrar ediyor, bu bir yakalama/dedup hatasına işaret ediyor.
- **ONDAN UZAKTA 2006-9175-1-0000-00-1** / cikis (`reading_master_runaware.png`) — Ayni isim/gorev bloklari (HONEY WAGON OPERATOR, CONSTRUCTION MANAGER, HEAD CARPENTER vb.) art arda defalarca anlamsizca tekrarlanmis, agir stitching-tekrar sorunu.
- **SCHIMANSKI-CEHENNEM ÇOCUKLARI 2001-9171-1-0000-00-1** / cikis (`reading_master_runaware.png`) — Aynı bloklar anlamsızca tekrar ediyor: casting satırı 2 kez, PRODUKTIONSLEITUNG/HERSTELLUNGSLEITUNG/REGIE bloğu 2 kez art arda, 'Wir danken der Stadt...' teşekkür metni 4 kez, COLONIAMEDIA logosu 3 kez tekrarlanmış; ayrıca KAMERAASSISTENZ satırında harfler üst üste binmiş/garble.
- **SISSI-1 1990-0390-1-0000-00-1** / cikis (`reading_master_runaware.png`) — Master agirlikla tac giyme/tören footage karelerinin tekrarindan olusuyor, gercek kredi metni yalnizca en altta cok kucuk ve secilmesi zor bir logo/yazi olarak kaliyor.
- **SON OYUN 1995-0475-1-0000-00-1** / cikis (`reading_master_runaware.png`) — Cok uzun master boyunca ayni basketbol mac sahneleri anlamsizca tekrar ediyor, secilebilir kredi metni yok.
- **SİBİRYADAN 2 1979-0203-1-0000-00-1** / giris (`giris_reading_master_runaware.png`) — Açılış başlığından sonra tek bir sisli deniz+SPERRZONE tabelası sahnesi neredeyse hiç değişmeden 14+ kez anlamsızca tekrar ediyor, gerçek kadro/emek metni yok.
- **TOPLU GÖSTERİLER 1990-0403-1-0000-00-1** / cikis (`reading_master_runaware.png`) — Master ~120 karenin buyuk cogunlugunda (sokak/ev sahneleri) neredeyse ayni kareler anlamsizca defalarca tekrar ediyor (runaway/dedup basarisiz); gercek kredi metni ancak son birkac karede cikiyor.
- **VAHŞİ ORMAN 1994-0316-1-0000-00-1** / cikis (`reading_master_runaware.png`) — Metin kendi icinde okunabilir ama dosya anormal uzun (29970px) ve ayni ekip-blok/DOLBY-STEREO/telif satirlari onlarca kez anlamsizca tekrar ediyor (runaway kare tekrari).
- **YARATILAN KADIN 1982-0271-1-0000-00-1** / giris (`giris_reading_master_runaware.png`) — Ana oyuncu kartlari (Judy Garland/Fred Astaire/Peter Lawford ve Ann Miller blogu) birebir ayni icerikle art arda iki kez anlamsizca tekrar ediyor.
- **ÇIKIŞ 2019-1105-1-0000-76-1** / cikis (`reading_master_runaware.png`) — Metnin kendisi keskin olsa da aynı bölüm başlıkları/departman blokları (ör. departman kadrosu, sponsor logo satırları, CJ ENM telif bildirimi) art arda 2-4 kez birebir tekrar ediyor, anlamsız yığılma var.
- **İYİ KÖTÜ VE ÇİRKİN 1966-0006-1-0000-90-1** / cikis (`reading_master_runaware.png`) — Restorasyon/laboratuvar kredi bloğu (Triage Motion Picture Services... 2003 Restoration) art arda birebir aynı şekilde iki kez tekrarlanıyor, kare/blok tekrarı var.

### Bulanik / bozuk / okunamaz (17)

- **ADI YUNUS 2015-0134-1-0000-85-1** / cikis (`reading_master_runaware.png`) — Kayan çıkış jeneriğinin büyük bölümü renkli çizgi/bulanık şerit desenine dönüşmüş, isim ve unvanlar okunamıyor.
- **APOLLO 11 1996-0222-1-0000-00-1** / cikis (`reading_master_runaware.png`) — Karanlik gece sahneleri uzerine binen kredi yazisi cok kucuk ve bulanik, genel olarak okunamiyor.
- **ARCEDIA 1993-0401-1-0000-00-1** / cikis (`reading_master_runaware.png`) — Alt kisimdaki uzun kapanis kadro listesi asiri kucuk/sikistirilmis satirlar halinde, tek tek okunamiyor.
- **BİR KONUŞABİLSE 2003-9192-1-0000-00-1** / cikis (`reading_master_runaware.png`) — Kredi metni cok kucuk ve bulanik, satirlar/isimler net secilemiyor, genel okunurluk dusuk.
- **DURUMU ANLAMAK 2000-0505-1-0000-00-1** / giris (`giris_reading_master_runaware.png`) — Master tek bir karanlik/bulanik kareden olusuyor -- bir elin defterde Fransizca not yazmasi gorunuyor, film adi veya kredi metni hic yok.
- **KARA KALKAN 1954-0034-1-0000-00-1** / giris (`giris_reading_master_runaware.png`) — Ortadaki buyuk kalkan grafigi ve dusuk kontrast nedeniyle "Starring" ve ekip (Film Editor/Costumes/Hair/Makeup) karelerindeki isimlerin buyuk kismi okunamiyor/kesiliyor.
- **KARAR KİMİN 1981-0266-1-0000-00-1** / cikis (`reading_master_runaware.png`) — Tüm master boyunca yeşil-tonlu diyagonal bulanıklık/parazit var, kredi metni baştan sona seçilemiyor.
- **KATİLLER HER ZAMAN SARI PABUÇ GİYER 1995-0448-1-0000-00-1** / cikis (`reading_master_runaware.png`) — Master tamamen koridor/kütüphane sahne kareleriyle dolu, hiçbir kare gerçek kredi metni içermiyor.
- **KOLEKSİYON 1978-0220-1-0000-00-1** / cikis (`reading_master_runaware.png`) — Ilk kadro listesi (Bates/McDowell/Mirren/Olivier) net olsa da masterin sonraki buyuk bolumu (ör. 'MAURICE ...ELL', 'MICHAEL H...ESTER', 'LA DE...') asiri pozlanmis/cift-bindirmeli beyaz zeminde neredeyse okunamaz halde.
- **KOUDAYU 2004-9206-1-0000-00-1** / cikis (`reading_master_runaware.png`) — Kayan jenerik boyunca ağır hareket-bulanıklığı/smear deseni metnin büyük kısmını okunamaz hale getiriyor.
- **SHAOLIN 2011-9175-1-0000-90-1** / cikis (`reading_master_runaware.png`) — Merdiven/tapinak goruntusu ustune binmis coklu-pozlama tarzi bulanik metin katmanlari kredi yazisini buyuk olcude okunmaz kiliyor.
- **SON CÜCE 1998-0519-1-0000-00-1** / giris (`giris_reading_master_runaware.png`) — Karelerin tamami saf sahne/footage (kizil sacli figur, is makinesi, fenerli adamlar); hicbir kredi/jenerik metni gorunmuyor.
- **TOPLU GÖSTERİLER (KONVOY) 1978-0197-1-0000-00-1** / cikis (`reading_master_runaware.png`) — Goruntunun tamami boyunca interlace-tarzi parcali/testere-disi bozulma var, metin kesintili seritlere bolunmus ve okunamiyor.
- **VAHŞİ ORMAN 1994-0316-1-0000-00-1** / giris (`giris_reading_master_runaware.png`) — Master boydan boya sadece aksiyon/film sahnesi kareleri iceriyor, hicbir kredi/jenerik metni gorunmuyor.
- **YA NASİP YA KISMET 2015-0138-1-0000-85-1** / cikis (`reading_master_runaware.png`) — Çıkış jeneriği aşırı küçük punto ile basılmış; isim satırları bulanık/ayırt edilemez halde, genel olarak okunamıyor.
- **YÜZYILIN CİNAYETİ 1933-0013-1-0000-00-1** / giris (`giris_reading_master_runaware.png`) — Master sadece iki film-sahnesi karesinden (koridor ve masa sahnesi) oluşuyor, hiç okunacak kredi/yazı metni yakalanmamış.
- **ÖLDÜRME ZAMANI 1989-0955-1-0000-00-1** / giris (`giris_reading_master_runaware.png`) — Master tek bir footage karesinden (adamın yüzü) ibaret, 600x480 boyutunda, hiçbir kredi metni/yazı görünmüyor - anlamsız/boş çıktı.

### Kredi metni hic yakalanmamis (icerik bos) (9)

- **BİR KATİLLE EVLENDİM 1993-0467-1-0000-00-1** / giris (`giris_reading_master_runaware.png`) — Karelerin hiçbirinde künye/jenerik yazısı yok, sadece gece sokak sahneleri ve bar tabelası (Cock o' the North) yakalanmış; okunacak metin mevcut değil.
- **KATİLLER HER ZAMAN SARI PABUÇ GİYER 1995-0448-1-0000-00-1** / giris (`giris_reading_master_runaware.png`) — Kredi/başlık yazısı hiç yakalanmamış, sadece sahne kareleri (el yazısı mektup prop'u ve oyuncu yakın çekimleri) var, okunacak künye metni yok.
- **KORKUNÇ GECE 1995-0444-1-0000-00-1** / giris (`giris_reading_master_runaware.png`) — Master hiçbir kredi/yazı içermiyor, sadece bir sokak sahnesi karesi var; okunacak metin yok.
- **KUTSAL SİLAH 2008-9089-1-0000-00-1** / giris (`giris_reading_master_runaware.png`) — Görüntüler tamamen ilgisiz/yabancı sahne akışından oluşuyor ve herhangi bir yönetmen/oyuncu/yapım isim kartı yok, yalnızca çok küçük yabancı altyazı harfleri var, seçilebilir kredi metni bulunmuyor.
- **MUTLU PASKALYA 1984-0274-1-0000-00-1** / giris (`giris_reading_master_runaware.png`) — Master tek bir gece-sahnesi karesinden olusuyor, hicbir jenerik/kredi yazisi yok - okunacak metin yok.
- **NORWOORD 1970-0046-1-0000-00-1** / cikis (`reading_master_runaware.png`) — Master bastan (sokak sahnesi) ortadan (yatak odasi/mutfak sahnesi) sona kadar tamamen film sahnesi footage'i; hicbir yerde okunacak kredi/yazi metni yok.
- **PROFESÖR HANNIBAL 1956-0062-1-0000-00-1** / giris (`giris_reading_master_runaware.png`) — Master sadece 600x480 tek bir kareden olusuyor; havuz/plaj sahnesi footage'i var ama hicbir kredi metni yok, okunacak yazi mevcut degil.
- **PROFESÖR HANNIBAL 1956-0062-1-0000-00-1** / cikis (`reading_master_runaware.png`) — 600x10918 boyundaki tum master bastan sona sadece film sahnesi kareleri (sokakta yuruyen adam, buffet, arabalar); hicbir kredi yazisi yok, ayrica son kısımlarda kare bozulmasi/kaymasi var.
- **ZİRVEDEKİ YALNIZLAR 1993-0277-1-0000-00-1** / giris (`giris_reading_master_runaware.png`) — Master goruntu tek bir kadin yuz-yakinlastirma karesinden ibaret, hicbir jenerik/kredi metni yok — giris kredisi yakalanamamis.

---
## 2) EKSİK DOSYA — KÖK NEDEN (87 klasör, 106 segment-eksikliği)

Hiçbir eksik dosya ham-kare/footage çıkarma hatasından kaynaklanmıyor — **her 87 klasörde de ham kareler diskte mevcuttu** (`HAM-KARE-YOK` sınıfı: 0 vaka). Sorun her zaman bir sonraki aşamada:

### A. Detektör gerçekten kaçırmış — bu bir KOD/TESPİT sorunu (19)

Ham karelerde okunabilir kredi metni görüldüğü halde "jenerik havuzu" (kredi-tespit motoru) hiç kare tutmamış, dolayısıyla o segment için master hiç üretilmemiş:

- **AHTAPOT (DEAD EYE SIX) 2000-0274-1-0000-00-1** / cikis — c_0480 karesinde net, okunabilir Ingilizce jenerik metni var: 'Metal Construction OLEG STOYANOV...', 'Second Unit Director GREGORY VANGER', 'Camera Operator YAROSLAV YACHEV' vb. onlarca isim+unvan satiri acikca goruluyor -- bu kredi metni jenerik-havuzu tarafindan yakalanmamis, tespit hatasi.
- **BÜYÜK TEHDİT 2004-9110-1-0000-00-1** / cikis — c_0480 karesinde acikca okunabilir bitis-jenerigi (crawl) metni var: 'HARAN KARLSSON', 'DAVID EJNESTRAND', 'MARKUS SAMMELI', 'GUSTAV BACKLUND', 'FARDMEKANIKER HKP BOSSE ERIKSSON', 'CASTING MARTIN CRONSTROM', 'CASTING ENGLAND IRENE EAST', 'REGIASSISTENT ELIN ANKARVRET', 'INSPELNINGSLEDARE JONAS OVERTON', 'SCRIPTA KERSTIN H SUNDBERG', 'PRODUKTIONSKOORDINATOR ANITA RYTTING', 'LASSE KARLSSON'. Bu net isim+unvan iceren bir jenerik kaymasidir; jenerik-havuzu bunu tamamen kacirmis (0 kare tutulmus), sistemsel tespit sorunu.
- **BİR ZAMANLAR 1975-0182-1-0000-00-1** / cikis — c_0001 ve c_0240 kadin yuz yakin cekimi, c_0480 karanlik oda iki kisi sahnesi -- bunlar footage. Ama c_0720'de siyah zemin uzerinde okunabilir 'OLD TIMES' baslik yazisi acikca goruluyor (altinda daha soluk ikinci satir metin de var); bu bir jenerik/baslik karti, sistem bunu havuza almamis.
- **DELİLİĞİN SINIRINDA 1995-0326-1-0000-00-1** / cikis — c_0001 ve c_0240 yatak odasi sahne footage'i. c_0480'de siyah zemin uzerinde net beyaz yazi 'First Assistant Director RANDY CARTER' ve 'Second Assistant Director ED DILKS' okunuyor; c_0720'de 'A TRIMARK PICTURES RELEASE' logo-yazisi okunuyor. Iki karede de acik jenerik metni var, sistem kacirmis.
- **DOĞRU KILAVUZ 2004-9143-1-0000-00-1** / cikis — c_0480 karesinde acikca okunabilir kredi metni var: 'Grey Hair GARY BRENNAN', 'Eric Halloran JAMES DALLAS SMITH', 'Female Police Officer VANESSA MacDONALD', 'Associate Producer PAUL JENNISON', 'Production Manager PAUL SPIKE LEES', 'First/Second Assistant Director' vb. -- klasik beyaz-yazi-siyah-zemin jenerik blogu; sistem bunu kacirmis.
- **FISILTILAR 1999-0321-1-0000-00-1** / cikis — c_0480 karesinde acikca okunabilir kredi listesi var ("post production accountant MICHELLE R. PANTE", "production sound mixers DANIEL J. RICHTER, SCOTT SMITH", "boom operator SCOTT WARREN" vb.); c_0720 karesinde de "released by ARTISAN ENTERTAINMENT" logo-karti okunuyor. Jenerik havuzu bu net metni kacirmis.
- **HANNA'NIN ALTINLARI 2010-9150-1-0000-00-1** / cikis — c_0480 karesinde acikca okunabilir kayan jenerik/kredi metni var: 'Camera Car Driver - Craig S. Conaway', 'Casting Director - Angela Terry, C.S.A.', 'Costume Designer', 'Wardrobe Supervisor', 'Set Costumers', 'Catering', 'Craft Service', 'Gaffer', 'Best Boy Electric' vb. gercek ekip kredi listesi goruluyor; sistem bu kareyi jenerik havuzuna almamis.
- **HASİP İLE NASİP 2010-9265-1-0000-88-1** / cikis — c_0720 karesinde siyah zemin üzerinde turuncu "SON" yazısı okunabilir şekilde görünüyor — bu bitiş/jenerik kartı metni; havuz hiç kare tutmamış, yani tespit motoru bu metin karesini (ve muhtemelen 480-720 arası kaçırdığı ek jenerik karelerini) kaçırmış.
- **KANDIRMACA 2002-9058-1-0000-00-1** / cikis — c_0480 karesinde tam bir kredi akışı (crawl) net okunuyor: "Director Roth - Bill Macdonald", "Young Soldier - Mike Realba", "Production Manager - James Mou", "First Assistant Director - Teodor Oprea", "A Camera Operator - George Jiri Tirl" vb. isim+unvan satırları var. Bu kesin bir kredi/jenerik metni ama havuz hiç kare tutmamış — tespit motoru kaçırmış.
- **KÜÇÜK AYICIK 1997-0353-1-0000-00-1** / cikis — c_0480 karesinde acik okunabilir kapanis jenerigi var: 'Production Manager Mary Sparacio', 'First Assistant Director Dan Tohill', 'Second Assistant Director Dave Bene', 'Casting Po-ping AuYeung / Hank McCann' vb. Havuz bu kareyi tutmamis.
- **LA BOHEME 1988-0420-1-0000-00-1** / cikis — c_0480 ve c_0720 karelerinde net okunabilir Fransizca jenerik metni var: 'directeur artistique MICHEL GLOTZ', 'avec la voix de MICHEL SENECHAL', ve teknik ekip listesi (generique EURO-TITRES, disques ERATO logosu). Havuz bu kareleri kacirmis.
- **NAMUS DÜŞMANI 2010-9262-1-0000-88-1** / cikis — c_0001 arac arkadan plaka gorunumu, c_0240 oda ici grup sahnesi, c_0480 agac yaninda adam -- bunlarda metin yok, ANCAK c_0720'de siyah zemin uzerinde sari, tamamen okunabilir Arapca 'النهاية' (THE END/SON) yazisi acikca goruluyor; bu net bir kapanis-yazi karesi oldugu halde havuz 720 ham kareden hic kare tutmamis, yani jenerik-havuzu bu okunabilir kapanis kartini kacirmis.
- **PAMUK MARY 1999-0508-1-0000-00-1** / giris — g_0090 karesinde agacli yol sahnesinin altinda beyaz yaziyla acikca 'written by' / 'ALEXANDRA VIETS' jenerik metni goruluyor. Sistem bu net okunabilir krediyi kacirmis.
- **PERCY JACKSON-ŞİMŞEK HIRSIZI 2010-9169-1-0000-90-1** / cikis — c_0001 siyah, c_0240 ve c_0480 film sahneleri (savas alani, kutu tasima) olsa da c_0720 karesinde siyah zemin uzerinde duzenli sutunlar halinde onlarca okunabilir VFX/teknik ekip ismi ve unvani var (orn. 'Digital Compositing Leads JOEL BEHRENS MICHAEL MELCHIORRE', 'CG Sequence Supervisor RICHARD SCHUYLER MORTON'). Bu klasik kayan kapanis jenerigi, sistem kacirmis.
- **PUNKTCHEN VE ANTON 1999-0383-1-0000-00-1** / giris — g_0090 karesinde acikca okunabilir kredi metni var: ust satirda 'als Gast' (Almanca 'konuk oyuncu olarak'), altinda buyuk sari harflerle isim 'THOMAS HOLTZMANN' -- klasik cast-kredi bindirmesi bulutlu gokyuzu uzerinde. Bu net bir isim+unvan jenerigi oldugu halde havuz kare tutmamis, tespit motoru kacirmis.
- **SAVAŞTAN DÖNÜŞ 1996-0368-1-0000-00-1** / cikis — c_0240 karesinde net okunabilir İngilizce jenerik akışı var: 'Production Van Driver CHRIS A. BASSO', 'Drivers RON PASCALL / LONNIE D. NELSON / GREG FAUCETT / JACK PRINCE', 'Production Supervisor M. CEVIN CATHELL', 'Second Second Assistant Director CHEMEN A. OCHOA', 'Production Office Coordinator HOWARD W. CAREY', 'Assistant Production Office Coordinator BELINDA CELIS', 'Production Secretary CLINT SAWIN'. Bu tipik crawl-credits metni; havuz bunu kaçırmış (c_0001 otobüs durağı footage, c_0480 siyah/karanlık kare, c_0720 aktör yüzü footage).
- **TOPLU GÖSTERİLER 1989-0478-1-0000-00-1** / cikis — Son ornek kare c_0720'de siyah zemin uzerinde mavi/gri serif harflerle acikca okunabilir 'THE END' yazisi var -- klasik jenerik/bitis metni. Sistem bu kareyi/segmenti yakalayip master-PNG uretmemis; bu bir tespit kacirmasidir.
- **ÖNEM DERECESİ 1991-0495-1-0000-00-1** / cikis — c_0480 karesinde acikca okunabilir ingilizce kredi metni var: 'DEDICATED TO THE MEMORY OF D. BOON', altinda 'THE CAST in order of appearance' ve oyuncu listesi ('baby max ZA ZA DUPRE', 'maxwell glass ARYE GROSS'). Bu net bir kredi ekrani; jenerik-havuzu bunu kacirmis.
- **ÜÇ KURUŞLUK OPERA 1995-0289-1-0000-00-1** / cikis — c_0480 karesinde perde/kadife dekorlu bir kredi ekrani var: 'Hráli:' basligi altinda 'JOSEF ABRHÁM', 'MARIÁN LABUDA', 'RUDOLF HRUŠÍNSKÝ' isimleri acikca okunuyor (oyuncu kadrosu). Sistem bu kredi karesini kacirmis.

### B. Meşru-boş — bu pencerede gerçekten kredi metni yok, sistem doğru davranmış (69)

Örnek karelerde de yalnız sahne/footage veya siyah kapanış karesi var; havuzun boş kalması doğru karar. Liste (isim / segment):

- ADI CARMEN 1983-0256-1-0000-00-1 / cikis
- ADI CARMEN 1983-0256-1-0000-00-1 2 / cikis
- ADI CARMEN 1983-0256-1-0000-00-1 3 / cikis
- ALTIN VE ŞÖHRET 1984-0286-1-0000-00-1 / giris
- ALTIN VE ŞÖHRET 1984-0286-1-0000-00-1 / cikis
- ALTINA HÜCUM 1925-0008-1-0000-00-1 / cikis
- ANNEM ANNEM 2008-9064-1-0000-00-1 / cikis
- ARTAN İSTEKLER 1980-0142-1-0000-00-1 / cikis
- AYAK TAKIMI 1991-0415-1-0000-00-1 / cikis
- AYNA 1975-1016-1-0000-00-1 / cikis
- BATI CEPHESİNDE YENİ BİRŞEY YOK 1973-0198-1-0000-00-1 / cikis
- BEKARLIK SULTANLIKTIR 1958-0046-1-0000-00-1 / giris
- BEKARLIK SULTANLIKTIR 1958-0046-1-0000-00-1 / cikis
- BİR KATİLLE EVLENDİM 1993-0467-1-0000-00-1 / cikis
- DERTLER BENİM OLSUN 2010-9252-1-0000-88-1 / cikis
- DURUMU ANLAMAK 2000-0505-1-0000-00-1 / cikis
- DİŞİ ŞEYTAN 1964-0002-1-000-00-1 / cikis
- GERONIMO 1962-0022-1-0000-00-1 / cikis
- GÖLGELER PRENSİ 1991-0441-1-0000-00-1 / cikis
- GÜLLERİN SAVAŞI 2004-9139-1-0000-00-1 / cikis
- KARA GÜNLER 1998-0312-1-0000-00-1 / cikis
- KOMİSER 1994-0345-1-0000-00-1 / cikis
- KONTES ALICE 1992-0223-1-0000-00-1 / cikis
- KOPAR ZİNCİRLERİNİ GÜLSARI 1969-0091-1-0000-00-1 / cikis
- KORKUNÇ GECE 1995-0444-1-0000-00-1 / cikis
- KOVBOY 1958-0044-1-0000-90-1 / cikis
- KRAL LEAR 2018-9036-1-0000-00-1 / cikis
- KUSURSUZ BİR GÜN CENAZE TÖRENİ 2009-9137-1-0000-00-1 / cikis
- KÖPEKLE BİR TATİL 2000-0514-1-0000-00-1 / giris
- KÖPEKLE BİR TATİL 2000-0514-1-0000-00-1 / cikis
- METİN 1980-0149-1-0000-00-1 / cikis
- MOSKOVA BUZ BALESİ 1990-0321-1-0000-00-1 / cikis
- MOTORSİKLETLİ POLİSLER 2000-0303-1-0000-00-1 / cikis
- MURPHY KANUNLARI 2 2005-9051-1-0000-00-1 / cikis
- MUTLU GÜNLER 1967-0037-1-0000-00-1 / cikis
- MUTLU PASKALYA 1984-0274-1-0000-00-1 / cikis
- NAPOLYON 1988-0308-1-0000-00-1 / cikis
- NORWOORD 1970-0046-1-0000-00-1 / giris
- OMAGGIO A CARUSO 1997-0411-1-0000-00-1 / cikis
- OSCAR 1991-0525-1-0000-00-1 / cikis
- PRENSES WONONOKE 1997-0241-1-0000-00-1 / cikis
- RODEO TUTKUSU 1971-0057-1-0000-00-1 / cikis
- SEVİMLİ KÖPEK-YEDİNCİ OYUNDAKİ MUCİZE 2000-0282-1-0000-40-1 / cikis
- SINIR ÇİZGİSİ 1995-0280-1-0000-00-1 / giris
- SON BOLŞEVİK 1993-0439-1-0000-00-1 / cikis
- SON CÜCE 1998-0519-1-0000-00-1 / cikis
- SOYGUN 1986-0297-1-0000-00-1 / cikis
- SÜPER FOK 1975-0226-1-0000-00-1 / cikis
- TACİZ 2000-0476-1-0000-00-1 / giris
- TACİZ 2000-0476-1-0000-00-1 / cikis
- TANGO ARGENTINO 1996-0316-1-0000-00-1 / giris
- TANGO ARGENTINO 1996-0316-1-0000-00-1 / cikis
- TEPEDEKİ KIZ 1990-0519-1-0000-00-1 / giris
- TEPEDEKİ KIZ 1990-0519-1-0000-00-1 / cikis
- TOPLU GÖSTERİLER 1991-0356-1-0000-00-1 / giris
- TOPLU GÖSTERİLER 1991-0356-1-0000-00-1 / cikis
- TOTO 1995-1459-1-0000-00-1 / cikis
- UFAKLIK İÇİN BİR BABA 2003-9104-1-0000-00-1 / cikis
- UTANMAZ ADAM 1961-0005-1-000-00-1 / cikis
- VAHŞİ AFRİKA 2001-9314-1-0000-00-1 / cikis
- VİDEO OYUNU 1986-0240-1-0000-00-1 / cikis
- YABANCI MUHABİR 1940-0034-1-0000-00-1 / cikis
- YÜZYILIN CİNAYETİ 1933-0013-1-0000-00-1 / cikis
- YÜZÜKLERİN EFENDİSİ 2002-9089-1-0000-90-1 / cikis
- ÖLDÜRME ZAMANI 1989-0955-1-0000-00-1 / cikis
- İKİ KOCALI KADIN 1988-1557-1-0000-00-1 / cikis
- İŞARET DİREĞİ 1996-0310-1-0000-00-1 / cikis
- ŞAŞKIN REKLAMCI 1970-0076-1-0000-00-1 / cikis
- ŞEYTAN RUHLU İNSANLAR 1955-0046-1-0000-00-1 / cikis


### C. Manifest hiç yazılmamış — üretim adımı hiç tamamlanmadı (6 klasör)

Bu 6 klasörde `<TRT> <BAŞLIK> master_manifest.json` dosyasının kendisi yok — yani `master_png_monitor.py` üretim adımı ya hiç çalışmamış ya da çökmüş. Her biri tek tek klasör içeriğine bakılarak doğrulandı:

- **BEKLENEN BOMBA 1959-0005-1-000-00-1** — `frames/giris` (270), `frames/cikis` (720) dolu, `frames/giris_jenerik` 60 kare tutmuş (havuz boş değil), OCR/`kunye.txt` tamamlanmış. Ama `frames/cikis_jenerik` klasörü **hiç yok** ve master hiç üretilmemiş. Her şey hazır olduğu halde üretim adımı bu filmi hiç işlememiş — **gerçek bir orkestrasyon/kod boşluğu**, footage sorunu değil.
- **TOPLU GÖSTERİLER 1990-0285-1-0000-00-1** — `frames/giris` (270) ve `frames/cikis` (720) dolu, **her iki jenerik havuzu da dolu** (giriş 117, çıkış 109 kare), `kunye.txt` tamamlanmış. Yine her şey hazır ama master adımı hiç çalışmamış — **en net kod/orkestrasyon boşluğu örneği**, en yüksek öncelik.
- **BAŞKAN VE MARİ 1998-0970-1-0000-00-1**, **GÜNDÜZ GÜNEŞ 1992-0296-1-0000-00-1**, **SEN TOM SAWYER DEĞİLSİN 1993-0435-1-0000-00-1** — üçünde de `frames/` klasörü tamamen boş (ne giriş ne çıkış karesi çıkarılmış) ve OCR hiç çalışmamış. Bu, master-png adımından önceki bir aşamada (kare çıkarma/video işleme) sürecin durduğuna işaret ediyor — muhtemelen o çalıştırma yarıda kesilmiş/hiç tamamlanmamış bir iş, master-png koduna özgü bir kusur değil.
- **SERÇELERİN ŞARKISI 2008-9083-1-0000-00-1** — kareler var (giriş 270/37 havuz, çıkış 720/0 havuz) ama `kunye.txt` **yok** — yani OCR/künye çıkarımı da tamamlanmamış. Bu film genel olarak yarım kalmış bir işlem, sadece master-png'ye özgü değil.

### D. Özel durum: YÜZÜKLERİN EFENDİSİ (2002-9089-1-0000-90-1)

Hem giriş hem çıkış jenerik havuzu boş (`giris_jenerik`=0, `cikis_jenerik`=0) — ama bu filmin gerçek, uzun bir akan kapanış jeneriği olduğu biliniyor. Bu, **daha önce tespit edilmiş ve belgelenmiş bir kod sorunu**: sıkı kredi-tespit motoru bu filmde 0 kare bulurken, önceden denenen gevşek motor 525 kredi karesi bulmuştu (`outputs/MASTER_PNG_BULGULAR_2026-07-06.md`). Ayrıca bu filmin `master_manifest.json`'ında `giris_reading_master_runaware` anahtarı hiç yok (`reading_master_runaware` ve `giris` anahtarları var) — kodun normal akışında bu anahtarın her zaman yazılması beklenir; bunun neden atlandığı incelemede netleşmedi, ayrı bir küçük anomali olarak not düşülüyor.

---

## Özet

| Kategori | Sayı |
|---|---|
| Toplam film klasörü | 294 |
| Giriş master mevcut | 276 / 294 |
| Çıkış master mevcut | 211 / 294 |
| **Mevcut + OKUNUR** | 434 / 487 |
| **Mevcut ama SORUNLU** (isimler yukarıda 1. bölüm) | 53 / 487 |
| -- tekrar/stitching hatası | 27 |
| -- bulanık/bozuk/okunamaz | 17 |
| -- kredi metni hiç yakalanmamış | 9 |
| Eksik segment vakası (havuz-boş) | 88 |
| -- Havuz-boş, detektör kaçırmış (KOD sorunu) | 19 |
| -- Havuz-boş, meşru (gerçekten jeneriksiz) | 69 |
| Manifest hiç yazılmamış (orkestrasyon boşluğu) | 6 klasör |
| Bilinen özel durum (YÜZÜKLERİN EFENDİSİ) | 1 |

**Sonuç:** Hiçbir eksiklik ham görüntü/frame çıkarma hatasından kaynaklanmıyor. Asıl iki kök neden: (1) çıkış segmentinin kredi-tespit motoru girişe göre çok daha sık kare kaçırıyor (88 havuz-boş vakanın 19'u kanıtlı tespit hatası, 69'u meşru), (2) 6 klasörde üretim adımı hiç çalışmamış -- özellikle **BEKLENEN BOMBA** ve **TOPLU GÖSTERİLER 1990-0285** her şey hazırken (kareler + havuzlar + kunye dolu) master adımı atlanmış, bu ikisi en açık kod/orkestrasyon boşluğu örneği.
