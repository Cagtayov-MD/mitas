# Jordan kulesi — canlı durum

> **Bu dosya bağlam sigortasıdır.** Oturum kesilirse yeni oturum BURADAN devam
> eder. Kimlik kartı için `README.md`, tarihçe için `CHANGELOG.md`.

**Son güncelleme:** 2026-08-13 — **KULE AYAKTA.** Sözleşme, iki geçiş, iki
checkpoint, CLI ve testler hazır; uçtan uca gerçek koşu yapıldı.

---

## Değişmez kurallar (her oturumda geçerli)

- **`git add -A`, `git add .`, `git reset --hard`, `git stash` YASAK.** Ağaçta
  bu işe ait olmayan onlarca değişik/silinmiş dosya var. Yalnız adı geçen
  yolları sahnele.
- **`model/` git'e girmez** (`Allstar/.gitignore: */model/`). 33 GB.
- **`model/bf16` SİLİNMEZ.** INT8'in ne kaybettirdiği ölçülene kadar kıyasın
  kontrol koludur.
- **`gereksinimler.txt`'ten paket çıkarma.** Kobe dersi: çıktı, kodun hiç
  import etmediği paketlere bağlı olabilir.
- Üretim durmuş — hiçbir toplu koşu başlatma.

## Kurulum durumu

| Parça | Durum |
|---|---|
| `venv/` (torch 2.11.0+cu130, transformers 5.14.1, compressed-tensors 0.17.0, torchcodec 0.16.0) | 5.0 GB, kurulu |
| `model/w8a8` — INT8, VARSAYILAN | 14 GB, kurulu |
| `model/bf16` — orijinal, kontrol kolu | 19 GB, kurulu |
| Testler | **52/52**, GPU gerektirmez |
| Uçtan uca | KUKLA ADAM 30 sn → `OKUNDU`, 23.3 sn |

## Bilinen açık kalemler

**① Hız — hızlı yol kapalı.** Yükleme uyarısı:
*"The fast path is not available… fla-org/flash-linear-attention,
Dao-AILab/causal-conv1d"*. Qwen3.5'in Gated DeltaNet katmanları saf torch
uygulamasına düşüyor. Doğruluğu etkilemez, **hızı etkiler**. İki paket kurulup
ölçülmeli — ama önce doğruluk taban çizgisi alınmalı, sonra hız.

**② INT8 vs bf16 ölçülmedi.** `model/w8a8` varsayılan; hangisinin daha iyi
okuduğu bilinmiyor. Beklenen ayrışma noktası **garble** (özel isimde karakter
bozulması): daha çok kare garble'ı düşürür, INT8 yükseltebilir — ikisi de aynı
metriğe iner, tek ölçüm çözer.

**③ Ölçüm yatağı henüz kule içinde değil.** Hazır malzeme:
`candidate_runs/vllm_bench_20260718/claude_gt/` — 24 film × 3482 satır
insan-okuması GT (190 giriş + 123 çıkış dilimi), puanlayıcı `grade_claude.py`
(recall_full / recall_core / uydurma / garble / kapsam-dışı). Önceki nesil
referansı: Qwen3-VL-8B → recall_full 0.769, recall_core 0.854, uydurma %2.1.
**Eksik:** o 24 filmin kaynak mp4'leri (`/home/cagatay/test_film/` boşalmış,
`/mnt/trt_depo`'dan tazelenmeli).

**④ Eşikleri Çağatay koyacak.** Kule sözleşme + mekanizma olarak teslim edildi;
kırmızı çizgi ve bağlantı kararı onun.

## Kule sınırı notu

`Allstar/MAP.md` "model ağırlıkları zemindedir" der. Jordan bunu **bilerek**
esnetiyor: o kural PAYLAŞILAN kaynağın çatallanmaması içindir (`core/lexicon`
örneği); bu iki checkpoint'i başka kule kullanmıyor, çatallanacak bir şey yok.
Buna karşılık Kobe'nin sürüm-dondurma gerekçesi (`KATALOG §2②`) tam tersini
söylüyor: ortak `hf_cache`'te biri modeli güncellerse Jordan'ın çıktısı
sessizce kayar.

## Sandbox

`scratch/model_sandbox/` **kapatıldı** (2026-08-13). Qwen3.5-9B bf16 ağırlıkları
oradan Jordan'a taşındı. Sandbox'ın kalan içeriği (deney script'leri, 39-film
OOM sonuçları, showdown çıktıları) **silinmedi** — Jordan'ın parça/keskinleştirme
ayarlarının kanıt kaynağı orası.
