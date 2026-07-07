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
    # Bileşik etiketler (AJAMİ doğruluk-denetimi 2026-07-03: "Written, Directed and Edited by
    # Scandar Copti, Yaron Shani" kartından eş-yönetmen düşmüştü)
    "WRITTEN AND DIRECTED", "DIRECTED AND EDITED", "PRODUCED AND DIRECTED", "WRITTEN, DIRECTED",
    # FR
    "REALISE PAR", "REALISATION", "REALISATEUR", "UN FILM DE", "MISE EN SCENE",
    "DIRIGE PAR",   # 117-film taraması 2026-07-03: ŞEYTAN RUHLU İNSANLAR (LES DIABOLIQUES) kanıtı
    # DE
    "EIN FILM VON", "REGIE", "INSZENIERUNG",
    # SV/DA/NO (İskandinav) — İNTİKAM (BECK) kanıtı 2026-07-03
    "REGISSOR", "INSTRUKTOR",
    # IT
    "DIRETTO DA", "UN FILM DI", "REGIA", "REGISTA",
    # ES
    "DIRIGIDA POR", "DIRIGIDO POR", "DIRECCION", "UNA PELICULA DE", "DIRECTOR",
    # PT
    "REALIZADO POR", "DIRIGIDO POR", "REALIZACAO", "DIRECAO",
    # ── ÇOK-DİLLİ GENİŞLEME (2026-07-06, Çağatay: "diller/sıfatlar/ihtimaller — DOLDUR") ──
    # Bileşik/varyant EN (BUZDAN/CENNETE kanıtları)
    "DIRECTED & PHOTOGRAPHED", "PRODUCED, WRITTEN & DIRECTED", "STORY AND DIRECTION",
    "SCREENPLAY AND DIRECTION", "STORY, SCREENPLAY AND DIRECTION", "FILM DIRECTED BY",
    # NL / PL / CZ-SK / HU / RO / EL(translit)
    "GEREGISSEERD DOOR", "REZYSERIA", "REZIE", "RENDEZTE", "RENDEZO", "REGIA", "SKINOTHESIA",
    # RU/UA/BG (Latin-translit — Kiril OCR'ı bazen translit döker)
    "REZHISSER", "REZHISSYOR", "REJISSER", "POSTANOVKA", "REZHYSER", "REZHISOR",
    # SR/HR/SL
    "REZIJA", "REDATELJ",
    # HI/UR (Hint kartları translit) + FA + AR (translit)
    "NIRDESHAK", "NIRDESHAN", "KARGARDAN", "IKHRAJ", "MUKHRIJ",
    # JA/ZH latin-kartlar (uluslararası kopyalarda İngilizce gelir; yine de pinyin/romaji nadir)
    "KANTOKU", "DAOYAN",
    # Bileşik başlıklar (2026-07-07 lexicon_anchor_misparse): FR/EN "üret VE yönet" birleşik
    # etiketi TEK SATIRDA gelince _match_head (en-uzun-önce) TAMAMINI yer → strip="" → isim
    # SONRAKİ satırdan alınır. (Kanıt: ŞEYTAN RUHLU 1955-0046 "PRODUIT ET DIRIGE PAR / H.G. CLOUZOT".)
    "PRODUIT ET DIRIGE PAR", "PRODUIT ET REALISE PAR", "ECRIT ET REALISE PAR",
    "ECRIT ET DIRIGE PAR", "PRODUCED AND DIRECTED BY", "WRITTEN AND DIRECTED BY",
    "DIRECTED AND PRODUCED BY", "PRODUCED WRITTEN AND DIRECTED BY",
]
PRODUCER = [
    "YURUTUCU YAPIMCI", "YAPIMCI", "YAPIM",
    "EXECUTIVE PRODUCER", "PRODUCED BY", "PRODUCER", "PRODUCTION",
    "PRODUIT PAR", "PRODUCTEUR", "PRODUCTRICE", "PRODUCTION",
    "HERGESTELLT VON", "PRODUZENT", "PRODUKTION",
    "PRODOTTO DA", "PRODUTTORE", "PRODUZIONE",
    "PRODUCIDA POR", "PRODUCIDO POR", "PRODUCTOR", "PRODUCCION",
    "PRODUZIDO POR", "PRODUTOR", "PRODUCAO",
    # SV (İsveççe) — İNTİKAM (BECK - HÄMNDENS PRIS) kanıtı 2026-07-03: 8 yapımcı bu etiketlerle kayıptı
    "PRODUCENT", "PRODUCENTER", "EXEKUTIV PRODUCENT", "EXEKUTIVA PRODUCENTER",
    # ÇOK-DİLLİ GENİŞLEME (2026-07-06): NL/PL/HU/RO/RU/HI/AR translit
    "PRODUCTIE", "PRODUKCJA", "PRODUKCE", "GYARTO", "PRODUCATOR",
    "PRODYUSER", "PRODJUSER", "NIRMATA", "MUNTIJ", "SEISAKU", "ZHIPIAN",
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
    # SANAT-YÖNETİMİ tüm dillerde (2026-07-06 BAŞKAN VE MARI regresyon: "DIRECTION ARTISTIQUE"
    # → "DIRECTION" içerdiği için yönetmen sanılıp 'ARISTIQUE FRANCE' uydurdu). ART DIRECTION ≠ yönetmen.
    "ARTISTIQUE", "ARTISTICA", "ARTISTICO", "ARTISTICH", "DIRECTION ARTISTIQUE",
    "DIRECAO DE ARTE", "DIREZIONE ARTISTICA", "KUNSTLERISCHE LEITUNG", "SANAT YONETMENI",
    # cast/yapımcı doğruluk-denetimi 2026-07-04 — yapımcı YANLIŞ-ROL grubu (14 vaka):
    # bu alt-yapımcı unvanları düz "Yapımcı" değildir (KESİN-KURAL). Exec-Producer LİSTEDE YOK
    # (o gerçek yapımcı sayılır) — burada yalnız associate/co/line/uygulayıcı + yardımcı-üretim.
    "CO PRODUCER", "COPRODUCER", "CO-PRODUCER", "ASSOCIATE PRODUCER", "SUPERVISING PRODUCER",
    "CONSULTING PRODUCER", "PRODUCTION SUPERVISOR", "UYGULAYICI YAPIMCI", "ORTAK YAPIMCI",
    "YARDIMCI YAPIMCI", "DIRECTEUR DE PRODUCTION", "PRODUCTEUR ASSOCIE", "PRODUCTEUR EXECUTIF DELEGUE",
    "COPRODUZIONE", "PRODUTTORE ASSOCIATO", "PRODUCTOR ASOCIADO", "PRODUCTOR EJECUTIVO ASOCIADO",
    "PRODUKTIONSLEITUNG", "AUFNAHMELEITUNG",   # DE yapım-yönetimi
    # crew alt-rol garble/dil varyantları (cast CREW-SIZINTISI destek):
    "SESLENDIRME YONETMENI", "DUBLAJ YONETMENI", "COLLABORATEURS", "TRUCCATORE",
    "FIREARMS", "ISPOLNITELI", "STUNT COORDINATOR", "STUNT",
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

# Cümle-parçası freni için dilbilgisi sözcükleri (artikel/bağlaç/edat). İsim-PARÇACIKLARI
# (DE/VON/VAN/DER/LA/LE/DI/DA/DEL/BIN...) KASITLA YOK → 'ROBERT DE NIRO' korunur. (2026-07-07)
_NONNAME_WORDS = {
    "THE", "AN", "AND", "OR", "BUT", "NOR", "BY", "WITH", "WITHOUT", "FROM", "INTO", "ONTO",
    "THROUGH", "THROUGHOUT", "DURING", "WHILE", "WHEN", "WHERE", "WHICH", "WHOSE",
    "THAT", "THIS", "THESE", "THOSE", "ARE", "WAS", "WERE", "BEEN", "BEING",
    "HAVE", "HAS", "HAD", "WILL", "WOULD", "SHALL", "SHOULD", "COULD", "THAN", "THEN",
    "OU", "MAIS", "DANS", "POUR", "AVEC", "SANS", "QUE", "QUI", "UNE",
}

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
    # Cümle-parçası freni (2026-07-07 lexicon_anchor_misparse; GLORIA 1992-0299
    # "DIRECTED BY / EXPLODED THROUGHOUT AN UNSUSPECTING..."): 3+ token içinde 2+ dilbilgisi
    # sözcüğü varsa bu bir isim değil cümle parçasıdır. İsim-parçacıkları hariç → yanlış-red yok.
    if len(toks) >= 3 and sum(1 for t in toks if t in _NONNAME_WORDS) >= 2:
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

# "A <İSİM> FILM" / "AN <İSİM> FILM" / "BIR <İSİM> FILMI" — yönetmen KARTI ters-deseni:
# FILM/FILMI SONDA, isim ORTADA. DIRECTOR listesinde "A FILM BY X" (isim sonra) var ama bu
# ters-biçim YOK -> "A NIKI CARO FILM" hiçbir head'e uymuyordu. norm() çıktısı üstünde (A-Z+boşluk),
# isim 1-3 BÜYÜK kelime. (McFarland USA formatı; çok-dilli kredide yaygın.)
_DIRECTOR_CARD_RE = re.compile(r"^(?:A|AN|BIR)\s+([A-Z]+(?:\s+[A-Z]+){0,2})\s+(?:FILM|FILMI|FILMS)$")
# Stüdyo/marka tokenleri: "A WALT DISNEY FILM" / "A WARNER BROS FILM" gibi bumper'lar "A X FILM"
# desenine uyar ama yönetmen DEĞİL STÜDYO'dur. CORP'a EKLEMEYİZ (CORP cast-tespitinde de kullanılır;
# "FOX/BELL" gerçek SOYAD olabilir -> cast'i kırardı). Yalnız yönetmen-kartı yolunda bakılır.
_STUDIO_BRANDS = {
    "DISNEY", "PIXAR", "MARVEL", "WARNER", "BROS", "UNIVERSAL", "PARAMOUNT", "COLUMBIA",
    "DREAMWORKS", "LIONSGATE", "MGM", "MIRAMAX", "NETFLIX", "AMAZON", "APPLE", "HBO", "SONY",
    "FOX", "TRISTAR", "ORION", "RKO", "BLUMHOUSE", "LUCASFILM", "STUDIOCANAL", "GAUMONT", "PATHE",
}

def _is_studio(name_norm):
    return any(t in _STUDIO_BRANDS for t in name_norm.split())

def director_name_from_line(text):
    """Yönetmen satırından ismi DETERMİNİSTİK çıkar (norm'lu); isim yoksa ''.
    'A NIKI CARO FILM' -> 'NIKI CARO' | 'DIRECTED BY JOHN FORD' -> 'JOHN FORD'. Alt-rol + stüdyo DIŞLA."""
    nl = norm(text)
    if not nl or _has_excl(nl):
        return ""
    # SİNEMATOGRAF VETO (2026-07-07, BİR BEBEK EVİ/Joseph Losey + DELİLİĞİN SINIRINDA/Danny Huston
    # kökü): EXCLUDE listesi "DIRECTOR OF PHOTOGRAPHY"yi TAM-STRING arıyor ama ağır garble ("DIRECTOR
    # OF PHON", "DIRECTOR OI PHEN", "DIRECTOR E PHAH") bu alt-dizgeyi TAŞIMIYOR → süzgeç atlanıyor,
    # "DIRECTOR" head'i eşleşip ardındaki garble parçası ("OF PHON") isim sanılıyor (gerçek yönetmen
    # ise SATIRLARCA SONRA, ayrı bir bare "DIRECTOR" etiketiyle geliyor, hiç bulunamıyor). Desen:
    # "DIRECTOR" + sonraki herhangi bir token "PH..." ile başlıyor → HER ZAMAN görüntü-yönetmeni
    # garble'ı (gerçek yönetmen-etiketi asla "DIRECTOR PH..." biçiminde olmaz).
    _tf0 = nl.split()
    if _tf0 and _tf0[0] == "DIRECTOR" and len(_tf0) >= 2 and any(t.startswith("PH") for t in _tf0[1:]):
        return ""
    m = _DIRECTOR_CARD_RE.match(nl)
    if m:
        cand = m.group(1).strip()
        return cand if (_is_name(cand) and not _is_studio(cand)) else ""
    h = _match_head(nl, DIRECTOR)
    if h and h != nl:                       # head VAR ve satır sadece head değil (isim taşıyor)
        rest = _strip_head(nl, h)
        if rest and _is_name(rest) and not _has_excl(rest) and not _is_studio(rest):
            return rest
    return ""

def is_director_line(text):
    """Satır KENDİ İÇİNDE yönetmen ismi taşıyan bir yönetmen-tabiri mi?
    ('A X FILM' ters-deseni VEYA 'DIRECTED BY X' head+isim). Bare head ('DIRECTOR') ve şirket
    isimleri False -> kurtarmada gürültü eklemez. Alt-rol (assistant/DoP) DIŞLANIR."""
    return bool(director_name_from_line(text))

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
        # "A X FILM" yönetmen-kartı ters-deseni (head listesinde YOK) — isim ortada, ORİJİNAL casing koru
        _cm = _DIRECTOR_CARD_RE.match(nl)
        if _cm and _is_name(_cm.group(1).strip()) and not _is_studio(_cm.group(1).strip()):
            _ot = raw[i].strip().split()
            _nm = " ".join(_ot[1:-1]) if len(_ot) >= 3 else _cm.group(1).strip()
            if _nm and _nm not in out["director"]:
                out["director"].append(_nm)
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
