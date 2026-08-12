# Allstar Kule Mimarisi — Kobe Kulesi (Tasarım)

| | |
|---|---|
| Tarih | 2026-08-12 |
| Durum | **ONAYLANDI** — Çağatay, 2026-08-12 |
| Kapsam | `Allstar/` kabı + **Kobe** kulesi. Diğer kuleler bu belgenin dışında. |
| Sonraki kule | Çağatay söyleyecek. Adım adım ilerlenir. |

---

## 1. Amaç

**Bugün:** bir film tek bir pipeline içinde baştan sona akıyor. Jenerik tespiti,
master PNG üretimi, okuma, QC ve PDF aynı koşunun içinde zincirlenmiş durumda.
Bir aşama tıkanınca film duruyor; üretim motorları `harness/` altında dağınık ve
o dizin `sys.path`'e ekleniyor.

**Hedef:** her iş bir **kule**. Kule kendi girdisini alır, kendi çıktısını kendi
klasörüne yazar, gerisine karışmaz. Kuleler birbirini beklemez — Kobe kendi
hızında binlerce filmin jenerik başlangıcını bulup klasörüne bırakır, LeBron
oradan hazır olanı alıp kendi işini yapar. Böylece iş kule kule dağıtılabilir,
CPU/GPU boş kalmaz, 7/24 akış mümkün olur.

**Yan kazanç — teşhis:** arıza "sorun Kobe'de" / "sorun Nash'te" diye tek
cümleyle yerini bulur. Düzeltme ayrı iş.

---

## 2. Kilitli kararlar

| # | Karar | Gerekçe |
|---|---|---|
| 1 | **Klasör + sözleşme**, tek süreç. Ağ yok, docker yok, HTTP yok. | Kule izolasyonunun tamamı klasör + sözleşmeden gelir; ağ katmanı tek makinede saf maliyettir. Her kule yine de CLI'dan tek başına koşabilir. |
| 2 | Kap adı **`Allstar/`** | Çağatay, 2026-08-12. |
| 3 | Okuma motoru **kendi kulesi** olacak (adı henüz konmadı) | LeBron/Nash/Jordan aynı okuyucuya besler; okuyucu fix'i tek yerde yapılır, üç besleme stratejisi adil kıyaslanır. |
| 4 | **Üretici sahipli veri.** Her kule ürettiğini kendi `out/`'una yazar. | Her dizinin tek yazarı olur; "bunu kim ezdi" sınıfı kazalar biter. |
| 5 | `Database/<Film>/` altına **hardlink** (symlink DEĞİL) | Hardlink gerçek bayttır: `cp`/`rsync`/`zip` doğru kopyalar, üretici klasörü silinse bile teslim dosyası yaşar. Kırık kısayol bu repoda zaten sessiz arıza üretti (`models/lid/…` → `C:/Users/TRT03/…`, Mayıs'tan beri ölü). |
| 6 | Göç: **kule kule tam taşıma** | Ara katman yok, temiz sonuç. Karşılığında import kırma riski doğrudan alınır → her taşımada *önce ölçüm / sonra ölçüm* zorunlu. |
| 7 | **Tasarım Opus'ta, işlemler Sonnet'te** | Spec ve plan mekanik yürütülebilir granülerlikte yazılır: dosya listesi, komut, geçme eşiği, geri-dönüş noktası. "Duruma göre karar ver" adımı sıfır. |
| 8 | **FIGO adı silinir.** Tek isim: **Kobe**. | Çağatay, 2026-08-12. `docs/FIGO.md` → `Allstar/kobe/README.md`. |
| 9 | Kobe **iki girdiyi de** kabul eder: video **veya** hazır kare dizini. **Standart yol: video.** | Video verilirse Kobe kapanış penceresini kendi çıkarır, kararı verir, kareleri siler — kareyi tüketen değil **eleyen** kule. Hazır kare dizini verilirse Kobe ona **dokunmaz**: kendi yaratmadığını silmez (tek-yazar ilkesi). |
| 10 | Dış konsey bu iş için **kapalı** | Çağatay, 2026-08-12. Hakemlik Claude'da. |
| 11 | Kobe'nin **kendi Paddle'ı** olur: `Allstar/kobe/.venv` | Çağatay, 2026-08-12. Gerekçe paralellik DEĞİL (o süreçten gelir, §4.7) — **sürüm dondurma**. Kobe'nin %94.5'i paddleocr 3.7.0'a bağlı; ortak venv'de başkası yükseltirse skor sessizce kayar ve ölçüm kapısı anlamsızlaşır. MITAS zaten bu desende (`venvs/` altında 20 venv); sınır *iş*'ten *kule*'ye kayıyor. |
| 12 | **Kule sınırı = kod + üretilen veri + sözleşme + çalışma zamanı.** Zemin (Python/CUDA/Paddle ikilileri, model ağırlıkları, `core/lexicon/` gibi paylaşılan salt-okunur sözlükler) sınırın dışındadır. | Zemini her kuleye kopyalamak sözlüğü çatallar: okuyucu için eklenen bir rol Kobe'ye ulaşmaz. Yasak olan şey **başka bir kulenin ÜRETTİĞİ veriyi doğrudan okumak**; statik ortak kaynak kullanmak değil. |

---

## 3. Allstar yerleşimi

```
Allstar/
├─ MAP.md                     # kod adı ↔ gerçek görev sözlüğü (kule eklendikçe büyür)
└─ kobe/
   ├─ README.md               # ← docs/FIGO.md taşınır: ne alır, ne verir, sorumluluk sınırı
   ├─ CHANGELOG.md            # Kobe'nin kendi güncellemeleri
   ├─ .venv/                  # Kobe'nin KENDİ Paddle'ı (karar 11, git'te değil)
   ├─ gereksinimler.txt       # tam sürüm pinleri — .venv bundan yeniden kurulur (git'te)
   ├─ config.yaml             # eşikler/bayraklar (MITAS_JENERIK_V5, _PAD=10, METIN_KAPI=1 …)
   ├─ sozlesme.py             # Girdi / Cikti / Ariza tipleri
   ├─ main.py                 # CLI girişi
   ├─ src/
   │  ├─ motor.py             # ← harness/kunye_kiyas/kobe.py     (1325 satır)
   │  ├─ kutu.py              # ← harness/kunye_kiyas/credit_box.py
   │  └─ icerik.py            # ← harness/kunye_kiyas/credit_content.py
   ├─ tests/                  # ← tests/test_kobe_router_ve_gorunurluk.py + sözleşme testleri
   ├─ olcum/                  # ← olc_pool.py, hata_atlasi.py, veri/det_isit.py
   ├─ golden/                 # örnek girdi + BEKLENEN çıktı (küçük, git'te)
   ├─ raporlar/               # ölçüm sonuçları (git'te)
   ├─ logs/                   # koşu günlükleri (git'te değil)
   ├─ scratch/                # geçici kare dizini — iş bitince SİLİNİR (git'te değil)
   └─ out/                    # <film_id>/kobe.json (git'te değil)
```

**Klasör adları alt çizgili/kısa olmalı** — Python paketi olarak import edilecekler.
Tireli isim (`lebron-james`) import edilemez.

**Bugün diskte duran boş `Players/` iskeleti silinir** — tek iskelet kalır.

---

## 4. Kobe kulesi

### 4.1 Sorumluluk sınırı

Kobe **tek** bir şey yapar: **film sonu jeneriğinin başladığı kareyi bulur.**

Yapmaz: kare havuzu kurmaz, master PNG üretmez, künye okumaz, isim düzeltmez,
PDF yazmaz, Database'e künye yazmaz. Bunların hepsi başka kulelerin işi.

### 4.2 Ne girer, ne girmez

**TAŞINIR** (`git mv` — eski yerde kalmaz):

| Kaynak | Hedef |
|---|---|
| `harness/kunye_kiyas/kobe.py` | `Allstar/kobe/src/motor.py` |
| `harness/kunye_kiyas/olc_pool.py` | `Allstar/kobe/olcum/olc_pool.py` |
| `harness/kunye_kiyas/hata_atlasi.py` | `Allstar/kobe/olcum/hata_atlasi.py` |
| `harness/kunye_kiyas/v5_izleme.py` | `Allstar/kobe/olcum/v5_izleme.py` |
| `harness/kunye_kiyas/veri/` (tümü: GT, ölçüm, `det_isit.py`) | `Allstar/kobe/olcum/veri/` |
| `tests/test_kobe_router_ve_gorunurluk.py` | `Allstar/kobe/tests/` |
| `docs/FIGO.md` | `Allstar/kobe/README.md` (FIGO adı temizlenerek) |
| `harness/kunye_kiyas/figo.py` | **SİLİNİR** (karar 8) |

**KOPYALANIR** (`git mv` DEĞİL — aslı yerinde kalır):

| Kaynak | Hedef | Neden kopya |
|---|---|---|
| `harness/kunye_kiyas/credit_box.py` | `Allstar/kobe/src/kutu.py` | Aslını **üretim okuyucusu** kullanıyor: `scripts/_pipe_hibrit_okuma.py:111` → `import credit_box`. Taşınırsa okuyucu kırılır; okuyucu yeni yolu gösterse bu kez okuyucu Kobe'nin klasörüne bağımlı olur — kaçtığımız şeyin ta kendisi. |
| `harness/kunye_kiyas/credit_content.py` | `Allstar/kobe/src/icerik.py` | Aslını `tests/test_credit_content_betik_rol.py` ve `tests/test_rol_iskandinav.py` kullanıyor. |

> **Kopyalama, Paddle kararının (karar 11) bir üst katmanda tekrarıdır:** ortak
> kaynak = ortak kader. Okuyucu için `credit_box`'a yapılan bir düzeltme Kobe'nin
> %94.5'ini sessizce oynatabilirdi. İki dosya zaten ayrışmak istiyor — Kobe'ye
> det **onset için**, okuyucuya det **okuma için** lazım; tek dosya olmaları
> tasarım değil, tarih.
>
> **Kayıtlı borç:** bu çift kopya kalıcı değil. Okuma kulesi kurulduğunda
> kendi kopyasını alır ve `harness/kunye_kiyas/` tamamen silinir. Borç burada
> yazılıdır — fark edilmemiş değil, ertelenmiş.

**Kule dışında kalır:**

| Ne | Neden |
|---|---|
| `core/lexicon/rol_tablosu.py` | **Zemin** (karar 12): saf-stdlib rol/betik sözlüğü, repoda 6+ tüketicisi var (`credit_text_read`, `credit_parse`, `credit_role_lexicon`, testler). Kopyalanırsa sözlük çatallanır — okuyucuya eklenen rol Kobe'ye ulaşmaz. Paylaşılan salt-okunur bilgi; üretilen veri değil. |
| `core/pipelines/ocr/jenerik_detector.py`, `jenerik_frame_pool_detector.py`, `jenerik_oneocr_detector.py`, `jenerik_primitifleri.py` | Adları "jenerik" ama işleri jenerik-başlangıç tespiti **değil**: kare havuzu kurma, master kırpma, görüntü yardımcıları (`imread_unicode`, `list_images`, `is_credit_text_line`). Nash/LeBron toprağı. `docs/FIGO.md`: *"jenerik-başlangıç bulma işi SADECE FIGO'dur"*. |
| `scripts/_jenerik_pool.py` | **Çağıran** taraf — hat orkestratörü. Kobe'yi sözleşmeden çağırır, kulenin içine girmez. |
| `harness/kunye_kiyas/isim_normalize.py`, `kunye_cikar.py`, `test_isim_normalize.py`, `exit_kesim/` | Künye çıkarma / kesim toprağı. Kobe hiçbirini import etmiyor. Okuma kulesi sırasında ele alınacak. |

### 4.3 Sözleşme

**Girdi**

```python
@dataclass(frozen=True)
class Girdi:
    film_id: str                  # arşiv kimliği, örn "2025-1307-1-0000-50-0" — TEK kimlik
    video: str | None = None      # MUTLAK yol — STANDART yol
    kareler: str | None = None    # MUTLAK yol — hazır kare dizini (alternatif yol)
    config: dict = field(default_factory=dict)   # config.yaml'dan; çağıran ezebilir
```

`video` ve `kareler`'den **tam olarak biri** verilir; ikisi birden ya da hiçbiri
verilirse `ARIZA(sinif="GIRDI_HATASI")` döner — sessizce bir tarafı seçmez.

**Çıktı** — `out/<film_id>/kobe.json`

```json
{
  "film_id": "2025-1307-1-0000-50-0",
  "durum": "BULUNDU",
  "baslangic_kare": 940,
  "baslangic_sn": 470.0,
  "guven": 0.87,
  "script": "ar",
  "kanit": {
    "kare_sayisi": 720,
    "kare_fps": 2.0,
    "pencere_baslangic_sn": 0.0,
    "yontem": "tespit_v5",
    "oy_dagilimi": {"ar": 4, "en": 1}
  },
  "motor_surumu": "kobe@8a7196f4",
  "uretim_zamani": "2026-08-12T18:04:11+03:00",
  "sure_sn": 42.1
}
```

**`durum` üç değer alır ve bu ayrım DEĞİŞMEZDİR:**

| durum | Anlamı |
|---|---|
| `BULUNDU` | Jenerik başlangıcı bulundu. |
| `KREDI_YOK` | Film gerçekten jeneriksiz — **içerik gerçeği**. |
| `ARIZA` | Okuyamadık: video bozuk, ffmpeg patladı, OCR çöktü, model yok. **Arıza gerçeği.** `sinif`, `mesaj`, `kanit` alanları zorunlu. |

> **Değişmez kural:** `ARIZA` asla `KREDI_YOK`'a dönüşmez. Son bir ayın tekrar
> eden hastalığı tam buydu — model EOL → "özet yok", CUDA OOM → "ses yok",
> çökme → "Latin". Geniş `except` arızayı içerik gerçeğine çevirdiği an
> aşağı akış kirlenir. Kobe'de bu kapı kapalı.

### 4.4 CLI

Giriş noktası `Allstar/kobe/kobe` — kendi venv'ini kendi bulan sarmalayıcı betik.
Çağıran hangi python'la koşulacağını **bilmez** (karar 11'in doğrudan sonucu):

```bash
# TOPLU — standart yol: girdi yolundaki her videoyu işle,
# bitmiş olanı atla (idempotent, kaldığı yerden devam eder)
Allstar/kobe/kobe start --input /yol/videolar

# TOPLU — alternatif: girdi yolu hazır kare dizinleri içeriyorsa
Allstar/kobe/kobe start --input /yol/kare_dizinleri --kareler

# TEK film
Allstar/kobe/kobe tek --video   /yol/film.mp4     --film-id 2025-1307-1-0000-50-0
Allstar/kobe/kobe tek --kareler /yol/frames/cikis --film-id 2025-1307-1-0000-50-0
```

Sarmalayıcı üç satırdır: `exec "$(dirname "$0")/.venv/bin/python" "$(dirname "$0")/main.py" "$@"`.
Paket (`python -m`) yapısı **kullanılmaz** — `Allstar` büyük harfli, `__init__.py`
zinciri gereksiz, ve MITAS'ın mevcut deyimi zaten `<venv>/bin/python <betik>`.

Çıktı daima `Allstar/kobe/out/<film_id>/`. Çağıran çıktı yolunu **seçmez** —
kule kendi evine yazar (karar 4).

**Toplu modda `film_id` nereden gelir** (tahmin yok, tek kural):

- `--input` altındaki her öğe bir filmdir.
- Video modunda: `film_id` = **video dosyasının uzantısız adı**.
  `/yol/videolar/2025-1307-1-0000-50-0.mp4` → `2025-1307-1-0000-50-0`
- `--kareler` modunda: `film_id` = **kare dizininin adı**.
- Farklı bir kimlik gerekiyorsa `tek --film-id` ile açıkça verilir; toplu mod
  kimlik türetmeye çalışmaz.
- `out/<film_id>/_TAMAM` varsa o öğe **atlanır** — `start` kaldığı yerden devam
  eder, aynı işi iki kez yapmaz.

### 4.5 Koşu akışı (tek film)

1. **Kare kaynağı belirlenir:**
   - `video` verildiyse (standart): `scratch/<film_id>/` açılır, kapanış
     penceresi çıkarılır. Bu dizin **Kobe'nindir**.
   - `kareler` verildiyse: o dizin doğrudan kullanılır, `scratch` açılmaz.
     Bu dizin **Kobe'nin değildir**.

   **Çıkarım tarifi — uydurulmaz, ölçüm yatağının tarifi birebir kullanılır**
   (`veri/havuz_kur.sh:74-78`, `TAIL_S=600  FPS=2`). Kobe'nin %94.5'i bu kare
   üretimiyle ölçüldü; başka bir tarif skoru geçersiz kılar:

   ```bash
   dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$VIDEO" | cut -d. -f1)
   ss=$(( dur > 600 ? dur - 600 : 0 ))          # son 10 dakika
   ffmpeg -y -v error -ss "$ss" -i "$VIDEO" -vf "fps=2" -q:v 3 "$SCRATCH/c_%05d.png"
   ```

   Dosya adı deseni `c_%05d.png` **sözleşmedir**: `motor._kare_no()` addaki son
   sayıyı mutlak kare numarası olarak okur, `motor.kareler()` `*.png`'yi sıralı
   glob'lar. `baslangic_sn` = `ss + baslangic_kare / 2.0`.
2. `src/motor.tespit_v5(...)` ile kararı üret.
3. `out/<film_id>/kobe.json.tmp` yaz → `os.replace()` ile `kobe.json` yap →
   `_TAMAM` işaret dosyası yaz.
4. `finally:` **yalnızca Kobe'nin açtığı** `scratch/<film_id>/` silinir —
   başarıda da, arızada da. Dışarıdan verilen kare dizinine **asla dokunulmaz**
   (tek-yazar ilkesi: kule kendi yaratmadığını silmez).

**Neden `os.replace` + `_TAMAM`:** kuyruk klasörün kendisi olduğu için tüketici
(LeBron) Kobe yazarken okuyabilir. Atomik yeniden adlandırma yarım dosya
okunmasını, `_TAMAM` ise "yazılıyor mu bitti mi" belirsizliğini kapatır.
Tüketici kuralı: **`_TAMAM` yoksa dosya yok sayılır.**

### 4.6 Database görünümü

`out/<film_id>/kobe.json` → `Database/<Film>/kobe.json` olarak **hardlink**'lenir
(karar 5). Film klasöründen her şeye erişim korunur, ek yer kaplamaz, gerçek
bayttır.

### 4.7 Çalışma zamanı ve kaynak bölüşümü

**Makine (2026-08-12 ölçümü):** tek RTX 3090 24 GB · 64 çekirdek · 121 GB RAM ·
35 GB pip önbelleği (Paddle tekerlekleri yerelde).

**Kobe'nin çalışma zamanı** — `Allstar/kobe/.venv`, `gereksinimler.txt`'ten
kurulur. Pinler `venvs/ocr`'dan alınır ki taşıma **aynı sürümlerle** ölçülsün:

```
paddlepaddle-gpu==3.3.1   paddleocr==3.7.0   paddlex==3.7.2
numpy==2.3.5   pillow==12.1.0   opencv-contrib-python==5.0.0.93
shapely==2.1.2   pyclipper==1.4.0   scikit-image==0.26.0   scipy==1.18.0
```

**Paralellik süreçten gelir, kurulumdan değil.** Bu ayrım kilitlidir: tek
kurulum N süreç açabilir, N kurulum tek süreç açarsa hiçbir şey paralelleşmez.
MITAS bunu bugün zaten yapıyor — `olc_pool.py:81` `mp.get_context("spawn").Pool(n)`,
her işçide Paddle bir kez init olur. Kobe'nin kendi venv'i **sürüm dondurmak**
içindir (karar 11), paralellik için değil.

**Reddedilen: ortak "Paddle kulesi" (servis).** ① Kobe canlı bir dış servise
bağımlı hale gelir — "sorun Kobe'de mi Paddle'da mı?" sorusu geri döner, kule
mimarisinin tek kazancı ölür. ② Paralellik zaten vermez: tek süreç istekleri
sıraya dizer, eşzamanlılık için yine N işçi = N model = aynı VRAM. ③ Tek nokta
arızası: Paddle kulesi düşerse tüm kuleler durur.

**Gerçek sınır disk değil, VRAM.** 24 GB paylaşımlı ve bu duvara bu proje zaten
çarptı: `_get_mms()` CUDA OOM'u ("free 80MB / total 25GB") sessizce yutuldu,
1035 kaydın 777'sinde ANA DİL boş kaldı. Kural: **OOM → `ARIZA`**, asla düşük
kaliteli sonuç (§4.3 değişmezi).

**Kaynak bölüşümü hedefi (ölçüme tabi, varsayım değil):** Kobe'nin Paddle yükü
ağırlıklı **detection-only** (`src/kutu.py` → `TextDetection`, kare serisi
boyunca); `rec` yalnız birkaç aday karede (`src/icerik.py` başlığı: *"rec sadece
ADAY karelerde, maliyet düşük"*). Bu yük profili CPU'ya uygun. Hedef bölüşüm:

| Kule | Cihaz | Paralellik |
|---|---|---|
| Kobe | **CPU** (64 çekirdek) | geniş süreç havuzu |
| Okuma kulesi (LeBron/Nash) | **GPU** (24 GB'ın tamamı) | dar |

Böylece iki kule farklı kaynakta koşar, birbirinin kuyruğunu beklemez —
*"CPU GPU boş kalmaz"* isteği bundan çıkar.

> **Bu bölüşüm bu taşımanın kapsamı DIŞINDA.** CPU ve GPU kayan-nokta farkı det
> kutu koordinatını oynatabilir, bir eşik dönebilir. 110 filmlik yatakta
> ölçülmeden kabul edilmez; Kobe kule olarak kurulduktan **sonra** ayrı bir iş
> olarak, Çağatay'ın onayıyla ölçülür. Taşıma GPU'da, mevcut davranışla yapılır.

**Toplu koşuda üç koruma** (Çağatay'ın *"1000 filmi işle bırak"* akışı için):

1. **İlk-parti kapısı** — 1000 değil: önce 20 film → ölç → sonra salıver.
   Yanlış config'le 1000 film = 1000 bozuk çıktı; bu, bu projeye bir ay
   kaybettiren hata sınıfının ta kendisi.
2. **`maxtasksperchild`** — `olc_pool.py` bugün ayarlamıyor. Uzun koşuda işçi
   süreç bellek/VRAM biriktirir. `Pool(n, maxtasksperchild=25)` → işçi her 25
   filmde tazelenir.
3. **`_TAMAM` ile yeniden başlatılabilirlik** — 700. filmde çökme 700 filmi
   kaybettirmez (§4.4). Toplu mod bunu opsiyonel olmaktan çıkarıp şart yapar.

---

## 5. Taşıma tarifi (Sonnet yürütür)

Her adımın geçme ölçütü var. **Ölçüt sağlanmazsa dur ve rapor et — kendi başına
düzeltmeye çalışma.**

| # | Adım | Komut / iş | Geçme ölçütü |
|---|---|---|---|
| 1 | **Ölçüm ÖNCE** | `cd harness/kunye_kiyas && venvs/ocr/bin/python olc_pool.py --paralel 8` → `Allstar/kobe/raporlar/olcum_ONCE.json` | Dosya yazıldı. **Gerçek referans** (`veri/olcum_son.json`, 2026-08-12 12:43): kapsam **110**, genel **%94.5**, üretim **%97.3**, kredi-var **75/81**, kredi-yok **29/29**, eksik **5** |
| 2 | **Geri-dönüş noktası** | Ağaç temiz olacak şekilde commit; SHA `raporlar/`'a yazılır | `git status` temiz, SHA kayıtlı |
| 3 | **Kobe'nin venv'i** | `Allstar/kobe/.venv` kur + `gereksinimler.txt` yaz (§4.7 pinleri) | `.venv/bin/python -c "import paddle,paddleocr"` → 3.3.1 / 3.7.0 |
| 4 | **Venv paritesi** | 1. adımın aynısı, **ama yeni venv ile**, dosyalar HÂLÂ eski yerinde → `olcum_VENV.json` | **Sapma sıfır.** Sapma varsa sorun venv'dedir, taşımada değil — burada yakalanır |
| 5 | **Taşıma** | §4.2: TAŞINIR satırları `git mv`, KOPYALANIR satırları `cp` | Dosyalar hedefte; `git log --follow` taşınanlarda çalışıyor |
| 6 | **Import yolları** | Taşınan dosyalarda `import figo` → `import motor`; `credit_box`/`credit_content` → `kutu`/`icerik`. `scripts/_jenerik_pool.py` doğrudan yeni yola çevrilir | Import hatası yok |
| 7 | **Testler** | `pytest Allstar/kobe/tests -q` | Taşıma öncesiyle **aynı** sonuç (19/19 geçiyor) |
| 8 | **Ölçüm SONRA** | 1. adımın aynısı, yeni yoldan → `olcum_SONRA.json` | **Sapma sıfır.** Herhangi bir sapmada DUR |
| 9 | **Temizlik** | `figo` adı repo genelinden temizlenir, boş `Players/` silinir | `grep -rn "figo" --include="*.py"` → sıfır sonuç; 7. ve 8. adım tekrar geçiyor |

**Neden 4. adım (venv paritesi) ayrı:** venv değişimi ile dosya taşıması aynı
anda yapılırsa ve skor kayarsa hangisinin kaydırdığı bilinemez. Tek seferde tek
değişken.

**Köprü katmanı YOK — gerek olmadığı ölçüldü.** `figo`'yu import eden 4 dosyanın
üçü (`olc_pool.py`, `hata_atlasi.py`, `veri/det_isit.py`) Kobe ile **birlikte
taşınıyor**; dışarıda kalan tek çağıran `scripts/_jenerik_pool.py` ve üretim
durmuş durumda, doğrudan güncellenebilir. Geçici köprü yazmak boş iş olurdu.

---

## 6. Kapsam dışı

- Diğer kuleler (LeBron, Nash, Jordan, Shaq, Phil Jackson, Lakers, Sixers,
  Iverson, okuma kulesi) — sırası geldiğinde Çağatay söyleyecek.
- Dizi modu.
- Okuma kulesinin adı.
- `core/pipelines/ocr/jenerik_*` dosyalarının akıbeti — Nash/LeBron taşınırken
  ele alınacak.
- Üretim hattının yeniden başlatılması — taşıma bitince Çağatay açacak.
