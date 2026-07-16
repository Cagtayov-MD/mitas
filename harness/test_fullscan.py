# -*- coding: utf-8 -*-
"""test_fullscan.py — GPT fikri testi: greedy-backward-stop yerine TAM-PENCERE tarama + en-erken
sürdürülen kredi bölgesi. ATTİLA'yı çözer mi + kontrolleri (SON_METRO/KIZGIN/CENNETİN) bozar mı?

Kredi bölgesi = kredi örnekleri + küçük-boşluk toleransı (GAP). En-erken sürdürülen bölge
(>=MIN_SUS kredi örneği) başlangıcı seçilir. GPT'nin 'no separate earlier candidate' + coarse
full-coverage prensibi.
"""
import sys, glob, os, json
sys.path.insert(0,"/opt/mitas/scripts")
from pathlib import Path
import credit_start_vlm as cvlm

RUN="/opt/mitas/candidate_runs/kunye51_20260714"
STRIDE=16          # tam-pencere coarse tarama adımı
GAP=3              # bölge içinde bu kadar ardışık non-credit örnek = boşluk-köprü (logo/diegetik-kart)
MIN_SUS=3          # sürdürülen bölge için min kredi örneği

FILMS={
 "ATTİLA_MARCEL":545, "SON_METRO":772, "KIZGIN_SİLAH":None, "CENNETİN":728,
}

def credit_regions(labels_sorted):
    """labels_sorted: [(idx,label)] artan idx. Kredi bölgelerini boşluk-toleransıyla bul."""
    regions=[]; cur=None; gap=0; ncred=0
    for idx,lab in labels_sorted:
        c = cvlm._is_credit(lab)
        if c:
            if cur is None: cur=[idx,idx]; ncred=1; gap=0
            else: cur[1]=idx; ncred+=1; gap=0
        elif lab=="BLANK":
            if cur is not None: cur[1]=idx    # blank köprü
        else:
            if cur is not None:
                gap+=1
                if gap>GAP:
                    regions.append((cur[0],cur[1],ncred)); cur=None; gap=0; ncred=0
    if cur is not None: regions.append((cur[0],cur[1],ncred))
    return [r for r in regions if r[2]>=MIN_SUS]

for name,truth in FILMS.items():
    cd=[d for d in glob.glob(f"{RUN}/Database/*") if name in os.path.basename(d)]
    if not cd: print(f"{name}: YOK"); continue
    full=sorted(Path(cd[0],"frames","cikis").glob("*.png"))
    n=len(full)
    samples=sorted(set(list(range(0,n,STRIDE))+[n-1]))
    labs=[(i, cvlm.classify(full[i])[0]) for i in samples]
    regs=credit_regions(labs)
    earliest = regs[0][0] if regs else None
    ok = "✅" if (truth is None and not regs) or (truth is not None and earliest is not None and abs(earliest-truth)<=20) else "❌"
    print(f"{ok} {name:>16} | truth={truth} | tam-tarama en-erken-bölge={earliest} | tüm bölgeler={regs}", flush=True)
