# 06 — KARARLAR GÜNLÜĞÜ

> Son güncelleme: 2026-05-14
> Son değişen bölüm: Live STT Preview player-audio WebSocket kararı (Karar 28)

Bu dosya MITAS projesinde **verilmiş kararların kalıcı kaydıdır**. Her karar tarih, başlık, kararın kendisi, gerekçesi ve varsa ilgili dosya referansıyla yazılır.

İptal edilen kararlar **silinmez**, üstü çizili olarak bırakılır ve neden iptal edildiği eklenir.

---

## Format

```
### YYYY-MM-DD / N — Karar başlığı

**Karar:** ...
**Gerekçe:** ...
**Referans:** ...
**Durum:** Aktif | İptal edildi (yyyy-mm-dd) | Revize edildi (yyyy-mm-dd)
```

---

## v5 Master Plan'dan miras kararlar (özet)

Aşağıdaki kararlar `MITAS_Master_Plan_Denetimli_v5.md` içinden seçilmiştir. Bu klasördeki operasyonel referans için en kritik olanlardır. Tam liste için master plan §9 ("Karar Günlüğü") bölümüne bakınız.

### 2026-05-09 / M1 — Türkçe-merkezli, web tabanlı, kurum içi MITAS

**Karar:** MITAS web tabanlı, Türkçe-merkezli, kurum içi (lokal) çalışan video/medya analiz sistemi olarak tasarlanır. Bulut çözümleri (axle.ai dahil) kapsam dışı kalır.
**Gerekçe:** TRT arşiv malzemesi biyometrik veri içerir; KVKK ve veri egemenliği bulut tabanlı çözümü engeller. Türkçe karakter ve TRT arşiv kalitesi yabancı çözümlerin optimize olmadığı alandır.
**Durum:** Aktif.

### 2026-05-09 / M2 — RTX 3090 / 24 GB VRAM hedef donanım

**Karar:** v1 planı RTX 3090 / 24 GB VRAM donanıma göre yapılır. RTX 6000 Pro / 96 GB varsayımları geçersizdir.
**Gerekçe:** Mevcut geliştirme donanımı 3090; production'da ölçeklenme adımı v2'ye bırakılır.
**Durum:** Aktif.

### 2026-05-09 / M3 — ASR ana motoru: faster-whisper large-v3

**Karar:** ASR ana motoru faster-whisper large-v3. Fallback: distil-large-v3 veya medium (OOM / performans bütçesi aşımı durumunda).
**Gerekçe:** Türkçe için en iyi açık model seçeneklerinden biri; RTX 3090'da çalışabilir; CTranslate2 ile hızlı.
**Referans:** Master plan §0.3.4.
**Durum:** Revize edildi (2026-05-14). Operasyonel ASR politikası için bkz. Karar 23 ve Karar 24: `large-v3-turbo` default, `large-v3` selective fallback / üst denetim modeli.

### 2026-05-09 / M4 — Filmde face identification kapalı

**Karar:** Filmde face identification yapılmaz. Sadece "yüz var" event'i tutulur. Kişi kimliği jenerik OCR + IMDb/TMDB eşleşmesiyle çözülür.
**Gerekçe:** Filmlerde yüz tanıma için referans bankası yok; yanlış kimlik riski yüksek; jenerik daha güvenilir kaynak.
**Referans:** Master plan §2.2.
**Durum:** Aktif.

### 2026-05-09 / M5 — Speaker / Voice Enrollment v1 dışı

**Karar:** Cross-session voice identification v1 scope'undan tamamen çıkarıldı. Sadece ASR içindeki in-session diarization (SPEAKER_01/02) kalır.
**Gerekçe:** Ses mikrofon / kanal / yaşlanma / dublaj / arşiv kalitesiyle dramatik bozulur. Yanlış voice identity arşiv metadata'sını kalıcı kirletir. Face Recognition zaten kişi tanımayı çözüyor.
**Referans:** Master plan §2.6.
**Durum:** Aktif. v2'de Demucs/vocal separator sonrası yeniden değerlendirme koşullu.

### 2026-05-09 / M6 — Logo ayrı modül değil, Görsel Tagleme altında

**Karar:** Logo / Marka bağımsız modül değildir. Görsel Tagleme §2.3 altında alt başlık olarak kapatılmıştır.
**Gerekçe:** Ayrı detector eğitimi v1 maliyeti yüksek; SigLIP similarity + referans logo kütüphanesi + sabit watermark ROI yeterli.
**Referans:** Master plan §2.5.
**Durum:** Aktif.

### 2026-05-09 / M7 — Tek seçenek mantığı

**Karar:** Master plan birden fazla alternatifle şişirilmez. Her sürüm için ana seçenek seçilir; yedekler ayrı bölümde benchmark koşuluyla yazılır.
**Gerekçe:** Tek kişilik geliştirmede karar paraleli enerji harcamak verimli değil; ana yol netleşmeli.
**Referans:** Master plan §0.2.
**Durum:** Aktif.

### 2026-05-09 / M8 — Showcase ≠ Final analiz

**Karar:** Demo/sunum pipeline'ı gerçek metadata üreten final analizden ayrı tutulur.
**Gerekçe:** Showcase izlenim için, değer final analizde; karışırlarsa demo gösterişli ama metadata güvenilmez olur (VITOS dersi).
**Referans:** Master plan §0.2.
**Durum:** Aktif.

### 2026-05-09 / M9 — Candidate ≠ Identity

**Karar:** Face cluster + KJ name + speaker_id ilişkileri **CandidateRelation** olarak tutulur. Kullanıcı onayı olmadan identity'ye dönüşmez.
**Gerekçe:** Yanlış metadata > eksik metadata. Otomatik identity ataması VITOS'ta felaketle bitmişti.
**Referans:** Master plan §0.3.5.
**Durum:** Aktif.

### 2026-05-09 / M10 — FilmCreditsParser v1.x'e ayrıldı

**Karar:** FilmCreditsParser v1 production hedefi değildir. v1.1 veya ayrı MVP fazı olarak detaylandırılır. KJ/OCR/Müzik hattı ile karıştırılmaz.
**Gerekçe:** Cast explosion, jenerik parser kalitesi, IMDb/TMDB doğrulama ayrı bir disiplin; v1'i bloke etmemeli.
**Referans:** Master plan §0.3.18 ve §2.4.2.
**Durum:** Aktif.

### 2026-05-09 / M11 — OCR ilk production hedefi KJ / Screen Text + Music Segment Linker

**Karar:** OCR & Text Extraction'ın v1 production hedefi KJ / Screen Text + Music Segment Linker. FilmCreditsParser ayrı.
**Gerekçe:** Haber / panel / belgesel / müzik programı KJ okuma TRT arşivinde en yüksek değer üreten OCR cephesi. axle.ai'nin Türkçe KJ'ye optimize olmayışı farklılaşma noktası.
**Referans:** Master plan §2.4.1.
**Durum:** Aktif.

### 2026-05-09 / M12 — ROI-first OCR

**Karar:** KJ / screen text için full-frame OCR ilk adım değildir. Sıra: bottom_band → center_lower → secondary ROI → full_frame_fallback.
**Gerekçe:** Performans + doğruluk; KJ çoğu zaman alt banttadır.
**Referans:** Master plan §0.3.11.
**Durum:** Aktif.

### 2026-05-09 / M13 — Görsel arama v0.1: free text + tag chip seçici, LLM yok

**Karar:** Görsel arama v0.1'de doğal dil parse + eş anlamlı sözlük match + tag chip seçici birlikte. LLM kullanılmaz.
**Gerekçe:** LLM halüsinasyon, deterministik olmayan dil çıktısı, audit zorluğu; basit parser + sözlük v1 için yeterli.
**Referans:** Master plan §2.3 + 2026-05-09 / 14.
**Durum:** Aktif.

### 2026-05-09 / M14 — VLM production metadata motoru değil

**Karar:** Qwen2.5-VL / Gemma 3 Vision gibi VLM'ler production metadata üretmez. Yalnızca yardımcı / review / sözlük geliştirme katmanlarında değerlendirilir.
**Gerekçe:** Halüsinasyon, deterministik olmayan çıktı, arama uyumsuzluğu, audit zorluğu, vocab dışına çıkma riski, performans uçurumu.
**Referans:** Master plan §2.3 v1 dışı bölümü.
**Durum:** Aktif.

### 2026-05-09 / M15 — Background worker + job_runs zorunlu

**Karar:** v1 kullanıcı isteğini bloklamaz. Analiz işleri background worker ile yürür. DB tabanlı single worker veya RQ/Redis yeterli başlangıç. Celery v2 adayı.
**Gerekçe:** Uzun analiz işleri UI'ı bloke etmemeli; recovery için job state tutulmalı.
**Referans:** Master plan §0.3.7.
**Durum:** Aktif. Skeleton kodu `core/jobs/` altında hazır.

---

## 2026-05 — Master plan dışı kararlar

### 2026-05-10 / 1 — Proje takip klasörü oluşturuldu

**Karar:** `_proje_takip/` klasörü E:\MITAS altında oluşturuldu. 8 referans dosya (00-07). Amaç: çoklu LLM oturumları arası süreklilik, "ne yapıyorduk?" stresinin önlenmesi, ana proje takibinin operasyonel beyni.
**Gerekçe:** Token sınırı kapanan oturumlar arasında bilinç sürekliliği gerekiyor. Master plan teknik karar dosyası; bu klasör operasyonel / takip dosyası.
**Referans:** Bu dosya.
**Durum:** Aktif.

### 2026-05-10 / 2 — Acele demo kararı geri çekildi

**Karar:** "3-5 günde GMY sunumu için stream demo yetiştir" kararı geri çekildi. Yeni odak: v0.1 ASR dikey diliminin düzgün ayağa kaldırılması.
**Gerekçe:** Acele kararlar sistem temelini sarsıyor. Yapılan altyapı (sözleşme, schema, job runner, 8 venv) zarar görmeden ilerlenmeli. Sunum geri gelirse Cephe D'de batch demo yedek plan olarak hazırlanır.
**Referans:** `04_YOL_HARITASI.md` §3 Cephe D, `05_AKTIF_GOREV.md`.
**Durum:** Aktif. Önceki "5 günlük shift planı" iptal edildi.

### 2026-05-11 / 15 — Diarization v1 mimarisinin temel parçasıdır

**Karar:** ASR pipeline sadece transkript değil, konuşmacı etiketli transkript
üretir. Diarization motoru (pyannote.audio) pipeline'ın zorunlu bileşenidir.
Konuşmacı etiketleri "SPEAKER_01", "SPEAKER_02" seviyesinde yeterlidir. Güven
eşiği altında kalan segment için speaker_id = null yazılır, label basılmaz.
İsim tanıma (voice identity), cross-session speaker enrollment ve overlap
recovery (üst üste binen konuşmaları kelime kelime kurtarma) kapsam dışıdır.
**Gerekçe:** TRT arşivi röportaj, panel, studio programı, haber gibi
çok-konuşmacılı içerik içerir. Diarization olmadan bu profil işlenemez.
"Eşik geçilmezse null" kuralı yanlış metadata üretimini engeller (Prensip 5.1).
**Referans:** 05_AKTIF_GOREV.md §3, handoff brief 2026-05-11.
**Durum:** Aktif.

### 2026-05-11 / 16 — Diarization fail için graceful degradation

**Karar:** ASR pipeline'ında diarization adımı başarısız olduğunda klip otomatik olarak tamamen failed durumuna düşmez. ASR transcribe başarılı + diarization fail durumunda klip `partial_success` ve `needs_review` olarak işaretlenir. Transcript üretilir ve output JSON'a yazılır. Tüm segmentlerde `speaker_id = null` olur. Output'a `speaker_labels_available = false` ve `diarization_status = failed` alanları eklenir. UI'da bu klipler sarı uyarı taşır. Export edilebilir; uyarı export ile beraber taşınır.

**Strict mode:** Tam `failed` durumu sadece şu hallerde uygulanır: ASR transcribe başarısız, medya okunamadı, output JSON üretilemedi, veya çağırırken `diarize_required=True` strict mode seçilmiş ve diarize başarısız. `diarize_override=True/False` profil default'unu ezmek içindir; `diarize_required=True/False` sadece fail davranışını sertleştirir.

**Batch davranışı:** Bir batch içinde bir veya daha fazla klip `partial_success` ise batch durumu `completed_with_warnings` olur. Batch tamamen `failed` durumuna sadece tüm klipler `failed` ise düşer.

**Gerekçe:** Diarization fail klibin transcript'i için geri dönülmez bir kayıp değildir; transcript zaten ASR'dan üretilmiştir. Sessizce yarı çıktı vermek yerine açıkça "speaker bilgisi yok" sinyali vererek hem veri kaybını önler hem operatöre kontrol kapısı bırakırız. Strict mode (`diarize_required`) bu davranışı disable eden seçenek olarak kalır.

**Referans:** `docs/MITAS_ASR_Pipeline_v0_1_Implementasyon_Plani_v2.md` §7, §10, §11.
**Durum:** Aktif.

### 2026-05-13 / 17 — Faz2, "üst denetim" katmanı olarak ele alınır

**Karar:** Phase 2 sadece özel isim düzeltme modülü değildir. ASR/OCR/metadata çıktılarının üstünde çalışan **MITAS Üst Denetim Katmanı** olarak tasarlanır. Model, özel isim hatası, quoted evidence, tabela/fiş/kart, OCR/ASR çelişkisi, tarihsel anakronizm ve bağlam kırığı yakalayan bir denetçi olur.

**Gerekçe:** 100.000 video ölçeğinde her bulguyu insana onaylatmak gerçekçi değildir; ama yanlış metadata eksik metadata'dan zararlıdır. Üst modelin doğru rolü "hakim" olmak değil, bağlamı tartan, kanıt isteyen ve riskli yeri kırmızı bayraklayan editör katmanı olmaktır.

**Referans:** `mutfak/09_UST_DENETIM_KATMANI.md`.
**Durum:** Aktif.

### 2026-05-13 / 18 — Üst model izinli aksiyon üretir, MITAS kanıtı toplar

**Karar:** Üst model serbestçe dosya açmaz veya sistemi değiştirmez. Yalnızca izinli aksiyonlar üretir: `canonical_link_only`, `replace_suggestion`, `review_only`, `fetch_frame`, `fetch_frame_crop`, `re_ocr_crop`, `re_asr_window`, `reference_check`, `red_flag`, `human_review`. MITAS orchestration katmanı bu aksiyonlara göre timestamp/frame/crop/OCR/ASR/reference kanıt paketini toplar ve gerekirse modele ikinci tur verir.

**Gerekçe:** "Bu isim bu filmde ne alaka?" gibi şüpheler ancak kanıt döngüsüyle güvenli çözülür. Modelin kendi bilgisine güvenerek kesin hüküm vermesi yanlış olabilir; kanıt istemesi ve kanıtla karar vermesi gerekir.

**Referans:** `mutfak/09_UST_DENETIM_KATMANI.md` §2-§4.
**Durum:** Aktif.

### 2026-05-13 / 19 — Otomatik replace dar kapıdan geçer

**Karar:** `replace_allowed=true` ancak şu koşullar birlikte sağlanırsa geçerli kabul edilir: `action == replace_suggestion`, `mention_context == normal_speech`, `canonical` dolu, confidence yeterli, deterministik kapı veto etmiyor. `quoted_evidence`, `sign_or_label`, `error_example`, OCR/text-on-screen, tabela, kart, fiş, altyazı ve görünür kanıt bağlamlarında transcript span'i otomatik ezilmez.

**Gerekçe:** Testlerde birçok model canonical adı doğru bulsa da kanıt/alıntı span'lerini yanlışlıkla replace etmeye kalktı. Arşiv sisteminde görünür kanıtı "düzeltmek" tarihsel kanıt değerini bozabilir.

**Referans:** `mutfak/09_UST_DENETIM_KATMANI.md` §5.
**Durum:** Aktif.

### 2026-05-13 / 20 — Üst-denetim model aday havuzu

**Karar:** Güncel aday havuzu şöyledir: default text üst-denetim için `google/gemma-4-26b-a4b`; kalite lideri/ikinci görüş için `qwen/qwen3.6-27b`; alternatif Qwen production adayı için `qwen/qwen3-30b-a3b-2507`; audit/hakem için `meta/llama-3.3-70b`; frame/OCR/crop/VLM kanıt okuyucu için `nvidia/nemotron-3-nano-omni` ve ayrıca görsel OCR testinde `qwen/qwen2.5-vl-7b`.

**Gerekçe:** Yerel LM Studio testlerinde Gemma 26B A4B hız/kalite dengesiyle öne çıktı; Qwen 27B policy ve bağlam ayrımında en dengeli model oldu; Qwen3-30B-A3B güçlü alternatif çıktı. Llama 70B pahalı ama audit için kullanılabilir. Nemotron Omni text-only ana model değil, multimodal kanıt okuma tarafında değerlidir.

**Referans:** `mutfak/09_UST_DENETIM_KATMANI.md` §6.
**Durum:** Aktif, benchmark seti tamamlanınca revize edilebilir.

### 2026-05-13 / 21 — ASR model politikası için fast-first selective quality adayı

**Karar:** ASR production politikası için şu an ana aday "fast-first selective quality" yaklaşımıdır. Tüm arşivi doğrudan `quality / large-v3` ile çözmek veya her klibi full fast + full quality decode edip full hybrid yapmak production default'u olarak kabul edilmez. Önce `fast / large-v3-turbo` full decode yapılır; riskli pencere/segmentler confidence ve kalite sinyalleriyle belirlenir; sadece seçili pencereler `quality / large-v3` ile yeniden çözülür; sonuç segment arbitration ve audit log ile birleştirilir.

**Gerekçe:** 2026-05-13'te UNC test WAV havuzundaki 14 dosya (`~682 dk`) fast ve quality profilleriyle koşuldu. Fast tarafında yüksek `no_speech_prob` neredeyse hiç görülmezken quality tarafında çok sayıda riskli segment görüldü. Fast ve quality farklı hata profilleri gösterdi; bazı yerlerde quality compound/bağlam kazanımı sağlıyor, bazı yerlerde high-no-speech segmentlerde hallüsinasyon üretiyor. Full hybrid doğruluk araştırması için yararlı ama production maliyetini yaklaşık ikiye katlıyor. Confidence tek başına doğruluk kanıtı değildir; karar gold set WER/CER ile kalibre edilecektir.

**Referans:** `outputs/asr_archive_all_wav_benchmark/batch_report.md`, `outputs/asr_archive_all_wav_benchmark/model_diff_reports/all_films_fast_quality_confidence.md`, `outputs/asr_archive_all_wav_benchmark/hybrid_simulation_reports/aggregate_hybrid_simulation.md`, `benchmark_templates/asr_gold_probe_benchmark.yaml`.
**Durum:** Revize edildi (2026-05-14). Karar 23 ile `large-v3-turbo default + large-v3 selective fallback` politikası uygulama yönü olarak seçildi; TRT transcriptleri gelince eşikler yeniden kalibre edilecek.

### 2026-05-14 / 22 — Dış Türkçe transcript kaynakları geçici ASR probu olarak indirildi

**Karar:** TRT transcript havuzu gelene kadar iki dış Türkçe transcript kaynağı geçici prob seti olarak tutulur: MediaSpeech Turkish / OpenSLR108 ana geçici ASR probu; Mozilla Common Voice Turkish 25.0 yardımcı kısa-utterance Türkçe kontrol korpusu. ISSAI Turkish Speech Corpus şimdilik indirilmez.

**Gerekçe:** MediaSpeech medya/news konuşmasına yakın, WAV/TXT çiftleri temiz ve yaklaşık 10 saatlik insan transcriptli veri sağlıyor. Common Voice büyük ve temiz ama domain olarak okuma cümlesi olduğu için TRT model kararında ana kaynak değildir. Yarın/sonraki erişilecek TRT transcriptleri gerçek gold karar kaynağı olacak.

**Referans:** `E:\MITAS\cache\external_datasets\mediaspeech_tr\`, `E:\MITAS\cache\external_datasets\common_voice_tr_25\`, `outputs/external_turkish_transcripts_review.md`, `outputs/external_turkish_transcripts_asr_smoke_20\benchmark_results.md`.

**Durum:** Aktif. Ham datasetler `cache/` altında git dışı kalır; inceleme raporları `outputs/` altında tutulur.

### 2026-05-14 / 23 — ASR default modeli large-v3-turbo, large-v3 selective fallback / üst-denetim modeli

**Karar:** ASR production yolunda default decode modeli `fast / large-v3-turbo` olur. `quality / large-v3` tüm arşiv için default ana motor değildir; tail-gap, safety failure, kritik segment veya ileride TRT ile kalibre edilecek kalite sinyallerinde selective fallback / üst denetim modeli olarak çalışır.

**Gerekçe:** 20 MediaSpeech segmentlik benchmark'ta `large-v3` WER/CER olarak çok az önde çıktı (`quality` WER 0.1775, CER 0.0961; `fast` WER 0.1853, CER 0.0966) ama decode süresi belirgin yüksek oldu (`quality` 48.773 sn, `fast` 14.098 sn). Örnek bazında 8 quality galibiyeti, 6 fast galibiyeti, 6 eşitlik görüldü. Bu tablo, kalite farkının küçük ve hız farkının büyük olduğunu gösterdi.

**Referans:** `outputs/external_turkish_transcripts_asr_smoke_20\benchmark_results.md`, `scripts/asr_mediaspeech_benchmark.py`, `outputs/external_turkish_transcripts_review.md`.

**Durum:** Aktif uygulama kararı. TRT transcriptleri geldiğinde aynı benchmark şekli TRT-domain WAV/TXT çiftlerinde koşulacak; eşikler ve gerekirse model politikası revize edilecek.

### 2026-05-14 / 24 — Adaptive fallback: tail-gap tetikleyici ve fallback result selector eklendi

**Karar:** `fast_with_fallback` artık sadece repetition/long-token/word-density arızalarında değil, VAD'in beklediği konuşma sonuna göre transcript erken bittiğinde de fallback tetikler. `large-v3` fallback sonucu kör kabul edilmez; quality unsafe ise veya coverage olarak turbo'dan belirgin kötüyse turbo korunur. Son seçim `selection_reason` alanıyla loglanır.

**Gerekçe:** Gerçek MediaSpeech örneği `430d0aaf-8f12-4a09-964d-aa75f4157100` içinde turbo 14.8 sn sesin yalnızca 7.42 sn kısmını kapsadı ve eski kod fallback tetiklemedi. Bu kritik eksik transcript riskiydi. Ayrıca fallback tetiklendiğinde quality sonucunu kör kabul etmek, quality'nin daha kısa/kopuk olduğu durumlarda daha kötü çıktı seçme riskini taşıyordu.

**Referans:** `core/pipelines/asr/transcribe.py`, `core/pipelines/asr/quality.py`, `core/pipelines/asr/result.py`, `tests/test_production_transcribe.py`, `tests/test_asr_quality.py`.

**Doğrulama:** `tests/test_production_transcribe.py + tests/test_asr_quality.py` → 31 passed; `tests/test_asr_pipeline.py + tests/test_asr_channel_merge.py` → 14 passed. Gerçek MediaSpeech `430d0aaf...` klibinde `fallback_triggered=True`, `fallback_reason=tail_gap_uncovered:gap=6.88s`, `profile_used=quality`.

**Durum:** Aktif. TRT transcriptleri geldiğinde `max_uncovered_tail_seconds=3.0` ve `max_uncovered_tail_ratio=0.25` eşikleri kalibre edilecek.

### 2026-05-14 / 25 — ASR v0.1 kapatma paketi: TimelineEvent emit, kalite raporu standardizasyonu, smoke test, demo output

**Karar:** ASR v0.1 dikey dilimi dört eksik maddeyle kapatıldı:

1. **TimelineEvent emit** — `core/pipelines/asr/pipeline.py` her clean_segment'i `EventType.asr_segment` olan bir `TimelineEvent` olarak üretir. `confidence = exp(avg_logprob)` ile normalize, `[0, 1]`'e clamp; `subtype = segment.language`; `source_module = "asr"`; `evidence_ids = [module_run_id]`; payload `{text, avg_logprob, no_speech_prob, flags, speaker_id?, channel?}`. Çıktı `outputs/.../timeline_events.json`.
2. **Kalite raporu standardizasyonu** — `summary.json` zorunlu alanlar: `model_name`, `fallback_triggered`, `fallback_reason`, `selection_reason`, `clean_segments`, `quality_drops`, `timeline_event_count`, `vad.speech_ratio` (+ speech_seconds, segment_count), `safety.diagnostics` (uncovered_tail dahil). VAD bilgisi `ProductionTranscribeResult.vad_speech_seconds/ratio/segment_count` alanları üzerinden taşınır; split-kanalda max/sum ile birleşir.
3. **Smoke test** — `tests/test_asr_v0_1_smoke.py` golden-file testi, demo çıktısını şema ve invariant açısından doğrular. 9 madde geçer. `core` venv'de pytest ile koşar; ASR runtime bağımlılığı yok.
4. **Demo output** — `outputs/asr_v0_1_demo/` altında 5 artifact (`archive.json`, `summary.json`, `module_run.json`, `transcript_review.md`, `timeline_events.json`). Üretim: `scripts/asr_v0_1_demo.py` (asr venv ile koşulur). Smoke klip: **001_h1** (TRT haber kameramanları, 101.739 sn; kaynak `\\depo01cifs.int.trt.net.tr\sas_h264\testset\wav\H1.wav`).

**Gerekçe:** Mutfak 05.4.2 alt görevleri E, F, G, H açıktı. Bu paket onları kapatır ve sözleşme katmanını (ModuleRun + TimelineEvent) gerçek ASR çıktısına bağlar. Smoke + demo ayrımı şu sebeple: gerçek model koşumu pahalı (~30 sn GPU), CI'da koşturulmamalı; bu yüzden demo bir kez koşulup `outputs/asr_v0_1_demo/` altına sabitlendi, smoke test o golden output'u doğrular.

**TRT klibinin seçim gerekçesi:** 001_h1 — 1m 42s, net Türkçe haber kesiti, TRT içeriği, benchmark'ta zaten kalite testi geçmiş. Master plan v0.1 hedefiyle (1-2 dk net TRT haber kesiti) birebir uyumlu.

**Doğrulama:** Demo koşumu sonucu: `profile_used=fast` (turbo passed fallback checks), `clean_segments=15`, `clean_words=166`, `timeline_event_count=15`, `vad.speech_ratio=0.849232`, `safety.safe=True`, total runtime ~38.5 sn. Test toplam sayısı: 45 mevcut ASR test + 9 v0.1 smoke = **54 yeşil**.

**Referans:** `core/pipelines/asr/{pipeline.py, transcribe.py, result.py, channel_merge.py}`, `scripts/asr_v0_1_demo.py`, `tests/test_asr_v0_1_smoke.py`, `outputs/asr_v0_1_demo/`.

**Durum:** Aktif. v0.1 dikey dilim sprint'i kilitlendi: [docs/SPRINT_4_ASR_V0_1_DONE.md](../docs/SPRINT_4_ASR_V0_1_DONE.md) yazıldı; master plan §2.1 kalite raporu kontratı `summary.quality_report` bloğuyla karşılandı (2/5 doğrudan, 3/5 `not_applicable` plak: WhisperX ve pyannote v0.2'ye devredildi). v0.2'ye devreden 5 açık (WhisperX, diarization profil bazlı çağrı, profile dispatch, persistent worker, TRT eşik kalibrasyonu) sprint kapanış raporunda §4'te listelendi.

### 2026-05-14 / 26 — Mutfak canlı kaynak ve ortak takip sistemi

**Karar:** `mutfak/` klasörü MITAS için canlı kaynak ve ortak takip sistemi kabul edilir. Kullanıcı "mutfak kaynak", "nerede kaldık" veya "kaldığımız yerden devam" dediğinde tüm yardımcılar aynı kaynak düzeninden devam eder. Her iş, gerçek test, karar ve ertelenen konu ilgili mutfak dosyasına işlenmeden tamamlandı sayılmaz.

**Gerekçe:** Claude / Opus / ChatGPT / Codex gibi birden fazla yardımcı paralel çalışırken worktree ve snapshot karışıklığı oluştu; bir yardımcı izole `.claude/worktrees/...` altında değişiklik yapıp ana `E:\MITAS` için uygulanmış gibi raporlayabildi. Kalıcı bir canlı takip sistemi olmadan "ne oldu, nerede kaldık, ne sonraya bırakıldı" bilgisi oturumlar arasında dağılıyor.

**Referans:** `mutfak/00_BURADAN_BASLA.md` §0, `mutfak/05_AKTIF_GOREV.md` §0, `mutfak/11_WORKTREE_KOORDINASYON.md`, `mutfak/12_CANLI_MUTFAK_PROTOKOLU.md`.

**Ek uygulama kuralı:** Kullanıcı "nerede kaldık?" veya "şunu yaptık mı?" diye sorduğunda ilk kaynak `mutfak/05_AKTIF_GOREV.md` canlı panodur. "Şunu yaptık mı?" sorusunda önce yapılanlar/kapananlar, sonra sonraya bırakılanlar/açık park listesi kontrol edilir; gerekiyorsa `06_KARARLAR_GUNLUGU.md` ve `07_REFERANS_HARITASI.md` ile doğrulanır. Her izlenebilir madde `PARK-*`, `TASK-*`, `DONE-*`, `TEST-*`, `DEC-*` ID öneklerinden birini alır ve sabit durum sözlüğü kullanır: `Açık`, `Ertelendi`, `Karar bekliyor`, `Devam ediyor`, `Yapıldı`, `Test edildi`, `Kapatıldı`, `İptal edildi`.

**Tamamlandı kriteri:** Bir iş, workspace/cwd kaydı, test/koşulmadı kaydı, `05_AKTIF_GOREV.md` canlı pano güncellemesi ve varsa karar günlüğü kaydı olmadan tamamlandı sayılmaz.

**Durum:** Aktif. Bundan sonra üst çalışma kuralı `00_BURADAN_BASLA.md` §0 içindedir. `05_AKTIF_GOREV.md` canlı pano; `06_KARARLAR_GUNLUGU.md` karar defteri; `11_WORKTREE_KOORDINASYON.md` canonical workspace/worktree protokolü; `12_CANLI_MUTFAK_PROTOKOLU.md` ise ayrıntı uygulama kılavuzudur.

### 2026-05-14 / 27 — ASR production default `condition_on_previous_text=False`

**Karar:** `core/pipelines/asr/models.py` içindeki `DEFAULT_TRANSCRIBE_PARAMS.condition_on_previous_text` default değeri `True` iken `False` yapıldı. Bu değer pipeline genelinde production transcribe çağrılarının ön-bağlam davranışını belirler; opt-in olarak bir profil veya çağıran kod ileride `True`'ya çekebilir.

**Gerekçe:** Önceki durum tek başına aykırıydı: operasyonel her şey (legacy `transcribe_vad_segments`, `scripts/real_media_smoke.py`, `scripts/tek_klip_child.py`, `scripts/asr_emergency_transcribe.py`, `scripts/asr_pyannote_pipeline.py`, `scripts/tur3_children/common.py`, `scripts/asr_exit_test_children/common.py`, `scripts/asr_child_exit_diagnosis.py`) `False` kullanırken yalnız production default `True` idi. Karar Günlüğü'nde dayanak yoktu; `test_production_transcribe.py:80` da kasıtlı olmadan bu davranışı kilitlemişti.

`condition_on_previous_text=True` faster-whisper'da bilinen repetition_collapse / outro hallucination (örn. "abone olmayı unutmayın") riskini bir segmentten sonrakine yayıyor. `quality.py` kalkanları (`repetition_collapse`, `long_token_artifact`, `very_low_logprob_short_text`, `multi_signal_low_quality`, tail_gap_uncovered) bu artifact'ları yakalayıp fallback'i tetikliyor; yani sistem "True ile problem üret, kalkanla yakala, large-v3 fallback'i tetikle" döngüsünde. `False` bu döngüyü kırar, fallback yükünü azaltır ve Karar 14'ün "segment bazında karar" felsefesiyle (multilingual=True) uyumlu hale getirir.

**Ek uygulama notları:**

- `tests/test_production_transcribe.py:80` `is True` → `is False` olarak güncellendi.
- Modülde Karar referansı yorumu (`models.py` `TranscribeParams.condition_on_previous_text`) eklendi.
- Bu karar Audit MED-5 (2026-05-14 ASR derinlemesine inceleme) ve ChatGPT ek değerlendirmesi ile aynı yönde.

**Geri alma kapısı (TRT kalibrasyonu):** Audit'in 5. devreden işi ("TRT verisi eşik kalibrasyonu") sırasında `True` vs `False` A/B karşılaştırması yapılır:
- WER karşılaştırması (TRT WAV + referans TXT)
- Fallback tetik oranı (False'un sözünü tuttuğu varsayım)
- Repetition_collapse / long_token_artifact drop oranı
- Tail-gap tetik oranı

`True` objektif bir avantaj gösterirse (örn. WER farkı > %X ve patolojik drop oranı kabul edilir seviyede) yeni bir Karar ile `True`'ya geri alınır veya profile bazlı ayrımı (`bulten_haber`/`belgesel` True, `studio_panel`/`muzik_programi`/`film` False gibi) Karar 15 zincirine eklenir.

**Referans:** `core/pipelines/asr/models.py` TranscribeParams, `tests/test_production_transcribe.py` (`test_quality_profile_basic`), audit raporu MED-5 (`docs/MITAS_P1_Blocker_ve_Mimari_Duzeltmeler_v1.md` ya da ilgili audit dosyası), Karar 14 (multilingual True felsefesi).

**Durum:** Aktif. TRT kalibrasyonu A/B sonucu beklemekte; sonuç bu kararın geçerliliğini teyit edecek.

### 2026-05-14 / 28 — Live STT Preview player sesiyle WebSocket üzerinden çalışır

**Karar:** UI'daki `Preview / Anlık çeviri` akışı `ASR > streaming_transcription` altında ele alınır. Kaynak mikrofon değil, tarayıcıdaki player'da çalan medya sesidir. Upload veya Preview checkbox tek başına ASR/STT modeli çalıştırmaz; canlı akış kullanıcı `Play` bastığında başlar. İlk sürüm yalnız canlı transcript üretir. Dil algılama ve Türkçe dışı konuşma için yanda Türkçe çeviri ikinci fazdır.

**Gerekçe:** Kullanıcının beklentisi "ben play bastığımda duyduğunu anlık çevirsin" şeklinde; batch `STT Başlat` akışıyla karıştırılmamalı. Player sesi kaynak seçilirse pause/seek/timeline ile aynı davranış izlenir. Ayrı WebSocket ve ayrı live executor, batch ASR kuyruğunu ve GPU yükünü daha kontrollü tutar.

**Uygulama notu:** FastAPI endpoint'i `/api/stt/preview/ws`; mesajlar `start`, `chunk`, `pause`, `resume`, `seek`, `stop`; chunk formatı 16 kHz mono PCM16. İlk implementasyon `large-v3-turbo` fast model ile küçük WAV parçalarını çözer; full dosya preprocessing, VAD ve fallback bu canlı hatta çalışmaz. Preview rolling-buffer modunda yaklaşık 7 sn player sesini bağlam olarak taşır, decode isteğini yaklaşık 1.25 sn aralıkla yollar ve server `publish_after` / `publish_until` penceresiyle yalnız stabil, yaklaşık 2 sn geriden gelen kısmı yayınlar. Live stream aktifken batch `STT Başlat` devre dışıdır.

**Referans:** `mutfak/10_UI_NOTLARI.md` §3.10, `core/api/asr_server.py`, `tests/test_asr_live_preview_api.py`, WebUI `src/app/live-stt-preview.ts`.

**Durum:** Aktif. Çeviri kolonu ve dil algılama sonraki fazda eklenecek.

### 2026-05-15 / 29 — MT benchmark için NLLB 1.3B ve 3.3B birlikte test edilir

**Karar:** Faz A MT benchmark'ında NLLB tarafında hem `facebook/nllb-200-distilled-1.3B` hem `facebook/nllb-200-3.3B` kurulup test edilir. "NLLB-200-distilled-3.3B" model adı kullanılmaz; Facebook böyle bir distilled 3.3B varyantı yayınlamamıştır. Şimdilik NLLB default / öncelikli aday `facebook/nllb-200-3.3B` olur. OPUS-MT-TC-BIG-EN-TR ayrıca EN→TR uzman aday olarak benchmark'a girer.

**Gerekçe:** Kullanıcı çeviride hızdan çok kaliteyi önceliklendirdi; bu nedenle 3.3B varsayılan aday olmalıdır. 1.3B distilled ise disk, VRAM ve hız avantajı nedeniyle aynı benchmark'ta tutulur; nihai seçim COMET/CHRF ve örnek çıktı incelemesiyle yapılır.

**Referans:** `CODEX_GOREV_BRIEF_v0_2_KANAL_CEVIRI.md` rev2 KN-1, kullanıcı kararı 2026-05-15.

**Durum:** Aktif. Nihai MT galibi Faz A benchmark raporundan sonra ayrıca karara bağlanacak.

### 2026-05-15 / 30 — EN→TR çeviri rotası OPUS, çok-dil fallback NLLB 3.3B

**Karar:** Faz A EN→TR benchmark sonucu Phase 0 çeviri rotası şöyle seçilir: İngilizce kaynak segmentlerde ana model `opus-mt-tc-big-en-tr-ct2-int8`, genel çok-dil fallback/default model `nllb-200-3.3B-ct2-int8` olur. `nllb-200-distilled-1.3B-ct2-int8` hız/boyut karşılaştırma adayı olarak kurulu tutulur ama Phase 0 route'a alınmaz.

**Gerekçe:** FLORES EN→TR 100 cümle benchmark'ında NLLB 3.3B COMET-22 skorunda OPUS'tan yalnızca `+1.4305` puan önde çıktı (`90.6477` vs `89.2172`); bu fark karar kuralındaki `>2.0` eşiğini geçmedi. OPUS CHRF++'ta önde (`59.0026` vs `57.1212`) ve gecikmede belirgin hızlıdır (`P50 243.0 ms` vs `1137.5 ms`). Bu nedenle EN→TR için OPUS; İngilizce dışı diller için NLLB 3.3B daha doğru dengedir.

**Referans:** `docs/MITAS_MT_Benchmark_v0_2_Rapor.md`, `outputs/translate_eval/scores.json`, kullanıcı KN-3 onayı 2026-05-15.

**Durum:** Aktif. Manifest'te `selected_as_engine` alanı mevcut politika/testler nedeniyle false kalır; gerçek route assignment Faz C'de `config/translation_router.yaml` ile yazılacak.

### 2026-05-10 / 3 — STT, ASR streaming_transcription alt moduna taşındı

**Karar:** STT ayrı ana venv/profil/modül değildir. Canlı transcript `ASR > streaming_transcription` alt modudur. Primary runtime `E:\MITAS\venvs\asr`; `E:\MITAS\venvs\stt` legacy olarak korunur.
**Gerekçe:** STT speech-to-text işidir; ASR'nin streaming kullanım biçimidir. Dosya/kayıt transkripti `file_transcription`, canlı/anlık transkript `streaming_transcription` olarak ayrılır.
**Referans:** `outputs/asr_stt_merge_report.json`, `requirements/asr.txt`, `requirements/stt.txt`.
**Durum:** Aktif.

### 2026-05-11 / 3 — asr venv ana ASR/STT runtime

**Karar:** ASR pipeline'ının ana runtime'ı `E:\MITAS\venvs\asr` olur. `E:\MITAS\venvs\stt` legacy olarak korunur ama primary runtime değildir.
**Gerekçe:** ASR/STT ayrımı modül değil kullanım biçimi ayrımıdır. Ana ASR runtime'ı faster-whisper, Silero VAD, pyannote ve servis paketlerini zaten birlikte taşır; `stt` venv'i geçmiş uyumluluk için saklanır.
**Referans:** `mutfak/05_AKTIF_GOREV.md` §3.1, `outputs/asr_stt_merge_report.json`, `CODEX_GOREV_BRIEF_v0_1_HAZIRLIK.md` §4.1.
**Durum:** Aktif.

### 2026-05-11 / 4 — WhisperX alignment venv'de kalır

**Karar:** WhisperX `asr` venv'e eklenmez. `E:\MITAS\venvs\alignment` venv'inde kalır. ASR pipeline, alignment aşaması için bu venv ile subprocess üzerinden konuşur.
**Gerekçe:** WhisperX bağımlılıkları ana ASR runtime'ını gereksiz riskle genişletebilir. Word-level alignment ayrı bir runtime sınırında tutulursa `asr` venv'in korunan paketleri bozulmadan kalır.
**Referans:** `mutfak/05_AKTIF_GOREV.md` §3.2, `CODEX_GOREV_BRIEF_v0_1_HAZIRLIK.md` §4.1 ve §4.5.
**Durum:** Aktif.

### 2026-05-11 / 5 — M16 Subprocess sleeve pattern

**Karar:** Dependency çatışması olan modüller ayrı venv'lerde yaşar; ana ASR runtime onlara dosya/JSON tabanlı subprocess çağrısıyla konuşur. Bu, MITAS için kalıcı mimari desendir.
**Gerekçe:** DeepFilterNet, WhisperX ve ileride benzer bağımlılık setleri tek venv içinde paket çakışması üretebilir. Subprocess sleeve yaklaşımı modül izolasyonunu korur, audit edilebilir dosya tabanlı kontrat sağlar ve ana runtime'ı kırılganlaştırmaz.
**Teknik not (2026-05-11):** Windows hostta her sleeve wrapper, kendi gerektirdiği FFmpeg DLL dizinini import-time `os.add_dll_directory()` ile eklemekle yükümlüdür. Python 3.8+ DLL arama davranışı nedeniyle PATH tek başına yeterli kabul edilmez.
**Referans:** `mutfak/01_PROJE_VIZYON.md` §5.7, `CODEX_GOREV_BRIEF_v0_1_HAZIRLIK.md` §4.1.
**Durum:** Aktif.

### 2026-05-11 / 6 — FFmpeg full-shared geçişi

**Karar:** Gyan static FFmpeg yerine full-shared build kurulur. Torchcodec native decode bu geçişle anlamlı çalışır hale getirilir.
**Gerekçe:** Torchcodec native decode için FFmpeg shared DLL'lerinin PATH üzerinden erişilebilir olması gerekir. Static build genel `ffmpeg` kullanımında yeterli olsa da torchcodec entegrasyonu için doğru temel değildir.
**Referans:** `CODEX_GOREV_BRIEF_v0_1_HAZIRLIK.md` §4.2 ve §4.3.
**Durum:** Aktif.

### 2026-05-11 / 7 — DeepFilterNet için ayrı denoise venv

**Karar:** DeepFilterNet `asr` venv'den ayrılır. Yeni `E:\MITAS\venvs\denoise` venv'inde `numpy<2` ile yaşar. ASR pipeline denoise çağrısını subprocess sleeve üzerinden yapar.
**Gerekçe:** DeepFilterNet'in `numpy<2` ihtiyacı `asr` venv'in korunan `numpy==2.2.6` durumuyla çelişir. Ana ASR paketlerini downgrade/upgrade etmeden çözüm, denoise işini izole venv'e taşımaktır.
**Referans:** `mutfak/01_PROJE_VIZYON.md` §5.7, `CODEX_GOREV_BRIEF_v0_1_HAZIRLIK.md` §3.1 ve §4.4.
**Durum:** Aktif.

### 2026-05-11 / 8 — large-v3 cache stratejisinin uygulanması

**Karar:** `MITAS_ASR_Model_Cache_NoInternet_Strategy_v1.md` dokümanındaki strateji uygulanır. Model `models/asr/faster-whisper/` altına çekilir; sonraki çağrılarda internet trafiği oluşmaz.
**Gerekçe:** Kurum içi çalışma ve tekrarlanabilir smoke test disiplini için model cache lokal ve denetlenebilir olmalıdır. ASR smoke ve sprint koşumları HuggingFace indirme durumuna bağlı kalmamalıdır.
**Referans:** `docs/MITAS_ASR_Model_Cache_NoInternet_Strategy_v1.md`, `CODEX_GOREV_BRIEF_v0_1_HAZIRLIK.md` §4.6.
**Durum:** Aktif.

### 2026-05-11 / 9 — Alignment venv'de torchcodec dormant kabulü

**Karar:** `alignment` venv'de `torchcodec==0.7.0` transitive dependency olarak bulunur, ancak WhisperX word-level alignment yolunda WAV manuel waveform olarak verildiğinde fiilen çağrılmaz. Bu nedenle FFmpeg 8.1.1 ile direct torchcodec decode smoke'unun kırmızı olması, alignment işlevi için bloke kabul edilmez.
**Gerekçe:** Teşhis koşumunda `E:\MITAS\testklipler\erd_test_sound.wav` üzerinde ASR segment girdisi hazırlandı; WhisperX `align(...)` fonksiyonu manuel 16 kHz mono waveform ile tamamlandı ve import kancası `torchcodec` import/çağrı denemesi yakalamadı. `torchcodec` paketini `whisperx` ve `pyannote-audio` çekiyor, fakat bu alignment çağrı yolunda dormant kalıyor.
**Referans:** `outputs/torchcodec_alignment_diagnosis.json`, `outputs/alignment_diagnosis_asr_segments.json`.
**Durum:** Aktif.

### 2026-05-11 / 10 — Lokal Git devreye alındı

**Karar:** `E:\MITAS` altında lokal Git deposu başlatılır. Remote/GitHub/push kapsam dışıdır; amaç yalnızca yerel versiyon kontrolü, checkpoint ve geri dönüş güvenliğidir.
**Gerekçe:** Hazırlık çalışmasında commit adımları `.git` olmadığı için uygulanamamıştı. Bu GitHub ile karıştırılmamalıdır; lokal Git internet gerektirmez ve proje disiplininin parçasıdır.
**Referans:** `.gitignore`, bu dosya.
**Durum:** Aktif.

### 2026-05-11 / 11 — `testklipler` ham test havuzu kayda alındı

**Karar:** `E:\MITAS\testklipler\` klasörü ham test video/ses havuzu olarak tutulur. Dosyalar büyük olduğu için Git'e alınmaz; envanter ve kullanım notları `mutfak/08_TEST_KLIPLER.md` dosyasında izlenir.
**Gerekçe:** ASR, OCR/KJ, denoise, visual tag, film/jenerik ve spor yayınları için farklı karakterde klipler mevcut. Hangi klibin hangi amaçla kullanılacağı yazılı olmazsa sprint sırasında seçim karışır.
**Referans:** `mutfak/08_TEST_KLIPLER.md`, `mutfak/07_REFERANS_HARITASI.md`.
**Durum:** Aktif.

### 2026-05-11 / 12 — ASR child process abnormal exit izleniyor

**Karar:** Windows hostta ASR child process, geçerli JSON çıktısı ürettikten sonra `0xC0000409` ile kapanırsa bu tek başına transcript çıktısını geçersiz kılmaz; ancak durum `needs_review` olarak izlenir ve production motor kararı yerine containment notu olarak tutulur.
**Gerekçe:** Teşhis koşumunda tek klipli CPU/CUDA/load-only/compute_type varyasyonları temiz kapanırken, aynı CUDA `large-v3` model instance'ında üç klip ardışık transcribe edilince JSON geçerli yazıldıktan sonra `3221226505 / 0xC0000409` yeniden üretildi. Açık cleanup (`del model`, `gc.collect()`, kısa sleep) multi-clip vakasında exit kodunu temizlemedi.
**Referans:** `outputs/asr_child_exit_diagnosis_report.json`, `scripts/asr_child_exit_diagnosis.py`.
**Durum:** Superseded by Karar 14 (2026-05-11). Native CUDA teardown bug'ı hipotezi yanlış çıkmıştır; gerçek sebep multilingual=False default'u idi.
**Ek teknik not:** Genişletilmiş test paketinde T1/T2 aynı klip tekrarları temiz kaldı; T3 farklı üç klip aynı instance'ta `0xC0000409` üretti; T4 her klip için yeni model instance kullansa da aynı process içinde yine `0xC0000409` üretti; T5 dirty exit çıktısının temiz referansla segment bazında eşleştiğini gösterdi; T6a/T6b/T6c aynı klip cleanup varyasyonları temiz kaldı; T7 faulthandler koşumu dirty exit'i yeniden üretti. Bu bulgu process-per-clip containment'ı daha güçlü aday yapar, ancak bu satır production motor kararı değildir.
**Ek referans:** `outputs/asr_child_exit_test_paketi_report.json`, `outputs/asr_child_exit_test_paketi_summary.md`, `scripts/asr_child_exit_test_paketi.py`.

### 2026-05-11 / 13 — wav_erd_test_sound deterministik dirty-exit patolojik klip

**Karar:** `wav_erd_test_sound` benzeri patolojik ASR klipleri için tolerant containment ve `low_quality` flag yeterli ilk güvenlik ağı kabul edilir; `news_trt_haber_1` ve `promo_1` kontrol klipleri aynı koşulda temiz referans sayılır. `wav_erd_test_sound` exit davranışı deterministik kirli kabul edilir, transcript içeriği ise stokastik varyans gösterebilir.
**Gerekçe:** Tek klip / tek process / tek transcribe tekrar testinde `wav_erd_test_sound` 10/10 kez `0xC0000409` ile kapandı. Aynı koşuda `news_trt_haber_1` ve `promo_1` 10/10 temiz kapandı. `wav_erd_test_sound` transcriptleri 10 tekrarın tamamında farklıydı ve süre aralığı 15.965-26.835 sn oldu; kontrollerde transcriptler identikti ve süreler kısa kaldı.
**Referans:** `outputs/asr_tek_klip_tekrar_report.json`, `outputs/asr_tek_klip_tekrar_summary.md`, `scripts/asr_tek_klip_tekrar.py`, `scripts/tek_klip_child.py`.
**Durum:** Superseded by Karar 14 (2026-05-11). wav_erd_test_sound patolojik klip değildir; multilingual içerik (Peres İngilizce + Erdoğan İngilizce araya girişi + alkış) Türkçe-kilitli ASR çağrısı ile çöp çıktı ve crash üretiyordu. multilingual=True ile aynı klip 3/3 temiz exit, anlamlı transcript verdi.

### 2026-05-11 / 14 — ASR transcribe çağrılarında multilingual=True default

**Karar:** MITAS ASR pipeline'ında `WhisperModel.transcribe()` çağrıları default olarak `multilingual=True` parametresi ile yapılır. Bu davranış pipeline genelinde geçerlidir; opt-out gerekmez. Tek-dilli klipler için marjinal yavaşlama (%12-15) kabul edilen üretim maliyetidir.

**Gerekçe:** TRT haber kanalı arşivi multilingual içeriği (uluslararası ziyaretler, BM/AB/NATO toplantıları, yabancı misafir röportajları, basın toplantıları) önemli oranda içerir. Default `multilingual=False` ile bu içeriklerde model dil kilidinde sıkışıyor, hem çöp transcript üretiyor hem 10x yavaşlıyor hem Windows native exit `0xC0000409` ile crash ediyordu. `multilingual=True` ile aynı tetikleyici klip 10x hızlandı, transcript anlamlı oldu, crash gitti. Tek-dilli kontrol klipleri marjinal yavaşlama ile temiz çalışmaya devam etti (anlam benzerliği 0.88-0.95).

**Ek teknik not (Karar 12 ve 13'ün düzeltilmesi):** Üç tur teşhis süresince varsayılan "native CUDA teardown bug'ı" ve "patolojik klip" hipotezleri yanlış çıktı. Gerçek root cause modelin dil çatışmasında uzun beam search'e girmesi, GPU state'ini yormaya, çıkışta CUDA cleanup'ı kirletmesiydi. multilingual=True her segment için ayrı dil tespiti yapmasını sağlayarak bu durumu engelliyor. Bu, "exit code patolojisi" semptomunun çıktı kalitesi semptomu ile birlikte değerlendirilmesinin önemini de gösteriyor.

**Üst üste binen konuşmalar:** ASR overlapping speech durumunda dominant konuşmacıyı seçer, diğerini düşürür. Bu Whisper'ın bilinen ve beklenen davranışıdır, bug değildir. v1 kapsamında speaker diarization eklenmez; v2'de değerlendirilebilir.

**Tolerant containment ve low_quality flag:** Karar 13'te önerilen "tolerant containment + low_quality flag wav_erd benzeri için yeterli" planı geçersizdir. multilingual=True ile crash kaynağı kalkmıştır; ASR worker normal subprocess olarak (process-per-clip izolasyonu gerekmeden) çalışabilir. Düşük kalite flag'i ayrı bir kalite metriği olarak kalabilir ama crash containment kaynağı olarak gerekçesi yoktur.

**Referans:** 
- `outputs/asr_multilingual_hipotez_report.json`
- `outputs/asr_multilingual_hipotez_summary.md`
- Önceki teşhis turları: `outputs/asr_child_exit_diagnosis_report.json`, `outputs/asr_child_exit_test_paketi_report.json`, `outputs/asr_child_exit_tur3_report.json`, `outputs/asr_tek_klip_tekrar_report.json`

**Durum:** Aktif. Sonraki adım ASR pipeline implementasyonuna geçmektir; pipeline tasarımı multi-clip aynı process desenini kullanabilir (process izolasyonuna ihtiyaç kalmadı).

### ~~2026-05-09 / Sunum öncesi gün gün plan~~

**~~Karar:~~ ~~Gün 1: Backend skeleton + streaming ASR; Gün 2: face detection + tracking; Gün 3: tıkla-seç showcase; Gün 4: UI bağlantı + yedek plan; Gün 5: sunum provası.~~**
**~~Gerekçe:~~ ~~axle.ai bağlamı nedeniyle GMY'ye 3-5 günde çalışan stream demo gerekli.~~**
**Durum:** **İptal edildi (2026-05-10).** Geliştirici "acele kararları geri çekiyorum, sistem temelini sarsmayacağım" dedi. Plan `05_AKTIF_GOREV.md`'de yerini ASR dikey dilim sprintine bıraktı.

---

## Açık (karar bekleyen) konular

Aşağıdaki konularda **henüz karar verilmedi**. Karar verildikçe yukarıdaki "kararlar" bölümüne taşınır.

### O1 — Demo backend venv stratejisi (revize edildi)

ASR/STT tarafı için karar verildi: FastAPI/uvicorn/websockets `asr` venv içindedir ve canlı transcript `ASR > streaming_transcription` olarak ele alınır.

Face streaming/showcase backend'i gerekirse ayrı karar olarak açılır.

### O2 — WhisperX'in v0.1 kabul kriterindeki rolü

WhisperX'in `asr` venv'e kurulmayacağı ve `alignment` venv'de kalacağı karara bağlandı (bkz. 2026-05-11 / 4). faster-whisper segment-level timestamp veriyor; word-level alignment için alignment venv smoke sonucu belirleyici olacak.

**Karar gerekiyor:** v0.1 word-level timestamp'i zorunlu kabul kriteri mi, yoksa kalite raporunda "alignment uygulanmadı / sınırlı uygulandı" olarak mı kalacak?

### ~~O3 — Pyannote v0.1 sprintine giriyor mu~~

`asr` venv'inde pyannote var. Master plan diarization'ı benchmark gated yapmış (eşik geçilmezse `speaker_id = null`). v0.1 smoke'da pyannote koşulur mu?

**Not:** Torchcodec sorunu hazırlık çalışmasında çözüldüğünde yeniden değerlendirilecek (bkz. 2026-05-11 / 6).

**Durum:** Karara bağlandı (2026-05-11). Diarization v1 kapsamındadır; bkz. 2026-05-11 / 15.

### O4 — Test video seçimi

v0.1 smoke için Türkçe TRT örneği gerekli. Henüz seçilmedi.

**Karar gerekiyor:** Hangi video?

### O5 — UI panel düzeltme görevlerinin önceliği

Güncel UI takip dosyası: `mutfak/10_UI_NOTLARI.md`.

2026-05-14'te kapatılan ilk UI davranış sorunları:

- Upload otomatik ASR başlatmıyor; ASR kullanıcı onayıyla `ASR Başlat` üzerinden çalışıyor.
- Dosya yüklenince görünür hazır mesajı veriliyor: `<dosya_adı> ASR için hazır`.
- `DEMO MODU` rozeti kaldırıldı.
- `İnceleme bekliyor` dili kaldırıldı; UI gerçek review görevi icat etmiyor.
- Timeline-ASR çift yönlü seçim/vurgu eklendi.
- Klavye kontrolü eklendi: `Space`/`K` play-pause, `J` geri, `L` ileri.

İlk UI panel zip'inde tespit edilen ve/veya hâlâ izlenen sözleşme/disiplin sapmaları:

1. Mock'tan yabancı ünlü face match örnekleri (Michael Jordan) çıkarılmalı.
2. Status vocabulary master plan'a hizalanmalı.
3. Audio Activity + Song Performance track'leri eklenmeli.
4. SPEAKER vs FACE_CLUSTER vs PERSON ayrımı.
5. Tag review queue item'ı kaldırılmalı (v1.1).
6. Türkçe label kararı.
7. Job status göstergesi.
8. CandidateRelation review kartı (sonraki sprint).

**Durum:** İlk davranış düzeltmeleri yapıldı. Kalan ürünleşme ve sözleşme işleri `mutfak/10_UI_NOTLARI.md` altında takip edilecek. CandidateRelation / gelişmiş review / ID ayrımı gibi kalıcı ürün kararları ayrıca karar olarak yazılmalı.

### O6 — KVKK retention sayıları

Master plan §0.3.15'te "unknown face crop retention: 30 gün" gibi sayılar var ama hukuki dayanak yok.

**Karar gerekiyor:** Avukat veya hukuk danışmanı görüşüyle revize edilecek. v0.4 öncesi netleşmeli.

### O7 — Lisans doğrulama sırası

InsightFace / buffalo_l, YOLO-World, OneOCR, PaddleOCR lisansları benchmark öncesi doğrulanmalı (master plan §0.3.15). Henüz yapılmadı.

**Karar gerekiyor:** Hangi sırayla, hangi haftada?

---

## Karar günlüğü disiplini

1. Yeni karar verildiğinde **hemen** bu dosyaya eklenir.
2. Tarih ve sıra numarası verilir (`2026-05-10 / 3` formatı).
3. Karar, gerekçe ve referans dosyaya yazılır.
4. Eski karar iptal edilirse silinmez, üstü çizilir, "İptal edildi" satırı eklenir.
5. Açık (karar bekleyen) konular "Açık konular" bölümünde tutulur; karara bağlandığında üst kısma taşınır.

Bu disiplin olmadan bir karara hangi sebeple varıldığı kaybolur. Kaybolan gerekçeler ileride aynı kararı tekrar tartışmaya yol açar.
