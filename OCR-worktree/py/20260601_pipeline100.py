"""100-FİLM — BİRLEŞİK SATIR-MOZAİĞİ. CLIP-tespit -> kareleri OCR-konumlu oku -> her kareden YALNIZ görülmemiş satırları kırpıp ekle.
Scroll / yavaş-drift / ayrık-kart / footage -> HEPSİ tek mantık (her satır bir kez). Footage'da yazı yok -> hiç eklenmez (otomatik elenir).
Bonus: text-bandına kırpıldığı için footage arka planı azalır; ve mozaik metni = temiz künye (895-garble biter).
Çıktı: clip_pipeline100/_MASTERS|_KUNYE|_CACHE  + _SUMMARY.json
"""
import sys, os, glob, importlib.util, json, argparse, difflib
from collections import Counter
from pathlib import Path
import numpy as np, cv2
sys.stdout.reconfigure(encoding="utf-8")
def load(m, p):
    s = importlib.util.spec_from_file_location(m, p); mod = importlib.util.module_from_spec(s); sys.modules[m] = mod; s.loader.exec_module(mod); return mod
# Linux fix (2026-07-30): _pipe_ocr 07-16'da env-aware yapılmış ama BU dosyanın
# kendi load'ları ham E:\MITAS kalmıştı — köprü dizin OCR-worktree içermeyince
# import patlıyor, üretim sessizce eski-OneOCR fallback'ine düşüyordu.
# Aynı sınıf: crop-stack'in yarım Linux fix'i (bounding_rect eklendi, words unutuldu).
_PY_KOK = str(Path(os.environ.get("MITAS_PROJECT_ROOT") or r"E:\MITAS") / "OCR-worktree" / "py")
cp = load("cp", _PY_KOK + os.sep + "20260601_clip_probe.py")
cl = load("cl", _PY_KOK + os.sep + "20260601_clean.py")
sl = load("sl", _PY_KOK + os.sep + "20260601_slitscan2.py")   # piksel-mozaiği (hareketli scroll için)
stx = load("stx", _PY_KOK + os.sep + "20260601_stitch.py")    # OCR-uzayında dikme (künye METNİ)
fp = cl.fp; fold = cl.fold; tr_upper = cl.tr_upper; cr = cl.cr
import duckdb

DB = Path(r"F:\REPO_GitHub\DATABASE")
OUT = Path(r"E:\MITAS\OCR-worktree\clip_pipeline100")
MAST = OUT/"_MASTERS"; KUN = OUT/"_KUNYE"; CACHE = OUT/"_CACHE"
THR = 0.5; SEGS = [("giris", "entry_frames"), ("cikis", "exit_frames")]

def safe_of(n): return "".join(c if c.isalnum() else "_" for c in n)[:40]
def near(a, b):
    if not a or not b: return a == b
    if abs(len(a.split())-len(b.split())) > 1: return False
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.82

def read_pos(img):
    """OCR -> [(fold, raw, y0, y1)] y'ye göre sıralı. Uzun görüntü (mozaik) için dikey tile."""
    eng = cl.rw.get_oneocr(); H = img.shape[0]; TILE, OV = 1400, 150; out = []; y = 0
    while y < H:
        tile = img[y:min(y+TILE, H), :]
        if tile.shape[0] < 40: break
        res = eng.recognize_cv2(np.ascontiguousarray(tile))
        for ln in (res.get("lines") or []):
            t = (ln.get("text") or "").strip()
            if not t: continue
            br = ln.get("bounding_rect") or {}
            ys = [float(br.get(k, 0) or 0) for k in ("y1", "y2", "y3", "y4")]
            out.append((fold(t), t, int(min(ys))+y, int(max(ys))+y))
        if y+TILE >= H: break
        y += TILE-OV
    out.sort(key=lambda L: L[2])
    return out

def is_placed(f, placed):
    """zaten yerleştirildi mi: fuzzy YA DA içerme (OCR satır birleştirme/bölme varyasyonu için)."""
    return any(near(f, p) or (len(f) >= 6 and f in p) or (len(p) >= 6 and p in f) for p in placed)

def is_scroll(run, imgs):
    """hareket VAR mı: row-profil tutarlı dikey kayma. Piksel-mozaiği bunda temiz; hareketsizde line-mozaiği."""
    if len(run) < 8: return False
    sigs = [sl.row_sig(imgs[i]) for i in run]
    sh = [sl.best_shift(sigs[k], sigs[k+1]) for k in range(len(sigs)-1)]
    if not sh: return False
    return float(np.median([s for s, c in sh])) >= 3 and float(np.median([c for s, c in sh])) >= 0.4

def _band_dup(a, b, thr=0.95):
    """FIX-A: a yeni band, b son eklenen band; görsel NCC >= thr ise True (dissolve-kart tekrar dedup)."""
    if a is None or b is None: return False
    ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).astype(np.float32)
    h = min(ga.shape[0], gb.shape[0]); w = min(ga.shape[1], gb.shape[1])
    if h < 12 or w < 12: return False
    ga = ga[:h, :w]; gb = gb[:h, :w]
    try:
        r = cv2.matchTemplate(ga, gb, cv2.TM_CCORR_NORMED)
        return float(r.max()) >= thr
    except Exception:
        return False

def _cy(o): return (o[2] + o[3]) / 2.0

def _ocr_shift_run(run, ocr_pos):
    """Her ardışık kare çifti için OCR-tabanlı dikey kayma tahmini -> kümülatif D[kare]."""
    def shift(A, B):
        ds = []
        for a in A:
            if not a[0]: continue
            for b in B:
                if b[0] and (a[0] == b[0] or difflib.SequenceMatcher(None, a[0], b[0]).ratio() >= 0.85):
                    ds.append(_cy(a) - _cy(b)); break
        if not ds: return None
        ds.sort(); return ds[len(ds) // 2]
    shifts = [shift(ocr_pos.get(run[k-1], []), ocr_pos.get(run[k], [])) for k in range(1, len(run))]
    valid = sorted(s for s in shifts if s is not None and 0 <= s < 400)
    gmed = valid[len(valid) // 2] if valid else 0.0   # hareketsiz run: gmed ~0
    D = {run[0]: 0.0}
    for k in range(1, len(run)):
        s = shifts[k-1]; s = s if (s is not None and 0 <= s < 400) else gmed
        D[run[k]] = D[run[k-1]] + s
    return D

# FIX-B: MININST=3 + P-tabanlı konum dedup (linemosaic.py'den taşındı).
# Geçiş-çöpü (1-2 karede görülen kırık OCR parçaları) MININST ile elenir.
# P = kümülatif_kayma + y_merkez  ->  sürüklenmeye dayanıklı kimlik (hareketsizde P ≈ y_merkez).
LMR_MININST = int(os.environ.get("MITAS_LMR_MININST", "3"))
LMR_FUZZY   = 0.90
LMR_MERGEP  = 60.0   # piksel; hareketsizde geniş tutulabilir
LMR_ROWTOL  = 5.0

def line_mosaic_run(run, imgs, ocr_pos, placed, W, pad=4):
    """hareketsiz run: her kareden GÖRÜLMEMİŞ satırların bandını kırp (drift/kart/footage sınırlı).
    FIX-A: son eklenen banda görsel NCC >= 0.95 ise band atlanır (dissolve-logo tekrarı biter).
    FIX-B: MININST>=3 + P-dedup — geçiş-çöpü (1-2 karede görülen kırık parça) atlanır.
           MITAS_LMR_MININST=1 ile eski davranışa dönülür."""
    MININST = LMR_MININST
    D = _ocr_shift_run(run, ocr_pos)

    # 1) Kare bazlı satır örnekleri topla (linemosaic adım 1-2)
    def xcenter(e): return (e[4]+e[5])/2.0 if len(e) >= 6 else 0.0
    rows = []
    for f in run:
        es = sorted(ocr_pos.get(f, []), key=lambda e: (e[2]+e[3])/2.0)
        grp = []
        def flush(grp, f=f):
            if not grp: return
            y1 = min(e[2] for e in grp); y2 = max(e[3] for e in grp)
            cols = sorted([(xcenter(e), e[1], e[0]) for e in grp], key=lambda t: t[0])
            canon = " ".join(t[2] for t in cols)
            rows.append(dict(frame=f, y1=y1, y2=y2,
                             P=D[f]+(y1+y2)/2.0, cols=cols, canon=canon))
        for e in es:
            if not e[1]: continue
            yc = (e[2]+e[3])/2.0
            if grp and yc - (grp[-1][2]+grp[-1][3])/2.0 > LMR_ROWTOL:
                flush(grp); grp = []
            grp.append(e)
        flush(grp)

    # 2) Metin-fuzzy + P-pencere dedup (linemosaic adım 2)
    groups = []
    for r in sorted(rows, key=lambda r: r["P"]):
        best, bestrat = None, LMR_FUZZY
        for g in groups:
            if abs(r["P"] - g["sumP"]/len(g["insts"])) > LMR_MERGEP: continue
            rat = difflib.SequenceMatcher(None, r["canon"], g["canon"]).ratio()
            if rat >= bestrat: best, bestrat = g, rat
        if best is None:
            groups.append(dict(insts=[r], sumP=r["P"], canon=r["canon"]))
        else:
            best["insts"].append(r); best["sumP"] += r["P"]

    # 3) MININST filtresi + P sırasına göre sırala
    groups = [g for g in groups if len(g["insts"]) >= MININST]
    groups.sort(key=lambda g: g["sumP"] / len(g["insts"]))

    # 4) Her grup için: placed-dedup geçerse en iyi kareyi kırp + band ekle (FIX-A dahil)
    bands = []; lines = []
    last_band = None
    for g in groups:
        canon = g["canon"]
        # placed-dedup: grup zaten placed ise atla (önceki run'lardan birikmiş)
        if is_placed(canon, placed): continue
        # en keskin kare: run ortasına (H*0.45) en yakın örnek
        H0 = imgs[run[0]].shape[0]; sy = H0 * 0.45
        best_inst = min(g["insts"], key=lambda r: abs((r["y1"]+r["y2"])/2.0 - sy))
        f = best_inst["frame"]
        H = imgs[f].shape[0]
        y0 = max(0, best_inst["y1"] - pad); y1 = min(H, best_inst["y2"] + pad)
        if y1 <= y0: continue
        b = imgs[f][y0:y1, :]
        if b.shape[1] < W: b = cv2.copyMakeBorder(b, 0, 0, 0, W-b.shape[1], cv2.BORDER_CONSTANT, value=(0, 0, 0))
        # FIX-A: görsel dedup
        if _band_dup(b, last_band):
            placed.append(canon); lines.append(g["insts"][0]["cols"][0][1] if g["insts"][0]["cols"] else "")
            continue
        last_band = b; bands.append(b)
        placed.append(canon)
        # mod-oylama ile en sık okunan ham metni seç
        cands = [" ".join(t[1] for t in sorted(ins["cols"], key=lambda t: t[0])) for ins in g["insts"]]
        lines.append(Counter(cands).most_common(1)[0][0] if cands else "")
    return bands, lines

def _textmask_on():
    return os.environ.get("MITAS_TEXTMASK", "").strip().lower() in ("1", "true", "on", "yes")

def text_isolate(bgr, ksize=23, min_area=10):
    """#1 TEXT-MASK (GPT v2 master_textonly fikri): footage arka-planini bastir, yaziyi (ince stroke)
    BEYAZ-siyaha indir. Polarite-duyarli (top-hat parlak / black-hat koyu yazi) + benek-filtresi
    (acma + alan). Pürüzsüz footage'da mukemmel; karmasik canli-aksiyon footage'inda kismi."""
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) if bgr.ndim == 3 else bgr
    # KOSULLU: koyu/temiz bg (median<70) -> footage yok, ZATEN temiz-kart -> DOKUNMA (clean regresyonunu onler).
    # Yalniz parlak/footage'li blokta text-mask uygula (AMELIA gokyuzu, 300 altin vs.).
    if float(np.median(g)) < 70:
        return bgr if bgr.ndim == 3 else cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ksize, ksize))
    th = cv2.morphologyEx(g, cv2.MORPH_TOPHAT, k); bh = cv2.morphologyEx(g, cv2.MORPH_BLACKHAT, k)
    resp = cv2.max(th, bh).astype(np.float32)
    blur = cv2.GaussianBlur(resp, (0, 0), 9); sd = float(resp.std()) or 1.0
    keep = ((resp > (blur + 0.6 * sd)) & (resp > 12)).astype(np.uint8)
    keep = cv2.morphologyEx(keep, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    nlab, lab, stats, _ = cv2.connectedComponentsWithStats(keep, connectivity=8)
    good = np.zeros(nlab, bool)
    for i in range(1, nlab):
        good[i] = stats[i, cv2.CC_STAT_AREA] >= min_area
    keep = good[lab].astype(np.uint8)
    # stroke-maskesi -> DOLU text-REGION (kapat ile harf-ici dolsun: outline DEGIL solid glyph)
    region = cv2.morphologyEx(keep, cv2.MORPH_CLOSE, k)
    region = cv2.dilate(region, np.ones((3, 3), np.uint8))
    # blok polaritesi: parlak-yazi -> orijinal piksel; koyu-yazi -> ters (yazi parlak kalsin)
    base = g if float(th.sum()) >= float(bh.sum()) else (255 - g)
    out = np.zeros_like(g); out[region > 0] = base[region > 0]
    return cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)

def _is_ghost(bf, seen):
    """#2 RUNS-ARASI FUZZY-DEDUP: blok satirlarinin %80+'i zaten dizildiyse tekrar (ghost) -> True."""
    if not bf:
        return False
    dup = sum(1 for f in bf if any(near(f, s) or (len(f) >= 6 and f in s) or (len(s) >= 6 and s in f) for s in seen))
    return dup / len(bf) >= 0.8

def _framegate_on():
    return os.environ.get("MITAS_FRAMEGATE", "").strip().lower() in ("1", "true", "on", "yes")

_LLMQC = None
def _qc_seg_labels(ocr_pos):
    """#6-GORSEL frame-gate: segmentteki TUM ham-satirlari qwen-QC ile TEK-cagri etiketle -> {ham: etiket}."""
    global _LLMQC
    if _LLMQC is None:
        _LLMQC = load("_llmqc", r"E:\MITAS\OCR-worktree\py\_llm_qc.py")
    texts = [L[1] for i in ocr_pos for L in ocr_pos[i] if L[1]]
    try:
        return _LLMQC.qc_text_labels(texts)
    except Exception:
        return {}

def _frame_is_credit(lines, lab):
    """GUVENLI gate: kareyi YALNIZ kesin-diegetik (UYARI/ALTYAZI VAR) + HIC KADRO/DUBLAJ yok ise ELE.
    Yazisiz (footage) kareyi burada eleme (mevcut footage-gate'e birak); garble/COP'a DOKUNMA (false-drop=0)."""
    ls = [L for L in lines if L[1]]
    if not ls:
        return True
    kad = sum(1 for L in ls if lab.get(L[1]) in ("KADRO", "DUBLAJ"))
    die = sum(1 for L in ls if lab.get(L[1]) in ("UYARI", "ALTYAZI"))
    return not (die > 0 and kad == 0)

def compose_hybrid(frames, idx, imgs, ocr_pos):
    """KÜNYE METNİ = OCR-uzayında dikme (stx.stitch_kunye: her satırın EN TEMİZ okuması; garble tufanı biter).
    GÖRSEL MASTER = panorama metin taşıyorsa o (slitscan2); yoksa line-mozaiği bantları (asla siyah)."""
    if _framegate_on() and idx:
        # #6 GORSEL frame-gate: kesin-diegetik (scene/altyazi, kredi-yok) kareyi master+metin'den ele
        _lab = _qc_seg_labels({i: ocr_pos[i] for i in idx})
        idx = [i for i in idx if _frame_is_credit(ocr_pos[i], _lab)] or idx
    runs = [[idx[0]]]
    for j in idx[1:]:
        (runs[-1].append(j) if j-runs[-1][-1] <= 3 else runs.append([j]))
    W = max(imgs[i].shape[1] for i in idx)
    # --- KÜNYE METNİ: OCR-uzayı dikme (per-frame garble -> tek temiz okuma; isim DROP yok) ---
    text, low_conf, medconf = stx.stitch_kunye(runs, ocr_pos)
    # --- GÖRSEL MASTER: temiz panorama varsa onu, yoksa line-mozaiği bantları ---
    blocks = []; vplaced = []
    for run in runs:
        if is_scroll(run, imgs):
            blk = sl.slitscan2([frames[i] for i in run])
            if blk is not None and getattr(blk, "size", 0) and blk.shape[0] >= 60:
                if len([L for L in read_pos(blk) if L[0]]) >= 5:
                    # FIX-C: saf-footage/logo bloğu at (parlak-piksel oranı < %0.5 → gerçek yazı yok)
                    g = cv2.cvtColor(blk, cv2.COLOR_BGR2GRAY) if blk.ndim == 3 else blk
                    bright_ratio = float((g > 150).sum()) / max(1, g.size)
                    if bright_ratio < 0.005:
                        pass  # footage smear: line_mosaic'e düş
                    else:
                        blocks.append(blk); continue
        bands, _ = line_mosaic_run(run, imgs, ocr_pos, vplaced, W)
        blocks += bands
    if not blocks: return None, text
    if _textmask_on():
        # #2 runs-arasi fuzzy-dedup: zaten dizilmis metni tasiyan blogu (ghost-tekrar) at
        seen = []; kept = []
        for b in blocks:
            bf = [L[0] for L in read_pos(b) if L[0]]
            if _is_ghost(bf, seen):
                continue
            seen.extend(bf); kept.append(b)
        blocks = kept or blocks
        # #1 text-mask: her blogun footage arka-planini bastir (yazi BEYAZ-siyah)
        blocks = [text_isolate(b) for b in blocks]
    norm = [cv2.copyMakeBorder(b, 0, 0, 0, W-b.shape[1], cv2.BORDER_CONSTANT, value=(0, 0, 0)) if b.shape[1] < W else b for b in blocks]
    return np.vstack(norm), text

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=100); ap.add_argument("--only", default="")
    a = ap.parse_args()
    for d in (MAST, KUN, CACHE): d.mkdir(parents=True, exist_ok=True)
    films = []
    for d in sorted(DB.iterdir(), key=lambda p: p.name.lower()):
        if not d.is_dir(): continue
        if a.only and a.only.lower() not in d.name.lower(): continue
        if glob.glob(str(d/"entry_frames"/"*.png")) or glob.glob(str(d/"exit_frames"/"*.png")): films.append(d)
        if not a.only and len(films) >= a.n: break
    print(f"{len(films)} film. CLIP yükleniyor...", flush=True)
    model, preprocess, tok = cp.load_clip(); ls = model.logit_scale.exp().item()
    cred = cp.class_embed(model, tok, cp.CREDIT_PROMPTS); scene = cp.class_embed(model, tok, cp.SCENE_PROMPTS)
    con = duckdb.connect(cr.DB, read_only=True)
    summary = []
    for n, d in enumerate(films, 1):
        safe = safe_of(d.name); asr = ""
        ap_ = list(d.glob("audio_transcript.txt"))
        if ap_: asr = fold(ap_[0].read_text(encoding="utf-8", errors="ignore"))
        rec = {"film": d.name}
        for seg, sub in SEGS:
            if (KUN/f"{safe}__{seg}.txt").exists(): continue       # resume
            frames = sorted(glob.glob(str(d/sub/"*.png")))
            if not frames: continue
            ps = cp.med_smooth(cp.score_frames(model, preprocess, frames, cred, scene, ls), 5)
            idx = [i for i in range(len(ps)) if ps[i] >= THR]
            if not idx:
                (KUN/f"{safe}__{seg}.txt").write_text("", encoding="utf-8"); rec[seg] = {"frames": len(frames), "credit": 0, "kunye": 0, "master_h": 0}; continue
            imgs = {i: fp.rd(frames[i]) for i in idx}
            ocr_pos = {i: read_pos(imgs[i]) for i in idx}
            master, placed_raw = compose_hybrid(frames, idx, imgs, ocr_pos)
            merged, buckets, asr_drop, dieg = cl.clean(placed_raw, con, asr)
            if master is not None: fp.wr(MAST/f"{safe}__{seg}.png", master)
            (KUN/f"{safe}__{seg}.txt").write_text(("# DIEGETIK %{:.0f}\n".format(dieg*100) if dieg > 0.30 else "") + "\n".join(tr_upper(t) for t, _, _ in merged), encoding="utf-8")
            (CACHE/f"{safe}__{seg}.json").write_text(json.dumps({"idx": idx, "ocr_pos": {str(i): ocr_pos[i] for i in idx}}, ensure_ascii=False), encoding="utf-8")
            rec[seg] = {"frames": len(frames), "credit": len(idx), "kunye": len(merged), "master_h": int(master.shape[0]) if master is not None else 0, "diegetik": round(dieg, 2)}
        summary.append(rec)
        g = rec.get("giris", {}); c = rec.get("cikis", {})
        print(f"  [{n}/{len(films)}] {d.name[:32]:34} G:k={g.get('credit')} künye={g.get('kunye')} h={g.get('master_h')} | Ç:k={c.get('credit')} künye={c.get('kunye')} h={c.get('master_h')}", flush=True)
    con.close()
    (OUT/"_SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> {MAST}", flush=True)

if __name__ == "__main__":
    main()
