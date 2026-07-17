# MITAS Koşu Denetimi + Fix — Final Rapor (2026-06-28/29)

Canlı koşu (W:\23.05 → 231 film). Her tamamlanan film 10-boyut (Sonnet ajan) tarandı; bulgular fix'lendi + canlı teyit edildi.

## Denetlenen filmler (derin, 10-ajan)
1. BEKARLIK SULTANLIKTIR (1958) — jeneriksiz/okunaksız, KONTROL
2. SUÇ MEVSİMİ (1985 ABD) — SAĞLIKLI künye, RENDER yanlış-pozitif → KONTROL
3. ŞERİF SHAUGNESSY (1996 ABD) — cast dolu, yön/yapımcı yok + RENDER

---

## 🔑 KRİTİK METODOLOJİ DÜZELTMESİ
Ajanlar PDF'i açamadığı (pdftoppm yok) için **ara dosyalara** (kunye_teslim.md, _DURUM.json) bakıp **3 yanlış-alarm** verdi. PDF önizlemesi (kunye_onizleme.png) görsel açılınca gerçek ortaya çıktı:
- **TÜR**: ara md'de `—` ama asıl PDF'de DOLU ("SUÇ/GERİLİM", "DRAM/WESTERN") ✅
- **Orijinal-ad**: ara md'de yok ama PDF'de VAR ("THE MEAN SEASON") ✅
- **Garble**: kunye.txt'de var ama final teslim cast'inde YOK (extraction eledi) ✅

**Asıl teslim (PDF + kök .txt) büyük ölçüde doğruydu.** Tek yüksek-etkili gerçek bug: RENDER yanlış-pozitif.

---

## ✅ FIX DURUMU

### P1 — RENDER yanlış-pozitif [ÇÖZÜLDÜ + CANLI TEYİT]
**Sorun:** `detect_script()` oransız — ham OCR'daki TEK latin-dışı karakter (TRT-logo→'西', prop→'ا') tamamen Latin filmi "latin-dışı kaynak" sanıp haksız KONTROL/RENDER'a yolluyordu.
**Fix:** `credit_text_read.py` — `_nonlatin_ratio()` + oran eşiği (`MITAS_NONLATIN_MIN_RATIO=0.02`). Tek-tük gürültü (<%2) RENDER tetiklemez; gerçek latin-dışı (≥%2) korunur.
**CANLI TEYİT (6 veri noktası):**
| Tip | Film | nonlatin | Sonuç |
|---|---|---|---|
| Gürültü→engellendi | SUÇ MEVSİMİ | %0.001 | ✅ ONAYLI olur |
| Gürültü→engellendi | ŞERİF | %0.012 | ✅ RENDER kalktı |
| Gürültü→engellendi | ARKADAŞIM BERNARD | %0.046 | ✅ TEMIZ |
| Gürültü→engellendi | İKİMİZİN HİKAYESİ | %0.00002 | ✅ sadece YONETMEN |
| Gerçek→korundu | SİHİRLİ KEDİ | %93.8 (CJK) | ✅ RENDER doğru |
| Gerçek→korundu | KUTSAL SİLAH | %71.6 (Hangul) | ✅ RENDER doğru |

### P2 + P5 — TÜR + orijinal-ad _DURUM'a geçmiyor [ÇÖZÜLDÜ]
**Sorun:** Teslim PDF/kök-txt doğruydu ama `mitas_pipeline.py summary_obj`'de `tur`/`orijinal_ad` alanları yoktu → `_DURUM.json` boş → QC/denetim ara-dosyaya bakınca "eksik" sanıyordu.
**Fix:** `summary_obj["tur"]=tur_final`, `["orijinal_ad"]=original`. _DURUM artık teslimle hizalı.

### P3 — Garble metrik [DÜŞÜK ÖNCELİK — teslimi etkilemiyor]
garble teslime sızmıyor (extraction eliyor); `garble_frac=0.0` metriği kör ama teslim temiz. Önleyici dedektör güçlendirme opsiyonel.

### P4 — kb_floor OCR'sız oyuncu ekliyor [KULLANICI KARARI BEKLİYOR]
ŞERİF: Sarah Paulson + M.J.White OCR'da yok, KB ekledi (PDF'de var). Memory'deki "künye geniş kapsam doldurma istiyorum" talimatıyla örtüşüyor (muhtemelen istenen tasarım). `kb_floor_added` _DURUM'da görünür. Seçenekler: olduğu gibi / güvenlik eşiği / teslimde işaretle.

### P6 — VL timeout [DÜŞÜK ÖNCELİK — üretimi etkilemiyor]
shadow-VL (jenerik_debug, salt-debug) timeout; üretim VL fallback ayrı çalışıyor. Boş kart filtresi opsiyonel.

---

## ✅ AYRICA DÜZELTİLEN
### reused-skip clip_id mismatch [CANLI FIX — restart bekliyor]
`asr_server.py` `_find_processed_hub()` (TRT-id). Backend restart edilince aktif (asr_server restart ister; pipeline script fix'leri her film subprocess olduğu için zaten canlı).

---

## DOĞRU ÇALIŞAN (tutarlı)
Jenerik tespiti, QC1 (sağlıklıya PASS/eksiğe RED), routing, PDF cast sadakati (uydurma/ezilme yok), master-png görsel üretimi, özet (ASR-kaynaklı), AUTOFIX (hafif afiş otomatik düzeltme).

## NOTLAR
- Pipeline kod fix'leri (P1/P2/P5) her film yeni `mitas_pipeline` subprocess'i olduğu için **sonraki filmlerde otomatik aktif** (restart gerekmez). 06-29 02:18 itibariyle fix sonrası filmler doğru işleniyor.
- Fix-öncesi KONTROL'e haksız düşen filmler (SUÇ MEVSİMİ, SİHİR vb.) istenirse yeniden işlenip ONAYLI'ya alınabilir (ayrı aksiyon).
