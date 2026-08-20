#!/usr/bin/env python3
"""Free OCR'a karsi grounded 512/1024/2048 kalite-hiz kapisi.

Varsayilan yatak 15 tarihî filmdir. Her filmden secilmis kredi kareleri aynı
model agirligina once Free OCR, sonra grounded istemle sorulur. Raporu Nash'in
`okuma.mod: auto` karari dogrudan tuketir.
"""
from __future__ import annotations

import argparse
import difflib
import gc
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

KULE = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(KULE), str(KULE / "src")]

import model  # noqa: E402
import okuyucu  # noqa: E402
import proof  # noqa: E402
import secim  # noqa: E402

VARSAYILAN_YATAK = Path("/opt/mitas/outputs/olcum_yatagi/klipler")
CAPLER = (512, 1024, 2048)


def _ornekler(yatak: Path, film_basina: int) -> list[tuple[str, Path]]:
    sonuc = []
    for film in sorted(p for p in yatak.iterdir() if p.is_dir()):
        dizin = film / "frames" / "cikis_jenerik"
        s = secim.sec(dizin, {"tavan": 100, "son_kare_zorla": True,
                              "ham_kuyruk": 0})
        if s.hata or not s.yollar:
            continue
        n = min(film_basina, len(s.yollar))
        indeksler = ({len(s.yollar) // 2} if n == 1 else
                     {round(i * (len(s.yollar) - 1) / (n - 1)) for i in range(n)})
        sonuc.extend((film.name, s.yollar[i]) for i in sorted(indeksler))
    return sonuc


def _temiz_satirlar(ham: str, *, grounded: bool) -> list[str]:
    if grounded:
        ogeler = proof.grounding_lines(proof.parse_grounding(ham))
        metin = "\n".join(okuyucu._kirp(x["label"]) for x in ogeler)
        if not metin and not proof.grounding_bicimi_var(ham):
            metin = ham or ""
    else:
        metin = ham or ""
    kayitlar, _ = okuyucu.oku([Path("olcum.png")], lambda _p: metin)
    return [x["text"] for x in kayitlar]


def _kos(ornekler: list[tuple[str, Path]], *, cap: int,
         grounded: bool) -> tuple[dict[str, list[str]], dict]:
    ayar = {"model_yol": "model/deepseek-ocr", "max_new_tokens": cap,
            "max_generation_seconds": 30, "istem": "Free OCR."}
    sor = model.yukle(ayar, KULE)
    cikti: dict[str, list[str]] = defaultdict(list)
    hatalar = []
    t0 = time.monotonic()
    for sira, (film, kare) in enumerate(ornekler, start=1):
        try:
            ham = sor(kare, proof.GROUNDING_PROMPT) if grounded else sor(kare)
            cikti[film].extend(_temiz_satirlar(ham, grounded=grounded))
        except Exception as exc:  # tek kare tum kapiyi durdurmaz, rapora duser
            hatalar.append({"film": film, "kare": kare.name,
                            "hata": f"{type(exc).__name__}: {exc}"[:300]})
        print(f"  {sira:03d}/{len(ornekler):03d} cap={cap} "
              f"{'grounded' if grounded else 'free'} {film[:28]}", flush=True)
    metrik = sor.metrics()
    metrik |= {"duvar_sure_sn": round(time.monotonic() - t0, 3),
               "hatalar": hatalar}
    del sor
    gc.collect()
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception:
        pass
    return dict(cikti), metrik


def _kapsama(referans: list[str], aday: list[str]) -> tuple[float, list[str]]:
    ref = [okuyucu.fold(x) for x in referans if okuyucu.fold(x)]
    ady = [okuyucu.fold(x) for x in aday if okuyucu.fold(x)]
    eksik = []
    for ham, katli in zip(referans, ref):
        if not any(katli == y or difflib.SequenceMatcher(None, katli, y).ratio() >= 0.92
                   for y in ady):
            eksik.append(ham)
    return (1.0 if not ref else (len(ref) - len(eksik)) / len(ref)), eksik


def _name_like(s: str) -> bool:
    kelimeler = [x for x in okuyucu.fold(s).split() if x]
    return len(kelimeler) >= 2 and sum(c.isalpha() for c in s) >= 5


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yatak", type=Path, default=VARSAYILAN_YATAK)
    ap.add_argument("--film-basina", type=int, default=2)
    ap.add_argument("--out", type=Path,
                    default=KULE / "raporlar" / "grounding_pareto.json")
    a = ap.parse_args(argv)
    ornekler = _ornekler(a.yatak, max(1, a.film_basina))
    if not ornekler:
        print("HATA: olcum karesi yok", file=sys.stderr)
        return 2
    print(f"Free OCR referansi: {len(ornekler)} kare / "
          f"{len({x[0] for x in ornekler})} film", flush=True)
    referans, ref_metrik = _kos(ornekler, cap=2048, grounded=False)
    sonuclar = []
    for cap in CAPLER:
        aday, metrik = _kos(ornekler, cap=cap, grounded=True)
        filmler, tum_ref, tum_aday = [], [], []
        for film in sorted({x[0] for x in ornekler}):
            oran, eksik = _kapsama(referans.get(film, []), aday.get(film, []))
            filmler.append({"film": film, "referans_satir": len(referans.get(film, [])),
                            "aday_satir": len(aday.get(film, [])),
                            "bulanik_kapsama": round(oran, 4), "eksik": eksik,
                            "eksik_name_like": [x for x in eksik if _name_like(x)]})
            tum_ref.extend(referans.get(film, []))
            tum_aday.extend(aday.get(film, []))
        genel, genel_eksik = _kapsama(tum_ref, tum_aday)
        sayisal_gecer = (genel >= 0.98
                         and all(x["bulanik_kapsama"] >= 0.95 for x in filmler)
                         and not metrik["hatalar"])
        sonuclar.append({"max_new_tokens": cap,
                         "genel_bulanik_kapsama": round(genel, 4),
                         "sayisal_kapi_gecti": sayisal_gecer,
                         "eksik": genel_eksik, "filmler": filmler,
                         "model_olcum": metrik})
    gecen = next((x for x in sonuclar if x["sayisal_kapi_gecti"]), None)
    oneri = ({"mode": "grounded", "max_new_tokens": gecen["max_new_tokens"],
             "reason": "en_kucuk_sayisal_kapi_gecen_cap"}
            if gecen else
            {"mode": "free_ocr", "max_new_tokens": 2048,
             "reason": "grounded_sayisal_kapiyi_gecemedi"})
    belge = {"schema": "nash.grounding-pareto/v1",
             "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
             "dataset": str(a.yatak), "film_n": len({x[0] for x in ornekler}),
             "frame_n": len(ornekler),
             "frames": [{"film": f, "path": str(p)} for f, p in ornekler],
             "free_ocr": {"max_new_tokens": 2048, "model_olcum": ref_metrik},
             "caps": sonuclar, "recommendation": oneri,
             "manual_review": "Eksik name-like satirlar gercek isim kaybi icin incelenmeli."}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(belge, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(oneri, ensure_ascii=False))
    print(f"yazildi: {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
