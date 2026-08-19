"""Paddle-first OCR ve hedefli DeepSeek fallback birlestirmesi."""
from __future__ import annotations

import difflib
import math
import statistics
import time
import unicodedata
from collections import defaultdict
from pathlib import Path

import okuyucu


def paddle_oku(yollar: list[Path], analizler: dict, ayar: dict,
               dedup_esigi: float = 0.92,
               fallback_yollari: list[Path] | None = None
               ) -> tuple[list[dict], dict, list[Path], dict]:
    """Paddle satirlarini zamansal uzlasmayla oku; belirsizi isaretle.

    `yollar` ucuz Paddle OCR yapilmis tum kronolojik havuz olabilir.
    `fallback_yollari` ise DeepSeek'e gitmesine izin verilen text-run
    temsilcileridir; boylece ana havuzun tamami agir modele sizmaz.
    """
    t0 = time.monotonic()
    kabul_esigi = float(ayar.get("paddle_kabul_esigi", 0.70))
    fallback_esigi = float(ayar.get("deepseek_fallback_esigi", 0.88))
    uzlasma_penceresi = max(0, int(ayar.get("paddle_uzlasma_penceresi", 12)))
    uzlasma_esigi = float(ayar.get("paddle_uzlasma_esigi", 0.82))
    yogun_kare_min_satir = max(2, int(ayar.get(
        "paddle_yogun_kare_min_satir", 8)))
    ham_tavan = ayar.get("deepseek_fallback_tavan", 20)
    if isinstance(ham_tavan, dict):
        ham_tavan = ham_tavan.get(str(ayar.get("bolum", "cikis")), 20)
    fallback_tavan = max(0, int(ham_tavan))
    fallback_izin = {p.name for p in (fallback_yollari or yollar)}
    logo_orani = float(ayar.get("logo_kalici_oran", 0.80))
    kalici_logolar = _kalici_logo_imzalari(yollar, analizler, logo_orani)
    # ham_tavan deseni: bölme sözlüğü verilirse ilgili bölümün eşiği,
    # yoksa skalar/varsayılan. Çiçek Taksi 2026-08-19: giriş jeneriğinde
    # kredi satırları altyazı geometrisindedir — giris için kapatılabilir.
    altyazi = ayar.get("altyazi_y", 0.80)
    if isinstance(altyazi, dict):
        altyazi = altyazi.get(str(ayar.get("bolum", "cikis")), 0.80)
    altyazi_y = float(altyazi)
    grounding: dict[str, list[dict]] = defaultdict(list)
    skorlar: list[float] = []
    fallback_komsu = max(0, int(ayar.get("paddle_fallback_komsu", 4)))
    fallback_acik = bool(ayar.get("deepseek_fallback_enabled", True))
    film_kabul_min_satir = max(1, int(ayar.get(
        "paddle_film_kabul_min_satir", 8)))
    fallback_adaylari: list[dict] = []
    adaylar: list[dict] = []
    elenen: list[dict] = []

    for kare_sira, p in enumerate(yollar, start=1):
        analiz = analizler.get(p.name) or {}
        ham_satirlar = analiz.get("lines") or []
        ham_kutular = [x for x in (analiz.get("boxes") or []) if _kutu_mu(x)]
        kutular = [x for x in ham_kutular if not (
            _logo_adayi(x) and _kutu_imzasi(x) in kalici_logolar)]
        okunabilir_kutular = [x for x in kutular if _okunabilir_metin_kutusu(x)]
        ham_dolu_n = 0
        ham_gecerli_n = 0
        yalniz_altyazi = bool(kutular) and all(
            (x[1] + x[3]) / 2 >= altyazi_y for x in kutular)
        kabul = []
        dusuk: list[dict] = []
        for oge in ham_satirlar:
            try:
                metin = okuyucu._kirp(str(oge.get("text", "")))
                skor = float(oge.get("score", 0.0))
                kutu = oge.get("box")
            except (TypeError, ValueError):
                continue
            if not metin or not _kutu_mu(kutu):
                continue
            ham_dolu_n += 1
            if _logo_adayi(kutu) and _kutu_imzasi(kutu) in kalici_logolar:
                elenen.append({"kaynak": p.name, "text": metin,
                               "sebep": "kalici_logo", "score": round(skor, 6)})
                continue
            # Alt bant tek basina yeterli degil: jenerik isimleri de ekranin
            # altinda durabilir. Secim katmaniyla ayni muhafazakar kural:
            # ancak karedeki TUM temiz kutular alt banda sikismissa altyazi.
            if yalniz_altyazi:
                elenen.append({"kaynak": p.name, "text": metin,
                               "sebep": "altyazi", "score": round(skor, 6)})
                continue
            sebep = _paddle_veto(metin)
            if sebep:
                elenen.append({"kaynak": p.name, "text": metin,
                               "sebep": sebep, "score": round(skor, 6)})
                continue
            ham_gecerli_n += 1
            skorlar.append(skor)
            if skor < fallback_esigi:
                dusuk.append({"fold": okuyucu.fold(metin), "box": kutu,
                              "score": skor})
            if skor < kabul_esigi:
                continue
            kabul.append((metin, skor, kutu))
            adaylar.append({"kaynak": p.name, "kare_sira": kare_sira,
                            "satir_sira": len(kabul) - 1, "text": metin,
                            "fold": okuyucu.fold(metin), "score": skor,
                            "box": kutu})
        if p.name not in fallback_izin:
            continue
        if analiz.get("error"):
            fallback_adaylari.append({"oncelik": 0, "skor": 0.0, "yol": p,
                                      "kare_sira": kare_sira,
                                      "sebep": "paddle_hata", "boxes": kutular,
                                      "dusuk": dusuk})
        elif (okunabilir_kutular and not kabul and not yalniz_altyazi
              and not (ham_dolu_n and not ham_gecerli_n)):
            fallback_adaylari.append({"oncelik": 1, "skor": 0.0, "yol": p,
                                      "kare_sira": kare_sira,
                                      "sebep": "kutu_var_metin_yok",
                                      "boxes": okunabilir_kutular, "dusuk": dusuk})
        elif dusuk:
            fallback_adaylari.append({"oncelik": 2,
                                      "skor": min(x["score"] for x in dusuk),
                                      "yol": p, "kare_sira": kare_sira,
                                      "sebep": "dusuk_guven", "boxes": kutular,
                                      "dusuk": dusuk})

    t_ayiklama = time.monotonic()
    kumeler: list[dict] = []
    aktif_kumeler: list[dict] = []
    for aday in adaylar:
        # Eski uygulama pencereden cikmis binlerce kumeyi de her satirda tekrar
        # tarardi; uzun kayan jenerikte O(n²) olup cag_output26'da 114 saniye
        # harcadi. Yalniz aktif zaman penceresini ve son 8 yazim varyantini
        # eslestirmek ayni karari sinirli maliyetle verir.
        aktif_kumeler = [
            k for k in aktif_kumeler
            if aday["kare_sira"] - k["son_sira"] <= uzlasma_penceresi
        ]
        uygun = [k for k in aktif_kumeler
                 if _kume_varyanti(aday, k, uzlasma_esigi)]
        if uygun:
            kume = max(uygun, key=lambda k: max(
                difflib.SequenceMatcher(None, aday["fold"], fold).ratio()
                for fold in k["esleme_foldlari"]))
            kume["ogeler"].append(aday)
            kume["son_sira"] = aday["kare_sira"]
            kume["esleme_foldlari"] = (
                kume["esleme_foldlari"] + [aday["fold"]])[-8:]
            kume["esleme_ozetleri"] = [
                _metin_ozeti(x) for x in kume["esleme_foldlari"]
            ]
            kume["esleme_kutulari"] = (
                kume["esleme_kutulari"] + [aday["box"]])[-8:]
            kume["esleme_siralari"] = (
                kume["esleme_siralari"] + [aday["kare_sira"]])[-8:]
        else:
            yeni_kume = {"ilk_sira": aday["kare_sira"],
                         "son_sira": aday["kare_sira"], "ogeler": [aday],
                         "esleme_foldlari": [aday["fold"]],
                         "esleme_ozetleri": [_metin_ozeti(aday["fold"])],
                         "esleme_kutulari": [aday["box"]],
                         "esleme_siralari": [aday["kare_sira"]]}
            kumeler.append(yeni_kume)
            aktif_kumeler.append(yeni_kume)

    t_kumeleme = time.monotonic()
    temsilciler = [_kume_temsilcisi(kume["ogeler"]) for kume in kumeler]
    kare_aday_sayisi: dict[int, int] = defaultdict(int)
    for aday in adaylar:
        kare_aday_sayisi[int(aday["kare_sira"])] += 1
    kararli_kumeler = [
        (kume, temsilci) for kume, temsilci in zip(kumeler, temsilciler)
        if len(kume["ogeler"]) >= 2
    ]
    satirlar = []
    for kume, secilen in zip(kumeler, temsilciler):
        alnum_n = sum(c.isalnum() for c in secilen["text"])
        if alnum_n <= 2 or (alnum_n <= 4 and len(kume["ogeler"]) < 2
                            and secilen["score"] < 0.90):
            elenen.append({"kaynak": secilen["kaynak"], "text": secilen["text"],
                           "sebep": "kararsiz_kisa",
                           "score": round(secilen["score"], 6)})
            continue
        if (len(kume["ogeler"]) == 1
                and kare_aday_sayisi[int(secilen["kare_sira"])]
                >= yogun_kare_min_satir):
            # Kayan jenerikte bir isim ekranda cok sayida ardışık kare kalır.
            # Tek karede gorulen, ayni anda onlarca satirin aktigi varyantlar
            # gercek yeni kredi degil; giris/cikis kenarindaki parcali OCR'dir.
            # Az satirli tek kartlar bu kapidan etkilenmez.
            elenen.append({"kaynak": secilen["kaynak"], "text": secilen["text"],
                           "sebep": "yogun_akista_tek_kare",
                           "score": round(secilen["score"], 6)})
            continue
        if (len(kume["ogeler"]) == 1
                and _gecis_bilesigi(secilen, kararli_kumeler)):
            # Cross-fade aninda Paddle iki ayri jenerik satirini tek kutuda
            # birlestirebiliyor ("GÖRUNIMÜZIK", "SENAYONETMANIMCI"). Tek
            # karelik bu satir, iki veya daha cok karede gorulen temiz bir
            # satirin parcasiysa yeni kredi degildir.
            elenen.append({"kaynak": secilen["kaynak"], "text": secilen["text"],
                           "sebep": "gecis_bilesik",
                           "score": round(secilen["score"], 6)})
            continue
        satirlar.append({"kaynak": secilen["kaynak"],
                         "sayfa_sira": secilen["kare_sira"],
                         "satir_sira": secilen["satir_sira"],
                         "text": secilen["text"], "motor": "paddle",
                         "score": round(secilen["score"], 6),
                         "support": len(kume["ogeler"]),
                         "box": list(secilen["box"])})
        grounding[secilen["kaynak"]].append({
            "label": secilen["text"],
            "boxes_999": [[round(v * 999, 3) for v in secilen["box"]]],
            "score": round(secilen["score"], 6), "engine": "paddle",
            "support": len(kume["ogeler"]),
        })
    satirlar.sort(key=lambda x: (x["sayfa_sira"], x["satir_sira"]))
    t_satir_secimi = time.monotonic()
    temporal_cozulmus = [
        x for x in fallback_adaylari
        if x["sebep"] != "paddle_hata"
        and _fallback_temporal_cozuldu(x, kararli_kumeler, fallback_komsu)
    ]
    film_kapisi_kapatilan: list[dict] = []
    config_kapatilan: list[dict] = []
    film_kapisi_gecti = len(satirlar) >= film_kabul_min_satir
    if not fallback_acik:
        cozulmus_adlar = {x["yol"].name for x in temporal_cozulmus}
        config_kapatilan = [
            x for x in fallback_adaylari if x["yol"].name not in cozulmus_adlar
        ]
    elif film_kapisi_gecti:
        # Kare duzeyindeki tek bir dusuk skor, onlarca temiz satir cikarmis
        # Paddle'i basarisiz sayamaz. Bu eski kapı cag_output01/02/03'te
        # sirasiyla 93/108/56 Paddle satirina ragmen 18/20/20 agir cagri acti.
        # DeepSeek film katmaninin kalite kapisi gecmediginde devreye girer.
        cozulmus_adlar = {x["yol"].name for x in temporal_cozulmus}
        film_kapisi_kapatilan = [
            x for x in fallback_adaylari if x["yol"].name not in cozulmus_adlar
        ]
    cozulmus_adaylar = (temporal_cozulmus + film_kapisi_kapatilan
                        + config_kapatilan)
    cozulmus_ad = {x["yol"].name for x in cozulmus_adaylar}
    fallback_adaylari = [x for x in fallback_adaylari
                         if x["yol"].name not in cozulmus_ad]
    fallback_adaylari.sort(key=lambda x: (x["oncelik"], x["skor"], x["yol"].name))
    secilen_adaylar = fallback_adaylari[:fallback_tavan]
    fallback = sorted((x["yol"] for x in secilen_adaylar), key=lambda p: p.name)
    fallback_nedenleri = {x["yol"].name: x["sebep"] for x in secilen_adaylar}
    kanit = {
        "sayfa_hata_n": 0,
        "sayfa_basarili_n": len(yollar),
        "sayfa_hatalari": [],
        "elenen_n": len(elenen),
        "elenme_sebepleri": _sebep_say(elenen),
        "elenen": elenen[:50],
        "paddle_satir_n": len(satirlar),
        "paddle_ham_satir_n": len(adaylar),
        "paddle_kalici_logo_imza_n": len(kalici_logolar),
        "paddle_uzlasma_kume_n": len(kumeler),
        "paddle_uzlasma_penceresi": uzlasma_penceresi,
        "paddle_uzlasma_esigi": uzlasma_esigi,
        "paddle_yogun_kare_min_satir": yogun_kare_min_satir,
        "paddle_kume_destekleri": [
            {"text": temsilci["text"], "kaynak": temsilci["kaynak"],
             "destek": len(kume["ogeler"])}
            for kume, temsilci in zip(kumeler, temsilciler)
        ],
        "paddle_skor_min": round(min(skorlar), 4) if skorlar else None,
        "paddle_skor_medyan": round(statistics.median(skorlar), 4) if skorlar else None,
        "paddle_kabul_esigi": kabul_esigi,
        "paddle_film_kabul_min_satir": film_kabul_min_satir,
        "paddle_film_kapisi_gecti": film_kapisi_gecti,
        "deepseek_fallback_esigi": fallback_esigi,
        "deepseek_fallback_enabled": fallback_acik,
        "deepseek_fallback_ham_aday_n": len(fallback_adaylari) + len(cozulmus_adaylar),
        "deepseek_fallback_temporal_cozuldu_n": len(temporal_cozulmus),
        "deepseek_fallback_temporal_cozuldu": {
            x["yol"].name: x["sebep"] for x in temporal_cozulmus
        },
        "deepseek_fallback_film_kapisi_kapatti_n": len(film_kapisi_kapatilan),
        "deepseek_fallback_film_kapisi_kapatti": {
            x["yol"].name: x["sebep"] for x in film_kapisi_kapatilan
        },
        "deepseek_fallback_config_kapatti_n": len(config_kapatilan),
        "deepseek_fallback_config_kapatti": {
            x["yol"].name: x["sebep"] for x in config_kapatilan
        },
        "deepseek_fallback_aday_n": len(fallback_adaylari),
        "deepseek_fallback_n": len(fallback),
        "deepseek_fallback_tavan": fallback_tavan,
        "deepseek_fallback_nedenleri": fallback_nedenleri,
        "paddle_postprocess_sureleri": {
            "ayiklama_sn": round(t_ayiklama - t0, 3),
            "kumeleme_sn": round(t_kumeleme - t_ayiklama, 3),
            "satir_secimi_sn": round(t_satir_secimi - t_kumeleme, 3),
            "fallback_sn": round(time.monotonic() - t_satir_secimi, 3),
            "toplam_sn": round(time.monotonic() - t0, 3),
        },
    }
    return satirlar, kanit, fallback, dict(grounding)


def birlestir(paddle_satirlari: list[dict], deepseek_satirlari: list[dict],
              tum_yollar: list[Path]) -> tuple[list[dict], dict]:
    """Paddle'i koru; DeepSeek'ten yalniz gercekten yeni satir ekle."""
    sonuc = [dict(x) for x in paddle_satirlari]
    eklenen, eslesen = 0, 0
    deepseek_elenen: list[dict] = []
    for aday in deepseek_satirlari:
        red = _deepseek_yeni_satir_veto(str(aday.get("text", "")))
        if red:
            deepseek_elenen.append({"kaynak": aday.get("kaynak"),
                                    "text": aday.get("text"), "sebep": red})
            continue
        ayni_kaynak = [x for x in sonuc if x.get("kaynak") == aday.get("kaynak")]
        if any(_ayni_metin(str(aday.get("text", "")), str(x.get("text", "")))
               for x in sonuc):
            eslesen += 1
            continue
        aday_token = set(okuyucu.fold(str(aday.get("text", ""))).split())
        kaynak_token = set().union(*(
            set(okuyucu.fold(str(x.get("text", ""))).split()) for x in ayni_kaynak
        )) if ayni_kaynak else set()
        if aday_token and aday_token <= kaynak_token:
            eslesen += 1
            continue
        yeni = dict(aday)
        yeni["motor"] = "deepseek_fallback"
        sonuc.append(yeni)
        eklenen += 1

    sira = {p.name: i for i, p in enumerate(tum_yollar, start=1)}
    sonuc.sort(key=lambda x: (sira.get(str(x.get("kaynak")), 10**9),
                              int(x.get("satir_sira", 0)),
                              0 if x.get("motor") != "deepseek_fallback" else 1))
    sayac: dict[str, int] = {}
    for row in sonuc:
        kaynak = str(row.get("kaynak", ""))
        row["sayfa_sira"] = sira.get(kaynak, int(row.get("sayfa_sira", 0)))
        row["satir_sira"] = sayac.get(kaynak, 0)
        sayac[kaynak] = row["satir_sira"] + 1
        row.setdefault("motor", "paddle")
    red_sebepleri: dict[str, int] = {}
    for oge in deepseek_elenen:
        red_sebepleri[oge["sebep"]] = red_sebepleri.get(oge["sebep"], 0) + 1
    return sonuc, {"deepseek_yeni_satir_n": eklenen,
                   "deepseek_paddle_eslesme_n": eslesen,
                   "deepseek_birlesim_elendi_n": len(deepseek_elenen),
                   "deepseek_birlesim_elenme_sebepleri": red_sebepleri,
                   "deepseek_birlesim_elenen": deepseek_elenen[:50]}


def script_satirlarini_sec(satirlar: list[dict], grounding: dict,
                           script: str = "arabic", min_oran: float = 0.35
                           ) -> tuple[list[dict], dict, dict]:
    """Ikinci Paddle tanıyıcıdan yalnız hedef yazı sistemini kabul et."""
    if script not in {"arabic", "eslav"}:
        raise ValueError(f"desteklenmeyen Paddle script fallback: {script!r}")
    karakter = _arap_karakteri if script == "arabic" else _kiril_karakteri
    secilen = []
    secilen_grounding: dict[str, list[dict]] = defaultdict(list)
    for row in satirlar:
        metin = str(row.get("text", ""))
        harfler = [c for c in metin if c.isalpha()]
        oran = (sum(karakter(c) for c in harfler) / len(harfler)
                if harfler else 0.0)
        if oran < min_oran:
            continue
        yeni = dict(row)
        yeni["motor"] = f"paddle_{script}"
        yeni["script_ratio"] = round(oran, 6)
        secilen.append(yeni)
        kaynak = str(row.get("kaynak", ""))
        for kanit in grounding.get(kaynak) or []:
            if _ayni_metin(metin, str(kanit.get("label", ""))):
                oge = dict(kanit)
                oge["engine"] = f"paddle_{script}"
                secilen_grounding[kaynak].append(oge)
    return secilen, dict(secilen_grounding), {
        "ham_satir_n": len(satirlar), "kabul_satir_n": len(secilen),
        "script": script, "min_script_orani": min_oran,
    }


def script_birlestir(birincil: list[dict], birincil_grounding: dict,
                     script_satirlari: list[dict], script_grounding: dict,
                     *, latin_min_score: float = 0.90,
                     latin_min_support: int = 2,
                     overlap_iou: float = 0.30,
                     script_ham_satirlari: list[dict] | None = None,
                     latin_corroboration_similarity: float = 0.82,
                     target_script: str = "eslav"
                     ) -> tuple[list[dict], dict, dict]:
    """Script takeover yaparken kanıtlı, ayrı konumdaki Latin krediyi koru.

    Aynı bbox bölgesindeki Latin tanıma hedef-script sonucu tarafından
    değiştirilir. Ayrı bir satırdaki yüksek güvenli ve zamansal destekli Latin
    kredi ise çift dilli jenerik olabilir. Ancak Latin tanıyıcının Kiril
    homogliflerini Latin sanmasını önlemek için aynı satır ikinci script
    tanıyıcısında da yakın karede ve aynı bölgede Latin olarak okunmalıdır.
    """
    hedef_kutular: dict[str, list[list[float]]] = defaultdict(list)
    for row in script_satirlari:
        box = row.get("box")
        if _kutu_mu(box):
            hedef_kutular[str(row.get("kaynak", ""))].append(list(box))

    korunan = []
    elenen = []
    ham_script = list(script_ham_satirlari or [])
    for row in birincil:
        score = float(row.get("score", 0.0) or 0.0)
        support = int(row.get("support", 0) or 0)
        box = row.get("box")
        ayni_bolge = bool(_kutu_mu(box) and any(
            _iou(box, hedef) >= overlap_iou
            for hedef in hedef_kutular.get(str(row.get("kaynak", "")), [])))
        capraz_gerekli = target_script == "eslav"
        capraz = (_latin_capraz_dogrulandi(
            row, ham_script, overlap_iou, latin_corroboration_similarity)
            if capraz_gerekli else None)
        if (score >= latin_min_score and support >= latin_min_support
                and _kutu_mu(box) and not ayni_bolge
                and capraz is not False):
            yeni = dict(row)
            yeni["motor"] = "paddle_latin_preserved"
            korunan.append(yeni)
        else:
            elenen.append({
                "kaynak": row.get("kaynak"), "text": row.get("text"),
                "score": round(score, 6), "support": support,
                "overlap": ayni_bolge, "capraz_dogrulama": capraz,
                "sebep": "script_takeover_gibberish",
            })

    sonuc = [*korunan, *(dict(row) for row in script_satirlari)]
    sonuc.sort(key=lambda row: (
        int(row.get("sayfa_sira", 0)), int(row.get("satir_sira", 0)),
        str(row.get("text", ""))))
    izin = {(str(row.get("kaynak", "")), okuyucu.fold(str(row.get("text", ""))))
            for row in sonuc}
    kanit: dict[str, list[dict]] = defaultdict(list)
    for kaynak, items in birincil_grounding.items():
        for item in items or []:
            if (str(kaynak), okuyucu.fold(str(item.get("label", "")))) in izin:
                kanit[str(kaynak)].append(dict(item))
    for kaynak, items in script_grounding.items():
        for item in items or []:
            if (str(kaynak), okuyucu.fold(str(item.get("label", "")))) in izin:
                kanit[str(kaynak)].append(dict(item))
    return sonuc, dict(kanit), {
        "script_takeover": True,
        "script_satir_n": len(script_satirlari),
        "latin_korunan_n": len(korunan),
        "latin_elenen_n": len(elenen),
        "latin_min_score": latin_min_score,
        "latin_min_support": latin_min_support,
        "overlap_iou": overlap_iou,
        "latin_corroboration_required": target_script == "eslav",
        "latin_corroboration_similarity": latin_corroboration_similarity,
        "elenen": elenen[:100],
    }


def _latin_capraz_dogrulandi(row: dict, script_ham_satirlari: list[dict],
                             min_iou: float, min_similarity: float) -> bool:
    """İkinci tanıyıcıdaki bağımsız Latin okumasıyla satırı doğrula."""
    box = row.get("box")
    if not _kutu_mu(box):
        return False
    metin = str(row.get("text", ""))
    sayfa = int(row.get("sayfa_sira", 0) or 0)
    for aday in script_ham_satirlari:
        aday_metin = str(aday.get("text", ""))
        if _latin_orani(aday_metin) < 0.60:
            continue
        aday_box = aday.get("box")
        if not _kutu_mu(aday_box) or _iou(box, aday_box) < min_iou:
            continue
        aday_sayfa = int(aday.get("sayfa_sira", 0) or 0)
        ayni_kaynak = str(row.get("kaynak", "")) == str(
            aday.get("kaynak", ""))
        if not ayni_kaynak and abs(sayfa - aday_sayfa) > 2:
            continue
        if difflib.SequenceMatcher(
                None, okuyucu.fold(metin),
                okuyucu.fold(aday_metin)).ratio() >= min_similarity:
            return True
    return False


def _latin_orani(metin: str) -> float:
    harfler = [c for c in metin if c.isalpha()]
    if not harfler:
        return 0.0
    latin = sum("LATIN" in unicodedata.name(c, "") for c in harfler)
    return latin / len(harfler)


def _ayni_metin(a: str, b: str) -> bool:
    fa, fb = okuyucu.fold(a), okuyucu.fold(b)
    if not fa or not fb:
        return False
    if fa == fb:
        return True
    return difflib.SequenceMatcher(None, fa, fb).ratio() >= 0.82


def _deepseek_yeni_satir_veto(metin: str) -> str | None:
    metin = okuyucu._kirp(metin)
    f = okuyucu.fold(metin)
    alnum_n = sum(c.isalnum() for c in f)
    if alnum_n < 4:
        return "cok_kisa"
    if len(metin) > 180:
        return "asiri_uzun"
    kelimeler = f.split()
    if len(kelimeler) >= 4 and sum(len(x) == 1 for x in kelimeler) >= math.ceil(
            len(kelimeler) * 0.6):
        return "parcali"
    return _paddle_veto(metin)


def _arap_karakteri(c: str) -> bool:
    n = ord(c)
    return (0x0600 <= n <= 0x06FF or 0x0750 <= n <= 0x077F
            or 0x08A0 <= n <= 0x08FF or 0xFB50 <= n <= 0xFDFF
            or 0xFE70 <= n <= 0xFEFF)


def _kiril_karakteri(c: str) -> bool:
    n = ord(c)
    return (0x0400 <= n <= 0x052F or 0x1C80 <= n <= 0x1C8F
            or 0x2DE0 <= n <= 0x2DFF or 0xA640 <= n <= 0xA69F)


def _iou(a: list[float], b: list[float]) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    kes = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    alan_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    alan_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    birlik = alan_a + alan_b - kes
    return kes / birlik if birlik > 0 else 0.0


def _varyant(a: str, b: str, esik: float) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    if min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)):
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= esik


def _metin_ozeti(metin: str) -> tuple[int, frozenset[str]]:
    kompakt = metin.replace(" ", "")
    return len(metin), frozenset(
        kompakt[i:i + 3] for i in range(max(0, len(kompakt) - 2)))


def _kume_varyanti(aday: dict, kume: dict, esik: float) -> bool:
    """Pahali SequenceMatcher'dan once kayipsiz/gevsek ucuz aday filtresi.

    0.82 benzerlikte uzunluklarin teorik ust siniri ve en az bir ortak
    trigram bulunmasi gerekir. Kisa metinlerde trigram kapisi uygulanmaz.
    Kayan jenerikte ayni anda yuzlerce satir varken ilgisiz isimlerin milyonlarca
    SequenceMatcher cagrisi acmasini engeller.
    """
    metin = aday["fold"]
    uzunluk, gramlar = _metin_ozeti(metin)
    for fold, (diger_uzunluk, diger_gramlar), kutu, kare_sira in zip(
            kume["esleme_foldlari"], kume["esleme_ozetleri"],
            kume["esleme_kutulari"], kume["esleme_siralari"]):
        # Benzer iki isim ayni karede farkli satirlarda bulunabilir. Temporal
        # uzlasma ayni zaman noktasindaki farkli kutulari birlestirmez. Farkli
        # karelerde kayan satirin konumu dogal olarak degisebildigi icin metin
        # izi belirleyicidir.
        if (int(aday["kare_sira"]) == int(kare_sira)
                and not _kutu_benzer(aday["box"], kutu)):
            continue
        if min(uzunluk, diger_uzunluk) >= 4 and (
                metin.startswith(fold) or fold.startswith(metin)):
            return True
        if 2 * min(uzunluk, diger_uzunluk) / max(
                1, uzunluk + diger_uzunluk) < esik:
            continue
        if min(uzunluk, diger_uzunluk) >= 5 and gramlar and diger_gramlar \
                and not (gramlar & diger_gramlar):
            continue
        if _varyant(metin, fold, esik):
            return True
    return False


def _kume_temsilcisi(ogeler: list[dict]) -> dict:
    gruplar: dict[str, list[dict]] = defaultdict(list)
    for oge in ogeler:
        gruplar[oge["fold"]].append(oge)

    def tipografi(metin: str) -> float:
        harf = [c for c in metin if c.isalpha()]
        return (sum(c.isupper() for c in harf) / len(harf)) if harf else 0.0

    def grup_puani(grup: list[dict]) -> float:
        en_iyi = max(grup, key=lambda x: (
            x["score"] + 0.05 * tipografi(x["text"])
            + 0.002 * min(80, sum(c.isalnum() for c in x["text"]))))
        return (en_iyi["score"] + 0.04 * min(5, len(grup))
                + 0.05 * tipografi(en_iyi["text"])
                + 0.002 * min(80, sum(c.isalnum() for c in en_iyi["text"])))

    grup = max(gruplar.values(), key=grup_puani)
    return max(grup, key=lambda x: (
        x["score"] + 0.05 * tipografi(x["text"])
        + 0.002 * min(80, sum(c.isalnum() for c in x["text"]))))


def _gecis_bilesigi(aday: dict, kararli_kumeler: list[tuple[dict, dict]]) -> bool:
    """Tek karelik satir, kararli bir satirin cross-fade birlesigi mi?"""
    f = aday["fold"]
    if len(f.replace(" ", "")) < 5:
        return False
    sira = int(aday["kare_sira"])
    for kume, temiz in kararli_kumeler:
        # Cross-fade ayni veya komsu karelerde olur. Filmin bambaska bir
        # anindaki benzer isim, tek-karelik gercek bir krediyi eleyemez.
        if sira < int(kume["ilk_sira"]) - 2 or sira > int(kume["son_sira"]) + 2:
            continue
        t = temiz["fold"]
        oran = difflib.SequenceMatcher(None, f, t).ratio()
        blok = max(x.size for x in difflib.SequenceMatcher(None, f, t)
                   .get_matching_blocks())
        if oran >= 0.55 and blok >= 4:
            return True
    return False


def _fallback_temporal_cozuldu(aday: dict,
                               kararli_kumeler: list[tuple[dict, dict]],
                               komsu: int) -> bool:
    """Belirsiz temsilci Paddle'in komsu kare uzlasmasiyla cozuldu mu?

    Dusuk-guven metnin aynisi komsularda kararliysa ya da metinsiz kutularin
    her biri komsudaki kararli kutularla geometrik olarak eslesiyorsa agir
    modele gitmek yeni bilgi getirmez. Eslesmeyen tek bir kutu bile fallback'i
    korur; boylece bir karelik gercek kart kaybolmaz.
    """
    sira = int(aday["kare_sira"])
    yakin = [oge for kume, _temsilci in kararli_kumeler
             if int(kume["ilk_sira"]) - komsu <= sira
             <= int(kume["son_sira"]) + komsu
             for oge in kume["ogeler"]
             if abs(int(oge["kare_sira"]) - sira) <= komsu]
    if not yakin:
        return False
    dusuk = aday.get("dusuk") or []
    # Dusuk-guvenli tek karakter sapmasinda (NES↔MES gibi hareketli logo)
    # 0.60 yeterli; kutu geometrisinin de eslesmesi zorunlu oldugundan ilgisiz
    # bir kisa isim bu kuralla kapatilmaz.
    if dusuk and not all(any(_varyant(x["fold"], y["fold"], 0.60)
                              for y in yakin) for x in dusuk):
        return False
    kutular = aday.get("boxes") or []
    return bool(kutular) and all(
        any(_kutu_benzer(kutu, y["box"]) for y in yakin) for kutu in kutular
    )


def _kutu_benzer(a, b) -> bool:
    if not (_kutu_mu(a) and _kutu_mu(b)):
        return False
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    kes = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    alan_a = (a[2] - a[0]) * (a[3] - a[1])
    alan_b = (b[2] - b[0]) * (b[3] - b[1])
    birlik = alan_a + alan_b - kes
    if birlik > 0 and kes / birlik >= 0.30:
        return True
    acx, acy = (a[0] + a[2]) / 2, (a[1] + a[3]) / 2
    bcx, bcy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    wr = (a[2] - a[0]) / max(1e-9, b[2] - b[0])
    hr = (a[3] - a[1]) / max(1e-9, b[3] - b[1])
    return (abs(acx - bcx) <= 0.08 and abs(acy - bcy) <= 0.06
            and 0.5 <= wr <= 2.0 and 0.5 <= hr <= 2.0)


def _paddle_veto(metin: str) -> str | None:
    f = okuyucu.fold(metin)
    kelimeler = f.split()
    alnum_n = sum(c.isalnum() for c in f)
    if not f or alnum_n < 2:
        return "cok_kisa"
    tekler = sum(len(x) == 1 for x in kelimeler)
    if alnum_n <= 6 and len(kelimeler) >= 2 and tekler >= math.ceil(len(kelimeler) / 2):
        return "parcali_gecis"
    return "gevezelik" if okuyucu.gevezelik_mi(metin) else okuyucu.yapisal_veto(metin)


def _sebep_say(elenen: list[dict]) -> dict[str, int]:
    sonuc: dict[str, int] = {}
    for oge in elenen:
        sebep = str(oge.get("sebep", "bilinmiyor"))
        sonuc[sebep] = sonuc.get(sebep, 0) + 1
    return sonuc


def _kutu_mu(kutu) -> bool:
    return (isinstance(kutu, (list, tuple)) and len(kutu) == 4
            and all(isinstance(x, (int, float)) and not isinstance(x, bool)
                    for x in kutu)
            and 0 <= kutu[0] < kutu[2] <= 1
            and 0 <= kutu[1] < kutu[3] <= 1)


def _okunabilir_metin_kutusu(kutu) -> bool:
    """Tam kare/yarim kare segmentation lekesini metin satiri sayma."""
    if not _kutu_mu(kutu):
        return False
    w, h = kutu[2] - kutu[0], kutu[3] - kutu[1]
    return h <= 0.45 and w * h <= 0.45


def _logo_adayi(kutu) -> bool:
    if not _kutu_mu(kutu):
        return False
    x1, y1, x2, y2 = kutu
    alan = (x2 - x1) * (y2 - y1)
    xm, ym = (x1 + x2) / 2, (y1 + y2) / 2
    return alan <= 0.05 and (xm <= 0.20 or xm >= 0.80) and (ym <= 0.20 or ym >= 0.80)


def _kutu_imzasi(kutu) -> tuple[int, ...]:
    return tuple(round(float(x) * 50) for x in kutu)


def _kalici_logo_imzalari(yollar: list[Path], analizler: dict,
                           oran: float) -> set[tuple[int, ...]]:
    sayac: dict[tuple[int, ...], int] = {}
    for p in yollar:
        gorulen = {_kutu_imzasi(kutu)
                   for kutu in (analizler.get(p.name) or {}).get("boxes") or []
                   if _logo_adayi(kutu)}
        for imza in gorulen:
            sayac[imza] = sayac.get(imza, 0) + 1
    esik = max(1, math.ceil(len(yollar) * max(0.0, min(1.0, oran))))
    return {imza for imza, adet in sayac.items() if adet >= esik}
