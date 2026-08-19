# -*- coding: utf-8 -*-
"""PROTOTİP (Çağatay fikri 2026-06-29): GİRİŞ master'ı CROP-STACK ile.
Optimize edildi: ROI 1 kere hesaplanıyor, Temsilci kare keskinliğe göre seçiliyor.
"""
import sys, os
from pathlib import Path
_PROJE_KOK = Path(os.environ.get("MITAS_PROJECT_ROOT") or "/opt/mitas")
sys.path.insert(0, str(_PROJE_KOK)); sys.path.insert(0, str(_PROJE_KOK / "scripts"))
os.environ.setdefault("JENERIK_PADDLE_FAST_NO_DOC", "1")
sys.stdout.reconfigure(encoding="utf-8")
import cv2, numpy as np
from core.pipelines.ocr.jenerik_detector import is_credit_text_line
from core.pipelines.ocr.jenerik_frame_pool_detector import imread_unicode, list_images, natural_frame_no
from core.pipelines.ocr.jenerik_oneocr_detector import oneocr_line_boxes
from _pipe_ocr import build_engine, fold

DB = _PROJE_KOK / "Database"
SUB_FRAC = float(os.environ.get("MITAS_GIRIS_SUB_FRAC", "0.82"))
ROW_H = int(os.environ.get("PROTO_ROW_H", "48"))
CW = int(os.environ.get("PROTO_W", "780"))
GAP = 10
PAD = 5

from difflib import SequenceMatcher

MIN_CONF = float(os.environ.get("PROTO_MIN_CONF", "0.55"))
FUZZY = float(os.environ.get("PROTO_FUZZY", "0.82"))
MAX_ROWS = int(os.environ.get("PROTO_MAX_ROWS", "0") or 0)

def _is_credit_text(t: str) -> bool:
    if is_credit_text_line(t):
        return True
    s = (t or "").strip()
    if s.endswith(".") and 2 <= len(s.split()) <= 3:
        return is_credit_text_line(s.rstrip(". "))
    return False

def _line_boxes_conf(eng, bgr):
    from PIL import Image
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    try:
        res = eng.recognize_pil(Image.fromarray(rgb))
    except Exception:
        return []
    out = []
    for ln in (res.get("lines") or []):
        t = (ln.get("text") or "").strip()
        if not t:
            continue
        br = ln.get("bounding_rect") or {}
        xs = [br[k] for k in ("x1", "x2", "x3", "x4") if br.get(k) is not None]
        ys = [br[k] for k in ("y1", "y2", "y3", "y4") if br.get(k) is not None]
        if not xs or not ys:
            continue
        box = (int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys)))
        cs = [w.get("confidence") for w in (ln.get("words") or [])
              if isinstance(w, dict) and w.get("confidence") is not None]
        if not cs:
            line_conf = ln.get("confidence") or ln.get("score") or ln.get("conf") or 0.85
            cs = [float(line_conf)]
        conf = (sum(cs) / len(cs)) if cs else 0.0
        out.append((box, t, conf))
    return out

from _letterbox_roi import letterbox_roi_from_paths

def build(src_dir: Path, out_png: Path) -> dict:
    eng, kind, err = build_engine()
    if eng is None:
        return {"status": "engine_error", "error": err}
    paths = list_images(src_dir)
    cands = []
    order = 0

    # --- ROI (LETTERBOX): FİLM GENELİNDEN 10 KARE ÖRNEKLENEREK 1 KEZ ---
    # Eskiden ilk kareden hesaplanıyordu; havuz scriptindeki ikizi 102 filmi bozdu
    # (kök vaka notu: scripts/_letterbox_roi.py). Şüphede tam kareye düşer.
    roi_y_min, roi_y_max, _roi_kaynak = letterbox_roi_from_paths(paths, imread_unicode)
    if roi_y_max <= roi_y_min:
        roi_y_min, roi_y_max = 0, 720
    active_H = max(1, roi_y_max - roi_y_min)
    # ---------------------------------------------------------

    for p in paths:
        bgr = imread_unicode(str(p))
        if bgr is None: continue
        H, Wd = bgr.shape[:2]
        
        y_min, y_max = roi_y_min, roi_y_max
        
        for box, text, conf in _line_boxes_conf(eng, bgr):
            x0, y0, x1, y1 = box
            yc = (((y0 + y1) / 2.0) - y_min) / active_H
            if yc >= SUB_FRAC: continue
            if not _is_credit_text(text): continue
            if conf < MIN_CONF: continue
            
            key = fold(text)
            if not key or len(key) < 2: continue
            
            xa, ya = max(0, x0 - PAD), max(0, y0 - PAD)
            xb, yb = min(Wd, x1 + PAD), min(H, y1 + PAD)
            if xb - xa < 8 or yb - ya < 8: continue
            
            cands.append((order, bgr[ya:yb, xa:xb], text, conf, key))
            order += 1

    n = len(cands)
    parent = list(range(n))
    def _find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    keys = [c[4] for c in cands]
    for i in range(n):
        li = len(keys[i])
        ri = _find(i)
        for j in range(i + 1, n):
            lj = len(keys[j])
            if min(li, lj) < 0.6 * max(li, lj): continue
            if _find(j) == ri: continue
            if SequenceMatcher(None, keys[i], keys[j]).ratio() >= FUZZY:
                parent[_find(j)] = ri
                
    from collections import defaultdict
    _members = defaultdict(list)
    for idx, c in enumerate(cands):
        _members[_find(idx)].append(c)
        
    clusters = []
    for ms in _members.values():
        def _skor(c):
            conf = c[3]
            try:
                gray = cv2.cvtColor(c[1], cv2.COLOR_BGR2GRAY)
                lap_var = float(cv2.Laplacian(gray, cv2.CV_32F).var())
            except Exception:
                lap_var = 0.0
            return conf * (lap_var + 1e-6)
            
        best = max(ms, key=_skor)
        clusters.append({"rep_key": best[4], "best": (best[0], best[1], best[2], best[3]),
                         "first": min(c[0] for c in ms)})

    clusters.sort(key=lambda cl: cl["first"])
    
    keys = [cl["rep_key"] for cl in clusters]
    drop = set()
    for i, ki in enumerate(keys):
        if len(ki) < 3: continue
        for j, kj in enumerate(keys):
            if i != j and 0.6 * len(kj) <= len(ki) < len(kj) and ki in kj:
                drop.add(i)
                break
    clusters = [cl for i, cl in enumerate(clusters) if i not in drop]
    
    flood = False
    if MAX_ROWS > 0 and len(clusters) > MAX_ROWS:
        flood = True
        clusters = sorted(clusters, key=lambda cl: -cl["best"][3])[:MAX_ROWS]
        clusters.sort(key=lambda cl: cl["first"])
        
    rows = [(cl["best"][1], cl["best"][2]) for cl in clusters]
    if not rows:
        return {"status": "empty", "lines": 0}

    scaled = []
    for c, t in rows:
        h, w = c.shape[:2]
        nw = max(1, int(round(w * ROW_H / h)))
        nw = min(nw, CW - 20)
        scaled.append(cv2.resize(c, (nw, ROW_H), interpolation=cv2.INTER_AREA))
        
    Hc = GAP + sum(ROW_H + GAP for _ in scaled)
    canvas = np.zeros((Hc, CW, 3), np.uint8)
    y = GAP
    for s in scaled:
        canvas[y:y + ROW_H, 12:12 + s.shape[1]] = s
        y += ROW_H + GAP
        
    out_png.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".png", canvas)
    if ok:
        buf.tofile(str(out_png))
    return {"status": "ok", "lines": len(rows), "flood": flood, "size": [CW, Hc], "out": str(out_png),
            "texts": [t for _, t in rows]}

def main():
    name = sys.argv[1]
    src = (DB / name / "frames" / "giris_jenerik")
    if not src.is_dir() or not list_images(src):
        src = DB / name / "frames" / "giris"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else (DB / name / f"_PROTO_giris_cropstack.png")
    import json
    print(json.dumps(build(src, out), ensure_ascii=False))


if __name__ == "__main__":
    main()
