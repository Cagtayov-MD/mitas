"""
ASR Emergency Transcribe — MITAS
Hedef: faster-whisper ile gerçek transcript çıktısı almak.
"""

import json
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path("E:/MITAS")
OUTPUTS = ROOT / "outputs"
OUTPUTS.mkdir(exist_ok=True)

SEARCH_DIRS = [
    ROOT / "test_assets",
    ROOT / "inputs",
    ROOT / "samples",
    ROOT,
]
AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".mp4", ".mov"}

SCIPY_FALLBACK = Path(
    "E:/MITAS/venvs/asr/Lib/site-packages/scipy/io/tests/data"
    "/test-44100Hz-le-1ch-4bytes.wav"
)

OUT_TXT  = OUTPUTS / "asr_emergency_transcript.txt"
OUT_JSON = OUTPUTS / "asr_emergency_transcript.json"
OUT_RPT  = OUTPUTS / "asr_emergency_report.json"

NO_INPUT = OUTPUTS / "ASR_NO_INPUT_FOUND.txt"

MAX_SECONDS = 60

# ---------------------------------------------------------------------------
def find_audio():
    for d in SEARCH_DIRS:
        if not d.exists():
            continue
        for f in d.iterdir():
            if f.is_file() and f.suffix.lower() in AUDIO_EXTS:
                return f
    return None


def write_report(data: dict):
    OUT_RPT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    report = {
        "input_file": None,
        "model_id": None,
        "device": None,
        "compute_type": None,
        "duration_processed_seconds": None,
        "detected_language": None,
        "language_probability": None,
        "runtime_seconds": None,
        "transcript_preview": None,
        "output_txt": str(OUT_TXT),
        "output_json": str(OUT_JSON),
        "status": "pending",
        "error_message": None,
    }

    # --- 1. Find input file --------------------------------------------------
    audio_file = find_audio()

    if audio_file is None:
        if SCIPY_FALLBACK.exists():
            audio_file = SCIPY_FALLBACK
            print(f"[ASR] Proje dizininde ses dosyası yok. Scipy fallback: {audio_file}")
        else:
            NO_INPUT.write_text(
                "Test edilecek ses/video dosyası bulunamadı.", encoding="utf-8"
            )
            report["status"] = "no_input"
            report["error_message"] = "No audio/video file found and scipy fallback missing."
            write_report(report)
            print("[ASR] Ses dosyası bulunamadı. ASR_NO_INPUT_FOUND.txt yazıldı.")
            sys.exit(0)

    report["input_file"] = str(audio_file)
    print(f"[ASR] Giriş dosyası: {audio_file}")

    # --- 2. Load faster-whisper ----------------------------------------------
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        report["status"] = "error"
        report["error_message"] = f"faster_whisper import failed: {e}"
        write_report(report)
        print(f"[ASR] HATA: {e}")
        sys.exit(1)

    # --- 3. Try model + compute_type combos ----------------------------------
    model_attempts = [
        ("Systran/faster-whisper-small", "float16"),
        ("Systran/faster-whisper-small", "int8_float16"),
        ("Systran/faster-whisper-small", "int8"),
        ("Systran/faster-whisper-tiny",  "float16"),
        ("Systran/faster-whisper-tiny",  "int8_float16"),
        ("Systran/faster-whisper-tiny",  "int8"),
    ]

    model = None
    chosen_model_id = None
    chosen_compute = None

    for model_id, compute_type in model_attempts:
        try:
            print(f"[ASR] Deneniyor: {model_id}  compute_type={compute_type} ...")
            model = WhisperModel(model_id, device="cuda", compute_type=compute_type)
            chosen_model_id = model_id
            chosen_compute = compute_type
            print(f"[ASR] Model yüklendi: {model_id}  compute_type={compute_type}")
            break
        except Exception as e:
            print(f"[ASR] Başarısız ({model_id} / {compute_type}): {e}")

    if model is None:
        report["status"] = "error"
        report["error_message"] = "Hiçbir model yüklenemedi."
        write_report(report)
        print("[ASR] HATA: Hiçbir model + compute_type kombinasyonu çalışmadı.")
        sys.exit(1)

    report["model_id"] = chosen_model_id
    report["device"] = "cuda"
    report["compute_type"] = chosen_compute

    # --- 4. Transcribe (max 60s) ---------------------------------------------
    try:
        t0 = time.time()
        segments, info = model.transcribe(
            str(audio_file),
            beam_size=5,
            condition_on_previous_text=False,
        )

        segments_list = []
        full_text_parts = []
        duration_processed = 0.0

        for seg in segments:
            if seg.start >= MAX_SECONDS:
                break
            end = min(seg.end, MAX_SECONDS)
            segments_list.append({
                "start": round(seg.start, 3),
                "end": round(end, 3),
                "text": seg.text.strip(),
            })
            full_text_parts.append(seg.text.strip())
            duration_processed = end

        runtime = round(time.time() - t0, 2)
        full_text = " ".join(full_text_parts).strip()

        report["duration_processed_seconds"] = round(duration_processed, 2)
        report["detected_language"] = info.language
        report["language_probability"] = round(info.language_probability, 4)
        report["runtime_seconds"] = runtime
        report["transcript_preview"] = full_text[:200]
        report["status"] = "success"

        print(f"[ASR] Dil: {info.language} ({info.language_probability:.2%})")
        print(f"[ASR] Süre: {runtime}s  |  İşlenen: {duration_processed:.1f}s")
        print(f"[ASR] Transcript: {full_text[:120]!r}")

    except Exception as e:
        report["status"] = "error"
        report["error_message"] = str(e)
        write_report(report)
        print(f"[ASR] Transcribe hatası: {e}")
        sys.exit(1)

    # --- 5. Write outputs ----------------------------------------------------
    OUT_TXT.write_text(full_text, encoding="utf-8")

    transcript_json = {
        "input_file": str(audio_file),
        "model_id": chosen_model_id,
        "detected_language": info.language,
        "language_probability": round(info.language_probability, 4),
        "segments": segments_list,
        "full_text": full_text,
    }
    OUT_JSON.write_text(json.dumps(transcript_json, ensure_ascii=False, indent=2), encoding="utf-8")

    write_report(report)

    print(f"\n[ASR] Çıktılar:")
    print(f"  TXT : {OUT_TXT}")
    print(f"  JSON: {OUT_JSON}")
    print(f"  RPT : {OUT_RPT}")
    print("[ASR] TAMAMLANDI.")


if __name__ == "__main__":
    main()
