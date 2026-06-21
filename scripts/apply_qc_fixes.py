#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""apply_qc_fixes.py — QC workflow sonuçlarını _rerender_kunye.py ile uygula.

GÜVENLİ uygulama: DATABASE'e dokunmaz. Her film için TEMP klasöre kunye_teslim.md kopyalar,
PIN'lenmiş corrections.json (mevcut değerler + düzeltme) yazar, _rerender_kunye.py koşar,
oluşan PDF'i export'taki orijinal dosyaya kopyalar.

ÖNEMLİ: _rerender_kunye cast/yonetmen/yapimci/ozet/tur'u SADECE corrections'tan alır (md'den DEĞİL).
Bu yüzden her alan PIN'lenir: final[f] = corrections[f] (varsa) yoksa current[f]. Böylece
düzeltilmeyen alanlar mevcut-temiz halini korur, garble md'ye düşmez.

KULLANIM:
  Kuru çalışma (varsayılan): python apply_qc_fixes.py --results .qc_results.json
  Uygula:                    python apply_qc_fixes.py --results .qc_results.json --apply
  Sadece bazı TRT'ler:       python apply_qc_fixes.py --results .qc_results.json --apply --only 1953-0042,2006-1058
  Durum filtresi:            --status DUZELT  (varsayılan; KONTROL/TEMIZ atlanır)
"""
import argparse, json, os, shutil, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")

ROOT = r"E:\MITAS"
HERE = os.path.dirname(os.path.abspath(__file__))
RERENDER = os.path.join(HERE, "_rerender_kunye.py")
PY = sys.executable  # global python (reportlab burada)
TMP_ROOT = os.path.join(ROOT, ".qc_apply_tmp")
FIELDS = ["cast", "yonetmen", "yapimci", "ozet", "tur"]


def find_db_folder(trt, hint=""):
    # hint yalnızca kunye_teslim.md içeriyorsa güvenilir (dup/yanlış-kasa klasörlerini ele)
    if hint and os.path.isdir(hint) and find_md(hint):
        return hint
    db = os.path.join(ROOT, "DATABASE")
    if not os.path.isdir(db):
        return hint if (hint and os.path.isdir(hint)) else None
    matches = [os.path.join(db, n) for n in os.listdir(db)
               if trt and trt in n and os.path.isdir(os.path.join(db, n))]
    for p in matches:           # md'si OLAN klasörü tercih et
        if find_md(p):
            return p
    if matches:
        return matches[0]
    return hint if (hint and os.path.isdir(hint)) else None


def find_md(db_folder):
    for c in (os.path.join(db_folder, "pdf", "kunye_teslim.md"),
              os.path.join(db_folder, "kunye_teslim.md")):
        if os.path.exists(c):
            return c
    return None


def find_poster(db_folder):
    for c in (os.path.join(db_folder, "pdf", "afis.jpg"),
              os.path.join(db_folder, "afis.jpg")):
        if os.path.exists(c) and os.path.getsize(c) > 5000:
            return c
    return None


def _extract_subtitle(pdf):
    """Mevcut PDF'ten orijinal-dil alt başlığını çıkar (başlık ile ANAHTAR SÖZCÜKLER arası)."""
    try:
        import fitz
    except Exception:
        return None
    if not (pdf and os.path.exists(pdf)):
        return None
    try:
        import re as _re
        doc = fitz.open(pdf)
        lines = [l.strip() for l in doc[0].get_text("text").splitlines() if l.strip()]
        doc.close()
        key = lambda s: _re.sub(r"\s+", "", s).upper()
        fi = None
        for i, l in enumerate(lines):
            if key(l) in ("FİLM", "FILM", "DİZİ", "DIZI"):
                fi = i
                break
        if fi is None or fi + 2 > len(lines):
            return None
        title = lines[fi + 1]
        sub = []
        for l in lines[fi + 2:]:
            if key(l).startswith("ANAHTARSÖZCÜKLER") or key(l).startswith("ANAHTARSOZCUKLER"):
                break
            sub.append(l)
        sub = " ".join(sub).strip()
        if not sub or key(sub) == key(title):
            return None
        return sub
    except Exception:
        return None


def find_original_subtitle(export_path, db_folder):
    """Önce export PDF, sonra DATABASE PDF'lerinden orijinal alt başlığı bul."""
    cands = [export_path, os.path.join(db_folder, "pdf", "kunye.pdf")]
    for n in os.listdir(db_folder):
        if n.lower().endswith(".pdf"):
            cands.append(os.path.join(db_folder, n))
    for c in cands:
        s = _extract_subtitle(c)
        if s:
            return s
    return None


def merge_final(rec):
    cur = rec.get("current") or {}
    cor = rec.get("corrections") or {}
    out = {}
    for f in FIELDS:
        # düzeltme varsa VE boş değilse onu kullan; aksi halde mevcut-temiz değeri PIN'le
        # (boş corrections alanı, mevcut değeri yanlışlıkla SİLMEZ — güvenli taraf)
        cv = cor.get(f)
        if isinstance(cv, str):
            cv = cv.strip()
        v = cv if cv else cur.get(f)
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        if isinstance(v, list) and not v:
            continue
        out[f] = v
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--apply", action="store_true", help="gerçekten yaz (varsayılan kuru çalışma)")
    ap.add_argument("--only", default="", help="virgüllü TRT listesi (sadece bunlar)")
    ap.add_argument("--status", default="DUZELT", help="hangi statü uygulanır (varsayılan DUZELT)")
    a = ap.parse_args()

    results_path = a.results if os.path.isabs(a.results) else os.path.join(ROOT, a.results)
    data = json.load(open(results_path, encoding="utf-8"))
    recs = data.get("results") if isinstance(data, dict) else data
    only = set(x.strip() for x in a.only.split(",") if x.strip())

    os.makedirs(TMP_ROOT, exist_ok=True)
    done, skipped, failed = [], [], []

    for rec in recs:
        trt = rec.get("trt", "").strip()
        title = rec.get("title", "")
        status = rec.get("status", "")
        export_path = rec.get("export_path") or rec.get("_export_path") or ""
        if only and trt not in only:
            continue
        if status != a.status:
            skipped.append((trt, title, f"statü={status}"))
            continue
        final = merge_final(rec)
        if not final:
            skipped.append((trt, title, "düzeltilecek alan yok"))
            continue
        db_folder = find_db_folder(trt, rec.get("db_folder", ""))
        if not db_folder:
            failed.append((trt, title, "DATABASE klasörü yok"))
            continue
        md = find_md(db_folder)
        if not md:
            failed.append((trt, title, "kunye_teslim.md yok"))
            continue
        if not export_path or not os.path.exists(export_path):
            failed.append((trt, title, f"export PDF yok: {export_path}"))
            continue

        poster = find_poster(db_folder)
        if poster:
            final["poster"] = poster
        orig = find_original_subtitle(export_path, db_folder)
        if orig:
            final["original"] = orig
        final["title"] = title

        print(f"\n=== {trt}  {title}  [{status}] ===")
        print(f"  export: {export_path}")
        print(f"  düzeltilen alanlar: {sorted(rec.get('corrections',{}).keys())}")
        for f in FIELDS:
            if f in (rec.get("corrections") or {}):
                print(f"    {f}: {rec['corrections'][f]}")
        if not a.apply:
            continue

        tmp = os.path.join(TMP_ROOT, trt.replace("/", "_"))
        os.makedirs(tmp, exist_ok=True)
        shutil.copy2(md, os.path.join(tmp, "kunye_teslim.md"))
        corr_path = os.path.join(tmp, "corrections.json")
        json.dump(final, open(corr_path, "w", encoding="utf-8"), ensure_ascii=False)
        cmd = [PY, RERENDER, "--folder", tmp, "--data", corr_path]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        out_pdf = os.path.join(tmp, "kunye.pdf")
        if os.path.exists(out_pdf) and os.path.getsize(out_pdf) > 10000:
            shutil.copy2(out_pdf, export_path)
            done.append((trt, title))
            print(f"  ✓ UYGULANDI → {export_path}")
        else:
            failed.append((trt, title, f"render boş; stdout={r.stdout[-200:]} stderr={r.stderr[-200:]}"))
            print(f"  ✗ RENDER BAŞARISIZ")

    print("\n================ ÖZET ================")
    print(f"UYGULANDI: {len(done)} | ATLANDI: {len(skipped)} | BAŞARISIZ: {len(failed)}")
    if failed:
        print("\nBAŞARISIZ:")
        for t, ti, why in failed:
            print(f"  - {t} {ti}: {why}")
    if not a.apply:
        print("\n(KURU ÇALIŞMA — gerçekten yazmak için --apply ekle)")


if __name__ == "__main__":
    main()
