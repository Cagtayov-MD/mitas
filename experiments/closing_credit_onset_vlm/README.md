# Kapanış jeneriği başlangıcı — `window-boundary-v1` test sürümü

Bu paket, `frames\cikis` içindeki kronolojik karelerden gerçek terminal kapanış
jeneriğinin ilk görünür karesini bulmak için hazırlanmış, production hattından
yalıtılmış bir deneydir. Sonuç `FOUND` olsa bile production havuzunu değiştirme
yetkisi yoktur.

Güvenlik sözleşmesi:

- Kaynak `frames\cikis` yalnız okunur.
- `frames\cikis_jenerik`, master PNG, production manifestleri,
  `scripts\mitas_pipeline.py` ve `scripts\_jenerik_pool.py` yazılmaz.
- Çıktı yalnız `E:\MITAS\outputs\closing_credit_onset_vlm` altında yeni ve daha
  önce var olmayan bir koşu dizinine yazılır.
- `publishable=false` ve `pool_may_be_replaced=false` bütün kararlarda sabittir.

## Neden önceki yaklaşım bırakıldı?

İlk prototip, 4x4 küçük mozaikte her hücreyi ayrı ayrı
`FOOTAGE/DIEGETIC/CREDIT/...` sınıflandırıyordu. Gerçek film logunda yazısız yüz,
manzara ve diegetic Arapça sahne yüksek güvenle CREDIT seçildi; gerçek ilk kredi
ise `UNCERTAIN` kaldı. Doğru görünen `c_0319.png` sonucu, hatalı semantik kanıtın
CV ile geriye alınması sayesinde tesadüfen oluşmuştu.

Yeni protokol kare başına sınıf istemez. Her VLM çağrısı bir zaman penceresi için
tek toplu sınır kararı verir ve CV doğrulanmış semantik sınırı değiştiremez.

## Boru hattı

1. **Ucuz CV teklif taraması**

   Tüm kareler 320 px genişlikte taranır. Text-mask, satır, yoğunluk ve luma
   sinyalleri yalnız coarse panele ek yüksek-recall adayları verir. CV hiçbir
   zaman CREDIT kararı veya nihai başlangıç karesi üretemez.

2. **Coarse semantik pencereler**

   Yaklaşık 120 saniyelik her pencere 9 düzenli kronolojik anchor taşır. 900
   kare/1.5 fps için en fazla yaklaşık 5 VLM çağrısı gerekir. Gerçek son panel,
   düzenli anchorlar arasında kalabilecek kısa `THE END/FIN/SON` kartı için son
   15 saniyeyi yaklaşık 1 saniye aralıkla örnekler; panel en fazla 24 hücredir.

   VLM yalnız şu `WindowEvidence` kararlarından birini döndürür:

   - `PRE_ONLY`: bu pencerede terminal kredi rejimi yok.
   - `TRANSITION`: yerel PRE hücresinden sonra başlangıç var.
   - `ACTIVE_FROM_LEFT`: kredi CELL 00'da zaten aktif; başlangıç solda.
   - `AMBIGUOUS`: semantik veya süreklilik doğrulanamadı.

   Karar ayrıca `first`, `last_support`, `kind`, `continuity` ve `reject`
   alanlarını taşır. Sayısal model confidence istenmez.

3. **Coarse state grammar**

   Bir pencere kararı sonraki hücrelere sahte CREDIT etiketi olarak açılmaz.
   Eksik çağrı, sert diegetic/story reject, desteklenmeyen erken pozitif veya
   `POSITIVE -> PRE -> yeni POSITIVE` rejimi fail-closed kalır. Gerçek Qwen aynı
   kesintisiz kredi bloğunun sonraki coarse panellerinde tekrar tekrar
   `TRANSITION` diyebildiği için, arada `PRE_ONLY` yoksa bunlar tek pozitif rejim
   sayılır ve en erken destekli aday fine aşamasına gider. Destekli coarse
   görünümler `kind` konusunda ayrışırsa sonuç `REVIEW` olur.
   Tek gerçek kredi bloğunun daha sonra siyah/logo ile bitmesi yasak değildir;
   kredinin fiziksel EOF'a kadar görünür olması şart koşulmaz.

   120 saniyelik iki core pencerenin ortak sınırında oluşabilecek özel kör alan
   ayrıca ele alınır: önceki pencerenin son hücrelerinde doğrulanamayan aday ve
   sonraki pencerede `ACTIVE_FROM_LEFT`, doğrudan onset sayılmaz; yalnız daha
   yoğun fine incelemeye gönderilir.

4. **Fine gap paneli**

   Coarse bracket çevresindeki 9 anchor 512 px/hücre ile yeniden sorulur.
   Terminal END card için başlangıç çevresi kare atlamadan taşınır ve gerçek EOF
   context'i eklenir. Fine kararın türü coarse türle aynı, local PRE hücresi ve
   doğrulanmış gelecek desteği olmalıdır.

5. **İki exact doğrulama görünümü**

   Fine kararının örneklenmiş PRE hücresinden bir gerçek kare daha sola gidilir.
   Bu sol context ile fine'ın yaklaşık ilk kredi hücresi arasındaki **bütün
   ardışık kareler** iki panelde de bulunur; böylece 1.5 fps'de seyrek fine
   anchorlar arasında veya ilk fine hücresinde kare kaçmaz. Prompt, JSON schema,
   parser ve provenance bu yoğun aralığı `boundary_search_cells` olarak bağlar.
   Daha sonraki seyrek hücreler yalnız `SUPPORT ONLY`'dir ve `first` olamaz.
   Her panel immediate-post kareleri ve en az 8 saniyelik destek horizonunu taşır.

   - A: 3 sütun, primary-boundary promptu, yaklaşık +3/+8/+15 sn destek.
   - B: 2 sütun, farklı context/cadence (+4/+8/+14 sn) ve diegetic/story
     açıklamasını aktif biçimde çürütmeye çalışan adversarial-reject promptu.

   JPEG95 ve en fazla 640 px/hücre kullanılır. Compose edilmiş exact mozaiği
   2,4 MP'yi aşacaksa hücre genişliği 32 px adımlarla, en az 384 px'e kadar
   düşer; 14 hücreli gerçek A/B koşusunda 512 px kullanılmıştır. Bu koruma
   `num_ctx=4096` üstündeki görsel-token HTTP 400 hatasını önler. İki çağrı aynı
   modelle yapıldığı için “bağımsız model oyu” değildir; farklı
   transport/context ile zorunlu corroboration'dır.

6. **FOUND kapıları**

   `FOUND` için tamamı gerekir:

   - fine ve iki exact görünüm `TRANSITION` olmalı; exact continuity
     `CONFIRMED`, `reject=NONE` olmalı;
   - iki exact görünüm aynı gerçek kareyi bulmalı (varsayılan tolerans 0 kare);
   - ilk hücrenin hemen önceki gerçek karesi PRE olmalı;
   - coarse, fine ve exact `kind` aynı olmalı;
   - normal kredi için coarse ve fine ile birlikte exact görünümlerden en az
     biri 8+ saniyelik continuation taşımalı; iki exact görünüm de kısa destekli
     ise `REVIEW` olmalı;
   - A/B frame listesi, call ID, görüntü hash'i, prompt hash'i/varyantı farklı ve
     denetlenebilir olmalı;
   - kaynak kare imzası koşu boyunca değişmemeli;
   - son VLM cevabı film duvar-süresi deadline'ından önce dönmeli.

   CV bu noktadan sonra sınırı bir kare bile geriye taşıyamaz.

## Terminal END card istisnası

`TERMINAL_END_CARD` yalnız gerçek EOF context'inde kabul edilir. İki yoğun
hücrede görülen tam ekran, non-diegetic bitiş kartı 8 saniyeden kısa olsa da
adaydır. Karttan sonra yalnız siyah/blank fade varsa en fazla 15 saniyelik kuyruk
kabul edilir. Coarse panel yalnız tek net kart hücresi gördüyse bu `FOUND`
değildir; konumu `UNVERIFIABLE` probe olarak fine + A/B exact doğrulamaya taşınır.

## Çalıştırma

Repo kökünde:

```powershell
E:\MITAS\venvs\ocr\Scripts\python.exe -m experiments.closing_credit_onset_vlm `
  --frames "E:\MITAS\Database\FILM_ADI\frames\cikis" `
  --fps 1.5 `
  --model qwen3-vl:30b
```

Özel çıktı dizini mutlaka deney allowlist'i içinde ve yeni olmalıdır:

```powershell
E:\MITAS\venvs\ocr\Scripts\python.exe -m experiments.closing_credit_onset_vlm `
  --frames "E:\MITAS\Database\FILM_ADI\frames\cikis" `
  --out "E:\MITAS\outputs\closing_credit_onset_vlm\manuel_test_01"
```

Önemli varsayılanlar:

- `--max-wall-seconds 120`
- `--coarse-window-seconds 120`
- `--coarse-anchors 9`
- `--coarse-max-cells 24`
- `--coarse-tile-width 384`
- `--fine-tile-width 512`
- `--verify-tile-width 640`
- `--panel-jpeg-quality 95`
- `--min-support-seconds 8`

Çıkış kodları: `FOUND=0`, `REVIEW/LEFT_CENSORED=3`, `NOT_FOUND=4`,
`MODEL_ERROR=5`, CLI/ayar hatası `10`.

## Koşu artefaktları

- `result.json`: nihai fail-closed karar ve başlangıç.
- `run_manifest.json`: config, kaynak imzaları, coarse/fine/exact kanıt ve karar.
- `calls.jsonl`: her çağrının süre, stage, frame listesi, prompt ve görsel hash'i.
- `features.csv`: CV teklif sinyalleri.
- `window_evidence.json`: modelin doğrudan pencere kararları; sentetik kare etiketi yok.
- `window_timeline.csv`: pencerelerin kısa denetim tablosu.
- `panels\*.jpg`: modelin gerçekten gördüğü exact byte'lar; sonradan çizilmiş
  debug görseli değildir.

Base64 görüntü içeriği loglanmaz.

## Maliyet ve performans

900 kare/1.5 fps için VLM çağrı sayısı tipik olarak 5 coarse + 1 fine + 2 exact
= 8'dir. 720 karede çoğunlukla 4 + 1 + 2 = 7 çağrı olur. CV taraması bu makinede
yaklaşık 11–16 saniyedir. Tek gerçek-film sıcak-model smoke testinde 720 kare,
CV dahil 18,761 saniyede tamamlandı: CV 10,684 saniye, 4 coarse + 1 fine + 2
exact çağrı. Bu tek-film ölçümüdür; stil korpusu benchmarkı veya yoğun GPU altında
1–2 dakika garantisi değildir. Tasarım yine 120 saniyelik hard budget içinde
fail-closed kalır. `calls.jsonl` gerçek kare-başı değil, panel-başı `wall_ms`
değerini verir.

Başka bir Ollama/GPU işi çalışıyorsa 1–2 dakika garantisi yoktur. Kalan güvenli
çağrı bütçesi 10 saniyenin altına düşerse veya çağrı deadline sonrasında dönerse
sonuç `MODEL_ERROR` olur; kısmi kanıtla `FOUND` üretilmez.

## Bilinen sınırlar

- A ve B aynı Qwen modelidir. Kalıcı diegetic yazının iki promptta da aynı
  semantik hatayla kabul edilme riski yalnız gerçek adversarial film korpusu ile
  ölçülebilir; unit test gate'in çalıştığını, model doğruluğunu kanıtlamaz.
- Kaynağın ilk karesinde kredi zaten aktifse güvenli PRE kanıtı yoktur ve
  `LEFT_CENSORED` döner.
- Bir kareden kısa/yalnız tek örneklenmiş terminal kart fine/exact aşamasında iki
  görünür hücre üretemezse fail-closed kalır.
- Ağır sıkışma, çok küçük veya tamamen görünmez düşük-kontrast yazı VLM tarafından
  kaçırılabilir.
- Fine model ilk görünür krediyi örneklenmiş predecessor'dan bir kareden daha
  erken kaçırırsa exact sol-genişletme yetmeyebilir ve sonuç güvenli `REVIEW`
  kalabilir.
- Uzun post-credit sahneyle ayrılmış ikinci kredi adası `REVIEW` üretebilir.
- Kaynak imzası orta karelerde yol/boyut/mtime metadata'sını, ilk ve son karede
  ayrıca tam içeriği hash'ler. Aynı boyut ve geri alınmış mtime ile yapılan
  kasıtlı bir orta-kare byte değişikliği bu test-sürümü imzasını aşabilir.
- Canlı CLI sabit dahili Ollama locator'ını kullanır. İleride harici/pluggable
  locator açılırsa prompt hash'inin locator kaydından bağımsız yeniden
  hesaplanması ayrıca sertleştirilmelidir.
- Bu sürüm production pipeline'a bağlı değildir; otomatik havuz kurmaz.

## Test ve statik kontroller

```powershell
E:\MITAS\venvs\ocr\Scripts\python.exe -m pytest -q `
  tests\test_closing_credit_onset_detector.py `
  tests\test_closing_credit_onset_temporal.py `
  tests\test_closing_credit_onset_window_protocol.py

E:\MITAS\venvs\ocr\Scripts\python.exe -m compileall -q `
  experiments\closing_credit_onset_vlm

E:\MITAS\venvs\ocr\Scripts\python.exe -m experiments.closing_credit_onset_vlm --help
```

Canlı karar/ilerleme notu:
`E:\MITAS\experiments\closing_credit_onset_vlm\HANDOFF_PROGRESS.md`.
