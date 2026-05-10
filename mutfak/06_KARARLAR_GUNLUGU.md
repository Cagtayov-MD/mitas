# 06 — KARARLAR GÜNLÜĞÜ

> Son güncelleme: 2026-05-11
> Son değişen bölüm: lokal git ve test klip havuzu

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
**Durum:** Aktif.

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

### O3 — Pyannote v0.1 sprintine giriyor mu

`asr` venv'inde pyannote var. Master plan diarization'ı benchmark gated yapmış (eşik geçilmezse `speaker_id = null`). v0.1 smoke'da pyannote koşulur mu?

**Not:** Torchcodec sorunu hazırlık çalışmasında çözüldüğünde yeniden değerlendirilecek (bkz. 2026-05-11 / 6).

**Karar gerekiyor:** Smoke ölçeğinde diarization test edilir mi, yoksa v0.2'ye bırakılır mı?

### O4 — Test video seçimi

v0.1 smoke için Türkçe TRT örneği gerekli. Henüz seçilmedi.

**Karar gerekiyor:** Hangi video?

### O5 — UI panel düzeltme görevlerinin önceliği

Dün UI panel zip'inde tespit edilen sözleşme/disiplin sapmaları:

1. Mock'tan yabancı ünlü face match örnekleri (Michael Jordan) çıkarılmalı.
2. Status vocabulary master plan'a hizalanmalı.
3. Audio Activity + Song Performance track'leri eklenmeli.
4. SPEAKER vs FACE_CLUSTER vs PERSON ayrımı.
5. Tag review queue item'ı kaldırılmalı (v1.1).
6. Türkçe label kararı.
7. Job status göstergesi.
8. CandidateRelation review kartı (sonraki sprint).

**Karar gerekiyor:** Bu düzeltmeler ne zaman? v0.5 öncesi mi (timeline birleşimi sırasında), yoksa v1.0 sonu mu?

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
