# Lebron — master PNG üretim kulesi

> **Klasör girer, master PNG çıkar; master okunur, metin çıkar.**
> Kompozitör: **magic** (terfi 2026-08-18 — derleyici/lebron ve ibrahimovic emekli).
> Lebron'a bir kare klasörü gösterirsin, içindekileri bağlar. Girdinin nereden
> geldiğini sormaz.

**DURUM: Faz 0-1-2 tamam.** Derleyici ve okuyucu kulede; DeepSeek-OCR kule
içinde yaşıyor, Ollama'ya gidilmiyor. Ayrıntı: `DURUM.md`.

**İlk kurulum:** `./venv_kur.sh` (11 GB) sonra `./model_kur.sh` (~3 GB torch +
6.3 GB ağırlık).

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

**`--bolum` bir KARAR DEĞİL, raf etiketidir.** Derleyici `giris` ve `cikis`'te
birebir aynıdır; etiket yalnız çıktının hangi rafa yazılacağını ve satır
izindeki kaynağı belirler. (Kobe'deki bölüm ayrımıyla karıştırma: orada iki
bölümün karar mantığı ayrıydı ve ayrı kalmak zorundaydı.)

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

## Okuyucu — model kulenin içinde

Üretimdeki okuyucu (`_pipe_hibrit_okuma.kol_master`) Ollama'ya HTTP atıyordu.
Kule modeli kendi taşır: *dışarıdaki bir servise bağlı kule kendi kendine yeten
bir kule değildir* (Çağatay). Ölçülmüş yan etkisi de var — Ollama açıkken Kobe
skoru %94.5 → %93.6 düşüyor.

**Okuma mantığı DEĞİŞMEDİ, yalnız taşıyıcı değişti:** aynı model
(DeepSeek-OCR), aynı istem (`Free OCR.`), aynı bant geometrisi.

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

## Çalışma zamanı — iki CUDA nesli yan yana

Kulede Paddle (`cu12`, derleyici) ve torch 2.11 (`cu13`, okuyucu) aynı venv'de.
torch'un JIT'i `libnvrtc-builtins.so.13.0`'ı **düz adla** arıyor ve yükleyici
önce cu12 dizinindeki 12.6 sürümünü buluyor:

```
nvrtc: error: failed to open libnvrtc-builtins.so.13.0
```

Bu hata her bandı sessizce düşürüyordu. `model_kur.sh` düzeltmeyi kuruyor:
`venv/nvrtc13/` içinde **yalnız o tek dosyanın** sembolik bağlantısı, `lebron`
betiği onu `LD_LIBRARY_PATH`'e ekliyor.

> **`cu13/lib`'i komple yola EKLEME.** Orada `libcufft.so.12`,
> `libcurand.so.10`, `libcusolver.so.12` gibi Paddle'ın cu12 zinciriyle **aynı
> soname**'e sahip dosyalar var — derleyici sessizce başka kütüphanelere
> bağlanır. Sadakat kapısı bunu yakalar ama hiç olmamalı.

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
- `src/magic.py` — **kulemaster'ı** (terfi 2026-08-18, Çağatay): 437 filmde
  üç eksende kazandı (370 sağlıklı / recall 0.586 / dup 0.000). Karar:
  `raporlar/kompozitor_secim_karari_2026-08-17.md`. `src/derleyici.py`
  (lebron motoru) emekli — kapı ve yardımcılar için dokunulmadan kalır.
- `olcum/kompozitor_kiyas.py` — kompozitör kıyas koşusu (lebron ↔
  ibrahimovic ↔ magic + ablasyon; saglik+sadakat+dup+çöküş).
- `OCR-worktree/master_png_monitor.py` — orkestratör: havuz seçer, Database'e
  yazar, symlink köprüsü kurar. Hiçbiri kule işi değil.
- `scripts/master_dilim_oku.py` — master'ı OneOCR ile okuyup VL korpusuna
  besleyen ayrı tüketici. Kule kapsamı dışı.
