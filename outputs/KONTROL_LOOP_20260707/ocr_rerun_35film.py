# -*- coding: utf-8 -*-
"""35-film OCR-partial toplu yeniden-koşu (KONTROL_LOOP_20260707).

Kok neden (dogrulandi, debug_trace/system_events log kanitiyla): 2026-07-06 06:50
gece-yarisi toplu-kosu sirasinda GECICI sistem-capinda bellek tukenmesi (OpenCV
"Insufficient memory" 843KB'lik ayirmada bile, ASR MemoryError, commit-bos 4.9GB/8GB
hedef) -> _pipe_ocr.py alt-sureci HICBIR stderr/stdout uretmeden coktu (Python
except'iyle YAKALANAMAYAN sert bir cokme; her yer try/except'li ama sifir-cikti
gozlemi bunu dogruluyor). mitas_pipeline.py bu durumda ocr_bucket="HATA" (varsayilan,
j={} oldugu icin) + status="partial" yazdi. Kareler (frames/giris + frames/cikis)
SAGLAM cikarilmisti -> videodan yeniden baslamaya GEREK YOK, yalniz OCR-okuma adimi
(_pipe_ocr.py) o kareler uzerinde yeniden calistirilir.

Bu script mitas_pipeline.py'nin ANA OCR blogunun (satir ~2025-2178) BIREBIR aynisini
tek-film icin tekrarlar: _pipe_ocr.py (venvs/ocr) -> clip.json modules.ocr guncelle
(update_clip_module ile AYNI semantik) -> tek_film_kunye.py --clip (PY_PDF) ile
DOGRULAMA render'i (--out scratchpad'e, hub'in kendi pdf/kunye.pdf'ine DOKUNULMAZ,
export/ONAYLI|KONTROL'e HIC DOKUNULMAZ -- o karar KONTROL-loop'un kendi sonraki
turuna ait).

Kullanim:
  python ocr_rerun_35film.py --hub "LA BOHEME 1988-0420-1-0000-00-1" --verify-dir <dir>
  python ocr_rerun_35film.py --hub-list hubs.txt --verify-dir <dir> --report out.jsonl
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time, os
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(r"E:\MITAS")
SCRIPTS = PROJECT_ROOT / "scripts"
PY_OCR = PROJECT_ROOT / "venvs" / "ocr" / "Scripts" / "python.exe"
PY_PDF = Path(r"C:\Users\TRT03\AppData\Local\Programs\Python\Python310\python.exe")
DATABASE = PROJECT_ROOT / "Database"
OCR_TIMEOUT = 3600   # mitas_pipeline.py varsayilaniyla AYNI (MITAS_OCR_TIMEOUT)
V4_TIMEOUT = 900     # mitas_pipeline.py varsayilaniyla AYNI (MITAS_V4_TIMEOUT)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def last_json(stdout: str):
    for line in reversed([l.strip() for l in stdout.splitlines() if l.strip()]):
        if line.startswith("{"):
            try:
                return json.loads(line)
            except Exception:  # noqa: BLE001
                continue
    return None


def update_clip_module(clip_dir: Path, module: str, status: str, job_id: str) -> dict:
    """mitas_pipeline.py:update_clip_module ile BIREBIR ayni semantik."""
    cj = clip_dir / "clip.json"
    rec = json.loads(cj.read_text(encoding="utf-8")) if cj.exists() else {}
    mods = rec.setdefault("modules", {})
    st = mods.setdefault(module, {"jobs": [], "latest_job_id": None, "status": None})
    if job_id not in st["jobs"]:
        st["jobs"].append(job_id)
    st["latest_job_id"] = job_id
    st["status"] = status
    st["updated_at"] = now_iso()
    cj.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    return rec


def rerun_ocr(clip_dir: Path, profile: str = "film") -> dict:
    giris = clip_dir / "frames" / "giris"
    cikis = clip_dir / "frames" / "cikis"
    if not giris.exists() or not any(giris.glob("*.png")):
        return {"ok": False, "reason": "no_giris_frames"}

    frame_dirs = [str(giris)]
    if cikis.exists() and any(cikis.glob("*.png")):
        frame_dirs.append(str(cikis))

    ocr_job = f"ocr-{uuid4().hex[:8]}"
    ocr_out = clip_dir / "ocr" / ocr_job
    cmd = [str(PY_OCR), str(SCRIPTS / "_pipe_ocr.py"), "--frames", *frame_dirs,
           "--out", str(ocr_out), "--profile", profile]
    t0 = time.perf_counter()
    try:
        r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=OCR_TIMEOUT)
    except subprocess.TimeoutExpired:
        update_clip_module(clip_dir, "ocr", "failed", ocr_job)
        return {"ok": True, "job_id": ocr_job, "status": "failed", "reason": "timeout",
                "elapsed": round(time.perf_counter() - t0, 2)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}

    elapsed = round(time.perf_counter() - t0, 2)
    j = last_json(r.stdout) or {}
    bucket = j.get("bucket", "HATA")            # mitas_pipeline.py ile AYNI varsayilan
    st = j.get("status", "failed")               # mitas_pipeline.py ile AYNI varsayilan
    final_status = "done" if st == "done" else "partial"   # AYNI ternary
    update_clip_module(clip_dir, "ocr", final_status, ocr_job)
    return {
        "ok": True, "job_id": ocr_job, "elapsed": elapsed, "rc": r.returncode,
        "bucket": bucket, "status": final_status, "raw_status": st,
        "kunye_line_count": j.get("kunye_line_count"), "engine": j.get("engine"),
        "kunye_path": str(ocr_out / "kunye.txt"),
        "stdout_had_json": bool(j),
        "stderr_tail": (r.stderr or "")[-2000:],
    }


def verify_render(clip_dir: Path, title, year, profile: str, verify_out: Path) -> dict:
    cmd = [str(PY_PDF), str(SCRIPTS / "tek_film_kunye.py"), "--clip", str(clip_dir),
           "--out", str(verify_out), "--profile", profile]
    if title:
        cmd += ["--title", str(title)]
    if year:
        cmd += ["--year", str(year)]
    t0 = time.perf_counter()
    try:
        r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=V4_TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
    elapsed = round(time.perf_counter() - t0, 2)
    rapor = None
    idx = r.stdout.find("{")
    if idx >= 0:
        try:
            rapor, _ = json.JSONDecoder().raw_decode(r.stdout[idx:])
        except Exception:  # noqa: BLE001
            rapor = None
    return {
        "ok": True, "rc": r.returncode, "elapsed": elapsed, "rapor": rapor,
        "pdf_exists": verify_out.exists(),
        "pdf_size": verify_out.stat().st_size if verify_out.exists() else 0,
        "stderr_tail": (r.stderr or "")[-2000:],
    }


def process_hub(hub_name: str, verify_dir: Path) -> dict:
    clip_dir = DATABASE / hub_name
    if not clip_dir.exists():
        return {"hub": hub_name, "ok": False, "reason": "hub_not_found"}
    cj_path = clip_dir / "clip.json"
    cj = json.loads(cj_path.read_text(encoding="utf-8")) if cj_path.exists() else {}
    profile = cj.get("profile") or "film"
    title = cj.get("title")
    trt = cj.get("trt_id", "") or ""
    year = trt.split("-")[0] if trt else None
    prev_status = ((cj.get("modules") or {}).get("ocr") or {}).get("status")

    ocr_result = rerun_ocr(clip_dir, profile=profile)
    render_result = None
    if ocr_result.get("ok") and ocr_result.get("status") == "done":
        verify_out = verify_dir / f"{trt}_{hub_name}_verify.pdf".replace("/", "_")
        render_result = verify_render(clip_dir, title, year, profile, verify_out)

    return {
        "hub": hub_name, "trt": trt, "title": title, "profile": profile,
        "prev_ocr_status": prev_status,
        "ocr": ocr_result, "render": render_result,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", action="append", default=[], help="Database/<hub klasor adi>, tekrarlanabilir")
    ap.add_argument("--hub-list", default=None, help="Her satirda bir hub adi olan dosya")
    ap.add_argument("--verify-dir", required=True)
    args = ap.parse_args(argv)

    hubs = list(args.hub)
    if args.hub_list:
        hubs += [l.strip() for l in Path(args.hub_list).read_text(encoding="utf-8").splitlines() if l.strip()]
    if not hubs:
        print("Hic hub verilmedi (--hub veya --hub-list).", file=sys.stderr)
        return 2

    verify_dir = Path(args.verify_dir)
    verify_dir.mkdir(parents=True, exist_ok=True)

    results_dir = verify_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    for i, hub in enumerate(hubs, 1):
        print(f"=== [{i}/{len(hubs)}] {hub} ===", file=sys.stderr)
        sys.stderr.flush()
        res = process_hub(hub, verify_dir)
        safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in hub)
        (results_dir / f"{safe_name}.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        ocr = res.get("ocr") or {}
        rend = res.get("render") or {}
        v4 = ((rend.get("rapor") or {}).get("v4") or {}) if rend else {}
        summary_line = (
            f"[{i}/{len(hubs)}] {hub}: ocr_ok={ocr.get('ok')} status={ocr.get('status')} "
            f"bucket={ocr.get('bucket')} lines={ocr.get('kunye_line_count')} "
            f"render_ok={rend.get('ok') if rend else None} "
            f"yonetmen={v4.get('yonetmen') or v4.get('yonetmen_list')} "
            f"cast_n={len(v4.get('cast_list') or v4.get('cast') or [])}"
        )
        print(summary_line, file=sys.stderr)
        sys.stderr.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
