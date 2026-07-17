#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Kaynak-telemetri x asama-zaman cizelgesi korelasyonu (SALT-OKUNUR).
res_samples.csv (epoch,cpu,gpu_sm,gpu_mem,pw,disk,net) + Database/*/_log.jsonl asama araliklarini
cakistir -> her asama icin ort CPU/GPU/disk/net + BOS-pencere (GPU idle / CPU idle) sn.

Kullanim:
  python res_correlate.py                # sampler kapsamindaki TUM filmleri otomatik bul + ozetle
  python res_correlate.py "<film klasor adi>"   # tek film detay
"""
import json, os, glob, sys, csv, statistics
from datetime import datetime

ROOT = r"E:\MITAS"
DB = os.path.join(ROOT, "Database")
CSV = os.path.join(ROOT, "outputs", "RUN_WATCH_20260622", "res_samples.csv")
PCSV = os.path.join(ROOT, "outputs", "RUN_WATCH_20260622", "proc_samples.csv")

# asama -> bitis-event eslesmesi (interval = [onceki milestone, bu event])
MILESTONES = [
    ("cozumleme",   "cozumleme_completed"),
    ("OCR_ASR",     "asr_completed"),       # OCR∥ASR join blogu (ASR'da kapanir)
    ("credit_text", "credit_text_completed"),
    ("VL_fallback", "credit_vl_fallback"),
    ("ozet",        "ozet_completed"),
    ("PDF",         "pdf_completed"),
    ("v4_finalize", "v4_finalize_completed"),
    ("qwen_qc",     "qwen_final_qc"),
]
SUBEVENTS = {"ocr_completed", "credit_qc1_red", "credit_validate", "media_imported"}

def parse_ts(s):
    try: return datetime.fromisoformat(s).timestamp()
    except Exception: return None

def load_samples():
    rows = []
    if not os.path.exists(CSV): return rows
    with open(CSV, newline="") as f:
        r = csv.DictReader(f)
        for d in r:
            try:
                rows.append((float(d["epoch_utc"]),
                             float(d.get("cpu_pct") or 0),
                             float(d.get("gpu_sm") or 0),
                             float(d.get("gpu_mem_mb") or 0),
                             float(d.get("gpu_pw_w") or 0),
                             float(d.get("disk_pct") or 0),
                             float(d.get("net_kbps") or 0)))
            except Exception: continue
    rows.sort()
    return rows

def load_proc():
    """proc_samples.csv -> [(epoch, pipe_cpu_pct, n_proc, rss_gb)] (pipeline-agaci, temiz)."""
    rows = []
    if not os.path.exists(PCSV): return rows
    with open(PCSV, newline="") as f:
        r = csv.DictReader(f)
        for d in r:
            try:
                rows.append((float(d["epoch_utc"]),
                             float(d.get("tree_cpu_pct") or 0),
                             int(float(d.get("n_proc") or 0)),
                             float(d.get("tree_rss_gb") or 0)))
            except Exception: continue
    rows.sort()
    return rows

def proc_slice(prows, t0, t1):
    seg=[r for r in prows if t0 <= r[0] <= t1 and r[2] > 0]
    if not seg: return None
    cpu=[r[1] for r in seg]
    return {"pipe_cpu":statistics.mean(cpu),
            "pipe_cpu_idle_frac":sum(1 for v in cpu if v < 10)/len(cpu)}

def film_stages(path):
    """_log.jsonl -> [(stage, t0, t1)] araliklar + meta."""
    evs = []
    for line in open(path, encoding="utf-8", errors="replace"):
        line=line.strip()
        if not line: continue
        try: e=json.loads(line)
        except: continue
        t=parse_ts(e.get("ts",""))
        if t is None: continue
        evs.append((t, e.get("kind",""), e))
    evs.sort()
    if not evs: return None
    t_first = evs[0][0]
    # milestone zamanlari
    mt = {}
    sub = {}
    for t,k,e in evs:
        if k in dict(MILESTONES).values(): mt.setdefault(k, t)
        if k in SUBEVENTS: sub.setdefault(k, t)
    stages=[]
    prev = sub.get("media_imported", t_first)
    for name, ev in MILESTONES:
        if ev in mt:
            stages.append((name, prev, mt[ev]))
            prev = mt[ev]
    return {"stages": stages, "t_first": t_first, "t_last": evs[-1][0], "sub": sub, "mt": mt}

def slice_stats(rows, t0, t1):
    seg=[r for r in rows if t0 <= r[0] <= t1]
    if not seg: return None
    cpu=[r[1] for r in seg]; gsm=[r[2] for r in seg]; mem=[r[3] for r in seg]
    pw=[r[4] for r in seg]; dsk=[r[5] for r in seg]; net=[r[6] for r in seg]
    n=len(seg)
    gpu_idle = sum(1 for v in gsm if v < 5)/n
    cpu_idle = sum(1 for v in cpu if v < 10)/n
    return {"n":n, "dur":t1-t0,
            "cpu":statistics.mean(cpu), "gpu":statistics.mean(gsm),
            "mem":statistics.mean(mem), "pw":statistics.mean(pw),
            "disk":statistics.mean(dsk), "net":statistics.mean(net),
            "gpu_idle_frac":gpu_idle, "cpu_idle_frac":cpu_idle}

def report_film(path, rows, prows, verbose=True):
    fs=film_stages(path)
    if not fs or not fs["stages"]: return None
    name=os.path.basename(os.path.dirname(path))
    # sampler bu filmi kapsiyor mu?
    if rows and (fs["t_last"] < rows[0][0] or fs["t_first"] > rows[-1][0]):
        return None
    out={"film":name,"stages":{}}
    if verbose:
        print(f"\n=== {name} ===")
        print(f"  {'asama':12} {'sure':>6} {'GPU%':>6} {'pipeCPU':>7} {'VRAM':>6} {'W':>5} {'sysCPU':>6} {'disk%':>6}  {'GPUbos':>7} {'pCPUbos':>8}")
    for name_s, t0, t1 in fs["stages"]:
        st=slice_stats(rows, t0, t1)
        if not st:
            if verbose: print(f"  {name_s:12} {t1-t0:6.0f}  (ornek yok)")
            continue
        ps=proc_slice(prows, t0, t1)
        st["pipe_cpu"]=ps["pipe_cpu"] if ps else None
        st["pipe_cpu_idle_frac"]=ps["pipe_cpu_idle_frac"] if ps else None
        out["stages"][name_s]=st
        if verbose:
            pc = f"{st['pipe_cpu']:7.1f}" if st['pipe_cpu'] is not None else f"{'-':>7}"
            pci = f"{st['pipe_cpu_idle_frac']*100:7.0f}%" if st['pipe_cpu_idle_frac'] is not None else f"{'-':>8}"
            print(f"  {name_s:12} {st['dur']:6.0f} {st['gpu']:6.1f} {pc} {st['mem']:6.0f} {st['pw']:5.0f} {st['cpu']:6.1f} {st['disk']:6.1f}  {st['gpu_idle_frac']*100:6.0f}% {pci}")
    return out

def main():
    rows=load_samples()
    prows=load_proc()
    if not rows:
        print("res_samples.csv bos/yok — sampler henuz veri yazmadi."); return
    print(f"Sampler kapsami: {len(rows)} ornek, "
          f"{datetime.fromtimestamp(rows[0][0]).strftime('%H:%M:%S')} – {datetime.fromtimestamp(rows[-1][0]).strftime('%H:%M:%S')} "
          f"({(rows[-1][0]-rows[0][0])/60:.0f} dk) | proc-CPU ornek: {len(prows)}")
    print("  [GPU% & pipeCPU = TEMIZ (izole); sysCPU/disk = es-zamanli QC/ATLAS isiyle KIRLI]")
    if len(sys.argv)>1:
        report_film(os.path.join(DB, sys.argv[1], "_log.jsonl"), rows, prows); return
    # otomatik: sampler penceresinde biten filmler
    paths=glob.glob(os.path.join(DB,"*","_log.jsonl"))
    covered=[]
    for p in paths:
        if os.path.getmtime(p) < rows[0][0]-5: continue
        r=report_film(p, rows, prows, verbose=True)
        if r: covered.append(r)
    if not covered:
        print("\nSampler penceresinde TAM kapsanan film yok (devam ediyor; bir sonraki uyanista dolacak).")
        return
    # toplam idle muhasebesi
    print(f"\n\n##### TOPLAM ({len(covered)} film) — kaynak boslugu muhasebesi #####")
    agg={}
    for r in covered:
        for s,st in r["stages"].items():
            agg.setdefault(s, []).append(st)
    print(f"  {'asama':12} {'ort sure':>8} {'ort CPU%':>9} {'ort GPU%':>9}  {'GPU-bos sn':>11} {'CPU-bos sn':>11}")
    tot_gpu_idle=0; tot_cpu_idle=0; tot_dur=0
    for s,_ in MILESTONES:
        if s not in agg: continue
        lst=agg[s]
        dur=statistics.mean([x["dur"] for x in lst])
        cpu=statistics.mean([x["cpu"] for x in lst])
        gpu=statistics.mean([x["gpu"] for x in lst])
        gpu_idle_s=statistics.mean([x["dur"]*x["gpu_idle_frac"] for x in lst])
        cpu_idle_s=statistics.mean([x["dur"]*x["cpu_idle_frac"] for x in lst])
        tot_gpu_idle+=gpu_idle_s; tot_cpu_idle+=cpu_idle_s; tot_dur+=dur
        print(f"  {s:12} {dur:8.0f} {cpu:9.1f} {gpu:9.1f}  {gpu_idle_s:11.0f} {cpu_idle_s:11.0f}")
    print(f"  {'-'*60}")
    print(f"  {'TOPLAM/film':12} {tot_dur:8.0f} {'':9} {'':9}  {tot_gpu_idle:11.0f} {tot_cpu_idle:11.0f}")
    print(f"\n  => Film basina GPU ~{tot_gpu_idle:.0f}s BOSTA ({100*tot_gpu_idle/tot_dur:.0f}%), CPU ~{tot_cpu_idle:.0f}s BOSTA ({100*tot_cpu_idle/tot_dur:.0f}%)")

if __name__=="__main__":
    main()
