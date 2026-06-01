# SlitScan + PhaseCorrelation — Çalışma Prensipleri (B yaklaşımı, kıyas için)

> **Amaç:** `boxtracking/` ile AYNI hedef — jeneriği (statik / stabil-akan /
> karma, BG sabit/hareketli) **tek okunaklı panorama PNG'ye** çıkarmak.
> Fark: bu modül akan içeriği **slit-scan (pushbroom) mozaikleme** ile diker ve
> kaymayı **faz-korelasyonu** ile ölçer. Bu, Çağatay'ın BoxMotionTrack çekirdeğinin
> (takip→dik, sınıf yok, faz-agnostik) literatürde kanıtlı, kırmızı-zemine dayanıklı,
> hayaletsiz (ghost-free) varyantıdır.
>
> **Bu bir KIYAS POC'u.** `boxtracking/` (A yaklaşımı, box-içi LK takip) ayrı bir
> Sonnet tarafından kuruluyor. İki yaklaşım AYNI test setinde, AYNI çıktı formatında
> koşulup karşılaştırılacak. **`boxtracking/` klasörüne ve mevcut pipeline dosyalarına
> DOKUNMA** — sen yalnız bu `slitscan/` klasöründe çalış.

---

## 1. Neden bu yaklaşım (literatür)
- **Slit-scan / pushbroom mozaikleme** (Peleg, Hebrew Univ — Crossed-Slits, Rectified Mosaicing): akan içeriği tek görsele çevirmenin klasik yolu. Her kareden sabit konumdaki ince bir **şerit (slit)** alıp kümülatif ofsette dizersin — tarayıcı/finiş-fotoğrafı gibi. Bindirme harmanı YOK → **hayalet (ghosting) yok.**
- **Faz-korelasyonu** (cv2.phaseCorrelate): kareler-arası dikey kaymayı alt-piksel, **dokusuz/düz zeminde bile** (SON METRO kırmızı!) sağlam ölçer — feature-tabanlı LK'dan üstün. Mevcut `text_layer_row_reconstruct` LK-stitch'inin kırmızıda çökmesinin panzehiri budur.

## 2. Çekirdek ilke (Çağatay — değişmedi)
Box durursa kart, kayarsa panorama, faz değiştirirse aynı akışta sürdür. Sınıflandırma
adımı yok. Burada "kaymayı ölçmek" işini faz-korelasyon, "dikmeyi" slit-scan yapar.

## 3. Üç tip = tek motor
- **STATİK** (dy≈0): o duruşun en net karesini blok olarak ekle.
- **STABİL** (dy>0 kararlı): slit-scan ile diken.
- **STABİL/STATİK** (dy 0↔pozitif geçer): aynı akışta sürdür, faz ayırma yok.

## 4. Algoritma (kare-kare)
1. **Kayma ölç (faz-korelasyon):** Ardışık kareler `I[t-1], I[t]` arasında
   `cv2.phaseCorrelate` (Hanning pencereli, grayscale) → `(dx, dy)` + tepe gücü (response).
   Jenerikte dx≈0 beklenir; dy = dikey kayma. Alt-piksel.
2. **Faz kararı:** `|dy| < STATIC_EPS` (öneri ~0.5px) → statik; aksi → akan.
3. **Slit-scan dikiş (akan):** `kümülatif_ofset += dy`. Her kareden ekranın **sabit
   referans bandından** (metnin en net olduğu orta bölge; bant kalınlığı ≈ |dy| veya
   küçük sabit) bir şerit al, panorama tuvaline `kümülatif_ofset` konumuna yapıştır.
   Sabit hızlı scroll'da bu **boşluksuz, bindirmesiz** tam rekonstrüksiyon verir.
4. **Statik faz:** dy≈0 sürerken o duruşun en keskin karesini blok olarak ekle; kayma
   başlayınca slit-scan'e dön ("durursa da kesmeyiz").
5. **Cut/dissolve → bölüm sınırı:** faz-korelasyon **tepe gücü düşükse** VEYA ardışık
   kare **global farkı yüksekse** → sahne kes/dissolve. Panoramada **bir satır boşluk**
   bırak, kümülatif ofseti yeni bloğa resetle, devam ("bir satır alttan").
6. **Drift'e karşı:** faz-korelasyon zaten her kare bağımsız ölçer (LK gibi tek global
   tahmine bağımlı değil); yine de uzun jenerikte kümülatif yuvarlama hatası için
   periyodik olarak son birkaç karenin medyan dy'siyle yumuşat.

## 5. Metin (Paddle minimal — GPU dostu)
Görsel panorama Paddle GEREKTİRMEZ (faz-korelasyon + slit-scan saf cv2/numpy). Metni
**nihai panorama üzerinde TEK OCR** ile çıkar: `paddle_engine.recognize(panorama_path,
strategy="scroll_canvas_ocr")`. Statik bloklar için en net karede de bir OCR yeter.
**Önce tüm görsel boru hattını Paddle'sız kur ve test et** (SON METRO kırmızı panorama
temiz çıkıyor mu?), OCR'ı en sona ekle.

## 6. Girdi / Çıktı sözleşmesi (boxtracking ile AYNI — kıyas için zorunlu)
**Girdi:** `frames: list[Path]`, `source_fps: float = 6.0`, `paddle_engine` (yalnız final OCR).
**Çıktı (`outputs/_slitscan_test_<ts>/<film>__<seg>/`):**
- `panorama.png` — tek görsel
- `lines.json` — `{canvas_path, line_count, lines:[{text,bbox,confidence}]}`
- `debug.json` — kare-kare `dy`, faz-korelasyon tepe gücü, statik/akan/cut olayları

## 7. Test planı (tam performans, mock değil) — boxtracking ile AYNI 4 vaka
Kareler: `outputs/_hakim_shadow_20films_20260529_1507/items/<film>/frames/<seg>/frame_*.png`
- `1980_son_metro_end_credits` / **closing** ← ASIL TEST. Şarkı kredileri (CHANSONS,
  BEI MIR BIST DU SCHÖN, PRIERE A ZUMBA, SOMBREROS ET MANTILLES) kırmızı zeminde önce
  durur sonra akar. Panorama bunları **gözle okunur** göstermeli (kırmızı boş bant DEĞİL).
- `1980_son_metro_end_credits` / opening (karma: DENEUVE, LE DERNIER MÉTRO, TRUFFAUT)
- `2000_x_men_end_credits` / closing (saf stabil scroll — temiz, drift yok)
- `1989_kukla_adam_end_credits` / closing (saf statik kart — bloklar anlamlı)
**Başarı kriteri:** SON METRO closing panoramasında şarkı kredileri okunur + diğerleri bozulmaz.

## 8. boxtracking (A) vs slitscan (B) — kıyas eksenleri
| Eksen | A: boxtracking (box-içi LK) | B: slitscan (faz-korelasyon + slit-scan) |
|---|---|---|
| Kayma ölçümü | box-içi LK medyanı | faz-korelasyon (global, alt-piksel) |
| Dikiş | box/şerit yapıştır | sabit slit pushbroom (hayaletsiz) |
| Kırmızı zemin | box-içi yazı feature'ı | frekans-domeni → daha dayanıklı |
| Paddle yükü | her seed karede | yalnız final panorama |
| Risk | feature azsa kayar | sabit-hız varsayımı; dy gürültüsü |

## 9. Kurallar (uygulayıcı için)
- **Master'da çalış, COMMIT ETME.** Yalnız `core/pipelines/ocr/slitscan/` altında üret.
- `boxtracking/`, `unified_credit_pipeline.py`, `text_layer_row_reconstruct.py`, `box_tracker.py`
  ve diğer uncommitted dosyalara **DOKUNMA** (başka agent + başka oturum işi).
- `venvs/ocr/Scripts/python.exe` ile koş. cv2 + numpy + paddle var.
- **GPU paylaşımı:** Başka bir agent aynı anda Paddle (RTX 3090) koşturuyor olabilir.
  Bu yüzden görsel boru hattını Paddle'sız kur; OCR'ı en sona bırak; tek seferde, sıralı
  koş. CUDA/Paddle init hatası alırsan = GPU çakışması, kısa bekleyip retry et.
- **cv2 Türkçe-İ tuzağı:** Windows'ta imread/imwrite Türkçe İ yolunu okuyamaz →
  `np.fromfile`+`imdecode` / `imencode`+`tofile` kullan.
