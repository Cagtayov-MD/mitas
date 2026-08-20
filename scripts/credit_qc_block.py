# -*- coding: utf-8 -*-
"""credit_qc_block.py — BİRLEŞİK KÜNYE KALİTE-KONTROL BLOĞU.

Tek modülde toplar: gelen künyeyi düzgün kontrol et → eksiği AKTİF doldur →
çöp sızdırma → Latin-dışını çevir → ASCII/İ politikası → ONAYLI/KONTROL kararı.

EN ÜST KURAL — OCR-OTORİTE (memory: feedback_ocr_otorite_kanunu):
  OCR ne okuduysa O KANUN. Gelen veri (KB/web) OCR'ı ASLA EZMEZ. İzin verilen tek dönüşümler:
    (a) Latin-dışı alfabeyi Latin'e çevir (kişi aynı, yalnız alfabe),
    (b) name_match/name_close ile AYNI kişinin KB-kanonik yazımını uygula,
    (c) kimlik OCR'dan KİLİTLİYSE boş/eksik yerleri doldur (OCR isimlerinden SONRA ekle).
  Okunan ismi BAŞKA isimle değiştirmek YASAK (garble → KONTROL, override değil).

INVARIANT (kanıtlanabilir): temiz_cast'in ilk k elemanı (k=OCR isim sayısı) yalnız (a)/(b)
dönüşümünden geçer; farklı isimle değiştirilemez/silinemez (yalnız gerçek-olmayan garble düşer).
Eklemeler SADECE index≥k ve SADECE kimlik.locked iken yapılır.

Mimari: saf-fonksiyon çekirdek + tek giriş qc_credit_block(). Tüm bağımlılıklar guard'lı
(import başarısızsa fail-safe fallback). duckdb bağlantısı (kb) dışarıdan verilebilir.

YENİDEN KULLANIM (varsayım değil, okunan imzalar):
  credit_crosscheck:  name_match/name_close/name_close_window/cast_overlap_fuzzy/fold/CreditKB.crosscheck
  credit_text_read:   _looks_garble/_apply_garble_gate(_yapimci)/_only_persons/filter_cast_by_raw_context
  credit_qc_gates:    web_identity
  name_normalize:     upper_names/tr_upper_prose/ascii_fold  (pdf-mitas'tan importlib ile)
"""
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# yabancı-aksan → ASCII (Türkçe ç ğ ı İ ö ş ü korunur); translit-list son-netinde uygulanır.
try:
    from translit_util import asciify_foreign as _asciify_foreign
except Exception:                      # noqa: BLE001 — modül yoksa kimlik fonksiyonu (no-regress)
    def _asciify_foreign(s):
        return s

# ───────────────────────── guard'lı bağımlılıklar ─────────────────────────
import credit_crosscheck as cc  # saf modül (duckdb yalnız CreditKB.__init__'te) → global py'da güvenli

try:
    import credit_qc_gates as _qg          # web_identity (kimlik kurtarma çapası)
except Exception:                          # noqa: BLE001
    _qg = None

# credit_text_read ağır bağımlılık çekebilir (cv2/torch) → yalnız gerekenleri al, başarısızsa fallback.
try:
    from credit_text_read import (
        _looks_garble, _apply_garble_gate, _apply_garble_gate_yapimci, _only_persons,
        _valid_person_name, filter_cast_by_raw_context,
    )
except Exception:                          # noqa: BLE001 — fail-safe minimal davranış
    def _valid_person_name(name):           # type: ignore
        return bool(name and len(str(name).split()) >= 2 and not any(c.isdigit() for c in str(name)))

    def _looks_garble(_n):                  # type: ignore
        return None

    def _apply_garble_gate(names, kb=None):  # type: ignore
        return list(names or [])

    def _apply_garble_gate_yapimci(names):   # type: ignore
        return list(names or [])

    def _only_persons(names):                # type: ignore
        return [n for n in (names or []) if n and len(str(n).split()) >= 2]

    def filter_cast_by_raw_context(cast, raw):  # type: ignore
        return list(cast or [])

# name_normalize pdf-mitas altında — tek_film_kunye'deki _load deseniyle yükle.
_PDFMITAS = os.environ.get("MITAS_PDFMITAS_DIR", r"E:\MITAS\OCR-worktree\pdf-mitas")


def _load_module(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


try:
    nn = _load_module("nn_qc", os.path.join(_PDFMITAS, "name_normalize.py"))
except Exception:                          # noqa: BLE001 — casing fallback (ham .upper())
    nn = None


def _upper_names(names):
    if not names:
        return []
    if nn is not None:
        try:
            return nn.upper_names(list(names))
        except Exception:                  # noqa: BLE001
            pass
    return [str(n).upper() for n in names]


def _tr_upper_prose(text, names):
    if nn is not None:
        try:
            return nn.tr_upper_prose(text or "", names=names)
        except Exception:                  # noqa: BLE001
            pass
    return (text or "").upper()


def _fold(s):
    try:
        return cc.fold(s)
    except Exception:                      # noqa: BLE001
        return re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).strip()


# ───────── OCR-OTORİTE DENETİM SİNYALLERİ (flag MITAS_QC_OTORITE_AUDIT; SIFIR-ROUTE) ─────────
# A/B ÖLÇÜM + ileride ENFORCE için: ham-OCR groundtruth ile "okunan-düştü / okunmayan-eklendi /
# yakın-yazım-çift" OCR-otorite sapmalarını ÖLÇER. Karar/route'u DEĞİŞTİRMEZ (yalnız rapora yazılır,
# _ekle çağrılmaz). Tümü fail-safe; flag kapalıyken hiç çağrılmaz → bayt-bayt mevcut davranış.
def _audit_raw_token_seq(raw_lines):
    """Ham-OCR satırlarından SIRALI folded token dizisi (≥3 harf). Sıra korunur ki bitişiklik
    (adjacency) test edilebilsin: star-kart 'ELEANOR'\\n'PARKER' ardışık satırlarda → dizide ardışık."""
    seq = []
    for line in (raw_lines or []):
        for t in re.findall(r"[^\W\d_]+", str(line), flags=re.UNICODE):
            if len(t) >= 3:
                seq.append(_fold(t))
    return seq


def _audit_name_in_raw(name, raw_seq):
    """İsmin anlamlı token'ları (≥3 harf) ham-OCR token DİZİSİNDE BİTİŞİK (ardışık alt-dizi) geçiyor mu?
    Küme-üyeliği DEĞİL — 'ad+soyad' iki AYRI isimden tesadüfen toplanmasını engeller (feedback_
    dogrulanmamis_iddia_yasak: ad+soyad bitişik şartı). 'ELEANOR PARKER' ardışık satırda → yakalanır;
    'ANN LEE' ham'da 'MARY ANN'+'BRUCE LEE' varken (bitişik değil) → yakalanmaz (FP engellendi)."""
    nts = [_fold(t) for t in re.findall(r"[^\W\d_]+", str(name), flags=re.UNICODE) if len(t) >= 3]
    if not nts:
        return False
    n = len(nts)
    return any(raw_seq[i:i + n] == nts for i in range(len(raw_seq) - n + 1))


def _audit_find_fuzzy_dups(names):
    """Aynı kişinin iki yazımı: token-sayısı eşit, TEK token farklı ve o fark Lev≤2 (HAZELTON↔HAZLETON).
    SIFIR-ROUTE olduğundan kardeş/ayrı-soyad FP'leri (AHMET ASLAN↔AHMET ARSLAN) yalnız rapor-gürültüsü;
    ENFORCE'a bağlanmadan önce A/B eşik-ölçümü ile daraltılacak."""
    out, seen = [], set()
    folded = [(_fold(n), n) for n in (names or []) if n and str(n).strip() not in ("", "—")]
    for i in range(len(folded)):
        fi, ni = folded[i]
        ti = fi.split()
        for j in range(i + 1, len(folded)):
            fj, nj = folded[j]
            if fi == fj or not ti or len(ti) != len(fj.split()):
                continue
            diffs = [(x, y) for x, y in zip(ti, fj.split()) if x != y]
            if len(diffs) != 1:
                continue
            try:
                close = cc._lev(diffs[0][0], diffs[0][1], 2) <= 2
            except Exception:              # noqa: BLE001
                close = False
            if close:
                key = tuple(sorted((fi, fj)))
                if key not in seen:
                    seen.add(key)
                    out.append([ni, nj])
    return out


def _compute_otorite_audit(raw_groundtruth, final_cast, final_yap, otoriter_cast, iz,
                           s5_form_snaps=None):
    """SIFIR-ROUTE denetim: ham-OCR groundtruth ile OCR-otorite sapmalarını ölç. Karar ETKİLEMEZ."""
    raw_seq = _audit_raw_token_seq(raw_groundtruth)
    used = bool(raw_seq)
    final_fold = {_fold(n) for n in (final_cast or [])}
    # ocr_dropped: HEM ham-OCR'da okunmuş HEM KB-cast'te (gerçek) olan AMA final'de OLMAYAN isim
    ocr_dropped = []
    if used:
        for a in (otoriter_cast or []):
            if a and _fold(a) not in final_fold and _audit_name_in_raw(a, raw_seq):
                ocr_dropped.append(a)
    # KB sıfırdan kişi eklemez; audit alanı geriye dönük şema uyumu için korunur.
    kb_floor_added = []
    fuzzy_dups = _audit_find_fuzzy_dups(list(final_cast or []) + list(final_yap or []))
    # FIX-D (2026-06-23): S5 fuzzy-snap OCR-form ezmeleri (LEFEBVRE→LEFEVRE). raw_groundtruth varsa,
    # OCR-formu ham-OCR'da GERÇEKTEN OKUNAN ezmeler 'ocr_in_raw=True' işaretlenir (gerçek-isim ezildi
    # imzası); raw yoksa unconfirmed. GÖZLEM — kararı ETKİLEMEZ.
    s5_overwrites = []
    for sn in (s5_form_snaps or []):
        ocr_form = sn.get("ocr")
        confirmed = bool(used and ocr_form and _audit_name_in_raw(ocr_form, raw_seq))
        s5_overwrites.append({"ocr": ocr_form, "kb": sn.get("kb"), "ocr_in_raw": confirmed})
    # fix3-A 2026-06-29 — CAP-ÜSTÜ DÜŞEN: ham-OCR'da bitişik okunan AMA final_cast'te olmayan
    # temiz isimler (garble değil, cap-üstü sebebiyle düştü). KB-bağımsız: raw_seq tabanlı.
    raw_cap_dropped = []
    if used:
        final_fold = {_fold(n) for n in (final_cast or [])}
        raw_toks = raw_seq  # zaten list[str]
        # Bitişik 2-token ad-adaylarını raw_seq'ten tara
        for _ri in range(len(raw_toks) - 1):
            cand_tokens = raw_toks[_ri: _ri + 2]
            cand = " ".join(t.title() for t in cand_tokens)
            if (_fold(cand) not in final_fold
                    and _valid_person_name(cand)
                    and _looks_garble(cand) is None):
                raw_cap_dropped.append(cand)
        # Tekrar → distinct (2026-08-02 fix: eski one-liner dedup hiç çalışmıyordu —
        # _seen_rcd.add() None döner, _seen_rcd - {_fold(n)} az önce ekleneni çıkarır)
        _seen_rcd = set()
        _unique_rcd = []
        for n in raw_cap_dropped:
            _f = _fold(n)
            if _f not in _seen_rcd:
                _seen_rcd.add(_f)
                _unique_rcd.append(n)
        raw_cap_dropped = _unique_rcd
    return {
        "raw_groundtruth_used": used,
        "ocr_dropped": ocr_dropped,
        "kb_floor_added": kb_floor_added,
        "fuzzy_dups": fuzzy_dups,
        # FIX-D: S5 fuzzy-snap form ezmeleri (gözlem) + en az biri ham-OCR-teyitli mi
        "s5_form_overwrites": s5_overwrites,
        "s5_form_overwrite_confirmed": bool(any(o["ocr_in_raw"] for o in s5_overwrites)),
        # fix1-KB 2026-06-29 — SAF-KB EKLEME tek başına ihlaldir (AND koşulu KALDIRILDI)
        "ocr_authority_violation": bool(kb_floor_added),
        # fix3-A 2026-06-29 — cap-üstü ham-OCR'dan düşen temiz isimler (görünürlük; karar ETKİLEMEZ)
        "raw_cap_dropped": raw_cap_dropped,
    }


# ════════════════════════ TRANSLİTERASYON + DİL TESPİTİ ════════════════════════
# Kiril → Latin (Rusça birincil + Ukraynaca/Sırpça yaygın harfler). Küçük harf tablosu;
# büyük harf token-bazlı title-case ile geri verilir.
_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "ґ": "g", "д": "d", "е": "e", "ё": "yo",
    "є": "ye", "ж": "zh", "з": "z", "и": "i", "і": "i", "ї": "yi", "й": "y", "к": "k",
    "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya", "ђ": "dj", "ј": "j",
    "љ": "lj", "њ": "nj", "ћ": "c", "џ": "dz",
}
# Yunanca → Latin (ISO-843 benzeri, isim odaklı).
_GREEK = {
    "α": "a", "β": "v", "γ": "g", "δ": "d", "ε": "e", "ζ": "z", "η": "i", "θ": "th",
    "ι": "i", "κ": "k", "λ": "l", "μ": "m", "ν": "n", "ξ": "x", "ο": "o", "π": "p",
    "ρ": "r", "σ": "s", "ς": "s", "τ": "t", "υ": "y", "φ": "f", "χ": "ch", "ψ": "ps",
    "ω": "o", "ά": "a", "έ": "e", "ή": "i", "ί": "i", "ό": "o", "ύ": "y", "ώ": "o", "ϊ": "i",
}


def detect_script(text):
    """Metnin baskın harf-sistemi: latin|cyrillic|greek|arabic|han|hangul|other.
    tr_upper'ın 'LATIN' in unicodedata.name(ch) deseniyle aynı mekanizma; silmek yerine yönlendirir."""
    counts = {}
    for ch in (text or ""):
        if not ch.isalpha():
            continue
        try:
            nm = unicodedata.name(ch)
        except ValueError:
            continue
        if "LATIN" in nm:
            s = "latin"
        elif "CYRILLIC" in nm:
            s = "cyrillic"
        elif "GREEK" in nm:
            s = "greek"
        elif "ARABIC" in nm:
            s = "arabic"
        elif "CJK" in nm or "HIRAGANA" in nm or "KATAKANA" in nm:
            s = "han"
        elif "HANGUL" in nm:
            s = "hangul"
        else:
            s = "other"
        counts[s] = counts.get(s, 0) + 1
    if not counts:
        return "latin"
    nonlatin = {k: v for k, v in counts.items() if k != "latin"}
    if not nonlatin:
        return "latin"
    return max(nonlatin, key=nonlatin.get)


def _titlecase_tokens(s):
    return " ".join(t.capitalize() for t in s.split())


def transliterate(name, script=None):
    """Latin-dışı ismi Latin'e çevir. Döner (latin, yontem).
    yontem ∈ {tablo, unidecode, pypinyin, FAILED}. Kiril/Yunan deterministik tablo (lib gerekmez);
    Arapça/CJK/diğer için unidecode/pypinyin VARSA, yoksa FAILED (sessiz silme YOK → KONTROL/RENDER)."""
    sc = script or detect_script(name)
    if sc == "latin":
        return name, "latin"
    if sc == "cyrillic":
        out = "".join(_CYR.get(ch.lower(), ch if ch.isascii() else "") for ch in name)
        return _titlecase_tokens(out), "tablo"
    if sc == "greek":
        out = "".join(_GREEK.get(ch.lower(), ch if ch.isascii() else "") for ch in name)
        return _titlecase_tokens(out), "tablo"
    # han → önce pypinyin (isimde unidecode'dan iyi)
    if sc == "han":
        try:
            from pypinyin import lazy_pinyin  # type: ignore
            return _titlecase_tokens(" ".join(lazy_pinyin(name))), "pypinyin"
        except Exception:                  # noqa: BLE001
            pass
    # arabic/han/other → unidecode (kuruluysa)
    try:
        from unidecode import unidecode     # type: ignore
        out = unidecode(name).strip()
        if out and any(c.isalpha() for c in out):
            return _titlecase_tokens(out), "unidecode"
    except Exception:                      # noqa: BLE001
        pass
    return name, "FAILED"


# ════════════════════════════ KÜÇÜK YARDIMCILAR ════════════════════════════
_SPLIT_RE = re.compile(r"\s*&\s*|\s+ve\s+|\s*/\s*|\s*,\s*|\s+-\s+", re.I)


def _split_names(lst):
    """Birleşik isim satırlarını ('&'/'ve'/'/'/',') böl + fold-bazlı tekrar ele (sıra korunur).

    NOT: _fold Latin-dışı alfabeyi (Kiril/Çince/vb.) boş stringe döndürür — bu durum isimlerin
    S0'da silinmesine yol açardı (S2 translit hiç çalışamazdı). Düzeltme: fold boşsa orijinal
    part.lower() ile tekilleştir; isim korunur, S2'de translit devreye girer.
    """
    out, seen = [], set()
    for item in (lst or []):
        for part in _SPLIT_RE.split(str(item)):
            part = part.strip()
            if not part:
                continue
            k = _fold(part) or part.lower()   # fold boşsa (Kiril/Han/vb.) orijinali kullan
            if k not in seen:
                seen.add(k)
                out.append(part)
    return out


def poster_ok(path):
    """Geçerli afiş = dosya var + >5KB + PORTRE (w<h). Yatay/kare frame-grab RED. PIL yoksa boyut-fallback."""
    try:
        if not (path and os.path.exists(path) and os.path.getsize(path) > 5000):
            return False
        from PIL import Image
        with Image.open(path) as im:
            w, h = im.size
        return w < h
    except Exception:                      # noqa: BLE001
        try:
            return bool(path and os.path.exists(path) and os.path.getsize(path) > 5000)
        except Exception:
            return False


def _ozet_gate(ozet, names):
    """Placeholder reddi + kelime sayımı. Döner (cased_ozet, kelime_sayisi)."""
    if not ozet or re.search(r"HAM\s*TRANSCR|KAL[İIıi]P\s*[ÖOöo]ZET", str(ozet), re.I):
        return "—", 0
    temiz = re.sub(r'[?!"\[\]]', "", str(ozet))
    kelime = len([w for w in temiz.split() if w.strip()])
    return _tr_upper_prose(temiz, names), kelime


def _kb_producers(kb, imdb_id, limit=3):
    """KB'den (imdb principals category=producer) yapımcı isimleri — destek-doldurma için."""
    try:
        if not (kb is not None and getattr(kb, "imdb", None) and imdb_id):
            return []
        rows = kb.imdb.execute(
            "SELECT n.primaryName FROM principals p JOIN names n ON p.nconst=n.nconst "
            "WHERE p.tconst=? AND p.category='producer' LIMIT ?",
            [imdb_id, limit * 4],
        ).fetchall()
        return [r[0] for r in rows if r and r[0]]
    except Exception:                      # noqa: BLE001
        return []


def _films_by_director(kb, director, year=None, maxc=10):
    """YÖNETMEN-ÖNCE arama (kilit-oranı kaldıracı): KB'de (imdb principals) bir yönetmen adının
    filmlerini ara (yıl±3). Başlık DB'de bulunamasa da gerçek-okunan yönetmenden kimlik kurmaya yarar.
    Tek-token yönetmen GÜVENİLMEZ (yanlış-kilit) → atlanır. Döner: [{imdb_id,name,original,year,cast}]."""
    try:
        if not (kb is not None and getattr(kb, "imdb", None) and director):
            return []
        fold = cc._castfold(director)
        if len(fold.split()) < 2:               # tek-token → güvenilmez, atla
            return []
        rows = None
        for _e in ("trim(regexp_replace(lower(strip_accents(primaryName)),'[^a-z0-9]+',' ','g'))",
                   "trim(regexp_replace(lower(primaryName),'[^a-z0-9]+',' ','g'))"):
            try:
                rows = kb.imdb.execute(f"SELECT nconst FROM names WHERE {_e}=? LIMIT 25", [fold]).fetchall()
                break
            except Exception:                   # noqa: BLE001
                continue
        if not rows:
            return []
        nconsts = list({r[0] for r in rows})
        ph = ",".join(["?"] * len(nconsts))
        trows = kb.imdb.execute(
            f"SELECT DISTINCT tconst FROM principals WHERE nconst IN ({ph}) AND category='director' LIMIT 80",
            nconsts).fetchall()
        out = []
        for (tc,) in trows:
            r = kb.imdb.execute(
                "SELECT primaryTitle,originalTitle,startYear,titleType FROM titles WHERE tconst=?", [tc]).fetchone()
            if not r or r[3] not in ("movie", "tvMovie", "tvSeries", "tvMiniSeries"):
                continue
            if year and r[2]:
                try:
                    if abs(int(r[2]) - int(year)) > 3:    # yıl±3 (TRT katalog kayması payı)
                        continue
                except Exception:                # noqa: BLE001
                    pass
            d, c = kb.imdb_credits(tc)
            out.append({"imdb_id": tc, "name": r[0], "original": r[1], "year": r[2], "director": d, "cast": c})
            if len(out) >= maxc:
                break
        return out
    except Exception:                            # noqa: BLE001
        return []


def _director_anchor_lock(kb, ocr_dirs, ocr_cast, title, original, year):
    """ÇAPA-3 (yönetmen-önce, KONSERVATİF). OCR yönetmeni geçerli-okunduysa KB'de o yönetmenin
    filmlerini ara; BENZERSİZ teyit varsa kilitle. Teyit kademeleri (güçlü→zayıf):
      STRONG: başlık-fold benzersiz  VEYA  cast-overlap≥1 benzersiz  → ONAYLI-uygun
      WEAK:   tek-aday  VEYA  yıl±1-benzersiz                        → kilit+alan-doldur ama KONTROL
    Üretken yönetmende (çok aday, teyit yok) → None (yanlış>boş). Döner {tier,director,cast,imdb_id,name,kanit} | None."""
    try:
        yi = None
        try:
            yi = int(year) if year not in (None, "", "—") else None
        except Exception:                        # noqa: BLE001
            yi = None
        for d in (ocr_dirs or []):
            if not d or not _valid_person_name(d):
                continue
            cands = _films_by_director(kb, d, yi)
            if not cands:
                continue
            scored = []
            for c in cands:
                try:
                    ov = cc.cast_overlap(ocr_cast, c.get("cast") or [])
                except Exception:                # noqa: BLE001
                    ov = 0
                tfold = bool((title and cc.fold(c["name"]) == cc.fold(title))
                             or (original and cc.fold(c["name"]) == cc.fold(original))
                             or (original and c.get("original") and cc.fold(c["original"]) == cc.fold(original)))
                ytight = bool(yi and c.get("year") and abs(int(c["year"]) - yi) <= 1)
                scored.append((c, ov, tfold, ytight))
            title_hits = [s for s in scored if s[2]]
            cast_hits = [s for s in scored if s[1] >= 1]
            ytight_hits = [s for s in scored if s[3]]
            pick, tier = None, None
            if len(title_hits) == 1:
                pick, tier = title_hits[0], "strong"
            elif len(cast_hits) == 1:
                pick, tier = cast_hits[0], "strong"
            elif len(cands) == 1:
                pick, tier = scored[0], "weak"
            elif len(ytight_hits) == 1:
                pick, tier = ytight_hits[0], "weak"
            if pick:
                c = pick[0]
                return {"tier": tier, "director": [d], "cast": c.get("cast") or [],
                        "imdb_id": c.get("imdb_id"), "name": c.get("name"),
                        "kanit": f"yön-çapası[{tier}]: {d} → {c.get('name')} ({c.get('year')}) "
                                 f"tfold={pick[2]} cast_ov={pick[1]} aday={len(cands)}"}
        return None
    except Exception:                            # noqa: BLE001
        return None


# ═══════════════════════════════ ANA GİRİŞ ═══════════════════════════════
YEAR_CUTOFF = 2000          # ≥2000 = güncel (floor 8), öncesi = eski (floor 6)
FLOOR_NEW = 8
FLOOR_OLD = 6
# B-fix-canli 2026-06-29: FILL_TARGET sabit kaldırıldı; satır 745'te _cast_cap() kullanılıyor.
# FLOOR_NEW/FLOOR_OLD DOKUNULMADI — bunlar karar-eşiği (KONTROL/ONAYLI), cast-cap değil.


def _cast_cap():
    # C-fix-canli 2026-06-29: standalone default 8→10 (env zaten 10 geçiyor; bu standalone güvencesi).
    try:
        v = int(os.environ.get("MITAS_CAST_CAP", "10"))
        return v if 1 <= v <= 50 else 10
    except Exception:                      # noqa: BLE001
        return 10


def _strong_external_director_validation(validation, temiz_yon):
    if not isinstance(validation, dict) or not temiz_yon:
        return False
    if validation.get("status") != "DOGRULANDI" or validation.get("confidence") != "KESIN":
        return False
    sources = {str(s).strip().lower() for s in (validation.get("sources_confirm") or []) if str(s).strip()}
    if not ("xml" in sources and ({"imdb", "wiki", "wikidata"} & sources)):
        return False
    if not (validation.get("imdb_id") or validation.get("tmdb_id") or validation.get("wikidata_id")):
        return False
    vals = validation.get("value") or []
    if isinstance(vals, str):
        vals = [vals]
    vals = [str(v).strip() for v in vals if str(v).strip()]
    if not vals:
        return False
    for got in temiz_yon:
        for val in vals:
            if _fold(got) == _fold(val) or cc.name_match(got, val):
                return True
    return False


# Karar tip önceliği (küçük = daha temel; credit_severity_router ile aynı).
_TIP_ONCELIK = {"YONETMEN": 1, "KIMLIK": 2, "CAST": 3, "OZET": 4, "RENDER": 5}


def qc_credit_block(
    ham_yon, ham_cast, ham_yap, *,
    title, original=None, year=None,
    ozet="", afis_yolu=None, xml_roles=None, kb=None,
    raw_context_lines=None, require_producer=False,
    raw_names_groundtruth=None,
    nonlatin_source=False,
    director_validation=None,
):
    """Birleşik künye QC: temizle + OCR-okunan isimleri düzelt + karar ver.

    Döner dict:
      temiz_yon[], temiz_cast[], temiz_yap[], ozet(cased), ozet_kelime, afis_ok,
      karar ∈ {ONAYLI, KONTROL, AUTO-FIX}, kontrol_tip, gerekceler[], hafif[],
      kaynak_izi[], kimlik{locked,method,imdb_id,tmdb_id,verdict,cast_ov,fuzzy_ov},
      floor{hedef, ulasilan, kabul}.
    """
    iz = []                                 # kaynak_izi: her dönüşüm/karar izlenebilir
    gerekceler = []                         # AĞIR sinyaller (→ KONTROL)
    hafif = []                              # HAFİF sinyaller (→ AUTO-FIX)
    try:
        y = int(year) if year not in (None, "", "—") else None
    except Exception:                      # noqa: BLE001
        y = None

    _own_kb = False
    if kb is None:
        try:
            kb = cc.CreditKB()
            _own_kb = True
        except Exception:                  # noqa: BLE001
            kb = None

    try:
        # ── S0: girdi normalize ──
        yon = _split_names(ham_yon)
        cast = _split_names(ham_cast)
        yap = _split_names(ham_yap)

        # ── S1: bağlam filtresi (yalnız ham satır verildiyse; negatif kapı, isim eklemez) ──
        _s1_dropped = []
        _nc_filter_on = (os.environ.get("MITAS_QC_NONCAST_FILTER", "").strip().lower()
                         in ("1", "true", "on", "yes"))
        if raw_context_lines and _nc_filter_on:
            _before_s1 = list(cast)
            cast = filter_cast_by_raw_context(cast, raw_context_lines)
            _kept_s1 = {_fold(n) for n in cast}
            _s1_dropped = [n for n in _before_s1 if _fold(n) not in _kept_s1]
        elif raw_context_lines:
            cast = filter_cast_by_raw_context(cast, raw_context_lines)

        # ── S2: SCRIPT-DETECT + TRANSLİT (garble'dan ÖNCE — Kiril garble sanılmasın) ──
        translit_failed = False

        def _translit_list(names, alan):
            nonlocal translit_failed
            out = []
            for nm in names:
                sc = detect_script(nm)
                if sc == "latin":
                    out.append(_asciify_foreign(nm))     # yabancı-aksan → ASCII (Türkçe korunur)
                    continue
                latin, yontem = transliterate(nm, sc)
                iz.append({"alan": alan, "ham": nm, "cikti": latin, "script": sc, "yontem": yontem})
                if yontem == "FAILED":
                    translit_failed = True
                    out.append(nm)          # KB-öncelik S4/S5'te deneyecek; çözülmezse RENDER/KONTROL
                else:
                    out.append(_asciify_foreign(latin))  # translit Latin + yabancı-aksan → ASCII
            return out

        yon = _translit_list(yon, "yonetmen")
        cast = _translit_list(cast, "oyuncu")
        yap = _translit_list(yap, "yapimci")

        # OCR-OTORİTE temeli: bu noktadaki cast = OCR otoritesi (translit sonrası). k dondurulur.
        ocr_cast = list(cast)
        k = len(ocr_cast)

        # ── S3: KİMLİK KİLİDİ ──
        # PERF + DOĞRULUK: kimlik-eşleştirmeye yalnız MAKUL KİŞİ-isimleri gönder (kurum/çöp/>4-token
        # crosscheck.cast_find'i 98M-satır principals'ta gereksiz yavaşlatır + yanlış-eşleşme riski).
        # Çıktı temizliği (S5/S6/S7) YİNE TÜM cast üzerinde kalır — bu yalnız kimlik-kapısı girdisi.
        id_cast = (_only_persons(cast) or cast)[:12]
        verdict, cast_ov, fuzzy_ov = None, 0, 0
        otoriter_yon, otoriter_cast = [], []
        imdb_id = tmdb_id = method = None
        if kb is not None:
            try:
                cross = kb.crosscheck(yon[0] if yon else "", id_cast,
                                      title_tr=title, original=original, year=y)
                verdict = cross.get("verdict")
                cast_ov = int(cross.get("cast_ortusme", 0) or 0)
                otoriter_yon = list(cross.get("otoriter_yonetmen") or [])
                otoriter_cast = list(cross.get("otoriter_cast") or [])
                imdb_id = cross.get("matched_imdb_id")
                tmdb_id = cross.get("wikidata_tmdb_id")
                if otoriter_cast:
                    try:
                        fuzzy_ov = cc.cast_overlap_fuzzy(id_cast, otoriter_cast)
                    except Exception:      # noqa: BLE001
                        fuzzy_ov = 0
            except Exception as _e:        # noqa: BLE001
                iz.append({"adim": "crosscheck", "hata": str(_e)})

        locked = (verdict == "TEYİT") or (cast_ov >= 2) or (fuzzy_ov >= 2)

        # ── S3b: web/köprü çapası (kimlik kurulamazsa) ──
        if not locked and _qg is not None and kb is not None:
            try:
                web = _qg.web_identity(title, original, y,
                                       ocr_director=(yon[0] if yon else None),
                                       summary=None, kb=kb)
                if web.get("locked"):
                    method = web.get("method")
                    web_dir = list(web.get("director") or [])
                    web_cast = list(web.get("cast") or [])
                    otoriter_yon = otoriter_yon or web_dir
                    otoriter_cast = otoriter_cast or web_cast
                    imdb_id = imdb_id or web.get("imdb_id")
                    tmdb_id = tmdb_id or web.get("tmdb_id")
                    locked = True
                    iz.append({"adim": "web_identity", "method": method,
                               "kaynak_izi": web.get("kaynak_izi")})
            except Exception as _e:        # noqa: BLE001
                iz.append({"adim": "web_identity", "hata": str(_e)})

        # ── S3b-2: YÖNETMEN-ÖNCE ÇAPASI (ÇAPA-3, Çağatay 2026-06-20) — kilit-oranı kaldıracı ──
        # web başlık-araması patlasa da (TR başlık DB'de yok), OCR yönetmeni TEMİZ okunduysa KB'de o
        # yönetmenin filmlerini ara + BENZERSİZ teyitle kilitle (Robert Duvall→Angelo, Woody Allen→Akrebin
        # Laneti). tier=weak (tek-aday/yıl±1) → KONTROL'de kalır ama alanlar dolar; tier=strong → ONAYLI-uygun.
        # PERF NOTU: director-anchor kilitsiz-film başına indekssiz principals(98M) sorgusu yapar
        # → büyük batch'te yavaş olabilir. MITAS_QC_DIRECTOR_ANCHOR=0 ile kapatılır (default AÇIK).
        _da_on = os.environ.get("MITAS_QC_DIRECTOR_ANCHOR", "1").strip().lower() not in ("0", "false", "off", "no")
        _da_tier = None
        if not locked and kb is not None and _da_on:
            try:
                _da = _director_anchor_lock(kb, yon, id_cast, title, original, y)
                if _da:
                    otoriter_yon = otoriter_yon or _da["director"]
                    otoriter_cast = otoriter_cast or (_da.get("cast") or [])
                    imdb_id = imdb_id or _da.get("imdb_id")
                    _da_tier = _da["tier"]
                    method = method or ("director-anchor" if _da_tier == "strong" else "director-anchor-weak")
                    locked = True
                    iz.append({"adim": "director_anchor", "tier": _da_tier, "kanit": _da["kanit"]})
            except Exception as _e:        # noqa: BLE001
                iz.append({"adim": "director_anchor", "hata": str(_e)})

        # ── S3c: KİLİT-VAR-YÖNETMEN-BOŞ KURTARMASI (Çağatay 2026-06-20) ──
        # Kimlik kilitlendi (cast-örtüşme) ama KB yönetmeni BOŞ gelebilir: wikidata eşleşmesi yönetmen-QID
        # çözememiş YA DA cast_find imdb-cast eşleşmesi yönetmen döndürmemiş olabilir. Eşleşen imdb_id'den
        # ikincil yönetmen-çek → "kilit var ama yön boş → KONTROL/YONETMEN" yakın-kurtarma boşluğunu kapatır.
        if locked and not otoriter_yon and imdb_id and kb is not None and hasattr(kb, "imdb_credits"):
            try:
                _dirs2, _ = kb.imdb_credits(imdb_id)
                if _dirs2:
                    otoriter_yon = list(_dirs2)
                    iz.append({"adim": "yon_kurtarma", "kaynak": "imdb_credits(imdb_id)",
                               "imdb_id": imdb_id, "yon": otoriter_yon[:3]})
            except Exception as _e:        # noqa: BLE001
                iz.append({"adim": "yon_kurtarma", "hata": str(_e)})

        # ── S1-readd: MITAS_QC_NONCAST_FILTER ile düşürülen ama KB-teyitli oyuncuları geri al ──
        if _s1_dropped and otoriter_cast:
            _readd = [n for n in _s1_dropped
                      if any(cc.name_match(n, a) or cc.name_close(n, a) for a in otoriter_cast)]
            if _readd:
                _have = {_fold(n) for n in cast}
                cast = [n for n in _readd if _fold(n) not in _have] + cast
                iz.append({"alan": "oyuncu", "kaynak": "s1-readd-kb-confirmed", "isim": _readd})

        # DEFERANS bayrağı (2026-06-28): yön/yapımcı KB-fill'i deferans açıkken atlanır (default-ON).
        # 2f4a2b53 deferans fix'inin DELİĞİ: credit_qc_block KB-fill'i MITAS_CREDIT_DEFERENCE'i
        # tanımıyordu → deferansla boş bırakılan yönetmen/yapımcıyı KB'den EZİYORDU. Burada da kapanır.
        _deference_on = os.environ.get("MITAS_CREDIT_DEFERENCE", "1").strip().lower() \
            not in ("0", "false", "off", "no")
        # ── S4: YÖNETMEN (OCR-otorite + KIRMIZI ÇİZGİ; ÇELİŞKİ→KONTROL, KB-değiştir YOK) ──
        yon_conflict = False
        if yon and locked and otoriter_yon:
            yeni = []
            for d in yon:
                m = (next((a for a in otoriter_yon if cc.name_match(d, a)), None)
                     or next((a for a in otoriter_yon if cc.name_close(d, a)), None))
                if m and m not in yeni:
                    yeni.append(m)
            if yeni:
                yon = yeni                  # KB-kanonik yazım (aynı kişi)
            else:
                # B-fix (2026-06-29): OCR yön KB ile eşleşmedi. AYIR — GARBLE ise at (kural: okunamadı>yanlış);
                # TEMİZ ise OCR-otorite KORU (KB yanlış-film eşleştirmiş olabilir; CHARLIE MARTINEZ/TERRY GEORGE
                # net OCR ama KB-teyitsiz). yon_conflict=True kalır → route KONTROL'e yollar (yön PDF'de + insan teyidi).
                _clean_yon = [d for d in yon if _looks_garble(d) is None]
                yon = _clean_yon            # temiz olanları KORU; garble elendi (eski: hepsi silinirdi)
                yon_conflict = True
        elif (not yon) and locked and otoriter_yon:
            # DEFERANS: yönetmen KB-fill YAPILMAZ (yön yalnız doğrulanmış yapısal hattan; OCR boşsa BOŞ).
            # Eski davranış (MITAS_CREDIT_DEFERENCE=0): kimlik-kilitliyse KB'den doldur.
            if _deference_on:
                iz.append({"alan": "yonetmen", "kaynak": "deferans: KB-fill atlandı (OCR boş)",
                           "aday": otoriter_yon[0]})
            else:
                yon = [otoriter_yon[0]]     # OCR boş + kimlik kilitli → KB-fill (destek)
                iz.append({"alan": "yonetmen", "kaynak": "kb-fill(kimlik-kilitli)", "isim": yon[0]})
        # else: OCR var + (kilit yok/KB yok) → OCR AYNEN

        if method == "director-anchor-weak" and _strong_external_director_validation(director_validation, yon):
            _validated_imdb_id = (director_validation or {}).get("imdb_id") or None
            _validated_tmdb_id = (director_validation or {}).get("tmdb_id") or tmdb_id
            if _validated_imdb_id and imdb_id and imdb_id != _validated_imdb_id:
                otoriter_cast = []
            method = "director-validated"
            imdb_id = _validated_imdb_id or imdb_id
            tmdb_id = _validated_tmdb_id
            iz.append({"adim": "director_validation",
                       "kaynak": "credit_validate",
                       "sources": (director_validation or {}).get("sources_confirm") or [],
                       "yon": _upper_names(yon)[:3],
                       "imdb_id": imdb_id})

        # ── S5: CAST yazım-düzeltme (OCR-otorite; eşleşen → KB-kanonik/KB-latin, eşleşmeyen → OCR) ──
        # GÖZLEM (FIX-D, 2026-06-23): fuzzy-only ezmeleri (se=None ama es=name_close/window) kaydedilir;
        # karar/davranış DEĞİŞMEZ — yalnız _s5_form_snaps biriktirir (otorite_audit.s5_form_overwrites).
        _s5_form_snaps = []
        if otoriter_cast:
            _form_keep = (os.environ.get("MITAS_OCR_FORM_KEEP", "").strip().lower()
                          in ("1", "true", "on", "yes"))
            duz = []
            for nm in cast:
                se = next((a for a in otoriter_cast if cc.name_match(nm, a)), None)
                es = se or next((a for a in otoriter_cast if cc.name_close(nm, a)), None)
                if not es and locked:
                    es = next((a for a in otoriter_cast if cc.name_close_window(nm, a)), None)
                # FUZZY-ONLY EZME: sıkı eşleşme yok (se=None) ama fuzzy var (es) ve es≠nm → OCR-formu
                # KB-formuyla değişti. GÖZLEM sinyali (LEFEBVRE→LEFEVRE). _form_keep kapalıyken gerçekten
                # ezilir; açıkken OCR korunur — her iki durumda da divergence ADAYI kaydedilir.
                if es is not None and se is None and _fold(es) != _fold(nm):
                    _s5_form_snaps.append({"ocr": nm, "kb": es})
                if _form_keep and es is not None and se is None:
                    duz.append(nm)
                else:
                    duz.append(es if es else nm)
            cast = duz

        # ── S6: GARBLE / ÇÖP ELEME (translit sonrası) ──
        _ocr_keep_on = (raw_names_groundtruth and os.environ.get(
            "MITAS_CAST_OCR_KEEP", "").strip().lower() in ("1", "true", "on", "yes"))
        _exempt = set()
        if _ocr_keep_on:
            _rseq6 = _audit_raw_token_seq(raw_names_groundtruth)
            for nm in cast:
                if (nm and _audit_name_in_raw(nm, _rseq6)
                        and _valid_person_name(nm) and not _looks_garble(nm)):
                    _exempt.add(_fold(nm))
        _pre_s6 = list(cast)
        cast = _apply_garble_gate(cast, kb=kb)
        cast = _only_persons(cast)
        if _exempt:
            _kept_fold = {_fold(n) for n in cast}
            for nm in _pre_s6:
                if _fold(nm) in _exempt and _fold(nm) not in _kept_fold:
                    cast.append(nm)
                    _kept_fold.add(_fold(nm))
        cast_garble_residual = [n for n in cast if _looks_garble(n)]

        # ── S7: KB sıfırdan cast eklemez ──
        # Bu aşamada cast yalnız OCR'da okunan isimlerin temizlenmiş/yazımı düzeltilmiş halidir.
        # KB'de olup OCR'da olmayan kişi artık floor-fill ile eklenmez.
        cast = cast[:_cast_cap()]

        floor_hedef = FLOOR_NEW if (y is not None and y >= YEAR_CUTOFF) else FLOOR_OLD
        ulasilan = len(cast)
        floor_kabul = ulasilan > 0                        # KB ile floor tamamlama yok; sadece boş-cast ağırdır

        # ── S8: YAPIMCI (OCR-otorite + kişi-only + KB-tamamla max 3) ──
        yap = _apply_garble_gate_yapimci(yap)
        yap = _only_persons(yap)[:3]
        _prod_strongid = (os.environ.get("MITAS_QC_PRODUCER_STRONGID", "1").strip().lower()
                          not in ("0", "false", "off", "no"))
        _id_strong = (verdict == "TEYİT") or (cast_ov >= 3)
        # DEFERANS (2026-06-28): yapımcı KB-tamamlama deferans açıkken YAPILMAZ (yapımcı yalnız
        # doğrulanmış yapısal hattan; OCR yetersizse eksik kalır). Eski davranış: MITAS_CREDIT_DEFERENCE=0.
        if locked and (_id_strong or not _prod_strongid) and len(yap) < 3 and imdb_id and not _deference_on:
            _fuzdedup = (os.environ.get("MITAS_QC_FUZZY_DEDUP", "").strip().lower()
                        in ("1", "true", "on", "yes"))
            kb_yap = _kb_producers(kb, imdb_id, limit=3)
            have_y = {_fold(n) for n in yap}
            for a in _only_persons(kb_yap):
                if len(yap) >= 3:
                    break
                # OCR-otorite: KB varyantı mevcut OCR yapımcısının YAKIN-yazımıysa (HAZLETON↔HAZELTON)
                # EKLEME — OCR'ın yazımı korunur, çift-kayıt önlenir (flag MITAS_QC_FUZZY_DEDUP).
                # Flag kapalı → yalnız name_match (mevcut davranış AYNEN).
                _dup = any(cc.name_match(a, o) or (_fuzdedup and cc.name_close(a, o)) for o in yap)
                if _fold(a) not in have_y and not _dup:
                    yap.append(a)
                    have_y.add(_fold(a))
                    iz.append({"alan": "yapimci", "kaynak": "kb-tamamla", "isim": a})

        # ── S9: CASING + İ politikası ──
        ham_isimler = list(cast) + list(yon) + list(yap)   # tr_upper_prose isim-farkındalığı için
        temiz_cast = _upper_names(cast)
        temiz_yon = _upper_names(yon)
        temiz_yap = _upper_names(yap)
        # ── S10: ÖZET + AFİŞ kapıları ──
        cased_ozet, ozet_kelime = _ozet_gate(ozet, ham_isimler)
        afis_ok = poster_ok(afis_yolu)

        # ── S11: KARAR MATRİSİ ──
        def _ekle(tip, neden):
            gerekceler.append({"tip": tip, "neden": neden})

        if not locked:
            _ekle("KIMLIK", "kimlik kurulamadı (cast-örtüşme<2, web çapası kilitlenemedi)")
        elif method == "tmdb":
            _ekle("KIMLIK", "versiyon cast-teyitsiz (web title+year kilidi — insan onayı)")
        elif method == "director-anchor-weak":
            _ekle("KIMLIK", "yönetmen-çapası zayıf-teyit (tek-aday/yıl±1 — insan onayı)")

        if yon_conflict:
            _ekle("YONETMEN", "OCR yönetmeni KB ile çelişti (kimlik çapası — KB ile ezilmedi)")
        elif not temiz_yon:
            _ekle("YONETMEN", "yönetmen okunamadı (KB-fill yok)")
        elif len(temiz_yon) > 2:
            _ekle("YONETMEN", f"yönetmen listesi şüpheli ({len(temiz_yon)} isim — crew karışması)")
        elif any(len(str(d)) > 45 for d in temiz_yon):
            _ekle("YONETMEN", "yönetmen adı şüpheli (>45 karakter — cümle karışması)")

        if ulasilan == 0:
            _ekle("CAST", "oyuncu yok")
        if cast_garble_residual:
            _ekle("CAST", f"cast garble kalıntısı ({', '.join(cast_garble_residual[:3])})")

        if require_producer and not temiz_yap:
            _ekle("CAST", "yapımcı yok (require_producer)")

        if ozet_kelime < 20:
            _ekle("OZET", f"özet yok/kısa ({ozet_kelime} kelime / placeholder)")

        if translit_failed and any(detect_script(n) != "latin" for n in (cast + yon + yap)):
            _ekle("RENDER", "Latin-dışı alfabe çevrilemedi (KB-Latin yok, kütüphane yok)")
        # LATIN-DIŞI KAYNAK (2026-06-22, NAMUS DÜŞMANI): extractor erken-translit yaptı (Arap/Kiril/Yunan→
        # Latin). Rough romanizasyon (özellikle Arapça unidecode) OTORİTE DEĞİL → asla auto-ONAYLI; insan
        # teyidi şart. İsim artık Latin olduğundan yukarıdaki translit_failed gate bunu yakalamaz; ayrı kapı.
        if nonlatin_source:
            _ekle("RENDER", "Latin-dışı kaynak (erken-translit) → romanizasyon insan teyidi gerek")

        if not afis_ok:
            hafif.append({"tip": "AFIS", "neden": "afiş yok / yatay frame-grab → poster_fetch yeniden"})

        # fix3-A 2026-06-29 — CAST_CAP_DUSEN: cap doluysa (>=cap) ham-OCR'da temiz okunan isimler
        # düşmüş olabilir → hafif sinyal (görünürlük). cap=10 DEĞİŞMEZ. fail-safe: raw_names_groundtruth
        # None ise atla. Bu blok S11 karar matrisinden ÖNCE → hafif[] S11'e katılır.
        try:
            if raw_names_groundtruth and len(cast) >= _cast_cap():
                _rseq_cap = _audit_raw_token_seq(raw_names_groundtruth)
                _final_fold_cap = {_fold(n) for n in cast}
                _cap_dropped = []
                for _ri in range(len(_rseq_cap) - 1):
                    _cand_t = _rseq_cap[_ri: _ri + 2]
                    _cand_n = " ".join(t.title() for t in _cand_t)
                    if (_fold(_cand_n) not in _final_fold_cap
                            and _valid_person_name(_cand_n)
                            and _looks_garble(_cand_n) is None):
                        _cap_dropped.append(_cand_n)
                if _cap_dropped:
                    _cap_seen = set()
                    _cap_dropped_u = []
                    for _cn in _cap_dropped:
                        _cf = _fold(_cn)
                        if _cf not in _cap_seen:
                            _cap_seen.add(_cf)
                            _cap_dropped_u.append(_cn)
                    hafif.append({"tip": "CAST",
                                  "neden": f"CAST_CAP_DUSEN: cap-ustu okunan {len(_cap_dropped_u)} "
                                           f"oyuncu dustu ({', '.join(_cap_dropped_u[:3])})"})
        except Exception:  # noqa: BLE001 — sinyal hatası karar/route'u ASLA bozmaz
            pass

        # karar + en temel tip
        if gerekceler:
            karar = "KONTROL"
            kontrol_tip = sorted(gerekceler, key=lambda g: _TIP_ONCELIK.get(g["tip"], 9))[0]["tip"]
        elif hafif:
            karar = "AUTO-FIX"
            kontrol_tip = hafif[0]["tip"]
        else:
            karar = "ONAYLI"
            kontrol_tip = None

        # ── S12: OCR-OTORİTE DENETİM (flag MITAS_QC_OTORITE_AUDIT; SIFIR-ROUTE, yalnız rapor) ──
        # Karar/route YUKARIDA verildi; bu blok onu ETKİLEMEZ (_ekle çağrılmaz). Yalnız sinyal üretir.
        otorite_audit = None
        # FIX-D (2026-06-23): PDF-render-audit (S5 form ezme) GÖZLEM bayrağı — default AKTIF (route ETMEZ).
        # MITAS_QC_OTORITE_AUDIT VEYA MITAS_PDF_RENDER_AUDIT açıksa audit hesaplanır.
        _pdf_audit_on = (os.environ.get("MITAS_PDF_RENDER_AUDIT", "1").strip().lower()
                         not in ("0", "false", "off", "no"))
        _audit_on = (os.environ.get("MITAS_QC_OTORITE_AUDIT", "").strip().lower()
                     in ("1", "true", "on", "yes")) or _pdf_audit_on
        if _audit_on:
            try:
                otorite_audit = _compute_otorite_audit(
                    raw_names_groundtruth, temiz_cast, temiz_yap, otoriter_cast, iz,
                    s5_form_snaps=_s5_form_snaps)
            except Exception:              # noqa: BLE001 — sinyal hatası karar/route'u ASLA bozmaz
                otorite_audit = {"hata": True}

        # ── S12b RESCUE (2026-07-07, UTANMAZ ADAM/Türkan Şoray): ocr_dropped'dan KB/GT-teyitli
        # düşen isim cast'e geri. ocr_dropped = HEM ham-OCR'da okunmuş HEM KB-cast'te gerçek AMA
        # final'de olmayan (audit'te çift-teyitli). Kimlik-kilitli iken güvenli; OCR isim-parçalama
        # (ör. ters/ayrık 'SORAY / TÜRKAN') yüzünden birleşemeyen gerçek oyuncuyu kurtarır.
        _rescue_on = (os.environ.get("MITAS_CAST_RESCUE_DROPPED", "1").strip().lower()
                      not in ("0", "false", "off", "no"))
        if (_rescue_on and locked and isinstance(otorite_audit, dict)
                and otorite_audit.get("ocr_dropped")):
            _rhave = {_fold(n) for n in temiz_cast}
            for _dn in (otorite_audit.get("ocr_dropped") or []):
                if _dn and _fold(_dn) not in _rhave:
                    temiz_cast.append(_upper_names([_dn])[0])
                    _rhave.add(_fold(_dn))
                    iz.append({"alan": "oyuncu", "kaynak": "rescue-ocr_dropped", "isim": _dn})

        return {
            "temiz_yon": temiz_yon, "temiz_cast": temiz_cast, "temiz_yap": temiz_yap,
            "ozet": cased_ozet, "ozet_kelime": ozet_kelime, "afis_ok": afis_ok,
            "karar": karar, "kontrol_tip": kontrol_tip,
            "gerekceler": [g["neden"] for g in gerekceler], "gerekce_tipleri": gerekceler,
            "hafif": hafif, "kaynak_izi": iz,
            "kimlik": {"locked": locked, "method": method, "imdb_id": imdb_id,
                       "tmdb_id": tmdb_id, "verdict": verdict,
                       "cast_ov": cast_ov, "fuzzy_ov": fuzzy_ov},
            "floor": {"hedef": floor_hedef, "ulasilan": ulasilan, "kabul": floor_kabul},
            "ocr_cast_k": k,
            # KB-otoriter (gerçek) değerler — yanlış-okuma analizi için (OCR ↔ gerçek karşılaştırma)
            "otoriter_yon": otoriter_yon, "otoriter_cast": otoriter_cast,
            # OCR-OTORİTE DENETİM (flag MITAS_QC_OTORITE_AUDIT; flag kapalıyken None) — SIFIR-ROUTE
            "otorite_audit": otorite_audit,
        }
    finally:
        if _own_kb and kb is not None:
            try:
                kb.close()
            except Exception:              # noqa: BLE001
                pass


# ───────────────────────── CLI (tek-film deneme) ─────────────────────────
def main():
    import argparse, json
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="credit_qc_block tek-film deneme")
    ap.add_argument("--baslik", required=True)
    ap.add_argument("--orijinal", default=None)
    ap.add_argument("--yil", default=None)
    ap.add_argument("--yonetmen", default="")
    ap.add_argument("--cast", default="", help="virgülle")
    ap.add_argument("--yapimci", default="")
    ap.add_argument("--ozet", default="")
    ap.add_argument("--afis", default=None)
    a = ap.parse_args()
    r = qc_credit_block(
        [x for x in a.yonetmen.split(",") if x.strip()],
        [x for x in a.cast.split(",") if x.strip()],
        [x for x in a.yapimci.split(",") if x.strip()],
        title=a.baslik, original=a.orijinal, year=a.yil, ozet=a.ozet, afis_yolu=a.afis,
    )
    print(json.dumps(r, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
