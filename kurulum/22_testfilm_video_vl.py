#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TEST_FILM VIDEO-VL: /home/cagatay/test_film MP4 filmleri → tespit_v5 (jenerik-başı)
→ 60s+5s-bindirmeli sessiz klipler → Qwen3-VL-8B ham transkript.

21_depo10_test.py uyarlaması (2026-07-23). Farklar:
  * mitas.env yüklenir (eksik anahtarlar) + MITAS_JENERIK_V5=1 ASSERT — v5 sessiz kapalı
    kalamaz (DEPO-10 v5-öncesiydi; bu koşunun amacı yeni dedektör).
  * Çalışma dizini ASCII slug (boşluk/apostrof → _pipe_video_vl file:// URL'i patlatır).
  * Yeniden başlatılabilir: jenerik_detection.json / video_vl_okuma.txt varsa faz atlanır.
  * Her film sonrası checkpoint (_sonuc.json) + artımlı rapor — çökmede sonuç kaybolmaz.
  * TimeoutExpired dahil her hata film-bazında yutulur; koşu durmaz.
  * Disk: faz1 sonrası frames/cikis + pool silinir (--keep-frames ya da --films pilotunda kalır).

Kullanım:
  pilot:  venvs/core/bin/python kurulum/22_testfilm_video_vl.py --films 1950-0016,1980-0186,2024-1315
  tümü:   venvs/core/bin/python kurulum/22_testfilm_video_vl.py
  liste:  ... --list   (hangi filmler dahil, slug'larıyla)
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

KOK = Path("/opt/mitas")
KAYNAK = Path("/home/cagatay/test_film")
CALISMA_KOK = KOK / "filmtest" / "test_film_vl"
PY_OCR = KOK / "venvs" / "ocr" / "bin" / "python"
RAPOR = KOK / "outputs" / "TESTFILM_VL_RAPOR_20260723.md"
CHECKPOINT = CALISMA_KOK / "_sonuc.json"
FPS, TAIL = 1.5, 600.0

TR_MAP = str.maketrans("İIŞĞÜÖÇışğüöçÂâÎîÛû", "IISGUOCisguocAaIiUu")


def _env_yukle() -> None:
    """mitas.env'den YALNIZ eksik anahtarları tamamla (source edilmiş env her zaman kazanır)."""
    p = KOK / "mitas.env"
    if not p.exists():
        return
    try:
        for satir in p.read_text(encoding="utf-8", errors="replace").splitlines():
            satir = satir.strip()
            if not satir or satir.startswith("#") or "=" not in satir:
                continue
            k, v = satir.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except OSError:
        pass


def filmleri_bul() -> list[Path]:
    """Sadece MP4 filmler — dizi/tester/upscale hariç (Çağatay kararı, 2026-07-23)."""
    secilen = []
    for v in sorted(KAYNAK.glob("*.mp4")):
        ad = v.name
        if ad.startswith("web_client_") or ad == "tester.mp4" or ad.startswith("need upscale"):
            continue
        secilen.append(v)
    return secilen


def kunye_coz(stem: str) -> tuple[str, str]:
    """Dosya adından (katalog-id, başlık). Örn ...S28_1950-0016-1-0000-00-1-KANSAS'LI_SÜVARİLER
    → ('1950-0016', "KANSAS'LI_SÜVARİLER"). Eşleşmezse ('', stem)."""
    m = re.search(r"(\d{4}-\d{4})-\d-\d{2,4}-\d{2}-[01]-(.+)$", stem)
    if m:
        return m.group(1), m.group(2)
    return "", stem


def slugla(stem: str) -> str:
    """ASCII-güvenli çalışma-dizini adı: katalog + translit başlık.
    Boşluk/apostrof _pipe_video_vl'nin file:// URL'inde patlar — tam translit."""
    katalog, baslik = kunye_coz(stem)
    duz = baslik.translate(TR_MAP)
    duz = unicodedata.normalize("NFKD", duz).encode("ascii", "ignore").decode("ascii")
    duz = re.sub(r"[^A-Za-z0-9]+", "_", duz).strip("_")
    return f"{katalog}_{duz}" if katalog else duz


def run(cmd, timeout=3600, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)


def sure(v: Path) -> float:
    o = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(v)], 120)
    return float(o.stdout.strip())


def faz1(video: Path, calisma: Path, force: bool, temizle: bool) -> dict:
    """Kare çıkarımı + tespit_v5 dedektörü. Döner: manifest dict (start_pos, engine vs.)."""
    frames = calisma / "frames" / "cikis"
    pool = calisma / "frames" / "cikis_jenerik"
    dbg = calisma / "jdebug"
    j = calisma / "frames" / "jenerik_detection.json"

    if j.is_file() and not force:
        m = json.loads(j.read_text(encoding="utf-8"))
        m["_atlandi"] = True
    else:
        frames.mkdir(parents=True, exist_ok=True)
        dur = sure(video)
        cstart = max(0.0, dur - TAIL)
        if not list(frames.glob("*.png")):
            r = run(["ffmpeg", "-v", "error", "-ss", f"{cstart:.2f}", "-i", str(video),
                     "-vf", f"fps={FPS}", "-q:v", "2", str(frames / "cikis_%06d.png")], 1800)
            if r.returncode != 0:
                return {"hata": f"ffmpeg: {r.stderr[:200]}"}
        r = run([str(PY_OCR), str(KOK / "scripts" / "_jenerik_pool.py"),
                 "--frames", str(frames), "--pool", str(pool), "--debug-root", str(dbg)],
                1800, cwd=str(KOK))
        if not j.is_file():
            return {"hata": f"detector rc={r.returncode}: {(r.stderr or r.stdout)[-200:]}"}
        m = json.loads(j.read_text(encoding="utf-8"))

    dur = sure(video)
    m["_sure"] = dur
    m["_cstart"] = max(0.0, dur - TAIL)

    # Disk: kareler + pool işini bitirdi — sil (jenerik_detection.json + jdebug KALIR).
    # faz2 yalnız JSON'u ve kaynak videoyu okur; karelere ihtiyaç yok.
    if temizle:
        shutil.rmtree(frames, ignore_errors=True)
        shutil.rmtree(pool, ignore_errors=True)
    return m


def faz2(video: Path, calisma: Path, force: bool) -> tuple[int, str]:
    okuma = calisma / "video_vl" / "video_vl_okuma.txt"
    if okuma.is_file() and okuma.stat().st_size > 0 and not force:
        return 0, "atlandı (video_vl_okuma.txt mevcut)"
    r = run([str(PY_OCR), str(KOK / "scripts" / "_pipe_video_vl.py"),
             "--clip", str(calisma), "--video", str(video)], 5400, cwd=str(KOK))
    return r.returncode, (r.stdout or "")[-400:]


def vllm(komut: str) -> bool:
    r = subprocess.run(["bash", str(KOK / "kurulum" / "vlm_sunucu.sh"), komut],
                       capture_output=True, text=True, timeout=600)
    return r.returncode == 0


def checkpoint_yukle() -> dict:
    if CHECKPOINT.is_file():
        try:
            return json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return {}


def checkpoint_yaz(sonuc: dict) -> None:
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT.write_text(json.dumps(sonuc, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")


def rapor_yaz(sonuc: dict) -> None:
    """Checkpoint'ten raporu SIFIRDAN kur (artımlı çağrılır — çökmede son hali kalır)."""
    tamam, kredisiz, hatali = [], [], []
    for slug, s in sonuc.items():
        if s.get("hata") or (s.get("faz2_rc") not in (None, 0, 5)):
            hatali.append((slug, s))
        elif s.get("start_pos") is None:
            kredisiz.append((slug, s))
        else:
            tamam.append((slug, s))

    R = ["# TEST_FILM Canlı Koşu — tespit_v5 → 60s klipler → Qwen3-VL-8B",
         "",
         f"Kaynak: /home/cagatay/test_film · {time.strftime('%Y-%m-%d %H:%M')}",
         "",
         f"**Özet:** {len(sonuc)} film işlendi — {len(tamam)} transkript, "
         f"{len(kredisiz)} jenerik-bulunamadı, {len(hatali)} hata.", ""]

    for slug, s in tamam:
        R.append(f"## {s.get('katalog', '?')} {s.get('baslik', slug)}")
        sn = s.get("baslangic_s")
        R.append(f"- jenerik başlangıcı: **{sn:.0f}s**" if sn is not None else "- jenerik başlangıcı: ?")
        R.append(f"  (film {s.get('sure_s', 0):.0f}s; start_pos={s.get('start_pos')}; "
                 f"dedektör={s.get('engine', '?')})")
        if s.get("faz2_rc") is not None:
            R.append(f"- {s.get('n_parca', 0)} parça, video-vl rc={s['faz2_rc']}"
                     + (" (kısmi — bazı parçalar hatalı)" if s["faz2_rc"] == 5 else ""))
            okuma = Path(s.get("okuma_yolu", ""))
            if okuma.is_file():
                metin = okuma.read_text(encoding="utf-8")
                R.append(f"- okuma: {len(metin)} karakter → `{okuma}`")
                R.append("\n```\n" + metin[:1200]
                         + ("\n... (devamı dosyada)" if len(metin) > 1200 else "") + "\n```")
        R.append("")

    if kredisiz:
        R += ["## Jenerik bulunamadı (start_pos yok — v5 'kredi yok' kararı ya da pencere dışı)", ""]
        for slug, s in kredisiz:
            R.append(f"- {s.get('katalog', '?')} {s.get('baslik', slug)} "
                     f"(dedektör={s.get('engine', '?')}, status={s.get('status', '?')})")
        R.append("")

    if hatali:
        R += ["## Hatalı filmler", ""]
        for slug, s in hatali:
            neden = s.get("hata") or f"video-vl rc={s.get('faz2_rc')}"
            R.append(f"- {s.get('katalog', '?')} {s.get('baslik', slug)}: {neden}")
        R.append("")

    RAPOR.write_text("\n".join(R) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="test_film → v5 onset → video-VL transkript")
    ap.add_argument("--films", default=None,
                    help="virgüllü alt-küme (slug/katalog alt-dizesi, örn 1950-0016,SON_METRO)")
    ap.add_argument("--force", action="store_true", help="mevcut çıktıları yok say, yeniden koş")
    ap.add_argument("--keep-frames", action="store_true", help="faz1 sonrası kareleri SİLME")
    ap.add_argument("--list", action="store_true", help="dahil filmleri listele ve çık")
    a = ap.parse_args()

    _env_yukle()
    if os.environ.get("MITAS_JENERIK_V5", "0").strip().lower() in ("0", "false", "off", "no"):
        print("HATA: MITAS_JENERIK_V5 aktif değil — bu koşunun amacı v5 dedektörü. "
              "mitas.env'i kontrol et.")
        return 1

    filmler = filmleri_bul()
    if a.films:
        anahtarlar = [x.strip().lower() for x in a.films.split(",") if x.strip()]
        filmler = [v for v in filmler
                   if any(k in slugla(v.stem).lower() for k in anahtarlar)]
    if not filmler:
        print("film yok (filtre çok mu dar?)")
        return 1

    pilot = bool(a.films)
    temizle = not (a.keep_frames or pilot)
    print(f"{len(filmler)} film · v5=1 · pilot={pilot} · frames-temizlik={temizle}")
    for v in filmler:
        print(f"  {slugla(v.stem)}  ←  {v.name}")
    if a.list:
        return 0

    CALISMA_KOK.mkdir(parents=True, exist_ok=True)
    sonuc = checkpoint_yukle()

    print("\n########## FAZ-1: tespit_v5 dedektörü ##########")
    for v in filmler:
        slug = slugla(v.stem)
        katalog, baslik = kunye_coz(v.stem)
        calisma = CALISMA_KOK / slug
        s = sonuc.setdefault(slug, {"film": str(v), "katalog": katalog, "baslik": baslik})
        t = time.time()
        try:
            m = faz1(v, calisma, a.force, temizle)
        except subprocess.TimeoutExpired:
            m = {"hata": "faz1 süre aşımı"}
        except Exception as e:  # noqa: BLE001
            m = {"hata": f"faz1 {type(e).__name__}: {str(e)[:150]}"}
        if "hata" in m:
            s["hata"] = m["hata"]
            print(f"  {slug}: HATA {m['hata'][:100]}")
        else:
            s.pop("hata", None)
            sp = m.get("start_pos")
            s.update({"start_pos": sp, "engine": m.get("engine"), "status": m.get("status"),
                      "sure_s": m["_sure"],
                      "baslangic_s": (m["_cstart"] + sp / FPS) if sp is not None else None})
            etiket = f"start_pos={sp} → {s['baslangic_s']:.0f}s" if sp is not None else "jenerik bulunamadı"
            atl = " (atlandı)" if m.get("_atlandi") else ""
            print(f"  {slug}: {etiket} [{m.get('engine')}]{atl} ({time.time()-t:.0f}s)")
        checkpoint_yaz(sonuc)
        rapor_yaz(sonuc)

    print("\n########## FAZ-2: video-VL okuma (vlm_sunucu) ##########")
    if not vllm("start"):
        print("HATA: vLLM sunucusu kalkmadı — log: kurulum/logs/vlm_sunucu.log")
        rapor_yaz(sonuc)
        return 2
    try:
        for v in filmler:
            slug = slugla(v.stem)
            calisma = CALISMA_KOK / slug
            s = sonuc.get(slug, {})
            if s.get("hata") or s.get("start_pos") is None:
                continue
            t = time.time()
            try:
                rc, out = faz2(v, calisma, a.force)
            except subprocess.TimeoutExpired:
                rc, out = -1, "faz2 süre aşımı"
            except Exception as e:  # noqa: BLE001
                rc, out = -1, f"faz2 {type(e).__name__}: {str(e)[:150]}"
            vdir = calisma / "video_vl"
            s["faz2_rc"] = rc
            s["n_parca"] = len(list(vdir.glob("parca_*.mp4"))) if vdir.is_dir() else 0
            s["okuma_yolu"] = str(vdir / "video_vl_okuma.txt")
            if rc == -1:
                s["hata"] = out
            print(f"  {slug}: rc={rc}, {s['n_parca']} parça ({time.time()-t:.0f}s)")
            checkpoint_yaz(sonuc)
            rapor_yaz(sonuc)
    finally:
        vllm("stop")

    rapor_yaz(sonuc)
    print(f"\nRAPOR: {RAPOR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
