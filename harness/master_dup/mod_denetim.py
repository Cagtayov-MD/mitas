#!/usr/bin/env python3
"""BAĞIMSIZ mod-denetimi: ham karelerden gerçek kayma ölç → kompozitörün
sınıflandırmasıyla karşılaştır. Amaç: "kayan jenerik statik-sayfa olarak
derlendi" (MOD HATASI) sınıfını yakalamak — dup metriğinin GÖREMEDİĞİ kusur.

Sinyal: ardışık ham kareler arasında METİN-MASKELİ dikey faz-korelasyonu.
Gerçek kayan jenerik → sürdürülen, tek-yönlü (monoton) dy. Statik kart → dy≈0.
Kompozitör manifest'i strict_scroll_frac≈0 + static_page baskın DERKEN ham
karelerde monoton kayma varsa = MOD HATASI.
"""
import glob
import json
import os
import sys

import cv2
import numpy as np

EX_KARE = "/home/cagatay/Ex_Frame"
EX_MASTER = "/opt/mitas/data/master_ex"


def _kareler(slug: str) -> list[str]:
    d = f"{EX_KARE}/{slug}-exit_frames"
    return sorted(glob.glob(f"{d}/exit_*.png"))


def _metin_maske(gray: np.ndarray) -> np.ndarray:
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1)
    mag = cv2.magnitude(gx, gy)
    m = (mag > (mag.mean() + mag.std())).astype(np.uint8)
    return cv2.dilate(m, np.ones((7, 7), np.uint8))


def kayma_olc(slug: str, ornek: int = 40) -> dict:
    kareler = _kareler(slug)
    if len(kareler) < 4:
        return {"slug": slug, "kare": len(kareler), "durum": "az_kare"}
    idx = np.linspace(0, len(kareler) - 1, min(ornek, len(kareler))).astype(int)
    kareler = [kareler[i] for i in idx]
    prev = None
    dys = []
    for p in kareler:
        im = cv2.imread(p)
        if im is None:
            continue
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
        mask = _metin_maske(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY))
        gm = g.copy()
        gm[mask == 0] = 0.0
        if prev is not None and mask.any() and prev.any():
            han = cv2.createHanningWindow((gm.shape[1], gm.shape[0]), cv2.CV_32F)
            (_, dy), resp = cv2.phaseCorrelate(prev * han, gm * han)
            if resp > 0.10:
                dys.append(dy)
        prev = gm
    if not dys:
        return {"slug": slug, "kare": len(kareler), "durum": "hareket_yok",
                "kayan_oran": 0.0, "monoton": 0.0, "dy_medyan": 0.0}
    dys = np.array(dys)
    kayan = np.abs(dys) > 2.0                    # anlamlı kayma
    kayan_oran = float(kayan.mean())
    # monotonluk: kayan karelerin baskın yön oranı
    k = dys[kayan]
    monoton = float(max((k > 0).mean(), (k < 0).mean())) if len(k) else 0.0
    return {"slug": slug, "kare": len(kareler), "durum": "olculdu",
            "kayan_oran": round(kayan_oran, 3), "monoton": round(monoton, 3),
            "dy_medyan": round(float(np.median(np.abs(k))) if len(k) else 0.0, 1)}


def kompozitor_modu(slug: str) -> dict:
    try:
        m = json.load(open(f"{EX_MASTER}/{slug}/manifest.json"))
    except Exception:
        return {"ssf": None, "static_oran": None, "atlas": 0}
    bl = [b for b in m.get("blocks", []) if isinstance(b, dict) and "skip" not in b and b.get("h")]
    sh = sum(b["h"] for b in bl if b.get("kind", "").startswith("static_page"))
    th = sum(b["h"] for b in bl) or 1
    ag = [x for x in (m.get("atlas_gruplari") or []) if isinstance(x, dict) and x.get("rec_dogrulama") == "gecti"]
    return {"ssf": m.get("strict_scroll_frac"), "static_oran": round(sh / th, 3), "atlas_kabul": len(ag)}


def denetle(slug: str) -> dict:
    kay = kayma_olc(slug)
    komp = kompozitor_modu(slug)
    # MOD HATASI: ham karelerde monoton kayma güçlü AMA kompozitör statik-baskın
    # ve atlas onarımı bunu KAPSAMAMIŞ (atlas_kabul düşük).
    mod_hatasi = (
        kay.get("durum") == "olculdu"
        and kay.get("kayan_oran", 0) >= 0.35
        and kay.get("monoton", 0) >= 0.75
        and (komp.get("static_oran") or 0) >= 0.70
        and (komp.get("ssf") or 0) < 0.25
    )
    return {**kay, **komp, "mod_hatasi": mod_hatasi}


def main() -> int:
    global EX_MASTER
    # --kok <path>: master manifest'lerinin okunacağı (ve mod_denetim.json'un
    # yazılacağı) kökü override eder -- varsayılan EX_MASTER (data/master_ex)
    # AYNEN korunur, mevcut çağrılar/davranış DEĞİŞMEZ. Kök-sebep fix doğrulaması:
    # data/master_ex_modfix üzerinde koşmak için (mevcut master_ex'i EZMEDEN).
    if "--kok" in sys.argv:
        EX_MASTER = sys.argv[sys.argv.index("--kok") + 1].rstrip("/")
    slugs = sorted(os.path.basename(p.rstrip("/")).replace("-exit_frames", "")
                   for p in glob.glob(f"{EX_KARE}/*-exit_frames"))
    if "--liste" in sys.argv:
        liste_yolu = sys.argv[sys.argv.index("--liste") + 1]
        istenen = [s.strip() for s in open(liste_yolu, encoding="utf-8") if s.strip()]
        havuz = set(slugs)
        slugs = [s for s in istenen if s in havuz]
    if "--film" in sys.argv:
        slugs = [sys.argv[sys.argv.index("--film") + 1]]
    sonuc = []
    hata = 0
    for i, s in enumerate(slugs):
        r = denetle(s)
        sonuc.append(r)
        if r.get("mod_hatasi"):
            hata += 1
        if "--film" in sys.argv or (i % 40 == 0):
            print(f"[{i+1}/{len(slugs)}] {s[:34]:<35} kayan={r.get('kayan_oran')} "
                  f"mono={r.get('monoton')} ssf={r.get('ssf')} static={r.get('static_oran')} "
                  f"MOD_HATASI={r.get('mod_hatasi')}", flush=True)
    json.dump({"n": len(sonuc), "mod_hatasi": hata, "sonuclar": sonuc},
              open(f"{EX_MASTER}/mod_denetim.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\nMOD HATASI: {hata}/{len(sonuc)} film — kayan jenerik statik-derlendi")
    return 0


if __name__ == "__main__":
    sys.exit(main())
