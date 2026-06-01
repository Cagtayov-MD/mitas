"""20260531_2330 — 3 OKUYUCU AYRI AYRI test koşusu: OneOCR / Paddle / qwen + KB desteği.
15 film (eski Türk / yabancı-dublaj / yeni Türk). Her (film,seg,master) için:
  - OneOCR oku  -> oneocr.txt
  - Paddle oku  -> paddle.txt
  - qwen oku    -> qwen.txt
  - KB desteği: her okuyucunun satırlarına kb-exact (≥2 token, notable kişi) uygula,
    kaç satır DEĞİŞTİ / TEYİT edildi / RAW kaldı say.
Birleştirme YOK — okuyucular ayrı. compare.json + _SUMMARY_3WAY.{json,txt}.
Fidelity: KB yalnız notable-isim YAZIM düzeltir; isim ekleme/çıkarma/değiştirme YOK.
"""
import sys, json, time, base64, urllib.request, importlib.util
from pathlib import Path
import numpy as np, duckdb

sys.stdout.reconfigure(encoding="utf-8")

# credit_read_v1 modülünü yeniden kullan (fold, FOLD_SQL, kb_exact_batch, get_paddle, ocr_master, fp)
spec = importlib.util.spec_from_file_location("cr", r"E:\MITAS\OCR-worktree\py\20260531_credit_read_v1.py")
cr = importlib.util.module_from_spec(spec); sys.modules["cr"] = cr; spec.loader.exec_module(cr)
fp = cr.fp
fold = cr.fold

import cv2, oneocr

# ── sabitler ──────────────────────────────────────────────────────────────
TESTER_IN  = Path(r"E:\MITAS\OCR-worktree\tester_fiso")
OUT        = Path(r"E:\MITAS\OCR-worktree\tester_3way")
DB         = cr.DB
OLLAMA     = fp.OLLAMA
MODEL      = fp.MODEL

OCR_TILE, OCR_OV   = 1500, 120     # OneOCR + Paddle dikey tile
QWEN_TILE, QWEN_OV = 1200, 100     # qwen tile (timeout güvenli)
QWEN_TIMEOUT       = 180
SKIP_QWEN          = False

QWEN_PROMPT = ("Transcribe the film-credit text in this image EXACTLY, top to bottom, one entry per line. "
               "Use '?' for unreadable characters. Do NOT guess, do NOT add names not visible. "
               "Preserve Turkish letters: ç ğ ı İ ö ş ü. Return JSON: {\"lines\":[\"...\",\"...\"]}")

# 15 film: (etiket, dizin-substring benzersiz). Karışık: eski Türk / yabancı-dublaj / yeni.
FILMS = [
    ("KANSAS_1950",      "1950-0016-1-0000-00-1-KANSAS_LI_SÜVARİLER"),   # eski yabancı-dublaj
    ("OLUM_ASANSORU_1958","1958-0020-1-0000-00-1-ÖLÜM_ASANSÖRÜ"),         # eski Türk
    ("DRAKULA_1960",     "1960-0046-1-0000-00-1-DRAKULA_NIN_GELİNLERİ"),  # eski yabancı-dublaj
    ("ZENGIN_1964",      "1964-0045-1-0000-00-1-ZENGİN_OLSAYDIN"),        # eski Türk
    ("GUZEL_OLUM_1968",  "1968-0022-1-0000-00-1-GÜZEL_BİR_ÖLÜM"),         # eski Türk
    ("ANJELIK_1968",     "1968-0067-1-0000-00-1-ANJELIK_VE_SULTAN"),      # eski yabancı-dublaj
    ("KIZGIN_SILAH_1953","1953-0044-1-0000-00-1-KIZGIN_SİLAH"),           # eski (sadece giris)
    ("SON_METRO_1980",   "1980-0186-1-0000-00-1-SON_METRO"),             # yabancı-dublaj scroll
    ("XMEN_2000",        "2000-0433-1-0000-90-1-X-MEN"),                 # yabancı-dublaj
    ("JURASSIC_1997",    "1997-0265-1-0000-00-1-JURASSIC_PARK"),         # yabancı-dublaj
    ("DIRILIS_2014",     "2014-0053-0-0010-90-1-DİRİLİŞ_ERTUĞRUL"),      # yeni Türk dizi (bilinen)
    ("YALAZA_2017",      "2017-0019-0-0001-90-1-YALAZA"),                # yeni Türk dizi (sulu-boya bg)
    ("BIZIM_EVIN_2000",  "2000-0111-0-0617-00-1-BİZİM_EVİN_HALLERİ"),    # Türk dizi
    ("SENIN_HIKAYEN_2024","2024-1315-1-0000-90-1-SENİN_HİKAYEN"),         # yeni Türk film
    ("ROBINSON_2025",    "2025-1011-1-0000-50-1-ROBINSON_CRUSOE"),       # yeni
]

TR_MARK = set("şŞğĞıİ")   # en Türkçe-ayırt-edici harfler (Paddle bunları kaybeder)

def tr_count(lines):
    return sum(1 for t in lines if any(c in TR_MARK for c in t))

# ── OneOCR oku ─────────────────────────────────────────────────────────────
_eng = None
def get_oneocr():
    global _eng
    if _eng is None:
        print("  [OneOCR] başlatılıyor...", flush=True); _eng = oneocr.OcrEngine(); print("  [OneOCR] hazır", flush=True)
    return _eng

def read_oneocr(img):
    eng = get_oneocr(); H = img.shape[0]; seen = {}; step = OCR_TILE - OCR_OV; y = 0
    while y < H:
        tile = img[y:min(y+OCR_TILE, H), :]
        if tile.shape[0] < 50: break
        try:
            res = eng.recognize_cv2(np.ascontiguousarray(tile))
        except Exception as e:
            print("    [oneocr tile]", str(e)[:60]); y += step; continue
        for ln in (res.get("lines") or []):
            t = (ln.get("text") or "").strip()
            if not t: continue
            br = ln.get("bounding_rect") or {}; yt = int(br.get("y1", 0) or 0) + y
            fk = fold(t)
            if fk and fk not in seen: seen[fk] = (t, yt)
        y += step
    return [t for t, _ in sorted(seen.values(), key=lambda x: x[1])]

# ── Paddle oku (cr.ocr_master'ı yeniden kullan, sadece text döndür) ─────────
def read_paddle(master_path):
    lines = cr.ocr_master(master_path)   # [(text, conf, y)]
    return [t for t, c, y in lines]

# ── qwen oku ───────────────────────────────────────────────────────────────
def read_qwen(img):
    H = img.shape[0]; seen = {}; order = []; step = QWEN_TILE - QWEN_OV; y = 0; bi = 0
    while y < H:
        tile = img[y:min(y+QWEN_TILE, H), :]; bi += 1
        if tile.shape[0] < 20: break
        ok, buf = cv2.imencode(".png", tile)
        if not ok: y += step; continue
        b64 = base64.b64encode(buf.tobytes()).decode()
        pl = {"model": MODEL, "prompt": QWEN_PROMPT, "stream": False, "format": "json",
              "keep_alive": "15m", "options": {"temperature": 0}, "images": [b64]}
        try:
            req = urllib.request.Request(OLLAMA, json.dumps(pl).encode(), {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=QWEN_TIMEOUT) as r: raw = json.loads(r.read())
            resp = raw.get("response", "{}"); resp = json.loads(resp) if isinstance(resp, str) else resp
            for ln in (resp.get("lines") or []):
                if not isinstance(ln, str): continue
                t = ln.strip()
                if not t: continue
                fk = fold(t)
                if fk and fk not in seen: seen[fk] = t; order.append(t)
        except Exception as e:
            print(f"    [qwen blok {bi}]", str(e)[:60])
        y += step
    return order

# ── KB desteği: her okuyucu satırlarına kb-exact (≥2 token) ─────────────────
def kb_support(lines, con):
    """Döndürür: (kb_lines, stats). stats: changed/confirmed/raw + örnek değişiklikler."""
    folds = list({fold(t) for t in lines})
    kb_map = cr.kb_exact_batch(con, folds)  # fold -> kb_name
    out = []; changed = 0; confirmed = 0; raw = 0; examples = []
    for t in lines:
        fk = fold(t)
        ntok = sum(1 for w in t.split() if any(c.isalpha() for c in w))
        if fk in kb_map and ntok >= 2:
            kbn = kb_map[fk]
            if kbn != t:
                changed += 1
                if len(examples) < 8: examples.append(f"{t}  ->  {kbn}")
                out.append(kbn)
            else:
                confirmed += 1; out.append(t)
        else:
            raw += 1; out.append(t)
    return out, {"changed": changed, "confirmed": confirmed, "raw": raw, "examples": examples}

# ── tek master işle (3 okuyucu + KB) ───────────────────────────────────────
def process_master(label, seg, master_path, con):
    img = fp.rd(str(master_path)); H, W = img.shape[:2]
    rec = {"label": label, "seg": seg, "master": str(master_path), "h": H, "w": W}

    # OneOCR
    t0 = time.time(); one = read_oneocr(img); rec["oneocr_t"] = round(time.time()-t0, 2); rec["oneocr_n"] = len(one)
    # Paddle
    t0 = time.time(); pad = read_paddle(master_path); rec["paddle_t"] = round(time.time()-t0, 2); rec["paddle_n"] = len(pad)
    # qwen
    if SKIP_QWEN:
        qwn = []; rec["qwen_t"] = None; rec["qwen_n"] = None
    else:
        t0 = time.time(); qwn = read_qwen(img); rec["qwen_t"] = round(time.time()-t0, 2); rec["qwen_n"] = len(qwn)

    # diakritik fidelity proxy (şğıİ içeren satır sayısı)
    rec["oneocr_tr"] = tr_count(one); rec["paddle_tr"] = tr_count(pad); rec["qwen_tr"] = tr_count(qwn)

    # KB desteği (her okuyucu ayrı)
    one_kb, one_st = kb_support(one, con)
    pad_kb, pad_st = kb_support(pad, con)
    qwn_kb, qwn_st = kb_support(qwn, con) if qwn else ([], {"changed":0,"confirmed":0,"raw":0,"examples":[]})
    rec["kb"] = {"oneocr": one_st, "paddle": pad_st, "qwen": qwn_st}

    # pairwise overlap (fold)
    fo, fp_, fq = {fold(x) for x in one}, {fold(x) for x in pad}, {fold(x) for x in qwn}
    rec["overlap"] = {
        "oneocr_paddle": len(fo & fp_), "oneocr_qwen": len(fo & fq), "paddle_qwen": len(fp_ & fq),
        "all3": len(fo & fp_ & fq),
        "oneocr_only": len(fo - fp_ - fq), "paddle_only": len(fp_ - fo - fq), "qwen_only": len(fq - fo - fp_),
    }

    # dosyalar
    od = OUT / label / seg; od.mkdir(parents=True, exist_ok=True)
    (od / "oneocr.txt").write_text("\n".join(one), encoding="utf-8")
    (od / "paddle.txt").write_text("\n".join(pad), encoding="utf-8")
    (od / "qwen.txt").write_text("\n".join(qwn), encoding="utf-8")
    (od / "oneocr_kb.txt").write_text("\n".join(one_kb), encoding="utf-8")
    (od / "paddle_kb.txt").write_text("\n".join(pad_kb), encoding="utf-8")
    (od / "compare.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    return rec

def find_dir(substr):
    for d in sorted(TESTER_IN.iterdir()):
        if substr in d.name: return d
    return None

def main():
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--no-qwen", action="store_true"); ap.add_argument("--only")
    a = ap.parse_args()
    global SKIP_QWEN; SKIP_QWEN = a.no_qwen
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(DB, read_only=True)
    cr.get_paddle()  # warmup
    print(f"=== 3-WAY test başladı (qwen={'KAPALI' if SKIP_QWEN else 'AÇIK'}) ===", flush=True)

    films = FILMS if not a.only else [f for f in FILMS if a.only.upper() in f[0]]
    all_recs = []
    for label, substr in films:
        d = find_dir(substr)
        if d is None:
            print(f"[{label}] dizin YOK ({substr})", flush=True); continue
        for seg in ("giris", "cikis"):
            mp = d / seg / "master.png"
            if not mp.exists(): continue
            print(f"\n[{label}/{seg}] -> {d.name}", flush=True)
            try:
                rec = process_master(label, seg, mp, con)
                all_recs.append(rec)
                q = rec.get('qwen_n'); qt = rec.get('qwen_t')
                print(f"  satır: OneOCR={rec['oneocr_n']} ({rec['oneocr_t']}s)  Paddle={rec['paddle_n']} ({rec['paddle_t']}s)  qwen={q} ({qt}s)", flush=True)
                print(f"  TR-diakritik satır: OneOCR={rec['oneocr_tr']}  Paddle={rec['paddle_tr']}  qwen={rec['qwen_tr']}", flush=True)
                print(f"  KB-değişti: OneOCR={rec['kb']['oneocr']['changed']}  Paddle={rec['kb']['paddle']['changed']}  qwen={rec['kb']['qwen']['changed']}", flush=True)
            except Exception as e:
                import traceback; print(f"  HATA: {e}", flush=True); traceback.print_exc()
                all_recs.append({"label": label, "seg": seg, "error": str(e)})

    # ── özet ────────────────────────────────────────────────────────────────
    ok = [r for r in all_recs if "error" not in r]
    def S(k): return sum(r.get(k, 0) or 0 for r in ok)
    tot = {
        "masters": len(ok),
        "oneocr_lines": S("oneocr_n"), "paddle_lines": S("paddle_n"), "qwen_lines": S("qwen_n"),
        "oneocr_tr": S("oneocr_tr"), "paddle_tr": S("paddle_tr"), "qwen_tr": S("qwen_tr"),
        "oneocr_t": round(S("oneocr_t"),1), "paddle_t": round(S("paddle_t"),1), "qwen_t": round(S("qwen_t"),1),
        "kb_changed_oneocr": sum(r.get("kb",{}).get("oneocr",{}).get("changed",0) for r in ok),
        "kb_changed_paddle": sum(r.get("kb",{}).get("paddle",{}).get("changed",0) for r in ok),
        "kb_changed_qwen":   sum(r.get("kb",{}).get("qwen",{}).get("changed",0) for r in ok),
    }
    (OUT / "_SUMMARY_3WAY.json").write_text(
        json.dumps({"totals": tot, "per_master": all_recs}, ensure_ascii=False, indent=2), encoding="utf-8")

    # okunabilir tablo
    L = []
    L.append("=== 3-WAY OKUYUCU TESTİ — özet ===")
    L.append(f"İşlenen master: {tot['masters']}")
    L.append("")
    L.append(f"{'':22} {'OneOCR':>10} {'Paddle':>10} {'qwen':>10}")
    L.append(f"{'toplam satır':22} {tot['oneocr_lines']:>10} {tot['paddle_lines']:>10} {tot['qwen_lines']:>10}")
    L.append(f"{'TR-diakritik satır':22} {tot['oneocr_tr']:>10} {tot['paddle_tr']:>10} {tot['qwen_tr']:>10}")
    L.append(f"{'toplam süre (s)':22} {tot['oneocr_t']:>10} {tot['paddle_t']:>10} {tot['qwen_t']:>10}")
    L.append(f"{'KB-düzeltti satır':22} {tot['kb_changed_oneocr']:>10} {tot['kb_changed_paddle']:>10} {tot['kb_changed_qwen']:>10}")
    L.append("")
    L.append(f"{'film/seg':30} {'1OCR':>5} {'Padl':>5} {'qwen':>5} | {'TR:1OCR':>7} {'Padl':>5} {'qwn':>4} | {'KB:1OCR':>7} {'Padl':>5}")
    for r in ok:
        kb = r.get("kb", {})
        L.append(f"{r['label']+'/'+r['seg']:30} {r['oneocr_n']:>5} {r['paddle_n']:>5} {str(r.get('qwen_n')):>5} | "
                 f"{r['oneocr_tr']:>7} {r['paddle_tr']:>5} {r['qwen_tr']:>4} | "
                 f"{kb.get('oneocr',{}).get('changed',0):>7} {kb.get('paddle',{}).get('changed',0):>5}")
    txt = "\n".join(L)
    (OUT / "_SUMMARY_3WAY.txt").write_text(txt, encoding="utf-8")
    print("\n" + txt, flush=True)
    print(f"\n_SUMMARY -> {OUT/'_SUMMARY_3WAY.json'}", flush=True)
    con.close()

if __name__ == "__main__":
    main()
