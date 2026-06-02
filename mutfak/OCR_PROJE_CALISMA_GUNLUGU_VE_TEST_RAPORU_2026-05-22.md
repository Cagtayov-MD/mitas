# OCR Proje Çalışma Günlüğü ve Test Raporu

Tarih: 2026-05-22

Bu rapor, OCR jenerik/KJ deney hattında bugüne kadar hangi aşamalardan geçtiğimizi, testlerde ne gördüğümüzü, hangi hataları düzelttiğimizi ve sistemin şu an neyi gerçekten yapabildiğini anlatır.

## 1. Başlangıç Noktası

İlk hedef ASR/Tedial tarafına dokunmadan bağımsız bir OCR deney hattı kurmaktı.

Amaç şuydu:

- Film sonu jeneriği, baş jenerik, KJ/lower-third ve logo/yazı benzeri video üstü metinleri okumak.
- Sadece "OCR çalıştı mı?" değil, farklı stratejilerin gerçek videoda işe yarayıp yaramadığını görmek.
- Frame OCR, temporal voting, text-mask motion ve de-scroll/canvas gibi yaklaşımları ölçülebilir hale getirmek.

İlk kritik karar:

- Bunu mevcut `simple.py` veya Tedial OCR akışına bağlamadık.
- Ayrı CLI, ayrı output klasörü ve ayrı rapor yapısı kurduk.
- ASR dosyalarına bilinçli olarak dokunmadık.

## 2. İlk Kurulan Deney Hattı

Ana dosya:

- `core/pipelines/ocr/credit_experiment.py`

CLI:

- `scripts/ocr_credit_experiment.py`

İlk sistem şunları yapacak şekilde kuruldu:

1. Manifest okur.
2. Video segmentinden frame çıkarır.
3. OCR motorlarını sırayla çalıştırır.
4. Frame bazlı OCR sonucu üretir.
5. Temporal voting yapar.
6. Text motion analizi yapar.
7. De-scroll canvas üretir.
8. JSON/Markdown rapor yazar.

Bu aşamada sistem teknik olarak çalışıyordu ama gerçek videoda iki zayıflık hızlıca ortaya çıktı:

- Full-frame canvas yaklaşımı kötü hizalanınca bozuk panoramalar üretti.
- OCR doğruluğunu sadece `confidence` veya `stable group` ile ölçmek yeterli değildi.

## 3. Model ve Engine Sağlık Kontrolü

Kurulu motorlar:

- PaddleOCR
- OneOCR
- EasyOCR
- Tesseract durumu sadece unavailable olarak raporlanacak şekilde bırakıldı.

Sonra EasyOCR devreden çıkarıldı; kullanıcı kararıyla ana adaylar Paddle + OneOCR oldu.

### Paddle Durumu

Paddle için önemli not:

- Paddle bozuk değil.
- GPU/PP-OCRv5 tarafı çalışıyor.
- Problem daha çok kalite/strateji meselesi; sistemsel yükleme hatası değil.

Paddle tarafında model pinleme mantığı eklendi:

- Detection: `PP-OCRv5_server_det`
- Recognition: `latin_PP-OCRv5_mobile_rec`

### OneOCR Durumu

OneOCR için `F:\REPO_GitHub\oneocr` içinden gerekli dosyalar projeye çekildi.

Sağlık kontrolünde aranan ana dosyalar:

- `oneocr.dll`
- `oneocr.onemodel`
- `onnxruntime.dll`

OneOCR sağlık testinde sentetik metinlerde iyi sonuç verdi:

- `ÇAĞATAY İŞLER`
- `MICHAEL DANTE`
- `GÖRÜNTÜ YÖNETMENİ`
- `DIGITAL INTERMEDIATE BY EFILM`

Sonuç:

- OneOCR kullanılabilir.
- Tek başına mucize değil ama Paddle'a tamamlayıcı motor olabilir.
- Fusion henüz aktif değil; kullanıcı önceliği olmadığı için bekletildi.

## 4. Ground Truth ve Deney Kalitesi Tartışması

İlk planın zayıf noktası şuydu:

> Stabil çıkan yanlış metin de stabil görünür.

Bu yüzden ground truth olmadan `F1`, `precision`, `recall`, `CER` gibi metrikler sağlıklı hesaplanamaz.

Bunun için:

- Manifest şemasına `ground_truth` alanı eklendi.
- Değerlendirme fonksiyonları normalize edilmiş metin üzerinden skor üretecek hale getirildi.
- Stable ama yanlış metnin cezalandırıldığı unit test eklendi.

Test:

- `test_ground_truth_scoring_penalizes_stable_wrong_text`

Gözlem:

- Sentetik testlerde F1=1.0 çıkması bizi yanıltıyor.
- Sentetik test kodun doğru çalıştığını gösteriyor ama gerçek strateji kalitesini göstermiyor.
- Gerçek film testleri bu yüzden şart.

## 5. Preprocess ve Türkçe Normalizasyon

İlk preprocess bank çok dardı.

Eklenen/iyileştirilen şeyler:

- `off`
- `auto`
- `always`
- upscale
- inverted upscale
- CLAHE/sharpen tarzı kontrol adımları
- düşük confidence / küçük x-height / düşük kontrast tetikleyicileri

Türkçe normalizasyon için:

- `İ/I/ı/i`
- `Ş/S`
- `Ğ/G`
- `Ü/U`
- `Ö/O`
- `Ç/C`

karşılaştırma ve grouping tarafında fold edildi.

Önemli ayrım:

- Final OCR text tamamen Türkçeye düzeltilmiyor.
- Normalizasyon daha çok karşılaştırma, grouping ve scoring için kullanılıyor.
- Türkçe karakter restorasyonu ayrı post-processing işi olarak hâlâ geliştirilmeye açık.

## 6. De-scroll Canvas Denemesi ve Başarısızlık

İlk büyük gerçek veri denemesinde full-frame canvas/contact sheet üretildi.

Gözlem:

- Bazı canvas'lar yatay/dikey doğru büyüdü.
- Ama çoğu görüntüde arka plan da stitch edildiği için yazı değil sahne panoraması oluştu.
- Hareketli arka plan jeneriği bozdu.
- Full-frame phase correlation jenerik için güvenilir değil.

Kritik sonuç:

> Dünya standartlarında yaklaşım full-frame panorama değil; text layer / bbox / tracking odaklı çalışmak gerekiyor.

Bu yüzden full-frame canvas artık ana çözüm değil, deneysel/yardımcı çıktı olarak tutuluyor.

## 7. Dış Kodların İncelenmesi

Kullanıcı farklı çalışmalardan şu dosyaları verdi:

- `batch_scroll_test.py`
- `scroll_reconstructor.py`
- `test_composite_ocr.py`
- `test_oneocr_composite.py`
- `test_paddle_composite.py`
- `test_row_ocr.py`
- `test_scroll_reconstruct.py`
- `test_vision_ocr.py`
- `approve_hatali_txt.py`

Bu dosyalardan doğrudan kopyala-yapıştır yapılmadı.

Alınan iyi fikirler:

- Full-frame yerine text row / text layer odaklı composite.
- Satır satır crop üretip OCR'ı daha küçük ve temiz bölgelerde çalıştırma.
- Rol/ad ayrımı için composite üzerinde otomatik split denemesi.
- Human review için hatalı/düşük güvenli çıktıları ayrı düşünme.

Alınmayan/ertelediğimiz şeyler:

- VLM tabanlı fallback şu an ana hatta alınmadı.
- Human approval UI henüz yapılmadı.
- Model fusion bekletildi.

## 8. Multi-label Credit Scene Router

Altı farklı yorum ve son değerlendirmeden çıkan en güçlü ortak fikir:

> Jenerik tek sınıf değildir; özellik vektörüdür.

Bu yüzden `CreditSceneRouter` eklendi.

Dosyalar:

- `core/pipelines/ocr/credit_scene_router.py`
- `core/pipelines/ocr/credit_pipeline_selector.py`

Router şunları üretir:

- background type
- text motion
- layout
- difficulty labels
- recommended pipeline

Örnek kararlar:

- `vertical_scroll` ise row reconstruction veya de-scroll denenir.
- `static_card` ise best-frame mantığı tercih edilir.
- `lower_third` ise KJ/lower band ROI düşünülür.
- `multi_column` ise column-aware işlem gerekir.

Gözlem:

- Router sistemi daha açıklanabilir hale getirdi.
- Her şeyi doğru sınıflandırıyor demek için henüz erken.
- Ama "neden bu pipeline seçildi?" sorusuna artık cevap veriyoruz.

## 9. CreditDetector: Jenerik Başlangıcı ve Scroll Tespiti

Sonradan eklenen fikir:

> Jenerik başlangıç tespiti ve scroll mu değil mi sorusu aynı kökten gelir.

Bunun için `CreditDetector` yazıldı.

Dosyalar:

- `core/pipelines/ocr/credit_detector.py`
- `scripts/ocr_credit_detector.py`

Yaptığı şey:

- Video içinde pencereler gezer.
- Her pencereye credit/scroll skoru verir.
- Text-like mask, koyu zemin, satır yapısı ve hareket tutarlılığı gibi sinyalleri kullanır.
- Ardışık yüksek skorlu alanı kredi/jenerik segmenti olarak raporlar.

Gerçek test:

- K-2 filmi
- Başlangıç bilgisi: `01:42:05`
- Sistem 6080-6165 aralığında tarandığında `6125.0` saniyeyi buldu.

Sonuç:

- Bu testte jenerik başlangıcını doğru yakaladı.
- Bu modül değerli ve kalıcı.

## 10. Text-layer Row Reconstruction

Full-frame canvas kötü çıkınca ana yön değişti:

> Ekranı değil, yazı satırını toparla.

Bunun için:

- `core/pipelines/ocr/text_layer_row_reconstruct.py`
- `scripts/ocr_text_layer_row_reconstruct.py`

eklendi.

Yaptığı şey:

1. Frame'lerden yazı yoğun merkezi strip alır.
2. Dikey kayma hızını tahmin eder.
3. Satır odaklı composite üretir.
4. Satır crop'ları çıkarır.
5. Otomatik rol/ad split dener.
6. Row crop OCR için veri hazırlar.

Ürettiği dosyalar:

- `row_composite.png`
- `row_composite_sharpened.png`
- `auto_split.json`
- `row_reconstruct_summary.json`
- `rows/`
- `role_crops/`
- `name_crops/`

Sentetik test:

- Dikey scroll yönü/hızı yakalandı.
- Composite büyüdü.
- Auto-split çalıştı.

Gerçek K-2 testinde:

- İlk başarılı okunabilir jenerik çıktısı bu hatla geldi.
- İsimler Paddle tarafında örnek olarak daha okunur hale geldi:
  - `CHARLES OBERMAN`
  - `JULIA NICKSON-SOUL`
  - `CHRISTOPHER BROWN`
  - `LUCA BERCOVICI`
  - `PATRICIA CHARBONNEAU`

Eksik:

- Rol sütunu hâlâ zayıf.
- Bazı split kararları hatalı.
- Bazı satırlarda OCR karakter bozuyor.

Ama bu aşama gerçek anlamda ilk çalışan yöne geçiş oldu.

## 11. Auto ROI v1/v2/v2c

Kullanıcı özellikle KJ için de OCR gerektiğini vurguladı:

> Tüm frame değil, yazının olduğu alan.

Bunun için Auto ROI geliştirildi.

İlk Auto ROI:

- Pre-OCR text-like mask ile yazı alanı bulmaya çalıştı.
- KJ/lower-third sentetikte başarılı oldu.

Gerçek jenerikte gözlem:

- Pre-OCR mask çoğu gerçek filmde yeterince güvenilir değil.
- Bu yüzden çoğu filmde güvenli center crop fallback'e düştü.

v2c sonucu:

- KJ zemini doğru.
- Gerçek jenerikte güvenli crop olarak işe yarıyor.
- Ama hassas text ROI değil.

Önemli dürüst sonuç:

> Auto ROI v2c üretim seviyesi hassas ROI değil; güvenli başlangıç crop'u.

## 12. Unicode Path Hatası ve Büyük Düzeltme

18 film batch sırasında önemli bir gerçek dünya hatası çıktı:

OpenCV bazı Türkçe karakterli path'lerde okuyup yazamıyordu.

Örnek karakterler:

- `SİNEMA`
- `ÇÖZÜMLEME`
- `ÖFKE`

Problem:

- `cv2.imread`
- `cv2.imwrite`

Windows path'lerinde başarısız olabiliyordu.

Düzeltme:

- Unicode-safe read/write eklendi.
- `np.fromfile + cv2.imdecode`
- `cv2.imencode(...).tofile(...)`

Etkilenen dosyalar:

- `credit_experiment.py`
- `text_layer_row_reconstruct.py`
- `credit_scene_router.py`
- `credit_detector.py`

Sonuç:

- Önceden hatalı/boş görünen row pipeline gerçek batch'te çalışmaya başladı.
- Bu çok kritik bir gerçek veri düzeltmesiydi.

## 13. 18 Film Gerçek Veri Batch

Test klasörü:

- `\\depo01cifs.int.trt.net.tr\sas_h264\testset\filmtest`

Manifest:

- `E:\MITAS\data\ocr_filmtest_last3min_manifest_20260522.json`

Geçerli batch output:

- `E:\MITAS\outputs\ocr_credit_experiments\filmtest_last3min_auto_roi_v2c_unicodefix_oneocr_20260522`

Geçerli rapor:

- `E:\MITAS\mutfak\OCR_FILMTEST_18_AUTO_ROI_V2C_UNICODEFIX_ONEOCR_RAPORU_2026-05-22.md`

Sonuç:

- 18/18 item işlendi.
- 0 failed.
- 13 done.
- 5 partial.

Özet metrikler:

- Toplam frame OCR records: `5308`
- Toplam stable groups: `741`
- Toplam row OCR records: `307`
- Toplam nonempty row pairs: `92`

Auto ROI stratejileri:

- `hint_credit_safe_center_crop`: 16
- `text_density_credit`: 2

Row reconstruct:

- 18/18 çalıştı.
- Motion status:
  - `ok`: 9
  - `static_or_low_scroll`: 9

Auto split:

- `detected`: 11
- `no_clear_column_gap`: 4
- `no_balanced_gap`: 2
- `detected_low_confidence`: 1

Gözlem:

- Sistem artık gerçek 18 film üzerinde kırılmadan çalışıyor.
- Ama "mükemmel jenerik JSON" üretmiyor.
- En değerli çıktı: hangi klipte hangi strateji iş görüyor, nerede zayıf kalıyor bunu göstermesi.

## 14. İkinci-pass OCR Bbox ROI

Son eklenen geliştirme:

> Pre-OCR mask gerçek jenerikte yetersiz. Önce güvenli ROI içinde OCR/detection çalıştır, sonra OCR bbox'larından ikinci-pass ROI rafine et.

Bu bugün eklendi.

Dosya:

- `core/pipelines/ocr/credit_experiment.py`

Yeni davranış:

1. İlk Auto ROI veya full-frame/güvenli crop uygulanır.
2. İlk `frame_ocr` çalışır.
3. OCR bbox'ları toplanır.
4. Çok düşük confidence, çok küçük, çok geniş veya anlamsız bbox'lar elenir.
5. Bbox union + padding ile rafine ROI hesaplanır.
6. Kalite kapısı geçerse kareler yeniden crop edilir.
7. Router ve frame OCR rafine ROI üzerinde yeniden çalıştırılır.
8. Eski ilk-pass OCR `frame_ocr_first_pass.json` olarak saklanır.

Yazılan yeni çıktı:

- `refined_auto_roi_detection.json`
- `frame_ocr_first_pass.json`
- `scene_router_after_refined_roi.json`

Güvenlik mantığı:

- Manifest ROI varsa dokunmaz.
- Multi-column manifest split varsa şimdilik dokunmaz.
- Çok az bbox varsa uygulamaz.
- Bbox union tüm frame'e yayılıyorsa uygulamaz.
- ROI aşırı küçükse uygulamaz.

Unit test:

- `test_second_pass_roi_refines_from_ocr_boxes`

Core test sonucu:

```text
10 passed, 12 skipped
```

Not:

- Bu ikinci-pass ROI henüz 18 film üzerinde yeniden koşulmadı.
- Sıradaki en doğru test budur.

## 15. Şu Anda Sistem Basit Dille Ne Yapıyor?

Şu an programın en düz haliyle yaptığı şey:

1. Videodan seçilen aralığı karelere böler.
2. Eğer manifest'te ROI varsa o alanı kullanır.
3. Yoksa önce yazı olabilecek güvenli bir alan seçer.
4. OCR motorunu çalıştırır.
5. İlk OCR bbox'larına bakıp "asıl yazı burada galiba" derse alanı daha daraltır.
6. Daraltılmış alanda OCR'ı tekrar çalıştırır.
7. Aynı/benzer yazıları zaman içinde gruplar.
8. Sahnenin hareketli mi, scroll mu, kart mı olduğunu tahmin eder.
9. Scroll ise row reconstruction dener.
10. Satır crop'larını ve rol/ad crop'larını üretir.
11. OCR sonuçlarını JSON/Markdown olarak raporlar.

## 16. Şu Anda Gerçekten İşe Yarayanlar

Gerçek veriyle değeri görülenler:

- Unicode path düzeltmesi.
- CreditDetector başlangıç/scroll tespiti.
- Row-first reconstruction.
- Row crop OCR.
- OneOCR sağlık ve gerçek batch çalışabilirliği.
- Router'ın açıklanabilir pipeline kararı.
- Auto ROI'nin KJ/lower-third için doğru zemin kurması.

Kısmen işe yarayanlar:

- Auto ROI gerçek jenerikte çoğunlukla güvenli crop olarak kalıyor.
- Auto split çoğu örnekte çalışıyor ama her düzende değil.
- Paddle/OneOCR ayrı ayrı değerli ama fusion yok.

Zayıf kalanlar:

- Full-frame de-scroll canvas.
- Rol-isim ayrıştırmanın doğruluğu.
- Türkçe karakter restorasyonu.
- Gerçek ground truth olmadan kalite skoru.
- Hareketli arka plan + zor font + düşük kontrast kombinasyonları.

## 17. Sıradaki En Doğru Adımlar

Öncelik sırası:

1. İkinci-pass ROI ile 1-2 kısa gerçek smoke test koş.
2. Sonra aynı yeni kodla 18 film batch'i yeniden koş.
3. `refined_auto_roi` gerçekten alanı daraltıyor mu, OCR record sayısı ve row OCR kalitesi artıyor mu ölç.
4. Auto split başarısız olan örnekleri incele.
5. Single-column / role-name / name-only durumlarını parser açısından ayır.
6. Paddle + OneOCR fusion'ı ancak ROI/row hattı oturduktan sonra ele al.
7. Ground truth örneklerini eklemeden nihai doğruluk iddiası yapma.

## 18. Dürüst Sonuç

Bu sistem artık sadece "OCR deniyorum" seviyesinde değil.

Şu seviyeye geldi:

- Gerçek video alıyor.
- Jenerik/KJ için alan seçmeye çalışıyor.
- Başlangıç/scroll tespiti yapabiliyor.
- Text-layer/row odaklı yeniden kurgu üretebiliyor.
- OneOCR/Paddle gibi motorları deney hattına bağlayabiliyor.
- 18 film üzerinde kırılmadan batch raporu üretebiliyor.

Ama hâlâ şunu söylemek doğru olmaz:

> Her jenerikten doğru, temiz, nihai rol-ad JSON'u çıkarıyoruz.

Doğru ifade şu:

> Jenerik OCR için dünya standartlarına yakın mimari yöne geçtik: ROI, detection bbox, temporal grouping, router, row reconstruction ve ölçüm hattı var. Şimdi bu hattı gerçek veride iyileştirme aşamasındayız.

