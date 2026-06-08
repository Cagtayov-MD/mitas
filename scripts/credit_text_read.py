#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""credit_text_read.py — OneOCR+GLM HAM METNİNDEN rol-eşleme (VLM-okuma YERİNE).

KURAL (Çağatay 2026-06-08): Okuma OneOCR+GLM ile yapılır; isimler OCR METNİNDEN gelir.
LLM yalnız ROL-EŞLEME yapar (pikselden OKUMAZ) → halüsinasyon imkânsız: her çıktı ismi
OCR metninde token olarak bulunmazsa ATILIR (anti-halüsinasyon kalkanı).

read_credits_from_text(lines, title, model) -> {"yonetmen":[...],"yapimci":[...],"cast":[...],"guven":...,"ham":...}

Akış: ham OCR satırları → LLM (rol-eşleme JSON, isim-metinden) → KALKAN (token-doğrulama)
      → GARBLE KAPISI (looks_garble) → KB ROL-FİLTRESİ (crew-oyuncu ayırt) → çıktı.

2026-06-08 F1/F2/F3 düzeltmeleri:
  F1 — ENSEMBLE: read_credits_auto artık tüm zinciri koşar, ilk-doluda durmaz;
       credit_video_read.fuse() mantığıyla yönetmen mutabakatı/KB-seçimi.
  F2 — KB ROL-FİLTRESİ: credit_video_read.KB ile crew→cast sızıntısını keser.
  F3 — GARBLE KAPISI: outputs/garble_audit.looks_garble ile garble isimler atılır.
"""
from __future__ import annotations
import json
import os
import re
import sys
import unicodedata
import urllib.request

OLLAMA = os.environ.get("MITAS_OLLAMA", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.environ.get("MITAS_CREDIT_TEXT_MODEL", "qwen3:8b")

_TR_FOLD = str.maketrans("ışğçöüİIÄ", "isgcouiia")


def _fold(s: str) -> str:
    s = (s or "").casefold().translate(_TR_FOLD)
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", s)


def _toks(s: str):
    return [t for t in _fold(s).split() if len(t) > 2]


SCHEMA = {
    "type": "object",
    "properties": {
        "yonetmen": {"type": "array", "items": {"type": "string"}},
        "yapimci": {"type": "array", "items": {"type": "string"}},
        "oyuncular": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["yonetmen", "yapimci", "oyuncular"],
}

PROMPT = """Aşağıda bir filmin jeneriğinden (künye) OCR ile okunan satırlar var. Satırlar BOZUK/eksik olabilir.
GÖREVİN: bu satırlardan YÖNETMEN, YAPIMCI ve baş OYUNCULARI çıkarmak — YENİDEN OKUMAK ya da bilgiden EKLEMEK DEĞİL.

KESİN KURALLAR:
0. BİÇİM (EN ÖNEMLİ): her isim GERÇEK "Ad Soyad" olmalı — en az İKİ kelime, gerçek bir insan. TEK kelime (yalnız ad VEYA yalnız soyad) YAZMA. Marka/şirket/stüdyo/logo adı (ör. Warner Bros, Lucasfilm, Columbia Pictures), sıfat, rol/etiket sözcüğü İSİM DEĞİLDİR — YAZMA. Emin değilsen o ismi atla.
1. SADECE aşağıdaki satırlarda GEÇEN isimleri kullan. Kendi bilginden/hafızandan İSİM EKLEME, TAHMİN ETME. Bir alan satırlarda yoksa boş liste [] ver.
2. Bir satır "KARAKTER_ADI OYUNCU_ADI" biçimindeyse (ör. "CAL MORSE SAM WATERSTON", "FLETCHER REEDE JIM CARREY", "MARGARET THATCHER MERYL STREEP"), yalnız OYUNCU (gerçek kişi) adını al; KARAKTER adını KOYMA. Tek başına KARAKTER/ROL adı görünüyorsa (ör. yalnız "FLETCHER REEDE" veya "MARGARET THATCHER") onu LİSTEYE KOYMA — sadece gerçek oyuncu adlarını ver.
3. Rol etiketleri (DIRECTED BY, PRODUCED BY, YÖNETMEN, YAPIMCI, CAST, STARRING, THE END, MUSIC BY, WRITTEN BY...) ve şirket/kurum adları (FILM, FILMS, PRODUCTION, PICTURES, STUDIO, MEDIA, TV) İSİM DEĞİLDİR — listeye koyma.
4. YÖNETMEN — şu kalıplardan birinin YANINDAKİ/ALTINDAKİ GERÇEK kişi adı:
   - "DIRECTED BY <İSİM>", "A FILM BY <İSİM>", "A <İSİM> FILM" (ör. "A JOHN MCTIERNAN FILM" → John McTiernan), "AN <İSİM> FILM"
   - "YÖNETMEN", "YÖNETEN", "REJİSÖR", "UN FILM DE", "EIN FILM VON", "REGIE", "RÉALISÉ PAR"
   "A <İSİM> FILM" kalıbında "FILM" kelimesi ETİKETtir; içindeki KİŞİ adını AL (kural 3'e takılıp atlama).
   YÖNETMEN DEĞİLDİR — KOYMA: "ASSISTANT DIRECTOR / 1ST / 2ND / FIRST / SECOND ASSISTANT DIRECTOR", "DIRECTOR OF PHOTOGRAPHY", "ART DIRECTOR", "CASTING (BY)", "MUSIC DIRECTOR", yardımcı/görüntü/müzik/yapım yönetmeni.
   Bu kalıplardan hiçbiri NET değilse [] ver — ASLA oyuncu adı koyma, ASLA tahmin etme.
5. OYUNCULAR: jenerikte görünen GERÇEK oyuncu adları (gerçek insanlar; karakter/rol adları DEĞİL), en fazla 8, görünme sırasıyla. Besteci/müzik, kurgu, senaryo, görüntü yönetmeni, yapımcı gibi EKİP üyeleri OYUNCU DEĞİLDİR — cast'e koyma.
6. YAPIMCI: "PRODUCED BY / YAPIMCI / PRODUCER" yanındaki kişi(ler). Besteci/müzik (COMPOSER/MUSIC BY), kurgu, senaryo YAPIMCI DEĞİLDİR — koyma. "Executive/Associate/Line/Co-producer / Yürütücü / Ortak yapımcı" da GERÇEK yapımcı sayılmaz.

ÇIKTI: yalnız JSON: {"yonetmen": [...], "yapimci": [...], "oyuncular": [...]}

SATIRLAR:
%s
"""


def _deepseek_json(model, prompt, timeout=120):
    """DeepSeek (API) JSON yanıtı — model adı 'deepseek*' ise. Anahtar yoksa {} (graceful)."""
    try:
        from _deepseek import deepseek_text
    except Exception:
        return {}
    txt = deepseek_text(prompt=prompt + "\n\nYALNIZ geçerli JSON döndür.",
                        model=model, temperature=0, max_tokens=1200,
                        fmt={"type": "json_object"}, timeout=timeout)
    if not txt:
        return {}
    try:
        return json.loads(txt)
    except Exception:
        i = txt.find("{")
        if i >= 0:
            try:
                return json.JSONDecoder().raw_decode(txt[i:])[0]
            except Exception:
                pass
    return {}


def _ollama_json(model, prompt, schema, timeout=180):
    payload = {
        "model": model, "prompt": prompt, "format": schema, "stream": False,
        "options": {"temperature": 0, "num_ctx": 8192},
    }
    # qwen3* düşünme modeli → think=False (zorunlu JSON `format` ile over-think çakışmasın).
    # gemma3 düşünme modeli DEĞİL → think gönderme (bazı sürümler 400 verir).
    if str(model).startswith("qwen3"):
        payload["think"] = False
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(OLLAMA + "/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        resp = json.loads(r.read().decode("utf-8"))
    txt = resp.get("response", "")
    try:
        return json.loads(txt)
    except Exception:
        i = txt.find("{")
        if i >= 0:
            try:
                return json.JSONDecoder().raw_decode(txt[i:])[0]
            except Exception:
                pass
    return {}


# Disclaimer/bağlaç/rol-etiketi kelimeleri — bir "isim"de geçiyorsa o cümle parçasıdır, isim DEĞİL.
# Deterministik junk-filtre (çok-dilli): LLM bazen "PELÍCULA SUBVENCİONADA POR EL" gibi disclaimer
# satırını cast'e koyuyor → exact-token eşleşmeyle düşür (alt-dize değil; "connery"≠"con").
_JUNK_WORDS = {
    "por", "the", "del", "della", "con", "apoyo", "subvencionada", "presenta", "presents",
    "presente", "avec", "mit", "und", "von", "par", "fund", "fondo", "support", "courtesy",
    "arrangement", "association", "produced", "directed", "production", "produccion", "pelicula",
    "film", "films", "colaboracion", "gracias", "thanks", "tarafindan", "destek", "katki", "sunar",
    "ile", "tarafından", "yapim", "yapimi", "music", "starring", "cast", "story", "screenplay",
    "written", "based", "company", "pictures", "studio", "media", "entertainment", "all", "rights",
    # TR rol-etiketi / ajans token'ları (bir "isim"de geçerse o etiket/kurum, kişi DEĞİL):
    "direktoru", "direktor", "yonetmeni", "yonetmen", "menajerlik", "menajer", "ajans", "ajansi",
    "ekibi", "amiri", "sefi", "sorumlusu", "operatoru", "koordinator", "kordinator", "muhendis",
    "teknisyen", "asistani", "yardimcisi", "supervisor", "coordinator", "manager", "designer",
    "casting", "editor", "mixer", "gaffer", "grip",
}


def _guard(names, ocr_fold_tokens, title_f):
    """Anti-halüsinasyon + junk-filtre: her ismin anlamlı tokenlarının TÜMÜ OCR metninde geçmeli;
    1-4 kelime; disclaimer/bağlaç kelimesi içermemeli. Aksi halde uydurma/çöp → atılır."""
    out, seen = [], set()
    for nm in names or []:
        nm = (nm or "").strip()
        if not nm:
            continue
        tk = _toks(nm)
        if not tk:
            continue
        # TÜM anlamlı tokenlar OCR metninde olmalı (halüsinasyon kalkanı)
        if not all(t in ocr_fold_tokens for t in tk):
            continue
        # isim 1-4 anlamlı kelime; daha uzunu cümle/disclaimer
        if len(tk) > 4:
            continue
        # disclaimer/bağlaç/etiket kelimesi içeren "isim" = cümle parçası → düş
        if any(t in _JUNK_WORDS for t in tk):
            continue
        if _fold(nm).strip() == title_f:  # film adının kendisi isim değil
            continue
        k = " ".join(tk)
        if k in seen:
            continue
        seen.add(k)
        out.append(nm)
    return out


# ─── F3: garble_audit.looks_garble import ───────────────────────────────────
# outputs/garble_audit.py script olarak yazılmıştır (if __name__== bloğu var).
# Sadece looks_garble + yardımcılarını yeniden tanımlamak en güvenli yol.
# (sys.path hack ile import etmek o dosyanın DB tarama kodunu çalıştırır → import-time yan etki)

import unicodedata as _uni

def _fold_ga(s: str) -> str:
    """garble_audit.fold() yerel kopyası (import-time yan etki yok)."""
    s = (s or "").replace("ı","i").replace("İ","i").replace("ş","s").replace("Ş","s")
    s = s.replace("ğ","g").replace("Ğ","g").replace("ç","c").replace("Ç","c")
    s = s.replace("ö","o").replace("Ö","o").replace("ü","u").replace("Ü","u")
    s = _uni.normalize("NFKD", s)
    s = "".join(c for c in s if not _uni.combining(c)).upper()
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


def _sim_ga(a: str, b: str) -> float:
    a, b = _fold_ga(a), _fold_ga(b)
    m = max(len(a), len(b)) or 1
    return 1 - _lev_ga(a, b) / m


def _apply_garble_gate(names: list[str], kb=None) -> list[str]:
    """F3: garble olanı at; garble-varyant near-dup (VAVIZ KARAKAC ≈ YAVUZ KARAKAŞ) → garble'ı at temizi tut."""
    # 1. tek-isim garble taraması
    clean = []
    for nm in names:
        if _looks_garble(nm) is None:
            clean.append(nm)
    # 2. near-dup garble-varyant: sim ∈ [0.6, 0.97), aynı token sayısı, her token benzer ama eşit değil
    out = list(clean)
    removed = set()
    for i in range(len(clean)):
        if i in removed:
            continue
        for j in range(i+1, len(clean)):
            if j in removed:
                continue
            fa, fb = _fold_ga(clean[i]), _fold_ga(clean[j])
            if fa == fb:
                # tam dedup — birini kaldır (j)
                removed.add(j)
                continue
            s = _sim_ga(clean[i], clean[j])
            if s < 0.6 or s > 0.97:
                continue
            ta, tb = fa.split(), fb.split()
            # Aynı token sayısı + HER token bound içinde (fa!=fb zaten üstte garanti → ≥1 token farklı).
            # NOT: '0 <' KOYMA — bir token fold'da eşit olabilir (KARAKAŞ/KARAKAÇ→KARAKAC), diğeri garble.
            if (len(ta) == len(tb) and len(ta) >= 1
                    and all(_lev_ga(x, y) <= max(2, len(x)//2) for x, y in zip(ta, tb))):
                ga = _looks_garble(clean[i])
                gb = _looks_garble(clean[j])
                if ga and not gb:
                    removed.add(i)
                elif gb and not ga:
                    removed.add(j)
                else:
                    # İkisi de _looks_garble=None: saf harf-bozulması OCR ÇİFT-OKUMASI
                    # (VAVIZ KARAKAC ≈ YAVUZ KARAKAŞ). Türkçe diakritik SAYISI fazla olanı KORU
                    # (OCR garble diakritiği kaybeder/bozar); eşitse ikisini de tut.
                    # GÜVENLİK: düşülecek isim KB'de gerçek OYUNCU ise DÜŞME (iki ayrı kişi olabilir).
                    _dia = lambda s: sum(c in "şŞıİğĞçÇöÖüÜ" for c in (s or ""))
                    di, dj = _dia(clean[i]), _dia(clean[j])
                    drop = j if di > dj else (i if dj > di else None)
                    if drop is not None and not (kb and _kb_has_actor_prof(clean[drop], kb)):
                        removed.add(drop)
    out = [nm for idx, nm in enumerate(clean) if idx not in removed]
    return out


# ─── F3 YAPIMCI için ROLE_INST ayrımı ────────────────────────────────────────
# Kurumsal yapımcı (TÜRK SİLAHLI KUVVETLERİ) gerçek olabilir → YAPIMCI'da sadece
# fiil-eki ve garble-varyant (near-dup) blocklist'i uygula, kurum-token ile kırma.
_GA_YAPIMCI_GARBLE_ONLY_TOKS = {
    "CEVIRDIGI","CEVIRME","MUSTEREKEN","FILMI","FILMHI","SANAK","PIIMIM","SOMR","ARSUANL",
    "PRODUCED","DIRECTED","PRESENTS","STARRING",
}

def _looks_garble_yapimci(name: str) -> str | None:
    """Yapımcı için özel garble: fiil-eki + üretim-etiketi tokenleri; kurum adı geçerse AT DEĞİL."""
    f = _fold_ga(name)
    toks = f.split()
    if not toks:
        return None
    for t in toks:
        if any(t.endswith(s) and len(t)>5 for s in _GA_VERB_SUFFIX):
            return f"cümle/fiil-eki ({t})"
    hit = [t for t in toks if t in _GA_YAPIMCI_GARBLE_ONLY_TOKS]
    if hit:
        return f"garble üretim-token ({','.join(hit)})"
    # fuzzy garbled rol-etiketi — yapımcıda da uygula
    for t in toks:
        if len(t)>=6:
            for r in _GA_ROLE_REF:
                if 0 < _lev_ga(t,r) <= 2:
                    return f"garbled rol-etiketi ({t}~{r})"
    return None


def _apply_garble_gate_yapimci(names: list[str]) -> list[str]:
    """Yapımcı için garble kapısı — kurum adını korur."""
    clean = []
    for nm in names:
        if _looks_garble_yapimci(nm) is None:
            clean.append(nm)
    # near-dup
    out = list(clean)
    removed = set()
    for i in range(len(clean)):
        if i in removed:
            continue
        for j in range(i+1, len(clean)):
            if j in removed:
                continue
            fa, fb = _fold_ga(clean[i]), _fold_ga(clean[j])
            if fa == fb:
                removed.add(j)
                continue
            s = _sim_ga(clean[i], clean[j])
            if s < 0.6 or s > 0.97:
                continue
            ta, tb = fa.split(), fb.split()
            if (len(ta) == len(tb) and len(ta) >= 1
                    and all(_lev_ga(x, y) <= max(2, len(x)//2) for x, y in zip(ta, tb))):
                ga = _looks_garble_yapimci(clean[i])
                gb = _looks_garble_yapimci(clean[j])
                if ga and not gb:
                    removed.add(i)
                elif gb and not ga:
                    removed.add(j)
                # else: ikisi de None → ikisini de tut (yapımcıda diakritik-tiebreak YOK, temkinli)
    return [nm for idx, nm in enumerate(clean) if idx not in removed]


# ─── F2: KB rol-filtresi (credit_video_read.KB) ──────────────────────────────
# KB'yi lazy import et; hata → filtre no-op (KB() zaten graceful)
_KB_INSTANCE = None

def _get_kb():
    global _KB_INSTANCE
    if _KB_INSTANCE is None:
        try:
            _scripts_dir = os.path.dirname(os.path.abspath(__file__))
            if _scripts_dir not in sys.path:
                sys.path.insert(0, _scripts_dir)
            from credit_video_read import KB
            _KB_INSTANCE = KB()
        except Exception:
            _KB_INSTANCE = _NullKB()
    return _KB_INSTANCE


class _NullKB:
    """KB yoksa graceful no-op: her verify → 'kayit-yok' (filtre geçir)."""
    def verify(self, name, role):
        return "kayit-yok"


# Non-acting meslek kümeleri — KB bu mesleklerden birini dönüyor ve oyunculuk İÇERMİYORSA cast'ten at.
# KB sadece "crew kökeni belli" olanı eler; 0-kayıt = belirsiz → filtre geçir.
_NON_ACTOR_PROFS = frozenset({
    "sound_department", "camera_department", "art_department", "costume_department",
    "editorial_department", "music_department", "visual_effects", "make_up_department",
    "production_manager", "script_and_continuity_department", "transportation_department",
    "electrical_department", "stunts", "special_effects", "set_decorator",
    # Bazen KB'de yönetmen/yapımcı dönebilir; cast'e koyulmuşsa yine de at.
    # (Yönetmen-cast karışıklığı F1'deki edge-case ile ele alınır, burada KB ile de yakalıyoruz.)
})
_ACTOR_PROFS = frozenset({"actor", "actress"})


def _kb_is_crew_not_actor(name: str, kb) -> bool:
    """KB net 'oyunculuk içermeyen ekip üyesi' diyorsa True → cast'ten at.
    0-kayıt / meslek-bos / hata → False (filtre geçir)."""
    try:
        result = kb.verify(name, "actor")
        if result in ("kayit-yok", "meslek-bos", "?", "ONAY"):
            return False
        # result == "RED": KB bu kişiyi "actor" değil dedi.
        # Ancak KB primaryProfession "producer/director" da diyebilir → bu durumda cast'ten at.
        # Ek kontrol: KB'deki professions setini doğrudan kontrol etmeliyiz.
        # credit_video_read.KB.verify() sadece ONAY/RED döndürüyor; profession setini açmıyor.
        # Biz RED gelmesi = "oyunculuk onaylanmadı" → ama KB "director" için RED verebilir.
        # Güvenli strateji: RED + KB üzerinde profession lookup
        if not kb.con:
            return False
        import unicodedata as _unn
        rows = kb.con.execute(
            "SELECT primaryProfession FROM names "
            "WHERE UPPER(strip_accents(primaryName))=UPPER(strip_accents(?))", [name]).fetchall()
        if not rows:
            return False
        profs = set()
        for (p,) in rows:
            if p:
                profs.update(x.strip() for x in str(p).split(","))
        if not profs:
            return False
        # Oyunculuk var mı?
        if profs & _ACTOR_PROFS:
            return False  # oyuncu → geçir
        # Oyunculuk YOK ve non-actor meslek var → cast'ten at
        if profs & _NON_ACTOR_PROFS:
            return True
        return False
    except Exception:
        return False


def _kb_has_actor_prof(name: str, kb) -> bool:
    """KB primaryProfession actor/actress içeriyor mu? 0-kayıt/hata → False.
    (Başrol-yönetmen ayrımı + garble-varyant güvenliği için.)"""
    try:
        if not getattr(kb, "con", None):
            return False
        rows = kb.con.execute(
            "SELECT primaryProfession FROM names "
            "WHERE UPPER(strip_accents(primaryName))=UPPER(strip_accents(?))", [name]).fetchall()
        profs = set()
        for (p,) in rows:
            if p:
                profs.update(x.strip() for x in str(p).split(","))
        return bool(profs & _ACTOR_PROFS)
    except Exception:
        return False


def _apply_kb_cast_filter(cast: list[str], kb) -> list[str]:
    """F2: KB 'oyuncu değil ve ekip-meslekli' diyenleri at; 0-kayıt → geçir."""
    return [nm for nm in cast if not _kb_is_crew_not_actor(nm, kb)]


def _apply_kb_yapimci_filter(yapimci: list[str], kb) -> list[str]:
    """Yapımcı için: KB net 'yapımcı değil' diyorsa düşür; 0-kayıt → geçir."""
    out = []
    for nm in yapimci:
        try:
            r = kb.verify(nm, "producer")
            if r == "RED":
                # Ek kontrol: gerçekten hiç yapımcılık yok mu?
                if kb.con:
                    rows = kb.con.execute(
                        "SELECT primaryProfession FROM names "
                        "WHERE UPPER(strip_accents(primaryName))=UPPER(strip_accents(?))", [nm]).fetchall()
                    profs = set()
                    for (p,) in rows:
                        if p:
                            profs.update(x.strip() for x in str(p).split(","))
                    # Oyuncu olanı yapımcıdan at
                    if "actor" in profs or "actress" in profs:
                        continue
                    # Yapımcılık/yönetmenlik yok ama başka meslek de yok → geçir
                    if "producer" not in profs and "director" not in profs:
                        out.append(nm)  # belirsiz → geçir
                        continue
                    # Net yapımcı değil → at
                    continue
                else:
                    out.append(nm)  # KB yok → geçir
            else:
                out.append(nm)
        except Exception:
            out.append(nm)
    return out


# ─── F1: ENSEMBLE yönetmen fusion (credit_video_read.fuse() mantığı) ─────────

def _dedup_fold(seq: list[str]) -> list[str]:
    out: list[str] = []
    for x in seq:
        if not any(_fold(x) == _fold(y) for y in out):
            out.append(x)
    return out


def _fuse_yonetmen(per_model: dict[str, list[str]], kb) -> tuple[list[str], str]:
    """
    Tüm modellerin yönetmen adaylarını birleştir:
      1. ≥2 modelde aynı → mutabakat (YÜKSEK güven)
      2. Tek model + KB-ONAY → al (ORTA güven)
      3. Çelişki (farklı isimler), KB-ONAY olanı seç; çoklu ONAY → hepsini al
      4. Hiçbiri KB-ONAY değilse tek okuma varsa al (DÜŞÜK güven)
      5. Çelişki + ONAY yok → [] (OKUNAMADI)

    EDGE-CASE — başrolu-yönetmen sanma:
      Bir yönetmen adayı cast listesinde üst sıralarda görünüyorsa ŞÜPHELI.
      Mutabakat yoksa ve sadece tek-model sinyali ise düşür.
      (Ör: Robert Redford başroldür, George Roy Hill yönetmendir.)
    """
    flat = [n for lst in per_model.values() for n in lst]
    if not flat:
        return [], "OKUNAMADI"

    all_flat = _dedup_fold(flat)

    # mutabakat: ≥2 modelde geçen
    agreed = [n for n in all_flat
              if sum(1 for lst in per_model.values()
                     if any(_fold(n) == _fold(x) for x in lst)) >= 2]
    if agreed:
        # KB-RED olanları çıkar
        agreed_ok = [n for n in agreed if kb.verify(n, "director") != "RED"]
        return (agreed_ok or agreed), "YÜKSEK (mutabakat)"

    # Tek model veya çelişki: KB-ONAY olanı seç
    kb_ok = [n for n in all_flat if kb.verify(n, "director") == "ONAY"]
    if kb_ok:
        return kb_ok, "ORTA (KB-onay)"

    # Tek okuma AMA mutabakat yok + KB onayı yok → GÜVENİLMEZ → ABSTAIN.
    # (Eski "DÜŞÜK tek-okuma" KALDIRILDI: tek-model yanlış yönetmeni ONAYLI'ya koyup
    #  VL-fallback'i engelliyordu — Asi→"John Platt", Sessiz Ölüm→"A.M.Thompson". "yanlış>boş".)
    return [], "OKUNAMADI (tek-okuma, mutabakat/KB yok)"


# ── KESİN KURAL (Çağatay): yönetmen/yapımcı/cast'te YALNIZ gerçek "İsim Soyisim" ──
# ≥2 anlamlı token (isim+soyisim; orta-harf "E." serbest). TEK-TOKEN (sadece isim/soyisim) RED.
# Marka/logo/şirket/kurum/sıfat/rol-etiketi/garble RED. Aksi → liste dışı.
_NONPERSON_TOK = {
    "film", "films", "filmi", "filmleri", "production", "productions", "prod", "pictures", "picture",
    "studio", "studios", "media", "entertainment", "company", "co", "inc", "ltd", "llc", "gmbh", "srl",
    "tv", "yapim", "yapimi", "yapimevi", "yapimlari", "kuvvetleri", "silahli", "ordu", "ordusu",
    "kurumu", "vakfi", "dernegi", "bakanligi", "genel", "mudurlugu", "presents", "present", "sunar",
    "starring", "cast", "the", "and", "ile", "feat", "international", "group", "team", "pictures",
    "bros", "brothers", "sons", "enterprises", "enterprise", "corp", "corporation", "limited",
    "distribution", "releasing", "classics", "animation", "filmworks", "worldwide", "global",
    "networks", "network", "channel", "broadcasting", "partners", "associates",
    # rol / sıfat / etiket
    "director", "directed", "producer", "produced", "executive", "associate", "yonetmen", "yapimci",
    "yoneten", "rejisor", "sunan", "anlatan", "music", "von", "der", "die",
}

def _valid_person_name(name: str) -> bool:
    nm = (name or "").strip()
    if not nm or any(ch in nm for ch in "<>|/\\@&") or any(c.isdigit() for c in nm):
        return False
    toks = [t for t in _fold(nm).split() if t]
    real = [t for t in toks if len(t) >= 2]            # orta-harf (E.) serbest; ≥2 GERÇEK token şart
    if len(real) < 2 or len(toks) > 4:                 # tek-token RED, cümle RED
        return False
    if any(t in _NONPERSON_TOK for t in toks) or any(t in _JUNK_WORDS for t in toks):
        return False
    if _looks_garble(nm):
        return False
    return True

def _only_persons(names):
    """KESİN KURAL süzgeci: yalnız geçerli 'İsim Soyisim' kalır."""
    return [n for n in (names or []) if _valid_person_name(n)]


def read_credits_from_text(lines, title="", model=None, *, dizi=False):
    model = model or DEFAULT_MODEL
    lines = [l.strip() for l in (lines or []) if l and l.strip()]
    text = "\n".join(lines)
    ocr_tokens = set(_toks(text))
    title_f = _fold(title).strip()
    out = {"yonetmen": [], "yapimci": [], "cast": [], "guven": "OKUNAMADI", "model": model}
    if not lines:
        out["hata"] = "bos_metin"
        return out
    try:
        if str(model).startswith("deepseek"):
            raw = _deepseek_json(model, PROMPT % text)
        else:
            raw = _ollama_json(model, PROMPT % text, SCHEMA)
    except Exception as e:
        out["hata"] = f"{type(e).__name__}: {e}"
        return out
    out["ham"] = raw
    yon = _guard(raw.get("yonetmen"), ocr_tokens, title_f)
    yap = _guard(raw.get("yapimci"), ocr_tokens, title_f)
    cast = _guard(raw.get("oyuncular"), ocr_tokens, title_f)
    if not dizi:
        cast = cast[:8]
    # KESİN KURAL: yalnız gerçek "İsim Soyisim"
    out["yonetmen"], out["yapimci"], out["cast"] = _only_persons(yon), _only_persons(yap), _only_persons(cast)
    if out["cast"] or out["yonetmen"]:
        out["guven"] = "OKUNDU (metin-rol-eşleme)"
    return out


def model_chain():
    """Metin model zinciri.
    KARAR (2026-06-09, 43-film ölçümü): TEK MODEL **qwen3:8b + think=False** (isabet %87, 2 yanlış).
    gemma3:12b ÇIKARILDI (isabet %64, 8 yanlış — gürültü + model-swap maliyeti; mutabakat artık
    VL aşamasında qwen2.5vl+gemma4 ile yapılır). Tek-model → fuse: yönetmen yalnız KB-onaylıysa
    metinde kalır, değilse abstain → VL-fallback devralır.
    Override: MITAS_CREDIT_TEXT_MODEL (virgüllü). DeepSeek opt-in: MITAS_CREDIT_TEXT_MODEL=deepseek-chat."""
    envm = os.environ.get("MITAS_CREDIT_TEXT_MODEL", "").strip()
    if envm:
        return [m.strip() for m in envm.split(",") if m.strip()]
    return ["qwen3:8b"]


def read_credits_auto(lines, title="", *, dizi=False):
    """F1: TÜM modelleri koş, ilk-doluda DURMA.
    Yönetmen: fuse() ile mutabakat/KB-seçimi.
    Cast: tüm modellerin birleşimi, dedup + F2 KB filtresi + F3 garble kapısı.
    Yapımcı: birleşim + F3 garble (yapımcı-özel) kapısı + F2 KB yapımcı filtresi.
    """
    chain = model_chain()
    lines = [l.strip() for l in (lines or []) if l and l.strip()]
    text = "\n".join(lines)
    ocr_tokens = set(_toks(text))
    title_f = _fold(title).strip()

    kb = _get_kb()

    per_model_yon: dict[str, list[str]] = {}
    per_model_cast: dict[str, list[str]] = {}
    all_cast: list[str] = []
    all_yap: list[str] = []
    any_success = False

    for m in chain:
        try:
            if str(m).startswith("deepseek"):
                raw = _deepseek_json(m, PROMPT % text)
            else:
                raw = _ollama_json(m, PROMPT % text, SCHEMA, timeout=180)
        except Exception as e:
            sys.stderr.write(f"[credit_text_read] {m} hata: {type(e).__name__}: {e}\n")
            per_model_yon[m] = []
            per_model_cast[m] = []
            continue

        yon_raw = _guard(raw.get("yonetmen"), ocr_tokens, title_f)
        yap_raw = _guard(raw.get("yapimci"), ocr_tokens, title_f)
        cast_raw = _guard(raw.get("oyuncular"), ocr_tokens, title_f)

        per_model_yon[m] = yon_raw
        per_model_cast[m] = cast_raw
        all_yap.extend(yap_raw)
        all_cast.extend(cast_raw)
        if yon_raw or cast_raw or yap_raw:
            any_success = True

    # ── F1: Yönetmen fusion ──────────────────────────────────────────────────
    yon_fused, guven_yon = _fuse_yonetmen(per_model_yon, kb)

    # ── F3 + F2: Cast boru hattı ─────────────────────────────────────────────
    cast_merged = _dedup_fold(all_cast)
    if not dizi:
        cast_merged = cast_merged[:8]
    cast_garble = _apply_garble_gate(cast_merged, kb)

    # F1 edge-case (BAŞROL-YÖNETMEN ayrımı): MUTABAKAT YOKSA, cast'te de görünen yönetmen
    # adayı büyük olasılıkla BAŞROL oyuncudur (ör. Waldo Pepper'da Robert Redford başrol,
    # yönetmen George Roy Hill; Redford KB'de yönetmen olduğu için ONAY alıp sızıyordu).
    # → yönetmenden DÜŞÜR (cast'te kalsın), "yanlış > boş" (okunamadı). Mutabakat (≥2 model)
    # varsa gerçek oyuncu-yönetmen olabilir (Eastwood/Allen) → DOKUNMA.
    # AYRAÇ (KB-bağımsız, self-consistency): bir yönetmen adayını öneren modellerden biri
    # AYNI ismi KENDİ cast'ine de koyduysa → o model kendi içinde çelişiyor → büyük olasılıkla
    # BAŞROL (Redford: qwen hem yönetmen dedi hem cast'ine koydu). Buna karşılık Cimino'yu
    # qwen yönetmen dedi ama KENDİ cast'ine koymadı (cast'e koyan gemma'ydı, o Walken dedi) →
    # çelişki YOK → KORU. Mutabakat (≥2 model) varsa gerçek oyuncu-yönetmen → dokunma.
    if guven_yon != "YÜKSEK (mutabakat)" and yon_fused:
        _kept = []
        for n in yon_fused:
            nf = _fold(n)
            proposers = [m for m, lst in per_model_yon.items() if any(_fold(x) == nf for x in lst)]
            self_contradict = any(
                any(_fold(c) == nf for c in per_model_cast.get(m, [])) for m in proposers)
            if self_contradict:
                continue  # başrol-yönetmen → düş ("yanlış > boş")
            _kept.append(n)
        if _kept != yon_fused:
            yon_fused = _kept
            if not _kept:
                guven_yon = "OKUNAMADI (başrol-yönetmen şüphesi)"
    # Kesin yönetmen cast'te de görünüyorsa cast'ten at (cast↔yönetmen kontaminasyon)
    yon_fold_set = {_fold(n) for n in yon_fused}
    cast_garble = [n for n in cast_garble if _fold(n) not in yon_fold_set]

    cast_kb = _apply_kb_cast_filter(cast_garble, kb)

    # ── F3 + F2: Yapımcı boru hattı ──────────────────────────────────────────
    yap_merged = _dedup_fold(all_yap)
    yap_garble = _apply_garble_gate_yapimci(yap_merged)
    yap_kb = _apply_kb_yapimci_filter(yap_garble, kb)

    # ── Güven skoru ──────────────────────────────────────────────────────────
    if not any_success:
        guven = "OKUNAMADI"
    elif cast_kb or yon_fused:
        guven = f"OKUNDU (ensemble; yön:{guven_yon})"
    else:
        guven = "KISMI (sadece yapımcı)"

    # KESİN KURAL (son süzgeç): yönetmen/yapımcı/cast'te yalnız gerçek "İsim Soyisim"
    return {
        "yonetmen": _only_persons(yon_fused),
        "yapimci": _only_persons(yap_kb),
        "cast": _only_persons(cast_kb),
        "guven": guven,
    }


def main():
    import argparse
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--ocr", required=True, help="OneOCR+GLM kunye.txt yolu")
    ap.add_argument("--title", default="")
    ap.add_argument("--model", default=None)
    ap.add_argument("--dizi", action="store_true")
    a = ap.parse_args()
    lines = open(a.ocr, encoding="utf-8", errors="ignore").read().splitlines()
    if a.model:
        # tek model modu (eski compat)
        res = read_credits_from_text(lines, a.title, a.model, dizi=a.dizi)
    else:
        res = read_credits_auto(lines, a.title, dizi=a.dizi)
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
