"""Gölge VL aşaması — üretime DOKUNMAZ, sadece okur+yazar.

CLI:
    python _pipe_shadow_vl.py --clip <clip_dir> --out <gemma_kunye.json>

Her durumda exit 0 döner (fail-safe).

Env değişkenleri:
    MITAS_SHADOW_VL_TILE   scroll dilim yüksekliği (varsayılan 1400)
    MITAS_SHADOW_VL_OV     dilim örtüşme miktarı   (varsayılan 150)
    MITAS_SHADOW_VL_CAP    havuz görüntü üst sınırı (varsayılan 30)
    MITAS_SHADOW_VL_MODEL  VL okuyucu modeli        (varsayılan glm-ocr:latest; gemma4:26b ile de çalışır)
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import sys
import time
import types
from pathlib import Path

import cv2
import numpy as np


# --------------------------------------------------------------------------- #
# loadf — modülü dosyadan dinamik yükle (_vlm_pipeline'ın kendi deseni)
# --------------------------------------------------------------------------- #
def loadf(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# Sabitler / env
# --------------------------------------------------------------------------- #
TILE_DEFAULT = 1400
OV_DEFAULT = 150
CAP_DEFAULT = 30
MODEL_DEFAULT = "glm-ocr:latest"   # OCR-uzmani okuyucu (kiyasta kazanan); gemma4:26b ile de calisir

DCM_PATH = r"E:\MITAS\OCR-worktree\db_compose_master.py"
VLM_PATH = r"E:\MITAS\OCR-worktree\_vlm_pipeline.py"


# --------------------------------------------------------------------------- #
# Yardımcı: natural sort
# --------------------------------------------------------------------------- #
def _nat_key(p: Path):
    nums = re.findall(r"\d+", p.name)
    return (int(nums[-1]) if nums else -1, p.name)


# --------------------------------------------------------------------------- #
# Atomik JSON yazımı (mitas_pipeline::write_json deseni)
# --------------------------------------------------------------------------- #
def _write_json(out_path: Path, obj: dict) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_name(out_path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(str(tmp), str(out_path))


def _write_jsonl(out_path: Path, rows: list[dict]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- #
# Masked motion hesabı (split_runs KULLANILMAZ — full-frame bug)
# Maskeleme: _vlm_pipeline slitscan'in text-masked phaseCorrelate yaklaşımı
# --------------------------------------------------------------------------- #
def _masked_dy(prev_masked: np.ndarray | None, cur_masked: np.ndarray,
               hann: np.ndarray, prev_has_text: bool) -> float:
    """Metin-maskeli phaseCorrelate ile dikey kayma miktarını döndür."""
    if prev_masked is None or not prev_has_text:
        return 0.0
    (_, dy), _ = cv2.phaseCorrelate(prev_masked.astype(np.float32),
                                    cur_masked.astype(np.float32))
    return float(dy)


def _build_masked_float(gray: np.ndarray, p, dcm) -> tuple[np.ndarray, bool]:
    """text_mask + dilate → masked float; (array, has_text)."""
    mask = dcm.text_mask(gray, p, "auto")
    dilated = cv2.dilate(mask, np.ones((11, 11), np.uint8))
    masked = gray.astype(np.float32).copy()
    masked[dilated == 0] = 0.0
    has_t = bool(dilated.any())
    return masked, has_t


# --------------------------------------------------------------------------- #
# A) build_pool
# --------------------------------------------------------------------------- #
def build_pool(
    clip_dir: Path,
    dcm,
    args_ns,
    *,
    source_dir: Path | None = None,
    pool_dir_override: Path | None = None,
) -> tuple[Path, dict]:
    """Kare havuzu oluştur; pool_dir ve manifest döndür."""

    tile = int(os.environ.get("MITAS_SHADOW_VL_TILE", TILE_DEFAULT))
    ov = int(os.environ.get("MITAS_SHADOW_VL_OV", OV_DEFAULT))
    cap = int(os.environ.get("MITAS_SHADOW_VL_CAP", CAP_DEFAULT))
    # Statik kart TEMPORAL çok-temsilci adımı (kare): kart uzunsa ~her N karede bir temsilci
    # (tek-sharpest DEĞİL) → kart içinde birden çok kredi/footage-tabela AYRIŞIR; sharpv footage-
    # tabelasını krediye yeğleyip yönetmen-gibi küçük-yazı kareyi ATMASIN. Default 8 (~4s @ 2fps).
    card_step = max(1, int(os.environ.get("MITAS_SHADOW_VL_CARD_STEP", "8") or 8))

    pool_dir = pool_dir_override or (clip_dir / "vl_pool")
    if pool_dir.exists():
        shutil.rmtree(pool_dir)
    pool_dir.mkdir(parents=True, exist_ok=True)

    # PNG'leri topla (giris + cikis)
    seg_frames: dict[str, list[Path]] = {}
    if source_dir is not None:
        if source_dir.is_dir():
            pngs = sorted(source_dir.glob("*.png"), key=_nat_key)
            if pngs:
                seg_frames[source_dir.name] = pngs
    else:
        for seg in ("giris", "cikis"):
            seg_path = clip_dir / "frames" / seg
            if seg_path.is_dir():
                pngs = sorted(seg_path.glob("*.png"), key=_nat_key)
                if pngs:
                    seg_frames[seg] = pngs

    if not seg_frames:
        manifest = {"status": "no_frames", "source_dir": str(source_dir) if source_dir else None}
        _write_json(pool_dir / "pool_manifest.json", manifest)
        return pool_dir, manifest

    # İlk okunabilir kare için boyut → derive_params
    p = None
    for seg, frames in seg_frames.items():
        for fp in frames:
            img = dcm.rd_cached(str(fp))
            if img is not None:
                h, w = img.shape[:2]
                p = dcm.derive_params(h, w, args_ns)
                break
        if p is not None:
            break

    if p is None:
        manifest = {"status": "no_readable_frames"}
        _write_json(pool_dir / "pool_manifest.json", manifest)
        return pool_dir, manifest

    card_counter = [0]
    scroll_counter = [0]
    pool_images: list[dict] = []   # {file, kind, src_run, src_frame, h}

    def _save_img(arr: np.ndarray, kind: str, meta: dict) -> dict | None:
        if arr is None or arr.size == 0:
            return None
        if kind == "card":
            fname = f"card_{card_counter[0]:04d}.png"
            card_counter[0] += 1
        else:
            fname = f"scroll_{scroll_counter[0]:04d}.png"
            scroll_counter[0] += 1
        fpath = pool_dir / fname
        ok, enc = cv2.imencode(".png", arr)
        if ok:
            enc.tofile(str(fpath))
            entry = {"file": str(fpath), "kind": kind, "h": int(arr.shape[0])}
            entry.update(meta)
            return entry
        return None

    # ------------------------------------------------------------------ #
    # Her segment için maskelı motion ile tip tespiti
    # ------------------------------------------------------------------ #
    for seg, frames in seg_frames.items():
        frame_strs = [str(fp) for fp in frames]
        n = len(frame_strs)
        if n == 0:
            continue

        hann = cv2.createHanningWindow((p.w, p.h), cv2.CV_32F)
        abs_dy_arr: list[float] = []
        prev_masked: np.ndarray | None = None
        prev_has_text = False

        # Tüm karelerin abs_dy'sini hesapla (maskelı)
        for fp in frame_strs:
            img = dcm.rd_cached(fp)
            if img is None:
                abs_dy_arr.append(0.0)
                prev_masked = None
                prev_has_text = False
                continue
            if img.shape[:2] != (p.h, p.w):
                img = cv2.resize(img, (p.w, p.h))
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            masked, has_t = _build_masked_float(gray, p, dcm)
            dy = _masked_dy(prev_masked, masked, hann, prev_has_text)
            abs_dy_arr.append(abs(dy))
            prev_masked = masked
            prev_has_text = has_t

        # 5-kare medyan smooth
        arr = np.array(abs_dy_arr)
        smooth = np.array([
            float(np.median(arr[max(0, i - 2): i + 3]))
            for i in range(len(arr))
        ])

        # Tip etiketleme: "S" static, "R" scroll (sticky)
        labels: list[str] = []
        state = "S"
        for v in smooth:
            if v < p.static_dy:
                state = "S"
            elif v > p.scroll_dy:
                state = "R"
            labels.append(state)

        # Run'lara birleştir, min_hold'dan kısa olanları at
        runs: list[tuple[int, int, str]] = []
        i = 0
        while i < n:
            lab = labels[i]
            j = i
            while j < n and labels[j] == lab:
                j += 1
            if (j - i) >= p.min_hold:
                runs.append((i, j - 1, lab))
            i = j

        # Run'ları işle
        for run_start, run_end, lab in runs:
            run_frames = frame_strs[run_start: run_end + 1]
            src_run = [run_start, run_end]

            if lab == "S":
                # STATİK → split_static_cards → her kart için TEMPORAL ÇOK-TEMSİLCİ (tek-sharpest DEĞİL):
                # kartı card_step'lik pencerelere böl, HER pencereden sharpest → kart içinde birden çok
                # kredi/footage-tabela ayrışır (sharpv footage'ı krediye yeğleyip yönetmeni atamaz).
                try:
                    cards = dcm.split_static_cards(run_frames, p, args_ns)
                except Exception:
                    cards = [run_frames]

                for card_frames in cards:
                    _nfr = len(card_frames)
                    if _nfr == 0:
                        continue
                    for _w0 in range(0, _nfr, card_step):          # temporal pencereler
                        _win = card_frames[_w0: _w0 + card_step]
                        best_sv = -1.0
                        best_img = None
                        best_fp = None
                        for cfp in _win:
                            img = dcm.rd_cached(cfp)
                            if img is None:
                                continue
                            if img.shape[:2] != (p.h, p.w):
                                img = cv2.resize(img, (p.w, p.h))
                            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                            sv = dcm.sharpv(gray)
                            if sv > best_sv:
                                best_sv = sv
                                best_img = img
                                best_fp = cfp
                        if best_img is None:
                            continue
                        gray = cv2.cvtColor(best_img, cv2.COLOR_BGR2GRAY)
                        mask = dcm.text_mask(gray, p, "auto")
                        band = dcm.text_rows(mask, p) or dcm.text_band(mask)
                        if band is None:
                            continue
                        crop = best_img[
                            max(0, band[0] - p.pad): min(best_img.shape[0], band[1] + p.pad),
                            :
                        ]
                        if crop is None or crop.size == 0:
                            continue
                        entry = _save_img(crop, "card", {"src_run": src_run, "src_frame": best_fp})
                        if entry:
                            pool_images.append(entry)

            elif lab == "R":
                # SCROLL → slitscan → dikey dilimleme
                try:
                    strip = dcm.slitscan(run_frames, p, args_ns)
                    # HİBRİT-DY imza değişikliği (2026-07-09): slitscan artık
                    # (block, hybrid_info) tuple döner; eski dcm ile geriye-uyumlu kal.
                    if isinstance(strip, tuple):
                        strip = strip[0]
                except Exception as e:
                    print(f"[shadow_vl] slitscan hata seg={seg} run={src_run}: {e}", file=sys.stderr)
                    strip = None

                if strip is None or strip.size == 0:
                    continue

                H = strip.shape[0]
                step = max(1, tile - ov)
                y = 0
                while y < H:
                    tile_arr = strip[y: min(y + tile, H), :]
                    if tile_arr.shape[0] < 20:
                        break
                    meta = {
                        "src_run": src_run,
                        "src_frame": run_frames[0] if run_frames else "",
                    }
                    entry = _save_img(tile_arr, "scroll", meta)
                    if entry:
                        pool_images.append(entry)
                    y += step

    # Bütçe kırpma
    capped = False
    dropped = 0
    if len(pool_images) > cap:
        total = len(pool_images)
        # Eşit aralıklı örnekle
        indices = [int(total * i / cap) for i in range(cap)]
        kept = [pool_images[idx] for idx in indices]
        dropped = total - len(kept)
        capped = True
        print(
            f"[shadow_vl] UYARI: havuz {total} görüntü → CAP={cap} uygulandı, "
            f"{dropped} görüntü düşürüldü.",
            file=sys.stderr,
        )
        pool_images = kept

    manifest: dict = {
        "status": "ok",
        "source_dir": str(source_dir) if source_dir else None,
        "total": len(pool_images),
        "capped": capped,
        "dropped": dropped,
        "images": pool_images,
    }
    _write_json(pool_dir / "pool_manifest.json", manifest)
    return pool_dir, manifest


# --------------------------------------------------------------------------- #
# gemma_call model-parametreli kopya (~_vlm_pipeline.gemma_call body, MODEL ile)
# --------------------------------------------------------------------------- #
import base64
import urllib.request


def gemma_call_shadow(frames: list[str], model: str) -> dict:
    """_vlm_pipeline.gemma_call'ın model-parametreli kopyası."""
    import json as _json
    import re as _re

    STRICT_SYS = (
        "Sen bir KAMERA-OCR cihazisin. Filmler/oyuncular hakkinda HICBIR BILGIN YOK ve olamaz. "
        "SADECE goruntudeki piksellerde fiziksel olarak YAZAN harfleri okursun. Bir ismi taniyor "
        "olsan bile EKRANDA YAZMIYORSA ASLA yazma. Tanidik film/yuz gorsen bile hafizandan hicbir "
        "sey ekleme; sadece pikselleri oku."
    )
    PROMPT = (
        "Bu jenerik karelerinde EKRANDA YAZAN metni rollere ata. Net YAZMAYAN hicbir ismi ekleme. "
        'Cikti SADECE JSON: {"yonetmen":["..."],"oyuncular":["..."],'
        '"diger_roller":[{"rol":"...","isimler":["..."]}]}. /no_think'
    )

    def b64(p: str) -> str:
        return base64.b64encode(open(p, "rb").read()).decode()

    msg = {
        "role": "user",
        "content": PROMPT,
        "images": [b64(p) for p in frames],
    }
    body = {
        "model": model,
        "messages": [{"role": "system", "content": STRICT_SYS}, msg],
        "stream": False,
        "think": False,
        "options": {"num_predict": 3072, "temperature": 0, "num_ctx": 16384},
    }
    req = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=_json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    r = _json.loads(urllib.request.urlopen(req, timeout=300).read())
    txt = r.get("message", {}).get("content", "")
    m = _re.search(r"\{.*\}", txt, _re.S)
    if m:
        try:
            return _json.loads(m.group(0))
        except Exception:
            pass
    # bozuk/truncate JSON kurtarma (_vlm_pipeline.gemma_call deseni)
    cand = _re.findall(r'"([^"\\]{3,70})"', txt)
    names = [c.strip() for c in cand if len(c.split()) >= 2]
    return {"oyuncular": names} if names else {}


# --------------------------------------------------------------------------- #
# OCR-uzmani okuyucu yolu (glm-ocr / deepseek-ocr): tek tile -> ham metin
# --------------------------------------------------------------------------- #
OCR_PROMPT = "Read ALL text in this image exactly as written, line by line. Output only the text, nothing else."


def _b64(p):
    return base64.b64encode(open(p, "rb").read()).decode()


def ocr_read_shadow(frame, model):
    """OCR-uzmani okuyucu: tek tile -> ham metin (yapisal JSON DEGIL)."""
    body = {"model": model,
            "messages": [{"role": "user", "content": OCR_PROMPT, "images": [_b64(frame)]}],
            "stream": False, "options": {"temperature": 0, "num_predict": 2048}}
    req = urllib.request.Request("http://localhost:11434/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=300).read())
    return r.get("message", {}).get("content", "")


def _is_chatbot(txt):
    """Footage'da model chatbot'a girer / sahne tarif eder / prompt'u tekrarlar -> tile metnini ele.
    Tarif-modu kaliplari ALİTA dogrulamasinda gozlemlendi (glm bos/blurry tile'i tarif ediyor)."""
    low = txt.lower()
    return any(s in low for s in ("you are a", "helpful assistant", "<|im", "i'm sorry",
                                  "as an ai", "read all text in this image",
                                  "the image is", "the text content in the image",
                                  "no visible text", "does not contain", "appears to be a scene",
                                  "the image shows", "the image depicts"))


def _cand_names(lines):
    """Ham metin satirlarindan aday-isim satirlari (2-8 kelime, harf-agirlikli). Kaba, kiyas icin."""
    out, seen = [], set()
    for s in lines:
        s = s.strip().lstrip("-*#>| ").strip()
        w = s.split()
        if not s or not (2 <= len(w) <= 8):
            continue
        if sum(c.isalpha() for c in s) < len(s) * 0.5:
            continue
        k = s.lower()
        if k not in seen:
            seen.add(k)
            out.append(s)
    return out


def _read_kunye(clip_dir):
    """En son kunye.txt satirlari (OneOCR uretimi) — guard/kiyas icin."""
    ocr_root = Path(clip_dir) / "ocr"
    if not ocr_root.is_dir():
        return []
    kf = sorted(ocr_root.glob("*/kunye.txt"),
                key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    if not kf:
        return []
    try:
        return [l.strip() for l in kf[0].read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
    except Exception:
        return []


def _in_lines(name, lines):
    """name token'larinin cogu OneOCR satirlarinda geciyor mu (kaba fuzzy)."""
    toks = "".join(c.lower() if (c.isalnum() or c.isspace()) else " " for c in name).split()
    if not toks:
        return False
    blob = " ".join(l.lower() for l in lines)
    return sum(1 for t in toks if t in blob) >= max(1, len(toks) - 1)


# --------------------------------------------------------------------------- #
# B) read_pool
# --------------------------------------------------------------------------- #
def read_pool(pool_dir: Path, manifest: dict, clip_dir: Path, out_path: Path,
              pipe, model: str) -> None:
    """Havuz PNG'lerini okut, birleştir, opsiyonel guard uygula, JSON'a yaz."""

    images = manifest.get("images", [])
    pool_files = [entry["file"] for entry in images if Path(entry["file"]).is_file()]

    # ── OCR-UZMANI YOLU (glm-ocr/deepseek): tile -> ham metin -> aday-isim. HAM METİN asıl çıktı. ──
    if "ocr" in model.lower():
        t0 = time.time()
        raw_tiles, all_lines, chatbot = [], [], 0
        raw_rows: list[dict] = []
        for entry in images:
            fp = entry["file"]
            if not Path(fp).is_file():
                continue
            try:
                txt = ocr_read_shadow(fp, model)
            except Exception as e:  # noqa: BLE001
                print(f"[shadow_vl] ocr-read hata {Path(fp).name}: {repr(e)[:80]}", file=sys.stderr)
                continue
            if _is_chatbot(txt):
                chatbot += 1
                continue   # footage-chatbot / prompt-echo atilir (kirletmesin)
            lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
            raw_tiles.append({"file": Path(fp).name, "kind": entry.get("kind"), "text": txt})
            raw_rows.append({
                "engine": "vl",
                "model": model,
                "mode": "ocr_text",
                "file": Path(fp).name,
                "path": str(fp),
                "kind": entry.get("kind"),
                "src_frame": entry.get("src_frame"),
                "src_run": entry.get("src_run"),
                "text": txt,
                "lines": lines,
            })
            all_lines += lines
        cand = _cand_names(all_lines)
        guarded = None
        klines = _read_kunye(clip_dir)
        if klines:
            kept = [n for n in cand if _in_lines(n, klines)]
            guarded = {"candidate_names": kept, "dropped": [n for n in cand if n not in kept]}
        _write_json(out_path, {
            "reader": model, "mode": "ocr_text",
            "candidate_names": cand, "raw_tiles": raw_tiles,
            "guarded": guarded, "chatbot_skipped": chatbot, "status": "ok",
            "_meta": {"model": model, "pool_dir": str(pool_dir),
                      "tiles_read": len(raw_tiles), "lines": len(all_lines),
                      "candidates": len(cand),
                      "duration_sec": round(time.time() - t0, 2),
                      "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())}})
        _write_jsonl(out_path.parent / "raw_reads.jsonl", raw_rows)
        return

    t0 = time.time()
    bs = 6
    batches = [pool_files[i: i + bs] for i in range(0, len(pool_files), bs)]

    results = []
    raw_rows: list[dict] = []
    for batch_index, batch in enumerate(batches):
        try:
            r = gemma_call_shadow(batch, model)
        except Exception as e:
            print(f"[shadow_vl] batch hatası: {e}", file=sys.stderr)
            r = {}
        results.append(r)
        raw_rows.append({
            "engine": "vl",
            "model": model,
            "mode": "structured_json",
            "batch_index": batch_index,
            "files": [Path(p).name for p in batch],
            "parsed": r,
            "lines": [str(x) for x in ((r.get("yonetmen") or []) + (r.get("oyuncular") or []))] if isinstance(r, dict) else [],
        })

    merged = pipe.merge(results)

    # Opsiyonel guard: clip_dir/ocr/*/kunye.txt (en son modified)
    guarded = None
    ocr_root = clip_dir / "ocr"
    kunye_files = sorted(
        ocr_root.glob("*/kunye.txt"),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    ) if ocr_root.is_dir() else []

    if kunye_files:
        kunye_path = kunye_files[0]
        try:
            lines = [ln.strip() for ln in kunye_path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
            import copy
            merged_copy = copy.deepcopy(merged)
            guarded_struct, dropped_names = pipe.ocr_net(merged_copy, lines)
            guarded = {
                "yonetmen": guarded_struct.get("yonetmen", []),
                "oyuncular": guarded_struct.get("oyuncular", []),
                "diger_roller": guarded_struct.get("diger_roller", []),
                "dropped": dropped_names,
            }
        except Exception as e:
            print(f"[shadow_vl] ocr_net guard hatası: {e}", file=sys.stderr)

    # card / scroll sayıları
    card_count = sum(1 for entry in images if entry.get("kind") == "card")
    scroll_count = sum(1 for entry in images if entry.get("kind") == "scroll")
    duration = round(time.time() - t0, 2)
    ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())

    out_obj = {
        "yonetmen": merged.get("yonetmen", []),
        "oyuncular": merged.get("oyuncular", []),
        "diger_roller": merged.get("diger_roller", []),
        "guarded": guarded,
        "status": "ok",
        "_meta": {
            "model": model,
            "pool_dir": str(pool_dir),
            "card_count": card_count,
            "scroll_tile_count": scroll_count,
            "total_sent": len(pool_files),
            "capped": manifest.get("capped", False),
            "batches": len(batches),
            "duration_sec": duration,
            "ts": ts,
        },
    }
    _write_json(out_path, out_obj)
    _write_jsonl(out_path.parent / "raw_reads.jsonl", raw_rows)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    parser = argparse.ArgumentParser(description="Gölge VL aşaması — üretime dokunmaz.")
    parser.add_argument("--clip", required=True, help="clip_dir tam yolu")
    parser.add_argument("--out", required=True, help="çıkış gemma_kunye.json tam yolu")
    parser.add_argument("--source-dir", default=None,
                        help="Opsiyonel doğrudan kaynak frame havuzu; verilirse frames/giris|cikis yerine sadece burası okunur.")
    parser.add_argument("--debug-root", default=None,
                        help="Opsiyonel debug kökü; ara VL havuzu burada tutulur.")
    args = parser.parse_args()

    clip_dir = Path(args.clip)
    out_path = Path(args.out)
    source_dir = Path(args.source_dir) if args.source_dir else None
    debug_root = Path(args.debug_root) if args.debug_root else None
    model = os.environ.get("MITAS_SHADOW_VL_MODEL", MODEL_DEFAULT)

    # --- Modülleri yükle (fail-safe) ---
    dcm = None
    pipe = None
    load_errors: list[str] = []

    try:
        dcm = loadf("db_compose_master", DCM_PATH)
    except Exception as e:
        load_errors.append(f"db_compose_master: {e}")

    try:
        pipe = loadf("_vlm_pipeline", VLM_PATH)
    except Exception as e:
        load_errors.append(f"_vlm_pipeline: {e}")

    if dcm is None or pipe is None:
        _write_json(out_path, {
            "status": "import_error",
            "errors": load_errors,
            "_meta": {"ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())},
        })
        sys.exit(0)

    # args namespace: db_compose_master'ın okuduğu TÜM alanlar
    # (derive_params: tht, min_hold; _prep: deinterlace; slitscan: luma_key;
    #  split_static_cards: card_same_thr, card_min_hold;
    #  compose_slit: no_dedup, no_card_split; polarity her yerde)
    args_ns = types.SimpleNamespace(
        tht=22,
        min_hold=5,
        polarity="auto",
        deinterlace=False,
        luma_key=False,
        no_dedup=False,
        no_card_split=False,
        card_same_thr=6,
        card_min_hold=5,
    )

    try:
        pool_dir, manifest = build_pool(
            clip_dir,
            dcm,
            args_ns,
            source_dir=source_dir,
            pool_dir_override=(debug_root / "pool") if debug_root else None,
        )

        if manifest.get("status") in ("no_frames", "no_readable_frames"):
            _write_json(out_path, {
                "status": manifest["status"],
                "_meta": {
                    "pool_dir": str(pool_dir),
                    "source_dir": str(source_dir) if source_dir else None,
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
                },
            })
            sys.exit(0)

        read_pool(pool_dir, manifest, clip_dir, out_path, pipe, model)

    except Exception as e:
        _write_json(out_path, {
            "status": "error",
            "error": str(e)[:400],
            "_meta": {"ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())},
        })

    sys.exit(0)


if __name__ == "__main__":
    main()
