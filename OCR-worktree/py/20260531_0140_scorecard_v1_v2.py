"""20260531_0140 — SCORECARD: v1 (tester/) vs v2 (tester_v2/) KIYAS.
Amac: v2 (madde 8 statik cok-kart) hicbir IYI filmi bozmadigini KANITLA.
Her film/seg icin v1+v2 manifest.json okur, run'lari [a,b] ile eslestirir,
master.png md5 + boyut + blok karsilastirir. Verdict + flag uretir.

VERDICT oncelik: BOS=BOS / GERILEME / YENI / AYNI(md5) / SCROLL~ / STATIK+ / AZALDI / FLIP
KRITIK: 'GERILEME' = v1'de icerik vardi v2 kaybetti (qwen-flip ya da bug). Bunu yakala.
"""
import sys, json, glob, hashlib, importlib.util
from pathlib import Path

FP = r"E:\MITAS\OCR-worktree\py\20260530_1744_full_pipeline.py"
spec = importlib.util.spec_from_file_location("fp", FP); fp = importlib.util.module_from_spec(spec)
sys.modules["fp"] = fp; spec.loader.exec_module(fp)
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

V1 = Path(r"E:\MITAS\OCR-worktree\tester")
V2 = Path(r"E:\MITAS\OCR-worktree\tester_v2")
OVERSPLIT_N = 15   # tek statik run bu kadar karta bolunduyse -> asiri-bolme adayi (madde 8.1)

def md5(p):
    try: return hashlib.md5(p.read_bytes()).hexdigest()
    except Exception: return None

def load(base, film, seg):
    m = base/film/seg/"manifest.json"
    if not m.exists(): return None
    try: d = json.loads(m.read_text(encoding="utf-8"))
    except Exception: return None
    d["_mpng"] = base/film/seg/"master.png"
    return d

def run_outcome(r):
    """run kaydini tek-kelime sonuca cevir."""
    if "skip" in r: return f"skip:{r['skip']}"
    k = r.get("kind")
    if k == "scroll": return "scroll"
    if k == "card":  return "card:1"          # v1 statik = 1 kart
    if k == "cards": return f"cards:{r.get('n_cards','?')}" + ("(fb)" if r.get("fallback") else "")
    return "?"

def scroll_h(d):
    """R(scroll) run'larinin toplam blok yuksekligi (manifest 'h' alaninda)."""
    return sum(int(r.get("h",0)) for r in d.get("runs",[]) if r.get("kind")=="scroll")

def compare(film, seg):
    a = load(V1, film, seg); b = load(V2, film, seg)
    v2_exists = (V2/film/seg/"manifest.json").exists()
    if a is None and b is None and not v2_exists: return None
    rec = {"film":film, "seg":seg, "v2_pending": (a is not None and not v2_exists)}
    av = a is not None; bv = b is not None
    am = a["master"] if av else None; bm = b["master"] if bv else None
    rec.update(v1_blocks = a["blocks"] if av else None, v2_blocks = b["blocks"] if bv else None,
               v1_H = (am[1] if am else None), v2_H = (bm[1] if bm else None))
    # run-level eslestirme (dy-split deterministik -> [a,b] ayni)
    flips=[]; static_improved=[]; scroll_runs=0; scroll_match=True
    if av and bv:
        ar = {tuple(r["run"]): r for r in a.get("runs",[])}
        br = {tuple(r["run"]): r for r in b.get("runs",[])}
        for key in sorted(set(ar)|set(br)):
            ra = ar.get(key); rb = br.get(key)
            oa = run_outcome(ra) if ra else "YOK"; ob = run_outcome(rb) if rb else "YOK"
            a_kept = ra is not None and "skip" not in ra
            b_kept = rb is not None and "skip" not in rb
            if a_kept != b_kept:
                flips.append({"run":list(key),"v1":oa,"v2":ob,"dir":("v2-LOST" if a_kept and not b_kept else "v2-GAIN")})
            if (ra and ra.get("kind")=="scroll"):
                scroll_runs += 1
                if not (rb and rb.get("kind")=="scroll" and int(ra.get("h",0))==int(rb.get("h",0))):
                    scroll_match=False
            if (ra and ra.get("kind")=="card" and rb and rb.get("kind")=="cards"):
                nc = rb.get("n_cards",1)
                if nc and nc>1 and not rb.get("fallback"): static_improved.append({"run":list(key),"n":nc})
    rec["flips"]=flips; rec["static_improved"]=static_improved
    rec["scroll_runs"]=scroll_runs; rec["scroll_match"]=scroll_match
    # asiri-bolme adayi: v2 run'larinda n_cards >= OVERSPLIT_N
    rec["oversplit"]=[{"run":r["run"],"n":r["n_cards"]} for r in (b.get("runs",[]) if bv else [])
                      if r.get("kind")=="cards" and (r.get("n_cards") or 0)>=OVERSPLIT_N and not r.get("fallback")]
    h1 = md5(a["_mpng"]) if av else None; h2 = md5(b["_mpng"]) if bv else None
    rec["identical"] = (h1 is not None and h1==h2)
    # VERDICT
    lost = any(f["dir"]=="v2-LOST" for f in flips)
    if rec["v2_pending"]: v="v2-PENDING (kosulmadi)"
    elif not am and not bm: v="BOS=BOS"
    elif am and not bm:   v="!! GERILEME (icerik kayboldu)"
    elif bm and not am:   v="+ YENI (v2 kazandi)"
    elif rec["identical"]: v="AYNI (md5)"
    elif lost and (rec["v2_blocks"] or 0) < (rec["v1_blocks"] or 0): v="!! GERILEME (run dustu)"
    elif static_improved and (rec["v2_blocks"] or 0) >= (rec["v1_blocks"] or 0): v="STATIK+ (kart arti)"
    elif scroll_runs and scroll_match and (rec["v2_blocks"]==rec["v1_blocks"]): v="SCROLL~ (korundu)"
    elif (rec["v2_blocks"] or 0) > (rec["v1_blocks"] or 0): v="+ blok artti"
    elif (rec["v2_blocks"] or 0) < (rec["v1_blocks"] or 0): v="? AZALDI (kontrol)"
    else: v="~ esit-ish"
    rec["verdict"]=v
    return rec

def main():
    meta = json.loads(Path(fp.META).read_text(encoding="utf-8"))
    idx2name = {int(it["idx"]): Path(it["path"]).name for it in meta}
    rows=[]
    for idx in sorted(fp.WIN.keys()):
        name = idx2name.get(idx)
        if not name: continue
        film = fp.safe(Path(name).stem)
        for seg in ["giris","cikis"]:
            r = compare(film, seg)
            if r: r["idx"]=idx; rows.append(r)
    out = V2/"_SCORECARD_v1_v2.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    # OZET
    from collections import Counter
    cnt = Counter(r["verdict"] for r in rows)
    print("="*70); print(f"SCORECARD  v1(tester) vs v2(tester_v2)   |  {len(rows)} segment")
    print("="*70)
    for v,c in sorted(cnt.items(), key=lambda x:-x[1]): print(f"  {c:3d}  {v}")
    print("-"*70)
    reg = [r for r in rows if "GERILEME" in r["verdict"]]
    print(f"\n!! GERILEME ({len(reg)}) -- KRITIK, v1'de vardi v2 kaybetti:")
    for r in reg:
        print(f"   {r['film'][:42]:42} {r['seg']:5} v1blk={r['v1_blocks']} v2blk={r['v2_blocks']} flips={r['flips']}")
    azal = [r for r in rows if "AZALDI" in r["verdict"]]
    print(f"\n? AZALDI ({len(azal)}) -- blok dustu, flip yok (scroll-merge olabilir):")
    for r in azal:
        print(f"   {r['film'][:42]:42} {r['seg']:5} v1blk={r['v1_blocks']} v2blk={r['v2_blocks']} v1H={r['v1_H']} v2H={r['v2_H']}")
    imp = [r for r in rows if "STATIK+" in r["verdict"]]
    print(f"\nSTATIK+ ({len(imp)}) -- statik kart zenginlesti (madde 8 kazanci):")
    for r in imp:
        tot=sum(s["n"] for s in r["static_improved"])
        print(f"   {r['film'][:42]:42} {r['seg']:5} v1blk={r['v1_blocks']}->v2blk={r['v2_blocks']} (kart:{[s['n'] for s in r['static_improved']]})")
    over=[r for r in rows if r.get("oversplit")]
    print(f"\n>> ASIRI-BOLME adayi ({len(over)}) -- tek statik run>={OVERSPLIT_N} kart (madde 8.1, gozle bak):")
    for r in over:
        print(f"   {r['film'][:42]:42} {r['seg']:5} {[(o['run'],o['n']) for o in r['oversplit']]}")
    pend=[r for r in rows if r.get("v2_pending")]
    if pend: print(f"\n(v2-PENDING: {len(pend)} segment henuz batch'ten gecmedi -- batch bitince tekrar kos)")
    flipped=[r for r in rows if r["flips"]]
    print(f"\nFLIP olan segment ({len(flipped)}) -- qwen non-determinizm (kazanc/kayip):")
    for r in flipped:
        g=sum(1 for f in r['flips'] if f['dir']=='v2-GAIN'); l=sum(1 for f in r['flips'] if f['dir']=='v2-LOST')
        print(f"   {r['film'][:42]:42} {r['seg']:5} GAIN={g} LOST={l} verdict={r['verdict']}")
    print(f"\n-> {out}")

if __name__=="__main__": main()
