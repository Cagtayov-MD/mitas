#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
kok_neden_triage.py — 14-15 Haziran batch'inde KÖK-NEDEN adli analizi için worklist üretir.

Her film için: final çıktı (yönetmen/yapımcı/cast) + OCR artefakt yolları + ocr_summary
sinyalleri toplanır. Ucuz heuristic'lerle CLEAN vs PROBLEMATIK ayrılır. Problematik filmler
forensic ajanlara (sonnet) verilecek worklist'e yazılır. Heuristic'ler yalnız FLAG'dir —
gerçek kök-neden sınıflandırmasını ajan yapar (false-positive = fazladan ajan, zararsız).
"""
import os, re, glob, json, sys
sys.stdout.reconfigure(encoding="utf-8")

DB = "E:/MITAS/Database"
OUT = "E:/MITAS/outputs/kok_neden_worklist.json"

# Cast/credit gürültü işaretçileri (yapım şirketi, fon, disclaimer, rol-etiketi)
NOISE = re.compile(
    r"(PRODUCTION|PRODUCCION|PRODUKTION|PRODUZIONE|PICTURES|STUDIOS?|ENTERTAINMENT|"
    r"\bMEDIA\b|\bFILMS?\b|CINEMA|DISTRIBUTION|ASSOCIAT|PARTICIPATION|\bAVEC\b|"
    r"EN ASSOCI|CON IL|CON LA|COURTESY|LOTTERY|EURIMAGES|\bCNC\b|\bREGION\b|MINISTR|"
    r"COPYRIGHT|©|ALL RIGHTS|PROTECTED|PRESENTS?\b|COLLABORATION|SUPPORTED BY|"
    r"WITH THE|THE END|\bSTARRING\b|\bCAST\b|MUSIC BY|\bEDITOR\b|PHOTOGRAPHY|\bEPK\b|"
    r"\bGMBH\b|\bS\.?R\.?L\b|\bLLC\b|\bINC\b|FOUNDATION|FONDS|\bSOUND\b|VISUAL EFFECT|"
    r"ANIMATION|GLOBAL|PRODUH|DIRECTOR OF|ART DIRECT|ASSISTANT|SUPERVIS|TELEVISION|"
    r"\bFILM FUND\b|\bSCREEN\b|FINANCE|PAYROLL|PERFORM|ARRANGED|RENTAL|LIGHTING)",
    re.I,
)

def field(label, text):
    m = re.search(rf"{label}:\s*(.+)", text)
    return m.group(1).strip() if m else ""

def looks_garble(name):
    """İsim garble mi? (sesli-harf oranı çok düşük / token çoğunluğu okunamaz)"""
    s = re.sub(r"[^A-Za-zÇĞİÖŞÜçğıöşü]", "", name)
    if len(s) < 3:
        return True
    vowels = sum(1 for c in s.lower() if c in "aeiouàáâäèéêëìíîïòóôöùúûüıİ")
    return (vowels / len(s)) < 0.18

def parse_film(d):
    p = os.path.join(DB, d)
    if not os.path.isdir(p):
        return None
    txts = [f for f in os.listdir(p) if f.endswith(".txt") and "teknik" not in f]
    if not txts:
        return None
    final_txt = os.path.join(p, txts[0])
    try:
        raw = open(final_txt, encoding="utf-8", errors="replace").read()
    except Exception:
        return None

    m = re.search(r"retim:\s*([\d\.]+)\s*[·•]\s*(.+)", raw)
    if not m:
        return None
    tarih, saat = m.group(1).strip(), m.group(2).strip()
    if "15.06" not in tarih and "14.06" not in tarih:
        return None

    trt = field("ID", raw) or (re.search(r"\b(\d{4}-\d{4}-\d-\d{4}-\d{2}-\d)\b", d) or [None,""])[0] \
        if False else field("ID", raw)
    if not trt:
        mm = re.search(r"(\d{4}-\d{4,5}-\d-\d{4}-\d{2}-\d)", d)
        trt = mm.group(1) if mm else d

    director = field("Yönetmen", raw)
    producer = field("Yapımcı", raw)
    ana_dil = field("Ana dil", raw)
    altyazi = field("Altyazı", raw)
    tur = field("Tür", raw)
    sure = field("Süre", raw)
    karar = field("Durum", raw)

    mo = re.search(r"--- Oyuncular ---\n(.*?)(?=\n---)", raw, re.DOTALL)
    cast = []
    if mo:
        cast = [l.strip().lstrip("-").strip() for l in mo.group(1).splitlines()
                if l.strip() and l.strip() != "-"]

    # OCR artefaktları
    ocrdirs = sorted(glob.glob(os.path.join(p, "ocr", "ocr-*")))
    ocr_dir = ocrdirs[0] if ocrdirs else None
    has = {}
    summ = {}
    if ocr_dir:
        for fn in ["kunye.txt", "paddle_kunye.txt", "paddle_status.txt",
                   "ocr_raw_all.txt", "ocr_ham.txt", "ocr_summary.json"]:
            has[fn] = os.path.exists(os.path.join(ocr_dir, fn))
        sp = os.path.join(ocr_dir, "ocr_summary.json")
        if os.path.exists(sp):
            try:
                sj = json.load(open(sp, encoding="utf-8"))
                summ = {k: sj.get(k) for k in
                        ["engine", "bucket", "garble_frac", "credit_frames",
                         "kunye_line_count", "raw_line_count", "diegetik_frac",
                         "glm_used", "frame_count", "stitched_lines", "master_lines_count"]}
            except Exception:
                pass

    # DEFECT FLAGS (heuristic)
    flags = []
    d_empty = (not director) or director.strip() in ("—", "-")
    p_empty = (not producer) or producer.strip() in ("—", "-")
    d_noise = bool(director) and bool(NOISE.search(director))
    d_over = bool(director) and len([x for x in re.split(r"[,/&]", director) if x.strip()]) > 2
    p_noise = bool(producer) and bool(NOISE.search(producer))
    cast_noise = [c for c in cast if NOISE.search(c)]
    cast_garble = [c for c in cast if looks_garble(c)]
    cast_low = len(cast) < 3

    if d_empty: flags.append("YONETMEN_BOS")
    if d_noise: flags.append("YONETMEN_GURULTU")
    if d_over:  flags.append("YONETMEN_FAZLA_ISIM")
    if p_empty: flags.append("YAPIMCI_BOS")
    if p_noise: flags.append("YAPIMCI_GURULTU")
    if cast_noise: flags.append(f"CAST_GURULTU({len(cast_noise)})")
    if cast_garble: flags.append(f"CAST_GARBLE({len(cast_garble)})")
    if cast_low: flags.append("CAST_AZ")

    problematic = bool(flags)

    return {
        "trt": trt, "film": d, "tarih": tarih, "saat": saat,
        "tur": tur, "sure": sure, "ana_dil": ana_dil, "altyazi": altyazi, "karar": karar,
        "final_txt": final_txt,
        "ocr_dir": ocr_dir,
        "has": has, "ocr_summary": summ,
        "out_director": director or "—",
        "out_producer": producer or "—",
        "out_cast": cast[:15],
        "cast_count": len(cast),
        "defect_flags": flags,
        "problematic": problematic,
    }


def main():
    all_films, problem = [], []
    for d in sorted(os.listdir(DB)):
        r = parse_film(d)
        if r is None:
            continue
        all_films.append(r)
        if r["problematic"]:
            problem.append(r)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(problem, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # Özet istatistik
    from collections import Counter
    flag_cnt = Counter()
    for r in problem:
        for f in r["defect_flags"]:
            flag_cnt[re.sub(r"\(\d+\)", "", f)] += 1

    print(f"Toplam 14-15 Haziran film : {len(all_films)}")
    print(f"  CLEAN (sorunsuz)         : {len(all_films)-len(problem)}")
    print(f"  PROBLEMATIK (ajan gider) : {len(problem)}")
    print(f"Worklist  : {OUT}")
    print("\n--- Defect flag dağılımı ---")
    for k, v in flag_cnt.most_common():
        print(f"  {k:28s}: {v}")
    no_ocr = [r for r in problem if not r["ocr_dir"]]
    if no_ocr:
        print(f"\nUYARI: {len(no_ocr)} problematik filmde ocr_dir yok (ajan sınırlı bakar)")


if __name__ == "__main__":
    main()
