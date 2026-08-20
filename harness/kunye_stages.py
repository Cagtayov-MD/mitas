# -*- coding: utf-8 -*-
"""kunye_stages.py — MITAS künye 51-film Linux test harness (ince sürücü).

Mevcut ÜRETİM script'lerini alt-süreç olarak çağırır (davranış-nötr); ASR/OneOCR-okuma/gemma YOK.
Her aşama tek film için ayrı çağrılır (Workflow toplu-aşama + rapor-kapısı akışına uyum).

Aşamalar:
  1  -> ffprobe kapısı + ffmpeg extract (cikis son600s / giris ilk240s @1.5fps) + paddle havuz (cikis+giris)
  2  -> master_png_monitor --once (giris/cikis reading-master)
  slice -> master_png_dilimle --clip (uzun master -> VL-okunur parçalar)
  vl -> _pipe_dilim_vl --clip --model (tek model transkripsiyon; sonra dilim_vl__<model>.json rename)

CLI:  python kunye_stages.py --film <path> --stage 1|2|slice|vl [--model M] [--backend ollama|openai --base URL]
Çıktı: stdout'a tek satır JSON (o aşamanın state parçası). State dosyası: $MITAS_RUN_ROOT/state/<id>.json (birleştirilir).
Kaynak filmler salt-okunur; tüm yazma $MITAS_RUN_ROOT altında.
"""
from __future__ import annotations
import argparse, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

REPO = Path(os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas"))
RUN_ROOT = Path(os.environ["MITAS_RUN_ROOT"])
DB_ROOT = RUN_ROOT / "Database"
STATE_DIR = RUN_ROOT / "state"
PY_OCR = os.environ.get("PY_OCR", str(REPO / "venvs" / "ocr" / "bin" / "python"))
FPS = 1.5
CIKIS_TAIL_S = 600      # son 10 dk
GIRIS_HEAD_S = 240      # ilk 4 dk
TRT_RE = re.compile(r"\d{4}-\d{3,4}-\d-\d{3,4}-\d{2}-\d")


def safe_id(film: Path) -> str:
    return film.stem


def clip_dir(film: Path) -> Path:
    return DB_ROOT / safe_id(film)


def _run(cmd, cwd=REPO, timeout=3600, env_extra=None):
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    t0 = time.time()
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, env=env)
    return {"rc": p.returncode, "stdout": p.stdout, "stderr": p.stderr, "secs": round(time.time() - t0, 1)}


def _last_json_line(s: str):
    for line in reversed([l for l in s.splitlines() if l.strip()]):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except Exception:
                continue
    return None


def load_state(film: Path) -> dict:
    p = STATE_DIR / f"{safe_id(film)}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"film_id": safe_id(film), "src": str(film),
            "trt_id": (TRT_RE.search(film.name).group(0) if TRT_RE.search(film.name) else None),
            "overall": "pending", "reached_stage": 0}


def save_state(film: Path, st: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    p = STATE_DIR / f"{safe_id(film)}.json"
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def ffprobe(film: Path) -> dict:
    r = _run(["/usr/bin/ffprobe", "-v", "error", "-show_entries",
              "format=duration:stream=codec_type,codec_name", "-of", "json", str(film)], timeout=120)
    try:
        j = json.loads(r["stdout"])
    except Exception:
        return {"has_video": False, "duration_s": 0.0, "err": r["stderr"][:300]}
    streams = j.get("streams", [])
    vids = [s for s in streams if s.get("codec_type") == "video"]
    dur = float(j.get("format", {}).get("duration") or 0.0)
    return {"has_video": bool(vids), "duration_s": round(dur, 1),
            "vcodec": (vids[0].get("codec_name") if vids else None),
            "n_streams": len(streams)}


def ffmpeg_extract(film: Path, out_dir: Path, start: float, length: float, prefix: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.png"):
        old.unlink()
    n = int(round(length * FPS))
    cmd = ["/usr/bin/ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    if start > 0:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(film), "-t", f"{length:.3f}", "-vf", f"fps={FPS}",
            "-frames:v", str(n), str(out_dir / f"{prefix}_%04d.png")]
    r = _run(cmd, timeout=1800)
    r["count"] = len(list(out_dir.glob("*.png")))
    r["expected"] = n
    return r


def stage1(film: Path) -> dict:
    st = load_state(film)
    cd = clip_dir(film)
    s1 = {"status": "pass", "root_cause": None}
    probe = ffprobe(film)
    s1["probe"] = probe
    if not probe["has_video"]:
        s1.update(status="fail", root_cause="no_video_stream", cls="film")
        st["stage1"] = s1; st["overall"] = "fail"; save_state(film, st); return st
    if probe["duration_s"] < 300:
        s1.update(status="fail", root_cause="duration_too_short", cls="film")
        st["stage1"] = s1; st["overall"] = "fail"; save_state(film, st); return st
    dur = probe["duration_s"]
    # cikis (son 10 dk) + giris (ilk 4 dk)
    clen = min(CIKIS_TAIL_S, dur); cstart = max(0.0, dur - clen)
    glen = min(GIRIS_HEAD_S, dur)
    ce = ffmpeg_extract(film, cd / "frames" / "cikis", cstart, clen, "c")
    ge = ffmpeg_extract(film, cd / "frames" / "giris", 0.0, glen, "g")
    s1["cikis_frames"] = ce["count"]; s1["giris_frames"] = ge["count"]
    if ce["count"] == 0:
        s1.update(status="fail", root_cause="ffmpeg_error", cls="film/system",
                  ffmpeg_err=ce["stderr"][:300])
        st["stage1"] = s1; st["overall"] = "fail"; save_state(film, st); return st
    # paddle havuz: cikis
    dbg = cd / "jenerik_debug"
    pc = _run([PY_OCR, "scripts/_jenerik_pool.py",
               "--frames", str(cd / "frames" / "cikis"),
               "--pool", str(cd / "frames" / "cikis_jenerik"),
               "--debug-root", str(dbg)], timeout=1800)
    mc = _last_json_line(pc["stdout"]) or {"status": "error", "stderr": pc["stderr"][:300]}
    # cikis detection.json çakışmasın diye stdout manifestini kullan; dosyayı da yeniden adlandır
    det_json = cd / "frames" / "jenerik_detection.json"
    if det_json.exists():
        shutil.copy2(det_json, cd / "frames" / "jenerik_detection_cikis.json")
    s1["cikis_pool"] = {"status": mc.get("status"), "start_pos": mc.get("start_pos"),
                        "pool_frames": mc.get("pool_frames"), "engine": mc.get("engine"),
                        "credit_type": mc.get("credit_type"), "accepted": mc.get("accepted"),
                        "review_required": mc.get("review_required")}
    # paddle havuz: giris (P-open, OneOCR'siz)
    # --segment giris (Dalga 2, 2026-07-29): v5'in SON_ERISIM kuralı ("aday son
    # %18'e ulaşmalı") açılış penceresinde anlamsız (ölçüldü: 270 karelik giriş
    # penceresinde v5 kare 135/181 döndürüyor) — CV bu segmentte birincil kalır.
    pg = _run([PY_OCR, "scripts/_jenerik_pool.py",
               "--frames", str(cd / "frames" / "giris"),
               "--pool", str(cd / "frames" / "giris_jenerik"),
               "--debug-root", str(cd / "jenerik_debug_giris"),
               "--segment", "giris"], timeout=1800)
    mg = _last_json_line(pg["stdout"]) or {"status": "error", "stderr": pg["stderr"][:300]}
    if det_json.exists():
        shutil.copy2(det_json, cd / "frames" / "jenerik_detection_giris.json")
    s1["giris_pool"] = {"status": mg.get("status"), "start_pos": mg.get("start_pos"),
                        "pool_frames": mg.get("pool_frames"), "accepted": mg.get("accepted")}
    # sınıflandır (kapanış birincil): kapanış havuzu doldu mu?
    cp = s1["cikis_pool"]["pool_frames"] or 0
    gp = s1["giris_pool"]["pool_frames"] or 0
    if cp == 0:
        if mc.get("status") in (None, "error"):
            s1.update(status="fail", root_cause="pool_error", cls="code")
        elif mc.get("status") == "review_kredi_yok" or mc.get("review_required"):
            # Dalga 3 (metin-kapı, bayrak MITAS_JENERIK_METIN_KAPI — default kapalı):
            # v5 "kredi_yok" dedi ama credit_box det-only taraması son %15 karede
            # credit-benzeri kutu oranını eşiğin (METIN_KAPI_ESIK) üstünde buldu.
            # Bu FAIL değil, insan-kuyruğu — CV devretmeden reddedilen bir aday.
            # overall="review" (aşağıda), "pass"/"fail" ikilisini bozmayan üçüncü
            # bir durum. report_basic.py npass/nfail yalnız "pass"/"fail" string'ini
            # sayıyor; "review" ikisine de eklenmez (yanlış sayılmaz, ayrı görünür).
            s1.update(status="review", root_cause="review_kredi_yok", cls="film")
        else:
            s1.update(status="fail", root_cause="detection_no_credit", cls="film/code")
    else:
        s1["status"] = "pass"
    if gp == 0:
        s1["opening_note"] = "opening_paddle_empty"
    s1["timings"] = {"extract_c": ce["secs"], "extract_g": ge["secs"],
                     "pool_c": pc["secs"], "pool_g": pg["secs"]}
    st["stage1"] = s1
    st["reached_stage"] = 1
    st["overall"] = ("partial" if s1["status"] == "pass"
                      else "review" if s1["status"] == "review"
                      else "fail")
    save_state(film, st)
    return st


def _base_name(film: Path) -> str:
    # master png prefix: TRT başlık kısmı (dosya adındaki okunur kısım). Basit: stem'in son parçası.
    return safe_id(film)


def stage2(film: Path) -> dict:
    st = load_state(film)
    cd = clip_dir(film)
    s2 = {"status": "pass", "root_cause": None}
    r = _run([PY_OCR, "OCR-worktree/master_png_monitor.py", "--once", str(cd), "--base", _base_name(film)],
             timeout=1800)
    s2["monitor_rc"] = r["rc"]; s2["monitor_secs"] = r["secs"]
    s2["monitor_tail"] = (r["stdout"] + r["stderr"])[-800:]
    # üretilen master/reading-master dosyalarını + manifest'i topla
    def _png_info(p: Path):
        if not p.exists():
            return None
        try:
            from PIL import Image
            with Image.open(p) as im:
                return {"file": p.name, "w": im.size[0], "h": im.size[1], "bytes": p.stat().st_size}
        except Exception as e:
            return {"file": p.name, "err": str(e)[:120]}
    segs = {}
    for seg, canon_glob, reading in (("cikis", "* cikis.png", "reading_master_runaware.png"),
                                     ("giris", "* giris.png", "giris_reading_master_runaware.png")):
        canon = next(iter(sorted(cd.glob(canon_glob))), None)
        segs[seg] = {"canonical": _png_info(canon) if canon else None,
                     "reading": _png_info(cd / reading)}
    s2["segments"] = segs
    mani = next(iter(sorted(cd.glob("* master_manifest.json"))), None)
    if mani:
        try:
            s2["manifest"] = json.loads(mani.read_text(encoding="utf-8"))
        except Exception:
            pass
    # sınıflandır: en az bir reading-master üretildi mi?
    has_reading = any(segs[s]["reading"] and "w" in (segs[s]["reading"] or {}) for s in segs)
    if not has_reading:
        s2.update(status="fail", root_cause="no_output", cls="film/code")
    st["stage2"] = s2
    st["reached_stage"] = max(st.get("reached_stage", 0), 2)
    if s2["status"] != "pass" and st.get("overall") != "fail":
        st["overall"] = "partial"
    save_state(film, st)
    return st


def stage_slice(film: Path) -> dict:
    st = load_state(film)
    cd = clip_dir(film)
    r = _run([PY_OCR, "scripts/master_png_dilimle.py", "--clip", str(cd)], timeout=900)
    j = _last_json_line(r["stdout"]) or {}
    parts = 0
    mani = cd / "master_dilim" / "dilim_manifest.json"
    if mani.exists():
        try:
            m = json.loads(mani.read_text(encoding="utf-8"))
            parts = sum(len(x.get("parts", [])) for x in m.get("results", []) if isinstance(x, dict))
        except Exception:
            pass
    s3 = st.get("stage3", {})
    s3["slice"] = {"stdout": j, "parts": parts, "secs": r["secs"],
                   "root_cause": None if parts > 0 else "slice_error"}
    st["stage3"] = s3
    st["reached_stage"] = max(st.get("reached_stage", 0), 3)
    save_state(film, st)
    return st


def stage_vl(film: Path, model: str, backend: str = "ollama", base_url: str = None) -> dict:
    st = load_state(film)
    cd = clip_dir(film)
    cmd = [PY_OCR, "scripts/_pipe_dilim_vl.py", "--clip", str(cd), "--model", model]
    if backend and backend != "ollama":
        cmd += ["--backend", backend]
    if base_url:
        cmd += ["--base", base_url]
    r = _run(cmd, timeout=3600)
    j = _last_json_line(r["stdout"]) or {"status": "vl_error", "stderr": r["stderr"][:300]}
    # sabit dilim_vl.json -> model'e özel yeniden adlandır
    mslug = re.sub(r"[^a-zA-Z0-9]+", "_", model)
    src = cd / "master_dilim" / "dilim_vl.json"
    dst = cd / "master_dilim" / f"dilim_vl__{mslug}.json"
    scored = {"model": model, "backend": backend, "status": j.get("status"), "secs": r["secs"]}
    if src.exists():
        try:
            data = json.loads(src.read_text(encoding="utf-8"))
            lines, unread, empty = 0, 0, 0
            for part in data.get("parts", []):
                tr = part.get("transcript", [])
                lines += len([l for l in tr if l not in ("[okunamadı]", "[yazı yok]")])
                unread += len([l for l in tr if l == "[okunamadı]"])
                if not tr or all(l in ("[okunamadı]", "[yazı yok]") for l in tr):
                    empty += 1
            tot = lines + unread
            scored.update(parts=len(data.get("parts", [])), lines_total=lines,
                          unreadable=unread, unreadable_rate=round(unread / tot, 3) if tot else None,
                          empty_parts=empty)
        except Exception as e:
            scored["parse_err"] = str(e)[:150]
        src.replace(dst)
        scored["out"] = dst.name
    else:
        scored["root_cause"] = "vl_error"
    s3 = st.get("stage3", {})
    s3.setdefault("models", {})[model] = scored
    st["stage3"] = s3
    save_state(film, st)
    return st


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--film", required=True)
    ap.add_argument("--stage", required=True, choices=["1", "2", "slice", "vl"])
    ap.add_argument("--model", default=os.environ.get("MITAS_DILIM_VL_MODEL", "qwen2.5vl:7b"))
    ap.add_argument("--backend", default="ollama")
    ap.add_argument("--base", default=None)
    a = ap.parse_args()
    film = Path(a.film)
    if a.stage == "1":
        st = stage1(film)
    elif a.stage == "2":
        st = stage2(film)
    elif a.stage == "slice":
        st = stage_slice(film)
    else:
        st = stage_vl(film, a.model, a.backend, a.base)
    # ilgili aşama özetini tek satır JSON bas
    key = {"1": "stage1", "2": "stage2", "slice": "stage3", "vl": "stage3"}[a.stage]
    print(json.dumps({"film_id": st["film_id"], "overall": st.get("overall"),
                      key: st.get(key)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
