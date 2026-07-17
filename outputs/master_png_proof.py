# -*- coding: utf-8 -*-
"""AŞAMA 1 — KANIT: compose_hybrid -> master PNG + OneOCR karşılaştırma.

CLIP ATLANIR (GPU yasak; ATLAS şu an GPU kullanıyor).
Tüm kareleri idx olarak alırız (CLIP-failed fallback ile aynı davranış).
Seçilen hublar:
  1. AHLAT AĞACI 2018-9024-1-0000-90-1   (cikis segment)
  2. BORSA 1987-0330-1-0000-00-1          (cikis segment)
  3. BRONX SOKAKLARINDA 1981-0262-1-0000-00-1 (cikis segment)

Çalıştır: E:\MITAS\venvs\ocr\Scripts\python.exe outputs\master_png_proof.py
"""
import sys, glob, json, difflib, time
from pathlib import Path
import numpy as np, cv2

sys.stdout.reconfigure(encoding="utf-8")

# ── OCR-worktree modüllerini ekle ────────────────────────────────────────
PY_DIR = Path(r"E:\MITAS\OCR-worktree\py")
sys.path.insert(0, str(PY_DIR))

import importlib.util

def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

print("[proof] modüller yükleniyor...", flush=True)
cp  = _load("cp",  str(PY_DIR / "20260601_clip_probe.py"))
cl  = _load("cl",  str(PY_DIR / "20260601_clean.py"))
sl  = _load("sl",  str(PY_DIR / "20260601_slitscan2.py"))
stx = _load("stx", str(PY_DIR / "20260601_stitch.py"))
fp  = cl.fp        # full_pipeline (rd + wr)
cr  = cl.cr        # credit_read_v1 (DB)
tr_upper = cl.tr_upper
print("[proof] modüller tamam.", flush=True)

# ── read_pos: OCR-worktree pipeline100 kalıbı (dikey tile döngüsü) ───────
def read_pos(img):
    """OneOCR -> [(fold, raw, y0, y1)] y'ye göre sıralı. Uzun görüntü için dikey tile."""
    eng = cl.rw.get_oneocr()
    H = img.shape[0]
    TILE, OV = 1400, 150
    out = []
    y = 0
    while y < H:
        tile = img[y:min(y + TILE, H), :]
        if tile.shape[0] < 40:
            break
        res = eng.recognize_cv2(np.ascontiguousarray(tile))
        for ln in (res.get("lines") or []):
            t = (ln.get("text") or "").strip()
            if not t:
                continue
            br = ln.get("bounding_rect") or {}
            ys = [float(br.get(k, 0) or 0) for k in ("y1", "y2", "y3", "y4")]
            out.append((cl.fold(t), t, int(min(ys)) + y, int(max(ys)) + y))
        if y + TILE >= H:
            break
        y += TILE - OV
    out.sort(key=lambda L: L[2])
    return out

# ── compose_hybrid: pipeline100.py'den kopyalandı (OCR-worktree kanonik) ──
# (import yerine kopyalandı çünkü pipeline100.py'nin main() DuckDB ve CLIP
#  açar; sadece compose_hybrid fonksiyonuna ihtiyacımız var)

def near(a, b):
    if not a or not b:
        return a == b
    if abs(len(a.split()) - len(b.split())) > 1:
        return False
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.82

def is_placed(f, placed):
    return any(near(f, p) or (len(f) >= 6 and f in p) or (len(p) >= 6 and p in f)
               for p in placed)

def is_scroll(run, imgs):
    if len(run) < 8:
        return False
    sigs = [sl.row_sig(imgs[i]) for i in run]
    sh = [sl.best_shift(sigs[k], sigs[k + 1]) for k in range(len(sigs) - 1)]
    if not sh:
        return False
    return (float(np.median([s for s, c in sh])) >= 3
            and float(np.median([c for s, c in sh])) >= 0.4)

def line_mosaic_run(run, imgs, ocr_pos, placed, W, pad=4):
    bands = []; lines_out = []
    for i in run:
        H = imgs[i].shape[0]
        new = [L for L in ocr_pos[i] if L[0] and not is_placed(L[0], placed)]
        if not new:
            continue
        y0 = max(0, min(L[2] for L in new) - pad)
        y1 = min(H, max(L[3] for L in new) + pad)
        if y1 <= y0:
            continue
        b = imgs[i][y0:y1, :]
        if b.shape[1] < W:
            b = cv2.copyMakeBorder(b, 0, 0, 0, W - b.shape[1],
                                   cv2.BORDER_CONSTANT, value=(0, 0, 0))
        bands.append(b)
        for L in new:
            placed.append(L[0])
            lines_out.append(L[1])
    return bands, lines_out

def compose_hybrid(frames, idx, imgs, ocr_pos):
    """GÖRSEL MASTER + OCR-metin (stx.stitch_kunye). OCR-worktree kanonik."""
    runs = [[idx[0]]]
    for j in idx[1:]:
        (runs[-1].append(j) if j - runs[-1][-1] <= 3 else runs.append([j]))
    W = max(imgs[i].shape[1] for i in idx)
    text, low_conf, medconf = stx.stitch_kunye(runs, ocr_pos)
    blocks = []; vplaced = []
    for run in runs:
        if is_scroll(run, imgs):
            blk = sl.slitscan2([frames[i] for i in run])
            if blk is not None and getattr(blk, "size", 0) and blk.shape[0] >= 60:
                if len([L for L in read_pos(blk) if L[0]]) >= 5:
                    blocks.append(blk)
                    continue
        bands, _ = line_mosaic_run(run, imgs, ocr_pos, vplaced, W)
        blocks += bands
    if not blocks:
        return None, text
    norm_blocks = [
        cv2.copyMakeBorder(b, 0, 0, 0, W - b.shape[1], cv2.BORDER_CONSTANT, value=(0, 0, 0))
        if b.shape[1] < W else b
        for b in blocks
    ]
    return np.vstack(norm_blocks), text

# ── hub tanımları ─────────────────────────────────────────────────────────
DB_ROOT = Path(r"F:\REPO_GitHub\DATABASE")
KUNYE_DIR = Path(r"E:\MITAS\OCR-worktree\clip_pipeline100\_KUNYE")
MASTER_REF_DIR = Path(r"E:\MITAS\OCR-worktree\clip_pipeline100\_MASTERS")
OUT_DIR = Path(r"E:\MITAS\outputs\_master_proof")
OUT_DIR.mkdir(parents=True, exist_ok=True)

HUBS = [
    {
        "name": "AHLAT",
        "dir": DB_ROOT / "AHLAT AĞACI 2018-9024-1-0000-90-1",
        "seg": "exit_frames",
        "existing_kunye": KUNYE_DIR / "AHLAT_AĞACI_2018_9024_1_0000_90_1__cikis.txt",
        "ref_master": MASTER_REF_DIR / "AHLAT_AĞACI_2018_9024_1_0000_90_1__cikis.png",
        "out_master": OUT_DIR / "AHLAT_cikis_master.png",
    },
    {
        "name": "BORSA",
        "dir": DB_ROOT / "BORSA 1987-0330-1-0000-00-1",
        "seg": "exit_frames",
        "existing_kunye": KUNYE_DIR / "BORSA_1987_0330_1_0000_00_1__cikis.txt",
        "ref_master": MASTER_REF_DIR / "BORSA_1987_0330_1_0000_00_1__cikis.png",
        "out_master": OUT_DIR / "BORSA_cikis_master.png",
    },
    {
        "name": "BRONX",
        "dir": DB_ROOT / "BRONX SOKAKLARINDA 1981-0262-1-0000-00-1",
        "seg": "exit_frames",
        "existing_kunye": KUNYE_DIR / "BRONX_SOKAKLARINDA_1981_0262_1_0000_00_1__cikis.txt",
        "ref_master": MASTER_REF_DIR / "BRONX_SOKAKLARINDA_1981_0262_1_0000_00_1__cikis.png",
        "out_master": OUT_DIR / "BRONX_cikis_master.png",
    },
]

# ── karşılaştırma yardımcıları ────────────────────────────────────────────
def load_existing_kunye(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return [l.strip() for l in lines if l.strip() and not l.startswith("#")]

def compare_lines(existing: list[str], master_lines: list[str]) -> dict:
    """Yeni satırlar (master'da var, existing'de yok) ve kaybedilen satırlar."""
    def fold_set(lst):
        return {l.lower().strip() for l in lst if l.strip()}
    ex_set = fold_set(existing)
    ms_set = fold_set(master_lines)
    added = [l for l in master_lines if l.lower().strip() not in ex_set]
    lost  = [l for l in existing  if l.lower().strip() not in ms_set]
    return {"added": added, "lost": lost, "existing_count": len(existing),
            "master_count": len(master_lines)}

# ── fail-safe testi: bozuk girdi verip pipeline'ın devam ettiğini göster ──
def test_failsafe():
    """compose_hybrid'e kasıtlı bozuk girdi -> exception -> üst catch -> devam."""
    print("\n[failsafe] Bozuk girdi testi...", flush=True)
    try:
        result = compose_hybrid(
            frames=[],          # boş liste -> runs oluşturulamaz
            idx=[0],            # ama idx var -> KeyError / IndexError
            imgs={},            # boş dict -> imgs[0] KeyError
            ocr_pos={},
        )
        print(f"[failsafe] compose_hybrid bozuk girdiyle döndü: {type(result)}", flush=True)
    except Exception as e:
        print(f"[failsafe] compose_hybrid exception attı: {type(e).__name__}: {e}", flush=True)
        print("[failsafe] -> Entegrasyonda try/except bunu yakalar, mevcut lines korunur. OK", flush=True)

# ── ana döngü ─────────────────────────────────────────────────────────────
results = []

for hub in HUBS:
    name = hub["name"]
    seg_dir = hub["dir"] / hub["seg"]
    print(f"\n{'='*60}", flush=True)
    print(f"[{name}] {seg_dir}", flush=True)

    if not seg_dir.exists():
        print(f"[{name}] HATA: Dizin bulunamadı: {seg_dir}", flush=True)
        results.append({"hub": name, "error": "dir_not_found"})
        continue

    # Kareleri topla — uniform örnekleme, max 40 kare (CLIP yok)
    all_frames = sorted(glob.glob(str(seg_dir / "*.png")))
    if not all_frames:
        print(f"[{name}] HATA: frame yok", flush=True)
        results.append({"hub": name, "error": "no_frames"})
        continue

    MAX_FRAMES = 40
    if len(all_frames) > MAX_FRAMES:
        step = len(all_frames) / MAX_FRAMES
        sel_frames = [all_frames[int(i * step)] for i in range(MAX_FRAMES)]
    else:
        sel_frames = all_frames
    idx = list(range(len(sel_frames)))
    print(f"[{name}] {len(all_frames)} kare -> {len(sel_frames)} seçildi (uniform, CLIP atlandı)", flush=True)

    # Kareleri yükle (fp.rd = Türkçe-path güvenli)
    t0 = time.perf_counter()
    imgs = {}
    load_errors = 0
    for i, fp_path in enumerate(sel_frames):
        img = fp.rd(fp_path)
        if img is None:
            load_errors += 1
        else:
            imgs[i] = img
    if not imgs:
        print(f"[{name}] HATA: hiçbir kare okunamadı", flush=True)
        results.append({"hub": name, "error": "all_frames_unreadable"})
        continue
    idx_valid = [i for i in idx if i in imgs]

    # ocr_pos: her geçerli kare için read_pos
    print(f"[{name}] OneOCR read_pos ({len(idx_valid)} kare)...", flush=True)
    ocr_pos = {}
    ocr_errors = 0
    for i in idx_valid:
        try:
            ocr_pos[i] = read_pos(imgs[i])
        except Exception as e:
            ocr_errors += 1
            ocr_pos[i] = []
            print(f"[{name}]   kare {i} OCR hatası: {e}", flush=True)

    # compose_hybrid
    print(f"[{name}] compose_hybrid...", flush=True)
    master = None
    stitch_lines = []
    try:
        master, placed_raw = compose_hybrid(sel_frames, idx_valid, imgs, ocr_pos)
        # clean ile tr_upper
        try:
            import duckdb as _ddb
            con = _ddb.connect(str(cr.DB), read_only=True)
            merged, _, _, _ = cl.clean(placed_raw, con, "")
            con.close()
            stitch_lines = [tr_upper(t) for t, _, _ in merged]
        except Exception as e:
            print(f"[{name}]   clean/DB hatası: {e} — ham placed_raw kullanılıyor", flush=True)
            stitch_lines = [tr_upper(t) for t in placed_raw]
    except Exception as e:
        print(f"[{name}] compose_hybrid HATA: {e}", flush=True)
        results.append({"hub": name, "error": f"compose_hybrid:{e}"})
        continue

    elapsed = round(time.perf_counter() - t0, 1)
    print(f"[{name}] süre: {elapsed}s, stitch_lines: {len(stitch_lines)}", flush=True)

    # Master PNG yaz
    if master is not None:
        fp.wr(hub["out_master"], master)
        master_h, master_w = master.shape[:2]
        print(f"[{name}] master PNG: {hub['out_master']} ({master_w}×{master_h}px)", flush=True)
    else:
        print(f"[{name}] master None (footage/boş segment?)", flush=True)
        master_h = master_w = 0

    # Mevcut kunye.txt ile karşılaştır
    existing = load_existing_kunye(hub["existing_kunye"])
    cmp = compare_lines(existing, stitch_lines)
    print(f"[{name}] mevcut={cmp['existing_count']} satır | master_ocr={cmp['master_count']} satır", flush=True)
    print(f"[{name}] EKLENEN ({len(cmp['added'])} satır):", flush=True)
    for l in cmp["added"][:20]:
        print(f"         + {l}", flush=True)
    if len(cmp["added"]) > 20:
        print(f"         ... (+{len(cmp['added'])-20} daha)", flush=True)
    print(f"[{name}] KAYBEDİLEN ({len(cmp['lost'])} satır):", flush=True)
    for l in cmp["lost"][:20]:
        print(f"         - {l}", flush=True)

    # Master üzerinde ayrıca OneOCR koş (doğrudan master PNG'yi oku)
    master_direct_lines = []
    if master is not None:
        print(f"[{name}] Master PNG üzerinde doğrudan OneOCR...", flush=True)
        try:
            master_ocr = read_pos(master)
            master_direct_lines = [tr_upper(L[1]) for L in master_ocr if L[0]]
            print(f"[{name}]   master doğrudan OCR: {len(master_direct_lines)} satır", flush=True)
            cmp2 = compare_lines(existing, master_direct_lines)
            print(f"[{name}]   master-direct EKLENEN: {len(cmp2['added'])} / KAYBEDİLEN: {len(cmp2['lost'])}", flush=True)
        except Exception as e:
            print(f"[{name}]   master doğrudan OCR hatası: {e}", flush=True)

    results.append({
        "hub": name,
        "frames_total": len(all_frames),
        "frames_sampled": len(sel_frames),
        "master_size": f"{master_w}x{master_h}" if master is not None else None,
        "master_path": str(hub["out_master"]) if master is not None else None,
        "stitch_lines": len(stitch_lines),
        "existing_lines": cmp["existing_count"],
        "added": len(cmp["added"]),
        "lost": len(cmp["lost"]),
        "master_direct_lines": len(master_direct_lines),
        "elapsed_s": elapsed,
        "ocr_errors": ocr_errors,
        "load_errors": load_errors,
    })

# ── failsafe testi ────────────────────────────────────────────────────────
test_failsafe()

# ── özet tablo ────────────────────────────────────────────────────────────
print(f"\n{'='*60}", flush=True)
print("ÖZET TABLO", flush=True)
print(f"{'Hub':<10} {'Mevcut':>8} {'Master-OCR':>10} {'Eklenen':>8} {'Kaybedilen':>10} {'Master-PNG':>20}", flush=True)
print("-" * 70, flush=True)
for r in results:
    if "error" in r:
        print(f"{r['hub']:<10}  HATA: {r['error']}", flush=True)
    else:
        ms = r.get("master_size") or "None"
        print(f"{r['hub']:<10} {r['existing_lines']:>8} {r['stitch_lines']:>10} {r['added']:>8} {r['lost']:>10} {ms:>20}", flush=True)

# ── sonuç JSON ────────────────────────────────────────────────────────────
out_json = OUT_DIR / "proof_results.json"
out_json.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n[proof] Sonuçlar: {out_json}", flush=True)
print(f"[proof] Master PNG'ler: {OUT_DIR}", flush=True)

# ── karar kapısı ──────────────────────────────────────────────────────────
ok = [r for r in results if "error" not in r and r.get("master_size") and r.get("stitch_lines", 0) > 0]
print(f"\n[KARAR KAPISI] {len(ok)}/{len(HUBS)} hub'da anlamlı çıktı üretildi.", flush=True)
if ok:
    print("[KARAR] GEÇER → Aşama 2 (entegrasyon) yapılabilir.", flush=True)
else:
    print("[KARAR] BAŞARISIZ → Entegrasyona GEÇME.", flush=True)
