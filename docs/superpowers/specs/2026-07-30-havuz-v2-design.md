# Havuz v2 — "Maks Verim" Kare Seçicisi (Tasarım)

> Onay: Çağatay, 2026-07-30 ("EVET. Plan sende, uygulaması Sonnet'te, kontrolü
> yine sende.") İş bölümü: plan+kontrol Fable, uygulama Sonnet subagent'ları.

## Amaç

Çıkış jeneriği karelerinden, **hiçbir içeriği kaçırmadan**, okunacak sayfa
listesini **OCR'sız** sinyallerle derlemek. Havuz, frame-first künye hattının
(havuz → deepseek-ocr → qwen-yapılandır → KB-doğrula) birinci katmanı ve
Çağatay'ın tespitiyle oyunun kilidi: havuzda olmayan kartı hiçbir okuyucu
okuyamaz.

## İlkeler (Çağatay kararları)

1. **Kaçırmamak her şeyden önce.** Şüphede kal → kareyi AL. GPU dakikası ucuz,
   kaçan isim geri gelmez.
2. **Tavan YOK.** 40-sayfa tavanı ve linspace inceltme kaldırıldı (40 uydurma
   bir sayıydı). Havuz boyutunu film belirler: kısa jenerik ~8, Deadpool-tipi
   150+ sayfa. "Maks verim konuşuyoruz, sınırlandırma değil."
3. **OCR'sız seçim.** Farsça/det-kör filmlerde de çalışmalı (kanıt:
   hayat-agaci, Paddle det 0-3 kutu/kare).
4. **Her adım tek tek, ölçülerek girer.** 2026-07-30 sabahı dersi: 5 konsey
   fix'i topluca uygulandı → 0.653→0.471 regresyon; ayrıştırma yarım gün yedi.
5. **Konsey döngüsü zorunlu:** her adım ölçümü sonrası "denedim, böyle oldu"
   geri-dönüş turu (GLM + Kimi; Kimi bakiyesi şarj olunca üç-sesli).

## Boru hattı (konsey-revizeli sıra)

### 1. Temporal-median ön-filtre
Her karenin gri kopyası, 3-karelik zaman penceresinin piksel-medyanıyla
değiştirilir. Kar tanesi, film greni, interlace tarak-etkisi imzadan silinir.
**Bütün aşağı-akış sinyalleri bu temiz görüntüden hesaplanır**; diske yazılmaz,
okumaya orijinal kare gider.

### 2. Çift-sinyal gruplama (dhash-256)
- **Ardışık-fark, kayan çapayla:** `onceki_h` her karede güncellenir (GLM
  bug tespiti: sabit çapa yavaş kaymada tek kartı 4-5 parçaya bölüyordu).
- **Birikimli çapa-farkı, ayrı eşikle:** grup açılışındaki imzaya karşı
  birikim ölçülür; fade (ardışık farklar küçük, birikim büyük) böyle yakalanır.
- Grup kapanışı: ardışık-fark > eşik **VEYA** birikim > birikim-eşiği
  (birikim-eşiği film-eşiğinden türetilir, örn. `k×eşik`; k, planda 5-film
  yatağında kalibre edilir — spec sabit sayı dayatmaz).
- **Açık risk (ölçümle karar):** konfetili-statik-kart senaryosu (GLM itirazı)
  — temporal-median konfeti farkını düşürmezse kayan çapa geri alınır.

### 3. Film-bazlı eşik: Otsu (mevcut) vs KDE-vadisi (aday)
Mevcut 1D-Otsu kanıtlı (hayat-agaci havuz 4→40, Farsça okuma 19→227 satır);
KDE-vadisi varyantı yanına ölçülür, kazanan kalır. Bimodallik zayıfsa
(ayrım < 0.8) güvenli taraf: `p25+2` (agresif-ALMA).

### 4. Sağır-kapı fix'i
"Yazı görmedim ama içerik değişti" kapısının eşiği `2×eşik` DEĞİL (dar-bantlı
filmde matematiksel olarak hiç açılamıyordu — GLM tespiti); dağılımdan
türetilen marj: `eşik + IQR`.

### 5. Temsilci seçimi düzeltmesi
Grubun temsilcisi **medyan Laplacian'a en yakın** kare — iki ucu da (flaş VE
bulanık) doğal dışlar. ~~Laplacian > film-P95 temsilci olamaz~~ **YANLIŞLANDI
(Task 5 ölçümü, 2026-07-30):** düz-beyaz flaş kenarsızdır → DÜŞÜK Laplacian
verir; P95 kesmesi ayrıca katı `<` ile özdeş-kare gruplarında tersine dönüp
tam da uç değeri seçiyordu. Yerine içeriksiz-kare kapısı: `std < 3` olan
sayfa (düz flaş/boş kart) havuza giremez. GLM'in P95 önerisi ölçümle
çürütüldü — konsey geri-dönüş turuna işlendi.

### 6. Tavansız havuz + istatistiksel alarm + kümeleme kurtarması
- Sabit %60 alarmı YIKILDI (örnekleme fps'ine göre anlamsız).
- Alarm imzası: fark-medyanı düşük (her şey benzeşiyor) **VE** sayfa/kare
  oranı anormal yüksek → `secici_supheli` (manifest'e).
- Kurtarma: "hepsini oku" değil — kareler imza-uzayında bağlantılı-bileşen
  kümelemesiyle (eps = 2×eşik) gruplanır, her kümeden **baş + son** temsilci
  okunur (fade uçları korunur; ~500 sayfa → ~20, kapsam korunarak).

### 7. Delta-enerji ikinci-geçiş sigortası
Okuma bittikten sonra: ardışık iki havuz sayfası arasında ELENEN karelerin
ardışık-fark enerjileri toplanır; toplam, tipik kart-geçişi enerjisini
aşıyorsa o aralıktan en yüksek enerjili 1-2 kare havuza eklenir ve **yalnız
onlar** ikinci tur okunur. Varsayılan AÇIK; `secici_supheli` filmde agresif.
(GLM: "tavansız dünyada daha da kritik — OCR kalite sigortası".)

## İptal edilenler (YAGNI — konsey yıkımı)

- **Merkez-%60 kırpım imzası:** alt-banttan/üstten akan jenerikleri kör eder.
- **R-B renk imzası, CLAHE varyantı:** film-özel numaralar; sigorta katmanı
  alt sınırı koruyor. Gerekirse ölçüm gösterdiğinde eklenir.
- **HSV/renk-delta yazı-maskesi güçlendirmesi:** aday olarak nota alındı,
  bu pakette yok.

## Yapı

- `harness/track_kunye/havuz.py` — bağımsız modül: `havuz_derle(kareler) ->
  HavuzSonucu(sayfalar, esik, alarm, istatistik)`. pilot_hat.py bunu import
  eder; kendi içindeki havuz kodu silinir.
- Üretime DOKUNMAZ; hat harness'te yaşıyor (üretim konumu ayrı karar).

## Test stratejisi (TDD — kırmızı önce)

Sentetik kare dizileriyle birim testler (`harness/track_kunye/test_havuz.py`):
konsey senaryoları test vakası olur:
1. kar fırtınası (beyaz gürültü + sabit metin) → tek grup kalmalı
2. siyah-üstü-siyah düşük kontrast → kart değişimi yakalanmalı
3. fade geçişi (15-kare sönüm) → birikimli sinyal grubu kapatmalı
4. kart üstünde pan → tek grup kalmalı
5. tek-kare flaş → temsilci OLMAMALI
6. konfetili statik kart → tek grup kalmalı (median sonrası)
7. interlace tarak-etkisi → tek grup kalmalı
8. Deadpool-tipi uzun jenerik (100+ içerik) → tümü havuzda, alarm YOK
9. sürünen scroll (fark hep eşik-altı) → delta-enerji sigortası yakalamalı

## Ölçüm protokolü

- Yatak: mevcut 5 film (gercek-yalanlar, karadeniz, 20-bulusma, mufreze,
  hayat-agaci) + 2 yeni: bir eski-TV/interlace adayı + bir uzun-modern
  jenerik adayı (Ex_Frame'den seçilecek).
- Metrikler: havuz boyutu, deepseek satır sayısı, token-recall (şişkinlik
  dipnotuyla), göz-QC (Çağatay + Fable — HER çıktı açılıp bakılır).
- Her boru-hattı adımı AYRI commit + AYRI ölçüm satırı; regresyonda adım
  geri alınır, konseye rapor edilir.

## İş bölümü

- **Fable:** plan (writing-plans), adım ölçümleri, göz-QC, konsey turları,
  kabul/ret hakemliği, commit kapısı.
- **Sonnet subagent'ları:** havuz.py + test_havuz.py uygulaması, plan
  adımlarına sadık, TDD (önce kırmızı test).
- **Çağatay:** nihai QC + yön kararları.

## Karar geçmişi (izlenebilirlik)

- 40-tavan: Fable'ın uydurması olduğu itiraf edildi, Çağatay kaldırttı
  (Deadpool argümanı).
- Sabit dhash eşiği: kök-sebep ölçümüyle yıkıldı (film fark-dilleri:
  hayat-agaci 6-25, gercek-yalanlar 0-112).
- Konsey turları: 2026-07-30 havuz-1 (GLM: 2 bug + KDE + delta-enerji) ve
  havuz-2 kırmızı-takım (GLM: flaş tuzağı, merkez-kırpım iptali, %60 yıkımı,
  DBSCAN kurtarma, sıra revizyonu). Kimi: bakiye askıda — şarj bekleniyor.
- Çift-sinyal çapa: Fable'ın GLM'e itirazı; konfeti karşı-örneğiyle
  "ölçümle karar" statüsünde.
