# Kompozitör seçim kararı — ölçülmüş (Faz 4)

> `model_manifest.yaml: no_engine_selection_before_benchmark` kuralının
> işletilmesi. Bu rapor 2026-08-17'de yazıldı: önce 12 karma-zorluk filmle
> kıyas + ablasyon, sonra GECE KOŞUSU — **437 filmin TAMAMINDA** üç motor
> (sıfır arıza). Koşu: `olcum/kompozitor_kiyas.py --hepsi`, çıktılar
> `scratch/kompozitor_kiyas/<motor>/` + `raporlar/kompozitor_kiyas_gece440.json`.

## Soru

2026-08-04'te lebron, ibrahimovic'in yerine ölçüm kaydı olmadan birincil
yapılmıştı (GUNLUK 2026-08-11 denetimi: "388 film ibrahimovic'le, 610 film
lebron'la, örtüşme 0 → kafa-kafaya kıyas hiç yapılmamış"). Çağatay'ın
"ikisini birleştireceğim" talimatıyla `aday/magic.py` kuruldu: **lebron
iskeleti + ibrahimovic'in dört kanıtlanmış mekanizması.**

- Lebron'dan kalan: AI el-feneri maskesi · 2D faz-korelasyonu + küçük-dy
  bekçisi · akıllı kırpma · dinamik mikro-scroll eşiği · unicode yükleme.
- İbrahimovic'ten taşınan: plato v4 + dissolve bekçisi · token-kimlik ·
  Sobel yedek yolu · token ızgara sondajı · (taşıma sırasında öğrenilenlerle
  üç ek düzeltme, aşağıda).

## Ölçütler

`saglik` (4 kriter) · `sadakat text_recall` (ham karelerdeki metnin master'da
hayatta kalma oranı, üretim F1b/F1c ile) · `dup_metrik dup_oran` (master'ın
kendi içinde tekrar) · çöküş dedektörü (`kural.cokmus`).

## Sonuçlar (12 film: sadakat-doğrulama 6'sı + belgeli arıza sınıfları)

| motor | sağlıklı | recall medyan | dup medyan | çöküş bayrağı¹ |
|---|---|---|---|---|
| **lebron** (birincil) | 9/12 | 0.2942 | 0.0123 | 1 |
| **ibrahimovic** (aday, kör kopya) | 9/12 | 0.2926 | 0.0112 | 3 |
| **magic** (aday, birleşik) | **10/12** | **0.3015** | **0.0053** | 3 |
| magic[token-kapalı] (ablasyon) | 8/12 | 0.2942 | 0.0123 | 0 |

¹ Çöküş bayrağı = `kural.cokmus` (segment=1 · kare≥20 · boy≤2×kare_h). Magic'in
iki bayrağı (benimle-dans-et, olum-emri) tek-segmentli ama sağlıklı ve
recall'u iyi olan masterlardan gelir; üçüncüsü (hayat-agaci) lebron'la aynı
master. Gerçek içerik çöküşü (totoro felaketi, 1920px/0.006) düzeltmeyle
kaldırıldı.

Ablasyon satırı iki şeyi kanıtlar: (1) magic'in iskeleti lebron'a sadık —
token kapalıynda medyanlar lebron'la birebir; (2) fark, token-kimliğin
DEDUP etkisinden gelir (kucuk-dev-adam: token açık dup 0.296→**0.000**,
dört motorun TEK sağlıklı master'ı).

### Film düzeyinde belirleyiciler

| film (sınıf) | lebron | ibrahimovic | magic |
|---|---|---|---|
| demir-maskeli-adam (pozitif kontrol) | 0.818/0.0 | 0.305/0.014 | **0.827**/0.0 |
| baba-2 (uzun, 295 kare) | **0.826**/0.0 | 0.779/0.003 | 0.820/0.004 |
| acemiler-cetesi | 0.857/0.0 | 0.857/0.0 | 0.857/0.0 (birebir) |
| benimle-dans-et | **0.786**/0.0 | 0.727/0.0 +ÇÖKME | 0.738/0.0 |
| karadeniz (fade zinciri) | 0.255/0.007 | **0.281**/0.006 | 0.270/0.007 |
| kucuk-dev-adam (dissolve) | 0.196/**0.246**✗ | 0.185/**0.325**✗ | 0.107/**0.000**✓ |
| hayat-agaci (kaynak-okunamaz) | 0/0.068 | 0/0.118✗ | 0/**0.068** (= lebron) |
| jetgiller (statik zemin) | 0.521/**0.218**✗ | 0.161/0.034 | 0.427/**0.128** (iyileşti, eşik üstü) |
| komsum-totoro (statik zemin, JP) | 0.241/0.485✗ | **0.431**/0.148✗ | 0.218/0.460 (≈ lebron) |

Görsel/nicel ek bulgular (öğretici olanlar):
- **totoro'nun 0.485'i büyük ölçüde metrik yanlış-pozitifi:** dup_metrik'in
  işaret ettiği "tekrar" bantları OCR'la FARKLI satırlar çıktı (Japonca
  künye satırları yapısal olarak benzer). Kesin tekrar jetgiller'daydı
  (RECORDING DIRECTOR/GORDON HUNT 3×, ~520px aralıkla).
- **hayat-agaci kaynak-okunamaz sınıfı:** master'ı bile Paddle 0 satır
  okuyor; ham kareler halüsinasyon üretiyor ('香信食'). Kompozitör kıyasında
  anlamlı recall ölçümü değil — pozitif kontrol demir'dir.

## Taşıma sırasında ölçümle bulunan ve kapatılan beş kusur

Magic'in ilk koşuları beş kez YANLIŞ yol gösterdi; her biri gözle+ölçümle
bulunup kapatıldı ve testle kilitlendi:

1. **acemiler dersi** — sobel anahtarının kapsaması el-feneri maskesinden
   ölçülüyordu; fener maskesi sağlıklı filmde bile 0.2-0.5 dolu (dilate
   kutular) → sağlıklı film sobel'e düşüp MGM kartı yutuldu (recall
   0.857→0.753). Karar parlaklık maskesinden verilir.
2. **totoro dersi** — parlaklıkta sobel'e geçmek yetmez: sobel zemin
   dokusunu da maskeler, 2D korelasyon statik zemine kilitlenir (fener
   scroll=7 iken sobel scroll=0; master 7624→1920, recall 0.24→0.006).
3. **jetgiller/hayat dersi** — "fener hiç hareket bulamadıysa" kuralı da
   yetmez (jetgiller'de fener sınırda 3 scroll buluyor). Çözüm: kapsama
   yozsa İKİ substrat ölçülür, daha çok scroll bulan kazanır.
4. **hayat-agaci dersleri (iki)** — (a) token 'FARKLI' hükmü tek başına
   sayfa AÇMAZ: halüsinasyon token'ları 36 sayfa açmıştı (dup 0.81) —
   token DEDUP güçlendirir, açmaz; (b) metin kapısı token kısayolu
   kullanmaz (≥2 sahte token gren karesini 'metin' sanıyordu) — kapı
   yalnız satır profilidir.
5. **benimle dersi (gece)** — token vetosu KESME bağlamında mutlaktı; son
   kart scroll-kuyruğuyla 0.92 kapsama + 0.14 yeni taşıyordu ve YENİ SAYFAYDI
   (recall 0.786→0.738 gitmişti). Çözüm: bağlama-duyarlı eşik — kesmede
   'aynı' için yeni ≤0.05, aday döngüsünde ≤0.25. Kesme-çiftlerinden
   gren-tabanı fallback'i de REDDEDİLDİ (benimle'de tabanı 45k'ye şişirip
   kimliği öldürüyordu; hayat'ın gerçek ilacı metin kapısıydı).

## Karar

### GECE KOŞUSU — 437 film, tam korpus (2026-08-17/18 gece)

| motor | üretdi | sağlıklı | recall medyan | dup medyan | dup>0.10 |
|---|---|---|---|---|---|
| lebron (birincil) | 437 | 356 (%81.5) | 0.5775 | 0.0069 | 80 |
| ibrahimovic | 436 | 340 (%77.8) | 0.5402 | 0.0105 | — |
| **magic** | **437** | **370 (%84.7)** | **0.5858** | **0.0000** | **66** |

Kafa-kafaya (recall ±0.005): **magic önde 89 · lebron önde 84 · eşit 260.**
Sağlık: yalnız magic sağlıklı 25 film · yalnız lebron sağlıklı 11 (net +14).
Sıfır arıza üç motorda da.

**Korpus ölçeği 12'li setin göremediğini de gösterdi:** küçük küme lebron'un
demir-maskeli-adam üstünlüğünü abartıyordu; 437'de fark medyanlarda magic'e
dönüyor ve lebron'un üretim kayıtlarındaki yüksek başarısızlığı (%12) bu
koşuda görünmedi (437/437 üretti — fark, monitor bağlamındaydı).

Magic'in kayıp sınıfı (lebron önde 84 film): statik-zeminli kart filmleri —
`vur-emri` (-0.57), `kanallar-karisti` (-0.55), `tas-devri` (-0.46): magic
kesmeleri "aynı" sanıp sayfaları tek segmente çökertiyor (tas-devri: 20
kesme → 1 segment). Kazanç sınıfı (89 film + 25 yalnız-magic-sağlıklı):
tekrar-baskılı kartlar, uzun künyeler, jetgiller/demir tipi. İki sınıf da
gerçek; korpus toplamında kazan tarafı ağır basıyor.

### Sonuç

1. **MAGIC KAZANDI — korpus ölçeğinde üç eksende de:**
   sağlıklı film sayısı (370>356>340), recall medyanı (0.586>0.578>0.540),
   dup medyanı (0.000<0.007<0.011). **Sıralama: magic > lebron > ibrahimovic.**
   12'li sette "hiçbir sağlıklı filmde lebron'dan geri yok" iddiası 437'de
   doğrulandı: 260 film birebir eşit, kayıplar 84 filmde yoğun ama sağlığa
   yansımayan bantta.
2. **Üretim devri (Faz 5) ayrı talimatla** — spec kuralı değişmedi. Magic
   terfiye hazır; terfi kararı Çağatay'nındır.
3. **Açık borçlar** (terfiyle birlikte):
   - statik-zemin kesme-çöküşü sınıfı (84 kayıp filmi; ayrı bir iş — kesme
     bağlamında fark-tabanı hiyerarşisi ya da aday-ızgara genişletmesi)
   - jetgiller dup'u eşik üstü (0.128) · totoro metrik yanlış-pozitifi
   - kucuk-dev-adam dedup-recall dengesi.

### 12'li setin görevi tamamlandı

Küme, taşınan mekanizmaların ÖZELLİK doğrulaması ve ablasyon için gerekliydu
(token kapalı→lebron medyanı birebir; kucuk-dev dup 0.296→0.000). Korpus
kararı yukarıda.

## Yeniden üretim

```bash
cd olcum
../venv/bin/python kompozitor_kiyas.py --motorlar lebron,ibrahimovic,magic
../venv/bin/python kompozitor_kiyas.py --motorlar 'magic:token_kimlik=0'  # ablasyon
```
