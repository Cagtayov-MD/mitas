"""glm + OneOCR BİRLEŞTİRME prototipi — DETERMİNİSTİK (LLM serbest-birleştirme YOK = fidelity güvenli).
Yöntem: iki sıralı liste, fold ile LCS-hizalama (difflib) -> ortak satırlar çapa, benzersizler SIRASINDA araya girer.
+ gürültü(çöp) ele + fold-dedup. Sonuç: glm'nin temizi + OneOCR'ın ek-yakaladığı, sırada, tekrarsız.
qwen'in YERİ: sadece ÇELİŞKİ (glm≠OneOCR aynı yerde garbled) için görsel-bölge hakemi — opsiyonel.
"""
import sys, difflib, importlib.util
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
spec=importlib.util.spec_from_file_location("rw", r"E:\MITAS\OCR-worktree\py\20260531_2330_read_3way.py")
rw=importlib.util.module_from_spec(spec); sys.modules["rw"]=rw; spec.loader.exec_module(rw)
fold=rw.fold
GLM=Path(r"E:\MITAS\OCR-worktree\tester_shootout15\glm-ocr_latest")
T3=Path(r"E:\MITAS\OCR-worktree\tester_3way")
TR_V=set("aeıioöuüAEIİOÖUÜ")
def cls(t):
    s=t.strip(); a=[c for c in s if c.isalpha()]
    if len(s)<=2 or len(a)<3: return "cop"
    if not any(c in TR_V for c in s): return "cop"
    if len(set(s.replace(" ","")))<=2: return "cop"
    toks=[w for w in s.split() if any(c.isalpha() for c in w)]
    if len(toks)<=1 and len(a)<=4: return "kisa"
    return "saglam"
def diac(t): return sum(1 for c in t if c in "şŞğĞıİçÇöÖüÜ")
def rd(p): return [x for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()] if Path(p).exists() else []

def merge(G, O, drop_noise=True):
    """G=glm (birincil), O=OneOCR (yedek). Sıralı union, çapa=ortak fold."""
    fg=[fold(x) for x in G]; fo=[fold(x) for x in O]
    sm=difflib.SequenceMatcher(None, fg, fo, autojunk=False)
    out=[]; prov=[]  # prov: her satırın kaynağı (ortak/glm/oneocr)
    for tag,i1,i2,j1,j2 in sm.get_opcodes():
        if tag=="equal":                       # ORTAK: daha iyi-diakritikli varyantı seç
            for k in range(i1,i2):
                g=G[k]; o=O[j1+(k-i1)] if j1+(k-i1)<j2 else g
                out.append(o if diac(o)>diac(g) else g); prov.append("ortak")
        elif tag=="delete":                     # sadece glm
            for k in range(i1,i2): out.append(G[k]); prov.append("glm")
        elif tag=="insert":                     # sadece OneOCR (glm kaçırmış)
            for k in range(j1,j2): out.append(O[k]); prov.append("oneocr+")
        elif tag=="replace":                    # AYNI yerde FARKLI (çelişki) -> ikisini de koy, işaretle
            for k in range(i1,i2): out.append(G[k]); prov.append("glm?")
            for k in range(j1,j2): out.append(O[k]); prov.append("oneocr?")
    # gürültü ele + fold-dedup
    seen=set(); fin=[]; finprov=[]
    for t,p in zip(out,prov):
        if drop_noise and cls(t)=="cop": continue
        fk=fold(t)
        if fk in seen: continue
        seen.add(fk); fin.append(t); finprov.append(p)
    return fin, finprov

def demo(label, seg):
    g=rd(GLM/f"{label}_{seg}.txt"); o=rd(T3/label/seg/"oneocr.txt")
    m,prov=merge(g,o)
    add=sum(1 for p in prov if p=="oneocr+")
    print(f"\n=== {label}/{seg} ===")
    print(f"  glm tek={len(g)}  OneOCR tek={len(o)}  ->  BİRLEŞİK(gürültüsüz)={len(m)}")
    print(f"  birleşik içinde OneOCR'ın eklediği (glm kaçırmıştı): {add} satır")
    print(f"  --- OneOCR'ın eklediği örnekler (glm'de yoktu): ---")
    shown=0
    for t,p in zip(m,prov):
        if p=="oneocr+" and cls(t)=="saglam":
            print(f"     +{t}"); shown+=1
            if shown>=12: break

demo("DIRILIS_2014","cikis")       # modern: glm zaten iyi, ek az
demo("GUZEL_OLUM_1968","giris")    # eski: glm az okudu, OneOCR çok ekler
