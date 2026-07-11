# -*- coding: utf-8 -*-
"""dedup_ayni_id.py — aynı TRT-ID'li çoklu-hub temizliği (Çağatay talimatı 2026-07-11).

KURAL: SİLME YOK — fazlalık kopyalar Database/_dedup_arsiv_<tarih>/<trt>/ altına TAŞINIR (geri-
alınabilir). Kanonik = suffix'siz taban ad (' 2'/' 3' YOK). GÜVENLİK: yalnız içerik-BİREBİR-AYNI
kopyalar (kunye.txt sha + _DURUM temel-alan) otomatik arşivlenir; FARKLI olanlar RAPOR'lanır,
DOKUNULMAZ (insan kararı — "her şey aynı" yalnız doğrulanmış-özdeşe uygulanır).

Dry-run varsayılan; --apply ile taşır."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DB = Path(r"E:\MITAS\Database")
TRT_RE = re.compile(r"\d{4}-\d{3,4}-\d-\d{3,4}-\d{2}-\d")


def _nfc(s): return unicodedata.normalize("NFC", s or "")


def _sha_kunye(hub: Path) -> str | None:
    ks = sorted(hub.glob("ocr/ocr-*/kunye.txt"), key=lambda p: p.stat().st_mtime)
    if not ks:
        return None
    return hashlib.sha256(ks[-1].read_bytes()).hexdigest()[:16]


def _durum_ozet(hub: Path) -> dict:
    try:
        d = json.loads((hub / "_DURUM.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    return {"karar": d.get("karar"), "yonetmen": d.get("yonetmen"),
            "cast": d.get("cast"), "ozet_var": (d.get("qwen_qc") or {}).get("ozet_var")}


def _kanonik_ad(names: list[str]) -> str:
    """Suffix'siz (' 2'/' 3' olmayan) tercih; yoksa en kısa."""
    base = [n for n in names if not re.search(r"\s\d+$", n)]
    return sorted(base or names, key=len)[0]


def scan():
    gruplar: dict[str, list[Path]] = defaultdict(list)
    for d in DB.iterdir():
        if d.is_dir() and (d / "_DURUM.json").exists():
            m = TRT_RE.search(_nfc(d.name))
            if m:
                gruplar[m.group(0)].append(d)
    return {t: hs for t, hs in gruplar.items() if len(hs) > 1}


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="dry-run değil GERÇEK arşivle")
    a = ap.parse_args()

    ciftler = scan()
    arsiv_kok = DB / f"_dedup_arsiv_{datetime.now():%Y%m%d}"
    print(f"=== AYNI-ID ÇOKLU-HUB TARAMASI ({len(ciftler)} TRT) {'[UYGULA]' if a.apply else '[DRY-RUN]'} ===\n")
    tasinacak, farkli = [], []
    for trt, hubs in sorted(ciftler.items()):
        adlar = [h.name for h in hubs]
        shalar = {h.name: _sha_kunye(h) for h in hubs}
        ozetler = {h.name: _durum_ozet(h) for h in hubs}
        # içerik-özdeşlik: kunye sha aynı (None-değil) VE cast/yonetmen aynı
        sha_set = set(v for v in shalar.values() if v)
        ozdes = (len(sha_set) == 1 and None not in shalar.values()
                 and len({json.dumps((o.get("yonetmen"), o.get("cast")), sort_keys=True)
                          for o in ozetler.values()}) == 1)
        kanon = _kanonik_ad(adlar)
        print(f"[{trt}] {'ÖZDEŞ ✅' if ozdes else 'FARKLI ⚠️'}  kanonik={kanon}")
        for ad in adlar:
            iaret = "KAL" if ad == kanon else ("→arşiv" if ozdes else "DOKUNMA(farklı)")
            print(f"    {ad:52s} sha={shalar[ad]} karar={ozetler[ad].get('karar')} [{iaret}]")
        if ozdes:
            for h in hubs:
                if h.name != kanon:
                    tasinacak.append((trt, h))
        else:
            farkli.append((trt, adlar))
        print()

    print(f"=== ÖZET: {len(tasinacak)} kopya arşive taşınacak, {len(farkli)} TRT FARKLI (insan kararı) ===")
    if a.apply and tasinacak:
        for trt, h in tasinacak:
            dst = arsiv_kok / trt / h.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(h), str(dst))
            print(f"  TAŞINDI: {h.name} → {dst}")
        print(f"\n[ARŞİV] {arsiv_kok} (geri-almak için: klasörü Database'e geri taşı)")
    elif tasinacak:
        print("  (--apply ile arşivlenir; SİLME YOK, yalnız _dedup_arsiv'e taşıma)")
    if farkli:
        print("\nFARKLI (dokunulmadı — Çağatay kararı):")
        for trt, adlar in farkli:
            print(f"  {trt}: {adlar}")


if __name__ == "__main__":
    main()
