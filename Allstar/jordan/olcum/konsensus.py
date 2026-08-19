#!/usr/bin/env python3
"""Konsensus referansi + model kiyasi — Cagatay'in kurali.

KURAL (Cagatay, 2026-08-14):
  "3 model de yonetmen yoksa demek ki bu klip yonetmen icermiyordur,
   onu dahil etme."
  → Hicbir modelin gormedigi satir PAYDAYA girmez.
  → >=2 modelin gordugu satir GERCEK sayilir (referans).
  → Tek modelin gordugu satir UYDURMA adayidir.

Bu, "isim klipte yok muydu yoksa model mi atladi" sorusunu elle kare okumadan
ayirir. Kor nokta riski: 3 model AYNI seyi kacirirsa sessizce paydadan duser —
o yuzden elle okunan klip 26 GT'si yontemin DENETIMI olarak ayri durur.

Kullanim: konsensus.py <sonuc.json> [--esik 0.86]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

DIAK = str.maketrans("çğıöşüÇĞİÖŞÜáàâäéèêëíìîïóòôöúùûüñçÁÀÂÄÉÈÊËÍÌÎÏÓÒÔÖÚÙÛÜÑÇ",
                     "cgiosuCGIOSUaaaaeeeeiiiioooouuuuncAAAAEEEEIIIIOOOOUUUUNC")
# Satir mi baslik/gurultu mu — kisa ya da tamamen noktalama olanlari at
GURULTU = re.compile(r"^[\W_]*$")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "")
    s = re.sub(r"[^\w\s'.-]", " ", s, flags=re.U)
    return re.sub(r"\s+", " ", s).strip().upper()


def dasciify(s: str) -> str:
    return norm(s).translate(DIAK)


def satirla(metin: str) -> list[str]:
    out = []
    for s in (metin or "").splitlines():
        s = s.strip()
        if len(s) >= 3 and not GURULTU.match(s):
            out.append(s)
    return list(dict.fromkeys(out))


def benzer(a: str, b: str) -> float:
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def kumele(tum: list[tuple[str, str]], esik: float) -> list[dict]:
    """[(model, satir)] → kume listesi: {yazimlar:{model:satir}, modeller:set}."""
    kumeler: list[dict] = []
    for model, satir in tum:
        yer = None
        for k in kumeler:
            if any(benzer(satir, v) >= esik for v in k["yazimlar"].values()):
                yer = k
                break
        if yer is None:
            kumeler.append({"yazimlar": {model: satir}, "modeller": {model}})
        else:
            yer["yazimlar"].setdefault(model, satir)
            yer["modeller"].add(model)
    return kumeler


def analiz(veri: dict, esik: float) -> dict:
    modeller = sorted({m for k in veri.values() for m in k})
    rapor = {"modeller": modeller, "klipler": {},
             "toplam": {m: defaultdict(int) for m in modeller}}

    for klip, kmap in sorted(veri.items()):
        tum = [(m, s) for m, t in kmap.items() for s in satirla(t)]
        kumeler = kumele(tum, esik)
        referans = [k for k in kumeler if len(k["modeller"]) >= 2]
        tekil = [k for k in kumeler if len(k["modeller"]) == 1]

        kd = {"referans_satir": len(referans), "model": {}}
        for m in modeller:
            if m not in kmap:
                continue
            bulunan = sum(1 for k in referans if m in k["modeller"])
            kacan = [next(iter(k["yazimlar"].values()))
                     for k in referans if m not in k["modeller"]]
            yalniz = [k["yazimlar"][m] for k in tekil if m in k["modeller"]]
            # diakritik dusus: bu model ASCII yazmis, baskasi aksanli yazmis
            dusen = []
            for k in referans:
                if m not in k["yazimlar"]:
                    continue
                benim = k["yazimlar"][m]
                for m2, v in k["yazimlar"].items():
                    if m2 != m and norm(v) != norm(benim) \
                       and dasciify(v) == dasciify(benim) and norm(benim) == dasciify(benim) \
                       and norm(v) != dasciify(v):
                        dusen.append(f"{benim}  ←  {v}")
                        break
            n = len(referans) or 1
            kd["model"][m] = {
                "recall": round(bulunan / n, 3), "bulunan": bulunan,
                "kacan": len(kacan), "yalniz": len(yalniz),
                "diakritik_dusus": len(dusen),
                "_kacan": kacan[:8], "_yalniz": yalniz[:8], "_dusen": dusen[:6],
            }
            t = rapor["toplam"][m]
            t["referans"] += len(referans); t["bulunan"] += bulunan
            t["kacan"] += len(kacan); t["yalniz"] += len(yalniz)
            t["diakritik_dusus"] += len(dusen)
        rapor["klipler"][klip] = kd

    for m, t in rapor["toplam"].items():
        t["recall"] = round(t["bulunan"] / (t["referans"] or 1), 3)
        rapor["toplam"][m] = dict(t)
    return rapor


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("json")
    ap.add_argument("--esik", type=float, default=0.86)
    ap.add_argument("--ayrinti", action="store_true")
    n = ap.parse_args()
    r = analiz(json.loads(Path(n.json).read_text(encoding="utf-8")), n.esik)

    print(f"Modeller: {', '.join(r['modeller'])}\n")
    print(f"{'MODEL':<26} {'recall':>7} {'bulunan':>8} {'kaçan':>6} "
          f"{'yalnız':>7} {'diakritik↓':>11}")
    for m, t in sorted(r["toplam"].items(), key=lambda x: -x[1]["recall"]):
        print(f"{m:<26} {t['recall']:>7} {t['bulunan']:>8} {t['kacan']:>6} "
              f"{t['yalniz']:>7} {t['diakritik_dusus']:>11}")

    if n.ayrinti:
        for klip, kd in r["klipler"].items():
            print(f"\n── {klip}  (referans {kd['referans_satir']} satır)")
            for m, d in kd["model"].items():
                print(f"   {m:<24} recall={d['recall']} kaçan={d['kacan']} yalnız={d['yalniz']}")
                for x in d["_kacan"]:
                    print(f"       KAÇIRDI: {x}")
                for x in d["_dusen"]:
                    print(f"       DİAKRİTİK: {x}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
