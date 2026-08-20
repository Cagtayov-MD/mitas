#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R2 KOŞUSU — en kötü 10 filmin düzeltilmiş profille yeniden okunması (2026-07-24).

Düzeltmeler (SABAH_RAPORU önerileri, Çağatay onaylı):
  * PENCERE=30s (sweep-kanıtlı: yoğun kayan jenerikte en sadık okuma; 90s+ çöküş)
  * MITAS_VIDEO_VL_MAX_TOKENS=3500 (2500 tavanı meşru metni kırpıyordu)
  * Çıktı AYRI dizine (video_vl_r2/) — run-1 ile A/B karşılaştırma için run-1 korunur
  * Koşu sonrası blackdetect anotasyonu (saf-siyah parçaların okumaları karşılaştırmada çöp sayılır)
  * JP2'de ek 15s sondası (Çağatay'ın "daha da küçük parça" sezgisinin ucuz testi) → video_vl_r15/

Kapsam: QA "kötü" 10'undan profil-düzeltmesiyle iyileşebilir 7 film + "orta"nın en ağır 3
scroll-dejenerasyonu. 3 rescue filmi (KIZGIN_SİLAH, DERT_BENDE, ÖLÜM_ASANSÖRÜ) HARİÇ —
onların çıkış penceresinde jenerik YOK (v5 haklıydı); hiçbir pencere profili footage'ı
jeneriğe çeviremez. Künyeleri giriş okumasından geldi; rescue-iptal kararı onları kapsıyor.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

KOK = Path("/opt/mitas")
CALISMA_KOK = KOK / "filmtest" / "test_film_vl"
PY_OCR = KOK / "venvs" / "ocr" / "bin" / "python"
CHECKPOINT = CALISMA_KOK / "_sonuc_r2.json"

FILMLER = [
    "1997-0265_JURASSIC_PARK_2_KAYIP_DUNYA",
    "2018-1054_DON_KISOT_U_OLDUREN_ADAM",
    "1977-0198_BEYAZ_BIZON",
    "1993-0475_MAKSIM_IN_KAPICISI",
    "2017-2124_POROROCA",
    "1985-0179_UYARI_ISARETI",
    "1999-0363_CENNETIN_RENGI",
    "2019-1203_BARBARLARI_BEKLERKEN",
    "2015-1132_MONTE_KRISTO_KONTU",
    "2001-9073_ALTIN_YUMRUK_ISTANBULDA",
]
SONDA_15S = "1997-0265_JURASSIC_PARK_2_KAYIP_DUNYA"


def run(cmd, timeout=5400, env=None):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          cwd=str(KOK), env=env)


def vllm(komut):
    e = dict(os.environ)
    e["MITAS_VLLM_GPU_UTIL"] = "0.89"
    r = subprocess.run(["bash", str(KOK / "kurulum" / "vlm_sunucu.sh"), komut],
                       capture_output=True, text=True, timeout=600, env=e)
    return r.returncode == 0


def siyah_oran(mp4: Path) -> float:
    """blackdetect ile parçanın siyah-kalış oranı (0-1)."""
    try:
        r = run(["ffmpeg", "-v", "info", "-i", str(mp4), "-vf",
                 "blackdetect=d=0.5:pix_th=0.10", "-an", "-f", "null", "-"], 300)
        toplam = 0.0
        for satir in (r.stderr or "").splitlines():
            if "black_duration:" in satir:
                toplam += float(satir.split("black_duration:")[1].strip())
        p = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", str(mp4)], 120)
        sure = float(p.stdout.strip())
        return round(min(1.0, toplam / sure), 3) if sure > 0 else 0.0
    except Exception:  # noqa: BLE001
        return -1.0


def oku_kosusu(slug: str, out_ad: str, pencere: int, cp: dict) -> None:
    kayit = cp.setdefault(slug, {})
    if kayit.get(out_ad) == "ok":
        print(f"  {slug} [{out_ad}]: atlandı (mevcut)", flush=True)
        return
    calisma = CALISMA_KOK / slug
    film = json.load(open(CALISMA_KOK / "_sonuc.json"))[slug]["film"]
    outdir = calisma / out_ad
    env = dict(os.environ)
    env["MITAS_VIDEO_VL_PENCERE"] = str(pencere)
    env["MITAS_VIDEO_VL_MAX_TOKENS"] = "3500"
    t = time.time()
    r = run([str(PY_OCR), str(KOK / "scripts" / "_pipe_video_vl.py"),
             "--clip", str(calisma), "--video", film, "--out", str(outdir)], env=env)
    n = len(list(outdir.glob("parca_*.mp4"))) if outdir.is_dir() else 0
    siyahlar = {p.name: siyah_oran(p) for p in sorted(outdir.glob("parca_*.mp4"))} if n else {}
    kayit[out_ad] = "ok" if r.returncode in (0, 5) else f"rc={r.returncode}"
    kayit[f"{out_ad}_parca"] = n
    kayit[f"{out_ad}_siyah"] = siyahlar
    CHECKPOINT.write_text(json.dumps(cp, ensure_ascii=False, indent=1), encoding="utf-8")
    cop = sum(1 for v in siyahlar.values() if v >= 0.95)
    print(f"  {slug} [{out_ad}]: rc={r.returncode}, {n} parça, {cop} saf-siyah "
          f"({time.time()-t:.0f}s)", flush=True)


def main() -> int:
    cp = {}
    if CHECKPOINT.is_file():
        try:
            cp = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    print(f"R2: {len(FILMLER)} film · pencere=30s · max_tokens=3500 · +15s sondası ({SONDA_15S})",
          flush=True)
    if not vllm("start"):
        print("HATA: vLLM kalkmadı")
        return 2
    try:
        for slug in FILMLER:
            oku_kosusu(slug, "video_vl_r2", 30, cp)
        oku_kosusu(SONDA_15S, "video_vl_r15", 15, cp)
    finally:
        vllm("stop")
    print("R2 TAMAM", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
