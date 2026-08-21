"""FAZ 3b / FAZ 4 — Kanıt tartısı ve birleştirici (Füzyon Motoru).

Şartname: docs/BIRLESTIRICI.md, docs/PLAN.md §3.
Bu modül üç bağımsız gözlemi (faz 0 VLM, faz K VLM, OCR kanıt indeksi) birleştirir:
  1. Koşu içi görünüm ve kesin-tekrar kontrolü
  2. Fazlar arası sıra-korumalı hizalama (faz_tutarlılığı)
  3. Rol-isim çiftlerinin birleşimi ve OCR adayları eşleştirmesi
  4. Konum ve Y-bandı tutarlılığı (Kendall uyumu)
  4b. KANIT ÇAPASIYLA KÜMELEME (mutasyon elemesi ve kesinlik kaldıracı)
  5. Sınıflandırma (KESİN, ZAYIF, ÇATIŞMA, SÜPHELİ)
  6. Diakritik hakemliği (Türkçe denklik)
  7. Pencere kanıtı ve sahne riski raporu
  8. Tam soy ağacı ve kanıt derlemesi

Bu modül BÖLÜM (giriş/çıkış) mantığı TAŞIMAZ — Kobe izolasyon kanunu (PLAN §1);
eşikler main.py'den parametre olarak geçirilir (tests/test_izolasyon.py kilitler).
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

try:
    from kanal_ocr import BANT_Y_TOLERANSI, CATISMA_ALT, CATISMA_UST, ara, benzer, norm
except ImportError:
    from src.kanal_ocr import BANT_Y_TOLERANSI, CATISMA_ALT, CATISMA_UST, ara, benzer, norm

SATIR_SINIFLARI = ("KESIN", "ZAYIF", "CATISMA", "SUPHELI")
VARSAYILAN_E1 = 0.70
VARSAYILAN_E2 = 0.50
VARSAYILAN_KARE_PAYI = 8
FAZ_HIZALAMA_ESIK = 0.90


# ---------------------------------------------------------------------------
# Adım 2 — Fazlar arası hizalama
# ---------------------------------------------------------------------------

def fazlari_hizala(satirlar_faz0: list[dict], satirlar_fazK: list[dict],
                   esik: float = FAZ_HIZALAMA_ESIK) -> list[dict]:
    """İki VLM fazının satır dizilerini SequenceMatcher + bulanık turla hizalar."""
    n0 = [norm(s["metin"]) for s in satirlar_faz0]
    nK = [norm(s["metin"]) for s in satirlar_fazK]

    sm = SequenceMatcher(None, n0, nK, autojunk=False)
    eslesmeler_0: dict[int, tuple[int, float]] = {}
    eslesmeler_K: dict[int, tuple[int, float]] = {}

    bosluklar: list[tuple[range, range]] = []
    for etiket, i1, i2, j1, j2 in sm.get_opcodes():
        if etiket == "equal":
            for k in range(i2 - i1):
                idx0, idxK = i1 + k, j1 + k
                eslesmeler_0[idx0] = (idxK, 1.0)
                eslesmeler_K[idxK] = (idx0, 1.0)
        else:
            bosluklar.append((range(i1, i2), range(j1, j2)))

    for r0, rK in bosluklar:
        adaylar = []
        for i in r0:
            for j in rK:
                skor = benzer(satirlar_faz0[i]["metin"], satirlar_fazK[j]["metin"])
                if skor >= esik:
                    adaylar.append((skor, i, j))
        adaylar.sort(key=lambda t: (-t[0], t[1], t[2]))
        tutulan_0, tutulan_K = set(), set()
        for skor, i, j in adaylar:
            if i in tutulan_0 or j in tutulan_K:
                continue
            tutulan_0.add(i)
            tutulan_K.add(j)
            eslesmeler_0[i] = (j, round(skor, 4))
            eslesmeler_K[j] = (i, round(skor, 4))

    birlesik: list[dict] = []
    eklenen_K: set[int] = set()

    for i, s0 in enumerate(satirlar_faz0):
        tutar = i in eslesmeler_0
        eslesen_K_idx = eslesmeler_0[i][0] if tutar else None

        if eslesen_K_idx is not None:
            for j in range(eslesen_K_idx):
                if j not in eklenen_K and j not in eslesmeler_K:
                    sK_once = dict(satirlar_fazK[j])
                    sK_once["faz_tutar"] = False
                    sK_once["fazlar"] = [satirlar_fazK[j].get("faz", "K")]
                    birlesik.append(sK_once)
                    eklenen_K.add(j)
            eklenen_K.add(eslesen_K_idx)

        aday = dict(s0)
        aday["faz_tutar"] = tutar
        aday["fazlar"] = [0]
        if tutar and eslesen_K_idx is not None:
            aday["fazlar"].append(satirlar_fazK[eslesen_K_idx].get("faz", "K"))
            aralik0 = s0.get("kare_araligi") or [1, 8]
            aralikK = satirlar_fazK[eslesen_K_idx].get("kare_araligi") or [1, 8]
            aday["kare_araligi"] = [min(aralik0[0], aralikK[0]), max(aralik0[1], aralikK[1])]
            aday["son_sn"] = max(s0.get("son_sn", 0.0), satirlar_fazK[eslesen_K_idx].get("son_sn", 0.0))
        birlesik.append(aday)

    for j, sK in enumerate(satirlar_fazK):
        if j not in eklenen_K and j not in eslesmeler_K:
            adayK = dict(sK)
            adayK["faz_tutar"] = False
            adayK["fazlar"] = [sK.get("faz", "K")]
            birlesik.append(adayK)
            eklenen_K.add(j)

    return birlesik


# ---------------------------------------------------------------------------
# Adım 3 — Rol-İsim Çiftlerini Birleştirme
# ---------------------------------------------------------------------------

def rol_isim_birlestir(adaylar: list[dict], ocr_indeksi: dict, pay: int = VARSAYILAN_KARE_PAYI) -> list[dict]:
    """Ayrı satırlara bölünmüş rol ve isimleri (örn. 'Kamera' ve '/ RÜŞTÜ ALTAY')
    OCR kanıtı ve açık ayraç (/ - — :) varsa tek satırda birleştirir.
    İki sütunlu oyuncu-rol listelerini (Ali Reyat / Gürkan Uygun) ayırmaz.
    """
    if len(adaylar) < 2:
        return adaylar

    sonuc: list[dict] = []
    i = 0
    while i < len(adaylar):
        s_curr = adaylar[i]
        if i + 1 < len(adaylar):
            s_next = adaylar[i + 1]
            m_curr = s_curr.get("metin", "").strip()
            m_next = s_next.get("metin", "").strip()

            ayracli = (m_next.startswith("/") or m_next.startswith("-") or
                       m_next.startswith("—") or m_next.startswith(":") or
                       m_curr.endswith("/") or m_curr.endswith("-") or
                       m_curr.endswith("—") or m_curr.endswith(":"))

            if ayracli and len(m_curr) > 1 and len(m_next) > 1:
                bilesik_metin = f"{m_curr} {m_next}"
                aralik_curr = s_curr.get("kare_araligi") or [1, 1]
                aralik_next = s_next.get("kare_araligi") or [1, 1]
                bilesik_aralik = [min(aralik_curr[0], aralik_next[0]), max(aralik_curr[1], aralik_next[1])]

                ocr_bilesik = ara(ocr_indeksi, bilesik_metin, bilesik_aralik, pay=pay)
                ocr_curr = ara(ocr_indeksi, m_curr, aralik_curr, pay=pay)
                ocr_next = ara(ocr_indeksi, m_next, aralik_next, pay=pay)

                if (ocr_bilesik["ocr_skor"] >= 0.65 and
                        ocr_bilesik["ocr_skor"] >= max(ocr_curr["ocr_skor"], ocr_next["ocr_skor"]) - 0.05):
                    birlesik_aday = dict(s_curr)
                    birlesik_aday["metin"] = bilesik_metin
                    birlesik_aday["kare_araligi"] = bilesik_aralik
                    birlesik_aday["son_sn"] = max(s_curr.get("son_sn", 0.0), s_next.get("son_sn", 0.0))
                    birlesik_aday["faz_tutar"] = bool(s_curr.get("faz_tutar") or s_next.get("faz_tutar"))
                    sonuc.append(birlesik_aday)
                    i += 2
                    continue

        sonuc.append(s_curr)
        i += 1

    return sonuc


# ---------------------------------------------------------------------------
# Adım 4 — Konum & Y-Bandı Tutarlılığı (Kendall Uyumu)
# ---------------------------------------------------------------------------

def konum_tutarliligi_denetle(adaylar: list[dict]) -> None:
    """Aynı gruptaki kanıtlı satırların Y bandı artan sırada mı denetler."""
    gruplar: dict[int, list[dict]] = {}
    for a in adaylar:
        g_no = a.get("grup_no", 0)
        gruplar.setdefault(g_no, []).append(a)

    for g_no, grup_uyeleri in gruplar.items():
        y_listesi = [(idx, a) for idx, a in enumerate(grup_uyeleri)
                     if a.get("y_orani") is not None and a.get("ocr_skor", 0.0) > 0.0]
        if len(y_listesi) < 2:
            for _, a in y_listesi:
                a["konum_uyumlu"] = True
                a["ocr_skor_etkin"] = a["ocr_skor"]
            continue

        for i, (pos_i, ai) in enumerate(y_listesi):
            ihlal_sayisi = 0
            yi = float(ai["y_orani"])
            for j, (pos_j, aj) in enumerate(y_listesi):
                if i == j:
                    continue
                yj = float(aj["y_orani"])
                if pos_i < pos_j and yi > yj + 0.08:
                    ihlal_sayisi += 1
                elif pos_i > pos_j and yi < yj - 0.08:
                    ihlal_sayisi += 1

            if ihlal_sayisi >= 2:
                ai["konum_uyumlu"] = False
                ai["ocr_skor_konumsuz"] = ai["ocr_skor"]
                ai["ocr_skor_etkin"] = 0.0
            else:
                ai["konum_uyumlu"] = True
                ai["ocr_skor_etkin"] = ai["ocr_skor"]

    for a in adaylar:
        if "konum_uyumlu" not in a:
            a["konum_uyumlu"] = True
            a["ocr_skor_etkin"] = a.get("ocr_skor", 0.0)


# ---------------------------------------------------------------------------
# Adım 4b — Kanıt Çapasıyla Kümeleme
# ---------------------------------------------------------------------------

def kanit_capasiyla_kumele(adaylar: list[dict], kare_payi: int = VARSAYILAN_KARE_PAYI) -> list[dict]:
    """Aynı OCR çapa satırıyla veya ardışık gruplardaki tekrarlarla eşleşen adayları
    tek bir fiziksel satır temsilcisinde toplar.
    """
    kumelenmis: list[dict] = []
    for aday in adaylar:
        m_norm = norm(aday.get("metin", ""))
        ocr_metin = aday.get("eslesen_metin")
        ocr_capa = norm(ocr_metin) if ocr_metin and aday.get("ocr_skor_etkin", 0.0) >= 0.40 else None
        aralik = aday.get("kare_araligi") or [1, 1]
        kare_merkez = (aralik[0] + aralik[1]) // 2

        eslesen_kume = None
        for k in kumelenmis:
            k_norm = norm(k.get("metin", ""))
            k_ocr = k.get("eslesen_metin")
            k_capa = norm(k_ocr) if k_ocr and k.get("ocr_skor_etkin", 0.0) >= 0.40 else None
            k_aralik = k.get("kare_araligi") or [1, 1]
            k_merkez = (k_aralik[0] + k_aralik[1]) // 2

            # 1. OCR Çapa eşleşmesi
            ocr_eslesiyor = (ocr_capa is not None and k_capa is not None and ocr_capa == k_capa and
                             (abs(kare_merkez - k_merkez) <= kare_payi * 3 or
                              not (aralik[1] < k_aralik[0] - kare_payi or aralik[0] > k_aralik[1] + kare_payi)))

            # 2. Metin tekrar eşleşmesi (ardışık gruplardan gelen mutasyon / aynı satır)
            metin_eslesiyor = ((m_norm == k_norm or benzer(aday.get("metin", ""), k.get("metin", "")) >= 0.90) and
                               abs(kare_merkez - k_merkez) <= kare_payi * 3)

            if ocr_eslesiyor or metin_eslesiyor:
                eslesen_kume = k
                break

        if eslesen_kume is None:
            aday["varyantlar"] = []
            kumelenmis.append(aday)
        else:
            eski_temsilci = eslesen_kume
            yeni_aday = aday

            eski_skor = eski_temsilci.get("ocr_skor_etkin", 0.0)
            yeni_skor = yeni_aday.get("ocr_skor_etkin", 0.0)

            eski_puan = (eski_skor, 1 if eski_temsilci.get("faz_tutar") else 0,
                         0 if eski_temsilci.get("dejenerasyon") else 1)
            yeni_puan = (yeni_skor, 1 if yeni_aday.get("faz_tutar") else 0,
                         0 if yeni_aday.get("dejenerasyon") else 1)

            birlesik_aralik = [
                min(eski_temsilci["kare_araligi"][0], yeni_aday["kare_araligi"][0]),
                max(eski_temsilci["kare_araligi"][1], yeni_aday["kare_araligi"][1])
            ]
            birlesik_faz_tutar = bool(eski_temsilci.get("faz_tutar") or yeni_aday.get("faz_tutar"))

            if yeni_puan > eski_puan:
                eski_metin = eski_temsilci["metin"]
                yeni_aday["varyantlar"] = eski_temsilci.get("varyantlar", []) + [eski_metin]
                yeni_aday["kare_araligi"] = birlesik_aralik
                yeni_aday["faz_tutar"] = birlesik_faz_tutar
                idx = kumelenmis.index(eski_temsilci)
                kumelenmis[idx] = yeni_aday
            else:
                eski_temsilci.setdefault("varyantlar", []).append(yeni_aday["metin"])
                eski_temsilci["kare_araligi"] = birlesik_aralik
                eski_temsilci["faz_tutar"] = birlesik_faz_tutar

    return kumelenmis


# ---------------------------------------------------------------------------
# Adım 5 — Sınıflandırma
# ---------------------------------------------------------------------------

def adaylari_siniflandir(adaylar: list[dict], E1: float, E2: float) -> None:
    """Adayları KESİN / ZAYIF / ÇATIŞMA / SÜPHELİ olarak etiketler."""
    for s in adaylar:
        skor = float(s.get("ocr_skor_etkin", 0.0))
        tutar = bool(s.get("faz_tutar", False))
        catisma = s.get("catisma")
        dejenere = bool(s.get("dejenerasyon", False))
        sahne = bool(s.get("sahne_riski", False))
        metin_temiz = s.get("metin", "").strip()

        # Aşırı kısa / çöp metinler (örn. 'Yay', 'a')
        if len(metin_temiz) <= 3 and skor < 0.80:
            s["sinif"] = "SUPHELI"
            continue

        # Sahne yazısı (jenerik öncesi neon tabela vb.)
        if sahne and skor < 0.80:
            s["sinif"] = "SUPHELI"
            continue

        # İki olumsuz sinyal: OCR yok VE faz-tutarsız -> KESİNLİKLE SÜPHELİ
        if skor < E2 and not tutar:
            s["sinif"] = "SUPHELI"
            continue

        # Dejenerasyon zinciri güçlü OCR kanıtı yoksa karantinaya gider
        if dejenere:
            if skor >= E1:
                s["sinif"] = "KESIN"
            elif skor >= E2:
                s["sinif"] = "ZAYIF"
            else:
                s["sinif"] = "SUPHELI"
            continue

        if skor >= E1 and tutar:
            s["sinif"] = "KESIN"
        elif catisma is not None and skor >= E2:
            s["sinif"] = "CATISMA"
        elif (skor >= E2 and not tutar) or (skor < E2 and tutar):
            s["sinif"] = "ZAYIF"
        else:
            s["sinif"] = "SUPHELI"


# ---------------------------------------------------------------------------
# Adım 6 — Diakritik Hakemi
# ---------------------------------------------------------------------------

def diakritik_hakemligi_uygula(adaylar: list[dict], mod: str = "ocr_kazanir") -> int:
    """VLM ve OCR metni diakritik katlandığında eşit fakat diakritikte ayrışıyorsa hakemlik eder."""
    if mod != "ocr_kazanir":
        return 0

    degisen_sayisi = 0
    for s in adaylar:
        ocr_metin = s.get("eslesen_metin")
        ocr_guven = float(s.get("guven") or 0.0)
        vlm_metin = s.get("metin", "")

        if not ocr_metin or ocr_guven < 0.85:
            continue

        if norm(vlm_metin, katla=True, bosluksuz=True) == norm(ocr_metin, katla=True, bosluksuz=True):
            if vlm_metin != ocr_metin:
                s["hakem"] = {
                    "onceki": vlm_metin,
                    "sonraki": ocr_metin,
                    "kaynak": "ocr_kazanir",
                    "guven": ocr_guven,
                }
                s["metin"] = ocr_metin
                degisen_sayisi += 1
    return degisen_sayisi


# ---------------------------------------------------------------------------
# Adım 7 — Pencere Kanıtı & Sahne Riski
# ---------------------------------------------------------------------------

def pencere_ve_sahne_kaniti(adaylar: list[dict], ocr_indeksi: dict,
                            manifest: dict | list[dict]) -> dict:
    """Pencere sınırlarında kesilme olup olmadığını ve sahne yazısı riskini raporlar."""
    kareler = manifest.get("kareler", []) if isinstance(manifest, dict) else list(manifest)
    toplam_kare = len(kareler)
    ocr_kareler = ocr_indeksi.get("kareler", {})

    ilk_kareler_dolu = any(bool(ocr_kareler.get(no) or ocr_kareler.get(str(no)))
                           for no in range(1, min(5, toplam_kare + 1)))
    son_kareler_dolu = any(bool(ocr_kareler.get(no) or ocr_kareler.get(str(no)))
                           for no in range(max(1, toplam_kare - 4), toplam_kare + 1))

    uyarilar = []
    if ilk_kareler_dolu:
        uyarilar.append("pencere_gec — cikis jeneriginin basi kacmis olabilir")
    if son_kareler_dolu:
        uyarilar.append("pencere_kisa — giris jeneriginin sonu kacmis olabilir")

    for a in adaylar:
        aralik = a.get("kare_araligi") or [1, 1]
        m = a.get("metin", "").lower()
        # Jenerik anahtar kelimeleri içermeyen ve ilk 8 karede kalanlar sahne yazısı olabilir
        jenerik_sozleri = ("yönetmen", "oyuncu", "oynayan", "yapım", "kurgu", "müzik", "ses", "ışık", "kamera", "dekor", "kostüm")
        if aralik[1] <= 8 and not any(k in m for k in jenerik_sozleri) and len(adaylar) > 8:
            a["sahne_riski"] = True
        else:
            a["sahne_riski"] = False

    return {
        "toplam_kare": toplam_kare,
        "ilk_kareler_metin_var": ilk_kareler_dolu,
        "son_kareler_metin_var": son_kareler_dolu,
        "uyarilar": uyarilar,
    }


# ---------------------------------------------------------------------------
# Ana Birleştirici API
# ---------------------------------------------------------------------------

def birlestir(manifest: dict | list[dict],
              ocr_indeksi: dict,
              vlm_fazlari: list[dict] | dict[int, dict],
              esikler: dict | None = None,
              cfg: dict | None = None) -> dict:
    """Tüm kanalları birleştirir ve nihai sınıflandırılmış satır listesini üretir."""
    cfg = cfg or {}
    esikler = esikler or {}
    E1 = float(esikler.get("E1") if esikler.get("E1") is not None else cfg.get("esik", {}).get("E1") or VARSAYILAN_E1)
    E2 = float(esikler.get("E2") if esikler.get("E2") is not None else cfg.get("esik", {}).get("E2") or VARSAYILAN_E2)
    pay = int(cfg.get("kanit", {}).get("kare_payi", VARSAYILAN_KARE_PAYI))
    hakem_modu = str(cfg.get("diakritik_hakem", "ocr_kazanir"))

    if isinstance(vlm_fazlari, dict):
        faz_listesi = [vlm_fazlari[k] for k in sorted(vlm_fazlari.keys())]
    else:
        faz_listesi = list(vlm_fazlari)

    if not faz_listesi:
        satirlar_faz0 = []
        satirlar_fazK = []
    elif len(faz_listesi) == 1:
        satirlar_faz0 = faz_listesi[0].get("satirlar", [])
        satirlar_fazK = []
    else:
        satirlar_faz0 = faz_listesi[0].get("satirlar", [])
        satirlar_fazK = faz_listesi[1].get("satirlar", [])

    if satirlar_fazK:
        birlesik_adaylar = fazlari_hizala(satirlar_faz0, satirlar_fazK)
    else:
        birlesik_adaylar = [dict(s, faz_tutar=True, fazlar=[0]) for s in satirlar_faz0]

    # Rol ve isim çiftlerini birleştir
    birlesik_adaylar = rol_isim_birlestir(birlesik_adaylar, ocr_indeksi, pay=pay)

    for aday in birlesik_adaylar:
        metin = aday.get("metin", "")
        aralik = aday.get("kare_araligi") or [1, 8]
        ocr_sonuc = ara(ocr_indeksi, metin, aralik, pay=pay)
        aday["ocr_skor"] = ocr_sonuc.get("ocr_skor", 0.0)
        aday["ocr_kare_no"] = ocr_sonuc.get("kare_no")
        aday["y_orani"] = ocr_sonuc.get("y_orani")
        aday["guven"] = ocr_sonuc.get("guven")
        aday["tip"] = ocr_sonuc.get("tip")
        aday["zayif_birlesim"] = ocr_sonuc.get("zayif_birlesim", False)
        aday["eslesen_metin"] = ocr_sonuc.get("eslesen_metin")
        if "catisma" in ocr_sonuc:
            aday["catisma"] = ocr_sonuc["catisma"]

    pencere_raporu = pencere_ve_sahne_kaniti(birlesik_adaylar, ocr_indeksi, manifest)
    konum_tutarliligi_denetle(birlesik_adaylar)
    kumeli_adaylar = kanit_capasiyla_kumele(birlesik_adaylar, kare_payi=pay)
    adaylari_siniflandir(kumeli_adaylar, E1=E1, E2=E2)
    hakem_degisen = diakritik_hakemligi_uygula(kumeli_adaylar, mod=hakem_modu)

    nihai_satirlar = []
    sinif_dagilimi = {"KESIN": 0, "ZAYIF": 0, "CATISMA": 0, "SUPHELI": 0}
    for a in kumeli_adaylar:
        sinif = a["sinif"]
        sinif_dagilimi[sinif] = sinif_dagilimi.get(sinif, 0) + 1
        kayit = {
            "metin": a["metin"],
            "sinif": sinif,
            "ocr_skor": round(float(a.get("ocr_skor_etkin", a.get("ocr_skor", 0.0))), 4),
            "ocr_kare": a.get("ocr_kare_no"),
            "y_orani": round(float(a["y_orani"]), 4) if a.get("y_orani") is not None else None,
            "guven_min": round(float(a["guven"]), 4) if a.get("guven") is not None else None,
            "faz_tutar": bool(a.get("faz_tutar", False)),
            "catisma": a.get("catisma"),
            "kare_araligi": a.get("kare_araligi"),
            "ilk_grup": a.get("grup_no"),
            "varyantlar": a.get("varyantlar", []),
            "dejenerasyon": bool(a.get("dejenerasyon", False)),
            "sahne_riski": bool(a.get("sahne_riski", False)),
        }
        if "hakem" in a:
            kayit["hakem"] = a["hakem"]
        nihai_satirlar.append(kayit)

    kanit_ozeti = {
        "esikler": {"E1": E1, "E2": E2, "kare_payi": pay},
        "diakritik_hakem": {"mod": hakem_modu, "degisen_sayisi": hakem_degisen},
        "sinif_dagilimi": sinif_dagilimi,
        "toplam_aday": len(birlesik_adaylar),
        "kumelenmis_aday": len(kumeli_adaylar),
        "pencere": pencere_raporu,
        "ocr_kanit": ocr_indeksi.get("kanit", {}),
        "vlm_fazlar": [f.get("kanit", {}) for f in faz_listesi],
    }

    return {"satirlar": nihai_satirlar, "kanit": kanit_ozeti}
