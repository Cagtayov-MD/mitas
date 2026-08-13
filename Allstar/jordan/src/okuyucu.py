"""Geçiş 1 — native video → ham metin blokları.

Kule ağzında da, modelin ağzında da VİDEO var: klip ffmpeg ile parçalara
kesilir (keskinleştirilerek) ve her parça mp4 olarak modele verilir. Parçalama
bir yorum katmanı değil, 24 GB'lık kartın fiziksel sınırı — bf16'da 36 kare
tek çağrıda 39/39 OOM verdi, 30 kare çalıştı (sandbox ölçümü, 2026-08-12).

Bu dosya sözleşmeyi BİLMEZ.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from model import CiktiBozuk, ModelHatasi   # noqa: F401  (main.py sınıflandırır)


class VideoHatasi(RuntimeError):
    """ffprobe/ffmpeg patladı ya da parça üretilemedi."""


# "hiç metin yok" dürüst işareti — isim sanılmasın (grade_claude.py deseni)
BOS_ISARET = re.compile(
    r"^(YAZI\s*YOK|NO\s*TEXT|METİN\s*YOK|TEXT\s*YOK|BOŞ|EMPTY|NONE|N/?A|-+)\.?$",
    re.I)

# Model "yazı yok"u CÜMLEYLE de söylüyor ve bunlar transkripte sızıyordu
# (KUKLA ADAM koşusu 2026-08-13: jenerik bitince 5 satır yorum girdi).
# İstemde "no commentary" yazması yetmiyor — süzgeç kodda olmak zorunda.
BOS_CUMLE = re.compile(
    r"(there\s*(is|are|'s)\s+no\s+(visible\s+)?text"
    r"|no\s+text\s+(is\s+)?(visible|present|found|shown)"
    r"|(metin|yazı|yazi)\s+(yok|bulunmuyor|görünmüyor|mevcut\s+değil))", re.I)


def bos_bildirim(satir: str) -> bool:
    """Satır, metnin YOKLUĞUNU bildiren bir ifade mi? Künye satırı değildir."""
    return bool(BOS_ISARET.match(satir) or BOS_CUMLE.search(satir))


def sure_sn(video: str) -> float:
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(video)],
        capture_output=True, text=True, timeout=120)
    try:
        return float(p.stdout.strip())
    except (ValueError, AttributeError):
        raise VideoHatasi(f"ffprobe sure okuyamadi: {p.stderr.strip()[:200]}")


def parcala(video: str, hedef: Path, cfg: dict) -> list[dict]:
    """Klibi bindirmeli parçalara kes → [{"no", "bas_sn", "yol"}].

    Bindirme parça sınırında kesilen ismi kurtarır: aynı isim iki parçada
    görünür, tekrar `_tekille` ile düşer. Kayıp, tekrardan pahalıdır.
    """
    p = cfg.get("parca", {})
    v = cfg.get("video", {})
    adim = max(1.0, float(p.get("sure_sn", 15)) - float(p.get("bindirme_sn", 2)))
    uzunluk = float(p.get("sure_sn", 15))
    fps = float(v.get("fps", 2))
    tavan = int(p.get("kare_tavani", 30))
    if uzunluk * fps > tavan:
        uzunluk = tavan / fps          # emniyet freni — kare tavanı aşılamaz

    suzgec = v.get("suzgec", "scale={genislik}:-2:flags=lanczos").format(
        genislik=int(v.get("genislik", 720)))
    toplam = sure_sn(video)
    hedef.mkdir(parents=True, exist_ok=True)

    parcalar = []
    bas, no = 0.0, 0
    while bas < toplam:
        yol = hedef / f"parca_{no:03d}.mp4"
        r = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{bas:.3f}",
             "-t", f"{uzunluk:.3f}", "-i", str(video),
             "-vf", f"fps={fps},{suzgec}", "-an", "-f", "mp4", str(yol)],
            capture_output=True, text=True, timeout=600)
        if yol.exists() and yol.stat().st_size > 0:
            parcalar.append({"no": no, "bas_sn": round(bas, 2), "yol": str(yol)})
        elif no == 0:
            raise VideoHatasi(
                f"ilk parca kesilemedi (rc={r.returncode}): {r.stderr.strip()[:200]}")
        bas += adim
        no += 1
    if not parcalar:
        raise VideoHatasi("hic parca uretilemedi")
    return parcalar


def _imza(satirlar: list[str]) -> tuple:
    return tuple(re.sub(r"\s+", " ", s).strip().upper() for s in satirlar)


def _bloklara_ayir(metin: str) -> list[list[str]]:
    """Boş satır = ekran bloğu sınırı (istemde böyle söylendi)."""
    bloklar = []
    for ham in re.split(r"\n\s*\n", metin):
        satirlar = [s.strip() for s in ham.splitlines() if s.strip()]
        satirlar = [s for s in satirlar if not bos_bildirim(s)]
        if satirlar:
            bloklar.append(satirlar)
    return bloklar


def oku(motor, parcalar: list[dict], cfg: dict) -> tuple[list[dict], dict]:
    """Her parçayı modele ver, blokları biriktir → (bloklar, kanit).

    Bindirme yüzünden komşu parçalar aynı bloğu iki kez verebilir; ardışık
    parçadaki BİREBİR aynı blok düşer. Uzak tekrarlar korunur — jenerikte
    aynı isim gerçekten iki kez geçebilir, onu silmek veri kaybıdır.
    """
    istem = cfg.get("istem", {}).get("okuma", "")
    bloklar: list[dict] = []
    onceki: set = set()
    hatali = 0

    for p in parcalar:
        try:
            metin = motor.sor(istem, video=p["yol"])
        except CiktiBozuk:
            hatali += 1
            continue                    # tek parça bozuk → koşu bitmez, sayılır
        simdiki = set()
        for satirlar in _bloklara_ayir(metin):
            im = _imza(satirlar)
            simdiki.add(im)
            if im in onceki:
                continue
            bloklar.append({"no": len(bloklar) + 1, "parca": p["no"],
                            "sn": p["bas_sn"], "satirlar": satirlar})
        onceki = simdiki

    kanit = {"parca_sayisi": len(parcalar), "bozuk_parca": hatali,
             "dusunme_sizinti": getattr(motor, "sizinti", 0),
             "blok_sayisi": len(bloklar),
             "satir_sayisi": sum(len(b["satirlar"]) for b in bloklar)}
    if hatali and hatali == len(parcalar):
        raise CiktiBozuk(f"parcalarin hepsi bozuk cevap verdi ({hatali})")
    return bloklar, kanit
