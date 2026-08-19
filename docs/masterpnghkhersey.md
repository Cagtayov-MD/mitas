# MASTER-PNG — Sıfırdan Bugüne Her Şey (2026-07-31)

Tek konu: jenerik karelerinden tek uzun okunabilir PNG (master) üretimi.
Kaynak: git geçmişi + GUNLUK + karar dokümanları + ölçüm çıktıları + 31 Temmuz oturumu.

## SONUÇ — NE BAĞLADIK (özet)

- **Üretim motoru: İBRAHİMOVİÇ** (eski adı adaptif_slit) — çıkış master'ında TEK motor, yedeksiz.
  Üretemezse sebep manifest'e yazılır, eski master korunur ("kötü master yerine hiç").
- **Giriş master: crop-stack** (ayrı motor) — slit girişte %23 GOOD verdiği için 06-29'da ayrıldı, hâlâ geçerli.
- **V2 (compose_reading_runaware): EMEKLİ** (07-30). Haftalarca süren F-serisi fix kampanyası (M1-M11)
  hiçbir zaman üretime girmedi — bayrak hep 0 kaldı, sonra motor komple değişti.
- **Okuyucu göz: deepseek-ocr** (07-31 turnuvası). Master'ı bant bant deepseek okur; Paddle üçüncü tanık.
- **Sırada:** sentetik master (track_kunye/Ronaldo hattı) İbra'yı metin-recall'da tutarlı geçiyor
  (0.62-0.65 vs 0.55) ama hâlâ harness'ta — Ronaldo-ana-motor ameliyatı "başla" bekliyor.

## VERİM — SAYILARLA

**427-film korpus sağlığı (harness ölçümü, sınıflandırıcı da evrildi — yüzdeler birebir kıyaslanamaz):**
268/427 (%62.8) taban → K4 kalibrasyon 285 (%66.7) → det-fix 331 (%77.5, 3 koşuda 0 film oynaması)
→ M10 şerit-atlası 369 (%86.4) → mod-hatası keşfi: dup metriği kördü, gerçek sağlık %58.3
→ F3b fix: mod hatası 137→13 film. Hedef: 388/427 (%90.9) — hâlâ açık.

**Üretim mevcudiyeti (Database taramaları):**
- 07-06 (263 künyeli film): giriş master %95, çıkış %77, hiç-yok %3.
- 07-09 (294 klasör, 487 segment): giriş %93.9, çıkış %71.8; mevcut olanın %89.1'i OKUNUR.
  Sorunlu 53: tekrar/stitch 27, bulanık 17, hiç metin 9. Eksik 88: detektör kaçırdı 19, gerçekten kredisiz 69.
- 07-31 taze 15-film: çıkış master 14/15 (%93.3), **giriş 0/15** (taze filmlerde giriş master hiç üretilmedi
  — açık sorun); gece testinde runaware master 7/15 filmde üretilmemişti (havuz boş).

**Metin-recall (asıl kalite ölçüsü — ham karelerdeki metnin master'a taşınma oranı):**
- 40-film örneklem (eski V2 çağı): medyan 0.431, %80'i 0.7 altında. En kötü: demir-maskeli-adam 0.005
  (dup=0, manifest OK görünürken tam kompozisyon felaketi — sadakat metriği olmadan görünmezdi).
- 25-film üçlü kıyas (07-29): **adaptif 0.589 | V2 0.522 | V2-kapalı 0.457** → adaptif birincil oldu.
- 40-film üçlü (07-30): V2 ort. 0.469 SONUNCU (2 filmde ~boş master) → V2 tamamen emekli.
- 10-film (07-30): **sentetik 0.653 | adaptif 0.549 | trackTXT 0.524** — sentetik önde ama harness'ta.
- Video-kıyas denetimi: videonun okuduğu 2096 ismin %32.4'ü hiçbir master'da yok (çıkış-only körlük +
  kart düşürme). Router denemesi (%74 doğruluk) dairesel ölçüm çıkınca durduruldu.

**Okuyucu turnuvası (07-31, 8 master, KB-doğrulamalı tam-isim):**
deepseek 297 > qwen8-vLLM 283 (%95 örtüşme) > glm 215 (döngü patolojisi, 1 filmde 5089sn) > gemma 206.
Hız: deepseek/qwen 1-4 sn/bant; gemma 40-80 sn/bant (10-21 dk/film — elenme sebebi).
**Kuantizasyon bulgusu:** aynı qwen8, ollama-4bit 45 satır / vLLM tam-ağırlık 82 satır (POLİS); 155→328 (ÖZEL).
Runtime kalite belirler. Bölünecekse: deepseek→frame, qwen8-vLLM→master (MASTER_GOZU bayrağı, öneri).

## KRONOLOJİ

**Mayıs–Haziran başı:** kare-OCR temeli, K-BoxTrack, slit-scan kavramı (06-02).

**06-13 Doğuş:** master-PNG additive yolu, bayrak-kapalı (compose_hybrid → OneOCR). BRONX 600×2376px
panorama +31 satır. 5-film A/B: 4/5 nötr, 1/5 hafif bozdu. Per-karakter oylama denendi: 1 kazanım/78 kayıp — çöp.
100-film taze test: 22 temiz / 78 sorunlu (FOOTAGE-BLOAT 44, KARIŞIK 16, BOŞ 9, HAYALET 7).

**06-14→22:** slitscan alt-margin + dissolve-dedup + footage-gate (BIBI 22910→7830px, COLUMBIA 3×→1×).
compose_slit/mosaic doğdu (47-film gözle QC: %83 teslime uygun). master_png_monitor.py doğdu (06-21).
Pipeline'a bağlandı: MITAS_MASTER_PNG_AUTO=1 (06-22) — bugün hâlâ canlı zincir bu.

**06-28:** Mosaic motoru EMEKLİ — 47 filmde sadece 1'inde kazandı, orada da daha kötüydü (34 vs 61 satır).
Fix A'nın canlı kodda ölü olduğu bulundu, dispatch tek noktaya (select_master) toplandı.

**06-29 Giriş/çıkış ayrımı:** giriş havuzu doğdu, master'lar film köküne taşındı. Giriş için crop-stack motoru
(slit girişte %23 GOOD). "Kötü master yerine hiç" ilkesi: havuz boşsa master üretilmez; ham frames'e ve
cikis_yazi fallback'ine ASLA düşülmez (GLENN MILLER tabelası / "FIN" sahte-master kanıtı).

**07-03 Dilimleme:** master_png_dilimle (201 master→549 parça, ≤3000px+120px bindirme) + dilim_oku:
109 filme 33.456 satır backfill; 117 taramada 14/17 kayıp yönetmen piksel-teyitli kurtarıldı.

**07-11 HİBRİT-DY:** yedi_numara vakası — metin maskesi %57.6 şişip 105/120 kare atlanınca hayalet isimler
(SEDEF PEHLİVANOĞLU → "SFAFF PEHI OANAGI U"). Fix + profil kilidi: FİLM=eski yol, DİZİ=hibrit (%100 ayrım).

**07-16:** WSL geçişinde kaybolan 4 fix (VLM-rescue, footage-trim, backward-extend, blank-veto) geri getirildi.

**07-17 DENSE kardeş havuz:** smear/collapse kökü bulundu — 1.5fps'te kayan kredi dy≈75px "cut" sanılıyor
→ kart-yığma (HALLERİ smear, MAVZER 854×111 tek-kart collapse, ZENGİN tekrar). Çözüm: havuzdaki gerçek dy
ölçülür, hedef banda (~8px) oturtan fps hesaplanır, kredi videodan yeniden çıkarılır (frames/cikis_jenerik_dense).
MAVZER 854×111 → 854×3257 temiz panorama. Standart 3fps'e çıkarıldı (%17 kare-arası kayma).

**07-23→26 M1-M11 kampanyası (V2):** dup-metriği, 135-film mekanizma sınıflandırması (%76.7 donuk-tekrar),
F1-F3c fix serisi. Dersler: min-3-kare fix'i pilot'ta %91 şişme regresyonu verdi (yakalandı);
hizli-silah'ın "statik kart" etiketi YANLIŞTI (gerçekte kayan liste); NCC eşiği 0.85 kalibrasyon ile çürütüldü
(0.3 ön-filtre + token-oranı 0.70 asıl karar). **Hepsi harness'ta kaldı, üretime hiç girmedi.**
Katman-0 sadakat metriği (text-recall) burada doğdu — dup'un göremediğini o gördü.

**07-26 Adaptif doğdu:** kare-başı metin-maskeli slit, 14-film gözle iterasyon v1→v16 (recall 0.337→0.400,
Sobel fallback ile parti 527→2355px). 07-28: iyileştirme bayrakları (OTSU/DY_SMOOTH/FUZZY/SUBPX) 12-film
benchmark'ı — çoğu filmde etkisiz (SSIM≈0.94-1.0), havaci'de dup %37.3→%9.4.

**07-29 Devrim günü:** 23 ölü kompozisyon fork'u arşive taşındı (arsiv/master-png-fosilleri) — canlı zincirin
tek olduğu kanıtlandı. 25-film kıyasla adaptif BİRİNCİL, V2 yedeğe düştü. hayat-ağacı istisnası: Farsça
karelerde det 0-3 kutu buluyor → çökme kuralı tanımlandı. Aynı gün track_kunye (sentetik master) doğdu.

**07-30:** Kesin adlar — MESSİ (frame hattı) + İBRAHİMOVİÇ (master motoru). V2 tamamen emekli (yedeksiz).
text_layer + slitscan + hibrit görsel dal silindi. Ronaldo (çapraz-birleşim) inşa edildi.
Pilot hat: **Farsça İLK KEZ okundu** (hayat-ağacı, iki ayda hiçbir motor tek satır çıkaramamıştı —
deepseek 19 satır; Otsu fix sonrası havuz 4→40 kare, 19→227 satır).
Ders: konsey fix'leri topluca uygulanınca 0.653→0.471 çöktü — fix'ler TEK TEK ölçülür.

**07-30 gece → 07-31:** track_kunye gölge entegrasyonu üretime bağlandı (MITAS_TRACK_KUNYE=1, ~2-3.5 dk/film).
15-film testi + okuyucu turnuvası (yukarıdaki sayılar) + üretim kalıcı durduruldu (Çağatay talimatı).

## HANGİ FORMATTA İYİ / KÖTÜ ÇALIŞTIK

| Format | Verim | Not |
|---|---|---|
| Kayan yazı (scroll), yeni film | EN İYİ | Slit'in ana sahası; BRONX/MAVZER-dense tipi temiz panorama |
| Sabit kart, normal kontrast | İYİ | Kart-bölme granülaritesi hâlâ en büyük kalan-91 kalemi |
| Giriş jeneriği (kart ağırlıklı) | crop-stack ile İYİ | Slit'le %23'tü; taze filmlerde üretilmeme sorunu açık |
| Eski film (1950'ler) | KÖTÜ | Jenerik-başlangıç tespiti ~%67 başarısız (2000'ler %1) |
| Loş/düşük kontrast metin | KÖTÜ | havaci sınıfı; sentetik master bile burada kaybediyor |
| Farsça/Arapça | ÇOK KÖTÜ→ÇÖZÜLDÜ* | det kutu bulamıyor; *deepseek frame okumasıyla, master'la değil |
| Dublaj + kaynakta kredisiz | ÜRETİLMEZ (doğru) | ZENGİN: kaynakta sadece "The End" — pipeline hatası değil |
| Düşük çözünürlük 512×288 | SORUN DEĞİL | Gözle net; XML "HD" etiketi 3/6 yanlış — meta'ya güvenme |
| Düşük fps arşiv kareleri (1.25-1.5) | KÖK SORUN | Nyquist ihlali, satır imhası — dense'in varlık sebebi |

## HAVUZ ZİNCİRİ

dk-havuzu (frames/cikis, ham) → jenerik-havuzu (frames/cikis_jenerik, credit_detect süzgeci)
→ [koşullu] dense kardeş havuz (cikis_jenerik_dense, ≥5 kare varsa tercih) → İbrahimoviç → master PNG
→ dilimleme (≤3000px) → okuyucu (deepseek bant-okuma / OneOCR-dilim eski yol).
Kurallar: havuz boşsa master YOK; slit yoğunluk ister → manifest'ten TAM yazı-seti derlenir (azaltılmış
havuz eksik master üretir); ham frames ve cikis_yazi asla kaynak olmaz. Giriş %94 kapsama / çıkış %70
(sıkı _accepted kapısı) asimetrisi bilinen açık konu.

## MEZARLIK (denenip gömülenler)

Mosaic motoru · per-karakter oylama (1/78) · cikis_yazi fallback (sahte master) · text_layer ailesi ·
compose_hybrid görsel dalı · slitscan/ klasörü · panoramic/uret_ex (loş filmde eridi) · video-router
(dairesel ölçüm) · V2 + tüm F-serisi (harness'ta kanıt olarak duruyor) · 23 fork (arşiv dalında).
GLM master-okuyucu ve gemma master-okuyucu turnuvada elendi.

## AÇIK İŞLER

1. Ronaldo-ana-motor ameliyatı (sentetik/mix hattını resmileştirme) — "başla" bekliyor.
2. Taze filmlerde giriş master 0/15 + runaware 7/15 üretilmeme — kök sebep incelenmedi.
3. Kalan-91 (kart-bölme granülaritesi) → %90.9 hedefi.
4. deepseek'i vLLM'e taşıma değerlendirmesi (kuantizasyon bulgusu gereği) + ünlü-film-uydurma korkuluğu.
5. Kaynak-havuz asimetrisi (giriş %94 / çıkış %70).
