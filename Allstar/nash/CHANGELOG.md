# Nash kulesi — değişiklik günlüğü

## 2026-08-20 — Metin izli ana jenerik okuyucusu

- Genel kutu tracker'ı yerine jeneriğe özel, kare başına bire-bir metin izi
  eklendi. Metin benzerliği, öngörülen hareket, bbox ve kırpım dHash birlikte
  kullanılıyor; hızlı scroll satırları artık aradaki karelerde parçalanmıyor.
- Scroll satır sırası, ilk görülme anı yerine doğrusal hareketten hesaplanan
  ekran-ortası geçiş zamanına bağlandı. Statik kartlar ayrı zaman grubunda.
- Her izden keskin ve zamansal olarak dağılmış üç kırpım seçiliyor;
  `PP-OCRv6_medium_rec` ikinci okuyucu, Türkçe Tesseract yalnız uyuşmazlık
  hakemi. Çatışmada kaynak metni koruyan sıkı kabul kapıları eklendi.
- Giriş kredi penceresi, küçük sahne yazısı ve layout aykırı süzgeçleri yalnız
  birleşik zamansal/geometrik/parlaklık kanıtıyla çalışıyor. Başlangıç hiçbir
  zaman kırpılmıyor; yoğun koyu scroll koruma altında.
- Global isim dedup yapılmıyor. Yalnız en az üç satırlık ardışık tekrar blok ve
  yakın karedeki zayıf, en az 0,96 benzer OCR varyantı temizleniyor.
- Sıralı fuzzy kabul aracı `olcum/jenerik_kabul.py` eklendi. 16 tam jenerik /
  4.966 kare 16/16 `OKUNDU`; KONTES ALICE, Çiçek Taksi 1, Marnalı ve SUÇ
  DOSYASI hedefli gerçek-kare regresyonları ayrıca doğrulandı.
- DeepSeek üretimde kapalı; Nash'in ana Latin okuyucusu v5 detector sonucu +
  v6 çok-kırpım uzlaşmasıdır.
- `olcum/okunmalik_toplu.py`, `Belgeler/okunmalık jenerikler` altındaki video
  ve MXF örneklerini 2 fps karelere ayırıp giriş/çıkış olarak Nash'e veren,
  kesinti sonrası devam edebilen ve tek `rapor.json` üreten kabul koşucusudur.

## 2026-08-20 — QC sözleşme ve zincir güvenliği

- Nash zincirde Kobe havuzu/sonucundan bağımsız, ana kare diziniyle bölüm
  başına bir kez çalışır; Kobe havuzu yoksa yalnız LeBron/Jordan atlanır.
- `film_id` yol geçişine kapatıldı; `Cikti.yaz` da aynı doğrulamayı uygular.
  Eski `_TAMAM` işareti `tek` başında kaldırılır, final atomik marker-last
  yazımı korunur.
- Düşük-güvenli makul Paddle OCR, kapalı DeepSeek fallback altında artık
  `ARIZA(CIKTI_BOZUK)` verir; yalnız gürültü/noise `METIN_YOK` olarak kalır.
- Bozuk `secim`/`okuma`/girdi override türleri `YAPILANDIRMA` ARIZA'sına
  çevrilir; toplu komut herhangi bir ARIZA varsa sıfır-dışı biter.

## 2026-08-19 — Dizi girişi altyazı-elemesi bölme-özel + kırpım-keskinleştirme iskeleti

- `altyazi_y` seçim katmanında (`metin_secici`) bölme-özel override ve okuma
  katmanında (`hibrit`) `ham_tavan` deseninde bölme sözlüğü desteği: giriş
  bölmesinde kural kapalı, çıkışta değişiklik yok. Gerekçe: Çiçek Taksi GT —
  dizi açılış kredileri altyazı geometrisinde; iki katman da doğru okunan
  satırları eliyordu. Kişi 17→24/29.
- `kirpim_keskinlestir` iskeleti: `worker_komutu` test-edilebilir ayrıldı,
  worker'a `--kirpim-keskinlestir` bayrağı + `kirpim_keskinlestir()`
  dönüşümü (2× lanczos + unsharp 5x5/1.0) eklendi. Ham-havuz A/B ölçümü:
  25→26/29 (ÜMİT YESİN düzeldi), zarar sıfır. Kule koşusu ve config
  açılması ayrı iş.
- Testler: +5 (bölme-özel eleme ×2, kırpım dönüşümü ×2, bayrak borulama ×1),
  toplam 163 geçti.

## 2026-08-18 — Hibrit ana-havuz okuyucusu

- Düşük satır/güvende Arabic → ESlav yönlendirmesi eklendi. Hedef alfabe %35
  ve satır yeterlilik kapıları zorlanıyor. ESlav devralmasında Latin satırlar
  ikinci tanıyıcıyla çapraz doğrulanıyor; Arabic çift-dilli kartlarda yüksek
  güvenli, zamansal destekli ve ayrı kutudaki Latin kredi korunuyor.
- Gerçek kapılar: `cag_output20` 71 Kiril + sıfır homoglif Latin;
  `cag_output23` 294 Arabic/Farsi + görüntüdeki gerçek `CPR`.
- Paddle 3.3.1 / PaddleOCR 3.7.0 ayrı CUDA 12.6 worker venv'ine alındı;
  Torch/DeepSeek CUDA 13 ile NCCL ve VRAM ömrü ayrıldı.
- Ana havuz full OCR, temporal satır uzlaşması, altyazı/logo/geçiş süzgeci ve
  koşullu Arapça/Farsça Paddle tanıyıcı eklendi. DeepSeek fallback kodu
  korunup config'te kapatıldı; Nash ağır model yüklemiyor.
- Detection `PP-OCRv6_medium_det`, Türkçe recognition resmî
  `latin_PP-OCRv5_mobile_rec`; yerel ağırlıklarla ve dış ağsız üretim.
- DeepSeek üretimi 1024 varsayılan / 2048 sert tavan, 30 sn, EOS 1, pad 2 ve
  tek ağır iş kuralıyla sınırlandı. `mitas.okuma/v2` bbox kanıtı korunuyor.
- Worker OCR için açtığı ndarray'i dHash için de kullanıyor; ana süreç PNG'leri
  ikinci kez açmıyor. Temporal kümeleme aktif pencere, trigram/uzunluk ön
  filtresi ve yoğun kayan jenerik tek-kare vetosuyla sınırlandı. En ağır
  239-kare örnek 70,9 sn'den 26,7 sn'ye indi; yedi bozuk tek-kare varyantı
  atıldı, gerçek `MUSTAFA VURAN` ayrıştırıldı.
- Final gerçek test: 29 video/7.414 kare, 29/29 OKUNDU, 2.583 satır, 372,64 sn,
  sıfır DeepSeek. İç peak 333,9 MB; canlı süreç 556–622 MiB. 2 fps yoğun
  örnekte 280 satır/26,6 sn, 3 fps 279 satır/36,9 sn; 2 fps korundu.
- Nash 152 test (1 atlandı), Sheriff 68 test geçti; iki venv `pip check` temiz.

## 2026-08-14 — Faz 1: kule kuruldu, havuz yarısı çalışıyor

**Kule ayakta.** Ham kare dizini girer; havuz derlenir, temsilci kareler seçilir,
karar `out/<film_id>/<bolum>/nash.json` + `_TAMAM` olarak yazılır. Okuyucu
(Faz 2) kurulmadığı için gerçek koşu `ARIZA(MODEL)` döner — **bilerek görünür
bir eksik**, kule tahmin etmez.

### Eklendi
- `sozlesme.py` — `OKUNDU` / `METIN_YOK` / `ARIZA`, 5 arıza sınıfı, atomik
  yazım + `_TAMAM` en son.
- `src/havuz.py` — `harness/track_kunye/steve_nash.py` **birebir** taşındı
  (yalnız docstring başlığı değişti).
- `src/secim.py` — dizin→seçim; üretimde üç ayrı yere dağılmış örnekleme ve
  iki sigorta (son-kare, ham-kuyruk) tek yerde toplandı.
- `src/okuyucu.py` — fold-dedup, gevezelik süzgeci, sağlık dedektörü. Modeli
  bilmez (`sor` geri-çağrısı) → tamamı GPU'suz test edilebilir.
- `main.py` + `nash` + `config.yaml` — CLI (`tek` / `start`), toplu kuyruk.
- `olcum/referans_uret.py` + `olcum/kapi1.py` — taşıma kapısı.
- 99 test (havuz 25 taşındı + 74 yeni), GPU gerektirmez.

### Ölçüldü
- **KAPI 1: 29/29 birebir aynı, sapma sıfır** (15 film × çıkış+giriş yüzeyi).
  Kule, bugünkü üretim koduyla aynı havuz istatistiğini üretiyor.

### Düzeltildi (üretimden devralınan kusurlar)
- **"Havuz boş" ikiye ayrıldı.** Üretimde (`_pipe_track_kunye.py:178`) iki
  farklı gerçek tek kutuda: kareler okundu-ama-içeriksiz mi, hiçbiri
  açılamadı mı? Kule ayırır: `METIN_YOK` / `ARIZA(KARE_OKUNAMADI)`.
- **`sayfa_hata_n` sayılır.** Üretimde patlayan sayfa `continue` ile sessizce
  atlanıyor; 12 sayfadan 9'u okunmuş çıktı "tam" görünüyordu.
- **`dusurulen_n` doğru hesaplanıyor.** Referans
  (`olcum_yatagi_faz2.py:147`) atamadan sonra çıkarma yapıyor → daima 0.

### Uygulama sırasında düzeltilen iki kendi kusurum
- **Sağlık bayraktır, hüküm değil.** İlk halde her olumsuz sağlık sonucu
  `ARIZA(CIKTI_BOZUK)` üretiyordu; testler yakaladı — 150 karakterlik gerçek
  bir kısa jenerik ARIZA olup içeriği çöpe gidiyordu. Artık yalnız
  `garble_yuksek` arıza üretir, `cok_kisa` kanıta yazılır.
- **`nash.txt` yalnız `OKUNDU`'da yazılır.** Gerçek koşuda görüldü: boş bir
  `nash.txt` + `_TAMAM`, metni okuyan tüketiciye "yazı yok" gibi görünüyor ve
  ARIZA/METIN_YOK ayrımını yutuyordu.

### Kayda geçen bulgu (Nash'in dışı)
- `e1a201d5` (2026-08-05) `film_esigi`'nin Otsu aramasını yeniden yazdı —
  *"O(n) optimizasyonu"* diye, ama **cevabı değiştiriyor**. MOBY DICK 1'de
  eşik 28→13, sayfa 15→165 (11×). Hangisinin doğru olduğu **ölçülmedi**.
  Ayrıntı: `DURUM.md`.

### Bekleyen
- **Faz 0′** — sadakat sondajı (Ollama vs transformers, aynı kareler).
  Çağatay onayı gerekiyor: ~6.7 GB model indirme.
- **Faz 2** — okuyucu kule içine (`src/model.py`, `model_kur.sh`).
- **Faz 3** — üretim geçişi + `harness/track_kunye` sökümü.
