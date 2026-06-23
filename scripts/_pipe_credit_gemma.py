# -*- coding: utf-8 -*-
"""Paralel gemma kunye-okuma — OCR'in URETTIGI frame havuzunu kullanir, AYRI cikti.

gemma4:26b (tum kareler, CLIP-bekci YOK, siki "kamera-OCR" prompt = halusinasyon yok)
-> YONETMEN + 8 OYUNCU. PDF YOK. Production OCR/PDF akisina DOKUNMAZ (yan-cikti).
Cikti: <out> dosyasi (OCR-PDF ile karsilastirma icin Database/<film>/ altinda).

  python _pipe_credit_gemma.py --film-dir "<Database/<film>>" --out "<...GEMMA.txt>"
"""
import sys, os, glob, json, time, argparse, importlib.util
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

_VP = importlib.util.spec_from_file_location("vlmpipe", r"E:\MITAS\OCR-worktree\_vlm_pipeline.py")
vp = importlib.util.module_from_spec(_VP); sys.modules["vlmpipe"] = vp; _VP.loader.exec_module(vp)

PER_SEG = int(os.environ.get("MITAS_GEMMA_PARALLEL_PERSEG", "30") or 30)   # dense-fallback: segment basina ornek
BS = int(os.environ.get("MITAS_GEMMA_PARALLEL_BS", "6") or 6)              # gemma batch (kucuk: timeout onler)

# --- METIN-MASKELI DEDUP: hareketli arka-plani yok say, her distinct yazi-karti 1 temsilci ---
import cv2 as _cv2, types as _types
_DC = importlib.util.spec_from_file_location("dcmaster", r"E:\MITAS\OCR-worktree\db_compose_master.py")
_dc = importlib.util.module_from_spec(_DC); sys.modules["dcmaster"] = _dc; _DC.loader.exec_module(_dc)
_DC_ARGS = _types.SimpleNamespace(tht=22, min_hold=5, polarity="auto")
DEDUP_TH = int(os.environ.get("MITAS_GEMMA_DEDUP_TH", "8") or 8)        # metin-hash Hamming farki > bu -> yeni kart
DEDUP_CAP = int(os.environ.get("MITAS_GEMMA_DEDUP_CAP", "120") or 120)  # guvenlik tavani (patolojik filmde sismesin)


def _text_hash(img):
    gray = _cv2.cvtColor(img, _cv2.COLOR_BGR2GRAY)
    p = _dc.derive_params(gray.shape[0], gray.shape[1], _DC_ARGS)
    mask = _dc.text_mask(gray, p, "auto")   # yazi=beyaz, footage/arka-plan=silinir
    return _dc.dhash(_cv2.cvtColor(mask, _cv2.COLOR_GRAY2BGR))


def _dedup_text(frames, th=None):
    th = DEDUP_TH if th is None else th
    kept, last = [], None
    for f in frames:
        img = _dc.rd_cached(f)
        if img is None:
            continue
        try:
            h = _text_hash(img)
        except Exception:
            kept.append(f); continue       # hash patlarsa kareyi TUT (kaybetme)
        if last is None or _dc.hamming(h, last) > th:
            kept.append(f); last = h
    return kept


def _dense(arr, k):
    n = len(arr)
    return list(arr) if n <= k else [arr[int(i * n / k)] for i in range(k)]


def read_gemma(film_dir):
    g = sorted(glob.glob(os.path.join(film_dir, "frames", "giris", "*.png")))
    c = sorted(glob.glob(os.path.join(film_dir, "frames", "cikis", "*.png")))
    # metin-maskeli dedup: her distinct yazi-karti 1 temsilci (israf yok, kart kacmaz)
    sel = _dedup_text(g) + _dedup_text(c)
    if len(sel) < 6:                       # dedup cok az tuttu (text_mask zayif/footage) -> dense'e dus
        sel = _dense(g, PER_SEG) + _dense(c, PER_SEG)
    elif len(sel) > DEDUP_CAP:             # guvenlik tavani
        sel = _dense(sel, DEDUP_CAP)
    res = {"nframes": len(g) + len(c), "nsel": len(sel), "yonetmen": [], "oyuncular": []}
    if not sel:
        res["status"] = "no_frames"
        return res
    batches = [sel[i:i + BS] for i in range(0, len(sel), BS)]
    results = []
    for b in batches:
        try:
            results.append(vp.gemma_call(b))
        except Exception:  # bir batch patlasa digerleri devam
            results.append({})
    merged = vp.merge(results)
    cast = merged["oyuncular"]
    # yonetmen: oyuncularda OLMAYAN (gemma bazen oyuncuyu yon-slotuna da koyar) -> temizle
    cast_f = {vp.cp.fold(x) for x in cast}
    yon = [y for y in merged["yonetmen"] if vp.cp.fold(y) not in cast_f] or list(merged["yonetmen"])
    res.update({"status": "ok", "yonetmen": yon, "oyuncular": cast[:8]})
    return res


def write_out(res, out_path):
    L = ["=== GEMMA OKUMA (gemma4:26b · tum kareler · OCR-disi paralel) ==="]
    L.append("YONETMEN: " + (", ".join(res["yonetmen"]) if res["yonetmen"] else "-"))
    L.append("")
    L.append("OYUNCULAR (8):")
    for i, a in enumerate(res["oyuncular"], 1):
        L.append(f"  {i}. {a}")
    if not res["oyuncular"]:
        L.append("  -")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    open(out_path, "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--film-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    t = time.time()
    try:
        res = read_gemma(args.film_dir)
    except Exception as e:
        res = {"status": "error", "err": repr(e)[:200], "yonetmen": [], "oyuncular": []}
    res["sec"] = round(time.time() - t, 1)
    write_out(res, args.out)
    print(json.dumps(res, ensure_ascii=False))
