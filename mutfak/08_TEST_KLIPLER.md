# 08 — TEST KLİPLERİ

> Son güncelleme: 2026-05-18
> Son değişen bölüm: §8.8 — RADYO_G_NLER kalibrasyonu (stock artifact, stereo redundancy, channel_mode default, content profile wire)

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
- 2026-05-16 itibarıyla üç referans dosyası gerçek içerik taşıyor ama timestamp marker içeriyor: `gold_neretva_bridge_0340_0440`, `gold_merakli_momolar_0000_0100`, `gold_baris_manco_children_0140_0340`. Skorlama sırasında marker'lar bellekte temizlendi; referans dosyalarına dokunulmadı.
- Kalan üç referans (`gold_h1_news_0000_0100`, `gold_kuran_0000_0100`, `gold_mehmed_0000_0100`) hâlâ TODO/placeholder.
- Referanslar tamamen temizlenince fast-only / quality-only / selective hybrid kararı daha geniş WER/CER ve named entity incelemesiyle tekrar ölçülecek.

2026-05-16 current pipeline ölçümü:

| Varyant | Örnek | Weighted WER | Macro WER | Weighted CER | WhisperX | Diarization | Safety | Pipeline RTF | Transcribe RTF |
|---|---:|---:|---:|---:|---|---|---|---:|---:|
| `bulten_haber` default (`large-v3-turbo`) | 3 | 0.1657 | 0.2747 | 0.1298 | 3/3 ok, min coverage 1.000 | 3/3 ok | 3/3 safe | 0.2697 | 0.0840 |
| `bulten_haber + quality override` (`large-v3`) | 3 | 0.1424 | 0.2497 | 0.1135 | 3/3 ok, min coverage 1.000 | 3/3 ok | 3/3 safe | 0.3211 | 0.1517 |

Per-sample kısa tablo:

| Örnek | Turbo WER/CER | Quality WER/CER | Not |
|---|---:|---:|---|
| `gold_neretva_bridge_0340_0440` | 0.3086 / 0.2160 | 0.2469 / 0.1920 | Quality daha iyi; özel isim/bağlam riski yüksek |
| `gold_merakli_momolar_0000_0100` | 0.4412 / 0.5130 | 0.4412 / 0.4456 | WER eşit; CER quality lehine, ikisi de zayıf |
| `gold_baris_manco_children_0140_0340` | 0.0742 / 0.0463 | 0.0611 / 0.0399 | Quality daha iyi ama turbo da kullanılabilir |

Ölçüm çıktıları:

| Amaç | Dosya / klasör |
|---|---|
| Current pipeline kalite raporu | `outputs/asr_current_pipeline_quality_20260516/report.md` |
| JSON rapor | `outputs/asr_current_pipeline_quality_20260516/report.json` |
| Turbo/default koşumları | `outputs/asr_current_pipeline_quality_20260516/<sample_id>/` |
| Quality override koşumları | `outputs/asr_current_pipeline_quality_20260516/<sample_id>__quality_override/` |

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

### 8.7 ASR + WhisperX: hangileri ciddi fark yaratır?

Bu bölüm 2026-05-16 kullanıcı sorusu için net özet kaydıdır. `large-v3` bazı gold probe örneklerinde WER/CER'i düşürdü; fakat önceki TRT-domain geniş koşumlarda `large-v3-turbo` birçok alanda daha sağlıklı ve daha stabil davrandı. Bu yüzden karar "quality ana model" değil, **turbo default + selective/hybrid kalite onarımı + WhisperX alignment** yönündedir.

| Katman | Ciddi fark seviyesi | Neyi iyileştirir? | Neden önemli? | Durum |
|---|---|---|---|---|
| WhisperX ana pipeline alignment | Çok yüksek ürün/evidence etkisi | Kelime timestamp, timeline, altyazı, arama sonucu, coverage ölçümü | Metni daha doğru yazmaz; ama transcript'i video/sese güvenilir biçimde bağlar | Yapıldı |
| Fast-first selective quality repair | Çok yüksek metin kalite/performance etkisi | Riskli pencereyi `large-v3` ile onarır, tüm dosyayı pahalı çözmez | Turbo default'un iyi olduğu alanları korur; quality'nin iyi olduğu pencereleri seçer | Yapıldı; `fallback_report` ile chunk arbitration raporu var |
| VAD gap repair | Yüksek | Atlanan konuşma pencerelerini geri kazanır | WER'den daha kritik olan "konuşma var ama transcript yok" riskini düşürür | Yapıldı; `vad_gap_uncovered` selective repair'e bağlı |
| Entity / özel isim normalizasyonu | Çok yüksek metadata etkisi | Kişi, yer, kurum, program adı hatalarını azaltır | TRT arşiv aramasında özel isim hatası genel WER'den daha zararlı olabilir | İlk katman yapıldı; deterministic lexicon reviewable normalized çıktı üretir |
| Diarization + WhisperX | İçeriğe bağlı yüksek | Kim, neyi, ne zaman söyledi | Tek anlatıcıda az fark; panel/röportaj/haber bülteninde ciddi fark | Yapıldı; `speaker_word_timeline` coverage bloğu var |
| WhisperX kalite denetimi | Orta-yüksek | Coverage düşükse retry/repair işareti | "Job done" ile "güvenilir alignment" ayrılır | Yapıldı; düşük coverage eksik segment retry var |
| UI kelime/timeline deneyimi | Yüksek ürün etkisi | Kelimeye tıklama, arama sonucuna atlama, altyazı düzeltme | WhisperX'in kullanıcının gördüğü değere dönüşmesi | Yapıldı; seçili/zoomlu segmentlerde word tick görünür |

İlk 3 uygulama notu:

2026-05-16 uygulama notu: İlk üç madde ürün yoluna alındı. Selective repair raporu `fallback_report`; VAD gap repair `vad_gap_uncovered` selective repair; entity normalization `normalized_text`/`normalized_transcript`/`normalized_entities` olarak çıktı verir. Entity katmanı ASR metnini ezmez, reviewable öneri üretir.

Kalan uygulama notu:

2026-05-16 ikinci uygulama notu: WhisperX düşük coverage durumunda eksik segmentler tek retry alır. Diarization+WhisperX birleşimi `quality_report.speaker_word_timeline` ile ölçülür. Entity önerileri Qwen/üst-denetim için kanıt paketi taşır. WebUI timeline kelime timestamp'lerini seçili/zoomlu segmentte küçük tick olarak gösterir.

2026-05-16 retest notu:

Tüm ASR+WhisperX kalite yatırımları tekrar test edildi. Hedefli ASR regresyon `46 passed`, ASR wildcard `139 passed, 9 skipped`, WebUI type-check/build geçti. Full `pytest tests -q` sonucu `257 passed, 10 skipped, 3 failed`; üç fail ASR dışı model manifest sayaç beklentisi (`candidate_count` 24 beklenirken 27).

Üç gerçek gold-probe current pipeline retestinde clean transcript eski current çıktıyla birebir aynı kaldı; bağlam/metin bozulmadı. Aggregate retest: weighted WER `0.1562`, macro WER `0.2569`, weighted CER `0.1122`; alignment `3/3 ok, coverage 1.000`; diarization `3/3 ok`; entity hit `0`. Speaker+word timeline yeni blok olarak 1/3 ok, 2/3 degraded raporladı; bu kaliteyi doğrudan artırmıyor ama "diarization ok olsa bile tüm kelimeler speaker'a bağlandı mı?" sorusuna dürüst sinyal veriyor.

Hız notu: Eski default current toplam `75.529 sn`, yeni retest toplam `83.687 sn`. Transcribe süresi aynı seviyede kaldı (`23.516 sn` -> `23.819 sn`). Artışın ana kaynağı Neretva klibinde diarization runtime varyansı (`7.768 sn` -> `17.880 sn`); yeni WhisperX retry bu kliplerde tetiklenmedi. Retest raporu: `outputs/asr_current_pipeline_retest_20260516/retest_report.md`.

Sonraki iyi olur listesi:

1. Entity normalization sözlüğünü TRT-domain kişi/kurum/program listesiyle büyütme.
2. Entity normalization için gerçek Qwen/üst-denetim hakem çağrısı: mevcut evidence packet + OCR/KJ/frame evidence ile karar üretme.
3. Diarization çok-konuşmacılı benchmark: panel/röportaj/stüdyo örneklerinde insan etiketli speaker label isabetini ölçme.
4. WebUI arama sonucundan kelime timestamp'e doğrudan atlama.
5. Düşük coverage retry eşiklerini gerçek hata klipleriyle kalibre etme.

Altın not:

Şu an yapılanlar güvenli altyapı ve doğru kalite sinyali tarafını sağlamlaştırdı. Bundan sonraki büyük kalite sıçraması model değiştirmekten değil; TRT kişi/kurum/program entity sözlüğü, gerçek Qwen evidence hakemi ve insan etiketli çok-konuşmacılı diarization benchmark üçlüsünden gelecek.

### 8.8 RADYO_G_NLER kalibrasyonu — stock artifact, stereo redundancy, channel_mode default, content profile wire (2026-05-18)

Bir radyo müzik programı klibinde (`RADYO_G_NLER.mp4`) çıkan üç somut patoloji bu turda kapatıldı. Klip bu envanterin formal "gold probe" setine değil, kalibrasyon vakası olarak kayda alındı. Önceki summary.json gözlemleri:

- Müzik / sessizlik pencerelerinde `Thank you`, `© transcript Emily Beynon` gibi ezberlenmiş İngilizce hallüsinasyonlar transcript'e sızıyordu.
- `summary.json:channels.requested_mode = "split"`, `auto_decided = false`, `lr_correlation = null` — yani split mode dış çağrıdan zorla forced edilmiş, Pearson hiç koşmamıştı. L ve R kanalı kulakla %99 aynı (aynı kaynak, iki mikrofon). Sonuç: aynı ses iki kez transkribe edildi, duplicate drop'lar ve yanıltıcı `selection_reason` üretti.
- `muzik_programi` content profile'ında `initial_prompt="Turkce muzik programi"` ve `beam_size=5` vardı ama `transcribe()` çağrısına ulaşmıyordu; sadece `summary.json:content_profile_metadata` içine yazılıyordu.

Yapılanlar:

| Patoloji | Müdahale | Referans |
|---|---|---|
| Stock English hallüsinasyon | `STOCK_ARTIFACTS` listesi `thank you`, `transcript emily beynon`, `subtitles by`, `amara org` vb. ile genişletildi. Normalize sonrası `quality_drop:stock_artifact` ile düşer. | DONE-ASR-009 |
| Forced split → duplicate transcribe | `analyze_stereo_redundancy()` Pearson median + Mid/Side dB ölçer; redundant ise summary'ye yazar ve forced split ile çakışıyorsa `channel_decision_override` flag + log WARNING. Otomatik mode-switch yok; observable katman. | DONE-ASR-010, Karar 35 |
| Default `channel_mode="mono"` stereo kırpıyordu / bilinçsiz split'e izin veriyordu | `run_asr_pipeline()` ve Tedial job runner default'ları `"auto"` yapıldı. Forced override saygı görür; observable katman yanlış override'ı yakalar. | DONE-ASR-011, Karar 36 |
| Content profile `beam_size` + `initial_prompt` Whisper'a ulaşmıyordu (DONE-ASR-004 teknik borcu) | `TranscribeParams.beam_size` eklendi; `transcribe()` `transcribe_params` parametresi alır; `pipeline.py:_build_transcribe_params()` content profile'dan override üretir ve L/R/mono çağrılarının üçüne birden geçirir. `muzik_programi` artık gerçekten `initial_prompt="Turkce muzik programi"` ile decode eder. | DONE-ASR-012 |

Doğrulama: `./venvs/core/Scripts/python.exe -m pytest tests/test_asr_stereo_redundancy.py tests/test_asr_pipeline.py tests/test_asr_channel_analysis.py -x -q` → 16 passed. Yeni `tests/test_asr_stereo_redundancy.py` 5 birim test içeriyor (identical channels → redundant high, independent freqs → not redundant, silence → insufficient_data, gain difference → still redundant, `to_dict()` JSON serializable).

Bekleyen iş: Üretim ASR sunucusu (asr_server.py uvicorn, `--reload` yok — kod değiştiğinde elle restart şart) elle restart sonrası RADYO_G_NLER klibiyle yeniden ölçüm. Beklenti: stock English hallüsinasyon düşer, summary'de `stereo_analysis.is_redundant_stereo=True` + `channel_decision_override` görünür (eğer çağrı hâlâ split forcing yapıyorsa), `muzik_programi` çağrılarında initial_prompt fiilen Whisper'a iner.

Sonraki kalibrasyon: gerçek TRT split-kanal kliplerinde (saha + stüdyo, çevirmen + konuşmacı vb. gerçek farklı kanal) `is_redundant_stereo=False` çıktığı doğrulanır; çıkmazsa Karar 35 eşikleri ayarlanır.
