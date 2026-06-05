"""ÇİFT-MOTOR CONSENSUS DENEYİ — GLM-OCR (VLM) master'ı okur; OneOCR-tabanlı stitch künyemizle uzlaştırır.
İkisi AYNI okursa = güvenilir (cross-engine). GLM-only = GLM'in yakaladığı/düzelttiği. our-only = stitch'te var GLM'de yok.
Salt-okuma. cv2 + Ollama (glm-ocr:latest). Kullanım: python 20260601_consensus_glm.py <alt-dize ...>
"""
import sys, json, base64, urllib.request, re, difflib, unicodedata
from pathlib import Path
import numpy as np, cv2
sys.stdout.reconfigure(encoding="utf-8")

OLLAMA = "http://localhost:11434/api/generate"
GLM = "glm-ocr:latest"
MAST = Path(r"E:\MITAS\OCR-worktree\clip_pipeline100\_MASTERS")
KUN = Path(r"E:\MITAS\OCR-worktree\clip_pipeline100\_KUNYE")
PROMPT = ("Transcribe the film-credit text in this image EXACTLY, top to bottom, one entry per line. "
          "Use '?' for unreadable characters. Do NOT guess, do NOT add names not visible. "
          "Preserve Turkish letters: ç ğ ı İ ö ş ü. Return JSON: {\"lines\":[\"...\",\"...\"]}")

def fold(s): return ''.join(c for c in unicodedata.normalize('NFKD', (s or '').lower()) if not unicodedata.combining(c)).strip()
def imread_u(p): return cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)

def extract_lines(text):
    if not text: return []
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I).strip()
    m = re.search(r"\{.*\"lines\".*\}", text, flags=re.S)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj.get("lines"), list):
                return [str(x).strip() for x in obj["lines"] if str(x).strip()]
        except Exception: pass
    out = []
    for ln in text.splitlines():
        t = ln.strip().strip("`").strip("-*•").strip()
        if not t or t in ("{", "}", "[", "]") or t.lower().startswith(("here", "sure", "```", "json")): continue
        if t.startswith('"') and t.endswith('",'): t = t[1:-2]
        out.append(t)
    return out

def glm_read(img, tile=1200, ov=100, timeout=300):
    H = img.shape[0]; seen = {}; order = []; step = tile - ov; y = 0
    while y < H:
        t = img[y:min(y+tile, H), :]
        if t.shape[0] < 20: break
        ok, buf = cv2.imencode(".png", t)
        if ok:
            b64 = base64.b64encode(buf.tobytes()).decode()
            pl = {"model": GLM, "prompt": PROMPT, "stream": False, "think": False,
                  "keep_alive": "10m", "options": {"temperature": 0}, "images": [b64]}
            try:
                req = urllib.request.Request(OLLAMA, json.dumps(pl).encode(), {"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=timeout) as r: raw = json.loads(r.read())
                for ln in extract_lines(raw.get("response", "")):
                    fk = fold(ln)
                    if fk and fk not in seen: seen[fk] = ln; order.append(ln)
            except Exception as e: print("   [glm]", str(e)[:70], flush=True)
        y += step
    return order

def fuzzy_in(f, fset_list):
    return any(difflib.SequenceMatcher(None, f, g).ratio() >= 0.85 for g in fset_list)

def run(stem):
    mp = MAST/f"{stem}.png"; kp = KUN/f"{stem}.txt"
    if not mp.exists(): print(f"{stem}: master yok"); return
    our = [l.strip() for l in kp.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip() and not l.startswith("#")]
    print(f"\n===== {stem} =====  (GLM okuyor...)", flush=True)
    glm = glm_read(imread_u(mp))
    fg = [fold(x) for x in glm]; fgs = set(fg)
    fo = [fold(x) for x in our]; fos = set(fo)
    agree = [x for x in our if fold(x) in fgs or fuzzy_in(fold(x), fg)]
    glm_only = [x for x in glm if fold(x) not in fos and not fuzzy_in(fold(x), fo)]
    our_only = [x for x in our if x not in agree]
    print(f"  stitch(OneOCR)={len(our)}  GLM={len(glm)}  | UZLAŞAN={len(agree)} (stitch'in %{len(agree)*100//max(len(our),1)}'i GLM-teyitli)")
    print(f"  --- UZLAŞAN örnek (güvenilir) ---")
    for x in agree[:12]: print("    ✓", x)
    print(f"  --- GLM-only (GLM yakaladı/farklı okudu) [{len(glm_only)}] ---")
    for x in glm_only[:14]: print("    +", x)
    print(f"  --- stitch-only (GLM'de yok / farklı) [{len(our_only)}] ---")
    for x in our_only[:10]: print("    -", x)

if __name__ == "__main__":
    subs = [fold(a) for a in sys.argv[1:]]
    stems = sorted({p.stem for p in MAST.glob("*.png") if any(s in fold(p.stem) for s in subs)})
    for st in stems: run(st)
