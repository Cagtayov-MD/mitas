# -*- coding: utf-8 -*-
"""MITAS — ORTAK künye parser + Film/Dizi sınıflandırma (TEK KAYNAK).

Konum: pdf-mitas/ — Film/Dizi PDF işinin tüm kuralları burada (bkz. PDF_Cikti_Kurallari.md).
Kullanan: scripts/_pipe_pdf.py (akış)  +  py/20260601_kunye_to_pdf.py (batch).

API:
  classify_trt(text)            -> (trt_id, tip 'FİLM'/'DİZİ', bolum|None, title_guess)   (§3)
  is_dizi(profile, trt_or_stem) -> bool   (merged 'film_dizi'/'auto' → TRT'den karar)
  parse_credits(lines, title, dizi=False) -> (cast, crew)                                 (§5.3–5.6)
    · FİLM: cast ilk 8 · crew {Yapımcı, Yönetmen}
    · DİZİ: cast TÜMÜ · crew TÜM bulunan rol, §5.4 kanonik sıra

Not: tek profil 'Film/Dizi' — tip TRT 3. parselden otomatik (1→FİLM, 0→DİZİ).
"""
from __future__ import annotations
import re
import unicodedata

# "&" veya " ve " (kelime-sınırlı, büyük/küçük duyarsız) ile birleşik kişi satırlarını böl
_AMPERSAND_RE = re.compile(r"\s*&\s*|\s+ve\s+", re.IGNORECASE)


# casefold sonrası Türkçe küçük harfleri ASCII'ye indir — KRİTİK: ı (U+0131) NFKD ile
# 'i'ye inmez, bu yüzden açık çeviri. Aksi halde "Yapımcı" anahtar "yapimci" ile eşleşmez.
_TR_FOLD = str.maketrans("ışğçöü", "isgcou")


def fold(s: str) -> str:
    s = (s or "").casefold().translate(_TR_FOLD)
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).strip()


# ---------- §3: TRT kimlikten Film/Dizi ----------
# blok:  YYYY-AAAA-T-EEEE-EE-E   ·  3. blok T: 1→FİLM, 0→DİZİ  ·  4. blok EEEE: bölüm no (dizi)
_TRT_DASH = re.compile(r"(\d{4})-(\d{3,4})-(\d)-(\d{3,4})-(\d{2})-(\d)")
_TRT_USC = re.compile(r"(\d{4})_(\d{3,4})_(\d)_(\d{3,4})_(\d{2})_(\d)")


def classify_trt(text: str):
    """(trt_id, tip, bolum, title_guess). TRT bulunamazsa FİLM varsayar, bütün metni başlık sayar."""
    s = text or ""
    m = _TRT_DASH.search(s) or _TRT_USC.search(s)
    if not m:
        return "", "FİLM", None, s.replace("_", " ").strip()
    y, a, typ, ep, e5, e6 = m.groups()
    trt = f"{y}-{a}-{typ}-{ep}-{e5}-{e6}"
    tip = "FİLM" if typ == "1" else "DİZİ"
    bolum = f"{int(ep)}. BÖLÜM" if typ == "0" else None
    title = (s[:m.start()] + " " + s[m.end():]).replace("_", " ").strip(" -_")
    return trt, tip, bolum, title


def is_dizi(profile: str, trt_or_stem: str = "") -> bool:
    """Merged profil ('film_dizi'/'auto'/boş) → TRT 3. parselden karar.
    Açık 'dizi'/'film' verilirse ona uyar (geri uyumluluk)."""
    p = (profile or "").strip().lower()
    if p == "dizi":
        return True
    if p == "film":
        return False
    _, tip, _, _ = classify_trt(trt_or_stem)
    return tip == "DİZİ"


# ---------- rol taksonomisi ----------
# EŞLEŞME sırası ÖNEMLİ: özgül roller önce. "assistant director" → Yön.Yard.,
# "director of photography" → Görüntü Yön.; bare "director/directed by" → Yönetmen.
_ROLE_MATCH = [
    ("Yönetmen Yardımcısı", ("yonetmen yard", "yard yonetmen", "yard. yonetmen", "asistan yonetmen",
                             "assistant director", "first assistant dir", "1st assistant dir",
                             "second assistant dir", "2nd assistant dir", "third assistant dir")),
    ("Görüntü Yönetmeni", ("goruntu yonet", "director of phot", "cinematograph", "d.o.p")),
    ("Sanat Yönetmeni", ("sanat yonet", "production design", "art director")),  # "yonetmeni" Yönetmen'e düşmesin
    ("Kameraman Yardımcısı", ("kameraman yard", "assistant camera", "focus puller", "asst camera")),
    ("Kameraman", ("kameraman", "cameraman", "camera operator")),
    ("Yönetmen", ("yonetmen", "directed by", "yoneten", "director",
                  "realise par", "mise en scene", "un film de", "film by",
                  "regie", "ein film von", "regia", "un film di",
                  "dirigida por", "dirigido por",
                  "rejissor", "rejisor",  # RU/AZ/KU (режиссёр fold->rejissor)
                  "skinothetis",  # GR (σκηνοθέτης fold)
                  "muharrij", "muharrac",  # AR (مخرج / المخرج fold yaklaşımı)
                  "daoyan")),  # ZH pinyin (导演)
    ("Yapımcı", ("yapimci", "produced by", "executive produc", "producer", "yapim ",
                 "produit par", "producteur", "produzent", "produziert von",
                 "prodotto da", "produttore", "productor",
                 "prodyuser",  # RU (продюсер fold)
                 "paragogos",  # GR (παραγωγός fold)
                 "muntij", "muntic",  # AR (منتج fold)
                 "zhizuoren", "zhipianren",  # ZH pinyin (制作人 / 制片人)
                 "berhemkar", "berhemvan", "berhemdar")),  # KU
    ("Senaryo", ("senaryo", "screenplay", "written by", "yazan", "screen story", "writer")),
    ("Kurgu", ("kurgu", "edited by", "film editor", "editor", "montaj")),
    ("Müzik", ("muzik", "music by", "besteci", "original score", "score by", "composer")),
    ("Ses", ("ses tasarim", "sound design", "sound mixer", "sound record", "sound by")),
    ("Işık", ("isik sefi", "gaffer", "lighting by")),
    ("Kostüm", ("kostum", "costume design", "wardrobe")),
    ("Makyaj", ("makyaj", "make-up", "make up", "makeup")),
    ("Dekor", ("dekor", "set decor", "set design")),
]
# §5.4 kanonik ÇIKTI sırası (eşleşme sırasından bağımsız sabit liste):
CANON_OUT = ["Yapımcı", "Yönetmen", "Yönetmen Yardımcısı", "Görüntü Yönetmeni",
             "Kameraman", "Kameraman Yardımcısı", "Kurgu", "Senaryo", "Müzik",
             "Sanat Yönetmeni", "Ses", "Işık", "Kostüm", "Makyaj", "Dekor"]

# Taksonomide ÖZGÜL karşılığı olmayan ama AÇIKÇA rol/ekip etiketi olan satırlar:
# kişi sanılıp cast/crew'e sızmasın diye "Diğer" başlığı sayılır (DİZİ'de gösterilir, FİLM'de düşer).
_GENERIC_ROLE_HINTS = (
    "coordinator", "cordinator", "co-ordinator", "manager", "supervisor", "assistant",
    "operator", "designer", "mixer", "recordist", "gaffer", "best boy", "grip", "runner",
    "trainee", "department", "wrangler", "accountant", "stand-in", "stand -in", "standby",
    "driver", "medic", "caterer", "publicist", "consultant", "chaperone", "trainer",
    "stunt", "rigger", "electrician", "carpenter", "painter", "plasterer", "armourer",
    "buyer", "dresser", "stylist", "technician", "loader", "puller", "clapper", "colorist",
    "colourist", "compositor", "animator", "captain", "engineer", "supervising", "head of",
    "casting", "continuity", "props", "second unit", "translator", "subtitl", "unit ",
    "location", "amiri", "sefi", "sorumlu", "asistani", "ekibi", "yonetimi",
    # Türkçe ekip etiketleri:
    "koordinator", "kordinator", "muhendis", "teknisyen", "mudur", "amir", "sef ",
    "operatoru", "uzman", "danisman", "egitmen", "sorumlusu", "yardimcisi",
)
# Bare "Yönetmen"/"Yapımcı" eşleşmesini GEÇERSİZ kılan nitelikçiler (D2: künyede
# YAPIM EKİBİ yalnız GERÇEK Yönetmen + GERÇEK Yapımcı). Bu kelimeler satırda
# geçiyorsa "director"/"produced by"/"producer" KİŞİYİ yönetmen/yapımcı yapmaz:
#   • "FINANCIAL/MUSIC/TECHNICAL/CASTING DIRECTOR", "DIRECTOR POSTPRODUCTIE/OF DEVELOPMENT"
#     → yönetmen DEĞİL  ·  • "EXECUTIVE/ASSOCIATE/LINE/SCORE ... PRODUCER/PRODUCED BY",
#   "YÜRÜTÜCÜ/ORTAK YAPIMCI" → (D2) GERÇEK yapımcı DEĞİL.
# Eşleşme bu yüzden "Diğer"e düşer (FİLM'de görünmez, DİZİ'de teknik başlık) — sızıntı yerine boş.
_ROLE_DISQUALIFY = (
    "financial", "finansal", "mali", "music", "muzik", "technical", "teknik", "casting",
    "post produc", "postproduc", "postprodüksiyon", "post prodüksiyon", "postproductie",
    "of development", "of photography", "score", "vocal", "voice", "dialogue", "dialog",
    "stunt", "fight", "stage", "floor", "second unit", "2nd unit", "unit ",
    "executive", "executif", "associate", "associe", "line produc", "co produc", "co-produc", "ortak yapim",
    "yurutucu", "delegate", "delege", "supervising produc", "field", "creative direct",
    "brand", "art ",  # "art director" zaten Sanat Yön.; emniyet için
)
_CAST_KW = ("oyuncular", "oyuncu", "cast", "starring", "oynayanlar", "rol dagilimi", "roller")
# "cast" substring eşleşmesi "casting director" gibi satırları yanlış CAST başlığına dönüştürüyor.
# Kelime-sınırlı regex ile kontrol: "casting director" → miss, "CAST" / "oyuncular" → hit.
_CAST_KW_RE = [re.compile(r"\b" + re.escape(k) + r"\b") for k in _CAST_KW]
_CORP_KW = ("film", "films", "production", "produksiyon", "prodüksiyon", "yapim", "yapimevi", "pictures",
            "picture", "studio", "entertainment", "media", "medya", "agency", "ajans", "fund", "fonu",
            "academy", "international", "gmbh", " inc", " llc", " ltd", "company", "distribution", "sales",
            "institute", "enstitu", "kurumu", "group", "grup", "sinema", "cinema", "televizyon", "arte",
            "radyo", "eurimages", "presents", "present", "organisation", "organization",
            "management", "menajerlik", "menajer", "iletisim")  # menajerlik/iletisim ajansi cast'e sizmasin


def role_of(line: str):
    f = fold(line).strip(" .:-")
    w = f.split()
    if not w or len(w) > 6:
        return None
    if any(r.search(f) for r in _CAST_KW_RE):
        return "CAST"
    # bare Yönetmen/Yapımcı niteliklendirilmişse (financial/executive/score...) → o etiketi atla,
    # satır aşağıda "Diğer"e düşsün (D2: yalnız GERÇEK yönetmen/yapımcı bu kovalara girer).
    disq = any(d in f for d in _ROLE_DISQUALIFY)
    for label, kws in _ROLE_MATCH:
        if disq and label in ("Yönetmen", "Yapımcı"):
            continue
        if any(k in f for k in kws):
            return label
    if any(h in f for h in _GENERIC_ROLE_HINTS) or disq:
        return "Diğer"  # bilinmeyen ama açık rol/ekip etiketi (veya niteliklendirilmiş yön/yapımcı)
    return None


def is_company(line: str) -> bool:
    return any(k in fold(line) for k in _CORP_KW)


def is_person(line: str, title_f: str = "") -> bool:
    t = (line or "").strip()
    w = t.split()
    if not (1 <= len(w) <= 5) or len(t) < 3:
        return False
    if "(" in t or ")" in t or any(ch.isdigit() for ch in t):
        return False
    letters = sum(c.isalpha() for c in t)
    nonsp = sum(not c.isspace() for c in t)
    if nonsp == 0 or letters / nonsp < 0.75:
        return False
    if is_company(line):
        return False
    if title_f and fold(t) == title_f:
        return False
    return True


def _dedup(xs):
    s, o = set(), []
    for x in xs:
        k = fold(x)
        if k and k not in s:
            s.add(k)
            o.append(x)
    return o


def parse_credits(lines, title: str = "", *, dizi: bool = False):
    """OCR künye satırları → (cast, crew). crew = [(rol, [isim,...])], §5.4 kanonik sıra.

    FİLM (dizi=False): cast ilk 8 · crew yalnız {Yapımcı, Yönetmen}.
    DİZİ (dizi=True):  cast tümü   · crew bulunan TÜM rol, kanonik sırayla (+ bilinmeyen roller sona).
    """
    title_f = fold(title)
    has_cast_h = any(role_of(l) == "CAST" for l in lines)
    cast: list[str] = []
    roles: dict[str, list[str]] = {}
    cur = None
    seen_crew = False
    cap = 99 if dizi else 3
    for l in lines:
        r = role_of(l)
        if r is not None:
            cur = r
            if r != "CAST":
                seen_crew = True
                roles.setdefault(r, [])
            continue
        if not is_person(l, title_f):
            # "&" / " ve " ile birleşik satır olabilir; parçalara böl ve her birini dene
            parts = [p.strip() for p in _AMPERSAND_RE.split(l) if p.strip()]
            if len(parts) < 2:
                continue
            for part in parts:
                if not is_person(part, title_f):
                    continue
                if cur == "CAST":
                    cast.append(part)
                elif cur in roles:
                    if len(roles[cur]) < cap:
                        roles[cur].append(part)
                elif cur is None and not seen_crew and not has_cast_h:
                    cast.append(part)
            continue
        # "&" / " ve " ile birleşik ama is_person geçti (nadir: çok kısa satır) → yine böl
        parts = [p.strip() for p in _AMPERSAND_RE.split(l) if p.strip()]
        if len(parts) >= 2:
            for part in parts:
                if not is_person(part, title_f):
                    continue
                if cur == "CAST":
                    cast.append(part)
                elif cur in roles:
                    if len(roles[cur]) < cap:
                        roles[cur].append(part)
                elif cur is None and not seen_crew and not has_cast_h:
                    cast.append(part)
            continue
        if not is_person(l, title_f):
            continue
        if cur == "CAST":
            cast.append(l)
        elif cur in roles:
            if len(roles[cur]) < cap:
                roles[cur].append(l)
        elif cur is None and not seen_crew and not has_cast_h:
            cast.append(l)

    cast = _dedup(cast)
    # tek-kelime cast girisleri (karakter-adi/crew-etiketi/OCR-cop: "Asuman"/"Cutter"/":"/"DI") sizar;
    # COK-kelime gercek isim VARSA tek-kelimeleri ele. Olcum (57 kunye / 505 cast): 27 tek-kelimenin
    # TAMAMI karakter/etiket/cop, 0 gercek mononim oyuncu. HEPSI tek-kelime ise DOKUNMA (nadir; cast'i
    # komple silme + haber anahtar-soz EKONOMI/HABER da tek-kelime, korunmali).
    _multi = [c for c in cast if len(c.split()) >= 2]
    if _multi:
        cast = _multi
    if not dizi:
        cast = cast[:8]
        order = [k for k in ("Yapımcı", "Yönetmen") if k in roles]
    else:
        order = [k for k in CANON_OUT if k in roles]
        order += [k for k in roles if k not in CANON_OUT]  # bilinmeyen ekstra roller sona

    crew = []
    for k in order:
        names = _dedup(roles.get(k, []))
        if names:
            crew.append((k, names))
    return cast, crew
