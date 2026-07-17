# -*- coding: utf-8 -*-
"""İKİ TEXT-CONFIG kıyas (yalnız text aşaması, VL yok — hızlı):
  A) qwen3-only          B) gemma3+qwen3 (mutabakatlı ensemble)
Soru: gemma3 eklemek VL-yükünü (kaç film abstain→VL) azaltıyor mu + yönetmen kalitesi?"""
import os, glob, sys, unicodedata, time
sys.path.insert(0, r"E:\MITAS\scripts")
import credit_text_read as ctr
raw=open(r"C:\Users\TRT03\AppData\Local\Temp\claude\E--MITAS\28d49f5c-3526-4e51-9e6a-307b0914ffde\tasks\w3tz88lbf.output",encoding="utf-8",errors="ignore").read()
import json
TAB={r["id"]:r for r in json.loads(raw)["result"]["table"]}

def fold(s):
    s=(s or "")
    for a,b in (("İ","i"),("I","i"),("ı","i"),("Ş","s"),("ş","s"),("Ğ","g"),("ğ","g"),
                ("Ü","u"),("ü","u"),("Ö","o"),("ö","o"),("Ç","c"),("ç","c")):
        s=s.replace(a,b)
    return unicodedata.normalize("NFKD",s).encode("ascii","ignore").decode().lower().strip()
def match(yon, gt):
    if not yon or not gt: return False
    gf=[fold(g) for g in gt]
    for y in yon:
        yf=fold(y)
        for g in gf:
            tk=[t for t in g.split() if len(t)>2]
            if tk and (tk[-1] in yf or yf in g or g in yf): return True
    return False
def ocr_lines(fid):
    p=glob.glob(rf"E:\MITAS\Database\evoArcadmin*{fid}*\ocr\ocr-*\kunye.txt")
    return open(p[0],encoding="utf-8",errors="ignore").read().splitlines() if p else None

FIDS=["1973-0173-1-0000-85-1","1978-0178-1-0000-40-1","1982-0253-1-0000-00-1",
      "1984-0246-1-0000-00-1","1985-0254-1-0000-00-1","1986-0241-1-0000-00-1",
      "1987-0248-1-0000-00-1","1989-0363-1-0000-00-1","1990-0393-1-0000-00-1",
      "1977-0211-1-0000-90-1","1996-0254-1-0000-00-1","1991-0392-1-0000-00-1"]

def run(env):
    os.environ["MITAS_CREDIT_TEXT_MODEL"]=env
    out={}
    t0=time.time()
    for fid in FIDS:
        title=TAB[fid].get("tr",""); lines=ocr_lines(fid)
        r=ctr.read_credits_auto(lines,title) if lines else {"yonetmen":[],"cast":[]}
        yon=r.get("yonetmen") or []; cast=r.get("cast") or []
        out[fid]=(yon, len(cast), (not yon) or (len(cast)<3), match(yon, TAB[fid].get("dogru_yonetmen") or []))
    return out, time.time()-t0

print("A) qwen3-only koşuyor...",flush=True)
A,ta=run("qwen3:8b")
print("B) gemma3+qwen3 koşuyor...",flush=True)
B,tb=run("gemma3:12b,qwen3:8b")

print(f"\n{'FİLM':<24}{'GT':<16}{'qwen3-only':<26}{'gemma3+qwen3'}",flush=True)
print("-"*100,flush=True)
for fid in FIDS:
    t=TAB[fid].get("tr","")[:22]; gt=", ".join(TAB[fid].get("dogru_yonetmen") or [])[:14]
    ay,ac,atr,aok=A[fid]; by,bc,btr,bok=B[fid]
    af=("VL" if atr else "✓text")+("·"+("M" if aok else "x"))
    bf=("VL" if btr else "✓text")+("·"+("M" if bok else "x"))
    print(f"{t:<24}{gt:<16}{(af+' '+str(ay)[:14]):<26}{bf+' '+str(by)[:14]}",flush=True)
print("-"*100,flush=True)
avl=sum(1 for f in FIDS if A[f][2]); bvl=sum(1 for f in FIDS if B[f][2])
amatch=sum(1 for f in FIDS if A[f][3]); bmatch=sum(1 for f in FIDS if B[f][3])
print(f"VL'ye düşen (az=hızlı):   qwen3-only={avl}/12   gemma3+qwen3={bvl}/12",flush=True)
print(f"text'te doğru yönetmen:   qwen3-only={amatch}/12   gemma3+qwen3={bmatch}/12",flush=True)
print(f"text süresi (12 film):    qwen3-only={ta:.0f}sn   gemma3+qwen3={tb:.0f}sn",flush=True)
