"""20260531_0320 — DOGRULAMA: v3 (native-res) vs v2. KANUN gereci batch sonrasi.
Beklenti: kaynak<=480 -> md5 BIREBIR (regresyon yok) ; kaynak>480 (720p) -> ~1.5x boyut + AYNI blok sayisi.
Ihlal = regresyon -> isaretle.
"""
import sys, json, hashlib, importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location("fp",r"E:\MITAS\OCR-worktree\py\20260530_1744_full_pipeline.py")
fp=importlib.util.module_from_spec(spec); sys.modules["fp"]=fp; spec.loader.exec_module(fp)
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
V2=Path(r"E:\MITAS\OCR-worktree\tester_v2"); V3=Path(r"E:\MITAS\OCR-worktree\tester_v3")
res={r[0]:r[2] for r in json.loads((V2/"_source_res.json").read_text(encoding="utf-8"))}  # idx->src_height
meta=json.loads(Path(fp.META).read_text(encoding="utf-8")); idx2name={int(it["idx"]):Path(it["path"]).name for it in meta}

def md5(p): return hashlib.md5(p.read_bytes()).hexdigest() if p.exists() else None
def dims(man):
    if not man.exists(): return None,None
    d=json.loads(man.read_text(encoding="utf-8")); m=d.get("master"); return d.get("blocks"),(m[1] if m else None)

ok_id=0; viol=[]; sharp=[]; missing=[]
for idx in sorted(fp.WIN):
    name=idx2name.get(idx);
    if not name: continue
    film=fp.safe(Path(name).stem); h=res.get(idx,0)
    for seg in ["giris","cikis"]:
        m2=V2/film/seg/"master.png"; m3=V3/film/seg/"master.png"
        man2=V2/film/seg/"manifest.json"; man3=V3/film/seg/"manifest.json"
        if not man3.exists():
            if man2.exists(): missing.append(f"{film[:34]}/{seg} (v2 var, v3 YOK)")
            continue
        b2,h2=dims(man2); b3,h3=dims(man3)
        if h<=480:   # 480p/288p -> BIREBIR olmali
            if md5(m2)==md5(m3) and md5(m3) is not None: ok_id+=1
            elif b2 is None and b3 is None: ok_id+=1   # ikisi de bos
            else: viol.append(f"!! {film[:36]}/{seg} src={h}p v2!=v3 (b {b2}->{b3}, H {h2}->{h3})")
        else:        # 720p -> ~1.5x + ayni blok
            r=(h3/h2) if (h2 and h3) else 0
            same_b=(b2==b3)
            if same_b and 1.35<=r<=1.65: sharp.append(f"OK {film[:30]}/{seg} {h}p blok={b3} H {h2}->{h3} ({r:.2f}x)")
            else: viol.append(f"?? {film[:36]}/{seg} src={h}p blok {b2}->{b3} H {h2}->{h3} oran={r:.2f} (beklenen ~1.5x + ayni blok)")

print("="*64); print(f"v2 -> v3 DOGRULAMA")
print(f"  480p/288p BIREBIR ozdes: {ok_id}")
print(f"  720p keskinlesti (1.5x + ayni blok): {len(sharp)}")
print(f"  IHLAL/incele: {len(viol)} | v3-eksik: {len(missing)}")
print("="*64)
if viol:
    print("\n!! IHLAL (regresyon adayi):")
    for v in viol: print("  ",v)
if missing:
    print("\nv3-EKSIK:")
    for m in missing: print("  ",m)
print("\n720p ornekleri:")
for s in sharp[:12]: print("  ",s)
