# BEKARLIK SULTANLIKTIR — 10-Boyut Denetim (İlk Tur / Şablon)

**TRT:** 1958-0046-1-0000-00-1 · **Karar:** KONTROL (YONETMEN_KIMLIK_CAST)
**Tip:** 1958, jenerik metni okunaksız/yok kopya (atipik forensik vaka)
**Hub:** `Database\BEKARLIK SULTANLIKTIR 1958-0046-1-0000-00-1`

## Ölçülen durum
OCR bucket=GOZDEN_GECIR, **ocr_lines=1** (`IOSAWIS IWAIRAM` garble), cast=0, yönetmen YOK, yapımcı YOK, afiş YOK, özet VAR, ASR done (2037 seg). QC1 RED → gemma4-VL fallback (248s) → yine RED → KONTROL.

## 10 Boyut Bulguları

| # | Boyut | Hüküm | Özet |
|---|-------|-------|------|
| 1 | Jenerik tespit | **KISMEN/SORUN** | Giriş 46-92s kabul ama kareler düz sahne (yazı yok). Çıkış 4950-4967s kabul ama `cikis`'te 1 kare (siyah) → pool boş. |
| 2 | İsim-kurtarma + master-png | **HATALI (isim) / DOĞRU-atlanma (master)** | OCR 1 garble satır; GLM+Paddle disabled. master-png `no_frames` (havuz boş) — bu film için doğru. |
| 3 | Gemma/VL eşleştirme | **DOĞRU** | `gemma_kunye.json status=no_frames` (havuz boş). Halüsinasyon YOK. VL boş döndü, doğru. |
| 4 | QC1 | **DOĞRU** | `_vl_need=(not yön) or (cast<3)` → RED doğru. Risk: cast<3 eşiği küçük-kadro filmde yanlış-pozitif. |
| 5 | QC2 | **DOĞRU (hafif kör nokta)** | credit_qc_block S0-S12 düzeltme+etiket. 3 AĞIR sinyal doğru. Kör nokta: ses_dil karar matrisine bağlı değil. |
| 6 | Çıktı routing | **DOĞRU** | KONTROL + `_YONETMEN_KIMLIK_CAST` ad doğru. ONAYLI'da 4 ESKİ elle-onaylı PDF (router öncesi). |
| 7 | Cast/yön/yapımcı eksik | **KAYNAK-KALİTE+OCR-TEKNİK** | 840 kareden tek okunan = tabela yansıması. Jenerik filme overlay/düşük kontrast. KB-fill tetiklenmedi. |
| 8 | Afiş/tür/özet/orijinal-ad | **AFİŞ=kaynak / TÜR=BUG / ÖZET=sağlam / ORİJİNAL=tasarım** | Afiş: kimlik yok→poster_fetch çağrılmadı. **TÜR: clip.json=DRAMA ama md=—**. Özet ASR'dan, gerçek. |
| 9 | PDF OCR-sadakat | **SADIK (ezilme/uydurma YOK)** | Garble filtresi çalıştı (IOSAWIS PDF'e sızmadı). Özet ASR-kaynaklı (tasarım). TÜR md/txt tutarsız. |
| 10 | Wiki/IMDb (KB) | **KB GİRDİ-BOŞ** | KB cross-check çağrıldı (imdb+wiki boş döndü). cast=0 → eşleşecek isim yok → kilit imkansız. "Doldurmaz, doğrular". |

## Sistemik Şüpheler (tek-film, doğrulanacak)

### A. TÜR veri-kaybı — GERÇEK ADAY BUG
`clip.json: tur=DRAMA` → `kunye_teslim.md: Tür: —`. Kod `mitas_pipeline.py:2078 tur_final=tur_xml` ile DRAMA'yı taşımalı. md'ye ulaşmıyor. **Asıl kunye.pdf'de de boş mu?** Sağlıklı filmde teyit edilecek. Yaygınsa yüksek öncelik.

### B. Master-PNG — iki yol, netleştirilecek
- `_pipe_ocr.py:764` `MITAS_MASTER_PNG` **default KAPALI** (compose_hybrid + additive-OCR yolu).
- `jenerik_debug/master_png/` (jenerik_parallel_debug→run_master_debug) **CANLI**; bu filmde `no_frames` (çıkış havuzu boş).
- **Doğrulanacak:** Çıkış jeneriği OLAN sağlıklı filmde master-png gerçekten üretiliyor mu, nerede (`stitch/` mi `jenerik_debug/master_png/` mi)?

### C. cikis_fb havuza beslenmiyor
Pool girdi olarak `cikis` (1 kare) kullanılıyor, `cikis_fb` (480 kare) değil. Bu filmde çıkış jeneriği gerçekten yok ama kod davranışı şüpheli. Çıkış jeneriği olan filmde test edilecek.

## Diğer öneriler (ajanlardan)
- QC1 cast<3 eşiği → cast<2/cast==0 (eski küçük-kadro filmler için yanlış-pozitif azaltır).
- ONAYLI'daki 4 eski `_onaylı.pdf` yeni router kriterleriyle yeniden doğrulanmalı.
- Eski Türk/yabancı filmler için: TRT-XML rol verisi KB-fill kanalı (OCR boşken), Türk-film KB genişletme (1950-70 Wikidata zayıf), title-only zayıf-kilit + insan-onay notu.

---
*Şablon doğrulandı: 10 boyut da kanıt-temelli çalıştı. Sonraki turlar film-grubu bazında.*
