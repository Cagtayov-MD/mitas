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

# GİRİŞ master motoru: crop-stack (Çağatay fikri 2026-06-29) — her kredi satırını kırp+alt alta diz,
# footage'sız temiz künye listesi. ÇIKIŞ slit-scan kalır. Yüklenemezse giriş eski slit'e düşer.
try:
    sys.path.insert(0, r"E:\MITAS\scripts")
    _cs_spec = importlib.util.spec_from_file_location("giris_cropstack", r"E:\MITAS\scripts\giris_master_cropstack.py")
    cs = importlib.util.module_from_spec(_cs_spec); sys.modules["giris_cropstack"] = cs
    _cs_spec.loader.exec_module(cs)
except Exception:
    cs = None

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


def _textset_from_manifest(manifest: Path, raw: Path):
    """Azaltılmış havuz manifestinden TAM yazı-setini (kept kareler) ham frames/<seg>'ten derle.
    Slit-scan master YOĞUNLUK ister; azaltılmış set master'ı eksik üretir."""
    try:
        mj = json.loads(manifest.read_text(encoding="utf-8"))
        kept = [r.get("file") for r in (mj.get("frames") or [])
                if str(r.get("decision", "")).startswith("kept")]
        fs = [str(raw / f) for f in kept if f and (raw / f).exists()]
        return sorted(fs, key=dc.nat_sort_key) if fs else None
    except Exception:
        return None


def _seg_source(film: Path, seg: str):
    """(frames_listesi, kaynak_etiketi). Master kaynak seçimi (Çağatay 2026-06-29).

    YALNIZ derlenmiş jenerik havuzundan üret: giris_jenerik azaltılmış+manifestli → TAM yazı-seti
    (giris_textset); cikis_jenerik bütün-pencere+manifestsiz → doğrudan. Havuz BOŞ/yok → BOŞ liste
    (master ÜRETİLMEZ = "kötü master yerine hiç"). Ham frames'e VE çıkış-yedek havuzuna (cikis_yazi)
    DÜŞÜLMEZ: ham=footage-master, cikis_yazi=çıkış-sonu sahne-yazısı/epilog → ikisi de SAHTE master üretir
    (GLENN MILLER tabela / SOĞUK SUYA 'FIN' kanıtı, 2026-06-29). cikis_yazi yedek havuzu yalnız VL içindir."""
    raw = film / "frames" / seg
    pool = film / "frames" / f"{seg}_jenerik"
    pool_fs = sorted(glob.glob(str(pool / "*.png")), key=dc.nat_sort_key) if pool.is_dir() else []
    if not pool_fs:
        return [], seg
    man = film / "frames" / f"{seg}_jenerik_manifest.json"
    if man.exists() and raw.is_dir():
        ts = _textset_from_manifest(man, raw)
        if ts:
            return ts, f"{seg}_textset"
    return pool_fs, f"{seg}_jenerik"


def gen_master(film: Path, base_override: str | None = None) -> dict:
    base = _delivery_base(film, base_override)
    args = make_args()
    res = {"film": film.name, "base": base}
    produced = False

    # GİRİŞ: CROP-STACK (footage'sız temiz künye listesi). Kaynak: giris_jenerik (azaltılmış yazı-kareleri),
    # yoksa ham frames/giris. Boşsa giriş master YOK. cs yüklenemediyse eski slit'e düş.
    giris_out = film / f"{base} giris.png"
    if cs is not None:
        gsrc = film / "frames" / "giris_jenerik"
        if not (gsrc.is_dir() and glob.glob(str(gsrc / "*.png"))):
            gsrc = film / "frames" / "giris"
        ginfo = {"source": "giris_cropstack", "status": "no_frames"}
        if gsrc.is_dir() and glob.glob(str(gsrc / "*.png")):
            try:
                r = cs.build(gsrc, giris_out)
                ginfo = {"source": "giris_cropstack", "status": r.get("status"),
                         "lines": r.get("lines"), "size": r.get("size")}
                if r.get("status") == "ok":
                    ginfo["path"] = str(giris_out)
                    produced = True
            except Exception as e:  # noqa: BLE001
                ginfo = {"source": "giris_cropstack", "status": "error", "error": f"{type(e).__name__}: {e}"}
        res["giris"] = ginfo
    else:
        frames, src = _seg_source(film, "giris")
        canon, info = _compose_seg(frames, args)
        info["source"] = src
        if canon is not None:
            dc.wr(giris_out, canon); info["path"] = str(giris_out); produced = True
        res["giris"] = info

    # ÇIKIŞ: slit-scan (mevcut, GOOD — DOKUNULMADI).
    frames, src = _seg_source(film, "cikis")
    canon, info = _compose_seg(frames, args)
    info["source"] = src
    if canon is not None:
        cout = film / f"{base} cikis.png"
        dc.wr(cout, canon)
        info["path"] = str(cout)
        produced = True
    res["cikis"] = info
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
