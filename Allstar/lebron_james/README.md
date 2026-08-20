# Lebron — master PNG üretim kulesi

> **Klasör girer, master PNG çıkar; master okunur, metin çıkar.**
> Kompozitör: **LeBron** (`src/derleyici.py`). 2026-08-18'de `magic` deney
> adıyla seçilen birleşik motor kalıcı LeBron adına terfi ettirildi.
> Lebron'a bir kare klasörü gösterirsin, içindekileri bağlar. Girdinin nereden
> geldiğini sormaz.

**DURUM:** Derleyici ve okuyucu kulede. Okuyucu ortak 11434 servisini değil,
kuleye kilitli GGUF ve Ollama 0.32.0 ile rastgele loopback portunda açılan özel
LeBron sürecini kullanır. Ayrıntı: `DURUM.md`.

**İlk kurulum:** `./venv_kur.sh`, sonra `./model_kur.sh`. İkinci komut ağdan
indirme yapmaz; mevcut yerel GGUF, manifest ve çalışma zamanını SHA-256
kilitleriyle kuleye kopyalar. Eski HF ağırlığı kabul tamamlanana kadar korunur.

## Sorumluluk sınırı

**Yapar:** verilen kare klasöründeki kareleri tek bir master PNG'ye bağlar, o
master'ı okur, ikisini de kendi `out/`'una yazar.

**Yapmaz:** jeneriğin nerede başladığını aramaz (Kobe) · ham kareleri okumaz
(Nash) · mp4'ü doğrudan okumaz (Jordan) · hangi klasörün işleneceğine karar
vermez (MITAS orkestrası) · Database'e yazmaz · PDF üretmez · isim/rol
düzeltmez (Ronaldo / Phil Jackson).

## Çalıştırma

Kule kendi çalışma zamanını kendi bulur — çağıran hangi python'la koşulacağını
bilmez:

```bash
# TEK klasör
Allstar/lebron_james/lebron tek --kareler /yol/kareler --film-id X --bolum cikis

# TOPLU — kaldığı yerden devam eder, _TAMAM olanı atlar
Allstar/lebron_james/lebron start --input /yol/kare_dizinleri --bolum cikis
```

Çıktı daima `Allstar/lebron_james/out/<film_id>/<bolum>/`. Çağıran çıktı yolunu
seçmez — kule kendi evine yazar.

```
out/<film_id>/
├─ giris/
│  ├─ master.png    # kompozisyon başarılıysa HER ZAMAN yazılır
│  ├─ lebron.txt    # YALNIZ durum=OKUNDU ise
│  ├─ lebron.json   # durum + satirlar + uretilen + kanit
│  └─ _TAMAM        # EN SON yazılır
└─ cikis/  (aynısı)
```

**`--bolum` bir karar değil, raf etiketidir.** Derleyici yolu bölüm adından
değil kare havuzunun sözleşmesinden seçilir. Kobe/Sheriff giriş havuzu
`_sinif.json` içinde `mod=ardisik_aralik` taşır; bu sözleşme LeBron'un aşağıdaki
kilitli giriş motoruna girmesini zorunlu kılar. Diğer havuzlar mevcut kayan
kapanış kompozitöründe kalır.

## Kilitli giriş-master kuralı

> **ÜRETİM KURALI — AYAR DEĞİLDİR:** `mod=ardisik_aralik` havuzu daima
> `giris-text-only/v1` ile işlenir. Bu yol config/CLI seçeneğiyle kapatılamaz,
> gevşetilemez ve eski kayan-kapanış motoruna düşürülemez.

Giriş jeneriğinde ardışık kareleri kaydırarak dikmek, statik oyuncu kartlarını
aynı zemin sanıp yarım kare ve kayıp kredi üretiyordu. Kalıcı davranış şudur:

- Paddle'ın pikselde yazı kutusu gördüğü kareler incelenir; yazısız sahne,
  görüntü arası ve altyazı mastera alınmaz.
- Aynı karta ait tekrar/fade kareleri gruplanır; her gerçek karttan en sağlam
  **tam kare** bir kez seçilir.
- Seçilen tam kareler kaynak zaman sırasıyla dikey dizilir; kırpılıp birbirine
  kaynatılmaz. Kobe havuzundaki kaynak kareler silinmez veya seyreltilmez.
- Paddle hiçbir kareyi analiz edemezse sessizce `METIN_YOK` denmez;
  `ARIZA(GIRIS_YAZI_ANALIZ)` üretilir.
- Manifest bu hükmü `mode=lebron_giris_text_only`, `text_only=true` ve
  `giris_plan.surum=giris-text-only/v1` alanlarıyla denetlenebilir kılar.

Bu motorun eşikleri ayar düğmesi değildir. Değişiklik ancak sürüm artırılarak,
`tests/test_giris_planlayici.py` regresyonları ve gerçek temiz toplu kabul
yeniden geçirilerek yapılabilir. Giriş-master kalitesi görülmeden eşik
"optimizasyonu" yapılmaz.

**Faz 1'de yalnız kare klasörü.** mp4 verilirse açık `ARIZA(GIRDI_HATASI)` —
mp4'ten kare çıkarımı fps'i ölçüm-kritik bir parametre yapar, o ayrı bir iş.

## Sözleşme

| durum | Anlamı | Zorunlu |
|---|---|---|
| `OKUNDU` | master üretildi **ve** metin okundu | `satirlar` (boş olamaz) |
| `METIN_YOK` | okunacak yazı gerçekten yok — **içerik gerçeği** | — |
| `ARIZA` | okuyamadık — **arıza gerçeği** | `sinif` + `mesaj` |

> **`ARIZA` asla `METIN_YOK`'a dönüşmez.** Geniş bir `except` arızayı içerik
> gerçeğine çevirdiği an aşağı akış kirlenir: "bu jenerikte yazı yok" ile
> "PaddleOCR çöktü" aynı kutuya girer ve fark bir daha bulunamaz.

| sinif | Ne oldu |
|---|---|
| `GIRDI_HATASI` | dizin yok · dizin boş · 2'den az kare |
| `KARE_OKUNAMADI` | kareler VAR ama hiçbiri açılamadı |
| `BOY_ASIMI` | master boyu > 45000 px |
| `COKME` | 20+ kare tek segmente çökmüş (aşağıda) |
| `MOTOR` | derleyici istisna attı / master yazılamadı |
| `MASTER_OKUNAMADI` | master yazıldı ama geri açılamadı |
| `MODEL` | model yüklenemedi / kurulmadı (`./model_kur.sh`) |
| `BELLEK` | CUDA OOM |
| `OKUYUCU` | okuyucu beklenmedik istisna attı |

**Master PNG okuma sonucundan BAĞIMSIZ yazılır.** Okuyucu çökse bile artefakt
diskte durur ve `uretilen` künyesine girer. Sebep: derlemeye harcanan iş çöpe
gitmesin, ve arızanın hangi tarafta olduğu (derleme mi, okuma mı) gözle görülür
kalsın. Bu Kobe'den bilinçli bir ayrışmadır.

Tüketici kuralı: **`_TAMAM` yoksa dosya yok sayılır.**

## Okuyucu — kuleye ait özel GGUF süreci

LeBron sistemdeki ortak 11434 servisine bağlanmaz. Her CLI toplu koşusunda
kendi kilitli Ollama 0.32.0 sürecini rastgele loopback portunda açar; tek model,
tek paralel istek ve `OLLAMA_NO_CLOUD=1` uygular. Süreç `bubblewrap` ile özel
bir `.ollama` durum dizinine bağlanır; kullanıcının `~/.ollama` içeriği değişmez.
Normal bitiş, hata, Ctrl-C ve Sheriff iptalinde model indirilir ve doğrulanmış
alt süreç ağacı kapatılır.

Okuma davranışı korunur: aynı DeepSeek-OCR GGUF, `Free OCR.`, 1100/120 bant
geometrisi, `temperature=0`, `num_predict=2048`, `num_ctx=8192`. Isıtma tavanı
90 sn, sıcak bant tavanı 30 sn'dir.

```
master.png
  → bantla: 1100 px, 120 px bindirme, <40 px son bant atılır
  → her bant: model.sor(bant) → satırlar
  → kutu_n piksel kalkanı · gevezelik süzgeci · yapısal veto · fold-dedup
  → lebron.txt
```

| Süzgeç | Ne yakalar | Nereden geldi |
|---|---|---|
| **`kutu_n` piksel kalkanı** | Paddle det 0 kutu bulmuşken model satır ürettiyse → **uydurma** | HAKEM v1, 2026-07-31 |
| Gevezelik | "No recognizable text", `Caption:`, `[图片中...]` | YAZ TATİLİ 1963-0035 |
| Yapısal veto | markdown, `<td>`, düzyazı fiili, harfsiz `- 1` | üretim |
| Garble | `LEE MARVIN LEE MARVIN` çift-basımı | ronaldo |
| Fold-dedup | 120 px bindirmeden gelen tekrar | pilot_hat |

**`kutu_n` üçlü ayrım yapar:** `0` = ekranda yazı yok, model uydurdu →
satırlar düşer. `None` = ölçemedik → **hüküm verilmez**. İkisi karışırsa sağlam
satırlar atılır.

**Elenen satırlar yok edilmez**, `kanit.elenen`e sebebiyle yazılır — yanlış
eleme yapıyorsak görünür olsun.

`src/okuyucu.py` modeli **bilmez** (`sor` geri-çağrısı alır), o yüzden tüm
süzgeçler GPU'suz test edilir. Modele dokunan tek dosya `src/model.py`.

## Çöküş dedektörü

Motor bazen 20+ kareyi tek ekrana çökertiyor. Üç koşul birlikte ararsa çıktı
reddedilir ("kötü master yerine hiç"):

| Koşul | Neden |
|---|---|
| `segment == 1` | motor hiç bölmemiş |
| `kare >= 20` | az karede tek segment MEŞRU (gerçek tek kart) |
| `boy <= 2 × kare_h` | 20+ karelik jenerik iki ekrana sığmaz |

`master_png_monitor._lebron_cokmus`'ten taşındı. Kule içinde yaşar ki her
tüketici aynı testi yeniden yazmak zorunda kalmasın — ve biri unutmasın.

## Yerleşim

| Ne | Yol |
|---|---|
| **Derleyici** (birincil kompozitör) | `src/derleyici.py` |
| Kare listeleme / okuma / yazma | `src/yukleyici.py` |
| Kulenin kendi çıktısı hakkındaki hükümler | `src/kural.py` |
| Okuyucu (Faz 2) | `src/okuyucu.py` · `src/model.py` |
| Sözleşme | `sozlesme.py` |
| CLI + koşu akışı | `main.py`, `lebron` |
| **Sadakat kapısı** | `olcum/kapi_sadakat.py` |
| Çalışma zamanı | `venv/`, `venv_kur.sh`, `gereksinimler.txt` |

Yükleme ve hükümler motorun DIŞINDA yaşar — testleri 11 GB'lık çalışma zamanı
gerektirmesin diye. Sıralama kuralının testi Paddle'sız koşar.

## Sadakat kapısı

Taşımanın doğruluğu iddia edilmez, **ölçülür**. Kapı, kule çıktısı ile bugünkü
üretim yolunun çıktısını aynı kare klasöründe koşturup SHA-256 karşılaştırır.

```bash
cd olcum && ../venv/bin/python kapi_sadakat.py --n 8
# KIRMIZI ÇİZGİ: sapma 0. Tek sapma bile kapıyı kapatır.
```

**Son sonuç: 8/8 bit-birebir, sapma 0** (2026-08-15, Ex_Frame ilk 8 film).
440 filmin tamamı henüz koşulmadı.

## Taşınırken kapatılan iki kusur

**(a) Sıralama.** Kaynak motor klasörü `sorted(glob("*.png"))` ile okuyordu —
sözlük sırası. Üretim ise `nat_sort_key` (addaki son sayı) kullanıyordu. Sıfır
dolgulu adlarda ikisi aynıdır, bu yüzden bugüne kadar patlamadı. Dolgusuz adda
(`kare_9` > `kare_10`) kareler yanlış sırada bağlanır ve master **sessizce**
bozulur. Kule "bana klasör göster" dediği için girdinin adlandırmasını seçemez.
`tests/test_siralama.py` kapıyı kilitler.

**(b) Çift okuma.** Kaynak her PNG'yi iki kez `imread` ediyordu — 659 karelik
havuzda 1318 disk okuması.

Bunlar dışında motora tek satır dokunulmadı; sadakat kapısı bunu kanıtlıyor.

## Paddle → GGUF bellek sırası

LeBron önce kompozisyonu ve tüm master bantlarının Paddle kutu sayılarını
tamamlar. Sonra Paddle referanslarını/cache'ini bırakır; özel GGUF süreci ancak
bunun ardından yüklenir. Gerçek `cag_output07` ölçümü: Paddle kalıntısı 338
MiB, Ollama süreç-ağacı tepesi 8660 MiB, en uzun sıcak bant 18.36 sn. Sheriff
rezervasyonu `(8660 + 1024)` değerinin 512 MiB yukarı yuvarlanmasıyla 9728
MiB'dir.

## Çalışma zamanı — paket çıkarma

`gereksinimler.txt` 167 pin içerir ve **elle budanmaz** — Kobe'de ölçülmüş
pahalı ders: 16 paketlik seçilmiş liste skoru %94.5'ten %92.7'ye düşürdü, altı
kilit paket birebir aynı olduğu halde. Paket çıkarmadan önce sadakat kapısını
koş.

Yeniden kurmak: `./venv_kur.sh` (sıfırdan: `./venv_kur.sh --temiz`).

## LEBRON OLMAYANLAR (karışıklık olmasın)

- `harness/master_dup/lebron_james.py` — kulenin **kaynağı**; kod buraya
  taşındı. Üretim henüz o dosyayı çağırıyor (Faz 5'e kadar).
- `harness/master_dup/ibrahimovic.py` — eski kompozitör, Lebron onun yerine
  geçti (2026-08-04). Kör kopyası `aday/ibrahimovic.py`.
- `arsiv/legacy_derleyici.py` — terfi öncesi LeBron motoru; yalnız tarihî
  karşılaştırma içindir.
- `olcum/kompozitor_kiyas.py` — kanonik LeBron ↔ legacy LeBron ↔
  ibrahimovic kıyası ve LeBron ablasyonları.
- `OCR-worktree/master_png_monitor.py` — orkestratör: havuz seçer, Database'e
  yazar, symlink köprüsü kurar. Hiçbiri kule işi değil.
- `scripts/master_dilim_oku.py` — master'ı OneOCR ile okuyup VL korpusuna
  besleyen ayrı tüketici. Kule kapsamı dışı.
