# MITAS Bulgu Defteri — 2026-08-01

> Çağatay: *"Bulduk, çözüp ilerleyelim. Atlarsam sen kaydederek gel."*
> Bu defter oturumda **ölçülerek** bulunan her sorunu tutar. Kapanan kapanır,
> açık kalan burada durur. Hiçbir bulgu sohbetin içinde kaybolmaz.

---

## A. KAPANANLAR (commit'li, doğrulanmış)

| # | Bulgu | Kanıt | Commit |
|---|---|---|---|
| A1 | Üretim Paddle'dan hibrit okumaya çekildi | 45 film, **0 fallback** | `05cfbed0` |
| A2 | CI hiç yeşil olmamış — silinmiş teste referans | pytest exit 4, 0 test toplandı | `9eb4f4cf` |
| A3 | CI eksik bağımlılık + `validate_benchmark_yaml` `E:\MITAS` | 7 dosya toplanamıyordu | `7730e838` |
| A4 | ASR normalize testleri ffprobe istiyordu | runner'da ffmpeg yok | `2d309727` |
| A5 | Özette yabancı ada Türkçe İ (`JİMMY`, `EMİLY`) | ŞANSLI FİRAR PDF'i | `466c93b0` |
| A6 | `garble_trigger_olcum` Linux'ta KÖR — **sahte yeşil** basıyordu | "%0 → GEÇ" derken 0 film görüyordu | `40c23236` |
| A7 | Yönetmen kurtarma (etiket + **adres teyidi**) | KUTSAL HAZİNE `kare_teyidi=g_0244.png` | `9afc13dc` |
| A8 | Kurtarma testleri (16) — gerçek üretim tuzaklarıyla | `OF PHOROGRAPHY`, `2nd Unit`, `PRODUCED BY` | `58170418` |
| A9 | Kiril çekim eki: `РЕЖИССЕРЫ` görülmüyordu | ANNA KARENINA satır 29 | `0af7c412` |
| A10 | 7 dil daha (ölçülerek) + `REGISSEUR ASSISTENT` tuzağı | regisseur 10 film, direccion 4, کارگردان 1 | `1bd5b427` |
| A11 | Sahte "Latin-dışı" damgası — model saplantısı | `Судьба` ×1027, %62'si `kutu_n=0` | `4e81185a` |
| A12 | "kimlik çelişkisi" etiketi yokluğa da basılıyordu | 17'nin 14'ü KAYNAK_YOK | `5742150c` |
| A13 | Kimlik hata sınıflandırıcı (6 sınıf) | 286 film: 110 uyuşuyor, gerçek çelişki 7 | `564c46e3` |
| A14 | KB-yönetmen-silme ölçüm kancası + giriş 180→240 sn | ALİE yapımcı kartı 03:16 | `642cb73b` |
| A15 | **500-satır kesmesi yönetmen kartını atıyordu** | `Directed by` satır 1504/1904 | `b4094deb` |
| A16 | **İbrahimovic kolu GİRİŞE kördü** | 47 filmin 29'unda `master_giris`=0 | `b7a88ec2` |
| A17 | Tek master ailesi — kanonik emekli, 525 dosya silindi | runaware 502 korundu | `97655ef1` |

---

## B. AÇIK — sırayla kapatılacak

### B1. Uçtan uca doğrulama YAPILMADI  ⬅ **sıradaki**
A15/A16 birim düzeyinde kanıtlı ama **hiçbir film yeniden koşulmadı**.
"Model artık o satırı görüyor" ile "yönetmen PDF'e çıkıyor" aynı şey değil.
**Yapılacak:** KUTSAL HAZİNE `from_hub` ile yeniden koş (video indirmez).
Tek koşu şunları birden sınar: kesme fix'i · giriş master'ı · gevezelik+piksel
süzgeçleri · kurtarıcı + adres teyidi · yönetmen alanı doluyor mu.

### B2. `ocr_ham.txt` %62 mükerrer — kesme baskısının KÖKÜ
Statik kart 41 karede duruyorsa okuyucum aynı satırı 41 kez yazıyor
(KUTSAL HAZİNE: 1904 satır, 726 tekil). A15 semptomu düzeltti, kök duruyor.
Bugünkü iki süzgeç (gevezelik + `kutu_n=0`) küçültmeli — **ölçülmedi**.

### B3. Frame kolu örnekleme adımı kart atlıyor
`MAX_SAYFA_GIRIS=40`, ham 270 kare → adım ~6.75. KUTSAL HAZİNE'de
`A JOHN HUNECK FILM` kartı (g_0020-0025) iki örnek arasına düştü
(g_0017 timecode → g_0027 Starring). Master kolu emniyet ağıydı, o da yoktu (A16).
**Fikir:** det-kutulu kareleri örneklemede öncelikle (kutu>0 olan kare atlanmasın).

### B4. `vlm_sunucu.sh` port kilidi — video-VL hiç başlayamaz
Port 8100'ü başka projenin container'ı (`odysseus-chromadb-1`) tutuyor;
`durum` yalnız porta bakıp **hep "CALISIYOR"** diyor → sunucu hiç kalkmıyor.

### B5. Hakem VL (video) kurulmadı
Ölçüldü ve hazır: **MiniCPM-V-4.5** (vLLM, ~20 GB, 105 sn kalkış, 3.1 GiB KV,
20 sn blok **2.9 sn**). Kanıt: KUTSAL HAZİNE'de `JOHN HUNECK` + etiket + saniye
döndürdü ve **deepseek'in `CONNICK`'inden DAHA DOĞRUydu** (temiz kart teyit etti).
**Şart (Çağatay ilkesi):** VL isim değil **adres** vermeli — saniye × 1.5 = kare no,
sonra o kareye det sorulur. Adressiz VL, KB'nin yerine geçen ikinci otorite olur.
**Girdi biçimi:** video (yeni havuz YOK), 20 sn blok — kanıtlı reçete.

### B6. Rol-eşleme: etiketin sahibi olmayan komşu isim (3 film)
`YAZ TATİLİ` HERBERT ROSS (koreograf) — **doğru isim bir alt satırda: PETER YATES**
`KARA GÜNLER` "NACH EINER GESCHICHTE VON" altındaki isim
`ÇİNGENE` "2ème assistant réalisateur" altındaki isim
Not: `yonetmen_kurtar` bu üç tuzağı **zaten reddediyor** — çıkarımda kullanılmıyor.

### B7. `CAST_CAP=10` — dizinin "eksiksiz" hedefini engelliyor
Tek env ama **yük taşıyor**: cap farkında olmadan çöp filtresi görevi görüyor.
HAYATIN TUZU'nda düşen "3902 oyuncu"nun içeriği: 8 gerçek isim + kurum-adı kayan
pencere çiftleri + `Q LJDH`, `SOW CINAN` gibi saf çöp.
**Önce** "bu satır gerçek oyuncu adı mı" kapısı, **sonra** cap kalkar.

### B8. KB'yi karardan makyaja indirme
Çağatay kararı, ama **sıra şart**: (1) eşlemeyi sertleştir → (2) hakem VL'yi
adres zorunluluğuyla kur → (3) *sonra* KB'yi indir. Ölçüm okuma katmanını
doğruluyor (110/164), eşleme katmanını değil. Ağı erken çekmek delik açar.
KB-silme ölçüm kancası (A14) takıldı — bir koşu sonra gerçek sayı gelecek.

### B9. JASON KIDD harf kapısı — PDF **alt başlığı** hiç normalize edilmiyor
Teslim edilmiş PDF'lerde bulundu: `MADE İN ITALY`, `SERPİCO`, `RED KİT`,
`RIYA QEŞAYÊ`. `_pipe_pdf.py:503` `subtitle=orig` ham geçiyor; cast/crew/title/özet
normalize ediliyor, **subtitle tek istisna**. Kaynak XML `<TITLE>` zaten kirli
(1998 başlığın 295'i non-ASCII).
**Uyarı:** körlemesine ascii_fold YAPILAMAZ — orijinal ad bazen Türkçe başlığın
kendisi (`AĞAÇ` → `AGAC` olurdu).

### B10. Üretim durgun — 74/1825
Çağatay talimatıyla duruyor. Bugünkü düzeltmelerle yeniden başlatılacak.

### B11. `codex-review` bu dalda hiç koşmadı
Bot "usage limits" dedi, tek kelime geri bildirim yok. CLAUDE.md'nin
"kritik fix → codex-review" kapısı **açık kaldı**. Alternatif: dış konseye
gerçek diff ile bağımsız bug-avı turu.

### B12. `Wiliam` — OCR yanlış okuması (kasa hatası DEĞİL)
HANK WILLIAMS künyesinde `Wiliam Marshall` (tek L) var; yanında `Henr Van`,
`Rolr Peter`, `Stephenson Assoclate` gibi kayan-pencere artefaktları. Bu okuma
kalitesi sorunu; A5'teki kasa düzeltmesi bunu çözmez.

### B13. Rol-model A/B yatağı kurulu ama tek tur koştu
`scripts/rol_model_ab.py` — 6 film × 2 model. Sonuç: `gemma4:26b` (Q4_K_M)
üç filmde cast=0, kontrol filminde farklı yönetmen → **31b Q4_0 kalıyor**.
Denenmemiş adaylar: `qwen36-35b-test`, `qwen3-vl:32b`, `mistral-small3.2`.

---

## D. BU TESTİN KAPSAMI (dürüstlük notu)

29 filmlik KONTROL kohortu **yalnız A bölümündeki kapanan fix'leri** sınar:
500-satır kesmesi · giriş master körlüğü · sahte Latin-dışı damgası ·
yönetmen kurtarma + adres teyidi · giriş penceresi 240 sn · kimlik etiketi ·
özet yabancı-ad kasası · tek master ailesi.

**Sınamadıkları:** B6 rol-eşleme (3 film kohortta bile yok), B2 mükerrerlik kökü,
B3 örnekleme adımı, B5 hakem VL, B7 CAST_CAP, B9 alt başlık, B11 codex-review.
Test yeşil çıksa bile bu kalemler AÇIK kalır.

---

## C. Oturumun dersi

Beş kez model/motor suçlamaya kalktım — FIGO'da üç kez, gemma'da, nicelemede.
**Beşinde de veri durdurdu.** Sorunlar hep taşıma/kesme/etiketleme katmanlarındaydı:

* FIGO çıkışta 0 kare buldu → **doğruydu**, o filmlerin çıkışında jenerik yok
* FIGO girişte 1 kare bıraktı → **doğruydu**, statik kart 1 temsilciye iner
* Bant slate'i künyeyi kirletiyor → 17 eşleşmenin 15'i yanlış pozitifti
* gemma yönetmeni atladı → **görmemişti**, girdi 500. satırda kesilmişti
* Q4_0 niceleme suçlu → daha iyi nicelemeli 26b **daha kötü** çıktı

Çağatay'ın *"işi modelden alma, en fazla modeli değiştir"* refleksi beş kere haklı.
