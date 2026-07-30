"""Kunye ismi normalizasyonu ve esleştirmesi.

Katman A sentez raporu (wf_aa9a936e-5bb, 2026-07-20) bu katmani ZORUNLU ilan etti:
referans kumesi TMDB/Wikipedia biçiminde, test ise JENERIK okuyor. Normalizasyon
olmadan onlarca yanlis-negatif cikar ("Keith Robinson" vs "Keith D. Robinson",
"Dlouhy" vs "Dlouhý", "LUNG TI" vs "Ti Lung").

TASARIM ILKESI — asimetrik risk:
  yanlis BIRLESTIRME (iki farkli kisiyi ayni saymak) sonucu IYIMSER gosterir;
  yanlis AYIRMA (ayni kisiyi farkli saymak) VLM'e haksiz ceza yazar.
Ikisi de kotu, ama ilki daha tehlikeli cunku hatayi GIZLER. Bu yuzden fuzzy
tolerans uzunluga bagli ve kisa isimlerde SIFIR.
"""
from __future__ import annotations

import re
import unicodedata

# ── Turkce buyuk/kucuk harf ──────────────────────────────────────────────
# str.lower() Turkce'de bozuk: "I"->"i" (dogrusu "ı"), "İ"->"i̇" (2 kod noktasi).
# Kunye metni tamamen BUYUK HARF geldigi icin her Turkce isimde tetiklenir.
_TR_MAP = str.maketrans({"İ": "i", "I": "ı"})


def tr_lower(s: str) -> str:
    """Turkce-farkinda kucuk harf. Diakritigi KORUR."""
    return s.translate(_TR_MAP).lower()


# ── normalizasyon ────────────────────────────────────────────────────────
_NOKTALAMA = re.compile(r"[.,;:!?\"'`´’‘“”()\[\]{}<>/\\|*_—–-]+")
_BOSLUK = re.compile(r"\s+")
# Referans verisinde parantezli aciklama var: "René Clair (senaryo ve diyalog)",
# "Daniel Lee (李仁港)". Karsilastirmada bunlar gurultu — atilir.
_PARANTEZ = re.compile(r"[(\[][^)\]]*[)\]]")

# isim olamayacak metinler (VL kacis degerleri + TRT tur etiketleri)
_ISIM_DEGIL = {
    "yerli sinema", "yabanci sinema", "okunamadi", "yazi yok",
    "bilinmiyor", "yok", "na", "n a",
}


def diakritik_kaldir(s: str) -> str:
    """é->e, ö->o, ş->s, ý->y ... Latin-genisletilmis ve Kiril-translit icin."""
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def normalize(s: str) -> str:
    """Karsilastirma icin kanonik biçim: tr-lower + diakritiksiz + sade."""
    s = _PARANTEZ.sub(" ", s or "")
    s = tr_lower(s)
    s = diakritik_kaldir(s)
    # "ı" (U+0131) NFD ile AYRISMAZ — combining mark degil, ayri bir base harf.
    # Elle esle, yoksa "okunamadı" != "okunamadi" olur ve kacis degerleri elenmez.
    s = s.replace("ı", "i").replace("ł", "l").replace("ø", "o").replace("đ", "d")
    s = _NOKTALAMA.sub(" ", s)
    return _BOSLUK.sub(" ", s).strip()


def isim_gibi_mi(s: str) -> bool:
    """Kisi adi olma ihtimali. Tur etiketleri, kacis degerleri, sayilar elenir."""
    n = normalize(s)
    if len(n) < 2 or n in _ISIM_DEGIL:
        return False
    if not re.search(r"[a-zçğıöşü]", n):   # en az bir harf
        return False
    if re.fullmatch(r"[\d\s]+", n):        # saf sayi
        return False
    return True


def _tokenlar(s: str) -> list[str]:
    return [t for t in normalize(s).split(" ") if t]


# ── token duzeyi karsilastirma ───────────────────────────────────────────
def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a or not b:
        return len(a) or len(b)
    onceki = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        simdiki = [i]
        for j, cb in enumerate(b, 1):
            simdiki.append(min(onceki[j] + 1, simdiki[j - 1] + 1,
                               onceki[j - 1] + (ca != cb)))
        onceki = simdiki
    return onceki[-1]


def _sub_tolerans(n: int) -> int:
    """Uzunluga bagli duzeltme butcesi.

    Kisa isimlerde SIFIR: "Lung"/"Long" ve "Lau"/"Lee" ayrilabilsin diye.
    Uzun isimlerde daha comert: "Tolypov"/"Tolepov" birlessin diye.
    """
    if n <= 4:
        return 0
    if n <= 7:
        return 1
    return 2


def _token_esit(a: str, b: str) -> bool:
    """Tek token ayni kisiye ait olabilir mi."""
    if a == b:
        return True
    # inisyal: "h" <-> "hans". Karsi token 5 harften uzunsa REDDET — yoksa
    # "Robert B. Lee" ile "Robert Buckner" birlesir ("b"<->"buckner") ve
    # "Maggie Q" ile "Maggie Cheung" birlesir. Inisyal bir ADIN kisaltmasidir,
    # adlar kisadir; uzun bir soyadi tek harfle temsil etmek fazla riskli.
    if len(a) == 1 or len(b) == 1:
        uzun_taraf = b if len(a) == 1 else a
        return a[0] == b[0] and len(uzun_taraf) <= 5
    # anagram / harf yer degistirmesi: MONREO <-> MONROE, BRASSUER <-> BRASSEUR
    if len(a) == len(b) and sorted(a) == sorted(b):
        return True
    # prefix: FLYN <-> FLYNN (ekleme affedilir, ortadaki degisim degil)
    kisa, uzun = (a, b) if len(a) <= len(b) else (b, a)
    if len(kisa) >= 4 and uzun.startswith(kisa) and len(uzun) - len(kisa) <= 2:
        return True
    # uzunluk-duyarli fuzzy
    if abs(len(a) - len(b)) > 2:
        return False
    return _levenshtein(a, b) <= _sub_tolerans(min(len(a), len(b)))


def _birlesimler(tok: list[str]) -> list[tuple[str, ...]]:
    """Bitisik token birlesmeleri: ["mc","cowen"] -> ("mccowen",)."""
    out = [tuple(tok)]
    for i in range(len(tok) - 1):
        out.append(tuple(tok[:i] + [tok[i] + tok[i + 1]] + tok[i + 2:]))
    return out


def ayni_kisi(a: str, b: str) -> bool:
    """Iki isim ayni kisiyi mi gosteriyor.

    Sira bagimsiz (LUNG TI <-> Ti Lung), orta ad/inisyal toleransli
    (Keith Robinson <-> Keith D. Robinson), alt-kume toleransli
    (Vangelis <-> Vangelis Papathanassiou).
    """
    if not (isim_gibi_mi(a) and isim_gibi_mi(b)):
        return False
    ta, tb = _tokenlar(a), _tokenlar(b)
    if not ta or not tb:
        return False
    if ta == tb:
        return True
    if _kume_esles(ta, tb):
        return True

    # Birlesim SADECE token sayilari farkliysa denenir ("Le Febvre" vs "Lefebvre").
    # Sayilar zaten esitken birlestirmek felakettir: "kadir savun"/"kadir savas"
    # -> "kadirsavun"/"kadirsavas" olur, string uzadigi icin fuzzy toleransi
    # buyur ve IKI FARKLI KISI birlesir. Birlesim ancak token sayilarini
    # ESITLIYORSA anlamlidir.
    if len(ta) != len(tb):
        for ca in _birlesimler(ta):
            for cb in _birlesimler(tb):
                if len(ca) == len(cb) and _kume_esles(list(ca), list(cb)):
                    return True
    return False


def _kume_esles(ta: list[str], tb: list[str]) -> bool:
    kisa, uzun = (ta, tb) if len(ta) <= len(tb) else (tb, ta)

    # kisa tarafin HER tokeni uzun tarafta bir karsilik bulmali (sira bagimsiz)
    kalan = list(uzun)
    anlamli_eslesme = 0
    for t in kisa:
        for i, u in enumerate(kalan):
            if _token_esit(t, u):
                if len(t) >= 4 and len(u) >= 4:
                    anlamli_eslesme += 1
                kalan.pop(i)
                break
        else:
            return False

    # Kalan token'lar (orta ad, inisyal, ikinci soyad) affedilir — AMA en az bir
    # ANLAMLI (>=4 harf) eslesme sart. Yoksa "Sean" ile "Sean Bean" birleşir.
    if anlamli_eslesme == 0:
        return False

    # Tek tokenlik isim uzun bir isme gomuluyorsa (Vangelis <-> Vangelis P.)
    # sadece o token >= 5 harfse kabul et — kisa ad cakismasini onler.
    if len(kisa) == 1 and len(uzun) > 1:
        return len(kisa[0]) >= 5

    return True


def metinde_gecer_mi(isim: str, satir: str) -> bool:
    """Bir referans ismi, jenerik SATIRININ ICINDE geciyor mu.

    Jenerik satirlari gorev etiketi + ismi BIRLIKTE tasir:
      "1. Yönetmen Yardımcısı / 1st AD MEHMET GEZMEN"
      "A Kamera Focus Puller / A Camera Focus Puller SELAMI ŞİMŞEK"
    Tam-satir karsilastirmasi (ayni_kisi) bunlari kaciririr. Recall olcerken
    ismin satir icinde ARDISIK token dizisi olarak gecip gecmedigine bakilir.
    """
    ti, ts = _tokenlar(isim), _tokenlar(satir)
    if not ti or len(ts) < len(ti):
        return False
    # tek-token isimler icin cok riskli (rastgele kelimeye carpar)
    anlamli = [t for t in ti if len(t) >= 3]
    if len(anlamli) < 2:
        return False
    for i in range(len(ts) - len(ti) + 1):
        if all(_token_esit(a, b) for a, b in zip(ti, ts[i:i + len(ti)])):
            return True
    return False


# ── liste duzeyi esleştirme ──────────────────────────────────────────────
def listeyi_esle(okunan: list[str], referans: list[str]) -> dict:
    """VL ciktisini referans kumesiyle esleştir.

    KRITIK: 'referansta_yok' UYDURMA DEGILDIR. Katman A referansi eksik kadrolu
    (sentez raporu: 12+ filmde jenerikte yazan ama referansta olmayan isim var).
    Bu kova NOTR'dur; uydurma hukmu ancak hedefli gorsel hakemlikle verilebilir.

    Her referans ismi EN FAZLA BIR kez eslesir — yoksa tekrarli okuma
    precision'i yapay olarak sisirir.
    """
    elenen = [x for x in okunan if not isim_gibi_mi(x)]
    adaylar = [x for x in okunan if isim_gibi_mi(x)]
    ref_kalan = list(referans)

    eslesen, yok = [], []
    for o in adaylar:
        for i, r in enumerate(ref_kalan):
            if ayni_kisi(o, r):
                eslesen.append({"okunan": o, "referans": r,
                                "birebir": normalize(o) == normalize(r)})
                ref_kalan.pop(i)
                break
        else:
            yok.append(o)

    return {
        "eslesen": eslesen,
        "referansta_yok": yok,      # NOTR kova
        "kacirilan": ref_kalan,
        "elenen": elenen,
        "precision_paydasi": len(eslesen) + len(yok),
        "recall_paydasi": len(referans),
    }
