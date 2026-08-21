# VINCE CARTER — kanıtlı jenerik okuma kulesi (plan)

> **Tek cümle:** Giriş ve çıkış jeneriğini okur; **her satırı piksel kanıtına
> bağlar**; kanıtsız satırı silmez, işaretler.
>
> Plan: Opus (2026-08-20) · Uygulama: Sonnet · Ölçüm: gerçek GT yatağı

## 0. Neden yeni bir kule?

Mevcut okuyucular (nash=Paddle/kare, jordan=Qwen-VL/kare, lebron=masterPNG)
aynı işi **tek kanaldan** yapıyor. Ölçülmüş kusur sınıfları
(`jenerik-okuma-hata-desenleri`) tek kanalda **yakalanamaz**:

| # | Hata | Neden tek kanal yakalayamaz |
|---|---|---|
| ① | Ünlü isim uydurması (`Edward Stevenson`→`Edith Head`) | Makul görünür; prompt kuralı engellemiyor |
| ② | Rol↔isim kayması | Her parça gerçek, yalnız BAĞ yanlış |
| ③ | `İ`→`I` çöküşü | Modelin kendi tokenizer'ı |
| ④ | Kelime ortası boşluk | Model tutarlı biçimde bozuyor |
| ⑤ | Kekeleme/dejenerasyon | Fazla kare → mutasyon |
| ⑥ | Kadraj kenarı tamamlama | Yarım ismi "tamamlıyor" |

Vince Carter'ın tezi: **bu kusurlar kanallar arası bağımsızdır.** Paddle OCR
`Edith Head` uydurmaz — pikselde ne varsa onu (bozuk da olsa) verir. VLM
stilize/kayan yazıyı okur ama uydurur. İkisini **çakıştırmak** kusurları
birbirine ihbar ettirir. Bedava kalite dedektörünün (aynı yeri iki koşuda
farklı okumak = uydurma) sistematik hali budur.

## 0b. Okuma penceresi — Çağatay'ın tanımı (2026-08-21)

| bölüm | pencere |
|---|---|
| **giris** | **filmin başı** → giriş jeneriğinin **bittiği** yer |
| **cikis** | çıkış jeneriğinin **başladığı** yer → **filmin sonu** |

> *"Girişteki ve çıkıştaki boşluklar sorun değil."*

Sonuçları:
- Pencere içinde jenerik **olmayan** malzeme bulunabilir (girişte açılış
  sahnesi, çıkışta jenerik öncesi son plan). Bu **beklenen** durumdur.
- Kule pencereyi **daraltmaz** — jenerik sınırı bulmak Kobe'nin işidir
  (MAP.md sorumluluk sınırı). Vince Carter kendisine verilen pencereyi okur.
- Ama pencere kenarındaki **film içi ekran yazısını** (tabela, gazete, altyazı)
  kredi diye sunmaz: `sahne_riski` işaretiyle görünür kılar
  (`docs/KANARYA_BULGULARI.md` bulgu 3 — pastane klibinin ilk 4 sn'si).
- Boş (yazısız) kareler arıza değildir; `METIN_YOK` yalnız **pencerenin
  tamamında** hiç yazı yoksa verilir.

### Asimetri kuralı (Çağatay, 2026-08-21)

> *"Filmin en başındaki ve en sonundaki boşluklar önemli değil; giriş
> jeneriğinin ÇIKIŞINI ve çıkış jeneriğinin BAŞINI kaçırmaması yeterli."*

Yani hata maliyeti **asimetriktir** — Kobe'nin üretim ölçütüyle aynı ruh
(erken zararsız, geç cast kaybettirir):

| hata | maliyet |
|---|---|
| pencere fazla geniş (başta/sonda boşluk) | **zararsız** |
| pencere kısa → giriş jeneriğinin SONU kaçtı | **pahalı** (kadro kaybı) |
| pencere geç → çıkış jeneriğinin BAŞI kaçtı | **pahalı** (kadro kaybı) |

**Kulenin buna katkısı — `pencere_kanit`:** kule pencereyi kesmez, ama
kırpılmayı **tespit edip raporlar**. OCR zaten kare başına metin varlığını
biliyor:

```
giris → pencerenin SON karelerinde hâlâ kredi metni varsa
        uyari: "pencere_kisa — giris jeneriginin sonu kacmis olabilir"
cikis → pencerenin İLK karelerinde zaten kredi metni varsa
        uyari: "pencere_gec — cikis jeneriginin basi kacmis olabilir"
```

Bu bir **rapor**tur, davranış değişikliği değil (`kanit.pencere` alanı).
Çağıran böylece pencereyi genişletip yeniden koşabilir. Kaçırma sessiz kalmaz.

## 1. Sözleşme (Kobe/Jordan deseni — değişmez)

```
Girdi(film_id, video=… | kareler=…, bolum="giris"|"cikis", config={})
→ out/<film_id>/<bolum>/
   ├─ vince.json        # karar + TAM kanıt (her satırın soy ağacı)
   ├─ vince.txt         # KESİN + ZAYIF satırlar, ekran sırasıyla
   ├─ vince_supheli.txt # SÜPHELİ satırlar (yalnız varsa)
   └─ _TAMAM            # EN SON yazılır
```

`durum`: **`OKUNDU`** · **`METIN_YOK`** (gerçekten yazı yok) · **`ARIZA`**
(okuyamadık: ffmpeg/model/OOM). **`ARIZA` asla `METIN_YOK`'a dönüşmez.**
Boş `vince.txt` yazılmaz (Nash dersi: `_TAMAM`+boş dosya = sessiz yalan).

**Giriş/çıkış izolasyonu (Kobe kanunu, `tests/test_izolasyon.py` kilitler):**
iki bölümün eşikleri ayrı sözlükte; bölüm modülleri "ben giriş miyim" diye
dallanmaz; yönlendirme yalnız `main.py`'de. Gerekçe: bir bölümün eşiği
diğerine sızarsa kod patlamaz — **sessizce yanlış cevap** üretir.

## 2. Mimari — 4 katman

```
GİRDİ (video | kare dizini)
  │
[1] hazirlik.py ── tek görsel reçete ──────────────────────────────
  │   video → ffmpeg: fps=2, scale=720:-2:lanczos, unsharp=5:5:1.0, jpg q=2
  │   kare dizini → aynı reçete (600x480 PNG de 720'ye çıkar)
  │   → kare_manifesti: sıra, kaynak_sn, sha256, WxH        [KANIT]
  │
[2] üç BAĞIMSIZ gözlem (aynı karelerden; kanallar birbirini GÖRMEZ)
  │   ├─ kanal_ocr.py   PaddleOCR PP-OCRv6 medium (det+rec, latin/tr)
  │   │                 → (metin, bbox, güven, kare_no)    DETERMİNİST
  │   ├─ kanal_vlm.py   Qwen3-VL-8B · faz 0 · 8 kare/grup, bindirme 1, greedy
  │   └─ kanal_vlm.py   Qwen3-VL-8B · faz K · gruplar K kare kaydırılmış
  │                     (AYNI model, AYNI ağırlık — 0 ek VRAM)
  │
[3] birlestirici.py ── kanıt tartısı ──────────────────────────────
  │   normalize → zaman sırasıyla birleştir → kesin tekrar ele
  │   kart kümeleri OCR geometrisinden türetilir (kare kümeleme + Y bandı)
  │   her satır için: ocr_skor · konum_uyumu · faz_tutarliligi · kare_araligi
  │   sınıf: KESİN / ZAYIF / ÇATIŞMA / SÜPHELİ  (§3)
  │   diakritik hakemi: tam Türkçe denklik tablosu, YALNIZ eşleştirmede
  │
[4] main.py ── sözleşme + atomik yazım + _TAMAM
```

### Neden bu kanallar? (konsey turu sonrası — `docs/KONSEY_2026-08-20.md`)

- **OCR (Paddle v6):** dünya bilgisi YOK → ① imkânsız. bbox verir → ② için
  geometrik kanıt ve kart kümesi. **Hakem değil, tanık.**
- **Qwen3-VL-8B:** 13-klip GT yarışının kazananı (%91; 27B %80, MiniCPM %35).
- **Faz-kaydırmalı ikinci koşu (aynı 8B):** ikinci bir VLM yerine bu seçildi.
  7B ölçülmüş olarak zayıf (%80), aynı aile olduğu için "bağımsız hata"
  varsayımı kanıtsız; faz-kaydırma **0 ek VRAM** ister ve ölçülmüş "bedava
  dedektör"ü (okunan yer her koşuda aynı, uydurulan yer farklı) doğrudan
  kullanır. `kanal_vlm_b` (7B) kodda **kapalı deney kolu** olarak durur.

**İki dedektör birbirinin yerine geçmez** (Nemotron uyarısı): faz-tutarlılığı
*rastgele* uydurmayı yakalar, sistematik/bias uydurmayı (`Edith Head` her
koşuda aynı) yakalayamaz — onu yalnız OCR-yokluğu yakalar. Bu yüzden ikisi de
gerekli, ve bu yüzden ikisi de tek başına **hüküm veremez**.

Üçü de ağırlıklarını **paylaşılan zemin**den alır (`~/.cache/huggingface`,
`~/.paddlex`) — MAP.md "ağırlıklar bilinçli istisnadır" kuralı. Ağırlık
dosyalarının sha256'sı kanıta yazılır: model sessizce değişirse görünür.

## 3. Kanıt tartısı (kulenin kalbi)

Her aday satır `s` için üç ölçü — **hiçbiri tek başına hüküm değil**:

```
ocr_skor(s)   = max benzerlik(norm(s), norm(ocr_metni))
                • yalnız s'nin kare aralığı ± pay içinde
                • yalnız aynı Y bandında  ← GLM bulgusu (aşağıda)
                • kutu birleştirme yalnız conf ≥ 0.80 kutularla
faz_tutar(s)  = s, faz-K koşusunda da (normalize) var mı
catisma(s)    = aynı kare+Y bandında OCR BAŞKA bir metin gösteriyor mu
```

> **GLM'in yakaladığı sessiz hata:** uydurulan isim ekranda **başka bir
> satırda** gerçekten varsa (VLM ismi yanlış role taşımıştır — hata ②), salt
> metin eşleşmesi yanlış satırı **KESİN'e terfi ettirir**. Bu yüzden kanıt
> (metin + kare aralığı + Y bandı) üçlüsüdür; konum uymuyorsa kanıt sayılmaz.

| sınıf | koşul | `vince.txt` |
|---|---|---|
| **KESİN** | `ocr_skor ≥ E1` (konum uyumlu) **ve** `faz_tutar` | evet |
| **ZAYIF** | tek olumlu sinyal (yalnız OCR **ya da** yalnız faz-tutarlılığı) | **evet** — işaretli |
| **ÇATIŞMA** | OCR aynı yerde **farklı** metin gösteriyor | evet — `catisma` alanıyla, insan kuyruğu |
| **SÜPHELİ** | **iki** olumsuz sinyal: OCR kanıtı yok **ve** faz-tutarsız | hayır → `vince_supheli.txt` |

**Karantina iki olumsuz sinyal ister** (konsey kararı 1). Tek başına "OCR
görmedi" bir satırı ana çıktıdan atmaz — kayan/stilize jenerikte OCR'ın
kör olduğu, VLM'in doğru okuduğu satırlar tam olarak buradadır ve eski tasarım
onları sessizce yiyordu (MiniMax: *"32/43'ün çoğunu elersiniz — felaket"*).

`E1`, `E2` **kalibrasyonla** (Faz 4) GT yatağında seçilir — elle atanmaz.
**Hiçbir satır silinmez**; sınıfı düşer ve `vince.json`'da gerekçesiyle durur
(Nash dersi: "yok etme, düşür" — madde-imi vetosu 14 gerçek ismi yemişti).

## 4. Ölçüm yatağı — ÖNCE kurulur (eval-harness-first)

`olcum/gt/` ← `Allstar/gt_dizi`'den **kopya** (kaynak+tarih+sha256 `KAYNAK.md`'de).
Kule kendi yatağını taşır; canlı GT'ye yazmaz, ona bağımlı koşmaz.

| film | bölüm | GT satır | klip |
|---|---|---|---|
| cennetin_cocuklari | çıkış | 272 | `cennetin_çocukları_son_1m37s.mp4` |
| marnali | çıkış | 137 | `marnalı_son_02m11s.mp4` |
| cicek_taksi | çıkış / giriş | 89 / 45 | (giriş klibi havuzda yok — kare yolu) |
| suc_dosyasi | çıkış | 88 | `suç_dosyası_29m35s_bitiş.mp4` |
| pastane | çıkış | 67 | `pastane_son_01m30s.mp4` |
| dost_eller | çıkış | 63 | `dost_eller_40m50s_bitiş.mp4` |
| gunes | çıkış | 34 | `güneş_son_27s.mp4` |
| iz_pesinde | çıkış | (yeni `İZ PEŞİNDE ÇIKTI.txt`) | `iz_peşinde_son_01m12s.mp4` |

**Puanlayıcı** (`olcum/puan.py`) — satır dizisi hizalaması:
`difflib.SequenceMatcher` ile sıra-korumalı hizalama, sonra artıklara bulanık
tur (Türkçe-duyarlı normalizasyon: casefold-tr, diakritik-eş, boşluk-eş).

| metrik | tanım |
|---|---|
| **BİREBİR** | normalize eşit |
| **YAKIN** | benzerlik ≥ 0.90 (diakritik/boşluk kusuru) |
| **KAYIP** | GT'de var, çıktıda yok — *en pahalı hata* |
| **FAZLA** | çıktıda var, GT'de yok — *uydurma adayı* |
| **F1** | birincil karar metriği (BİREBİR+YAKIN üzerinden) |

**Sıfır maliyetli taban çizgisi:** `gt_dizi/*/{giris,cikis}_referans_{8b,27b,7b,mini}.txt`
zaten mevcut motor çıktılarıdır. Faz 0'da bunlar GT'ye karşı puanlanır →
**yenilmesi gereken sayı** koşu yapılmadan elde edilir.

## 5. Fazlar ve kapılar

| Faz | İş | KAPI (geçmeden sonrakine geçilmez) |
|---|---|---|
| **0** | İskelet + sözleşme + puanlayıcı + GT kopyası + taban çizgisi | Taban çizgisi tablosu üretildi; testler yeşil |
| **1** | Çalışma zamanı (`venv`, `venv_ocr`) + `hazirlik.py` | Kare manifesti + sha256 yeniden üretilebilir |
| **2** | `kanal_vlm_a` (8B) + tek-kanal uçtan uca | GT yatağında **F1 ≥ taban_8b** |
| **3** | `kanal_ocr` (Paddle) + kanıt tartısı | Kapılı sürüm **FAZLA'yı düşürür, KAYIP'ı artırmaz** |
| **4** | `kanal_vlm_b` (7B) + füzyon + `E1/E2` kalibrasyonu | **F1 > Faz 2** — değilse kanal geri alınır |
| **5** | Havuz B (16 film, GT yok) sağlamlık + öz-tutarlılık raporu | 16/16 `OKUNDU`, çökme yok |

**Geri alma kuralı:** her faz kendi ölçüm dosyasını `olcum/veri/`ye yazar.
Bir faz sayıyı düşürürse **kanal kapatılır**, kod silinmez (bayrakla kapalı).

## 6. Çalışma zamanı (kule sınırı)

- `venv/` ← `jordan/venv` **kopyası** (transformers 5.14.1 + torch 2.11 —
  ölçülmüş Qwen yığını). Kopya, `pip install` yerine: MAP.md'nin pahalı dersi
  ("76 eksik paket skoru %94.5→%92.7 düşürdü") çalışma zamanını dondurmayı
  emrediyor. Kurulumdan sonra `pip freeze > gereksinimler.txt`.
- `venv_ocr/` ← `kobe/venv` kopyası (Paddle 3.3.1 / paddleocr 3.7.0 —
  PIR hatasız ölçülmüş yığın). Ayrı venv, çünkü Nash'in dersi: transformers
  sürümleri kuleler arasında **uyumsuz**; tek venv'de zorlamak riskli.
- Ağırlıklar kopyalanmaz (zemin). Yol + sha256 `config.yaml` + kanıtta.

## 7. Kesin çizgiler

1. **Yalnız `Allstar/vince_carter/` altına yazılır.** Havuzlar, `gt_dizi`,
   diğer kuleler **salt okunur**. GT kopyası kule içine alınır.
2. **Frame beslemesi KANUN** — native video girdisi yasak
   (`jenerik-okuma-frame-catisi`: video beslemede oyuncu eşleşmesi 0/16).
3. `do_sample=False` (üretim tekrar-üretilebilir olmalı).
4. GPU tek: kanallar **sırayla** koşar (8B ~19 GB tepe; 24 GB kartta iki VLM
   aynı anda sığmaz). Koşudan önce boş VRAM denetlenir.
5. Ölçüm yapılmadan hiçbir eşik/kanal "iyileştirme" sayılmaz.
