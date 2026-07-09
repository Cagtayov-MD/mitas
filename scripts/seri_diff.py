#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""seri_diff.py — dizi modu: LOCKED seri master'ı vs BolumOkuma SAF diff motoru.

Sözleşme: scripts/dizi_SISTEM.md "Diff çıktı şeması" + "Diff politikası ve kuralları" (1-7).
KISITLAR:
  • SAF modül — IO/ağ/DB YOK; `diffle` master'ı DEĞİŞTİRMEZ, `uygula` derin-kopya üzerinde çalışır.
  • Eşleşme YALNIZ `credit_crosscheck.name_match` (sıkı) VEYA okunan yazımın master tanık
    `yazimlar` anahtarlarında fold-birebir geçmesi. `name_close` bu eşikte KULLANILMAZ.
  • Aynı bölümde birlikte görülen iki isim ASLA birleştirilmez → üye eşleşmesi ENJEKTİF
    (bir master girdisine en çok BİR okunan yazım; artan yazım ayrı kişi sayılır).
  • Master güncellemesi (kalıcı değişim) tek motor kanıtıyla YAPILMAZ — VL çapraz-tanık şart;
    yoksa MASTER_ADAY beklemede + KONTROL ("okunamadı > yanlış oku").
  • `seri_kayit.versiyon_atla` İTHAL EDİLMEZ — aynı semantik (alanlar[..]=yeni + master_surum+1
    + surum_gecmisi append) burada uygulanır ki modül saf/bağımsız kalsın.
"""
from __future__ import annotations

import copy
import os
import sys
from dataclasses import dataclass

_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from credit_crosscheck import fold, name_match  # noqa: E402  (kural 1: tek eşleşme otoritesi)
from credit_text_read import _looks_garble      # noqa: E402  (kural 4: garble sinyali)

# dizi_SISTEM.md "TEKİL alanlar" — şema sözleşmesi
TEKIL_ALANLAR = ("Yönetmen", "Yapımcı", "Senaryo", "Müzik", "Görüntü Yönetmeni", "Kurgu")


@dataclass
class DiffPolitika:
    eksik_esik: int = 3       # ardışık kaç bölüm yoksa AYRILDI
    kalici_esik: int = 2      # aynı fark kaç ardışık bölümde (VL-teyitli) → master güncelle
    terfi_esik: int = 3       # konuk kaç bölümde görülünce AKTIF kadroya
    konuk_max: int = 12       # bölümde bundan çok yeni isim → OCR patlaması → KONTROL
    kopus_esik: float = 0.40  # eşleşme oranı bunun altındaysa FORMAT_KOPUSU


# --------------------------------------------------------------------- eşleşme
def _yazim_foldlari(yazimlar):
    return {fold(y) for y in (yazimlar or {})}


def _isim_eslesir(okunan, kanonik, yazimlar=None):
    """Kural 1: name_match VEYA okunan yazımın tanık `yazimlar` anahtarlarında fold-birebir
    geçmesi. Kanonik yazımın kendisiyle fold-birebir eşitlik de eşleşmedir (kısa-token
    adlarda name_match'in bilinçli reddine karşı güvence — kanonik zaten tanıktır)."""
    fo = fold(okunan)
    if not fo:
        return False
    if fo == fold(kanonik):
        return True
    if name_match(okunan, kanonik):
        return True
    return fo in _yazim_foldlari(yazimlar)


def _oncelik(okunan, kanonik, yazimlar):
    """Enjektif seçim önceliği: 0=kanonikle fold-birebir, 1=tanık-yazım, 2=name_match.
    None → eşleşme yok. İki benzer yazım aynı bölümdeyse exact olan kazanır (kural 1 istisnası
    tek kişiye bağlanır; diğeri AYRI kişi kalır)."""
    fo = fold(okunan)
    if not fo:
        return None
    if fo == fold(kanonik):
        return 0
    if fo in _yazim_foldlari(yazimlar):
        return 1
    if name_match(okunan, kanonik):
        return 2
    return None


def _vl_isimleri(vl, alan):
    """VL teyidi hangi listeden okunur (kural 5): Yönetmen→yonetmen, cast→oyuncular,
    diğer TEKİL alanlar→diger_roller."""
    vl = vl or {}
    if alan == "Yönetmen":
        return vl.get("yonetmen") or []
    if alan == "oyuncular":
        return vl.get("oyuncular") or []
    return vl.get("diger_roller") or []


def _vl_teyitli(deger, vl, alan):
    return any(fold(deger) == fold(v) or name_match(deger, v)
               for v in _vl_isimleri(vl, alan))


# ------------------------------------------------------------------------ diffle
def diffle(master: dict, okuma: dict, politika: DiffPolitika = DiffPolitika()) -> dict:
    """LOCKED master ile BolumOkuma'yı karşılaştırır → dizi_SISTEM.md diff şeması.
    SAF: master DEĞİŞTİRİLMEZ. NOT: DEGISIM_ADAYI `yeni` girdilerine `vl_teyit` bayrağı
    eklenir — `uygula` bekleyen_degisimler'in VL defterini bununla tutar (şemaya EK alan;
    çıkarılmaz, çünkü uygula okuma nesnesini görmez)."""
    n = okuma.get("bolum_no")
    diff = {
        "bolum_no": n,
        "eslesen": {"oyuncular": [], "alanlar": {}},
        "eksik": [],
        "yeni": [],
        "kalici_degisim": [],
        "terfi": [],
        "format_kopusu": False,
        "bolum_ozel": {"konuk_oyuncular": [], "alan_override": {}},
        "kontrol_nedenleri": [],
    }
    oyuncular = master.get("oyuncular") or {}
    alanlar = master.get("alanlar") or {}
    crew = okuma.get("crew") or {}
    vl = okuma.get("vl") or {}
    cast_okuma = [s for s in (okuma.get("cast") or []) if s]
    konuk_acik = [s for s in (okuma.get("konuk_acik") or []) if s]

    # ---- kural 6: FORMAT_KOPUSU — payda = oyuncular(AKTIF) + alanlar kanonikleri
    # (ZAYIF_UYE/AYRILDI paydaya girmez — sözleşme "oyuncular(AKTIF)" der; muhafazakâr okuma).
    havuz = cast_okuma + konuk_acik + [x for v in crew.values() for x in (v or [])]
    beklenen = [(ad, k.get("yazimlar")) for ad, k in oyuncular.items()
                if k.get("durum") == "AKTIF"]
    for _alan, f in alanlar.items():
        tanik = f.get("tanik") or {}
        for kn in (f.get("kanonik") or []):
            beklenen.append((kn, (tanik.get(kn) or {}).get("yazimlar")))
    if beklenen:
        hit = sum(1 for ad, yz in beklenen
                  if any(_isim_eslesir(r, ad, yz) for r in havuz))
        if hit / len(beklenen) < politika.kopus_esik:
            # alan-alan diff YAPILMAZ: eksik/yeni üretilmez, tek KONTROL nedeni
            diff["format_kopusu"] = True
            diff["kontrol_nedenleri"].append(
                "FORMAT_KOPUSU: master eşleşme oranı %d/%d < %.2f (bölüm %s)"
                % (hit, len(beklenen), politika.kopus_esik, n))
            return diff

    # ---- kural 2/3: üye eşleşmesi (ENJEKTİF) — konuk_acik da varlık kanıtıdır
    # (jenerik-başlığı altına düşmüş AKTİF üye yanlışlıkla AYRILDI sayılmasın).
    havuz_uye = [(s, "cast") for s in cast_okuma] + [(s, "konuk_acik") for s in konuk_acik]
    kullanilan = set()
    eslesen_uyeler = set()

    def _uye_esle(ad, kayit):
        en_iyi = None  # (oncelik, index)
        for i, (s, _src) in enumerate(havuz_uye):
            if i in kullanilan:
                continue
            o = _oncelik(s, ad, kayit.get("yazimlar"))
            if o is None:
                continue
            if en_iyi is None or o < en_iyi[0]:
                en_iyi = (o, i)
                if o == 0:
                    break
        if en_iyi is None:
            return None
        kullanilan.add(en_iyi[1])
        return havuz_uye[en_iyi[1]][0]

    for ad, kayit in oyuncular.items():
        if kayit.get("durum") not in ("AKTIF", "ZAYIF_UYE"):
            continue
        okunan = _uye_esle(ad, kayit)
        if okunan is None:
            continue
        eslesen_uyeler.add(ad)
        diff["eslesen"]["oyuncular"].append({"master": ad, "okunan": okunan})

    # kural 4: AYRILDI üyenin dönüşü konuk DEĞİL → yeniden eşleşen (uygula AKTIF'e çevirir)
    for ad, kayit in oyuncular.items():
        if kayit.get("durum") != "AYRILDI":
            continue
        okunan = _uye_esle(ad, kayit)
        if okunan is None:
            continue
        eslesen_uyeler.add(ad)
        diff["eslesen"]["oyuncular"].append({"master": ad, "okunan": okunan})

    # kural 3: master VAR + bölüm YOK → eksik (KONTROL YOK; isim kanondan yine basılır)
    for ad, kayit in oyuncular.items():
        if kayit.get("durum") not in ("AKTIF", "ZAYIF_UYE") or ad in eslesen_uyeler:
            continue
        ayy = int(kayit.get("ardisik_yok") or 0) + 1
        diff["eksik"].append({
            "alan": "oyuncular", "isim": ad, "ardisik_yok_yeni": ayy,
            "karar": "AYRILDI" if ayy >= politika.eksik_esik else "OCR_KACAK",
        })

    # ---- kural 4 + 7: bölüm VAR + master YOK (cast) → KONUK_ADAYI / terfi
    konuk_gecmisi = master.get("konuk_gecmisi") or {}
    for i, (s, src) in enumerate(havuz_uye):
        if i in kullanilan:
            continue
        # terfi kontrolü: konuk_gecmisi'nde bu isim + bu bölüm = terfi_esik FARKLI bölüm?
        anahtar = next((kad for kad, kk in konuk_gecmisi.items()
                        if _isim_eslesir(s, kad, kk.get("yazimlar"))), None)
        if anahtar is not None:
            bolumler = sorted(set((konuk_gecmisi[anahtar].get("bolumler") or [])) | {n})
            if len(bolumler) >= politika.terfi_esik:
                # terfi eden isim konuk/yeni listelerine GİRMEZ — kadroya taşınacak
                diff["terfi"].append({"isim": anahtar, "bolumler": bolumler})
                continue
        kaynak = "jenerik-basligi" if src == "konuk_acik" else "cast-diff"
        diff["yeni"].append({"alan": "oyuncular", "isim": s,
                             "karar": "KONUK_ADAYI", "kaynak": kaynak})
        diff["bolum_ozel"]["konuk_oyuncular"].append(
            {"isim": s, "kaynak": kaynak, "kesin": src == "konuk_acik"})

    yeni_oyuncu = sum(1 for y in diff["yeni"] if y["alan"] == "oyuncular")
    if yeni_oyuncu > politika.konuk_max:
        diff["kontrol_nedenleri"].append(
            "yeni-isim patlaması: %d > konuk_max=%d (bölüm %s)"
            % (yeni_oyuncu, politika.konuk_max, n))

    # ---- kural 2/3/4: TEKİL alanlar (teknik_ekip rolleri bu motorun kapsamı DIŞI —
    # sözleşme diff kurallarında yalnız oyuncular + TEKİL alanları tanımlar)
    for alan in TEKIL_ALANLAR:
        f = alanlar.get(alan) or {}
        kanonik = list(f.get("kanonik") or [])
        tanik = f.get("tanik") or {}
        okunanlar = [s for s in (crew.get(alan) or []) if s]
        if not kanonik and not okunanlar:
            continue
        kalan = list(okunanlar)
        es_m, es_o = [], []
        for kn in kanonik:
            yz = (tanik.get(kn) or {}).get("yazimlar")
            hit = next((s for s in kalan if _isim_eslesir(s, kn, yz)), None)
            if hit is not None:
                es_m.append(kn)
                es_o.append(hit)
                kalan.remove(hit)
        if es_m:
            diff["eslesen"]["alanlar"][alan] = {"master": es_m, "okunan": es_o}
        if kanonik and not okunanlar:
            # alan bölümde HİÇ okunmadı → OCR_KACAK (alan için kalıcı yokluk sayacı YOK —
            # ardisik_yok_yeni hep 1 kalır, alan asla "AYRILDI" olmaz; kanondan basılır)
            for kn in kanonik:
                diff["eksik"].append({"alan": alan, "isim": kn,
                                      "ardisik_yok_yeni": 1, "karar": "OCR_KACAK"})
        for s in kalan:
            garble = _looks_garble(s)
            diff["yeni"].append({"alan": alan, "isim": s, "karar": "DEGISIM_ADAYI",
                                 "vl_teyit": _vl_teyitli(s, vl, alan)})
            if garble is None:
                diff["bolum_ozel"]["alan_override"].setdefault(alan, []).append(s)
                diff["kontrol_nedenleri"].append(
                    "%s master'dan farklı: '%s' (bölüm %s)" % (alan, s, n))
            else:
                # garble → override YOK, master basılır ("okunamadı > yanlış oku")
                diff["kontrol_nedenleri"].append(
                    "%s okuması garble (%s): '%s' — override yok, master basılır (bölüm %s)"
                    % (alan, garble, s, n))

    # ---- kural 5: kalıcı değişim — bekleyen + bu bölüm = kalici_esik ARDIŞIK ve HER
    # görüldüğü bölümde VL aynı değeri içeriyor → kalici_degisim; VL eksikse beklemede.
    for p in (master.get("bekleyen_degisimler") or []):
        if p.get("tip") != "alan_degisim":
            continue
        alan = p.get("alan")
        hedef = list(p.get("yeni") or [])
        ay = next((y for y in diff["yeni"]
                   if y["alan"] == alan and y["karar"] == "DEGISIM_ADAYI"
                   and any(fold(y["isim"]) == fold(h) or name_match(y["isim"], h)
                           for h in hedef)), None)
        if ay is None:
            continue  # fark bu bölümde görülmedi (uygula bekleyeni sıfırlar)
        gorulen = list(p.get("gorulen_bolumler") or [])
        if not gorulen or gorulen[-1] != (n - 1 if isinstance(n, int) else None):
            continue  # ardışık değil → kalıcı sayılmaz (uygula taze kayda sıfırlar)
        if len(gorulen) + 1 < politika.kalici_esik:
            continue
        vl_tam = bool(ay.get("vl_teyit")) and \
            set(p.get("vl_teyit_bolumler") or []) >= set(gorulen)
        if vl_tam:
            diff["kalici_degisim"].append({"alan": alan, "yeni": hedef,
                                           "kanit_bolumler": sorted(gorulen) + [n]})
        else:
            diff["kontrol_nedenleri"].append(
                "MASTER_ADAY beklemede (VL çapraz-tanık eksik): %s=%s (bölüm %s)"
                % (alan, hedef, n))
    return diff


# ------------------------------------------------------------------------ uygula
def uygula(master: dict, diff: dict, politika: DiffPolitika = DiffPolitika(),
           simdi: str = "") -> tuple[dict, list[dict]]:
    """Diff'i master KOPYASINA işler → (yeni_master, olaylar). SAF: girdi değişmez.
    Dönen olaylar gecmis.jsonl'e yazılmak üzere (çağıran yazar; bu modül IO yapmaz)."""
    m = copy.deepcopy(master)
    olaylar: list[dict] = []
    n = diff.get("bolum_no")

    def _olay(tip, **ek):
        ev = {"ts": simdi, "bolum": n, "tip": tip}
        ev.update(ek)
        olaylar.append(ev)

    m.setdefault("format_kopusu", {"ardisik": 0, "ilk_bolum": None})

    # ---- kural 6: kopuş bölümü — sayaç dışında HİÇBİR duruma dokunulmaz
    # (bozuk-OCR bölümüyle üye cezalandırılmaz, bekleyen kayıtlar sıfırlanmaz).
    if diff.get("format_kopusu"):
        fk = m["format_kopusu"]
        fk["ardisik"] = int(fk.get("ardisik") or 0) + 1
        if fk.get("ilk_bolum") is None:
            fk["ilk_bolum"] = n
        if fk["ardisik"] == 2:  # olay 2. ardışıkta BİR KEZ günlüğe (dizi_isle tohum açar)
            _olay("format_kopusu", ardisik=fk["ardisik"], ilk_bolum=fk["ilk_bolum"])
            m.setdefault("surum_gecmisi", []).append(
                {"surum": m.get("master_surum"), "olay": "format_kopusu",
                 "bolumler": [fk["ilk_bolum"], n], "ts": simdi})
        m["guncelleme"] = {"ts": simdi, "modul": "seri_diff", "bolum": n}
        return m, olaylar
    m["format_kopusu"] = {"ardisik": 0, "ilk_bolum": None}

    oyuncular = m.setdefault("oyuncular", {})

    # ---- eşleşen oyuncular: tanık + son_gorulme + ardisik_yok=0; AYRILDI dönüşü → AKTIF
    for e in (diff.get("eslesen") or {}).get("oyuncular") or []:
        kayit = oyuncular.get(e["master"])
        if kayit is None:
            continue
        if n is not None and n not in (kayit.get("bolumler") or []):
            kayit["bolumler"] = sorted(set(kayit.get("bolumler") or []) | {n})
        yaz = kayit.setdefault("yazimlar", {})
        yaz[e["okunan"]] = yaz.get(e["okunan"], 0) + 1
        kayit["son_gorulme"] = n
        kayit["ardisik_yok"] = 0
        if kayit.get("durum") == "AYRILDI":
            kayit["durum"] = "AKTIF"
            kayit["ayrilma_bolumu"] = None
            _olay("geri_donus", isim=e["master"])

    # ---- eşleşen TEKİL alanlar: tanık defteri
    for alan, e in ((diff.get("eslesen") or {}).get("alanlar") or {}).items():
        f = (m.get("alanlar") or {}).get(alan)
        if f is None:
            continue
        tk = f.setdefault("tanik", {})
        for kn, okunan in zip(e.get("master") or [], e.get("okunan") or []):
            t = tk.setdefault(kn, {"bolumler": [], "yazimlar": {}})
            t["bolumler"] = sorted(set(t.get("bolumler") or []) | ({n} if n is not None else set()))
            t.setdefault("yazimlar", {})
            t["yazimlar"][okunan] = t["yazimlar"].get(okunan, 0) + 1

    # ---- kural 3: eksik oyuncular — ardisik_yok güncelle; eşikte AYRILDI + olay
    for e in diff.get("eksik") or []:
        if e.get("alan") != "oyuncular":
            continue  # alan-eksiğinde kalıcı sayaç yok (kanondan basılır)
        kayit = oyuncular.get(e["isim"])
        if kayit is None:
            continue
        kayit["ardisik_yok"] = e["ardisik_yok_yeni"]
        if e.get("karar") == "AYRILDI" and kayit.get("durum") != "AYRILDI":
            kayit["durum"] = "AYRILDI"
            kayit["ayrilma_bolumu"] = n
            m.setdefault("surum_gecmisi", []).append(
                {"surum": m.get("master_surum"), "olay": "ayrilma",
                 "isim": e["isim"], "bolum": n, "ts": simdi})
            _olay("ayrilma", isim=e["isim"], ardisik_yok=e["ardisik_yok_yeni"])

    # ---- kural 5: kalıcı değişim → versiyon_atla SEMANTİĞİ (import edilmez):
    # alanlar[..]=yeni + master_surum+1 + surum_gecmisi append
    for k in diff.get("kalici_degisim") or []:
        alan, yeni = k["alan"], list(k.get("yeni") or [])
        kanit = list(k.get("kanit_bolumler") or [])
        f = m.setdefault("alanlar", {}).setdefault(
            alan, {"kanonik": [], "guven": "KESIN", "kb_teyit": False, "tanik": {}})
        f["kanonik"] = list(yeni)
        tk = f.setdefault("tanik", {})
        for ad in yeni:
            t = tk.setdefault(ad, {"bolumler": [], "yazimlar": {}})
            t["bolumler"] = sorted(set(t.get("bolumler") or []) | set(kanit))
            t.setdefault("yazimlar", {})
            t["yazimlar"][ad] = t["yazimlar"].get(ad, 0) + len(kanit)
        m["master_surum"] = int(m.get("master_surum") or 0) + 1
        m.setdefault("surum_gecmisi", []).append(
            {"surum": m["master_surum"], "olay": "kalici_degisim", "alan": alan,
             "yeni": list(yeni), "bolumler": kanit, "ts": simdi})
        _olay("kalici_degisim", alan=alan, yeni=list(yeni), kanit_bolumler=kanit)

    # ---- bekleyen_degisimler yönetimi (kural 5):
    #   fark görülmedi → kayıt düşer; ardışık değil → taze kayda sıfırlanır;
    #   ardışık → bölüm eklenir (+ VL defteri); kalıcı işlenen alan → kayıt kapanır.
    adaylar = [y for y in (diff.get("yeni") or []) if y.get("karar") == "DEGISIM_ADAYI"]
    kalici_alanlar = {k["alan"] for k in (diff.get("kalici_degisim") or [])}
    tuketilen = set()
    yeni_bekleyen = []
    for p in (m.get("bekleyen_degisimler") or []):
        if p.get("tip") != "alan_degisim":
            yeni_bekleyen.append(p)
            continue
        if p.get("alan") in kalici_alanlar:
            continue  # master'a işlendi
        hedef = list(p.get("yeni") or [])
        es = next((i for i, y in enumerate(adaylar)
                   if i not in tuketilen and y["alan"] == p.get("alan")
                   and any(fold(y["isim"]) == fold(h) or name_match(y["isim"], h)
                           for h in hedef)), None)
        if es is None:
            continue  # araya farksız bölüm girdi → bekleyen SIFIRLANIR (kayıt düşer)
        tuketilen.add(es)
        ay = adaylar[es]
        gorulen = list(p.get("gorulen_bolumler") or [])
        if gorulen and gorulen[-1] == n:
            yeni_bekleyen.append(p)  # aynı bölüm zaten kayıtlı (idempotent)
        elif gorulen and isinstance(n, int) and gorulen[-1] == n - 1:
            p2 = copy.deepcopy(p)
            p2["gorulen_bolumler"] = gorulen + [n]
            if ay.get("vl_teyit"):
                p2.setdefault("vl_teyit_bolumler", []).append(n)
            yeni_bekleyen.append(p2)
        else:
            yeni_bekleyen.append({
                "tip": "alan_degisim", "alan": p.get("alan"), "yeni": [ay["isim"]],
                "gorulen_bolumler": [n],
                "vl_teyit_bolumler": [n] if ay.get("vl_teyit") else [],
                "ilk_bolum": n})
    for i, ay in enumerate(adaylar):
        if i in tuketilen or ay["alan"] in kalici_alanlar:
            continue
        yeni_bekleyen.append({
            "tip": "alan_degisim", "alan": ay["alan"], "yeni": [ay["isim"]],
            "gorulen_bolumler": [n],
            "vl_teyit_bolumler": [n] if ay.get("vl_teyit") else [],
            "ilk_bolum": n})
    m["bekleyen_degisimler"] = yeni_bekleyen

    # ---- konuk_gecmisi güncelle (diff bolum_ozel.konuk_oyuncular üzerinden)
    kg = m.setdefault("konuk_gecmisi", {})
    for g in (diff.get("bolum_ozel") or {}).get("konuk_oyuncular") or []:
        s = g["isim"]
        anahtar = next((kad for kad, kk in kg.items()
                        if _isim_eslesir(s, kad, kk.get("yazimlar"))), None)
        kayit = kg.setdefault(anahtar or s, {"bolumler": [], "yazimlar": {}})
        kayit["bolumler"] = sorted(set(kayit.get("bolumler") or []) | ({n} if n is not None else set()))
        kayit.setdefault("yazimlar", {})
        kayit["yazimlar"][s] = kayit["yazimlar"].get(s, 0) + 1

    # ---- kural 7: terfi → AKTIF kadroya, sira = mevcut max+1; konuk_gecmisi'nden çıkar
    for t in diff.get("terfi") or []:
        isim = t["isim"]
        gk = kg.pop(isim, None) or {"bolumler": [], "yazimlar": {}}
        yaz = dict(gk.get("yazimlar") or {})
        yaz[isim] = yaz.get(isim, 0) + 1  # bu bölümdeki görülme
        sira = max([int(o.get("sira") or 0) for o in oyuncular.values()], default=-1) + 1
        oyuncular[isim] = {
            "yazimlar": yaz,
            "bolumler": sorted(set(t.get("bolumler") or []) | ({n} if n is not None else set())),
            "sira": sira, "kb_teyit": False, "durum": "AKTIF",
            "son_gorulme": n, "ardisik_yok": 0, "ayrilma_bolumu": None}
        m.setdefault("surum_gecmisi", []).append(
            {"surum": m.get("master_surum"), "olay": "terfi", "isim": isim,
             "bolumler": list(t.get("bolumler") or []), "ts": simdi})
        _olay("terfi", isim=isim, bolumler=list(t.get("bolumler") or []))

    # ---- ZAYIF_UYE 5-bölüm kuralı: kilitten sonraki 5 bölümün >=2'sinde görülmediyse
    # konuk_gecmisi'ne düşer. Konuk defterine YALNIZ pencere görülmeleri taşınır —
    # tohum bölümleri sayılırsa tek konuk-görünümüyle anında geri-terfi döngüsü doğar.
    kilitler = m.get("kilit_bolumler") or []
    son_kilit = max(kilitler) if kilitler else None
    if son_kilit is not None and isinstance(n, int) and n >= son_kilit + 5:
        for ad in list(oyuncular.keys()):
            kayit = oyuncular[ad]
            if kayit.get("durum") != "ZAYIF_UYE":
                continue
            pencere = [b for b in (kayit.get("bolumler") or [])
                       if son_kilit < b <= son_kilit + 5]
            if len(pencere) >= 2:
                continue
            oyuncular.pop(ad)
            kayit_kg = kg.setdefault(ad, {"bolumler": [], "yazimlar": {}})
            kayit_kg["bolumler"] = sorted(set(kayit_kg.get("bolumler") or []) | set(pencere))
            kayit_kg.setdefault("yazimlar", {})
            for yz, c in (kayit.get("yazimlar") or {}).items():
                kayit_kg["yazimlar"][yz] = kayit_kg["yazimlar"].get(yz, 0) + c
            _olay("zayif_dusme", isim=ad, pencere=pencere)

    m["guncelleme"] = {"ts": simdi, "modul": "seri_diff", "bolum": n}
    return m, olaylar
