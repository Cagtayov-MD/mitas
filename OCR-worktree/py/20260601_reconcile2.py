"""20260601 — UZLAŞTIRICI v2: v1 (OneOCR+glm+KB) üstüne (a) SPONSOR-FİLTRE + (b) ROL-SÖZLÜĞÜ normalize.
(a) sponsor/URL/telefon/firma + tek-kelime-marka (KB-kişi değilse) ELE.
(b) rol-başlığını kanonik Türkçe-diakritikli forma çek (KOSTUM->KOSTÜM TASARIM ASİSTANLARI), rolü KORU.
Çıktı: temiz isim+rol listesi, Türkçe-BÜYÜK-harf.
"""
import sys, difflib, importlib.util, duckdb, argparse
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
spec=importlib.util.spec_from_file_location("rec", r"E:\MITAS\OCR-worktree\py\20260601_reconcile.py")
rec=importlib.util.module_from_spec(spec); sys.modules["rec"]=rec; spec.loader.exec_module(rec)
fold=rec.fold; tr_upper=rec.tr_upper; cr=rec.cr

# (b) KANONİK ROL SÖZLÜĞÜ (doğru Türkçe diakritik)
ROLES=["YAPIMCI","UYGULAYICI YAPIMCI","YÖNETMEN","YÖNETMEN YARDIMCISI","GÖRÜNTÜ YÖNETMENİ",
 "KAMERAMAN","KAMERAMAN YARDIMCISI","KURGU","SENARYO","ÖZGÜN MÜZİK","MÜZİK",
 "KOSTÜM TASARIMI","KOSTÜM TASARIM ASİSTANLARI","KOSTÜM ASİSTANLARI",
 "MAKYAJ","MAKYAJ ASİSTANLARI","SAÇ MAKYAJ EKİBİ","SET TERZİSİ",
 "IŞIK EKİBİ","IŞIK ŞEFİ","IŞIK ASİSTANLARI","SES EKİBİ","SES KAYIT","SES ASİSTANI",
 "SES MÜHENDİSİ","SES TASARIM VE MİKSAJ","BOOM OPERATÖRÜ",
 "SET AMİRİ","SET ASİSTANLARI","KUAFÖR","KUAFÖR ASİSTANLARI","SANAT YÖNETMENİ",
 "DEKOR","ATÖLYELER","VFX YAPIMCISI","VFX SÜPERVİZÖRÜ","VFX KOORDİNASYON","VFX SANATÇILARI",
 "PIPELINE TD","PROJE SÜPERVİZÖRÜ","DUBLÖR VE KOREOGRAF EKİBİ","STUNT VE KOREOGRAFİ EKİBİ",
 "OYUNCULAR","KOORDİNATÖR","SÜPERVİZÖR","TOZ ALÇI","ALÇI LEVHA"]
ROLE_FOLD={fold(r):r for r in ROLES}
def role_match(t):
    fl=fold(t)
    if fl in ROLE_FOLD: return ROLE_FOLD[fl]
    best=None;bs=0.0
    for rf,r in ROLE_FOLD.items():
        ra=difflib.SequenceMatcher(None,fl,rf).ratio()
        if ra>bs: bs=ra; best=r
    return best if bs>=0.84 else None

# (a) SPONSOR FİLTRE
CORP=["ltd","tic","tekstil","elektron","makina","makine","reklam","insaat","otomotiv",
      "kurye","sigorta","limited","sirket","textile","lamp","ofset","matbaa","san ","aractan"]
def is_sponsor(t, kbpersons):
    low=t.lower(); fl=fold(t)
    if any(x in low for x in ["www.","http",".com",".tr",".net"]): return True,"url"
    d=sum(c.isdigit() for c in t); a=sum(c.isalpha() for c in t)
    if a<2 or d>a: return True,"numerik"
    if any(m in fl for m in CORP): return True,"firma-eki"
    toks=[w for w in t.split() if any(c.isalpha() for c in w)]
    if len(toks)==1 and fl not in kbpersons: return True,"tek-kelime-marka"
    return False,None

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--film",default="DIRILIS_2014"); ap.add_argument("--seg",default="cikis"); a=ap.parse_args()
    one=[x for x in (Path(r"E:\MITAS\OCR-worktree\tester_3way")/a.film/a.seg/"oneocr.txt").read_text(encoding="utf-8").splitlines() if x.strip()]
    glm=[x for x in (Path(rf"E:\MITAS\OCR-worktree\tester_shootout15\glm-ocr_latest\{a.film}_{a.seg}.txt")).read_text(encoding="utf-8").splitlines() if x.strip()]
    con=duckdb.connect(cr.cr.DB if hasattr(cr,'cr') else cr.DB,read_only=True) if False else duckdb.connect(cr.DB,read_only=True)
    final=rec.reconcile(one,glm,con)
    folds=list({fold(t) for t,_ in final}); kb=cr.kb_exact_batch(con,folds); kbpersons=set(kb.keys()); con.close()
    clean=[]; dropped=[]; rolesn=[]
    for t,s in final:
        r=role_match(t)
        if r:
            clean.append((r,"ROL"));
            if fold(r)!=fold(t): rolesn.append((t,r))
            continue
        sp,why=is_sponsor(t,kbpersons)
        if sp: dropped.append((t,why)); continue
        clean.append((t,s))
    print(f"=== UZLAŞTIRICI v2 — {a.film}/{a.seg} ===")
    print(f"v1 birleşik={len(final)} -> sponsor-filtre+rol-normalize -> TEMİZ={len(clean)} (atılan sponsor={len(dropped)}, normalize-edilen-rol={len(rolesn)})")
    print("\n--- TEMİZ ÇIKTI (Türkçe-BÜYÜK-harf, ilk 42) ---")
    for t,s in clean[:42]:
        print(f"  {tr_upper(t):36} {'[ROL]' if s=='ROL' else ''}")
    print("\n--- ATILAN sponsor/gürültü (örnek) ---")
    for t,w in dropped[:14]: print(f"   ✗ {t:34} ({w})")
    print("\n--- NORMALİZE edilen rol (önce -> sonra) ---")
    for o,r in rolesn[:10]: print(f"   {o:32} -> {r}")
    od=Path(r"E:\MITAS\OCR-worktree\tester_reconcile")/f"{a.film}_{a.seg}"; od.mkdir(parents=True,exist_ok=True)
    (od/"temiz_UPPER.txt").write_text("\n".join(tr_upper(t) for t,_ in clean),encoding="utf-8")
    print(f"\n-> {od/'temiz_UPPER.txt'}")

if __name__=="__main__": main()
