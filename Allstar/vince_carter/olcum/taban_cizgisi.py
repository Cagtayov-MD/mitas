#!/usr/bin/env python3
"""taban_cizgisi.py — Vince Carter'ın YENMESİ GEREKEN SAYI.

`gt_dizi/<film>/{giris,cikis}_referans_{8b,27b,7b,mini}.txt` dosyaları
MEVCUT okuyucuların (jordan/nash/lebron denemeleri) çıktılarıdır. Bunlar
GT'ye karşı puanlanır → koşu yapılmadan, SIFIR GPU maliyetiyle taban çizgisi
elde edilir (docs/PLAN.md §4 "Sıfır maliyetli taban çizgisi").

Kural (docs/PLAN.md §5): Faz 2'nin kapısı "GT yatağında F1 ≥ taban_8b".
Bu dosya o eşiğin sayısını üretir. Referans dosyaları gt_dizi içinde
YERİNDE (salt okunur) okunur — kopyalanmaz.

Çıktı:
    olcum/veri/taban_cizgisi.json   makine okur
    docs/TABAN_CIZGISI.md           insan okur (film × motor tablosu)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

KULE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KULE / "olcum"))

from puan import VARSAYILAN_ESIK, puanla  # noqa: E402

GT_DIZI = Path("/opt/mitas/Allstar/gt_dizi")
# docs/PLAN.md §4'te adı geçen dört motor. Sıralama raporda korunur.
MOTORLAR = ("8b", "27b", "7b", "mini")


def _referans_yolu(kaynak_dizin: str, bolum: str, motor: str) -> Path:
    return GT_DIZI / kaynak_dizin / f"{bolum}_referans_{motor}.txt"


def _ek_referanslar(kaynak_dizin: str, bolum: str) -> list[tuple[str, Path]]:
    """Standart dörtlünün DIŞINDAKİ referans dosyaları (ör. cicek_taksi
    girişindeki JORDANKULE8b / YARISKODUJORDANKARE). Gizlenmezler: ayrı
    bölümde raporlanır ki "ölçülmemiş dosya var mı" sorusu açık kalmasın."""
    d = GT_DIZI / kaynak_dizin
    if not d.is_dir():
        return []
    onek = f"{bolum}_referans_"
    bulunan = []
    for p in sorted(d.glob(f"{onek}*.txt")):
        motor = p.stem[len(onek):]
        if motor not in MOTORLAR:
            bulunan.append((motor, p))
    return bulunan


def olc(yatak_yolu: Path, esik: float = VARSAYILAN_ESIK) -> dict:
    yatak = json.loads(Path(yatak_yolu).read_text(encoding="utf-8"))
    satirlar, eksik, ekler = [], [], []

    for y in yatak["yuzeyler"]:
        gt_yolu = KULE / y["gt"]
        kaynak_dizin = y.get("kaynak_dizin")
        if not kaynak_dizin:
            eksik.append({"film": y["film"], "bolum": y["bolum"],
                          "sebep": "yatakta kaynak_dizin yok"})
            continue
        for motor in MOTORLAR:
            ref = _referans_yolu(kaynak_dizin, y["bolum"], motor)
            if not ref.exists():
                eksik.append({"film": y["film"], "bolum": y["bolum"],
                              "motor": motor, "sebep": f"referans dosyasi yok: {ref}"})
                continue
            s = puanla(gt_yolu, ref, esik, dokum=True)
            satirlar.append({
                "film": y["film"], "bolum": y["bolum"], "motor": motor,
                "dogrulanmis_gt": bool(y.get("dogrulanmis", True)),
                "referans": str(ref),
                "metrikler": s["metrikler"],
                "sebep_sayaclari": s["fark_dokumu"]["sebep_sayaclari"],
            })
        for motor, ref in _ek_referanslar(kaynak_dizin, y["bolum"]):
            s = puanla(gt_yolu, ref, esik, dokum=True)
            ekler.append({
                "film": y["film"], "bolum": y["bolum"], "motor": motor,
                "dogrulanmis_gt": bool(y.get("dogrulanmis", True)),
                "referans": str(ref),
                "metrikler": s["metrikler"],
                "sebep_sayaclari": s["fark_dokumu"]["sebep_sayaclari"],
            })

    return {
        "olcum_tarihi": str(date.today()),
        "esik": esik,
        "gt_dizi": str(GT_DIZI),
        "motorlar": list(MOTORLAR),
        "olcumler": satirlar,
        "ek_olcumler": ekler,
        "eksik": eksik,
        "motor_ozeti": motor_ozeti(satirlar),
    }


def motor_ozeti(satirlar: list[dict]) -> dict:
    """Motor başına ortalama — YALNIZ doğrulanmış GT yüzeylerinden.

    Doğrulanmamış GT (iz_pesinde) ortalamaya karışmaz: yenilecek sayının
    kendisi şüpheliyse kapı anlamsızlaşır.
    """
    ozet: dict[str, dict] = {}
    for r in satirlar:
        if not r["dogrulanmis_gt"]:
            continue
        m = r["metrikler"]
        if m["f1"] is None:
            continue
        d = ozet.setdefault(r["motor"], {
            "yuzey_sayisi": 0, "f1_toplam": 0.0,
            "birebir": 0, "yakin": 0, "kayip": 0, "fazla": 0,
            "gt_toplam": 0, "cikti_toplam": 0})
        d["yuzey_sayisi"] += 1
        d["f1_toplam"] += m["f1"]
        for a in ("birebir", "yakin", "kayip", "fazla", "gt_toplam", "cikti_toplam"):
            d[a] += m[a]
    for motor, d in ozet.items():
        d["f1_ortalama"] = round(d.pop("f1_toplam") / d["yuzey_sayisi"], 4)
        # Havuz geneli (mikro) metrik: büyük filmler daha çok ağırlık taşır.
        tutan = d["birebir"] + d["yakin"]
        d["havuz_kesinlik"] = (round(tutan / d["cikti_toplam"], 4)
                               if d["cikti_toplam"] else None)
        d["havuz_duyarlilik"] = (round(tutan / d["gt_toplam"], 4)
                                 if d["gt_toplam"] else None)
        k, r = d["havuz_kesinlik"], d["havuz_duyarlilik"]
        d["havuz_f1"] = (round(2 * k * r / (k + r), 4)
                         if k and r and (k + r) else None)
    return ozet


# --------------------------------------------------------------------------
def _y(v, b: int = 3) -> str:
    return "—" if v is None else f"{v:.{b}f}"


def tablo_yaz(rapor: dict) -> None:
    print(f"TABAN ÇİZGİSİ — {rapor['olcum_tarihi']}  (eşik={rapor['esik']})")
    print("=" * 92)
    print(f"{'film':<20} {'bölüm':<6} {'motor':<6} {'BİREBİR':>7} {'YAKIN':>6} "
          f"{'KAYIP':>6} {'FAZLA':>6} {'kesin':>6} {'duyar':>6} {'F1':>6}")
    print("-" * 92)
    for r in rapor["olcumler"]:
        m = r["metrikler"]
        isaret = "" if r["dogrulanmis_gt"] else " *"
        print(f"{r['film'] + isaret:<20} {r['bolum']:<6} {r['motor']:<6} "
              f"{m['birebir']:>7} {m['yakin']:>6} {m['kayip']:>6} {m['fazla']:>6} "
              f"{_y(m['kesinlik']):>6} {_y(m['duyarlilik']):>6} {_y(m['f1']):>6}")
    print("-" * 92)
    print("MOTOR ÖZETİ (yalnız doğrulanmış GT yüzeyleri):")
    print(f"{'motor':<8} {'yüzey':>5} {'F1 ort':>8} {'havuz F1':>9} "
          f"{'BİREBİR':>8} {'YAKIN':>6} {'KAYIP':>6} {'FAZLA':>7}")
    for motor in rapor["motorlar"]:
        d = rapor["motor_ozeti"].get(motor)
        if not d:
            continue
        print(f"{motor:<8} {d['yuzey_sayisi']:>5} {d['f1_ortalama']:>8.3f} "
              f"{_y(d['havuz_f1']):>9} {d['birebir']:>8} {d['yakin']:>6} "
              f"{d['kayip']:>6} {d['fazla']:>7}")
    if rapor["ek_olcumler"]:
        print("-" * 92)
        print("EK REFERANSLAR (standart dörtlü dışı — özete katılmaz):")
        for r in rapor["ek_olcumler"]:
            m = r["metrikler"]
            print(f"  {r['film']}/{r['bolum']}/{r['motor']}: F1={_y(m['f1'])} "
                  f"birebir={m['birebir']} kayip={m['kayip']} fazla={m['fazla']}")
    if rapor["eksik"]:
        print("-" * 92)
        print(f"EKSİK ({len(rapor['eksik'])} referans dosyası bulunamadı)")


def markdown_uret(rapor: dict) -> str:
    s = [f"# Taban çizgisi — yenilmesi gereken sayı",
         "",
         f"> Ölçüm: **{rapor['olcum_tarihi']}** · eşik (YAKIN) = "
         f"`{rapor['esik']}` · alet: `olcum/puan.py`",
         "",
         "`gt_dizi/<film>/<bölüm>_referans_<motor>.txt` dosyaları MEVCUT",
         "okuyucuların çıktılarıdır. Bunlar kule içindeki GT anlık görüntüsüne",
         "(`olcum/gt/`) karşı puanlandı — **hiç GPU koşusu yapılmadan**.",
         "Vince Carter'ın Faz 2 kapısı: **GT yatağında F1 ≥ taban_8b**",
         "(docs/PLAN.md §5).",
         "",
         "## Motor özeti (yalnız doğrulanmış GT yüzeyleri)",
         "",
         "| motor | yüzey | F1 ortalama | havuz F1 | BİREBİR | YAKIN | KAYIP | FAZLA |",
         "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for motor in rapor["motorlar"]:
        d = rapor["motor_ozeti"].get(motor)
        if not d:
            continue
        s.append(f"| **{motor}** | {d['yuzey_sayisi']} | {d['f1_ortalama']:.3f} | "
                 f"{_y(d['havuz_f1'])} | {d['birebir']} | {d['yakin']} | "
                 f"{d['kayip']} | {d['fazla']} |")
    s += ["",
          "`F1 ortalama` = yüzey başına F1'lerin ortalaması (her film eşit ağırlık).",
          "`havuz F1` = tüm satırlar tek havuzda (büyük filmler ağır basar).",
          "İkisi birlikte verilir: tek sayı yanıltır — küçük filmde iyi, büyük",
          "filmde kötü bir motor yalnız `F1 ortalama`ya bakınca iyi görünür.",
          "",
          "## Film × motor",
          "",
          "| film | bölüm | motor | BİREBİR | YAKIN | KAYIP | FAZLA | kesinlik | duyarlılık | F1 |",
          "|---|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rapor["olcumler"]:
        m = r["metrikler"]
        isaret = "" if r["dogrulanmis_gt"] else " ⚠"
        s.append(f"| {r['film']}{isaret} | {r['bolum']} | {r['motor']} | "
                 f"{m['birebir']} | {m['yakin']} | {m['kayip']} | {m['fazla']} | "
                 f"{_y(m['kesinlik'])} | {_y(m['duyarlilik'])} | **{_y(m['f1'])}** |")
    s.append("")
    if any(not r["dogrulanmis_gt"] for r in rapor["olcumler"]):
        s += ["⚠ = GT doğrulanmamış (bkz. `olcum/gt/KAYNAK.md`) — tabloda",
              "gösterilir ama **motor özetine katılmaz**.", ""]

    s += ["## Hata sebepleri (fark dökümü toplamı)",
          "",
          "`olcum/puan.py --fark-dokumu` sayaçlarının motor başına toplamı.",
          "Ham F1 'ne kadar kötü' der; bu tablo **NEDEN kötü** der.",
          "",
          "| motor | FAZLA uydurma adayı | FAZLA tekrar | FAZLA motor notu | "
          "FAZLA GT-dışı eşleşme | KAYIP hiç yok | KAYIP eşik altı |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    for motor in rapor["motorlar"]:
        toplam: dict[str, int] = {}
        for r in rapor["olcumler"]:
            if r["motor"] != motor or not r["dogrulanmis_gt"]:
                continue
            for k, v in r["sebep_sayaclari"].items():
                toplam[k] = toplam.get(k, 0) + v
        if not toplam:
            continue
        s.append(f"| **{motor}** | {toplam.get('FAZLA_UYDURMA_ADAYI', 0)} | "
                 f"{toplam.get('FAZLA_TEKRAR', 0)} | "
                 f"{toplam.get('FAZLA_MOTOR_NOTU', 0)} | "
                 f"{toplam.get('FAZLA_GT_DISI_ESLESME', 0)} | "
                 f"{toplam.get('KAYIP_HIC_YOK', 0)} | "
                 f"{toplam.get('KAYIP_ESIK_ALTI', 0)} |")

    if rapor["ek_olcumler"]:
        s += ["", "## Ek referanslar (standart dörtlü dışı)",
              "",
              "Bu dosyalar `gt_dizi`'de mevcut ama `{8b,27b,7b,mini}` adlandırma",
              "kalıbına girmiyor. Ölçüldüler ama motor özetine katılmadılar —",
              "gizlenmesinler diye buradalar.",
              "",
              "| film | bölüm | motor | BİREBİR | YAKIN | KAYIP | FAZLA | F1 |",
              "|---|---|---|---:|---:|---:|---:|---:|"]
        for r in rapor["ek_olcumler"]:
            m = r["metrikler"]
            s.append(f"| {r['film']} | {r['bolum']} | `{r['motor']}` | "
                     f"{m['birebir']} | {m['yakin']} | {m['kayip']} | "
                     f"{m['fazla']} | {_y(m['f1'])} |")

    if rapor["eksik"]:
        s += ["", "## Bulunamayan referans dosyaları", "",
              f"{len(rapor['eksik'])} kombinasyonda referans dosyası yok "
              "(o motor o film için hiç koşulmamış):", ""]
        for e in rapor["eksik"]:
            s.append(f"- `{e['film']}/{e['bolum']}` · **{e.get('motor', '?')}** "
                     f"— {e['sebep']}")
    s.append("")
    return "\n".join(s)


# --------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="taban_cizgisi.py",
        description="mevcut motor ciktilarini GT'ye karsi puanla (yenilecek sayi)")
    ap.add_argument("--yatak", default=str(KULE / "olcum/yatak.json"))
    ap.add_argument("--esik", type=float, default=VARSAYILAN_ESIK)
    ap.add_argument("--yaz", action="store_true",
                    help="olcum/veri/taban_cizgisi.json + docs/TABAN_CIZGISI.md yaz")
    n = ap.parse_args(argv)

    rapor = olc(Path(n.yatak), n.esik)
    tablo_yaz(rapor)

    if n.yaz:
        veri_dizini = KULE / "olcum/veri"
        veri_dizini.mkdir(parents=True, exist_ok=True)
        j = veri_dizini / "taban_cizgisi.json"
        j.write_text(json.dumps(rapor, ensure_ascii=False, indent=1),
                     encoding="utf-8")
        md = KULE / "docs/TABAN_CIZGISI.md"
        md.write_text(markdown_uret(rapor), encoding="utf-8")
        print(f"\nyazildi: {j}")
        print(f"yazildi: {md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
