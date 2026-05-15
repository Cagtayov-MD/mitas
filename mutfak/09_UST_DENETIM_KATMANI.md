# 09 — ÜST DENETİM KATMANI

> Son güncelleme: 2026-05-13
> Son değişen bölüm: ilk kayıt — Faz2 üst akıl / model adayları

Bu dosya MITAS'ın Faz2 üst-denetim fikrini tutar. Kısa cevap: amaç bir LLM'e transcript'i ezdirmek değil; ASR/OCR/metadata çıktılarının üstünde **kanıt isteyen, bağlam bilen, risk sınıflayan bir denetçi** kurmaktır.

---

## 1. Ana fikir

MITAS modülleri önce kanıt üretir:
- ASR konuşmayı döker.
- OCR/KJ ekrandaki yazıyı çıkarır.
- Face/visual/audio modülleri sahne ve varlık sinyali üretir.
- Metadata/reference katmanı film, kişi, kurum, eser ve tarih bağlamı verir.

Üst-denetim modeli bu kanıtların üstüne bakar ve şunu yapar:
- özel isim hatası veya canonical eşleşme adayı üretir,
- quoted evidence / tabela / fiş / kart / altyazı gibi kanıt span'lerini ezmez,
- tarihsel anakronizm veya bağlam kırığı yakalar,
- yeterli kanıt yoksa frame/crop/OCR/ASR/reference ister,
- emin değilse insan review veya kırmızı bayrak üretir.

Bu katmanın çalışma adı:

```text
MITAS Üst Denetim Katmanı
Evidence-Seeking Semantic Review Layer
```

---

## 2. Neden gerekli

100.000 video ölçeğinde her özel isim, her OCR satırı ve her bağlam şüphesi insana tek tek sorulamaz. Ama yanlış metadata, eksik metadata'dan daha tehlikelidir.

Bu nedenle modelin rolü:

```text
hakim değil
kanıt isteyen denetçi
```

Örnekler:
- Belgeselde "Barış Mango" geçiyorsa bu gerçekten ASR hatası mı, yoksa ekrandaki kanıt/örnek span'i mi?
- 1936 filminde "Ahmet Necdet Sezer oyuncuydu" gibi bir cümle varsa bu metadata/ASR/OCR bağlam kırığı mı?
- Atatürk modern bir nesneyle görünüyorsa bu tespit hatası mı, canlandırma mı, yoksa etiketsiz temsilî sahne mi?

Üst-denetim bunları "düzeltmek" yerine önce sınıflandırır ve kanıt ister.

---

## 3. İzinli aksiyonlar

Model serbest aksiyon alamaz. Sadece şu aksiyonları önerebilir:

| Action | Anlam |
|---|---|
| `canonical_link_only` | Span korunur; sadece canonical varlık bağlantısı kurulur. |
| `replace_suggestion` | Normal konuşma ASR hatası için normalize katmanda replace önerilir. |
| `review_only` | Otomatik işlem yok; review notu. |
| `fetch_frame` | İlgili timestamp frame'i getir. |
| `fetch_frame_crop` | Yazı/nesne/kişi bölgesini crop olarak getir. |
| `re_ocr_crop` | Crop üzerinde OCR tekrar çalıştır. |
| `re_asr_window` | İlgili ses penceresini tekrar ASR yap. |
| `reference_check` | Cast/film/person/organization/reference cache ile kontrol et. |
| `red_flag` | Bağlam çelişkisi veya yüksek riskli metadata problemi. |
| `human_review` | İnsan review gerekir. |

MITAS orchestration katmanı bu aksiyonları çalıştırır; model kendi başına dosya getirmez, değiştirmez veya kalıcı metadata yazmaz.

---

## 4. Kanıt isteyen döngü

Temel akış:

```text
ASR/OCR/metadata çıktısı
→ text üst-denetim modeli
→ findings + allowed_actions
→ MITAS kanıt toplar
→ frame/crop/OCR/ASR/reference paketi
→ VLM veya text üst-denetim ikinci tur
→ final finding / red flag / normalized entity
```

Örnek:

```text
OCR/ASR: Ahmet Necdet Sezer filmin oyuncularındandı
Film: 1936 yapımı siyah beyaz film

Model:
contextual_anomaly, reference_check + fetch_frame_crop iste

MITAS:
timestamp, frame, crop, OCR, cast reference getir

Final:
detection_error / unlabeled_reenactment / context_mismatch / human_review
```

---

## 5. Deterministik replace kapısı

Model `replace_allowed=true` dese bile MITAS aşağıdaki kapıyı uygular.

Replace ancak şu koşullarda geçerlidir:

```text
action == replace_suggestion
mention_context == normal_speech
canonical dolu
confidence high veya kabul edilen medium
deterministik kapı veto etmiyor
```

Otomatik replace kesin kapalıdır:

```text
quoted_evidence
sign_or_label
error_example
OCR text / on-screen text
tabela / fiş / kart / altyazı / arşiv notu
canonical boş
confidence low
prompt injection veya görünen talimat metni
```

Bu durumlarda doğru davranış genellikle:

```text
canonical_link_only
review_only
red_flag
```

---

## 6. Model adayları ve güncel gözlem

### Ana adaylar

| Model | Gözlem | Olası rol |
|---|---|---|
| `google/gemma-4-26b-a4b` | Çok iyi, Qwen'e yakın, yaklaşık 5x hızlı gözlendi. | Default text üst-denetim adayı |
| `moonshotai/Kimi-K2.6` | ASR/OCR proper-name JSON testinde çok güçlü çıktı; schema temiz, yerel tabela tuzaklarına düşmedi, `İnce Mehmet`, çift bağlamlı `Müzeyyen Şener`, `C. AUBREY SMlTH` ve tarihsel imkansızlık vakalarını yakaladı. | Yeni güçlü default / production adayı; Gemma ve Qwen ile tekrar benchmark edilmeli |
| `qwen/qwen3.6-27b` | En dengeli policy ve bağlam ayrımı; yavaş kalabiliyor. | Kalite lideri / ikinci görüş |
| `qwen/qwen3-30b-a3b-2507` | Çok iyi, bazı kaçırmalar var; Qwen 27B alternatifi. | Production alternatifi |
| `meta/llama-3.3-70b` | Doğru promptla güvenli/konservatif; pahalı. | Audit / hakem |
| `nvidia/nemotron-3-nano-omni` | Textte iyi; asıl değeri multimodal. | Frame/OCR/VLM kanıt okuyucu |

### Orta / koşullu

| Model | Gözlem | Not |
|---|---|---|
| `google/gemma-4-e4b` | Kısa blokta iyi; thinking sızdırabiliyor. | Ucuz kısa blok tarayıcı olabilir |
| `Qwen3 14B` | Canonical iyi, replace agresif. | Post-processor şart |
| `mistral-nemo-instruct-2407` | Orta, policy tutarsız. | Ön eleme olabilir |
| `openai/gpt-oss-20b` | Bu görevde zayıf/orta-alt. | Structured output ile tekrar denenebilir |

### Bu iş için zayıf veya yanlış rol

| Model | Neden |
|---|---|
| `ibm/granite-3.2-8b` | Bağlam tuzaklarına düştü, yanlış canonical üretti. |
| `zai-org/glm-4.7-flash` | Çok uzun thinking, eksik schema, normal_speech ayrımı zayıf. |
| `qwen/qwq-32b` | Reasoning sızdırma/format ve agresif replace riski. |
| `qwen/qwen2.5-vl-7b` | Text-only testte loop'a girdi; görsel OCR/crop testinde ayrıca değerlendirilecek. |

Geçici karar:

```text
Default text üst-denetim: google/gemma-4-26b-a4b
Yeni güçlü text adayı: moonshotai/Kimi-K2.6
Kalite/ikinci görüş: qwen/qwen3.6-27b
Alternatif Qwen: qwen/qwen3-30b-a3b-2507
Audit: meta/llama-3.3-70b
Görsel kanıt: nvidia/nemotron-3-nano-omni, qwen2.5-vl-7b ayrı test
```

---

## 7. Benchmark rubriği

Her model aynı prompt ve test setiyle şu başlıklarda puanlanır:

1. JSON-only ve schema uyumu.
2. Doğru özel isimleri gereksiz listelememe.
3. Canonical alanını doğru doldurma.
4. `quoted_evidence` / `sign_or_label` / `error_example` bağlamında replace'i kapatma.
5. Normal konuşma ASR hatasında replace önerme.
6. Prompt injection / görünen talimat metnine kapılmama.
7. Tarihsel anakronizm veya bağlam kırığı yakalama.
8. Gereksiz review şişirmeme.
9. Hız / VRAM / thinking sızıntısı.

İlk benchmark seti 10-20 kısa örnekten oluşacak:
- özel isim hatası,
- yerel tabela/işletme adı,
- quoted evidence,
- OCR/ASR çelişkisi,
- tarihsel anakronizm,
- prompt injection,
- film/cast/reference kontrolü,
- belgesel/canlandırma/temsili sahne ayrımı.

---

## 8. Faz2 MVP kapsamı

İlk uygulanacak kapsam text-only olmalı:

```text
transcript blokları
→ üst model findings JSON
→ deterministik kapı
→ normalized_entities + red_flags
```

Blok stratejisi:

```text
haber/spot: 60-90 saniye blok, 10-15 saniye overlap
belgesel/program: 3-5 dakika blok, 20-40 saniye overlap
token hedefi: 800-2000 token/blok
max: 3000 token/blok
```

60 dakikalık programı tek seferde modele vermek production için doğru yol değildir. Uzun context'i sadece final compact review veya audit için kullanılır.

---

## 9. Sıradaki somut işler

1. Benchmark setini 10-20 örnekle sabitle.
2. En iyi text modellerini aynı ayarlarla tekrar test et: Gemma 26B A4B, `moonshotai/Kimi-K2.6`, Qwen 27B, Qwen3-30B-A3B.
3. VLM test seti hazırla: frame/crop OCR doğrulama, KJ, jenerik, tabela, arşiv kartı.
4. Faz2 JSON schema taslağını çıkar.
5. Deterministik kapı testlerini yaz.
6. `core/pipelines/asr/phase2/entity_normalization.py` stub'ını text-only MVP için gerçek modüle çevirmeden önce geliştirici onayı al.

---

## 10. Kısa hatırlatma

Bu katmanın başarısı modelin "çok bilmesine" değil, **nerede emin olmadığını bilip kanıt istemesine** bağlıdır.

Doğru davranış:

```text
az ama güvenilir replace
bol ama izlenebilir canonical link
yüksek riskte red flag
belirsizlikte kanıt iste
kanıt yoksa insana sor
```
