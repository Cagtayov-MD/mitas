Kod kanıtları teyit edildi. Bir kritik çapraz kontrol daha: dedektörün çıkış taraması (`close_start = dur - 900s`) ile sabit pencere (`dur - 240s`) arasındaki 660s körlük iddiası. `close_start` = son 15dk, pencere = son 4dk — yani dedektör 15 dk içinde HER YERİ tarar, körlük yok aslında. Bu noktayı düzelteceğim. Tüm kanıtlar elimde, sentezi yazıyorum.

# Adım 2 Davranışı — Mantık Hatası Var mı?

## Kısa cevap

Evet, **bir gerçek mantık hatası var** ve Çağatay'ın hipotezi temelde doğru. Düşük güvende dedektör bulduğu konumu **tamamen atar** ve dar 4 dk pencereye düşer (`mitas_pipeline.py:1365` else-dalı `_cik_start`'a hiç dokunmaz). Asıl kötü olan: bu durumda `_detect_changed=False` kalır, bu yüzden tek kurtarma mekanizması olan **sonuç-temelli yedek hiç çalışmaz** (`:1499`). Diğer bulguların çoğu (giriş/çıkış asimetrisi, head=180s tabanı, timeout) kasıtlı ve doğru tasarım.

## Gerçek mantık hataları

### 1. Düşük güvende dedektör konumu atılır VE yedek devre dışı kalır (Çağatay'ın hipotezi)
- **Ne:** Dedektör jeneriği buluyor ama `conf < 0.60` (ve scroll değilse), `_accept_credit_detect` False döner. O zaman `_cik_start` 240s sabit varsayılanda kalır — dedektörün okuduğu konum **çöpe atılır**.
- **Neden hata:** Belirsizlikte daralma. "Nerede olduğundan %55 eminim" bilgisi, "hiçbir şey bilmiyorum" muamelesi görüyor. Daha kötüsü, pencere sabit kaldığı için `_detect_changed=False` olur (`:1389-1391`, ABS farkı 0) → sonuç-temelli yedek `_detect_changed` şartına takılıp **hiç tetiklenmez** (`:1499`).
- **Hangi filmde patlar:** Çıkış jeneriği son 15 dk içinde ama son 4 dk'nın DIŞINDA, `conf 0.45-0.60`, `type=static`. Örn. 80 dk film, jenerik 65. dk'da (4. dakikalık kuyruğun dışında), statik beyaz-metin/siyah-zemin (modern TRT yapımı), conf=0.55 → pencere son 4 dk'da kalır, jenerik tamamen kaçar.
- **Kod kanıtı:** `scripts/mitas_pipeline.py:1365` (else-dalı `_cik_start`'a dokunmaz) + `:1389-1391` (`_detect_changed` sadece pencere koordinatına bakar) + `:1499` (yedek `_detect_changed` şartlı).
- **Düzeltme fikri (uygulamadan):** Düşük güvenli tespit reddedilse bile, dedektörün bulduğu konum sabit pencereden DIŞARIDAysa `_detect_changed=True` zorla → sonuç-temelli yedek devreye girsin (az satır çıkarsa sabit pencereye düşer, zararsız). Daha temiz alternatif: düşük güvende pencereyi atmak yerine **birleştir** — `_cik_start = min(detected_start-5, sabit_start)` yaparak hem dedektör bölgesini hem sabit kuyruğu kapsa (pencere genişler, isim kaçmaz, fazla footage'ı CLIP eler).

### 2. Çıkış koşulunda `end_sec=None` korunmuyor (giriş korunuyor)
- **Ne:** Giriş dalı `end_sec is not None` kontrol eder (`:1342`); çıkış dalı sadece `start_sec is not None` kontrol eder (`:1365`), `end_sec` None gelirse `_ce = 0.0 + 10.0 = 10s` olur.
- **Neden hata:** Asimetrik guard. `end_sec=None` döndüğünde çıkış penceresi `_cik_start+30s` tabanına çöker; gerçek jenerik 10 dk sürüyorsa tamamı kaçabilir. Ve `_detect_changed=True` olduğu için yedek tetiklenir AMA yalnızca `ocr_lines < 30` ise — uzun jenerikten 30+ satır çıkıp yanlış (kısa) pencere korunabilir.
- **Hangi filmde:** Dedektör `start_sec=5000, end_sec=None, found=True` döndüren çıkış jeneriği (şema None'a izin veriyor); jenerik 5000-5600s ise pencere 4995-5025s'de kalır, 575s kaçar.
- **Kod kanıtı:** `scripts/mitas_pipeline.py:1342` (giriş guard'lı) vs `:1365,1368` (çıkış guard'sız, `_ce = float(_closing.get("end_sec") or 0.0) + 10.0`).
- **Düzeltme fikri:** Çıkış koşuluna giriş'le simetrik `and _closing.get("end_sec") is not None` ekle; None ise sabit pencereye düş (zaten kurtarıcı davranış).

### 3. (Şartlı) 7 dk altı içerikte çıkış jeneriği hiç işlenmez
- **Ne:** `dur_sec > (180+240+5) = 425s` koşulu sağlanmazsa çıkış kareleri (`nf_c`) hiç çıkarılmaz, sadece giriş penceresi OCR'lanır. Sonuç-temelli yedek de aynı 425s şartını taşır (`:1500`) → kısa içerikte yedek de yok.
- **Neden şartlı hata:** TRT arşivinde 7 dk altı içerik (kısa dizi bölümü, haber, fragman) **varsa** kesin patlar; yoksa moot. Bu bağımlılık doğrulanmadı, o yüzden #1 ve #2 kadar kesin değil.
- **Kod kanıtı:** `scripts/mitas_pipeline.py:1292` + `:1500`.
- **Düzeltme fikri:** Kısa içerikte de basit "son N saniye" çıkış penceresi çıkar (dedektörsüz), ya da eşiği içerik tipine göre düşür.

## Kasıtlı tasarım (garip ama doğru)

- **Giriş `head` 180s tabanından inmez, çıkışta taban yok:** Bilinçli — giriş jeneriği parçalı/aralıklı olabilir (kural yorumu `:1295`), çıkış genelde tek blok. Fazla giriş footage'ını CLIP eler (`_pipe_ocr.py:431-449`).
- **Uzun-scroll istisnası sadece `type=scroll`:** Bilinçli (`:1333` yorumu). Statik title-card'da çalışmaması bir boşluk ama #1 ile aynı kök — ayrı hata değil.
- **`_cik_start = min(_ds, _cik_start)` no-regress:** Doğru; pencere asla geri gitmez.
- **360s timeout → sabit pencere:** Doğru fail-safe (`:1384`), pipeline çökmez.
- **`_cik_end` en az 30s tabanı:** OCR çekme penceresinin minimumu, jenerik süresi tahmini değil. Doğru emniyet payı.
- **`--parallel` CLIP lock'u:** Thread-güvenli (`jenerik_detector.py:825-831`), VRAM çift kullanılmaz. Doğru.
- **Giriş kareleri çıkıştan sonra çıkarılır:** Ayrı klasörler, sıra önemsiz. Bug değil.

## Tartışmalı (iyileştirilebilir)

- **0.60 güven eşiği kalibre değil:** Manuel seçim, env ile override edilebilir. Dedektörün kendi `LOW_CONF=0.55`'inden farklı/bağımsız olması kafa karıştırıcı ama production'da ayarlanabilir.
- **Yorum "film-sonuna GİTME" yanıltıcı:** Kod aslında `min(dur_sec, ...)` ile film sonuna **gidebilir**; yorum yanlış. Dokümantasyon tutarsızlığı, bug değil.
- **CLIP çökerse tüm kareler OCR'a girer:** `_pipe_ocr.py:446` except'inde `idx = list(range(...))` → footage gürültüsü; ama downstream `garble_frac` + QC bloğu KONTROL'e düşürür, ONAYLI olmaz.
- **13. dakikadaki giriş jeneriği:** Hem dedektör (12dk tarama) hem pencere (720s cap) ıskalar. Tutarlı ama nadir; TRT içeriği için düşük frekans.

## Çağatay'ın hipotezi: doğru mu?

**Evet, doğru — ve düşündüğünden biraz daha sinsi.** "Düşük güvende dedektör bulduğunu atıp dar 4dk pencereye düşüyor" iddiası `mitas_pipeline.py:1365` else-dalında birebir doğrulandı: `_cl_ok=False` olduğunda `_cik_start` `:1298`'deki sabit `dur-240s` değerinde kalır, dedektörün konumu kullanılmaz.

Hipotezin **yakalamadığı ek katman:** bu daralma kendini bir kör noktayla pekiştiriyor — pencere oynamadığı için `_detect_changed=False` olur ve sistemin tek kurtarıcısı olan sonuç-temelli yedek (`:1499`) hiç çalışmaz. Yani "belirsizlikte daralma" sadece pencereyi daraltmıyor, aynı zamanda kurtarma ağını da devre dışı bırakıyor. **Kurtarma yok.** Hipotez bir gerçek mantık hatasını işaret ediyor.

**Tek nüans:** Bu hata, çıkış jeneriği son 4 dk'nın DIŞINDA ama son 15 dk'nın İÇİNDE + düşük güven + statik-tip olduğunda patlar. Dedektörün tarama penceresi (son 15 dk, `jenerik_detector.py:805`) sabit pencereden (son 4 dk) geniş olduğu için bu boşluk gerçek ve düzenli oluşur.

Relevant dosyalar:
- `E:\MITAS\scripts\mitas_pipeline.py:1281-1396` (blok çöz + pencere kararı), `:1499-1537` (sonuç-temelli yedek)
- `E:\MITAS\core\pipelines\ocr\jenerik_detector.py:789-832` (tarama penceresi)