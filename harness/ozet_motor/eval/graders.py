# -*- coding: utf-8 -*-
"""ozet_motor not vericileri — hata kovasi basina BIR grader, once deterministik.

Kovalar 2026-06-27 bake-off'unda isimlendirildi; buradaki karsiliklari:
  B1 BICIM   — uretimin kendi kapisi (_ozet_kalite): kelime/cumle/noktali-virgul/spoiler-final.
  B2 DIL     — garble/yabanci sozcuk/tekrar/think-sizintisi (bake-off kova D "klise doldurma"nin
               olculebilir yuzu + elenen modellerin Ingilizce+Cince kusma hatasi).
  B3 OLGU    — Sonnet referansiyla ozel-ad ve icerik ortusmesi (kova A "kilit donum atlama" ve
               kova B "kim-kime tersine"nin deterministik VEKILI — hakem degil, tarama).

B3 bir VEKIL: dusuk skor "bak buraya" der, yuksek skor dogruluk KANITLAMAZ. Sadakat gercek
hakemi LLM-juri isi ve juri BASKA model ailesinden olmali (skill kurali) — bu tur deterministik.
"""
from __future__ import annotations

import re
import sys
import unicodedata

sys.path.insert(0, "/opt/mitas/scripts")
import _ozet_kalite as qa  # noqa: E402  — uretimin GERCEK kapisi; ayri kopya tutmuyoruz

# Turkce'de sik gecen ve ozel-ad sanilabilecek cumle-basi sozcukler (ad sayimindan duser).
_AD_DISI = {
    "Bu", "Şu", "O", "Bir", "Ancak", "Fakat", "Ama", "Sonra", "Sonunda", "Finalde",
    "Filmin", "Film", "Daha", "Her", "Kendi", "Onun", "Bunun", "İki", "Üç", "Böylece",
    "Yıllar", "Genç", "Küçük", "Büyük", "Yeni", "Eski", "Son", "İlk",
}
_AD_RE = re.compile(r"\b([A-ZÇĞİÖŞÜ][a-zçğıöşü]{2,})\b")
_KELIME_RE = re.compile(r"\w+", re.UNICODE)
# Ingilizce sizinti: ozet Turkce olmali, ozel ad disinda yabanci sozcuk yasak (prompt kurali).
_INGILIZCE = re.compile(
    r"\b(the|and|with|from|this|that|which|when|while|after|before|because|"
    r"story|film|movie|character|summary|however|during|through)\b", re.IGNORECASE)
_THINK = re.compile(r"<think>|</think>|<\|.*?\|>|^\s*(Düşün|Analiz|Taslak)\s*:", re.IGNORECASE | re.MULTILINE)


def _sadelestir(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").lower()
    return "".join(c for c in s if not unicodedata.combining(c))


def adlar(metin: str) -> set[str]:
    """Ozet icindeki ozel ad adaylari (cumle-basi genel sozcukler ayiklanmis)."""
    return {a for a in _AD_RE.findall(metin or "") if a not in _AD_DISI}


def b1_bicim(ozet: str) -> dict:
    """Uretim kapisi: _ozet_kalite.summary_errors + spoiler-final. Ikili gecti/kaldi."""
    hatalar = qa.summary_errors(ozet)
    final_var = qa.has_spoiler_final(ozet)
    return {
        "gecti": (not hatalar) and final_var,
        "hatalar": hatalar,
        "spoiler_final": final_var,
        "kelime": qa.summary_word_count(ozet),
        "cumle": len(qa.split_sentences(ozet)),
    }


def b2_dil(ozet: str) -> dict:
    """Dil sagligi: Latin-disi, Ingilizce sizinti, think sizintisi, n-gram tekrari."""
    t = ozet or ""
    latin_disi = [c for c in t if c.isalpha() and "LATIN" not in unicodedata.name(c, "")]
    ingilizce = sorted({m.group(0).lower() for m in _INGILIZCE.finditer(t)})
    think = bool(_THINK.search(t))
    kel = _KELIME_RE.findall(_sadelestir(t))
    tekrar = []
    if len(kel) >= 10:
        gram = [" ".join(kel[i:i + 4]) for i in range(len(kel) - 3)]
        gorulen: dict[str, int] = {}
        for g in gram:
            gorulen[g] = gorulen.get(g, 0) + 1
        tekrar = sorted(g for g, n in gorulen.items() if n > 1)
    return {
        "gecti": not latin_disi and not ingilizce and not think and not tekrar,
        "latin_disi": "".join(sorted(set(latin_disi))),
        "ingilizce": ingilizce,
        "think_sizintisi": think,
        "tekrar_4gram": tekrar[:5],
    }


def b3_olgu(ozet: str, referans: str, transcript: str = "") -> dict:
    """Sonnet referansina karsi ozel-ad ve icerik ortusmesi (VEKIL — kanit degil, tarama).

    DUZELTME 2026-07-30: Sonnet referanslari kunyede TAMAMI BUYUK HARF yazili ("WALDO TORNICRAFT"),
    bu yuzden Title-Case regex'i referansta HIC ad bulamiyor → ad_isabet hep None donuyordu (kor
    grader). Cozum: kanonik ad kumesi TRANSKRIPTTEN cikarilir (buyuk/kucuk harf sorunu yok), sonra
    hem adayda hem referansta ASCII-katlanmis olarak ARANIR."""
    if transcript:
        import sys as _s
        _s.path.insert(0, "/opt/mitas/harness/ozet_motor")
        from motorlar import _adlari_topla   # ayni kanonik cikarici — tek dogruluk kaynagi
        kanonik = _adlari_topla(transcript, sayi=20)
        oz_k, ref_k = _sadelestir(ozet), _sadelestir(referans)
        a_oz = {a for a in kanonik if _sadelestir(a) in oz_k}
        a_ref = {a for a in kanonik if _sadelestir(a) in ref_k}
    else:
        a_oz, a_ref = adlar(ozet), adlar(referans)
    ad_isabet = len(a_oz & a_ref) / len(a_ref) if a_ref else None

    def govde(s: str) -> set[str]:
        return {k for k in _KELIME_RE.findall(_sadelestir(s)) if len(k) > 4}

    g_oz, g_ref = govde(ozet), govde(referans)
    ortak = len(g_oz & g_ref) / len(g_oz | g_ref) if (g_oz | g_ref) else 0.0
    return {
        "ad_isabet": None if ad_isabet is None else round(ad_isabet, 3),
        "ozette_olmayan_ad": sorted(a_ref - a_oz),
        "uydurma_ad_adayi": sorted(a_oz - a_ref),
        "icerik_jaccard": round(ortak, 3),
    }


def b4_topraklama(ozet: str, transcript: str) -> dict:
    """SADAKAT kapisi — ozetteki iddialar transkriptte KARSILIGI VAR MI (2026-07-30 eklendi).

    Neden: B1 bicime, B3 referansa bakiyor; ikisi de "akici Turkce ile yazilmis YANLIS ozet"i
    goremiyor. Olculen gercek vakalar: KANDAHAR "Sonunda Ami ile kavusur" (Ami = ASR gurultusu),
    AYI YOGI "Korucu Simit Celis Don'un baskorucusu oldu", HAYAT BIR SARKIDIR finali tamamen yanlis.
    Bunlarin ortak yani: cumle akici, bicim kapisindan geciyor, ama kaynakta karsiligi yok/yanlis yerde.

    Iki deterministik olcum:
      • uydurma_ad  : ozetteki ozel adlardan transkriptte HIC gecmeyenler (saf uydurma).
      • final_toprak: SON cumlenin icerik sozcuklerinden transkriptin SON %25'inde gecenlerin orani.
                      Film finali transkriptin sonunda gecer; orada karsiligi yoksa final uydurma
                      ya da yanlis yerden alinmis demektir.
    Vekil degil KAPI: dusuk final_toprak somut bir kusurdur, "bak buraya" degil.
    """
    tk = _sadelestir(transcript)
    kuyruk = tk[int(len(tk) * 0.75):]

    # Cumle-basi buyuk harfliler ad DEGILDIR ("Filmde/Sonucta/Zorlu") — yalniz cumle ORTASINDAKI
    # buyuk harfli sozcukleri ad say (motorlar._adlari_topla ile ayni kural).
    ozet_adlari = set()
    for c in re.split(r"(?<=[.!?])\s+", (ozet or "").strip()):
        for s in c.split()[1:]:
            t = s.strip(".,!?:;\"'()…-")
            if len(t) > 2 and _AD_RE.fullmatch(t) and t not in _AD_DISI:
                ozet_adlari.add(t)
    uydurma = sorted(a for a in ozet_adlari if _sadelestir(a) not in tk)

    cumleler = [c for c in re.split(r"(?<=[.!?])\s+", (ozet or "").strip()) if c.strip()]
    son = cumleler[-1] if cumleler else ""
    icerik = [k for k in _KELIME_RE.findall(_sadelestir(son)) if len(k) > 4]
    # Turkce sondan eklemeli: tam sozcuk yerine ilk 5 harflik kok araniyor (kavus-ur/kavus-tu).
    tutan = [k for k in icerik if k[:5] in kuyruk]
    oran = len(tutan) / len(icerik) if icerik else None

    return {
        "gecti": (not uydurma) and (oran is None or oran >= 0.5),
        "uydurma_ad": uydurma,
        "final_toprak": None if oran is None else round(oran, 2),
        "final_cumle": son[:120],
        "kuyrukta_yok": [k for k in icerik if k[:5] not in kuyruk][:6],
    }


def notla(ozet: str, referans: str, transcript: str = "") -> dict:
    b1 = b1_bicim(ozet)
    b2 = b2_dil(ozet)
    b3 = b3_olgu(ozet, referans, transcript)
    b4 = b4_topraklama(ozet, transcript) if transcript else None
    return {"b1_bicim": b1, "b2_dil": b2, "b3_olgu": b3, "b4_topraklama": b4,
            "deterministik_gecti": b1["gecti"] and b2["gecti"] and (b4 is None or b4["gecti"])}
