# Birleştirici — kanıt tartısının tam tasarımı

> Faz 3–4'ün uygulama şartnamesi. Belirsizlik bırakmaz: burada yazmayan bir
> eşik/kural koda girmez, koda giren her eşik burada gerekçesiyle durur.

## Girdi

| ad | içerik |
|---|---|
| `manifest` | `[{sira, dosya, kaynak_sn, sha256, genislik, yukseklik}]` |
| `ocr` | `[{kare_no, metin, bbox:[x1,y1,x2,y2], guven}]` |
| `vlm[faz]` | `[{grup_no, kare_araligi:[a,b], satirlar:[str]}]` — faz ∈ {0, K} |

## Adım 1 — koşu içi görünüm (her faz için ayrı)

Gruplar zaman sırasıyla birleştirilir. Jordan kuralı korunur: **yalnız kesin
tekrar** düşer — son `kesin_tekrar_penceresi=12` satır içinde aynı
casefold+boşluk imzası varsa satır görünümden düşer, düştüğü `kesin_tekrarlar`
kanıtına yazılır. **Bulanık eleme YOK** (`Ahmat` ve `Ahmet` iki ayrı adaydır).

Her aday satır taşır: `metin`, `ilk_grup`, `kare_araligi`, `tekrar_sayisi`.

## Adım 2 — fazlar arası hizalama

`faz0` ve `fazK` satır dizileri, puanlayıcının hizalama işleviyle hizalanır
(`SequenceMatcher` + ≥0.90 bulanık tur, Türkçe katlamalı).

```
faz_tutar(s) = s bir karşı-faz satırıyla ≥0.90 hizalandı mı
```

Birleşim listesi sıra korunarak kurulur. **Tek fazda görünen satır ATILMAZ** —
grup sınırı etkisiyle gerçek satır tek fazda kalabilir; kararı OCR verir.

## Adım 3 — OCR satırlarının kurulması (kare içi)

Kutular kare içinde **satır bantlarına** toplanır:
- iki kutu aynı banttadır ⟺ dikey merkezleri, ikisinin ortalama yüksekliğinin
  %60'ından az ayrışır;
- bant içi sıralama `x1`'e göre; birleşim `" "` ile.

**Üç aday türü birden üretilir** (ÖLÇÜMLE düzeltilmiş kural —
`docs/OLCUM_OCR_RECALL.md`):

| aday | nasıl | ağırlık |
|---|---|---|
| `bant_guclu` | yalnız `guven ≥ 0.80` kutular birleşti | tam |
| `bant_tum` | tüm kutular birleşti | düşük — `zayif_birlesim: true` |
| `kutu` | tekil kutu | tam |

> Konsey kararı 5 ("zayıf kutu birleşime girmesin") **ölçümle düzeltildi**:
> pastane'de iki-sütunlu 5 gerçek satır (`Hacer—SERPİL TEZCAN` gibi) tam da
> bu kural yüzünden kanıtsız kalıyordu. Zayıf birleşim **etiketlenir**,
> yok edilmez. Aday üretmek bedava; hüküm veren skordur.

Her OCR satırı: `{kare_no, metin, y_orani = y_merkez/kare_yuksekligi,
guven_min, tip, zayif_birlesim}`.

## Adım 4 — kanıt (metin + zaman + konum ÜÇLÜSÜ)

Aday satır `s`, kare aralığı `[a,b]`, pay `P = 8 kare` (config: `kanit.kare_payi`):

```
adaylar = [a-P, b+P] aralığındaki tüm OCR satırları
ocr_skor(s) = max benzerlik(norm(s), norm(aday))
```

`norm` = puanlayıcının normalizasyonu (Türkçe casefold + diakritik katlama +
boşluksuz varyant). En iyi eşleşmenin `kare_no`, `y_orani`, `guven_min`
değerleri saklanır.

### Konum tutarlılığı — GLM'in yakaladığı sessiz hata

> Uydurulan isim ekranın **başka bir yerinde** gerçekten varsa, salt metin
> eşleşmesi yanlış satırı KESİN'e terfi ettirir.

VLM bir grubun satırlarını **yukarıdan aşağıya** verir. Dolayısıyla aynı grubun
kanıtlanmış satırlarının `y_orani` değerleri de **artan** olmalıdır.

```
konum_uyumlu(s) = s'nin y_orani'ı, aynı gruptaki komşu kanıtlı satırların
                  y sırasını bozmuyor  (Kendall uyumu; tek ihlal toleransı 1)
```

`konum_uyumsuz` ise `ocr_skor` **kanıt sayılmaz** (0'a çekilir, ham değeri
kanıtta `ocr_skor_konumsuz` olarak durur — görünürlük).

### Çatışma — hata sınıfı ② (rol↔isim kayması)

```
catisma(s) = s'nin eşleştiği bant, aynı karede FARKLI bir metin taşıyor
             ve 0.30 ≤ benzerlik ≤ 0.75
```

Bu aralık kasten dar: 0.75 üstü "aynı satırın OCR kusuru", 0.30 altı "alakasız
metin". Arası = *aynı yuvada başka içerik* → insan bakmalı.

## Adım 4b — KANIT ÇAPASIYLA KÜMELEME (en büyük kesinlik kaldıracı)

**Bulgu (2026-08-21, taban çizgisi ölçümü):** marnali'de mevcut 8B çıktısı
476 satır üretmiş — **hepsi benzersiz**, ama GT 128 satır. Yani sorun tekrar
değil, **mutasyon**:

```
ŞÜKRÜ TİRKİŞ
ŞÜKRÜ TIRKİŞ      ← aynı fiziksel satır, üç farklı okuma
ŞÜKRÜ TIRKIŞ
```

Kesin-tekrar elemesi bunları yakalayamaz (imzaları farklı). Bulanık metin
elemesi de **yapılamaz** — `Ahmat` ile `Ahmet` gerçekten iki ayrı kişi olabilir
(Jordan kuralı). Çıkmaz gibi görünüyor; kanıt katmanı çözüyor:

> **Üç varyant da AYNI OCR satırıyla, AYNI karelerde, AYNI Y bandında
> eşleşiyor. Demek ki tek bir fiziksel satırdır.**

```
capa(s) = ( norm(s.ocr_eslesen_metin), s.ocr_kare_araligi )
aynı çapa + örtüşen kare aralığı  ⇒  aynı fiziksel satır
```

- Küme temsilcisi: `ocr_skor` en yüksek olan; eşitlikte faz-tutarlı olan;
  yine eşitlikte ilk görülen.
- Diğer varyantlar **silinmez**, `varyantlar[]` alanında durur.
- Kanıtsız satırlar (OCR eşleşmesi yok) **kümelenmez** — çapaları yoktur,
  ayrı aday kalırlar. Bu kasıtlı: pikselde karşılığı olmayan iki satırın
  "aynı şey" olduğunu iddia edecek dayanağımız yok.

**Neden metin benzerliğiyle değil çapayla:** iki ayrı kişinin adı asla aynı
OCR kutusuna denk gelmez. Çapa fiziksel, benzerlik ise tahminidir. Bu kural
`Ahmat`/`Ahmet` ikilemini de doğru çözer: ekranda iki ayrı satırsa iki ayrı
çapaları olur, tek satırsa zaten tek çapa.

**Yan kazanç — diakritik onarımı bedava gelir:** temsilci seçimi `ocr_skor`'a
göre yapıldığı için, OCR'ın `ŞÜKRÜ TİRKİŞ` okuduğu yerde VLM'in `TIRKIŞ`
varyantı elenir. Adım 6'nın hakemliği bu kümelemenin üstüne biner.

## Adım 5 — sınıflandırma

| sınıf | koşul |
|---|---|
| **KESİN** | `ocr_skor ≥ E1` (konum uyumlu) **ve** `faz_tutar` |
| **ZAYIF** | tam olarak bir olumlu sinyal (`ocr_skor ≥ E2` **veya** `faz_tutar`) |
| **ÇATIŞMA** | `catisma` — sınıf bağımsız olarak işaretlenir, çıktıda KALIR |
| **SÜPHELİ** | `ocr_skor < E2` **ve** `faz_tutar` yanlış — **iki olumsuz sinyal** |

`E1`/`E2` Faz 4'te GT yatağında taranarak seçilir (`olcum/kalibre.py`).
**Izgara ölçümle daraltıldı** (`docs/OLCUM_OCR_RECALL.md`): GT satırlarının
%91,5–100'ü OCR'da ≥0.70 benzerlikle var, ama yalnız %61–96'sı ≥0.90 —
yani `E1 ≈ 0.90` gerçek satır eler. Izgara: **`E1 ∈ [0.62..0.82]`**,
**`E2 ∈ [0.45..0.65]`**. Seçim ölçütü: **F1 maksimum, KAYIP artışı sıfır** —
kesinlik uğruna duyarlılık satılmaz.

## Adım 6 — diakritik hakemliği (ÖLÇÜLECEK, varsayılan KAPALI)

VLM satırı ile OCR eşleşmesi diakritik katlandığında eşit ama diakritikte
ayrışıyorsa (`YETIM` ↔ `YETİM`), hangisi yazılacak?

```yaml
diakritik_hakem: kapali | ocr_kazanir | vlm_kazanir   # varsayılan: kapali
```

Üç ayar da GT yatağında ölçülür, **BİREBİR sayısını en çok artıran** kazanır.
`ocr_kazanir` yalnız `guven_min ≥ 0.90` eşleşmelerde uygulanır. Hakemlik
uygulandığında satırın `hakem: {onceki, sonraki, kaynak}` kanıtı yazılır —
metin sessizce değişmez.

## Adım 6b — kırpım hakemi (hedefli yüksek-çözünürlük yeniden okuma)

Adım 6'nın kör hakemliği yerine **bakarak karar ver**. Yalnız ihtilaflı
satırlar için, yani tüm satırların küçük bir azınlığı için çalışır.

Tetik: satırın OCR eşleşmesi diakritik-katlamada eşit ama diakritikte ayrışıyor,
**ya da** `catisma` işaretli.

```
1. eşleşen OCR kutusunun bbox'ını al (en yüksek güvenli kare)
2. kutuyu %15 payla kırp → 3× lanczos büyüt → unsharp
3. iki hakem (config ile seçilir):
   a. paddle_kirpim : aynı Latin tanıyıcı, tek kırpım üzerinde
   b. vlm_kirpim    : tek görüntü + "Transcribe this single line exactly."
4. hakem çıktısı, iki adaydan hangisine daha yakınsa o kazanır
   (eşitlikte VLM'in ilk okuması korunur — değişiklik için kanıt gerekir)
```

**Neden bu, kör hakemlikten iyi:** `YETIM` ↔ `YETİM` ikileminde "OCR daha
güvenilir" gibi ölçülmemiş bir kural yerine, o tek satırın **daha iyi
görüntüsüne** bakılır. Maliyet küçük: ihtilaflı satır sayısı × bir küçük çağrı.

**Ölçüm zorunlu.** Üç ayar (`kapali` / `paddle_kirpim` / `vlm_kirpim`) GT
yatağında koşulur; BİREBİR'i en çok artıran kazanır, KAYIP'ı artıran elenir.
Beklenen kazanç büyük: bilinen canlı koşuda 43 satırın **11'i** yakın-yanlıştı
ve çoğu diakritik/boşluk kusuruydu — bu satırlar BİREBİR'e dönerse skor
32/43'ten 40+/43'e çıkar. Bu yüzden bu adım "süs" değil, **en büyük tekil
kaldıraç**tır.

Uygulanan her değişiklik `hakem: {onceki, sonraki, kaynak, kirpim_kare}`
kanıtıyla yazılır. Metin sessizce değişmez.

## Adım 7 — çıktı

- `vince.txt`: KESİN + ZAYIF + ÇATIŞMA, ekran sırasıyla, düz metin.
- `vince_supheli.txt`: SÜPHELİ satırlar (yalnız varsa).
- `vince.json`: her satır için tam soy ağacı —
  `{metin, sinif, ocr_skor, ocr_kare, y_orani, guven_min, faz_tutar,
    catisma, kare_araligi, ilk_grup, hakem}`
  \+ koşu kanıtı: model sha256, kare manifesti özeti, ffmpeg reçetesi,
  faz ayarı, eşikler, `kayma_hizi` ölçümü, `kesin_tekrarlar`.

## Ölçülmeden yazılmayacaklar (açık borç listesi)

1. **Paddle'ın satır-bazında recall'ı** — üç konsey üyesinin ortak uyarısı.
   Faz 3'ün İLK işi: GT satırlarının kaçı OCR'da (≥0.90) var? Bu sayı düşükse
   (`<%60`) `E1` kapısı gerçek satır eler ve tasarım yeniden düşünülür.
2. **Faz kaydırma miktarı** (`K=4`) — 2, 4, 6 denenip tutarlılık sinyalinin
   ayırt ediciliği ölçülmeden sabitlenmez.
3. **Diakritik hakemi** — yukarıda.
4. **3./4. faz** — 2 faz yetmezse; her faz tam koşu maliyeti.
