Confirmed — this is a **static frame** (`giris`, "entry"), not scrolling text: both character (y0=88) and actor (y0=174) sit at clearly different y-bands (~86px apart), a genuine single-column layout stacked vertically. So VANYA DAYI's failure has NOTHING to do with y-collision at all — the character line and actor line are cleanly separated, both survive to `ocr_ham.txt` fully intact, and the LLM simply picked the wrong one (or kept both, incorrectly including the character one) because its prompt only covers same-line fusion, not adjacent-line stacking. This is a **pure LLM/prompt-rule gap**, fully fixable via option (C) prompt improvement alone.

I now have complete, well-grounded findings across all mechanism types. Let me write the final report.

## Bulgular (kanıtlı, ham-OCR referanslı)

**Kapsam düzeltmesi:** Talep edilen "2 ek KARAKTER-ADI filmi" `CAST_YAPIMCI_DOGRULUK_104.json`'da şunlar: **KURTLAR VADİSİ FİLİSTİN 2011-9138** (2 vaka: ABDULLAH EŞ/ABDULLAH KIZKARDEŞ) ve **ÇİNGENE GÜVELERİ (THE GYPSY MOTHS) 1969-0032** (MALCOLM WEBSON). Toplam 6 film incelendi.

### Mekanizma tablosu (satır/bbox kanıtlı)

| Film | Düzen | Casing sinyali | Kök neden |
|---|---|---|---|
| **SINIR ÇİZGİSİ** (`ocr-d02b4f45`) | İki-kolon (aynı satırda yan yana, y0/y1 tıpatıp aynı: örn. c_0445.png `CHARLES BRONSON` y0=396/y1=418 ↔ `Jeb Maynard` y0=396/y1=418) | TUTUYOR (oyuncu CAPS / karakter Title-Case) ama **rastgele kazanan**: BRONSON/Maynard sayımı 24 vs 25 (neredeyse berabere) | y-kümeleme çakışması → `pick_best` bir grubu tamamen atıyor |
| **KIZIL HAYAT** (`ocr-3d855acc`) | İki-kolon, bazen OneOCR'ın kendisi tek satırda birleştiriyor (`"Vadim Alexander Balouev"` tek OCR line'ı, bkz. c_0544.png) | Tutmuyor — ikisi de Title-Case (`Vadim` / `Alexander Balouev`) | Aynı y-çakışması + OneOCR satır-birleştirme (OCR motoru düzeyinde, stitch'ten önce) |
| **KURTLAR VADİSİ FİLİSTİN** (`ocr-f0a1ec9a`) | İki-kolon, aynı y0/y1 (c_0136 `ABDULLAH EŞ` y0=442/y1=455 ↔ `LİNDA ÇANDIR` y0=443/y1=455) | Tutmuyor — ikisi de ALL-CAPS (Türkçe konvansiyonu) | Aynı y-çakışması |
| **ÇİNGENE GÜVELERİ** (`ocr-bce5145a`) | İki-kolon, aynı y0/y1 (c_0581 `Scott Wilson` y0=376/y1=414 ↔ `Malcolm Webson` y0=382/y1=413) | Tutmuyor — ikisi de Title-Case | Aynı y-çakışması |
| **VANYA DAYI** (`ocr-ee227bdb`) | TEK-KOLON, dikey 3-satır blok (Karakter/rol-açıklaması/OYUNCU), y-çakışması YOK (y0=88 vs y0=174, ~86px ayrı) | TUTUYOR (Karakter Title-Case Kiril / Oyuncu ALL-CAPS Kiril) | Çakışma yok — saf LLM/prompt kapsam boşluğu (kural 2 yalnız tek-satır "KARAKTER OYUNCU" birleşimini kapsıyor, 3-satır bloğu kapsamıyor) |
| **BJ VE AYI** (`ocr-968ad6c4`) | Alakasız — jenerik kartı değil, hikâye-içi kamyon-tabelası rekvizit yazısı (`Billie Joe McKay` tabelası) iki OCR-bozuk varyantla cast'e sızmış | Alakasız | CLIP-bekçi/OCR yanlış-pozitif kare, kolon-karışması DEĞİL |

**Kök-neden zinciri (SINIR ÇİZGİSİ/KIZIL HAYAT/KURTLAR VADİSİ/ÇİNGENE — 4/6 film):** `E:\MITAS\OCR-worktree\py\20260601_pipeline100.py:38-43` (`read_pos()`) OneOCR'ın `bounding_rect`'inden **yalnız y1..y4'ü alıyor, x'i hiç okumuyor** — halbuki `E:\MITAS\venvs\ocr\Lib\site-packages\oneocr.py:290-318` OneOCR'ın hem satır hem KELİME düzeyinde x-içeren `bounding_rect` döndürdüğünü gösteriyor (veri kaynakta var, drop noktası `read_pos`). Bu yüzden `20260601_stitch.py:118-133` (`stitch_kunye`) yalnız dikey-merkeze (`cy`) göre kümeliyor; aynı satırdaki iki kolon aynı kümeye düşüyor, `pick_best` (satır 29-51) tsim<0.80 olan iki farklı metni ayrı alt-gruplara ayırıp yalnız BÜYÜK grubu döndürüyor — küçük grup (~%40-50 ihtimalle gerçek oyuncu) tamamen düşüyor. Bazı karelerde (KIZIL HAYAT) OneOCR satır-tanıma aşamasının kendisi iki kolonu tek satırda birleştiriyor (`"Vadim Alexander Balouev"`), bu da stitch'ten önceki bir kayıp.

**VANYA DAYI ayrı kök-neden:** `credit_text_read.py:391` PROMPT kural-2 yalnız `"KARAKTER_ADI OYUNCU_ADI"` TEK-SATIR kalıbını kapsıyor; VANYA DAYI'nın 3-satırlı dikey blok (`Character` / `role-desc` / `ACTOR`) deseni kurala hiç girmiyor — OCR/stitch katmanında veri kaybı YOK, ham metin tam ve doğru (`master_dilim/dilim_oneocr.txt:10-12`), yalnız LLM rol-eşlemesi hata yapıyor.

---

## Çözüm seçeneklerinin değerlendirmesi

**(A) CASING-heuristic** (cast bloğunda CAPS+Title-Case karışıksa Title-Case'i karakter-şüphesi say, CAPS'i tercih et)
- Çözer: SINIR ÇİZGİSİ (kısmen — sinyal doğru ama zaten hangisinin cast'e girdiği rastgele, "tercih" için ikisinin de ham metinde hayatta kalması lazım, ki SINIR ÇİZGİSİ'nde tam tersi oluyor: ikisi de kalıyor ama biri stitch'te siliniyor), VANYA DAYI (temiz çözer — karakter/oyuncu ayrımı casing ile net).
- Çözmez: KIZIL HAYAT, KURTLAR VADİSİ FİLİSTİN, ÇİNGENE GÜVELERİ — üçünde de karakter VE oyuncu **aynı casing** (ya ikisi de Title-Case ya ikisi de CAPS). Heuristic bunlarda nötr kalır, yanlış isim düşmez ama düzeltme de yapmaz.
- Regresyon riski: DÜŞÜK — ADI CARMEN/ALTINA HÜCUM gibi temiz filmlerde cast bloğu casing-homojen (hepsi CAPS), heuristic hiç tetiklenmiyor (karışık-casing koşulu sağlanmıyor). Ama garanti değil: "a film by John Smith" gibi tek-satır director-kartları cast bloğu İÇİNDE değilse sorun yok; cast bloğu sınırlarını yanlış çizen bir üst-akış varsa (örn. bir yapımcı/senarist Title-Case satırı yanlışlıkla cast'e sızmışsa) o satır haksız yere elenebilir — düşük ama sıfır değil.
- Efor: DÜŞÜK — `credit_text_read.py` içinde saf metin-post-filtre, yeni env-flag ile kapatılabilir kill-switch.
- Katman: `credit_text_read.py` (LLM çıktısı sonrası post-filtre VEYA PROMPT'a ipucu — bkz. C).

**(B) BBOX-kolon** (x-koordinat kümeleme ile iki kolon ayır, KB-cast-örtüşmesiyle oyuncu-kolonunu belirle)
- Çözer: TÜM 4 y-çakışma vakasını (SINIR ÇİZGİSİ, KIZIL HAYAT, KURTLAR VADİSİ, ÇİNGENE) — dil-bağımsız, en genel çözüm, KURTLAR VADİSİ gibi "ikisi de aynı casing" vakalarını da kapsar çünkü casing'e hiç bakmaz.
- Çözmez: VANYA DAYI (zaten x-çakışması yok, ayrı sorun) ve KIZIL HAYAT'ın OneOCR-satır-birleşimi alt-vakasını (OCR motoru ikisini TEK metin string'i olarak zaten birleştirmişse, artık ayrı x-box'ları da yok — bu durumda bbox çözümsüz kalır, regex-split gerekir).
- Regresyon riski: DÜŞÜK-ORTA — mimari değişiklik olduğu için yeni kod yolu, ama additive (mevcut y-only akışa dokunmadan yeni alan eklemek), doğru test edilirse cast'e ekstra isim ATMAZ, yalnız iki-kolon durumunda hangi kolonun tutulacağına karar verir.
- Efor: YÜKSEK — üç katmanda değişiklik gerekir: (1) `read_pos()` içinde x0/x1'i de yakala (kaynak veri OneOCR'da hazır, satır 1 değişiklik), (2) `ocr_raw_reads.jsonl` şemasına x0/x1 ekle (geriye-dönük: **mevcut 6 filmin cache'i x içermiyor, yeniden-OCR gerekir**), (3) `stitch_kunye`/`stitch_run`'ı x-farkındalıklı iki-boyutlu kümelemeye çevir (kayda değer algoritma değişikliği, mevcut y-only regresyon testleriyle çakışabilir). Ayrıca "oyuncu-kolonunu KB-örtüşmesiyle belirle" adımı gerçek oyuncu-KB'si YOKSA (KIZIL HAYAT/KURTLAR VADİSİ gibi obskür/yabancı yapımlarda KB `KAYNAK_YOK` döndü — doğrulandı) çalışmaz, dil-bazlı sabit kural (örn. "İngilizce/Fransızca 'avec' bloğunda sol=oyuncu" ) gerekir ki bu da VANYA DAYI'nin TERSİ bir düzen olduğunu unutmamalı (karakter solda/üstte, oyuncu sağda/altta — ama VANYA DAYI y-çakışması olmayan tek-kolon, yani B'nin kapsamı dışında zaten).
- Katman: `20260601_pipeline100.py` (read_pos), `_pipe_ocr.py` (jsonl şeması), `20260601_stitch.py` (stitch_run/pick_best).

**(C) LLM-PROMPT** (casing-ipucu + "karakter Title-Case, oyuncu CAPS; karışıksa CAPS'i al" kuralı + çok-satırlı karakter/oyuncu bloğu kuralı eklensin)
- Çözer: VANYA DAYI TAM (3-satır bloğunu prompt'a örnekle eklemek yeterli — ham metin zaten sağlam). SINIR ÇİZGİSİ'Nİ ÇÖZMEZ çünkü sorun prompt değil, LLM'e ulaşan `ocr_ham.txt`'nin KENDİSİNDE gerçek oyuncu adı zaten YOK (stitch aşamasında silinmiş) — LLM'e ne kadar iyi kural verilse de görmediği ismi çıkaramaz. Aynı sebep KIZIL HAYAT/KURTLAR VADİSİ/ÇİNGENE için de geçerli: prompt-seviyesi çözüm veri kaybını telafi edemez.
- Regresyon riski: ÇOK DÜŞÜK — yalnız talimat metni genişliyor, davranış değişikliği yalnız net "karakter-şüpheli" örneklerde.
- Efor: ÇOK DÜŞÜK — `credit_text_read.py:391` PROMPT'a birkaç cümle/örnek eklemek.
- Katman: `credit_text_read.py` PROMPT.

**(D) KB-cast-örtüşme kapısı** (PDF-cast KB-cast ile <2 örtüşüyorsa + Title-Case baskınsa → KONTROL)
- Çözer: HİÇBİRİNİ otomatik-düzeltmez — yalnız İŞARETLER (insan payına havale). SINIR ÇİZGİSİ/VANYA DAYI gibi KB kaydı olan (IMDb/kino.mail.ru teyitli) filmlerde çalışır; KIZIL HAYAT/KURTLAR VADİSİ FİLİSTİN gibi KB `KAYNAK_YOK` dönen filmlerde ÇALIŞMAZ (zaten kanıtlı: KIZIL HAYAT scan notu "cast_ortusme=null").
- Regresyon riski: DÜŞÜK — yalnız KONTROL etiketler, isim silmez/eklemez.
- Efor: ORTA — `credit_kb_lookup.py`/`credit_qc_gates.py`'e yeni kapı, `cast_ortusme` zaten mevcut altyapı.
- Katman: `credit_qc_gates.py` veya `_pipe_credit_validate.py`.

---

## NET ÖNERİ

**Kombinasyon: C (hemen) + D (kapı, güvenlik ağı) + B (orta-vadeli, gerçek kök-neden çözümü) — A'yı bağımsız birincil çözüm olarak KULLANMA.**

1. **Hemen (C, düşük efor, VANYA DAYI'yı tam çözer):** PROMPT'a (a) "KARAKTER / rol-açıklaması / OYUNCU" 3-satırlık dikey blok örneği ekle (VANYA DAYI kalıbı: Title-Case satır → küçük-harf açıklama satırı → sonraki ALL-CAPS satır = gerçek oyuncu, aradaki Title-Case satır KARAKTER'dir, atla), (b) iki-kolon "aynı frekansta beliren iki yakın isim" durumunda LLM'e hiçbir ek bilgi veremeyiz çünkü bu senaryoda VERİ ZATEN KAYIP — bu yüzden C tek başına 4/6 filmi çözmez, yalnız 1/6'yı (VANYA DAYI) çözer.

2. **Orta-vadeli gerçek çözüm (B, yüksek efor ama TEK dil-bağımsız kalıcı çözüm):** `read_pos()`'a x0/x1 eklemek tek satırlık bir değişiklik (kaynak veri zaten OneOCR'dan geliyor) — bunu şimdiden ekleyip yeni koşulan filmlerde x-verisini biriktirmeye başlamak düşük-risk/yüksek-kazanç bir "veri toplama" adımıdır (davranış değişmez, yalnız jsonl şemasına alan eklenir). Asıl `stitch_kunye`'yi x-farkındalı kümelemeye çevirmek ayrı, dikkatli bir ikinci faz — regresyon riskini gerçek golden-set ile test etmeden CANLI'ya alınmamalı (mevcut memory'de "golden regresyon seti" zaten var, kullanılabilir). Bu, SINIR ÇİZGİSİ/KIZIL HAYAT/KURTLAR VADİSİ/ÇİNGENE'nin **hepsini** kapsar çünkü casing'e bakmaz, salt geometriye bakar.
   - Kolon-yönü kararı: KB-örtüşmesi varsa onu kullan (D); yoksa dil-bazlı varsayılan gerekir ama bu varsayılan da güvenilmez olabilir (İngilizce "Cast of Characters" ÇİNGENE GÜVELERİ'nde SOL=oyuncu/SAĞ=karakter, ama İngilizce "avec" KIZIL HAYAT'ta SOL=karakter/SAĞ=oyuncu farklı konvansiyon) — **kolonun hangisi olduğunu geometriden tek başına çıkaramazsınız, mutlaka KB veya bağlam-kelimesi (örn. "Cast of Characters" başlığından sonra ilk kolon oyuncu) gerekir.**

3. **Sürekli güvenlik ağı (D):** KB `cast_ortusme < 2` VE (B canlıysa) "iki-kolon çakışması tespit edildi" bayrağı birlikteyse → KONTROL. B henüz yokken bile, bu kapı en azından obskür-olmayan filmlerde (SINIR ÇİZGİSİ, VANYA DAYI gibi KB-teyitli olanlarda) yanlış cast'i insan gözden geçirmeye yönlendirir — KIZIL HAYAT/KURTLAR VADİSİ gibi `KAYNAK_YOK` filmlerde işe yaramaz ama zarar da vermez.

**A'yı NEDEN birincil çözüm olarak önermiyorum:** 6 filmin 3'ünde (KIZIL HAYAT, KURTLAR VADİSİ FİLİSTİN, ÇİNGENE GÜVELERİ) karakter ve oyuncu **aynı casing**'de — heuristic bu üçünde nötr kalıp hiçbir şey çözmüyor, "en çok kurtaran" değil "en az kurtaran" seçenek (yalnız SINIR ÇİZGİSİ + VANYA DAYI'da sinyal var, ama SINIR ÇİZGİSİ'nde asıl sorun zaten stitch-katmanında veri kaybı olduğu için casing kuralı bile devreye giremeden isim kayboluyor). A, yalnızca B/C ile birleşik bir ikincil-sinyal olarak (örn. B'nin x-kümeleme sonrası iki-kolon adayını KB yoksa casing ile ayırt et) değerli.

**Dosya/katman özeti:**
- `E:\MITAS\scripts\credit_text_read.py` — PROMPT (satır 385-411, kural 2 genişletme) — C
- `E:\MITAS\OCR-worktree\py\20260601_pipeline100.py:31-47` (`read_pos`) — x0/x1 yakalama — B faz-1
- `E:\MITAS\scripts\_pipe_ocr.py:1131-1133` (jsonl şema) — x0/x1 alanı ekle — B faz-1
- `E:\MITAS\OCR-worktree\py\20260601_stitch.py:71-133` (`stitch_run`/`pick_best`/`stitch_kunye`) — x-farkındalı kümeleme — B faz-2 (yüksek efor, regresyon-testli)
- `E:\MITAS\scripts\credit_kb_lookup.py` / `credit_qc_gates.py` — KB-örtüşme kapısı — D

**Kanıt dosyaları (ham referans):**
- SINIR ÇİZGİSİ: `E:\MITAS\DATABASE\SINIR ÇİZGİSİ 1995-0280-1-0000-00-1\ocr\ocr-d02b4f45\{ocr_raw_all.txt,ocr_ham.txt,ocr_raw_reads.jsonl}`
- KIZIL HAYAT: `E:\MITAS\DATABASE\KIZIL HAYAT 1996-0325-1-0000-00-1\{master_dilim\dilim_oneocr.txt, ocr\ocr-3d855acc\{ocr_ham.txt,ocr_raw_reads.jsonl}}`
- KURTLAR VADİSİ FİLİSTİN: `E:\MITAS\DATABASE\KURTLAR VADİSİ FİLİSTİN 2011-9138-1-0000-90-1\ocr\ocr-f0a1ec9a\{ocr_raw_all.txt,ocr_ham.txt,ocr_raw_reads.jsonl}`
- ÇİNGENE GÜVELERİ: `E:\MITAS\DATABASE\ÇİNGENE GÜVELERİ 1969-0032-1-0000-00-1\ocr\ocr-bce5145a\{ocr_raw_all.txt,ocr_ham.txt,ocr_raw_reads.jsonl}`
- VANYA DAYI: `E:\MITAS\DATABASE\VANYA DAYI 1989-0476-1-0000-00-1\{master_dilim\dilim_oneocr.txt, ocr\ocr-ee227bdb\ocr_raw_reads.jsonl}`
- BJ VE AYI: `E:\MITAS\DATABASE\BJ VE AYI 1978-0215-1-0000-00-1\ocr\ocr-968ad6c4\{ocr_raw_all.txt,ocr_ham.txt}`
- OneOCR kaynak (x-verisi mevcudiyeti kanıtı): `E:\MITAS\venvs\ocr\Lib\site-packages\oneocr.py:290-318`
- x-drop noktası: `E:\MITAS\OCR-worktree\py\20260601_pipeline100.py:38-47`