# Jordan — multi-image jenerik okuma kulesi

Jordan'ın dış girdisi jeneriğin videosu veya `frames.jsonl` taşıyan doğrulanmış
kare havuzudur. Sheriff üretim yolu kalıcı olarak kare havuzunu kullanır. Kule
kaynak kareleri 720 px JPEG reçetesiyle hazırlar ve modele yalnız ayrı resim
listeleri verir. Native-video model yolu yoktur.

Varsayılan üretim kolu Qwen3-VL-8B BF16 transformers'dır. Ölçülmüş reçete:
2 fps, 720 px Lanczos + unsharp, 8 ayrı kare/çağrı, bindirme 1, greedy üretim
ve 512 token tavanı. Qwen3.6-27B GGUF yalnız açıkça `--backend llama_mtmd`
verilen deney kolu olarak korunur; Sheriff model/backend seçmez.

## Sınır

Jordan verilen klipteki yazıyı okur. Jenerik sınırını bulmaz, isim
düzeltmez, IMDb/Wikipedia sorgulamaz ve Shaq kararını vermez. BBox/proof
henüz üretmez; Sheriff paketinde `proof_status=NONE` kalır.

## Çalıştırma

```bash
# Tek klip
Allstar/jordan/jordan tek \
  --video /yol/jenerik.mp4 \
  --film-id film_001 \
  --bolum cikis

# Sheriff/üretim yolu: doğrulanmış frame-v1 havuzu
Allstar/jordan/jordan tek \
  --kareler /yol/materialized/cikis/jordan_frames \
  --film-id film_001 \
  --bolum cikis

# Toplu; _TAMAM bulunan filmi atlar, modeli bir kez yükler
Allstar/jordan/jordan start --input /yol/klipler --bolum cikis

# Aynı multi-image motorunda model/grup deneyi
Allstar/jordan/jordan tek --video /yol/jenerik.mp4 --film-id deney \
  --model model/qwen3-vl-8b --dtype float16 --grup-kare 12

# İsteğe bağlı 27B deney kolu; üretim varsayılanı değildir
Allstar/jordan/jordan tek --video /yol/jenerik.mp4 --film-id deney_27b \
  --backend llama_mtmd
```

Geçici CUDA resource-allocation/OOM hatası yalnız bir kontrollü retry alır;
ikinci hata terminal `ARIZA(BELLEK)` olur. Her deneme grup kanıtında saklanır.
KSK kabul koşusu tek Jordan çıktısında 71 kare/3 grup/0 bozuk grup olarak
50,4 saniyede tamamlandı; üç grup da ilk denemede geçti. Kanıt:
`out/jordan_27b_buyuk_kosu_hazirlik_20260817/cikis/jordan.json`.

Varsayılan çıktı:

```text
out/<film_id>/<bolum>/
├─ jordan.json
├─ jordan.txt
└─ _TAMAM
```

`_TAMAM` en son yazılır. Tüketici `_TAMAM` yoksa sonucu yok sayar.

## Akış

```text
video klip veya Sheriff frame-v1 havuzu
  → ffmpeg: 2 fps kaynak, scale=720:-2:lanczos + unsharp, JPEG q=2
  → 8'li ayrı image grupları (son grup kısa olabilir)
  → Qwen3-VL-8B BF16 ham kredi metni cevapları
  → protokol başlığı/altyazı ayrımı
  → yalnız kesin yakın-dönem tekrarların düşürüldüğü kredi görünümü
  → jordan.json + jordan.txt + _TAMAM
```

Fuzzy birleştirme yapılmaz. `Ahmat Güldiken` ve `Ahmet Güldiken` iki ayrı
okuma olarak korunur. Düşürülen kesin tekrarlar da dahil her ham grup cevabı
`kanit.gruplar` içinde saklanır.

Her kare için sıra, kaynak saniyesi, JPEG SHA-256 ve boyut taşınır. Kareler
scratch'te geçicidir; bu künye aynı ffmpeg reçetesiyle yeniden üretimi
doğrulamaya yarar. BBox uydurulmaz.

Metin-only rol/isim çiftleyici KSK reçetesinin parçası olmadığı için
varsayılan kapalıdır. Yalnız `--ciftle` ile açılır; ham okuma bundan
bağımsız korunur.

## Durum sözleşmesi

| Durum | Anlam |
|---|---|
| `OKUNDU` | En az bir kredi satırı okundu |
| `METIN_YOK` | Okunacak kredi metni yok |
| `ARIZA` | Video/model/çıktı hatası; `sinif` ve `mesaj` zorunlu |

`ARIZA` hiçbir zaman `METIN_YOK`'a çevrilmez. Tek grup bozulursa tanıda
görünür ve diğer gruplar korunur; bütün gruplar bozuksa sonuç arızadır.

## Doğrulama

```bash
Allstar/jordan/venv/bin/python -m pytest -q Allstar/jordan/tests
```

KARA ŞİMŞEK Qwen2.5-VL Sheriff ölçümünde giriş/çıkış tepe VRAM'i 17284 MiB;
tepe RSS 15244 MiB ölçüldü. 27B tarihî deney sonucu ayrıca korunur.
