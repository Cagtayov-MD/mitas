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


---

## GÜNCELLEME (2026-08-17, akşam) — ŞELALE UYGULANDI, ölçüldü

Yukarıdaki "kazanan yok" kararı 8 filmle alınmıştı. GT 36'ya çıkınca iki yeni
yol (ikisi de Çağatay fikri) 18 eğitim / 18 sınav bölmesiyle sınandı:

1. **Sağdan-sola kuralı** — pencere sonundan geriye ilk KALIN içerik bloğu
   (W=30 karede ≥K=12 gerçek kredi-içerik karesi; recall kareleri AYIKLANIR).
   Sınav: ort|Δ| 96, medyan 19 (sinir: 155/122). Zayıflık: izci-yoğun
   filmlerde geç kalıyor.
2. **Ters-motor** — çıkış motoru TERS kare dizisinde koşar; motorun onset'i
   gerçek zamanda jeneriğin bitişidir. Ateşlendiğinde en isabetli aday
   (çoğu ±30 kare) ama 36'nın 16'sında ateşlenmiyor (kredi_yok).

**ŞELALE (ters-motor → kural → sinir)** uygulandı (`src/giris/bitis.py` +
`main.py:_ters_bitis` — izolasyon korunur: src/giris motor import etmez,
aday main'den enjekte edilir). Üretim yoluyla ölçüm (`main.giris_karar`):

| | sinir (önce) | ŞELALE (sonra) |
|---|---|---|
| ort\|Δ\| | 131.8 | **57.0** |
| medyan | ~122 | **~19** |
| çok erken (<−60) | 20/36 | **0/36** |
| ±60 içinde | ~16/36 | **29/36** |
| kaynak dağılımı | — | ters-motor 17, kural 19 |

Kalan borç: 7 film hâlâ >60 geç (ALTIN_YUMRUK +393, YABANDAN +308,
DUNYANIN +294, KOBRA +207 — izci-sınıfı: jenerikten sonra da yoğun
isimli-metin akan filmler). Çözüm yolu: içerik-sınıf ayıracı (kredi-TARZI:
ortalı dizilim/kayan yazı vs diyalog-üstü yazı) — yeni ölçüm maddesi.
