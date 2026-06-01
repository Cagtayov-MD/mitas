"""20260601 — 3-OKUYUCU UZLAŞTIRICI v1: OneOCR (spine) + glm → deterministik birleştir + KB + Türkçe-BÜYÜK-harf.
- LCS hizalama (difflib) → agree / 1ocr-only / glm-only / conflict.
- conflict + near-dup (Türkel/Türkkel): KB notable-isim varsa KB kanonik, yoksa literal (diakritik+uzunluk).
- KB notable yazım + Türkçe-büyük-harf (i→İ, ı→I).
- qwen3.6 hakem AYRI katman (burada conflict'leri İŞARETLER, sonra hakeme gider).
Demo: kayıtlı OneOCR (tester_3way) + glm (tester_shootout15) çıktılarını uzlaştırır.
"""
import sys, difflib, importlib.util, duckdb, argparse
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
spec=importlib.util.spec_from_file_location("rw", r"E:\MITAS\OCR-worktree\py\20260531_2330_read_3way.py")
rw=importlib.util.module_from_spec(spec); sys.modules["rw"]=rw; spec.loader.exec_module(rw)
fold=rw.fold; cr=rw.cr

def tr_upper(s): return s.replace("i","İ").upper()   # Türkçe: i→İ, ı→I (.upper ı'yı zaten I yapar)
def diac(s): return sum(c in "şŞğĞıİçÇöÖüÜ" for c in s)
def near(a,b):  # fold-near-dup (aynı kişi, farklı garble) — KONSERVATİF
    fa,fb=fold(a),fold(b)
    if not fa or not fb: return False
    ta,tb=fa.split(),fb.split()
    if len(ta)!=len(tb) or ta[0]!=tb[0]: return False     # aynı token sayısı + aynı ilk kelime
    return difflib.SequenceMatcher(None,fa,fb).ratio()>=0.86

def resolve(cands, kb):
    """aynı girdinin varyantları → KB kanonik > en-diakritikli/uzun (literal)."""
    for c in cands:
        ntok=sum(1 for w in c.split() if any(ch.isalpha() for ch in w))
        if fold(c) in kb and ntok>=2: return kb[fold(c)],"KB"
    return max(cands,key=lambda c:(diac(c),len(c))),"literal"

def reconcile(one, glm, con):
    sm=difflib.SequenceMatcher(None,[fold(x) for x in one],[fold(x) for x in glm],autojunk=False)
    merged=[]  # (text, kaynak)
    for tag,i1,i2,j1,j2 in sm.get_opcodes():
        if tag=="equal":
            for k in range(i1,i2): merged.append([one[k],"uzlaşı"])
        elif tag=="delete":
            for k in range(i1,i2): merged.append([one[k],"1ocr"])
        elif tag=="insert":
            for k in range(j1,j2): merged.append([glm[k],"glm"])
        elif tag=="replace":
            os=list(one[i1:i2]); gs=list(glm[j1:j2]); used=set()
            for o in os:
                pi=next((gi for gi,g in enumerate(gs) if gi not in used and near(o,g)),None)
                if pi is not None: used.add(pi); merged.append([o,"çelişki",gs[pi]])  # çift sakla
                else: merged.append([o,"1ocr"])
            for gi,g in enumerate(gs):
                if gi not in used: merged.append([g,"glm"])
    # KB toplu
    folds=list({fold(m[0]) for m in merged}|{fold(m[2]) for m in merged if len(m)>2})
    kb=cr.kb_exact_batch(con,folds)
    # çözümle + KB yazım + büyük-harf
    out=[]
    for m in merged:
        if m[1]=="çelişki":
            chosen,how=resolve([m[0],m[2]],kb); src=f"çelişki→{how}"
        else:
            # tekil satıra da KB-yazım uygula (notable ise)
            ntok=sum(1 for w in m[0].split() if any(ch.isalpha() for ch in w))
            chosen=kb[fold(m[0])] if (fold(m[0]) in kb and ntok>=2) else m[0]; src=m[1]
        out.append([chosen,src])
    # global near-dup süpürme (LCS yakalamadıysa) — konservatif
    final=[];
    for t,s in out:
        dup=next((f for f in final if near(f[0],t)),None)
        if dup:
            # daha iyi yazımı tut (KB/diakritik)
            if diac(t)>diac(dup[0]): dup[0]=t
            continue
        final.append([t,s])
    return final

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--film",default="DIRILIS_2014"); ap.add_argument("--seg",default="cikis"); a=ap.parse_args()
    one=[x for x in (Path(r"E:\MITAS\OCR-worktree\tester_3way")/a.film/a.seg/"oneocr.txt").read_text(encoding="utf-8").splitlines() if x.strip()]
    glm=[x for x in (Path(rf"E:\MITAS\OCR-worktree\tester_shootout15\glm-ocr_latest\{a.film}_{a.seg}.txt")).read_text(encoding="utf-8").splitlines() if x.strip()]
    con=duckdb.connect(cr.DB,read_only=True)
    final=reconcile(one,glm,con); con.close()
    from collections import Counter
    c=Counter(s.split("→")[0] for _,s in final)
    print(f"=== UZLAŞTIRICI — {a.film}/{a.seg} ===")
    print(f"OneOCR={len(one)}  glm={len(glm)}  ->  BİRLEŞİK={len(final)}")
    print(f"kaynak dağılımı: {dict(c)}")
    print("\n--- BİRLEŞİK ÇIKTI (Türkçe-BÜYÜK-harf, ilk 40) ---")
    for t,s in final[:40]:
        tag={"uzlaşı":"✓","1ocr":"·1","glm":"·g"}.get(s, "⚠"+s)
        print(f"  {tr_upper(t):38} [{tag}]")
    # conflict çözümleri ayrı göster
    print("\n--- ÇELİŞKİ çözümleri (KB/literal karar) ---")
    n=0
    for t,s in final:
        if "çelişki" in s:
            print(f"   {tr_upper(t):30} [{s}]"); n+=1
            if n>=12: break
    od=Path(r"E:\MITAS\OCR-worktree\tester_reconcile")/f"{a.film}_{a.seg}"; od.mkdir(parents=True,exist_ok=True)
    (od/"merged_UPPER.txt").write_text("\n".join(tr_upper(t) for t,_ in final),encoding="utf-8")
    print(f"\n-> {od/'merged_UPPER.txt'}")

if __name__=="__main__": main()
