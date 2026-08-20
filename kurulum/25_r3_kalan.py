#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R3 — Kova-1 profilinin kalan filmlere uygulanması (2026-07-24, Çağatay onayı).

FAZ-A (çıkış, 27 film): R2'de koşulmayan + rescue-olmayan filmler; dinamik pencere
  (credit_type scroll→30s, değilse 60s) + MAX_TOKENS=3500 → video_vl_r2/ (tek tip ad).
FAZ-B (giriş-300s, 10 film): giriş QA'sında yönetmeni bulunamayan filmler; ilk 305s
  klip → video_vl_giris300/ (240s penceresinin kestiği DIRECTED BY kartlarını yakalar).
3 rescue filmi (KIZGIN_SILAH, DERT_BENDE, OLUM_ASANSORU) çıkışta OKUNMAZ (rescue-iptal).
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

KOK = Path("/opt/mitas")
CALISMA_KOK = KOK / "filmtest" / "test_film_vl"
PY_OCR = KOK / "venvs" / "ocr" / "bin" / "python"
CHECKPOINT = CALISMA_KOK / "_sonuc_r3.json"

R2_BITTI = {"1997-0265_JURASSIC_PARK_2_KAYIP_DUNYA", "2018-1054_DON_KISOT_U_OLDUREN_ADAM",
            "1977-0198_BEYAZ_BIZON", "1993-0475_MAKSIM_IN_KAPICISI", "2017-2124_POROROCA",
            "1985-0179_UYARI_ISARETI", "1999-0363_CENNETIN_RENGI",
            "2019-1203_BARBARLARI_BEKLERKEN", "2015-1132_MONTE_KRISTO_KONTU",
            "2001-9073_ALTIN_YUMRUK_ISTANBULDA"}
GIRIS300 = ["1953-0044_KIZGIN_SILAH", "1985-0179_UYARI_ISARETI", "1991-0342_CIPLAK_AGACLAR",
            "2018-0047_MAVZER", "2015-1052_OZGURLUK_YURUYUSU", "2015-1132_MONTE_KRISTO_KONTU",
            "2024-1196_MUMYA_GERI_DONUYOR", "2024-1266_KAZANANLAR_KULUBU",
            "2025-1011_ROBINSON_CRUSOE", "2017-2124_POROROCA"]


def run(cmd, timeout=5400, env=None):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          cwd=str(KOK), env=env)


def vllm(komut):
    e = dict(os.environ)
    e["MITAS_VLLM_GPU_UTIL"] = "0.89"
    r = subprocess.run(["bash", str(KOK / "kurulum" / "vlm_sunucu.sh"), komut],
                       capture_output=True, text=True, timeout=600, env=e)
    return r.returncode == 0


def cp_io(cp=None):
    if cp is not None:
        CHECKPOINT.write_text(json.dumps(cp, ensure_ascii=False, indent=1), encoding="utf-8")
        return cp
    if CHECKPOINT.is_file():
        try:
            return json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return {}


def pencere_sec(slug: str) -> int:
    j = CALISMA_KOK / slug / "frames" / "jenerik_detection.json"
    try:
        ct = str(json.loads(j.read_text(encoding="utf-8")).get("credit_type", ""))
        return 30 if "scroll" in ct else 60
    except Exception:  # noqa: BLE001
        return 60


def cikis_oku(slug: str, cp: dict) -> None:
    k = cp.setdefault(slug, {})
    if k.get("cikis") == "ok":
        return
    ana = json.load(open(CALISMA_KOK / "_sonuc.json"))[slug]
    calisma = CALISMA_KOK / slug
    outdir = calisma / "video_vl_r2"
    okuma = outdir / "video_vl_okuma.txt"
    if okuma.is_file() and okuma.stat().st_size > 0:
        k["cikis"] = "ok"
        cp_io(cp)
        return
    p = pencere_sec(slug)
    env = dict(os.environ)
    env["MITAS_VIDEO_VL_PENCERE"] = str(p)
    env["MITAS_VIDEO_VL_MAX_TOKENS"] = "3500"
    t = time.time()
    try:
        r = run([str(PY_OCR), str(KOK / "scripts" / "_pipe_video_vl.py"),
                 "--clip", str(calisma), "--video", ana["film"], "--out", str(outdir)], env=env)
        k["cikis"] = "ok" if r.returncode in (0, 5) else f"rc={r.returncode}"
    except subprocess.TimeoutExpired:
        k["cikis"] = "timeout"
    k["pencere"] = p
    cp_io(cp)
    print(f"  [cikis] {slug}: {k['cikis']} pencere={p}s ({time.time()-t:.0f}s)", flush=True)


def giris300_oku(slug: str, cp: dict) -> None:
    k = cp.setdefault(slug, {})
    if k.get("giris300") == "ok":
        return
    ana = json.load(open(CALISMA_KOK / "_sonuc.json"))[slug]
    calisma = CALISMA_KOK / slug
    klip = calisma / "giris_300.mp4"
    if not (klip.is_file() and klip.stat().st_size > 1024):
        r = run(["ffmpeg", "-v", "error", "-ss", "0", "-i", ana["film"], "-t", "305",
                 "-an", "-c:v", "copy", "-y", str(klip)], 600)
        if not (klip.is_file() and klip.stat().st_size > 1024):
            run(["ffmpeg", "-v", "error", "-ss", "0", "-i", ana["film"], "-t", "305",
                 "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                 "-y", str(klip)], 1200)
    outdir = calisma / "video_vl_giris300"
    env = dict(os.environ)
    env["MITAS_VIDEO_VL_MAX_TOKENS"] = "3500"
    t = time.time()
    try:
        r = run([str(PY_OCR), str(KOK / "scripts" / "_pipe_video_vl.py"),
                 "--video", str(klip), "--start-sec", "0", "--out", str(outdir)], env=env)
        k["giris300"] = "ok" if r.returncode in (0, 5) else f"rc={r.returncode}"
    except subprocess.TimeoutExpired:
        k["giris300"] = "timeout"
    cp_io(cp)
    print(f"  [giris300] {slug}: {k['giris300']} ({time.time()-t:.0f}s)", flush=True)


def main() -> int:
    d = json.load(open(CALISMA_KOK / "_sonuc.json"))
    rescue = {k for k, v in d.items() if v.get("engine") == "vlm_rescue"}
    kalan = [k for k in d if k not in R2_BITTI and k not in rescue]
    cp = cp_io()
    print(f"R3: çıkış={len(kalan)} film (dinamik pencere) + giriş-300s={len(GIRIS300)} film",
          flush=True)
    if not vllm("start"):
        print("HATA: vLLM kalkmadı")
        return 2
    try:
        for slug in kalan:
            cikis_oku(slug, cp)
        for slug in GIRIS300:
            giris300_oku(slug, cp)
    finally:
        vllm("stop")
    print("R3 TAMAM", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
