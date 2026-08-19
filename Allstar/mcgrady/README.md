# McGrady — künye kimlik/doğrulama kulesi (QC2)

> Eski pipeline'daki QC2 katmanının (scripts/credit_qc_gates +
> tek_film_kunye QC2 bloğu) bağımsız yeni evi. Kimliği kilitler, doğrular,
> ÖNERİR — künye verisini ASLA ezmez (OCR-otorite + deferans).
> (MAP.md'deki planlı `qc2_sixers` kod adının gerçekleşmesidir.)
> **Tamamlandı (2026-08-18):** gerçek-zemin kanarya DOGRULANDI + afiş portre
> kapısından geçti; 36/36 test.

## Sorumluluk sınırı

**Yapar:** bir künye adayı paketini (başlık/yıl/OCR cast-yönetmen-yapımcı)
KB (Wikidata+IMDb duckdb, zemin salt-okunur) ile çapraz-doğrular; kilitlenemezse
yönetmen-çapası (KB) ve TMDB-çapası ile kimlik kurmayı dener (internet kendi
çıkışından); kanonikleştirme/garble/yönetmen ÖNERİLERİ ve afiş üretir; kararını
kendi `out/`'una yazar.

**Yapmaz:** künye PDF'i yazmaz, cast/yönetmen verisini EZMEZ/doldurmaz (yalnız
öneri üretir — tüketici uygular), jenerik okumaz, künye üretmez, sheriff'e
kayıt yaptırmaz (entegrasyon ayrı iş).

## Çalıştırma

Kule kendi çalışma zamanını kendi bulur:

```bash
# TEK film
Allstar/mcgrady/mcgrady tek --girdi in/paket.json --film-id 2025-1307-1-0000-50-0

# TOPLU — in/ altındaki her *.json; _TAMAM olanı atlar
Allstar/mcgrady/mcgrady start --input in/
```

Çıktı daima `out/<film_id>/mcgrady.json` + `_TAMAM` (atomik yazım; `_TAMAM`
yalnız yazım bariyeridir, başarı hükmü değildir — tüketici JSON'a bakar).

## Girdi paketi (`mcgrady.girdi/v1`)

```json
{"schema_version": "mcgrady.girdi/v1", "film_id": "...", "profile": "film",
 "baslik": {"tr": "AHLAT AĞACI", "orijinal": "The Wild Pear Tree", "yil": 2018},
 "yonetmen": ["Nuri Bilge Ceylan"], "cast": ["Doğu Demirkol", "Murat Cemcir"],
 "yapimci": [], "script": "tr"}
```

Örnek: `in/ornek_paket.json`.

## Sözleşme

| durum | Anlam |
|---|---|
| `DOGRULANDI` | Kimlik kilitlendi (cast-örtüşme ya da çapa) — `kimlik` bloğu dolu |
| `KILITLENEMEDI` | Çapalar kilitlenemedi → tüketiciye KONTROL sinyali (yanlış>boş) |
| `ARIZA` | Koşu arızası — `sinif`+`mesaj` zorunlu. **ARIZA asla KILITLENEMEDI'ye dönüşmez** |

`mcgrady.json` içerik blokları: `kimlik` {method, imdb_id, tmdb_id, kaynak_izi,
cast_ortusme, versiyon_teyitli} · `oneriler` [{alan, ocr, kanonik, kaynak}] —
EZME YOK, tüketici uygular · `yonetmen` {ocr, karar, kaynak, kontrol_onerisi} ·
`web_oneri` (TMDB cast'i yalnız ÖNERİ) · `garble` (imza-yokluğu — SİLME YOK) ·
`afis` (poster_ok kapısı: >5KB + portre w<h) · `karar_onerileri` (KONTROL
sebepleri — tüketici uygular).

Sheriff kimlik env'leri (`MITAS_SHERIFF_RUN_ID/TASK_ID/ATTEMPT_ID`) set edilmişse
çıktıya `mitas.boundary/v1` kimlik bloğu eklenir (kobe kalıbı).

## Dizi politikası

`profile=dizi` paketlerinde internet katmanı (çapalar) **bilerek atlanır**:
dizi/bölüm kimliği TRT kataloğundan gelir, cast TRT XML'inde mevcuttur, teknik
ekip internette yok — dış-bağımlılık sıfır (2026-08-18 kararı).

## Zemin (salt-okunur paylaşım — MAP.md kuralı)

| Ne | Yol | Bağ |
|---|---|---|
| Wikidata KB | `/opt/mitas/cache/duckdb/mitas.duckdb` (19G) | config.yaml → `MITAS_WIKIDATA_DUCKDB` |
| IMDb KB | `/opt/mitas/cache/duckdb/imdb.duckdb` (12G) | config.yaml → `MITAS_IMDB_DUCKDB` |
| TMDB anahtarı | — | env `MITAS_TMDB`/`TMDB_API_KEY` (internet gerekiyorsa kule çıkışından) |

Model ağırlığı kategorisi: kopya YOK — merkezi güncellenen DB kuleye böyle ulaşır.

## Yerleşim

| Ne | Yol |
|---|---|
| Motor (orkestrasyon) | `src/motor.py` |
| Sözleşme (paket_oku/Cikti/ariza) | `sozlesme.py` |
| KB çapraz-kontrol (kule kopyası) | `src/credit_crosscheck.py` |
| QC2 graft'ları (kule kopyası) | `src/credit_qc_gates.py` |
| Afiş indirici (kule kopyası) | `src/poster_fetch.py` |
| Garble dedektörü (söküm) | `src/garble.py` |
| Web önbelleği (kule kopyası) | `src/web_cache.py` (kule-içi cache/web) |
| Sabit sorgular | `src/sql/sorgular.sql` |
| Çalışma zamanı | `venv/`, `venv_kur.sh`, `gereksinimler.txt` (duckdb/pillow/PyYAML/pytest — venvs/ocr pin'leri) |

## Testler

```bash
cd Allstar/mcgrady && ./venv/bin/python -m pytest tests/ -q   # 36 passed
```

Motor testleri KB/web'i fake'ler (internet ve duckdb GEREKTİRMEZ).

## Çift-kopya dönemi (söküm şartı)

scripts/ içindeki eski QC2 **yerinde kalır**; üretim `MITAS_QC2=1` ile değişmez.
Kule gölgedir. Söküm (eski bloğun kaldırılması) pipeline McGrady'ye bağlanınca
AYRI iş olarak yapılır. Kule kopyaları drift ederse referans: scripts/
orijinalleri + bu klasörün DURUM.md'sindeki fark listesi.
