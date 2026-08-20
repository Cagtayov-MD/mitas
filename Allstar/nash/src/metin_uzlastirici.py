"""Secilmis izlerde Latin v5 + v6 + istege bagli Tesseract uzlasmasi."""
from __future__ import annotations

import difflib
import json
import subprocess
import tempfile
import unicodedata
from collections import defaultdict
from pathlib import Path


class UzlastiriciArizasi(RuntimeError):
    pass


def ikinci_tani(satirlar: list[dict], kare_kok: Path, ayar: dict,
                detector_ayari: dict | None = None
                ) -> tuple[list[dict], dict, dict]:
    """Temsilci kırpımları ikinci modelle oku ve kanıtlı uzlaşma uygula."""
    cfg = ayar or {}
    if not satirlar or not bool(cfg.get("enabled", True)):
        return [dict(x) for x in satirlar], {}, {
            "enabled": bool(cfg.get("enabled", True)), "request_n": 0,
            "changed_n": 0, "conflict_n": 0,
        }
    kule = Path(__file__).resolve().parent.parent
    worker = Path(__file__).with_name("kirpim_worker.py")
    detector_cfg = detector_ayari or {}
    python = Path(str(cfg.get("python") or detector_cfg.get("python")
                      or (kule / "detector_venv/bin/python")))
    model = str(cfg.get("model", "PP-OCRv6_medium_rec"))
    model_dir = Path(str(cfg.get("model_dir", f"model/paddle/{model}")))
    if not model_dir.is_absolute():
        model_dir = kule / model_dir
    istekler = []
    satir_haritasi = {}
    for no, satir in enumerate(satirlar):
        if not _latin_agirlikli(str(satir.get("text", ""))):
            continue
        kirpimlar = satir.get("_ensemble_crops") or [{
            "kaynak": satir.get("kaynak"), "box": satir.get("box"),
            "text": satir.get("text"), "score": satir.get("score", 0.0),
        }]
        for kirpim_no, kirpim in enumerate(kirpimlar):
            kaynak = Path(kare_kok) / str(kirpim.get("kaynak", ""))
            kutu = kirpim.get("box")
            if not kaynak.is_file() or not _kutu_mu(kutu):
                continue
            kimlik = f"iz-{satir.get('iz_id', no + 1)}-{no}-k{kirpim_no}"
            istekler.append({
                "id": kimlik, "path": str(kaynak), "box": list(kutu),
                "primary_text": str(satir.get("text", "")),
                "primary_score": float(satir.get("score", 0.0)),
                "tesseract_eligible": kirpim_no == 0,
            })
            satir_haritasi[kimlik] = no
    if not istekler:
        return [dict(x) for x in satirlar], {}, {
            "enabled": True, "request_n": 0, "changed_n": 0,
            "conflict_n": 0,
        }

    with tempfile.TemporaryDirectory(prefix="nash-rec-") as gecici:
        girdi = Path(gecici) / "requests.json"
        cikti = Path(gecici) / "results.json"
        girdi.write_text(json.dumps(istekler, ensure_ascii=False), encoding="utf-8")
        komut = [str(python), str(worker), "--input", str(girdi),
                 "--output", str(cikti),
                 "--device", str(cfg.get("device", detector_cfg.get(
                     "device", "gpu:0"))),
                 "--model", model, "--model-dir", str(model_dir),
                 "--batch", str(max(1, int(cfg.get("batch", 16)))),
                 "--padding", str(max(0, int(cfg.get("padding", 2)))),
                 "--tesseract-lang", str(cfg.get("tesseract_lang", "tur")),
                 "--tesseract-psm", str(int(cfg.get("tesseract_psm", 7))),
                 "--tesseract-tavan", str(max(0, int(cfg.get(
                     "tesseract_tavan", 120))))]
        if bool(cfg.get("tesseract_enabled", True)):
            komut.append("--tesseract")
        try:
            sonuc = subprocess.run(
                komut, capture_output=True, text=True, shell=False,
                timeout=float(cfg.get("timeout_seconds", 300)))
        except subprocess.TimeoutExpired as exc:
            raise UzlastiriciArizasi("kirpim worker zaman asimi") from exc
        if sonuc.returncode or not cikti.is_file():
            ayrinti = (sonuc.stderr or sonuc.stdout or "sonuc yok").strip()
            raise UzlastiriciArizasi(
                f"kirpim worker rc={sonuc.returncode}: {ayrinti[-500:]}")
        try:
            belge = json.loads(cikti.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise UzlastiriciArizasi(f"kirpim sonucu bozuk: {exc}") from exc

    yeni_satirlar = [dict(x) for x in satirlar]
    for satir in yeni_satirlar:
        satir.pop("_ensemble_crops", None)
    grounding_degisim = {}
    ayrintilar = []
    changed_n = conflict_n = rejected_n = 0
    min_benzerlik = float(cfg.get("min_similarity", 0.68))
    tek_conflict_score = float(cfg.get("single_conflict_score", 0.90))
    reddedilen_indeksler = set()
    kayit_gruplari: dict[int, list[dict]] = defaultdict(list)
    for kayit in belge.get("results") or []:
        if kayit.get("id") in satir_haritasi and not kayit.get("error"):
            kayit_gruplari[satir_haritasi[kayit["id"]]].append(kayit)
    for no, kayitlar in sorted(kayit_gruplari.items()):
        onceki = str(yeni_satirlar[no].get("text", ""))
        ikincil, ikincil_skor, secilen_kayit = _coklu_ikincil_sec(
            kayitlar, onceki)
        tesseract = _coklu_tesseract_sec(kayitlar, onceki, ikincil)
        oy_orani = _coklu_oy_orani(kayitlar, onceki, ikincil)
        etkin_min_benzerlik = min_benzerlik
        if (len(kayitlar) >= 2
                and oy_orani >= float(cfg.get(
                    "multi_consensus_vote_ratio", 1.0))):
            etkin_min_benzerlik = min(
                etkin_min_benzerlik,
                float(cfg.get("multi_consensus_similarity", 0.74)))
        son, karar = uzlastir(
            onceki, ikincil, tesseract,
            min_benzerlik=etkin_min_benzerlik,
            primary_score=float(yeni_satirlar[no].get("score", 0.0) or 0.0),
            secondary_score=ikincil_skor)
        degisti = son != onceki
        if karar == "conflict":
            conflict_n += 1
            if (int(yeni_satirlar[no].get("support", 0) or 0) <= 1
                    and float(yeni_satirlar[no].get("score", 0.0) or 0.0)
                    < tek_conflict_score and ikincil_skor < tek_conflict_score):
                reddedilen_indeksler.add(no)
                rejected_n += 1
                grounding_degisim[(str(yeni_satirlar[no].get("kaynak", "")),
                                    _fold(onceki))] = None
        if degisti:
            changed_n += 1
            yeni_satirlar[no]["text"] = son
            yeni_satirlar[no]["motor"] = "paddle_ensemble"
            grounding_degisim[(str(yeni_satirlar[no].get("kaynak", "")),
                               _fold(onceki))] = son
        ayrintilar.append({
            "iz_id": yeni_satirlar[no].get("iz_id"),
            "kaynak": yeni_satirlar[no].get("kaynak"),
            "primary": onceki, "secondary": ikincil,
            "secondary_score": round(ikincil_skor, 6),
            "tesseract": tesseract,
            "result": son, "decision": karar, "changed": degisti,
            "accepted": no not in reddedilen_indeksler,
            "crop_n": len(kayitlar),
            "secondary_vote_ratio": round(oy_orani, 6),
            "effective_min_similarity": etkin_min_benzerlik,
            "selected_crop": secilen_kayit.get("id"),
            "secondary_candidates": [
                {"id": x.get("id"),
                 "text": _ikincil_sec(x, onceki)[0],
                 "score": round(_ikincil_sec(x, onceki)[1], 6)}
                for x in kayitlar
            ],
        })
    yeni_satirlar = [satir for no, satir in enumerate(yeni_satirlar)
                     if no not in reddedilen_indeksler]
    tani = {"enabled": True, "request_n": len(kayit_gruplari),
            "crop_request_n": len(istekler),
            "changed_n": changed_n, "conflict_n": conflict_n,
            "rejected_n": rejected_n,
            "worker": belge.get("meta") or {}, "items": ayrintilar}
    return yeni_satirlar, grounding_degisim, tani


def grounding_guncelle(grounding: dict, degisimler: dict) -> dict:
    sonuc = {}
    for kaynak, items in (grounding or {}).items():
        sonuc[kaynak] = []
        for item in items or []:
            yeni = dict(item)
            anahtar = (str(kaynak), _fold(str(item.get("label", ""))))
            if anahtar in degisimler:
                if degisimler[anahtar] is None:
                    continue
                yeni["label"] = degisimler[anahtar]
                yeni["engine"] = "paddle_ensemble"
            sonuc[kaynak].append(yeni)
    return sonuc


def uzlastir(primary: str, secondary: str, tesseract: str = "", *,
             min_benzerlik: float = 0.68, primary_score: float = 0.0,
             secondary_score: float = 0.0) -> tuple[str, str]:
    """v6 iskeletini koru; v5/Tesseract'tan uyumlu Turkce isaretleri al."""
    primary = _temiz(primary)
    secondary = _temiz(secondary)
    tesseract = _temiz(tesseract)
    if not secondary:
        return primary, "secondary_empty"
    oran = _benzerlik(primary, secondary)
    if oran < min_benzerlik:
        return primary, "conflict"

    # v6 temel harf/kelime iskeletidir. Daha fazla gercek kelime siniri v5'te
    # bulunuyorsa onun separator sablonunu v6 karakterlerine tasiriz.
    taban_metin = secondary
    if (primary_score >= secondary_score + 0.01
            and _taban_kompakt(primary) != _taban_kompakt(secondary)):
        taban_metin = primary
    if _kelime_ici_rakam(secondary) > _kelime_ici_rakam(primary):
        # "ışık şefi" -> "1s1k sefi" gibi daha yuksek skorlu olsa bile
        # harf kelimesinin icine rakam sokan okuma yapisal olarak gerilemedir.
        taban_metin = primary
    sablon = secondary
    if ((_ayirici_puani(primary), _buyuk_harf_orani(primary))
            > (_ayirici_puani(secondary), _buyuk_harf_orani(secondary))
            and len(_taban_kompakt(primary)) == len(_taban_kompakt(secondary))):
        sablon = primary
    if (tesseract and _taban_kompakt(tesseract) == _taban_kompakt(taban_metin)):
        # Tesseract'in ':'/'/' gibi tekil noktalama tahminini kanoniğe taşıma;
        # yalnız kelime sınırları üçüncü bağımsız oy olarak değerlidir.
        tess_sablon = " ".join("".join(
            c if c.isalnum() else " " for c in tesseract).split())
        if _ayirici_puani(tess_sablon) > _ayirici_puani(sablon):
            sablon = tess_sablon
    taban = list(_kompakt_karakterler(taban_metin))
    for kaynak in (primary, secondary):
        if not kaynak or _benzerlik(taban_metin, kaynak) < min_benzerlik:
            continue
        _diyakritik_tasi(taban, taban_metin, kaynak)
    turkce_kanit = any(c in "ıİşŞğĞçÇöÖüÜ" for c in primary + secondary)
    if (tesseract and turkce_kanit
            and _benzerlik(taban_metin, tesseract) >= min_benzerlik
            and len(_taban_kompakt(tesseract)) == len(_taban_kompakt(taban_metin))):
        # Ek/eksik karakterli Tesseract dizisi yüksek benzerlik alsa bile
        # diyakritikleri bir pozisyon kaydırabilir (FUNDA -> ĞUNDA). Ayrıca
        # tek hakemin "oo"yu "öö" yapması gibi çift komşu ekler geri alınır.
        tesseract_oncesi = list(taban)
        _diyakritik_tasi(taban, taban_metin, tesseract)
        for i in range(len(taban) - 1):
            if (_taban_harf(taban[i]) == _taban_harf(taban[i + 1])
                    and _diyakritik_puani(taban[i])
                    and _diyakritik_puani(taban[i + 1])
                    and not _diyakritik_puani(tesseract_oncesi[i])
                    and not _diyakritik_puani(tesseract_oncesi[i + 1])):
                taban[i:i + 2] = tesseract_oncesi[i:i + 2]
    # Iki Paddle iskeleti farkli sayida karakter urettiğinde birinin bosluk
    # sablonuna digerinin harflerini zorla sigdirmak, tum bosluklari yok eden
    # yapay bir kelime üretir. Bu durumda secilmis taban kendi ayiricilariyla
    # kalir; uzlasma yalniz guvenli diyakritikleri tasir.
    if len(_kompakt_karakterler(sablon)) != len(taban):
        sablon = taban_metin
    sonuc = _sablona_yerlestir(sablon, taban, fallback=taban_metin)
    return (_temiz(sonuc) or primary), "consensus"


def _ikincil_sec(kayit: dict, primary: str) -> tuple[str, float]:
    adaylar = [
        (str(kayit.get("secondary_text", "")),
         float(kayit.get("secondary_score", 0.0))),
        (str(kayit.get("secondary_sharp_text", "")),
         float(kayit.get("secondary_sharp_score", 0.0))),
    ]
    return max(adaylar, key=lambda x: (
        x[1] + 0.15 * _benzerlik(primary, x[0])
        + 0.06 * _ayirici_puani(x[0]), len(_taban_kompakt(x[0]))))


def _coklu_ikincil_sec(kayitlar: list[dict], primary: str
                       ) -> tuple[str, float, dict]:
    """Farkli kare kirpimlarindan en guvenli v6 okumasini sec."""
    adaylar = []
    for kayit in kayitlar:
        metin, skor = _ikincil_sec(kayit, primary)
        if metin:
            adaylar.append((metin, skor, kayit))
    if not adaylar:
        return "", 0.0, {}

    def puan(aday) -> tuple[float, int]:
        metin, skor, _kayit = aday
        diger = [x[0] for x in adaylar if x is not aday]
        coklu_uyum = (sum(_benzerlik(metin, x) for x in diger) / len(diger)
                      if diger else 0.5)
        ayni_oy = sum(_fold(metin) == _fold(x[0]) for x in adaylar)
        oy_orani = ayni_oy / len(adaylar)
        return (skor + 0.12 * _benzerlik(primary, metin)
                + 0.12 * coklu_uyum + 0.08 * oy_orani
                + 0.03 * _ayirici_puani(metin),
                len(_taban_kompakt(metin)))

    return max(adaylar, key=puan)


def _coklu_tesseract_sec(kayitlar: list[dict], primary: str,
                         secondary: str) -> str:
    adaylar = [str(x.get("tesseract_text", "")) for x in kayitlar
               if str(x.get("tesseract_text", "")).strip()]
    if not adaylar:
        return ""
    return max(adaylar, key=lambda x: (
        _benzerlik(x, secondary) + _benzerlik(x, primary),
        _ayirici_puani(x), len(_taban_kompakt(x))))


def _coklu_oy_orani(kayitlar: list[dict], primary: str,
                     secilen: str) -> float:
    adaylar = [_ikincil_sec(x, primary)[0] for x in kayitlar]
    adaylar = [x for x in adaylar if x]
    if not adaylar or not secilen:
        return 0.0
    return sum(_fold(x) == _fold(secilen) for x in adaylar) / len(adaylar)


def _diyakritik_tasi(taban: list[str], hedef: str, kaynak: str) -> None:
    hedef_chars = _kompakt_karakterler(hedef)
    kaynak_chars = _kompakt_karakterler(kaynak)
    a = "".join(_taban_harf(c) for c in hedef_chars)
    b = "".join(_taban_harf(c) for c in kaynak_chars)
    for blok in difflib.SequenceMatcher(None, a, b).get_matching_blocks():
        for ofset in range(blok.size):
            hi, ki = blok.a + ofset, blok.b + ofset
            if hi >= len(taban) or ki >= len(kaynak_chars):
                continue
            aday = kaynak_chars[ki]
            if (_taban_harf(taban[hi]) == _taban_harf(aday)
                    and _diyakritik_puani(aday) > _diyakritik_puani(taban[hi])):
                taban[hi] = aday.upper() if taban[hi].isupper() else aday


def _sablona_yerlestir(sablon: str, karakterler: list[str],
                       fallback: str = "") -> str:
    if len(_kompakt_karakterler(sablon)) != len(karakterler):
        return fallback or sablon
    sonuc, no = [], 0
    for c in sablon:
        if c.isalnum():
            yeni = karakterler[no]
            if c.islower():
                yeni = yeni.lower()
            elif c.isupper():
                yeni = yeni.upper()
            sonuc.append(yeni)
            no += 1
        elif c == "/":
            sonuc.append(" ")
        else:
            sonuc.append(c)
    return "".join(sonuc)


def _diyakritik_puani(c: str) -> int:
    if not c.isalpha():
        return 0
    return int(any(unicodedata.combining(x) for x in unicodedata.normalize(
        "NFKD", c)) or c in "ıİşŞğĞçÇöÖüÜ")


def _kelime_ici_rakam(metin: str) -> int:
    return sum(any(c.isalpha() for c in parca)
               and any(c.isdigit() for c in parca)
               for parca in metin.split())


def _taban_harf(c: str) -> str:
    ozel = {"ı": "i", "İ": "i"}
    if c in ozel:
        return ozel[c]
    s = unicodedata.normalize("NFKD", c.lower())
    return "".join(x for x in s if not unicodedata.combining(x))


def _kompakt_karakterler(metin: str) -> list[str]:
    return [c for c in metin if c.isalnum()]


def _taban_kompakt(metin: str) -> str:
    return "".join(_taban_harf(c) for c in _kompakt_karakterler(metin))


def _fold(metin: str) -> str:
    return " ".join(_taban_kompakt(kelime) for kelime in metin.split())


def _benzerlik(a: str, b: str) -> float:
    aa, bb = _taban_kompakt(a), _taban_kompakt(b)
    if not aa or not bb:
        return 0.0
    return difflib.SequenceMatcher(None, aa, bb).ratio()


def _ayirici_puani(metin: str) -> int:
    # Tekrarlanan bosluk puan kazandirmasin; nokta ve tire kredi bilgisidir.
    temiz = _temiz(metin)
    return len(temiz.split()) - 1 + sum(c in ".-" for c in temiz)


def _buyuk_harf_orani(metin: str) -> float:
    harfler = [c for c in metin if c.isalpha()]
    return (sum(c.isupper() for c in harfler) / len(harfler)
            if harfler else 0.0)


def _temiz(metin: str) -> str:
    return unicodedata.normalize(
        "NFC", " ".join((metin or "").strip().split()))


def _latin_agirlikli(metin: str) -> bool:
    harfler = [c for c in metin if c.isalpha()]
    if not harfler:
        return False
    latin = sum("LATIN" in unicodedata.name(c, "") for c in harfler)
    return latin / len(harfler) >= 0.60


def _kutu_mu(kutu) -> bool:
    return (isinstance(kutu, (list, tuple)) and len(kutu) == 4
            and all(isinstance(x, (int, float)) and not isinstance(x, bool)
                    for x in kutu)
            and 0 <= kutu[0] < kutu[2] <= 1
            and 0 <= kutu[1] < kutu[3] <= 1)
