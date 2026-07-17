# YAPILACAKLAR — Künye QC Bloğu (demir-atma 2026-06-20)

**Durum:** credit_qc_block CANLI (`MITAS_QC_BLOCK=1`). Commit'ler: `8ece9fffd8`, `40744f5029`, `f8c67de05e`, `1d1697ca9b`. 19/19 test.

---

## A. DEVREYE ALMA / DOĞRULAMA  *(önce bunlar — yoksa hiçbiri canlıda görünmez)*

- [ ] **A1. ASR server restart** — env değişiklikleri (`MITAS_QC_BLOCK=1`, `MITAS_SES_DIL_KONTROL=0`) canlıya yansısın. `scripts\start_mitas.ps1` çalıştır. *(operasyonel, kısa)*
- [ ] **A2. Uçtan-uca production doğrulaması** — gerçek bir batch'i TAM pipeline'dan (mitas_pipeline → tek_film_kunye) geçir, qc_block standalone DEĞİL. ONAYLI/KONTROL dağılımını + 5-10 örnek PDF'i gözle kontrol et (alan-doldurma + ses-kanalı yok + dublaj-rol yok).

## B. ONAY ORANI — en yüksek kaldıraç

- [ ] **B1. RE-RENDER BATCH** *(en yüksek ROI)* — mevcut 886 filme yeni fix'leri uygula. Fix'ler (qc_block override, dublaj-rol, ses-dil) yalnız YENİ-işleme/re-render'da görünür; mevcut .txt/.pdf'ler hâlâ eski-bozuk. Onay-oranı sıçraması ASIL burada. Batch tool yazılmalı (re-render, OCR'ı yeniden koşmadan mevcut OCR ham'ından).
- [ ] **B2. Director-anchor PERF** — kilitsiz-film başına indekssiz `principals`(98M) sorgusu yavaş. Çözüm: `principals(nconst)` indeksi VEYA `MITAS_QC_DIRECTOR_ANCHOR` flag (default açık, kapatılabilir). Production-batch öncesi şart.
- [ ] **B3. 289 tam rescue ölçümü** — `python outputs/qc_block_rescue_measure.py 289` (durdu, ~%28-31'de oturmuştu). Kesin kurtarma sayısı + kategori kırılımı. *(düşük öncelik — oran zaten oturdu)*
- [ ] **B4. OCR cast recall** *(büyük iş, ayrı)* — kilitlenemeyen ~%55'in çoğu cast okunamadığı için (recall-tavanı ~%47). Frame-seçimi/OCR iyileştirmesi → kilit oranı → onay oranı. En büyük ama en pahalı kaldıraç.

## C. ROL-ATFI / TEMİZLİK  *(OCR-okuma katmanı — credit_text_read)*

- [ ] **C1. Rol-etiketi sızması (dublaj-DIŞI)** — "ASISTENTES DE PRODUCCION" (yapım asistanları), crew üyeleri, garble-oyuncu adları hâlâ yönetmen alanına sızıyor (ACI ÇİKOLATA, ALTINCI ADAM, AMELIA). Dublaj-fix (`_drop_dubbing_directors`) gibi deterministik genişlet. *(NOT: bu katmanı Çağatay kendisi ele almayı düşünüyordu — koordine et.)*
- [ ] **C2. Garble-isim filtresi** — "MIL R SWA K" (=garble Hilary Swank) tipi bozuk okumalar isim alanlarına girmesin.

## D. DOĞRULAMA / İZLEME

- [ ] **D1. Misread bulucu — tam 886** — `outputs/yanlis_okuma_bul.py` 886'da koş (yavaş; gece batch). Tam yanlış-okuma + OKUNAMADI + CAST-GARBLE envanteri. *(bu oturumda yalnız "A" filmleri tarandı, timeout)*
- [ ] **D2. Same-title yanlış-kilit kontrolü** — cast-lock yanlış filme kilitlenip OCR-DOĞRU-yönetmeni "yanlış" gösteriyor olabilir mi? Misread "yanlış-yön" vakalarının web-teyidi (3.GÖZ gerçek çıktı, ama hepsini doğrula). `feedback_yonetmen_kimlik_capasi` riski.
- [ ] **D3. cast_kesişim 0 (88 film)** — XML-cast vs OCR-cast örtüşme 0; yanlış-film mi yoksa cast-okunamadı mı, ayır.

## E. KULLANICININ KENDİ ALANI

- [ ] **E1. Özet motoru** — ~261 özet-gate'li film (Çağatay ele alacak). qc_block özet kapısını KORUYOR (placeholder/<20 kelime → KONTROL/OZET); özet gelince doğru-yönetmenle ONAYLI olur.

---

### Sıra önerisi: A1 → A2 → B2 → B1 → (C1 ile koordine) → D1 → B3/B4
