# JORDAN KATALOĞU

> Kulenin kimlik kartı. Günlük kullanım için `README.md`, tarihçe için
> `CHANGELOG.md`, canlı durum için `DURUM.md`. Bu belge **ne olduğunu ve neden
> öyle olduğunu** anlatır.
>
> Sürüm: 2026-08-13 · Kule: `Allstar/jordan/`

## Beş soru — doğrudan cevaplar

| # | Soru | Bölüm |
|---|---|---|
| 1 | Jordan kulesi **neden var?** | [§1](#1-jordan-neden-var) |
| 2 | Jordan kulesi **nasıl hizmet verir?** | [§2](#2-jordan-nasıl-hizmet-verir) |
| 3 | Jordan kulesi **nasıl çalışır** (taslak)? | [§3](#3-jordan-nasıl-çalışır) |
| 4 | **Girdi ve çıktı sözleşmeleri** nedir? | [§4](#4-girdi-ve-çıktı-sözleşmeleri) |
| 5 | Jordan kulesinin **iç yapısı** | [§5](#5-iç-yapı) |
| + | Model seçimi ve donanım sınırı | [§6](#6-model-seçimi-ve-donanım) |
| + | Doğrulama durumu ve bilinen sınırlar | [§7](#7-doğrulama-durumu) |

**Jordan'a dair her şey bu klasörde yaşar.** Kod, sözleşme, çalışma zamanı,
model ağırlıkları, testler, koşu sonuçları, raporlar, günlük — hepsi
`Allstar/jordan/` içinde. Kulenin dışında Jordan'a ait hiçbir şey yoktur.

---

## 1. Jordan neden var?

Bir filmin künyesini okumanın bugünkü yolu **master PNG**'dir: kareler
çıkarılır, jenerik bölgesi kesilir, birleştirilir, sonra okunur. Uzun bir
zincir; her halkası ayrı bir hata kaynağı.

Jordan tek bir soruyu cevaplanabilir kılar: **videoyu doğrudan okutsak ne olur?**

`Allstar/MAP.md` bunu şöyle tarif eder: LeBron (master PNG), Nash (kare havuzu)
ve Jordan (native video) aynı işe **üç ayrı beslemedir**. Üçü de aynı yatakta
ölçülünce "master PNG gerekli mi" sorusu tartışmayla değil sayıyla kapanır.

### Ne YAPMAZ

Jeneriğin nerede başladığını aramaz (**Kobe'nin işi**) · isim düzeltmez ·
eksik tamamlamaz · hangi filmin hangi yoldan okunacağına karar vermez
(**router değildir**) · PDF yazmaz · Database'e yazmaz.

Bu liste kısaltma değil, sınır. Jordan'a router eklenirse "video mu master PNG
mi daha iyi" sorusu ölçülemez hale gelir: kule kendi lehine seçim yapmış olur.

---

## 2. Jordan nasıl hizmet verir?

**Ağ yok, servis yok, API yok.** Kule bir **klasör + sözleşme**dir.

```
Kobe klibi → CLI → Jordan → out/<film_id>/<bolum>/  ← Tüketici okur
                                    ^
                               kuyruk BURASI
```

| Kural | Neden |
|---|---|
| Çağıran **çıktı yolunu seçmez** | Her dizinin tek yazarı olur |
| `_TAMAM` **en son** yazılır | Tüketici yarım veri okuyamaz |
| `_TAMAM` yoksa **dosya yok sayılır** | Tüketicinin tek kuralı bu |
| `os.replace` ile atomik yazım | Yarım JSON okunamaz |
| `_TAMAM` varsa öğe **atlanır** | İdempotent — koşu kaldığı yerden devam eder |
| Model **bir kez** yüklenir | 14 GB'ı her film için okumak saçmadır |

---

## 3. Jordan nasıl çalışır?

```
GİRDİ: mp4 (jeneriğin KENDİSİ olan bir klip — standart: Kobe --uret klip)
   │
   ├─ PARÇALAMA  src/okuyucu.py :: parcala
   │    ffprobe → süre
   │    ffmpeg -ss/-t + fps=2 + lanczos/hqdn3d/unsharp @720p  →  scratch/
   │    15 sn parça, 2 sn bindirme, kare tavanı 30
   │    (bu dizin JORDAN'INDIR — iş bitince silinir)
   │
   ├─ GEÇİŞ 1 — OKUMA  src/okuyucu.py :: oku
   │    her parça mp4 olarak MODELE verilir (native video)
   │    çıktı: boş satırla ayrılmış ekran blokları
   │    · düşünme sızıntısı ayıklanır + sayılır
   │    · "yazı yok" bildirimleri (işaret VE cümle) elenir
   │    · ardışık parçadaki birebir aynı blok düşer
   │
   ├─ GEÇİŞ 2 — ÇİFTLEME  src/ciftleyici.py :: ciftle
   │    YALNIZ geçiş 1'in METNİ girer — görüntü GİRMEZ
   │    çıktı: ROL<TAB>İSİM
   │    · SIZDIRMAZLIK KAPISI: her rol/isim geçiş 1'de geçmeli
   │
   ▼
KARAR: OKUNDU │ METIN_YOK │ ARIZA
   ├─ jordan.txt yaz (düz metin)
   ├─ jordan.json yaz (atomik)
   ├─ _TAMAM yaz  ← EN SON
   └─ scratch/ sil (yalnız kendi açtığını)
```

### Neden iki geçiş?

Tek istekte model rolü tutturmak için **metni düzeltmeye başlar**. O an okuma
hatasıyla eşleme hatası birbirine karışır ve hangisinin bozuk olduğu
ayrılamaz. Geçiş 2'ye görüntü vermemek bunu yapısal olarak imkânsız kılar:
elinde pikselden gelen yeni bilgi yoktur, yalnız geçiş 1'in metni vardır.

**Sızdırmazlık kapısı** bunu kodla mühürler: geçiş 2'nin ürettiği her rol ve
her isim, geçiş 1'in satırlarında geçmek zorundadır. Geçmiyorsa çıktıya
girmez, `kanit.cift_eleme` sayacına yazılır. Uydurma sessizce veri olmaz,
görünür bir sayı olur.

**Geçiş 2 çökerse geçiş 1 atılmaz.** Bloklar gerçek okumadır, çiftler türev
veridir.

### Neden parçalanıyor? — ölçülmüş sınır

Sandbox ölçümü (2026-08-12), aynı model, aynı kart:

| Kurulum | Sonuç |
|---|---|
| 36 kare/çağrı @720p, tek istek | **39 filmin 39'unda CUDA OOM** |
| 30 kare/çağrı, 15 sn parça + 2 sn bindirme | çalıştı |

Marj jilet gibi. Parçalama bir yorum katmanı değil — modelin 24 GB'lık bu
kartta koşabilmesinin **tek** yolu. `parca.kare_tavani` bu sınırın freni:
`sure_sn × fps` tavanı aşarsa parça süresi otomatik kısalır.

Bindirme, parça sınırında kesilen ismi kurtarır. Ardışık parçadaki **birebir
aynı** blok düşer; **uzak tekrarlar korunur** — jenerikte aynı isim gerçekten
iki kez geçebilir ve onu silmek veri kaybıdır.

### Neden düşünme kapalı?

Qwen3.5 varsayılan olarak akıl yürütür. Sandbox çıktısında model
*"Wait, looking closely at the first frame…"* diye kendi kendine tartışıyor ve
cevabı kaçak bir `</think>` ile **iki kez** basıyordu. Bu hem "yorum yok"
kuralının ihlali hem de bozuk çıktı.

`dusunme: false` + ayıklayıcı: son `</think>` sonrası alınır, sızıntı
`kanit.dusunme_sizinti`'ye yazılır; blok kapanmamışsa `ARIZA(CIKTI_BOZUK)`.
Sessizce temizleyip "okundu" denmez.

---

## 4. Girdi ve çıktı sözleşmeleri

### GİRDİ

```python
@dataclass(frozen=True)
class Girdi:
    film_id: str                  # TEK kimlik, arşiv numarası
    video:   str                  # MUTLAK yol — mp4. ZORUNLU.
    bolum:   str = "cikis"        # cikis | giris
    config:  dict = {}            # config.yaml'ı ezmek için
```

**Jordan kare dizini/PNG havuzu almaz.** Girdisi videodur ve verilen klibin
**jeneriğin kendisi olduğunu varsayar**. "Jenerik nerede" sorusu Kobe'nindir;
Jordan onu ikinci kez cevaplamaya kalkarsa iki motor iki cevap üretir ve
hangisinin doğru olduğu belirsizleşir.

`film_id` toplu modda dosyanın uzantısız adıdır — tahmin yok.

### ÇIKTI — `out/<film_id>/<bolum>/`

```json
{
  "film_id": "1989-0352_KUKLA_ADAM",
  "bolum": "cikis",
  "durum": "OKUNDU",
  "bloklar": [
    {"no": 1, "parca": 5, "sn": 65.0,
     "satirlar": ["EDITOR", "MURRAY FERGUSON"]}
  ],
  "ciftler": [
    {"rol": "EDITOR", "isim": "MURRAY FERGUSON", "blok": 1}
  ],
  "kanit": {
    "parca_sayisi": 19, "bozuk_parca": 0, "dusunme_sizinti": 0,
    "blok_sayisi": 15, "satir_sayisi": 28,
    "cift_sayisi": 8, "cift_eleme": 0,
    "model": "model/w8a8", "parca_sn": 15, "bindirme_sn": 2,
    "video_fps": 2, "video_genislik": 720
  },
  "motor_surumu": "jordan@<sha>",
  "uretim_zamani": "2026-08-13T16:24:11+03:00",
  "sure_sn": 120.0
}
```

Yanında `jordan.txt` — satırlar göründüğü sırayla, tek sütun.

**`sn` parça çözünürlüğündedir:** bloğun içinde bulunduğu parçanın başlangıç
saniyesidir, bloğun ekrana geldiği tam an değil. Daha ince zaman istenirse
`parca.sure_sn` küçültülür.

### `durum` — üç değer, DEĞİŞMEZ ayrım

| durum | Anlamı | Zorunlu |
|---|---|---|
| `OKUNDU` | Metin okundu | `bloklar` (boş olamaz) |
| `METIN_YOK` | Klipte gerçekten okunacak yazı yok — **içerik gerçeği** | — |
| `ARIZA` | Okuyamadık — **arıza gerçeği** | `sinif`, `mesaj` |

> ### En önemli değişmez
> **`ARIZA` asla `METIN_YOK`'a dönüşmez.**
>
> Geniş bir `except` arızayı içerik gerçeğine çevirdiği an aşağı akış kirlenir
> ve **kimse fark etmez**. Kobe'den devralınan ders budur.
>
> Sözleşme kodla zorlar: `ARIZA` `sinif`+`mesaj` olmadan yaratılamaz;
> `METIN_YOK` ve `ARIZA` blok/çift **taşıyamaz**; `OKUNDU` bloksuz olamaz.

| sinif | Ne oldu |
|---|---|
| `GIRDI_HATASI` | video yok / sözleşme ihlali |
| `VIDEO_OKUNAMADI` | ffprobe/ffmpeg patladı, parça üretilemedi |
| `BELLEK` | CUDA OOM — çaresi `parca.sure_sn` küçültmek |
| `CIKTI_BOZUK` | Model konuştu ama çıktısı kullanılamaz |
| `MODEL` | Model yüklenemedi / beklenmedik istisna |

---

## 5. İç yapı

```
Allstar/jordan/
├─ jordan                  ← GİRİŞ NOKTASI (kendi venv'ini bulur)
├─ main.py                 ← CLI + koşu akışı + arıza sınıflandırması
├─ sozlesme.py             ← Girdi / Cikti / ariza  (kulenin DIŞ yüzü)
├─ config.yaml             ← eşikler, parça ayarları, istemler
│
├─ src/                    ← MOTOR (dış dünyayı bilmez)
│  ├─ model.py             ← Qwen yükleme/sorma — transformers'a dokunan TEK yer
│  ├─ okuyucu.py           ← geçiş 1: parçalama + video → bloklar
│  └─ ciftleyici.py        ← geçiş 2: bloklar → çiftler + sızdırmazlık kapısı
│
├─ model/                  ← AĞIRLIKLAR (git'te değil, 33 GB)
│  ├─ w8a8/                ← INT8 W8A8, 14 GB — VARSAYILAN
│  └─ bf16/                ← orijinal, 19.3 GB — kıyasın KONTROL KOLU
├─ model_kur.sh            ← ağırlık kurulumu
├─ venv/ venv_kur.sh gereksinimler.txt
│
├─ tests/                  ← 60 test, GPU gerektirmez
├─ olcum/                  ← ölçüm yatağı (HENÜZ BOŞ — bkz. DURUM.md)
├─ out/  scratch/  logs/   ← git'te değil
└─ README.md KATALOG.md CHANGELOG.md DURUM.md
```

### Katman kuralı — tek yönlü bağımlılık

```
jordan → main.py → sozlesme.py
                        ↑
         main.py → src/okuyucu.py  → src/model.py
                 → src/ciftleyici.py ↗
```

**`src/` sözleşmeyi BİLMEZ.** Motor kendi istisnalarını atar
(`VideoHatasi`, `BellekHatasi`, `CiktiBozuk`, `ModelHatasi`); bunların
`ARIZA` sınıflarına çevrilmesi yalnız `main.py`'dedir.

---

## 6. Model seçimi ve donanım

| | `model/w8a8` (VARSAYILAN) | `model/bf16` |
|---|---|---|
| Kaynak | `RedHatAI/Qwen3.5-9B-quantized.w8a8` | `Qwen/Qwen3.5-9B` |
| Biçim | INT8 W8A8 (ağırlık kanal-simetrik, aktivasyon dinamik) | bfloat16 |
| Boyut | 14 GB | 19.3 GB |
| **Görüntü kulesi** | **kuantize DEĞİL** — `model.visual.*` bf16 | bf16 |
| Serbest VRAM (24 GB kartta) | ~9.5 GiB | ~4.5 GiB |

### FP8 bu kartta yok

RTX 3090 = Ampere `sm_86`. FP8 tensör çekirdeği `sm_89`+ (Ada/Hopper) ister.
"8-bit" istendiğinde bu donanımda doğru cevap **INT8**'dir; FP8 checkpoint'i ya
reddedilir ya emülasyonla sürünür.

### Hangisi daha iyi okuyor? — ÖLÇÜLMEDİ

INT8 varsayılandır çünkü **bellek kısıtı ölçülmüş** (39/39 OOM), kuantizasyon
kaybı ise henüz **varsayım**. Ölçülmüş kısıtı çözmek, varsayılan kaybı
önlemekten önceliklidir.

Beklenen ayrışma noktası **garble** — özel isimde karakter bozulması. Sıradan
metinde model dil önbilgisiyle toparlanır; künyede okunan şey özel isimdir ve
orada dayanacak önbilgi yoktur. Aynı metriğe iki yönden basınç var:

- daha çok kare → parça sınırı azalır → **garble düşer**
- INT8 → dil tarafında logit kayması → **garble yükselebilir**

İkisi de `garble`'a indiği için **tek ölçüm** bu soruyu kapatır.
`model/bf16` o ölçüm yapılana kadar silinmez.

---

## 7. Doğrulama durumu

**Test:** 60/60 (sözleşme 17 · okuyucu 22 · çiftleyici 8 · akış 13). Hiçbiri
GPU istemez; model sahte motorla değiştirilir.

**Uçtan uca gerçek koşu** — KUKLA ADAM, 245 sn klip, `model/w8a8`:
19 parça · 0 bozuk · düşünme sızıntısı 0 · 15 blok / 28 satır · 8 çift ·
**0 eleme** · **120.0 sn**. Jenerik doğru okundu (`DIRECTOR → PAUL HOGAN` dahil).

**Doğruluk ölçümü YAPILMADI.** Kule ayakta ve çalışıyor; ne kadar doğru
okuduğu ölçülmedi. Hazır malzeme ve eksik parça `DURUM.md` §③'te.

### Bu koşuda görülen yapısal sınır

Jenerik 91. saniyede bitiyor; klip 245 saniye sürüyor. Sonrasında model
sahnedeki metinleri okudu (`The manor of the sea`, `H.N.`, `30`) — doğru
okuma, ama künye değil. Bu Jordan'ın kusuru değil, **girdi sözleşmesinin
kendisi**: Jordan verilen klibin jenerik olduğunu varsayar. Kobe'nin klibi
verildiğinde bu bölge zaten yoktur.

2026-07 benchmark'ının "%24.7 uydurma" bulgusunun kökü de buydu: orada video
penceresi konumdan tahmin ediliyordu ("çıkış son 3 dk"). Kobe'nin onset'i bu
tahmini ortadan kaldırır — ve bu, ölçülmesi gereken ilk şeydir.
