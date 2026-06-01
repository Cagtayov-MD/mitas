"""footage-gate metrik DOĞRULAMA: credit_text_score — yapısal yatay yazı-satırı sayısı.
Kredi karesi (yazı-satırları) yüksek; footage (rastgele doku) düşük çıkmalı.
ACEMİLER exit_frames (600) üzerinde skor dağılımı + en yüksek/düşük kareleri işaretle.
"""
import sys, glob, importlib.util
import numpy as np, cv2
sys.stdout.reconfigure(encoding="utf-8")
spec=importlib.util.spec_from_file_location("fp",r"E:\MITAS\OCR-worktree\py\20260530_1744_full_pipeline.py")
fp=importlib.util.module_from_spec(spec); sys.modules["fp"]=fp; spec.loader.exec_module(fp)

def credit_text_score(g):
    """yatay yazı-satırı sayısı: yazı-bileşenlerini satırlara grupla, çok-bileşenli/geniş satırları say."""
    m=fp.tophat(g)                                  # parlak yazı maskesi (bright-on-dark)
    md=cv2.dilate(m,np.ones((3,3),np.uint8))
    n,lab,st,_=cv2.connectedComponentsWithStats(md,8)
    H,W=g.shape; comps=[]
    for i in range(1,n):
        x,y,w,h,area=st[i]
        if 7<=h<=60 and w>=16 and 1.2<=w/max(h,1)<=30 and area>=35:   # yazı-benzeri şekil
            comps.append((y+h/2.0,h,x,w))
    if not comps: return 0,0
    comps.sort()
    rows=[]; cur=[comps[0]]
    for c in comps[1:]:
        if abs(c[0]-cur[-1][0])<=max(9,cur[-1][1]*0.8): cur.append(c)
        else: rows.append(cur); cur=[c]
    rows.append(cur)
    # yazı-satırı = >=2 bileşen YA DA 1 geniş bileşen (>=%14 genişlik)
    text_rows=sum(1 for r in rows if len(r)>=2 or any(c[3]>=W*0.14 for c in r))
    return text_rows, len(comps)

films=[("ACEMİLER","F:/REPO_GitHub/DATABASE/ACEMİLER ÇETESİ 1974-0205-1-0000-90-1"),
       ("ACI_ÇİKOLATA","F:/REPO_GitHub/DATABASE/ACI ÇİKOLATA 1992-0478-1-0000-00-1")]
for nm,base in films:
    for seg in ["entry_frames","exit_frames"]:
        frs=sorted(glob.glob(f"{base}/{seg}/*.png"))
        if not frs: continue
        scores=[]
        for f in frs:
            g=cv2.cvtColor(fp.rd(f),cv2.COLOR_BGR2GRAY)
            tr,nc=credit_text_score(g); scores.append((tr,f))
        trs=sorted(s[0] for s in scores)
        hi=sum(1 for t,_ in scores if t>=2); mid=sum(1 for t,_ in scores if t==1); lo=sum(1 for t,_ in scores if t==0)
        print(f"{nm}/{seg} ({len(frs)} kare): text_rows>=2 (KREDİ)={hi} | ==1={mid} | ==0 (FOOTAGE)={lo}")
        print(f"   dağılım: min={trs[0]} medyan={trs[len(trs)//2]} max={trs[-1]}")
        # en yüksek + en düşük kare yolunu yaz (gözle kontrol için)
        scores.sort(key=lambda s:-s[0])
        print(f"   EN YÜKSEK skor kare ({scores[0][0]}): {scores[0][1].split(chr(47))[-1]}")
        print(f"   EN DÜŞÜK skor kare ({scores[-1][0]}): {scores[-1][1].split(chr(47))[-1]}")
