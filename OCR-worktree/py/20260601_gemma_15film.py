"""gemma4:26b 15-FİLM DEĞERLENDİRME — bitti (29/29). OneOCR + glm'e karşı.
Per-film: gemma/glm/OneOCR satır, gemma TR-diac vs OneOCR, gemma süre. Aggregat + verdikt.
"""
import sys, json, importlib.util
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
spec=importlib.util.spec_from_file_location("rw", r"E:\MITAS\OCR-worktree\py\20260531_2330_read_3way.py")
rw=importlib.util.module_from_spec(spec); sys.modules["rw"]=rw; spec.loader.exec_module(rw)
fold=rw.fold
GE=Path(r"E:\MITAS\OCR-worktree\tester_shootout15\gemma4_26b")
GL=Path(r"E:\MITAS\OCR-worktree\tester_shootout15\glm-ocr_latest")
T3=Path(r"E:\MITAS\OCR-worktree\tester_3way")
TR_MARK=set("şŞğĞıİ")
def trc(L): return sum(1 for t in L if any(c in TR_MARK for c in t))
def rd(p): return [x for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()] if Path(p).exists() else []

# gemma süreleri _PROGRESS'ten
prog=json.load(open(r"E:\MITAS\OCR-worktree\tester_shootout15\_PROGRESS.json",encoding="utf-8"))
gtime={(r["label"],r["seg"]):r["sec"] for r in prog if r["model"]=="gemma4:26b"}

rows=[]; gt=glt=ot=gtr=otr=gsec=0.0
for label,sub in rw.FILMS:
    d=rw.find_dir(sub)
    if not d: continue
    for seg in ("giris","cikis"):
        gf=GE/f"{label}_{seg}.txt"
        if not gf.exists(): continue
        g=rd(gf); gl=rd(GL/f"{label}_{seg}.txt"); o=rd(T3/label/seg/"oneocr.txt")
        sec=gtime.get((label,seg),0)
        rows.append((f"{label}/{seg}", len(g), len(gl), len(o), trc(g), trc(o), sec))
        gt+=len(g); glt+=len(gl); ot+=len(o); gtr+=trc(g); otr+=trc(o); gsec+=sec

print("=== gemma4:26b — 15 FİLM (vs glm vs OneOCR) ===")
print(f"{'film/seg':28} {'gemma':>5} {'glm':>5} {'1OCR':>5} | {'gTR':>4} {'1TR':>4} | {'süre':>6}")
print("-"*72)
for nm,gn,gln,on,gtr_,otr_,sec in rows:
    print(f"{nm:28} {gn:>5} {gln:>5} {on:>5} | {gtr_:>4} {otr_:>4} | {sec:>5}s")
print("-"*72)
print(f"{'TOPLAM':28} {gt:>5} {glt:>5} {ot:>5} | {gtr:>4} {otr:>4} | {round(gsec)}s")
print(f"\ngemma toplam satır={gt}  (glm={glt}, OneOCR={ot})  -> gemma OneOCR'ın %{round(gt/max(ot,1)*100)}'i, glm'in %{round(gt/max(glt,1)*100)}'i")
print(f"gemma TR-diakritik={gtr}  (OneOCR={otr})  -> %{round(gtr/max(otr,1)*100)}")
print(f"gemma toplam süre={round(gsec)}s = {round(gsec/60,1)} dk  (ort {round(gsec/max(len(rows),1),1)}s/master)")
print(f"  [kıyas] glm ~3-30s/master, OneOCR ~1-15s/master — gemma {round(gsec/max(len(rows),1),1)}s")
# nerede gemma öne/geri
better=[r for r in rows if r[1]>r[3]]; worse=[r for r in rows if r[1]<r[3]*0.7]
print(f"\ngemma OneOCR'dan ÇOK okuduğu film sayısı: {len(better)}")
print(f"gemma OneOCR'ın %70'inden AZ okuduğu (zayıf): {len(worse)}")
for nm,gn,gln,on,a,b,s in sorted(worse,key=lambda r:r[1]/max(r[3],1))[:6]:
    print(f"   {nm:28} gemma={gn} OneOCR={on} (%{round(gn/max(on,1)*100)})")
