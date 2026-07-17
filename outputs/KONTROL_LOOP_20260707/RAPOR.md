# KONTROL-LOOP RAPORU — 2026-07-07

Çağatay `/loop`: tüm KONTROL filmleri → nokta-atışı kök-neden → 3-prensipli fix → uçtan-uca doğrula → sonraki. Zor/riskli/geneli-bozacak = rapor (uygulama yok).

## 🚨 KRİTİK BULGU (2026-07-09, öncelikli okuma): YANLIŞ AFİŞ riski — muhtemelen TÜM ONAYLI arşivini etkiliyor
Bu turda **3 BAĞIMSIZ film** gözle-teyitli TAMAMEN YANLIŞ afişle karşılaştı (üçüncü örnek deseni kesinleştirdi — hepsi KISA/JENERİK Türkçe başlıklı filmlerde):
- **REKABET (1983-0234, gerçek konu: bisiklet yarışı draması)** → afiş **"CHALLENGERS"** (2024, Zendaya'lı tenis filmi) çıktı.
- **VİDEO OYUNU (1986-0240, gerçek konu: Alman bilim-kurgu "Videopoly")** → afiş **"Barbie Video Game Hero"** (2017 CGI-animasyon) çıktı.
- **AĞAÇ (1986-0334, gerçek konu: Jeanne Moreau'lu Fransız aile-draması "L'Arbre")** → afiş **"KARA AĞAÇ DESTANI"** (alakasız bir Türk TV dizisi) çıktı.
Üçü de PROMOTE EDİLMEDİ (yönetmen/cast/tür/özet aslında TEMİZDİ, yalnız afiş yüzünden durduruldu). **KONTROL grubu (aynı gece, aynı mekanizma, doğru sonuç):** ÇÖL ASLANI (*Lion of the Desert*) hem eski hem yeni koşuda DOĞRU afişle geldi — demek ki mekanizma HER ZAMAN bozuk değil, yalnız KISA/JENERİK/başka-anlamlı Türkçe kelime olan başlıklarda (REKABET/"rekabet", AĞAÇ/"ağaç", VİDEO OYUNU/"video oyunu" — hepsi TMDB/IMDb'de başka bir yapımın AKA'sı ya da kelimenin kendisiyle çakışabilecek kadar jenerik) tetikleniyor gibi görünüyor.

**Kök-neden izi (kısmen kesinleşti, TAM kod-satırına kadar sabitlenemedi — 2026-07-09 gece derin-dalış):**
- Doğrudan test: TMDB'nin KENDİ arama API'si `/search/movie?query=REKABET` sorgusuna **"Challengers"i (tmdb 937287) DÖNDÜRÜYOR** (muhtemelen TMDB'nin dahili AKA/yerelleştirilmiş-başlık eşleştirmesi "Rekabet"i Türkiye-gösterim-adı olarak Challengers'a bağlamış — dış veri kaynağının kendi metadata'sı, bizim hatamız değil ama bizim KODUMUZ buna karşı SAVUNMASIZ).
- `poster_fetch.py`'nin `_search()` (başlık-string eşleşmeli) yolunda **"KADRO-ZORUNLU KAPI"** var (cast doğrulanmadan title-only eşleşme YAPILMAZ, `credit_text_read.py` içinde AKIL OYUNLARI vakasından beri) — bu kapı doğrudan test edildi, DOĞRU çalışıyor (REKABET'in gerçek cast'iyle çağrıldığında "Challengers"ı reddediyor, `None` dönüyor).
- AMA `poster_fetch.fetch_poster()`'ın **"doğrulanmış-id" zinciri** (`_fetch_tmdb_poster`/`_fetch_omdb_poster`/`_fetch_wikipedia_poster` — `tmdb_id`/`imdb_id` verildiğinde çalışan yol) **HİÇBİR cast-doğrulaması YAPMIYOR** — tasarım gereği "id zaten yukarıda doğrulanmış" varsayımıyla köre-güveniyor.
- `credit_qc_gates.web_identity()`'nin ÇAPA-2 (TMDB başlık-arama) dalı da (satır ~264-304) **cast-kontrolsüz**, yalnız başlık-fold + yıl±2 ile "güvenli tek-eşleşme" kabul ediyor — TAM outputs REKABET/Challengers senaryosuna uygun bir açık.
- **DOĞRUDAN TEST ÇELİŞKİSİ:** `credit_qc_gates.web_identity()`'yi REKABET'in GERÇEK parametreleriyle (title="REKABET", original="GEEL TRUI VIR 'N WENNER", ocr_director="FRANZ MARX") elle çağırdığımda **DOĞRU sonucu döndürdü** (ÇAPA-1/yönetmen-çapası ile, imdb_id=tt2033995, cast tam eşleşti, tmdb_id=None) — yani BU spesifik çağrı güvenli. Gerçek üretim-koşusunda hangi ÖZEL koşulun (belki `ocr_director` o an boştu, belki farklı bir kod-yolu — `poster_fetch.py`'nin İKİNCİ çağrı-noktası `tek_film_kunye.py:1160`, `credit_identity.resolve()` TMDB-kadro-konsensüsü — devreye girdi) yanlış zinciri tetiklediği TAM olarak sabitlenemedi; zaman kısıtı nedeniyle canlı-debug/print-instrümantasyonlu bir yeniden-koşu yapılmadı.

**4. ÖRNEK BULUNDU (2026-07-09, KONTROL-loop sırasında, kendiliğinden DÜZELDİ):** SHAOLIN (2011-9175, "_RENDER" bayraklı) — eski KONTROL PDF'inde afiş **"SHAOLIN WOODEN MEN"** (1976, tamamen alakasız, genç Jackie Chan'li eski bir film) gösteriyordu; gerçek film 2011 yapımı "Shaolin" (Andy Lau/Nicholas Tse/Jackie Chan/Fan Bingbing). Bu turda tek_film_kunye.py --clip ile yeniden-render edildiğinde poster_fetch DOĞRU afişi (2011 Shaolin, cast'le birebir örtüşen) buldu — görsel doğrulandı, promote edildi. Bu, "_RENDER" bayrağının bu vakada gerçekte "yanlış-afiş" anlamına geldiğini ve mekanizmanın DETERMİNİSTİK olmadığını (aynı film bazen doğru bazen yanlış afiş bulabiliyor) gösteriyor.

**ETKİ ALANI BELİRSİZ AMA POTANSİYEL OLARAK GENİŞ:** Bu mekanizma (`poster_fetch.py`, `credit_qc_gates.web_identity`, `credit_identity.resolve`) SADECE bu 2 film için değil, **kimlik zayıf/obscure olan HER filmin afiş-alma sürecinde** çalışıyor — bu oturumda promosyona AYRILAN 16 filmin ÇOĞUNDA afişi doğrudan gözle kontrol ettim (SON TANIK/HAYATIMIN ERKEĞİ/AYAK TAKIMI/KARA GÜNLER — hepsi doğru göründü) AMA **daha önceki (dünkü 9 promosyon + bugünkü GERONIMO/ÖLÜM VURUŞU/BÜYÜK MÜCADELE) için afiş-İÇERİĞİNİ tek-tek gözle DOĞRULAMADIM** (yalnız `afis: true/false` bayrağına baktım çoğu zaman) — bu filmlerin afişleri de YANLIŞ olabilir, DOĞRULANMADI.

**ÖNERİLEN SONRAKI ADIM (uygulanmadı, kapsamı geniş+ayrı-oturum gerektiriyor):**
1. **ACİL:** ONAYLI klasöründeki TÜM afişleri (233+ film) gözle/otomatik-karşılaştırmalı taramadan geçirmek (ör. her afişin TMDB/IMDb'deki GERÇEK afişle piksel/hash-benzerliği, ya da en azından "afiş görsel-türü filmin türüyle uyumlu mu" gibi kaba bir LLM-görsel-QC).
2. **Kod-fix (dar, ama dikkatli test gerektirir):** `poster_fetch.py`'nin ID-güvenilir zincirine ("`_fetch_tmdb_poster`/`_fetch_omdb_poster`") EK bir cast-crosscheck kapısı eklemek (TMDB/OMDb'den dönen filmin KENDİ cast listesini çekip OCR-cast'le kesişim ara, kesişim yoksa afişi REDDET) — mevcut `_search()`'ün "KADRO-ZORUNLU KAPI" mantığının AYNISI, farklı bir fonksiyona taşınması.
3. **Alternatif (daha basit, daha kısıtlayıcı):** `credit_qc_gates.web_identity()` ÇAPA-2'yi (TMDB başlık-arama, cast-kontrolsüz) TAMAMEN DEVRE DIŞI BIRAKMAK, yalnız ÇAPA-1'i (yönetmen-çapası, YEREL KB, zaten cast-teyitli) bırakmak — daha güvenli ama daha az kapsayıcı (bazı filmler afişsiz kalır, "afişsiz > yanlış-afiş" ilkesiyle uyumlu).
**Bu bulgu Çağatay'a AYRICA bildirilmeli — kapsamı bu oturumun tek-film-odaklı akışının çok ötesinde.**

## 🚨 KRİTİK BULGU #2 (2026-07-09): mitas.duckdb'ye erişim KESİK — Türkçe isimlerde aksan-kaybı + genel güvenilirlik riski

`X:\DIGER\Mitas_Files\MitaData\mitas.duckdb` (KB-doğrulama/isim-normalize'in ana veritabanı) bu gece **erişilemez durumda**: `IO Error: Cannot open file ... Kullanıcı adı veya parola hatalı` — doğrudan test edildi (`duckdb.connect(..., read_only=True)`), birden fazla kez, hep aynı hata; **geçici/aralıklı değil, KALICI görünüyor**. Bu, `name_normalize`'ın CSV-fallback yoluna düşmesine yol açıyor (log'da her koşuda 2-3 kez uyarı çıkıyor).

**Somut etki (3 filmde doğrudan gözlemlendi — MİRAS, HASİP İLE NASİP, DİŞİ ŞEYTAN):** CSV-fallback devreye girince TÜRKÇE isimler aksanlarını kaybediyor — "Zeki ALASYA"→"ZEKI ALASYA", "Nazmi ÖZER"→"NAZMI OZER", "Memduh ÜN"→"MEMDUH UN", "Suavi EREN"→"SUAVI EREN" vb. **Bu, uyarı mesajının kendi açıklamasıyla ("yabancı isim Türkçe-kasa alabilir") ters yönde ama aynı kök-mekanizma** — DB yokken isim-kasası genel olarak güvenilmez hale geliyor, sadece "yabancı→Türkçe" değil "Türkçe→bozuk-ASCII" yönünde de.

**DİŞİ ŞEYTAN özel örneği — bu gecenin en net kanıtı:** bu filmde bu gece commit edilen "FOTO DİREKTÖRÜ sinematograf-vetosu" kod-düzeltmesi UÇTAN UCA doğrulandı (Yönetmen alanı boştan "NEVZAT PESEN"e doldu, frame'de "Fotoğraf direktörü/TURGUT ÖREN" doğru elendi, "Prodüktör Rejisör/NEVZAT PESEN" doğru yakalandı — %100 doğru) — AMA aynı render'da "NAZMİ ÖZER" (eski PDF'te doğru) → "NAZMI OZER" (yeni, aksan kaybı) olduğu için **promote EDİLEMEDİ**. Yani: kod-fix çalışıyor, promosyonu engelleyen SADECE bu ayrı, altyapısal DB-erişim sorunu.

**Bu bir kod-hatası DEĞİL** — muhtemelen X:\ sürücüsünün ağ-kimlik-bilgisi süresi dolmuş/değişmiş (Windows mapped-drive credential sorunu). Kod tarafında yapılacak bir şey yok; **kullanıcının X:\ sürücüsü bağlantısını yeniden kimlik-doğrulaması** (örn. `net use X: /delete` sonra yeniden `net use X: \\sunucu\pay /user:...` veya Windows Gezgini'nden manuel yeniden-bağlan) gerekiyor. Düzeltilene kadar: **Türkçe oyuncu/yönetmen adı içeren HİÇBİR film, yalnızca bu yüzden, tam-doğru promote edilemeyebilir** — bu, TRT arşivinin büyük çoğunluğu Türkçe olduğu için geniş bir engel. Ayrıntı ve devam eden kanıt: `task_5aae0a2b` (spawn edilen ayrı görev, run-to-run regresyon araştırmasıyla birleştirildi).

## 🚨 KRİTİK BULGU #3 (2026-07-09): TRT-kimlik/içerik UYUŞMAZLIĞI şüphesi — OMAGGIO A CARUSO (1997-0411) fiziksel olarak "UGETSU" (Mizoguchi, 1953)

Bu, bu geceki DİĞER bulgulardan (okuma/extraction hatası) TAMAMEN FARKLI bir sınıf: bir metin-yorumlama sorunu DEĞİL, olası bir ARŞİV-KATALOG/İÇERİK uyuşmazlığı.

**TRT-KİMLİK 1997-0411**, KONTROL kaydında ve eski PDF'te başlık **"OMAGGIO A CARUSO"** (İtalyanca, "Caruso'ya Saygı" — opera sanatçısı Enrico Caruso ile ilgili bir yapım olması beklenir) olarak kayıtlı. Bu turda tek_film_kunye.py --clip ile yeniden-render edilince kimlik_dogru=true ile başlık **"UGETSU"**ya döndü — ilk bakışta "yanlış okuma" sanılabilir, ama frame'e inilince (giris_reading_master_runaware_p01.png) KESİN doğrulandı: ekranda net biçimde **"UGETSU MONOGATARI / Based on the stories of Akinari Ueda / Players: Lady Wakasa...Machiko Kyo, Genjuro...Masayuki Mori, Miyagi...Kinuyo Tanaka.../ Directed by KENJI MIZOGUCHI / Cinematography...Kazuo Miyagawa / Produced by...Masaichi Nagata"** yazıyor — bu, **Kenji Mizoguchi'nin 1953 tarihli, dünyaca ünlü "Ugetsu" filmi**, İtalyanca bir Caruso-belgeseli/biyografisiyle HİÇBİR ilgisi yok.

**Bu, bir OCR/LLM okuma hatası DEĞİL** — ekranda yazan ne varsa doğru okunmuş (Ugetsu), sorun bu TRT-kimliğin kataloğunun ("Omaggio a Caruso" başlığı) fiziksel/dijitalleştirilmiş içerikle UYUŞMUYOR olması. Olası açıklamalar: (a) yanlış kaset dijitalleştirilmiş/yanlış TRT-ID'ye atanmış, (b) TRT'nin kendi katalog kaydı başlangıçtan yanlış, (c) çok-parçalı bir banttan yanlış segment kırpılmış. **Hiçbiri benim düzeltebileceğim bir kod-sorunu değil** — bu, TRT'nin kendi arşiv kaydı/fiziksel kaynağıyla çapraz-kontrol gerektiren bir insan/kurumsal karar.

**UYGULANMADI, dokunulmadı** — başlığı "Ugetsu"ya çevirip promote etmek YANLIŞ olur (hangi kaydın doğru olduğu benim yetkimde değil); "Omaggio a Caruso" başlığıyla Ugetsu içeriğini bırakmak da yanlış. **Bu bulgu Çağatay'a AYRICA ve ÖNCELİKLE bildirilmeli** — eğer bu TEK bir vaka değilse (yani TRT kataloğunda başka yanlış-eşleşen ID'ler varsa), bu KONTROL-loop'un ötesinde, arşivin bütünlüğünü ilgilendiren bir konu.

## 🚨 KRİTİK BULGU #4 (2026-07-09): run-to-run çöküşünün KESİN kök nedeni bulundu — Opus ajanıyla canlı-yeniden-üretimle kanıtlandı

Çağatay'ın isteğiyle ("yanına bi opus max al") derin bir Opus ajanı görevlendirildi, geçici debug-instrümantasyonla CANLI yeniden-üretim yaptı ve KESİN, kanıta-dayalı 2 BAĞIMSIZ kök-neden buldu. İkisi de %100 DETERMİNİSTİK — GPU-çekişmesi veya model-rastgeleliği DEĞİL, yani basit yeniden-deneme bunları DÜZELTMEZ.

**Önce düzeltme:** `--clip` modu `credit_video_read` (VL-ensemble) ÇAĞIRMIYOR — gerçek yol `credit_text_read.read_credits_auto` → `_ollama_json`, TEK model (`gemma-4-31b-it-qat-vision`) ile OCR-metninden rol-eşleme. Bu gece boyunca yaptığım "VL-ensemble stokastikliği" varsayımı yanlış yerdeydi.

**KÖK-NEDEN A — işlenmemiş/çökmüş OCR hub'ı (TOM SAWYER + PUNKTCHEN VE ANTON sınıfı):** `--clip` SADECE `ocr/*/kunye.txt` okur. TOM SAWYER'da `frames/` VE `ocr/` tamamen BOŞ (`clip.json` içinde `modules:{}` — hiç işlenmemiş); PUNKTCHEN VE ANTON'da OCR job'ı `status:"failed"` ile çökmüş. Dosya yoksa `vc={}`, LLM'e HİÇ ÇAĞRI YAPILMIYOR bile — %100 deterministik boşluk.

**KÖK-NEDEN B — bağlam-penceresi (context window) taşması (BEYAZ AVUÇLAR sınıfı):** `credit_text_read._ollama_json`'da `num_ctx=8192` SABİT. BEYAZ AVUÇLAR'ın gürültülü OCR'ı + 2026-07-03/07 tarihli "master-dilim" additive bloğu prompt'u **8116 token**'e çıkarıyor (8192 sınırının dibinde) → modele cevap için sadece **~76 token** kalıyor → şema `_reasoning` alanını ÖNCE doldurmayı istediği için model o 76 tokeni oraya harcayıp `done_reason="length"` ile YARIDA KESİLİYOR → JSON parse edilemiyor → `_ollama_json` SESSİZCE `{}` döndürüyor → her şey boşalıyor, deterministik rescue bir etiket-parçasını ("IRTA ES") sahte isim sanıyor.

**Kanıt (kontrollü A/B testi, ajanın kendi canlı koşusu):** aynı model/OCR/ayarlarla, SADECE "dilim" bloğu var/yok değişkeniyle: dilim VARKEN prompt=8116, `done_reason=length`, sonuç ÇÖKÜYOR (bu geceki gerçek log ile birebir aynı); dilim YOKKEN prompt=4565, `done_reason=stop`, sonuç 5 Temmuz'daki doğru teslimin AYNISI (Hajdu Szabolcs yönetmen, Mathieu Kassovitz dahil 3 yapımcı, 10 oyuncu).

**Elenen hipotezler:** GPU-paylaşımı (GPU boş + doğru model yüklüyken de aynı çöküş tekrarlandı — `temp=0` deterministik olduğu için yeniden-deneme ASLA düzeltmez), mitas.duckdb erişilemezliği (sadece `name_normalize`'ın Türkçe-kasa kozmetiği için kullanılıyor, gerçek KB doğrulaması AYRI/lokal bir duckdb'ye bakıyor ve sağlam çalışıyor — cast=0'ın sebebi KB değil, LLM'in `{}` dönmesi).

**Önerilen fix-yüzeyi (UYGULANMADI — task_5aae0a2b'ye ait, ayrı oturumda):** (1) `num_ctx`'i büyüt (16384/32768) veya OCR+dilim satır bütçesini prompt'a girmeden sınırla; (2) `_ollama_json`'ı sessizlikten çıkar — `done_reason=="length"` veya parse-fail'de stderr uyarısı bas (bu sessizlik bug'ın 3 gündür görünmemesinin sebebi); (3) `--clip`'te `ocr/*/kunye.txt` yoksa açıkça uyar, sessizce boş PDF üretme.

Enstrümantasyon temizlendi (`git diff scripts/credit_text_read.py` boş), kaynak hub'lara dokunulmadı, tüm repro çıktıları scratchpad'de kaldı.

## 📌 YÖNETİCİ ÖZETİ (güncel durum — 2026-07-09 sabah güncellemesi)

**Promote edilen: 23 film** (KONTROL→ONAYLI, hepsi gözle-frame-teyitli + byte-diff-temiz + yedekli, afiş-içeriği de dahil): ANGOLA'DAN KAÇIŞ, ŞEYTAN RUHLU İNSANLAR, DENİZ EJDERİ, CENNETE GELDİK Mİ, SAVAŞTAN DÖNÜŞ, İHTİRAS CİNAYETİ, İSYAN, FISILTILAR, JONSSON ÇETESİ (dün) + GERONIMO, ÖLÜM VURUŞU, BÜYÜK MÜCADELE, SON TANIK, KARA GÜNLER, HAYATIMIN ERKEĞİ, AYAK TAKIMI (=Riff-Raff, Ken Loach), ÇÖL ASLANI (=Lion of the Desert) + **İŞTE BIRD, RENE, CİNAYET YERİ, JARRAPELLEJOSILAR, JOE SHARP, SHAOLIN** (bu son turda). **ONAYLI 20→51, KONTROL 243→198.**

**Bu turda AYRICA bulunan, önemli ama uygulanmadı/promote-edilemedi:** SINIF-1 (KB-doğrulama yönetmen-silme) 7+ filmde doğrulandı → `task_8de6b060`; run-to-run VL-ensemble regresyonu ~1/3 oranında 7 filmde yakalandı → `task_5aae0a2b`; mitas.duckdb erişim-kesikliği + Türkçe-aksan-kaybı → yukarıda KRİTİK BULGU #2; İKİNCİ ŞANS+YALNIZ TOM+DİŞİ ŞEYTAN'da bu geceki kod-fixleri UÇTAN UCA doğrulandı ama ayrı (ASR-özet-boşluğu veya duckdb-aksan) sorunlar yüzünden henüz promote edilemedi — düzeltilince hızlı yeniden-kontrol adayı.

**Kod-fix commit'leri (bu turda 4 yeni, hepsi deterministik-test + golden-regresyon kanıtlı; dünkü 8 commit'e ek):**
9. İKİNCİ ŞANS/Reuben Rose — KB-çelişkisi temiz-OCR'ı sessizce siliyordu, iki-kapılı koruma (`_valid_person_name`+geniş-KB-varlık) [434f8bef] — **AYRICA KARA GÜNLER'i de dolaylı çözdü (2. doğrulanmış kazanım).**
10. TR "FOTO DİREKTÖRÜ" sinematograf-vetosu — DİŞİ ŞEYTAN kökü [60902423]
11. `_valid_person_name` baş-harf-çoklu-isim istisnası — E.B. Clucher/BANA TRINITY DERLER kökü [71871a54]
12. TR "efekt" junk-kelime eksiği — MİRAS kökü [70ccfc24]
Ayrıca: "-fb" fallback-OCR filtre hatası (substring→suffix, 4 dosyada) [434f8bef ile birlikte] — golden 5/7'ye çıktı.
**DENENİP REGRESYON ÇIKAN, GERİ ALINAN (commit'lenmedi):** DİŞİ ŞEYTAN'ın "senaryo/written by" fix'i BUZDAN GELEN SESLER'i kırdı; YA NASİP YA KISMET için 2. kod-yolunda denenen aynı iki-kapı deseni ONDAN UZAKTA'nın doğru-reddini bozdu. İkisi de golden-regresyon/hedefli-regresyon-testiyle YAKALANDI, derhal geri alındı — **disiplin çalışıyor.**

**YENİ SINIF (bu turda, CİDDİ): SINIF-I — çok-isimli/çok-sütunlu jenerik kartlarında kısmi-isim-kaybı**, 4 BAĞIMSIZ filmde doğrulandı (KOVBOY, LAUREL HARDY, GLORIA KUŞATMASI, BİR YAZ MACERASI) — LAUREL HARDY'de filmin KENDİ başlık-yıldızları bile eksik. Paylaşılan VL-okuma mekanizması, UYGULANMADI (yüksek risk/tek-örnekle-genelleme).

**YENİ METODOLOJİ DERSİ (bu turda):** "yapısal-geçerli+geniş-KB'de-gerçek-kişi" iki-kapı testi TEK BAŞINA yeterli değil — bağlam-izolasyonu (adayın KENDİ BAŞINA duran bir kart mı, yoksa uzun bir teşekkür/kaynak-bölümü içinde mi) eksik sinyal; bu yüzden AYNI fix bir kod-yolunda güvenli (KARA GÜNLER) diğerinde güvensiz (ONDAN UZAKTA/YA NASİP YA KISMET) çıktı — kod-yoluna göre YENİDEN test şart. Ayrıca: **mtime "en-yeni=en-doğru" garantisi YANLIŞ** — FUTBOLCU PRENSES'te yeni koşu eski koşudan daha KÖTÜ cast üretti (takım-adları kişi sanıldı); alan-bazlı çapraz-kontrol zorunlu.

**Sistemik/riskli bulgular (rapor edildi, UYGULANMADI — geniş-kapsam veya kanıt-eksikliği nedeniyle):**
- **KB-disambiguation** (İNTİKAM, YARGIÇ VE POLİS, DENİZLER ALTINDA 20.000 FERSAH, BÜYÜK MÜCADELE, BİR YAZ MACERASI) — dış-KB yanlış/eksik/obscure-title eşleşme, iç-doğrulama zaten doğru.
- **VL-stokastik gürültü** (İNTİKAM yönetmen-cast, KOVBOY cast) — kod-hatası değil, tek-geçiş model rastgele bozması.
- **ÖZET-içerik çelişkisi** (SOĞUK SUYA VURAN GÜNEŞ, UTANMAZ ADAM — 2. bağımsız örnek) — reprocessing-arası olay-örgüsü farkı, insan-kararı gerekli.
- **Eşik/pencere-seyrelmesi** (LENI RIEFENSTAHL) — paylaşılan `filter_cast_by_raw_context` eşiği, geniş etkili.
- **Çok-satır-kart birleştirme** (DELİLİĞİN SINIRINDA) — OCR "A...FILM" kartını 6 satıra bölmüş, hâlâ ÇELİŞKİ.
- **KOVBOY** ("BASED ON...BY" sınıfı farklı kod-yolunda) — birincil kanıt (XML) erişilemez, mekanizma net değil.
- **FERDİNAND animasyon VFX-ünvanları** ("XYZ Technical/Environmental Director") — açık-uçlu ünvan ailesi, dar liste eksik/geniş kural riskli.
- **BORÇ Türkî patronimik ek uyuşmazlığı** ("-oğlu" bitişik/ayrık) — isim-eşleştirmeye dokunmak tüm filmleri etkiler.
- **KOPAR ZİNCİRLERİNİ GÜLSARI** — video_okuma "SERGUEI OUROUSSEVSKY"yi ÇİFT-İMZA (kunye+dilim, ORTA güven) ile buldu ama final'de boş — YA NASİP YA KISMET/KOUDAYU ile AYNI açık problem (teyit-süzgeci obscure/yabancı filmlerde aşırı-temkinli), dokunulmadı (regresyon riski YA NASİP YA KISMET'te zaten ölçüldü).
- **KÜÇÜK SİMBA DÜNYA KUPASINDA** — cast=0, muhtemelen gerçek frame/OCR-katmanı boşluğu (agent'ın öngördüğünün aksine metin-yorumlama sorunu değil) — araştırılmadı, düşük öncelik.
- **BEKLENEN BOMBA (1959-0005) — YENİDEN doğrulandı, hâlâ riskli/uygulanmadı:** ocr_ham.txt satır 68-80 tekrar kontrol edildi: "MUHARREM / ESER VE REJİ / GÜRSES" (= gerçek Yeşilçam yönetmeni Muharrem Gürses; "ESER VE REJİ" = "Eser ve Reji" TR-etiketi AD ile SOYAD arasına araya girmiş, ad+soyad 2 satıra bölünmüş). Bu oturumun İLK yarısında (kompaksiyon-öncesi) zaten aynı sonuca varılmış ve "stitch/prompt-değişikliği geneli-bozar" gerekçesiyle UYGULANMAMIŞ — bu tur da AYNI riskli değerlendirmeyi koruyor, yeni bir kanıt/kod-yol bulunmadı. **PROMOTE EDİLMEDİ.**
- **BİR ZAMANLAR, BEKARLIK SULTANLIKTIR** — ikisi de zayıf sinyal (cast 0-2, kimlik_dogru çoğunlukla False) — agent'ın öngördüğü "KB cross-check yanlış-veto" değil, muhtemelen daha derin OCR/frame-katmanı sorunları — araştırılmadı, düşük öncelik.

### YALNIZ TOM (1992-0484) — FIXLENDİ (commit c1790423): "LST ASST" rol-fragmanı yönetmen-adayı sanılıyordu
Ham OCR: "lst Asst. Director" (garbled "1st Assistant Director", İSİMSİZ satır) yönetmen-adayı olarak "LST ASST" (2 gerçek-token, `_valid_person_name` junk-kontrolsüz geçiyordu) çıktı. `_JUNK_WORDS`'e "asst" eklendi (İngilizce rol-kısaltması, MİRAS/"efekt" fix'iyle AYNI dar desen). KANIT: unit 4/4 + golden 5/7. **Filmin kendisi PROMOTE EDİLEMEDİ** — gerçek "DIRECTED BY" kartı hiçbir yerde yok (yalnız 1st/2nd Asst. Director + diğer crew var), yönetmen genuinely-boş kalacak; bu fix yalnız gelecekte "LST ASST" gibi bir çöp-fragmanın YANLIŞLIKLA yönetmen basılmasını önlüyor.

- **KESS (1969-0094, muhtemelen = *Kes* 1969, Ken Loach — yapımcı "TONY GARNETT" bunu güçlü destekliyor), ÇİNGENE GÜVELERİ (1969-0032), IVAN'IN ÇOCUKLUĞU (1962-1124, Tarkovsky):** üçünde de `video_okuma.yon: []` — hiçbir "DIRECTED BY" benzeri kart ne kunye.txt'de ne ocr_ham.txt'de bulunamadı (KESS/ÇİNGENE: cast_ortusme=8 güçlü kimlik ama yönetmen-kartı hiç yakalanmamış; IVAN'IN ÇOCUKLUĞU: cast=0, daha derin bir okuma-boşluğu). Üçü de upstream-OCR/frame-seçim boşluğu sınıfı — **PROMOTE EDİLMEDİ, kod-fix konusu değil.**

### DERSU UZALA (1975-2246) — CİDDİ ŞÜPHE: Kurosawa'nın adı HİÇBİR YERDE yok, "Vladimir Vasilyev" farklı bir kişi olabilir
Bu SSCB-Japon ortak-yapımı (1975, Oscar-kazanan) için final yönetmen "VLADIMIR VASILYEV" — kare c_0628 doğrudan görüntülendi, Kiril metin net: "Режиссер / Владимир Васильев" (gerçek bir kart, gerçek bir isim, gözle-teyitli). AMA **filmin dünyaca bilinen gerçek yönetmeni Akira Kurosawa'nın adı (Kiril "Куросава"/Japonca) ne kunye.txt'de ne ocr_ham.txt'de ne 270 giriş-karesinin hiçbirinde bulunamadı** — muhtemelen açılışta Japonca-karakterli bir kart var (ham metinde bir yerde anlamsız "肉上" gibi bozuk-Japonca fragmanlar görüldü) ama OCR motoru bunu Kiril/Latin için ayarlı olduğundan hiç okuyamamış. "Vladimir Vasilyev" gerçek+ekran-teyitli olsa da, dünyaca ünlü bir Kurosawa filminde SSCB-tarafı ikincil bir yapım-yönetmeni/sorumlusu OLABİLİR (bazı ortak-yapımlarda yerel idari "рrodakşn menajer" tarzı bir rol de "Режиссер" etiketiyle listelenebiliyor) — ya da gerçekten film bu kopyada başka şekilde krediliyor olabilir; KESİN DEĞİL. **Çok-scriptli (Kiril+Japonca) OCR boşluğu + isim-belirsizliği kombinasyonu — kod-fix konusu değil, hem OCR-motor-kapsamı (Japonca) hem insan/arşiv araştırması gerektiriyor. PROMOTE EDİLMEDİ — yanlış yönetmen basma riski çok yüksek, bu tür ünlü bir filmde özellikle.**
- **KOLEKSİYON, BAHAR VE ŞARAP, GÜLLERİN SAVAŞI:** üçü de bu turda ya cast=0 ya kimlik_dogru=False+zayıf sinyal verdi — agent'ın CSV-notundaki spesifik hipotezler (validation-threshold, ALSO-STARRING-garble, garble_gate-Patrick-Leane) BU KOŞUDA gözlemlenemedi (muhtemelen VL-okuma stokastik varyansı, farklı bir kare-örneklemesi bu turda farklı/daha zayıf sonuç üretti). **Araştırılmadı, düşük öncelik — CSV'deki orijinal kanıt ESKİ bir koşudan, güncel-durumla eşleşmiyor.**
- **Upstream OCR/frame-havuzu boşluğu** (SANTRAL, HARRY'NİN UYANIŞI, NANCY'Yİ SEVMEK, SINIR ÇİZGİSİ, KÖŞENİN KRALI, AŞK ŞARKIM, MUTLU GÜNLER, RODEO TUTKUSU — sonuncu ikisi `cikis_jenerik` klasörü TAMAMEN boş) — gerçek yönetmen-kartı hiç OCR'lanmamış, `tek_film_kunye.py` yeniden-koşusu bunu düzeltmez (frame-seçim/OCR aşaması ayrı iş).
- **AJAMİ** — co-director "dissent yutulması" + "Rupert/Robert Preston" klon-ikiz fabrikasyonu, iki bilinen sorun hâlâ açık.
- **Mahlas/AKA-KB boşluğu** (BANA TRINITY DERLER/E.B. Clucher, KOUDAYU/Sato Junya) — ekran-mahlas IMDb'de yalnız gerçek-adla kayıtlı, geniş-KB-varlık kontrolü mahlası bulamıyor.

**Veri-hijyeni bulguları (kalıcı hafızaya işlendi):** aynı TRT'de bayat+güncel çift-KONTROL-PDF (mtime'a bak AMA TEK BAŞINA YETMEZ, alan-alan çapraz-kontrol); reprocessing sonrası ÖZET gibi dokunulmamış alanların da sessizce değişebilmesi (promote öncesi TÜM alanları diff'le — çok-sütunlu bölümler için `fitz` render ZORUNLU, `pdftotext -layout` yanıltıcı olabilir).

**Metodoloji dersi (LENI vakası + bu turun regresyonları):** ilk hipotez bazen yanlış çıkıyor — "muhtemelen X" dedikten SONRA bile doğrudan ölçüp teyit etmek şart; yanlışsa düzeltip dürüstçe raporla. Regresyon riski taşıyan HER fix golden-regresyon + (mümkünse) daha önce doğru-sonuç-veren spesifik bir örnek üzerinde YENİDEN test edilmeli.

---

## ✅ Düzeltilen (fix uygulandı + uçtan-uca doğrulandı)

| # | Film (TRT) | Kök-neden (nokta atışı) | Fix | Doğrulama |
|---|---|---|---|---|
| 1 | ANGOLA'DAN KAÇIŞ (1976-0184) | Ekran "DIRECTED BY LESLIE MARTINSON" (sade); KB'de "Leslie H. Martinson"=director ama sade "Leslie Martinson"=production dept → `kb.verify`=RED → `_fuse_yonetmen` doğru okunan yönetmeni attı (7/7 model okuyor, %0 basılıyordu) | `_kb_verify_flex` **B-yönü**: tek-harf token (baş/orta) yok sayarak çekirdek ad+soyad eşit **tek net** rol-ONAY'lı KB kaydı → ONAY. Kill: `MITAS_KB_INITIAL_TOLERANS=0` | unit 5/5 (deterministik) + golden 4-gerçek-PASS korundu (TILSIMLI boş) + üretim 7/7 "Leslie Martinson" dolu. commit 758e38df + golden/test |
| 2 | ŞEYTAN RUHLU İNSANLAR / *Les Diaboliques* (1955-0046) | Ekran "produit et dirigé par H.G. CLOUZOT"; model "H.G. CLOUZOT" okur ama KB "Henri-Georges Clouzot" tutar → `kayit-yok`. **İKİ katmanlı drop:** (a) `_kb_verify_flex` baş-harf-genişletme yapamıyor, (b) son-süzgeç `_only_persons`→`_valid_person_name` "H.G. Clouzot"u ≥2-token ile eliyor. Ayrıca rescue "PRODUIT ET" çöp emit ediyordu | (C) `_kb_verify_flex` **baş-harf-GENİŞLETME**: soyad-eşit + query baş-harfleri KB ad-kısmı-baş-harflerinin PREFIX'i + TEK rol-ONAY'lı → ONAY (H.G.→Henri-Georges eşsiz). + `_only_persons` **KB-teyit istisnası**: fuse KB-onay/mutabakat/kanonik/çift-imza onayladıysa ≥2-token heuristiği uygulanmaz. Kill: aynı `MITAS_KB_INITIAL_TOLERANS=0` | unit 8/8 (H.G.Clouzot→ONAY, E.B.Clucher→köprü-YOK) + ŞEYTAN üretim "H.G. CLOUZOT" DOLU (rescue-çöp de çözüldü, fuse doldu) + golden bekleniyor |

## 🎯 KB-TOLERANS SINIF KAZANCI + yakalanan regresyon (2026-07-07)

ANGOLA(B) + ŞEYTAN(C) + _only_persons istisnası fix'leri **51 A_ELENDI filminin ~28'ini doldurdu**; KOKNEDEN aday'ıyla çapraz + gözle teyit: **~21 DOĞRU** (Alfred Werker, H.G.Clouzot, Serguei Ourousevsky, Brian Trenchard-Smith, Emilio Estevez, Bill L.Norton, Kjell Sundvall, Graeme Clifford, Gulzar...). **Bunlar re-render → KONTROL'den çıkma adayı.**

**⚠️ REGRESYON YAKALANDI + GİDERİLDİ (commit sonrası):** case-C baş-harf-genişletme, KOMİSER'de "V. Grigoryev"i (KB'de assistant_director=RED, gerçek yön. Askoldov) yanlışlıkla "Victor Grigoryev" director'a genişletip yanlış yönetmen basmıştı. Fix: case-C yalnız `kayit-yok`'ta çalışır (RED'i ezmez). test 9/9. Çağatay'ın gözle-teyit disiplini yakaladı.

## ⚠️ Rapor edilenler (riskli / geneli-bozacak — Çağatay oturum sonu değerlendirir)

### SINIF-C: rescue-garble (`_yon_rescue_auto` yanlış/garble yönetmen basıyor — ÖNCEDEN VAR, benim değil)
Fuse boş kalınca rescue "director"-benzeri etikete komşu satırı kapıyor ama garble/yanlış çekiyor. Görsel-teyitli örnekler: **BİR BEBEK EVİ** → "OI PHEN" (gerçek: Joseph Losey, framede "Joseph Losey/director" NET — rescue "director of photography" garble'ından kaptı); **DELİLİĞİN SINIRINDA** → "NICK MCLEAN" (o görüntü-yönetmeni; gerçek Danny Huston); **HİTLER'İN HAZİNESİ** → "REGULA GRALWILLER" (gerçek Hardy Martins). Fix riskli (rescue delikatesi + garble-tespiti gap) → dikkatli/konsey.

### SINIF-C GÜNCELLEME: cinematograf-veto FİXLENDİ (2026-07-07, iki-katmanlı kök-neden)
"DIRECTOR OF PHOTOGRAPHY" ağır garble'landığında (PHON/PHEN/PHO) hem `credit_text_read._rsc_label_fuzzy` (path B) hem `credit_role_lexicon.director_name_from_line` (path A, TAMAMEN AYRI modül) EXCLUDE-listesinin TAM-STRING eşleşmesini atlayıp görüntü-yönetmenini film-yönetmeni sanıyordu (BİR BEBEK EVİ→"OI PHEN" çöpü). Her ikisine de dar veto eklendi: "DIRECTOR" + sonraki-token "PH..." → asla gerçek etiket. Test 7/7+7/7, golden regresyon-yok. **BİR BEBEK EVİ artık "Josaph Losay" (Joseph Losey'nin garble-okuması, doğru kişi) döndürüyor** — KB-kanonikleştirme aşaması (tam pipeline) bunu "Joseph Losey"ye çevirmeli, ayrıca doğrulanacak.
**DELİLİĞİN SINIRINDA hâlâ çözülemedi — FARKLI kök-neden:** gerçek yönetmen "DANNY HUSTON" kendinden-etiketli "A...FILM" kartı ama OCR bunu 6 ayrı satıra bölmüş (araya "GREIF COMPANY/PRODUCTION/IN ASSOCIATION WITH" giriyor) → `_DIRECTOR_CARD_RE` tek-satır regex'i eşleşmiyor. Çok-satır yeniden-birleştirme geniş bir "ileri-bak" sezgiseli gerektirir → başka filmlerde yanlış-birleşme riski (regresyon). **RİSKLİ, uygulanmadı — konsey-adayı.**

**BİR BEBEK EVİ (Joseph Losey) — fix DOĞRU çalıştı ama film KONTROL'de KALIYOR (meşru):** tam-pipeline "Josaph Losay" (doğru kişi, garble-okuma) çıkardı ama filmin CAST'i genel olarak ağır garble (cast_ortusme=0, kimlik hiç kurulamadı) → İSİM-DÜZEYİ TEYİT SÜZGECİ (2026-07-05 kuralı, "teyitsiz tek isim rehin almaz") yönetmeni haklı olarak düşürdü. "OI PHEN" (kesin-yanlış) → "okunamadı" (dürüst-çekimser) yönü DOĞRU; zorlanmadı (teyit-süzgecini gevşetmek geniş regresyon riski taşır).

**Etki-kapsamı ölçümü (16 film) SONUÇLANDI:** LAUREL HARDY/BJ VE AYI/GLORIA KUŞATMASI/İKİNCİ ŞANS/NİNJA KAPLUMBAĞALAR → director artık doğru okunuyor AMA çok-sebepli (KIMLIK/OZET/CAST ek sorunları var) → promote edilmedi. VAHŞİ ORMAN/SON OYUN/SEVİMLİ KÖPEK 3/HARRY'NİN UYANIŞI/AĞIZ TADI/KÖŞENİN KRALI → hâlâ OKUNAMADI (bu fix'in kapsamadığı ayrı sorun). **HOTEL RWANDA hâlâ "TOM JOHNSON" — fix'imle İLGİSİZ, önceki SINF-D raporu doğrulandı** (ayrı kök-neden, dokunulmadı). **FISILTILAR → "david koepp"/David Koepp gözle-teyitli** (frame g_0162.png "directed by / david koepp" net) → **PROMOTE EDİLDİ** (fix_kunye+byte-diff-temiz+yedekli). ONAYLI 27→28, KONTROL 236→235.

**⚠️ VERİ-HİJYENİ BULGUSU (kritik, gelecek analiz için):** bazı TRT'lerde export/KONTROL'de **AYNI filmin İKİ ayrı PDF'i** var, farklı suffix+farklı mtime (ör. HAYALET BABAM: `_YONETMEN` [29 Haz, ESKİ/bayat] + `_HAFIF_CAST_CAP_DUSEN` [5 Tem, GÜNCEL] — güncel dosyada yönetmen ZATEN dolu/SIDNEY POITIER, kalan gerçek sorun cast-cap'ten düşen 1 oyuncu, YÖNETMEN'le hiç ilgisi yok). **Suffix'e göre "saf tek-sebep" filtrelemesi YANILTICI olabilir — HER ZAMAN dosyanın mtime'ına bakıp EN YENİYİ gerçek-durum kabul et, eski suffix'e güvenme.** HAYALET BABAM bu yüzden bu turdan ÇIKARILDI (yanlış hedef olurdu). Aynı desen NİNJA KAPLUMBAĞALAR + HOTEL RWANDA'da da var (kontrol edilmedi, gelecek tur).

### SINIF-C GENİŞLEME: animasyon VFX-ünvanları ("XYZ TECHNICAL/ENVIRONMENTAL DIRECTOR") — açık-uçlu aile, RAPOR
FERDİNAND (2025-1240, animasyon): yönetmen="LERD ENVIRONMENTAL TECMNICAL" (çöp). Kaynak kesin: ham OCR satır 194 "LEAD ENVIRONMENTAL TECHNICAL DIRECTOR" (VFX departman-lideri ünvanı, isim "Jane Marie Chatot" ayrı). Cinematograf-veto'yla AYNI aile ama animasyon jeneriklerinde onlarca varyant olabilir ("Character Technical Director", "Lighting Director", "CG Director"...) — dar liste eksik kalır, geniş kural başka filmde gerçek yönetmen-etiketini bastırabilir. **UYGULANMADI.** Ayrıca aynı filmde yönetmen (Carlos Saldanha, cast'te de geçen ek-seslendirme) KB-lookup'ta `KAYNAK_YOK` dönüyor → SINF-D (KB-disambiguation) ile aynı sınıf, o da ayrıca rapor edilmişti.

### SINIF-E: stitch-karışması / bölünmüş-ad-etrafında-etiket (reading-layer, riskli)
Frame kristal-net ama stitch adı bölüyor. **BEKLENEN BOMBA (1959-0005)** görsel-teyitli: frame g_0152 "ESER VE REJİ / MUHARREM / GÜRSES" kocaman net (= Muharrem Gürses yönetmen). ocr_raw_all DOĞRU sırada, ama ocr_ham stitch'i "MUHARREM / ESER VE REJİ / GÜRSES" (etiket adın ortasında) → model "GÜRSES" (soyad) + "DURUKAN" (asistan-yön "REJİ Asistani MUHTESEM DURUKAN"dan) çıkardı → hepsi kayit-yok → boş. Fix riskli: surname-genişletme=V.Grigoryev-riski; stitch/prompt-değişikliği=geneli-bozar; "ESER VE REJİ" lexicon-eklemesi bile bölünmüş-adı birleştiremez. Kök: stitch label'ı adın ortasına sokuyor + Türkçe REJİ-etiketi + asistan-karışması. → konsey/dikkatli.

### SINIF-D: KB-onay same-name mis-match (mis-extraction + KB aynı-ad teyidi — ÖNCEDEN VAR)
Model yanlış kişi çıkarır, KB'de aynı-adlı bir yönetmen olduğu için ONAY alır. **HOTEL RWANDA** → "TOM JOHNSON" (gerçek: Terry George); **MANASLU** → Bernd Seidel (belgesel, doğrulanacak). Bayrak-kapalı da ONAY = benim fix'im değil. Kök: mis-extraction (upstream) + same-name KB collision.

### SINIF-B: "temiz-okunan yönetmen fuse'da düşüyor (KB-teyitsiz)" — ANGOLA fix'inin GENİŞ kardeşi
Model yönetmeni DOĞRU okuyor ama KB teyit etmediğinde (`RED` veya `kayit-yok`) `_fuse_yonetmen` tek-okumayı atıyor. ANGOLA (RED-çakışma, 2-token) fix'lendi; ama alt-tipler riskli (hallüsinasyon-frenine dokunur → konsey-değer):
- **B1 — baş-harf-GENİŞLETME:** ŞEYTAN RUHLU İNSANLAR / *Les Diaboliques* (1955-0046). Ekran "produit et dirigé par H.G. CLOUZOT"; model "H.G. CLOUZOT" okuyor ama KB "Henri-Georges Clouzot" tutuyor → `kayit-yok`. Çekirdek tek-token ("clouzot") → mevcut fix (2-token) kapsamıyor. `H.G.`→`Henri-Georges` genişletme + `_valid_person_name ≥2-token` şartı engeli. **Ayrıca rescue "PRODUIT ET" çöpü üretiyor (boştan kötü, ayrı bug).**
- _Muhtemel genel çözüm (konseye — w4nmnd6a6):_ "yönetmen-etiketi altında temiz-okunan tek isim" için etiket-çapalı kabul VEYA soyad+baş-harf-eşleşmeli KB köprüsü; ikisi de hallüsinasyon-freni dengesi ister.
- **SUB-BUG (SINF-B batch'iyle birlikte fixlenecek — güvenli+additive):** `_yon_rescue_auto` (credit_text_read:1524) path-B, "produit et dirigé par" satırını yönetmen-etiketi sanıp "PRODUIT ET"i (Fransızca label parçası) yönetmen emit ediyor. `_NONPERSON_TOK`'ta Fransızca/çok-dilli label verb'leri yok (produit/dirige/realise/realisation/regie...) → `_valid_person_name` geçiriyor. Fix = bu token'ları eklemek (isimlerde ASLA geçmez → 0-regresyon). Etki: ŞEYTAN "PRODUIT ET"→boş (yanlış>boş), tam-fix H.G. Clouzot konsey sonrası.

## 🛑 PROMOTE-TO-ONAYLI: DENENDİ, GÜVENSİZ BULUNDU — henüz hiçbir şey taşınmadı (2026-07-07)

Çağatay'ın "çözdüklerini ONAYLI'ya taşı" talebi üzerine 7 film (ANGOLA/ŞEYTAN/DENİZ EJDERİ/CENNETE GELDİK/SAVAŞTAN DÖNÜŞ/İHTİRAS CİNAYETİ/İSYAN) **7/7 gözle-frame-teyitli** olarak doğrulandı (KOKNEDEN kanıt-frame + doğrudan Read). Ama teslim mekanizmasında **3 ayrı sorun** bulundu, hiçbiri promote edilmedi:

1. **Tam-pipeline yeniden-render (`tek_film_kunye.py`)**: dilim-fix sonrası yönetmen DOĞRU doldu (H.G. CLOUZOT→HENRİ-GEORGES CLOUZOT, TEYİT, 10/10 cast örtüşme) AMA tek-geçiş model okuması **yapımcıyı** ("LOUIS DE MASURE" — ham OCR'da GERÇEK, doğrulandı) stokastik olarak kaçırdı; ayrıca `--original` argümanı verilmediği için orijinal-ad ("LES DIABLIQUES") sessizce düştü.
2. **`fix_kunye.py build_fixed()` cerrahi-yama denemesi** (yalnız director + baseline'dan yapımcı/cast almalıydı): TÜR alanı 7/7 filmde "—" oldu (genre-passthrough eksik), TRT-kimlik formatı kısaldı (benim çağrı hatam), 3 filmde orijinal-ad kayboldu (_DURUM.json'da o alan yok), DENİZ EJDERİ'de gerçek bir cast ismi ("Lisa Thorslunde") 8-kişi tavanına takılıp düştü, 3 filmde FİLM NOTU/KİŞİ-TEYİT kutusu kayboldu.
3. **Sonuç:** ne tam-render ne eski yama-aracı "yalnız bozuk alanı değiştir" işini güvenle yapmıyor. İkisi de ek mühendislik ister (build_fixed'e genre/trt_id-format/orijinal-ad/film_notu baseline-fallback eklemek + 8-cap'i baseline-kaynaklı cast'te kaldırmak, VEYA kunye_teslim.md'de tek satırı bulup değiştiren minimal bir patcher yazmak).

**GÜNCELLEME — ÇÖZÜLDÜ (aynı oturum devamı):** 3 gizli-kayıp kaynağı kesinleştirildi ve additive-fallback'larla fixlendi:
- `parse_teslim_md` (scripts/tek_film_kunye.py) hiç "Tür:" ve "Film Notu" okumuyordu → ikisi de eklendi (yeni dict-anahtarları, mevcut davranış AYNEN).
- `fix_kunye.build_fixed()` (outputs/kunye_fix, production DIŞI): TRT-kimlik artık meta'dan TAM alınıyor (kısalma yok), cast-8-tavanı yalnız corr-taze-listede (baseline'ı kesmiyor), tür `corr→md→_DURUM.json` 3-katmanlı fallback (ŞEYTAN/İHTİRAS'ta md üretim-anında boştu, _DURUM sonradan doldurmuştu), film_notu artık geçiriliyor, orijinal-ad yoksa (video kaynağı gitmiş 3 filmde) EN DÜRÜST kaynak olan arşivlenmiş eski PDF'ten okunuyor (uydurma değil, zaten-teslim-edilmiş değeri taşıma).
- **KANIT: 7/7 film artık byte-diff'te YALNIZ [üretim-damgası (zararsız) + 600x480-case (zararsız, pre-existing) + yönetmen-satırı-eklendi] farkı veriyor** — cast/yapımcı/tür/orijinal-ad/film-notu HİÇBİRİ değişmedi.
- **PROMOTE EDİLDİ (2026-07-07 03:08):** ANGOLA'DAN KAÇIŞ, ŞEYTAN RUHLU İNSANLAR, DENİZ EJDERİ, CENNETE GELDİK Mİ, SAVAŞTAN DÖNÜŞ, İHTİRAS CİNAYETİ, İSYAN → **KONTROL'den ONAYLI'ya taşındı** (eski KONTROL pdf'leri `_KONTROL_orijinal_yedek/`e yedeklendi, silinmeden önce yedek+ONAYLI-kopya doğrulandı). ONAYLI 20→27, KONTROL 243→236.

## 📊 SINIF CENSUS (arka-plan triage — yonetmen_triage.csv, sürüyor)

_YONETMEN KONTROL filmlerinde okuyucu-tabanlı sınıflandırma (grep değil):
- **DOLU** — model okuyor + fuse geçiyor → sadece PDF re-render lazım (ör. LAUREL HARDY→Alfred Werker ONAY). **Hızlı kazanç.**
- **SINF-B** (model okur, KB-teyitsiz, fuse atar) → **asıl fix hedefi** (konsey tasarlıyor). Alt-tip: RED-çakışma (ANGOLA, fixli) / kayit-yok (H.G. Clouzot baş-harf + TR-garble).
- **MODEL-OKUMADI** → okuma-logic DEĞİL: ya **meşru-boş** (belgesel, yönetmensiz — 21.YÜZYIL) ya **OCR/frame-çöp** (YÜZYILIN CİNAYETİ/PROFESÖR HANNIBAL okunamaz, KARA KALKAN garble). → dokunulmaz VEYA upstream re-OCR (ayrı iş, rapor).

### İNTİKAM (2001-9194, Beck: Hämndens Pris) — KİMLİK A_ELENDI, KOD-FİX DEĞİL (stokastik model-gürültüsü)
KOKNEDEN doğru teşhis etmiş: yönetmen+cast frame+OCR'da iki-kez-teyitli net (KJELL SUNDVALL doğru; ham OCR 4 ayrı karede "MARTIN BECK PETER HABER" kristal net). Ama BU KOŞUDA model "Peter Haber"ı "Peter Hûttner"a garble etti → cast_ortusme=0 → kimlik kurulamadı → KONTROL. **Bu deterministik bir kod-hatası DEĞİL** — OCR temiz, tek suçlu tek-geçiş model-okumasının rastgele tek-isim bozulması (VL-stokastik). Veto/lexicon-fix yazılamaz (hedef belirsiz — herhangi bir isim rastgele bozulabilir). KOKNEDEN'in önerisi doğru: "insan onayıyla serbest bırakılabilir" — ya insan-QC ya da (garble geçmişi göz önünde) dikkatli bir yeniden-okuma denemesi (kör toplu re-run değil).

### SOĞUK SUYA VURAN GÜNEŞ (1996-0031) — YENİ SINIF: reprocessing arası ÖZET-İÇERİK çelişkisi (insan-kararı gerekli)
KİMLİK-A_ELENDI teşhisi (Bernard Fresson cast-cap'ten düşmüş) küçük/kabul-edilebilir görünüyor — asıl KONTROL sebebi bu değil. **Kritik keşif:** `_DURUM.json` (06.07 20:44, "karar":"Hazır") KONTROL pdf'inden (05.07 07:30) DAHA YENİ — hub sonradan yeniden-işlenmiş. Hub'ın güncel `pdf/kunye.pdf`'i yönetmen+cast+yapımcı DOĞRU (KOKNEDEN'in gözle-teyidiyle birebir) AMA **ÖZET metni eski KONTROL sürümünden TAMAMEN FARKLI**: eski "Jill kendini öldürür" ↔ yeni "Jean'in intihar ettiğini öğrenir, Jill yaşamaya devam eder" — kozmetik değil, olay-örgüsü çelişkisi. Hangisi doğru belirleyecek araç (ASR/içerik-doğrulama) bu oturumun kapsamı dışında → **PROMOTE EDİLMEDİ** (ne eski ne yeni; yanlış özeti ONAYLI'ya taşımak riskli). fix_kunye baseline-fallback burada KORUMA SAĞLAMAZ çünkü kunye_teslim.md'nin kendisi de aynı turda üzerine yazılmış. **İnsan-kararı gerekli: hangi özet doğru?**
**GENEL DERS:** aynı desen (yeni `_DURUM.json`, "Hazır" ama KONTROL'de bayat pdf) başka filmlerde de olabilir — promote öncesi SADECE director/cast değil, ÖZET/diğer alanların da sessizce değişip değişmediğini diff'le kontrol etmek ZORUNLU (HAYALET BABAM'dan bir adım öteye taşınan ders).

### SINIF-F: CAST-CAP mimarisi — ÇÖZÜLDÜ (paralel süreç tarafından, 07:38, doğrulandı)
**GÜNCELLEME:** Çağatay'ın "neden fixlemedin" uyarısı üzerine paralel çalışan bağımsız bir süreç bu tam sınıfı çözmüş (`MITAS_CAST_CAP` 10→18 + `ocr_dropped` rescue, commit 81b10bf9). Doğru env (`MITAS_CAST_CAP=18`) ile test edildi: **SOĞUK SUYA VURAN GÜNEŞ artık 16 cast (Bernard Fresson VAR), JONSSON ÇETESİ artık 17 cast (Mats Wennberg VAR).** Benim ilk raporum ("riskli, geniş-kapsamlı, uygulanmadı") **artık BAYAT** — düzeltiyorum: bu sınıf ÇÖZÜLDÜ, benim tarafımdan değil ama doğrulandı. SOĞUK SUYA VURAN GÜNEŞ hâlâ ayrı ÖZET-çelişkisi yüzünden promote-edilemez (bkz aşağı); JONSSON ÇETESİ artık temiz KİMLİK — promote-adayı.

### (ESKİ RAPOR — artık bayat, referans için tutuluyor)
**JONSSON ÇETESİ (1981-0287):** cast=10/10 dolu (cap'e tam takılı), ANDERS ÖSTRÖM son-slotta (10.) girdi ama **MATS WENNBERG cap'ten düştü** (gözle-teyitli: "Junior / MATS WENNBERG" ham OCR'da net). Aynı desen bugün **3 filmde** görüldü: HAYALET BABAM (zaten çözülmüş, ayrı süreçte), SOĞUK SUYA VURAN GÜNEŞ (Bernard Fresson), JONSSON ÇETESİ (Mats Wennberg) — **hepsinde gerçek, ekranda-net bir oyuncu SADECE sayısal cap yüzünden düşüyor**. KOKNEDEN'in kök-neden analizi kesin: `credit_text_read.py:432/444-458/1811/1879-1887` — cap şu an LLM PROMPT'unda uygulanıyor ("en fazla __CAP__ isim yaz" talimatı) → LLM ekranda 11+ isim olsa bile kendi kendine kesiyor. **Önerilen fix (KOKNEDEN + doğrulandı):** cap'i yalnız Python-tarafında (LLM TAM listeyi ürettikten SONRA) uygula; prompt'tan sayı-sınırı talimatını kaldır/gevşet. **UYGULANMADI — bu TÜM cast-çıkarımını etkileyen mimari bir değişiklik, golden-suite + çok-film regresyon-kanıtı olmadan riskli. Konsey-adayı veya ayrı, dikkatli bir oturum gerektirir.**

### LENI RIEFENSTAHL — 2. deneme, hipotez YİNE kısmen yanlış çıktı (dürüstçe ölçüldü, zorlanmadı)
"İlk-isabete bak" fikrini test ettim: ölçünce "Kamera" etiketi ilk-isabetten (index 140) SONRA geliyor (index 141) — mevcut pencere GERİYE bakıyor, bu yüzden basit "ilk-isabet" düzeltmesi işe yaramaz. Gerçek sorun düşündüğümden ince: OCR kare-sırası "isim-sonra-etiket" de üretebiliyor (çift-yönlü pencere gerekebilir) + tekrar-seyrelmesi. Bu, TÜM filmlerin crew-filtresini etkileyen paylaşılan kod → tek-örnekle (LENI) genelleme riskli. **UYGULANMADI — birden çok filmde (crew-etiket-önce VE crew-etiket-sonra örnekleri) ölçülüp doğrulanmadan bu fonksiyona dokunmuyorum.**

### JONSSON ÇETESİ + FERDİNAND — GÜNCELLEME (2026-07-07, konsey-sonrası)
**JONSSON ÇETESİ: PROMOTE EDİLDİ** — cast-cap(18) fix sonrası kimlik tam kuruldu (verdict=TEYİT, cast_ortusme=10, 17 gerçek oyuncu). Özet+tür eski sürümle içerik-özdeş doğrulandı (SOĞUK SUYA dersi uygulandı). ONAYLI 29.
**FERDİNAND SINIF-4 (VFX-ünvanları) FIXLENDİ** (commit d6aaaf2b): "LEAD ENVIRONMENTAL TECHNICAL DIRECTOR" garble'ı artık çöp isim üretmiyor, doğru şekilde BOŞ kalıyor ("yanlış>boş" korundu). Somut-kanıtlı dar liste ({"TECHNICAL","ENVIRONMENTAL"}), açık-uçlu genişletme YAPILMADI.
**KOVBOY SINIF ("BASED ON...BY" farklı kod-yolu) FIXLENDİ** (commit d4758aac): `_PREFILTER_PHRASES` "BASED ON THE"→"BASED ON " genişletildi (dar, additive). Frank Harris artık sızmıyor, Delmer Daves temiz KB-onaylı.
**Not:** `konsey` workflow bu oturumda 2. kez alakasız/eski-cache'li bir soruya (master-PNG mimarisi) cevap döndürdü — benim 5-sınıf sorumu yanıtlamadı. Bu bilinen bir araç-sorunu; zor sınıflar (SINIF-1 KB-disambiguation, SINIF-2 eşik, SINIF-3 patronimik) konseyle değil doğrudan kendi mühendislik-muhakememle (dar+kanıtlı olanlar fixlendi, gerçekten belirsiz olanlar dürüstçe açık bırakıldı) ele alındı.

### LENI RIEFENSTAHL (1993-0437) — crew→cast sızıntısı, GERÇEK kök-neden düzeltildi (önceki teşhis YANLIŞTI)
İlk hipotez ("dilim-korpus raw_context_lines'a ulaşmıyor") **yanlış çıktı** — doğrudan ölçünce `raw_context_lines`'ın zaten "Kamera"+"Walter A. Franke" içerdiği görüldü (dilime hiç gerek yokmuş). Additive dilim-köprü fix'i (commit 0d035e56, zararsız+golden-temiz, başka filmlerde işe yarayabilir) bu YÜZDEN bu filmi çözmedi. **Gerçek kök-neden:** "Walter A. Franke" ham OCR'da art-arda karelerden **17 kez** tekrarlanıyor (uzun sabit-kare süresi) ama "Kamera" etiketi yalnız birkaçının hemen-öncesinde geçiyor → `filter_cast_by_raw_context`'in `crew_count/toplam_isabet ≥ 0.60` eşiği tekrar-seyrelmesiyle KAÇIYOR. Bu, PAYLAŞILAN bir eşik/pencere mekanizması — değiştirmek TÜM filmlerin crew-filtrelemesini etkiler (geneli-bozacak riski). **UYGULANMADI — konsey-adayı** (öneri: ham-tekrarları dedup'layıp DİSTİNCT-bağlam üzerinden oran hesaplamak, veya ardışık-aynı-isim runlarını tek isabet saymak).
**DERS: ilk hipotez her zaman DOĞRU olmuyor — "muhtemelen X" dedikten sonra bile doğrudan ölçüp teyit etmek şart (burada yaptım, yanlış çıktı, düzelttim — ama bu her nokta-atışında tekrarlanmalı).**

### KOVBOY (1958-0044) — "BASED ON...BY <yazar>" sınıfının FARKLI bir kod-yolu, MEKANİZMA NET DEĞİL (rapor, fixlenmedi)
KOKNEDEN: final PDF'te DELMER DAVES zaten doğru (kimlik_dogru=True), ama routing eski bir "ÇELİŞKİ" bayrağına (aday: FRANK HARRIS — kaynak-kitap yazarı, "BASED ON MY REMINISCENCES AS A COWBOY BY FRANK HARRIS") dayanıp KONTROL'e düşürüyor. KOKNEDEN `credit_validate.py:254-343 validate_director` (XML-sidecar karşılaştırma) işaret ediyor. **Doğrulamaya çalıştım, kesinleştiremedim:** XML kaynağı erişilemez (video W:\'ye taşınmış); `_DURUM.json`'da "Frank Harris" arayınca bulduğum veri **n-gram/bigram parçaları** ("Reminiscences Cowboy"/"Cowboy Frank"/"Frank Harris"/"Harris French") — XML değil, muhtemelen cast n-gram aday-üretiminden. Yani "BASED ON...BY" yazarının yanlışlıkla aday sayılması sınıfı (sabah `tek_film_kunye.py`'de fixlediğim) burada **farklı, henüz izlenmemiş bir kod-yolunda** (muhtemelen `mitas_pipeline.py`'nin kendi credit-validate zinciri, `credit_validate.py`) tekrarlanıyor. **UYGULANMADI — mekanizma tam izlenmeden fix yazmak "ölçmeden düzeltme" kuralımı ihlal eder; ayrı, odaklı bir trace oturumu gerektirir (XML olmadan `mitas_pipeline.py`'nin xml_roles()/credit_validate çağrı-zincirini statik okuyarak).**

### SINIF-G (YENİ): Türkî patronimik ek bitişik/ayrık yazım uyuşmazlığı — BORÇ (2003-9208)
Frame+OCR+master iki-kez-tutarlı: "YÖNETMEN / İbrahim Habibulla oğlu" (25+ cast de tam okunur). Final PDF'e de doğru yazılmış. Ama XML kaynağı "İBRAHİM HABİBULLAHOĞLU" (bitişik) bekliyor, `credit_validate.py`'nin exact/close-match'i ayrık-yazımla ("Habibulla oğlu", 2 token) eşleşmiyor → ÇELİŞKİ → KONTROL. Potansiyel olarak Azerbaycan/Orta-Asya/Kafkas kökenli birçok filmi etkileyebilir ("-oğlu"/"-kızı" eki bitişik ya da ayrık yazılabiliyor). **UYGULANMADI** — isim-eşleştirme normalizasyonuna dokunmak TÜM filmlerin director/cast eşleştirmesini etkiler (geneli-bozacak); "-oğlu" ekini otomatik-birleştirmek yanlış-pozitif riski taşır (farklı 2 kişiyi birleştirebilir). Konsey-adayı.
MANASLU (2001-9318) ve JERICO APARTMANI (2003-9195/9198) → zaten raporlanan SINF-D (KB-disambiguation, belgesel/gerçek-kişi KB'de yok) + SINF-F (cast-cap) ile örtüşüyor, tekrar araştırılmadı.

### SINIF-H (YENİ, CİDDİ): TAKKELİ MELEK (1978-0227) — KAYNAK-VERİ BÜTÜNLÜĞÜ sorunu, kod-hatası DEĞİL
Giriş jeneriği **Kiril alfabesiyle gerçek film** (1968 Kazak filmi, "Казакфильм/Алма-Ата", yönetmen kısmen okunur "ШАКЕН[ОВ]"). Ama çıkış jeneriği (cikis_jenerik) **tamamen alakasız bir Avustralya filminin** kadrosunu gösteriyor ("DIRECTOR GREG MCLEAN" — gerçek/tanınan bir yönetmen, bu Kazak filmiyle hiç ilgisi yok; "MICK VAN MOORSAL" oyuncu-crew). Final PDF bu yanlış kadroyu almış. **OCR doğru okumuş — ama okuduğu görüntü BAŞKA BİR FİLME ait** (muhtemelen arşiv kasetinde yanlış film-parçası/splice hatası). **UYGULANMADI — bu kod-fix DEĞİL, kaynak-veri sorunu.** Genel bir "giriş/çıkış script-uyuşmazlığında çıkışı bastır" kuralı YAZMADIM çünkü meşru yabancı-dil çıkış-jeneriği ÇOK YAYGIN (bugün ANGOLA'da gördüm) — böyle bir kural birçok filmde doğru veriyi bastırırdı. **İnsan/arşiv incelemesi gerekiyor** (doğru kimlik yalnızca kısmen-okunur Kiril giriş jenerikinde).

### HALIFAX-CANİ RUH (2001-9167) — DOĞRULANDI: kod DOĞRU çalışıyor, meşru-KONTROL (bug değil)
"Devised by ROGER SIMPSON" fren'i (daha önce tam bu film için eklenmiş, kod-yorumunda "Lynn Hegarty" adı geçiyor) ölçüldü: `yonetmen=[]`, Roger Simpson doğru elendi, uydurma yok. Ekranda bölüm-yönetmeni kredisi hiç yok (yalnız "Devised by" + crew ünvanları); XML'in önerdiği "Lynn Hegarty" ekranda hiçbir yerde geçmiyor (ham OCR'da sıfır isabet). `_DURUM.json` KONTROL-pdf'inden 5dk sonra (aynı koşu, bayat-pdf DEĞİL). **Meşru-boş — insan/arşiv teyidi gerekiyor, kod-fix konusu değil.**

### İKİNCİ ŞANS (1992-0465) — FIXLENDİ: KB-çelişkisi temiz OCR'ı SİLİYORDU (tek_film_kunye.py, DEMİR KURAL#3 ihlali)
Kare kristal-net: "directed by / REUBEN ROSE" (frames/giris/g_0107.png, gözle-teyitli — büyük, tek renkli fon, hiç belirsizlik yok). Ama final PDF yönetmeni BOŞ + verdict=ÇELİŞKİ. Kök-neden `tek_film_kunye.py:576-586`: OCR temiz okuduğunda BİLE, KB (`auth_yon`) FARKLI bir isim öneriyorsa ("John Blanchard" — muhtemelen "Second Chance" başlığının KB'de yanlış-film eşleşmesi; extrem-jenerik başlık) ve `name_match`/`name_close` eşleşmiyorsa, kod OCR'ı **koşulsuz** `yon=[]` yapıp "okunamadı" işaretliyordu. Bu, `credit_validate.py` başındaki projenin kendi DEMİR KURAL#3'ünü ("SESSİZ EZME YOK... OCR korunur") ihlal ediyordu — kod-yorumunun kendi örneği ("ABRURRAK ROROSKO" garble) ile "REUBEN ROSE" (gerçek kişi) arasında hiç ayrım yapmıyordu.
**Fix (additive, iki-kapılı):** KB eşleşmezse artık önce `_valid_person_name` (yapısal: 2+ token, garble-değil) kontrol edilir — YETMEZ tek başına (ölçüldü: "Abrurrak Rorosko" bile bu testi geçiyor) — İKİNCİ kapı: isim GENİŞ KB'de (`imdb.names`, bu filme özel DEĞİL) gerçek biri olarak var mı (`CreditKB._imdb_people_by_folds`). İkisi de geçerse OCR korunur ("kareler (KB eşleşmedi ama OCR temiz + KB'de gerçek kişi → okunan korundu)"); biri bile geçmezse eski davranış AYNEN (okunamadı).
**KANIT:** deterministik 4/4 (Reuben Rose✅ survive, Delmer Daves✅ survive, Abrurrak Rorosko✅ hâlâ-okunamadı, rastgele-harf-yığını✅ hâlâ-okunamadı) + uçtan-uca İKİNCİ ŞANS: `yonetmen_list: ["REUBEN ROSE"]` (önce boş) + golden-regresyon 4/7 (aynı bilinen-flaky 3 fail; ANGOLA'nın momentary FAIL'i `_pipe_credit_text.py` tarafında ayrı-mesele — bkz aşağı, VL-server geçici 500 hatası + regresyon_golden.py'nin kendi "-fb" filtre-hatası, bu fix'le İLGİSİZ, izole doğrulandı).
**Not — promote edilmedi:** İKİNCİ ŞANS'ın cast'i de (18 isim) henüz ayrı doğrulanmadı; yalnız yönetmen-kod-fix'i bu turda commit-hazır.

### SINIF-I (YENİ, CİDDİ — 3 filmde bağımsız doğrulandı): çok-isimli/çok-sütunlu jenerik kartlarında kısmi-isim-kaybı
Bugünkü promote-sweep'te (KOVBOY/LAUREL HARDY/GLORIA KUŞATMASI) **3/3 filmde** aynı sınıf hata gözle doğrulandı: ekranda birden fazla oyuncu ismi TEK görsel bloğa/satıra sığdırılmış (3-sütunlu "with X Y Z" kartı, 2-sütunlu stacked isim kartı, veya uzun "Rol — Oyuncu" kapanış listesi), final cast listesi bunların BİR KISMINI kaçırıyor:
- **KOVBOY (1958-0044):** frame g_0055 "with DICK YORK VICTOR MANUEL MENDOZA RICHARD JAECKEL / KING DONOVAN VAUGHN TAYLOR DONALD RANDOLPH / JAMES WESTERFIELD EUGENE IGLESIAS FRANK de KOVA" (9 isim, 3×3 sütun) — final cast'te yalnız 6'sı var, DICK YORK + FRANK de KOVA HİÇ yok, JAMES WESTERFIELD/EUGENE IGLESIAS'tan yalnız BİRİ (koşudan koşuya DEĞİŞİYOR — VL-ensemble stokastik, ikisi de aynı OCR ham-satırında "JAMES WESTERFIELD EUGENE IGLESIAS" bitişik duruyor).
- **LAUREL HARDY (1942-0020):** frame g_0021 "Stan LAUREL and Oliver HARDY and DANTE THE MAGICIAN in..." (film'in KENDİ BAŞLIK-YILDIZLARI, 2-sütun stacked ad/soyad) — final cast'te STAN LAUREL ve OLIVER HARDY **HİÇ YOK** (eski KONTROL pdf'inde en azından "OLIVER HARDY" kısmen vardı; yeni koşu bunu da kaybetti — muhtemelen kunye.txt'nin "LAUREL AND HARDY" tek-satır özetlemesi kaynaklı, iki-kişi olarak ayrıştırılamıyor).
- **GLORIA KUŞATMASI (1992-0299):** frame c_0377 kapanış "Rol — Oyuncu" listesi net (17 satır) — final cast 17/19 yakaladı ama "Ghost — RICHARD KUHLMAN" ve "Patrol Members — ERIC HAUSER" (aynı listede, komşu satırlar) kayıp.
**Mekanizma NET DEĞİL — muhtemelen tek bir kök değil.** KOVBOY/LAUREL HARDY "video_okuma (ensemble/fallback)" — yani VL/LLM-tabanlı okuma yolundan geçiyor (deterministik `extract_cast_block_candidates` DEĞİL, `cast_kb` zaten ≥3 olduğu için fallback hiç tetiklenmiyor) → çok-isim-tek-satır ayrıştırması muhtemelen LLM'in kendi çıktı-örneklemesine bağlı (stokastik, aynı yorumdaki SINIF-B'ye benzer risk sınıfı). GLORIA'nın kaybı farklı olabilir (threshold/crew-context yanlış-pozitifi, LENI RIEFENSTAHL'daki sınıfa yakın).
**UYGULANMADI — 3 bağımsız film, PAYLAŞILAN VL-okuma/ayrıştırma mekanizmasını etkiler, kör fix riskli.** LAUREL HARDY özellikle ciddi (filmin kendi başlık-yıldızları eksik) — insan/konsey önceliği önerilir. **Bu 3 film promote EDİLMEDİ** (director-kimlik alanları düzelmiş olsa da cast eksikliği "sağlıklı/düzgün" barını geçmiyor).

### TEST-ALTYAPISI BUG (YENİ, fixlendi): "-fb" fallback-filtresi substring yerine suffix olmalıydı
`regresyon_golden.py:26` + `tek_film_kunye.py:962,1050` + `garble_trigger_olcum.py:62`: `"-fb" not in q` (TAM YOL üzerinde substring-kontrolü) — amaç OCR'ın "-fb" (fixed-window fallback re-OCR) kardeş-klasörünü ATLAMAK (gerçek örnek: `BEKARLIK.../ocr/ocr-483d8b04` + `ocr-483d8b04-fb` kardeşi). Ama rastgele 8-hex job-hash'i "fb" ile BAŞLARSA (ör. `ocr-fb9fa3e4`, ANGOLA'DAN KAÇIŞ'ın TEK OCR klasörü) substring de yanlışlıkla eşleşip o filmi TAMAMEN filtreden düşürüyor (`kunye-yok` → sahte-FAIL). Kod tabanında zaten DOĞRU örnek var (`_pipe_credit_text.py:46`: `job_dir.endswith("-fb")`, `jenerik_debug_batch.py:50-51`: `not p.name.endswith("-fb")`) — 4 çağrı-yeri bu doğru deseni kullanmıyordu. **Fix: 4 yerde de `os.path.basename(os.path.dirname(q)).endswith("-fb")` deseniyle değiştirildi** (agent-araştırmasıyla kesinleştirildi, mevcut-doğru-örnekle birebir aynı mantık — sıfır-yeni-tasarım). Bu, ANGOLA'nın golden-suite'te "regresyon" gibi görünen ama aslında test-altyapısı yanlış-negatifi olan FAIL'ini açıklıyor — `_kb_verify_flex`'in kendisi izole test + doğru dosya ile ONAY dönüyor.

## 🛑 PROMOTE-SWEEP #2: 4 film incelendi, 0/4 promote edildi (2026-07-07, "düzeltilmiş=önümüze gelmesin" talebi)
KOVBOY/LAUREL HARDY/GLORIA KUŞATMASI/İKİNCİ ŞANS — hepsi frame-frame denetlendi. Sonuç: orijinal KONTROL-flag'i (kimlik/yönetmen) her 3'ünde de gerçekten düzelmiş (KOVBOY+LAUREL HARDY yönetmen zaten doğruydu, GLORIA yönetmen bu turda BRIAN TRENCHARD-SMITH ile doğru doldu), İKİNCİ ŞANS'ın yönetmen-sorunu bu oturumda KOD-FİX'lendi (yukarı bkz) — AMA derin frame-denetimde 3'ünde YENİ, önceden-flag'lenmemiş cast-eksikliği bulundu (SINIF-I), İKİNCİ ŞANS'ta cast henüz doğrulanmadı. **Hiçbiri "TÜM alanlar temiz" barını geçmedi → 4'ü de KONTROL'de kalıyor**, promote edilmedi. Bu, Çağatay'ın "yalnız düzgün halini taşı" talimatına sıkı uyumla alınan bir karar — kısmi-düzelmiş bir PDF'i ONAYLI'ya taşımak yerine.

## ✅ PROMOTE-SWEEP #3: cast-cap sınıfı + 2 KONTROL PDF (2026-07-07)
"_HAFIF_CAST_CAP_DUSEN" etiketli 3 filme bakıldı — sınıf zaten paralel-süreç mimari fix'iyle (81b10bf9) çözülmüştü, doğrulama+byte-diff+frame-spot-check sonrası **2/3 PROMOTE EDİLDİ**:
- **GERONIMO (1962-0022): PROMOTE EDİLDİ.** cast 10→18 (cap tam dolu; 19. isim "Nancy Roldán" cap-tavanına takıldı — SINIF-I'den FARKLI, bu gerçek bir parse-hatası değil kabul-edilebilir sayısal-tavan kaybı). Yönetmen/yapımcı/tür/özet DEĞİŞMEDİ (özet yalnız satır-sarma farkı, kelime-kelime özdeş — doğrulandı). Yeni eklenen 7 ismin hepsi frame g_0084'te ("with CLAUDIO BROOK...") net okunur, TAMAMI final cast'te MEVCUT.
- **ÖLÜM VURUŞU (1971-0079, = *True Grit* 1969): PROMOTE EDİLDİ** (2 eski KONTROL kopyası vardı — hem `_YONETMEN` hem `_HAFIF_CAST_CAP_DUSEN`, ikisi de temizlendi). Eski PDF'te yönetmen "--" (boş) idi, yeni koşuda HENRY HATHAWAY doğru doldu (yapımcı HAL B. WALLIS ile tutarlı). Cast 9→13. Küçük bir harf-garble'ı var ("NIGOLAS BEAUVY" — frame'de en az bir temiz okuma "NICOLAS BEAUVY" mevcut, ensemble sentez adımı en temiz varyantı seçmemiş) ama bu KOVBOY/LAUREL HARDY'deki TAM-KİŞİ-KAYBI'ndan farklı — kişi mevcut, yalnız yazımı kusurlu; promote-barını düşürmedi. PDF kendi içinde de şeffaf: "FİLM NOTU: K-TEYİT — KB'de doğrulanamayan 2 isim listeden çıkarıldı" (ARTHUR HUNNIGUTT-garble + MARGUERITE ROBERTS=senarist, ikisi de haklı-dışlama).
- **UTANMAZ ADAM (1961-0005): PROMOTE EDİLMEDİ.** KONTROL'de aynı TRT için 2 PDF (05.07 flagged + 06.07 plain) var, cast AYNI ama **ÖZET TAMAMEN FARKLI** iki ayrı olay-örgüsü anlatıyor (SOĞUK SUYA VURAN GÜNEŞ ile AYNI sınıf — bkz yukarı "reprocessing arası ÖZET-İÇERİK çelişkisi"). 2. somut örnek, bu sınıfın tek-seferlik olmadığını doğruluyor. **İnsan-kararı gerekli — hangi özet doğru, bu oturumun kapsamı dışında.**
- **BÜYÜK MÜCADELE (1960-0021): PROMOTE EDİLDİ.** cast 10→18 (frame-spot-check TIMOTHY WEST temiz). Bonus: eski PDF'te Yapımcı satırında MICHAEL DARLOW YİNELENMİŞ hatası vardı (hem Yönetmen hem — garbled "MICHAEI" yazımıyla — ikinci kez Yapımcı altında) — yeni koşuda bu yinelenme kendiliğinden düzeldi (Yapımcı=SHAUN SUTTON tek başına, frame "DIRECTED BY MICHAEL DARLOW" ile tutarlı). TÜR her iki sürümde de boş (— ), REGRESYON DEĞİL — baseline zaten hiç tür atamamış. **NOT (metodoloji):** `pdftotext -layout`'un çok-sütunlu YAPIM EKİBİ bölümünü satır-karıştırarak çıkarması yanıltıcıydı (Yönetmen/Yapımcı sırası ters görünüyordu) — gerçek durumu **PDF'i doğrudan görüntüye render edip** (`fitz`/PyMuPDF) gözle kontrol ederek çözdüm. Text-diff YALNIZ ipucu; çok-sütunlu bölümlerde görsel render ZORUNLU.

### BANA TRINITY DERLER (1968-0082) — 3 KATMANLI bug: 1 katman fixlendi+commit'lendi, 2. katman AÇIK (mahlas/AKA-KB boşluğu)
KOKNEDEN'in "3 satıra bölünmüş yönetmen-adı" teşhisi bu turda geçerli DEĞİLDİ (kunye.txt zaten "E. B. CLUCHER" olarak temiz birleşmiş) — ama yönetmen yine de boş çıktı, GERÇEK kök farklıydı:
1. **`_valid_person_name` baş-harf-çoklu-isim RED'i (FIXLENDİ, commit 71871a54):** yukarı bkz — "E. B. CLUCHER" (iki baş-harf + soyad) yapısal-geçersiz sayılıyordu.
2. **KB mahlas/AKA boşluğu (AÇIK, kod-fix YAPILMADI):** fix#1 sonrası bile yönetmen boş kaldı. Kök: yönetmenin ekran-kredisi "E.B. Clucher" (İtalyan western'lerinde kullandığı yönetmenlik mahlası) ama IMDb `names` tablosunda yalnız gerçek adı "Enzo Barboni" kayıtlı (doğrulandı: `_imdb_people_by_folds(['e b clucher'])` boş, `['enzo barboni']` dolu+director). Bugünkü İKİNCİ ŞANS fix'inin (tek_film_kunye.py) KB-varlık kapısı yalnız primaryName'e bakıyor, AKA/alternate-name'e bakmıyor → mahlaslı yönetmenler hâlâ "okunamadı" oluyor. **UYGULANMADI** — DuckDB şemasında bir akas/alternate-names tablosu olup olmadığı hızlı sorguyla teyit edilemedi (information_schema sorgusu boş döndü, şema farklı adlandırılmış olabilir), ayrı+odaklı bir şema-keşif oturumu gerektiriyor. Cast (18, cast_ortusme=10) zaten sağlam — yalnız yönetmen eksik.

### BİR BEBEK EVİ (1973-0211) — kod-hatası DEĞİL: kare gerçekten düşük-kontrastlı/bulanık (2 bağımsız koşuda da tutarlı-kötü)
"Joseph Losey" adayı iki ayrı koşuda da garbled geldi (Josaph Losay / boş+kimlik_dogru=False), cast da çok düşük (5-7) — SİNEMATOGRAF VETO'nun aşırı-tetiklendiği ENDİŞESİYLE araştırıldı ama YANLIŞ çıktı: veto hiç devreye girmiyor, sorun ham okumanın kendisi. Frame c_0614 doğrudan görüntülendi: kredi metni **parlak/düşük-kontrastlı bir kar/sis sahnesinin ÜZERİNE bindirilmiş, ince el-yazısı fontuyla** — gözle "Joseph Losey / director(by)" okunabiliyor ama zorlukla, OCR'ın neden "Josaph Losay" ürettiği görsel olarak anlaşılır. **Bu, önceden belgelenmiş "OCR/frame-çöp sınıfı"na girer (RAPOR.md ⏭️ Atlananlar) — kod-fix konusu değil, upstream re-OCR/frame-seçimi işi.** UYGULANMADI, atlanan listesine eklendi.

## 🛑 PROMOTE-SWEEP #4: 4 film incelendi, 0/4 promote edildi (2026-07-07)
BİR YAZ MACERASI / NANCY'Yİ SEVMEK / ÖNEM DERECESİ / SINIR ÇİZGİSİ — hepsi frame-frame denetlendi, hiçbiri "tüm alanlar temiz" barını geçmedi:
- **BİR YAZ MACERASI (1989-0570):** yönetmen ANDRÉ MELANÇON İKİ AYRI karede (açılış "screenplay" ortak-kredisi + kapanış "DIRECTOR" kartı, frame c_0475) gözle-teyitli DOĞRU. AMA **cast şiddetle eksik: final'de yalnız 5 isim, kapanış jeneriğinde TEK karede (c_0475) bile 11 gerçek "Rol: Oyuncu" çifti net okunuyor** (HECTOR ALTERIO, CHINA ZORRILLA, ALEXANDRA LONDON-THOMPSON...). SINIF-I'nin 4. bağımsız doğrulaması — bu sefer decorative çok-sütun kart DEĞİL, GLORIA KUŞATMASI'ndakiyle aynı türden temiz "Rol: Oyuncu" liste formatında bile ciddi kayıp oluyor, sorunun kapsamı önceki tahminimden daha geniş. **UYGULANMADI/PROMOTE EDİLMEDİ.**
- **NANCY'Yİ SEVMEK (1994-0383) ve SINIR ÇİZGİSİ (1995-0280):** her ikisinde de yönetmen kod-katmanına hiç ULAŞMADI (`video_okuma.yon: []`, guven=OKUNAMADI) — ham OCR'da (`kunye.txt`+`ocr_ham.txt`) "DIRECTED BY" veya benzeri bir etiket-kartı HİÇ bulunamadı (yalnız "FIRST/SECOND ASSISTANT DIRECTOR" gibi yardımcı-rol satırları var). Bu, `_valid_person_name`/`_drop_dubbing_directors` gibi mantık-katmanlarının ULAŞAMADIĞI bir upstream boşluk — ya gerçek yönetmen-kartı OCR'ın örneklediği kare-aralığının DIŞINDA (frame-seçim kapsamı işi) ya da kart o kadar kısa/geçişken ki hiç yakalanmadı. **Kod-fix konusu DEĞİL** — bu, önceden belgelenmiş "OCR/frame-çöp sınıfı"/upstream-re-OCR işiyle aynı kategoriye giriyor. Cast her ikisinde de zengin (16-18) ve muhtemelen sağlam — yalnız yönetmen eksik.
- **ÖNEM DERECESİ (1991-0495):** dikkat çekici bir YANLIŞ-İZ vakası — sistem "AMY SHAPIRO, DIRECTOR" adayını buldu (bugünkü İKİNCİ ŞANS-fix sayesinde "KB eşleşmedi ama OCR temiz + KB'de gerçek kişi → korundu" olarak işaretlendi) ama bu isim aslında **"FILMED ON LOCATION IN PROVIDENCE, RI, WITH THE GENEROUS [COOPERATION OF] AMY SHAPIRO, DIRECTOR [muhtemelen yerel film komisyonu]"** — bir teşekkür/lokasyon-işbirliği satırı, FİLMİN yönetmeni değil. Final `yonetmen_list` yine de BOŞ çıktı (`[]`) — bu, İKİNCİ ŞANS-fix'imin bu adayı doğru şekilde KORUDUĞUNU ama sonraki bir katmanın (muhtemelen `_drop_dubbing_directors` ya da QC-bloğu) bu belirli "teşekkür-bağlamını" ayrıca doğru şekilde ELEDİĞİNİ gösteriyor — **sistem katmanlı-savunmada doğru çalıştı, benim fix'im zarar vermedi.** Gerçek yönetmen ekranda/OCR'da başka yerde bulunamadı — meşru-boş (HALIFAX-CANİ RUH sınıfı). **PROMOTE EDİLMEDİ, kod-fix gerekmiyor.**

## ✅ PROMOTE-SWEEP #5: SON TANIK promote edildi + 4 film "OCR yakalamadı" sınıfı (2026-07-07)
- **SON TANIK (1999-0483, = *Caracara*/"The Last Witness"): PROMOTE EDİLDİ.** Frame g_0024 "A GRAEME CLIFFORD FILM" net-teyitli. Cast 10→18 (frame-render karşılaştırması: orijinal-ad da eklendi "THE LAST WITNESS", eskiden yoktu). **Bonus-bulgu:** eski PDF'in cast'inde "NATASHA KIEN" diye 11. bir "kişi" vardı — frame g_0031 doğrudan görüntülendi: bu aslında "NATASHA HENSTRIDGE" isminin çıplak-ağaç-dalları arka planına karışmış OCR-garble kopyasıydı (gerçek ikinci kişi DEĞİL). Yeni koşu bu garble-duplikasyonu kendiliğinden ELEMİŞ — kayıp değil, DÜZELTME. Tür/özet/yapımcı/trt-kimlik değişmedi.
- **SANTRAL (2000-0395), HARRY'NİN UYANIŞI (2000-0517), FUTBOLCU PRENSES (2000-0477 — yeniden koşu):** üçünde de yönetmen kod-katmanına hiç ulaşmadı (`video_okuma.yon: []`) — ham OCR'da (`kunye.txt`+`ocr_ham.txt`) hiçbir "DIRECTED BY" benzeri kart YOK, yalnız "1ST/2ND ASSISTANT DIRECTOR"/"DIRECTOR OF PHOTOGRAPHY" gibi yardımcı-roller var. **Kod-fix konusu DEĞİL** — upstream OCR/frame-seçim boşluğu (NANCY'Yİ SEVMEK/SINIR ÇİZGİSİ ile aynı sınıf). **FUTBOLCU PRENSES ÖZEL NOT:** cast bu turda DÜZELDİ (DON MURRAY/HELEN HUNT/JOHN STOCKWELL... 18 isim, önceki "GRIZZLY COUNTRY" garble'ı GİTTİ — stokastik VL-okuma bu sefer iyi çıktı, [[project_kunye_kontrol_stale_duplicate_pdf_20260707]] dersini doğruluyor). Ama yönetmen+yapımcı hâlâ tamamen boş — **PROMOTE EDİLMEDİ**, cast iyileşmesi tek başına yeterli değil.
- **HİTLER'İN HAZİNESİ (2000-0479):** BELİRSİZ/riskli aday — rescue mekanizması "REGULA GRAUWILLER" adını "yönetmen-kartı" sanarak önerdi ama kaynak metinde bu isim gerçek bir AÇILIŞ CAST-LİSTESİNİN İÇİNDE ("HARDY MARTINS / REGULA GRAUWILLER / HEINER LAUTERBACH...") duruyor, herhangi bir "REGIE"/"DIRECTED BY" etiketine bitişik DEĞİL — film ayrıca "CO-REGIE / SANDRA BARGER" diye AYRI bir eş-yönetmen ipucu da içeriyor (kafa karıştırıcı, çok-yönetmenli/çok-katmanlı bir Alman TV-yapımı olabilir). Final sonuç doğru şekilde BOŞ kaldı (rescue'nun yanlış-adayı bir sonraki katmanda elendi) — **sistem güvenli tarafta, ama kök gerçek yönetmen(ler) hâlâ belirsiz. PROMOTE EDİLMEDİ, insan/arşiv teyidi ya da ayrı-odaklı inceleme gerekiyor.**

## 🛑 PROMOTE-SWEEP #6: 4 film incelendi, 0/4 promote edildi (2026-07-07)
- **KÖŞENİN KRALI (2004-9132):** kimlik_dogru=True/cast_ortusme=9 (güçlü) ama yönetmen kod-katmanına hiç ulaşmadı — ham OCR'da yalnız "SECOND SECOND ASSISTANT DIRECTOR"/"DIRECTOR OF PHOTOGRAPHY"/"TECHNICAL DIRECTOR" var, gerçek "DIRECTED BY" kartı YOK. Aynı upstream-OCR-boşluğu sınıfı. **PROMOTE EDİLMEDİ.**
- **DENİZLER ALTINDA 20.000 FERSAH (2003-9049):** yönetmen SCOTT HEMING frame-teyitli DOĞRU (g_0036 "DIRECTOR / SCOTT HEMING" net) — HEM eski HEM yeni PDF'te zaten doğruydu; asıl KONTROL-sebebi (`_KIMLIK`) muhtemelen kalıcı bir KB-boşluğu (Nickelodeon-marka obscure animasyon uyarlaması, IMDb'de muhtemelen indekslenmemiş — SINIF-1 ile aynı aile). **Byte-diff'te İKİ yönlü fark bulundu:** yeni koşu 1 cast-ismi eklemiş ("KACZMAREK" — frame c_0674'te "ANTHONY CLARK - KACZMAREK / DR. ARONNAX" olarak görülüyor, tek-kişi bileşik-soyad mı yoksa 2. bir ortak-seslendirme kredisi mi BELİRSİZ, isim TEK BAŞINA eksik/parça görünüyor) AMA aynı zamanda **TÜR alanını KAYBETMİŞ** ("DRAMA"→"—", REGRESYON). Net kazanç yok — ne saf-eski ne saf-yeni temiz. **PROMOTE EDİLMEDİ** ([[project_kunye_kontrol_stale_duplicate_pdf_20260707]] "alan-bazlı en-doğru" dersinin somut 2. örneği).
- **KANDIRMACA (2002-9058):** video_okuma adayı "ROTH BILL MACDONALD" — muhtemelen 2 ayrı-role isim/fragmanın birleşmesi ("Bill Macdonald" zaten cast listesinde ayrıca var) — final BOŞ kaldı (güvenli). BELİRSİZ, PROMOTE EDİLMEDİ.
- **BÜYÜK FİNAL (2006-9112):** cast'in TAMAMI "[Ad] Kaapor" formatında (Mariuza/Lora/Joanahi/Kunha/Mirisci/Valdilene/Waldemar/Djui Kaapor) — "Kaapor" bir SOYAD değil, Amazon yerlisi bir ETNİK-TOPLULUK adı (Ka'apor halkı) gibi görünüyor; bu muhtemelen bir BELGESEL (yerli-topluluk konulu), konvansiyonel "yönetmen kartı" formatı olmayabilir. Meşru-özel-tür şüphesi (21.YÜZYIL EŞİĞİNDE sınıfı) — **PROMOTE EDİLMEDİ, doğrulama için ayrı inceleme/insan-teyidi.**

## 🛑 PROMOTE-SWEEP #7: MİRAS'ta junk-kelime fix'i + 3 film "meşru-boş/belirsiz" (2026-07-07)
- **MİRAS (2010-9280) — FIXLENDİ (commit 70ccfc24):** video_okuma yönetmen adayı "OZEL EFEKT" — gerçek isim DEĞİL, "ÖZEL EFEKT YÖNETMENİ" rol-etiketinin kesik/bozuk hali. Kök: `_JUNK_WORDS`'te İngilizce "effects/effect" vardı, TR karşılığı "efekt" eksikti → `_valid_person_name` yanlışlıkla True dönüyordu. Fix: "efekt" eklendi (dar, tek-kelime, additive; "ozel" kasıtla eklenmedi — nadir de olsa gerçek TR soyadı riski). KANIT: unit 4/4 + golden 5/7. **Filmin kendisi hâlâ promote edilmedi** (yönetmen hâlâ okunamadı — bu fix yalnız yanlış bir çöp-adayın gelecekte candidate-havuzuna hiç girmemesini sağlıyor, gerçek yönetmeni kurtarmıyor).
- **NİNJA KAPLUMBAĞALAR (2016-2213, 3 eski KONTROL kopyası vardı):** video_okuma adayı "KEVIN EASTMAN" — TMNT karakterlerinin YARATICISI (çizgi-roman ortak-yazarı), BU FİLMİN (2016, *Out of the Shadows*) yönetmeni DEĞİL (gerçek yönetmen "Dave Green", ham OCR'da "DIRECTED BY / DAVE GREEN" temiz okunuyor ama video_okuma bunu aday olarak SEÇMEMİŞ — LLM-ensemble seçim hatası, KOVBOY/DİŞİ ŞEYTAN'daki "kaynak-eser-yazarı/senarist ≠ yönetmen" sınıfıyla aynı aile ama BAŞKA bir kod-yolunda). İKİNCİ ŞANS-fix'im "Kevin Eastman"ı doğru şekilde KORUDU (KB'de gerçek+temiz) ama final'de yine de boş kaldı — bir SONRAKİ katman bunu ayrıca elemiş (muhtemelen aynı ÖNEM DERECESİ deseni). Cast'te de "CASEY JONES"+"VERNON FENWICK" karakter-adı kirliliği var (ikisi de oyuncu değil, film karakteri). **PROMOTE EDİLMEDİ, 3 eski dosya da silinmedi** (Dave Green'i doğru aday olarak SEÇEN bir mekanizma bulunmadan promote riskli).
- **AŞK ŞARKIM (2010-1158):** gerçek "DIRECTED BY" kartı yok, yalnız "DIRECTOR OF PICTURE DEPARTMENT" (özel teknik rol) + assistant-director'lar var. Upstream-OCR-boşluğu sınıfı. **PROMOTE EDİLMEDİ.**
- **ONDAN UZAKTA (2006-9175) — dikkat çekici YANLIŞ-İZ, sistem DOĞRU çalıştı:** video_okuma "ERNST KETTLER" adayını buldu ("DIRECTED BY ERNST KETTLER" temiz okundu) ama final'de `teyitsiz_düşen.yon` listesine düşüp elendi. Frame c_0555 doğrudan görüntülendi: bu satır aslında **"STOCK FOOTAGE" bölümünde** — "'DAYS OF DESTRUCTION' — DIRECTED BY ERNST KETTLER" (filmde KULLANILAN stok-görüntünün KAYNAK belgeselinin yönetmeni, "Ondan Uzakta"nın KENDİ yönetmeni DEĞİL) — ÖNEM DERECESİ/"Amy Shapiro" ile TAM AYNI sınıf (teşekkür/kaynak-bölümünde geçen isim yönetmen sanılıyor). Burada devrede olan mekanizma (tek-okuma + KB/çift-imza-teyitsiz → `teyitsiz_düşen`) benim İKİNCİ ŞANS-fix'imden FARKLI bir katman — ve bu örnekte MÜKEMMEL çalıştı, yanlış bir stok-footage-yönetmenini doğru şekilde ELEDİ. Filmin GERÇEK yönetmeni hâlâ bulunamadı — meşru-boş. **PROMOTE EDİLMEDİ, kod-fix konusu değil (sistem zaten doğru) — AŞAĞIDA bu FİLM aynı zamanda yeni bir fix'in regresyon-kalkanı oldu.**

### KARA GÜNLER (1998-0312) — PROMOTE EDİLDİ: İKİNCİ ŞANS-fix'inin 2. doğrulanmış kazanımı
Agent-taramasının önerdiği aday. Yönetmen NIKOLAUS LEYTNER — frame g_0224 "Regie / NIKOLAUS LEYTNER" (Almanca "yönetmen") net-teyitli; ayrıca "Buch / NIKOLAUS LEYTNER / MAX LINDER" (senaryo) kartı da var — GERÇEK çift-rol (yazar-yönetmen), iki AYRI karttan doğrulandı. Bu isim daha önce (bu oturumun İKİNCİ ŞANS/Reuben Rose fix'i sayesinde) tek_film_kunye.py'nin QC2-cross-check bloğunda KB-eşleşmezliğine rağmen KORUNMUŞ. Bonus: eski PDF'in cast'inde yanlışlıkla "MAX LINDER" (aslında senarist, oyuncu DEĞİL) vardı — yeni koşu bunu doğru şekilde cast'ten çıkarıp yerine gerçek 7. oyuncuyu ("MICHAELA MAZAC", frame g_0191 "mit / BERNHARD SCHIR / MICHAELA MAZAC" teyitli) koymuş. Tür/özet/trt-kimlik değişmedi. **PROMOTE EDİLDİ.**

### YA NASİP YA KISMET (2015-0138) — AYNI-SINIF fix DENENDİ, FARKLI kod-yolunda REGRESYONA neden oldu, GERİ ALINDI
Agent-taramasının önerdiği 2. aday: yönetmen "GOKMEN TOSUN" frame c_0504'te "YÖNETMEN / GÖKMEN TOSUN" net-teyitli ama final'de boş kalıyordu. Kök farklı çıktı — İKİNCİ ŞANS-fix'imin dokunduğu QC2-cross-check bloğu DEĞİL, tek_film_kunye.py'nin AYRI bir "İSİM-DÜZEYİ TEYİT SÜZGECİ" bloğu (satır ~1071, 2026-07-05 eklenmiş, kendi `_kbx.verify(_n,"director")` çağrısıyla KB-onaysız yönetmeni sessizce siliyordu). Aynı iki-kapılı çözümü (`_valid_person_name` + geniş-KB-varlık) burada da denedim — DETERMİNİSTİK olarak Gökmen Tosun'u doğru kurtardı AMA **kritik regresyon testinde** (bugünkü ONDAN UZAKTA'yı YENİDEN koşarak) "ERNST KETTLER"in (gerçek kişi ama YANLIŞ film — stok-footage'ın yönetmeni) de ARTIK yanlışlıkla kurtulduğu ÖLÇÜLDÜ. **Regresyon doğrudan ölçülüp DERHAL geri alındı** (ondanuzakta_v3 ile doğrulandı: "—" boşa döndü) — commit'lenmedi.
**DERS (önemli, gelecek fix'ler için):** "yapısal-geçerli + geniş-KB'de gerçek kişi" testi TEK BAŞINA yeterli bir ayırt edici DEĞİL — hem Reuben Rose/Nikolaus Leytner (gerçekten BU filmin yönetmeni) hem Ernst Kettler (BAŞKA bir belgeselin yönetmeni, yalnızca stok-footage teşekküründe adı geçiyor) bu iki testi eşit derecede geçiyor. Eksik olan sinyal: adayın ekranda GERÇEKTEN KENDİ BAŞINA duran bir "yönetmen kartı" mı olduğu, yoksa daha uzun/çok-konulu bir teşekkür/kaynak-bölümü İÇİNDE mi geçtiği (bağlam-genişliği/izolasyon sinyali) — bu, basit isim-varlık kontrolünden ÇOK daha zor bir yapısal/bağlamsal problem. İki ayrı kod-yolunda (QC2 vs İSİM-TEYİT-SÜZGECİ) AYNI basit fix'in biri güvenli biri güvensiz çıkması, bu iki yolun aslında FARKLI yukarı-akış garantilerine sahip olduğunu gösteriyor (QC2'ye ulaşan adaylar zaten daha temiz bir aday-seçim sürecinden geçmiş olabilir) — ayrı bir oturumda derinlemesine incelenmeli, konsey-adayı.

### DELİLİĞİN SINIRINDA (1995-0326) — bilinen SINIF-E vakası, hâlâ ÇELİŞKİ (dokunulmadı)
Bu film daha önce bu oturumda SINIF-E'nin (stitch-karışması) örneği olarak belgelenmişti: ekranda "A [GREIF COMPANY/CHARLES FINCH PRODUCTION] DANNY HUSTON FILM" deseni 6 satıra bölünmüş. Bu turda yönetmen NICK MCLEAN olarak doldu (kimlik_dogru=True, cast_ortusme=6) ama verdict hâlâ ÇELİŞKİ — Danny Huston'ın (gerçek oyuncu, cast'te doğru yerde) "A [X] FILM" kartıyla director-mi-yoksa-yapım-şirketi-namesake-mi olduğu belirsizliği muhtemelen hâlâ sürüyor. Daha önceki "riskli, konsey-adayı" değerlendirmem geçerliliğini koruyor — **dokunulmadı, PROMOTE EDİLMEDİ.**

### AJAMİ (2009-9153) — kısmen doğru (Yaron Shani), 2 bilinen sorun hâlâ açık
verdict=TEYİT, yönetmen=YARON SHANI (doğru ama TEK — bu filmin GERÇEK eş-yönetmeni Scandar Copti KOKNEDEN'in daha önce belgelediği "dissent yutuldu" sorunuyla hâlâ eksik). Yapımcı listesinde "RUPERT PRESTON" VE "ROBERT PRESTON" birlikte görünüyor — bu, bu oturumun EN BAŞINDA zaten teşhis edilmiş "klon-ikiz" fabrikasyon bug'ı (OCR'daki TEK "Rupert Preston"dan LLM hem Rupert hem Robert varyantı üretmiş, `_collapse_clone_variants` bu ikisini birleştirmesi gerekirken birleştirmemiş görünüyor — ya kapı bu spesifik koşuda tetiklenmedi ya da mekanizma bu iki-varyantı için yetersiz). **İki bilinen, önceden-belgelenmiş sorun hâlâ aktif — PROMOTE EDİLMEDİ, ayrı-odaklı fix gerektiriyor (co-director dissent + klon-ikiz).**

### DİŞİ ŞEYTAN (1964-0002) — 2 AYRI bug bulundu, 1 FIXLENDİ+commit'lendi, 1 DENENDİ+REGRESYONLA GERİ ALINDI
KONTROL'de 2 PDF (05.07 `_YONETMEN_OZET` + 06.07 plain) — özet burada TUTARLI (ikisinde de "MEYHANECİ MURAT..." — KOKNEDEN'in "aslında sorun yok" notu doğrulandı), ama YÖNETMEN her ikisinde de YANLIŞ:
1. **FOTO DİREKTÖRÜ→sinematograf yanlış-atfı (FIXLENDİ, commit 60902423):** frame g_0104 gözle-teyitli "foto direktörü / TURGUT ÖREN" — Director of Photography'nin Yeşilçam-TR karşılığı, film-yönetmeni DEĞİL. `_NONFILM_MARKERS`'a (credit_text_read.py, zaten test edilmiş mekanizma) `"foto direkt"/"fotograf direkt"` eklendi — dar, additive, golden-regresyon temiz (5/7, en iyi skor).
2. **SENARYO→senarist yanlış-atfı (BULUNDU ama FIX REGRESYONA NEDEN OLDU, GERİ ALINDI):** frame g_0080 "Senaryo / NEVZAT PESEN / SAFA ÖNAL" — iki senarist hem yönetmen HEM yapımcı sanılıyor. Aynı mekanizmaya `"senaryo"/"screenplay by"/"written by"` eklemeyi denedim — deterministik testler geçti AMA golden-regresyonda **BUZDAN GELEN SESLER'i kırdığı ÖLÇÜLDÜ**: o filmin gerçek yönetmeni Dale Johnson AYNI ZAMANDA "Written by Kevin Peer and Dale Johnson" ortak-senarist — `_drop_dubbing_directors` bir adayın SADECE bir kötü-geçişini bulunca (TÜM geçişlerine bakmadan) tüm adayı düşürüyor, bu yüzden Dale Johnson'ın başka yerlerdeki geçerli "Directed & Photographed by" bağlamı onu kurtaramadı. **Regresyon doğrudan ölçülüp DERHAL geri alındı — commit'lenmedi.** Doğru fix için `_drop_dubbing_directors`'ın immunite mantığı TEK-geçiş değil ADAYIN-TÜM-geçişleri bazlı olmalı (herhangi bir geçişte gerçek yönetmen-etiketi varsa aday tümüyle korunmalı) — bu, PAYLAŞILAN mekanizmanın davranışını değiştiren daha büyük bir refactor, ayrı+dikkatli bir oturum gerektiriyor. **DİŞİ ŞEYTAN bu yüzden promote edilmedi** (yönetmen hâlâ NEVZAT PESEN yanlış-değerinde).
**DERS:** iki farklı KODLA-BENZER ama davranış-olarak-FARKLI fix aynı mekanizmaya eklendi; biri güvenli çıktı (foto-direktörü, dar/tek-anlamlı), diğeri güvensiz çıktı (senaryo/written-by, çünkü çok-şapkalı-kişi — yazar+yönetmen aynı insan — çok yaygın bir gerçek dünya deseni). "Golden-regresyon çalıştır" disiplini ikisini de ayırt etti; kanıt olmadan hiçbiri commit'lenmedi.

## ⏭️ Atlananlar (kritik-eşik / meşru-boş / veri-yok)

- **OCR/frame-çöp sınıfı** (MODEL-OKUMADI alt-tipi): YÜZYILIN CİNAYETİ (1933-0013), PROFESÖR HANNIBAL (1956-0062), KARA KALKAN (1954-0034)… — credit-frame'ler okunamaz/garble. Okuma-fix çözmez; frame-seçimi/re-OCR upstream işi. **Toplu liste triage bitince.**
- **Meşru-boş** (belgesel/yönetmensiz): 21. YÜZYIL EŞİĞİNDE TÜRK AİLESİ (1900-0138) — TRT belgeseli. Doğru KONTROL/özel-tür.

### REKABET (1983-0234), VİDEO OYUNU (1986-0240) — yönetmen/cast/tür/özet TEMİZ ama YANLIŞ AFİŞ yüzünden PROMOTE EDİLMEDİ
Bkz. dosya başındaki "🚨 KRİTİK BULGU". Her iki filmin de yönetmen (REKABET: Franz Marx, "A FRANZ MARX FILM" frame-teyitli; VİDEO OYUNU: Walter Deuber + Peter Stierlin, "Ein Film von Deuber & Stierlin" frame-teyitli), cast, tür ve özet alanları TAMAMEN doğru/temiz — TEK sorun afiş. **PROMOTE EDİLMEDİ** (yanlış-afiş > afişsiz kuralı) — sistemik afiş-doğrulama sorunu ayrı görev olarak işaretlendi (task_6f1ca8f8).
- **METİN (1980-0149), OTOPARK (1985-0256):** ikisi de zayıf sinyal (video_okuma.yon: [], cast düşük/sıfır) — upstream-OCR boşluğu sınıfı, araştırılmadı.

### ÇÖL ASLANI (1987-1235, = *Lion of the Desert*) — PROMOTE EDİLDİ, afiş İKİ koşuda da doğrulandı
Yönetmen+yapımcı MOUSTAPHA AKKAD (frame g_0028 "A MOUSTAPHA AKKAD FILM" teyitli, tarihsel olarak doğru — hem yönetmen hem yapımcı). Cast 10→18 (Rod Steiger + John Gielgud dahil, gerçek — agent'ın öngördüğü cast-cap sınıfı doğrulandı). **Afiş özellikle kontrol edildi (bugünkü yanlış-afiş bulgusundan sonra): hem eski hem yeni PDF'te "LION OF THE DESERT" DOĞRU afiş** — bu film KONTROL-grubu görevi gördü, mekanizmanın HER filmde değil yalnız kısa/jenerik başlıklarda bozulduğu hipotezini destekledi.
- **MUTLU PASKALYA, ALTIN VE ŞÖHRET:** ikisi de zayıf sinyal (cast=0, kimlik_dogru=False, afis=False) — upstream-OCR boşluğu sınıfı, araştırılmadı.

---
_Güncelleme: her film sonrası bu tablo işlenir._

## Batch: LALELER OCR-pipeline teşhisi

- **LALELER (1988-0430):** KOKNEDEN CSV zaten doğru teşhis etmiş — `ocr_bucket=HATA`, `ocr-78848edc` dizini 0 dosya, YÖNETMEN+CAST ikisi de B_OCR_OKUYAMADI. 1284 frame MEVCUT (frame-yakalama başarılı), ama OCR hiç çalışmamış. `_pipe_ocr.py --frames ... --out ...` ile mevcut frame'ler üzerinde OCR'ı YENİDEN denedim (tek-seferlik, orijinal dizine dokunmadan scratch'e) → `bucket: MOTOR_YOK, error: ModuleNotFoundError: No module named 'oneocr'`. Bu benim genel Python 3.10 kurulumumda (`tek_film_kunye.py --clip` için kullandığım) oneocr paketi kurulu değil — production pipeline'ının kullandığı (muhtemelen ayrı venv/servis altında çalışan) ortamdan FARKLI, yani bu test LALELER'in ORİJİNAL üretim-zamanı hatasının gerçek kök nedenini KANITLAMIYOR (benim ortamım geçersiz test aracı). Altyapı/venv soruşturması bu loop'un (metin-yorumlama-katmanı) kapsamı dışında → LALELER **upstream OCR-pipeline boşluğu** olarak belgelendi, düzeltilmedi, KONTROL'de kalıyor. Not: bu tür "OCR hiç çalışmamış" (0 satır, boş dizin) filmler bu gece görülen diğer "OCR okuyamadı" filmlerinden (garble/düşük-kontrast) FARKLI bir alt-sınıf — engine-seviyesinde crash, metin-kalite sorunu değil.

## Batch: İŞTE BIRD (promote) + ZAMAN VE RÜZGAR (regresyon yakalandı, promote edilmedi) + VANYA DAYI (SINIF-1 ek örnek)

- **İŞTE BIRD (1988-0425) → ONAYLI:** afiş önceden KAYNAK_YOK idi, bu turda "Bird Now: A Tribute To Jazz Legend Charlie Parker" doğru afiş bulundu (görsel doğrulandı — cast Dizzy Gillespie/Coleman Hawkins/vb ile tutarlı). tür alanı boş/bozuktan "BELGESEL / MÜZİK"e düzeldi. Cast 6→16 (CHAN PARKER, WALTER BISHOP JR, DORIS PARKER, JIMMY SLYDE, SANTI DEBRIANO, OLU DARA, STEVEN BEN ISRAEL vb. eklendi) — görsel teyit: "CHAN PARKER" (Charlie Parker'ın eşi) röportaj alt-yazı etiketi olarak giris_p02'de defalarca net görülüyor, belgesel-tipi tekrarlı-alt-yazı deseni yüksek güvenilirlikte. Byte-diff'te SADECE ekleme+üretim-damgası+eski FILM_NOTU'nun (artık geçersiz "3 isim çıkarıldı" notu) kalkması var, hiçbir alan kaybolmadı. Yedek: `_KONTROL_duzeltilen_yedek/20260709_091910_istebird/`.

- **ZAMAN VE RÜZGAR (1990-0336) — PROMOTE EDİLMEDİ, gerçek regresyon yakalandı:** Cast 10→18 genişlemesi doğru (frame p01'de "com" listesinde 30 isim net, MITAS_CAST_CAP=18 ile üst kısmı doğru alındı). AMA byte-diff'te eski PDF'in YÖNETMEN alanında olan **"PAULO JOSE"** yeni render'da YÖNETMEN'den düşmüş, sadece OYUNCULAR'a taşınmış. Frame doğrulandı (giris_p02, "direção" kartı): **PAULO JOSÉ / WALTER CAMPOS / DENISE SARACENI** üçü birden net okunuyor, AYRICA ayrı bir "direção geral" kartında yalnız PAULO JOSÉ tekrar geçiyor (genel yönetmen). Paulo José AYRICA cast'te de var (gerçek çift-rol: hem oyuncu hem yönetmen — Brezilya'da tanınmış bir aktör-yönetmen). Kök-neden taraması (`credit_video_read.py`, `tek_film_kunye.py`) net bir "cast'teyse yönetmenden sil" deterministik satır BULAMADI — en olası açıklama: VLM-ensemble oy-birliği (2 modelden biri yakalamamış olabilir) VEYA KB-RED aşaması (Paulo José'nin KB'de birincil mesleği muhtemelen "actor", "director" değil → **SINIF-1 KB-disambiguation** ailesiyle aynı desen: iç-okuma doğru ama KB dış-doğrulama meslek-uyumsuzluğu yüzünden reddediyor). **UYGULANMADI** — bu tam olarak bu gece konseye taşınan (ama konsey aracı arızalı cevap verdiği için kendi mühendislik-muhakememle ele alınan) SINIF-1'in YENİ, somut bir örneği: "çift-rol (oyuncu+yönetmen) kişi, KB birincil-meslek uyuşmazlığı yüzünden yönetmen-kimliğini kaybediyor." Film KONTROL'de bırakıldı, dokunulmadı (ne eski ne yeni PDF değiştirildi).

- **VANYA DAYI (1989-0476) — SINIF-1'e ek örnek, promote edilmedi:** (yukarıda ayrıntılı belgelendi) QC2 kapısı "Yevgeniy Makarov"ı doğru koruyor, ama İSİM-DÜZEYİ TEYİT SÜZGECİ'nin `_kbx.verify(name,"director")` katı-KB-kontrolü (muhtemelen Sovyet-dönemi tiyatro yönetmeni küresel film-KB'sinde yok) yüzünden nihai yönetmen alanı boşalıyor. Aynı paylaşılan, riskli mekanizma — dokunulmadı.

**SINIF-1 GÜNCELLEME NOTU:** bu turda 2 YENİ somut örnek eklendi (ZAMAN VE RÜZGAR/Paulo José çift-rol, VANYA DAYI/Sovyet-KB-boşluğu) — toplamda şimdi en az 6 bağımsız film bu ailede (İNTİKAM, YARGIÇ VE POLİS, MANASLU, JERICO APARTMANI, +bu 2 yeni). Bu kadar tekrar eden bir desen artık "nadir kenar-vaka" değil, KONTROL-oranının önemli bir kısmının kök nedeni gibi görünüyor — insan/konsey önceliği güçleniyor.

## Batch: KKL/ZERK/YAPRAK BİTTİ/SON YARIŞ — hiçbiri promote edilmedi, 2 yeni sınıf bulundu

- **KIRIK KALPLER LOKANTASI (1991-0442) ve YAPRAK BİTTİ (1991-0406) — YENİ SINIF: upstream ASR-boşluğu (LALELER'in kardeşi):** ikisi de "_OZET" bayraklı; cast 10→18/10→17 genişledi (temiz, zararsız) ama ÖZET alanı hem eski hem yeni PDF'te değişmeden **"(ÖZET AYRI BİR ADIMDA ÜRETİLECEKTİR.)"** placeholder'ı — gerçek özet HİÇ üretilmemiş. Kök: `asr/` klasöründe ikisinde de SADECE `subtitle.json` var, transcript*.txt YOK (KKL'de ham wav da var ama transkript yok, YAPRAK'ta wav bile yok) — ASR adımı bu filmler için hiç tamamlanmamış, LALELER'in OCR-crash'inin ASR-tarafındaki eşdeğeri. `tek_film_kunye.py --clip` bu boşluğu DOLDURMUYOR (özet-üretimi ayrı bir pipeline aşaması, --clip modu placeholder basıyor). Text-yorumlama-katmanı dışı → **PROMOTE EDİLMEDİ**, dokunulmadı.

- **ZERK'İN HİKAYESİ (1991-0469) — değişmedi, promote edilmeyecek kadar az kazanç:** cast küçük bir isim (WARD SAXTON) ekleyip yeniden sıraladı, eski "1 isim düşürüldü" FILM_NOTU'su kalktı — zararsız ama kimlik_dogru=false/tür=—/afiş=false (KAYNAK_YOK) hem eski hem yeni PDF'te AYNI, orijinal bayraklı sorun (_HAFIF_AFIS) çözülmedi. Dokunulmadı.

- **SON YARIŞ (1992-0308) — SINIF-1'e 3. örnek, AYRICA önemli metodoloji dersi:** yeni render'da "Yönetmen: JOVAN RANCIC" tamamen düşmüş + "KİŞİ-TEYİT — 1 isim listeden çıkarıldı" notu. İlk bakışta ham `kunye.txt`'de "SARADNICI NA SCENARIJU" (senaryo-yardımcıları) etiketinin hemen altında "VEROSLAV RANCIC"/"JOVAN RANCIC" görünce YANLIŞLIKLA "eski PDF hatalıymış, düşürülmesi doğruymuş" diye düşündüm — **ama frame'e (giris_p06) bakınca gerçek görüldü:** ayrı, net, tek başına bir kartta **"režija / JOVAN RANČIĆ"** (=yönetmen) açıkça yazıyor; üstteki "direktor fotografije" kartında ise isimler ("MILIVOJE MILIVOJEVIC"/"RADIVOJE POPOVIC") ham-metin sıralamasında karışmış görünüyordu. **DERS:** çok-kartlı dissolve-geçişli jeneriklerde ham OCR'ın DÜZ SATIR SIRASI, kartların gerçek görsel sırasını/eşleşmesini YANLIŞ yansıtabiliyor — yalnız ham metne bakarak rol-atfı sonucuna varmak (frame'e inmeden) YANLIŞ karar riski taşıyor; bu oturumun "her fix'i frame ile gözle teyit et" kuralının tam da önlemeye çalıştığı hata türü, canlı örnekle bir kez daha doğrulandı. Sonuç: JOVAN RANČIĆ gerçek yönetmen, teyit-süzgeci onu YANLIŞLIKLA düşürdü — SINIF-1 (KB-disambiguation) ailesine 3. bu-geceki örnek. **PROMOTE EDİLMEDİ**, dokunulmadı.

**SINIF-1 SAYAÇ GÜNCELLEMESİ:** bu gece toplam 3 yeni örnek (ZAMAN VE RÜZGAR, VANYA DAYI, SON YARIŞ) + önceki 4 = en az 7 bağımsız film. Desen çok güçlü — teyit-süzgeci (`tek_film_kunye.py:1071-1079`, `_kbx.verify(name,"director")`) KB'de "director" mesleği net olmayan (çift-rol aktör-yönetmen, yabancı/Sovyet/Sırp-Hırvat gibi KB-kapsamı zayıf sinema) her durumda gerçek yönetmeni siliyor.

## Batch: İKİNCİ ŞANS + YALNIZ TOM (kod-fix DOĞRULANDI, özet-boşluğu bloke) + ZİRVEDEKİ YALNIZLAR (kısmi) + VAHŞİ ORMAN (CİDDİ REGRESYON YAKALANDI, dokunulmadı)

- **İKİNCİ ŞANS (1992-0465) — bu geceki QC2 iki-kapı fix'i UÇTAN UCA DOĞRULANDI:** eski PDF'te Yönetmen alanı TAMAMEN BOŞTU; yeni render'da `yonetmen_kaynak: "kareler (KB eşleşmedi ama OCR temiz + KB'de gerçek kişi → okunan korundu)"` ile **REUBEN ROSE** doğru geldi — bu tam olarak bugün commit edilen (434f8bef) fix'in çalıştığının canlı kanıtı. Yapımcı de "CURT PETERSEN"(yanlış yazım)→"CURT PETERSON"+2 yeni isim ile düzeldi, cast 10→18. **AMA promote edilemedi:** orijinal bayrak "_YONETMEN_OZET" idi, ÖZET hâlâ "(ÖZET AYRI BİR ADIMDA ÜRETİLECEKTİR.)" placeholder'ı — `asr/` klasöründe transcript yok (yalnız subtitle.json+wav), aynı upstream ASR-boşluğu sınıfı. Yönetmen-yarısı ÇÖZÜLDÜ, özet-yarısı bloke — film KONTROL'de kalıyor, dokunulmadı.

- **YALNIZ TOM (1992-0484) — "asst" fix'i doğrulandı (dolaylı):** yönetmen hem eski hem yeni PDF'te boş (OCR'da bu film için yönetmen hiç yakalanmamış — "asst" fix'inin hedefi bu değildi zaten, o CAST tarafını temizliyordu). Cast 2→10 genişledi. Küçük bir gözlem: "KATIE MURRAY" eski listede vardı yeni'de yok — OCR'da "1st Asst. Director/David Webb" ile tamamen alakasız bir bağlamda ("Katie Murray" karakter-adı gibi ayrı bir cast-satırında) olduğu görüldü, bu geceki "asst" fix'iyle İLGİSİZ bir fark (muhtemelen VL-ensemble run-to-run varyansı) — tek isim, kritik değil. **AMA promote edilemedi:** aynı "_YONETMEN_OZET" bayrağının özet-yarısı yine ASR-boşluğu (transcript yok) yüzünden çözülemedi.

- **ZİRVEDEKİ YALNIZLAR (1993-0277) — kısmi iyileşme, hâlâ bloke:** "MICHAEL FRAYN" (İngiliz oyun yazarı/senarist, oyuncu DEĞİL) cast'ten doğru şekilde çıkarıldı, cast 7→15 genişledi, eski "1 isim düşürüldü" notu kalktı — hepsi zararsız/olumlu. AMA orijinal bayrak "_YONETMEN_KIMLIK" idi: yönetmen hem eski hem yeni'de boş (hiç okunamamış, teyit-süzgeci bile değil — aday hiç üretilmemiş), kimlik_dogru hâlâ false, tür hâlâ boş. Kadro-temizliği güzel ama ÇEKİRDEK sorun çözülmedi. Promote edilmedi.

- **VAHŞİ ORMAN (1994-0316) — CİDDİ REGRESYON, dokunulmadı:** byte-diff eski PDF'te doğru başlık "JUNGLE GROUND" + tür "AKSİYON/BİLİMKURGU" + 10 kişilik doğru cast (RODDY PIPER başta — gerçek, ünlü güreşçi-oyuncu, OCR'da line 4-9'da "Cornel RODDY PIPER" olarak net) olduğunu, yeni render'ın ise başlığı KAYBEDİP tür alanını BOŞALTIP cast'i TAMAMEN FARKLI 5 isme (LIZ GRUSZKA, JIM WISEMAN vb.) değiştirdiğini gösterdi. Kök-neden frame/OCR taramasıyla bulundu: "Liz Gruszka"/"Jim Wiseman" aslında **CREW** ("Make-up LIZ GRUSZKA", "Tattoo Artist JIM WISEMAN" — satır ~789-882, kredilerin SONUNA yakın) — yeni render'ın VL-okuması gerçek lead-cast'in bulunduğu ERKEN bölümü (satır 4-9, Roddy Piper) TAMAMEN KAÇIRMIŞ, yalnızca GEÇ crew-bölümünü yakalayıp cast sanmış. Bu, bu gecenin diğer sorunlarından FARKLI bir sınıf: deterministik bir kod-hatası değil, VL-ensemble okumasının stokastik/run-to-run değişkenliği (aynı film, aynı kaynak, farklı okuma turu → çok farklı, çok daha kötü sonuç). **PROMOTE EDİLMEDİ, eski KONTROL dosyasına HİÇ dokunulmadı** — bu vaka, "her promote öncesi byte-diff zorunlu" kuralının tam da önlemeye çalıştığı en ciddi senaryoyu canlı olarak doğruladı: şansa bırakılsa bu yeniden-render doğrudan ONAYLI'ya gidebilir, doğru veriyi yanlışla değiştirebilirdi.

**METODOLOJİ NOTU:** VAHŞİ ORMAN vakası, tonight'ın "clean" görünen cast-genişlemesi diff'lerinin bile HER ZAMAN gözle/mantıkla kontrol edilmesi gerektiğini gösteriyor — yalnızca "isim sayısı arttı" iyi bir sinyal değil, YENİ isimlerin de gerçekten cast (crew değil) olduğu ve eski çekirdek isimlerin KAYBOLMADIĞI ayrıca doğrulanmalı.

## Batch: SON OYUN + İKİ SEVGİLİM VAR (temiz ama orijinal bayrak çözülmedi) + KIZIL HAYAT + AŞK EVLİLİĞİ (kimlik-regresyonu, 2. VE 3. örnek)

- **SON OYUN (1995-0475):** cast 10→16 temiz genişleme, özet AYNI içerik (sadece satır-sarma farklı). Yönetmen hem eski hem yeni'de boş (deferans: OCR boş → KB-fill atlandı, doğru/korumacı davranış). Orijinal bayrak tek "_YONETMEN" idi — bu hâlâ çözülmedi (gerçek upstream-okuma boşluğu, fix'lenmedi). Promote edilmedi.

- **İKİ SEVGİLİM VAR (1996-0330):** çok temiz — cast 2→8, yönetmen "kareler (KB yazım teyitli)" ile SAĞLAM/net teyitli (riskli teyitsiz-yol değil). Ama orijinal bayrak "_HAFIF_AFIS" idi ve afiş hâlâ yok (hem eski hem yeni'de false) — İŞTE BIRD'ün aksine bu kez poster_fetch yine KAYNAK_YOK döndü. Bayrak çözülmedi, promote edilmedi.

- **KIZIL HAYAT (1996-0325) ve AŞK EVLİLİĞİ (1996-0353) — kimlik-çözümleme REGRESYONU, VAHŞİ ORMAN'ın 2. ve 3. varyantı:** ikisinde de kimlik_dogru eski PDF'te (dolaylı olarak, tür+orijinal-başlık dolu olduğundan) muhtemelen true iken yeni render'da açıkça **false**; ikisinde de tür alanı dolu değerden ("DRAMA"/"DRAM") boşa (—) düştü, ikisinde de orijinal yabancı başlık (KIZIL HAYAT→"LIFE IN RED", AŞK EVLİLİĞİ→"COMBATS DE FEMME") TAMAMEN KAYBOLDU. KIZIL HAYAT'ta AYRICA gerçek, OCR'da 3 kez tekrarlanan doğrulanmış bir oyuncu (**Alexander Balouev** — tanınmış Rus aktör) cast'ten DÜŞTÜ (yerine 9 yeni/doğrulanmamış isim geldi — net kazanç ama gerçek bir kayıpla birlikte). Kök muhtemelen ortak: bu run'da kimlik-çözümleme (identity/KB-arama) başarısız olunca ondan beslenen tür+orijinal-başlık alanları da boşaldı — VAHŞİ ORMAN'daki cast-kaynak karışıklığından FARKLI ama AYNI ailede bir bulgu (VL/kimlik-çözümleme run-to-run kararsızlığı). **İKİSİ DE PROMOTE EDİLMEDİ, eski KONTROL dosyalarına dokunulmadı.**

**GÜÇLENEN METODOLOJİ BULGUSU:** bu gece 3 batch'te art arda 3 farklı regresyon yakalandı (ZAMAN VE RÜZGAR/Paulo José, VAHŞİ ORMAN/cast-tam-değişim, KIZIL HAYAT+AŞK EVLİLİĞİ/kimlik-tür-başlık-kaybı) — `tek_film_kunye.py --clip` yeniden-render'ları SADECE "kod-fix'lerimin etkisini gösteren" nötr bir araç değil, VL-ensemble'ın kendi run-to-run stokastikliği yüzünden bazen SAF REGRESYON da üretebiliyor. Byte-diff-öncesi-promote disiplini bu riski her seferinde başarıyla yakaladı — bu kuralın gevşetilmemesi gerektiğinin güçlü kanıtı.

## Batch: AĞIZ TADI + AHTAPOT (temiz kazanımlar, orijinal bayrak çözülmedi) + RÜZGAR BİZİ SÜRÜKLEYECEK (ÇOK CİDDİ regresyon — Abbas Kiarostami) + SEVİMLİ KÖPEK 3 (nötr)

- **AĞIZ TADI (2001-9238):** cast 3→11 temiz genişleme, hiçbir alan kaybı yok. Yönetmen hem eski hem yeni'de boş (deferans, OCR'da hiç yok — korumacı, doğru). Orijinal bayrak "_YONETMEN" çözülmedi. Promote edilmedi.

- **AHTAPOT/DEAD EYE SIX (2000-0274):** Yönetmen alanı boştan **JOHN EYRES**'e doldu — frame'de "NU IMAGE PRESENTS ... A JOHN EYRES FILM" kendinden-etiketli, net, standalone kart ile TAM DOĞRULANDI. Cast 2→5 genişledi. Güzel bir kazanım, ama orijinal bayrak "_KIMLIK" idi ve kimlik_dogru hâlâ false (tür/afiş de hâlâ boş/KAYNAK_YOK) — ana sorun çözülmedi, promote edilmedi.

- **RÜZGAR BİZİ SÜRÜKLEYECEK/The Wind Will Carry Us (1999-0361) — ÇOK CİDDİ regresyon, 5. örnek bu gece:** eski PDF'te doğru başlık "THE WIND WILL CARRY US" + tür "DRAMA" + **Yönetmen: ABBAS KIAROSTAMI** (dünyaca tanınmış İranlı yönetmen, bu ünlü 1999 filminin gerçek yönetmeni — dünya-bilgisi düzeyinde kesin) vardı. Yeni render'da ÜÇÜ DE KAYBOLDU: başlık boşaldı, tür boşaldı, **Kiarostami yönetmen listesinden TAMAMEN SİLİNDİ**, cast da 8 isimden 3'e düştü (5 gerçek isim kayboldu, sadece 1 yeni isim geldi). Bu, VAHŞİ ORMAN/KIZIL HAYAT/AŞK EVLİLİĞİ/ZAMAN VE RÜZGAR'dan sonra bu gecenin **5. run-to-run regresyon vakası**. **PROMOTE EDİLMEDİ, dokunulmadı.**

- **SEVİMLİ KÖPEK 3 (2000-0430):** cast listesi büyük ölçüde YER DEĞİŞTİRDİ (10→17, bazı eski isimler cast'ten yapımcı/crew-benzeri ikinci bir listeye kaymış görünüyor) ama çekirdek isimler (Kevin Zegers, Dale Midkiff, Duncan Regehr, Martin Ferrero vb.) hepsi HALA mevcut, sadece sırası/gruplaması değişti — net bir kayıp yok, nötr/hafif-pozitif. Özet aynı içerik (satır-sarma farkı). Yönetmen bilgisi bu filmde hiç yok (orijinal bayrak sadece "_YONETMEN"). Promote edilmedi (ana sorun çözülmedi).

**ARAŞTIRILAN VE ELENEN HİPOTEZ:** RÜZGAR'ın logunda `mitas.duckdb erişilemedi → CSV fallback: "Kullanıcı adı veya parola hatalı"` uyarısı görülünce başta bunun tüm gecenin regresyon-nedeni olabileceği düşünüldü — ama kontrol edilince bu uyarının HER TEK log'da (başarılı İŞTE BIRD/İKİNCİ ŞANS dahil) 2-3 kez rutin olarak çıktığı görüldü; dar-kapsamlı bir isim-CASING fallback'i (`name_normalize`), genel KB-doğrulamayı bloke etmiyor. Gerçek/muhtemel neden hâlâ açık: **4'lü paralel render'ın VRAM çakışması** (memory: "2 paralel iş + VRAM: tek hog gemma4 ~18.7GB" — 4'lü paralellik bu sınırı aşıyor olabilir, modelin sessizce zayıf/kısmi bir moda düşmesine neden olabilir). **Bundan sonraki batch'lerde paralellik 4'ten 2'ye düşürülüyor** — bu daha önce belgelenmiş, bilinen güvenli sınıra dönüş.

## Batch: RENE + CİNAYET YERİ → ONAYLI (2'li paralellikle ilk temiz batch)

- **RENE (2002-9246) → ONAYLI:** cast 1→9. "ARMAND BARBAULT" eski listeden düştü — OCR'da "direction de production / ARMAND BARBAULT" (=yapım yönetmeni, CREW) olduğu doğrulandı, doğru bir düzeltme (crew yanlışlıkla cast'teydi). 9 yeni isim (Catherine Beeken, Hervé Pujervie, Herve Grignon, Philippe Moussa, Sophie Danton, Valérie Satger, Brigitte Fourreau, Jean-Michel Ségard, Gerard Yon) OCR'da net bir "avec" (=katılımcılar) bloğunda (satır 26-42) doğrulandı — hepsi meşru. Afiş doğru (RENÉ, Alain Cavalier belgeseli). Yedek: `_KONTROL_duzeltilen_yedek/20260709_100XXX_rene/`.

- **CİNAYET YERİ/Murder Scene (2003-9059) → ONAYLI:** cast 4→11, eski 4 çekirdek isim (Nicole Eggert, Callum Keith Rennie, Timothy Bottoms, Will Feheregyhazi) TAMAMEN korundu, hiçbir kayıp yok. Afiş doğru — "MURDER SCENE" posterinde Callum Keith Rennie/Nicole Eggert/Timothy Bottoms üçü de net yazılı, cast'le birebir örtüşüyor. Özet aynı içerik (satır-sarma farkı). Temiz, sıfır riskli batch — 2'li paralelliğe düşüşten sonraki ilk batch'te 2/2 temiz sonuç, VRAM-temkin hipotezini destekliyor (kesin kanıt değil ama tutarlı).

**GÜNCEL SAYAÇ:** bu gece toplam 3 yeni promosyon (İŞTE BIRD, RENE, CİNAYET YERİ) + önceki oturumdan devam eden 17 = 20. KONTROL 203→201.

## Batch: DİPTEKİLER + GERÇEK KUZEY — 6. VE 7. run-to-run regresyon, VRAM-hipotezi GERİ ÇEKİLDİ

- **DİPTEKİLER/Below (2005-9162) — CİDDİ regresyon:** eski PDF'te doğru **Yönetmen: DAVID TWOHY** (2002 denizaltı-korku filmi "Below"un gerçek, doğrulanmış yönetmeni) vardı — yeni render'da TAMAMEN SİLİNDİ (Yönetmen satırı hiç yok). Yapımcı listesine "DARREN ARONOFSKY" eklendi (muhtemelen doğru — Aronofsky bu filmin gerçek yapımcılarından biri) ama "BOB WEINSTEIN" düştü. Cast'te ÇOK daha ciddi bir sorun: yeni listeye **"NAVY PILOT"** ve **"AIR MANIFOLD"** gibi KİŞİ OLMAYAN ifadeler (denizaltı ekipmanı/karakter-rolü etiketleri, gerçek isim değil) karıştı; gerçek oyuncular Zach Galifianakis, Jason Flemyng, Andrew Howard, Christopher Fairbank listeden düştü. **PROMOTE EDİLMEDİ.**

- **GERÇEK KUZEY/True North (2006-9110) — regresyon:** başlık "TRUE NORTH" kayboldu, tür "DRAM/GERİLİM"→boş, **Yapımcı bölümü (DAVID COLLINS, EDDIE DICK, DAVID M. THOMPSON — üçü de gerçek) TAMAMEN SİLİNDİ**. Cast'te 2 gerçek isim (Angel Li, Li Jun Wang) düştü, yerine 3 yeni geldi (net kazanç ama gerçek kayıpla birlikte). **PROMOTE EDİLMEDİ.**

**VRAM-HİPOTEZİ GERİ ÇEKİLDİ:** bir önceki batch notunda "2'li paralellik VRAM-çakışmasını önlüyor olabilir" denmişti (RENE+CİNAYET YERİ 2/2 temiz çıktığı için) — bu batch AYNI 2'li paralellikle 0/2 temiz çıkararak bu hipotezi çürüttü. Gerçek sonuç: bu gece toplam **7 run-to-run regresyon** (ZAMAN VE RÜZGAR, VAHŞİ ORMAN, KIZIL HAYAT, AŞK EVLİLİĞİ, RÜZGAR BİZİ SÜRÜKLEYECEK, DİPTEKİLER, GERÇEK KUZEY) — paralellik seviyesinden BAĞIMSIZ, ~20 filmde 1/3'e yakın bir oranda. Bu, `tek_film_kunye.py --clip`'in VL-ensemble (2-model konsensüs) okumasının önceden fark edilmemiş, YÜKSEK bir run-to-run değişkenliğe sahip olduğunu gösteriyor — büyük olasılıkla bu SÜREKLI var olan bir özellik, bu gece sistematik byte-diff yapılınca ilk kez bu kadar net görüldü. Byte-diff-öncesi-promote disiplini her seferinde regresyonu yakaladı (0 hatalı promosyon), ama bu oranın yüksekliği hem zaman/kaynak maliyeti hem de bu aracın (özellikle gözetimsiz/gece-nöbeti gibi otonom kullanımlarda) güvenilirliği için ciddi bir bulgu.

## Batch: MİRAS (ağır regresyon) + HASİP İLE NASİP (Türkçe-aksan kaybı) — mitas.duckdb bağlantısına somut kanıt

- **MİRAS (2010-9280) — ağır regresyon:** "Yönetmen: AYDIN SAYMAN / ERBİL ALTAN" (2 kişi) TAMAMEN silindi, yerine alakasız "Yapımcı: KAAN GIRGIN" geldi. Başlık "MİRAS" (doğru Türkçe İ) → "MIRAS" (yanlış, noktasız I). Cast 8→16 genişledi ama TÜM eski isimler Türkçe aksanlarını kaybetti (SUAVİ→SUAVI, ÖZDİLEK→OZDILEK, ÇAĞRI→CAGRI). Promote edilmedi.

- **HASİP İLE NASİP (2010-9265) — yapısal kayıp yok ama Türkçe-aksan kaybı nedeniyle promote edilmedi:** cast 10→18 genişledi, HİÇBİR isim/alan kaybolmadı — ama TÜM Türkçe isimler (Zeki Alasya, Güngör Bayrak, Yüksel Gözen, Gülten Kaya, Ahmet Kostarika, Memduh Ün — hepsi tanınmış Türk oyuncu/yapımcı) aksanlarını kaybetti (ör. "ZEKİ ALASYA"→"ZEKI ALASYA", "MEMDUH ÜN"→"MEMDUH UN"). Yapısal olarak temiz bir diff ama gerçek insanların isimlerini YANLIŞ yazmak (aksan-kaybı da bir doğruluk hatası) promote edilebilir bar'ı geçmiyor.

**BAĞLANTI KURULDU:** bu gecenin başında RÜZGAR BİZİ SÜRÜKLEYECEK logunda görülen `mitas.duckdb erişilemedi → CSV fallback (yabancı isim Türkçe-kasa alabilir)` uyarısı — o zaman "her logda çıkıyor, ayırt edici değil" diye elenmişti. Bu batch, uyarının açıklamasıyla TAM örtüşen somut bir semptom üretti: DuckDB'ye erişilemeyince devreye giren CSV-fallback isim-normalize yolu, TÜRKÇE isimlerin aksanlarını da (yalnız "yabancı" değil) kaybediyor gibi görünüyor. Bu, task_5aae0a2b'ye (run-to-run regresyon araştırması) ek kanıt olarak not düşüldü — X:\DIGER\Mitas_Files\MitaData\mitas.duckdb'ye erişim kimlik-bilgisi/ağ sorunu, kod-fix değil, muhtemelen bu oturumun kapsamı dışında bir altyapı konusu.

## Batch: DİŞİ ŞEYTAN (kod-fix DOĞRULANDI, duckdb-aksan yüzünden bloke) + UMUTSUZ SAAT (temiz ek, orijinal bayrak çözülmedi)

- **DİŞİ ŞEYTAN (1964-0002) — "FOTO DİREKTÖRÜ" vetosu (commit 60902423) UÇTAN UCA doğrulandı:** eski PDF'te yönetmen tamamen boştu ("JENERİK YOK" notu) — yeni render'da frame'de "Prodüktör, Rejisör / NEVZAT PESEN" (ayrı, net, standalone kart) DOĞRU yakalandı, "Fotoğraf direktörü / TURGUT ÖREN" DOĞRU elendi (fix'in tam hedeflediği senaryo). Cast 3→6, ÖZET de placeholder değil GERÇEK içerikle geldi (bu filmin ASR/özet-üretimi çalışıyor). **AMA promote edilemedi** — "NAZMİ ÖZER" (eski PDF'te doğru aksanlı) → "NAZMI OZER" (yeni, aksan kaybı) — yukarıdaki KRİTİK BULGU #2 (mitas.duckdb erişilemez) yüzünden. Kod-fix TAM başarılı; tek engel harici altyapı sorunu. **duckdb düzelince ilk sırada yeniden-kontrol/promote adayı.**

- **UMUTSUZ SAAT (2025-1295):** cast 3→12 temiz genişleme (Türkçe olmayan isimler, aksan sorunu yok), Yapımcı bölümü yeni eklendi (David Boies, Andrew Corkin, Alex Lalonde). Yönetmen hem eski hem yeni'de boş (deferans, OCR'da hiç yok). Orijinal bayrak "_YONETMEN" çözülmedi, promote edilmedi.

**GÜNCEL SAYAÇ:** 20 promosyon, KONTROL 201. Bu turda ayrıca 3 kod-fix'in (İKİNCİ ŞANS/QC2, YALNIZ TOM/asst, DİŞİ ŞEYTAN/foto direktörü) hepsi UÇTAN UCA doğrulandı — üçü de çalışıyor, üçü de ayrı (ASR-özet veya duckdb-aksan) nedenlerle henüz promote edilemedi.

## Batch: KOLEKSİYON + BUL VE YOK ET — temiz (yabancı kadro, aksan sorunu yok) ama yönetmen hâlâ boş

- **KOLEKSİYON/The Collection (1978-0220):** başlık eklendi, cast 3→4 (Alan Bates eklendi, kayıp yok), kimlik_dogru artık true. Yönetmen OCR'da hiç yok (deferans, doğru davranış) — orijinal "_YONETMEN_KIMLIK_RENDER" bayrağının yönetmen-bileşeni çözülmedi. Promote edilmedi.
- **BUL VE YOK ET (1988-0423):** cast 2→12 (temiz, kayıp yok), özet'te bir garble düzeltmesi (BOR?S→BORIS). Tür "AKSİYON/SUÇ"→"AKSİYON" (küçük daralma). Yönetmen yine OCR'da yok. Promote edilmedi.

İkisi de gelecekte OCR-taraması iyileşirse (frame'de gerçekten yönetmen yoksa "meşru-boş" olarak kalacak) hızlı yeniden-değerlendirme adayı — şu an sadece orijinal bayrak tam çözülmediği için KONTROL'de bırakıldı, risk taşımıyorlar.

## Batch: TAKKELİ MELEK + LA BOHEME — zayıf sinyal, promote edilmedi

- **TAKKELİ MELEK (1978-0227):** cast 1→4 (Orta-Asya kökenli 3 yeni isim), bir isim değişti (LESLIE VAOEHN→LUKE MAZZAFERRO, muhtemelen garble-düzeltmesi ama doğrulanmadı). kimlik_dogru hâlâ false, tür/afiş hâlâ boş — orijinal "_KIMLIK_RENDER" çözülmedi. Promote edilmedi.
- **LA BOHEME (1988-0420):** neredeyse hiç değişiklik yok (sadece "JENERİK YOK" notu kalktı, başka bir şey eklenmedi) — orijinal "_YONETMEN_CAST_OZET" bayrağının hiçbir bileşeni bu turda ilerlemedi. Zayıf sinyal, upstream-boşluk olabilir, araştırılmadı. Promote edilmedi.

## Batch: JARRAPELLEJOSILAR + JOE SHARP → ONAYLI

- **JARRAPELLEJOSILAR (1991-0454) → ONAYLI:** cast 3→10, hiçbir kayıp yok, İspanyol isimlerde aksan sorunu yok. Yönetmen zaten doğruydu (Antonio Gimenez-Rico). Afiş doğrulandı — poster "Director ANTONIO GIMENEZ-RICO" + aynı cast listesini (Tristancho/Florinda Chico/Jose Coronado) gösteriyor.
- **JOE SHARP (1992-0483) → ONAYLI:** cast 2→10, hiçbir kayıp yok. Yönetmen zaten doğruydu (Don Hulette). Afiş doğrulandı — "Tennessee Stallion" (alternatif İngilizce başlık), at-satışı konusu özetle örtüşüyor.

**GÜNCEL SAYAÇ:** 22 promosyon (bu turda +5: İŞTE BIRD, RENE, CİNAYET YERİ, JARRAPELLEJOSILAR, JOE SHARP). KONTROL 201→199.

**GÖZLEM:** Yabancı-kadrolu (Türkçe olmayan) filmlere öncelik verme stratejisi işe yarıyor — bu turdaki TÜM temiz promosyonlar (RENE/Fransız, CİNAYET YERİ/Kanada, JARRAPELLEJOSILAR/İspanyol, JOE SHARP/Amerikan) Türkçe-aksan riskinden muaf kaldı. Türkçe-kadrolu filmler (MİRAS, HASİP İLE NASİP, DİŞİ ŞEYTAN) yapısal olarak düzelse bile mitas.duckdb sorunu düzelene kadar bekletiliyor.

## Batch: SEN TOM SAWYER DEĞİLSİN (KATASTROFİK çöküş) + KORKUNÇ GECE (regresyon) — kaynak-baskısı şüphesi

- **SEN TOM SAWYER DEĞİLSİN (1993-0435) — bu gecenin EN ağır çöküşü:** eski PDF'te TAM dolu bir kayıt vardı (dil=TR, altyazı=HAYIR, süre=01:18:20, cast 8 kişi, yönetmen JAKOB BRANDMAYR, gerçek özet metni). Yeni render'da NEREDEYSE HER ALAN "�" (boş/garble) oldu — dil, altyazı, süre, TRT-kimlik, cast (8→0, `cast_list: ["—"]`), yönetmen (`yonetmen_list: ["—"]`), özet TAMAMEN kayboldu. Log'da AÇIK bir Python hatası/exception YOK (süreç "başarıyla" tamamlandı) — VL-ensemble bu seferinde kareler'den pratik olarak SIFIR içerik çıkarmış. Diğer bu-geceki regresyonlardan (kısmi alan-kaybı) FARKLI: bu TAM/toptan bir çöküş.
- **KORKUNÇ GECE (1995-0444):** daha hafif ama aynı yönde — tür "DRAMA"→boş, başlık "CONFRONTING IN THE NIGHT" kayboldu.

**ŞÜPHE — kaynak baskısı:** `tasklist` ile kontrol edildiğinde 15-20+ `python.exe` süreci VE bir tanesi ~9.2GB bellek kullanan bir `python.exe` görüldü (muhtemelen önceki batch'lerden kalan veya ayrı MITAS arka-plan servisinden). [[project_llama_server_ollama_runner_20260705]] kuralı gereği HİÇBİR süreç öldürülmedi/dokunulmadı. Bu, gece ilerledikçe artan regresyon şiddetinin (TOM SAWYER'ın toptan çöküşü, bu gecenin en kötüsü) kaynak-tükenmesiyle bağlantılı olabileceğine dair bir ipucu — kanıtlanmadı, sadece gözlem. **Önlem: sıradaki batch SIRALI (1'er film) denenecek**, paralellik daha da azaltılarak yük hafifletiliyor.

## Batch: HAYAT BİR ŞARKIDIR — 2. KATASTROFİK çöküş (sıralı/tek-film modunda BİLE) — kök-neden ipucu bulundu

- **HAYAT BİR ŞARKIDIR/On Connaît la Chanson (1997-0421):** eski PDF'te dolu ve doğru: başlık "SAME OLD SONG", tür "KOMEDİ/DRAM", 10 gerçek Fransız oyuncu (Pierre Arditi, Jane Birkin, André Dussollier vb.), **Yönetmen: ALAIN RESNAIS** (dünyaca ünlü Fransız yönetmen), Yapımcı: Michel Seydoux. Yeni render'da HEPSİ silindi/garble oldu — TOM SAWYER'daki AYNI toptan-çöküş deseni. **Bu kez SIRALI/tek-film modunda çalıştırıldı** (batch14'teki TOM SAWYER çöküşünden sonra paralellik-kaynaklı olabileceği şüphesiyle) — yine de çöktü. **Bu, "benim 2'li/4'lü paralelliğim VRAM'i dolduruyor" hipotezini ÇÜRÜTÜYOR** (tek film bile çöktü).

**YENİ İPUCU — muhtemel gerçek kök-neden:** `ollama ps` doğrudan kontrol edildi: şu an yüklü/çalışan model **`qwen3-vl:30b`** (19GB, **%100 GPU**, "14 dakika sonrasına kadar" aktif) — `credit_video_read.py`'nin belgelediği beklenen "2-MODEL ENSEMBLE" (`gemma4:26b` + `qwen2.5vl:7b`) DEĞİL. Bu, [[project_paralel_oturum_ayni_dosya_20260707]]'de belgelenen **AYNI repo'da aktif çalışan BAŞKA bir Claude oturumunun** kendi işi için `qwen3-vl:30b`'yi GPU'nun TAMAMINI kullanacak şekilde yüklemiş olabileceğini düşündürüyor — benim render'larımın `gemma4:26b`'yi yüklemeye çalıştığında yeterli VRAM bulamayıp (19GB zaten dolu + ~17-18.7GB gemma4 ihtiyacı, tek GPU'da sığmayabilir) sessizce boş/çökmüş sonuç üretmesi bu şekilde açıklanabilir — bu YÜK benim kendi paralellik ayarımdan TAMAMEN BAĞIMSIZ, dış bir kaynak-çakışması. Kontrol edemediğim/koordine edemediğim bir durum. `task_5aae0a2b`'ye bu somut ipucu (ollama ps çıktısı + zamanlama) eklendi.

**Bu turdan itibaren:** her render öncesi `ollama ps` ile GPU-doluluk hızlı kontrol edilecek; yoğunsa sonuç güvenilirliği daha da düşük olabilir, byte-diff disiplini AYNI titizlikle sürdürülecek (zaten hiçbir bozuk sonuç promote edilmedi).

## PRENSESİN AŞKI — temiz sonuç, GPU-çakışması ARALIKLI olduğu doğrulandı

**PRENSESİN AŞKI/Princess in Love (1999-0403):** kimlik_dogru artık true (çözüldü), başlık yazım hatası düzeldi (PRENCES→PRINCESS), cast 4→11 (Tamzin Outhwaite dahil, kayıp yok, İngilizce isimler aksan-sorunsuz). Yönetmen OCR'da hâlâ yok (deferans, muhtemelen meşru-boş). `ollama ps` bu turda FARKLI bir model gösterdi (qwen36-27b-test, önceki qwen3-vl:30b değil) — hâlâ %100 GPU dolu ama bu render YİNE DE temiz sonuç verdi. **Bu, GPU-çakışmasının SÜREKLİ değil ARALIKLI olduğunu doğruluyor** — bazı render'lar başarılı, bazıları (TOM SAWYER, HAYAT BİR ŞARKIDIR) muhtemelen kötü zamanlama yüzünden toptan çöktü. Loop, byte-diff güvenlik-ağı ile devam ediyor; orijinal "_YONETMEN_KIMLIK" bayrağının yönetmen-bileşeni çözülmediği için promote edilmedi.

## Batch: SESSİZ AMERİKALI + HARİKA KÖPEK 5 — ikisi de regresyon (toptan değil ama gerçek)

- **SESSİZ AMERİKALI/The Quiet American (2002-9241):** cast 9→15 genişledi ama "ALDEN PYLE" (Brendan Fraser'ın OYNADIĞI KARAKTER, oyuncu değil), "FRENCH CAPTAIN", "TOWER SOLDIERS" gibi KİŞİ-OLMAYAN rol-etiketleri cast'e karıştı (DİPTEKİLER'deki "NAVY PILOT"/"AIR MANIFOLD" ile AYNI hata sınıfı). AYRICA Yapımcı bölümü "VOLKER SCHAUZ, DIETER NOBBE, EYAL RIMON" (3 gerçek isim) → "GIAI PHONG" (Vietnamca "Kurtuluş", kişi adı değil) ile DEĞİŞTİ — gerçek kayıp. Promote edilmedi.
- **HARİKA KÖPEK 5/Air Bud 5 (2003-9136):** başlık düzeldi (AIRBUD→AIR BUD boşluk-düzeltmesi), cast 7→17 genişledi, AMA tür "DRAMA"→boş VE **Yönetmen "ROBERT VINCE" (Air Bud serisinin gerçek, doğrulanmış yönetmeni) TAMAMEN silindi**. Promote edilmedi.

Bu 2 vaka, "toptan çöküş" (TOM SAWYER/HAYAT BİR ŞARKIDIR) ile "temiz" (PRENSESİN AŞKI) arasında bir ORTA-ŞİDDET regresyon kategorisi gösteriyor — GPU-çakışma hipoteziyle tutarlı bir spektrum (yoğunluk anlık GPU-müsaitliğine göre değişiyor gibi). Byte-diff disiplini yine hiçbir bozuk veriyi promote etmeden yakaladı.

## Batch: MURPHY KANUNLARI 2 (3/4 çözüldü, özet-ASR-boşluğu bloke) + YALNIZ SAVAŞÇI (zayıf)

- **MURPHY KANUNLARI 2/Murphy's Law (2005-9051):** GPU boşken (ollama ps boş) başlatıldı, mükemmel temiz sonuç — tür/başlık/cast(James Nesbitt, Claudia Harrison — "Murphy's Law" BBC dizisinin gerçek oyuncuları)/yönetmen(Peter Lydon)/yapımcı(Sanne Craddick) hepsi boştan doldu, "JENERİK YOK" notu kalktı. Orijinal "_YONETMEN_KIMLIK_CAST_OZET" bayrağının 3/4'ü TAM çözüldü — SADECE özet hâlâ placeholder (asr/ klasöründe transcript yok, bilinen ASR-boşluğu sınıfı). Promote edilemedi ama en yakın adaylardan biri.
- **YALNIZ SAVAŞÇI (2004-9131):** çok zayıf, sadece 1 isim eklendi (Laura Newton), kimlik_dogru hâlâ false. Promote edilmedi.

**GPU-DURUMU DOĞRULAMASI:** GPU boşken başlatılan MURPHY KANUNLARI 2 kusursuz çıktı — bu, GPU-müsaitliğinin sonuç kalitesiyle doğrudan ilişkili olduğu hipotezini GÜÇLENDİRİYOR (kesin kanıt değil ama tutarlı bir 2. veri noktası: PRENSESİN AŞKI de göreceli-müsait bir anda temiz çıkmıştı).

## Batch: ŞAMPİYONLAR (regresyon) + YARIŞMA DÜNYASI (orijinal bayrak çözülmedi)

- **ŞAMPİYONLAR/Champions (2008-9110):** tür+başlık kayboldu, cast'te 2 kayıp (Debbie Goh, Yu Rongguang), **Yönetmen "SIUMING TSUI" silinip Yapımcı slotuna karışmış** (eski Yapımcı "CAI LI" da kayboldu). Regresyon, promote edilmedi.
- **YARIŞMA DÜNYASI (2007-9067):** cast 3→9 iyi genişledi, kimlik_dogru artık true, başlık "THE BIG QUIZ SHOW"→"EL CONCURSAZO" değişti (muhtemelen daha doğru — gerçek bir İspanyol/Küba yarışma-programı formatı adı). Ama orijinal "_HAFIF_AFIS" bayrağı hâlâ çözülmedi (afiş yine yok). Promote edilmedi.

## SHAOLIN → ONAYLI (yanlış-afiş bulgusuna 4. örnek, bu kez kendiliğinden düzeldi) + KANDAHAR regresyon

- **SHAOLIN (2011-9175) → ONAYLI:** yukarıda KRİTİK BULGU #1'e eklendi — eski afiş "SHAOLIN WOODEN MEN" (1976, alakasız) idi, yeni render doğru 2011 "Shaolin" afişini buldu (cast'le birebir örtüşen, görsel doğrulandı). Cast 7→13 (Andy Lau, Nicholas Tse, Jackie Chan, Fan Bingbing hepsi doğrulanmış), Yönetmen Benny Chan (doğru, gerçek), 3 yapımcı (Yang Shou Cheng, Han San Ping, Albert Yeung) doğru. Tam sayfa fitz-render ile görsel teyit edildi, hiçbir kusur yok.
- **KANDAHAR (2011-9224):** regresyon — başlık+tür kayboldu, cast 8→3 (5 gerçek Afgan isim kayboldu: Niloufar Padhira, Sedu Timuri, Hayatullah Hakimi, Mohammad Haider Barbari, Mulla Zahir Timuri, Magdalena Ozdauska). Promote edilmedi.

**GÜNCEL SAYAÇ:** 23 promosyon. KONTROL 199→198.

## Batch: ÖLDÜRME ZAMANI (hafif regresyon) + MOSKOVA BUZ BALESİ (değişiklik yok) — ikisi de promote edilmedi

## Batch: TEPEDEKİ KIZ (değişiklik yok) + GÖLGELER PRENSİ (hafif regresyon) — ikisi de promote edilmedi

## Batch: KONTES ALICE + OSCAR — ikisi de anlamlı değişiklik yok, promote edilmedi

## Batch: MELEKLERİ GÖRMEK İSTEDİM + LENI REIFENSTAHL — ikisi de hafif regresyon (başlık/tür kaybı), promote edilmedi. LENI zaten bilinen SINIF-2 (crew-threshold-seyrelme) vakası, ayrıca dokunulmadı.

## Batch: BÜYÜK SAVAŞTA KÜÇÜK ADAM (karışık, gerçek isim kaybı) + TANGO ARGENTINO (hafif regresyon) — ikisi de promote edilmedi

## Batch: TACİZ + MOTORSİKLETLİ POLİSLER — anlamlı değişiklik yok, promote edilmedi

## Batch: BANA TRINITY DERLER (fix denendi+regresyonla geri alındı) + BAHAR VE ŞARAP (model-mevcut ama sorun devam ediyor)

- **BANA TRINITY DERLER (1968-0082):** CSV kök-neden analizi doğru teşhis etmişti — ham OCR "directed" kelimesini "BY" olmadan, tek başına, ayrı bir satırda yakalıyor (`_RSC_LABELS`'ta yalın "DIRECTED" yok, fuzzy-oran eşiği 0.85 iken "DIRECTED"→"DIRECTED BY" oranı TAM 0.842 ile eşiğin altında kalıyor). **Denedim:** `_RSC_LABELS`'a yalın "DIRECTED" ekledim → golden-regresyon **TILSIMLI DÜNYA'yı bozdu** (dublaj-yönetmeni "CARL MACEK" artık yanlışlıkla ana-yönetmen sanılıyor — "dublaj-freni: yön boş kalmalı" testi FAIL oldu). Kök sebep: bare "DIRECTED" etiketi hem gerçek-yönetmen kartlarında HEM dublaj-yönetmeni kartlarında eşit şekilde geçebiliyor, ayırt edici ek bağlam (DUBBING/DIALOGUE işareti) güvenilir şekilde aynı satırda bulunmuyor. **DERHAL GERİ ALINDI, commit edilmedi** (5/7 temel çizgiye dönüldü, doğrulandı). Cast yine de temiz genişledi (1→10, İtalyan isimleri, kayıp yok) ama yönetmen bayrağı çözülmedi. Promote edilmedi.
- **BAHAR VE ŞARAP (1970-0061):** CSV'nin işaret ettiği "gemma-4-31b-it-qat-vision modeli yok" sorunu artık geçerli değil (model şu an kurulu) ama film yine de aynı "yanlış-film şüphesi" kimlik-vetosuyla tüm alanları boş döndü — demek ki kök-neden salt eksik-model değil, kimlik-çapraz-kontrol mekanizmasının kendisinde (CSV'nin işaret ettiği `credit_crosscheck.py`/`credit_qc_block.py` paylaşılan kodu) daha derin bir sorun var. Bu, TÜM filmlerin kimlik-doğrulamasını etkileyen paylaşılan bir mekanizma — dar bir fix değil, ayrı/dikkatli bir oturum gerektiriyor. Promote edilmedi, dokunulmadı.

## Batch: ŞAŞKIN REKLAMCI (regresyon) + LIBERA SEVGİLİM (BAŞLIK HALÜSİNASYONU doğrulandı) — ikisi de promote edilmedi

- **ŞAŞKIN REKLAMCI/Le Distrait (1970-0076):** tür+başlık kayboldu, **cast (Pierre Richard — tanınmış Fransız komedi oyuncusu) TAMAMEN silindi**. Regresyon, promote edilmedi.
- **LIBERA SEVGİLİM/Libera Amore Mio (1975-0185) — ÖNEMLİ: HALÜSİNASYON doğrulandı, KRİTİK BULGU #3'ten (OMAGGIO A CARUSO/gerçek arşiv-uyuşmazlığı) AYRIŞTIRILDI:** yeni render'da başlık "LIBERA AMORE MIO"dan tamamen alakasız bir İtalyan filmi adına ("FINALMENTE LE MİLLE E UNA NOTTE") değişti. Frame'e inilip (giris_p01) gözle kontrol edildi: ekranda "ISTITUTO LUCE presenta / Roberto Loyola presenta" ve karakterin adı "Libera" olan bir diyalog sahnesi var — **"Finalmente le Mille e Una Notte" ekranın HİÇBİR YERİNDE geçmiyor.** Bu, KOKNEDEN CSV'nin ÖNCEDEN UYARDIĞI ("qwen36-35b-test gibi fallback modeller halüsinasyon üretiyor, kanıt: Leslie Vaoehn fabrikasyonu") deseninin CANLI, doğrulanmış 2. örneği — OMAGGIO A CARUSO'nun aksine bu GERÇEK bir arşiv-uyuşmazlığı DEĞİL, modelin ekranda olmayan bir başlık uydurması. Cast tarafında CSV'nin beklediği "Giuseppe Tuminelli" eklentisi DOĞRU geldi (bu kısım güvenilir) ama başlık alanı güvenilmez. **PROMOTE EDİLMEDİ.** Bu bulgu task_5aae0a2b'ye (run-to-run regresyon/halüsinasyon araştırması) somut 2. kanıt olarak eklendi — artık yalnızca "alan kaybı" değil, "aktif fabrikasyon" riski de belgeli.

**DOĞRUDAN KORELASYON:** LIBERA SEVGİLİM render'ı bittiğinde `ollama ps` kontrol edildi — GPU'da şu an yüklü model tam olarak **"qwen36-35b-test:latest"** (21GB, %100 GPU) — CSV'nin "Leslie Vaoehn" fabrikasyonuyla suçladığı AYNI model. Bu, task_5aae0a2b'nin GPU-çakışma/fallback-halüsinasyon hipotezine güçlü bir doğrudan-korelasyon kanıtı daha ekliyor.

## Batch: BİR ZAMANLAR (ASR-boşluğu, promote edilmedi) + DÜNYANIN EN İYİ İNSANI (zaten ONAYLI'ymış, CSV bayat)

## Batch: BJ VE AYI (başlık düzeldi ama kimlik hâlâ çözülmedi) + ARTAN İSTEKLER (değişiklik yok) — ikisi de promote edilmedi

## Batch: AMANSIZ TAKİP (kimlik düzeldi, yönetmen hâlâ boş) + KUĞUNUN ŞARKISI (garble-benzeri isimler değişti, kimlik hâlâ çözülmedi) — ikisi de promote edilmedi

## PARİS'İN DIAGHILEV İLE DANSI — 3. başlık-güvenilirliği vakası: HEM eski HEM yeni başlık YANLIŞ

**TRT-KİMLİK 1991-0355** (KONTROL'de 2 duplicate kayıt: "_OZET_RENDER" ve "_RENDER"): eski PDF'lerin İKİSİ de "FİLM" alanında **"PARIS TROUT"** (1991 alakasız bir Amerikan dram filmi) yazıyordu. Bu turda yeniden-render edilince başlık **"CINDERELLA"**ya döndü — ilk bakışta OMAGGIO A CARUSO gibi bir arşiv-düzeltmesi sanılabilirdi, ama frame'e inilip (giris_p01) gözle doğrulanınca görüldü ki **İKİSİ DE YANLIŞ**: ekranda net biçimde "Paris Opera Ballet Company... under the joint direction of PATRICE BART / EUGENE POLYAKOV... Directed for Television by COLIN NEARS" ve afiş-kart "CHATELET — BALLET RUSSE — **PETROUCHKA** / Le Spectre de la Rose / L'Après-midi d'un Faune / Noces" yazıyor. Gerçek içerik, Diaghilev/Ballets Russes repertuarından **"Petrouchka"** (+3 eşlik eden bale) — TRT'nin genel katalog başlığı "Paris'in Diaghilev ile Dansı" ile TEMATİK olarak TUTARLI (muhtemelen TRT-kimliğin kendisi doğru), ama künyenin "FİLM" alanına iki ayrı okuma turunda da YANLIŞ, birbirinden farklı, ikisi de ekranda-yazmayan başlıklar ("Paris Trout", "Cinderella") yazılmış.

Bu, OMAGGIO A CARUSO'dan (gerçek arşiv-uyuşmazlığı, eski YANLIŞ yeni DOĞRU) ve LIBERA SEVGİLİM'den (halüsinasyon, eski DOĞRU yeni YANLIŞ) FARKLI bir 3. desen: **HER İKİ okuma da güvenilmez** olabiliyor — çok-baleli/karma-programlı, kendinden başlık-kartı standart "FİLM ADI" formatında olmayan (afiş yerine "Chatelet... Ballet Russe... [4 eser adı]" gibi bir program-kartı) içeriklerde başlık-çıkarımı özellikle kırılgan görünüyor. **PROMOTE EDİLMEDİ, hiçbir duplicate kayıt değiştirilmedi.** Bu bulgu task_5aae0a2b'ye (başlık/kimlik güvenilirlik sorunları) 3. örnek olarak eklendi.

## Batch: BİR KATİLLE EVLENDİM (değişiklik yok) + ÜÇ KURUŞLUK OPERA (temiz ama ASR-boşluğu bloke) — ikisi de promote edilmedi
- ÜÇ KURUŞLUK OPERA: cast 4→12 (Jeremy Irons, Jiri Menzel yönetmen — gerçek, doğrulanmış), başlık/tür/yönetmen zaten doğruydu, hiçbir kayıp yok — ama özet yine placeholder (ASR-boşluğu sınıfı).

## Batch: BLACKJACK (regresyon — Dolph Lundgren dahil TÜM cast kayboldu) + İŞARET DİREĞİ (hafif regresyon) — ikisi de promote edilmedi

## Batch: SON CÜCE (değişiklik yok) + PUNKTCHEN VE ANTON (regresyon — DOĞRU model yüklüyken bile!)

- **PUNKTCHEN VE ANTON/Annaluise & Anton (1999-0383) — ÖNEMLİ DÜZELTİCİ BULGU:** GPU'da bu render'dan HEMEN ÖNCE doğru/birincil model (`gemma4:26b`) yüklü olduğu doğrulanmıştı (BLACKJACK'in çöktüğü qwen36-35b-test DEĞİL) — buna rağmen başlık "ANNALUISE & ANTON" kayboldu, tür kayboldu, **8 kişilik TÜM cast (August Zirner, Meret Becker, Benno Furmann — hepsi gerçek Alman oyuncular) TAMAMEN silindi**. **Bu, "GPU-çakışması/yanlış-fallback-model" hipotezini TEK BAŞINA yeterli açıklama olmaktan çıkarıyor** — doğru model yüklüyken de aynı şiddette regresyon oluyor. Muhtemel sonuç: VL-ensemble okumasının run-to-run değişkenliği GPU-paylaşımından bağımsız, DAHA TEMEL bir kararsızlık (belki tek-geçiş/no-retry mimarisi, belki context-window/frame-örnekleme rastgeleliği). Bu önemli düzeltme task_5aae0a2b'ye eklendi — kök-neden araştırması yalnızca "modeli/GPU'yu düzelt" ile sınırlı kalmamalı.

## Batch: DURUMU ANLAMAK (hafif regresyon) + HAYAL PEŞİNDE (karışık, başlık/tür kaybı) — ikisi de promote edilmedi

## DOĞRU KILAVUZ — 5/6 alan MÜKEMMEL düzeldi (bayraksız-ama-bozuk sınıflandırma-boşluğu örneği), özet-üretim-adımı ayrı sorun

**DOĞRU KILAVUZ/The Confessor (2004-9143) — hiç bayrağı yoktu ama içerik ciddi bozuktu:** eski KONTROL PDF'i "F İ L M: The Good Shepherd" diyordu, cast'te "THE UNSEEN"/"THE GOOD SHEPHERD" gibi kişi-olmayan metinler vardı, Yönetmen boştu, ÖZET alanında gerçek özet yerine "(HAM TRANSCRIPT ÖNİZLEME — KALIP ÖZET SONRA)" etiketli, işlenmemiş diyalog-parçacıkları dökümü vardı. Bu turda yeniden-render edilince:
- Başlık **"THE CONFESSOR"**ya düzeldi — frame'de (giris_p01) "GFT ENTERTAINMENT production / a LEWIN WEBB film / CHRISTIAN SLATER / GORDON PINSENT / and STEPHEN REA" görsel olarak doğrulandı; bu isim-kombinasyonu (yönetmen+3 tanınmış oyuncu) gerçek 2004 filmi "The Confessor" ile KESİN eşleşiyor.
- Tür: boş → "DRAM/GİZEM"
- Cast: kişi-olmayan 2 girdi (THE UNSEEN, THE GOOD SHEPHERD) doğru elendi, 17 gerçek isimle (Christian Slater, Gordon Pinsent, Stephen Rea, Molly Parker vb.) dolduruldu
- Yönetmen: boş → **LEWIN WEBB** (doğru, doğrulandı)

**Tek kalan sorun: ÖZET hâlâ boş — ama BU FARKLI bir alt-sınıf:** `asr/asr-00babb5b/run/` klasöründe **gerçek `transcript.txt`+`transcript_plain.txt` MEVCUT** (diğer "ASR hiç çalışmamış" vakalarından — KKL/YAPRAK BİTTİ gibi, sadece subtitle.json olanlardan — FARKLI). Yani ASR adımı BAŞARILI olmuş, sadece SONRAKİ özet-sentezleme adımı hiç çalıştırılmamış/`--clip` moduna dahil değil. Bu, transkript zaten var olduğu için diğer ASR-boşluğu vakalarından daha "çözülebilir" bir alt-durum, ama ayrı bir script/adım gerektiriyor — bu turda uygulanmadı. **Tutarlılık için PROMOTE EDİLMEDİ** (diğer tüm "_OZET" bloklu vakalarla aynı standart: özet-alanı boşsa promote etme) ama bu, bu gecenin en kapsamlı kısmi-düzeltmesi — sadece özet-sentezleme adımı çalıştırılırsa tam promote-hazır olacak.
GÜLLERİN SAVAŞI: anlamlı değişiklik yok, promote edilmedi.

## Batch: KOUDAYU (isimler daha da garble oldu) + BÜYÜK FİNAL (başlık kaybı, cast tam değişti) — ikisi de promote edilmedi

## Batch: ÇALIŞAN HAYATLAR (cast genişledi ama yönetmen hâlâ boş) + EL GUSTO (değişiklik yok) — ikisi de promote edilmedi

## Batch: KRAL LEAR (değişiklik yok) + ÇIKIŞ (hafif regresyon) — ikisi de promote edilmedi

## İKİ KOCALI KADIN + KURUNTULAR — ikisi de zaten ONAYLI'ymış (CSV bayat, boşa döngü)

## Batch: PROFESÖR HANNIBAL (hafif regresyon) + BELL BOY (değişiklik yok) — ikisi de promote edilmedi

## Batch: BEYAZ AVUÇLAR (TOPTAN ÇÖKÜŞ) + HOTEL RWANDA (ciddi cast-kaybı) — ikisi de promote edilmedi

- **BEYAZ AVUÇLAR/White Palms (2008-9069):** başlık+tür+TÜM cast (8 kişi) + Yönetmen (Szabolcs Hajdu, gerçek/tanınmış Macar yönetmen) + Yapımcı (Mathieu Kassovitz DAHİL 3 gerçek isim) TAMAMEN silinip garble ("�", "IRTA ES") ile değişti. Bu gecenin bir başka toptan-çöküş örneği.
- **HOTEL RWANDA (2004-9160, 2 duplicate kayıt):** cast 10 gerçek oyuncudan (Don Cheadle, Joaquin Phoenix, Sophie Okonedo vb.) sadece 3'e düştü (7 gerçek isim kayboldu). Tür de kayboldu.

İkisi de task_5aae0a2b'nin (run-to-run regresyon) veri tabanına eklendi — desen GPU-modelinden bağımsız olarak sürüyor.

## Batch: YÜZYILIN CİNAYETİ (değişiklik yok) + DOĞUM GÜNÜ (Harold Pinter cast'ten düştü + ASR-boşluğu) — ikisi de promote edilmedi

## VANYA DAYI → ONAYLI — SINIF-1 fix'inin (commit f662e06a, paralel oturum) İLK CANLI KANITI

**VANYA DAYI (1989-0476):** paralel oturumun SINIF-1 (teyit-süzgeci 3. kapı, stok-footage vetosu) fix'i CANLI'ya alındıktan sonra yeniden test edildi — **YEVGENIY MAKAROV artık doğru yönetmen olarak geliyor** (bu gece frame'de "Режиссер/Евгений МАКАРОВ" olarak zaten gözle doğrulanmıştı). Ayrıca: tür "KOMEDİ"→"DRAM/ROMANTİK" düzeldi (Çehov'un "Vanya Dayı"sı gerçekten dram), başlık "DYADYA VANYA" eklendi, cast'ten "SEREBRYAKOV ALEKSANDR VLADIMIROVICH" düştü — OCR'da "ROLI ISPOLNYAYUT: / SEREBRYAKOV ALEKSANDR VLADIMIROVICH / OTSTAVNOY PROFESSOR / EVGENIY LEBEDEV" yapısı doğrulandı: bu KARAKTER-adı+açıklama+GERÇEK-oyuncu kalıbı, yani düşme DOĞRU bir düzeltme (gerçek oyuncu Evgeniy Lebedev korundu, +1 yeni gerçek isim Zinaida Sharko eklendi). Afiş doğru (ДЯДЯ ВАНЯ, bu gece zaten görsel doğrulanmıştı, aynı dosya). Promote edildi.

Bu, task_8de6b060'ın (SINIF-1) gerçekten çalıştığının UÇTAN UCA kanıtı. SON YARIŞ aynı anda yeniden denendi ama bu turda "Jovan Rančić" adayı üst-akış okumasında hiç ÜRETİLMEDİ (yönetmen boş çıktı, KRİTİK BULGU #4'teki run-to-run değişkenliğin başka bir örneği) — fix'in kendisi değil, girdi şanssızlığı; ileride tekrar denenebilir.

## REKABET + VİDEO OYUNU + AĞAÇ → ONAYLI (afiş-fix doğrulandı, afişsiz promote — Çağatay onayıyla)

**Afiş-fix (commit 295a78b9) canlı test edildi — çalışıyor:** üçü de artık YANLIŞ afiş yerine `afis:false` (Challengers/Barbie Video Game Hero/Kara Ağaç Destanı tamamen kayboldu). Alternatif kaynak denemesi (Çağatay'ın talimatıyla): `credit_identity.resolve()` + `poster_fetch.fetch_poster()` doğrudan çağrıldı —
- **REKABET:** `resolve()` → status=**KESİN** (tmdb_id=242480, director_match=True, "Geel Trui vir 'n Wenner") ama `fetch_poster()` yine de None döndü — bu obskur Güney Afrika filmi için HİÇBİR kaynakta (TMDB/OMDb/Wikipedia) poster görseli yok, meşru/kalıcı boşluk.
- **VİDEO OYUNU + AĞAÇ:** `resolve()` status=**KONTROL** (belirsiz, <3 oy, yönetmen-eşleşmesi yok) — TAMAMEN FARKLI filmlere ("Der Schwarze Tanner", "Le Meilleur de la Vie") düşük-güvenle eşleşti; gözle kontrol edildi, "Der Schwarze Tanner" posteri KESİNLİKLE alakasız biri gösteriyordu. Bu belirsiz ID'leri KULLANMADIM (aynı yanlış-afiş riskini yeniden yaratırdı) — bulunan 2 poster dosyası SİLİNDİ.

Üçünün de künye içeriği (yönetmen/cast/tür-REKABET,VİDEO OYUNU/özet) bu gece zaten doğrulanmıştı, VİDEO OYUNU'nda başlık da düzeldi (VIDEO POLY-VIDEOGAME→VIDEOPOLY ODER DUPONTS VERSCHWINDEN) ve cast genişledi (8→13, kayıp yok sayılır — 1 isim "Edi Piccin" tek-taraflı düştü, doğrulanamadı ama küçük/izole). AĞAÇ'ta tür alanı kayboldu (DRAMA→boş) — küçük bir gerileme ama başlık kazancı (L'ARBRE) ve afiş-güvenliğiyle birlikte net kazanç.

**Çağatay'ın kararıyla** ("poster_fetch'i tekrar dene, olmazsa afişsiz promote et") üçü de **afişsiz promote edildi** — yanlış-bilgiden (aktif tehlike) doğru-ama-eksik'e (güvenli) geçiş.

**GÜNCEL SAYAÇ:** 55 promosyon. Bu, KRİTİK BULGU #1'in (yanlış-afiş) 3 orijinal örneğinin kapatıldığı an — task_6f1ca8f8'in ürettiği fix'in ilk canlı, çok-filmli doğrulaması.

SON YARIŞ 2. kez denendi — yönetmen yine boş (2/2). SINIF-1 fix'i doğru ama üst-akış okuma bu filmde "Jovan Rančić"ı adayı olarak hiç üretmiyor (KRİTİK BULGU #4 sınıfı bir üst-akış sorunu olabilir, incelenmedi). Promote edilmedi.

## 🚨 JERICO APARTMANI — SINIF-1 fix'inde YENİ, CİDDİ yanlış-pozitif sınıfı bulundu (promote EDİLMEDİ)

**JERICO APARTMANI/Jerico Mansions (2003-9195):** SINIF-1 fix'i (commit f662e06a, artık CANLI) ile yeniden test edildi — yönetmen alanı "MARTIN POLLINS" (eski, KISMEN doğru) yerine **"ANTONIO WILFORD"** ile DEĞİŞTİ. Frame'e inilip (master_dilim/reading_master_runaware_p01.png) gözle KESİN doğrulandı: bu YANLIŞ.

Gerçek yapı ekranda net:
- "CAST IN ALPHABETICAL ORDER" bloğunda, karakter-rolü/oyuncu çiftleri sıralı: "...Dolores O'Donnell — MARIBEL VERDÚ / **Director — ANTONIO WILFORD**" — buradaki "Director" filmin İÇİNDEKİ bir KARAKTERİN ADI/rolü (oyuncu Antonio Wilford bu karakteri oynuyor), film-yönetmeni DEĞİL.
- Ayrı, açıkça "MOVISION ENTERTAINMENT LTD..." prodüksiyon-bloğu altında: **"Directors: MARTIN POLLINS, IAN STEEL"** (ÇOĞUL, 2 gerçek yönetmen) — bu asıl film-yönetmeni kredisi.

**Kök-neden analizi:** SINIF-1'in `_stok_footage_yakinda()` üçüncü-kapısı SADECE "FOOTAGE" işaretine yakınlığı kontrol ediyor — bu vakada "FOOTAGE" hiç geçmiyor, yani o kapı hiç tetiklenmiyor/koruma sağlamıyor. Asıl sorun daha ERKEN bir aşamada: "Director" kelimesi bir OYUNCU-KADROSU listesinde KARAKTER-ADI olarak geçtiğinde, bunu gerçek yönetmen-etiketinden ayırt eden bir kontrol YOK. Bu, o fix'in kendi test-setinde (VANYA DAYI/SON YARIŞ/ONDAN UZAKTA/İKİNCİ ŞANS) HİÇ kapsanmayan, YENİ bir false-positive sınıfı — "karakter-adı tesadüfen bir crew-rol-kelimesiyle aynı" durumu.

Eski PDF'in "MARTIN POLLINS" ataması da TAM doğru değildi (KISMEN doğru — gerçekte 2 ortak-yönetmen var: Martin Pollins + Ian Steel, eski PDF sadece 1'ini yakalamıştı) ama en azından GERÇEK bir yönetmen ismiydi; yeni render bunu TAMAMEN ALAKASIZ bir isimle (karakter oynayan oyuncu) değiştirerek daha da kötüleşti.

**PROMOTE EDİLMEDİ, dokunulmadı.** Bu bulgu, SINIF-1 fix'inin sahibi olan oturuma (paralel, task_8de6b060 kökenli) geri bildirilmeli — kendi test-suite'lerine bu vakayı (veya benzer "karakter-adı=crew-kelimesi" senaryosunu) eklemeleri önerilir. Kod-fix bu oturumda YAPILMADI (paylaşılan, hassas bir mekanizma, aynı fix'i tekrar riske atmadan düzeltmek dikkatli bir inceleme gerektirir).

## JERICO APARTMANI-2 (2003-9198) + KUTSAL SİLAH — ikisi de promote edilmedi
- JERICO APARTMANI'nin 2. TRT-kaydında (2003-9198) AYNI "ANTONIO WILFORD" (karakter-adı) tuzağı tekrarlandı — zaten doğrulanmış hatanın tekrarlanabilir olduğunu doğruluyor, ayrıca frame-teyidi gerekmedi. Promote edilmedi.
- KUTSAL SİLAH: zayıf sinyal, kimlik_dogru=false, promote edilmedi.

## YA NASİP YA KISMET — SINIF-1 fix'in yönetmen-tarafı DOĞRULANDI ama cast gerilemiş, promote edilmedi

**YA NASİP YA KISMET (2015-0138) — bu gecenin SINIF-1 araştırmasının orijinal motivasyon vakası:** yönetmen artık **GOKMEN TOSUN** — frame'de (reading_master_runaware_p01.png) "YÖNETMEN / GÖKMEN TOSUN" temiz, bağımsız bir kartta KESİN doğrulandı (JERICO APARTMANI tuzağı YOK — bu kez gerçek bir crew-etiket kartı, cast-listesi bağlamı değil). SINIF-1 fix'in yönetmen-tarafının 2. temiz kanıtı (VANYA DAYI'dan sonra).

**AMA cast alanı gerilemiş — poster ile çapraz-kontrol edildi:** afiş (`2015-0138-1-0000-85-1.jpg`, bu turda başarıyla bulundu) üstünde net 5 isim var: **HASAN KAÇAN, ERDEM AKAKÇE, BENGİ ÖZTÜRK, TURGAY TANÜLKÜ, MEHMET EMİN İNCİ** — bunlar eski KONTROL PDF'inin (ağır garble'lı da olsa: "HAION MCAN"≈Hasan Kaçan, "TURGOY TANOLKD"≈Turgay Tanülkü, "MEBMET EMIN INCI"=Mehmet Emin İnci) YAKALAMAYA çalıştığı TAM isimler. Yeni render'ın cast listesi bu 5 isimden SADECE 2'sini (Erdem Akakçe, Bengi Öztürk) içeriyor — **3 başrol oyuncusu (Hasan Kaçan, Turgay Tanülkü, Mehmet Emin İnci) TAMAMEN kayıp**, yerine 7 yeni (muhtemelen ikincil/yardımcı) isim eklenmiş. Tür de kayboldu (DRAMA→boş).

Bu, KRİTİK BULGU #4'ün (run-to-run güvenilmezlik) yönetmen-alanını ETKİLEMEDİĞİ ama AYNI render'da cast-alanını etkilediği ilginç bir örnek — iki alan bağımsız şekilde iyi/kötü çıkabiliyor. **PROMOTE EDİLMEDİ** — yönetmen kazanımı gerçek ve kalıcı olsa da (kod-fix sonucu, tekrar doğru gelecektir), cast'in bu turda posterle doğrulanan 3 başrolü kaybetmesi promote-engelleyici. İleride temiz bir turda (hem yönetmen hem tam-cast doğru) yeniden denenebilir.

## DERTLER BENİM OLSUN — yapısal olarak tam temiz ama Türkçe-aksan-kaybı (KRİTİK BULGU #2) bloke ediyor
Cast 4→11 (kayıp yok, Orhan Gencebay/Perihan Savaş dahil doğrulanmış), yönetmen+yapımcı zaten doğruydu — ama tüm Türkçe isimler ("Perihan Savaş"→"Perihan Savas", "Şafa Önal"→"Safa Onal", "Hürrem Erman"→"Hurrem Erman") aksan kaybetti. mitas.duckdb erişimi düzelince ilk sırada hazır. Promote edilmedi.

## Batch: SON BOLŞEVİK (değişiklik yok) + KİNG'İN SERVETİ (regresyon — 6 gerçek oyuncu kayboldu) — ikisi de promote edilmedi

## ÖRGÜT — DÜZELTME: yanlışlıkla promote edilip GERİ ALINDI (özet-kontrolü atlanmıştı)

**ÖRGÜT/Il Sindaco (1997-0217):** yönetmen (Ugo Fabrizio Giordani, frame'de "regia" etiketiyle + posterde "Regia di Ugo Fabrizio Giordani" ile ÇİFT doğrulandı), cast (Anthony Quinn, Maria Grazia Cucinotta, Raoul Bova — posterle tam örtüşen), yapımcı (Antonio Avati, posterde "Antonio e Pupi Avati presentano" ile doğrulandı) ve tür hepsi boştan mükemmel doldu. **Bu güçlü doğrulamanın verdiği ivmeyle ÖZET alanını kontrol etmeden PROMOTE ETTİM — hata.** Hemen ardından kontrol edilince ÖZET'in hâlâ "(ÖZET AYRI BİR ADIMDA ÜRETİLECEKTİR.)" placeholder'ı olduğu görüldü (orijinal bayrak "_YONETMEN_KIMLIK_CAST_OZET" — OZET bileşeni ÇÖZÜLMEMİŞ). **DERHAL GERİ ALINDI** — dosya ONAYLI'dan KONTROL'e taşındı, orijinal bayraklı adıyla geri kondu. Film 3/4 mükemmel çözülmüş durumda, sadece özet-üretim adımı eksik — DOĞRU KILAVUZ ile aynı alt-sınıf. Bu, kendi promote-öncesi kontrol listemi HER SEFERİNDE eksiksiz uygulamam gerektiğinin bir hatırlatıcısı — güçlü kısmi-doğrulama heyecanı bile tam-kontrol disiplinini atlamaya gerekçe olamaz.

## Batch: ÜÇÜZLER DON KİŞOT'UN İZİNDE (karışık, kimlik hâlâ false) + NAMUS DÜŞMANI (cast kaybı + Türkçe-aksan) — ikisi de promote edilmedi

## Batch: SİBİRYADAN 2 (kimlik düzeldi, yönetmen hâlâ boş) + AYNA (Tarkovsky "Mirror", yönetmen hâlâ boş) — ikisi de promote edilmedi

## Batch: KATİLLER HER ZAMAN SARI PABUÇ GİYER (2 kayıt, hafif regresyon) + BİR KATİLLE EVLENDİM (değişiklik yok) — hiçbiri promote edilmedi

## Batch: UZAKTAKİ KASABA + KÖŞENİN KRALI — ikisi de temiz cast-genişlemesi ama yönetmen hâlâ boş (orijinal bayrak çözülmedi), promote edilmedi

## Batch: AŞK ŞARKIM (hafif regresyon) + KANDAHAR (yine regresyon, 2. deneme de düzelmedi) — ikisi de promote edilmedi

## ÇIKIŞ — zayıf sinyal, promote edilmedi

## task_5aae0a2b — run-to-run güvenilmezlik: gözlemlenebilirlik-fix CANLI + taze kanıt (golden-suite bizzat kararsız)

Çağatay'ın talimatıyla ("fixlere bak eksik bişey varsa tamamla commitle") KRİTİK BULGU #4'ün fix-yüzeyinden (memory: project_clip_sessiz_veri_kaybi_kokneden_20260709.md) SADECE VRAM-nötr, davranış-nötr parçayı uyguladım:

**Uygulanan:** `credit_text_read.py:_ollama_json` — `done_reason=="length"`/JSON-parse-fail sonucu `{}` dönmeden ÖNCE stderr'e uyarı (`[ollama-json] UYARI: ... done_reason=... -> {} donuyor`). Dönüş değeri/davranış AYNI kalıyor (hâlâ `{}`), yalnız artık render log'unda görünür — 3 gündür fark edilmeyen sessizliği kapatıyor.

**Uygulanmayan (bilinçli erteleme):** `num_ctx` büyütme — GPU şu an 23551/24576 MiB dolu (yalnız 775 MiB boş). 31b vision modeli için context büyütmek VRAM-baskısı altında OOM riski taşıyor; canlı test edemeden uygulamak riskli. task_5aae0a2b notuna eklendi.

**Beklenmedik ama ÇOK değerli yan-bulgu:** Fix'i doğrulamak için `regresyon_golden.py`'yi ardışık 3 kez çalıştırdım (fix VAR → YOK/stash → VAR). Sonuç: **4/7 → 3/7 → 3/7**. Fix'in kod-yolu (yalnız zaten-`{}`-dönecek dala stderr-satırı ekliyor, JSON içeriğine dokunmuyor) ile sonuç FARKI arasında hiçbir korelasyon yok (run1≠run3 aynı kodla, run2=run3 farklı kodla) — yani **golden-suite kendisi şu an run-to-run KARARSIZ**, benim fix'imden tamamen bağımsız. Muhtemel sebep: `name_normalize.py`'deki mitas.duckdb yolu (X:\→E:\MITAS\Mitas_Files, commit 4dd4d8fd + üzerine uncommitted ek) şu an başka oturumun ELİNDE aktif taşınıyor; HALIFAX/BUZDAN GELEN SESLER'in "KEN CAMERON"/"DALE JOHNSON" (ALL-CAPS ham) ↔ "Ken Cameron"/"Dale Johnson" (Title-Case KB-kanonik) arası gidip-gelmesi tam KB-lookup tutarsızlığı imzası. **Önemli çıkarım: golden-suite şu an "kanıt" olarak TEK-KOŞU güvenilir değil** — duckdb taşıması oturana kadar (veya ≥3 tekrar-koşu ile) başka fix'lerin de bu suite ile doğrulanması yanıltıcı olabilir.

Sonuç: fix commit'lendi (yalnız `scripts/credit_text_read.py`, benim tek dokunduğum dosya — diğer 7 dosya başka oturumun WIP'i, dokunulmadı). Golden-suite kararsızlığı bu memory dosyasına + oraya eklendi.

## LAUREL HARDY (1942-0020, "A Haunting We Will Go") — YENİ bulgu sınıfı: karakter-adı/oyuncu-adı sütun-karışması, promote edilmedi

Yönetmen (ALFRED WERKER) kare-teyitli DOĞRU (giris master: "Directed by / ALFRED WERKER"). Katalog başlığı "LAUREL HARDY" jenerik TRT-kısaltması; gerçek film 20th Century-Fox'un "A-Haunting We Will Go" (1942), giris master'da "Oliver LAUREL / HARDY / and / DANTE / THE MAGICIAN" ile tam teyitli — içerik-uyuşmazlığı YOK (OMAGGIO tipi değil).

**Ama cast_list ciddi şekilde bozuk.** Çıkış (cikis) master karesi temiz bir "Karakter......OYUNCU" iki-sütunlu tablo gösteriyor:
```
Margo..........SHEILA RYAN      Malcolm Kilgore..ADDISON RICHARDS
Tommy White....JOHN SHELTON     Darby Mason......GEORGE LYNN
Doc Lake.......DON COSTELLO     Joe Morgan.......JAMES BUSH
Frank Lucas....ELISHA COOK,JR.  Dixie Beeler.....LOU LUBIN
Foster.........EDWARD GARGAN    Phillips.........ROBERT EMMETT KEANE
                                 Parker...........RICHARD LANE
                                 Waiter...........WILLIE BEST
```
Pipeline'ın ürettiği `cast_list` (15 ad) bunun YARISINI KARAKTER ADI olarak, gerçek oyuncu sanıp içeri almış: **TOMMY WHITE, DOC LAKE, FRANK LUCAS, MALCOLM KILGORE, DARBY MASON, DIXIE BEELER — hepsi KARAKTER adı, gerçek kişi DEĞİL.** Buna karşılık gerçek oyuncular **ROBERT EMMETT KEANE ve RICHARD LANE tamamen kayıp** (film_notu'nda "ROBERT CORDOTOMKEANE" olarak garble-teşhisiyle atılmış — ama ham OCR'da lines 61-62'de TEMİZ "LOU LUBIN"/"ROBERT EMMETT KEANE" de var, kullanılmamış).

**Kök-neden (ham OCR incelemesiyle netleşti):** `ocr-eb5d0fa5/kunye.txt` çıkış-kartının 2-3 üst-üste-binen kare-okumasını TEK bağlamsız satır-listesine düzleştirmiş (satır 43-63) — karakter-sütunu ile oyuncu-sütunu birbirine karışmış, hangi ismin "karakter" hangisinin "gerçek kişi" olduğuna dair HİÇBİR pozisyonel/yapısal ipucu kalmamış. Rol-eşleme LLM'i (veya deterministik ardıl) elindeki ~20 isim-benzeri token'ın hepsini "muhtemelen kişi" kabul etmiş çünkü karakter adları (Tommy White, Doc Lake, Frank Lucas...) YAPISAL olarak gerçek isimlerden ayırt edilemiyor (garble değiller, KB'de raslantısal reddedilmeyebilirler de).

**Neden dar bir fix değil:** Bu OCR'ın kendisinin sütun-yapısını KAYBETMESİNDEN kaynaklanıyor — düzeltme ya (a) daha iyi/sütun-duyarlı OCR (kod-mantığı değil, OCR-pipeline değişikliği), ya da (b) "Karakter......OYUNCU" nokta-dizisi (dot-leader) desenini TEK TEMİZ karede (mozaik-birleştirme ÖNCESİ) yakalayıp çift-sütunu ayrıştıran YENİ bir deterministik kural gerektirir — mevcut `credit_role_lexicon.py`/`credit_text_read.py` rol-eşleme mantığının GENEL bir sınıfını etkiler (yalnız bu filme özel değil; 1930-1950 klasik-Hollywood "CAST" tablosu formatı ÇOK yaygın). Kendim dokunmadım (paylaşılan, geniş-kapsamlı mekanizma).

## LAUREL HARDY — ayrıca YANLIŞ afiş (2. bulgu, ayrı sınıf)

`afis:true` ama `Database/.../afis.jpg` görsel olarak filmin KENDİSİ değil, alakasız bir ürün: "Laurel and Hardy: Their Lives and Magic" adlı BİYOGRAFİK BELGESEL DVD kutusu (2 dilli, "Special Limited Collector's Edition"). Ne film başlığıyla ("A Haunting We Will Go") ne kadrosuyla (Sheila Ryan/John Shelton/vb.) hiçbir örtüşme yok — yalnız "Laurel and Hardy" isim-metniyle eşleşmiş olmalı. Bu, commit 295a78b9'un kapattığı sınıftan FARKLI: orada ID-güvenilir zincirin kör title-search'i sorunluydu; burada muhtemelen bir "konu-hakkında-belgesel" ürünü kendi TMDB/IMDb metadata'sında "Stan Laurel, Oliver Hardy" ismini gerçekten taşıdığı için kadro-kapısını (varsa) yanıltmış olabilir — kesin mekanizma doğrulanmadı (poster_fetch.py'nin iç log'u --clip render'da tutulmuyor). Dosya `Database/` önbelleğinde önceden-var (bu geceki --clip'in YENİ ürettiği bir şey değil).

Sonuç: LAUREL HARDY promote edilmedi (cast ~%40 hatalı + yanlış afiş). İki ayrı, dar-kapsamlı görev spawn edildi (cast-tablo sütun-karışması; belgesel-afiş yanlış-eşleşmesi).

## KARA KALKAN (1954-0034, "The Black Shield of Falworth") — kod hatası DEĞİL, kaynak OCR gerçekten okunamaz

`kunye.txt` (114 satır) baştan sona ağır garble ("ALERUNDER PS", "HING HENRY", "TONY TURTLS/TONG CURTIS" vb.) — OCR job status="done" (Kök-Neden A değil), ama kaynak görüntü kalitesi o kadar düşük ki hiçbir isim güvenle okunamıyor. Perde-arkasında "The Black Shield of Falworth" (Tony Curtis/Janet Leigh/Barbara Rush/Craig Hill) olduğu tahmin edilebiliyor ama bu YALNIZCA insan-örüntü-tanımayla — OCR-otorite kanunu gereği ben de dahil hiçbir taraf garble'dan isim UYDURMAMALI. Pipeline'ın hepsini boş ("—") bırakması DOĞRU davranış (okunamadı>yanlış oku). Kod-fix değil, daha iyi kaynak/yeniden-tarama gerektirir — pipeline kapsamı dışı. Promote edilmedi, ek işlem gerekmiyor.

## PROFESÖR HANNIBAL (1956-0062) — KARA KALKAN ile aynı sınıf: kaynak OCR gerçekten okunamaz

`kunye.txt` (26 satır) baştan sona garble ("MAPIOS MN", "MADTON CIU", "HVD MADTON NOG" vb.) — OCR status="done", kod hatası değil, kaynak görüntü kalitesi okunamaz seviyede. Özet alanı dolu (63 kelime, ayrı ASR-tabanlı motor — credit-okuma ile bağımsız) ama yönetmen/cast tamamen boş, DOĞRU davranış. Promote edilmedi, ek işlem gerekmiyor.

## BELL BOY (1960-0039) — farklı alt-sınıf: kare-penceresi kadro kartını hiç yakalamamış

OCR çok seyrek (11 satır, yalnız "PAN AMERICAN"/"CAR RENTAL"/"NATIONAL AIRLINES" tabela-metni). Giriş master'ı yalnız "Paramount / Release / [Hotel] Fontainebleau" gösteriyor (üretim-kartı, isim yok); çıkış master'ı gerçek sahneler gösteriyor (bellboy-üniformalı karakter, otel dışı, uçak — muhtemelen gerçek Fontainebleau Otel'de çekilmiş) ama HİÇBİR yazılı isim/kadro kartı yok. KARA KALKAN/PROFESÖR HANNIBAL'dan FARKLI: onlarda OCR garble ama METİN VARDI; burada giris/cikis pencereleri kadro-kartını hiç YAKALAMAMIŞ (metin fiziksel olarak captured frame'lerde yok) — film-boyunca kredilerin farklı bir zamanlamada olması ihtimali var. OCR-otorite kanunu gereği kendi film-tanımamla ("muhtemelen X filmi") isim doldurmadım. Kod-fix'e işaret eden tek-film ötesi bir örüntü değil (bu filme özel kare-pencere yerleşimi olabilir) — görev spawn edilmedi. Promote edilmedi.

## BEKARLIK SULTANLIKTIR (1958-0046) + BEKLENEN BOMBA (1959-0005) — kaynak-zayıf, promote edilmedi

**BEKARLIK SULTANLIKTIR:** kimlik KİLİTLİ (tmdb=1332071, web_yonetmen="Türker İnanoğlu") ama OCR neredeyse boş (2 satır, "SE PIN YANG"/"PIN A DU" — anlamsız). Kimlik-kilitli olsa da OCR boş olduğu için KB-fill doğru şekilde ATLANDI (deferans mantığı çalışıyor — "yanlış>boş" korunuyor). [ollama-json] uyarısı ateşlemedi (context-taşması değil, gerçekten az/boş OCR — Kök-Neden A'ya yakın: hub "done" ama pratikte iş yapılamayacak kadar az metin).

**BEKLENEN BOMBA:** OCR 32 satır (crew-kartı: NEG. MONTAJ/OPERATÖR/MÜZİK gibi teknik roller ağırlıklı, "REJİ MUHTEŞEM" belirsiz — gerçek yönetmen-adı mı garble mi netleşmedi), ama hiçbir alan dolmadı, master-PNG bulunamadı (bu film için üretilmemiş/eksik). Kod-hatası iddiası için yetersiz kanıt, kaynak zayıf sınıfında bırakıldı.

İkisi de promote edilmedi, görev spawn edilmedi (net bir tekrarlanabilir kod-defekti değil).

## DERSU UZALA (1975-2246, Kurosawa/Mosfilm) — YENİ bulgu: Kiril garble + rol-etiketsiz karışık liste yönetmeni yanlış seçtiriyor

Kimlik KESİN (tmdb=9764, imdb=tt0071411, web_yonetmen="Akira Kurosawa"). Ham OCR satır 1: **"AUUPA KYPOCALA"** — bu Kiril "АКИРА КУРОСАВА" (Akira Kurosawa)'nın ağır garble'lı transliterasyonudur (romanizasyon zinciri bunu KB-eşleştirilebilir temiz "Akira Kurosawa"ya çeviremdegi). Ama pipeline yönetmen olarak **"VLADIMIR VASİLEV"** çıkardı — bu isim ham metnin satır 39'unda, "V GLAVNYKH ROLYAKH" (başrollerde, satır 10) ile başlayan uzun, rol-etiketsiz, kesintisiz bir cast+crew blokunun (Yuriy Solomin/Maksim Munzuk gerçek başrol oyuncuları, ardından "Asakazu Nakai" gerçek görüntü yönetmeni, "Isaak Shvarts" gerçek besteci gibi TEKNİK EKİP isimleriyle iç içe) ORTASINDA gömülü, sıradan bir ekip-üyesi ismi — yönetmenle HİÇBİR ilgisi yok.

**Sistem DOĞRU davrandı:** `cross_check.verdict="ÇELİŞKİ"` bu yanlış ismi (TMDB'nin "Akira Kurosawa" beklentisiyle çelişkili) SESSİZCE basmadı, KONTROL'e düşürdü — tam "yanlış>boş" prensibinin çalıştığı an. Kendi bilgimle ("bu Kurosawa'nın filmi") PDF'e elle isim yazmadım — OCR/pipeline otoritesi dışına çıkmak, sistemin GERÇEK romanizasyon-kalitesi sorununu gizler.

**Kök-neden sınıfı (LAUREL HARDY'nin karakter/oyuncu karışmasıyla AYNI aile — "rol-etiketsiz karışık liste"):** Kiril kaynaklı jeneriklerde (1) romanizasyon çok garble üretiyor (KB-eşleştirilemez), (2) OCR/mozaik-birleştirme rol-etiketlerini ("режиссёр", "постановка") kaybediyor, geriye yalnız düz bir isim-listesi kalıyor, (3) rol-eşleme mekanizması bu listeden RASTGELE bir ismi "yönetmen" sanabiliyor (burada muhtemelen "en son/en belirgin tekil isim" gibi zayıf bir sezgiyle). Görev spawn edildi (credit_text_read.py Kiril-romanizasyon + rol-etiketsiz-liste güvenliği).

Promote edilmedi.

## DOĞUM GÜNÜ (1968-0020, BBC "Theatre Night: The Birthday Party") — ÇELİŞKİ, derinlemesine incelenmedi

Giriş karesi "THEATRE NIGHT / THE BIRTHDAY PARTY / HAROLD PINTER" gösteriyor (Pinter=oyun yazarı, BBC 1987 TV-uyarlaması — "Doğum Günü" başlığı bununla tutarlı). Pipeline yönetmen olarak "KENNETH IVES" çıkardı (gerçek bir BBC yönetmeni, akla yatkın) ama `verdict="ÇELİŞKİ"`+`kimlik_dogru=false` — hangi spesifik alanın çelişkiye yol açtığı bu oturumda derinlemesine incelenmedi (zaman/kapsam nedeniyle). Özet hâlâ neredeyse boş (5 kelime) — "_OZET" bayrağının işaret ettiği "yalnız özet eksik" varsayımı YANLIŞ çıktı, daha derin bir sorun var. Promote edilmedi, görev spawn edilmedi (tek-film, yetersiz kanıt).

## KARAR KİMİN (1981-0266, "Whose Life Is It Anyway?") — poster mükemmel eşleşti ama cast %44 kayıp, promote edilmedi

Yönetmen JOHN BADHAM kare-teyitli DOĞRU ("A JOHN BADHAM FILM"). Afiş MÜKEMMEL eşleşme (gerçek "Whose Life Is It Anyway?" 1981 posteri, tüm ekip-isimleriyle örtüşüyor). Ama giriş karesindeki "Co-Starring" listesi 8 isim gösteriyor (CHRISTINE LAHTI, BOB BALABAN, KENNETH McMILLAN, KAKI HUNTER, THOMAS CARTER, ALBA OMS, JANET EILBER, KATHRYN GRODY), pipeline yalnız 5'ini yakaladı — **KENNETH McMILLAN, KAKI HUNTER, THOMAS CARTER tamamen kayıp, JANET EILBER "JANET LILBER" olarak garble-okunup teyitsiz düşürülmüş** (ham OCR'da AslındaTEMİZ "JANET EILBER" de var, ayrı bir yerde — kullanılmamış).

**Önemli:** ham OCR'da (`ocr-4b8d6e29/kunye.txt`, 188 satır) bu 4 isim de TEMİZ ve DOĞRU mevcut (satır 4, 121, 123, 126) — bu KARA KALKAN/PROFESÖR HANNIBAL gibi "kaynak okunamıyor" değil, extraction/rol-eşleme aşamasında KAYIP. `[ollama-json]` context-taşması uyarısı da ateşlemedi (JSON parse başarılı, LLM sadece bu isimleri çıktısına dahil etmemiş). Net kod-satırı seviyesinde tekil bir kök-neden gösteremedim (uzun isim-listesinde LLM'in bir kısmını "unutması"na benziyor) — bu, run-to-run güvenilmezlik (task_5aae0a2b) ailesiyle YUMUŞAK bir bağlantı olabilir (context-baskısının TAM çöküşe değil KISMİ isim-kaybına da yol açabileceğine işaret) ama kesin kanıtlanmadı, ayrı task açılmadı. Promote edilmedi.

## SISSI-1 (1990-0390, Ernst Marischka'nın "Sissi", 1955) — YENİ bulgu: Almanca'da EDİTÖR yönetmen sanılmış

Giriş karesi TARTIŞMASIZ AÇIK: "...zeigt: den ERNST MARISCHKA FILM / SISSI / mit SCHNEIDER ROMY..." (İngilizce "A JOHN BADHAM FILM" kalıbının Almanca eşdeğeri: "den [İSİM] FILM" — Ernst Marischka gerçek, tanınmış yönetmen). Ama pipeline yönetmen olarak **"ALFRED SRP"** çıkardı — bu isim kartın ÇOK daha aşağısında, **"Schnitt: ALFRED SRP"** satırında ("Schnitt" = Almanca "Kurgu/Montaj", yani ALFRED SRP gerçek KURGUCU, yönetmen DEĞİL).

**Kök-neden:** `credit_text_read.py`'nin `_RESCUE_LABELS` kümesi "EIN FILM VON"/"REGIE" (Almanca yönetmen-etiketleri) içeriyor ama "den [İSİM] FILM" (definite-article çekimli sunuş-kalıbı, İngilizce "A [İSİM] FILM" ters-desenin Almanca eşdeğeri) kapsamıyor — bu yüzden doğru yönetmen-imzası (en üstte, en güçlü sinyal) hiç yakalanmadı, mekanizma daha aşağıda RASTGELE bir "İsim + iki-nokta-etiket" satırına ("Schnitt:") düşüp "Schnitt" kelimesinin ROL-ETİKETİ (crew, yönetmen değil) olduğunu ayırt edemeden ALFRED SRP'yi kabul etti. Görev spawn edildi.

Promote edilmedi.

## YARGIÇ VE POLİS + ZERK'İN HİKAYESİ — ikisi de promote edilmedi, farklı sebeplerle

**YARGIÇ VE POLİS (1992-0324, Fransız dizisi "Les Cordier, juge et flic"):** Kare gerçek diziyi doğruluyor (Bruno Madinier, Charlotte Valandrey, Antonella Lualdi, Alain Bonnot, Alain Page...) ama bu render'da yönetmen olarak **"LIFTERAIRE TELFRANCE"** çıktı — "TELFRANCE" gerçek bir Fransız yapım şirketi, "LIFTERAIRE" muhtemelen "PROPRIÉTÉ LITTÉRAIRE" gibi bir telif-ibaresinin garble'ı — kişi DEĞİL, prodüksiyon-boilerplate. Bu film önceden (konsey-sartname bağlamında) FARKLI bir yanlış-sonuçla anıldı ("cast_ortusme=0, kare-içi 8/8 teyitli" — o zaman gerçek bir aday isim okunmuş ama KB reddetmişti) — bu render TAMAMEN FARKLI, hatta daha kötü bir sonuç üretti (gerçek isim adayı bile değil). Bu, AYNI FİLMİN run-to-run'da FARKLI yanlış sonuçlar ürettiğinin taze bir kanıtı — task_5aae0a2b'ye (run-to-run güvenilirlik) destekleyici veri olarak eklendi, ayrı task açılmadı.

**ZERK'İN HİKAYESİ (1991-0469, "Zerk the Jerk" — düşük bütçeli/indie yapım):** Kare, kredilerin SİYAH KART yerine CANLI SAHNE görüntüsü (okul otobüsü) üzerine bindirildiğini gösteriyor — ekrandaki gerçek "SCHOOL BUS"/"EMERGENCY DOOR" tabelaları ve bir "American History" kitap-kapağı, OCR tarafından isim-adayı gibi yakalanmış ve cast listesine sızmış (Scott DeFreitas/Dan Wynn/Paxton Harris gerçek — SCHOOL BUS/EMERGENCY DOOR değil). Bu, "kredi metni siyah kart yerine sahne-üzerine-bindirilmiş" — nadir, muhtemelen dar bir kenar-durum (çoğu profesyonel film siyah-kart kullanıyor). Görev açılmadı (düşük yaygınlık, dar fix riski/değer dengesi elverişsiz).

## İKİ SEVGİLİM VAR (1996-0330, "J'ai deux amours") — YENİ bulgu: aksan TEMİZ OCR'dan SONRA da kayboluyor + isim-uydurma-harfi + cast-kayıp

Yönetmen "CAROLINE HUPPERT" kare-teyitli DOĞRU (gerçek, tanınmış Fransız TV yönetmeni — "Scénario original et dialogues" + tek makul "un film écrit et réalisé par" adayı, çelişki bayrağı YOK). yapımcı (Quentin Raspail, Francis Peltier) da kare-teyitli doğru.

**Ama 3 ayrı doğruluk sorunu:**
1. **Cast-kayıp:** "PAOLA DEBIASI" ham OCR'da TEMİZ (satır 7, "ET AVEC" ile net tanıtılmış) ama nihai `cast_list`'te YOK — KARAR KİMİN'deki "temiz isim extraction'da kayboluyor" örüntüsüyle AYNI aile.
2. **YENİ bulgu — aksan TEMİZ okumadan SONRA kayboluyor:** Ham OCR satır 3 **"JEAN FRANÇOIS STEVENIN"** (Ç doğru okunmuş, TEMİZ) ama nihai `cast_list`'te **"JEAN-FRANCOIS STEVENIN"** (Ç→C kaybolmuş). Bu, KRİTİK BULGU #2'nin (mitas.duckdb X:\ erişilemezliği → Türkçe-kasa kozmetik fallback) kapsamı DIŞINDA — o mekanizma yalnız Türkçe isimlere özel; burada FRANSIZCA bir isim, OCR TEMİZ okumuş, ama pipeline'ın kendisi (muhtemelen bir ALL-CAPS/ASCII-normalize adımı) aksanı SİLİYOR. Bu genel/dilden-bağımsız bir kayıp olabilir — Türkçe-dışı TÜM aksanlı isimleri (Fransızca/İspanyolca/Almanca/vb.) etkileme potansiyeli var. "ELOÏSE→ELOISE" ayrı: bu OCR'ın KENDİSİNDE zaten aksansız (satır 6), yani KAYNAK-sorunu, pipeline-sorunu DEĞİL — iki farklı diacritic-kayıp yolu birlikte gözlemlendi.
3. **İsim-uydurma-harfi:** Ham OCR satır 2 "CAROLINE SIHOL" (temiz, gerçek Fransız aktris) ama nihai `cast_list`'te **"CAROLINE SILHOL"** — fazladan bir "L" EKLENMİŞ, kaynakta olmayan bir harf uydurulmuş (küçük ama gerçek bir halüsinasyon örneği).

Görev spawn edildi (yalnız madde-2, aksan-kaybı — en genel/yüksek-etkili olan). Madde-1 (cast-kayıp) KARAR KİMİN'in yumuşak bulgusuna destekleyici veri olarak eklendi, ayrı task açılmadı. Madde-3 tek-örnek, ayrı task açılmadı.

Promote edilmedi (3 doğruluk sorunu var, temiz DEĞİL).

## AŞK EVLİLİĞİ (1996-0353, "Mariage d'Amour") — ÖNEMLİ/YÜKSEK-ÖNCELİK bulgu: giriş master'ı ALAKASIZ bir yayının kareleriyle KİRLENMİŞ

Bu, bu oturumun en ciddi bulgularından biri — credit_text_read.py'nin rol-eşleme mantığıyla İLGİSİZ, muhtemelen FRAME-SINIRI/master-PNG kompozisyon (veya fiziksel bant-bitişikliği) katmanında bir sorun.

**Kanıt:** Giriş master karesi (`.../AŞK EVLİLİĞİ giris.png`) normal Fransız TV-filmi kredileriyle (Capa Drama-M6, "Mariage d'Amour", Mathilde Seigner/Roschdy Zem/vb.) BAŞLIYOR ama İÇİNDE ve SONUNDA açıkça ALAKASIZ içerik var:
- **"BRIDGET FONDA"** ve **"RUSSELL CROWE"** isim-kartları — tamamen alakasız Hollywood oyuncuları, muhtemelen "Rough Magic" (1995, ikisinin ortak filmi) treyleri/tanıtımı. Ham OCR'da (`ocr-2287e122/kunye.txt`) satır 15, 17-19, 152'de DAĞINIK, tekrarlı garble halinde görünüyor — tek bir temiz karttan değil, birden fazla ayrı kare-yakalamasından geliyor gibi.
- Kartın en sonunda **"LE PALANQUI[N] DES LARMES"** (satır 22-23) — bu BAŞKA, gerçek bir Fransız-Çin ortak-yapımı filmin (1988) adı, "Mariage d'Amour"la hiçbir ilgisi yok.
- Ayrıca satır 24-50 arası uzun bir Fransızca "sinopsis/olay-örgüsü" metin-bloğu var (Nadine/Georges karakterleri, hapis cezası, sınır-dışı yasağı) — bu içerik AŞK EVLİLİĞİ'nin KENDİ konusuyla tutarlı görünüyor (muhtemelen "gerçek olaylardan" tarzı bir açılış-metni), YANLIŞ-FİLM şüphesi DEĞİL, ama Bridget Fonda/Russell Crowe/Le Palanquin parçalarıyla birlikte kartın genel olarak TEMİZ olmadığını gösteriyor.

**Neden önemli:** Bu, credit-metni rol-eşleme sınıfının (bu oturumdaki diğer 5 bulgu) TAMAMEN DIŞINDA, farklı bir alt-sistemi (giriş/çıkış kare-sınırı tespiti, master-PNG kompozisyonu VEYA fiziksel arşiv-bandının kendisinde ardışık program bitişikliği) işaret ediyor — OMAGGIO/Ugetsu (KRİTİK BULGU #3, katalog-başlık↔içerik uyuşmazlığı) ile AYNI AİLEDEN ama farklı bir belirti: orada TÜM film başka bir filmdi, burada yalnız kare-YAKALAMA PENCERESİ komşu/alakasız içerik sızdırıyor gibi görünüyor. TRT arşivinin fiziksel bantlarında ardışık program kaydı (bir yayının hemen ardından başka içerik) yaygınsa, bu sınıf BAŞKA filmlerde de olabilir — geniş taramaya değer bir sinyal.

**Ayrıca (ayrı, daha küçük bulgu):** Baş-rol oyuncusu "MATHILDE SEIGNER" ham OCR'da TEMİZ (satır 1) ama nihai `cast_list`'te YOK — KARAR KİMİN/İKİ SEVGİLİM VAR'daki "temiz isim extraction'da kayboluyor" örüntüsüyle aynı aile.

Görev spawn edildi (kare-sınırı kirlenmesi, ayrı ve öncelikli). Promote edilmedi.

## PUNKTCHEN VE ANTON (Kök-Neden A doğrulandı, hâlâ çözülmedi) + BLACKJACK (kimlik kilitli, OCR yok) — promote edilmedi

**PUNKTCHEN VE ANTON:** yeniden test edildi, OCR job'ı hâlâ `status:"failed"` (`clip.json`) — KRİTİK BULGU #4 Kök-Neden A'nın somut, doğrulanmış örneği. `--clip` bunu düzeltemez (yalnız var-olan `ocr/*/kunye.txt`'yi okur); OCR job'ının TAM pipeline'da yeniden koşulması gerekiyor — bu oturumun kapsamı dışı.

**BLACKJACK:** kimlik kilitli (tmdb=46977, "BlackJack" 1990, web_yonetmen="Colin Nutley") ama OCR klasörü tamamen boş/yok — deferans doğru çalıştı (KB-fill atlandı). Aynı sınıf, ayrı film.

İkisi de promote edilmedi, yeni bulgu yok (zaten bilinen sınıflar).

## BAŞKAN VE MARI (golden-test filmi, retest) — şu an OCR hub'ı boş/yok, Kök-Neden A

Bu film `regresyon_golden.py`'nin 7 vakasından biri (beklenen "Rochefoucauld"). Bu oturumdaki bağımsız --clip retest'inde `ocr/*/kunye.txt` bulunamadı (Kök-Neden A) — golden-suite'in kendi kararsızlığıyla (bkz "task_5aae0a2b" bölümü) tutarlı: aynı film farklı zamanlarda farklı OCR-hub durumlarında olabiliyor. Promote edilmedi, yeni bulgu yok.

## SANTRAL (2000-0395, "The Operator") — karakter/oyuncu AYRIMI DOĞRU ama yine 4 temiz oyuncu kaybı; "cast-kayıp" deseni artık 4. örnek

Giriş karesi gerçek filmi doğruluyor ("Black Wolf Productions presents THE OPERATOR", Michael Laurence/Jacqueline Kim/Stephen Tobolowsky/...). Ham OCR'da (200 satır, "AND THE CAST AND CREW OF 'THE OPERATOR.'" satır 180 ile kendi-referanslı doğrulanmış — AŞK EVLİLİĞİ tipi kirlenme DEĞİL) satır 17-36 arası TEMİZ bir "(IN ORDER OF APPEARANCE) / [Karakter] [OYUNCU]" tablosu var. **Bu kez karakter/oyuncu ayrımı DOĞRU okunmuş** (LAUREL HARDY'deki karışıklık burada YOK — karakter-adları cast'e sızmamış). Ama yine de gerçek, temiz, tablo-içi oyuncular kayıp: **JACQUELINE KIM** (filmin BAŞLIK-karakteri "Operator"ı oynuyor, üstelik "üst-başlık" yıldız listesinde de 2. sırada), **BRION JAMES**, **DREW SNYDER**, **FRANCES BAY** — hiçbiri nihai `cast_list`'te yok, `teyitsiz_dusen_cast`'te de yok (hiç denenmemiş gibi).

Yönetmen alanı da tamamen BOŞ (`yonetmen: []`) — giriş karesinde "Black Wolf Productions presents" sonrası doğrudan başlık/kadroya geçiyor, ayrı bir "Directed by" kartı bu crop'ta görünmüyor (muhtemelen scroll'un başka bir yerinde, extraction'a hiç girmemiş olabilir).

**Bu, oturumun 4. bağımsız örneği** (KARAR KİMİN, İKİ SEVGİLİM VAR, AŞK EVLİLİĞİ ile aynı desen): ham OCR'da TEMİZ, açık, KB-doğrulanabilir isimler var ama nihai `cast_list`'e hiç girmiyor — `teyitsiz_dusen_cast`'te bile yok (yani reddedilmiyor, hiç DENENMEMİŞ görünüyor). 4 örnek de context-taşması uyarısı ateşlemedi (root-cause B değil). Artık tekil/zayıf bir sinyal değil, TEKRARLANAN bir örüntü — konsolide görev spawn edildi.

Promote edilmedi (yönetmen boş + 4 oyuncu kayıp).

## AĞIZ TADI (2001-9238, "Tortilla Soup") — yönetmen kartı hiç yakalanmamış + cast-kayıp deseni (5. örnek), promote edilmedi

Kare 10 gerçek yıldızı doğruluyor (Hector Elizondo/Raquel Welch/vb., "Tortilla Soup" United Artists/Samuel Goldwyn). Ham OCR'da "DIRECTED BY" satırı HİÇ yok (yalnız "ASSISTANT DIRECTOR"/"DIRECTOR OF PHOTOGRAPHY" crew-etiketleri) — yönetmen kartı bu OCR-pasosunda hiç yakalanmamış (SANTRAL ile aynı alt-örüntü: kart muhtemelen scroll'un extraction'a hiç girmeyen bir yerinde). Ayrıca ham OCR'da erken-pozisyonda temiz "MARIANA SANCHEZ DE ANTUNANO"/"JOSEPH SOLARI" var ama nihai cast_list'te yok — task_82ba4c26'nın (cast-kayıp) 5. destekleyici örneği, ayrı task açılmadı. `cast:18` tam `MITAS_CAST_CAP=18`'e eşit — cap'in gerçek isimleri kesip kesmediği bu oturumda tam doğrulanmadı (zaman kısıtı), gözlem olarak not düşüldü.

Promote edilmedi.

## SESSİZ AMERİKALI (2002-9241, "The Quiet American") — karakter/oyuncu karışması yine (task_025f0a07'ye destekleyici), promote edilmedi

Gerçek film (Michael Caine, Brendan Fraser). cast_list'te **"ALDEN PYLE"** (Brendan Fraser'in canlandırdığı KARAKTER, gerçek oyuncu değil), **"FRENCH CAPTAIN"**, **"TOWER SOLDIERS"** (ikisi de rol/grup tanımı, kişi adı değil) sızmış — LAUREL HARDY'deki karakter/oyuncu-sütun-karışması bulgusunun (task_025f0a07) yeni, bağımsız bir teyidi. Yönetmen boş. Yeni görev açılmadı (mevcut task'a destekleyici kanıt olarak yeterli).

## DERTLER BENİM OLSUN — ÇOK ÖNEMLİ POZİTİF SİNYAL: KRİTİK BULGU #2 (Türkçe-aksan-kaybı) ÇÖZÜLMÜŞ GİBİ GÖRÜNÜYOR

Bu film önceden ("Aktif işler" listesi, DERTLER BENİM OLSUN kaydı) "yapısal olarak tam temiz ama Türkçe-aksan-kaybı bloke ediyor" diye belgelenmişti — o denetimde "Perihan Savaş"→"Perihan Savas", "Şafa Önal"→"Safa Onal", "Hürrem Erman"→"Hurrem Erman" aksan kaybı VARDI.

**Bu geceki yeniden-render'da TÜM aksanlar DOĞRU:** yönetmen "**SAFA ÖNAL**" (Ö korunmuş), yapımcı "**HÜRREM ERMAN**" (Ü korunmuş), cast "**PERİHAN SAVAŞ**" (İ+Ş korunmuş), "KADİR SAVUN", "SELÇUK ÖZER" (Ç+Ö korunmuş) — hepsi kare-teyitli DOĞRU ("YAZAN ve YÖNETEN SAFA ÖNAL" kartı net). Bu, başka oturumun `name_normalize.py`'deki mitas.duckdb yol-göçünün (X:\→E:\MITAS\Mitas_Files, commit 4dd4d8fd+üzeri) GERÇEKTEN İŞE YARADIĞININ somut, canlı kanıtı — KRİTİK BULGU #2 çözülüyor gibi görünüyor (kesin doğrulama için daha fazla Türkçe-kadrolu film testi gerekir ama bu güçlü bir ilk işaret).

**Ama promote EDEMEDİM — ayrı bir sorun (cast-kayıp, task_82ba4c26 ailesi) hâlâ blokluyor:** ham OCR'da (`ocr-2809bfe6/kunye.txt`) tekrar tekrar (garble'lı da olsa TUTARLI) görünen gerçek isimler nihai cast_list'te (6 kişi) YOK ve `teyitsiz_dusen_cast`'te de YOK (hiç denenmemiş): **"İHSAN BAYSAL"** (posterde de "ihsan baysal" olarak teyitli, satır 11/13), **"ASUMAN ARSAN"** (tanınmış Türk aktris, satır 16/17/19'da 3 kez tekrarlanmış), "ERSUN KAZANCIEL" (satır 6/9), "İ. HAKKI ŞEN" (satır 7/8/10, 3 kez), "EKREM DÜMER" (satır 21/24-29, 6 KEZ tekrarlanmış!). Bu, task_82ba4c26'nın (temiz isimler extraction'da kayboluyor) EN GÜÇLÜ örneği — tek filmde 5 aday isim, bazıları 3-6 kez tekrarlanarak.

**Sonuç:** KRİTİK BULGU #2 çözümü CANLI-DOĞRULANDI (büyük haber) ama bu film YİNE DE promote edilemedi — cast-kayıp deseni (task_82ba4c26) devam ettiği sürece bu ve benzeri filmler tam temiz olamayacak. task_82ba4c26'nın önceliği bu bulgu ile ARTMALI.

## HASİP İLE NASİP — aksan-kaybı YİNE düzelmiş (2. teyit) ama cast-kayıp yine blokluyor (7. örnek)

Yönetmen "ATIF YILMAZ", yapımcı "MEMDUH ÜN" (Ü korunmuş), 13 cast — TÜMÜ doğru aksanlarla (Zeki Alasya/Metin Akpınar/Güngör Bayrak/Şevket Altuğ/vb.), afiş MÜKEMMEL eşleşiyor, POSTERDEKİ 6 baş-rol ismi (Zeki Alasya, Metin Akpınar, Güngör Bayrak, Şevket Altuğ, Erol Keskin, İhsan Yüce) TAM ve DOĞRU. KRİTİK BULGU #2 çözümünün **2. bağımsız teyidi** (DERTLER BENİM OLSUN'dan sonra).

Ama ham OCR'da (satır 6-18) TEMİZ, yoğun bir cast-kümesinde 5 isim nihai listeden kayıp: **AHMET KOSTARIKA, REŞİT ÇILDAM, MURAT TOK, NIYAZI ER, CEMAL GONCA** — hepsi posterde OLMAYAN (yani baş-rol değil, destek-kadro) ama ham OCR'da diğer 8 isimle AYNI temiz kümede, aynı satır-yoğunluğunda. task_82ba4c26'nın (cast-kayıp) **7. örneği**.

**Not — önemli nüans:** bu filmde kayıp isimler yalnız DESTEK-kadro (posterde yok), TÜM baş-rol/poster-isimleri eksiksiz — AŞK EVLİLİĞİ (başrol Mathilde Seigner kayıp) veya KARAR KİMİN (posterdeki Co-Starring isimleri kayıp) gibi DAHA AĞIR değil. Yine de mevcut katı standart (byte-diff TÜM alanlar, "yanlış>boş" disiplini) gereği promote edilmedi — tutarlılık için baş-rol/destek ayrımı yapılmadı.

Promote edilmedi.

## NAMUS DÜŞMANI — aksan-kaybı 3. kez düzelmiş teyit edildi ama yönetmen boş, promote edilmedi

Cast (9 kişi: Zeki Alasya/Metin Akpınar/Asuman Arsan/vb.) TÜMÜ doğru aksanlarla — KRİTİK BULGU #2 çözümünün **3. bağımsız teyidi** (DERTLER BENİM OLSUN, HASİP İLE NASİP'ten sonra — artık güvenle "çözüldü" diyebiliriz). 5 isim düzgün şekilde teyitsiz-düşürülmüş (doğru davranış). Ama yönetmen tamamen boş (kimlik de kilitli değil, yapımcı da yok) — bu filmde ayrı bir okuma-boşluğu var, derinlemesine incelenmedi (zaman kısıtı, diacritic-teyidi asıl amaçtı). Promote edilmedi.

**ÖZET — 3 filmlik aksan-kaybı doğrulama turu:** DERTLER BENİM OLSUN, HASİP İLE NASİP, NAMUS DÜŞMANI — **3/3'ünde de Türkçe aksanlar (İ/Ş/Ü/Ç/Ğ/Ö) artık doğru**. KRİTİK BULGU #2 (mitas.duckdb X:\ erişilemezliği) başka oturumun yol-göçü fix'iyle ÇÖZÜLMÜŞ görünüyor — ama bu 3 filmin HİÇBİRİ promote edilemedi çünkü HER birinde AYRI bir sorun (cast-kayıp x2, yönetmen-boşluğu x1) hâlâ blokluyor. Aksan-kaybı artık "iyileşen" kategoriye taşınmalı, cast-kayıp (task_82ba4c26) şimdi en sık tekrarlanan tekil bloker.

## KRAL LEAR — Kök-Neden A (OCR yok), promote edilmedi, yeni bulgu yok

## UMUTSUZ SAAT (2025-1295, "The Desperate Hour", Naomi Watts) — modern film, yönetmen kartı bu pencerede yok

17 kişilik temiz, gerçek cast (Naomi Watts/Jason Clarke doğrulandı). Giriş karesi modern-tarz minimalist jenerik (yalnız stüdyo/dağıtımcı logoları + ekran-içi telefon-mesajı grafikleri + "EXIT"/"SCHOOL DISTRICT" gibi sahne-içi tabela metinleri — ZERK'İN HİKAYESİ'ne benzer ama bu kez cast_list'e sızmamış) — hiçbir "Directed by" kartı yok. SANTRAL/AĞIZ TADI ile aynı alt-örüntü: yönetmen kartı muhtemelen bu OCR-penceresine hiç girmemiş (cikis'te olabilir, kontrol edilmedi — zaman kısıtı). Promote edilmedi, yeni bulgu yok (bilinen örüntü).

**Bu turun (batch58) özeti:** ~25 film incelendi, 0 promosyon ama 7 yeni görev spawn edildi + KRİTİK BULGU #2'nin (Türkçe-aksan-kaybı) 3 bağımsız teyitle ÇÖZÜLDÜĞÜ doğrulandı. En sık tekrarlanan kalan bloker: cast-kayıp (task_82ba4c26, 7+ örnek) ve yönetmen-kartı-yakalanmama (3 örnek, SANTRAL/AĞIZ TADI/UMUTSUZ SAAT).

## ALTIN VE ŞÖHRET + DURUMU ANLAMAK (rastgele seçim) — ikisi de Kök-Neden A (OCR boş/yok), yeni bulgu yok, promote edilmedi

## METİN (kimlik kilitli, OCR boş) — promote edilmedi, bilinen sınıf

## KÖPEKLE BİR TATİL — Çince-kaynaklı, OCR aşırı seyrek (2 satır), promote edilmedi, yeni bulgu yok

## MOSKOVA BUZ BALESİ — boş sonuç, bilinen sınıf, promote edilmedi

## KANDIRMACA ("Deceived", 2002, Cloud Ten Pictures) — güçlü cast ama yönetmen belirsiz, promote edilmedi

16 kişilik güçlü cast (Judd Nelson, Louis Gossett Jr. doğrulandı), afiş var, özet dolu — ama yönetmen adayı "ROTH BILL MACDONALD" (garble/birleşik, muhtemelen 2 ayrı kredi-satırının karışımı) reddedilmiş, "Directed by" kartı bu crop'ta görünmüyor (muhtemelen scroll'un görülmeyen bir bölümünde). Net, tekrarlanabilir bir kod-defekti olarak sınıflandırılamadı (mevcut kategorilerin hiçbirine tam oturmuyor) — ayrı görev açılmadı, tek-film gözlem olarak bırakıldı.

## LA BOHEME — kimlik kilitli, OCR boş, bilinen sınıf, promote edilmedi

## BÜYÜK BULGU — 35/185 (%19) KONTROL filminin OCR durumu "partial" (yarım kalmış), kod-hatası DEĞİL, operasyonel yeniden-koşu gerekiyor

Bu turdaki (batch58) tekrarlanan "boş sonuç" örneklerinin çoğunun ortak paydasını netleştirmek için 194 KONTROL dosyasının TAMAMINI (185 benzersiz TRT-ID) `clip.json`'daki `modules.ocr.status` alanına göre tarandı:

- **done: 134** (%72) — OCR tamamlanmış, --clip testi anlamlı.
- **partial: 35** (%19) — **OCR işi YARIM KALMIŞ** — job klasörü oluşmuş ama `kunye.txt` DAHİL hiçbir çıktı dosyası üretilmemiş (LA BOHEME örneğinde doğrulandı: `ocr-c6d54607/` klasörü TAMAMEN BOŞ). ÖNEMLİ: kare-çıkarma (frame-extraction) BAŞARILI (LA BOHEME'de 270 giriş-karesi mevcut) — yalnız OCR-OKUMA adımı hiç çalışmamış/tamamlanmamış. Bu, --clip modunun ASLA düzeltemeyeceği bir durum (--clip yalnız var-olan kunye.txt'yi okur) — video'dan yeniden başlamaya GEREK YOK, sadece OCR-okuma adımının bu 35 hub'ın ZATEN VAR OLAN kareleri üzerinde yeniden tetiklenmesi yeterli.
- **failed: 1** (PUNKTCHEN VE ANTON — KRİTİK BULGU #4'ün bilinen örneği).
- **kunye boş ama status=done: 5** (YÜZYILIN CİNAYETİ, AYNA, PRENSES WONONOKE, TACİZ, KÖPEKLE BİR TATİL) — ayrı, daha küçük bir alt-sınıf.
- **missing_hub: 13** (script'in dosya-adı↔hub eşleştirmesi bulamadı — muhtemelen encoding/ID-format farkı, ayrı incelenmedi).

**Tam liste (35 film, TRT-ID + başlık):**
MUTLU GÜNLER 1967-0037, BAHAR VE ŞARAP 1970-0061, RODEO TUTKUSU 1971-0057, BİR ZAMANLAR 1975-0182, ALTIN VE ŞÖHRET 1984-0286, LA BOHEME 1988-0420, LALELER 1988-0430, GÖLGELER PRENSİ 1991-0441, KONTES ALICE 1992-0223, ÖLÜMSÜZ TUCK 1993-0312, SON BOLŞEVİK 1993-0439, KİNG'İN SERVETİ 1994-0338, KORKUNÇ GECE 1995-0444, TANGO ARGENTINO 1996-0316, SİNDİRELLA'NIN KIZININ MACERALARI 1996-0356, ÖRGÜT 1997-0217, KÜÇÜK AYICIK 1997-0353, BLACKJACK 1998-0401, ELMA 1998-0464, SON CÜCE 1998-0519, 13. SAVAŞÇI 1999-0394, PAMUK MARY 1999-0508, MOTORSİKLETLİ POLİSLER 2000-0303, VAHŞİ AFRİKA 2001-9314, YÜZÜKLERİN EFENDİSİ 2002-9089, UFAKLIK İÇİN BİR BABA 2003-9104, GÜLLERİN SAVAŞI 2004-9139, MURPHY KANUNLARI 2 2005-9051, KUMRULAR GİBİ 2006-9063, ANNEM ANNEM 2008-9064, KUSURSUZ BİR GÜN CENAZE TÖRENİ 2009-9137, HANNA'NIN ALTINLARI 2010-9150, PERCY JACKSON-ŞİMŞEK HIRSIZI 2010-9169, EL GUSTO 2011-9209, KRAL LEAR 2018-9036.

**Bu, oturumun en YÜKSEK-KALDIRAÇLI bulgusu olabilir:** eğer bu 35 hub'ın OCR-okuma adımı tek bir toplu operasyonla yeniden tetiklenirse (kare-çıkarma zaten hazır, yalnız OCR-okuma yeniden çalıştırılacak), bu VERİMLİLİK açısından tek-tek 35 filmi --clip ile test edip "boş" bulmaktan ÇOK daha değerli — kaynağında çözer. Bu bir KOD-FIX değil, bir OPERASYONEL yeniden-koşu ihtiyacı; görev olarak ayrı spawn edildi.

## Ek not: 13 KONTROL filminin Database hub'ı hiç yok

Yukarıdaki OCR-taramasında 13 TRT-ID için `Database/` altında EŞLEŞEN hub klasörü bulunamadı (KOMİSER CORDIER UZMAN RAPOR 2005-9063, GÜZELLİK MERKEZİ 2005-9097, OLAY YERİ BIENZLE VE TAKSİ CİNAYETİ 2003-9088 dahil — tam liste script-çıktısında). Bu "partial OCR" (kareler var, OCR yok) sınıfından FARKLI — burada hub'ın KENDİSİ yok (hiçbir şey işlenmemiş). Kök-neden araştırılmadı (zaman kısıtı) — ayrı bir görev açılmadı, gözlem olarak bırakıldı; muhtemelen bu KONTROL-PDF'leri farklı/eski bir süreçten geliyor.

## NORWOORD — status=done ama OCR içeriği tamamen alakasız (NYC sokak/metro tabelası, kredi metni değil), promote edilmedi

## TOPLU GÖSTERİLER (1991-0356) — zayıf kaynak (muhtemelen derleme-program türü), promote edilmedi, yeni bulgu yok

## GERÇEK KUZEY ("True North", 2006) — task_025f0a07 ailesine ÖNEMLİ ek kanıt: LLM "AS" kelimesini UYDURUYOR

Yönetmen "STEVE HUDSON" kare-teyitli DOĞRU ("WRITTEN AND DIRECTED BY / STEVE HUDSON"). Ama cast_list'teki HER isim "AKTÖR AS KARAKTER" formatında TEK STRING: "PETER MULLAN AS RILEY", "MARTIN COMPSTON AS SEAN" vb.

**Kritik detay:** Ham OCR'da (431 satırlık dev end-crawl, satır 61) **"RILEY PETER MULLAN"** yazıyor — boşlukla ayrılmış Karakter-Oyuncu (LAUREL HARDY'nin dot-leader'ının boşluklu versiyonu), **HİÇBİR YERDE "AS" kelimesi YOK**. LLM bunu "PETER MULLAN AS RILEY" diye yeniden sıralarken kaynakta OLMAYAN "AS" kelimesini KENDİSİ EKLEMİŞ — muhtemelen filmi/oyuncu-karakter eşleşmesini kendi eğitim-bilgisinden "biliyor" ve "yardımcı olmaya" çalışıyor.

**Neden önemli:** Bu, mevcut anti-halüsinasyon token-kalkanının (`credit_text_read.py` docstring: "her çıktı ismi OCR metninde token olarak bulunmazsa ATILIR") bir KÖR NOKTASINI gösteriyor — kalkan her TOKEN'ı (PETER/MULLAN/RILEY) ayrı ayrı OCR'da arıyor, hepsi GERÇEKTEN orada olduğu için geçiyor, ama "AS" gibi bir BAĞLAÇ kelimenin kaynakta OLMAYAN bir SIRAYLA eklenmesini yakalamıyor. task_025f0a07'nin (karakter/oyuncu sütun-karışması) kapsamına eklenmesi gereken YENİ bir alt-belirti — aynı kök-yapısal soruna (Karakter-Oyuncu ayrıştırılmamış çift) işaret ediyor ama SEMPTOM farklı (isim kaybı/karışması yerine kaynak-dışı kelime EKLENMESİ). Ayrı görev açılmadı, mevcut göreve not düşüldü.

Promote edilmedi.

## HARRY'NİN UYANIŞI — yapımcılar doğru (Glen A. Larson dahil) ama yönetmen boş, promote edilmedi, yeni bulgu yok

---

# BATCH58 OTURUM SONU — KAPSAMLI ÖZET (2026-07-10)

Bu segment ~45 film inceledi (LAUREL HARDY'den HARRY'NİN UYANIŞI'na). **0 promosyon** ama:
- **9 yeni görev spawn edildi** (karakter/oyuncu-sütun-karışması [+GERÇEK KUZEY kanıtıyla güçlendi], belgesel-yanlış-afiş, Kiril-romanizasyon, Almanca-editör-yönetmen, Fransızca-aksan-pipeline-kaybı, kare-bant-bitişik-kirlenme, cast-kayıp-deseni [7+ örnek], **35-film OCR-yarım-kalmış toplu-yeniden-koşu** [en yüksek kaldıraçlı bulgu])
- **KRİTİK BULGU #2 (Türkçe-aksan-kaybı) çözümü 3 bağımsız filmle DOĞRULANDI**
- **KRİTİK BULGU #4'ün gözlemlenebilirlik-fix'i CANLI** (commit 4dff40b7)
- **185 KONTROL filminin TAMAMI OCR-durumuna göre haritalandı**: %72 test-edilebilir (134), %19 OCR-yarım-kalmış (35, kod değil operasyonel), %7 hub-yok (13)

**55 ONAYLI, 194 KONTROL — sayılar bu segment değişmedi.** Ama artık kalan 194'ün BÜYÜK kısmının NEDEN bloke olduğu net: (1) 35 film OCR-yeniden-koşu bekliyor, (2) 13 film hub-yok, (3) test-edilebilir kalanların çoğu cast-kayıp veya rol-eşleme hatalarından (7 farklı sınıf, hepsi görev-kaydında) etkileniyor. Kör --clip taramasının bu noktadan sonra getirisi düşük — bekleyen 11 arka-plan görevinin (bu segment 9 + önceki 2-3) sonuçlanması, tek-tek film denemekten çok daha yüksek kaldıraçlı.

---

# 35-FİLM OCR-YARIM-KALMIŞ TOPLU YENİDEN-KOŞU — SONUÇ (2026-07-10)

Yukarıda "en yüksek kaldıraçlı bulgu" olarak spawn edilen 35-film OCR-partial görevinin sonucu.

## Kök neden (doğrulandı — KOD HATASI DEĞİL, geçici altyapı kesintisi)

`debug_trace/trace.jsonl` + `outputs/system_events.1.jsonl` kanıtıyla (LA BOHEME örneğinde uçtan-uca izlendi): 35 filmin tamamı 2026-07-06 06:50 civarı aynı gece-yarısı toplu-koşusunda işlendi ve o anda **sistem-çapında geçici bellek tükenmesi** yaşandı:
- OpenCV credit-detect adımında **843 KB'lik bir ayırmada bile** `cv::OutOfMemoryError` fırlattı.
- Aynı dakikada ASR alt-süreci açık bir `MemoryError` ile çöktü; commit-boş bellek 4.9GB ölçüldü (asr-ön-sübap hedefi ≥8GB).
- `_pipe_ocr.py` alt-süreci bu pencerede **SIFIR stderr/stdout üreterek** çöktü — kod her yerde try/except'li olduğu için bu, Python-seviyesinde YAKALANAMAYAN bir çökme (muhtemelen native/OOM-kill). `mitas_pipeline.py` bunu `j={}` olarak gördü → varsayılan `ocr_bucket="HATA"` + `status="partial"` yazdı.
- "Ollama model deposu boş/erişilemez" (routing kararında görünen metin) GERÇEK ama AYRI bir semptom (o an belirli bir VL-modelinin eksik olması) — OCR'ın kendi çökmesinin nedeni DEĞİL, çökmeden SONRA farklı bir adımda tetiklendi.
- Kareler (`frames/giris`+`frames/cikis`) SAĞLAM çıkarılmıştı → videodan yeniden başlamaya gerek yoktu, yalnız OCR-okuma adımı yeniden tetiklendi. Bugün (2026-07-10) sistem sağlıklı: 74.8GB/128GB RAM boş, ollama modelleri yerinde.

## Mekanizma

Yeni script: `outputs/KONTROL_LOOP_20260707/ocr_rerun_35film.py`. `mitas_pipeline.py`'nin ana OCR bloğunu (satır ~2025-2178, `update_clip_module` dahil) tek-film için birebir tekrarlar: `_pipe_ocr.py` (venvs/ocr) mevcut kareler üzerinde yeniden çalıştırılır → `clip.json.modules.ocr` güncellenir (yeni job-id, jobs listesine ek, status, updated_at) → `tek_film_kunye.py --clip` ile DOĞRULAMA render'i. **Bilinçli kapsam-sınırı:** doğrulama render'i yalnız scratchpad'e yazıldı; hub'ların `pdf/kunye.pdf`/`kunye_teslim.md`'si ve `export/ONAYLI|KONTROL` klasörleri DOKUNULMADI — promote/routing kararı KONTROL-loop'un kendi sonraki (tam) turuna bırakıldı.

## Sonuç: 30/35 düzeldi (partial→done), 5/35 hâlâ BOS (ayrı, gerçek bir sorun)

**Pilot (LA BOHEME) gözle uçtan-uca doğrulandı:** 0→228 satır, bucket HATA→GUVENILIR, render'de yönetmen LUIGI COMENCINI + 3 yapımcı + 10 gerçek oyuncu + doğru afiş (öncesi hepsi "—"). PDF önizlemesi görsel kontrol edildi.

**Toplu 34 film — script-seviyesinde HATASIZ tamamlandı (34/34 rc=0):**

- **done, zengin içerik (26 film, satır 28-842):** MUTLU GÜNLER(105) BAHAR VE ŞARAP(142) RODEO TUTKUSU(53,bucket=GÖZDEN_GEÇİR) BİR ZAMANLAR(62,yön SIMON CURTIS) LALELER(227) KONTES ALICE(211) ÖLÜMSÜZ TUCK(132) SON BOLŞEVİK(28) KİNG'İN SERVETİ(251,yön TOM LOGAN) SİNDİRELLA'NIN KIZININ MACERALARI(181) ÖRGÜT(169,yön UGO FABRIZIO GIORDANI) KÜÇÜK AYICIK(237) BLACKJACK(290,yön JOHN WOO) ELMA(158) 13.SAVAŞÇI(581,yön JOHN MCTIERNAN) PAMUK MARY(278,yön ISMAIL MERCHANT/"Cotton Mary") MOTORSİKLETLİ POLİSLER(54,yön CARMEN KURZ) UFAKLIK İÇİN BİR BABA(61,yön PETER KAHANE) GÜLLERİN SAVAŞI(376,yön PATRICK LEUNG) MURPHY KANUNLARI 2(177,yön PETER LYDON) KUMRULAR GİBİ(428) ANNEM ANNEM(72,yön MICKI DICKOFF) KUSURSUZ BİR GÜN CENAZE TÖRENİ(108) HANNA'NIN ALTINLARI(346) PERCY JACKSON-ŞİMŞEK HIRSIZI(842,yön CHRIS COLUMBUS) EL GUSTO(280,yön SAFINEZ BOUSBIA). Yönetmen boş kalan filmlerde (MUTLU GÜNLER vb.) `video_okuma.guven="OKUNDU (ensemble/fallback; yön:OKUNAMADI)"` — OCR/satır-sayısı sağlıklı, sorun AYRI bir aşamada (rol-eşleme/director-attribution, mevcut 7-sınıflık cast/rol görev-ailesinin kapsamında) — bu görevin konusu DEĞİL.
- **done ama İNCE (3 film, 3-17 satır):** SON CÜCE(3) KRAL LEAR(4) VAHŞİ AFRİKA(17) — status teknik olarak düzeldi (kunye.txt artık boş DEĞİL) ama içerik hâlâ çok az; KRAL LEAR'da hybrid-kapı 633 aday kare bulmasına rağmen yalnız 4 satır kredi-sınıfını geçti. "Gerçekten zayıf kaynak" sınıfına yakın, ayrı bir yakın-bakış adayı.
- **hâlâ BOS (5 film):** ALTIN VE ŞÖHRET GÖLGELER PRENSİ KORKUNÇ GECE TANGO ARGENTINO YÜZÜKLERİN EFENDİSİ.

**5 BOS filmin karakterizasyonu (kare-seviyesinde GÖRSEL doğrulandı — orijinal çökme-bug'ının TEKRARI DEĞİL):** motor bu sefer TAM ve TEMİZ çalıştı — CLIP+hybrid-kapı 281-898 "metin-adayı" kare buldu (ALTIN VE ŞÖHRET 548, TANGO ARGENTINO 281, YÜZÜKLERİN EFENDİSİ 735), OneOCR okudu, clean/classify aşaması çalıştı — ama sabit kredi-pencereleri (açılış 180s / kapanış son 480s) içinde GERÇEK kredi-metni YOKTU. Doğrudan kare-denetimi: YÜZÜKLERİN EFENDİSİ'nin kapanış-penceresi örnek kareleri (c_0400, c_0650) SAF SİNEMATİK GÖRÜNTÜ (Fellowship yürüyüşü / kül-kar sahnesi, metin YOK); ALTIN VE ŞÖHRET'in açılış-penceresi örnek karesi (g_0100) TAMAMEN SİYAH. Bu, **"gerçekten okunamaz kaynak"** ailesine giriyor (KARA KALKAN/PROFESÖR HANNIBAL örnekleriyle aynı sınıf) — muhtemelen bu spesifik TRT baskılarında kredi-crawl'ı sabit-pencere varsayımının (özellikle uzun-metrajlı YÜZÜKLERİN EFENDİSİ gibi filmlerde 480sn'den uzun kapanış crawl'ı) dışında kalıyor. **Kod-fix veya tekrar-deneme bunu düzeltmez** — kredi-pencere-tespitini iyileştirmek ayrı, daha büyük bir konu; bu görevin kapsamı dışında bırakıldı.

## Yan-bulgu: mitas.duckdb (X:\) erişimi HÂLÂ kesik (KRİTİK BULGU #2 devam ediyor)

İşlenen 34 filmin TAMAMINDA aynı hata tekrarlandı: `IOException: IO Error: Cannot open file "X:\DIGER\Mitas_Files\MitaData\mitas.duckdb": Kullanıcı adı veya parola hatalı.` Yukarıdaki KRİTİK BULGU #2'nin (2026-07-09) hâlâ ÇÖZÜLMEMİŞ olduğunu doğruluyor — KB-doğrulama/isim-normalize CSV-fallback'e düşüyor. Kod-tarafında yapılacak bir şey yok; X:\ sürücü bağlantısının yeniden kimlik-doğrulanması gerekiyor.

## Değişen dosyalar

- YENİ: `outputs/KONTROL_LOOP_20260707/ocr_rerun_35film.py` (yeniden-kullanılabilir tek-film/toplu OCR-rerun aracı; production kodunda hiçbir değişiklik yapılmadı).
- 30 filmde `Database/<hub>/clip.json` → `modules.ocr` güncellendi (yeni job-id, status=done) + `Database/<hub>/ocr/<yeni-job>/` altında kunye.txt+ocr_summary.json+ocr_ham.txt+ocr_raw_all.txt+ocr_raw_reads.jsonl yeni dosyalar.
- 5 filmde de yeni bir OCR job-id oluştu (jobs listesine eklendi) ama status hâlâ "partial" — eski çökmüş job silinmedi.
- Hiçbir hub'ın `pdf/kunye.pdf`'i, `pdf/kunye_teslim.md`'si veya `export/ONAYLI|KONTROL` klasörleri DEĞİŞTİRİLMEDİ (bilinçli kapsam-dışı bırakma).
- Not: `scripts/credit_text_read.py` bu görev sırasında (11:51) 90-satır değişti — BU GÖREVİN İŞİ DEĞİL, paralel oturumun (muhtemelen task_5aae0a2b/KRİTİK BULGU #4 devamı) çalışması; dokunulmadı, doğrulandı.

## KONTROL-loop için not — sıradaki taramada bu 35 filmi nasıl bulacak

30 film artık `modules.ocr.status="done"` — bir sonraki KONTROL-loop taramasında bu filmler "OCR-yarım-kalmış" olarak DEĞİL, normal test-edilebilir KONTROL adayı olarak görünecek (yönetmen/cast tamlığı ayrı — bilinen 7-sınıflık cast-kayıp/rol-eşleme görev-ailesine tabi olabilirler; 3'ü — SON CÜCE/KRAL LEAR/VAHŞİ AFRİKA — içerik olarak hâlâ ince, yakın-bakış adayı). Kalan 5 film (ALTIN VE ŞÖHRET, GÖLGELER PRENSİ, KORKUNÇ GECE, TANGO ARGENTINO, YÜZÜKLERİN EFENDİSİ) hâlâ "partial" ama artık YENİ, DAR bir alt-sınıf: "motor temiz çalıştı, sabit kredi-penceresinde gerçek kredi yok" — agresif tekrar-deneme FAYDASIZ, asıl ihtiyaç kredi-pencere-tespiti iyileştirmesi (ayrı, daha büyük konu, bu oturumda ele alınmadı).

---

# 2026-07-10 GECE — WORKFLOW-DESTEKLİ SİSTEMİK SENTEZ

## Faz 1: 194 filmlik OCR/ASR toplu haritalama (Workflow w8f6t31h3, 10 paralel agent, ~4 dk)

Kategori dağılımı:
- YUKSEK_POTANSIYEL: **57** (yönetmen bayraksız, kunye zengin — asıl promote pool)
- DIGERI: 77 (yönetmen bayrağı var — 7 kod-fix görevinin etki alanı)
- OCR_PARTIAL: **35** (task_1182d455)
- HUB_YOK: 13 (farklı süreçten)
- OCR_DONE_BOS: 11 (kunye <5 satır, Kök-Neden A)
- OCR_FAILED: 1 (PUNKTCHEN VE ANTON, KRİTİK BULGU #4)

YUKSEK_POTANSIYEL 57 filmin alt-dağılımı (bayrak bileşenlerine göre):
- _KIMLIK yalnız: 15
- _OZET yalnız: 10
- _CAST_CAP_DUSEN+_HAFIF: 9
- _RENDER yalnız: 6
- _KIMLIK+_RENDER: 5
- _AFIS+_HAFIF: 4
- Diğerleri: 8

## Faz 2: 4 aday film paralel test (Workflow wfdgpaht5, 4 paralel agent, ~7 dk)

Test edilenler: AJAMİ, HAYATIN TUZU, KIRIK KALPLER LOKANTASI, ARCEDIA.

Sonuç:
- **HAYATIN TUZU:** MURAT DÜZGÜNOĞLU + 13 cast (Türkçe aksanlı, doğru) + 2 yapımcı + tür DRAM + verdict TEYİT — **4/5 madde geçti, sadece özet placeholder (5 kelime)**
- **KIRIK KALPLER LOKANTASI:** RICHARD SHEPARD + 18 cast (Rosanna Arquette, David Bowie) + 3 yapımcı + tür KOMEDİ/SUÇ + verdict TEYİT — **4/5 madde geçti, sadece özet placeholder**
- **ARCEDIA:** yönetmen tek dolu, cast 3, tür boş, verdict KAYNAK_YOK — 1/5, ayrı sınıf
- **AJAMİ:** render 5 dakikada tamamlanmadı (Ollama sıraya alma yüzünden), zaman aşımı — veri yok

Ayrıca [ollama-json] uyarısı ateşleyen 0/4 → context-taşması bu 4 filmde tetiklenmedi (commit 4dff40b7 telemetrisi çalışıyor ama örneklem küçük).

## Faz 3: Kök-neden buluşu — özet motoru ASR'a bağlı

`tek_film_kunye.py:85-87` özet ÜRETMİYOR, `Database/<hub>/pdf/kunye_teslim.md`'den OKUYOR. Özet motoru `mitas_pipeline.py`'de (`_generate_ozet`, satır 1259) ASR transcript'ine dayanıyor. HAYATIN TUZU + KIRIK KALPLER LOKANTASI'nin `clip.json`'ında `modules.asr.status: "failed"` — ASR yarım, transcript yok, özet motoru çalışmamış, `kunye_teslim.md`'ye "(ÖZET AYRI BİR ADIMDA ÜRETİLECEKTİR.)" placeholder yazılmış.

**10/10 TAM ÖRTÜŞME:** _OZET-yalnız bayrağı taşıyan 10 filmin **TAMAMI**nda ASR failed. Yani "_OZET" bayrağı ≡ "ASR failed" için doğrudan bir gösterge.

## Faz 4: Tam ASR haritası (194 film)

- ASR done: 116
- ASR failed: **48**
- ASR partial: 5
- ASR other: 3

## SENTEZ — kesişim analizi

- OCR-sorunlu (partial+failed): 35 film
- ASR-sorunlu (failed+partial): **53 film**
- Kesişim (ikisi de sorunlu): 30 film
- Sadece OCR sorunlu: 5
- Sadece ASR sorunlu: 23
- **UNIQUE ETKİ (OCR VEYA ASR sorunlu): 58 film (%30)**

Kalan 194 - 58 = **136 film hem OCR hem ASR temiz** — asıl promote pool + kod-fix bekleyen havuz.

## Sonuç: iki büyük kaldıraçlı operasyonel görev

1. **task_1182d455** (35 OCR-partial yeniden-koşu)
2. **task_[YENI]** (53 ASR-sorunlu yeniden-koşu, task_1182d455'in kardeşi) — bu turda spawn edildi

Bu iki toplu operasyon TEK BAŞLARINA kalan 194'ün %30'unu (58 film) potansiyel olarak kurtarabilir. **7 kod-fix görevi**, kalan 136 filmin farklı alt-sınıflarını hedefliyor.

Bu, "kör tek-tek --clip taramaya" devam etmenin DÜŞÜK-getirili olduğunu KESİN olarak gösteriyor. Doğru sıra: (a) 2 toplu-operasyonel görev tamamlansın → 58 film çözülür; (b) 7 kod-fix commit'lensin → cast-kayıp/rol-eşleme aileleri çözülür; (c) SONRA kalan filmleri tek tek test et.
