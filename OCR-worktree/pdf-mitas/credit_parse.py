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
import os
import re
import sys
import unicodedata
from pathlib import Path

# ── Korumalı bootstrap (§4.0, betik-farkında rol tanıma tasarımı) — bu dosya
# ayrı ağaçta (OCR-worktree/pdf-mitas/), _pipe_pdf.py importlib+path ile yüklüyor;
# korumalı bootstrap ikisinde de çalışır (§4.0'daki desenin AYNISI, yeni yöntem
# icat edilmedi).
_KOK = Path(os.environ.get("MITAS_PROJECT_ROOT") or "/opt/mitas")
if str(_KOK) not in sys.path:
    sys.path.insert(0, str(_KOK))
from core.lexicon.rol_tablosu import TABLO, rol_esles   # noqa: E402

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
#
# SIRA HATASI DÜZELTMESİ (2026-08-12, betik-farkında rol tanıma tasarımı §4.5):
# 'Kameraman' önceden 'Yönetmen'den ÖNCE geliyordu — role_of() ilk-eşleşeni
# döndürdüğü için "Director-Cameraman" (SENİ SEVİYORUM FRANK 1988-0480 gerçek OCR
# satırı) 'Kameraman' sayılıyordu (yanlış). Düzeltilmiş öncelik sırası:
#   Yönetmen Yardımcısı > Görüntü Yönetmeni > Sanat Yönetmeni > Yönetmen >
#   Kameraman Yardımcısı > Kameraman
# 'Yönetmen' kelime listesi core/lexicon/rol_tablosu.TABLO["LATIN"]["YONETMEN"]'e
# delege edildi (credit_role_lexicon.DIRECTOR birebir kopyası) — eski hardcoded
# liste SİLİNDİ; kapsam GENİŞLİYOR (ör. 'diretto da' eski listede yoktu, TABLO'da
# var) ve iki ayrı translit-tahmin listesinin (bu dosyanınki + credit_role_lexicon
# DIRECTOR'ınki) tutarsız yazımı (muharrij/muharrac vs mukhrij/ikhraj) TEK kaynağa
# indirgeniyor.
# EŞLEŞME + DIŞLAMA rol_tablosu.rol_esles'e TAM delege edilir (yalnız kelime
# listesi DEĞİL — ALGORİTMA da): düz substring DEĞİL, kelime-sınırlı ("RENDEZO"
# Macarca bileşik 'RENDEZOASSZISZTENS' — yönetmen ASİSTANI — içinde düz substring
# olarak da geçer, credit_role_lexicon._match_head zaten kelime-sınırlı olduğu
# için orada sorun yok). haric_uygula=True ŞART: TABLO["LATIN"]["YONETMEN"]
# genişletilmiş kelime dağarcığı (ör. bare 'REALISATION'/'REGISTA') HARIC
# uygulanmazsa Fransızca/İtalyanca ASİSTAN-yönetmen ifadelerini ("assistante
# réalisation", "aiuto regista", "1er assistant réalisateur") YANLIŞLIKLA
# 'Yönetmen' sayardı (2026-08-12, olc kanıtı: scripts/anlik_latin_taban.py §6.1
# taban karşılaştırması bunu yakaladı — önce kelime-sınırsız 558 satır fark,
# sınır eklenince 300 satır fark, rol_esles'in HARIC'i eklenince ~30 kaldı;
# kalanlar _ROLE_DISQUALIFY'a taşındı, bkz. aşağıdaki 'auxiliaire'/'exposure
# sheet' notu — TABLO["LATIN"]["HARIC"] credit_role_lexicon.EXCLUDE'un BİREBİR
# kopyası olmak ZORUNDA (§4.1), bu yüzden buraya özel eklenti YAPILAMAZ; onun
# yerine bu dosyanın KENDİ _ROLE_DISQUALIFY listesi kullanılır).
_YONETMEN_KWS = tuple(kelime.lower() for kelime in TABLO["LATIN"]["YONETMEN"])
_ROLE_MATCH = [
    ("Yönetmen Yardımcısı", ("yonetmen yard", "yard yonetmen", "yard. yonetmen", "asistan yonetmen",
                             "assistant director", "first assistant dir", "1st assistant dir",
                             "second assistant dir", "2nd assistant dir", "third assistant dir")),
    ("Görüntü Yönetmeni", ("goruntu yonet", "director of phot", "cinematograph", "d.o.p")),
    ("Sanat Yönetmeni", ("sanat yonet", "production design", "art director")),  # "yonetmeni" Yönetmen'e düşmesin
    ("Yönetmen", _YONETMEN_KWS),
    ("Kameraman Yardımcısı", ("kameraman yard", "assistant camera", "focus puller", "asst camera")),
    ("Kameraman", ("kameraman", "cameraman", "camera operator")),
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
    "brand", "art direct",  # "art director/direction"; dar tutuldu ki "Art Malik" gibi adı elemesin
    # 2026-08-12 (betik-farkında rol tanıma, adım 5): 'Yönetmen' artık
    # rol_tablosu.TABLO["LATIN"]["YONETMEN"]'e delege (bkz. yukarıdaki not) —
    # genişleyen kelime dağarcığı (bare 'REALISATION'/'REGISTA') haric_uygula=True
    # ile korunuyor AMA TABLO["LATIN"]["HARIC"] (credit_role_lexicon.EXCLUDE'un
    # birebir kopyası, §4.1 — buraya ÖZEL EKLENTİ YAPILAMAZ) Fransızca 'auxiliaire'
    # (yardımcı) ve animasyon-departmanı 'exposure sheet' (zaman çizelgesi, film
    # yönetmenliği DEĞİL) taşımıyor. Bu iki girdi credit_parse.py'ye ÖZEL (TABLO
    # kapsamı dışı) — olcum kanıtı: scripts/anlik_latin_taban.py §6.1 taban
    # karşılaştırması "Auxiliaire de réalisation" / "Exposure Sheet Direction &
    # Storyboard Slugging" satırlarını yanlışlıkla 'Yönetmen' sayıyordu.
    "auxiliaire", "exposure sheet",
)
_CAST_KW = ("oyuncular", "oyuncu", "cast", "starring", "oynayanlar", "rol dagilimi", "roller")
# "cast" substring eşleşmesi "casting director" gibi satırları yanlış CAST başlığına dönüştürüyor.
# Kelime-sınırlı regex ile kontrol: "casting director" → miss, "CAST" / "oyuncular" → hit.
_CAST_KW_RE = [re.compile(r"\b" + re.escape(k) + r"\b") for k in _CAST_KW]
_CAST_HEADER_DISQUALIFY = (
    "assistant", "editing", "casting", "extras", "department", "buyer", "director",
    "camera", "unit", "coordinator", "manager", "supervisor", "producer",
)
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
        # "CAST/EDITING ASSISTANT" and "EXTRAS CASTING" are crew roles, not a cast header.
        if any(k in f for k in _CAST_HEADER_DISQUALIFY) and f not in ("cast", "oyuncular", "oyuncu"):
            return "Diğer"
        return "CAST"
    # bare Yönetmen/Yapımcı niteliklendirilmişse (financial/executive/score...) → o etiketi atla,
    # satır aşağıda "Diğer"e düşsün (D2: yalnız GERÇEK yönetmen/yapımcı bu kovalara girer).
    disq = any(d in f for d in _ROLE_DISQUALIFY)
    for label, kws in _ROLE_MATCH:
        if disq and label in ("Yönetmen", "Yapımcı"):
            continue
        if label == "Yönetmen":
            if rol_esles(line, "YONETMEN", haric_uygula=True):    # betik-farkında + HARIC, bkz. yukarıdaki not
                return label
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


# ───────────────────────────────────────────────────────────────────────────
# FIX-1 (flag MITAS_CREDIT_PARSE_V2, default KAPALI): parse_credits ÇÖP-SERTLEŞTİRME.
# Kök-neden (2026-06-15 forensic): _pipe_pdf BİRİNCİL parse_credits kullanıyor; bu mekanik
# parser (a) "UN FILM DE <İSİM>" satırını etiket sayıp İSMİ DÜŞÜRÜYOR, (b) etiketten sonra
# gelen oyuncu satırlarını cap=3'e dek role DOLDURUYOR (overreach), (c) disclaimer/garble
# rol-etiketini (is_person harf-oranı geçer) role/cast'e SIZDIRIYOR. qwen (credit_text_read)
# bu süzgeçlere ZATEN sahip; buraya YÜKSEK-İSABET kopyaları taşınır. FLAG-OFF = davranış AYNI.
# İlke: yalnız ELE (uydurma yok), gerçek isim DÜŞMEZ (yüksek-isabet garble/junk/disclaimer).
_V2_STOP = "\x00V2STOP\x00"   # ön-geçiş işareti: inline-kurtarılan isimden SONRA bleed'i durdurur

# çok-kelime disclaimer/teknik-credit alt-dizeleri (fold'lu substring)
_V2_DISCLAIMER_SUB = (
    "tous droit", "droit reserve", "droits reserve", "all right", "right reserved",
    "rights reserved", "copyright", "tutti i diritti", "todos los derecho", "alle rechte",
    "with the participation", "avec la participation", "avec le soutien", "with the support",
    "in association with", "en association", "with support of", "made with the",
    "courtesy of", "developed with", "filmed with", "shot on", "filmed on", "color by",
    "pellicule", "eastmancolor", "kodak", "dolby", "in collaboration",
)
# tek-token junk (rol/etiket/şirket/disclaimer parçası) — credit_text_read._JUNK_WORDS portu
_V2_JUNK_TOK = {
    "por", "del", "della", "apoyo", "subvencionada", "presenta", "presents", "presente",
    "avec", "mit", "und", "von", "par", "fund", "fondo", "support", "courtesy", "arrangement",
    "association", "produced", "directed", "production", "produccion", "pelicula",
    "colaboracion", "gracias", "thanks", "tarafindan", "destek", "katki", "sunar",
    "starring", "screenplay", "written", "based", "entertainment", "rights", "reserved",
    "droits", "tous", "pellicule", "kodak", "eastmancolor",
    "direktoru", "direktor", "menajerlik", "menajer", "ajans", "ajansi", "amiri",
    "sefi", "sorumlusu", "operatoru", "koordinator", "kordinator", "muhendis", "teknisyen",
    "supervisor", "coordinator", "mixer", "gaffer", "grip",
    "assistee", "assiste", "province", "council", "councl", "regional",
}
_V2_ROLE_REF = ("DESIGNER", "DIRECTOR", "PRODUCER", "EDITOR", "OPERATOR", "CAMERAMAN",
                "SUPERVISOR", "ASSISTANT", "COMPOSER", "PRESENTS", "MANAGER")
_V2_VERB_SUFFIX = ("DIGI", "DUGU", "DIGINI", "ERKEN", "EREK", "MEKTE", "MAKTA",
                   "TIGI", "TUGU", "MISTIR", "MUSTUR")
# inline etiket-prefix → rol (fold'lu prefix). "<PREFIX> <İSİM>" satırında İSİM kurtarılır.
_V2_INLINE_LABELS = (
    ("directed by", "Yönetmen"), ("a film by", "Yönetmen"), ("an film by", "Yönetmen"),
    ("un film de", "Yönetmen"), ("ein film von", "Yönetmen"), ("realise par", "Yönetmen"),
    ("mise en scene", "Yönetmen"), ("dirigida por", "Yönetmen"), ("dirigido por", "Yönetmen"),
    ("regia di", "Yönetmen"), ("un film di", "Yönetmen"), ("yoneten", "Yönetmen"),
    ("produced by", "Yapımcı"), ("written by", "Senaryo"), ("screenplay by", "Senaryo"),
)


def _v2_on(v2):
    if v2 is not None:
        return bool(v2)
    return os.environ.get("MITAS_CREDIT_PARSE_V2", "").strip().lower() in ("1", "true", "on", "yes")


def _fold_lp(s: str) -> str:
    """Uzunluk-koruyan fold (NFKD YOK) — inline split'te konum eşlemesi için."""
    return (s or "").casefold().translate(_TR_FOLD)


def _lev(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _v2_garble_rolelabel(name: str) -> bool:
    """Yüksek-isabet garble rol-etiketi: Türkçe fiil-eki veya rol-sözcüğüne fuzzy(≤2) yakın token.
    Ör. 'FİRET AZTİSTANT DİRSETAR' → AZTISTANT~ASSISTANT (lev=2) → True. Gerçek isimde nadir."""
    f = fold(name).upper()
    for t in f.split():
        if any(t.endswith(s) and len(t) > 5 for s in _V2_VERB_SUFFIX):
            return True
        if len(t) >= 6:
            for r in _V2_ROLE_REF:
                if 0 < _lev(t, r) <= 2:
                    return True
    return False


def _v2_reject_name(name: str) -> bool:
    """v2: disclaimer/junk-token/garble-rol-etiketi/şirket ise True (role/cast'tan düş).
    GERÇEK 'İsim Soyisim' → False (düşmez). Yüksek-isabet — recall korunur."""
    if any(ch in (name or "") for ch in '/\\|<>@&"'):   # isimde olmayan noktalama → kişi değil
        return True
    f = fold(name)
    if not f:
        return True
    if any(sub in f for sub in _V2_DISCLAIMER_SUB):
        return True
    if any(t in _V2_JUNK_TOK for t in f.split()):
        return True
    if is_company(name):
        return True
    if _v2_garble_rolelabel(name):
        return True
    return False


def _v2_split_inline(lines):
    """v2 ön-geçiş: 'UN FILM DE NICOLAS VANIER' → ['UN FILM DE', 'NICOLAS VANIER', STOP].
    İSİM kurtarılır + STOP işareti sonraki oyuncu-satırı bleed'ini durdurur (overreach freni)."""
    out = []
    for l in lines:
        lf = _fold_lp(l).strip()
        hit = None
        for pref, _rol in _V2_INLINE_LABELS:
            if lf.startswith(pref + " "):
                rest = l[len(pref):].strip(" :.-")
                if rest and is_person(rest) and not _v2_reject_name(rest):
                    hit = (l[:len(pref)], rest)
                break
        if hit:
            out.append(hit[0])     # etiket parçası (role_of yine eşler → cur=rol)
            out.append(hit[1])     # kurtarılan isim
            out.append(_V2_STOP)   # bleed-stop: takip eden cast satırları role dolmasın
        else:
            out.append(l)
    return out


def parse_credits(lines, title: str = "", *, dizi: bool = False, v2=None):
    """OCR künye satırları → (cast, crew). crew = [(rol, [isim,...])], §5.4 kanonik sıra.

    FİLM (dizi=False): cast ilk 8 · crew yalnız {Yapımcı, Yönetmen}.
    DİZİ (dizi=True):  cast tümü   · crew bulunan TÜM rol, kanonik sırayla (+ bilinmeyen roller sona).
    """
    title_f = fold(title)
    v2 = _v2_on(v2)
    if v2:
        lines = _v2_split_inline(lines)   # "UN FILM DE X" → isim kurtar + bleed-stop
    has_cast_h = any(role_of(l) == "CAST" for l in lines)
    cast: list[str] = []
    roles: dict[str, list[str]] = {}
    cur = None
    seen_crew = False
    cap = 99 if dizi else 3
    for l in lines:
        if v2 and l == _V2_STOP:       # inline-kurtarılan isimden sonra bleed'i durdur
            cur = None
            continue
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
    if v2:   # FIX-1 post-filtre: disclaimer/junk/garble-rol-etiketi/şirket → role+cast'tan düş
        cast = [c for c in cast if not _v2_reject_name(c)]
        roles = {rol: [n for n in names if not _v2_reject_name(n)] for rol, names in roles.items()}
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
