"""
ASR + Pyannote diarization pipeline.
Kaynak: E:\MITAS içinde ses/video arar, yoksa scipy fallback kullanır.
Çıktılar: outputs/ klasörüne yazılır.
"""

import json
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

OUTPUTS = Path("E:/MITAS/outputs")
OUTPUTS.mkdir(parents=True, exist_ok=True)

AUDIO_EXTS = {".wav", ".mp3", ".mp4", ".m4a", ".mov", ".flac", ".ogg",
              ".mkv", ".avi", ".aac", ".opus", ".webm"}

SCIPY_FALLBACK = Path(
    "E:/MITAS/venvs/asr/Lib/site-packages/scipy/io/tests/data"
    "/test-44100Hz-le-1ch-4bytes.wav"
)

SEARCH_ROOTS = [
    Path("E:/MITAS/test_assets"),
    Path("E:/MITAS/inputs"),
    Path("E:/MITAS/samples"),
    Path("E:/MITAS"),
]

HF_TOKEN = "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"


def find_audio():
    for root in SEARCH_ROOTS:
        if not root.exists():
            continue
        for p in root.iterdir():
            if p.suffix.lower() in AUDIO_EXTS and "venvs" not in str(p):
                return p
    return SCIPY_FALLBACK


def load_waveform_dict(audio_path):
    """soundfile ile yükle, pyannote için dict döndür."""
    import soundfile as sf
    import torch
    data, sr = sf.read(str(audio_path), dtype="float32", always_2d=True)
    waveform = torch.from_numpy(data.T)  # (channels, samples)
    return {"waveform": waveform, "sample_rate": sr}, sr


# ─── 1. Ses dosyası ─────────────────────────────────────────────────────────

audio_path = find_audio()
source_type = "scipy_fallback" if "scipy" in str(audio_path) else "project_file"
print(f"[audio] {audio_path}  ({source_type})")


# ─── 2. ASR — faster-whisper ─────────────────────────────────────────────────

from faster_whisper import WhisperModel

MODEL_ATTEMPTS = [
    ("Systran/faster-whisper-small", "float16"),
    ("Systran/faster-whisper-small", "int8_float16"),
    ("Systran/faster-whisper-small", "int8"),
    ("Systran/faster-whisper-tiny",  "float16"),
    ("Systran/faster-whisper-tiny",  "int8"),
]

asr_model = None
asr_model_id = None
asr_compute = None

for model_id, compute in MODEL_ATTEMPTS:
    try:
        print(f"[asr] Yükleniyor: {model_id} ({compute}) ...")
        asr_model = WhisperModel(model_id, device="cuda", compute_type=compute)
        asr_model_id = model_id
        asr_compute = compute
        print(f"[asr] Model hazır: {model_id} / {compute}")
        break
    except Exception as e:
        print(f"[asr] {model_id}/{compute} başarısız: {e}")

if asr_model is None:
    raise RuntimeError("Hiçbir ASR modeli yüklenemedi.")

t0 = time.time()
segments_raw, info = asr_model.transcribe(
    str(audio_path),
    language=None,
    beam_size=5,
    word_timestamps=True,
    condition_on_previous_text=False,
)

segments = []
full_text_parts = []
for seg in segments_raw:
    if seg.start > 60.0:
        break
    entry = {
        "start": round(seg.start, 3),
        "end":   round(seg.end, 3),
        "text":  seg.text.strip(),
        "words": [
            {"word": w.word, "start": round(w.start, 3), "end": round(w.end, 3),
             "probability": round(w.probability, 4)}
            for w in (seg.words or [])
        ],
    }
    segments.append(entry)
    full_text_parts.append(seg.text.strip())

asr_runtime = round(time.time() - t0, 3)
full_text = " ".join(full_text_parts).strip()

print(f"[asr] Tamamlandı — {len(segments)} segment, {asr_runtime}s")
print(f"[asr] Dil: {info.language} ({info.language_probability:.1%})")
print(f"[asr] Metin: {full_text[:120]!r}")

# Çıktılar
(OUTPUTS / "asr_emergency_transcript.txt").write_text(full_text, encoding="utf-8")

transcript_json = {
    "model":        asr_model_id,
    "compute_type": asr_compute,
    "device":       "cuda",
    "language":     info.language,
    "language_prob": round(info.language_probability, 4),
    "audio_file":   str(audio_path),
    "source_type":  source_type,
    "segments":     segments,
}
(OUTPUTS / "asr_emergency_transcript.json").write_text(
    json.dumps(transcript_json, ensure_ascii=False, indent=2), encoding="utf-8"
)

asr_report = {
    "status":           "success",
    "model":            asr_model_id,
    "compute_type":     asr_compute,
    "device":           "cuda",
    "language":         info.language,
    "language_prob":    round(info.language_probability, 4),
    "audio_file":       str(audio_path),
    "source_type":      source_type,
    "segment_count":    len(segments),
    "runtime_seconds":  asr_runtime,
    "transcript_preview": full_text[:200],
}
(OUTPUTS / "asr_emergency_report.json").write_text(
    json.dumps(asr_report, ensure_ascii=False, indent=2), encoding="utf-8"
)

print("[asr] Çıktılar yazıldı.")


# ─── 3. Pyannote diarization smoke ──────────────────────────────────────────

from pyannote.audio import Pipeline
import torch

print("\n[diar] Pipeline yükleniyor ...")
t1 = time.time()

from pyannote.audio.pipelines import speaker_diarization as _sd
_sd.get_plda = lambda *args, **kwargs: None

SNAPSHOT = (
    r"C:\Users\TRT03\.cache\huggingface\hub"
    r"\models--pyannote--speaker-diarization-3.1"
    r"\snapshots\84fd25912480287da0247647c3d2b4853cb3ee5d"
)
pipeline = Pipeline.from_pretrained(SNAPSHOT, token=HF_TOKEN)
pipeline = pipeline.to(torch.device("cuda"))
print("[diar] Pipeline hazır")

# Torchaudio ile yükle (FFmpeg yok → waveform dict)
waveform_dict, sample_rate = load_waveform_dict(audio_path)
print(f"[diar] Waveform: shape={waveform_dict['waveform'].shape}, sr={sample_rate}")

diarization = pipeline(waveform_dict)
diar_runtime = round(time.time() - t1, 3)

print(f"[diar] Output type: {type(diarization)}")
# pyannote 4.x: DiarizeOutput.speaker_diarization is the Annotation
annotation = (
    diarization.speaker_diarization
    if hasattr(diarization, "speaker_diarization")
    else diarization
)

# serialize() da kullanılabilir ama RTTM için kendin üret
serialized = diarization.serialize() if hasattr(diarization, "serialize") else {}

# RTTM
rttm_lines = []
speaker_segments = []
for turn, _, speaker in annotation.itertracks(yield_label=True):
    rttm_line = (
        f"SPEAKER {audio_path.stem} 1 "
        f"{turn.start:.3f} {turn.duration:.3f} "
        f"<NA> <NA> {speaker} <NA> <NA>"
    )
    rttm_lines.append(rttm_line)
    speaker_segments.append({
        "start":    round(turn.start, 3),
        "end":      round(turn.end, 3),
        "duration": round(turn.duration, 3),
        "speaker":  speaker,
    })

rttm_text = "\n".join(rttm_lines)
(OUTPUTS / "pyannote_smoke.rttm").write_text(rttm_text, encoding="utf-8")

speakers_found = sorted({s["speaker"] for s in speaker_segments})

(OUTPUTS / "pyannote_smoke.json").write_text(
    json.dumps({
        "audio_file":      str(audio_path),
        "source_type":     source_type,
        "num_speakers":    len(speakers_found),
        "speakers":        speakers_found,
        "segments":        speaker_segments,
    }, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

(OUTPUTS / "pyannote_smoke_report.json").write_text(
    json.dumps({
        "status":          "success",
        "model":           "pyannote/speaker-diarization-3.1",
        "device":          "cuda",
        "audio_file":      str(audio_path),
        "source_type":     source_type,
        "num_speakers":    len(speakers_found),
        "speakers":        speakers_found,
        "segment_count":   len(speaker_segments),
        "runtime_seconds": diar_runtime,
        "rttm_preview":    rttm_lines[:5],
    }, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"[diar] Tamamlandı — {len(speakers_found)} konuşmacı, "
      f"{len(speaker_segments)} segment, {diar_runtime}s")
print(f"[diar] Konuşmacılar: {speakers_found}")
print("[diar] Çıktılar yazıldı.")

print("\n=== PIPELINE TAMAM ===")
