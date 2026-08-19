# -*- coding: utf-8 -*-
"""TOPLAYICI TURU — sadece son adimi olcer, cikarma adimini TEKRAR KOSMAZ.

Bulgu (2026-07-30): parcali hatta darbogaz CIKARMA degil TOPLAMA. 8B dogru olgulari buluyor
(ad-isabet 0.75) ama olay listesini 40 kelimelik yaya sikistiramiyor (kapi 0/6). Ayni listeden
GLM 3/3 gecti → hammadde yeterli, sorun toplayicida.

Bu script kayitli olay listelerini (runs/*/results.json → ara_urun) alir ve YALNIZ nihai ozet
cagrisini farkli modellerde kosturur. Cikarma tekrar kosmadigi icin:
  • cok ucuz (film basina TEK cagri, ~2.6k token girdi)
  • VRAM ihtiyaci dusuk (uzun baglam gerekmiyor)
  • kiyas ADIL: tum modeller AYNI olay listesini gorur, tek degisken toplayici

Kullanim:
  python3 toplayici_turu.py --modeller gemma4:26b,mistral-small3.2:latest
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "eval"))

import graders  # noqa: E402
import motorlar  # noqa: E402

# Toplama isteminin GOVDESI — cikar_ozetle ile BIREBIR ayni (tek degisken model olsun).
TOPLA_ONSOZ = (
    "Aşağıdaki liste, filmin transkriptinden bölüm bölüm çıkarılmış OLAY NOTLARIDIR "
    "(transkriptin kendisi değil). Bölümler filmin ZAMAN SIRASINA göre dizilidir. "
    "Bu notlara dayanarak özeti yaz. Notlarda olmayan hiçbir şey ekleme. Madde madde "
    "değil, akıcı tek paragraf yaz.\n\nOLAY NOTLARI:\n"
)


def tahtalari_topla() -> list[dict]:
    """Onceki kosulardan kayitli olay listelerini (ara_urun) cikar. Film basina EN SON kosu."""
    tahta: dict[str, dict] = {}
    for rj in sorted(glob.glob(str(HERE / "runs" / "*" / "results.json"))):
        d = json.load(open(rj, encoding="utf-8"))
        for r in d.get("sonuc", []):
            if r.get("sekil") == "cikar_ozetle" and r.get("ara_urun"):
                tahta[r["film"]] = {
                    "film": r["film"], "baslik": r["baslik"], "tahta": r["ara_urun"],
                    "referans_sonnet": r["referans_sonnet"],
                    "uretici": d["model"], "onceki_ozet": r["ozet"],
                }
    return list(tahta.values())


def main() -> int:
    a = argparse.ArgumentParser()
    a.add_argument("--modeller", required=True, help="virgülle: gemma4:26b,mistral-small3.2:latest")
    a.add_argument("--uc", default="ollama", choices=["ollama", "vllm"])
    a.add_argument("--num-ctx", type=int, default=8192)   # 2.6k girdi → 8k fazlasıyla yeter
    a.add_argument("--vllm-host", default="http://127.0.0.1:8101/v1")
    p = a.parse_args()

    sistem = open(motorlar.PROMPT_V2, encoding="utf-8").read()
    tahtalar = tahtalari_topla()
    if not tahtalar:
        print("Kayıtlı olay listesi yok — önce cikar_ozetle koşusu gerekir.")
        return 1

    goldens = {json.loads(s)["id"]: json.loads(s)
               for s in (HERE / "eval" / "goldens.jsonl").read_text(encoding="utf-8").splitlines() if s.strip()}

    modeller = [m.strip() for m in p.modeller.split(",") if m.strip()]
    kosu_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-toplayici"
    cikti = HERE / "runs" / kosu_id
    cikti.mkdir(parents=True, exist_ok=True)
    print(f"[toplayıcı] {len(tahtalar)} film × {len(modeller)} model = {len(tahtalar) * len(modeller)} çağrı")
    print(f"[toplayıcı] olay listeleri {tahtalar[0]['uretici']} tarafından üretildi — TEKRAR ÇIKARILMIYOR\n")

    def _ollama_bosalt() -> None:
        """Yuklu ollama modellerini bosalt — 17 GB + 15 GB ayni anda karta SIGMAZ, eviction
        yerine biz bosaltiriz (deterministik, OOM riski yok)."""
        import urllib.request
        try:
            with urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=10) as r:
                yuklu = [x["name"] for x in json.loads(r.read()).get("models", [])]
        except Exception:  # noqa: BLE001
            return
        for y in yuklu:
            try:
                urllib.request.urlopen(urllib.request.Request(
                    "http://127.0.0.1:11434/api/generate",
                    data=json.dumps({"model": y, "keep_alive": 0}).encode(),
                    headers={"Content-Type": "application/json"}), timeout=30).read()
                print(f"   (boşaltıldı: {y})")
            except Exception:  # noqa: BLE001
                pass
        time.sleep(6)

    sonuc = []
    for m in modeller:
        if p.uc == "ollama":
            _ollama_bosalt()
        uc = (motorlar.Ollama(m, num_ctx=p.num_ctx) if p.uc == "ollama"
              else motorlar.VLLM(m, host=p.vllm_host))
        print(f"──── {m}")
        for t in tahtalar:
            kullanici = f"Dosya: {t['baslik']}\nSüre: —\n\n" + TOPLA_ONSOZ + t["tahta"]
            t0 = time.perf_counter()
            try:
                y = uc.uret(sistem, kullanici)
                ozet, sn = y.metin, y.saniye
            except Exception as e:  # noqa: BLE001
                print(f"   {t['baslik'][:34]:34s} HATA {type(e).__name__}")
                sonuc.append({"model": m, "film": t["film"], "hata": str(e)[:200]})
                continue
            tr = Path(goldens[t["film"]]["transcript"]).read_text(encoding="utf-8", errors="ignore")
            n = graders.notla(ozet, t["referans_sonnet"], tr)
            ai = n["b3_olgu"]["ad_isabet"]
            sonuc.append({"model": m, "film": t["film"], "baslik": t["baslik"], "ozet": ozet,
                          "referans_sonnet": t["referans_sonnet"], "saniye": round(sn, 1),
                          "onceki_8b_ozet": t["onceki_ozet"], "notlar": n})
            print(f"   {t['baslik'][:34]:34s} {sn:5.1f}s {n['b1_bicim']['kelime']:>4}kel "
                  f"{'GEÇTİ' if n['b1_bicim']['gecti'] else 'kaldı':>6} "
                  f"dil-{'ok' if n['b2_dil']['gecti'] else 'HATA'} "
                  f"ad {('%.2f' % ai) if ai is not None else ' -- '}")
        print()

    (cikti / "results.json").write_text(
        json.dumps({"kosu_id": kosu_id, "tip": "toplayici", "uc": p.uc, "modeller": modeller,
                    "zaman": datetime.now().isoformat(timespec="seconds"), "sonuc": sonuc},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    print("═" * 62)
    print(f"{'toplayıcı':28s} {'kapı':>7} {'dil':>6} {'ad-isabet':>10} {'ort kel':>8}")
    for m in modeller:
        v = [r for r in sonuc if r.get("model") == m and "ozet" in r]
        if not v:
            print(f"{m:28s}   (çıktı yok)")
            continue
        ai = [r["notlar"]["b3_olgu"]["ad_isabet"] for r in v if r["notlar"]["b3_olgu"]["ad_isabet"] is not None]
        print(f"{m:28s} {sum(1 for r in v if r['notlar']['b1_bicim']['gecti'])}/{len(v):<5} "
              f"{sum(1 for r in v if r['notlar']['b2_dil']['gecti'])}/{len(v):<4} "
              f"{(sum(ai) / len(ai) if ai else 0):>10.2f} "
              f"{sum(r['notlar']['b1_bicim']['kelime'] for r in v) / len(v):>8.0f}")
    print(f"\nkıyas — GLM (bulut, aynı listelerden): kapı 3/3 · dil 3/3 · ad 0.71 · ort 38 kelime")
    print(f"kıyas — 8B (kendi toplaması)        : kapı 0/6 · dil 2/6 · ad 0.75 · ort 82 kelime")
    print(f"\n→ {cikti}/results.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
