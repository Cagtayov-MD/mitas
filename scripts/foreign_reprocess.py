#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""foreign_reprocess.py — YABANCI-ses + BOZUK-özet filmleri YERİNDE düzelt (dir-dup YARATMADAN).
Zincir: tüm-film FULL large-v3 ASR (auto-detect → temiz yabancı transkript) → Sonnet özet →
kunye_teslim.md özet bölümünü yamala → tek_film_kunye ile künyeyi yeniden render.
Hedef: ana_dil≠TR + özeti bozuk (meta-sızıntı/çok kısa) filmler. venvs/asr python + ANTHROPIC_API_KEY env."""
import sys, os, re, glob, time, subprocess, datetime, shutil
sys.path.insert(0, r"E:\MITAS\scripts")
sys.stdout.reconfigure(encoding="utf-8")
import mitas_pipeline as mp          # _generate_ozet
from faster_whisper import WhisperModel

PY_PDF = r"C:\Users\TRT03\AppData\Local\Programs\Python\Python310\python.exe"
TK = r"E:\MITAS\scripts\tek_film_kunye.py"
FF = r"E:\MITAS\tools\ffmpeg-shared\ffmpeg-8.1.1-full_build-shared\bin\ffmpeg.exe"
DEST = r"E:\MITAS\Mitas Output\DUZELTILMIS_44"
DB = r"E:\MITAS\Database"
trt_re = re.compile(r"(\d{4})-(\d{3,4})-(\d)-(\d{4})-\d{2}-\d")
thr = datetime.datetime(2026, 6, 5, 0, 0).timestamp()
META = ["TRANSKR", "TRANSCR", " ASR ", "GÜRÜLTÜ", "OKUNAMA", "ANLAŞILMAZ", "ÇIKARMAK MÜMKÜN",
        "ANLAMLI BİR OLAY", "YETERLİ OLAY", "BELİRSİZ DİL"]

def md_fields(md):
    t = open(md, encoding="utf-8").read()
    mt = re.search(r"#\s*M[İI]TAS\s*[•·]\s*\w+\s*[•·]\s*(.+)", t)
    title = mt.group(1).strip() if mt else ""
    du = re.search(r"Süre:\s*([0-9:]+)", t)
    dur = du.group(1) if du else ""
    ma = re.search(r"-\s*Ana dil:\s*(.+)", t)
    ad = ma.group(1).strip().upper() if ma else "?"
    mo = re.search(r"##\s*Özet\s*\n(.+)", t, re.S)
    oz = re.sub(r"\s+", " ", mo.group(1)).strip() if mo else ""
    return t, title, dur, ad, oz

def garbled(oz):
    u = " " + oz.upper() + " "
    return (len(oz) < 45) or any(w in u for w in META)

clips = [d for d in glob.glob(os.path.join(DB, "*"))
         if os.path.isdir(d) and os.path.exists(os.path.join(d, "pdf", "kunye_teslim.md"))
         and os.path.exists(os.path.join(d, "pdf", "kunye.pdf"))
         and os.path.getmtime(os.path.join(d, "pdf", "kunye.pdf")) >= thr and trt_re.search(os.path.basename(d))]
targets = []
for d in clips:
    try:
        _, title, dur, ad, oz = md_fields(os.path.join(d, "pdf", "kunye_teslim.md"))
    except Exception:
        continue
    if ad not in ("TR", "—", "?") and garbled(oz):
        targets.append((d, title, dur, ad))
print(f"=== YABANCI + BOZUK-özet hedef: {len(targets)} film ===", flush=True)
for d, ti, du, ad in targets:
    print(f"  {ad:3} | {ti[:26]:26} | {os.path.basename(d)[:40]}", flush=True)
if not targets:
    print("hedef yok — bitti"); print("FOREIGN_REPROCESS_DONE"); sys.exit(0)

print("[full large-v3] yükleniyor (1 kez)...", flush=True)
model = WhisperModel("large-v3", device="cuda", compute_type="float16")
done = 0
for d, title, dur, ad in targets:
    name = os.path.basename(d); t0 = time.time()
    audio = os.path.join(d, "audio", "audio16k.wav")
    if not os.path.exists(audio):
        src = next(iter(glob.glob(os.path.join(d, "source", "*.*"))), None)
        if not src:
            print(f"X {name[:40]} ses YOK", flush=True); continue
        audio = os.path.join(d, "audio", "_reasr16k.wav"); os.makedirs(os.path.dirname(audio), exist_ok=True)
        subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error", "-i", src, "-vn", "-ac", "1",
                        "-ar", "16000", "-acodec", "pcm_s16le", audio], check=True)
    try:
        segs, info = model.transcribe(audio, language=None, beam_size=1, vad_filter=True,
                                      vad_parameters=dict(min_silence_duration_ms=500),
                                      condition_on_previous_text=False, word_timestamps=False)
        transcript = "\n".join(s.text.strip() for s in segs)
    except Exception as e:
        print(f"X {name[:40]} ASR hata {type(e).__name__}", flush=True); continue
    ozet = mp._generate_ozet(transcript, title=title, duration=dur) or ""
    md = os.path.join(d, "pdf", "kunye_teslim.md"); txt = open(md, encoding="utf-8").read()
    if ozet and len(ozet) > 45:
        if re.search(r"##\s*Özet", txt):
            txt = re.sub(r"##\s*Özet\s*\n.*$", "## Özet\n" + ozet, txt, flags=re.S)
        else:
            txt = txt.rstrip() + "\n\n## Özet\n" + ozet + "\n"
        open(md, "w", encoding="utf-8").write(txt)
    m = trt_re.search(name)
    prof = "dizi" if m.group(3) == "0" else "film"
    bol = f"{int(m.group(4))}. BÖLÜM" if prof == "dizi" else None
    tmp = os.path.join(d, "pdf", "kunye_reoz.pdf")
    cmd = [PY_PDF, TK, "--clip", d, "--out", tmp, "--profile", prof]
    if bol:
        cmd += ["--bolum", bol]
    subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    ok = os.path.exists(tmp) and os.path.getsize(tmp) > 10000
    if ok:
        os.replace(tmp, os.path.join(d, "pdf", "kunye.pdf"))
        png = tmp.replace(".pdf", "_onizleme.png")
        if os.path.exists(png):
            os.replace(png, os.path.join(d, "pdf", "kunye_onizleme.png"))
        dd = os.path.join(DEST, name); os.makedirs(dd, exist_ok=True)
        for fn in ("kunye.pdf", "kunye_onizleme.png"):
            s = os.path.join(d, "pdf", fn)
            if os.path.exists(s):
                shutil.copy2(s, dd)
        done += 1
    elif os.path.exists(tmp):
        os.remove(tmp)
    print(f"{'OK' if ok else 'X '} {name[:36]} dil={info.language} {len(transcript)}kar {round(time.time()-t0)}s | özet: {ozet[:70]!r}", flush=True)
print(f"=== {done}/{len(targets)} yabancı film özeti DÜZELTİLDİ ===")
print("FOREIGN_REPROCESS_DONE")
