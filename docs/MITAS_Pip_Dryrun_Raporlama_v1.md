# MITAS Pip Dry-Run Raporlama v1

## Amaç

Bu doküman, Sprint 4.6 kapsamında requirements taslaklarının gerçek kurulum yapılmadan `pip install --dry-run --report` ile nasıl çözümleneceğini açıklar.

Bu görev kurulum değildir. Normal `pip install` çalıştırılmaz. Paketler venv içine kurulmaz. Model indirilmez. Benchmark yapılmaz. `selected_as_engine` alanı değiştirilmez.

## Kapsam

İncelenen requirements dosyaları:

- `requirements/ocr.txt`
- `requirements/asr.txt`
- `requirements/face.txt`
- `requirements/visual.txt`
- `requirements/audio.txt`
- `requirements/tag.txt`

Legacy referans:

- `requirements/stt.txt` (`legacy_stt_venv`, primary runtime değil)

Her dosya kendi venv Python'ı ile çözümlenecek şekilde planlanmıştır:

- `venvs/ocr/Scripts/python.exe`
- `venvs/asr/Scripts/python.exe`
- `venvs/face/Scripts/python.exe`
- `venvs/visual/Scripts/python.exe`
- `venvs/audio/Scripts/python.exe`
- `venvs/tag/Scripts/python.exe`

`venvs/stt/Scripts/python.exe` legacy olarak korunur, yeni dry-run planında primary runtime sayılmaz.

## Runner

Script:

`scripts/run_pip_dryrun_reports.py`

Varsayılan mod `pip_dryrun_plan_only` modudur. Bu modda hiçbir pip komutu çalıştırılmaz; komutlar hazırlanır, requirements satırları analiz edilir ve rapor üretilir.

Gerçek pip dry-run çözümlemesi için kullanılacak mod:

```powershell
E:\MITAS\venvs\core\Scripts\python.exe E:\MITAS\scripts\run_pip_dryrun_reports.py --execute-pip-dryrun --timeout 120
```

Bu komut normal kurulum yapmaz; sadece pip'in `--dry-run --ignore-installed --report` modunu kullanır. Yine de paket index erişimi, metadata çözümleme ve pip cache yazımı yapabileceği için ayrı onayla çalıştırılmalıdır.

## Cache ve Geçici Dosya Kararı

Runner gerçek pip dry-run modunda geçici ve cache yollarını `E:\MITAS` altında tutacak şekilde ayarlar:

- `PIP_CACHE_DIR=E:\MITAS\cache\pip`
- `TMP=E:\MITAS\tmp\pip_dryrun`
- `TEMP=E:\MITAS\tmp\pip_dryrun`

Kalıcı sistem environment değişikliği yapılmaz.

## Placeholder Kontrolü

Requirements dosyalarındaki yorum satırları pip tarafından yok sayılır.

Runner, yorum olmayan satırlarda `placeholder` veya `TBD` ifadesi görürse bunu hata kabul eder. Böylece yanlışlıkla placeholder metninin paket adı gibi çözülmesi engellenir.

## Çıktılar

Özet rapor:

- `outputs/pip_dryrun_summary_report.json`

Gerçek pip dry-run modunda üretilecek pip report dosyaları:

- `outputs/pip_dryrun_ocr.json`
- `outputs/pip_dryrun_asr.json`
- `outputs/pip_dryrun_face.json`
- `outputs/pip_dryrun_visual.json`
- `outputs/pip_dryrun_audio.json`
- `outputs/pip_dryrun_tag.json`
- `outputs/pip_dryrun_stt.json` legacy kayıt olarak kalabilir.

## Risk Notları

- `faster-whisper`, `insightface`, `transformers`, `opencv-python` ve `librosa` çözümleme sırasında büyük wheel metadata ve transitive dependency etkisi yaratabilir.
- `torch`, `torchaudio`, `onnxruntime-gpu`, `tensorflow`, PaddleOCR, WhisperX ve YOLO-World bu sprintte placeholder veya ağır paket riski olarak tutulmuştur.
- Tesseract ve fpcalc/Chromaprint pip paketi değildir; harici binary olarak ayrı kurulmalıdır.

## Son Karar

Sprint 4.6 için güvenli pip dry-run runner altyapısı hazırlanmıştır. Kurulum yapılmadan çözümleme raporu alınabilir. Gerçek dry-run çalıştırması, paket index/cache erişimi nedeniyle ayrı onayla yapılmalıdır.
