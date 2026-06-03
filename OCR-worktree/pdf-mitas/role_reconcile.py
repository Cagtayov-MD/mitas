# -*- coding: utf-8 -*-
"""MITAS — rol akli: OCR kunye rollerini XML + meslek-DB ile dogrula/duzelt.

SORUN: credit_parse.parse_credits MEKANIK (satir sirasi) -> roller karisir
(yonetmen oyuncuya, goruntu yonetmeni yonetmene duser). Bu katman SAF, yan
etkisiz bir dogrulama gecisi ekler:

  Katman 1 (BIRINCIL, deterministik) — XML ankraj:
    TRT XML rol listeleri otoritedir. OCR'da rol-X'e ama XML'de rol-Y'ye
    dusen isim -> XML kazanir, dogru role TASINIR. (DIKKAT: XML yapimci alani
    cogu kez TRT/dublaj personeli icerir -> yapimci ankrajina AZ guven.)
  Katman 2 (IKINCIL) — meslek-DB:
    XML kararsizsa, _kunye_classify.imdb_professions ile cast'teki bir isim
    SADECE crew meslegine sahipse dogru role tasinir. DB yoksa ATLA (graceful).

SADAKAT: eslesmeyen/belirsiz isim SILINMEZ, OCR hali korunur ("okunamadi >
yanlis oku"). UYDURMA YOK — yalniz var olan ismi rol arasinda TASIR + isaretler.

API (saf; ayni tip in/out):
  reconcile(cast, crew, *, xml_roles=None, use_kb=True) -> (cast, crew, meta)
    cast: list[str]
    crew: list[(rol, [isim,...])]          (credit_parse.parse_credits cikisi)
    xml_roles: {"oyuncu":[...], "yonetmen":[...], "yapimci":[...]} | None
    meta: {moved:[...], unverified:[...], xml_used:bool, kb_used:bool}
"""
from __future__ import annotations
import importlib.util
from pathlib import Path

# --- TEK fold/dedup kaynagi: credit_parse (tutarlilik) ---
# Bu modul pdf-mitas/ icinde; credit_parse de ayni klasorde. Hem normal import
# (paket olarak yuklenmisse) hem de dosya-yolu yuklemesi (mitas_pipeline._load
# kalibinda izole yukleme) icin guvenli sekilde fold/_dedup'i bul.
_HERE = Path(__file__).resolve().parent
try:
    from credit_parse import fold as _fold, _dedup as _dedup  # type: ignore
except Exception:  # noqa: BLE001 — izole/dosya-yolu yuklemesinde sys.path'te olmayabilir
    _spec = importlib.util.spec_from_file_location("credit_parse", str(_HERE / "credit_parse.py"))
    _cp = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_cp)
    _fold, _dedup = _cp.fold, _cp._dedup


# OCR crew etiketi (Turkce kanonik) -> XML rol anahtari. credit_parse'in urettigi
# rol basliklari ("Yonetmen", "Goruntu Yonetmeni", "Yapimci"...) hangi XML
# kovasina ait? XML yalniz 3 kovaya ayirir (yonetmen/yapimci/oyuncu), bu yuzden
# yonetim-disi crew rolleri (kurgu, muzik, senaryo...) XML ankrajina GIRMEZ.
def _crew_label_to_xml_key(label: str) -> str | None:
    f = _fold(label)
    if "yonetmen yard" in f:          # Yonetmen Yardimcisi: yonetmen DEGIL
        return None
    if "goruntu yonet" in f:          # Goruntu Yonetmeni: yonetmen DEGIL (XML'de oyuncu/crew karisik)
        return None
    if "sanat yonet" in f:            # Sanat Yonetmeni: yonetmen DEGIL
        return None
    if "yonetmen" in f:               # bare Yonetmen
        return "yonetmen"
    if "yapimci" in f:                # Yapimci
        return "yapimci"
    return None


def _xml_lookup(xml_roles: dict) -> dict:
    """{fold(isim): xml_key} — XML rol listelerinden ters indeks.

    Yapimci'ya AZ guven: yonetmen/oyuncu zaten gercek kisidir; yapimci alani
    TRT/dublaj personeli olabilir. Bir isim birden cok kovada gorunurse
    yonetmen > oyuncu > yapimci onceligiyle TEK kovaya baglanir (yanlis yapimci
    ankrajini en aza indirir)."""
    idx: dict = {}
    for key in ("yapimci", "oyuncu", "yonetmen"):   # ters oncelik: sonraki ezer
        for nm in (xml_roles.get(key) or []):
            k = _fold(nm)
            if k:
                idx[k] = key
    return idx


def _ensure_crew_role(crew: list, label: str) -> list:
    """crew icinde 'label' rolu yoksa BOS listeyle ekler; ayni crew'i dondurur."""
    for rol, _ in crew:
        if rol == label:
            return crew
    crew.append((label, []))
    return crew


# crew rol etiketinin XML-key ile uyumu (tasima hedefi secerken). XML'de yonetmen
# olan bir ismi crew'de hangi role koyacagiz? bare "Yonetmen". Yapimci -> "Yapimci".
_XML_KEY_TO_CREW_LABEL = {"yonetmen": "Yönetmen", "yapimci": "Yapımcı"}


def reconcile(cast, crew, *, xml_roles: dict | None = None, use_kb: bool = True):
    """OCR cast/crew'i XML (birincil) + meslek-DB (ikincil) ile dogrula/duzelt.

    Saf: girdiyi KOPYALAR, mutasyon yok. cast=list[str], crew=[(rol,[isim])]
    yapisi KORUNUR. Hicbir isim silinmez/uydurulmaz; yalniz rol DUZELTILIR.
    """
    # --- girdiyi kopyala (saf) ---
    cast = list(cast or [])
    crew = [(rol, list(names)) for rol, names in (crew or [])]
    meta = {"moved": [], "unverified": [], "xml_used": False, "kb_used": False}

    # ===== Katman 1: XML ankraj (birincil, deterministik) =====
    if xml_roles:
        xml_idx = _xml_lookup(xml_roles)
        if xml_idx:
            meta["xml_used"] = True

            # crew rolunden -> XML beklenen anahtar (yonetim rolleri icin)
            def _move_to(target_label: str, name: str, src: str):
                nonlocal crew
                crew = _ensure_crew_role(crew, target_label)
                for i, (rol, names) in enumerate(crew):
                    if rol == target_label:
                        if not any(_fold(x) == _fold(name) for x in names):
                            names.append(name)
                        crew[i] = (rol, names)
                        break
                meta["moved"].append({"name": name, "from": src, "to": target_label})

            # 1a) cast'teki isim XML'de yonetmen/yapimci ise -> crew'e tasi, cast'ten cikar
            new_cast = []
            for nm in cast:
                key = xml_idx.get(_fold(nm))
                if key in _XML_KEY_TO_CREW_LABEL:
                    # DIKKAT: yapimci ankrajina az guven — yapimciya tasimayi,
                    # isim XML yapimci listesinde VE OCR'da zaten kisi sayilmissa yap.
                    _move_to(_XML_KEY_TO_CREW_LABEL[key], nm, "oyuncu")
                else:
                    new_cast.append(nm)        # XML'de yok VEYA oyuncu -> dokunma
            cast = new_cast

            # 1b) crew'deki isim YANLIS yonetim rolundeyse (OCR rol-X, XML rol-Y) duzelt.
            #     Yalniz XML'in net ayirdigi yonetmen<->yapimci karisikligini ele al.
            fixed_crew = []
            for rol, names in crew:
                src_key = _crew_label_to_xml_key(rol)   # bu crew rolu hangi XML kovasi?
                keep = []
                for nm in names:
                    key = xml_idx.get(_fold(nm))
                    # isim XML'de NET baska bir yonetim rolune aitse tasi
                    if key in _XML_KEY_TO_CREW_LABEL and src_key is not None and key != src_key:
                        _move_to(_XML_KEY_TO_CREW_LABEL[key], nm, rol)
                    else:
                        keep.append(nm)        # XML'de yok / belirsiz / ayni rol -> dokunma
                fixed_crew.append((rol, keep))
            crew = fixed_crew

            # 1c) XML'de oyuncu olan ama OCR'da YANLIS crew'e dusmus isimleri cast'e geri al.
            #     (yalniz yonetim crew rollerinden; "Diger"/teknik rollere dokunma — XML eksik olabilir.)
            cast_fold = {_fold(c) for c in cast}
            recovered_crew = []
            for rol, names in crew:
                src_key = _crew_label_to_xml_key(rol)
                if src_key is None:            # yonetim disi rol -> XML otoritesi yok, dokunma
                    recovered_crew.append((rol, names))
                    continue
                keep = []
                for nm in names:
                    if xml_idx.get(_fold(nm)) == "oyuncu" and _fold(nm) not in cast_fold:
                        cast.append(nm)
                        cast_fold.add(_fold(nm))
                        meta["moved"].append({"name": nm, "from": rol, "to": "oyuncu"})
                    else:
                        keep.append(nm)
                recovered_crew.append((rol, keep))
            crew = recovered_crew

    # ===== Katman 2: meslek-DB (ikincil; XML kararsizsa) =====
    # cast'teki bir isim IMDB'de SADECE crew meslegine sahipse (oyuncu DEGIL),
    # ilgili role tasinir. DB yoksa/yuklenmezse sessiz atlanir (graceful).
    if use_kb and cast:
        try:
            kc = _load_kunye_classify()
            if kc is not None:
                # XML'in zaten kesin yonetmen/yapimci dedigi isimleri KB'ye sorma
                # (XML otorite). Kalan cast'i sorgula.
                xml_idx = _xml_lookup(xml_roles) if xml_roles else {}
                # SADECE >=2 token isimler KB ile tasinabilir: tek-token OCR gurultusu
                # (karakter adi "Asuman"/"Idris" gibi) yanlislikla IMDB'de bir crew'e
                # eslesip rol degistirmesin. (_kunye_classify de >=2 token sartı kullanir.)
                cand_names = [c for c in cast
                              if xml_idx.get(_fold(c)) != "oyuncu" and len(kc.norm(c).split()) >= 2]
                norm_map = {c: kc.norm(c) for c in cand_names}
                prof = kc.imdb_professions(sorted({v for v in norm_map.values() if v}))
                prof.pop("__error__", None)
                if prof:
                    meta["kb_used"] = True
                    CREW_PROF = {"director", "producer", "writer", "composer",
                                 "cinematographer", "editor", "production_designer",
                                 "casting_director"}
                    # meslek -> crew rol etiketi (yalniz net yonetmen/yapimci tasinir;
                    # digerleri OCR halinde kalir — XML/KB cast'i bos yere parcalamasin)
                    DIR = {"director"}
                    PROD = {"producer"}
                    new_cast = []
                    for nm in cast:
                        ps = prof.get(norm_map.get(nm, ""), set())
                        is_actor = ("actor" in ps or "actress" in ps)
                        if ps and not is_actor and (ps & CREW_PROF):
                            if ps & DIR:
                                _kb_move(crew, "Yönetmen", nm, meta)
                            elif ps & PROD:
                                _kb_move(crew, "Yapımcı", nm, meta)
                            else:
                                # net rol degil ama oyuncu da degil -> belirsiz, OCR'da birak
                                new_cast.append(nm)
                                meta["unverified"].append(nm)
                        else:
                            new_cast.append(nm)
                    cast = new_cast
        except Exception:  # noqa: BLE001 — duckdb yok / ag share / herhangi DB hatasi -> graceful
            pass

    # --- final dedup (TEK fold kaynagi) ---
    cast = _dedup(cast)
    crew = [(rol, _dedup(names)) for rol, names in crew if names]
    return cast, crew, meta


def _kb_move(crew: list, target_label: str, name: str, meta: dict) -> None:
    """meslek-DB tasimasi: crew'e ekle (yoksa rol olustur), meta.moved'a yaz."""
    _ensure_crew_role(crew, target_label)
    for i, (rol, names) in enumerate(crew):
        if rol == target_label:
            if not any(_fold(x) == _fold(name) for x in names):
                names.append(name)
            crew[i] = (rol, names)
            break
    meta["moved"].append({"name": name, "from": "oyuncu", "to": target_label, "by": "kb"})


def _load_kunye_classify():
    """scripts/_kunye_classify.py'yi izole yukle (norm + imdb_professions icin).

    Bu modul pdf-mitas/ icinde; _kunye_classify scripts/ altinda. Once normal
    import, sonra bilinen yol denenir. duckdb/pandas import'u modul SEVIYESINDE
    olmadigindan yukleme kendisi cokmez; gercek DB erisimi imdb_professions
    icinde try/except ile sarili."""
    try:
        import _kunye_classify as kc  # type: ignore
        return kc
    except Exception:  # noqa: BLE001
        pass
    cand = _HERE.parent.parent / "scripts" / "_kunye_classify.py"   # OCR-worktree/pdf-mitas -> E:\MITAS\scripts
    try:
        if not cand.exists():
            return None
        spec = importlib.util.spec_from_file_location("_kunye_classify", str(cand))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:  # noqa: BLE001
        return None
