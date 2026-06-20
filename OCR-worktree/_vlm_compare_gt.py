"""GERÇEK TEST — head-to-head: PRODUCTION künye vs HİBRİT künye, web-GT'ye karşı.
GT kaynağı: E:\\QwenModels\\ayikla_bench\\gt.json (20 film, web-doğrulanmış director+cast).
Production künye: manifest.json -> kunye.txt. Hibrit: Database frames -> gemma+OneOCR-net.
Eşleştirme: ad+soyad BİTİŞİK (token-ardışık, fuzzy>=0.85) — yanlış-pozitif tuzağına karşı.

Kullanım:  python _vlm_compare_gt.py            # 20 film hepsi
           python _vlm_compare_gt.py 0 3 7     # sadece bu indeksler (hızlı)
Çıktı: _vlm_compare_gt_results.json + _vlm_compare_gt_REPORT.txt
"""
import sys, os, json, glob, re, difflib, importlib.util
sys.path.insert(0, r"E:\MITAS\OCR-worktree")
sys.path.insert(0, r"E:\MITAS\OCR-worktree\pdf-mitas")
P = importlib.util.spec_from_file_location("P", r"E:\MITAS\OCR-worktree\_vlm_pipeline.py")
pipe = importlib.util.module_from_spec(P); sys.modules["P"] = pipe; P.loader.exec_module(pipe)
import credit_parse as cp

BENCH = r"E:\QwenModels\ayikla_bench"
GT = json.load(open(os.path.join(BENCH, "gt.json"), encoding="utf-8"))
MAN = json.load(open(os.path.join(BENCH, "manifest.json"), encoding="utf-8"))


def toks(s):
    return [w for w in re.findall(r"[a-z0-9]+", cp.fold(s)) if len(w) >= 2]


def name_in(name, lines):
    """ad+soyad BİTİŞİK eşleşmesi: isim token'ları bir satırda ardışık + her token fuzzy>=0.85."""
    nt = toks(name); n = len(nt)
    if not nt:
        return False
    for ln in lines:
        lt = toks(ln)
        for s in range(len(lt) - n + 1):
            if all(difflib.SequenceMatcher(None, nt[j], lt[s + j]).ratio() >= 0.85 for j in range(n)):
                return True
    return False


def hybrid_names(folder):
    fr = rf"E:\MITAS\Database\{folder}\frames"
    g = sorted(glob.glob(fr + r"\giris\*.png")); c = sorted(glob.glob(fr + r"\cikis\*.png"))

    def samp(arr, k):
        nn = len(arr)
        return [arr[int(nn * i / (k + 1))] for i in range(1, k + 1)] if nn >= k else list(arr)
    # giris ön-yüklü (cast kartları açılış başında yoğun) + cikis even — daha geniş kapsam
    gfront = [g[int(len(g) * f)] for f in (0.02, 0.05, 0.09, 0.14) if g]
    sel = sorted(set(gfront + samp(g, 16) + samp(c, 16)))
    sel = [x for x in sel if x]
    if not sel:
        return {"yonetmen": [], "oyuncular": [], "diger_roller": []}, [], 0
    batches = [sel[i:i + 6] for i in range(0, len(sel), 6)]
    results = [pipe.gemma_call(b) for b in batches]
    merged = pipe.merge(results)
    ol = pipe.ocr_lines(sel)
    final, dropped = pipe.ocr_net(json.loads(json.dumps(merged)), ol)
    names = list(final["yonetmen"]) + list(final["oyuncular"])
    for rr in final["diger_roller"]:
        names += rr["isimler"]
    return final, names, len(sel)


if __name__ == "__main__":
    idx = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else list(range(len(GT)))
    rows = []
    rep = open(os.path.join(r"E:\MITAS\OCR-worktree", "_vlm_compare_gt_REPORT.txt"), "w", encoding="utf-8")

    def w(s=""):
        print(s.encode("ascii", "replace").decode()); rep.write(s + "\n"); rep.flush()

    w("=== GERCEK TEST: PRODUCTION vs HIBRIT (web-GT'ye karsi) ===\n")
    for i in idx:
        g, m = GT[i], MAN[i]
        gt_dir = g.get("director", []); gt_cast = g.get("cast", [])
        try:
            prod = open(m["kunye"], encoding="utf-8", errors="ignore").read().splitlines()
        except Exception:
            prod = []
        try:
            final, hyb, nsel = hybrid_names(m["folder"])
        except Exception as e:
            w(f"[{i}] {g.get('matched_film','?')[:40]} HIBRIT HATA: {repr(e)[:80]}"); continue

        pd = sum(name_in(d, prod) for d in gt_dir); hd = sum(name_in(d, hyb) for d in gt_dir)
        pc = sum(name_in(c, prod) for c in gt_cast); hc = sum(name_in(c, hyb) for c in gt_cast)
        nd, nc = max(1, len(gt_dir)), max(1, len(gt_cast))
        row = {"i": i, "film": g.get("matched_film", "?"), "gt_dir": len(gt_dir), "gt_cast": len(gt_cast),
               "prod_dir": pd, "hyb_dir": hd, "prod_cast": pc, "hyb_cast": hc,
               "hyb_isim": len(hyb), "nsel": nsel,
               "cast_kacti_prod": [c for c in gt_cast if not name_in(c, prod)],
               "cast_kacti_hyb": [c for c in gt_cast if not name_in(c, hyb)]}
        rows.append(row)
        w(f"[{i:2}] {g.get('matched_film','?')[:42]}")
        w(f"     YONETMEN  GT={len(gt_dir)}  prod={pd}  HIBRIT={hd}")
        w(f"     CAST      GT={len(gt_cast)}  prod={pc}/{len(gt_cast)}  HIBRIT={hc}/{len(gt_cast)}   (hibrit toplam {len(hyb)} isim, {nsel} kare)")
        w("")

    # aggregate
    if rows:
        TD = sum(r["gt_dir"] for r in rows); TC = sum(r["gt_cast"] for r in rows)
        w("=== TOPLAM ===")
        w(f"YONETMEN GT={TD}: production={sum(r['prod_dir'] for r in rows)}  HIBRIT={sum(r['hyb_dir'] for r in rows)}")
        w(f"CAST     GT={TC}: production={sum(r['prod_cast'] for r in rows)} (%{100*sum(r['prod_cast'] for r in rows)//max(1,TC)})  "
          f"HIBRIT={sum(r['hyb_cast'] for r in rows)} (%{100*sum(r['hyb_cast'] for r in rows)//max(1,TC)})")
        w(f"\n-> KAZANC: hibrit, GT-cast'in production'dan {sum(r['hyb_cast'] for r in rows)-sum(r['prod_cast'] for r in rows):+d} fazlasini yakaladi")
    json.dump(rows, open(r"E:\MITAS\OCR-worktree\_vlm_compare_gt_results.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    rep.close()
    print("\n-> _vlm_compare_gt_REPORT.txt + _vlm_compare_gt_results.json")
