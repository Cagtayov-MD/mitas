# MITAS Model Manifest ve Smoke Test Planı v1

## Amaç

Bu doküman Sprint 4 kapsamında test edilecek model ve araç adaylarını tek manifest altında toplamayı ve manifest parse/validasyon altyapısını hazırlamayı amaçlar.

Bu sprintte model seçimi yapılmaz.
Benchmark çalıştırılmaz.
Model indirilmez veya kurulmaz.
Video analizi, OCR/ASR/Face/VisualTag pipeline veya UI yazılmaz.

## Temel Kural

Hiçbir model benchmark öncesi production ana motor ilan edilmez.

Bu nedenle `model_manifest.yaml` içindeki tüm adaylarda:

```yaml
selected_as_engine: false
```

olarak kalır.

## Manifest Alanları

Her aday şu alanları taşır:

- `module_area`
- `candidate_name`
- `priority`
- `status`
- `venv`
- `install_state`
- `smoke_test_command`
- `expected_outputs`
- `benchmark_required`
- `selected_as_engine`
- `notes`

## İlk Aday Listesi

### OCR

1. OneOCR
2. PaddleOCR
3. VITOS baseline
4. EasyOCR
5. Tesseract

### ASR

1. faster-whisper large-v3
2. faster-whisper medium
3. faster-whisper distil-large-v3
4. WhisperX alignment
5. Silero VAD

### Diarization

1. pyannote
2. TBD fallback

### Audio Activity

1. YAMNet
2. basic energy/VAD baseline
3. music/speech detector TBD

### Face

1. SCRFD
2. ArcFace / InsightFace
3. ByteTrack tracker

### Visual Tag

1. YOLO-World
2. SigLIP
3. tag dictionary baseline

### Song Recognition

1. Chromaprint / fpcalc
2. local fingerprint DB
3. online lookup disabled by default

## Validasyon Kuralları

- YAML parse edilebilir olmalı.
- Her candidate `selected_as_engine: false` olmalı.
- Her candidate `benchmark_required: true` veya explicit `false` taşımalı.
- `module_area` boş olamaz.
- `candidate_name` boş olamaz.
- `priority` sayı olmalı.
- `status` boş olamaz.

## Smoke Test Hazırlığı

Manifest içindeki `smoke_test_command` alanları planlanan import/smoke komutlarını temsil eder.
Bu sprintte bu komutlar çalıştırılmaz.

Smoke testlerin amacı:

- adayın import edilebilirliğini görmek
- minimum CLI/runtime varlığını doğrulamak
- model seçimi yapmadan önce kurulum risklerini görünür yapmak
- VRAM/runtime benchmark öncesi temel uyumluluk kapısını hazırlamak

## Son Karar

Sprint 4 bu aşamada yalnızca model manifest ve smoke test hazırlığıdır.
Production ana motor seçimi, benchmark, model indirme/kurma ve pipeline çalıştırma bu sprint kapsamında yapılmaz.
