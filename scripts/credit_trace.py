# -*- coding: utf-8 -*-
"""KÜNYE İZ — bir filmin künye-verisinin aşama-aşama yolculuğunu gösteren SALT-OKUR araç.

OneOCR → LLM ayıklayıcı → VL yedek → KB/validate cross-check → QC → final künye.
Üretime DOKUNMAZ; yalnız Database/<film>/_log.jsonl + _DURUM.json + _teknik.txt + stitch/ocr_ham.txt okur.

Kullanım:
  python credit_trace.py "TAKIM 2017-1062"          # ad/trt ile (glob)
  python credit_trace.py "Database/TAM KLASÖR ADI"   # tam yol
"""
from __future__ import annotations
import sys, os, io, json, glob, re
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DB = Path(r"E:\MITAS\Database")


def _find_film(arg: str) -> Path | None:
    p = Path(arg)
    if p.is_dir():
        return p
    if (DB / arg).is_dir():
        return DB / arg
    hits = [d for d in DB.iterdir() if d.is_dir() and d.name.startswith(arg)]
    if not hits:
        hits = [d for d in DB.iterdir() if d.is_dir() and arg.lower() in d.name.lower()]
    return sorted(hits, key=lambda d: len(d.name))[0] if hits else None


def _last_events(log: Path) -> dict:
    """Her kind için EN SON olayı tut (en güncel koşu)."""
    out: dict[str, dict] = {}
    if not log.exists():
        return out
    for line in log.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        k = e.get("kind")
        if k:
            out[k] = e
    return out


def _det(ev: dict | None) -> dict:
    d = (ev or {}).get("detail")
    return d if isinstance(d, dict) else {}


def _jl(v) -> str:
    return json.dumps(v, ensure_ascii=False)


def _final_kunye(film: Path) -> dict:
    tk = glob.glob(str(film / "*_teknik.txt"))
    res = {"yonetmen": None, "cast": [], "neden": None}
    if not tk:
        return res
    txt = Path(tk[0]).read_text(encoding="utf-8", errors="replace")
    m = re.search(r"Yönetmen:\s*(.+)", txt)
    if m:
        res["yonetmen"] = m.group(1).strip()
    # OYUNCULAR bloğu (BLOK 2)
    mb = re.search(r"OYUNCULAR\s*\n=+\n(.*?)(?:\n=+|\Z)", txt, re.S)
    if mb:
        res["cast"] = [l.strip() for l in mb.group(1).splitlines() if l.strip()][:8]
    return res


def trace(film: Path) -> None:
    name = film.name
    ev = _last_events(film / "_log.jsonl")
    durum = {}
    if (film / "_DURUM.json").exists():
        try:
            durum = json.loads((film / "_DURUM.json").read_text(encoding="utf-8"))
        except Exception:
            durum = {}

    line = "=" * 70
    print(line)
    print(f"  KÜNYE İZ — {name}")
    print(line)
    print(f"  KARAR : {durum.get('karar','?')}   route={(durum.get('route') or {}).get('tier','?')}")
    if durum.get("neden"):
        print(f"  neden : {durum['neden']}")

    # ADIM 1 — OneOCR
    print("\nADIM 1 — OneOCR (ham okuma)")
    for k in ("credit_detect_opening", "credit_detect_closing", "ocr_completed"):
        if k in ev:
            print(f"  {k:22s}: {(ev[k].get('summary') or '')[:120]}")
    ham = film / "stitch" / "ocr_ham.txt"
    if ham.exists():
        lines = [l.strip() for l in ham.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
        print(f"  ham satır       : {len(lines)}")
        for s in lines[:4]:
            print(f"      | {s[:70]}")
    else:
        print("  (stitch/ocr_ham.txt yok)")

    # ADIM 2 — LLM ayıklayıcı
    print("\nADIM 2 — LLM Ayıklayıcı (credit_text)")
    d = _det(ev.get("credit_text_completed"))
    if d:
        print(f"  yönetmen        : {_jl(d.get('yonetmen'))}")
        print(f"  güven           : {d.get('guven')}")
    else:
        print("  (credit_text_completed olayı yok)")

    # ADIM 3 — VL yedek
    print("\nADIM 3 — VL Yedek (gemma4 vision)")
    if "credit_vl_fallback" in ev:
        d = _det(ev["credit_vl_fallback"])
        print(f"  KOŞTU — yönetmen: {_jl(d.get('yonetmen'))}  cast_supplement={len(d.get('cast_supplement') or [])}")
    else:
        print("  (koşmadı)")

    # ADIM 4 — validate (KB/IMDb/Wiki)
    print("\nADIM 4 — validate (KB / IMDb / Wiki cross-check)")
    d = _det(ev.get("credit_validate"))
    res = d.get("result") if isinstance(d.get("result"), dict) else {}
    yv = res.get("yonetmen") or {}
    cv = res.get("cast") or {}
    kn = res.get("kaynaklar") or {}
    if yv:
        print(f"  yönetmen        : value={_jl(yv.get('value'))}  status={yv.get('status')}  conf={yv.get('confidence')}")
        if yv.get("sources_confirm"):
            print(f"    teyit-kaynak  : {yv['sources_confirm']}")
        if yv.get("conflict_candidates"):
            print(f"    çelişki-aday  : {yv['conflict_candidates']}")
        if yv.get("notes"):
            print(f"    notlar        : {' | '.join(yv['notes'])}")
    cval = cv.get("value") or []
    if cval:
        print(f"  cast (ilk 6)    : {_jl(cval[:6])}")
        if cv.get("notes"):
            print(f"    cast-notlar   : {' | '.join((cv.get('notes') or [])[:3])}")
    if kn:
        im = kn.get("imdb") or {}
        wk = kn.get("wiki") or {}
        print(f"  kaynaklar       : imdb.dir={_jl(im.get('director'))}({im.get('strength')})  "
              f"wiki.dir={_jl(wk.get('director'))}({wk.get('strength')})")
    if not d:
        print("  (credit_validate olayı yok)")

    # ADIM 5 — v4 dolgu (KÖR NOKTA)
    print("\nADIM 5 — v4 dolgu (tek_film_kunye)")
    print("  ⚠ KÖR NOKTA: yon_kaynak + KB-lookup kararı henüz loglanmıyor (instrumentation gerekiyor)")

    # ADIM 6 — QC final
    print("\nADIM 6 — QC final (qwen)")
    qc = _det(ev.get("qwen_final_qc")).get("qwen_qc") or durum.get("qwen_qc") or {}
    if qc:
        print(f"  yonetmen_var={qc.get('yonetmen_var')}  oyuncu={qc.get('oyuncu_sayisi')}  "
              f"yapimci_var={qc.get('yapimci_var')}  afis_var={qc.get('afis_var')}")
    else:
        print("  (qc verisi yok)")

    # SONUÇ
    fk = _final_kunye(film)
    print("\nSONUÇ — final künye (_teknik.txt)")
    print(f"  Yönetmen        : {fk['yonetmen']}")
    if fk["cast"]:
        print(f"  Oyuncular(ilk)  : {_jl(fk['cast'][:6])}")

    # ── SIZINTI DEDEKTÖRÜ ──
    ext_yon = (_det(ev.get("credit_text_completed")).get("yonetmen")) or []
    val_yon = (yv.get("value")) or []
    fin_yon = (fk["yonetmen"] or "").strip()
    fin_empty = (not fin_yon) or fin_yon in ("-", "—", "okunamadı")
    print("\n" + "-" * 70)
    if (not ext_yon) and (not val_yon) and not fin_empty:
        print("  ★ SIZINTI: extractor+validate yönetmen BOŞ ama final DOLU → yönetmen UYDURULMUŞ")
        # cast[0] sızması mı?
        c0 = (cval[0] if cval else (fk["cast"][0] if fk["cast"] else None))
        if c0 and re.sub(r"\W", "", fin_yon.lower()) == re.sub(r"\W", "", c0.lower()):
            print(f"    → KAYNAK: cast[0] ('{c0}') yönetmen alanına sızmış (cast→director leak)")
        else:
            print(f"    → KAYNAK: validate-dışı (v4/KB/XML dolgu) — ADIM 5 kör-noktası. final='{fin_yon}'")
    elif fin_empty and (ext_yon or val_yon):
        print("  ⚠ TERS-KAYIP: OCR/validate yönetmen okudu ama final BOŞ → propagation kaybı")
    else:
        print("  ✓ yönetmen akışı tutarlı (extractor/validate ↔ final)")
    print("-" * 70)


def main(argv):
    if len(argv) < 2:
        print("kullanım: python credit_trace.py <film-adı | trt | yol>")
        return 2
    film = _find_film(argv[1])
    if not film:
        print(f"film bulunamadı: {argv[1]!r}")
        return 1
    trace(film)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
