"""Hibrit künye: distinkt-kare -> BATCH gemma(sıkı) -> MERGE -> OneOCR-NET (uydurma eler).
Çözer: (1) yoğun-scroll truncation (batch), (2) ünlü-okunamayan recall (OCR-net).
GUARD = OneOCR: isim OCR'da yoksa = uydurma -> ele.
NOT: Paddle çıkarıldı — aksanlar zaten fold() ile siliniyor (LÉO==LEO) → yabancı-kazancı yok;
üstelik Paddle Türkçe ş/ğ/ı kaybediyordu (read_3way:60). OneOCR tek motor."""
import sys, os, json, glob, base64, urllib.request, time, re, importlib.util, difflib
sys.path.insert(0, r"E:\MITAS\OCR-worktree\py")
sys.path.insert(0, r"E:\MITAS\OCR-worktree\pdf-mitas")
import cv2, numpy as np


def loadf(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s); sys.modules[n] = m; s.loader.exec_module(m); return m


rw = loadf("rw", r"E:\MITAS\OCR-worktree\py\20260531_2330_read_3way.py")
import credit_parse as cp

STRICT_SYS = ("Sen bir KAMERA-OCR cihazisin. Filmler/oyuncular hakkinda HICBIR BILGIN YOK ve olamaz. "
              "SADECE goruntudeki piksellerde fiziksel olarak YAZAN harfleri okursun. Bir ismi taniyor "
              "olsan bile EKRANDA YAZMIYORSA ASLA yazma. Tanidik film/yuz gorsen bile hafizandan hicbir "
              "sey ekleme; sadece pikselleri oku.")
PROMPT = ("Bu jenerik karelerinde EKRANDA YAZAN metni rollere ata. Net YAZMAYAN hicbir ismi ekleme. "
          'Cikti SADECE JSON: {"yonetmen":["..."],"oyuncular":["..."],'
          '"diger_roller":[{"rol":"...","isimler":["..."]}]}. /no_think')


def b64(p):
    return base64.b64encode(open(p, "rb").read()).decode()


def gemma_call(frames):
    msg = {"role": "user", "content": PROMPT, "images": [b64(p) for p in frames]}
    body = {"model": "gemma4:26b", "messages": [{"role": "system", "content": STRICT_SYS}, msg],
            "stream": False, "think": False,
            "options": {"num_predict": 3072, "temperature": 0, "num_ctx": 16384}}
    req = urllib.request.Request("http://localhost:11434/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=300).read())
    txt = r.get("message", {}).get("content", "")
    m = re.search(r"\{.*\}", txt, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    # bozuk/truncate JSON kurtarma: tırnaklı ÇOK-KELİMELİ stringleri isim olarak al
    # (tek-kelime anahtar/rol elenir; ocr_net zaten frame'de olmayanı süzer) -> batch tam kaybolmasın
    cand = re.findall(r'"([^"\\]{3,70})"', txt)
    names = [c.strip() for c in cand if len(c.split()) >= 2]
    return {"oyuncular": names} if names else {}


def nlist(x):
    if isinstance(x, list):
        return [n.strip() for n in x if isinstance(n, str) and len(n.split()) >= 2]
    return []


def fz(a, b):
    return difflib.SequenceMatcher(None, cp.fold(a), cp.fold(b)).ratio()


def dedup(names):
    out = []
    for n in names:
        if not any(fz(n, o) >= 0.85 for o in out):
            out.append(n)
    return out


def _names_any(v):
    """Anahtar-bağımsız isim toplayıcı: liste/dict/string ne olursa olsun çok-kelimeli isimleri çıkarır.
    gemma 'isimlar' typo'su / placeholder rol / beklenmedik yuva → okunan isim KAYBOLMASIN."""
    out = []
    if isinstance(v, str):
        out.append(v)
    elif isinstance(v, list):
        for it in v:
            out += _names_any(it)
    elif isinstance(v, dict):
        for k, vv in v.items():
            if str(k).strip().lower() in ("rol", "role", "rolü", "rolu"):
                continue
            out += _names_any(vv)
    return [n.strip() for n in out if isinstance(n, str) and len(n.split()) >= 2]


def merge(results):
    yon, cast, roles = [], [], {}
    for r in results:
        if not isinstance(r, dict):
            continue
        for k in ("yonetmen", "yönetmen", "director", "directors", "yonetmenler"):
            if k in r:
                yon += _names_any(r[k])
        for k in ("oyuncular", "oyuncu", "cast", "actors", "oyunculari"):
            if k in r:
                cast += _names_any(r[k])
        dr = r.get("diger_roller") or r.get("diğer_roller") or r.get("roller") or []
        if isinstance(dr, list):
            for rr in dr:
                if isinstance(rr, dict):
                    rol = rr.get("rol") or rr.get("role") or "?"
                    nms = []
                    for kk, vv in rr.items():
                        if str(kk).strip().lower() in ("rol", "role", "rolü", "rolu"):
                            continue
                        nms += _names_any(vv)
                    if nms:
                        roles.setdefault(str(rol), []).extend(nms)
    return {"yonetmen": dedup(yon), "oyuncular": dedup(cast),
            "diger_roller": [{"rol": k, "isimler": dedup(v)} for k, v in roles.items() if v]}


def ocr_lines(frames):
    """OneOCR ile kareleri oku (guard kaynağı)."""
    raw = []
    for f in frames:
        img = cv2.imdecode(np.fromfile(f, np.uint8), 1)
        if img is None:
            continue
        try:
            for ln in rw.read_oneocr(img):
                t = ln if isinstance(ln, str) else (ln[0] if ln else "")
                if t and t.strip():
                    raw.append(t.strip())
        except Exception:
            pass
    return raw


def in_ocr(name, lines, alltok):
    fn = cp.fold(name)
    if not fn:
        return False
    for L in lines:
        fl = cp.fold(L)
        if fn in fl or fz(name, L) >= 0.72:
            return True
    toks = [t for t in fn.split() if len(t) >= 2]
    return bool(toks) and all(t in alltok for t in toks)   # TUM token'lar OCR'da olmali (sert)


def ocr_net(struct, lines):
    alltok = set(" ".join(cp.fold(L) for L in lines).split())
    dropped = []

    def filt(names):
        keep = []
        for n in names:
            (keep if in_ocr(n, lines, alltok) else dropped).append(n)
        return keep
    struct["yonetmen"] = filt(struct["yonetmen"])
    struct["oyuncular"] = filt(struct["oyuncular"])
    for rr in struct["diger_roller"]:
        rr["isimler"] = filt(rr["isimler"])
    struct["diger_roller"] = [rr for rr in struct["diger_roller"] if rr["isimler"]]
    return struct, dropped


def run_film(film, nframes=18, bs=6):
    fd = glob.glob(rf"C:\Users\TRT03\Desktop\test\frame- {film}*")[0]
    frames = sorted(glob.glob(fd + r"\*.png")); n = len(frames)
    sel = [frames[int(n * f)] for f in [(i + 1) / (nframes + 1) for i in range(nframes)]]
    batches = [sel[i:i + bs] for i in range(0, len(sel), bs)]
    t = time.time()
    results = [gemma_call(b) for b in batches]
    merged = merge(results)
    ol = ocr_lines(sel)
    final, dropped = ocr_net(json.loads(json.dumps(merged)), ol)

    def cnt(s):
        return len(s["yonetmen"]) + len(s["oyuncular"]) + sum(len(r["isimler"]) for r in s["diger_roller"])
    print(f"=== {film} ({len(batches)} batch, {time.time()-t:.0f}s) ===")
    print(f"MERGE (ham gemma): {cnt(merged)} isim | OCR-NET sonrasi: {cnt(final)} isim | ELENEN: {len(dropped)}")
    if dropped:
        print(f"ELENEN (OCR'da yok = uydurma): {dropped[:12]}")
    print("FINAL yonetmen:", final["yonetmen"])
    print("FINAL oyuncular:", final["oyuncular"][:8])
    print("FINAL roller:", [(r["rol"], r["isimler"][:3]) for r in final["diger_roller"][:8]])
    return final, dropped, merged


if __name__ == "__main__":
    for f in sys.argv[1:]:
        try:
            run_film(f)
        except Exception as e:
            import traceback
            print(f"{f} HATA: {repr(e)[:120]}"); traceback.print_exc()
        print()
