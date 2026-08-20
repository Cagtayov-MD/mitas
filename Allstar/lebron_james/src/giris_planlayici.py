"""Giriş jeneriği için yalnız yazılı karelerden güvenli master üretimi.

Kapanış jeneriği çoğunlukla tek yönde kayan sürekli bir akıştır; LeBron'un
faz-korelasyonlu dikişi bu geometri için tasarlanmıştır. Giriş jeneriğinde ise
aynı akışa statik oyuncu kartları, dissolve geçişleri ve uzun görüntü araları
karışır. Ardışık bütün kareleri kayma motoruna vermek farklı kartları aynı
statik zeminde birleştirip sessizce kaybettirebilir.

Bu modül girişte daha muhafazakâr bir sözleşme uygular:

* Paddle'ın pikselde gerçekten yazı kutusu gördüğü kareler adaydır.
* Zamansal olarak aynı karta ait tekrarlar gruplanır.
* Her grubun en sağlam tam karesi seçilir; grubun kalıcı tokenlarını tek kare
  kapsamıyorsa ek tam kareler seçilir.
* Geçiş/footage kareleri mastera hiç girmez. Kaynak dosyalar silinmez.

Çıktı bir "okuma masterı"dır; estetik video panoraması değildir. Önceliği
yazı kaybetmemek ve yarım dikiş üretmemektir.
"""
from __future__ import annotations

from difflib import SequenceMatcher
import math
import re
import unicodedata

import cv2
import numpy as np


# URETIM KILIDI (giris-text-only/v1): Bunlar kullanici ayari degildir.
# Esik veya gruplama davranisi ancak surum artisi, bu modülün regresyon
# testleri ve gerçek temiz toplu kabul birlikte yenilenerek degistirilir.
# config.yaml ya da CLI üzerinden gevsetilecek bir kaçis anahtari eklenmez.
PLAN_SURUMU = "giris-text-only/v1"
MIN_GUVEN = 0.35
GRUP_KARE_BOSLUGU = 2       # 2 fps'te tek OCR kaçağını tolere et
AYNI_TOKEN_KAPSAMA = 0.60
AYNI_METIN_ORANI = 0.90
NGRAM_KAPSAMA = 0.75
KART_KOPRU_MAKS_KARE = 32  # 2 fps'te aynı bindirme en çok 16 sn kesilebilir


def _norm(metin: str) -> str:
    metin = unicodedata.normalize("NFKD", str(metin or "")).upper()
    # Paddle aynı kartı bazen Türkçe karakterli, bazen ASCII ve bazen
    # de kelimeleri birleştirerek okuyor. Bunlar yeni kart değil.
    metin = metin.replace("ı", "I").replace("İ", "I")
    metin = "".join(c for c in metin if not unicodedata.combining(c))
    return " ".join(re.findall(r"[^\W_]+", metin, flags=re.UNICODE))


def _kompakt(metinler: list[str]) -> str:
    return "".join(_norm(" ".join(metinler)).split())


def _ngramlar(metinler: list[str], n: int = 3) -> set[str]:
    metin = _kompakt(metinler)
    return {metin[i:i + n] for i in range(max(0, len(metin) - n + 1))}


def _goruntu_ozeti(im: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    gri = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    gri = cv2.resize(gri, (128, 72), interpolation=cv2.INTER_AREA)
    return gri, cv2.Canny(gri, 50, 150) > 0


def _goruntu_surekli(a: dict, b: dict) -> bool:
    ga, ea = a["goruntu_ozeti"]
    gb, eb = b["goruntu_ozeti"]
    sa, sb = ga.astype(np.float32).ravel(), gb.astype(np.float32).ravel()
    if float(sa.std()) < 1e-6 or float(sb.std()) < 1e-6:
        ncc = 1.0 if np.array_equal(ga, gb) else 0.0
    else:
        ncc = float(np.corrcoef(sa, sb)[0, 1])
    birlesim = int(np.logical_or(ea, eb).sum())
    kenar_iou = (int(np.logical_and(ea, eb).sum()) / birlesim
                 if birlesim else 0.0)
    return ncc >= 0.965 or kenar_iou >= 0.55


def _tokenler(metinler: list[str]) -> set[str]:
    return {t for metin in metinler for t in _norm(metin).split() if len(t) >= 2}


def _harf_sayisi(metinler: list[str]) -> int:
    return sum(1 for metin in metinler for c in metin if c.isalnum())


def _buyuk_harf_orani(metin: str) -> float:
    harfler = [c for c in metin if c.isalpha()]
    return (sum(1 for c in harfler if c.isupper()) / len(harfler)) if harfler else 0.0


def _bbox_iou(a: list[int] | None, b: list[int] | None) -> float:
    if not a or not b:
        return 0.0
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    kes = max(0, x1 - x0) * max(0, y1 - y0)
    aa = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
    bb = max(0, b[2] - b[0]) * max(0, b[3] - b[1])
    return kes / (aa + bb - kes) if aa + bb - kes else 0.0


def _birlesik_bbox(satirlar: list[dict]) -> list[int] | None:
    kutular = [s.get("bbox") for s in satirlar if s.get("bbox")]
    if not kutular:
        return None
    return [min(b[0] for b in kutular), min(b[1] for b in kutular),
            max(b[2] for b in kutular), max(b[3] for b in kutular)]


def _kare_no(kaynak: str, varsayilan: int) -> int:
    m = re.search(r"(\d+)(?=\.[^.]+$)", str(kaynak))
    return int(m.group(1)) if m else int(varsayilan)


def kare_kaniti(index: int, kaynak: str, im: np.ndarray,
                analiz: dict | None) -> dict:
    """Paddle satır kanıtını küçük, JSON-uyumlu plan kaydına çevir."""
    h, w = im.shape[:2]
    goruntu_ozeti = _goruntu_ozeti(im)
    if analiz is None:
        return {"index": index, "kare_no": _kare_no(kaynak, index + 1),
                "kaynak": kaynak, "analiz_hatasi": True, "aday": False,
                "guclu": False, "altyazi": False, "tokenler": set(),
                "metinler": [], "bbox": None, "skor": 0.0,
                "goruntu_ozeti": goruntu_ozeti}

    satirlar = []
    for s in analiz.get("satirlar") or []:
        try:
            guven = float(s.get("confidence"))
        except (TypeError, ValueError):
            continue
        if guven < MIN_GUVEN or not str(s.get("text") or "").strip():
            continue
        satirlar.append({"text": str(s["text"]).strip(), "confidence": guven,
                         "bbox": list(s.get("bbox") or [])})

    metinler = [s["text"] for s in satirlar]
    tokenler = _tokenler(metinler)
    bbox = _birlesik_bbox(satirlar)
    harf = _harf_sayisi(metinler)
    kutu_n = int(analiz.get("kutu_n") or 0)
    guvenler = [s["confidence"] for s in satirlar]

    # Diyalog altyazısını kredi sanma: yalnız alt bölgede duran, uzun/cümle
    # biçimli 1-2 satır. Büyük-harf kısa isim kartları bu kapıya girmez.
    alt_bolge = bool(satirlar) and all((s.get("bbox") or [0, 0, 0, 0])[1] >= 0.64 * h
                                      for s in satirlar)
    kelime_n = sum(len(_norm(m).split()) for m in metinler)
    noktalama = any(str(m).rstrip().endswith((".", "?", "!", ":", ";"))
                    for m in metinler)
    buyuk_isim = any(_buyuk_harf_orani(m) >= 0.72 and 1 <= len(_norm(m).split()) <= 4
                     for m in metinler)
    altyazi = (alt_bolge and len(satirlar) <= 2 and (kelime_n >= 5 or noktalama)
               and not buyuk_isim)

    guclu = bool(satirlar) and not altyazi and (
        (harf >= 4 and max(guvenler, default=0.0) >= MIN_GUVEN)
        or (len(satirlar) >= 2 and harf >= 2))
    # Rec kısa/başarısız olabilir; gerçek det kutusunu hemen atmak yerine
    # zamansal süreklilik kanıtına bırakıyoruz. Tek başına mastera giremez.
    aday = not altyazi and kutu_n > 0
    keskinlik = float(cv2.Laplacian(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY),
                                   cv2.CV_64F).var())
    bbox_alan = (max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1])
                 if bbox else 0)
    skor = (100.0 * (sum(guvenler) / len(guvenler)) if guvenler else 0.0)
    skor += min(harf, 120) + 20.0 * (bbox_alan / max(1, h * w))
    skor += min(20.0, math.log1p(max(0.0, keskinlik)))
    return {"index": index, "kare_no": _kare_no(kaynak, index + 1),
            "kaynak": kaynak, "analiz_hatasi": False, "aday": aday,
            "guclu": guclu, "altyazi": altyazi, "tokenler": tokenler,
            "metinler": metinler, "bbox": bbox, "skor": round(skor, 3),
            "kutu_n": kutu_n, "harf_n": harf,
            "guven_ort": round(sum(guvenler) / len(guvenler), 4) if guvenler else None,
            "goruntu_ozeti": goruntu_ozeti}


def _ayni_kart(a: dict, b: dict) -> bool:
    ta, tb = a["tokenler"], b["tokenler"]
    if ta and tb:
        ortak = len(ta & tb)
        kapsama = ortak / min(len(ta), len(tb))
        # Sözcük sınırları OCR'da kararsızdır (ERLER FILM /
        # ERLERFILM). Karşılaştırmayı boşluksuz da yap; ancak eşiği
        # yüksek tut ki BIRINCI KART / IKINCI KART birleşmesin.
        oran = SequenceMatcher(None, _kompakt(a["metinler"]),
                               _kompakt(b["metinler"])).ratio()
        na, nb = _ngramlar(a["metinler"]), _ngramlar(b["metinler"])
        ngram_kapsama = (len(na & nb) / min(len(na), len(nb))
                         if na and nb else 0.0)
        if (kapsama >= AYNI_TOKEN_KAPSAMA or oran >= AYNI_METIN_ORANI
                or ngram_kapsama > NGRAM_KAPSAMA):
            return True
        return False
    return _bbox_iou(a.get("bbox"), b.get("bbox")) >= 0.68


def _guclu_metin_kimligi(a: dict, b: dict) -> bool:
    """Aynı yazı bindirmesinin araya sahne kesmesi girse de kimlik kanıtı."""
    ca, cb = _kompakt(a["metinler"]), _kompakt(b["metinler"])
    if min(len(ca), len(cb)) < 4:
        return False
    oran = SequenceMatcher(None, ca, cb).ratio()
    na, nb = _ngramlar(a["metinler"]), _ngramlar(b["metinler"])
    kapsama = len(na & nb) / min(len(na), len(nb)) if na and nb else 0.0
    return oran >= 0.86 or kapsama > NGRAM_KAPSAMA


def _zayif_gecis_kimligi(a: dict, b: dict) -> bool:
    """Dissolve ucundaki eksik OCR'yi komşu kalıcı karta bağla."""
    ca, cb = _kompakt(a["metinler"]), _kompakt(b["metinler"])
    if min(len(ca), len(cb)) < 4:
        return False
    ortak_uzun = any(len(t) >= 4 for t in a["tokenler"] & b["tokenler"])
    oran = SequenceMatcher(None, ca, cb).ratio()
    na, nb = _ngramlar(a["metinler"]), _ngramlar(b["metinler"])
    kapsama = len(na & nb) / min(len(na), len(nb)) if na and nb else 0.0
    # Soldan beliren kartta her satırın yalnız başı okunabilir:
    # "Meh / UGU / Osm / YAS" -> tam dokuz satırlı oyuncu kartı.
    la = [_kompakt([m]) for m in a["metinler"] if len(_kompakt([m])) >= 3]
    lb = [_kompakt([m]) for m in b["metinler"] if len(_kompakt([m])) >= 3]
    eslesen_satir = 0
    kullanilan = set()
    for x in la:
        for j, y in enumerate(lb):
            if j not in kullanilan and (x.startswith(y) or y.startswith(x)):
                kullanilan.add(j)
                eslesen_satir += 1
                break
    satir_kapsama = (eslesen_satir / min(len(la), len(lb)) if la and lb else 0.0)
    return (ortak_uzun or oran >= 0.55 or kapsama >= 0.42
            or satir_kapsama >= 0.60)


def _gruplandir(kanitlar: list[dict]) -> list[list[dict]]:
    gruplar: list[list[dict]] = []
    for k in (x for x in kanitlar if x["aday"]):
        if not gruplar:
            gruplar.append([k])
            continue
        g = gruplar[-1]
        bosluk = k["index"] - g[-1]["index"]
        # İlk kare dissolve/yarım OCR olabilir. Grubun o ana kadarki en güçlü
        # karesini anchor almak, aynı tam kartın OCR varyantlarını ayırmaz.
        # Tek anchor kullanmak kayan yazıda transitive zinciri yine engeller.
        anchor = max(g, key=lambda x: x["skor"])
        metin_ayni = _ayni_kart(anchor, k)
        # Düşük kontrastlı yazılarda rec her karede bozulabilir. Yalnız
        # gerçekten ardışık iki karede, kutu geometrisi de aynıyken görüntü
        # sürekliliği ikinci kanıttır. Metin kartları arasındaki kesmeyi bu
        # kapıdan geçirmemek için fallback anchor'a değil son kareye bakar.
        onceki = g[-1]
        geometri_ayni = (
            bosluk == 1
            and _bbox_iou(onceki.get("bbox"), k.get("bbox")) >= 0.72
            and abs(int(onceki.get("kutu_n") or 0) - int(k.get("kutu_n") or 0)) <= 1
            and _goruntu_surekli(onceki, k)
        )
        if bosluk <= GRUP_KARE_BOSLUGU + 1 and (metin_ayni or geometri_ayni):
            g.append(k)
        else:
            gruplar.append([k])
    return gruplar


def _gruplari_duzelt(gruplar: list[list[dict]]) -> list[list[dict]]:
    """OCR kopmalarını birleştir; gerçek kart sırasına dokunma.

    İki ayrı durum var: dissolve ucunda tek/iki eksik kare ve düşük
    kontrastlı sabit yazının arka plandaki sahne kesmesi yüzünden parçalanması.
    İlki yalnız komşu kalıcı karta, ikincisi ise en fazla 16 saniyelik iki
    güçlü aynı-metne bakarak aradaki OCR gürültüsüyle birlikte bağlanır.
    """
    gruplar = [list(g) for g in gruplar]

    # Aynı güçlü yazı iki uçta yeniden okunmuşsa aradaki parçalar aynı
    # bindirmedir (GÜNEŞ: hareketli fon üstünde sabit kredi).
    i = 0
    while i < len(gruplar):
        en_uzak = None
        for j in range(i + 1, len(gruplar)):
            if gruplar[j][-1]["index"] - gruplar[i][0]["index"] > KART_KOPRU_MAKS_KARE:
                break
            # En yüksek puanlı OCR her zaman en doğru okuma değil; grubun
            # herhangi iki karesinde sağlam kimlik bulmak yeterli.
            if any(_guclu_metin_kimligi(a, b)
                   for a in gruplar[i] for b in gruplar[j]):
                en_uzak = j
        if en_uzak is not None:
            birlesik = [k for g in gruplar[i:en_uzak + 1] for k in g]
            gruplar[i:en_uzak + 1] = [birlesik]
        i += 1

    def _kararsiz(g: list[dict]) -> bool:
        okumalar = {_kompakt(k["metinler"]) for k in g if _kompakt(k["metinler"])}
        return len(g) >= 3 and len(okumalar) / len(g) >= 0.50

    # Aynı yerde duran ama rec'i her karede bozulan iki komşu parçayı
    # birleştir. Kararlı iki ayrı kart (BIRINCI/IKINCI gibi) bu kapıya girmez.
    i = 0
    while i + 1 < len(gruplar):
        a, b = gruplar[i], gruplar[i + 1]
        ka, kb = max(a, key=lambda k: k["skor"]), max(b, key=lambda k: k["skor"])
        bosluk = b[0]["index"] - a[-1]["index"]
        oran = SequenceMatcher(None, _kompakt(ka["metinler"]),
                               _kompakt(kb["metinler"])).ratio()
        geometri = (_bbox_iou(ka.get("bbox"), kb.get("bbox")) >= 0.58
                    and abs(int(ka.get("kutu_n") or 0)
                            - int(kb.get("kutu_n") or 0)) <= 1)
        if (bosluk <= 3 and geometri and oran >= 0.58
                and (_kararsiz(a) or _kararsiz(b))):
            gruplar[i:i + 2] = [a + b]
        else:
            i += 1

    # Bir-iki karelik eksik fade OCR'sini yanındaki sürekli karta al.
    degisti = True
    while degisti:
        degisti = False
        for i, g in enumerate(gruplar):
            if len(g) > 1:
                continue
            adaylar = []
            # Arada det kutusu var ama rec metni olmayan 1-2 gürültü grubu
            # bulunabilir; 16 karelik penceredeki kalıcı komşuları tara.
            for j in range(i - 1, -1, -1):
                if g[0]["index"] - gruplar[j][-1]["index"] > 16:
                    break
                adaylar.append(j)
            for j in range(i + 1, len(gruplar)):
                if gruplar[j][0]["index"] - g[-1]["index"] > 16:
                    break
                adaylar.append(j)
            merkez = max(g, key=lambda k: k["skor"])
            eslesen = []
            for j in adaylar:
                if len(gruplar[j]) < 2:
                    continue
                kenar = gruplar[j][-1] if j < i else gruplar[j][0]
                dogrudan = abs(merkez["index"] - kenar["index"]) == 1
                geometri = (_bbox_iou(merkez.get("bbox"), kenar.get("bbox")) >= 0.45
                            and abs(int(merkez.get("kutu_n") or 0)
                                    - int(kenar.get("kutu_n") or 0)) <= 1)
                uzaklik = abs(merkez["index"] - kenar["index"])
                kimlik = any(_zayif_gecis_kimligi(merkez, k) for k in gruplar[j])
                guclu_kimlik = any(_guclu_metin_kimligi(merkez, k)
                                    for k in gruplar[j])
                bitisik_grup = abs(j - i) == 1
                if ((bitisik_grup and uzaklik <= 3 and kimlik)
                        or (uzaklik <= 16 and guclu_kimlik)
                        or (dogrudan and geometri)):
                    eslesen.append(j)
            if not eslesen:
                continue
            hedef = max(eslesen, key=lambda j: len(gruplar[j]))
            if hedef < i:
                gruplar[hedef].extend(g)
                del gruplar[i]
            else:
                gruplar[hedef] = g + gruplar[hedef]
                del gruplar[i]
            degisti = True
            break
    return gruplar


def _tekrarlari_at(gruplar: list[list[dict]], toplam_kare: int) -> list[list[dict]]:
    """Aynı okuma kartının kısa aralıklı tekrarını sayfalama."""
    kalan: list[list[dict]] = []
    for g in gruplar:
        tekrar = False
        for onceki in reversed(kalan):
            if g[0]["index"] - onceki[-1]["index"] > 80:
                break
            for a in onceki:
                for b in g:
                    if len(a["metinler"]) != len(b["metinler"]):
                        continue
                    ca, cb = _kompakt(a["metinler"]), _kompakt(b["metinler"])
                    if min(len(ca), len(cb)) >= 4 and SequenceMatcher(None, ca, cb).ratio() >= 0.88:
                        tekrar = True
                        break
                if tekrar:
                    break
            if tekrar:
                break
        if not tekrar:
            kalan.append(g)

    # Jenerik bittikten sonra sahnedeki dizi tabelası tekrar okunabilir
    # (ÇİÇEK TAKSİ). Uzun yazısız kuyruktan hemen önceki kısa son
    # grup, daha önceki 1-2 satırlı başlıkla aynıysa kredi değil tekrardır.
    while (len(kalan) >= 2
           and toplam_kare - 1 - kalan[-1][-1]["index"] >= 6
           and len(kalan[-1]) <= 2):
        son = kalan[-1]
        bulundu = False
        for onceki in kalan[:-1]:
            for a in onceki:
                for b in son:
                    if len(a["metinler"]) > 2 or len(b["metinler"]) > 2:
                        continue
                    ca, cb = _kompakt(a["metinler"]), _kompakt(b["metinler"])
                    if (min(len(ca), len(cb)) >= 5
                            and SequenceMatcher(None, ca, cb).ratio() >= 0.68):
                        bulundu = True
                        break
                if bulundu:
                    break
            if bulundu:
                break
        if bulundu:
            kalan.pop()
        else:
            break
    return kalan


def _grup_gecerli(g: list[dict]) -> bool:
    if len(g) == 1:
        k = g[0]
        # 2 fps havuzda gerçek kısa bir kredi iki karede kanıtlanır. Tek
        # karelik kısa okuma ise g_0440 "NO", "VNAD", "KNUS" gibi sahne
        # dokusu/transition hatasıdır. Uzun ve yüksek güvenli tek kartı koru.
        return bool(k["guclu"] and k.get("harf_n", 0) >= 8
                    and float(k.get("guven_ort") or 0.0) >= 0.72)
    if any(k["guclu"] for k in g):
        return True
    # Kısa/okunamayan gerçek yazı ancak en az iki kare sürüyor ve kutu aynı
    # yerde kalıyorsa kabul edilir. g_0440 türü tek-kare sahte "NO" elenir.
    return (len(g) >= 2 and _bbox_iou(g[0].get("bbox"), g[-1].get("bbox")) >= 0.50)


def _gecis_tek_karelerini_at(gruplar: list[list[dict]]) -> list[list[dict]]:
    kalan = []
    for i, g in enumerate(gruplar):
        if 0 < i < len(gruplar) - 1 and len(g) == 1:
            t = g[0]["tokenler"]
            onceki = set().union(*(k["tokenler"] for k in gruplar[i - 1]))
            sonraki = set().union(*(k["tokenler"] for k in gruplar[i + 1]))
            if t and t & onceki and t & sonraki and not (onceki & sonraki):
                continue
        kalan.append(g)
    return kalan


def _temsilciler(g: list[dict]) -> list[dict]:
    # Grup "aynı kart" hükmüdür; birden fazla kare seçmek masterda
    # tekrarı geri getirir. En iyi OCR/kontrast puanı eşitse dissolve
    # uçlarından uzak, grubun merkezindeki kareyi tercih et.
    merkez = (g[0]["index"] + g[-1]["index"]) / 2.0
    en_iyi = max(g, key=lambda k: (k["skor"], -abs(k["index"] - merkez)))
    return [en_iyi]


def planla(ims: list[np.ndarray], kaynaklar: list[str],
           analizler: list[dict | None]) -> dict:
    kanitlar = [kare_kaniti(i, kaynak, im, analiz)
                for i, (kaynak, im, analiz) in enumerate(zip(kaynaklar, ims, analizler))]
    gruplar = _tekrarlari_at(_gecis_tek_karelerini_at([
        g for g in _gruplari_duzelt(_gruplandir(kanitlar)) if _grup_gecerli(g)
    ]), len(kanitlar))
    secilen = [k for g in gruplar for k in _temsilciler(g)]
    secilen = sorted({k["index"]: k for k in secilen}.values(), key=lambda k: k["index"])

    grup_kaniti = []
    secili_indexler = {k["index"] for k in secilen}
    for no, g in enumerate(gruplar, 1):
        grup_kaniti.append({
            "grup": no, "ilk_kare": g[0]["kare_no"], "son_kare": g[-1]["kare_no"],
            "aday_kare": len(g),
            "secili": [k["kare_no"] for k in g if k["index"] in secili_indexler],
            "ornek_metin": max(g, key=lambda k: k["skor"])["metinler"][:4],
        })
    return {
        "surum": PLAN_SURUMU,
        "girdi_kare": len(ims),
        "analiz_hatasi": sum(1 for k in kanitlar if k["analiz_hatasi"]),
        "paddle_aday_kare": sum(1 for k in kanitlar if k["aday"]),
        "altyazi_elenen": sum(1 for k in kanitlar if k["altyazi"]),
        "grup": len(gruplar),
        "secili_kare": len(secilen),
        "secili_indexler": [k["index"] for k in secilen],
        "secili_kare_nolari": [k["kare_no"] for k in secilen],
        # Jenerik sınırı temsilci karesi değil, ilk/son geçerli yazı
        # grubunun gerçek ucudur. Temsilci ayrı alanlarda denetlenebilir.
        "ilk_yazi_kare": gruplar[0][0]["kare_no"] if gruplar else None,
        "bitis_kare": gruplar[-1][-1]["kare_no"] if gruplar else None,
        "ilk_secili_kare": secilen[0]["kare_no"] if secilen else None,
        "son_secili_kare": secilen[-1]["kare_no"] if secilen else None,
        # Her geçerli karttan tam bir temsilci alındığının yapısal
        # kanıtı. OCR token yazımı kalite metriği değildir.
        "kart_kapsama": 1.0 if gruplar and len(secilen) == len(gruplar) else 0.0,
        "gruplar": grup_kaniti,
    }


def master_uret(slug: str, ims: list[np.ndarray], kaynaklar: list[str],
                analizler: list[dict | None], h_maks: int) -> tuple[np.ndarray | None, dict]:
    """Planla ve seçilen TAM kareleri zaman sırasıyla dikey olarak sırala."""
    plan = planla(ims, kaynaklar, analizler)
    if ims and plan["analiz_hatasi"] == len(ims):
        return None, {"slug": slug, "durum": "giris_analiz_ariza", "kare": 0,
                      "giris_plan": plan, "sebep": "Paddle hicbir kareyi analiz edemedi"}
    secili = plan["secili_indexler"]
    if not secili:
        return None, {"slug": slug, "durum": "kare_yok", "kare": 0,
                      "giris_plan": plan, "sebep": "Yazili kare bulunamadi"}

    parcalar = [ims[i] for i in secili]
    kanvas = np.vstack(parcalar) if len(parcalar) > 1 else parcalar[0].copy()
    if int(kanvas.shape[0]) > h_maks:
        return None, {"slug": slug, "durum": "boy_asimi", "boy": int(kanvas.shape[0]),
                      "kare": len(secili), "giris_plan": plan}

    layout_map = []
    master_y = 0
    for i in secili:
        h, w = ims[i].shape[:2]
        layout_map.append({"master_y0": master_y, "master_y1": master_y + h,
                           "source_path": kaynaklar[i], "source_y0": 0,
                           "source_y1": h, "width": w, "height": h})
        master_y += h

    return kanvas, {
        "slug": slug, "durum": "OK", "mode": "lebron_giris_text_only",
        "kare": len(secili), "size": [int(kanvas.shape[1]), int(kanvas.shape[0])],
        "segment": len(secili), "segment_kareler": [1] * len(secili),
        "layout_map_version": "mitas.master-layout/v1", "layout_map": layout_map,
        "segment_dusuren": [], "dissolve_kesme": 0,
        "sinif_sayimi": {"yazi": len(secili),
                          "elenen": max(0, len(ims) - len(secili))},
        "scroll_dy_medyan": 0.0, "ciftler": [],
        "olcum_yolu": "paddle_text_only", "maske_kapsama": None,
        "sobel_kurtarma": False, "girdi_modu": "ardisik_aralik",
        "bicak": {"aktif": False, "neden": "giris_text_only",
                  "baslangic_cifti": None, "bitis_cifti": None},
        "collapse_recovery": {"triggered": False, "original_frames": len(ims),
                              "original_segments": len(secili),
                              "original_height": int(kanvas.shape[0])},
        "text_only": True, "giris_plan": plan,
    }
