# Katman-0 Sadakat Ölçümü — Ham-Kare vs Master Text-Recall

> Kaynak: `harness/master_dup/sadakat.py` — ham kareler (`/home/cagatay/Ex_Frame/<slug>-exit_frames/`)
> ile master PNG (`data/master_ex/<slug>/reading_master.png`) arasında OCR-tabanlı
> metin-recall ölçer. Amaç: `dup_metrik.py` (M1) master-PNG'yi YALNIZ KENDİ İÇİNDE
> ölçüyor — "künye kaynaktaki OKUNABİLİR metni sadık taşıyor mu" sorusunu hiç
> sormuyor. Bu doküman metriği 6-film bilinen-vaka setinde ve 40-film rastgele
> örneklemde doğrular, iki gerçek metodoloji hatasını (uyarlamalı örnekleme,
> bant-örtüşme çifte-sayımı) düzeltir ve metriğin güvenilirliğini değerlendirir.

## 1. Yöntem özeti

- **var olan** = ham kareler örneklenir (linspace; n<=20 ise tümü, n>20 ise
  `hedef_kare_uyarla` ile `sqrt(n)*2` tabanlı, taban 20/tavan 40 arası uyarlamalı
  hedef — bkz. §3), üretimle AYNI OCR motoru (`db_compose_master.py` F1b det +
  F1c rec, `saglik.py` üzerinden SALT-OKUNUR import) ile taranır, kutu metinleri
  kelimelere bölünüp (>=3 karakter, zaten `_f1c_normalize_text` ile küçük-harf +
  noktalama-sadeleştirilmiş) benzersiz kümede toplanır.
- **yakalanan** = master PNG aynı motorla, 45000px'e kadar çıkabilen boy için
  1200px örtüşmeli bantlar halinde (200px örtüşme) taranır.
- `text_recall = |yakalanan ∩ var| / |var|` (var boşsa `durum='kunye_yok'`,
  recall=None — 0 ile karıştırılmaz).
- `okunabilirlik` = master'da bulunan token-okunuşlarının (kutu-güveni,
  çekirdek-bölgeye göre tekilleştirilmiş — bkz. §4) conf>=0.6 oranı.

## 2. 6-film doğrulama tablosu

| Film | recall | okunabilirlik | var / yakalanan | Durum |
|---|---|---|---|---|
| benimle-dans-et | **0.829** | 0.998 | 187 / 171 | Beklenti "DÜŞÜK" idi, YÜKSEK çıktı — **görsel doğrulandı, gerekçeli** |
| olum-emri | **0.189** | 0.982 | 1429 / 989 | Beklenti "DÜŞÜK" — **eşleşti** |
| solaris | **0.333** | 1.0 | 6 / 2 | Beklenti "YÜKSEK" idi, DÜŞÜK çıktı — **OCR-motor sınırlaması, master kaybı DEĞİL** |
| baba-2 | **0.306** | 0.997 | 516 / 234 | Beklenti "makul" — **kısmen eşleşti (gerçek atlas-ghosting kanıtlandı)** |
| hizli-silah | **0.042** | 0.25 | 48 / 12 | Beklenti "makul/yüksek" idi, ÇOK DÜŞÜK çıktı — **OCR-motor sınırlaması, görsel doğrulandı** |
| acemiler-cetesi | **0.857** | 0.992 | 77 / 72 | dup_oran=0 vakası — YÜKSEK çıktı — **görsel doğrulandı, gerekçeli** |

Her birinin gerekçesi (hepsi görsel karşılaştırmayla doğrulandı, tahmin değil):

- **benimle-dans-et / acemiler-cetesi** (ikisi de mod_denetim.py'de `mod_hatasi=True`):
  Master görseli incelendiğinde ikisi de art arda ÇOK ÖRTÜŞEN "statik enstantane"
  zinciri — her yeni blok bir öncekinin çoğu satırını TEKRAR ederek birkaç yeni
  satır ekliyor. Süreç yanlış (gerçekten kayan bir jenerik, hatalı biçimde statik-
  sayfa dizisi olarak derlenmiş) AMA birikimli olarak TÜM isimleri kapsıyor —
  bu yüzden recall YÜKSEK çıkıyor. Bu, **mod_hatasi (süreç bayrağı) ile
  text_recall (içerik-sonucu) arasında birebir denklik OLMADIĞININ** doğrudan
  kanıtı: yanlış yöntem bazen kazara tam kapsama üretiyor. Buna karşılık bu
  redundant-örtüşen yapı, `dup_oran`'ın YAKALAMASI gereken gerçek bir "gereksiz
  şişkinlik" kusurudur (aynı satırlar defalarca tekrarlanıyor) — dup_oran=0
  çıkması dup_metrik'in AYRI, hâlâ açık bir kör noktası (periyodik-doku
  muafiyeti/farklı-kırpım-penceresi nedeniyle tekrar-örtüşmesini kaçırıyor).
  **sadakat metriği içerik-kaybını doğru ölçüyor, ama "şişkinlik" kusurunu
  ölçmek için tasarlanmadı — bu dup_oran'ın hâlâ ayrı bir iş olarak kalan alanı.**
- **olum-emri**: master (600x8900px, 272 ham kare) çok-satırlı, küçük fontlu,
  yoğun bir crawl gösteriyor — mod_denetim.py'de `dy_medyan=232.6px/kare` (aşırı
  hızlı kayma). Uyarlamalı örneklemeden SONRA bile (var_token 1429, §3) recall
  düşük (0.189) — bu, gerçek Nyquist-kaynaklı içerik kaybının (kayma hızı ham-
  kare yakalama hızını aşıyor) yanı sıra muhtemelen bir miktar küçük-font OCR
  zorluğunu da içeriyor (ikisini tam ayrıştırmak bu ölçümün kapsamı dışında).
- **solaris**: Master 600x31px, tek kart, **KİRİL alfabeli** "КОНЕЦ ФИЛЬМА" (Tarkovsky,
  1972). Ham kare ve master GÖRSEL OLARAK PİKSEL-DÜZEYİNDE özdeş (bkz. iki
  görsel karşılaştırması) — üretim burada MÜKEMMEL. Ama PP-OCRv5 (Latin-odaklı)
  Kiril karakterlerini HER seferinde FARKLI gürültülü Latin-benzeri string'e
  okuyor (`kohel`/`kohell`/`koheli`/`koheil` gibi varyantlar, aynı pikselden!).
  **Düşük recall burada OCR motorunun betik-kapsamı sınırlamasıdır, master
  kalite kaybı DEĞİL.** okunabilirlik=1.0 olması da yanıltıcı — motor Kiril'i
  YANLIŞ ama YÜKSEK-güvenle okuyor (kendinden-emin ama hatalı).
- **hizli-silah**: Master 600x915px oyuncu listesi. Görsel incelemede hem ham
  kare hem master GRİ/DÜŞÜK-KONTRAST ama İNSAN GÖZÜYLE tam okunabilir bir liste
  ("Clint Cooper...ANDIE MURPHY" vb. net seçiliyor). PaddleOCR mobile rec bu
  düşük-kontrast/taneli (eski baskı/tarama) görüntü stilinde zayıf kalıyor —
  solaris'e benzer ama FARKLI bir OCR-motor sınırlaması (betik değil, kontrast/doku).
  okunabilirlik=0.25 bu okuma-zorluğunu doğru yansıtıyor (motor kendinden-emin
  DEĞİL burada — solaris'ten farklı, motorun kendi belirsizliği görünür).
- **baba-2**: Master 512x5310px, atlas-onarımlı (`atlas_kabul=4`). Görsel
  incelemede GERÇEK çift-pozlama/hayalet-metin artefaktları var ("AL PACINO",
  "DIANE KEATON", editör listesi isimleri görsel olarak İKİLENMİŞ/üst-üste
  binmiş) — atlas dikişi TAM temiz değil, kısmi başarı. Orta-düşük recall (0.306)
  bunu tutarlı yansıtıyor: dup_oran=0.1073 (sağlık eşiğinin ÜSTÜNDE, saglik.py
  zaten bunu ayrı ihlal olarak işaretliyor) ile BİRLİKTE okunduğunda "atlas-
  onarımı kısmen işe yaramış ama tam değil" hikâyesi iki metrikte de tutarlı.

**Sonuç:** 6 filmin 2'si (olum-emri, baba-2 kısmen) ham beklentiyle uyumlu,
2'si (solaris, hizli-silah) OCR-motor sınırlamasıyla açıklanan sapma, 2'si
(benimle-dans-et, acemiler-cetesi) "mod_hatasi≠içerik-kaybı" gerçek bir kavramsal
ayrımla açıklanan sapma. HİÇBİRİ kodda gizli bir hata değil — hepsi görsel
kanıtla doğrulandı.

## 3. Düzeltme #1 — Uyarlamalı örnekleme (olum-emri kanıtı)

Düz sabit-20 hedefle ilk ölçümde olum-emri `var_token=972` verdi AMA master'ın
(TÜM 272 kareden derlenmiş) `yakalanan_token`'ı **1068** çıktı — referans
master'dan daha zengin olamayacağına göre bu, "var" referansının kendisinin
master'dan DAHA DAR örneklendiğinin doğrudan kanıtıydı (düşük recall'in bir
kısmı ölçüm-tarafı eksik-örnekleme olabilirdi, gerçek içerik kaybı değil).

**Düzeltme:** `hedef_kare_uyarla(n)` — hedefi `n`'in karekökÜyle hafif (alt-
doğrusal) ölçekler, taban 20 / tavan 40 ile sınırlı. Kısa filmlerde (n<=20)
davranış DEĞİŞMEZ. Düzeltme sonrası olum-emri `var_token=1429`'a çıktı (artık
`yakalanan_token=989`'dan büyük — mantıklı), recall 0.206→0.189 (yönü/sonucu
DEĞİŞMEDİ, sadece ölçümün kendi-içi tutarlılığı düzeldi). Diğer 4 filmde
(n<=~70 ham kare) hedef zaten tabanda kaldığı için sonuç birebir aynı kaldı.

## 4. Düzeltme #2 — Bant-örtüşme çifte-sayımı (dış konsey bulgusu)

`codex-review` skill'i bu ortamda **kullanılamadı** (`codex` CLI kurulu değil —
`command not found`). Onun yerine CLAUDE.md'nin "kod incelemesi" maddesi gereği
tam kod (özet değil) `ask_council` (GLM/Qwen/Kimi, mercek-ataması: veri bütünlüğü
/ performans / edge-case) ile bağımsız incelendi. **Qwen ve Kimi bu turda API
erişim hatası verdi** (Qwen: `AccessDenied.Unpurchased`; Kimi: 3 denemede yanıt
yok — altyapı sorunu, `docs/` içindeki konsey anahtar notlarına eklendi).
Yalnız **GLM** yanıt verdi (üç merceği de kendi içinde ele aldı):

- **Kabul edilen gerçek bulgu:** `master_bantlari` 200px örtüşmeli bantlar
  kullanıyor (satır kaybını önlemek için, bkz. modül docstring) ama
  `master_tokenlari` her bandın sonucunu koşulsuz `occ.extend(...)` ile
  ekliyordu — örtüşme bölgesine düşen bir metin satırı HEM önceki HEM sonraki
  bant taramasında algılanıp `occ`'a İKİ KEZ giriyordu. `text_recall` SET
  tabanlı olduğundan etkilenmiyordu, ama `okunabilirlik` (occurrence-ağırlıklı
  tasarlandığı için, bkz. §modül docstring) sistematik çarpılıyordu.
  **Düzeltme:** `bant_cekirdekleri()` — `dup_metrik.py`'nin zaten kullandığı
  "pencere/hücre" ayrımıyla AYNI fikir: geniş örtüşmeli bant algılama/bağlam
  için, dar ÇAKIŞMASIZ "çekirdek" ise sayım için. Her kutu yalnız KENDİ
  bandının çekirdeğine düşerse `occ`'a girer. Fix sonrası 6-film ölçümünde
  `yakalanan_token`/`okunabilirlik` küçük ama gerçek farklarla değişti (ör.
  olum-emri yakalanan_token 1068→989, okunabilirlik 0.9828→0.982); recall
  hiçbirinde değişmedi (beklenen — set-tabanlı, bu bug'dan zaten bağışıktı).
  Regresyon testi eklendi (`test_master_tokenlari_ortusme_bolgesinde_cifte_saymaz`).
- **Reddedilen (yanlış-pozitif) bulgu:** GLM "küçük/büyük harf ve noktalama
  normalize edilmiyor" dedi — bu YANLIŞ, çünkü brifingte `_f1c_rec_boxes`'ın
  iç implementasyonu (kaynak kod) paylaşılmamıştı, yalnız var olduğu
  SÖYLENMİŞTİ. Kaynağı ben zaten okumuştum: `db_compose_master.py`'nin
  `_f1c_normalize_text` fonksiyonu (`_f1c_rec_boxes` içinde HER kutuya
  otomatik uygulanıyor) zaten `s.lower()` + `re.sub(r"[^\w]+", " ", s)`
  yapıyor — normalize ZATEN var, GLM'in göremediği bir bağlamdı.
- **İncelenip ERTELENEN (şu an gerekçesiz değişiklik yapmadım) öneriler:**
  (a) *Paralel OCR (ThreadPoolExecutor)*: `_F1B_DET_ENGINE`/`_F1C_REC_ENGINE`
  tekil (singleton) motor nesneleri — thread-safety doğrulanmadı, yanlış
  varsayımla eklemek sessiz bozulmaya yol açabilir; gerçek ölçülen süre zaten
  bütçenin çok altında (§6), ek karmaşıklık gerekçesiz. (b) *Tavan(40) çok
  uzun masterlarda bant sayısını (teorik 45000px'te ~45 bant) karşılamayabilir*:
  gözlenen evrende (6+40 film) en uzun master 8900px (~9 bant) — tavan bunu
  rahat karşılıyor; 427-film tam taramasında daha uzun bir master çıkarsa
  bu sınır yeniden değerlendirilmeli (dokümante edilen, kod-değişikliği
  YAPILMAYAN bilinen sınır).

## 5. 40-film rastgele örneklem (tohum=42)

`n=40/40` ölçülebilir (hiç `kare_yok`/`master_yok`/`kunye_yok` çıkmadı).

- **Medyan: 0.431 · Ortalama: 0.458 · Min: 0.000 · Maks: 0.945** (stdev=0.244)
- recall<0.7: **32/40** (%80) · recall>=0.7: **8/40** (%20)

### mod_hatasi korelasyonu

| | recall<0.7 | recall>=0.7 | Toplam |
|---|---|---|---|
| mod_hatasi=True | 8 | 2 | 10 |
| mod_hatasi=False | 24 | 6 | 30 |

P(recall<0.7 \| mod_hatasi=True) = 8/10 = **%80**
P(recall<0.7 \| mod_hatasi=False) = 24/30 = **%80**

**Bulgu: BU ÖRNEKLEMDE mod_hatasi ile recall<0.7 arasında HİÇBİR ayırt edici
korelasyon YOK — oranlar birebir aynı.** Bu, başlangıç varsayımımla (mod_hatasi
→ düşük recall) ÇELİŞİYOR ve §2'deki bulguyla tutarlı: mod_hatasi (kompozisyon-
YÖNTEMİ bayrağı) ile text_recall (içerik-SONUCU) FARKLI eksenler ölçüyor.
mod_hatasi bazen içerik kaybı YARATMIYOR (redundant-ama-tam örtüşme, §2), VE
düşük recall'in büyük çoğunluğu (24/32) mod_hatasi'nin hiç yakalamadığı BAŞKA
sebeplerden geliyor (OCR-motor sınırlamaları — §2/§7, atlas-ghosting gibi
farklı defekt sınıfları, veya gerçek kompozisyon kaybı). **Bu, sadakat
metriğinin mod_denetim.py'nin YERİNE değil, ONA EK, gerçekten BAĞIMSIZ bir
sinyal olduğunu doğruluyor** — ikisi aynı şeyi iki kez ölçmüyor.

### En güçlü pozitif-kontrol: demir-maskeli-adam (recall=0.005)

40-örneklemin en uç değeri. `var_token=417, yakalanan_token=4` — 417 farklı
tokendan yalnız ~2'si master'da bulunabildi. Görsel doğrulama: ham kare
(`exit_000561.png`) TAM TEMİZ, kusursuz okunabilir bir ekip listesi gösteriyor
("SPECIAL EFFECTS COORDINATOR: GEORGE GIBBS" vb., her satır net); master ise
BİRDEN FAZLA farklı kartın (ör. "GABRIEL BYRNE" ismi İngilizce film adı "IRON
MASK" ile, "PETER SARSGAARD" başka bir ghost metinle) üst üste bindirilmiş,
GARBLE bir çift/üç-pozlama karmaşası. **Bu, kesin bir kompozisyon felaketi** —
ve mevcut hiçbir sinyal bunu yakalamıyor: `dup_oran=0.0`, `manifest.status=OK`,
`doku_kapsami=0.229` (saglik.py'nin 0.05 eşiğini geçiyor, sağlıklı sayılıyor),
`mod_hatasi=False`. **sadakat metriği bu filmi TEK BAŞINA, kesin biçimde
yakalayan tek sinyal** — görevin motive edici tezinin (dup_oran'ın kaçırdığı
gerçek kayıp) en net kanıtı, orijinal 6-film setinden bile daha çarpıcı.

## 6. Bilinen sınırlamalar

1. **Betik-kapsamı (solaris):** OCR motoru (PP-OCRv5 mobile) Latin/Türkçe
   odaklı — Kiril/Yunan/Arapça gibi scriptlerde düşük recall OCR-motor
   sınırlamasını yansıtır, master defekti değil. 427-film evreninde kaç film
   bu kategoriye girer bilinmiyor (bu görevde araştırılmadı — orantısız
   olurdu); düşük-recall outlier'lar gate'e bağlanmadan önce TEK TEK görsel
   spot-check gerektirir (bu raporun kendisinin yöntemi).
2. **Düşük-kontrast/taneli baskı (hizli-silah):** Motor bazı eski/taneli
   kaynaklarda insan-okunabilir metni bile zayıf okuyor.
3. **Eşik kalibrasyonu belirsiz:** 40-örneklem medyanı (0.431) "recall>=0.7"
   gibi sabit bir kabul eşiğinin ÇOĞU filmi "başarısız" işaretleyeceğini
   gösteriyor — bu ya gerçek yaygın bir kalite sorunu ya da (§6.1/6.2 kanıtıyla
   daha olası) OCR-motor gürültüsünün ölçeği sistematik aşağı çektiği anlamına
   gelir. **Bu raporun kapsamı bir eşik ÖNERMEK değil** — mevcut haliyle metrik
   MUTLAK bir kesim çizgisinden çok, GÖRECELİ bir sıralama/outlier-tarama aracı
   olarak daha güvenilir (en uçtaki demir-maskeli-adam gibi vakalar net; orta-
   bant değerler tek başına yorumlanmamalı).
4. **Tavan(40) çok-uzun masterlarda teorik sınır** (bkz. §4) — gözlenen
   evrende sorun değil, çok daha uzun bir master (~45000px) çıkarsa yeniden
   değerlendirilmeli.
5. **Paralel OCR yok** — gerekli değildi (gerçek süreler bütçenin çok altında),
   ama 427-film tam taramasında (bu görevin kapsamı DIŞINDA) düşünülebilir.

## 7. Maliyet (gerçek ölçüm)

- 6-film doğrulama: **33.2sn toplam** (~5.5sn/film ortalama)
- 40-film örneklem: **128sn toplam** (~3.2sn/film ortalama, motor tek süreçte
  ısındıktan sonra) — en uzun tekil film 11.4sn (affedilmeyen). Hedef
  (<60sn/film) her filmde rahat karşılandı.

## 8. Kendi değerlendirmem

**Metrik güvenilir, ama TEK BAŞINA/mutlak-eşik olarak DEĞİL — bağımsız bir
GÖRECELİ sinyal olarak.** Kanıt:

- **Lehine güçlü kanıt:** demir-maskeli-adam gibi vakalarda (dup_oran=0,
  mod_hatasi=False, status=OK — HERŞEY "sağlıklı" diyor) tek başına gerçek bir
  felaketi yakalıyor. mod_hatasi ile ölçülebilir bağımsızlığı (§5 korelasyon
  tablosu — %80/%80 özdeş oran) onun GERÇEKTEN YENİ bir eksen ölçtüğünü, var
  olan sinyallerin yeniden-paketlenmesi olmadığını kanıtlıyor.
- **Aleyhine/dikkat gerektiren kanıt:** Mutlak ölçeği OCR-motor sınırlamalarıyla
  (betik, kontrast) sistematik olarak aşağı çekiliyor — bu yüzden "recall<0.7 =
  kötü" gibi düz bir okuma YANLIŞ POZİTİF üretir (solaris, hizli-silah böyle
  ölçülür ama görsel olarak İKİSİ DE ya kusursuz ya insan-okunabilir).
- **Önerilen kullanım biçimi:** (a) 427-film tam taramasında en düşük N
  (örn. alt %10) görsel spot-check listesi olarak; (b) zaman-içi karşılaştırma
  (aynı film farklı kompozisyon denemelerinde) için GÖRECELİ iyileşme/kötüleşme
  göstergesi; (c) demir-maskeli-adam tipi UÇ DEĞERLERİ (recall<0.05 gibi) sabit
  bir "kesin-felaket" alt-eşiği olarak — bu bölge OCR-gürültüsüyle
  açıklanamayacak kadar aşırı.

## 9. Dosyalar

- `harness/master_dup/sadakat.py` — ana modül (CLI: `--film`, `--dogrulama`,
  `--ornek N --tohum T`, `--tumu`)
- `harness/master_dup/test_sadakat.py` — 25 birim testi (sahte OCR motoruyla,
  gerçek PaddleOCR'a dokunmadan; band-örtüşme regresyon testi dahil)
- `data/master_dup/sadakat_dogrulama6.json` — 6-film ham sonuç (commit edilmedi,
  `data/` genel kural gereği — bkz. .gitignore dışı ama git add'e dahil değil)
- `data/master_dup/sadakat_ornek40.json` — 40-film ham sonuç (aynı şekilde)
