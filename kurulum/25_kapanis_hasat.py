#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KAPANIŞ HASADI: depo01 'Film Kapanış' MP4'leri (tam film) → son 600s kare çıkarımı
→ tespit_v5 jenerik havuzu → dedup'lu OKUMA SETİ (Claude vision için, VL YOK).

22_testfilm_video_vl.py faz1 uyarlaması (2026-07-24, acil PDF işi). Farklar:
  * Kaynak gvfs/SMB — tail önce STREAM-COPY ile lokale alınır (ağ seek yerine tek
    sıralı ~80MB okuma; 8+ paralel decoder gvfs'i boğmasın).
  * v5 "kredi yok"/havuz boş → KÖR FALLBACK: son 300s'nin kareleri (klasör adı
    "Film Kapanış" — jenerik sonda olmak zorunda, boş dönmek kabul değil).
  * Havuz → PIL aHash dedup + örnekleme → ≤MAX_OKUMA kare `okuma_seti/`.
  * Disk agresif temizlik: tail.mp4 + frames + pool silinir; okuma_seti + meta.json
    + jenerik_detection.json KALIR (kanıt = okuma_seti'nin kendisi).
  * venvs/ocr python ile çalıştırılır (PIL burada garanti).

Kullanım:
  pilot:  venvs/ocr/bin/python kurulum/25_kapanis_hasat.py --films 1947-1094,1986-0072
  tümü:   venvs/ocr/bin/python kurulum/25_kapanis_hasat.py --workers 8
  liste:  ... --list
"""
import argparse
import concurrent.futures as cf
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
from pathlib import Path

KOK = Path("/opt/mitas")
GVFS = Path(f"/run/user/{os.getuid()}/gvfs/"
            "smb-share:server=depo01cifs.int.trt.net.tr,share=sas_h264/Film Kapanış")
CALISMA_KOK = KOK / "filmtest" / "kapanis_hasat"
PY_OCR = KOK / "venvs" / "ocr" / "bin" / "python"
CHECKPOINT = CALISMA_KOK / "_sonuc_kapanis.json"
FPS, TAIL = 1.5, 600.0
GIRIS_S = 245.0             # giriş jeneriği penceresi (23_testfilm_giris_vl sözleşmesi)
FALLBACK_S = 300.0          # kör fallback penceresi (tail sonundan)
MAX_OKUMA = 80              # kapanış okuma seti üst sınırı (Sonnet vision bütçesi)
MAX_OKUMA_GIRIS = 60        # giriş okuma seti üst sınırı
AHASH_ESIK = 5              # hamming < eşik → aynı kart say, at

TR_MAP = str.maketrans("İIŞĞÜÖÇışğüöçÂâÎîÛû", "IISGUOCisguocAaIiUu")
_ckpt_kilit = threading.Lock()


def _env_yukle() -> None:
    p = KOK / "mitas.env"
    if not p.exists():
        return
    for satir in p.read_text(encoding="utf-8", errors="replace").splitlines():
        satir = satir.strip()
        if not satir or satir.startswith("#") or "=" not in satir:
            continue
        k, v = satir.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def kunye_coz(stem: str) -> tuple[str, str]:
    """Dosya adından (TAM trt-id, başlık). Örn ..._1947-1094-1-0000-50-1-MÖSYÖ_VERDOUX
    → ('1947-1094-1-0000-50-1', 'MÖSYÖ_VERDOUX')."""
    m = re.search(r"(\d{4}-\d{4}-\d-\d{2,4}-\d{2}-[01])-(.+)$", stem)
    if m:
        return m.group(1), m.group(2)
    return "", stem


def slugla(stem: str) -> str:
    trt, baslik = kunye_coz(stem)
    duz = baslik.translate(TR_MAP)
    duz = unicodedata.normalize("NFKD", duz).encode("ascii", "ignore").decode("ascii")
    duz = re.sub(r"[^A-Za-z0-9]+", "_", duz).strip("_")[:60]
    return f"{trt}_{duz}" if trt else duz


def filmleri_bul(kaynak: Path) -> list[Path]:
    return sorted(v for v in kaynak.glob("*.mp4") if kunye_coz(v.stem)[0])


def run(cmd, timeout=3600, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)


def probe(v: Path) -> dict:
    o = run(["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height:format=duration",
             "-of", "json", str(v)], 300)
    d = json.loads(o.stdout)
    st = (d.get("streams") or [{}])[0]
    return {"sure_s": float(d["format"]["duration"]),
            "genislik": st.get("width"), "yukseklik": st.get("height")}


def _ahash(png: Path):
    from PIL import Image
    with Image.open(png) as im:
        g = im.convert("L").resize((8, 8), Image.BILINEAR)
        px = list(g.getdata())
    ort = sum(px) / 64
    return sum(1 << i for i, p in enumerate(px) if p > ort)


def okuma_seti_kur(kaynak_kareler: list[Path], hedef: Path, maks: int = MAX_OKUMA) -> int:
    """Ardışık aHash-dedup (statik kartlar çöker) → tavan aşılırsa HAREKET-AĞIRLIKLI
    eleme: önceki kareye hamming'i EN DÜŞÜK kareler önce atılır (kayan jenerik
    kareleri yüksek-hamming'dir, korunur; statik/footage kırpılır). İlk+son korunur."""
    hedef.mkdir(parents=True, exist_ok=True)
    secilen, son_h = [], None            # (path, prev'e hamming)
    for f in kaynak_kareler:
        try:
            h = _ahash(f)
        except Exception:
            continue
        ham = 64 if son_h is None else bin(h ^ son_h).count("1")
        if son_h is None or ham >= AHASH_ESIK:
            secilen.append((f, ham))
            son_h = h
    if kaynak_kareler and (not secilen or secilen[-1][0] != kaynak_kareler[-1]):
        secilen.append((kaynak_kareler[-1], 64))
    if len(secilen) > maks:
        sabit = {0, len(secilen) - 1}                      # ilk + son
        aday = sorted((i for i in range(len(secilen)) if i not in sabit),
                      key=lambda i: secilen[i][1])         # düşük hareket önce atılır
        at = set(aday[:len(secilen) - maks])
        secilen = [s for i, s in enumerate(secilen) if i not in at]
    for f, _ in secilen:
        shutil.copy2(f, hedef / f.name)
    return len(secilen)


def hasat(video: Path, force: bool = False) -> dict:
    stem = video.stem
    trt, baslik = kunye_coz(stem)
    calisma = CALISMA_KOK / slugla(stem)
    meta_j = calisma / "meta.json"
    okuma = calisma / "okuma_seti"

    if meta_j.is_file() and not force:
        m = json.loads(meta_j.read_text(encoding="utf-8"))
        if "giris_okuma_kare" in m or m.get("hata"):   # giriş'siz eski kayıt → yeniden
            m["_atlandi"] = True
            return m

    calisma.mkdir(parents=True, exist_ok=True)
    frames = calisma / "frames" / "cikis"
    pool = calisma / "frames" / "cikis_jenerik"
    dbg = calisma / "jdebug"
    tail_mp4 = calisma / "tail.mp4"
    meta = {"trt_id": trt, "baslik": baslik.replace("_", " "),
            "kaynak_dosya": video.name, "hata": None}

    try:
        p = probe(video)
        meta.update(p)
        cstart = max(0.0, p["sure_s"] - TAIL)
        meta["tail_start_s"] = cstart

        # 1) tail'i lokale stream-copy (tek sıralı ağ okuması, ses yok)
        r = run(["ffmpeg", "-v", "error", "-ss", f"{cstart:.2f}", "-i", str(video),
                 "-an", "-c:v", "copy", "-y", str(tail_mp4)], 1800)
        if r.returncode != 0 or not tail_mp4.is_file() or tail_mp4.stat().st_size < 1024:
            # stream-copy tutmadı (nadir konteyner sorunu) → doğrudan kaynaktan decode
            tail_kaynak = video
            meta["tail_kopya"] = False
        else:
            tail_kaynak, meta["tail_kopya"] = tail_mp4, True

        # 2) kare çıkarımı 1.5 fps
        frames.mkdir(parents=True, exist_ok=True)
        if not list(frames.glob("*.png")):
            on_arg = [] if tail_kaynak == tail_mp4 else ["-ss", f"{cstart:.2f}"]
            r = run(["ffmpeg", "-v", "error", *on_arg, "-i", str(tail_kaynak),
                     "-vf", f"fps={FPS}", "-q:v", "2", str(frames / "cikis_%06d.png")], 1800)
            if r.returncode != 0:
                raise RuntimeError(f"ffmpeg kare: {r.stderr[:200]}")
        tail_mp4.unlink(missing_ok=True)

        # 3) KÖR HAVUZ (v5 YOK — hız kararı 2026-07-24): tüm 600s kuyruk dedup'a girer.
        #    Footage elemesi okuma katmanında (Sonnet "jenerik değil" der, bedava).
        #    v5/GPU hattı film başına ~3-4 dk tespit ekliyordu → 1691 filmde ~20 saat.
        havuz_kareler = sorted(frames.glob("*.png"))
        meta["engine"] = "kor_dedup"
        meta["fallback"] = False

        # 4) okuma seti (dedup + hareket-ağırlıklı örnekleme)
        meta["havuz_kare"] = len(havuz_kareler)
        meta["okuma_kare"] = okuma_seti_kur(havuz_kareler, okuma)

        # 5) GİRİŞ jeneriği (ilk 245s — klasik filmlerde yönetmen/oyuncu burada;
        #    40-film testi: çıkışta 19, girişle 30/40 yönetmen)
        giris_frames = calisma / "frames_giris"
        giris_tail = calisma / "giris.mp4"
        r = run(["ffmpeg", "-v", "error", "-ss", "0", "-i", str(video), "-t",
                 f"{GIRIS_S:.0f}", "-an", "-c:v", "copy", "-y", str(giris_tail)], 900)
        g_kaynak = giris_tail if (r.returncode == 0 and giris_tail.is_file()
                                  and giris_tail.stat().st_size > 1024) else video
        giris_frames.mkdir(parents=True, exist_ok=True)
        r = run(["ffmpeg", "-v", "error", "-i", str(g_kaynak), "-t", f"{GIRIS_S:.0f}",
                 "-vf", f"fps={FPS}", "-q:v", "2", str(giris_frames / "giris_%06d.png")], 1800)
        giris_tail.unlink(missing_ok=True)
        g_kareler = sorted(giris_frames.glob("*.png"))
        meta["giris_okuma_kare"] = okuma_seti_kur(
            g_kareler, calisma / "okuma_seti_giris", MAX_OKUMA_GIRIS) if g_kareler else 0
        shutil.rmtree(giris_frames, ignore_errors=True)
    except Exception as e:  # noqa: BLE001 — film-bazlı yut, koşu durmasın
        meta["hata"] = f"{type(e).__name__}: {e}"[:300]
    finally:
        shutil.rmtree(frames.parent, ignore_errors=True)   # frames/ + pool
        shutil.rmtree(calisma / "frames_giris", ignore_errors=True)
        shutil.rmtree(dbg, ignore_errors=True)
        tail_mp4.unlink(missing_ok=True)
        (calisma / "giris.mp4").unlink(missing_ok=True)

    meta_j.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    with _ckpt_kilit:
        ck = json.loads(CHECKPOINT.read_text(encoding="utf-8")) if CHECKPOINT.is_file() else {}
        ck[slugla(stem)] = {"trt_id": trt, "hata": meta["hata"],
                            "okuma_kare": meta.get("okuma_kare"),
                            "fallback": meta.get("fallback"), "engine": meta.get("engine")}
        CHECKPOINT.write_text(json.dumps(ck, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kaynak", default=str(GVFS))
    ap.add_argument("--films", help="virgüllü TRT-id/başlık filtresi (alt-dize)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--tail", type=float, default=TAIL, help="kuyruk penceresi sn (telafi: 900)")
    ap.add_argument("--giris-s", type=float, default=GIRIS_S, help="giriş penceresi sn (telafi: 420)")
    a = ap.parse_args()
    global TAIL, GIRIS_S
    TAIL, GIRIS_S = a.tail, a.giris_s

    _env_yukle()
    if os.environ.get("MITAS_JENERIK_V5", "0").strip().lower() in ("0", "false", "off", "no"):
        print("HATA: MITAS_JENERIK_V5 aktif değil")
        return 1

    filmler = filmleri_bul(Path(a.kaynak))
    if a.films:
        anahtarlar = [s.strip() for s in a.films.split(",") if s.strip()]
        filmler = [f for f in filmler if any(k in f.stem for k in anahtarlar)]
    if a.limit:
        filmler = filmler[:a.limit]
    if a.list:
        for f in filmler:
            print(slugla(f.stem))
        print(f"toplam: {len(filmler)}")
        return 0

    CALISMA_KOK.mkdir(parents=True, exist_ok=True)
    print(f"{len(filmler)} film, workers={a.workers}", flush=True)
    t0, tamam, hatali = time.time(), 0, 0
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        isler = {ex.submit(hasat, v, a.force): v for v in filmler}
        for fut in cf.as_completed(isler):
            v = isler[fut]
            try:
                m = fut.result()
            except Exception as e:  # noqa: BLE001
                m = {"hata": str(e)[:200]}
            if m.get("hata"):
                hatali += 1
                print(f"[HATA] {v.stem[:70]} → {m['hata']}", flush=True)
            else:
                tamam += 1
                et = "atlandı" if m.get("_atlandi") else (
                    f"okuma={m.get('okuma_kare')} eng={m.get('engine')}"
                    f"{' FALLBACK' if m.get('fallback') else ''}")
                print(f"[OK {tamam}] {slugla(v.stem)[:60]} → {et}", flush=True)
            if (tamam + hatali) % 25 == 0:
                hiz = (tamam + hatali) / max(1e-9, time.time() - t0) * 3600
                print(f"  ... {tamam+hatali}/{len(filmler)} (~{hiz:.0f} film/saat)", flush=True)
    print(f"BİTTİ: {tamam} ok, {hatali} hata, {(time.time()-t0)/60:.1f} dk", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
