"""fps A/B: ayni filmde 2fps (tam) vs 1fps (her ikinci kare) OCR recall + sure.

Dedup KAPALI (tek degisken=fps). 1fps mevcut 2fps karelerinin [::2] alt-kumesiyle simule edilir
(yeniden cikarma gerekmez). RECALL: 1fps kunye.txt, 2fps'in satirlarini kaybediyor mu?

Kullanim: python outputs/fps_compare.py <film_index>
"""
import os, sys, time, tempfile, shutil, re, subprocess
from pathlib import Path

PY_OCR = r"E:\MITAS\venvs\ocr\Scripts\python.exe"
PIPE_OCR = r"E:\MITAS\scripts\_pipe_ocr.py"
DB = Path(r"E:\MITAS\Database")
FILMS = [
    "BANA TRINITY DERLER 1968-0082-1-0000-00-1",
    "ALİTA SAVAŞ MELEĞİ 2025-1241-1-0000-90-1",
    "ARŞIN MAL ALAN 1917-1000-1-0000-21-1",
    "AĞ 2016-1031-1-0000-50-1",
]


def natkey(p):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", p.name)]


def seg_dirs(film):
    base = DB / film / "frames"
    return [(seg, base / seg) for seg in ("giris", "cikis")
            if (base / seg).exists() and any((base / seg).glob("*.png"))]


def build_subset(film, stride, root):
    """stride=1 -> orijinal dizinler; stride=2 -> her ikinci kare temp'e kopyala (1fps simulasyonu)."""
    if stride == 1:
        return [str(d) for _, d in seg_dirs(film)], sum(len(list(d.glob("*.png"))) for _, d in seg_dirs(film))
    dirs, total = [], 0
    for seg, d in seg_dirs(film):
        frames = sorted(d.glob("*.png"), key=natkey)[::stride]
        sub = root / f"{seg}_sub"
        sub.mkdir(parents=True, exist_ok=True)
        for f in frames:
            shutil.copy2(f, sub / f.name)
        dirs.append(str(sub))
        total += len(frames)
    return dirs, total


def run_ocr(frame_dirs, out_dir):
    env = dict(os.environ)
    env["MITAS_OCR_GLM_CONSENSUS"] = "0"
    env["MITAS_OCR_PADDLE"] = "0"
    env["MITAS_FRAME_DEDUP"] = "0"   # dedup KAPALI — tek degisken fps
    cmd = [PY_OCR, PIPE_OCR, "--frames", *frame_dirs, "--out", str(out_dir), "--profile", "film"]
    t0 = time.perf_counter()
    p = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p, time.perf_counter() - t0


def kunye(out_dir):
    kp = Path(out_dir) / "kunye.txt"
    if not kp.exists():
        return set()
    return {l.strip() for l in kp.read_text(encoding="utf-8").splitlines() if l.strip()}


def main():
    film = FILMS[int(sys.argv[1]) if len(sys.argv) > 1 else 1]
    root = Path(tempfile.mkdtemp(prefix="fps_cmp_"))
    print(f"FILM: {film}")
    res = {}
    for label, stride in (("2fps", 1), ("1fps", 2)):
        fdirs, nframe = build_subset(film, stride, root / label)
        out = root / ("out_" + label)
        out.mkdir(parents=True, exist_ok=True)
        p, dt = run_ocr(fdirs, out)
        k = kunye(out)
        res[label] = k
        print(f"[{label}] giris_kare~{nframe} sure={dt:.1f}s rc={p.returncode} kunye_satir={len(k)}")
        if p.returncode != 0:
            print(f"     STDERR(son): {(p.stderr or '')[-300:]}")
    base, test = res["2fps"], res["1fps"]
    lost, added = sorted(base - test), sorted(test - base)
    print("\n=== KARSILASTIRMA (1fps, 2fps'e gore) ===")
    print(f"2fps satir={len(base)}  1fps satir={len(test)}")
    print(f"1fps'te KAYIP (2fps'te VARDI): {len(lost)}")
    for x in lost[:30]:
        print(f"   - {x}")
    print(f"1fps'te DEGISEN/EKLENEN: {len(added)}")
    for x in added[:15]:
        print(f"   + {x}")
    print(f"\nRECALL (1fps 2fps'i koruyor mu): {'PASS' if base == test else 'FAIL — kayip var'}")
    print(f"out: {root}")


if __name__ == "__main__":
    main()
