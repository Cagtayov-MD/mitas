"""Taze arşiv klibi uçtan-uca: pencere → İbra + Messi + Ronaldo → 3-kollu skor.

Kullanım:
  /opt/mitas/venvs/ocr/bin/python taze_pilot.py --klip "<...mp4>" --slug magic-flute-1995
Not: kareler /home/cagatay/Ex_Frame/<slug>-exit_frames/ altına çekilir (mevcut
motorların okuduğu kök); çıktılar /opt/mitas/outputs/taze_pilot/<slug>/.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/opt/mitas/harness/master_dup")
sys.path.insert(0, "/opt/mitas/OCR-worktree")

EX = Path("/home/cagatay/Ex_Frame")
OUT_KOK = Path("/opt/mitas/outputs/taze_pilot")


def xml_kimlik(xml_yolu: Path) -> dict:
    m = xml_yolu.read_text(encoding="utf-8", errors="ignore")
    def cek(etiket):
        e = re.search(rf"<{etiket}>([^<]+)", m)
        return e.group(1).strip() if e else ""
    return {"media_id": cek("MEDIAID"), "title": cek("TITLE")}


def skor_satiri(slug: str, ibra: dict, messi: dict, ronaldo: dict) -> str:
    return f"{slug}\t{ibra.get('f1')}\t{messi.get('f1')}\t{ronaldo.get('f1')}"


def pencere_cek(klip: Path, slug: str, pencere_s: int) -> Path:
    hedef = EX / f"{slug}-exit_frames"
    hedef.mkdir(parents=True, exist_ok=True)
    sure = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(klip)], capture_output=True, text=True).stdout.strip())
    bas = max(0.0, sure - pencere_s)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", str(bas), "-i", str(klip), "-vf", "fps=1",
                    str(hedef / "exit_%06d.png")], check=True)
    return hedef


def referans_cikar(slug: str) -> set[str]:
    """Ham karelerin Paddle taraması (sadakat yöntemi) → referans token seti."""
    import sadakat
    import db_compose_master as dc
    kareler = sadakat.ham_kareler(slug)
    ornek = sadakat.orneklenmis_kareler(kareler, sadakat.hedef_kare_uyarla(len(kareler)))
    ref: set[str] = set()
    for p in ornek:
        for tok, _c in sadakat.det_rec_tokenlari(sadakat._gri_yukle(p), dc):
            if len(tok) >= 3:
                ref.add(tok)
    return ref


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--klip", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--pencere-s", type=int, default=240)
    a = ap.parse_args()
    klip = Path(a.klip)
    out = OUT_KOK / a.slug
    out.mkdir(parents=True, exist_ok=True)

    import pilot_hat as ph
    import ibrahimovic
    import metrik

    hedef = pencere_cek(klip, a.slug, a.pencere_s)
    xml = klip.with_suffix(".xml")
    if xml.is_file():
        (out / "kimlik.json").write_text(
            json.dumps(xml_kimlik(xml), ensure_ascii=False), encoding="utf-8")

    # KOL 1: Messi + deepseek
    sayfalar = ph.havuz_derle(a.slug)
    messi_dokum = ph.oku_deepseek(sayfalar)
    (out / "frame_dokum.txt").write_text("\n".join(messi_dokum) + "\n", encoding="utf-8")
    havuz_ist = dict(ph.SON_HAVUZ_ISTATISTIK or {})

    # KOL 2: İbrahimovic + deepseek
    ibrahimovic.calistir(a.slug, out)
    master_png = out / a.slug / "reading_master.png"
    master_dokum = ph.oku_master(master_png, out) if master_png.is_file() else []
    (out / "master_dokum.txt").write_text("\n".join(master_dokum) + "\n", encoding="utf-8")

    # KOL 3: Ronaldo
    kb = ph.kb_yukle()
    kb_tok = {t for ad in kb for t in ad.split() if len(t) >= 3}
    kare_toplam = len(list(hedef.glob("exit_*.png")))
    manifest = ph.ronaldo_kos(a.slug, out, messi_dokum, master_dokum, kb, kb_tok,
                              kare_toplam=kare_toplam,
                              messi_kare=len(sayfalar), ibra_kare=None)
    manifest["havuz"] = havuz_ist

    # SKOR (3 kolon)
    ref = referans_cikar(a.slug)
    (out / "referans.json").write_text(
        json.dumps(sorted(ref), ensure_ascii=False), encoding="utf-8")
    ronaldo_kunye = (out / "ronaldo_kunye.txt").read_text(encoding="utf-8").splitlines()
    skor = {"ibrahimovic": metrik.skorla(master_dokum, ref, kb_tok),
            "messi": metrik.skorla(messi_dokum, ref, kb_tok),
            "ronaldo": metrik.skorla(ronaldo_kunye, ref, kb_tok),
            "manifest": manifest}
    (out / "SKOR.json").write_text(json.dumps(skor, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
    print(skor_satiri(a.slug, skor["ibrahimovic"], skor["messi"], skor["ronaldo"]), flush=True)


if __name__ == "__main__":
    main()
