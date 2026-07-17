# MİTAS — KÜNYE PDF DÜZELTME REHBERİ (OPUS İÇİN, TAM DETAY)

> Bu doküman başka bir oturumda Opus'a verilecek. Amaç: künye PDF düzeltme işini
> **bu oturumun bağlamı olmadan**, sıfırdan, hatasız yapabilmek. Her yol, her kural,
> her tuzak burada. Tahmin etme — burada yazana uy.
>
> Yazıldığı tarih: 2026-06-14 · Platform: Windows 10, PowerShell · Repo: `E:\MITAS`

---

## 0. TL;DR — 30 SANİYELİK ÖZET

MİTAS, TRT film arşivini işleyip her film için bir **künye PDF**'i üretir (yönetmen, oyuncular,
yapımcı, özet, ses/altyazı, afiş). Pipeline'ın OCR'ı bazen **çöp (garble)** okur: şarkı sözü,
diyalog, ekip rolü ("PROJE KOORDİNATÖRÜ") isim sanılır. Senin işin:

1. Bir PDF'i aç, **gözünle** içeriği oku (oyuncu/yönetmen/yapımcı/özet).
2. Çöp/eksik olanı tespit et.
3. Web'den (Wikipedia/IMDb/TMDB/beyazperde) **gerçek** kadroyu doğrula.
4. Bir **corrections JSON** yaz.
5. `fix_kunye.py --promote` çalıştır → PDF yeniden render edilir + doğru kademeye taşınır.
6. Sonucu **fitz ile tekrar oku, gözünle doğrula**.

Araç hazır ve çalışıyor (`E:\MITAS\outputs\kunye_fix\fix_kunye.py`). Sen sadece doğru
corrections JSON'u üretip koşturacaksın.

---

## 1. EN KRİTİK 3 KURAL (ÖNCE BUNLAR)

### KURAL 1 — GARBLE = ÇÖP = SİL VE DEĞİŞTİR
OCR'ın okuduğu şey **gerçek bir isim değil de çöpse** (garble), onu silmek ve web'den gelen
gerçekle değiştirmek SERBESTTİR ve DOĞRUDUR. Garble örnekleri:
- `LIGHIING SENIOR ARTISTS` (ekip rolü + bozuk harf)
- `PROJE KOOROINATORD FERAT EİLGİN` ("Proje Koordinatörü" başlığı isim sanılmış)
- `A NOVEL BY`, `IN FOUR VOLUMES`, `HISTORY OF MY LIFE` (jenerikteki kitap kapağı metni)
- `SN. OMER AHUNEAY` ("Sn." öneki + bozuk soyad)
- `KOMUTAN / COMMANDER ERGIN KILIKCIER` (karakter unvanı "Jandarma Komutanı" isim olmuş)
- `JBURÏÏN BİLDİK` (tamamen bozuk harfler)

Bunlar çöptür. Tereddüt etme, web-doğrulanmış gerçek isimle değiştir.

### KURAL 2 — OCR OTORİTE KURALI (gerçek isimleri korur)
OCR'ın okuduğu şey **geçerli, gerçek bir isimse**, web onu **EZEMEZ**. Web sadece:
- BOŞ alanı doldurur (yönetmen yoksa web'den ekle),
- okunan ismin **yazımını** düzeltir (OCR `YILMAZ ERDOGAN` → web teyidiyle `YILMAZ ERDOĞAN`),
- eksiği tamamlar (6 oyuncu okunmuş, web 2 tane daha doğruluyorsa ekle).

**"Ahmet okuyup Mehmet yazmak" YASAK.** Gerçek bir ismi başka bir isimle değiştirme.
Ama Kural 1'i unutma: garble gerçek isim DEĞİLDİR, o yüzden bu koruma garble'a uygulanmaz.

**Ayırt etme:** Bir token gerçek isim mi garble mı? Test: Google/web'de o film + o isim
geçiyor mu? Geçiyorsa gerçek (koru). Geçmiyor + bozuk harf/rol-kelimesi/cümle-parçası ise
garble (sil-değiştir).

### KURAL 3 — KONTROLÜ KAYBETME, GÖZÜNLE DOĞRULA
İş bittiğinde "tamam" demeden ÖNCE PDF'i **kendin aç ve oku**. Çöp varsa SEN görmelisin,
Çağatay değil. Her render sonrası fitz ile metni çıkar, oyuncu/yönetmen/yapımcı/özet'i
tek tek gözden geçir. Tek örnekle "hazır" deme.

---

## 2. SİSTEM HARİTASI (YOLLAR — EZBERLE)

```
E:\MITAS\                                  ← repo kökü, working dir
├── Database\                              ← her filmin "hub" klasörü
│   └── {AD} {TRT}\                         ← örn: "BEYAZ BALİNA 2017-9028-1-0000-90-1"
│       ├── _DURUM.json                     ← pipeline durum/karar/neden + meta
│       └── pdf\
│           ├── kunye_teslim.md             ← BASELINE metin (cast/yön/yap/özet/ses)
│           ├── kunye.pdf                   ← pipeline'ın ürettiği PDF
│           ├── kunye_fixed.pdf             ← fix_kunye.py'nin ürettiği (render çıktısı)
│           ├── kunye_fixed_onizleme.png    ← önizleme görseli
│           └── afis.jpg                     ← afiş (varsa)
│
├── Mitas Output\export\                    ← TESLİM klasörleri (kademeler)
│   ├── ONAYLI\        {TRT} {AD} ONAYLI.pdf       ← ana_dil=TR + temiz
│   ├── SES_TEYIT\     {TRT} {AD} SESTEYIT.pdf     ← yabancı ses (KU/EN/JA…)
│   ├── KONTROL\       {TRT} {AD}.pdf              ← insan teyidi gerekli
│   ├── SORUNLU\       {TRT} {AD}.pdf              ← ASR fail / kimlik sorunu
│   └── _KONTROL_orijinal_yedek\                   ← promote öncesi otomatik yedek
│
├── outputs\kunye_fix\                      ← DÜZELTME MUTFAĞI (burada çalış)
│   ├── fix_kunye.py                         ← ★ ANA ARAÇ (tek film düzelt+render+promote)
│   ├── run_batch.py                         ← çoklu corrections → toplu render+promote
│   ├── corrections\{TRT}.json               ← batch'in yazdığı corrections (alt klasör)
│   ├── {TRT}.json                           ← tek-film corrections (kök; --corrections ile ver)
│   ├── state.json                           ← batch işlenmiş-film durumu
│   └── log.md                               ← batch log
│
├── _102_ozet_prompt_v2.md                  ← ÖZET YAZMA KURALLARI (birebir uy)
├── scripts\tek_film_kunye.py               ← parse_teslim_md, ozet_v4, _split_dedup_names
└── OCR-worktree\pdf-mitas\
    ├── _make_pdf.py                          ← mp.build(out_pdf, d) — PDF çizici
    ├── name_normalize.py                     ← isim kasası (tr_upper, upper_names…)
    └── poster_fetch.py                       ← afiş çekici
```

### PYTHON YORUMLAYICISI — ÇOK ÖNEMLİ
`fix_kunye.py` ve `run_batch.py` **GLOBAL Python 3.10** ile koşar (reportlab/fitz/PIL orada):
```
C:\Users\TRT03\AppData\Local\Programs\Python\Python310\python.exe
```
**venv KULLANMA.** PowerShell'de:
```powershell
$py = "C:\Users\TRT03\AppData\Local\Programs\Python\Python310\python.exe"
Set-Location "E:\MITAS\outputs\kunye_fix"
& $py fix_kunye.py --corrections "2017-9028-1-0000-90-1.json" --promote
```

---

## 3. KADEME (TIER) SİSTEMİ

Bir film 4 klasörden birine düşer. Kademe **deterministik** belirlenir (ajan "tier" alanı
yalnızca öneri; gerçek karar ana_dil + kimlik + müzikal + özet'e göre kodda verilir):

| Kademe | Koşul | Anlam |
|--------|-------|-------|
| **ONAYLI** | `tier=KESIN` + `ana_dil=TR` + özet≥20 kelime + kimlik OK + müzikal değil | Teslime hazır |
| **SES_TEYIT** | `tier=KESIN` ama `ana_dil≠TR` (EN/KU/JA…) | Yabancı ses, ayrı teyit |
| **KONTROL** | `ana_dil=—` (ses yok/ASR fail) VEYA müzikal VEYA özet<20 VEYA kimlik şüphesi | İnsan kararı |
| **SORUNLU** | ASR çökmüş / yanlış-film kimlik / çıktı yok | Derin inceleme / yeniden-işle |

**Otomatik demote'lar (fix_kunye.py `main()` + run_batch.py):**
- `ana_dil != TR` ve `tier=KESIN` → otomatik `SES_TEYIT` (yabancı ses ONAYLI'ya giremez).
- `müzikal` (genre içinde MÜZİKAL) → `KONTROL` (müzikal teslime alınmaz, v4 D4 kuralı).
- özet < 20 kelime (placeholder reddedildi) → `KONTROL`.
- `identity_ok=false` → `KONTROL`.

**NOT (TR otorite dersi):** ana_dil **kanıtlanmış** TR olmalı. Pipeline'ın whisper-LID'i
(baseline `_DURUM.json`/MD'deki "Ana dil") BİRİNCİL kaynaktır. Ajan "TR" diye TAHMİN ederse
GÜVENME — doğrulanmamış TR ONAYLI'ya kaçmasın. Baseline boşsa ve ajan yabancı dil
doğruladıysa → SES_TEYIT. Baseline boş + 1. ses kanalı TR ise → TR-dublaj kabul (güvenilir
`_channel_lang` tespiti).

---

## 4. ÇEKİRDEK ARAÇ: `fix_kunye.py` — TAM DAVRANIŞ

### Ne yapar
Buggy OCR cross-check'i ATLAR. cast/yönetmen/yapımcı/tür/afiş'i **web-doğrulanmış corrections
JSON**'undan alır. `tek_film_kunye.py` ile AYNI render zincirini kullanır (isim kasası + ozet_v4
+ poster_fetch + _make_pdf.build). Böylece garble/crew-sızıntı/eksik-yönetmen **inşaen** temiz.

### Akış (build_fixed → promote)
1. `trt_id` → hub klasörü bul: `glob(Database\*{trt}*)`, `_DURUM.json` olanı/en yenisini seç.
2. **Baseline** = `parse_teslim_md(pdf/kunye_teslim.md)` → title, res, dur, ses_kanallari,
   ana_dil, altyazı, özet. Ayrıca MD'den ham cast/yönetmen/yapımcı satırlarını da okur
   (corrections o alanı vermezse fallback).
3. **Corrections uygula** (varsa override, yoksa MD baseline):
   - `director` → yönetmen (yoksa MD'deki Yönetmen satırı)
   - `producers` → yapımcı, `_split_dedup_names` ile böl+dedup, **max 3**
   - `cast` → oyuncular, böl+dedup, **max 8**
   - `genre` → tür, izinli listeden max 2, TR-büyük, "/" ile
   - `title_override` → TRT yazım hatasını düzeltir (REPLEY→RIPLEY), en yüksek öncelik
   - `original_title` → alt başlık (TR başlıkla aynıysa düşürülür)
   - `ana_dil`, `altyazi`, `channels` → ses bloğu override
   - `poster` → afiş kontrolü (aşağıda)
4. **İSİM KASASI** (kritik — bkz §7 Tuzak 2):
   - Corrections'tan gelen cast/crew → **yalnız `nn.tr_upper`** (Türkçe İ/Ş/Ğ/Ç/Ö/Ü korunur).
   - MD baseline'dan gelenler → `nn.upper_names`/`nn.upper_crew` (DB/DeepSeek karar verir).
5. **Özet**: `corr["summary"]` veya `corr["ozet"]` veya MD'deki özet → `ozet_v4()` ile
   biçimlenir (spoiler korunur, ~72 kelime tavanı, isim-farkında büyük harf). Placeholder
   ("HAM TRANSCRIPT…" / "KALIP ÖZET") **reddedilir → "—"**.
6. **Afiş kapısı**: poster portre (dikey, w<h) ve >5KB olmalı. Yatay/kare görsel = afiş değil
   (frame-grab/backdrop tuzağı) → reddedilir. Afişsiz kalmak yanlış-fotodan iyidir.
7. `mp.build()` → `hub/pdf/kunye_fixed.pdf` + önizleme PNG.
8. **Self-verify**: fitz ile metni çıkar, checks döndür (yönetmen_var, cast_sayı, özet_kelime…).
9. `--promote` ile: kademe `KESIN`→ONAYLI'ya kopyala (eski KONTROL/yanlış-ONAYLI sil, önce
   `_KONTROL_orijinal_yedek`'e yedekle). `SES_TEYIT`→SES_TEYIT klasörü. `KONTROL`→KONTROL'de
   düzeltilmiş yaz (insan görsün).

### Kullanım
```powershell
# Tek film, render + doğru kademeye taşı:
& $py fix_kunye.py --corrections "2017-9028-1-0000-90-1.json" --promote

# Sadece render (taşıma yok, önizleme için):
& $py fix_kunye.py --corrections "2017-9028-1-0000-90-1.json"

# Dry-run (ne yapacağını söyler, dosya taşımaz):
& $py fix_kunye.py --corrections "2017-9028-1-0000-90-1.json" --promote --dry
```

Çıktı JSON'unda bak: `"ok": true`, `checks.yonetmen_var`, `checks.cast_sayi`,
`checks.ozet_kelime`, `tier_final`, `promote_dest`.

---

## 5. corrections JSON FORMATI

Dosya: `E:\MITAS\outputs\kunye_fix\{TRT}.json` (tek film için; `--corrections` ile yol verilir).
UTF-8, tek satır veya pretty — fark etmez. **Türkçe karakterleri DOĞRU yaz** (ASCII'ye çevirme,
araç hallediyor).

### Tam şema (tüm alanlar opsiyonel, ama `trt_id` zorunlu):
```json
{
  "trt_id": "2017-9028-1-0000-90-1",        // ZORUNLU — hub'ı bulmak için
  "director": ["A. UYGUR ÖZTÜRK"],          // yönetmen(ler), liste
  "cast": ["EFE KARAMAN", "KAAN ÜRKMEZ"],   // max 8, BÜYÜK HARF, gerçek oyuncular
  "producers": ["A. UYGUR ÖZTÜRK"],          // max 3
  "ozet": "ANNE BABASINI KAYBEDEN ALİ...",   // BÜYÜK HARF, 4 cümle, 40-65 kelime, spoiler final
  "genre": ["DRAM"],                          // izinli tür listesinden (bkz §6), max 2
  "tier": "KESIN",                            // KESIN | SES_TEYIT | KONTROL (öneri; kod yine doğrular)
  "title_override": "RIPLEY",                 // SADECE TRT başlığı yazım hatalıysa
  "original_title": "Beyaz Balina",           // yabancı/orijinal ad (alt başlık)
  "ana_dil": "EN",                            // SADECE baseline boş + web-doğrulanmış yabancı dil
  "altyazi": "EVET",                          // override
  "channels": ["TR", "EN", "TR", "EN"],       // ses kanalları override (LID hatası düzeltir)
  "poster": {"fetch": true, "imdb_id": "tt..."},  // afiş (aşağıda)
  "year": "2017",                             // afiş aramada yardımcı
  "identity_ok": true,                        // false → KONTROL (yanlış-film şüphesi)
  "notes": "garble cast+yapımcı web ile değiştirildi"  // log için, opsiyonel
}
```

### `poster` alt-nesnesi:
```json
"poster": {"none": true}                    // afiş İSTEME (afişsiz bırak)
"poster": {"fetch": true}                   // afiş çek (poster_fetch ile)
"poster": {"fetch": true, "year": "2017"}   // yıl ipucuyla çek
"poster": {"imdb_id": "tt1234567"}          // FORCE: mevcut yanlış afişi sil, bu ID'den çek
"poster": {"tmdb_id": "602865"}             // FORCE: TMDB ID'den çek
"poster": {"force": true, "fetch": true}    // mevcut afişi yoksay, yeniden çek
```
- `imdb_id`/`tmdb_id`/`force` verilirse mevcut (yanlış) afiş **silinir** ve taze çekilir
  (aynı-başlık-farklı-dönem tuzağını kırar, örn. Karayip Korsanları yanlış film afişi).
- Afiş alanı verilmezse: mevcut `afis.jpg`/cache >5KB ise korunur.
- **DİKKAT:** `poster_fetch` ağ çağrısı yavaş/asılabilir. Toplu işte
  `$env:MITAS_FAST_NO_POSTER="1"` ile ağ fetch'ini atla (kötü afiş yine silinir); afişleri
  sonra ayrı `prefetch_posters.py`/`apply_posters.py` pass'inde çek.

### Minimal örnek (sadece eksik yönetmen + özet):
```json
{"trt_id":"2001-9313-1-0000-00-1","director":["GIACOMO BATTIATO"],
 "ozet":"VENEDİK SOKAKLARINDA...","tier":"KESIN"}
```

---

## 6. ÖZET YAZMA KURALLARI (BİREBİR UY)

Kaynak: `E:\MITAS\_102_ozet_prompt_v2.md`. Özeti sen web'den (Wikipedia konu/olay örgüsü)
üretirsin. Kurallar TAVİZSİZ:

1. **TÜMÜ BÜYÜK HARF. Kasa kuralı:**
   - TÜRKÇE sözcükler ve TÜRK isimleri → Türkçe büyük harf: `i→İ`, `ı→I`, ve `ç ğ ö ş ü` KORUNUR.
     (güzellik→GÜZELLİK, genç→GENÇ, çöküş→ÇÖKÜŞ)
   - YABANCI özel adlar → SADECE ASCII: `i→I` (İ DEĞİL), aksanlar düşer (é→E, ñ→N, ø→O).
     İçinde Türkçe harf (İ/Ş/Ğ/Ç/Ö/Ü) OLMAZ. (Katie→KATIE, José→JOSE, New York→NEW YORK)
   - Türkçe ekler yabancı ada Türkçe kuralla: Hollywood'a→HOLLYWOOD'A.
2. **UZUNLUK: 4 cümle, 40–65 kelime. Tek paragraf.**
3. **SADE — SÜS YOK.** Her cümle somut olay (neden→sonuç). Edebi kuyruk AT.
4. **KORUNACAK:** ana karakteri adıyla tanıtan açılış + **SPOILER final** (kim ölür/kazanır/
   barışır AÇIKÇA). Final cümlesi muğlak/temalı OLAMAZ.
5. **YASAK:** soru, ünlem, tırnak, köşeli parantez, klişe ("hayatı değişir", "kendini bulur"),
   karakter listesi, yan olay örgüsü, yumuşatma (ölüm→ayrılış).

> NOT: `ozet_v4()` zaten spoiler-finali korur ve ~72 kelime tavanı uygular; ama sen 40-65
> kelime SADE yazarsan hiç kırpmaz (anlam kaybı olmaz). Büyük harf kasası `tr_upper_prose`
> ile isim-farkında yapılır — yani özet metnini DOĞRU Türkçe büyük harfle yazman yeterli,
> yabancı isimleri ASCII bırak.

**İyi özet örneği (Terminatör Kara Kader, 54 kelime, spoiler final):**
> GELECEĞE AİT BİR AJAN OLAN GRACE, MEKSİKA'DA FABRİKA İŞÇİSİ DANI'Yİ ÖLDÜRMEYE GELEN GELİŞMİŞ
> TERMINATOR REV-9'A KARŞI KORUR. SARAH CONNOR ONLARA KATILIR VE ÜÇLÜ, GEÇMİŞTE JOHN CONNOR'I
> ÖLDÜREN T-800 CARL'I BULUR. SON SAVAŞTA GRACE, DANI'Yİ KURTARMAK İÇİN YAŞAM KAYNAĞI OLAN GÜÇ
> ÜNİTESİNİ FEDA EDER. CARL İSE REV-9'I SÜRÜKLEYEREK BİRLİKTE BARAJDAN DÜŞER VE İKİSİ DE ÖLÜR.

### İzinli TÜR listesi (genre alanı için):
```
DRAM, KOMEDİ, KORKU, GERİLİM, AKSİYON, MACERA, BİLİM KURGU, ANİMASYON, WESTERN, ROMANTİK,
SUÇ, POLİSİYE, SAVAŞ, TARİH, BİYOGRAFİ, MÜZİKAL, FANTASTİK, GİZEM, AİLE, BELGESEL, DOĞA, SPOR, KISA
```
(MÜZİKAL yazarsan film KONTROL'e düşer — müzikal teslime alınmaz.)

---

## 7. BİLİNEN TUZAKLAR (HER BİRİNE DİKKAT)

### Tuzak 1 — DeepSeek HTTP 402 gürültüsü
İsim kasası DB-miss'te DeepSeek API'ye sorar; anahtar ölü (402 Payment Required). Konsola
kırmızı `[_deepseek] HTTP 402 …` satırları basılır. **Zararsız** — render yine biter. Ama:
- `run_batch.py` zaten `MITAS_DEEPSEEK`/`DEEPSEEK_API_KEY` env'lerini siliyor (gürültü yok).
- Tek `fix_kunye.py` koşusunda görürsün; **görmezden gel**, çıktı JSON'una bak.

### Tuzak 2 — Ü/Ö ASCII'ye düşme (ÇÖZÜLDÜ ama bil) ★
`upper_names()` saf-ASCII + sadece-Ç/Ö/Ü isimleri Türk-mü diye DB/DeepSeek'e sorar. DB-miss
+ DeepSeek-402'de **fallback `ascii_fold().upper()`** çalışır → `ÖZTÜRK`→`OZTURK`, `ÜRKMEZ`→
`URKMEZ` olur. **Gerçek Türk ismi bozulur.**

**ÇÖZÜM (zaten uygulandı, `fix_kunye.py` satır ~147-159):** corrections JSON'dan gelen
cast/crew web-doğrulanmış ve zaten doğru büyük harf olduğu için, onlara `upper_names` DEĞİL
doğrudan `tr_upper` uygulanıyor:
```python
_from_corr_cast = bool(corr.get("cast"))
_from_corr_crew = bool(corr.get("director") or corr.get("producers"))
castU = ([nn.tr_upper(n) for n in cast] if _from_corr_cast else nn.upper_names(cast)) if cast else []
...
if _from_corr_crew and crew:
    crewU = [(r, [nn.tr_upper(x) for x in xl]) for r, xl in crew]
else:
    crewU = nn.upper_crew(crew) if crew else [("Yönetmen", ["—"])]
```
**Sonuç:** corrections'ta `KAAN ÜRKMEZ` yazarsan PDF'te `KAAN ÜRKMEZ` çıkar (Ü korunur).
MD baseline'dan gelen isimler eski DB-yoluna devam eder. **Bu düzeltme `run_batch.py`'ye de
otomatik yansır** (o da `build_fixed` çağırır).
→ Yine de her render sonrası fitz ile kontrol et: `OZTURK` görürsen JSON'da `ÖZTÜRK` mi
diye bak.

### Tuzak 3 — MD'deki özet PLACEHOLDER
`kunye_teslim.md`'nin `## Özet` bölümü çoğu filmde **placeholder**'dır:
- `(ÖZET AYRI BİR ADIMDA ÜRETİLECEKTİR.)`
- `(HAM TRANSCRİPT ÖNİZLEME — KALIP ÖZET SONRA) …ham ASR…`

`parse_teslim_md` ve `ozet_v4` bunları **reddeder → "—"**. Yani özeti MD'ye güvenip alma;
**SEN web'den üret ve corrections'a `ozet` koy.** Özet < 20 kelime → film KONTROL'de kalır.

### Tuzak 4 — fitz iki-sütun okuma artefaktı (PANİK YAPMA)
PDF iki sütunlu. `fitz`'in `get_text()`'i bazen özet metnini yapımcı bölümünden SONRA okur
(ham çıkarımda `Yapımcı … Ö Z E T … GELECEĞE AİT…` gibi). **Bu PDF'in layout sorunu DEĞİL,
fitz okuma sırası artefaktı.** Görsel PDF doğru. Doğrulama için `get_text("blocks")` kullan
ve bölüm başlıklarını ("O Y U N C U L A R", "Yönetmen", "Ö Z E T") regex'le yakala.

### Tuzak 5 — Re-render özeti KAYBEDER
`fix_kunye.py`'yi **özet alanı OLMADAN** koşarsan (örn. sadece `director` düzeltmesi), özet
MD baseline'dan alınır = placeholder = "—". Yani daha önce render ettiğin gerçek özet SİLİNİR.
**KURAL:** her re-render'da corrections JSON'a `ozet` alanını HER ZAMAN koy (gerçek özeti
elinde tut). Yalnız-yönetmen düzeltmesi yapsan bile özeti tekrar yaz.

### Tuzak 6 — Kısa garble denetimden kaçar
Garble dedektörü uzun/anahtar-kelimeli çöpü yakalar ama **< 4 kelimelik** kısa garble'lar
(örn. yönetmen `JBURÏÏN BİLDİK`) kaçabilir. Bu yüzden gözle kontrol şart. Yönetmen satırında
bozuk harf (Ï, ÏÏ, mantıksız harf dizisi) görürsen web'den gerçek yönetmeni çek.

### Tuzak 7 — Yanlış-film kimlik (cast kesişimi 0)
`_DURUM.json`'da `"XML-PDF cast kesişimi 0 (yanlış-film şüphesi)"` neden'i varsa: OCR'ın
okuduğu kadro ile TRT XML'indeki kadro hiç örtüşmüyor. Bu CİDDİ — film yanlış tanınmış
olabilir. Web'den TRT başlığı + yıl ile doğrula; emin değilsen `identity_ok: false` koy
(KONTROL'de kalır). Afişi de yanlış film afişi olabilir, dikkat.

### Tuzak 8 — Bayat tarayıcı/working-tree
"Düzelttim ama hâlâ eski görünüyor": PDF'i tekrar fitz ile oku (cache değil disk). Export
klasöründeki dosyanın mtime'ına bak. Gerekirse `--promote`'u tekrar koş.

---

## 8. ADIM ADIM İŞ AKIŞI (BİR FİLM İÇİN)

```
1. PDF'i oku (fitz blocks ile) → cast/yönetmen/yapımcı/özet'i gör.
2. Garble/eksik tespit et (Kural 1 vs 2 ayrımını yap).
3. _DURUM.json'a bak → neden, ana_dil, kimlik durumu.
4. Web ara (paralel ajan): TRT başlığı + yıl → gerçek yönetmen/cast/yapımcı.
   - Türkçe film: beyazperde, sinematurk, sinemalar, TMDB, Wikipedia.
   - Yabancı film: IMDb, TMDB, Wikipedia.
   - "Producer" = yapımcı (executive producer'ı AYIR, sadece asıl yapımcı).
   - Karakter unvanını (Komutan, Doktor) oyuncu sanma.
5. Özet üret (web olay örgüsünden, §6 kurallarına göre, spoiler final).
6. corrections JSON yaz → outputs\kunye_fix\{TRT}.json
   - cast max 8, producers max 3, BÜYÜK HARF, Türkçe karakterler doğru.
   - ozet HER ZAMAN koy (Tuzak 5).
   - tier=KESIN (kod ana_dil'e göre düzeltir).
7. & $py fix_kunye.py --corrections "{TRT}.json" --promote
8. Çıktı JSON'da ok/checks/tier_final/promote_dest doğrula.
9. fitz ile export'taki yeni PDF'i OKU, gözle doğrula (Tuzak 2: OZTURK mu ÖZTÜRK mü).
10. Temizse bir sonraki filme geç.
```

### Web araması için ajan kullan (paralel, 3-5 tane)
Çağatay kuralı: **78+ paralel ajan ÇALIŞTIRMA, 3-5 tane.** Her ajana net JSON şeması ver:
```
"director": ["..."], "cast": ["...×8"], "producers": ["...×3"]
Türkçe isim → Türkçe büyük harf (İ/Ş/Ğ). Yabancı isim → ASCII (İ değil I).
Executive producer'ı dahil etme. Karakter unvanını cast'e koyma.
```
Ajan dönüşünü **körlemesine kullanma** — döndüğü isimleri mantık süzgecinden geçir (ajan
da halüsine edebilir; çapraz-kaynak ister).

---

## 9. DOĞRULAMA — fitz ile PDF OKUMA (KOPYALA-KULLAN)

```powershell
$py = "C:\Users\TRT03\AppData\Local\Programs\Python\Python310\python.exe"
$script = @'
import fitz, re, sys
sys.stdout.reconfigure(encoding="utf-8")
files = {
    "FILM ADI": r"E:\MITAS\Mitas Output\export\ONAYLI\{TRT} {AD} ONAYLI.pdf",
}
for title, f in files.items():
    doc = fitz.open(f)
    blocks = []
    for page in doc:
        for b in page.get_text("blocks"):
            t = b[4].strip()
            if t: blocks.append(t)
    text = "\n".join(blocks)
    cast_m = re.search(r"O Y U N C U L A R\n(.*?)Y A P I M", text, re.S)
    yon_m  = re.search(r"Y.netmen\n(.+)", text)
    yap_m  = re.search(r"Yap.mc.\n([\s\S]+?)(?=\n[A-Z] [A-Z]|\Z)", text)
    ozet_m = re.search(r"Z E T\n([\s\S]+?)$", text)
    print("=== " + title + " ===")
    print("CAST: " + (cast_m.group(1).replace(chr(10)," | ").strip() if cast_m else "YOK"))
    print("YON:  " + (yon_m.group(1).strip() if yon_m else "YOK"))
    print("YAP:  " + (yap_m.group(1).replace(chr(10)," | ").strip()[:80] if yap_m else "YOK"))
    print("OZET: " + (ozet_m.group(1).replace(chr(10)," ").strip()[:120] if ozet_m else "YOK"))
'@
$script | & $py
```
**Kontrol listesi:** yönetmen gerçek mi? cast'te garble/rol/cümle-parçası var mı?
yapımcı "Sn."/rol-başlığı içeriyor mu? özet 4 cümle + spoiler final mi? Türkçe harfler
(Ü/Ö/Ş/Ğ/İ) korunmuş mu yoksa ASCII'ye mi düşmüş?

---

## 10. TOPLU İŞ (`run_batch.py`)

Çok film varsa tek tek değil toplu koş. Bir corrections **dizisi** (JSON array) ver:
```json
[
  {"trt_id":"...","director":["..."],"cast":["..."],"producers":["..."],"ozet":"...","tier":"KESIN"},
  {"trt_id":"...", ...}
]
```
```powershell
& $py run_batch.py --in corrections_all.json
# veya promote etmeden önce gör:
& $py run_batch.py --in corrections_all.json --no-promote
```
- Her corrections `corrections\{TRT}.json`'a yazılır, render+promote+log yapılır.
- `state.json` işlenenleri tutar (idempotent), `log.md`'ye satır eklenir.
- Kademe DETERMİNİSTİK (ajan tier'i değil, ana_dil+kimlik+müzikal+özet).
- DeepSeek env'leri otomatik kapatılır (gürültü yok).
- Çıktıda KESIN/SES_TEYIT/KONTROL/ERR sayıları + TRT listeleri basılır.

---

## 10B. RUTİN: TESPİT → STAGING → ONAY (3 ARAÇ, MANUEL)

Garble/eksik künyeleri **yarı-otomatik** temizlemek için 3 araç var. Akış: araç sorunu bulur,
ağır işi (web-doğrula + render) STAGING'e hazırlar, **insan onaylar** ("hazırla, onay bende"
modeli — ONAYLI'ya otonom dokunulmaz). Hepsi global python ile, `outputs\kunye_fix\`'te.

### 1) `detect_problems.py` — DETERMİNİSTİK TARAYICI (salt-okunur)
Export PDF'lerini tarar, sorunlu künyeleri (garble/eksik/placeholder) work-list'e yazar.
LLM yok, web yok, değişiklik yok.
```powershell
& $py detect_problems.py --folders ONAYLI                 # sadece ONAYLI
& $py detect_problems.py --folders ONAYLI SES_TEYIT KONTROL  # hepsi
# çıktı: worklist_detect.json + konsola sorun listesi
```
Tespit: özet-boş/placeholder/kısa · yönetmen-boş/garble · oyuncu/yapımcı-garble (rol-kelimesi
`KOORDINATOR/KAMERA/SENARYO/COMMANDER/SN.`, bozuk harf `Ï`, 4+ kelimelik birleşik satır, rakam).
**Garble tespiti kusursuz DEĞİL** — aday listesi üretir, kesin hüküm değil; insan/ajan teyidi şart.

### 2) `stage_batch.py` — STAGING'E HAZIRLA (PROMOTE YOK)
Web-doğrulanmış corrections dizisini alır, her filmi `export\_STAGING\`'e render eder.
**ONAYLI/KONTROL/SES_TEYIT'e DOKUNMAZ.** İnsan gözden geçirsin diye aday + rapor üretir.
```powershell
& $py stage_batch.py --in corrections.json
# üretir: _STAGING\{TRT} {AD} ADAY.pdf + _onizleme.png
#         _STAGING\corrections\{TRT}.json  (onay girdisi)
#         _STAGING\_REVIEW_REPORT.md       (insan bunu okur: kademe/yön/cast/özet/not)
```
corrections formatı §5 ile AYNI (array olarak ver). Kademe deterministik hesaplanır ama yalnız
rapora yazılır.

### 3) `approve_staged.py` — İNSAN ONAYI (gerçek promote)
STAGING'deki **seçili** adayları gerçekten ONAYLI/SES_TEYIT/KONTROL'e taşır. Onaylananı
`_STAGING\_onaylanan\`'a arşivler.
```powershell
& $py approve_staged.py --trt 2024-1248-1-0000-90-1 2001-9264-1-0000-00-1   # seçili
& $py approve_staged.py --all                                                # STAGING'deki hepsi
& $py approve_staged.py --trt <TRT> --reject                                 # onaylamadan sil
```

### Tam manuel döngü (kopyala-kullan)
```powershell
$py = "C:\Users\TRT03\AppData\Local\Programs\Python\Python310\python.exe"
Set-Location "E:\MITAS\outputs\kunye_fix"
& $py detect_problems.py --folders ONAYLI          # 1. NE bozuk?
#   → worklist'i oku, sorunlu filmleri web-doğrula (3-5 ajan), corrections.json (array) yaz
& $py stage_batch.py --in corrections.json         # 2. STAGING'e hazırla (ONAYLI'ya dokunmaz)
#   → _STAGING\ADAY pdf'leri + _REVIEW_REPORT.md'yi GÖZLE incele (fitz/önizleme)
& $py approve_staged.py --trt <iyi olanlar>        # 3. SADECE doğru olanları onayla
```

> **Cron KURULMADI** (kullanıcı tercihi: token kontrolü tamamen onda). Bu araçlar elle
> çalıştırılır. İstenirse zamanlanmış göreve bağlanabilir — ama "tam otonom promote" QC kuralına
> aykırı; rutin yalnız STAGING'e KADAR otomatiktir, onay her zaman insanda.

### KOR örneği (staging modelinin DEĞERİ)
KOR (2024-1248) ONAYLI'daydı; detector yapımcı=`SENARYO` (garble) yakaladı. Web-doğrulama
filmin Zeki Demirkubuz "Kor" olduğunu KESİNLEŞTİRDİ (özet+yönetmen+yapımcı tuttu) AMA OCR
kadrosu (`DAVIIT SINIRTAS` vb.) web ile uyuşmuyordu. Rutin bunu **ezmedi** → STAGING'e bayrakla
koydu ("OCR↔web farklı, insan teyidi") → insan görüp onayladı. Otonom olsaydı yanlış-cast
riski vardı; staging tam da bu nüansı yakalar.

---

## 11. BUGÜN YAPILAN İŞ (ÇALIŞAN ÖRNEKLER — REFERANS)

4 ONAYLI film garble cast/yapımcı içeriyordu; web-doğrulayıp düzeltildi:

| Film | TRT | Sorun | Düzeltme |
|------|-----|-------|----------|
| TERMİNATÖR KARA KADER | 2025-1247-1-0000-90-1 | cast=`LIGHIING SENIOR ARTISTS`, yapımcı garble | 8 gerçek oyuncu + JAMES CAMERON vd. |
| KELEBEĞİN RÜYASI | 2013-9098-1-0000-90-1 | cast garble, yapımcı=`PROJE KOOROINATORD…` | KIVANÇ TATLITUĞ vd. + NECATİ AKPINAR |
| CASANOVA | 2001-9313-1-0000-00-1 | cast=kitap-kapağı metni, yönetmen YOK | GIACOMO BATTIATO + 8 İtalyan oyuncu |
| BEYAZ BALİNA | 2017-9028-1-0000-90-1 | cast=`KOMUTAN/COMMANDER`, yapımcı=`SN. …` | A. UYGUR ÖZTÜRK + gerçek kadro |

Her biri için corrections JSON `outputs\kunye_fix\{TRT}.json`'da DURUYOR (örnek olarak bak).
BEYAZ BALİNA, Tuzak 2'yi (Ü/Ö→ASCII) ortaya çıkardı; fix_kunye.py'ye tr_upper-bypass eklendi.

---

## 12. KALAN İŞ (DEVAM EDİLECEK)

### Hemen — `detect_problems.py` çıktısı (ONAYLI'da 11 gerçek sorun, 2026-06-14)
`& $py detect_problems.py --folders ONAYLI` ile her zaman güncelini al. Son tarama:

| TRT | Film | Sorun |
|-----|------|-------|
| 1981-0312 | KORKUNÇ ŞÜPHE | oyuncu `DANS LE ROLE DE` (Fr. etiket) |
| 2001-9264 | GİZLİ SİLAH | yönetmen-boş |
| 2002-9261 | PUMPKIN | oyuncu `DANNY D. MIISCOPI AT` garble |
| 2010-9110 | ZEFİR | 7 oyuncu satırı birleşmiş (2 isim/satır) |
| 2012-0233 | DÜNYANIN MERKEZİNE YOLCULUK | yönetmen-boş |
| 2013-9097 | HÜKÜMET KADIN 2 | yapımcı `HAYK KİRAKOSYAN R.G.C.` garble |
| 2015-9072 | YENİ HAYAT | yönetmen-boş |
| 2017-1026 | SHANE | oyuncu `PROCESS PHOTOGRAPHY` (crew) |
| 2017-1082 | JOHNY GUİTAR | oyuncu `GHID DA JOA AYDEN` garble (+başlık JOHNNY) |
| 2023-1158 | BEBEK FİRARDA | yapımcı `AARON SİMS JİM LEONARD` garble |
| 2025-1397 | ASİ KABADAYI | yapımcı `MARTİN RİTT AND IRVİNG RA` (yabancı, ASCII olmalı) |

> Her birini §10B döngüsüyle işle (web-doğrula → stage → onay). ZEFİR'de isimler GERÇEK ama
> birleşik (split gerek, garble değil). ASİ KABADAYI yabancı olabilir (Martin Ritt → batı
> western'i; SES_TEYIT'e düşebilir). DANS LE ROLE DE = Fransızca "…rolünde" etiketi.

- **SAĞ SAĞLİM 2 SİL BAŞTAN** (`2024-1312`): yönetmen `JBURÏÏN BİLDİK` (kısa garble, Tuzak 6).
  Web'den gerçek yönetmeni çek → corrections (ozet dahil!) → `--promote`.
- **KOR** (`2024-1248`) ✅ 2026-06-14 düzeltildi (staging testi; yapımcı SENARYO→gerçek, kadro web-teyitli).

### Geniş kümeler (kademe bazında)
- **ONAYLI (~32):** Bugün hepsi tek tek doğrulandı (yön+cast+yapımcı+özet temiz). Yeni
  düzeltme sonrası tekrar fitz-tara.
- **SES_TEYIT (~31):** Yabancı ses; oyuncu/yönetmen/özet temizliği gerekiyorsa aynı akış.
- **KONTROL (~58):** Çoğu `ana_dil=—` (ASR fail / ses yok) veya özet-eksik yüzünden burada.
  - Özet eksikse → web'den üret, corrections'a koy, ana_dil baseline TR ise ONAYLI'ya çıkar.
  - ana_dil gerçekten yoksa/yabancıysa → KONTROL/SES_TEYIT'te kalır (insan kararı).
- **SORUNLU (~100):** ASR çökmesi / yanlış-film kimlik / çıktı yok. Derin inceleme veya
  pipeline yeniden-işleme gerekebilir. Önce `_DURUM.json` neden'lerini oku, grupla.

> Kademe sayıları anlık (2026-06-14); **oturum başında yeniden say**
> (`ls "E:\MITAS\Mitas Output\export\ONAYLI" | measure`).

### Çalışma prensibi (Çağatay'ın kuralları)
1. **Kontrolü kaybetme** — her PDF'i gözünle aç-gör-doğrula, çöpü SEN yakala.
2. **3-5 paralel ajan** yeter, 78+ değil.
3. **Garble = çöp = sil-değiştir**; gerçek isim = OCR otorite, web ezmez.
4. **Özet eksikliği KONTROL sebebi DEĞİL** — sen web'den üretirsin, gerisi temizse ONAYLI'ya çıkar.
5. **Tek örnekle "hazır" deme**; çeşitli sette sürekli ölç.
6. Türkçe iletişim. Doğrulanmamış kesin iddia yasak (isim "OCR'da var" demeden önce
   ad+soyad bitişik substring testi).

---

## 13. HIZLI BAŞLANGIÇ (OPUS, BUNU OKUYUNCA)

```
1. Bu dokümanı oku (bitti).
2. & $py ile bir film düzelt-test et (örn. SAĞ SAĞLİM 2):
   a. fitz ile PDF oku → garble'ı gör.
   b. _DURUM.json oku.
   c. 1 web ajanı → gerçek yönetmen/cast.
   d. özet üret (§6).
   e. corrections JSON yaz.
   f. fix_kunye.py --corrections --promote.
   g. fitz ile doğrula.
3. Çalıştığını gördükten sonra kalan kümeyi 3-5 ajanla paralel işle.
4. Her partiden sonra fitz-tara, gözle doğrula.
```

**Tek cümle:** Garbleı web-gerçeğiyle değiştir, gerçek ismi koru, özeti sen üret, her PDF'i
gözünle doğrula, Türkçe karakterleri koru, fix_kunye.py zaten hazır.
