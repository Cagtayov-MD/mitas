#!/usr/bin/env python3
"""ÖLÇÜM YATAĞI — FAZ 1: HAM ÇIKTILAR (model YOK, LLM YOK, PDF YOK).

KAPSAM (Çağatay, 2026-07-31): "sen ham çıktılara odaklan bu kadar."
QC1 SINIR, geçilecek kapı değil. gemma devre dışı. PDF/teslim/karar YOK.
QC1→QC2 ve QC2→çıkış ayrı konular, buraya girmiyor.

ÜRETİLEN HAM ÇIKTILAR (film başına):
    frames/cikis/             720 kare  — üretim kare sözleşmesi (480 sn × 1.5 fps)
    frames/giris/             baş pencere kareleri
    frames/cikis_jenerik/     FIGO jenerik havuzu          ← Kol A (MESSİ) girdisi
    frames/jenerik_detection.json                          ← FIGO onset kanıtı
    reading_master_runaware.png + _manifest.json           ← Kol B (İBRAHİMOVİC) girdisi
    giris_reading_master_runaware.png + _manifest.json

NEDEN PIPELINE'I KOŞMUYORUZ: mitas_pipeline tam akış — OCR (Paddle) + gemma
rol-eşleme + QC1 + PDF + teslim. Bunların hiçbiri bu ölçümün konusu değil ve
gemma açıkça devre dışı bırakıldı. Ama kare çıkarma SÖZLEŞMESİ birebir aynı
olmak zorunda, o yüzden fonksiyonları YENİDEN YAZMIYORUZ — üretim modülünden
İMPORT ediyoruz (sapma riski sıfır).

YATAK KÖKÜ: outputs/olcum_yatagi/klipler/  — Database'e DOKUNMAZ (üretim temiz kalır).

KULLANIM:
    python3 scripts/olcum_yatagi_faz1.py              # listedeki tümü
    python3 scripts/olcum_yatagi_faz1.py --film 3     # yalnız 3. film
    python3 scripts/olcum_yatagi_faz1.py --bas 2 --son 5
    python3 scripts/olcum_yatagi_faz1.py --kuru       # ne yapacağını yaz, yapma
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJE = Path(os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas"))
SCRIPTS = PROJE / "scripts"
KOK = PROJE / "outputs" / "olcum_yatagi"
KLIPLER = KOK / "klipler"
STAGE = PROJE / "cache" / "staging" / "olcum"
PY_OCR = PROJE / "venvs" / "ocr" / "bin" / "python"

# Üretim sözleşmesi — mitas_pipeline varsayılanlarıyla BİREBİR
CIKIS_TAIL_S = 480.0
GIRIS_HEAD_S = 180.0
FPS = 1.5

sys.path.insert(0, str(SCRIPTS))
import mitas_pipeline as mp  # noqa: E402  — extract_window / exit_frame_contract / probe


def _ortam() -> dict:
    """Alt süreçlere ÜRETİM ortamını geçir.

    İki gerçek çökme buradan geldi (2026-07-31, ölçüldü):
      * `_jenerik_pool.py` → ModuleNotFoundError: No module named 'core'
        (PYTHONPATH proje kökünü içermiyordu)
      * `master_png_monitor.py` → FileNotFoundError '/opt/mitas/E:\\MITAS/...'
        (MITAS_PROJECT_ROOT yoksa Windows sabitine düşüyor — mitas_roots.py:28
        ile aynı desen, sessizce geçersiz yol üretiyor)
    Pipeline çalışıyor çünkü toplu_kosu.sh `set -a; . mitas.env` yapıyor.
    """
    env = dict(os.environ)
    envf = PROJE / "mitas.env"
    if envf.is_file():
        for satir in envf.read_text(encoding="utf-8", errors="ignore").splitlines():
            satir = satir.strip()
            if not satir or satir.startswith("#") or "=" not in satir:
                continue
            k, _, v = satir.partition("=")
            env.setdefault(k.strip(), v.strip())
    env["MITAS_PROJECT_ROOT"] = str(PROJE)
    mevcut = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{PROJE}:{mevcut}" if mevcut else str(PROJE)
    return env


def _probe_sure(video: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(video)],
                       capture_output=True, text=True, timeout=300)
    return float((r.stdout or "0").strip() or 0)


def kareleri_cikar(video: Path, clip_dir: Path) -> dict:
    """Çıkış (kuyruk) + giriş (baş) karelerini üretim sözleşmesiyle çıkarır."""
    frames = clip_dir / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    dur = _probe_sure(video)
    if dur <= 0:
        raise RuntimeError(f"süre okunamadı: {video.name}")

    # ÇIKIŞ: bağlayıcı sözleşme — 480 sn × 1.5 fps = tam 720 kare
    c_start, c_len, c_bekl = mp.exit_frame_contract(dur, CIKIS_TAIL_S, FPS)
    nf_c = mp.extract_window(video, frames / "cikis", prefix="cikis", fps=FPS,
                             start=c_start, length=c_len, expected_count=c_bekl)

    # GİRİŞ: baş pencere (sözleşme bağlayıcı değil — dedektör kullanır)
    g_len = min(GIRIS_HEAD_S, dur)
    nf_g = mp.extract_window(video, frames / "giris", prefix="giris", fps=FPS,
                             start=0.0, length=g_len,
                             expected_count=mp.expected_frame_count(g_len, FPS))
    return {"sure_sn": round(dur, 2), "cikis_kare": nf_c, "giris_kare": nf_g,
            "cikis_start": round(c_start, 2), "cikis_bekl": c_bekl}


def figo_havuzu(clip_dir: Path, segment: str = "cikis") -> dict:
    """FIGO jenerik havuzu — üretimin kendi betiği, aynı bayraklarla."""
    frames = clip_dir / "frames"
    kaynak = frames / segment
    havuz = frames / f"{segment}_jenerik"
    debug = clip_dir / "jenerik_debug"
    cmd = [str(PY_OCR), str(SCRIPTS / "_jenerik_pool.py"),
           "--frames", str(kaynak), "--pool", str(havuz),
           "--debug-root", str(debug), "--segment", segment]
    t0 = time.perf_counter()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, env=_ortam())
    n = len(list(havuz.glob("*.png"))) if havuz.is_dir() else 0
    return {"rc": r.returncode, "havuz_kare": n,
            "sure_sn": round(time.perf_counter() - t0, 1),
            "stderr": (r.stderr or "")[-400:] or None}


def manifest_tipleme(man: Path) -> dict | None:
    """Master manifest'inden kayan/statik tiplemesini çıkar — İKİ ŞEMA da tanınır.

    Dolaşımda iki farklı manifest şeması var ve alan adları ORTAK DEĞİL:
      * `mode: "ibrahimovic"` (2026-07-29'dan beri BİRİNCİL kompozitör):
        sinif_sayimi / scroll_dy_medyan / ciftler[].sinif / segment / dissolve_kesme
      * `db_compose_master` (eski, hâlâ eski hub'larda):
        runs / strict_runs (S=statik, R=kayan) / strict_scroll_frac / kept_blocks
    Yalnız birini okuyan kod, öteki şemadaki filmlerde SESSİZCE None alır —
    2026-07-31'de tam bu tuzağa düştüm (bkz. tasarım dokümanı §2.4 düzeltmesi).
    """
    if not man.is_file():
        return None
    try:
        m = json.loads(man.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    mode = m.get("mode")
    out: dict = {"mode": mode, "sema": None}

    if m.get("sinif_sayimi") is not None or m.get("scroll_dy_medyan") is not None:
        sayim = m.get("sinif_sayimi") or {}
        ciftler = m.get("ciftler") or []
        kayan = sum(v for k, v in sayim.items() if "scroll" in str(k).lower())
        durak = sum(v for k, v in sayim.items() if "duraksama" in str(k).lower())
        kesme = sum(v for k, v in sayim.items() if "kesme" in str(k).lower())
        out.update({"sema": "ibrahimovic", "sinif_sayimi": sayim,
                    "kayan_cift": kayan, "duraksama_cift": durak, "kesme_cift": kesme,
                    "cift_n": len(ciftler),
                    "scroll_dy_medyan": m.get("scroll_dy_medyan"),
                    "segment": m.get("segment"), "kare": m.get("kare"),
                    "dissolve_kesme": m.get("dissolve_kesme"),
                    "maske_kapsama": m.get("maske_kapsama"), "durum": m.get("durum")})
        # Tek cümlelik sınıf: kayma var mı?
        dy = m.get("scroll_dy_medyan")
        out["sinif"] = ("kayan" if (kayan > 0 or (dy or 0) > 0.5)
                        else ("statik" if durak or kesme else "belirsiz"))
        return out

    runs = m.get("strict_runs") or m.get("runs") or []
    s = sum(1 for r in runs if len(r) > 2 and str(r[2]) == "S")
    r_ = sum(1 for r in runs if len(r) > 2 and str(r[2]) == "R")
    out.update({"sema": "db_compose_master", "statik_run": s, "kayan_run": r_,
                "scroll_frac": m.get("strict_scroll_frac"),
                "kept_blocks": m.get("kept_blocks"), "durum": m.get("status")})
    out["sinif"] = "kayan" if r_ > s else ("statik" if s else "belirsiz")
    return out


def master_uret(clip_dir: Path, base: str) -> dict:
    """İbrahimovic master PNG — üretimin kendi koşucusu (--once)."""
    runner = PROJE / "OCR-worktree" / "master_png_monitor.py"
    t0 = time.perf_counter()
    r = subprocess.run([str(PY_OCR), str(runner), "--once", str(clip_dir), "--base", base],
                       capture_output=True, text=True, timeout=900, env=_ortam())
    cikis = clip_dir / "reading_master_runaware.png"
    giris = clip_dir / "giris_reading_master_runaware.png"
    man = clip_dir / "reading_master_runaware_manifest.json"
    tip = manifest_tipleme(man)
    return {"rc": r.returncode,
            "cikis_master": cikis.is_file(), "giris_master": giris.is_file(),
            "cikis_master_bayt": cikis.stat().st_size if cikis.is_file() else 0,
            "manifest_tipleme": tip,
            "sure_sn": round(time.perf_counter() - t0, 1),
            "stderr": (r.stderr or "")[-400:] or None}


def bir_film(f: dict, kuru: bool) -> dict:
    tid = f["trt_id"]
    mp4_kaynak = Path(f["mp4"])
    ad = mp4_kaynak.stem
    # Başlık: dosya adının son parçası (TRT-ID'den sonrası)
    baslik = ad.split(tid + "-", 1)[1].replace("_", " ").strip() if tid + "-" in ad else tid
    clip_dir = KLIPLER / f"{tid} {baslik}"
    base = f"{tid} {baslik}"

    print(f"\n[{f['sira']:>2}/15] {tid} — {baslik}", flush=True)
    if kuru:
        print(f"    KURU: {clip_dir}")
        return {"trt_id": tid, "kuru": True}

    clip_dir.mkdir(parents=True, exist_ok=True)
    sonuc: dict = {"sira": f["sira"], "trt_id": tid, "baslik": baslik,
                   "clip_dir": str(clip_dir)}
    t0 = time.perf_counter()

    # Staging kopya — SMB kopmasına dayanıklı (toplu_kosu.sh deseni)
    STAGE.mkdir(parents=True, exist_ok=True)
    staged = STAGE / mp4_kaynak.name
    if not mp4_kaynak.is_file():
        sonuc["hata"] = "kaynak yok (mount düşmüş olabilir)"
        print(f"    HATA: {sonuc['hata']}")
        return sonuc
    try:
        print("    staging kopya…", flush=True)
        shutil.copyfile(mp4_kaynak, staged)

        print("    kareler…", flush=True)
        sonuc["kareler"] = kareleri_cikar(staged, clip_dir)
        print(f"      cikis={sonuc['kareler']['cikis_kare']} "
              f"giris={sonuc['kareler']['giris_kare']}", flush=True)

        print("    FIGO havuzu…", flush=True)
        sonuc["havuz"] = figo_havuzu(clip_dir, "cikis")
        print(f"      cikis_jenerik={sonuc['havuz']['havuz_kare']} kare "
              f"({sonuc['havuz']['sure_sn']} sn)", flush=True)

        print("    master PNG…", flush=True)
        sonuc["master"] = master_uret(clip_dir, base)
        t = sonuc["master"].get("manifest_tipleme") or {}
        print(f"      cikis_master={sonuc['master']['cikis_master']} "
              f"tip={t.get('mode')} statik={t.get('statik_run')} kayan={t.get('kayan_run')} "
              f"({sonuc['master']['sure_sn']} sn)", flush=True)
    except Exception as e:  # noqa: BLE001 — bir film çuvallarsa yatak durmaz, o da veridir
        sonuc["hata"] = f"{type(e).__name__}: {e}"[:400]
        print(f"    HATA: {sonuc['hata']}")
    finally:
        staged.unlink(missing_ok=True)

    sonuc["toplam_sn"] = round(time.perf_counter() - t0, 1)
    print(f"    → {sonuc['toplam_sn']} sn", flush=True)
    return sonuc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yatak", default=str(KOK / "yatak_15.json"))
    ap.add_argument("--film", type=int, default=None, help="yalnız bu sıra")
    ap.add_argument("--bas", type=int, default=1)
    ap.add_argument("--son", type=int, default=999)
    ap.add_argument("--kuru", action="store_true")
    a = ap.parse_args()

    yatak = json.loads(Path(a.yatak).read_text(encoding="utf-8"))
    filmler = yatak["filmler"]
    if a.film:
        filmler = [f for f in filmler if f["sira"] == a.film]
    else:
        filmler = [f for f in filmler if a.bas <= f["sira"] <= a.son]

    KLIPLER.mkdir(parents=True, exist_ok=True)
    print(f"=== FAZ 1 · HAM ÇIKTILAR · {len(filmler)} film ===")
    print(f"    yatak kökü : {KLIPLER}")
    print("    model YOK · gemma YOK · OCR YOK · PDF YOK — yalnız kare/havuz/master")

    sonuclar = []
    for f in filmler:
        if (KOK / "DURDUR").exists():
            print("DURDUR görüldü — duruyorum.")
            break
        sonuclar.append(bir_film(f, a.kuru))

    if not a.kuru:
        rap = KOK / "faz1_rapor.json"
        eski = []
        if rap.is_file():
            try:
                eski = json.loads(rap.read_text(encoding="utf-8")).get("filmler", [])
            except Exception:  # noqa: BLE001
                pass
        birlesik = {s["trt_id"]: s for s in eski}
        birlesik.update({s["trt_id"]: s for s in sonuclar})
        rap.write_text(json.dumps({"filmler": list(birlesik.values())},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n→ {rap}")

        hatali = [s for s in sonuclar if s.get("hata")]
        print(f"\nÖZET: {len(sonuclar) - len(hatali)}/{len(sonuclar)} tamam"
              + (f", {len(hatali)} HATA" if hatali else ""))
        for s in hatali:
            print(f"  HATA {s['trt_id']}: {s['hata']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
