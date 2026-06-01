"""clip_pipeline100 çıktıları için GÜVENİLİR TRİYAJ (stdlib-only; bayat _SUMMARY.json'a güvenmez).
Master PNG yüksekliklerini (PNG header'dan) + künye metinlerini doğrudan tarar -> şüpheli sıralaması.
Çıktı: clip_pipeline100/_TRIAGE.json  + en şüpheli 30'un tablosu.
"""
import sys, json, struct, re, difflib, statistics as st
from pathlib import Path
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")

OUT = Path(r"E:\MITAS\OCR-worktree\clip_pipeline100")
MAST = OUT/"_MASTERS"; KUN = OUT/"_KUNYE"
VOWELS = set("aeıioöuüAEIİOÖUÜ")

def png_size(p):
    with open(p, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return (0, 0)
    w, h = struct.unpack(">II", head[16:24])
    return (w, h)

def is_garble(line):
    t = line.strip()
    if not t:
        return False
    nonsp = sum(not c.isspace() for c in t)
    if nonsp == 0:
        return False
    letters = sum(c.isalpha() for c in t)
    if letters/nonsp < 0.55:
        return True
    toks = t.split()
    if any(len(tk) >= 4 and not any(c in VOWELS for c in tk) for tk in toks):
        return True
    return False

def analyze_kunye(p):
    raw = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    dieg = bool(raw and raw[0].startswith("#"))
    lines = [l.strip() for l in raw if l.strip() and not l.startswith("#")]
    folded = [re.sub(r"\s+", " ", l.lower()) for l in lines]
    cnt = Counter(folded)
    dup = sum(v-1 for v in cnt.values() if v > 1)
    max_rep = max(cnt.values()) if cnt else 0
    consec = sum(1 for a, b in zip(folded, folded[1:])
                 if a and b and difflib.SequenceMatcher(None, a, b).ratio() >= 0.85)
    garble = sum(is_garble(l) for l in lines)
    return {"kunye": len(lines), "dieg": dieg, "dup": dup, "max_rep": max_rep, "consec": consec, "garble": garble}

rows = []
for png in sorted(MAST.glob("*.png")):
    stem = png.stem
    w, h = png_size(png)
    kp = KUN/f"{stem}.txt"
    a = analyze_kunye(kp) if kp.exists() else {"kunye": 0, "dieg": False, "dup": 0, "max_rep": 0, "consec": 0, "garble": 0}
    ppl = h/max(1, a["kunye"])
    flags = []
    if h > 12000: flags.append("BLOAT_H")
    if ppl > 400 and h > 3000: flags.append("FOOTAGE/GHOST?")
    if a["max_rep"] >= 3: flags.append(f"REPEAT_x{a['max_rep']}")
    if a["consec"] >= 3: flags.append("GHOST_CONSEC")
    if a["garble"] >= 3: flags.append(f"GARBLE_{a['garble']}")
    if a["kunye"] == 0: flags.append("EMPTY")
    elif a["kunye"] <= 2: flags.append("THIN")
    if a["dieg"]: flags.append("DIEGETIK")
    score = ((h > 12000)*3 + (ppl > 400 and h > 3000)*3 + min(a["max_rep"], 8)
             + a["consec"] + a["garble"] + (a["kunye"] == 0)*2 + a["dieg"]*1)
    rows.append({"film": stem, "w": w, "h": h, "kunye": a["kunye"], "ppl": round(ppl),
                 "max_rep": a["max_rep"], "consec": a["consec"], "garble": a["garble"],
                 "dieg": a["dieg"], "flags": flags, "score": score})

rows.sort(key=lambda r: -r["score"])
(OUT/"_TRIAGE.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(rows)} master analiz edildi. EN ŞÜPHELİ 30:\n")
print(f"{'film':44}{'h':>6}{'künye':>6}{'p/l':>6}{'rep':>4}{'cns':>4}{'grb':>4}  bayraklar")
for r in rows[:30]:
    print(f"{r['film'][:44]:44}{r['h']:>6}{r['kunye']:>6}{r['ppl']:>6}{r['max_rep']:>4}{r['consec']:>4}{r['garble']:>4}  {','.join(r['flags'])}")
hs = [r["h"] for r in rows]
print(f"\nyükseklik medyan={int(st.median(hs))} max={max(hs)} | künye=0: {sum(r['kunye']==0 for r in rows)}"
      f" | diegetik: {sum(r['dieg'] for r in rows)} | flag'li: {sum(1 for r in rows if r['flags'])}")
print(f"-> {OUT/'_TRIAGE.json'}")
