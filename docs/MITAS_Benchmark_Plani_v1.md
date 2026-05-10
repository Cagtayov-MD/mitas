# MITAS Benchmark / Test Set Plani v1

## Sprint

- Sprint: Sprint 3 — Benchmark / Test Set Plani
- Kapsam: Plan ve tablo yapisi
- Yapilmayanlar: model kurulumu, benchmark kosma, video analizi, OCR/ASR/Face/VisualTag calistirma, UI, pipeline

## Amac

MITAS model ve arac secimlerini hissiyata degil, olculebilir benchmarklara baglamak.

Bu sprint model kurulum sprinti degildir. Hedef, hangi modulin hangi test setiyle, hangi metriklerle ve hangi gecme/kalma esikleriyle degerlendirilecegini netlestirmektir.

## Minimum Test Seti

V1 oncesi minimum test seti toplam 20 saat olarak planlanir.

| Kategori | Sure | Amac |
| --- | ---: | --- |
| Haber / panel KJ | 5 saat | KJ, alt yazi, konusmaci ve ekran metni davranisini olcmek |
| Muzik programi | 5 saat | Sarkı anonsu, performans, ASR ve audio activity senaryolarini olcmek |
| Belgesel / intertitle | 5 saat | Ara baslik, anlatim, sahne baglami ve OCR davranisini olcmek |
| Film / jenerik | 5 saat | Jenerik, credit event, ekran metni ve uzun metin akislarini olcmek |

## Sahiplik

Benchmark kapanisi icin iki sahiplik rolu atanmalidir.

| Rol | Atama | Durum |
| --- | --- | --- |
| Test Set Owner | TBD | BLOCKING |
| Ground Truth Owner | TBD | BLOCKING |

Bu iki rol atanmadan Sprint 3 kabul kriterleri tam kapanmis sayilmaz.

## Benchmark Kayit Alanlari

Her benchmark kaydi su alanlari tasir:

- `benchmark_id`
- `benchmark_name`
- `module`
- `models_or_tools`
- `test_video_set`
- `ground_truth_owner`
- `metric_list`
- `pass_fail_threshold`
- `target_week`
- `responsible_person_or_team`
- `final_decision`
- `decision_date`
- `notes`
- `blocking_before_model_install`

## Ilk Benchmark Listesi

| Benchmark | Modul | Blocking | Dosya |
| --- | --- | --- | --- |
| OCR/KJ benchmark | OCR/KJ | Yes | `benchmark_templates/ocr_kj_benchmark.yaml` |
| ASR benchmark | ASR | Yes | `benchmark_templates/asr_benchmark.yaml` |
| Audio Activity benchmark | Audio Activity | Yes | `benchmark_templates/audio_activity_benchmark.yaml` |
| Face benchmark | Face | Yes | `benchmark_templates/face_benchmark.yaml` |
| Visual Tag benchmark | Visual Tag | Yes | `benchmark_templates/visual_tag_benchmark.yaml` |

## OCR/KJ Benchmark

Amac:

- OneOCR, PaddleOCR, VITOS baseline, EasyOCR ve Tesseract karsilastirmasi.

Metrikler:

- KJ line accuracy
- Turkce karakter dogrulugu
- ROI-first basari orani
- Temporal merge basarisi
- Runtime per minute
- False positive orani

Oncelik:

1. OneOCR
2. PaddleOCR / PP-OCRv5 multilingual
3. VITOS baseline
4. EasyOCR
5. Tesseract

## ASR Benchmark

Amac:

- faster-whisper large-v3 ana motor
- distil-large-v3 / medium fallback
- WhisperX timestamp dogrulugu

Metrikler:

- WER
- Timestamp drift
- Word-level alignment success
- Runtime per minute
- VRAM usage

## Audio Activity Benchmark

Amac:

- Speech / music / applause / silence ayrimi.

Metrikler:

- Music segment precision
- Music segment recall
- Speech/music boundary error
- Runtime per minute

## Face Benchmark

Amac:

- SCRFD / ArcFace / HDBSCAN akisinda kalite kapilarini test etmek.

Baslangic esikleri:

- `min_face_height`: 80 px
- `blur_laplacian_min`: 100
- `pose_yaw_max`: 30 derece
- `pose_pitch_max`: 25 derece
- `min_track_duration`: 1.5 sn
- `min_detector_confidence`: 0.70

Metrikler:

- False match rate
- Missed face rate
- Cluster purity
- Review yuku
- Runtime per minute

## Visual Tag Benchmark

Amac:

- YOLO-World / SigLIP kontrollu tag uretimini test etmek.

Metrikler:

- Tag precision
- Tag recall
- Scene-level voting success
- False positive orani
- Runtime per minute

## Kabul Kriterleri

- Benchmark tablosu olusturuldu.
- Minimum 20 saatlik test seti kategorileri belirlendi.
- Test Set Owner alani tanimlandi.
- Ground Truth Owner alani tanimlandi.
- Her benchmark icin metrik ve gecme/kalma alanlari olusturuldu.
- Model kurulumuna gecmeden once blocking benchmarklar isaretlendi.

## Son Karar

- Sprint 3 plan yapisi hazir.
- Sahip atamalari `TBD` oldugu icin operasyonel benchmark kapanisi icin owner atamasi bekleniyor.
