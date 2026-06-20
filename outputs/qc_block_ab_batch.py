# -*- coding: utf-8 -*-
"""qc_block_ab_batch.py — credit_qc_block GERÇEK-FILM A/B doğrulaması.

Database/ film klasörlerinden ~20 karışık film seçer (eski/yeni/sorunlu/temiz),
her birinin FINAL künye .txt'sinden alanları (yön/cast/yap/özet) + folder'dan yıl +
_DURUM.json'dan MEVCUT kararı okur; credit_qc_block'tan geçirip KARŞILAŞTIRIR.

Amaç: blok gerçek veride ne yapıyor — çöp eliyor mu, eksik dolduruyor mu, kararı
mevcut pipeline'la uyumlu mu (floor/translit ektir). Üretime DOKUNMAZ (salt-okuma).

Çalıştır: python outputs/qc_block_ab_batch.py [N]
"""
import os
import re
import sys
import glob
import json

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.pop("MITAS_TMDB", None)               # batch ağa gitmesin (deterministik)
os.environ.pop("TMDB_API_KEY", None)

import credit_qc_block as q
import credit_crosscheck as cc

DB = os.path.join(ROOT, "Database")
_YEAR_RE = re.compile(r"\s(\d{4})-\d{4}-\d")
_COMPANY_HINT = re.compile(r"\b(TV|INT'L|BVI|WORLD|PRODUCTION|PICTURES|STUDIOS?|MEDIA|FILM(S|İ)?|"
                           r"ENTERTAINMENT|GMBH|LTD|INC|A\.?Ş|YAPIM)\b", re.I)


def _parse_folder(name):
    m = _YEAR_RE.search(name)
    if not m:
        return None, None
    return name[:m.start()].strip(), int(m.group(1))


def _section(txt, baslik):
    """'--- baslik ---' ile sonraki '---' arası satırları döndür."""
    m = re.search(r"---\s*" + re.escape(baslik) + r"\s*---\s*\n(.*?)(?:\n---|\Z)", txt, re.S)
    return m.group(1) if m else ""


def _parse_txt(path):
    txt = open(path, encoding="utf-8").read()
    cast = [ln.strip() for ln in _section(txt, "Oyuncular").splitlines() if ln.strip()]
    ekip = _section(txt, "Yapım Ekibi")
    yon, yap = [], []
    for ln in ekip.splitlines():
        ln = ln.strip()
        m = re.match(r"Yönetmen:\s*(.+)", ln)
        if m and m.group(1).strip() not in ("—", "-", ""):
            yon = [x.strip() for x in re.split(r"[;,]", m.group(1)) if x.strip() not in ("—", "")]
        m = re.match(r"Yapımcı:\s*(.+)", ln)
        if m and m.group(1).strip() not in ("—", "-", ""):
            yap = [x.strip() for x in re.split(r"[;,]", m.group(1)) if x.strip() not in ("—", "")]
    ozet = _section(txt, "Özet").strip()
    return yon, cast, yap, ozet


def _gather():
    rows = []
    for folder in sorted(glob.glob(os.path.join(DB, "*"))):
        if not os.path.isdir(folder):
            continue
        base = os.path.basename(folder)
        title, year = _parse_folder(base)
        if not title:
            continue
        txts = [p for p in glob.glob(os.path.join(folder, "*.txt"))
                if not p.endswith("_teknik.txt")]
        if not txts:
            continue
        try:
            yon, cast, yap, ozet = _parse_txt(txts[0])
        except Exception:
            continue
        durum = {}
        dj = os.path.join(folder, "_DURUM.json")
        if os.path.exists(dj):
            try:
                durum = json.load(open(dj, encoding="utf-8"))
            except Exception:
                durum = {}
        afis = os.path.join(folder, "afis.jpg")
        garbage = any(_COMPANY_HINT.search(c) for c in cast)
        rows.append({
            "title": title, "year": year, "yon": yon, "cast": cast, "yap": yap,
            "ozet": ozet, "afis": afis if os.path.exists(afis) else None,
            "cur_karar": durum.get("karar", "?"), "cur_neden": durum.get("neden", ""),
            "garbage": garbage, "yon_bos": not yon,
        })
    return rows


def _select(rows, n):
    """Çeşitlilik: sorunlu (çöp/yön-boş) + temiz, eski + yeni karışık."""
    problemli = [r for r in rows if r["garbage"] or r["yon_bos"]]
    temiz = [r for r in rows if not (r["garbage"] or r["yon_bos"])]
    eski_p = [r for r in problemli if r["year"] < 2000]
    yeni_p = [r for r in problemli if r["year"] >= 2000]
    eski_t = [r for r in temiz if r["year"] < 2000]
    yeni_t = [r for r in temiz if r["year"] >= 2000]
    out, i = [], 0
    # dönüşümlü seç (çeşitlilik)
    pools = [eski_p, yeni_p, eski_t, yeni_t]
    while len(out) < n and any(pools):
        pool = pools[i % len(pools)]
        if pool:
            out.append(pool.pop(0))
        i += 1
        if i > 4 * n:
            break
    return out[:n]


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    rows = _gather()
    print(f"Database'te {len(rows)} parse-edilebilir film bulundu. {n} seçiliyor...\n")
    sel = _select(rows, n)
    kb = cc.CreditKB()
    out_rows = []
    try:
        for _i, r in enumerate(sel):
            print(f"  [{_i+1}/{len(sel)}] {r['title'][:40]} ({r['year']}) ...", flush=True)
            res = q.qc_credit_block(
                r["yon"], r["cast"], r["yap"],
                title=r["title"], year=r["year"], ozet=r["ozet"], afis_yolu=r["afis"], kb=kb)
            out_rows.append((r, res))
            # INLINE sonuç (timeout olsa bile veri kaybolmasın)
            _k = res["kimlik"]; _fl = res["floor"]
            _drop = [c for c in r["cast"] if not any(cc.fold(c) == cc.fold(t) for t in res["temiz_cast"])]
            print(f"       mevcut={r['cur_karar']} → qc={res['karar']}/{res['kontrol_tip'] or '-'} "
                  f"| kilit={'E' if _k['locked'] else 'h'} cast={len(r['cast'])}→{_fl['ulasilan']} "
                  f"| yön={res['temiz_yon']} | düşen={_drop[:3]}", flush=True)
    finally:
        kb.close()

    # ── RAPOR ──
    line = "=" * 110
    print(line)
    print(f"{'FİLM':<34}{'YIL':<6}{'MEVCUT':<9}{'QC-BLOK':<10}{'TİP':<10}{'KİLİT':<7}{'CAST':<8}")
    print(line)
    for r, res in out_rows:
        k = res["kimlik"]
        floor = res["floor"]
        print(f"{r['title'][:33]:<34}{r['year']:<6}{str(r['cur_karar'])[:8]:<9}"
              f"{res['karar']:<10}{str(res['kontrol_tip'] or '-'):<10}"
              f"{('EVET' if k['locked'] else 'hayır'):<7}"
              f"{str(len(r['cast']))+'→'+str(floor['ulasilan']):<8}")
    print(line)

    # ── DETAY (sorunlu/değişen filmler) ──
    print("\n\n### DETAY — bloğun ne yaptığı (çöp eleme / doldurma / çeviri)\n")
    for r, res in out_rows:
        degisim = []
        if len(r["cast"]) != res["floor"]["ulasilan"]:
            degisim.append(f"cast {len(r['cast'])}→{res['floor']['ulasilan']}")
        if not r["yon"] and res["temiz_yon"]:
            degisim.append(f"yön DOLDU: {res['temiz_yon']}")
        if not r["yap"] and res["temiz_yap"]:
            degisim.append("yapımcı DOLDU")
        dropped = [c for c in r["cast"]
                   if not any(cc.fold(c) == cc.fold(t) or cc.name_match(c, t)
                              for t in res["temiz_cast"])]
        if dropped:
            degisim.append(f"DÜŞEN: {dropped[:4]}")
        if degisim or res["karar"] != "ONAYLI":
            print(f"• {r['title']} ({r['year']}) — mevcut={r['cur_karar']} → qc={res['karar']}/{res['kontrol_tip'] or '-'}")
            if degisim:
                print(f"    {' | '.join(degisim)}")
            if res["gerekceler"]:
                print(f"    gerekçe: {'; '.join(res['gerekceler'][:3])}")

    # ── ÖZET istatistik ──
    print("\n" + line)
    onayli = sum(1 for _, res in out_rows if res["karar"] == "ONAYLI")
    autofix = sum(1 for _, res in out_rows if res["karar"] == "AUTO-FIX")
    kontrol = sum(1 for _, res in out_rows if res["karar"] == "KONTROL")
    locked = sum(1 for _, res in out_rows if res["kimlik"]["locked"])
    filled = sum(1 for r, res in out_rows if len(r["cast"]) < res["floor"]["ulasilan"])
    cleaned = sum(1 for r, res in out_rows
                  if any(not any(cc.fold(c) == cc.fold(t) for t in res["temiz_cast"]) for c in r["cast"]))
    print(f"ÖZET: {len(out_rows)} film | ONAYLI={onayli} AUTO-FIX={autofix} KONTROL={kontrol} | "
          f"kimlik-kilit={locked} | cast-dolduruldu={filled} | çöp-elendi={cleaned}")
    print(line)

    # CSV
    csv_path = os.path.join(HERE, "qc_block_ab_batch_sonuc.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("film;yil;mevcut_karar;qc_karar;qc_tip;kilit;cast_giris;cast_cikis;yon_cikis;gerekce\n")
        for r, res in out_rows:
            f.write(f"{r['title']};{r['year']};{r['cur_karar']};{res['karar']};"
                    f"{res['kontrol_tip'] or ''};{res['kimlik']['locked']};"
                    f"{len(r['cast'])};{res['floor']['ulasilan']};"
                    f"{'|'.join(res['temiz_yon'])};{' / '.join(res['gerekceler'])}\n")
    print(f"\nCSV: {csv_path}")


if __name__ == "__main__":
    main()
