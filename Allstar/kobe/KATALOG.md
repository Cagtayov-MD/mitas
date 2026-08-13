# KOBE KATALOĞU

> Kulenin kimlik kartı. Günlük kullanım için `README.md`, tarihçe için
> `CHANGELOG.md`, canlı durum için `DURUM.md`. Bu belge **ne olduğunu ve neden
> öyle olduğunu** anlatır.
>
> Sürüm: 2026-08-13 · Kule: `Allstar/kobe/`

---

## 1. Kobe neden var?

### Çözdüğü gerçek problem

Bir filmin künyesini (yönetmen, oyuncular, ekip) okumak için önce **nereye
bakacağını** bilmen gerekir. 90 dakikalık bir filmde künye bilgisi son 2-3
dakikadadır. Tüm filmi OCR'lamak hem imkânsız pahalı, hem de sahte veri üretir:
film içindeki tabelalar, gazete manşetleri, ara yazılar isim listesi sanılır.

**Kobe tek bir soruyu cevaplar: kapanış jeneriği hangi karede başlıyor?**

Bu cevap olmadan aşağıdaki her şey çöker. Yanlış cevap verirse:
- **Geç** söylerse → cast listesinin başı kaçar, PDF'te eksik oyuncu
- **Erken** söylerse → jenerik olmayan kareler havuza girer, sahte isimler
- **"Yok" derken var** derse → film künyesiz kalır
- **"Var" derken yok** derse → uydurma künye üretilir

Bu asimetri politikaya dönüşmüştür: **erken ≤120 kare kabul, geç ≤20 kare.**
Fazla kare zararsızdır (okuyucu eler), eksik kare veri kaybıdır.

### Neden ayrı bir kule?

Üç somut sebep:

**① Tek sorumluluk, tek teşhis.** Arıza çıktığında "sorun Kobe'de" denebilmeli.
Bu motor daha önce `harness/kunye_kiyas/figo.py` içinde, pipeline'ın ortasında
yaşıyordu; bir hata çıktığında onset mi, okuma mı, PDF mi bozuk anlaşılmıyordu.

**② Sürüm dondurma.** Kobe'nin skoru (`%94.5`) belirli bir paket kümesine
bağlı. Ortak bir sanal ortamda başkası `paddleocr`'ı yükseltirse skor sessizce
kayar. Kendi `venv/`'i bunu imkânsız kılar. *(Bu teorik değil — ölçülmüş bir
olay, bkz. §6.)*

**③ Kuyruk bağımsızlığı.** Kobe binlerce filmi kendi hızında işleyip klasörüne
bırakır; tüketici (okuma kulesi) hazır olanı alır. Kimse kimseyi beklemez,
CPU/GPU boş kalmaz.

### Ne YAPMAZ

Master PNG üretmez · künye okumaz · isim düzeltmez · PDF yazmaz ·
Database'e yazmaz · **giriş jeneriği tespit etmez** (bkz. §7).

---

## 2. Kobe nasıl hizmet verir?

**Ağ yok, servis yok, API yok.** Kule bir **klasör + sözleşme**dir. Hizmet
modeli şudur:

```
Çağıran → CLI → Kobe → out/<film_id>/  ← Tüketici okur
                         ^
                    kuyruk BURASI
```

**Kuyruk, çıktı klasörünün kendisidir.** Broker yok. Tüketici `out/`'a bakar,
`_TAMAM` dosyası olan her klasör hazırdır.

| Kural | Neden |
|---|---|
| Çağıran **çıktı yolunu seçmez** | Her dizinin tek yazarı olur; "bunu kim ezdi" sınıfı kazalar biter |
| Kobe **kendi evine** yazar | Üretici-sahipli veri (Allstar ilkesi) |
| `_TAMAM` **en son** yazılır | Tüketici yarım veri okuyamaz |
| `_TAMAM` yoksa **dosya yok sayılır** | Tüketicinin tek kuralı bu |
| `os.replace` ile atomik yazım | Yarım JSON okunamaz |
| `_TAMAM` varsa öğe **atlanır** | İdempotent — koşu kaldığı yerden devam eder |

### Üç kullanım biçimi

```bash
# 1) Tek film — soru sor, cevap al
Allstar/kobe/kobe tek --video film.mp4 --film-id 2025-1307-1-0000-50-0

# 2) Toplu kuyruk — "bu klasördeki her şeyi işle, gerisine karışma"
Allstar/kobe/kobe start --input /yol/videolar

# 3) Artefaktla — kararla birlikte kesilmiş veri iste
Allstar/kobe/kobe start --input /yol/videolar --uret klip
```

Üçüncüsü Çağatay'ın tarif ettiği akıştır: *"Kobe'ye derim ki inputlar bunlar,
sen çıktı üret, gerisine karışma. LeBron'a derim ki Kobe'nin çıktısı geldikçe
oradan PNG üret. 7/24 çalışır."*

---

## 3. Kobe nasıl çalışır? (taslak)

### Genel akış

```
GİRDİ (video VEYA hazır kare dizini)
   │
   ├─ video ise: kapanış penceresini çıkar
   │    ffprobe → süre;  ss = süre - 600 sn
   │    ffmpeg -ss $ss -vf fps=2 -q:v 3  →  scratch/<id>/c_%05d.png
   │    (bu dizin KOBE'NİNDİR — iş bitince silinir)
   │
   ├─ kare dizini ise: doğrudan kullan
   │    (bu dizin KOBE'NİN DEĞİLDİR — asla silinmez, asla değiştirilmez)
   │
   ▼
KARAR MOTORU  src/motor.py :: tespit_v5
   │
   │  ① DİL YÖNLENDİRİCİ — son %20'den örnek kareler → Qwen Vision (Ollama)
   │     "hangi alfabe?" → en/ru/ar/... → OCR modeli seçilir
   │     (Ollama kapalıysa 'en'e düşer — skor bundan etkilenir, bkz. DURUM.md)
   │
   │  ② KUTU SİNYALİ  src/kutu.py — PaddleOCR *detection-only*
   │     Her karede metin kutusu var mı? Dilden bağımsız, ucuz.
   │     Sahne = 0-1 kutu · jenerik = sürdürülen ≥2 kutu
   │     → aday "kutu koşuları" (ardışık kutu-dolu pencereler)
   │
   │  ③ İÇERİK DOĞRULAMA  src/icerik.py — PaddleOCR *recognition*
   │     Aday karelerde GERÇEKTEN isim listesi mi var?
   │     Rol sözlüğü (core/lexicon/rol_tablosu) ile eşleşme.
   │     PAHALI — yalnız birkaç aday karede koşar, önbelleklenir.
   │     Ayraç budur: sahne tabelası kutu üretir ama İSİM LİSTESİ DEĞİLDİR.
   │
   │  ④ SEÇİM — son-çapa + scroll
   │     SON_ERISIM=0.82: aday, pencerenin son %18'ine ULAŞMALI.
   │     Ulaşmıyorsa kredi değildir — "ardından film devam ediyor" demektir.
   │     scroll: kayan jenerik mi, sabit kart mı (dy analizi)
   │
   │  ⑤ KURTARMA — hiçbir aday içerik eşiğini geçemezse
   │     Son çare: son %25'te ≥8 sn sürdürülen scroll+kutu → düşük güvenle kabul
   │
   ▼
KARAR: BULUNDU (kare no) │ KREDI_YOK │ ARIZA
   │
   ├─ (istenirse) ARTEFAKT ÜRET — onset'ten 10 sn ÖNCE, film sonuna kadar
   │    --uret kare → out/<id>/kareler/    (kaynaktan KOPYALANIR)
   │    --uret klip → out/<id>/klip/klip.mp4  (SESSİZ, -c:v copy)
   │
   ├─ kobe.json yaz (atomik: .tmp → os.replace)
   ├─ _TAMAM yaz  ← EN SON
   └─ scratch/<id>/ sil (yalnız kendi açtığını)
```

### Neden bu sıra?

**Ucuzdan pahalıya.** Kutu tespiti (det) her karede koşar ve ucuzdur; içerik
tanıma (rec) pahalıdır ve yalnız aday karelerde koşar. Tersi olsaydı bir film
dakikalar sürerdi.

**Kutu tek başına yetmez.** Konsey (GLM, 2026-07-21) tespiti: sahne tabelası
(BILLY saloon), ara yazı (MODERN Chaplin), gazete — hepsi kutu üretir ama
isim listesi değildir. Krediyi ayıran metin **içeriği**dir.

**Son-çapa şart.** Eski filmlerin ~%40'ı kapanış kredisiz. Güvenle "YOK"
diyebilmek için "krediler filmin sonuna kadar akar" değişmezine dayanılır.

---

## 4. Girdi ve çıktı sözleşmeleri

### GİRDİ

```python
@dataclass(frozen=True)
class Girdi:
    film_id: str                  # TEK kimlik, arşiv numarası
    video:   str | None = None    # MUTLAK yol — STANDART yol
    kareler: str | None = None    # MUTLAK yol — hazır kare dizini (alternatif)
    config:  dict = {}            # config.yaml'ı ezmek için
```

**`video` ve `kareler`'den TAM OLARAK biri verilir.** İkisi birden ya da
hiçbiri → `GirdiHatasi` → `ARIZA(sinif="GIRDI_HATASI")`. Kule sessizce bir
tarafı seçmez.

**`film_id` toplu modda nasıl türetilir** (tahmin yok, tek kural):
- Video modu → dosyanın **uzantısız adı**
- `--kareler` modu → **dizinin adı**
- Başka kimlik gerekiyorsa `tek --film-id` ile açıkça verilir

**Kare dosya adı sözleşmesi:** `c_%05d.png`. `motor._kare_no()` addaki son
sayıyı **mutlak kare numarası** olarak okur; klasörler `c_00001`'den
başlamayabilir.

### ÇIKTI — `out/<film_id>/kobe.json`

```json
{
  "film_id": "1925-1028-1-0000-90-1_POTEMKİN_ZIRHLISI",
  "durum": "BULUNDU",
  "baslangic_kare": 1133,
  "baslangic_sn": 566.5,
  "guven": 1.0,
  "script": "en",
  "uretilen": {"tip": "kare", "yol": "kareler", "adet": 88,
               "ilk_kare": 1113, "geri_pay_sn": 10},
  "kanit": {
    "kare_sayisi": 1200,
    "kare_fps": 2.0,
    "pencere_baslangic_sn": 0.0,
    "yontem": "kutu+scroll+içerik",
    "ocr_hata": 0
  },
  "motor_surumu": "kobe@0fb50f0e",
  "uretim_zamani": "2026-08-13T09:46:24+03:00",
  "sure_sn": 21.3
}
```

### `durum` — üç değer, DEĞİŞMEZ ayrım

| durum | Anlamı | Zorunlu alanlar |
|---|---|---|
| `BULUNDU` | Jenerik başlangıcı bulundu | `baslangic_kare`, `baslangic_sn`, `guven`, `script` |
| `KREDI_YOK` | Film gerçekten jeneriksiz — **içerik gerçeği** | — |
| `ARIZA` | Okuyamadık — **arıza gerçeği** | `sinif`, `mesaj` |

> ### En önemli değişmez
> **`ARIZA` asla `KREDI_YOK`'a dönüşmez.**
>
> Bu, bir aylık bir hastalığın panzehiridir: model EOL → "özet yok",
> CUDA OOM → "ses yok", çökme → "Latin". Geniş bir `except` arızayı içerik
> gerçeğine çevirdiği an aşağı akış kirlenir ve **kimse fark etmez.**
>
> Sözleşme bunu kodla zorlar: `ARIZA` `sinif`+`mesaj` olmadan yaratılamaz;
> `KREDI_YOK` arıza alanı **taşıyamaz** (`ValueError`).

### Arıza sınıfları

| sinif | Ne oldu |
|---|---|
| `GIRDI_HATASI` | video/kareler XOR ihlali, geçersiz `--uret`, klip için video yok |
| `KARE_CIKARIM` | ffprobe/ffmpeg patladı, kare çıkmadı |
| `MOTOR` | `tespit_v5` istisna attı (OCR çöktü, model yok, OOM) |
| `URETIM_KARE` / `URETIM_KLIP` | Karar doğru ama artefakt üretilemedi |

### ARTEFAKT (isteğe bağlı) — `--uret kare|klip`

| | Kare havuzu | Sessiz klip |
|---|---|---|
| Yol | `out/<id>/kareler/` | `out/<id>/klip/klip.mp4` |
| Başlangıç | onset − 10 sn (= 20 kare @ fps 2) | onset − 10 sn |
| Bitiş | Kaynağın sonu | Filmin sonu |
| Nasıl | Kaynaktan **kopyalanır** (taşınmaz) | `-c:v copy -an -f mp4` |
| Ses | — | **YOK** (`-an`) |

**Yalnız `BULUNDU` durumunda üretilir.** `KREDI_YOK`'ta kesecek bir şey,
`ARIZA`'da güvenilecek bir onset yoktur — sözleşme bunu `ValueError` ile
engeller.

**Klip keyframe'e geri yaslanır.** `-ss` girdi tarafında olduğu için ffmpeg en
yakın anahtar kareye **geri** gider. Kayma daima erken yöndedir ve 10 sn payın
içindedir — üretim asimetrisiyle uyumlu (erken zararsız, geç cast kaybettirir).

---

## 5. İç yapı

```
Allstar/kobe/
├─ kobe                    ← GİRİŞ NOKTASI (3 satır: kendi venv'ini bulur)
├─ main.py                 ← CLI + koşu akışı + artefakt üretimi
├─ sozlesme.py             ← Girdi / Cikti / ariza  (kulenin DIŞ yüzü)
├─ config.yaml             ← eşikler ve bayraklar
│
├─ src/                    ← KARAR MOTORU (dış dünyayı bilmez)
│  ├─ motor.py    1325 s.  ← tespit_v5 — karar mantığı
│  ├─ kutu.py      145 s.  ← Paddle det, kutu sinyali (dilden bağımsız)
│  └─ icerik.py    616 s.  ← isim/rol analizi, çok-dil OCR
│
├─ venv/                   ← KENDİ PADDLE'I (11 GB, 167 pin)
├─ venv_kur.sh             ← sıfırdan kurulum tarifi
├─ gereksinimler.txt       ← tam sürüm pinleri (BUDANMAZ, bkz. §6)
│
├─ olcum/                  ← ÖLÇÜM YATAĞI
│  ├─ olc_pool.py          ← 110 film × GT karşılaştırması
│  ├─ hata_atlasi.py       ← hataların kanıt atlası
│  ├─ v5_izleme.py         ← koşular-arası kayma + şüphe kuyruğu
│  └─ veri/                ← GT (dogrulama_sonuc.json), ölçüm kayıtları
│
├─ havuz/                  ← 120 film × kapanış kareleri (28 GB, git'te değil)
├─ tests/                  ← 51 test (motor + sözleşme + akış + üretim)
├─ golden/                 ← tek-film karar demiri (hızlı kanarya)
├─ raporlar/               ← ölçüm kayıtları + geri-dönüş noktası
│
├─ out/                    ← ÜRETİLEN VERİ = KUYRUK  (git'te değil)
├─ scratch/                ← geçici kareler, iş bitince silinir (git'te değil)
└─ logs/                   ← koşu günlükleri (git'te değil)
```

### Katman kuralı — tek yönlü bağımlılık

```
kobe → main.py → sozlesme.py
                      ↑
         main.py → src/motor.py → src/kutu.py
                                → src/icerik.py → core/lexicon/rol_tablosu
```

**`src/` sözleşmeyi BİLMEZ.** Motor kendi tiplerini (`Sonuc`) döndürür;
`Cikti`'ya çeviri yalnız `main.py`'de yapılır. Böylece motorun iç tipleri
dışarı sızmaz ve sözleşme motora dokunmadan değişebilir.

### Kule sınırı

| İÇERİ | DIŞARI (zemin) | YASAK |
|---|---|---|
| Kod, üretilen veri, sözleşme, **kendi venv'i** | Python/CUDA ikilileri, model ağırlıkları, `core/lexicon/` gibi paylaşılan salt-okunur sözlükler | Başka bir kulenin **ÜRETTİĞİ** veriyi doğrudan okumak |

`core/lexicon/rol_tablosu` bilerek dışarıdadır: kopyalanırsa sözlük çatallanır
ve okuyucuya eklenen bir rol Kobe'ye ulaşmaz.

### Kule dışında kalan tek bağ

`scripts/_jenerik_pool.py` — **çağıran/orkestratör.** Kobe'yi sözleşmeden
çağırır. Kulenin içine alınamaz: kule kendi tüketicisini içine alırsa
bağımsızlık biter.

---

## 6. Doğrulama ve bilinen sınırlar

### Skor — 110 film, insan-doğrulanmış GT

| Ölçüt | Değer | Kırmızı çizgi |
|---|---|---|
| Genel | **104/110 = %94.5** | ≥104 |
| Üretim (asimetrik) | **107/110 = %97.3** | ≥107 |
| Kredi-VAR | 75/81 | — |
| **Kredi-YOK reddi** | **29/29** | **≥29/30** |

Üretim ölçütü: erken ≤120 kare OK, geç ≤20 kare OK.

```bash
systemctl is-active ollama          # 'inactive' OLMALI
cd Allstar/kobe/olcum && ../venv/bin/python olc_pool.py --paralel 8
```

### Bilinen 6 hata (dar-VLM sınıfı)

`YALNIZ_SAVAŞÇI` −190 · `HARİKA_KÖPEK_5` −124 (film-içi ekran metni yapışması)
· `İNİŞLİ_ÇIKIŞLI` +89 (okunamayan kaligrafi) · `İKİ_KAFADAR` / `KIZIL_HAYAT`
/ `TESS` (üretim ölçütünde doğru). Çözüm yolu: dar-VLM — ayrı proje.

### Ölçüm ortamı sabiti — dikkat

`ollama.service` **kapalı** olmalı. Kobe'nin dil yönlendiricisi ona HTTP ile
bağlanır; erişilemezse her film için `'en'` döner. Yukarıdaki %94.5
**yönlendirici devre dışıyken** ölçülmüş bir sayıdır. Ollama açıkken skor
~%93.6'dır (Farsça film doğru okunur, onset 28 kare erkene kayar —
asimetri politikasının içinde, üretim skoru düşmez).

### Pahalı ders — çalışma zamanı budanmaz

`gereksinimler.txt` **167 pin** içerir ve elle kısaltılamaz.

Kuleye kendi venv'i kurulurken `venvs/ocr`'dan **elle seçilmiş 16 paketlik**
bir liste kullanıldı. Ölçüm **%94.5 → %92.7** düştü: iki film doğru →
`KREDI_YOK` oldu. Bu olurken **altı kilit paket birebir aynıydı** (paddle
3.3.1 / CUDA 12.6 / cuDNN 9.5.1 / aynı commit, paddleocr 3.7.0, paddlex 3.7.2,
numpy, pillow, opencv). Det önbelleği, model ağırlıkları ve ölçümün
tekrarlanabilirliği de tek tek elendi. Eksik 76 paket kurulunca skor **tam
olarak** geri geldi.

> **Kobe'nin çıktısı, kodunun HİÇ import etmediği paketlere bağlı.**
> `motor`/`kutu`/`icerik` hiçbiri torch, sklearn, easyocr, timm veya
> transformers'a dokunmaz — ama onlarsız yanlış cevap verir.
> "Hangi paket önemli" **tahmin edilmez**; ortam bütün olarak dondurulur.

### Şüphe katmanı (davranış-nötr görünürlük)

Kobe tespit edemese bile şüpheyi raporlar: `gec_riski` (önünde okunamayan blok
— cast başı kayıp olabilir), `erken_riski` (koşu başı footage olabilir),
`parcalanma_riski` (seyrek kart). Karar dallarını **etkilemez**, yalnız insan
kuyruğuna düşer (`olcum/v5_izleme.py`).

---

## 7. GİRİŞ JENERİĞİ — Kobe'nin yetkisi var mı?

**HAYIR. Ve bu bir eksiklik değil, yapısal bir sınırdır.**

### Kanıt

**① Motorun temel ayracı kapanışa özgü.** `src/motor.py:814-816`:

```
# ardından FİLM DEVAM EDER. Aday sonu son %18'e ulaşmıyorsa kredi değildir.
SON_ERISIM = 0.82
```

Bu kural, jeneriği sahne yazısından ayıran ana testtir: *gerçek kapanış
kredisi pencerenin sonuna kadar akar.* **Giriş jeneriğinde bu tam tersidir** —
giriş jeneriğinden sonra film HER ZAMAN devam eder. `tespit_v5` giriş
karelerine doğrultulursa neredeyse her filme `KREDI_YOK` der: emin, sessiz ve
sistematik olarak yanlış.

**② Kurtarma yolu da sona çapalı.** `motor.py:378` — *"filmin son %25'inde
≥8 sn sürdürülen scroll+kutu"*.

**③ Ölçüm yatağında giriş verisi YOK.** `olcum/veri/havuz_kur.sh` →
`TAIL_S=600`: yalnız son 10 dakika çıkarılmış. 120 film klasörünün hiçbirinde
film başı yok.

**④ Doğrulanmış giriş verisi YOK.** GT alanları: `film`, `yil`, `v5_tahmin`,
`karar`, `gercek_onset`, `aciklama`. **Tek bir onset** — kapanış onset'i.
Giriş için hiçbir insan doğrulaması yapılmamış.

**⑤ Giriş bugün başka motorda.** `core/pipelines/ocr/jenerik_detector.py`
(`prefer="first"`) + `scripts/giris_jenerik_havuzu.py`. Bunlar Kobe'nin
"KOBE OLMAYANLAR" listesindedir.

### Sonuç ve öneri

Kobe'ye `--bolum giris` eklemek **kolaydır ve yanlıştır.** Motoru giriş
karelerine doğrultmak, bu kulenin var oluş sebebi olan sessiz-bozulmayı
elleriyle geri getirmek olur: ölçülmemiş, doğrulanmamış, yapısal olarak ters
bir kararı "başarı" gibi raporlamak.

**Doğru yol üç adımdır — ve ilki koddan önce gelir:**

| Adım | İş | Neden önce bu |
|---|---|---|
| 1 | **Giriş GT'si kur** — N film × insan-doğrulanmış giriş jeneriği sınırları | Ölçüm yatağı olmadan yazılan motor, doğru mu yanlış mı bilinmez (`eval-harness-first`) |
| 2 | **Giriş penceresi çıkarımı** — `TAIL_S` yerine `HEAD_S`, film başından | Yatağın girdisi |
| 3 | **Giriş karar mantığı** — "krediler nerede BİTER" sorusu; `SON_ERISIM` yerine "ilk sürdürülen kutu bloğu + film başlangıcı" | Kapanış mantığı kopyalanamaz, tersidir |

### Ama çıktı yapısı ŞİMDİDEN ikiye ayrılmalı

Bu doğru ve ucuz. Tüketici kuleler (LeBron/Nash) daha kurulmadan yapıyı
ayırmak, sonradan kırıcı değişiklik yapmaktan çok daha ucuz:

```
out/<film_id>/
├─ cikis/                 ← BUGÜN çalışan (kapanış jeneriği)
│  ├─ kobe.json
│  ├─ _TAMAM
│  ├─ kareler/   veya
│  └─ klip/klip.mp4
└─ giris/                 ← YARIN (giriş jeneriği) — bugün ARIZA döner
   └─ kobe.json           ← durum=ARIZA, sinif=BOLUM_HAZIR_DEGIL
```

`--bolum giris` istenirse Kobe **açıkça** `ARIZA(BOLUM_HAZIR_DEGIL)` döner —
tahmin etmez, boş klasör bırakmaz, sessizce atlamaz. Eksik **görünür** olur.

---

## 8. Hızlı başvuru

```bash
# Karar
kobe tek --video film.mp4 --film-id ID
kobe tek --kareler /yol/frames --film-id ID

# Karar + artefakt
kobe tek --video film.mp4 --film-id ID --uret klip
kobe tek --kareler /yol/frames --film-id ID --uret kare

# Toplu kuyruk (idempotent)
kobe start --input /yol/videolar --uret klip

# Ölçüm (~140 sn)
cd olcum && ../venv/bin/python olc_pool.py --paralel 8

# Hızlı kanarya (saniyeler)
cat golden/BENIOKU.md

# Çalışma zamanını yeniden kur
./venv_kur.sh --temiz

# Testler
venv/bin/python -m pytest tests -q
```

| Belge | Ne için |
|---|---|
| `KATALOG.md` | **bu belge** — ne, neden, nasıl |
| `README.md` | günlük kullanım |
| `CHANGELOG.md` | ne zaman ne değişti |
| `DURUM.md` | canlı durum, oturumlar arası süreklilik |
| `golden/BENIOKU.md` | karar demiri, hızlı doğrulama |
