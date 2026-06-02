# PaddleOCR GPU Kontrol Raporu

Tarih: 2026-05-22 14:24 Europe/Istanbul

## Sonuç

PaddleOCR GPU'ya geçmiş durumda.

```text
paddle_version=3.3.1
cuda_compiled=True
device=gpu:0
cuda_device_count=1
```

Kurulu paket:

```text
paddlepaddle-gpu 3.3.1
paddleocr 3.5.0
```

GPU:

```text
NVIDIA GeForce RTX 3090
Driver Version: 560.94
CUDA Version: 12.6
VRAM: 24576 MiB
```

## PaddleOCR Healthcheck

Komut:

```powershell
E:\MITAS\venvs\ocr\Scripts\python.exe -m scripts.ocr_model_healthcheck --output-dir E:\MITAS\outputs\ocr_model_healthcheck\paddle_gpu_check_20260522 --engines paddle
```

Sonuç:

| Motor | Device | Durum | Kayıt | Ortalama Güven | Çıktı |
| --- | --- | --- | ---: | ---: | --- |
| PaddleOCR | `gpu:0` | OK | 4 | 0.995 | `ÇAĞATAY İŞLER`, `MICHAEL DANTE`, `GÖRÜNTÜ YÖNETMENİ`, `DIGITAL INTERMEDIATE BY EFILM` |

Rapor:

- `E:\MITAS\outputs\ocr_model_healthcheck\paddle_gpu_check_20260522\ocr_model_healthcheck.md`
- `E:\MITAS\outputs\ocr_model_healthcheck\paddle_gpu_check_20260522\ocr_model_healthcheck.json`

## Kontrol Notları

- `pip check`: `No broken requirements found.`
- Paddle runtime logunda cuDNN 8.9 uyarısı yazdı, ama sağlık testi geçti.
- `pip` hâlâ eski kırık kurulumdan kalan `~addlepaddle-3.3.1.dist-info` için `Ignoring invalid distribution -addlepaddle` uyarısı veriyor. Bu çalışma hatası üretmedi, ama venv temizliği için ayrıca silinebilir.
