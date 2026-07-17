# MİTAS — KÜNYE DÜZELTME: KANUN, KURAL ve GÖREV (TAM DETAY)

> Bu doküman, künye PDF düzeltme işinin **tek ve eksiksiz** referansıdır.
> Başka bir oturumda Opus'a bu doküman + corrections araçları verilir → iş **sıfırdan,
> bağlam olmadan, hatasız** yapılabilir. Her kanun, her kural, her tuzak, her araç, ve
> 2026-06-15'te yapılan işin tam kaydı burada.
>
> **Önceki rehberi (PDF_DUZELTME_REHBERI_OPUS.md) KAPSAR ve GÜNCELLER.** Çelişki olursa
> BU doküman geçerlidir. Yazıldığı tarih: 2026-06-15 · Platform: Windows 10, PowerShell · Repo: `E:\MITAS`

---

## 0. TL;DR — 60 SANİYELİK ÖZET

MİTAS, TRT film arşivini işleyip her film için bir **künye PDF** üretir (yönetmen, oyuncular,
yapımcı, özet, tür, ses/altyazı, afiş, anahtar sözcükler). Pipeline'ın OCR'ı bazen **çöp (garble)**
okur, bazen **yanlış filme** karar verir. Görev: ONAYLI teslim klasöründeki her PDF'i tek tek
incelemek, hataları web-doğrulamayla düzeltmek, ve **5 bağımsız vektörle** doğrulamak.

**EN BÜYÜK DERS (2026-06-15):** Deterministik metin-kontrolü TEK BAŞINA YETMEZ. Üç hata sınıfı
yalnızca **görsel afiş taraması** ve **yönetmen-çapası denetimi** ile yakalandı:
yanlış-film kimliği, yanlış afiş, kısmi-ASCII/meta özet. "Bitti" demeden önce **5 vektör de** koşmalı.

---

## 1. KANUNLAR (ÇİĞNENEMEZ — ÖNCE BUNLAR)

### KANUN 1 — GARBLE = ÇÖP = SİL VE DEĞİŞTİR
OCR'ın okuduğu **gerçek isim değil de çöpse** (garble), silip web-gerçeğiyle değiştir SERBESTTİR.
Garble örnekleri: `A NOVEL BY`, `IN FOUR VOLUMES`, `LIGHIING SENIOR ARTISTS`, `PROJE KOOROINATORD`,
`SN. OMER AHUNEAY`, `KOMUTAN / COMMANDER`, `DANS LE ROLE DE` (Fr. rol etiketi), `SOUND CHARLES TOMARAS`,
`VERY SPECİAL THANKS`, `İN COPRODUZİONE CON` (İt. jenerik), `EFFECTS EDİTER`, bozuk harf (`Ï`, `ÏÏ`),
4+ kelimelik birleşik cümle, rakam içeren satır.

### KANUN 2 — OCR OTORİTE (gerçek isimi web EZEMEZ)
OCR'ın okuduğu **geçerli, gerçek isimse**, web onu **EZEMEZ**. Web sadece: boş-doldurur,
**yazımı düzeltir** (`YILMAZ ERDOGAN`→`YILMAZ ERDOĞAN`), eksiği tamamlar. **"Ahmet okuyup Mehmet
yazmak" YASAK.** (Garble bu korumadan muaf — KANUN 1.)

### KANUN 3 — YÖNETMEN = KİMLİK ÇAPASI ★ (2026-06-15, EN KRİTİK YENİ KANUN)
**Yönetmen filmin kimliğini belirleyen en güçlü tek alandır** (film başına tek + kesin; aynı-başlık
tuzağına karşı en güçlü kilit). Kural:
- OCR **geçerli** bir yönetmen okuduysa → o **KİLİT**. Ajan yalnız **yazımı/casing'i** düzeltir,
  **kişiyi DEĞİŞTİREMEZ.**
- Ajanın araştırması **farklı yönetmene** işaret ediyorsa → **KIRMIZI BAYRAK** (büyük olasılık
  same-title tuzağı). **SESSİZ override YASAK** → insan onayı / güçlü çapraz-kanıt şart.
- Yönetmen OCR'da garble/yoksa → web'den doldurulabilir (çapa yok).
- **NEDEN:** Bu kanun olmadığı için ajanlar 2 filmi yanlış-filme bağladı (MUCİZE → 7. Koğuştaki
  Mucize; GÖLGE SAVAŞÇI → Zhang Yimou'nun Shadow'u). Oyuncu+başlıktan türetip OCR-yönetmenini ezdiler.

### KANUN 4 — TÜM-OCR-KANITI (Yönetmen tek başına değil) ★ (2026-06-15, NİNNİ dersi)
Kimlik **tek sinyalle** belirlenmez. OCR'ın **bütün kanıtı** (yönetmen + cast + başlık + konu)
**birlikte** tartılır. Tek bir OCR alanı (yönetmen-satırı) garble olabilirken diğerleri temiz olabilir.
- **NEDEN:** NİNNİ'de OCR yönetmen-satırı="JUANMA BAJO ULLOA" (yanlış okuma) ama OCR cast="LAIA COSTA"
  + başlık literal "CINCO LOBITOS" + konu "Amaya yeni anne" → film **Cinco lobitos**. Audit'i körü
  körüne takip eden verify-ajanı OCR-yönetmenine güvenip DOĞRU filmi "Baby (2020)"ye çevirip **BOZDU**.
  Sadece afiş-görsel ("Lullaby" posteri) + OCR-cast yakaladı.
- **UYGULAMA:** Her kimlik-değişimi (audit-fix dahil) afiş-görsel + OCR-cast çapraz-kontrolüyle
  doğrulanmadan KESİNLEŞMEZ.

### KANUN 5 — AFİŞ GÖRSEL-SWEEP ŞART ★ (2026-06-15)
Metin kontrolleri afişi **HİÇ görmez**. Yanlış afiş (yanlış-film posteri, frame-grab, jenerik
portre) yalnızca **gözle** yakalanır. Teslimden önce **TÜM afişler** montaj-ızgaraya dökülüp
gözle taranmalı. (Afiş çoğu zaman orijinal pipeline'dan **korunan** afiştir; has_poster=True diye
yeniden çekilmez → yanlış afiş gizli kalır.)

### KANUN 6 — KONTROLÜ KAYBETME, GÖZÜNLE DOĞRULA
İş bittiğinde "tamam" demeden önce **kendin aç-gör-doğrula**. Tek örnekle "hazır" deme; çeşitli
sette sürekli ölç. **Deterministik triage TEK BAŞINA "bitti" demek için yeterli DEĞİLDİR.**

### KANUN 7 — EKSİK NORMAL, UYDURMA YASAK
Bilgi yoksa boş bırak (oyuncu "—", yapımcı "—"). Asla uydurma. (Sovyet stüdyo filmi → yapımcı yok = normal.)
Kimlik çözülemezse → identity_ok=false → KONTROL'e bırak / kullanıcıya bildir, zorla doldurma.

---

## 2. SİSTEM HARİTASI (YOLLAR — EZBERLE)

```
E:\MITAS\                                  ← repo kökü, working dir
├── Database\{AD} {TRT}\                    ← her filmin hub'ı
│   ├── _DURUM.json                          ← pipeline karar/neden/meta (resolution, duration, fps, ana_dil)
│   └── pdf\
│       ├── kunye_teslim.md                  ← BASELINE (cast/yön/yap/özet/ses kanalları/ana_dil/altyazı)
│       ├── kunye.pdf  /  kunye_fixed.pdf    ← pipeline / düzeltme çıktısı
│       ├── kunye_fixed_onizleme.png         ← önizleme görseli
│       └── afis.jpg                          ← afiş kaynağı (varsa)
│
├── Mitas Output\export\
│   ├── ONAYLI\                              ← TESLİM KLASÖRÜ (hem '... ONAYLI.pdf' hem '... SESTEYIT_onaylı.pdf')
│   ├── SES_TEYIT\ , KONTROL\ , SORUNLU\     ← pipeline'ın diğer kademeleri
│   ├── müzikal+animasyon\                   ← TÜR=MÜZİKAL/ANİMASYON ayrılanlar (teslime girmez)
│   ├── _ONAYLI_yedek\                       ← in-place düzeltme öncesi orijinal yedekleri
│   └── _KONTROL_orijinal_yedek\             ← promote öncesi yedek
│
├── outputs\kunye_fix\                       ← ★ DÜZELTME MUTFAĞI (burada çalış)
│   ├── fix_kunye.py                          ← render motoru (tek film build+render+promote)
│   ├── render_in_place.py                    ← ★ YERİNDE overwrite (promote DEĞİL) — 2026-06-15
│   ├── _triage_onayli.py                     ← tüm ONAYLI'yı tara/bayrakla (deterministik)
│   ├── _prep_render.py                       ← corr_new → render corrections + afiş/genre mantığı
│   ├── _director_audit.py                    ← ★ OCR-yönetmen vs final-yönetmen (kimlik çapası kapısı)
│   ├── _poster_montage.py                    ← ★ tüm afişleri montaj-ızgaraya dök (görsel sweep)
│   ├── _find_muzikal_anim.py                 ← TÜR=MÜZİKAL/ANİMASYON bul+taşı
│   ├── _versiyon_check.py                    ← duplikat/versiyon tespiti
│   ├── _poster_audit.py                      ← afiş kaynağı denetimi + gömülü-afiş çıkarma
│   ├── corr_new\{trt}.json                   ← ★ AJANLARIN yazdığı araştırma sonucu (kimlik/cast/crew/özet/imdb)
│   └── corr_new\_in\{trt}.json               ← ajan girdisi (mevcut OCR ham verisi: yon/cast/ozet)
│
├── _102_ozet_prompt_v2.md                   ← özet yazma kuralları (referans)
├── MITAS_KUNYE_KURALLARI.md                 ← v4 kesin kurallar (referans)
├── scripts\tek_film_kunye.py                ← parse_teslim_md, ozet_v4, up_o, _split_dedup_names
└── OCR-worktree\pdf-mitas\
    ├── _make_pdf.py                           ← mp.build(out_pdf, d) — PDF çizici
    ├── name_normalize.py                      ← tr_upper / upper_names / tr_upper_prose / ascii_fold
    └── poster_fetch.py                        ← afiş çekici (imdb_id/tmdb_id/title)
```

### PYTHON YORUMLAYICISI — ÇOK ÖNEMLİ
Tüm `outputs\kunye_fix\` araçları **GLOBAL Python 3.10** ile koşar (reportlab/fitz/PIL orada). **venv KULLANMA.**
```powershell
$py = "C:\Users\TRT03\AppData\Local\Programs\Python\Python310\python.exe"
Set-Location "E:\MITAS\outputs\kunye_fix"
& $py render_in_place.py --in <corrections.json>
```

---

## 3. KADEME SİSTEMİ ve İN-PLACE FELSEFESİ

- Pipeline filmleri 4 klasöre düşürür: ONAYLI (TR ses+temiz) / SES_TEYIT (yabancı ses) / KONTROL / SORUNLU.
- **AMA kullanıcı tüm onaylı teslimatları TEK klasörde (ONAYLI) topladı** — hem `... ONAYLI.pdf` (TR)
  hem `... SESTEYIT_onaylı.pdf` (yabancı-ses ama onaylanmış). Bu klasör = **teslim seti.**
- **KURAL: ONAYLI'daki dosyalar YERİNDE düzeltilir (promote DEĞİL).** `fix_kunye.py --promote` tier'e
  göre dosyayı SES_TEYIT klasörüne **TAŞIR** → kullanıcının topladığı klasörü bozar. Bunun yerine
  **`render_in_place.py`** kullan: aynı dosya adına overwrite eder, `_ONAYLI_yedek`'e yedekler, taşımaz.
- ana_dil bilgisi künyenin SES&ALTYAZI bloğunda gösterilir (baseline'dan). TR-dublaj filmler ana_dil=TR
  (ONAYLI suffix), yabancı-ses ana_dil=EN/JA/ES… (SESTEYIT suffix). Bu in-place'te korunur.

---

## 4. ÇEKİRDEK ARAÇLAR — TAM DAVRANIŞ

### 4.1 `fix_kunye.py` (render motoru)
- Buggy OCR cross-check'i ATLAR; cast/yön/yap/tür/afiş/özet'i **web-doğrulanmış corrections JSON**'undan alır.
- `tek_film_kunye.py` ile AYNI zincir: isim kasası + `ozet_v4` + `poster_fetch` + `mp.build`.
- **Kritik davranışlar:**
  - `keywords=" ; ".join(castU)` → **ANAHTAR SÖZCÜKLER, cast'ten OTOMATİK üretilir** (fix_kunye.py:262).
    Cast'i düzeltince anahtar sözcükler **otomatik senkron**. Ayrı verme.
  - corrections'tan gelen isimlere `nn.tr_upper` uygulanır (Türkçe İ/Ş/Ğ korunur; upper_names'in
    ASCII-fold bug'ı bypass edilir).
  - **BOŞ cast/yön/yap verirsen → MD baseline'a düşer** (garble geri gelir). Tamamen boşaltmak için
    hub MD'sini elle temizle (CASANOVA örneği).
- `--promote` tier'e göre taşır → ONAYLI in-place işinde **KULLANMA**.

### 4.2 `render_in_place.py` ★ (2026-06-15, yeni)
- corrections dizisini alır; her filmi render edip **ONAYLI'daki MEVCUT dosyanın üzerine yazar**
  (klasör taşıma YOK). Orijinali bir kez `_ONAYLI_yedek`'e yedekler.
- Aynı tam-TRT birden çok dosyaysa (ONAYLI+SESTEYIT) ikisini de aynı içerikle overwrite eder.
```powershell
& $py render_in_place.py --in _render_corr.json
& $py render_in_place.py --in _render_corr.json --no-poster   # ağ-fetch atla (hızlı)
```

### 4.3 `_triage_onayli.py` (deterministik tarayıcı)
- Tüm ONAYLI PDF'lerini fitz ile tarar; cast/yön/yap/özet/afiş çıkarır; bayraklar:
  CAST_GARBLE, YAP_GARBLE, YON_GARBLE, *_BOS, KW_CAST_MISMATCH, OZET_TARIH_GIRIS, OZET_KISA, AFIS_YOK.
- Çıktı: `_triage_onayli.json` (her filmin tam içeriği + ozet_full) + konsol özeti.
- **KISITI:** Heuristik kabadır → yanlış-pozitif verir (tek-harf token "WILLARD E PUGH", 4-kelime
  gerçek isim "JUAN DE DIOS LARRAIN", cümle-ortası "YILLARINDA"). Ve ince hatayı (kısmi-ASCII,
  meta-açılış, yanlış-film, yanlış-afiş) **HİÇ yakalamaz.** Sadece kaba ön-eleme.

### 4.4 `_prep_render.py`
- `corr_new\*.json` (ajan sonuçları) → `_render_corr.json` (render corrections):
  - genre **canonicalize** (ASCII "SUC"/"AKSIYON" → "SUÇ"/"AKSİYON"; fold-tabanlı eşleme).
  - afiş mantığı: afiş varsa **koru** (poster alanı yok), yoksa imdb/tmdb'den çek, force_poster/poster_none flag'leri.
  - identity_ok=false + cast-boş → **ATLA** (skip).
  - **cast-saptı** (mevcut gerçek isim varken cast ortak=0) → BAYRAKLA (inceleme).
  - **ozet-ASCII-şüphe** (Türkçe harf YOK) → BAYRAKLA. *(Not: kısmi-ASCII'yi (ç var ama İ yok)
    yakalamaz — reading-QC şart.)*

### 4.5 `_director_audit.py` ★ (2026-06-15, kimlik çapası kapısı)
- Her film: `_in\{trt}.json` (ham OCR yönetmen) vs `corr_new\{trt}.json` (final yönetmen) fold-karşılaştırma.
- **Aksan-fold** (É→E, Ž→Z, NFKD) ile aksan-farkı false-positive'leri eler.
- OCR'da **gerçek isim** varken final'de yoksa = yönetmen-ezme = **inceleme noktası**.
- **Her künye-toplu-işinde STANDART koşulur.** Çıkan her uyuşmazlık adversarial doğrulanır
  (TÜM-OCR-KANITI ile — KANUN 4).

### 4.6 `_poster_montage.py` ★ (2026-06-15, görsel sweep)
- Tüm ONAYLI PDF'lerinin gömülü afişini çıkarıp ~30'arlı **montaj-ızgaralara** dizer
  (`_poster_montaj\montaj_N.png`). Afiş yoksa kırmızı "AFİŞ YOK".
- İnsan/Opus **her montaja gözle bakar**: afiş↔başlık uyumu, yanlış-film posteri, frame-grab var mı.

### 4.7 Diğer
- `_find_muzikal_anim.py --apply` → TÜR=MÜZİKAL/ANİMASYON filmleri `müzikal+animasyon\`'a taşır.
- `_versiyon_check.py` → aynı tam-TRT çok-dosya (duplikat) / aynı temel-TRT farklı versiyon / aynı başlık farklı TRT.
- `_poster_audit.py --apply` → afiş kaynağı denetimi; gömülü-sadece afişleri hub'a çıkarır (koruma).

---

## 5. CORRECTIONS JSON FORMATI (corr_new\{trt}.json)

```json
{
  "trt_id": "2017-1169-1-0000-50-0",
  "resolved_title": "MUCİZE", "year": "2015",
  "imdb_id": "tt3138782", "tmdb_id": "321050",
  "confidence": "high|med|low", "evidence": "bu filmi benzersiz doğrulayan kanıt",
  "director": ["MAHSUN KIRMIZIGÜL"],          // FINAL BÜYÜK HARF, KİLİT (KANUN 3)
  "cast": ["...≤8 FINAL BÜYÜK HARF..."],
  "producers": ["...≤3, exec/co/line HARİÇ..."],
  "genre": ["DRAM","TARİH"],                   // izinli listeden ≤2
  "original_title": "Mucize",
  "ozet": "...DOĞAL TÜRKÇE, küçük harf...",     // render uppercase'ler — Bölüm 7
  "ozet_action": "kept|rewritten",
  "force_poster": true,                         // afiş zorla yeniden-çek
  "poster_none": true,                          // afiş YOK = kaldır (yanlış afiş yerine afişsiz)
  "poster_maybe_wrong": false,
  "identity_ok": true,                          // false → render'da atlanır
  "notes": "ne değiştirildi, neden; belirsizlik"
}
```
İzinli TÜR: DRAM, KOMEDİ, KORKU, GERİLİM, AKSİYON, MACERA, BİLİM KURGU, ANİMASYON, WESTERN, ROMANTİK,
SUÇ, POLİSİYE, SAVAŞ, TARİH, BİYOGRAFİ, MÜZİKAL, FANTASTİK, GİZEM, AİLE, BELGESEL, DOĞA, SPOR, KISA.
(MÜZİKAL/ANİMASYON → teslime girmez, ayrı klasör.)

---

## 6. İSİM / CASING KURALLARI (çok detay — birebir uy)

### İSİMLER (cast / yönetmen / yapımcı) → **FINAL BÜYÜK HARF** ver
- **YABANCI ad** → SAF ASCII BÜYÜK: aksanlar düşer (é→E, ñ→N, ø→O, ž→Z), nokta-i değil düz **I**.
  Örn: Christopher→CHRISTOPHER, José→JOSE, Bruce Willis→BRUCE WILLIS, Hélène→HELENE.
- **TÜRK adı** (gerçekten Türk) → Türkçe büyük: i→İ, ı→I, ç ğ ö ş ü KORUNUR.
  Örn: Yılmaz Erdoğan→YILMAZ ERDOĞAN, Kıvanç Tatlıtuğ→KIVANÇ TATLITUĞ.
- **NEDEN final-büyük:** `fix_kunye` corrections isimlerine `nn.tr_upper` uygular. tr_upper
  (name_normalize.py:171) = `s.replace("ı","I").replace("i","İ").upper()`. Zaten-büyük-harf
  **idempotent** ("CHRISTOPHER"→"CHRISTOPHER"); ama küçük harf verirsen "Christopher"→"CHRİSTOPHER"
  (yabancıda yanlış İ). Bu yüzden isimleri ZATEN doğru büyük harf ver.

### ÖZET → **DOĞAL TÜRKÇE (küçük harf, ç/ğ/ı/ö/ş/ü ŞART)** yaz
- `fix_kunye` özete `ozet_v4` → `nn.tr_upper_prose(text, names)` uygular: gövdeyi Türkçe-büyük yapar
  (i→İ doğru), cast listesindeki yabancı isimleri ASCII bırakır.
- **Doğal Türkçe yazarsan** ("hapishaneden kaçıp") → render "HAPİSHANEDEN KAÇIP" (İ doğru).
- **Büyük-harf-ASCII yazarsan** ("HAPISHANEDEN") → tr_upper_prose idempotent kalır → BOZUK ("HAPISHANEDEN").
- ⚠️ **AJANLAR "güvenli olsun diye" ASCII-katlama EĞİLİMİNDE** → prompt'ta "gerçek Türkçe harfleri
  ç ğ ı i ö ş ü KULLAN, ASCII-fold YASAK" vurgusu ŞART. *(2026-06-15: 5+ ajan özeti ASCII-katladı.)*
- **Mevcut iyi özet KORUNUR** (verbatim, zaten doğru büyük harf, idempotent); sadece bozuk/tarih-girişli/
  meta olanlar yeniden yazılır.

---

## 7. ÖZET KURALLARI (TAVİZSİZ)

1. **DİL & UZUNLUK:** Türkçe, tek paragraf, **4 cümle, 40–65 kelime.**
2. **CASING:** Bölüm 6 (doğal Türkçe yaz, render uppercase'ler; yabancı isim ASCII).
3. **AÇILIŞ — İKİ YASAK:**
   - ❌ **TARİH/ÇAĞ girişi:** "1959 yılında geçen bu filmde...", "1940'larda...", "18. yüzyılda...",
     "Seul, 1994." → **YASAK.** Konuyla/karakterle DİREKT başla.
   - ❌ **META girişi:** "Christopher Nolan'ın filmi...", "Matteo Garrone'nin yönettiği İtalyan yapımı dram..."
     → **YASAK.** Olay-örgüsünü anlat, filmi/yönetmeni tarif etme.
   - ✓ Tarih cümle-ortasında olabilir; sadece **açılış** tarih/meta olmamalı.
4. **FİNAL:** Açık **SPOILER** (kim ölür/kazanır/barışır). Muğlak/temalı final OLMAZ.
5. **YASAK:** soru, ünlem, tırnak, köşeli parantez, klişe ("hayatı değişir", "kendini bulur"),
   karakter-listesi, ASCII-katlama, telgraf-üslubu, kesik/yarım anlatım.

**İyi örnek (HAYDUT/Bandits, doğal Türkçe → render uppercase):**
> Joe Blake ve Terry Collins, hapishaneden kaçıp banka müdürlerinin evlerinde geceleyerek soygunlar
> düzenleyen uykucu haydutlar olarak ün kazanır. ... Son soygunlarında sahte ölümlerini sahneleyip
> ödülü toplar ve Meksika'ya kaçarak yeni bir hayata başlarlar.

---

## 8. AFİŞ KURALLARI

1. **Koru-öncelik:** Film doğru afişe sahipse koru. `_prep_render` has_poster=True ise poster alanı
   vermez → mevcut korunur.
2. **Eksikse çek:** has_poster=False → ajan **imdb_id/tmdb_id** sağlar → `poster:{fetch:true, tmdb_id}`.
   Yanlış-film tuzağını kırmak için **id ile** çek (başlık-aramasıyla değil).
3. **AFİŞ KAPISI:** Gerçek afiş PORTRE'dir (w<h, >5KB). Yatay/kare = frame-grab/backdrop → REDDEDİLİR.
4. **Yanlış afiş = afişsizden kötü:** Yanlış-film posteri tespit edilirse `poster_none:true` → kaldır.
   (Kısa filmlerde gerçek afiş olmayabilir → afişsiz bırak.)
5. ★ **GÖRSEL SWEEP ŞART (KANUN 5):** `_poster_montage.py` → tüm afişleri gözle tara. Çoğu yanlış afiş
   **orijinal pipeline'dan korunan** afiştir (has_poster=True diye yeniden çekilmez) → metin kontrolleri
   görmez, sadece göz görür. Aynı-Türkçe-başlık tuzağı buradan sızar.

---

## 9. KİMLİK DOĞRULAMA PROTOKOLÜ (en kritik)

Yanlış-film hataları (same-title tuzağı) en sinsi ve en zararlı sınıftır. İki kapı:

### 9.1 Yönetmen-çapası audit (`_director_audit.py`)
- Her künye-işinin sonunda koş. OCR-yönetmen ≠ final-yönetmen olan **her** filmi listele (aksan-fold ile).
- Her uyuşmazlığı **adversarial doğrula** (Bölüm 11), **TÜM-OCR-KANITI** ile (KANUN 4): OCR'ın
  cast+başlık+konu'su hangi filme işaret ediyor?
  - OCR-yönetmeni geçerli + final farklı → büyük olasılık yanlış-film → **OCR'a göre düzelt.**
  - OCR-yönetmeni garble/oyuncu/başlık → ajanın web-yönetmeni muhtemelen doğru → **doğrula, bırak.**

### 9.2 Afiş görsel-sweep (`_poster_montage.py`)
- Yanlış-film genelde yanlış-afiş ile gelir (afiş, kimliğe göre çekilir). Görsel sweep ikinci kapı.

> **2026-06-15 bulunan yanlış-film hataları:** MUCİZE (→7. Koğuştaki Mucize sanılmış, gerçek Mucize 2015),
> GÖLGE SAVAŞÇI (→Zhang Yimou Shadow sanılmış, gerçek Kagemusha 1980). İkisi de afiş-sweep + yönetmen-audit
> ile yakalandı; metin-triage ve reading-QC ikisini de KAÇIRDI.

---

## 10. BİLİNEN TUZAKLAR (HER BİRİNE DİKKAT)

1. **DeepSeek HTTP 402** — isim-kasası DB-miss'te API'ye sorar, anahtar ölü; zararsız, render biter.
   `run_batch.py`/`render_in_place` env'leri siler.
2. **Ü/Ö ASCII düşme** — corrections isimleri `tr_upper` ile gelir (Türkçe korunur). Yine de render
   sonrası fitz-kontrol: "OZTURK" görürsen JSON'da "ÖZTÜRK" mü bak.
3. **MD özeti PLACEHOLDER** — `kunye_teslim.md`'nin `## Özet` çoğu filmde "(ÖZET AYRI ADIMDA…)";
   `parse_teslim_md`/`ozet_v4` reddeder. Özeti SEN web'den üret.
4. **fitz 2-sütun okuma artefaktı** — özet bazen yapımcıdan SONRA okunur; PDF doğru, fitz sıra sorunu.
   `get_text("blocks")` + başlık-regex kullan.
5. **Re-render özeti KAYBEDER** — corrections'a `ozet` HER ZAMAN koy (yoksa MD placeholder → "—").
6. **Kısa garble denetimden kaçar** — <4 kelimelik garble (yönetmen `JBURÏÏN BİLDİK`) heuristiği geçer.
7. **BOŞ cast → MD baseline garble'ı geri gelir** — tamamen boşaltmak için hub MD'sini elle temizle.
8. ★ **Ajan ASCII-fold özeti** — "güvenli" diye Türkçe harfleri atar; kısmi-ASCII (ç var, İ yok)
   deterministik kontrolü geçer → reading-QC şart.
9. ★ **Ajan yanlış-filme karar verir** — same-title + ortak-oyuncu tuzağı; OCR-yönetmenini ezer (KANUN 3/4).
10. ★ **Yanlış afiş korunur** — has_poster=True diye yeniden çekilmez; görsel-sweep şart (KANUN 5).
11. ★ **Audit-fix yeni hata üretebilir** — verify-ajanı tek sinyale (OCR-yönetmen) güvenip doğru filmi
    bozabilir (NİNNİ). Her fix afiş+OCR-cast ile çapraz-kontrol.
12. **Server rate-limit** — 16-eşzamanlı ajan "Server is temporarily limiting requests" verir
    (kullanım-limiti DEĞİL); workflow'da **chunk=5 sıralı** koş.
13. **Bayat tarayıcı/working-tree** — düzeltme görünmüyorsa fitz ile diskten oku, mtime'a bak.
14. **Canlı pipeline eşzamanlı** — `mitas_pipeline.py` arşivden YENİ film işliyor olabilir; araştırma
    web-only (çakışma yok), render kısa pencere (kontrollü). Render öncesi taze re-triage.

---

## 11. İŞ AKIŞI (UÇTAN UCA — STANDART GÖREV)

### Aşama 0 — Hazırlık
1. `_triage_onayli.py` → tüm ONAYLI'yı tara, kategorize et, durumu anla.
2. `_poster_audit.py --apply` → gömülü-afişleri hub'a çıkar (koruma).
3. Canlı pipeline çalışıyor mu kontrol et (çakışma riski).

### Aşama 1 — Araştırma (paralel ajanlar, dosyaya dokunmaz)
4. Her film için bir ajan (Workflow, **chunk=5** rate-limit için): `_in\{trt}.json` (mevcut OCR) okur,
   web-doğrular, `corr_new\{trt}.json` yazar. Ajan prompt'u ŞUNLARI içermeli:
   - KANUN 1-7 (garble-sil, OCR-otorite, **YÖNETMEN ÇAPASI**, TÜM-OCR-KANITI, casing, özet kuralları).
   - İsimler FINAL BÜYÜK; özet DOĞAL TÜRKÇE (ASCII-fold YASAK).
   - imdb_id/tmdb_id sağla (afiş için).
   - Kimlik belirsizse identity_ok=false (uydurma yok).

### Aşama 2 — Render (deterministik, sen)
5. `_prep_render.py` → `_render_corr.json` (genre canon, afiş mantığı, skip/flag).
6. Kısmi-ASCII özet kontrolü + 5 ASCII-özeti düzelt (gerekirse ajan).
7. `render_in_place.py --in _render_corr.json` → ONAYLI'yı yerinde düzelt (yedekli).

### Aşama 3 — 5-VEKTÖRLÜ DOĞRULAMA (KANUN 6 — hepsi şart)
8. **Vektör 1 — Deterministik triage** (`_triage_onayli.py`): garble/casing/keyword/tarih-girişi/eksik.
9. **Vektör 2 — Adversarial cast-doğrulama:** cast-saptı (ortak=0) filmleri bağımsız web-kontrol
   (halüsinasyon avı). Her cast gerçekten o filmde mi?
10. **Vektör 3 — Reading-QC** (3-5 Sonnet ajanı, TÜM filmler): prozayı yargıyla oku — kısmi-ASCII,
    meta-açılış, kesik özet, yanlış-dil, garble. *(Deterministik kontrolün KÖR olduğu sınıf.)*
11. **Vektör 4 — Afiş görsel-sweep** (`_poster_montage.py` + gözle): yanlış-film posteri / frame-grab.
12. **Vektör 5 — Yönetmen-çapası audit** (`_director_audit.py` + adversarial): yanlış-film kimliği.
13. Her vektörde çıkanı düzelt → ilgili filmleri re-render → re-doğrula.

### Aşama 4 — Temizlik
14. Müzikal/animasyon ayır (`_find_muzikal_anim.py --apply`).
15. Duplikat/versiyon (`_versiyon_check.py`): aynı film tekrarını tek'e indir; versiyon-çiftleri tutarlı mı.
16. Kimliği çözülemeyen (identity_ok=false) filmleri kullanıcıya bildir (sil/KONTROL/elle).

### Aşama 5 — Teslim
17. Kalibreli, **dürüst** durum raporu (her vektörün sonucu + kalan risk). "Bitti" demeden 5 vektör de koşmuş olmalı.

---

## 12. 2026-06-15 YAPILAN İŞİN TAM KAYDI (ne düzeltildi, ne bakıldı)

**Başlangıç:** ONAYLI = 171 PDF. Pipeline o gün yeniden render etmiş, garble mevcut (CASANOVA kanıtı).
**Bitiş:** ONAYLI = **161 PDF teslim edildi.**

### Yapılan işlemler (sırayla)
1. **Triage** (171 PDF): 80 heuristik-temiz, 91 bayraklı. Casing/keyword mekaniği çözüldü
   (keywords=cast otomatik; tr_upper idempotent; özet doğal-Türkçe).
2. **Afiş koruma:** 90 hub + 52 cache + 11 gömülü-çıkarıldı = 153 korundu; ~16 eksik.
3. **`render_in_place.py` yazıldı** (promote değil, yerinde overwrite — kullanıcının topladığı klasör korunur).
4. **Pilot 2/2:** HAYDUT (garble cast→Bruce Willis/Cate Blanchett; yapımcı exec ayıklandı),
   İÇ İŞLERİ 2 (tarih-girişi "1991 yılları…"→"Genç polis Lau…"). Metin+görsel doğrulandı.
5. **Araştırma workflow:** 167 ajan (chunk=5; 16-eşzamanlı rate-limit'e takıldı). 166 ok + 1 re-run.
   corr_new\ yazıldı. Ajanlar: garble-sil, gerçek-isim-koru, imdb/tmdb sağla.
6. **ASCII-özet düzeltme:** ajanlar Türkçe harf atlamış → 5 özet (ÇİT, KLONDİKE, LUNANA, JACKIE,
   GELECEĞİN SAVAŞI) Türkçe'ye düzeltildi.
7. **Genre canon:** "SUC"/"AKSIYON"→"SUÇ"/"AKSİYON" (deterministik).
8. **Batch render-in-place:** 166/166 ok.
9. **Re-triage:** 159 temiz, 11 bayraklı → 10 heuristik yanlış-pozitif (gerçek isim/meşru-boş) + CASANOVA.
10. **Adversarial cast-doğrulama (17 cast-saptı):** 17/17 OK, sıfır halüsinasyon (Mudbound, Hive,
    Mandela, MİNARİ, BARS, ARAMA MOTORU… hepsi gerçek kadro; "JOHN Y" gerçek isim çıktı).
11. **Reading-QC (5 Sonnet, tüm filmler):** 10 gerçek kusur:
    - 4 kısmi-ASCII özet (AŞK ŞİMDİ, KAPTAN FANTASTİK, TERMİNATÖR, SAĞ SAĞLİM 2)
    - 2 meta-açılış (DUNKIRK "Christopher Nolan'ın filmi…", KAPTAN BENİM "Matteo Garrone'nin yönettiği…")
    - 1 kesik özet (YAŞAMIN KIYISINDA = Manchester by the Sea, tam yazıldı)
    - 2 typo (RÜZGARA "FEDAA"→"FEDA", JOHNY→JOHNNY GUITAR başlık)
    - BEYAZ BALON cast yazımı (ANNA BORKOWSKA gerçek çıktı, yanlış-alarm)
12. **CASANOVA:** kimlik çözülemedi (65dk Casanova belgeseli, web'de tekil eşleşme yok) → garble
    temizlendi (hub MD elle düzeltildi) → kullanıcı "sil" dedi → ONAYLI'dan silindi.
13. **Müzikal/animasyon (4):** SEN ŞARKILARINI SÖYLE, KORO (MÜZİKAL), KULE, BİR DİLEK TUT (ANİMASYON)
    → `export\müzikal+animasyon`'a taşındı.
14. **Duplikat/versiyon:** AŞK ŞİMDİ (aynı TRT 2 dosya, EN-sesli→SESTEYIT doğru, ONAYLI kopya silindi);
    KEFERNAHUM -88-1 cast'i -88-0'a eşitlendi; 3 versiyon-çifti (ZORAKİ KRAL, KEFERNAHUM, GÜL BAHÇESİ,
    aynı süre+çözünürlük=duplikat) tek'e indirildi (-1 silindi).
15. **Afiş görsel-sweep (161, 6 montaj):** 4 yanlış afiş bulundu:
    - **MUCİZE** → "Wonder" (ABD) afişi (yanlış-film, aşağıda)
    - **AİLE GİBİ** → "These Are the Rules" afişi → Una especie de familia afişine düzeltildi
    - **BABAMIN KAMYONU** → "Father and Son" afişi → My Father's Truck afişine
    - **YANKESİCİLERİN MOZART'I** → Mozart besteci portresi → afişsiz (TMDB'de gerçek afiş yok)
    - (ARAMIZDAKİ SÖZLER, ARAKÇILAR şüphelendi ama afişleri DOĞRU çıktı — yanlış-alarm)
16. **Yönetmen-çapası audit:** OCR-yönetmen vs final-yönetmen, 32→23 (aksan-fold). 23'ün hepsi doğrulandı.

### Bulunan YANLIŞ-FİLM hataları (en kritik) — afiş+yönetmen ile yakalandı, metin/QC kaçırdı
- **MUCİZE (2017-1169):** Ajan, başlık "Mucize"+oyuncu "Aras Bulut İynemli"den **7. Koğuştaki Mucize (2019)**
  sanmış; OCR-yönetmeni MAHSUN KIRMIZIGÜL'ü ezmiş. → **Mucize (2015, Mahsun Kırmızıgül)** olarak geri kuruldu.
- **GÖLGE SAVAŞÇI (2022-1150):** Ajan **Zhang Yimou'nun Shadow'u (2018)** sanmış; OCR=AKİRA KUROSAWA +
  afiş=Kagemusha'yı ezmiş. → **Kagemusha (1980, Kurosawa)** olarak geri kuruldu (özet de tarih-girişinden arındırıldı).
- **NİNNİ (2022-1006):** DOĞRUYDU (Cinco lobitos, Alauda Ruiz de Azúa). Benim yönetmen-verify ajanım
  audit'i körü körüne takip edip OCR-yönetmen-satırı "Juanma Bajo Ulloa"ya (yanlış-okuma) güvenip
  "Baby (2020)"ye çevirip **BOZDU**. Afiş-görsel ("Lullaby") + OCR-cast ("Laia Costa","Cinco Lobitos")
  yakaladı → **Cinco lobitos'a geri** kuruldu. → **KANUN 4 (TÜM-OCR-KANITI) bu olaydan doğdu.**

### 23 yönetmen-değişiminin tam dökümü
- **2 gerçek yanlış-film:** MUCİZE, GÖLGE SAVAŞÇI (düzeltildi).
- **1 doğruydu (fix bozdu→geri):** NİNNİ.
- **20 meşru garble-düzeltmesi (doğrulandı):** OCR-yönetmeni oyuncu/ekip/başlık/garble'mış, ajan doğru
  yönetmeni koymuş. Örn: HAVADA İNTİKAM (Fred Olen Ray/Ed Raymond), AŞK BALIK KOKAR (Analeine Cal y Mayor),
  SONA DOĞRU (J.C. Chandor/All Is Lost), İTALYAN YAZI (James D'Arcy/Made in Italy), KAPTAN BENİM
  (Matteo Garrone/Io Capitano), SON KELİME (Mark Pellington/The Last Word 2017), ÜZGÜNÜZ (Ken Loach),
  SİNEK KUŞU (Kim Bora), KÖTÜ ÇOCUK (Yağız Alp Akaydın), SAĞ SAĞLİM 2 (Ersoy Güler), vd.

### Kim/hangi aşama hatayı yaptı (kök-neden)
- MUCİZE & GÖLGE: **ilk araştırma workflow'u** (167-ajan turu) — "EXACT film bul" deyince kimliği
  sıfırdan türettiler, OCR-yönetmenini çapa almadılar.
- NİNNİ: **düzeltme aşamasının kendisi** (yönetmen-verify ajanım) — tek sinyale güvendi.
- Ortak kök: **"tek-sinyale güven + sessiz override".** Çözüm: KANUN 3 + KANUN 4.

---

## 13. ÇALIŞMA PRENSİPLERİ (Çağatay'ın kuralları — özet)
1. **Kontrolü kaybetme** — her PDF'i gözünle aç-gör-doğrula, çöpü/yanlışı SEN yakala.
2. **Deterministik triage YETMEZ** — 5 vektör (triage + cast-adversarial + reading-QC + afiş-görsel + yönetmen-audit).
3. **Garble = sil-değiştir; gerçek isim = OCR otorite; yönetmen = çapa** (değişim ek-izin/bayrak).
4. **Tek-sinyalle kimlik değiştirme** — OCR'ın tüm kanıtı (yönetmen+cast+başlık+konu) birlikte.
5. **Tek örnekle "hazır" deme**; çeşitli sette ölç. Dürüst raporla (kalan riski sakla­ma).
6. **Eksik normal, uydurma yasak.** Müzikal/animasyon ayrı. Duplikat tek'e in.
7. **Türkçe iletişim. Yerinde-düzelt (promote değil). Her orijinali yedekle.**

---

## 14. HIZLI BAŞLANGIÇ CHECKLIST (kopyala-kullan)
```
□ _triage_onayli.py            → durumu gör
□ _poster_audit.py --apply     → gömülü afişleri koru
□ araştırma workflow (chunk=5) → corr_new\ (KANUN 3-7 promptta)
□ kısmi-ASCII özet kontrolü    → düzelt
□ _prep_render.py              → _render_corr.json
□ render_in_place.py           → yerinde düzelt (yedekli)
□ V1 _triage_onayli.py         → garble/casing/keyword/tarih
□ V2 cast-adversarial          → halüsinasyon avı
□ V3 reading-QC (5 Sonnet)     → kısmi-ASCII/meta/kesik özet
□ V4 _poster_montage.py + göz  → yanlış afiş/film
□ V5 _director_audit.py + adv. → yanlış-film kimliği (TÜM-OCR-KANITI)
□ _find_muzikal_anim.py --apply→ müzikal/animasyon ayır
□ _versiyon_check.py           → duplikat tek'e in
□ dürüst kalibreli rapor       → 5 vektör de koşmadan "bitti" deme
```

**Tek cümle:** Garble'ı web-gerçeğiyle değiştir, gerçek ismi koru, **yönetmeni çapa al ve sessiz
değiştirme**, kimliği **tüm OCR kanıtıyla** belirle, özeti konu-başlı+spoiler+doğal-Türkçe yaz,
**afişleri gözle tara**, ve 5 vektör koşmadan "bitti" deme.
