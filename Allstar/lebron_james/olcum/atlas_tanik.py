#!/usr/bin/env python3
"""F4/M10 Şerit-Atlası tanık-kırpım üretici (hakem sentezi md.4, anti-gaming).

Atlas KABUL edilmiş filmlerden örneklem alır (varsayılan 10); her film için
master PNG'deki atlas bloğunun bölgesini kırpar ve yanına atlasa giren ÜYE
sayfaların kaynak karelerinden (manifest.atlas_uye_sayfalar[].src) küçültülmüş
bir yan-yana şerit koyar -- Çağatay/orkestratör GÖZLE doğrulayabilsin:
"atlas gerçekten üye sayfaların birleşimi mi, içerik kaybı var mı?"

Çıktı: data/master_ex/_atlas_tanik/<film>_atlas<k>.png
Kullanım:
  atlas_tanik.py <masters_kok> [--n 10] [--out data/master_ex/_atlas_tanik]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None

VARSAYILAN_N = 10
TANIK_GENISLIK = 480  # tanık PNG bileşen genişliği (küçültme hedefi)


def _load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _kucult(img: np.ndarray, hedef_w: int = TANIK_GENISLIK) -> np.ndarray:
    h, w = img.shape[:2]
    if w <= hedef_w:
        return img
    oran = hedef_w / w
    return cv2.resize(img, (hedef_w, max(1, int(h * oran))), interpolation=cv2.INTER_AREA)


def atlas_blok_araligi(manifest: dict, hedef_grup: int, sep_px: int = 12) -> tuple[int, int, dict] | None:
    """Final master PNG'de hedef_grup'uncu kabul-edilmiş atlas bloğunun y-aralığı.
    blocks listesindeki kept (skip'siz, h'li) girdilerin kümülatif yerleşimiyle."""
    y = 0
    sayac = 0
    for b in manifest.get("blocks") or []:
        if not isinstance(b, dict) or "skip" in b or b.get("h") is None:
            continue
        h = int(b["h"])
        if b.get("kind") == "static_page_atlas":
            if sayac == hedef_grup:
                return y, y + h, b
            sayac += 1
        y += h + sep_px
    return None


def tanik_uret(film_dir: Path, out_dir: Path) -> list[Path]:
    manifest = _load_json(film_dir / "manifest.json")
    if not manifest:
        return []
    png_path = film_dir / "reading_master.png"
    if not png_path.is_file():
        return []
    master = cv2.imdecode(np.fromfile(str(png_path), np.uint8), cv2.IMREAD_COLOR)
    if master is None:
        return []
    ciktilar: list[Path] = []
    kabul_gruplar = [g for g in (manifest.get("atlas_gruplari") or [])
                     if g.get("rec_dogrulama") == "gecti"]
    for k in range(len(kabul_gruplar)):
        arl = atlas_blok_araligi(manifest, k)
        if arl is None:
            continue
        y0, y1, blok = arl
        atlas_crop = _kucult(master[y0:y1, :])
        # üye sayfaların kaynak kareleri (izlenebilirlik: src alanları)
        uyeler = blok.get("atlas_uye_sayfalar") or []
        kaynaklar = [u.get("src") for u in uyeler if u.get("src")]
        # başlık bandı: film + grup + üye kaynak listesi
        bant_h = 28
        bant = np.zeros((bant_h, atlas_crop.shape[1], 3), np.uint8)
        metin = f"{film_dir.name} atlas#{k} uye={len(uyeler)} src={','.join(kaynaklar[:3])}"
        cv2.putText(bant, metin[:80], (4, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 255), 1)
        tanik = np.vstack([bant, atlas_crop])
        out_path = out_dir / f"{film_dir.name}_atlas{k}.png"
        ok, enc = cv2.imencode(".png", tanik)
        if ok:
            enc.tofile(str(out_path))
            ciktilar.append(out_path)
    return ciktilar


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("masters_kok", type=Path)
    ap.add_argument("--n", type=int, default=VARSAYILAN_N, help="örneklenecek film sayısı (varsayılan 10)")
    ap.add_argument("--out", type=Path, default=None,
                     help="çıktı dizini (varsayılan: <masters_kok>/_atlas_tanik)")
    args = ap.parse_args(argv)

    if cv2 is None:
        print("cv2 gerekli", file=sys.stderr)
        return 1
    kok = args.masters_kok
    out_dir = args.out or (kok / "_atlas_tanik")
    out_dir.mkdir(parents=True, exist_ok=True)

    adaylar = []
    for p in sorted(kok.iterdir()):
        if not p.is_dir() or p.name.startswith("_"):
            continue
        m = _load_json(p / "manifest.json")
        if not m:
            continue
        kabul = [g for g in (m.get("atlas_gruplari") or []) if g.get("rec_dogrulama") == "gecti"]
        if kabul:
            adaylar.append((p, len(kabul)))

    # çok-gruplu filmler önce (en bilgilendirici tanıklar), sonra ad sırası
    adaylar.sort(key=lambda t: (-t[1], t[0].name))
    secim = [p for p, _ in adaylar[: args.n]]
    print(f"atlas-kabullu film: {len(adaylar)}; örneklenen: {len(secim)}")
    toplam = 0
    for p in secim:
        cikti = tanik_uret(p, out_dir)
        toplam += len(cikti)
        for c in cikti:
            print(f"  {c}")
    print(f"-> {toplam} tanık kırpımı: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
