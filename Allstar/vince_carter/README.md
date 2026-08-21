# Vince Carter — kanıtlı jenerik okuma kulesi

> Giriş ve çıkış jeneriğini okur; **her satırı piksel kanıtına bağlar**;
> kanıtsız satırı silmez, **işaretler**.

Tasarım: `docs/PLAN.md` · Konsey kararları: `docs/KONSEY_2026-08-20.md`
Taban çizgisi: `docs/TABAN_CIZGISI.md`

## Durum — FAZ 0 (iskelet + ölçüm yatağı)

| Faz | İş | Durum |
|---|---|---|
| **0** | Sözleşme + CLI + puanlayıcı + GT kopyası + taban çizgisi | **BİTTİ** |
| 1 | Çalışma zamanı + `hazirlik.py` | sürüyor (ayrı ajan) |
| 2 | `kanal_vlm_a` (8B) + tek-kanal uçtan uca | bekliyor |
| 3 | `kanal_ocr` (Paddle) + kanıt tartısı | bekliyor |
| 4 | `kanal_vlm_b` + füzyon + `E1/E2` kalibrasyonu | bekliyor |
| 5 | Havuz B sağlamlık | bekliyor |

**FAZ 0'da okuma motoru YOKTUR.** `vince tek ...` bilerek
`ARIZA(MODEL_HATASI, "okuyucu henuz kurulmadi …")` döner: sözleşme, CLI ve
atomik yazım çalışır, motor Faz 1+'de takılır. Bu bir hata değil, kapıdır.

## Kullanım

```bash
./vince tek --video <yol> --film-id <id> [--bolum giris|cikis]
./vince tek --kareler <dizin> --film-id <id> [--bolum giris|cikis]
./vince start --input <dizin>          # toplu; _TAMAM olanı atlar
```

`vince` kendi venv'ini kendi bulur — çağıran python bilmez.
`--bolum` varsayılanı `cikis` (kapanış jeneriği, standart yol).

### Çıktı sözleşmesi

Çıktı **daima** `out/<film_id>/<bolum>/` altına yazılır:

```
out/<film_id>/<bolum>/
├─ vince.json         karar + TAM kanıt (her satırın soy ağacı)
├─ vince.txt          KESİN + ZAYIF + ÇATIŞMA satırları, ekran sırasıyla
├─ vince_supheli.txt  SÜPHELİ satırlar (yalnız varsa)
└─ _TAMAM             EN SON yazılır
```

`durum` ∈ `OKUNDU` · `METIN_YOK` (gerçekten yazı yok) · `ARIZA` (okuyamadık).

Değişmezler (`tests/test_sozlesme.py` kilitler):

- **`ARIZA` asla `METIN_YOK`'a dönüşemez** — kuruluşta da, sonradan
  mutasyonla da. Başarısız mutasyon nesneyi bozuk bırakmaz, geri alır.
- **Boş `vince.txt` yazılmaz** (Nash dersi: `_TAMAM` + boş dosya = sessiz yalan).
- **`_TAMAM` en son yazılır**; tüketici kuralı: `_TAMAM` yoksa dosya yok sayılır.
- **Bayat dosya kalmaz**: koşu başında eski çıktılar (önce `_TAMAM`) silinir —
  yoksa `OKUNDU → ARIZA` geçişinde eski `vince.txt` geçerli okuma sanılırdı.
- **`film_id` tek yol bileşenidir** — `/`, `\`, `.`, `..` reddedilir.
- `video` ve `kareler` birbirini dışlar; tam olarak biri zorunlu.

### Giriş/çıkış izolasyonu (Kobe kanunu)

Bölüm yönlendirmesi **yalnız `main.py`'de**; eşikler bölüm-özel sözlükte
(`ESIK_GIRIS` / `ESIK_CIKIS`), `_esik(bolum)` ile çözülür ve motora
**parametre** geçirilir. `src/` altındaki modüller "ben giriş miyim" diye
dallanmaz. `tests/test_izolasyon.py` bunu AST ile tarayarak kilitler (regex
değil — yorum satırındaki metin yanlış pozitif üretmesin diye). `src/` boşken
test SKIP olur, modül belirdiğinde otomatik taramaya başlar.

Gerekçe: bir bölümün eşiği diğerine sızarsa kod patlamaz — **sessizce yanlış
cevap** üretir.

## Ölçüm yatağı

```
olcum/
├─ gt/               GT anlık görüntüsü (gt_dizi'den KOPYA, 2026-08-20)
│  └─ KAYNAK.md      her dosya: kaynak yol + sha256 + satır sayısı
├─ yatak.json        ölçüm yüzeyleri: film × bölüm × GT × klip
├─ puan.py           PUANLAYICI (işin kalbi)
├─ taban_cizgisi.py  yenilecek sayıyı üretir
└─ veri/             ölçüm çıktıları (faz başına)
```

Kule **kendi yatağını taşır**: canlı `gt_dizi`'ye yazmaz, ona bağımlı koşmaz.
`gt_dizi` değişirse `olcum/gt/` otomatik güncellenmez — yeniden kopyalanmalı.

**9 ölçüm yüzeyi** var (8 doğrulanmış + 1 doğrulanmamış). `iz_pesinde/cikis`
GT'si doğrulanmamıştır (`cikis_BELIRSIZ.txt`) — tabloda görünür ama motor
özetine **katılmaz**, Çağatay onayı bekler.

### Puanlayıcı

```bash
./venv/bin/python olcum/puan.py --gt <dosya> --cikti <dosya> [--fark-dokumu]
./venv/bin/python olcum/puan.py --yatak --cikti-kok out/
```

`--cikti` düz `.txt` ya da `vince.json` olabilir; JSON ise satır `sinif`
alanları **sınıf bazlı rapora** dönüşür (konsey kararı 7):
*"SÜPHELİ'ye attıklarım gerçekte doğru muydu?"* — mimarinin recall'ı sessizce
kırıp kırmadığının tek dürüst ölçüsü.

**Normalizasyon YALNIZ karşılaştırma içindir; çıktı metni asla değişmez.**
Raporlar her zaman ham satırı gösterir.

| adım | ne yapar |
|---|---|
| süzme | `#` ile başlayan ve boş satırlar atılır |
| boşluk | baş/son kırpılır, iç boşluklar teke iner |
| Türkçe casefold | `İ→i`, `I→ı` (özel tablo — `str.lower()` yanlış sonuç verir) |
| diakritik katlama | `ı↔i ş↔s ğ↔g ü↔u ö↔o ç↔c â↔a î↔i û↔u` |
| boşluksuz varyant | `SEDA CANPOL A T` ↔ `SEDA CANPOLAT` (hata sınıfı ④) |

Hizalama: `difflib.SequenceMatcher` ile sıra-korumalı (**BİREBİR**), sonra
hizalanmayan boşluklarda yerel bulanık tur ≥ 0.90 (**YAKIN**). Bir GT satırı
yalnız bir kez eşleşir. Kalan GT = **KAYIP** (en pahalı hata), kalan çıktı =
**FAZLA** (uydurma adayı).

`--fark-dokumu` ham F1'in söylemediğini söyler — **neden** kötü:

| sebep | anlamı |
|---|---|
| `FAZLA_UYDURMA_ADAYI` | GT'nin hiçbir yerinde yok (① isim uydurması adayı) |
| `FAZLA_TEKRAR` | aynı metin çıktıda zaten var (⑤ kekeleme) |
| `FAZLA_MOTOR_NOTU` | modelin kendi cümlesi (*"No credit text is visible…"*) |
| `FAZLA_GT_DISI_ESLESME` | GT'de var ama başka yerde (② rol kayması adayı) |
| `KAYIP_ESIK_ALTI` | benzeri okunmuş ama bozuk |
| `KAYIP_HIC_YOK` | hiç okunmamış |
| `YAKIN_DIAKRITIK` / `YAKIN_BOSLUK` / `YAKIN_YAZIM` | YAKIN'ın sebebi |

## Taban çizgisi — yenilecek sayı

`gt_dizi/*/<bölüm>_referans_{8b,27b,7b,mini}.txt` mevcut okuyucuların
çıktılarıdır; **sıfır GPU maliyetiyle** puanlandılar (`docs/TABAN_CIZGISI.md`).

| motor | yüzey | F1 ortalama | havuz F1 |
|---|---:|---:|---:|
| **8b** | 7 | **0.761** | **0.685** |
| 27b | 7 | 0.628 | 0.470 |
| 7b | 6 | 0.614 | 0.533 |
| mini | 7 | 0.555 | 0.397 |

**Faz 2 kapısı: F1 ≥ taban_8b.** Yeniden üretmek için:

```bash
./venv/bin/python olcum/taban_cizgisi.py --yaz
```

## Testler

```bash
./venv/bin/python -m pytest tests/ -q
```

`tests/test_sozlesme.py` · `tests/test_puan.py` · `tests/test_izolasyon.py`
(`tests/test_hazirlik.py` ayrı ajanın dosyasıdır.)

## Kesin çizgiler

1. **Yalnız `Allstar/vince_carter/` altına yazılır.** Havuzlar, `gt_dizi`,
   diğer kuleler salt okunur.
2. **Frame beslemesi KANUN** — native video girdisi yasak.
3. `do_sample=False` — üretim tekrar-üretilebilir olmalı.
4. GPU tek: kanallar **sırayla** koşar.
5. **Ölçüm yapılmadan hiçbir eşik/kanal "iyileştirme" sayılmaz.**
