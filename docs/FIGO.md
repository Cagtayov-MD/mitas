# FIGO — MITAS Jenerik Başlangıç Tespit Motoru

> Resmi ad: **FIGO** (Çağatay, 2026-07-30). Film SONU jeneriğinin başladığı
> kareyi bulur. Projede jenerik-başlangıç bulma işi SADECE FIGO'dur.

## Konum (path)

| Ne | Path |
|---|---|
| **Ana motor** (karar: `tespit_v5`) | `/opt/mitas/harness/kunye_kiyas/figo.py` |
| Kutu sinyali (Paddle det, dilden bağımsız) | `/opt/mitas/harness/kunye_kiyas/credit_box.py` |
| İçerik analizi (isim/rol, çok-dil) | `/opt/mitas/harness/kunye_kiyas/credit_content.py` |
| **Pipeline bağlantısı** (orkestratör) | `/opt/mitas/scripts/_jenerik_pool.py` |

## Üretim zinciri

```
systemd mitas-asr → scripts/mitas_pipeline.py → scripts/_jenerik_pool.py
  → figo.tespit_v5(frames/cikis)  [MITAS_JENERIK_V5=1]
  → start_pos (güvenlik payı MITAS_JENERIK_V5_PAD=10 kare erken)
  → Database/<film>/frames/cikis_jenerik havuzu + jenerik_detection.json
```

FIGO `kredi_yok` derse: havuz BOŞ kalır (`MITAS_JENERIK_METIN_KAPI=1` —
kredisizde eski CV devralmaz, sahte cast biter); son %15'te det-metin varsa
`review_kredi_yok` → insan kuyruğu (`v5_izleme.py`). FIGO HATA verirse
(exception): eski CV'ye fail-safe düşüş (nadir).

## Skor (110-film insan-doğrulanmış GT)

**%94.5 genel · %97.3 üretim · kredisiz-red 29/29** (baseline:
`veri/olcum_BASELINE_9455.json`). Üretim ölçütü: erken ≤120 kare OK, geç ≤20
(asimetri politikası: erken zararsız, geç cast kaybettirir).

## Ölçüm / regresyon

```bash
cd /opt/mitas/harness/kunye_kiyas && \
  CUDA_VISIBLE_DEVICES=0 /opt/mitas/venvs/ocr/bin/python olc_pool.py --paralel 8 2>/dev/null
# KIRMIZI ÇİZGİ: kredi-yok >= 29/30; genel >= 104; üretim >= 107
# DİKKAT: --film modu olcum_son.json'u EZER — kullanma.
# GPU şart (paddle CPU'da PIR hatası verir). Kabuktan: source mitas.env.
```

## Bayraklar (mitas.env)

| Bayrak | Değer | Ne |
|---|---|---|
| `MITAS_JENERIK_V5` | 1 | FIGO birincil motor |
| `MITAS_JENERIK_V5_PAD` | 10 | güvenlik payı (kare, erken tarafa) |
| `MITAS_JENERIK_METIN_KAPI` | 1 | kredisizde FIGO son söz (CV devralmaz) |
| `MITAS_JENERIK_SUPHE_GENIS_HAVUZ` | kapalı | `gec_riski` şüphesinde havuzu elenen-aday başından doldur (aç: =1) |

## Şüphe katmanı (görünürlük)

FIGO tespit edemese bile ŞÜPHEYİ raporlar (`Sonuc.suphe` → manifest `v5.suphe`
→ `v5_izleme.py` ŞÜPHE KUYRUĞU): `gec_riski` (önünde okunamayan blok — cast
başı kayıp olabilir), `erken_riski` (koşu başı footage olabilir),
`parcalanma_riski` (seyrek-kart). Bilinen sınırlar: HARİKA-tipi footage
markaları erken_riski'yle yakalanamıyor; KNUTE gec_riski'nde bilinen
yanlış-pozitif (zararsız — davranış değişmez, sadece insan bakar).

## FIGO OLMAYANLAR (karışıklık olmasın)

- `core/pipelines/ocr/jenerik_frame_pool_detector.py` — eski CV motoru;
  GİRİŞ-jeneriği havuzunun (`giris_jenerik_havuzu.py`) ve FIGO-HATA
  fail-safe'inin bağımlılığı olarak yaşıyor. Kapanış-onset işi YAPMAZ.
- `jenerik_oneocr_detector.py` — giriş-havuzu primitifleri (Linux'ta Paddle
  wrapper'la). Onset işi yapmaz.
- `_jenerik_detect.py` / `_credit_detect.py` — jenerik SINIR tespiti (hangi
  saniyelerden kare çıkarılacağı); FIGO'nun GİRDİSİNİ hazırlar, onset bulmaz.

## Bilinen kalan hatalar (6/110 — dar-VLM sınıfı)

YALNIZ_SAVAŞÇI -190, HARİKA -124 (film-içi ekran-metni yapışması), İNİŞLİ +89
(okunamayan kaligrafi — artık `gec_riski` ile GÖRÜNÜR); İKİ_KAFADAR/KIZIL/TESS
üretim ölçütünde doğru. Çözüm yolu: dar-VLM (ayrı proje). Ayrıntı:
`docs/GUNLUK.md` 2026-07-29/30 kayıtları.
