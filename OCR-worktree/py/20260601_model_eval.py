"""Bir okuyucu modelini 15 filmde değerlendir — vs glm vs OneOCR + kaçırdığı isim mi gürültü mü.
Kullanım: python 20260601_model_eval.py --dir qwen2.5vl_7b --name "qwen2.5vl:7b"
"""
import sys, json, importlib.util, duckdb, argparse
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
spec=importlib.util.spec_from_file_location("rw", r"E:\MITAS\OCR-worktree\py\20260531_2330_read_3way.py")
rw=importlib.util.module_from_spec(spec); sys.modules["rw"]=rw; spec.loader.exec_module(rw)
fold=rw.fold; cr=rw.cr
BASE=Path(r"E:\MITAS\OCR-worktree\tester_shootout15"); T3=Path(r"E:\MITAS\OCR-worktree\tester_3way")
GL=BASE/"glm-ocr_latest"
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

ap=argparse.ArgumentParser(); ap.add_argument("--dir",required=True); ap.add_argument("--name",required=True); a=ap.parse_args()
MD=BASE/a.dir
prog=json.load(open(BASE/"_PROGRESS.json",encoding="utf-8"))
tm={(r["label"],r["seg"]):r["sec"] for r in prog if r["model"]==a.name}
con=duckdb.connect(cr.DB, read_only=True)

rows=[]; mt=glt=ot=mtr=otr=msec=0.0
miss_all=[]; brk={"cop":0,"kisa":0,"saglam":0}; perfilm={}
for label,sub in rw.FILMS:
    d=rw.find_dir(sub)
    if not d: continue
    for seg in ("giris","cikis"):
        mf=MD/f"{label}_{seg}.txt"
        if not mf.exists(): continue
        m=rd(mf); gl=rd(GL/f"{label}_{seg}.txt"); o=rd(T3/label/seg/"oneocr.txt")
        sec=tm.get((label,seg),0)
        rows.append((f"{label}/{seg}",len(m),len(gl),len(o),trc(m),trc(o),sec))
        mt+=len(m); glt+=len(gl); ot+=len(o); mtr+=trc(m); otr+=trc(o); msec+=sec
        fm={fold(x) for x in m}
        oo=[x for x in o if fold(x) not in fm]
        for t in oo: brk[cls(t)]+=1
        sag=[x for x in oo if cls(x)=="saglam"]; perfilm[f"{label}/{seg}"]=sag; miss_all+=sag

print(f"=== {a.name} — 15 FİLM (vs glm vs OneOCR) ===")
print(f"{'film/seg':28} {a.name[:9]:>9} {'glm':>5} {'1OCR':>5} | {'TR':>4} {'1TR':>4} | {'süre':>6}")
for nm,mn,gln,on,mtr_,otr_,sec in rows:
    print(f"{nm:28} {mn:>9} {gln:>5} {on:>5} | {mtr_:>4} {otr_:>4} | {sec:>5}s")
print(f"{'TOPLAM':28} {mt:>9.0f} {glt:>5.0f} {ot:>5.0f} | {mtr:>4.0f} {otr:>4.0f} | {round(msec)}s")
print(f"\n{a.name}: {mt:.0f} satır = OneOCR'ın %{round(mt/max(ot,1)*100)}'i, glm'in %{round(mt/max(glt,1)*100)}'i")
print(f"TR-diakritik {mtr:.0f} vs OneOCR {otr:.0f} (%{round(mtr/max(otr,1)*100)}) · süre {round(msec/60,1)}dk, {round(msec/max(len(rows),1),1)}s/master")

# kaçırdığı isim mi gürültü mü
folds=list({fold(t) for t in miss_all}); kbmap=cr.kb_exact_batch(con,folds)
def person(t):
    fk=fold(t); n=sum(1 for w in t.split() if any(c.isalpha() for c in w))
    return fk in kbmap and n>=2
tot=sum(brk.values()); kbp=sum(1 for t in miss_all if person(t))
print(f"\n--- KAÇIRDIĞI (OneOCR'da var, modelde yok): {tot} ---")
print(f"  çöp={brk['cop']} (%{round(brk['cop']/max(tot,1)*100)}) · kısa={brk['kisa']} · SAĞLAM={brk['saglam']} (%{round(brk['saglam']/max(tot,1)*100)})")
print(f"  sağlam-miss'in KB-kesin-kişi olanı: {kbp}/{brk['saglam']}")
print("  -- en zayıf 3 filmde sağlam-miss örnekleri (👤=KB-kişi): --")
worst=sorted(rows,key=lambda r:r[1]/max(r[3],1))[:3]
for nm,mn,gln,on,*_ in worst:
    sag=perfilm.get(nm,[])
    print(f"   [{nm}] model={mn} OneOCR={on}:")
    for t in sag[:10]: print(f"      {'👤' if person(t) else '  '} {t}")
con.close()
