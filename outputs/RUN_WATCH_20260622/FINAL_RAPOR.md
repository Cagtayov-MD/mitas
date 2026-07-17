# MITAS 42-FİLM DENETİMİ — FİNAL RAPOR (düzeltme + yeniden-koşu için)

*Tarafsız Opus denetçi sentezi · 2026-06-22 · SALT-OKUNUR (kod/Database değiştirilmedi, hiçbir şey çalıştırılmadı, commit yok). İddialar artefakt + kod-satırı çift-teyitiyle bağımsızca doğrulandı.*

---

## 1) YÖNETİCİ ÖZETİ

**Genel sağlık hükmü (tarafsız):** Denetim **genelde sağlam ve dürüst** — iddiaların büyük çoğunluğu hem kodda hem canlı artefaktta birebir doğrulandı (CEMİLE Kiril silme, BEKARLIK uydurma yapımcı `tek_film_kunye.py:563-564`, S5 name_close ezme `credit_qc_block.py:627-631`, _fold Latin-strip `credit_text_read.py:42`, HABABAM, BÜLBÜL dublaj kaybı — hepsini kendim okudum). Boru hattının **güvenlik mimarisi gerçekten sağlam**: hata yapmaktansa boş/KONTROL'e düşüyor (fail-safe doğru). Asıl zaaf **doğruluk değil, recall/kapsam**.

**ANCAK denetimin iki sistematik abartısı var — ben düzelttim:**

1. **🔴 RAPOR.md TİER-OKUMA HATASI (yeni, denetimin kaçırdığı en büyük öz-kusur):** Aynı TRT'nin `" 2"` yinelenen klasörleri **önceki koşudan bayat ONAYLI/Hazır** taşıyor; bu **canlı 42-film koşusunun** kararı DEĞİL. Canlı koşu (sonek-siz `-1` klasörü) aynı filmleri **AutoFix**'e yolladı. Doğruladığım eşleştirme:

   | Film | RAPOR'un dediği | `" 2"` (bayat) | **Canlı koşu (`-1`)** |
   |---|---|---|---|
   | KEDİ GÖZÜ | Hazır→ONAYLI (YANLIŞ) | Hazır/ONAYLI | **AutoFix/AUTOFIX** |
   | BÜLBÜL | Hazır→ONAYLI | Hazır/ONAYLI | **AutoFix/AUTOFIX** |
   | MAYMUN AKLI | Hazır→ONAYLI | Hazır/ONAYLI | **AutoFix/AUTOFIX** |
   | DELİ KAN | Hazır→ONAYLI | Hazır/ONAYLI | **AutoFix/AUTOFIX** |

   **Sonuç:** "7/8 ONAYLI kusurlu" istatistiği ŞİŞİK. Bu filmlerin kusurları GERÇEK (lost-actor, garble, ikame, dublaj kaybı hepsi doğrulandı) ama **canlı QC onları AutoFix'e bayrakladı** — yani "kusurlu→sessiz ONAYLI false-negative" anlatısı bu vakalarda DOĞRU DEĞİL; sistem onları flagledi. AutoFix de insan-atlamalı bir tier olduğu için risk sürüyor, ama bu "ONAYLI temizlik garantisi değil" mesajından farklı: **gerçek kör nokta AutoFix kovası**, ONAYLI değil.

2. **🟡 H2 (ÇILDIRIŞ yanlış-film kadrosu PDF'e yazıldı) ARTEFAKTLA ÇELİŞİYOR:** KOD_DENETIMI "HINDAWI/Poppe PDF'e yazıldı" dedi; ben tüm ÇILDIRIŞ teslim ağacını taradım — **HINDAWI/POPPE/Mathijs HİÇBİR teslim dosyasında YOK**, yalnız "JACKET" var (o da ham OCR'da, doğru). Film **Kontrol**'e gitti. Fail-safe çalıştı; mekanizma kodda mevcut ama **gösterilen örnekte zarar gerçekleşMEDİ.** H2 "olası mekanizma", "gerçekleşmiş felaket" değil.

**En kritik 3 GERÇEK şey (düzeltmelerden sonra hayatta kalan):**
1. **HABABAM (CRITICAL):** Türk klasiği — açılış yıldız-kartları OCR'da hiç okunmadı (başroller yok) + Türkçe-film `ku` sanıldı→ASR atlandı→yanlış-film TMDB özeti cascade. TR arşivinde yaygın olabilir. (Canlı koşu Hazır/ONAYLI — bu gerçekten ONAYLI, doğrulandı.)
2. **OCR-otorite ihlali ailesi (CRITICAL):** BEKARLIK uydurma yapımcı (kimlik-kapısız KB-fill, `tek_film_kunye.py:563-564` teyitli) + KEDİ GÖZÜ Parker(OCR 6×)çıkar/Sarrazin(OCR 0×)ekle ikame + S5 name_close ezme (LEFEBVRE→LEFEVRE). Kurucu kanun ihlali.
3. **TR-dublaj seslendiren kaybı (CRITICAL-TRT):** BÜLBÜL 19 Türkçe ses oyuncusu 8-cap'le düştü. TRT arşivi dublaj-ağırlıklı → en alakalı metadata sistematik kayıp.

---

## 2) HATA SINIFLARI — ÖNCELİK SIRALI

| # | Sınıf | Doğrulanmış şiddet | Kök-neden (dosya:satır) | Önerilen fix (additive, flag-kapılı) | Regresyon | Hangi filmde doğrulanır |
|---|---|---|---|---|---|---|
| 1 | **OCR-otorite ihlali**: kimlik-kapısız KB-yapımcı fill + KB/VL OCR-dışı isim ekleme/ikame | **CRITICAL** | `tek_film_kunye.py:563-564` (gateless `if not yap and cc.get("yapimci")`); VL `_pipe_credit_vl.py:76-83` `_in_raw` blob-adjacency gediği; floor-fill `credit_qc_block.py:639-643` | `MITAS_KB_PRODUCER_GATE` kimlik-kapısı + `MITAS_VL_ADJACENCY_SHIELD` satır-bazlı `_in_raw_adjacent` + floor öncesi OCR-okunanı geri-al | DÜŞÜK | BEKARLIK 1958-0046, MANASLU 9318, KEDİ GÖZÜ 1969-0057 |
| 2 | **LOST-ACTOR**: başrol/yıldız kadrodan düşüyor (tek-blok seçimi + 8-cap + frag-kapısı + floor OCR-ezme) | **CRITICAL** | tek-blok: `credit_text_read.py:848-875` (ilk-blok dolunca return); 8-cap: `credit_qc_block.py:369,572`; frag: `OCR-worktree/.../clean.py:61`; floor: `credit_qc_block.py:639-643` | `MITAS_CAST_MULTIBLOCK` (açılış+kapanış union) + `MITAS_CAST_OCR_RECLAIM` + `MITAS_CAST_NO_HARD_CAP` (cap=max(8,OCR-okunan)) | DÜŞÜK | FEDORA 1978-0238, KEDİ GÖZÜ, DÖRT CENAZE 9137, POTA 2020-0011 |
| 3 | **TR-dublaj seslendiren kaybı** (8-cap orijinal-kadroyu tutup TR-ses kadrosunu atıyor) | **CRITICAL (TRT)** | `credit_qc_block.py:572` 8-cap + ayrı-alan yok | Seslendirenler bloğunu ayrı-alan koru, 8-cap orijinal-kadroyla yarıştırma | DÜŞÜK | BÜLBÜL 1962-0033 |
| 4 | **v4/S5 name_close OCR-form ezme + orijinal-ad fabrikasyonu** | **HIGH** (karışık-harm: bazen accuracy↑) | `credit_qc_block.py:627-631` (`duz.append(es if es else nm)` fuzzy-snap); orijinal-ad `tek_film_kunye.py:649-650` | `MITAS_OCR_FORM_KEEP`: name_match(sıkı)→snap kalsın; name_close/window(fuzzy)→OCR-formu KORU, es'i yalnız dedup işareti yap | DÜŞÜK | HAYATIN DENGESİ 9162 (LEFEBVRE), KULÜP EVİ 9065 (DELANY), ÇELİK MASKE 1974-0173 (ROBO MAN) |
| 5 | **NON-CAST→CAST sızma** (crew/thanks/asistan/müzisyen/hayvan/film-içi-film) | **HIGH** | `_CREW_CONTEXT_KW` çok-dilli eksik `credit_text_read.py:44-57`; QC-savunma ölü (`tek_film_kunye.py:614-618` `raw_context_lines` geçmiyor); yapımcı kapısı yok | _CREW_CONTEXT_KW çok-dilli genişlet (redaktion/scénario/dialogue coach/trained by/special thanks) + qc_block çağrısına `raw_context_lines` bağla + `filter_yap_by_raw_context` | DÜŞÜK | SESSİZ ÇOCUK 2151, OLAY YERİ 9084, ŞİRKET ADAMLARI 9157, DELİ KAN, KÖPRÜNÜN ÖTESİ 1957-0034 |
| 6 | **H1 Latin-dışı sıfırlama + LID Türkçe→Kürtçe** | **HIGH** (fail-safe→KONTROL, veri-zararı yok) | `_fold` `credit_text_read.py:42` `[^a-z0-9 ]+`; translit ölü `credit_qc_block.py:415-437` (çağrı `raw_context_lines=None`); LID `_channel_lang.py:180-197`+`mitas_pipeline.py:1728` | qc_block'a `raw_context_lines` ver→Latin-dışı ek-doldurma (translit-FAILED→KONTROL) + `MITAS_LID_TR_VETO` (borderline-conf + tr-oyu varsa ku→tr) | ORTA (LID over-veto riski) | CEMİLE 1998-0498, NAMUS DÜŞMANI 9262, HABABAM 1976-0147 |
| 7 | **garble teslime girdi + garble-gate Latin kör noktası** | **HIGH** | stitch cross-cluster seçimi `OCR-worktree/.../stitch.py:23-34,78-82`; `_looks_garble` char/frekans-kör `credit_text_read.py:430-450` | `MITAS_STITCH_XCLUSTER_VOTE` (frekans-çoğunluk temsilci) + `MITAS_QC_FREQ_GARBLE` (düşük-frekans varyant→KONTROL); naif char-garble KULLANMA (yanlış-pozitif) | DÜŞÜK | AYI YOGİ 1964-0032 |
| 8 | **POSTER yanlış-film** (yanlış-installment + aynı-başlık yanlış-film) | **MEDIUM-HIGH** (görsel-teyit kısmen eksik) | `poster_fetch.py:340-369` id-fallback `vsig` versiyon-imzasını atlıyor; `credit_identity.py:104` shared-cast ambiguous gevşek | `MITAS_POSTER_VER_GATE`: id-fallback'a `_version_ok(vsig, resolved_title)` kapısı (alt-başlık/seq pozitifse) | DÜŞÜK | KARAYİP2 9148, ÇOCUKLARIN SAVAŞI 1980-0220 |
| 9 | **QC false-positive KIMLIK→gereksiz KONTROL** | **MEDIUM** (müşteri-zararsız) | `mitas_pipeline.py:1923-1932` XML-cast strict==0; `credit_qc_block.py:469` locked yön-doğrulandı'yı saymıyor | `MITAS_XMLCAST_GATE_RELAX`: fuzzy≥1 VEYA yön-TEYİT varsa bayrağı kaldır | DÜŞÜK | BEKLENEN BOMBA 1959-0005 (düzelmeli), KÖŞENİN KRALI 9132/ANGOLA 1976-0184 (hâlâ KONTROL kalmalı) |
| 10 | **Kozmetik/metadata** (footage-bloat master, karar↔route bayat, sidecar bayat, `" 2"` klasör, tür-gürültü) | **LOW** (sidecar+tür alt-kalemi MEDIUM) | master_png=null (zararsız); sidecar v4-sonrası bayat; tür-sınıflandırıcı gürültü | sidecar v4-sonrası yeniden-serileştir; tür iki-sinyal doğrulama; `" 2"` klasör çakışması temizliği | DÜŞÜK | YAĞMUR 9265 (.txt=Cooper/PDF=Wilson), BEYAZ BALİNA 9031 (sidecar garble), MARY POPPINS 1964-0031 (tür) |

---

## 3) BAĞIMSIZ DENETÇİ DÜZELTMELERİ (şeffaflık — denetimin abartı/çürütülen bulguları)

1. **`" 2"` tier-okuma hatası (EN ÖNEMLİ, denetimin kaçırdığı öz-kusur).** RAPOR.md birçok filmi "Hazır→ONAYLI" diye işaretledi ama bunlar bayat duplikat klasörler; **canlı koşu KEDİ GÖZÜ/BÜLBÜL/MAYMUN AKLI/DELİ KAN'ı AutoFix'e** yolladı (kendim doğruladım). "7/8 ONAYLI kusurlu" istatistiği bu yüzden şişik; "kusurlu→sessiz ONAYLI false-negative" anlatısı bu vakalarda yanlış — QC onları flagledi. (Not: HABABAM gerçekten Hazır/ONAYLI; o vaka geçerli.)

2. **H2 canlı zarar çürütüldü.** ÇILDIRIŞ teslim dosyalarında HINDAWI/Poppe **yok**; film Kontrol'e gitti, fail-safe çalıştı. "Yanlış-film kadrosu PDF'e yazıldı" mekanizma-olasılığı; gerçekleşmiş zarar değil.

3. **v4-ezme tek-yönlü çerçevelendi.** S5 name_close ezme bazı vakalarda gerçek-dünya doğru yazımını üretiyor (LEFEBVRE→Lefevre IMDb-doğru). "EN GÜÇLÜ KALIP/felaket" abartılı; harm karışık → şiddet HIGH değil MEDIUM-HIGH. Fix'in kör-koruma yapması recall'ı düşürmemeli (sıkı name_match snap'i korunmalı).

4. **BEKARLIK satır-atfı kısmen kaba (ama özü doğru).** `563-564` gateless DOĞRU; fakat asıl gedik yanlış-film imdb eşleşmesi + `_GLOBAL_PERSON_GATE`'in producer'ı kendi film_pool'una doğrulaması (self-validation). Tek-satır fix izlenimi yanıltıcı.

5. **Poster iddiaları görsel-teyitsiz.** KARAYİP2/ÇOCUKLARIN SAVAŞI afişleri PDF-gömülü; denetim PDF-görselini çıkarıp karşılaştırmamış → "BELİRSİZ" olmalı (ben de doğrulayamadım; mekanizma `poster_fetch.py:340-369` makul).

6. **Örneklem yanlılığı not edilmemiş.** 42 filmin çoğu eski/yabancı/garble-ağır "COZUMLEME" kaynaklı; modern-temiz Türkçe oranı düşük. ONAYLI-defekt oranı bu sapmış örneklemden modern üretime genellenemez.

7. **KOD_DENETIMI iç-çelişkisi.** Ön-kod denetimi "hiçbir eksende sessiz yanlış-ONAYLI yok / üretime güvenli" dedi; canlı denetim çok sayıda DOĞRULUK ihlali (ezme/ikame/sızma/uydurma) buldu. İki katman çelişiyor → "güvenli" hükmü canlı bulgularla nitelenmeli. (Düzeltmeyle: ihlaller GERÇEK ama çoğu AutoFix/KONTROL'e gitti, ONAYLI'ya değil → her iki katman da kısmen haklı.)

---

## 4) YENİDEN-KOŞU PLANI

**Kapsam:** Aynı 42 oturum-filmi (`outputs/RUN_WATCH_20260622/seen.txt`, 42 satır doğrulandı). Her fix flag-kapılı (default OFF) → baseline (tüm flag OFF) ile fix-açık koşu **aynı setde A/B**.

**Ön-koşul:** `" 2"` duplikat klasör çakışmasını çöz (yoksa yeniden-koşu yine yeni `" 3"` üretir ve metrik kirlenir). Karşılaştırma **yalnız canlı `-1` klasörlerinden** yapılmalı, bayat duplikatlardan değil.

**Öncesi/sonrası metrikleri (her biri 42-film üstünde sayılır):**
| Metrik | Ölçüm yöntemi | Hedef |
|---|---|---|
| **AutoFix+ONAYLI defekt oranı** | `-1` klasörlerinde karar∈{Hazır,AutoFix} olup içerik-kusuru olan film / toplam | düşmeli |
| **lost-actor sayısı** | OCR-ham'da ≥3× okunup final cast'te olmayan başrol (ocr_raw_all vs PDF) | düşmeli (FEDORA/KEDİ GÖZÜ/DÖRT CENAZE) |
| **OCR-otorite ihlali sayısı** | final'de OCR-bitişik-okunmayan KB/VL isim (BEKARLIK/MANASLU/KEDİ GÖZÜ) | →0 |
| **garble-teslim** | final cast'te `_looks_garble`+frekans-azınlık (AYI YOGİ) | →0 |
| **yanlış-afiş** | vsig-aktif film + fallback-id başlık tutarsız (KARAYİP2) | →0 |
| **gereksiz-KONTROL (false-pos)** | sole-reason "XML-PDF kesişimi 0" + yön-TEYİT (BEKLENEN BOMBA) | düşmeli |
| **Latin-dışı kurtarma** | CEMİLE/NAMUS final cast dolu mu (translit) | >0 (veya KONTROL, asla uydurma) |

**Negatif-kontrol (regresyon-yok ispatı):** MAYMUN AKLI 1981-0270, İNTİKAM ÇOCUKLARI 1041, ZORLU ADAM 1957-0023 — bu 3 temiz film flag-açıkken karar+cast **DEĞİŞMEMELİ**.

**Re-OCR gerekmez:** Tüm `ocr_raw_all.txt` mevcut → fix'ler salt yeniden-render/yeniden-stitch ile A/B'lenebilir (HABABAM/CEMİLE OCR-recall hariç — onlar frame-seçimi gerektirir).

---

## 5) İYİ ÇALIŞAN (regresyon yaratmamak için KORUNMASI gerekenler)

- **Fail-safe mimarisi:** Kimlik kilitlenemeyince KB DOLDURMUYOR → uydurma yapmadan KONTROL (HAYALPEREST: poster isimleri sızmadı). ÇILDIRIŞ yanlış-film cast'i teslime YAZILMADI. **En değerli özellik — fix'ler bunu bozmamalı.**
- **OCR-otorite kalkanı** çoğu sızıntıyı kesiyor (garble/rol-etiketi/disclaimer PDF'e girmiyor; `tr_upper` İ-bozması düzelmiş, GRUBER korundu).
- **Yönetmen çelişki-çapası (S4, `credit_qc_block.py:604-617`):** OCR-okunan yönetmeni KB ile EZMEZ, çelişki→KONTROL. (Cast tarafında bu koruma eksik — fix budur, ama yön tarafı model alınmalı.)
- **v4 recovery (ZORLU ADAM):** RUDY BOND+2 yapımcı OCR'dan geri kazanıldı — mantık VAR ama tutarsız; tutarlı kılınmalı, silinmemeli.
- **Özel-tür yönlendirme** (MANASLU belgesel doğru), **memory'deki 3 tarihsel kritik** (`_v4j`/`_qc1_failed`/K2-propagation) koda göre KAPALI — yeniden açılmamalı.
- **AutoFix tier'in flagleme yeteneği:** Canlı koşu KEDİ GÖZÜ/BÜLBÜL/MAYMUN AKLI'yı AutoFix'e ayırdı — QC'nin bu ayırt-etme gücü korunmalı; asıl iş AutoFix kovasının içeriğini iyileştirmek.

---

## 6) NET KARAR — önce yapılacak 3-4 fix (en yüksek getiri / en düşük risk)

Hepsi **additive + flag-kapılı (default OFF) → sıfır regresyon yüzeyi**; A/B sonrası açılır. Sıra:

1. **FIX-1 — Kimlik-kapısız KB-yapımcı fill'i kapat** (`tek_film_kunye.py:563-564`, `MITAS_KB_PRODUCER_GATE`). En kesin, en küçük, en yüksek-güven (BEKARLIK uydurma yapımcı). Kimlik şüphesinde yap=[]→KONTROL (yanlış>boş). **Tek dosya, ~2 satır.**

2. **FIX-2 — LOST-ACTOR: floor öncesi OCR-okunanı geri-al + cap'i OCR için esnet** (`credit_qc_block.py:639-643,572`, `MITAS_CAST_OCR_RECLAIM`+`MITAS_CAST_NO_HARD_CAP`). En pervasif izleyici-görünür kayıp; KEDİ GÖZÜ Parker'ı kurtarır, KB-sismeyi FILL_TARGET'ta tutar. Multiblock (FEDORA) ikinci dalga.

3. **FIX-3 — NON-CAST→CAST savunmasını canlandır** (`tek_film_kunye.py:614-618`'e `raw_context_lines` bağla + `_CREW_CONTEXT_KW` çok-dilli genişlet). İki değişiklik ölü-savunmayı açar; SESSİZ ÇOCUK/ŞİRKET ADAMLARI sızıntısını keser. Yalnız DÜŞÜRÜR, asla eklemez → garble→KONTROL invariant'ı korunur.

4. **FIX-4 — LID Türkçe→Kürtçe vetosu** (`_channel_lang.py select_summary`, `MITAS_LID_TR_VETO`). HABABAM cascade'inin yukarı-akış kökü; TR arşivinde potansiyel yaygın. **ORTA-riskli (over-veto)** → borderline-conf + tr-oyu koşuluyla daralt; net-Kürtçe filmlere DOKUNMA.

**Ertelenecek:** v4-ezme fix'i (FIX-4 sınıf-4) accuracy'i bazen artırdığı için A/B-bağımlı; poster (görsel-teyit gerek); QC false-positive gevşetme (muhafazakâr-güvenli taraf, en son); Latin-dışı translit (ORTA-risk, raw_context_lines köprüsü FIX-3 ile birlikte gelir).

**TRT-özel uyarı:** FIX-3 (dublaj-koruma boyutu) ve seslendirenler-ayrı-alan (sınıf-3) **TRT teslim-değeri açısından kritik** — dublaj-ağırlıklı arşivde en alakalı kadro bu. Fix sıralamasında düşürülmemeli.

---

## 6b) SESLENDİRME (TR-DUBLAJ KADROSU) — DETAYLI ÖNERİ

**Sorun:** TR-dublaj filmlerinde OCR "seslendirenler" bloğunu **tertemiz** okuyor (BÜLBÜLÜ ÖLDÜRMEK: garble_frac=0, 19 Türkçe ses oyuncusu + dublaj ekibi net okundu) ama boru hattı **tutarsız**: BÜLBÜL'de 8-cap orijinal (İngilizce) kadroyu tutup **Türkçe ses kadrosunu komple attı**; MAYMUN AKLI'da TR-dublajı dışladı (orijinal kadroyu tuttu). TRT arşivi **dublaj-ağırlıklı** olduğundan teslim için en alakalı metadata (Türkçe seslendirenler) sistematik kayboluyor.

**Önerilen çözüm (additive, regresyon-riski DÜŞÜK):**
1. **Künye şemasına AYRI `SESLENDİRENLER` alanı ekle.** Orijinal kadro `OYUNCULAR`'da kalır; Türkçe ses kadrosu kendi alanında listelenir. **8-cap yalnız `OYUNCULAR`'a uygulanır → seslendirenler slot için yarışmaz, düşmez.**
2. **Tespit OCR-etiketinden:** `seslendiren(ler)` / `seslendirme` / `Türkçe seslendirme` başlığı altındaki isimleri ayrı-alana yönlendir. OCR zaten okuyor — sorun çıkarım/yönlendirme; `credit_text_read` rol-bağlamı ile bu blok ayrıştırılabilir (crew-keyword genişletmesiyle — FIX-3 ile aynı altyapı).
3. **Dublaj ekibi** (seslendirme yönetmeni, ses kayıt, çeviri/diyalog) → `YAPIM EKİBİ` altında "Dublaj" alt-bölümü (cast'e KARIŞTIRMA — krş. DELİ KAN müzisyen-sızması, OLAY YERİ Redaktion-sızması ile aynı non-cast→cast ailesi).
4. **Politika kararı (Çağatay):** TRT dublaj-arşivi için `SESLENDİRENLER`'in **zorunlu alan** olması önerilir; ama bunun teslim-şartı olup olmadığı içerik-politikası kararıdır.
5. **Doğrulama:** BÜLBÜLÜ ÖLDÜRMEK (19 isim) + MAYMUN AKLI (TR-dublaj var) yeniden-koşuda `SESLENDİRENLER` alanı dolu mu; orijinal `OYUNCULAR` değişmemiş mi (negatif-kontrol).
6. **OCR-otorite invariant korunur:** bu alan yalnız OCR-okunan seslendirme bloğundan doldurulur; KB-uydurma YOK, okunmayan eklenmez.

---
*İlgili dosyalar (mutlak): `E:/MITAS/outputs/RUN_WATCH_20260622/RAPOR.md`, `.../KOD_DENETIMI.md`, `.../seen.txt`. Anahtar kök-neden satırları: `E:/MITAS/scripts/tek_film_kunye.py:563-564,614-618`, `E:/MITAS/scripts/credit_qc_block.py:572,627-631,639-643`, `E:/MITAS/scripts/credit_text_read.py:42,44-57`, `E:/MITAS/scripts/_channel_lang.py:180-197`. Düzeltme/commit Çağatay tarafından yapılacak — bu rapor salt gözlemdir.*

---

## 7) TEK TEK 42 FİLM — her filmin kendi sorunu

> Tier notu: `*` işaretli ONAYLI'lar **bayat `" 2"` duplikat klasörden** okundu; **canlı koşu o filmi AutoFix'e** yolladı (§1/§3). Şiddet: 🔴🔴=CRITICAL, 🔴=HIGH, 🟡=MEDIUM, ✅=temiz/kozmetik.

| # | Film | Karar/Tier | Filmin kendi sorunu | Şiddet |
|---|------|-----------|---------------------|--------|
| 1 | RED ROCK 9152 | Kontrol→KONTROL | Giriş master footage-bloat (17726px) + çıkış smear. **Final kadro DOĞRU** (Caan/Carradine/Gyllenhaal). karar↔route metadata çelişki. | 🟡 (master+metadata) |
| 2 | HAYATIN DENGESİ 9162 | ONAYLI | KIM BERLIN KB-form bozuk (ekranda KIMBERLEY) + **LEFEBVRE→LEFEVRE OCR ezme**. Şüpheli ONAYLI. | 🔴 |
| 3 | SIRILSIKLAM 9187 | KONTROL | Yapımcı alanı kirliliği (BEN SILVERMAN=cast, ROBERT SIMONDS=disclaimer'dan). Doğru KONTROL. | 🟡 |
| 4 | YAĞMUR 9265 | KONTROL | 🔴 **Başrol SCOTT COOPER kadrodan düştü** (validate yönü düzeltti, eski ismi cast'e geri eklemedi). | 🔴 |
| 5 | MANASLU 9318 (ORF belgesel) | KONTROL | 🔴 **UYDURMA OYUNCU "HANS EBNER"** (VL halüsinasyon, token-kalkan gediği). Özel-tür yönlendirme doğru. | 🔴 |
| 6 | DÖRT CENAZE BİR NİKAH 9137 | ONAYLI | 🔴 **Christopher Walken + Lee Evans 8-cap'te düştü** (OCR'da net) + JOSH→JOSHUA ezme. Çıkış master boş. Şüpheli ONAYLI. | 🔴 |
| 7 | ÖLDÜREN POZ 9172 (Exposure) | KONTROL | ✅ İçerik TEMİZ (8 cast OCR-otoriter). Kusurlar reporting: `neden` bayat-şablon + afiş PDF'e gömülmemiş (HAFIF_AFIS). | ✅/🟡 |
| 8 | KULÜP EVİ DEDEKTİFLERİ 9065 | ONAYLI | v4 isim-ezme: JAIMEE **LEE** WYSON→JAIMEE WYSON + DELANY→DELANEY. İç .txt doğru. | 🟡 |
| 9 | OLAY YERİ-BÜYÜK AŞK 9084 (Alman Tatort) | KONTROL | 🔴 footage-bloat→başrol kaybı (Manchen/Held/Broumis master'da var, OCR'da yok) + 🔴 "Redaktion" (Alman crew)→cast sızdı. | 🔴 |
| 10 | KLEPTOMAN 9127 | KONTROL | İçerik temiz; 1 sarı: yapımcı ANDY WINDERBAUM KB-eklenti (zaten flag'li). (denetim 529-degrade) | ✅/🟡 |
| 11 | KÖŞENİN KRALI 9132 | KONTROL (KIMLIK) | ✅ İçerik TEMİZ (Riegert). **Gereksiz KONTROL** = KIMLIK false-positive (klipte XML-cast yok). ANTHONV garble düzeltilmedi. | false-pos |
| 12 | KOMİSER CORDIER 9065 (Fransız) | ONAYLI | 🔴 Senarist **"Scénario / Marc-Antoine Laurent" oyuncuya sızdı** (Fransız crew). Şüpheli ONAYLI→KONTROL olmalı. | 🔴 |
| 13 | GEÇMİŞİN GÖLGELERİ 9074 | ONAYLI | Kadronun **5/8'i KB-türetilmiş** (OCR sadece 3, 2'si Co-Exec-Producer), yön doğrulanamadı = H2-komşusu. | 🟡 borderline |
| 14 | HAYALPEREST 9081 (Dreamer) | KONTROL (KIMLIK_CAST) | ✅ **Doğru karar + fail-safe**: OCR 1 cast (footage-bloat)→kilitlenemedi→KONTROL, **uydurma YOK** (poster isimleri sızmadı). | ✅ |
| 15 | KARAYİP KORSANLARI 2 9148 | ONAYLI | ✅ Kadro/yön TEMİZ AMA 🔴 **PDF afişi YANLIŞ film** (Pirates 3 posteri basılmış). Çıkış master üretilmemiş. | 🔴 (afiş) |
| 16 | SIRDAŞ 9162 (Entrusted) | KONTROL | v4 isim-ezme (Sangster→Brodie-Sangster, Steven→Stephen) + Lhermitte düştü + "Dialogue Coach"→cast + "Assistant to"→yapımcı. Doğru KONTROL. | 🟡 |
| 17 | PRESTİJ 9179 (The Prestige) | KONTROL | ✅ İçerik TEMİZ (Nolan OCR-boş alana KB-doldur=doğru). Çıkış master üretilmemiş (2. vaka). | ✅ |
| 18 | ŞİRKET ADAMLARI 9157 (The Company Men) | ONAYLI | 🔴 Yapımcı alanı **"SPECIAL THANKS" bloğundan sızmış** + orijinal-ad ezme COMPANY MEN→MAN. Şüpheli ONAYLI. | 🔴 |
| 19 | NAMUS DÜŞMANI 9262 (Arap-yazısı künye) | KONTROL | 🔴 **H1 CANLI:** Arap künye mükemmel okundu (garble=0) ama extractor parse edemedi→**12 oyuncu+yön Zeki Alasya düştü**. Doğru KONTROL; `neden` yanıltıcı. | 🔴 |
| 20 | İNTİKAM ÇOCUKLARI 1041 (Brotherhood of the Rose) | ONAYLI | ✅ **TEMİZ** (1 KB-additive gerçek oyuncu meşru). Tek kusur master-bloat kozmetik. **İlk temiz ONAYLI.** | ✅ |
| 21 | SESSİZ ÇOCUK 2151 (The Silent Child) | KONTROL | 🔴 **EN CİDDİ rol-eşleme çökmesi:** cast'e **6 YAPIMCI sızdı**, **7 gerçek oyuncu düştü** (Shenton/Sly) = tersine çevirme. Doğru KONTROL; `neden` yanıltıcı. | 🔴 |
| 22 | BEYAZ BALİNA 9031 (Kürtçe) | KONTROL | ✅ İçerik TEMİZ; KU→TMDB özet çalıştı. Kusur: **sidecar HÂLÂ GARBLE** (VAIIAP/BURIIAN) PDF temizken. | ✅/🟡 |
| 23 | POTA 2020-0011 (Türk) | KONTROL (OZET) | 🔴 Başrol **EGEMEN ALMACI atıldı** (OCR'da 38×, afişte 4.). Ezme YOK; doğru KONTROL. | 🔴 (recall) |
| 24 | ZORLU ADAM 1957-0023 (The Hard Man) | ONAYLI | ✅ **TEMİZ** — v4 düşen RUDY BOND+2 yapımcıyı **OCR'dan geri kazandı (recovery)**. Sidecar bayat. **2. temiz ONAYLI.** | ✅ |
| 25 | KÖPRÜNÜN ÖTESİ 1957-0034 (Across the Bridge) | ONAYLI | 🔴 **5 gerçek oyuncu düştü** (Gifford/Brook... OCR'da 14-17×) + 🐕 **KÖPEK "DOLORES" oyuncu listelendi**. Şüpheli ONAYLI. | 🔴 |
| 26 | BEKARLIK SULTANLIKTIR 1958-0046 | Kontrol→**MÜZİKAL klasör** | 🔴🔴 **CRITICAL:** OCR boş iken **KB UYDURMA yapımcı** (Norman Lear/Bud Yorkin — alakasız). **Kök: `tek_film_kunye.py:563-564`.** Özel-tür kapısı KONTROL'ü ezdi (yanlış-sınıf MÜZİKAL). | 🔴🔴 |
| 27 | BEKLENEN BOMBA 1959-0005 (Muharrem Gürses) | KONTROL (**gereksiz**) | ✅ İçerik TEMİZ+DOĞRU (yön Gürses IMDb+XML+Wiki teyitli) ama 🔴 **FALSE-POSITIVE KIMLIK→gereksiz KONTROL** (garble-vs-XML kesişim 0). | false-pos |
| 28 | BÜLBÜLÜ ÖLDÜRMEK 1962-0033 `*` | ONAYLI (canlı=**AutoFix**) | 🔴 **19 Türkçe SESLENDİREN tamamen düşürüldü** (TR-dublaj kadrosu — TRT-kritik) + Gregory Peck OCR'sız KB-eklendi. | 🔴🔴 (TRT) |
| 29 | MARY POPPINS 1964-0031 | KONTROL | ✅ İçerik TEMİZ; yön düşük-kontrast→KB doğru doldurdu. **Tür "KOMEDİ/AİLE" (müzikal değil!)** yanlış-sınıf. | ✅ |
| 30 | AYI YOGİ 1964-0032 (animasyon) | SORUN→**ANİMASYON klasör** | 🔴 **GARBLE teslim kadrosuna girdi** (stitch temiz JAMES DARREN-7× yerine 1× garble DAMES DARREN seçti; çöp "JJAME SBENREET"). **garble_frac=0.0 Latin kör noktası**. | 🔴 |
| 31 | KEDİ GÖZÜ 1969-0057 `*` | ONAYLI (canlı=**AutoFix**) | 🔴🔴 **OCR-otorite ihlali (kurucu kanun):** Parker (OCR 6×) DÜŞTÜ + Sarrazin (OCR 0×) EKLENDİ = ikame. Yapımcı HAZELTON/HAZLETON çift-kayıt. [tam kod-trace forensik] | 🔴🔴 |
| 32 | BABAMIN SİNEMASI 1971-0047 (Le Cinéma de Papa) | KONTROL | 🔴 **GÖMÜLÜ film-içi-film kadrosu sızdı** (Morgan/Marais asıl #1-2'ye). Yön çelişki-çapasıyla kurtarıldı, cast'te o koruma yok. | 🔴 |
| 33 | DOKTOR POPOL 1972-0107 (Chabrol) | ONAYLI | Daniel Ivernel **8-cap'te düştü** + Belmondo yapımcı OCR-dışı KB-eklendi. | 🟡/🔴 |
| 34 | ÇELİK MASKE 1974-0173 (Who?) | KONTROL | 🔴 **ORİJİNAL-AD FABRİKASYONU** "ROBO MAN..." (OCR'da 0×) + cast 8-cap (14+→8) + ana-dil TR yanlış (İngilizce). Doğru KONTROL. | 🔴 |
| 35 | HABABAM SINIFI UYANIYOR 1976-0147 | **ONAYLI (EN BOZUK)** | 🔴🔴 **CRITICAL — Türk klasiği "kusursuz" damgalı ama felaket:** başroller komple kayıp (açılış kartları OCR'da okunmadı) + Halit→Sıtkı ezme + uydurma yapımcı + **Türkçe film KU sanıldı→yanlış-film özeti**. | 🔴🔴 |
| 36 | ANGOLA'DAN KAÇIŞ 1976-0184 (Escape from Angola) | KONTROL | ✅ İçerik TEMİZ (afiş teyit). Orijinal-ad ezme (ESCAPING FORM) + KIMLIK false-positive. | ✅/🟡 |
| 37 | DOSTLUK 1977-0215 (Cody) | KONTROL | 🔴 **Patricia Kane (OCR'da 38×, rol Rosemary) cast'ten düştü** (blok-segmentasyon). Doğru KONTROL ama neden eksik. | 🔴 (recall) |
| 38 | DELİ KAN 1978-0225 `*` | ONAYLI (canlı=**AutoFix**) | 🔴 **Kadronun 5/8'i MÜZİSYEN** (funk grubu WAR üyeleri "music performed by"→cast) + v4 REN→RENN reformat. | 🔴 |
| 39 | FEDORA 1978-0238 (Billy Wilder) | KONTROL | 🔴 **Kapanış "Cast of Characters" tablosu YOK SAYILDI** → William Holden + Henry Fonda düştü (tek-blok seçimi; HABABAM'ın tersi). | 🔴 (recall) |
| 40 | KORKULU GECE 1979-0236 (Night Terror) | KONTROL | ✅ İçerik temiz (garble "Harper Cone"→Harper temizlendi). Kozmetik: çıkış master-bloat + DAMON+BRADLEY KB orta-ad. | ✅ |
| 41 | ÇOCUKLARIN SAVAŞI 1980-0220 (İspanyol Parchís müzikali) | ONAYLI (yanlış) | 🔴 **AFİŞ TAMAMEN YANLIŞ FİLM:** çocuk müzikaline aynı İng. başlıklı **Acholi çocuk-asker BELGESELİ** posteri gömülmüş + KB OCR-dışı soyad. KONTROL olmalıydı. | 🔴 |
| 42 | MAYMUN AKLI 1981-0270 (Monkey Business) | ONAYLI | ✅ **TAM TEMİZ (10/10):** Cary Grant/Marilyn/Hawks OCR-sadık, TR-dublaj doğru dışlandı. Kozmetik master-bloat. **3. temiz ONAYLI.** | ✅ |

**Özet sayım (42 film):** 🔴🔴 CRITICAL: 4 (BEKARLIK, KEDİ GÖZÜ, HABABAM, BÜLBÜL-TRT) · 🔴 HIGH: ~17 · 🟡 MEDIUM: ~9 · ✅ temiz/temiz-karar: ~12 (ÖLDÜREN POZ, KLEPTOMAN, KÖŞENİN KRALI, HAYALPEREST, PRESTİJ, İNTİKAM, BEYAZ BALİNA, ZORLU ADAM, MARY POPPINS, ANGOLA, KORKULU GECE, MAYMUN AKLI). Doğru KONTROL'e giden kusurlular fail-safe'in çalıştığını; ONAYLI/AutoFix'e giden kusurlular kör-noktayı gösterir.