#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DEPO-10 CANLI TEST: 10 depo filmi → dedektör (jenerik-başı) → 60s sessiz klipler → VL okuma.
FAZ-1 (tüm filmler): son-600s@1.5fps kare çıkarımı + _jenerik_pool dedektörü (ollama açık — VLM-rescue).
FAZ-2 (tüm filmler): _pipe_video_vl (vlm_sunucu.sh start/stop bu script çağrılmadan önce/sonra DEĞİL,
                     script kendisi yönetir: faz-2 başında start, sonunda stop).
Çıktı: /opt/mitas/filmtest/depo_3006/<film>/ altında frames/, jenerik_detection.json, video_vl/
Rapor: /opt/mitas/outputs/DEPO10_VL_RAPOR_20260716.md
"""
import json
import subprocess
import sys
import time
from pathlib import Path

KOK = Path("/opt/mitas")
DEPO = KOK / "filmtest" / "depo_3006"
PY_OCR = KOK / "venvs" / "ocr" / "bin" / "python"
RAPOR = KOK / "outputs" / "DEPO10_VL_RAPOR_20260716.md"
FPS, TAIL = 1.5, 600.0


def run(cmd, timeout=3600, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)


def sure(v: Path) -> float:
    o = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(v)], 120)
    return float(o.stdout.strip())


def faz1(video: Path, calisma: Path) -> dict:
    """Kare çıkarımı + dedektör. Döner: manifest dict (start_pos vs.)"""
    frames = calisma / "frames" / "cikis"
    pool = calisma / "frames" / "cikis_jenerik"
    dbg = calisma / "jdebug"
    frames.mkdir(parents=True, exist_ok=True)
    dur = sure(video)
    cstart = max(0.0, dur - TAIL)
    if not list(frames.glob("*.png")):
        r = run(["ffmpeg", "-v", "error", "-ss", f"{cstart:.2f}", "-i", str(video),
                 "-vf", f"fps={FPS}", "-q:v", "2", str(frames / "cikis_%06d.png")], 1800)
        if r.returncode != 0:
            return {"hata": f"ffmpeg: {r.stderr[:200]}"}
    r = run([str(PY_OCR), str(KOK / "scripts" / "_jenerik_pool.py"),
             "--frames", str(frames), "--pool", str(pool), "--debug-root", str(dbg)], 1800,
            cwd=str(KOK))
    j = calisma / "frames" / "jenerik_detection.json"
    if j.is_file():
        m = json.loads(j.read_text(encoding="utf-8"))
        m["_sure"] = dur
        m["_cstart"] = cstart
        return m
    return {"hata": f"detector rc={r.returncode}: {(r.stderr or r.stdout)[-200:]}"}


def faz2(video: Path, calisma: Path) -> tuple[int, str]:
    r = run([str(PY_OCR), str(KOK / "scripts" / "_pipe_video_vl.py"),
             "--clip", str(calisma), "--video", str(video)], 3600, cwd=str(KOK))
    return r.returncode, (r.stdout or "")[-400:]


def main():
    filmler = sorted(DEPO.glob("*.mp4"))
    if not filmler:
        print("film yok"); return 1
    print(f"{len(filmler)} film bulundu")
    R = ["# DEPO-10 Canlı Test — dedektör → 60s klipler → Qwen3-VL-8B", "",
         f"Kaynak: sas_h264/30.06/1 · {time.strftime('%Y-%m-%d %H:%M')}", ""]
    sonuc = {}

    print("\n########## FAZ-1: dedektör (ollama açık) ##########")
    for v in filmler:
        ad = v.stem.split("-", 5)[-1] if "-" in v.stem else v.stem
        calisma = DEPO / v.stem
        t = time.time()
        m = faz1(v, calisma)
        sonuc[v.stem] = m
        if "hata" in m:
            print(f"  {ad}: HATA {m['hata'][:80]}")
        else:
            sp = m.get("start_pos")
            sn = (m["_cstart"] + sp / FPS) if sp is not None else None
            print(f"  {ad}: start_pos={sp} → {sn and f'{sn:.0f}s'} ({time.time()-t:.0f}s)")

    print("\n########## FAZ-2: VL okuma (vlm_sunucu) ##########")
    subprocess.run(["bash", str(KOK / "kurulum" / "vlm_sunucu.sh"), "start"], timeout=600)
    try:
        for v in filmler:
            ad = v.stem.split("-", 5)[-1] if "-" in v.stem else v.stem
            calisma = DEPO / v.stem
            m = sonuc.get(v.stem, {})
            if "hata" in m or m.get("start_pos") is None:
                R.append(f"## {ad}\nDEDEKTÖR: {m.get('hata', 'start_pos yok (jenerik bulunamadı)')}\n")
                continue
            t = time.time()
            rc, out = faz2(v, calisma)
            okuma = calisma / "video_vl" / "video_vl_okuma.txt"
            n_parca = len(list((calisma / "video_vl").glob("parca_*.mp4"))) if (calisma / "video_vl").is_dir() else 0
            print(f"  {ad}: rc={rc}, {n_parca} parça, {time.time()-t:.0f}s")
            sn = m["_cstart"] + m["start_pos"] / FPS
            R.append(f"## {ad}")
            R.append(f"- jenerik başlangıcı: **{sn:.0f}s** (film {m['_sure']:.0f}s; start_pos={m['start_pos']})")
            R.append(f"- {n_parca} parça, video-vl rc={rc}")
            if okuma.is_file():
                metin = okuma.read_text(encoding="utf-8")
                R.append(f"- okuma: {len(metin)} karakter → `{okuma}`")
                R.append("\n```\n" + metin[:1200] + ("\n... (devamı dosyada)" if len(metin) > 1200 else "") + "\n```")
            R.append("")
    finally:
        subprocess.run(["bash", str(KOK / "kurulum" / "vlm_sunucu.sh"), "stop"], timeout=120)

    RAPOR.write_text("\n".join(R) + "\n", encoding="utf-8")
    print(f"\nRAPOR: {RAPOR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
