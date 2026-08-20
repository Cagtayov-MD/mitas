#!/usr/bin/env python3
"""Hızlı-silah iz-dökümü + toleranslı-eşitlik simülasyonu (Görev M9, Task 3
docs/MITAS_Master_Dup_Kok_Sebep_Plani_v1.md M7/M8 takibi). SALT-ANALİZ --
composer'a (OCR-worktree/db_compose_master.py) TEK SATIR yazılmaz; yalnız
onun SALT-OKUNUR export ettiği det/rec/dHash/gray-diff yardımcıları (uret.py
üzerinden `_dc()`, saglik.py/kalibrasyon_k1.py ile AYNI desen) çağrılıp
NEDEN hizli-silah'ın 4 "Cast of Characters" kartının (aynı metin, dup=0.93)
hiçbir F1/F1b/F1c izinin oluşmadığı teşhis edilir + bu bulgu ışığında
"toleranslı REC-eşitliği (normalize + Levenshtein-oran<=0.15 + güven-ağırlıklı)
adayı serbest bıraksa idi kaç çift birleşirdi, kaçı GERÇEKTEN özdeş" OFFLINE
simüle edilir (composer'ın gerçek karar yoluna dokunmadan).

İki mod:
  --iz            yalnız hizli-silah'ın 5 kartı arasındaki TÜM çiftler için
                  F1 (masked-dHash) + F1b (gray-phase-diff) kapı durumunu +
                  (kapı geçilmese bile, teşhis amaçlı) rec-metnini döker.
  --simulasyon    kalan91_atlas.py çıktısındaki S2/S3/S3b filmlerinin
                  raporlanan cross-blok çiftlerinde rec çalıştırıp
                  strict-eşitlik (mevcut K1 kuralı) ile toleranslı-eşitliği
                  karşılaştırır; kaç çift YENİ birleşirdi + birleşen çiftlerin
                  witness kırpımı (görsel örneklem için) yazılır.

CLI:
  hizli_silah_iz.py --iz
  hizli_silah_iz.py --simulasyon --siniflandirma kalan91_siniflandirma.json
                     --out simulasyon.json --witness-dir data/master_ex/_kalan91/_sim
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MASTER_EX = PROJECT_ROOT / "data" / "master_ex"
EX_FRAME_ROOT = Path("/home/cagatay/Ex_Frame")
EX_SUFFIX = "-exit_frames"
HERE = Path(__file__).resolve().parent

sys.path.insert(0, str(HERE))
import uret  # noqa: E402 -- build_args/_monitor/_dc (SALT-OKUNUR, saglik.py ile aynı desen)

HIZLI_SILAH_SLUG = "hizli-silah"
HIZLI_SILAH_FRAMES = [
    "exit_000540.png", "exit_000544.png", "exit_000548.png",
    "exit_000552.png", "exit_000556.png",
]

TOLERANT_LEV_RATIO_GATE = 0.15
TOLERANT_CONF_GATE = 0.6  # F1C_REC_CONF_GATE ile TUTARLI


def _cv2():
    import cv2
    return cv2


def load_frame_bgr(path: Path):
    cv2 = _cv2()
    im = cv2.imread(str(path))
    return im


def load_frame_gray(path: Path):
    cv2 = _cv2()
    im = cv2.imread(str(path))
    if im is None:
        return None
    return cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)


def _normalize_text(dc, s: str) -> str:
    return dc._f1c_normalize_text(s)


def _lev_ratio(dc, a: str, b: str) -> float:
    if not a and not b:
        return 0.0
    d = dc._levenshtein(a, b)
    return d / max(1, max(len(a), len(b)))


def rec_page_text(dc, gray) -> tuple[str, float, int]:
    """Bir tam-kare üzerinde det+rec: (birleşik-normalize-metin, ort.conf,
    kutu_sayisi). Kutu yoksa ("",0.0,0)."""
    boxes = dc._f1b_det_boxes(gray)
    if not boxes:
        return "", 0.0, 0
    boxes_sorted = dc._f1b_boxes_sorted(boxes)
    recs = dc._f1c_rec_boxes(gray, boxes_sorted)  # [(norm_metin, conf), ...]
    reals = [(t, c) for t, c in recs if t]
    if not reals:
        return "", 0.0, len(boxes)
    metin = " ".join(t for t, _ in reals)
    conf = float(np.mean([c for _, c in reals]))
    return metin, conf, len(boxes)


# --------------------------------------------------------------------------- #
# Mod 1: hizli-silah iz-dökümü
# --------------------------------------------------------------------------- #
def iz_dokumu() -> dict:
    dc = uret._dc()
    args = uret.build_args()
    src_dir = EX_FRAME_ROOT / f"{HIZLI_SILAH_SLUG}{EX_SUFFIX}"

    grays = {}
    for name in HIZLI_SILAH_FRAMES:
        g = load_frame_gray(src_dir / name)
        grays[name] = g

    # F1 masked-dHash (_textmask_dhash Params + args ister; ilk okunabilir
    # kareden derive_params ile üretim-SADIK boyut).
    first = None
    for name in HIZLI_SILAH_FRAMES:
        bgr = load_frame_bgr(src_dir / name)
        if bgr is not None:
            first = bgr
            break
    h0, w0 = first.shape[:2]
    p = dc.derive_params(h0, w0, args)

    thh = {}
    for name in HIZLI_SILAH_FRAMES:
        bgr = load_frame_bgr(src_dir / name)
        if bgr is None:
            thh[name] = None
            continue
        if bgr.shape[:2] != (p.h, p.w):
            bgr = _cv2().resize(bgr, (p.w, p.h))
        thh[name] = dc._textmask_dhash(bgr, p, args)

    pairs = []
    names = HIZLI_SILAH_FRAMES
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            entry = {"a": a, "b": b}
            # F1 kapısı
            if thh[a] is not None and thh[b] is not None:
                ham = dc.hamming(thh[a], thh[b])
                entry["f1_dhash_hamming"] = ham
                entry["f1_kapi_gecti"] = ham <= dc.F1_HASH_GATE
            else:
                entry["f1_dhash_hamming"] = None
                entry["f1_kapi_gecti"] = False
            # F1b kapısı (gri tam-kare faz-hizalı fark)
            ga, gb = grays[a], grays[b]
            if ga is not None and gb is not None and ga.shape == gb.shape:
                diff = dc._f1b_gray_band_diff(ga, gb)
            else:
                diff = None
            if diff is not None:
                entry["f1b_global_fark"] = round(diff["global_fark"], 4)
                entry["f1b_max_band_fark"] = round(diff["max_band_fark"], 4)
                entry["f1b_response"] = round(diff["response"], 4)
                entry["f1b_kapi_gecti"] = (
                    diff["global_fark"] < dc.F1B_GLOBAL_DIFF_GATE
                    and diff["max_band_fark"] < dc.F1B_BAND_DIFF_GATE
                )
            else:
                entry["f1b_kapi_gecti"] = False
            # Teşhis amaçlı: kapı geçilmese BİLE rec ne okuyor (üretim bunu
            # ASLA çağırmaz -- bu yalnız "eğer görseydi ne olurdu" teşhisi).
            if ga is not None and gb is not None:
                ta, ca, na = rec_page_text(dc, ga)
                tb, cb, nb = rec_page_text(dc, gb)
                entry["rec_a"] = ta
                entry["rec_b"] = tb
                entry["rec_conf_a"] = round(ca, 3)
                entry["rec_conf_b"] = round(cb, 3)
                entry["det_kutu_a"] = na
                entry["det_kutu_b"] = nb
                entry["strict_esit"] = bool(ta and ta == tb)
                lev = _lev_ratio(dc, ta, tb)
                entry["lev_oran"] = round(lev, 4)
                entry["toleransli_esit"] = bool(
                    ta and tb and lev <= TOLERANT_LEV_RATIO_GATE
                    and min(ca, cb) >= TOLERANT_CONF_GATE
                )
            pairs.append(entry)

    return {"film": HIZLI_SILAH_SLUG, "frames": HIZLI_SILAH_FRAMES, "pairs": pairs}


# --------------------------------------------------------------------------- #
# Mod 2: S2/S3/S3b genelinde toleranslı-eşitlik simülasyonu
# --------------------------------------------------------------------------- #
def _frame_path(slug: str, src_name: str) -> Path | None:
    if not src_name:
        return None
    return EX_FRAME_ROOT / f"{slug}{EX_SUFFIX}" / src_name


def simulasyon(siniflandirma_path: Path, witness_dir: Path, siniflar: tuple[str, ...]) -> dict:
    dc = uret._dc()
    data = json.loads(siniflandirma_path.read_text(encoding="utf-8"))

    aday_ciftler = []
    for s in data["sonuclar"]:
        if s["sinif"] not in siniflar:
            continue
        # En büyük CROSS (src_idx != es_idx) çifti al (varsa)
        secilen = None
        for p in s.get("pairs", []):
            if p["src_idx"] != p["es_idx"] and p.get("src_kind") == "static_page" and p.get("es_kind") == "static_page":
                secilen = p
                break
        if secilen is None:
            continue
        aday_ciftler.append((s["film"], secilen))

    sonuclar = []
    yeni_birlesen = 0
    zaten_esit_olurdu = 0
    for film, pair in aday_ciftler:
        pa = _frame_path(film, pair.get("src_src"))
        pb = _frame_path(film, pair.get("es_src"))
        if pa is None or pb is None or not pa.is_file() or not pb.is_file():
            sonuclar.append({"film": film, "durum": "kare-bulunamadi", "pair": pair})
            continue
        ga = load_frame_gray(pa)
        gb = load_frame_gray(pb)
        if ga is None or gb is None:
            sonuclar.append({"film": film, "durum": "kare-okunamadi", "pair": pair})
            continue
        ta, ca, na = rec_page_text(dc, ga)
        tb, cb, nb = rec_page_text(dc, gb)
        strict_esit = bool(ta and ta == tb)
        lev = _lev_ratio(dc, ta, tb)
        toleransli_esit = bool(
            ta and tb and lev <= TOLERANT_LEV_RATIO_GATE and min(ca, cb) >= TOLERANT_CONF_GATE
        )
        if strict_esit:
            zaten_esit_olurdu += 1
        elif toleransli_esit:
            yeni_birlesen += 1
        sonuclar.append({
            "film": film, "durum": "olculdu",
            "src_src": pair.get("src_src"), "es_src": pair.get("es_src"),
            "rec_a": ta, "rec_b": tb, "conf_a": round(ca, 3), "conf_b": round(cb, 3),
            "det_kutu_a": na, "det_kutu_b": nb,
            "lev_oran": round(lev, 4),
            "strict_esit": strict_esit, "toleransli_esit": toleransli_esit,
        })
        if toleransli_esit and not strict_esit:
            # Witness: yeni-birleşecek çiftin görsel kanıtı (yanlış-birleşme
            # örneklemi için) -- reading_master.png'den DEĞİL, doğrudan kaynak
            # kareden (rec'in okuduğu TAM kare) kırpım.
            try:
                witness_dir.mkdir(parents=True, exist_ok=True)
                im_a = np.array(Image.open(pa).convert("RGB"))
                im_b = np.array(Image.open(pb).convert("RGB"))
                th = max(im_a.shape[0], im_b.shape[0])

                def padh(arr):
                    if arr.shape[0] == th:
                        return arr
                    extra = np.full((th - arr.shape[0], arr.shape[1], 3), 200, dtype=np.uint8)
                    return np.vstack([arr, extra])

                gap = np.full((th, 16, 3), 255, dtype=np.uint8)
                combo = np.hstack([padh(im_a), gap, padh(im_b)])
                Image.fromarray(combo).save(witness_dir / f"{film}_tolerant_witness.png")
            except Exception:
                pass

    return {
        "n_aday_cift": len(aday_ciftler),
        "n_zaten_strict_esit": zaten_esit_olurdu,
        "n_yeni_birlesen_toleransli": yeni_birlesen,
        "sonuclar": sonuclar,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--iz", action="store_true", help="hizli-silah 5-kart iz-dökümü")
    ap.add_argument("--simulasyon", action="store_true", help="S2/S3/S3b toleranslı-eşitlik simülasyonu")
    ap.add_argument("--siniflandirma", type=Path, default=None)
    ap.add_argument("--siniflar", nargs="+", default=["S2", "S3", "S3b"])
    ap.add_argument("--witness-dir", type=Path, default=MASTER_EX / "_kalan91" / "_sim")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    if args.iz:
        out = iz_dokumu()
        print(json.dumps(out, ensure_ascii=False, indent=1))
        if args.out:
            args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        return 0

    if args.simulasyon:
        if not args.siniflandirma:
            print("--simulasyon icin --siniflandirma gerekli", file=sys.stderr)
            return 1
        out = simulasyon(args.siniflandirma, args.witness_dir, tuple(args.siniflar))
        print(f"n_aday_cift={out['n_aday_cift']}  "
              f"n_zaten_strict_esit={out['n_zaten_strict_esit']}  "
              f"n_yeni_birlesen_toleransli={out['n_yeni_birlesen_toleransli']}")
        if args.out:
            args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"-> {args.out}")
        return 0

    print("--iz veya --simulasyon secilmeli", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
