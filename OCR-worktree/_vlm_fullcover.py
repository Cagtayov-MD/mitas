"""Çağatay'ın fikri: 30-örnek DEĞİL — TÜM jenerik kareleri yoğun (≈1.5-2sn), 24'er batch, MERGE.
gemma tüm kareleri görür (OneOCR gibi) -> kart kaçırmaz. Recall'i GT'ye karşı ölç."""
import sys, os, glob, json, re, difflib, importlib.util
sys.path.insert(0, r"E:\MITAS\OCR-worktree"); sys.path.insert(0, r"E:\MITAS\OCR-worktree\pdf-mitas")
P = importlib.util.spec_from_file_location("P", r"E:\MITAS\OCR-worktree\_vlm_pipeline.py")
pipe = importlib.util.module_from_spec(P); sys.modules["P"] = pipe; P.loader.exec_module(pipe)
import credit_parse as cp
BENCH = r"E:\QwenModels\ayikla_bench"
GT = json.load(open(os.path.join(BENCH, "gt.json"), encoding="utf-8"))
MAN = json.load(open(os.path.join(BENCH, "manifest.json"), encoding="utf-8"))


def toks(s): return [w for w in re.findall(r"[a-z0-9]+", cp.fold(s)) if len(w) >= 2]


def name_in(name, lines):
    nt = toks(name); n = len(nt)
    if not nt: return False
    for ln in lines:
        lt = toks(ln)
        for s in range(len(lt) - n + 1):
            if all(difflib.SequenceMatcher(None, nt[j], lt[s + j]).ratio() >= 0.85 for j in range(n)): return True
    return False


def dense(arr, k):
    n = len(arr)
    if n <= k: return list(arr)
    st = n / k
    return [arr[int(i * st)] for i in range(k)]


def fullcover(folder, per_seg=int(os.environ.get("MITAS_PERSEG", "48")), bs=24):
    fr = rf"E:\MITAS\Database\{folder}\frames"
    g = sorted(glob.glob(fr + r"\giris\*.png")); c = sorted(glob.glob(fr + r"\cikis\*.png"))
    sel = dense(g, per_seg) + dense(c, per_seg)
    if not sel: return None, [], 0, 0
    batches = [sel[i:i + bs] for i in range(0, len(sel), bs)]
    results = [pipe.gemma_call(b) for b in batches]
    merged = pipe.merge(results)
    names = list(merged["yonetmen"]) + list(merged["oyuncular"]) + [x for r in merged["diger_roller"] for x in r["isimler"]]
    return merged, names, len(sel), len(batches)


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    idx = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else [8]
    print("=== TAM-KAPSAM gemma (yoğun kare + 24-batch + merge) vs GT ===\n")
    tot_gt = tot_hit = tot_hit_old = 0
    for i in idx:
        g, m = GT[i], MAN[i]
        gt_cast = g.get("cast", []); gt_dir = g.get("director", [])
        merged, names, nsel, nb = fullcover(m["folder"])
        if merged is None:
            print(f"[{i}] {g.get('matched_film','?')[:38]} — kare yok"); continue
        ch = sum(name_in(c, names) for c in gt_cast)
        dh = sum(name_in(d, names) for d in gt_dir)
        tot_gt += len(gt_cast); tot_hit += ch
        print(f"[{i:2}] {g.get('matched_film','?')[:40]}")
        print(f"     kare={nsel} ({nb} batch) | gemma {len(names)} isim")
        print(f"     CAST  {ch}/{len(gt_cast)}   YÖNETMEN {dh}/{len(gt_dir)}")
        kacan = [c for c in gt_cast if not name_in(c, names)]
        if kacan: print(f"     kaçan cast: {kacan}")
        print()
    print(f"=== TOPLAM CAST RECALL (tam-kapsam): {tot_hit}/{tot_gt} (%{100*tot_hit//max(1,tot_gt)}) ===")
    print("(kıyas: 36-örnekle KELEBEĞİN 0/8 idi)")
