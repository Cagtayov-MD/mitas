#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KUYRUK KIRPMA KURTARMASI (2026-07-26).

Bulgu: yayın kopyalarında dosya sonunda uzun BOŞ (siyah/beyaz/bar) kuyruk olabiliyor.
Sabit "son 600s" penceresi bu durumda jeneriği ıskalıyor
(YANİ BİZ EVLENDİK Mİ: içerik ~5000s'de bitiyor, pencere 5222s'de başlıyor → jenerik dışarıda).

Akış (film başına):
  1) Son 1500s'de 20s aralıkla sonda kareler → parlaklık/varyans ile İÇERİK SONU bulunur.
  2) İçerik sonu, dosya sonundan >120s geride ise (=boş kuyruk var):
     [icerik_sonu-420s, icerik_sonu+15s] penceresinden 1.5 fps kare çıkarılır,
     dedup+filtre uygulanıp okuma_seti YENİLENİR (eski set _eski_okuma_seti'ne taşınır).
  3) okuma.json/kunye.json silinir → NIM okuma turu bu filmi yeniden okur.

Kullanım: venvs/ocr/bin/python kurulum/36_kuyruk_kirp.py --films-file <liste> --workers 6
"""
import argparse
import concurrent.futures as cf
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

KOK = Path("/opt/mitas")
HASAT = KOK / "filmtest" / "kapanis_hasat"
GVFS = Path(f"/run/user/{os.getuid()}/gvfs/"
            "smb-share:server=depo01cifs.int.trt.net.tr,share=sas_h264/Film Kapanış")
FPS = 1.5
PENCERE = 420.0        # içerik sonundan geriye okunacak süre
SONDA_ARALIK = 20      # içerik sonu arama adımı (sn)
SONDA_MENZIL = 1500    # dosya sonundan geriye ne kadar aranacak
MAX_OKUMA = 80


def run(cmd, timeout=900):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def bos_mu(png: Path) -> bool:
    """Kare boş mu (siyah/beyaz/tek renk)? Varyans çok düşükse boş."""
    try:
        from PIL import Image, ImageStat
        with Image.open(png) as im:
            st = ImageStat.Stat(im.convert("L"))
        return st.stddev[0] < 8.0
    except Exception:
        return False


def icerik_sonu_bul(video: Path, sure: float, tmp: Path) -> float:
    """Sondan geriye tarayıp son DOLU karenin zamanını döndür."""
    tmp.mkdir(parents=True, exist_ok=True)
    t = sure - 3
    en_geri = max(0.0, sure - SONDA_MENZIL)
    while t > en_geri:
        p = tmp / f"s_{int(t)}.png"
        r = run(["ffmpeg", "-v", "error", "-ss", f"{t:.1f}", "-i", str(video),
                 "-frames:v", "1", "-q:v", "5", "-y", str(p)], 180)
        if r.returncode == 0 and p.is_file() and not bos_mu(p):
            return t
        t -= SONDA_ARALIK
    return sure - 3          # hep boş → değiştirme


def kurtar(dizin_ad: str) -> str:
    d = HASAT / dizin_ad
    mj = d / "meta.json"
    if not mj.is_file():
        return "meta_yok"
    meta = json.loads(mj.read_text(encoding="utf-8"))
    kaynak = GVFS / meta.get("kaynak_dosya", "")
    if not kaynak.is_file():
        return "kaynak_yok"
    sure = float(meta.get("sure_s") or 0)
    if sure < 300:
        return "kisa"
    tmp = d / "_sonda"
    try:
        son = icerik_sonu_bul(kaynak, sure, tmp)
        shutil.rmtree(tmp, ignore_errors=True)
        bos_kuyruk = sure - son
        if bos_kuyruk < 120:
            return "kuyruk_yok"          # boş kuyruk yok → mevcut pencere doğruydu
        # yeni pencere
        bas = max(0.0, son - PENCERE)
        yeni = d / "_yeni_kareler"
        shutil.rmtree(yeni, ignore_errors=True)
        yeni.mkdir(parents=True, exist_ok=True)
        r = run(["ffmpeg", "-v", "error", "-ss", f"{bas:.1f}", "-i", str(kaynak),
                 "-t", f"{(son - bas + 15):.1f}", "-an", "-vf", f"fps={FPS}",
                 "-q:v", "2", str(yeni / "cikis_%06d.png")], 1800)
        kareler = sorted(yeni.glob("*.png"))
        if r.returncode != 0 or len(kareler) < 10:
            shutil.rmtree(yeni, ignore_errors=True)
            return "kare_yok"
        # dolu kareleri seç + eşit adımlı örnekle
        dolu = [k for k in kareler if not bos_mu(k)]
        if len(dolu) < 5:
            shutil.rmtree(yeni, ignore_errors=True)
            return "hepsi_bos"
        if len(dolu) > MAX_OKUMA:
            adim = len(dolu) / MAX_OKUMA
            dolu = [dolu[int(i * adim)] for i in range(MAX_OKUMA)]
        eski = d / "okuma_seti"
        if eski.is_dir():
            shutil.rmtree(d / "_eski_okuma_seti", ignore_errors=True)
            eski.rename(d / "_eski_okuma_seti")
        (d / "okuma_seti").mkdir(exist_ok=True)
        for k in dolu:
            shutil.copy2(k, d / "okuma_seti" / k.name)
        shutil.rmtree(yeni, ignore_errors=True)
        # okumayı sıfırla → NIM yeniden okuyacak
        for f in ("okuma.json", "zengin.json", "ozet_web.json", "filtre.json"):
            (d / f).unlink(missing_ok=True)
        meta["kuyruk_kirpma"] = {"icerik_sonu_s": round(son, 1),
                                 "bos_kuyruk_s": round(bos_kuyruk, 1),
                                 "yeni_pencere": [round(bas, 1), round(son + 15, 1)],
                                 "kare": len(dolu)}
        mj.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        return "kurtarildi"
    except Exception as e:  # noqa: BLE001
        shutil.rmtree(tmp, ignore_errors=True)
        return f"hata:{type(e).__name__}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--films-file")
    ap.add_argument("--films")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    if a.films_file:
        a.films = open(a.films_file).read().strip()
    hedef = [s.strip() for s in (a.films or "").split(",") if s.strip()]
    dizinler = [d.name for d in sorted(HASAT.iterdir())
                if d.is_dir() and any(h in d.name for h in hedef)] if hedef else []
    if a.limit:
        dizinler = dizinler[:a.limit]
    print(f"{len(dizinler)} film → kuyruk kırpma", flush=True)
    say = {}
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for r in ex.map(kurtar, dizinler):
            say[r] = say.get(r, 0) + 1
            n = sum(say.values())
            if n % 25 == 0:
                print(f"  {n}/{len(dizinler)} kurtarılan={say.get('kurtarildi',0)}", flush=True)
    print(f"BİTTİ: {say} ({(time.time()-t0)/60:.1f} dk)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
