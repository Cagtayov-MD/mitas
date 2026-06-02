# MITAS Requirements Denetimi ve Kurulum Sırası v1

## 1. Amaç

Bu doküman, Sprint 4.4'te oluşturulan requirements taslaklarını denetlemek, paketleri risk/ağırlık sınıfına ayırmak ve ileride yapılacak kontrollü kurulumlar için güvenli sıra önermek amacıyla hazırlanmıştır.

Bu çalışma kurulum değildir. Bu çalışmada `pip install` çalıştırılmamış, model indirilmemiş, benchmark yapılmamış ve hiçbir aday production ana motor olarak seçilmemiştir.

## 2. İncelenen requirements dosyaları

- `requirements/ocr.txt`
- `requirements/asr.txt`
- `requirements/face.txt`
- `requirements/visual.txt`
- `requirements/audio.txt`
- `requirements/tag.txt`
- `requirements/stt.txt` (legacy referans; primary runtime değil)
- `model_manifest.yaml`

## 3. Paket sınıfları

### lightweight

Kurulumu görece düşük riskli, küçük veya yaygın yardımcı paketlerdir.

- `numpy`
- `pillow`
- `soundfile`
- `pydub`
- `pydantic`
- `rapidfuzz`
- `regex`
- `pyyaml`
- `websockets`

### medium

Binary wheel, daha büyük bağımlılık ağacı veya modül etkisi nedeniyle ayrı kontrol edilmesi gereken paketlerdir.

- `opencv-python`
- `librosa`
- `faster-whisper`
- `silero-vad`
- `insightface`
- `transformers`

### heavy_gpu

CUDA, GPU provider, büyük framework veya sürüm uyumluluğu nedeniyle ayrı onay ve ortam kontrolü gerektiren paketlerdir.

- `torch`
- `torchaudio`
- `onnxruntime-gpu`
- `tensorflow`
- `ultralytics` / YOLO-World adayı
- PaddleOCR GPU/CPU seçimi
- WhisperX bağımlılık zinciri

### external_binary

Pip paketi gibi ele alınmaması gereken, PATH veya ayrı installer ile yönetilecek araçlardır.

- `tesseract`
- `fpcalc` / Chromaprint

### placeholder

Bu sprintte bilinçli olarak kesin paket/sürüm haline getirilmemiş, benchmark veya smoke test sonrası netleşecek maddelerdir.

- OneOCR runtime durumu
- PaddleOCR sürüm ve CPU/GPU seçimi
- pytesseract / Tesseract binary bağlantısı
- WhisperX alignment kararı
- torch wheel kararı
- torchaudio wheel kararı
- onnxruntime-gpu provider kararı
- ByteTrack paket stratejisi
- YOLO-World / ultralytics stratejisi
- YAMNet runtime kararı
- tensorflow CPU/GPU kararı
- chromaprint/fpcalc binary kurulumu
- zeyrek / Türkçe morfoloji adayı
- fastapi servis ihtiyacı
- uvicorn servis ihtiyacı

## 4. Venv bazlı paket özeti

### ocr

- Lightweight: `pillow`, `numpy`
- Medium: `opencv-python`
- Placeholder: OneOCR, PaddleOCR, pytesseract
- External binary riski: Tesseract

### asr

- Lightweight/servis: `soundfile`, `numpy`, `fastapi`, `uvicorn`, `websockets`
- Medium: `faster-whisper`, `silero-vad`, `librosa`
- Runtime/servis desteği: `onnxruntime`
- Heavy GPU / uyumluluk: `torch`, `torchaudio`
- Placeholder: WhisperX alignment, torch wheel, torchaudio wheel

### face

- Lightweight: `numpy`, `pillow`
- Medium: `insightface`, `opencv-python`
- Heavy GPU / uyumluluk: `onnxruntime-gpu`
- Placeholder: onnxruntime-gpu provider kararı, ByteTrack paket stratejisi

### visual

- Lightweight: `pillow`, `numpy`
- Medium: `transformers`, `opencv-python`
- Heavy GPU / uyumluluk: `torch`, YOLO-World / ultralytics
- Placeholder: YOLO-World paketi ve model stratejisi, torch wheel

### audio

- Lightweight: `soundfile`, `pydub`, `numpy`
- Medium: `librosa`
- Heavy GPU / uyumluluk: `tensorflow`
- Placeholder: YAMNet, tensorflow CPU/GPU seçimi
- External binary riski: `fpcalc` / Chromaprint

### tag

- Lightweight: `pydantic`, `rapidfuzz`, `regex`, `pyyaml`
- Placeholder: zeyrek veya başka Türkçe morfoloji adayı

### legacy stt

- `legacy_stt_venv`
- `deprecated_as_primary_runtime`
- `do_not_delete_yet`
- Canlı transkript artık `ASR > streaming_transcription` altında değerlendirilir.

## 5. Placeholder kalan maddeler

- OneOCR yerel runtime/import doğrulaması
- PaddleOCR kesin sürüm ve CPU/GPU kararı
- pytesseract ile Tesseract binary ilişkisinin netleşmesi
- WhisperX alignment kullanımı ve bağımlılık etkisi
- torch CUDA/CPU wheel seçimi
- torchaudio ile torch sürüm kilidi
- onnxruntime-gpu CUDAExecutionProvider uyumluluğu
- ByteTrack için `supervision` veya ayrı paket seçimi
- YOLO-World için paket/model stratejisi
- YAMNet için TensorFlow/model dağıtım kararı
- tensorflow Windows ve GPU uyumluluğu
- chromaprint/fpcalc binary kurulumu
- zeyrek veya alternatif Türkçe morfoloji paketi
- fastapi/uvicorn servis ihtiyacının netleşmesi

## 6. Harici binary gerektirenler

- `tesseract`: OCR fallback için sistem binary olarak kurulmalı ve PATH erişimi ayrıca doğrulanmalıdır.
- `fpcalc` / Chromaprint: Song recognition fingerprint çıkarımı için sistem binary olarak kurulmalı ve PATH erişimi ayrıca doğrulanmalıdır.

Bu araçlar pip dependency gibi kurulmayacaktır. Her biri ayrı onay ve ayrı PATH doğrulaması gerektirir.

## 7. Kurulum sırası önerisi

A. Lightweight paketler  
Önce yardımcı paketler kurulmalı: `numpy`, `pillow`, `soundfile`, `pydub`, `pydantic`, `rapidfuzz`, `regex`, `pyyaml`, `websockets`.

B. OCR lightweight  
`ocr` venv içinde önce `numpy`, `pillow`, ardından `opencv-python` denenmeli. OCR motor adayları ayrı onayla kurulmalıdır.

C. ASR lightweight/servis  
`asr` venv içinde `numpy`, `soundfile`, `librosa`, `fastapi`, `uvicorn`, `websockets` ve `onnxruntime` doğrulanmalıdır. Sonra `faster-whisper` ve `silero-vad` ayrı smoke test ile denenmelidir.

D. Audio lightweight  
`audio` venv içinde `numpy`, `soundfile`, `pydub`, `librosa` kurulmalı. TensorFlow/YAMNet daha sonra ayrı onaya bırakılmalıdır.

E. Face lightweight  
`face` venv içinde `numpy`, `pillow`, `opencv-python` kurulmalı. `insightface`, `onnxruntime-gpu` ve tracker seçimi ayrı adım olmalıdır.

F. Visual lightweight  
`visual` veya `tag` venv içinde `numpy`, `pillow`, `opencv-python`, `transformers` kontrollü denenmeli. `torch` ve YOLO-World/ultralytics ayrı onayla kurulmalıdır.

G. Heavy GPU paketleri ayrı onayla  
`torch`, `torchaudio`, `onnxruntime-gpu`, `tensorflow`, PaddleOCR GPU varyantı, WhisperX ve YOLO-World/ultralytics ayrı karar ve onay gerektirir.

H. Harici binary araçları ayrı kur  
Tesseract ve fpcalc/Chromaprint pip akışından ayrı ele alınmalı, PATH doğrulaması yapılmalı ve smoke test raporuna ayrıca yazılmalıdır.

## 8. Riskler

- CUDA/torch uyumsuzluğu: Torch wheel seçimi Python, CUDA ve ekran kartı durumuna göre yapılmalıdır.
- onnxruntime-gpu çakışması: CUDAExecutionProvider uyumluluğu ve torch/onnxruntime DLL çakışmaları kontrol edilmelidir.
- tensorflow ağırlığı: Kurulum boyutu, Windows uyumluluğu ve GPU desteği ayrı değerlendirilmelidir.
- whisperx bağımlılıkları: PyTorch, torchaudio, diarization ve alignment bağımlılıkları ASR ortamını ağırlaştırabilir.
- paddleocr bağımlılıkları: PaddlePaddle CPU/GPU wheel seçimi ve Windows uyumluluğu ayrı kontrol gerektirir.
- Windows binary/path sorunları: Tesseract ve fpcalc kurulumları PATH, dosya izinleri ve binary sürümü nedeniyle ayrı doğrulanmalıdır.

## 9. Kurulum yapılmadan önce onay gerektiren paketler

- `torch`
- `torchaudio`
- `onnxruntime-gpu`
- `tensorflow`
- `paddleocr` / PaddlePaddle varyantları
- `whisperx`
- `ultralytics` / YOLO-World adayı
- `insightface`
- ByteTrack için seçilecek paket
- OneOCR runtime paketi veya kurum içi bileşeni
- Tesseract harici binary
- fpcalc / Chromaprint harici binary

## 10. Son karar

Sprint 4.5 kapsamında requirements taslakları denetlenmiş ve kontrollü kurulum sırası çıkarılmıştır.

Kurulum yapılmamıştır. Model indirilmemiştir. Benchmark çalıştırılmamıştır. `selected_as_engine` alanı değiştirilmemiştir.

Önerilen sonraki adım, kullanıcı onayıyla önce lightweight paketlerin venv bazlı küçük partiler halinde kurulması ve her parti sonrasında smoke/import raporu alınmasıdır.
