# Çöküş kurtarma doğrulaması — 2026-08-19

`LEBRON_FIX_DEVIR_PLANI_20260819.md` (nash/olcum) 1–4. adımlarının ölçüm
kaydı. Kod değişikliği Terra (2026-08-19 sabah); testler, izole koşular ve
bu belge aynı gün Çağatay adına ZCode oturumunda üretildi. Üretim terfisi
YAPILMADI — Sheriff kabul yatağı henüz yeni pipeline hash'iyle koşulmadı.

## 1. Yeni davranış testleri

Dört yeni dosya, 17 test; tam kule suiti **180 passed** (163 + 17):

- `tests/test_derleyici_cokme_kurtarma.py` — 120 kare sentetik çöküş →
  10×12'lik temporal chunk stack (514→2110 px ölçekte), layout haritasının
  satır-satır kaynak paritesi, parça sınırlarında 12'lik zaman adımı,
  H_MAKS aşımının `collapse_recovery` künyesiyle görünür kalması, çöküş
  yoksa normal masterın `_segment_kanvas` ile piksel-birebir olması,
  parçalamanın segment bazlı yapılması.
- `tests/test_proof_paddle.py` — tek açık eşleşmede bant-y0 ofsetli master
  bbox + layout üzerinden kaynak-kare kanıtı + COMPLETE; fold_exact;
  çift aday = `PADDLE_ESLESME_BELIRSIZ`, kanıt yok; yakın metin fuzzy
  YASAK; bozuk bbox = `PADDLE_BBOX_GECERSIZ`; görüntü-geneli
  `image[[...]]` parserdan geçmez, satır kanıtı olamaz.
- `tests/test_okuma_v2.py` — `PrivateOllama.line_grounding_supported=False`
  beyanı; `_line_grounding_supported` yalnız açık beyanla geçer; beyan
  yoksa bant başına model çağrısı BİRE düşer (`paddle_exact`,
  `grounding_unsupported` yazılır, grounding istemi asla gönderilmez);
  beyan eden backendte ikinci çağrı yapılır (`model_line_grounding`).
- `tests/test_main_kurtarma_kanit.py` — kurtarılmış master COKME arızası
  üretmez, `collapse_recovery` künyesi kanıta akar; H_MAKS aşımı yine
  görünür ARIZA(BOY_ASIMI) ve künyeyi taşır.

## 2. Beş gerçek COKME girdisinin izole yeniden koşusu

Koşu: `MITAS_OKUMA_V2=1`, çıktı `/tmp/lebron-cokme-kurtarma-20260819/`
(gece çıktılarına dokunulmadı). Girdiler Sheriff `materialized/<bolum>/frames`
(en yeni run). Kare sayıları eski COKME künyeleriyle birebir eşleşti.

| koşu | eski | yeni | satır | parça | master px | proof | kaynak-kanıtlı | çağrı/bant | VRAM tepe | Paddle kalıntı | sn |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cag_output02/giris | COKME | OKUNDU | 29 | 6 | 514→2929 | PARTIAL | 9/29 | 3/3 | 8660 MiB | 336 MiB | 72.4 |
| cag_output02/cikis | COKME | OKUNDU | 38 | 10 | 516→4859 | PARTIAL | 13/38 | 5/5 | 8660 MiB | 336 MiB | 77.7 |
| cag_output17/giris | COKME | OKUNDU | 7 | 3 | 935→2455 | NONE | 0/7 | 3/3 | 8660 MiB | 336 MiB | 71.6 |
| cag_output17/cikis | COKME | OKUNDU | 5 | 4 | 947→2909 | PARTIAL | 2/5 | 3/3 | 8660 MiB | 336 MiB | 76.6 |
| cag_output18/cikis | COKME | OKUNDU | 7 | 3 | 748→1897 | PARTIAL | 3/7 | 2/2 | 8618 MiB | 334 MiB | 83.1 |

Kapılar: model çağrısı her koşuda bant sayısına EŞİT (ikinci DeepSeek çağrısı
gerçekten kalktı) · VRAM tepe ≤ 9216 MiB kapısı · Paddle kalıntısı ≤ 512 MiB
kapısı · ısıtma ~22.6–22.9 sn (bilinen açık borç, ayrı iş).

Proof kapsamı dürüsttür: tüm master kanıtları `paddle_exact`; eşleşmeyen
satırlar `PADDLE_ESLESME_YOK`/`PADDLE_ESLESME_BELIRSIZ` olarak görünür
kalır, fuzzy bbox uydurulmaz. cag_output17/giris'te hiç açık eşleşme yok
(NONE) — kapsama sorunu kalite uzlaştırıcısı planının konusudur, bu kapının
değil.

## 3. 29-film terfi parite yatağı (normal masterlar)

`olcum/lebron_terfi_parite.py`, referans `out/master_kiyas_20260818`,
çıktı `/tmp/lebron-cokme-kurtarma-20260819/parite/`:

- **26/29 piksel-birebir + manifest özeti eşit** — normal kompozisyon yolu
  değişmedi.
- 3 film (cag_output02, cag_output17, cag_output18) piksel farkı TAHMİN
  EDİLİYORDU: bunlar çöküş filmleridir; yeni motor çöken master yerine
  kurtarılmış çok-parçalı master üretir (ör. 02: 516→4862 px). Özet farkı
  yalnız `segment` alanındadır; `durum/olcum_yolu/sinif_sayimi` eşittir.
  Başka hiçbir filmde sapma yok.

## Sonuç ve kalan iş

Devir planının 1–4. adımları kapıda. Kalan: (5) 29-video Sheriff kabul
yatağının yeni pipeline hash'iyle yeniden koşulu — ağır ve durum değiştiren
iş, Çağatay onayıyla; (6) warm-model ~23 sn görev-başı ısıtma borcu;
(7) `KALITE_UZLASTIRICI_PLANI_20260819.md` shadow/offline aşaması.
