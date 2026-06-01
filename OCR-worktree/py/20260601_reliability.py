"""GÜVENİLİRLİK RAPORU — her film/segment'i medconf + garble + son künye sayısına göre
GÜVENİLİR / GÖZDEN-GEÇİR / ZOR / BOŞ diye ayırır. Teslimat dürüstlüğü: hangi künyeye güvenilir?
Kaynak: cache (medconf için stitch) + _KUNYE/*.txt (son sayım). Salt-okuma. Çıktı: _RELIABILITY.md + .json
"""
import sys, json, importlib.util, unicodedata
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
def load(m, p):
    s = importlib.util.spec_from_file_location(m, p); mod = importlib.util.module_from_spec(s); sys.modules[m] = mod; s.loader.exec_module(mod); return mod
stx = load("stx", r"E:\MITAS\OCR-worktree\py\20260601_stitch.py")
CACHE = Path(r"E:\MITAS\OCR-worktree\clip_pipeline100\_CACHE")
KUN = Path(r"E:\MITAS\OCR-worktree\clip_pipeline100\_KUNYE")
OUT = Path(r"E:\MITAS\OCR-worktree\clip_pipeline100")
VOWELS = set("aeıioöuüâîû")
def gnorm(s): return ''.join(c for c in unicodedata.normalize('NFKD', s.lower()) if not unicodedata.combining(c))
def is_garble(t):
    nonsp = sum(not c.isspace() for c in t); letters = sum(c.isalpha() for c in t)
    if nonsp == 0: return True
    if letters/nonsp < 0.6: return True
    return any(len(gnorm(tk)) >= 4 and not any(c in VOWELS for c in gnorm(tk)) for tk in t.split())

rows = []
for cj in sorted(CACHE.glob("*.json")):
    stem = cj.stem
    try:
        c = json.loads(cj.read_text(encoding="utf-8")); idx = c["idx"]
    except Exception:
        rows.append({"film": stem, "n": 0, "low": 0, "medconf": 0.0, "gf": 0.0, "bucket": "BOZUK"}); continue
    kp = KUN/f"{stem}.txt"
    kn = len([l for l in kp.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip() and not l.startswith("#")]) if kp.exists() else 0
    if not idx:
        rows.append({"film": stem, "n": kn, "low": 0, "medconf": 1.0, "gf": 0.0, "bucket": "BOŞ"}); continue
    op = {int(k): v for k, v in c["ocr_pos"].items()}
    lines, low, mc = stx.stitch_kunye(stx.runs_of(idx), op)
    gf = (sum(is_garble(l) for l in lines)/len(lines)) if lines else 0.0
    lowfrac = len(low)/max(1, len(lines))
    # PRİMER SİNYAL = düşük-güven ORANI (medconf uzun scroll'da fazla muhafazakâr).
    if not lines: b = "BOŞ"
    elif gf > 0.5: b = "ZOR(yabancı/garble)"
    elif lowfrac > 0.25 or mc < 0.40: b = "ZOR"
    elif lowfrac > 0.08 or gf > 0.30: b = "GÖZDEN-GEÇİR"
    else: b = "GÜVENİLİR"
    rows.append({"film": stem, "n": kn, "low": len(low), "medconf": round(mc, 2), "gf": round(gf, 2), "bucket": b})

order = {"GÜVENİLİR": 0, "GÖZDEN-GEÇİR": 1, "ZOR": 2, "ZOR(yabancı/garble)": 3, "BOŞ": 4, "BOZUK": 5}
rows.sort(key=lambda r: (order.get(r["bucket"], 9), r["medconf"]))
from collections import Counter
cnt = Counter(r["bucket"] for r in rows)
(OUT/"_RELIABILITY.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
md = ["# GÜVENİLİRLİK RAPORU — clip_pipeline100", "",
      "| bucket | adet |", "|---|---:|"]
for b in ["GÜVENİLİR", "GÖZDEN-GEÇİR", "ZOR", "ZOR(yabancı/garble)", "BOŞ", "BOZUK"]:
    if cnt.get(b): md.append(f"| {b} | {cnt[b]} |")
md += ["", f"Toplam: {len(rows)} segment", "",
       "## Segment listesi (bucket, medconf, künye, düşük-güven, garble%)", "",
       "| film | bucket | medconf | künye | düşük | garble% |", "|---|---|---:|---:|---:|---:|"]
for r in rows:
    md.append(f"| {r['film']} | {r['bucket']} | {r['medconf']} | {r['n']} | {r['low']} | {int(r['gf']*100)} |")
(OUT/"_RELIABILITY.md").write_text("\n".join(md), encoding="utf-8")
print(f"{len(rows)} segment | " + " ".join(f"{b}={cnt[b]}" for b in order if cnt.get(b)))
print(f"-> {OUT/'_RELIABILITY.md'}")
