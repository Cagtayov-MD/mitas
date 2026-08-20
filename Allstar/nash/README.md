# Nash — ham kare havuzundan jenerik okuma kulesi

> **Ana kare havuzu girer, kanıtlı yazı çıkar.** Paddle tüm kareleri GPU'da
> tarar ve okur. Türkçe/Latin model zayıf kalırsa yalnız o filmde önce
> Arapça/Farsça, kabul kapısını geçmezse ESlav/Kiril Paddle tanıyıcı çalışır.
> Kobe sınırı veya sonucu kullanılmaz; zincir, Nash'i her mevcut bölüm ana kare
> dizininde Kobe havuzu olmasa da bir kez çalıştırır.

**DURUM: çok-alfabeli Paddle okuyucu çalışıyor.** DeepSeek fallback kodu
korunuyor fakat üretim config'inde kapalıdır; Nash şu anda ağır modeli hiç
yüklemez. Ayrıntı: `DURUM.md`.

## Sorumluluk sınırı

**Yapar:** verilen ana havuzun tamamında metin kutularını ve metni tarar;
altyazı/logo gürültüsünü, geçiş birleşiklerini ve zamansal tekrarları eler;
kanıt bbox'larıyla kendi `out/`una yazar.

**Yapmaz:** jeneriğin nerede başladığını aramaz (Kobe'nin işi) · master PNG
üretmez (İbrahimovic) · isim düzeltmez · rol eşlemez (Ronaldo/Phil Jackson) ·
Database'e yazmaz · PDF üretmez · hangi filmin hangi yoldan okunacağına karar
vermez (router değildir).

## Çalıştırma

Kule kendi çalışma zamanını kendi bulur — çağıran hangi python'la koşulacağını
bilmez:

```bash
# TEK film
Allstar/nash/nash tek --kareler /yol/ana_havuz/cikis --film-id <id>
Allstar/nash/nash tek --kareler /yol/frames/giris --film-id <id> --bolum giris

# TOPLU — kaldığı yerden devam eder; filmler tek Paddle worker ile sırayla gider
Allstar/nash/nash start --input /yol/kare_dizinleri
```

Çıktı varsayılan olarak `Allstar/nash/out/<film_id>/<bolum>/`; testte `--out`
ile güvenli biçimde başka kök seçilebilir.

```
out/<film_id>/cikis/
├─ nash.json     # durum + satırlar + kanıt
├─ nash.okuma.json # Sheriff/MITAS_OKUMA_V2 altında bbox kanıt paketi
├─ nash.txt      # YALNIZ durum=OKUNDU ise
└─ _TAMAM        # EN SON yazılır
```

## Sözleşme

| durum | Anlamı | Zorunlu |
|---|---|---|
| `OKUNDU` | Metin okundu | `satirlar` (boş olamaz) |
| `METIN_YOK` | Karelerde gerçekten okunacak yazı yok — **içerik gerçeği** | — |
| `ARIZA` | Okuyamadık — **arıza gerçeği** | `sinif` + `mesaj` |

> **`ARIZA` asla `METIN_YOK`'a dönüşmez.** Ve aynası da geçerli: içerik gerçeği
> arıza diye etiketlenmez. `METIN_YOK` ve `ARIZA` satır **taşıyamaz** — sözleşme
> bunu kodla zorlar.

| sinif | Ne oldu |
|---|---|
| `GIRDI_HATASI` | dizin yok / desene uyan dosya yok |
| `KARE_OKUNAMADI` | kareler VAR ama `cv2.imread` hiçbirini açamadı |
| `BELLEK` | CUDA OOM |
| `CIKTI_BOZUK` | model konuştu ama çıktı garble |
| `MODEL` | model yüklenemedi / kurulmadı |

**Havuz boş'un ikiye ayrılması — kulenin kapattığı körlük.** Üretimde
(`_pipe_track_kunye.py:178`) iki farklı gerçek tek kutuya giriyor
(`skipped/messi_havuz_bos`): kareler okundu ama hepsi içeriksiz mi, yoksa hiçbir
kare açılamadı mı? Ölçüm yatağında `"durum": "havuz_bos"` yazan bir film var ve
hangisi olduğu **bilinmiyor**. Kule ayırır: içeriksiz → `METIN_YOK`,
açılamayan → `ARIZA(KARE_OKUNAMADI)`.

**`nash.txt` yalnız `OKUNDU`'da yazılır.** Boş bir `nash.txt`, yalnız metni okuyan
bir tüketiciye "yazı bulunamadı" gibi görünür ve tam da bu ayrımı yutar. Dosya
yoksa tüketici `nash.json`'a bakmak zorunda kalır.

Tüketici kuralı: **`_TAMAM` yoksa dosya yok sayılır.**

## Bölüm farkları — uydurma yok, üretimden taşındı

| | `cikis` | `giris` |
|---|---|---|
| Text-run temsilci tavanı | 100 | 60 |
| Sigorta | **son kare zorla** | **son 12 HAM kare zorla** |
| Neden | © / "SON" kartı düzgün-adımda hiç seçilmiyordu (konsey bug-avı GLM-3) | ALİE, 2026-07-31: TRT geleneğinde YÖNETMEN kartı girişin SON kartıdır; ALİE'de giriş master'ı 'senaryo'da kesildi ve yönetmen 1632 satırın hiçbirine girmedi → QC1 RED |

İkisinin de arkasında kayıtlı bir üretim kazası var; tek rejime indirmek birini
kaybetmek olurdu.

## Sağlık bir bayraktır, hüküm değil

`kanit.saglik` her koşuda yazılır (`ok` / `cok_kisa` / `garble_yuksek` /
`bos_cikti`). Yalnız **`garble_yuksek`** `ARIZA(CIKTI_BOZUK)` üretir — çünkü
elimizdeki metin YANLIŞTIR ve aşağı akışa bırakmak künyeyi zehirler (rodeo
vakası: iki kol da çöktüğü için "Kubrick/Godfather" uydurmaları künyeye girdi).

`cok_kisa` **arıza değildir.** Kısa olmak yanlış olmak demek değil; 5 satırlık
gerçek bir jenerik arızaya çevrilirse içerik gerçeği arızaya kurban gider.

## Ölçüm — KAPI 1 (taşıma kapısı)

Havuz yarısı saf numpy/cv2: model yok, ağ yok, rastgelelik yok. Doğru
taşındıysa aynı karelerde aynı sayıları vermek **zorunda**.

```bash
# 1) BUGÜNKÜ üretim kodundan referans üret (üretimin kendi yorumlayıcısıyla)
/opt/mitas/venvs/ocr/bin/python olcum/referans_uret.py
# 2) kuleyle kıyasla
venv/bin/python olcum/kapi1.py
```

**Sonuç: 29/29 birebir aynı, sapma sıfır** (15 film × çıkış+giriş yüzeyi).

> **Tarihî JSON'lara karşı ölçmeyin.**
> `outputs/olcum_yatagi/.../olcum_kol_frame.json` 2026-07-31'de üretildi.
> `e1a201d5` (2026-08-05) `film_esigi`'nin Otsu aramasını yeniden yazdı
> ("O(n) optimizasyonu") ve **cevabı değiştirdi**: eski arama her iki yanda
> ≥3 eleman şartıyla **kısıtlıydı**, yenisi şartsız arayıp ≥3'ü **sonradan**
> reddediyor. MOBY DICK'te eşik 28→13, sayfa **15→165 (11×)**. Bu fark
> taşımanın değil o commit'in eseridir; `kapi1.py` onu ayrı satırda raporlar.
> Otsu onarımı 29/29 yüzeyde eski kararlarla ölçüldü; buna karşılık yoğun ve
> seyrek havuzların aşağı akış okuma kalitesi hâlâ ayrı bir açık ölçümdür.

## Testler

```bash
venv/bin/python -m pytest tests -q      # yapısal koruma testi dışında skip yok
```

## Yerleşim

| Ne | Yol |
|---|---|
| Havuz çekirdeği (SAF — algoritma değişmez) | `src/havuz.py` |
| Ana havuz full OCR worker'ı | `src/metin_worker.py` (ayrı Paddle venv'i) |
| Metin bloğu/temsilci seçimi | `src/metin_secici.py`, `src/secim.py` |
| Paddle temporal uzlaşma + alfabe/fallback birleştirme | `src/hibrit.py` |
| Kareler → satırlar (dedup + gevezelik süzgeci) | `src/okuyucu.py` |
| DeepSeek adaptörü ve sert üretim sınırları | `src/model.py` |
| `mitas.okuma/v2` bbox kanıtı | `src/proof.py` |
| Sözleşme (`Girdi`/`Cikti`/`ariza`) | `sozlesme.py` |
| CLI + koşu akışı | `main.py`, `nash` |
| Eşikler, sigortalar, istem | `config.yaml` |
| Taşıma kapısı | `olcum/kapi1.py`, `olcum/referans_uret.py` |
| Çalışma zamanı | `venv/`, `venv_kur.sh`, `gereksinimler.txt` |

`src/` sözleşmeyi **bilmez** — çeviri yalnız `main.py`'de.

## Çalışma zamanı

`venv_kur.sh` **python 3.12.13 zorunlu** kılar (`~/.pyenv/versions/3.12.13`).
Sistem python'u 3.14; referans ölçüm verisini üreten ortam 3.12.13 idi ve
havuz çıktısının sürümden bağımsız olduğu **ölçülmedi**. Kobe dersi: ortam
bütün olarak dondurulur, "hangi paket önemli" tahmin edilmez.

Paddle ayrı `detector_venv/` içindedir: **Paddle 3.3.1, PaddleOCR 3.7.0,
PaddleX 3.7.2, CUDA 12.6**. Detection `PP-OCRv6_medium_det`; Türkçe/Latin
tanıma `latin_PP-OCRv5_mobile_rec`; koşullu ikinci tanımalar sırasıyla
`arabic_PP-OCRv5_mobile_rec` ve `eslav_PP-OCRv5_mobile_rec` kullanır.
Orientation/unwarp/HPI kapalı, FP32 ve `gpu:0` sabittir. Dört model de Nash'in
yerel model dizininden açılır; ağdan model indirilmez.

Script yönlendirmesi birincil satır sayısı 8'in altında veya Latin medyan
güveni 0,80'in altındaysa tetiklenir. Hedef alfabe oranı en az %35 olmalıdır.
ESlav devralmasında Latin satır ayrıca ikinci tanıyıcı tarafından yakın
kare/örtüşen kutuda doğrulanır; böylece Kiril homoglifleri Latin isim diye
kalmaz. Arabic devralmasında yüksek güven (≥0,90), zamansal destek (≥2) ve ayrı
kutu (IoU<0,30) kapısı korunur; `cag_output23`teki gerçek `CPR` kredisi bu
sayede kaybolmaz.

## Gerçek ölçüm — `/home/cagatay/Belgeler/test`

29 video, 7.414 adet 2-fps kare son sürümle baştan sona işlendi: **29/29
`OKUNDU`**, 2.583 kabul edilmiş satır, sıfır DeepSeek çağrısı, 372,64 sn duvar
süresi. İç Paddle peak en çok 333,9 MB; canlı `nvidia-smi` süreci 556–622 MiB.
Sheriff Nash için 2.048 MB ayırır. 114-karelik gerçek örnek 9,84 sn; en ağır
Latin kayan jenerik 239 kare/280 satırda 26,71 sn; 490-kare Arapça/Farsça çift
Paddle geçişi 26,12 sn. Aday seçimi hiçbir filmde çıkış tavanı 100'ü aşmadı.

65-kare `cag_output14` 18 temiz satırı 5,9 sn'de verdi. Genel v6 tanıyıcının
bozduğu `MÜZİK`, `İRSEL ÇİVİT`, `UĞUR UZUNOK`, `BERAT ÖZDOĞAN` resmî Latin
modelinde doğru çıktı. Arapça/Farsça iki zayıf film koşullu ikinci Paddle
geçişiyle 51 ve 74 satıra çıktı. Yeni alfabe kapıları ayrıca
`cag_output20`de 71 Kiril satır ve sıfır sahte korunmuş Latin;
`cag_output23`te 294 Arabic/Farsi satır + görüntüdeki gerçek `CPR` satırını
verdi.

Yoğun `cag_output26` karşılaştırmasında 2 fps: **280 satır / 26,6 sn**;
3 fps: **279 satır / 36,9 sn**. 3 fps %39 daha uzun sürdü, toplam satır
kazandırmadı ve `BURAK KARAKULLUKCU`yu `MURAT...` okudu. Bu nedenle varsayılan
2 fps olarak bırakıldı.

## Tasarım

`docs/superpowers/specs/2026-08-14-allstar-nash-kulesi-design.md`
