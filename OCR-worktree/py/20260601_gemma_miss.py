"""gemma'nın KAÇIRDIKLARI isim mi, gürültü/logo mu? OneOCR-only (gemma'da yok) sınıfla + KB-kişi kontrolü.
Aggregat (çöp/kısa/sağlam) + KB-doğrulanmış-kişi sayısı + en zayıf filmlerde gözle örnek.
"""
import sys, importlib.util, duckdb
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
spec=importlib.util.spec_from_file_location("rw", r"E:\MITAS\OCR-worktree\py\20260531_2330_read_3way.py")
rw=importlib.util.module_from_spec(spec); sys.modules["rw"]=rw; spec.loader.exec_module(rw)
fold=rw.fold; cr=rw.cr
GE=Path(r"E:\MITAS\OCR-worktree\tester_shootout15\gemma4_26b"); T3=Path(r"E:\MITAS\OCR-worktree\tester_3way")
TR_V=set("aeıioöuüAEIİOÖUÜ")
def cls(t):
    s=t.strip(); a=[c for c in s if c.isalpha()]
    if len(s)<=2 or len(a)<3: return "cop"
    if not any(c in TR_V for c in s): return "cop"
    if len(set(s.replace(" ","")))<=2: return "cop"
    toks=[w for w in s.split() if any(c.isalpha() for c in w)]
    if len(toks)<=1 and len(a)<=4: return "kisa"
    return "saglam"
def rd(p): return [x for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()] if Path(p).exists() else []

con=duckdb.connect(cr.DB, read_only=True)
miss_all=[]; brk={"cop":0,"kisa":0,"saglam":0}; per_film={}
for label,sub in rw.FILMS:
    d=rw.find_dir(sub)
    if not d: continue
    for seg in ("giris","cikis"):
        gf=GE/f"{label}_{seg}.txt"
        if not gf.exists(): continue
        g=rd(gf); o=rd(T3/label/seg/"oneocr.txt")
        fg={fold(x) for x in g}
        oo=[x for x in o if fold(x) not in fg]   # gemma kaçırdı
        for t in oo: brk[cls(t)]+=1
        sag=[x for x in oo if cls(x)=="saglam"]
        per_film[f"{label}/{seg}"]=sag
        for t in sag: miss_all.append(t)

# KB-kişi kontrolü: sağlam-miss'lerin kaçı 13M kişi dizininde (≥2 token) = KESİN gerçek isim
folds=list({fold(t) for t in miss_all})
kbmap=cr.kb_exact_batch(con, folds)
def is_person(t):
    fk=fold(t); ntok=sum(1 for w in t.split() if any(c.isalpha() for c in w))
    return fk in kbmap and ntok>=2
kb_person=sum(1 for t in miss_all if is_person(t))

print("=== gemma'nın KAÇIRDIĞI (OneOCR'da var, gemma'da yok) — 15 film toplam ===")
tot=sum(brk.values())
print(f"  toplam kaçırılan: {tot}")
print(f"   - çöp/gürültü      : {brk['cop']:4} (%{round(brk['cop']/max(tot,1)*100)})  -> zaten istemiyoruz")
print(f"   - kısa-parça       : {brk['kisa']:4} (%{round(brk['kisa']/max(tot,1)*100)})")
print(f"   - SAĞLAM (içerik)  : {brk['saglam']:4} (%{round(brk['saglam']/max(tot,1)*100)})")
print(f"\n  SAĞLAM kaçırılanların KB-doğrulanmış GERÇEK KİŞİ olanı: {kb_person} / {brk['saglam']}")
print(f"   (gerisi: sponsor/firma/rol-başlığı/notable-olmayan-kadro/garble — KB'de yok)")

print("\n=== EN ZAYIF filmlerde gemma'nın SAĞLAM kaçırdıkları (gözle: isim mi logo mu?) ===")
for fn in ["KANSAS_1950/cikis","GUZEL_OLUM_1968/giris","ANJELIK_1968/cikis","SENIN_HIKAYEN_2024/cikis"]:
    sag=per_film.get(fn,[])
    print(f"\n--- {fn}  (sağlam-miss: {len(sag)}) ---")
    for t in sag[:16]:
        mark="👤KİŞİ" if is_person(t) else "      "
        print(f"   {mark} {t}")
con.close()
