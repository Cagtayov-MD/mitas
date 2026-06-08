# KÜNYE OKUMA PIPELINE v2 — DETAYLI TASARIM
**2026-06-08 · text-primary + VL-fallback + tiebreak merdiveni + KESİN KURAL**

---

## 0. AMAÇ & KIRMIZI ÇİZGİLER

**Amaç:** Her film/dizi künyesinden **Yönetmen + Yapımcı + Cast**'i, kontrol gerektirmeyen güvenle çıkarmak. Çıkaramadığında dürüstçe **Kontrol**'e ayırmak.

**Kırmızı çizgiler (hepsi bağlayıcı):**
1. **YANLIŞ > BOŞ** — emin değilsen yaz**ma**; yanlış yazmaktansa "okunamadı" de. (`feedback_unreadable_over_wrong`)
2. **OCR/jenerik OTORİTE** — isim kaynağı karelerdeki yazıdır. Web/KB **uydurmaz**, sadece **doğrular/eler/yazım düzeltir**. (`feedback_jenerik_otorite`)
3. **Halüsinasyon yasak** — metin tarafında her isim OCR token'ı olmalı; VL tarafında mutabakat+KB+self-consistency kalkanı.
4. **KESİN KURAL** — yönetmen/yapımcı/cast'te YALNIZ gerçek **"Ad Soyad"** (≥2 kelime, gerçek kişi). Tek-kelime/marka/logo/şirket/sıfat/rol-etiketi/garble **YOK**.

---

## 1. GENEL AKIŞ

```
┌────────────────────────────────────────────────────────────────────┐
│ AŞAMA 1 — METİN                                                     │
│  OneOCR+GLM (kunye.txt) → LLM rol-eşleme (gemma3:12b ∥ qwen3:8b,    │
│  think=False) → _guard → fuse → KB-crew-filtre → garble-kapısı →    │
│  self-consistency → KESİN KURAL süzgeci                             │
└───────────────┬────────────────────────────────────────────────────┘
                ▼
┌────────────────────────────────────────────────────────────────────┐
│ AŞAMA 2 — QC KAPISI                                                  │
│  yönetmen VAR + cast yeterli + temiz → ───────────► ONAYLI (text)   │
│  yönetmen YOK / cast<3 / garble-bayrak → VL RE-READ                 │
└───────────────┬────────────────────────────────────────────────────┘
                ▼ (sadece tetiklenirse, ~%40 film)
┌────────────────────────────────────────────────────────────────────┐
│ AŞAMA 3 — VL RE-READ (kareler, video-tag)                           │
│  qwen2.5vl:7b + gemma4:26b → her biri yön+cast, kendi cast'inden    │
│  geçen yönetmeni at (self-consistency)                              │
└───────────────┬────────────────────────────────────────────────────┘
                ▼
┌────────────────────────────────────────────────────────────────────┐
│ AŞAMA 4 — TIEBREAK MERDİVENİ (çelişkiyi ATMA, ÇÖZ)                   │
│  a) MUTABAKAT (iki VL aynı) → al                                    │
│  b) cross-cast: aday HERHANGİ cast'te (metin+VL) → BAŞROL → ele     │
│  c) KB-onay: kalanlar arasında IMDB-yönetmen → al                   │
│  d) [gelecek] film-özel KB (cast-match → bu filmin yönetmeni)       │
│  e) [gelecek] etiket-yakınlığı ("Directed by/A NAME FILM" kartı)    │
│  f) hiçbiri → PES                                                    │
└───────────────┬────────────────────────────────────────────────────┘
                ▼
┌────────────────────────────────────────────────────────────────────┐
│ AŞAMA 5 — MERGE & AUTHORITY                                          │
│  VL metnin BOŞ alanını DOLDURUR (text'in güvenle okuduğunu EZMEZ).  │
│  Final KESİN KURAL süzgecinden geçer.                               │
└───────────────┬────────────────────────────────────────────────────┘
                ▼
        çözüldü → ONAYLI        çözülemedi → KONTROL (dürüst)
```

---

## 2. AŞAMA 1 — METİN OKUMA (detay)

**Girdi:** `clip/ocr/ocr-<uuid>/kunye.txt` (OneOCR + GLM-OCR çıktısı). İsim kaynağı budur.

**a) LLM rol-eşleme** (`credit_text_read.read_credits_auto`)
- Model zinciri **ENSEMBLE**: `gemma3:12b` + `qwen3:8b` — ikisi de koşar (eski "ilk-dolu durur" KALDIRILDI).
- `qwen3:8b` için **think=False** (düşünme + `format=schema` çakışması → kapatıldı).
- Prompt (KESİN kurallarla):
  - **rule-0 (BİÇİM):** gerçek "Ad Soyad", tek-kelime/marka/sıfat yazma.
  - **rule-4 (yönetmen-etiket):** "DIRECTED BY", **"A <İSİM> FILM"**, "A FILM BY", YÖNETEN/REJİSÖR, UN FILM DE, REGIE… + assistant-director/DoP/art-director AYRIMI.
  - rule 2/3/5/6: karakter-oyuncu ayrımı, şirket/etiket eleme, crew≠oyuncu, yürütücü≠yapımcı.

**b) `_guard` (anti-halüsinasyon):** her ismin anlamlı token'ları OCR metninde olmalı; 1-4 kelime; `_JUNK_WORDS` (disclaimer/bağlaç/ajans) elenir.

**c) `_fuse_yonetmen` (ensemble birleştirme):**
- ≥2 modelde aynı → **MUTABAKAT** (yüksek güven)
- çelişki/tek → **KB-onaylı** (IMDB director) olanı al
- aksi → **ABSTAIN** ("DÜŞÜK tek-okuma" KALDIRILDI — tek-model onaysız yönetmeni ONAYLI'ya koymuyoruz)

**d) F2 — KB crew-filtresi (`imdb.duckdb`):** cast'ten KB'nin "oyunculuk içermeyen ekip" dediğini at (BEN BURTT=ses vb.). 0-kayıt → geçir (Türk/obskür olabilir).

**e) F3 — garble kapısı (`garble_audit.looks_garble` + near-dup):** fiil-eki/rol-kurum/fuzzy-rol-etiketi garble'ı at; garble-varyant (VAVIZ KARAKAC ≈ YAVUZ KARAKAŞ) → garble'ı düşür, temizi tut (diakritik + KB-güvenlik).

**f) self-consistency:** bir yönetmen adayını öneren model AYNI ismi kendi cast'ine de koyduysa → başrol → düş (Redford düşer, Cimino korunur).

**g) KESİN KURAL süzgeci (`_only_persons`):** yön/yap/cast'te yalnız geçerli "Ad Soyad" kalır (iki katman: prompt rule-0 + `_valid_person_name` blocklist).

---

## 3. AŞAMA 2 — QC KAPISI (detay)

**VL re-read TETİKLERİ** (biri yeterli):
- Yönetmen **BOŞ**, VEYA
- Cast sayısı **< 3** (oyuncuda soru), VEYA
- Garble-kapısı bayrak attı (şüpheli isim kaldı).

**Tetiklenmezse:** text-only → **ONAYLI** (hızlı yol, ~%60 film).
**Önemli:** Yanlış-ama-dolu metin yönetmenini ONAYLI'ya koymamak için Aşama 1'deki abstain (DÜŞÜK kaldırma) şart — yoksa QC "dolu" sanıp VL'yi atlar (Asi→"John Platt" deliği).

---

## 4. AŞAMA 3 — VL RE-READ (detay)

- Girdi: `frames/giris` + `frames/cikis` (baş+son örnekleme, ≤36 kare, `/api/chat` `images[]` = "video-tag").
- Modeller: **qwen2.5vl:7b** (hızlı ~35sn, yüksek recall, başrol-gürültüsü) + **gemma4:26b** (temiz, güvenli, ~70sn). *(qwen3-vl:30b PRATİK DEĞİL — tek film bitmiyor, 24GB sınırda.)*
- `num_ctx=40960` (36 kare ~37k token; 16384'te HTTP 400).
- `think=False` (video çoklu-kare şartı).
- Prompt: rule-0 + yönetmen-etiket kalıpları (metinle aynı).
- Her modelin yönetmeninden, **o modelin kendi cast'inde** geçeni at + KESİN KURAL süzgeci.

---

## 5. AŞAMA 4 — TIEBREAK MERDİVENİ (detay)

Sıra (her basamak çözerse dur):
1. **MUTABAKAT** — iki VL aynı ismi der → al. *(Gerçek oyuncu-yönetmen, ör. Eastwood, burada hayatta kalır.)*
2. **CROSS-CAST self-consistency** — mutabakat yoksa: aday **metin cast'i + iki VL cast'i** birleşiminde geçiyorsa = BAŞROL → **ele**. *(Waldo→Redford burada düşer.)*
3. **KB-onay** — kalan adaylar arasında IMDB'de yönetmen olan → al. *(Kar Kraliçesi: Gates'i seçer, Randall'ı eler.)*
4. **[GELECEK] film-özel KB** — OCR cast'iyle IMDB başlığını eşle → o **filmin** gerçek yönetmenini çek (genel-yönetmen yerine). KÖPRÜ-tarzı çapraz-kontrol; imdb şema gerektirir.
5. **[GELECEK] etiket-yakınlığı** — hangisi net "Directed by / A NAME FILM" kartının yanından okundu (pozisyon sinyali).
6. **PES** — hiçbiri ayıramıyorsa → **Kontrol** (gerçekten bilemiyoruz; doğru davranış).

---

## 6. AŞAMA 5-6 — MERGE, AUTHORITY, ROUTE

- **VL = gap-filler:** metnin **boş** yönetmenini doldurur; metnin **güvenle okuduğunu EZMEZ** (jenerik-otorite).
- Cast: OCR/metin otorite. VL cast'i (a) cross-cast self-consistency için, (b) [açık karar] metin cast<3 ise **eksiği tamamlamak** için kullanılabilir.
- Final tüm listeler **KESİN KURAL** süzgecinden geçer.
- **ROUTE:** yönetmen çözüldü + güvenli → **ONAYLI**; çözülemedi → **KONTROL**.

---

## 7. ELE ALINAN EDGE-CASE'LER
| Vaka | Tehlike | Çözüm |
|---|---|---|
| Waldo→Redford | oyuncu-yönetmen, KB-genel onaylıyor | cross-cast (Redford metin cast'inde) → ele |
| Cennetin→Cimino | model yanlışlıkla yönetmeni cast'e koymuş | self-consistency yalnız ÖNEREN modele bakar → korunur |
| Eastwood (kendi filmi) | gerçek oyuncu-yönetmen | MUTABAKAT'ta hayatta kalır |
| Kar Kraliçesi | qwen✓/gemma✗ çelişki | cross-cast + KB → Gates |
| Asi/Sessiz Ölüm | tek-model yanlış yönetmen | DÜŞÜK kaldırıldı → abstain → VL devralır |
| VAVIZ KARAKAC | garble-varyant OCR dup | garble near-dup → düşer |
| Warner Bros | marka cast/yönetmende | KESİN KURAL blocklist → düşer |
| Ağlıyorum/Waldo | ne metin ne VL okuyabiliyor | dürüstçe KONTROL |

---

## 8. MALİYET
- Metin: ~12sn/film (her film).
- VL: yalnız abstain'de (~%40) — qwen2.5vl ~35sn + gemma4 ~70sn.
- Amortismanlı: ~25sn/film ek. ASR (asıl yük, saatler) yanında ihmal edilebilir.

---

## 9. UYGULAMA DURUMU
| Bileşen | Durum |
|---|---|
| Metin: ensemble, think=False, prompt rule-0/4, fuse(abstain), KB-crew, garble, self-consistency, KESİN KURAL | **KODLANDI** `scripts/credit_text_read.py` (production, **COMMIT'SİZ**) |
| VL-fallback akışı + tiebreak merdiveni (mutabakat→cross-cast→KB) | **SADECE TEST** `outputs/pipeline_v2_test.py` (production'a bağlı DEĞİL) |
| Film-özel KB (cast-match) | **YOK** (gelecek rung) |
| Etiket-yakınlığı | **YOK** (gelecek rung) |
| Production'a VL-fallback wiring (`mitas_pipeline`) | **YAPILMADI** (Çağatay onayı bekliyor — VLM revival) |

---

## 10. KARARLAR — KİLİTLENDİ (2026-06-09)
1. **VL-fallback production'a BAĞLANACAK** (= tasarımı uygula; 2026-06-08 "VLM yok" kararı kalkanlı biçimde gözden geçirildi). ✅
2. **Yapımcı: SADECE KİŞİ** — kurum/marka/logo YOK (KESİN KURAL'a tabi; Türk Silahlı Kuvvetleri gibi kurumsal yapımcı listeye girmez). ✅
3. **Cast VL-supplement: EVET** — metin cast<3 ise VL cast'i eksiği tamamlar (KESİN KURAL + cross-cast süzgecinden geçerek). ✅
4. **VL = 2 MODEL** (qwen2.5vl + gemma4, mutabakat). ✅
5. **Dizi vs film:** sonra netleştirilecek (dizide tam-kadro hedefi/cap farkı).
6. **Film-özel KB & etiket-yakınlığı (rung d/e):** sonra — bonus pozitif-teyit; cross-cast+KB gözlenen delikleri zaten kapatıyor.
```
