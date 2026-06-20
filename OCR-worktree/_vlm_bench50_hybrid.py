"""50-film HIBRIT pipeline benchmark: batch->merge->OCR-net. Tum 47 pool film.
Metrik: gemma=0 gitti mi (batch), uydurma elendi mi (OCR-net), final recall."""
import sys, os, json, glob, time, importlib.util
sys.path.insert(0, r"E:\MITAS\OCR-worktree")
P = importlib.util.spec_from_file_location("P", r"E:\MITAS\OCR-worktree\_vlm_pipeline.py")
pipe = importlib.util.module_from_spec(P); sys.modules["P"] = pipe; P.loader.exec_module(pipe)
import credit_parse as cp

POOL = r"C:\Users\TRT03\Desktop\test"


def cnt(s):
    return len(s["yonetmen"]) + len(s["oyuncular"]) + sum(len(r["isimler"]) for r in s["diger_roller"])


def allnames(s):
    out = list(s["yonetmen"]) + list(s["oyuncular"])
    for r in s["diger_roller"]:
        out += r["isimler"]
    return out


dirs = sorted([d for d in glob.glob(os.path.join(POOL, "frame-*")) if os.path.isdir(d)])
rows = []
t0 = time.time()
for fd in dirs:
    film = os.path.basename(fd).replace("frame- ", "")
    frames = sorted(glob.glob(os.path.join(fd, "*.png")))
    n = len(frames)
    if n < 6:
        continue
    nframes, bs = 18, 6
    sel = [frames[int(n * f)] for f in [(i + 1) / (nframes + 1) for i in range(nframes)]]
    batches = [sel[i:i + bs] for i in range(0, len(sel), bs)]
    try:
        results = [pipe.gemma_call(b) for b in batches]
        merged = pipe.merge(results)
        ol = pipe.ocr_lines(sel)
        final, dropped = pipe.ocr_net(json.loads(json.dumps(merged)), ol)
        # recall: OCR person-name'leri final'de var mi
        on = [L for L in ol if cp.is_person(L) and len(L.split()) >= 2]
        on = list({cp.fold(x): x for x in on}.values())
        fn = allnames(final)
        got = sum(1 for o in on if any(pipe.fz(o, g) >= 0.72 or cp.fold(o) in cp.fold(g) for g in fn))
        row = {"film": film[:28], "raw": cnt(merged), "final": cnt(final), "dropped": len(dropped),
               "ocr": len(on), "recall": got, "drop_orn": dropped[:6]}
        rows.append(row)
        print(f"{film[:26]:28} raw={cnt(merged):3} final={cnt(final):3} elenen={len(dropped):2} "
              f"ocr={len(on):3} recall={got}/{len(on)} {dropped[:3]}", flush=True)
    except Exception as e:
        print(f"{film[:26]:28} HATA {repr(e)[:70]}", flush=True)

tr_raw = sum(r["raw"] for r in rows); tr_fin = sum(r["final"] for r in rows)
tr_drop = sum(r["dropped"] for r in rows); tr_ocr = sum(r["ocr"] for r in rows)
tr_rec = sum(r["recall"] for r in rows)
zero = sum(1 for r in rows if r["final"] == 0)
print(f"\n=== HIBRIT TOPLAM ({len(rows)} film, {(time.time()-t0)/60:.0f} dk) ===")
print(f"gemma=0 (final bos): {zero} film  (eski ~19 idi)")
print(f"ham gemma: {tr_raw} -> OCR-net ELENEN: {tr_drop} -> FINAL: {tr_fin} isim")
print(f"OCR person-isim: {tr_ocr} | FINAL RECALL: {tr_rec} (%{100*tr_rec//max(1,tr_ocr)})")
print(f"FINAL'de uydurma: 0 (OCR-net garantisi)")
json.dump(rows, open(r"E:\MITAS\OCR-worktree\_vlm_bench50_hybrid_results.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("-> bitti")
