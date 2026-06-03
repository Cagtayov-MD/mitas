# -*- coding: utf-8 -*-
"""MITAS pipeline — OCR kunye blok runner (venvs/ocr ile kosar).

Girdi: bir veya daha cok frame dizini (acilis/kapanis kredi pencereleri).
Cikti: <out>/kunye.txt (tek satir bir isim/rol) + <out>/ocr_summary.json.

IKI AKIS VAR:
  1) "scroll-aware" pipeline100 zinciri (OCR-worktree/py): CLIP bekci ile kredi
     karelerini sec -> konumlu OneOCR oku -> OCR-uzayinda dik (stitch) -> temizle
     (clean). Akan jenerikte 900-garble cozumu; her satir tek temiz okuma.
  2) Eski kare-kare OneOCR akisi (FALLBACK): zincir importu/DB/CLIP cokerse
     buna duser. Asla cokmez; kunye.txt MUTLAKA uretilir (bosken BOS bucket).

NOT: downscale YOK; kareler native cozunurlukte gelir. Fidelity: ne okunduysa
aynen yazilir, isim DROP edilmez (stitch KEEP-ALL). stdout'a tek satir JSON
sonuc basar; sema (status/kunye_path/kunye_line_count/bucket/engine) DEGISMEZ.
"""
from __future__ import annotations
import sys, json, glob, time, unicodedata, argparse, importlib.util
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# pipeline100 zincirinin sabit mutlak yollari (DEGISMEZ kaynak dosyalar).
PY_OCR_DIR = Path(r"E:\MITAS\OCR-worktree\py")
CLIP_PROBE = PY_OCR_DIR / "20260601_clip_probe.py"
PIPELINE100 = PY_OCR_DIR / "20260601_pipeline100.py"
STITCH = PY_OCR_DIR / "20260601_stitch.py"
CLEAN = PY_OCR_DIR / "20260601_clean.py"

# Kare-secim KALICILIK esikleri (Cagatay yontemi): gercek jenerik = KESINTISIZ uzun blok.
# Acilis sahne-ustu kredi + altyazi KISA-aralikli bloklar verir -> elenir.
CREDIT_MIN_RUN = 10   # CLIP-kredi blogu en az bu kadar kare KESINTISIZ surmeli (fps2 -> ~5 sn)
CREDIT_RUN_GAP = 3    # blok ici tolere edilen bosluk (CLIP tek kare kacirsa blok kopmasin)


def _load(name: str, path: Path):
    """importlib mutlak-yol modul yukleyici (credit_parse/_pipe_pdf _load kalibi)."""
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", (s or "").casefold()) if not unicodedata.combining(c)).strip()


def alpha_ratio(s: str) -> float:
    nonsp = [c for c in s if not c.isspace()]
    if not nonsp:
        return 0.0
    return sum(c.isalpha() for c in nonsp) / len(nonsp)


def is_prose(s: str) -> bool:
    w = s.split()
    return len(w) >= 7 or s.count(",") >= 2


def is_noise(s: str) -> bool:
    t = s.strip()
    if len(t) < 2:
        return True
    if not any(c.isalpha() for c in t):  # tum rakam/noktalama
        return True
    if is_prose(t):  # tesekkur bloklari / cumleler
        return True
    return False


def build_engine():
    """OneOCR motorunu kur; basarisizsa (None, hata)."""
    try:
        import oneocr  # type: ignore
        from PIL import Image  # noqa: F401
        eng = oneocr.OcrEngine()
        return eng, "oneocr", None
    except Exception as exc:  # noqa: BLE001
        return None, "yok", f"{type(exc).__name__}: {exc}"


def ocr_frame(eng, path: Path) -> list[str]:
    from PIL import Image
    res = eng.recognize_pil(Image.open(str(path)))
    out: list[str] = []
    for ln in (res.get("lines") or []):
        t = (ln.get("text") if isinstance(ln, dict) else str(ln)).strip()
        if t:
            out.append(t)
    if not out:
        txt = (res.get("text") or "")
        out = [x.strip() for x in txt.splitlines() if x.strip()]
    return out


# ── ESKI kare-kare OneOCR akisi (FALLBACK) ──────────────────────────────────
def run_oneocr_fallback(frames: list[Path], started: float, profile: str) -> dict:
    """Zincir/CLIP/DB yoksa: her kareyi ayri OneOCR oku, fold-dedup, gurultu ele.
    Mevcut (eski) davranis aynen korunur; engine alani 'oneocr-fallback'."""
    eng, engine_name, eng_err = build_engine()
    if engine_name == "oneocr":
        engine_name = "oneocr-fallback"

    seen: dict[str, str] = {}
    order: list[str] = []
    raw_count = 0
    read_err = 0
    if eng is not None:
        for fp_ in frames:
            try:
                for ln in ocr_frame(eng, fp_):
                    raw_count += 1
                    fk = fold(ln)
                    if fk and fk not in seen:
                        seen[fk] = ln
                        order.append(ln)
            except Exception:  # noqa: BLE001 - tek kare hatasi bloklamaz
                read_err += 1

    # gurultu/prose ele
    kunye = [s for s in order if not is_noise(s)]
    garble = [s for s in kunye if alpha_ratio(s) < 0.55]
    gf = (len(garble) / len(kunye)) if kunye else 0.0

    if eng is None:
        bucket = "MOTOR_YOK"
    elif not kunye:
        bucket = "BOS"
    elif gf > 0.5:
        bucket = "ZOR"
    elif len(kunye) < 3 or gf > 0.30 or len(kunye) > 300:
        # >300 satir = akan scroll'da kare-basi OCR fazla-uretimi (bloat) -> incele.
        bucket = "GOZDEN_GECIR"
    else:
        bucket = "GUVENILIR"

    return {
        "lines": kunye,
        "engine": engine_name,
        "engine_error": eng_err,
        "frame_read_errors": read_err,
        "raw_line_count": raw_count,
        "garble_frac": round(gf, 4),
        "bucket": bucket,
    }


# ── YENI scroll-aware akis (pipeline100 zinciri) ────────────────────────────
def run_pipeline100(frames: list[Path], started: float, profile: str) -> dict | None:
    """CLIP bekci -> konumlu OneOCR -> OCR-uzayinda dik -> temizle.
    Her adim try/except; herhangi biri coker (CLIP/duckdb/oneocr yok) -> None
    dondurur ve cagiran eski OneOCR akisina graceful duser.

    Donen dict basariliysa: lines (temiz kunye), engine='pipeline100', bucket,
    + tani alanlari. None ise import/CLIP cokmus demektir."""
    try:
        # Zincir modullerini yukle (pipeline100 orkestratoru cp/cl/sl/stx'i
        # kendi icinde zaten yukler; ondan re-export'lari aliriz).
        pl = _load("pl_pipeline100", PIPELINE100)
        cp = pl.cp          # clip_probe (load_clip / score_frames / med_smooth)
        cl = pl.cl          # clean (clean / tr_upper)
        stx = pl.stx        # stitch (stitch_kunye)
        cr = pl.cr          # credit_read_v1 (DB / kb_exact_batch)
        fp = pl.fp          # full_pipeline (rd: Turkce-yol guvenli imread)
        read_pos = pl.read_pos
        # runs_of pipeline100'de TOP-LEVEL degil (compose_hybrid icinde inline);
        # dogru kaynak stitch (stx.runs_of) -> idx listesini dogrudan run'lara boler.
        runs_of = stx.runs_of
        tr_upper = pl.tr_upper
    except Exception as exc:  # noqa: BLE001 - import zinciri cokerse fallback
        print(f"[pipeline100] import basarisiz, fallback: {type(exc).__name__}: {exc}", file=sys.stderr)
        return None

    frame_paths = [str(p) for p in frames]

    # a) CLIP bekci: her kareye kredi-olasiligi -> esik>=0.5 kareler.
    #    CLIP yuklemesi pahali/coker -> bekciyi atla, TUM kareleri kullan.
    THR = 0.5
    clip_ok = True
    try:
        model, preprocess, tok = cp.load_clip()
        ls = model.logit_scale.exp().item()
        cred = cp.class_embed(model, tok, cp.CREDIT_PROMPTS)
        scene = cp.class_embed(model, tok, cp.SCENE_PROMPTS)
        ps = cp.med_smooth(cp.score_frames(model, preprocess, frame_paths, cred, scene, ls), 5)
        # KALICILIK (Cagatay): dağınık tek-tük yuksek kare DEGIL, KESINTISIZ uzun blok = jenerik.
        # Acilis sahne-ustu kredi+altyazi kisa-aralikli bloklar verir (elenir); gercek jenerik
        # (acilista uzun VEYA kapanista surekli) >=CREDIT_MIN_RUN kare suren blok = alinir.
        _runs = cp.runs_of(ps >= THR, gap=CREDIT_RUN_GAP, minlen=CREDIT_MIN_RUN)
        idx = [i for a, b in _runs for i in range(int(a), int(b) + 1)]
        if not idx:  # hicbir uzun blok yok (kisa-jenerikli/dip-kalite) -> eski davranisa dus, kapsama kaybetme
            idx = [i for i in range(len(ps)) if ps[i] >= THR]
    except Exception as exc:  # noqa: BLE001 - CLIP coker -> tum kareler
        print(f"[pipeline100] CLIP bekci atlandi: {type(exc).__name__}: {exc}", file=sys.stderr)
        clip_ok = False
        idx = list(range(len(frame_paths)))

    if not idx:
        # CLIP "hicbir kare kredi degil" dedi -> bos kunye, footage demek.
        return {
            "lines": [], "engine": "pipeline100", "engine_error": None,
            "frame_read_errors": 0, "raw_line_count": 0, "garble_frac": 0.0,
            "bucket": "BOS", "clip_used": clip_ok, "credit_frames": 0,
            "diegetik_frac": 0.0, "low_conf_frac": 0.0,
        }

    # b) Konumlu oku: secili karelerde read_pos -> ocr_pos[i] = [(fold,raw,y0,y1)]
    try:
        imgs = {i: fp.rd(frame_paths[i]) for i in idx}
        ocr_pos = {i: read_pos(imgs[i]) for i in idx}
    except Exception as exc:  # noqa: BLE001 - OneOCR/okuma coker -> fallback
        print(f"[pipeline100] konumlu okuma basarisiz, fallback: {type(exc).__name__}: {exc}", file=sys.stderr)
        return None
    raw_count = sum(len(ocr_pos[i]) for i in idx)

    # c) Dik: runs_of(idx) -> stitch_kunye -> placed_raw (her satir tek temiz okuma)
    try:
        runs = runs_of(idx)
        placed_raw, low_conf, medconf = stx.stitch_kunye(runs, ocr_pos)
    except Exception as exc:  # noqa: BLE001
        print(f"[pipeline100] stitch basarisiz, fallback: {type(exc).__name__}: {exc}", file=sys.stderr)
        return None

    # d) Temizle: DB (duckdb) baglanmaya calis; yoksa con=None ile kb bos calisir.
    con = None
    db_ok = False
    try:
        import duckdb  # type: ignore
        con = duckdb.connect(cr.DB, read_only=True)
        db_ok = True
    except Exception as exc:  # noqa: BLE001 - DB yok/kilitli -> KB'siz devam
        print(f"[pipeline100] DB baglanamadi, KB'siz devam: {type(exc).__name__}: {exc}", file=sys.stderr)
        con = None
    try:
        # asr_fold="" -> ASR-diyalog elemesi devre disi (zarar yok). con=None ise
        # clean icinde kb_exact_batch hic cagrilmaz (folds varsa cagrilir) -> guvenli.
        merged, buckets, asr_drop, dieg = cl.clean(placed_raw, con, "")
    except Exception as exc:  # noqa: BLE001 - clean coker -> ham placed_raw'a duser
        print(f"[pipeline100] clean basarisiz, ham stitch kullanildi: {type(exc).__name__}: {exc}", file=sys.stderr)
        merged = [(t, "raw", 1) for t in placed_raw]
        buckets, dieg = {}, 0.0
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:  # noqa: BLE001
                pass

    # e) kunye satirlari (mevcut formatla ayni: satir basina bir metin, # yok).
    #    clean Turkce-BUYUK yazimi tr_upper ile verir (pipeline100 ile ayni cikti).
    lines = [tr_upper(t) for t, _how, _votes in merged]

    # bucket: yeni sinyallerle, mevcut degerler korunarak.
    low_frac = (len(low_conf) / len(placed_raw)) if placed_raw else 0.0
    if not lines:
        bucket = "BOS"
    elif dieg > 0.50 or low_frac > 0.5:
        # cumle/diegetik orani yuksek YA DA dusuk-guven cogunluk -> zor okuma.
        bucket = "ZOR"
    elif len(lines) < 3 or dieg > 0.30 or low_frac > 0.30:
        bucket = "GOZDEN_GECIR"
    else:
        bucket = "GUVENILIR"

    return {
        "lines": lines,
        "engine": "pipeline100",
        "engine_error": None,
        "frame_read_errors": 0,
        "raw_line_count": raw_count,
        "garble_frac": round(low_frac, 4),
        "bucket": bucket,
        "clip_used": clip_ok,
        "db_used": db_ok,
        "credit_frames": len(idx),
        "stitched_lines": len(placed_raw),
        "low_conf_frac": round(low_frac, 4),
        "diegetik_frac": round(dieg, 4),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", nargs="+", required=True, help="frame dizin(ler)i")
    ap.add_argument("--out", required=True)
    ap.add_argument("--profile", default="film")
    args = ap.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    frames: list[Path] = []
    for d in args.frames:
        frames += sorted(Path(p) for p in glob.glob(str(Path(d) / "*.png")))

    # Once scroll-aware pipeline100 zincirini dene; coker/None -> eski OneOCR.
    res = None
    if frames:
        try:
            res = run_pipeline100(frames, started, args.profile)
        except Exception as exc:  # noqa: BLE001 - hicbir kosulda cokme
            print(f"[pipeline100] beklenmeyen hata, fallback: {type(exc).__name__}: {exc}", file=sys.stderr)
            res = None
    if res is None:
        res = run_oneocr_fallback(frames, started, args.profile)

    kunye = res["lines"]
    kunye_path = out / "kunye.txt"
    kunye_path.write_text("\n".join(kunye) + ("\n" if kunye else ""), encoding="utf-8")

    summary = {
        "engine": res["engine"],
        "engine_error": res.get("engine_error"),
        "frame_count": len(frames),
        "frame_read_errors": res.get("frame_read_errors", 0),
        "raw_line_count": res.get("raw_line_count", 0),
        "kunye_line_count": len(kunye),
        "garble_frac": res.get("garble_frac", 0.0),
        "bucket": res["bucket"],
        "profile": args.profile,
        "runtime_sec": round(time.perf_counter() - started, 3),
    }
    # pipeline100'e ozgu tani alanlari (varsa) ekle — sema icin zorunlu degil.
    for k in ("clip_used", "db_used", "credit_frames", "stitched_lines", "low_conf_frac", "diegetik_frac"):
        if k in res:
            summary[k] = res[k]
    summary_path = out / "ocr_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    status = "done" if (res["bucket"] not in ("MOTOR_YOK",) and kunye) else "partial"
    print(json.dumps({
        "status": status,
        "kunye_path": str(kunye_path),
        "summary_path": str(summary_path),
        "kunye_line_count": len(kunye),
        "bucket": res["bucket"],
        "engine": res["engine"],
        "runtime_sec": summary["runtime_sec"],
        "error": res.get("engine_error"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
