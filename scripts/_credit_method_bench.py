#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Künye okuma YÖNTEMLERİ head-to-head: credit_parse (deterministik) vs LLM-metin-rol-eşleme (model'ler).
OneOCR+GLM kunye.txt'i girdi alır; yönetmen + cast'i karşılaştırır. GT (bildiğim) ile skor.
Kullanım: _credit_method_bench.py --models qwen3:8b,gemma3:12b
"""
import argparse, glob, json, os, sys, time
sys.path.insert(0, r"E:\MITAS\OCR-worktree\pdf-mitas")
sys.path.insert(0, r"E:\MITAS\scripts")
import credit_parse as cp
import credit_text_read as ctr

DB = r"E:\MITAS\Database"
# (klasör, başlık, GT-yönetmen-soyad[None=metinde-yok-beklenir], GT-cast-soyadları)
GT = [
  ("evoArcadmin_S_NEMA_F_LM4_2017-1054-1-0000-90-1-K_T__EVLAT","KÖTÜ EVLAT",["hathaway"],["wayne","martin","anderson","holliman","kennedy","gregory","fix","slate"]),
  ("evoArcadmin_COZUMLEMEV2S18_1985-0179-1-0000-00-1-UYARI__ARET","UYARI İŞARETİ",[],["waterston","quinlan","kotto","demunn","dysart","bailey","hardin","rossovich","paulin","raz"]),
  ("evoArcadmin_COZUMLEMEV2S21_1997-0199-1-0000-00-1-YALANCI_YALANCI","YALANCI YALANCI",["shadyac"],["carrey","tierney","cooper","tilly","donohoe","haney"]),
  ("evoArcadmin_S_NEMA_F_LM3_2023-1121-1-0000-73-1-SAYGIN_VATANDA","SAYGIN VATANDAŞ",["duprat","cohn"],["martinez","frigerio"]),
  ("evoArcadmin_COZUMLEMEV2S30_1960-0032-1-0000-00-1-B_R_DAHA_DENEYEL_M","BİR DAHA DENEYELİM",["donen"],["brynner","kendall"]),
  ("evoArcadmin_S_NEMA_F_LM3_2011-1127-1-0000-50-0-DEM_R_LEYD","DEMİR LEYDİ",["lloyd"],["streep","broadbent"]),
  ("evoArcadmin_S_NEMA_F_LM3_2011-2205-1-0000-50-1-MOBY_DICK_1","MOBY DICK",["barker"],["hurt","hawke","sutherland","anderson"]),
  ("evoArcadmin_S_NEMA_F_LM3_2025-1286-1-0000-50-0-KATWE_KRAL_ES","KATWE KRALİÇESİ",["nair"],["oyelowo","nyong","nalwanga"]),
  ("evoArcadmin_S_NEMA_F_LM4_2017-1039-1-0000-91-1-STAJYER","STAJYER",["meyers"],["niro","hathaway","russo"]),
  ("evoArcadmin_S_NEMA_F_LM4_2025-1186-1-0000-90-1-K_TAP_KURDU_2","KİTAP KURDU 2",None,None),
]

def ocr_path(folder):
    g = glob.glob(os.path.join(DB, folder, "ocr", "*", "kunye.txt"))
    return g[0] if g else None

def sur_hit(names, surs):
    """GT soyadlarından kaçı çıktı isimlerinde geçiyor."""
    if not surs: return None
    blob = ctr._fold(" ".join(names))
    return sum(1 for s in surs if s in blob)

def score_dir(dirs, gt):
    if gt is None: return "?"
    blob = ctr._fold(" ".join(dirs))
    if not gt:  # metinde yok beklenir → boş olmalı
        return "✓(boş)" if not dirs else f"✗(boş olmalıydı: {dirs})"
    hit = sum(1 for s in gt if s in blob)
    return f"{hit}/{len(gt)}" + ("✓" if hit==len(gt) else "✗")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--models", default="qwen3:8b"); a=ap.parse_args()
    models = a.models.split(",")
    for folder, title, gtd, gtc in GT:
        p = ocr_path(folder)
        print(f"\n{'='*78}\n{title}   (GT yön={gtd}  cast-soyad={gtc})")
        if not p: print("  OCR YOK"); continue
        lines = open(p, encoding="utf-8", errors="ignore").read().splitlines()
        # credit_parse
        cpc, cpcrew = cp.parse_credits(lines, title, dizi=False)
        cpd = dict(cpcrew).get("Yönetmen", [])
        print(f"  [credit_parse]  YÖN={cpd}  dir-skor={score_dir(cpd,gtd)}")
        print(f"                  CAST={cpc}  cast-hit={sur_hit(cpc,gtc)}/{len(gtc) if gtc else '?'}")
        # LLM modeller
        for m in models:
            t0=time.time()
            try:
                r = ctr.read_credits_from_text(lines, title, m)
            except Exception as e:
                print(f"  [{m}] HATA {e}"); continue
            dt=time.time()-t0
            print(f"  [{m}]  YÖN={r['yonetmen']}  dir-skor={score_dir(r['yonetmen'],gtd)}  ({dt:.0f}s)")
            print(f"  {' '*len(m)}    CAST={r['cast']}  cast-hit={sur_hit(r['cast'],gtc)}/{len(gtc) if gtc else '?'}")

if __name__=="__main__": main()
