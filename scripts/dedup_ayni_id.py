# -*- coding: utf-8 -*-
"""dedup_ayni_id.py — aynı TRT-ID'li çoklu-hub → TEK KLASÖR birleştirme (Çağatay 2026-07-11).

POLİTİKA (Çağatay talimatı): BİR FİLM = BİR KLASÖR.
  • Kanonik = suffix'siz taban ad ('ADI CARMEN <TRT>', ' 2'/' 3' YOK).
  • Dosya-DÜZEYİ birleştirme (klasör-arşiv DEĞİL):
      – ÖZDEŞ dosya (kanonikte aynı yol + aynı bayt) → tek kopya kalır (fazlalık atlanır).
      – FARKLI dosya (aynı yol, farklı bayt)         → kanoniğe '<ad>_2.<uzantı>' / '_3' ile eklenir.
      – TEKİL dosya (kanonikte yok)                   → kanoniğe olduğu gibi kopyalanır.
  • Böylece hiçbir FARKLI içerik kaybolmaz (yalnız birebir-tekrar sadeleşir).
  • Birleştirme kanıtı: kanonikte `_dedup_merge_manifest.json` (ne özdeşti/farklıydı/tekildi).
  • Kaynak (' 2'/' 3') klasörleri birleştirme SONRASI _dedup_arsiv_<tarih>/'e taşınır (SİLME YOK;
    içerikleri zaten kanonikte — arşiv yalnız güvenlik yedeği, geri-alınabilir).

Dry-run varsayılan; --apply ile birleştirir."""
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


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _kanonik_ad(names: list[str]) -> str:
    base = [n for n in names if not re.search(r"\s\d+$", n)]
    return sorted(base or names, key=len)[0]


def _suffix_name(rel: Path, n: int) -> str:
    """'<stem>_<n><suffix>' — çakışan farklı dosyayı ayır (bir film bir klasör; içerik korunur)."""
    return str(rel.parent / f"{rel.stem}_{n}{rel.suffix}") if rel.parent != Path(".") \
        else f"{rel.stem}_{n}{rel.suffix}"


def scan():
    gruplar: dict[str, list[Path]] = defaultdict(list)
    for d in DB.iterdir():
        if d.is_dir() and not d.name.startswith("_") and (d / "_DURUM.json").exists():
            m = TRT_RE.search(_nfc(d.name))
            if m:
                gruplar[m.group(0)].append(d)
    return {t: hs for t, hs in gruplar.items() if len(hs) > 1}


def merge_group(trt: str, hubs: list[Path], *, apply: bool, arsiv_kok: Path) -> dict:
    kanon_ad = _kanonik_ad([h.name for h in hubs])
    kanon = next(h for h in hubs if h.name == kanon_ad)
    digerleri = [h for h in hubs if h.name != kanon_ad]

    # kanonik dosya haritası: rel-path → sha
    kanon_files: dict[str, str] = {}
    for p in kanon.rglob("*"):
        if p.is_file():
            kanon_files[str(p.relative_to(kanon))] = _sha(p)

    plan = {"trt": trt, "kanonik": kanon_ad, "ozdes": 0, "farkli": [], "tekil": [], "kaynaklar": []}
    for dup in digerleri:
        n = int(re.search(r"\s(\d+)$", dup.name).group(1)) if re.search(r"\s(\d+)$", dup.name) else 2
        plan["kaynaklar"].append(dup.name)
        for p in dup.rglob("*"):
            if not p.is_file():
                continue
            rel = str(p.relative_to(dup))
            sha = _sha(p)
            if rel in kanon_files:
                if kanon_files[rel] == sha:
                    plan["ozdes"] += 1                              # birebir tekrar → atla
                else:
                    hedef = _suffix_name(Path(rel), n)              # farklı → _n ile ayır
                    plan["farkli"].append({"kaynak": f"{dup.name}/{rel}", "hedef": hedef})
                    if apply:
                        dst = kanon / hedef
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(p, dst)
            else:
                plan["tekil"].append({"kaynak": f"{dup.name}/{rel}", "hedef": rel})
                if apply:
                    dst = kanon / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p, dst)
    if apply:
        # manifest + kaynak klasörleri arşive (yedek; içerik kanonikte)
        man = kanon / "_dedup_merge_manifest.json"
        man.write_text(json.dumps({**plan, "merged_at": datetime.now().isoformat(timespec="seconds")},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
        for dup in digerleri:
            dst = arsiv_kok / trt / dup.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dup), str(dst))
    return plan


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="dry-run değil GERÇEK birleştir")
    a = ap.parse_args()
    ciftler = scan()
    arsiv_kok = DB / f"_dedup_arsiv_{datetime.now():%Y%m%d}"
    print(f"=== BİR FİLM BİR KLASÖR birleştirme ({len(ciftler)} TRT) "
          f"{'[UYGULA]' if a.apply else '[DRY-RUN]'} ===\n")
    for trt, hubs in sorted(ciftler.items()):
        plan = merge_group(trt, hubs, apply=a.apply, arsiv_kok=arsiv_kok)
        print(f"[{trt}] kanonik={plan['kanonik']}")
        print(f"    kaynaklar: {plan['kaynaklar']}")
        print(f"    özdeş(atlandı)={plan['ozdes']}  farklı(_n)={len(plan['farkli'])}  "
              f"tekil(kopya)={len(plan['tekil'])}")
        for f in plan["farkli"][:8]:
            print(f"      FARKLI → {f['hedef']}")
        for f in plan["tekil"][:8]:
            print(f"      TEKİL  → {f['hedef']}")
        print()
    if a.apply:
        print(f"[TAMAM] bir film bir klasör; kaynak-yedekleri: {arsiv_kok} (geri-alınabilir)")
    else:
        print("(--apply ile birleştirilir)")


if __name__ == "__main__":
    main()
