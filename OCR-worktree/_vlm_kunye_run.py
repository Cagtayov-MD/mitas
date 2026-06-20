"""HIBRIT KÜNYE RUNNER — distinkt-kare -> batch gemma -> merge -> konsensüs-net (OneOCR∪Paddle).
Her filme okunur künye .txt yazar. Kullanım:
  python _vlm_kunye_run.py                 # tüm havuz (C:\\Users\\TRT03\\Desktop\\test\\frame-*)
  python _vlm_kunye_run.py "attila marcel" "monte kristo"   # seçili film(ler)
Çıktı: E:\\MITAS\\OCR-worktree\\_KUNYE_HIBRIT\\<film>.txt  + _ozet.json
"""
import sys, os, glob, json, time, importlib.util
sys.path.insert(0, r"E:\MITAS\OCR-worktree")
P = importlib.util.spec_from_file_location("P", r"E:\MITAS\OCR-worktree\_vlm_pipeline.py")
pipe = importlib.util.module_from_spec(P); sys.modules["P"] = pipe; P.loader.exec_module(pipe)

POOL = r"C:\Users\TRT03\Desktop\test"
OUT = r"E:\MITAS\OCR-worktree\_KUNYE_HIBRIT"
os.makedirs(OUT, exist_ok=True)


def write_kunye(film, final, dropped):
    lines = [f"# {film}", ""]
    if final["yonetmen"]:
        lines += ["YÖNETMEN", *[f"  {n}" for n in final["yonetmen"]], ""]
    if final["oyuncular"]:
        lines += ["OYUNCULAR", *[f"  {n}" for n in final["oyuncular"]], ""]
    for rr in final["diger_roller"]:
        lines += [rr["rol"].upper(), *[f"  {n}" for n in rr["isimler"]], ""]
    if dropped:
        lines += ["", "--- ELENEN (hiçbir OCR'da yok = uydurma şüphesi) ---",
                  *[f"  {d}" for d in dropped]]
    path = os.path.join(OUT, film.replace("/", "_")[:60] + ".txt")
    open(path, "w", encoding="utf-8").write("\n".join(lines))
    return path


def cnt(s):
    return len(s["yonetmen"]) + len(s["oyuncular"]) + sum(len(r["isimler"]) for r in s["diger_roller"])


if __name__ == "__main__":
    sel = sys.argv[1:]
    if sel:
        films = sel
    else:
        films = [os.path.basename(d).replace("frame- ", "")
                 for d in sorted(glob.glob(os.path.join(POOL, "frame-*"))) if os.path.isdir(d)]
    summary = []
    t0 = time.time()
    print(f"{len(films)} film -> {OUT}\n", flush=True)
    for film in films:
        try:
            final, dropped, merged = pipe.run_film(film)
            p = write_kunye(film, final, dropped)
            summary.append({"film": film, "final": cnt(final), "elenen": len(dropped)})
            print(f"  -> {os.path.basename(p)}  ({cnt(final)} isim, {len(dropped)} elenen)\n", flush=True)
        except Exception as e:
            import traceback
            print(f"{film} HATA: {repr(e)[:120]}"); traceback.print_exc()
            summary.append({"film": film, "hata": repr(e)[:120]})
    json.dump(summary, open(os.path.join(OUT, "_ozet.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    tot = sum(s.get("final", 0) for s in summary)
    print(f"\n=== BİTTİ: {len(films)} film, {tot} isim, {(time.time()-t0)/60:.0f} dk -> {OUT} ===")
