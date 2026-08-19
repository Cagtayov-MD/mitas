# MITAS — Jenerik Başlangıç Tespiti: Tek Motor Temizliği

**Tarih:** 2026-07-29/30 · **Branch:** `jenerik-tek-motor` · **Karar:** Çağatay (tasarım Opus, uygulama Sonnet)

## Amaç

Film SONU jeneriğinin başlangıç karesini bulan üretim hattı iki motorluydu:
eski CV/paddle (`jenerik_frame_pool_detector.detect_frame_dir`) + 2026-07-23'te
birincil ilan edilen `credit_onset.tespit_v5`. Çağatay kararı: **tek motor** —
"yeni stratejimiz bu dediğim dışındaki stratejileri sil, kafa karıştırmasın".

Kod incelemesi 8 bulgu çıkardı; hepsi aynı kökten (iki motorun tek manifest'e
yazması). Kırmızı çizgi: 110-film GT ölçümü (`olc_pool.py`) — **103/110 = %93.6
genel, %96.4 üretim, kredisiz-red 29/29**. Her dalga bu kapıdan geçmek zorunda.

## İnen dalgalar

| Dalga | Commit | Ne | Kapı |
|---|---|---|---|
| 0 | `7b0a46f` | %93.6 baseline sabitlendi (commit'siz duruyordu) | 110/103 ✓ |
| 1 | `4d1798b`+`4503d15` | `tespit()`/`tespit_v4()`/`credit_vlm`/`olc_gt`/`experiments` SÖKÜLDÜ (19.698 satır); `_scroll_kurtarma` güveni 1.0→`KURTARMA_GUVEN=0.35` | 110/103 ✓, kanarya ✓ |
| 2 | `01f66b5`+`8f57090`+`fc6bac3` | CV tembelleşti (v5 kazanınca koşmaz, %70 hız); manifest v5 gerçek değerlerini taşıyor; `v5` alt-nesnesi kredi_yok kararını görünür kıldı; `--segment giris` gardı | 110/103 ✓, parite 12/12 ✓ |

**Çözülen bulgular:** ①(manifest yalanı) ②(güven şişmesi) ③(boşuna CV) ④(tespit çökmesi, silinerek) ⑧(kredi_yok kararının eziliyor olması, görünür kılındı).
**Kapsam dışı (ayrı doğruluk dalgası):** ⑤ Macarca diyakritik, ⑥ Kiril/Arapça örneklem kayması, ⑦ İtalyanca `baglam`.

**Ölçülen kalıcı gerçekler:** `Sonuc.guven` eşik için kullanılamaz (81 pozitiften 80'i 1.0).
`scroll_orani` bimodal (boşluk 0.42-0.55) → manifest `credit_type` eşiği 0.50 (karar dalı 0.30 dokunulmadı).
CV maliyeti havuz aşamasının %77'si (ölçüldü: EK TAKS 720 kare, CV 17.4s / v5 5.2s).

## Konsey kırmızı-takım turu (Dalga 2 sonrası — 2026-07-29)

**Soru:** v5 "kredi_yok" dediğinde ne olmalı? Öneri: v5 son söz, havuz boş (görünür boşluk > sessiz yanlış).
**Üyeler:** GLM, Kimi, Nemotron (MiniMax hata). Merceğe göre değil, hepsi iki merceği de oynadı.

**Birleştikleri (güçlü):**
1. Bugünkü CV-devralma net zararlı → teslimden çıkmalı.
2. `return 3` + sessiz atlama yetersiz → `review_required` QC durumu şart (alan değil, bayrak).
3. Kuru-koşu kapısı yanlışlığı ölçmüyor → kredi_yok filmlerin insan-doğrulaması (FN=0) şart.

**Ayrıştıkları (CV'nin kaderi):** Nemotron "tamamen öl" · GLM "Audit Scan olarak kalsın" · Kimi "önce gölge-koş ölç" (+istatistik eleştirisi: 29/29'un rule-of-three üst sınırı %10, "en kesin sinyal" iddiası p≈0.15 ile kurulmamış).

**Hakem kararı (Claude):** Kimi'nin istatistik eleştirisi kabul. Ama CV'nin *zarar sınıfı* (jeneriksiz filmde sahne çapası) ile *kurtarma sınıfı* (footage-üstü jenerik) aynı davranıştan doğuyor — ayırt edici tek şey çapa karesinde overlay metin var mı. O ayrımı yapan araç hattımızda zaten var: `credit_box` det-only. →

## Revize Dalga 3 — metin-kapılı karar (koşulsuz boş havuz DEĞİL)

v5 kredi_yok derse CV havuzu DOLDURMAZ. Bunun yerine `credit_box` det-only UCUZ
metin taraması (OCR değil) son %15'te metin arar:

| v5 kredi_yok + | det metin | Sonuç |
|---|---|---|
| | YOK | `status=kredi_yok`, havuz boş, VL koşmaz |
| | VAR | `review_required=true`, havuz boş, VL koşmaz, insan kuyruğu |

Uydurma cast üretmez (VL boş havuzu okumaz), gerçek cast'i sessizce kaybetmez
(çelişki → alarm). CV'nin OCR+VL yolu ölür; det metin-varlığı doğrulayıcı kalır.

**Devreye alma ön-koşulları (konsey şartı, Çağatay onayı gerekli):**
- [ ] `return 3` tüketicileri denetlendi (retry/SLA/dashboard) — rutin sonuç oldu, nadir arıza değil
- [ ] Kuru-koşu düzeltildi: üretim kuyruğundan (GT değil, döngüsellik), kredi_yok'ların %100 insan-doğrulaması, FN=0
- [ ] `review_required` bir QC durumu olarak yüzeye çıkıyor (`kunye_stages` ayrı root_cause)
- [ ] Kredi_yok oranı %45'i aşarsa DUR

**Kapsam:** OneOCR/VLM/footage-trim/backward-extend sökümü, `MITAS_JENERIK_V5=1`
kaldırma (`_V5_PAD=10` kalır), bayrak assert'leri, `BAYRAK_ENVANTERI.md` yeniden üretimi.

## ⚠️ Database olayı (2026-07-29, temizlikle ilgisiz)

İş sırasında `/opt/mitas/Database` boşaldı (300→197→0 film, 21:53). Claude yapmadı
(o penceredeki tek iş parite'ydi, hepsi env eksikliğinden import'ta öldü). İşaret
eşzamanlı "dizin sadeleştirme" oturumunun `git clean -fdx` riskine gidiyor, kesin
sebep doğrulanmadı. Restore: `/opt/yedek/mitas_db/son` (07-29 06:30, 197 film) →
rsync 124G, çıkış=0, birebir. **Kurtarılabilir:** 07-28 yedeği 300 film — aradaki
~103 film kararı Çağatay'a bırakıldı.
