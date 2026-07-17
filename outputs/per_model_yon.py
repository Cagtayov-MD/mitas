# -*- coding: utf-8 -*-
"""Model-model YÖNETMEN doğruluk karşılaştırması (43 film, tek tek — ensemble DEĞİL).
TEXT (gemma3:12b, qwen3:8b) → OCR kunye.txt. VISION (qwen2.5vl:7b, gemma4:26b) → KARELER (video-tag).
Her model: GT'ye karşı MATCH / WRONG / ABSTAIN. Model-dış döngü, streaming, partial→JSON."""
import glob, json, sys, unicodedata
sys.path.insert(0, r"E:\MITAS\scripts")
import credit_text_read as ctr
import credit_video_read as cv
cv.NUM_CTX = 40960  # 36 kare > 16384 ctx → HTTP 400 fix

raw=open(r"C:\Users\TRT03\AppData\Local\Temp\claude\E--MITAS\28d49f5c-3526-4e51-9e6a-307b0914ffde\tasks\w3tz88lbf.output",encoding="utf-8",errors="ignore").read()
TAB={r["id"]:r for r in json.loads(raw)["result"]["table"]}
FIDS=list(TAB.keys())

def fold(s):
    s=(s or "")
    for a,b in (("İ","i"),("I","i"),("ı","i"),("Ş","s"),("ş","s"),("Ğ","g"),("ğ","g"),
                ("Ü","u"),("ü","u"),("Ö","o"),("ö","o"),("Ç","c"),("ç","c")):
        s=s.replace(a,b)
    return unicodedata.normalize("NFKD",s).encode("ascii","ignore").decode().lower().strip()

def classify(got, gt):
    if not got: return "ABSTAIN"
    if not gt:  return "GT-YOK"
    gf=[fold(g) for g in gt]
    for y in got:
        yf=fold(y)
        for g in gf:
            toks=[t for t in g.split() if len(t)>2]
            if toks and (toks[-1] in yf or yf in g or g in yf): return "MATCH"
    return "WRONG"

def base(fid):
    b=glob.glob(rf"E:\MITAS\Database\evoArcadmin*{fid}*"); return b[0] if b else None
def ocr_lines(fid):
    p=glob.glob(rf"E:\MITAS\Database\evoArcadmin*{fid}*\ocr\ocr-*\kunye.txt")
    return open(p[0],encoding="utf-8",errors="ignore").read().splitlines() if p else None

results={fid:{} for fid in FIDS}
score={}
kb=cv.KB()

def tally(model):
    c={"MATCH":0,"WRONG":0,"ABSTAIN":0,"GT-YOK":0,"YOK":0}
    for fid in FIDS:
        v=results[fid].get(model)
        if v is None: continue
        if v=="YOK": c["YOK"]+=1; continue
        c[classify(v, TAB[fid].get("dogru_yonetmen") or [])]+=1
    score[model]=c
    print(f"  >>> {model}: MATCH={c['MATCH']} WRONG={c['WRONG']} ABSTAIN={c['ABSTAIN']} (veri-yok={c['YOK']})",flush=True)

def run_text(model):
    print(f"--- TEXT {model} ---",flush=True)
    for fid in FIDS:
        title=TAB[fid].get("tr",""); lines=ocr_lines(fid)
        if not lines: results[fid][model]="YOK"; continue
        try: yon=ctr.read_credits_from_text(lines,title,model).get("yonetmen") or []
        except Exception as e: yon=[f"HATA"]
        results[fid][model]=yon
        cls=classify(yon, TAB[fid].get("dogru_yonetmen") or [])
        fl="X" if cls=="WRONG" else ("+" if cls=="MATCH" else ".")
        print(f"  {fl} {title[:24]:<25} {yon}",flush=True)
    tally(model); json.dump(results,open(r"E:\MITAS\outputs\per_model_yon.json","w",encoding="utf-8"),ensure_ascii=False)

def run_vision(model):
    print(f"--- VISION {model} (kare/video-tag) ---",flush=True)
    for fid in FIDS:
        title=TAB[fid].get("tr",""); b=base(fid)
        g=(b+r"\frames\giris") if b else None; c=(b+r"\frames\cikis") if b else None
        if not (g and glob.os.path.isdir(g)): results[fid][model]="YOK"; print(f"  ? {title[:24]:<25} KARE-YOK",flush=True); continue
        try: yon=cv.read_credits(g, c if (c and glob.os.path.isdir(c)) else None, models=[model], kb=kb).get("yonetmen") or []
        except Exception as e: yon=[f"HATA:{type(e).__name__}"]
        results[fid][model]=yon
        cls=classify(yon, TAB[fid].get("dogru_yonetmen") or [])
        fl="X" if cls=="WRONG" else ("+" if cls=="MATCH" else ".")
        print(f"  {fl} {title[:24]:<25} {yon}",flush=True)
    tally(model); json.dump(results,open(r"E:\MITAS\outputs\per_model_yon.json","w",encoding="utf-8"),ensure_ascii=False)

for m in ("gemma3:12b","qwen3:8b"): run_text(m)
for m in ("qwen2.5vl:7b","gemma4:26b"): run_vision(m)

print("\n\n================ KİM DAHA DOĞRU — YÖNETMEN (43 film) ================",flush=True)
print(f"{'MODEL':<16}{'GİRİŞ':<10}{'MATCH':<8}{'WRONG':<8}{'ABSTAIN':<9}{'isabet% (M/(M+W))'}",flush=True)
for m,inp in (("gemma3:12b","metin"),("qwen3:8b","metin"),("qwen2.5vl:7b","kare"),("gemma4:26b","kare")):
    c=score.get(m,{}); M=c.get("MATCH",0); W=c.get("WRONG",0); A=c.get("ABSTAIN",0)
    prec=f"{100*M/(M+W):.0f}%" if (M+W) else "—"
    print(f"{m:<16}{inp:<10}{M:<8}{W:<8}{A:<9}{prec}",flush=True)
print("\nNot: WRONG=0 + en yüksek MATCH ideal. Vision, metnin ABSTAIN kaldığını kareden kurtarabilir.",flush=True)
