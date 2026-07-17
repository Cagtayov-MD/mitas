# MITAS Künye Hata-Sentezi — 117 Film Denetimi

## 1. HATA SINIFLANDIRMASI (C/D vakaları — kayıp_asaması bazlı gruplama)

### GRUP A: `llm-rol-esleme` — ana cast/yapımcı bloğunun yarısı okunmuyor (EN BÜYÜK grup, ~28 film)
**Ortak desen:** ham-OCR/master-PNG'de isim NET var, LLM (gemma-4-31b, credit_text_read.py `read_credits_auto`) çok-isimli bloğu kısmi çıkarıyor — genelde ilk 7-8 isimden sonrasını "görmüyor". Cap (MITAS_CAST_CAP=10) SUÇLU DEĞİL çünkü çıkan sayı zaten cap altında kalıyor.
- **Filmler:** ADI CARMEN (x2), BİR KONUŞABİLSE, BATI CEPHESİNDE YENİ BİRŞEY YOK, DAĞ KADINI(yapımcı), DEFİNE GEZEGENİ, HALIFAX-CANİ RUH, HAROLD VE MAUDE, HARİKA KÖPEK 5, HAYALET PEŞİNDE, HERŞEY ÇOK GÜZEL OLACAK, HIZLI VE ÖFKELİ, KOVBOY, KANADA SALAMI, KAYA(yapımcı), MEYDAN OKUMA, MÜREKKEP YÜREK, NEHİRDE YARIŞ, TOPLU GÖSTERİLER(KONVOY), TOPLU GÖSTERİLER 1990-0409, ÖLÜMCÜL PROJE, İNTİKAM(yapımcı), YEDİ CÜCELER 1, YÜZÜKLERİN EFENDİSİ(x2), BORÇ, AŞK ŞARKIM, KABAKÇIĞIN HAYATI(D-versiyon: senarist/cast karışması)
- **Kod-katmanı tahmini:** `scripts/credit_text_read.py` — `read_credits_auto()` ensemble/LLM çıkarım fonksiyonu; ayrıca `PROMPT` şablonundaki sabit **"en fazla 8"** metni (satır ~295) — 2026-06-29 cap-fix (`[:8]`→`[:_cap]`) yalnız post-filtre hard-cut'ları düzeltti, LLM'e giden PROMPT'taki sözel "8" sınırını GÜNCELLEMEDİ. Bu tek satır muhtemelen grubun yarısını açıklıyor.

### GRUP B: `vl-kalkan` — VL doğru okuyor, kalkan (guard) reddediyor (~7 film)
**Ortak desen:** `_pipe_credit_vl.py` içindeki `_in_raw`/fuzzy-eşleşme kalkanı, VL'nin doğru bulduğu ismi ham-OCR-korpusunda tam-eşleşme bulamayınca "halüsinasyon" sayıp siliyor — isim genelde 2 satıra bölünmüş (ad/soyad ayrı satır) veya yazım-varyantı (Josaph/Joseph) farklı.
- **Filmler:** BİR BEBEK EVİ (SequenceMatcher 0.8333 < eşik 0.84), CAZCI (aynı fix'in henüz commit edilmemiş hali), BJ VE AYI, KOMİSER, KÜÇÜK SİMBA DÜNYA KUPASINDA, SÜPER FOK, NANCY'Yİ SEVMEK
- **Kod-katmanı tahmini:** `scripts/_pipe_credit_vl.py` — `_in_raw()`/`_fuzzy_line_hit()`, `MITAS_VL_RAW_FUZZY_RATIO` (default 0.84). CAZCI dosyasında A1/A1-b fix'leri zaten yazılmış ama commit edilmemiş (`git status: M scripts/_pipe_credit_vl.py`).

### GRUP C: `oneocr-okuma` / stitch-kaybı — kare doğru var, ham-metne hiç girmiyor (~12 film)
**Ortak desen:** Havuz/kare-bazlı OCR (`giris_jenerik_havuzu.py` veya frame-manifest) ismi doğru yakalıyor, ama ana kredi-OCR akışı (`_pipe_ocr.py`→`ocr_ham.txt`) o kareyi/satırı hiç görmüyor — iki alt-sistem entegre değil.
- **Filmler:** ALTIN ZİNCİR(Co-Producer), ARTAN İSTEKLER, ALTINA HÜCUM(Chaplin ismi dedup'ta düşmüş), MEKKE'YE YOLCULUK, PEPPER VE ARABASI, HARİKA KÖPEK 5(yapımcı-havuz), MISSOURI GÜZELİ(yapımcı), TEK PATİ, GÖKDAĞ(classify() tek-token kuralı), ÇIKIŞ(Korece boşluksuz-yazı aynı bug), İHTİRAS CİNAYETİ, YABANDAN GELEN ADAM(ikincil alan)
- **Kod-katmanı tahmini:** `scripts/_pipe_ocr.py` (frame-sampling/dedup) + `scripts/giris_jenerik_havuzu.py` (izole havuz, ana zincire beslenmiyor) + **`OCR-worktree/py/20260601_clean.py:61`** (`if n==1: return "frag"` — boşluksuz-yazı dillerinde/kısaltmalarda isim satırlarını sessizce çöp sayıyor; GÖKDAĞ + ÇIKIŞ'ta AYNI kod-satırı kanıtlanmış).

### GRUP D: `qc-dusurme` / cap-floor mantığı — KB doğru biliyor ama floor karşılanınca aramayı durduruyor (~8 film)
**Ortak desen:** `qc_block_floor` hedef=6-8'e ulaşılınca (`kabul=true`) sistem "yeterli" sayıp KB'nin bildiği ek ismi eklemiyor; `otorite_audit.ocr_dropped` bunu görünürlük-amaçlı loglar ama **karar zincirine hiç bağlanmıyor**.
- **Filmler:** GENERALİN KIZI, VAHŞETİN ÇAĞRISI, DERTLER BENİM OLSUN, LIBERA SEVGİLİM, SON YARIŞ, BÜYÜK YOLCULUK(hayır bu A), BEŞ KAFADAR(hayır A) — asıl net örnekler: GENERALİN KIZI(Daniel von Bargen), VAHŞETİN ÇAĞRISI(Rutger Hauer!), SON YARIŞ(11 isim eksik)
- **Kod-katmanı tahmini:** `scripts/credit_qc_block.py:174-227` (`_compute_otorite_audit`, docstring: "Karar ETKİLEMEZ") + `:837-864` (`CAST_CAP_DUSEN` yalnız `len(cast)>=cap` iken tetikleniyor — cap altında kalan eksik listeleri hiç yakalamıyor).

### GRUP E: `D-sınıfı yanlış-dolu` — rol karışması / kalkan ezme (~10 film, EN CİDDİ)
**Alt-desenler:**
1. **Guard kararının downstream'de ezilmesi:** JERICO APARTMANI(x2 — aynı hata farklı klasörde tekrarlanmış!), TILSIMLI DÜNYA — kimlik-guard doğru `yon=[]` yapıyor ama ikinci bir kod-yolu (`temiz_yon`) orijinal hatalı değeri geri yazıyor.
2. **Yapımcı-şirket/DoP-yakını kart yönetmen sanılıyor:** APOLLO 11 ("A James Manos Production"), SORGU/SOYGUN(Alan R. Trustman senarist→yapımcı), KAYA(Executive Producers→Producer karışması)
3. **Kolon-karışması (karakter↔oyuncu):** SINIR ÇİZGİSİ, KURTLAR VADİSİ FİLİSTİN, OMAGGIO A CARUSO(KB-fabrikasyon 4 isim)
4. **Rol-etiket karışması (teknik-ekip→cast/yapımcı):** LENI RIEFENSTAHL, BÜYÜK SAVAŞTA KÜÇÜK ADAM(şarkı-seslendiren→oyuncu)

**Kod-katmanı tahmini:** `scripts/tek_film_kunye.py` (rol-reconcile çakışan iki blok — JERICO/TILSIMLI kanıtı: satır ~683-719 `credit_qc_block` çıktısı `_yon_ocr_original` üzerinden guard'ı eziyor) + `scripts/credit_text_read.py` (rol-etiket sözlüğü eksikliği, örn. "DIRIGE PAR" `credit_role_lexicon.py:33-43`'te yok → ŞEYTAN RUHLU İNSANLAR).

---

## 2. FREKANS TABLOSU (aşama-bazlı kayıp dağılımı, 117 film)

| kayıp_aşaması | film sayısı | oran |
|---|---|---|
| llm-rol-esleme | ~30 | %26 |
| oneocr-okuma / stitch / havuz-kopukluğu | ~14 | %12 |
| vl-kalkan | ~8 | %7 |
| qc-dusurme / cap-floor | ~9 | %8 |
| kb-qc-block | ~4 | %3 |
| clip-secim (frame-pencere/jenerik-tespit atlıyor) | ~7 | %6 |
| tespit-edilemedi / kayıp yok (B-meşru veya A-temiz) | ~35 | %30 |
| pdf-render (md/pdf senkron kaybı, içerik doğru) | ~4 | %3 |
| havuz (giris_jenerik_havuzu ana zincire hiç bağlı değil) | ~4 | %3 |
| cap-tavanı (floor karşılanınca durma) | ~2 | %2 |

**Not:** Yüzdeler toplam >100 çünkü çok-nedenli filmler (örn. APOLLO 11: vl-kalkan+llm-rol-esleme) birden fazla satırda sayıldı.

---

## 3. DoP-SIZINTI VAKALARI — TAM LİSTE

**Sonuç: 117 filmin HİÇBİRİNDE gerçek DoP→yönetmen sızıntısı YOK** (`dop_sizinti:false` hepsinde, tek `true` işaretli VAHŞETİN ÇAĞRISI/TEK PATİ'de bile field'ın kendisi `false` çıkmış, muhtemelen kopyala-yapıştır kalıntısı).

**Ortak desen (neden sızmadı):** OCR/LLM sistemi DoP etiketini ("Director of Photography", "DIRECTEUR DE LA PHOTOGRAPHIE", "GÖRÜNTÜ YÖNETMENİ", "operatör-postancık") tutarlı biçimde ayrı ve doğru tanıyor — bu MITAS'ın en sağlam mekanizması. Riskin gerçekleştiği tek yakın-ıskalama: **BİR BEBEK EVİ** (VL doğru "Joseph Losey"i buldu, DoP değil ama kalkan-eşiği yüzünden düştü — DoP karışması değil, farklı hata). Sızıntı **YOK** demek yerine, bunun yerine ters yönde bir risk kalıbı var: **yapımcı-şirket kartları yönetmen/yapımcı alanına sızıyor** (APOLLO 11, JERICO APARTMANI'nda "Martin Pollins" muhasebe/yönetim-kurulu kartından sızmış — bu DoP değil ama aynı aile: "yakın-metin-bloğu yanlış-role atanıyor").

**Öneri:** dop_sizinti alanı bu taramada ayırt edici sinyal vermedi; asıl izlenmesi gereken "yapımcı-şirket/muhasebe/yönetim-kurulu kartı → yönetmen" sızıntısı ayrı bir kategori olarak flag'lenmeli.

---

## 4. FIX ÖNCELİK SIRASI (en çok filmi kurtaracaktan aza)

### #1 — PROMPT'taki sabit "en fazla 8" metnini kaldır (credit_text_read.py PROMPT şablonu, ~satır 295)
- **Etki:** GRUP A'nın (~28 film) büyük kısmını düzeltir — cap zaten 10'a çıkarılmış ama LLM'e talimat olarak hâlâ "8" gidiyor.
- **Dosya/katman:** `scripts/credit_text_read.py` (PROMPT string, tek satır değişikliği)
- **Regresyon riski:** DÜŞÜK. Salt metin değişikliği, mekanik cap zaten 10'da güvenlik ağı; ama LLM'in ürettiği isim sayısı artarsa gürültü/çöp-isim riski hafif artabilir → cap+QC ikinci savunma hattı zaten var.

### #2 — otorite_audit.ocr_dropped / raw_cap_dropped sinyalini KARARA bağla
- **Etki:** GRUP D (~9 film) + GRUP A'nın örtüştüğü kısım. Şu an "Karar ETKİLEMEZ" olarak dokümante edilmiş salt-gözlem alanı; `ocr_dropped` doluysa ve KB `cast_ortusme` düşükse otomatik KONTROL'e düşürülmeli.
- **Dosya/katman:** `scripts/credit_qc_block.py:174-227` (`_compute_otorite_audit`) + karar-matrisi (`:799-864` civarı `CAST_CAP_DUSEN` koşulu genişletilmeli: `len(cast)>=cap` şartı kaldırılıp `ocr_dropped` boş-değilse de tetiklenmeli).
- **Regresyon riski:** ORTA. Bu değişiklik "Hazır" olan filmleri "KONTROL"e kaydırır → KONTROL kuyruğu şişer, insan iş-yükü artar. Ama sessiz-hata riski azalır. Aşamalı rollout (önce yalnız log/uyarı, sonra route-etkisi) önerilir.

### #3 — VL-korpus-doğrulama kalkanının fuzzy-eşiğini gevşet + 2-satırlı isim birleştirme
- **Etki:** GRUP B (~7 film).
- **Dosya/katman:** `scripts/_pipe_credit_vl.py` (`_in_raw`, `_fuzzy_line_hit`, `MITAS_VL_RAW_FUZZY_RATIO`). CAZCI dosyasında zaten yazılmış (A1/A1-b) ama commit edilmemiş fix var — önce onu commitleyip 16 filmlik smoke-test'e sokmak en hızlı kazanç.
- **Regresyon riski:** ORTA-YÜKSEK. Eşik düşürülürse gerçek halüsinasyonların sızma riski artar — bu tam da kalkanın var oluş nedeni. Eşik değişmeden önce "cross-line" (iki-satır birleştirilmiş) kontrolü eklenmesi daha güvenli (zaten yorum satırında planlı görünüyor).

### #4 — `giris_jenerik_havuzu.py` çıktısını ana `_pipe_ocr.py`/`ocr_ham.txt` zincirine besle
- **Etki:** GRUP C'nin yarısı (~6 film: ALTIN ZİNCİR, MISSOURI GÜZELİ, TEK PATİ, HARİKA KÖPEK 5, MEKKE'YE YOLCULUK).
- **Dosya/katman:** `scripts/giris_jenerik_havuzu.py` + `scripts/_pipe_ocr.py` (entegrasyon noktası — havuzun `credit_lines` çıktısını ana OCR corpus'una merge etmek).
- **Regresyon riski:** ORTA. İki bağımsız sistemi birleştirmek entegrasyon-bug riski taşır; MEMORY'de zaten "3. tip havuz" salt-dedup amaçlı tasarlanmış — mimariyi değiştirmek yerine "iki corpus'u VL/kalkan doğrulamasında birlikte kullan" daha düşük riskli ara-çözüm olabilir.

### #5 — `OCR-worktree/py/20260601_clean.py:61` tek-token kuralını düzelt (boşluksuz-yazı dilleri)
- **Etki:** Şimdilik 2 film kanıtlı (GÖKDAĞ, ÇIKIŞ) ama **sistemik risk** — tüm Korece/Japonca/bitişik-Kiril-kısaltma filmlerinde tekrarlanabilir; tarama önerilir.
- **Dosya/katman:** `OCR-worktree/py/20260601_clean.py` (`classify()`, `atok()`) — `has_role()` kontrolü tek-token'a da uygulanmalı, salt boşluk-sayımı yeterli değil.
- **Regresyon riski:** DÜŞÜK-ORTA. Dil-bazlı bir istisna eklemek (script-detection: Hangul/Kiril-bitişik) izole edilebilir, ama mevcut çöp-filtreleme davranışını (gerçek fragman-gürültüyü elemek) bozmama testi gerekir — MEMORY'deki 16/16 test seti benzeri bir regresyon-seti şart.

### #6 — Rol-etiket sözlüğünü genişlet (`credit_role_lexicon.py`)
- **Etki:** Düşük film sayısı ama yüksek-güven (ŞEYTAN RUHLU İNSANLAR: "DIRIGE PAR"; BÜYÜK YOLCULUK gibi diğer dil-varyantları da muhtemelen aynı listede eksik).
- **Dosya/katman:** `scripts/credit_role_lexicon.py:33-43` (DIRECTOR listesine "DIRIGE PAR"/"PRODUIT ET DIRIGE PAR" ekle; benzer taramayla İsveççe PRODUCENTER/EXEKUTIVA PRODUCENTER gibi yapımcı-etiketleri de eklenmeli — İNTİKAM filmi kanıtı).
- **Regresyon riski:** DÜŞÜK. Ek-sözlük girişi, var-olanı bozmaz.

---

## 5. BELİRSİZ VAKALAR (insan/ikinci-tur gerektirir)

1. **KIZIL HAYAT** — yönetmen sadece TRT-XML'de var, video/OCR'da hiç yok; C mi B mi tartışmalı.
2. **PROFESÖR HANNIBAL** — TMDB kimlik-kilitli ama OCR tamamen çöp; kaynak-video gerçekten jenerik içermiyor mu yoksa kesilmiş mi belirsiz.
3. **CAZCI** — yapımcı alanı "Production manager" rolünün yapımcı sayılıp sayılmayacağı şema-belirsizliği.
4. **ŞİRKET İLİŞKİLERİ / GÜLE GÜLE JÜPİTER** — `kunye_teslim.md` ile nihai `kunye.pdf` arasında içerik çelişkisi; hangisi "gerçek teslim" sayılmalı net değil (mimari/export-hijyen sorunu, çoklu filmde tekrarlanıyor: DAĞ KADINI, MEKKE'YE YOLCULUK, RÜZGAR BİZİ SÜRÜKLEYECEK, YÜZÜKLERİN EFENDİSİ 2001, SHERLOCK HOLMES'İN DOĞUŞU — **bu md/pdf senkron-kaybı kendi başına ayrı bir sistemik konu, en az 6 filmde görüldü**).
5. **YARIŞMA DÜNYASI** — "Joan Campabadal" oyuncu mu karakter mi kolon-şüphesi, ek çerçeve gerekli.
6. **APOLLO 11 (yapımcı)** — "James Manos" yapımcı alanına da sızmış, D mi kısmen-savunulabilir mi sınırda.
7. **GÜNDÖNÜMÜ GÜNEŞ** — pipeline hiç çalışmamış (`_DURUM.json` yok), sınıflandırma dışı; yeniden-koşu gerekiyor.
8. **TOPLU GÖSTERİLER 1991-0356** — "SIYING XUE"/"HAMZA ARORE" muhtemelen tam fabrikasyon (Latin-dışı OCR gürültüsünden LLM uydurması), ama kesin teyit için kaynak video gerekli.

**Ayrı sistemik gözlem (fix-listesine girmeyen ama önemli):** en az 6 filmde `pdf/kunye_teslim.md` (ara-ürün) ile nihai `pdf/kunye.pdf` (v4-final) arasında **içerik çelişkisi** var — md dosyası v4-render'dan önceki bayat hali taşıyor ve hiç senkronize edilmiyor. Bu görevin "kayıp" sınıflandırmasının dışında ama raporlama-hijyeni açısından ayrı bir fix-adayı: `mitas_pipeline.py`'de v4-final sonrası `kunye_teslim.md`'nin de yeniden yazılması ya da export sürecinde yalnız `kunye.pdf`'in nihai kaynak sayılması net kural haline getirilmeli.