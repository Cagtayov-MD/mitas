#!/usr/bin/env python3
"""Exit-frame jenerik kesici — jenerik ÖNCESİ kareleri siler (gardlı).

Karar (onset) GÖRSEL AJAN tarafından verilir; bu script yalnız uygular ve emniyet
gardlarını zorlar. `onset` = kapanış bloğunun İLK karesi (bu kare TUTULUR; sadece
numarası < onset olanlar silinir).

Kullanım:
  kes.py <film_dir> --onset N --guven G [--bayrak X] [--gerekce "..."] [--uygula]

Gardlar (biri tetiklenirse SİLMEZ, flag'ler):
  * --uygula yoksa           -> dry-run (hiçbir şey silinmez)
  * onset <= ilk kare        -> tut_hepsi (pencere jenerikle başlıyor; silme yok)
  * --bayrak dolu            -> flag:<bayrak>  (jenerik_yok / belirsiz / ...)
  * guven < 0.60             -> flag:dusuk_guven
  * onset > son kare         -> flag:onset_gecersiz
  * tutulacak kare < 8       -> flag:cok_az_jenerik  (muhtemel hata)

Her çağrıda (silsin/silmesin) audit şeridi + manifest satırı yazılır.
"""
import os
import sys
import json
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import montaj as M  # noqa: E402

GUVEN_ESIK = 0.60
MIN_KEEP = 8
KOK_OUT = "/opt/mitas/outputs/exit_kesim"
MANIFEST = os.path.join(KOK_OUT, "manifest.jsonl")
AUDIT_DIR = os.path.join(KOK_OUT, "audit")


def _audit_serit(ks, onset: int, ad: str) -> str:
    yari = 8
    pen = [c for c in ks if onset - yari <= c[1] <= onset + yari] or [ks[0]]
    out = os.path.join(AUDIT_DIR, f"{ad}_onset{onset}.png")
    M.montaj_uret(pen, out, kolon=len(pen), tw=170, th=120)
    return out


def _yaz_manifest(kayit: dict) -> None:
    os.makedirs(KOK_OUT, exist_ok=True)
    with open(MANIFEST, "a", encoding="utf-8") as f:
        f.write(json.dumps(kayit, ensure_ascii=False) + "\n")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("film_dir")
    p.add_argument("--onset", type=int, required=True)
    p.add_argument("--guven", type=float, default=0.0)
    p.add_argument("--bayrak", default="")
    p.add_argument("--gerekce", default="")
    p.add_argument("--uygula", action="store_true")
    args = p.parse_args()

    film_dir = args.film_dir
    if not os.path.isdir(film_dir):
        print(f"HATA: klasör yok: {film_dir}", file=sys.stderr)
        return 2
    ks = M.kareler(film_dir)
    if not ks:
        print(f"HATA: kare yok: {film_dir}", file=sys.stderr)
        return 2

    ad = M._ad(film_dir)
    ilk, son = ks[0][1], ks[-1][1]
    onset = args.onset
    silinecek = [c for c in ks if c[1] < onset]
    tutulacak = len(ks) - len(silinecek)

    # --- karar / gardlar ---
    if onset <= ilk:
        karar = "tut_hepsi"
    elif args.bayrak.strip():
        karar = f"flag:{args.bayrak.strip()}"
    elif args.guven < GUVEN_ESIK:
        karar = "flag:dusuk_guven"
    elif onset > son:
        karar = "flag:onset_gecersiz"
    elif tutulacak < MIN_KEEP:
        karar = "flag:cok_az_jenerik"
    else:
        karar = "silinebilir"

    # --- audit şeridi (her zaman) ---
    try:
        audit = _audit_serit(ks, onset, ad)
    except Exception as e:
        audit = f"(audit hata: {e})"

    silinen = 0
    if karar == "silinebilir":
        if args.uygula:
            for yol, _no in silinecek:
                try:
                    os.remove(yol)
                    silinen += 1
                except OSError as e:
                    print(f"UYARI silinemedi {yol}: {e}", file=sys.stderr)
            karar = "silindi"
        else:
            karar = "dry-run"

    kayit = {
        "film": ad,
        "film_dir": os.path.abspath(film_dir),
        "onset": onset,
        "guven": round(args.guven, 3),
        "bayrak": args.bayrak.strip(),
        "gerekce": args.gerekce.strip(),
        "ilk": ilk, "son": son, "toplam": len(ks),
        "tutulacak": tutulacak,
        "silinecek": len(silinecek),
        "silinen": silinen,
        "karar": karar,
        "audit": audit,
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _yaz_manifest(kayit)
    print(json.dumps(kayit, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
