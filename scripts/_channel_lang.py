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
import sys, os, json, subprocess
os.environ.setdefault("USE_TF", "0")        # transformers TF'yi import etmesin (numpy2 çakışması)
os.environ.setdefault("USE_FLAX", "0")
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
AST_MODEL = "MIT/ast-finetuned-audioset-10-10-0.4593"   # MÜZİK-GATE: müzik/konuşma ayrımı (AudioSet)


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


_AST = None
_AST_TRIED = False


def _get_ast():
    """AST müzik/konuşma sınıflandırıcısını BİR KEZ yükle (tekil). Yüklenemezse None → gate kapanır."""
    global _AST, _AST_TRIED
    if _AST_TRIED:
        return _AST
    _AST_TRIED = True
    try:
        from transformers import pipeline
        _AST = pipeline("audio-classification", model=AST_MODEL, device=0, top_k=6)
        print("[info] müzik-gate AÇIK (AST yüklendi)", file=sys.stderr, flush=True)
    except Exception as exc:  # noqa: BLE001 - yüklenemezse gate'siz devam
        print(f"[uyarı] AST yüklenemedi → müzik-gate KAPALI: {type(exc).__name__}: {exc}",
              file=sys.stderr, flush=True)
        _AST = None
    return _AST


def _is_music(ast_top) -> bool:
    """AST top-k → bu 30s örnek MÜZİK mi? (top-1 müzik-tipi VE top-3'te konuşma YOK).
    Konuşma top-3'teyse (diyalog + müzik yatağı dahil) KORUNUR — tutucu: gerçek konuşmayı atma."""
    labels = [d["label"].lower() for d in ast_top]
    speech_top3 = any(("speech" in l or "conversation" in l or "narration" in l) for l in labels[:3])
    top1 = labels[0]
    return (("music" in top1) or ("singing" in top1)) and not speech_top3


def _sample_into(model, video, s, c, times, votes, n, skipped):
    ast = _get_ast()
    for t in times:
        smp = TMP / f"s{s}_c{c}_{int(t)}.wav"
        if not extract(video, s, c, t, SDUR, smp):
            continue
        if ast is not None:                       # MÜZİK-GATE: müzik örneğini LID oyuna KATMA
            try:
                if _is_music(ast(str(smp))):
                    skipped[0] += 1
                    continue
            except Exception:                     # noqa: BLE001 - AST hata verirse gate'siz say
                pass
        try:
            _segs, info = model.transcribe(str(smp), language=None, beam_size=1, vad_filter=True)
            votes[info.language] = votes.get(info.language, 0.0) + float(info.language_probability or 0.0)
            n[0] += 1
        except Exception:
            continue


def detect(model, video, s, c) -> dict:
    votes, n, skipped = {}, [0], [0]
    _sample_into(model, video, s, c, SAMPLES, votes, n, skipped)
    top = sorted(votes.items(), key=lambda x: -x[1])
    # müzik ATLANDI→az konuşma örneği kaldı, VEYA iki dil EŞİKTE → örneği çoğalt (≈1 dk sonrası +30s)
    need_more = (n[0] < 2 and skipped[0] > 0) or (len(top) >= 2 and top[1][1] >= AMBIG_RATIO * top[0][1])
    if need_more:
        _sample_into(model, video, s, c, EXTRA_SAMPLES, votes, n, skipped)
        top = sorted(votes.items(), key=lambda x: -x[1])
    if not votes:
        return {"stream": s, "channel": c, "language": None, "confidence": 0.0, "role": "efekt/sessiz",
                "mixed": False, "secondary": None, "label": "boş", "samples": n[0], "skipped_music": skipped[0]}
    best, bv = top[0]
    conf = round(bv / max(1, n[0]), 3)
    # ikincil dil belirgin payda mı? → "iç içe" (seslendirme + orijinal karışık)
    secondary = top[1][0] if (len(top) >= 2 and top[1][1] >= MIX_RATIO * bv) else None
    mixed = secondary is not None
    role = "konuşma" if conf >= MIN_PROB else "efekt/zayıf"
    label = best.upper() if role == "konuşma" else "efekt"   # rayda kısa; "iç içe" ayrı not
    return {"stream": s, "channel": c, "language": best, "secondary": secondary, "mixed": mixed,
            "confidence": conf, "role": role, "label": label, "samples": n[0], "skipped_music": skipped[0],
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
        # Konuşma kanalı YOK → dil belirlenemez; units[0]'ın düşük-güven tahmini atanmaz.
        summary = {"stream": 0, "channel": 0, "language": None}
        reason = "konuşma yok → dil belirlenemedi"

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
