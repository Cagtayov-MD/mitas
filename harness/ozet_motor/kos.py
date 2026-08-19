# -*- coding: utf-8 -*-
"""ozet_motor kosucu — aday motorlari altin-sete karsi kosturur, not verir, rapor yazar.

Kullanim:
  python3 kos.py --model qwen3:8b --sekil tek_atis,cikar_ozetle --film 6
  python3 kos.py --uc vllm --model /yol/AWQ --sekil cikar_ozetle --film 10

Cikti: runs/<kosu-id>/results.json + RAPOR.md   (eval/ ASLA yazilmaz — olcum cubugu sabit)
"""
from __future__ import annotations

import argparse
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

GOLDENS = HERE / "eval" / "goldens.jsonl"


def altin_set(n: int | None) -> list[dict]:
    """goldens.jsonl kelime-sayisina gore sirali; n verilirse ESIT ARALIKLI ornekle.

    Esit araliklı ornekleme bilerek: en kisa/en uzun transkript ayni sette olsun, uzunluk
    cesitliligi bedava gelsin (CLAUDE.md 'test cesitliligi zorunlu')."""
    satir = [json.loads(s) for s in GOLDENS.read_text(encoding="utf-8").splitlines() if s.strip()]
    if not n or n >= len(satir):
        return satir
    adim = (len(satir) - 1) / (n - 1) if n > 1 else 1
    return [satir[round(i * adim)] for i in range(n)]


def main() -> int:
    a = argparse.ArgumentParser()
    a.add_argument("--uc", default="ollama", choices=["ollama", "vllm"])
    a.add_argument("--model", required=True)
    a.add_argument("--sekil", default="tek_atis,cikar_ozetle")
    a.add_argument("--film", type=int, default=6)
    a.add_argument("--parca", type=int, default=6)
    a.add_argument("--num-ctx", type=int, default=32768)
    a.add_argument("--vllm-host", default="http://127.0.0.1:8101/v1")
    a.add_argument("--not", dest="notu", default="")
    p = a.parse_args()

    uc = (motorlar.Ollama(p.model, num_ctx=p.num_ctx) if p.uc == "ollama"
          else motorlar.VLLM(p.model, host=p.vllm_host))
    sekiller = [s.strip() for s in p.sekil.split(",") if s.strip()]
    filmler = altin_set(p.film)

    kosu_id = datetime.now().strftime("%Y%m%d-%H%M%S") + f"-{p.uc}-{p.model.replace('/', '_').replace(':', '-')}"
    cikti = HERE / "runs" / kosu_id
    cikti.mkdir(parents=True, exist_ok=True)

    print(f"[ozet_motor] kosu={kosu_id}")
    print(f"[ozet_motor] {len(filmler)} film × {len(sekiller)} sekil = {len(filmler) * len(sekiller)} uretim\n")

    sonuc = []
    for f in filmler:
        metin = Path(f["transcript"]).read_text(encoding="utf-8", errors="ignore")
        print(f"── {f['baslik'][:48]:48s} ({f['transcript_kelime']:>6} kelime)")
        for s in sekiller:
            fn = motorlar.SEKILLER[s]
            try:
                k = (fn(uc, metin, f["baslik"], n_parca=p.parca) if s == "cikar_ozetle"
                     else fn(uc, metin, f["baslik"]))
            except Exception as e:  # noqa: BLE001 — bir kosu patlarsa digerleri devam etsin
                print(f"   {s:14s} HATA: {type(e).__name__}: {e}")
                sonuc.append({"film": f["id"], "sekil": s, "hata": f"{type(e).__name__}: {e}"})
                continue
            n = graders.notla(k.ozet, f["referans_sonnet"])
            sonuc.append({
                "film": f["id"], "baslik": f["baslik"], "sekil": s,
                "transcript_kelime": f["transcript_kelime"],
                "ozet": k.ozet, "referans_sonnet": f["referans_sonnet"],
                "saniye": round(k.saniye, 1), "cagri": k.cagri, "girdi_token": k.girdi_token,
                "ara_urun": k.ara_urun, "notlar": n,
            })
            bayrak = "GECTI" if n["deterministik_gecti"] else "KALDI"
            print(f"   {s:14s} {k.saniye:6.1f}s  {k.cagri} cagri  "
                  f"{k.girdi_token:>6} girdi-tok  {n['b1_bicim']['kelime']:>3} kelime  "
                  f"ad-isabet {n['b3_olgu']['ad_isabet']}  [{bayrak}]")
        print()

    (cikti / "results.json").write_text(json.dumps({
        "kosu_id": kosu_id, "uc": p.uc, "model": p.model, "sekiller": sekiller,
        "num_ctx": p.num_ctx if p.uc == "ollama" else None, "n_parca": p.parca,
        "not": p.notu, "zaman": datetime.now().isoformat(timespec="seconds"),
        "sonuc": sonuc,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    sat = [f"# ozet_motor — {kosu_id}", "",
           f"uc **{p.uc}** · model **{p.model}** · num_ctx {p.num_ctx} · {len(filmler)} film",
           ""]
    for s in sekiller:
        alt = [r for r in sonuc if r.get("sekil") == s and "ozet" in r]
        if not alt:
            continue
        gecti = sum(1 for r in alt if r["notlar"]["deterministik_gecti"])
        ort_s = sum(r["saniye"] for r in alt) / len(alt)
        ad = [r["notlar"]["b3_olgu"]["ad_isabet"] for r in alt
              if r["notlar"]["b3_olgu"]["ad_isabet"] is not None]
        sat += [f"## {s} — kapi {gecti}/{len(alt)} · ort {ort_s:.1f}s · "
                f"ad-isabet ort {sum(ad) / len(ad):.2f}" if ad else f"## {s}", ""]
        for r in alt:
            n = r["notlar"]
            sat += [f"### {r['baslik']}  `{r['saniye']}s · {r['cagri']} çağrı · "
                    f"{r['girdi_token']} girdi-token`",
                    f"**aday:** {r['ozet']}", "",
                    f"**Sonnet:** {r['referans_sonnet']}", "",
                    f"kapı: {'GEÇTİ' if n['deterministik_gecti'] else 'KALDI'} · "
                    f"biçim {n['b1_bicim']['hatalar'] or 'temiz'} · "
                    f"dil {'temiz' if n['b2_dil']['gecti'] else n['b2_dil']} · "
                    f"ad-isabet {n['b3_olgu']['ad_isabet']} · "
                    f"eksik ad {n['b3_olgu']['ozette_olmayan_ad']}", ""]
    (cikti / "RAPOR.md").write_text("\n".join(sat), encoding="utf-8")
    print(f"[ozet_motor] → {cikti}/RAPOR.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
