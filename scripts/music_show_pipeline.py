"""
Müzik Programı Pipeline — Gönlünüzdeki Şarkılar
  1. inaSpeechSegmenter  → müzik/konuşma zaman damgaları
  2. Audfprint            → müzik segmentlerini DB'ye karşı eşleştir
  3. MITAS ASR            → konuşma segmentlerini transkribe et

Kullanım:
  python music_show_pipeline.py --input <mp4> [--build-db] [--limit-min N]
"""

from __future__ import annotations
import argparse, io, json, os, subprocess, sys, tempfile, time
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT   = Path(__file__).resolve().parents[1]
FFMPEG = ROOT / "tools/ffmpeg-shared/ffmpeg-8.1.1-full_build-shared/bin/ffmpeg.exe"
AFP    = ROOT / "tools/audfprint/audfprint.py"
DB     = ROOT / "outputs/fingerprint_db/trt_shows.pklz"
INA_PY = ROOT / "venvs/ina/Scripts/python.exe"
ASR_PY = ROOT / "venvs/asr/Scripts/python.exe"

sys.path.insert(0, str(ROOT))


# ── Araçlar ──────────────────────────────────────────────────────────────────

def extract_wav(src: Path, dst: Path, start: float = 0, duration: float | None = None,
                sr: int = 16000) -> None:
    cmd = [str(FFMPEG), "-y", "-i", str(src)]
    if start:
        cmd += ["-ss", str(start)]
    if duration:
        cmd += ["-t", str(duration)]
    cmd += ["-map", "0:a:0", "-ar", str(sr), "-ac", "1", str(dst), "-loglevel", "error"]
    subprocess.run(cmd, check=True)


def segment_audio(wav: Path) -> list[tuple[str, float, float]]:
    """inaSpeechSegmenter ile segmentlere böl. ina venv'de çalışır."""
    script = f"""
import sys, json, warnings; warnings.filterwarnings('ignore')
sys.path.insert(0, r'{ROOT}')
from inaSpeechSegmenter import Segmenter
seg = Segmenter()
result = seg(r'{wav}')
print(json.dumps([[l,round(s,2),round(e,2)] for l,s,e in result]))
"""
    out = subprocess.check_output([str(INA_PY), "-c", script], stderr=subprocess.DEVNULL)
    # TF progress bar'ları stdout'a karışabiliyor — sadece [ ile başlayan son satırı al
    lines = [l.strip() for l in out.decode("utf-8", errors="replace").splitlines()
             if l.strip().startswith("[")]
    return [(l, s, e) for l, s, e in json.loads(lines[-1])]


def audfprint_add(wav: Path, song_id: str) -> None:
    DB.parent.mkdir(parents=True, exist_ok=True)
    cmd_base = [str(ASR_PY), str(AFP)]
    if DB.exists():
        subprocess.run(cmd_base + ["add", "--dbase", str(DB), str(wav)],
                       capture_output=True)
    else:
        subprocess.run(cmd_base + ["new", "--dbase", str(DB), str(wav)],
                       capture_output=True)


def audfprint_match(wav: Path) -> str | None:
    if not DB.exists():
        return None
    out = subprocess.run(
        [str(ASR_PY), str(AFP), "match", "--dbase", str(DB), str(wav)],
        capture_output=True, text=True
    ).stdout
    for line in out.splitlines():
        if "Matched" in line and "at" in line:
            # "Matched ... as <path> at X.X s with Y of Z..."
            parts = line.split(" as ")
            if len(parts) > 1:
                name = Path(parts[1].split(" at ")[0].strip()).stem
                return name
    return None


def mitas_transcribe(wav: Path) -> str:
    script = f"""
import sys, warnings; warnings.filterwarnings('ignore')
sys.path.insert(0, r'{ROOT}')
from pathlib import Path
from core.pipelines.asr.transcribe import transcribe
r = transcribe(Path(r'{wav}'), profile='fast_with_fallback')
print(r.clean_transcript)
"""
    try:
        out = subprocess.check_output([str(ASR_PY), "-c", script],
                                      stderr=subprocess.DEVNULL, timeout=120)
        return out.decode("utf-8", errors="replace").strip()
    except Exception as e:
        return f"[ASR HATA: {e}]"


# ── Ana akış ─────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--build-db", action="store_true",
                        help="Bulunan müzik segmentlerini DB'ye ekle")
    parser.add_argument("--limit-min", type=float, default=None,
                        help="Sadece ilk N dakikayı işle")
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "outputs" / "muzik_pipeline")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="mitas_music_"))

    # ── WAV çıkar ────────────────────────────────────────────────────────────
    wav_full = tmp / "full.wav"
    duration = args.limit_min * 60 if args.limit_min else None
    print(f"\nWAV çıkarılıyor: {args.input.name}" +
          (f" (ilk {args.limit_min:.0f} dk)" if args.limit_min else " (tam)"))
    extract_wav(args.input, wav_full, duration=duration)

    # ── Segmentasyon ─────────────────────────────────────────────────────────
    print("Segmentasyon (inaSpeechSegmenter)...")
    t0 = time.perf_counter()
    segments = segment_audio(wav_full)
    print(f"  Tamam: {time.perf_counter()-t0:.1f}s  |  {len(segments)} segment")

    # Kısa segmentleri birleştir (< 3s geçiş gürültüsü)
    merged: list[tuple[str, float, float]] = []
    for lbl, start, end in segments:
        if merged and merged[-1][0] == lbl and start - merged[-1][2] < 1.5:
            merged[-1] = (lbl, merged[-1][1], end)
        elif end - start >= 2.0:
            merged.append((lbl, start, end))
    segments = merged

    music_segs  = [(s, e) for l, s, e in segments if l == "music"]
    speech_segs = [(l, s, e) for l, s, e in segments if l in ("male", "female")]
    print(f"  Müzik: {len(music_segs)} segment  |  Konuşma: {len(speech_segs)} segment")

    # ── Müzik DB build (isteğe bağlı) ────────────────────────────────────────
    if args.build_db:
        print("\nDB'ye şarkılar ekleniyor...")
        for i, (start, end) in enumerate(music_segs):
            dur = end - start
            if dur < 10:
                continue
            seg_wav = tmp / f"music_{i:03d}.wav"
            extract_wav(wav_full, seg_wav, start=start, duration=min(dur, 60))
            song_id = f"{args.input.stem}_music_{i:03d}_at_{int(start)}s"
            audfprint_add(seg_wav, song_id)
            print(f"  [{i+1}/{len(music_segs)}] {start:.0f}s-{end:.0f}s ({dur:.0f}s) → {song_id}")

    # ── Pipeline çalıştır ────────────────────────────────────────────────────
    print("\nPipeline çalışıyor...\n")
    print("=" * 70)
    results = []

    for lbl, start, end in segments:
        dur = end - start
        ts  = f"{int(start//60):02d}:{int(start%60):02d}"
        te  = f"{int(end//60):02d}:{int(end%60):02d}"

        if lbl == "music":
            seg_wav = tmp / f"seg_{int(start)}.wav"
            extract_wav(wav_full, seg_wav, start=start, duration=min(dur, 60))
            match = audfprint_match(seg_wav)
            label = f"SARKI: {match}" if match else "SARKI: [tanınmadı — DB gerekli]"
            print(f"🎵  {ts}-{te}  ({dur:.0f}s)  {label}")
            results.append({"type": "music", "start": start, "end": end,
                            "duration": dur, "match": match})

        elif lbl in ("male", "female"):
            seg_wav = tmp / f"seg_{int(start)}.wav"
            extract_wav(wav_full, seg_wav, start=start, duration=dur)
            if dur < 3.0:
                text = "[çok kısa]"
            else:
                text = mitas_transcribe(seg_wav)
            print(f"💬  {ts}-{te}  ({dur:.0f}s)  {text[:120]}")
            results.append({"type": "speech", "gender": lbl, "start": start,
                            "end": end, "duration": dur, "text": text})

        elif lbl == "noEnergy":
            results.append({"type": "silence", "start": start, "end": end})

    # ── Rapor kaydet ─────────────────────────────────────────────────────────
    stem = args.input.stem[:40]
    json_out = args.output_dir / f"{stem}_pipeline.json"
    md_out   = args.output_dir / f"{stem}_pipeline.md"

    json_out.write_text(json.dumps(results, ensure_ascii=False, indent=2),
                        encoding="utf-8")

    md_lines = [f"# Pipeline Raporu — {args.input.name}\n"]
    for r in results:
        ts = f"{int(r['start']//60):02d}:{int(r['start']%60):02d}"
        te = f"{int(r['end']//60):02d}:{int(r['end']%60):02d}"
        if r["type"] == "music":
            md_lines.append(f"**🎵 {ts}–{te}** ({r['duration']:.0f}s) — {r.get('match') or 'tanınmadı'}\n")
        elif r["type"] == "speech":
            md_lines.append(f"**💬 {ts}–{te}** ({r['duration']:.0f}s) [{r['gender']}]\n> {r.get('text','')}\n")
    md_out.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"\n{'='*70}")
    print(f"JSON : {json_out}")
    print(f"MD   : {md_out}")

    import shutil; shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
