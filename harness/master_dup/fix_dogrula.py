#!/usr/bin/env python3
"""Sınıflandırıcı fix benimseme doğrulaması: modfix vs eski master_ex.
- sağlık (mevcut kriterler) + mod-hatası (K6) birleşik → gerçek sağlık
- REGRESYON: eski-sağlıklı film modfix'te bozuldu mu (byte-parite ideal)
- yeni-kazanılan / yeni-kaybedilen listeleri
"""
import hashlib
import json
import pathlib
import sys

sys.path.insert(0, "/opt/mitas/harness/master_dup")
import saglik  # noqa: E402

ESKI = pathlib.Path("/opt/mitas/data/master_ex")
YENI = pathlib.Path("/opt/mitas/data/master_ex_modfix")


def md5(p: pathlib.Path):
    f = p / "reading_master.png"
    return hashlib.md5(f.read_bytes()).hexdigest() if f.is_file() else None


def saglikli_set(kok, mod_json):
    """sağlık kriterleri + K6 (mod-hatası) birleşik sağlıklı küme."""
    mh = {r["slug"] for r in json.load(open(mod_json, encoding="utf-8"))["sonuclar"]
          if r.get("mod_hatasi")} if pathlib.Path(mod_json).is_file() else set()
    r = saglik.olc_kok(kok)
    sag = set()
    for s in r["sonuclar"]:
        if s["saglikli"] and s["film"] not in mh:   # K6: mod-hatalı = sağlıksız
            sag.add(s["film"])
    return sag, r["n"], mh


def main():
    print("ESKI (master_ex) ölçülüyor...")
    e_sag, e_n, e_mh = saglikli_set(ESKI, f"{ESKI}/mod_denetim.json")
    print(f"  eski: {len(e_sag)}/{e_n} sağlıklı (K6 dahil), mod-hatası {len(e_mh)}")
    print("YENI (modfix) ölçülüyor...")
    y_sag, y_n, y_mh = saglikli_set(YENI, f"{YENI}/mod_denetim.json")
    print(f"  yeni: {len(y_sag)}/{y_n} sağlıklı (K6 dahil), mod-hatası {len(y_mh)}")

    kazanildi = sorted(y_sag - e_sag)
    kaybedildi = sorted(e_sag - y_sag)   # REGRESYON adayı
    # regresyon: eski-sağlıklı film modfix'te değişti mi?
    degisen = [f for f in e_sag if md5(ESKI / f) != md5(YENI / f)]
    print(f"\n  KAZANILDI: {len(kazanildi)}   KAYBEDİLDİ(regresyon): {len(kaybedildi)}")
    print(f"  eski-sağlıklı ama modfix'te DEĞİŞEN çıktı: {len(degisen)}")
    if kaybedildi:
        print("  regresyon örnekleri:", kaybedildi[:10])
    if degisen:
        print("  değişen-sağlıklı örnek:", degisen[:10])
    json.dump({"eski_saglik": len(e_sag), "yeni_saglik": len(y_sag), "n": y_n,
               "kazanildi": kazanildi, "kaybedildi": kaybedildi, "degisen_saglikli": degisen},
              open(f"{YENI}/fix_dogrula.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n  ESKI %{100*len(e_sag)/e_n:.1f} → YENI %{100*len(y_sag)/y_n:.1f}")


if __name__ == "__main__":
    main()
