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
