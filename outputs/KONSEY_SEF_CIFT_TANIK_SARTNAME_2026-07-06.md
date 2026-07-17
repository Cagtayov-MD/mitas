Kritik olgu doğrulandı. ELEŞTİRMEN haklı: `_PROD_DEFAULTS["MITAS_SHADOW_VL"]="0"` (satır 1385), `setdefault` (1412) bunu ezemez, satır 3482'deki inline `"1"` ölü-default. Shadow-VL üretimde KAPALI, gerekçe DALGA-181 ~5-6dk/film GPU. Ayrıca fuzzy-kanonik `_garble_imzali` (1093) case-garble'ı yakalar ama case-temiz harf-garble'ı (Minneti) kaçırır; çift-ekran-imza `_case_garble` (1133-1138) da aynı case-only imza. Sentezi yazıyorum.

---

# KONSEY SENTEZ ŞARTNAMESİ — MITAS Künye-Okuma Stratejik Yönü

## Karar özeti (tek cümle)

**OneOCR birincil KALIR; garble-VE-kör iki-kanallı tetikle, master-PNG'nin YALNIZ yönetmen-kart bölgesine GLM'yi mevcut `_fuse_yonetmen` karar-kapısına ek TANIK olarak sokan cerrahi kurtarma inşa edilir** — master-PNG asla birincil-okuyucu yapılmaz, cast'e GLM-liste yasak, her adım kanıt-kapılı + kill-switch + yeni-yanlış=0.

---

## 1) SEÇİLEN MİMARİ ve NEDEN

**SEÇİLEN: OneOCR-first + iki-kanallı-tetikli cerrahi kurtarma (B tabanı + ELEŞTİRMEN'in 3. yolu), D-kademeli rollout ile.**

Adı: **ÇİFT-TANIK KURTARMA** (GLM/VL birincil-okuyucu değil, karar-kapısına tanık).

Neden bu:
- **Çağatay'ın kuzey-yıldızı iki-yönlüdür**: frame'deki isim (a) PDF'e GİRMELİ (recall) ve (b) DOĞRU girmeli (precision). "Okunamadı>yanlış" precision'ı recall'dan üstün tutar. Bu iki-yön birleşik metrik: **yüksek-recall ∧ yeni-yanlış=0.**
- OneOCR'ın çok-kare mutabakatı + mevcut `_fuse_yonetmen` çok-tanık kapısı (fuzzy-kanonik + KB-rol-kısıt + çift-ekran-imza + ABSTAIN, kod 1085-1161) precision'ın KANITLI omurgasıdır. Sökülmez.
- Eksik olan recall'dır: garble-ama-dolu yönetmen (VincenTe Minneti) QC1'i geçtiği için hiçbir pahalı motora ulaşmıyor (`_vl_need=(not yonetmen) or cast<3`, mitas_pipeline.py:2422). Çözüm bu deliği KAPATMAK — tüm mimariyi ters çevirmek değil.

**Reddedilenler (tek-cümle gerekçe):**
- **A (master-PNG→GLM birincil):** RED — bozuk-ama-dolu master (footage-bloat) GLM'ye "temiz-yanlış" okutur, tek-kaynak-tek-motor mutabakat-otoritesini yıkar, "okunamadı>yanlış"ı yapısal ihlal eder; master-üretim kırılganlığını (siyah-zemin-CUT) kritik-yola sokar.
- **C-saf (yönetmen için master-PNG birincil):** RED — yönetmen-birincil bile bozuk-master riskini taşır; GLM birincil-okuyucu değil, mevcut kapıya TANIK olmalı.
- **B-mevcut-tetik (yalnız case-garble):** YETERSİZ — case-temiz harf-garble (Minneti) ve OneOCR-tümden-kör vakayı kaçırır; tetik genişletilmeli.

---

## 2) YÖNETMEN vs CAST MOTOR-AYRIMI (pazarlıksız)

Konsey oybirliği bu noktada — GLM performans-profili bunu zorunlu kılar:

| Alan | Format | Birincil motor | Kurtarma motoru | Gerekçe |
|---|---|---|---|---|
| **YÖNETMEN** | tekil-kart ("DIRECTED BY / X") | OneOCR + `_fuse_yonetmen` | tetikli → master-PNG kart-bölgesi → **GLM** | GLM'nin sweet-spot'u: tek-net-kart, 5-19sn, TERTEMİZ, formata-sadık |
| **CAST** | yoğun Türkçe LİSTE (8-15 sıkışık isim) | OneOCR + KB-imza-süzgeci (`identity_first_cast`, credit_qc_gates.py:54-87) | **yalnız fuzzy-kanonik + tek-isim VL** (garble-satır) | **GLM-LİSTE YASAK**: GLM yoğun-Türkçe-listede bozar/loop + CJK-çöp |

**KIRMIZI ÇİZGİ: Cast'e GLM-liste-okuması YASAK.** Cast kurtarması yalnız tek-tek garble-satır düzeyinde (fuzzy-kanonik, gerekirse tek-isim VL) — asla "master-PNG cast-bloğunu GLM oku". Bu, GLM'yi zaafına değil gücüne koşma ilkesidir.

---

## 3) BOZUK-MASTER KALKANI (bozuk-ama-dolu master nasıl elenir)

ELEŞTİRMEN'in TEZ-1'i öldüren tespiti korunur: **text_mask/sharpness tek başına footage-bloat'lı bozuk-ama-dolu master'ı ayırt EDEMEZ** (footage-üstü yazı da "sağlıklı" görünür). Bu yüzden sağlık-skoru TEK kalkan değildir. Üç-katman, birbirini yedekler:

**Kalkan-1 — Master-PNG birincil-yola SOKULMAZ (yapısal).** GLM master-PNG'den bir çıktı üretir ama bu çıktı ASLA doğrudan PDF'e gitmez; yalnız `_fuse_yonetmen` kapısına bir aday-tanık olur. Bozuk-master → GLM temiz-yanlış üretse bile, kapı onu teyitsiz görürse KONTROL'e atar. Bu, bozuk-master'ın "temiz-yanlış"ını nötralize eden ASIL kalkandır (sağlık-skoruna bağlı değil).

**Kalkan-2 — Çapraz-tanık zorunluluğu (mevcut kapı mantığı).** GLM-adayı ancak şu koşullardan biriyle ONAYLI-yola girer:
- (a) KB-rol-kısıtlı imza (`_kb_verify_flex` ≠ RED + name_match/close), VEYA
- (b) fuzzy-kanonik güvenli-hit (jw≥0.92 + marj≥0.03, mevcut eşik), VEYA
- (c) ekran çift-imza (kunye.txt VE dilim-korpusta harfiyen).

Hiçbiri yoksa → **KONTROL (okunamadı, yanlış değil).** Garble-vakada OneOCR-tanığı garble olsa bile GLM-adayı fuzzy-kanonik/KB üzerinden teyit bulabilir (Minnelli KB'de var) — bu, ELEŞTİRMEN'in "garble-vakada tanık yok" itirazına cevap: tanık OneOCR-token değil, KB/dilim/fuzzy-kanoniktir.

**Kalkan-3 — Ucuz master-sağlık ön-elemesi (chatbot-guard + kaba-bloat).** `_pipe_shadow_vl.py`'de mevcut `_is_chatbot` (footage/boş-kare sahne-tarifi eler) + kaba text_mask-oranı eşiği (footage baskınsa GLM'yi hiç çağırma, GPU tasarrufu). Bu kalkan **precision için değil, maliyet için** — en tehlikeli bozuk-master'ı Kalkan-1+2 tutar; Kalkan-3 sadece boşa-GLM'yi azaltır.

---

## 4) GARBLE-TESPİT TETİKLEYİCİSİ (iki ortogonal kanal + eşikler)

Yönetmen alanı DOLU olsa bile (QC1 geçmiş olsa bile) şu iki kanaldan ≥1 ateşlerse → "yönetmen-şüpheli" → kurtarma-merdiveni. İki kanal ORTOGONALDİR (biri diğerinin kör-noktasını kapatır):

**KANAL-A — Kareler-arası tutarsızlık (OneOCR kendi içinde çelişiyor).**
- Tetik: aynı yönetmen-kartı N≥2 karede okunduğunda, benzersiz normalize-okuma sayısı ≥2 (fold+ascii sonrası). Bugünkü kanıt: 4 kare → {minneti, Minnati, minneLti, Minneti} = 4 varyant.
- Eşik: `jw_max_pair < 0.97` (kareler-arası en-benzer çift bile %97 altında) VEYA benzersiz-fold-okuma ≥ 2.
- Kapatır: case-temiz harf-garble'ın DEĞİŞKEN halini (Minneti≠Minnati case-temiz ama tutarsız).

**KANAL-B — Kart-var-ama-OneOCR-kör (ELEŞTİRMEN'in eklediği, iki tezin de kör-noktası).**
- Tetik: `credit_detect` bir yönetmen-etiketi ("DIRECTED BY / YÖNETEN / YÖNETMEN") ekranda VAR diyor AMA `_fuse_yonetmen` o bölgeden geçerli-isim çıkaramadı (boş VEYA `_looks_garble`-pozitif VEYA `_case_garble`-pozitif).
- Kapatır: KANAL-A'nın kör-noktasını — OneOCR TUTARLI-yanlış (4 kez aynı "Minneti") veya TÜMDEN-kör okuduğunda kare-varyansı yoktur, ama etiket-var-isim-yok sinyali ateşler.

**Case-garble kanadı (mevcut):** `_garble_imzali` (1093) + `_case_garble` (1133) ZATEN CANLI — VincenTe tipini yakalar. Korunur, üçüncü sinyal olarak kalır.

**ÖN-KOŞUL ÖLÇÜMÜ (ELEŞTİRMEN şartı, inşadan ÖNCE):** KANAL-B ateşleme-oranı geriye-dönük loglardan sayılır — "kaç filmde credit_detect-pozitif + `_fuse_yonetmen`=OKUNAMADI/garble". Eğer bu oran yüksekse (>%40) KANAL-B "her filme GLM"e yozlaşır → A'nın reddedilen maliyeti geri gelir. Ölçüm ADIM-0'dır (§7).

---

## 5) "FRAME'DE VARSA DOĞRU PDF'E" ÖLÇÜTÜ (ölçülebilir, doğrulanabilir)

Tek metrik: **FRAME-TO-PDF SADAKATİ** (byte-nötr A/B ile).

15-vaka pilot (garble-riskli filmler: TOPLU GÖSTERİLER tipi + normal-temiz kontrol filmleri karışık). Her film için ELLE ground-truth (insan gözü, frame'de fiziksel ne yazıyor):

| Metrik | Tanım | Kabul-kapısı |
|---|---|---|
| **Sadakat (recall)** | frame'de-okunabilir isimlerden PDF'e DOĞRU aktarılan oranı (K/N) | ARTMALI (en az TOPLU GÖSTERİLER Minnelli kurtulmalı) |
| **Yeni-yanlış (regresyon)** | ÖNCE doğru → SONRA yanlış olan alan sayısı | **= 0 (PAZARLIKSIZ)** |
| **Uydurma** | KB-komşusuna yanlış-eşleme (Caldana→Judd tipi) | **= 0** (garble-freni korur) |
| **Abstain isabeti** | okunamayanı KONTROL'e atma doğruluğu | DÜŞMEMELİ |

**Kesin hüküm: Yeni-yanlış=0 VE Uydurma=0 sağlanmadan hiçbir katman canlıya alınmaz.** Bu, "okunamadı>yanlış"ın sayısal karşılığıdır. A bu kapıyı geçemez (bozuk-master yeni-yanlış üretir); ÇİFT-TANIK KURTARMA geçebilir (additive + teyit-kapılı → en kötü KONTROL'de kalır, asla yeni-yanlış-ONAYLI).

**Doğrulama yöntemi:** aynı 15 film MİMARİ-ESKİ (flag-off) vs ÇİFT-TANIK (flag-on), byte-nötr diff. golden 28/28 flag-off'ta değişmemeli.

---

## 6) KİLL-SWITCH'ler + GOLDEN-REGRESYON KORUMASI

Her yeni davranış anayasa-gereği kill-switch'li + default-OFF (flag-off byte-nötr):
- `MITAS_GARBLE_INCONSISTENCY` (KANAL-A) — default OFF.
- `MITAS_CREDIT_BLIND_TRIGGER` (KANAL-B) — default OFF.
- `MITAS_DIRECTOR_GLM_RESCUE` (master-PNG kart→GLM tanık) — default OFF.
- Mevcut `MITAS_FUZZY_KANONIK` (CANLI, kill-switch'li) — korunur.

Koruma:
- **Golden 28/28 KORUNUR**: tüm flag-off iken byte-nötr (regresyon=0). Flag-on golden AYRI koşulur (A/B).
- **Additive-yapı**: kurtarma yalnız garble-şüpheli/KONTROL vakalarını kurtarmaya çalışır; temiz-tutarlı okumaya DOKUNMAZ. En kötü durum: vaka KONTROL'de kalır (asla yeni-yanlış-ONAYLI).
- **Fail-safe**: her basamak hata→önceki-davranış AYNEN (mevcut VL-fallback deseni, mitas_pipeline.py:2437-2492).
- **Yeni-yanlış=0 bekçisi**: her adımda §5 metriği; 0'dan çıkarsa adım GERİ ALINIR.

---

## 7) KADEMELİ İNŞA PLANI (her adım kanıt-kapılı)

**ADIM-0 — ÖLÇÜM (bugün, SIFIR üretim-değişikliği, kanıt-toplama).**
İki geriye-dönük ölçüm scripti (salt-okur, mevcut loglar/çıktılar üzerinde):
1. **KANAL-B ateşleme-oranı**: kaç filmde `credit_detect`-yönetmen-etiketi-pozitif + `_fuse_yonetmen`=OKUNAMADI/garble. → KANAL-B'nin "her filme GLM"e yozlaşıp yozlaşmayacağını belirler.
2. **Shadow-vs-OneOCR 15-vaka kıyas** (Task #23 pending): shadow-VL/GLM offline koşulup (KAPALI olduğu için ÖZEL offline-run) mevcut OneOCR-birincil çıktısıyla yan-yana. → "GLM ne kadar recall kazandırır" kanıtı.
- **KANIT-KAPISI**: KANAL-B oranı <%40 VE 15-vakada GLM net-recall-kazancı gösteriyorsa → ADIM-1'e geç. Değilse tetik-eşikleri yeniden-ayarlanır.
- **DÜRÜST MALİYET NOTU (ELEŞTİRMEN şartı)**: shadow-VL üretimde KAPALI (5-6dk/film, DALGA-181). Bu ölçüm offline-run'dır; üretim-hızına ETKİ ETMEZ. Herhangi bir GLM/VL yeniden-devreye-alma maliyeti (kare-başı 5-19sn × tetik-oranı) ADIM-1 bütçesine açıkça yazılır.

**ADIM-1 — TETİK-GENİŞLETME (KANAL-A+B, byte-nötr, kurtarma-YOK).**
Yalnız "yönetmen-şüpheli" bayrağını hesapla+logla (kurtarma tetikleme YOK). golden byte-nötr. → tetiğin doğru filmlerde ateşlediğini, temiz filmlerde ateşlemediğini KANITLA (false-positive oranı ölç).
- **KANIT-KAPISI**: tetik TOPLU GÖSTERİLER'de ateşliyor, temiz-golden'da ateşlemiyorsa → ADIM-2.

**ADIM-2 — KURTARMA-MERDİVENİ (yönetmen, ilk-teyitli).**
Tetik ateşlenince sırayla, ilk-teyitte dur (GPU tasarrufu):
1. fuzzy-kanonik (ucuz, KB-kilitli, CANLI) — yeterse dur.
2. yetmezse master-PNG **yönetmen-kart-bölgesi** → GLM → `_fuse_yonetmen` kapısına tanık.
3. yetmezse tek-isim VL (yavaş, son-çare).
- Her basamak kill-switch + fail-safe. Cast'e GLM-liste YOK.
- **KANIT-KAPISI**: 15-vaka A/B'de yeni-yanlış=0 VE uydurma=0 VE recall↑ → CANLI (default-OFF→ON kademeli).

**ADIM-3 — CAST garble-satır kurtarma (opsiyonel, yönetmen kanıtlanınca).**
Tek-tek garble-cast-satır → fuzzy-kanonik (+ gerekirse tek-isim VL). Liste-GLM YOK. Aynı yeni-yanlış=0 kapısı.

**ADIM-4 (uzak, opsiyonel) — A-yeniden-değerlendirme.** master-PNG-first, ancak ADIM-2/3 kanıtı + izole-A/B-yeni-yanlış=0 kapısını geçerse, üçüncü-motor adayı olarak (birincil-yol DEĞİL) yeniden görüşülür.

---

## 8) TEK-GPU MALİYET (kabul edilebilir mi)

**Kabul edilebilir — çünkü tetikli, her-filme değil.**

- Donanım: tek RTX 3090 24GB, gemma-31b resident ~18.7GB, GLM/VL kare-başı 5-19sn.
- **Çağatay "hız<kalite" = gereğinde-pahalı, gereksizde-ucuz** (sınırsız-GLM değil). ÇİFT-TANIK KURTARMA GLM'yi yalnız yönetmen-şüpheli filmde + yalnız kart-bölgesinde çağırır.
- Beklenen ek: yönetmen-şüpheli-oranı × (~15-40sn/film). Garble azınlık-vaka olduğundan (bugün 1 film) marjinal. ~890sn/film gerçeğinde şüpheli-filmlerde %2-5, temiz-filmlerde SIFIR ek.
- **Kritik: shadow-VL (5-6dk/film) yeniden-AÇILMAZ.** Kurtarma shadow'dan bağımsız, cerrahi çağrıdır — DALGA-181'in söndürdüğü tam-master-VL maliyetine DÖNMEZ. Bu, ELEŞTİRMEN'in "sıfır-risk altyapı" yanılsamasına düzeltme: altyapı bedava değil, ama kurtarma o pahalı yolu KULLANMAZ.
- VRAM: GLM-OCR küçük-model, resident-31b yanında sıralı-çağrı sığar; yönetmen-kartları BATCH'lenir (tek çağrı-dizisi, swap-thrash önlenir).

---

## 9) İLK ADIM (bugün yazılacak kod — dosya + fonksiyon)

**ADIM-0, salt-okur ölçüm scripti — SIFIR üretim-değişikliği. Fable bunu yazar:**

**Dosya:** `E:\MITAS\scripts\garble_trigger_olcum.py` (YENİ, salt-okur, üretim-koduna dokunmaz)

**İki fonksiyon:**

1. `kanal_b_ateslenme_orani(cikti_kok)` — mevcut film çıktı-klasörlerini tarar; her filmde:
   - `credit_detect` yönetmen-etiketi var mı (mevcut credit-detect log/çıktısından),
   - `_fuse_yonetmen` sonucu OKUNAMADI/boş/garble mı (mevcut kunye.txt / karar-çıktısından `_looks_garble` + `_case_garble` uygula — bu iki fonksiyon `credit_text_read.py`'den import edilir, SALT-OKUR),
   - **döndür**: `(kart_var_isim_yok_sayisi / kart_var_toplam)` = KANAL-B ateşleme-oranı + film-listesi.

2. `kanal_a_tutarsizlik_tara(cikti_kok)` — her filmde jenerik-kare-OCR'larını (kare-kare OneOCR çıktıları) toplar; yönetmen-kartı karelerinde benzersiz-fold-okuma sayısını + `jw_max_pair` hesaplar; ≥2 benzersiz VEYA jw<0.97 olanları "KANAL-A-pozitif" listeler.

**Çıktı:** scratchpad'e JSON rapor (üretim outputs/'a değil) — Çağatay'a "KANAL-B oranı %X, KANAL-A %Y film, örtüşme %Z" özeti. Bu, ADIM-1'in KANIT-KAPISINI besler.

**Neden ilk-adım bu:** üretim-davranışı DEĞİŞMEZ (byte-nötr, golden dokunulmaz), Çağatay'ın istediği kanıt (Task #23) toplanır, ve ELEŞTİRMEN'in "KANAL-B her-filme-GLM'e yozlaşır mı" ön-koşul-ölçümü inşadan ÖNCE cevaplanır. `credit_text_read.py`'nin `_looks_garble`/`_case_garble` fonksiyonları import edilir (kopyalanmaz — tek-kaynak).

---

## KAPANIŞ (konsey mutabakatı)

**OneOCR birincil kalır; garble-VE-kör iki-kanallı tetik, master-PNG yönetmen-kartını GLM'ye YALNIZ tanık olarak verir, mevcut çok-tanık kapısı yeni-yanlış'ı sıfırda tutar.** Master-PNG birincil YAPILMAZ (A-RED), cast'e GLM-liste YASAK, shadow-VL'nin kapalı-maliyeti dürüstçe hesaba yazılır, her adım kanıt-kapılı + kill-switch + byte-nötr. İlk somut kod: `garble_trigger_olcum.py` (salt-okur ölçüm) — inşadan önce tetik-oranını ve GLM-recall-kazancını ölçer.

**Pazarlıksız kırmızı-çizgiler:** yeni-yanlış=0 ∧ uydurma=0 kabul-kapısı; cast'e GLM-liste YASAK; master-PNG doğrulama/tanık kalır, birincil-yola sokulmaz; OneOCR mutabakatı OTORİTE; her katman kill-switch+fail-safe+byte-nötr; shadow-VL yeniden-açılmaz (kurtarma o pahalı yolu kullanmaz); KANAL-B ateşleme-oranı inşadan ÖNCE ölçülür.

**Doğruladığım kod (mutlak yol, DOSYA DEĞİŞTİRİLMEDİ):**
- `E:\MITAS\scripts\mitas_pipeline.py` — `_PROD_DEFAULTS["MITAS_SHADOW_VL"]="0"` (1385) + `MITAS_OCR_GLM_CONSENSUS="0"` (1358); `_apply_production_defaults` setdefault (1410-1413, shadow-KAPALI ispatı); satır 3482 inline-default "1" ölü (setdefault ezemez); DALGA-181 5-6dk/film gerekçesi (1381-1384).
- `E:\MITAS\scripts\credit_text_read.py` — fuzzy-kanonik `_garble_imzali` case-only tetik (1091-1108, Minneti case-temiz→KAÇAR onaylandı); çift-ekran-imza `_case_garble` (1132-1140, aynı case-only sınır); ABSTAIN "yanlış>boş" (1158-1161).

**ELEŞTİRMEN'in kök-düzeltmesi kabul edildi ve şartnameye işlendi**: shadow-VL üretimde KAPALI olgusu tüm maliyet-hesabına yazıldı; "sıfır-risk hazır altyapı" yanılsaması düzeltildi (kurtarma shadow'un pahalı tam-master yolunu KULLANMAZ, cerrahi kart-bölgesi çağrısıdır); KANAL-B (kart-var-kör) iki tezin de kör-noktası olarak eklendi ve ateşleme-oranı ADIM-0 ön-koşul-ölçümü yapıldı.