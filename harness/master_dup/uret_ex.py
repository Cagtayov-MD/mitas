#!/usr/bin/env python3
"""Ex_Frame büyük-koşu adaptörü (Görev M7, MITAS_Master_Dup_Kok_Sebep_Plani_v1.md).

Amaç: `/home/cagatay/Ex_Frame/<slug>-exit_frames/` (427 film; kareler
`exit_%06d.png`, ~1.25fps, 600x480, JENERİK BAŞLANGICINDAN film sonuna --
onset adımı YOK, klasördeki TÜM kareler pencere) üzerinde `uret.py`'nin (M2)
kompozisyon çekirdeğini AYNEN yeniden kullanarak (kopyalamadan, İMPORT ederek)
`reading_master.png` üretir.

SADAKAT -- nasıl sağlanıyor: bu dosya `uret.py`yi bir modül olarak import eder
ve onun `build_args()` (monitor'un argparse varsayılanlarından programatik
kurulmuş args), `_monitor()`/`_dc()` (OCR-worktree/master_png_monitor.py'nin
`_compose_reading_seg` fonksiyonu -- SALT-OKUNUR, yalnız import edilir) ve
`compute_metric()` (dup_metrik.py M1 entegrasyonu) fonksiyonlarını ÇAĞIRIR.
Kompozisyon mantığının BİR SATIRI bile burada kopyalanmaz.

Ex_Frame ile SMB/eslesme.tsv/dogrulama_sonuc havuzu arasındaki fark:
  - girdi: yerel kare klasörü (indirme/ffmpeg YOK -- kareler zaten disk üzerinde)
  - kare listesi: sorted(glob exit_*.png) (uret.py'nin ffmpeg çıktısı yerine)
  - pencere: YOK -- klasördeki TÜM kareler kompozisyona girer (onset adımı
    Ex_Frame kesim hattında -- harness/kunye_kiyas/exit_kesim/ -- zaten yapıldı)
  - MITAS_MASTER_V2 HER ZAMAN 1 (F1/F1b/F1c fix'leri taban ölçümüne dahil --
    plan M7 flag-sonrası taban koşusu istiyor, flag-kapalı bit-parite değil)

KÜRESEL KISITLAR (plan dokümanından):
  - venv python: /opt/mitas/venvs/ocr/bin/python
  - harness/kunye_kiyas/* bu dosyanın HİÇ dokunmadığı bir alan (kullanılmıyor bile)
  - OCR-worktree/* SALT-OKUNUR (yalnız uret.py üzerinden dolaylı import)
  - pkill yasak, git add -A yasak

Kullanım:
  uret_ex.py --film apaci                  # slug alt-dizesi -> tek film
  uret_ex.py --n 5                         # havuzdan ilk 5 film (ad sırasıyla)
  uret_ex.py --n 5 --paralel 3             # 3 film eşzamanlı (ayrı süreç)
  uret_ex.py --paralel 4                   # TÜM 427 film
  uret_ex.py --force                       # idempotent atlamayı yoksay, yeniden üret

ÇIKTI:
  /opt/mitas/data/master_ex/<slug>/{reading_master.png, manifest.json, metrik.json}
  /opt/mitas/data/master_ex/ozet_ex.json (toplu özet)

İDEMPOTENT: bir filmin masters_dir'i zaten TAM bir sonuç içeriyorsa (manifest.json
status alanı OK/NO_OUTPUT + OK ise reading_master.png + metrik.json da mevcut ve
okunabilir) o film YENİDEN İŞLENMEZ -- var olan sonuç ozet_ex.json'a aynen taşınır
(--force ile bu davranış bypass edilir).
"""
from __future__ import annotations

import argparse
import concurrent.futures
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

# --------------------------------------------------------------------------- #
# Sabit yollar
# --------------------------------------------------------------------------- #
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # /opt/mitas
assert PROJECT_ROOT.name == "mitas" or (PROJECT_ROOT / "OCR-worktree").is_dir(), (
    f"beklenmeyen proje kökü: {PROJECT_ROOT}"
)

EX_FRAME_ROOT = Path("/home/cagatay/Ex_Frame")
EX_SUFFIX = "-exit_frames"

URET_PY = Path(__file__).resolve().parent / "uret.py"  # M2 kompozisyon çekirdeği (import edilir)

OUT_ROOT = PROJECT_ROOT / "data" / "master_ex"
OZET_PATH = OUT_ROOT / "ozet_ex.json"


# --------------------------------------------------------------------------- #
# uret.py'yi modül olarak import et (kopyalama değil -- build_args/_monitor/
# _dc/compute_metric/configure_v2 buradan çağrılır). Her süreçte (ana + fork
# edilen worker'lar) tembel/önbellekli import.
# --------------------------------------------------------------------------- #
_URET = None


def _uret_core():
    global _URET
    if _URET is None:
        spec = importlib.util.spec_from_file_location("uret_core_ex", str(URET_PY))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _URET = mod
    return _URET


# --------------------------------------------------------------------------- #
# Film havuzu: Ex_Frame/<slug>-exit_frames/ dizinleri
# --------------------------------------------------------------------------- #
def list_films() -> list[str]:
    if not EX_FRAME_ROOT.is_dir():
        return []
    slugs = [
        p.name[: -len(EX_SUFFIX)]
        for p in EX_FRAME_ROOT.iterdir()
        if p.is_dir() and p.name.endswith(EX_SUFFIX)
    ]
    slugs.sort()
    return slugs


def source_dir_for(slug: str) -> Path:
    return EX_FRAME_ROOT / f"{slug}{EX_SUFFIX}"


def frames_for(slug: str) -> list[str]:
    """kare listesi = sorted(glob exit_*.png) (plan M7 talimatı, birebir)."""
    d = source_dir_for(slug)
    return sorted(str(p) for p in d.glob("exit_*.png"))


# --------------------------------------------------------------------------- #
# İdempotent atlama: mevcut+tam çıktı yeniden üretilmez
# --------------------------------------------------------------------------- #
def _load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_cached_result(slug: str, masters_dir: Path) -> dict | None:
    """masters_dir'de zaten TAM bir sonuç varsa onu ozet şemasına çevirip döner;
    eksik/bozuksa None (yeniden işlensin)."""
    manifest = _load_json(masters_dir / "manifest.json")
    if manifest is None:
        return None
    status = manifest.get("status")
    if status not in ("OK", "NO_OUTPUT"):
        return None

    prov = manifest.get("_uret_provenance", {}) if isinstance(manifest, dict) else {}
    result = {
        "film": slug,
        "status": status,
        "frame_sayisi": prov.get("frame_sayisi"),
        "mode": manifest.get("mode"),
        "strict_scroll_frac": manifest.get("strict_scroll_frac"),
        "kept_blocks": manifest.get("kept_blocks"),
        "size": manifest.get("size"),
        "cached": True,
    }
    if status == "OK":
        png_path = masters_dir / "reading_master.png"
        metrik_path = masters_dir / "metrik.json"
        if not png_path.is_file():
            return None
        metrik = _load_json(metrik_path)
        if metrik is None:
            return None
        result["metrik_status"] = metrik.get("status", "ok" if "dup_oran" in metrik else "?")
        if "dup_oran" in metrik:
            result["dup_oran"] = metrik["dup_oran"]
    return result


# --------------------------------------------------------------------------- #
# Tek film uçtan uca
# --------------------------------------------------------------------------- #
def process_film_ex(slug: str, out_root: Path | None = None) -> dict:
    t0 = time.time()
    result: dict = {"film": slug}
    source_dir = source_dir_for(slug)
    masters_dir = (Path(out_root) if out_root is not None else OUT_ROOT) / slug

    try:
        uret = _uret_core()
        uret.configure_v2(True)  # MITAS_MASTER_V2=1 -- taban koşusu F1/F1b/F1c fix'leri dahil ölçer

        if not source_dir.is_dir():
            result["status"] = "hata"
            result["hata"] = f"kaynak klasör yok: {source_dir}"
            return result

        frames = frames_for(slug)
        result["frame_sayisi"] = len(frames)
        if not frames:
            result["status"] = "hata"
            result["hata"] = "exit_*.png bulunamadı"
            return result

        mon = uret._monitor()
        dc = uret._dc()
        dc.clear_cache()
        del dc.HYBRID_LOG[:]
        # Ex_Frame slug adlarında TRT-tip regex ("\d{4}-\d{3,4}-(\d)-...") genelde
        # eşleşmez -> dc.SLIT_DY_HYBRID mevcut (env varsayılanı) değerinde kalır;
        # çağrı yine de üretimle simetri için yapılır (bkz. uret.py process_film).
        mon._profil_dy_kilidi(Path(slug))
        args = uret.build_args()

        master, info = mon._compose_reading_seg(frames, args)
        manifest = info.pop("manifest", None) or info

        masters_dir.mkdir(parents=True, exist_ok=True)
        png_path = masters_dir / "reading_master.png"
        pano_path = masters_dir / "panoramic_master.png"
        if master is not None:
            dc.wr(png_path, master)
            
            # --- YENI: Panoramik Üretim Hattı ---
            try:
                import sys
                if "/home/cagatay/Programlar/mitas/OCR-worktree" not in sys.path:
                    sys.path.append("/home/cagatay/Programlar/mitas/OCR-worktree")
                from panoramic_composer import process_panorama
                process_panorama(str(png_path), str(pano_path))
            except Exception as e:
                print(f"[!] Panoramik motor hatasi: {e}")
            # ------------------------------------

            result["status"] = "OK"
        else:
            result["status"] = "NO_OUTPUT"
            result["hata"] = manifest.get("status", "NO_OUTPUT") if isinstance(manifest, dict) else "NO_OUTPUT"

        result["mode"] = manifest.get("mode") if isinstance(manifest, dict) else None
        result["strict_scroll_frac"] = manifest.get("strict_scroll_frac") if isinstance(manifest, dict) else None
        result["kept_blocks"] = manifest.get("kept_blocks") if isinstance(manifest, dict) else None
        result["size"] = manifest.get("size") if isinstance(manifest, dict) else None

        provenance = {
            "slug": slug,
            "source_dir": str(source_dir),
            "frame_sayisi": len(frames),
            "src_first": Path(frames[0]).name,
            "src_last": Path(frames[-1]).name,
            "args": vars(args),
            "slit_dy_hybrid": dc.SLIT_DY_HYBRID,
            "mitas_master_v2": os.environ.get("MITAS_MASTER_V2", "0"),
            "kaynak_fps_notu": "~1.25fps (Ex_Frame exit_frames) -- uret.py'nin ffmpeg fps=1.5 "
                               "çıkarımı YOK, kareler zaten diskte bu hızda üretilmişti",
        }
        manifest_out = dict(manifest) if isinstance(manifest, dict) else {"raw_info": manifest}
        manifest_out["_uret_provenance"] = provenance
        (masters_dir / "manifest.json").write_text(
            json.dumps(manifest_out, ensure_ascii=False, indent=1), encoding="utf-8"
        )

        if master is not None:
            metrik = uret.compute_metric(png_path)
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


# --------------------------------------------------------------------------- #
# Toplu çalıştırma
# --------------------------------------------------------------------------- #
def _worker(gorev: tuple[str, str]) -> dict:
    """ProcessPoolExecutor worker'ı -- (slug, out_root) çifti açıkça geçirilir
    (env/fork-kalıtımına GÜVENMEZ; --paralel ile ayrı süreçlerde de doğru kök)."""
    slug, out_root = gorev
    return process_film_ex(slug, Path(out_root))


def _fmt(r: dict, *, tag: str = "") -> str:
    return (
        f"[{r.get('status', '?'):9}] {r['film'][:55]:55} {tag}"
        f"{r.get('elapsed_s', '?')}s  mode={r.get('mode')}  "
        f"kept_blocks={r.get('kept_blocks')}  size={r.get('size')}"
    )


def run(
    slugs: list[str],
    paralel: int = 1,
    force: bool = False,
    ozet_yolu: Path | None = None,
    out_root: Path | None = None,
) -> list[dict]:
    """out_root verilmezse mevcut davranış (data/master_ex) AYNEN korunur -- yeni
    parametre geriye-uyumlu (kök-sebep fix doğrulaması: /opt/mitas/data/master_ex_modfix/,
    mevcut master_ex EZILMEZ -- sadakat ölçümü onu okuyor)."""
    kok = Path(out_root) if out_root is not None else OUT_ROOT
    kok.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    to_process: list[str] = []

    for slug in slugs:
        masters_dir = kok / slug
        cached = None if force else load_cached_result(slug, masters_dir)
        if cached is not None:
            print(_fmt(cached, tag="(atlandı/önbellek) "), flush=True)
            results.append(cached)
        else:
            to_process.append(slug)

    if to_process:
        if paralel <= 1 or len(to_process) <= 1:
            for slug in to_process:
                r = process_film_ex(slug, kok)
                print(_fmt(r), flush=True)
                results.append(r)
        else:
            with concurrent.futures.ProcessPoolExecutor(max_workers=paralel) as ex:
                gorevler = [(slug, str(kok)) for slug in to_process]
                for r in ex.map(_worker, gorevler):
                    print(_fmt(r), flush=True)
                    results.append(r)

    order = {slug: i for i, slug in enumerate(slugs)}
    results.sort(key=lambda r: order.get(r["film"], 10**9))

    hedef = ozet_yolu if ozet_yolu is not None else (OZET_PATH if out_root is None else kok / "ozet_ex.json")
    hedef.write_text(
        json.dumps({"n": len(results), "sonuclar": results}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    return results


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--film", default=None, help="slug alt-dizesi -> eşleşen film(ler)")
    ap.add_argument("--n", type=int, default=None, help="havuzdan ilk N film (ad sırasıyla)")
    ap.add_argument("--liste", default=None, help="slug listesi dosyası (satır-başına bir slug -- G0/golden-50/regresyon setleri için)")
    ap.add_argument("--paralel", type=int, default=1, help="eşzamanlı film sayısı (ayrı süreç)")
    ap.add_argument("--force", action="store_true", help="idempotent atlamayı yoksay, yeniden üret")
    ap.add_argument("--ozet-yolu", default=None, help="toplu özet JSON çıktı yolu (varsayılan: data/master_ex/ozet_ex.json)")
    ap.add_argument(
        "--cikti-kok", default=None,
        help="çıktı kökü override (varsayılan: data/master_ex). Kök-sebep fix doğrulaması "
             "için: /opt/mitas/data/master_ex_modfix -- mevcut master_ex'i EZMEZ (sadakat "
             "ölçümü onu okuyor). Belirtilirse özet de bu kökte yazılır (--ozet-yolu ile ezilebilir).",
    )
    args = ap.parse_args(argv)

    slugs = list_films()
    if args.liste:
        istenen = [s.strip() for s in Path(args.liste).read_text(encoding="utf-8").splitlines() if s.strip()]
        havuz = set(slugs)
        eksik = [s for s in istenen if s not in havuz]
        if eksik:
            print(f"UYARI: liste'de havuzda olmayan {len(eksik)} slug atlanıyor: {eksik[:10]}", file=sys.stderr)
        slugs = [s for s in istenen if s in havuz]
    if args.film:
        slugs = [s for s in slugs if args.film in s]
    if args.n:
        slugs = slugs[: args.n]

    if not slugs:
        print("Havuzda eşleşen film yok.", file=sys.stderr)
        return 1

    ozet_yolu = Path(args.ozet_yolu) if args.ozet_yolu else None
    out_root = Path(args.cikti_kok) if args.cikti_kok else None
    print(
        f"=== uret_ex.py: {len(slugs)} film işlenecek (paralel={args.paralel}, "
        f"force={args.force}, cikti_kok={out_root or OUT_ROOT}) ===",
        flush=True,
    )
    results = run(slugs, paralel=args.paralel, force=args.force, ozet_yolu=ozet_yolu, out_root=out_root)
    ok = sum(1 for r in results if r.get("status") == "OK")
    hedef = ozet_yolu if ozet_yolu is not None else (OZET_PATH if out_root is None else out_root / "ozet_ex.json")
    print(f"\n-> {hedef}  ({ok}/{len(results)} OK)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
