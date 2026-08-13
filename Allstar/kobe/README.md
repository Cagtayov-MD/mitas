# Kobe — jenerik başlangıç tespit kulesi

> Film **SONU** jeneriğinin başladığı kareyi bulur. Projede jenerik-başlangıç
> bulma işi SADECE Kobe'dir. (Eski adı FIGO'ydu; 2026-08-13'te tek isme indi.)

## Sorumluluk sınırı

**Yapar:** bir filmin kapanış jeneriğinin başladığı kareyi bulur, kararını
kendi `out/`'una yazar.

**Yapmaz:** kare havuzu kurmaz, master PNG üretmez, künye okumaz, isim
düzeltmez, PDF yazmaz, Database'e künye yazmaz. Hepsi başka kulelerin işi.

## Çalıştırma

Kule kendi çalışma zamanını kendi bulur — çağıran hangi python'la koşulacağını
bilmez:

```bash
# TEK film — hazır kare dizini
Allstar/kobe/kobe tek --kareler /yol/frames/cikis --film-id 2025-1307-1-0000-50-0

# TEK film — video (kapanış penceresini kendi çıkarır, sonra siler)
Allstar/kobe/kobe tek --video /yol/film.mp4 --film-id 2025-1307-1-0000-50-0

# TOPLU — kaldığı yerden devam eder, _TAMAM olanı atlar
Allstar/kobe/kobe start --input /yol/videolar
Allstar/kobe/kobe start --input /yol/kare_dizinleri --kareler
```

Çıktı daima `Allstar/kobe/out/<film_id>/kobe.json` + `_TAMAM`. Çağıran çıktı
yolunu seçmez — kule kendi evine yazar.

### Talebe göre artefakt üretimi

Kobe varsayılan olarak **yalnız kararı** üretir. İstenirse iki artefakttan
birini de kendi klasörüne koyar:

```bash
kobe tek --kareler <dizin> --film-id <id> --uret kare   # kare havuzu
kobe tek --video   <film>  --film-id <id> --uret klip   # SESSİZ mp4
kobe start --input /yol/videolar --uret klip            # toplu
```

```
out/<film_id>/
├─ kobe.json          # karar + üretilen artefaktın künyesi
├─ _TAMAM             # EN SON yazılır — varsa artefakt da hazırdır
├─ kareler/           # --uret kare  → c_01113.png … c_01200.png
└─ klip/klip.mp4      # --uret klip  → sessiz, filmin sonuna kadar
```

| | |
|---|---|
| **Başlangıç** | İkisi de onset'ten **10 sn ÖNCE** başlar (`config.yaml: geri_pay_sn`). Aynı jeneriğin iki temsili farklı yerden başlarsa kıyas bozulur |
| **Bitiş** | Filmin sonu — jenerik sona kadar akar |
| **Klip** | Ses akışı **yok** (`-an`). `-c:v copy` — yeniden kodlamaz; `-ss` girdi tarafında olduğu için en yakın keyframe'e **geri** yaslanır (kayma daima erken yönde, 10 sn payın içinde) |
| **Kare havuzu** | Kaynak dizinden **kopyalanır**, taşınmaz — Kobe kendi yaratmadığına dokunmaz. Dosya adları korunur (`_kare_no` mutlak numarayı addan okur) |
| **`--uret klip` + `--kareler`** | `ARIZA(GIRDI_HATASI)` — kare dizininden klip kesilemez, sessizce atlanmaz |
| **`KREDI_YOK` / `ARIZA`** | Artefakt üretilmez; kesecek bir şey yoktur. Sözleşme bunu zorlar |

`kobe.json` içindeki künye:

```json
"uretilen": {"tip": "klip", "yol": "klip/klip.mp4", "baslangic_sn": 5335.5,
             "sessiz": true, "geri_pay_sn": 10, "boyut_bayt": 19535204}
"uretilen": {"tip": "kare", "yol": "kareler", "adet": 88,
             "ilk_kare": 1113, "geri_pay_sn": 10}
```

## Sözleşme

`durum` üç değer alır ve bu ayrım **değişmezdir**:

| durum | Anlamı |
|---|---|
| `BULUNDU` | Jenerik başlangıcı bulundu (`baslangic_kare`, `baslangic_sn`, `guven`, `script`) |
| `KREDI_YOK` | Film gerçekten jeneriksiz — **içerik gerçeği** |
| `ARIZA` | Okuyamadık: video bozuk, ffmpeg patladı, OCR çöktü. **Arıza gerçeği.** `sinif` + `mesaj` zorunlu |

> **`ARIZA` asla `KREDI_YOK`'a dönüşmez.** Geniş `except` arızayı içerik
> gerçeğine çevirdiği an aşağı akış kirlenir. Kobe'de bu kapı kapalı.

Tüketici kuralı: **`_TAMAM` yoksa dosya yok sayılır.** Kuyruk klasörün kendisi
olduğu için tüketici Kobe yazarken okuyabilir; `os.replace` yarım dosya
okunmasını, `_TAMAM` "yazılıyor mu bitti mi" belirsizliğini kapatır.

## Yerleşim

| Ne | Yol |
|---|---|
| **Karar motoru** (`tespit_v5`) | `src/motor.py` |
| Kutu sinyali (Paddle det, dilden bağımsız) | `src/kutu.py` |
| İçerik analizi (isim/rol, çok-dil) | `src/icerik.py` |
| Sözleşme (`Girdi`/`Cikti`/`ariza`) | `sozlesme.py` |
| CLI + koşu akışı | `main.py`, `kobe` |
| Ölçüm yatağı + GT | `olcum/` |
| Çalışma zamanı (kendi Paddle'ı) | `venv/`, `venv_kur.sh`, `gereksinimler.txt` |
| **Pipeline bağlantısı** (orkestratör, kule DIŞI) | `/opt/mitas/scripts/_jenerik_pool.py` |

## Skor (110 film, insan-doğrulanmış GT)

**%94.5 genel · %97.3 üretim · kredisiz-red 29/29.** Üretim ölçütü asimetrik:
erken ≤120 kare OK, geç ≤20 (erken zararsız, geç cast kaybettirir).

```bash
systemctl is-active ollama          # 'inactive' OLMALI — açıksa skor ~%93.6
cd /opt/mitas/Allstar/kobe/olcum && ../venv/bin/python olc_pool.py --paralel 8
# KIRMIZI ÇİZGİ: kredi-yok >= 29/30; genel >= 104; üretim >= 107
# DİKKAT: --film modu olcum_son.json'u EZER — kullanma.
# GPU şart (paddle CPU'da PIR hatası verir).
```

Hızlı kanarya (tek film, saniyeler): `golden/BENIOKU.md`.

## Çalışma zamanı — paket çıkarma

`gereksinimler.txt` 167 pin içerir ve **elle budanmaz**. Kobe'nin çıktısı,
kodunun hiç import etmediği paketlere bağlı: 16 paketlik seçilmiş bir liste
denendi, skor %92.7'ye düştü (iki film doğru→`KREDI_YOK`), altı kilit paket
birebir aynı olduğu halde. Paket çıkarmadan önce 110 filmlik ölçümü koş.

Yeniden kurmak: `./venv_kur.sh` (veya sıfırdan: `./venv_kur.sh --temiz`).

## Üretim zinciri

```
systemd mitas-asr → scripts/mitas_pipeline.py → scripts/_jenerik_pool.py
  → motor.tespit_v5(frames/cikis)  [MITAS_JENERIK_V5=1]
  → start_pos (güvenlik payı MITAS_JENERIK_V5_PAD=10 kare erken)
  → Database/<film>/frames/cikis_jenerik havuzu + jenerik_detection.json
```

Kobe `kredi_yok` derse havuz BOŞ kalır (`MITAS_JENERIK_METIN_KAPI=1` —
kredisizde eski CV devralmaz, sahte cast biter); son %15'te det-metin varsa
`review_kredi_yok` → insan kuyruğu (`olcum/v5_izleme.py`).

## Bayraklar (mitas.env)

| Bayrak | Değer | Ne |
|---|---|---|
| `MITAS_JENERIK_V5` | 1 | Kobe birincil motor |
| `MITAS_JENERIK_V5_PAD` | 10 | güvenlik payı (kare, erken tarafa) |
| `MITAS_JENERIK_METIN_KAPI` | 1 | kredisizde Kobe son söz (CV devralmaz) |
| `MITAS_JENERIK_SUPHE_GENIS_HAVUZ` | kapalı | `gec_riski` şüphesinde havuzu elenen-aday başından doldur (aç: =1) |

## Şüphe katmanı (görünürlük)

Kobe tespit edemese bile ŞÜPHEYİ raporlar (`Sonuc.suphe` → manifest `v5.suphe`
→ `olcum/v5_izleme.py` ŞÜPHE KUYRUĞU): `gec_riski` (önünde okunamayan blok —
cast başı kayıp olabilir), `erken_riski` (koşu başı footage olabilir),
`parcalanma_riski` (seyrek-kart). Bilinen sınırlar: HARİKA-tipi footage
markaları `erken_riski`'yle yakalanamıyor; KNUTE `gec_riski`'nde bilinen
yanlış-pozitif (zararsız — davranış değişmez, sadece insan bakar).

## KOBE OLMAYANLAR (karışıklık olmasın)

- `core/pipelines/ocr/jenerik_frame_pool_detector.py` — eski CV motoru;
  GİRİŞ-jeneriği havuzunun (`giris_jenerik_havuzu.py`) ve Kobe-HATA
  fail-safe'inin bağımlılığı olarak yaşıyor. Kapanış-onset işi YAPMAZ.
- `jenerik_oneocr_detector.py` — giriş-havuzu primitifleri. Onset işi yapmaz.
- `_jenerik_detect.py` / `_credit_detect.py` — jenerik SINIR tespiti (hangi
  saniyelerden kare çıkarılacağı); Kobe'nin GİRDİSİNİ hazırlar, onset bulmaz.

## Bilinen kalan hatalar (6/110 — dar-VLM sınıfı)

YALNIZ_SAVAŞÇI -190, HARİKA -124 (film-içi ekran-metni yapışması), İNİŞLİ +89
(okunamayan kaligrafi — artık `gec_riski` ile GÖRÜNÜR); İKİ_KAFADAR/KIZIL/TESS
üretim ölçütünde doğru. Çözüm yolu: dar-VLM (ayrı proje). Ayrıntı:
`docs/GUNLUK.md` 2026-07-29/30 kayıtları.
