# BoxTracking — Çalışma Prensipleri (Çağatay'ın mimarisi)

> **Amaç:** Film jeneriğini — statik kart olsun, stabil akan scroll olsun, ikisi
> karışık (faz değiştiren) olsun fark etmez — **tek bir okunaklı panorama PNG'ye**
> çıkarmak. Sınıflandırma yapmadan: box'ı izle, durursa kart, kayarsa panorama.
>
> Bu klasör Çağatay'ın **BoxMotionTrack** fikrinin temiz uygulamasıdır. Mevcut
> `text_layer_row_reconstruct.py` (LK global stitch) bunu YAPMIYOR; o, SON METRO
> kırmızı-zemin karma jeneriğinde çöktü (boş kırmızı bant + metin emniyet ağıyla
> kurtarıldı, temiz görsel kayboldu). Bu modül o kırılmayı kökten çözmek için var.

---

## 1. Çekirdek ilke (Çağatay)

1. Jenerikte **box alabileceğimiz ilk sağlıklı yazıyı** bul, motion-track'e al, izle.
2. **Box durursa → statik** (o duruşu kart gibi kaydet). **Durması takibi bitirmez** ("durursa da kesmeyiz").
3. **Box kayarsa → kaydıkça aynı hızda panoramayı dik.**
4. Takip edilen box ekranın **üst %15'ine girince → alttan yeni beliren box'a devret** (handoff), kaldığın kümülatif ofsetten dikmeye devam.
5. Yazı **cut/dissolve ile silinip yenisi gelirse** → onu hemen box'la, **panoramada bir satır boşluk bırakıp** kesintisiz devam et (yeni bölüm).

**Kilit:** Sınıflandırma adımı YOK. Takip etmek = dikmek (box'ın yerini bildiğin
için ofset bilinir; ayrı piksel-hizalayıcı yok → kırmızı zemin sorunu yok).

## 2. Üç tip = tek motor

| Tip | Davranış | Motorun tepkisi |
|---|---|---|
| **STATİK** | yazı hiç kımıldamaz (kart) | konsensüs dy ≈ 0 → en net kareyi blok olarak kaydet |
| **STABİL** | kararlı hızda akar (scroll) | konsensüs dy > 0 → kümülatif ofsetle panorama dik |
| **STABİL/STATİK** | aynı jenerikte ikisi (SON METRO) | dy 0↔pozitif geçer → aynı akışta sürdür, faz ayırma yok |

Üç tip ayrı kod yolu DEĞİL — tek "box izle + kaymayı ölç" motorunun davranışı.

## 3. Algoritma (online, kare-kare) — sağlamlaştırılmış

Çağatay'ın tek-box fikri korunur ama **kırılganlığı alınır** (Opus değerlendirmesi):

1. **Seyrek OCR (seed/refresh):** Her `OCR_STRIDE` karede bir (öneri 6–12) PaddleOCR
   detection → ekrandaki text box'ları bul. Yeni box'ları aktif takip setine ekle,
   mevcutlarla pozisyon+metin benzerliğiyle eşleştir. **(Maliyet kontrolü: her kare
   OCR bizi patlatır — eski 22 dk felaketi. Seyrek tut.)**
2. **Sık takip (her kare, ucuz):** Aktif box'ların her birini bir sonraki karede
   **box-İÇİ optik akış (Lucas-Kanade sparse)** veya template-matching ile sürükle →
   her box için dy (ve dx). **Feature'ı SADECE box içinde (yüksek kontrastlı yazı)
   ara — tüm karede değil.** Kırmızı düz zeminde feature yok ama sarı yazıda var →
   eski global-LK'nın kırmızı-zemin çöküşü burada OLMAZ.
3. **Çok-box konsensüs kayması:** Aktif box'ların dy'lerinin **medyanı** = bu karenin
   panorama kayması (robust). Tek box kaçsa diğerleri taşır → zincir kopmaz.
   `|medyan dy| < STATIC_EPS` → statik faz; `>= STATIC_EPS` → akan faz.
4. **Panorama dik:** `kümülatif_ofset += medyan dy`. Akan fazda ekranın taze şeridini
   (alttan giren içerik) kümülatif ofsette tuvale yapıştır. Statik fazda o duruşun
   en net karesini blok olarak ekle.
5. **Handoff / yenileme:** Box üst %15'e girince (veya kaybolunca) aktif setten düş.
   Seyrek OCR alttan gireni ekler. Çok-box olduğu için "devretme anı" kritik tekillik
   değil — küme sürekli yenilenir.
6. **Cut/dissolve:** Ardışık kareler arası **global fark (sahne kesimi)** VEYA tüm
   box'ların ani kaybı → "yeni bölüm" → panoramada bir satır boşluk, yeni seed ile devam.
7. **Drift çapası:** Kümülatif kayma birikince drift olur (uzun jenerik, 500+ satır).
   Seyrek OCR'ı **absolute çapa** olarak kullan: OCR'ın bulduğu box pozisyonu ile
   takip-tahmini ofseti ara ara senkronla.

## 4. Kapatılan açıklar (Opus değerlendirmesi → çözüm)

| Açık | Çözüm (yukarıda) |
|---|---|
| Tek box = tek kırılma noktası | §3.3 çok-box medyan konsensüs |
| Her-kare-OCR patlatır | §3.1 seyrek OCR + §3.2 ucuz optik akış |
| Kümülatif drift | §3.3 medyan + §3.7 OCR çapa |
| Handoff'ta yanlış box / tekrar eden metin | §3.5 çok-box küme (tekillik yok), pozisyon öncelikli eşleştirme |
| Cut vs dissolve karışır | §3.6 sahne-kesim sinyali + box-kaybı birlikte |

## 5. Girdi / Çıktı sözleşmesi

**Girdi:** `frames: list[Path]` (segmentin kareleri, sıralı), `source_fps: float`,
`paddle_engine` (mevcut PaddleOcrEngine örneği, OCR seed için).

**Çıktı:** `BoxTrackResult`:
- `panorama_path: Path` — tek PNG (segmentin tüm jeneriği, faz-agnostik)
- `text_lines: list[dict]` — panorama üstünde OCR veya box gözlemlerinden (text, bbox, conf)
- `sections: list[dict]` — cut/dissolve ile ayrılan bölümler (başlangıç karesi, tip)
- `debug: dict` — kare-kare dy, konsensüs, handoff/cut olayları (görsel doğrulama için)

**cv2 Türkçe-İ tuzağı:** Windows'ta `cv2.imread/imwrite` Türkçe `İ` yollarını okuyamaz
→ `np.fromfile`+`imdecode` / `imencode`+`tofile` kullan (SON METRO'da İ yok ama kural).

## 6. Test planı (tam performans, mock değil)

Kareler hazır: `outputs/_hakim_shadow_20films_20260529_1507/items/<film>/frames/<seg>/`

| Film | Segment | Beklenti |
|---|---|---|
| **1980_son_metro** | closing | **ASIL TEST** — şarkı kredileri (CHANSONS/BEI MIR...) önce durur sonra akar; panorama TEMİZ çıkmalı (kırmızı boş bant DEĞİL) + oyuncu kartları |
| **1980_son_metro** | opening | karma — başlık + kadro (DENEUVE, LE DERNIER MÉTRO, TRUFFAUT) tek panoramada |
| **2000_x_men** | closing | saf stabil scroll — temiz panorama, drift yok (referans, regression) |
| **1989_kukla_adam** | closing | saf statik kart — kartlar blok blok, panorama anlamlı |

**Başarı kriteri:** SON METRO closing panoramasında şarkı kredileri **gözle okunur**
(eski kırmızı-boş-bant kırılması tekrarlamaz) + X-MEN/KUKLA bozulmaz.

Çıktı dizini: `outputs/_boxtracking_test_<ts>/<film>__<seg>/` (panorama.png + lines.json + debug).
Koşum: `venvs/ocr/Scripts/python.exe ...` (MITAS OCR venv).

## 7. Mevcut row_reconstruct'tan farkı (neden ayrı modül)

| | row_reconstruct (mevcut) | BoxTracking (bu) |
|---|---|---|
| Takip & dikiş | AYRI (LK tüm-kare global displacement) | TEK (box-içi takip = dikiş) |
| Sınıflandırma | binary static/scroll (önce) | yok (dy davranışı) |
| Kırmızı zemin | çöküyor (feature yok) | box-içi yazı feature'ı → sağlam |
| Faz geçişi | ezilir (tek tip seçilir) | doğal (aynı box izlenir) |
| Kırılma | tek global tahmin | çok-box medyan (robust) |

## 8. MITAS kuralları (uygulayıcı için)

- **Master'da çalış, worktree yok. COMMIT ETME** (Çağatay onayı bekler).
- Mevcut pipeline'a (`unified_credit_pipeline.py`, `text_layer_row_reconstruct.py`)
  **DOKUNMA** — bu ayrı bir POC klasörü. Çalışırsa SONRA entegre edilir.
- Pre-existing uncommitted dosyalara (ASR/webui/docs, Hakim değişikliği) dokunma.
