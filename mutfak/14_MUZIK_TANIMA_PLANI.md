# 14 — MÜZİK TANIMA PLANI

> Son güncelleme: 2026-05-18
> Son değişen bölüm: spesifikasyon tamamlama revizyonu — strawman çerçeve düzeltildi, composition entity netleşti, depo dosya-tabanlı, OCR benchmark-gated, KJ güveni OCR'a koşullu, v0.1.x Paket 3 önkoşulu ve kanonik karar (Karar 37) referansları eklendi

Bu dosya MITAS'ın **müzik tanıma** alt sistemi için detaylı analiz ve revize mimari teklifidir. v0.2 sprintindeki "OCR/KJ + Müzik segment" başlığını TRT müzik programlarının gerçek doğasına göre yeniden çerçeveler.

Kısa cevap: mevcut mutfak dokümanları **yanlış bir mimari kurmamış**; sadece TRT müzik programları için gerekli **sinyal hiyerarşisini, veri modelini ve v0.2 uygulanabilir çekirdeğini yeterince spesifik yazmamış**. `01_PROJE_VIZYON.md:39` Song Recognition araçlarını (Chromaprint / AcoustID / local fingerprint DB) **eşit listeler, bir hiyerarşi kurmaz** — yani "Chromaprint primary" demez; ama bu boşluk dışardan bakınca müzik tanımanın fingerprint-merkezli anlaşılmasına açıktır. Bu dosya o eksik spesifikasyonu tamamlar: TRT'de **KJ + ASR Anonsu** primary, fingerprint **doğrulayıcı** katmandır. Ayrıca "müzik bankası" mutfakta tek terim altında karışmış; gerçekte **iki ayrı bileşen** gerekiyor: ① Repertuvar Bankası (eser/sanatçı varlık sözlüğü), ② Fingerprint DB (kayıt parmak izleri).

---

## 1. Sorun: TRT müzik programının doğası

### 1.1 Hedef çıktı (somut)

Bir müzik programı klibi geldiğinde sistem şu metadata'yı üretmeli:

```
performance_id: perf_01HF...
  composition: "Ne Güzel Güldün"
  composer:    "Selâhattin Pınar"
  lyricist:    "Vecdi Bingöl"
  makam:       "Hicaz"            (varsa)
  performer:   "Bülent Ersoy"
  start:       00:12:11.240
  end:         00:13:44.880
  evidence:
    - kj_event_id: ev_kj_...
    - asr_event_id: ev_anons_...
    - audio_activity_event_id: ev_aa_...
    - fingerprint_match_id: null  (canlı icra, eşleşmedi)
  confidence: 0.87
  status: auto
```

### 1.2 TRT müzik programlarının yapısal özellikleri

| Özellik | Sonuç |
|---|---|
| **Stüdyo canlı icrası ağırlıklı** ("Akşam Sefası", "Beyaz Show", "7'den 77'ye") | Aynı eserin arşivde fingerprint'i yok; her klipte yeni icra |
| **Sunucu anonsu yapar** ("Şimdi sizlere Y'den X'i dinleteceğiz") | ASR ile yakalanabilir, en erken sinyal |
| **KJ (alt bant) detaylı bilgi gösterir** (eser, beste, güfte, okuyan) | OCR ile çözülebilir, en zengin sinyal |
| **TSM / THM / TTM repertuvarı** | Uluslararası DB'lerde (AcoustID, MusicBrainz) marjinal kapsam |
| **Eserin kendisi vs icrası ayrımı** ("Ne Güzel Güldün" 30 farklı sanatçıda) | Composition ≠ Performance ayrımı zorunlu |
| **Eserler arası geçiş ve fonda müzik** | speech/music sınır tespiti ±2 sn tolerans gerekli |

### 1.3 Mutfak'ta eksik bırakılan 5 spesifikasyon noktası

Aşağıdaki noktalar mutfak'ın "yanlış" yaptığı şeyler değil; TRT müzik programları için **spesifik yazılmamış** bırakılmış kararlardır. Bu dosya bunları tamamlar.

| # | Mutfak'ta spesifik yazılmamış | TRT gerçeği | Tamamlanması gereken |
|---|---|---|---|
| 1 | `01_PROJE_VIZYON.md:39` Song Recognition araçlarını eşit listeler; primary/doğrulayıcı hiyerarşisi **yazılmamış** (dışardan fingerprint-merkezli okunmaya açık) | AcoustID kayıt (recording) fingerprint tutar, beste (composition) değil; TSM/THM ve canlı stüdyo icrasında çoğunlukla eşleşmez | Açık sinyal hiyerarşisi: KJ + Anons primary, fingerprint doğrulayıcı (Karar 37) |
| 2 | "Kurum içi local fingerprint DB" tek terimle anılmış | İhtiyaç iki ayrı DB: ① repertuvar (eser/besteci varlık sözlüğü) ② fingerprint (kayıt parmak izi). Birincisi olmadan ikincisinin metadata değeri yok | Repertuvar mimaride yok; fingerprint match'i geldiğinde "bu hangi eser?" sorusu cevapsız |
| 3 | `song_performance` event tek seviye | Aynı eser onlarca klipte → metadata tekrarı, "Bülent Ersoy hangi eserleri okudu" sorgusu zor | Composition vs Performance ayrımı şart |
| 4 | `04_YOL_HARITASI.md:87` "KJ + ASR + audio_activity + fingerprint birleşimi" der ama **ağırlık/öncelik tanımlamaz** (KJ zaten ilk listelenmiş) | TRT'de KJ ve anons doğrudan ground-truth içerir; fingerprint canlı icrada zayıf | Birleşim kuralı değil, açık güven sırası ve karar matrisi spesifikasyonu |
| 5 | "song announcement detection" tek satırda geçmiş (`04_YOL_HARITASI.md:95`) | "Şimdi X'ten Y'yi dinleyeceğiz" cümlesi eserin başından önce gelir, KJ'den daha erken sinyal | Anons parser bağımsız modül olmalı |

---

## 2. Önerilen mimari

### 2.0 Üç tanıma seviyesi (kavramsal çerçeve)

"Şarkı tanıma" tek bir Shazam-vari fingerprint problemi **değildir**; TRT arşivi için üç ayrı tanıma seviyesi vardır ve sistem her seviyeyi ayrı ele alır:

1. **Kayıt tanıma** — "Bu duyduğum ses şu *kayıt* mı?" → Chromaprint / AcoustID / local fingerprint DB. Arşiv kaydı çalındıysa güçlü; canlı stüdyo icrasında çoğu zaman boş döner. (§3.6 · `song_recognition_match`)
2. **Eser tanıma** — "İcra edilen *eser* hangisi?" → KJ "Beste/Güfte/Okuyan" + sunucu anonsu + Repertuvar Bankası. **TRT için asıl değer burada.** (§3.2-§3.4 · `composition` entity)
3. **İcra tanıma** — "Bu klipte *kim*, *hangi eseri*, *hangi zaman aralığında* söyledi?" → `song_performance` event'i: `composition_id` + performer + start/end + evidence. (§3.7 · `song_performance` event)

Seviyeler birbirini dışlamaz; aggregator (§3.7) eldeki sinyallerle hangi seviyeye kadar gidebiliyorsa oraya kadar gider, emin değilse `needs_review` üretir. En güçlü senaryo KJ + anons birlikte; en zor senaryo yalnız canlı müzik sesi (Demucs + lyric match ile güçlenir, §3.5).

### 2.1 Sinyal hiyerarşisi (TRT-kalibre)

```
GÜVEN ←──────────────────────────────────── DÜŞÜK
 1. KJ/OCR Parser         (canonical, programın gösterdiği)
 2. ASR Anons Parser      (sunucu söylüyor, eserden önce)
 3. Lyric Match           (vokal → güfte → repertuvar)
 4. Audio Activity Layer  (sınır tespiti — ±2sn için)
 5. Chromaprint/AcoustID  (arşiv kaydı çalındıysa son şans)
```

**Neden bu sıra:** TRT yapımı klipte KJ ve anons bilerek üretilmiştir (yapımcı orada ona zaman ayırmıştır). Fingerprint canlı icrada başarısızdır. Lyric match repertuvarı zenginleştikçe değerli olur. Audio activity sınır tespiti için, identification için değil.

### 2.2 Şema genişletmeleri

Mevcut `EventType` ve `RelationType` çekirdek; iki yeni event ve üç yeni relation eklenmesi gerekiyor:

```python
class EventType(str, Enum):
    # mevcut (core/schemas/common.py'de doğrulandı):
    audio_activity = "audio_activity"
    song_announcement = "song_announcement"
    song_recognition_match = "song_recognition_match"
    song_performance = "song_performance"
    # yeni (tek ekleme):
    kj_music_credit = "kj_music_credit"               # KJ'den çıkan structured credit (timeline event)

class RelationType(str, Enum):
    # mevcut:
    kj_mentions_song_candidate = "kj_mentions_song_candidate"
    asr_supports_song_candidate = "asr_supports_song_candidate"
    fingerprint_supports_song_candidate = "fingerprint_supports_song_candidate"
    # yeni:
    performance_uses_composition = "performance_uses_composition"
    announcement_introduces_performance = "announcement_introduces_performance"
    lyric_match_supports_composition = "lyric_match_supports_composition"
```

> **Not — composition timeline event değildir:** Eser (composition) kalıcı bir **entity**'dir (aşağıdaki tablo), zamanda akan bir timeline event değil. Bu yüzden `EventType`'a `music_composition_ref` gibi bir değer **eklenmez**; `song_performance` event'i `composition_id` foreign key'i taşır ve eser bilgisi entity tablosundan resolve edilir. `core/schemas/common.py:15` `EventType` enum'u tamamen timeline-event'lerden oluşur; oraya entity eklemek kategori hatasıdır.

**Entity tabloları (repertuvar bankası):**

```
Composition (eser):
  composition_id, canonical_name, aliases[], composer_id, lyricist_id,
  makam, usul, genre(TSM|THM|TTM|POP|...), lyrics_text?, source_ref

Artist (sanatçı):
  artist_id, canonical_name, aliases[], roles[besteci|güfteci|icracı|...],
  birth, death, source_ref

Performance (icra):
  performance_id, composition_id, media_id, start_ms, end_ms,
  performer_ids[], confidence, status, evidence_ids[]
```

### 2.3 Veri akışı — paralel + birleştirici

```
KLİP
 ├─► ASR (mevcut) ─────► text + timestamps
 │                       └─► ASR Anons Parser
 │                       └─► Lyric Window Extractor
 ├─► Audio Activity Layer ─► music regions [start,end]
 │                       └─► Boundary Refinement (onset/offset)
 ├─► Video Frames ─► OCR (alt bant) ─► KJ Parser ─► structured credits
 ├─► Demucs (opsiyonel) ─► vocals.wav ─► ASR_vocal ─► Lyric Match
 └─► Chromaprint ─► fingerprint ─► AcoustID + Local DB lookup

HEPSİ → CandidateRelation Builder → Performance Aggregator
                                    ├─► Repertuvar DB Resolver
                                    └─► Performance Event + status(auto|needs_review)
```

---

## 3. Bileşen bileşen tasarım ve model kararları

### 3.1 Audio Activity Layer (sınır tespiti)

**Görev:** Klipteki her saniye için `{speech, music, applause, silence}` etiketi + olasılık eğrisi.

**Aday modeller:**

| Model | Boyut/VRAM | Türkçe? | Kalite | Lisans | Hız |
|---|---|---|---|---|---|
| **YAMNet** (Google) | 17 MB / CPU OK | dil agnostik | iyi (kaba 1s) | Apache 2.0 | çok hızlı |
| **PANNs CNN14** (Kong+) | 320 MB / ~1 GB | dil agnostik | belirgin daha iyi | MIT | hızlı |
| **PANNs Wavegram-Logmel-CNN14** | 360 MB / ~1.2 GB | dil agnostik | SOTA-yakın | MIT | hızlı |
| **BEATs** (MSR 2022) | 90 MB / ~2 GB | dil agnostik | SOTA | MIT | orta |
| **AST** (MIT) | 86 MB / ~1.5 GB | dil agnostik | çok iyi | BSD | orta |
| **Essentia MusicExtractor** | CPU | dil agnostik | klasik DSP, gürültüye duyarlı | AGPLv3 ⚠️ | hızlı |

**Karar (önerim):** **PANNs CNN14 birincil**, YAMNet yedek smoke.

**Gerekçe:**
- AudioSet'te eğitilmiş, applause ve "singing" alt sınıfları var
- MIT, kurum içi ücretsiz
- 3090'da batch koşumda hızlı
- BEATs daha kaliteli ama 2× VRAM, v0.2'de zorlanmaz; v1.x'te aday olabilir
- Essentia AGPL → dağıtım kısıtı, MITAS prensibine uymaz (kurum içi ama lisans ileride risk)

**Sınır rafine etmek için ek katman:**
- PANNs `music` olasılığında onset/offset detection (BIC veya basit threshold + hysteresis)
- Cross-validation: KJ görünüm anı, applause sinyali, ASR boşluk = music start adayı

**Kabul kriteri:** speech/music ayrımı insan etiketle %90+ uyum (mutfaktan); sınır ±2 sn (mutfaktan).

---

### 3.2 OCR + KJ Parser (en yüksek değerli sinyal)

**Görev:** Müzik penceresinde alt bant OCR → "eser / beste / güfte / okuyan" alanları.

**OCR motoru:**
mutfakta karar gated (`03_GUNCEL_DURUM.md`'de PaddleOCR PP-OCRv5 aday). Bunu devralıyoruz — yeni karar açmıyoruz.

| Model | Türkçe karakter | Kalite | Hız (3090) | Lisans |
|---|---|---|---|---|
| **PaddleOCR PP-OCRv5** | iyi (multilingual) | yüksek | hızlı | Apache 2.0 |
| **OneOCR (Windows)** | iyi | yüksek | hızlı | Windows lisansı ⚠️ |
| **Tesseract** | zayıf | düşük | CPU OK | Apache 2.0 |

**OCR motoru:** PaddleOCR PP-OCRv5 hattıyla ilerlenir. EasyOCR 2026-05-21 kararıyla aktif test/benchmark kapsamından çıkarıldı; Torch tabanlı OCR fallback taşınmaz. Türkçe karakter post-processing altyapısı `core/pipelines/asr/phase2/entity_normalization.py`'de mevcut; müzik KJ alanları için genişletilir.

**KJ Parser — yeni alt-modül:**
TRT müzik KJ formatı kalıplaşmış:
```
GENİŞ FONT — eser adı
küçük font — Güfte: X / Beste: Y / Okuyan: Z
```

Parser yaklaşımı:
1. **Layout-aware extraction:** OCR satırlarını font-size + Y koordinatına göre kümele
2. **Anahtar kelime tabanlı alan tespiti:** `^Güfte\s*[:|]`, `^Beste\s*[:|]`, `^Söz\s*[:|]`, `^Müzik\s*[:|]`, `^Okuyan\s*[:|]`, `^Yorumlayan\s*[:|]`, `^Söyleyen\s*[:|]`, `^Aranje\s*[:|]`
3. **Fuzzy match repertuvara:** rapidfuzz ile alias-aware
4. **Türkçe karakter normalizasyonu:** ı/İ/I, ş/s, ğ/g, ö/o, ü/u, ç/c — hem orijinal hem normalize edilmiş haliyle match

**Lib:** mevcut `zeyrek`, `rapidfuzz` (tag venv'inde — `03_GUNCEL_DURUM.md:260`), TR NER için ek olarak **savasy/bert-base-turkish-ner** veya **dbmdz/bert-base-turkish-cased-ner** opsiyonel.

**Kabul kriteri:** Pilot 1 saatlik klipte KJ kişi/eser çıkarımı %80+ (mutfaktan, korunuyor).

---

### 3.3 ASR Anons Parser (sunucu konuşması)

**Görev:** Müzik penceresinden önceki 30 saniyelik ASR transcript'inde anons cümlesi yakala, eser+sanatçı entity'lerini çıkar.

**Yaklaşım:**
1. **Pattern bank:**
   - `şimdi sizlere (.+?)['ı]?ı? (sun|takdim|dinlet|söyle|çal)`
   - `bu eser (.+?)['ı]?n (.+)`
   - `(.+?)['ı]?n (besteleyip|bestelediği) (.+)`
   - `(.+?)['ı]?ı? okuyacak (.+)`
   - `sözleri (.+?)['ı]?ı?n, müziği (.+?)['ı]?ı?n`
   - ~30 kalıp
2. **Pattern eşleşmesi → entity slot doldurma**
3. **Lexicon ankrajı:** Çıkan span'i repertuvar bankasına fuzzy-match et; eşik altıysa `needs_review`

**Model:** Patternlar deterministik (regex + Türkçe morphological awareness için zeyrek). Üst-denetim (Karar 17) zayıf eşleşmeleri Qwen'e kanıt paketiyle gönderebilir — ama bu Faz 2.

**Kabul kriteri:** Pilot 1 saatlik kliptte ≥%70 anons cümlesinin doğru yakalanması (insan etiketle). %70 mütevazı çünkü her program anons kalıbı kullanmıyor.

---

### 3.4 Repertuvar Bankası (yeni — en kritik eksik)

**Görev:** Eser/besteci/güfteci/icracı varlık sözlüğü ve sorgulama API'si.

**Veri kaynakları:**

| Kaynak | Kapsam | Erişim | Kalite |
|---|---|---|---|
| **TRT Repertuvar Kurulu** veritabanı | TSM + THM kanonik eserler | TRT içi — istenmeli | yüksek, küratör onayı geçmiş |
| **TRT Müzik veritabanı** (varsa) | TRT yapımı icralar | TRT içi | yüksek |
| **MusicBrainz Turkish subset** | popüler + bazı klasik | açık (Lisans CC0) | orta, eksik |
| **Wikipedia / Vikipedi** | sanatçı meta | açık | düzensiz, kaynak doğrulamalı |
| **TSMK / Üsküdar Müzik vb.** | uzmanlık derlemeler | sınırlı | yüksek, dağıtık |

**Karar (önerim):** Birincil = TRT Repertuvar Kurulu (proje sahibinden istenmesi gerekir, formatı CSV/XML/MDB ne olursa olsun); ikincil = MusicBrainz Turkish parser; doldurucu = elle seed.

**Şema (yukarıda taslak); depolama (v0.2):** Dosya-tabanlı — SQLite veya CSV/JSONL. Gerekçe: proje şu an **JSON-primary** (`outputs/.../timeline_events.json`); ortada Postgres instance **yok** ve müzik kodu v0.2'ye ait. PostgreSQL + pgvector v0.4 yüz bankasıyla birlikte planlı; o altyapı geldiğinde repertuvar deposu PG'ye migrate edilebilir. v0.2'de PG varsaymak projenin JSON-primary duruşuyla çelişir.

**Sorgulama API'si:**
- `resolve_composition(text, fuzzy_threshold=0.85) → composition_id | None`
- `resolve_artist(text, role_filter=['besteci'|'icracı'|...]) → artist_id | None`
- `compositions_by_artist(artist_id, role) → list`
- `lyrics_of(composition_id) → text | None`

Türkçe karakter normalizasyonu, ALL CAPS düzeltmesi, ünvanı temizleme (`Sn.`, `Üstad`, `Sanatçı` vb.) gibi pre-processing katmanı zorunlu.

---

### 3.5 Vocal Isolation + Lyric Match (orta-vade)

**Görev:** Müzik bölgesinde vokali izole et → vokal üzerinde ASR → çıkan güftenin repertuvardaki güfteyle eşleşmesi → eser kimliği.

**Source separation modelleri:**

| Model | Kalite | VRAM | Lisans | Hız |
|---|---|---|---|---|
| **Demucs htdemucs_ft** | en yüksek (MUSDB SDR ~9.3) | ~3 GB | MIT | yavaş-orta |
| **Demucs htdemucs** | yüksek (SDR ~8.8) | ~2.5 GB | MIT | orta |
| **MDX-Net (UVR)** | yüksek | ~3 GB | MIT | orta |
| **Spleeter** | orta | ~1 GB | MIT | hızlı |
| **Open-Unmix** | orta | ~1 GB | MIT | hızlı |

**Karar (önerim):** **htdemucs_ft** — kalite/lisans en iyi denge, 3090'a sığar, izole ses ASR'nin doğruluğunu belirgin artırır. Spleeter düşük kaliteli vokal verir, ASR akıbeti kötü.

**Lyric match:**
1. Demucs → vokal.wav
2. Demucs vokali üzerinde mevcut Whisper (turbo veya large-v3 fallback) koşar — `word_timestamps=True`
3. Çıkan transcript → repertuvar `lyrics_text` ile BM25 + fuzzy phrase match
4. Eşik üzerindeyse `lyric_match_supports_composition` relation üretilir

**Model — text matching:**
- Birinci kat: **BM25** (rank_bm25 lib) — hızlı, çoğunlukla yeterli
- İkinci kat: **Türkçe Sentence-BERT** — `emrecan/bert-base-turkish-cased-mean-nli-stsb-tr` — semantic similarity, BM25 düşük güvenliyse
- Üçüncü kat (opsiyonel): üst-denetim Qwen'e kanıt paketi

**Önemli:** Bu modül v0.2 **çekirdeğine girmez** — v0.2.x/v0.3'e opsiyonel modül olarak ertelenir. Gerekçe: en pahalı modül (GPU + repertuvarın `lyrics_text` alanlarının dolu olması gerekir) ve repertuvar olgunlaşmasına bağlı. v0.2 çekirdeği KJ + Anons + Audio Activity + Aggregator'dır; lyric match sonraki fazın opsiyonel katmanıdır.

**Kabul kriteri:** Repertuvar lyrics_text'i dolu olan eserlerde tespit ≥%75.

---

### 3.6 Chromaprint / AcoustID (yedek son katman)

**Görev:** Klipte arşiv kaydı çalındıysa fingerprint match.

**Model:** Mevcut karar Chromaprint (fpcalc binary'si PATH'te, `03_GUNCEL_DURUM.md:273`). Devralıyoruz.

**Lookup hiyerarşisi:**
1. **Local fingerprint DB** (TRT arşivindeki kayıtların fingerprint'leri — seed işi)
2. **AcoustID** (eğer kurum politikası dış API'ye izin veriyorsa — KVKK uyumu kontrol edilmeli; AcoustID query'si sadece hash gönderir, ses göndermez → muhtemelen OK)
3. Eşleşme yoksa: `fingerprint_supports_song_candidate` üretme — sessizce skip

**Önemli kısıtlar:**
- Stüdyo canlı icrasında eşleşme beklemiyoruz
- Müzik fonu (BGM) çalındığında düşük confidence ile eşleşme alabilir — speech overlap penaltısı uygulanmalı

**Karar:** Chromaprint doğrulayıcı katman, primary değil. Eşleşmezse mimari işliyor olmalı.

---

### 3.7 Karar Aggregator (CandidateRelation → Performance Event)

**Görev:** Tüm sinyalleri birleştirip `performance` event'i üretmek (auto / needs_review / failed).

**Karar matrisi (basitleştirilmiş):**

> **KJ güveni OCR confidence'ına koşulludur.** TRT eski arşiv KJ'si bozuk/okunması zor olabilir (`01_PROJE_VIZYON.md:24`) ve OCR motoru henüz benchmark-gated. Bu yüzden matristeki "KJ ✅" hücreleri **yüksek OCR confidence** varsayar; OCR confidence düşükse KJ tek başına `auto` değil `needs_review` üretir. Sabit yüksek KJ öncülü prensip 5.1'i (`01_PROJE_VIZYON.md:62` — "yanlış metadata eksikten kötüdür") çiğner. KJ güveni `f(ocr_conf)`'tir, düz sabit değil.

| KJ | Anons | Lyric | Fingerprint | Status | Confidence |
|---|---|---|---|---|---|
| ✅ | ✅ | ✅ | ✅ | `auto` | 0.95+ |
| ✅ | ✅ | – | – | `auto` | 0.85-0.9 |
| ✅ (yüksek ocr_conf) | – | – | – | `auto` | 0.75-0.8 |
| ✅ (düşük ocr_conf) | – | – | – | `needs_review` | 0.45-0.6 |
| – | ✅ | ✅ | – | `auto` | 0.75-0.85 |
| – | ✅ | – | – | `needs_review` | 0.55-0.65 |
| – | – | ✅ | – | `needs_review` | 0.55-0.65 |
| – | – | – | ✅ | `needs_review` | 0.5-0.6 |
| – | – | – | – | (event üretme) | — |

**Sınır (start/end) seçimi:**
- KJ görünüm/kaybolma anı varsa primary
- Yoksa Audio Activity onset/offset
- Anons cümlesi sonu → music start adayı
- Applause sinyali → music end adayı

**Eşik kalibrasyonu:** İlk pilot klipler üzerinde yapılır; mutfak Karar 24 modelinde olduğu gibi sayısal gerekçe ile (TRT verisinde).

---

## 4. Uygulama planı — paket sıralı

Mutfak Karar 25/26 disiplini gereği, her paket commit + test + karar kaydı.

> **Sert önkoşul — v0.1.x Paket 3:** Paket E (ASR Anons Parser) ve Paket H (lyric ASR) `muzik_programi` content profile'ına bağımlıdır. Bu profil **v0.1.x Paket 3 (profile dispatch)** ile gelir ve henüz kapanmadı (`04_YOL_HARITASI.md:53-72`: "profiles.py yok; run_asr_pipeline() sadece MODEL profili alıyor"). Mutfak disiplini "bir dilim oturmadan diğerine geçilmez" (`04_YOL_HARITASI.md:13`) gereği müzik sprinti **başlamadan önce v0.1.x Paket 3 oturmuş olmalıdır**. Bu plan v0.1.x'i ezmez, ona yaslanır.

### Paket A — Veri ve repertuvar hazırlığı (kod yok, veri işi)
1. **TRT Repertuvar Kurulu verisi talep et** (formatı ne olursa olsun)
2. MusicBrainz Turkish subset indir, yerel mirror
3. İlk 50-100 eser seed et — TSM/THM dengeli; pilot test seti için
4. Pilot 1 saatlik 3 müzik programı klibi seç (Akşam Sefası tipi, popüler tip, çocuk programı tipi)
5. Manuel olarak "ground truth" hazırla — her klipteki eser/başlangıç/bitiş/icracı

**Çıktı:** `references/music_repertoire/` + `references/music_pilot/`
**Kabul:** 3 klip × ortalama 5 eser × tam metadata = 15 referans satır

### Paket B — Schema + DB tabloları + Repertuvar API
1. `EventType` ve `RelationType` enum'larına yeni değerleri ekle
2. `core/schemas/music.py` yeni dosya: `Composition`, `Artist`, `Performance` modelleri
3. PostgreSQL migration: `compositions`, `artists`, `performances`, `composition_aliases`, `artist_aliases`, `lyrics` tabloları
4. `core/services/repertoire.py`: `resolve_composition`, `resolve_artist` API'leri (rapidfuzz tabanlı)
5. Paket A'daki seed'i DB'ye yükle

**Kabul:** Unit test — "Selâhattin Pınar" → besteci artist_id'si döner; "ne güzel güldün" → composition_id döner.

### Paket C — Audio Activity Layer
1. `venvs/audio_activity` venv kur — PyTorch + PANNs
2. `core/pipelines/audio_activity/` modülü
3. PANNs CNN14 + AudioSet checkpoint load
4. Klip → 1 sn pencerede sınıflandırma + 100 ms hop'ta refine
5. `audio_activity` event'leri (speech/music/applause/silence aralıkları)
6. Smoke test 3 pilot klipte

**Kabul:** Pilot kliplerde speech/music sınırı insan-etiketle %90+ overlap, sınır ±2 sn.

### Paket D — OCR + KJ Parser
1. `venvs/ocr` venv kur — PaddleOCR
2. `core/pipelines/ocr/` modülü; ROI-first akış (Karar M12)
3. KJ region detection (alt bant): video → frame → bottom_band ROI → OCR
4. Layout-aware field extraction (font size + Y kümele)
5. Anahtar kelime tabanlı alan parser ("Güfte:", "Beste:", "Okuyan:")
6. Repertuvar API ile fuzzy ankraj
7. `kj_music_credit` event'leri

**Kabul:** Pilot kliplerde KJ kişi/eser %80+ doğru çıkarım.

### Paket E — ASR Anons Parser
1. `core/pipelines/asr/announcement_parser.py` yeni dosya — mevcut ASR sonuçları üzerinde post-processing
2. Pattern bank (regex ~30 kalıp, Türkçe morphology-aware)
3. Repertuvar ankrajı
4. `song_announcement` event'leri

**Kabul:** Pilot kliplerde ≥%70 anonsları doğru yakalama.

### Paket F — Karar Aggregator + Performance Event
1. `core/pipelines/music_performance/` modülü
2. CandidateRelation builder (sinyalleri ortak performance pencereye eşle)
3. Karar matrisi uygulaması
4. `song_performance` event'leri (status: auto / needs_review)
5. Timeline merge'a bağlama

**Kabul:** Pilot 3 klipte ground truth ile %80+ eşleşme (auto'lar için), needs_review'lar mantıklı eşik altında.

### Paket G — UI: Uyarılar + Timeline track
1. `Sidebar.tsx` Uyarılar sekmesine "Müzik" alt-rozeti
2. `Timeline.tsx` yeni lane: `Müzik / Şarkı performance`
3. Segment kartı: eser adı + icracı + ▶ buton
4. Video preview üstünde overlay: "12:11–13:44 · Ne Güzel Güldün · Bülent Ersoy"
5. Tıklayınca evidence paneli (KJ snippet, anons cümlesi, fingerprint sonucu)

**Kabul:** Pilot klipte UI doğru gösteriyor, evidence açılıyor.

### Paket H — Vocal Isolation + Lyric Match (opsiyonel, v0.2.x)
1. `venvs/source_sep` venv — Demucs
2. Müzik bölgelerinde Demucs koşar — vokal.wav
3. Vokal üzerinde Whisper turbo
4. BM25 + Sentence-BERT eşleşmesi → `lyric_match_supports_composition`

**Kabul:** Lyrics_text dolu eserlerde ≥%75 tespit.

### Paket I — Chromaprint local + AcoustID
1. fpcalc binary mevcut — entegrasyon kodu
2. Local fingerprint DB seed (TRT arşiv kayıtları için, ileri iş)
3. AcoustID query (KVKK onayı sonrası)

**Kabul:** Bilinen-fingerprint klipte eşleşme.

---

## 5. Risk matrisi ve karşı önlemler

| Risk | Olasılık | Etki | Önlem |
|---|---|---|---|
| TRT Repertuvar verisine erişilemez | orta | yüksek | MusicBrainz + manuel seed ile küçük başla, paralel olarak TRT içi süreci sürdür |
| Stüdyo canlı icrada hiçbir motor fingerprint bulamaz | yüksek | düşük | Mimari zaten primary KJ+Anons'a yaslanıyor; bu beklenen davranış |
| KJ olmadan, anons olmadan, sadece müzik var | orta | yüksek | `audio_activity` event üretilir ama `song_performance` üretilmez; "müzik var, eser bilinmiyor" uyarısı |
| Türkçe karakter OCR hataları | yüksek | orta | İki katmanlı match: orijinal + normalize; entity lexicon ankrajı |
| Aynı isimli besteci/icracı karışıklığı | düşük | orta | Role-aware fuzzy match; KJ'de rol etiketi var |
| Demucs 3090'da diğer modüllerle çakışır | orta | orta | Module config (Karar 5.8) ile sıralı koşum; OCR+ASR bittikten sonra Demucs |
| MusicBrainz Türkiye verisi eksik/yanlış | yüksek | düşük | Sadece doldurucu olarak kullan, kanıt olarak değil; manuel onay gerekli |
| Anons cümle pattern'leri çok değişken, regex yetmiyor | orta | orta | İlk paket regex; gerekirse Türkçe NER modeline (dbmdz/savasy) geç |
| Background music news'te yanlış song_performance üretir | yüksek | yüksek | Eşik: speech overlap > %40 ise song_performance üretme; sadece audio_activity event |
| `fast_with_fallback` ASR vokal track'inde yetersiz olabilir | orta | orta | Vokal track için `large-v3` zorunlu (selective fallback'e gerek yok) |

---

## 6. Açık kararlar (cevap bekliyor)

Aşağıdaki maddeler karar gerektiriyor; karar verildiklerinde `06_KARARLAR_GUNLUGU.md`'ye yazılmalı:

1. **TRT Repertuvar Kurulu verisi** — proje sponsoru ile temas; format ve erişim
2. **AcoustID dış API kullanımı** — KVKK onayı (sadece hash gönderiyor, ses göndermez ama yine de prosedür)
3. **Demucs v0.2'de mi v0.2.x'te mi?** — VRAM bütçesi, sprint uzunluğu
4. **Lyrics_text repertuvarın zorunlu alanı mı?** — Yoksa lyric match opsiyonel mi?
5. **Pilot klip 3'ünün seçimi** — `08_TEST_KLIPLER.md`'ye eklenecek
6. **Background music vs performance ayrımı eşiği** — speech overlap yüzdesi
7. **UI'da müzik için ayrı timeline lane mi, mevcut lane'lerde renkle mi gösterilecek**

---

## 7. Bir paragrafta cevap

Mevcut mutfak mimarisi doğru iskelete sahip ama yanlış ağırlıklara sahip: TRT müzik programlarının doğası gereği Chromaprint/AcoustID primary olamaz, çünkü stüdyo canlı icralarında ve TSM/THM repertuvarında eşleşmez. Asıl güvenilir sinyaller **KJ (alt bant OCR)** ve **ASR sunucu anonsu**; bu ikisi olmadan tasarım çalışmaz. Ayrıca "müzik bankası" mutfakta tek terim altında karışmış; gerçekte iki ayrı DB gerekiyor: ① **Repertuvar Bankası** (eser/besteci/güfteci/icracı varlık sözlüğü — TRT Repertuvar Kurulu seed'i ile), ② **Fingerprint DB** (kayıt parmak izleri — yedek katman). Şemada **composition (eser) vs performance (icra)** ayrımı eklenmeli; aynı eser onlarca klipte tekrar etmemeli. Pipeline sıralaması: KJ → ASR Anons → Lyric Match → Audio Activity (sınır) → Chromaprint (son). Modeller: **PANNs CNN14** (audio activity), **PaddleOCR PP-OCRv5** (OCR, mevcut karar), **htdemucs_ft** (vocal isolation), mevcut Whisper turbo + large-v3 fallback (ASR + lyric ASR), **BM25 + Türkçe Sentence-BERT** (lyric match), **Chromaprint + AcoustID** (fingerprint, son katman). Uygulama 9 pakete bölünmüş (A-I); pilot 3 klipte ölçülecek; kabul kriterleri mutfak v0.2 hedefiyle uyumlu.

---

## 8. Bağlantılı mutfak dosyaları

> **Bu dosya türetilmiş analizdir.** Kanonik kararlar başka yerde: sinyal hiyerarşisi + composition entity + dosya-tabanlı repertuvar → `06_KARARLAR_GUNLUGU.md` Karar 37; v0.2 kapsam deltası → `04_YOL_HARITASI.md` §v0.2; Song Recognition primary/doğrulayıcı niyeti → `01_PROJE_VIZYON.md` §3. Çelişki çıkarsa kanonik dosyalar kazanır, bu dosya güncellenir.

- `01_PROJE_VIZYON.md` §3 — Song Recognition modülü tanımı
- `04_YOL_HARITASI.md` §v0.2 — OCR/KJ + Müzik Segment sprinti
- `06_KARARLAR_GUNLUGU.md` Karar M11 (OCR ilk hedefi KJ + Music Segment Linker), Karar M12 (ROI-first OCR), Karar 15-16 (diarization + graceful degradation modeli — aynı pattern müzik için de geçerli), Karar 17-18 (üst-denetim katmanı)
- `09_UST_DENETIM_KATMANI.md` — zayıf eşleşmeleri Qwen hakemine bağlama yolu
- `core/schemas/common.py` — EventType ve RelationType enum'ları
- `core/pipelines/asr/phase2/entity_normalization.py` — Türkçe entity ankraj altyapısı (genişletilecek)
