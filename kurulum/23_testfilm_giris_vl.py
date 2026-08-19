#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TEST_FILM GİRİŞ-VL: 40 filmin İLK 240 saniyesini aynı video-VL hattıyla oku.

Çağatay talimatı (2026-07-23 gece): "iş bittikten sonra bu filmlerin ilk 240 sn
aynı şekilde vl ile oku" — klasik dönem filmlerinde yönetmen/kadro GİRİŞ
jeneriğinde (kapanışta yalnız oyuncu listesi var; 13-film ara-bulgusu).

Yöntem: _pipe_video_vl başlangıçtan film SONUNA kadar parçalar; giriş için bu
yanlış (tüm filmi keser). Çözüm: her filmden önce ffmpeg ile 245s'lik giriş
klibi çıkarılır (GIRIS_HEAD_S=240 sözleşmesi + 5s kuyruk payı), _pipe_video_vl
o klibe --start-sec 0 ile koşar → 60s+5s bindirmeli parçalar → Qwen3-VL-8B.
Çıktı: <calisma>/video_vl_giris/. 22'nin slug/checkpoint/rapor desenleri korunur.
"""
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

KOK = Path("/opt/mitas")
KAYNAK = Path("/home/cagatay/test_film")
CALISMA_KOK = KOK / "filmtest" / "test_film_vl"
PY_OCR = KOK / "venvs" / "ocr" / "bin" / "python"
RAPOR = KOK / "outputs" / "TESTFILM_GIRIS_VL_RAPOR_20260724.md"
CHECKPOINT = CALISMA_KOK / "_sonuc_giris.json"
GIRIS_S = 245.0  # 240s sözleşme + 5s pay (son pencere kuyruğu)

TR_MAP = str.maketrans("İIŞĞÜÖÇışğüöçÂâÎîÛû", "IISGUOCisguocAaIiUu")


def filmleri_bul() -> list[Path]:
    secilen = []
    for v in sorted(KAYNAK.glob("*.mp4")):
        ad = v.name
        if ad.startswith("web_client_") or ad == "tester.mp4" or ad.startswith("need upscale"):
            continue
        secilen.append(v)
    return secilen


def kunye_coz(stem: str) -> tuple[str, str]:
    m = re.search(r"(\d{4}-\d{4})-\d-\d{2,4}-\d{2}-[01]-(.+)$", stem)
    if m:
        return m.group(1), m.group(2)
    return "", stem


def slugla(stem: str) -> str:
    katalog, baslik = kunye_coz(stem)
    duz = baslik.translate(TR_MAP)
    duz = unicodedata.normalize("NFKD", duz).encode("ascii", "ignore").decode("ascii")
    duz = re.sub(r"[^A-Za-z0-9]+", "_", duz).strip("_")
    return f"{katalog}_{duz}" if katalog else duz


def run(cmd, timeout=3600, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)


def giris_klip(video: Path, calisma: Path) -> Path | None:
    """İlk 245s'i sessiz klip olarak çıkar (copy; olmazsa hızlı re-encode)."""
    klip = calisma / "giris_240.mp4"
    if klip.is_file() and klip.stat().st_size > 1024:
        return klip
    calisma.mkdir(parents=True, exist_ok=True)
    r = run(["ffmpeg", "-v", "error", "-ss", "0", "-i", str(video), "-t", f"{GIRIS_S:.0f}",
             "-an", "-c:v", "copy", "-y", str(klip)], 600)
    if r.returncode != 0 or not klip.is_file() or klip.stat().st_size < 1024:
        r = run(["ffmpeg", "-v", "error", "-ss", "0", "-i", str(video), "-t", f"{GIRIS_S:.0f}",
                 "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                 "-y", str(klip)], 1200)
        if r.returncode != 0:
            return None
    return klip


def vl_oku(klip: Path, outdir: Path, force: bool) -> tuple[int, str]:
    okuma = outdir / "video_vl_okuma.txt"
    if okuma.is_file() and okuma.stat().st_size > 0 and not force:
        return 0, "atlandı (mevcut)"
    r = run([str(PY_OCR), str(KOK / "scripts" / "_pipe_video_vl.py"),
             "--video", str(klip), "--start-sec", "0", "--out", str(outdir)],
            5400, cwd=str(KOK))
    return r.returncode, (r.stdout or "")[-300:]


def vllm(komut: str) -> bool:
    r = subprocess.run(["bash", str(KOK / "kurulum" / "vlm_sunucu.sh"), komut],
                       capture_output=True, text=True, timeout=600)
    return r.returncode == 0


def checkpoint_io(sonuc: dict | None = None) -> dict:
    if sonuc is not None:
        CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
        CHECKPOINT.write_text(json.dumps(sonuc, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
        return sonuc
    if CHECKPOINT.is_file():
        try:
            return json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return {}


def rapor_yaz(sonuc: dict) -> None:
    tamam = [(k, s) for k, s in sonuc.items() if s.get("rc") in (0, 5)]
    hatali = [(k, s) for k, s in sonuc.items() if s.get("rc") not in (None, 0, 5)]
    R = ["# TEST_FILM GİRİŞ Jeneriği — ilk 240s → 60s klipler → Qwen3-VL-8B",
         "",
         f"Kaynak: /home/cagatay/test_film · {time.strftime('%Y-%m-%d %H:%M')}",
         f"**Özet:** {len(sonuc)} film — {len(tamam)} okundu, {len(hatali)} hata.", ""]
    for slug, s in tamam:
        R.append(f"## {s.get('katalog', '?')} {s.get('baslik', slug)}")
        R.append(f"- {s.get('n_parca', 0)} parça, rc={s['rc']}"
                 + (" (kısmi)" if s["rc"] == 5 else ""))
        okuma = Path(s.get("okuma_yolu", ""))
        if okuma.is_file():
            metin = okuma.read_text(encoding="utf-8")
            R.append(f"- okuma: {len(metin)} karakter → `{okuma}`")
            R.append("\n```\n" + metin[:1200]
                     + ("\n... (devamı dosyada)" if len(metin) > 1200 else "") + "\n```")
        R.append("")
    if hatali:
        R += ["## Hatalı", ""]
        for slug, s in hatali:
            R.append(f"- {s.get('katalog', '?')} {s.get('baslik', slug)}: rc={s.get('rc')} {s.get('not', '')}")
    RAPOR.write_text("\n".join(R) + "\n", encoding="utf-8")


def main() -> int:
    force = "--force" in sys.argv
    filmler = filmleri_bul()
    print(f"GİRİŞ-VL: {len(filmler)} film (ilk {GIRIS_S:.0f}s)")
    sonuc = checkpoint_io()

    if not vllm("start"):
        print("HATA: vLLM sunucusu kalkmadı")
        return 2
    try:
        for v in filmler:
            slug = slugla(v.stem)
            katalog, baslik = kunye_coz(v.stem)
            calisma = CALISMA_KOK / slug
            s = sonuc.setdefault(slug, {"film": str(v), "katalog": katalog, "baslik": baslik})
            if s.get("rc") in (0, 5) and not force:
                continue
            t = time.time()
            try:
                klip = giris_klip(v, calisma)
                if klip is None:
                    s["rc"], s["not"] = -2, "giriş klibi kesilemedi"
                else:
                    outdir = calisma / "video_vl_giris"
                    rc, out = vl_oku(klip, outdir, force)
                    s["rc"] = rc
                    s["n_parca"] = len(list(outdir.glob("parca_*.mp4"))) if outdir.is_dir() else 0
                    s["okuma_yolu"] = str(outdir / "video_vl_okuma.txt")
            except subprocess.TimeoutExpired:
                s["rc"], s["not"] = -1, "süre aşımı"
            except Exception as e:  # noqa: BLE001
                s["rc"], s["not"] = -1, f"{type(e).__name__}: {str(e)[:120]}"
            print(f"  {slug}: rc={s.get('rc')}, {s.get('n_parca', 0)} parça ({time.time()-t:.0f}s)",
                  flush=True)
            checkpoint_io(sonuc)
            rapor_yaz(sonuc)
    finally:
        vllm("stop")

    rapor_yaz(sonuc)
    print(f"RAPOR: {RAPOR}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
