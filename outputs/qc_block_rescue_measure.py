# -*- coding: utf-8 -*-
"""qc_block_rescue_measure.py — SAF-KÜNYE KONTROL filmlerinde QC blok KURTARMA ORANI.

kontrol_analiz_dataset.json'dan yalnız KÜNYE-darboğazlı (özet/ses/ASR/OCR-fail gate'i OLMAYAN)
Kontrol filmlerini seçer; her birinin final .txt alanlarını qc_credit_block'tan geçirir;
kaç film ONAYLI/AUTO-FIX'e kurtuluyor + neden hâlâ KONTROL olduğunu ölçer. Üretime DOKUNMAZ.

Çalıştır: python outputs/qc_block_rescue_measure.py [N]
"""
import os, re, sys, json, glob, importlib.util
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.pop("MITAS_TMDB", None); os.environ.pop("TMDB_API_KEY", None)
import credit_qc_block as q
import credit_crosscheck as cc

# qc_block_ab_batch'ten .txt parse + folder parse'ı yeniden kullan
_spec = importlib.util.spec_from_file_location("ab", os.path.join(HERE, "qc_block_ab_batch.py"))
ab = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ab)

DS = json.load(open(os.path.join(HERE, "kontrol_analiz_dataset.json"), encoding="utf-8"))

# Özet/ses/ASR/OCR-fail gate'i OLMAYAN = saf künye darboğazı
_NONKUNYE = ("özet yok", "qwen: özet", "ses/dil yok", "ana_dil yabancı", "ASR=",
             "SES_MANTIKSIZ", "OCR bucket=BOS", "OCR bucket=ZOR", "qwen: ses")
def _pure_kunye(r):
    return r["karar"] == "Kontrol" and not any(any(s in n for s in _NONKUNYE) for n in r["neden"])

def _primary(r):
    ns = " ".join(r["neden"])
    if "Latin-dışı" in ns or "cast garble" in ns: return "GARBLE/LATIN"
    if "yönetmen okunamadı" in ns or "yönetmen doğrulama" in ns: return "YONETMEN"
    if "kimlik çelişki" in ns: return "KIMLIK_CELISKI"
    if "cast kesişimi 0" in ns: return "CAST_KESISIM0"
    if "versiyon" in ns: return "VERSIYON"
    if "ORTA güven" in ns: return "CAST_ORTA"
    return "DIGER"

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    pure = [r for r in DS if _pure_kunye(r)]
    # blocker-tipine göre tabakalı seç (çeşitlilik)
    by = {}
    for r in pure:
        by.setdefault(_primary(r), []).append(r)
    print(f"Saf-künye KONTROL: {len(pure)} film. Tip dağılımı: "
          f"{ {k: len(v) for k, v in by.items()} }", flush=True)
    sel, i = [], 0
    keys = sorted(by, key=lambda k: -len(by[k]))
    while len(sel) < n and any(by[k] for k in keys):
        k = keys[i % len(keys)]
        if by[k]: sel.append(by[k].pop(0))
        i += 1
        if i > 6 * n: break

    kb = cc.CreditKB()
    res_rows = []
    try:
        for j, r in enumerate(sel):
            folder = r["folder"]
            txts = [p for p in glob.glob(os.path.join(folder, "*.txt")) if not p.endswith("_teknik.txt")]
            if not txts:
                continue
            title, year = ab._parse_folder(os.path.basename(folder))
            try:
                yon, cast, yap, ozet = ab._parse_txt(txts[0])
            except Exception:
                continue
            afis = os.path.join(folder, "afis.jpg")
            print(f"  [{j+1}/{len(sel)}] {title[:38]} ({year}) [{_primary(r)}] ...", flush=True)
            res = q.qc_credit_block(yon, cast, yap, title=title, year=year, ozet=ozet,
                                    afis_yolu=(afis if os.path.exists(afis) else None), kb=kb)
            res_rows.append({"title": title, "year": year, "tip": _primary(r),
                             "qc_karar": res["karar"], "qc_kontrol_tip": res["kontrol_tip"],
                             "kilit": res["kimlik"]["locked"], "yon": res["temiz_yon"],
                             "cast_n": res["floor"]["ulasilan"], "gerekceler": res["gerekceler"]})
            print(f"       → {res['karar']}/{res['kontrol_tip'] or '-'} | kilit={'E' if res['kimlik']['locked'] else 'h'}"
                  f" | yön={res['temiz_yon']} | cast={res['floor']['ulasilan']}", flush=True)
    finally:
        kb.close()

    onayli = [x for x in res_rows if x["qc_karar"] == "ONAYLI"]
    autofix = [x for x in res_rows if x["qc_karar"] == "AUTO-FIX"]
    kontrol = [x for x in res_rows if x["qc_karar"] == "KONTROL"]
    print("\n" + "=" * 90)
    print(f"SAF-KÜNYE KONTROL KURTARMA: {len(res_rows)} film ölçüldü")
    print(f"  → ONAYLI'ya kurtulan:   {len(onayli)}  ({[x['title'] for x in onayli]})")
    print(f"  → AUTO-FIX (afiş eksik): {len(autofix)}  ({[x['title'] for x in autofix]})")
    print(f"  → hâlâ KONTROL:         {len(kontrol)}")
    print(f"  kurtarma oranı (ONAYLI+AUTOFIX): {100*(len(onayli)+len(autofix))//max(1,len(res_rows))}%")
    print(f"  kimlik-kilit oranı: {100*sum(1 for x in res_rows if x['kilit'])//max(1,len(res_rows))}%")
    print("=" * 90)
    json.dump(res_rows, open(os.path.join(HERE, "qc_block_rescue_sonuc.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("JSON: outputs/qc_block_rescue_sonuc.json")

if __name__ == "__main__":
    main()
