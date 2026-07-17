# MASTER-PNG — GENEL DURUM ve STRATEJİK KARAR NOKTASI
> 2026-06-14 · jenerik (film credits) → tek uzun okunabilir görüntü ("master PNG") · MITAS

## 0. KAVRAM (Çağatay'ın icadı)
Bir filmin jeneriğini (açılış+kapanış kredileri) **tek uzun okunabilir görüntüye** indirmek, sonra okumak. 4 jenerik tipi (2×2):
- sabit-yazı + sabit-bg · sabit-yazı + hareketli-bg · akan-yazı + sabit-bg · akan-yazı + hareketli-bg.
- Akan jenerikte yazıyı dinamik-hızda takip; sabit kartları peş peşe dizmek.

## 1. PRODUCTION'DA NE VAR (gerçek)
Master-PNG **İKİ yarı** (`compose_hybrid` ikisini döndürür):
- **METİN yarısı = `stitch_kunye`** (kare-kare OneOCR → OCR-uzayında dik → satır-başı bulanık-mode oylama → tek temiz okuma). **CANLI, production künye omurgası.** 10-film film-bench'te TÜM VLM'leri yendi (202 temiz satır/40s).
- **GÖRSEL yarısı = slitscan2 (akan) + line_mosaic (sabit)** → tek uzun PNG. **`MITAS_MASTER_PNG` bayrağı arkasında ÖLÜ** (commit a54f166023; rol-etiket gürültüsü ölçülmedi → savunmacı kapı).
- Ayrıca `dynamic_credit_mosaic.py` (Çağatay'ın dinamik-hız motoru) = AYRI, production'a bağlı değil.

## 2. BU OTURUMDA NE YAPTIK (süreç)
1. **Derleme:** dağınık çalışma (3 klasör) tek tabloya getirildi. İki nesil (Gen-1 4-kutu slit-scan / Gen-2 pipeline100 compose_hybrid).
2. **Konsey #1 (master-PNG mimarisi):** master = ARAÇ değil amaç; dünya-SOTA "track-then-aggregate-with-voting"; **COMO AGUA kazanımı dynamic'in DEĞİL compose_hybrid-master'ın** (Yaratıcı kendi geri çekti).
3. **Per-karakter oylama ÇÜRÜTÜLDÜ (ölçümle):** 8 film, 1676 satır-kümesi, adil test → per-char 1 kazanım / 78 kayıp. Arşiv-OCR hataları yapısal, karakter-bağımsız değil; mevcut satır-mode oylama bu alana uygun, temporal-oylama TAVANINDA.
4. **Defect-audit (68-ajan):** 61 ham → 20 onaylı defekt. EN BÜYÜK: `clean.py:15 tr_upper` her ASCII i→İ bozuyor (WILLIAM→WİLLİAM, 115+ canlı). AMA bunlar OKUMA katmanı (stitch/clean), master-PNG OLUŞTURMA değil — AYRI cephe.
5. **Master-PNG OLUŞTURMA QC:** 4-tip; iki kök görsel-defekt: **footage-bloat** + **hayalet-tekrar**.
6. **Hayalet kökü deşildi (3 hipotez ölçümle çürüdü):** asıl kök = `slitscan2` şeridi frame-altından alıyor, kredi alt-margini siyah → master KAPKARA → read_pos<5 reddet → line_mosaic'e düş → 3× şişme.
7. **3-FIX uygulandı + COMMIT a18c87bf37** (Sonnet uyguladı, Opus denetledi; SADECE görsel yol, production metin/clean DEĞİŞMEDİ):
   - **B (slitscan alt-margin):** şerit yazı-bölgesi altından. KANITLI — BIBI 22910→7830 kusursuz.
   - **A (line_mosaic dissolve-dedup):** görsel NCC≥0.95 bitişik tekrar. KISMİ — COLUMBIA 3×→1× tam, ama varyasyonlu/araklı tekrarı çözmez.
   - **C (footage-gate):** saf-footage slitscan bloğu (parlak<%0.5) at. Sınırlı tetiklenme.
   - Doğrulandı: 9 master ~%50 şişme-azalması, **künye 9/9 BİREBİR korundu (0 içerik-kaybı), regresyon yok.**
8. **Fix-A sınırı ölçüldü:** eski/animasyonlu held-kadro (ALICE Disney 1951) için band-dedup (K/NCC) VE kare-dedup başarısız (26→23/25 band). Sebep: tekrarlar piksel+OCR-segmentasyon varyasyonlu. AMA ALICE'in METNİ TEMİZ (18 satır, her cast 1×) → ghost SADECE GÖRSEL, veri değil.
9. **100-FİLM TAZE TEST** (pipeline100 ile C-D yeni + B taze, 3-fix'li) → **10 Sonnet gözcü** her biri 10 master'ı tek tek açıp denetledi (Opus gözle 3'ünü doğruladı, accurate):
   - **22 TEMİZ / 78 sorunlu:** FOOTAGE-BLOAT 44 · KARISIK 16 · BOŞ 9 · HAYALET 7 · OKUNAKSIZ 2.

## 3. ELİMİZDEKİ VERİLER
- DB: **506 film** (F:\REPO_GitHub\DATABASE, her filmde entry_frames/exit_frames).
- İşlenmiş: ~89 cache'li (B'ye kadar) + ~100+ yeni (C-D…, pipeline100 hâlâ koşuyor).
- Çıktı: her film `_MASTERS/<film>__{giris,cikis}.png` (görsel) + `_KUNYE/...txt` (metin) + `_CACHE`.
- Cache idx+ocr_pos sayesinde `recompose100` ile saniyeler içinde yeniden-dizilebilir (CLIP/OCR'sız).

## 4. GELDİĞİMİZ NOKTA (dürüst karne)
- **Fix-B = GERÇEK kazanım:** scroll-bloat kökten çözüldü, modern siyah-bg scroll'lar artık temiz.
- **Fix-A = KISMİ:** bitişik dissolve-tekrarı çözer (COLUMBIA), eski/animasyonlu varyasyonlu tekrarı çözmez (ALICE/AŞK_RÜZGARI Universal 6×→3×). Ama o ghost GÖRSEL — metin temiz.
- **Footage-bloat = AÇIK CEPHE, çözülmedi:** çeşitli/eski sette **%60** görsel footage-bloat (kredi-üstü-footage). B+A bunu HEDEFLEMEDİ.
- **İÇERİK-DURUMU (asıl önemli):** footage-bloat'lı master'da bile cast DATA'sı çoğunlukla ÇIKIYOR (CUMARTESİ 41, BATIYA 69, DAĞ ADAMLARI 140 satır — yazı footage üstünde, stitch okuyor). Footage-bloat veri için **kozmetik.**
- **Azınlık veri-sorunları:** diegetik-metin sızması (filmin ekran-yazısı kredi sanılıyor: "MOTION CAPTURE SETUP SUCCESSFUL"), BÜYÜK SESSİZLİK çıkış 600×53647px anomalisi, BOŞ-kaynak segmentler (kredisiz).
- **İçerik-bağımlılık NET:** modern siyah-bg = temiz; eski kredi-üstü-footage = footage-bloat.

## 5. DÜNYA STANDARDI (referans)
Slit-scan/strip-photography meşru; ama "tek görüntüye dik → bir kez OCR" = 2019-öncesi terk-edilen paradigma; SOTA "track-then-aggregate"; **kompozit görüntü AMAÇ değil ARAÇ, ürün = yapılandırılmış metin + güven.** MITAS'ta metin zaten `stitch_kunye` ile bu işi yapıyor (data); görsel master ikincil/artefakt.

## 6. AÇIK SORULAR / PLAN (konseye)
- **A) Footage-bloat cephesi (text-isolation/fiso):** filmi yazıdan ayır (top-hat maske + temporal-medyan) → eski-arşivin %60 görsel footage'ını temizle. BÜYÜK İŞ, riskli (renkli/koyu yazı yenebilir). Değer mi?
- **B) Veri-odaklı kal:** footage-bloat'ı KOZMETİK kabul et (data zaten çıkıyor), sadece diegetik-sızma + anomalileri çöz. Görsel-master = debug/arşiv artefaktı, OCR'ın TEK kaynağı değil.
- **C) Master-PNG'nin rolü:** görsel-master OCR'ın tek-kaynağı mı olmalı (footage-bloat onu kirletir) yoksa stitch-metin birincil + master additive-yedek mi (zaten MITAS_MASTER_PNG additive tasarımı)?
- **Stratejik gerilim:** görsel master-PNG'yi "kusursuz tek görüntü" yapmak (büyük yatırım, eski-arşivde footage-isolation) MI, yoksa "data zaten stitch'ten geliyor, görsel ikincil" kabul edip ENERJİYİ okuma-katmanı defektlerine (tr_upper, garble, diegetik-sızma) mı vermeli?
