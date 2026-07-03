# -*- coding: utf-8 -*-
"""master_dilim_oku.py — dilimlenmiş reading-master parçalarını OneOCR ile oku (K1 katmanı).

AMAÇ (Çağatay 2026-07-03 "master png hayata geçir"): master_png_dilimle.py'nin ürettiği
<film>/master_dilim/*_pNN.png parçaları OneOCR ile okunur → dilim_oneocr.txt (+ .jsonl).
Bu satırlar VL hayalet-kalkanı korpusuna ADDITIVE beslenebilir (manifest-korpus deseni):
reading-master run-aware ve kapsayıcı olduğundan ana-OCR'ın CLIP-seçiminde/stitch'te
kaçırdığı gerçek piksel-okumalarını taşır. OneOCR YEREL motor — ollama'ya bağımlı DEĞİL
(F:-disk/LLM kesintisinde bile çalışır).

Kullanım (venvs/ocr python'u ile):
  venvs\\ocr\\Scripts\\python.exe scripts/master_dilim_oku.py --clip "E:\\MITAS\\Database\\<film>"
  ... --all           (tüm Database; yalnız master_dilim'i olan filmler)
  ... --force         (mevcut dilim_oneocr.txt olsa da yeniden oku)

Çıktı: <film>/master_dilim/dilim_oneocr.txt   (fold'suz ham satırlar, kaynak-sınırı işaretli)
       <film>/master_dilim/dilim_oneocr.jsonl (satır-başına {part, text, y0,y1,x0,x1})
FAIL-SAFE: parça-başına try/except; motor açılamazsa tek satır JSON hata basar, dosya YAZMAZ.
Ana dosyalara/dilimlere DOKUNMAZ (salt-okur girdi, yalnız kendi çıktı dosyalarını yazar).
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path

DB_ROOT = Path(r"E:\MITAS\Database")
DILIM_DIRNAME = "master_dilim"
OUT_TXT = "dilim_oneocr.txt"
OUT_JSONL = "dilim_oneocr.jsonl"
# Kaynak-sınırı işaretçisi — _pipe_credit_vl._load_raw_ocr tüketirken parça/dosya sınırında
# yapay satır-bitişikliği oluşmasın (sentinel deseniyle aynı amaç; tüketici tarafı ayrıca
# kendi _CORPUS_SENTINEL'ine çevirir, bu sadece insan-okunur dosyadaki ayraçtır).
BOUNDARY = "### DILIM-SINIRI ###"


def read_clip(clip_dir: Path, eng, force: bool = False, ocr_job: str = "") -> dict:
    md = clip_dir / DILIM_DIRNAME
    parts = sorted(md.glob("*_p[0-9][0-9].png")) if md.is_dir() else []
    res = {"film": clip_dir.name, "parts": len(parts), "lines": 0, "status": "ok"}
    if not parts:
        res["status"] = "dilim-yok"
        return res
    txt_p, jl_p = md / OUT_TXT, md / OUT_JSONL
    if txt_p.exists() and not force:
        res["status"] = "zaten-var"
        return res
    import cv2
    import numpy as np
    from jenerik_oneocr_detector import oneocr_line_boxes
    txt_lines, jl_rows = [], []
    for p in parts:
        try:
            # cv2.imread Windows'ta non-ASCII yolda (İHTİRAS'taki 'İ') SESSİZCE None döner —
            # unicode-güvenli yol: bytes oku + imdecode.
            buf = np.fromfile(str(p), dtype=np.uint8)
            bgr = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            if bgr is None:
                continue
            for (x0, y0, x1, y1), text in oneocr_line_boxes(eng, bgr):
                t = (text or "").strip()
                if not t:
                    continue
                txt_lines.append(t)
                jl_rows.append({"part": p.name, "text": t,
                                "x0": int(x0), "y0": int(y0), "x1": int(x1), "y1": int(y1)})
        except Exception as exc:  # noqa: BLE001 — bir parça bozuksa diğerleri okunmaya devam
            jl_rows.append({"part": p.name, "error": f"{type(exc).__name__}: {exc}"})
        txt_lines.append(BOUNDARY)
    # atomik-ish yazım: önce meta+jsonl sonra txt (txt varlığı 'tamamlandı' sinyali sayılır).
    # RUN-SCOPE DAMGASI (tasarım-incelemesi şartı 2026-07-03): tüketici (_pipe_credit_vl) bayat-dilim
    # riskine karşı meta.ocr_job'u güncel koşuyla karşılaştırır — damga eşleşmiyorsa dahil ETMEZ.
    from datetime import datetime, timezone
    meta = {"ocr_job": ocr_job or "", "ts": datetime.now(timezone.utc).isoformat(),
            "parts": len(parts), "engine": "oneocr"}
    (md / "dilim_oneocr.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                               encoding="utf-8")
    with jl_p.open("w", encoding="utf-8") as h:
        for r in jl_rows:
            h.write(json.dumps(r, ensure_ascii=False) + "\n")
    txt_p.write_text("\n".join(txt_lines) + "\n", encoding="utf-8")
    res["lines"] = sum(1 for t in txt_lines if t != BOUNDARY)
    return res


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    _root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(_root))                                   # 'core' paketi için proje kökü
    sys.path.insert(0, str(_root / "core" / "pipelines" / "ocr"))    # düz-modül importu için
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--ocr-job", default="", help="güncel koşu job-id — run-scope damgası (meta.json)")
    a = ap.parse_args()
    try:
        from jenerik_oneocr_detector import make_oneocr_engine
        eng = make_oneocr_engine()
    except Exception as exc:  # noqa: BLE001 — motor yoksa dürüst hata, dosya yazma
        print(json.dumps({"status": "engine_error", "error": f"{type(exc).__name__}: {exc}"},
                         ensure_ascii=False))
        return 2
    clips = [Path(a.clip)] if a.clip else (sorted(d for d in DB_ROOT.iterdir() if d.is_dir()) if a.all else [])
    if not clips:
        ap.error("--clip veya --all verin")
    t0 = time.perf_counter()
    tot = {"clips": 0, "lines": 0, "atlanan": 0}
    for c in clips:
        r = read_clip(c, eng, force=a.force, ocr_job=a.ocr_job)
        if r["status"] == "ok":
            tot["clips"] += 1
            tot["lines"] += r["lines"]
        else:
            tot["atlanan"] += 1
    tot["secs"] = round(time.perf_counter() - t0, 1)
    print(json.dumps(tot, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
