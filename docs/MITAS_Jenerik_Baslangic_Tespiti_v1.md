# MITAS — Jenerik Başlangıcı Tespiti: Tasarım + Konsey Kararı v1

**Tarih:** 2026-07-21
**Sorun:** Kapanış jeneriğinin GERÇEK başlangıç karesini bul. Mevcut tamamen-OCR
yaklaşımı üretimde %19 not_found (487 film), yaşla güçlü korelasyonlu (1950'ler
~%67 başarısız, 2000'ler %1). Bu, Yol B ve Yol C'nin ORTAK ilk adımı — yanlışsa
master PNG, dilim, okuma, karşılaştırma hepsi bozulur ("yanlış iliklenen düğme").

## Ground Truth
42 etiketli film (`jenerik testpi testi/`), LLM görsel inceleme ile gerçek başlangıç
karesi + hata sınıfı çıkarıldı (`scratchpad/ground_truth.json`). Dağılım: scroll 29,
karma 12, statik 1. Hata: tespit_dogru 16, sahne_metni_yanlis_pozitif 10, diğer 9,
gec_giris_scroll 6, epilog 1. Zemin: siyah 20, görüntü-üzeri 17.

**Başarı kriteri:** 39 ölçülebilir filmde ±15 kare toleransla ≥%90 + ERKEN sınıfının
(60-440 kare erken tetikleme) elenmesi.

## Ölçülen sinyal gücü (GT'den)
- **dy çapraz-korelasyon (scroll):** 32/42 kare-hassas. EN GÜÇLÜ.
- **Statik kart nabzı:** 10 film, scroll'un başarısız olduğu yerlerde tamamlayıcı.
- Alt-kenar parlak-piksel rampası: 11 film, geri-tarama capası.
- İki-sütun hizalama: 9 film, jenerik teyidi.
- Zemin kararması: 10 çalışır / 17 TUZAK. → ÇIKAR.
- Sahne-kesme durması: 0 tek-başına, 7 zararlı. → sadece ön-koşul.

## Konsey turu (2026-07-21, kırmızı takım)
GLM güçlü tur verdi (her iki merceği doldurdu). Kimi rate-limit/timeout (thinking
modeli, 5 deneme). Qwen 401 (hesap). **GLM'in yıktığı noktalar — kabul edilenler:**

1. **Zemin-kararması tamamen ÇIKARILMALI** (doğrulayıcı bile değil): 10 getiri / 17
   zarar. Görüntü-üzeri jenerik (17 film) onu ters çalıştırıyor (LALELER 70→97 YÜKSELİŞ).
2. **Statik kart nabzı KARE değil ZAMAN (saniye) bazlı olmalı.** Telecine/fps farkı
   (18/24fps→25fps) kare-sayısı ritmini bozar. 8-16 kare → fps'e bölünüp saniye penceresi.
3. **Optik-baskı titreşimi (jitter) İz A'yı eski filmlerde öldürüyor olabilir** — 1950'ler
   %67 başarısızlığın MUHTEMEL sebebi. "±2px sabit" kuralı ±1-2px rastgele jitter'da hiç
   tetiklenmez. → jitter-toleranslı: kümülatif monotonik kayma ara, kare-başı katı sabitlik
   değil. (Bunu GT'de doğrulamak için 1950'ler kohortu şart — henüz yok.)
4. **Hakemlik "ilk tetikleyen kazanır" BOZUK.** Karma filmde (scroll→statik geçiş)
   çelişki. → tetikte "onay penceresi" (sonraki ~N kare) aç; statik ritim yakalanırsa
   geri-tarama ile statik kartın başına in.
5. **Geri-tarama "sinyal bozulana kadar" DEĞİL "OCR/ızgara doğrulaması bozulana kadar."**
   Görüntü-üzeri jenerikte kamera pan (dy=1) + yazı kayması (dy=2) toplanır; sinyal-kaybı
   ölçütü sahne içine taşar. İsim/rol ızgarası kaybolunca dur.
6. **9 gizemli erken-tetikleme (metin yok):** İKİ bağımsız açıklama:
   - GLM (format-düzeyi): kodek I-frame hayaleti, stüdyo logosu, letterbox çubuk hareketi.
   - Kimi (sahne-fiziği): **şebeke flicker banding'i (50/60Hz ışık → HER İKİ sinyali birden
     üretir — en güçlü aday)**, telecine gate-weave, kötü deinterlace bob artefaktı (1px
     dikey osilasyon), dikey kamera+pratik ışık (flaşör/şimşek), yükselen parçacık (kıvılcım/
     kar) + titrek ışık. Bonus: sahne içi stilize VHS-roll efekti.
   - ORTAK SAVUNMA: bu mekanizmaların HİÇBİRİ metin-ızgara (iki-sütun) yapısı üretmez.
     Sinyali kabul etmeden önce ızgara doğrulaması ara → yanlış-pozitiflerin çoğu elenir.
7. **30px kör kırpma 480p'de agresif** — jenerik metnini kesebilir. → bandı TESPİT et,
   kör kırpma.
8. **1950'ler test kohortu ŞART** — bu tasarıma bağlanmadan önce blocker. `30.06/` kaynağından
   çekilecek.

## Revize tasarım (v1 prototip)
```
ön-işleme:  head-switching bandı TESPİT+kırp (kör 30px değil)
İz A scroll: satır-profili çapraz-korelasyon → kümülatif monotonik dy (jitter-toleranslı)
İz B statik: merkezi ROI metin-piksel nabzı, ZAMAN-bazlı pencere (fps-normalize)
hakemlik:   onay penceresi — statik ritim varsa statik kartın başına geri-tara
geri-tarama: OCR/ızgara doğrulaması bozulana kadar (sinyal-kaybı değil)
zemin-kararması: KULLANILMIYOR
OCR: sadece doğrulayıcı ("burada isim/rol var mı")
```

## İterasyon 1 sonuçları (2026-07-21) — `credit_onset.py`
Prototip v1→v3, 39 ölçülebilir GT filminde ±15 kare:
- v1 (geri-tarama): %28 — geri-tarama SAHNEYE TAŞIYOR (konsey uyarısı doğrulandı), her şey frame 1.
- v2 (aktivite koşusu): %28 — statik dedektör açılışta tetikliyor.
- **v3 (scroll-birincil): %38** ← checkpoint. GEÇ sınıfı 3/3 tam.

**EN ÖNEMLİ BULGU — sinyal sınırı net çizildi:**
- **Scroll sinyali (dy çapraz-korelasyon) TEMİZ ve GÜÇLÜ, OCR'sız.** Nerede jenerik
  kayıyorsa dy~20 corr>0.9, onlarca kare. Scroll-yöntem tek başına: 8/15 (%53).
- **"Statik" (dy=0+corr>0.9) AYIRT EDİCİ DEĞİL** — yavaş/durgun sahne de aynı
  (VAHŞİ AFRİKA idx0-215 hepsi statik ama jenerik idx221). ATILDI.
- **`izgara_skoru` DOYUYOR** (sahne içeriğinde 1.0), metin-satır otokorelasyon
  denendi (%38→%33 düşürdü) — çünkü BAŞLIK KARTI + sahne-metni de yüksek verir.
- **SONUÇ: sinyal-işleme statik/görüntü-üzeri jenerikte "cast/crew mi başlık mı"
  ayıramıyor — OCR/VLM ŞART.** Tam da MITAS'ın OCR kullanma sebebi. Konseyin
  "OCR doğrulayıcı" dediği yer. 17 görüntü-üzeri film bu sınıfta.

**Scroll over-shoot (ana scroll hatası):** LALELER/ELMA/ÖRGÜT/SEN BEN'de jenerik
STATİK KARTLA başlıyor (GT onu işaretliyor), scroll sonra geliyor → scroll-dedektör
kartı atlıyor, +30..+80 kare geç. Çözüm: scroll onset'ten önce sürdürülen-metin
statik bölge varsa oraya çek (sınırlı, karta kadar — sahneye değil).

## İterasyon 2 (2026-07-21) — OCR KUTU SİNYALİ = ATILIM: %41 → %74
Konsey turu 2 (GLM güçlü, Kimi 429/overloaded): PaddleOCR **detection-only** (rec kapalı,
~0.02 sn/kare) kutu-YAPISI ayırıcısı. `credit_box.py` + `credit_onset.tespit_v4`.
- **Kenar-yoğunluğu sahne kenarlarına DOYUYOR; PaddleOCR GERÇEK metni buluyor.** Sahne 0-1
  kutu, jenerik sürdürülen ≥2 kutu. Geçiş (0→≥2) onset'i işaretliyor. VAHŞİ jenerik-öncesi
  kart izg=0.86 veriyordu ama PaddleOCR 0 kutu — doğru.
- Kutu-BİRİNCİL (scroll-yalnız tetikleme kaldırıldı, letterbox/pan yanlış-tetikliyordu).
  Scroll yalnız kutu-doğrulanmış bölgede kare-hassas iyileştirir.
- Yapı filtresi (GLM): tek-geniş-kutu=başlık elenir, yalnız-alt-%20=altyazı/haber-bandı elenir.

## KRİTİK: GT'NİN KENDİSİ HATALI (konseyin uyarısı doğrulandı)
%74 ölçülüyor ama görsel hakemlikte **6 filmde DEDEKTÖR HAKLI, GT yanlış**:
- BAJA (GT=333, 149 karelik klasör — imkânsız; kare 12'de cast akıyor). Dedektör 3 = doğru.
- SİNDİRELLA (GT=121 ama scroll frame 1'den). Dedektör 9 = doğru.
- 13.CUMA (GT=29 ama "starring BETSY PALMER" kare 3'te). Dedektör 3 = doğru.
- YILDIZ (GT=46 ama "UNIT PRODUCTION MANAGER" kare 21'de). Dedektör 21 = doğru.
- HERŞEY (GT=201 ama "avec par ordre alphabétique" kare 219'da). Dedektör 219 = doğru.
- HANNA (GT=18, CAST kartı frame 1'de beliriyor). Dedektör 1 = sınırda-doğru.
→ **GERÇEK performans ~%87-90.** GT LLM-üretimi, insan-doğrulanmamış. Yanlılıksız yeniden-
  doğrulama workflow'u başlatıldı (wf_05c3ff0a, 10 film, dedektör-çıktısı verilmeden).

GERÇEK dedektör hataları (yeniden-doğrulama sonrası kalanlar): ANNEM (-18 erken-sahne),
URANÜS (-69 erken-sahne), SICAK (+112 görüntü-üzeri kredi kaçtı), UĞURSUZ (-30 sınırda).

## İterasyon 3 (2026-07-21) — %92 HEDEF TUTTU (36/39)
İki düzeltme %74→%92:
1. **HARNESS BUG:** klasörler c_0001'den başlamıyor (BAJA c_0332, HANNA c_0018,
   13.CUMA c_0027). Dedektör 1-tabanlı indeks dönüyordu, GT mutlak dosya numarası.
   `_kare_no()` ile mutlak numaraya çevrildi. Bu tek başına ~5 filmi düzeltti.
2. **GT yeniden-doğrulama (yanlılıksız workflow, dedektör-çıktısı verilmeden):** 6
   filmde GT hatalıydı — ANNEM 303→289, HERŞEY 201→216, SİNDİRELLA 121→120,
   YILDIZ 26→46 (THE END kartı, Çağatay kuralı "THE END tek başına onset değil").

**NİHAİ: 36/39 = %92.** Sınıf bazında: tespit_dogru 16/16, gec_giris 3/3,
sahne_metni 9/10, diğer 8/9, epilog 0/1.

### Kalan 3 gerçek hata — VLM katmanı gerektiriyor (konsey-öngörülü)
- **SICAK (GT=59):** kredi kadın yüzü üstünde, PaddleOCR kutu=0 (düşük-kontrast
  görüntü-üzeri). GLM/Kimi öngörüsü: OCR bulamazsa VLM'e yönlendir.
- **UĞURSUZ (GT=291):** kare 270-284 epilog ŞİİRİ 5 kutu veriyor (metin ama kredi
  değil). Kutu-yapısı şiir/cast ayrımı yapamaz → VLM/okuma gerekir (epilog sınıfı).
- **URANÜS (GT=84):** erken izole seyrek kutu bölgesi gerçek yoğun bölgeyi geçiyor
  — sinyal-mantığı düzeltmesiyle çözülebilir (VLM'siz).

### İterasyon 4 — kalan 3 vaka incelendi, VLM denendi
- **VLM verifier (credit_vlm.py, MITAS_JENERIK_VLM=1):** konsey tie-breaker denendi
  (qwen2.5vl:7b). İYİLEŞTİRMEDİ (%92→%90) — VLM sınıflandırması ince ayrımlarda
  güvenilmez: URANÜS pankartını "kredi" sandı. Varsayılan KAPALI. Kod referans için duruyor.
- **URANÜS (GT=84):** dedektör hatası doğrulandı — kare 25'te protesto PANKARTLARI
  ("INTERNATIONALE") var, PaddleOCR+VLM ikisi de kredi sandı. Gerçek kredi kare 90.
  Kimi'nin "sahne metni/pankart" uyarısı. Overlay-vs-sahne-metni ayrımı hard.
- **SICAK (GT=59):** görüntü-üzeri kredi kısa belirip sahneyle kayboluyor — sürdürülmüyor,
  min_koşu reddediyor. Görüntü-üzeri özel-işleme gerekir.
- **UĞURSUZ (GT=291):** epilog şiiri (270-284) kutu üretiyor; VLM reddetmeli ama
  forward-walk 265'e kadar gitti (şiir-cast geçişi ince).

## NİHAİ DURUM: %92 (36/39), TEMİZ + HIZLI (VLM'siz)
Kod: `credit_onset.tespit_v4` + `credit_box.py`. Varsayılan VLM kapalı — hızlı, harici
bağımlılık yok. 3 residual GENUINE hard edge-case (sahne-pankart / görüntü-üzeri-fade /
epilog-şiir) — bunları zorlamak 42-filme OVERFIT riski (GLM uyarısı).

## İterasyon 5 (2026-07-21) — BÜYÜK HAVUZ (30.06) → v5 TAM-FİLM tasarımı
Çağatay: "39 filmle %92 tarzım değil, büyük havuzda dene." 30.06'da 387 tam-film
(çok eski: 1925 Operadaki Hayalet, 1936 Modern Zamanlar). Validasyon 2 film → %92 ÇÖKTÜ:
- **BILLY YOUNG (1969):** gerçek kredi filmin EN SONUNDA (1137/1200); v4 saloon
  TABELALARINA (kare 401) tetikledi.
- **MODERN ZAMANLAR (1936):** kapanış kredisi YOK (krediler başta); v4 bir ARA-YAZIYA
  tetikledi. Eski filmlerin çoğu böyle.
→ **%92, 42 önceden-kırpılmış KREDİ klibinin yanlılığıydı.** Tam filmde 10dk tail'de
  bol sahne-metni/ara-yazı/gazete var.

**v5 (credit_onset.tespit_v5 + credit_content.py) — konsey (GLM) tasarımı:**
1. Aday kutu-koşuları bul (PaddleOCR det).
2. **OCR-İÇERİK (rec) doğrula:** kredi = SÜRDÜRÜLEN yoğun isim-listesi (BILLY cast 11
   isim/kare, onlarca kare); tabela/ara-yazı/gazete SEYREK veya TEK-kare (MODERN
   arananıyor-afişi). `kredi_skoru_coklu`: ≥yoğun-kare sayısı.
3. **SON-ERİŞİM kuralı:** gerçek kapanış kredisi filmin SONUNA uzanır (son %18); film-
   ortası insert (gazete) erken biter → elenir. MODERN'i temiz çözdü.
4. **"KREDİ YOK" tespiti:** hiçbir aday isim-listesi+son-erişim değilse → None (eski filmler).
Validasyon: BILLY→1137 (doğru), MODERN→KREDİ YOK (doğru). Büyük batch (39 film) koşuluyor.

## BÜYÜK HAVUZ SONUCU (2026-07-21) — GERÇEK SAYI: %73.9 (88/119)
119 tam film (30.06, eski-ağırlıklı), 121-agent görsel doğrulama (6.1M token, 0 hata).
**%92 tam-filme GENELLEŞMİYOR.** Rakam BİMODAL — iki ayrı motor:
- **Kredisiz-film reddedici: %96.8 (30/31)** — ÇOK GÜÇLÜ. Yanlış-pozitif ~yok (1/31).
  "kredi_yok" + son-erişim + içerik tasarımı mükemmel çalışıyor. Bu gerçek bir başarı.
- **Kare-lokalize edici: %65.9 (58/88)** — ORTA-ZAYIF. Kredi VARKEN doğru kareyi bulma.

**Hata sınıfları (kredili filmlerde, asıl iş):**
1. Kare-kayması (19): kredi bulunuyor ama yanlış kare — çoğu DEVASA sapma (+320, +317,
   -188), kalibrasyon değil tamamen yanlış sahne. Modern uzun-metrajlarda (2000+) yoğun:
   jenerik-öncesi sahneyi jenerik sanıyor.
2. False-negative (11): kredi VAR ama "kredi_yok" — sessiz veri kaybı, en tehlikeli sınıf
   (üretimde görünmez). DERSU UZALA, ROBOCOP, VANYA DAYI, KANDAHAR...

**HÜKÜM: ÜRETİME HAZIR DEĞİL.** %92 kırpılmış-klip + kredi_yok bolluğuyla şişmişti.
Gerçek: kredili filmlerde her 3'ten 1'i yanlış. Ama false-positive ÇÖZÜLDÜ (%96.8 reddedici).

**Yön:** (1) kredisiz-reddedici olduğu gibi korunacak — değerli. (2) kare-bulucu AYRI ele
alınacak: devasa-sapma + false-negative vakaları systematic-debugging'e. (3) tolerans netleşmeli
(±20 gevşek; ±5 ise %74 daha da düşer).

## SIRADAKİ FAZ (öneri): kare-bulucu kök-sebep > başka şey
- 1950'ler kohortu testi (`30.06/`) — GLM'in blocker'ı. 42-film scroll-ağırlıklı;
  %92 eski/görüntü-üzeri-ağırlıklı kohortta tutuyor mu? ASIL soru bu.
- Üretim entegrasyonu: `_jenerik_pool.py`'ye credit_box sinyalini bağla (mevcut paddle
  CV dedektörü eski filmlerde cv_start=None veriyordu).
- [x] prototip kodla + GT ölç → v3 %38
- [ ] **Scroll over-shoot fix:** statik-kart-önce-scroll → karta çek (LALELER tipi)
- [ ] **OCR/VLM doğrulayıcı:** statik/görüntü-üzeri aday bölgelerde "cast/crew mi" onayı
  (sinyal aday üretir, OCR/VLM karara bağlar). Bu 40'lık zoru açar.
- [ ] **1950'ler kohortu** (`30.06/`), jitter hipotezini test (GLM'in blocker'ı)
- [ ] 9 gizemli erken-tetikleme: dedektörün ürettiği kareyi vererek mekanizma doğrula
- [ ] İç konsey (konsey_kod) — dedektör kodunu incelet
