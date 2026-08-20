# Kalan-91 Taze Atlası + rec-Eşitlik Simülasyonu (M9)

> Bağlam: `docs/MITAS_Master_Dup_Kok_Sebep_Plani_v1.md` (M7/M8 takibi). Taban:
> Ex_Frame 427 filmde sağlık %78.0 (333/427, det-fix ÖNCESİ); hedef ≥%91
> (+56 film gerek). Kalan 94 sağlıksızın 91'i `dup_oran_yuksek`. Bu doküman
> SALT-TEŞHİS: (1) paylaşılan det motorunun kısa-kırpım salınımını gideren
> küçük fix + kanıtı, (2) 91 filmin TAZE (eski etikete güvenmeden) yeniden
> sınıflandırılması, (3) `hizli-silah` özelinde aday/karar iz-dökümü +
> toleranslı-REC-eşitliği OFFLINE simülasyonu, (4) projeksiyon tablosu.
> Composer'a (`OCR-worktree/db_compose_master.py`) TEK SATIR dokunulmadı --
> yalnız onun SALT-OKUNUR export ettiği det/rec/dHash/gray-diff yardımcıları
> (`uret.py` üzerinden `_dc()`) teşhis amaçlı çağrıldı.

## 1. Det-None stabilite fix'i (küçük fix)

**Bulgu:** `harness/master_dup/saglik.py:det_metin_var()` (tek-kart istisnası,
K4-ii) paylaşılan PaddleOCR `TextDetection` motorunu kısa/dar kırpımlarda
çağırıyordu; motor bu boyutlarda ARA SIRA sessizce istisna atıp `None`
dönüyordu (`_f1b_det_boxes` içinde yakalanıp `None`'a çevriliyor). Kırılma
noktası tam olarak **32px** civarında: `mavzer`/`solaris` (H=25/31px) art arda
ölçümlerde True/False arasında sıçrıyordu, `ipek-yolu`/`kasabanin-gulu`/
`yilmayan-adam` (H=43-73px) ise 4/4 tutarlı kalıyordu.

**Fix (`harness/master_dup/saglik.py`):**
1. `DET_MIN_KIRPIM_PX = 32` -- h VEYA w bu eşiğin altındaysa det'e HİÇ
   girilmez, deterministik "metin-yok" (`False`) sayılır.
2. 32px üstü kırpımlarda `_f1b_det_boxes` `None` dönerse (composer'ın
   "istisna/kapı geçmedi" durumu) 1 kez daha denenir; hâlâ `None` ise o tur
   için deterministik boş-kutu-listesi sayılır (`boxes` bundan sonra HER ZAMAN
   bir liste -- None bir daha dışarı sızmaz).
3. Composer'ın karar yollarına (`db_compose_master.py`) DOKUNULMADI -- yalnız
   sağlık/ölçüm tarafı (`saglik.py`) değişti.

**Kanıt -- 3 ardışık tam-427 ölçüm (fix SONRASI):**

| Koşu | Sağlıklı | Oran | İhlal dağılımı |
|---|---|---|---|
| run1 | 331/427 | %77.52 | dup_oran_yuksek=91, boy_anormal=6, uretim_basarisiz=1, doku_kapsami_dusuk=1 |
| run2 | 331/427 | %77.52 | (birebir aynı) |
| run3 | 331/427 | %77.52 | (birebir aynı) |

Üç koşu arasında **0 film farkı** (tam 427-film popülasyonu birebir diff'lendi
-- run1/run2/run3 ikili karşılaştırmaların HİÇBİRİNDE tek bir film bile
değişmedi). `mavzer`, `solaris`, `ipek-yolu`, `kasabanin-gulu`, `yilmayan-adam`
üçünde de tutarlı `boy_anormal` (det hiç çağrılmadı, h<32px). Salınım ≤±1
kanıtı **fazlasıyla** karşılandı (gerçek salınım = 0).

**Yan not (beklenen, kasıtlı):** fix ÖNCESİ tek ölçümde 333/427 (%78.0) idi
(bu koşuda `mavzer`/`solaris` "şanslı" True gelmişti); fix SONRASI 331/427
(%77.52) -- **-2 film**. Bu, motorun güvenilir-olmayan rejimine hiç
girilmediği için beklenen, kasıtlı bir değiş-tokuş: "şansa bağlı optimistik"
sonuç yerine deterministik/tutarlı (ve bu ölçekte muhafazakâr) sonuç tercih
edildi. Sağlık ORANI değil, ÖLÇÜMÜN GÜVENİLİRLİĞİ bu fix'in amacıydı.

**Commit:** `fix(master-dup): det-None stabilite fix'i -- 32px kısa-kırpım kapısı (M9)`

---

## 2. Kalan-91 taze atlası -- S1..S4 dağılımı

**Yöntem** (`harness/master_dup/kalan91_atlas.py`, SALT-ANALİZ): her filmin
`metrik.json`'undaki TÜM tekrar bloklarının "es" (yalnız tekrar/sonraki taraf,
dup_metrik'in kendi muhasebesiyle TUTARLI) y-aralığı, manifest'in kept-blok
kümülatif y-aralıklarına eşlenip piksel-kapsama ağırlıklı olarak
`static_page` / `scroll_slit` kind'ine bölüştürüldü (yalnız en büyük 5 bloğu
değil, TÜMÜNÜ kapsar -- karışık/S1+S2 filmlerin S1 payını gizlemez).

**Önemli düzeltme (görsel örneklem bulgusu, `tarzan-kaciyor`):** bazı "tekrar"
blokları AYNI kept-bloğun (src_idx==es_idx) İÇİNDE kaydırılmış bir ofsette
kendisiyle eşleşiyor -- kart-arası değil. Görsel doğrulamada bu türden bir
örnek FARKLI metin içeriyordu (dup_metrik'in tekrarlayan yerleşim/alt-çizgi
deseni üzerindeki YANLIŞ-POZİTİFİ). Bu yüzden "self" (kendine-eşleşme) ve
"cross" (kart-arası, gerçek H2/F1c hedefi) ayrı hesaplandı; SINIFLANDIRMA
yalnız CROSS kapsamasına göre yapıldı.

### Dağılım (91/91)

| Sınıf | Film sayısı | Oran | Tanım |
|---|---|---|---|
| **S1** (saf, ≥%50 slit) | **0** | %0 | kart-arası tekrarın çoğunluğu `scroll_slit` bloklara düşüyor |
| **S2** | **73** | %80.2 | iki taraf da `static_page`, filmde HİÇBİR distant-dup* izi yok -- aday hiç ateşlenmemiş |
| **S3** | **5** | %5.5 | iki taraf da `static_page`, filmde F1c rec-hakemi (`rec_kanit`) izi VAR ama bu çift ayrı |
| **S3b** | **3** | %3.3 | iki taraf da `static_page`, filmde F1/F1b skip izi var (rec_kanit yok) ama bu çift ayrı |
| **S4** (belirsiz) | 3 | %3.3 | kart-arası eşleşme net değil (bir kısmı boundary/mapping kusuru -- bkz. not) |
| **S4-az-blok** | 1 | %1.1 | `kaptan-january` -- ÜRETİM BAŞARISIZ (status≠OK), gerçek bir "dup" vakası değil |
| **S4-kendine-eslesme** | 6 | %6.6 | tekrarın ≥%90'ı AYNI blok içi self-match -- metrik/kompozisyon artığı |
| **Karışık** (S1+S2, her ikisi ≥%20, S2 içine gömülü) | 5 | %5.5 | `aslan-yurekli-cavus, belki-bir-gun, buyuk-umutlar, demiryolu-kovboyu, tas-devri` |

**S1 SIFIR çıkması ÖNEMLİ bir bulgu:** orijinal plan (M3/ex_dup_siniflandirma.md,
K1/K3 fix'lerinden ÖNCEKİ 135-film havuzu) A2/slit-tekrarını ~%30-39
(41/135 projeksiyon) tahmin ediyordu. K1/K3/F1c fix'leri SONRASI kalan-91'de
saf S1 payı ölçülemez küçük (yalnız 5 film "karışık", hiçbiri saf-slit-baskın
değil). **Eski etiketlere güvenmeme talimatı DOĞRU çıktı** -- slit/pencere-
örtüşmesi artık kalan-91'in birincil itici gücü DEĞİL.

### S4-kendine-eslesme çapraz-doğrulama (D-class ile tutarlı)

`S4-kendine-eslesme` listesindeki `tehlikeli-yolculuk-kentucky-guzeli`
(dup=0.1282), **ex_dup_siniflandirma.md'nin ÖNCEKİ "D" bulgusuyla BİREBİR
örtüşüyor** ("kept_blocks=1, gerçekten tek sayfa, düz/gradyanlı gökyüzü bandı
kendi içinde başka bir düz banda YP ile eşleşti"). Bu, self/cross ayrımının
gerçek bir metrik-katmanı yanlış-pozitifini doğru yakaladığının bağımsız
kanıtı. Diğer 5 kendine-eşleşme filmi (`deli-doktoru, laurel-hardy,
savas-mahkemesi, serifi-destekleyin, yanlis-araba`) görsel örneklemde
(`deli-doktoru`) GERÇEKTEN aynı görsel içeriği (aynı "FINE" tabelası) iki kez
gösteriyordu -- bunun saf metrik-YP mi yoksa composer'ın tek-blok içinde
tuttuğu-hold'u gereksiz uzatması mı olduğu netleşmedi (küçük sınıf, %6.6,
düşük öncelik -- ayrı bir mini-teşhis gerektirir).

---

## 3. Görsel doğrulama (25 tanık kırpımı üretildi, 14+ doğrudan incelendi)

Tanık kırpımları: `data/master_ex/_kalan91/<slug>_witness.png` (kaynak/tekrar
yan yana, CROSS-blok tercih edilir -- self-match yanıltıcı olduğundan
witness seçiminde ELENIR).

**Doğrulanan alt-desenler (görsel + REC metniyle çapraz-kontrol):**

| Alt-desen | Örnekler | Yorum |
|---|---|---|
| Gerçek özdeş statik kart (aynı metin, iki kez) | `cek-postaya-verildi, aslan-yurekli-cavus (THE END), dr-doolithl, holman-kalesinde-katliam, mavi-gokyuzu, kabaran-ofke, borsa, ask-ruzgari, celestina` | Klasik S2 -- gerçek H2, adayın hiç ateşlenmemesi ciddi içerik-kaybı riski |
| **Kayan-liste/scroll AŞIRI-BÖLÜNME** (yeni bulgu, aşağıda detay) | `onemsizlik, belki-bir-gun, gecmisten-gelen, sihirli-ev, hizli-silah` | "static_page" etiketli ama ASLINDA sürekli scroll; kart-sınır tespiti gren/küçük kaymayı "yeni kart" sanıyor |
| Aynı arka-plan + FARKLI metin (C-benzeri, meşru fark) | `kacis, buyuk-umutlar (kısmi), muhtemelen babam-ve-ben'in top-pair'i` | dup_metrik baskın-piksel (arka plan) eşleşmesini "tekrar" sayıyor; İÇERİK FARKLI -- BİRLEŞTİRİLMEMELİ |
| Kendine-eşleşme (metrik/kompozisyon artığı) | `tehlikeli-yolculuk-kentucky-guzeli (D-class ile teyitli), deli-doktoru` | Küçük sınıf (%6.6), ayrı mini-teşhis gerekir |

### KRİTİK BULGU -- `hizli-silah` yeniden-teşhisi (eski etiket YANLIŞTI)

`ex_dup_siniflandirma.md` (K1/K3 ÖNCESİ) `hizli-silah`'ı "4 kart, hepsi Cast
of Characters listesinin BİREBİR aynı metnini taşıyor" (A1/statik-tekrar)
olarak etiketlemişti. **Ham kareleri (`exit_000540/544/548.png`)
doğrudan görsel incelemede bu YANLIŞ çıktı:** kareler aslında SÜREKLİ,
YAVAŞ KAYAN bir "Cast of Characters" listesinin ÖRTÜŞEN pencereleri --
`exit_000540` "Clint Cooper...Reverend Slater" gösterirken `exit_000544`
aynı listeyi bir-iki satır aşağı kaymış halde ("...Reverend Slater, Don
Evans") gösteriyor; `exit_000548` daha da aşağı kaymış. Bu KLASİK bir
kayan-liste/scroll deseni -- ama composer'ın run-sınıflandırması bunu
`static_page` (kart) olarak etiketlemiş ve `split_static_cards` her küçük
kaymayı "yeni kart" sanıp 5 ayrı statik karta bölmüş. **Bu H2 (uzak-kart-
tekrarı) DEĞİL, H3'e yakın bir mekanizma (scroll'un statik sanılması, ama
kart-bölme granülaritesi seviyesinde).**

**Aday/karar iz-dökümü** (`harness/master_dup/hizli_silah_iz.py --iz`,
composer'ın SALT-OKUNUR export ettiği gerçek F1/F1b fonksiyonları çağrılarak):
5 kart arasındaki **TÜM 10 çift** için hem F1 (maskeli-dHash) hem F1b
(gri faz-hizalı piksel-fark) kapısı test edildi:

| Ölçü | Sonuç |
|---|---|
| F1 dHash hamming (eşik≤4) | **20-29** (10/10 çift eşik ÜSTÜ, ~5-7x aşım) |
| F1b global_fark (eşik<0.06) | 0.036-0.22 (çoğu eşik üstü, en iyi 0.036 bile marjinal) |
| F1b max_band_fark (eşik<0.10) | 0.14-0.29 (10/10 çift eşik ÜSTÜ) |
| **Sonuç: aday hiç ateşlenmedi** | **10/10 çiftte HEM F1 HEM F1b kapısı reddetti** |

Bu, manifest'te hiçbir `skip` izi olmamasını TAM açıklıyor -- S2 sınıflaması
mekanik olarak doğru (aday ateşlenmedi), ama KÖK SEBEP "uzak kart" değil
"gren + gerçek küçük kayma, kompozisyonun tek-kart sandığı ortak yerleşim".

**Ayrıca (teşhis amaçlı, üretim ASLA bunu çağırmaz):** kapı geçilmese bile
REC ne okuyor diye bakıldı -- sonuç **güven 0.46-0.53** ile OKUNAMAZ/GARBLED
metin ("cdo vntersade ton atism brch..."). Bu, film greninin yalnız dHash'i
değil REC'in kendisini de köreltebileceğini gösteriyor: **`hizli-silah`
özelinde, aday-kapısı bypass edilse BİLE güven-ağırlıklı toleranslı-eşitlik
(gate=0.6) bu çiftleri GÜVENLİ ŞEKİLDE reddedecekti** (garbage'ı garbage ile
eşleştirmiyor) -- yani bu FİLM için önerilen "toleranslı REC" fix'i tek
başına YETERSİZ; gerçek çözüm scroll/örtüşme-kırpma tarzı bir yaklaşım
(F2'nin NCC-dikiş mantığının statik-kart moduna genişletilmesi ya da
kart-bölme sınır-hassasiyetinin düzeltilmesi).

---

## 4. Genelleştirilmiş hipotez testi -- 80 aday çiftte toleranslı-eşitlik simülasyonu

**Kare-mesafe istatistiği (80 S2/S3/S3b cross-çifti, TÜMÜ):** `hizli-silah`
deseni izole bir vaka DEĞİL -- kalan-91'in geneline yayılmış:

| Ölçü | Değer |
|---|---|
| Medyan kare-mesafesi | **4 kare** (~3.2sn @1.25fps) |
| Ortalama | 10.0 kare |
| ≤10 kare (~8sn) | **59/80 (%73.75)** |
| ≤20 kare (~16sn) | 68/80 (%85.0) |
| >50 kare (gerçek "uzak" kart) | **1/80 (%1.25)** |

Bu, orijinal H2 varsayımının ("ardışık-OLMAYAN/uzak kart tekrarı" -- F1'in
global kart-kaydının TAM olarak hedeflediği senaryo) kalan-91 popülasyonunda
**neredeyse YOK** olduğunu gösteriyor. Baskın desen `hizli-silah` ile aynı:
YAKIN kareler arasında (çoğunlukla birkaç saniye), muhtemelen ya (a) yavaş
scroll'un statik-kart sanılıp aşırı bölünmesi, ya da (b) gerçekten sabit bir
kare uzun tutulurken gren/titremenin kart-sınır dedektörünü yanlış tetiklemesi.

**Simülasyon** (`harness/master_dup/hizli_silah_iz.py --simulasyon`,
S2+S3+S3b'nin her birinin TOP cross-çiftinde gerçek det+rec koşturuldu --
composer'a dokunulmadan, offline): mevcut KATI eşitlik kuralı (`real_a==
real_b`) ile toleranslı kural (normalize + Levenshtein-oran≤0.15 +
güven-ağırlıklı, conf≥0.6) karşılaştırıldı.

| Ölçü | Değer |
|---|---|
| Test edilen aday çift | 80 |
| Mevcut KATI kuralla ZATEN eşit olurdu | **3** (`ask-ruzgari, borsa, celestina` -- "THE END"/"FINE" panoları) |
| Toleranslı kuralla YENİ birleşen | **4** (`alice-harikalar-diyarinda, ask-sarkisi, belki-bir-gun, cep-harcligi`) |
| **Toplam birleşen / yanlış-birleşme** | **7 çift birleşti, 0 yanlış-birleşme (görsel + metin çapraz-kontrolüyle 7/7 GERÇEK özdeş)** |

**Yanlış-birleşme oranı: %0 (7/7 doğrulanan çift gerçek özdeş).** Toleranslı
kural GÜVENLİ görünüyor (bu örneklemde) ama **VERİM DÜŞÜK**: 80 adaydan
yalnız 7'si (%8.75) kurtarıldı. 5 "yakın-ıskala" (lev-oranı 0.21-0.33,
eşiğin hemen üstü) incelendiğinde ikisi (`intikam-gecidi: "A PARAMOUNT
PICTURE" vs "C PARAMOUT GICTUE"`, `aslan-yurekli-cavus: "THE END WARNER
BROS..."`) OCR-gürültüsü yüzünden kaçırılan GERÇEK tekrarlar (eşik biraz
gevşetilse +2 daha kurtarılabilir), ama **DİĞER ÜÇÜ** (`onemsizlik,
gecmisten-gelen, sihirli-ev`) **KISMİ-ÖRTÜŞEN scroll listeleri** --
Levenshtein-EŞİTLİĞİ yapısal olarak yanlış araç (aynı liste, bir satır
kaymış -- iki metin ASLA "eşit" olmaz, olması da gerekmiyor; gereken
ÖRTÜŞME/ALT-KÜME tespiti, F2'nin NCC-dikiş mantığına benzer bir şey).

**Sonuç (Task 3'ün kritik sorusu):** toleranslı REC-eşitliği A1/S2'yi
**KISMEN** açıyor (~%9, güvenli) ama kalan-91'in ÇOĞUNLUĞUNU (kare-mesafe
kanıtıyla ~%74-85'i) AÇMIYOR -- çünkü o çoğunluğun kök mekanizması "iki
kartın metni eşit" değil "bir listenin bir kısmı diğerinde de var" (örtüşme),
yapısal olarak FARKLI bir problem.

---

## 5. Projeksiyon tablosu

Hedef: 331 → ≥388/427 (%90.9), yani **+57 film** gerekli (det-fix sonrası
taban 331; görev metnindeki +56 rakamı fix-öncesi 333 tabanına göreydi).

| Sınıf | Film sayısı | Reçete | Tahmini kazanım | Güven/Not |
|---|---|---|---|---|
| **S1 + Karışık** | 0 saf + 5 karışık | K2 (dy-düzeltme + slit kırpma) | **+2-4** | Plan-varsayımının aksine KÜÇÜK lever -- slit artık baskın sorun değil |
| **S2 -- toleranslı-REC alt-kümesi** | ~9-12/73 (simülasyon+eşik-gevşetme projeksiyonu) | Mevcut K1 katı-eşitlik kuralını normalize+Levenshtein-oran≤0.20-0.25+güven-ağırlıklı yap (composer'da tek koşullu değişiklik) | **+6-10** | YÜKSEK güven (0/7 yanlış-birleşme ölçüldü), DÜŞÜK risk, DÜŞÜK-ORTA verim |
| **S2 -- scroll/aşırı-bölünme çoğunluğu** | ~50-62/73 (kare-mesafe kanıtı ~%74-85) | **YENİ, henüz tasarlanmamış**: kart-bölme sınır-hassasiyeti (`card_same_thr`/`min_hold`) gren-dirençli hale getirilmeli VE/VEYA F2'nin NCC-dikiş/örtüşme-kırpma mantığı `static_page` moduna genişletilmeli (yakın-kart örtüşme testi) | **+35-55 (İZDÜŞÜM, DOĞRULANMAMIŞ)** | TEK büyük-yeter lever ama TASARLANMADI/test edilmedi -- risk seviyesi bilinmiyor, kendi M10-tarzı teşhis+konsey turu gerektirir |
| **S3** | 5 | Belirsiz -- test edilen 8 (S3+S3b) adaydan HİÇBİRİ toleranslı kuralla da açılmadı; en az 1'i (`babam-ve-ben`'in top-çifti) muhtemelen MEŞRU-FARKLI (aynı arka-plan-fotoğraf, farklı isim) -- K3 kanıt-şartı SIKI TUTULMALI, gevşetme ÖNERİLMİYOR bu örneklemde | **+0-2** | Küçük N (5), düşük güven; per-çift adli inceleme (yalnız top-1 değil TÜM adaylar) gerekir |
| **S3b** | 3 | Aynı (yukarı) | **+0-1** | Küçük N (3) |
| **S4 (belirsiz)** | 3 | En az 1'i (`kabaran-ofke`) GÖRSEL olarak gerçek özdeş metin -- benim y-aralığı eşleme mantığımın sınır/gap kusuru; muhtemelen gerçekte S2 | **+1-3** | Metrik-katmanı/analiz kusuru, composer'ı ilgilendirmiyor |
| **S4-az-blok** | 1 | `kaptan-january` üretim hatası (status≠OK) -- ayrı kök-sebep (dup ile ilgisiz), bu kampanyanın kapsamı DIŞINDA | **+0-1** | Üretim hatası düzelirse otomatik "dup" listesinden de çıkar |
| **S4-kendine-eslesme** | 6 | `dup_metrik.py`'ye self-match/düz-gradyan güvenlik filtresi (composer'a dokunmadan, ölçüm-katmanı) -- D-class ile aynı reçete | **+3-5** | Orta güven, düşük risk (yalnız metrik) |
| **TOPLAM (scroll-fix HARİÇ)** | | | **~+12-27** (331→343-358, %80.3-%83.8) | Hedefin ÇOK ALTINDA |
| **TOPLAM (scroll-fix DAHİL, izdüşüm)** | | | **~+47-82** (331→378-413, %88.5-%96.7) | Hedefe ULAŞABİLİR ama TEK KANITLANMAMIŞ levere bağımlı |

### En kritik çıkarım

**Kampanyanın orijinal H2 varsayımı (F1/F1b/F1c/K1/K3'ün TÜMÜNÜN üzerine
kurulduğu "ardışık-olmayan/uzak kart tekrarı") kalan-91 popülasyonunda
neredeyse hiç görülmüyor** (80 adayın yalnızca 1'i >50 kare mesafeli).
Baskın mekanizma bunun yerine **YAKIN-mesafeli, muhtemelen scroll'un
statik-kart sanılıp aşırı bölünmesi** (`hizli-silah`, `onemsizlik`,
`belki-bir-gun`, `gecmisten-gelen`, `sihirli-ev` GÖRSEL olarak doğrulandı).
Bu, M4/M8'in tüm det/rec-tabanlı "uzak kart karşılaştırma" apparatının
YANLIŞ SORUNU optimize ettiği anlamına gelebilir -- ≥91% hedefine ulaşmak
için muhtemelen gereken şey composer'ın **kart-bölme/run-sınıflandırma
sınır-hassasiyetini** (H3'ün ruhuna daha yakın, ama F3'ün zaten çözdüğü
"dy-kanıtlı run" sorunundan FARKLI bir granülarite-seviyesi sorunu) ele
almak, REC-eşitliğini daha da genişletmek DEĞİL.

**Bu, CLAUDE.md'nin "sistematik veri anomalisi → doğrudan konsey" tetikleyicisini
karşılıyor:** kampanyanın temel varsayımını sarsan, büyük ölçekli (91 filmin
~%80'i) bir bulgu. Orkestratöre ÖNERİ: bir sonraki fix yönüne karar vermeden
ÖNCE bu bulguyu (özellikle kare-mesafe istatistiği + hizli-silah/onemsizlik
görsel kanıtı) GLM/Kimi kırmızı-takım turuna taşı -- mevcut F1/F1b/F1c/K1/K3
yatırımının bir kısmının yanlış hedefe gitmiş olabileceği ciddi bir olasılık.

---

## 6. Sınırlamalar / dürüst notlar

- Sınıflandırma HER filmin yalnız TOP-skorlu cross-çiftine dayanıyor (witness
  + simülasyon); bazı filmlerde birden fazla mekanizma birlikte olabilir
  (bkz. "karışık" S1+S2 5 filmi). Tam-kapsamlı (TÜM çiftler) analiz bu
  pasoya sığmadı.
- `babam-ve-ben` (S3) örneğinde görsel witness "aynı fotoğraf" gösterdi ama
  simülasyonun kullandığı TOP-çift muhtemelen FARKLI bir bölge/kart-çiftiydi
  (aynı arka-plan-fotoğraf, farklı isim) -- witness_crop ile simülasyon
  ARASINDA %100 hizalama garantisi yok (ikisi de aynı `top_dup_blocks`
  sıralamasını kullanıyor ama farklı amaçlarla farklı elemanlar seçilebilir).
  Per-film TAM hizalı tekil-doğrulama gerekirse ayrı bir mini-tur şart.
- `S4-kendine-eslesme`'nin ne kadarının SAF metrik-YP (D-class gibi) ne
  kadarının GERÇEK composer-içi tekrar (uzun hold'un gereksiz iki-kart
  olması) olduğu netleşmedi -- küçük sınıf (6/91), düşük öncelik.
- Toleranslı-eşitlik simülasyonu yalnız `static_page`×`static_page`
  cross-çiftlerinde koştu (S1/karışık filmlerin slit-tarafı test edilmedi --
  o zaten farklı bir mekanizma/reçete alanı, K2).

## Dosyalar

- `harness/master_dup/saglik.py` -- det-fix (M9)
- `harness/master_dup/kalan91_atlas.py` -- 91-film taze sınıflandırma + witness üretici
- `harness/master_dup/hizli_silah_iz.py` -- iz-dökümü + toleranslı-eşitlik simülasyonu
- `data/master_ex/_kalan91/kalan91_siniflandirma.json` -- tam sınıflandırma çıktısı (91/91)
- `data/master_ex/_kalan91/hizli_silah_iz.json` -- hizli-silah 10-çift tam iz
- `data/master_ex/_kalan91/tolerans_simulasyon.json` -- 80-çift simülasyon çıktısı
- `data/master_ex/_kalan91/*_witness.png` (25) + `_sim/*_tolerant_witness.png` (4) -- tanık kırpımları
