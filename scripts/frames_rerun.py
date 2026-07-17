# -*- coding: utf-8 -*-
"""frames_rerun.py — MEVCUT FRAME'LERDEN yeniden-koşu motoru (Çağatay 2026-07-11).

NEDEN: kaynak videolar offline (0/292); ama künye-okuma zaten FRAME'lerden çalışır (source'tan
DEĞİL) ve 284/284 hub'da frame var. ASR kalıcı kapalı (frames-only zaten ASR istemez). Bu motor
her hub'ı ayrı-kök (candidate) altında yeniden-koşar — mevcut Database'e DOKUNMAZ — ve çıktığı anda
sınıflar + kalite-tabanına (KALITE_TABANI_BEFORE) karşı FARK yazar.

ZİNCİR (hub başına, test-edilmiş production bileşenleri): _pipe_ocr (frames→kunye, OCR-venv) →
_pipe_credit_text (kunye→yönetmen/cast/yapımcı + extraction_status, YENİ kod) → classify (karar) →
mesru_bos (boş-alan 6-durum ön-eleme) → baseline-diff → canlı-rapor.

SİLME YOK: sonuçlar candidate_runs/frames_rerun_<ts>/<hub>/ altına. Database güvenlik-ağı.
Kullanım: python scripts/frames_rerun.py [--limit N] [--hub "<ad>"] [--out-root <dir>]"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
FORCE_OCR = False
import credit_severity_router as router  # noqa: E402
import mesru_bos as mb  # noqa: E402

# Linux geçişi 2026-07-17: env-aware kök + platform-farkında yorumlayıcılar (mitas_pipeline deseni).
PROJECT_ROOT = Path(os.environ.get("MITAS_PROJECT_ROOT") or Path(__file__).resolve().parents[1])
DB = PROJECT_ROOT / "Database"
PY_OCR = (PROJECT_ROOT / "venvs" / "ocr"
          / ("Scripts" if os.name == "nt" else "bin")
          / ("python.exe" if os.name == "nt" else "python"))
PY_PDF = Path(os.environ.get("MITAS_PDF_PYTHON") or sys.executable)
BASELINE = PROJECT_ROOT / "outputs" / "KALITE_TABANI_BEFORE_2026-07-11.json"


def _run(cmd, timeout, env=None):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, cwd=str(PROJECT_ROOT), env=env)


def _last_json(s):
    for ln in reversed((s or "").splitlines()):
        ln = ln.strip()
        if ln.startswith("{"):
            try:
                return json.loads(ln)
            except Exception:  # noqa: BLE001
                pass
    return None


def _load(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def rerun_hub(hub: Path, out_root: Path, baseline: dict) -> dict:
    d = _load(hub / "_DURUM.json")
    title = d.get("title") or hub.name
    profile = d.get("profile") or "film"
    giris = hub / "frames" / "giris"
    cikis = hub / "frames" / "cikis"
    frames = [str(p) for p in (giris, cikis) if p.exists() and any(p.glob("*.png"))]
    r = {"hub": hub.name, "trt": d.get("trt_id"), "title": title, "ts": datetime.now().isoformat(timespec="seconds")}
    if not frames:
        return {**r, "durum": "FRAME_YOK", "hata": "giris/cikis frame yok"}

    cand = out_root / hub.name
    ocr_out = cand / "ocr" / f"ocr-{hashlib.sha256(hub.name.encode()).hexdigest()[:8]}"
    ocr_out.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    # 1) KÜNYE: OCR kodu DEĞİŞMEDİ → mevcut kunye yeniden-kullanılır (akıllı-varsayılan, ~10x hız;
    # iyileştirmeler credit+classify adımında). --force-ocr ile frame'den taze OCR. ASR YOK.
    ocr_reused = False
    kunye = None
    if not FORCE_OCR:
        mevcut = sorted(hub.glob("ocr/ocr-*/kunye.txt"), key=lambda p: p.stat().st_mtime)
        mevcut = [k for k in mevcut if not k.parent.name.endswith("-fb") and k.stat().st_size > 0]
        if mevcut:
            kunye = mevcut[-1]
            ocr_reused = True
    if kunye is None:
        ocr_cmd = [str(PY_OCR), str(HERE / "_pipe_ocr.py"), "--frames", *frames,
                   "--out", str(ocr_out), "--profile", profile]
        rc_o = _run(ocr_cmd, timeout=1800)
        kunye = ocr_out / "kunye.txt"
        if not kunye.exists():
            return {**r, "durum": "OCR_HATA", "rc": rc_o.returncode, "stderr": (rc_o.stderr or "")[-300:]}
    kunye_txt = kunye.read_text(encoding="utf-8", errors="replace")
    kunye_satir = len([l for l in kunye_txt.splitlines() if l.strip()])
    kunye_sha = hashlib.sha256(kunye.read_bytes()).hexdigest()[:16]

    # 2) credit (kunye → yönetmen/cast/yapımcı + extraction_status) — YENİ kod
    ct_cmd = [str(PY_PDF), str(HERE / "_pipe_credit_text.py"), "--ocr", str(kunye),
              "--title", title, "--profile", profile]
    rc_c = _run(ct_cmd, timeout=900)
    cred = _last_json(rc_c.stdout) or {}

    # 3) classify (karar) — production classify, minimal sig (OCR+credit temelli)
    ext = cred.get("extraction_status")
    sig = {
        "cast_count": len(cred.get("cast") or []),
        "yon_missing": not bool(cred.get("yonetmen")),
        "yon_fillable": False,
        "cast_all_garble": False,
    }
    route = router.classify(sig)
    karar = "Hazır" if route["tier"] == "TEMIZ" else "Kontrol"
    if str(ext).upper() == "TECHNICAL_FAILURE":
        karar = "Kontrol"

    sure = round(time.perf_counter() - t0, 1)
    yeni = {"kunye_satir": kunye_satir, "kunye_sha": kunye_sha, "ocr_reused": ocr_reused,
            "yonetmen": cred.get("yonetmen"), "cast": cred.get("cast"),
            "yapimci": cred.get("yapimci"), "extraction_status": ext,
            "karar": karar, "tier": route["tier"], "guven": cred.get("guven")}

    # 4) baseline diff (kalite farkı)
    b = baseline.get("hubs", {}).get(hub.name, {})
    diff = {
        "kunye_satir_before": b.get("kunye_satir"), "kunye_satir_after": kunye_satir,
        "kunye_degisti": (b.get("kunye_sha") != kunye_sha) if b.get("kunye_sha") else None,
        "karar_before": b.get("karar"), "karar_after": karar,
        "yonetmen_before_dolu": bool(b.get("yonetmen")), "yonetmen_after_dolu": bool(cred.get("yonetmen")),
    }
    return {**r, "durum": "OK", "sure_sn": sure, "yeni": yeni, "diff": diff}


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="ilk N hub (0=hepsi)")
    ap.add_argument("--hub", default=None, help="tek hub adı")
    ap.add_argument("--out-root", default=None)
    ap.add_argument("--force-ocr", action="store_true",
                    help="mevcut künyeyi yeniden-kullanma; frame'den TAZE OCR (yavaş; OCR kodu değişmediyse gereksiz)")
    a = ap.parse_args()
    global FORCE_OCR
    FORCE_OCR = a.force_ocr

    baseline = _load(BASELINE)
    out_root = Path(a.out_root) if a.out_root else \
        PROJECT_ROOT / "candidate_runs" / f"frames_rerun_{datetime.now():%Y%m%d_%H%M%S}"
    out_root.mkdir(parents=True, exist_ok=True)
    rapor = out_root / "_frames_rerun_rapor.jsonl"

    hubs = []
    for h in sorted(DB.iterdir()):
        if not h.is_dir() or h.name.startswith("_"):
            continue
        if a.hub and h.name != a.hub:
            continue
        if (h / "frames" / "giris").exists() or (h / "frames" / "cikis").exists():
            hubs.append(h)
    if a.limit:
        hubs = hubs[:a.limit]

    print(f"=== FRAMES-ONLY YENİDEN-KOŞU ({len(hubs)} hub) → {out_root.name} ===")
    print(f"ASR: KAPALI | Database: DOKUNULMAZ | taban: {'VAR' if baseline else 'YOK'}\n")
    say = {"OK": 0, "OCR_HATA": 0, "FRAME_YOK": 0}
    for i, h in enumerate(hubs, 1):
        res = rerun_hub(h, out_root, baseline)
        say[res["durum"]] = say.get(res["durum"], 0) + 1
        with rapor.open("a", encoding="utf-8") as f:
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
        if res["durum"] == "OK":
            y = res["yeni"]; df = res["diff"]
            ok_iar = "↑" if (df["karar_before"] == "Kontrol" and y["karar"] == "Hazır") else \
                     ("↓" if (df["karar_before"] == "Hazır" and y["karar"] == "Kontrol") else "=")
            print(f"[{i}/{len(hubs)}] {ok_iar} {res['title'][:32]:32s} kunye {df['kunye_satir_before']}→{y['kunye_satir']} "
                  f"| karar {df['karar_before']}→{y['karar']} | yön:{'✓' if df['yonetmen_after_dolu'] else '·'} "
                  f"| {y['extraction_status']} | {res['sure_sn']}sn")
        else:
            print(f"[{i}/{len(hubs)}] ✗ {res['title'][:32]:32s} {res['durum']} {res.get('hata') or res.get('stderr','')[:60]}")
    print(f"\n=== ÖZET: {say} ===\nrapor: {rapor}")


if __name__ == "__main__":
    main()
