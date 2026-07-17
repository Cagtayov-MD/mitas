# MITAS Panel-Fix Uygulama Raporu (gece otonom)

**Tarih:** 2026-06-23 · **Mod:** otonom (Opus tasarımcı + Opus/Sonnet adversarial doğrulayıcı) · **Commit:** YOK (working tree, geri-alınabilir)

## Amaç
Tarafsız Opus panelinin (B+ / 7.4) bulgularını güvenli/additive/flag-kapılı düzelt; smoke + adversarial doğrula; commit etme. İlke: hiçbir düzeltme başka şeyi bozmasın; riskli olanı beklet.

## Uygulanan fix'ler (4) — hepsi adversarial-doğrulama: SAGLAM

| Fix | Ne | Dosya | Risk | Durum |
|---|---|---|---|---|
| **FIX-A** | Config-to-code: üretim flag seti `os.environ.setdefault` ile koda taşındı (QC_BLOCK/CREDIT_DETECT/GEMMA_FULLCOVER/OTORITE_AUDIT/FLOORFILL… bare-run'da ON). Kill-switch `MITAS_PROD_DEFAULTS=0`. Config parmak-izi `system_events`'e loglanır. A/B-bekleyen flag'ler HARİÇ. | mitas_pipeline.py | DÜŞÜK | ✅ E2E KANITLI (bare run → `QC_BLOCK=1 source=default`) |
| **FIX-B** | OCR-otorite ihlali (`ocr_authority_violation`: okunan başrol düştü + okunmayan eklendi = KEDİ GÖZÜ imzası) → KONTROL (additive reason). Flag `MITAS_QC_OTORITE_ROUTE` default-ON. Reason'a hangi isim düştü/eklendi gömülü (auditability). | mitas_pipeline.py + start_mitas.ps1 | DÜŞÜK | ✅ wiring canlı doğrulandı |
| **FIX-C** | `nonlatin_source`/`translit_method` propagasyonu: `_pipe_credit_text` out-dict'inde DROP ediliyordu → eklendi. Latin-dışı doğrulanmamış romanize künye artık ONAYLI yerine KONTROL'e. | _pipe_credit_text.py (+yeni test) | DÜŞÜK | ✅ uçtan-uca doğrulandı |
| **FIX-D** | PDF-render (S5 fuzzy-snap, LEFEBVRE→LEFEVRE) form-ezme **GÖZLEM** sinyali (`otorite_audit.s5_form_overwrites` + `_confirmed`). Flag `MITAS_PDF_RENDER_AUDIT` default-ON. **Route YOK** (FP riski → A/B sonrası). | credit_qc_block.py | DÜŞÜK (saf gözlem) | ✅ davranış değişmiyor |

**Ek (auditability/safety-net):** FIX-B reason'a kanıt-isim gömme · flag-drift notu (`_pipe_ocr.py` GLM_CONSENSUS kod-default farkı) · CI: edit edilen credit dosyalarına py_compile + 10 credit testi pytest-kapısına (lazy-duckdb → CI-güvenli doğrulandı).

## Smoke test sonuçları (hepsi YEŞİL)
- py_compile: mitas_pipeline / credit_qc_block / _pipe_credit_text → OK
- FIX-A birim: PASS (setdefault + override-korur + A/B-flag sızmıyor)
- Credit suite (panel 55) + cf66458390 fix testleri (c1/c2/c4/c5) + nonlatin: **85/85 PASS**
- Otorite-audit standalone: **TUMU PASS** (s5 param geri-uyumlu)
- OCR suite: **156 passed, 1 skipped**
- test_credit_crew_leak_gate (CI'a eklenen): 4/4 PASS
- ci.yml: geçerli YAML
- **E2E (çıplak --no-asr, hiç flag yok):** config-event `QC_BLOCK=1/default`, `OTORITE_ROUTE=1/default`, `CREDIT_DETECT/GEMMA=1` → FIX-A pratikte çalışıyor

## Ertelenenler (adversarial-kritik gerekçeli DEFER)
- **#7 kimlik-eşik hizalama (≥2 vs ≥3): YAPILMADI — panel yanılmış.** Eleştirmen kanıtladı: bunlar aynı karar için farklı eşik değil, **farklı-yarıçaplı AYRI kapılar** (film-kilidi ≥3 zaten üstte; tek_film_kunye ≥2 yalnız düşük-riskli yazım-düzeltme açar). Hizalama gereksiz + regresyon-riskli.
- **#5 PDF-render route:** GÖZLEM yapıldı (FIX-D); KONTROL'e route ERTELENDİ — KB kanonik-yazım çoğu zaman DOĞRU düzeltme (LEFEVRE IMDb-doğru olabilir); route açmak doğru-düzeltmeleri KONTROL'e boğar. 50-100 film gözlem verisi sonrası karar.
- **#6 garble saf-scramble route:** GÖZLEM zaten ON (`GARBLE_NGRAM=1`); ROUTE ERTELENDİ — n-gram eşiği Bati-Latin eğitimli, Türkçe/nadir gerçek-isimde yüksek FP (memory: "naif garble-gate gerçek-isim düşürür = bug'dan kötü"). Kalibrasyon şart.
- **Bayat-artefakt export temizliği:** silme onay-bekler, davranış-dışı → Çağatay'ın karantina rutinine bırakıldı.

## Öz-eleştiri (daha iyisini yapabilir miydim?)
1. **Tasarım ajanları salt-okuma olmalıydı:** biri FIX-C'yi kendiliğinden uyguladı (doğru çıktı ama kontrolsüz). Ders: tasarım fazında Explore/read-only ajan kullan.
2. **GEMMA_FULLCOVER default-ON, bare-run'a ~+2.5dk/film ekler** — üretimle eşitlenme istenen ama hızlı-debug için sürpriz maliyet; config-event ile görünür kılındı.
3. **Merkezî config modülü (panel önerisi) yerine setdefault-in-main seçtim** — daha minimal, eşit etkili, daha az refactor-riski; gece-değişikliği için doğru tercih.
4. **#7'yi körü körüne uygulamadım** — adversarial kritik panelin hatasını yakaladı; bu, çok-katman doğrulamanın değerini gösterdi.

## Geri alma
Commit yok. Geri almak için: `git checkout scripts/mitas_pipeline.py scripts/credit_qc_block.py scripts/_pipe_credit_text.py scripts/start_mitas.ps1 .github/workflows/ci.yml` + `rm tests/test_nonlatin_source_propagation_20260623.py`. Veya tek-flag: `MITAS_PROD_DEFAULTS=0` (FIX-A katmanını kapatır).
