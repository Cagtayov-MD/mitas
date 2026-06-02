# MİTAS — Profil Konfigürasyon Matrisi

> **İLKE (Çağatay, 2026-06-02):** Her profil **BAĞIMSIZ**. Hiçbir ayar default/miras **DEĞİL**.
> Her profil için her satır **AYRI AYRI ve BİLİNÇLİ** girilir. Hiçbir modül "default açık/kapalı"
> varsaymaz — profilde ne yazıyorsa o koşar.
>
> `⬜ DOLDURULACAK` = henüz karar verilmedi. **Boş = "karar bekliyor", DEFAULT DEĞİL.**
> Parantez içi `(ölçüm: …)` = elde olan veri (karar için), ayar değil.

**Profiller:** `film_dizi` · `belgesel` · `müzik_eğlence` · `spor` · `stüdyo` · `haber` · `stt`

---

## Aksiyom (ayar) referansı — her profil için doldurulacak satırlar

### A. ASR (konuşma→metin)
| anahtar | seçenekler | not |
|---|---|---|
| `asr` | AÇIK / KAPALI | hiç koşsun mu |
| `asr.model` | large-v3-turbo / large-v3 | turbo hızlı, v3 kaliteli |
| `asr.word_alignment` | AÇIK / KAPALI | whisperx kelime hizalama (yavaş; özet için gereksiz) |
| `asr.diarize` | AÇIK / KAPALI | konuşmacı ayrımı (yavaş; özet için gereksiz) |
| `asr.fallback` | AÇIK / KAPALI | large-v3 düzeltme passı (yavaş) |
| `asr.word_timestamps` | AÇIK / KAPALI | kelime-zamanı |
| `asr.beam_size` | 1 / 5 | 1 = greedy/hızlı, 5 = kaliteli/yavaş |
| `asr.vad` | AÇIK / KAPALI | sessizlik atlama |
| `asr.content_profile` | film / bulten_haber / muzik_programi / studio_panel / spor / belgesel | |
| `asr.language` | tr / en / ar / … / **AUTO** | AUTO = kanal-dil tespiti (film); en iyi özet için doğru dilde dinle |
| `asr.channel_lang` | AÇIK / KAPALI | TÜM stream/kanal dilini KONUŞMADA tespit → türkçe kanaldan özet; yoksa kanal-1 kendi dilinde; diğer dil bilgi için saklanır; efekt elenir |

### B. OCR (künye / jenerik)
| anahtar | seçenekler | not |
|---|---|---|
| `ocr` | AÇIK / KAPALI | künye çıkarılsın mı |
| `ocr.jenerik_finder` | AÇIK / KAPALI | gerçek kredi bölgesi tespiti (altyazıyı eler) |
| `ocr.panorama` | AÇIK / KAPALI | hareketli scroll'u composite'e diz + OneOCR |
| `ocr.fqc_stroke_px` | sayı | okunabilirlik eşiği (altı = FQC RED → kimlik-teyit) |
| `ocr.reader` | OneOCR / … | okuma motoru |
| `ocr.format` | TRT-oto / film / dizi | film/dizi PDF formatı |

### C. Özet (summary)
| anahtar | seçenekler | not |
|---|---|---|
| `ozet` | AÇIK / KAPALI | |
| `ozet.motor` | Sonnet / qwen35local / … | (qwen ÖLÇÜLDÜ: prompt tutmuyor) |
| `ozet.prompt` | ozet_promt.txt / profil-özel | spor vb. özel soru seti olabilir |
| `ozet.girdi` | transcript | |
| `ozet.hedef` | hız / kalite notu | |

### D. PDF · E. Afiş · F. İsim normalizasyon · G. Diğer
| anahtar | seçenekler |
|---|---|
| `pdf` / `pdf.format` | AÇIK/KAPALI · TRT-oto/film/dizi |
| `afis` | AÇIK / KAPALI (IMDb güvenli eşleşme) |
| `isim_norm` | AÇIK / KAPALI (Türkçe koru / yabancı ASCII + Qwen) |
| `translate` `face` `visual` `audio` `tag` | AÇIK / KAPALI (her biri ayrı) |

═══════════════════════════════════════════════════════════════════════

## ⬛ PROFİL: FİLM / DİZİ   (tür TRT 3. parselden oto: 1→film, 0→dizi)

### A. ASR — **LEAN / transcript-only modu** (özet için: en hızlı, sadece metin)
| anahtar | DEĞER |
|---|---|
| `asr` | **AÇIK** |
| `asr.model` | **large-v3-turbo** |
| `asr.word_alignment` | **KAPALI** |
| `asr.diarize` | **KAPALI** |
| `asr.fallback` | **KAPALI** |
| `asr.word_timestamps` | **KAPALI** |
| `asr.beam_size` | **1** |
| `asr.vad` | **AÇIK** |
| `asr.content_profile` | **film** |
| `asr.language` | **film → AUTO** (kanal-dil tespiti) · **dizi → tr** (sabit) |
| `asr.channel_lang` | **AÇIK (film)**: tüm stream/kanal tara (130/300/480s, konuşmada); türkçe kanal→özet (Whisper tr), yoksa kanal-1 kendi dilinde; diğer dil bilgi için sakla; efekt at — `scripts/_channel_lang.py` |
> Ölçüm: bu ayarla 2.5 saatlik bölüm **~2.5 dk** (~25–60x realtime). Runner: `scripts/_fast_asr.py`.

### B. OCR
| anahtar | DEĞER |
|---|---|
| `ocr` | **AÇIK** |
| `ocr.jenerik_finder` | **AÇIK** |
| `ocr.panorama` | **AÇIK** |
| `ocr.fqc_stroke_px` | ⬜ DOLDURULACAK *(ölçüm: stroke_px<3 okunmaz — Don Kişot 1.9 vs Ahlat 5.48)* |
| `ocr.reader` | **OneOCR** |
| `ocr.format` | **TRT-oto** |

### C. Özet
| anahtar | DEĞER |
|---|---|
| `ozet` | **AÇIK** |
| `ozet.motor` | **Sonnet** (Claude API) — *API en sonda bağlanacak; şimdilik placeholder* |
| `ozet.prompt` | **ozet_promt.txt** |
| `ozet.girdi` | **lean transcript** (yukarıdaki ASR çıktısı) |
| `ozet.hedef` | **EN HIZLI + KALİTE-OPTİMİZE** (hız = lean ASR; kalite = Sonnet) |

### D–G
| anahtar | DEĞER |
|---|---|
| `pdf` / `pdf.format` | **AÇIK** / **TRT-oto** |
| `afis` | **AÇIK** |
| `isim_norm` | **AÇIK** |
| `translate` `face` `visual` `audio` `tag` | ⬜ DOLDURULACAK |

═══════════════════════════════════════════════════════════════════════

## ⬜ PROFİL: BELGESEL — hepsi DOLDURULACAK
A.ASR: ⬜ · B.OCR: ⬜ · C.Özet: ⬜ · D.PDF: ⬜ · E.Afiş: ⬜ · F.İsim: ⬜ · G.Diğer: ⬜

## ⬜ PROFİL: MÜZİK / EĞLENCE — hepsi DOLDURULACAK
A.ASR: ⬜ · B.OCR: ⬜ · C.Özet: ⬜ · D.PDF: ⬜ · E.Afiş: ⬜ · F.İsim: ⬜ · G.Diğer: ⬜

## ⬜ PROFİL: SPOR — hepsi DOLDURULACAK
A.ASR: ⬜ · B.OCR: ⬜ · C.Özet: ⬜ *(not: spor için özel soru seti olabilir)* · D.PDF: ⬜ · E.Afiş: ⬜ · F.İsim: ⬜ · G.Diğer: ⬜

## ⬜ PROFİL: STÜDYO — hepsi DOLDURULACAK
A.ASR: ⬜ · B.OCR: ⬜ · C.Özet: ⬜ · D.PDF: ⬜ · E.Afiş: ⬜ · F.İsim: ⬜ · G.Diğer: ⬜

## ⬜ PROFİL: HABER — hepsi DOLDURULACAK
A.ASR: ⬜ · B.OCR: ⬜ · C.Özet: ⬜ · D.PDF: ⬜ · E.Afiş: ⬜ · F.İsim: ⬜ · G.Diğer: ⬜

## ⬜ PROFİL: STT — hepsi DOLDURULACAK
A.ASR: ⬜ *(yalnız transcript; PDF/özet yok olabilir)* · B–G: ⬜

═══════════════════════════════════════════════════════════════════════

## Notlar
- **Kod durumu:** Bu matris **spec**'tir. Şu an pipeline'da ASR aksiyomları (whisperx/diarize/
  fallback) `_pipe_asr.py`'da HARDCODE; lean mod ayrı script (`_fast_asr.py`). Sıradaki iş:
  bu toggle'ları `core/pipelines/asr/models.py` profillerine + `_pipe_asr`'a kalıcı bağlamak.
- **Panorama OCR** da ayrı script (`_panorama_ocr.py`); mitas_pipeline ana akışı hâlâ ham OCR
  (`_pipe_ocr`) çağırıyor — entegre edilecek.
- Her ⬜ doldurulduğunda buraya işlenir; matris **tek karar kaynağı**.
