#!/usr/bin/env python3
"""Okunmalik jenerik videolarini 2 fps karelere ayirip Nash ile kos."""
from __future__ import annotations

import argparse
import json
import subprocess
import time
import unicodedata
from pathlib import Path


UZANTILAR = {".mp4", ".mxf", ".mov", ".mkv", ".avi"}


def taban(metin: str) -> str:
    metin = unicodedata.normalize("NFKD", metin.casefold())
    return "".join(c for c in metin if not unicodedata.combining(c))


def bolum_bul(yol: Path) -> str:
    ad = taban(yol.stem)
    return "giris" if any(x in ad for x in ("ilk", "giris")) else "cikis"


def film_id(no: int, yol: Path) -> str:
    ad = taban(yol.stem)
    guvenli = "_".join("".join(
        c if c.isalnum() else " " for c in ad).split())[:100]
    return f"{no:02d}_{guvenli or 'jenerik'}"


def videolari_bul(kok: Path) -> list[Path]:
    return sorted((p for p in kok.iterdir()
                   if p.is_file() and p.suffix.casefold() in UZANTILAR),
                  key=lambda p: p.name.casefold())


def json_yaz(yol: Path, belge: dict) -> None:
    gecici = yol.with_suffix(yol.suffix + ".tmp")
    gecici.write_text(json.dumps(belge, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    gecici.replace(yol)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=Path(
        "/home/cagatay/Belgeler/okunmalık jenerikler"))
    ap.add_argument("--run-dir", type=Path, default=Path(
        "/tmp/nash-okunmalik-jenerikler"))
    ap.add_argument("--fps", type=float, default=2.0)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--list", action="store_true",
                    help="yalniz bulunacak videolari ve bolumleri yaz")
    a = ap.parse_args(argv)
    if not a.input.is_dir():
        ap.error(f"girdi dizini yok: {a.input}")
    videolar = videolari_bul(a.input)
    if a.limit is not None:
        videolar = videolar[:max(0, a.limit)]
    if a.list:
        for no, video in enumerate(videolar, 1):
            print(f"{no:02d}\t{bolum_bul(video)}\t{video.name}")
        return 0

    kule = Path(__file__).resolve().parents[1]
    a.run_dir.mkdir(parents=True, exist_ok=True)
    rapor_yolu = a.run_dir / "rapor.json"
    rapor = {"input": str(a.input), "fps": a.fps, "run_dir": str(a.run_dir),
             "video_n": len(videolar), "results": []}
    for no, video in enumerate(videolar, 1):
        kimlik = film_id(no, video)
        bolum = bolum_bul(video)
        kareler = a.run_dir / "frames" / kimlik
        kare_marker = kareler / "_FRAMES_OK"
        kareler.mkdir(parents=True, exist_ok=True)
        kayit = {"id": kimlik, "source": str(video), "bolum": bolum}
        bas = time.monotonic()
        try:
            if not kare_marker.is_file():
                if any(kareler.glob("*.png")):
                    raise RuntimeError(
                        f"yarim kare dizini var; yeni --run-dir kullan: {kareler}")
                subprocess.run([
                    "ffmpeg", "-nostdin", "-v", "error", "-i", str(video),
                    "-vf", f"fps={a.fps:g}", str(kareler / "frame_%06d.png"),
                ], check=True)
                kare_marker.write_text("OK\n", encoding="ascii")
            kayit["frame_n"] = len(list(kareler.glob("*.png")))
            sonuc = subprocess.run([
                str(kule / "nash"), "tek", "--kareler", str(kareler),
                "--film-id", kimlik, "--bolum", bolum,
                "--out", str(a.run_dir / "out"),
            ], text=True, capture_output=True)
            kayit["returncode"] = sonuc.returncode
            log = a.run_dir / "logs"
            log.mkdir(exist_ok=True)
            (log / f"{kimlik}.stdout.log").write_text(
                sonuc.stdout, encoding="utf-8")
            (log / f"{kimlik}.stderr.log").write_text(
                sonuc.stderr, encoding="utf-8")
            nash_json = a.run_dir / "out" / kimlik / bolum / "nash.json"
            if nash_json.is_file():
                belge = json.loads(nash_json.read_text(encoding="utf-8"))
                kayit["durum"] = belge.get("durum")
                kayit["satir_n"] = len(belge.get("satirlar") or [])
                kayit["nash_json"] = str(nash_json)
            else:
                kayit["durum"] = "SONUC_YOK"
        except Exception as exc:  # diğer filmleri ölçmeye devam et
            kayit.update({"returncode": 1, "durum": "TEST_ARIZASI",
                          "hata": str(exc)})
        kayit["seconds"] = round(time.monotonic() - bas, 3)
        rapor["results"].append(kayit)
        json_yaz(rapor_yolu, rapor)
        print(f"[{no}/{len(videolar)}] {kimlik}: "
              f"{kayit.get('durum')} ({kayit.get('satir_n', 0)} satir)",
              flush=True)

    rapor["okundu_n"] = sum(x.get("durum") == "OKUNDU"
                             for x in rapor["results"])
    rapor["ariza_n"] = sum(x.get("returncode", 1) != 0
                            for x in rapor["results"])
    json_yaz(rapor_yolu, rapor)
    print(f"Rapor: {rapor_yolu}")
    return 1 if rapor["ariza_n"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
