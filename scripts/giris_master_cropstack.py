# -*- coding: utf-8 -*-
"""PROTOTİP (Çağatay fikri 2026-06-29): GİRİŞ master'ı CROP-STACK ile.
Her kredi satırını (OneOCR kutusu) kırp, benzersizleri ALT ALTA diz → footage'sız temiz master.
Girdi: frames/giris_jenerik (azaltılmış yazı-kareleri). Kayan jenerik (nadir) ayrı ele alınır.
Koşum: venvs/ocr/Scripts/python.exe scripts/_giris_master_cropstack.py "<film adı>" [out.png]
"""
import sys, os
from pathlib import Path
sys.path.insert(0, r"E:\MITAS"); sys.path.insert(0, r"E:\MITAS\scripts")
os.environ.setdefault("JENERIK_PADDLE_FAST_NO_DOC", "1")
sys.stdout.reconfigure(encoding="utf-8")
import cv2, numpy as np
from core.pipelines.ocr.jenerik_detector import is_credit_text_line
from core.pipelines.ocr.jenerik_frame_pool_detector import imread_unicode, list_images, natural_frame_no
from core.pipelines.ocr.jenerik_oneocr_detector import oneocr_line_boxes
from _pipe_ocr import build_engine, fold

DB = Path(r"E:\MITAS\Database")
SUB_FRAC = float(os.environ.get("MITAS_GIRIS_SUB_FRAC", "0.82"))
ROW_H = int(os.environ.get("PROTO_ROW_H", "48"))   # her satır yüksekliği (ölçek)
CW = int(os.environ.get("PROTO_W", "780"))          # kanvas genişliği
GAP = 10
PAD = 5


from difflib import SequenceMatcher

MIN_CONF = float(os.environ.get("PROTO_MIN_CONF", "0.55"))   # garble-fragment eşiği (ayarlandı: 0.55 temiz/eksiksiz denge)
FUZZY = float(os.environ.get("PROTO_FUZZY", "0.82"))          # aynı-satır birleştirme benzerlik


def _is_credit_text(t: str) -> bool:
    if is_credit_text_line(t):
        return True
    s = (t or "").strip()
    if s.endswith(".") and 2 <= len(s.split()) <= 3:
        return is_credit_text_line(s.rstrip(". "))
    return False


def _line_boxes_conf(eng, bgr):
    """(box, text, conf) — OneOCR satır kutusu + ortalama kelime güveni."""
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
        conf = (sum(cs) / len(cs)) if cs else 0.0
        out.append((box, t, conf))
    return out


def build(src_dir: Path, out_png: Path) -> dict:
    eng, kind, err = build_engine()
    if eng is None:
        return {"status": "engine_error", "error": err}
    paths = list_images(src_dir)
    cands = []   # (order, crop, text, conf, key)
    order = 0
    for p in paths:
        bgr = imread_unicode(str(p))
        if bgr is None:
            continue
        H, Wd = bgr.shape[:2]
        for box, text, conf in _line_boxes_conf(eng, bgr):
            x0, y0, x1, y1 = box
            yc = ((y0 + y1) / 2.0) / max(1, H)
            if yc >= SUB_FRAC:
                continue
            if not _is_credit_text(text):
                continue
            if conf < MIN_CONF:                    # garble/soluk satır — at
                continue
            key = fold(text)
            if not key or len(key) < 2:
                continue
            xa, ya = max(0, x0 - PAD), max(0, y0 - PAD)
            xb, yb = min(Wd, x1 + PAD), min(H, y1 + PAD)
            if xb - xa < 8 or yb - ya < 8:
                continue
            cands.append((order, bgr[ya:yb, xa:xb], text, conf, key))
            order += 1

    # FUZZY dedup: aynı satırın OCR-varyantlarını birleştir; küme başına EN GÜVENLİ örneği tut.
    clusters = []   # her küme: {rep_key, best:(order,crop,text,conf)}
    for o, crop, text, conf, key in cands:
        hit = None
        for cl in clusters:
            if SequenceMatcher(None, key, cl["rep_key"]).ratio() >= FUZZY:
                hit = cl
                break
        if hit is None:
            clusters.append({"rep_key": key, "best": (o, crop, text, conf), "first": o})
        else:
            if conf > hit["best"][3]:
                hit["best"] = (o, crop, text, conf)
            hit["first"] = min(hit["first"], o)

    clusters.sort(key=lambda cl: cl["first"])
    # ALT-DİZGE PARÇA temizliği: bir kümenin anahtarı daha UZUN bir kümenin alt-dizgesiyse (kelime-parçası) at.
    keys = [cl["rep_key"] for cl in clusters]
    drop = set()
    for i, ki in enumerate(keys):
        if len(ki) < 3:
            continue
        for j, kj in enumerate(keys):
            if i != j and len(ki) < len(kj) and ki in kj:
                drop.add(i)
                break
    clusters = [cl for i, cl in enumerate(clusters) if i not in drop]
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
    return {"status": "ok", "lines": len(rows), "size": [CW, Hc], "out": str(out_png),
            "texts": [t for _, t in rows]}


def main():
    name = sys.argv[1]
    src = (DB / name / "frames" / "giris_jenerik")
    if not src.is_dir() or not list_images(src):
        src = DB / name / "frames" / "giris"   # havuz yoksa ham
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else (DB / name / f"_PROTO_giris_cropstack.png")
    import json
    print(json.dumps(build(src, out), ensure_ascii=False))


if __name__ == "__main__":
    main()
