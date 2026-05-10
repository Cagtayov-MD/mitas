# 08 — TEST KLİPLERİ

> Son güncelleme: 2026-05-11
> Son değişen bölüm: ilk kayıt

Bu dosya `E:\MITAS\testklipler\` altındaki ham test materyalini anlatır. Video/ses dosyaları Git'e alınmaz; sadece bu envanter ve kullanım notları takip edilir.

---

## 1. Klasör

`E:\MITAS\testklipler\`

Bu klasör smoke, benchmark hazırlığı ve sprint içi uygun örnek seçimi için ham havuzdur. Ground truth değildir. Bir dosya sprint kabul klibi seçildiğinde ayrıca ilgili sprint dosyasına yazılır.

---

## 2. Haber / Stüdyo Kısa Klipleri

| Dosya | Süre | Teknik | Kullanım notu |
|---|---:|---|---|
| `trt_haber (1).mp4` | 01:35.660 | 1280x720 H.264, AAC 44.1 kHz stereo | Düz haber; spiker, KJ ve röportaj içeriği için uygun. |
| `trt_haber (2).mp4` | 02:26.744 | 1280x720 H.264, AAC 44.1 kHz stereo | Düz haber; spiker, KJ ve röportaj içeriği için uygun. |
| `trt_haber (3).mp4` | 01:15.452 | 1280x720 H.264, AAC 44.1 kHz stereo | Açık stüdyo haber sunumu / spiker konuşmaları derlemesi. |

---

## 3. Geniş Test Klipleri

| Dosya | Süre | Teknik | Kullanım notu |
|---|---:|---|---|
| `1.mp4` | 02:51.680 | 1280x720 H.264, çoklu AAC 48 kHz stereo | Müzikli TRT tanıtımı; farklı konuşmalar, hızlı plan geçişleri. Showcase/robustness için iyi, ilk ASR smoke için zorlayıcı. |
| `2.mp4` | 02:05:35.488 | 854x480 H.264, çoklu AAC 48 kHz stereo | Türkçe film; iyi çözünürlük, sonunda jenerik var. FilmCreditsParser ve OCR/jenerik çalışmaları için aday. |
| `3.mp4` | 02:03:36.576 | 854x480 H.264, çoklu AAC 48 kHz stereo | Türkçe film; iyi çözünürlük, sonunda jenerik var. FilmCreditsParser ve OCR/jenerik çalışmaları için aday. |
| `4.mp4` | 04:21:51.840 | 1280x720 H.264, çoklu AAC 48 kHz stereo | Atletizm şampiyonası; İngilizce KJ'ler, konuşmalar, iyi görüntü ve çok sayıda branş. OCR/visual/audio activity için geniş stres klibi. |
| `5.mp4` | 40:36.040 | 1280x720 H.264, çoklu AAC 48 kHz stereo | Belgesel. ASR, sahne/tag ve uzun form segmentleme için aday. |

---

## 4. Ses Smoke Materyali

| Dosya | Süre | Teknik | Kullanım notu |
|---|---:|---|---|
| `erd_test_sound.wav` | 03:15.210 | PCM16 WAV, 44.1 kHz stereo | ASR/alignment/denoise hazırlık smoke'larında kullanıldı. |
| `erd_test_sound_noisy_12dB.wav` | 03:15.210 | PCM16 WAV, 44.1 kHz stereo | Synthetic 12 dB SNR noisy varyant. Denoise smoke için uygun. |
| `erd_test_video.mp4` | 03:15.297 | 1280x720 H.264, AAC 44.1 kHz stereo | `erd_test_sound.wav` ile ilişkili kısa video smoke materyali. |

---

## 5. Kullanım Kılavuzu

İlk ASR v0.1 batch smoke için en uygun adaylar `trt_haber (1).mp4`, `trt_haber (2).mp4` ve `trt_haber (3).mp4` dosyalarıdır.

`1.mp4`, `4.mp4` ve uzun film/belgesel klipleri ilk smoke için değil, daha sonra zorlayıcı benchmark ve modül stres testleri için tutulur.

Kliplerin hiçbiri otomatik ground truth kabul edilmez. Ground truth ayrı dosyada ve geliştirici onayıyla oluşturulur.
