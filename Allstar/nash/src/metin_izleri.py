"""Video jenerigi icin metne ozel zamansal izler.

Genel nesne tracker'lari kutuyu izler; jenerikte ise ayni hizla kayan onlarca
satir ayni geometriyi paylasabilir. Bu modul metin benzerligini, tahmin edilen
kutu hareketini ve (varsa) kirpim imzasini birlikte kullanir. Kararlar saf
Python'dur; GPU/model bagimliligi yoktur ve birim testinde denetlenebilir.
"""
from __future__ import annotations

import difflib
import math
import statistics
from collections import defaultdict


def kompakt(metin: str) -> str:
    """Bosluk/noktalama OCR sapmasina dayanikli karsilastirma anahtari."""
    return "".join(c for c in (metin or "") if c.isalnum())


def izleri_kur(adaylar: list[dict], ayar: dict | None = None
               ) -> tuple[list[dict], dict]:
    """Kronolojik OCR gozlemlerini bire-bir metin izlerine bagla.

    Esleme kare bazinda ve bire-birdir: bir iz ayni karedeki iki satiri, bir
    satir da iki izi yutamaz. Bu ozellikle kayan jenerikte yan yana/ust uste
    hareket eden benzer adlarin sessizce birlesmesini engeller.
    """
    cfg = ayar or {}
    # Eski public config anahtari override'larda yasiyor; geriye uyumluluk
    # icin o varsa yetkilidir. Yeni ad tani/niyet acikligi icin alias'tir.
    max_bosluk = max(0, int(cfg.get(
        "paddle_uzlasma_penceresi", cfg.get("paddle_iz_max_bosluk", 12))))
    metin_esigi = float(cfg.get("paddle_iz_metin_esigi", 0.66))
    kisa_esik = float(cfg.get("paddle_iz_kisa_metin_esigi", 0.80))
    gram_anahtar_n = max(1, int(cfg.get("paddle_iz_gram_anahtar", 4)))
    kareler: dict[int, list[dict]] = defaultdict(list)
    for aday in adaylar:
        yeni = dict(aday)
        yeni["compact"] = kompakt(str(yeni.get("fold", "")))
        kareler[int(yeni["kare_sira"])].append(yeni)

    izler: list[dict] = []
    aktif: list[dict] = []
    eslesme_n = 0
    aday_cifti_n = 0
    ham_cifti_n = 0
    onfiltre_cifti_n = 0
    for kare_sira in sorted(kareler):
        gozlemler = kareler[kare_sira]
        aktif = [iz for iz in aktif
                 if kare_sira - int(iz["son_sira"]) <= max_bosluk]
        ham_cifti_n += len(aktif) * len(gozlemler)
        gram_indeksi: dict[str, set[int]] = defaultdict(set)
        uzunluk_indeksi: dict[int, set[int]] = defaultdict(set)
        for iz_no, iz in enumerate(aktif):
            for onceki in iz["ogeler"][-8:]:
                compact = str(onceki.get("compact", ""))
                uzunluk_indeksi[len(compact)].add(iz_no)
                for gram in _bigramlar(compact):
                    gram_indeksi[gram].add(iz_no)
        ciftler = []
        for gozlem_no, gozlem in enumerate(gozlemler):
            metin = str(gozlem.get("compact", ""))
            olasi_izler: set[int] = set()
            mevcut_gramlar = [g for g in _bigramlar(metin) if gram_indeksi.get(g)]
            # Ortak "YONETMEN/KREDI" gramları binlerce izi aday yapar. En
            # seyrek dört bigram soyad/benzersiz parça gibi davranır; birinin
            # OCR'da bozulmasına karşı tek gram yerine küçük bir küme alınır.
            mevcut_gramlar.sort(key=lambda g: (len(gram_indeksi[g]), g))
            secili_gramlar = mevcut_gramlar[:gram_anahtar_n]
            gram_destegi: dict[int, int] = defaultdict(int)
            for gram in secili_gramlar:
                for iz_no in gram_indeksi.get(gram, ()):
                    gram_destegi[iz_no] += 1
            gereken_gram = 2 if len(metin) >= 8 and len(secili_gramlar) >= 2 else 1
            olasi_izler.update(
                iz_no for iz_no, destek in gram_destegi.items()
                if destek >= gereken_gram)
            # 1-4 karakterde bigram zayif bir ayraçtır. Yalnız teorik olarak
            # esige ulasabilecek uzunluk kovalarını eklemek kayipsiz ucuz kapı.
            if len(metin) <= 4:
                for uzunluk, numaralar in uzunluk_indeksi.items():
                    esik = kisa_esik if min(len(metin), uzunluk) <= 4 else metin_esigi
                    if _teorik_oran(len(metin), uzunluk) >= esik:
                        olasi_izler.update(numaralar)
            onfiltre_cifti_n += len(olasi_izler)
            for iz_no in olasi_izler:
                iz = aktif[iz_no]
                sonuc = _eslesme_maliyeti(
                    gozlem, iz, metin_esigi=metin_esigi,
                    kisa_esik=kisa_esik)
                if sonuc is None:
                    continue
                maliyet, tani = sonuc
                ciftler.append((maliyet, iz_no, gozlem_no, tani))
        aday_cifti_n += len(ciftler)

        kullanilan_iz: set[int] = set()
        kullanilan_gozlem: set[int] = set()
        for _maliyet, iz_no, gozlem_no, tani in sorted(
                ciftler, key=lambda x: (x[0], x[1], x[2])):
            if iz_no in kullanilan_iz or gozlem_no in kullanilan_gozlem:
                continue
            iz = aktif[iz_no]
            gozlem = gozlemler[gozlem_no]
            _ize_ekle(iz, gozlem, tani)
            kullanilan_iz.add(iz_no)
            kullanilan_gozlem.add(gozlem_no)
            eslesme_n += 1

        for gozlem_no, gozlem in enumerate(gozlemler):
            if gozlem_no in kullanilan_gozlem:
                continue
            iz = _yeni_iz(gozlem, len(izler) + 1)
            izler.append(iz)
            aktif.append(iz)

    for iz in izler:
        iz.pop("_son_eslesme", None)
    return izler, {
        "iz_n": len(izler),
        "iz_eslesme_n": eslesme_n,
        "iz_ham_cifti_n": ham_cifti_n,
        "iz_onfiltre_cifti_n": onfiltre_cifti_n,
        "iz_aday_cifti_n": aday_cifti_n,
        "iz_max_bosluk": max_bosluk,
        "iz_metin_esigi": metin_esigi,
        "iz_kisa_metin_esigi": kisa_esik,
        "iz_gram_anahtar_n": gram_anahtar_n,
    }


def kredi_penceresi(izler: list[dict], toplam_kare: int, bolum: str,
                     ayar: dict | None = None) -> tuple[set[int], dict]:
    """Guclu acilis dizisinden jenerik sonunu bul; baslangici asla kirpma.

    Kobe/Sheriff havuzu giristen once baslayabilir ve bazen jenerikten cok
    sonra da devam edebilir. Nash'in gorevi baslangici yeniden tahmin etmek
    degil; yeterli kanit varsa uzaktaki sahne yazilarini kredi havuzundan
    ayirmaktir. Suphede tam pencere korunur.
    """
    cfg = ayar or {}
    enabled = bool(cfg.get("paddle_kredi_penceresi_enabled", True))
    if bolum != "giris" or not enabled or not izler:
        return {int(iz["iz_id"]) for iz in izler}, {
            "uygulandi": False, "sebep": "bolum_veya_config",
            "bas": 1, "son": max(0, toplam_kare), "elenen_iz_n": 0,
        }

    min_destek = max(2, int(cfg.get("paddle_kredi_kuvvet_min_destek", 2)))
    min_iz = max(2, int(cfg.get("paddle_kredi_pencere_min_iz", 8)))
    grup_bosluk = max(1, int(cfg.get("paddle_kredi_grup_bosluk", 24)))
    son_bosluk = max(1, int(cfg.get("paddle_kredi_son_bosluk", 36)))
    kuyruk = max(0, int(cfg.get("paddle_kredi_son_kuyruk", 4)))
    baskin_oran = max(1.0, float(cfg.get("paddle_kredi_baskin_oran", 1.8)))

    guclu = [iz for iz in izler if _guclu_iz(iz, min_destek)]
    gruplar: list[dict] = []
    for iz in sorted(guclu, key=lambda x: (x["ilk_sira"], x["son_sira"])):
        if not gruplar or int(iz["ilk_sira"]) - gruplar[-1]["son"] > grup_bosluk:
            gruplar.append({"bas": int(iz["ilk_sira"]),
                            "son": int(iz["son_sira"]), "izler": [iz]})
        else:
            gruplar[-1]["son"] = max(gruplar[-1]["son"], int(iz["son_sira"]))
            gruplar[-1]["izler"].append(iz)
    for grup in gruplar:
        destek = sum(min(5, len(iz["ogeler"])) for iz in grup["izler"])
        genis = sum(_medyan_kutu(iz)[2] - _medyan_kutu(iz)[0] >= 0.24
                    for iz in grup["izler"])
        grup["puan"] = 3 * len(grup["izler"]) + destek + genis

    if not gruplar:
        return {int(iz["iz_id"]) for iz in izler}, {
            "uygulandi": False, "sebep": "guclu_iz_yok",
            "bas": 1, "son": max(0, toplam_kare), "elenen_iz_n": 0,
            "gruplar": [],
        }

    en_iyi = max(gruplar, key=lambda g: (g["puan"], len(g["izler"]), -g["bas"]))
    diger_puan = max((g["puan"] for g in gruplar if g is not en_iyi), default=0)
    yeterli = len(en_iyi["izler"]) >= min_iz
    uzakta_kuyruk = toplam_kare - int(en_iyi["son"]) >= son_bosluk
    baskin = not diger_puan or en_iyi["puan"] >= diger_puan * baskin_oran
    if not (yeterli and uzakta_kuyruk and baskin):
        return {int(iz["iz_id"]) for iz in izler}, {
            "uygulandi": False, "sebep": "kanit_yetersiz",
            "bas": 1, "son": max(0, toplam_kare), "elenen_iz_n": 0,
            "gruplar": _grup_ozeti(gruplar),
            "kosullar": {"yeterli": yeterli, "uzakta_kuyruk": uzakta_kuyruk,
                          "baskin": baskin},
        }

    son = min(toplam_kare, int(en_iyi["son"]) + kuyruk)
    izin = {int(iz["iz_id"]) for iz in izler if int(iz["ilk_sira"]) <= son}
    return izin, {
        "uygulandi": True, "sebep": "baskin_kredi_dizisi",
        "bas": 1, "son": son, "elenen_iz_n": len(izler) - len(izin),
        "gruplar": _grup_ozeti(gruplar),
        "kosullar": {"yeterli": yeterli, "uzakta_kuyruk": uzakta_kuyruk,
                      "baskin": baskin},
    }


def kucuk_sahne_yazisi_izleri(izler: list[dict], izinli: set[int],
                              ayar: dict | None = None) -> set[int]:
    """Baskin jenerik tipografisine uymayan kucuk, yalitilmis izleri bul.

    Salt piksel konumu kullanilmaz. Once cok-kareli ve genis satirlardan filmin
    kendi font olcegi/y-bantlari ogrenilir; yalniz hem kucuk hem de bu bantlara
    yabanci iz elenir. Yeterli sablon kaniti yoksa hicbir sey elenmez.
    """
    cfg = ayar or {}
    if not bool(cfg.get("paddle_kucuk_sahne_yazisi_enabled", True)):
        return set()
    aday_izler = [iz for iz in izler if int(iz["iz_id"]) in izinli]
    capalar = []
    for iz in aday_izler:
        kutu = _medyan_kutu(iz)
        w, h = kutu[2] - kutu[0], kutu[3] - kutu[1]
        if len(iz["ogeler"]) >= 3 and w >= 0.24 and 0.025 <= h <= 0.30:
            capalar.append(iz)
    min_capa = max(4, int(cfg.get("paddle_sahne_yazisi_min_capa", 8)))
    if len(capalar) < min_capa:
        return set()
    # Kayan jenerikte kucuk puntolu iki/uc sutun normaldir. Statik sablon
    # kaniti yoksa bu filtreyi calistirmamak, tek tek kredileri korur.
    hareketli = sum(abs(_iz_dikey_hizi(iz)) >= 0.015 for iz in capalar)
    if hareketli >= max(2, math.ceil(len(capalar) * 0.25)):
        return set()
    medyan_h = statistics.median(
        _medyan_kutu(iz)[3] - _medyan_kutu(iz)[1] for iz in capalar)
    h_oran = float(cfg.get("paddle_sahne_yazisi_h_oran", 0.72))
    genislik = float(cfg.get("paddle_sahne_yazisi_max_genislik", 0.24))
    y_tolerans = float(cfg.get("paddle_sahne_yazisi_y_tolerans", 0.07))
    x_tolerans = float(cfg.get("paddle_sahne_yazisi_x_tolerans", 0.22))
    y_min_capa = max(2, int(cfg.get("paddle_sahne_yazisi_y_min_capa", 3)))
    capa_merkezleri = [((_medyan_kutu(iz)[0] + _medyan_kutu(iz)[2]) / 2,
                        (_medyan_kutu(iz)[1] + _medyan_kutu(iz)[3]) / 2)
                       for iz in capalar]
    elenen = set()
    for iz in aday_izler:
        kutu = _medyan_kutu(iz)
        w, h = kutu[2] - kutu[0], kutu[3] - kutu[1]
        if not (w < genislik and h < medyan_h * h_oran):
            continue
        y = (kutu[1] + kutu[3]) / 2
        x = (kutu[0] + kutu[2]) / 2
        ayni_bant = sum(abs(y - cy) <= y_tolerans
                        and abs(x - cx) <= x_tolerans
                        for cx, cy in capa_merkezleri)
        if ayni_bant < y_min_capa:
            elenen.add(int(iz["iz_id"]))
    return elenen


def zayif_layout_disinda_izler(izler: list[dict], izinli: set[int],
                               ayar: dict | None = None,
                               tani: list[dict] | None = None) -> set[int]:
    """Yakindaki guclu kredi kolonundan uzakta kalan 1-2 karelik izi bul.

    Metnin anlamina bakmaz. Yalniz ayni zaman cevresindeki cok-kareli kredi
    kutularinin x yerlesimini kanit sayar. Boylece canli sahnedeki plaka/tabela
    elenirken ayni kolonda duran tek-karelik gercek rol veya ad korunur.
    """
    cfg = ayar or {}
    if not bool(cfg.get("paddle_layout_aykiri_enabled", True)):
        return set()
    adaylar = [x for x in izler if int(x["iz_id"]) in izinli]
    gucluler = [x for x in adaylar if len(x.get("ogeler") or []) >= 3]
    min_luma = float(cfg.get("paddle_layout_min_luma", 45.0))
    scroll_max_luma = float(cfg.get("paddle_layout_scroll_max_luma", 50.0))
    guclu_lumalar = [
        float(o["frame_luma"]) for x in gucluler for o in x.get("ogeler") or []
        if o.get("frame_luma") is not None
    ]
    global_luma = (statistics.median(guclu_lumalar)
                   if guclu_lumalar else None)
    # Kayan jenerikte farkli kolonlar ve ekrana yeni giren tek-kare kenar
    # parcalari normaldir. Bu filtre yalniz statik kart dizilerinde anlamlidir.
    hareketli = sum(abs(_iz_dikey_hizi(x)) >= 0.015 for x in gucluler)
    scroll_min = max(4, int(cfg.get("paddle_layout_scroll_min_iz", 8)))
    scroll_oran = float(cfg.get("paddle_layout_scroll_oran", 0.60))
    if (len(gucluler) >= scroll_min
            and hareketli >= math.ceil(len(gucluler) * scroll_oran)
            and (global_luma is None or global_luma < scroll_max_luma)):
        if tani is not None:
            tani.append({"scope": "all", "decision": "scroll_skip",
                         "strong_n": len(gucluler), "moving_n": hareketli,
                         "global_luma": global_luma})
        return set()
    zayif_tavan = max(1, int(cfg.get("paddle_layout_zayif_destek_tavan", 2)))
    kare_komsu = max(1, int(cfg.get("paddle_layout_kare_komsu", 8)))
    x_tolerans = float(cfg.get("paddle_layout_x_tolerans", 0.24))
    h_min_oran = float(cfg.get("paddle_layout_h_min_oran", 0.50))
    h_max_oran = float(cfg.get("paddle_layout_h_max_oran", 1.60))
    min_capa = max(2, int(cfg.get("paddle_layout_min_capa", 2)))
    elenen = set()
    for iz in adaylar:
        if len(iz.get("ogeler") or []) > zayif_tavan:
            continue
        lumalar = [float(x["frame_luma"]) for x in iz.get("ogeler") or []
                   if x.get("frame_luma") is not None]
        # Eski onbellekte veya mock analizde görsel kanıt yoksa metni silme.
        if not lumalar or statistics.median(lumalar) < min_luma:
            if tani is not None:
                tani.append({"iz_id": int(iz["iz_id"]),
                             "decision": "keep_no_visual_evidence",
                             "luma": (round(statistics.median(lumalar), 3)
                                      if lumalar else None)})
            continue
        bas, son = int(iz["ilk_sira"]), int(iz["son_sira"])
        x = (_medyan_kutu(iz)[0] + _medyan_kutu(iz)[2]) / 2
        yakin = []
        for capa in gucluler:
            uzaklik = max(int(capa["ilk_sira"]) - son,
                          bas - int(capa["son_sira"]), 0)
            if uzaklik <= kare_komsu:
                kutu = _medyan_kutu(capa)
                yakin.append(((kutu[0] + kutu[2]) / 2,
                              kutu[3] - kutu[1]))
        kutu = _medyan_kutu(iz)
        h = kutu[3] - kutu[1]
        medyan_h = statistics.median(x[1] for x in yakin) if yakin else 0.0
        x_aykiri = bool(yakin) and all(
            abs(x - capa_x) > x_tolerans for capa_x, _h in yakin)
        h_aykiri = bool(medyan_h) and not (
            medyan_h * h_min_oran <= h <= medyan_h * h_max_oran)
        if len(yakin) >= min_capa and (x_aykiri or h_aykiri):
            elenen.add(int(iz["iz_id"]))
        if tani is not None:
            tani.append({
                "iz_id": int(iz["iz_id"]),
                "decision": ("remove" if int(iz["iz_id"]) in elenen
                             else "keep_layout"),
                "luma": round(statistics.median(lumalar), 3),
                "local_anchor_n": len(yakin), "x": round(x, 6),
                "height": round(h, 6),
                "local_median_height": round(medyan_h, 6),
                "x_outlier": x_aykiri, "height_outlier": h_aykiri,
            })
    return elenen


def iz_sira_bilgisi(iz: dict, ayar: dict | None = None) -> dict:
    """Bir izin ekrandaki ortak referans cizgisini gecis zamanini hesapla.

    Kayan jenerikte ilk gorulen kare sira demek degildir: ilk havuz
    karesinde ekran zaten on satirla dolu olabilir. Her izin y merkezine
    dogrusal egim uydurup ekran ortasini gecis zamanini bulmak, satirlari
    kare sinirindan bagimsiz gercek akis sirasina koyar. Hareket kaniti zayifsa
    statik kart davranisina geri donulur.
    """
    cfg = ayar or {}
    ogeler = sorted(iz.get("ogeler") or [],
                    key=lambda x: int(x["kare_sira"]))
    ilk = int(iz.get("ilk_sira", ogeler[0]["kare_sira"] if ogeler else 0))
    x_medyan = statistics.median(
        _merkez(x["box"])[0] for x in ogeler) if ogeler else 0.5
    y_medyan = statistics.median(
        _merkez(x["box"])[1] for x in ogeler) if ogeler else 0.5
    if len(ogeler) < 3:
        return {"zaman": float(ilk), "hareketli": False,
                "egim": 0.0, "uyum": 0.0, "x": x_medyan,
                "y": y_medyan}

    zamanlar = [float(x["kare_sira"]) for x in ogeler]
    yler = [_merkez(x["box"])[1] for x in ogeler]
    t_orta = statistics.mean(zamanlar)
    y_orta = statistics.mean(yler)
    payda = sum((t - t_orta) ** 2 for t in zamanlar)
    egim = (sum((t - t_orta) * (y - y_orta)
                for t, y in zip(zamanlar, yler)) / payda
            if payda else 0.0)
    tahminler = [y_orta + egim * (t - t_orta) for t in zamanlar]
    hata = sum((y - p) ** 2 for y, p in zip(yler, tahminler))
    toplam = sum((y - y_orta) ** 2 for y in yler)
    uyum = max(0.0, min(1.0, 1.0 - hata / toplam)) if toplam > 1e-12 else 0.0
    min_egim = float(cfg.get("paddle_akis_min_egim", 0.004))
    min_yol = float(cfg.get("paddle_akis_min_yol", 0.08))
    min_uyum = float(cfg.get("paddle_akis_min_uyum", 0.55))
    yol = max(yler) - min(yler)
    hareketli = abs(egim) >= min_egim and yol >= min_yol and uyum >= min_uyum
    referans = float(cfg.get("paddle_akis_referans_y", 0.50))
    zaman = (t_orta + (referans - y_orta) / egim
             if hareketli else float(ilk))
    # Baslangicta/sonda yarim gorunen satir icin sinir disina kisa
    # ekstrapolasyon gerekir; bozuk tek izin yuzlerce kare savrulmasi gerekmez.
    toplam_kapsam = max(1.0, float(ogeler[-1]["kare_sira"])
                       - float(ogeler[0]["kare_sira"]))
    pay = float(cfg.get("paddle_akis_ekstrapolasyon_orani", 1.5))
    alt = float(ogeler[0]["kare_sira"]) - toplam_kapsam * pay
    ust = float(ogeler[-1]["kare_sira"]) + toplam_kapsam * pay
    zaman = max(alt, min(ust, zaman))
    return {"zaman": zaman, "hareketli": hareketli,
            "egim": egim, "uyum": uyum, "x": x_medyan,
            "y": y_medyan}


def _iz_dikey_hizi(iz: dict) -> float:
    ogeler = sorted(iz["ogeler"], key=lambda x: int(x["kare_sira"]))
    if len(ogeler) < 2:
        return 0.0
    ilk, son = ogeler[0], ogeler[-1]
    dt = int(son["kare_sira"]) - int(ilk["kare_sira"])
    if dt <= 0:
        return 0.0
    _x1, y1, _w1, _h1 = _merkez(ilk["box"])
    _x2, y2, _w2, _h2 = _merkez(son["box"])
    return (y2 - y1) / dt


def _yeni_iz(gozlem: dict, iz_id: int) -> dict:
    return {
        "iz_id": iz_id,
        "ilk_sira": int(gozlem["kare_sira"]),
        "son_sira": int(gozlem["kare_sira"]),
        "ogeler": [gozlem],
        "esleme_foldlari": [gozlem["fold"]],
        "esleme_kutulari": [gozlem["box"]],
        "esleme_siralari": [int(gozlem["kare_sira"])],
        "_son_eslesme": None,
    }


def _ize_ekle(iz: dict, gozlem: dict, tani: dict) -> None:
    iz["ogeler"].append(gozlem)
    iz["son_sira"] = int(gozlem["kare_sira"])
    iz["esleme_foldlari"] = (iz["esleme_foldlari"] + [gozlem["fold"]])[-8:]
    iz["esleme_kutulari"] = (iz["esleme_kutulari"] + [gozlem["box"]])[-8:]
    iz["esleme_siralari"] = (
        iz["esleme_siralari"] + [int(gozlem["kare_sira"])])[-8:]
    iz["_son_eslesme"] = tani


def _eslesme_maliyeti(gozlem: dict, iz: dict, *, metin_esigi: float,
                      kisa_esik: float) -> tuple[float, dict] | None:
    en_iyi = None
    for onceki in reversed(iz["ogeler"][-8:]):
        if int(onceki["kare_sira"]) == int(gozlem["kare_sira"]):
            continue
        a, b = gozlem.get("compact", ""), onceki.get("compact", "")
        if not a or not b:
            continue
        esik = kisa_esik if min(len(a), len(b)) <= 4 else metin_esigi
        if not _hizli_metin_adayi(a, b, esik):
            continue
        benzerlik = _metin_benzerligi(a, b)
        if benzerlik < esik:
            continue
        geo = _geometri(gozlem, iz, onceki, benzerlik)
        if geo is None:
            continue
        hash_benzerlik = _hash_benzerligi(
            gozlem.get("crop_dhash"), onceki.get("crop_dhash"))
        maliyet = (0.68 * (1.0 - benzerlik) + 0.22 * geo
                   + 0.10 * (1.0 - hash_benzerlik))
        sonuc = (maliyet, {"metin": round(benzerlik, 6),
                            "geometri": round(geo, 6),
                            "kirpim": round(hash_benzerlik, 6)})
        if en_iyi is None or sonuc[0] < en_iyi[0]:
            en_iyi = sonuc
    return en_iyi


def _metin_benzerligi(a: str, b: str) -> float:
    if a == b:
        return 1.0
    oran = difflib.SequenceMatcher(None, a, b).ratio()
    if min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)):
        oran = max(oran, 2 * min(len(a), len(b)) / (len(a) + len(b)))
    return oran


def _bigramlar(metin: str) -> set[str]:
    if len(metin) < 2:
        return {metin} if metin else set()
    return {metin[i:i + 2] for i in range(len(metin) - 1)}


def _teorik_oran(a: int, b: int) -> float:
    return 2 * min(a, b) / max(1, a + b)


def _hizli_metin_adayi(a: str, b: str, esik: float) -> bool:
    if not a or not b or _teorik_oran(len(a), len(b)) < esik:
        return False
    if a == b or a.startswith(b) or b.startswith(a):
        return True
    return min(len(a), len(b)) < 5 or bool(_bigramlar(a) & _bigramlar(b))


def _geometri(gozlem: dict, iz: dict, onceki: dict,
              metin_benzerligi: float) -> float | None:
    a = gozlem["box"]
    b = onceki["box"]
    acx, acy, aw, ah = _merkez(a)
    bcx, bcy, bw, bh = _merkez(b)
    wr, hr = aw / max(1e-9, bw), ah / max(1e-9, bh)
    if not (0.35 <= wr <= 2.85 and 0.45 <= hr <= 2.20):
        return None
    gap = max(1, int(gozlem["kare_sira"]) - int(onceki["kare_sira"]))
    vx, vy = _hiz(iz)
    px, py = bcx + vx * gap, bcy + vy * gap
    dx, dy = abs(acx - px), abs(acy - py)
    x_kapi = max(0.10, 0.85 * max(aw, bw))
    y_kapi = max(0.10, 2.2 * max(ah, bh), abs(vy) * gap + 0.05)
    if gap <= 2 and metin_benzerligi >= 0.76:
        # 2 fps'e dusurulmus hizli scroll bir karede ekranin dortte biri
        # kadar ilerleyebilir. Ilk eslesmede iz hizi henuz bilinmez; metin
        # yakin ve x/boyut uyumluysa yalniz dikey bootstrap kapisini ac.
        # Sonraki karelerde olculen hiz zaten normal tahmini devralir.
        y_kapi = max(y_kapi, 0.36)
    if metin_benzerligi >= 0.94:
        x_kapi, y_kapi = max(x_kapi, 0.24), max(y_kapi, 0.35)
    if dx > x_kapi or dy > y_kapi:
        return None
    konum = 0.5 * min(1.0, dx / x_kapi) + 0.5 * min(1.0, dy / y_kapi)
    boyut = min(1.0, (abs(math.log(max(1e-9, wr)))
                      + abs(math.log(max(1e-9, hr)))) / 2)
    return 0.75 * konum + 0.25 * boyut


def _hiz(iz: dict) -> tuple[float, float]:
    ogeler = iz["ogeler"]
    if len(ogeler) < 2:
        return 0.0, 0.0
    a, b = ogeler[-2], ogeler[-1]
    dt = int(b["kare_sira"]) - int(a["kare_sira"])
    if dt <= 0:
        return 0.0, 0.0
    acx, acy, _aw, _ah = _merkez(a["box"])
    bcx, bcy, _bw, _bh = _merkez(b["box"])
    return (bcx - acx) / dt, (bcy - acy) / dt


def _hash_benzerligi(a, b) -> float:
    if not (isinstance(a, int) and isinstance(b, int)):
        return 0.5
    # Worker 128-bit yatay fark imzasi yazar.
    return 1.0 - min(128, (a ^ b).bit_count()) / 128


def _merkez(kutu) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = (float(x) for x in kutu)
    return ((x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1)


def _medyan_kutu(iz: dict) -> list[float]:
    kutular = [oge["box"] for oge in iz["ogeler"]]
    return [statistics.median(float(k[i]) for k in kutular) for i in range(4)]


def _guclu_iz(iz: dict, min_destek: int) -> bool:
    if len(iz["ogeler"]) < min_destek:
        return False
    en_iyi = max(iz["ogeler"], key=lambda x: float(x.get("score", 0.0)))
    if sum(c.isalnum() for c in str(en_iyi.get("fold", ""))) < 3:
        return False
    kutu = _medyan_kutu(iz)
    w, h = kutu[2] - kutu[0], kutu[3] - kutu[1]
    return h <= 0.45 and w * h <= 0.45


def _grup_ozeti(gruplar: list[dict]) -> list[dict]:
    return [{"bas": g["bas"], "son": g["son"],
             "iz_n": len(g["izler"]), "puan": g["puan"]}
            for g in gruplar]
