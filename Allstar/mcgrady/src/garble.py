# -*- coding: utf-8 -*-
"""garble.py — garble dedektörü + kişi-adı süzgeci (McGrady kule kopyası).

SÖKÜM KAYNAĞI: scripts/credit_text_read.py'den yalnız QC2'nin kullandığı iki
zincir, birebir alındı (2026-08-18):
  • _looks_garble + yardımcıları (satır 1095-1163): _fold_ga, _lev_ga,
    _GA_ROLE_INST, _GA_VERB_SUFFIX, _GA_ROLE_REF
  • _only_persons + yardımcıları (satır 92-98, 1032-1054, 1717-1872): _fold,
    _TR_FOLD, _JUNK_WORDS, _NONPERSON_TOK, _ROLE_PREP/_ROLE_ORDINAL/
    _AMBIG_ROLE_NOUN/_ROLE_PHRASE_EXACT, _role_filter_on, _looks_character_role,
    _valid_person_name
Modülün TAMAMI kopyalanMADI: credit_text_read'un top-level import'unda
core.lexicon bağımlılığı var (kule yasak) ve QC2'nin ihtiyacı yok.
"""
import os
import re
import unicodedata

# ── temel katlama (credit_text_read satır 92-98) ─────────────────────────────
_TR_FOLD = str.maketrans("ışğçöüİIÄ", "isgcouiia")


def _fold(s: str) -> str:
    s = (s or "").casefold().translate(_TR_FOLD)
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", s)


# ── F3: garble_audit.looks_garble yerel kopyası (satır 1095-1163) ────────────
def _fold_ga(s: str) -> str:
    """garble_audit.fold() yerel kopyası (import-time yan etki yok)."""
    s = (s or "").replace("ı","i").replace("İ","i").replace("ş","s").replace("Ş","s")
    s = s.replace("ğ","g").replace("Ğ","g").replace("ç","c").replace("Ç","c")
    s = s.replace("ö","o").replace("Ö","o").replace("ü","u").replace("Ü","u")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).upper()
    s = re.sub(r"[^A-Z ]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def _lev_ga(a: str, b: str) -> int:
    if a == b: return 0
    if not a: return len(b)
    if not b: return len(a)
    prev = list(range(len(b)+1))
    for i,ca in enumerate(a,1):
        cur=[i]
        for j,cb in enumerate(b,1):
            cur.append(min(prev[j]+1, cur[j-1]+1, prev[j-1]+(ca!=cb)))
        prev=cur
    return prev[-1]

# garble_audit.ROLE_INST — tam eşleşme blocklist (folded)
_GA_ROLE_INST = {
 "KUVVETLERI","SILAHLI","MUSTEREKEN","CEVIRDIGI","CEVIRME","TARAFINDAN","ORDU","ORDUSU",
 "DESIGNER","DIRECTOR","PRODUCER","EDITOR","OPERATOR","SENATORS","SENATOR","CHORUS","IORUS",
 "MAKEUP","MAKSUP","BASIGNER","FILMI","FILMHI","SANAK","PIIMIM","SOMR","ARSUANL","THEBAN",
 "PRODUCED","DIRECTED","SCREENPLAY","CAMERA","MUSIC","SOUND","COSTUME","COMPANY","STUDIO",
 "PICTURES","PRESENTS","STARRING",
 # EK (2026-06-20 garble-routing): müzik-kredi / departman / şirket-lisans token'ları (kişi-adı DEĞİL).
 # NOT: gerçek-oyuncu SOYADIYLA çakışan token'lar KASTEN dışarıda — DRIVER (Adam/Minnie Driver),
 # CRAFT (Christine Craft), FOLEY (Scott/Dave Foley), RUNNER. "CRAFT SERVICES" zaten SERVICES ile yakalanır.
 "PERFORMED","MIXED","ENGINEERED","ARRANGED","RECORDED","MASTERED","COMPOSED","CONDUCTED",
 "ORCHESTRATED","COURTESY","LICENSING","RECORDS","SOUNDTRACK","SERVICES","PRODUCTIONS",
 "ENTERTAINMENT","STUDIOS","RIGHTS","RESERVED","COORDINATOR","SECURITY",
 "CATERING","WRANGLER","GAFFER","TRANSPORTATION","TRANSPORT","DEPARTMENT","FACILITIES",
 "STANDBY","ACCOUNTANT","PUBLICIST","CASTING","WARDROBE","STUNTS","RERECORDING",
 "SUPERVISING","VISUAL","EFFECTS","COLORIST","COLOURIST","DUBBING","DISTRIBUTED","DISTRIBUTION",
}
# Türkçe fiil/cümle eki
_GA_VERB_SUFFIX = ("DIGI","DUGU","DIGINI","ERKEN","EREK","MEKTE","MAKTA","TIGI","TUGU","MISTIR","MUSTUR")
# garbled rol-etiketi fuzzy referansları
_GA_ROLE_REF = ["DESIGNER","DIRECTOR","PRODUCER","EDITOR","OPERATOR","CAMERAMAN","SUPERVISOR","ASSISTANT","COMPOSER"]


def _looks_garble(name: str) -> str | None:
    """garble_audit.looks_garble() yerel kopyası — SADECE YÜKSEK-İSABET sinyaller."""
    f = _fold_ga(name)
    toks = f.split()
    if not toks:
        return None
    # cümle eki
    for t in toks:
        if any(t.endswith(s) and len(t)>5 for s in _GA_VERB_SUFFIX):
            return f"cümle/fiil-eki ({t})"
    # rol/kurum/çöp token tam eşleşme
    hit = [t for t in toks if t in _GA_ROLE_INST]
    if hit:
        return f"rol/kurum/çöp token ({','.join(hit)})"
    # fuzzy garbled rol etiketi
    for t in toks:
        if len(t)>=6:
            for r in _GA_ROLE_REF:
                if 0 < _lev_ga(t,r) <= 2:
                    return f"garbled rol-etiketi ({t}~{r})"
    return None


# ── KESİN KURAL zinciri (satır 1032-1054 junk + 1717-1872 kişi süzgeci) ──────
# Disclaimer/bağlaç/rol-etiketi kelimeleri — bir "isim"de geçiyorsa o cümle
# parçasıdır, isim DEĞİL. Deterministik junk-filtre (çok-dilli); exact-token.
_JUNK_WORDS = {
    "por", "the", "del", "della", "con", "apoyo", "subvencionada", "presenta", "presents",
    "presente", "avec", "mit", "und", "von", "par", "fund", "fondo", "support", "courtesy",
    "arrangement", "association", "produced", "directed", "production", "produccion", "pelicula",
    "film", "films", "colaboracion", "gracias", "thanks", "tarafindan", "destek", "katki", "sunar",
    "ile", "tarafından", "yapim", "yapimi", "music", "starring", "cast", "story", "screenplay",
    "written", "based", "company", "pictures", "studio", "media", "entertainment", "all", "rights",
    "performed", "mixed", "visual", "effects", "effect", "licensing", "license", "records",
    # TR rol-etiketi / ajans token'ları (bir "isim"de geçerse o etiket/kurum, kişi DEĞİL):
    "direktoru", "direktor", "yonetmeni", "yonetmen", "menajerlik", "menajer", "ajans", "ajansi",
    "ekibi", "amiri", "sefi", "sorumlusu", "operatoru", "koordinator", "kordinator", "muhendis",
    "teknisyen", "asistani", "yardimcisi", "supervisor", "coordinator", "manager", "designer",
    "casting", "editor", "mixer", "gaffer", "grip",
    # MİRAS (2010-9280) kökü: "efekt" (TR "effect" karşılığı)
    "efekt",
    # YALNIZ TOM (1992-0484) kökü: "asst" — İngilizce rol-kısaltması
    "asst",
}

# KESİN KURAL: yönetmen/yapımcı/cast'te YALNIZ gerçek "İsim Soyisim" —
# ≥2 anlamlı token (isim+soyisim; orta-harf "E." serbest). TEK-TOKEN RED.
_NONPERSON_TOK = {
    "film", "films", "filmi", "filmleri", "production", "productions", "prod", "pictures", "picture",
    "studio", "studios", "media", "entertainment", "company", "co", "inc", "ltd", "llc", "gmbh", "srl",
    "tv", "yapim", "yapimi", "yapimevi", "yapimlari", "kuvvetleri", "silahli", "ordu", "ordusu",
    "kurumu", "vakfi", "dernegi", "bakanligi", "genel", "mudurlugu", "presents", "present", "sunar",
    "starring", "cast", "the", "and", "ile", "feat", "international", "group", "team", "pictures",
    "bros", "brothers", "sons", "enterprises", "enterprise", "corp", "corporation", "limited",
    "distribution", "releasing", "classics", "animation", "filmworks", "worldwide", "global",
    "networks", "network", "channel", "broadcasting", "partners", "associates",
    # kurum / vakıf / sendika / kuruluş (çok-dilli; gerçek "İsim Soyisim" token'ı değil)
    "foundation", "fondation", "fondazione", "stiftung", "agency", "agence",
    "association", "associazione", "guild", "union", "syndicate", "syndicat",
    "society", "societe", "societa", "institute", "institut", "instituto",
    "federation", "council", "conseil", "committee", "comite", "ministry",
    "ministere", "ministerio", "authority", "government", "gouvernement",
    "cinema", "cinematografica", "filmes", "filmproduktion", "produzione",
    "produktion", "telewizja", "presente", "presenta", "records", "rights", "reserved",
    # rol / sıfat / etiket
    "director", "directed", "producer", "produced", "executive", "associate", "yonetmen", "yapimci",
    "yoneten", "rejisor", "sunan", "anlatan", "music", "performed", "mixed", "visual", "effects",
    "effect", "licensing", "license", "records", "von", "der", "die",
}

# KAPI 1 — KARAKTER-ROL / TARİF ÇÖPÜ: yalnız YAPISAL olarak kesin desenler
# düşülür → hiçbir gerçek ada denk gelmez (token-bazlı rol-kelimesi reddi YASAK:
# birçok rol-kelimesi gerçek SOYADIDIR — Adam DRIVER, Mike JUDGE, Pat PRIEST).
_ROLE_PREP = {"at", "in", "on", "of", "with", "near", "behind", "outside", "inside",
              "aboard", "atop", "beside", "among", "amongst", "to", "from"}
_ROLE_ORDINAL = {"first", "second", "third", "fourth", "fifth", "sixth", "seventh",
                 "eighth", "ninth", "tenth", "1st", "2nd", "3rd", "4th"}
# ambiguous rol-ismi: TEK BAŞINA red ETMEZ (Man Ho / Boy George korunur); yalnız edatla birleşince.
_AMBIG_ROLE_NOUN = {"man", "woman", "boy", "girl", "lady", "guy", "men", "women", "boys",
                    "girls", "kid", "child", "children", "people", "voice", "guard",
                    "officer", "soldier", "cop", "policeman", "policewoman", "maid",
                    "waiter", "waitress", "nurse", "driver", "doctor", "captain", "priest"}
# tam-ifade (folded) çöp: bare rol-etiketleri + kredi-konvansiyonları (exact match).
_ROLE_PHRASE_EXACT = {
    "immigration officer", "police officer", "prison guard", "french maid",
    "night watchman", "himself", "herself", "themselves", "narrator",
}


def _role_filter_on() -> bool:
    return os.environ.get("MITAS_QC_ROLE_FILTER", "0").strip().lower() in ("1", "true", "on", "yes")


def _looks_character_role(name: str) -> bool:
    """True = karakter-tarifi/çöp (oyuncu ADI değil). Yalnız yapısal-kesin desen; gerçek ad düşürmez."""
    f = " ".join(_fold(name).split())
    if not f:
        return False
    if f in _ROLE_PHRASE_EXACT:                                              # (3) tam-ifade çöp
        return True
    toks = f.split()
    if any(t in _ROLE_PREP for t in toks) and any(t in _AMBIG_ROLE_NOUN for t in toks):  # (1)
        return True
    if toks[0] in _ROLE_ORDINAL and len(toks) >= 2:                          # (2) ordinal-önek
        return True
    return False


def _valid_person_name(name: str) -> bool:
    nm = (name or "").strip()
    if not nm or any(ch in nm for ch in "<>|/\\@&") or any(c.isdigit() for c in nm):
        return False
    toks = [t for t in _fold(nm).split() if t]
    real = [t for t in toks if len(t) >= 2]            # orta-harf (E.) serbest; ≥2 GERÇEK token şart
    # BAŞ-HARF-ÇOKLU İSİM: real TAM 1 + geri kalan TÜM token'lar saf tek-harf baş-harfse uzunluk-kapısı atlanır
    _init_only = [t for t in toks if len(t) == 1]
    _is_initials_name = (len(real) == 1 and bool(_init_only)
                          and len(_init_only) + len(real) == len(toks)
                          and all(t.isalpha() for t in _init_only))
    # 5-6 token YALNIZ soy-bağlacı içeriyorsa serbest; cümle-RED korunur.
    _VP_SOYBAG = {"de", "la", "le", "van", "von", "di", "del", "da", "dos", "el", "al", "bin", "der", "den"}
    if len(toks) > 6:
        return False
    if not _is_initials_name and len(real) < 2:        # tek-token RED, uzun-cümle RED
        return False
    if len(toks) > 4 and not _is_initials_name and not any(t in _VP_SOYBAG for t in toks):
        return False                                   # 5-6 token ama bağlaçsız = cümle şüphesi

    if any(t in _NONPERSON_TOK for t in toks) or any(t in _JUNK_WORDS for t in toks):
        return False
    if _looks_garble(nm):
        return False
    if _role_filter_on() and _looks_character_role(nm):     # KAPI 1: karakter-rol/tarif çöpü (flag'li)
        return False
    return True


def _only_persons(names):
    """KESİN KURAL süzgeci: yalnız geçerli 'İsim Soyisim' kalır."""
    return [n for n in (names or []) if _valid_person_name(n)]
