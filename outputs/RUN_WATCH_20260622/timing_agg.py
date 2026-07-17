#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MITAS zaman profili toplayicisi (SALT-OKUNUR).
Database/*/_log.jsonl dosyalarini tarar, asama sureleri + wall-clock cikarir, ozetler.
"""
import json, os, glob, statistics, sys
from datetime import datetime

DB = r"E:\MITAS\Database"

# durdugu yer: hangi event hangi asamayi temsil eder
DUR_STAGES = [
    ("cozumleme_completed", "decode+credit_detect+frame"),
    ("ocr_completed",       "OCR (paralel ASR ile)"),
    ("asr_completed",       "ASR (paralel OCR ile)"),
    ("credit_text_completed","credit_text (kunye-metin)"),
    ("credit_vl_fallback",  "VL-fallback (gemma4, kosullu)"),
    ("pdf_completed",       "PDF teslim"),
    ("v4_finalize_completed","v4_finalize"),
    ("qwen_final_qc",       "qwen final-QC"),
]

def parse_ts(s):
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None

def analyze(path):
    events = []
    for line in open(path, encoding="utf-8", errors="replace"):
        line=line.strip()
        if not line: continue
        try: e=json.loads(line)
        except: continue
        events.append(e)
    if not events: return None
    rec = {"film": os.path.basename(os.path.dirname(path)), "stages": {}, "meta": {}}
    ts_first = parse_ts(events[0].get("ts",""))
    ts_last  = parse_ts(events[-1].get("ts",""))
    if ts_first and ts_last:
        rec["wall"] = (ts_last - ts_first).total_seconds()
    else:
        rec["wall"] = None
    rec["mtime"] = os.path.getmtime(path)
    # asama sureleri + meta
    for e in events:
        k=e.get("kind",""); d=e.get("duration_seconds")
        det=e.get("detail",{}) or {}
        if k=="cozumleme_completed":
            rec["meta"]["duration"]=det.get("duration")
            rec["meta"]["res"]=det.get("resolution")
            rec["meta"]["giris_frames"]=det.get("giris_frames")
            rec["meta"]["cikis_frames"]=det.get("cikis_frames")
        if k=="asr_completed":
            rec["meta"]["asr_profile"]=det.get("profile_used")
            rec["meta"]["asr_fallback"]=det.get("fallback_triggered")
        if k=="asr_progress" and "dil=" in e.get("summary",""):
            s=e.get("summary","")
            rec["meta"]["asr_dil"]=s.split("dil=")[-1].rstrip(").")
            # ses suresi
            asec=det.get("audio_seconds")
            if asec: rec["meta"]["audio_sec"]=asec
        if k=="ocr_completed":
            rec["meta"]["ocr_engine"]=det.get("engine")
            rec["meta"]["ocr_lines"]=det.get("lines")
            rec["meta"]["ocr_bucket"]=det.get("bucket")
        if d is not None and k in dict(DUR_STAGES):
            rec["stages"][k]=d
    return rec

def main():
    cutoff = float(sys.argv[1]) if len(sys.argv)>1 else 0
    paths = glob.glob(os.path.join(DB,"*","_log.jsonl"))
    recs=[]
    for p in paths:
        if cutoff and os.path.getmtime(p) < cutoff: continue
        r=analyze(p)
        if r: recs.append(r)
    recs.sort(key=lambda r: r["mtime"])
    if not recs:
        print("Kayit yok (cutoff cok yuksek?)"); return

    print(f"=== {len(recs)} film analiz edildi (cutoff={cutoff}) ===\n")
    # asama bazli toplam
    agg={k:[] for k,_ in DUR_STAGES}
    walls=[]; asr_list=[]
    for r in recs:
        if r.get("wall"): walls.append(r["wall"])
        for k,_ in DUR_STAGES:
            if k in r["stages"]: agg[k].append(r["stages"][k])

    def stat(vals):
        if not vals: return "-"
        return f"n={len(vals):3d}  ort={statistics.mean(vals):6.1f}s  med={statistics.median(vals):6.1f}s  max={max(vals):6.1f}s  top={sum(vals):7.0f}s"

    print("ASAMA SURELERI (saniye):")
    for k,label in DUR_STAGES:
        print(f"  {label:34} {stat(agg[k])}")
    print()
    if walls:
        print(f"WALL-CLOCK / film: ort={statistics.mean(walls):.0f}s ({statistics.mean(walls)/60:.1f}dk)  med={statistics.median(walls):.0f}s  min={min(walls):.0f}s  max={max(walls):.0f}s")
    # toplam wall + asama-toplam orani (paralellik kayipsizsa esit olmaz)
    print()

    # ASR detay
    print("ASR PROFIL/DIL dagilimi:")
    from collections import Counter
    prof=Counter(r["meta"].get("asr_profile") for r in recs if r["meta"].get("asr_profile"))
    dil=Counter(r["meta"].get("asr_dil") for r in recs if r["meta"].get("asr_dil"))
    fb=Counter(r["meta"].get("asr_fallback") for r in recs if "asr_fallback" in r["meta"])
    print("  profiller:", dict(prof))
    print("  diller   :", dict(dil))
    print("  fallback :", dict(fb))
    print()

    # VL-fallback ne siklikta tetikleniyor (kosullu agir asama)
    vl_count=sum(1 for r in recs if "credit_vl_fallback" in r["stages"])
    print(f"VL-fallback tetiklenme: {vl_count}/{len(recs)} film ({100*vl_count/len(recs):.0f}%)")
    print()

    # En yavas 8 film (wall)
    print("EN YAVAS 8 FILM (wall-clock):")
    for r in sorted([x for x in recs if x.get('wall')], key=lambda x:-x["wall"])[:8]:
        st=r["stages"]
        big=max(st.items(), key=lambda kv:kv[1]) if st else ("-",0)
        print(f"  {r['wall']:6.0f}s  {r['film'][:42]:42}  film_suresi={r['meta'].get('duration','-')}  enbuyuk_asama={big[0]}({big[1]:.0f}s)")
    print()
    # per-film satir dokumu (son 15)
    print("SON 15 FILM detay (asama saniye):")
    hdr=["coz","ocr","asr","ctext","vlfb","pdf","v4fin","qc"]
    keys=[k for k,_ in DUR_STAGES]
    print("  "+ "  ".join(f"{h:>6}" for h in hdr) + "   wall   film")
    for r in recs[-15:]:
        cells=[]
        for k in keys:
            v=r["stages"].get(k)
            cells.append(f"{v:6.0f}" if v is not None else f"{'-':>6}")
        w=r.get("wall")
        print("  "+"  ".join(cells)+f"  {w:5.0f}  {r['film'][:38]}" if w else "  "+"  ".join(cells))

if __name__=="__main__":
    main()
