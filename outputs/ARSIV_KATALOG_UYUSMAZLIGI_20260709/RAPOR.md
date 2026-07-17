# ARŞİV KATALOG-UYUŞMAZLIĞI ARAŞTIRMASI — 2026-07-09/10

**Kapsam:** TRT-kimlik 1997-0411-1-0000-00-1 ("OMAGGIO A CARUSO" / gerçek içerik "UGETSU") vakasının kök-neden zinciri + arşiv genelinde sistemik tarama.
**Durum:** Salt araştırma. **Hiçbir dosya, kayıt ya da kod değiştirilmedi.** Karar Çağatay/TRT arşiv ekibine ait.
**Kaynak talep:** bkz. `E:\MITAS\outputs\KONTROL_LOOP_20260707\RAPOR.md` → "KRİTİK BULGU #3".

---

## YÖNETİCİ ÖZETİ

1. **"OMAGGIO A CARUSO" başlığı MITAS'ın icadı değil — TRT'nin kendi dijitalleştirme dosya-adının salt bir geçişi.** Kod satır-satır izlendi: `title` alanı yalnızca kaynak `.mp4` dosya-adından ayrıştırılıyor, hiçbir harici katalog/tablo sorgulanmıyor. Bu desen **286/286 örneklenen kayıtta %100 tutarlı** — yani arşiv genelinde başlığın tek kaynağı TRT'nin kendi "evoArcadmin...COZUMLEME SAYFAxx" dosya-adlandırması.
2. **Sistem bunu neredeyse yakalıyordu.** Pipeline'da gerçek bir "yanlış-film şüphesi" kapısı var (XML-kadro ile ekran-OCR-kadrosu kesişimi 0 ise KONTROL'e düşürüyor) — ama bu kayıtta, kimlik-çözümleme motoru Ugetsu'nun gerçek yan-kadrosunu (Eitarô Ozawa, Sugisaku Aoyama...) doğru bulduğu için, "bir gerçek filmi tanıdık" güveni bu şüpheyi **varsayılan-açık bir bayrakla sessizce bastırdı** — "hangi filmi tanıdık, o katalog başlığıyla uyuşuyor mu" diye hiç sormadan. Katalog başlık-metnini ekrandaki başlık-kartı OCR'ıyla doğrudan karşılaştıran hiçbir kod bulunamadı.
3. **143 kayıtlık sistemik tarama (tüm 51 ONAYLI + KONTROL'ün yarısı, ~%48 arşiv kapsaması) İKİNCİ bir Ugetsu/Caruso vakası bulamadı** — 112 MATCH (çoğu kadro/yönetmen web-doğrulamasıyla kesinleşti), 31 NO_DATA (jenerik okunamamış — ayrı, bilinen bir OCR sorunu, ne kanıt ne çürütme), **0 SUSPECT_MISMATCH**. Bu, vakanın şu an için **İZOLE** göründüğüne dair güçlü ama kesin-olmayan kanıt (152 kayıt hiç taranmadı).
4. **Karar gerektiren tek nokta değişmedi:** 1997-0411 için "Omaggio a Caruso" mı "Ugetsu" mü doğru TRT-kimliği — bu bir insan/kurumsal karar, koda dokunulmadı.

---

## 1. VAKA: 1997-0411-1-0000-00-1

### 1.1 Görsel kanıt (zaten doğrulanmıştı, dosyalar üzerinden teyit edildi)
`master_dilim\giris_reading_master_runaware_p01.png` karesinde net biçimde:
> UGETSU MONOGATARI / Based on the stories of Akinari Ueda / Players: Lady Wakasa...Machiko Kyo, Genjuro...Masayuki Mori, Miyagi...Kinuyo Tanaka... / Directed by KENJI MIZOGUCHI / Cinematography...Kazuo Miyagawa / Produced by...Masaichi Nagata

= Kenji Mizoguchi'nin 1953 Japon filmi *Ugetsu*. Katalog başlığı ("Omaggio a Caruso", İtalyanca "Caruso'ya Saygı") bununla hiçbir ortak yönü olmayan bir konu/ülke/dil/dönem öneriyor.

### 1.2 Başlığın kökeni — dosya-adı geçişi, kanıtlı
`_DURUM.json` → `"video": "W:\\23.05 sonrası FİLMLER\\5\\evoArcadmin_19062026 COZUMLEME SAYFA12_1997-0411-1-0000-00-1-OMAGGIO_A_CARUSO.mp4"`

Kod-tarafı doğrulama (`E:\MITAS\scripts\mitas_pipeline.py`):
- Satır 84: `TRT_RE = re.compile(r"(\d{4})-(\d{3,4})-(\d)-(\d{3,4})-(\d{2})-(\d)")`
- Satır 463-483, `parse_filename(video)`: TRT-kimlik regex dosya-adında (`stem`) bulunur; eşleşmeden **sonraki** kısım aynen `title` olur (`stem[m.end():].lstrip("-_ ").replace("_", " ")`). "OMAGGIO_A_CARUSO" → "OMAGGIO A CARUSO" böyle üretiliyor.
- Çağrı yeri satır 1501, her filmin en başında.
- Harici bir TRT ana-katalog/tablo/XML-manifest sorgusu **yok** — tek kaynak dosya adının kendisi.
- Ayrı bir ikinci kanal var (`xml_original()` 518-530, `xml_roles()` 533-559) — TRT'nin video-yanı `.xml` sidecar'ı (varsa) orijinal-ad + cast/yönetmen besler — ama bu **yalnız `orijinal_ad` alanını doldurur, `title` alanını hiç doğrulamaz/üzerine yazmaz.**
- **Arşiv-geneli doğrulama:** 286/286 örneklenen `_DURUM.json`'da `video` alanı aynı `evoArcadmin_<tarih> COZUMLEME[V2S]<N>..._<TRT-kimlik>-<BAŞLIK>.mp4` desenine uyuyor (TEPEDEKİ KIZ/1990, DERSU UZALA/1975, HOTEL RWANDA/2004, FERDİNAND/2025, MOTORSİKLETLİ POLİSLER/2000 dahil) — **%100 tutarlı, tek-kayda-özgü değil.**

**Sonuç:** Eğer "Omaggio a Caruso" yanlışsa, bu MITAS'ın ürettiği bir hata değil — TRT'nin kendi dijitalleştirme-öncesi kaset-etiketleme/sayfa-manifestosu (`COZUMLEME SAYFA12`) aşamasında oluşmuş bir hata olmalı (yanlış kaset dijitalleştirilmiş/yanlış sayfaya yazılmış). `W:\` sürücüsüne bu oturumda okuma erişimi yoktu ("Permission denied") — o yüzden TRT'nin fiziksel SAYFA12 manifestosu doğrudan görülemedi; dosya-adı zaten güçlü/tutarlı bir kanıt ama nihai teyit TRT arşiv ekibinin elindeki kaynak kayıtla çapraz-kontrol gerektirir.

### 1.3 Neden sistem bunu yakalamadı — "yanlış-film şüphesi" kapısı var ama susturuldu
- Kimlik-çözümleme motoru (`credit_crosscheck.py:497 cast_find()`, `credit_qc_gates.py:151 web_identity()`, `credit_identity.py resolve()`) bu kayıtta **muhtemelen gerçek kimliği (Ugetsu) doğru çözdü** — kanıt: `_DURUM.json → otorite_audit.kb_floor_added` alanında gerçek Ugetsu yan-kadrosu isimleri var (Eitarô Ozawa, Sugisaku Aoyama, Mitsusaburô Ramon, Ryôsuke Kagawa).
- Gerçek bir "yanlış-film" kapısı var: `mitas_pipeline.py:2923-2938` + `3057-3064` — XML-sidecar kadrosu ile ekran-OCR kadrosu kesişimi 0 ise `"XML-PDF cast kesişimi 0 (yanlış-film şüphesi)"` → KONTROL'e düşürür.
- **AMA** `MITAS_XMLCAST_GATE_RELAX=1` (varsayılan **AÇIK**), yukarıdaki motor "locked" (kimliği güvenle kilitledi) derse bu şüpheyi **satır 3061-3064'te sessizce bastırıyor** — yani sistem "bir gerçek filmi tanıdık" ile "katalog başlığı doğru" kavramlarını birbirine karıştırıyor. Bu kaydın `neden` listesinde bu bayrak yok — motor Ugetsu'yu güvenle tanıdığı için şüphe hiç tetiklenmedi.
- `credit_qc.py`'deki `crosscheck_check()`/`CROSSCHECK_CELISKI` çelişki-bayrağı var ama yalnız **yönetmen adı** için çalışıyor, `mitas_pipeline.py` onu hiç import etmiyor (ayrı, elle-çalıştırılan `credit_export.py`/`dagitim/` yolu, kendi içinde de varsayılan kapalı).
- **Kapsamlı arama sonucu: katalog başlığının METNİNİ ekrandaki başlık-kartının OCR'ıyla doğrudan karşılaştıran hiçbir kod bulunamadı.** En basit/en direkt kontrol pipeline'da hiç yok.

**Okunuşu:** Sistem en çok tam da bu tür bir vakada — kimlik-motoru bir filmi YÜKSEK güvenle tanıdığında — savunmasız kalıyor, çünkü "güvenle tanıma" sinyali "şüpheyi bastır" olarak kodlanmış; "hangi filmi tanıdın, katalog başlığıyla eşleşiyor mu" sorusu hiç sorulmuyor.

---

## 2. SİSTEMİK TARAMA — 143/295 kayıt (~%48 arşiv kapsaması)

### 2.1 Yöntem
- **ONAYLI: 51/51 (%100)** — küçük, sınırlı, zaten "onaylanmış" havuz olduğu için tam kapsama mantıklı.
- **KONTROL: 92/189 benzersiz TRT-kimlik (~%49)** — sistematik örnekleme (alfabetik-başlık sıralı listenin yarısı).
- **Taranmayan:** 97 KONTROL kaydı + henüz KONTROL/ONAYLI'ya yönlendirilmemiş ~46-55 hub-klasörü (pipeline'da hâlâ işlemde).
- Her kayıt için önce hub-klasöründeki kompakt özet (`<TRT-kimlik> <BAŞLIK>.txt`) okundu (katalog başlığı + kadro + yönetmen + tür bir arada); belirsiz/boş vakalarda `_DURUM.json`, ham OCR (`master_dilim\dilim_oneocr.txt`) ve gerekirse doğrudan jenerik-kare PNG'si (`giris_reading_master_runaware.png` / `master_dilim\*_p0N.png`) açıldı; hâlâ belirsiz kalan ~35 vaka WebSearch ile kadro/yönetmen/olay-örgüsü bağımsız doğrulandı.
- **Hüküm ölçütü:** SUSPECT_MISMATCH = çıkarılan yönetmen/kadro, katalog başlığıyla hiçbir makul ilgisi olmayan, belirli/farklı/tanımlanabilir gerçek bir yapıma ait (Ugetsu/Caruso deseni). Türkçe-çevrilmiş/yerelleştirilmiş yabancı başlıklar, devam/franchise numaraları, antoloji şemsiye-başlıkları (TOPLU GÖSTERİLER) NORMAL kabul edildi, işaretlenmedi.

### 2.2 Sonuç
| Hüküm | Adet | % |
|---|---|---|
| MATCH | 112 | 78.3 |
| NO_DATA (kadro/yönetmen okunamamış — ayrı OCR sorunu) | 31 | 21.7 |
| SUSPECT_MISMATCH | **0** | 0 |
| UNCERTAIN (çözülemeyen) | 0 | 0 |

**Yorum:** 143 kayıtlık örneklemde — ki bunun 112'si somut kadro/yönetmen/olay-örgüsü kanıtıyla gerçek bir yapıma bağlandı, 35'i ayrıca WebSearch ile bağımsız doğrulandı — Ugetsu/Caruso türü ikinci bir vaka **bulunamadı**. Bu, sorunun şu an için **izole** olduğuna dair güçlü kanıt. Ama kesin kanıt değil: 152 kayıt (97 KONTROL + işlemdeki ~46-55 hub) hiç taranmadı, ve 31 NO_DATA kaydı (kadro/yönetmen tümüyle boş/okunamaz) bu kontrol için doğası gereği bilgisiz kaldı — yani aralarında sessiz bir uyuşmazlık olması teorik olarak dışlanamaz.

### 2.3 Tam sonuç tablosu (143 satır)

*(DURUM = ONAYLI: zaten insan-onaylı/teslim edilmiş. KONTROL: hâlâ insan-incelemesi bekliyor.)*

| TRT-kimlik | Katalog Başlığı | Durum | Hüküm | Kanıt (kısa) |
|---|---|---|---|---|
| 1900-0138-0-0009-00-1 | 21. YÜZYIL EŞİĞİNDE TÜRK AİLESİ | KONTROL | MATCH | Türkçe belgesel-dizi, sunucu kadrosu+konu tutarlı |
| 1942-0020-1-0000-00-1 | LAUREL HARDY | KONTROL | MATCH | = "A-Haunting We Will Go" (1942), web-doğrulandı |
| 1955-0046-1-0000-00-1 | ŞEYTAN RUHLU İNSANLAR | ONAYLI | MATCH | = "Les Diaboliques" (1955, Clouzot) |
| 1956-0062-1-0000-00-1 | PROFESÖR HANNIBAL | KONTROL | NO_DATA | Kadro/yönetmen boş; orijinal_ad="PROFESSOR HANNIBAL" ipucu var ama teyit-verisi yok |
| 1958-0046-1-0000-00-1 | BEKARLIK SULTANLIKTIR | KONTROL | NO_DATA | Kare-görüntüsü açıldı, gerçek isim verisi çıkmadı (görüntü-gürültüsü) |
| 1960-0021-1-0000-00-1 | BÜYÜK MÜCADELE | ONAYLI | MATCH | Galsworthy "Strife" TV uyarlaması, web-doğrulandı |
| 1960-0039-1-0000-00-1 | BELL BOY | KONTROL | MATCH | Ham-OCR "Paramount Release"+"Fontainebleau" = "The Bellboy" (1960, Jerry Lewis) |
| 1962-0022-1-0000-00-1 | GERONIMO | ONAYLI | MATCH | Chuck Connors/Arnold Laven = "Geronimo" (1962) |
| 1962-1124-1-0000-72-0 | IVAN'IN ÇOCUKLUĞU | KONTROL | MATCH | = "Ivan's Childhood" (Tarkovsky, 1962), orijinal_ad doğruluyor |
| 1966-0006-1-0000-90-1 | İYİ KÖTÜ VE ÇİRKİN | ONAYLI | MATCH | = "The Good, the Bad and the Ugly" (Leone) |
| 1967-0037-1-0000-00-1 | MUTLU GÜNLER | KONTROL | NO_DATA | Tam işlem hatası (OCR/ASR/LLM başarısız) |
| 1968-0082-1-0000-00-1 | BANA TRINITY DERLER | KONTROL | MATCH | = "They Call Me Trinity" (1970), kadro birebir |
| 1969-0091-1-0000-00-1 | KOPAR ZİNCİRLERİNİ GÜLSARI | KONTROL | MATCH | Aitmatov "Elveda Gülsarı" konusuyla birebir |
| 1970-0046-1-0000-00-1 | NORWOORD | KONTROL | MATCH | = "Norwood" (1970, Glen Campbell), karakter adları birebir |
| 1970-0072-1-0000-00-1 | KIRKSEKİZ SAAT | ONAYLI | MATCH | = "The Forty-Eight Hour Mile" (1970, "The Outsider" TV), web-doğrulandı |
| 1970-0076-1-0000-00-1 | ŞAŞKIN REKLAMCI | KONTROL | MATCH | = "Le Distrait" (1970, Pierre Richard) |
| 1971-0079-1-0000-40-1 | ÖLÜM VURUŞU | ONAYLI | MATCH | = "Shoot Out" (1971, Gregory Peck) |
| 1973-0211-1-0000-00-1 | BİR BEBEK EVİ | KONTROL | MATCH | Ibsen "A Doll's House" konusuyla birebir |
| 1975-0185-1-0000-00-1 | LIBERA SEVGİLİM | KONTROL | MATCH | = "Libera, amore mio!" (1975, İtalyan) |
| 1975-2246-1-0000-72-0 | DERSU UZALA | KONTROL | MATCH | Kadro (Solomin/Munzuk) birebir; yönetmen-alanı ayrı hatalı (bkz. §2.4) |
| 1976-0179-1-0000-00-1 | DÜNYANIN EN İYİ İNSANI | ONAYLI | MATCH | = "The Nicest Man in the World" (1976), web-doğrulandı |
| 1976-0184-1-0000-00-1 | ANGOLA'DAN KAÇIŞ | ONAYLI | MATCH | = "Escape from Angola" (1976, Ivan Tors), web-doğrulandı |
| 1978-0220-1-0000-00-1 | KOLEKSİYON | KONTROL | MATCH | = "The Collection" (1976 TV, Pinter), kadro birebir |
| 1979-0203-1-0000-00-1 | SİBİRYADAN 2 | KONTROL | MATCH | = "Sibiriade/Siberiade" (1979), kadro (Mikhalkov vb.) birebir |
| 1980-0149-1-0000-00-1 | METİN | KONTROL | MATCH | Gerçek Alman TV filmi "Metin" (1979/80), web-doğrulandı |
| 1981-0287-1-0000-00-1 | JONSSON ÇETESİ | ONAYLI | MATCH | = "Lilla Jönssonligan..." (İsveç), web-doğrulandı |
| 1983-0223-1-0000-00-1 | SICAK VE TOZ | ONAYLI | MATCH | = "Heat and Dust" (1983, Merchant-Ivory) |
| 1983-0234-1-0000-00-1 | REKABET | KONTROL | MATCH | Yönetmen Franz Marx gerçek/doğrulanmış; not: afiş-bug'ı ayrı (BULGU #1) |
| 1983-0256-1-0000-00-1 | ADI CARMEN | ONAYLI | MATCH | = "Prénom Carmen" (1983, Godard) |
| 1984-0286-1-0000-00-1 | ALTIN VE ŞÖHRET | KONTROL | NO_DATA | Kadro/yönetmen tümüyle boş; web-arama da doğrulayamadı |
| 1985-0223-1-0000-00-1 | AMANSIZ TAKİP | KONTROL | MATCH | Kadro = Sammo Hung/Jackie Chan/Yuen Biao üçlüsü |
| 1986-0240-1-0000-00-1 | VİDEO OYUNU | KONTROL | MATCH | = "Videopoly" (İsviçre bilim-kurgu), web-doğrulandı; not: afiş-bug'ı ayrı (BULGU #1) |
| 1986-0334-1-0000-00-1 | AĞAÇ | KONTROL | MATCH | = "L'Arbre" (1982, Jeanne Moreau), web-doğrulandı; not: afiş-bug'ı ayrı (BULGU #1) |
| 1987-1235-1-0000-00-1 | ÇÖL ASLANI | ONAYLI | MATCH | = "Lion of the Desert" (Akkad/Quinn) |
| 1988-0308-1-0000-00-1 | NAPOLYON | ONAYLI | MATCH | = "Napoléon" (1955, Sacha Guitry) |
| 1988-0316-1-0000-00-1 | SÜPER ZEKALI ÇOCUK | ONAYLI | MATCH | = "The Kid with the 200 I.Q." (1983), kadro birebir |
| 1988-0420-1-0000-00-1 | LA BOHEME | KONTROL | NO_DATA | Altyapı hatası (ollama erişilemedi), tüm alanlar boş |
| 1988-0425-1-0000-00-1 | İŞTE BIRD | ONAYLI | MATCH | = "Bird Now" (1987, Charlie Parker belgeseli), web-doğrulandı |
| 1988-0430-1-0000-00-1 | LALELER | KONTROL | NO_DATA | Aynı altyapı hatası |
| 1988-1557-1-0000-00-1 | İKİ KOCALI KADIN | ONAYLI | MATCH | = "Doucement les basses!" (1971, Delon), web-doğrulandı |
| 1988-1835-1-0000-00-1 | KURUNTULAR | ONAYLI | MATCH | Dino Campana/Sibilla Aleramo hikâyesiyle örtüşüyor |
| 1989-0476-1-0000-00-1 | VANYA DAYI | KONTROL | MATCH | Çehov uyarlaması, Leningrad BDT kadrosu, web-doğrulandı |
| 1989-0478-1-0000-00-1 | TOPLU GÖSTERİLER | ONAYLI | MATCH | İçerik = "The Eddy Duchin Story" (1956); şemsiye-başlık normu |
| 1989-0570-1-0000-00-1 | BİR YAZ MACERASI | KONTROL | MATCH | = "Fierro...l'été des secrets" (1989), web-doğrulandı |
| 1989-0624-1-0000-00-1 | DÖNÜŞÜ OLMAYAN NEHİR | ONAYLI | MATCH | = "River of No Return" (1954, Monroe/Mitchum) |
| 1989-0955-1-0000-00-1 | ÖLDÜRME ZAMANI | KONTROL | MATCH | orijinal_ad="TEMPO DI MASSACRO" (Fulci, 1966), olay-örgüsü birebir |
| 1990-0321-1-0000-00-1 | MOSKOVA BUZ BALESİ | KONTROL | NO_DATA | OCR okundu ama isim/tür çıkmadı |
| 1990-0350-1-0000-00-1 | DENİZ EJDERİ | ONAYLI | MATCH | = "Sea Dragon" (1990), web-doğrulandı |
| 1990-0390-1-0000-00-1 | SISSI-1 | KONTROL | MATCH | = "Sissi" (1955, Romy Schneider) |
| 1990-0488-1-0000-00-1 | HAYALET BABAM | ONAYLI | MATCH | = "Ghost Dad" (1990, Sidney Poitier/Cosby) |
| 1990-0519-1-0000-00-1 | TEPEDEKİ KIZ | KONTROL | NO_DATA | Nihai kayıtta boş; VL-önerisi doğrulanamadan elenmiş |
| 1991-0356-1-0000-00-1 | TOPLU GÖSTERİLER | KONTROL | NO_DATA | Minimal OCR, şemsiye-tip zaten normal |
| 1991-0415-1-0000-00-1 | AYAK TAKIMI | ONAYLI | MATCH | = "Riff-Raff" (1991, Ken Loach) |
| 1991-0441-1-0000-00-1 | GÖLGELER PRENSİ | KONTROL | NO_DATA | Kare-görüntüsü boş/okunaksız (gece sahnesi) |
| 1991-0454-1-0000-00-1 | JARRAPELLEJOSILAR | ONAYLI | MATCH | = "Jarrapellejos" (1988, İspanyol) + TR çoğul-eki |
| 1991-0469-1-0000-00-1 | ZERK'İN HİKAYESİ | KONTROL | MATCH | Başlık özetteki karakter soyadından ("Karl Zerk") |
| 1991-0525-1-0000-00-1 | OSCAR | KONTROL | NO_DATA | Minimal OCR, tüm alanlar boş |
| 1992-0299-1-0000-00-1 | GLORIA KUŞATMASI | KONTROL | MATCH | = "The Siege of Firebase Gloria" (1989), web-doğrulandı |
| 1992-0324-0-0001-00-1 | YARGIÇ VE POLİS | KONTROL | MATCH | orijinal_ad ipucu + "Les Cordier, juge et flic" (Fransız TV), web-doğrulandı |
| 1992-0454-1-0000-00-1 | HAYATIMIN ERKEĞİ | ONAYLI | NO_DATA | Yönetmen/yapımcı boş, özet üretilmemiş |
| 1992-0455-1-0000-00-1 | MELEKLERİ GÖRMEK İSTEDİM | KONTROL | MATCH | = "I Wanted to See Angels" (1992, Bodrov), web-doğrulandı |
| 1992-0468-1-0000-00-1 | CENNETE GELDİK Mİ | ONAYLI | NO_DATA | Yönetmen/tür boş, kadro KB-doğrulanamamış |
| 1992-0483-1-0000-00-1 | JOE SHARP | ONAYLI | MATCH | Başlık=başkahraman adı, yön. Don Hulette web-doğrulandı |
| 1992-0484-1-0000-00-1 | YALNIZ TOM | KONTROL | MATCH | = "Tom Alone" (Magic Hour), kadro birebir |
| 1993-0277-1-0000-00-1 | ZİRVEDEKİ YALNIZLAR | KONTROL | MATCH | = "Make and Break" (1987 TV, Frayn), web-doğrulandı |
| 1993-0401-1-0000-00-1 | ARCEDIA | KONTROL | MATCH | = "Arcadia" (1990 kısa film), kadro birebir |
| 1993-0437-1-0000-00-1 | LENI REIFENSTAHL'IN KORKUNÇ MUHTEŞEM YAŞAMI | KONTROL | MATCH | Aynı adlı Ray Müller belgeseli (1993), özet birebir |
| 1993-0467-1-0000-00-1 | BİR KATİLLE EVLENDİM | KONTROL | NO_DATA | Yönetmen/kadro tamamen boş |
| 1994-0338-1-0000-00-1 | KİNG'İN SERVETİ | KONTROL | MATCH | = "King's Ransom" (1993), kadro birebir |
| 1994-0383-1-0000-00-1 | NANCY'Yİ SEVMEK | KONTROL | MATCH | = "For the Love of Nancy" (1994), kadro+konu birebir |
| 1995-0289-1-0000-00-1 | ÜÇ KURUŞLUK OPERA | KONTROL | MATCH | = "Žebrácká opera" (Menzel, 1991), kadro birebir |
| 1995-0363-1-0000-00-1 | KÜÇÜK SİMBA DÜNYA KUPASINDA | KONTROL | NO_DATA | Yönetmen/kadro boş, yalnız yapımcı var |
| 1995-0444-1-0000-00-1 | KORKUNÇ GECE | KONTROL | NO_DATA | Tüm kimlik alanları boş |
| 1995-0475-1-0000-00-1 | SON OYUN | KONTROL | MATCH | = "The Last Game" (1995), kadro+konu birebir |
| 1995-1459-1-0000-00-1 | TOTO | ONAYLI | MATCH | = Tourneur'ün 1933 Fransız filmi "Toto", web-doğrulandı |
| 1996-0031-1-0000-00-1 | SOĞUK SUYA VURAN GÜNEŞ | ONAYLI | MATCH | = "Un peu de soleil dans l'eau froide" (1971), web-doğrulandı |
| 1996-0310-1-0000-00-1 | İŞARET DİREĞİ | KONTROL | NO_DATA | Tüm kimlik alanları boş |
| 1996-0325-1-0000-00-1 | KIZIL HAYAT | KONTROL | MATCH | Rus-Fransız kadro, mafya-dramı temasıyla tutarlı |
| 1996-0350-1-0000-00-1 | IRIS'IN SIRRI | ONAYLI | MATCH | = "Le Secret d'Iris" (1996), kadro birebir |
| 1996-0353-1-0000-00-1 | AŞK EVLİLİĞİ | KONTROL | MATCH | Yön. Pascale Bailly, Fransız kadro, tema tutarlı |
| 1996-0368-1-0000-00-1 | SAVAŞTAN DÖNÜŞ | ONAYLI | MATCH | = "The War at Home" (1996, Estevez/Sheen) |
| 1997-0217-1-0000-00-1 | ÖRGÜT | KONTROL | NO_DATA | "JENERİK YOK" |
| 1997-0353-1-0000-00-1 | KÜÇÜK AYICIK | KONTROL | NO_DATA | "JENERİK YOK" |
| 1997-0421-1-0000-00-1 | HAYAT BİR ŞARKIDIR | KONTROL | MATCH | = "On connaît la chanson" (1997, Resnais), kadro birebir |
| 1998-0312-1-0000-00-1 | KARA GÜNLER | ONAYLI | MATCH | orijinal_ad="SCHWARZE TAGE" (1995), ham-OCR'da bulundu |
| 1998-0464-1-0000-90-1 | ELMA | KONTROL | NO_DATA | "JENERİK YOK" |
| 1998-0519-1-0000-00-1 | SON CÜCE | KONTROL | NO_DATA | "JENERİK YOK" |
| 1998-1000-1-0000-00-1 | DÜŞLER ÜLKESİ | ONAYLI | MATCH | = BBC "Screenplay: The Land of Dreams" (1990), web-doğrulandı |
| 1999-0321-1-0000-00-1 | FISILTILAR | ONAYLI | MATCH | = "Stir of Echoes" (1999), kadro birebir |
| 1999-0361-1-0000-90-1 | RÜZGAR BİZİ SÜRÜKLEYECEK | KONTROL | MATCH | = "The Wind Will Carry Us" (Kiarostami, 1999) |
| 1999-0394-1-0000-90-1 | 13. SAVAŞÇI | KONTROL | MATCH | = "The 13th Warrior" (2000, McTiernan/Banderas) |
| 1999-0407-1-0000-00-1 | KÜÇÜK KAHRAMAN | ONAYLI | MATCH | = "One Small Hero" (1999), kadro birebir |
| 1999-0450-1-0000-00-1 | SCHIMANSKI HASRET | ONAYLI | MATCH | Alman "Schimanski" franchise |
| 1999-0483-1-0000-00-1 | SON TANIK | ONAYLI | MATCH | = "The Last Witness"/"Caracara" (1999), kadro birebir |
| 1999-0508-1-0000-00-1 | PAMUK MARY | KONTROL | MATCH | = "Cotton Mary" (1999, Merchant-Ivory) |
| 2000-0282-1-0000-40-1 | SEVİMLİ KÖPEK-YEDİNCİ OYUNDAKİ MUCİZE | ONAYLI | MATCH | = "Air Bud: Seventh Inning Fetch" (2002) |
| 2000-0303-1-0000-00-1 | MOTORSİKLETLİ POLİSLER | KONTROL | NO_DATA | "JENERİK YOK" |
| 2000-0323-1-0000-00-1 | 6. GÜN | ONAYLI | MATCH | = "The 6th Day" (2000, Schwarzenegger) |
| 2000-0430-1-0000-00-1 | SEVİMLİ KÖPEK 3 | KONTROL | MATCH | = "Air Bud: World Pup" (2000), konu birebir |
| 2000-0476-1-0000-00-1 | TACİZ | KONTROL | NO_DATA | Kadro/yönetmen boş |
| 2000-0479-1-0000-00-1 | HİTLER'İN HAZİNESİ | KONTROL | MATCH | Alman kadro, "Kehribar Odası" temasıyla tutarlı |
| 2000-0491-1-0000-00-1 | PARDAYYAN | ONAYLI | MATCH | = "Pardaillan" (1997 TV), kadro birebir |
| 2000-0504-1-0000-00-1 | MENZİL DIŞI | ONAYLI | MATCH | = "The Boy Who Drank Too Much" (1980), kadro birebir |
| 2000-0514-1-0000-00-1 | KÖPEKLE BİR TATİL | KONTROL | NO_DATA | Kadro/yönetmen boş |
| 2001-9167-1-0000-00-1 | HALIFAX-CANİ RUH | KONTROL | MATCH | Avustralya "Halifax f.p." dizisi |
| 2001-9171-1-0000-00-1 | SCHIMANSKI-CEHENNEM ÇOCUKLARI | ONAYLI | MATCH | "Schimanski" franchise |
| 2001-9184-1-0000-00-1 | SÜPER ŞEMPANZE 2 | ONAYLI | MATCH | = "MVP 2: Most Vertical Primate" (2001) |
| 2001-9201-1-0000-00-1 | HAYAL PEŞİNDE | KONTROL | MATCH | Fransız "Vertiges" dizisi bölümü, web-doğrulandı |
| 2001-9314-1-0000-00-1 | VAHŞİ AFRİKA | KONTROL | NO_DATA | Jenerik yok, muhtemel doğa belgeseli |
| 2001-9375-1-0000-00-1 | UZAKTAKİ KASABA | KONTROL | MATCH | = "Almost Salinas" (2003), web-doğrulandı |
| 2002-9089-1-0000-90-1 | YÜZÜKLERİN EFENDİSİ | KONTROL | MATCH | = "The Two Towers" içerik; kardeş-ID (Fellowship) ile karışmamış |
| 2002-9202-1-0000-00-1 | SHERLOCK HOLMES'İN DOĞUŞU | ONAYLI | MATCH | = "Murder Rooms" (2000), konu birebir |
| 2002-9241-1-0000-00-1 | SESSİZ AMERİKALI | KONTROL | MATCH | = "The Quiet American" (2002), kadro birebir |
| 2002-9246-1-0000-00-1 | RENE | ONAYLI | MATCH | Yön. Alain Cavalier, başlık zaten orijinal |
| 2003-9048-1-0000-00-1 | İHTİRAS CİNAYETİ | ONAYLI | MATCH | Yapımcılar (Longbow Productions) web-doğrulandı |
| 2003-9059-1-0000-00-1 | CİNAYET YERİ | ONAYLI | MATCH | = "Murder Seen/Scene" (2000, Kanada TV), web-doğrulandı |
| 2003-9136-1-0000-00-1 | HARİKA KÖPEK 5 | KONTROL | MATCH | = "Air Bud: Spikes Back" (2003), kadro birebir |
| 2003-9195-1-0000-00-1 | JERICO APARTMANI | KONTROL | MATCH | = "Jericho Mansions" (2003, James Caan) |
| 2003-9208-1-0000-00-1 | BORÇ | KONTROL | MATCH | Kare-görüntüsünde "BORÇ" başlık-kartı doğrudan görüldü |
| 2004-9094-1-0000-00-1 | İSYAN | ONAYLI | MATCH | = Bollywood "Hu Tu Tu" (1999, Gulzar), kadro birebir |
| 2004-9131-1-0000-00-1 | YALNIZ SAVAŞÇI | KONTROL | MATCH | = "Spartan" (2004, David Mamet) |
| 2004-9139-1-0000-00-1 | GÜLLERİN SAVAŞI | KONTROL | NO_DATA | Jenerik yok |
| 2004-9160-1-0000-90-1 | HOTEL RWANDA | KONTROL | MATCH | = "Hotel Rwanda" (2004), kadro birebir |
| 2005-9051-1-0000-00-1 | MURPHY KANUNLARI 2 | KONTROL | NO_DATA | Jenerik yok |
| 2005-9135-1-0000-90-1 | AEON FLUX | ONAYLI | MATCH | Charlize Theron, kadro birebir |
| 2006-9063-1-0000-40-1 | KUMRULAR GİBİ | KONTROL | NO_DATA | Jenerik yok |
| 2006-9112-1-0000-90-1 | BÜYÜK FİNAL | KONTROL | MATCH | = "La Gran Final"/"The Great Match" (2006), web-doğrulandı |
| 2007-9067-1-0000-00-1 | YARIŞMA DÜNYASI | KONTROL | MATCH | = "El concursazo" (2007, İspanya), web-doğrulandı |
| 2008-9069-1-0000-00-1 | BEYAZ AVUÇLAR | KONTROL | MATCH | = "Fehér tenyér/White Palms" (2006, Macar), web-doğrulandı |
| 2008-9110-1-0000-90-1 | ŞAMPİYONLAR | KONTROL | MATCH | = "Champions" (2008, HK), web-doğrulandı |
| 2009-9007-1-000-00-1 | HAYATIN TUZU | KONTROL | MATCH | Türk yapım, Türk kadro tutarlı |
| 2009-9153-1-0000-00-1 | AJAMİ | KONTROL | MATCH | = "Ajami" (2009, İsrail), kadro birebir |
| 2010-9150-1-0000-00-1 | HANNA'NIN ALTINLARI | KONTROL | NO_DATA | "JENERİK YOK" |
| 2010-9199-0-0001-88-1 | AYNADAKİ DÜŞMAN | KONTROL | MATCH | Gerçek TRT dizisi, Arapça-dublaj OCR-çöpü (bkz. §2.4) |
| 2010-9262-1-0000-88-1 | NAMUS DÜŞMANI | KONTROL | MATCH | Gerçek 1986 Türk filmi (Zeki Alasya), web-doğrulandı |
| 2010-9280-1-0000-88-1 | MİRAS | KONTROL | MATCH | Gerçek 2008 Türk filmi, kadro birebir |
| 2011-9175-1-0000-90-1 | SHAOLIN | ONAYLI | MATCH | Andy Lau/Jackie Chan, kadro birebir |
| 2011-9209-1-0000-90-1 | EL GUSTO | KONTROL | NO_DATA | "JENERİK YOK" |
| 2015-0134-1-0000-85-1 | ADI YUNUS | ONAYLI | MATCH | Türk yapım, kadro+yönetmen tutarlı |
| 2015-0138-1-0000-85-1 | YA NASİP YA KISMET | KONTROL | NO_DATA | Kadro OCR-bozuk, tanınmıyor |
| 2018-9036-1-0000-00-1 | KRAL LEAR | KONTROL | NO_DATA | "JENERİK YOK" |
| 2025-1240-1-0000-90-1 | FERDİNAND | ONAYLI | MATCH | = "Ferdinand" (2017 animasyon), sahne-sahne örtüşüyor |
| 2025-1295-1-0000-50-1 | UMUTSUZ SAAT | KONTROL | MATCH | = "The Desperate Hour"/"Lakewood" (2021) |

### 2.4 Yan-bulgular (görev-dışı ama not edilmeye değer)

- **Mevcut "yanlış-film şüphesi" bayrağının yanlış-pozitif oranı yüksek:** `_DURUM.json`'larda zaten var olan `"kimlik kurulamadı (cast-örtüşmesi 0)"` bayrağı (§1.3'teki aynı kapı, susturulmadığı durumlar) obscure/yabancı/mainstream-olmayan yapımlarda (Sovyet tiyatro filmi, Québec-Arjantin ortak yapımı, Fransız TV dizisi, İtalyan spagetti-western) sık yanlış-alarm veriyor — bu taramada bu bayrağı taşıyan 6 kayıttan (VANYA DAYI, BİR YAZ MACERASI, ÖLDÜRME ZAMANI, YARGIÇ VE POLİS, BELL BOY, IVAN'IN ÇOCUKLUĞU) **hepsi** bağımsız doğrulamada gerçek MATCH çıktı. Yani bu bayrak tek başına ne "güvenli" ne "şüpheli" anlamına geliyor — referans KB'nin obscure yapımları iyi indekslememesinden kaynaklanan gürültü.
- **AYNADAKİ DÜŞMAN (2010-9199):** İlk bakışta şüpheli görünüyordu (yönetmen doğru ama kadro tamamen farklı Arapça isimler). Kare-görüntüsü açılınca gerçek bir TRT dizisi olduğu ama Arapça-dublajlı yayın kopyası olduğu anlaşıldı — "oyuncu" alanı ekrandaki Arap-harfli künye metninin OCR-transliterasyon çöpüydü. Bu, projenin bilinen "OCR-kalite" sorun sınıfına giriyor, Ugetsu-tipi kimlik uyuşmazlığına değil.
- **DERSU UZALA (1975-2246):** Zaten `KONTROL_LOOP_20260707/RAPOR.md`'de ayrıca belgelenmiş bir "yönetmen-alanı hatası" (Kurosawa'nın adı hiçbir yerde yok, "Vladimir Vasilyev" farklı biri olabilir şüphesi) — bu taramada da doğrulandı: kadro (Solomin/Munzuk) filmi kesin olarak doğruluyor, sorun AYNI film içinde bir alan-karışıklığı (muhtemelen Kiril "АКИРА КУРОСАВА" harflerinin OCR-homoglif yanlış-okuması), katalog-başlık/içerik uyuşmazlığı DEĞİL.

---

## 3. KARAR GEREKTİREN NOKTA — DEĞİŞMEDİ

**1997-0411-1-0000-00-1 için "Omaggio a Caruso" mı "Ugetsu" mü doğru TRT-kimliği, bu araştırmayla çözülmedi ve çözülemez** — bu MITAS'ın kod-tarafında karar verilecek bir şey değil. Kayıt KONTROL'de dokunulmadan bekliyor.

### Önerilen sonraki adımlar (UYGULANMADI, yalnızca öneri — karar Çağatay'ın)
1. **TRT arşiv ekibine bildirim:** 1997-0411 kimliğinin fiziksel kaynak-kaseti/orijinal kayıt-defteri ile çapraz-kontrolü — `evoArcadmin` dijitalleştirme toplu-işleminin "COZUMLEME SAYFA12" manifestosunun (muhtemelen `W:\23.05 sonrası FİLMLER\5\` civarında, bu oturumda erişilemedi) TRT'nin kendi arşiv-kaydıyla uyuşup uyuşmadığının doğrulanması.
2. **(opsiyonel, kod-tarafı, TASARLANMADI/UYGULANMADI):** `MITAS_XMLCAST_GATE_RELAX` davranışı gözden geçirilebilir — ya da dar/additive bir ek-kapı: kimlik-motoru "locked" olsa bile, çözülen kimliğin (yönetmen adı/dil/üretim-menşei) katalog başlığından KÖKTEN farklıysa (örn. tamamen farklı alfabe/dil-ailesi) insan-KONTROL'e düşürmeye devam etsin. Bu sadece bir gözlem — tasarlanmadı, test edilmedi, riski ölçülmedi.
3. **Tarama genişletilebilir:** İstenirse taranmayan 152 kayıt (97 KONTROL + işlemdeki hub'lar) için aynı yöntem tekrarlanabilir; şu anki 143'lük örneklem "izole" hipotezini güçlü destekliyor ama %100 kapsamıyor.

---

## Yöntem ve dürüstlük notu
- 11 paralel araştırma-ajanı kullanıldı (1 kod-araştırma + 10 örnekleme-batch'i); hepsi salt-okunur çalıştı, Read/Grep/Bash-ls/WebSearch dışında araç kullanmadılar.
- Hiçbir dosya, `_DURUM.json`, kod satırı ya da PDF değiştirilmedi/silinmedi.
- `W:\` sürücüsüne bu oturumda okuma erişimi yoktu ("Permission denied") — TRT'nin fiziksel kaynak-kaydı/manifestosu bu yüzden doğrudan görülemedi; tüm kanıtlar `E:\MITAS\Database\` altındaki JSON/metin/görüntü dosyalarından.
- 31 NO_DATA kaydı kanıt-eksikliğinden MATCH/SUSPECT_MISMATCH olarak zorlanmadı — dürüst çekimserlik tercih edildi.
