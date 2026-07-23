#!/usr/bin/env python3
"""Atlanan-blok (distant-dup*) OCR-özdeşlik denetimi (Görev M4 adım 5e,
docs/MITAS_Master_Dup_Kok_Sebep_Plani_v1.md).

MITAS_MASTER_V2 F1/F1b fix'leri (OCR-worktree/db_compose_master.py -- global
kart kaydı, H2 kök-sebep), bir statik kartı atladığında bunu
data/master_dup/masters_v2/<FİLM>/manifest.json'a üç olası skip türünden
biriyle yazar:
  - "distant-dup"       (F1, dHash+XOR): {es_blok_indeksi, response, fark_orani,
    en_yuksek_bant_farki}
  - "distant-dup-text"  (F1b, det-kutu+NCC eşleşti -- özdeş metin tekrarı):
    {es_blok_indeksi, global_fark, max_band_fark, det_kutular_a/b, kutu_ncc}
  - "distant-dup-scene" (F1b, iki sayfada da det-kutusu YOK -- donuk sahne):
    {..., det_kutular_a: 0, det_kutular_b: 0}

Denetim türe göre değişir (orkestratör kararı, F1b DÜZELTMESİ):
  - "distant-dup" / "distant-dup-text": atlanan kartın kaynak karesi + eşleştiği
    (es_blok_indeksi) kartın kaynak karesi -- ikisi de kaynak video'dan hedefli
    (tek kare) yeniden çıkarılıp PaddleOCR (rec) ile okunur, metinler normalize
    edilip (harness/kunye_kiyas/isim_normalize.normalize -- SALT-OKUNUR import)
    karşılaştırılır. ÖZDEŞ OLMAYAN atlama = TASARIM HATASI (eşikler sıkılaştırılmalı
    -- F1_TOTAL_DIFF_GATE 0.05->0.03 / F1B_NCC_GATE yükseltilmeli -- ve o vaka
    sınıfı için fix devre dışı bırakılmalı).
  - "distant-dup-scene": manifest'e zaten yazılmış det_kutular_a=0/det_kutular_b=0
    kanıtı YETERLİ (det-only kutu sayımı yeniden hesaplanmaz -- kaybolacak metin
    yoktu demek zaten "iki sayfada da 0 kutu" ölçümünün kendisi). Bu betik yalnız
    bu ÖN-KOŞULUN (kayıtlı alanların gerçekten 0/0 olduğu) tutarlılığını doğrular.

Kullanım:
  /opt/mitas/venvs/ocr/bin/python harness/master_dup/skip_audit.py
  /opt/mitas/venvs/ocr/bin/python harness/master_dup/skip_audit.py --json cikti.json

SALT-OKUNUR kaynaklar: harness/kunye_kiyas/isim_normalize.py (yalnız import),
data/master_dup/masters_v2/* (yalnız okunur + gerekli kareler için kaynak mp4
gio ile yeniden kopyalanır -- kalıcı kare/kayıt YAZILMAZ, tmp'ler iş bitince silinir).
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MASTERS_V2 = PROJECT_ROOT / "data" / "master_dup" / "masters_v2"
TMP_ROOT = PROJECT_ROOT / "data" / "master_dup" / "_skip_audit_tmp"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import uret  # noqa: E402  (aynı dizin -- load_pool/gio_copy/locate_source/ensure_mount)

_NORM_PATH = PROJECT_ROOT / "harness" / "kunye_kiyas" / "isim_normalize.py"
_norm_spec = importlib.util.spec_from_file_location("isim_normalize_ro_skipaudit", str(_NORM_PATH))
_norm_mod = importlib.util.module_from_spec(_norm_spec)
_norm_spec.loader.exec_module(_norm_mod)
normalize = _norm_mod.normalize

FPS = 1.5


# --------------------------------------------------------------------------- #
# manifest tarama: distant-dup atlamaları + eş bloğun kaynak karesini bul
# --------------------------------------------------------------------------- #
def _kept_block_index_map(blocks: list[dict]) -> dict[int, dict]:
    """block_index -> o bloğun manifest girdisi. db_compose_master.py'deki
    `len(blocks)` indekslemesini birebir tekrar eder (scroll+card ORTAK sayaç)."""
    idx_map = {}
    counter = 0
    for entry in blocks:
        if "h" in entry and "skip" not in entry:
            idx_map[counter] = entry
            counter += 1
    return idx_map


DISTANT_DUP_SKIP_TYPES = ("distant-dup", "distant-dup-text", "distant-dup-scene")


def find_distant_dup_cases() -> list[dict]:
    cases = []
    for man_path in sorted(MASTERS_V2.glob("*/manifest.json")):
        film = man_path.parent.name
        try:
            man = json.loads(man_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"[uyari] {man_path}: okunamadi ({exc})", file=sys.stderr)
            continue
        blocks = man.get("blocks", [])
        if not blocks:
            continue
        idx_map = _kept_block_index_map(blocks)
        prov = man.get("_uret_provenance", {})
        for entry in blocks:
            skip_type = entry.get("skip")
            if skip_type not in DISTANT_DUP_SKIP_TYPES:
                continue
            es_idx = entry.get("es_blok_indeksi")
            twin = idx_map.get(es_idx)
            cases.append({
                "film": film,
                "skip_type": skip_type,
                "kaynak_dosya": prov.get("kaynak_dosya"),
                "pencere_basi_s": prov.get("pencere_basi_s"),
                "skipped_src": entry.get("src"),
                "twin_src": twin.get("src") if twin else None,
                "es_blok_indeksi": es_idx,
                "response": entry.get("response"),
                "fark_orani": entry.get("fark_orani"),
                "en_yuksek_bant_farki": entry.get("en_yuksek_bant_farki"),
                "global_fark": entry.get("global_fark"),
                "max_band_fark": entry.get("max_band_fark"),
                "det_kutular_a": entry.get("det_kutular_a"),
                "det_kutular_b": entry.get("det_kutular_b"),
                "kutu_ncc": entry.get("kutu_ncc"),
            })
    return cases


# --------------------------------------------------------------------------- #
# hedefli kare çıkarımı (tüm pencere değil -- yalnız gereken 1-2 kare)
# --------------------------------------------------------------------------- #
def _frame_index_from_name(name: str) -> int | None:
    import re
    m = re.search(r"(\d+)", name or "")
    return int(m.group(1)) if m else None


def extract_single_frame(local_mp4: Path, pencere_basi_s: float, frame_name: str, out_png: Path) -> bool:
    n = _frame_index_from_name(frame_name)
    if n is None:
        return False
    ts = pencere_basi_s + (n - 1) / FPS
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(local_mp4), "-ss", f"{ts:.3f}",
        "-frames:v", "1", str(out_png),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0 and out_png.exists() and out_png.stat().st_size > 0


# --------------------------------------------------------------------------- #
# PaddleOCR (rec) -- tek instance, tekrar kullanılır
# --------------------------------------------------------------------------- #
_PADDLE = None


def _paddle_engine():
    global _PADDLE
    if _PADDLE is not None:
        return _PADDLE
    os.environ.setdefault("FLAGS_json_format_model", "0")
    os.environ.setdefault("FLAGS_enable_pir_api", "0")
    from paddleocr import PaddleOCR
    det_name = os.environ.get("MITAS_PADDLEOCR_TEXT_DET_MODEL_NAME") or "PP-OCRv5_mobile_det"
    rec_name = os.environ.get("MITAS_PADDLEOCR_TEXT_REC_MODEL_NAME") or "PP-OCRv5_mobile_rec"
    _PADDLE = PaddleOCR(
        text_detection_model_name=det_name,
        text_recognition_model_name=rec_name,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        enable_mkldnn=False,
    )
    return _PADDLE


def ocr_lines(png_path: Path) -> list[str]:
    eng = _paddle_engine()
    raw = eng.predict(str(png_path)) if hasattr(eng, "predict") else eng.ocr(str(png_path), cls=False)
    texts: list[str] = []

    def walk(node):
        if node is None:
            return
        if isinstance(node, dict):
            if "rec_texts" in node:
                for t in node["rec_texts"]:
                    if t:
                        texts.append(str(t))
            for v in node.values():
                walk(v)
        elif isinstance(node, (list, tuple)):
            for item in node:
                walk(item)

    walk(raw)
    return texts


def normalized_set(lines: list[str]) -> set[str]:
    out = set()
    for line in lines:
        n = normalize(line)
        if n:
            out.add(n)
    return out


def line_overlap(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


# --------------------------------------------------------------------------- #
# ana denetim
# --------------------------------------------------------------------------- #
def audit(overlap_gate: float = 0.5) -> dict:
    cases = find_distant_dup_cases()
    result = {"n_atlama": len(cases), "vakalar": []}
    if not cases:
        return result

    ozdes_olmayan = 0

    # "distant-dup-scene" (F1b): manifest'e zaten yazılmış det_kutular_a=0/
    # det_kutular_b=0 kanıtı YETERLİ (orkestratör kararı) -- yeniden kare
    # çıkarma/OCR YOK, yalnız bu ÖN-KOŞULUN kayıtlı haliyle tutarlılığı doğrulanır.
    scene_cases = [c for c in cases if c["skip_type"] == "distant-dup-scene"]
    for c in scene_cases:
        tutarli = c.get("det_kutular_a") == 0 and c.get("det_kutular_b") == 0
        if not tutarli:
            ozdes_olmayan += 1
        result["vakalar"].append({
            **c,
            "denetim": "ozdes" if tutarli else "OZDES_DEGIL",
            "not": "det=0/0 kanıtı (manifest'te zaten kayıtlı) yeterli -- yeniden OCR gerekmedi",
        })

    # "distant-dup" (F1) / "distant-dup-text" (F1b): tam OCR-rec özdeşlik denetimi
    # -- atlanan kartın kaynak karesi + eşleştiği kartın kaynak karesi hedefli
    # yeniden çıkarılır, PaddleOCR ile okunur, normalize edilip karşılaştırılır.
    ocr_cases = [c for c in cases if c["skip_type"] in ("distant-dup", "distant-dup-text")]
    if ocr_cases:
        uret.ensure_mount()
        TMP_ROOT.mkdir(parents=True, exist_ok=True)
        by_film: dict[str, list[dict]] = {}
        for c in ocr_cases:
            by_film.setdefault(c["film"], []).append(c)

        for film, film_cases in by_film.items():
            kaynak_dosya = film_cases[0]["kaynak_dosya"]
            pencere_basi_s = film_cases[0]["pencere_basi_s"]
            film_tmp = TMP_ROOT / film
            film_tmp.mkdir(parents=True, exist_ok=True)
            local_mp4 = film_tmp / "kaynak.mp4"
            try:
                src = uret.locate_source(kaynak_dosya)
                if src is None or not uret.gio_copy(src, local_mp4):
                    for c in film_cases:
                        result["vakalar"].append({**c, "denetim": "hata", "not": "kaynak/gio_copy basarisiz"})
                    continue
                for c in film_cases:
                    skipped_png = film_tmp / "skipped.png"
                    twin_png = film_tmp / "twin.png"
                    ok1 = extract_single_frame(local_mp4, pencere_basi_s, c["skipped_src"], skipped_png)
                    ok2 = c["twin_src"] and extract_single_frame(local_mp4, pencere_basi_s, c["twin_src"], twin_png)
                    if not ok1 or not ok2:
                        result["vakalar"].append({**c, "denetim": "hata", "not": "kare cikarilamadi"})
                        continue
                    lines_skip = ocr_lines(skipped_png)
                    lines_twin = ocr_lines(twin_png)
                    set_skip = normalized_set(lines_skip)
                    set_twin = normalized_set(lines_twin)
                    overlap = line_overlap(set_skip, set_twin)
                    ozdes = overlap >= overlap_gate
                    if not ozdes:
                        ozdes_olmayan += 1
                    result["vakalar"].append({
                        **c,
                        "denetim": "ozdes" if ozdes else "OZDES_DEGIL",
                        "overlap": round(overlap, 3),
                        "skipped_ocr": sorted(set_skip),
                        "twin_ocr": sorted(set_twin),
                    })
            finally:
                import shutil
                shutil.rmtree(film_tmp, ignore_errors=True)

    result["ozdes_olmayan_sayisi"] = ozdes_olmayan
    result["n_scene_dogrulanan"] = len(scene_cases)
    result["n_ocr_denetlenen"] = len(ocr_cases)
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", type=Path, default=None, help="sonucu bu dosyaya da yaz")
    ap.add_argument("--overlap-esik", type=float, default=0.5,
                    help="normalize satır kümesi kesişim/birleşim orani -- bunun ALTI 'OZDES_DEGIL'")
    args = ap.parse_args(argv)

    r = audit(overlap_gate=args.overlap_esik)
    print(f"n_atlama (distant-dup* skip toplam): {r['n_atlama']}")
    if r["n_atlama"]:
        print(f"  -> n_scene_dogrulanan (det=0/0, OCR gerekmedi): {r.get('n_scene_dogrulanan')}")
        print(f"  -> n_ocr_denetlenen (distant-dup/distant-dup-text): {r.get('n_ocr_denetlenen')}")
        print(f"ozdes_olmayan_sayisi: {r.get('ozdes_olmayan_sayisi')}")
        for v in r["vakalar"]:
            if v.get("denetim") != "ozdes":
                print(f"  [{v.get('denetim')}] {v['film']} ({v.get('skip_type')})  overlap={v.get('overlap')}  "
                      f"skip={v['skipped_src']} twin={v['twin_src']}")
    if args.json:
        args.json.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"-> {args.json}")
    return 0 if r.get("ozdes_olmayan_sayisi", 0) == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
