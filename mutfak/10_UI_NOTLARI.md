# 10 — UI NOTLARI

> Son güncelleme: 2026-05-14
> Son değişen bölüm: Live STT Preview sağ ASR paneli akışı ve imleç/toplam süre göstergesi

Bu dosya MITAS arayüzü için operasyonel takip yeridir. UI ile ilgili konuşmalar, yapılan düzeltmeler, açık kararlar ve ASR backend ile UI arasındaki sözleşme burada tutulur.

---

## 1. UI nerede?

Aktif UI çalışma dizini:

`E:\MITAS\.claude\worktrees\wonderful-vaughan-884d20\webui\`

Teknik yapı:

- React + Vite + Tailwind + shadcn/ui
- Ana giriş: `src/app/App.tsx`
- ASR API köprüsü: `src/app/asr-api.ts`
- Ana ekran: `src/app/components/AnalysisWorkspace.tsx`
- Üst bar: `src/app/components/Header.tsx`
- Oynatıcı: `src/app/components/VideoPlayer.tsx`
- Timeline: `src/app/components/Timeline.tsx`
- Sağ panel: `src/app/components/Sidebar.tsx`

Dev server:

`http://127.0.0.1:5173/`

Backend proxy:

`/api` → `http://localhost:8787`

---

## 2. ASR modeli ile UI arasındaki sınır

Kısa karar: **ASR modeli/pipeline değişince UI genellikle değişmez.** UI, ASR motoru değildir; ASR sonucunu gösteren görsel kabuktur.

UI şu sözleşmeyi okur:

- `job_id`
- `status`
- `filename`
- `profile`
- `channel_mode`
- `message`
- `error`
- `summary.model_name`
- `summary.profile_used`
- `summary.audio_duration`
- `summary.clean_segments`
- `summary.raw_segments`
- `summary.quality_drops`
- `summary.safety`
- `archive.quality.drop_reasons`
- `transcript`
- `segments[]`
- `segments[].start`
- `segments[].end`
- `segments[].text`
- `segments[].speaker`
- `segments[].channel`
- `segments[].avg_logprob`
- `segments[].no_speech_prob`

ASR tarafında model `large-v3-turbo`, `large-v3`, selective fallback veya başka bir motor olsa bile bu alanlar aynı kalıyorsa UI değişmeden çalışır.

UI değişikliği gerektiren durumlar:

- Endpoint değişirse (`/api/asr/transcribe`, `/api/jobs/{id}`).
- Response alan isimleri veya şekli değişirse (`segments` başka yere taşınırsa vb.).
- UI'dan gönderilen parametreler değişirse (`profile`, `channel_mode`, içerik profili, model seçimi).
- Yeni görsel davranış istenirse: word-level highlight, konuşmacı renkleri, kanal karşılaştırma, alignment görünümü.
- Yeni kalite uyarı türleri özel olarak gösterilecekse.
- Upload/onay/job akışı değişirse.

Prensip: **ASR sabit API sözleşmesi döndürsün, UI onu okusun.** Model değişikliği UI işi olmamalı; sözleşme değişikliği UI işidir.

---

## 3. 2026-05-14 yapılan UI düzeltmeleri

### 3.1 Upload ASR başlatmaz

Eski davranış:

- Dosya yüklenir yüklenmez `startAsrJob(file)` çağrılıyordu.
- Kullanıcı ASR onayı vermeden model çalışıyordu.

Yeni davranış:

- Upload sadece dosyayı seçer, preview hazırlar ve state'e koyar.
- ASR ancak kullanıcı `ASR Başlat` düğmesine basarsa başlar.
- Bu ayrım `App.tsx` içinde `selectedFile` + `handleStartAsr()` ile kuruldu.

Değişen dosya:

- `src/app/App.tsx`
- `src/app/components/Header.tsx`

### 3.2 Upload sonrası görünür hazır bilgisi

Kullanıcı dosya seçtiğinde UI artık açıkça şunu gösterir:

`erd_test_sound.wav ASR için hazır`

Bu bilgi iki yerde görünür:

- Header içinde dosya adının altında.
- Medya/oynatıcı alanının üstünde.

Ek not:

`Model çalışmadı. Başlatmak için ASR Başlat.`

Amaç: Kullanıcı "dosya yüklendi mi, sistem ne durumda?" diye aramasın.

Değişen dosyalar:

- `src/app/components/Header.tsx`
- `src/app/components/VideoPlayer.tsx`
- `src/app/components/AnalysisWorkspace.tsx`

### 3.3 Demo modu rozeti kaldırıldı

`DEMO MODU` rozeti üst bardan kaldırıldı.

Gerekçe:

- Kullanıcı artık gerçek ASR akışıyla çalışıyor.
- UI'da "demo" hissi yanlış beklenti yaratıyor.

Değişen dosya:

- `src/app/App.tsx`

### 3.4 "İnceleme bekliyor" dili kaldırıldı

Eski sorun:

- UI'da `İnceleme Bekleyen`, `{n} bekliyor`, segment altında `inceleme bekliyor` gibi ifadeler vardı.
- Kullanıcı haklı olarak "neye göre bekliyor, ne inceleyeceğim, bunu görev olarak istedim mi?" diye sordu.

Yeni davranış:

- Sağ panel sekmesi `Sıra` yerine `Uyarılar`.
- Başlık `ASR Uyarıları`.
- Rozet `{n} uyarı`.
- Segment güven etiketi:
  - `yüksek güven`
  - `orta güven`
  - `düşük güven`

Not: Gerçek review workflow kurulmadan UI "inceleme görevi" icat etmeyecek.

Değişen dosya:

- `src/app/components/Sidebar.tsx`

### 3.5 Klavye kontrolleri eklendi

Eklenen kontroller:

- `Space` → play / pause
- `K` → play / pause
- `J` → 10 saniye geri
- `L` → 10 saniye ileri

Not:

- Input, textarea, button, role=button ve contenteditable içindeyken global kısayol tetiklenmez.
- Böylece arama kutusunda veya ASR satırı seçerken yanlışlıkla oynatma değişmez.

Değişen dosya:

- `src/app/components/VideoPlayer.tsx`

### 3.6 Timeline ile ASR paneli çift yönlü senkronlandı

Eski sorun:

- Timeline akıyordu ama kullanışlı değildi.
- Kullanıcı "adam bir şey diyor ama hangi satırda bilmiyorum" dedi.

Yeni davranış:

- Timeline'daki ASR segmentine tıklayınca:
  - Video o segment başlangıcına gider.
  - Sağdaki ASR satırı seçilir.
  - ASR satırı görünür bölgeye kaydırılır.
  - Timeline bloğu vurgulanır.
- Sağdaki ASR satırına tıklayınca:
  - Video/timeline o segment başlangıcına gider.
  - Timeline bloğu vurgulanır.
- Oynatma akarken aktif segment otomatik seçili hale gelir.

Değişen dosyalar:

- `src/app/App.tsx`
- `src/app/components/AnalysisWorkspace.tsx`
- `src/app/components/Timeline.tsx`
- `src/app/components/Sidebar.tsx`

### 3.7 Profil seçimi eklendi

Kullanıcı isteği:

UI'da tıklanıp seçilebilen bir profil alanı olmalı. Daha önce hazırlanan içerik/işlem profilleri buraya konmalı:

- Belgesel
- Müzik / Eğlence
- Spor Karşılaşmaları
- Stüdyo Programları
- Haber
- STT

Karar:

- Bu liste UI'da `Profil` seçimi olarak gösterilir.
- `fast_with_fallback` backend ASR motor profilidir; bu listeyle karıştırılmaz.
- Konuşmadan metne işlemi **STT seçiliyken** başlatılır.
- Diğer profiller şimdilik seçilebilir, ama STT/ASR job başlatmaz; ileride ilgili modül/akış davranışlarını açacak.

Değişen dosyalar:

- `src/app/asr-api.ts` — `AnalysisProfile` tipi ve profil listesi eklendi.
- `src/app/App.tsx` — seçili profil state'i eklendi.
- `src/app/components/Header.tsx` — profil seçimi UI'a eklendi; `STT Başlat` sadece STT seçiliyken aktif.

### 3.8 STT Preview seçeneği eklendi

Kullanıcı isteği:

STT kısmında `Preview` seçeneği olsun. Kullanıcı tik atınca aktif olsun. Bu aktif olduğunda "anlık çeviri" dediğimiz show alanı hazırlanacak.

Yeni davranış:

- STT seçiliyken `Preview / Anlık çeviri` checkbox'ı aktif olur.
- STT dışında Preview kapalı ve disabled kalır.
- Preview aktifken video alanında `STT Preview açık` ve `Anlık çeviri / show alanı` placeholder'ı görünür.
- Gerçek canlı transcript/translation akışı henüz bağlanmadı; şu an görsel ve kullanıcı akışı hazırlandı.

Değişen dosyalar:

- `src/app/App.tsx`
- `src/app/components/Header.tsx`
- `src/app/components/VideoPlayer.tsx`

### 3.9 Tema biraz aydınlatıldı

Kullanıcı notu:

`Ekran çok karanlık. Renkleri biraz düzelt.`

Yapılan:

- Ana shell siyaha çok yakın tondan daha okunur koyu griye alındı.
- Surface/elevated surface değerleri yükseltildi.
- Border ve muted text kontrastı artırıldı.
- Video player dış kabuğu saf `black` yerine uygulama shell tonu kullanacak şekilde yumuşatıldı.

Değişen dosyalar:

- `src/styles/theme.css`
- `src/app/components/VideoPlayer.tsx`

### 3.10 Live STT Preview tasarımı uygulandı ve popup iptal edildi

Kullanıcı isteği:

- `Preview / Anlık çeviri` yalnızca STT profilinde çalışsın.
- Kaynak mikrofon değil, player'da çalan medya sesi olsun.
- Upload veya checkbox tek başına model çalıştırmasın; canlı akış kullanıcı `Play` bastığında başlasın.
- Şimdilik çıktı canlı transcript olsun. Dil algılama + Türkçe dışı konuşmada yanda Türkçe çeviri sonraki fazdır.

Yeni backend davranışı:

- FastAPI endpoint: `/api/stt/preview/ws`
- WebSocket client mesajları: `start`, `chunk`, `pause`, `resume`, `seek`, `stop`
- WebSocket server mesajları: `ready`, `status`, `final`, `error`
- `chunk` mesajı 16 kHz mono PCM16 audio taşır; yanında `chunk_id`, `media_time_start`, `media_time_end` vardır. Canlı bağlam için client son 2 saniyelik sesi yeni chunk'a overlap olarak ekler ve server `publish_after` öncesindeki eski kısmı yayınlamaz.
- Live preview `large-v3-turbo` / fast model ile küçük WAV parçalarını çözer.
- Batch ASR kuyruğundan ayrı tek worker'lı live executor kullanılır.
- Full dosya preprocessing, fallback, VAD ve batch job bu hatta çalışmaz.

Yeni UI davranışı:

- Eski alt placeholder kaldırıldı.
- İlk tasarımda düşünülen floating popup/drawer iptal edildi.
- Preview açılınca sağdaki normal `ASR` sekmesi canlı transcript alanına dönüşür.
- Sağ ASR panelindeki durumlar: `Hazır`, `Dinliyor`, `Çözümlüyor`, `Durakladı`, `Bağlantı hatası`.
- `Play` ile Web Audio API player sesini yakalar, 16 kHz mono PCM16 chunk olarak WebSocket'e yollar.
- Chunk sınırında cümle kaybını azaltmak için 5 saniyelik canlı parçaya önceki 2 saniye bağlam olarak eklenir; UI yalnız yeni zaman aralığını gösterir.
- `Pause` chunk göndermeyi durdurur ve elde kalan kısa buffer'ı çözdürür.
- `Seek` canlı bağlamı resetler ve yeni konumdan devam eder.
- Normal/batch STT zaman kodlu kalır; Preview modunda zaman damgası gizlenir.
- Preview metni ayrı zaman kodlu satırlar yerine tek akan metin blokunda gösterilir.
- Yeni live metin geldikçe panel otomatik alta kayar; kullanıcı konuşmanın sonunu takip eder.
- Preview metni daktilo etkisiyle harf harf ve batch satırlardan biraz daha yavaş görünür; `Dinliyor/Çözümlüyor` durumlarında spinner görünür.
- Preview metni canlı hissi bozmasın diye tamamlanmamış kısa son kelime/cümle kuyruğunu tamponlar. Örneğin chunk sınırında yalnız "Ama" gibi yeni cümle başı geldiyse, devamı gelene kadar ekrana basılmaz; canlı imleç akışın sürdüğünü gösterir.
- Overlap kaynaklı tekrarlar Preview görünümünde kelime seviyesinde tekilleştirilir. Örneğin bir chunk "Biliyorum ki sesinin bu kadar çok" ile bitip sonraki chunk aynı başlangıcı tekrar ederek devam ederse, ikinci başlangıç atılır ve yalnız devam eden kelimeler eklenir.
- Deneysel rolling-buffer davranışı: player sesi küçük parçalarla sürekli dinlenir; decode isteği yaklaşık 1.25 sn aralıkla, 7 sn rolling context üzerinden yapılır. UI'ye yazılan kısım `publish_until` ile yaklaşık 2 sn geriden commit edilir. Amaç cümle beklemek değil, daha stabil kelime akışı üretmektir.
- 2026-05-15 düzeltmesi: segment bazlı publish filtresi bazı uzun Whisper segmentlerinin başını atıyordu. Live decode `word_timestamps=True` ile kelime bazlı publish'e alındı; rolling context 10 sn, decode aralığı ~1.5 sn, yazma gecikmesi ~3 sn olarak ayarlandı. `erd_test_video.mp4` 29-40 sn doğrudan testinde "Biliyorum ki sesinin bu kadar çok" artık ayrı publish penceresinde korunuyor.
- 2026-05-15 tempo denemesi: Preview yazma gecikmesi sabit olmaktan çıkarıldı. Client sonuç kalitesi, boş çıktı, kısa/tamamlanmamış kuyruk ve canlı backlog'a göre gecikmeyi yaklaşık 1.6-4.8 sn arasında adaptif oynatır. UI daktilo efekti de biriken karakter kuyruğu uzunsa hızlanır, sona yaklaşınca yavaşlar.
- Preview kapanınca WebSocket kapanır; aynı dosyada son satırlar kullanıcı temizleyene kadar kalır.
- Yeni dosya yüklenince live preview buffer temizlenir.
- Live stream gerçekten çalışırken `STT Başlat` devre dışı kalır; aynı anda batch ASR ve live ASR GPU'ya yük bindirmez.
- Üst bardaki büyük süre artık yalnız toplam klip süresi değildir; `imleç / toplam süre` formatındadır.
- Live Preview hattında speaker diarization çalışmaz. Kişi/konuşmacı ayırma sadece batch STT diarization sonucu `speaker` alanı üretirse sağ ASR satırlarında görünür.

Doğrulama notu:

- `erd_test_video.mp4` / job `asr-d55ae4d27275` üzerinden batch transcript ile canlı chunk simülasyonu karşılaştırıldı.
- Overlap öncesi 160-170 sn civarında "Benim için de Davos bitmiştir" cümlesi parça sınırında kopuyordu.
- 2 sn overlap sonrası canlı simülasyon 165-167 sn aralığında "Benim için de bundan böyle Davos bitmiştir." satırını yakaladı. Kalan farklar canlı modun VAD/fallback/uzun bağlam kullanmamasından kaynaklanan kalite farkı olarak izleniyor.

Değişen dosyalar:

- Backend: `core/api/asr_server.py`
- Backend test: `tests/test_asr_live_preview_api.py`
- UI hook: `src/app/live-stt-preview.ts`
- UI bağlama: `src/app/App.tsx`, `src/app/components/AnalysisWorkspace.tsx`, `src/app/components/Header.tsx`, `src/app/components/VideoPlayer.tsx`
- UI canlı transcript: `src/app/components/Sidebar.tsx`
- Vite proxy: `webui/vite.config.ts`

---

## 4. Doğrulama

2026-05-14 doğrulama:

- `tsc --noEmit` geçti.
- `vite build` geçti.
- `http://127.0.0.1:5173/` HTTP 200 döndü.

Not:

- In-app browser otomasyon bağlantısı iki kez zaman aşımına düştü. Bu yüzden görsel doğrulama otomasyonla tamamlanamadı.
- Dev server çalışıyorsa Vite HMR değişiklikleri sayfaya basar; gerekirse manuel refresh yapılır.

---

## 5. Bilinçli açıklar

### 5.1 ASR kalite sorunu: Guardian / İngiliz

Kullanıcı örneği:

`Üngiliz gazetesi Guardian'da şunu söylüyor.`

Beklenen:

`İngiliz gazetesi Guardian'da şunu söylüyor.`

veya bağlama göre:

`İngiliz gazetesi The Guardian'da şunu söylüyor.`

Bu UI değil, ASR/normalizasyon/üst-denetim kalite konusudur. Gerekirse ayrıca ASR kalite raporuna alınacak.

### 5.2 ASR kritik eksik: 03:15 Davos cümlesi görünmüyor

Kullanıcı notu:

`03:15 civarında "Benim için de Davos bitmiştir" görünmüyor.`

Bu kritik kabul engelidir. Olası kaynaklar:

- VAD konuşma penceresini eksik yakaladı.
- ASR segmenti üretti ama kalite filtresi temiz transcript'ten düşürdü.
- Fallback tetiklenmedi.
- UI doğru segmenti göstermiyor.
- Timeline-ASR veri eşleşmesinde eksik var.

Bu madde UI düzeltmelerinden ayrı ele alınacak. Önce ilgili job output'larında raw/clean/timeline karşılaştırması yapılmalı.

---

## 6. Bundan sonra UI notu nasıl tutulacak?

UI ile ilgili yeni konuşmalar bu dosyaya eklenecek.

Kural:

- Kullanıcı davranış beklentisi → bu dosyada "Beklenti" olarak yazılır.
- Yapılan UI değişikliği → dosya + davranış + doğrulama ile yazılır.
- ASR kalite problemi UI'da görünse bile kökü ASR ise burada sadece referans verilir; detay ASR kalite/benchmark dosyasında tutulur.
- Kalıcı ürün kararı ise ayrıca `mutfak/06_KARARLAR_GUNLUGU.md` içine karar olarak geçirilir.

---

## 7. Segment Bazlı Türkçe Çeviri

Tarih: 2026-05-15

Beklenti:

- Batch STT sonucunda yabancı dil satırının üzerinde veya yanında `T` aksiyonu görünsün.
- Kullanıcı `T` bastığında orijinal satır sabit kalsın, Türkçe çeviri aynı segmentin altında görünsün.
- Türkçe segmentler yeniden çevrilmesin.

Yapılan:

- Backend'e `POST /api/translate/segments` endpoint'i eklendi. Endpoint ana ASR API içinde kalıyor ama çeviri runtime'ını izole `venvs/translate` ortamında subprocess olarak çağırıyor.
- Router kararı `config/translation_router.yaml` içine bağlandı: EN→TR için `opus-mt-tc-big-en-tr`, diğer destekli diller için `nllb-200-3.3b`.
- UI'da ASR segment satırlarına `T` butonu eklendi. Buton yabancı dil segmentlerde aktif, Türkçe segmentlerde `TR` etiketi gösteriliyor.
- Çeviri sonucu segment altında `TR çeviri` bloğu olarak saklanıyor; aynı job açık kaldığı sürece UI state'te korunuyor.

Doğrulama:

- `translate_smoke.py --model all` üç modelde geçti.
- `/api/translate/segments` EN örneğinde OPUS ile `Sayın Başbakan, bir dakika lütfen.` döndürdü.
- `/api/translate/segments` FR örneğinde NLLB 3.3B ile Türkçe sonuç döndürdü.
- UI `tsc --noEmit` ve `vite build` geçti.

2026-05-15 ek:

- Çeviri çıktısına `broadcast_tr_v1` post-edit katmanı eklendi. Amaç ham MT çıktısını daha doğal TRT/haber altyazısı Türkçesine yaklaştırmak.
- Örnek düzeltme: `Başbakan, tartışmayı tekrar başlatamayız, lütfen, sadece zamanımız yok.` → `Sayın Başbakan, tartışmayı yeniden açamayız, lütfen; buna zamanımız yok.`
- ASR sekmesi üstüne `T Tümünü Çevir` aksiyonu eklendi. Bu aksiyon tüm transcript satırlarını Türkçe hedefe çevirir; zaten Türkçe görünen satırlar `orijinal Türkçe` olarak korunur.
- Segmentlerde kanal bilgisi `L/R` gelirse timeline iki ASR lane'e ayrılır: `ASR Kanal 1` ve `ASR Kanal 2`.
- Sağ ASR panelinde kanal filtresi eklendi: `Tümü / Kanal 1 / Kanal 2`.

---

## 8. ASR İlerleme ve Kalıcı İşlem Logu

Tarih: 2026-05-16

Beklenti:

- ASR devam ederken kullanıcı yüzde kaçta olduğunu görmeli.
- Aynı yerde işlemin kaç dakikadır sürdüğü görünmeli.
- Sağ panelde yapılan işlemleri gösteren bir `Log` sekmesi olmalı.
- Sayfa yenilense veya kapatılıp açılsa log kaybolmamalı.

Yapılan:

- Backend job kaydına `progress_percent`, `progress_label`, `elapsed_seconds` ve `logs` alanları eklendi.
- Her ASR job için kalıcı `job_log.jsonl` tutuluyor: `outputs/webui_asr_jobs/<job_id>/job_log.jsonl`.
- Backend, upload/kuyruk/worker/pipeline/artifact/tamamlandı/hata aşamalarını logluyor.
- Pipeline içi chunk callback'i olmadığı için running yüzdesi şimdilik tahmini akar; gerçek aşama logları ayrıca kalıcıdır.
- UI Header, `yüzde + geçen süre` bilgisini rozet ve progress bar olarak gösteriyor.
- Sağ panelde `Log` sekmesi eklendi.
- UI açıldığında son ASR job otomatik geri yükleniyor; böylece yenileme sonrası log ve sonuçlar tekrar görünür.

Doğrulama:

- Küçük wav smoke job'da running sırasında progress `17 → 20 → 22`, tamamlanınca `100` döndü.
- Aynı smoke job için `6` log kaydı API'den geri döndü.
- `py_compile core/api/asr_server.py`, UI `tsc --noEmit`, UI `vite build` geçti.
