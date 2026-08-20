# Nash çok-alfabeli Paddle gerçek test raporu — 2026-08-18

## Karar

- Üretim varsayılanı **2 fps**.
- Nash birincil olarak `PP-OCRv6_medium_det` +
  `latin_PP-OCRv5_mobile_rec` kullanır.
- Birincil sonuç 8 temiz satırın altındaysa yalnız o filmde
  `arabic_PP-OCRv5_mobile_rec` çalışır.
- `deepseek_fallback_enabled: false`; bu testte DeepSeek yüklenmedi.

## Ortam

| Bileşen | Sürüm/ayar |
|---|---|
| Paddle | `paddlepaddle-gpu 3.3.1`, CUDA 12.6 |
| OCR | PaddleOCR 3.7.0, PaddleX 3.7.2 |
| Görüntü | OpenCV 4.10.0.84 (worker) |
| Çalışma | GPU `gpu:0`, FP32, HPI/orientation/unwarp kapalı |
| Kaynak | `/home/cagatay/Belgeler/test`, 29 MP4 |
| Örnekleme | 2 fps, toplam 7.414 PNG |

## Final toplu sonuç

| Ölçü | Sonuç |
|---|---:|
| Film | 29 |
| `OKUNDU` | 29 |
| `METIN_YOK` / `ARIZA` | 0 / 0 |
| Kabul edilmiş satır | 2.583 |
| DeepSeek çağrısı | 0 |
| Duvar süresi | 372,64 sn |
| Medyan film uçtan uca | 11,13 sn |
| P95 film uçtan uca | 26,42 sn |
| En yüksek film uçtan uca | 26,71 sn |
| Worker iç Paddle peak | 333,9 MB |
| Canlı `nvidia-smi` worker | 556–622 MiB |
| Toplu `MAXRSS` | 2.185.896 KiB |
| Sheriff rezervasyonu | 2.048 MB VRAM / 4.096 MB RAM |
| En yüksek text-run seçimi | 100 (tavan aşılmadı) |

Uçtan uca film süresi, toplu koşuda önceden yapılan birincil worker süresi ile
sonuç işleme süresinin toplamıdır; konsoldaki `sure_sn` tek başına ön-taramayı
içermez.

## Temsilci vakalar

| Film/vaka | Kare | Satır | Uçtan uca | Not |
|---|---:|---:|---:|---|
| `cag_output01` | 114 | 79 | 9,84 sn | 100-kare sınıfına en yakın gerçek örnek |
| `cag_output14` | 65 | 18 | 5,9 sn | Türkçe karakterler doğru; tek Latin geçişi |
| `cag_output26` | 239 | 280 | 26,71 sn | En yoğun kayan jenerik; postprocess 8,93 sn |
| `cag_output28` | 251 | 311 | 23,52 sn | Yoğun kayan jenerik; postprocess 7,33 sn |
| `cag_output13` | 490 | 51 | 26,12 sn | 1 Latin + 50 Arap/Fars, koşullu ikinci worker |
| `cag_output19` | 128 | 74 | 16,53 sn | 74 Arapça, koşullu ikinci worker |

`cag_output19` kanıtlı koşusunda 74/74 satır `paddle_arabic` bbox kanıtı
taşıdı; paket üreticisi `text-run-paddle-multiscript`, sürüm
`nash-paddle/v5` ve model alanında DeepSeek yoktu.

## 2 fps / 3 fps kontrollü kıyas

Aynı `cag_output26` videosu, aynı final filtre koduyla:

| FPS | Kare | Satır | Süre | Paddle peak |
|---:|---:|---:|---:|---:|
| **2** | 239 | **280** | **26,6 sn** | 222,3 MB |
| 3 | 358 | 279 | 36,9 sn | 222,3 MB |

3 fps %39 daha uzun sürdü; toplam satır artırmadı. Bulanık-normalize 0,90
eşikte 2 fps satırlarının 275/280'i 3 fps'de, 3 fps satırlarının 275/279'u
2 fps'de bulundu. 3 fps `BURAK KARAKULLUKCU`yu `MURAT...` okurken 2 fps doğru
varyantı korudu. Bu nedenle 2 fps kalite/hız varsayılanıdır.

## Kalite notu ve ertelenen kapı

Türkçe `cag_output14` elle incelendi: `ÜMİT KANTARCILAR`, `İRSEL ÇİVİT`,
`MÜZİK`, `UĞUR UZUNOK`, `BERAT ÖZDOĞAN` ve kapanış açıklaması doğru çıktı.
Yoğun kayan jenerikte yalnız tek kare görülen varyantların incelenen örnekleri
(`UILLR HAUIRUIU`, `MERI RURAMAZ` vb.) gerçek yeni kredi değil, ekran kenarı
bulanıklığıydı; yoğun-akış tek-kare filtresi bunları eledi.

Arapça/Farsça iki filmde önceki 0/1 satır 74/51 satıra çıktı ve örnekler
isim/rol biçiminde anlamlı. Ancak bu alfabeler için etiketli ground truth yok;
kesin karakter recall/precision iddiası yapılmıyor.

DeepSeek veya daha hafif ağır-model seçimi kullanıcı kararıyla ertelendi.
Bu nedenle plandaki 512/1024/2048 DeepSeek Pareto kapısı bu raporun parçası
değildir; fallback yeniden açılmadan önce ayrıca koşulmalıdır.

## Otomatik kapılar

- Nash: `152 passed, 1 skipped`
- Sheriff: `68 passed`
- Nash ve Paddle worker venv'leri: `pip check` temiz
- 29/29 `_TAMAM` üretildi
- `git diff --check`: temiz
