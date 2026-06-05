#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
gece_batch.py — filmtest/aaaa filmlerini SIRAYLA mitas_pipeline'dan geçir (UI baypas, GÜVENİLİR).

Neden: webui akış-kuyruğu KAYIT HATASI veriyor (queue.json'a dosya yolları kaydedilemiyor →
server worker işleyemiyor). Bu betik orijinal dosyaları (doğru adlı, yerel) doğrudan koşturur:
tarayıcı/kayıt-hatası YOK, künye garanti, her film bağımsız (tek çökme tüm batch'i bozmaz).

ÇALIŞTIR: venvs/asr python ile + ANTHROPIC_API_KEY env'de (özet için). Resumable (işlenmiş atlanır).
  $env:ANTHROPIC_API_KEY=[Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY','User')
  & 'E:\MITAS\venvs\asr\Scripts\python.exe' 'E:\MITAS\scripts\gece_batch.py'
"""
import glob, json, os, re, subprocess, sys, time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"E:\MITAS\scripts")
import mitas_pipeline as mp  # sadece sanitize (resume) için

ROOT = r"E:\MITAS"
SRC = r"E:\filmtest\aaaa"
DB = r"E:\MITAS\Database"
PIPELINE = r"E:\MITAS\scripts\mitas_pipeline.py"
LOG = r"E:\MITAS\outputs\gece_batch.log"
PY = sys.executable  # venvs/asr (bu betik onunla koşuyor)

def log(m):
    s = f'[{time.strftime("%H:%M:%S")}] {m}'
    print(s, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(s + "\n")
    except Exception:
        pass

def find_films():
    fs = []
    for e in ("mp4", "mxf", "MP4", "MXF"):
        fs += glob.glob(os.path.join(SRC, "*." + e))
    # sadece TRT-id'li gerçek filmler (E~3J2XLC gibi junk atlanır)
    return [f for f in sorted(set(fs)) if re.search(r"\d{4}-\d{3,4}-\d-\d{4}", os.path.basename(f))]

def already_done(video):
    try:
        clip = mp.sanitize(Path(video).stem)
        return (Path(DB) / clip / "_DURUM.json").exists()
    except Exception:
        return False

def main():
    fs = find_films()
    log(f"=== GECE BATCH başladı: {len(fs)} film (filmtest/aaaa) — sıralı, ~6.4dk/film ===")
    ok = skip = fail = 0
    t_all = time.time()
    for i, v in enumerate(fs, 1):
        n = os.path.basename(v)[:58]
        if already_done(v):
            skip += 1
            log(f"[{i}/{len(fs)}] ATLA (zaten işlenmiş): {n}")
            continue
        log(f"[{i}/{len(fs)}] BAŞLIYOR: {n}")
        t0 = time.time()
        try:
            r = subprocess.run(
                [PY, PIPELINE, "--video", v, "--profile", "film_dizi", "--no-copy-source"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                cwd=ROOT, timeout=5400, check=False,
            )
            res = None
            for ln in reversed((r.stdout or "").splitlines()):
                ln = ln.strip()
                if ln.startswith("{"):
                    try:
                        res = json.loads(ln)
                    except Exception:
                        pass
                    else:
                        break
            dt = round(time.time() - t0)
            if res:
                ok += 1
                log(f"[{i}/{len(fs)}] OK BITTI {dt}s karar={res.get('karar')} hub={os.path.basename(str(res.get('hub') or ''))[:40]}")
            else:
                fail += 1
                log(f"[{i}/{len(fs)}] SONUCSUZ {dt}s rc={r.returncode} stderr={(r.stderr or '')[-160:]}")
        except Exception as e:
            fail += 1
            log(f"[{i}/{len(fs)}] HATA {round(time.time() - t0)}s: {type(e).__name__} {str(e)[:140]}")
    log(f"=== BATCH TAMAM ({round((time.time()-t_all)/60)}dk): ok={ok} atla={skip} hata={fail} / {len(fs)} ===")

if __name__ == "__main__":
    main()
