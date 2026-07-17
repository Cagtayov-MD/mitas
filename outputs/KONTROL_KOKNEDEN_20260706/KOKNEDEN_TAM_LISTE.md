# KONTROL — FILM-FILM TAM LISTE (kok-neden)

## 01:31:25 — 
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Jenerikte ana yonetmen kredisi fiziksel olarak yok gorunuyor (2nd Unit Director var, ana Director yok); _DURUM.json 'yönetmen garble (okunamadı)' diyor ama gorsel+OCR taramasi 'garble/okunamadi' degil

## 1900-0138 — 21. YÜZYIL EŞİĞİNDE TÜRK AİLESİ
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: 3 farkli OCR motoru (final kunye.txt, ham dilim_oneocr.txt, VL/gemma_kunye.json) ve 2 master frame (giris+cikis) hep ayni sonucu veriyor: yonetmen ibaresi jenerikte yok. Format itibariyle 'yonetmen' y
- **KIMLIK** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **NABI AVCI; AYŞE KARAMEHMET**
   - ipucu: Cast okunurdu (B degil, gorsel net) ama pipeline yanlis siniflandirma yapmis: teknik ekip 'Oyuncu' sayilmis, gercek sunucu ikilisi cast alanindan dislanmis -- classification/kategori hatasi, D_JENERIK

## 1933-0013 — YÜZYILIN CİNAYETİ
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Pipeline gercek acilis/kapanis jenerigini hic yakalayamamis; OCR sahne icindeki kapi levhasi ve viski etiketini 'kredi' sanmis. drop_stage=guard/garble_gate oncesi zaten kaynak yok.
- **KIMLIK** → E_VERI_YOK  — _VERI YOK_
   - ipucu: KB+Wiki+IMDb hicbir eslesme bulamamis (KAYNAK_YOK), web capasi kilitlenememis; kimlik kurulamadi hukmu OCR/CAST eksikligiyle de tutarli.
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Gercek acilis jenerigi videoda tespit edilememis/yakalanamamis oldugundan oyuncu isimleri kaynakta mevcut degil (D), OCR okuma hatasi degil.
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: _DURUM.json asr_status='failed', transcript_chars=null; transcript*.txt/chlang.json hic yok; final ciktida '(ÖZET AYRI BİR ADIMDA ÜRETİLECEKTİR.)' placeholder kalmis.
- **RENDER** → C_OKUNAMAZ  — _OKUNAMAZ (yabanci/bozuk)_
   - kod: `scripts/credit_text_read.py:1750-1796 (nonlatin_source tetikleyici) ; scripts/credit_qc_bl`
   - ipucu: Degisiklik gerekmiyor (fonksiyonel olarak dogru calisiyor): route etiketi zaten cok-nedenli KONTROL kararina katki olarak kullaniliyor ve kod isim uretmedigi icin sizinti riski yok. Istege bagli iyile

## 1942-0020 — LAUREL HARDY
- **YONETMEN** → A_ELENDI / `lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **ALFRED WERKER**
   - kod: `scripts/credit_text_read.py:1495-1548 (_yon_rescue_auto, ozellikle eski commit 8ffbb4a5'te`
   - ipucu: Bu belirli hata ZATEN duzeltildi (commit dd55c0ae, 2026-07-05 07:29, +2 pencere + _ROLE_VETO_F fuzzy rol-etiketi vetosu). Film sadece SAAT farkiyla (22:37 vs ertesi gun 07:29) eski koddan gecti. Aksiy
- **KIMLIK** → A_ELENDI / `deferans`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Cast listesi (Sheila Ryan, John Shelton, Don Costello, Elish**
   - ipucu: KB cross-check cast_ortusme=8/8 (otoriter_cast: Stan Laurel, Oliver Hardy, Dante, Sheila Ryan, John Shelton, Don Costello, Elisha Cook Jr., Edward Gargan) tam eslesiyor; kimlik.locked=true, imdb_id=tt

## 1942-0020 — LAUREL HARDY
- **YONETMEN** → A_ELENDI / `lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **ALFRED WERKER**
   - ipucu: _DURUM.json otorite_audit/trace_summary.md: KB cross-check dogru sekilde 'otoriter_yonetmen: Alfred L. Werker' buldu (ÇELİŞKİ verdict), ama credit_text extraction OCR'daki asil WERKER satirini degil '
- **KIMLIK** → B_OCR_OKUYAMADI / `cast_cap`  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **ROBERT EMMETT KEANE, RICHARD LANE, WILLIE BEST, LOU LUBIN**
   - ipucu: Ham OCR'da ve ikinci bir VL/gemma passinda (gemma_kunye.json) tum 14 isim mevcutken, ana pipeline'in credit_text/v4 extraction asamasi sadece ilk 9 ismi teslime tasidi (Robert Emmett Keane, Richard La

## 1954-0034 — KARA KALKAN
- **YONETMEN** → B_OCR_OKUYAMADI / `garble_gate`  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **Rudolph Maté (varsayim, filmin gercek yonetmeni)**
   - ipucu: _DURUM.json: qwen_qc.yonetmen_var=false, notlar='Yonetmen satiri bos'; credit_validate.qc_decision: status=OKUNAMADI, 'OCR bos -> doldurma yok'. Isim frame'de zayif okunur ama OCR hic yakalayamamis; f
- **KIMLIK** → B_OCR_OKUYAMADI / `garble_gate`  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **Tony Curtis, Janet Leigh, David Farrar, Barbara Rush, Herber**
   - ipucu: otorite_audit.raw_cap_dropped ~400 tekrarli/garble isim parcasi icerir (crawl-OCR gurultusu); KB cross-check cast-ortusme=0 -> 'kimlik kurulamadi'. Isimler framede okunur ama OCR harf-duzeyinde bozuk 

## 1955-0046 — ŞEYTAN RUHLU İNSANLAR
- **YONETMEN** → A_ELENDI / `lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **H.G. CLOUZOT (Henri-Georges Clouzot)**
   - kod: `scripts/credit_role_lexicon.py:29-64 (DIRECTOR listesi, 'DIRIGE PAR' satir 39, 2026-07-03 `
   - ipucu: Bu spesifik dosya icin: pipeline'i GUNCEL credit_role_lexicon.py (DIRIGE PAR dahil, commit d4df63f3+) ile YENIDEN CALISTIR (re-run/reprocess) -- kod fix'i zaten mevcut, sadece bu filmin DB kaydi eski/

## 1956-0062 — PROFESÖR HANNIBAL
- **YONETMEN** → D_JENERIKTE_YOK / `garble_gate`  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: _DURUM.json route.agir 'yonetmen garble (okunamadi)' diyor ama gercekte hicbir karede yonetmen jenerik yazi ekrani bulunamamis; OCR'daki tum parcalar sokak tabelalarinin (TITAN, AUTOMAT) bozuk okumasi
- **CAST** → D_JENERIKTE_YOK / `cast_cap`  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: raw_cap_dropped'daki 180+ 'isim' aslinda ayni bina tabelalarinin (Titan Epitoipari, Automat, Werboczi) tekrar eden bozuk OCR parcalari; gercek oyuncu ismi jenerik karede hic gorulmedi, bu yuzden cast_

## 1958-0044 — KOVBOY
- **KIMLIK** → A_ELENDI / `deferans`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **DELMER DAVES (yönetmen)**
   - kod: `scripts/_pipe_credit_validate.py:11-42 (xml_roles), scripts/credit_validate.py:254-343 (va`
   - ipucu: 1) mitas_pipeline.py:3155 'except Exception: pass' yerine dbg.emit(...,status='error') ekle (neden sessiz kaldigi gorunur olsun). 2) credit_video_read.KB.__init__ baglanti basarisiz oldugunda ayri bir
- **KIMLIK** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **DICK YORK, BRIAN DONLEVY (cast)**
   - kod: `scripts/_pipe_credit_validate.py:11-42 (xml_roles), scripts/credit_validate.py:254-343 (va`
   - ipucu: 1) mitas_pipeline.py:3155 'except Exception: pass' yerine dbg.emit(...,status='error') ekle (neden sessiz kaldigi gorunur olsun). 2) credit_video_read.KB.__init__ baglanti basarisiz oldugunda ayri bir

## 1958-0046 — BEKARLIK SULTANLIKTIR
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: jenerik_debug/detector/result.json ve detector_oneocr/result.json ikisi de status=not_found, reason='No persistent credit text cluster found'; credit_validate.yonetmen=OKUNAMADI, notes='OCR bos -> dol
- **KIMLIK** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - isim: **SE PIN YANG / PIN A DU (final PDF'e yazilmis, ancak kaynagi **
   - ipucu: KB cross-check verdict=KAYNAK_YOK, cast_ortusme=null, qc2_web='capa bulunamadi'. Ozetteki gercek karakter isimleriyle (Alberto/Elena/Otello/Toci) OCR cast'i (Se Pin Yang/Pin A Du) tamamen uyumsuz -> g
- **RENDER** → C_OKUNAMAZ  — _OKUNAMAZ (yabanci/bozuk)_
   - ipucu: qwen_qc alaninda 'latin_disi_alfabe_var:false' denmesi de bu tespiti destekliyor (final gorselde gercek yabanci alfabe yok); asil sorun OCR motorunun halusinasyon uretip bunu 'Latin-disi kaynak' olara

## 1959-0005 — BEKLENEN BOMBA
- **YONETMEN** → A_ELENDI / `garble_gate`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **MUHARREM GÜRSES**
   - ipucu: Ham OCR (ocr_ham.txt, ocr_raw_reads.jsonl) ismi dogru yakaladigi halde final kunye.txt'de sadece 'ESER VE REJİ' satiri kaldi, 'MUHARREM' ve 'GÜRSES' satirlari stitching/pipeline100 asamasinda dusurulm
- **KIMLIK** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **EŞREF KOLÇAK, NERİMAN KÖKSAL, HADİ HÜN, A.TARIK TEKÇE, HİKME**
   - ipucu: giris_jenerik_manifest.json bu isimleri 'kept/credit_line' olarak frame frame dogru tespit etmis (dedup_cluster'lar ile). Ancak final kunye.txt (ve debug_trace/artifacts/ocr/kunye.txt, ikisi ayni) ici

## 1960-0021 — BÜYÜK MÜCADELE
- **KIMLIK** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Kate Buffery / Bernard Archard / Howard Lew Lewis / Timothy **
   - ipucu: _DURUM.json neden[2] ve otorite_audit.raw_cap_dropped 296 satir listeliyor; final ciktida (1960-0021-1-0000-00-1 BÜYÜK MÜCADELE.txt/teknik.txt) sadece 10 oyuncu var (Kate Buffery...Andrew Burt) — cast

## 1960-0039 — BELL BOY
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: _DURUM.json neden: 'yönetmen doğrulama: okunamadı'; detector_oneocr cikis'ta metin bulmus (469-475) ama bu National Airlines reklami+THE END, yonetmen degil. Jenerik kart yok -> D.
- **KIMLIK** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: _DURUM.json: 'kimlik kurulamadı (cast-örtüşmesi 0) / yanlış-film şüphesi', vl_yon_aday=null, vl_cast_aday=null. OZET alani (kunye_teslim.md) dogru ve ASR transkriptiyle (Türkçe dublaj, Miami/bellboy/o
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: _DURUM.json: qwen_qc.oyuncu_sayisi=0, 'qc_block: oyuncu yok'; detector(paddle) 'No persistent credit text cluster found', detector_oneocr sadece THE END/reklam metnini yakalamis. Film (The Bellboy tar

## 1961-0005 — UTANMAZ ADAM
- **CAST** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **TÜRKAN SORAY**
   - kod: `scripts/credit_text_read.py:1837-1858 (LLM cagrisi + _guard), scripts/credit_qc_block.py:1`
   - ipucu: OCR-bolunmus isim-birlestirme (multi-line name stitching) extraction-LLM'e GITMEDEN once uygulanmali; ya da _romanize/_merge_split_names benzeri bir 'parcali-isim-toparlama' katmani SORAY+TÜRKAN+ARDUT
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **FAİK COŞKUN**
   - kod: `scripts/credit_text_read.py:1837-1858 (LLM cagrisi + _guard), scripts/credit_qc_block.py:1`
   - ipucu: OCR-bolunmus isim-birlestirme (multi-line name stitching) extraction-LLM'e GITMEDEN once uygulanmali; ya da _romanize/_merge_split_names benzeri bir 'parcali-isim-toparlama' katmani SORAY+TÜRKAN+ARDUT
- **CAST** → A_ELENDI / `guard`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **İSMET AY**
   - kod: `scripts/credit_text_read.py:1837-1858 (LLM cagrisi + _guard), scripts/credit_qc_block.py:1`
   - ipucu: OCR-bolunmus isim-birlestirme (multi-line name stitching) extraction-LLM'e GITMEDEN once uygulanmali; ya da _romanize/_merge_split_names benzeri bir 'parcali-isim-toparlama' katmani SORAY+TÜRKAN+ARDUT
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **CUMHUR KERSİN**
   - kod: `scripts/credit_text_read.py:1837-1858 (LLM cagrisi + _guard), scripts/credit_qc_block.py:1`
   - ipucu: OCR-bolunmus isim-birlestirme (multi-line name stitching) extraction-LLM'e GITMEDEN once uygulanmali; ya da _romanize/_merge_split_names benzeri bir 'parcali-isim-toparlama' katmani SORAY+TÜRKAN+ARDUT
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **İPEK ÖLÇEN**
   - kod: `scripts/credit_text_read.py:1837-1858 (LLM cagrisi + _guard), scripts/credit_qc_block.py:1`
   - ipucu: OCR-bolunmus isim-birlestirme (multi-line name stitching) extraction-LLM'e GITMEDEN once uygulanmali; ya da _romanize/_merge_split_names benzeri bir 'parcali-isim-toparlama' katmani SORAY+TÜRKAN+ARDUT
- **CAST** → A_ELENDI / `identity_unlocked`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **ABDURRAHMAN PALAY**
   - kod: `scripts/credit_text_read.py:1837-1858 (LLM cagrisi + _guard), scripts/credit_qc_block.py:1`
   - ipucu: OCR-bolunmus isim-birlestirme (multi-line name stitching) extraction-LLM'e GITMEDEN once uygulanmali; ya da _romanize/_merge_split_names benzeri bir 'parcali-isim-toparlama' katmani SORAY+TÜRKAN+ARDUT

## 1962-0022 — GERONIMO
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **KAMALA DEVI**
   - kod: `E:\MITAS\scripts\credit_text_read.py:1808-1886 (cap tanimi + cast_garble/cast_merged/cast_`
   - ipucu: cap-oncesi siralamayi 'ekran-sirasi/on-screen order' yerine 'billing-onemi/karakter-agirligi' ile yeniden sirala YA DA _cast_cap()'i credit_qc_block'taki 'introducing X' / 'and introducing' onek-etike

## 1962-1124 — IVAN'IN ÇOCUKLUĞU
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: OCR+VL ikisi de yonetmen=[] dondurmus (_log.jsonl: 'kunye-okuma(metin) ... yon=[]' ve 'gemma4 VL-fallback ... yon=[]'); jenerik segmentinde orijinal yonetmen kunyesi hic yer almiyor, drop degil yokluk
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: qwen_qc.oyuncu_sayisi=0 ve qwen_final_qc log kaydi da dogruluyor; jenerikte gercekten oyuncu blogu yok (versiyon cast-teyitsiz).
- **RENDER** → A_ELENDI / `garble_gate`  — _FIXLENEBILIR (framede var, elendi)_
   - ipucu: qwen_qc.latin_disi_alfabe_var=true + notlar='Afiş üzerinde Kiril alfabesi mevcut' dogru tespit; raw_cap_dropped ile bozuk/anlamsiz Latin parcalar garble_gate tarafindan zaten elenmis, final kunyeye si

## 1964-0002 — DİŞİ ŞEYTAN
- **YONETMEN** → E_VERI_YOK  — _VERI YOK_
   - isim: **NEVZAT PESEN**
   - ipucu: Bu alan aslinda A_ELENDI DEGIL: yonetmen bilgisi ham OCR+goruntude var ve final kunyede 'Yonetmen: NEVZAT PESEN' olarak dogru sekilde yazilmis (otorite_audit.ocr_dropped bos). Sema geregi bir dus/hata
- **OZET** → OZET_VAR_YANLIS_FLAG  — _YANLIS FLAG_
   - ipucu: Aslinda bir sorun tespit edilmedi: asr_status=done, 997 segment, transcript.txt Turkce ve tutarli diyaloglar iceriyor, final kunyedeki ozet ('MEYHANECİ MURAT...') bu transkriptle uyumlu; OZET_VAR_YANL

## 1967-0037 — MUTLU GÜNLER
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Giris jeneriginde director karti gercekten yok/taranmamis olabilir (cok tipik bicimde bu donem Amerikan filmlerinde director karti en sonda ayri gelir); cikis jenerigi hic islenmedigi icin orada olup 
- **YONETMEN** → E_VERI_YOK / `guard`  — _VERI YOK_
   - ipucu: Bu ikinci hukum, sistemin kendi karar zincirini yansitiyor: birincil OCR (video_kunye) motor=None ile HATA verdigi ve LLM(ollama) preflight basarisiz oldugu icin yonetmen alani hic degerlendirilememis
- **KIMLIK** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **GOOD TIMES (1967, Columbia Pictures, Sonny & Cher basrolde)**
   - kod: `scripts/_pipe_credit_text.py:78-87 (ocr_metni_yok erken-don); scripts/mitas_pipeline.py:22`
   - ipucu: mitas_pipeline.py:2941-2943'te iki farkli kok-nedeni (gercek CELISKI vs veri-yoklugu/OKUNAN_YOK) ayri reason metinleriyle ayirin (orn. 'kimlik celiskisi' yalniz verdict=='CELISKI' icin; 'kimlik kurula
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **GEORGE SANDERS, NORMAN ALDEN, PETER ROBBINS, KELLY THORDSEN,**
   - kod: `scripts/credit_text_read.py:444-458 (_cast_cap tanimi, calismadi cunku girdi bos) ve :1713`
   - ipucu: frames/giris_jenerik_manifest.json'daki 'kept' frame'lerin credit_lines/subtitle_lines alanlarini, ana OCR (ocr-cf7af2f9) HATA/0-satir durumunda FALLBACK kaynagi olarak _pipe_credit_text.py._find_ocr(
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: _DURUM.json: asr_status='failed', asr_segments=null, transcript_chars=null, neden listesinde 'özet yok/kısa (5k — gerçek özet üretilmemiş)'. ASR bellek hatasiyla tamamen crash oldugu icin transkript h

## 1968-0020 — DOĞUM GÜNÜ
- **OZET** → OZET_URETILEMEDI  — _ASR ARIZASI_
   - ipucu: ASR asamasi bellek yetersizligi (MemoryError) nedeniyle cokmus, 0 segment/0 karakter uretmis; transcript*.txt hic olusmamis (asr/asr-f21226ce/run altinda sadece _asr_16k.wav ve subtitle.json var, subt

## 1968-0082 — BANA TRINITY DERLER
- **YONETMEN** → A_ELENDI / `lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **E. B. CLUCHER**
   - kod: `scripts/credit_role_lexicon.py:29-64 (DIRECTOR listesi, 'DIRECTED BY' var ama yalin 'DIREC`
   - ipucu: (1) credit_role_lexicon.py DIRECTOR listesine yalin 'DIRECTED' (BY'siz) ekle VE/VEYA credit_text_read._rsc_label_fuzzy icindeki 'DIRECTED in tf and BY in tf' sartina 'veya sadece DIRECTED tek-basina t

## 1969-0032 — ÇİNGENE GÜVELERİ
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Ham OCR'da (ocr_ham.txt, kunye.txt, dilim_oneocr.txt) ve VL/GLM okumalarinda (gemma_kunye.json) YONETMEN/DIRECTED BY/DIRECTOR/REALISATION gibi hicbir ibare veya isim adayi bulunamadi; sadece MGM logos

## 1969-0091 — KOPAR ZİNCİRLERİNİ GÜLSARI
- **YONETMEN** → A_ELENDI / `cast_cap/lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **SERGUEÏ OUROUSSEVSKY**
   - kod: `scripts/tek_film_kunye.py:905-913 (KİŞİ-TEYİT bloğu) + scripts/credit_video_read.py:183-20`
   - ipucu: Director alanı için de cast'teki gibi bir fuzzy-KB/çift-imza kurtarma yolu (_fz_kb benzeri, JW-similarity + prefix eşleştirme) eklensin; ya da ekran-teyitli VL-crossline eşleşmesi (vl_yon_kaynak içind
- **KIMLIK** → A_ELENDI / `dublaj_filtresi`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **N. JANTOURINE, B. KYDYKEEVA, K. ALIEV, S. DJOUMADLOV, Y. SOL**
   - kod: `scripts/credit_text_read.py:1312-1336 (_valid_person_name / _only_persons, kritik satır 13`
   - ipucu: _valid_person_name() L1317: tek-harfli baş-token (örn. 'N.', 'B.') varlığında GERÇEK token sayısını 1'e düşürmesin — kural 'en az 1 çok-harfli soyad token + opsiyonel tek-harf ön-ek' olacak şekilde de

## 1969-0094 — KESS
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: _DURUM.json: vl_yon_aday=null, qwen_qc.yonetmen_var=false, route.agir=['YONETMEN','yönetmen garble (okunamadı)'], final .txt kunyesinde Yönetmen: — (bos); frame havuzu yonetmen kredisinin tipik geldig
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: _DURUM.json: asr_status=failed, asr_segments=null, transcript_chars=null; gercek transcript*.txt dosyasi hic yok; final .txt kunyesinde ozet alani '(ÖZET AYRI BİR ADIMDA ÜRETİLECEKTİR.)' placeholder m

## 1970-0046 — NORWOORD
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Ham OCR'daki 'garble' bir yonetmen adi degil, arka plandaki NYC metro/dukkan tabelalarinin OCR yanlis-okumasi (Cince/Tamil karakterleri dahil karisik gurultu); gercek jenerikte metin karti hic yok, fi
- **KIMLIK** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: route.agir'de 'kimlik kurulamadi (cast-ortusme 0) / yanlis-film suphesi' zaten dogru tespit; frame'lerde kimlik dogrulayacak yazi karti yok, KB cross-check icin gorsel kanit mevcut degil -> D_JENERIKT
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Cast bilgisi ne frame'de ne ham OCR'da mevcut; jenerik havuzunun 'found' isaretlemesi yanlis-pozitif (aslinda sokak-tabela sahnesi), gercek isim karti hic yok -> D_JENERIKTE_YOK, cast-cap/garble_gate 

## 1970-0061 — BAHAR VE ŞARAP
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Ham OCR 102 satirin hicbirinde YONETMEN/DIRECTOR/DIRECTED BY yok; sadece 'Director of Photography' (goruntu yon.) var - bu farkli bir unvan, yonetmenle karistirilmamali. drop_stage: guard (nonfilm_mar
- **KIMLIK** → A_ELENDI  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Spring And Port Wine (1970, Ingiliz filmi - Anglo Amalgamate**
   - kod: `E:\MITAS\scripts\mitas_pipeline.py:2937-2943 (reasons.append kimlik celiskisi); E:\MITAS\s`
   - ipucu: 1) Ollama model deposunu (gemma-4-31b-it-qat-vision:latest) yeniden yukle/onar, LLM-preflight'i pipeline basinda hard-fail yapip filmi tekrar kuyruğa al (mevcut fallback modelleri KULLANMA — qwen36-35
- **CAST** → A_ELENDI  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **James Mason, Susan George, Diana Coupland, Hannah Gordon, Ro**
   - kod: `E:\MITAS\scripts\credit_text_read.py:1580-1721 (read_credits_from_text; LLM exception -> o`
   - ipucu: Ayni fix: LLM modelini onar + yeniden kos. Ek olarak credit_role_lexicon.py CAST listesine (satir 79-86) OCR-garble-toleransli 'also starring/string/staring' varyantlarini esik-mesafeli (levenshtein) 
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: asr/asr-eadbfb0e/run altinda sadece _asr_16k.wav ve subtitle.json var; transcript*.txt veya chlang.json hic yok. subtitle.json icerigi: altyazili=false, oran=0.0, hits=0/total=60, guven=yuksek - yani 

## 1970-0076 — ŞAŞKIN REKLAMCI
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: _log.jsonl credit_validate kaydi: yonetmen.value=[] status=OKUNAMADI notes='OCR bos -> doldurma yok'; IMDB/Wiki KB de director=[] donmus. Kart fiziksel olarak jenerikte yok (garble degil, gercek eksik
- **KIMLIK** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **MARIE-CHRISTINE BARRAULT**
   - kod: `scripts/credit_text_read.py:1339 (_CAST_HEADER_RE tanimi — 'AVEC' eksik) ve scripts/credit`
   - ipucu: (1) _CAST_HEADER_RE deseinine Fransizca 'AVEC' (ve varsa 'AVEC LA PARTICIPATION DE' disinda salt 'AVEC' satiri) ekle — ancak 'avec la participation'/'avec le concours' gibi non-cast kaliplarla karisma

## 1971-0057 — RODEO TUTKUSU
- **KIMLIK** → A_ELENDI / `identity_unlocked`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **CLIFF ROBERTSON (oyuncu/J.W. Coop) - yonetmen karti bulunama**
   - ipucu: _DURUM.json: vl_yon_aday=null, kimlik kurulamadi (cast-ortusme 0). Cast net okunuyor ama yonetmen adi filmde ayri kart olarak gorunmuyor (D'ye yakin); KB'de J.W. Coop yonetmeninin Robert Culp oldugu b
- **CAST** → A_ELENDI / `garble_gate`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **CLIFF ROBERTSON, GERALDINE PAGE, CRISTINA FERRARE, R.G. ARMS**
   - ipucu: cikis_jenerik secim adimi (giris_jenerik_pool=0.01sn, cikis icin karsilik yok) bu end-credits karelerini hic yakalamamis; frame var+okunur+cast net ama sistemde secilip OCR'a girmedigi icin final'de k
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: _DURUM.json: asr_status=failed, transcript_chars=null, asr_segments=null. Final txt'de '(OZET AYRI BIR ADIMDA URETILECEKTIR.)' yazan placeholder var, gercek ozet hic uretilmemis; LLM/ollama katmani da

## 1971-0079 — ÖLÜM VURUŞU
- **YONETMEN** → B_OCR_OKUYAMADI / `guard`  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **HENRY HATHAWAY**
   - kod: `scripts/credit_validate.py:254-258 (validate_director erken-cikis) + scripts/tek_film_kuny`
   - ipucu: (a) credit_validate.validate_director icinde ocr_dir bos oldugunda bile xml_dir/imdb_res/wiki_res'i deger olarak DONDUR (status='OKUNAMADI_XML_MEVCUT' gibi ayri bir bayrakla) ki asagi-akis (tek_film_k

## 1973-0211 — BİR BEBEK EVİ
- **YONETMEN** → A_ELENDI / `lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Joseph Losey (OCR: 'Josaph Losay' / 'Joseph Losay')**
   - ipucu: OCR ham+VL(Gemma) ikisi de 'Joseph Losay'+'director' cift satirini net yakalamis; ama otorite_audit.raw_cap_dropped listesinde sadece gurultulu bigram varyantlari (Losay Cont/David/Michel/Rectow) var,

## 1975-0182 — BİR ZAMANLAR
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Jenerik (İngilizce 'OLD TIMES' TV-tiyatro performansi, muhtemelen BBC 'Performance' dizisi) yazar adi veriyor ama yonetmen kartini hic icermiyor; _DURUM.json'daki 'yönetmen garble (okunamadı)' notu is
- **KIMLIK** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **OLD TIMES (Harold Pinter, TV performansi - Malkovich/Nelliga**
   - ipucu: Sistem kimlik celiskisini dogru tespit etmis (kb cross-check, cast-ortusme 0, web capasi kilitlenemedi) - jenerik gercekten baska bir esere (Pinter'in 'Old Times'i) ait; TRT kaydi/kunye 'BİR ZAMANLAR'
- **CAST** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **JOHN MALKOVICH, KATE NELLIGAN, MIRANDA RICHARDSON**
   - ipucu: Cast frame'de VE ham OCR'da acikca var ve dogru okunmus (B degil), ama final kunyede '—' (bos) cikmis; muhtemelen KB cross-check bu isimleri 'BİR ZAMANLAR' (1975) filmiyle eslesmedigi icin (yabanci/fa
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: clip.json ve _DURUM.json ASR status='failed'/'partial' olarak isaretlemis, transcript_chars=null, asr_segments=null; ozet uretecek herhangi bir transkript metni mevcut degil, bu yuzden final kunyede '

## 1975-0185 — LIBERA SEVGİLİM
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - isim: **Roberto Loyola (yapimci/sunan olarak gecer, yonetmen degil)**
   - ipucu: Sistem 'yonetmen garble (okunamadi)' demis ama gercekte jenerikte yonetmen unvanli bir kredi yok; okunan 'Roberto Loyola presenta'/'Una Produzione' yapimci/sunum unvanidir, bu yuzden dogru hukum garbl
- **KIMLIK** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Giuseppe Tuminelli (9. oyuncu, final listede yok)**
   - ipucu: pdf/kunye_teslim.md Oyuncular listesinde sadece 8 isim var, Giuseppe Tuminelli hem ham OCR'da hem GLM-VL'de hem master PNG'de net okunur halde iken final ciktida kesilmis; qwen_qc.oyuncu_sayisi=8 bunu

## 1975-1016 — AYNA
- **YONETMEN** → D_JENERIKTE_YOK / `deferans`  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: _DURUM.json 'yonetmen garble (okunamadi)' diyor ama gorsel incelemede garble degil, jenerikte yonetmen karti hic yok; KB disaridan Andrei Tarkovski onerdi (otoriter_yonetmen) ama OCR/frame kaniti olma
- **CAST** → D_JENERIKTE_YOK / `KB_veto`  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: KB dis kaynak (TMDB/IMDb kilidi) otoriter_cast=['Margarita Terekhova','Oleg Yankovsky','Anatoly Solonitsyn', ...] onerdi, cast_ortusme=0; bu isimler framede/OCR'da dogrulanamadigindan dogru sekilde bo
- **RENDER** → A_ELENDI / `nonfilm_marker`  — _FIXLENEBILIR (framede var, elendi)_
   - kod: `scripts/credit_text_read.py:1750-1796 (nonlatin_source hesaplama, _nonlatin_ratio/_NONLATI`
   - ipucu: Mevcut davranis ZATEN guvenli/istenen (auto-ONAYLI asla verilmiyor, insan teyidi zorunlu). Iyilestirme onerisi: _DURUM.json'da qwen_qc.latin_disi_alfabe_var=false ile neden[]='Latin-dışı kaynak' ayni 

## 1975-2246 — DERSU UZALA
- **RENDER** → C_OKUNAMAZ  — _OKUNAMAZ (yabanci/bozuk)_
   - isim: **VLADIMIR VASILYEV (yon.) / YURIY SOLOMIN, MAKSIM MUNZUK, BOK**
   - ipucu: Kaynak jenerik Kiril; sistem bunu dogru okuyup ocr_ham.txt'ye Kiril olarak yazmis, sonra ayri bir romanizasyon adiminda (ocr/ocr-f8b0a69f/kunye.txt) ASCII'ye cevirmis (VLADIMIR VASILEV, MAKSIM MUNZUK,

## 1976-0179 — DÜNYANIN EN İYİ İNSANI
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Virginia Clay (Clav), Judith Nelmes**
   - ipucu: route.hafif=CAST_CAP_DUSEN dogru tespit: 9 kisilik cap nedeniyle en az 2 net-okunur oyuncu (Virginia Clay, Judith Nelmes) elenmis; karar KONTROL'e dusmus, bu dogru.
- **CAST** → A_ELENDI / `garble_gate`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Neville Marten, Donald Eccles, John Stuart (Clergyman)**
   - ipucu: OCR bu karede 3 gercek oyuncu adini o kadar bozuk okumus ki (Iarten/Lecles/Johistrast) isim-adayi bile uretilememis; final cap'a girme sansi hic olmadi -- garble_gate asamasinda elendi, cast_cap'tan o
- **CAST** → B_OCR_OKUYAMADI  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **Neville Marten / Donald Eccles / John Stuart tam ad eslesmes**
   - ipucu: Frame okunur durumda ama OCR ciktisi kullanilamaz derecede bozuk; bu 3 isim hicbir asamada dogru aday olarak uretilemedi (B_OCR_OKUYAMADI), cast_cap'tan bagimsiz bir kayip.
- **CAST** → A_ELENDI  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **-**
   - ipucu: Bu finding sadece dogrulama amacli: kalan 9 isim dogru ve kanitli; sorun sadece cap disina tasan fazladan gercek oyunculardadir (yukaridaki 2 finding).

## 1976-0184 — ANGOLA'DAN KAÇIŞ
- **YONETMEN** → A_ELENDI / `garble_gate`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **LESLIE MARTINSON**
   - ipucu: Yönetmen adı hem ham OCR'da hem master frame'de açıkça 'LESLIE MARTINSON' okunuyor; final kunye.txt ve teslim PDF/MD'de 'Yönetmen: —' olarak boş bırakılmış; sistem bunun yerine yanlışlıkla 'Ivan Tors'

## 1978-0215 — BJ VE AYI
- **YONETMEN** → B_OCR_OKUYAMADI / `guard`  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **BRUCE BILSON**
   - ipucu: Ham OCR (kunye.txt/ocr_ham.txt/dilim_oneocr.txt) DIRECTED BY/BILSON gecirmez; giris_jenerik havuzu yalnizca 14 kareyle asiri seyrek orneklenmis, bu kritik kredi karesi OCR motoruna hic girmemis/okunam
- **KIMLIK** → B_OCR_OKUYAMADI / `KB_veto`  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **8 yardimci rol oyuncusu okunmus (DENNIS FIMPLE, WOODROW PARF**
   - ipucu: Okunan 8 isim gercek ve framede/OCR'da dogrulanabilir (tali roller); ancak KB cross-check basarisiz oldugu ve ana-yildiz credit karti bulunamadigi icin kimlik nihai olarak kurulamamis -> KONTROL. Ana 

## 1978-0220 — KOLEKSİYON
- **YONETMEN** → A_ELENDI / `guard`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **MICHAEL ... (soyadı okunamadı; vl_yon_aday: Harold Pinter [y**
   - kod: `scripts/credit_role_lexicon.py:29-64 (DIRECTOR listesi, 'BY' yok); scripts/_pipe_credit_vl`
   - ipucu: DIRECTOR listesine yalin 'BY' (dusuk-oncelikli, cok-anlamli oldugu icin dikkatli) veya kart-bolunmus 'by\n<isim>' cross-line desenini _match_head'e ekle; VL-fallback icin _in_raw_detail fuzzy esigini 
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - kod: `scripts/credit_role_lexicon.py:29-64 (DIRECTOR listesi, 'BY' yok); scripts/_pipe_credit_vl`
   - ipucu: DIRECTOR listesine yalin 'BY' (dusuk-oncelikli, cok-anlamli oldugu icin dikkatli) veya kart-bolunmus 'by\n<isim>' cross-line desenini _match_head'e ekle; VL-fallback icin _in_raw_detail fuzzy esigini 
- **KIMLIK** → A_ELENDI / `lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **ALAN BATES (James), HELEN MIRREN (Stella)**
   - kod: `scripts/credit_qc_block.py:174-227 (_compute_otorite_audit, raw_cap_dropped uretimi) ve 87`
   - ipucu: raw_cap_dropped icin 2-token bitisik pencere yerine, ayni-kart bbox-y-araligi icinde COK-SUTUNLU jenerik satirlarini (karakter-adi sutunu vs oyuncu-adi sutunu) x0-koordinatina gore ayirip iki bagimsiz
- **KIMLIK** → B_OCR_OKUYAMADI  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **MAURICE O'CONNELL (yapimci olarak muhtemelen; cast degil)**
   - kod: `scripts/credit_qc_block.py:174-227 (_compute_otorite_audit, raw_cap_dropped uretimi) ve 87`
   - ipucu: raw_cap_dropped icin 2-token bitisik pencere yerine, ayni-kart bbox-y-araligi icinde COK-SUTUNLU jenerik satirlarini (karakter-adi sutunu vs oyuncu-adi sutunu) x0-koordinatina gore ayirip iki bagimsiz
- **RENDER** → C_OKUNAMAZ  — _OKUNAMAZ (yabanci/bozuk)_
   - ipucu: Frame gorsel olarak incelendiginde (c_0694.png) bu bolgede yalnizca cok kucuk, dusuk cozunurluklu, aydinlik gokyuzune gomulu bir Latin harfli tabela metni (GRANADA benzeri) var; Kiril/Yunan/Arap/CJK y

## 1978-0227 — TAKKELİ MELEK
- **KIMLIK** → A_ELENDI / `identity_unlocked / lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **GREG MCLEAN (yönetmen) / MICK VAN MOORSAL (oyuncu)**
   - ipucu: Final kunyede yazan yönetmen/oyuncu, filmin kendi (Kiril) jeneriğinden değil, cikis_jenerik'teki alakasız Avustralya film crew listesinden sızmış; guard/lexicon-anchor bunu elememiş, drop_stage=identi
- **RENDER** → C_OKUNAMAZ  — _OKUNAMAZ (yabanci/bozuk)_
   - ipucu: route.agir kaydı 'Latin-dışı alfabe (Kiril/Yunan/Arap/CJK) sızdı' doğrulandı; qwen_qc.latin_disi_alfabe_var=false olması QC'nin bunu kaçırdığını gösteriyor (QC yanlış negatif), gerçek görsel kanıt Kir

## 1979-0203 — SİBİRYADAN 2
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: _DURUM.json qwen_qc.notlar: 'Yonetmen satiri bos'; route.agir 'yonetmen garble' diyor ama incelenen frame'lerde yonetmen karti fiziksel olarak yok, garble olan SPERRZONE/cast kartlaridir; D_JENERIKTE_
- **RENDER** → A_ELENDI  — _FIXLENEBILIR (framede var, elendi)_
   - kod: `scripts/_pipe_ocr.py:1109-1125 (erken Kiril->Latin translit, translit_util.transliterate_m`
   - ipucu: (a) MITAS_CAST_CAP degerini bu tur cok-kalabalik-kadrolu (>10 rol-satiri tespit edilen) filmlerde otomatik yukseltmek icin V ROLYAKH/CAST blogundaki toplam aday sayisina gore dinamik cap (orn. min(tes

## 1980-0142 — ARTAN İSTEKLER
- **YONETMEN** → B_OCR_OKUYAMADI  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **Joe McGrath**
   - ipucu: Ana pipeline OCR motoru (pipeline100) ve VL-fallback (gemma4, log: 'yon=[] cast=5') yonetmen satirini hic yakalayamamis; ayni frame'i farkli bir OneOCR gecisi (master_dilim) dogru okumus -> motor/pipe
- **RENDER** → C_OKUNAMAZ / `garble_gate`  — _OKUNAMAZ (yabanci/bozuk)_
   - ipucu: Dusuk cozunurluklu dukkan-sahnesi objelerinden (dergi kapaklari, MILD BUTTER kutusu) OneOCR/ana-OCR halusinasyonu uretmis; gercek Latin-disi kaynak metin yok, bu yuzden qc_block 'romanizasyon insan te

## 1980-0149 — METİN
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Route'ta 'yonetmen garble (okunamadi)' denmis olsa da gercekte jenerikte hic yonetmen ibaresi/isim adayi yok; sorun garble degil, veri yoklugu -- route etiketi yanlis konumlandirilmis (garble_gate deg
- **KIMLIK** → D_JENERIKTE_YOK / `identity_unlocked`  — _YAPILAMAZ (jenerikte yok)_
   - isim: **ERSTE GESCHICHTE VON METIN**
   - ipucu: cast-ortusme 0 ve web-capasi kilitlenememesi jenerikte veri olmamasindan kaynaklaniyor; KB celiskisi jenerik goruntusunde degil disaridaki veritabani eslesmesinde -- gorsel kanitla D_JENERIKTE_YOK tey
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Cast bilgisi jenerikte hic bulunmuyor (D), OCR/VL okuma hatasi degil; final ciktida bos birakilmasi dogru davranis.

## 1981-0266 — KARAR KİMİN
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: asr_status=failed, transcript_chars=null, asr_segments=null; asr/asr-7914d47e/run icinde transcript*.txt yok, sadece subtitle.json var ve icerigi {"altyazili": false, "oran": 0.0, "hits": 0, "total": 

## 1981-0287 — JONSSON ÇETESİ
- **KIMLIK** → A_ELENDI / `identity_unlocked`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **ANDERS ÖSTRÖM; MATS WENNBERG (cast) — CHRISTJAN WEGNER (yöne**
   - kod: `scripts/credit_text_read.py:432 (PROMPT '...en fazla __CAP__...'), :444-458 (_cast_cap/_pr`
   - ipucu: MITAS_CAST_CAP varsayılanını (10) gerçek ekran-kanıtlı isim sayısına göre esnet VEYA prompt'a 'ekranda cap'ten fazla İSİM VARSA HEPSİNİ yaz, kesme LLM'in işi değil' talimatı ekle + cap'i yalnız Python

## 1983-0234 — REKABET
- **HAFIF** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Klasorde *afis*/*poster* deseniyle eslesen hicbir dosya bulunamadi (find sonucu bos); route.hafif=['AFIS'] ve teslim dosyasi adi '_HAFIF_AFIS.pdf' ile tutarli — afis gercekten hic uretilememis, bu bir

## 1984-0274 — MUTLU PASKALYA
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: vl_yon_aday=null, credit_text ve VL fallback (gemma4:26b) ikisi de bos donmus; jenerik segment tespiti muhtemelen yanlis zaman araligi (sahne) yakalamis, gercek jenerik kart hic bulunamamis.
- **KIMLIK** → E_VERI_YOK  — _VERI YOK_
   - ipucu: Kimlik kurulamama nedeni yonetmen+cast alanlarinin ikisinin de OCR/VL'de bos donmus olmasi; ayri bir 'yanlis film' kaniti yok.
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: vl_cast_aday=null; qwen_qc.oyuncu_sayisi=0; raw_cap_dropped cast_cap asamasinda dusen oge degil zaten isim degil, bu yuzden A_ELENDI degil D_JENERIKTE_YOK.

## 1984-0286 — ALTIN VE ŞÖHRET
- **YONETMEN** → C_OKUNAMAZ  — _OKUNAMAZ (yabanci/bozuk)_
   - ipucu: OCR ham cikti (MKRKTE/CHE/ISMI/CHER) frame'deki gercek soluk metinle uyumlu ama alfabe/harf ayirt edilemiyor; kaynak kaydin asiri karanlik/dusuk kontrastli VHS transferi kok neden.
- **KIMLIK** → C_OKUNAMAZ  — _OKUNAMAZ (yabanci/bozuk)_
   - ipucu: Kimlik kurulamamasinin nedeni cast-metninin okunamamasidir (fiziksel goruntu bozuk); veri yoklugu degil, okuma engeli.
- **CAST** → C_OKUNAMAZ  — _OKUNAMAZ (yabanci/bozuk)_
   - ipucu: Cikista jenerik hic yok (D benzeri), giriste fiziksel olarak okunamaz metin var (C); en dogru hukum giristeki gercek-ama-okunamaz metin oldugundan C_OKUNAMAZ verildi, cast_cap/guard kaynakli bir ELEME

## 1985-0223 — AMANSIZ TAKİP
- **YONETMEN** → A_ELENDI / `lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **洪金寶 / HONG JIN BAO (Hung Kam-bo / Sammo Hung)**
   - ipucu: Isim hem framede hem ham OCR'da (CJK ve pinyin-romanize halde) mevcut; final kunye_teslim.md 'Yönetmen: —' cikmis ve qwen_qc.yonetmen_var=false — Latin-disi/Kanton kaynak oldugu icin insan-teyid gate'
- **KIMLIK** → A_ELENDI / `cast_cap_dusen`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **洪金寶(HONG JINBAO), 成龍(CHENG LONG), 元彪(YUAN BIAO), 楊紫瓊 vb. + G**
   - ipucu: Cast isimleri hem framede hem OCR'da okunur durumda (B/D degil); sorun KB-dogrulama/web-capasi kilitlenememesi ve 'Twinkle Twinkle Lucky Stars' (1985 HK filmi) ile 'AMANSIZ TAKİP' etiketi arasindaki o
- **RENDER** → A_ELENDI / `guard`  — _FIXLENEBILIR (framede var, elendi)_
   - ipucu: Latin-disi (CJK/Kanton) alfabe pipeline gard'i tarafindan tespit edilip finale dogrudan CJK olarak degil pinyin-romanize (ör. 'YING GUO JIN JUN FU KE LAN QUN DAO') olarak aktarilmis; route.agir bunu '

## 1985-0256 — OTOPARK
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Sistem trace log'unda (debug_trace/trace_summary.md) credit_text.candidate_read asamasindan itibaren yonetmen alani zaten bos array ('yonetmen': []) donuyor; credit_validate notu 'OCR boş → doldurma y

## 1986-0240 — VİDEO OYUNU
- **HAFIF** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Klasorde afis/poster dosyasi (glob *afis*, *poster*) hic bulunamadi; route.hafif=["AFIS"] karari zaten bu eksikligi dogru tespit etmis; poster_fetch adimi bu kayit icin afis uretmemis/getirememis.

## 1986-0264 — KUĞUNUN ŞARKISI
- **YONETMEN** → A_ELENDI / `garble_gate/identity_unlocked/lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **张泽鸣 (Zhang Zeming) — 编剧/导演 (senarist/yönetmen) etiketiyle**
   - ipucu: Yönetmen adı hem framede hem ham OCR'da acikca var (Zhang Zeming / 张泽鸣); final kunyede '—' cikmis. Pipeline CJK alfabeyi guvenilmez sayip yonetmeni bos birakmis; guard/garble_gate veya identity_unlock
- **KIMLIK** → A_ELENDI / `lexicon_anchor_misparse/cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **孔宪珠, 陈锐, 冯狄青, 刘倩仪, 黎剑筠, 莫少鹰, 梁玉瑾 (gercek cast tablosu, '演员表'**
   - ipucu: Final kunyede cast olarak 'XIA TIAN XI, BU TIAN XI TU, XING LONG SHE HUO, WAN SHE' yazilmis; bunlar gercek cast tablosuyla (satir 93-118) hic alakasiz — ocr_ham.txt satir 5-7/16-18'deki bozuk/garble k
- **RENDER** → E_VERI_YOK  — _VERI YOK_
   - ipucu: RENDER icin 'sizinti' iddiasi ham OCR/ara-veri seviyesinde dogru (CJK yogun) ama incelenen final render ciktisinda (PDF onizleme) sizinti gozlemlenemedi; hangi ara-urunde (ör. video_kunye/v4 rapor JSO

## 1986-0334 — AĞAÇ
- **HAFIF** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: _DURUM.json: route.hafif=['AFIS'], qwen_qc.afis_var=false, qwen_uyari='afis yok (deterministik poster_fetch garanti - uyari)'. Kaynakta (giris/cikis master + 11 jenerik kare) afis gorseli hic uretilme

## 1987-0352 — TILSIMLI DÜNYA
- **KIMLIK** → A_ELENDI / `identity_unlocked`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **CARL MACEK (gercek yonetmen) vs teslimde GREG SNEGOFF (yanli**
   - kod: `scripts/credit_role_lexicon.py:232-240 (take_adjacent, 2-satir penceresi) + scripts/_pipe_`
   - ipucu: credit_role_lexicon.take_adjacent icindeki sabit (i+1,i+2) penceresini role-turune gore genislet (ornegin EXECUTIVE PRODUCERS/PRODUCERS gibi coklu-isim basliklarinda yeni bir rol-basligina/ROLE_WORDS'

## 1987-1235 — ÇÖL ASLANI
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **ROD STEIGER, JOHN GIELGUD, ROBERT BROWN, RODOLFO BIGOTTI/BIG**
   - kod: `scripts/credit_qc_block.py:754 (S7 hard-cut) + scripts/credit_qc_block.py:489-495 (_cast_c`
   - ipucu: cast_cap oncesi OCR-okuma sirasi 'ekrandaki sira' degil rastgele/model-cikti sirasi olabilir; onem/screen-time siralamasi yoksa ekrandaki ilk-14 isimden ilk-10'u alinir. Cozum: cap uygulanmadan once '

## 1988-0420 — LA BOHEME
- **YONETMEN** → A_ELENDI / `guard/nonfilm_marker`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **LUIGI COMENCINI**
   - kod: `scripts/mitas_pipeline.py:1974-2126 (ocr_bucket=HATA atamasi); scripts/_pipe_credit_text.p`
   - ipucu: (a) _pipe_ocr.py'de OneOCR/GPU native-crash sonrasi communicate() basarili donup bos stdout birakma senaryosuna karsi ayrik bir 'crash-detected' bayragi + retry/CPU-fallback eklenmeli; (b) mitas_pipel
- **CAST** → A_ELENDI / `guard/nonfilm_marker`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **BARBARA HENDRICKS (Mimi), JOSE CARRERAS (Rodolfo), LUCA CANO**
   - kod: `scripts/_pipe_credit_text.py:76-87 (out={cast:[],guven:OKUNAMADI,hata:ocr_metni_yok}); scr`
   - ipucu: YONETMEN ile ayni kok-fix: OCR subprocess crash-toleransi + master_dilim/ham-OCR alternatif kaynaginin credit_text asamasina zamaninda (final PDF'den ONCE) ulastirilmasi. Ek olarak: otorite_audit.ocr_
- **OZET** → OZET_URETILEMEDI  — _ASR ARIZASI_
   - ipucu: asr_status=failed, transcript_chars=null; asr/asr-84a9cce5/run altinda transcript*.txt/chlang.json yok, sadece dublaj-altyazi tespiti (subtitle.json) ve ham ses var. Final kunyede 'OZET AYRI BIR ADIMD

## 1988-0423 — BUL VE YOK ET
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - isim: **J. CHRISTIAN INGVORDSEN (Screenplay/Produced by olarak gecen**
   - ipucu: _log.jsonl kayitlarinda (evt-13a2f8c0d702, evt-6082d9037413, evt-70b85808f5d6) hem OCR hem gemma4 VL-fallback yon=[] (bos) donmus, QC1-RED yon=BOS; bu sistem davranisi gorsel bulguyla tutarli: jenerik

## 1988-0425 — İŞTE BIRD
- **HAFIF** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Afis frame/OCR kaynakli degil; KB/harici poster_fetch 'KAYNAK_YOK' donduğu icin uretilememis. E:\MITAS\_102_afis_cache klasorunde bu TRT icin (1988-0425-1-0000-00-1.jpg) dosya yok, sadece yanlislikla 

## 1988-0430 — LALELER
- **YONETMEN** → B_OCR_OKUYAMADI / `guard`  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **STAN FERRIS**
   - ipucu: OCR pipeline tamamen HATA (ocr_bucket=HATA, ocr_lines=0, ./ocr/ocr-78848edc bos) oldugu icin ana OCR yolu isim hic goremedi; ancak paralel master_dilim/dilim_oneocr.txt motoru ayni ismi dogru yakalami
- **KIMLIK** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **LALELER / TULIPS (1981, Bennett Films-Astral Bellevue Pathe)**
   - kod: `scripts/mitas_pipeline.py:131-138 (last_json), scripts/mitas_pipeline.py:2086-2113 (ocr_bu`
   - ipucu: (1) _pipe_ocr.py neden sessizce 0 JSON-satiri uretip crash oldugunu ayri kok-neden olarak arastir (94.2sn suruyor ama stderr bos -> muhtemelen PaddleOCR/ana motor icinde yutulan istisna ya da stdout/s
- **CAST** → B_OCR_OKUYAMADI / `cast_cap`  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **GABE KAPLAN, BERNADETTE PETERS, HENRY GIBSON, AL WAXMAN, DAV**
   - ipucu: _DURUM.json 'qc_block: oyuncu yok' ve AGIR listede 'CAST: oyuncu yok' diyor; ana OCR HATA verdigi (0 satir) icin cast_cap/guard hicbir aday gormeden yok sonucuna varmis - gercek cast dilim-OCR'da ve g
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: asr klasorunde sadece subtitle.json (altyazi-var-mi testi) ve ham _asr_16k.wav var; transcript*.txt/chlang.json hic uretilmemis, _DURUM.json asr_status=failed ve transcript_chars=null - gercek konusma

## 1988-1557 — İKİ KOCALI KADIN
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **YVAN CHIFFRE, LIONEL VITRANT, JEAN-MARIE LANCELOT, JULIEN GU**
   - ipucu: Frame ve OCR'da net var ama final kunye_teslim.md Oyuncular listesinde yok; cap=10 siniri framede olmayan isimlerce dolduğu icin bunlar disarida kaldi.
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - isim: **ALAIN DELON, PAUL MEURISSE, NATHALIE DELON**
   - ipucu: Ham OCR'da var ama jenerikte gorsel karsiligi yok; buna ragmen final Oyuncular listesine dahil edilmis ve gercek isimlerin cap disi kalmasina sebep olmus.
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **PHILIPPE CASTELLI**
   - ipucu: Final ciktida mevcut ve dogru; sadece raw_cap_dropped listesinde tekrarli bozuk varyantlari sayilmis, bilgi amacli.

## 1988-1835 — KURUNTULAR
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **KENNETH BELTON**
   - kod: `scripts/credit_qc_block.py:754 (cast = cast[:_cast_cap()]) ve scripts/credit_qc_block.py:4`
   - ipucu: Eger Kenneth Belton gibi net/temiz-okunan (garble olmayan, ham-OCR'da tek-blokta ardisik) isimlerin PDF'e girmesi isteniyorsa MITAS_CAST_CAP degerini artirmak (ör. 12) ya da credit_qc_block.py:754'tek

## 1989-0476 — VANYA DAYI
- **YONETMEN** → A_ELENDI / `guard`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Евгений МАКАРОВ (Yevgeni Makarov)**
   - ipucu: _DURUM.json route.agir: 'yönetmen garble (okunamadı)' diyor ama hem ham OCR hem master goruntude Rejisor adi acikca Kiril alfabede okunur halde mevcut; Latin/translit beklentisi yuzunden guard/lexicon
- **RENDER** → C_OKUNAMAZ  — _OKUNAMAZ (yabanci/bozuk)_
   - ipucu: _DURUM.json route.agir: 'Latin-dışı alfabe (Kiril) sızdı', qwen_qc.latin_disi_alfabe_var=true, notlar='Afişte Kiril alfabesi mevcut' - dogrulandi; 1986 Sovyet/Leningrad TV yapimi oldugu icin orijinal 

## 1989-0478 — TOPLU GÖSTERİLER
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **KIM NOVAK, REX THOMPSON, JAMES WHITMORE, VICTORIA SHAW, TYRO**
   - kod: `scripts/credit_qc_block.py:840-864 (CAST_CAP_DUSEN blogu) + scripts/credit_qc_block.py:123`
   - ipucu: CAST_CAP_DUSEN sinyali (_audit_raw_token_seq bigram-tarama) satir-siniri-farkinda hale getirilmeli: (1) bigram'lar SADECE ayni satir icinde veya ardisik iki satir arasinda (ad+soyad ayri satirlarda) o

## 1989-0570 — BİR YAZ MACERASI
- **KIMLIK** → E_VERI_YOK  — _VERI YOK_
   - isim: **ANDRE MELANÇON (yonetmen); FEDERICO HECTOR ALTERIO, ANA CHIN**
   - ipucu: _DURUM.json route.agir=KIMLIK, neden: 'kimlik kurulamadi (cast-ortusme<2, web capasi kilitlenemedi)' + 'CAST_CAP_DUSEN: cap-ustu okunan 986 oyuncu dustu'; vl_yon_aday/vl_cast_aday=null yani web/KB dog

## 1989-0955 — ÖLDÜRME ZAMANI
- **YONETMEN** → D_JENERIKTE_YOK / `lexicon_anchor_misparse`  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: giris_jenerik_manifest.json'da g_0110.png 'kept/credit_line' olarak isaretlenmis ve OCR 'கதிதில' (Tamil script) okumus; frame'i buyutup incelediginde bu bir aktorun agiz/dis bolgesi, hicbir yazi yok -
- **KIMLIK** → D_JENERIKTE_YOK / `cast_cap`  — _YAPILAMAZ (jenerikte yok)_
   - isim: **Andrea Riva (yanlislikla cast sayilmis, gercekte 'arredament**
   - ipucu: _DURUM.json otorite_audit.raw_cap_dropped listesinde onlarca isim var (Gastone di Giovanni, Sergio Martinelli, Carlo Tafani, Silvano Giusti, Albino Morandin, Mario Barboni, Enzo Mazzucchi) ama hepsi c

## 1990-0285 — TOPLU GÖSTERİLER
- **YONETMEN** → E_VERI_YOK  — _VERI YOK_
   - isim: **VINCENTE MINNELLI (OCR: VincenTe Minnati/minneti/Minnerti)**
   - ipucu: Bu klasorde _DURUM.json hic yok; debug_trace/trace.jsonl'da credit_text asamasi 'status: error, [Errno 22] Invalid argument' ile cokmus (19:51 civari) -> final KB-onayli/normalize YONETMEN karari hic 
- **KIMLIK** → B_OCR_OKUYAMADI  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **DEBORAH KERR, JOHN KERR, LEIF ERICKSON, EDWARD ANDREWS, DARR**
   - ipucu: Cast hem gorselde hem ham OCR'da (ocr_raw_all.txt) hem de final kunye.txt'de dogru ve tutarli sekilde mevcut (D_JENERIKTE_YOK degil, cast bol ve net). Ancak final structured DURUM.json/route/otorite_a

## 1990-0321 — MOSKOVA BUZ BALESİ
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: _DURUM.json route.agir='yönetmen garble (okunamadı)' ve vl_yon_aday=null; jenerikte yonetmen kredi karesi fiziksel olarak yok, kart sadece film adini iceriyor.
- **KIMLIK** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Kimlik alani ayrik bir credit karesine dayanmiyor; cast-örtüşme 0 oldugu icin KB ile eslesme kurulamamis -- kanit yetersizligi D_JENERIKTE_YOK'u destekliyor, E_VERI_YOK sinirinda.
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: qwen_qc.oyuncu_sayisi=0 ve otorite_audit.raw_cap_dropped listesi (364 satir) ayni sponsor-pano tekrarlarindan olusuyor; gercek cast credit karesi jenerikte yok.
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: asr/asr-ab5b97dc/run/transcript.txt ve transcript_plain.txt tamamen bos; chlang.json: 'select_reason':'ses yok → dil belirlenemedi', tum kanallar confidence 0.0 role='efekt/sessiz'; kunye_teslim.md Oz

## 1990-0336 — ZAMAN VE RÜZGAR
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **JOSE DE ABREU, DANIEL DANTAS, DIOGO VILELA, ODILON WAGNER, G**
   - ipucu: Final PDF/md Oyuncular listesi sadece ilk 10 ismi iceriyor (TARCISIO MEIRA...MARIO LAGO, ELOISA MAFALDA ile bitiyor); route.hafif=[CAST_CAP_DUSEN] ve qwen_qc.oyuncu_sayisi=10 sabit-tavan kanitiyla dog

## 1990-0350 — DENİZ EJDERİ
- **YONETMEN** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **AUGUST GUDMUNDSSON**
   - kod: `scripts/tek_film_kunye.py:489-501 (drop noktasi) + scripts/credit_crosscheck.py:23-29 fold`
   - ipucu: credit_crosscheck.py fold() fonksiyonuna (satir 23-29) Izlandaca/Faroece ozel harfleri ekle: ð/Ð->d, þ/Þ->th, ayrica NFKD-decompose OLMAYAN diger Latin-genisletilmis harfleri (æ/Æ->ae, ø/Ø->o vb.) kap

## 1990-0390 — SISSI-1
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: _DURUM.json: asr_status=failed, asr_segments=null, transcript_chars=null; asr\asr-4516ca02\run\subtitle.json sadece {altyazili:false, hits:0, total:60} altyazi-varlik testi, gercek transkript dosyasi 

## 1990-0403 — TOPLU GÖSTERİLER
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: ASR klasorunde (asr-681de05d/run) sadece ham _asr_16k.wav ve subtitle.json (altyazi-tespit, 'altyazili': false, 'hits': 0, 'ornekler': []) var; gercek transcript*.txt veya chlang.json hic uretilmemis;

## 1990-0488 — HAYALET BABAM
- **YONETMEN** → E_VERI_YOK  — _VERI YOK_
   - isim: **SIDNEY POITIER**
   - ipucu: HUKUM DUZELTME: bu aslinda A_ELENDI/D/vb degil basarili bir tespit -- final kunye_teslim.md'de 'Yonetmen: SIDNEY POITIER' dogru yazili, ham OCR ve gorsel tam uyumlu, alan sorunsuz uretilmis (karar='Ha

## 1990-0519 — TEPEDEKİ KIZ
- **YONETMEN** → C_OKUNAMAZ / `garble_gate`  — _OKUNAMAZ (yabanci/bozuk)_
   - ipucu: Otomatik dedektor (paddle+oneocr) her iki motor de 720 cikis karesinde 'not_found/no_frames' verdi; ham OCR bozuk parcaciklar uretti ama isme baglanamadi; vl_yon_aday=null. Yeniden-okuma (yuksek cozun
- **KIMLIK** → D_JENERIKTE_YOK / `identity_unlocked`  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: cast-ortusme=0, KB cross-check celiskili; web-capasi kilitlenemedi. Final kunyede kimlik alani tamamen bos (-), ozet ASR-kaynakli (Tom/Angelina/Benson) ama bu kunye kaniti degil.
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Ham OCR'da (ocr_ham.txt, kunye.txt) tek bir Latin-alfabe oyuncu adi yok; sadece Cince/Tamil/Ibranice karakterler ve bozuk parcaciklar (Bikini, FUMCAS, LYC) var, isim formatinda degil.
- **RENDER** → A_ELENDI / `nonfilm_marker`  — _FIXLENEBILIR (framede var, elendi)_
   - kod: `scripts/credit_text_read.py:1750-1796 (nonlatin_source uretimi) -> scripts/credit_qc_block`
   - ipucu: Bulgu dogru; duzeltme gerekmiyor. Yalnizca raporlama/gorunurluk icin: _DURUM.json'da iki farkli 'Latin-disi' sinyali (qwen_qc.latin_disi_alfabe_var = final-PDF gorsel-QC katmani; qc_block nonlatin_sou

## 1991-0355 — PARİS'İN DIAGHILEV İLE DANSI
- **RENDER** → C_OKUNAMAZ  — _OKUNAMAZ (yabanci/bozuk)_
   - kod: `scripts/credit_text_read.py:1750-1796 (nonlatin_source hesaplama, _nonlatin_ratio/_NONLATI`
   - ipucu: Kod bir bug degil, tasarim geregi calisiyor (yorum satiri credit_text_read.py:1750-1757'de 'NAMUS DUSMANI' notuyla acikca belgelenmis). Onceki incelemenin 'celiski' iddiasi field-semantiği karistirmas

## 1991-0356 — TOPLU GÖSTERİLER
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: OCR de bos donmus (_log.jsonl: yon-dogrulama=OKUNAMADI, VL-fallback yon=[]); guard 'OCR bos -> doldurma yok' demis. Yonetmen bilgisi hicbir karede/master'da yok.
- **KIMLIK** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Kimlik cast-ortusmesi=0, web capasi kilitlenemedi. Jenerik hicbir frame'de bulunamadigindan kimlik dogrulanamiyor.
- **CAST** → D_JENERIKTE_YOK / `cast_cap`  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: _log.jsonl: credit_qc1_red/credit_qc1_failed 'yon=BOS, cast=0' iki kez teyit edilmis (OCR ve VL-fallback ikisi de). Gercekten jenerikte oyuncu adi yok.
- **RENDER** → C_OKUNAMAZ / `garble_gate`  — _OKUNAMAZ (yabanci/bozuk)_
   - isim: **四影雪 (SI YING XUE)**
   - ipucu: kunye.txt (final) Latin harfli CANYON WATER AD/CABLE TV/SI YING XUE/VIDEO REPLAY birakmis; ham OCR'daki Kiril-Arap-CJK karisimi elenmis ama final metin de anlamli isim degil, Latin-disi/bozuk kaynak i

## 1991-0406 — YAPRAK BİTTİ
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: asr/asr-44aac29d/run/subtitle.json de 60 karede 0 hit/altyazili=false teyit ediyor; ASR tamamen basarisiz oldugu icin ozet adimi transkript olmadan calisamadi, .txt ve .md teslimlerinde de ayni placeh

## 1991-0415 — AYAK TAKIMI
- **CAST** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Ricky Tomlinson**
   - ipucu: _DURUM.json otorite_audit.ocr_dropped=['Ricky Tomlinson'] diyor; ancak isim hem frame'de hem ham OCR'da temiz okunuyordu, KB/otorite tarafindan yanlislikla dusurulmus, cap-asimi ile karistirilmamali.
- **CAST** → A_ELENDI / `identity_unlocked`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Jimmy Coleman / Jim R. Coleman**
   - ipucu: Isim frame'de/OCR'da dogru okunmus ama final'de KB-formu 'Jim R. Coleman' ile degistirilmis (form-overwrite); bilgi kaybi degil ama OCR-otoritesi ile KB-normu celisiyor, dogrulanmasi gerekir.
- **CAST** → D_JENERIKTE_YOK / `cast_cap`  — _YAPILAMAZ (jenerikte yok)_
   - isim: **Itions Criptions / Criptions Itions / Itions Cio**
   - ipucu: Bu parcali metin gercek bir oyuncu adi degil, harabe uzerindeki basilik/pankart kalintisi tekrar tekrar OCR'a takilmis; cast_cap dogru calismis, gercek isim kaybi yok.
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **vl_cast_aday (VLM adaylari)**
   - ipucu: _DURUM.json route.hafif='CAST_CAP_DUSEN' geregi 10 oyuncu cap-ustu sayildigi icin dustu; frame/OCR kaniti acik okunur oldugundan cap-parametresinin (10 sinirinin) gozden gecirilmesi onerilir.

## 1991-0441 — GÖLGELER PRENSİ
- **YONETMEN** → C_OKUNAMAZ / `garble_gate`  — _OKUNAMAZ (yabanci/bozuk)_
   - ipucu: Ham OCR alfabesi bozuk/anlamsiz (garble); jenerik havuzu (cikis_jenerik) 0 kare, detector 'No persistent credit text cluster found' diyor; yonetmen icin hicbir okunabilir kaynak yok.
- **KIMLIK** → E_VERI_YOK / `KB_veto`  — _VERI YOK_
   - ipucu: _DURUM.json 'kimlik celiskisi (KB cross-check)' + 'yanlis-film suphesi' bildiriyor (orijinal_ad='BELTENE BROS' vs TRT basligi 'GOLGELER PRENSI'); cast-ortusme 0, web capasi kilitlenemedi; kimlik dogru
- **CAST** → D_JENERIKTE_YOK / `cast_cap`  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: qwen_qc.oyuncu_sayisi=0; VL/GLM/master_png ucu de empty_pool/no_frames; gercek oyuncu adi hicbir kaynakta yok, cast gercekten mevcut degil.

## 1991-0442 — KIRIK KALPLER LOKANTASI
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: _DURUM.json: asr_status='failed', asr_segments=null, transcript_chars=null; qwen_qc.ozet_var=false, notlar='Özet bölümü placeholder metin içeriyor.'; route.agir=[['OZET','gerçek özet yok/placeholder, 

## 1991-0454 — JARRAPELLEJOSILAR
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **CARLOS LUCENA, JOSE VIVO, JOSE MARIA CAFARELL, GABRIEL LLOPA**
   - ipucu: _DURUM.json neden alanindaki '604 oyuncu dustu' uyarisi YANLIS/gurultu: raw_cap_dropped listesi aslinda tum jenerik metninin sliding-window trigram debug cikisi (Producciones Cinematograficas, Junta E
- **CAST** → E_VERI_YOK  — _VERI YOK_
   - isim: **ANTONIO FERRANDIS, JUAN DIEGO, LYDIA BOSCH, AMPARO LARRANAGA**
   - ipucu: Bu alan icin gercek bir HATA/dusme YOK: final cikti 10/10 doguruluyor, drop iddiasi asilsiz cikti; 'E_VERI_YOK' etiketi burada 'incelenecek somut bir hata/kayip veri yok, cikti dogru ve tam' anlaminda
- **KIMLIK** → A_ELENDI / `identity_unlocked`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Joaquin Rinojosa (OCR ham) -> Joaquín Hinojosa (final, KB/s5**
   - ipucu: OCR motoru gotik fontun H harfini R olarak yanlis okumus (karakter-seviyesi OCR hatasi); KB/s5 duzeltmesi gorsel kanitla DOGRULANDI, cast okunur ve dogruydu (D degil, gercek isim mevcuttu).

## 1991-0469 — ZERK'İN HİKAYESİ
- **HAFIF** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: _DURUM.json route.hafif=['AFIS'], qwen_qc.afis_var=false, qwen_uyari='afiş yok (deterministik poster_fetch garanti — uyarı)'; gorsel inceleme bu tespiti dogruluyor, jenerikte/master'da gercek afis yok

## 1991-0495 — ÖNEM DERECESİ
- **YONETMEN** → A_ELENDI / `lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **AMY SHAPIRO (yanlis aday) / W.T. Morgan (KB otoriter, jeneri**
   - ipucu: trace.jsonl (kb.external_lookup, ts 04:40:07): LLM 'AMY SHAPIRO'yu yonetmen sanmis (Film Komisyonu direktoru unvanindaki 'DIRECTOR' kelimesinden yanlis eslesme), KB otoriter yonetmen 'W.T. Morgan' ile
- **KIMLIK** → B_OCR_OKUYAMADI  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **ZA ZA DUPRE, ARYE GROSS, TOM SIZEMORE, WENDELL PIERCE, JUDIT**
   - ipucu: OCR/goruntude cast TAM ve dogru okunmus; nihai teslimde de 10/10 yazili (kunye_teslim.md). Ancak trace'e gore KB cross-check verdict='CELISKI' (yonetmen uyusmazligindan dogan genel celiski), cast_ortu

## 1991-0525 — OSCAR
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: 'garble (okunamadi)' etiketi aslinda yonetmen jenerigi degil, sahne-ici gazete mansetinin yanlis-okunmus metni; gercek yonetmen jenerik karesi hic yakalanmamis (D), garble bir yan-etkidir.
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: _DURUM.json qwen_qc.oyuncu_sayisi=0 ve otorite_audit.raw_cap_dropped listesi (Haby Face Barcimi zinciri) de ayni gazete-manseti OCR ciktisinin varyantlari; gercek bir cast/jenerik karesi pipeline'a hi
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: _DURUM.json: asr_status=failed, asr_segments=null, transcript_chars=null; qwen_qc.ozet_var=false, notlar='Ozet placeholder metin'. Gercek konusma transkripti hic uretilmemis.
- **RENDER** → A_ELENDI / `garble_gate`  — _FIXLENEBILIR (framede var, elendi)_
   - kod: `scripts/credit_text_read.py:1758-1768 (nonlatin_source hesaplama, detect_script+_nonlatin_`
   - ipucu: ocr_ham.txt/ocr_raw_all.txt icindeki cok-kisa (<=3 karakter) veya salt-sembol satirlarin (orn. 'Σ','ΚΟΣ','0','E','....','1:','வி','547','835 870' gibi metrik/damga/coordinate-benzeri gurultu) detect_s

## 1992-0223 — KONTES ALICE
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: _DURUM.json 'yonetmen garble (okunamadi)' diyor ve log'da yon=[] (guven=OKUNAMADI); ben butun giris(270)+cikis(720) frame setinde ayrica bir 'Directed by' karti bulamadim -> D_JENERIKTE_YOK'e daha yak
- **KIMLIK** → E_VERI_YOK / `KB_veto`  — _VERI YOK_
   - isim: **THE COUNTESS ALICE (BBC, giris) vs Robert Greenwald Producti**
   - ipucu: Otorite_audit.ocr_dropped bos ama kimlik-celiskisi gercek: giris jenerigi bir BBC dramasina, cikis jenerigi baska (Amerikan) bir yapima ait; karisik-kaynak/yanlis-esleme supheli, dogrulanmis tek kimli
- **CAST** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **WENDY HILLER, ZOE WANAMAKER, DUNCAN BELL**
   - ipucu: Ham OCR'da isimler dogru okunmus (kucuk harf hatalariyla), ama final kunye.txt/md'de 'Oyuncular: —' cikmis; _DURUM.json 'oyuncu yok' + 'cast-ortusme 0' diyor -> muhtemelen KB/web-capa dogrulamasi bu i
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: _DURUM.json: asr_status='failed', asr_segments=null, transcript_chars=null; klasorde asr/*/run/transcript*.txt hic yok, sadece _asr_16k.wav ve subtitle.json (altyazi-tespit) var. Ozet uretilecek gerce

## 1992-0299 — GLORIA KUŞATMASI
- **YONETMEN** → A_ELENDI / `lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **BRIAN TRENCHARD-SMITH**
   - ipucu: credit_text.candidate_read (LLM/ocr_ham.txt extraction) yönetmen alanına yanlışlıkla 'exploded throughout an unsuspecting' (Tet Offensive alt-yazı cümlesi) yazdı; KB lookup doğru ismi 'otoriter_yonetm
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: _DURUM.json: asr_status='failed', asr_segments=null, transcript_chars=null; pdf/kunye_teslim.md Özet bölümü '(ÖZET AYRI BİR ADIMDA ÜRETİLECEKTİR.)' placeholder metnini içeriyor; qwen_qc.ozet_var=false

## 1992-0308 — SON YARIŞ
- **KIMLIK** → B_OCR_OKUYAMADI  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **JOVAN RANCIC (Yönetmen) + 7 oyuncu (PAVLE VUJISIC, ALENKA RA**
   - ipucu: Final teslim (kunye.pdf, teknik.txt, master_manifest) DOGRU: Yonetmen=JOVAN RANCIC, 7 oyuncu tam eslesiyor. Kontrol tetikleyicisi, 'režija' basligindan hemen sonraki OCR akisinin (satir 238-287) bozuk
- **RENDER** → C_OKUNAMAZ  — _OKUNAMAZ (yabanci/bozuk)_
   - ipucu: qwen_qc.latin_disi_alfabe_var=true dogru tespit ama kaynagi kunye alanlari (yonetmen/oyuncu/yapimci - hepsi temiz Latin) degil, muhtemelen ara sahnedeki pist/yaris tabelasi metni; bu yuzden RENDER ala

## 1992-0324 — YARGIÇ VE POLİS
- **KIMLIK** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **ALAIN BONNOT (yönetmen); BRUNO MADINIER, CHARLOTTE VALANDREY**
   - ipucu: _DURUM.json route.agir='kimlik kurulamadı (cast-örtüşmesi 0)/yanlış-film şüphesi' ile KONTROL'e dusmus, ANCAK _log.jsonl credit_validate event'i yonetmen.status=DOGRULANDI (XML kaynakli, confidence=OR

## 1992-0332 — BUZ ÜSTÜNDE
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: asr/asr-35bd4c7d/run/subtitle.json icerigi {"altyazili": false, "oran": 0.0, "hits": 0, "total": 60} - gercek transcript*.txt dosyasi hic uretilmemis; asr klasorunde baska hicbir dosya yok.

## 1992-0454 — HAYATIMIN ERKEĞİ
- **YONETMEN** → A_ELENDI / `identity_unlocked`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Jean Charles Tacchella**
   - ipucu: Yonetmen adi hem framede hem ham OCR'da tam ve net okunur halde mevcut; ancak final kunye_teslim.md'de 'Yönetmen: —' ve _DURUM.json'da 'yönetmen yok ve KB/web ile doldurulamadı' deniyor. 'réalisation'
- **KIMLIK** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Maria de Medeiros, Anne Letourneau, Ginette Mathieu, Alain D**
   - ipucu: Cast final ciktida (kunye_teslim.md) mevcut ve dogru gorunuyor, ancak _DURUM.json 'kimlik kurulamadı (cast-örtüşmesi 0) / yanlış-film şüphesi' diyor -- bu KIMLIK sorunu cast'in okunamamasi degil, cast
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: _DURUM.json'da asr_status='failed', asr_segments=null, transcript_chars=null. chlang.json ve transcript*.txt dosyalari klasorde bulunamadi (find ile arandi, yok). kunye_teslim.md icinde '## Özet' basl

## 1992-0455 — MELEKLERİ GÖRMEK İSTEDİM
- **RENDER** → A_ELENDI / `deferans`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **СЕРГЕЙ БОДРОВ / АЛЕКСЕЙ БАРАНОВ / ЛИЯ АХЕДЖАКОВА (Kiril jene**
   - kod: `scripts/credit_text_read.py:1758-1796 (nonlatin_source hesaplama + _romanize_lines_llm cag`
   - ipucu: Fix gerekmiyor -- guard tasarlandigi gibi calisiyor (isim kaybi yok, romanizasyon dogru, insan-onayi bekliyor). Iyilestirme istenirse: nonlatin_source true oldugunda kunye_teslim.md'ye kaynak-Kiril fo

## 1992-0465 — İKİNCİ ŞANS
- **YONETMEN** → A_ELENDI / `deferans`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **REUBEN ROSE**
   - ipucu: Trace (debug_trace/trace.jsonl, stage=v4): credit_text OCR'dan 'REUBEN ROSE' dogru okumus (video_okuma.yon=['REUBEN ROSE'], guven='OKUNDU'), ama kb.external_lookup filmi yanlis eslestirmis ('The Miles
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: _DURUM.json: asr_status='failed', asr_segments=null, transcript_chars=null. asr/asr-f15d1521/run/ klasorunde transcript*.txt veya chlang.json YOK, sadece _asr_16k.wav ve bir dil-tespit subtitle.json v

## 1992-0468 — CENNETE GELDİK Mİ
- **YONETMEN** → A_ELENDI / `guard`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **CARL CALDANA**
   - ipucu: Ham OCR + master PNG + VL hepsi 'Carl Caldana'yi net yakalamis; _DURUM.json alanindaki vl_yon_dop_dropped:['Carl Caldana'] sistemin bu adayi DOP(Kevin Brown)/yonetmen karistirma guard'i ile elediginin

## 1992-0483 — JOE SHARP
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Judy Landers**
   - ipucu: Isim frame'de net okunur ve ham OCR/raw-cap penceresinde de yakalanmis (raw_cap_dropped listesinde defalarca gorunuyor), ancak final v4 cast_list'e (10 kisi: Reid Smith...Michael Macrae) alinmamis; _D
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Margaret Shendal**
   - ipucu: Frame'de okunan ve ham/raw-cap katmaninda tespit edilen isim, final cast_list'e (10 kisi limitli) girmemis; ayni CAST_CAP_DUSEN kusuru altinda A_ELENDI olarak degerlendirildi, final PDF/teslim metnind
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **final cast_list (10 kisi, kabul edilenler)**
   - ipucu: Belinda Beeman da frame'de 'and introducing' etiketiyle okunur durumda ama final cast_list'te yok ve _DURUM.json'da ayrica raporlanmamis; bu isim icin ayri drop kaydi (ocr_dropped) bulunmadigindan muh

## 1992-0484 — YALNIZ TOM
- **YONETMEN** → A_ELENDI / `lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **LST ASST (garble) / gercek: yok**
   - ipucu: Pipeline 'lst Asst. Director' OCR satirini 'LST ASST' olarak yanlis parcalayip yonetmen adayi sanmis; KB kontrolu 'ÇELİŞKİ' (Magic Hour: Tom Alone 1989 eslesmesi, otoriter_yonetmen=Randy Bradshaw guve
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: ASR calismasi basarisiz; asr/asr-54e8ffd4/run/ altinda yalniz altyazi-tespit ozeti subtitle.json var (altyazili=false, hits=1/60), gercek transcript*.txt veya chlang.json hic uretilmemis. Ozet uretile

## 1993-0277 — ZİRVEDEKİ YALNIZLAR
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Bu jenerik ZİRVEDEKİ YALNIZLAR'a ait degil (Ingilizce 'MAKE AND BREAK BY MICHAEL FRAYN' TV oyunu); yonetmen karti hicbir frame'de yok, sistem 'Michael Frayn'i (oyun yazari) yanlislikla cast'in ilk ele
- **KIMLIK** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - isim: **FRANK WINDSOR, STEFFANIE PITT, RONALD HINES, ANTHONY PEDLEY,**
   - ipucu: Kimlik kurulamama nedeni cast'in okunmamasi degil, klasordeki video/jenerigin baska bir yapima (Ingiliz TV oyunu, arka planda POLYMUR set tabelasi) ait olmasi; otorite_audit.raw_cap_dropped listesinde

## 1993-0312 — ÖLÜMSÜZ TUCK
- **OZET** → OZET_URETILEMEDI  — _ASR ARIZASI_
   - ipucu: ASR, ses dizisini bellege alirken MemoryError ile cokmus (0 segment/0 karakter); asr/asr-98a613de/run altinda transcript*.txt veya chlang.json hic olusmamis, sadece subtitle.json (altyazili:false, hit

## 1993-0401 — ARCEDIA
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: ASR basarisiz (status=failed, transcript_chars=null) oldugu icin ozet ASR'dan uretilemedi; OCR ham metni (ocr/ocr-7426bed5/ocr_ham.txt, 248 satir) da sadece diyalog+jenerik iceriyor, film konusunu anl

## 1993-0435 — SEN TOM SAWYER DEĞİLSİN
- **KIMLIK** → E_VERI_YOK  — _VERI YOK_
   - ipucu: _DURUM.json hic uretilmemis. debug_trace/trace.jsonl'de SADECE tek satir var: {"stage":"pipeline","event":"stage_started","ts":"2026-07-06T19:45:41"} - pipeline sadece baslamis, hicbir asama (OCR/VL/A

## 1993-0437 — LENI REIFENSTAHL'IN KORKUNÇ MUHTEŞEM YAŞAMI
- **KIMLIK** → A_ELENDI  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Ray Müller (Yönetmen); Walter A. Franke / Ulrich Jaenchen (y**
   - ipucu: Yönetmen doğru teslim edilmiş (final txt: 'Yönetmen: RAY MULLER'). Asıl hata: final Oyuncular alanına 'WALTER A. FRANKE' ve 'ULRICH JAENCHEN' yazılmış — bunlar framede 'Kamera' ve 'Kameraassistenz/Wer

## 1993-0439 — SON BOLŞEVİK
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: _DURUM.json vl_yon_aday=null, otorite_audit.ocr_dropped=[] -- hicbir aday tespit edilmemis, drop degil yoklukla acikliyor.
- **KIMLIK** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: KB cross-check celiskisi harici veritabani karsilastirmasindan kaynaklaniyor, frame/OCR kanitinda kimlik metni zaten hic yok.
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: qwen_qc.oyuncu_sayisi=0, vl_cast_aday=null; 720 cikis frame'den sadece ornekleme yapildi (tam 720 tek tek acilmadi), bu yuzden guven ORTA.
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: asr/asr-8823f30f/run/subtitle.json sadece altyazi-tespit sonucu icat: {altyazili:false, oran:0.017, hits:1, total:60}. Gercek transcript dosyasi yok. _DURUM.json asr_status='failed', transcript_chars=

## 1993-0467 — BİR KATİLLE EVLENDİM
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Hiçbir frame'de yönetmen adı/etiketi yok; _DURUM'daki 'garble' notuna rağmen gerçek görüntüde okunacak bir yönetmen metni dahi mevcut değil.
- **KIMLIK** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Cast-örtüşme 0, KB cross-check çelişkili; kaynak veri (ekranda isim) yok, okuma hatası değil.
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Final kunye Oyuncular alanı '—'; hem OCR hem VL-fallback (gemma4) boş döndü, kaynakta isim metni yok.
- **RENDER** → A_ELENDI / `garble_gate`  — _FIXLENEBILIR (framede var, elendi)_
   - ipucu: route.agir 'Latin-dışı alfabe sızdı' diyor ve ham OCR'da kanıtı var; final alanlar boş olduğu için drop somut bir isim üzerinden izlenemedi, garble_gate/OCR aşamasında elenmiş kabul edildi.

## 1994-0316 — VAHŞİ ORMAN
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: vl_yon_aday=null, otorite_audit.ocr_dropped=[] (yonetmen hic drop edilmemis, zaten hic bulunamamis); trace: credit_validate.external_lookup (IMDb/Wikidata/XML) sonucu da value=[], status=OKUNAMADI, no

## 1994-0338 — KİNG'İN SERVETİ
- **OZET** → OZET_URETILEMEDI  — _ASR ARIZASI_
   - ipucu: ASR calisti (asr suresi 38.67 sn kaydedilmis) ama klasorde transcript*.txt/chlang.json yok; sadece altyazi-tespit ozeti (hits=0) var; _DURUM.json asr_status=failed, transcript_chars=null, qwen_qc.ozet

## 1994-0345 — KOMİSER
- **YONETMEN** → A_ELENDI / `lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **ALEKSANDRA ASKOLDOVA (Александр Аскольдов)**
   - ipucu: Isim hem framede hem final OCR kunye.txt'de mevcut (satir 28-29) ama kunye_teslim.md/pdf'te Yonetmen alani '—' birakilmis; 'Сценария и постановка' (senaryo+mizansen) kalibi yonetmen-anchor lexicon'und
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: transcript.txt ve transcript_plain.txt tamamen bos (sadece bos satir); final kunye_teslim.md OZET alaninda placeholder: '(ÖZET AYRI BİR ADIMDA ÜRETİLECEKTİR.)' — gercek ozet hic uretilmemis, kaynak tr
- **RENDER** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Route.agir uyarisi uretim sirasinda (kaynak jenerik tamamen Kiril oldugu icin) tetiklenmis bir kontrol/insan-teyidi nedeni; nihai render dosyalarinda (pdf/md/onizleme) aranan Latin-disi sizinti fiilen

## 1994-0383 — NANCY'Yİ SEVMEK
- **YONETMEN** → B_OCR_OKUYAMADI  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **PAUL SCHNEIDER**
   - ipucu: Orijinal pipeline ham-OCR'i (ocr/ocr-0029d142/ocr_raw_reads.jsonl, 1888 satir) ve ocr_ham.txt/kunye.txt icinde 'Schneider'/'Directed' hic gecmiyor; _log.jsonl'da 'OCR boş → doldurma yok', 'yön:OKUNAMA

## 1995-0280 — SINIR ÇİZGİSİ
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: _DURUM.json 'yonetmen garble (okunamadi)' diyor ama vl_yon_aday=None; gercekte jenerikte yonetmen bilgisi hic yok (giris bos, cikis dogrudan cast ile basliyor) - sistem tanisi yanlis, veri esasen mevc
- **KIMLIK** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **CHARLES BRONSON, BRUNO KIRBY, BERT REMSEN, MICHAEL LERNER, K**
   - ipucu: Final .txt/pdf 'Oyuncular' listesi yanlislikla karakter adlarini (JEB MAYNARD, JIMMY FANTE...) iceriyor; gercek oyuncu adlari (Charles Bronson, Bruno Kirby, Bert Remsen vb.) iki-sutun OCR karismasi so

## 1995-0289 — ÜÇ KURUŞLUK OPERA
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: _DURUM.json: asr_status=failed, asr_segments=null, transcript_chars=null. asr/asr-b88260a6/run altinda sadece subtitle.json var (altyazili:false, hits:0); transcript*.txt veya chlang.json hic yok. ASR

## 1995-0326 — DELİLİĞİN SINIRINDA
- **YONETMEN** → A_ELENDI / `identity_unlocked/lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **DANNY HUSTON**
   - ipucu: Yonetmen adi hem frame'de hem ham OCR'da doğru okunmus ama final kunyede 'Yonetmen: —' bos birakilmis; ayni isim yanlislikla OYUNCULAR listesinin basina yazilmis (kunye_onizleme.png, kunye_teslim.md, 
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: _DURUM.json asr_status='failed'; ASR sesten anlamli transkript uretememis (60 segmentin sadece 1'i eslesmis, ornegi anlamsiz/bozuk 'Q LuNuID CTun'); gercek ozet hic uretilmemis, placeholder kalmis.

## 1995-0363 — KÜÇÜK SİMBA DÜNYA KUPASINDA
- **YONETMEN** → A_ELENDI / `identity_unlocked`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Kim Jun Ok**
   - ipucu: debug_trace/trace.jsonl: vl_fallback asamasinda 'candidate_dropped', before:['Kim Jun Ok'] after:[], reason='VL director not found in raw OCR corpus', ayrica 'vl_yon_hallucinated' etiketlendi -- ANCAK
- **KIMLIK** → E_VERI_YOK  — _VERI YOK_
   - ipucu: KB cross-check 'KAYNAK_YOK' donmus (film bilinen veritabanlarinda yok/eslesmiyor); bu celiski degil veri yoklugu -- film adi ve orijinal ad gorsel olarak tutarli, sadece harici referans eksik.
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Bu bir Italyan-Kore ortak yapimi (Mondo TV/Studio Sek) cocuk animasyonu; jenerikte seslendirme kadrosu credit'i bastan itibaren mevcut degil, OCR/pipeline hatasi degil gercek eksiklik.

## 1995-0404 — BÜYÜK SAVAŞTA KÜÇÜK ADAM
- **YONETMEN** → A_ELENDI / `vl_fallback_hata/guard`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Valentin Yakovlev / Valentina Zhirnova (REJİSSERİ: Валентин **
   - ipucu: _DURUM.json: qwen_qc.yonetmen_var=false, neden='qwen: yon+yapimci yok', jenerik_debug/analysis_report.md VL durum=error (gemma_kunye.json hata) -> yonetmen adaylari OCR'da mevcutken VL fallback hatasi
- **RENDER** → A_ELENDI / `dublaj_filtresi/lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - ipucu: _DURUM.json otorite_audit.raw_cap_dropped listesi bu ayni garip dizileri (Cbemo Wass, Wass Shatobapnt, Nas Tpy, Itamraha Wyp) icerir -> guard/cap katmani bunlari gecerli isim/kurum sanip filtrelemis; 

## 1995-0444 — KORKUNÇ GECE
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: OCR'daki 'SUPER' tam olarak g_0014-g_0017 karelerindeki market tabelasindan geliyor (oneocr raw_reads.jsonl ile frame-eslesme dogrulandi); yonetmen bilgisi filmde/jenerikte hic yok.
- **KIMLIK** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: _DURUM.json: qwen_qc.yonetmen_var=false, oyuncu_sayisi=0; kunye_teslim.md Yonetmen/Oyuncular alani bos (—); route.agir 'kimlik kurulamadı (cast-örtüşmesi 0)/yanlış-film şüphesi' diyor; jenerik havuzu 
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: otorite_audit.raw_cap_dropped listesi (Super Super/Sorte Sohte/Billeto Ellets/Ellets Ftets) tamami metro-tabelasi OCR-gurultusu; gercek oyuncu ismi hicbir karede yok; qwen: 'Oyuncular ve yönetmen kısı

## 1995-0448 — KATİLLER HER ZAMAN SARI PABUÇ GİYER
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: OCR+VL fallback ikisi de bos donduu (guven=OKUNAMADI); gorsel taramada da matbu kredi blogu fiziken yok - jenerikte yonetmen bilgisi mevcut degil, drop degil yokluk.
- **KIMLIK** → E_VERI_YOK  — _VERI YOK_
   - ipucu: Kimlik celiskisi degil, kimlik kurmak icin gereken cast/yonetmen veri tabanda hic yok; KB de bagimsiz olarak baglanti kuramadi -> gercek veri eksikligi.
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Hem OCR hem VL hem qwen_qc oyuncu bulamadi; jenerikte fiziksel olarak oyuncu-kredi metni yok (yalnizca ham/bozuk dokuma-tas OCR satirlari var, isim degil).

## 1995-0475 — SON OYUN
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: _DURUM.json route.agir 'yönetmen garble (okunamadı)' diyor ama gercekte garble degil: jenerikte yonetmen unvani hic yer almiyor (yalnizca Yazar/Yapimci/DoP var); D_JENERIKTE_YOK daha dogru tani, garbl

## 1996-0031 — SOĞUK SUYA VURAN GÜNEŞ
- **KIMLIK** → A_ELENDI / `otorite_audit`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Bernard Fresson**
   - ipucu: _DURUM.json otorite_audit.ocr_dropped=['Bernard Fresson']; ham OCR ve frame'de net okunan isim final kunye_teslim.md Oyuncular listesine (10 isim: Claudine Auger, Marc Porel, Judith Magre, Barbara Bac
- **KIMLIK** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: YONETMEN ve final 10 oyuncunun tamami dogru/tutarli okunmus (sorunsuz); bu finding sadece Bernard Fresson disindaki KIMLIK alaninin genel dogrulugunu kayit altina alir, ayri bir hata degildir.

## 1996-0310 — İŞARET DİREĞİ
- **YONETMEN** → D_JENERIKTE_YOK / `garble_gate`  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Jenerikte (giris+cikis, 45+720 kare tarandi) hicbir alfabede yonetmen adi yok; route.agir 'garble' diyor ama gercekte CJK metin okunakli-JAPONCA, yonetmen bilgisi hic mevcut degil -> D_JENERIKTE_YOK i
- **KIMLIK** → D_JENERIKTE_YOK / `KB_veto`  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: KB cross-check 'kimlik celiskisi' bulmus olabilir cunku OCR motoru CJK metni yanlis pinyin/latin harflere donusturmus (garble); ancak gorsel dogrulamada baslik-ceviri tutarli, film kimligi doğru gorun
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: qwen_qc.oyuncu_sayisi=0 ve otorite_audit.ocr_dropped=[] (hicbir isim drop edilmemis çünkü hic tespit edilmemis) ile tutarli; gercekten oyuncu-kredisi jenerik parcasinda yok -> D_JENERIKTE_YOK.
- **RENDER** → C_OKUNAMAZ  — _OKUNAMAZ (yabanci/bozuk)_
   - ipucu: route.agir 'Latin-disi alfabe (Kiril/Yunan/Arap/CJK) sizdi' hukmu dogrulandi; kaynak gercekten Japonca ve OCR/romanizasyon motoru bunu guvenilir okuyamiyor -> insan/uzman CJK okumasi gerekli, C_OKUNAM

## 1996-0316 — TANGO ARGENTINO
- **YONETMEN** → D_JENERIKTE_YOK / `garble_gate`  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Jenerik-detektoru 720 cikis karesinde 'No persistent credit text cluster found' demis (detector/result.json); YONETMEN hicbir karede gorsel olarak mevcut degil, OCR'daki 'garble' harfler sahne dokusun
- **KIMLIK** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Kimlik kurulamamasinin nedeni cast/yonetmen bilgisinin hem OCR'da hem gorselde gercekten yok olmasi (D), OCR-okuyamama (B) degil; web-capa kilitlenememesi bagimsiz bir KB sorunu.
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Final kunye_teslim.md 'Oyuncular' alani bos cikti; bu D_JENERIKTE_YOK hukmunu dogruluyor (cast karti hic yok, OCR-okuma hatasi degil).
- **RENDER** → A_ELENDI / `garble_gate`  — _FIXLENEBILIR (framede var, elendi)_
   - ipucu: normalization_log.jsonl: tum 18 raw satir action=deleted_by_clean_dedup_or_filter, best_final_text="" — final kunye_teslim.md'de hicbir Latin-disi karakter yok; garble_gate/lexicon filtreleri sizintiy

## 1996-0325 — KIZIL HAYAT
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: route.agir 'yönetmen garble (okunamadı)' diyor ama gercekte garble degil, yonetmen bilgisi jenerikte fiilen hic yok; drop_stage etiketi yanlis (garble yerine D_JENERIKTE_YOK olmali).
- **KIMLIK** → A_ELENDI / `identity_unlocked`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Vadim Alexander Balouev, Serguei Stepantchenko, Dimitri Pevt**
   - ipucu: Cast frame+OCR'da net okunuyor ve final PDF'e de (8 oyuncu, dusurulmeden) gecmis; sorun OCR degil, KB/web-capa cross-check katmani ('kimlik çelişkisi', 'XML-PDF cast kesişimi 0', 'cast-örtüşme<2 web ç

## 1996-0330 — İKİ SEVGİLİM VAR
- **HAFIF** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: AFIS/poster OCR veya frame'den degil harici deterministik poster_fetch adimindan gelir; bu adim afis bulamamis (afis_var:false). Klasorde *afis*/*poster*/*.jpg/*.jpeg aramasi da sifir sonuc verdi, mas

## 1996-0350 — IRIS'IN SIRRI
- **CAST** → A_ELENDI  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **VIKTOR LAZLO**
   - ipucu: VIKTOR LAZLO ham OCR'da (ocr_ham.txt) net ve dogru sirada mevcut; final kunye.txt Oyuncular listesine dogru sekilde gecmis; sadece incelenen 2 master-dilim sayfasinda kendine ait ayri kart gorulmedi, 
- **CAST** → D_JENERIKTE_YOK / `lexicon_anchor_misparse`  — _YAPILAMAZ (jenerikte yok)_
   - isim: **Trintignant Marie / Trintignant Lambert / Wilson Lambert**
   - ipucu: qwen_uyari CAST_CAP_DUSEN uyarisi yanlis-pozitif: bu 3 isim gercek oyuncu degil, bigram/dedup artefakti; uyarida 'gorunurluk-karar-etkisiz' notu dogru
- **CAST** → E_VERI_YOK  — _VERI YOK_
   - isim: **MARIE TRINTIGNANT; LAMBERT WILSON; ANTOINE DULERY; ANNE JACQ**
   - ipucu: CAST alani genel hukmu: qwen_qc.oyuncu_sayisi=10 dogrulandi, gercek eleme yok, tum veri mevcut ve dogru -- protokol geregi alan basina hukum zorunlu oldugundan buraya not dusuldu, ancak fiilen kayip v

## 1996-0353 — AŞK EVLİLİĞİ
- **HAFIF** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: route.hafif=["AFIS"] dogru tespit: afis harici deterministik poster_fetch adiminin sorumlulugunda, bu klasorde (frames/, master_dilim/, pdf/, kok dizin) afis/poster adinda veya icerigin de hicbir dosy

## 1996-0356 — SİNDİRELLA'NIN KIZININ MACERALARI
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Jenerik boyunca (giris+cikis, tum crawl) ayri bir yonetmen karti hic gecmiyor; DOP ile karistirilmamali; gercekten jenerikte yok gibi gorunuyor
- **KIMLIK** → A_ELENDI / `guard`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Laurie Plaksin, Jim Wise, Liz Lavoie, Joe Lando, Shirley Jon**
   - ipucu: Asil OCR modeli (model=None) hic calismamis, QC1 RED ile cast=0/yon=BOS kabul edilmis; oysa alternatif oneocr katmani (dilim_oneocr.txt) ve gorsel master'da kimlik tam ve net okunur durumda; final kun
- **CAST** → A_ELENDI / `guard`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Laurie Plaksin (Cindy), Jim Wise (Fred the Fairy Godbrother)**
   - ipucu: _log.jsonl 'credit_qc1_red: yon=BOS, cast=0' ve pdf_completed 'cast=0' kayitlariyla teyitli; asil OCR sureci calismadigindan (model=None) tespit edilen cast final'e hic yansitilmamis; teknik.txt/kunye
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: ASR tamamen basarisiz olmus (asr-92b68ec1 klasorunde sadece ham wav ve bos subtitle.json var), gercek transkript hic uretilmemis; kunye.txt'de 'OZET AYRI BIR ADIMDA URETILECEKTIR' notu ile ozet zaten 

## 1996-0368 — SAVAŞTAN DÖNÜŞ
- **YONETMEN** → A_ELENDI / `lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **BUS DEPOT (yerine EMILIO ESTEVEZ olmaliydi)**
   - ipucu: credit_text.candidate_read (LLM/OCR-satir cikarimi) 'DIRECTED BY' anchor'ini dogru buldu ama hemen ardindan/civarinda tekrarlayan 'BUS DEPOT' otobus-istasyonu tabela metnini yonetmen adayi olarak aldi

## 1997-0217 — ÖRGÜT
- **YONETMEN** → C_OKUNAMAZ / `identity_unlocked`  — _OKUNAMAZ (yabanci/bozuk)_
   - isim: **UGO FABRIZIO GIORDANI (yanlis-film adayi, ÖRGÜT'e ait degil)**
   - ipucu: Kaynak video dosyasi (evoArcadmin_ÇÖZÜMLEMEV2S9_...ÖRGÜT.mp4) yanlis-film icerigi tasiyor gorunuyor; gercek OCR motoru da crash (engine=yok, access violation) oldugu icin ÖRGÜT'e ait yönetmen hicbir k
- **KIMLIK** → D_JENERIKTE_YOK / `KB_veto`  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: _DURUM.json 'kimlik çelişkisi (KB cross-check)' ve 'cast-örtüşme 0 / yanlış-film şüphesi' diyor — gorsel inceleme bu supheyi DOGRULUYOR: kaynak muhtemelen yanlis video/karisik footage.
- **CAST** → D_JENERIKTE_YOK / `cast_cap`  — _YAPILAMAZ (jenerikte yok)_
   - isim: **Anthony Quinn, Anna Bonaiuto, Maria Grazia Cucinotta, Raoul **
   - ipucu: PDF/manifest cast alanini bos birakmis; bu dogru davranis olabilir cunku okunan isimler ÖRGÜT'e degil baska bir filme ait (yanlis-footage supheli), sistem muhtemelen bu isimleri gecerli KB eslesmesi b
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: _DURUM.json: asr_status='failed', asr_segments=null, transcript_chars=null. asr/asr-1bd72f0f/run/ klasorunde sadece subtitle.json (altyazi-tespit, transkript degil) ve ham wav var; gercek transkript u

## 1997-0241 — PRENSES WONONOKE
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Kapanis jenerigi (cikis_jenerik) hic render edilmemis; yonetmen bilgisi muhtemelen staff-roll'da ama frame havuzu bos oldugundan hic denenmemis.
- **KIMLIK** → E_VERI_YOK  — _VERI YOK_
   - ipucu: Icerik dogru filme isaret ediyor ama yonetmen/cast eksikligi yuzunden KB cross-check kimlik kurulamadi diyor; veri eksikligi asil neden.
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Final PDF/MD 'Oyuncular: —' dogru sekilde bos birakilmis, halusinasyon yok; veri gercekten yok/yakalanamadi.
- **RENDER** → C_OKUNAMAZ  — _OKUNAMAZ (yabanci/bozuk)_
   - ipucu: Latin-disi alfabe (Japonca+bozuk Arapca) gercekten kaynak goruntude var; romanizasyon/insan teyidi gerekiyor, OCR hatasi degil.

## 1997-0353 — KÜÇÜK AYICIK
- **YONETMEN** → A_ELENDI / `garble_gate`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Paul Ziller**
   - ipucu: _DURUM.json + _log.jsonl kaniti: canli OCR motoru 0 satir/bucket=HATA/motor=None dondu, LLM preflight FAILED (ollama modeli yok), VL-fallback 'kostu' (crash); yonetmen='OKUNAMADI' kaydedilip final kun
- **KIMLIK** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Mark of the Bear (calisma adi: Ms. Bear) - Le Monde Entertai**
   - ipucu: _DURUM.json 'neden': 'kimlik celiskisi (KB cross-check)' ve 'qc_block: kimlik kurulamadi (cast-ortusme<2, web capasi kilitlenemedi)'; canli OCR/LLM crash oldugu icin hicbir isim KB'ye ulasmadi, cast-o
- **CAST** → A_ELENDI / `garble_gate`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Ed Begley Jr., Shaun Johnston, Kaitlyn Burke, Natja Jamaan, **
   - ipucu: _log.jsonl: 'credit_qc1_red ... yon=BOS, cast=0' ve 'credit_qc1_failed ... cast=0' — canli OCR/LLM hic calismadigi icin cast listesi hic uretilmedi (cast_cap devreye bile girmedi), final PDF 'oyuncu y
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: ASR adimi bellek hatasiyla (MemoryError) tamamen crash oldu; transcript hic uretilmedi, bu yuzden ozet de hic uretilmedi (placeholder: '(OZET AYRI BIR ADIMDA URETILECEKTIR.)').

## 1997-0411 — OMAGGIO A CARUSO
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: ASR transcript.txt tamamen bos (1 satir bos); chlang.json confidence 0.528 dil=nn (belirsiz/net konusma yok); asr_status=partial, transcript_chars=0. Kunye teslim.md'de ozet alani placeholder: '(OZET 
- **RENDER** → C_OKUNAMAZ  — _OKUNAMAZ (yabanci/bozuk)_
   - isim: **UGETSU MONOGATARI / KENJI MIZOGUCHI**
   - ipucu: Master PNG (297 frame'den derlenen 22 kart) fiilen acildi: ust kartlarda net Latin alfabesiyle 'UGETSU MONOGATARI / Directed by KENJI MIZOGUCHI' okunuyor, alt taraftaki genis blok dusuk-cozunurluklu/b
- **KIMLIK** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - isim: **Machiko Kyo, Masayuki Mori, Kinuyo Tanaka, Sakas Ozawa, Mits**
   - ipucu: KIMLIK bu talepte incelenecek alan olarak belirtilmedi ama _DURUM.json'da 'CAST_CAP_DUSEN' hafif uyarisi var; final PDF'teki kadro (Machiko Kyo, Masayuki Mori, Kinuyo Tanaka vb.) OMAGGIO A CARUSO film

## 1997-0421 — HAYAT BİR ŞARKIDIR
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **AGNES JAOUI, JEAN-PIERRE BACRI**
   - ipucu: otorite_audit.ocr_dropped=['Jean-Pierre Bacri','Agnès Jaoui'] ve route.neden='qc_block: CAST_CAP_DUSEN: cap-ustu okunan 3041 oyuncu dustu'; final pdf/kunye_teslim.md Oyuncular listesinde bu iki isim Y

## 1998-0312 — KARA GÜNLER
- **YONETMEN** → A_ELENDI / `lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **NIKOLAUS LEYTNER**
   - ipucu: credit_text.candidate_read OCR'dan 'DOMINIQUE ROULET'i (aslinda senaryo yazari) yonetmen sanmis; KB dogru yonetmeni 'Nikolaus Leytner' olarak bulmus ama fuzzy.candidate_dropped asamasinda 'OCR yönetme
- **YONETMEN** → A_ELENDI / `deferans`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **NIKOLAUS LEYTNER**
   - ipucu: [Ikinci drop_stage etiketi ayni bulgunun deferans bileseni] kb.external_lookup: otoriter_yonetmen=['Nikolaus Leytner'] dogru tespit edilmis (verdict=ÇELİŞKİ), ama credit_validate.qc_decision OCR-okuna
- **KIMLIK** → B_OCR_OKUYAMADI  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **STEPHANE BONNET, BERNHARD SCHIR, MICHAELA MAZAC, MICHAELA RO**
   - ipucu: Asil KIMLIK celiskisi cast eksikliginden degil, YONETMEN eksikliginden kaynaklaniyor: trace'te kimlik_dogru=true, cast_ortusme=6-7 iken route.agir metni 'cast-örtüşmesi 0' diyor (rapor metni ile trace

## 1998-0401 — BLACKJACK
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: asr klasöründe transcript*.txt veya chlang.json hiç yok, sadece subtitle.json (altyazı-var-mı tespiti) mevcut; _DURUM.json'da asr_status='failed', asr_segments=null, transcript_chars=null. Özet üretim

## 1998-0464 — ELMA
- **YONETMEN** → A_ELENDI / `garble_gate`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Samira Makhmalbaf (سمیرا مخملباف)**
   - ipucu: Birincil OCR motoru (ocr-02c78187) Farsça/Arap alfabesini okuyamayıp bucket=HATA/ocr_metni_yok döndürdü; credit_text/QC1/VL zinciri hep boş kaldı. KB cross-check (trace_summary.md) harici olarak doğru
- **KIMLIK** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Film: The Apple / Sib (1998, İran, yön. Samira Makhmalbaf)**
   - ipucu: Sistem doğru filmi (The Apple/ELMA, Samira Makhmalbaf) harici KB ile bulmuş ama OCR cast listesi boş olduğu için 'cast_ortusme<2' hesaplanmış, qc2_web 'çapa bulunamadı' deyip kimlik kilidini reddetmiş
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Massoumeh Naderi, Zahra Naderi, Ghorbanali Naderi, Azizeh Mo**
   - ipucu: Birincil OCR bucket=HATA olduğu için credit_text 'cast: []' ile başladı, VL fallback da 'kostu' (boş) döndü; final pipeline cast=0 kabul etti. Görsel ve master_dilim ikinci-geçiş OCR'da liste tam mevc
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: ASR başarısız (Farsça konuşma + düşük çözünürlük/gürültü nedeniyle dil tespiti bile 60 denemeden sadece 1'inde anlamlı sonuç verdi, örnek çıktı anlamsız harf dizisi). Gerçek transkript hiç üretilmemiş

## 1998-0519 — SON CÜCE
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: OCR ham cikti sadece marka/ekipman logolarini (SUGAR, CAT) yakalamis; yonetmen karti hicbir framede yok -> okunacak jenerik metni mevcut degil (VL de bos donmus, credit_text.candidate_read: yonetmen=[
- **KIMLIK** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Kimlik/cast okunabilir degil cunku gercekten hicbir karede metin yok (D), ayrica KB/web capasi da kilitlenemedigi icin kimlik celiskisi (yanlis-film supheli) olarak KONTROL'e dusmus; bu OCR-okuyamama 
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - isim: **Pierce Brosnan**
   - ipucu: A_ELENDI degil: 'Pierce Brosnan' hicbir framede/ham OCR'da hic gorulmedi (VL halusinasyonu), bu yuzden guard/drop asamasindan degil dogrudan D_JENERIKTE_YOK/uydurma-red olarak degerlendirildi.
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: _DURUM.json asr_status=failed, asr_segments=null, transcript_chars=null; asr klasorunde transcript*.txt veya chlang.json yok, sadece altyazi-varlik testi (subtitle.json) var -> gercek konusma transkri

## 1998-0970 — BAŞKAN VE MARI
- **YONETMEN** → E_VERI_YOK  — _VERI YOK_
   - ipucu: Pipeline sadece import+trace_init asamasinda kalmis; frame cikarma/OCR/ASR hic calismamis, YONETMEN icin degerlendirilecek hicbir gorsel/metin kanit yok.

## 1998-1000 — DÜŞLER ÜLKESİ
- **HAFIF** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Afis deterministik poster_fetch (harici web kaynagi) ile getirilemedi; kunye_onizleme.png final belgede afis gorseli hic yok. Bu OCR okuma hatasi degil, dis-kaynak/poster_fetch basarisizligi + yanlis 

## 1999-0321 — FISILTILAR
- **YONETMEN** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **David Koepp**
   - ipucu: OCR+ilk KB katmani TEYIT/kimlik_dogru=True verdi (otoriter_yonetmen=['David Koepp'], verdict=TEYIT); v4 render'daki ikinci 'KISI-TEYIT' katmani ayni ismi 'KB'de dogrulanamayan' sayip dusurdu (teyitsiz

## 1999-0361 — RÜZGAR BİZİ SÜRÜKLEYECEK
- **RENDER** → C_OKUNAMAZ  — _OKUNAMAZ (yabanci/bozuk)_
   - isim: **YOK (Latin transliterasyon yok, sadece Arap alfabesi)**
   - ipucu: route.agir='RENDER: Latin-disi alfabe (Kiril/Yunan/Arap/CJK) sizdi' dogru tespit; VL/gemma romanizasyon adimi jenerik_debug/vl/summary.json'da 180sn TIMEOUT ile basarisiz (master_lines_count=0), bu yu

## 1999-0383 — PUNKTCHEN VE ANTON
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: _DURUM.json: asr_status=failed, asr_segments=null, transcript_chars=null; asr/ klasorunde transcript*.txt veya chlang.json hic yok, sadece subtitle.json (altyazi-tespit) var, hits=0. Teslim ciktisi (p

## 1999-0394 — 13. SAVAŞÇI
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: _DURUM.json: asr_status=failed, asr_segments=null, transcript_chars=null; asr/asr-ff08766a/run/ klasorunde transcript*.txt veya chlang.json YOK, sadece subtitle.json (bir ASR transkripti degil, altyaz

## 1999-0403 — PRENSESİN AŞKI
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: qwen_qc.yonetmen_var=false ve route.agir='yönetmen garble (okunamadı)' notuyla uyumlu; giris jenerigi cok kisa olup sadece yapimci sirket logosunu iceriyor, yonetmen karti hicbir frame'de yakalanmamis
- **KIMLIK** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Tamzin Outhwaite, Nicola Maddox, Alan Hogg, Amanda Drewery, **
   - ipucu: Final teslim (kunye_teslim.md) sadece ilk 8 oyuncuyu aliyor; geri kalan ~25+ okunur isim (Tamzin Outhwaite, Nicola Maddox, Amanda Drewery, prens rolleri vb.) final listeye girmemis. route.agir='kimlik

## 1999-0407 — KÜÇÜK KAHRAMAN
- **OZET** → E_VERI_YOK  — _VERI YOK_
   - ipucu: OZET alani gorsel/frame konusu degil; ASR transkriptinden uretiliyor ve _DURUM.json'da neden=[], route.agir=[], asr_status=done, qwen_qc.ozet_var=true -- hicbir drop/uyari yok, dolayisiyla A/B/C/D huk

## 1999-0450 — SCHIMANSKI HASRET
- **KIMLIK** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Chiem van Houweninge**
   - ipucu: _DURUM.json otorite_audit.ocr_dropped=['Chiem van Houweninge'] ve qwen_uyari 'otorite: temiz-okunan isim dustu -> Chiem van Houweninge' diyor; final kunye_teslim.md Oyuncular listesinde bu isim yok (s

## 1999-0483 — SON TANIK
- **YONETMEN** → A_ELENDI / `lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **GRAEME CLIFFORD**
   - ipucu: Ham OCR/frame'de yonetmen adi (GRAEME CLIFFORD) acikca mevcut ve dogru okunmus; ancak pipeline credit_text extraction asamasinda yonetmen alanina yanlislikla 'DIRECTOR OF PHOTOGRAPHY' satirinin bozuk 
- **KIMLIK** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **NATASHA HENSTRIDGE, JOHNATHON SCHAECH, MICHAEL FILIPOWICH, D**
   - ipucu: Cast 9/10 oraninda KB'nin otoriter listesiyle (The Last Witness, 1999) tam ortustugu halde, sistem KB sonucunu 'ÇELİŞKİ'/yanlış-film şüphesi olarak flaglemis (asiri temkinli esik: 9/10 ortusme celiski

## 1999-0508 — PAMUK MARY
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: _DURUM.json: asr_status="failed", asr_segments=null, transcript_chars=null. kunye_teslim.md ve final .txt'de Ozet alani placeholder: "(OZET AYRI BIR ADIMDA URETILECEKTIR.)". Kok neden: ASR adimi basar

## 2000-0274 — AHTAPOT (DEAD EYE SIX)
- **KIMLIK** → B_OCR_OKUYAMADI  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **JAY HARRINGTON; RAVIL ISYANOV; DAVID BEECROFT; CAROLYN LOWER**
   - ipucu: DUZELTME: gercekte drop yok - cast hamOCR+gercek karede(c_0395-399) net okunmus VE final txt 'Oyuncular' bolumune 10 isim birebir girmis; otorite_audit.ocr_dropped=[]. raw_cap_dropped'daki 'Age Rge/Mh

## 2000-0282 — SEVİMLİ KÖPEK-YEDİNCİ OYUNDAKİ MUCİZE
- **CAST** → D_JENERIKTE_YOK / `lexicon_anchor_misparse`  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Teslim edilen CAST alani (10 isim, JEFFREY BALLARD...JIM HUGHSON) frame c_0634.png ile birebir eslesiyor; _DURUM.json qwen_qc.oyuncu_sayisi=10 dogrulaniyor. route.hafif=CAST_CAP_DUSEN sadece bilgilend

## 2000-0303 — MOTORSİKLETLİ POLİSLER
- **YONETMEN** → A_ELENDI / `identity_unlocked`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **THOMAS KIRCHNER (fikir sahibi) / DRAGAN ROGULJ (kamera) — yo**
   - ipucu: Bu jenerik MOTORSİKLETLİ POLİSLER'e (2000, TR) degil Alman 'Y - Wie alles begann' filmine ait; yonetmen adi bulunsa bile bu filme atfedilemez, final dogru sekilde bos birakilmis (route.agir: yonetmen 
- **KIMLIK** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: otorite_audit.ocr_dropped=[] ve vl_cast_aday=null: sistem yanlis-film icerigini dogru sekilde reddetmis (kimlik kurulamadi), guard/KB_veto calismis; kok neden video-kaynagin/footage'in yanlis film old
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Giris jenerigindeki tek oyuncu-benzeri metin de (varsa) yanlis filme ait oldugu icin gecerli sayilmadi; cast gercekten hem cikista hem giriste okunabilir sekilde yok.
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: asr/asr-28458b1e/run altinda transcript*.txt dosyasi mevcut degil; sadece subtitle.json var ve icerigi {altyazili:false, hits:0, total:60, guven:yuksek} — yani altyazi/transkript hic uretilememis. _DU

## 2000-0395 — SANTRAL
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Sistem _DURUM.json'da route.agir='yonetmen garble (okunamadi)' diyor ama gercekte OCR'in okuyamadigi bir YONETMEN satiri yok -- byle bir kart/satir hicbir acilan karede (giris master + cikis p01-p03 +

## 2000-0430 — SEVİMLİ KÖPEK 3
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Cikis jenerik (194 kare, c_0527-c_0720) de kontrol edildi: CAST listesi + tam crew/post-production listesi (Sound, Music, VFX, Titles) ile bitiyor, sonra ekran tamamen karariyor (c_0719/c_0720 siyah);

## 2000-0454 — BUZDAN GELEN SESLER
- **KIMLIK** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Dale Johnson**
   - ipucu: Yonetmen adi OCR+frame+final txt'de dogru mevcut (final: 'Yonetmen: DALE JOHNSON'); route.agir KIMLIK dropu isim kaybi degil, KB/web-capasi kimlik dogrulama celismesi (cast-ortusme=0, 'Buzdan Gelen Se
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Film bir doga/buzul belgeseli (insan oyuncu yok, sadece anlatim/crew kredisi); qwen_qc.oyuncu_sayisi=0 ve final txt 'Oyuncular: —' dogru, veri gercekten yok, OCR/frame kaynakli kayip degil.

## 2000-0476 — TACİZ
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Jenerik segmenti hic tespit edilememis (result.json: reason=No persistent credit text cluster found); yonetmen adi hicbir katmanda uretilmemis, drop degil yoklukdur.
- **KIMLIK** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Kimlik kurulamadi cunku ne OCR ne VL gercek bir isim uretebildi; KB'nin onerdigi film adayi cast-orgusmesi sifir oldugundan reddedilmis, dogru davranis.
- **CAST** → D_JENERIKTE_YOK / `identity_unlocked`  — _YAPILAMAZ (jenerikte yok)_
   - isim: **Uma Thurman, Ethan Hawke (VL halisinasyonu, dogrulanamadi)**
   - ipucu: VL'nin onerdigi Hollywood oyuncu adlari filmin gorsel icerigiyle (dusuk cozunurluklu VHS-tarzi Avrupa filmi sahneleri) tutarsiz, dogru sekilde dusurulmus; gercek jenerikte cast metni hic yok.
- **RENDER** → C_OKUNAMAZ / `garble_gate`  — _OKUNAMAZ (yabanci/bozuk)_
   - ipucu: Latin-disi alfabe sizmasi gercek yazidan degil, dusuk cozunurluklu/gurultu kaynakli OCR yanlis-okumasindan geliyor; route bunu dogru sekilde KONTROL'e almis (romanizasyon/insan teyidi gerek notu dogru

## 2000-0477 — FUTBOLCU PRENSES
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: 1983 CBS TV-filmi formatinda ayri yonetmen karti yok; JOHN STOCKWELL cast/Starring blogunda gecen bir oyuncu adi, yonetmen degil - _DURUM.json/log da yonetmen adayini hic uretmemis (vl_yon_aday: null,
- **KIMLIK** → A_ELENDI / `lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **TIM ROBBINS / DAPHNE ZUNIGA / HELEN HUNT / KATHLEEN WILHOITE**
   - ipucu: trace_summary.md + _log.jsonl acikca gosteriyor: credit_text extraction cast alanina Co-Starring blogunu degil, sahne-ici tabela/banner metinlerini ('Yeuns Wortd','Grizzly Country','Clinton Real','For

## 2000-0479 — HİTLER'İN HAZİNESİ
- **YONETMEN** → A_ELENDI / `garble_gate`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **HARDY MARTINS**
   - ipucu: Delivered 'giris.png' (giris_cropstack, 780x2852) master farkli/ayri bir stack build'i ve 'REGIE' kelimesinde kesiliyor, isim eksik kaliyor; oysa giris_reading_master_runaware.png (600x10474) ayni sah

## 2000-0491 — PARDAYYAN
- **HAFIF** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Diskte E:\MITAS\Database\PARDAYYAN 2000-0491-1-0000-00-1\afis.jpg var ama bu gercek bir afis degil, credit_identity_cast_consensus_fallback ile secilmis bir oyuncu (Jean-Luc Bideau) film-karesi; KB/po

## 2000-0505 — DURUMU ANLAMAK
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Ham OCR ve master PNG'de yonetmen ismi/etiketi hic yok; VL(gemma4:26b) fallback da bos donmus (guven=OKUNAMADI), KB cross-check verdict=KAYNAK_YOK, otoriter_yonetmen=[]. Film gercek jenerik yazi akisi
- **KIMLIK** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Kimlik unsurlari (yonetmen/cast adi) hicbir karede/OCR'da fiziksel olarak yok; katalog XML'de isim kaydi var olabilir ama goruntu/OCR kanitiyla dogrulanamadi -> D_JENERIKTE_YOK (gorsel jenerikte yok).
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: qwen_qc.oyuncu_sayisi=0; raw_cap_dropped 798 ogenin tumu Fransizca reklam panosu metninin bozuk n-gram varyasyonlari (guard/garble_gate tarafindan dogru elenmis), gercek isim degil. Gercek cast jeneri

## 2000-0514 — KÖPEKLE BİR TATİL
- **YONETMEN** → C_OKUNAMAZ  — _OKUNAMAZ (yabanci/bozuk)_
   - ipucu: OCR 2 satir uretti (GOZDEN_GECIR bucket), credit_text/vl_fallback ikisi de yonetmen=[] guven=OKUNAMADI dondu; KB/IMDb sorgusu da 'OCR bos -> doldurma yok' notuyla bos kaldi. Kaynak karisik/bozuk latin
- **KIMLIK** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Kimlik cakismasi/kurulamama sebebi cast-ortusme=0 ve web capasi kilitlenememesi (KB verdict=KAYNAK_YOK); bu bir A_ELENDI (var-ama-silindi) durumu degil, D_JENERIKTE_YOK cunku jenerik/kredi metni gorun
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: otorite_audit.raw_cap_dropped listesinde 'Buto Bufo/Bufo Bufo/Bufo Pura/Pee Eaira/Taxra Taira' gibi 21 sahte-aday var ama bunlar gercek isim degil, goruntu gurultusunden (kumas deseni, isik yansimasi)
- **RENDER** → C_OKUNAMAZ  — _OKUNAMAZ (yabanci/bozuk)_
   - ipucu: _DURUM.json qwen_qc.latin_disi_alfabe_var=false (VL bunu gormemis) ama otorite_audit ve route.agir'de acikca 'Latin-disi kaynak (erken-translit) -> romanizasyon insan teyidi gerek' deniyor; ham OCR ve

## 2000-0517 — HARRY'NİN UYANIŞI
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - isim: **Declan Lowney (yalnizca KB otoriter kaynaginda; frame/OCR'da**
   - ipucu: _DURUM.json otorite_audit/kb.external_lookup: eslesen_film='Wild About Harry' (2000), otoriter_yonetmen=['Declan Lowney'] KB'de biliniyor ama 'OCR bos -> doldurma yok' kirmizi-cizgi kurali geregi KB-f
- **KIMLIK** → A_ELENDI / `guard`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **NightMan (1997/1999, Glen A. Larson yapimi TV filmi) footage**
- **OZET** → E_VERI_YOK  — _VERI YOK_
   - ipucu: INCELENECEK ALAN(LAR) sadece YONETMEN olarak belirtildigi icin OZET alaninda kanit toplanmadi; guven DUSUK, E_VERI_YOK isaretlendi. Gerekirse ayri bir OZET turu acilmali.

## 2001-9167 — HALIFAX-CANİ RUH
- **KIMLIK** → A_ELENDI / `deferans`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **LYNN HEGARTY (harici XML aday) vs ROGER SIMPSON (OCR/frame)**
   - ipucu: Yonetmen alani OCR+frame ile net (ROGER SIMPSON, final ciktiya da girmis) ama harici XML kaynagi celiskili 'LYNN HEGARTY' adayi sundugu icin sistem 'yon-dogrulama=CELISKI' bayragi koyup KONTROL'e dusu
- **CAST** → B_OCR_OKUYAMADI / `KB_veto`  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **REBECCA GIBNEY, CATHERINE WILKIN, EMILY BROWNING, NELL FEENE**
   - ipucu: Cast isimleri OCR+VL fallback ile dogru okunup final'e girmis (8/8); asil 'kimlik kurulamadi' bayragi cast-KB-ortusme=0 (kb.external_lookup verdict=KAYNAK_YOK, çapa bulunamadı) nedeniyle, yani harici 

## 2001-9194 — İNTİKAM
- **YONETMEN** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **KJELL SUNDVALL**
   - ipucu: _log.jsonl credit_validate: yonetmen status=DOGRULANAMADI, confidence=DUSUK, not='XML yakin(exact-degil): Kjell Sundvall~KTEL SUNDVALL' -- KB/XML cross-check bozuk transliterasyonla eslesmedigi icin d
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **PETER HABER**
   - ipucu: Final kunye 8 oyuncu listeler (Persbrandt..Aliaga) ama seri basrolu Peter Haber (Martin Beck) eksik; raw_cap_dropped kaniti onun izole bigram olarak degil hep onceki karakter-adiyla ('Martin Beck Pete
- **KIMLIK** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **KJELL SUNDVALL / PETER HABER**
   - ipucu: route.agir=[['KIMLIK','kimlik kurulamadi (cast-ortusmesi 0) / yanlis-film suphesi']] -- aslinda film doğru (Beck: Hamndens Pris/Intikam, 2001, yön. Kjell Sundvall) ve künye ogeleri frame+OCR'da dogru;

## 2001-9201 — HAYAL PEŞİNDE
- **KIMLIK** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Marc Martin LECAPITAINE / Professeur Raphael Marcel DOSSOGNE**
   - ipucu: Final kunye/PDF/txt sadece ILK 8 oyuncuyu birakmis (ELISE TIELROOY...MARTIN LECAPITAINE); kalan 17+ oyuncu hem framede hem ham OCR'da (ocr_ham.txt, dilim_oneocr.jsonl) NET okunuyor ama teslimde yok ->
- **KIMLIK** → A_ELENDI / `deferans`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **yok (yonetmen dogru cikti, ancak _DURUM.json bunu KONTROL ne**
   - ipucu: _DURUM.json neden listesinde 'qc_block: yonetmen-capasi zayif-teyit (tek-aday/yil±1 - insan onayi)' yaziyor; bu insan-onay bayragidir, hatali sonuc DEGIL -- final PDF'de Yonetmen=ALAIN ROBAK dogru ve 
- **KIMLIK** → E_VERI_YOK  — _VERI YOK_
   - isim: **yok**
   - ipucu: Video-ici OCR/gorsel kanit (baslik 'Les visions de Julia'/'JULIA'S VISIONS', yonetmen Alain Robak, tam cast) kendi icinde tutarli; 'yanlis film supesi' OCR/gorsel acidan desteklenmiyor ama KB tarafi v

## 2001-9238 — AĞIZ TADI
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Gercek yonetmen kredisi (Directed by) bu kopyada hic gorunmuyor; jenerikte yalnizca 2.unite/DP yonetmen unvanlari var, bunlar KB-fill/film-yonetmeni ile karistirilmamali.

## 2001-9314 — VAHŞİ AFRİKA
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: OCR+VL ikisi de bos donmus (ollama model deposu erisilemez, sistemsel ariza) ama gorsel jenerik zaten sadece harita - yonetmen karti mevcut degil gorunuyor.
- **KIMLIK** → E_VERI_YOK  — _VERI YOK_
   - ipucu: OCR bucket=HATA (0 satir ilk pass) + LLM/VL preflight basarisiz (ollama model deposu bos/erisilemez) -> kimlik dogrulama zinciri hic calisamadi; elenme degil veri-uretilememe durumu.
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: cikis_jenerik klasoru hic olusmamis (manifest: cikis frames=0); cikis_jenerik/giris_jenerik tum orneklerde insan ismi metni yok.
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: _DURUM.json: asr_status=failed, asr_segments=null, transcript_chars=null; subtitle.json sadece dil-tespit sinyali icerir, gercek transkript metni hic uretilmemis.

## 2001-9318 — MANASLU
- **YONETMEN** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Hans-Peter Stauber**
   - ipucu: Final kunyede Yonetmen alaninda sadece 3 isim var (Bernd Seidel, Lutz Maurer, Manfred Gabrielli); Hans-Peter Stauber hem framede hem ham OCR'da acikca yonetmen listesinde iken final'de dusurulmus - mu
- **YONETMEN** → A_ELENDI  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **(sira/sayisi dogrulamasi)**
   - ipucu: _DURUM.json neden alaninda zaten 'yonetmen listesi supheli (3 isim - crew karismasi olasi)' notu var; frame kaniti 4 isim oldugunu ve 4.sunun (Stauber) yanlislikla elendigini dogruluyor.
- **CAST** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Hans Ebner / Erika Huber / Veronika Schweighofer / Wolfgang **
   - ipucu: Final kunyede Oyuncular alaninda bu gercek expedition kadrosundan hic isim yok; final'e sadece Sprecher (Ernst Grissemann) ve konuk-roportaj Extrembergsteiger (Peter Habeler) girmis - gercek film konu
- **CAST** → A_ELENDI / `lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Ernst Grissemann (Sprecher) / Peter Habeler (Extrembergsteig**
   - ipucu: Final kunye bu iki ismi 'Oyuncular' seklinde etiketlemis ama gercekte biri spiker/anlatici biri konuk-roportaj uzmani; gercek expedition kadrosu (Ebner, Huber, Kristinus, Staudacher, Gruber, Schweigho
- **KIMLIK** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - ipucu: KIMLIK genel hukmu: cast okunurdu (A) - hem yonetmen hem gercek expedition-cast isimleri framede/OCR'da nettir; sorun OCR okuyamamasi degil, KB/web-capa dogrulamasinin bu isimleri eslestirememesi ve f

## 2001-9375 — UZAKTAKİ KASABA
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: _log.jsonl/trace_summary.md: KB lookup otoriter_yonetmen=['Terry Green'] bulundu ama OCR/goruntude karsiligi olmadigi icin (verdict=OKUNAN_YOK, kb_floor_added=[]) finale yazilmadi; bu bir 'elenme' deg

## 2002-9058 — KANDIRMACA
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Hem master PNG hem ham OCR hem VL (vl_yon_aday=null) yonetmen bulamadi; bu kopyada yonetmen kredisi jenerikte fiilen yok (ya da kesilmis) - KB/web ile de doldurulamadi.
- **KIMLIK** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **JUDD NELSON, MICHELLE NOLDEN, STEWART BICK, LOUIS GOSSETT JR**
   - kod: `scripts/credit_role_lexicon.py:164-203 (_match_head/_strip_head/director_name_from_line); `
   - ipucu: credit_role_lexicon.director_name_from_line/anchor_roles icine 'karakter-adi + oyuncu-adi' cift-sutun tespiti eklenmeli: adayin HEMEN ALTINDAKI/yanindaki satir buyuk-harf 2-3 kelimelik baska bir isims

## 2002-9089 — YÜZÜKLERİN EFENDİSİ
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: jenerik_debug/detector/result.json: status=not_found, reason='No persistent credit text cluster found'; vl/pool ve master_png de no_frames/empty_pool -- tum katmanlar bos, yonetmen jenerik dogal olara
- **KIMLIK** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: orijinal_ad alaninda 'THE LORD OF THE RINGS (THE TWO TOWERS)' dolu geliyor (muhtemelen KB/otomatik esleme), ancak bu goruntu/OCR kanitiyla degil harici KB ile geldigi icin kimlik alani jenerikte gorse
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: qwen_qc.oyuncu_sayisi=0, qwen_qc.notlar='Oyuncular ve yonetmen kisimlari bos'; jenerik_debug/detector ve vl/pool ikisi de bos donmus -- cast bilgisi gercekten jenerikte yok, OCR-okuyamama degil (D, B 

## 2002-9115 — HALIFAX - İKİ SUÇLU
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **MONICA MAUGHAN; ROSS THOMPSON; MARGARET CAMERON; IAN ROBERTS**
   - ipucu: _DURUM.json route.hafif=[CAST_CAP_DUSEN], neden='cap-ustu okunan 621 oyuncu dustu (Beyond Simpson, Simpson Mesurier, Gibney Rebecca)'; final kunye_teslim.md sadece ilk 10 oyuncuyu birakmis (GIBNEY..JE

## 2002-9202 — SHERLOCK HOLMES'İN DOĞUŞU
- **HAFIF** → A_ELENDI / `guard`  — _FIXLENEBILIR (framede var, elendi)_
   - ipucu: Kaynak afis.jpg (hub kokunde ve pdf/ altinda, 780x1169, MURDER ROOMS/THE DARK BEGINNINGS OF SHERLOCK HOLMES posteri, gozle acildi ve okunur) 'credit_identity_cast_consensus_fallback' kaynagindan pdf a

## 2002-9241 — SESSİZ AMERİKALI
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Ham OCR (1148 satir) ve tum giris_reading_master dilimleri (p01-p03, gorsel olarak acildi) taranmis; 'DIRECTED BY' / tam ad 'Phillip Noyce' hicbir yerde yok. Sadece soyadi 'Noyce' ekip-listesi baglami

## 2002-9246 — RENE
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Joël Lefrançois**
   - ipucu: otorite_audit.ocr_dropped listesinde; route.hafif=CAST_CAP_DUSEN; final kunye_teslim.md Oyuncular listesinde (10 kisi cap) yok, cap-disi dustu.
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Michel Barbelivien**
   - ipucu: otorite_audit.ocr_dropped listesinde; qwen_uyari 'temiz-okunan isim dustu'; final Oyuncular (10 kisi cap) listesinde yok; master_dilim birlestirmesinde de bu orta segment dahil edilmemis.

## 2003-9048 — İHTİRAS CİNAYETİ
- **YONETMEN** → A_ELENDI / `guard`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Bill L. Norton**
   - ipucu: Ham OCR yonetmeni DOGRU yakalamis (master_dilim/dilim_oneocr.txt) ama final derlemede kullanilan ocr/ocr-15959d5b/ocr_ham.txt ve kunye.txt sadece CIKIS jenerigini icerir (620 satir, 'Ronnie D. Clemmer

## 2003-9049 — DENİZLER ALTINDA 20.000 FERSAH
- **YONETMEN** → B_OCR_OKUYAMADI / `deferans`  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **SCOTT HEMING**
   - ipucu: Frame+ham-OCR'da acik ve net; final kunye.txt'de 'Yonetmen: SCOTT HEMING' dogru yazilmis (VAR, sorun yok). route.agir'deki 'yonetmen-capasi zayif-teyit (tek-aday/yil±1)' uyarisi OCR okunabilirligiyle 
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **NILS HAALAND / MICHAEL HARTIG / HANNAH KOSLOSKY / JERRY LONG**
   - ipucu: Final kunye.txt'de sadece 6 oyuncu kaldi (JOHN LEE, JENNIFER ANDREWS ANDERSON, ANTHONY CLARK, MATT KAMPRATH, TONY WIKE, D. KEVIN WILLIAMS); qwen_qc.oyuncu_sayisi=6 ile uyumlu -- cast_cap (ust-sinir) y
- **CAST** → B_OCR_OKUYAMADI  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **JOHN LEE (AS CAPTAIN NEMO)**
   - ipucu: Bas rol JOHN LEE hem framede hem ham OCR'da acik; final kunye.txt'de de dogru VAR -- bu alt-kanit tutarliligi teyit icin eklendi, ayri bir drop yok.

## 2003-9059 — CİNAYET YERİ
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **SHARON BAKKER / BLAINE HART / JODY PETERS / SEAN HOY / KAREN**
   - ipucu: _DURUM.json otorite_audit.raw_cap_dropped listesinde bu 7 isim (Sharon Bakker, Blaine Hart, Jody Peters, Sean Hoy, Karen Kimberly, Danielle Lindenbach, Brie Spilchen, ayrica Hellen/Donald Collier) 14-
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Bu finding sadece dogrulama amacli: ana 10 oyuncu icin final kunye dogru, sorun yalnizca cap=10 sinirlamasindan sonraki tasan (11.+) roller icin A_ELENDI bulgusunda; iki finding birlikte CAST alaninin

## 2003-9104 — UFAKLIK İÇİN BİR BABA
- **YONETMEN** → A_ELENDI / `guard`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Peter Kahane**
   - ipucu: Ana OCR job (ocr-fe498dde) bos donmus (bucket=HATA, 'ocr_metni_yok'), VL fallback gemma4:26b crash olmus ('vl':'kostu'); paralel master_dilim OneOCR gecisi yonetmeni dogru okumus ama bu veri credit_te
- **KIMLIK** → A_ELENDI / `identity_unlocked`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Ein Vater fur Klette (Peter Kahane, 2003, Alman filmi)**
   - ipucu: Kimlik kilitlenememesi, yonetmen+cast alanlari OCR/VL zincir hatasi yuzunden bos kaldigi icin KB/TMDB aramasina hicbir aday (isim) verilememesinden kaynaklaniyor; karede kimlik acikca okunur (Alman ya
- **CAST** → A_ELENDI / `guard`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Heio von Stetten, Muriel Baumeister, Vespa Vasic, Sabrina Wh**
   - ipucu: v4 raporunda 'cast': 0, 'cast_list': ['—'] -- OCR ana job hatasi + VL fallback crash zincirinden dolayi hicbir isim credit_text asamasina ulasamadi; frame'de kadro acikca mevcut ve okunur, D_JENERIKTE
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: debug_trace/trace.jsonl icinde 'asr' asamasina ait tek bir log kaydi yok (stage listesi: credit_text, credit_validate, kb, ocr, pdf, pipeline, qc_final, routing, vl_fallback) -- ASR sessizce basarisiz

## 2003-9136 — HARİKA KÖPEK 5
- **KIMLIK** → B_OCR_OKUYAMADI  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **Tyler Boissonnault; Edie McClurg; Patrick Cranshaw; Robert T**
   - ipucu: Cast hem framede hem ham OCR'da (kunye.txt) net okunur halde mevcut; _DURUM'daki 'cast-orusmesi 0' KB/XML referans-eslesme sorunu (orijinal ad karisikligi AIRBUD 5 SPIKES BACK), OCR/frame okunabilirli

## 2003-9195 — JERICO APARTMANI
- **KIMLIK** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Jennifer Tilly / Maribel Verdú / Peter Keleghan / Pierre Rio**
   - ipucu: Ham OCR 30 oyuncuyu da yakalamis (ocr_ham.txt satir 23-52) ama final teslimde (kunye_teslim.md, .txt) sadece ilk 8 isim (Allen..Cobden) kalmis; otorite_audit.ocr_dropped'ta acikca 6 isim itiraf edilmi
- **KIMLIK** → A_ELENDI / `identity_unlocked`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **IAN STEEL (ortak yonetmen)**
   - ipucu: Final teslimde (kunye_teslim.md) sadece 'Yonetmen: MARTIN POLLINS' yazili; ortak yonetmen IAN STEEL kaybolmus. DAVID SEIDEL zaten yonetmen degil (yanlislikla ham OCR'da yonetmen blogunun hemen altina 
- **KIMLIK** → C_OKUNAMAZ / `KB_veto`  — _OKUNAMAZ (yabanci/bozuk)_
   - isim: **ALBERTO SCIAMMA (vl_yon_aday / KB adayi)**
   - ipucu: _DURUM.json neden[]: 'yonetmen dogrulama: kaynak-celiskisi (aday: ALBERTO SCIAMMA)' -- bu gercek-dunya (IMDB) KB adayi olabilir ama filmin kendi jenerik goruntusunde/OCR'da desteklenmiyor; jenerikteki

## 2003-9198 — JERICO APARTMANI
- **KIMLIK** → A_ELENDI / `cast_cap/KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Jennifer Tilly / Peter Keleghan / Pierre Rioux / Bruce Ramsa**
   - ipucu: _DURUM.json otorite_audit.ocr_dropped listesi ile birebir örtüşüyor; trace.jsonl'de qc_block_floor={hedef:8,ulasilan:8,kabul:true} — sistem yalnızca KB'nin 8 kişilik otoriter cast'ıyla örtüşen ilk 8 i

## 2003-9208 — BORÇ
- **KIMLIK** → A_ELENDI / `deferans`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **YÖNETMEN: İbrahim Habibulla oğlu | CAST: Rüstem Mürsel oğlu,**
   - ipucu: Kimlik verisi OCR ham metinde, master_dilim OneOCR'da, VE iki ayrı master görselde (giris+cikis) birebir tutarlı ve tam okunur; final teslim PDF/MD'ye de zaten yazılmış (drop edilmemiş). Sistem yine d

## 2004-9094 — İSYAN
- **YONETMEN** → A_ELENDI / `garble_gate`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **GULZAR**
   - ipucu: Ham per-frame OCR (ocr_raw_all.txt) yonetmeni 9 kez dogru okumus; fakat kunye-konsolidasyon adiminda ocr_ham.txt icine giris'teki 'Written & Directed By' satiri ile alakasiz cikis-segment cop metni ('
- **KIMLIK** → D_JENERIKTE_YOK / `cast_cap`  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Asil oyuncu kadrosu (10 kisi) genel olarak OKUNABILIR (B degil), ama 927 satirlik cap mekanizmasi hem cop n-gramlari hem de gercekten gecerli iki ismi (Tabu, Mohan Agashe) beraber elemis; bu bir cast_
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: _DURUM.json'da asr_status=done, asr_segments=2002, transcript_chars=52194 -- transkript mevcut (asr/asr-8fe3faa6/run/transcript.txt), ancak inceleme talimati sadece YONETMEN alani icin verildi; OZET a

## 2004-9131 — YALNIZ SAVAŞÇI
- **KIMLIK** → A_ELENDI / `deferans`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **DAVID MAMET**
   - ipucu: _DURUM.json.otorite_audit.raw_cap_dropped listesinde 'David Mamet' 5 kez dusurulmus; neden alaninda 'yonetmen-capasi zayif-teyit (tek-aday/yil±1 - insan onayi)' yaziyor - OCR/frame dogru yakalamis ama
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: qwen_qc.oyuncu_sayisi=0 ve notlar 'Oyuncular bolumu bos' diyor; ham OCR'in tamaminda (58+59+107 satir) gercek oyuncu ismi gecmiyor, yalnizca kurgu-ici TV haber altyazisi 'LAURA NEWTON' (karakter adi) 

## 2004-9132 — KÖŞENİN KRALI
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Ham OCR (ocr_ham.txt, dilim_oneocr.txt, kunye.txt) ve master PNG/frame taramasinda YONETMEN/DIRECTOR/REJI etiketi hic bulunamadi; IMDb/Wikidata/XML dis-kaynak dogrulamasi da bos donmus (KB-fill yapilm

## 2004-9139 — GÜLLERİN SAVAŞI
- **YONETMEN** → A_ELENDI / `garble_gate`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Patrick Leung / Cory (Gary) Yuan (梁柏堅 / 元奎) - 'directed by'**
   - ipucu: Yonetmen adi (Patrick Leung/Cory Yuan) hem gorselde hem ham OCR'da mevcut ama OCR ciktisi agir garble (rected, Patrick Leane, 梁佰壓) oldugu icin credit_text/garble_gate tarafindan elendi; _DURUM route.a
- **KIMLIK** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **THE HUADU CHRONICLES: BLADE OF THE ROSE (2004, Emperor Motio**
   - ipucu: KB, TR baslik 'Güllerin Savaşı' ile 1989 ABD filmi 'War of the Roses'i (Danny DeVito/Michael Douglas) eslestirmis; ama gercek goruntu 2004 HK filmi Blade of the Rose'dur; cast_ortusme=0 -> qc2_web 'ça
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Donnie Yen (甄子丹), Jaycee Chan (房祖名), Charlene Choi, Gillian **
   - ipucu: OCR ciktisi agir garble (isim kesikleri: 'onsie Yen', 'Chee Po L', 'isoe C') oldugu ve dublaj/lexicon anchor eslesmedigi icin credit_validate cast=0 birakti; trace: 'qc_block: oyuncu yok', cast_ortusm
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: ASR asamasi basarisiz oldugu icin gercek transkript uretilmemis; _DURUM.neden listesinde 'özet yok/kısa (5k — gerçek özet üretilmemiş)' teyit ediyor; final PDF'te '(ÖZET AYRI BİR ADIMDA ÜRETİLECEKTİR.

## 2004-9143 — DOĞRU KILAVUZ
- **HAFIF** → E_VERI_YOK  — _VERI YOK_
   - ipucu: route.hafif dizisi bos oldugundan HAFIF kategorisinde denetlenecek somut kayit yok; sistem bu filmi kusursuz/TEMIZ siniflandirmis. Gorsel/OCR dogrulamasi yapildi: giris master (master_dilim/giris_read

## 2004-9160 — HOTEL RWANDA
- **YONETMEN** → A_ELENDI / `lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **TERRY GEORGE**
   - ipucu: _DURUM.json route.agir 'yonetmen garble (okunamadi)' ve vl_yon_aday=null diyor ama hem ham OCR hem master goruntu ismi tertemiz veriyor; final PDF'de isim yanlislikla sadece 'Yapimci' satirina yazilmi

## 2004-9206 — KOUDAYU
- **YONETMEN** → A_ELENDI / `guard`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **佐藤純彌 (Junya Sato / Sato Junya)**
   - ipucu: OCR 7 varyant uretmis (蓝督/上督/進督/底督/店餐/監督/監情), hepsinde isim '佐藤純彌' sabit ama unvan-token'i (監督) tutarsiz okunmus; sistem konsensus kuramayip yonetmen alanini bos birakmis olabilir. _DURUM.json vl_yon_
- **KIMLIK** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **市原清彦, 山崎有右, 重水直人, 伊藤哲哉, 天田益男 (Japon oyuncular - Kanji) ve ヴィ**
   - ipucu: c_0471.png ve c_0520.png frame'lerinde onlarca oyuncu adi (hem Japon Kanji hem Rus Katakana transliterasyonu) tamamen okunur durumda; final PDF'te sadece 9 romanize isim kalmis (KAWATANI TAKUZO, OKITA
- **RENDER** → B_OCR_OKUYAMADI / `lexicon_anchor_misparse`  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - ipucu: Kaynak jenerik tamamen Japonca (Kanji/Katakana), Latin metin sadece 'TOKYO FM·JFN', 'IMAGICA', 'FUJICOLOR', 'DOLBY STEREO' gibi kurumsal etiketlerden olusuyor; final PDF'te Kiril/Yunan/Arap/CJK karakt

## 2005-9051 — MURPHY KANUNLARI 2
- **YONETMEN** → B_OCR_OKUYAMADI  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **Peter Lydon**
   - ipucu: _DURUM.json 'yonetmen garble (okunamadi)' diyor ama gercek OCR kaynagi (dilim_oneocr.txt, oneocr fallback) yazi yi dogru yakalamis; credit_text asamasi bunun yerine bos kalan ocr-6fe6e673/kunye.txt'yi
- **KIMLIK** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Murphy's Law (BBC dizisi, S1E?) - TRT kaydi: MURPHY KANUNLAR**
   - ipucu: kb.external_lookup verdict=KAYNAK_YOK, cast_ortusme=null, qc2_web capa bulunamadi -> kimlik dogrulanmis olsa da KB/TMDB eslesme mekanizmasi (cast bos oldugu icin) devreye giremedi; kok neden CAST/YONE
- **CAST** → B_OCR_OKUYAMADI  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **James Nesbitt, Claudia Harrison**
   - ipucu: credit_text/vl_fallback asamalari cast:[] donmus (guven=OKUNAMADI); sebep primer OCR motorunun MOTOR_YOK/DLL hatasiyla bos kunye.txt uretmesi, oysa fallback oneocr (dilim_oneocr.txt) isimleri dogru ya
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: _DURUM.json asr_status=failed, transcript_chars=null; kunye_teslim.md 'ÖZET AYRI BİR ADIMDA ÜRETİLECEKTİR' notuyla bos birakilmis; ozet uretimi icin ASR/transkript adimi hic basarili calismamis.

## 2005-9162 — DİPTEKİLER
- **CAST** → A_ELENDI / `nonfilm_marker`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Low Fuel / Fuel Low / Fuel Wiu**
   - ipucu: _DURUM.json neden: 'CAST_CAP_DUSEN: cap-ustu okunan 2696 oyuncu dustu (Low Fuel, Fuel Low, Fuel Wiu)' -> bu adaylar gercekte prop/sahne yazisi oldugu icin dogru elenmis (nonfilm_marker); gercek oyuncu

## 2006-9063 — KUMRULAR GİBİ
- **YONETMEN** → A_ELENDI / `garble_gate`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Michelle Danner**
   - ipucu: Birincil OCR pipeline (ocr/ocr-db1960fb/kunye.txt) diskte hic uretilmemis (bucket=HATA, ocr_lines=0) -> credit_text 'ocr_metni_yok' ile bos donmus, VL fallback de bos kalmis; final teslimde Yonetmen='
- **KIMLIK** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **How to Go Out on a Date in Queens (2006)**
   - ipucu: cast okunurdu (A) ama OCR-pipeline hatasi nedeniyle KB/TMDB capa bulunamadi ('capa bulunamadi (KB+TMDB)') -> kimlik_dogru=False, kimlik celismesi ile KONTROL'e dustu.
- **CAST** → A_ELENDI / `guard`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Brian Drillinger, Christine Dunford, Esai Morales, Enrique M**
   - ipucu: Birincil OCR dosyasi (ocr/ocr-db1960fb/) diskte yok; credit_text ve VL fallback ikisi de 'guven: OKUNAMADI, hata: ocr_metni_yok' ile bos donmus, final PDF'te Oyuncular='-', cast=0.
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: _DURUM.json: asr_status=failed, asr_segments=null, transcript_chars=null; asr klasorunde run/subtitle.json ve _asr_16k.wav disinda transcript*.txt/chlang.json yok -> ozet uretilecek kaynak metin hic o

## 2006-9110 — GERÇEK KUZEY
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **YVONNE COSTELLO, PAT KIERNAN, TUTU BABATUNDE, ZANDIE MABIUSA**
   - ipucu: _DURUM.json.neden ve route.hafif='CAST_CAP_DUSEN' (karar=Kontrol) bu 5 yan rol + 24 figurani onaylar; final kunye_teslim.md sadece 10 ana oyuncuyu iceriyor, kapasite sinirindan dustu.

## 2006-9112 — BÜYÜK FİNAL
- **YONETMEN** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Gerardo Olivares**
   - ipucu: KB cross-check (debug_trace/trace.jsonl, stage=kb) otoriter_yonetmen=['Gerardo Olivares'] (IMDb tt0476240, film='La gran final' 2006) dogru buldu, ama okunan_yonetmen bos/garble oldugu icin 'kirmizi c

## 2006-9175 — ONDAN UZAKTA
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - isim: **Sarah Polley (KB/web adayi, kaynak-celiskili, reddedilmis)**
   - ipucu: Ham OCR (467 satirlik tam kunye) ve tum giris-jenerigi frame'lerinde filmin yonetmenine ait tek bir DIRECTED BY/WRITTEN AND DIRECTED BY karti yok; 'Sarah Polley' KB-tahminidir, goruntude/OCR'da hic ge
- **KIMLIK** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Kristen Thomson, Michael Murphy, Wendy Crewson, Nina Dobrev**
   - ipucu: otorite_audit.ocr_dropped alani bu 4 ismi acikca 'temiz-okunan isim dustu' olarak listeliyor; qwen_qc.oyuncu_sayisi=12 derken final'de 10 var - cast-cap/oyuncu-sinirlama mekanizmasi OCR'da var olan do

## 2007-9067 — YARIŞMA DÜNYASI
- **HAFIF** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: route.hafif=["AFIS"], teslim dosya adi "_HAFIF_AFIS.pdf" ile tutarli; afis/poster hicbir kaynakta (ham OCR, master PNG, jenerik frame havuzu) tespit edilemedi, dolayisiyla eksiklik bir OCR/okuma hatas

## 2008-9064 — ANNEM ANNEM
- **YONETMEN** → B_OCR_OKUYAMADI  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **MICKI DICKOFF**
   - ipucu: reading_master_runaware (cikis) manifest'i frames=0/status=no_frames; ana OCR motoru da 0 satir/bucket=HATA/motor=None dondu (MemoryError sonrasi) — cikis segmenti hic OCR edilmedi, yonetmen bilgisi f
- **KIMLIK** → A_ELENDI / `identity_unlocked`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Mother, Mother (1989, yön. Micki Dickoff)**
   - ipucu: trace.jsonl: video_okuma.cast_okunan=[] / guven=OKUNAMADI oldugu icin KB cross-check cast-örtüşme=0 çıktı ve web çapası kilitlenemedi; oysa cast+başlık+telif üçgeni framede zaten mevcuttu — asıl OCR m
- **CAST** → A_ELENDI / `identity_unlocked`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **BESS ARMSTRONG, POLLY BERGEN, PIPER LAURIE, JOHN DYE**
   - ipucu: trace.jsonl video_okuma.cast_okunan=[]/guven=OKUNAMADI — ana OCR motoru (ocr-f0bf3042) 0 satır/bucket=HATA verdiği için cast pipeline'a hiç girmedi; aynı isimler ayrı bir OneOCR geçişinde (master_dili
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: asr/asr-4cd16079/run/ klasöründe transcript*.txt hiç yok, sadece ham wav ve boş subtitle.json var; _log.jsonl 'ozet_atlandi: transcript yok (ASR atlandı/boş)' diyor — özet üretecek transkript hiçbir a

## 2008-9069 — BEYAZ AVUÇLAR
- **HAFIF** → E_VERI_YOK  — _VERI YOK_
   - ipucu: _DURUM.json: route.hafif=[] ve route.agir=[], neden=[], karar='Hazır', aciklama='kusursuz'; qwen_qc tum bayraklar temiz (turkce_karakter_bozuk_var=false, latin_disi_alfabe_var=false); vl_yon_aday=null

## 2008-9089 — KUTSAL SİLAH
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Jenerikte bagimsiz 'YONETMEN/감독' basligi hic yok; sadece 조감독(yardimci yönetmen)+무술감독(dovus yönetmeni) var. _DURUM.json vl_yon_aday=null, 'yönetmen garble (okunamadı)' notuyla tutarli; raw_cap_dropped'
- **CAST** → B_OCR_OKUYAMADI / `garble_gate`  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **정재영 (Jung Jae-young), 안성기 (Ahn Sung-ki), 한은정 (Han Eun-jung)**
   - ipucu: Cast isimleri framede acik/okunur durumda ama ham OCR motoru '( CAST )' basligindan sonraki tum satirlari tamamen garble etmis (hicbiri gercek isimle eslemiyor); qwen_qc.oyuncu_sayisi=0 kaydi framedek
- **RENDER** → C_OKUNAMAZ / `nonfilm_marker`  — _OKUNAMAZ (yabanci/bozuk)_
   - ipucu: Iki ayri sorun: (1) filmin gorsel dekorundaki Latin-disi Hanja motifleri OCR'a kredi metni gibi sizmis, (2) net okunan Latin teknik terimler (Dolby, EON, Bluecap) OCR tarafindan fonetik olarak bozular

## 2008-9110 — ŞAMPİYONLAR
- **KIMLIK** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **SIUMING TSUI (yönetmen) + DICKY CHEUNG, PRISCILLA WONG, DEBB**
   - ipucu: OCR+görsel kanıt tam okunuyor ve final PDF'de (2008-9110-1-0000-90-1 ŞAMPİYONLAR.pdf) yönetmen+8 oyuncu eksiksiz mevcut (kayıp yok); trace_summary.md satır29'da fuzzy modülü 'yonetmen KB ile eşleşmedi
- **RENDER** → A_ELENDI / `lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **驕陽電影 / 徐小明 (Çince jenerik metni)**
   - ipucu: Final render'da romanize Latin isimler kullanılmış (final PDF'de CJK yok) ama route.agir kaydı 'Latin-dışı alfabe sızdı' diyor çünkü kaynak/ham OCR katmanında CJK karakterler mevcut; qwen_qc.latin_dis

## 2008-9163 — ÜÇÜZLER DON KİŞOT'UN İZİNDE
- **KIMLIK** → A_ELENDI / `garble_gate / lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Jordi Valbuena + Maria Gol (Realizacion / Dirigido por - iki**
   - ipucu: Final PDF'de Yonetmen alaninda sadece 'JORDI VALBUENA' basilmis, es-yonetmen 'MARIA GOL' dusurulmus; _DURUM.json otorite_audit.raw_cap_dropped listesinde 'Valbuena Maria'/'Maria Gol' n-gram cifti tekr
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Bu bir animasyon dizisi (Las Tres Mellizas/CROMOSOMA-TVC yapimi) olup jenerikte seslendirme kadrosu credit'i hic yer almiyor; qwen_qc ve ham OCR taramasi (grep: voc|voice|actor|actriz|reparto|cast) so

## 2009-9007 — HAYATIN TUZU
- **OZET** → OZET_URETILEMEDI  — _ASR ARIZASI_
   - ipucu: ASR tamamen basarisiz (asr_status=failed); transcript dosyasi hic yok, chlang.json yok; final teslimde OZET alani placeholder metin.

## 2009-9137 — KUSURSUZ BİR GÜN CENAZE TÖRENİ
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Sistem cikis jenerigini hic OCR'a sokmamis (cikis_jenerik klasoru bos, ocr cikis frames=0); ama gozle de tam ekip listesinde 'Director' satiri yok — TV bolumu jeneriginde bu unvan hic verilmemis olabi
- **KIMLIK** → B_OCR_OKUYAMADI  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **Perfect Day: The Funeral (Ingilizce yapim, TV filmi/dizi bol**
   - ipucu: Cast ve prodüksiyon ekibi cikis jeneriginde net okunur durumda ama sistem cikis'i hic OCR/kimlik-eslesmesine sokmamis (ocr cikis frames=0, cikis_jenerik klasoru bos); dolayisiyla kimlik cikis kredisiy
- **CAST** → B_OCR_OKUYAMADI  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **Christopher Bisson (Billy), Josephine Butler (Rachel), Tom G**
   - ipucu: final_DURUM.json ocr_lines=0, otorite_audit.ocr_dropped=[] (drop yok, hic uretilmemis); cikis jenerigi (720 kare mevcut) pipeline tarafindan hic taranmamis/OCR'a sokulmamis, bu yuzden 14 oyuncu ismi t
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: _DURUM.json: asr_status="failed", asr_segments=null, transcript_chars=null; asr/ altinda transcript*.txt veya chlang.json yok, sadece bos altyazi-tespit sonucu var; kunye_teslim.md'de '(ÖZET AYRI BİR 

## 2009-9153 — AJAMİ
- **YONETMEN** → A_ELENDI / `deferans`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Scandar Copti**
   - ipucu: _log.jsonl credit_validate event'inde IMDb+Wiki HER IKISI de yonetmen olarak ['Yaron Shani','Scandar Copti'] listeliyor (GUCLU), ama not: 'dissent yutuldu (bagimsiz teyit var): XML=[SCANDAR COPTI]', c

## 2010-1158 — AŞK ŞARKIM
- **YONETMEN** → D_JENERIKTE_YOK / `guard`  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: _DURUM.json'daki 'yonetmen garble (okunamadi)' etiketi yaniltici: aslinda garble degil, jenerikte (ne giris ne cikis crawl'inde) yonetmen karti/etiketi hic bulunmuyor -> D_JENERIKTE_YOK, guard/garble_
- **KIMLIK** → A_ELENDI / `lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **RENEE ZELLWEGER / FOREST WHITAKER / NICK NOLTE (gercek basro**
   - ipucu: cast gercekten okunabiliyordu (crew/performed-by baglaminda Zellweger, Whitaker adlari acikca var) fakat cikarim adimi rol-etiketi/oyuncu-adi hizalamasini kaybedip yanlislikla ilk 8 yan-rol ismini 'Oy

## 2010-9150 — HANNA'NIN ALTINLARI
- **YONETMEN** → B_OCR_OKUYAMADI / `guard`  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **(yonetmen adi jenerikte tespit edilemedi; sadece DOP=Eric Zi**
   - ipucu: Asil OCR motoru (paddle) HATA/0-satir verdi; ayni jenerik master'i 17 dk sonra ayri calisan OneOCR (dilim_oneocr, ts 08:18) net okudu ama final _DURUM.json/PDF/routing (ts 08:02:58) bu sonucu hic kull
- **KIMLIK** → B_OCR_OKUYAMADI / `guard`  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **Morissa O'Mara (Hanna), Alana O'Mara (Jasmine), Dan Benson (**
   - ipucu: KB/IMDb/Wiki cross-check hic denenmedi cunku giris otomatik OCR ciktisi bos geldi (otorite_audit.ocr_dropped=[] -- lookup hic tetiklenmedi); cast-ortusme=0 bu yuzden yapay. Frame'ler okunur, sadece as
- **CAST** → B_OCR_OKUYAMADI / `guard`  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **Morissa O'Mara, Alana O'Mara, Dan Benson, Kevin Horton, Boyd**
   - ipucu: _DURUM.json 'cast': [] ve 'oyuncu yok' diyor ama bu yalnizca paddle-OCR HATA (0 satir) verdigi icin; frame'ler bizzat acilip okundugunda oyuncu listesi tamamen mevcut ve okunur -- final karara giren O
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: Ardindan 'ozet_atlandi: transcript yok (ASR atlandi/bos) -- ozet uretilmedi' (ts 08:02:27). _DURUM.json: asr_status=failed, transcript_chars=null. Kok neden GPU bellek yetersizligi -- transkript hic y

## 2010-9169 — PERCY JACKSON-ŞİMŞEK HIRSIZI
- **YONETMEN** → A_ELENDI / `guard`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Chris Columbus**
   - ipucu: Ana OCR motoru (ocr-1d4f3d25) 990 frame tarayip bucket=HATA/ocr_metni_yok donmus; credit_text/qc1/vl_fallback/kb tum zinciri bu bosluktan dolayi 'yonetmen': [] ile ilerlemis. Giris_jenerik modulu (one
- **KIMLIK** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - ipucu: Ana OCR'in HATA/bos donmesi yuzunden credit_text zincirine yonetmen/cast hic girmedi; KB lookup'a bos girdi verildigi icin dogal olarak eslesme bulunamadi. Kok neden ayni guard/OCR-HATA zinciri; kimli
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Giris jeneriginde sadece prodüksiyon/dagitim logolari + 1 yonetmen karti var, oyuncu kartlari yok; cikis jenerigi (genelde tam cast listesinin oldugu yer) hic tespit edilmemis/frame uretilmemis. Ana O
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: asr/asr-0e297f29/run altinda sadece _asr_16k.wav ve subtitle.json var; hicbir transcript*.txt veya chlang.json dosyasi yok. ASR tamamen basarisiz kaydedilmis (60 ornekten 0 hit). Final kunye_teslim.md

## 2010-9199 — AYNADAKİ DÜŞMAN
- **KIMLIK** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **HAKAN KURŞUN**
   - ipucu: _DURUM.json neden alanında 'aday: CEM AKYOLDAŞ' geçiyor ama bu isim 3 ham OCR kaynağında (ocr_ham.txt, dilim_oneocr.txt, kunye.txt), VL guarded/candidate_names ve card_0001.png karesinde HİÇ görünmüyo
- **KIMLIK** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - isim: **HARİKA UYGÜR / MİNE GÜLER**
   - ipucu: KIMLIK 'cast-örtüşmesi 0' hükmü doğru: jenerikte gerçekten yalnızca 2 oyuncu adı listelenmiş (kapsamlı bir 8 kişilik oyuncu kadrosu görsel/OCR kaynaklarında yok), raw_cap_dropped'daki uzun bozuk çift-
- **RENDER** → C_OKUNAMAZ  — _OKUNAMAZ (yabanci/bozuk)_
   - ipucu: _DURUM.json qc_block 'Latin-dışı kaynak (erken-translit)' tespiti doğrulandı: framede ve ham OCR'da Arapça metin fiilen mevcut, romanizasyon/insan teyidi gerekliliği gerçek bir bulgudur, OCR motoru bu

## 2010-9252 — DERTLER BENİM OLSUN
- **RENDER** → E_VERI_YOK  — _VERI YOK_
   - ipucu: _DURUM.json'daki 'Latin-dışı alfabe sızdı' uyarısı jenerik/RENDER'dan degil, ocr_ham.txt satır 128-163'teki Arapça diyalog-altyazı bloğundan kaynaklanıyor (film içi sahne, kunye/jenerik değil); final 

## 2010-9262 — NAMUS DÜŞMANI
- **YONETMEN** → B_OCR_OKUYAMADI  — _FIXLENEBILIR (framede okunur, OCR kacirdi)_
   - isim: **Zeki Alasya (زكي آلاسيا)**
   - ipucu: Ana besleme OCR'i (ocr/ocr-7bae00ff/ocr_ham.txt, bucket=GUVENILIR) yonetmen adi satirini kacirmis; ayni frame'i tarayan alternatif master_dilim/dilim_oneocr.txt motoru ismi dogru yakalamis ama final k
- **RENDER** → C_OKUNAMAZ  — _OKUNAMAZ (yabanci/bozuk)_
   - ipucu: Route'un 'RENDER: Latin-disi alfabe (Kiril/Yunan/Arap/CJK) sizdi' tespiti ISABETLI ve dogru bir guvenlik/KONTROL tetiklemesi; bu bir hatali eleme degil, kaynagin gercekten Arapca dublaj/jenerik kopyas

## 2010-9265 — HASİP İLE NASİP
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **ERSUN KAZANÇEL, AHMET SERT, YUSUF ÇAĞATAY**
   - ipucu: _DURUM.json neden alani: 'CAST_CAP_DUSEN: cap-ustu okunan 103 oyuncu dustu'; final oyuncu listesi tam 10 kisi (qc_block.py:492 MITAS_CAST_CAP varsayilan=10); credit_qc_block.py:837-864 kodu bu ismi ra
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **ŞEVKET ALTUĞ, EROL KESKİN**
   - ipucu: Ham OCR (master_dilim/dilim_oneocr.txt) bu ikili adi tasiyor, ocr-21500055/ocr_ham.txt icinde YOK (o dosyada dilim atlanmis); final CAST'te de yok -> cap=10 dolulugu nedeniyle elendi.
- **CAST** → A_ELENDI / `cast_cap`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **MURAT TOK, NİYAZİ ER, CEMAL GONCA**
   - ipucu: Ham OCR'da acikca var, frame'de okunur; final 10-kisilik CAST listesine cap doldugu icin girmedi (raw_cap_dropped listesinde 'Murat Tok', 'Niyazi... Cemal' bigram parcalari mevcut).
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - isim: **SET YÖNETİMİ / SONAY KANAT / KADIR YILMAZ / CENGİZ ÖKTEN / İ**
   - ipucu: Bu kisiler 'set yonetimi' basligi altinda -> teknik/yardimci ekip (asistan yonetmen/set amiri turu), gercek 'oyuncu/cast' kategorisi degil; final CAST listesinde olmamasi dogru kabul edilebilir (D_JEN
- **KIMLIK** → A_ELENDI / `lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **ZEKİ ALASYA, METİN AKPINAR (ilk 2 oyuncu-yildiz)**
   - ipucu: KIMLIK sorusu icin: cast okunurlugu MUKEMMEL (A/B degil, gercekten okunuyor); ancak _DURUM.json neden alaninda raw_cap_dropped listesinde 'Nasip Hasip','Nasip Zeki','Alasya Zeki','Alasya Metin' gibi b
- **CAST** → E_VERI_YOK  — _VERI YOK_
   - ipucu: Qwen-QC sayisal skor (12) ile final teslim listesi (10) arasindaki fark net kanitla (frame+OCR) A_ELENDI olarak yukarida ayri ayri gosterildi (Kazancel/Sert/Cagatay, Altug/Keskin, Tok/Er/Gonca gibi > 

## 2010-9280 — MİRAS
- **YONETMEN** → A_ELENDI / `garble_gate`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Aydın Sayman (drama yönetmeni)**
   - ipucu: Final kunye.txt/ocr_ham.txt'de 'Yönetmen' hic gecmiyor (sadece 'drama yönetmeni', 'aksiyon yönetmeni', 'yardımcı yönetmen' alt-birim rolleri var); teknik.txt'de 'Yönetmen: —' olarak bos birakilmis. ro

## 2011-9170 — ÇALIŞAN HAYATLAR
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: _DURUM.json route.agir='yonetmen garble (okunamadi)' diyor ve KONTROL'e dusurmus, ancak hem tum OCR kaynaklari (kunye.txt/ocr_ham.txt x2/dilim_oneocr.txt/ocr_raw_all.txt) hem de tum master PNG+jenerik

## 2011-9175 — SHAOLIN
- **RENDER** → A_ELENDI / `lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Benny Chan / 陳木勝**
   - ipucu: Final PDF'te YONETMEN='BENNY CHAN' dogru Latin olarak basilmis (kunye_onizleme.png); route.agir'i tetikleyen CJK sizintisi bu alanda degil, pdf/afis.jpg gorselinde (少林木人巷 vb.) - kunye metin alanlari (
- **RENDER** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Afis-eslestirme hatasi ayri bir sorun; RENDER alaninin CJK-sizma gerekcesi bu yanlis afisten kaynaklaniyor, kunye metin alanlarindan degil.
- **RENDER** → E_VERI_YOK  — _VERI YOK_
   - ipucu: Final render metin alanlarinda ek bir latin-disi/render defekti gozlemlenmedi; route karari afis kaynakli oldugu icin bu alt-bulgu icin ayrica veri yok.

## 2011-9209 — EL GUSTO
- **YONETMEN** → A_ELENDI / `identity_unlocked`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **SAFINEZ BOUSBIA**
   - ipucu: _DURUM.json 'yonetmen garble (okunamadi)' diyor ama asil neden OCR job (ocr-9aef57e9) bucket=HATA/0 satir donmus; ayri bir gec-OCR pass (master_dilim/dilim_oneocr.txt) adi dogru yakalamis fakat credit
- **KIMLIK** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **El Gusto (2011), imdb tt1946205**
   - ipucu: Kimlik kurulamama nedeni gercek veri eksikligi degil; OCR bucket=HATA oldugu icin cast/yonetmen KB'ye hic girdi olarak gitmedi, boylece cast_ortusme hesaplanamadan 0 kaldi ve 'kimlik celiskisi' etiket
- **CAST** → A_ELENDI / `guard`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Robert Castel, Maurice El Medioni, Mustapha Tahmi, Mohamed E**
   - ipucu: Ana OCR job'i (ocr-9aef57e9) 0 satir/HATA dondugu ve VL fallback da bos ('vl':'kostu' ama sonuc bos) kaldigi icin credit_text asamasi cast'i hic goremedi; final cast=['-'] oldu. Gec-OCR (dilim_oneocr.
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: pdf/kunye_teslim.md'de ozet alani placeholder: '(OZET AYRI BIR ADIMDA URETILECEKTIR.)' - hic uretilmemis; ASR gercekten failed oldugundan uretilecek transkript kaynak metni de yok.

## 2011-9224 — KANDAHAR
- **KIMLIK** → A_ELENDI / `identity_unlocked`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Mohsen Makhmalbaf + 8 oyuncu (Niloufar Padhira, Hassan Tanta**
   - ipucu: Onemli duzeltme: bu alan FIILEN ELENMEMIS. _log.jsonl credit_validate yonetmeni 'DOGRULANAMADI' (KB zayif-teyit/tek-aday) isaretlemis ve KONTROL rotasina dusurmus, ama final teslim metninde (2011-9224
- **RENDER** → A_ELENDI / `identity_unlocked`  — _FIXLENEBILIR (framede var, elendi)_
   - ipucu: RENDER bayragi dogru tespit: kaynak Latin-disi alfabede oldugu icin qc_block 'romanizasyon insan teyidi gerek' ile KONTROL'e dusurulmus. Final render (txt/pdf) kontrol edildi: Latin-disi karakter YOK,

## 2015-0134 — ADI YUNUS
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: ASR transkripti sadece jenerik kapanis cumlesi (33 karakter, 1 segment); ozet uretilecek konusma/olay verisi yok, sistem bunu dogru raporlamis (placeholder degil, aciklayici metin); _DURUM.json qwen_q

## 2015-0138 — YA NASİP YA KISMET
- **YONETMEN** → A_ELENDI / `KB_veto / deferans`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **GÖKMEN TOSUN**
   - ipucu: Yonetmen adi frame+OCR+XML(xml_roles.yonetmen=['GÖKMEN TOSUN'])'de UCU UCUNA dogrulanmis halde mevcutken, credit_validate asamasinda IMDb'den yanlis kisi (Muharrem Muhsin Aydin - aslinda YAPIMCI) 'GUC

## 2016-2213 — NİNJA KAPLUMBAĞALAR
- **YONETMEN** → A_ELENDI / `deferans`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **DAVE GREEN**
   - ipucu: _log.jsonl credit_validate: sistem yonetmen.value='KEVIN EASTMAN' (yanlış aday) seçmiş, DAVE GREEN'i (XML kaynağında zaten doğru) Wiki='Jonathan Liebesman' çelişkisiyle CELISKI/BAYRAK'a düşürmüş; fina
- **KIMLIK** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **MEGAN FOX / WILL ARNETT / LAURA LINNEY / STEPHEN AMELL / NOE**
   - ipucu: route.agir 'kimlik kurulamadı (cast-örtüşmesi 0) / yanlış-film şüphesi' diyor ama cast hem ham OCR'da hem gerçek framede tam ve okunur; _log.jsonl credit_validate.cast.value de doğru isimlerle dolu. S

## 2018-9036 — KRAL LEAR
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Hem OCR hem gorsel ayni: sadece teknik lab-karti var, DIRECTED BY/YONETMEN ibaresi hicbir karede yok; _DURUM zaten 'garble/okunamadi' diyor ama aslinda alan jenerikte mevcut degil.
- **KIMLIK** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - isim: **KING LEAR (BBC/tvi 'Chestermead' teknik kunye baslığı)**
   - ipucu: vl_yon_aday/vl_cast_aday=null, otorite_audit.ocr_dropped=[] -> kimlik verisi hicbir asamada üretilmemis; cast okunabilirlik sorunu degil, gercekten yok (D), KB cross-check celiskisi bu yuzden.
- **CAST** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Kanit: cast okunamadi degil, gercekten jenerikte/ekranda mevcut degil (D); vl_cast_aday=null bunu dogruluyor.
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: asr/asr-6d72f8dc/run/ altinda gercek transcript*.txt veya chlang.json yok, sadece 93 byte'lik subtitle.json ve ham _asr_16k.wav var; _DURUM.json asr_status=failed, transcript_chars=null -> özet üretil

## 2019-1105 — ÇIKIŞ
- **YONETMEN** → A_ELENDI / `deferans`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **이상근 (Lee Sang-geun)**
   - ipucu: Isim hem framede hem ham OCR'da dogru Korece olarak yakalanmis ancak Latin-disi alfabe oldugu icin final kunyede 'Yonetmen: —' birakilmis; _DURUM.json neden: 'yonetmen dogrulama: okunamadi (yeniden-ok
- **CAST** → A_ELENDI / `garble_gate`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **정지우, 신다은, 채수빈 (bozuk OCR ile karisik karakter-rolu + oyuncu **
   - ipucu: OCR alfabesi Korece + dusuk cozunurluk nedeniyle isim/rol ayristirmasi guvenilmez cikmis; final kunyede Oyuncular: '—', qwen_qc.oyuncu_sayisi=0 -- garble_gate/cast_cap tarafindan elenmis, D_JENERIKTE_
- **RENDER** → A_ELENDI / `nonfilm_marker`  — _FIXLENEBILIR (framede var, elendi)_
   - ipucu: RENDER bayragi kunye render/onizlemesinde afis gorseli icindeki Korece metinden kaynaklaniyor (dogru tespit, KONTROL'e dogru yonlendirilmis); metin alanlarina sizma yok, sistem bunu isaretleyip insan 

## 2025-1032 — GÖKDAĞ
- **YONETMEN** → A_ELENDI / `lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **В.МИНГАЛЁВ (translit: V. Mingalyov)**
   - ipucu: debug_trace/trace_summary.md: credit_text.candidate_read asamasinda dogrudan 'yonetmen': [] cikarilmis (Kiril alfabesi anchor/lexicon tarafindan hic yakalanmamis); VL fallback (gemma) da ayni bos sonu
- **KIMLIK** → A_ELENDI / `KB_veto`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Cast 8 isim (Yosıf/Farit BİKÇƏNTƏYEV, Renat TAJETDİNOV, Ezğä**
   - ipucu: kb.external_lookup verdict=KAYNAK_YOK, cast_ortusme=null; qc2_web 'capa bulunamadi (KB+TMDB)' -> kimlik_dogru=False; XML-PDF cast kesisimi 0 (yanlis-film supheci) -> KONTROL'e dustu; cast okunmustu (A
- **RENDER** → A_ELENDI / `guard`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Kiril alfabeli Tatarca jenerik (orn. 'Татарстан мәдәният мин**
   - ipucu: Kaynak filmin orijinal jenerigi tamamen Kiril/Tatarca; render/OCR asamasi bunu dogru okumus ama sistem guard'i Latin-disi alfabe sizintisi olarak isaretleyip romanizasyon icin insan teyidi istemis (tr

## 2025-1240 — FERDİNAND
- **KIMLIK** → A_ELENDI / `lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **Andreas A. Esparza; Laura Bayonas; Jordi Caballero; Anna Clo**
   - ipucu: Final kunyede (kunye_teslim.md, ocr-0970553b/ocr_ham.txt) sadece 7 isim kaldi (2. ve 3. sutun karisik/eksik okunmus); pipeline ocr_source=ocr_ham.txt'yi esas aldi ve daha zengin master_dilim/dilim_one
- **KIMLIK** → A_ELENDI / `identity_unlocked`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **CARLOS SALDANHA (Additional Voices listesinde de gecen, ama **
   - ipucu: trace_summary.md: credit_validate KB/IMDb/XML uzerinden CARLOS SALDANHA'yi yonetmen olarak KESIN dogruladi ve cast listesinden yonetmen alanina tasidi (C2-fix backfill); bu dogru davranis ama KB cross
- **KIMLIK** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - isim: **Yapimci (yapimci) alani**
   - ipucu: Bu alan icin veri gercekten jenerikte yok (yapimci karti framede mevcut degil), bu nedenle D_JENERIKTE_YOK; A_ELENDI degil cunku hicbir OCR/frame kanitinda yapimci adi gecmiyor.

## 2025-1295 — UMUTSUZ SAAT
- **YONETMEN** → D_JENERIKTE_YOK  — _YAPILAMAZ (jenerikte yok)_
   - ipucu: Sistem trace'i de aynı sonuca varmış: debug_trace/trace_summary.md satır 22/50 'credit_validate.qc_decision: yonetmen; status=OKUNAMADI, notes=[OCR boş -> doldurma yok]' ve harici IMDb/Wikidata/XML so

## GLORIA KUŞATMASI 1992-0299-1-0000-00-1 — 
- **YONETMEN** → A_ELENDI / `lexicon_anchor_misparse`  — _FIXLENEBILIR (framede var, elendi)_
   - isim: **BRIAN TRENCHARD-SMITH**
   - ipucu: kunye.txt'de de isim (satir 11) ile 'DIRECTED BY' (satir 40) mevcut ama bitisik degil; otomatik 'DIRECTED BY'->isim eslestirme bu yuzden basarisiz olup yonetmen bos/okunamadi olarak isaretlenmis; oysa
- **OZET** → OZET_TRANSKRIPT_YOK  — _YAPILAMAZ (sessiz/konusma yok)_
   - ipucu: _DURUM.json: asr_status='failed', asr_segments=null, transcript_chars=null; qwen_qc.ozet_var=false, notlar='Ozet bolumu placeholder metin iceriyor'. Gercek transkript hic uretilmemis, dolayisiyla ozet

## test — 
