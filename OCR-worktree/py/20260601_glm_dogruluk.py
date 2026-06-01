"""glm-ocr DOĞRULUK testi — kbsiz ham verisi ne kadar doğru?
glm-ocr çıktısına KB uygula: KB kaç satır DEĞİŞTİRİYOR (=glm hatası) / TEYİT (=zaten doğru) / RAW (eşleşme yok).
Az değişiklik = glm kbsiz zaten doğru. DİRİLİŞ detay + 29 master agregat. OneOCR ile kıyas.
"""
import sys, json, glob, importlib.util
from pathlib import Path
import duckdb
sys.stdout.reconfigure(encoding="utf-8")
spec=importlib.util.spec_from_file_location("rw", r"E:\MITAS\OCR-worktree\py\20260531_2330_read_3way.py")
rw=importlib.util.module_from_spec(spec); sys.modules["rw"]=rw; spec.loader.exec_module(rw)
fold=rw.fold; kb_support=rw.kb_support
GLM=Path(r"E:\MITAS\OCR-worktree\tester_shootout15\glm-ocr_latest")
T3=Path(r"E:\MITAS\OCR-worktree\tester_3way")
con=duckdb.connect(rw.cr.DB, read_only=True)

def rd(p): return [x for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()] if Path(p).exists() else []

# ── DİRİLİŞ/çıkış DETAY ────────────────────────────────────────────────────
gl=rd(GLM/"DIRILIS_2014_cikis.txt")
gkb,gst=kb_support(gl,con)
print(f"=== glm-ocr DİRİLİŞ/çıkış DOĞRULUK ===")
print(f"  satır={len(gl)} | KB-DEĞİŞTİRDİ={gst['changed']} | KB-TEYİT(zaten doğru)={gst['confirmed']} | eşleşme-yok(raw)={gst['raw']}")
print(f"  -> notable isimlerin %{round(gst['confirmed']/max(gst['changed']+gst['confirmed'],1)*100)}'i KB'siz ZATEN DOĞRU yazılmış")
print("  --- KB'nin DÜZELTTİĞİ satırlar (glm hatası -> doğru): ---")
for e in gst["examples"]: print("    ",e)

# OneOCR DİRİLİŞ ile kıyas (aynı KB)
one=rd(T3/"DIRILIS_2014"/"cikis"/"oneocr.txt")
okb,ost=kb_support(one,con)
print(f"\n  [kıyas] OneOCR DİRİLİŞ/çıkış: satır={len(one)} KB-değiştirdi={ost['changed']} teyit={ost['confirmed']}")

# ── 29 master AGREGAT ──────────────────────────────────────────────────────
print(f"\n=== glm-ocr 29-master AGREGAT (KB ne kadar müdahale ediyor) ===")
tot_n=tot_ch=tot_cf=tot_rw=0; per=[]
for f in sorted(GLM.glob("*.txt")):
    L=rd(f)
    if not L: continue
    _,st=kb_support(L,con)
    tot_n+=len(L); tot_ch+=st["changed"]; tot_cf+=st["confirmed"]; tot_rw+=st["raw"]
    per.append((f.stem, len(L), st["changed"], st["confirmed"]))
print(f"  toplam satır={tot_n} | KB-değiştirdi={tot_ch} ({round(tot_ch/max(tot_n,1)*100,1)}%) | KB-teyit={tot_cf} | eşleşme-yok={tot_rw}")
print(f"  -> KB yalnız %{round(tot_ch/max(tot_n,1)*100,1)} satıra dokundu; notable-eşleşenlerin %{round(tot_cf/max(tot_ch+tot_cf,1)*100)}'i KB'siz doğruymuş")
print("  --- en çok KB-düzeltme gereken filmler ---")
for stem,n,ch,cf in sorted(per,key=lambda x:-x[2])[:8]:
    print(f"    {stem:28} satır={n:4} KB-değiştirdi={ch:3} teyit={cf:3}")
con.close()
