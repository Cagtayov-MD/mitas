"""Standalone DATABASE -> master PNG composer (dual-mode, hardened).

Upgrade of the original db_compose_standalone.py with two engines:

  --mode slit    : hardened version of the original slit-scan pipeline.
  --mode mosaic  : two-pass, text-masked, motion-compensated vertical mosaic
                   (the "panoramic photo" approach). Estimates a single global
                   vertical offset per frame from TEXT (background ignored),
                   then composites every frame onto a tall canvas at its
                   integrated offset with mask-weighted blending. Static cards
                   and scrolling cast are handled by the same pass, no regime
                   switch, no per-box identity tracking.

Fixes vs the original (marked `# FIX:` inline):
  1. Resolution-normalized thresholds (calibrated to ~720x576 baseline).
  2. Natural frame sort (frame_2 < frame_10), not lexicographic.
  3. Polarity-aware text mask: tophat (bright-on-dark) OR blackhat
     (dark-on-bright), auto-detected per frame.
  4. Per-frame None guard: a corrupt/unreadable frame is skipped, not fatal.
  5. Slit strip height = actual motion (no artificial VMAX drop -> no content
     holes on fast scroll); only sub-pixel jitter and cut-residue are skipped.
  6. Optional --deinterlace (bob) fixes combing + the false-sharpness it causes.
  7. Cross-card dedup (dHash) so a repeated card is not OCR'd twice.
  8. Optional --hash-names to avoid output-folder collisions (off by default,
     keeps your existing db_masters layout untouched).
  9. Decode cache: each frame is read from disk once per segment, not 3-4x.
 10. luma-key wired to --luma-key (was dead code), manifest records source
     frame names for traceability.

Input  : F:/REPO_GitHub/DATABASE/<film>/{entry_frames,exit_frames}
Output : E:/MITAS/OCR-worktree/db_masters/<film_safe>/{giris,cikis}/master.png
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


DB = Path(r"F:\REPO_GitHub\DATABASE")
OUT = Path(r"E:\MITAS\OCR-worktree\db_masters")
SEGS = [("giris", "entry_frames"), ("cikis", "exit_frames")]

SLIT_FRAC = 0.55      # slit position as fraction of frame height
SEP_PX = 12           # black separator between stacked slit blocks
DUP_HAM = 8           # dHash hamming distance below which two cards are "same"
CONSEC_DUP = 14       # looser bound vs the IMMEDIATELY-previous block (kills "THE END" x2)
MAX_CANVAS_H = 80000  # mosaic safety cap to avoid OOM on pathological motion
READING_PASSTHROUGH_SCROLL_FRAC = float(os.environ.get("MITAS_READING_PASSTHROUGH_SCROLL_FRAC", "0.75") or 0.75)
READING_OPENING_FRAMES = int(os.environ.get("MITAS_READING_OPENING_FRAMES", "10") or 10)
READING_CARD_MIN_HOLD = int(os.environ.get("MITAS_READING_CARD_MIN_HOLD", "3") or 3)
READING_OPENING_CARD_MIN_HOLD = int(os.environ.get("MITAS_READING_OPENING_CARD_MIN_HOLD", "2") or 2)
READING_CARD_SAME_THR = int(os.environ.get("MITAS_READING_CARD_SAME_THR", "7") or 7)
READING_EARLY_SPLIT_FRAMES = int(os.environ.get("MITAS_READING_EARLY_SPLIT_FRAMES", "45") or 45)

# DEDUP-VETO: the coarse 8x8 dedup below MERGES distinct same-layout credit cards
# (role-left/name-right) -> a real card is dropped (kukla lost its crew card; x-men
# its "EDITED BY"). A 256-bit content hash (dhash_hi) VETOES the merge when content
# clearly differs. Completeness-safe by construction: only flips drop->keep, never
# keep->drop. Validated on 47 films (0 content loss). Default ON.
DEDUP_HIRES = os.environ.get("MITAS_MASTER_DEDUP_HIRES", "1") == "1"
DEDUP_HI_SIZE = int(os.environ.get("MITAS_DEDUP_HI_SIZE", "16"))
DEDUP_TDIFF = int(os.environ.get("MITAS_DEDUP_TDIFF", "40"))  # hi-res hamming above which two cards are DISTINCT (rescue)

# HİBRİT-DY (şartname: outputs/MASKELI_DY_KONTROLLU_GECIS_SARTNAME_2026-07-09.md).
# slitscan hız-kestirimi kanal seçimi: "0"=KAPALI (bit-identik eski yol; yeni fonksiyonlar
# hiç çağrılmaz), "golge"=karar+seriler AYRI sidecar'a yazılır, piksel/manifest değişmez,
# "1"=karar uygulanır (FULL: tam-kare dy; DEMOTE: allow_demote'lu çağrıda None→statik-fallback).
# Ölçülmüş zemin: donmuş-arkaplan dizi jeneriğinde şişik maske (cov 0.576) maskeli-dy'yi
# çökertti (105/120 skip), tam-kare 31.63'ü kusursuz ölçtü; ters yönde (footage-hareketli)
# maskeli doğruydu → içerik-koşullu seçim şart, tek-metrik iki yönde de batıyor.
SLIT_DY_HYBRID = os.environ.get("MITAS_SLIT_DY_HYBRID", "0").strip().lower()
# Eşikler — KANITSIZ-VARSAYILAN: gölge korpusu ayrılabilirlik-kanıtıyla kalibre edilecek
# (sağlam-p99 < eşik < patolojik-min). vmin/vmax'a DOKUNULMAZ.
SLIT_HY_COV_THR = float(os.environ.get("MITAS_SLIT_HY_COV_THR", "0.40"))
SLIT_HY_SKIP_THR = float(os.environ.get("MITAS_SLIT_HY_SKIP_THR", "0.5"))
SLIT_HY_NCOIN_NULL = 1
SLIT_HY_MIN_MEAS = 8          # bundan kısa run'da istatistik anlamsız → hibrit karar verilmez
HYBRID_LOG: list = []          # gölge kayıtları; process_film koşu sonunda sidecar'a boşaltır


# --------------------------------------------------------------------------- #
# MITAS_MASTER_V2 — Görev M4 (docs/MITAS_Master_Dup_Kok_Sebep_Plani_v1.md) kök-sebep
# fix'leri (F1: bu commit; F2/F3 sonraki commit'lerde eklenecek) bu bayrak ARKASINDA.
# KRİTİK: bayrak MODÜL YÜKLEME zamanında DEĞİL, her compose_reading_runaware/
# compose_slit ÇAĞRISINDA os.environ'dan okunur (_v2_enabled()) -- böylece aynı
# süreçte (örn. bit-parite testinde) flag AÇIK/KAPALI iki çağrı art arda yapılabilir.
# Bayrak KAPALI (varsayılan) -> bu fonksiyonların hiçbiri çağrılmaz, eski kod yolu
# bit-birebir (np.array_equal kanıtı: harness/master_dup/test_bit_parite.py).
def _v2_enabled() -> bool:
    return os.environ.get("MITAS_MASTER_V2", "0").strip() == "1"


# F1 (H2 kök-sebep: ardışık-OLMAYAN kart tekrarı gardı yoktu, 60/112 filmde birincil
# hipotez) -- global kart kaydı eşikleri. KONSEY KARARI (2026-07-23, GLM tam katılım):
# kapı-1 dHash ham eşiği 2'den 4'e gevşetildi (codec artefaktı payı); kapı-2 hizalı-
# maske faz-korelasyon yanıtı >=0.8; kapı-3 hizalı-maske XOR fark-oranı (toplam +
# 32px bant-yerel) -- bant-yerel kontrol tek IoU sayısı yerine, çünkü iki kart genel
# olarak örtüşse bile TEK bir bantta (örn. isim satırı) farklıysa bu "aynı" değil
# "farklı kredi" demektir; herhangi bir kapı tutmazsa kart KORUNUR (yanlış-silmeye
# ASLA yatma).
F1_HASH_GATE = 4
F1_RESP_GATE = 0.8
F1_TOTAL_DIFF_GATE = 0.05   # skip-audit (M4 adım 5e) özdeş-olmayan atlama bulursa ->0.03
F1_BAND_DIFF_GATE = 0.30
F1_BAND_PX = 32             # KONSEY KARARI: sabit 32px (çözünürlüğe göre ölçeklenmez)

# F1b DÜZELTMESİ (2026-07-23 gece, orkestratör ölçümleri -- docs/MITAS_Master_Dup_
# Kok_Sebep_Plani_v1.md "F1b DÜZELTMESİ"): F1'in dHash aday kapısı GRENLİ donuk-
# sahne sayfalarında hiç tetiklenmiyor (film greni textmask-dHash'i ham<=4'ün çok
# ötesine savuruyor). F1b, hash ön-eleme OLMADAN gri (metin maskesi DEĞİL) tam-kare
# görüntüyü faz-hizalayıp doğrudan piksel farkı ölçer (kalibre eşikler -- ölçülmüş,
# marjlı: aynı-donuk çiftler 0.005-0.045/0.005-0.080, farklı kartlar 0.087+/0.130+).
# Salt piksel kapısı TEK BAŞINA yeterli DEĞİL (görsel kanıt: farklı-altyazılı bir
# çiftin piksel farkı, gren farkından ayırt edilemiyor) -- bu yüzden piksel-aday
# bulununca PaddleOCR TextDetection (det-only, TEMBEL init, yalnız v2 + yalnız
# aday sayfalarda) ile doğrulanır: iki sayfada da kutu YOKSA (donuk sahne, kaybolacak
# metin yok) veya kutu sayıları+konumları+içerik NCC'si eşleşiyorsa (özdeş metin
# tekrarı) skip; aksi halde (kutu sayısı/konum/NCC uyuşmuyorsa -- farklı altyazı,
# farklı "Gün 1/Gün 2" rakamı vb.) KORU. Eski dHash+XOR yolu (F1) DEĞİŞMEDEN kalır;
# F1b yalnız F1 eşleşme BULAMADIĞINDA devreye giren EK bir kapı.
F1B_GLOBAL_DIFF_GATE = 0.06
F1B_BAND_DIFF_GATE = 0.10
F1B_NCC_GATE = 0.90
F1B_CENTER_TOL = 0.10

# F1c KARARI (2026-07-24 M4-sonu teşhisi -- docs/MITAS_Master_Dup_Kok_Sebep_Plani_v1.md
# "F1c KARARI"): F1b'nin metin-yolu bazı donuk (statik/kredisiz) sayfa çiftlerinde
# TEK KÜÇÜK HAYALET kutu buluyor -- det, doku/özne hareketini kutu sanıyor (gözlenen
# skor 0.7-0.93); sayfa böylece "text" yoluna düşüyor ama doku-NCC (gözlenen 0.29-0.69)
# eşiği (0.90) doğal olarak tutmuyor -> KORU (yanlış-negatif: gerçek tekrar silinmiyor).
# Alan/skor filtresi RİSKLİ (YAKIN_PLAN'ın gerçek altyazı kutusu da küçük -- filtre onu
# da öldürür, İÇERİK KAYBI). GÜVENLİ ayrım: text-yolu REDDETTİĞİNDE (kutu sayısı/konumu
# uyuşmuyor YA DA NCC eşiği tutmuyor) tartışmalı kutulara PaddleOCR REC (rec-only,
# TEMBEL init, yalnız v2 + yalnız bu aday-çiftte) uygulanır -- rec BOŞ ya da güven<0.6
# olan kutu HAYALET sayılır (yok say). Hayalet elendikten sonra: iki sayfada da gerçek
# kutu kalmadıysa "distant-dup-scene" (kaybolacak metin yok); gerçek kutular kaldıysa
# normalize (küçük-harf, noktalama/boşluk sadeleştir) metin EŞİTLİĞİ şartıyla
# "distant-dup-rec"; aksi halde (gerçek metinler FARKLI -- örn. YAKIN_PLAN'ın farklı
# altyazısı) None -- KORU. Maliyet sınırlı: yalnız piksel-benzer aday çiftlerinde
# (F1b'nin global/band-fark kapısını geçmiş sayfalarda).
F1C_REC_CONF_GATE = 0.6

# K1 (Görev M8, MITAS_Master_Dup_Kok_Sebep_Plani_v1.md "M8: Ex sağlık turları"):
# Ex_Frame korpusunda film-içi aynı-kart/farklı-kart çiftleriyle YENİDEN kalibre
# edilen eşikler (harness/master_dup/kalibrasyon_k1.py) + GÜVENLİK hakem kararı:
# "rec-eşitlik yolu kalibre eşiklerle çalışır; 0-kutu SAHNE-birleştirme yolu
# YALNIZ ÇOK SIKI piksel-özdeşlikte (global_fark<0.02); rec boş/conf<0.6 ->
# DAİMA koru." Bu, F1c'nin "hayalet-kutu elendikten sonra iki sayfa da
# gerçek-kutusuz kalırsa scene-skip" kuralını SIKILAŞTIRIYOR: eskiden bu dal
# yalnız F1B_GLOBAL/BAND_DIFF_GATE'in (candidate ön-filtresi, gevşek) altında
# kalan HERHANGİ bir çiftte tetiklenebiliyordu; artık "sahne" kararı ayrıca
# K1_SCENE_PIXEL_IDENTIK_GATE'in de altında olmayı ŞART koşuyor -- piksel
# gerçekten özdeşse det'in kaçırdığı silik metin bile tutulan kopyada birebir
# vardır (içerik-kaybı riski matematiksel kapalı), aksi halde KORU.
K1_SCENE_PIXEL_IDENTIK_GATE = 0.02

# K1: "koşu-içi TÜM-ÇİFT karşılaştırma ... aday tavanı 50/koşu" -- kayıt
# (card_registry) taraması, pathological (çok-kartlı, ör. uzun oyuncu listesi)
# filmlerde O(n^2) maliyetini sınırlamak için en-yakın-tarihli N kayıtla
# sınırlanır (H2'nin "ÖNCEKİ TÜM kartlar" hedefiyle çelişmez -- pratikte
# tekrarlar birkaç kart arayla olur, çok-uzak eşleşme nadir/kabul edilebilir
# artık-risk, plan metninde açıkça sanılan bir ödünleşim).
F1_REGISTRY_CAP = 50

# K1: rec-çağrı sayacı (film başına, clear_cache() ile sıfırlanır) -- süre/
# maliyet gözlemi için manifest'e yazılır, >REC_CALL_WARN_ESIK olursa uyarı.
REC_CALL_WARN_ESIK = 200

# F2 (H1 kök-sebep: slit dy tahmin hatası -> bitişik dilimlerde satır tekrarı) --
# ardışık iki slit/scroll bloğu (aralarında hiç statik/kart bloğu YOKSA) dikiş
# örtüşmesi için NCC ile hizalanır; en iyi hizada benzerlik>=0.9 ise örtüşen kısım
# yeni bloğun BAŞINDAN kırpılır. "dur-devam koruması": kırpma segment yüksekliğinin
# yarısını asla aşmaz (gerçek/uzun scroll içeriğinin yanlışlıkla silinmesini önler).
F2_PROBE_PX = 200
F2_NCC_GATE = 0.9

# F3 (H3 kök-sebep: dy-kanıtlı koşu kısa diye statik/sayfa moduna düşüyordu) --
# split_runs_reading kısa-run demote kararında, medyan |dy| bu eşiğin üstündeyse VE
# korelasyon kanıtı (faz-korelasyon yanıtı) gürültü tabanının üstündeyse run "R"
# (slit) kalır, "S"(sayfa/kart)'a düşemez. 30px KONSEY KARARI (titreme/gate-weave
# bandı 0-15px'in güvenle üstü). Yanıt tabanı (0.15) uygulayıcı takdiri -- gürültüde
# phaseCorrelate yanıtı bunun belirgin altında kalır; council/Çağatay onayına açık.
F3_RUN_DY_FLOOR_PX = 30.0
F3_RUN_RESP_FLOOR = 0.15
# M4 doğrulama bulgusu (worst-10 pilotu, 1999-0407 KÜÇÜK_KAHRAMAN): bazı filmlerde
# gerçek scroll hızı ~p.cut eşiğine denk geliyor (örn. p.cut=33.6px, ölçülen dy
# -32..-34px arası salınıyor) -- bu, TEK KARELİK "R" parçacıklarının "C"(kesim) ile
# art arda gelmesine yol açıyor. Medyan tek örnekten güvenilir değil (gürültü/kesim
# sınırında yanlış-pozitif rescue riski); "F3 eşiğini yükselt" (plan M4 adım 5e
# kaçış maddesi) burada uygulanıyor: en az 3 kare (mevcut min_scroll tabanıyla
# aynı konvansiyon) olmadan rescue YOK.
F3_RUN_MIN_FRAMES = 3

# F3b (MITAS_MASTER_V2, H3 kök-sebep ARTIĞI -- docs/MITAS_Master_Dup_Kok_Sebep_Plani_v1.md
# kök-sebep turu, bağımsız denetim: harness/master_dup/mod_denetim.py, taban koşusunda
# 137/427 "mod hatası"). F3 (yukarısı) yalnız raw etiketi zaten "R" olan KISA patlamaları
# kurtarır. Burada hedeflenen kusur farklı: kredi koyu/düz zemin üstünde kayarken TÜM-KARE
# phaseCorrelate (split_runs_reading'in birincil sinyali) ARKA PLAN tarafından domine
# edilip dy≈0 ölçüyor -- raw etiket hiç "R" olmuyor, koşu baştan "S" (statik/sayfa)
# kalıyor, kayan jenerik tekrarlı statik-sayfa olarak derleniyor (görsel kanıt:
# acemiler-cetesi, benimle-dans-et). Çözüm: estimate_offsets() ile AYNI maskeleme
# deseniyle (text_mask + 11x11 dilate + maske-dışını sıfırla -- bkz. _text_masked_dy_series)
# METİN-MASKELİ dy de hesaplanır; nihai "S" koşusu bu ikinci sinyalle mod_denetim.py'nin
# TAM AYNI imzasıyla yeniden sınanır: kayan_oran (|dy|>2px payı) >= 0.35 VE monoton
# (baskın-yön payı, kayan alt-kümesinde) >= 0.75 VE medyan|dy| (kayan alt-kümesinde)
# >= F3_RUN_DY_FLOOR_PX (mevcut gate-weave/titreme tabanıyla PAYLAŞILIYOR -- yeni bir
# eşik icat edilmiyor). Üçü de tutarsa "S" -> "R" (slit'e gider). response>0.10 kapısı
# mod_denetim.py ile birebir aynı (güvenilmez korelasyon tepesini eler). Bayrak kapalıyken
# ya da diziler verilmediyse bu geçiş hiç çalışmaz -- eski davranış bit-birebir korunur.
F3B_KAYAN_FLOOR_PX = 2.0       # mod_denetim.py: "anlamlı kayma" eşiğiyle AYNI
F3B_KAYAN_ORAN_MIN = 0.35      # mod_denetim.py imzasıyla AYNI
F3B_MONOTON_MIN = 0.75         # mod_denetim.py imzasıyla AYNI
F3B_RESP_FLOOR = 0.10          # mod_denetim.py: güvenilmez faz-korelasyon tepesini eler

# F4 -- Şerit-Atlası (Görev M10, docs/MITAS_Master_Dup_Kok_Sebep_Plani_v1.md,
# KONSEY OYBİRLİĞİ hakem sentezi -- Nemotron O2+/Kimi S5 tasarımı). Kanıt (M9):
# kalan-91'in %80'i (S2=73) YAVAŞ-KAYAN bir listenin "statik kart" sanılıp
# örtüşen sayfalara aşırı bölünmesi (çift-mesafe medyanı 4 kare); F1/F1b/F1c'nin
# "uzak kart" varsayımı bu popülasyonda neredeyse hiç tetiklenmiyor. F4, "statik"
# koşunun ARDIŞIK sayfalarını dikey NCC ile zincir-hizalar; zincir kurulursa TÜM
# içerik TEK atlas şeridine taşınır (kırpma-hatası riski yapısal olarak yok --
# yalnız örtüşen kısım atılır, benzersiz kısım hep korunur). Zincir KURULAMAZSA
# (gerçek farklı-içerikli kart koşusu -- NCC düşük) otomatik veto, sayfalar AYNEN
# kalır. Rec-doğrulama (F1b/F1c motorlarını yeniden kullanır) ZORUNLU ikinci kapı.
ATLAS_DY_MIN_PX = 3.0        # dy≈0 çiftler zincire girmez -- F1b/F1c dedup yoluna zaten düşer
# ATLAS_RESP_GATE: F3_RUN_RESP_FLOOR (0.15) ile AYNI değer -- aynı fiziksel sinyal
# (1.25fps gerçek/gürültülü Ex_Frame görüntüsünde phaseCorrelate yanıtı), aynı
# proje-kalibreli gürültü tabanı. Ölçülmüş kanıt (gecmisten-gelen pilot, GÖRSEL
# doğrulanmış gerçek kayan-liste çifti): response=0.31-0.61 -- 0.5'lik ilk
# varsayım gerçek çekimde GERÇEK eşleşmeleri reddediyordu. Zayıf ön-eleme --
# asıl doğrulama NCC + ZORUNLU rec-token denetimi (md.2).
ATLAS_RESP_GATE = 0.15
# ATLAS_NCC_GATE: F1B_NCC_GATE (0.90) kutu-içi lokal NCC için kalibre edilmişti
# (arka plan gürültüsü yok); tüm-sayfa örtüşme NCC'si (metin+arka plan karışık,
# büyük kaymalarda warp-ekstrapolasyonu da eklenince) doğal olarak daha düşük
# çıkıyor -- ölçülmüş kanıt (gecmisten-gelen, GÖRSEL doğrulanmış İKİ gerçek
# eşleşme, AYNI zincir): ncc=0.82 (büyük kayma/düşük yanıt) ve 0.8996 (küçük
# kayma/yüksek yanıt). NCC burada ADAY kapısı -- asıl içerik-güvenliği ZORUNLU
# rec-token alt-küme denetimi (md.2, "NCC-tek başına RED" konsey kararı).
# Ölçülmüş kanıta göre gevşetildi; G0 (333 sağlıklı filmde 0-ateşleme) bu
# seçimi ampirik olarak doğrulayacak/reddedecek.
ATLAS_NCC_GATE = 0.80
# ATLAS_DY_TOL_ORAN -- REVİZYON (2026-07-24, koordinatör direktifi + ölçülmüş teşhis):
# dy-hız tutarlılığı artık zincir-KIRICI kapı DEĞİL, yalnız manifest TEŞHİS alanı.
# Ölçülmüş kanıt (hizli-silah, GÖRSEL doğrulanmış gerçek yavaş-kayan liste):
# 4/4 çift NCC'yi geçti (0.9064-0.9741) ama dy-hızlar -19.75/-37.71/-51.00/-23.31
# px/kare -- ardışık oranlar 0.48/0.26/0.54, ±%20 hepsini reddediyordu (±%35 bile
# 2/3'ünü). KÖK SEBEP yapısal: sayfalar metin-bandına kırpılıyor (text_rows, y0
# sayfa-başına farklı) -- kırpımlar-arası dy = gerçek-kayma + kırpım-orijin-farkı;
# sabit hızlı scroll'da bile çift-dy'si değişken. md.3'ün bu şartla önlemek
# istediği senaryo (satır-periyot yanlış-kilitleme) DİKİŞ-DÜZEYİ rec sıfır-çelişki
# kapısıyla (ATLAS_SEAM_*) yakalanır: yanlış satıra kilitlenen hizalamada örtüşme
# bölgesinin iki kırpımı FARKLI gerçek metin taşır -> çelişki -> atlas atılır.
ATLAS_DY_TOL_ORAN = 0.35     # yalnız manifest'teki dy_tutarli teşhis bayrağı için
ATLAS_OVERLAP_MIN_SATIR = 2  # örtüşme >= 2 satır-yüksekliği (hakem sentezi md.3)
# ATLAS_MIN_CHAIN_EDGES -- REVİZYON (koordinatör direktifi): 2-sayfalı çiftlerde
# tek-dikiş + dikiş-rec yeterli (>=2-ardışık-çift şartı kaldırıldı; güvenlik
# NCC>=0.8 + örtüşme>=2satır + dikiş-başına rec sıfır-çelişki üçlüsünde).
ATLAS_MIN_CHAIN_EDGES = 1
# Dikiş-düzeyi rec-doğrulama (Kimi kuralının doğru uygulaması -- koordinatör
# direktifi md.2): her dikişte örtüşen bölge İKİ sayfada da fiziksel olarak var;
# iki kırpım AYRI AYRI det+rec'lenir. Konum-eşleşmiş kutu çiftlerinde İKİSİ DE
# yüksek-güvenliyse (conf>=0.8) SIFIR ÇELİŞKİ şart (kısa token birebir; uzun
# token'da -- >=6 harf -- Levenshtein<=1 kabul, OCR tek-karakter gürültüsü);
# düşük-güvenli/eşleşmemiş kutu TOLERE edilir. Bütün-atlas OCR'ı KULLANILMAZ:
# sentetik uzun şeridin bütün-OCR'ı satır-parçalanması yüzünden güvenilmez
# (ölçüldü: 59/63 sahte red -- aynı kelime farklı sayfalarda farklı garble).
ATLAS_SEAM_CONF = 0.8
ATLAS_SEAM_KISA_TOKEN = 5    # <=5 harf (isim/kısaltma boyutu): birebir şart, tolerans yok
# Kırpım-SINIRINA değen kutular çelişki denetiminden MUAF (pilot kanıtı,
# gecmisten-gelen dikiş[2,3]: örtüşme sınırı bir metin satırını ORTADAN kesince
# yarım-glifli kırpım rec'i 'dave parker 0' okudu, tam satır 'dave parker craig
# woods' -- İKİSİ AYNI FİZİKSEL SATIR, sahte çelişki). Sınır-kesiği yapısal bir
# kırpım artefaktı, gerçek içerik farkı değil; sınırdan uzak kutulardaki gerçek
# çelişkiler (yanlış-hizalama kanıtı: 'barfly' vs 'stranger') ETKİLENMEZ.
ATLAS_SEAM_KENAR_PAY = 6     # px -- kutunun üst/alt kenarı bu kadar yakınsa muaf
ATLAS_CANVAS_H_MAKS = 20000  # güvenlik: patolojik zincir büyümesine karşı mutlak tavan
ATLAS_LINE_H_VARSAYILAN = 24


# --------------------------------------------------------------------------- #
# resolution-normalized parameters
# --------------------------------------------------------------------------- #
@dataclass
class Params:
    h: int
    w: int
    thk: int          # tophat/blackhat kernel width
    tht: int          # morph binarize threshold (intensity, NOT scaled)
    min_h: int        # text component height bounds
    max_h: int
    min_w: int        # text component min width
    static_dy: float  # state-machine thresholds (slit)
    scroll_dy: float
    cut: float        # |dy| above this == cut / scene change
    vmin: float       # slit: ignore sub-pixel jitter below this
    vmax: float       # slit/mosaic: |dy| above this == glitch, skip / treat as cut
    pad: int          # padding around a detected card text band
    min_hold: int


def _odd(x: int) -> int:
    x = int(round(x))
    return x if x % 2 == 1 else x + 1


def derive_params(h: int, w: int, args) -> Params:
    # FIX(1): everything spatial is a fraction of frame size; the literals below
    # reproduce the original constants at the ~720x576 baseline they were tuned on.
    return Params(
        h=h,
        w=w,
        thk=max(9, _odd(0.021 * w)),       # was 15 @ w=720
        tht=args.tht,                       # intensity threshold, resolution-independent
        min_h=max(4, round(0.009 * h)),     # was 5  @ h=576
        max_h=max(12, round(0.18 * h)),     # was 52 @ h=576; loosened so big title cards pass
        min_w=max(18, round(0.055 * w)),    # was 40 @ w=720
        static_dy=0.0026 * h,               # was 1.5 @ h=576
        scroll_dy=0.0043 * h,               # was 2.5 @ h=576
        cut=0.07 * h,                        # was 40  @ h=576
        vmin=max(1.0, 0.0018 * h),           # was 1   @ h=576
        vmax=0.5 * h,                        # FIX(5): generous; only true glitches dropped
        pad=max(4, round(0.014 * h)),        # was 8   @ h=576
        min_hold=args.min_hold,
    )


# --------------------------------------------------------------------------- #
# IO + cache
# --------------------------------------------------------------------------- #
_CACHE: dict[str, np.ndarray] = {}
_CACHE_CAP = 2000  # credit sequences are small; cap just bounds memory

# K1: film başına rec-çağrı sayacı -- process_film() her segmentte clear_cache()
# çağırdığı için (zaten var olan per-film/per-segment sıfırlama noktası) buraya
# eklendi, ayrı bir reset kancası GEREKMEDİ.
_REC_CALL_COUNT = [0]


def clear_cache() -> None:
    _CACHE.clear()
    _REC_CALL_COUNT[0] = 0


def rec_call_count() -> int:
    return _REC_CALL_COUNT[0]


def rd_cached(path: str | Path) -> np.ndarray | None:
    key = str(path)
    img = _CACHE.get(key)
    if img is not None:
        return img
    # FIX(4): imdecode returns None on a corrupt/missing file -> caller skips.
    try:
        img = cv2.imdecode(np.fromfile(key, np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        img = None
    if img is not None and len(_CACHE) < _CACHE_CAP:
        _CACHE[key] = img
    return img


def wr(path: str | Path, image: np.ndarray) -> None:
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError(f"PNG encode failed: {path}")
    encoded.tofile(str(path))


def safe(name: str, hash_names: bool) -> str:
    slug = re.sub(r"[^\w\-]+", "_", name).strip("_")
    if not hash_names:
        return slug[:70]
    # FIX(8): append a short content hash so two films that collapse to the
    # same first-70-chars slug don't overwrite each other.
    digest = hashlib.md5(name.encode("utf-8")).hexdigest()[:8]
    return f"{slug[:60]}_{digest}"


def nat_sort_key(path: str):
    # FIX(2): sort by the last integer in the filename, falling back to name.
    name = Path(path).name
    nums = re.findall(r"\d+", name)
    return (int(nums[-1]) if nums else -1, name)


# --------------------------------------------------------------------------- #
# image helpers
# --------------------------------------------------------------------------- #
def deinterlace(image: np.ndarray) -> np.ndarray:
    # FIX(6): bob deinterlace - keep one field, line-double it. Kills combing
    # (which otherwise inflates Laplacian sharpness and breaks morphology).
    top = image[::2]
    return cv2.resize(top, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_LINEAR)


def luma_key(image: np.ndarray, thr: int = 150) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    out = np.zeros_like(image)
    out[gray > thr] = image[gray > thr]
    return out


def text_mask(gray: np.ndarray, p: Params, polarity: str = "auto") -> np.ndarray:
    # FIX(3): pick tophat or blackhat based on background brightness so dark
    # text on a light background is no longer silently missed.
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (p.thk, 5))
    pol = polarity
    if pol == "auto":
        pol = "dark" if float(np.median(gray)) > 127 else "bright"
    op = cv2.MORPH_TOPHAT if pol == "bright" else cv2.MORPH_BLACKHAT
    morph = cv2.morphologyEx(gray, op, kernel)
    _, mask = cv2.threshold(morph, p.tht, 255, cv2.THRESH_BINARY)
    return mask


def has_text(mask: np.ndarray, p: Params) -> bool:
    # FIX: merge adjacent letters into a word-blob with a horizontal kernel before
    # labelling, so large display titles (tall, narrow per-letter) aren't rejected
    # by the per-letter aspect test that was tuned for small wide cast lines.
    kx = max(15, _odd(0.015 * p.w))
    merged = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_RECT, (kx, 3)))
    n_labels, _, stats, _ = cv2.connectedComponentsWithStats(merged, 8)
    for label in range(1, n_labels):
        height = stats[label, cv2.CC_STAT_HEIGHT]
        width = stats[label, cv2.CC_STAT_WIDTH]
        if p.min_h <= height <= p.max_h and width >= p.min_w and width / max(1, height) >= 1.5:
            return True
    return False


def sharpv(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def text_band(mask: np.ndarray) -> tuple[int, int] | None:
    rows = np.where(mask.sum(axis=1) > 0)[0]
    if not rows.size:
        return None
    return int(rows.min()), int(rows.max())


def text_rows(mask: np.ndarray, p: Params) -> tuple[int, int] | None:
    """Row span of TEXT-like components only — wide-short word blobs, excluding
    big/square blobs (portraits, logos). So a card crops to its NAME line(s), not
    the photo + solid-colour void (son_metro: Deneuve's name, not her portrait)."""
    kx = max(15, _odd(0.015 * p.w))
    merged = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_RECT, (kx, 3)))
    n_labels, _, stats, _ = cv2.connectedComponentsWithStats(merged, 8)
    spans = []
    for label in range(1, n_labels):
        y = int(stats[label, cv2.CC_STAT_TOP])
        hh = int(stats[label, cv2.CC_STAT_HEIGHT])
        ww = int(stats[label, cv2.CC_STAT_WIDTH])
        if p.min_h <= hh <= p.max_h and ww >= p.min_w and ww / max(1, hh) >= 1.5:
            spans.append((y, y + hh))
    if not spans:
        return None
    return min(a for a, _ in spans), max(b for _, b in spans)


def dhash(image: np.ndarray, size: int = 8) -> int:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (size + 1, size))
    diff = gray[:, 1:] > gray[:, :-1]
    bits = 0
    for value in diff.flatten():
        bits = (bits << 1) | int(value)
    return bits


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def _best_stable_candidate(candidates: list[tuple]) -> tuple[tuple | None, int | None]:
    """Choose the text-layout medoid, preferring a settled middle/later frame."""
    if not candidates:
        return None, None
    center = (len(candidates) - 1) / 2.0
    ranked = []
    for index, candidate in enumerate(candidates):
        text_hash = candidate[4]
        distance = sum(
            hamming(text_hash, other[4])
            for other_index, other in enumerate(candidates)
            if other_index != index
        )
        rel = int(candidate[2])
        ranked.append((distance, abs(rel - center), -rel, -float(candidate[0]), index))
    distance, _, _, _, index = min(ranked)
    return candidates[index], int(distance)


def _aligned_text_mask_similarity(first: np.ndarray, second: np.ndarray) -> tuple[float, float]:
    """Return phase-correlation response and aligned IoU for equal-size text masks."""
    if first is None or second is None or first.shape != second.shape:
        return 0.0, 0.0
    a = (first > 0).astype(np.float32)
    b = (second > 0).astype(np.float32)
    (dx, dy), response = cv2.phaseCorrelate(a, b)
    transform = np.float32([[1, 0, dx], [0, 1, dy]])
    aligned = cv2.warpAffine(a, transform, (a.shape[1], a.shape[0]))
    aligned_on = aligned > 0.5
    b_on = b > 0.5
    union = np.logical_or(aligned_on, b_on).sum()
    iou = np.logical_and(aligned_on, b_on).sum() / max(1, int(union))
    return float(response), float(iou)


# --------------------------------------------------------------------------- #
# MITAS_MASTER_V2 / F1 -- global kart kaydı (H2 kök-sebep) yardımcıları
# --------------------------------------------------------------------------- #
def _aligned_mask_diff_bands(first: np.ndarray, second: np.ndarray, band_px: int = F1_BAND_PX) -> dict | None:
    """F1 kapı-2/kapı-3: faz-korelasyonla hizala, toplam XOR fark-oranı + 32px'lik
    yatay bantlarda YEREL fark-oranı hesapla. Şekiller farklıysa (ya da None) None
    döner -- çağıran bunu "kapı geçmedi" (kart KORUNUR) olarak okur.

    Not: toplam fark_oranı = XOR/birleşim = 1 - IoU (matematiksel olarak
    _aligned_text_mask_similarity'nin IoU'suyla özdeş); burada AYRICA bant-yerel
    fark gerektiği için hizalanmış ikili maskeler yeniden üretiliyor (mevcut
    fonksiyon yalnız skaler döndürüyor, _aligned_text_mask_similarity'nin kendisi
    bit-parite şartı nedeniyle DEĞİŞTİRİLMEDİ)."""
    if first is None or second is None or first.shape != second.shape:
        return None
    a = (first > 0).astype(np.float32)
    b = (second > 0).astype(np.float32)
    (dx, dy), response = cv2.phaseCorrelate(a, b)
    transform = np.float32([[1, 0, dx], [0, 1, dy]])
    aligned = cv2.warpAffine(a, transform, (a.shape[1], a.shape[0]))
    aligned_on = aligned > 0.5
    b_on = b > 0.5
    union = np.logical_or(aligned_on, b_on)
    inter = np.logical_and(aligned_on, b_on)
    union_n = int(union.sum())
    fark_orani = float((union_n - int(inter.sum())) / union_n) if union_n else 0.0
    h = aligned_on.shape[0]
    max_band_fark = 0.0
    for y0 in range(0, h, band_px):
        y1 = min(h, y0 + band_px)
        band_union_n = int(union[y0:y1, :].sum())
        if band_union_n == 0:
            continue
        band_inter_n = int(inter[y0:y1, :].sum())
        band_fark = (band_union_n - band_inter_n) / band_union_n
        if band_fark > max_band_fark:
            max_band_fark = band_fark
    return {
        "response": float(response),
        "fark_orani": fark_orani,
        "max_band_fark": float(max_band_fark),
    }


def _card_distant_dup_match(
    new_thh: int,
    new_mask: np.ndarray,
    registry: list[dict],
    *,
    hash_gate: int = F1_HASH_GATE,
    resp_gate: float = F1_RESP_GATE,
    total_diff_gate: float = F1_TOTAL_DIFF_GATE,
    band_diff_gate: float = F1_BAND_DIFF_GATE,
    band_px: int = F1_BAND_PX,
) -> dict | None:
    """F1 (H2): yeni kart, kaydedilmiş ÖNCEKİ TÜM kartlarla üç-kapılı denetimden
    geçirilir (kapı-1 dHash aday, kapı-2 hizalama yanıtı, kapı-3 XOR fark-bandı).
    Herhangi bir kapı tutmazsa (ya da hiçbir aday geçmezse) None -- kart KORUNUR.
    Yalnız ilk eşleşen aday döner (registry ekleniş sırasıyla, en erken eş kart)."""
    for entry in registry:
        if hamming(new_thh, entry["dhash"]) > hash_gate:
            continue  # kapı-1: aday bile değil
        diff = _aligned_mask_diff_bands(entry["mask"], new_mask, band_px=band_px)
        if diff is None or diff["response"] < resp_gate:
            continue  # kapı-2: hizalama güvenilir değil
        if diff["fark_orani"] >= total_diff_gate or diff["max_band_fark"] > band_diff_gate:
            continue  # kapı-3: içerik yeterince farklı -> distinct kart, KORU
        return {
            "es_blok_indeksi": int(entry["block_index"]),
            "response": round(diff["response"], 4),
            "fark_orani": round(diff["fark_orani"], 4),
            "en_yuksek_bant_farki": round(diff["max_band_fark"], 4),
        }
    return None


# --------------------------------------------------------------------------- #
# MITAS_MASTER_V2 / F1b -- gren-dirençli sahne-tekrarı denetimi (H2 kök-sebep,
# F1'in dHash aday kapısı GRENLİ donuk-sahne sayfalarında hiç tetiklenmediği için)
# --------------------------------------------------------------------------- #
_F1B_DET_ENGINE = None  # TEMBEL -- yalnız v2 modda İLK aday sayfa çıktığında yüklenir


def _f1b_det_engine():
    """PaddleOCR TextDetection (det-only, ~0.02sn/sayfa) -- TEMBEL init. Flag KAPALI
    yol bu fonksiyonu ASLA çağırmaz (bit-parite: paddle'a hiç dokunulmaz)."""
    global _F1B_DET_ENGINE
    if _F1B_DET_ENGINE is None:
        os.environ.setdefault("FLAGS_json_format_model", "0")
        os.environ.setdefault("FLAGS_enable_pir_api", "0")
        from paddleocr import TextDetection
        det_name = os.environ.get("MITAS_PADDLEOCR_TEXT_DET_MODEL_NAME") or "PP-OCRv5_mobile_det"
        _F1B_DET_ENGINE = TextDetection(model_name=det_name)
    return _F1B_DET_ENGINE


def _f1b_gray_band_diff(first_gray: np.ndarray, second_gray: np.ndarray, band_px: int = F1_BAND_PX) -> dict | None:
    """F1b kapı-1: iki TAM-KARE GRİ görüntü (metin maskesi DEĞİL -- donuk/metinsiz
    sahne tekrarını da yakalamak için) arasında faz-hizalı SÜREKLİ piksel farkı.
    F1'in ikili maske XOR'undan farklı: burada 0-1 normalize edilmiş gri fark
    kullanılır (kalibrasyon: KONSEY/orkestratör ölçümleri, F1B_GLOBAL/BAND_DIFF_GATE)."""
    if first_gray is None or second_gray is None or first_gray.shape != second_gray.shape:
        return None
    a = first_gray.astype(np.float32) / 255.0
    b = second_gray.astype(np.float32) / 255.0
    hann = cv2.createHanningWindow((a.shape[1], a.shape[0]), cv2.CV_32F)
    (dx, dy), response = cv2.phaseCorrelate(a * hann, b * hann)
    transform = np.float32([[1, 0, dx], [0, 1, dy]])
    aligned = cv2.warpAffine(a, transform, (a.shape[1], a.shape[0]))
    diff = np.abs(aligned - b)
    h = diff.shape[0]
    max_band_fark = 0.0
    for y0 in range(0, h, band_px):
        y1 = min(h, y0 + band_px)
        band_fark = float(diff[y0:y1, :].mean())
        if band_fark > max_band_fark:
            max_band_fark = band_fark
    return {
        "dx": float(dx), "dy": float(dy), "response": float(response),
        "global_fark": float(diff.mean()),
        "max_band_fark": max_band_fark,
    }


def _f1b_det_boxes(gray: np.ndarray) -> list[tuple] | None:
    """Det-only kutu listesi: [(cx,cy,bw,bh normalize 0-1, x0,y0,x1,y1 piksel), ...].
    Det başarısız/kullanılamazsa None (çağıran bunu "kapı geçmedi" -- KORU -- olarak
    okur, ASLA "kutu yok" ile karıştırılmaz -- ikisi de ayrı anlam taşır)."""
    try:
        eng = _f1b_det_engine()
        bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        res = eng.predict(bgr)
    except Exception:
        return None
    h, w = gray.shape[:2]
    boxes = []
    for item in res:
        polys = item.get("dt_polys")
        if polys is None:
            continue
        for poly in polys:
            arr = np.asarray(poly, dtype=np.float32).reshape(-1, 2)
            if arr.shape[0] < 3:
                continue
            x0, y0 = float(arr[:, 0].min()), float(arr[:, 1].min())
            x1, y1 = float(arr[:, 0].max()), float(arr[:, 1].max())
            boxes.append((
                (x0 + x1) / 2.0 / max(1, w), (y0 + y1) / 2.0 / max(1, h),
                (x1 - x0) / max(1, w), (y1 - y0) / max(1, h),
                x0, y0, x1, y1,
            ))
    return boxes


def _f1b_boxes_sorted(boxes: list[tuple]) -> list[tuple]:
    return sorted(boxes, key=lambda b: (round(b[1], 2), round(b[0], 2)))


def _f1b_boxes_match(boxes_a: list[tuple], boxes_b: list[tuple], *, center_tol: float = F1B_CENTER_TOL) -> bool:
    """Kutu sayıları eşit VE (y sonra x'e göre sıralı) her kutu merkezi toleransta
    eşleşiyor mu. Farklı-altyazı / farklı "Gün 1"-"Gün 2" gibi konum/sayı farklı
    içerikler burada elenir (kutu sayısı/konumu tutarsız kalır)."""
    if len(boxes_a) != len(boxes_b) or not boxes_a:
        return False
    for a, b in zip(_f1b_boxes_sorted(boxes_a), _f1b_boxes_sorted(boxes_b)):
        if abs(a[0] - b[0]) > center_tol or abs(a[1] - b[1]) > center_tol:
            return False
    return True


def _f1b_box_ncc(gray_a: np.ndarray, gray_b: np.ndarray, boxes_a: list[tuple], boxes_b: list[tuple]) -> float:
    """Eşleşmiş kutu çiftlerinin HER birinde NCC hesapla, EN DÜŞÜĞÜ döndür (tek bir
    kutu bile farklıysa -- örn. altyazı metni değişmiş -- "özdeş metin" iddiası
    çöker). Kutu boyları farklıysa küçüğe yeniden ölçeklenir (NCC eşit-şekil ister)."""
    worst = 1.0
    a_f = gray_a.astype(np.float32)
    b_f = gray_b.astype(np.float32)
    for a, b in zip(_f1b_boxes_sorted(boxes_a), _f1b_boxes_sorted(boxes_b)):
        ax0, ay0, ax1, ay1 = a[4:8]
        bx0, by0, bx1, by1 = b[4:8]
        pa = a_f[int(ay0):max(int(ay0) + 1, int(ay1)), int(ax0):max(int(ax0) + 1, int(ax1))]
        pb = b_f[int(by0):max(int(by0) + 1, int(by1)), int(bx0):max(int(bx0) + 1, int(bx1))]
        if pa.size == 0 or pb.size == 0:
            return 0.0
        th, tw = min(pa.shape[0], pb.shape[0]), min(pa.shape[1], pb.shape[1])
        if th < 2 or tw < 2:
            return 0.0
        pa_r = cv2.resize(pa, (tw, th)) if pa.shape[:2] != (th, tw) else pa
        pb_r = cv2.resize(pb, (tw, th)) if pb.shape[:2] != (th, tw) else pb
        a0 = pa_r - pa_r.mean()
        b0 = pb_r - pb_r.mean()
        denom = float(np.sqrt(float((a0 * a0).sum())) * np.sqrt(float((b0 * b0).sum())))
        ncc = float((a0 * b0).sum() / denom) if denom > 1e-6 else 0.0
        if ncc < worst:
            worst = ncc
    return worst


# --------------------------------------------------------------------------- #
# MITAS_MASTER_V2 / F1c -- hayalet-kutu REC hakemi (H2 kök-sebep artığı; bkz.
# docs/MITAS_Master_Dup_Kok_Sebep_Plani_v1.md "F1c KARARI")
# --------------------------------------------------------------------------- #
_F1C_REC_ENGINE = None  # TEMBEL -- yalnız F1b'nin text-yolu REDDETTİĞİ anda yüklenir


def _f1c_rec_engine():
    """PaddleOCR TextRecognition (rec-only) -- TEMBEL init. Flag KAPALI yol VE F1b'nin
    text-yolunun zaten skip/koru kararı verdiği durumlar bu fonksiyonu HİÇ çağırmaz
    (bit-parite: paddle'a hiç dokunulmaz; maliyet: yalnız gerçekten tartışmalı adayda)."""
    global _F1C_REC_ENGINE
    if _F1C_REC_ENGINE is None:
        os.environ.setdefault("FLAGS_json_format_model", "0")
        os.environ.setdefault("FLAGS_enable_pir_api", "0")
        from paddleocr import TextRecognition
        rec_name = os.environ.get("MITAS_PADDLEOCR_TEXT_REC_MODEL_NAME") or "PP-OCRv5_mobile_rec"
        _F1C_REC_ENGINE = TextRecognition(model_name=rec_name)
    return _F1C_REC_ENGINE


def _f1c_normalize_text(s: str) -> str:
    """Küçük-harf + noktalama/boşluk sadeleştirme -- iki bağımsız REC okumasının
    biçimsel farkları (nokta, çoklu boşluk, vb.) yüzünden aynı metnin yanlışlıkla
    'farklı' sayılmasını önler (F1c metin-eşitliği karşılaştırması için)."""
    s = s.lower()
    s = re.sub(r"[^\w]+", " ", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip()


def _f1c_rec_text(gray: np.ndarray, box: tuple) -> tuple[str, float]:
    """Bir det-kutusunu kırp, REC uygula -> (ham metin, güven). Kutu boş/rec
    başarısızsa ("", 0.0) -- çağıran bunu HAYALET olarak okur (F1c_REC_CONF_GATE
    ile birlikte: boş metin zaten güven eşiğinin altına düşer)."""
    x0, y0, x1, y1 = box[4:8]
    h, w = gray.shape[:2]
    xi0, yi0 = max(0, int(x0)), max(0, int(y0))
    xi1 = min(w, max(xi0 + 1, int(x1)))
    yi1 = min(h, max(yi0 + 1, int(y1)))
    crop = gray[yi0:yi1, xi0:xi1]
    if crop.size == 0:
        return "", 0.0
    try:
        eng = _f1c_rec_engine()
        res = eng.predict(cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR))
    except Exception:
        return "", 0.0
    if not res:
        return "", 0.0
    item = res[0]
    return str(item.get("rec_text") or ""), float(item.get("rec_score") or 0.0)


def _f1c_rec_boxes(gray: np.ndarray, boxes_sorted: list[tuple]) -> list[tuple[str, float]]:
    """Sıralı (okuma sırasıyla) kutu listesindeki HER kutuya REC uygula ->
    [(normalize_metin, güven), ...]. Sıra korunur ki A/B metin karşılaştırması
    konum-tutarlı kalsın."""
    out = []
    for box in boxes_sorted:
        text, score = _f1c_rec_text(gray, box)
        out.append((_f1c_normalize_text(text), score))
    _REC_CALL_COUNT[0] += len(boxes_sorted)  # K1: rec-çağrı sayacı
    return out


# --------------------------------------------------------------------------- #
# K3 (Görev M8): korunması-gereken-farklı-metin kanıtı -- normalize Levenshtein
# + token-Jaccard. Küçük, bağımsız (harici kütüphane yok) -- composer'ın
# harness/master_dup/* katmanına bağımlılığı OLMAMASI için burada tanımlı
# (harness kendi kalibrasyon/recall script'lerinde bu modülü SALT-OKUNUR
# import eder, tersi asla).
# --------------------------------------------------------------------------- #
K3_PROTECTED_CONF_GATE = 0.7
K3_PROTECTED_LEV_GATE = 3
K3_PROTECTED_JACCARD_GATE = 0.7


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        prev = cur
    return prev[-1]


def _token_jaccard(a: str, b: str) -> float:
    ta, tb = set(a.split()), set(b.split())
    if not ta and not tb:
        return 1.0
    union = ta | tb
    return len(ta & tb) / len(union) if union else 1.0


def _k3_protected_evidence(
    rec_a: list[tuple[str, float]], rec_b: list[tuple[str, float]],
    *, conf_gate: float = K3_PROTECTED_CONF_GATE,
    lev_gate: int = K3_PROTECTED_LEV_GATE, jaccard_gate: float = K3_PROTECTED_JACCARD_GATE,
) -> dict | None:
    """K3: iki karede de det>=1 kutu + rec conf>=0.7 (STRICT -- F1C_REC_CONF_GATE'in
    0.6'sından farklı, K3'e özgü daha sıkı bir eşik) + normalize Levenshtein>=3
    VEYA token-Jaccard<=0.7 ise korunması-gereken-farklı-metin kanıtı üretir.
    Karar mantığını (skip/koru) DEĞİŞTİRMEZ -- yalnız manifest KAYDI için."""
    real_a = [(n, s) for n, s in rec_a if n and s >= conf_gate]
    real_b = [(n, s) for n, s in rec_b if n and s >= conf_gate]
    if not real_a or not real_b:
        return None
    text_a = " ".join(n for n, _ in real_a)
    text_b = " ".join(n for n, _ in real_b)
    lev = _levenshtein(text_a, text_b)
    jac = _token_jaccard(text_a, text_b)
    if lev < lev_gate and jac > jaccard_gate:
        return None
    return {
        "text_a": text_a, "text_b": text_b,
        "conf_a": round(min(s for _, s in real_a), 4),
        "conf_b": round(min(s for _, s in real_b), 4),
        "protected": True,
        "levenshtein": lev, "jaccard": round(jac, 4),
    }


def _card_distant_dup_match_f1b(
    new_gray: np.ndarray,
    registry: list[dict],
    *,
    global_gate: float = F1B_GLOBAL_DIFF_GATE,
    band_gate: float = F1B_BAND_DIFF_GATE,
    ncc_gate: float = F1B_NCC_GATE,
    center_tol: float = F1B_CENTER_TOL,
    rec_conf_gate: float = F1C_REC_CONF_GATE,
    scene_pixel_identik_gate: float = K1_SCENE_PIXEL_IDENTIK_GATE,
    registry_cap: int = F1_REGISTRY_CAP,
) -> tuple[dict | None, dict | None]:
    """F1b: F1 (dHash+XOR) eşleşme BULAMADIĞINDA çağrılan EK kapı. Hash ön-elemesi
    YOK -- doğrudan gri piksel-benzerlik adayı arar, sonra det-only kutu kapısıyla
    doğrular. Üç karar yolu: "distant-dup-scene" (iki sayfada da metin kutusu YOK
    -- donuk sahne, kaybolacak içerik yok -- K1 hakem kararı: YALNIZ piksel
    global_fark<scene_pixel_identik_gate ise, aksi KORU), "distant-dup-text"
    (kutu sayısı+konumu+NCC'si eşleşen özdeş metin tekrarı), "distant-dup-rec"
    (F1c -- kutu-kapısı REDDETTİĞİNDE, yani kutu sayısı/konumu uyuşmadığında YA
    DA NCC eşiği tutmadığında, tartışmalı kutulara REC hakemi devreye girer: rec
    boş/güven<0.6 olan kutu HAYALET sayılır, elenir; iki sayfada da gerçek kutu
    kalmazsa -- K1 hakem kararı: YALNIZ piksel de özdeşse -- scene, kalan gerçek
    kutu metinleri normalize-eşitse rec-skip). Herhangi bir kapı tutmazsa (piksel
    farkı büyük, det başarısız, gerçek metinler farklı, ya da "sahne" kararı
    piksel-özdeşlik şartını tutmuyorsa) None -- kart KORUNUR.

    K1: `registry`, en-yakın-tarihli `registry_cap` kayıtla sınırlı taranır
    (maliyet sınırı, "aday tavanı 50/koşu" -- bkz. F1_REGISTRY_CAP tanımı).

    Dönüş (K3, Görev M8): `(match, korunan_kanit)`. `match` eskisiyle BİREBİR
    aynı sözleşme (skip kararı, None=KORU -- ÇAĞIRAN DAVRANIŞI DEĞİŞMEDİ).
    `korunan_kanit`: KORUNAN bir kart, K3'ün sıkı kanıt şartını (iki karede de
    det>=1 + rec conf>=0.7 + normalize Levenshtein>=3 VEYA Jaccard<=0.7)
    karşılıyorsa {text_a,text_b,conf_a,conf_b,protected:True,...} -- yalnız
    KAYIT amaçlı, skip/koru kararını ETKİLEMEZ. İlk karşılanan adayda durur."""
    boxes_b: list[tuple] | None = None
    boxes_b_ready = False
    boxes_b_rec: list[tuple[str, float]] | None = None
    korunan_kanit: dict | None = None
    for entry in registry[-registry_cap:] if registry_cap else registry:
        prev_gray = entry.get("gray")
        if prev_gray is None:
            continue
        diff = _f1b_gray_band_diff(prev_gray, new_gray)
        if diff is None:
            continue
        if diff["global_fark"] >= global_gate or diff["max_band_fark"] >= band_gate:
            continue  # piksel-aday bile değil
        if not boxes_b_ready:
            boxes_b = _f1b_det_boxes(new_gray)
            boxes_b_ready = True
        if boxes_b is None:
            continue  # det başarısız -- güvenli taraf: KORU
        boxes_a = entry.get("f1b_boxes")
        if boxes_a is None:
            boxes_a = _f1b_det_boxes(prev_gray)
            entry["f1b_boxes"] = boxes_a  # sayfa-başına önbellek -- yalnız BİR kez det
        if boxes_a is None:
            continue
        base = {
            "es_blok_indeksi": int(entry["block_index"]),
            "global_fark": round(diff["global_fark"], 4),
            "max_band_fark": round(diff["max_band_fark"], 4),
            "det_kutular_a": len(boxes_a),
            "det_kutular_b": len(boxes_b),
        }
        # K1 GÜVENLİK HAKEM KARARI: "sahne" (distant-dup-scene) kararı candidate
        # ön-filtresinden (global_gate/band_gate, gevşek) DAHA SIKI bir ikinci
        # piksel-özdeşlik şartına tabi -- yalnız bu iki dalın (0-kutu VE
        # hayalet-elendikten-sonra-0-gerçek-kutu) ortak şartı.
        pixel_ozdes = diff["global_fark"] < scene_pixel_identik_gate
        if len(boxes_a) == 0 and len(boxes_b) == 0:
            if pixel_ozdes:
                return {**base, "karar_yolu": "distant-dup-scene"}, korunan_kanit
            continue  # kutu yok ama piksel özdeş DEĞİL -- KORU, sıradaki adaya bak
        if _f1b_boxes_match(boxes_a, boxes_b, center_tol=center_tol):
            ncc = _f1b_box_ncc(prev_gray, new_gray, boxes_a, boxes_b)
            if ncc >= ncc_gate:
                return {**base, "karar_yolu": "distant-dup-text", "kutu_ncc": round(ncc, 4)}, korunan_kanit
            base["kutu_ncc"] = round(ncc, 4)
        # F1c KARARI: text-yolu REDDETTİ (kutu sayısı/konumu uyuşmadı YA DA NCC
        # eşiği tutmadı) -- tartışmalı kutulara REC hakemi (hayalet-kutu ayrımı).
        # Yalnız BURADA çağrılır: piksel-benzer aday + kutu-kapısı zaten reddetmiş
        # (maliyet sınırlı -- docs "F1c KARARI").
        if boxes_b_rec is None:
            boxes_b_rec = _f1c_rec_boxes(new_gray, _f1b_boxes_sorted(boxes_b))
        boxes_a_rec = entry.get("f1c_rec")
        if boxes_a_rec is None:
            boxes_a_rec = _f1c_rec_boxes(prev_gray, _f1b_boxes_sorted(boxes_a))
            entry["f1c_rec"] = boxes_a_rec  # kutu-kırpım başına önbellek
        ghost_scores = [round(score, 4) for norm, score in (boxes_a_rec + boxes_b_rec)
                        if not norm or score < rec_conf_gate]
        real_a = [norm for norm, score in boxes_a_rec if norm and score >= rec_conf_gate]
        real_b = [norm for norm, score in boxes_b_rec if norm and score >= rec_conf_gate]
        rec_kanit = {
            "karar_yolu": "rec",
            "hayalet_kutular": ghost_scores,
            "metin_a": " ".join(real_a),
            "metin_b": " ".join(real_b),
        }
        if not real_a and not real_b:
            # K1 HAKEM KARARI: rec boş/düşük-güven -> DAİMA KORU -- SADECE piksel
            # de (0-kutu yoluyla AYNI sıkı eşik) özdeşse sahne-skip'e izin var.
            if pixel_ozdes:
                return {**base, "karar_yolu": "distant-dup-scene", "rec_kanit": rec_kanit}, korunan_kanit
            continue  # KORU
        if real_a and real_a == real_b:
            return {**base, "karar_yolu": "distant-dup-rec", "rec_kanit": rec_kanit}, korunan_kanit
        # gerçek kutu metinleri FARKLI (örn. YAKIN_PLAN'ın farklı altyazısı) --
        # bu aday KORUNUR; döngü sıradaki registry adayına bakmaya devam eder.
        # K3 (Görev M8): bu "farklı-metin, korunan" anı sıkı kanıt şartını
        # karşılıyorsa KAYDET (karar mantığını ETKİLEMEZ, yalnız manifest için).
        if korunan_kanit is None:
            korunan_kanit = _k3_protected_evidence(boxes_a_rec, boxes_b_rec)
    return None, korunan_kanit


# --------------------------------------------------------------------------- #
# MITAS_MASTER_V2 / F2 -- slit dikiş kırpma (H1 kök-sebep) yardımcısı
# --------------------------------------------------------------------------- #
def _slit_seam_crop(
    prev_block: np.ndarray,
    new_block: np.ndarray,
    *,
    probe_px: int = F2_PROBE_PX,
    ncc_gate: float = F2_NCC_GATE,
    min_crop_px: int = 4,
) -> dict | None:
    """F2 (H1): iki ARDIŞIK slit bloğu arasında (aralarında statik/kart bloğu YOK)
    dikiş örtüşmesini bulur. Önceki bloğun son `probe_px` satırı ile yeni bloğun
    ilk `probe_px` satırı arasında, olası HER örtüşme derinliği `crop` (4..probe_px)
    için NCC (normalize çapraz-korelasyon: önceki bloğun SON `crop` satırı vs yeni
    bloğun İLK `crop` satırı) hesaplanır -- sabit boy bir şablon yerine değişken
    derinlik taranır, çünkü gerçek dikiş örtüşmesi birkaç pikselden ~200px'e kadar
    herhangi bir derinlikte olabilir (1.5fps'te kare-arası dy büyük -> örtüşme de
    büyük olabilir). En iyi NCC >= ncc_gate ise, o derinlik yeni bloğun BAŞINDAN
    kırpılır. "dur-devam koruması": kırpma miktarı segment yüksekliğinin yarısını
    asla aşmaz (gerçek/uzun scroll içeriğinin yanlışlıkla kesilmesine karşı) --
    ARAMA aralığı 200px probe penceresiyle sınırlı kalır (dur-devam kapağı yalnız
    SONUCU kırpar, aksi halde derin ama meşru bir örtüşme yarıdan büyük diye hiç
    aranmadan atlanır, hiç kırpma yapılmaz). Hizalama yetersizse (veya bloklar çok
    kısaysa) None -- kırpma YAPILMAZ.

    Manifest alanı "y": önceki bloğun İÇİNDE örtüşen içeriğin BAŞLADIĞI satır
    (prev_block.shape[0] - kırpılan_px) -- dikişin önceki segmentteki konumunu
    izlenebilir kılar (uygulayıcı tercihi; şartname yalnız alan adını verdi)."""
    if prev_block is None or new_block is None or not prev_block.size or not new_block.size:
        return None
    tail_h = min(probe_px, prev_block.shape[0])
    head_h = min(probe_px, new_block.shape[0])
    limit = min(tail_h, head_h)
    if limit < min_crop_px:
        return None
    w = min(prev_block.shape[1], new_block.shape[1])
    if w <= 0:
        return None
    tail = cv2.cvtColor(prev_block[-tail_h:, :w], cv2.COLOR_BGR2GRAY).astype(np.float32)
    head = cv2.cvtColor(new_block[:head_h, :w], cv2.COLOR_BGR2GRAY).astype(np.float32)
    best_ncc, best_crop = 0.0, 0
    for crop in range(min_crop_px, limit + 1):
        a = tail[-crop:, :]
        b = head[:crop, :]
        a0 = a - a.mean()
        b0 = b - b.mean()
        denom = float(np.sqrt(float((a0 * a0).sum())) * np.sqrt(float((b0 * b0).sum())))
        if denom < 1e-6:
            continue
        ncc = float((a0 * b0).sum() / denom)
        if ncc > best_ncc:
            best_ncc, best_crop = ncc, crop
    if best_crop <= 0 or best_ncc < ncc_gate:
        return None
    max_crop = new_block.shape[0] // 2   # dur-devam koruması: SONUCU kırp (aramayı değil)
    crop = min(best_crop, max_crop)
    if crop <= 0:
        return None
    return {
        "y": int(prev_block.shape[0] - crop),
        "kirpilan_px": int(crop),
        "ncc": round(best_ncc, 4),
    }


def dhash_hi(image: np.ndarray, size: int = DEDUP_HI_SIZE) -> int:
    """Higher-resolution dHash (default 16x16 = 256-bit) for the dedup-veto. Captures
    glyph-level differences the 8x8 dhash misses, so DISTINCT same-layout cards
    (x-men 'DIRECTOR OF PHOTOGRAPHY' vs 'EDITED BY') are not merged as duplicates."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (size + 1, size))
    diff = gray[:, 1:] > gray[:, :-1]
    bits = 0
    for value in diff.flatten():
        bits = (bits << 1) | int(value)
    return bits


# --------------------------------------------------------------------------- #
# content-based static-card split  (son_metro fix)
# --------------------------------------------------------------------------- #
# Why: split_runs() finds card boundaries from FULL-FRAME motion. When the
# background is a constant color (e.g. son_metro's red), the inter-card motion is
# ~0 (measured: 0 cuts over 318 frames) so a whole sequence of ~22 distinct cards
# collapses into ONE static run -> only one card kept, the rest of the cast lost.
# X-Men's cards sit on black, so the inter-card change is large (192 cuts) and
# split_runs separates them already. The text-mask dHash below is background-
# invariant: it tracks the TEXT layout, so it exposes the hidden card boundaries
# (measured: ~21-26 cards on son_metro, matching the truth). Debounced so a new
# layout must persist >= min_hold frames -> dissolves / 1-frame noise don't
# over-split, and X-Men's already-distinct cards are not broken up.
def _textmask_dhash(image: np.ndarray, p: Params, args) -> int:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mask = text_mask(gray, p, args.polarity)
    small = cv2.resize(mask, (9, 8), interpolation=cv2.INTER_AREA)
    diff = small[:, 1:] > small[:, :-1]
    bits = 0
    for value in diff.flatten():
        bits = (bits << 1) | int(value)
    return bits


def split_static_cards(
    run_frames: list[str],
    p: Params,
    args,
    *,
    timeline_offset: int = 0,
    opening_frame_limit: int = 0,
    opening_min_hold: int | None = None,
    min_hold_override: int | None = None,
    same_thr_override: int | None = None,
    chain_stability: bool = False,
) -> list[list[str]]:
    """Split a 'static' run into distinct cards by CONTENT (text-mask dHash).

    A boundary is a SUDDEN jump vs the PREVIOUS frame that then forms a STABLE
    plateau (held >= min_hold frames). Comparing consecutive frames (not a fixed
    reference) means a GRADUAL background drift -- kansas's panning map, drakula's
    flickering fire -- never trips a boundary (each step is small, nothing new
    stabilises), so a single held card is not split into copies. A real cut
    (son_metro: new name+portrait) is a big, sustained jump -> split."""
    same_thr = int(
        same_thr_override
        if same_thr_override is not None
        else getattr(args, "card_same_thr", 6)
    )
    min_hold = max(
        2,
        int(
            min_hold_override
            if min_hold_override is not None
            else getattr(args, "card_min_hold", p.min_hold)
        ),
    )
    opening_hold = (
        max(2, int(opening_min_hold))
        if opening_min_hold is not None and opening_frame_limit > 0
        else min_hold
    )
    valid = []
    for i, frame in enumerate(run_frames):
        image = _prep(frame, p, args)
        if image is not None:
            valid.append((i, _textmask_dhash(image, p, args)))
    if len(valid) < 2:
        return [run_frames]

    bounds = [0]                          # run-frame index where each card starts
    k = 1
    while k < len(valid):
        idx, h = valid[k]
        prev_h = valid[k - 1][1]
        if hamming(h, prev_h) > same_thr:           # sudden change vs previous frame
            persist, j = 1, k + 1
            stable_h = h
            while j < len(valid) and hamming(valid[j][1], stable_h) <= same_thr:
                persist += 1
                if chain_stability:
                    stable_h = valid[j][1]
                j += 1
            required_hold = (
                opening_hold
                if int(timeline_offset) + int(idx) < int(opening_frame_limit)
                else min_hold
            )
            if persist >= required_hold:            # new layout HELD -> a real card
                bounds.append(idx)
                k = j
                continue
        k += 1
    bounds.append(len(run_frames))
    return [run_frames[bounds[i]: bounds[i + 1]]
            for i in range(len(bounds) - 1) if bounds[i + 1] > bounds[i]]


def _prep(frame: str, p: Params, args) -> np.ndarray | None:
    """Read + (optional) deinterlace + size-normalize a frame, or None if unreadable."""
    image = rd_cached(frame)
    if image is None:
        return None
    if args.deinterlace:
        image = deinterlace(image)
    if image.shape[:2] != (p.h, p.w):
        image = cv2.resize(image, (p.w, p.h))
    return image


def first_readable(frames: list[str]):
    for frame in frames:
        image = rd_cached(frame)
        if image is not None:
            return image
    return None


# --------------------------------------------------------------------------- #
# MODE A: slit-scan
# --------------------------------------------------------------------------- #
def split_runs(frames: list[str], p: Params, args) -> list[list]:
    """Split timeline into static/scroll/cut runs via full-frame vertical motion."""
    hann = cv2.createHanningWindow((p.w, p.h), cv2.CV_32F)
    prev = None
    abs_dy: list[float] = []

    for frame in frames:
        image = _prep(frame, p, args)
        if image is None:
            abs_dy.append(0.0)  # treat missing as no motion
            continue
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
        dy = 0.0
        if prev is not None:
            (_, dy), _ = cv2.phaseCorrelate(prev * hann, gray * hann)
        prev = gray
        abs_dy.append(abs(dy))

    abs_dy_arr = np.array(abs_dy)
    is_cut = abs_dy_arr > p.cut
    smooth = np.array(
        [
            np.median(np.clip(abs_dy_arr, 0, p.cut)[max(0, i - 2): i + 3])
            for i in range(len(abs_dy_arr))
        ]
    )

    labels = []
    state = "S"
    for i, value in enumerate(smooth):
        if is_cut[i]:
            labels.append("C")
            continue
        if value < p.static_dy:
            state = "S"
        elif value > p.scroll_dy:
            state = "R"
        labels.append(state)

    runs = []
    start = 0
    for i in range(1, len(labels) + 1):
        if i == len(labels) or labels[i] != labels[start]:
            runs.append([start, i - 1, labels[start]])
            start = i

    return [
        run for run in runs
        if run[2] != "C" and (int(run[1]) - int(run[0]) + 1) >= p.min_hold
    ]


def _text_masked_dy_series(
    frames: list[str], p: Params, args
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-adjacent-frame TEXT-MASKED vertical motion: (dy, response, measured?).

    F3b yardımcısı -- masking deseni estimate_offsets() ile BİREBİR AYNI (text_mask
    + 11x11 dilate + maske-dışını sıfırla + Hanning-pencereli phaseCorrelate); yeni
    bir görüntü-işleme yolu İCAT EDİLMİYOR, Mode B (mozaik) zaten kullandığı birincil
    sinyal split_runs_reading'in karar yoluna yeniden kullanılıyor. estimate_offsets'i
    doğrudan çağırmak yerine küçük bir ikiz fonksiyon yazıldı çünkü o fonksiyonun
    yön-çözümleme/kesim/entegrasyon mantığı (mozaike özgü) burada gerekmiyor -- yalnız
    ham (dy, response, ölçüldü mü) üçlüsü lazım. `image is None` durumunda estimate_
    offsets ile AYNI davranış: `prev` SIFIRLANMAZ (sonraki geçerli kare, son geçerli
    öncekiyle karşılaştırılır) -- ölçüm boşluğu atlanır, sahte-sıfır enjekte edilmez.
    """
    hann = cv2.createHanningWindow((p.w, p.h), cv2.CV_32F)
    prev = None
    prev_has_text = False
    dy = np.zeros(len(frames), dtype=np.float64)
    resp = np.zeros(len(frames), dtype=np.float64)
    measured = np.zeros(len(frames), dtype=bool)

    for i, frame in enumerate(frames):
        image = _prep(frame, p, args)
        if image is None:
            continue
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        mask = cv2.dilate(text_mask(gray, p, args.polarity), np.ones((11, 11), np.uint8))
        masked = gray.astype(np.float32)
        masked[mask == 0] = 0.0
        has_text = bool(mask.any())
        if prev is not None and prev_has_text and has_text:
            (_, d), r = cv2.phaseCorrelate(prev * hann, masked * hann)
            dy[i] = float(d)
            resp[i] = float(r)
            measured[i] = True
        prev = masked
        prev_has_text = has_text
    return dy, resp, measured


def _f3b_text_masked_rescue(
    dy_seg: np.ndarray, resp_seg: np.ndarray, measured_seg: np.ndarray
) -> bool:
    """mod_denetim.py'nin TAM AYNI imzası, run-yerel dilimde: kayan_oran>=0.35,
    monoton>=0.75, medyan|dy| (kayan alt-kümede) >= F3_RUN_DY_FLOOR_PX. Örnek sayısı
    SLIT_HY_MIN_MEAS'ın (8) altındaysa istatistik güvenilmez -- rescue YOK (statüko)."""
    valid = measured_seg & (resp_seg > F3B_RESP_FLOOR)
    if int(valid.sum()) < SLIT_HY_MIN_MEAS:
        return False
    d = dy_seg[valid]
    kayan = np.abs(d) > F3B_KAYAN_FLOOR_PX
    if float(kayan.mean()) < F3B_KAYAN_ORAN_MIN:
        return False
    moving = d[kayan]
    if not moving.size:
        return False
    monoton = float(max((moving > 0).mean(), (moving < 0).mean()))
    if monoton < F3B_MONOTON_MIN:
        return False
    return float(np.median(np.abs(moving))) >= F3_RUN_DY_FLOOR_PX


def _resolve_reading_runs(
    raw_runs: list[list],
    min_scroll: int,
    *,
    dy_signed=None,
    resp=None,
    dy_masked=None,
    resp_masked=None,
    measured_masked=None,
) -> list[list]:
    """Resolve cut/noisy motion conservatively while preserving card boundaries.

    Sustained vertical motion stays R. Short R bursts become ordinary S because a
    false static page may duplicate content, while a false slit can lose it. Cuts
    become uncertain static boundaries and are absorbed by the following S run
    when possible because the first cut frame commonly carries the new card.

    F3 (MITAS_MASTER_V2, H3 kök-sebep -- docs/MITAS_Master_Dup_Kok_Sebep_Plani_v1.md
    Görev M4 KONSEY KARARI): bayrak AÇIK ve dy_signed/resp verilmişse, kısa bir "R"
    koşusu (yukarıdaki uzunluk şartını sağlamadığı için normalde "S"ye düşecek olan)
    EN AZ F3_RUN_MIN_FRAMES kare uzunluğundaysa VE medyan |dy| >= F3_RUN_DY_FLOOR_PX
    (30px -- titreme/gate-weave bandının güvenle üstü) VE korelasyon kanıtı (medyan
    faz-korelasyon yanıtı >= F3_RUN_RESP_FLOOR) taşıyorsa "S"ye DÜŞÜRÜLMEZ, "R"
    (slit) kalır -- gerçek scroll'un sayfa/kart moduna düşüp kare-kare örtüşen tekrar
    üretmesini (H3) engeller. Uzunluk şartı: gerçek scroll hızı p.cut eşiğine yakın
    filmlerde TEK KARELİK "R"/"C" salınımı (ölçüm gürültüsü, medyan tek örnekten
    güvenilir değil) yanlış-pozitif rescue'a yol açabiliyordu (M4 worst-10 pilotu,
    KÜÇÜK_KAHRAMAN bulgusu) -- "F3 eşiğini yükselt" kaçışı burada uygulanıyor.
    Bayrak kapalıyken (varsayılan) ya da dy_signed/resp verilmediyse bu dal hiç
    çalışmaz -- eski davranış bit-birebir korunur.

    F3b (MITAS_MASTER_V2, H3 kök-sebep ARTIĞI -- bkz. modül-üstü F3b yorumu +
    _text_masked_dy_series/_f3b_text_masked_rescue): F3, raw etiketi zaten "R" olan
    KISA patlamaları kurtarır; ama tam-kare sinyal arka plan tarafından domine
    edildiğinde raw etiket hiç "R" olmuyor -- koşu baştan sona "S" kalıyor, F3'ün
    hedefi dışında kalır (görsel kanıt: acemiler-cetesi, benimle-dans-et). Burada,
    NİHAİ (birleşmiş) "S" koşuları üzerinde -- kısa "U" parçalarını yutmuş olsa
    bile yeterli örnek sayısına ulaşsın diye ayrı bir SON geçiş yapılır: her "S"
    koşusunun metin-maskeli dy/response dilimine mod_denetim.py imzası uygulanır
    (_f3b_text_masked_rescue); tutarsa "R"ye çevrilir (slit'e gider). Bu çevirme
    ardışık iki (ya da daha fazla) "R" bloğu oluşturabilir (biri F3b'den, biri
    zaten "R"yse, ya da art arda birden çok F3b-çevirisi) -- bunlar AYRI bir
    geçişte TEK run'a birleştirilir (bkz. altındaki "adjacent-R merge" bloğu);
    F2 (_slit_seam_crop) böyle bir bitişikliği NCC ile SONRADAN kırpmayı dener
    ama HER ZAMAN güvenli örtüşme bulamıyor (gözlem: babam-ve-ben pilotu) --
    baştan birleştirmek dy-entegrasyonunu kesintisiz tutar, dikiş ihtiyacını
    yapısal olarak ortadan kaldırır. Bayrak kapalıyken ya da dy_masked/
    resp_masked/measured_masked verilmediyse bu geçişlerin hiçbiri çalışmaz --
    eski davranış bit-birebir korunur.
    """
    f3_on = _v2_enabled() and dy_signed is not None and resp is not None
    classified = []
    for start, end, label in raw_runs:
        length = int(end) - int(start) + 1
        resolved = "U" if label == "C" else (
            "R" if label == "R" and length >= min_scroll else "S"
        )
        if f3_on and label == "R" and resolved == "S" and length >= F3_RUN_MIN_FRAMES:
            seg_dy = np.abs(np.asarray(dy_signed[int(start): int(end) + 1], dtype=np.float64))
            seg_resp = np.asarray(resp[int(start): int(end) + 1], dtype=np.float64)
            if seg_dy.size:
                med_dy = float(np.median(seg_dy))
                med_resp = float(np.median(seg_resp)) if seg_resp.size else 0.0
                if med_dy >= F3_RUN_DY_FLOOR_PX and med_resp >= F3_RUN_RESP_FLOOR:
                    resolved = "R"
        if classified and resolved == "U" and classified[-1][2] == "U":
            classified[-1][1] = int(end)
        elif classified and resolved == "S" and classified[-1][2] == "S":
            classified[-1][1] = int(end)
        else:
            classified.append([int(start), int(end), resolved])

    runs = []
    pending_uncertain = None
    for index, (start, end, label) in enumerate(classified):
        if label != "U":
            if pending_uncertain is not None:
                start = pending_uncertain[0]
                pending_uncertain = None
            runs.append([int(start), int(end), str(label)])
            continue

        next_label = classified[index + 1][2] if index + 1 < len(classified) else None
        if next_label == "S":
            pending_uncertain = [int(start), int(end)]
        elif runs and runs[-1][2] == "S":
            runs[-1][1] = int(end)
        else:
            runs.append([int(start), int(end), "S"])

    if pending_uncertain is not None:
        runs.append([int(pending_uncertain[0]), int(pending_uncertain[1]), "S"])

    f3b_on = (
        _v2_enabled()
        and dy_masked is not None
        and resp_masked is not None
        and measured_masked is not None
    )
    if f3b_on:
        flipped = [False] * len(runs)
        for i, run in enumerate(runs):
            if run[2] != "S":
                continue
            start, end = int(run[0]), int(run[1])
            seg = slice(start, end + 1)
            if _f3b_text_masked_rescue(
                np.asarray(dy_masked[seg], dtype=np.float64),
                np.asarray(resp_masked[seg], dtype=np.float64),
                np.asarray(measured_masked[seg], dtype=bool),
            ):
                run[2] = "R"
                flipped[i] = True

        # Bitişik "R" koşularını TEK koşuya birleştir. Öncesi-algoritma yapısal
        # olarak ASLA bitişik iki "R" üretmiyordu (raw_runs ardışık farklı
        # etiketlerden oluşur; aralarına giren "C"/kısa-"R" hep kendi "S" koşusuna
        # düşer -- bkz. yukarıdaki U-çözümleme) -- bitişiklik YALNIZ burada, bir
        # "S" koşusu iki "R" koşusunun arasında (ya da bir başka yeni-"R"nin
        # yanında) "R"ye çevrildiğinde ortaya çıkar. Birleştirmezsek her parça
        # AYRI slitscan() çağrısı alır (dy-entegrasyonu parça başına sıfırlanır);
        # F2 (_slit_seam_crop) bunu NCC ile SONRADAN kırpmaya çalışır ama HER
        # ZAMAN güvenli örtüşme bulamaz (gözlemlenen: babam-ve-ben pilotu -- 3
        # bitişik F3b-çevirisi, F2 hiçbirinde kırpmadı, iç-dikişte birkaç satır
        # tekrarı kaldı). Baştan birleştirmek F2'nin sonradan-kırpmasından daha
        # güvenilir: TEK slitscan() çağrısı kesintisiz dy entegre eder, dikiş
        # İHTİYACI YAPISAL OLARAK ORTADAN KALKAR.
        # KEMER-VE-ASKI (dış konsey bulgusu, GLM+Kimi bağımsız turu, 2026-07-26):
        # yukarıdaki yapısal ispat "bitişik R-R yalnız bir çeviri varsa oluşur"
        # diyor, ama merge'i yine de EN AZ BİR taraf bu geçişte çevrildiyse
        # şartına bağlıyoruz -- ispat başka bir F1/F1b/F1c/F2/F4 etkileşiminde
        # bozulursa bile iki BAĞIMSIZ/önceden-var "R" koşusu YANLIŞLIKLA
        # birleştirilemez (flip provenance zincirleme birleşmelerde de taşınır).
        merged: list[list] = []
        merged_flipped: list[bool] = []
        for i, run in enumerate(runs):
            if (
                merged and merged[-1][2] == "R" and run[2] == "R"
                and (merged_flipped[-1] or flipped[i])
            ):
                merged[-1][1] = run[1]
                merged_flipped[-1] = True
            else:
                merged.append(run)
                merged_flipped.append(flipped[i])
        runs = merged

    return runs


def _merge_short_reading_cards(
    cards: list[list[str]],
    *,
    timeline_offset: int,
    opening_frame_limit: int,
    opening_min_hold: int,
    min_hold: int,
) -> list[list[str]]:
    """Attach transition fragments to the next stable card, or the prior at EOF."""
    merged = []
    pending = []
    consumed = 0
    for card in cards:
        global_start = int(timeline_offset) + consumed
        required = opening_min_hold if global_start < opening_frame_limit else min_hold
        consumed += len(card)
        if len(card) < required:
            pending.extend(card)
            continue
        if pending:
            card = pending + card
            pending = []
        merged.append(card)
    if pending:
        if merged:
            merged[-1].extend(pending)
        else:
            merged.append(pending)
    return merged


def _split_long_reading_cards(
    cards: list[list[str]],
    p: Params,
    args,
    *,
    min_hold: int,
    same_thr: int,
    timeline_offset: int,
    frame_limit: int,
) -> list[list[str]]:
    """Split a long mixed group at a strong internal text-layout jump."""
    jump_floor = max(int(same_thr) + 2, 9)

    def split_one(card: list[str]) -> list[list[str]]:
        if len(card) < 2 * min_hold:
            return [card]
        hashes = []
        for frame in card:
            image = _prep(frame, p, args)
            if image is None:
                return [card]
            hashes.append(_textmask_dhash(image, p, args))
        candidates = [
            (hamming(hashes[index - 1], hashes[index]), index)
            for index in range(min_hold, len(card) - min_hold + 1)
        ]
        if not candidates:
            return [card]
        jump, boundary = max(candidates)
        if jump <= jump_floor:
            return [card]
        return split_one(card[:boundary]) + split_one(card[boundary:])

    result = []
    cursor = int(timeline_offset)
    for card in cards:
        if cursor < int(frame_limit):
            result.extend(split_one(card))
        else:
            result.append(card)
        cursor += len(card)
    return result


def split_runs_reading(frames: list[str], p: Params, args) -> list[list]:
    """Reader-facing S/R runs.

    Unlike split_runs(), this keeps the full timeline covered. Cut/noisy spans are
    treated as static candidates, and very short scroll bursts fall back to static
    sampling instead of disappearing from the reading master.
    """
    if not frames:
        return []

    hann = cv2.createHanningWindow((p.w, p.h), cv2.CV_32F)
    prev = None
    abs_dy: list[float] = []
    # F3 (MITAS_MASTER_V2) girdisi: imzalı dy + faz-korelasyon yanıtı. Var olan
    # abs_dy hesaplamasına EK yük getirmiyor (aynı phaseCorrelate çağrısının daha
    # önce atılan dönüş değerleri) -- bayrak kapalıyken bu diziler hiç okunmaz.
    dy_signed: list[float] = []
    resp_list: list[float] = []

    for frame in frames:
        image = _prep(frame, p, args)
        if image is None:
            abs_dy.append(0.0)
            dy_signed.append(0.0)
            resp_list.append(0.0)
            continue
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
        dy = 0.0
        resp = 0.0
        if prev is not None:
            (_, dy), resp = cv2.phaseCorrelate(prev * hann, gray * hann)
        prev = gray
        abs_dy.append(abs(dy))
        dy_signed.append(float(dy))
        resp_list.append(float(resp))

    abs_dy_arr = np.array(abs_dy)
    is_cut = abs_dy_arr > p.cut
    smooth = np.array(
        [
            np.median(np.clip(abs_dy_arr, 0, p.cut)[max(0, i - 2): i + 3])
            for i in range(len(abs_dy_arr))
        ]
    )

    labels = []
    state = "S"
    for i, value in enumerate(smooth):
        if is_cut[i]:
            labels.append("C")
            state = "S"
            continue
        elif value < p.static_dy:
            state = "S"
        elif value > p.scroll_dy:
            state = "R"
        labels.append(state)

    raw_runs = []
    start = 0
    for i in range(1, len(labels) + 1):
        if i == len(labels) or labels[i] != labels[start]:
            raw_runs.append([start, i - 1, labels[start]])
            start = i

    min_scroll = max(3, int(p.min_hold))
    # F3b (MITAS_MASTER_V2): metin-maskeli dy/response yalnız bayrak AÇIKKEN
    # hesaplanır (ek maliyet: tüm kareler üzerinde bir text_mask+phaseCorrelate
    # geçişi daha) -- bayrak kapalıyken bu satır hiç çalışmaz, bit-parite korunur.
    dy_masked = resp_masked = measured_masked = None
    if _v2_enabled():
        dy_masked, resp_masked, measured_masked = _text_masked_dy_series(frames, p, args)
    return _resolve_reading_runs(
        raw_runs, min_scroll,
        dy_signed=np.array(dy_signed), resp=np.array(resp_list),
        dy_masked=dy_masked, resp_masked=resp_masked, measured_masked=measured_masked,
    )


def _slit_channel_stats(frames: list[str], p: Params, args) -> dict | None:
    """HİBRİT-DY şartname 1a: R-run için iki kanalın (maskeli/tam-kare) dy+response
    serileri + maske kapsaması TEK geçişte. TÜM istatistikler bu tek geçişin
    serilerinden türetilir (ölçüm-hijyeni: ikinci sayım kaynağı YASAK —
    skip105+spike18=123>120 dersi). Kısa run'da (n<SLIT_HY_MIN_MEAS) None."""
    hann = cv2.createHanningWindow((p.w, p.h), cv2.CV_32F)
    prev_m = prev_f = None
    prev_has = False
    dy_m: list[float] = []
    dy_f: list[float] = []
    resp_m: list[float] = []
    resp_f: list[float] = []
    cov: list[float] = []
    for frame in frames:
        image = _prep(frame, p, args)
        if image is None:
            continue
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gf = gray.astype(np.float32)
        mask = text_mask(gray, p, args.polarity)
        dil = cv2.dilate(mask, np.ones((11, 11), np.uint8))
        m = gf.copy()
        m[dil == 0] = 0.0
        cov.append(float((dil > 0).mean()))
        if prev_m is not None and bool(dil.any()) and prev_has:
            (_, dm), rm = cv2.phaseCorrelate(prev_m * hann, m * hann)
            (_, df), rf = cv2.phaseCorrelate(prev_f * hann, gf * hann)
            dy_m.append(float(dm))
            dy_f.append(float(df))
            resp_m.append(float(rm))
            resp_f.append(float(rf))
        prev_m, prev_f, prev_has = m, gf, bool(dil.any())
    n = len(dy_m)
    if n < SLIT_HY_MIN_MEAS:
        return None
    am = np.abs(np.array(dy_m, dtype=np.float64))
    af = np.abs(np.array(dy_f, dtype=np.float64))
    gecerli_f = np.array([v for v in dy_f if p.vmin <= abs(v) <= p.vmax], dtype=np.float64)
    med_f = float(np.median(np.abs(gecerli_f))) if gecerli_f.size else 0.0
    med_f_signed = float(np.median(gecerli_f)) if gecerli_f.size else 0.0
    if gecerli_f.size:
        q1, q3 = np.percentile(np.abs(gecerli_f), [25, 75])
        iqr_f = float(q3 - q1)
    else:
        iqr_f = 0.0
    tol = max(2.0, 0.1 * med_f)
    return {
        "n_meas": n,
        "skip_frac_m": float(((am < p.vmin) | (am > p.vmax)).mean()),
        "cov_med": float(np.median(cov)) if cov else 0.0,
        "med_f": med_f, "med_f_signed": med_f_signed, "iqr_f": iqr_f,
        "valid_rate_f": float(gecerli_f.size) / n,
        "n_coin": int((np.abs(am - af) <= tol).sum()),
        "tol_coin": tol,
        "resp_m_med": float(np.median(resp_m)),
        "resp_f_med": float(np.median(resp_f)),
        "dy_m": [round(float(x), 3) for x in dy_m],
        "dy_f": [round(float(x), 3) for x in dy_f],
        "cov_seri": [round(float(x), 4) for x in cov],
    }


def _slit_channel_decision(stats: dict | None, p: Params) -> str:
    """HİBRİT-DY şartname 3: run-başına TEK karar. SAF — birim-test edilebilir.
    FULL   = maske-şişme (çelişki + kesişme tanığı): şişik maske ara ara gerçek hıza
             kilitlenip 'itiraf eder' (n_coin), gerçekten duran yazı asla etmez.
    DEMOTE = duran-yazı (maske dürüst ama hareket yok; kesişme sıfır).
    MASKED = statüko — sağlıklı ve TÜM belirsiz durumlar (üçüncü mod dahil)."""
    if stats is None:
        return "MASKED"
    n_coin_min = max(3, int(np.ceil(0.05 * stats["n_meas"])))
    if (stats["cov_med"] >= SLIT_HY_COV_THR
            and stats["skip_frac_m"] >= SLIT_HY_SKIP_THR
            and stats["n_coin"] >= n_coin_min
            and stats["med_f"] >= p.vmin):
        return "FULL"
    if (stats["skip_frac_m"] >= SLIT_HY_SKIP_THR
            and stats["n_coin"] <= SLIT_HY_NCOIN_NULL
            and stats["cov_med"] < SLIT_HY_COV_THR):
        return "DEMOTE"
    return "MASKED"


def _slit_hybrid_log(frames: list[str], stats: dict | None, decision: str, applied: bool) -> dict:
    """Gölge kaydı: HYBRID_LOG'a ekle (process_film sidecar'a boşaltır). Ana manifest'e
    ve PNG'ye golge modda DOKUNULMAZ (SHA bit-identikliği şartı)."""
    kayit = {
        "src_first": Path(frames[0]).name if frames else None,
        "src_last": Path(frames[-1]).name if frames else None,
        "n_frames": len(frames),
        "decision": decision,
        "applied": bool(applied),
        "stats": stats,
    }
    HYBRID_LOG.append(kayit)
    return kayit


def _hy_manifest_ozet(hy: dict, block_h: int) -> dict:
    """Bayrak='1' iken manifest scroll bloğuna yazılacak kompakt hibrit özeti
    (+TRAVEL bekçi girdileri). Gölge modda manifest'e ASLA yazılmaz (SHA şartı)."""
    st = hy.get("stats") or {}
    med_f = float(st.get("med_f") or 0.0)
    n = int(st.get("n_meas") or 0)
    beklenen = med_f * n
    return {
        "decision": hy.get("decision"),
        "applied": bool(hy.get("applied")),
        "dy_source": "full" if (hy.get("applied") and hy.get("decision") == "FULL") else "masked",
        "cov_med": round(float(st.get("cov_med") or 0.0), 4),
        "skip_frac_masked": round(float(st.get("skip_frac_m") or 0.0), 4),
        "n_coin": int(st.get("n_coin") or 0),
        "med_f": round(med_f, 3),
        "travel_expected": round(beklenen, 1),
        "travel_ratio": round(block_h / beklenen, 4) if beklenen > 0 else None,
    }


def slitscan(frames: list[str], p: Params, args,
             allow_demote: bool = False) -> tuple[np.ndarray | None, dict | None]:
    """Dönüş: (block, hybrid_info|None). HİBRİT-DY bayrağı '0' iken hybrid_info=None
    ve kod yolu bit-identik (yeni fonksiyonlar hiç çağrılmaz)."""
    hy_info = None
    hy_full = False
    med_signed = 0.0
    clamp_band = 0.0
    if SLIT_DY_HYBRID in ("golge", "1"):
        stats = _slit_channel_stats(frames, p, args)
        decision = _slit_channel_decision(stats, p)
        uygula = SLIT_DY_HYBRID == "1" and stats is not None
        if uygula and decision == "DEMOTE" and allow_demote:
            hy_info = _slit_hybrid_log(frames, stats, decision, True)
            return None, hy_info      # çağıran statik-sayfa fallback'ine düşer
        hy_full = bool(uygula and decision == "FULL")
        hy_info = _slit_hybrid_log(frames, stats, decision, hy_full)
        if hy_full:
            med_signed = stats["med_f_signed"]
            clamp_band = 3.0 * max(stats["iqr_f"], 0.5)   # parlama/interlace sigortası

    hann = cv2.createHanningWindow((p.w, p.h), cv2.CV_32F)
    ref = round(SLIT_FRAC * p.h)
    prev = None
    prev_full = None
    prev_has_text = False
    strips = []
    seed_top = None       # FIX: first frame's region ABOVE the slit (else it's lost)
    last_image = None
    last_v = 0

    for frame in frames:
        image = _prep(frame, p, args)
        if image is None:
            continue
        if args.luma_key:  # FIX(10): wired up, was dead code
            image = luma_key(image)
        if seed_top is None:
            seed_top = image[:ref, :].copy()
        last_image = image

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray_float = gray.astype(np.float32)
        mask = text_mask(gray, p, args.polarity)
        dilated = cv2.dilate(mask, np.ones((11, 11), np.uint8))
        masked = gray_float.copy()
        masked[dilated == 0] = 0.0

        dy = 0.0
        if prev is not None and bool(dilated.any()) and prev_has_text:
            if hy_full:
                # FULL kanal: hız tam-kareden akar (kare-başına; rampa serbest) +
                # med±3·IQR kelepçesi. Maske yalnız yazı-varlığı kapısı olarak kalır.
                (_, dy), _ = cv2.phaseCorrelate(prev_full * hann, gray_float * hann)
                if abs(dy - med_signed) > clamp_band:
                    dy = med_signed
            else:
                (_, dy), _ = cv2.phaseCorrelate(prev * hann, masked * hann)
        prev = masked
        prev_full = gray_float
        prev_has_text = bool(dilated.any())

        velocity = int(round(abs(dy)))
        # FIX(5): strip height == real motion; drop only jitter or glitch/cut.
        if velocity < p.vmin or velocity > p.vmax:
            continue
        strip = image[ref: ref + velocity, :].copy()
        if strip.shape[0] > 0:
            strips.append(strip)
            last_v = velocity

    if not strips:
        return None, hy_info
    # FIX: prepend the first frame's above-slit content and append the last
    # frame's below-slit content so the head/tail of the roll aren't dropped.
    parts = []
    if seed_top is not None and seed_top.shape[0] > 0:
        parts.append(seed_top)
    parts.append(np.vstack(strips))
    if last_image is not None and ref + last_v < p.h:
        parts.append(last_image[ref + last_v:, :].copy())
    return np.vstack(parts), hy_info


def compose_slit(frames: list[str], p: Params, args) -> tuple[np.ndarray | None, list[dict], np.ndarray | None]:
    # MITAS_MASTER_V2 (Görev M4): ÇAĞRI ZAMANINDA okunur (bkz. _v2_enabled) --
    # bayrak kapalıyken v2_on=False, aşağıdaki F1 dalı hiç çalışmaz ve bu fonksiyon
    # eski (bit-birebir) davranışını korur.
    v2_on = _v2_enabled()
    runs = split_runs(frames, p, args)
    blocks = []
    manifest = []
    block_kinds: list[str] = []  # F2: "scroll"/"card" -- ardışık scroll tespiti için
    card_registry: list[dict] = []  # F1: {"dhash","mask","block_index"} -- yalnız v2_on
    seen_hashes: list[int] = []
    seen_text: list[int] = []   # text-mask hashes (bg-tolerant) for moving-bg dedup
    seen_hi: list[int] = []     # hi-res 256-bit content hashes (DEDUP_HIRES veto anchors)

    def _sharpest_with_text(card_frames):
        """Return (best_frame, best_image, best_mask) for the sharpest readable
        frame of a card, or (None, None, None) if none has text."""
        sh = []
        for frame in card_frames:
            image = _prep(frame, p, args)
            if image is None:
                continue
            sh.append((sharpv(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)), frame))
        if not sh:
            return None, None, None
        _, bf = max(sh, key=lambda item: item[0])
        bi = _prep(bf, p, args)
        bm = text_mask(cv2.cvtColor(bi, cv2.COLOR_BGR2GRAY), p, args.polarity)
        return bf, bi, bm

    for start, end, label in runs:
        si, ei = int(start), int(end)
        run_frames = frames[si: ei + 1]

        if label == "R":
            # scroll: gate on the sharpest frame, then slit-scan the whole run
            best_frame, _bi, best_mask = _sharpest_with_text(run_frames)
            if best_frame is None:
                manifest.append({"run": [si, ei], "lab": label, "skip": "unreadable"})
                continue
            if not has_text(best_mask, p):
                manifest.append({"run": [si, ei], "lab": label, "skip": "no-text"})
                continue
            block, hy = slitscan(run_frames, p, args)   # allow_demote=False: film-ortak
            # hat; DEMOTE kararı statüko-MASKED'e düşer, yalnız sidecar'a yazılır.
            if block is not None and block.size:
                seam = None
                if v2_on and block_kinds and block_kinds[-1] == "scroll":
                    # F2 (H1 kök-sebep): aralarında statik/kart bloğu OLMAYAN iki
                    # ardışık slit bloğu -- dikiş örtüşmesini NCC ile bul+kırp.
                    seam = _slit_seam_crop(blocks[-1], block)
                    if seam is not None:
                        block = block[seam["kirpilan_px"]:, :]
                girdi = {"run": [si, ei], "lab": label, "kind": "scroll",
                         "h": int(block.shape[0]), "src": Path(best_frame).name}
                if seam is not None:
                    girdi["dikis"] = seam
                if SLIT_DY_HYBRID == "1" and hy:
                    girdi["hybrid"] = _hy_manifest_ozet(hy, int(block.shape[0]))
                blocks.append(block)
                block_kinds.append("scroll")
                manifest.append(girdi)
            else:
                manifest.append({"run": [si, ei], "lab": label, "skip": "empty"})
            continue

        # static run -> split into distinct cards by CONTENT (son_metro fix),
        # crop each to its TEXT rows (drop photo + solid-colour void), dedup on
        # the text crop (so different names are not merged like the old whole-card
        # dHash did on son_metro's near-identical red layouts).
        cards = [run_frames] if getattr(args, "no_card_split", False) else \
            split_static_cards(run_frames, p, args)
        for ci, card_frames in enumerate(cards):
            best_frame, best_image, best_mask = _sharpest_with_text(card_frames)
            if best_frame is None or not has_text(best_mask, p):
                manifest.append({"run": [si, ei], "card": ci, "lab": label, "skip": "no-text"})
                continue
            band = text_rows(best_mask, p) or text_band(best_mask)
            block = (
                best_image[max(0, band[0] - p.pad): min(best_image.shape[0], band[1] + p.pad), :]
                if band else None
            )
            if block is None or not block.size:
                manifest.append({"run": [si, ei], "card": ci, "lab": label, "skip": "empty"})
                continue
            if not args.no_dedup:
                # raw dHash catches identical-bg repeats; the text-mask dHash is
                # background-tolerant and catches a card repeated over a MOVING bg
                # (kansas drifting map) the raw hash misses. Neither fully cleans a
                # heavily-textured moving bg (drakula fire) -> some repeats remain.
                hh = dhash(block)
                thh = _textmask_dhash(block, p, args)
                consec = bool(seen_hashes) and hamming(hh, seen_hashes[-1]) <= CONSEC_DUP
                coarse_dup = (consec
                              or any(hamming(hh, ph) <= DUP_HAM for ph in seen_hashes)
                              or any(hamming(thh, pt) <= DUP_HAM for pt in seen_text))
                # HI-RES VETO: the coarse hashes above MERGE distinct same-layout cards
                # (role-left/name-right) -> a real card is dropped (kukla lost its crew
                # card; x-men its editors). If coarse says "drop" but the 256-bit content
                # hash differs from EVERY kept card by > DEDUP_TDIFF, the cards are
                # genuinely different -> KEEP. Only flips drop->keep, never keep->drop,
                # so it can never lose a coarse-kept card (worst case = old behavior + a
                # cosmetic fade-variant dup, which no geometric metric can separate from
                # a distinct card -> accepted; cosmetic dup << dropped real credit).
                hhi = None
                if DEDUP_HIRES and coarse_dup and seen_hi:
                    hhi = dhash_hi(block)
                    if min(hamming(hhi, ph) for ph in seen_hi) > DEDUP_TDIFF:
                        coarse_dup = False
                if coarse_dup:
                    manifest.append({"run": [si, ei], "card": ci, "lab": label, "kind": "card",
                                     "skip": "dup", "src": Path(best_frame).name})
                    continue
                f1b_gray = None
                if v2_on:
                    # F1 (H2 kök-sebep): eski coarse_dup ardışık/pencere-içi eşleşmeyi
                    # yakalamadı -- global kayıtla UZAK (ardışık-olmayan) tekrarı denetle.
                    match = _card_distant_dup_match(thh, best_mask, card_registry)
                    if match is not None:
                        skip_entry = {"run": [si, ei], "card": ci, "lab": label, "kind": "card",
                                      "skip": "distant-dup", "src": Path(best_frame).name}
                        skip_entry.update(match)
                        manifest.append(skip_entry)
                        continue
                    # F1b DÜZELTMESİ: F1 dHash aday kapısı GRENLİ donuk-sahne sayfalarında
                    # hiç tetiklenmiyordu -- hash ön-elemesi olmadan gri piksel-benzerlik +
                    # det-only kutu doğrulaması ile EK kapı.
                    f1b_gray = cv2.cvtColor(best_image, cv2.COLOR_BGR2GRAY)
                    match_f1b, korunan_kanit = _card_distant_dup_match_f1b(f1b_gray, card_registry)
                    if match_f1b is not None:
                        skip_entry = {"run": [si, ei], "card": ci, "lab": label, "kind": "card",
                                      "skip": match_f1b.pop("karar_yolu"), "src": Path(best_frame).name}
                        skip_entry.update(match_f1b)
                        manifest.append(skip_entry)
                        continue
                seen_hashes.append(hh)
                seen_text.append(thh)
                if DEDUP_HIRES:
                    seen_hi.append(hhi if hhi is not None else dhash_hi(block))
                if v2_on:
                    card_registry.append({
                        "dhash": thh, "mask": best_mask, "block_index": len(blocks),
                        "gray": f1b_gray,
                    })
            blocks.append(block)
            block_kinds.append("card")
            kept_entry = {"run": [si, ei], "card": ci, "lab": label, "kind": "card",
                          "h": int(block.shape[0]), "src": Path(best_frame).name}
            # K3 (Görev M8): korunan (skip edilmeyen) kart, sıkı kanıt şartını
            # karşılıyorsa manifest'e {text_a,text_b,conf_a,conf_b,protected:true}
            # kaydı -- karar mantığını DEĞİŞTİRMEZ, saglik.py'nin protected-çift
            # muafiyeti + recall testi için.
            if v2_on and korunan_kanit is not None:
                kept_entry["korunan_esleme"] = korunan_kanit
            manifest.append(kept_entry)

    if not blocks:
        return None, manifest, None

    max_width = max(block.shape[1] for block in blocks)
    normalized = [
        cv2.copyMakeBorder(block, 0, 0, 0, max_width - block.shape[1],
                           cv2.BORDER_CONSTANT, value=(0, 0, 0))
        if block.shape[1] < max_width else block
        for block in blocks
    ]
    stacked = []
    for block in normalized:
        stacked.append(block)
        stacked.append(np.zeros((SEP_PX, max_width, 3), np.uint8))
    return np.vstack(stacked[:-1]), manifest, None


# --------------------------------------------------------------------------- #
# MITAS_MASTER_V2 / F4 -- Şerit-Atlası (Görev M10, yavaş-kayan-liste onarımı)
# --------------------------------------------------------------------------- #
def _atlas_line_height_estimate(gray: np.ndarray, *, min_lag: int = 8, max_lag: int = 200,
                                 varsayilan: int = ATLAS_LINE_H_VARSAYILAN) -> int:
    """dup_metrik.py'nin satır-yüksekliği tahminiyle AYNI fikir (yatay kenar-
    yoğunluğu profilinin otokorelasyon tepesi) -- composer harness'a bağımlı
    OLMASIN diye burada bağımsız/küçük olarak yeniden uygulanır (tek yönlü
    bağımlılık: harness composer'ı import eder, tersi asla)."""
    h = gray.shape[0]
    if h < min_lag * 4:
        return varsayilan
    gy = cv2.Sobel(gray.astype(np.float32), cv2.CV_32F, 0, 1, ksize=3)
    profil = np.abs(gy).mean(axis=1)
    profil = profil - profil.mean()
    varyans = float(np.dot(profil, profil))
    if varyans <= 1e-6:
        return varsayilan
    lag_max = min(h // 3, max_lag)
    if lag_max <= min_lag:
        return varsayilan
    skorlar = np.array(
        [float(np.dot(profil[:-lag], profil[lag:])) / varyans for lag in range(min_lag, lag_max + 1)]
    )
    tepe = float(skorlar.max())
    if tepe < 0.15:
        return varsayilan
    esik = 0.6 * tepe
    for offset, skor in enumerate(skorlar):
        if skor >= esik:
            return int(min_lag + offset)
    return varsayilan  # pragma: no cover


def _atlas_pair_align(prev_gray: np.ndarray, new_gray: np.ndarray) -> dict | None:
    """İki ardışık 'statik' sayfa arasında dikey kaymayı (dy) faz-korelasyonla
    bul, hizalanmış örtüşme bölgesinde NCC ile DOĞRULA (iki bağımsız kanıt --
    F1/F1b'nin phaseCorrelate+XOR-doğrulama desenini izler). Genişlik ORTAK
    (aynı film/run çözünürlüğü); yükseklikler farklı olabilir -- ortak
    (maksimum) yüksekliğe alta sıfır-doldurma ile getirilir. Herhangi bir kapı
    tutmazsa None (çağıran bunu 'zincir kurulamadı' -- sayfalar AYNEN kalır --
    olarak okur)."""
    if prev_gray is None or new_gray is None or not prev_gray.size or not new_gray.size:
        return None
    if prev_gray.shape[1] != new_gray.shape[1]:
        return None
    h1, h2 = prev_gray.shape[0], new_gray.shape[0]
    w = prev_gray.shape[1]
    if h1 < 8 or h2 < 8 or w < 8:
        return None
    hmax = max(h1, h2)
    a = np.zeros((hmax, w), np.float32)
    b = np.zeros((hmax, w), np.float32)
    a[:h1, :] = prev_gray.astype(np.float32) / 255.0
    b[:h2, :] = new_gray.astype(np.float32) / 255.0
    hann = cv2.createHanningWindow((w, hmax), cv2.CV_32F)
    (dx, dy), response = cv2.phaseCorrelate(a * hann, b * hann)
    if response < ATLAS_RESP_GATE:
        return None
    if abs(dy) < ATLAS_DY_MIN_PX:
        return None  # dy≈0 -- zaten F1b/F1c dedup yoluna düşmüş olmalı, atlas dokunmaz
    y_lo = max(0.0, dy)
    y_hi = min(float(h2), float(h1) + dy)
    if y_hi - y_lo < 2:
        return None
    transform = np.float32([[1, 0, dx], [0, 1, dy]])
    prev_f = prev_gray.astype(np.float32) / 255.0
    aligned = cv2.warpAffine(prev_f, transform, (w, h2))
    y0, y1 = int(round(y_lo)), int(round(y_hi))
    if y1 - y0 < 2:
        return None
    seg_a = aligned[y0:y1, :]
    seg_b = new_gray.astype(np.float32)[y0:y1, :] / 255.0
    a0 = seg_a - seg_a.mean()
    b0 = seg_b - seg_b.mean()
    denom = float(np.sqrt(float((a0 * a0).sum())) * np.sqrt(float((b0 * b0).sum())))
    ncc = float((a0 * b0).sum() / denom) if denom > 1e-6 else 0.0
    if ncc < ATLAS_NCC_GATE:
        return None
    line_h = min(_atlas_line_height_estimate(prev_gray), _atlas_line_height_estimate(new_gray))
    overlap_px = int(round(y1 - y0))
    if overlap_px < ATLAS_OVERLAP_MIN_SATIR * line_h:
        return None
    return {
        "dy": float(dy), "dx": float(dx), "response": round(float(response), 4),
        "ncc": round(ncc, 4), "overlap_px": overlap_px, "line_height": int(line_h),
        # dikiş-doğrulama için örtüşme koordinatları: YENİ sayfa yerelinde
        # [y0,y1); ÖNCEKİ sayfa yerelinde aynı bölge = [y0-round(dy), y1-round(dy))
        "overlap_new": [int(y0), int(y1)],
    }


def _atlas_seam_verify(prev_gray: np.ndarray, new_gray: np.ndarray, align: dict) -> dict:
    """Dikiş-düzeyi rec-doğrulama (Kimi kuralı -- bkz. ATLAS_SEAM_* sabit notu).

    Örtüşme bölgesinin İKİ kırpımı (önceki sayfadan + yeni sayfadan) ayrı ayrı
    det+rec'lenir; kutular konum-eşleştirilir (merkez toleransı F1B_CENTER_TOL).
    ÇELİŞKİ = konum-eşleşmiş bir kutu çiftinde İKİ taraf da yüksek-güvenli
    (conf>=ATLAS_SEAM_CONF) okunduğu halde metinler uyuşmuyor (kısa token birebir
    değil; uzun token Levenshtein>1). Düşük-güvenli/eşleşmemiş kutu TOLERE.
    Dönüş: {"gecti": bool, "celiski": [...], "kontrol_cift": int, ...}."""
    dyi = int(round(align["dy"]))
    ny0, ny1 = align["overlap_new"]
    py0, py1 = ny0 - dyi, ny1 - dyi
    py0 = max(0, py0)
    py1 = min(prev_gray.shape[0], py1)
    ny0 = max(0, ny0)
    ny1 = min(new_gray.shape[0], ny1)
    h_ortak = min(py1 - py0, ny1 - ny0)
    sonuc = {"gecti": True, "celiski": [], "kontrol_cift": 0,
             "kutu_prev": 0, "kutu_new": 0, "overlap_h": int(h_ortak)}
    if h_ortak < 32:
        # det motoru bu kısalıkta güvenilmez (bkz. saglik.py DET_MIN_KIRPIM_PX
        # kanıtı) -- metin denetimi yapılamaz; NCC+örtüşme kapıları geçilmişti,
        # boş/metinsiz kısa dikiş vacuous-geçer (Kimi kuralı: eksik TOLERE).
        return sonuc
    crop_prev = prev_gray[py0:py0 + h_ortak, :]
    crop_new = new_gray[ny0:ny0 + h_ortak, :]
    boxes_p = _f1b_det_boxes(crop_prev) or []
    boxes_n = _f1b_det_boxes(crop_new) or []
    sonuc["kutu_prev"] = len(boxes_p)
    sonuc["kutu_new"] = len(boxes_n)
    if not boxes_p or not boxes_n:
        return sonuc  # bir tarafta hiç kutu yok -- eksik TOLERE (çelişki tanımsız)
    def _sinira_degiyor(box) -> bool:
        # box[5]=y0piksel, box[7]=y1piksel (bkz. _f1b_det_boxes şeması)
        return box[5] < ATLAS_SEAM_KENAR_PAY or box[7] > h_ortak - ATLAS_SEAM_KENAR_PAY

    kullanildi: set[int] = set()
    for bp in _f1b_boxes_sorted(boxes_p):
        if _sinira_degiyor(bp):
            continue  # sınır-kesikli kutu -- yapısal kırpım artefaktı, MUAF
        # konum-eşleşme: en yakın merkezli yeni-kutu (normalize koordinatta)
        best_j, best_d = None, None
        for j, bn in enumerate(boxes_n):
            if j in kullanildi:
                continue
            d = abs(bp[0] - bn[0]) + abs(bp[1] - bn[1])
            if best_d is None or d < best_d:
                best_j, best_d = j, d
        if best_j is None or best_d is None or best_d > 2 * F1B_CENTER_TOL:
            continue  # eşleşmemiş kutu -- TOLERE
        kullanildi.add(best_j)
        bn = boxes_n[best_j]
        if _sinira_degiyor(bn):
            continue  # karşı-taraf sınır-kesikli -- MUAF
        text_p, conf_p = _f1c_rec_text(crop_prev, bp)
        text_n, conf_n = _f1c_rec_text(crop_new, bn)
        if conf_p < ATLAS_SEAM_CONF or conf_n < ATLAS_SEAM_CONF:
            continue  # düşük-güvenli -- TOLERE (Kimi kuralı)
        na = _f1c_normalize_text(text_p)
        nb = _f1c_normalize_text(text_n)
        sonuc["kontrol_cift"] += 1
        if na == nb:
            continue
        tok_a, tok_b = na.split(), nb.split()
        uyusuyor = False
        if len(tok_a) == len(tok_b):
            uyusuyor = all(
                ta == tb or (len(ta) > ATLAS_SEAM_KISA_TOKEN and len(tb) > ATLAS_SEAM_KISA_TOKEN
                             and _levenshtein(ta, tb) <= 1)
                for ta, tb in zip(tok_a, tok_b)
            )
        else:
            # kelime-bölme farkı ("johnsmith" vs "john smith"): boşluksuz kıyas
            ja, jb = na.replace(" ", ""), nb.replace(" ", "")
            uyusuyor = ja == jb or (len(ja) > ATLAS_SEAM_KISA_TOKEN and len(jb) > ATLAS_SEAM_KISA_TOKEN
                                     and _levenshtein(ja, jb) <= 1)
        if not uyusuyor:
            sonuc["celiski"].append({"prev": na, "new": nb,
                                      "conf": [round(conf_p, 3), round(conf_n, 3)]})
    sonuc["gecti"] = len(sonuc["celiski"]) == 0
    return sonuc


def _atlas_dy_tutarli(a: dict, b: dict, *, oran: float = ATLAS_DY_TOL_ORAN) -> bool:
    """REVİZYON (koordinatör direktifi): artık zincir-KIRICI değil, yalnız
    manifest TEŞHİS bayrağı (dy_tutarli alanı -- anti-gaming denetimi md.4 için
    izlenebilirlik). Gerekçe: bant-kırpım orijin farkı yüzünden çift-dy'si sabit
    hızlı gerçek scroll'da bile değişken (bkz. ATLAS_DY_TOL_ORAN sabit notu,
    hizli-silah ölçümü). Karşılaştırma dy-HIZI (px/kare, 'dy_rate') üzerinden --
    temsilci kart-kareleri zaman ekseninde eşit aralıklı değildir (gecmisten-
    gelen kanıtı); 'dy_rate' yoksa ham dy'ye düşülür."""
    da = a.get("dy_rate", a["dy"])
    db = b.get("dy_rate", b["dy"])
    if (da >= 0) != (db >= 0):
        return False
    m = max(abs(da), abs(db))
    if m <= 1e-6:
        return False
    return abs(da - db) / m <= oran


def _atlas_refine_seam_row(card: np.ndarray, candidate_row: int, line_h: int, *, yon: str = "erken") -> int:
    """Dikiş satırını, yatay kenar-yoğunluğu (Sobel-y) profilinin candidate_row
    çevresindeki YEREL minimumuna yaslar -- bağlı bir metin satırının/glifin
    ortadan bölünmesini önler (hakem sentezi md.3, 'bağlı-bileşen bölünmez').

    `yon` YÖN KISITI (pilot görsel-kanıt fix'i -- hizli-silah atlası): arama
    penceresi TEK yönlüdür. "erken" (alt-büyüme: piece=card[cut:]) -> dikiş
    yalnız candidate_row'dan ERKEN (örtüşmenin İÇİNE) kayabilir; erken kayan
    dikişte fazladan kopyalanan satırlar önceki kartın AYNI dünya-satırlarının
    üzerine hizalı yazılır (zararsız), GEÇ kayan dikişte ise [candidate,cut)
    satırları hiçbir karttan kopyalanmaz -- SİYAH BANT + yarım-satır KAYBI
    (ölçüldü: hizli-silah ilk atlasında ~15px bantlar, 'Reverend Slater' satırı
    yarım). "gec" (üst-büyüme: piece=card[:cut]) simetrik olarak yalnız GEÇ."""
    h = card.shape[0]
    candidate_row = max(0, min(h, candidate_row))
    radius = max(2, line_h // 2)
    if yon == "erken":
        y0 = max(0, candidate_row - radius)
        y1 = min(h, candidate_row + 1)
    else:  # "gec"
        y0 = max(0, candidate_row)
        y1 = min(h, candidate_row + radius + 1)
    if y1 - y0 < 3:
        return candidate_row
    gray = cv2.cvtColor(card, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gy = np.abs(cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3))
    profil = gy[y0:y1, :].mean(axis=1)
    best = int(np.argmin(profil))
    return y0 + best


def _atlas_stitch_chain(cards: list[np.ndarray], aligns: list[dict]) -> tuple[np.ndarray, dict] | None:
    """Zincire giren N kartı (BGR, sırayla) kümülatif dünya-koordinatı
    yerleşimiyle tek şeride birleştirir: İLK kart TAM, her sonraki kartın
    yalnız ÖRTÜŞMEYEN (yeni) kısmı eklenir -- yükseklik = toplam kayma, TÜM
    YENİ içerik BİREBİR (piksel-kopyalama, harmanlama YOK) taşınır. Yön-
    bağımsız (dy pozitif/negatif her iki tarafa büyümeyi de doğru işler).

    rapor["atilan_bolgeler"]: her kart için ATILAN (örtüşen, kopyalanmayan)
    YEREL satır aralığı (y0,y1) ya da None (hiç atılmadı -- kart0 HER ZAMAN
    None, tamamı korunur). Rec-doğrulama (md.2) SADECE bu aralıkları kontrol
    eder -- kopyalanan (asla atılmayan) pikseller yapısal olarak zaten
    korunuyor; onların token'ını da istemek yalnız OCR'ın aynı pikseli farklı
    kırpım-bağlamında (tek sayfa vs uzun atlas) FARKLI okumasından kaynaklanan
    YANLIŞ-ALARM üretir, gerçek bir içerik-kaybı riskini YAKALAMAZ.

    rapor["katki_araliklari"]: her kart için atlas-YEREL (bu şeridin 0..canvas_h
    çerçevesi) KOPYALANAN aralık(lar)ı -- [(y0,y1), ...], kart0 için HER ZAMAN
    tek [(top0, top0+h0)] (tamamı kopyalanır). M10 protected-pair taşıma
    (_atlas_post_process) BUNU kullanır: bir üye korunan_esleme taşıyorsa,
    yalnız BU aralık(lar) atlas bloğunun korunan_alt_araliklar'ına eklenir --
    TÜM-ŞERİT MUAFİYETİ YASAK (bkz. docs M10)."""
    n = len(cards)
    if n < 2 or len(aligns) != n - 1:
        return None
    w = cards[0].shape[1]
    if any(c.shape[1] != w for c in cards):
        return None
    shift = [0.0]
    for a in aligns:
        shift.append(shift[-1] - a["dy"])
    heights = [int(c.shape[0]) for c in cards]
    lo = min(shift[k] for k in range(n))
    hi = max(shift[k] + heights[k] for k in range(n))
    canvas_h = int(round(hi - lo))
    if canvas_h < heights[0] or canvas_h > ATLAS_CANVAS_H_MAKS:
        return None
    canvas = np.zeros((canvas_h, w, 3), np.uint8)
    top0 = int(round(shift[0] - lo))
    canvas[top0:top0 + heights[0], :] = cards[0]
    covered_lo, covered_hi = shift[0], shift[0] + heights[0]
    toplam_yeni_px = 0
    atilan_bolgeler: list[tuple[int, int] | None] = [None]  # kart0: hiç atılmadı
    # M10: kart0 TAM kopyalanır -- atlas-YEREL (canvas 0..canvas_h) katkısı tüm
    # şeridin kendisidir (bkz. korunan_alt_araliklar taşıma -- _atlas_post_process).
    katki_araliklari: list[list[tuple[int, int]]] = [[(top0, top0 + heights[0])]]
    for k in range(1, n):
        card = cards[k]
        h_k = heights[k]
        card_lo, card_hi = shift[k], shift[k] + h_k
        line_h = aligns[k - 1]["line_height"]
        kopyalanan: list[tuple[int, int]] = []  # bu kartın YEREL kopyalanan aralık(lar)ı
        katki_bu_kart: list[tuple[int, int]] = []  # aynı aralık(lar), ATLAS-YEREL (canvas) çerçevesinde
        if card_hi > covered_hi + 1e-6:
            cut_local = max(0.0, covered_hi - card_lo)
            cut_row = _atlas_refine_seam_row(card, int(round(cut_local)), line_h, yon="erken")
            piece = card[cut_row:, :]
            dst0 = int(round(card_lo + cut_row - lo))
            dst1 = min(canvas_h, dst0 + piece.shape[0])
            if dst1 > dst0:
                canvas[dst0:dst1, :] = piece[: dst1 - dst0]
                toplam_yeni_px += dst1 - dst0
                kopyalanan.append((cut_row, cut_row + (dst1 - dst0)))
                katki_bu_kart.append((dst0, dst1))
            covered_hi = max(covered_hi, card_lo + cut_row + (dst1 - dst0))
        if card_lo < covered_lo - 1e-6:
            cut_local = min(float(h_k), covered_lo - card_lo)
            cut_row2 = _atlas_refine_seam_row(card, int(round(cut_local)), line_h, yon="gec")
            piece = card[:cut_row2, :]
            dst1 = int(round(card_lo + cut_row2 - lo))
            dst0 = max(0, dst1 - piece.shape[0])
            if dst1 > dst0:
                canvas[dst0:dst1, :] = piece[-(dst1 - dst0):]
                toplam_yeni_px += dst1 - dst0
                kopyalanan.append((cut_row2 - (dst1 - dst0), cut_row2))
                katki_bu_kart.append((dst0, dst1))
            covered_lo = min(covered_lo, card_lo)
        katki_araliklari.append(katki_bu_kart)
        # ATILAN = [0,h_k) EKSİ kopyalanan aralık(lar) -- basit/güvenli yaklaşım:
        # kopyalanan TEK bir sürekli aralık (normal durum -- bir kart ya üstten
        # ya alttan büyür, ikisi birden NADİR); en büyük kopyalanan parçanın
        # TAMAMLAYICISI atılan sayılır (hiç kopyalanmadıysa TÜM kart atılmıştır).
        if not kopyalanan:
            atilan_bolgeler.append((0, h_k))
        else:
            c0, c1 = max(kopyalanan, key=lambda r: r[1] - r[0])
            if c0 <= 0 and c1 >= h_k:
                atilan_bolgeler.append(None)  # kart tamamı kopyalandı (nadir, tam büyüme)
            elif c0 <= 0:
                atilan_bolgeler.append((c1, h_k))
            elif c1 >= h_k:
                atilan_bolgeler.append((0, c0))
            else:
                # kopyalanan ORTADA -- atılan iki parçalı; basit/güvenli: daha
                # büyük atılan parçayı kontrol kapsamına al (küçük uç zaten
                # komşu karta ait bir sonraki/önceki karşılaştırmada örtük
                # denetlenir; aşırı-mühendislik yerine güvenli-basit tercih).
                atilan_bolgeler.append((0, c0) if c0 >= (h_k - c1) else (c1, h_k))
    rapor = {
        "dy_ort": round(float(np.mean([a["dy"] for a in aligns])), 2),
        "dy_liste": [round(a["dy"], 2) for a in aligns],
        "overlap_ratio": round(1.0 - (toplam_yeni_px / max(1, sum(heights[1:]))), 4),
        "boy_once": heights,
        "boy_sonra": int(canvas_h),
        "atilan_bolgeler": atilan_bolgeler,
        "katki_araliklari": katki_araliklari,
    }
    return canvas, rapor


# NOT (REVİZYON, koordinatör direktifi): bütün-atlas token-kapsama doğrulaması
# (_atlas_verify_rec/_atlas_rec_tokens/_atlas_token_*) KALDIRILDI -- sentetik
# uzun şeridin bütün-OCR'ı satır-parçalanması ve tekrar-garble yüzünden
# güvenilmezdi (ölçüldü: 59/63 sahte red; aynı kelime farklı sayfalarda farklı
# yanlış-okundu, atlasın tek okuması hepsini birebir içeremez). Yerine DİKİŞ-
# DÜZEYİ doğrulama: _atlas_seam_verify (yukarıda) -- örtüşme bölgesinin iki
# GERÇEK sayfa kırpımı karşılaştırılır, sentetik şerit OCR'ına hiç gidilmez.


def _atlas_post_process(
    blocks: list[np.ndarray],
    block_manifest: list[dict],
    block_manifest_idx: list[int],
    run_card_ranges: list[tuple[int, int]],
) -> dict:
    """F4 ana sürücüsü: her 'statik' koşunun kart-aralığında NCC-zincir arar,
    zincir kurulan gruplarda rec-doğrulama ŞARTIYLA blocks/block_manifest'i
    YERİNDE günceller (yalnız çağıran v2_on ise çağırır). block_manifest'teki
    ARADAKİ skip-kayıtları (consecutive-dup/distant-dup vb.) DOKUNULMADAN
    korunur -- yalnız GRUBUN kendi kept-girdileri tek atlas girdisine indirgenir."""
    sayfa_once = len(blocks)
    atlas_gruplari: list[dict] = []
    replacements: list[tuple[int, int, np.ndarray, dict]] = []

    for start, end in run_card_ranges:
        n = end - start
        if n < ATLAS_MIN_CHAIN_EDGES + 1:
            continue
        grays = [cv2.cvtColor(blocks[i], cv2.COLOR_BGR2GRAY) for i in range(start, end)]
        # F4: temsilci kart-kareleri zaman ekseninde eşit aralıklı DEĞİL (medoid
        # seçimi) -- dy_rate (px/kare) için block_manifest'teki timeline_index
        # farkı kullanılır (bkz. _atlas_dy_tutarli docstring'i).
        tlines = [block_manifest[block_manifest_idx[i]].get("timeline_index") for i in range(start, end)]
        aligns: list[dict | None] = []
        for i in range(n - 1):
            a = _atlas_pair_align(grays[i], grays[i + 1])
            if a is not None:
                t0, t1 = tlines[i], tlines[i + 1]
                gap = (t1 - t0) if (t0 is not None and t1 is not None and t1 > t0) else None
                a["frame_gap"] = gap
                a["dy_rate"] = (a["dy"] / gap) if gap else a["dy"]
            aligns.append(a)

        i = 0
        while i < n - 1:
            if aligns[i] is None:
                i += 1
                continue
            # REVİZYON (koordinatör direktifi): zincir = ARDIŞIK geçerli kenarların
            # AYNI dy-YÖNLÜ maksimal koşusu. dy-hız tutarlılığı zincir-kırıcı DEĞİL
            # (bkz. ATLAS_DY_TOL_ORAN notu -- bant-kırpım orijin farkı yüzünden
            # yapısal olarak güvenilmez sinyal); yalnız manifest teşhis alanı.
            # Yön-değişimi (scroll tersine dönemez) zinciri yine KIRAR -- zigzag
            # dikişe karşı minimal geometrik gard.
            chain = [i]
            j = i + 1
            while (
                j < n - 1
                and aligns[j] is not None
                and (aligns[j]["dy"] >= 0) == (aligns[chain[-1]]["dy"] >= 0)
            ):
                chain.append(j)
                j += 1
            # chain, EDGE indeksleri listesi (chain[k] = kart[chain[k]]<->kart[chain[k]+1]
            # çifti) -- m kenar zinciri m+1 kart kapsar; bu yüzden hi = son-kenar+2
            # (son-kenarın İKİNCİ kartını da dahil et), son-kenar+1 DEĞİL.
            lo, hi = start + chain[0], start + chain[-1] + 2
            grup_cards = blocks[lo:hi]
            grup_aligns = [aligns[k] for k in chain]
            grup_kayit: dict = {"sayfalar": [lo, hi - 1], "sayfa_sayisi": hi - lo}
            # dy-tutarlılık TEŞHİS bayrağı (anti-gaming md.4 izlenebilirliği)
            grup_kayit["dy_tutarli"] = all(
                _atlas_dy_tutarli(grup_aligns[k], grup_aligns[k + 1])
                for k in range(len(grup_aligns) - 1)
            ) if len(grup_aligns) > 1 else True
            # DİKİŞ-DÜZEYİ rec-doğrulama (Kimi kuralı): HER dikiş ayrı denetlenir.
            # Stitch'ten ÖNCE koşulur (rec maliyeti dikiş-kırpımlarıyla sınırlı;
            # sentetik şerit OCR'ı hiç yok).
            seam_sonuclari = []
            seam_gecti: list[bool] = []
            for k_idx, k in enumerate(chain):
                sv = _atlas_seam_verify(grays[k], grays[k + 1], grup_aligns[k_idx])
                seam_gecti.append(sv["gecti"])
                seam_sonuclari.append({
                    "dikis": [start + k, start + k + 1],
                    "gecti": sv["gecti"],
                    "kontrol_cift": sv["kontrol_cift"],
                    "kutu": [sv["kutu_prev"], sv["kutu_new"]],
                    "overlap_h": sv["overlap_h"],
                    **({"celiski": sv["celiski"][:5]} if sv["celiski"] else {}),
                })
            grup_kayit["dikisler"] = seam_sonuclari
            # ZİNCİR-BÖLME (koordinatör direktifi ruhu -- 'dikişlerin hepsi geçerse
            # atlas geçer' kuralı ALT-ZİNCİR başına uygulanır): çelişkili dikiş
            # zinciri KIRAR ama geçen-dikişli ardışık alt-zincirler bağımsız
            # kabul edilir (her alt-zincirin TÜM dikişleri geçmiştir). Çelişkili
            # dikişin paylaştığı kartlar yalnız KOMŞU alt-zincirlere gider --
            # alt-zincirler kart paylaşmaz (kenar b'de kırılınca: A=..b-1 kenarı
            # -> kart b'ye kadar; B=b+1 kenarından -> kart b+1'den; ayrık).
            alt_zincirler: list[list[int]] = []
            cur: list[int] = []
            for k_idx, k in enumerate(chain):
                if seam_gecti[k_idx]:
                    cur.append(k)
                else:
                    if cur:
                        alt_zincirler.append(cur)
                    cur = []
            if cur:
                alt_zincirler.append(cur)
            kabul_sayisi = 0
            son_kenar_kabul = False
            for alt in alt_zincirler:
                a_lo, a_hi = start + alt[0], start + alt[-1] + 2
                alt_cards = blocks[a_lo:a_hi]
                alt_aligns = [aligns[k] for k in alt]
                stitched = _atlas_stitch_chain(alt_cards, alt_aligns)
                if stitched is None:
                    continue  # bu alt-zincir kurulamadı; kartlar aynen kalır
                canvas, rapor = stitched
                rapor.pop("atilan_bolgeler", None)  # dikiş-doğrulamada kullanılmıyor
                katki_araliklari = rapor.pop("katki_araliklari", None) or []
                # M10 (docs/MITAS_Master_Dup_Kok_Sebep_Plani_v1.md, K3 protected-pair
                # taşıma): atlasa giren üye sayfalardan `korunan_esleme` taşıyanların
                # ATLAS-YEREL (bu bloğun 0..h çerçevesi) katkı aralık(lar)ı taşınır --
                # yalnız BU aralıklar; TÜM-ŞERİT MUAFİYETİ YASAK (saglik.py'nin K3
                # muafiyeti bu yüzden zayıflamıştı -- bkz. M10 kök-sebep notu).
                korunan_alt_araliklar: list[list[int]] = []
                korunan_esleme_tasinan: list[dict] = []
                for m, k_global in enumerate(range(a_lo, a_hi)):
                    uye_manifest = block_manifest[block_manifest_idx[k_global]]
                    korunan = uye_manifest.get("korunan_esleme") if isinstance(uye_manifest, dict) else None
                    if not korunan:
                        continue
                    uye_katki = katki_araliklari[m] if m < len(katki_araliklari) else []
                    for y0, y1 in uye_katki:
                        korunan_alt_araliklar.append([int(y0), int(y1)])
                    korunan_esleme_tasinan.append({
                        "sayfa": k_global,
                        "korunan_esleme": korunan,
                        "atlas_yerel_araliklar": [[int(y0), int(y1)] for y0, y1 in uye_katki],
                    })
                alt_kayit = {
                    "sayfalar": [a_lo, a_hi - 1], "sayfa_sayisi": a_hi - a_lo, **rapor,
                }
                yeni_manifest = {
                    "kind": "static_page_atlas",
                    "h": int(canvas.shape[0]), "w": int(canvas.shape[1]),
                    "atlas_uye_sayfalar": [
                        dict(block_manifest[block_manifest_idx[k]]) for k in range(a_lo, a_hi)
                    ],
                    "atlas_bilgisi": dict(alt_kayit),
                }
                if korunan_alt_araliklar:
                    yeni_manifest["korunan_alt_araliklar"] = korunan_alt_araliklar
                    yeni_manifest["korunan_esleme_tasinan"] = korunan_esleme_tasinan
                replacements.append((a_lo, a_hi, canvas, yeni_manifest))
                grup_kayit.setdefault("kabul_alt_zincirler", []).append(alt_kayit)
                kabul_sayisi += 1
                if alt[-1] == chain[-1]:
                    son_kenar_kabul = True
            if kabul_sayisi == len(alt_zincirler) and kabul_sayisi > 0 and all(seam_gecti):
                grup_kayit["rec_dogrulama"] = "gecti"
            elif kabul_sayisi > 0:
                grup_kayit["rec_dogrulama"] = "kismi"
                grup_kayit["red_sebebi"] = "dikis_rec_celiski_kismi"
            else:
                grup_kayit["rec_dogrulama"] = "atildi"
                grup_kayit["red_sebebi"] = (
                    "dikis_rec_celiski" if not all(seam_gecti) else "stitch_basarisiz"
                )
            atlas_gruplari.append(grup_kayit)
            # YEREL kenar-imleci ilerletme: zincirin SON kenarı bir kabul-edilen
            # alt-zincire girdiyse son kart tüketildi -- bir sonraki kenar
            # (chain[-1]+1, o kartı paylaşır) kullanılamaz, +2'ye atla. Aksi
            # halde +1'den devam (replacement aralıkları asla çakışmaz).
            i = chain[-1] + (2 if son_kenar_kabul else 1)

    if replacements:
        manifest_action: dict[int, dict] = {}
        drop_positions: set[int] = set()
        for lo, hi, _canvas, yeni_manifest in replacements:
            manifest_action[block_manifest_idx[lo]] = yeni_manifest
            for k in range(lo + 1, hi):
                drop_positions.add(block_manifest_idx[k])
        final_manifest = []
        for idx, entry in enumerate(block_manifest):
            if idx in manifest_action:
                final_manifest.append(manifest_action[idx])
            elif idx in drop_positions:
                continue
            else:
                final_manifest.append(entry)
        block_manifest[:] = final_manifest

        for lo, hi, canvas, _m in sorted(replacements, key=lambda r: -r[0]):
            blocks[lo:hi] = [canvas]

    return {
        "atlas_gruplari": atlas_gruplari,
        "sayfa_sayisi_once": sayfa_once,
        "sayfa_sayisi_sonra": len(blocks),
    }


def compose_reading_runaware(frames: list[str], p: Params, args) -> tuple[np.ndarray | None, dict, None]:
    """Parallel reading master: scroll runs as slit, static/noisy runs as pages.

    This is intentionally not the canonical master. It is more inclusive, keeps
    short/noisy timeline spans visible, and is meant for OCR/VL comparison.
    """
    # MITAS_MASTER_V2 (Görev M4): ÇAĞRI ZAMANINDA okunur -- bayrak kapalıyken
    # v2_on=False, F1 dalı çalışmaz (bit-parite: harness/master_dup/test_bit_parite.py).
    v2_on = _v2_enabled()
    strict_runs = split_runs(frames, p, args)
    strict_static = sum(int(r[1]) - int(r[0]) + 1 for r in strict_runs if r[2] == "S")
    strict_scroll = sum(int(r[1]) - int(r[0]) + 1 for r in strict_runs if r[2] == "R")
    strict_scroll_frac = strict_scroll / max(1, strict_static + strict_scroll)
    if strict_scroll_frac >= READING_PASSTHROUGH_SCROLL_FRAC:
        passthrough, slit_manifest, _ = compose_slit(frames, p, args)
        if passthrough is not None:
            kept = [m for m in slit_manifest if isinstance(m, dict) and "h" in m and "skip" not in m]
            return passthrough, {
                "mode": "reading_runaware_passthrough",
                "reason": "high_scroll_frac",
                "frames": len(frames),
                "runs": [[int(a), int(b), str(t)] for a, b, t in strict_runs],
                "strict_scroll_frac": round(strict_scroll_frac, 4),
                "passthrough_threshold": READING_PASSTHROUGH_SCROLL_FRAC,
                "status": "OK",
                "size": [int(passthrough.shape[1]), int(passthrough.shape[0])],
                "kept_blocks": len(kept),
                "blocks": slit_manifest,
            }, None

    runs = split_runs_reading(frames, p, args)
    opening_frames = max(0, int(getattr(args, "reading_opening_frames", READING_OPENING_FRAMES)))
    opening_min_hold = max(
        2,
        int(getattr(args, "reading_opening_min_hold", READING_OPENING_CARD_MIN_HOLD)),
    )
    reading_min_hold = max(
        2,
        int(getattr(args, "reading_card_min_hold", READING_CARD_MIN_HOLD)),
    )
    reading_same_thr = max(
        1,
        int(getattr(args, "reading_card_same_thr", READING_CARD_SAME_THR)),
    )
    early_split_frames = max(
        0,
        int(getattr(args, "reading_early_split_frames", READING_EARLY_SPLIT_FRAMES)),
    )
    blocks: list[np.ndarray] = []
    block_manifest: list[dict] = []
    last_static_hash: int | None = None
    last_static_mask: np.ndarray | None = None
    last_static_index: int | None = None
    card_registry: list[dict] = []    # F1: {"dhash","mask","block_index"} -- yalnız v2_on
    block_kinds: list[str] = []       # F2: "scroll_slit"/"card" -- ardışık scroll tespiti
    block_manifest_idx: list[int] = []      # F4: blocks[i] <-> block_manifest[block_manifest_idx[i]]
    # F4 (run_card_ranges): ana run-döngüsü BİTTİKTEN SONRA block_kinds'ten
    # türetilir (bkz. döngü sonu) -- burada YER TUTUCU gerekmiyor.

    def _frame_text_block(frame: str) -> tuple[np.ndarray | None, np.ndarray | None, str | None]:
        image = _prep(frame, p, args)
        if image is None:
            return None, None, "unreadable"
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        mask = text_mask(gray, p, args.polarity)
        band = text_rows(mask, p) or text_band(mask)
        if band is None:
            return None, None, "no-text-band"
        y0 = max(0, int(band[0]) - p.pad)
        y1 = min(image.shape[0], int(band[1]) + p.pad)
        if y1 <= y0:
            return None, None, "empty-band"
        return image[y0:y1, :].copy(), mask, None

    def _best_static_block(card_frames: list[str]) -> tuple[
        np.ndarray | None,
        str | None,
        int | None,
        float | None,
        int | None,
        np.ndarray | None,
        str | None,
    ]:
        candidates = []
        last_skip = "no-text"
        for rel, frame in enumerate(card_frames):
            block, full_mask, skip = _frame_text_block(frame)
            if block is None:
                last_skip = skip or last_skip
                continue
            score = sharpv(cv2.cvtColor(block, cv2.COLOR_BGR2GRAY))
            candidates.append((score, frame, rel, block, _textmask_dhash(block, p, args), full_mask))
        best, stability_distance = _best_stable_candidate(candidates)
        if best is None:
            return None, None, None, None, None, None, last_skip
        score, frame, rel, block, _, full_mask = best
        return block, frame, rel, score, stability_distance, full_mask, None

    def _append_static(block: np.ndarray, full_mask: np.ndarray, meta: dict, frame_path: str | None = None) -> None:
        nonlocal last_static_hash, last_static_mask, last_static_index
        if block is None or not block.size or block.shape[0] < 2:
            return
        thh = _textmask_dhash(block, p, args)
        is_dup = last_static_hash is not None and hamming(thh, last_static_hash) <= 2
        current_index = meta.get("timeline_index")
        if (
            not is_dup
            and last_static_mask is not None
            and last_static_index is not None
            and current_index is not None
            and int(last_static_index) < opening_frames
            and int(current_index) < opening_frames
        ):
            response, iou = _aligned_text_mask_similarity(last_static_mask, full_mask)
            is_dup = response >= 0.5 and iou >= 0.5
        if is_dup:
            skipped = dict(meta)
            skipped["skip"] = "consecutive-dup"
            block_manifest.append(skipped)
            return
        full_gray = None
        korunan_kanit = None
        if v2_on:
            # F1 (H2 kök-sebep -- birincil, 60/112 film): yukarıdaki kontroller yalnız
            # HEMEN ÖNCEKİ kartla kıyaslar. Burada kart ÖNCEKİ TÜM kartlarla (global
            # kayıt) üç-kapılı denetimden geçirilir -- ardışık-OLMAYAN tekrar (kart A
            # -> sahne -> kart A yine girer) böylece yakalanır. Herhangi bir kapı
            # tutmazsa None -- kart KORUNUR (yanlış-silmeye ASLA yatmaz).
            match = _card_distant_dup_match(thh, full_mask, card_registry)
            if match is not None:
                skipped = dict(meta)
                skipped["skip"] = "distant-dup"
                skipped.update(match)
                block_manifest.append(skipped)
                return
            # F1b DÜZELTMESİ: F1 dHash aday kapısı GRENLİ donuk-sahne sayfalarında
            # hiç tetiklenmiyordu (görsel kanıt: BAŞKAN_VE_MARI). Hash ön-elemesi
            # OLMADAN gri piksel-benzerlik + det-only kutu doğrulaması ile EK kapı.
            if frame_path is not None:
                image = _prep(frame_path, p, args)
                if image is not None:
                    full_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                    match_f1b, korunan_kanit = _card_distant_dup_match_f1b(full_gray, card_registry)
                    if match_f1b is not None:
                        skipped = dict(meta)
                        skipped["skip"] = match_f1b.pop("karar_yolu")
                        skipped.update(match_f1b)
                        block_manifest.append(skipped)
                        return
        blocks.append(block)
        block_kinds.append("card")
        if v2_on:
            card_registry.append({
                "dhash": thh, "mask": full_mask, "block_index": len(blocks) - 1,
                "gray": full_gray,
            })
        last_static_hash = thh
        last_static_mask = full_mask
        last_static_index = int(current_index) if current_index is not None else None
        kept = dict(meta)
        kept["h"] = int(block.shape[0])
        kept["w"] = int(block.shape[1])
        # K3 (Görev M8): korunan kart, sıkı kanıt şartını (det>=1 + rec conf>=0.7 +
        # normalize Levenshtein>=3 VEYA Jaccard<=0.7) karşılıyorsa manifest kaydı --
        # karar mantığını DEĞİŞTİRMEZ, saglik.py'nin protected-çift muafiyeti için.
        if v2_on and korunan_kanit is not None:
            kept["korunan_esleme"] = korunan_kanit
        block_manifest_idx.append(len(block_manifest))  # F4: blocks[-1] <-> bu girdi
        block_manifest.append(kept)

    def _append_static_pages(run_frames: list[str], run_meta: dict) -> None:
        if getattr(args, "no_card_split", False):
            cards = [run_frames]
        else:
            cards = split_static_cards(
                run_frames,
                p,
                args,
                timeline_offset=int(run_meta["run"][0]),
                opening_frame_limit=opening_frames,
                opening_min_hold=opening_min_hold,
                min_hold_override=reading_min_hold,
                same_thr_override=reading_same_thr,
                chain_stability=True,
            )
            cards = _merge_short_reading_cards(
                cards,
                timeline_offset=int(run_meta["run"][0]),
                opening_frame_limit=opening_frames,
                opening_min_hold=opening_min_hold,
                min_hold=reading_min_hold,
            )
            cards = _split_long_reading_cards(
                cards,
                p,
                args,
                min_hold=reading_min_hold,
                same_thr=reading_same_thr,
                timeline_offset=int(run_meta["run"][0]),
                frame_limit=early_split_frames,
            )
        card_cursor = 0
        for ci, card_frames in enumerate(cards):
            block, frame, rel, score, stability_distance, full_mask, skip = _best_static_block(card_frames)
            timeline_index = (
                int(run_meta["run"][0]) + card_cursor + int(rel)
                if rel is not None
                else None
            )
            meta = {
                **run_meta,
                "kind": "static_page",
                "card": int(ci),
                "card_frames": len(card_frames),
                "rel": int(rel) if rel is not None else None,
                "timeline_index": timeline_index,
                "src": Path(frame).name if frame else None,
            }
            card_cursor += len(card_frames)
            if score is not None:
                meta["sharpness"] = round(float(score), 3)
            if stability_distance is not None:
                meta["stability_distance"] = int(stability_distance)
            if block is None:
                meta["skip"] = skip
                block_manifest.append(meta)
                continue
            _append_static(block, full_mask, meta, frame_path=frame)

    for start, end, label in runs:
        si, ei = int(start), int(end)
        run_frames = frames[si: ei + 1]
        run_meta = {"run": [si, ei], "lab": str(label), "frames": len(run_frames)}

        if label == "R":
            # allow_demote=True: DEMOTE kararı None döndürür → mevcut statik-sayfa
            # fallthrough'u devreye girer (kısmi-çökme baypası da böylece kapanır).
            block, hy = slitscan(run_frames, p, args, allow_demote=True)
            if block is not None and block.size:
                seam = None
                if v2_on and block_kinds and block_kinds[-1] == "scroll_slit":
                    # F2 (H1 kök-sebep): aralarında statik/kart bloğu OLMAYAN iki
                    # ardışık slit bloğu -- dikiş örtüşmesini NCC ile bul+kırp.
                    seam = _slit_seam_crop(blocks[-1], block)
                    if seam is not None:
                        block = block[seam["kirpilan_px"]:, :]
                girdi = {
                    **run_meta,
                    "kind": "scroll_slit",
                    "h": int(block.shape[0]),
                    "w": int(block.shape[1]),
                    "src_first": Path(run_frames[0]).name if run_frames else None,
                    "src_last": Path(run_frames[-1]).name if run_frames else None,
                }
                if seam is not None:
                    girdi["dikis"] = seam
                if SLIT_DY_HYBRID == "1" and hy:
                    girdi["hybrid"] = _hy_manifest_ozet(hy, int(block.shape[0]))
                blocks.append(block)
                block_kinds.append("scroll_slit")
                last_static_hash = None
                last_static_mask = None
                last_static_index = None
                block_manifest_idx.append(len(block_manifest))  # F4: blocks[-1] <-> bu girdi
                block_manifest.append(girdi)
                continue
            girdi = {**run_meta, "kind": "scroll_slit",
                     "skip": "demote" if (hy and hy.get("applied") and hy.get("decision") == "DEMOTE")
                     else "empty"}
            if SLIT_DY_HYBRID == "1" and hy:
                girdi["hybrid"] = _hy_manifest_ozet(hy, 0)
            block_manifest.append(girdi)

        _append_static_pages(run_frames, run_meta)

    # F4 (Görev M10, Şerit-Atlası): yalnız v2_on -- ardışık 'statik' SAYFALARI
    # NCC-zincir ile atlas şeridine birleştirir (rec-doğrulama ŞARTIYLA).
    # Kapsam: block_kinds'te KESİNTİSİZ "card" aralıkları (final İSTİF SIRASINDA
    # fiziksel bitişiklik) -- split_runs_reading'in ORİJİNAL run sınırı DEĞİL.
    # ÖLÇÜLMÜŞ KANIT (belki-bir-gun pilotu): yavaş-kayan listeler pratikte tek
    # bir uzun "S" run'a değil, art arda gelen ÇOK SAYIDA KISA "S" run'a
    # bölünüyor (split_runs_reading'in kendi gürültüsü) -- run-sınırlı kapsam bu
    # yüzden gerçek adayların büyük kısmını KAÇIRIYORDU (belki-bir-gun'da 7 aday
    # grup, run-sınırlı taramada 0 -- hiçbiri >=3 kart içeren TEK bir run'a
    # sığmıyordu). Aralarında scroll_slit blok YOKSA (block_kinds kesintisiz)
    # bu sayfalar zaten final PNG'de bitişik duruyor -- atlas için önemli olan
    # BUDUR, hangi run-nesnesinden geldikleri değil. Güvenlik DEĞİŞMEDİ: NCC +
    # rec-doğrulama kapıları aynı sıkılıkta, yalnız ADAY HAVUZU genişledi.
    run_card_ranges: list[tuple[int, int]] = []
    ci = 0
    while ci < len(block_kinds):
        if block_kinds[ci] == "card":
            cj = ci
            while cj < len(block_kinds) and block_kinds[cj] == "card":
                cj += 1
            run_card_ranges.append((ci, cj))
            ci = cj
        else:
            ci += 1

    atlas_rapor: dict | None = None
    if v2_on and run_card_ranges:
        atlas_rapor = _atlas_post_process(blocks, block_manifest, block_manifest_idx, run_card_ranges)

    manifest = {
        "mode": "reading_runaware",
        "frames": len(frames),
        "runs": [[int(a), int(b), str(t)] for a, b, t in runs],
        "strict_runs": [[int(a), int(b), str(t)] for a, b, t in strict_runs],
        "strict_scroll_frac": round(strict_scroll_frac, 4),
        "passthrough_threshold": READING_PASSTHROUGH_SCROLL_FRAC,
        "static_policy": "card_chain_split_text_layout_medoid",
        "uncertain_policy": "cut_boundary_short_motion_static",
        "opening_card_policy": {
            "frames": opening_frames,
            "min_hold": opening_min_hold,
            "default_min_hold": reading_min_hold,
            "same_threshold": reading_same_thr,
            "early_split_frames": early_split_frames,
        },
        "blocks": block_manifest,
    }
    if atlas_rapor is not None:
        # F4 (Görev M10): atlas_gruplari HEM kabul (rec_dogrulama="gecti") HEM RED
        # (rec_dogrulama="atildi") adaylarını içerir -- anti-gaming/G0 denetimi için
        # her ateşleme (kabul edilmese bile) tek tek izlenebilir olsun diye.
        manifest["atlas_gruplari"] = atlas_rapor["atlas_gruplari"]
        manifest["sayfa_sayisi_once"] = atlas_rapor["sayfa_sayisi_once"]
        manifest["sayfa_sayisi_sonra"] = atlas_rapor["sayfa_sayisi_sonra"]
    if not blocks:
        manifest["status"] = "NO_OUTPUT"
        return None, manifest, None

    max_width = max(block.shape[1] for block in blocks)
    normalized = [
        cv2.copyMakeBorder(block, 0, 0, 0, max_width - block.shape[1],
                           cv2.BORDER_CONSTANT, value=(0, 0, 0))
        if block.shape[1] < max_width else block
        for block in blocks
    ]
    stacked = []
    for block in normalized:
        stacked.append(block)
        stacked.append(np.zeros((SEP_PX, max_width, 3), np.uint8))
    master = np.vstack(stacked[:-1])
    manifest["status"] = "OK"
    manifest["size"] = [int(master.shape[1]), int(master.shape[0])]
    manifest["kept_blocks"] = len(blocks)
    if v2_on:
        # K1 (Görev M8): rec-çağrı sayacı -- süre/maliyet gözlemi (film başına
        # clear_cache() ile sıfırlanır, process_film()'in zaten çağırdığı nokta).
        manifest["rec_calls"] = rec_call_count()
        if manifest["rec_calls"] > REC_CALL_WARN_ESIK:
            print(f"  [K1 UYARI] rec-çağrı sayısı yüksek: {manifest['rec_calls']} "
                  f"(> {REC_CALL_WARN_ESIK})", file=sys.stderr)
    return master, manifest, None


# --------------------------------------------------------------------------- #
# MODE B: motion-compensated mosaic
# --------------------------------------------------------------------------- #
def estimate_offsets(frames: list[str], p: Params, args):
    """Pass 1: per-frame global vertical offset from TEXT motion (bg ignored)."""
    hann = cv2.createHanningWindow((p.w, p.h), cv2.CV_32F)
    prev = None
    prev_any = False
    dys = []
    resp = []
    valid = []          # True only if phaseCorrelate actually ran for this frame
    dropped = 0

    for frame in frames:
        image = _prep(frame, p, args)
        if image is None:
            dropped += 1
            dys.append(0.0)
            resp.append(0.0)
            valid.append(False)
            continue
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        mask = cv2.dilate(text_mask(gray, p, args.polarity), np.ones((11, 11), np.uint8))
        masked = gray.astype(np.float32)
        masked[mask == 0] = 0.0

        dy, r, measured = 0.0, 0.0, False
        if prev is not None and prev_any and bool(mask.any()):
            (_, dy), r = cv2.phaseCorrelate(prev * hann, masked * hann)
            measured = True
        prev = masked
        prev_any = bool(mask.any())
        dys.append(dy)
        resp.append(r)
        valid.append(measured)

    dys = np.array(dys)
    resp = np.array(resp)
    valid = np.array(valid)

    # FIX: a cut is only meaningful where we actually measured motion. The first
    # frame and any dropped/blank frame are NOT cuts (they used to be, because
    # their correlation peak is 0 -> they wrongly shoved the canvas).
    cut = valid & ((np.abs(dys) > p.cut) | (resp < args.cut_resp))

    # FIX: resolve dominant scroll direction up front so static->scroll segments
    # don't get mis-stacked by a post-integration flip.
    scroll_vals = dys[valid & ~cut]
    scroll_vals = scroll_vals[np.abs(scroll_vals) > p.vmin]
    sign = 1.0
    if scroll_vals.size and float(np.median(scroll_vals)) < 0:
        sign = -1.0
    if args.flip:
        sign = -sign

    clean = dys * sign
    clean[cut] = 0.0
    clean[~valid] = 0.0   # dropped / blank frame -> no advance
    clean = np.array([np.median(clean[max(0, i - 1): i + 2]) for i in range(len(clean))])
    return clean, cut, valid, dropped, dys, resp, sign


def _mosaic_debug(frames, raw, resp, valid, cut, clean, pos, sign) -> dict:
    return {
        "frames": [Path(f).name for f in frames],
        "dy_raw": [round(float(x), 3) for x in raw],
        "resp": [round(float(x), 4) for x in resp],
        "valid": [int(x) for x in valid],
        "cut": [int(x) for x in cut],
        "dy_used": [round(float(x), 3) for x in clean],
        "pos": [round(float(x), 2) for x in pos],
        "sign": float(sign),
    }


def compose_mosaic(frames: list[str], p: Params, args):
    """Pass 2: integrate offsets, composite frames with mask-weighted blend.

    Returns (master | None, manifest, debug | None).
    """
    clean, cut, valid, dropped, raw, resp, sign = estimate_offsets(frames, p, args)

    pos = np.zeros(len(frames))
    acc = 0.0
    for i in range(len(frames)):
        if i == 0:
            continue
        # A cut pushes a full frame down so pre/post-cut content does not overlap.
        acc += p.h if cut[i] else clean[i]
        pos[i] = acc

    # direction already resolved in estimate_offsets; just normalize to >= 0.
    pos -= pos.min()
    debug = _mosaic_debug(frames, raw, resp, valid, cut, clean, pos, sign) if args.debug else None

    canvas_h = int(round(pos.max())) + p.h
    if canvas_h > MAX_CANVAS_H:
        return None, {"mode": "mosaic", "frames": len(frames),
                      "err": f"canvas too tall ({canvas_h}px); motion likely noisy"}, debug

    # BLOAT / CUT-STORM guard: on scroll or noisy motion the offset integration
    # runs away (measured: diriliş 136x/0.39, yalaza 88x/0.37). A GOOD footage
    # static-card mosaic stays small (measured: drakula 3.7x/0.005 = clean cast,
    # once). Reject > 5x or cut-storm > 0.25 -> catches the catastrophes, keeps the
    # clean small ones; the (always-built) slit takes over when rejected.
    bloat = canvas_h / max(1.0, float(p.h))
    cut_frac = float(cut.sum()) / max(1, len(frames))
    if bloat > 5.0 or cut_frac > 0.25:
        return None, {"mode": "mosaic", "frames": len(frames), "reject": True,
                      "bloat": round(bloat, 2), "cut_frac": round(cut_frac, 3),
                      "err": f"reject mosaic: bloat {bloat:.1f}x / cut-storm {cut_frac:.2f}"}, debug

    acc_img = np.zeros((canvas_h, p.w, 3), np.float32)
    wsum = np.zeros((canvas_h, p.w), np.float32)
    # eps lets background contribute faintly; --text-only sets it to 0 so only
    # masked text composites and everything else stays pure black (OCR-ready).
    eps = 0.0 if args.text_only else 0.05
    used = 0

    for i, frame in enumerate(frames):
        image = _prep(frame, p, args)
        if image is None:
            continue
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        mask = cv2.dilate(text_mask(gray, p, args.polarity), np.ones((5, 5), np.uint8))
        weight = mask.astype(np.float32) / 255.0 + eps  # text dominates, bg ~ eps
        y0 = int(round(pos[i]))
        y0 = max(0, min(y0, canvas_h - p.h))
        acc_img[y0: y0 + p.h] += image.astype(np.float32) * weight[..., None]
        wsum[y0: y0 + p.h] += weight
        used += 1

    wsum[wsum == 0] = 1.0
    master = (acc_img / wsum[..., None]).clip(0, 255).astype(np.uint8)

    # crop to the rows that actually carry text
    full_mask = text_mask(cv2.cvtColor(master, cv2.COLOR_BGR2GRAY), p, args.polarity)
    rows = np.where(full_mask.sum(axis=1) > 0)[0]
    if not rows.size:
        return None, {"mode": "mosaic", "frames": len(frames), "used": used,
                      "dropped": int(dropped), "master": None}, debug
    a = max(0, int(rows.min()) - p.pad)
    b = min(master.shape[0], int(rows.max()) + p.pad)
    master = master[a:b]

    manifest = {
        "mode": "mosaic",
        "frames": len(frames),
        "used": used,
        "dropped": int(dropped),
        "cuts": int(cut.sum()),
        "canvas": [int(master.shape[1]), int(master.shape[0])],
    }
    return master, manifest, debug


# --------------------------------------------------------------------------- #
# debug instrumentation
# --------------------------------------------------------------------------- #
def write_debug(base: Path, debug: dict) -> None:
    """Dump per-frame motion estimate. CSV always; PNG plot if matplotlib exists.

    Columns: idx, frame, dy_raw, resp, valid, cut, dy_used, pos
      dy_raw : raw vertical shift from text-masked phase correlation
      resp   : correlation peak (low -> poor match -> likely cut/bg-lock)
      valid  : 1 if phaseCorrelate actually ran (prev+cur both had text)
      cut    : 1 if this frame was treated as a scene cut (canvas pushed)
      dy_used: shift after sign-resolve + cut-zero + median smoothing
      pos    : integrated canvas position (where the frame was placed)
    Look for: pos going flat then jumping, resp collapsing, or runs of cut=1
    inside what should be smooth scroll -> that frame range is the culprit.
    """
    csv_path = base.with_suffix(".debug.csv")
    rows = ["idx,frame,dy_raw,resp,valid,cut,dy_used,pos"]
    fr = debug["frames"]
    for i in range(len(fr)):
        rows.append(
            f'{i},{fr[i]},{debug["dy_raw"][i]},{debug["resp"][i]},'
            f'{debug["valid"][i]},{debug["cut"][i]},{debug["dy_used"][i]},{debug["pos"][i]}'
        )
    csv_path.write_text("\n".join(rows), encoding="utf-8")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        idx = list(range(len(fr)))
        cut_idx = [i for i in idx if debug["cut"][i]]
        fig, ax = plt.subplots(3, 1, figsize=(13, 9), sharex=True)
        ax[0].plot(idx, debug["pos"], lw=1.2)
        for c in cut_idx:
            ax[0].axvline(c, color="r", alpha=0.35, lw=0.8)
        ax[0].set_ylabel("pos (canvas y)")
        ax[0].set_title(f"{base.name}  (red = detected cut)  sign={debug['sign']}")
        ax[1].plot(idx, debug["dy_raw"], lw=0.8, label="dy_raw")
        ax[1].plot(idx, debug["dy_used"], lw=1.0, label="dy_used")
        ax[1].axhline(0, color="k", lw=0.5)
        ax[1].set_ylabel("dy / frame")
        ax[1].legend(loc="upper right")
        ax[2].plot(idx, debug["resp"], lw=0.8, color="g")
        ax[2].set_ylabel("corr peak")
        ax[2].set_xlabel("frame index")
        fig.tight_layout()
        fig.savefig(base.with_suffix(".debug.png"), dpi=110)
        plt.close(fig)
    except Exception:
        pass  # matplotlib not installed -> CSV is enough



def select_master(slit_master, mosaic_master=None, scroll_frac=None, h=None):
    """Single-source master dispatch. MOSAIC ENGINE RETIRED (2026-06-28): on the only
    film it ever won the dispatch (drakula — cast over moving fire, the very case mosaic
    was built for) its motion-comp blend GHOSTED the text and yielded ~half the OCR of
    slit (34 vs 61 lines / 371 vs 687 chars, OneOCR). Slit (sharpest-frame-per-card) is
    canonical for EVERY film. mosaic_master kept only as a last-resort fallback when slit
    is None, so this can never produce a WORSE master than before (only ever flips
    None->something). scroll_frac/h retained for signature compat; no longer used."""
    if slit_master is not None:
        return slit_master, "slit"
    if mosaic_master is not None:
        return mosaic_master, "mosaic"
    return None, None


def process_film(film_dir: Path, out_dir: Path, args) -> dict:
    result = {"film": film_dir.name}
    modes = ["slit", "mosaic"] if args.mode == "both" else [args.mode]

    for seg, subdir in SEGS:
        if args.seg and seg != args.seg:
            continue
        clear_cache()  # FIX(9): bound cache memory per segment
        del HYBRID_LOG[:]   # hibrit gölge kayıtları segment-kapsamlı

        frames = sorted(glob.glob(str(film_dir / subdir / "*.png")), key=nat_sort_key)
        film_safe = safe(film_dir.name, args.hash_names)
        segment_dir = out_dir / film_safe / seg
        segment_dir.mkdir(parents=True, exist_ok=True)

        if not frames:
            (segment_dir / "manifest.json").write_text("{}", encoding="utf-8")
            result[seg] = {"frames": 0}
            continue

        first = first_readable(frames)
        if first is None:
            (segment_dir / "manifest.json").write_text("{}", encoding="utf-8")
            result[seg] = {"frames": len(frames), "err": "no readable frame"}
            continue
        h, w = first.shape[:2]
        if args.deinterlace:
            h = deinterlace(first).shape[0]
        p = derive_params(h, w, args)

        # ----- legacy explicit modes (slit / mosaic / both) for debugging -----
        if args.mode != "master":
            seg_result = {}
            for mode in modes:
                stem = "master" if args.mode != "both" else f"master_{mode}"
                mpath = segment_dir / f"{stem}.png"
                manifest_path = segment_dir / (f"{stem}.json" if args.mode == "both" else "manifest.json")
                if mpath.exists() and not args.overwrite:
                    seg_result[mode] = {"skip": "exists", "path": str(mpath)}
                    continue
                try:
                    if mode == "slit":
                        master, manifest, debug = compose_slit(frames, p, args)
                    else:
                        master, manifest, debug = compose_mosaic(frames, p, args)
                    if master is not None:
                        wr(mpath, master)
                        if args.flat_out is not None:
                            args.flat_out.mkdir(parents=True, exist_ok=True)
                            tag = seg if args.mode != "both" else f"{seg}_{mode}"
                            wr(args.flat_out / f"{film_safe}__{tag}.png", master)
                        seg_result[mode] = {"frames": len(frames),
                                            "master": [int(master.shape[1]), int(master.shape[0])],
                                            "path": str(mpath)}
                    else:
                        seg_result[mode] = {"frames": len(frames), "master": None,
                                            "note": manifest.get("err", "no text") if isinstance(manifest, dict) else "no text"}
                    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
                    if args.debug and debug is not None:
                        write_debug(mpath, debug)
                        seg_result[mode]["debug"] = str(mpath.with_suffix(".debug.csv"))
                except Exception as exc:
                    seg_result[mode] = {"frames": len(frames), "err": repr(exc)[:200]}
            _hybrid_flush(segment_dir)
            result[seg] = seg_result if args.mode == "both" else seg_result[modes[0]]
            continue

        # ----- smart "master" mode: slit canonical + optional mosaic candidate -----
        master_path = segment_dir / "master.png"
        if master_path.exists() and not args.overwrite:
            result[seg] = {"skip": "exists", "path": str(master_path)}
            continue

        info = {"frames": len(frames), "h": int(h), "w": int(w), "flags": [], "warnings": []}
        try:
            runs = split_runs(frames, p, args)
            s_frames = sum((int(r[1]) - int(r[0]) + 1) for r in runs if r[2] == "S")
            r_frames = sum((int(r[1]) - int(r[0]) + 1) for r in runs if r[2] == "R")
            tot = max(1, s_frames + r_frames)
            scroll_frac = r_frames / tot
            info["regime"] = {"runs": len(runs), "static_frames": s_frames,
                              "scroll_frames": r_frames, "scroll_frac": round(scroll_frac, 3)}

            # canonical = slit (scroll via slit-scan + multi-card static via content split)
            slit_master, slit_manifest, _ = compose_slit(frames, p, args)
            kept = [m for m in slit_manifest if isinstance(m, dict) and "h" in m and "skip" not in m]
            n_blocks = len(kept)
            n_card = sum(1 for m in kept if m.get("kind") == "card")
            n_scroll = sum(1 for m in kept if m.get("kind") == "scroll")
            info["slit_blocks"] = n_blocks
            info["card_blocks"] = n_card
            info["scroll_blocks"] = n_scroll
            if slit_master is not None:
                wr(segment_dir / "master_slit.png", slit_master)

            reading_master, reading_manifest, _ = compose_reading_runaware(frames, p, args)
            if reading_master is not None:
                reading_path = segment_dir / "reading_master_runaware.png"
                wr(reading_path, reading_master)
                info["reading_master_runaware"] = {
                    "path": str(reading_path),
                    "size": [int(reading_master.shape[1]), int(reading_master.shape[0])],
                    "kept_blocks": reading_manifest.get("kept_blocks"),
                }
            else:
                info["reading_master_runaware"] = {"status": reading_manifest.get("status", "NO_OUTPUT")}
            (segment_dir / "reading_master_runaware.json").write_text(
                json.dumps(reading_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

            # canonical = slit for every film. Mosaic engine retired (2026-06-28):
            # measured worse than slit on the one film it ever won (drakula). See select_master.
            canonical, info["selected_mode"] = select_master(slit_master)

            if canonical is None:
                info["status"] = "NO_OUTPUT"
                info["flags"].append("no_output")
            else:
                wr(master_path, canonical)
                if args.flat_out is not None:
                    args.flat_out.mkdir(parents=True, exist_ok=True)
                    wr(args.flat_out / f"{film_safe}__{seg}.png", canonical)
                info["status"] = "OK"
                info["master"] = [int(canonical.shape[1]), int(canonical.shape[0])]
                # upstream flags (free, structural) — composer FLAGS, does not fix
                if canonical.shape[0] < int(1.6 * h):
                    info["flags"].append("very_short_master")
                # single_card = ONE card and NO scroll (a real scroll block is not "single card")
                if n_card <= 1 and n_scroll == 0:
                    info["flags"].append("single_card_only")
                if "very_short_master" in info["flags"] and "single_card_only" in info["flags"]:
                    info["flags"].append("no_cast")
                    info["warnings"].append("kredi yok gibi (tek kart / cok kisa) -> upstream klip?")

            info["slit_manifest"] = slit_manifest
        except Exception as exc:
            import traceback
            info["status"] = "ERROR"
            info["err"] = repr(exc)[:300]
            info["trace"] = traceback.format_exc()[-700:]

        (segment_dir / "manifest.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
        _hybrid_flush(segment_dir)
        result[seg] = {k: info.get(k) for k in ("status", "selected_mode", "master", "flags", "frames")}

    return result


def _hybrid_flush(segment_dir: Path) -> None:
    """HİBRİT-DY gölge kayıtlarını AYRI sidecar'a boşalt (ana manifest/PNG'ye dokunmaz;
    SHA bit-identiklik şartının tesisatı). Bayrak '0' iken HYBRID_LOG hep boştur."""
    if not HYBRID_LOG:
        return
    try:
        yol = segment_dir / "hybrid_shadow.jsonl"
        with yol.open("w", encoding="utf-8") as h:
            for kayit in HYBRID_LOG:
                h.write(json.dumps(kayit, ensure_ascii=False) + "\n")
    except Exception as exc:  # noqa: BLE001 — gölge kaydı compose'u ASLA bozamaz
        print(f"[warn] hybrid_shadow yazilamadi: {exc}", flush=True)
    finally:
        del HYBRID_LOG[:]


def select_films(db_root: Path, film_filter: str | None, start: int, count: int) -> list[Path]:
    dirs = sorted([path for path in db_root.iterdir() if path.is_dir()], key=lambda p: p.name)
    if film_filter:
        needle = film_filter.lower()
        matches = [path for path in dirs if needle in path.name.lower()]
        if len(matches) > 1:
            # FIX(12): don't silently swallow extra matches.
            print(f"[warn] --film '{film_filter}' matched {len(matches)} films; "
                  f"using '{matches[0].name}'. Others: "
                  f"{', '.join(m.name for m in matches[1:4])}"
                  + (" ..." if len(matches) > 4 else ""), flush=True)
        return matches[:1]
    return dirs[start: start + count]


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument("--db-root", type=Path, default=DB)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--flat-out", type=Path, default=None)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--film", default=None, help="substring -> single film")
    parser.add_argument("--seg", choices=["giris", "cikis"], default=None)
    parser.add_argument("--overwrite", action="store_true")
    # engine
    parser.add_argument("--mode", choices=["master", "slit", "mosaic", "both"], default="master",
                        help="master (default) = smart dispatch: canonical master.png (slit + content "
                             "card-split) + mosaic candidate + flags. slit/mosaic/both = legacy debug.")
    parser.add_argument("--no-card-split", action="store_true",
                        help="disable content-based static-card splitting (son_metro fix)")
    parser.add_argument("--card-same-thr", type=int, default=6,
                        help="text-mask dHash hamming <= this == same held card")
    parser.add_argument("--card-min-hold", type=int, default=5,
                        help="a new card layout must persist >= this many frames (debounce)")
    parser.add_argument("--reading-opening-frames", type=int, default=READING_OPENING_FRAMES,
                        help="reading master: use sensitive card detection in the first N frames")
    parser.add_argument("--reading-card-min-hold", type=int, default=READING_CARD_MIN_HOLD,
                        help="reading master: minimum held frames outside the opening window")
    parser.add_argument("--reading-card-same-thr", type=int, default=READING_CARD_SAME_THR,
                        help="reading master: text-layout hamming threshold for a held card")
    parser.add_argument("--reading-early-split-frames", type=int, default=READING_EARLY_SPLIT_FRAMES,
                        help="reading master: limit forced internal card splits to the first N frames")
    parser.add_argument("--reading-opening-min-hold", type=int, default=READING_OPENING_CARD_MIN_HOLD,
                        help="reading master: minimum held frames for an opening card")
    parser.add_argument("--polarity", choices=["auto", "bright", "dark"], default="auto",
                        help="bright=light text/dark bg, dark=dark text/light bg")
    parser.add_argument("--deinterlace", action="store_true",
                        help="bob deinterlace for interlaced SD content")
    parser.add_argument("--no-dedup", action="store_true",
                        help="slit: keep duplicate cards instead of dropping them")
    parser.add_argument("--luma-key", action="store_true",
                        help="slit: keep only bright pixels before slit-scan")
    parser.add_argument("--text-only", action="store_true",
                        help="mosaic: drop the background, composite only text on black (OCR-ready)")
    parser.add_argument("--debug", action="store_true",
                        help="mosaic: dump per-frame motion estimate (CSV + plot) next to master")
    parser.add_argument("--hash-names", action="store_true",
                        help="append a hash to output folder names (avoids collisions)")
    parser.add_argument("--flip", action="store_true",
                        help="mosaic: force-flip vertical stacking direction")
    # tunables (kept as flags so you can A/B without editing the file)
    parser.add_argument("--tht", type=int, default=22, help="morph binarize threshold")
    parser.add_argument("--min-hold", type=int, default=5, help="slit: min frames per run")
    parser.add_argument("--cut-resp", type=float, default=0.05,
                        help="mosaic: phaseCorrelate peak below this == cut")
    parser.add_argument("--slit-dy-hybrid", choices=["0", "golge", "1"], default=None,
                        help="HIBRIT-DY kanal secimi (sartname 2026-07-09): 0=kapali "
                             "(bit-identik eski yol), golge=karar+seriler sidecar'a, "
                             "1=uygula. Env aynasi: MITAS_SLIT_DY_HYBRID")
    args = parser.parse_args()

    global SLIT_DY_HYBRID
    if args.slit_dy_hybrid is not None:
        SLIT_DY_HYBRID = args.slit_dy_hybrid

    args.out.mkdir(parents=True, exist_ok=True)
    selected = select_films(args.db_root, args.film, args.start, args.count)
    total = len([path for path in args.db_root.iterdir() if path.is_dir()])
    print(
        f"=== DB-COMPOSE [{args.mode}]: {len(selected)} film "
        f"(total {total}; range {args.start}-{args.start + args.count}) ===",
        flush=True,
    )

    def _brief(entry):
        if not entry:
            return "-"
        if "slit" in entry or "mosaic" in entry:   # --mode both -> nested
            return " ".join(
                f"{m}:{v.get('master') or v.get('skip') or v.get('err') or v.get('frames')}"
                for m, v in entry.items()
            )
        return str(entry.get("master") or entry.get("skip")
                   or entry.get("frames") or entry.get("err"))

    summary = []
    for offset, film_dir in enumerate(selected):
        t0 = time.time()
        record = process_film(film_dir, args.out, args)
        elapsed = round(time.time() - t0, 1)
        print(
            f"[{args.start + offset:3}] {film_dir.name[:46]:46} | "
            f"giris:{_brief(record.get('giris', {}))} "
            f"cikis:{_brief(record.get('cikis', {}))} "
            f"({elapsed}s)",
            flush=True,
        )
        summary.append(record)

    suffix = f"{args.mode}_{args.start}_{args.start + args.count}"
    if args.seg:
        suffix = f"{suffix}_{args.seg}"
    summary_path = args.out / f"_SUMMARY_{suffix}.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> {summary_path}", flush=True)


if __name__ == "__main__":
    main()
