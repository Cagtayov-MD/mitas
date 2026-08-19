# Allstar / LEBRON kulesi — tasarım

**Tarih:** 2026-08-15 · **Tasarım:** Opus · **Talimat:** Çağatay —
*"Lebron'a bir klasör gösteririz, o da içindekileri master PNG yapar. Lebron
için girdi önemli değil. MITAS der ki şu klasör içindekileri bağla, o bağlar."*
· *"Lebron çıktı paylaşacak, kendi içinde okumayı yapacak."*

> **Kulenin tek cümlesi:** *klasör girer, METİN çıkar; master PNG artefakt
> olarak paylaşılır.*
>
> Jeneriğin nerede başladığı Kobe'nin işiydi ve bitti. Lebron'a gelen klasörde
> ne varsa onu bağlar, bağladığını okur, ikisini de kendi `out/`'una koyar.

**Neden cevap metin, PNG değil?** MAP.md: *"LeBron / Nash / Jordan aynı işe üç
ayrı beslemedir: sırasıyla master PNG, ham kare havuzu, doğrudan mp4. 'Master
PNG gerekli mi' sorusu ancak üçü de karşılaştırılabilir **metin** ürettiğinde
adil ölçülebilir."* Lebron master'da durursa üç besleme kıyaslanamaz — kulenin
varlık sebebi ölçülemez hale gelir.

---

## 1. Lebron bugün ne? (koddan doğrulanmış)

Kule iki parçadan kurulur; ikisi de bugün üretimde çalışıyor ama **iki ayrı
yerde** yaşıyor.

### 1.1 Kompozitör — `harness/master_dup/lebron_james.py` (357 satır)

Saf kompozitör: kare listesi girer, tek uzun PNG (`kanvas`) + manifest çıkar.
Disk yazmaz, Database bilmez, film adı bilmez.

Akış: her karede PaddleOCR **det** ile yazı kutuları bulunur → kutu dışı siyaha
boğulur (*AI flashlight*) → ardışık çiftler `phaseCorrelate` ile ölçülür →
çiftler `scroll` / `duraksama` / `kesme` olarak sınıflanır → akıllı bıçak baş/son
footage'ı kırpar → segmentler ayrı kanvaslara derlenir → `vstack`.

**İmza:** `compose_lebron(slug, kare_dizini=None, ims=None) -> (kanvas, manifest)`

Bağımlılığı yalnız `cv2` + `numpy` + `paddleocr`. Taşınması ucuz.

### 1.2 Okuyucu — `scripts/_pipe_hibrit_okuma.py:285` `kol_master`

| Adım | Değer / yer |
|---|---|
| Bantlama | `BANT_H=1100`, `BINDIRME=120` (`_pipe_hibrit_okuma.py:59` — *"pilot_hat.oku_master ile aynı geometri"*) |
| Bant elemesi | yüksekliği < 40 px olan son bant atılır |
| Model | `deepseek-ocr:latest` — bugün **Ollama HTTP** üzerinden (`ollama_oku`) |
| Halüsinasyon kalkanı | `kutu_n` = Paddle det kutu sayısı. **0 kutu + satır üretilmiş = UYDURMA** (`_det_kutu_n`, satır 95) |
| İz | her satırda `kol`, `kaynak`, `sira`, `bant_y0` |
| Gevezelik süzgeci | `_RET_KALIP` + `_model_gevezeligi` (satır 183) |

**Kaynak-etiketi dersi (2026-08-01 konsey turu):** `master_giris` ve
`master_cikis` bantları **ikisi de** `bant_000.png` adını kullanıyordu; yalnız
dosya adı kaydedilince iki ayrı kolun bantları aynı kart sanılıyor, araya
`--- KART ---` konmuyor ve dedup yanlış tetikleniyordu. GLM 56 üretim örneği
tarayıp 8'inde doğruladı. Kulede kaynak izi **bölüm etiketiyle birlikte**
taşınır.

**İkinci, bağımsız okuyucu:** `scripts/master_dilim_oku.py` — `master_dilim/`
parçalarını **OneOCR** ile okur, VL hayalet-kalkanı korpusuna *additive*
beslenir. Bu kule kapsamı dışıdır (farklı tüketici, farklı amaç) — §10.

### 1.3 Üretimdeki çağrı yolu (kompozitör tarafı)

| Adım | Yer | Kule işi mi? |
|---|---|---|
| Havuz seçimi (`cikis_jenerik` / `_dense` / textset) | `master_png_monitor.py:316` `_seg_source` | ❌ MITAS |
| Sıralama `nat_sort_key` (**adın SON sayısına göre**) | `master_png_monitor.py:326,336` | ✅ |
| Yükleme `cv2.imdecode(np.fromfile(...))` + önbellek | `db_compose_master.py:522` `rd_cached` | ✅ |
| Motor çağrısı | `master_png_monitor.py:148` | ✅ |
| **Çöküş dedektörü** | `master_png_monitor.py:132` `_lebron_cokmus` | ✅ |
| Yazma · symlink köprüsü · Database | `master_png_monitor.py:467-498` | ❌ teslim katmanı |

**Çöküş dedektörü kuleye girer, çünkü kulenin KENDİ çıktısı hakkındaki
hükmüdür:** `segment == 1` **ve** kare ≥ 20 **ve** boy ≤ 2 × kare yüksekliği →
motor 20+ kareyi tek ekrana çökertmiş demektir. Üretimde bu çıktı reddedilir
("kötü master yerine hiç"). Dışarıda bırakılırsa her tüketici bu testi kendi
yeniden yazmak zorunda kalır — ve biri unutur.

### 1.4 Taşınırken düzeltilecek iki kusur

**(a) Sıralama — sessiz bozulma riski.** Üretim `nat_sort_key` kullanıyor;
kompozitörün kendi klasör okuyucusu (`lebron_james.py:178`) düz
`sorted(glob("*.png"))` — **sözlük sırası**. Sıfır dolgulu adlarda
(`c_01113.png`, `exit_000566.png`) ikisi aynıdır, bugün bu yüzden patlamıyor.
Dolgusuz ad gelirse (`kare_9.png` > `kare_10.png`) kareler yanlış sırada
bağlanır ve master **sessizce** bozulur. Kule "bana klasör göster" diyecekse
girdinin adlandırmasını seçemez → kapı kapatılmalı.

**(b) Çift okuma.** `lebron_james.py:179` her PNG'yi iki kez `imread` ediyor
(biri koşulda, biri listede). 659 karelik havuzda 1318 disk okuması.

Bunlar dışında motora **tek satır dokunulmaz** — §6'daki kapı bunu kanıtlar.

---

## 2. Kule sınırı

MAP.md'nin ayırt edici sorusu: *"bu şey değişirse kulenin CEVABI değişir mi?"*

**İçeri:** kompozitör · çöküş dedektörü · boy tavanı (`H_MAKS=45000`) · kare
yükleme + sıralama · **okuyucu** (bantlama geometrisi + model + süzgeçler +
halüsinasyon kalkanı) · sözleşme · kendi venv'i.

**Dışarı:** hangi klasörün işleneceği kararı (MITAS) · Database'e teslim ·
symlink köprüleri · PDF · isim/rol düzeltme · Paddle model ağırlıkları
(`~/.paddlex` — MAP.md'nin kasıtlı istisnası).

**Ollama kuraldışı.** Bugünkü okuyucu Ollama HTTP'ye gidiyor; bu kule kuralını
ihlal eder (*"dışarıdaki bir servise bağlı kule kendi kendine yeten bir kule
değildir"*, Çağatay 2026-08-14). Ayrıca ölçülmüş bir yan etkisi var: **Ollama
açıkken Kobe skoru %94.5 → %93.6 düşüyor.** Lebron modelini Nash gibi kendi
içinde taşır (§4.2).

**Bedel — dürüst tahmin:** venv ≈ 11 GB (Paddle yığını, Kobe'ninkiyle aynı) +
DeepSeek-OCR ağırlıkları ≈ 6.3 GB (Nash'te ölçüldü). Toplam ~17 GB. Diskte
369 GB boş. Kule başına ağır ama MAP.md'nin bilinçli olarak kabul ettiği fiyat.

---

## 3. Sözleşme

### 3.1 Çalıştırma

```bash
lebron tek   --kareler /yol/kareler --film-id X --bolum cikis
lebron start --input /yol/kare_dizinleri --bolum cikis   # kaldığı yerden devam
```

Kule kendi çalışma zamanını kendi bulur — çağıran hangi python'la koşulacağını
bilmez (`lebron` betiği `venv/bin/python main.py` çalıştırır). Toplu koşuda
model **BİR KEZ** yüklenir; film başına yeniden yükleme yoktur (Nash deseni).

**`--bolum` bir KARAR DEĞİL, raf etiketidir.** Kompozitör ve okuyucu `giris` ve
`cikis`'te birebir aynıdır; etiket (i) çıktının hangi rafa yazılacağını ve
(ii) satır izindeki kaynak etiketini belirler — §1.2'deki `bant_000.png`
çakışması bu yüzden kapanır.

> Kobe'deki bölüm ayrımıyla karıştırılmamalı: orada iki bölümün **karar
> mantığı** ayrıydı ve ayrı kalmak zorundaydı (`SON_ERISIM` girişte ters
> çalışır). Burada karar yok — bağlama ve okuma var.

**Faz 1'de yalnız kare klasörü.** mp4 verilirse açık `ARIZA(GIRDI_HATASI)` —
sessizce tahmin edilmez. Gerekçe: mp4'ten kare çıkarımı **fps'i ölçüm-kritik
bir parametre** yapar (üretim notu: 1.5 fps'te scroll adımı `dy≈75px` "kesme"
sanılıp master çöküyordu, `master_png_monitor.py:329-332`). Kobe zaten
`--uret kare` ile kare havuzu üretebiliyor; bugün mp4 yoluna ihtiyaç yok.

### 3.2 Çıktı

**Her iki bölüm de master PNG + metin üretir** (Çağatay, 2026-08-15: *"master
png yine üretilecek, o klasörün içine koyulacak — hem giriş hem çıkış için"*):

```
out/<film_id>/
├─ giris/
│  ├─ master.png    # kompozisyon başarılıysa HER ZAMAN yazılır
│  ├─ lebron.txt    # YALNIZ durum=OKUNDU ise
│  ├─ lebron.json   # durum + satirlar + uretilen + kanit
│  └─ _TAMAM        # EN SON yazılır
└─ cikis/
   ├─ master.png
   ├─ lebron.txt
   ├─ lebron.json
   └─ _TAMAM
```

Master PNG **kulenin ürettiği ve paylaştığı artefakttır** — okuma sonucundan
bağımsız yazılır. Okuyucu çökse bile (`durum=ARIZA`) master diskte durur ve
`uretilen` künyesine girer; kompozisyona harcanan iş çöpe gitmez, ayrıca
arızanın hangi tarafta olduğu gözle görülebilir kalır. Kulenin *cevabı* metin
olması bunu değiştirmez: cevap metin, artefakt PNG, ikisi de teslim edilir.

Çağıran çıktı yolunu seçmez — kule kendi evine yazar. `lebron.json` atomik
yazılır (`os.replace`), `_TAMAM` en son. Tüketici kuralı: **`_TAMAM` yoksa
dosya yok sayılır.**

**`lebron.txt` yalnız `OKUNDU`'da yazılır.** Boş bir `lebron.txt`, yalnız metni
okuyan bir tüketiciye "yazı bulunamadı" gibi görünür ve `METIN_YOK` / `ARIZA`
ayrımını yutar. Dosya yoksa tüketici `lebron.json`'a bakmak zorunda kalır.
(Nash'in birebir aynı kuralı.)

### 3.3 Durum — üç değer, ayrım değişmez

| durum | Anlamı | Zorunlu |
|---|---|---|
| `OKUNDU` | master üretildi **ve** metin okundu | `satirlar` (boş olamaz) |
| `METIN_YOK` | okunacak yazı gerçekten yok — **içerik gerçeği** | — |
| `ARIZA` | okuyamadık — **arıza gerçeği** | `sinif` + `mesaj` |

> **`ARIZA` asla `METIN_YOK`'a dönüşmez.** Geniş bir `except` arızayı içerik
> gerçeğine çevirdiği an aşağı akış kirlenir: "bu jenerikte yazı yok" ile
> "PaddleOCR çöktü" aynı kutuya girer ve fark bir daha bulunamaz. Aynası da
> geçerli: içerik gerçeği arıza diye etiketlenmez.

`METIN_YOK` ve `ARIZA` **satır taşıyamaz** — sözleşme kodla zorlar.

**`uretilen` künyesi** (Kobe deseni, HER ZAMAN liste):

```json
"uretilen": [{"tip": "master", "yol": "master.png", "en": 1920, "boy": 18400,
              "segment": 7, "kare": 659, "sinif_sayimi": {...}}]
```

Kompozisyon başarılıysa `master.png` **okuma sonucundan bağımsız** yazılır ve
künyeye girer — okuma çökse bile artefakt paylaşılır, `durum=ARIZA` olur.
Kompozisyon başarısızsa `uretilen` boştur.

### 3.4 Arıza sınıfları — iç gerçeklerin sözleşmeye çevrimi

| Gerçek | durum / sinif |
|---|---|
| dizin yok · desene uyan dosya yok · < 2 kare | `ARIZA(GIRDI_HATASI)` |
| mp4 / desteklenmeyen girdi | `ARIZA(GIRDI_HATASI)` |
| kareler VAR ama hiçbiri açılamadı | `ARIZA(KARE_OKUNAMADI)` |
| kareler açıldı, geçerli segment kalmadı | `METIN_YOK` |
| boy > `H_MAKS` (45000) | `ARIZA(BOY_ASIMI)` |
| çöküş dedektörü tetiklendi (§1.3) | `ARIZA(COKME)` |
| kompozitör istisna attı | `ARIZA(MOTOR)` |
| model yüklenemedi / kurulmadı | `ARIZA(MODEL)` |
| CUDA OOM | `ARIZA(BELLEK)` |
| model konuştu ama çıktı garble | `ARIZA(CIKTI_BOZUK)` |
| master okundu, hiçbir bantta satır çıkmadı | `METIN_YOK` |
| satır üretildi ama `kutu_n == 0` (uydurma) | satırlar **atılır** → `METIN_YOK` |

**Bu tablo bir körlüğü kapatıyor.** Kompozitör bugün üç ayrı gerçeği tek
kelimeye indiriyor: `durum="kare_yok"` hem "klasör bulunamadı" hem "2'den az
kare" hem "geçerli segment kalmadı" için dönüyor
(`lebron_james.py:177,182,310`). Nash'in `METIN_YOK` / `ARIZA(KARE_OKUNAMADI)`
ayrımıyla kapattığı körlüğün aynısı.

**Tek kare kararı:** `< 2` kare → `ARIZA(GIRDI_HATASI)`. Gerekçe: Lebron'un
işi *bağlamak*; tek kare bağlama işi değildir. Sessizce o kareyi "master" diye
geri vermek bozuk bir beslemeyi gizler ve MITAS bunu asla öğrenemez.
*(Gözden geçirilmeye açık — §10 açık borç.)*

---

## 4. Yerleşim

```
Allstar/lebron_james/
├─ lebron                # kendi venv'ini bulan giriş (kobe deseni)
├─ main.py               # CLI + koşu akışı: tek / start · çeviri burada
├─ sozlesme.py           # Girdi / Cikti / ariza
├─ config.yaml           # eşikler — çağıran Girdi.config ile tek tek ezebilir
├─ src/
│  ├─ derleyici.py       # lebron_james.py taşınır — BİRİNCİL kompozitör
│  ├─ ibrahimovic.py     # aday kompozitör — §7
│  ├─ okuyucu.py         # bantlama + süzgeçler + kalkan — MODELİ BİLMEZ
│  └─ model.py           # transformers'a dokunan TEK yer
├─ model/deepseek-ocr/   # ağırlıklar (~6.3 GB) — §4.2
├─ olcum/                # saglik.py · sadakat.py · dup_metrik.py + veri
├─ tests/
├─ out/<film_id>/{giris,cikis}/
├─ scratch/              # kulenin kendi geçici alanı (kendi açtığını siler)
├─ raporlar/
├─ README.md · DURUM.md · CHANGELOG.md
└─ venv/ · gereksinimler.txt · venv_kur.sh · model_kur.sh
```

Klasör adı `lebron_james` — alt çizgi, tire değil (Python paketi olarak import
edilebilmeli; MAP.md klasör adı kuralı).

### 4.1 `okuyucu.py` / `model.py` ayrımı — Nash'ten alınan desen

`okuyucu.py` modeli **bilmez**; `sor(png) -> str` geri-çağrısı alır. Böylece
bantlama, dedup, gevezelik süzgeci ve halüsinasyon kalkanının tamamı
**GPU'suz test edilebilir**. Modele dokunan tek dosya `model.py`.

Jordan dersi (Nash'in docstring'inde kayıtlı): *istemde "no commentary"
yazması YETMEZ — süzgeç kodda olmak zorunda.*

### 4.2 Model ağırlıkları — kopya mı, paylaşım mı

Nash `model/deepseek-ocr`'ı **kendi içinde** taşıyor (6.3 GB). MAP.md ise model
ağırlıklarını *"dışarı (zemin)"* saymış — *"kasten paylaşılırlar; kopyalanırsa
güncellenen bir model kuleye hiç ulaşmaz."* İki emsal çelişiyor.

**KARAR VERİLDİ (Çağatay, 2026-08-15): kopya.** *"İçine deepseek kur, kule
içinde yaşasın."* Ağırlık `model/deepseek-ocr` altında (6.3 GB); `model_kur.sh`
Nash'in yanındaki kopyadan alıyor (aynı ağırlık, 6.3 GB indirme yok) — bu bir
çalışma zamanı bağlantısı DEĞİL, tek seferlik kurulum kopyasıdır. Kopyalandıktan
sonra Lebron Nash'i hiç tanımaz.

---

## 5. Akış — bir filmin kule içindeki yolu

```
klasör (N kare)
   │  nat_sort + imdecode          ← §1.4(a) kusuru kapalı
   ▼
derleyici (Paddle det + phaseCorrelate)
   │  → kanvas + manifest
   │  çöküş dedektörü · boy tavanı  ← ARIZA(COKME) / ARIZA(BOY_ASIMI)
   ▼
master.png  ───────────────────────► out/<film>/<bolum>/master.png  (PAYLAŞILIR)
   │
   │  bantla (1100 px, 120 bindirme, <40 px atılır)
   ▼
okuyucu: bant → model.sor() → satırlar
   │  gevezelik süzgeci · fold-dedup · garble dedektörü
   │  kutu_n == 0 → satırları AT (uydurma kalkanı)
   ▼
lebron.txt + lebron.json + _TAMAM
```

Paddle det iki yerde çalışıyor (flashlight maskesi + `kutu_n` kalkanı). Aynı
kule içinde olduğu için motor **bir kez** yüklenir.

---

## 6. Kompozitör taşıma — sadakat kapısı

Kompozitör **birebir** taşınır. "Taşırken iyileştirme" yapılmaz; §1.4'teki iki
kusur dışında tek satır değişmez.

**Taşımanın doğruluğu iddia edilmez, ÖLÇÜLÜR.** Kapı: aynı kare klasöründe
kule çıktısı ile bugünkü üretim yolunun çıktısı **bit düzeyinde aynı** olmalı.

| | |
|---|---|
| Test yatağı | `/home/cagatay/Ex_Frame` — **440 film** exit_frames dizini (harness'in `EX_KARE_ROOT`'u) |
| Kıyas | kule `master.png` SHA-256 ↔ bugünkü `compose_lebron` + `rd_cached` yolunun PNG SHA-256 |
| Eşik | **sapma 0**. Tek sapma bile kapıyı kapatır; sebebi bulunmadan ilerlenmez |

Nash'in sökme kapısı deseni (29/29 sapma sıfır, 2026-08-14). Kapı geçmeden kule
"kuruldu" sayılmaz.

**`Database/` şu an boş** — üretim 2026-07-31'de Çağatay talimatıyla
durduruldu. Kapı bu yüzden Ex_Frame üzerinden kurulur; `candidate_runs/`
altındaki gerçek havuzlar (`*/frames/cikis_jenerik`) ikinci örnek kaynağıdır.

**§1.4(a) düzeltmesi kapıyı bozmaz:** Ex_Frame adları sıfır dolgulu
(`exit_000566.png`), üretim havuzları da öyle (`c_01113.png`) — iki sıralama bu
adlarda aynı sonucu verir. Kapı tam olarak bunu kanıtlar.

**Okuyucu tarafı için ayrı kapı:** aynı master PNG'de kule okuyucusu ile
bugünkü `kol_master` **aynı satır kümesini** üretmeli. Model Ollama'dan
transformers'a taşındığı için bit-birebirlik beklenemez; ölçüt satır düzeyinde
kıyastır (Nash'in okuyucu geçişinde kullanılan ölçüt). Eşik plan aşamasında,
gerçek sapma dağılımı görülerek konur — **peşinen sayı uydurulmaz.**

---

## 7. İbrahimovic — birincil değil, aday

`harness/master_dup/ibrahimovic.py` (740 satır) kuleye **taşınır**, ama birincil
yapılmaz. Bugünün birincili Çağatay'ın 2026-08-04 kararıyla lebron_james'tir.

Seçim tahminle değil ölçümle yapılır — `model_manifest.yaml`'ın
`no_engine_selection_before_benchmark` kuralı. İki kompozitör kulede yan yana
durur; `olcum/` hangisinin daha iyi master ürettiğini söyler.

> İbrahimovic'in `EX_KARE_ROOT = /home/cagatay/Ex_Frame` gibi **gömülü mutlak
> yolları** var (`ibrahimovic.py:90`). Taşınırken girdiye çevrilir; kule sabit
> bir dış yola bakmaz.

---

## 8. Ölçüm yatağı

| Araç | Ne ölçer |
|---|---|
| `saglik.py` (586 satır) | üretim OK · dup_oran ≤ 0.10 · boy 300–45000 · doku kapsamı ≥ 0.05 |
| `sadakat.py` (465 satır) | **metin-recall:** ham karelerde okunabilen metnin master'da ne kadarı hayatta kaldı |
| `dup_metrik.py` (510 satır) | master'ın kendi içindeki tekrar oranı |

`sadakat.py` özellikle kritik: `dup_metrik` master'ı yalnız kendi içinde
ölçtüğü için *"kayan jenerik statik sayfa olarak derlendi"* tipi mod
hatalarında `dup_oran ≈ 0` çıkıp defekt tamamen gözden kaçıyordu
(`acemiler-cetesi` / `benimle-dans-et` vakaları).

**Kule metin ürettiği için dördüncü bir ölçüt açılır:** Lebron'un metni ile
Nash/Jordan'ın metni kıyaslanabilir hale gelir — MAP.md'nin *"master PNG
gerekli mi"* sorusu ilk kez adil ölçülebilir. Bu kıyas ayrı bir iştir (üç kule
de metin üretir hale geldikten sonra), burada yalnız kapısı açılıyor.

---

## 9. Testler

| Test | Neyi kilitler |
|---|---|
| `test_sozlesme.py` | `ARIZA` sinif/mesajsız olamaz · `METIN_YOK`/`ARIZA` satır taşıyamaz · durum üçlüsü · `lebron.txt` yalnız `OKUNDU`'da |
| `test_main_akis.py` | `tek()` istisna sızdırmaz · `_TAMAM` en son · `start` `_TAMAM` olanı atlar · model bir kez yüklenir |
| `test_siralama.py` | dolgusuz adlarda (`kare_9`, `kare_10`) doğru sıra — §1.4(a) geri gelemesin |
| `test_ariza_sinif.py` | §3.4 tablosunun her satırı: hangi gerçek hangi sınıfa gidiyor |
| `test_cokme.py` | çöküş dedektörü eşikleri (segment=1 · kare≥20 · boy≤2×h) |
| `test_okuyucu.py` | bantlama geometrisi (1100/120, <40 atılır) · gevezelik süzgeci · fold-dedup · **`kutu_n==0` → satır atılır** — hepsi GPU'suz |
| `test_kaynak_izi.py` | `giris`/`cikis` bantları aynı ada çökmüyor (2026-08-01 konsey bulgusu) |
| `test_izolasyon.py` | kule dışarıdaki `master_png_monitor` / `db_compose_master` / `Database` / **Ollama**'ya uzanmıyor |

Son satır kuralı kodda kilitler: kule bir daha dış dosyaya veya servise
bağlanmak isterse önce bu testi silmek zorunda kalsın — yanlışlıkla değil,
bilerek yapsın. (Kobe'nin `test_izolasyon.py`'sinin aynı gerekçesi.)

---

## 10. Fazlar

| Faz | İş | Kapı |
|---|---|---|
| **0** | İskelet: klasör · `sozlesme.py` · `main.py` CLI · `lebron` betiği · testler · venv | sözleşme + akış testleri yeşil |
| **1** | Kompozitör taşınır (`src/derleyici.py`) + §1.4 iki kusur kapatılır | **sadakat kapısı: Ex_Frame'de sapma 0** |
| **2** | Okuyucu taşınır (`okuyucu.py` + `model.py` + ağırlıklar) | **okuyucu kapısı: `kol_master` ile satır kıyası** |
| **3** | İbrahimovic aday olarak taşınır + `olcum/` taşınır | ölçüm araçları kulede koşuyor |
| **4** | Kompozitör seçimi: lebron vs ibrahimovic | `saglik` + `sadakat` ile ölçülmüş karar |
| **5** | Üretim devri — pipeline'ın kuleye bağlanması | **EN SON, ayrı talimatla** |

Faz 5 bilinçli olarak sona konmuştur: *"şu anda kuleleri oluşturuyoruz, kule
görevini iyi yapsın, pipeline en son düzenlenecek"* (Çağatay). Üretim
2026-07-31'den beri duruyor; hiçbir fazda toplu koşu başlatılmaz.

---

## 11. Kapsam dışı ve açık borçlar

**Kule yapmaz:** jeneriğin nerede başladığını bulmak (Kobe) · ham kareleri
okumak (Nash) · mp4'ü doğrudan okumak (Jordan) · hangi klasörün işleneceğine
karar vermek (MITAS) · Database'e teslim · symlink köprüleri · PDF · isim/rol
düzeltme (Ronaldo / Phil Jackson) · `master_dilim_oku.py`'nin OneOCR korpusu
(farklı tüketici, farklı amaç).

**Açık borçlar:**

1. ~~Model ağırlıkları: kopya mı paylaşım mı~~ — **kapandı** (§4.2, Çağatay
   2026-08-15: kopya).
2. **mp4 girdisi** — Faz 1'de kapalı. Açılacaksa fps ölçüm-kritik bir parametre
   olarak ayrıca kalibre edilmeli (§3.1).
3. **Tek kare davranışı** — `ARIZA(GIRDI_HATASI)` seçildi (§3.4). Tek-kart
   jeneriklerde doğru cevap olup olmadığı ölçülmedi.
4. **Giriş bölümünde kompozitör kalitesi** — kule giriş ve çıkışta aynı
   kompozitörü çalıştırır. Üretimin bugünkü giriş yolu farklıdır
   (`compose_reading_runaware`, 3796 satırlık `db_compose_master.py` içinde,
   üstelik `giris_jenerik_manifest.json` okuyan bir "semantik kurtarma"
   adımıyla — kule kuralına aykırı bir dış veri bağımlılığı). Lebron'un giriş
   çıktısı `olcum/` ile ölçülmeden üretime bağlanmaz. Kötü çıkarsa run-aware'in
   sökülüp taşınması **ayrı bir faz** olarak açılır.
5. **Okuyucu kapısının eşiği** (§6) — gerçek sapma dağılımı görülmeden sayı
   konmaz.
6. **Ex_Frame kapsamı** — 440 film var; kapının kaç filmle koşulacağı (hepsi mi,
   örneklem mi) plan aşamasında süre ölçülerek kararlaştırılır.
