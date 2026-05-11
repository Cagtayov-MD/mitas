# ASR Code Starter Günlüğü

> Başlangıç: 2026-05-11
> Amaç: ASR v0.1 pipeline kodlamasını kontrollü, blok blok ve gerekçeli ilerletmek.

Bu dosya, ASR pipeline implementasyonu sırasında yapılan işleri, neden yapıldıklarını ve her blok sonunda yapılan öz-kontrolü kaydeder. Hedef, tek kişilik geliştirmede "sonra neden böyle yaptık?" sorusuna açık cevap bırakmaktır.

---

## Çalışma Disiplini

- Her kod bloğu küçük tutulacak.
- Her bloktan sonra test veya en azından doğrulama yapılacak.
- Her bloktan sonra şu sorular sorulacak:
  - Uyumlu mu?
  - Amaca hizmet ediyor mu?
  - Başka bir şeyi bozuyor mu?
  - Daha iyi olabilir miydi?
- ASR pipeline implementasyonu, mevcut plana göre sırayla ilerleyecek: normalize -> VAD -> transcribe -> diarize -> merge -> quality -> worker/pipeline.

---

## 2026-05-11 / Blok A Başlangıç - Audio Normalize

### Neden Bu Blok?

ASR pipeline'ın ilk gerçek adımı, bütün video/ses girdilerini tek güvenilir ses formatına indirmektir. faster-whisper, Silero VAD ve pyannote tarafında sürprizleri azaltmak için hedef format sabitlenmiştir:

- 16 kHz
- mono
- 16-bit PCM WAV

Bu blok, henüz VAD/transcribe/diarization kodlamasına girmez. Sadece ses hazırlığı yapar.

### Ön Kontrol

- Git çalışma ağacı temiz başladı.
- `core/pipelines/asr/` henüz yoktu; bu yüzden yeni ASR kodu için doğru başlangıç noktası burası.
- `docs/MITAS_ASR_Pipeline_v0_1_Implementasyon_Plani_v2.md` dosyasındaki §5 Audio normalize hedefi esas alındı.
- `ffmpeg -version` başarılı çalıştı; sistemde FFmpeg 8.1 erişilebilir.
- `ffprobe` ile `samples/torchcodec_smoke.wav` kontrol edildi; dosya zaten `pcm_s16le`, `16000 Hz`, `1 channel`.

### Tasarım Kararı

Normalize fonksiyonu iki yollu davranacak:

1. Girdi zaten hedef formatta WAV ise dosyayı tekrar üretmeyecek, doğrudan mevcut dosyayı döndürecek.
2. Girdi farklı formatta ise `tmp/asr_normalize/` altında hedef WAV üretecek.

Bu karar gereksiz dosya yazımını azaltır ve smoke testleri hızlı tutar. Aynı zamanda video input geldiğinde ffmpeg ile audio extract yolunu açar.

### Eklenen Kod

- `core/pipelines/__init__.py` eklendi.
  - Sebep: ASR ve sonraki pipeline modülleri için ortak paket alanı açmak.
- `core/pipelines/asr/__init__.py` eklendi.
  - Sebep: ASR v0.1 parçalarını modül olarak import edilebilir yapmak.
- `core/pipelines/asr/normalize.py` eklendi.
  - Sebep: ffprobe ile ses formatını okumak, hedef formatta dosyayı tekrar üretmeden kullanmak, hedef dışı input'u ffmpeg ile 16 kHz mono PCM WAV'a çevirmek.
- `tests/test_asr_normalize.py` eklendi.
  - Sebep: normalize davranışını küçük ve bağımsız testlerle doğrulamak; GPU/model yüklemeden ilk pipeline taşını güvenceye almak.

### Kodlama Notları

- Hedef format sabitleri kod içinde açık yazıldı: `16000 Hz`, `1 channel`, `pcm_s16le`, `s16`.
- `AudioNormalizeError` özel hata sınıfı eklendi.
  - Sebep: ileride pipeline `stage=normalize` fail üretirken ffmpeg/ffprobe hatasını ayırt edebilsin.
- `NormalizeResult` dataclass'i eklendi.
  - Sebep: sadece path döndürmek yerine, input/output stream bilgisini ve dosyanın yeniden üretilip üretilmediğini açıkça taşımak.
- Çıktı dosya adı input path hash'i ile deterministik üretildi.
  - Sebep: aynı isimli farklı klasör dosyalarının `tmp/asr_normalize/` altında çakışmasını önlemek.
- İlk gözden geçirmede default output klasörü repo köküne sabitlendi: `E:\MITAS\tmp\asr_normalize`.
  - Sebep: fonksiyon farklı working directory'den çağrılsa bile geçici ASR dosyaları proje dışına dağılmasın.

### Test ve Doğrulama

- `tests/test_asr_normalize.py` çalıştırıldı: 4 passed.
- Temel schema/job testleri çalıştırıldı: 28 passed.
- Tüm test paketi çalıştırıldı: 71 passed.
- Default output klasörü düzeltildikten sonra tekrar doğrulandı:
  - `tests/test_asr_normalize.py`: 4 passed.
  - Tüm test paketi: 71 passed.

### Blok Sonu Öz-Kontrol

**Uyumlu mu?**  
Evet. Kod, ASR implementasyon planındaki Audio normalize hedefiyle uyumlu: ffprobe kontrolü, hedef formatta reuse, hedef dışı input için ffmpeg dönüşümü var.

**Amaca hizmet ediyor mu?**  
Evet. VAD/transcribe/diarize aşamalarının bekleyeceği sabit ses formatını üretmek için yeterli ilk taş kondu.

**Başka bir şeyi bozuyor mu?**  
Şu an hayır. Tüm mevcut test paketi 71 passed. Yeni kod ayrı `core/pipelines/asr/` altında ve mevcut schema/job koduna dokunmuyor.

**Daha iyi olabilir miydi?**  
İleride pipeline tamamlanırken geçici dosya yaşam döngüsü için cleanup politikası eklenmeli. Bu blokta özellikle eklenmedi; çünkü normalize fonksiyonu tek sorumlulukta kaldı, dosyayı ne zaman sileceğine üst pipeline karar verecek.

### Takip Dosyası Güncellemesi

- `mutfak/05_AKTIF_GOREV.md` içinde A adımı tamamlandı olarak işaretlendi.
  - Sebep: Sprint dosyası "her adım sonunda işaretleme" disiplinini istiyor.

### 2026-05-11 / Ek Kontrol - Gerçek Medya Normalize Smoke

Kullanıcı sorusu üzerine A bloğunda gerçek medya smoke'u ayrıca kontrol edildi. İlk test turunda küçük gerçek WAV sample ve sentetik WAV dönüşümü vardı; gerçek video input ile normalize smoke henüz yapılmamıştı. Bu küçük eksik giderildi.

**Komut amacı:** `testklipler/trt_haber (1).mp4` dosyasından sadece audio normalize adımını çalıştırmak; VAD/transcribe/diarize çalıştırmamak.

**Sonuç:**

- Input: `E:\MITAS\testklipler\trt_haber (1).mp4`
- Output: `E:\MITAS\tmp\asr_normalize\trt_haber (1)_d3e6436bc9_16000hz_mono_s16.wav`
- `reused_input`: `False`
- Codec: `pcm_s16le`
- Sample rate: `16000`
- Channels: `1`
- Sample format: `s16`

**Yorum:** Gerçek MP4 üzerinde ffmpeg extract + normalize yolu çalışıyor. Bu sadece A bloğunu doğrular; henüz gerçek medya ile VAD, transcribe veya diarization testi yapılmadı.

### 2026-05-11 / Ek Kontrol - Gerçek Medya Pytest Smoke Seti

Kullanıcı "gerçek medyalarla da test yap, eksik kalmasın" dediği için A bloğuna kalıcı bir gerçek medya pytest'i eklendi.

**Eklenen test dosyası:** `tests/test_asr_normalize_real_media.py`

**Neden eklendi?**

Tek seferlik manuel smoke yeterli değildi. Normalize/extract davranışının gerçek MP4 dosyalarında tekrar tekrar doğrulanabilmesi için pytest içine alınması daha güvenli. Test, `testklipler/` klasörü mevcutsa çalışır; başka ortamda gerçek medya yoksa skip eder. Böylece lokal güvence artar, repo taşınabilirliği bozulmaz.

**Gerçek medya smoke seti:**

- `E:\MITAS\testklipler\erd_test_video.mp4`
- `E:\MITAS\testklipler\trt_haber (1).mp4`
- `E:\MITAS\testklipler\trt_haber (2).mp4`
- `E:\MITAS\testklipler\trt_haber (3).mp4`
- `E:\MITAS\testklipler\1.mp4`

**Ön gözlem:**

- İlk dört dosya: AAC, 44.1 kHz, stereo.
- `1.mp4`: AAC, 48 kHz, stereo.
- Hepsi hedef dışı formattaydı; yani test gerçekten ffmpeg dönüşüm yolunu çalıştırdı.

**Test sonuçları:**

- `tests/test_asr_normalize_real_media.py`: 5 passed.
- `tests/test_asr_normalize.py tests/test_asr_normalize_real_media.py`: 9 passed.
- Tüm test paketi: 76 passed.

**Blok Sonu Ek Öz-Kontrol:**

**Uyumlu mu?**  
Evet. Gerçek medya testi sadece A bloğunun sorumluluğunu doğruluyor: video/audio input -> 16 kHz mono PCM WAV.

**Amaca hizmet ediyor mu?**  
Evet. Artık normalize adımı sadece sentetik veya küçük sample ile değil, gerçek TRT MP4 dosyalarıyla da regression altında.

**Başka bir şeyi bozuyor mu?**  
Hayır. Tüm test paketi 76 passed. Yeni test dosyası gerçek medya yoksa skip edecek şekilde yazıldı; `testklipler/` Git dışında kaldığı için başka ortamları kırmaması hedeflendi.

**Daha iyi olabilir miydi?**  
Multi-GB dosyalar (`2.mp4`, `3.mp4`, `4.mp4`, `5.mp4`) bu blokta tam normalize smoke'a sokulmadı. Bunun nedeni A bloğunu hızlı ve tekrar edilebilir tutmak. Büyük dosyalar için ayrı "ASR real media stress/benchmark" aşaması açılmalı; normalize unit/regression testine karıştırılırsa her test turu gereksiz ağırlaşır.

---

## 2026-05-11 / Blok B - Silero VAD

### Neden Bu Blok?

Normalize sonrası ASR pipeline'ın ikinci taşı, konuşmanın geçtiği zaman aralıklarını çıkarmaktır. Bu bilgi iki nedenle gerekli:

- faster-whisper öncesinde konuşma bölgelerini bilmek.
- `speech_ratio` metriğini kalite raporuna yazmak.

Bu blok sadece VAD yapar. Transcribe, diarization ve segment-speaker merge bu blokta yapılmadı.

### Ön Kontrol

- `venvs/asr` içinde `silero_vad==6.2.1` mevcut.
- API kontrol edildi:
  - `load_silero_vad(onnx=False, opset_version=16)`
  - `get_speech_timestamps(..., return_seconds=False/True, sampling_rate=16000)`
  - `read_audio(path, sampling_rate=16000)`
- `venvs/asr` içinde pytest yok. Bu yüzden gerçek Silero runtime testi stdlib `unittest` ile yazıldı.
- `venvs/core` içinde Silero yok. Bu beklenen durum; ana ASR runtime `venvs/asr`.

### Eklenen Kod

- `core/pipelines/asr/vad.py` eklendi.
  - Sebep: normalize edilmiş WAV üzerinde Silero VAD çalıştırmak, konuşma segmentlerini ve `speech_ratio` metriğini üretmek.
- `core/pipelines/asr/__init__.py` güncellendi.
  - Sebep: VAD tiplerini ve `run_silero_vad` fonksiyonunu ASR paketinden import edilebilir yapmak.
- `tests/test_asr_vad.py` eklendi.
  - Sebep: model yüklemeden çalışan kontrat testleri sağlamak; duration okuma, timestamp clamp ve normalize edilmemiş WAV reddi.
- `tests/test_asr_vad_real_media.py` eklendi.
  - Sebep: gerçek medya üzerinde normalize + gerçek Silero VAD runtime smoke'u yapmak. Bu test `asr` venv'de `unittest` ile çalıştırılır; `core` venv'de Silero olmadığı için skip olur.

### İlk Sorun ve Düzeltme

İlk gerçek runtime denemesinde sorun çıktı:

- Silero'nun kendi `read_audio()` fonksiyonu `torchaudio.load()` yoluna girdi.
- Bu yol `torchcodec` yüklemeye çalıştı.
- `venvs/asr` içinde torchcodec native DLL yükleme hatası verdi.

Bu, A bloğundaki gerçek normalize testlerinde görünmemişti; çünkü normalize ffmpeg/ffprobe ile çalışıyor, Silero audio reader yolunu kullanmıyordu.

**Düzeltme:** `run_silero_vad()` artık Silero'nun `read_audio()` fonksiyonunu kullanmıyor. Normalize edilmiş WAV zaten 16 kHz mono 16-bit PCM olduğu için:

1. stdlib `wave` ile WAV okunuyor.
2. PCM s16 sample'ları stdlib `array` ile alınıyor.
3. `torch.tensor(..., dtype=torch.float32) / 32768.0` ile Silero'nun beklediği waveform tensor'ı üretiliyor.

**Neden böyle?**
Bu yöntem torchcodec/torchaudio decode zincirini tamamen bypass eder. Audio decode sorumluluğu zaten A bloğunda ffmpeg normalize ile çözülmüştü; B bloğunda tekrar decode stack riski almak gereksizdi.

### Gerçek Medya Runtime Sonucu

Gerçek medya: `E:\MITAS\testklipler\trt_haber (1).mp4`

Akış:

1. MP4 -> normalize WAV
2. normalize WAV -> Silero VAD

Sonuç:

- Audio duration: `95.62`
- Speech segment count: `10`
- Speech seconds: `65.0`
- Speech ratio: `0.679774`
- First segment: `start=6.2`, `end=7.6`, `duration=1.4`

### Test ve Doğrulama

- `tests/test_asr_vad.py` (`core` venv): 3 passed.
- `tests/test_asr_vad_real_media.py` (`core` venv): 1 skipped.
  - Sebep: Silero `core` venv'de yok; bu test gerçek ASR runtime'a ait.
- `tests.test_asr_vad_real_media` (`asr` venv, unittest): OK.
- `tests/test_asr_vad.py tests/test_asr_vad_real_media.py` (`core` venv): 3 passed, 1 skipped.
- Tüm test paketi (`core` venv): 79 passed, 1 skipped.

### Blok Sonu Öz-Kontrol

**Uyumlu mu?**
Evet. Kod, ASR planındaki "Normalize sonrası Silero VAD -> speech region listesi + speech_ratio" hedefiyle uyumlu.

**Amaca hizmet ediyor mu?**
Evet. Normalize edilmiş WAV'dan start/end/duration segmentleri ve clip-level `speech_ratio` üretildi.

**Başka bir şeyi bozuyor mu?**
Hayır. Tüm mevcut test paketi geçti. VAD kodu `core/pipelines/asr/` altında izole. `core` venv'de model bağımlılığı zorlanmıyor.

**Daha iyi olabilir miydi?**
Evet, ileride VAD parametreleri profile göre ayarlanabilir. Şimdilik default Silero threshold/min_speech/min_silence değerleri kullanıldı; çünkü bu blok entegrasyon ve kontrat bloğu. Profil bazlı kalibrasyon transcribe smoke sonuçlarıyla birlikte ele alınmalı.

### 2026-05-11 / Kullanıcı Doğrulama Kontrolü - Konuşma Yok vs Gerçek Sessizlik

Kullanıcı "çalıştığını kanıtlamak için bir video üzerinden gerçek test yapabilir miyiz, bana şu videoda şurada ses yok diye söyle" dedi. Bunun için aynı gerçek medya üzerinde iki kontrol yapıldı:

1. Silero VAD ile konuşma segmentleri ve konuşma olmayan aralıklar çıkarıldı.
2. ffmpeg `silencedetect` ile gerçek düşük seviye sessizlik arandı.

**Önemli ayrım:** Silero VAD "ses yok" değil, "konuşma yok" tespiti yapar. Fonda müzik, ambiyans veya efekt olabilir; VAD bunu konuşma olarak saymayabilir. Bu nedenle kullanıcıya iki ayrı sonuç verilecek.

**Video:** `E:\MITAS\testklipler\trt_haber (1).mp4`

**VAD sonucu:**

- Toplam süre: `95.62 sn`
- Speech ratio: `0.679774`
- Konuşma segmentleri: `10`

**VAD'a göre konuşma olmayan kontrol aralıkları:**

- `00:00.000 - 00:06.200`
- `00:11.600 - 00:14.600`
- `00:28.200 - 00:33.300`
- `00:46.600 - 00:47.800`
- `01:02.300 - 01:06.000`
- `01:13.900 - 01:15.500`
- `01:26.400 - 01:35.620`

**ffmpeg `silencedetect` sonucu (`noise=-35dB`, `d=0.5`):**

- Gerçek düşük seviye sessizlik: `01:33.343 - 01:35.660`

**Yorum:** Kullanıcı videoyu elle kontrol edecekse en net kontrol noktası sondaki `01:33.3 - 01:35.6` aralığıdır; ffmpeg'e göre de gerçek sessizlik burada. VAD açısından daha geniş son aralık `01:26.4 - 01:35.6` konuşmasız görünüyor; bu bölümde gerçek sessizlik sadece son ~2.3 saniyeye denk geliyor olabilir.

### 2026-05-11 / Son Denetim - B Bloğu Eksik Var mı?

Kullanıcı "burada yapmamız gereken başka test var mı, bu kısım tamam mı, tekrar bak" dedi. Bunun üzerine B bloğu son kez test kapsamı açısından denetlendi.

**Yakalanan küçük eksik:** Gerçek konuşmalı video runtime testi vardı; ancak tamamen sessiz normalize WAV için `0 segment / speech_ratio=0` runtime testi yoktu.

**Kapatılan eksik:**

- `tests/test_asr_vad_real_media.py` içine sessiz normalize WAV testi eklendi.
- Test gerçek Silero modeliyle `venvs/asr` içinde çalıştırıldı.
- Sonuç: sessiz WAV için `speech_segments=[]`, `speech_seconds=0.0`, `speech_ratio=0.0`.

**Çoklu gerçek medya smoke:**

Aynı Silero modeli tek kez yüklenerek 5 gerçek medya üzerinde normalize + VAD çalıştırıldı:

| Medya | Süre | Segment | Speech seconds | Speech ratio |
|---|---:|---:|---:|---:|
| `erd_test_video.mp4` | `195.257` | `64` | `143.9` | `0.736977` |
| `trt_haber (1).mp4` | `95.62` | `10` | `65.0` | `0.679774` |
| `trt_haber (2).mp4` | `146.704` | `20` | `126.0` | `0.858872` |
| `trt_haber (3).mp4` | `75.418` | `5` | `58.8` | `0.779655` |
| `1.mp4` | `171.691` | `5` | `15.9` | `0.092608` |

**Son test durumu:**

- `tests.test_asr_vad_real_media` (`asr` venv, unittest): 2 tests OK.
- `tests/test_asr_vad.py tests/test_asr_vad_real_media.py` (`core` venv): 3 passed, 2 skipped.
- Tüm test paketi (`core` venv): 79 passed, 2 skipped.

**Son karar:** B bloğu, yani Silero VAD entegrasyonu, mevcut kapsam için tamam kabul edilebilir. Bilinçli kalan tek konu profil bazlı VAD parametre kalibrasyonu; bu C/D bloklarından sonra gerçek transcript ve diarization sonuçlarıyla birlikte yapılmalı.

---

## 2026-05-11 / Blok C - faster-whisper Transcribe

### Neden Bu Blok?

ASR pipeline'ın üçüncü taşı, normalize edilmiş WAV ve VAD konuşma aralıklarından transcript üretmektir. Bu blok sadece segment-level transcript üretir; pyannote diarization ve speaker merge bu blokta yapılmaz.

### Ön Kontrol

- `models/asr/faster-whisper/large-v3` cache mevcut.
- `WhisperModel.transcribe()` imzası kontrol edildi.
- `multilingual` parametresinin faster-whisper default'u `False`; bu nedenle Karar 14 gereği kodda açıkça `multilingual=True` sabitlendi.
- Önceki teşhis scriptleri `local_files_only=True`, `device="cuda"`, `compute_type="float16"` ile çalışıyordu; C bloğu aynı yolu izliyor.

### Tasarım Kararı

Transcribe modülü VAD segmentlerini doğrudan faster-whisper'a parametre olarak vermez. Bunun yerine:

1. Normalize WAV'dan her VAD segmenti için küçük WAV chunk çıkarılır.
2. Her chunk faster-whisper ile transcribe edilir.
3. Chunk içi timestamp'ler ana medya zamanına `vad_segment.start` offset'iyle geri map edilir.

**Neden böyle?**
Bu, ASR implementasyon planındaki "Silero VAD region listesi faster-whisper'a doğrudan parametre olarak verilmez; transcribe modülü region'ları chunk/clip üretip işler" kararına uyar. Ayrıca C bloğu, faster-whisper'ın kendi `vad_filter` yolunu kapalı tutar.

### Eklenen Kod

- `core/pipelines/asr/transcribe.py` eklendi.
  - Sebep: faster-whisper model load, VAD chunk çıkarma, transcribe çağrısı, timestamp offset mapping ve transcript çıktısını tek sorumlulukta toplamak.
- `core/pipelines/asr/__init__.py` güncellendi.
  - Sebep: transcribe tiplerini ve fonksiyonlarını ASR paketinden import edilebilir yapmak.
- `tests/test_asr_transcribe.py` eklendi.
  - Sebep: model yüklemeden fake model ile kontrat testleri yapmak; özellikle `multilingual=True`, `vad_filter=False`, `word_timestamps=False`, timestamp offset mapping ve boş VAD davranışını doğrulamak.
- `tests/test_asr_transcribe_real_media.py` eklendi.
  - Sebep: gerçek medya üzerinde normalize -> VAD -> faster-whisper large-v3 transcribe smoke yapmak. Bu test `asr` venv'de `unittest` ile çalışır; `core` venv'de faster-whisper/Silero olmadığı için skip olur.

### Gerçek Medya Runtime Sonucu

Gerçek medya: `E:\MITAS\testklipler\trt_haber (1).mp4`

Akış:

1. MP4 -> normalize WAV
2. normalize WAV -> Silero VAD
3. İlk 3 uygun VAD segmenti -> faster-whisper large-v3 (`multilingual=True`)

Seçilen VAD segmentleri:

- `7.8 - 11.6`
- `14.6 - 28.2`
- `33.3 - 36.0`

Transcribe sonucu:

- Transcript segment count: `4`
- Language distribution: `{"tr": 4}`
- Transcript:

```text
P-16'lar Eskişehir 1. Anajet Üssü'nden havalandı. Eskişehir'de F-16 pilotlarının İzmir'de gerçekleştirilen EFES 2026 tatbikatı için hazırlıklarını TRT Haber ekibi görüntüledi. Pilotlar gökyüzünde karşılışacakları G kuvvetine karşı ekipmanlarını giyip hangara geçti. İntim kontroller, uçuş hazırlıkları yapıldı.
```

**Kalite notu:** Bu blok transcript kalitesini mükemmelleştirme bloğu değildir. Örneğin `F-16` -> `P-16` ve bazı kelime hataları görüldü. Bu beklenen bir smoke sonucu; kalite kalibrasyonu C bloğu sonunda değil, daha geniş gerçek medya transcribe/benchmark aşamasında yapılmalı.

### Test ve Doğrulama

- `tests/test_asr_transcribe.py` (`core` venv): 3 passed.
- `tests/test_asr_transcribe.py tests/test_asr_transcribe_real_media.py` (`core` venv): 3 passed, 1 skipped.
- `tests.test_asr_transcribe_real_media` (`asr` venv, unittest): OK.
- Tüm test paketi (`core` venv): 82 passed, 3 skipped.

### Blok Sonu Öz-Kontrol

**Planla uyumlu mu?**
Evet. Normalize + VAD çıktısı kullanılarak segment-level transcript üretildi. `multilingual=True`, `vad_filter=False`, `word_timestamps=False` açıkça uygulanıyor.

**Amaca hizmet ediyor mu?**
Evet. C bloğunun amacı olan "VAD segmentleri -> transcript segmentleri" davranışı hem fake model testinde hem gerçek medya + large-v3 smoke'ta çalıştı.

**Başka şeyi bozuyor mu?**
Şimdilik hayır. Kod yeni `core/pipelines/asr/transcribe.py` altında izole. Core testleri model bağımlılığına zorlanmıyor; gerçek model testi ASR venv'e ait.

**Daha iyi olabilir miydi?**
Evet. Chunk bazlı transcribe, segmentler arası bağlamı sınırlayabilir. Buna karşılık bu yöntem kontrollü, VAD uyumlu ve timestamp offset açısından açık. Daha sonra kalite benchmark'ında full-audio transcribe + VAD chunk transcribe karşılaştırması yapılabilir.

### 2026-05-11 / C Bloğu Düzeltme - Giriş Cümlesi ve Multilingual Test

Kullanıcı üç kritik nokta sordu:

1. Kalite ne zaman düzeltilecek?
2. Girişte atlanan cümlenin sebebi ne?
3. Türkçe/İngilizce karışık gerçek test için `erd_test_video.mp4` eklenmeli.

#### Kalite Ne Zaman Düzeltilecek?

Kalite kalibrasyonu C bloğunun içinde kapatılmayacak. C bloğunda amaç transcribe hattının doğru bağlanmasıydı. Kalite düzeltme için doğru zaman:

- C bloğu sonunda bariz entegrasyon hataları düzeltilir.
- D diarization ve E/F schema + kalite raporu bağlandıktan sonra gerçek mini ASR benchmark yapılır.
- O aşamada VAD threshold, chunk padding, chunk bazlı vs full-audio transcribe karşılaştırması, beam/temperature/condition ayarları birlikte değerlendirilir.

Sebep: Transcript kalitesi tek parametreyle çözülmez; VAD sınırı, chunk bağlamı, multilingual davranış, diarization ve kalite metrikleri birlikte görülmeli.

#### Girişte Atlanan Cümlenin Sebebi

Video: `E:\MITAS\testklipler\trt_haber (1).mp4`

Kullanıcı `5. sn de başlayan "tüm hazırlıklar tamamlandı"` cümlesinin eksik olduğunu söyledi. Teşhis:

- İlk VAD segmenti: `6.2 - 7.6`
- Kullanıcı gözlemine göre cümle yaklaşık `5. sn` civarında başlıyor.
- C smoke testinde ayrıca `duration >= 2.0` filtresi vardı; ilk segment `1.4 sn` olduğu için smoke seçimine girmemişti.
- İlk segment tek başına transcribe edildiğinde `Hazırlıklar tamamlandı.` geliyordu; yani hem smoke seçimi hem de VAD başlangıç sınırı ilk kelimeyi riske atıyordu.

**Düzeltme:**

- `transcribe_vad_segments()` artık VAD segmentini tam sınırdan kesmiyor.
- Her VAD chunk için `1.5 sn` pre/post padding eklendi.
- Padding komşu VAD segmentinin içine taşmıyor; böylece gereksiz tekrar azaltılıyor.

Yeni sonuç:

```text
Tüm hazırlıklar tamamlandı.
```

Bu cümle artık gerçek medya transcribe testinde assert ediliyor.

#### erd_test_video Multilingual Test

Yeni gerçek medya testi `tests/test_asr_transcribe_real_media.py` içine eklendi.

Video: `E:\MITAS\testklipler\erd_test_video.mp4`

Seçilen VAD aralığı:

- VAD segment indexleri: `38:44`
- Yaklaşık zaman: `108.3 - 127.5`

Bu bölümde Türkçe ve İngilizce birlikte var. Test artık şunları doğruluyor:

- `multilingual=True`
- Dil dağılımında en az 1 `tr`
- Dil dağılımında en az 1 `en`
- Transcript içinde `Prime Minister`
- Transcript içinde `don't have time`
- Transcript içinde `Altıncı`

Gerçek smoke çıktısında görülen örnek:

```text
iki söz söyleyeceğim. Prime Minister, we can't start the debate again. Please, we just don't have time. ... Altıncı maddesinde der ki öldürmeyeceksin.
```

**Sonuç:** Türkçe/İngilizce karışık gerçek medya test kapsamına alındı. Bu, Karar 14 (`multilingual=True`) için C bloğundaki en önemli gerçek regresyon testidir.

**Doğrulama:**

- `tests/test_asr_transcribe.py tests/test_asr_transcribe_real_media.py` (`core` venv): 4 passed, 2 skipped.
- `tests.test_asr_transcribe_real_media` (`asr` venv, unittest): 2 tests OK.
- Tüm test paketi (`core` venv): 83 passed, 4 skipped.
