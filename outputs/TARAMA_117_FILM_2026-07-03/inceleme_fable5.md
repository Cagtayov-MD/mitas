İnceleme tamam. Tüm kanıtları topladım — hüküm ve bulgular:

---

# HÜKÜM: KOŞULLU-ONAY

Paketin mimarisi sağlam: additive, fail-safe'li, kırmızı çizgi (alan doldurmama A0'da) korunmuş, MANASLU-Frankenstein koruması sayısal olarak doğrulandı (chunk uzunluk-ön-filtresi `hans`↔`hans-peter stauber` ve `ebner`↔`hannelore ebner`'i SKIP'liyor — ölçtüm). Router-nötrlük iddiası (C) **doğrulandı**. Ancak fuzzy kalkan-delmesi yönlü yeni yanlış-pozitif zarfı gerçek ve **işaretsiz** — canlıya alınmadan önce en az Bulgu-1'in görünürlük düzeltmesi şart.

## Bulgular (önem sıralı)

**1. [YÜKSEK — B] Fuzzy 0.84, farklı-GERÇEK-kişi çiftlerini birleştirir ve sonuç İŞARETSİZ alan doldurur** — `_pipe_credit_vl.py:175` + `:313-315`
Ölçülü kanıt (SequenceMatcher, hepsi uzunluk-ön-filtresini de geçiyor):
- `richard johnson` ↔ `richard johnston` = **0.968** (iki ünlü, farklı yönetmen)
- `john huston` ↔ `john houston` = 0.957 · `paul schneider` ↔ `paul schneier` = 0.963
- **`atif yilmaz` ↔ `arif yilmaz` = 0.909, `metin erksan` ↔ `cetin erksan` = 0.917** — TRT arşivi için kritik: tek-harf farklı Türkçe ad çiftleri eşiği rahat geçer.
- `dennis hopper` ↔ `dennis harper` = 0.846 — eşiğin hemen üstü.

Kalkanın anlamı "bu isim korpusta VAR"dan "korpusta buna 1-2 harf uzak BİR ŞEY var"a gevşedi. Fuzzy-geçen aday `out["yonetmen"]`'i **doldurur** ve `vl_yon_kaynak="gemma4"` der — exact-geçenle ayırt edilemez. VL, jenerikteki başka bir kişinin (kurgucu/görüntü yönetmeni) soyadını yanlış okuyup yönetmen ilan ederse, eski kalkan düşürüp KONTROL'e yollardı; yeni kalkan geçirir → downstream cross-check yakalamazsa yanlış kişi ONAYLI'ya gidebilir. **Öneri:** fuzzy/cross-line yoluyla geçen doldurmayı işaretle (`vl_yon_kaynak="gemma4+fuzzy"` + `vl_yon_fuzzy_matched_line` alanı); mümkünse fuzzy-geçişte KB `verify(y,"director")=="ONAY"` corroboration'ı şart koş ya da reasons'a görünürlük satırı ekle (A2'nin ÇAPA-1'i zaten bu yönde — o gelene dek asgari işaretleme).

**2. [ORTA — B] Cross-line "ardışıklık" dosya/kare sınırı tanımıyor** — `_pipe_credit_vl.py:121-138` + `:209`
`raw_lines`, üç glob deseninin dosya-dosya birleşimi + manifest'in kare-kare `credit_lines` eklemesi. Dosya-X'in son satırı ile dosya-Y'nin ilk satırı, kare-N'in son kartıyla kare-N+1'in ilk kartı yapay "ardışık" olur. Kurgu senaryosu: kare-N'de tek-kelime pür-satır `JOHN` (dev-font ad kartı üst parçası), kare-N+1'de `SMITH` (başka kişinin kartı) → VL uydurması "John Smith" `_cross_line_hit`'ten geçer. Ek nit: `_fold` iç boşlukları normalize etmiyor → `line == chunk` exact'i çift-boşlukta kaçar (fuzzy telafi eder ama exact yolun amacı buydu). **Öneri:** korpus birleştirirken her dosya/kare sınırına sentinel satır (`"\x00"` gibi) ekle — `_chunk_eq` asla eşleşmez, yapay bitişiklik ölür; `_fold`'a `" ".join(s.split())` ekle.

**3. [ORTA — B] Manifest korpusuna altyazı/diyalog sızıntısı mümkün** — `giris_jenerik_havuzu.py:209-224` + `jenerik_detector.py:597-612`
`credit_lines` filtresi = alt-bant (y≥0.82) VE `_is_credit_text`. Ama `is_credit_text_line` gevşek: ≤5 kelime + nokta-yok + ≥%50 harf yeter. Letterbox'lı içerikte yukarı kayan altyazı (y-merkez ~0.75), üst-konumlu çeviri, şarkı sözü parçası, ekrandaki karakter-adı → hepsi `credit_lines`'a girer. "Her satır gerçek piksel-okuması" invariantı doğru; "her satır KREDİ metni" değil. Sonuç: kalkan-korpusu diyalog kelimeleriyle genişler → VL uydurması bir replikteki adla (fuzzy 0.84) doğrulanabilir. Kabul edilebilir risk ama belgelenmeli; istenirse manifest'ten yalnız `in_sub_band=False` **ve** `y_center_frac<0.70` satırları alınabilir.

**4. [ORTA — A] Giriş-havuz VL girdisi: dolu-ama-eksik havuzda geri dönüş YOK** — `_pipe_credit_vl.py:71-74`
Fallback yalnız havuz TAMAMEN boşken. OneOCR stilize-font yönetmen kartını okuyamayıp o kareyi `footage_no_text` diye elerse ama başka kareleri havuza alırsa, VL o kartı hiç görmez — eski davranışta ham `frames/giris` ile görürdü. Yorum bu takası "bilinçli" diyor ama yalnız boş-havuz ucunu kapatıyor. Hafifletici: o kart OneOCR-körüyse korpus da onu içermez → kalkan zaten düşürürdü; yani net kayıp havuzun yanlış-eleme (FN) vakalarıyla sınırlı. Yine de `MITAS_VL_USE_GIRIS_POOL` env'i var (kill-switch tam) — kabul, izlenmeli.

**5. [ORTA-DÜŞÜK — D] Run-scope'un env kill-switch'i YOK** — `_pipe_credit_vl.py:112-114`, `mitas_pipeline.py:2130`
Diğer her yenilik env'li (`MITAS_VL_RAW_FUZZY`, `..._CROSSLINE`, `..._CORPUS_MANIFEST`, `..._USE_GIRIS_POOL`, eski `..._RAW_ADJACENCY`); korpus run-scope'u yalnız CLI'dan geliyor ve pipeline **hep** gönderiyor. Fail-safe yalnız BOŞ kapsamda tetiklenir; "scoped-ama-fakir" durumda (eski koşu 1fps-uzun-kuyrukla kartı okumuştu, yeni 1.5fps koşu kaçırdı → scoped korpus dolu ama o satır yok) eski davranışa dönüş için kod değişikliği gerekir. **Öneri:** `MITAS_VL_CORPUS_RUNSCOPE=0` env'i ekle (ocr_job'u yok say). Not: `ocr-{8hex}` + prefix-glob çakışma riski pratikte sıfır (eski job'lar da tam-8-hex; tek ek-eşleşme `-fb` kardeşi — amaçlanan), `ocr_job` 1862'de koşulsuz atanıyor → NameError yolu yok. Bu kısım temiz.

**6. [DÜŞÜK — D] Kill-switch bağlaşması: `MITAS_VL_RAW_FUZZY=0` cross-line'ı da öldürür** — `_pipe_credit_vl.py:166-167`
Erken `return False` + `rmin` fuzzy bloğunda parse ediliyor → `MITAS_VL_RAW_CROSSLINE=1` tek başına çalıştırılamaz. Bilinçliyse tek satır yorum; değilse `rmin` parse'ını fuzzy-gate'in üstüne al.

**7. [DÜŞÜK — A] Glob-metakarakter ucu: manifest, "kalkan-kapalı"yı "yarım-korpusla-kalkan-açık"a çevirir** — `_pipe_credit_vl.py:108-110` + `:127-136`
Clip yolu `[`/`]` içerirse tüm glob'lar boş döner (pre-existing bug) ama manifest `os.path.isfile` ile OKUNUR → korpus artık boş değil, giriş-manifest-only. Eskiden `raw yok → kalkan atla (FAIL-SAFE)` çalışırdı; şimdi ÇIKIŞ jeneriğinden okunan doğru yönetmen giriş-korpusunda bulunamayıp düşürülür. `glob.escape(clip)` (dizin kısmına) kökten çözer.

**8. [NİT] A0 kapsamı eksik:** `mitas_pipeline.py:2139-2156`'daki "VL-yönetmen cast'te de var" düşürmesi (`_drop`) reasons/_DURUM'a yüzeylenmiyor — yalnız kalkan-düşürmeleri görünür. Ayrıca tek-token ≥8-harf adaylar (soyad-tek başına) fuzzy'ye çapasız girer (`petersen`↔`peterson` 0.87 geçer); `len(name)<8` boşluk-dahil sayım muhafazakâr yönde, sorun değil.

## C) Router-nötrlük — DOĞRULANDI
Yeni reason `"VL aday ismi (teyitsiz, insan baksın): …"` metnini `_sig` substring setiyle (`mitas_pipeline.py:2763-2783`: "yönetmen okunamadı", "yön+yapımcı yok", "yönetmen doğrulama: okunamadı", "kimlik çelişki", "yanlış-film", "cast kesişimi 0", "kimlik kurulamadı", "kaynak-çelişkisi", "oyuncu yok", "cast garble", "özet yok", "Latin-dışı", "karakter bozuk", "isim-QC", "CAST_CAP_DUSEN") ve `credit_severity_router.from_durum` desenleriyle (`:166-195`) tek tek karşılaştırdım: **çakışma yok**. Reason yalnız `not _v4_yon` dalında, "yönetmen okunamadı (KB-fill yok…)" zaten eklendikten SONRA ekleniyor → hem ikili karar (`reasons` zaten dolu) hem tip-etiketi değişmez; `_R and not _r["agir"]` güvenlik bendi de duruyor. Tek teorik açık: metne katılan aday-isimler serbest metin — kişi adının bir router desenini içermesi pratikte imkânsız. `video_credits` akışı da temiz: yalnız 2069/2076/2135'te atanıyor, `vl_yon_hallucinated` anahtarı 2618 ve 2868'e bozulmadan ulaşır; `_merged` falsy ise `get→None→atla`.

## Performans (A)
Kabul: 14k satırda aday başına exact-regex + fuzzy (uzunluk ön-filtreli) + yalnız-fuzzy-başarısızsa cross-line (n=2-3 için ≤3 split × korpus taraması, çoğu satır `max(2, %25)` ön-filtresinde elenir). VL çağrısının dakikalar mertebesindeki maliyeti yanında ihmal edilebilir; run-scope korpusu ayrıca küçültüyor.

## Koşullar (öncelik sırasıyla)
1. Fuzzy/cross-line yoluyla geçen yönetmen doldurmasını **işaretle** (`vl_yon_kaynak="gemma4+fuzzy"` + eşleşen korpus satırını alana yaz) — Bulgu-1'in asgari, karar-nötr düzeltmesi.
2. Korpus kaynak-sınırlarına sentinel satır (Bulgu-2) — 3 satırlık değişiklik.
3. `MITAS_VL_CORPUS_RUNSCOPE` env kill-switch'i (Bulgu-5).
4. Golden 10/10 testi repo'da persist değil (yalnız `_pipe_credit_vl.py` sembolleri içeriyor; ayrı test dosyası yok) — task #6'daki regresyon setine bu 10 vaka + Bulgu-1'in Johnson/Johnston-tipi NEGATİF vakaları eklensin.

İlgili dosyalar: `E:\MITAS\scripts\_pipe_credit_vl.py` (satır 71-74, 104-138, 161-228, 298-330), `E:\MITAS\scripts\mitas_pipeline.py` (2130, 2612-2623, 2763-2783, 2867-2871), `E:\MITAS\scripts\credit_severity_router.py` (166-195), `E:\MITAS\scripts\giris_jenerik_havuzu.py` (209-241), `E:\MITAS\core\pipelines\ocr\jenerik_detector.py` (597-612).