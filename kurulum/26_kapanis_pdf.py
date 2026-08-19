#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KAPANIŞ PDF ÜRETİCİ: kapanis_hasat/<film>/ altındaki meta.json + kunye.json →
resmi künye PDF'i (_make_pdf.build) + pdftoppm önizleme → export dizini.

Acil PDF işi (2026-07-24). venvs/asr python ile çalıştırılır (reportlab burada).
Afiş: _102_afis_cache/<trt-id>.jpg → yoksa IMDb suggestion (orijinal_ad ile, yıl
teyitli güvenli eşleşme) → yoksa boş panel. ANA DİL/ALTYAZI verilmez (bölüm çizilmez).

Kullanım:
  venvs/asr/bin/python kurulum/26_kapanis_pdf.py --films 1947-1094
  venvs/asr/bin/python kurulum/26_kapanis_pdf.py            # kunye.json'u olan herkes
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

KOK = Path("/opt/mitas")
HASAT = KOK / "filmtest" / "kapanis_hasat"
EXPORT = KOK / "export" / "KAPANIS_PDF_20260724"
AFIS_CACHE = KOK / "_102_afis_cache"

os.environ.setdefault("MITAS_PROJECT_ROOT", str(KOK))
os.environ.setdefault("MITAS_MSFONT_DIR", "/usr/share/fonts/truetype/msttcorefonts")
sys.path.insert(0, str(KOK / "OCR-worktree" / "pdf-mitas"))
import _make_pdf  # noqa: E402  (reportlab + font kaydı import'ta)

_TR_UP = str.maketrans("iı", "İI")


def tr_upper(s: str) -> str:
    """Türkçe karakter içeren metin: i→İ kuralıyla; saf-ASCII isim (yabancı):
    düz ASCII upper (ALLISON, ALLİSON değil)."""
    if s.isascii():
        return s.upper()
    return s.translate(_TR_UP).upper()


def sure_fmt(s: float | None) -> str:
    if not s:
        return "—"
    s = int(s)
    return f"{s//3600:02d}:{s%3600//60:02d}:{s%60:02d}"


def afis_bul(trt_id: str, orijinal_ad: str | None, yil: str, calisma: Path,
             net: bool = True, baslik: str = "") -> str | None:
    """Önce cache, sonra IMDb suggestion (yıl-teyitli güvenli eşleşme). Bulunamazsa None."""
    c = AFIS_CACHE / f"{trt_id}.jpg"
    if c.is_file():
        return str(c)
    hedef = calisma / "afis.jpg"
    if hedef.is_file():
        return str(hedef)
    sorgu = orijinal_ad or baslik          # yerli film: Türkçe başlıkla ara
    if not (net and sorgu):
        return None
    try:
        q = urllib.parse.quote(sorgu[:40])
        url = f"https://v3.sg.media-imdb.com/suggestion/x/{q}.json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        d = json.loads(urllib.request.urlopen(req, timeout=10).read())
        aday = None
        for it in d.get("d", []):
            if it.get("qid") not in ("movie", "tvMovie"):
                continue
            img = (it.get("i") or {}).get("imageUrl")
            if not img:
                continue
            # güvenli eşleşme: yıl ±2 VEYA başlık birebir (yanlış afiş > afişsiz)
            y = it.get("y")
            ad_es = it.get("l", "").strip().lower() == sorgu.strip().lower()
            yil_es = y and yil.isdigit() and abs(int(y) - int(yil)) <= 2
            if ad_es or yil_es:
                aday = img
                break
        if not aday:
            return None
        buyuk = re.sub(r"\._V1_.*\.jpg$", "._V1_SX1000.jpg", aday)
        req = urllib.request.Request(buyuk, headers={"User-Agent": "Mozilla/5.0"})
        hedef.write_bytes(urllib.request.urlopen(req, timeout=20).read())
        return str(hedef) if hedef.stat().st_size > 5000 else None
    except Exception:
        return None


try:
    from name_normalize import tr_upper_prose  # üretim kuralı: özet BÜYÜK HARF
except Exception:
    def tr_upper_prose(s):  # type: ignore
        return tr_upper(s)


def pdf_uret(calisma: Path, net_afis: bool = True) -> dict:
    meta = json.loads((calisma / "meta.json").read_text(encoding="utf-8"))
    k = json.loads((calisma / "kunye.json").read_text(encoding="utf-8"))
    trt = meta["trt_id"]
    yil = trt[:4]
    baslik = tr_upper(meta["baslik"])

    oyuncular = [tr_upper(o) for o in (k.get("oyuncular") or [])][:8]
    yonetmen = [tr_upper(y) for y in (k.get("yonetmen") or [])]
    yapimci = [tr_upper(y) for y in (k.get("yapimci") or [])]
    crew = []
    if yapimci:
        crew.append(("Yapımcı", yapimci))
    if yonetmen:
        crew.append(("Yönetmen", yonetmen))

    coz = (f"{meta.get('genislik')}×{meta.get('yukseklik')}"
           if meta.get("genislik") else "—")
    d = dict(
        profile="FİLM",
        date=dt.datetime.now().strftime("%d.%m.%Y  ·  %H:%M"),
        title=baslik,
        subtitle=((k.get("orijinal_ad") or "").upper()
                  if (k.get("orijinal_ad") or "").upper().strip() != baslik.strip()
                  else None) or None,
        poster=afis_bul(trt, k.get("orijinal_ad"), yil, calisma, net_afis,
                        baslik=meta["baslik"]),
        specs=[("ÇÖZÜNÜRLÜK", coz),
               ("TÜR", tr_upper(k.get("tur") or "—")),
               ("TOPLAM SÜRE", sure_fmt(meta.get("sure_s"))),
               ("TRT KİMLİK", trt)],
        keywords=" ; ".join(oyuncular) if oyuncular else "—",
        cast=oyuncular,
        crew=crew,
        ozet=("" if os.environ.get("MITAS_NO_OZET")
              else tr_upper_prose((k.get("ozet") or "").strip())),
    )

    EXPORT.mkdir(parents=True, exist_ok=True)
    pdf_ad = f"{trt} {baslik}".replace("/", "-")
    pdf_yol = EXPORT / f"{pdf_ad}.pdf"
    # GÖNDERİLENLER DONDURULDU (2026-07-24): teslim edilen PDF asla yeniden yazılmaz.
    gonderildi = EXPORT / "_GONDERILDI.txt"
    if gonderildi.is_file() and pdf_yol.name in gonderildi.read_text(encoding="utf-8").splitlines():
        return {"pdf": str(pdf_yol), "afis": True, "ozet": True, "dondu": True}
    _make_pdf.build(str(pdf_yol), d)
    # BASIM-SONRASI ÖZ-DENETİM: render edilen PDF metni kapı kurallarını geçemezse
    # klasörde KALMAZ → _EKSIK'e taşınır (hiçbir kusurlu çıktı gözden kaçamaz).
    try:
        t = subprocess.run(["pdftotext", str(pdf_yol), "-"],
                           capture_output=True, text=True, timeout=60).stdout
        kusur = []
        if "Yönetmen" not in t:
            kusur.append("yonetmen")
        if any(ord(c) > 0x24F and c not in "ÇĞİÖŞÜçğıöşüâîû’·—" for c in t):
            kusur.append("latin")
        if "SESLENDİREN" in t.upper() or "DUBLAJ" in t.upper():
            kusur.append("dublaj")
        if kusur:
            eks = EXPORT / "_EKSIK"
            eks.mkdir(exist_ok=True)
            pdf_yol.rename(eks / pdf_yol.name)
            raise RuntimeError(f"öz-denetim: {','.join(kusur)}")
    except RuntimeError:
        raise
    except Exception:
        pass
    # önizleme (QC için) — pdftoppm; hata olursa önemsiz
    try:
        subprocess.run(["pdftoppm", "-png", "-r", "110", "-singlefile",
                        str(pdf_yol), str(calisma / "onizleme")],
                       capture_output=True, timeout=60)
    except Exception:
        pass
    return {"pdf": str(pdf_yol), "afis": bool(d["poster"]), "ozet": bool(d["ozet"])}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--films", help="virgüllü dizin-adı filtresi (alt-dize)")
    ap.add_argument("--no-net", action="store_true", help="IMDb'ye çıkma (yalnız cache)")
    a = ap.parse_args()

    dizinler = sorted(p for p in HASAT.iterdir()
                      if p.is_dir() and (p / "kunye.json").is_file()
                      and (p / "meta.json").is_file())
    if a.films:
        keys = [s.strip() for s in a.films.split(",") if s.strip()]
        dizinler = [p for p in dizinler if any(kk in p.name for kk in keys)]

    print(f"{len(dizinler)} film PDF'e gidiyor", flush=True)
    ok = hata = atla = 0
    for p in dizinler:
        try:
            # BOŞ KÜNYE KAPISI (2026-07-24): yönetmen+yapımcı+oyuncu üçü de boşsa
            # PDF BASILMAZ — kabuk PDF export'a giremez, film karantina listesine düşer.
            # ÇEKİRDEK KAPISI (Çağatay 2026-07-24): yönetmen + en az 3 ana oyuncu şart.
            # Özet varsa basılır, yoksa panel çizilmez (temiz künye belgesi) — özet
            # artık PDF'i engellemiyor, çekirdek künye (yön+oyuncu) esas.
            _k = json.loads((p / "kunye.json").read_text(encoding="utf-8"))
            # FRAME-KANIT KAPISI (Çağatay 2026-07-26, "kaliteden ödün verme"):
            # künye ya yönetmen+≥2 oyuncu frame'den okunmuş olacak, ya ≥3 oyuncu
            # frame'den okunup özet-doğrulaması yönetmeni teyit etmiş olacak.
            _o = json.loads((p / "okuma.json").read_text(encoding="utf-8")) \
                if (p / "okuma.json").is_file() else {}
            def _kar(ks):
                return {x["ad"].strip().upper() for x in ks or []
                        if isinstance(x, dict) and x.get("kare")
                        and x.get("guven") in ("yuksek", "orta")}
            _fy, _fo = _kar(_o.get("yonetmen")), _kar(_o.get("oyuncular"))
            _dy = any(y.upper() in _fy for y in (_k.get("yonetmen") or []))
            _dn = sum(1 for x in (_k.get("oyuncular") or []) if x.upper() in _fo)
            if not ((_dy and _dn >= 2) or _dn >= 3):
                with open(EXPORT / "_ZAYIF_KANIT.txt", "a", encoding="utf-8") as fh:
                    fh.write(p.name + "\n")
                atla += 1
                continue
            if not (_k.get("yonetmen") and len(_k.get("oyuncular") or []) >= 3):
                with open(EXPORT / "_EKSIK_KUNYE.txt", "a", encoding="utf-8") as fh:
                    fh.write(p.name + "\n")
                atla += 1
                continue
            # değişmemişse yeniden basma (bekçi döngüsü için): pdf, kunye'den yeniyse atla
            k_m = (p / "kunye.json").stat().st_mtime
            eski = list(EXPORT.glob(f"{p.name.split('_')[0]} *.pdf"))
            if eski and eski[0].stat().st_mtime > k_m:
                atla += 1
                continue
            r = pdf_uret(p, net_afis=not a.no_net)
            ok += 1
            print(f"[OK {ok}] {p.name[:60]} afiş={'VAR' if r['afis'] else 'yok'} "
                  f"özet={'VAR' if r['ozet'] else 'yok'}", flush=True)
        except Exception as e:  # noqa: BLE001
            hata += 1
            print(f"[HATA] {p.name[:60]} → {type(e).__name__}: {e}", flush=True)
        time.sleep(0.15 if not a.no_net else 0)   # IMDb nezaket aralığı
    print(f"BİTTİ: {ok} ok, {hata} hata, {atla} atlandı → {EXPORT}", flush=True)
    return 0 if hata == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
