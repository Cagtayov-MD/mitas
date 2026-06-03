"""
Jeneriği tek PNG'ye birleştir (paddle text-mask + overlap stitch).

Kullanim:
    # Onerilen: paddle-destekli, yazi-eslemeli
    venvs/ocr/Scripts/python.exe scripts/jenerik_tek_png.py \
        --src <frames_klasoru_VEYA_video.mp4> \
        --out output.png \
        --paddle

    # paddle olmadan fallback (text-mask = morfolojik tophat)
    python scripts/jenerik_tek_png.py --src ... --out ...

Mantik (--paddle):
  1) Her kare icin Paddle text-detection -> dt_polys (yazi kutulari).
     Sonuc <out_yan_klasoru>/_paddle_boxes_cache.json icinde cache'lenir.
  2) Her kareden 'text-only gri' uretilir: kutu disi mid-gray (128),
     kutu ici orijinal gri. Arka plan / hareketli sahne NCC sinyaline girmez.
  3) Overlap stitch: canvas'in altinda kalan son seridi (text-only) yeni karede
     template-match ile bul -> sadece eslesmenin altinda kalan YENI satirlari
     PNG'ye ekle. Cikti gercek karelerin (BGR) birlesimi.
  4) Eslesme bulunamayan kareler 'kart kesimi' kabul edilir, pHash dedup ile
     ayni kart tekrarlamadan tam frame eklenir.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, sys, time
from pathlib import Path
import numpy as np
import cv2


# ----------------------------- frame yukleme -----------------------------

def _read_bgr(path: Path) -> np.ndarray | None:
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)


def list_frame_paths(d: Path) -> list[Path]:
    files = [p for p in d.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}]
    def key(p: Path):
        m = re.findall(r"\d+", p.stem)
        return (int(m[-1]) if m else 0, p.name)
    files.sort(key=key)
    return files


def extract_frames_from_video(path: Path, fps: float, dst: Path) -> list[Path]:
    dst.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(path))
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, int(round(src_fps / fps)))
    paths: list[Path] = []
    i, j = 0, 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        if i % step == 0:
            p = dst / f"frame_{j:06d}.png"
            cv2.imencode(".png", fr)[1].tofile(str(p))
            paths.append(p)
            j += 1
        i += 1
    cap.release()
    return paths


# ----------------------------- yardimcilar -----------------------------

def phash(img: np.ndarray, size: int = 16) -> int:
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, (size, size), interpolation=cv2.INTER_AREA)
    med = np.median(g)
    bits = (g > med).flatten()
    out = 0
    for b in bits:
        out = (out << 1) | int(b)
    return out


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


# ----------------------------- paddle text boxes -----------------------------

_PADDLE = None

def _paddle_engine():
    global _PADDLE
    if _PADDLE is not None:
        return _PADDLE
    os.environ.setdefault("FLAGS_json_format_model", "0")
    os.environ.setdefault("FLAGS_enable_pir_api", "0")
    from paddleocr import PaddleOCR
    det_dir = os.environ.get("MITAS_PADDLEOCR_TEXT_DET_MODEL_DIR") or None
    rec_dir = os.environ.get("MITAS_PADDLEOCR_TEXT_REC_MODEL_DIR") or None
    det_name = os.environ.get("MITAS_PADDLEOCR_TEXT_DET_MODEL_NAME") or "PP-OCRv5_mobile_det"
    rec_name = os.environ.get("MITAS_PADDLEOCR_TEXT_REC_MODEL_NAME") or "PP-OCRv5_mobile_rec"
    _PADDLE = PaddleOCR(
        text_detection_model_name=det_name,
        text_detection_model_dir=det_dir,
        text_recognition_model_name=rec_name,
        text_recognition_model_dir=rec_dir,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        enable_mkldnn=False,
    )
    return _PADDLE


def paddle_text_lines(img_path: Path) -> list[dict]:
    """Kareye Paddle uygula -> [{text, poly[4x2 int]}, ...] (taninan metin + kutusu)."""
    eng = _paddle_engine()
    raw = eng.predict(str(img_path)) if hasattr(eng, "predict") else eng.ocr(str(img_path), cls=False)
    out: list[dict] = []

    def push(poly, text):
        if not text:
            return
        a = np.asarray(poly, dtype=np.float32).reshape(-1, 2)
        if a.shape[0] < 3:
            return
        out.append({"text": str(text), "poly": a.astype(np.int32).tolist()})

    def walk(node):
        if node is None:
            return
        if isinstance(node, dict):
            polys = node.get("dt_polys") or node.get("rec_polys") or node.get("boxes")
            texts = node.get("rec_texts") or node.get("texts")
            if polys is not None and texts is not None:
                for poly, text in zip(polys, texts):
                    push(poly, text)
                return
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            if (len(node) == 2 and isinstance(node[1], (tuple, list))
                    and len(node[1]) >= 1 and isinstance(node[1][0], str)):
                push(node[0], node[1][0])
            else:
                for v in node:
                    walk(v)

    walk(raw)
    return out


def file_sig(p: Path) -> str:
    st = p.stat()
    return f"{p.name}:{st.st_size}:{int(st.st_mtime)}"


def detect_or_load_cache(paths: list[Path], cache_file: Path) -> dict[str, list[dict]]:
    cache: dict[str, list[dict]] = {}
    if cache_file.exists():
        try:
            raw = json.loads(cache_file.read_text(encoding="utf-8"))
            for k, v in raw.items():
                # eski format (sadece poly listesi) -> kullanima uygunsa atla
                if v and isinstance(v[0], dict) and "text" in v[0]:
                    cache[k] = v
        except Exception:
            cache = {}
    t0 = time.time()
    new = 0
    for i, p in enumerate(paths, 1):
        sig = file_sig(p)
        if sig in cache:
            continue
        cache[sig] = paddle_text_lines(p)
        new += 1
        if new % 20 == 0:
            dt = time.time() - t0
            print(f"  paddle {i}/{len(paths)}  (yeni={new}, gecen={dt:.1f}s)")
    if new:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    print(f"[+] paddle hazir: toplam {len(cache)} kareli cache  (yeni={new})")
    return cache


# ----------------------------- text-only goruntu -----------------------------

def text_only_gray(img: np.ndarray, lines: list[dict], fill: int = 128) -> np.ndarray:
    """Kutu disinda mid-gray, ici orijinal gri. NCC arka plani 'gormez'."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    out = np.full_like(g, fill)
    if not lines:
        return out
    mask = np.zeros_like(g)
    for ln in lines:
        cv2.fillPoly(mask, [np.asarray(ln["poly"], dtype=np.int32)], 255)
    out[mask > 0] = g[mask > 0]
    return out


# ----------------------------- satir bazli dedup -----------------------------

import re as _re
_NORM = _re.compile(r"[^a-z0-9çğıöşü]+")

def norm_line(t: str) -> str:
    t = t.lower().replace("â", "a").replace("é", "e").replace("è", "e").replace("ê", "e")
    t = t.replace("ô", "o").replace("ï", "i").replace("ü", "u").replace("ö", "o")
    return _NORM.sub("", t)


import difflib

def _match_lines(a: str, b: str, ratio_thr: float = 0.88, sub_min: int = 5) -> bool:
    """Iki normalize string ayni satirin OCR varyanti mi?"""
    if not a or not b:
        return False
    if a == b:
        return True
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    if len(short) >= sub_min and short in long:
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= ratio_thr


def stitch_text_dedup(frames: list[np.ndarray], lines_per_frame: list[list[dict]],
                      pad: int = 6, min_text_len: int = 5) -> tuple[np.ndarray, list[str]]:
    """Satir-bazli dedup:
      1) Tum karelerden satirlar toplanir. Her satir normalize edilir.
      2) Fuzzy-match (substring + difflib) ile kumeler olusur.
      3) Her kume icin en uzun normalize -> kanonik (en temiz okuma).
      4) Kumeler ilk gorulme sirasinda (frame_idx, y0) diziilir.
      5) Her kume icin kanonik satirin bulundugu frame'den y bandi crop'lanir.
    """
    W = max(f.shape[1] for f in frames)
    clusters: list[dict] = []

    for fi, (fr, lines) in enumerate(zip(frames, lines_per_frame)):
        if fr.shape[1] != W:
            new_h = int(fr.shape[0] * W / fr.shape[1])
            fr = cv2.resize(fr, (W, new_h))
        Hf = fr.shape[0]

        for ln in lines:
            text = ln["text"]
            n = norm_line(text)
            if len(n) < min_text_len:
                continue
            ys = [p[1] for p in ln["poly"]]
            y0 = max(0, min(ys) - pad)
            y1 = min(Hf, max(ys) + pad)
            if y1 <= y0:
                continue

            matched = None
            for c in clusters:
                if _match_lines(n, c["canon"]):
                    matched = c
                    break

            if matched is None:
                clusters.append({
                    "canon": n,
                    "canon_text": text,
                    "first_fi": fi, "first_y0": y0,
                    "best_fi": fi, "best_y0": y0, "best_y1": y1,
                    "best_len": len(n),
                })
            else:
                # en uzun normalize -> kanonik kabul, kirpma kaynagi olarak kullan
                if len(n) > matched["best_len"]:
                    matched["canon"] = n
                    matched["canon_text"] = text
                    matched["best_fi"] = fi
                    matched["best_y0"] = y0
                    matched["best_y1"] = y1
                    matched["best_len"] = len(n)

    if not clusters:
        return frames[0], []

    clusters.sort(key=lambda c: (c["first_fi"], c["first_y0"]))

    parts: list[np.ndarray] = []
    texts_out: list[str] = []
    for c in clusters:
        fr = frames[c["best_fi"]]
        if fr.shape[1] != W:
            new_h = int(fr.shape[0] * W / fr.shape[1])
            fr = cv2.resize(fr, (W, new_h))
        crop = fr[c["best_y0"]:c["best_y1"], :, :]
        if crop.size == 0:
            continue
        if crop.shape[1] < W:
            crop = cv2.copyMakeBorder(crop, 0, 0, 0, W - crop.shape[1],
                                      cv2.BORDER_CONSTANT, value=(0, 0, 0))
        parts.append(crop)
        texts_out.append(c["canon_text"])

    if not parts:
        return frames[0], []
    return np.vstack(parts), texts_out


def fallback_text_mask(img: np.ndarray) -> np.ndarray:
    """Paddle yoksa: tophat + blackhat ile harf strokelarini cikar."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    th_white = cv2.morphologyEx(g, cv2.MORPH_TOPHAT, k)
    th_black = cv2.morphologyEx(g, cv2.MORPH_BLACKHAT, k)
    th = cv2.max(th_white, th_black)
    bw = cv2.threshold(th, 18, 255, cv2.THRESH_BINARY)[1]
    bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN,
                          cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)))
    # NCC icin 0/128/255 yerine 128 zemin + 255 yazi
    out = np.full_like(g, 128)
    out[bw > 0] = 255
    return out


# ----------------------------- overlap stitch -----------------------------

def stitch_overlap(frames: list[np.ndarray], signals: list[np.ndarray],
                   tail_h: int = 120, match_thr: float = 0.55) -> np.ndarray:
    H, W = frames[0].shape[:2]
    canvas = frames[0].copy()
    canvas_sig = signals[0].copy()
    last_full_hashes: list[int] = [phash(frames[0])]

    for idx, (fr, sig) in enumerate(zip(frames[1:], signals[1:]), start=1):
        if fr.shape[1] != W:
            new_h = int(fr.shape[0] * W / fr.shape[1])
            fr = cv2.resize(fr, (W, new_h))
            sig = cv2.resize(sig, (W, new_h))
        Hf = fr.shape[0]

        th = min(tail_h, canvas_sig.shape[0], Hf - 1)
        tail_sig = canvas_sig[-th:, :]
        # Eslesme icin yeterli text var mi? (boş zemin)
        tail_has_text = (tail_sig != 128).sum() > 30
        fr_has_text   = (sig      != 128).sum() > 30

        if not fr_has_text:
            # yeni karede yazi yok (siyah/fade/manzara) -> es gec
            continue
        if not tail_has_text:
            # canvas dibi yazisizsa (gecis bolgesi) yeni kareyi tam ekle ama dedup'la
            h = phash(fr)
            if any(hamming(h, k) < 20 for k in last_full_hashes):
                continue
            last_full_hashes.append(h)
            canvas = np.vstack([canvas, fr])
            canvas_sig = np.vstack([canvas_sig, sig])
            continue

        res = cv2.matchTemplate(sig, tail_sig, cv2.TM_CCOEFF_NORMED)
        _, mv, _, ml = cv2.minMaxLoc(res)
        my = ml[1]

        if mv >= match_thr:
            new_start = my + th
            if new_start < Hf:
                canvas = np.vstack([canvas, fr[new_start:, :, :]])
                canvas_sig = np.vstack([canvas_sig, sig[new_start:, :]])
            # else: ortusme tam dipte, yeni icerik yok -> skip
        else:
            h = phash(fr)
            if any(hamming(h, k) < 20 for k in last_full_hashes):
                continue
            last_full_hashes.append(h)
            canvas = np.vstack([canvas, fr])
            canvas_sig = np.vstack([canvas_sig, sig])
    return canvas


# ----------------------------- main -----------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="frames klasoru veya video dosyasi")
    ap.add_argument("--out", required=True, help="cikti PNG yolu")
    ap.add_argument("--fps", type=float, default=1.0, help="video icin ornekleme fps")
    ap.add_argument("--paddle", action="store_true",
                    help="yazi maskesini Paddle text-detection ile cikar (onerilen)")
    ap.add_argument("--dedup", choices=["overlap", "text"], default="text",
                    help="text: paddle taninan satirlari benzersiz dedup (onerilen); "
                         "overlap: template-match overlap stitch")
    ap.add_argument("--write-txt", action="store_true",
                    help="text dedup modunda yaninda .txt da yaz")
    ap.add_argument("--cache", default=None,
                    help="paddle box cache JSON (default: out yaninda _paddle_boxes_cache.json)")
    ap.add_argument("--tail", type=int, default=120)
    ap.add_argument("--match-thr", type=float, default=0.55)
    ap.add_argument("--max-width", type=int, default=0)
    args = ap.parse_args()

    src = Path(args.src)
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)

    if src.is_dir():
        paths = list_frame_paths(src)
    else:
        tmp = out.parent / "_video_frames_tmp"
        paths = extract_frames_from_video(src, args.fps, tmp)
    if not paths:
        print("kare bulunamadi", file=sys.stderr); sys.exit(2)
    print(f"[+] {len(paths)} kare")

    frames = [_read_bgr(p) for p in paths]
    frames = [f for f in frames if f is not None]
    if not frames:
        print("kare okunamadi", file=sys.stderr); sys.exit(2)

    if args.paddle:
        cache_file = Path(args.cache) if args.cache else (out.parent / "_paddle_boxes_cache.json")
        cache = detect_or_load_cache(paths, cache_file)
        lines_per_frame = [cache.get(file_sig(p), []) for p in paths]
    else:
        if args.dedup == "text":
            print("[X] dedup=text icin --paddle gerekli", file=sys.stderr); sys.exit(2)
        lines_per_frame = [[] for _ in paths]

    if args.dedup == "text":
        canvas = stitch_text_dedup(frames, lines_per_frame)
        if args.write_txt:
            seen, ordered = set(), []
            for lns in lines_per_frame:
                for ln in lns:
                    k = norm_line(ln["text"])
                    if len(k) < 2 or k in seen:
                        continue
                    seen.add(k); ordered.append(ln["text"])
            txt_path = out.with_suffix(".txt")
            txt_path.write_text("\n".join(ordered), encoding="utf-8")
            print(f"[+] txt: {txt_path}  ({len(ordered)} satir)")
    else:
        if args.paddle:
            signals = [text_only_gray(img, lns) for img, lns in zip(frames, lines_per_frame)]
        else:
            print("[!] paddle yok, fallback (tophat) maske kullaniliyor")
            signals = [fallback_text_mask(img) for img in frames]
        canvas = stitch_overlap(frames, signals, tail_h=args.tail, match_thr=args.match_thr)

    if args.max_width and canvas.shape[1] > args.max_width:
        scale = args.max_width / canvas.shape[1]
        canvas = cv2.resize(canvas, (args.max_width, int(canvas.shape[0] * scale)),
                            interpolation=cv2.INTER_AREA)

    ok, buf = cv2.imencode(".png", canvas)
    if not ok:
        print("PNG encode hatasi", file=sys.stderr); sys.exit(3)
    buf.tofile(str(out))
    print(f"[OK] yazildi: {out}  ({canvas.shape[1]}x{canvas.shape[0]})")


if __name__ == "__main__":
    main()
