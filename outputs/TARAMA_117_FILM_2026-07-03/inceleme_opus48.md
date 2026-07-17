Performans somut: worst-case ~0.8s/isim, film başına ~8s eklenebilir (yönetmen genelde 1-2 isim + cast<3 durumunda birkaç aday → gerçekte ~2-4s). VL-fallback zaten dakikalar süren bir gemma4 VL çağrısı olduğu için bu ihmal edilebilir. Ama tek endişe: `_fuzzy_line_hit` her satırda `line.split()` yapıyor ve `_cross_line_hit` her satırda `_fold` edilmiş korpus üstünde çalışıyor — `_in_raw` her çağrıda tüm korpusu yeniden tarıyor. 10 isim × 14k satır tolere edilebilir ama optimize edilebilir (korpus bir kez fold+split cache'lenebilir). Kritik değil.

Şimdi tüm doğrulamalar tamam. Bir son kontrol: `_qc1_failed=True` yolunda (satır 2543) veya credit_validate geri-yazma sonrası `video_credits`'in `vl_yon_hallucinated` alanını kaybedip kaybetmediği. Satır 2268-2269 sadece `yonetmen`'i güncelliyor, sözlüğün diğer alanlarını korur. Alan korunuyor. Ayrıca `MITAS_NO_VL_FALLBACK` kill-switch'i mevcut. Yeni env kill-switch'lerin (MITAS_VL_RAW_FUZZY, MITAS_VL_RAW_CROSSLINE, MITAS_VL_USE_GIRIS_POOL, MITAS_VL_CORPUS_MANIFEST) hepsi default-ON ve `=0` ile kapanabiliyor. Fail-safe'leri diff'te teyit ettim.

İncelemem tamamlandı. Hükmümü veriyorum.

---

## HÜKÜM: KOŞULLU-ONAY

Değişiklik paketi mühendislik açısından **titiz, fail-safe'leri sağlam, router-nötr iddiası DOĞRU**. Kırmızı çizgi (alan-doldurmama) korunuyor. Ancak fuzzy 0.84 katmanı hayalet-kalkanının uydurma-yakalama gücünü ölçülebilir biçimde zayıflatıyor — bu bilinçli bir recall/precision tavizi, ama boyutu belgede iddia edilenden daha büyük. Aşağıdaki F-1'i giderirseniz (veya bilinçli kabul ederseniz) ONAY.

---

## BULGULAR (önem sıralı)

### F-1 [ORTA-YÜKSEK] — Fuzzy 0.84 kalkanı, aynı-ön-adlı soyad-varyantlarının TAMAMINI birleştiriyor (kalkan zayıflaması)
`_pipe_credit_vl.py:172` (`rmin=0.84`) + `_fuzzy_line_hit:215`. Ampirik ölçüm (kendi çalıştırdığım testler):

| VL okuması | Korpustaki FARKLI/yanlış isim | ratio | Kalkan kararı |
|---|---|---|---|
| Paul Schneider | PAUL SCHNEIER | 0.963 | **GEÇER** |
| Robert Johnson | ROBERT JOHNSTON | 0.966 | **GEÇER** |
| Steven Spielberg | STEVE SPIELBURG | 0.867 | **GEÇER** |
| John Williams | JOHN WILLIAMSON | 0.929 | **GEÇER** |
| Michael Kahn | MICHAEL KANN | 0.917 | **GEÇER** |

0.84 eşiği ~%16 karakter-drift'e izin verir; ortak ön-ad + benzer soyad neredeyse her zaman 0.90+ verir. Somut sonuç: VL yönetmeni **hafif-yanlış** okursa (gerçek "Schneier" → VL "Schneider"), kalkan artık bunu yakalamıyor, VL'nin yanlış yazımını GEÇİRİYOR. Bu, "okunamadı > yanlış" kanununa ters bir sızıntı kanalı açar.

**Bağlamsal hafifletici (RED yerine KOŞULLU-ONAY sebebi):** Kalkan yalnızca VL'nin ZATEN okuduğu ismi geçirir/düşürür; korpustaki ismi cast/yönetmen'e YAZMAZ. Yani F-1 yeni bir kişi uydurmuyor — sadece VL'nin kendi yazım-hatasını yakalama şansını azaltıyor. Ayrıca doğrulama-modu recall-öncelikli olduğu için bu tasarım niyetiyle uyumlu.

**Öneri:** (a) Eşiği yönetmen için 0.88-0.90'a çekin (belgedeki 4 kurtarmanın hepsi — Chakhnazarov 0.86+, Schneider — bu bantta bile geçer; testte doğrulayın). VEYA (b) fuzzy'yi asimetrik yapın: **ilk-token (ön-ad) EXACT eşleşmeli**, yalnız soyadına fuzzy uygulansın — bu, "steven→steve", "michael→micheal" gibi ön-ad driftlerini kapatır ama gerçek OCR-soyad-bozulmasını (shakhnazarov→chakhnazarov) korur. Belgede iddia edilen "tek harf/digraf farkı" çoğunlukla soyadındadır.

### F-2 [DÜŞÜK-BİLGİ] — Manifest korpusu kalkanı gerçekten genişletiyor; net etki "daha az düşürme"
`_pipe_credit_vl.py:127-138`. Doğruladım: manifest korpusu yalnız `credit_lines` okuyor (`subtitle_lines` DEĞİL), ve `giris_jenerik_havuzu._classify_frame:214` altyazıyı çift-filtreliyor (SUB_FRAC=0.82 alt-bant + `is_credit_text_line`). **Altyazı sızıntısı YOK — bu iddia doğru.** Ancak manifest, ana-OCR korpusunda OLMAYAN satırlar ekler (Norton kurtarmasının amacı). Yan etki: kalkanın "uydurma = ham OCR'da yok" invaryantı zayıflar, çünkü korpus artık ana-OCR'ın görmediği kareleri de içeriyor. Bu **niyet-uyumlu** ama F-1 ile birleşince kalkan iki yönden birden gevşiyor. Kill-switch (`MITAS_VL_CORPUS_MANIFEST=0`) mevcut — kabul edilebilir.

### F-3 [DÜŞÜK] — Cross-line kuralı SAĞLAM; kandırma senaryosu başarısız oldu (olumlu bulgu)
`_cross_line_hit:187`. Adversarial test kurdum: iki farklı kişinin adları art arda pür-satır olarak dizildiğinde ("john howarth" vs korpusta "john carpenter"/"alan howarth" ayrı satırlarda) → **BLOCKED**. Sebep: her parça ardışık satırın TAMAMINA eşleşmeli; "howarth" ≠ "alan howarth" satırının tamamı. MANASLU-Frankenstein koruması gerçekten duruyor. Bu katman için endişe yok.

### F-4 [DÜŞÜK] — Router nötrlüğü iddiası DOĞRULANDI
`credit_severity_router.py`'nin `from_durum`/`_sig` (mitas_pipeline:2762-2783) taradığı TÜM substring'leri yeni A0 reason'ıyla karşılaştırdım: `"VL aday ismi (teyitsiz, insan baksın): ..."` router'ın hiçbir anahtar-kelimesiyle ("yönetmen okunamadı", "kimlik çelişki", "cast garble", "özet yok", "Latin-dışı", "karakter bozuk", "isim-QC", "afiş yok", "CAST_CAP_DUSEN" vb.) çakışmıyor. Ayrıca bu reason yalnız `_v4_yon` boşken (satır 2610) ekleniyor — film ZATEN "yönetmen okunamadı (KB-fill yok)" reason'ıyla AĞIR-YONETMEN kovasında; A0 ilave routing etkisi sıfır. **Karar-nötr iddia geçerli.** (Teorik kenar: VL aday ismi tesadüfen bir router-anahtarı içerirse çakışır — ama kişi adları bu Türkçe QC-cümlelerini içeremez; pratik risk yok.)

### F-5 [DÜŞÜK] — Fail-safe zinciri eksiksiz
Doğruladım: (a) `ocr_job` scoped korpus boş → tüm-işlere geri düşme (`_load_raw_ocr:113`). (b) manifest bozuk → sessiz geç, korpus eski haliyle kalır (137). (c) `_in_raw` raw yoksa `True` döner (kalkan atlanır, FAIL-SAFE:149). (d) A0 yüzeyleme `try/except` sarılı (2617/2622). (e) tüm yeni davranışlar env kill-switch'li ve default-ON, `=0` ile kapanır: `MITAS_VL_USE_GIRIS_POOL`, `MITAS_VL_CORPUS_MANIFEST`, `MITAS_VL_RAW_FUZZY`, `MITAS_VL_RAW_CROSSLINE`, `MITAS_VL_RAW_FUZZY_RATIO`. `MITAS_VL_RAW_FUZZY_RATIO` `ValueError` yakalıyor ama `""` boş-string'e `or 0.84` fallback'i var (172). Eski davranışa dönüş yolları tam.

### F-6 [ÇOK DÜŞÜK — perf] — `_in_raw` her çağrıda korpusu yeniden fold/split ediyor
`_fuzzy_line_hit`/`_cross_line_hit` her isim için 14k satırı yeniden tarıyor; ölçüm: ~0.8s/isim worst-case, film başına ~2-8s. VL-fallback zaten dakikalar süren gemma4 çağrısı olduğu için **ihmal edilebilir**. İstenirse `raw_lines`'ın fold+split hâli bir kez cache'lenip `_in_raw`'a geçirilebilir. Blocking değil.

### F-7 [ÇOK DÜŞÜK — kozmetik] — Giriş-havuz VL girişi çıkış-havuzdan farklı fail-safe stratejisi kullanıyor
`_find_frames:71-74`: giriş havuzu boşsa ham `frames/giris`'e düşülüyor; çıkış tarafı (76-80) düşmüyor. Yorumda bilinçli açıklanmış ("giriş recall-öncelikli, VL'nin değeri havuz-boş durumunda"). Tutarsızlık kasıtlı ve belgeli — bulgu değil, sadece not: bu, VL'nin footage-üstü karelerden okuma yapabilmesine izin verir (giriş havuzu boşken), ki bu da hayalet-riskini artırır. Kalkan hâlâ arkada duruyor, kabul edilebilir.

---

## ÖZET
- **Router nötrlüğü (C):** DOĞRULANDI — çakışma yok, karar-nötr. ✔
- **Cross-line güvenliği (B):** SAĞLAM — adversarial stacking başarısız oldu. ✔
- **Manifest çöp-sızması (B):** YOK — altyazı çift-filtreli. ✔
- **Fail-safe/kill-switch (D):** EKSİKSİZ. ✔
- **Fuzzy 0.84 zarfı (B):** TEK GERÇEK ZAYIFLIK — kalkanın yazım-hatası yakalama gücünü düşürüyor; F-1 önerisi (asimetrik ön-ad-exact VEYA eşik 0.88-0.90) uygulanmalı ya da bilinçli kabul edilmeli.

İncelenen dosyalar: `E:\MITAS\scripts\_pipe_credit_vl.py`, `E:\MITAS\scripts\mitas_pipeline.py`, `E:\MITAS\scripts\credit_severity_router.py`, `E:\MITAS\scripts\giris_jenerik_havuzu.py`.