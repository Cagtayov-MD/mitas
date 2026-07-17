# MITAS 10-Eksen ÖN KOD DENETİMİ — wf_4fd64209-a40

axes=10/10, doğrulanmış CRITICAL/HIGH=6, çürütülen=0

## DOĞRULANMIŞ BULGULAR (detay)

### [MEDIUM] A1-jenerik-tespit (giriş/çıkış jenerik sınır tespiti)
**Video yolunda saniye hesabi stride/fps uyumsuzlugundan ~%4 sisiyor (end_sec gercek sureyi 30-40s asabiliyor)**

- Dosya: core/pipelines/ocr/jenerik_detector.py:769,533-534
- Detay: _sample_video stride=round(native/fps) TAM SAYI kullanir (25fps→stride=12→gercek dt=0.48s), ama _region_dict/_apply_ocr_refine saniyeyi sf/fps ile (fps=2.0→dt=0.5s) hesaplar. Sisme carpani 0.5/0.48=1.0417. Bu YALNIZ video yolunu (detect_from_video; canli pipeline _jenerik_detect.py --video) etkiler; kare-klasoru yolu (detect_from_frames) ffmpeg fps=2 ile dogru. KANIT (canli loglar): ANNE BOLEYN dur=7975s ama cikis end_sec=8013.3 (>sure!); FLASHDANCE dur=5600s ama cikis end_sec=5637.5 (>sure!). Her ikisinde de tespit edilen end_sec gercek film suresini asiyor — bariz hesap hatasi.
- Doğrulama: İddia GERÇEK — koda VE canlı çıktıya doğrulandı, çürütülemedi.

MEKANİZMA (kod): Canlı boru hattı _jenerik_detect.py'yi `--video --parallel` ile çağırır (scripts/mitas_pipeline.py:1314-1315) → detect_from_video → _sample_video. _sample_video stride'ı TAM SAYI olarak hesaplar: `stride = max(1, int(round(native/max(0.1,fps))))` (jenerik_detector.py:769). 25fps natif + fps=2.0 → round(12.5)=12 → gerçek örnekleme dt = 12/25 = 0.48s. Ama tüm saniye matematiği `window_start_sec + frame_index/fps` (=1/2.0=0.5s) kullanır: _region_dict satır 533-534, _select_region/near_miss 516, _apply_ocr_refine 657, _apply_ocr_refine_end 680. Şişme = 0.5/0.48 = 1.0417 (+%4.17). Yalnız native=25fps'te ciddi; 24/30/50fps'te 0.00%, 23.976/29.97'de -%0.10 (sayısal doğrulandı). 25fps PAL = TRT arşivinin baskın oranı,

### [HIGH] A7-eksik-kisi-koknedeni (oyuncu/yonetmen/yapimci NEDEN eksik — kod yollarinda kok-neden)
**Latin-disi (Kiril/Yunan/Arapca) cast+yonetmen credit_text_read'de SIFIRLANIR — qc_block'taki translit makinesi OLU**

- Dosya: scripts/credit_text_read.py:34-42 (_fold/_toks), :347-374 (_guard), :780-796 (_valid_person_name) ; scripts/credit_qc_block.py:415-437 (S2 translit) ; scripts/tek_film_kunye.py:614-615
- Detay: _fold() Latin-disi her harfi `[^a-z0-9 ]+`→bosluk ile siler: 'СЮЙМЕНКУЛ ЧОКМОРОВ'→'   ', _toks=[]. _guard TUM token'in OCR'da olmasini ister (Latin LLM ciktisi Kiril metinde yok → fire), _valid_person_name >=2 gercek-token ister (yok) → cast=[]. Yani non-Latin isimler credit_text_read'de TAMAMEN dusurulur. credit_qc_block'a (satir 614) beslenen vc.cast=[] oldugu icin S2'deki Kiril→Latin transliterasyon kodu (satir 415-437) cast/yon icin PRATIKTE HIC CALISMAZ (bos listeye uygulanir). SPOT-CHECK kaniti: CEMİLE (Aytmatov/Cemile, Sovyet-Kirgiz filmi) kunye.txt'de 'В РОЛЯХ :' (=Starring) altinda Suimenkul Chokmorov, Nasredin Dubasev, B.Beysenaliev acikca OCR'da OKUNDU; final PDF OYUNCULAR='?' (bos), _DURUM neden='qc_block: oyuncu yok'. Test ile dogrulandi: c._guard(['СЮЙМЕНКУЛ ЧОКМОРОВ'],...)=[] , Yunanca 'Ειρήνη Παπά'→'   '.
- Doğrulama: İddia GERÇEK ve doğrulandı — çürütülemedi. Her halka kod+çıktı ile teyit edildi.

1) MEKANİK ELEME (test edildi, salt-okunur): scripts/credit_text_read.py:34-37 _fold() `re.sub(r'[^a-z0-9 ]+',' ',...)` ile tüm Latin-dışı harfi boşluğa çevirir. Çalıştırdım: 'СЮЙМЕНКУЛ ЧОКМОРОВ'->'   ', _toks=[]; 'Ειρήνη Παπά'->'   ', _toks=[]. Sonuç: _guard(['СЮЙМЕНКУЛ ЧОКМОРОВ'],...)=[], _valid_person_name(...)=False, _only_persons([Kiril,Yunan])=[].

2) AKTİF KOD YOLU (flag-bağımsız, hep çalışır): vc.cast kaynağı read_credits_auto (tek_film_kunye.py:326). read_credits_auto çıktısı _guard (credit_text_read.py:1008-1010) VE _only_persons (1092-1094) süzgecinden geçer; ikisi de _fold/_toks kullanır → non-Latin isimler burada sıfırlanır. Latin-LLM-çıktısı durumunda da düşer: Kiril OCR'ın folded token kümesi B

### [HIGH] A7-eksik-kisi-koknedeni (oyuncu/yonetmen/yapimci NEDEN eksik — kod yollarinda kok-neden)
**Bos OCR cast'te kimlik web/title+year ile YANLIS filme kilitlenip yabanci kadro dolduruyor (OCR-otorite ihlali, PROPAGATION turu)**

- Dosya: scripts/credit_qc_block.py:471-489 (S3b web_identity), :562-572 (S7 KB-floor), :611-612 (method=='tmdb' karar)
- Detay: ÇILDIRIŞ ornegi: OCR icerigi acikca 'THE JACKET' (2005, Brody/Knightley) — subtitle dogru THE JACKET basildi. AMA credit_text_read guven=OKUNAMADI yon=[] dondurdu (OCR'da temiz cast-blok yok, hepsi crew/diyalog). qc_block kimligi web title+year (ÇILDIRIŞ) ile ALAKASIZ bir belgesele (Mathijs Poppe yon., Elisa Heene yap., cast=JAMAL/MONA/FARAH HINDAWI — Suriyeli aile belgeseli) kilitledi; S7 floor o filmin kadrosunu doldurdu. Final PDF: gercek-film THE JACKET subtitle'i ile yanlis-film kadrosu yan yana. method=='tmdb' → 'versiyon cast-teyitsiz' KONTROL'e gitti (iyi: yanlis>onayli engellendi) ama uretilen kunye tamamen yanlis kisi.
- Doğrulama: İDDİA GERÇEK — hem kodda hem ÇILDIRIŞ çıktısında doğrulandı.

KOD AKIŞI (scripts/credit_qc_block.py):
- OCR boş geldi: _log.jsonl 'credit_text_completed ... guven=OKUNAMADI yon=[]'; pdf_completed cast=0. OCR ham içeriği gerçekten THE JACKET (2005) — kunye.txt'de 'SECTION EIGHT PRODUCTION' (Clooney/Soderbergh prodüksiyonu), 'THE JACKET' başlığı + diyalog/crew satırları, temiz cast-blok YOK. Yani credit_text_read doğru davrandı (cast okunamadı).
- locked=False (S3 KB cross: cast_ov<2). Sonra S3b web_identity (satır 472-489) devreye girdi.
- web_identity ÇAPA-2/TMDB (credit_qc_gates.py:231-290): title-fold eşleşmesiyle kilitler (satır 282-290 _yfold(item_title)==_yfold(original/title)). OCR original='THE JACKET' → TMDB 'the jacket' aramasında HEM 2005 gerilim HEM Belçika/Suriye belgeseli 'The

### [MEDIUM] A7-eksik-kisi-koknedeni (oyuncu/yonetmen/yapimci NEDEN eksik — kod yollarinda kok-neden)
**Dizi/seri modunda cast credit_qc_block'ta 8'e zorla kirpiliyor — 'herkesi kapsa' kuralina aykiri**

- Dosya: scripts/credit_qc_block.py:369 (FILL_TARGET=8), :572 (cast=cast[:FILL_TARGET]) ; imza satir 375-380 'dizi' parametresi YOK ; tek_film_kunye.py:614-618 cagri dizi/profile gecmiyor
- Detay: credit_text_read.read_credits_auto dizi=True iken cast'i [:99] tutar (recall icin). AMA QC_BLOCK=1 canli oldugundan cikti credit_qc_block ile EZILIR; qc_block'un dizi parametresi yok ve cast'i kosulsuz cast[:FILL_TARGET]=cast[:8] keser (satir 572). tek_film_kunye satir 614 cagri ne profile ne dizi bayragi gecirir. Memory 'kunye_herkesi_kapsa': dizi modunda herkes listede olmali. Canli yolda dizi cast 8'e dusuyor.
- Doğrulama: İddia GERÇEK — çürütülemedi. Her teknik nokta kodda doğrulandı:

1) scripts/credit_qc_block.py:369 `FILL_TARGET = 8`; :572 `cast = cast[:FILL_TARGET]` → KOŞULSUZ 8-kırpma (dizi escape yok).
2) qc_credit_block imzası (credit_qc_block.py:375-380) `dizi`/`profile` parametresi İÇERMİYOR.
3) tek_film_kunye.py:614-618 çağrısı ne `dizi` ne `profile` geçiriyor.
4) Dizi recall'i ([:99]) ZATEN üretiliyor: credit_text_read.read_credits_auto:972 `extract_cast_block_candidates(lines, limit=(99 if dizi else 8))`; _pipe_credit_text.py:50-52 `dizi=(a.profile=="dizi")` geçiyor; mitas_pipeline.py:1618-1621 dizi profilini bu runner'a iletiyor → video_credits["cast"] dizi'de 99'a kadar isim taşıyor. Bu tam liste v4 çağrısına (mitas_pipeline.py:1834 `--video-credits`) → tek_film_kunye:312'ye akıyor.

EK BULGU 

### [HIGH] A8-eksik-afis-tur-ozet-orijinaltad
**Internet ozet fallback YALNIZ Kurtce'ye bagli — diger transcript-yok durumlari placeholder kaliyor**

- Dosya: E:/MITAS/scripts/mitas_pipeline.py:1728-1771
- Detay: mitas_pipeline.py:1728 `if asr_info.get('language') == 'ku':` _fetch_internet_ozet'i SADECE Kurtce-ailesi icin cagiriyor. ASR atlandi/bos/basarisiz olan AMA Kurtce-olmayan filmler (yabanci dil, --no-asr batch, ASR cokmesi) 1745 else dali -> 1768 transcript yoksa 1769 'ozet_atlandi: transcript yok' -> placeholder kalir. Internet ozet (TMDB plot, kimligi OCR ile dogrulanan) ASLA denenmez. Spot-check ÇILDIRIŞ tam bu: ana_dil EN (yabanci), ASR ATLANDI, log'da 'ozet_atlandi: transcript yok (ASR atlandi)', ozet=placeholder. OCR'da gercek orijinal ad 'THE JACKET' aciktan goruluyor — TMDB ile cekilebilirdi.
- Doğrulama: İddia GERÇEK, çürütülemedi. Kod kanıtı: E:/MITAS/scripts/mitas_pipeline.py:1728 `if asr_info.get("language") == "ku":` → _fetch_internet_ozet (1731) YALNIZ Kürtçe-ailesi için çağrılıyor. Else dalı (1745) → transcript yoksa 1768-1771 `transcript yok (ASR atlandi/bos) — ozet uretilmedi` log'u atıp 1727'de set edilen placeholder ozet'i bırakıyor. _fetch_internet_ozet'in TEK çağrı yeri 1731 (grep doğrulandı). _pipe_pdf.py:389 `--ozet`'i olduğu gibi kullanır; içinde internet/TMDB özet yedeği YOK (sadece 362-382 afiş yedeği). credit_qc_block.py özet üretmiyor. Yani Kürtçe-olmayan ama ASR atlanan/boş/yabancı filmlerde TMDB-plot (OCR-kimlik doğrulamalı) ASLA denenmiyor.

CANLI SPOT-CHECK (Database/ÇILDIRIŞ 2025-1142-1-0000-50-1): Ana dil=EN (yabancı), _DURUM.json asr_status=ATLANDI, yüzey .txt ve 

### [MEDIUM] A8-eksik-afis-tur-ozet-orijinaltad
**Bos/garble cast -> KB kimligi dogrulanamaz -> hem TUR hem ORIJINAL-AD hem AFIS birlikte dususuyor (tek kok)**

- Dosya: E:/MITAS/scripts/credit_kb_lookup.py:173-203,243 ; E:/MITAS/scripts/tek_film_kunye.py:649-650
- Detay: credit_kb_lookup.py:184'te title-only IMDb fallback KASTEN kaldirilmis: kimlik (matched_id veya okunan-yonetmen) dogrulanmadan imdb_id bos kalir -> TUR bos (credit_kb_lookup.py:187-203), afis kapisi (243 kimlik_dogrulandi=False) afis vermez, eslesen_film de kimlik-guclu degilse orijinal-ada gecmez (tek_film_kunye.py:650 _kimlik_guclu). Cast bos/garble oldugunda crosscheck cast_ortusme=0 + verdict!=TEYIT -> dort alan ZINCIRLEME duser. Spot-check ÇILDIRIŞ: ocr/kunye.txt cast bloku yok (altyazi+crew garble), surface 'Oyuncular: —', Tur:—, orijinal yok, yonetmen 'NİCOLAS MARİON' (gercek John Maybury degil=garble). Wikidata KADEME-B baslik+yil ile TUR kurtarabilirdi ama Turkce baslik 'ÇILDIRIŞ' + orijinal 'The Jacket' gecmedigi icin eslesmedi.
- Doğrulama: Iddiayi curutemedim — kod ve canli cikti birebir dogruluyor. ZINCIR KODDA GERCEK: (1) credit_kb_lookup.py:184-186 title-only IMDb fallback'i KASTEN kaldirilmis; kimlik dogrulanmazsa (matched_id yok + okunan yonetmen tutmaz) imdb_id bos kalir. (2) Bos imdb_id -> tur_imdb None (191-203) -> tur "—" (218,232). Wikidata KADEME-B fallback (88-122) imdb_id YOKKEN title match ister; "ÇILDIRIŞ" works_master label_tr'de yok + orijinal "The Jacket" XML'de yok (a.original=None) -> clause fire etmez -> tur kurtarilamaz (133 onaylar). (3) Afis kapisi 243 kimlik_dogrulandi=(verdict==TEYIT or cast_ortusme>=3) -> cast bos/garble -> False -> id verilmez -> afis yok. (4) tek_film_kunye.py:649-650 _kimlik_guclu ayni esik -> _orig_raw=a.original(None) or None -> orijinal-ad bos. ANA TETIK: crosscheck (credit_c


## SENTEZ RAPORU

Çıktılar mevcut. Sentez için yeterli kanıt elimde — eksen sonuçları zaten kod+çıktı doğrulamalı ve çekişmeli-doğrulama tamamlanmış. Raporu yazıyorum.

---

# MITAS 10-EKSEN KOD DENETİMİ — YÖNETİCİ ÖZETİ
**Tarih:** 2026-06-22 · **Kapsam:** Canlı 100-film koşusu (MITAS_QC2=1, QC2_WEB=1, QC_BLOCK=1, CREDIT_DETECT=1, JENERIK_DETECT=1, MASTER_PNG_AUTO=1, GEMMA_FULLCOVER=1, KB_CAST_ADD=1, QC_DIRECTOR_ANCHOR=1) · **Tür:** SALT-OKUNUR (hiçbir değişiklik yapılmadı/önerilmedi-uygulanmadı)

---

## 1) GENEL DURUM

Boru hattının **güvenlik mimarisi sağlam**: bu koşuda hiçbir eksende "sessiz yanlış-ONAYLI" üreten kritik bir kusur bulunmadı. Sistemin en üst kuralı olan **OCR-otorite** (okunanı başka isimle ezmeme) S4/S5/S7'de gerçekten korunuyor; QC1/QC_BLOCK kapıları additive+fail-safe; memory'de "açık" diye geçen üç tarihsel risk (`_v4j` UnboundLocalError, `_qc1_failed` ölü-kablo, K2 propagation/parse) **koda göre kapalı**. Çift-dedektör çakışması (denetimin merkez endişesi) **geçersiz** — yeni jenerik dedektörü ve eski OpusCreditDetector if/else ile birbirini dışlıyor. Buna karşılık sistemin **asıl zaafı doğruluk değil kapsam/recall**: Latin-dışı (Kiril/Yunan/Arap) filmlerde OCR mükemmel okusa bile cast+yönetmen tamamen siliniyor; boş/garble OCR'da TUR+orijinal-ad+afiş+özet zincirleme düşüyor; internet-özet yedeği yalnız Kürtçe'ye bağlı. Yani hata yapan değil, **eksik bırakan** bir sistem — ki bu doğru fail-safe tasarımının (yanlış>boş yerine boş tercih) bilinçli sonucu. 100-film koşusu için verdict: **üretime güvenli, ancak ONAYLI verimi düşük ve bu verim kaybının büyük kısmı yukarı-akış OCR recall'ı + birkaç genelleştirilmemiş yedek yoldan geliyor.**

---

## 2) DOĞRULANMIŞ CRITICAL/HIGH SORUNLAR (öncelik sıralı)

> Not: Hiçbiri CRITICAL'a yükselmedi. Sebep: tümü fail-safe yönünde düşüyor (yanlış teslim değil, KONTROL/boş). Aşağıdakiler doğrulanmış HIGH ve şiddeti yüksek MEDIUM'lar.

### H1 — Latin-dışı (Kiril/Yunan/Arap) cast+yönetmen tamamen siliniyor `[HIGH]`
- **Ne:** `credit_text_read._fold()` (`scripts/credit_text_read.py:34-37`) `[^a-z0-9 ]+`→boşluk ile her Latin-dışı harfi siler. `СЮЙМЕНКУЛ ЧОКМОРОВ`→`   `, `Ειρήνη Παπά`→`   `. `_guard` (anti-halüsinasyon, tüm token OCR'da olmalı) + `_valid_person_name` (≥2 token) bu yüzden fire eder → cast=[]. qc_block'taki Kiril→Latin **translit makinesi (`credit_qc_block.py:415-437`) ölü doğuyor** çünkü çağrı (`tek_film_kunye.py:614-618`) ona boş cast veriyor ve `raw_context_lines` hiç geçilmiyor.
- **Risk:** Arşivdeki tüm Sovyet/Yunan/Arap filmlerinin kadrosu+yönetmeni, OCR mükemmel okumuş olsa bile kalıcı kayboluyor. (Veri-bütünlüğü tehlikesi YOK — uydurma değil, KONTROL'e düşüyor.)
- **Çıktıda tespit:** `ocr/*/kunye.txt`'de Kiril/Yunan cast bloğu OKUNMUŞ ("В РОЛЯХ"/cast altı isimler) **AMA** final PDF/`_DURUM.json` "oyuncu yok"/Kontrol → teyit. Doğrulanan örnek: **CEMİLE 1998-0498** (OCR'da Suimenkul Chokmorov vb. var, `_DURUM` neden="qc_block: oyuncu yok" + "yönetmen okunamadı").

### H2 — Boş/garble OCR'da kimlik YANLIŞ filme kilitlenip yabancı kadro dolduruyor `[HIGH]`
- **Ne:** S3b `web_identity` TMDB title-fold eşleşmesiyle kilitler (`credit_qc_block.py:471-489`); `clip.json`'da yıl yoksa yıl-penceresi guard'ı atlanır → aynı-başlıklı yanlış film seçilir. S4+S7 o filmin yönetmen+cast'ini PDF'e yazar.
- **Risk:** Doğru-görünen altbaşlık + tamamen alakasız kadro → insan denetçiyi yanıltır. Doğrulanan örnek: **ÇILDIRIŞ** = OCR içeriği "THE JACKET" (2005, Brody/Knightley), ama kimlik bir Belçika/Suriye belgeseline (Mathijs Poppe yön., HINDAWI ailesi cast) kilitlendi; PDF Tür=BELGESEL + alakasız kadro yazdı.
- **Hafifletici:** `method=='tmdb'` → "versiyon cast-teyitsiz" → **KONTROL** (ONAYLI'ya sızmadı, kapı doğru çalıştı).
- **Çıktıda tespit:** `_DURUM.json` neden="versiyon cast-teyitsiz (web title+year kilidi)" olanlarda PDF cast'i `ocr/kunye.txt` ham içeriğiyle örtüşüyor mu bak — örtüşmüyorsa (HINDAWI gibi OCR'da hiç geçmeyen isim) yanlış-film kilidi.

### H3 — İnternet-özet fallback YALNIZ Kürtçe'ye bağlı `[HIGH]`
- **Ne:** `mitas_pipeline.py:1728` `if asr_info.get('language')=='ku':` → `_fetch_internet_ozet`'in TEK çağrı yeri. ASR atlanan/boş/yabancı-dil/Kürtçe-olmayan tüm filmler else dalında placeholder kalıyor; TMDB-plot (OCR-kimlik doğrulamalı) asla denenmiyor.
- **Risk:** Teslim kalitesi düşer (placeholder özet). Künye bütünlüğünü bozmaz, sessiz yanlış-veri yok (placeholder dürüst). Doğrulanan örnek: **ÇILDIRIŞ** (dil=EN, ASR ATLANDI, özet=placeholder, orijinal "THE JACKET" OCR'da açıkça var ama TMDB denenmedi).
- **Çıktıda tespit:** `_log.jsonl`'de "transcript yok (ASR atlandi/bos) — ozet uretilmedi" + ana dil≠ku olan filmlerde özet placeholder.

### H4 — Video yolunda saniye hesabı stride/fps uyumsuzluğundan ~%4 şişiyor `[MEDIUM, kanıtlı]`
- **Ne:** `_sample_video` stride'ı TAM SAYI (`jenerik_detector.py:769` `int(round(native/fps))`); 25fps+fps=2.0 → stride=12 → gerçek dt=0.48s ama tüm saniye matematiği 1/2.0=0.5s kullanıyor (`:533-534` vd.). Şişme = 0.5/0.48 = **+%4.17** (yalnız 25fps PAL'de; TRT arşivinin baskın oranı).
- **Risk:** `end_sec` gerçek süreyi aşıyor (kanıt: **ANNE BOLEYN** end_sec=8013>dur=7975; **FLASHDANCE** 5637>5600) → span/uzun-scroll kararları ve log doğruluğu bozuk; giriş tarafında geç-jenerikte -5s emniyet payı yenip açılışın ilk saniyeleri kesilebilir. Çıkış tarafı `min(dur,...)` clamp'iyle güvende.
- **Çıktıda tespit:** 25fps natif filmde `_log.jsonl` `credit_detect_closing` detail.end_sec > film süresi (asr_progress HH:MM:SS) ise teyit.

### H5 — Dizi/seri modunda cast 8'e zorla kırpılıyor `[MEDIUM]`
- **Ne:** `credit_qc_block.py:572` `cast=cast[:8]` KOŞULSUZ (dizi escape yok); imzada `dizi`/`profile` parametresi yok; çağrı (`tek_film_kunye.py:614-618`) geçmiyor. EK: `tek_film_kunye.py:633` `castU=upper_names(cast[:8])` QC_BLOCK kapalıyken DE 8'e sıkıyor — yani dizi `[:99]` recall'i SADECE LLM rol-eşlemeye yarıyor, nihai çıktıya 8'den fazla isim asla geçmiyor. `feedback_kunye_herkesi_kapsa` ile çelişiyor.
- **Risk:** Gerçek dizi bölümlerinde kadro eksilir. Hafifletici: TRT tip-0 etiketi bu veri setinde güvenilir "dizi" demek değil (REHİNELER/AMELIA/MAUDIE aslında uzun-metraj film, 8-cap istenen).
- **Çıktıda tespit:** Gerçek çok-bölümlü dizinin `ocr/*/kunye.txt`'sinde 8+ geçerli oyuncu okunup yüzey .txt cast'inin tam 8'e düşmesi.

---

## 3) EKSEN-EKSEN ÖZET

| Eksen | Hüküm | En önemli bulgu |
|---|---|---|
| **A1 jenerik-tespit** | SAĞLAM | Çift-dedektör çakışması YOK (if/else mutually-exclusive). Tek gerçek kod hatası: 25fps saniye-şişmesi → end_sec süreyi aşıyor (**H4**). |
| **A2 isim-kurtarma/master-PNG** | SAĞLAM (1 MEDIUM gözlem) | `tr_upper` WILLIAM→WİLLİAM bug'ı DÜZELTİLDİ; master-PNG metni BESLEMİYOR (çifte-kaynak yok). Kusur: master_png_* olayları `_log.jsonl`'a hiç yazılmıyor (surface_logs blok'tan ÖNCE çalışıyor, `mitas_pipeline.py:2203<2230`) → teşhis körlüğü. |
| **A3 gemma-eşleşme** | SAĞLAM | gemma yalnız VL-fallback (yön boş/cast<3), okunanı EZMEZ; ham-OCR teyit kalkanı (`_in_raw`) uydurmayı keser (JEFF TOWLES örneği). cast-anchored resolver (WIP) PASİF (0 caller). 2 LOW: FULLCOVER batch-merge KB-RED'siz; tek-model fuse mutabakat dalı ölü. |
| **A4 QC1** | SAĞLAM | `_v4j`/`_qc1_failed`/parse riskleri kapalı; sessiz ONAYLI üretmiyor. LOW: pipeline100 bucket'ında >300-satır bloat çapı yok (eski yolda var). |
| **A5 QC2/QC_BLOCK** | SAĞLAM | OCR-otorite invariant S4/S5/S7'de korunuyor; KB-floor yalnız kilitli+gerçek-cast. MEDIUM: S5 name_close_window fuzzy-snap tek teorik gedik (0.80 sıkı, riski düşük); director-anchor indekssiz tam-tablo scan (kilitsiz-film başına saniyeler, batch'i kilitlemez). |
| **A6 çıktı-yönlendirme** | SAĞLAM (2 MEDIUM) | karar↔teslim yapısal tutarlı, 0 yanlış-teslim (942 _DURUM tarandı). MEDIUM: 20/32 KONTROL filmi ETİKETSİZ (router `_sig` kalıpları gerçek reason string'lerine uymuyor → kontrol_tip=None); bayat AUTOFIX/eski alt-klasör _DURUM kayıtları. |
| **A7 eksik-kişi kök-nedeni** | KAPSAM SORUNU | Latin-dışı silme (**H1**) + yanlış-film kilidi (**H2**) + dizi 8-cap (**H5**); ortak kök = yukarı-akış OCR/cast recall. |
| **A8 eksik-afiş/tür/özet/orijinal-ad** | KAPSAM SORUNU | İnternet-özet yalnız-Kürtçe (**H3**); boş/garble cast → TUR+orijinal-ad+afiş zincirleme düşer (tek kök, kasıtlı-savunmacı title-only fallback kaldırması). |
| **A9 / A10** | (JSON'da kesik — eksen sonuçları A1-A8 tam, A9-A10 sağlanan veride truncate) | Sentez yalnız sağlanan tam-eksen verisine dayanıyor. |

> Uyarı: Sağlanan eksen-JSON'u A6'nın ortasında ve toplam listede kesilmiş; A9/A10 eksen başlıkları veride yok. Bu rapor A1-A8 (tam) + çekişmeli-doğrulanmış 6 bulguyu kapsar.

---

## 4) ÇIKTI DENETİMİNDE NEYE BAKMALI (film geldikçe kontrol listesi)

- **A1:** 25fps natif filmlerde `_log.jsonl` `credit_detect_closing.end_sec` ≤ film süresi mi? Aşıyorsa H4 teyitli. `_giris_start>0` filmlerde giriş kareleri gerçek jenerik başını kesiyor mu (görsel).
- **A2:** Yabancı-kadrolu filmin `kunye.txt`+yüzey .txt'sinde WILLIAM/MICHAEL'de İ YOK (ASCII I var). `master/master_manifest.json` var ama `_log.jsonl`'da `master_png_completed` YOK → gözlemlenebilirlik boşluğu.
- **A3:** `credit_vl_fallback` event'inde `vl_yon_kaynak='gemma4'` SADECE metin-yönetmeni boş filmlerde olmalı; yön dolu filmde ASLA. `vl_yon_hallucinated/vl_cast_hallucinated>0` → kalkan çalıştı.
- **A4:** `v4_finalize_failed/skipped` event'li filmde `_DURUM.json` yine üretilmiş + karar dolu (çökme yok). `credit_qc1_failed` event varsa neden listesinde "QC1 başarısız" + karar=Kontrol.
- **A5:** Yüzey .txt'te OCR'da OLMAYAN cast ismi varsa `kimlik.locked=True` ve gerçek-film cast'inde olmalı. Çıktı cast'inde OCR satırının KESİTİNE benzeyen ama tam-geçmeyen isim → same-title yanlış-kilit kontrolü.
- **A6:** `export/KONTROL/*.pdf`'te ` _` etiketi OLMAYAN dosya sayısı (şu an ~20) → router `_sig` kapsam eksiği. `_DURUM.json`'da karar=='AutoFix' → bayat kayıt.
- **A7:** Latin-dışı film: `ocr/*/kunye.txt`'de Kiril/Yunan/Arap cast okunmuş + final "oyuncu yok" → H1. `_DURUM` neden="versiyon cast-teyitsiz (web title+year kilidi)" → PDF cast'i OCR ile örtüşüyor mu → H2.
- **A8:** ana dil≠ku + ASR atlandı filmde özet=placeholder + OCR'da orijinal-ad açık → H3. Boş cast filminde Tür=—/afiş yok/orijinal-ad boş hep birlikte → tek-kök zincir.

---

## 5) ÇÜRÜTÜLEN YANLIŞ-ALARMLAR

Çekişmeli-doğrulama aşamasında **çürütülen bulgu YOK** (refuted listesi boş). Ancak şiddeti düşürülenler:
- **A1 saniye-şişmesi:** İlk işaretleme HIGH → **MEDIUM** (çıkış tarafı clamp'le güvende; somut zarar log-doğruluğu + nadir giriş-kesme).
- **A7 dizi 8-cap:** HIGH iddia → **MEDIUM** (tip-0 etiketi bu sette güvenilir "dizi" değil; çoğu örnek uzun-metraj, 8-cap istenen).
- **A8 boş-cast zincir-düşme:** HIGH → **MEDIUM** (title-only fallback kaldırması bug değil, yanlış-film zehirlenmesini önleyen bilinçli-savunmacı tasarım).
- **Memory'deki 3 "açık kritik":** `_v4j` çökme, `_qc1_failed` ölü-kablo, K2 propagation → hepsi **koda göre KAPALI**, artık geçerli değil.
- **"garble-gate ters predikat gerçek-ismi düşürür":** Yalnız `credit_qc.py is_garble`'da; o dosya pipeline tarafından **import edilmiyor** → aktif yolda risk yok.

---

## 6) GENEL EKSİK + DAHA İYİ İÇİN ÖNERİLER (yalnız gözlem, uygulama yok)

1. **Asıl darboğaz doğruluk değil RECALL.** ONAYLI veriminin düşüklüğü router/QC kapılarından değil, yukarı-akış OCR/cast-okuma kaybından (frame seçimi + stitch/clean + Latin-dışı fold). En yüksek getiri buradadır.
2. **Latin-dışı destek tamamen kopuk (H1).** `_fold`'un Kiril/Yunan/Arap'ı silmesi ile qc_block'taki translit makinesinin boş-listeyle çalışması birleşince Sovyet/Yunan/Arap arşivi sistematik kayıp; translit yolu ham-OCR metnine bağımsız erişemediği için ölü.
3. **Yedek-yolların genelleştirilmemiş olması:** internet-özet (yalnız-Kürtçe, H3) ve title-based kimlik (yalnız-yıllı, H2) tek-koşula bağlı; "transcript yok + kimlik doğrulanabilir" gibi genel koşullara açılmamış.
4. **Gözlemlenebilirlik boşlukları:** master-PNG olayları per-film log'a hiç düşmüyor (A2); 20 KONTROL filmi etiketsiz (A6); bayat _DURUM kayıtları re-sort'u yanıltabilir. Teşhis körlüğü = ileride sessiz regresyon riski.
5. **Kırılgan substring-eşleşmeler:** router `_sig` (A6) ve qc_block snap'leri (A5) tam-string'e bağlı; reason ifadesi tek kelime değişirse sessizce kapsam-dışı kalır.
6. **Çekişmeli kanıt değeri:** Bu denetimin en güçlü yanı — her HIGH bulgu hem kodda hem canlı çıktıda (CEMİLE, ÇILDIRIŞ, ANNE BOLEYN, FLASHDANCE) teyit edilebildi; bu pattern (kod-iddia → canlı-çıktı-teyit) devam eden çıktı denetiminde standart yapılmalı.

**Sonuç:** Boru hattı bu koşu için güvenli ve doğru-yanlış ayrımında titiz; iyileştirme ekseni **kapsam genişletme** (Latin-dışı, yedek-yol genelleştirme, OCR recall) + **gözlemlenebilirlik kapatma** üzerinde yoğunlaşmalı. Hiçbir değişiklik yapılmadı.