# Jordan — mp4'ten jenerik okuma kulesi

> **mp4 girer, yazı çıkar.** Native video okuma. Düzeltme yok, yorum yok,
> ek katman yok. Model: Qwen3.5-9B.

## Sorumluluk sınırı

**Yapar:** verilen klipte ekranda YAZAN metni okur, kendi `out/`'una yazar.

**Yapmaz:** jeneriğin nerede başladığını aramaz (Kobe'nin işi) · isim
düzeltmez · eksik tamamlamaz · Database'e yazmaz · PDF üretmez · hangi filmin
hangi yoldan okunacağına karar vermez (router değildir).

## Çalıştırma

Kule kendi çalışma zamanını kendi bulur — çağıran hangi python'la koşulacağını
bilmez:

```bash
# TEK klip
Allstar/jordan/jordan tek --video /yol/klip.mp4 --film-id 2025-1307-1-0000-50-0

# TOPLU — kaldığı yerden devam eder, _TAMAM olanı atlar, model BİR KEZ yüklenir
Allstar/jordan/jordan start --input /yol/klipler

# Model değiştir (config.yaml'ı ezer)
Allstar/jordan/jordan start --input /yol/klipler --model model/bf16
```

Çıktı daima `Allstar/jordan/out/<film_id>/<bolum>/`. Çağıran çıktı yolunu
seçmez — kule kendi evine yazar.

```
out/<film_id>/cikis/
├─ jordan.json     # bloklar + çiftler + kanıt
├─ jordan.txt      # düz metin, satırlar göründüğü sırayla
└─ _TAMAM          # EN SON yazılır
```

## Girdi

Jordan'ın tek girdisi **video**'dur; ve verilen klibin **jeneriğin kendisi
olduğunu varsayar**. Kare dizini, PNG havuzu almaz. Standart besleme Kobe'nin
`--uret klip` çıktısıdır:

```bash
Allstar/kobe/kobe tek --video film.mp4 --film-id ID --uret klip
Allstar/jordan/jordan tek --video Allstar/kobe/out/ID/cikis/klip/klip.mp4 --film-id ID
```

## İki geçiş — neden ayrı

| | Geçiş 1 — **okuyucu** | Geçiş 2 — **çiftleyici** |
|---|---|---|
| Girdi | native video (mp4) | *yalnız* geçiş 1'in metni |
| Çıktı | `bloklar` — ekranda birlikte duran satırlar | `ciftler` — rol → isim |
| Görüntü görür mü | evet | **hayır** |

Tek istekte model rolü tutturmak için metni "düzeltmeye" başlar; o an okuma
hatasıyla eşleme hatası ayrılamaz. Ayrı geçiş bunu imkânsız kılar.

**Sızdırmazlık kapısı:** çıkan her rol ve her isim, geçiş 1'in satırlarında
gerçekten geçmek zorundadır. Geçmiyorsa çıktıya girmez, `kanit.cift_eleme`
sayacına yazılır. Model geçiş 2'de yeni metin uyduramaz.

**Geçiş 2 çökerse geçiş 1 atılmaz.** Bloklar gerçek okumadır, çiftler türev
veridir; türev çökünce asıl korunur (`kanit.cift_ariza`).

## Sözleşme

`durum` üç değer alır ve bu ayrım **değişmezdir**:

| durum | Anlamı | Zorunlu |
|---|---|---|
| `OKUNDU` | Metin okundu | `bloklar` (boş olamaz) |
| `METIN_YOK` | Klipte gerçekten okunacak yazı yok — **içerik gerçeği** | — |
| `ARIZA` | Okuyamadık: video bozuk, model çöktü, OOM — **arıza gerçeği** | `sinif` + `mesaj` |

> **`ARIZA` asla `METIN_YOK`'a dönüşmez.** Geniş bir `except` arızayı içerik
> gerçeğine çevirdiği an aşağı akış kirlenir ve kimse fark etmez. Sözleşme
> bunu kodla zorlar; `METIN_YOK` ve `ARIZA` blok/çift **taşıyamaz**.

| sinif | Ne oldu |
|---|---|
| `GIRDI_HATASI` | video yok / sözleşme ihlali |
| `VIDEO_OKUNAMADI` | ffprobe/ffmpeg patladı, parça üretilemedi |
| `BELLEK` | CUDA OOM — çaresi parça küçültmek |
| `CIKTI_BOZUK` | Model konuştu ama çıktısı kullanılamaz (bitmemiş düşünme, boş) |
| `MODEL` | Model yüklenemedi / beklenmedik istisna |

Tüketici kuralı: **`_TAMAM` yoksa dosya yok sayılır.**

## Neden parçalanıyor — ölçülmüş sınır

24 GB'lık RTX 3090'da tek çağrıya giren kare sayısı fiziksel bir tavana çarpar.
Sandbox ölçümü (2026-08-12): **36 kare/çağrı → 39 filmin 39'unda CUDA OOM.
30 kare → çalıştı.** Marj jilet gibi.

Bu yüzden klip `parca.sure_sn` saniyelik, `parca.bindirme_sn` bindirmeli
parçalara kesilir ve her parça ayrı çağrıda okunur. Bindirme, parça sınırında
kesilen ismi kurtarır; ardışık parçadaki **birebir aynı** blok düşer, uzak
tekrarlar korunur (jenerikte aynı isim gerçekten iki kez geçebilir).

Parçalama bir yorum katmanı değil — modelin bu kartta koşabilmesinin tek yolu.

## Model — iki checkpoint kurulu

| | `model/w8a8` (VARSAYILAN) | `model/bf16` |
|---|---|---|
| Ne | INT8 W8A8 (`RedHatAI/Qwen3.5-9B-quantized.w8a8`) | Orijinal (`Qwen/Qwen3.5-9B`) |
| Boyut | 14 GB | 19.3 GB |
| Görüntü kulesi | **kuantize DEĞİL** — `model.visual.*` bf16 | bf16 |
| Serbest VRAM | ~9.5 GiB | ~4.5 GiB |

**FP8 bu kartta yok.** RTX 3090 = Ampere `sm_86`; FP8 çekirdeği `sm_89`+ ister.
8-bit istendiğinde doğru cevap INT8'dir.

> **Hangisinin daha iyi okuduğu ÖLÇÜLMEDİ.** INT8 varsayılan çünkü bellek
> kısıtı ölçülmüş (39/39 OOM), kuantizasyon kaybı ise henüz varsayım. bf16
> kıyasın kontrol koludur — ölçüm yapılmadan silinmez.

Kurulum: `./venv_kur.sh` sonra `./model_kur.sh`.

## Yerleşim

| Ne | Yol |
|---|---|
| Sözleşme (`Girdi`/`Cikti`/`ariza`) | `sozlesme.py` |
| CLI + koşu akışı | `main.py`, `jordan` |
| Model yükleme/sorma (transformers'a dokunan TEK yer) | `src/model.py` |
| Geçiş 1 — video → bloklar | `src/okuyucu.py` |
| Geçiş 2 — bloklar → çiftler | `src/ciftleyici.py` |
| Eşikler, istemler | `config.yaml` |
| Çalışma zamanı | `venv/`, `venv_kur.sh`, `gereksinimler.txt` |
| Model ağırlıkları (git'te değil) | `model/w8a8`, `model/bf16`, `model_kur.sh` |

`src/` sözleşmeyi **bilmez** — çeviri yalnız `main.py`'de.

## Testler

```bash
venv/bin/python -m pytest tests -q      # 52 test, GPU gerektirmez
```
