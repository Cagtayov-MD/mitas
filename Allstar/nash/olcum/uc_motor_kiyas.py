#!/usr/bin/env python3
"""Nash / LeBron / Jordan satirlarini film bazinda karsilastir.

Rapor bir ground-truth skoru degildir. Ham birebir, normalize-birebir ve
SequenceMatcher tabanli bulanik ortakligi ayri tutar; tum satir ve eslesmeler
JSON'a, ozet ve film tablosu Markdown'a yazilir.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import statistics
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any


MOTORLAR = ("nash", "lebron", "jordan")
ESLESMELER = (("nash", "lebron"), ("nash", "jordan"),
              ("lebron", "jordan"))


def _temiz(metin: Any) -> str:
    return " ".join(str(metin or "").split())


def fold(metin: str) -> str:
    metin = unicodedata.normalize("NFKD", _temiz(metin).casefold())
    metin = "".join(c for c in metin if not unicodedata.combining(c))
    metin = metin.translate(str.maketrans({"ı": "i", "ł": "l", "đ": "d"}))
    return " ".join("".join(c if c.isalnum() else " " for c in metin).split())


def _satir_metni(oge: Any) -> str:
    if isinstance(oge, dict):
        return _temiz(oge.get("text", ""))
    return _temiz(oge)


def oku(yol: Path, motor: str) -> dict[str, Any]:
    belge = json.loads(yol.read_text(encoding="utf-8"))
    if motor == "jordan":
        ham = [satir for blok in (belge.get("bloklar") or [])
               for satir in (blok.get("satirlar") or [])]
    else:
        ham = belge.get("satirlar") or []
    satirlar = [metin for oge in ham if (metin := _satir_metni(oge))]
    sayac = Counter(fold(x) for x in satirlar if fold(x))
    benzersiz, gorulen = [], set()
    for metin in satirlar:
        anahtar = fold(metin)
        if anahtar and anahtar not in gorulen:
            gorulen.add(anahtar)
            benzersiz.append(metin)
    sure = float(belge.get("sure_sn") or 0.0)
    if motor == "nash":
        # Nash toplu yolu Paddle worker'i sonucu islemeden once kosar; JSON'daki
        # sure_sn bu on-taramayi icermez. Film E2E icin ikisini topla.
        sure += float((belge.get("kanit") or {}).get("detector_sure_sn") or 0.0)
    return {
        "path": str(yol.resolve()), "status": belge.get("durum"),
        "duration_s": round(sure, 3), "raw_count": len(satirlar),
        "unique_count": len(benzersiz),
        "duplicate_count": sum(max(0, n - 1) for n in sayac.values()),
        "lines": satirlar, "unique_lines": benzersiz,
    }


def _maksimum_esleme(sol: list[str], sag: list[str], esik: float
                     ) -> list[tuple[int, int, float]]:
    """Esik ustunde maksimum-kardinalite bulanik esleme.

    Komsular skor sirasinda denenir. DFS augmenting-path maksimum eslesme
    sayisini bulur; bu bir semantik/ground-truth karari degildir.
    """
    komsular: list[list[tuple[int, float]]] = []
    for a in sol:
        fa = fold(a)
        adaylar = []
        for j, b in enumerate(sag):
            fb = fold(b)
            if not fa or not fb:
                continue
            # SequenceMatcher'in ulasabilecegi teorik ust sinir.
            if 2 * min(len(fa), len(fb)) / max(1, len(fa) + len(fb)) < esik:
                continue
            oran = difflib.SequenceMatcher(None, fa, fb).ratio()
            if oran >= esik:
                adaylar.append((j, oran))
        komsular.append(sorted(adaylar, key=lambda x: (-x[1], x[0])))

    sagdan_sola: dict[int, int] = {}

    def yerlestir(i: int, gorulen: set[int]) -> bool:
        for j, _oran in komsular[i]:
            if j in gorulen:
                continue
            gorulen.add(j)
            if j not in sagdan_sola or yerlestir(sagdan_sola[j], gorulen):
                sagdan_sola[j] = i
                return True
        return False

    # En az secenekli satiri once yerlestirmek belirsiz eslesmeyi azaltir.
    for i in sorted(range(len(sol)), key=lambda x: (len(komsular[x]), x)):
        yerlestir(i, set())
    sonuc = []
    for j, i in sagdan_sola.items():
        oran = next(oran for jj, oran in komsular[i] if jj == j)
        sonuc.append((i, j, oran))
    return sorted(sonuc)


def kiyas(a: dict[str, Any], b: dict[str, Any], esik: float) -> dict[str, Any]:
    aa, bb = a["unique_lines"], b["unique_lines"]
    raw_b = set(bb)
    raw_exact = sum(x in raw_b for x in aa)
    b_fold_indeks = {fold(x): i for i, x in enumerate(bb)}
    exact_pairs = []
    a_kullan, b_kullan = set(), set()
    for i, metin in enumerate(aa):
        if (j := b_fold_indeks.get(fold(metin))) is not None:
            a_kullan.add(i); b_kullan.add(j)
            exact_pairs.append({"a": metin, "b": bb[j], "kind": "normalized_exact",
                                "ratio": 1.0})
    a_kalan = [(i, x) for i, x in enumerate(aa) if i not in a_kullan]
    b_kalan = [(j, x) for j, x in enumerate(bb) if j not in b_kullan]
    fuzzy_pairs = []
    for ii, jj, oran in _maksimum_esleme(
            [x for _, x in a_kalan], [x for _, x in b_kalan], esik):
        i, ametin = a_kalan[ii]
        j, bmetin = b_kalan[jj]
        a_kullan.add(i); b_kullan.add(j)
        fuzzy_pairs.append({"a": ametin, "b": bmetin, "kind": "fuzzy",
                            "ratio": round(oran, 6)})
    eslesen = len(a_kullan)
    return {
        "a_unique": len(aa), "b_unique": len(bb), "raw_exact": raw_exact,
        "normalized_exact": len(exact_pairs), "fuzzy_additional": len(fuzzy_pairs),
        "matched_total": eslesen,
        "a_coverage": round(eslesen / len(aa), 6) if aa else None,
        "b_coverage": round(eslesen / len(bb), 6) if bb else None,
        "pairs": exact_pairs + fuzzy_pairs,
        "a_only": [x for i, x in enumerate(aa) if i not in a_kullan],
        "b_only": [x for j, x in enumerate(bb) if j not in b_kullan],
    }


def _bul(kok: Path, film: str, motor: str) -> Path:
    ad = f"{motor}.json"
    adaylar = [kok / film / "cikis" / ad]
    # Jordan buyuk kosu kokunde ayni standart yuzeyi kullanir; bu ikinci aday
    # farkli cagiricilar icin uyumluluk saglar.
    adaylar.append(kok / film / ad)
    for yol in adaylar:
        if yol.is_file():
            return yol
    raise FileNotFoundError(f"{motor}/{film} sonucu yok: {adaylar}")


def _yuzde(x: float | None) -> str:
    return "—" if x is None else f"%{100*x:.1f}"


def _ornek(liste: list[str], n: int = 6) -> str:
    if not liste:
        return "—"
    secim = liste[:n]
    metin = " · ".join(x.replace("|", "\\|") for x in secim)
    return metin + (f" · … (+{len(liste)-n})" if len(liste) > n else "")


def markdown(rapor: dict[str, Any], json_yolu: Path) -> str:
    g = rapor["global"]
    out = [
        f"# Nash / LeBron / Jordan — {g['film_count']} video birebir karşılaştırma",
        "",
        "> Bu rapor ground truth değildir. Motorlar arası ortaklık güçlü bir "
        "tanıdır; tek motordaki satır hem gerçek ek içerik hem hata olabilir.",
        "",
        "## Kapsam ve yöntem",
        "",
        f"- Film: **{g['film_count']}**, fuzzy eşik: **{rapor['fuzzy_threshold']}**",
        "- `raw_exact`: yalnız boşlukları toparlanmış karakter dizisi birebir.",
        "- `normalized_exact`: case/aksan/noktalama farkı kaldırıldıktan sonra birebir.",
        "- `fuzzy`: kalan benzersiz satırlarda film içi maksimum eşleme.",
        f"- Tüm satırlar, eşleşmeler ve yalnız-motor listeleri: `{json_yolu.name}`",
        "",
        "## Genel çıktı ve maliyet",
        "",
        "| Motor | Durum | Ham satır | Benzersiz | Tekrar | Film süre toplamı | Medyan | En yüksek |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for motor in MOTORLAR:
        m = g["engines"][motor]
        durum = ", ".join(f"{k}:{v}" for k, v in sorted(m["statuses"].items()))
        out.append(f"| {motor.title()} | {durum} | {m['raw_count']} | "
                   f"{m['unique_count']} | {m['duplicate_count']} | "
                   f"{m['duration_sum_s']:.1f} sn | {m['duration_median_s']:.1f} sn | "
                   f"{m['duration_max_s']:.1f} sn |")
    out += ["", "## İkili örtüşme", "",
            "| Çift | Normalize birebir | Ek fuzzy | Toplam eşleşme | İlk motor kapsama | İkinci motor kapsama |",
            "|---|---:|---:|---:|---:|---:|"]
    for a, b in ESLESMELER:
        p = g["pairs"][f"{a}__{b}"]
        out.append(f"| {a.title()} ↔ {b.title()} | {p['normalized_exact']} | "
                   f"{p['fuzzy_additional']} | {p['matched_total']} | "
                   f"{_yuzde(p['a_coverage'])} | {_yuzde(p['b_coverage'])} |")
    out += ["", "## En az bir başka motor tarafından desteklenen satırlar", "",
            "Bu ölçüm doğruluk değildir; iki farklı mimarinin aynı satırı okumasını "
            "destek sinyali sayar. İzole satır gerçek ek içerik de OCR hatası da olabilir.",
            "", "| Motor | Desteklenen | İzole | Destek oranı |",
            "|---|---:|---:|---:|"]
    for motor in MOTORLAR:
        m = g["support"][motor]
        out.append(f"| {motor.title()} | {m['supported']} | {m['isolated']} | "
                   f"{_yuzde(m['coverage'])} |")
    out += ["", "## Film bazında", "",
            "| Film | N/L/J benzersiz | N↔L | N↔J | L↔J | N/L/J süre (sn) |",
            "|---|---:|---:|---:|---:|---:|"]
    for film in rapor["films"]:
        e, p = film["engines"], film["pairs"]
        counts = "/".join(str(e[m]["unique_count"]) for m in MOTORLAR)
        times = "/".join(f"{e[m]['duration_s']:.1f}" for m in MOTORLAR)
        def pc(a: str, b: str) -> str:
            x = p[f"{a}__{b}"]
            return f"{x['matched_total']} ({_yuzde(x['a_coverage'])}/{_yuzde(x['b_coverage'])})"
        out.append(f"| {film['film_id']} | {counts} | {pc('nash','lebron')} | "
                   f"{pc('nash','jordan')} | {pc('lebron','jordan')} | {times} |")
    out += ["", "## Film bazında yalnız-motor örnekleri", ""]
    for film in rapor["films"]:
        out += [f"### {film['film_id']}", ""]
        for a, b in ESLESMELER:
            p = film["pairs"][f"{a}__{b}"]
            out.append(f"- Yalnız {a.title()} ({b.title()} kıyası, {len(p['a_only'])}): "
                       f"{_ornek(p['a_only'])}")
            out.append(f"- Yalnız {b.title()} ({a.title()} kıyası, {len(p['b_only'])}): "
                       f"{_ornek(p['b_only'])}")
        out.append("")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nash-root", type=Path, required=True)
    ap.add_argument("--lebron-root", type=Path, required=True)
    ap.add_argument("--jordan-root", type=Path, required=True)
    ap.add_argument("--out-json", type=Path, required=True)
    ap.add_argument("--out-md", type=Path, required=True)
    ap.add_argument("--fuzzy-threshold", type=float, default=0.90)
    a = ap.parse_args()

    film_setleri = []
    for kok, motor in ((a.nash_root, "nash"), (a.lebron_root, "lebron"),
                       (a.jordan_root, "jordan")):
        ad = f"{motor}.json"
        film_setleri.append({p.parents[1].name for p in kok.glob(f"*/cikis/{ad}")})
    filmler = sorted(set.intersection(*film_setleri))
    eksikler = {motor: sorted(set.union(*film_setleri) - film_setleri[i])
                for i, motor in enumerate(MOTORLAR)}
    if any(eksikler.values()):
        raise SystemExit(f"motor kapsamları esit degil: {eksikler}")

    film_raporlari = []
    for film in filmler:
        motorlar = {motor: oku(_bul(kok, film, motor), motor)
                    for motor, kok in (("nash", a.nash_root),
                                       ("lebron", a.lebron_root),
                                       ("jordan", a.jordan_root))}
        eslesmeler = {f"{x}__{y}": kiyas(motorlar[x], motorlar[y],
                                          a.fuzzy_threshold)
                       for x, y in ESLESMELER}
        destek = {}
        for motor in MOTORLAR:
            eslesen_anahtarlar: set[str] = set()
            for x, y in ESLESMELER:
                if motor not in (x, y):
                    continue
                alan = "a" if motor == x else "b"
                eslesen_anahtarlar.update(
                    fold(cift[alan]) for cift in eslesmeler[f"{x}__{y}"]["pairs"]
                )
            desteklenen = [satir for satir in motorlar[motor]["unique_lines"]
                            if fold(satir) in eslesen_anahtarlar]
            izole = [satir for satir in motorlar[motor]["unique_lines"]
                     if fold(satir) not in eslesen_anahtarlar]
            destek[motor] = {"supported": len(desteklenen),
                              "isolated": len(izole),
                              "coverage": (round(len(desteklenen) /
                                                   len(motorlar[motor]["unique_lines"]), 6)
                                           if motorlar[motor]["unique_lines"] else None),
                              "isolated_lines": izole}
        film_raporlari.append({"film_id": film, "engines": motorlar,
                               "pairs": eslesmeler, "support": destek})

    motor_ozet = {}
    for motor in MOTORLAR:
        ogeler = [f["engines"][motor] for f in film_raporlari]
        sureler = [x["duration_s"] for x in ogeler]
        motor_ozet[motor] = {
            "statuses": dict(Counter(x["status"] for x in ogeler)),
            "raw_count": sum(x["raw_count"] for x in ogeler),
            "unique_count": sum(x["unique_count"] for x in ogeler),
            "duplicate_count": sum(x["duplicate_count"] for x in ogeler),
            "duration_sum_s": round(sum(sureler), 3),
            "duration_median_s": round(statistics.median(sureler), 3),
            "duration_max_s": round(max(sureler, default=0), 3),
        }
    pair_ozet = {}
    for x, y in ESLESMELER:
        ogeler = [f["pairs"][f"{x}__{y}"] for f in film_raporlari]
        an, bn = sum(o["a_unique"] for o in ogeler), sum(o["b_unique"] for o in ogeler)
        eslesen = sum(o["matched_total"] for o in ogeler)
        pair_ozet[f"{x}__{y}"] = {
            "a_unique": an, "b_unique": bn,
            "raw_exact": sum(o["raw_exact"] for o in ogeler),
            "normalized_exact": sum(o["normalized_exact"] for o in ogeler),
            "fuzzy_additional": sum(o["fuzzy_additional"] for o in ogeler),
            "matched_total": eslesen,
            "a_coverage": round(eslesen / an, 6) if an else None,
            "b_coverage": round(eslesen / bn, 6) if bn else None,
        }
    destek_ozet = {}
    for motor in MOTORLAR:
        desteklenen = sum(f["support"][motor]["supported"] for f in film_raporlari)
        izole = sum(f["support"][motor]["isolated"] for f in film_raporlari)
        toplam = desteklenen + izole
        destek_ozet[motor] = {
            "supported": desteklenen, "isolated": izole,
            "coverage": round(desteklenen / toplam, 6) if toplam else None,
        }
    rapor = {
        "schema": "mitas.ocr-engine-comparison/v1",
        "fuzzy_threshold": a.fuzzy_threshold,
        "roots": {"nash": str(a.nash_root.resolve()),
                  "lebron": str(a.lebron_root.resolve()),
                  "jordan": str(a.jordan_root.resolve())},
        "global": {"film_count": len(filmler), "engines": motor_ozet,
                   "pairs": pair_ozet, "support": destek_ozet},
        "films": film_raporlari,
    }
    a.out_json.parent.mkdir(parents=True, exist_ok=True)
    a.out_md.parent.mkdir(parents=True, exist_ok=True)
    a.out_json.write_text(json.dumps(rapor, ensure_ascii=False, indent=1) + "\n",
                          encoding="utf-8")
    a.out_md.write_text(markdown(rapor, a.out_json), encoding="utf-8")
    print(json.dumps(rapor["global"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
