#!/usr/bin/env python3
"""Iverson — ASR transkript kulesi. Başka hiçbir şey yapmaz.

Kule girişi. Motor (src/motor.py) burayı bilmez; çeviri tek yönlüdür.
Çalıştırma:
    Allstar/iverson/iverson tek --girdi /yol/ses.wav --film-id 2025-1307-1-0000-50-0
    Allstar/iverson/iverson tek --girdi film.mkv --film-id X --lid        # MMS-LID kanal-dil
    Allstar/iverson/iverson start --input in/                            # toplu, _TAMAM atlar

Çıktı daima out/<film_id>/iverson.json + _TAMAM (+ transcript.txt,
transcript_plain.txt, chlang.json). Çağıran çıktı yolunu seçmez.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# TEPEDE set — transformers TF'yi import etmesin (TF↔numpy2 çökmesi; _pipe_asr dersi).
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

KULE = Path(__file__).resolve().parent
SRC = KULE / "src"
OUT = KULE / "out"
sys.path.insert(0, str(KULE))
sys.path.insert(0, str(SRC))

# Kule-içi HF önbelleği: MMS-LID modeli <kule>/model/hf altında (dışa bağımlılık yok).
os.environ.setdefault("HF_HOME", str(KULE / "model" / "hf"))

from sozlesme import Cikti, GirdiHatasi, SES_UZANTILARI, ariza, paket_oku  # noqa: E402


def _config() -> dict:
    y = KULE / "config.yaml"
    if not y.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(y.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _surum() -> str:
    try:
        sha = subprocess.run(["git", "-C", str(KULE), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        return "iverson@" + sha if sha else "iverson@?"
    except Exception:
        return "iverson@?"


def _ayar_birlestir(config: dict, cli) -> dict:
    """config.yaml profil(film) + CLI bayrakları → motor ayar sözlüğü.
    getattr: 'start' alt-komutunda tek-bayrakları yoktur (profil default'ları geçer)."""
    profil = (config.get("profil") or {}).get("film") or {}
    return {
        "model": getattr(cli, "model", None) or profil.get("model", "large-v3-turbo"),
        "beam_size": (getattr(cli, "beam", None) if getattr(cli, "beam", None) is not None
                      else profil.get("beam", 1)),
        "vad": getattr(cli, "vad", None) or profil.get("vad", "on"),
        "dil": getattr(cli, "dil", None) or profil.get("dil", "auto"),
        "lid": getattr(cli, "lid", False) or bool(profil.get("lid", False)),
        "tr_mensei": (getattr(cli, "tr_mensei", None)
                      if getattr(cli, "tr_mensei", None) is not None
                      else bool(profil.get("tr_mensei", True))),
        "max_saniye": getattr(cli, "max_saniye", None),
        "llm_valve": bool(profil.get("llm_valve", False)),
        "ffmpeg": (config.get("zemin") or {}).get("ffmpeg", "ffmpeg"),
    }


def tek(girdi_yolu: str, film_id: str, cli, kok: Path | None = None) -> Cikti:
    """Bir ses dosyası → bir Cikti. İstisna sızdırmaz."""
    kok = Path(kok) if kok else OUT
    t0 = time.time()
    import motor
    cfg = _config()
    ayar = _ayar_birlestir(cfg, cli)
    try:
        r = motor.calistir(Path(girdi_yolu), kok / film_id, ayar)
    except Exception as e:  # MotorArizasi dahil — geniş yakalama bilinçli (kobe kalıbı)
        sinif = getattr(e, "sinif", None) or "MOTOR"
        c = ariza(film_id, sinif, (type(e).__name__ + ": " + str(e))[:300])
        c.sure_sn, c.motor_surumu = round(time.time() - t0, 1), _surum()
        c.yaz(kok)
        return c
    c = Cikti(
        film_id=film_id, durum=r["durum"], dil=r["dil"], model=r["model"],
        kanal=r["kanal"], segment_sayisi=r["segment_sayisi"],
        ses_sure_sn=r["ses_sure_sn"], transkript=r["transkript"],
        chlang=r["chlang"], kanit=r["kanit"],
        sure_sn=round(time.time() - t0, 1), motor_surumu=_surum(),
    )
    c.yaz(kok)
    return c


def toplu(girdi_dizini: Path, cli, kok: Path | None = None) -> list[Cikti]:
    """Klasördeki her ses dosyasını işle; _TAMAM varsa atla (kaldığı yerden devam)."""
    kok = Path(kok) if kok else OUT
    sonuc = []
    for p in sorted(Path(girdi_dizini).iterdir()):
        if not p.is_file() or p.suffix.lower() not in SES_UZANTILARI:
            continue
        fid = p.stem
        if (kok / fid / "_TAMAM").exists():
            print("[atla] " + fid)
            continue
        c = tek(str(p), fid, cli, kok)
        sonuc.append(c)
        print("[" + c.durum + "] " + fid + " dil=" + str(c.dil)
              + " segment=" + str(c.segment_sayisi) + " sure=" + str(c.sure_sn) + "s")
    return sonuc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="iverson", description="ASR transkript kulesi")
    alt = ap.add_subparsers(dest="komut", required=True)

    a = alt.add_parser("start", help="toplu: girdi klasöründeki her sesi işle")
    a.add_argument("--input", required=True, help="ses dosyaları klasörü — örn. in/")
    a.add_argument("--out", help="çıktı kök dizinini ezer (varsayılan: out/)")

    b = alt.add_parser("tek", help="tek film/ses")
    b.add_argument("--girdi", required=True, help="ffmpeg çıktısı ses dosyası (wav önerilir)")
    b.add_argument("--film-id", required=True)
    b.add_argument("--model", help="large-v3-turbo | large-v3 (default: profil)")
    b.add_argument("--dil", help="auto | tr | <whisper kodu> (default: auto)")
    b.add_argument("--beam", type=int, help="beam size (default: profil=1)")
    b.add_argument("--vad", choices=["on", "off"], help="VAD (default: on)")
    b.add_argument("--lid", action="store_true", help="MMS-LID kanal-dil tespiti (çok-stream girdi)")
    b.add_argument("--tr-mensei", dest="tr_mensei", default=None, action="store_true",
                   help="menşei TR + 'ku' tespiti → TR-veto (default: profil=true)")
    b.add_argument("--max-saniye", dest="max_saniye", type=float, default=None,
                   help="yalnız ilk N saniye (test kolaylığı)")
    b.add_argument("--out", help="çıktı kök dizinini ezer (varsayılan: out/)")

    n = ap.parse_args(argv)
    kok = Path(n.out) if n.out else None
    if n.komut == "start":
        toplu(Path(n.input), n, kok)
        return 0
    c = tek(n.girdi, n.film_id, n, kok)
    print(json.dumps(c.sozluk(), ensure_ascii=False))
    return 2 if c.durum == "ARIZA" else 0


if __name__ == "__main__":
    sys.exit(main())
