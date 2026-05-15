# 08 — TEST KLİPLERİ

> Son güncelleme: 2026-05-14
> Son değişen bölüm: dış Türkçe transcript probu / MediaSpeech benchmark

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

---

## 6. UNC WAV test havuzu — ASR fast/quality benchmark

Klasör:

`\\depo01cifs.int.trt.net.tr\sas_h264\testset\wav`

2026-05-13'te bu klasördeki 14 WAV dosyası küçükten büyüğe fast (`large-v3-turbo`) ve quality (`large-v3`) profilleriyle koşuldu. Toplam süre yaklaşık 682 dakikadır.

Çıktılar:

| Amaç | Dosya / klasör |
|---|---|
| Batch durum raporu | `outputs/asr_archive_all_wav_benchmark/batch_report.md` |
| Batch manifest | `outputs/asr_archive_all_wav_benchmark/batch_manifest.json` |
| Tüm fast/quality confidence diff | `outputs/asr_archive_all_wav_benchmark/model_diff_reports/all_films_fast_quality_confidence.md` |
| Aggregate diff özeti | `outputs/asr_archive_all_wav_benchmark/model_diff_reports/aggregate_fast_quality_diff.md` |
| Hybrid simülasyon özeti | `outputs/asr_archive_all_wav_benchmark/hybrid_simulation_reports/aggregate_hybrid_simulation.md` |

Özet bulgu:

- Fast tarafında high `no_speech_prob` segmentleri pratikte yok veya çok az.
- Quality tarafında high `no_speech_prob` segmentleri çok sayıda; bu segmentlerde hallüsinasyon adayı farklar görüldü.
- Fast ve quality farklı hata profillerine sahip; tek model kararı ground truth olmadan verilmemeli.
- Full hybrid araştırma için yararlı ama production için pahalı; aday yön `fast-first selective quality`.

Bu havuz ground truth değildir. Sadece model davranışı, confidence sinyali ve hybrid arbitration hipotezi için geniş stres/veri havuzudur.

---

## 7. Gold probe referans seti

Amaç: fast-only, quality-only ve hybrid adayını gerçek WER/CER ile küçük ama çeşitli bir sette ölçmek.

Manifest:

`benchmark_templates/asr_gold_probe_benchmark.yaml`

Çıktılar:

| Amaç | Dosya / klasör |
|---|---|
| Gold probe raporu | `outputs/asr_gold_probe_benchmark/report.md` |
| Draft referanslar | `outputs/asr_gold_probe_benchmark/draft_references/` |
| Elle düzeltilecek referanslar | `references/asr_gold_probe/` |

Seçilen örnekler:

| Sample | İçerik |
|---|---|
| `gold_h1_news_0000_0100` | temiz haber/profesyonel konuşma |
| `gold_neretva_bridge_0340_0440` | Neretva/Mostar özel isim ve önceki hallüsinasyon riski |
| `gold_merakli_momolar_0000_0100` | çocuk/dublaj/karakter adı |
| `gold_baris_manco_children_0140_0340` | Barış Manço çocuk/konuşma/müzik karışımı |
| `gold_kuran_0000_0100` | Kur'an yarışması / dini terimler |
| `gold_mehmed_0000_0100` | tarih/drama/özel isim |

Durum: fast ve quality çıktıları üretildi; referans `.txt` dosyaları hâlâ TODO. Elle düzeltme tamamlanınca `--score` ile WER/CER ölçülecek.

---

## 7A. Dış Türkçe transcript probu — MediaSpeech ve Common Voice

Bu bölüm `testklipler/` değil, `cache/external_datasets/` altındaki dış transcript kaynaklarını takip eder. Ham veri Git'e alınmaz.

| Kaynak | Yerel yol | Kullanım |
|---|---|---|
| MediaSpeech Turkish / OpenSLR108 | `E:\MITAS\cache\external_datasets\mediaspeech_tr\` | Geçici ASR gold/probe; medya-domain'e en yakın dış kaynak |
| Common Voice Turkish 25.0 | `E:\MITAS\cache\external_datasets\common_voice_tr_25\` | Yardımcı Türkçe kısa-utterance kontrol korpusu |

MediaSpeech ölçümü:

| Ölçüm | Değer |
|---|---:|
| Segment | 2,513 WAV/TXT |
| Toplam ses | yaklaşık 10 saat |
| 20 segment benchmark fast WER / CER | 0.1853 / 0.0966 |
| 20 segment benchmark quality WER / CER | 0.1775 / 0.0961 |
| Fast decode toplam | 14.098 sn |
| Quality decode toplam | 48.773 sn |

Karar etkisi:

- `large-v3-turbo` default decode modeli seçildi.
- `large-v3` selective fallback / üst denetim modeli oldu.
- `430d0aaf-8f12-4a09-964d-aa75f4157100` gerçek tail-gap regression örneği olarak kayda geçti.

Çıktılar:

| Amaç | Dosya / klasör |
|---|---|
| İnceleme raporu | `outputs/external_turkish_transcripts_review.md` |
| 20 segment benchmark | `outputs/external_turkish_transcripts_asr_smoke_20\benchmark_results.md` |
| Aday listesi | `outputs/external_turkish_transcripts_asr_smoke_20\candidates.json` |
| Benchmark scripti | `scripts/asr_mediaspeech_benchmark.py` |

Not: TRT iç transcript havuzu geldiğinde final kalibrasyon bu dış veriyle değil, TRT-domain WAV/TXT çiftleriyle yapılacak.

---

## 8. 2026-05-13 ASR test sonuçları ve denenen yollar

Bu bölüm 2026-05-13 ASR model seçimi / hybrid tartışması sırasında yapılan testleri ve ara sonuçları özetler.

### 8.1 Üç kliplik ilk tam test

İlk kapsam:

| Klip | Kaynak | Amaç |
|---|---|---|
| Barış Manço ile 7'den 77'ye | UNC WAV | çocuk/konuşma/müzik karışımı |
| Neretva Üstüne Düşen Hilal | UNC WAV | belgesel, özel isim, Mostar/Neretva |
| Meraklı Momolar | UNC WAV | çocuk/dublaj/karakter adı |

Çıktılar:

| Amaç | Dosya / klasör |
|---|---|
| İlk 3 klip benchmark | `outputs/asr_archive_full_benchmark/report.md` |
| Barış/Neretva/Momolar fast-quality transcriptleri | `outputs/asr_archive_full_benchmark/<sample_id>/{fast,quality}/transcript.txt` |
| Neretva confidence örnek raporu | `outputs/asr_archive_full_benchmark/model_diff_reports/neretva_screenshot_diff_confidence.md` |

Bulgu:

- Fast ve quality farklı yerlerde doğru/yanlış okuyor.
- Neretva'da `quality` bazı compound/bağlam kazanımları sağladı, ama `köprü yok -> köprüyor Mostar...` gibi hallüsinasyon da üretti.
- `avg_logprob` ve `no_speech_prob` skorlarının `archive.json` içinde saklanmadığı görüldü; bu eksik düzeltildi. Artık segment arşivinde `avg_logprob`, `no_speech_prob`, `source_chunk_index` tutuluyor.

### 8.2 Tüm UNC WAV havuzu fast/quality testi

Kapsam:

- 14 WAV
- Yaklaşık 682 dakika ses
- Her dosya için `fast / large-v3-turbo` ve `quality / large-v3`

Çalışma şekli:

| Yol | Deneme | Sonuç |
|---|---|---|
| 3 paralel worker | Küçükten büyüğe dosya bazlı fast+quality | Fast tarafı büyük ölçüde tamamlandı; bazı quality koşuları native crash ile yarım kaldı |
| Resume, 1 worker | Eksik quality koşuları tamamlandı | 14/14 dosyada fast ve quality çıktısı tamamlandı |

Not: İlk 3 paralel koşuda bazı worker'lar `3221226505 / 0xC0000409` ile düştü. Resume koşusu kalan işleri tamamladı. Bu yüzden uzun production decode için paralellik kontrollü ele alınmalı; 3 paralel GPU iş yükü mümkün ama stable kabul edilmemeli.

Toplu çıktı:

| Amaç | Dosya |
|---|---|
| Batch durum | `outputs/asr_archive_all_wav_benchmark/batch_report.md` |
| Manifest | `outputs/asr_archive_all_wav_benchmark/batch_manifest.json` |
| Worker logları | `outputs/asr_archive_all_wav_benchmark/logs/` |

Öne çıkan runtime/verim:

| Örnek | Süre | Fast runtime | Quality runtime | Quality / Fast |
|---|---:|---:|---:|---:|
| H1 | 1.70 dk | 22.616 sn | 33.517 sn | 1.48x |
| Neretva | 33.01 dk | 96.947 sn | 387.548 sn | 4.00x |
| Meraklı Momolar | 20.39 dk | 107.578 sn | 160.933 sn | 1.50x |
| Barış Manço | 46.50 dk | 213.848 sn | 389.381 sn | 1.82x |
| Adam Olacak Çocuk | 45.53 dk | 300.644 sn | 908.437 sn | 3.02x |
| Mehmed Fetihler Sultanı | 155.72 dk | 507.684 sn | 1078.512 sn | 2.12x |

Bulgu:

- Quality genelde daha yavaş; fark klip karakterine göre 1.5x ile 4x arasında oynuyor.
- Full fast+quality production maliyeti ciddi; bu yüzden full hybrid production default'u uygun görünmüyor.

### 8.3 Fast/quality kelime farkı ve confidence raporları

Üretilen raporlar:

| Amaç | Dosya |
|---|---|
| Tüm filmler tek dosya confidence diff | `outputs/asr_archive_all_wav_benchmark/model_diff_reports/all_films_fast_quality_confidence.md` |
| Tüm filmler JSON | `outputs/asr_archive_all_wav_benchmark/model_diff_reports/all_films_fast_quality_confidence.json` |
| Aggregate diff | `outputs/asr_archive_all_wav_benchmark/model_diff_reports/aggregate_fast_quality_diff.md` |

Toplam farklar:

| Metrik | Değer |
|---|---:|
| İncelenen klip | 14 |
| Fast/quality kelime değişimi | 2024 |
| Fast ekstra kelime | 511 |
| Quality ekstra kelime | 1500 |

En fazla fark çıkanlar:

| Klip | Substitution |
|---|---:|
| Mehmed Fetihler Sultanı | 645 |
| Adam Olacak Çocuk | 404 |
| Barış Manço | 265 |
| Kur'an-ı Kerim yarışması | 246 |
| Kampüsteyiz | 101 |
| Neretva | 71 |

Confidence bulgusu:

- Quality `no_speech_prob > 0.10` olan fark satırı: 838.
- Bu 838 satırda combined skora göre fast daha güvenli görünen: 743; quality daha güvenli görünen: 60; near-tie: 35.
- Bu, hybrid fikrini destekler ama doğruluğu kanıtlamaz; çünkü confidence modelin kendi öz-güvenidir, ground truth değildir.

### 8.4 Hybrid simülasyonu

Amaç: Full hybrid production pahalı olduğu için, mevcut fast/quality archive çıktılarından konservatif arbitration simülasyonu yapmak.

Kural:

```text
quality default

auto_swap_to_fast if:
  quality no_speech > 0.10
  quality segment <= 4 sn
  fast combined >= quality combined + 0.10
  time overlap var
```

Çıktılar:

| Amaç | Dosya |
|---|---|
| Aggregate hybrid simülasyon | `outputs/asr_archive_all_wav_benchmark/hybrid_simulation_reports/aggregate_hybrid_simulation.md` |
| Tekil simülasyon raporları | `outputs/asr_archive_all_wav_benchmark/hybrid_simulation_reports/` |

Sonuç:

| Metrik | Değer |
|---|---:|
| Toplam ses | 682.251 dk |
| Riskli quality segmenti | 2770 |
| Otomatik fast'e swap adayı | 1793 |
| Review adayı | 977 |
| Auto-swap toplam süre | 3359 sn (~56 dk) |
| Review toplam süre | 5062 sn (~84 dk) |

Yorum:

- Hybrid fikri destekleniyor: quality risk sinyali verdiğinde fast çok sık daha güvenli skora sahip.
- Ancak otomatik doğruluk kanıtı yok; WER/CER için gold set gerekli.
- Full hybrid pahalı; daha doğru üretim yönü `fast-first selective quality`.

### 8.5 Gold probe testi

Opus eleştirisi sonrası ana eksik netleşti: ground truth olmadan model/hybrid doğruluğu kanıtlanamaz.

Bu yüzden küçük ama çeşitli gold probe seti başlatıldı:

| Örnek | Amaç |
|---|---|
| `gold_h1_news_0000_0100` | temiz haber |
| `gold_neretva_bridge_0340_0440` | Mostar/Neretva özel isim ve hallüsinasyon riski |
| `gold_merakli_momolar_0000_0100` | çocuk/dublaj |
| `gold_baris_manco_children_0140_0340` | çocuk/konuşma/müzik |
| `gold_kuran_0000_0100` | dini terimler |
| `gold_mehmed_0000_0100` | tarih/drama/özel isim |

Çıktılar:

| Amaç | Dosya / klasör |
|---|---|
| Manifest | `benchmark_templates/asr_gold_probe_benchmark.yaml` |
| Gold probe raporu | `outputs/asr_gold_probe_benchmark/report.md` |
| Draft referanslar | `outputs/asr_gold_probe_benchmark/draft_references/` |
| Elle düzeltilecek referanslar | `references/asr_gold_probe/` |

Durum:

- Fast ve quality çıktıları üretildi.
- Referans dosyaları hâlâ TODO.
- Referanslar doldurulunca WER/CER ile gerçek karar verilecek.

### 8.6 Şu anki ara sonuç

Şu an kesin üretim kararı yok. Desteklenen hipotez:

```text
fast-first selective quality
```

Yani:

1. Fast full decode.
2. Riskli segment/pencere tespiti.
3. Sadece seçili pencerelerde quality decode.
4. Segment arbitration.
5. Audit log ve gerekirse review candidate.

Reddedilen veya ertelenen yollar:

| Yol | Durum | Neden |
|---|---|---|
| Sadece fast | Ertelendi | Bazı bağlam/compound/özel isim kazanımları quality'de daha iyi olabilir |
| Sadece quality | Zayıf aday | Daha yavaş ve high-no-speech/hallüsinasyon riski var |
| Full hybrid | Araştırma için iyi, production için pahalı | Her klipte fast+quality full decode maliyeti yüksek |
| Hotwords/manual prompt | Production ana çözüm değil | 200k belgesel ölçeğinde manuel veri sağlanamaz; metadata varsa opsiyonel destek olabilir |
| Beam size artırma | Şimdilik ertelendi | Süreyi artırır; önce gold set ve selective strategy ölçülmeli |

Sonraki zorunlu adım:

1. `references/asr_gold_probe/` altındaki 6 referans metin elle doldurulur.
2. Gold probe score çalıştırılır.
3. Fast-only / quality-only / konservatif hybrid gerçekten WER/CER ve named entity hatası açısından karşılaştırılır.
