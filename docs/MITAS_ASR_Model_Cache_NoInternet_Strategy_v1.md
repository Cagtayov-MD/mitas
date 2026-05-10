# MITAS ASR Model Cache / No-Internet Model Strategy v1

## 1. Amaç

Bu doküman, ASR model dosyalarının nerede tutulacağını, ne zaman internet kullanılacağını ve model yükleme smoke testlerinin nasıl yapılacağını belirlemek için hazırlanmıştır.

Bu sprintte model indirilmez, model instantiate edilmez, ses/video işlenmez, benchmark çalıştırılmaz ve production ana motor seçimi yapılmaz.

## 2. Cache Klasörleri

ASR model dosyaları ve Hugging Face cache dosyaları `E:\MITAS` altında tutulacaktır.

- `E:\MITAS\models\asr\faster-whisper`
- `E:\MITAS\cache\huggingface`

## 3. Hugging Face Cache Environment Planı

İleride model indirme veya local cache kullanımı yapılırken şu environment değerleri geçici olarak kullanılacaktır:

- `HF_HOME=E:\MITAS\cache\huggingface`
- `HF_HUB_CACHE=E:\MITAS\cache\huggingface\hub`

Kalıcı `setx` veya sistem environment değişikliği yapılmayacaktır.

## 4. Offline Guard

Varsayılan smoke testlerde şu alanlar korunacaktır:

- `model_download_executed: false`
- `model_instantiated: false`

Model yükleme sprinti haricinde `HF_HUB_OFFLINE=1` kullanılacaktır.

Amaç, yanlışlıkla Hugging Face Hub üzerinden model indirilmesini veya model instantiate edilmesini engellemektir.

## 5. İlk Model-Load Smoke Stratejisi

İlk gerçek model-load smoke büyük modelle yapılmayacaktır.

İlk aday:

- `Systran/faster-whisper-tiny` veya küçük eşdeğer model

Bu sprintte model indirilmeyecektir.

## 6. Büyük Model Stratejisi

`large-v3`, `distil-large-v3` ve `medium` modelleri benchmark öncesi production ana motor ilan edilmeyecektir.

Sıra:

1. Tiny/small model-load smoke
2. Local cache ve offline guard doğrulaması
3. Gerçek ASR test setiyle benchmark
4. VRAM/runtime/kalite metrikleri
5. Profil bazlı uygunluk değerlendirmesi
6. Seçim nedeni raporu

## 7. Raporlama Alanları

Model yükleme yapılacak sprintte raporda şu alanlar tutulacaktır:

- `model_id`
- `model_cache_dir`
- `download_allowed`
- `download_executed`
- `local_files_only`
- `model_instantiated`
- `device`
- `compute_type`
- `vram_before_mb`
- `vram_after_mb`
- `status`

## 8. Yasaklar

Bu sprintte şunlar yapılmayacaktır:

- Model indirme
- `WhisperModel` instantiate
- `transcribe`
- Ses/video işleme
- Benchmark
- Production ana motor seçimi
- `selected_as_engine` değiştirme

## Son Karar

ASR model cache ve no-internet çalışma stratejisi belirlenmiştir.

Model yükleme ve model indirme ayrı sprintte, açık kullanıcı onayıyla yapılacaktır.
