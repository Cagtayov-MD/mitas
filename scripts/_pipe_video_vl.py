# -*- coding: utf-8 -*-
"""VIDEO-VL jenerik okuma hattı (2026-07-16) — ADAY-ÜRETİCİ, otorite DEĞİL.

Akış: jenerik_detection.json'daki start_pos → kaynak videoda saniyeye çevrilir
(kareler son CIKIS_TAIL_S saniyeden FPS=1.5 ile çekilmişti) → o andan film sonuna
kadar SESSİZ (-an) 60s+bindirmeli mp4 parçaları kesilir → vLLM'deki VL modele
(video_url, kanıtlı profil: Qwen3-VL-8B) kare-bölümlü okutulur → hub/video_vl/.

FAIL-SAFE: her hata yalnız uyarı+exit!=0; pipeline'ı DURDURMAZ (çağıran taraf
MITAS_VIDEO_VL=1 kapısıyla ve yut-hata modunda çağırır). vLLM sunucusu YOKSA
dürüst hata verir (sessiz yanlış yok) — sunucu: kurulum/vlm_sunucu.sh start.

Env:
  MITAS_VIDEO_VL_URL      (default http://127.0.0.1:8100)
  MITAS_VIDEO_VL_MODEL    (default qwen3-vl-8b — served-model-name)
  MITAS_VIDEO_VL_PENCERE  (default 60)   saniye
  MITAS_VIDEO_VL_BINDIRME (default 5)    saniye
  MITAS_VIDEO_VL_PAY      (default 5)    başlangıçtan geri güvenlik payı
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

# Havuz sözleşmesiyle BİREBİR aynı sabitler (harness/kunye_stages.py)
FPS = 1.5
CIKIS_TAIL_S = 600.0

FF = os.environ.get("MITAS_FFMPEG") or "ffmpeg"
FP = os.environ.get("MITAS_FFPROBE") or "ffprobe"
URL = os.environ.get("MITAS_VIDEO_VL_URL", "http://127.0.0.1:8100").rstrip("/")
MODEL = os.environ.get("MITAS_VIDEO_VL_MODEL", "qwen3-vl-8b")
PENCERE = float(os.environ.get("MITAS_VIDEO_VL_PENCERE", "60"))
BINDIRME = float(os.environ.get("MITAS_VIDEO_VL_BINDIRME", "5"))
PAY = float(os.environ.get("MITAS_VIDEO_VL_PAY", "5"))

SORU = ("Bu bir film kapanış jeneriği (end credits) videosu. Her kareyi AYRI AYRI oku: "
        "'--- Kare N ---' başlığı altında o karede görünen metni AYNEN satır satır yaz. "
        "Kareleri BİRLEŞTİRME. Rol etiketi (örn. 'Directed by') varsa MUTLAKA yaz; "
        "etiket YOKSA etiket uydurma, sadece ismi yaz. Okuyamadığını atla; uydurma.")


def _sure(video: Path) -> float:
    out = subprocess.check_output([FP, "-v", "error", "-show_entries", "format=duration",
                                   "-of", "csv=p=0", str(video)], text=True, timeout=120)
    return float(out.strip())


def _baslangic_saniyesi(clip_dir: Path, video: Path) -> float | None:
    """jenerik_detection.json start_pos → kaynak-video saniyesi (yoksa None)."""
    j = clip_dir / "frames" / "jenerik_detection.json"
    if not j.is_file():
        return None
    try:
        m = json.loads(j.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    sp = m.get("start_pos")
    if sp is None:
        return None
    dur = _sure(video)
    cstart = max(0.0, dur - CIKIS_TAIL_S)
    return cstart + float(int(sp)) / FPS


def _parcala(video: Path, bas: float, outdir: Path) -> list[Path]:
    dur = _sure(video)
    bas = max(0.0, bas - PAY)
    outdir.mkdir(parents=True, exist_ok=True)
    parcalar: list[Path] = []
    adim = PENCERE - BINDIRME
    i = 0
    t = bas
    while t < dur - 1.0:
        p = outdir / f"parca_{i:02d}.mp4"
        # -an: SESSİZ; -c copy: hızlı kesim (keyframe'e yaslanır, fazladan başlar — kayıp yok)
        cmd = [FF, "-v", "error", "-ss", f"{t:.2f}", "-i", str(video),
               "-t", f"{PENCERE:.2f}", "-an", "-c:v", "copy", "-y", str(p)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if r.returncode != 0 or not p.is_file() or p.stat().st_size < 1024:
            # copy başarısızsa (nadir konteyner): hızlı yeniden-kodla
            cmd = [FF, "-v", "error", "-ss", f"{t:.2f}", "-i", str(video),
                   "-t", f"{PENCERE:.2f}", "-an", "-c:v", "libx264", "-preset", "ultrafast",
                   "-crf", "23", "-y", str(p)]
            subprocess.run(cmd, capture_output=True, text=True, timeout=1200, check=True)
        parcalar.append(p)
        i += 1
        t += adim
    return parcalar


def _saglik() -> bool:
    try:
        urllib.request.urlopen(f"{URL}/health", timeout=5)
        return True
    except Exception:  # noqa: BLE001
        return False


def _dejenerasyon_filtresi(metin: str) -> str:
    """Bilinen VLM dejenerasyonlarını temizle (2026-07-16 depo-10 bulguları):
    (a) '[Name]'/'[İsim]' şablon satırları atılır (okunamayan kare = boş bırak, uydurma-kuzeni),
    (b) ardışık ÖZDEŞ satır tekrarı 2'ye kırpılır (Strehler/McGaughy döngü sınıfı)."""
    cikti: list[str] = []
    onceki = None
    tekrar = 0
    for satir in metin.splitlines():
        s = satir.strip()
        if s and s.strip("[]() ").lower() in ("name", "isim", "i̇sim", "unknown", "n/a"):
            continue
        if s and s == onceki:
            tekrar += 1
            if tekrar >= 2:          # aynı satır en fazla 2 kez ardışık
                continue
        else:
            tekrar = 0
        onceki = s
        cikti.append(satir)
    return "\n".join(cikti)


def _oku(mp4: Path) -> dict:
    payload = {"model": MODEL, "temperature": 0, "max_tokens": 2500,
               "repetition_penalty": 1.05,   # tekrar-döngüsü freni (McGaughy sınıfı)
               "messages": [{"role": "user", "content": [
                   {"type": "video_url", "video_url": {"url": f"file://{mp4}"}},
                   {"type": "text", "text": SORU}]}]}
    req = urllib.request.Request(f"{URL}/v1/chat/completions",
                                 data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    r = json.load(urllib.request.urlopen(req, timeout=1800))
    u = r.get("usage", {}) or {}
    return {"metin": _dejenerasyon_filtresi((r["choices"][0]["message"]["content"] or "").strip()),
            "sure_s": round(time.time() - t0, 1),
            "prompt_tok": u.get("prompt_tokens"), "cikti_tok": u.get("completion_tokens")}


def main() -> int:
    ap = argparse.ArgumentParser(description="VIDEO-VL jenerik okuma (aday-üretici)")
    ap.add_argument("--clip", help="hub dizini (jenerik_detection.json buradan okunur)")
    ap.add_argument("--video", required=True, help="kaynak video")
    ap.add_argument("--start-sec", type=float, default=None,
                    help="jenerik başlangıcı (verilirse detection.json atlanır — test için)")
    ap.add_argument("--out", default=None, help="çıkış dizini (default: <clip>/video_vl)")
    a = ap.parse_args()

    video = Path(a.video)
    if not video.is_file():
        print(f"UYARI[video_vl]: video yok: {video}")
        return 2

    bas = a.start_sec
    clip_dir = Path(a.clip) if a.clip else None
    if bas is None:
        if clip_dir is None:
            print("UYARI[video_vl]: --clip ya da --start-sec gerekli")
            return 2
        bas = _baslangic_saniyesi(clip_dir, video)
        if bas is None:
            print("UYARI[video_vl]: jenerik_detection.json/start_pos yok — atlanıyor (fail-safe)")
            return 3

    if not _saglik():
        print(f"UYARI[video_vl]: vLLM sunucusu yok ({URL}) — kurulum/vlm_sunucu.sh start")
        return 4

    outdir = Path(a.out) if a.out else (clip_dir / "video_vl" if clip_dir else video.parent / "video_vl")
    parcalar = _parcala(video, bas, outdir)
    print(f"video_vl: {len(parcalar)} parça (bas={bas:.1f}s, pencere={PENCERE:.0f}s, sessiz)")

    manifest = {"model": MODEL, "url": URL, "video": str(video), "baslangic_s": round(bas, 2),
                "pencere_s": PENCERE, "bindirme_s": BINDIRME, "parcalar": []}
    birlesik: list[str] = []
    hata = 0
    for i, p in enumerate(parcalar):
        try:
            r = _oku(p)
            (outdir / f"okuma_parca_{i:02d}.txt").write_text(r["metin"] + "\n", encoding="utf-8")
            manifest["parcalar"].append({"parca": p.name, **{k: v for k, v in r.items() if k != "metin"}})
            birlesik.append(f"===== PARÇA {i} ({p.name}) =====\n{r['metin']}")
            print(f"  parça {i}: {r['sure_s']}s, prompt={r['prompt_tok']}tok")
        except Exception as e:  # noqa: BLE001
            hata += 1
            manifest["parcalar"].append({"parca": p.name, "hata": f"{type(e).__name__}: {str(e)[:150]}"})
            print(f"  parça {i}: HATA {type(e).__name__}: {str(e)[:120]}")

    (outdir / "video_vl_okuma.txt").write_text("\n\n".join(birlesik) + "\n", encoding="utf-8")
    (outdir / "video_vl_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"video_vl TAMAM: {len(parcalar) - hata}/{len(parcalar)} parça → {outdir / 'video_vl_okuma.txt'}")
    return 0 if hata == 0 else 5


if __name__ == "__main__":
    sys.exit(main())
