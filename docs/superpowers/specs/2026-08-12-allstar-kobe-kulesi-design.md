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

---

## 3. Allstar yerleşimi

```
Allstar/
├─ MAP.md                     # kod adı ↔ gerçek görev sözlüğü (kule eklendikçe büyür)
└─ kobe/
   ├─ README.md               # ← docs/FIGO.md taşınır: ne alır, ne verir, sorumluluk sınırı
   ├─ CHANGELOG.md            # Kobe'nin kendi güncellemeleri
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

**Kule içine taşınır:**

| Kaynak | Hedef |
|---|---|
| `harness/kunye_kiyas/kobe.py` | `Allstar/kobe/src/motor.py` |
| `harness/kunye_kiyas/credit_box.py` | `Allstar/kobe/src/kutu.py` |
| `harness/kunye_kiyas/credit_content.py` | `Allstar/kobe/src/icerik.py` |
| `harness/kunye_kiyas/olc_pool.py` | `Allstar/kobe/olcum/olc_pool.py` |
| `harness/kunye_kiyas/hata_atlasi.py` | `Allstar/kobe/olcum/hata_atlasi.py` |
| `harness/kunye_kiyas/veri/det_isit.py` | `Allstar/kobe/olcum/veri/det_isit.py` |
| `tests/test_kobe_router_ve_gorunurluk.py` | `Allstar/kobe/tests/` |
| `docs/FIGO.md` | `Allstar/kobe/README.md` (FIGO adı temizlenerek) |
| `harness/kunye_kiyas/figo.py` | **SİLİNİR** (karar 8) |

**Kule dışında kalır:**

| Ne | Neden |
|---|---|
| `core/pipelines/ocr/jenerik_detector.py`, `jenerik_frame_pool_detector.py`, `jenerik_oneocr_detector.py`, `jenerik_primitifleri.py` | Adları "jenerik" ama işleri jenerik-başlangıç tespiti **değil**: kare havuzu kurma, master kırpma, görüntü yardımcıları (`imread_unicode`, `list_images`, `is_credit_text_line`). Nash/LeBron toprağı. `docs/FIGO.md`: *"jenerik-başlangıç bulma işi SADECE FIGO'dur"*. |
| `scripts/_jenerik_pool.py` | **Çağıran** taraf — hat orkestratörü. Kobe'yi sözleşmeden çağırır, kulenin içine girmez. |
| `harness/kunye_kiyas/isim_normalize.py`, `kunye_cikar.py`, `v5_izleme.py` | Phil Jackson / künye çıkarma toprağı. Kobe değil. |

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

```bash
# TOPLU — standart yol: girdi yolundaki her videoyu işle,
# bitmiş olanı atla (idempotent, kaldığı yerden devam eder)
python -m Allstar.kobe start --input /yol/videolar

# TOPLU — alternatif: girdi yolu hazır kare dizinleri içeriyorsa
python -m Allstar.kobe start --input /yol/kare_dizinleri --kareler

# TEK film
python -m Allstar.kobe tek --video   /yol/film.mp4        --film-id 2025-1307-1-0000-50-0
python -m Allstar.kobe tek --kareler /yol/frames/cikis    --film-id 2025-1307-1-0000-50-0
```

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
   - `video` verildiyse (standart): `scratch/<film_id>/` açılır, ffmpeg ile
     **kapanış penceresi** çıkarılır (`fps=2.0`, mevcut `_jenerik_detect`
     davranışı). Bu dizin **Kobe'nindir**.
   - `kareler` verildiyse: o dizin doğrudan kullanılır, `scratch` açılmaz.
     Bu dizin **Kobe'nin değildir**.
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

---

## 5. Taşıma tarifi (Sonnet yürütür)

Her adımın geçme ölçütü var. **Ölçüt sağlanmazsa dur ve rapor et — kendi başına
düzeltmeye çalışma.**

| # | Adım | Komut / iş | Geçme ölçütü |
|---|---|---|---|
| 1 | **Ölçüm ÖNCE** | `cd harness/kunye_kiyas && python olc_pool.py --paralel 8` → `Allstar/kobe/raporlar/olcum_ONCE.json` | Dosya yazıldı; sayılar kaydedildi. Referans: simetrik **%93.6**, üretim **%97.3**, kredisiz-red **29/29** |
| 2 | **Geri-dönüş noktası** | Ağaç temiz olacak şekilde commit; SHA `raporlar/`'a yazılır | `git status` temiz, SHA kayıtlı |
| 3 | **Taşıma** | §4.2 tablosundaki her satır için `git mv` | Tüm dosyalar hedefte; git geçmişi korunmuş (`git log --follow` çalışıyor) |
| 4 | **Köprü** | Eski `figo`/`kobe` import adları geçici olarak yeni yola yönlendirilir | Mevcut 4 çağıran (`olc_pool`, `hata_atlasi`, `det_isit`, `scripts/_jenerik_pool`) import hatası vermiyor |
| 5 | **Testler** | `pytest Allstar/kobe/tests -q` | Taşıma öncesiyle **aynı** sonuç (hepsi geçiyor) |
| 6 | **Ölçüm SONRA** | 1. adımın aynısı → `olcum_SONRA.json` | **Sapma sıfır.** Herhangi bir sapmada DUR |
| 7 | **Temizlik** | Çağıranlar sözleşmeye çevrilir, köprü silinir, `figo` adı repo genelinden temizlenir, boş `Players/` silinir | `grep -rn "figo" --include="*.py"` → sıfır sonuç; 5. ve 6. adım tekrar geçiyor |

---

## 6. Kapsam dışı

- Diğer kuleler (LeBron, Nash, Jordan, Shaq, Phil Jackson, Lakers, Sixers,
  Iverson, okuma kulesi) — sırası geldiğinde Çağatay söyleyecek.
- Dizi modu.
- Okuma kulesinin adı.
- `core/pipelines/ocr/jenerik_*` dosyalarının akıbeti — Nash/LeBron taşınırken
  ele alınacak.
- Üretim hattının yeniden başlatılması — taşıma bitince Çağatay açacak.
