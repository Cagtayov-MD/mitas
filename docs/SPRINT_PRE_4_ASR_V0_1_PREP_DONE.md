# Sprint Pre-4 — ASR v0.1 Runtime Hazırlığı DONE

## Kapsam

Bu çalışma ASR v0.1 pipeline kodlaması değildir. Amaç, sprint başlamadan runtime temelini temizlemekti: FFmpeg shared build, torchcodec decode, alignment sleeve, denoise sleeve, large-v3 lokal cache ve offline smoke.

## Oluşturulan / Güncellenen Dosyalar

- `mutfak/03_GUNCEL_DURUM.md`
- `mutfak/05_AKTIF_GOREV.md`
- `mutfak/06_KARARLAR_GUNLUGU.md`
- `scripts/alignment_subprocess.py`
- `locks/denoise.freeze.txt`
- `locks/denoise.inspect.json`
- `outputs/ffmpeg_shared_install_report.json`
- `outputs/torchcodec_smoke_asr.json`
- `outputs/torchcodec_smoke_alignment.json`
- `outputs/torchcodec_alignment_diagnosis.json`
- `outputs/alignment_diagnosis_asr_segments.json`
- `outputs/denoise_venv_install_report.json`
- `outputs/denoise_smoke_report.json`
- `outputs/alignment_whisperx_smoke.json`
- `outputs/alignment_whisperx_raw_output.json`
- `outputs/large_v3_download_report.json`
- `outputs/large_v3_offline_smoke.json`

## Validasyon

- FFmpeg: Gyan 8.1.1 full-shared PATH'e alındı; `--enable-shared` ve DLL erişimi doğrulandı.
- Torchcodec/asr: `torchcodec==0.11.1` ile 10 sn WAV decode başarılı.
- Torchcodec/alignment: direct decode FFmpeg 8 ile uyumsuz, ancak WhisperX alignment yolunda torchcodec dormant; karar günlüğüne işlendi.
- Denoise: `venvs/denoise` kuruldu; `pip check` temiz; DeepFilterNet3 synthetic 12 dB SNR smoke çıktı üretti.
- Alignment: WhisperX Türkçe alignment modeliyle 54 word segment üretildi; word boundary violation yok.
- large-v3: `models/asr/faster-whisper/large-v3` altında lokal cache oluşturuldu; offline socket guard ile transcribe smoke ağ denemesi olmadan geçti.

## Sürprizler

- `E:\MITAS` Git deposu değil; bu yüzden brief'teki commit adımları uygulanamadı.
- Python 3.11 sistemde yoktu. Yeni sistem Python kurmak yerine DeepFilterNet'in desteklediği Python 3.10 fallback'i kullanıldı.
- DeepFilterNet 0.5.6 metadata'sı torch constraint bildirmiyor; ancak runtime `df.enhance` yolunda torch/torchaudio import ediyor. `torchaudio.backend.common` gereksinimi nedeniyle `torch/torchaudio 2.8.0+cu126` seçildi.
- DeepFilterNet varsayılan model cache'i AppData'ya yazmak istedi. Model `E:\MITAS\models\denoise\DeepFilterNet3` altına lokal indirildi ve CLI `--model-base-dir` ile çalıştırıldı.
- Python 3.8+ Windows DLL arama davranışı nedeniyle PATH tek başına güvenilir değil. M16 sleeve wrapper'ları import-time `os.add_dll_directory()` kullanacak.

## Bilerek Yapılmayanlar

- ASR production pipeline kodu yazılmadı.
- `core/schemas/` ve JSON schema dosyalarına dokunulmadı.
- `asr` ve `alignment` venv paketleri değiştirilmedi.
- Mevcut test dosyaları değiştirilmedi.
- UI/backend/demo kodu açılmadı.

## Son Karar

ASR v0.1 runtime hazırlığı tamamlandı. Pipeline kodlamaya teknik zemin hazır; sprint başlangıcında hedef video ve ASR pipeline dosya yapısı kararı ayrıca netleştirilmeli.
