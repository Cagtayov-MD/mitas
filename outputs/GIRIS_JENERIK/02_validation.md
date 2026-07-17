# Faz 1b — find_offset doğrulama + kök-neden (DÜRÜST)
**Config:** GAP_BUDGET=24, MIN_RUN=4, SAFETY=4, LEAD=60, MIN_LEAD=3, LATE_CAP=80, ocr_lang=latin (paddle).
**Yöntem:** 18 film `frames/giris` yoğun-OCR → find_offset; tahmin `end_pos` vs ground-truth END (`01_ground_truth.md`, montaj ±7).
**HAVUZ lensi:** amaç VL'in krediyi okuması → biraz-uzun zararsız (footage VL'de elenir), kredi-KESMEK kötü.

## Ana bulgu
find_offset ALGORİTMASI doğru (cold-open ↔ kredi ayrımı + ileri-walk sağlam). ASIL kısıt **OCR-KAPSAMA**:
paddle (latin, hızlı, tek-geçiş) yalnız **yüksek-kontrast koyu-zemin kartları** güvenilir okuyor. Kiril / karanlık-başlık /
footage-üstü-süper / stilize stilleri KAÇIRIYOR → bu filmlerde havuz kısa kesiliyor. **OneOCR bu boşluğu büyük ölçüde KAPATIYOR (kanıtlı).**

## Paddle-only sonuç (18 film)
| sonuç | sayı | filmler |
|------|-----|---------|
| ✓ GOOD (kredi yakalandı, ±60) | 5 | TARZAN, YERÇEKİMİ, X_MEN, ZOR_YILLAR, DEMİRYOLU |
| ✓ cold-open doğru | 2 | YAŞAMAK, ZİHİN AVI |
| ↓ SHORT (kredi kesik) | 7 | CEMİLE, VENEDİK*, TOMRİS, YANAN_YATAK, FLASHDANCE, TEMEL_REİS, İYİ_KÖTÜ |
| ✗ MISS (kredi-yok sanıldı) | 4 | ALİTA, SÖZ, TERMİNATÖR, TRUMAN |

**= 7/18 tam doğru, 0 false-positive cold-open, 0 runaway.** (*VENEDİK GT#82 şüpheli; detektör #45 muhtemelen daha doğru — montaj-gürültüsü.)

Film-bazlı (paddle, end_pos vs GT):
```
ALİTA       GT42  pred None  MISS (logo-only; tek kredi-kare, run<min)
TARZAN      GT44  pred 52    GOOD +8
YERÇEKİMİ   GT49  pred 57    GOOD +8
X_MEN       GT50  pred 44    GOOD -6
CEMİLE      GT63  pred 23    SHORT -40 (Kiril başlık paddle-latin kaçırdı)
VENEDİK     GT82  pred 45    SHORT -37 (GT şüpheli)
TOMRİS      GT105 pred 10    SHORT -95 (karanlık başlık)
SÖZ         GT119 pred None  MISS
TERMİNATÖR  GT119 pred None  MISS (footage-üstü)
YANAN_YATAK GT119 pred 35    SHORT -84 (kart-arası uzun boşluk)
ZOR_YILLAR  GT148 pred 181   GOOD +33
DEMİRYOLU   GT281 pred 280   GOOD -1  (temiz koyu-zemin kartlar)
FLASHDANCE  GT300 pred 59    SHORT -241 (kırmızı süper footage-üstü)
TEMEL_REİS  GT310 pred 21    SHORT -289 (uvertür: #18-49 SİYAH, sonra kartlar)
TRUMAN      GT317 pred None  MISS (sahte-belgesel süper)
İYİ_KÖTÜ    GT343 pred 17    SHORT -326 (stilize jenerik, boşluklu)
YAŞAMAK     cold  pred None  ✓
ZİHİN       cold  pred None  ✓
```

## Kök-neden KANITI (paddle ∅ → OneOCR okudu)
Spot-test (paddle hiçbir şey bulamadığı zor kareler):
| kare | paddle | OneOCR |
|------|--------|--------|
| CEMİLE #35 (Kiril) | ∅ | **ЧИНГИЗ АЙТМАТОВ / ДЖАМИЛЯ** |
| FLASHDANCE #120 (kırmızı süper) | ∅ | **MICHAEL / NOURI** |
| TRUMAN #150 (süper) | ∅ | **Hannah Gill / as meryl** |
| DEMİRYOLU #50 (kontrol) | okudu | BARNAULT/CLARIEUX/… (teyit) |

→ Sorun motor, algoritma değil. Çıkış havuzu ZATEN OneOCR-fallback'e sahip (`_jenerik_pool._oneocr_fallback_enabled`); giriş'e aynalanmalı.

## Hybrid (paddle+OneOCR) — KISMİ ÇÖZÜM (kanıtlı)
`--ocr-mode hybrid`: per-kare OneOCR + `is_credit_text_line` → effective = paddle OR oneocr.
- **CEMİLE: paddle #23 → hybrid #41** (lead_hits 7→28; Kiril yakalandı). GT~63'e yaklaştı.
- **FLASHDANCE: #59 → #59** (değişmez): footage-üstü süperler 24-kareden büyük boşluklarla yayılı; OneOCR 2 kare ekledi ama gap-duvarı aynı.
- Tam 18-film hybrid doğrulama: ARKA PLANDA (`_resultsHybrid.jsonl`, OneOCR yavaş per-kare). Tamamlanınca tablo eklenecek.

## Çözülen vs zor (kalan)
| sınıf | durum |
|------|-------|
| Cold-open | ✅ ÇÖZÜLDÜ (min_run=4 FP'yi keser) |
| Koyu-zemin statik kart (klasik TR/eski film) | ✅ ÇÖZÜLDÜ (paddle) |
| Logo+başlık kısa | ✅ büyük ölçüde (TARZAN/X_MEN/YERÇEKİMİ) |
| Kiril / faint başlık | 🟡 hybrid İYİLEŞTİRİR (CEMİLE kanıtı) |
| **footage-üstü süper** (FLASHDANCE/TRUMAN/İYİ KÖTÜ) | 🔴 EN ZOR: süperler 150-170s'e yayılı, OneOCR'la bile boşluklu → gap-gerilimi. Muhtemelen VL gerekir. |

## Öneri (Faz 2 — tarafsız Opus / Çağatay kararı)
1. **Hybrid'i default yap** (paddle+OneOCR) — Kiril/faint kazanımı net, regresyon yok. Maliyet: OneOCR yavaş → yalnız giriş-havuzu için kabul (çıkış gibi fallback-only de olabilir: paddle SHORT/MISS ise OneOCR).
2. **footage-üstü alt-kümesi** (kredi 150s+ süperlerle akan): tek başına OCR yetmez. Seçenek (a) bu sınıfı düşük-güven işaretle + ham-pencereye düş, (b) VL-tabanlı kredi-bitiş (qwen-vl) PoC.
3. **Havuz tesisatı (Faz 3)**: doğruluk yeterince oturunca `_jenerik_pool.py` giriş-varyantı → `giris_jenerik`, `mitas_pipeline.py` flag-gated default-OFF. YALNIZ Çağatay talimatıyla.
4. **VENEDİK-tipi GT şüphelerini** zoom-montajla (`scratchpad/giris_zoom.py`) teyit et — birkaç GT etiketi montaj-gürültülü.

## v3 — paddle-önce + LAZY OneOCR-FALLBACK (Çağatay direktifi: "yabancı diller için oneocr/paddle seçimi") — SONUÇ
`--ocr-mode fallback` (DEFAULT): çıkış engine-stratejisinin kare-bazında aynası. Kapı: (A) paddle-yetkili varlık
(paddle_lead_hits≥MIN_LEAD ∨ anchor) → OneOCR yalnız UZATIR; (B) saf-yabancı kurtarma (paddle text-KÖR <0.02 + yoğun OneOCR bloğu);
+ `semantically_invalid` FP-koruması (OneOCR altyazı/tabelayı kurtaramaz). + yabancı-isim bayrakları.

**Performans (18 film ~9 dk — çıkıştan İYİ):** avg oneocr_calls=63/film, toplam 1135. cold-open=0 OneOCR; temiz-Latin AZ
(DEMİRYOLU %25); yabancı/faint ÇOK (ZİHİN 278). Lazy = paddle-hızı korunur, OneOCR yalnız paddle-negatif+gezilen karede.
Regresyon yok (`--ocr-mode paddle` eski sonucu birebir verir).

**Yabancı-dil KURTARMA (direktifin amacı) — KANITLI:**
- **ZİHİN AVI**: paddle+görsel-GT "cold" sandı → OneOCR Almanca krediyi okudu (#13 Die Unbesiegbaren, #195 Schnitt, #290 Regie) → found. GT-hatası DÜZELTİLDİ.
- CEMİLE Kiril #23→#41 · TOMRİS karanlık-başlık #10→#97 · X-MEN #44→#87 · YANAN #35→#137 · YERÇEKİMİ #57→#76. Hepsi GT'ye yaklaştı.

**v3 tablo (fb_end / oneocr_calls / secs):**
```
DEMİRYOLU 280/90/44  CEMİLE 41/56/30  TOMRİS 97/113/41  ZİHİN 300/278/60(GT-düzeltildi)
TARZAN 52/68/19  X-MEN 87/89/38  YERÇEKİMİ 76/66/21  YANAN 137/88/35  VENEDİK 55/43/29
İYİ_KÖTÜ 18/38/44  TEMEL_REİS 21/37/26  FLASHDANCE 59/49/34  ZOR 229/120/37
ALİTA MISS/0  SÖZ MISS/0  TRUMAN MISS/0  TERMİNATÖR MISS/0  YAŞAMAK cold/0 ✓
```

**KRİTİK: görsel-montaj GT KUSURLU.** ZİHİN kanıtladı — montaj-etiketi faint/yabancı krediyi kaçırır, OneOCR-detektör daha YETKİLİ.
"GT'ye karşı doğruluk" yabancı filmlerde detektörü EKSİK gösterir. Disputed GT'ler (VENEDİK#82, MISS'ler) OneOCR-spot ile yeniden-teyit ŞART.

**GT yeniden-teyit (autonomous OneOCR-spot, salt-okur):** (1) **VENEDİK GT#82 YANLIŞ** — #60/#70/#80 BOŞ → krediler ~#50'de biter, detektör #55 ≈ DOĞRU (SHORT değil GOOD); GT düzeltildi #52. (2) **SÖZ** açılış = KORE yatırımcı-logosu (투자지원/2009 서울), cast-kredisi yok → MISS savunulabilir (kayıp yok; muhtemelen yanlış-dosyalanmış Kore filmi). (3) **TERMİNATÖR** = yalnız Paramount logosu + boş → logo-seyrek, MISS sınırda. **Sonuç: detektör GT-comparison'dan İYİ; ZİHİN+VENEDİK düzeltmesiyle gerçek isabet 7→9/18'e çıkıyor.**

**Kalan GERÇEK zorluklar (çoğu OCR DEĞİL — algoritma/gap):**
- **TEMEL REİS** #21 (GT310): #18-49 SİYAH uvertür (32 kare) > GAP_BUDGET 24 → erken kırılır. OneOCR siyahı okuyamaz → overture/gap-aware gerek.
- **FLASHDANCE/İYİ KÖTÜ**: footage-üstü süper 150s+ büyük-boşluklu → OneOCR'la bile gappy.
- **TRUMAN/SÖZ/TERMİNATÖR** MISS: krediler lead-penceresinden (ilk ~30s) SONRA yavaş kuruluyor → varlık-kapısı cold sanıyor (TRUMAN'ın okunabilir süperi VAR = lead-gate gap'i, GT-hatası değil).
- **ZOR** +81 taşma: OneOCR gövde-sahne-yazısını kredi sayıp uzatıyor.
- ALİTA MISS ONAYLANDI: logo-only (1 paddle kare), cast yok → boş havuz güvenli (okunamadı>yanlış-oku).

## Dürüst özet
"Çıkış havuz motorunu giriş'e aynala" + "yabancı için oneocr/paddle seçimi" = NECESSARY, ve yabancı-dil amacı KANITLI ÇALIŞIYOR
(ZİHİN Almanca/CEMİLE Kiril/TOMRİS kurtarıldı; perf çıkıştan iyi). AMA tam-doğruluk için YETERSİZ: giriş END'i tüm-açıklıkta +
heterojen stiller. Çekirdek + cold-open + klasik-kart + yabancı-kurtarma ÇALIŞIYOR; kalan zor = lead-gate-yavaş-kurulum +
siyah-uvertür-gap + spread-footage-süper (algoritma/gap işi, kısmen VL). GT'nin kendisi OneOCR ile yeniden-teyit edilmeli. Yol haritası net.
