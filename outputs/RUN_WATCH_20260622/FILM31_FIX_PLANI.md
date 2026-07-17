# Film #31 KEDİ GÖZÜ — BİRLEŞİK ONARIM PLANI (çekişmeli-doğrulanmış)
2026-06-22 · Kaynak: tasarım workflow'u (11 ajan) + 2 kör denetçi + 1 tarafsız uygulama-denetçisi.

## UYGULAMA DURUMU (2026-06-22)
**ADIM A+B (gözlem-katmanı) UYGULANDI** — flag `MITAS_QC_OTORITE_AUDIT` (default **OFF**), SIFIR-ROUTE, commit YOK (working-tree).
- `credit_qc_block.py`: `_audit_*` yardımcıları + `_compute_otorite_audit` + `raw_names_groundtruth` param + S12 gated blok + return'e `otorite_audit`. Bitişik-altdizi eşleme (FP-güvenli).
- `tek_film_kunye.py`: ham-OCR (`ocr_raw_all.txt`) groundtruth yükleme (yeni `_raw_gt`, `_raw_context` tuzağına dokunmaz) + qc_block'a geçir + `_DURUM`'a `qc_block_otorite_audit`.
- Sinyaller: `ocr_dropped` (okunan-düştü), `kb_floor_added` (okunmayan-eklendi), `fuzzy_dups` (yakın-yazım-çift), `ocr_authority_violation` (substitüsyon imzası).
- Doğrulama: py_compile OK · flag-OFF bayt-bayt invariant · KEDİ GÖZÜ imzası birebir (Parker düştü/Sarrazin uyduruldu/Hunnicutt meşru-refill hariç/Hazleton çift) · kalıcı test `scripts/credit_qc_otorite_audit_test.py` 16/16.
- Tarafsız denetim: sıfır-route + runtime-güvenlik GEÇTİ; token-küme→bitişik FP düzeltildi; 1 yanlış-alarm (PRODUCER_IDENTITY_GATE — aslında kullanıcının eşzamanlı edit'i, benim değil).
**BEKLEYEN:** C (ENFORCE→KONTROL routing) yalnız A/B ölçümünden sonra; ② recall (Parker geri) B+② ile; ③ producer dedup; ① en son.

## Çekirdek teşhis
PARKER+HUNNICUTT ham OCR'da DOĞRU okundu → `clean.py:61` tek-token frag-drop sildi → qc_block floor-fill telafi ederken (PARKER okunduğundan habersiz) yanlış kişiyi (SARRAZIN 0× OCR) ekledi + cap=8 PARKER'ı kesti → karar AutoFix. Dört suçlunun ortak paydası: **qc_block "ham OCR'da gerçekte ne okundu" bilgisine sahip değil.**

## ÇEKİŞMELİ DOĞRULAMANIN YAKLAŞIMI DEĞİŞTİREN BULGULARI
1. **①-clean naif fix TEHLİKELİ (canlı ölçüldü):** ardışık tek-token'ları birleştirip 13.04M-satır `mitas_people_index`'e doğrulatmak → 41 çiftin 10'u (%24) gerçek-isme çakışıyor ('will smith','john wayne','may day','art smith'). Bu UYDURMA OYUNCU = OCR-otorite kanununu fix'in KENDİSİ ihlal ediyor. dieg-gate koruması KÖR (tek-kelime altyazı frag'a gider, sentence'a değil). → yalnız w==3 trigram, ROLE/FUNC/DIALOG dışlamalı, run-içi, EN SON.
2. **ARCH-groundtruth ÜRETİM-KIRAN bug:** canlı yol `mitas_pipeline:1834` `--video-credits` geçirir → `tek_film_kunye:310` video_credits dalı `_raw_context`'in atandığı else-dalını (325) ATLAR → naif init NameError → except yutar → **qc_block TÜMÜYLE atlanır** (MITAS_QC_BLOCK otoritesi sessizce kaybolur). Init `if a.video_credits`'ten ÖNCE olmalı + video_credits dalında da clip'ten raw yüklenmeli yoksa groundtruth canlıda HEP boş.
3. **③ naif fuzzy = over-merge makinesi:** `name_close(0.80)` ASLAN↔ARSLAN, HANSON↔HANSEN, DEMIR↔DEMIREL hepsini birleştirir (Türk korpusunda en yaygın AYRI soyad çiftleri; kod-test 14/14). Güvenli çıkış: yalnız KB-eşleşen çiftte kanonikleştir (KB hakem); iki ham-OCR ismini birbirine eritme YASAK.
4. **② Parker'ı ANCAK IMDb principals onu içeriyorsa kurtarır.** 1969 filmi → principals çoğu top-credited birkaç kişi → PARKER içinde olmayabilir. Bu ÖLÇÜLMEDEN ① mi ② mi gerektiği bilinemez (B-testi belirleyici).
5. **④ güvenli fail-safe:** iki-aşama (AUDIT sinyal-only sıfır-route → ölçümden sonra ENFORCE). Ama `ocr_dropped` garble-filtresi güçlendirilmeli (`_looks_garble` leksikal-only, scramble'ı "gerçek-isim düştü" sanır) + tetikleme-oranı <%30 olmadan ENFORCE açılmaz.

## UYGULAMA SIRASI (risk artan; gözlem önce, müdahale sonra)
| # | Adım | Rol | Flag (default OFF) | Risk | A/B |
|---|---|---|---|---|---|
| A | **④-AUDIT** sinyal-only, sıfır-route | KALKAN/GÖZ | MITAS_QC_OTORITE_AUDIT | DÜŞÜK | 200+12 bozuk(KEDİ GÖZÜ)+50 temiz |
| B | **ARCH-groundtruth** ham-OCR kanalı | VERİ TEMELİ | MITAS_QC_RAW_GROUNDTRUTH | ORTA | KÜME-1 **--video-credits ile** |
| C | **④-ENFORCE** aç (A+B ölçümünden sonra) | KALKAN-AKTİF | MITAS_QC_OTORITE_ENFORCE | ORTA | A'nın seti + route; KEDİ GÖZÜ→KONTROL |
| D | **③-S8** yapımcı dedup (KB-hakem-only) | NOKTA-FIX | MITAS_QC_FUZZY_DEDUP | YÜKSEK | ≥50 over-merge tuzak, kişi-kaybı=0 |
| E | **②-floorfill** OCR-öncelik (minimal varyant) | TELAFİ | MITAS_QC_FLOORFILL_OCRGUARD | YÜKSEK | 50, 5 invariant; C olmadan canlıya GİRMEZ |
| F | **①-clean-recall** frag-rejoin | RECALL-KÖKÜ | MITAS_CLEAN_FRAG_REJOIN | YÜKSEK(en) | 50 ÖNCE-ÖLÇ garble-influx |

Mantık: önce görmeyi öğren (A) → doğru veriyle gör (B) → kalkanı aç (C) → ucuz noktaları düzelt (D) → telafiyi güvene al (E) → recall-köküne en son dokun (F).

## TEK-BAŞINA mı KOMBİNE mi (Parker kurtarma zinciri)
- Hiçbir fix tek-başına KEDİ GÖZÜ'nü tam çözmez.
- **Recall'ı GERÇEKTEN kurtar (PARKER cast'e geri):** ① şart (principals'ta yoksa) VEYA ② yeter (principals'ta varsa) → **B-testi belirler.**
- **Güvenliği GARANTİ et (yanlış AutoFix engelle):** ④-ENFORCE şart → ①/② başarısız olsa bile KEDİ GÖZÜ KONTROL'e düşer.
- **Minimum güvenli kombinasyon = A+B+C.** KEDİ GÖZÜ (ve ~189 benzer film) asla sessiz yanlış-AutoFix olmaz; recall kurtulmasa bile hata görünür olur.

## HEMEN GÜVENLE YAPILABİLİR (sıfır-route veya bug-önleme)
- A iskeleti (④-AUDIT sinyal hesabı) — karar değiştirmez.
- B-init-guard (`_raw_context=[]` video_credits dalından ÖNCE) — bu zaten bir NameError BUG-önleme.

## BELİRLEYİCİ ÖLÇÜM — CEVAPLANDI (kör denetçi A, deterministik repro)
**IMDb principals (otoriter_cast) ELEANOR PARKER'ı İÇERİYOR** — billing sırası:
`[1.Sarrazin, 2.Hunnicutt, 3.PARKER, 4.Tim Henry, 5.Naismith, 6.Leak, 7.Chiles, 8.Herron]`.
→ **SONUÇ: ARCH(B)+②(E) kombinasyonu KEDİ GÖZÜ'nü TAM kurtarır, EN RİSKLİ ①'e GEREK YOK.**
Mekanizma: ARCH ham-OCR isim-kümesini ({PARKER, HUNNICUTT, +6}) qc_block'a verir; ② floor-fill'i
billing'i gezerken "hem otoriter_cast'te HEM ham-OCR'da olan" isimleri (PARKER, HUNNICUTT) "yalnız
KB'de olan"a (SARRAZIN, 0× OCR) ÖNCELİKLER. 6 OCR + PARKER + HUNNICUTT = 8 → cap dolar, SARRAZIN
girmez. Net: PARKER geri, HUNNICUTT geri, SARRAZIN dışarı — kusursuz 8.
→ **① (clean frag-rejoin) yalnız ARTIK kalan sınıf için gerekir:** düşen başrol IMDb principals'ta
DA yoksa (gerçekten belirsiz/yerli-eski filmler). KEDİ GÖZÜ bu sınıfta DEĞİL. ① en sona ertelenebilir
veya tamamen opsiyonel kalabilir.

## EK DEFEKT (A buldu, kök-neden değil ama ayrı teslim-hatası)
**PDF (6 oyuncu) ile kök .txt (8 oyuncu) AYRIŞIYOR.** v4 yüzey .txt'yi `_patch_md_credits` ile
yamalıyor (`mitas_pipeline.py:259-273`) ama `kunye_teslim.md`/PDF'i yeniden render ETMİYOR → aynı
filmin PDF'i ve .txt'i farklı kadro gösteriyor. "v4-render vs yüzey .txt EZME" deseninin ters yönü
(txt zenginleşmiş, PDF eski). `qwen_qc.oyuncu_sayisi:7` bu ara-durumun yansıması.

Kanıt-dosyaları: `OCR-worktree/py/20260601_clean.py:61`, `scripts/credit_qc_block.py:440,562-593`, `scripts/credit_severity_router.py:91-117`, `scripts/credit_crosscheck.py:158-208`, `scripts/tek_film_kunye.py:310-330,614-628`, `scripts/mitas_pipeline.py:1834,2090-2104`.
