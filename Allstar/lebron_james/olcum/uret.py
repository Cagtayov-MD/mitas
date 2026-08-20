#!/usr/bin/env python3
"""Aslına-sadık üretim harness'ı (Görev M2, MITAS_Master_Dup_Kok_Sebep_Plani_v1.md).

Amaç: Üretimin master-PNG kompozisyonunu (OCR-worktree/master_png_monitor.py ->
db_compose_master.compose_reading_runaware) doğrulanmış 110-film havuzunda
BİREBİR yeniden üretmek — dup-metriği/atlas çalışmaları için sağlam bir taban.

SADAKAT — nasıl sağlanıyor:
  1. Kompozisyon parametreleri (args) db_compose_master.py'nin argparse
     kurulumunun bir kopyası + `parser.parse_args([])` ile PROGRAMATİK üretilir
     (sayısal varsayılanlar db_compose_master modülünün READING_* sabitlerinden
     OKUNUR — elle yazılmaz). db_compose_master.py'nin parser'ı main() içinde
     yerel olduğu ve OCR-worktree SALT-OKUNUR olduğu için dışa aktarılamıyor;
     bu yüzden add_argument çağrıları burada bire bir kopyalanır ama DEĞERLER
     modülden gelir. `sadakat_kaniti()` bunu monitor'un make_args()'ıyla
     karşılaştırıp doğrular — bkz. `--selfcheck`.
  2. Kareler üretimle aynı şekilde çıkarılır: ffmpeg -vf fps=1.5, native
     çözünürlük (ölçekleme YOK), c_%05d.png adlandırması, nat_sort_key ile sıralama.
  3. `_compose_reading_seg(frames, args)` OCR-worktree/master_png_monitor.py'den
     doğrudan import edilip çağrılır — kompozisyon mantığı asla kopyalanmaz.
  4. monitor'un TRT-tipi profil kilidi (`_profil_dy_kilidi`) aynen tekrarlanır
     (dc.SLIT_DY_HYBRID global'i FİLM/DİZİ ayrımına göre üretimle aynı değere
     ayarlanmazsa slitscan farklı kanal seçebilir — sessiz sadakat kaybı olurdu).

KÜRESEL KISITLAR (plan dokümanından):
  - venv python: /opt/mitas/venvs/ocr/bin/python
  - harness/kunye_kiyas/* SALT-OKUNUR (yalnız OKUNUR, hiç yazılmaz)
  - OCR-worktree/* SALT-OKUNUR (yalnız import edilir)
  - pkill yasak, git add -A yasak (bu dosyanın kendi commit'i ayrı ele alınır)

Kullanım:
  uret.py --selfcheck                      # sadakat kanıtı (ağ/ffmpeg gerekmez)
  uret.py --film OPERADAKİ_HAYALET         # tek film (ad parçası, hedef_klasör alt-dizesi)
  uret.py --n 5                            # havuzdan ilk 5 film
  uret.py --n 5 --paralel 3                # 3 film eşzamanlı (ayrı süreçler)
  uret.py                                  # tüm havuz (112 film — bkz. not aşağıda)
  uret.py --v2 --n 10 --paralel 3          # Görev M4 F1/F2/F3 fix'leri (MITAS_MASTER_V2=1)
                                            # -> masters_v2/ + veri_ozet_v2.json (legacy masters/ KORUNUR)

ÇIKTI:
  /opt/mitas/data/master_dup/masters/<FİLM>/{reading_master.png, manifest.json, metrik.json}
  --v2 ile: /opt/mitas/data/master_dup/masters_v2/<FİLM>/{...} + veri_ozet_v2.json
  /opt/mitas/data/master_dup/veri_ozet.json (toplu özet)

NOT (film listesi sayımı): Plan dokümanı "110-film havuzu" der; bu betiğin kendi
formülü (eslesme.tsv ∩ dogrulama_sonuc − dislanan) 112 film üretiyor (eslesme.tsv
115 satır - 3 dışlanan = 112). Fark orkestratöre M2 dönüşünde ayrıca raporlanır;
sessizce 110'a yuvarlanmaz — sayı burada olduğu gibi bırakıldı.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# --------------------------------------------------------------------------- #
# Sabit yollar (Küresel Kısıtlar)
# --------------------------------------------------------------------------- #
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # /opt/mitas
if not (PROJECT_ROOT / "OCR-worktree").is_dir():
    # KULE KOPYASI (Allstar/lebron_james/olcum/uret.py): parents[2] burada
    # Allstar'dır — mitas köküsü bir üsttedir. Ölçüm zinciri
    # (saglik -> uret -> monitor -> db_compose_master F1b/F1c) kulede koşsun
    # diye kök çözümlemesi eklendi; harness'teki orijinal davranış değişmez.
    ust = PROJECT_ROOT.parent
    if (ust / "OCR-worktree").is_dir():
        PROJECT_ROOT = ust
assert PROJECT_ROOT.name == "mitas" or (PROJECT_ROOT / "OCR-worktree").is_dir(), (
    f"beklenmeyen proje kökü: {PROJECT_ROOT}"
)

VENI_KUNYE = PROJECT_ROOT / "harness" / "kunye_kiyas" / "veri"
ESLESME_TSV = VENI_KUNYE / "eslesme.tsv"          # SALT-OKUNUR
DOGRULAMA_JSON = VENI_KUNYE / "dogrulama_sonuc.json"  # SALT-OKUNUR
DISLANAN_JSON = VENI_KUNYE / "dislanan.json"      # SALT-OKUNUR

MONITOR_PY = PROJECT_ROOT / "OCR-worktree" / "master_png_monitor.py"  # SALT-OKUNUR (import edilir)

SMB_ROOT = Path(
    "/run/user/1000/gvfs/smb-share:server=depo01cifs.int.trt.net.tr,share=sas_h264"
) / "Film Kapanış"
SMB_URI = "smb://depo01cifs.int.trt.net.tr/sas_h264"

OUT_ROOT = PROJECT_ROOT / "data" / "master_dup"
TMP_ROOT = OUT_ROOT / "_pencere_tmp"
MASTERS_ROOT = OUT_ROOT / "masters"
VERI_OZET_PATH = OUT_ROOT / "veri_ozet.json"

# --v2 (Görev M4): MITAS_MASTER_V2=1 üretim akışı -- eski masters/ SİLİNMEZ/EZİLMEZ,
# çıktılar ayrı masters_v2/ + veri_ozet_v2.json altına yazılır (karşılaştırma tabanı
# korunur). configure_v2() main()'de --v2 görülünce çağrılır; ProcessPoolExecutor
# Linux'ta fork ile başladığından (ex.map çağrılmadan ÖNCE mutasyon yapıldığı için)
# alt süreçler bu güncel modül durumunu miras alır -- ayrıca process_film() kendi
# içinde de env'i açıkça set eder (spawn/başka platform güvencesi, ucuz/idempotent).
V2_MODE = False


def configure_v2(enabled: bool) -> None:
    global V2_MODE, MASTERS_ROOT, VERI_OZET_PATH
    V2_MODE = bool(enabled)
    MASTERS_ROOT = OUT_ROOT / ("masters_v2" if V2_MODE else "masters")
    VERI_OZET_PATH = OUT_ROOT / ("veri_ozet_v2.json" if V2_MODE else "veri_ozet.json")
    # os.environ üzerinden set etmek fork/spawn ayrımından bağımsız çalışır (OS
    # ortam değişkenleri her iki başlatma yönteminde de alt sürece geçer).
    os.environ["MITAS_MASTER_V2"] = "1" if V2_MODE else "0"


FPS = 1.5
KREDISIZ_PENCERE_S = 240.0
ONSET_ON_PENCERE_S = 15.0
GT_FPS = 2.0  # dogrulama_sonuc kare numaraları bu fps'e göre (son-600s çıkarımı)
GT_PENCERE_S = 600.0

DUP_METRIK_PATH = Path(__file__).resolve().parent / "dup_metrik.py"

# gio-copy üstel backoff (M3 bulgusu: 3-paralel yükte kırılgan -- flat 2s retry
# yetersizdi). 3 deneme arası bekleme: 2s -> 5s -> 15s (toplam 4 deneme).
GIO_COPY_BACKOFF_S = [2.0, 5.0, 15.0]


# --------------------------------------------------------------------------- #
# monitor / db_compose_master import (OCR-worktree SALT-OKUNUR — yalnız import)
# --------------------------------------------------------------------------- #
def _import_monitor():
    """master_png_monitor.py'yi (ve onun içinden db_compose_master.py'yi) import eder.

    monitor.py kendi _PR'sini `MITAS_PROJECT_ROOT` env değişkeninden okuyor
    (yoksa Windows-döneminden kalma `E:\\MITAS` varsayılanına düşüyor — Linux'ta
    bu yanlış olurdu). Bu yüzden import ÖNCESİ env'i bu sürecin kendi proje
    köküne ayarlıyoruz; bu, OCR-worktree dosyalarına DOKUNMADAN doğru davranışı
    garantiler (docs/MITAS_Linux_Performans_Denetimi_2026-07-17.md'deki kurulmuş
    desenle tutarlı: "MITAS_PROJECT_ROOT yalnız harness ortamına yüklenir").
    """
    os.environ.setdefault("MITAS_PROJECT_ROOT", str(PROJECT_ROOT))
    spec = importlib.util.spec_from_file_location("master_png_monitor", str(MONITOR_PY))
    mon = importlib.util.module_from_spec(spec)
    sys.modules["master_png_monitor"] = mon
    spec.loader.exec_module(mon)
    return mon


_MON = None
_DC = None


def _monitor():
    global _MON, _DC
    if _MON is None:
        _MON = _import_monitor()
        _DC = _MON.dc
    return _MON


def _dc():
    _monitor()
    return _DC


# --------------------------------------------------------------------------- #
# Argparse SADAKATİ — db_compose_master.py:main()'deki add_argument çağrılarının
# birebir kopyası (parser main() içinde yerel olduğu için başka türlü erişilemez).
# Sayısal READING_* varsayılanları modülden okunur, elle yazılmaz.
# --------------------------------------------------------------------------- #
def _build_parser() -> argparse.ArgumentParser:
    dc = _dc()
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["master", "slit", "mosaic", "both"], default="master")
    p.add_argument("--no-card-split", action="store_true")
    p.add_argument("--card-same-thr", type=int, default=6)
    p.add_argument("--card-min-hold", type=int, default=5)
    p.add_argument("--reading-opening-frames", type=int, default=dc.READING_OPENING_FRAMES)
    p.add_argument("--reading-card-min-hold", type=int, default=dc.READING_CARD_MIN_HOLD)
    p.add_argument("--reading-card-same-thr", type=int, default=dc.READING_CARD_SAME_THR)
    p.add_argument("--reading-early-split-frames", type=int, default=dc.READING_EARLY_SPLIT_FRAMES)
    p.add_argument("--reading-opening-min-hold", type=int, default=dc.READING_OPENING_CARD_MIN_HOLD)
    p.add_argument("--polarity", choices=["auto", "bright", "dark"], default="auto")
    p.add_argument("--deinterlace", action="store_true")
    p.add_argument("--no-dedup", action="store_true")
    p.add_argument("--luma-key", action="store_true")
    p.add_argument("--text-only", action="store_true")
    p.add_argument("--debug", action="store_true")
    p.add_argument("--hash-names", action="store_true")
    p.add_argument("--flip", action="store_true")
    p.add_argument("--tht", type=int, default=22)
    p.add_argument("--min-hold", type=int, default=5)
    p.add_argument("--cut-resp", type=float, default=0.05)
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--flat-out", type=Path, default=None)
    p.add_argument("--seg", choices=["giris", "cikis"], default=None)
    return p


def build_args() -> argparse.Namespace:
    """`parser.parse_args([])` ile programatik varsayılan args (kopyala-yapıştır DEĞİL)."""
    args = _build_parser().parse_args([])
    # monitor.make_args() 'overwrite'ı True'ya SABİTLER (argparse store_true varsayılanı
    # False'tur — CLI'de --overwrite geçmek gerekir). Composition matematiğini etkilemez
    # (yalnız process_film'in "zaten var mı" atlama mantığında okunur, biz onu
    # kullanmıyoruz) ama tam alan-eşitliği için monitor semantiğini burada da uyguluyoruz.
    args.overwrite = True
    return args


def sadakat_kaniti() -> dict:
    """build_args() ile monitor.make_args()'ı alan alan karşılaştırır."""
    mon = _monitor()
    built = vars(build_args())
    ref = vars(mon.make_args())
    only_built = sorted(set(built) - set(ref))
    only_ref = sorted(set(ref) - set(built))
    mismatch = {k: [built[k], ref[k]] for k in built if k in ref and built[k] != ref[k]}
    ok = not only_built and not only_ref and not mismatch
    return {
        "ok": ok,
        "built": built,
        "ref_monitor_make_args": ref,
        "only_in_built": only_built,
        "only_in_ref": only_ref,
        "mismatch": mismatch,
    }


# --------------------------------------------------------------------------- #
# Film havuzu: eslesme.tsv ∩ dogrulama_sonuc(karar bilgisiyle) − dislanan
# (harness/kunye_kiyas/veri/* yalnız OKUNUR)
# --------------------------------------------------------------------------- #
def load_pool() -> list[dict]:
    rows = []
    with ESLESME_TSV.open(encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            kaynak, hedef = line.split("\t", 1)
            rows.append((kaynak, hedef))

    dogrulama = json.loads(DOGRULAMA_JSON.read_text(encoding="utf-8"))
    gt_by_name = {x["film"]: x for x in dogrulama["filmler"]}
    dislanan = set(json.loads(DISLANAN_JSON.read_text(encoding="utf-8"))["filmler"])

    pool = []
    for kaynak, hedef in rows:
        if hedef in dislanan:
            continue
        gt = gt_by_name.get(hedef)
        if gt is None:
            continue  # eslesme'de var, dogrulama_sonuc'ta yok -> havuz dışı
        pool.append({
            "kaynak_dosya": kaynak,
            "hedef_klasor": hedef,
            "gercek_onset": gt.get("gercek_onset"),
            "karar": gt.get("karar"),
            "v5_tahmin": gt.get("v5_tahmin"),
        })
    pool.sort(key=lambda r: r["hedef_klasor"])
    return pool


# --------------------------------------------------------------------------- #
# SMB kaynak erişimi: mount kontrolü + gio copy (bekle-tekrarla)
# --------------------------------------------------------------------------- #
def ensure_mount(timeout_min: int = 30, poll_s: int = 30) -> bool:
    if SMB_ROOT.is_dir():
        return True
    try:
        subprocess.run(["gio", "mount", SMB_URI], capture_output=True, text=True, timeout=60)
    except Exception:
        pass
    deadline = time.time() + timeout_min * 60
    while time.time() < deadline:
        if SMB_ROOT.is_dir():
            return True
        time.sleep(poll_s)
        try:
            subprocess.run(["gio", "mount", SMB_URI], capture_output=True, text=True, timeout=60)
        except Exception:
            pass
    return False


def locate_source(kaynak_dosya: str) -> Path | None:
    direct = SMB_ROOT / kaynak_dosya
    if direct.is_file():
        return direct
    # yedek: düz-değil yerleşim ihtimaline karşı yeniden-ara (havuz büyüdükçe alt klasör olabilir)
    hits = list(SMB_ROOT.rglob(kaynak_dosya))
    return hits[0] if hits else None


def gio_copy(src: Path, dst: Path, backoff: list[float] | None = None) -> bool:
    """gio copy + üstel backoff (M3 bulgusu: 3-paralel yükte flat 2s retry kırılgandı).
    backoff=[2,5,15] -> 4 deneme (1 ilk + 3 tekrar), her tekrar öncesi artan bekleme."""
    delays = list(GIO_COPY_BACKOFF_S if backoff is None else backoff)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    attempts = len(delays) + 1
    for attempt in range(1, attempts + 1):
        r = subprocess.run(
            ["gio", "copy", str(src), str(dst)],
            capture_output=True, text=True,
        )
        if r.returncode == 0 and dst.exists() and dst.stat().st_size > 0:
            return True
        if attempt <= len(delays):
            time.sleep(delays[attempt - 1])
    return False


# --------------------------------------------------------------------------- #
# Pencere hesabı
# --------------------------------------------------------------------------- #
def ffprobe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(r.stdout.strip())


def compute_window(gercek_onset: int, sure_s: float) -> tuple[float, str]:
    """(pencere_başı_saniye, sebep). Pencere sonu her zaman film sonu (ffmpeg EOF'a kadar akar)."""
    if gercek_onset == -1:
        basi = max(0.0, sure_s - KREDISIZ_PENCERE_S)
        return basi, "kredisiz_son240s"
    onset_saniye_abs = max(0.0, sure_s - GT_PENCERE_S) + (gercek_onset / GT_FPS)
    basi = max(0.0, onset_saniye_abs - ONSET_ON_PENCERE_S)
    return basi, "onset-15s"


# --------------------------------------------------------------------------- #
# ffmpeg çıkarım: ÜRETİMLE AYNI (fps=1.5, native çözünürlük, c_%05d.png)
# --------------------------------------------------------------------------- #
def extract_frames(local_mp4: Path, pencere_basi_s: float, out_dir: Path) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.png"):
        old.unlink()
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", f"{pencere_basi_s:.3f}",
        "-i", str(local_mp4),
        "-vf", f"fps={FPS}",
        "-q:v", "3",
        str(out_dir / "c_%05d.png"),
    ]
    subprocess.run(cmd, check=True)
    dc = _dc()
    frames = sorted((str(p) for p in out_dir.glob("*.png")), key=dc.nat_sort_key)
    return frames


# --------------------------------------------------------------------------- #
# dup_metrik (M1) — opsiyonel/idempotent entegrasyon
# --------------------------------------------------------------------------- #
def _load_dup_metrik():
    if not DUP_METRIK_PATH.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("dup_metrik_m2", str(DUP_METRIK_PATH))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "olc"):
            return mod
    except Exception:
        return None
    return None


def compute_metric(png_path: Path) -> dict:
    mod = _load_dup_metrik()
    if mod is None:
        return {
            "status": "bekliyor",
            "not": "dup_metrik.py (M1) henüz mevcut/çağrılabilir değildi; "
                   "bu adım atlandı. Sonraki koşuda (dup_metrik.py hazır olduğunda) "
                   "idempotent olarak tamamlanır — reading_master.png zaten diskte.",
        }
    try:
        return mod.olc(str(png_path))
    except Exception as exc:  # noqa: BLE001
        return {"status": "hata", "hata": f"{type(exc).__name__}: {exc}"}


# --------------------------------------------------------------------------- #
# Tek film uçtan uca
# --------------------------------------------------------------------------- #
def process_film(row: dict, *, keep_tmp: bool = False) -> dict:
    hedef = row["hedef_klasor"]
    kaynak = row["kaynak_dosya"]
    t0 = time.time()
    result = {"film": hedef, "kaynak_dosya": kaynak, "gercek_onset": row.get("gercek_onset")}

    film_tmp = TMP_ROOT / hedef
    local_mp4 = film_tmp / "kaynak.mp4"
    frames_dir = film_tmp / "frames"
    masters_dir = MASTERS_ROOT / hedef

    try:
        if not ensure_mount():
            result["status"] = "hata"
            result["hata"] = "smb mount bulunamadı (30dk bekleme sonunda)"
            return result

        src = locate_source(kaynak)
        if src is None:
            result["status"] = "hata"
            result["hata"] = f"kaynak dosya bulunamadı: {kaynak}"
            return result

        if not gio_copy(src, local_mp4):
            result["status"] = "hata"
            result["hata"] = f"gio copy {len(GIO_COPY_BACKOFF_S) + 1} denemede başarısız (backoff {GIO_COPY_BACKOFF_S})"
            return result

        sure_s = ffprobe_duration(local_mp4)
        pencere_basi, pencere_sebep = compute_window(row.get("gercek_onset"), sure_s)
        result["sure_s"] = round(sure_s, 3)
        result["pencere_basi_s"] = round(pencere_basi, 3)
        result["pencere_sebep"] = pencere_sebep

        frames = extract_frames(local_mp4, pencere_basi, frames_dir)
        result["frame_sayisi"] = len(frames)
        if not frames:
            result["status"] = "hata"
            result["hata"] = "ffmpeg 0 kare üretti"
            return result

        mon = _monitor()
        dc = _dc()
        dc.clear_cache()
        del dc.HYBRID_LOG[:]
        mon._profil_dy_kilidi(Path(hedef))  # üretimle aynı FİLM/DİZİ dy-kanalı kilidi
        args = build_args()

        master, info = mon._compose_reading_seg(frames, args)
        manifest = info.pop("manifest", None) or info

        masters_dir.mkdir(parents=True, exist_ok=True)
        png_path = masters_dir / "reading_master.png"
        if master is not None:
            dc.wr(png_path, master)
            result["status"] = "OK"
        else:
            result["status"] = "NO_OUTPUT"
            result["hata"] = manifest.get("status", "NO_OUTPUT") if isinstance(manifest, dict) else "NO_OUTPUT"

        result["mode"] = manifest.get("mode") if isinstance(manifest, dict) else None
        result["strict_scroll_frac"] = manifest.get("strict_scroll_frac") if isinstance(manifest, dict) else None
        result["kept_blocks"] = manifest.get("kept_blocks") if isinstance(manifest, dict) else None
        result["size"] = manifest.get("size") if isinstance(manifest, dict) else None

        provenance = {
            "kaynak_dosya": kaynak,
            "hedef_klasor": hedef,
            "sure_s": result["sure_s"],
            "pencere_basi_s": result["pencere_basi_s"],
            "pencere_sebep": pencere_sebep,
            "frame_sayisi": len(frames),
            "src_first": Path(frames[0]).name,
            "src_last": Path(frames[-1]).name,
            "args": vars(args),
            "slit_dy_hybrid": dc.SLIT_DY_HYBRID,
            "mitas_master_v2": os.environ.get("MITAS_MASTER_V2", "0"),
        }
        manifest_out = dict(manifest) if isinstance(manifest, dict) else {"raw_info": manifest}
        manifest_out["_uret_provenance"] = provenance
        (masters_dir / "manifest.json").write_text(
            json.dumps(manifest_out, ensure_ascii=False, indent=1), encoding="utf-8"
        )

        if master is not None:
            metrik = compute_metric(png_path)
            (masters_dir / "metrik.json").write_text(
                json.dumps(metrik, ensure_ascii=False, indent=1), encoding="utf-8"
            )
            result["metrik_status"] = metrik.get("status", "ok" if "dup_oran" in metrik else "?")
            if "dup_oran" in metrik:
                result["dup_oran"] = metrik["dup_oran"]

        result["elapsed_s"] = round(time.time() - t0, 1)
        return result
    except Exception as exc:  # noqa: BLE001
        import traceback
        result["status"] = "hata"
        result["hata"] = f"{type(exc).__name__}: {exc}"
        result["trace"] = traceback.format_exc()[-1500:]
        result["elapsed_s"] = round(time.time() - t0, 1)
        return result
    finally:
        if not keep_tmp:
            shutil.rmtree(film_tmp, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Toplu çalıştırma
# --------------------------------------------------------------------------- #
def _worker(row):
    return process_film(row)


def run(rows: list[dict], paralel: int = 1) -> list[dict]:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    MASTERS_ROOT.mkdir(parents=True, exist_ok=True)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    results = []
    if paralel <= 1 or len(rows) <= 1:
        for row in rows:
            r = process_film(row)
            print(f"[{r['status']:9}] {r['film'][:60]:60} "
                  f"{r.get('elapsed_s', '?')}s  mode={r.get('mode')}  "
                  f"kept_blocks={r.get('kept_blocks')}  size={r.get('size')}", flush=True)
            results.append(r)
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=paralel) as ex:
            for r in ex.map(_worker, rows):
                print(f"[{r['status']:9}] {r['film'][:60]:60} "
                      f"{r.get('elapsed_s', '?')}s  mode={r.get('mode')}  "
                      f"kept_blocks={r.get('kept_blocks')}  size={r.get('size')}", flush=True)
                results.append(r)

    VERI_OZET_PATH.write_text(
        json.dumps({"n": len(results), "sonuclar": results}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    return results


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--film", default=None, help="hedef_klasör alt-dizesi -> tek film")
    ap.add_argument("--n", type=int, default=None, help="havuzdan ilk N film")
    ap.add_argument("--paralel", type=int, default=1, help="eşzamanlı film sayısı (ayrı süreç)")
    ap.add_argument("--selfcheck", action="store_true", help="sadakat kanıtını yazdır ve çık (ağ/ffmpeg gerekmez)")
    ap.add_argument(
        "--v2", action="store_true",
        help=(
            "MITAS_MASTER_V2=1 (Görev M4 F1/F2/F3 fix'leri) ile üret; çıktılar "
            "masters_v2/<FİLM>/ + veri_ozet_v2.json altına yazılır (legacy masters/ "
            "KORUNUR -- karşılaştırma tabanı)"
        ),
    )
    args = ap.parse_args(argv)

    configure_v2(args.v2)

    if args.selfcheck:
        proof = sadakat_kaniti()
        print(json.dumps(proof, ensure_ascii=False, indent=1))
        return 0 if proof["ok"] else 1

    pool = load_pool()
    if args.film:
        pool = [r for r in pool if args.film in r["hedef_klasor"]]
    if args.n:
        pool = pool[: args.n]

    if not pool:
        print("Havuzda eşleşen film yok.", file=sys.stderr)
        return 1

    print(f"=== uret.py: {len(pool)} film işlenecek (paralel={args.paralel}, v2={V2_MODE}) ===", flush=True)
    results = run(pool, paralel=args.paralel)
    ok = sum(1 for r in results if r.get("status") == "OK")
    print(f"\n-> {VERI_OZET_PATH}  ({ok}/{len(results)} OK)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
