# Nash — ham kare havuzundan jenerik okuma kulesi

> **Ham kare dizini girer, yazı çıkar.** Kareleri sadeleştirir (havuz), kalanları
> okur. Düzeltme yok, yorum yok. Model: DeepSeek-OCR.

**DURUM: Faz 1 tamam — havuz yarısı çalışıyor, okuyucu (Faz 2) bekliyor.**
Model kurulmadan çağrılırsa açık `ARIZA(MODEL)` döner. Ayrıntı: `DURUM.md`.

## Sorumluluk sınırı

**Yapar:** verilen ham kare dizininden temsilci kareleri seçer, onlarda YAZAN
metni okur, kendi `out/`'una yazar.

**Yapmaz:** jeneriğin nerede başladığını aramaz (Kobe'nin işi) · master PNG
üretmez (İbrahimovic) · isim düzeltmez · rol eşlemez (Ronaldo/Phil Jackson) ·
Database'e yazmaz · PDF üretmez · hangi filmin hangi yoldan okunacağına karar
vermez (router değildir).

## Çalıştırma

Kule kendi çalışma zamanını kendi bulur — çağıran hangi python'la koşulacağını
bilmez:

```bash
# TEK film
Allstar/nash/nash tek --kareler /yol/frames/cikis_jenerik --film-id <id>
Allstar/nash/nash tek --kareler /yol/frames/giris --film-id <id> --bolum giris

# TOPLU — kaldığı yerden devam eder, _TAMAM olanı atlar, model BİR KEZ yüklenir
Allstar/nash/nash start --input /yol/kare_dizinleri
```

Çıktı daima `Allstar/nash/out/<film_id>/<bolum>/`. Çağıran çıktı yolunu seçmez.

```
out/<film_id>/cikis/
├─ nash.json     # durum + satırlar + kanıt
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
| Sayfa tavanı | 100 | 40 |
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
> **Bu değişiklik hiç ölçülmedi** — açık borç, `DURUM.md`.

## Testler

```bash
venv/bin/python -m pytest tests -q      # 99 test, GPU gerektirmez
```

## Yerleşim

| Ne | Yol |
|---|---|
| Havuz çekirdeği (SAF — algoritma değişmez) | `src/havuz.py` |
| Dizin → seçim + örnekleme + sigortalar | `src/secim.py` |
| Kareler → satırlar (dedup + gevezelik süzgeci) | `src/okuyucu.py` |
| Modele dokunan TEK yer | `src/model.py` — **Faz 2** |
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

## Tasarım

`docs/superpowers/specs/2026-08-14-allstar-nash-kulesi-design.md`
