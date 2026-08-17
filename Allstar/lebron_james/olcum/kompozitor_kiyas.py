#!/usr/bin/env python3
"""KOMPOZİTÖR KIYASI — lebron ↔ ibrahimovic ↔ magic, AYNI karelerde, ölçümle.

Faz 3+4 kapısı (spec §7-§10, model_manifest: no_engine_selection_before_benchmark):
kompozitör seçimi bu koşunun sayılarıyla yapılır, tahminle değil. 2026-08-11
GUNLUK denetiminin bulduğu boşluk — "388 film ibrahimovic'le, 610 film
lebron'la üretilmiş, örtüşme 0 → kafa-kafaya kıyas hiç yapılmamış" — burada
kapanır.

Motorlar (hiçbirine dokunulmaz):
  lebron      : src/derleyici.derle            — kulenin hizmet motoru
  ibrahimovic : aday/ibrahimovic.compose_adaptif — kör kopya aday
  magic       : aday/magic.derle                — birleşik aday (Faz 4)

İbrahimovic'in iki bilinen borcu (gömülü /home/cagatay/Ex_Frame yolu, olcum/
saglik bağımlılığı) KOŞUCU düzeyinde çözülür; dosya kör kopya kalır ve
test_aday_motorun_bilinen_borclari Testi borçları görmeye devam eder:
  * kareler ims= ile beslenir → diskten okumaz, gömülü yol devre dışı
  * sys.path'e olcum/ ÖNCE eklenir → kendi `import saglik`'i KULEDEKİ ölçüm
    kopyasına düşer → token motoru (F1b/F1c) canlı kalır

TOKEN BEKÇİSİ: ibrahimovic'in _dc_al()'ı None dönerse koşu DURUR. Geometrik-
fallback ibrahimovic ile kıyas sessiz yalan olur — kıyaslanan şey v16
token-kimlik motoru, onun topal hali değil.

Ölçütler (mevcut araçlar yeniden kullanılır, yeniden yazılmaz):
  dup_metrik.olc      → dup_oran, doku_kapsami          (master iç tekrar)
  saglik.degerlendir  → 4 sağlık kriteri                 (sahte-film düzeni)
  sadakat.master_tokenlari → text_recall                 (MASTER_KOK yönlendirilir;
                        "var" tarafı motorlardan bağımsız BİR KEZ hesaplanır)
  kural.cokmus        → 20+ kare → tek ekrana çöküş

ÇIKTI:
  scratch/kompozitor_kiyas/<motor>/<slug>/{reading_master.png, manifest.json, metrik.json}
  raporlar/kompozitor_kiyas_<tarih>.json + .md     (her film sonrası artımlı yazılır)

Kullanım:
  ../venv/bin/python kompozitor_kiyas.py                          # taban: lebron+ibrahimovic
  ../venv/bin/python kompozitor_kiyas.py --motorlar lebron,ibrahimovic,magic
  ../venv/bin/python kompozitor_kiyas.py --motorlar 'magic:plato=0'   # ablasyon
  ../venv/bin/python kompozitor_kiyas.py --filmler acemiler-cetesi   # tek film
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import statistics
import sys
import time
from pathlib import Path

KULE = Path(__file__).resolve().parents[1]
KOK = KULE.parents[1]                      # mitas kökü
EX_KARE_ROOT = Path(os.environ.get("MITAS_EX_KARE_ROOT",
                                   Path.home() / "Ex_Frame"))
SCRATCH = KULE / "scratch" / "kompozitor_kiyas"

# monitor zinciri (uret._import_monitor) kendi _PR'sini bu env'den okur —
# import ÖNCESI ayarlanmalı (kapi_sadakat ile aynı dikkat).
os.environ.setdefault("MITAS_PROJECT_ROOT", str(KOK))

# SIRA ÖNEMLİ: ibrahimovic'in `import saglik`'i kuledeki ölçüm kopyasını
# bulmalı (aday/ içinde saglik yok — yalnız olcum/ içinde var).
for _p in (str(KULE / "olcum"), str(KULE / "aday"), str(KULE / "src"), str(KULE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# 12 film — GUNLUK 2026-08-11'de kuyruğa alınmış karma-zorluk kümesi:
# sadakat doğrulama 6'sı + belgeli arıza sınıfları (her eşik hangi filmle
# kalibre edildiyse o film burada).
FILMLER: list[tuple[str, str]] = [
    ("benimle-dans-et",   "sadakat-doğrulama (recall 0.829)"),
    ("olum-emri",         "sadakat-doğrulama (recall 0.189)"),
    ("solaris",           "sadakat-doğrulama (17 kare, az kare)"),
    ("baba-2",            "sadakat-doğrulama (295 kare, uzun)"),
    ("hizli-silah",       "sadakat-doğrulama (okunabilirlik 0.25)"),
    ("acemiler-cetesi",   "sadakat-doğrulama (kule ilk koşusu)"),
    ("kucuk-dev-adam",    "dissolve zinciri (plato/fake-scroll kalibrasyonu)"),
    ("karadeniz",         "fade zinciri + soluk kartlar (110'da görünmez)"),
    ("hayat-agaci",       "çöküş + kar-tulumu gren (fark-tabanı sınıfı)"),
    ("demir-maskeli-adam", "pozitif kontrol (üretimde recall 0.005)"),
    ("jetgiller-ve-cakmaktaslar", "statik zemin (fark yalnız fallback)"),
    ("komsum-totoro",     "statik zemin (NCC dominasyon sınıfı)"),
]

TARİH = _dt.date.today().isoformat()


# --------------------------------------------------------------------------- #
# motor kaydı
# --------------------------------------------------------------------------- #
def _magic_ozellikler(anahtar: str) -> dict:
    """'plato=0,token=0' → {'plato': False, 'token': False} — ablasyon koşusu."""
    oz = {}
    for parca in anahtar.split(","):
        parca = parca.strip()
        if not parca:
            continue
        k, _, v = parca.partition("=")
        oz[k.strip()] = v.strip() not in ("0", "false", "False", "")
    return oz


def motor_getir(ad: str):
    """'lebron' | 'ibrahimovic' | 'magic[:anahtar=deger,...]' → (etiket, çağrılan)."""
    if ad == "lebron":
        import derleyici
        return "lebron", derleyici.derle
    if ad == "ibrahimovic":
        import ibrahimovic
        dc = ibrahimovic._dc_al()
        if dc is None:
            print("DUR: ibrahimovic'in token motoru (saglik→uret→monitor→F1b/F1c) "
                  "yüklenemedi. Geometrik-fallback ibrahimovic ile kıyas SESSİZ "
                  "YALAN olur — kıyaslanan v16 token-kimlik motorudur. Zinciri "
                  "onarmadan koşu başlamaz.", file=sys.stderr)
            raise SystemExit(3)
        return "ibrahimovic", ibrahimovic.compose_adaptif
    if ad.startswith("magic"):
        import magic
        anahtar = ad.split(":", 1)[1] if ":" in ad else ""
        oz = _magic_ozellikler(anahtar) if anahtar else None
        etiket = "magic" if not anahtar else f"magic[{anahtar}]"

        def _cagri(slug, ims=None, _oz=oz):
            return magic.derle(slug, ims=ims, ozellikler=_oz)
        return etiket, _cagri
    raise SystemExit(f"bilinmeyen motor: {ad}")


# --------------------------------------------------------------------------- #
# ölçüm
# --------------------------------------------------------------------------- #
def film_kos(slug: str, sinif: str, motorlar: dict[str, object],
             dc, sadakat_mod, dup_metrik, saglik_mod, yukleyici, kural
             ) -> dict:
    kare_dizini = EX_KARE_ROOT / f"{slug}-exit_frames"
    ims, dosya = yukleyici.kareleri_yukle(kare_dizini)

    # "var" tarafı motorlardan bağımsız — film başına BİR KEZ (sadakat'ın
    # örneklemesi sqrt-ölçekli, motor başına tekrar etmek 2/3 boşa GPU demek).
    var_sonuc = sadakat_mod.var_kunye_tokenlari(slug, dc)
    var: set = var_sonuc["var"]

    kayit: dict = {"film": slug, "sinif": sinif, "kare": len(ims),
                   "dosya": dosya, "var_token": len(var), "motorlar": {}}

    for etiket, fn in motorlar.items():
        t0 = time.time()
        try:
            master, man = fn(slug, ims=ims) if len(ims) >= 2 else (None, {"durum": "kare_yok"})
        except Exception as e:  # noqa: BLE001 — motor istisnası da bir sonuçtur
            kayit["motorlar"][etiket] = {
                "durum": "ARIZA", "hata": f"{type(e).__name__}: {e}",
                "sure_s": round(time.time() - t0, 1)}
            continue

        m: dict = {"durum": man.get("durum", "?"),
                   "sure_s": round(time.time() - t0, 1),
                   "olcum_yolu": man.get("olcum_yolu"),
                   "sinif_sayimi": man.get("sinif_sayimi")}

        if master is not None:
            film_dir = SCRATCH / etiket / slug
            film_dir.mkdir(parents=True, exist_ok=True)
            png = film_dir / "reading_master.png"
            yukleyici.yaz(png, master)

            metrik = dup_metrik.olc(png)
            (film_dir / "metrik.json").write_text(
                json.dumps(metrik, ensure_ascii=False, indent=1), encoding="utf-8")
            (film_dir / "manifest.json").write_text(
                json.dumps({**man, "status": "OK",
                            "kept_blocks": man.get("segment") or 1},
                           ensure_ascii=False, indent=1), encoding="utf-8")

            m.update({"boy": (man.get("size") or [None, None])[1],
                      "segment": man.get("segment"),
                      "dup_oran": metrik.get("dup_oran"),
                      "doku_kapsami": metrik.get("doku_kapsami")})

            sag = saglik_mod.degerlendir(film_dir)
            m["saglikli"] = bool(sag.get("saglikli"))
            m["ihlaller"] = sag.get("ihlaller") or []

            # sadakat "yakalanan" tarafı — MASTER_KOK bu motora yönlendirilir
            sadakat_mod.MASTER_KOK = SCRATCH / etiket
            mt = sadakat_mod.master_tokenlari(slug, dc)
            yakalanan: set = mt["yakalanan"]
            m["text_recall"] = (round(len(yakalanan & var) / len(var), 4)
                                if var else None)
            occ = mt["occ"]
            m["okunabilirlik"] = (round(sum(1 for _, c in occ
                                             if c >= sadakat_mod.OKUNABILIRLIK_CONF_ESIK)
                                        / len(occ), 4) if occ else None)

            m["cokme"] = kural.cokmus(man, len(ims), master.shape[0])
        kayit["motorlar"][etiket] = m
    return kayit


def motor_ozeti(filmler: list[dict]) -> dict:
    ozet: dict = {}
    etiketler: list[str] = []
    for f in filmler:
        for e in f["motorlar"]:
            if e not in etiketler:
                etiketler.append(e)
    for e in etiketler:
        kayitlar = [f["motorlar"][e] for f in filmler if e in f["motorlar"]]
        uretti = [k for k in kayitlar if k.get("boy")]
        recall = [k["text_recall"] for k in kayitlar if k.get("text_recall") is not None]
        dup = [k["dup_oran"] for k in kayitlar if k.get("dup_oran") is not None]
        boy = [k["boy"] for k in kayitlar if k.get("boy")]
        ozet[e] = {
            "film": len(kayitlar),
            "uretti": len(uretti),
            "ariza": sum(1 for k in kayitlar if k.get("durum") == "ARIZA"),
            "saglikli": sum(1 for k in kayitlar if k.get("saglikli")),
            "cokme": sum(1 for k in kayitlar if k.get("cokme")),
            "recall_medyan": round(statistics.median(recall), 4) if recall else None,
            "dup_medyan": round(statistics.median(dup), 4) if dup else None,
            "boy_medyan": int(statistics.median(boy)) if boy else None,
        }
    return ozet


def main(argv=None) -> int:
    global EX_KARE_ROOT
    ap = argparse.ArgumentParser(prog="kompozitor_kiyas")
    ap.add_argument("--motorlar", default="lebron,ibrahimovic")
    ap.add_argument("--filmler", help="virgülle slug listesi (varsayılan: 12'li küme)")
    ap.add_argument("--hepsi", action="store_true",
                    help="kökteki TÜM film dizinleri (440) — gece koşusu")
    ap.add_argument("--devam", action="store_true",
                    help="çıktı dosyasında zaten ölçülmüş filmları atla "
                         "(yarıda kalan koşuyu kaldığı yerden sürdürür)")
    ap.add_argument("--n", type=int, default=None, help="kümeden ilk N film")
    ap.add_argument("--kok", default=str(EX_KARE_ROOT))
    ap.add_argument("--cikti", default=str(KULE / "raporlar" / f"kompozitor_kiyas_{TARİH}.json"))
    a = ap.parse_args(argv)

    EX_KARE_ROOT = Path(a.kok)

    import yukleyici, kural
    import dup_metrik, saglik as saglik_mod, sadakat as sadakat_mod

    motorlar: dict[str, object] = {}
    for ad in [m.strip() for m in a.motorlar.split(",") if m.strip()]:
        etiket, fn = motor_getir(ad)
        motorlar[etiket] = fn
    dc = saglik_mod._uret_mod()._dc()

    if a.hepsi:
        kok = Path(a.kok)
        secim = [(d.name.removesuffix("-exit_frames"), "")
                 for d in sorted(kok.iterdir()) if d.is_dir()]
    elif a.filmler:
        secim = [(s.strip(), "") for s in a.filmler.split(",") if s.strip()]
    else:
        secim = FILMLER
    if a.n:
        secim = secim[:a.n]

    # varlık kontrolü — eksik slug ATLANIR ama rapora yazılır (sessiz kayıp yok)
    eksikler = [s for s, _ in secim
                if not (EX_KARE_ROOT / f"{s}-exit_frames").is_dir()]
    secim = [(s, c) for s, c in secim
             if (EX_KARE_ROOT / f"{s}-exit_frames").is_dir()]

    cikti = Path(a.cikti)
    cikti.parent.mkdir(parents=True, exist_ok=True)
    filmler: list[dict] = []
    if a.devam and cikti.is_file():
        try:
            eski = json.loads(cikti.read_text(encoding="utf-8"))
            filmler = [f for f in eski.get("filmler", [])
                       if all(e in f.get("motorlar", {}) for e in motorlar)]
            print(f"[devam] {len(filmler)} film zaten ölçülmüş — atlanıyor",
                  flush=True)
        except Exception:
            filmler = []
    tamam = {f["film"] for f in filmler}
    secim = [(s, c) for s, c in secim if s not in tamam]
    t_bas = time.time()
    for i, (slug, sinif) in enumerate(secim, 1):
        kayit = film_kos(slug, sinif, motorlar, dc, sadakat_mod, dup_metrik,
                         saglik_mod, yukleyici, kural)
        filmler.append(kayit)
        satirlar = []
        for e, m in kayit["motorlar"].items():
            satirlar.append(
                f"{e}: {'ARIZA' if m['durum'] == 'ARIZA' else m['durum']}"
                + (f" boy={m['boy']} seg={m['segment']}"
                   f" recall={m.get('text_recall')} dup={m.get('dup_oran')}"
                   f" saglikli={m.get('saglikli')}" if m.get("boy") else
                   (f" hata={m.get('hata', '')[:80]}" if m["durum"] == "ARIZA" else "")))
        print(f"[{i}/{len(secim)}] {slug} ({kayit['kare']} kare, "
              f"{kayit['var_token']} var-token) :: " + " | ".join(satirlar),
              flush=True)
        # artımlı yazım — koşu yarıda kesilse elde olan kaybolmaz
        rapor = {"olusturma": _dt.datetime.now().isoformat(timespec="seconds"),
                 "motorlar": list(motorlar), "eksik_filmler": eksikler,
                 "filmler": filmler, "motor_ozeti": motor_ozeti(filmler),
                 "sure_s": round(time.time() - t_bas, 1)}
        cikti.write_text(json.dumps(rapor, ensure_ascii=False, indent=1),
                         encoding="utf-8")

    rapor["sure_s"] = round(time.time() - t_bas, 1)
    cikti.write_text(json.dumps(rapor, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    _markdown_yaz(rapor, cikti.with_suffix(".md"))
    print(json.dumps(rapor["motor_ozeti"], ensure_ascii=False, indent=1))
    return 0


def _markdown_yaz(rapor: dict, yol: Path) -> None:
    satirlar = [f"# Kompozitör kıyası — {rapor['olusturma']}", "",
                f"Motorlar: {', '.join(rapor['motorlar'])}"
                + (f" · EKSİK: {', '.join(rapor['eksik_filmler'])}" if rapor["eksik_filmler"] else ""),
                ""]
    baslik = ["| film | sınıf | kare |"]
    ayirici = ["|---|---|---|"]
    for e in rapor["motorlar"]:
        baslik[0] += f" {e}: boy/seg/recall/dup/sağlıklı |"
        ayirici[0] += "---|"
    satirlar += baslik + ayirici
    for f in rapor["filmler"]:
        satir = f"| {f['film']} | {f['sinif']} | {f['kare']} |"
        for e in rapor["motorlar"]:
            m = f["motorlar"].get(e, {})
            if m.get("durum") == "ARIZA":
                satir += " ARIZA |"
            elif m.get("boy"):
                satir += (f" {m['boy']}/{m['segment']}/{m.get('text_recall')}"
                          f"/{m.get('dup_oran')}"
                          f"/{'✓' if m.get('saglikli') else '✗'}"
                          + (" (çökme)" if m.get("cokme") else "") + " |")
            else:
                satir += f" {m.get('durum', '?')} |"
        satirlar.append(satir)
    satirlar += ["", "## Motor özeti", "", "| motor | üretti | sağlıklı | çökme | arıza | recall medyan | dup medyan | boy medyan |",
                 "|---|---|---|---|---|---|---|---|"]
    for e, o in rapor["motor_ozeti"].items():
        satirlar.append(f"| {e} | {o['uretti']}/{o['film']} | {o['saglikli']} | "
                        f"{o['cokme']} | {o['ariza']} | {o['recall_medyan']} | "
                        f"{o['dup_medyan']} | {o['boy_medyan']} |")
    satirlar.append(f"\nSüre: {rapor['sure_s']} s · Çıktılar: `scratch/kompozitor_kiyas/<motor>/`")
    yol.write_text("\n".join(satirlar), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
