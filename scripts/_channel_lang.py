# -*- coding: utf-8 -*-
"""Ses STREAM + KANAL envanteri + her birinin DİLİ + özet kanalı seçimi (film dil-tespit).

KURAL (Çağatay, 2026-06-02):
  • TÜM ses stream'leri ve kanallarına bak; her birinin dilini KONUŞMADA tespit et
    (130/300/480s film gövdesi). Düşük güven / konuşmasız = efekt → elenir.
  • Özet kanalı: hangisi TÜRKÇE ise ONDAN (Whisper tr). Türkçe yoksa → ilk konuşma kanalı (kanal 1) ne ise o dilde.
  • Farklı dildeki diğer kanal = bilgi için saklanır (özet değil). Fiziksel no önemsiz.

Whisper'ın kendi dil-tespiti (ekstra LID modeli yok). stdout'a tek JSON.
  venvs/asr/Scripts/python.exe scripts/_channel_lang.py "<video>"
"""
import sys, json, subprocess
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
from faster_whisper import WhisperModel

ROOT = Path(r"E:\MITAS")
FF = ROOT / "tools" / "ffmpeg-shared" / "ffmpeg-8.1.1-full_build-shared" / "bin" / "ffmpeg.exe"
FP = ROOT / "tools" / "ffmpeg-shared" / "ffmpeg-8.1.1-full_build-shared" / "bin" / "ffprobe.exe"
MODEL = ROOT / "models" / "asr" / "faster-whisper" / "large-v3-turbo"
TMP = ROOT / "outputs" / "_ocrpdf_run" / "_chlang"
TMP.mkdir(parents=True, exist_ok=True)

SAMPLES = [130, 300, 480]
EXTRA_SAMPLES = [190, 360, 540]   # iki dil eşikte gezerse örneği ÇOĞALT (≈1 dk sonrasından +30s)
SDUR = 30
MIN_PROB = 0.60
MIX_RATIO = 0.30                  # ikincil/birincil oran → "iç içe" (seslendirme + orijinal karışık)
AMBIG_RATIO = 0.25                # bu üstü belirsiz → ekstra örnek al


def audio_streams(video: str) -> list[int]:
    """Her ses stream'inin kanal sayısı → [2, 2] = 2 stream, 2'şer kanal."""
    try:
        out = subprocess.run([str(FP), "-v", "error", "-select_streams", "a",
                              "-show_entries", "stream=channels", "-of", "csv=p=0", video],
                             capture_output=True, text=True).stdout.strip().splitlines()
        return [int(x) for x in out if x.strip().isdigit()] or [1]
    except Exception:
        return [1]


def extract(video: str, s: int, c: int, start: int, dur: int, dst: Path) -> bool:
    subprocess.run([str(FF), "-y", "-hide_banner", "-loglevel", "error",
                    "-ss", str(start), "-t", str(dur), "-i", video,
                    "-map", f"0:a:{s}", "-af", f"pan=mono|c0=c{c}",
                    "-ar", "16000", "-acodec", "pcm_s16le", str(dst)], capture_output=True)
    return dst.exists() and dst.stat().st_size > 1000


def _sample_into(model, video, s, c, times, votes, n):
    for t in times:
        smp = TMP / f"s{s}_c{c}_{int(t)}.wav"
        if not extract(video, s, c, t, SDUR, smp):
            continue
        try:
            _segs, info = model.transcribe(str(smp), language=None, beam_size=1, vad_filter=True)
            votes[info.language] = votes.get(info.language, 0.0) + float(info.language_probability or 0.0)
            n[0] += 1
        except Exception:
            continue


def detect(model, video, s, c) -> dict:
    votes, n = {}, [0]
    _sample_into(model, video, s, c, SAMPLES, votes, n)
    top = sorted(votes.items(), key=lambda x: -x[1])
    # iki dil EŞİKTE geziyorsa → örneği çoğalt (≈1 dk sonrasından tekrar 30s)
    if len(top) >= 2 and top[1][1] >= AMBIG_RATIO * top[0][1]:
        _sample_into(model, video, s, c, EXTRA_SAMPLES, votes, n)
        top = sorted(votes.items(), key=lambda x: -x[1])
    if not votes:
        return {"stream": s, "channel": c, "language": None, "confidence": 0.0, "role": "efekt/sessiz",
                "mixed": False, "secondary": None, "label": "boş", "samples": n[0]}
    best, bv = top[0]
    conf = round(bv / max(1, n[0]), 3)
    # ikincil dil belirgin payda mı? → "iç içe" (seslendirme + orijinal karışık)
    secondary = top[1][0] if (len(top) >= 2 and top[1][1] >= MIX_RATIO * bv) else None
    mixed = secondary is not None
    role = "konuşma" if conf >= MIN_PROB else "efekt/zayıf"
    label = best.upper() if role == "konuşma" else "efekt"   # rayda kısa; "iç içe" ayrı not
    return {"stream": s, "channel": c, "language": best, "secondary": secondary, "mixed": mixed,
            "confidence": conf, "role": role, "label": label, "samples": n[0],
            "votes": {k: round(v, 3) for k, v in votes.items()}}


def main():
    video = sys.argv[1]
    streams = audio_streams(video)
    print(f"[info] {len(streams)} stream, kanallar={streams}", file=sys.stderr, flush=True)
    model = WhisperModel(str(MODEL), device="cuda", compute_type="float16", local_files_only=True)

    units = []
    for s, nch in enumerate(streams):
        for c in range(nch):
            units.append(detect(model, video, s, c))

    speech = [u for u in units if u["role"] == "konuşma"]
    tr = next((u for u in speech if u["language"] == "tr"), None)
    if tr:
        summary, reason = tr, "türkçe kanal bulundu → özet ondan (Whisper tr)"
    elif speech:
        summary, reason = speech[0], "türkçe yok → ilk konuşma kanalı, kendi dilinde"
    else:
        summary, reason = (units[0] if units else {"stream": 0, "channel": 0, "language": None}), "konuşma yok → fallback kanal 0"

    others = [{"stream": u["stream"], "channel": u["channel"], "language": u["language"]}
              for u in speech if (u["stream"], u["channel"]) != (summary["stream"], summary["channel"])]
    print(json.dumps({
        "n_streams": len(streams), "channels_per_stream": streams,
        "units": units,
        "summary_stream": summary["stream"], "summary_channel": summary["channel"],
        "summary_language": summary["language"], "select_reason": reason,
        "sesler_ic_ice": any(u.get("mixed") for u in speech),
        "ic_ice_diller": sorted({d for u in speech if u.get("mixed")
                                 for d in (u["language"], u.get("secondary")) if d}),
        "info_channels (bilgi için saklanır)": others,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
