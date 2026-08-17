# Giriş bitişi — kalibrasyon denemesi ve karar (2026-08-17)

## Ölçülen sorun

İlk GT'li ölçüm (8 film): sinirün bitişi **8/8 filmde ERKEN** (−2 .. −327 kare).
Sebep: footage-üstü jeneriklerde (Yeşilçam stili) metin aralıklı akar; dedektör
ilk sessizlikte "bitti" sanıyor.

## Denenen düzeltme — havuz sinyalinden bitiş türetme

Kobe'nin (b) havuz sinyali (kutu + içerik + dedup, tam pencere taraması) her
filmde 421–479. kareye kadar kredi-benzeri kare buluyor — hem sinirün hem
GT'nin ötesinde (diyalog-isimleri, şarkı sözü, konum yazıları). Tek başına
bitiş oracle'ı değil. Yedi tahminci GT'ye karşı denendi
(`veri/havuz_secili_listeler.json` — seçili kare listeleri):

| tahminci | toplam \|sapma\| (8 film) |
|---|---|
| **sinir (mevcut)** | **965** |
| havuz son karesi | 1808 |
| havuz kantil 0.75 | 833 |
| havuz kantil 0.90 | 1344 |
| gap-cut G=30 | 1365 |
| gap-cut G=60 | 1551 |
| yoğunluk-pencere | 1516 |

## Karar — düzeltme YAPILMADI

1. **Kazanan yok.** En iyi aday (kantil 0.75) 965→833 — 8 filmde fark gürültü
   düzeyinde; film bazında iki yönde de sapıyor (KUZEN +208 geç, DİLEK −25).
   8 film üzerinde eşik ayarlamak GT'ye overfit olur.
2. **Erken bitiş zararsız yön.** Klipte credit KUYRUĞU kaybolur (cast başı
   değil — jenerik başında). Kare havuzu ana artefakt zaten TÜM pencereyi
   tarar; bitişten etkilenmez.
3. **Çağatay notu:** "tam çıkışta mükemmel hassasiyete gerek yok."

**Yeniden değerlendirme koşulu:** GT ≥ 20 film olunca (örnek büyütme
sürüyor) veya içerik-sınıf ayıracı (kredi vs diyalog-ismi) yazılınca.
