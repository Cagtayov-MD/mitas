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
