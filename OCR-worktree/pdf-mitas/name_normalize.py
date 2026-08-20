# -*- coding: utf-8 -*-
"""MITAS — isim karakter normalizasyonu (Türkçe koru / diğer dil ASCII).

KURAL (Çağatay, 2026-06-02):
  • Türkçe isimler  →  ç ğ ı İ ö ş ü KORUNUR.
  • Diğer diller    →  ASCII (aksanlar düşürülür: é→e, ñ→n, ø→o, ü(Almanca)→u ...).

Türkçe-mi kararı:
  1) Heuristik: ı/İ/ş/ğ içeriyorsa → Türkçe (kesin).  Yabancı aksan (é,ñ,ø,ä...) → değil.
     Saf ASCII → zaten değişmez (karar gereksiz).
  2) SADECE ç/ö/ü içeren isim BELİRSİZ (Türkçe de Almanca/Fransızca da olabilir) →
     "gerekirse" QWEN'e sorulur (Ollama). Qwen yoksa güvenli taraf = ASCII.

Kullanan: scripts/_pipe_pdf.py + py/20260601_kunye_to_pdf.py (cast + crew isimleri).
"""
from __future__ import annotations
import json
import os
import re
import sys
import tempfile
import unicodedata
import urllib.request

_SPECIAL = {
    "ø": "o", "Ø": "O", "ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "þ": "th", "Þ": "Th",
    "ß": "ss", "æ": "ae", "Æ": "Ae", "œ": "oe", "Œ": "Oe", "ð": "d", "Ð": "D",
    # Azerice schwa — NFKD ile decompose olmaz, açık çeviri şart (U+018F / U+0259)
    "Ə": "E", "ə": "e",
}
_TR_STRONG = set("ışğİıŞĞ")       # ı, ş, ğ, İ — güçlü Türkçe sinyali
_TR_STRONG_REAL = set("ışğıŞĞ")   # sentetik i->İ kirlenmesiyle oluşmayan güçlü Türkçe sinyali
_TR_AMBIG = set("çöüÇÖÜ")          # ç, ö, ü — Türkçe VEYA Almanca/Fransızca (belirsiz)

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
QWEN_MODEL = "qwen3:8b"            # hızlı metin modeli (ollama list'te mevcut)


def ascii_fold(s: str, *, yok_etme_koru: bool = True) -> str:
    """Aksanları düşürerek ASCII'ye indir (Türkçe dahil tüm özel harfler).

    YOK-ETME KORUMASI (2026-08-01, konsey turu KANITLI bulgusu): Latin-dışı
    yazılar (Kiril/Yunan/Arap/CJK) NFKD ile ASCII'ye ÇÖZÜLMEZ → tamamen SİLİNİR.
    Ölçüldü: upper_names(['ФЁДОР БОНДАРЧУК']) → [' '] — PDF'te BOŞ satır, işaret
    bile yok. Bu, Çağatay'ın "isim atlamayalım" kuralının en net ihlali; isim
    sessizce yok oluyor ve kimse görmüyor.
    ÇÖZÜM: fold sonucu anlamlı harf bırakmıyorsa ORİJİNALİ döndür. Latin-dışı
    kaynak filmler ZATEN nonlatin_source ile KONTROL'e gidiyor → insan Kiril
    ismi görür ve romanize eder. Görünen yabancı harf, görünmeyen boşluktan iyidir.
    yok_etme_koru=False ile eski davranış (eşleştirme/fold-anahtarı çağrıları için).
    """
    ham = s
    out = []
    for ch in s:
        if ch in _SPECIAL:
            out.append(_SPECIAL[ch])
            continue
        dec = "".join(c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c))
        out.append(dec if dec.isascii() else "")
    sonuc = "".join(out)
    if yok_etme_koru and (ham or "").strip():
        if not any(c.isalnum() for c in sonuc) and any(c.isalpha() for c in ham):
            return ham          # fold ismi YOK ETTİ → orijinali koru (insan görsün)
    return sonuc


# Türkçe harfleri ASCII karşılığına AÇIKÇA çevir (NFKD 'ı'yı SİLER → "Tarık"→"TARK"≠DB;
# bu eşleme ile "Tarık"→"TARIK" DB'deki ascii_name/strip_accents(name) ile eşleşir).
# Desen scripts/credit_crosscheck.py:31-44 (_tfold/_sqlfold) ile AYNI — DB-eşleştirme anahtarı.
_TR_FOLD_MAP = (("İ", "i"), ("I", "i"), ("ı", "i"), ("Ş", "s"), ("ş", "s"), ("Ğ", "g"), ("ğ", "g"),
                ("Ü", "u"), ("ü", "u"), ("Ö", "o"), ("ö", "o"), ("Ç", "c"), ("ç", "c"))


def _tr_fold_key(s: str) -> str:
    """DB-eşleştirme anahtarı: Türkçe harf→ASCII (ı→i…) ÖNCE, sonra accent-strip, UPPER.
    Sonuç DuckDB tarafı UPPER(strip_accents(...)) ile eşleşir ('TARIK AKAN')."""
    s = s or ""
    for a, b in _TR_FOLD_MAP:
        s = s.replace(a, b)
    dec = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return dec.upper().strip()


def _sql_tr_fold(col: str) -> str:
    """col için SQL Türkçe-fold ifadesi (REPLACE zinciri + strip_accents + UPPER) —
    _tr_fold_key ile EŞLEŞİR (DuckDB UPPER sürüm-farkı riskini ortadan kaldırır)."""
    e = col
    for a, b in _TR_FOLD_MAP:
        e = f"replace({e},'{a}','{b}')"
    return f"UPPER(strip_accents({e}))"


def classify(name: str) -> str:
    """'tr' (Türkçe, koru) | 'ascii' (yabancı, indir) | 'ask' (belirsiz → Qwen) | 'keep' (saf ASCII)."""
    if any(c in _TR_STRONG for c in name):
        return "tr"
    has_ambig = False
    for ch in name:
        if ch in _TR_AMBIG:
            has_ambig = True
        elif not ch.isascii() and unicodedata.category(ch).startswith("L"):
            return "ascii"  # yabancı aksan (é, ñ, ø, ä...) → kesin yabancı
    return "ask" if has_ambig else "keep"


def qwen_is_turkish(names: list[str], model: str = QWEN_MODEL, timeout: int = 60) -> dict[str, bool]:
    """Belirsiz isimleri Qwen'e (Ollama) sor. {isim: True/False}. Hata/yoksa boş döner."""
    names = [n for n in names if n]
    if not names:
        return {}
    listing = "\n".join(f"- {n}" for n in names)
    prompt = (
        "Görev: Aşağıdaki kişi isimlerinin her biri TÜRKÇE bir isim mi (bir Türk'ün ismi) "
        "yoksa yabancı bir isim mi? Sadece geçerli JSON döndür, açıklama yok. "
        'Biçim: {"İsim Soyisim": true, ...}  (true=Türkçe, false=yabancı). /no_think\n\n' + listing
    )
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0, "num_predict": 512},
    }).encode("utf-8")
    try:
        req = urllib.request.Request(OLLAMA_URL, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.loads(r.read())
        content = (resp.get("message") or {}).get("content", "")
        data = json.loads(content)
        # anahtar eşleşmesini gevşet (fold)
        norm = {_fold(k): bool(v) for k, v in data.items()}
        return {n: norm.get(_fold(n), False) for n in names if _fold(n) in norm}
    except Exception:  # noqa: BLE001 - Qwen yoksa sessiz geç
        return {}


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", (s or "").casefold()) if not unicodedata.combining(c)).strip()


def normalize_names(names, *, use_qwen: bool = True) -> list[str]:
    """İsim listesini kurala göre normalize et. Belirsizleri (sadece ç/ö/ü) Qwen'e sorar."""
    if not names:
        return names
    verdict: dict[str, str] = {n: classify(n) for n in names}
    ask = [n for n, v in verdict.items() if v == "ask"]
    qmap: dict[str, bool] = {}
    if ask and use_qwen:
        qmap = qwen_is_turkish(ask)
    out = []
    for n in names:
        v = verdict[n]
        if v == "tr" or v == "keep":
            out.append(n)                                   # Türkçe ya da saf ASCII → koru
        elif v == "ascii":
            out.append(ascii_fold(n))                       # yabancı aksan → ASCII
        else:  # 'ask'
            is_tr = qmap.get(n, False)                      # Qwen dönmediyse güvenli = yabancı
            out.append(n if is_tr else ascii_fold(n))
    return out


def normalize_crew(crew, *, use_qwen: bool = True):
    """crew = [(rol, [isim...])] → isimleri normalize et, rol etiketleri Türkçe sabit kalır."""
    flat = [nm for _, names in crew for nm in (names if isinstance(names, list) else [names])]
    mapping = dict(zip([_fold(x) for x in flat], normalize_names(flat, use_qwen=use_qwen)))
    out = []
    for role, names in crew:
        nl = names if isinstance(names, list) else [names]
        out.append((role, [mapping.get(_fold(x), x) for x in nl]))
    return out


def tr_upper(s: str) -> str:
    """Turkce buyuk harf: i->İ, ı->I; digerleri standart upper (ş->Ş, ç->Ç, ğ->Ğ...).
    Latin-disi ozel harfler (Ə, ø, ł...) Latin'e cevrilir; Turkce harfler _SPECIAL'da yok -> korunur.
    Latin-disi ALFABE harfleri (Kiril/Yunan/Arap/CJK...) ELENIR — kunye yalniz Latin/Turkce (kural B:
    'baska bir dil alfabeyle cikti gelmeyecek'); ozellikle ozet prozasina yabanci-alfabe sizmasini onler."""
    s = s or ""
    if any(ch in _SPECIAL for ch in s):
        s = "".join(_SPECIAL.get(ch, ch) for ch in s)   # Ə->E vb. (isim Ş icerip Turkce sanilsa bile)
    # Latin-disi harf (Kiril/Yunan/Arap/CJK...) sizintisini ele; ASCII + Latin/Turkce harfler ve
    # harf-disi (bosluk, rakam, noktalama) korunur. Cevrilemeyen alfabe DUSER (translit degil, drop).
    s = "".join(ch for ch in s
                if ch.isascii()
                or unicodedata.category(ch)[0] != "L"
                or "LATIN" in unicodedata.name(ch, ""))
    return s.replace("ı", "I").replace("i", "İ").upper()


def _turkish_name_set(names) -> tuple[bool, set]:
    """names icinden TURK olanlari OTORITER belirle (duckDB mitas_people_index, countries Q43/Q23681).
    DeepSeek YOK (sadece duckDB sorgusu). Doner (db_calisti, {turk_isim...}).
    duckDB yoksa (False, {}) -> cagiran _is_tr_name heuristigine duser. 'Julia McKenzie'/'Eric Roberts'
    -> Wikidata'da Turk DEGIL -> yabanci; 'Şener Şen' -> Q43 -> Turk. (_is_tr_name gevsek seti bunlari
    yanlis Turk sayiyordu: JULIA ad-setinde, MCKENZIE soyad-setinde tesadufen var.)"""
    try:
        db_ok, tr_map = _mitas_people_set([n for n in names if n])
        if db_ok:
            return True, set(tr_map.keys())
    except Exception:  # noqa: BLE001
        pass
    return False, set()


_TR_HARF = "çğıİöşüÇĞıİÖŞÜ"
# Cumle BASI sayilan noktalama: bu isaretten sonraki ilk sozcuk buyuk harfle baslar
# ve ozel ad OLMAYABILIR ("Film ... ." -> FİLM dogru), o yuzden aday sayilmaz.
_CUMLE_BASI = re.compile(r"(?:^|[.!?:;]\s+|\n\s*)$")


def _ozel_ad_repl(ham: str) -> dict:
    """HAM (buyutulmemis) prose'da cumle ORTASINDAKI saf-ASCII ozel adlari bul.

    Donen: {tr_upper(tok): ascii_upper(tok)} — yalniz ikisi FARKLI olanlar, yani
    icinde 'i' bulunan yabanci adlar (Emily -> EMİLY/EMILY). 'Rudy' gibi i-siz
    adlar iki yolda da ayni cikar, sozluge girmez.
    Turkce harf tasiyan ozel ad (İstanbul, Şener) ATLANIR — Turkce buyutme dogrudur.
    """
    out: dict[str, str] = {}
    if not ham or os.environ.get("MITAS_PROSE_OZEL_AD", "1").strip().lower() in ("0", "false", "off"):
        return out
    for m in re.finditer(r"[A-Za-zÇĞİıŞÖÜçğşöü]+", ham):
        tok = m.group(0)
        if len(tok) < 2 or not tok[0].isupper() or not tok[1:].islower():
            continue                      # yalniz 'Emily' kalibi (BUYUK+kucuk)
        if any(c in _TR_HARF for c in tok):
            continue                      # Turkce ozel ad -> dokunma
        if _CUMLE_BASI.search(ham[:m.start()]):
            continue                      # cumle basi: buyuk harf ozel ad kaniti degil
        bad, good = tr_upper(tok), ascii_fold(tok).upper()
        if bad != good:
            out[bad] = good
    return out


def _ozel_ad_geri_al(repl: dict, name: str) -> None:
    """Kunye 'bu isim TURKCE' dediyse, _ozel_ad_repl'in o isim icin urettigi
    ASCII donusumunu sozlukten CIKAR (kunye bilgisi sezgiden ustundur)."""
    for tok in re.split(r"[\s'’/&,.]+", str(name or "")):
        tok = tok.strip()
        if len(tok) >= 2:
            repl.pop(tr_upper(tok), None)


def tr_upper_prose(text: str, names=(), tr_set=None) -> str:
    """Ozet PROZASI icin Turkce buyuk harf — isim-FARKINDA, DETERMINISTIK (LLM/uppercase-LLM YOK).
    Govde tr_upper (i->İ). ANCAK verilen cast/crew YABANCI isimleri ASCII buyuk harf kalir:
    'MASSİMO' DEGIL 'MASSIMO', 'KİNSKİ' DEGIL 'KINSKI'. Turkce isimler (Şener, Deniz) DOKUNULMAZ
    (İ korunur). names = filmin cast+yonetmen+yapimci ham adlari.
    tr_set: ONCEDEN hesaplanmis OTORITER Turk-isim kumesi (toplu duckDB; batch'te film-basi baglanti
    KILITLENMESINI onler). None ise burada duckDB (Q43) sorgulanir; duckDB cokerse _is_tr_name'e duser
    (Turkce ismi ASLA bozmaz, yabanciyi guvenli tarafta İ birakir)."""
    up = tr_upper(text or "")
    # OZEL-AD YAKALAMA (Cagatay kurali 2026-08-01: "hicbir aksan gecmeyecek, hangi dil
    # oldugu onemli degil; Latin'de ne aksan var ne ÜĞİŞÇÖ").
    # _repair_foreign_prose_i BELIRTEC ariyor (W/Q/X, -IE/-IO/-IA, sabit liste) ve
    # belirtecsiz yabanci adlari kaciriyordu: EMİLY, DİANA, NİRO, HOPKİNS.
    # Cozum: tr_upper KUCUK/BUYUK bilgisini yok etmeden ONCE HAM metne bak — cumle
    # ORTASINDA buyuk harfle baslayan saf-ASCII sozcuk = ozel ad => ASCII buyut.
    # Turkce prose sozcukleri (ile, film, geciyor) kucuk harfle gectigi icin ETKILENMEZ;
    # Turkce ozel adlar (İstanbul, Şener) Turkce harf tasidigi icin ELENIR.
    onceki = _ozel_ad_repl(text or "")
    names = [n for n in (names or ()) if n]
    if not names:
        for bad, good in onceki.items():
            up = re.sub(r"(?<![A-Za-zÇĞİıŞÖÜçğşöü])" + re.escape(bad)
                        + r"(?![A-Za-zÇĞİıŞÖÜçğşöü])", good, up)
        return _repair_foreign_prose_i(up)
    if tr_set is not None:
        db_ok = True                       # cagiran otoriter kume verdi
    else:
        db_ok, tr_set = _turkish_name_set(names)
    repl: dict[str, str] = dict(onceki)   # ham-metin ozel adlari (kunye listesinde olmayanlar)
    for name in names:
        if any(c in _TR_STRONG for c in name):
            _ozel_ad_geri_al(repl, name)   # kunye 'KESIN Turk' dedi → sezgiyi iptal et
            continue  # ışğİı -> KESIN Turk (tr_upper dogru)
        is_tr = (name in tr_set) if db_ok else _is_tr_name(name)
        if is_tr:
            # ONCELIK: kunye/DB bilgisi ham-metin sezgisini EZER. Saf-ASCII Turk adi
            # ('Ali Kaya') prose'da buyuk harfle gectigi icin _ozel_ad_repl'e dusmus
            # olabilir; oradan CIKAR, yoksa ALİ yerine ALI yazardik.
            _ozel_ad_geri_al(repl, name)
            continue  # Turkce isim: İ korunur
        for tok in re.split(r"[\s'’/&,.]+", str(name)):
            tok = tok.strip()
            if len(tok) < 2:
                continue
            bad = tr_upper(tok)              # 'Massimo' -> 'MASSİMO' (yanlis: yabancida İ)
            good = ascii_fold(tok).upper()  # 'Massimo' -> 'MASSIMO' (dogru: ASCII)
            if bad != good:
                repl[bad] = good
    for bad, good in repl.items():
        # SADECE tam kelime/ek siniri: 'MASSİMO'YU' -> 'MASSIMO'YU; 'ELİ' icin 'ELİF'i BOZMA.
        up = re.sub(r"(?<![A-Za-zÇĞİıŞÖÜçğşöü])" + re.escape(bad) + r"(?![A-Za-zÇĞİıŞÖÜçğşöü])", good, up)
    return _repair_foreign_prose_i(up)


# Turkce ad DB (saf-ASCII isim kokeni icin; qwen'den guvenilir). Yoksa bos -> qwen.
_TR_GIVEN: set = set()
_TR_SUR: set = set()
try:
    import importlib.util as _ilu
    # Linux gecisi (2026-08-01, 8. sabit-yol vakasi): r"E:\MITAS\scripts\..." Linux'ta
    # yok → import sessizce dusuyor → _TR_GIVEN/_TR_SUR BOS kaliyor → _is_tr_name HER
    # saf-ASCII ismi "yabanci" sayiyor. Yani JASON KIDD'in Turkce/yabanci ayrimi
    # DB'siz calisiyordu: 'Ali Kaya' → ALI (ALİ olmali). Env-aware + depo-goreli.
    import os as _os
    _kok = _os.environ.get("MITAS_PROJECT_ROOT") or str(Path(__file__).resolve().parents[2])
    _kc_yol = _os.path.join(_kok, "scripts", "_kunye_classify.py")
    _spec = _ilu.spec_from_file_location("_kunye_classify_kb", _kc_yol)
    _kc = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_kc)
    _TR_GIVEN, _TR_SUR = _kc.load_turkish()
except Exception:  # noqa: BLE001 - DB/pandas yoksa qwen'e dus
    _TR_GIVEN, _TR_SUR = set(), set()


def _is_tr_name(n: str) -> bool:
    """Saf-ASCII ismi ad+soyad DB'sinden Turkce mi (duckDB KAPALI fallback). SIKI (Cagatay:
    'duckDB kapaliyken fallback gevsek olmasin; belirsizde YABANCI varsay'):
      • >=2 token: ilk GIVEN'da VE son SUR'da (IKISI DE) → Turk.  Yabanci soyad (Gasmia/Kitanov) eler.
      • TEK token: BELIRSIZ → YABANCI say (False) — tek isim kokeni guvenilmez, ASCII'de birak."""
    if not (_TR_GIVEN or _TR_SUR):
        return False
    toks = ascii_fold(n).upper().split()
    if len(toks) < 2:
        return False  # tek token belirsiz → yabanci (i->I), Turkce-kasa (İ) verme
    return toks[0] in _TR_GIVEN and toks[-1] in _TR_SUR


_MITAS_DB = os.environ.get("MITAS_WIKIDATA_DUCKDB", r"E:\MITAS\Mitas_Files\MitaData\mitas.duckdb")


# Wikidata Turk ulke kumesi: Q43=Turkiye, Q23681=KKTC (Kuzey Kibris). mitas_people_index DUNYA
# kisi DB'si; countries '|' ile coklu olabilir (Q43|Q23681, sadece Q23681...). Hazar Erguclu=Q23681.
_MITAS_TR_QIDS = {"Q43", "Q23681"}


def _mitas_people_set(names):
    """Isimleri mitas_people_index (Wikidata DUNYA kisi DB'si) icinde TOPLU ara, countries
    Q43 (Turkiye) VEYA Q23681 (KKTC) olanlari Turk say. Doner (db_calisti, giren_isim->canonical_name).
    canonical_name: DB'deki Turkce yazim (Ayşenil Şamlıoğlu / Hazar Ergüçlü) — tr_upper icin dogru base.
    Anahtar Turkce-duyarli fold (_tr_fold_key: 'Tarık'→'TARIK'); exact-miss icin GUVENLI fuzzy
    (unique+conf>=0.7+ilk&son token DB'de). Nuri Bilge Ceylan/Murat Cemcir/Hazar Ergüçlü -> Turk;
    François Truffaut -> Q142 (Fransa, yabanci); Fabian Gasmia -> ulke yok -> yabanci.
    DB/duckdb yoksa (False, {}) -> CSV fallback."""
    if not names:
        return True, {}
    try:
        import duckdb
        con = duckdb.connect(_MITAS_DB, read_only=True)
        # (1) Turkce-duyarli anahtar: _tr_fold_key ('Tarık'→'TARIK') DB UPPER(strip_accents)=_sql_tr_fold
        #     ile eşleşir; eski ascii_fold 'ı'yı silip 'TARK' uretiyor, DB miss'e yol aciyordu.
        keys = [_tr_fold_key(n) for n in names]
        nm_e, an_e = _sql_tr_fold("name"), _sql_tr_fold("ascii_name")
        ph = ",".join(["?"] * len(keys))
        sql = (f"SELECT name, {nm_e} nm, {an_e} an, countries "
               f"FROM main.mitas_people_index "
               f"WHERE {nm_e} IN ({ph}) OR {an_e} IN ({ph})")
        rows = con.execute(sql, keys + keys).fetchall()
        # ascii_key (nm veya an) → kanonik Türkçe isim (name sutunu).
        # (2) countries '|' kume; Q43 (Turkiye) VEYA Q23681 (KKTC) HERHANGI biri varsa Turk.
        tr_canonical: dict[str, str] = {}
        for canon_name, nm, an, c in rows:
            if canon_name and c and (_MITAS_TR_QIDS & set(str(c).split("|"))):
                for ak in (nm, an):
                    if ak:
                        tr_canonical[ak] = canon_name
        # giren ismin _tr_fold_key anahtar ile eşleştir → {giren_isim: kanonik_ad}
        result = {}
        for n, k in zip(names, keys):
            if k in tr_canonical:
                result[n] = tr_canonical[k]
        # NOT: Gevsek "fuzzy isim tamamlama" KASITLI eklenmedi. Exact-fold (yukarisi) ayni ismi
        # (yalniz diakritik/kasa farkli) deterministik+hizli (tek batch IN sorgusu) yakalar. Token
        # ekleyen/degistiren fuzzy ("Nuri Bilge"->"...Ceylan", orta-token tamamlama) ICERIGI degistirir
        # ("okunamadi>yanlis oku" ihlali) + isim basina 13M-satirda LIKE taramasi (perf) getirir.
        # Isim TAMAMLAMA/cozumleme KB cross-check'in (credit_crosscheck) isi, kasa fonksiyonunun degil.
        con.close()
        return True, result
    except Exception as e:  # noqa: BLE001 - DB/duckdb yoksa CSV fallback
        import sys
        sys.stderr.write(f"[name_normalize][UYARI] mitas.duckdb erisilemedi -> CSV fallback "
                         f"(yabanci isim Turkce-kasa alabilir): {e}\n")
        return False, {}


# ---------------------------------------------------------------------------
# DeepSeek + cache HIBRIT fallback (denetim "Approach C") — SADECE DB-MISS isimler.
# Deterministik DB (mitas_people_index) ismi BULAMAYINCA, MITAS_DEEPSEEK anahtari
# VARSA DeepSeek'e "Turk mu yabanci mi + kanonik yazim" sorulur, sonuc CACHE'lenir
# (isim basina deterministik). Anahtar yok / DeepSeek None / parse-fail -> MEVCUT
# davranis (ascii_fold(isim).upper()); ASLA cokme.
# ---------------------------------------------------------------------------

# Bu dosya OCR-worktree/pdf-mitas altinda; ana proje koku iki ust dizin.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_NAME_CACHE_PATH = os.path.join(_PROJECT_ROOT, "outputs", "name_norm_cache.json")
_SCRIPTS_DIR = os.path.join(_PROJECT_ROOT, "scripts")


# turkce-aksan-fix 2026-06-29
# Türkçe circumflex (Â/Î/Û) → düz A/I/U normalize eder; Türkçe özel harfler (ç ğ ı İ ö ş ü)
# KORUNUR. translit_util.asciify_foreign scripts/ altında; bulunamazsa girdi DEĞİŞMEDEN döner
# (fail-soft — pipeline çökmez). name_normalize stdlib-only import eder, translit_util burada
# lazy yüklenir (_deepseek yükleme paterni, satır 361-362, ile aynı yöntem).
def _asciify_foreign(s: str) -> str:
    """Yabancı aksan→ASCII, Türkçe circumflex (Â/Î/Û)→A/I/U düzleştir; ç ğ ı İ ö ş ü KORUNUR.
    translit_util.asciify_foreign: _TR_KEEP={çÇğĞıİöÖşŞüÜ} ile korur, NFKD ile Â→A indirir."""
    try:
        if _SCRIPTS_DIR not in sys.path:
            sys.path.insert(0, _SCRIPTS_DIR)
        import translit_util as _tu  # noqa: WPS433
        return _tu.asciify_foreign(s)
    except Exception:  # noqa: BLE001 - translit_util yoksa/patlarsa sessiz geç
        return s


def _deepseek_available() -> bool:
    """MITAS_DEEPSEEK (veya DEEPSEEK_API_KEY) anahtari var mi? (cagri-oncesi ucuz kontrol)."""
    return bool(os.environ.get("MITAS_DEEPSEEK") or os.environ.get("DEEPSEEK_API_KEY"))


def _name_cache_load() -> dict:
    """name_norm_cache.json oku. Yoksa/bozuksa {} (asla cokme)."""
    try:
        with open(_NAME_CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _name_cache_store(cache: dict) -> None:
    """cache'i ATOMIK (temp + os.replace) yaz. Tum hatalari yut."""
    try:
        out_dir = os.path.dirname(_NAME_CACHE_PATH)
        os.makedirs(out_dir, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=out_dir, prefix=".name_norm_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
            os.replace(tmp, _NAME_CACHE_PATH)
        finally:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001 - cache best-effort
        return


def _load_deepseek():
    """scripts/_deepseek modulunu yukle (sys.path'e scripts/ ekleyerek). Yoksa None."""
    try:
        if _SCRIPTS_DIR not in sys.path:
            sys.path.insert(0, _SCRIPTS_DIR)
        import _deepseek  # noqa: WPS433
        return _deepseek
    except Exception:  # noqa: BLE001 - _deepseek yoksa/patlarsa sessiz
        return None


_DEEPSEEK_PROMPT_TMPL = (
    "Bu bir kişi ADI: '{name}'. Türk ismi mi yabancı mı? "
    "Türk ise Türkçe-diakritikli (ç ğ ı İ ö ş ü) KANONİK yazımını; "
    "yabancı ise SADE ASCII halini ver. "
    'SADECE JSON döndür: {{"turk": true/false, "yazim": "..."}}'
)


def _deepseek_resolve(name: str, cache: dict) -> str | None:
    """DB-MISS ismi DeepSeek+cache ile cozumle. Donus:
      • Turk  -> tr_upper(yazim)        (diakritik korunur)
      • Yabanci -> ascii_fold(yazim).upper()
      • cozulemedi/anahtar-yok/parse-fail -> None  (cagiran MEVCUT davranisa duser)
    Cache HIT -> DeepSeek CAGRILMAZ. MISS -> cagir, sonucu ATOMIK cache'le.
    cache dict YERINDE guncellenir (cagiran tek sefer diske yazar)."""
    key = _fold(name)
    if not key:
        return None
    rec = cache.get(key)
    if not isinstance(rec, dict):
        # MISS -> anahtar varsa DeepSeek'e sor
        if not _deepseek_available():
            return None
        ds = _load_deepseek()
        if ds is None:
            return None
        try:
            txt = ds.deepseek_text(
                prompt=_DEEPSEEK_PROMPT_TMPL.format(name=name),
                temperature=0,
                fmt={"type": "json_object"},
                max_tokens=100,
            )
            if not txt:
                return None
            parsed = json.loads(txt)
            rec = {"turk": bool(parsed.get("turk")), "yazim": str(parsed.get("yazim") or "")}
        except Exception:  # noqa: BLE001 - parse/cagri hatasi -> MEVCUT davranis
            return None
        cache[key] = rec          # yerinde guncelle (cagiran diske yazacak)
    # HIT ya da taze sonuc -> uygula
    try:
        if rec.get("turk"):
            return tr_upper(rec.get("yazim") or name)
        return ascii_fold(rec.get("yazim") or name).upper()
    except Exception:  # noqa: BLE001
        return None


_FOREIGN_SYNTHETIC_I_TOKENS = {
    # Eski tr_upper kirlenmesinde sık görülen Batı dilleri kişi adı parçaları.
    "ANDRE", "ANDREA", "ANDREAS", "ANDREW", "ANTONIO", "BRIGITTE", "CHARLIE",
    "CHRISTIAN", "CHRISTOPHER", "DANIEL", "DAVID", "DICAPRIO", "ELIZABETH",
    "FABIAN", "FEDERICO", "FREDRIC", "FREDERICK", "GIOVANNI", "GIUSEPPE",
    "FREDDIE", "JAMES", "JEAN", "JIM", "JODIE", "JOHN", "JOSEPH", "KINSKI", "LEONARDO",
    "MARCIN", "MARTIN", "MASSIMO", "MICHAEL", "NICOLAS", "PATRICK", "PIERRE",
    "RICHARD", "ROBERT", "ROBERTO", "SIMON", "STEPHEN", "THOMAS", "VINCENT",
    "VITTORIO", "WILLIAM",
    # Somut saha örnekleri / soyadları.
    "DARROUSSIN", "GIROTTI", "KAURISMAKI", "KELLEGHER", "PATAKI", "RITT",
    "SINEAD", "SOPHIE", "TINA", "WILMS",
}


def _repair_foreign_prose_i(text: str) -> str:
    """Buyuk-harfli prose icinde yabanci ad kokundeki sentetik İ'yi geri al.

    Turkce ek korunur: SOPHİE'NİN -> SOPHIE'NİN.
    """
    def repl(m):
        token = m.group(0)
        base, sep, suffix = token.partition("'")
        if "İ" not in base or any(c in _TR_STRONG_REAL for c in base):
            return token
        folded = ascii_fold(base).upper()
        marker = (
            folded in _FOREIGN_SYNTHETIC_I_TOKENS
            or folded.endswith(("IE", "IO", "IA"))
            or any(ch in folded for ch in "WQX")
        )
        if not marker:
            return token
        return folded + (sep + suffix if sep else "")

    return re.sub(r"[A-ZÇĞİIÖŞÜ]+(?:'[A-ZÇĞİIÖŞÜ]+)?", repl, text or "")


def _has_foreign_latin_accent(name: str) -> bool:
    return any((not c.isascii()) and unicodedata.category(c).startswith("L")
               and c not in _TR_AMBIG and c != "İ"
               for c in (name or ""))


def _repair_synthetic_dotted_i(name: str, tr_hits: dict[str, str]) -> str | None:
    """Eski tr_upper yabancı addaki i'leri İ yapmışsa ASCII'ye geri al.

    Sadece tek güçlü sinyal sentetik dotted-İ ise çalışır. Gerçek Türkçe sinyal
    (ş/ğ/ı) veya DB/yerel sözlük Türk doğrulaması varsa dokunmaz.
    """
    if "İ" not in (name or ""):
        return None
    if any(c in _TR_STRONG_REAL for c in name):
        return None
    if tr_hits.get(name) is not None or _is_tr_name(name):
        return None

    folded = ascii_fold(name).upper()
    toks = re.findall(r"[A-Z]+", folded)
    foreign_marker = (
        _has_foreign_latin_accent(name)
        or "-" in name
        or any(any(ch in tok for ch in "WQX") for tok in toks)
        or any(tok in _FOREIGN_SYNTHETIC_I_TOKENS for tok in toks)
    )
    return folded if foreign_marker else None


def upper_names(names, *, use_qwen: bool = False):
    """Isimleri BUYUK harfe cevir (kunye kurali, Cagatay):
      • Turkce isim  -> Turkce upper:  irfan->İRFAN, gökhan->GÖKHAN (i->İ; ç ğ ı ö ş ü KORUNUR)
      • Yabanci isim -> ASCII upper:   ivan ->IVAN, fabian->FABIAN (i->I, aksan duser)
    Karar sirasi (qwen YOK):
      1) Turkce-ozel karakter (ç ğ ı ö ş ü) iceren -> KESIN Turk, KORU.
         Yalniz İ sinyali eski tr_upper kirlenmesi olabilir; acik yabanciysa ASCII'ye geri al.
      2) Yabanci aksan (é,ñ,ø...) -> kesin yabanci, fold.
      3) Saf-ASCII -> mitas_people_index (Turk-kisi DB): VAR=Turk (i->İ), YOK=yabanci (i->I).
         (Nuri Bilge Ceylan VAR, Fabian Gasmia YOK.) DB erissizse given+sur CSV fallback."""
    if not names:
        return names
    # _TR_STRONG (ı,İ,ş,ğ) KESIN Turk; _TR_AMBIG (ç,ö,ü) belirsiz → DB'ye sor.
    # pure: DB'ye sorulacaklar — _TR_STRONG YOK ve _TR_AMBIG dışında non-ASCII Latin harf YOK.
    # (Önceki hata: tüm non-ASCII-L içereni dışlıyordu; _TR_AMBIG içerenleri de dışlıyordu
    #  → Ali Öztürk/Eslem Öztürk DB'ye sorulmadan ascii_fold.upper()=ASCII çıkıyordu.)
    pure = [n for n in names
            if not any(c in _TR_STRONG for c in n)
            and all(c.isascii() or unicodedata.category(c)[0] != "L" or c in _TR_AMBIG
                    for c in n)]
    db_ok, mitas_tr = _mitas_people_set(pure)
    # mitas_tr: {giren_isim: kanonik_Turkce_ad} (ornek: "Aysenil Samlioglu" -> "Ayşenil Şamlıoğlu")
    # DeepSeek+cache (Approach C): SADECE DB-MISS isimler icin, anahtar VARSA. Cache bir kez yuklenir,
    # _deepseek_resolve cache'i yerinde gunceller; en sonda (degistiyse) bir kez diske yazilir.
    _ds_on = db_ok and _deepseek_available()
    _ds_cache = _name_cache_load() if _ds_on else {}
    _ds_cache_before = len(_ds_cache)
    out = []
    for n in names:
        repaired = _repair_synthetic_dotted_i(n, mitas_tr)
        if repaired is not None:
            out.append(repaired)
        elif any(c in _TR_STRONG for c in n):
            # turkce-aksan-fix 2026-06-29: Â/Î/Û (TRT-dışı circumflex) → A/I/U düzleştir;
            # ç ğ ı İ ö ş ü korunur. Bu path: TÜRKÂN ŞORAY buraya düşer (ş→_TR_STRONG).
            out.append(_asciify_foreign(tr_upper(n)))     # ı/İ/ş/ğ KESIN Turk -> koru, Â→A
        elif any((not c.isascii()) and unicodedata.category(c).startswith("L") and c not in _TR_AMBIG for c in n):
            out.append(ascii_fold(n).upper())             # baska yabanci aksan (é,ñ,ø...) -> fold
        else:                                             # saf-ASCII veya yalniz ç/ö/ü -> koken
            if db_ok:
                canonical = mitas_tr.get(n)              # DB'den Turkce kanonik (ornek: "Ayşenil Şamlıoğlu")
                if canonical is not None:
                    # turkce-aksan-fix 2026-06-29: kanonik DB adında Â kalırsa A'ya indir.
                    out.append(_asciify_foreign(tr_upper(canonical)))  # DB-HIT -> Turkce buyuk harf, Â→A
                else:
                    # DB-MISS: once DeepSeek+cache (anahtar varsa); cozulemezse MEVCUT davranis.
                    ds_val = _deepseek_resolve(n, _ds_cache) if _ds_on else None
                    out.append(ds_val if ds_val is not None else ascii_fold(n).upper())
            else:
                is_tr = _is_tr_name(n)
                out.append(tr_upper(n) if is_tr else ascii_fold(n).upper())
    # Cache'e yeni kayit eklendiyse (DeepSeek cagrildi) bir kez ATOMIK yaz.
    if _ds_on and len(_ds_cache) != _ds_cache_before:
        _name_cache_store(_ds_cache)
    return out


def upper_crew(crew, *, use_qwen: bool = True):
    """crew = [(rol, [isim...])] -> isimleri upper_names ile BUYUK; rol etiketi sabit."""
    flat = [nm for _, names in crew for nm in (names if isinstance(names, list) else [names])]
    mapping = dict(zip([_fold(x) for x in flat], upper_names(flat, use_qwen=use_qwen)))
    out = []
    for role, names in crew:
        nl = names if isinstance(names, list) else [names]
        out.append((role, [mapping.get(_fold(x), x) for x in nl]))
    return out
