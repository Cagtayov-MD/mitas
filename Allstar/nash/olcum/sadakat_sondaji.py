#!/usr/bin/env python3
"""FAZ 0′ — SADAKAT SONDAJI: Ollama/llama.cpp vs transformers, aynı kareler.

SORU: Modeli kule içine alınca (Karar 2) çıktı ne kadar kayar?

NEDEN SORULUYOR: DeepSeek-OCR patch-tabanlı bir modeldir. Ağırlık aynı
(Ollama katmanı `file_type: F16`, 6.687 GB; HF `deepseek-ai/DeepSeek-OCR`
3336.1M param — birebir), ama görüntü ÖN-İŞLEME iki yığında farklıdır:
llama.cpp'nin `deepseekocr` handler'ı kendi normalizasyonunu, transformers
`AutoProcessor` başkasını yapar. Patch sınırları farklı düşerse çıktı
satır düzeyinde kayar (`YÖNETMEN` → `YÖNETME N`) ve `dedup_esigi=0.92` bunu
YENİ SATIR sayıp künyeye sızdırır. (MiniMax, 2026-08-13 konsey turu.)

KAPI 0′: sapma bandı ölçülür ve KAYDA GEÇER. Beklenmedik ölçüde büyükse
Karar 2 Çağatay'a yeniden açılır — sessizce devam edilmez.

TEST ÇEŞİTLİLİĞİ (CLAUDE.md Prensip 2/3): tek film değil, dört FARKLI dönemden
film. Aynı örneği tekrar kullanmak dar/yanıltıcı sinyal verir.

Koşum:
    sudo systemctl start ollama       # DİKKAT: açıkken Kobe ölçümü koşturma
    venv/bin/python olcum/sadakat_sondaji.py --motor ollama
    venv/bin/python olcum/sadakat_sondaji.py --motor yerel
    venv/bin/python olcum/sadakat_sondaji.py --kiyas
    sudo systemctl stop ollama
"""
from __future__ import annotations

import argparse
import base64
import difflib
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

KULE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KULE / "src"))

import okuyucu as ok_mod  # noqa: E402
import secim as secim_mod  # noqa: E402

PROJE = Path(os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas"))
YATAK = PROJE / "outputs" / "olcum_yatagi" / "klipler"
RAPOR = KULE / "raporlar"
ISTEM = "Free OCR."
OLLAMA = (os.environ.get("MITAS_OLLAMA_URL") or "http://127.0.0.1:11434").rstrip("/")

# DORT FARKLI DONEM — cesitlilik kasitli (1955 / 1985 / 2002 / 2018).
FILMLER = [
    "1955-0007-1-0000-00-1 BOZGUNCULAR",
    "1985-0173-1-0000-00-1 LA SEGUA",
    "2002-9044-1-0000-00-1 KERMİT BATAKLIKTA",
    "2018-1077-1-0000-90-1 ÇİĞERPAREM",
]
KARE_BASINA_FILM = 4
AYAR = {"tavan": 100, "son_kare_zorla": True, "ham_kuyruk": 0}


def kareler() -> list[tuple[str, Path]]:
    """Nash'in GERÇEKTEN seçtiği karelerden düzgün-adımlı örnek. Rastgele kare
    değil — sondaj üretimde okunacak karelerin üstünde yapılmalı."""
    secilen: list[tuple[str, Path]] = []
    for film in FILMLER:
        s = secim_mod.sec(YATAK / film / "frames" / "cikis_jenerik", AYAR)
        if s.hata or not s.yollar:
            print(f"  [atla] {film}: {s.hata}", file=sys.stderr)
            continue
        adim = max(1, len(s.yollar) // KARE_BASINA_FILM)
        for p in s.yollar[::adim][:KARE_BASINA_FILM]:
            secilen.append((film, p))
    return secilen


# ── motorlar ─────────────────────────────────────────────────────────────────

def sor_ollama(p: Path, timeout: int = 300) -> str:
    gov = {"model": "deepseek-ocr:latest", "prompt": ISTEM, "stream": False,
           "images": [base64.b64encode(p.read_bytes()).decode()],
           "options": {"temperature": 0.0, "num_predict": 2048, "num_ctx": 8192}}
    req = urllib.request.Request(OLLAMA + "/api/generate",
                                 data=json.dumps(gov).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read()).get("response", "")


def sor_yerel_kur():
    """transformers + yerel ağırlık. Model BİR KEZ yüklenir."""
    import model  # src/model.py — Faz 2'nin ilk parçası
    return model.yukle({"model_yol": "model/deepseek-ocr", "istem": ISTEM,
                        "max_new_tokens": 2048}, KULE)


# ── koşu ─────────────────────────────────────────────────────────────────────

def kos(motor: str) -> int:
    sor = sor_ollama if motor == "ollama" else sor_yerel_kur()
    kare_listesi = kareler()
    print(f"SONDAJ · motor={motor} · {len(kare_listesi)} kare "
          f"({len(FILMLER)} farkli film)\n")
    kayitlar = []
    for film, p in kare_listesi:
        t0 = time.time()
        try:
            ham = sor(p)
            hata = None
        except Exception as e:  # noqa: BLE001
            ham, hata = "", f"{type(e).__name__}: {e}"[:200]
        sure = time.time() - t0
        satirlar = [ok_mod._kirp(x) for x in (ham or "").splitlines()]
        satirlar = [x for x in satirlar if x and len(ok_mod.fold(x)) >= 2]
        kayitlar.append({"film": film, "kare": p.name, "sure_sn": round(sure, 1),
                         "hata": hata, "satirlar": satirlar})
        print(f"  {film[:32]:32s} {p.name:16s} {len(satirlar):3d} satir "
              f"{sure:5.1f}s" + (f"  HATA {hata}" if hata else ""), flush=True)
    RAPOR.mkdir(exist_ok=True)
    (RAPOR / f"sondaj_{motor}.json").write_text(
        json.dumps({"motor": motor, "istem": ISTEM,
                    "zaman": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "kayitlar": kayitlar}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"\nyazildi: raporlar/sondaj_{motor}.json")
    return 0


# ── kıyas ────────────────────────────────────────────────────────────────────

def _esles(a: list[str], b: list[str]) -> dict:
    """İki satır listesini kıyasla: birebir, katlanmış ve bulanık eşleşme."""
    fa, fb = [ok_mod.fold(x) for x in a], [ok_mod.fold(x) for x in b]
    sa, sb = set(fa), set(fb)
    ortak = sa & sb
    # Bulanik: A'daki her satir icin B'de >=0.92 benzer var mi (dedup esigi).
    bulanik = sum(1 for x in fa if x in sb or
                  any(difflib.SequenceMatcher(None, x, y).ratio() >= 0.92
                      for y in fb))
    return {"a_n": len(a), "b_n": len(b),
            "birebir_ortak": len(ortak),
            "yalniz_a": len(sa - sb), "yalniz_b": len(sb - sa),
            "bulanik_kapsanan": bulanik,
            "bulanik_oran": round(bulanik / max(1, len(fa)), 3),
            "dizi_benzerligi": round(
                difflib.SequenceMatcher(None, "\n".join(fa), "\n".join(fb)).ratio(), 3)}


def kiyas() -> int:
    yollar = {m: RAPOR / f"sondaj_{m}.json" for m in ("ollama", "yerel")}
    for m, y in yollar.items():
        if not y.is_file():
            print(f"HATA: {y} yok — once --motor {m}", file=sys.stderr)
            return 2
    o = json.loads(yollar["ollama"].read_text("utf-8"))
    l = json.loads(yollar["yerel"].read_text("utf-8"))
    ok = {(k["film"], k["kare"]): k for k in o["kayitlar"]}
    lk = {(k["film"], k["kare"]): k for k in l["kayitlar"]}
    anahtarlar = sorted(set(ok) & set(lk))

    print(f"KIYAS · {len(anahtarlar)} kare\n")
    print(f"  {'kare':18s} {'ollama':>7s} {'yerel':>7s} {'birebir':>8s} "
          f"{'bulanik':>8s} {'dizi':>6s}")
    satir_rapor = []
    for a in anahtarlar:
        e = _esles(ok[a]["satirlar"], lk[a]["satirlar"])
        satir_rapor.append({"film": a[0], "kare": a[1], **e})
        print(f"  {a[1]:18s} {e['a_n']:7d} {e['b_n']:7d} "
              f"{e['birebir_ortak']:8d} {e['bulanik_oran']:8.3f} "
              f"{e['dizi_benzerligi']:6.3f}")

    tum_o = [s for a in anahtarlar for s in ok[a]["satirlar"]]
    tum_l = [s for a in anahtarlar for s in lk[a]["satirlar"]]
    genel = _esles(tum_o, tum_l)

    # VETO SONRASI — asil olculmesi gereken bu. Kulenin GERCEK ciktisi ham
    # model cevabi degil, yapisal vetodan gecmis satirlardir. Sondajda gorulldu
    # ki sapma METIN OLMAYAN karelerde toplaniyor ve orada iki motor da
    # uyduruyor; o satirlar zaten iki tarafta da eleniyor.
    def _suz(ss):
        return [s for s in ss
                if not ok_mod.gevezelik_mi(s) and not ok_mod.yapisal_veto(s)]
    genel_veto = _esles(_suz(tum_o), _suz(tum_l))

    print(f"\n{'=' * 72}")
    print(f"HAM          ollama {genel['a_n']:4d} · yerel {genel['b_n']:4d} satir · "
          f"birebir {genel['birebir_ortak'] / max(1, genel['a_n']):6.1%} · "
          f"bulanik {genel['bulanik_oran']:6.1%}")
    print(f"VETO SONRASI ollama {genel_veto['a_n']:4d} · yerel {genel_veto['b_n']:4d} satir · "
          f"birebir {genel_veto['birebir_ortak'] / max(1, genel_veto['a_n']):6.1%} · "
          f"bulanik {genel_veto['bulanik_oran']:6.1%}")
    print(f"             yalniz ollama {genel_veto['yalniz_a']} · "
          f"yalniz yerel {genel_veto['yalniz_b']}")

    rapor = {"zaman": time.strftime("%Y-%m-%dT%H:%M:%S"),
             "kare_basina": satir_rapor, "genel": genel,
             "genel_veto_sonrasi": genel_veto}
    (RAPOR / "sondaj_kiyas.json").write_text(
        json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nyazildi: raporlar/sondaj_kiyas.json")
    print("\nYORUM ANAHTARI (bant KAYDA GECER, esik degil):")
    print("  bulanik kapsama yuksek + birebir dusuk → satir duzeyinde KAYMA var")
    print("  ikisi de dusuk                          → farkli okuma, Karar 2 acilir")
    print("  ikisi de yuksek                         → tasima guvenli")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="sadakat_sondaji")
    ap.add_argument("--motor", choices=("ollama", "yerel"))
    ap.add_argument("--kiyas", action="store_true")
    a = ap.parse_args(argv)
    if a.kiyas:
        return kiyas()
    if not a.motor:
        ap.error("--motor veya --kiyas gerekli")
    return kos(a.motor)


if __name__ == "__main__":
    sys.exit(main())
