#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_filmtest_batch.py — E:\\filmtest\\aaaa filmlerini mitas_pipeline'dan TAZE geçir (gece koşusu).
KREDI-ODAKLI: --no-asr (özet zaten ANTHROPIC-keysiz atlanır; bu gece amaç YENİ OCR-metin okuyucuyu
end-to-end test: frame→OneOCR+GLM→credit_text→v4→routing). Resumable, per-film izole.
ÇALIŞTIR: venvs/asr python. Log: outputs/filmtest_batch.log + sonuç: outputs/filmtest_batch_results.jsonl
"""
import glob, json, os, re, subprocess, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"E:\MITAS\scripts")
import mitas_pipeline as mp

ROOT = r"E:\MITAS"; SRC = r"E:\filmtest\aaaa"; DB = r"E:\MITAS\Database"
PIPELINE = r"E:\MITAS\scripts\mitas_pipeline.py"
LOG = r"E:\MITAS\outputs\filmtest_batch.log"
RESJL = r"E:\MITAS\outputs\filmtest_batch_results.jsonl"
PY = sys.executable

def log(m):
    s = f'[{time.strftime("%H:%M:%S")}] {m}'
    print(s, flush=True)
    try:
        open(LOG, "a", encoding="utf-8").write(s + "\n")
    except Exception:
        pass

def find_films():
    fs = []
    for e in ("mp4", "mxf", "MP4", "MXF"):
        fs += glob.glob(os.path.join(SRC, "*." + e))
    return [f for f in sorted(set(fs)) if re.search(r"\d{4}-\d{3,4}-\d-\d{4}", os.path.basename(f))]

def done(video):
    try:
        return (Path(DB) / mp.sanitize(Path(video).stem) / "_DURUM.json").exists()
    except Exception:
        return False

def main():
    fs = find_films()
    log(f"=== FILMTEST BATCH (kredi-odaklı --no-asr): {len(fs)} film ===")
    ok = skip = fail = 0; t_all = time.time()
    for i, v in enumerate(fs, 1):
        n = os.path.basename(v)[:60]
        if done(v):
            skip += 1; log(f"[{i}/{len(fs)}] ATLA: {n}"); continue
        log(f"[{i}/{len(fs)}] BAŞLA: {n}")
        t0 = time.time()
        try:
            r = subprocess.run(
                [PY, PIPELINE, "--video", v, "--profile", "film_dizi", "--no-copy-source", "--no-asr"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                cwd=ROOT, timeout=3600, check=False)
            res = None
            for ln in reversed((r.stdout or "").splitlines()):
                ln = ln.strip()
                if ln.startswith("{"):
                    try:
                        res = json.loads(ln); break
                    except Exception:
                        pass
            dt = round(time.time() - t0)
            if res:
                ok += 1
                rec = {"film": n, "dt": dt, "karar": res.get("karar"), "hub": res.get("hub")}
                log(f"[{i}/{len(fs)}] OK {dt}s karar={res.get('karar')}")
            else:
                fail += 1
                rec = {"film": n, "dt": dt, "rc": r.returncode, "stderr": (r.stderr or '')[-200:]}
                log(f"[{i}/{len(fs)}] SONUCSUZ {dt}s rc={r.returncode} {(r.stderr or '')[-160:]}")
            open(RESJL, "a", encoding="utf-8").write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception as e:
            fail += 1
            log(f"[{i}/{len(fs)}] HATA: {type(e).__name__} {str(e)[:140]}")
    log(f"=== BATCH TAMAM ({round((time.time()-t_all)/60)}dk): ok={ok} atla={skip} hata={fail}/{len(fs)} ===")

if __name__ == "__main__":
    main()
