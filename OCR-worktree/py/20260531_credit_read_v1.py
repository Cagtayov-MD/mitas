"""20260531 — credit_read_v1 — Jenerik OKUMA pipeline v1.
Paddle → KB-yazim-düzelt → qwen çapraz-kontrol → transcript.txt + labels.json + _SUMMARY.json
"""
import sys, json, re, base64, difflib, csv, time, urllib.request, importlib.util
from pathlib import Path
import cv2, numpy as np, duckdb

sys.stdout.reconfigure(encoding="utf-8")

# ── fp modülünü import (rd / wr / META / WIN / safe / OLLAMA / MODEL) ──────
spec = importlib.util.spec_from_file_location(
    "fp", str(__import__("pathlib").Path(__import__("os").environ.get("MITAS_PROJECT_ROOT") or r"E:\MITAS") / "OCR-worktree" / "py" / "20260530_1744_full_pipeline.py")
)
fp = importlib.util.module_from_spec(spec)
sys.modules["fp"] = fp
spec.loader.exec_module(fp)

# ── sabitler ──────────────────────────────────────────────────────────────
DB         = r"X:\DIGER\Mitas_Files\MitaData\mitas.duckdb"
TR_DIR     = Path(r"X:\DIGER\Mitas_Files\MitaData\06_name_databases\turkish")
TESTER_IN  = Path(r"E:\MITAS\OCR-worktree\tester_fiso")
TESTER_OUT = Path(r"E:\MITAS\OCR-worktree\tester_read")
META       = fp.META
OLLAMA     = fp.OLLAMA
MODEL      = fp.MODEL

TILE_H     = 1500   # dikey tile yüksekliği px
OVERLAP    = 120    # tile overlap px
QWEN_SAMPLE= 5      # film başına max qwen bloğu sayısı
SKIP_QWEN  = False  # --no-qwen ile True (hızlı bulk koşu için)

# 15 film: (kısa-ad, idx)  — META'dan idx ile bul
FILM_LIST = [
    ("KULUBE",       1),
    ("KANSAS",      23),
    ("DRAKULA",      5),
    ("ANJELIK",     27),
    ("SON_METRO",   13),
    ("GUZEL_BIR_OLUM", 11),
    ("OLUM_ASANSORU", 25),
    ("X-MEN",       21),
    ("JURASSIC",    19),
    ("YALAZA",      48),
    ("DIRILIS",     49),
    ("BIZIM_EVIN",  51),
    ("BENI_BOYLE",  52),
    ("SENIN_HIKAYEN", 42),
    ("DUZINESI",    24),
]

# ── fold: küçük-harf + Türkçe → latin + kesme/tire çıkar ─────────────────
def fold(s):
    s = (s or "").lower()
    for a, b in [("ı","i"),("İ","i"),("i̇","i"),("ş","s"),("ğ","g"),("ç","c"),("ö","o"),("ü","u"),
                 ("'",""),("’",""),("-"," ")]:
        s = s.replace(a, b)
    return " ".join(s.split())

# SQL-fold builder (duckdb tarafı) ─────────────────────────────────────────
def FOLD_SQL(col):
    e = f"lower({col})"
    for a, b in [("ı","i"),("İ","i"),("ş","s"),("ğ","g"),("ç","c"),("ö","o"),("ü","u"),
                 ("i̇","i"),("'",""),("’",""),("-"," ")]:
        aa = a.replace("'","''"); bb = b.replace("'","''")
        e = f"replace({e},'{aa}','{bb}')"
    return e

# ── Türkçe-DB yükle (ad/soyad seti) ──────────────────────────────────────
def load_turkish_db():
    """
    CSV başlığı BOM'lu olabilir (﻿name). ascii_key kolonunu (büyük harf, ASCII)
    ve name kolonunu okur. Fold edilmiş token seti döner.
    """
    names = {}   # folded -> proper (diakritikli) yazim. SADECE diakritik-restore icin.
    for fn in ["turkish_given_names.csv","turkish_surnames.csv","turkish_names_master.csv"]:
        fpath = TR_DIR / fn
        if not fpath.exists():
            continue
        try:
            with open(fpath, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    val = (row.get("name","") or "").strip()
                    if val and any(c.isalpha() for c in val):
                        names.setdefault(fold(val), val)   # folded -> proper (ilk gorulen)
        except Exception as e:
            print(f"  [TR-DB UYARI] {fn}: {e}")
    print(f"  Türkçe-DB: {len(names)} isim (folded->proper)")
    return names

# edit distance ≤ 1 (Levenshtein, basit) ──────────────────────────────────
def edit1(a, b):
    if abs(len(a)-len(b)) > 1:
        return False
    if a == b:
        return True
    if len(a) > len(b):
        a, b = b, a
    # len(a) <= len(b)
    if len(b) - len(a) == 1:
        for i in range(len(b)):
            if a == b[:i] + b[i+1:]:
                return True
        return False
    # same length
    diffs = sum(1 for x,y in zip(a,b) if x!=y)
    return diffs <= 1

# ── KB exact-fold lookup (toplu) ──────────────────────────────────────────
def kb_exact_batch(con, tokens):
    """tokens: liste fold(isim). Döndürür: fold(isim) -> kb_name (düzeltilmiş yazım)"""
    if not tokens:
        return {}
    # SQL: fold(name)=? OR fold(ascii_name)=? için VALUES ile toplu sorgu
    placeholders = ",".join(["?"] * len(tokens))
    fn = FOLD_SQL("name")
    fa = FOLD_SQL("ascii_name")
    sql = f"""
        SELECT DISTINCT {fn} AS fn, name
        FROM main.mitas_people_index
        WHERE {fn} IN ({placeholders})
           OR {fa} IN ({placeholders})
        LIMIT {len(tokens)*10}
    """
    params = list(tokens) + list(tokens)
    result = {}
    try:
        rows = con.execute(sql, params).fetchall()
        for fn_val, name_val in rows:
            result[fn_val] = name_val
    except Exception as e:
        print(f"  [KB-EXACT ERR] {e}")
    return result

# ── PaddleOCR init (bir kez) ──────────────────────────────────────────────
_paddle = None
def get_paddle():
    global _paddle
    if _paddle is None:
        from paddleocr import PaddleOCR
        print("  [Paddle] Başlatılıyor (lang=tr)...", flush=True)
        # lang='tr': ş/ğ/ı/İ TANIR (en bunları ASCII'ye ezer). Tespit aynı (kutu sayısı=en),
        # sadece tanıma Türkçeleşir -> sıfır tespit-gerilemesi, diakritik kazancı. KANITLI (lang_test).
        _paddle = PaddleOCR(lang="tr", use_textline_orientation=False)
        print("  [Paddle] Hazır (tr)", flush=True)
    return _paddle

# ── master'ı tile'la + OCR ────────────────────────────────────────────────
def ocr_master(img_path):
    """Döndürür: [(text, conf, y_top)] listesi — fold-dedup ile.
    PaddleOCR 3.x: paddle.predict(tile) -> list[OCRResult]
    OCRResult: dict-like, anahtarlar: rec_texts, rec_scores, rec_polys
    """
    img = cv2.imdecode(np.fromfile(str(img_path), np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return []
    H, W = img.shape[:2]
    paddle = get_paddle()
    seen_fold = {}       # fold(text) -> (text, conf, y)
    step = TILE_H - OVERLAP
    y = 0
    while y < H:
        tile = img[y:min(y+TILE_H, H), :]
        try:
            results = paddle.predict(tile)
        except Exception as e:
            print(f"    [Paddle tile y={y}] hata: {e}")
            y += step
            continue
        if not results:
            y += step
            continue
        for item in results:
            # PaddleOCR 3.x: OCRResult -> .json (bazen 'res' altinda). KANITLI erisim deseni.
            d = item if isinstance(item, dict) else (getattr(item, "json", {}) or {})
            res = d.get("res", d) if isinstance(d, dict) else {}
            if not isinstance(res, dict): res = {}
            texts  = res.get("rec_texts")  or d.get("rec_texts")  or []
            scores = res.get("rec_scores") or d.get("rec_scores") or []
            polys  = res.get("rec_polys")  or d.get("rec_polys")  or []
            for i, text in enumerate(texts):
                text = (text or "").strip()
                if not text or len(text) < 2:
                    continue
                conf = float(scores[i]) if i < len(scores) else 0.5
                # y_top: poly'nin en üst koordinatı + tile offset
                if i < len(polys) and polys[i] is not None:
                    try:
                        poly = polys[i]
                        # poly: array shape (N,2) ya da liste
                        if hasattr(poly, '__len__'):
                            ys = [pt[1] for pt in poly]
                        else:
                            ys = [0]
                        y_top = int(min(ys)) + y
                    except Exception:
                        y_top = y
                else:
                    y_top = y
                fk = fold(text)
                if fk not in seen_fold:
                    seen_fold[fk] = (text, conf, y_top)
                elif conf > seen_fold[fk][1]:
                    # daha yüksek confidence, y koordinatını koru (ilk görülen)
                    seen_fold[fk] = (text, conf, seen_fold[fk][2])
        y += step

    # y koordinatına göre sırala
    lines = sorted(seen_fold.values(), key=lambda t: t[2])
    return [(text, conf, y_top) for text, conf, y_top in lines]

# ── qwen çapraz-kontrol (örneklem) ────────────────────────────────────────
QWEN_PROMPT = (
    "You are an OCR verifier for film credit images.\n"
    "Transcribe EXACTLY what you see. Use '?' for unreadable parts.\n"
    "NO guessing, NO adding names not visible. Preserve Turkish: ç ğ ı İ ö ş ü.\n"
    'Return JSON: {"lines": ["line1", "line2"]}'
)
QWEN_BLOCK_H = 600   # her qwen tile'ının yüksekliği (px) — küçük tutarak timeout önle
QWEN_TIMEOUT = 90    # saniye

def qwen_crosscheck(img_path, paddle_lines):
    """Paddle satırlarını qwen ile örneklem karşılaştırması.
    Döndürür: (agree_list, halluc_suspect_list).
    """
    img = cv2.imdecode(np.fromfile(str(img_path), np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return [], []
    H = img.shape[0]
    agree_all = []
    halluc_all = []

    # QWEN_SAMPLE kadar blok: eşit aralıklı (0, H/5, 2H/5, ...) başlangıçlı
    n_blocks = min(QWEN_SAMPLE, max(1, H // QWEN_BLOCK_H))
    step = H // max(n_blocks, 1)

    for bi in range(n_blocks):
        y0 = bi * step
        y1 = min(y0 + QWEN_BLOCK_H, H)
        tile = img[y0:y1, :]
        if tile.shape[0] < 20:
            continue
        ok, buf = cv2.imencode(".png", tile)
        if not ok:
            continue
        b64 = base64.b64encode(buf.tobytes()).decode()

        # bu y aralığına düşen paddle satırları
        block_paddle = [t for t, c, y in paddle_lines if y0 <= y < y1]

        try:
            payload = {
                "model": MODEL,
                "prompt": QWEN_PROMPT,
                "stream": False,
                "format": "json",
                "keep_alive": "15m",
                "options": {"temperature": 0},
                "images": [b64]
            }
            req = urllib.request.Request(
                OLLAMA, json.dumps(payload).encode(),
                {"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=QWEN_TIMEOUT) as r:
                resp_raw = json.loads(r.read())
            resp_str = resp_raw.get("response", "{}")
            resp = json.loads(resp_str) if isinstance(resp_str, str) else resp_str
            qwen_lines = resp.get("lines", [])
            if not isinstance(qwen_lines, list):
                qwen_lines = []
        except Exception as e:
            print(f"    [qwen block {bi}] hata: {e}")
            continue

        # karşılaştır
        qfolds = {fold(q) for q in qwen_lines if isinstance(q, str) and q.strip()}
        pfolds = {fold(p) for p in block_paddle if p.strip()}
        agree = list(qfolds & pfolds)
        # qwen'de var ama paddle'da yok: halüsinasyon şüphesi (paddle'a güven)
        halluc = [q for q in qwen_lines
                  if isinstance(q, str) and fold(q) not in pfolds and len(q.strip()) > 3]
        agree_all.extend(agree)
        halluc_all.extend(halluc)

    return agree_all, halluc_all

# ── KB-yazım düzeltme (toplu, 3 katman) ──────────────────────────────────
def correct_names(raw_lines, con, tr_names):
    """
    raw_lines: [(text, conf, y)] listesi
    Döndürür: [(corrected, method, changed)] listesi (aynı sırada)
    method: 'kb-exact' | 'tr-token' | 'raw'
    """
    # distinct name-token'ları topla (rol/başlık satırları dahil, KB'ye sorsak da zarar vermez)
    fold2raw = {}  # fold(text) -> text
    for text, conf, y in raw_lines:
        fold2raw[fold(text)] = text

    distinct_folds = list(fold2raw.keys())

    # (a) KB exact-fold toplu sorgu
    kb_map = kb_exact_batch(con, distinct_folds)  # fold -> kb_name

    results = []
    for text, conf, y in raw_lines:
        fk = fold(text)
        # (a) KB exact — SADECE ≥2 token (tam-isim "Ad Soyad" deseni).
        #     Kısa tek-token fragmanlar (OR/ER/ARTA/HOME) 13M'de tesadüfen eşleşir -> ele.
        ntok = sum(1 for t in text.split() if any(c.isalpha() for c in t))
        if fk in kb_map and ntok >= 2:
            corrected = kb_map[fk]
            results.append((corrected, "kb-exact", corrected != text))
            continue

        # (b) tr-token DEVRE DIŞI: Türkçe-DB folded->proper diakritik-restore AMBİGÜ
        #     (Ebru/Ebrü, Tolgahan/Tolğahan -> yanlış variant; ÖzAk->Ozak doğruyu bozar).
        #     Fidelity kuralı: emin değilsen OCR'ı KORU. Sadece kb-exact (tam-isim, kesin kişi) güvenli.
        results.append((text, "raw", False))

    return results

# ── tek (film, seg) işle ─────────────────────────────────────────────────
def process_seg(film_key, seg, master_path, out_dir, con, tr_names):
    print(f"  [{film_key}/{seg}] OCR başlıyor: {master_path}", flush=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. PaddleOCR ile oku
    raw_lines = ocr_master(master_path)
    print(f"    Paddle: {len(raw_lines)} satır", flush=True)

    # 2. KB-yazım düzeltme
    corrections = correct_names(raw_lines, con, tr_names)

    # 3. qwen çapraz-kontrol (örneklem) — --no-qwen ile atlanır (hız)
    if SKIP_QWEN:
        agree, halluc_suspect = [], []
    else:
        agree, halluc_suspect = qwen_crosscheck(master_path, raw_lines)
        print(f"    qwen: agree={len(agree)}, halüsinasyon-şüphe={len(halluc_suspect)}", flush=True)

    # 4. Çıktı dosyaları
    # transcript.txt — düzeltilmiş satırlar
    transcript_lines = []
    for i, (raw_t, conf, y_top) in enumerate(raw_lines):
        corrected, method, changed = corrections[i]
        transcript_lines.append(corrected)
    transcript_path = out_dir / "transcript.txt"
    transcript_path.write_text("\n".join(transcript_lines), encoding="utf-8")

    # labels.json
    labels = []
    for i, (raw_t, conf, y_top) in enumerate(raw_lines):
        corrected, method, changed = corrections[i]
        labels.append({
            "raw": raw_t,
            "corrected": corrected,
            "method": method,
            "changed": changed,
            "conf": round(conf, 3),
            "y": y_top
        })
    (out_dir / "labels.json").write_text(
        json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "film": film_key,
        "seg": seg,
        "total_lines": len(raw_lines),
        "kb_exact": sum(1 for _,m,_ in corrections if m=="kb-exact"),
        "tr_token": sum(1 for _,m,_ in corrections if m=="tr-token"),
        "raw_kept": sum(1 for _,m,_ in corrections if m=="raw"),
        "qwen_agree": len(agree),
        "qwen_halluc_suspect": len(halluc_suspect),
        "halluc_examples": halluc_suspect[:5],
        "transcript_path": str(transcript_path),
        "label_examples": labels[:6]
    }

# ── meta'dan film dizin adını bul ────────────────────────────────────────
def find_film_dir(film_key, meta_path):
    """META'dan ilgili film stem'ini çıkar, tester_fiso'da karşılığını döndür."""
    meta = json.loads(Path(meta_path).read_text(encoding="utf-8"))

    def fold_dir(s):
        s2 = s.upper()
        for a, b in [("İ","I"),("Ğ","G"),("Ş","S"),("Ç","C"),("Ö","O"),("Ü","U"),
                     ("I","I"),("'",""),("'","")]:
            s2 = s2.replace(a,b)
        return re.sub(r"[^A-Z0-9]","", s2)

    fk_fold = fold_dir(film_key)

    # META'dan idx -> stem
    for it in meta:
        stem = Path(it["path"]).stem
        if fk_fold in fold_dir(stem):
            # tester_fiso'da bul
            for d in TESTER_IN.iterdir():
                if fold_dir(d.name) == fold_dir(stem):
                    return d
            # stem bulunamadı ama META eşleşti, JURASSIC gibi kısaltma durumunda
            for d in TESTER_IN.iterdir():
                if fk_fold in fold_dir(d.name):
                    return d
    # son çare: doğrudan tester_fiso'da fk_fold ara
    for d in TESTER_IN.iterdir():
        if fk_fold in fold_dir(d.name):
            return d
    return None

# ── ANA AKIŞ ─────────────────────────────────────────────────────────────
def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="sadece bu filmi çalıştır, örn. DIRILIS")
    ap.add_argument("--seg", choices=["giris","cikis"], help="sadece bu segment")
    ap.add_argument("--no-qwen", action="store_true", help="qwen çapraz-kontrolü atla (hızlı)")
    a = ap.parse_args()
    global SKIP_QWEN
    SKIP_QWEN = a.no_qwen

    TESTER_OUT.mkdir(parents=True, exist_ok=True)
    print("=== credit_read_v1 başladı ===", flush=True)

    # DB bağlan
    con = duckdb.connect(DB, read_only=True)
    print(f"DB bağlandı: {DB}", flush=True)

    # Türkçe-DB
    tr_names = load_turkish_db()

    # Paddle warmup (bir kez init)
    _ = get_paddle()

    # META yükle
    meta = json.loads(Path(META).read_text(encoding="utf-8"))
    idx2stem = {it.get("idx"): Path(it["path"]).stem for it in meta}

    summary_all = []

    film_list = FILM_LIST
    if a.only:
        fk_upper = a.only.upper()
        film_list = [(k,i) for k,i in FILM_LIST if k == fk_upper or fk_upper in k]
        if not film_list:
            print(f"[UYARI] --only={a.only} hiçbir filme eşleşmedi, hepsi çalıştırılıyor")
            film_list = FILM_LIST

    for film_key, idx in film_list:
        film_dir = find_film_dir(film_key, META)
        if film_dir is None:
            print(f"[{film_key}] tester_fiso'da dizin bulunamadı, atlanıyor", flush=True)
            continue

        segs = ["giris","cikis"] if not a.seg else [a.seg]
        for seg in segs:
            master_path = film_dir / seg / "master.png"
            if not master_path.exists():
                print(f"  [{film_key}/{seg}] master.png YOK, atlanıyor", flush=True)
                continue
            out_dir = TESTER_OUT / film_key / seg
            try:
                result = process_seg(film_key, seg, master_path, out_dir, con, tr_names)
                summary_all.append(result)
                print(f"  [{film_key}/{seg}] TAMAM: {result['total_lines']} satır", flush=True)
            except Exception as e:
                import traceback
                print(f"  [{film_key}/{seg}] HATA: {e}", flush=True)
                traceback.print_exc()
                summary_all.append({"film": film_key, "seg": seg, "error": str(e)})

    # _SUMMARY.json
    total_lines = sum(r.get("total_lines",0) for r in summary_all)
    total_kb_exact = sum(r.get("kb_exact",0) for r in summary_all)
    total_tr_token = sum(r.get("tr_token",0) for r in summary_all)
    total_raw = sum(r.get("raw_kept",0) for r in summary_all)
    total_agree = sum(r.get("qwen_agree",0) for r in summary_all)
    total_halluc = sum(r.get("qwen_halluc_suspect",0) for r in summary_all)

    def pct(n, d): return f"{n/max(d,1)*100:.1f}%"

    summary = {
        "total_films_processed": len(summary_all),
        "total_lines": total_lines,
        "kb_exact": total_kb_exact, "kb_exact_pct": pct(total_kb_exact, total_lines),
        "tr_token": total_tr_token, "tr_token_pct": pct(total_tr_token, total_lines),
        "raw_kept": total_raw, "raw_pct": pct(total_raw, total_lines),
        "qwen_agree": total_agree,
        "qwen_halluc_suspect": total_halluc,
        "per_film": summary_all
    }
    summary_path = TESTER_OUT / "_SUMMARY.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== TAMAMLANDI ===")
    print(f"Toplam satır: {total_lines}")
    print(f"kb-exact: {total_kb_exact} ({pct(total_kb_exact, total_lines)})")
    print(f"tr-token: {total_tr_token} ({pct(total_tr_token, total_lines)})")
    print(f"raw:      {total_raw} ({pct(total_raw, total_lines)})")
    print(f"qwen-agree: {total_agree} | halüsinasyon-şüphe: {total_halluc}")
    print(f"_SUMMARY -> {summary_path}")
    con.close()

if __name__ == "__main__":
    main()
