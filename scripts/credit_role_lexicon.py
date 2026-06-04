#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
credit_role_lexicon.py — Çok-dilli, DETERMİNİSTİK rol çapalama (yönetmen/yapımcı/cast).

NEDEN: Bir VLM'e "yönetmen kim?" diye sormak HALÜSİNE edebilir (güven riski). Bunun yerine
VLM jeneriği TRANSKRİPT etsin (güçlü olduğu iş), sonra bu sözlük metinde "yönetmen" kelimesinin
TÜM DİLLERDEKİ karşılığını arayıp yanındaki ismi DETERMİNİSTİK alsın. Kelime yoksa -> "okunamadı"
(uydurma YOK). _kunye_classify.py'deki TR+EN HEAD_DIR mantığının çok-dilli + alt-rol-dışlamalı hâli.

KAPSAM: Latin-yazılı diller (TR/EN/FR/DE/IT/ES/PT + yaygın). norm() aksan soyar; Kiril/CJK
(Режиссёр/監督) A-Z'ye inince kaybolur -> o filmler VLM-etiketi/KB'ye düşer (arşivde nadir).

KRİTİK: Alt-roller DIŞLANIR — "yönetmen yardımcısı / seslendirme yönetmeni / görüntü yönetmeni /
assistant director / director of photography / aiuto regista ..." film yönetmeni DEĞİLDİR.
"""
import re
import sys
import unicodedata

def norm(s):
    s = (s or "").replace("ı", "i").replace("İ", "i")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).upper()
    s = re.sub(r"[^A-Z ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

# --- POZİTİF başlıklar (normalize edilmiş; uzun kalıplar önce eşleşsin diye uzunluk sıralı kullanılır) ---
DIRECTOR = [
    # TR
    "YONETMEN", "YONETEN", "REJISOR", "YONETMENI",
    # EN
    "DIRECTED BY", "A FILM BY", "FILM BY", "DIRECTOR", "DIRECTION",
    # FR
    "REALISE PAR", "REALISATION", "REALISATEUR", "UN FILM DE", "MISE EN SCENE",
    # DE
    "EIN FILM VON", "REGIE", "INSZENIERUNG",
    # IT
    "DIRETTO DA", "UN FILM DI", "REGIA", "REGISTA",
    # ES
    "DIRIGIDA POR", "DIRIGIDO POR", "DIRECCION", "UNA PELICULA DE", "DIRECTOR",
    # PT
    "REALIZADO POR", "DIRIGIDO POR", "REALIZACAO", "DIRECAO",
]
PRODUCER = [
    "YURUTUCU YAPIMCI", "YAPIMCI", "YAPIM",
    "EXECUTIVE PRODUCER", "PRODUCED BY", "PRODUCER", "PRODUCTION",
    "PRODUIT PAR", "PRODUCTEUR", "PRODUCTRICE", "PRODUCTION",
    "HERGESTELLT VON", "PRODUZENT", "PRODUKTION",
    "PRODOTTO DA", "PRODUTTORE", "PRODUZIONE",
    "PRODUCIDA POR", "PRODUCIDO POR", "PRODUCTOR", "PRODUCCION",
    "PRODUZIDO POR", "PRODUTOR", "PRODUCAO",
]
CAST = [
    "ROL DAGILIMI", "OYNAYANLAR", "OYUNCULAR", "OYUNCU",
    "STARRING", "FEATURING", "CAST", "WITH",
    "INTERPRETES", "DISTRIBUTION", "AVEC",
    "DARSTELLER", "BESETZUNG", "MIT",
    "INTERPRETI", "CON", "CAST",
    "REPARTO", "ELENCO", "COM",
]
# --- NEGATİF: bu sözcüklerden biri başlıkta varsa o satır FİLM yönetmeni/asıl yapımcı DEĞİL ---
EXCLUDE = [
    # TR alt-roller
    "YARDIMCI", "SESLENDIRME", "MUZIK", "GORUNTU", "SANAT", "DUBLAJ", "CASTING",
    # EN alt-roller
    "ASSISTANT", "ASSOCIATE", "SECOND UNIT", "ART DIRECTOR", "CASTING DIRECTOR",
    "MUSIC DIRECTOR", "DIRECTOR OF PHOTOGRAPHY", "TECHNICAL DIRECTOR", "CO DIRECTOR",
    "PHOTOGRAPHY", "PRODUCTION ASSISTANT", "PRODUCTION MANAGER", "PRODUCTION COORDINATOR",
    "LINE PRODUCER",
    # FR/DE/IT/ES alt-roller
    "ASSISTANT REALISATEUR", "DIRECTEUR DE LA PHOTOGRAPHIE", "DIRECTEUR ARTISTIQUE",
    "REGIEASSISTENZ", "AIUTO REGISTA", "DIRETTORE DELLA FOTOGRAFIA",
    "AYUDANTE DE DIRECCION", "DIRECTOR DE FOTOGRAFIA", "DIRECTOR ARTISTICO",
]
CORP = {"FILM", "FILMS", "PRODUCTION", "PRODUCTIONS", "PICTURES", "STUDIO", "STUDIOS",
        "ENTERTAINMENT", "MEDIA", "INC", "LLC", "LTD", "COMPANY", "TV", "INTERNATIONAL",
        "GROUP", "CORP", "CORPORATION", "ASSOCIATES", "PRESENTS", "PRESENTE"}
# departman/rol-LİDER sözcükleri: bir satır bunlardan biriyle BAŞLIYORSA isim değildir
# (komşu satır taramasını yeni bir rol satırında durdurur)
ROLE_WORDS = {
    "KAMERA", "CAMERA", "GORUNTU", "PHOTOGRAPHY", "IMAGE", "FOTOGRAFIA",
    "MUZIK", "MUSIC", "MUSIQUE", "MUSICA", "MUSIK",
    "KURGU", "MONTAJ", "EDITOR", "EDITING", "MONTAGE", "MONTAGGIO",
    "SES", "SOUND", "SON", "TON", "SUONO", "SONIDO",
    "SENARYO", "SCREENPLAY", "WRITER", "WRITTEN", "SCENARIO", "DREHBUCH", "SCENEGGIATURA", "GUION",
    "SANAT", "ART", "DEKOR", "DESIGN", "DESIGNER", "DECORS", "AUSSTATTUNG",
    "KOSTUM", "COSTUME", "COSTUMES", "KOSTUME", "MAKYAJ", "MAKEUP", "MAKE",
    "YAPIM", "YAPIMCI", "PRODUCER", "PRODUCED", "PRODUCTION", "PRODUKTION", "PRODUZIONE",
    "PRODUCTEUR", "PRODUTTORE", "PRODUCTOR", "PRODUTOR", "EXECUTIVE",
    "YONETMEN", "YONETEN", "REJISOR", "DIRECTOR", "DIRECTED", "REGIE", "REGIA", "REGISTA",
    "REALISATION", "REALISATEUR", "REALISE", "DIRECTION", "DIRECCION",
    "OYUNCULAR", "OYUNCU", "CAST", "STARRING", "AVEC", "MIT", "CON", "REPARTO", "ELENCO",
    "SESLENDIRME", "DUBLAJ", "YARDIMCI", "ASSISTANT", "ASSOCIATE", "CASTING", "SUPERVISOR",
}
ALL_HEADS = DIRECTOR + PRODUCER + CAST

def _has_excl(nline):
    return any(x in nline for x in EXCLUDE)

def _is_name(nline):
    toks = nline.split()
    if not (1 <= len(toks) <= 5):
        return False
    if toks[0] in ROLE_WORDS:            # rol/departman lideriyle baslayan satir isim degil
        return False
    if any(h == nline or nline.startswith(h + " ") for h in ALL_HEADS):
        return False
    if any(t in CORP for t in toks):
        return False
    return True

def _strip_head(nline, head):
    """Satırdan başlığı ve ayraçları çıkar, kalan ismi döndür ('DIRECTED BY JOHN FORD' -> 'JOHN FORD')."""
    rest = nline
    if rest == head:
        return ""
    if rest.startswith(head + " "):
        rest = rest[len(head):].strip()
    elif rest.endswith(" " + head):
        rest = rest[:-len(head)].strip()
    return rest

def _match_head(nline, heads):
    """Satır bu rol başlıklarından biriyle başlıyor/bitiyor/eşit mi? (en uzun kalıp önce)"""
    for head in sorted(heads, key=len, reverse=True):
        if nline == head or nline.startswith(head + " ") or nline.endswith(" " + head):
            return head
    return None

def anchor_roles(text, max_cast=8):
    """
    Transkript metninden DETERMİNİSTİK yönetmen/yapımcı/cast çıkar.
    Mantık: her satırı normalize et; bir rol başlığı (alt-rol DEĞİL) içeren satırda
    ismi aynı satırdan, yoksa komşu satırdan al. Bulamazsa boş (dürüst çekimserlik).
    """
    raw = [l.strip() for l in (text or "").splitlines() if l.strip()]
    nlines = [norm(l) for l in raw]
    out = {"director": [], "producer": [], "cast": []}

    def take_adjacent(i, head):
        # 1) AYNI satırda başlıktan sonra/önce isim — başlığı token-sayısıyla soy, ORİJİNAL casing'i koru
        hw = len(head.split()); ot = raw[i].split(); nl = nlines[i]; cand = ""
        if nl != head:
            if nl.startswith(head + " "):
                cand = " ".join(ot[hw:])
            elif nl.endswith(" " + head):
                cand = " ".join(ot[:-hw])
        cand = cand.strip(" :,-–—\t")
        if cand and _is_name(norm(cand)) and not _has_excl(norm(cand)):
            return [cand]
        # 2) SONRAKİ satır(lar) — yeni rol satırında dur
        names = []
        for j in (i + 1, i + 2):
            if j < len(raw) and _is_name(nlines[j]) and not _has_excl(nlines[j]):
                names.append(raw[j])
            else:
                break
        if names:
            return names
        # 3) ÖNCEKİ satır (NAME \n Regista düzeni)
        if i - 1 >= 0 and _is_name(nlines[i - 1]) and not _has_excl(nlines[i - 1]):
            return [raw[i - 1]]
        return []

    for i, nl in enumerate(nlines):
        if _has_excl(nl):
            continue
        for role, heads in (("director", DIRECTOR), ("producer", PRODUCER), ("cast", CAST)):
            h = _match_head(nl, heads)
            if h:
                for nm in take_adjacent(i, h):
                    if nm not in out[role]:
                        out[role].append(nm)
                break
    out["cast"] = out["cast"][:max_cast]
    return out

def _selftest():
    sys.stdout.reconfigure(encoding="utf-8")
    cases = {
        "TR": "OYUNCULAR\nKEMAL SUNAL\nŞENER ŞEN\nYÖNETMEN\nERTEM EĞİLMEZ\nYÖNETMEN YARDIMCISI\nALİ VELİ",
        "EN": "Directed by John Ford\nProduced by Merian C. Cooper\nDirector of Photography Gregg Toland\nStarring\nJohn Wayne\nMaureen O'Hara",
        "FR": "Un film de Jean Renoir\nAvec\nJean Gabin\nMichel Simon\nAssistant réalisateur Jacques Becker",
        "DE": "Regie\nFritz Lang\nKamera Karl Freund\nMit\nPeter Lorre",
        "IT": "Regia\nFederico Fellini\nProdotto da Dino De Laurentiis\nDirettore della fotografia Otello Martelli",
    }
    for lang, txt in cases.items():
        r = anchor_roles(txt)
        print(f"[{lang}] yön={r['director']} | yap={r['producer']} | cast={r['cast']}")

if __name__ == "__main__":
    _selftest()
