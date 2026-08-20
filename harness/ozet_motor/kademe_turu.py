# -*- coding: utf-8 -*-
"""KADEMELİ HAT TURU — sadakati düzeltmek için hangi adımı büyütmek gerekiyor?

Ölçülen (2026-07-30): 8B çıkarabiliyor (ad-isabet 0.75) ama TOPLAYAMIYOR (kapı 0/6).
26-35B toplayınca BİÇİM düzeliyor (kapı 4-6/6) ama SADAKAT düzelmiyor — çünkü 8B'nin FİNAL
bloğu yanlış/gürültülü ve toplayıcı onu sadakatle cilalıyor ("Sonunda Ami ile kavuşur").

Ayrıştırılan soru:
  B  8B çıkar · 26B final · 26B topla   → yalnız FİNAL turunu büyütmek yetiyor mu? (ucuz)
  C  26B çıkar · 26B final · 26B topla  → tüm çıkarmayı büyütmek gerekiyor mu? (pahalı)

MODELE GÖRE ÖBEKLEME (2026-07-30 dersi): film-film dönmek her filmde 8B↔26B takası yaptırıyordu
(~20 sn × 12 = 4 dk saf model taşıma). Bunun yerine önce TÜM 8B işi, sonra TÜM 26B işi → toplam
2 model yüklemesi. Aynı sonuç, çok daha hızlı.

Kapı artık B4 SADAKAT'i içerir: uydurma ad + finalin transkript kuyruğunda karşılığı.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "eval"))

import graders  # noqa: E402
import motorlar  # noqa: E402

KUCUK, BUYUK = "qwen3:8b", "gemma4:26b"
N_FILM, N_PARCA = 4, 6          # 4 film: sinyal için yeterli, tur güvenle bitiyor
ZAMAN_ASIMI = 240               # takılırsa 4 dk kaybet, 16 değil


def yaz(*a) -> None:
    print(*a, flush=True)       # flush ZORUNLU — tamponlu log "takıldı mı çalışıyor mu" gizliyor


def altin(n: int) -> list[dict]:
    s = [json.loads(x) for x in (HERE / "eval" / "goldens.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    adim = (len(s) - 1) / (n - 1)
    return [s[round(i * adim)] for i in range(n)]


def ollama_bosalt() -> None:
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
            yaz(f"   (boşaltıldı: {y})")
        except Exception:  # noqa: BLE001
            pass
    time.sleep(6)


def parcala_ve_cikar(uc, tr: str, etiket: str) -> tuple[list[str], list[str], str]:
    """Bir filmin BÖLÜM notlarını çıkar (final turu HARİÇ). Döner: (parçalar, olay-blokları, kişi-satırı)."""
    metin = motorlar._TS.sub("", tr)
    parcalar = motorlar._satirdan_bol(metin, N_PARCA)
    kisiler = motorlar._adlari_topla(metin)
    ksatir = (f"Filmde geçen kişi adları (transkriptin tamamından): {', '.join(kisiler)}.\n"
              if kisiler else "")
    olaylar = []
    for i, p in enumerate(parcalar, 1):
        kelime = len(p.split())
        madde = min(10, max(5, kelime // 250))
        y = uc.uret("Sen bir film transkriptinden olay çıkaran bir asistansın. Sadece metinde "
                    "açıkça geçeni yazarsın; uydurmazsın.",
                    motorlar._PARCA_SORU.format(i=i, n=N_PARCA, metin=p, kisiler=ksatir, madde=madde),
                    max_token=min(700, 120 + madde * 55))
        olaylar.append(f"[Bölüm {i}/{N_PARCA}]\n{y.metin}")
        yaz(f"      {etiket} bölüm {i}/{N_PARCA} ({y.saniye:.0f}s)")
    return parcalar, olaylar, ksatir


def final_ve_topla(uc_f, uc_t, parcalar, olaylar, ksatir, baslik) -> tuple[str, str]:
    """Final turu + nihai özet. Döner: (özet, tahta)."""
    son_blok = "\n".join(parcalar[-2:])
    yf = uc_f.uret("Sen bir film transkriptinin son bölümünden filmin bitişini çıkaran bir "
                   "asistansın. Sadece metinde açıkça geçeni yazarsın; uydurmazsın.",
                   motorlar._FINAL_SORU.format(metin=son_blok, kisiler=ksatir), max_token=350)
    tahta = ("\n\n".join(olaylar)
             + "\n\n[FİLMİN BİTİŞİ — son bölümden ayrıca çıkarıldı, ÖNCELİKLİDİR: yukarıdaki "
               "bölüm notlarıyla çelişirse BU doğrudur]\n" + yf.metin)
    sistem = open(motorlar.PROMPT_V2, encoding="utf-8").read()
    kullanici = (f"Dosya: {baslik}\nSüre: —\n\n"
                 "Aşağıdaki liste, filmin transkriptinden bölüm bölüm çıkarılmış OLAY NOTLARIDIR "
                 "(transkriptin kendisi değil). Bölümler filmin ZAMAN SIRASINA göre dizilidir. "
                 "Bu notlara dayanarak özeti yaz. Notlarda olmayan hiçbir şey ekleme. Madde madde "
                 "değil, akıcı tek paragraf yaz.\n\nOLAY NOTLARI:\n" + tahta)
    return uc_t.uret(sistem, kullanici).metin, tahta


def notla_yaz(sonuc, kol, f, ozet, tahta, tr, sn) -> None:
    n = graders.notla(ozet, f["referans_sonnet"], tr)
    b4 = n["b4_topraklama"]
    sonuc.append({"kol": kol, "film": f["id"], "baslik": f["baslik"], "ozet": ozet,
                  "referans_sonnet": f["referans_sonnet"], "saniye": round(sn, 1),
                  "ara_urun": tahta, "notlar": n})
    yaz(f"   {f['baslik'][:28]:28s} {sn:6.1f}s {n['b1_bicim']['kelime']:>4}kel "
        f"biçim-{'ok' if n['b1_bicim']['gecti'] else 'X'} "
        f"dil-{'ok' if n['b2_dil']['gecti'] else 'X'} "
        f"SADAKAT-{'ok' if b4['gecti'] else 'X'} (toprak {b4['final_toprak']})")


def main() -> int:
    filmler = altin(N_FILM)
    kosu_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-kademe"
    cikti = HERE / "runs" / kosu_id
    cikti.mkdir(parents=True, exist_ok=True)
    yaz(f"[kademe] {N_FILM} film · B(8B çıkar+26B final/topla) vs C(tam 26B) · {kosu_id}")
    for f in filmler:
        yaz(f"   · {f['baslik'][:40]:40s} {f['transcript_kelime']:>6} kelime")
    yaz("")

    sonuc, metinler = [], {f["id"]: Path(f["transcript"]).read_text(encoding="utf-8", errors="ignore")
                           for f in filmler}

    # ── AŞAMA 1: 8B yüklü — TÜM filmlerin bölüm notları (B kolu için) ──────────────
    ollama_bosalt()
    yaz(f"════ AŞAMA 1/3 — {KUCUK} ile bölüm çıkarma ({N_FILM} film)")
    uc8 = motorlar.Ollama(KUCUK, num_ctx=16384, timeout=ZAMAN_ASIMI)
    b_notlari = {}
    for f in filmler:
        t0 = time.perf_counter()
        try:
            b_notlari[f["id"]] = (*parcala_ve_cikar(uc8, metinler[f["id"]], f["baslik"][:16]),
                                  time.perf_counter() - t0)
        except Exception as e:  # noqa: BLE001
            yaz(f"   {f['baslik'][:28]:28s} ÇIKARMA HATASI {type(e).__name__}: {str(e)[:60]}")

    # ── AŞAMA 2+3: 26B yüklü — B kolunun final/toplaması, sonra C kolunun tamamı ───
    ollama_bosalt()
    yaz(f"\n════ AŞAMA 2/3 — B kolu: 8B notları + {BUYUK} final/toplama")
    uc26f = motorlar.Ollama(BUYUK, num_ctx=16384, timeout=ZAMAN_ASIMI)
    uc26t = motorlar.Ollama(BUYUK, num_ctx=8192, timeout=ZAMAN_ASIMI)
    for f in filmler:
        if f["id"] not in b_notlari:
            continue
        parcalar, olaylar, ksatir, sn_cikar = b_notlari[f["id"]]
        t0 = time.perf_counter()
        try:
            ozet, tahta = final_ve_topla(uc26f, uc26t, parcalar, olaylar, ksatir, f["baslik"])
        except Exception as e:  # noqa: BLE001
            yaz(f"   {f['baslik'][:28]:28s} HATA {type(e).__name__}: {str(e)[:60]}")
            continue
        notla_yaz(sonuc, "B_8Bcikar_26Bfinal_26Btopla", f, ozet, tahta,
                  metinler[f["id"]], sn_cikar + (time.perf_counter() - t0))

    yaz(f"\n════ AŞAMA 3/3 — C kolu: tam {BUYUK}")
    uc26c = motorlar.Ollama(BUYUK, num_ctx=16384, timeout=ZAMAN_ASIMI)
    for f in filmler:
        t0 = time.perf_counter()
        try:
            parcalar, olaylar, ksatir = parcala_ve_cikar(uc26c, metinler[f["id"]], f["baslik"][:16])
            ozet, tahta = final_ve_topla(uc26f, uc26t, parcalar, olaylar, ksatir, f["baslik"])
        except Exception as e:  # noqa: BLE001
            yaz(f"   {f['baslik'][:28]:28s} HATA {type(e).__name__}: {str(e)[:60]}")
            continue
        notla_yaz(sonuc, "C_tam26B", f, ozet, tahta, metinler[f["id"]], time.perf_counter() - t0)

    (cikti / "results.json").write_text(json.dumps(
        {"kosu_id": kosu_id, "tip": "kademe", "n_film": N_FILM,
         "zaman": datetime.now().isoformat(timespec="seconds"), "sonuc": sonuc},
        ensure_ascii=False, indent=2), encoding="utf-8")

    yaz("\n" + "═" * 78)
    yaz(f"{'kol':30s} {'biçim':>7} {'dil':>6} {'SADAKAT':>9} {'ort toprak':>11} {'ort sn':>7}")
    for kol in ("B_8Bcikar_26Bfinal_26Btopla", "C_tam26B"):
        v = [r for r in sonuc if r["kol"] == kol]
        if not v:
            yaz(f"{kol:30s}  (çıktı yok)")
            continue
        tp = [r["notlar"]["b4_topraklama"]["final_toprak"] for r in v
              if r["notlar"]["b4_topraklama"]["final_toprak"] is not None]
        yaz(f"{kol:30s} {sum(1 for r in v if r['notlar']['b1_bicim']['gecti'])}/{len(v):<6} "
            f"{sum(1 for r in v if r['notlar']['b2_dil']['gecti'])}/{len(v):<5} "
            f"{sum(1 for r in v if r['notlar']['b4_topraklama']['gecti'])}/{len(v):<8} "
            f"{(sum(tp) / len(tp) if tp else 0):>11.2f} "
            f"{sum(r['saniye'] for r in v) / len(v):>7.1f}")
    yaz("\nkıyas — 8B çıkar+8B final+26B topla (ölçüldü): biçim 4/6 · SADAKAT 2/6 · toprak 0.45")
    yaz(f"→ {cikti}/results.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
