# db_compose_master.py — final özet (2026-06-20)

std2 (`db_compose_standalone2.py`) üstüne inşa; tek dosya, GÖRSEL-only, prep-bağımsız. 47-film havuzunda koşuldu.

## Ne yapıldı
1. **İçerik-tabanlı kart bölme (son_metro fix):** statik run'ı tam-kare hareketle değil text-mask dHash **ani-sıçrama + kalıcı-plato** ile böler. Sabit zemin (son_metro kırmızı) tam-kare kesim-dedektörünü kör ediyordu → 318-kare/1-kart çöküşü; artık ~16-18 kart, cast tamam. Kademeli zemin-drift (kansas harita) sıçrama üretmediği için bölünmez → aşırı-bölünme azaldı.
2. **Kart metne kırpma:** `text_rows` ile sadece yazı-satırlarına kırpar (portre/boşluk düşer; tam değil — yüz çizgileri text gibi geçebiliyor).
3. **Mosaic şişme-guard + zarif-düşüş:** `canvas_h/frame_h > 5` veya `cut_frac > 0.25` → mosaic reddedilir, slit devralır (diriliş 65199px→3047px; mumya EXIT_0→çıktı var).
4. **Mosaic-tercih dispatch:** footage-kart filmi + biraz hareket (`0.10 ≤ scroll < 0.40`) + geçerli mosaic → mosaic kanonik (drakula cast-tek, slit'in tekrarından kaçınır). Saf-statik (scroll~0) slit'te kalır (mosaic ghost yapar). Scroll filmler slit.
5. **Manifest + bayraklar:** regime, selected_mode, bloat/cut_storm/very_short/single_card/no_cast — composer DÜZELTMEZ, işaretler (upstream).

## Sonuç (47 film)
- **45 slit + 2 mosaic** (drakula, beyaz_bizon). 0 ERROR, 0 boş.
- **Çözülenler:** son_metro cast 1→16 kart; drakula mosaic cast-tek; kansas slit (ghost yok).
- **Aşırı-bölünme azaldı:** robinson 21→11, yalaza 13→7, jurassic 19→13, senin_hikayen 22→14, mumya 30→27, kansas 7→4.
- **Regresyon yok:** x-men/monte/mavzer/altın yumruk + tüm scroll temiz.
- **bloat (6):** diriliş/franny/maksim/son_metro/yalaza/zengin — felaket mosaic reddedildi.

## Dürüst kalan sınır
Ağır-dokulu hareketli zeminde (mumya stilize-kredi, drakula-tipi) residual tekrar/over-split tam çözülmedi — bg her metin-sinyalini (dHash) kirletiyor. Tam temizlik **footage-bastırma** gerektirir (kullanıcı şimdilik erteledi: "yazı net okunuyorsa arka-plan sorun değil"). İsimler her durumda mevcut + okunur.

## Dosyalar
- Kod: `E:\MITAS\OCR-worktree\db_compose_master.py`
- Havuz-runner: `E:\MITAS\OCR-worktree\_master_pool_run.py`
- Çıktı: `E:\MITAS\OCR-worktree\db_masters_master\<film>\cikis\{master.png, master_slit.png, master_mosaic.png, manifest.json}`
