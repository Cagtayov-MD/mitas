"""Master PNG monitör — production core'a DOKUNMAZ.
db_compose_master'ın compose fonksiyonlarını + 'master' dispatch'ini yeniden kullanır;
Database/<film>/frames/{giris,cikis} hazır olunca master.png üretip
Database/<film>/master/{giris,cikis}.png olarak yazar.

  Tek film test:   python master_png_monitor.py --once "<Database klasör adı>"
  Canlı monitör:   python master_png_monitor.py            (Database'i izler, biten filmlere üretir)
"""
import sys, os, time, glob, json, types, importlib.util
from pathlib import Path

sys.path.insert(0, r"E:\MITAS\OCR-worktree")
_spec = importlib.util.spec_from_file_location("dcmaster", r"E:\MITAS\OCR-worktree\db_compose_master.py")
dc = importlib.util.module_from_spec(_spec); sys.modules["dcmaster"] = dc; _spec.loader.exec_module(dc)

DB = Path(r"E:\MITAS\Database")
POLL_SEC = 60


def make_args():
    """db_compose_master argparse defaultları (master modu)."""
    return types.SimpleNamespace(
        mode="master", seg=None, hash_names=False, overwrite=True, flat_out=None,
        deinterlace=False, no_card_split=False, card_same_thr=6, card_min_hold=5,
        polarity="auto", no_dedup=False, luma_key=False, text_only=False, debug=False,
        flip=False, tht=22, min_hold=5, cut_resp=0.05)


def _compose_seg(frames, args):
    """process_film 'master' dispatch replikası (slit kanonik + mosaic adayı + seçim)."""
    if not frames:
        return None, {"frames": 0}
    first = dc.first_readable(frames)
    if first is None:
        return None, {"frames": len(frames), "err": "no readable frame"}
    h, w = first.shape[:2]
    if args.deinterlace:
        h = dc.deinterlace(first).shape[0]
    p = dc.derive_params(h, w, args)
    runs = dc.split_runs(frames, p, args)
    s = sum(int(r[1]) - int(r[0]) + 1 for r in runs if r[2] == "S")
    r_ = sum(int(r[1]) - int(r[0]) + 1 for r in runs if r[2] == "R")
    scroll_frac = r_ / max(1, s + r_)
    slit_master, _, _ = dc.compose_slit(frames, p, args)
    mosaic_master = None
    if scroll_frac < 0.5:
        mosaic_master, _, _ = dc.compose_mosaic(frames, p, args)
    canon, mode = dc.select_master(slit_master, mosaic_master, scroll_frac, h)
    return canon, {"frames": len(frames), "mode": mode, "scroll_frac": round(scroll_frac, 3),
                   "size": ([int(canon.shape[1]), int(canon.shape[0])] if canon is not None else None)}


def gen_master(film: Path) -> dict:
    out = film / "master"
    out.mkdir(parents=True, exist_ok=True)
    args = make_args()
    res = {"film": film.name}
    for seg in ("giris", "cikis"):
        frames = sorted(glob.glob(str(film / "frames" / seg / "*.png")), key=dc.nat_sort_key)
        canon, info = _compose_seg(frames, args)
        if canon is not None:
            dc.wr(out / f"{seg}.png", canon)
            info["path"] = str(out / f"{seg}.png")
        res[seg] = info
    (out / "master_manifest.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def _has_frames(film: Path) -> bool:
    return bool(glob.glob(str(film / "frames" / "giris" / "*.png")) or
               glob.glob(str(film / "frames" / "cikis" / "*.png")))


def _ready(film: Path) -> bool:
    # kareler var + işleme ilerlemiş (ocr veya pdf çıktısı) -> kareler artık final
    return _has_frames(film) and ((film / "ocr").exists() or (film / "pdf").exists())


def _done(film: Path) -> bool:
    return (film / "master" / "giris.png").exists() or (film / "master" / "cikis.png").exists()


def monitor():
    print(f"[master-monitor] başladı, {DB} izleniyor (poll {POLL_SEC}s). Ctrl-C ile dur.", flush=True)
    seen = set()
    while True:
        for film in sorted(DB.iterdir()):
            if not film.is_dir() or film.name in seen:
                continue
            if _done(film):
                seen.add(film.name)
                continue
            if _ready(film):
                try:
                    r = gen_master(film)
                    seen.add(film.name)
                    sz = {k: r[k].get("size") for k in ("giris", "cikis") if isinstance(r.get(k), dict)}
                    print(f"[master] OK {film.name} -> {sz}", flush=True)
                except Exception as e:
                    print(f"[master] HATA {film.name}: {repr(e)[:140]}", flush=True)
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(sys.argv) > 2 and sys.argv[1] == "--once":
        # arg: tam yol VEYA Database altindaki klasor adi (pipeline tam clip_dir yolu gecer)
        _arg = sys.argv[2]
        _film = Path(_arg) if os.path.isabs(_arg) else (DB / _arg)
        print(json.dumps(gen_master(_film), ensure_ascii=False, indent=1))
    else:
        monitor()
