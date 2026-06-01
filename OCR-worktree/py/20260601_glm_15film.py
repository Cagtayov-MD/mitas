"""glm-ocr 15-FİLM DEĞERLENDİRME — zaten bitti (29/29). OneOCR baseline'a karşı.
Per-film: glm satır/OneOCR satır, TR-diac, glm%, glm-only-sağlam, OneOCR-only-sağlam (glm kaçırmış mı).
Soru: glm 15 filmde de 'temiz isim oku, sponsor/gürültü atla' davranışını sürdürüyor mu?
"""
import sys, importlib.util
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
spec=importlib.util.spec_from_file_location("rw", r"E:\MITAS\OCR-worktree\py\20260531_2330_read_3way.py")
rw=importlib.util.module_from_spec(spec); sys.modules["rw"]=rw; spec.loader.exec_module(rw)
fold=rw.fold
GLM=Path(r"E:\MITAS\OCR-worktree\tester_shootout15\glm-ocr_latest")
T3=Path(r"E:\MITAS\OCR-worktree\tester_3way")
TR_MARK=set("şŞğĞıİ"); TR_V=set("aeıioöuüAEIİOÖUÜ")
def trc(L): return sum(1 for t in L if any(c in TR_MARK for c in t))
def cls(t):
    s=t.strip(); a=[c for c in s if c.isalpha()]
    if len(s)<=2 or len(a)<3: return "cop"
    if not any(c in TR_V for c in s): return "cop"
    if len(set(s.replace(" ","")))<=2: return "cop"
    toks=[w for w in s.split() if any(c.isalpha() for c in w)]
    if len(toks)<=1 and len(a)<=4: return "kisa"
    return "saglam"
def rd(p): return [x for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()] if Path(p).exists() else []

rows=[]; gtot=otot=gtr=otr=0; miss_saglam_all=[]
for label,sub in rw.FILMS:
    d=rw.find_dir(sub)
    if not d: continue
    for seg in ("giris","cikis"):
        gf=GLM/f"{label}_{seg}.txt"; of=T3/label/seg/"oneocr.txt"
        if not gf.exists() or not of.exists(): continue
        g=rd(gf); o=rd(of)
        fg={fold(x) for x in g}; fo={fold(x) for x in o}
        one_only=[x for x in o if fold(x) not in fg]
        one_only_sag=[x for x in one_only if cls(x)=="saglam"]
        glm_only_sag=[x for x in g if fold(x) not in fo and cls(x)=="saglam"]
        pct=round(len(g)/max(len(o),1)*100)
        rows.append((f"{label}/{seg}", len(g), len(o), trc(g), trc(o), pct, len(glm_only_sag), len(one_only_sag)))
        gtot+=len(g); otot+=len(o); gtr+=trc(g); otr+=trc(o)
        for x in one_only_sag: miss_saglam_all.append((f"{label}/{seg}", x))

print("=== glm-ocr 15-FİLM (vs OneOCR) ===")
print(f"{'film/seg':28} {'glm':>4} {'1OCR':>4} {'glm%':>5} | {'gTR':>4} {'1TR':>4} | {'glm+':>4} {'1OCR+':>5}")
print("-"*78)
for nm,gn,on,gt,ot,pc,go,oo in rows:
    flag=" ⚠düşük" if pc<60 else ""
    print(f"{nm:28} {gn:>4} {on:>4} {pc:>4}% | {gt:>4} {ot:>4} | {go:>4} {oo:>5}{flag}")
print("-"*78)
print(f"{'TOPLAM':28} {gtot:>4} {otot:>4} {round(gtot/max(otot,1)*100):>4}% | {gtr:>4} {otr:>4}")
print(f"\nglm toplam satır={gtot} | OneOCR={otot} | glm OneOCR'ın %{round(gtot/max(otot,1)*100)}'i")
print(f"glm TR-diakritik={gtr} | OneOCR={otr}")
print(f"\nOneOCR-only SAĞLAM (glm'nin kaçırdığı, ama çoğu sponsor/logo olabilir): toplam {len(miss_saglam_all)}")
print("  -- glm%'si en düşük 5 film (glm en çok kaçırdığı yerler): --")
for nm,gn,on,gt,ot,pc,go,oo in sorted(rows,key=lambda r:r[5])[:5]:
    print(f"     {nm:28} glm={gn} OneOCR={on} (%{pc}) — OneOCR-only-sağlam={oo}")
