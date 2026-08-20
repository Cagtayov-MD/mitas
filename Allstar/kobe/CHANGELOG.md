# Kobe — değişiklik günlüğü

## 2026-08-20 — girişte yanlış `KREDI_YOK` yoğun içerik kanıtıyla kurtarıldı

- Genel `STATIC_NBLOB_MIN=3` kalkanı gevşetilmedi; altyazı/tabela
  yanlış-pozitif koruması aynen kaldı.
- İlk sezgisel sınır motoru hiçbir koşuyu kabul etmese bile mevcut
  sağdan-sola bitşi kuralı 30 karede en az 12 gerçek kredi-içerik karesi
  bulursa sonuç `KREDI_YOK` değil `BULUNDU` olur.
- Kanıt açık: `sinir_kaynagi=bitis-kaniti`, `bitis_kaynagi=kural`,
  içerik kare sayısı ve W/K eşikleri JSON'a yazılır; uydurma güven
  üretilmez.
- Gerçek kanıt: Çiçek Taksi b1 `KREDI_YOK → 1..225`, b3
  `KREDI_YOK → 1..229`. B1'de 223. kareden itibaren saf yol görüntüsü;
  jenerik yazısı kesilmiyor.
- Kapılar: Kobe `105 passed`; Sheriff sözleşme/DAG/materialize entegrasyonu
  `26 passed`.

## 2026-08-20 — girişte kare eleme kaldırıldı, ardışık aralık sözleşmesi

- `--bolum giris --uret kare` artık OCR sınıflandırması/dedup havuzu değil,
  `baslangic_kare..bitis_kare` kapalı aralığının tamamını kopyalar.
- `_sinif.json` içinde `mod=ardisik_aralik`, kaynak ve ilk/son kare taşınır.
- Yeniden koşuda eski görüntüler temizlenir; daha kısa yeni sınırın arkasında
  bayat kare kalamaz.
- LeBron ardışık giriş manifestosunda akıllı bıçağı kapatır; Sheriff manifestoyu
  materialized frame girdisine taşır ve birleşik hash ile doğrular.
- Gerçek kanıt: Çiçek Taksi b2 228/228 kare, tam Erol/Gül/Ümit/Tuna kartları,
  `OKUNDU`; Suç Dosyası b6 170/170 kare, eski `ARIZA`dan `OKUNDU`ya geçti.
- Kapılar: Kobe `103 passed`, LeBron `199 passed`, Sheriff `73 passed`.

## 2026-08-17 (9) — GİRİŞ BİTİŞİ REVİZE: şelale (ters-motor → kural → sinir)

36-film GT teşhisi: sinirün bitişi 20 filmde çok erken kesiyordu (aralıklı
jenerikte ilk sessizlikte durma). Çözüm, Çağatay'nın iki fikrinin birleşimi:

- **Ters-motor** (`main.py:_ters_bitis`) — kareler ZAMAN TERSİNE symlink
  görünümde çıkış motoruna verilir; ters-zamanda jenerik pencere sonuna
  yaslanır, motorun başlangıcı gerçek zamanda BİTİŞ olur. Ateşlenmezse
  (16/36) kurala düşer; her türlü hatada None (karar ölmez). Bu bilinçli
  izolasyon istisnasıdır: motor ÇAĞRISI main.py'de (yönlendirici), src/giris
  motor import ETMEZ — test_izolasyon geçer; yeni sözleşme testi
  (`test_giris_motoru_sadece_ters_gorunumde_cagirilir`) ileri-yönlü dizinin
  asla motora gitmediğini kilitler.
- **Sağdan-sola kuralı** (`src/giris/bitis.py`) — pencere sonundan geriye ilk
  kalın blok: W=30 karede ≥K=12 GERÇEK içerik karesi. `havuz.icerik_kareleri`
  recall karelerini (okunamadı→garanti) ayıklar — kanıt taraması GT sonrası
  karelerin çoğunun recall/izci olduğunu gösterdi. Kalibrasyon 18/18
  eğitim-sınav (değerler teyit: 58/60 — ezber yok).
- **Şelale** kanıta yazar: `bitis_kaynagi` (ters-motor|kural|sinir) +
  `bitis_sinir_ham`. `main.giris_karar` TEK NOKTA — üretim ve ölçüm aynı yolu
  koşar (ölçülen=koşulan).

**Sonuç (üretim yolu, 36 film):** ort|Δ| 131.8→**57.0**, medyan ~**19**,
çok-erken 20→**0**, ±60 **29/36**, kaynak ters-motor 17/kural 19. Kalan: 7
izci-film >60 geç (kredi-TARZI ayıracı = gelecek iş, G10 kaydında).
Testler 93/93 (+19). Golden giris: KOBRA bit 41→449/kural.
`config.yaml: giris.bitis_selale` ile kapatılabilir.

## 2026-08-17 (8) — Sheriff için Allstar-only çalışma zamanı

- Giriş sınır motoru `src/giris/jenerik_detector.py` ve iki küçük primitifiyle
  Kobe içine alındı; `src/giris/sinir.py` artık `core/` import etmiyor.
- Rol sözlüğü `src/ortak/rol_tablosu.py` içine alındı; aktif içerik süzgeci
  dış `core/lexicon` bağımlılığı taşımıyor.
- `--out` ile Sheriff'in run/attempt'e özel çıktı kökü kullanılabiliyor.
- Sheriff ortamında sonuç `mitas.boundary/v1` ve run/task/attempt kimliği taşıyor.
- Aktif Allstar kodunda eski `scripts/core/mitas_pipeline` import'u olmadığını
  doğrulayan AST izolasyon kapısı Sheriff testlerine eklendi.

## 2026-08-17 (7) — giriş ölçümü 36 filme çıktı

Çağatay GT'yi 36'ya tamamladı (28 yeni + önceki 8; karar alanları değerlerden
türetilip kayda geçti, biçim onarımları 72 alan). Sonuç:
**jenerik-var 36/36 bulundu** — giriş jeneriği olan hiçbir film kaçmıyor.
Başlangıçta geç hata 0 (politika tamam). Bitiş: 20/36 çok erken, 10 hafif
erken, 4 hafif geç, 2 geç (en kötüler −430..−327; geç uçlar +301, +122).
Kredisiz-red 0/0 — GT'de jenerik_yok örneği yok, red yolu ölçülemiyor (açık
delik, EKSIKLER G5). Kayıt: `veri/olcum_giris_son.json`.

## 2026-08-17 (6) — ilk giriş ölçümü, başlangıç politikası, yatak 50 film

- **İlk GT'li ölçüm** (8 film): jenerik-var 8/8 bulundu; bitiş 8/8 erken
  (−2..−327) — kayıt `olcum_giris_son.json`. GT biçim onarımları şeffaf
  kayıtlı (dosya-adı→int, karar türetme).
- **Başlangıç politikası** (Çağatay: "3 kareyse 1 olur, 6 olmaz; geriye dönük
  kabul — hatta hep 1'den başla, çalışma yapma"): sinir karar başlangıcı daima
  1; motorun ham start'ı `kanit.tespit_bas_kare`'de. olc_giris yalnız
  `gec_baslangıç`ı hata sayar. Golden giris demiri güncellendi.
- **Bitiş kalibrasyonu** (`bitis_kalibrasyonu.md`): 7 havuz-tabanlı tahminci
  GT'ye karşı denendi — kazanamadı (965 vs en iyi 833, gürültü); overfit
  riskiyle uygulanmadı. G10: GT ≥20 film olunca yeniden.
- **Yatak 10→50 film**: test_film_vl'deki `giris_240.mp4` kesitleri ikinci
  kaynak oldu (giriş için tam pencere); teklifler üretildi, gt.json'a boş
  girişler eklendi — Çağatay doldurdukça kapsam büyür.

## 2026-08-17 (5) — G7 + E4 + E6(yarısı): kanarya, görünüm, işçi tazeleme

- **G7** — `golden/giris_tek_film.json`: KOBRA giriş kararı demirlendi
  (BULUNDU, 0-41 kare / 21.0 sn, güven 0.754). 2026-08-13 gerçek-koşu kaydıyla
  birebir uyumlu çıktı — önceki şüphelenilen "1 kare sapma" yoktu (saniye/kare
  gösterim farkıydı). KARAR demiridir, doğruluk demiri değil — BENIOKU'da
  ayrımı açık yazılı.
- **E4** — spec §4.6 Database görünümü: `Database/<Film>/kobe_<bolum>.json`
  HARDLINK (aynı inode — 3 test: samefile, Database-dışı sessizlik, idempotent
  tazeleme). İsim bölümlü; spec'in düz `kobe.json` adı bölümler öncesinden
  kalmaydı, çakışırdı. Best-effort: link başarısızlığı kararı etkilemez.
- **E6** — `olc_pool.py` `maxtasksperchild=25`; kapı yeniden koşuldu:
  **%94.5 / %97.3 / 29-29 — sapma sıfır.** `main.toplu()` paralelliği AÇIK
  kaldı (işçi başına VRAM payı ölçülmeden eklenmez; üretim toplu'yu kullanmıyor).
- **Bilinçli erteleme:** G8 (GT'siz ölçülemez), E5 (ollama servis durumu),
  E7 (saatler süren optimizasyon).

## 2026-08-17 (4) — G6: giriş ölçüm yatağı altyapısı (GT hâlâ insanda)

Girişin doğruluğu için gereken üç parçadan ikisi kuruldu; üçüncüsü (GT)
bilinçli olarak insana bırakıldı — motor kendi ölçütünü üretirse ölçüm
döngüsel olur.

- `olcum/giris/yatak_kur.sh` — `filmtest/depo_3006/` TAM filmlerinden ilk
  240 sn × fps 2 çıkarır (tarif `main.py:kare_cikar(giris)` ile birebir).
  10 film kuruldu (tarif 15 diyordu; depoda 10 TAM film var — fark kayıtlı,
  script idempotent).
- `olcum/giris/gt_topla.py` — her film için `sinir.bul()` teklifi + önerilen
  sınırın ±10 karesinde bakılacak dosya listesi → `veri/gt_taslak.json`.
  `gercek_*` alanları BOŞ kalır. İlk koşu: 10/10 film teklif aldı, hepsi
  `sinir_kaynagi=tespit`, güven 0.68-0.96, 95 sn.
- `olcum/giris/olc_giris.py` — `veri/gt.json` yoksa koşmaz (açık red).
  Metrik şekli çıkıştan farklı: İKİ uçlu sapma (başlangıç+bitiş, ayrı ayrı)
  + kredisiz-red doğruluğu. Çıkışın asimetrik toleransı kopyalanmadı —
  girişte her iki yön farklı zarar verir; kırmızı çizgi GT dağılımı
  görülünce Çağatay ile konur. Script raporlar, hüküm vermez.

## 2026-08-17 (3) — E2: `src/cikis/` + `src/ortak/` — kapı sapma sıfır

DURUM.md Karar 2'de kurulan ama uygulanmayan yapı gerçekleşti: karar motoru
`src/cikis/motor.py`'ye, aletler (`kutu.py`, `icerik.py`) `src/ortak/`'ta,
giriş bloğu `src/giris/`'te. Simetri tamam: her bölümün kendi klasörü var,
ortak yalnız aletler.

**Donmuş dosyaya sıfır diff.** `motor.py`'nin `kutu`/`icerik` importları
fonksiyon içinde (satır 249, 730-731); `src/cikis` + `src/ortak` sys.path'e
konunca düz `import kutu`/`import icerik` yeni yerden çözülür — dosyanın
kendisi `git mv` dışında değişmedi (EKSİKLER E2 metni import satırlarına
dokunulabileceğini söylüyordu; gerekmedi, dokunulmadı).

Yol ayarı değişenler: `main.py` (cikis+ortak+src), `src/giris/havuz.py`
(ortak), `olcum/olc_pool.py` + `olcum/hata_atlasi.py` (cikis+ortak — spawn
işçilerinde de çözülür), `tests/test_motor_yonlendirici.py`. `test_izolasyon.py`
yeni yollara bağlandı; `test_yapi_kilitli` bekçisi eklendi (motor tekrar src/
düzlemine dönerse kırmızı).

**Kapı:** `olc_pool.py --paralel 8` → kapsam 110, **104/110 = %94.5**,
**107/110 = %97.3**, kredi-yok **29/29**, eksik 5; hata listesi bilinen
6 filmle birebir. Kayıt: `raporlar/olcum_E2.json`. Kanarya: BULUNDU 1133.
Testler 71/71.

## 2026-08-17 (2) — E1: üretim kuleyi sözleşmeden çağırıyor

Kulenin değeri sözleşmedeydi; üretim ona `import motor` ile kütüphane gibi
dokunuyordu — `kobe.json`, `_TAMAM`, `out/` kuyruğu, sürüm dondurma hiçbiri
devrede değildi. Bu kayıt o boşluğu kapattı (EKSIKLER E1, en önemli madde).

**`scripts/_jenerik_pool.py`** — `_v5_detect` artık `_kobe_karari_al()`
çağırır: `kobe tek --kareler <dizin> --film-id <id>` ALT-SÜREÇ (kobe bash
girişi kendi venv'ini bulur) → karar `out/<id>/cikis/kobe.json`'dan okunur.
ARIZA/okunamayan JSON → RuntimeError → create_pool'un mevcut CV fail-safe'i.
`import motor`, `sys.path.insert(kobe/src)` ve `_co._kare_no` bağımlılığı
kalktı; kare-no eşlemesi yerel `_kare_no` aynasıyla (motor.py:74) yapıldı.
`_V5Karar` — JSON'dan kurulan Sonuc aynası; aşağı akış (manifest `v5`
alt-nesnesi) attribute erişim sözünü korur.

**`main.py`** — `_cikis_sonucu` kanıt telemetrisi genişledi: `tip`,
`scroll_orani`, `ardisik_scroll`, `son_capa`, `aday_sayisi`, `notlar`,
`suphe`, `suphe_geri_kare` (KREDI_YOK'ta da; Sonuc default'larıyla). Karar
alanları (durum/baslangic_*/guven/script) DEĞİŞMEDİ — golden kanarya aynı.

**Doğrulama:** 3 gerçek film (POTEMKİN BULUNDU; NAPOLYON_1, YÜZYILIN_CİNAYETİ
KREDI_YOK→CV), eski/yeni manifest BİREBİR AYNI (engine/status/start_pos/v5
alt-nesnesi). Kanarya: BULUNDU, kare 1133, en. Testler 70/70 (+1: kanıt
telemetrisi Sonuc'u birebir taşır — `ardisic/ardisik` typo'su A/B'de
yakalanınca sınıfı kapatmak için).

**E10 bulundu (önceden var, dokunulmadı):** metin-kapının `import credit_box`'ı
pool bağlamında ModuleNotFoundError veriyor → yakalanıyor → tarama hep
atlanıyor; `MITAS_JENERIK_METIN_KAPI=1` fiilen etkisiz. Davranış değişimi
gerektirdiğinden (kredi_yok→review kuyruğu) Çağatay onayı bekliyor.

## 2026-08-17 (1) — belge senkronu: giriş bloğu belgelere işlendi

Kod değişikliği YOK. `41bc799f`'te giriş bloğu uygulandığında belgelerin
bir kısmı güncellenmedi — kule "giriş yapıyor" iken üç belge "yapmıyor"
diyordu. Bu kayıt o uçları kapattı:

- `README.md` — ağaç şemasındaki `giris/ ← HENÜZ YOK, ARIZA(BOLUM_HAZIR_DEGIL)`
  satırı ve "giriş jeneriği henüz desteklenmiyor" paragrafı gerçekle
  değiştirildi (giriş çalışır; ölçülmemişliği açıkça yazılı). Sorumluluk
  sınırı ve Yerleşim tablosu giriş bloğunu görecek şekilde düzeltildi.
- `KATALOG.md` §1 "Ne YAPMAZ" — "giriş jeneriği tespit etmez" maddesi
  kaldırıldı (§7'nin "yetkisi VAR" hükmüyle çelişiyordu).
- `EKSIKLER.md` — test sayısı 61 → 69 olarak düzeltildi.

Ders (3. soru): davranış değiştiren commit, belgeleri de aynı commit'te
taşımış olmalıydı; "kod yazar, belge sonra" uçları açık bırakıyor.

## 2026-08-13 (4) — giriş bloğu uygulandı, uçtan uca çalışıyor

Kapsam Çağatay tarafından daraltıldı ("çalışsın, mükemmel olmasına gerek
yok") — GT/ölçüm yatağı (G5-G7) sonraki faz, bu turda hedef yalnız işlevsel
uçtan uca akış. `src/motor.py`'ye dokunulmadı.

**Sözleşme:** `Cikti`'ya `bitis_kare`/`bitis_sn` eklendi (yalnız giriş
doldurur, çıkış `None` bırakır — giriş iki sınır taşır, çıkış tek). `uretilen`
artık HER ZAMAN liste (tek artefaktta bile tek elemanlı) — `--uret kare,klip`
gibi çoklu istek aynı bölüm klasörüne ikisini de yazabilsin diye.

**`src/giris/sinir.py`** — (a) SINIR. Mevcut `core/pipelines/ocr/
jenerik_detector.detect_from_frames` ÇAĞRILIR (kopyalanmadı). Güven kapısı:
güven ≥ 0.60 → tespit edilen sınır; altındaysa sabit pencereye (0-240 sn)
düşer ve bunu `kanit.sinir_kaynagi` ile açıkça işaretler (`"tespit"|"sabit"`)
— sessiz tahmin yok. Motor çökerse `ARIZA(GIRIS_SINIR)`.

**`src/giris/havuz.py`** — (b) HAVUZ. `scripts/giris_jenerik_havuzu.py`'nin
stratejisi (dosya kopyalanmadı), aletler Kobe'nin kendisi (`kutu.py` +
`icerik.py`): kutu yoksa footage/elenir, altyazı-bandı elenir, kredi-benzeri
≥1 satır varsa alınır, OCR patlarsa/boş dönerse RECALL ile koşulsuz alınır
("okunamadı > yanlış oku"), aynı metin-imzalı kareler teke iner. Havuz,
sınırın dar aralığıyla KISITLANMAZ — tüm giriş penceresini tarar (aynen
`giris_jenerik_havuzu.py` gibi), çünkü gerçek koşuda geç köşe-kredileri
sınırın dışında kaldı (aşağıya bkz).

**`main.py`** — `bolum=="giris"` artık gerçek karar üretiyor (eski açık
`ARIZA(BOLUM_HAZIR_DEGIL)` kaldırıldı). `kare_cikar()` bölüme duyarlı: giriş
`ss=0, uzunluk=240` (600 DEĞİL — kapanış simetrisinden uydurulmuştu).
`--bolum` ve `--uret` virgüllü çok-seçimli oldu (`choices=` yerine kendi
ayrıştırıcı, geçersiz değerde net hata); varsayılanlar değişmedi
(`cikis`, `yok`). Giriş klibi çıkıştan farklı: `baslangic_sn-10 → bitis_sn`
(filmin sonuna GİTMEZ).

**Gerçek koşu** (`filmtest/depo_3006/`, 2 farklı film):

```
KOBRA --bolum giris --uret klip
  → BULUNDU, güven 0.754, sınır 0.0-21.0 sn, kanit.sinir_kaynagi=tespit
  → klip.mp4: ffprobe 21.000000 sn, h264, ses akışı yok, 10.9 sn'de bitti

SİLAHLAR_KONUŞUYOR --bolum giris --uret kare
  → BULUNDU, güven 0.761, sınır 0.0-17.5 sn
  → havuz: taranan=480, elenen_footage=231, dedup_temsilci=75 (75 PNG diskte,
    kare 11'den 476'ya yayılı — havuzun sınırla kısıtlanmama kararı burada
    kanıtlandı: sınır 0-34'te bitiyor ama gerçek kredi kareleri çok ötede)
  → 51.5 sn'de bitti
```

Testler 62/62 (3 eski "giriş hep ARIZA" testi silindi — artık doğru değil,
4 yeni test geldi: sinir.bul çağrılır/çağrılmaz, bitis_* dolar, bulunamazsa
KREDI_YOK, çökerse ARIZA). Havuz/sınır iç mantığı için ağır mock'lu test
yazılmadı — gerçek koşu asıl doğrulama.

**SON KAPI DEĞİŞTİ:** `olc_pool.py --paralel 8` (110 filmlik ölçüm) bu turda
ÇALIŞTIRILMADI — kapsam dışı bırakıldı (kalite fazı, sonraki iş). Kapı
yalnız: `pytest tests/ -q` yeşil + `git diff --stat src/motor.py` boş.

## 2026-08-13 (3) — bölüm ayrımı + KATALOG

`KATALOG.md` yazıldı: kulenin kimlik kartı — neden var, nasıl hizmet verir,
nasıl çalışır (akış taslağı), girdi/çıktı sözleşmeleri, iç yapı, doğrulama ve
bilinen sınırlar.

**Çıktı `out/<film_id>/<bolum>/` oldu.** `--bolum cikis|giris` (varsayılan
`cikis`). İki jenerik ayrı klasörlere yazılır, birbirini ezmez. Sözleşmeye
`bolum` alanı eklendi; `toplu` modda `_TAMAM` denetimi bölüm bazında yapılır.

**Giriş jeneriği: açık ARIZA, sessiz tahmin YOK.** `--bolum giris` verilirse
motor **hiç çağrılmadan** `ARIZA(BOLUM_HAZIR_DEGIL)` döner ve diske yazılır.
Gerekçe: motorun temel ayracı `SON_ERISIM=0.82` (*"aday pencerenin son %18'ine
ulaşmalı"*) girişte ters çalışır — giriş jeneriğinden sonra film HER ZAMAN
devam eder. Motoru giriş karelerine doğrultmak neredeyse her filme `KREDI_YOK`
dedirtirdi: emin, sessiz ve sistematik olarak yanlış. Ayrıca giriş için ne
ölçüm yatağı (`havuz_kur.sh TAIL_S=600` → yalnız son 10 dk) ne de doğrulanmış
GT var. Yol haritası `KATALOG.md` §7: önce GT, sonra pencere çıkarımı, sonra
karar mantığı.

Testler 61/61 (yeni: 10 bölüm testi).

## 2026-08-13 (2) — talebe göre artefakt üretimi

`--uret kare|klip` eklendi. Kobe artık kararının yanında, istenirse iki
artefakttan birini kendi klasörüne koyar: **kare havuzu** (`out/<id>/kareler/`)
veya **sessiz mp4 klip** (`out/<id>/klip/klip.mp4`). İkisi de onset'ten
**10 sn önce** başlar (`config.yaml: geri_pay_sn`) ve filmin sonuna kadar
sürer. Varsayılan `yok` — talep edilmedikçe üretilmez.

Değişmezler: artefakt `kobe.json`'dan ÖNCE üretilir, `_TAMAM` en SON yazılır
(tüketici `_TAMAM` görünce her şey hazırdır). `KREDI_YOK`/`ARIZA` artefakt
taşıyamaz — sözleşme bunu `ValueError` ile zorlar. Kare havuzu kaynaktan
**kopyalanır**, taşınmaz. `--uret klip` + `--kareler` → `ARIZA(GIRDI_HATASI)`,
sessizce atlanmaz.

Gerçek koşu doğrulaması: GÜL VE ÇAKAL (5421 sn) → onset 5345.5 sn, klip
5335.5'ten başladı, **85.94 sn**, ses akışı **0**, geçici dosya kalmadı.

**Yakalanan hata — birim testin göremediği:** ffmpeg geçici dosya `.mp4.tmp`
ile bittiği için formatı uzantıdan çıkaramıyordu ("Unable to choose an output
format"). Birim testler `klip_kes`'in tamamını sahtelediği için bunu kaçırdı;
yalnız gerçek videoda görüldü. Kule doğru davrandı — sessizce başarısız olmak
yerine `ARIZA(URETIM_KLIP)` döndü. `-f mp4` eklendi + komutun kendisini
denetleyen regresyon testi yazıldı. Testler 51/51.

## 2026-08-13 — kule kuruldu

**Taşıma.** `harness/kunye_kiyas/` içinden `Allstar/kobe/`'ye taşındı;
`figo` adı repo genelinden silindi (tek isim: Kobe). `kobe.py → src/motor.py`,
`credit_box.py → src/kutu.py`, `credit_content.py → src/icerik.py`,
ölçüm yatağı `olcum/`'a, testler `tests/`'e. Çağıran `scripts/_jenerik_pool.py`
yeni yola çevrildi.

**Kendi çalışma zamanı.** `venv/` — paddlepaddle-gpu 3.3.1 (CUDA 12.6) +
paddleocr 3.7.0, 167 pin. `venv_kur.sh` sıfırdan kurar. Gerekçe paralellik
değil **sürüm dondurma**: ortak venv'de biri paddleocr'ı yükseltirse Kobe'nin
skoru sessizce kayar ve ölçüm kapısı anlamsızlaşır.

**Sözleşme.** `sozlesme.py` — `Girdi` (film_id + video XOR kareler), `Cikti`
(`BULUNDU`/`KREDI_YOK`/`ARIZA`), `ariza()`. Atomik yazım (`os.replace`) +
`_TAMAM` işareti. Değişmez: `ARIZA` kanıtsız olamaz, `KREDI_YOK` arıza alanı
taşıyamaz.

**CLI.** `main.py` + `kobe` sarmalayıcı + `config.yaml`. `kobe start --input`
idempotent toplu kuyruk (`_TAMAM` olanı atlar, kaldığı yerden devam eder);
`kobe tek` tek film. Video verilirse kapanış penceresini kendi çıkarır
(`havuz_kur.sh` tarifi birebir: son 600 sn, fps 2) ve **kendi açtığı**
`scratch/` dizinini siler — dışarıdan verilen kare dizinine dokunmaz.

**Üç ölçüm kapısı da geçti, sapma sıfır.** kapsam 110, genel 104/110 = %94.5,
üretim 107/110 = %97.3, kredi-var 75/81, kredi-yok 29/29. Kayıtlar:
`raporlar/olcum_{ONCE,SONRA_tasima,SONRA}.json`. Testler 39/39. Uçtan uca
gerçek koşu: POTEMKİN ZIRHLISI → `BULUNDU`, kare 1133, 21.4 sn
(`golden/tek_film.json`).

**Ölçüm havuzu içeri alındı.** `data/jenerik_havuz/pool_frames/` (120 film,
28 GB, +118 `_det_cache.json`) → `Allstar/kobe/havuz/`. Bu dizini kule dışında
kullanan yoktu; yolu yalnız Kobe'nin kendi dosyaları biliyordu. Aynı diskte
olduğu için taşıma anlık (kopyalama yok). Taşıma sonrası ölçüm birebir aynı:
%94.5 / %97.3 / 29-29. `data/jenerik_havuz/` dizini tamamen kalktı.

### Pahalı ders — çalışma zamanı budanmaz

İlk denemede `venvs/ocr`'dan **elle seçilmiş 16 paketlik** bir pin listesi
kullanıldı. Ölçüm **%94.5 → %92.7** düştü: iki film doğru → `KREDI_YOK` oldu
(`MELEKLERİ`/Kiril, `ARKADAŞIMIN`/Farsça), bir film 2 kare kaydı.

Bu olurken altı kilit paket **ikisinde de birebir aynıydı**: paddle 3.3.1
(CUDA 12.6, cuDNN 9.5.1, aynı commit), paddleocr 3.7.0, paddlex 3.7.2,
numpy 2.3.5, pillow 12.1.0, opencv 5.0.0.93. Det önbelleği, model ağırlıkları
ve ölçümün tekrarlanabilirliği de tek tek elendi.

Eksik 76 paket kurulunca skor **tam olarak** geri geldi.

> **Kobe'nin çıktısı, kodunun HİÇ import etmediği paketlere bağlı.**
> `motor.py`/`kutu.py`/`icerik.py` hiçbiri torch, sklearn, easyocr, timm veya
> transformers'a dokunmuyor. "Hangi paket önemli" TAHMİN EDİLMEZ — ortam bütün
> olarak dondurulur. Paket çıkarmadan önce 110 filmlik ölçümü koş.

### Bilinen borç

`src/kutu.py` ve `src/icerik.py`, `harness/kunye_kiyas/` altındaki asıllarının
**kopyasıdır**. Aslını üretim okuyucusu `scripts/_pipe_hibrit_okuma.py:111`
kullanıyor; taşınsaydı okuyucu kırılırdı, yeni yolu gösterseydi bu kez okuyucu
Kobe'nin klasörüne bağımlı olurdu. Okuma kulesi kurulunca o kule kendi
kopyasını alacak ve `harness/kunye_kiyas/` tamamen silinecek.

### Ertelenen

CPU/GPU kaynak bölüşümü ölçümü (spec §4.7): Kobe'yi CPU'da geniş paralel,
okuma kulesini GPU'da koşturma hedefi. Kobe'nin Paddle yükü ağırlıkla
detection-only olduğu için CPU'ya uygun görünüyor, ama kayan-nokta farkı det
kutusunu oynatabilir — 110 filmlik yatakta ölçülmeden kabul edilmez.
