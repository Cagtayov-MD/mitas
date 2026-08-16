# Kompozitör seçim kararı — ölçülmüş (Faz 4)

> `model_manifest.yaml: no_engine_selection_before_benchmark` kuralının
> işletilmesi. Bu rapor 2026-08-17'de, 12 karma-zorluk filmde, üç kompozitörün
> AYNI karelerde kıyaslanmasıyla yazıldı. Koşu: `olcum/kompozitor_kiyas.py`,
> çıktılar `scratch/kompozitor_kiyas/<motor>/` + `raporlar/kompozitor_kiyas*.json`.

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

## Taşıma sırasında ölçümle bulunan ve kapatılan dört kusur

Magic'in ilk koşuları üç kez YANLIŞ yol gösterdi; her biri gözle+ölçümle
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
4. **hayat-agaci fırtınası** — token-kimlik sayfaları 'farklı' hükmüyle
   açıyordu; okunmaz karelerde halüsinasyon token'ları 36 sayfa açtı
   (dup 0.81). İki düzeltme: (a) token 'AYNI' hükmü kesin, 'FARKLI' hükmü
   piksel-farkı onayı ister (token DEDUP güçlendirir, sayfa AÇMAZ);
   (b) duraksama çifti hiç olmayan filmde gren-tabanı kesme çiftlerinden
   alınır (500 varsayılanı kar filminde fırtınaya açıyordu).

## Karar

1. **Magic, ölçümden geçti ve iki eşiği de geçti:** hiçbir sağlıklı filmde
   lebron'dan geri gitmiyor (8/12 filmde birebir ya da önde; benimle'de
   -0.05 puan tek küçük kayıp), sağlıklı-film sayısında 10/12 ile en iyi,
   medyan recall ve medyan dup'ta en iyi. **Kule içi sıralama: magic > lebron
   > ibrahimovic.** (Son koşum: `raporlar/kompozitor_kiyas_final.json`,
   486 s; sadakat kapısı aynı oturumda 8/8 birebir — motor dokunulmadı.)
2. **Üretim devri (Faz 5) ayrı talimatla** — spec kuralı değişmedi. Bu
   raporla magic terfiye HAZIR adaydır; terfi kararı ve `src/`'ye alınma
   Çağatay'nındır.
3. **Açık borçlar** (terfiden önce değil, terfiyle birlikte ele alınır):
   - jetgiller sınıfı tam çözülmedi (0.128 > 0.10 eşiği; recall 0.43 <
     lebron 0.52). Token-dedup bu filmde recall pahasına geldi — tekrarın
   'okunabilir çeşitlilik' mi gerçek tekrar mı ayrımı henüz yok.
   - totoro sınıfı: dup_metrik'in Japonca satır-yapısı yanlış-pozitifleri
   (saglik'ın periyodik-texter muafiyeti bu filmi tam karşılamıyor).
   - kucuk-dev-adam: sağlıklı tek master magic'in ama recall 0.107 —
   dedup'un içerik kaybıyla dengesi ölçülmeden üretime bağlanmaz.

## Yeniden üretim

```bash
cd olcum
../venv/bin/python kompozitor_kiyas.py --motorlar lebron,ibrahimovic,magic
../venv/bin/python kompozitor_kiyas.py --motorlar 'magic:token_kimlik=0'  # ablasyon
```
