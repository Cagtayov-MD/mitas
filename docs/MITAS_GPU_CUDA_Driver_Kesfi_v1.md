# MITAS GPU / CUDA / Driver Keşfi v1

## Amaç

Sprint 4.9 kapsamında ağır AI/GPU paketleri kurulmadan önce sistemdeki NVIDIA GPU, driver, CUDA görünürlüğü ve VRAM durumu raporlanmıştır.

Bu görev kurulum değildir. Benchmark değildir. Model seçimi değildir.

## Kapsam

Kontrol script'i:

- `scripts/inspect_gpu_cuda.py`

Üretilen rapor:

- `outputs/gpu_cuda_inventory_report.json`

## Kontrol Edilenler

- `nvidia-smi` PATH içinde var mı
- GPU adı
- driver version
- VRAM total / used / free
- `nvidia-smi` genel çıktısından okunabilirse CUDA Version
- Birden fazla GPU varsa tüm GPU listesi
- Manifest içinde `selected_as_engine` sayısı

## Bilerek Yapılmayanlar

- `torch` import edilmedi veya kurulmadı.
- `torchaudio` kurulmadı.
- `tensorflow` kurulmadı.
- `onnxruntime-gpu` kurulmadı.
- `whisperx` kurulmadı.
- `faster-whisper` kurulmadı.
- `paddleocr` kurulmadı.
- `easyocr` kurulmadı.
- `insightface` kurulmadı.
- `ultralytics` kurulmadı.
- `transformers` kurulmadı.
- Model indirilmedi.
- Benchmark çalıştırılmadı.
- Video/ses/görüntü analizi yapılmadı.
- UI yazılmadı.
- `selected_as_engine` değiştirilmedi.

## Readiness Yorumu

`heavy_install_ready` alanı kesin kurulum kararı değildir.

Kurallar:

- `nvidia_smi_found: false` ise `heavy_install_ready: false`
- `gpu_count: 0` ise `heavy_install_ready: false`
- GPU varsa ama CUDA Version okunamıyorsa `heavy_install_ready: needs_review`
- GPU ve CUDA Version okunuyorsa sonuç yine kurulum kararı değil, inceleme sinyalidir.

## Son Karar

Bu sprint yalnızca GPU/driver/CUDA görünürlüğünü keşfeder.

PyTorch, ONNX Runtime GPU, TensorFlow veya başka ağır paketlerin kurulup kurulmayacağı bu sprintte kararlaştırılmaz.
