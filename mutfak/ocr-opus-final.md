# OCR-OPUS-FINAL — Kesinleşmiş Kararlar

> Bu dosya, jenerik→tek-master işinde **kanıtlanmış ve kesinleşmiş** yöntemleri tutar.
> Her karar yalnızca bir durumu kapsar. Tarih: 2026-05-30.

---

## KARAR 1 — Akan (scrolling) + arka planı sabit/siyah jenerik → **SLIT-SCAN**

### Kapsam (yalnızca bu)
Jenerik yazısı ekranda **sabit planda, ~sabit hızda akıyor.**
Örnek: Hollywood kapanış scroll'u (siyah üstüne beyaz, iki sütun rol+isim),
SON METRO kapanış şarkı listesi. **Kart değil, akan yazı.**

### Yöntem — Slit-scan (photo-finish)
Tek cümle:
> **Ekranda sabit bir yatay çizgi seç. Her kareden, o çizgide, o karenin kaydığı kadar
> (hız = v piksel) yükseklikte ince bir şerit al. Şeritleri sırayla alt alta diz.**

Yazı o sabit çizgiden akıp geçtikçe, şeritler tüm jeneriği yeniden kurar.
OCR yok, NCC yok, optical-flow yok, dedup yok, harman yok.

### Neden çalışır (basit ve garantili)
Sabit hızlı akışta içerik her karede `v` piksel kayar. Sabit çizgide `v` piksellik şerit
alırsan, ardışık iki şerit içerikte **tam `v` piksel ayrı** olur → üst üste binme yok,
boşluk yok. Her içerik satırı çizgiden **tam bir kez** geçer →
- her satır master'da **tam bir kez**,
- **keskin** (gerçek piksel kopyalanır; ortalama/harman yok → bulanıklık yok),
- hız sabit olduğu sürece kusursuz.

### Algoritma (öz — yeniden üretilebilir)
1. Ardışık iki kare arası dikey kaymayı ölç:
   `(_, dy), _ = cv2.phaseCorrelate(prev_gray*hann, cur_gray*hann)`
   (siyah/sabit zeminde tüm kare hareketi = scroll; maskeye gerek yok)
2. `v = round(abs(dy))`
3. **Kural A — duran kareyi atla:** `v < 1` ise scroll duraklamış → hiçbir şey ekleme
   (tekrar/çift basımı önler).
4. **Kural B — sıçrama/cut kırp:** `v > ~40` ise atla.
5. Aksi halde sabit çizgiden şerit al ve ekle:
   `strip = frame[ref : ref+v, :]`  (tam genişlik), `ref = round(0.55 * H)`
6. Tüm şeritleri sırayla `np.vstack`.

### Doğrulanmış parametreler (X-MEN kapanışında)
| Parametre | Değer |
|---|---|
| Çizgi konumu `SLIT_FRAC` | 0.55 × kare yüksekliği |
| Hız ölçümü | maskesiz tam-kare `cv2.phaseCorrelate` |
| Statik eşiği | `v < 1` atla |
| Sıçrama eşiği | `v > 40` atla |
| Harman / OCR / dedup | **YOK** |

### Kanıt
X-MEN (2000) kapanış: 3240 kare → 2328 şerit, median hız **8.4 px/kare** →
master **854×19846**. İki sütun (rol+isim) hizalı, **her satır TEK**, keskin,
**hayalet/çift YOK**. Baş (CAST: HUGH JACKMAN, PATRICK STEWART, IAN McKELLEN…)
ile orta (VFX crew, iki sütun) ile son baştan sona temiz.

### NE YAPILMAZ (denendi, battı)
- **NCC overlap-template** (motor A): yoğun iki-sütun küçük metinde eşleşme belirsizleşir
  → hayalet/çift. (Tek-sütun seyrek kredide iyi, yoğun iki-sütunda hayır.)
- **OCR satır-dedup** (motor D): iki-sütunda rol (sol) + isim (sağ) AYRI satır sanılır,
  her birine tam-genişlik bant verilir → her satır **2× basılır** (ghosting). Üstelik yavaş.
- **Optical-flow + medyan harman** (motor B): ortalama → küçük metin bulanık; ayrıca
  parlaklık-kapısı yüzünden tek filme aşırı-uyum (beyaz-siyah scroll'da boş kalır).
- **Sabit şerit yüksekliği** (eski slitscan `SLIT_H=8`): gerçek hız 8 değilse dikey ölçek
  bozulur. **Gerçek ölçülen `v`'yi kullan.**

### Kapsam DIŞI (bu karar değil — ayrı kararlar gelecek)
- Statik (akmayan) kartlar → KARAR 2.
- Film footage ↔ jenerik ayrımı.
- Karışık segment (kart + akan + film bir arada).

---

## KARAR 2 — Statik (akmayan) kartlar + arka plan SABİT → "duran koşuyu yakala"

### Kapsam (yalnızca bu)
Jenerik yazısı ekranda **DURUYOR** (akmıyor) ve **arka plan SABİT/düz-renk**
(kırmızı/siyah/tek-renk). Örn: SON METRO açılış isim kartları; her kart ~2-3 sn basılı.

### Yöntem — A = ANA (ham kareden, slit-scan'in ikizi)
Slit-scan ile **aynı tek motion ölçümü** static↔scroll ayırır:
- `dy ≈ 0` (akış yok) + üstünde yazı + düz-renk zemin → kart **HELD**.
- Held run'ın **EN KESKİN** karesi (max Laplacian) = kart. **Stitch yok, harman yok**
  (kart tek ekran; sadece doğru kareyi seç).
- **Kart değişimi (swap):** `dy≈0` AMA **YAZI-BÖLGESİ diff'i** sıçradı → yeni kart.
  > Global diff DEĞİL — yazı karenin küçük kısmı, isim değişince global diff kımıldamaz.
  > Diff'i sadece YAZI MASKESİ içinde ölç → isim değişince sıçrar. ("Kaybolan aktör" ilacı;
  > dissolve ile geçen cast kartlarını ayırır.)
- **Bitişik kart dedup:** yazı-bandının NCC görüntü-korelasyonu ≥0.97 → aynı kart.
  > Maske-ŞEKLİ ile dedup YAPMA — tek-isim kartların maskeleri benzer şekilli, farklı
  > isimleri yanlış birleştirir. Gerçek görüntü içeriğine bak.
- Her benzersiz kartın en keskin karesinden **yazı bandını (tam genişlik)** al, sırayla diz.

### Doğrulanmış parametreler (SON METRO açılış: 10 → 28 kart, cast+crew tam)
| Parametre | Değer |
|---|---|
| `STATIC_DY` | 1.5 (|dy| altı = akmıyor) |
| `TB_SWAP` | 22 (YAZI-BÖLGESİ mean-abs-diff; swap eşiği) |
| `MIN_HOLD` | 5 kare |
| `DOMINANT_BG_MIN` | 0.42 (düz-renk zemin kapısı) |
| dedup | yazı-bandı NCC ≥ 0.97 |
| Script | `scripts/_static_cards_from_frames.py` |

### İki yöntem — A ve B nedir
- **A** (`scripts/_static_cards_from_frames.py`): Kartları **ham kareden KENDİ bulur**,
  pipeline'a bağımsız. Top-hat ile yazı maskesi → held-run + en keskin kare + yazı-bölgesi
  swap. Hızlı, OCR yok. (Benzetme: filmi kendin izleyip "işte kart, en net an" demek.)
- **B** (`scripts/_prototype_credits_png_compose.py`): Pipeline'ın hazır çıktısını
  (`unified/.../events.json` + `cards/*.json`: best_frame + y_range) **dizer**. Pipeline
  **gerçek bir metin-dedektörü** (PaddleOCR det) kullandığı için arka-plan-bağımsız; ama
  pipeline'a bağımlı. (Benzetme: başkasının hazırladığı listeye göre fotokopi çekmek.)

### Test sonuçları (kanıt)
**Sabit arka plan — SON METRO açılış (kırmızı kartlar):**
- A: 28 kart, cast+crew temiz. B: 29 parça, temiz. → **İkisi de iyi (başa baş).**

**Hareketli arka plan — ANJELIK açılış (yazı, oynayan gemi/deniz üstünde):**
- A (top-hat): 12 kart AMA giriş-metni **7× tekrar** — hareketli bg top-hat maskesini
  gürültülendirip swap/dedup'ı bozuyor.
- A (OCR-det maske denendi): dup düzeldi ama **cast kayboldu** (OCR, oynayan sahne üstünde
  flicker yapıyor → held-run kırılıyor) → yalnız 4 crew kartı.
- B (pipeline): cast+crew **ayrı ayrı, temiz** (giriş 2×) → **açık ara en iyi.**

### KARAR
- **Sabit arka plan → A VEYA B** (ikisi de net; A = hızlı/bağımsız, B = pipeline'la).
- **Hareketli arka plan → SADECE B.**
  > Sebep: hareketli zeminde "bu bir yazı mı?" ayrımı **gerçek metin-dedektörü + içerik
  > takibi** ister. A'nın kare-bazlı held-run'ı (top-hat da OCR-det de) flicker/gürültüde
  > kırılgan kalıyor — ya çiftliyor ya kaçırıyor. B/pipeline bunu sağlam yapıyor.

Tek cümle: **statik kart → sabit bg'de A veya B, hareketli bg'de B.**

### Kapsam DIŞI
- Film footage ↔ jenerik ayrımı (kart sonrası sızan film) → ayrı karar (aşağıda KARAR 3'te ASIL SORUN olarak işlendi).

---
---

# ⚠️ KARAR 3 — Hareketli plan + AKAN (scroll) jenerik   ·   *ayrı tutulur*

> **Neden ayrı başlık:** 2×2'nin bu son kutusunun reconstruction'ı teknik olarak çözüldü
> (aşağıda YOL 1 kanıtlı). AMA bu kutunun **etrafında** projenin asıl çözülmemiş sorunu
> duruyor → **"bu segment gerçekten JENERİK mi, yoksa FİLM FOOTAGE'ı mı?" = film↔jenerik AYRIMI.**
> Bu yüzden bu karar diğerlerinden ayrı ve vurguludur. (En alttaki "ASIL AÇIK PROBLEM" bloğu.)

## Kapsam (yalnızca bu)
Jenerik yazısı ekranda **AKIYOR (scroll)** AMA arka plan **siyah değil — oynayan film görüntüsü**
(yüz, manzara, sahne). Örn: end credits bir oyuncunun yüzünün / hareketli sahnenin üstünden kayıyor.
KARAR 1'den farkı: orada zemin siyah/sabitti; burada zemin **footage ve oynuyor.**

## ÖNCE BÜYÜK BULGU — bu kutu arşivde NADİR ve sahtesi bol (kanıt)
`scripts/_scan_scroll_darkratio.py` ile **60 filmin TÜM scroll segmentleri** tarandı
(pipeline'ın kendi `row_reconstruct_summary.json` → `frame_filter.median_dark_ratio` +
`motion.median_dy_per_frame` + `quality`). Bulgular:
- **Yüksek dark_ratio (~0.9+)** = siyah-bg scroll = KARAR 1 alanı (X-MEN, Robinson, Jurassic…).
- **Düşük dark_ratio** = parlak/dokulu zemin = "hareketli scroll" SANILAN segmentler. AMA
  açıp baktığımız **5 düşük-dark segmentin 5'i de scroll DEĞİL — yazısız film footage'ıydı**
  (kamera/özne hareketi sahte "scroll dy" üretmiş):
  franny kapanış = çizgi-film sahneleri; anjelik kapanış = atlı/yüz/çift; pilkington = kitap
  tutan el; dnyanin_en_mthi = "Harm" başlığı+gazete; bizim_evin = resepsiyon sahnesi.
- **Üstelik dark_ratio tek başına AYIRMIYOR:** gerçek type-3 kazançlarımız (yabandan, marie)
  **orta-yüksek dark'ta (0.75–0.80)** çıktı (footage karanlıktı), sahte olanlar **0.01–0.09**'daydı.
  Yani parlaklık "jenerik mi footage mı"yı söylemiyor.

→ **DERS: "hareketli bg + scroll" sanılanın çoğu, footage'ın yanlış sınıflanmasıdır.
   Bu kutuda ASIL SORUN reconstruction değil, AYRIM.**

## ⓘ NETLEŞTİRME NOTU (kanıt kaynakları — karışmasın)
- **ANJELIK açılış ≠ kapanış.** §ÖNCE BÜYÜK BULGU'daki *"anjelik **kapanış** = footage"* tespiti,
  bu oturumda bakılan KAPANIŞ kareleri içindir (atlı / kadın yüzü / çift = saf film). YOL 2'nin
  temiz çıkardığı **2-sütun Fransızca cast-scroll** ise AÇILIŞ tarafıdır (oynayan deniz üstünde).
  Yani çelişki yok — **farklı segment**. Dahası açılışın kendisi **karışık**: giriş-yazısı (caption)
  + cast-scroll + footage iç içe. **Kritik ders:** bekçi/router TÜM segmente değil, **KARE-ARALIĞINA**
  karar vermeli; tek segment birden çok tip içerebiliyor (bkz. §10.3).
- **Kare numaraları iki ayrı extraction'dan.** YOL 2 ve §8 GÖZ'deki frame no'ları (ör. "frame 750 =
  scroll, frame 60 = yüz") ÖTEKİ-ORTAM çıkarımına aittir. Pipeline'ın `frames/opening`
  numaralandırması farklıdır (orada ~frame 60 = caption, ~frame 750 = yüz). İçerik yargısı aynı;
  mutlak indeksleri **kaynağına göre** oku.

## YOL 1 — Pipeline `row_composite` (KARAR 2'deki B'nin scroll kardeşi)   ✅ ÇALIŞIYOR

**Üreten kod (AÇIK):** `core/pipelines/ocr/text_layer_row_reconstruct.py`
→ fonksiyon **`run_text_layer_row_reconstruct(item_dir, ...)`**, strateji adı `text_layer_row_reconstruct_v1`.
**Çıktı:** `unified/<segment>/scroll/row_composite.png` (+ `row_reconstruct_summary.json` = kalite metrikleri).

**Adım adım ne yapıyor:**
1. Segmentin karelerini oku; `_filter_low_dark_frames` ile aşırı-karanlık kareleri ele.
2. `_select_best_row_candidate` iki aday kurar:
   - **(a) `current_displacement`** — ardışık kareler arası **dikey kaymayı (scroll hızını)** tahmin
     eder, merkez şeridi o kadar kaydırıp **alt alta dizer** = yazı-farkında photo-finish.
   - **(b) `static_best_frame`** — tek en keskin kare (akış yoksa).
   En iyiyi **kalite + satır sayısı + hareket** skoruyla seçer.
3. `detect_auto_split` rol/isim sütun ayrımını, `detect_rows` satır bantlarını bulur.
4. `_trim_composite_by_row_gap` kuyruktaki boşluğu kırpar.
5. `row_composite.png` + özet yazar. Özette `quality.score`, `quality.ghost_penalty`,
   `motion.median_dy_per_frame` var → çıktı kalitesini **kendisi raporluyor**.

**Neden hareketli zeminde çalışır (özü):** Yöntem yazıyı **metin olarak** (tutarlı kayan içerik)
takip eder. Yazı her karede aynı hızla kaydığı için şeritler üst üste **temiz** oturur; arka plandaki
footage kareden kareye **tutarsız** olduğu için birikemez → sadece **zararsız dikey smear** bırakır.
(KARAR 1 slit-scan'in maskesiz tam-kare hız ölçümünü oynayan zemin BOZAR; burada metin-farkında
stacking bunu aşıyor — KARAR 2'deki "hareketli bg → sadece B" mantığının scroll versiyonu.)

**Ne sonuç aldık (kanıt — GERÇEK type-3'lerde):**
| Film / seg | dark | dy/kare | satır | kalite/ghost | Sonuç |
|---|---|---|---|---|---|
| 2014_yabandan_gelen_adam closing ("DUCK YOU SUCKER", Leone) | 0.753 | −26.2 | 126 | 1.0 / 0.0 | **TEMİZ** — tüm cast (BRONSON, COBURN, STEIGER, yön. LEONE … THE END) her isim **bir kez**; oynayan footage dikey smear oldu. *Frame 1300 = beyaz yazı oynayan yüz üstünde = type-3 kanıtı.* |
| 2016_marie_currie closing | 0.797 | −5.6 | 41 | 0.94 / 0.0 | **TEMİZ** — üst/alt siyah-bg jenerik net; orta bantta footage smear ama yazı korunmuş. |

**YOL 1 NEREDE patlar:** Önüne **yazısız footage** konursa (yukarıdaki 5 misclassification) → çöp
(franny: koca çizgi-film karesi + ezik yazı bandı). Bu YOL 1'in suçu DEĞİL; segmenti yanlış besleyen
**AYRIM** eksikliğidir.

**Kanıt görselleri (yollar):**
- yabandan kare (kanıt): `outputs/ocr_50films_aaaa_v21_paddle_20260525/items/2014_yabandan_gelen_adam_end_credits/frames/closing/frame_01300.png`
- yabandan composite (WIN): `…/2014_yabandan_gelen_adam_end_credits/unified/closing/scroll/row_composite.png`
- marie_currie composite (WIN): `…/2016_marie_currie_end_credits/unified/closing/scroll/row_composite.png`
- franny composite (FAIL=misclassification): `…/2003_franny_nİn_ayaklari_end_credits/unified/closing/scroll/row_composite.png`

## YOL 2 — Ham kareden MASKELİ-hız slit-scan + GÖZ bekçisi (Opus oturumu, 2026-05-30)   ✅ ÇALIŞIYOR (tek filmde kanıtlı)

> YOL 1 pipeline'ın hazır `row_composite`'ine bağlı. **YOL 2 pipeline'sız, HAM KAREDEN** çalışır
> ve scroll hızını **yazı piksellerinden** ölçer (oynayan zemini yok sayarak). Bağımsız bir
> doğrulama + alternatif. Aynı sonuca KARAR 1 slit-scan'inin küçük bir twist'iyle ulaştık.

### 1) NEREDEN YOLA ÇIKTIK (soru)
Çağatay sordu: *"Akan jenerikte arka plan hareketli — yazıyı arka plandan AYIRABİLİR miyiz?"*
Cevabın özü: **Evet — ama ayraç tek karede değil, ZAMANDA/HAREKETTE.** Yazı sabit hızda
tek-vücut hareket eder; arka plan başka türlü. Bu farkı kullanırız.

### 2) NELERİ YAPAMADIK / NASIL BU YOLA GELDİK
- KARAR 2'deki A (`_static_cards_from_frames.py`) hareketli bg'de **kare-bazlı held-run** ile
  tökezliyordu: top-hat maskesi oynayan zeminde gürültülenince swap/dedup bozuluyor (Anjelik
  açılış: giriş metni **7× tekrar**; OCR-det maskesi denendi → **cast kayboldu**, OCR flicker).
  Ders: **duran kartı tek-kare seçme mantığı, akan+hareketli durumda kırılgan.**
- Akan durumda doğru hamle: kart seçmek değil, **akışın hızında şerit biriktirmek** (slit-scan).
  Ama KARAR 1 hızı **maskesiz tam-kareden** ölçüyor → oynayan zemin onu şaşırtır.
- **Bulduğumuz düzeltme (YOL 2'nin özü):** hızı sadece **YAZI strokelarından** ölç (top-hat
  maske → maskeli `phaseCorrelate`). Hız yazıya kilitlenir, deniz yok sayılır.

### 3) ÜRETEN KOD / .py (AÇIK)
**(a) `scripts/_probe_textmotion.py`** — ucuz tarama: 900 kareyi tek tek açmadan, hangi karede
yazı var + akıyor mu (`dy`) çıkarır. Anjelik'te yapıyı buldu: 600-900 = akan jenerik (~9 px/kare).
```python
"""Cheap probe: where is the text, and does it scroll or hold? (no images returned)"""
import sys, glob
from pathlib import Path
import cv2, numpy as np
D = sys.argv[1] if len(sys.argv) > 1 else r"...anjelik...end_credits\frames"
STRIDE = int(sys.argv[2]) if len(sys.argv) > 2 else 3
def rd(p): return cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)
def tophat_mask(g):
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 5))
    th = cv2.morphologyEx(g, cv2.MORPH_TOPHAT, k)
    _, m = cv2.threshold(th, 25, 255, cv2.THRESH_BINARY); return m
def blobs(m):                       # wide+short blobs = text lines (film blobs elenir)
    n,_,st,_ = cv2.connectedComponentsWithStats(cv2.dilate(m,np.ones((3,3),np.uint8)),8); c=0
    for l in range(1,n):
        h=st[l,cv2.CC_STAT_HEIGHT]; w=st[l,cv2.CC_STAT_WIDTH]
        if 5<=h<=48 and w>=40 and w/max(1,h)>=1.5: c+=1
    return c
frames = sorted(glob.glob(D+r"\frame_*.png"), key=lambda p:int(Path(p).stem.split("_")[-1]))[::STRIDE]
H=W=hann=prevf=None
for f in frames:
    img=rd(f); g=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    if H is None: H,W=g.shape; hann=cv2.createHanningWindow((W,H),cv2.CV_32F)
    nb=blobs(tophat_mask(g)); gf=g.astype(np.float32); dy=0.0
    if prevf is not None: (_,dy),_=cv2.phaseCorrelate(prevf*hann, gf*hann)
    prevf=gf   # -> her karede (idx, blob sayısı, dy) raporla; yazı-var + dy~sabit aralığı = scroll
```
**(b) `scripts/_separate_scroll.py`** — ASIL ayırma: maskeli-hız slit-scan + temiz-zemin katmanı.
```python
"""TEXT vs MOVING-BG separation on a SCROLLING credit (case 4)."""
import sys, glob
from pathlib import Path
import cv2, numpy as np
D="...anjelik...end_credits\\frames"; OUT=Path(r"E:\MITAS\outputs\_text_bg_sep_anjelik")
LO,HI=600,900; SLIT_FRAC=0.55; VMIN,VMAX=1,40; TOPHAT_K,TOPHAT_THR=15,22
def rd(p): return cv2.imdecode(np.fromfile(str(p),np.uint8),cv2.IMREAD_COLOR)
def wr(p,i):
    ok,b=cv2.imencode(".png",i)
    if ok: b.tofile(str(p))
def tophat(g):
    k=cv2.getStructuringElement(cv2.MORPH_RECT,(TOPHAT_K,5))
    th=cv2.morphologyEx(g,cv2.MORPH_TOPHAT,k); _,m=cv2.threshold(th,TOPHAT_THR,255,cv2.THRESH_BINARY); return m

allf=sorted(glob.glob(D+r"\frame_*.png"), key=lambda p:int(Path(p).stem.split("_")[-1]))
frames=[f for f in allf if LO<=int(Path(f).stem.split("_")[-1])<=HI]
H=W=hann=prev_mg=None; prev_any=False; strips=[]; vs=[]
for f in frames:
    img=rd(f)
    if H is None:
        H,W=img.shape[:2]; hann=cv2.createHanningWindow((W,H),cv2.CV_32F); ref=round(SLIT_FRAC*H)
    g=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY); gf=g.astype(np.float32)
    m=tophat(g); mdil=cv2.dilate(m,np.ones((11,11),np.uint8))   # YAZI maskesi (deniz değil)
    mg=gf.copy(); mg[mdil==0]=0.0                               # zemini sıfırla
    dy=0.0
    if prev_mg is not None and bool(mdil.any()) and prev_any:
        (_,dy),_=cv2.phaseCorrelate(prev_mg*hann, mg*hann)      # hız = YAZIdan
    prev_mg=mg; prev_any=bool(mdil.any())
    v=int(round(abs(dy)))
    if v<VMIN or v>VMAX: continue                              # durdu / cut -> atla
    strip=img[ref:ref+v,:].copy()                              # sabit çizgiden v-yükseklik şerit
    if strip.shape[0]>0: strips.append(strip); vs.append(v)
master=np.vstack(strips); wr(OUT/"master_slitscan.png", master)
# literal ayrım: parlak yazı katmanını saf siyaha taşı
gm=cv2.cvtColor(master,cv2.COLOR_BGR2GRAY)
th=cv2.morphologyEx(gm,cv2.MORPH_TOPHAT,cv2.getStructuringElement(cv2.MORPH_RECT,(TOPHAT_K,5)))
_,tmask=cv2.threshold(th,18,255,cv2.THRESH_BINARY); luma=(gm>140).astype(np.uint8)*255
mask=cv2.morphologyEx(cv2.bitwise_and(tmask,luma),cv2.MORPH_CLOSE,np.ones((3,9),np.uint8))
crisp=np.zeros_like(master); crisp[mask>0]=(255,255,255); wr(OUT/"master_textonly_crisp.png", crisp)
```

### 4) ADIM ADIM NE YAPIYOR
1. Yazı maskesi: `tophat(15×5)+thr` → ince parlak strokelar (deniz parıltısı/footage değil).
2. Hızı **yazıdan** ölç: maske dışını sıfırla → `phaseCorrelate(prev*hann, cur*hann)` → `dy`.
3. `v=round(|dy|)`; `v<1` atla (akış durdu), `v>40` atla (cut/sıçrama).
4. Sabit çizgiden (`ref=0.55*H`) `v` yükseklikte şerit al; hepsini `vstack` → **master**.
5. Temiz-zemin: master'da `tophat + luma>140` → yazıyı saf siyaha taşı (text-only katman).

### 5) NEDEN HAREKETLİ ZEMİNDE ÇALIŞIR (fizik — şans değil)
Yazı kendi hızında hizalanır → ardışık şeritler yazıda **tam örtüşür** → her satır tek + keskin.
Aynı şeritlerde deniz hizasız → ortalanıp **bulanık washa** döner → silinir. **Doğru hızda
tarama = yazı odakta, zemin defokus.** (YOL 1'in "metin-farkında stacking"inin ham-kare +
maskeli-hız kardeşi; aynı fizik, farklı uygulama.)

### 6) NELERİ TEST ETTİK — SONUÇ (kanıt + path)
**ANJELIK end_credits 600-900** (301 kare, 600×480; oynayan deniz+yelkenli üstünde Fransızca
rol+isim iki sütun, ~9 px/kare akıyor):
- 293 şerit, medyan hız 9 px/kare → master **600×2773**.
- **Tüm kadro tek sütunda, her satır BİR KEZ, keskin, iki sütun (rol+isim) hizalı.**
- **Oynayan deniz kendiliğinden silindi** (koyu wash). Gözle doğrulandı: frame 750 ham =
  yazı oynayan deniz üstünde; master = temiz liste.
- Çıktılar:
  - `outputs/_text_bg_sep_anjelik/master_slitscan.png` ← asıl sonuç
  - `outputs/_text_bg_sep_anjelik/master_textonly_crisp.png` ← yazı saf siyaha ayrılmış

### 7) NEREDE PATLAR (sınırlar)
- **Parlak-yazı varsayımı:** temiz-zemin/luma katmanı yazı parlaksa çalışır; koyu yazıda luma
  çöker → o zaman sadece slit-scan master'ı kullan (master hareketten bağımsız).
- Zemin yazıyla **aynı hız+yönde** hareket ederse (nadir) ayrım düşer.
- Ekranda nispeten sabit duran nesne (ufuk/yelkenli) slit çizgisinde ince **dikey iz** bırakır.
- **Önüne yazısız footage konursa çöp** (YOL 1 ile aynı zaafiyet → çözüm = bekçi, aşağıda).

### 8) EK — GÖZ router: aşağıdaki "ASIL AÇIK PROBLEM"in (bekçi) adayı
"Bu segment jenerik mi, footage mı?" sorusuna bu oturumda bir **aday** kurduk: kareye bakıp
karar veren **yerel görsel-LLM** (bulut yok, TRT verisi yerelde).
- **İş bölümü:** **GÖZ (1 kare, `qwen2.5vl:7b`)** = görünüm (yazı parlak/koyu, jenerik/film,
  sütun, dil, zemin-tipi); **MATEMATİK (2 kare, `dy`)** = hareket (göz hareketi **tek kareden
  bilemez** — fizik); **KOD** ikisini birleştirip motoru seçer. Gözün *method önerisine güvenme*.
- **Kanıt (`scripts/_vlm_router.py`):** Anjelik frame 750 → `bright`✅ `columns=2`✅ `French`✅
  `moving_scene`✅ (yalnız `motion=static_card`✗, tek-kare sınırı); frame 60 (kadın yüzü) →
  `is_credits=false`✅ *"film, jenerik değil"* = **bekçinin tam yapması gereken iş.**
```python
import json, base64, urllib.request
from pathlib import Path
URL="http://localhost:11434/api/generate"; MODEL="qwen2.5vl:7b"
PROMPT=("You see ONE frame from a film's credit sequence. Judge ONLY what is visible. "
  "STRICT JSON keys: is_credits(bool), text_color(bright|dark|mixed|none), "
  "motion_guess(scrolling|static_card|unknown), background(moving_scene|static_scene|black_plain|unknown), "
  "columns(0-3), language, recommended_method(slitscan_text_velocity|luma_key|temporal_median|held_run_cards|skip_not_credits), "
  "note(<=12 words). Return ONLY the JSON.")
def _post(body,t):
    req=urllib.request.Request(URL,json.dumps(body).encode(),{"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=t) as r: return json.loads(r.read())
def classify(path):
    b64=base64.b64encode(Path(path).read_bytes()).decode()
    out=_post({"model":MODEL,"prompt":PROMPT,"images":[b64],"stream":False,
               "format":"json","keep_alive":"10m","options":{"temperature":0}},600)
    return json.loads(out.get("response","{}"))
# NOT: ilk çağrı modeli VRAM'e yükler (soğuk start) -> önce bir warmup _post'u at, timeout=600.
```

### 9) ŞU AN NEREDEYİZ — NE BAŞARDIK
- ✅ En zor kutu (**akan yazı + hareketli zemin**) artık **iki bağımsız yolla** çalışıyor:
  YOL 1 (pipeline `row_composite`) + YOL 2 (ham-kare maskeli-hız). Anjelik'te yazı oynayan
  denizden **temiz ayrıldı.**
- ✅ "Yazıyı arka plandan ayırmak" sorusu cevaplandı: ayraç **hareket/zaman**; doğru hızda
  tarayınca ayırma **bedava** geliyor (zemin defokus olur).
- ✅ Bekçi (film↔jenerik) için somut bir aday: **yerel GÖZ router** — PoC'da doğru ayırdı.
- ✅ Araç alternatifi: ffmpeg `lumakey` = python'suz temiz-zemin **VİDEO** (yazı parlaksa);
  ama master'a düzleştirme yine slit-scan ister.

### 10) SORU İŞARETİ OLARAK KALANLAR
1. **Genelleme:** YOL 2 yalnız **Anjelik'te (1 film)** kanıtlı → çok-film doğrulaması şart
   (10-film sette gerçek type-3 yok; *yabandan / marie* gibi filmlerde sınanmalı).
2. **Bekçi gerçek-ölçek:** GÖZ router **3 karede PoC**; çok filmde doğruluk/hız ölçülmeli.
3. **Anjelik çelişkisi:** doc yukarıda *"anjelik kapanış = footage (yanlış sınıflama)"* diyor;
   ama benim kullandığım end_credits **600-900 gerçek scroll** çıktı → segment ya farklı
   kesilmiş ya **karışık** (footage + scroll). Bu, bekçinin **segment değil, kare-aralığı**
   düzeyinde çalışması gerektiğini gösteriyor (açık tasarım sorusu).
4. **YOL 1 vs YOL 2:** hangisi daha iyi genelliyor? "SONRAKİ İŞ"teki yarış henüz yapılmadı.

## SONRAKİ İŞ — büyük veri grubunda YOL 1 vs YOL 2 yarışı
İki yol da hazır olunca **büyük bir film grubunda** (sadece 10 değil) yan yana test:
- **Metrik:** kapsama (jenerik metni tam mı), `ghost_penalty` (her satır bir kez mi),
  okunabilirlik, footage'a karşı dayanıklılık.
- **ÖN ŞART:** girdiye **gerçek scroll segmentleri** ver (footage'ı ayıkla) — yoksa iki yol da
  haksız yere çöp üretir (bkz. ASIL AÇIK PROBLEM).

## ⚠️ ASIL AÇIK PROBLEM (bunun üstünde duralım) — Film footage ↔ jenerik AYRIMI
Yukarıdaki 5 misclassification net gösterdi: pipeline **hareketli footage'ı** (kamera hareketi =
sahte "scroll dy") jenerik scroll'u sanıp boş yere `row_composite` üretiyor; ve **dark_ratio bunu
ayırmaya yetmiyor** (gerçek type-3 de footage da aynı parlaklıkta olabiliyor). 4 kutunun
reconstruction'ı tamam — **ama doğru segmenti doğru kutuya yollayan "bekçi" (jenerik mi / film mi?)
yok.** Projenin bir sonraki GERÇEK işi budur; YOL 1/YOL 2 ne kadar iyi olsa da bu bekçi olmadan
footage'da çöp üretmeye mahkûm.
