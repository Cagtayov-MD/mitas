# JORDAN KATALOĞU

> Sürüm: 2026-08-17 · Kule: `Allstar/jordan/`

## 1. Neden var?

Jordan, Kobe'nin belirlediği jenerik klibini frame tabanlı bir VLM okuyucuyla
okur. LeBron/Magic master-PNG, Nash kendi kare havuzu yoludur; Jordan ise
klibi kendi içinde standart karelere ayırıp multi-image olarak okuyan bağımsız
kanaldır.

Kule router değildir. Jenerik sınırı bulmaz, isim düzeltmez, harici isim
veritabanı sorgulamaz ve Shaq uzlaştırma kararını vermez.

## 2. Dış sözleşme

Girdi:

```python
Girdi(
    film_id="film_001",
    video="/mutlak/yol/jenerik.mp4",
    bolum="giris" | "cikis",
    config={},
)
```

Dış sözleşmede video kalması, modelin video modunda çalıştığı anlamına
gelmez. Video yalnız ffmpeg kare üretiminin kaynağıdır. `src/model.py`
native-video girdi kabul etmez.

Çıktı:

```text
out/<film_id>/<bolum>/
├─ jordan.json
├─ jordan.txt
└─ _TAMAM
```

Durumlar `OKUNDU`, `METIN_YOK`, `ARIZA`'dır. Atomik JSON/TXT yazımından
sonra `_TAMAM` oluşturulur. `ARIZA` içerik yokluğu gibi sunulamaz.

## 3. İç akış

```text
Kobe/Sheriff jenerik klibi
  │
  ├─ ffmpeg tek geçiş
  │    fps=2, scale=720:-2:flags=lanczos, JPEG q=2
  │
  ├─ kare manifesti
  │    sıra + kaynak_sn + SHA-256 + genişlik/yükseklik
  │
  ├─ sabit gruplama
  │    varsayılan 8 resim, bindirme 0, son grup kısa olabilir
  │
  ├─ Qwen-VL multi-image çağrısı
  │    image + image + ... + prompt
  │
  ├─ kayıpsız tanı
  │    ham grup cevapları + hash + model bölüm etiketleri
  │
  └─ deterministik kredi görünümü
       yalnız case/whitespace-normalize kesin tekrar elenir
```

Model isteminde `[CREDITS]` ve `[SUBTITLES]` ayrımı vardır. Protokol
başlıkları ve altyazıya ayrılan satırlar kredi görünümüne girmez; neyin
neden ayrıldığı `derleyicide_elenen` listesinde, cevabın tamamı ise
`ham_metin` alanında kalır. Modelin bölümleme hatası böylece gizlenmez.

## 4. Model reçetesi

Varsayılan:

| Alan | Değer |
|---|---|
| Model | `model/qwen2.5-vl-7b` |
| Ağırlık/hesap | FP16 |
| Besleme | ayrı image listesi; native video yok |
| Kare | 2 fps, 720 px, düz Lanczos, JPEG q=2 |
| Grup | 8 kare, bindirme 0 |
| Piksel bütçesi | `256·28²` – `1280·28²` |
| Üretim | greedy, max 1024, repetition 1.05, no-repeat-ngram 3 |

Bu seçim KSK/28-klip ölçümünden gelir. 2.5-VL kolu 28/28 dolu
sonuç ve mevcut elle doğrulanmış alt kümede 0,9301 skor verdi.

`model/qwen3-vl-8b` aynı motorla `--grup-kare 12` kullanılarak denenebilir.
27B aynı kareleri kullansa da `llama-mtmd-cli` çalışma zamanı gerektirdiği
için Jordan'ın transformers motoruna zorla yerleştirilmez; ayrı adaptör/model
kolu olmalıdır.

Eski Qwen3.5 `w8a8`/`bf16` ağırlıkları silinmemiştir fakat native-video
stratejisi devre dışıdır ve varsayılan değildir.

## 5. Derleyici kuralları

- Fuzzy satır eleme yoktur.
- `Ahmat` ve `Ahmet` iki ayrı aday olarak kalır.
- Yalnız son `kesin_tekrar_penceresi` içinde aynı casefold/boşluk imzasına
  sahip satır görünümden düşer.
- Her düşürme `kesin_tekrarlar` alanında ilk/tekrar grup numarasıyla
  kaydedilir.
- Ham yanıt hiçbir zaman değiştirilmez.
- BBox yoksa uydurulmaz; bugün proof `NONE`'dır.

Metin-only rol/isim çiftleyici ölçülen OCR reçetesinin parçası değildir.
Varsayılan kapalı, `--ciftle` ile isteğe bağlıdır. Çiftleyici yeni metin
ekleyemez; rol ve isim ham okuma havuzunda bulunmak zorundadır.

## 6. Kanıt yüzeyi

Her grup tanısı şunları taşır:

- grup/kare aralığı ve kaynak zamanı;
- her karenin JPEG SHA-256'sı ve boyutu;
- ham model cevabı ve cevabın SHA-256'sı;
- protokol/altyazı/boş-bildirim ayrımları;
- bozuk grup ve düşürülen kesin tekrar kayıtları.

Scratch kareleri iş sonunda silinir. Kaynak klip, ffmpeg reçetesi ve kare
hash'leri yeniden üretilebilirliği denetler. Satırın belirli bir kare/bbox'a
bağlanması henüz yoktur ve varmış gibi sunulmaz.

## 7. Dosya yapısı

| Yol | Sorumluluk |
|---|---|
| `jordan`, `main.py` | CLI, kuyruk, arıza çevirisi |
| `sozlesme.py` | dış Girdi/Cikti sözleşmesi |
| `src/model.py` | model yükleme ve image/text sorma |
| `src/okuyucu.py` | kare üretimi, gruplama, okuma, derleme |
| `src/ciftleyici.py` | isteğe bağlı metin-only rol/isim türetme |
| `config.yaml` | model, frame, grup, prompt ve üretim ayarları |
| `tests/` | CPU sözleşme ve akış testleri |
| `out/`, `scratch/` | kule çıktısı ve geçici alan |

`src/` dış `Cikti` tipini bilmez. `VideoHatasi`, `BellekHatasi`,
`CiktiBozuk` ve `ModelHatasi` yalnız `main.py` tarafından dış duruma
çevrilir.

## 8. Doğrulama

- Jordan: 64/64 CPU testi.
- Sheriff: 67/67 CPU testi.
- KARA ŞİMŞEK: 71 kare, 9 grup, 0 bozuk grup, 54,9 sn.
- KSK 2.5-VL referansıyla orta 7/9 ham grup byte-eşdeğer metin; ilk grup
  iki satırı kaçırdı, son grup referansta olmayan bir isim satırı ekledi.
  Kare JPEG hash'leri referans havuzuyla aynıdır; dolayısıyla fark kare
  üretiminden gelmez. Gözlenen en belirgin ortam farkı iki venv'in
  transformers/torch sürümleridir; nedensellik henüz ayrıca kanıtlanmadı.

Canlı sonuç:
`out/jordan_multiimage_ksk_25_final_20260817/cikis/jordan.json`.
