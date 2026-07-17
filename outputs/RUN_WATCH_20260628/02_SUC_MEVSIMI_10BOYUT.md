# SUÇ MEVSİMİ (The Mean Season, 1985 ABD) — 10-Boyut Denetim

**TRT:** 1985-0221-1-0000-40-1 · **Karar:** KONTROL/RENDER
**Tip:** SAĞLIKLI künye (cast=8, yön/yapımcı/afiş/özet ✅, OCR GUVENILIR 198 satır) — RENDER yüzünden KONTROL
**Hub:** `Database\SUÇ MEVSİMİ 1985-0221-1-0000-40-1`

## 10 Boyut

| # | Boyut | Hüküm | Özet |
|---|---|---|---|
| 1 | Jenerik | ✅ SAĞLIKLI | Giriş 360 + çıkış 411 kare gerçek jenerik. Küçük: cikis_jenerik'e preroll c_0070-71 off-by-one (zararsız). |
| 2 | İsim-kurtarma + master-png | ✅/⚠️ | master-png 600×6398px, %97 okunabilir, üst %2-3 footage (kabul). **master_png OCR'a beslenmiyor** (`master_png:null`, additive=0 → SALT GÖRSEL). garble_frac=0.0 ama gerçekte 2-3 garble (DINECTOR, FRANK TSE) var. |
| 3 | Gemma/VL | ✅ | Cast OCR'dan (GLM disabled, VL salt-debug, üretime katkı 0). Halüsinasyon yok. GLM-OCR card prompt-sızması döngüsü (guard temizledi). |
| 4 | QC1 | ✅ DOĞRU | Tetiklenmedi (cast=8≥3, yön var) = implicit PASS. Sağlıklı künyeyi VL'e atmadı. |
| 5 | QC2 | ⚠️ YANLIŞ-POZİTİF | RENDER, ham OCR'daki TEK '西' (U+897F, TRT-logo gürültüsü) yüzünden tetiklendi. qwen_qc latin_disi=FALSE (PDF temiz) — iki katman tutarsız. |
| 6 | Routing | ⚠️ | Teknik doğru ama RENDER yanlış-pozitif → sağlıklı film gereksiz KONTROL. ONAYLI olmalıydı. |
| 7 | Cast/yön/yapımcı | ⚠️ KAYIP | **ROSE PORTILLO (Kathy Vasquez) OCR'da 9+ kez var, PDF'e girmemiş** → cast 8 değil 9 olmalı. Yön+yapımcı doğru. |
| 8 | Tür/afiş/özet/orijinal | ❌/✅ | **TÜR kök-neden bulundu** (aşağıda). **Orijinal-ad eksik** (The Mean Season yazılmıyor). Afiş+özet ✅. |
| 9 | PDF sadakat | ✅ SADIK | Ezilme/uydurma/sızıntı YOK. Garble PDF'e sızmadı. RENDER yanlış-pozitif (detect_script oran eşiği yok). |
| 10 | KB (IMDb/Wiki) | ⚠️ BOŞ DÖNDÜ | Çağrıldı ama "SUÇ MEVSİMİ"↔"The Mean Season" eşleşemedi → kimlik kilidi yok. |

## KRİTİK: TÜR bug — KESİN kök-neden
- `clip.json: tur="OYUNCULU DRAMA"` (dolu) → `_DURUM.json`: **tur anahtarı YOK** → `kunye_teslim.md: Tür: —`
- **Kök-neden:** `mitas_pipeline.py` `summary_obj` (~satır 2476-2488) `"tur"` alanını içermiyor → `_DURUM.json`'a tür hiç yazılmıyor. Ayrıca jenerik_debug bloğu (~2570) `_DURUM.json`'ı summary_obj ile yeniden yazıp tür'ü siliyor.
- **Fix (öneri, ~2 satır):** `summary_obj`'e `"tur": tur_final` + `"orijinal_ad": original` ekle.

## Sağlıklı filmde bile çıkan sistemik sorunlar
1. **TÜR kaybı** (summary_obj eksik) — net fix
2. **RENDER yanlış-pozitif** (detect_script oran eşiği yok; tek latin-dışı gürültü tüm filmi KONTROL'e atıyor)
3. **Cast kaybı** (karakter-rol "Kathy Vasquez ROSE PORTILLO" formatından oyuncu çekilemiyor)
4. **Orijinal-ad kaybı** (summary_obj eksik + ana_dil=TR subtitle gizleme)
5. **master-png salt-görsel** (OCR additive katkı 0)
6. **TR↔EN başlık eşleşmesi yok** (KB kimlik kilidi yabancı filmde kurulamıyor)
7. **garble_frac=0.0 yanlış** (garble dedektörü bilindik OCR hatalarını kaçırıyor)
