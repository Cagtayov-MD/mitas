"""Frame-dedup A/B smoke: ayni karelerde _pipe_ocr.py'yi OFF vs ON kosup kunye.txt karsilastir.

Tek degisken = MITAS_FRAME_DEDUP. Diger her sey sabit (GLM=0 -> ollama darbogazi yok, her iki kosuda).
RECALL INVARIANT: OFF ve ON kunye.txt satir KUMESI birebir eslesmeli (esmezse dedup isim dusurmus).

Kullanim: python outputs/frame_dedup_ab_smoke.py <film_index>
"""
import os, sys, json, subprocess, time, tempfile
from pathlib import Path

PY_OCR = r"E:\MITAS\venvs\ocr\Scripts\python.exe"
PIPE_OCR = r"E:\MITAS\scripts\_pipe_ocr.py"
DB = Path(r"E:\MITAS\Database")

# Turkce-isim argv kodlama sorununu onlemek icin adaylar burada gomulu.
FILMS = [
    "BANA TRINITY DERLER 1968-0082-1-0000-00-1",   # 0: eski western, statik-kart bekleniyor (dedup ateslemeli)
    "ALİTA SAVAŞ MELEĞİ 2025-1241-1-0000-90-1",     # 1: modern, scroll bekleniyor (dedup ~dokunmamali)
    "ARŞIN MAL ALAN 1917-1000-1-0000-21-1",         # 2: cok eski, statik-kart
    "AĞ 2016-1031-1-0000-50-1",                      # 3: modern
]


def frames_dirs(film):
    base = DB / film / "frames"
    dirs = []
    for seg in ("giris", "cikis"):
        d = base / seg
        if d.exists() and any(d.glob("*.png")):
            dirs.append(str(d))
    return dirs


def run_ocr(film, dedup, out_dir):
    env = dict(os.environ)
    env["MITAS_OCR_GLM_CONSENSUS"] = "0"   # ollama darbogazi KAPALI (her iki kosuda ayni)
    env["MITAS_OCR_PADDLE"] = "0"
    env["MITAS_FRAME_DEDUP"] = "1" if dedup else "0"
    if dedup:
        env["MITAS_FRAME_DEDUP_HAM"] = "4"
        env["MITAS_FRAME_DEDUP_KEEP"] = "3"
    cmd = [PY_OCR, PIPE_OCR, "--frames", *frames_dirs(film), "--out", str(out_dir), "--profile", "film"]
    t0 = time.perf_counter()
    p = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p, time.perf_counter() - t0


def read_out(out_dir):
    out_dir = Path(out_dir)
    kunye, summary = [], {}
    kp = out_dir / "kunye.txt"
    if kp.exists():
        kunye = [l.strip() for l in kp.read_text(encoding="utf-8").splitlines() if l.strip()]
    sp = out_dir / "ocr_summary.json"
    if sp.exists():
        try:
            summary = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            pass
    return kunye, summary


def main():
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    film = FILMS[idx]
    base_out = Path(tempfile.mkdtemp(prefix="dedup_ab_"))
    print(f"FILM: {film}")
    print(f"frames: {frames_dirs(film)}")
    res = {}
    for label, dedup in (("OFF", False), ("ON", True)):
        out = base_out / label
        out.mkdir(parents=True, exist_ok=True)
        p, dt = run_ocr(film, dedup, out)
        kunye, summary = read_out(out)
        res[label] = (kunye, summary)
        fd = summary.get("frame_dedup")
        print(f"\n[{label}] sure={dt:.1f}s rc={p.returncode} kunye_satir={len(kunye)} "
              f"credit_frames={summary.get('credit_frames')} bucket={summary.get('bucket')} frame_dedup={fd}")
        for line in (p.stderr or "").splitlines():
            if "frame-dedup" in line:
                print(f"     {line.strip()}")
        if p.returncode != 0:
            print(f"     STDERR(son): {(p.stderr or '')[-400:]}")
    off_k, on_k = set(res['OFF'][0]), set(res['ON'][0])
    print("\n=== KARSILASTIRMA ===")
    print(f"OFF satir={len(off_k)}  ON satir={len(on_k)}")
    lost = sorted(off_k - on_k)
    added = sorted(on_k - off_k)
    print(f"ON'da KAYIP (yalniz OFF): {len(lost)}")
    for x in lost[:25]:
        print(f"   - {x}")
    print(f"ON'da DEGISEN/EKLENEN (yalniz ON): {len(added)}")
    for x in added[:25]:
        print(f"   + {x}")
    print(f"\nRECALL INVARIANT (satir kumesi birebir): {'PASS' if off_k == on_k else 'FAIL'}")
    print(f"out: {base_out}")


if __name__ == "__main__":
    main()
