"""Master PNG monitör — production core'a DOKUNMAZ.
db_compose_master'ın compose fonksiyonlarını + 'master' dispatch'ini yeniden kullanır.

ÇIKTI (Çağatay 2026-06-29): master PNG'ler film KÖKÜNDE açıkta durur (alt-klasör YOK):
  Database/<film>/<TRT BAŞLIK> giris.png   ve   <TRT BAŞLIK> cikis.png
KAYNAK: derlenmiş havuz tercih edilir — frames/giris_jenerik & frames/cikis_jenerik;
havuz klasörü yoksa (eski film) ham frames/giris & frames/cikis'e düşer. Havuz VARSA ve BOŞSA
(cold-open / yazı yok) master ÜRETİLMEZ (ham footage'a düşmez). Yeni master üretildiyse eski
master/ alt-klasörü SİLİNİR; üretilemediyse eski master/ KORUNUR ("kötü master yerine hiç").

  Tek film:   python master_png_monitor.py --once "<Database klasör adı VEYA tam yol>" [--base "<TRT BAŞLIK>"]
  Monitör:    python master_png_monitor.py            (Database'i izler, biten filmlere üretir)
"""
import sys, os, time, glob, json, types, shutil, importlib.util
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
    """process_film 'master' dispatch replikası (slit kanonik + seçim)."""
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
    canon, mode = dc.select_master(slit_master)  # mosaic retired 2026-06-28 (slit-only)
    return canon, {"frames": len(frames), "mode": mode, "scroll_frac": round(scroll_frac, 3),
                   "size": ([int(canon.shape[1]), int(canon.shape[0])] if canon is not None else None)}


def _delivery_base(film: Path, base_override: str | None = None) -> str:
    """Kök teslim ad-tabanı '<TRT> <BAŞLIK>' (master PNG'ler bununla adlandırılır).
    Öncelik: açık --base > kök *.pdf stem > kök *.txt (teknik/_ hariç) stem > klasör adı."""
    if base_override:
        return base_override.strip()
    pdfs = sorted(film.glob("*.pdf"))
    if pdfs:
        return pdfs[0].stem
    txts = [t for t in sorted(film.glob("*.txt"))
            if not t.stem.endswith("_teknik") and not t.name.startswith("_")]
    if txts:
        return txts[0].stem
    return film.name


def _seg_source(film: Path, seg: str):
    """(frames_listesi, kaynak_etiketi). Master için kaynak seçimi.

    GİRİŞ havuzu (giris_jenerik) AZALTILMIŞ settir (yalnız temsilci, VL içindir). Slit-scan master
    YOĞUNLUK ister → azaltılmış set master'ı eksik üretir. Bu yüzden master için TAM yazı-setini
    manifestten (kept kareler) ham frames/<seg>'ten derle. (Çağatay 2026-06-29)
    Sıra: manifest-textset > havuz(frames/<seg>_jenerik) > ham frames/<seg>. Havuz var-ama-manifest
    yoksa havuzu kullan (cikis: cikis_jenerik bütün penceredir, manifesti yok → havuzdan)."""
    raw = film / "frames" / seg
    manifest = film / "frames" / f"{seg}_jenerik_manifest.json"
    if manifest.exists() and raw.is_dir():
        try:
            mj = json.loads(manifest.read_text(encoding="utf-8"))
            kept = [r.get("file") for r in (mj.get("frames") or [])
                    if str(r.get("decision", "")).startswith("kept")]
            fs = [str(raw / f) for f in kept if f and (raw / f).exists()]
            if fs:
                return sorted(fs, key=dc.nat_sort_key), f"{seg}_textset"
        except Exception:
            pass
    pool = film / "frames" / f"{seg}_jenerik"
    if pool.is_dir():
        fs = sorted(glob.glob(str(pool / "*.png")), key=dc.nat_sort_key)
        return fs, f"{seg}_jenerik"
    fs = sorted(glob.glob(str(raw / "*.png")), key=dc.nat_sort_key)
    return fs, seg


def gen_master(film: Path, base_override: str | None = None) -> dict:
    base = _delivery_base(film, base_override)
    args = make_args()
    res = {"film": film.name, "base": base}
    produced = False
    for seg in ("giris", "cikis"):
        frames, src = _seg_source(film, seg)
        canon, info = _compose_seg(frames, args)
        info["source"] = src
        if canon is not None:
            outp = film / f"{base} {seg}.png"
            dc.wr(outp, canon)
            info["path"] = str(outp)
            produced = True
        res[seg] = info
    res["produced"] = produced
    # provenance manifest (kökte, base adlı)
    try:
        (film / f"{base} master_manifest.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass
    # ESKİ master/ alt-klasörünü kaldır — YALNIZ yeni master üretildiyse ("kötü yerine hiç" korunur).
    if produced:
        old = film / "master"
        if old.is_dir():
            try:
                shutil.rmtree(old)
            except Exception:
                pass
    return res


def _has_frames(film: Path) -> bool:
    return bool(glob.glob(str(film / "frames" / "giris" / "*.png")) or
               glob.glob(str(film / "frames" / "cikis" / "*.png")))


def _ready(film: Path) -> bool:
    # kareler var + işleme ilerlemiş (ocr veya pdf çıktısı) -> kareler artık final
    return _has_frames(film) and ((film / "ocr").exists() or (film / "pdf").exists())


def _done(film: Path) -> bool:
    # kökte herhangi bir '<base> giris.png' / '<base> cikis.png' üretilmiş mi
    return bool(glob.glob(str(film / "* giris.png")) or glob.glob(str(film / "* cikis.png")))


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
        _base = None
        if "--base" in sys.argv:
            try:
                _base = sys.argv[sys.argv.index("--base") + 1]
            except Exception:
                _base = None
        print(json.dumps(gen_master(_film, _base), ensure_ascii=False, indent=1))
    else:
        monitor()
