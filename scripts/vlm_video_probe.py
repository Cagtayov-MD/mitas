#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
vlm_video_probe.py — "Videoyu ver, soruyu sor."

Bir video parcasindan ffmpeg ile kare cikarir, kareleri yerel Ollama'daki bir
gorsel-dil modeline (qwen2.5vl / qwen3-vl ...) DIZI olarak verir ve sorulan
soruyu cevaplatir. Ollama videoyu direkt yutmadigi icin kare ornekleme bizde.

Ornek:
  python scripts/vlm_video_probe.py ^
    --video "\\\\depo01...\\film.mp4" ^
    --question "Bu klipte ne oluyor? Ekranda gorunen isimleri/yazilari oku." ^
    --start 0 --dur 90 --fps 0.2 --model qwen2.5vl:7b

Stdlib disinda bagimlilik YOK (urllib + base64 + ffmpeg subprocess).
"""
import argparse
import base64
import glob
import json
import os
import subprocess
import sys
import time
import urllib.request

FFMPEG = r"E:\MITAS\tools\ffmpeg-shared\ffmpeg-8.1.1-full_build-shared\bin\ffmpeg.exe"
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"


def extract_frames(video, out_dir, start, dur, fps, width):
    os.makedirs(out_dir, exist_ok=True)
    for old in glob.glob(os.path.join(out_dir, "f_*.jpg")):
        os.remove(old)
    vf = "fps={fps},scale={w}:-2".format(fps=fps, w=width)
    cmd = [
        FFMPEG, "-hide_banner", "-loglevel", "error",
        "-ss", str(start), "-t", str(dur), "-i", video,
        "-vf", vf, "-q:v", "3",
        os.path.join(out_dir, "f_%04d.jpg"),
    ]
    subprocess.run(cmd, check=True)
    return sorted(glob.glob(os.path.join(out_dir, "f_*.jpg")))


def b64(path):
    with open(path, "rb") as fh:
        return base64.b64encode(fh.read()).decode("ascii")


def ask_ollama(model, question, frames, num_ctx, num_predict, repeat_penalty, top_p):
    images = [b64(f) for f in frames]
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": question, "images": images}],
        "stream": False,
        "think": False,  # Qwen3-VL gibi modellerde <think> modunu kapat -> direkt cevap
        "options": {
            "temperature": 0.3,
            "top_p": top_p,
            "num_ctx": num_ctx,
            "num_predict": num_predict,
            "repeat_penalty": repeat_penalty,
            "repeat_last_n": 256,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL, data=data, headers={"Content-Type": "application/json"}
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=1800) as r:
        resp = json.loads(r.read().decode("utf-8"))
    dt = time.time() - t0
    msg = resp.get("message", {})
    content = (msg.get("content") or "").strip()
    if not content:  # bazi modeller cevabi thinking alanina koyabilir
        content = (msg.get("thinking") or "").strip()
    return content, dt, resp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--question", required=True)
    ap.add_argument("--model", default="qwen2.5vl:7b")
    ap.add_argument("--start", type=float, default=0.0, help="saniye")
    ap.add_argument("--dur", type=float, default=90.0, help="saniye")
    ap.add_argument("--fps", type=float, default=0.2, help="kare/sn (0.2 = 5 sn'de 1 kare)")
    ap.add_argument("--width", type=int, default=512)
    ap.add_argument("--num-ctx", type=int, default=32768)
    ap.add_argument("--num-predict", type=int, default=900, help="cevap token siniri")
    ap.add_argument("--repeat-penalty", type=float, default=1.3, help="tekrar cezasi (loop kirar)")
    ap.add_argument("--top-p", type=float, default=0.9)
    ap.add_argument("--out", default=r"E:\MITAS\_vlm_probe")
    ap.add_argument("--frames-from", default=None,
                    help="ffmpeg ile cikarmak yerine bu klasordeki *.jpg kareleri kullan")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    if args.frames_from:
        run_dir = args.frames_from
        frames = sorted(glob.glob(os.path.join(run_dir, "*.jpg")))
        print("[1/3] Hazir kareler kullaniliyor: {n} kare <- {d}".format(n=len(frames), d=run_dir), flush=True)
    else:
        run_dir = os.path.join(args.out, "frames")
        print("[1/3] Kare cikariliyor (ffmpeg)...", flush=True)
        frames = extract_frames(args.video, run_dir, args.start, args.dur, args.fps, args.width)
    if not frames:
        print("HATA: hic kare cikmadi. Video yolu / start-dur dogru mu?", file=sys.stderr)
        sys.exit(2)
    print("      {n} kare -> {d}".format(n=len(frames), d=run_dir), flush=True)

    print("[2/3] Model dusunuyor: {m} ({n} kare)...".format(m=args.model, n=len(frames)), flush=True)
    answer, dt, raw = ask_ollama(
        args.model, args.question, frames, args.num_ctx,
        args.num_predict, args.repeat_penalty, args.top_p,
    )
    with open(os.path.join(args.out, "raw.json"), "w", encoding="utf-8") as fh:
        json.dump(raw, fh, ensure_ascii=False, indent=2)

    # Qwen3-VL gibi modeller /no_think'e ragmen "thinking" yapabilir ve asil
    # cevabi orada birakip content'i token sinirina takilip yarim verebilir.
    # Bu yuzden thinking alanini ayri dosyaya dok; gerekiyorsa kullaniciya isaret et.
    thinking = (raw.get("message", {}).get("thinking") or "").strip()
    done_reason = raw.get("done_reason", "")
    if thinking:
        with open(os.path.join(args.out, "thinking.txt"), "w", encoding="utf-8") as fh:
            fh.write(thinking + "\n")
    if done_reason == "length" and thinking and len(thinking) > len(answer) * 2:
        print("[!] UYARI: cevap token sinirina takildi (done_reason=length) ve asil "
              "okuma 'thinking' alaninda kaldi -> thinking.txt", flush=True)

    print("[3/3] Cevap geldi ({s:.1f} sn).".format(s=dt), flush=True)
    ans_path = os.path.join(args.out, "answer.txt")
    with open(ans_path, "w", encoding="utf-8") as fh:
        fh.write("MODEL: {m}\n".format(m=args.model))
        fh.write("VIDEO: {v}\n".format(v=args.video))
        fh.write("PENCERE: start={s}s dur={d}s fps={f} -> {n} kare\n".format(
            s=args.start, d=args.dur, f=args.fps, n=len(frames)))
        fh.write("SORU: {q}\n".format(q=args.question))
        fh.write("SURE: {s:.1f} sn\n".format(s=dt))
        fh.write("\n=== CEVAP ===\n")
        fh.write(answer.strip() + "\n")

    print("\n================= CEVAP =================\n")
    print(answer.strip())
    print("\n========================================")
    print("Kareler : {d}".format(d=run_dir))
    print("Cevap   : {p}".format(p=ans_path))


if __name__ == "__main__":
    main()
