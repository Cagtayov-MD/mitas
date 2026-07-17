# ŞERİF SHAUGNESSY (Shaughnessy, 1996 ABD/CBS) — 10-Boyut Denetim

**TRT:** 1996-0177-1-0000-00-1 · **Karar:** KONTROL/YONETMEN_RENDER
**Tip:** cast=8 DOLU ama yön+yapımcı YOK; afiş+özet var; OCR GUVENILIR 132 satır
**Hub:** `Database\ŞERİF SHAUGNESSY 1996-0177-1-0000-00-1`

## 10 Boyut
| # | Boyut | Hüküm | Özet |
|---|---|---|---|
| 1 | Jenerik | ✅ DOĞRU | Giriş 360 + çıkış 150 kare gerçek jenerik. Pencere doğru. |
| 2 | İsim-kurtarma + master-png | ✅ | master-png 600×4441, okunabilir, salt-görsel (additive=0 teyit). |
| 3 | Gemma/VL | ⚠️ **VL TIMEOUT** | gemma4-VL 180s timeout → gemma_kunye.json YAZILMADI. 20 kart (card_0000=8KB boş dahil) + 600×480 düşük çöz. Halüsinasyon yok. |
| 4 | QC1 | ✅ DOĞRU | yön boş → RED → VL de bulamadı → KONTROL. Doğru. |
| 5 | QC2/RENDER | ⚠️ YANLIŞ-POZİTİF | Tek 'ا' (U+0627, prop/tabela yazısı) → nonlatin_source → RENDER. qwen_qc latin_disi=False. |
| 6 | Routing | ✅ DOĞRU | YONETMEN gerçek defekt → KONTROL doğru. RENDER eki zararsız. |
| 7 | Cast/yön/yapımcı | ⚠️ KAYNAK-EKSİK | Yön/yapımcı çıkış jeneriğinde YOK (muhtemelen giriş jeneriğinde). cast=8 temiz. |
| 8 | Tür/afiş/özet/orijinal | ❌/⚠️ | TÜR bug 4/4. Orijinal-ad eksik (+TRT'de "SHAUGNESSY" yanlış, doğru "SHAUGHNESSY"). Afiş kaynaksız. Özet makul. |
| 9 | PDF sadakat | ⚠️ **GARBLE SIZINTISI** | garble_frac=0.0 ama kunye.txt'ye 3 garble sızmış (SPODNETION RSOCIAT..., BKEANLVE ASSISTANTS, NADRY BRADBARN). Cast sadık. |
| 10 | KB (IMDb/Wiki) | ⚠️ **kb_floor UYDURMA RİSKİ** | kb_floor_added 2 oyuncu (Sarah Paulson, Michael Jai White) OCR'da OKUNMADAN eklendi; ocr_authority_violation=false. |

## YENİ bulgular (bu filmden)
- **VL timeout**: boş/küçük kartlar (card_0000=8KB) + düşük çözünürlük → gemma4-VL 180s'de tamamlayamıyor, çıktı yazılmıyor. Öneri: boş kart (<N KB) filtrele, kart sayısını azalt.
- **kb_floor OCR-otorite gerilimi**: kimlik kilitliyken (cast-örtüşme≥2) KB eksik koltukları dolduruyor — ama eklenen oyuncular OCR'da YOK ve `ocr_authority_violation=false` sayılıyor. "kb_only_cast" bayrağı + insan onayı yok. (OCR-otorite KANUNU ile gerilim.)
- **Yön/yapımcı giriş jeneriğinde**: çıkış jeneriğinde "Directed by" yok; giriş jeneriği OCR'a tam giriyor mu sorusu (S11).
- **garble kunye.txt'ye sızıyor** (sadece metrik değil): garble dedektörü "Production Associates" tipi kısmen-okunan satırları sağlıklı sayıyor.
