#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_pipe_credit_vl.py — VL-FALLBACK (additif, FAIL-SAFE).

mitas_pipeline çağırır: metin künye-okuma (qwen3) yönetmen BOŞ ya da cast<3 ise →
jenerik KARELERİNDEN VL re-read (qwen2.5vl + gemma4) + tiebreak merdiveni → metnin
BOŞ alanını doldur. Metnin GÜVENLE okuduğunu EZMEZ (gap-filler).

TASARIM (Çağatay 2026-06-09, TASARIM_KUNYE_PIPELINE_v2.md):
  AŞAMA 4 tiebreak: a) mutabakat  b) cross-cast self-consistency  c) KB-onay  d) PES→Kontrol
  Cast-supplement (#3): text cast<3 → VL cast'ten tamamla. Yapımcı: sadece-kişi (#2, KESİN KURAL).
  2-model VL (#4). num_ctx=40960 (36 kare>16384→400). think=False (read_segment'te).

FAIL-SAFE: kare yok / ollama kapalı / herhangi hata → girdi text-credits AYNEN döner (ASLA çökmez).
Çıktı: tek-satır JSON (mitas_pipeline'ın last_json'u okur), credit_text ile AYNI şema (drop-in merge).
"""
import argparse
import difflib
import glob
import json
import os
import re
import sys
import time
import unicodedata
import debug_trace as dbg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# VL prompt: yönetmen-etiket kalıpları + KESİN KURAL (metin tarafıyla aynı mantık)
_VL_PROMPT = (
    "Bunlar bir film jeneriğinin ARDIŞIK kareleri (video). Kareler boyunca görünen yazıları "
    "birleştir. SADECE karelerde AÇIKÇA YAZAN isimleri kullan, UYDURMA; yoksa 'yok'.\n"
    "YÖNETMEN: şu kalıpların YANINDAKİ/ALTINDAKİ KİŞİ adı: 'DIRECTED BY', 'A <İSİM> FILM' "
    "(ör. 'A JOHN McTIERNAN FILM' -> John McTiernan), 'A FILM BY', 'YÖNETMEN', 'YÖNETEN', "
    "'REJİSÖR', 'UN FILM DE', 'EIN FILM VON', 'REGIE', 'RÉALISÉ PAR'. "
    "'ASSISTANT DIRECTOR / DIRECTOR OF PHOTOGRAPHY / ART DIRECTOR / MUSIC' YÖNETMEN DEĞİLDİR. "
    "DİKKAT: 'A <İSİM> PRODUCTION' / '<İSİM> PRODUCTIONS' YAPIM-ŞİRKETİ kartıdır, YÖNETMEN DEĞİLDİR "
    "(ör. 'A JAMES MANOS PRODUCTION' -> yönetmen DEĞİL). Net değilse 'yok'.\n"
    "Çıktıyı tam olarak şu formatta ver:\n"
    "YÖNETMEN: <isim | yok>\nYAPIMCI: <Producer/Yapımcı yanındaki isim(ler) | yok>\n"
    "OYUNCULAR: <görünen başrol oyuncu adları, en fazla 8, virgülle | yok>"
)
VL_MODELS = ["gemma4:26b"]  # tek model: gemma4 VL-fallback (qwen2.5vl kaldırıldı)


def _fold(s):
    s = (s or "")
    for a, b in (("İ", "i"), ("I", "i"), ("ı", "i"), ("Ş", "s"), ("ş", "s"), ("Ğ", "g"),
                 ("ğ", "g"), ("Ü", "u"), ("ü", "u"), ("Ö", "o"), ("ö", "o"), ("Ç", "c"), ("ç", "c")):
        s = s.replace(a, b)
    out = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()
    return " ".join(out.split())   # iç-boşluk normalize (inceleme 2026-07-03: çift-boşluk exact'i kaçırıyordu)


# Korpus kaynak-sınırı işaretçisi (inceleme 2026-07-03): dosya-X'in son satırı ile dosya-Y'nin ilk
# satırı GERÇEK komşu değildir; sentinel satır cross-line eşleşmenin sınırdan Frankenstein üretmesini
# yapısal olarak engeller (_chunk_eq sentinel'e asla uymaz — uzunluk/karakter uyuşmaz).
_CORPUS_SENTINEL = "\x00--kaynak-siniri--\x00"


def _find_frames(clip):
    """clip/frames/giris + cikis.

    Paralel jenerik havuzu aktifse çıkış tarafında `frames/cikis_jenerik`
    tercih edilir. Klasör boş olsa bile ham `frames/cikis`e geri düşülmez; bu,
    not_found kararının VL tarafında gizlice bypass edilmesini önler.
    """
    g = os.path.join(clip, "frames", "giris")
    c = os.path.join(clip, "frames", "cikis")
    cj = os.path.join(clip, "frames", "cikis_jenerik")
    if not os.path.isdir(g):
        cand = glob.glob(os.path.join(clip, "**", "giris"), recursive=True)
        g = cand[0] if cand else None
    # A1 GİRİŞ-HAVUZ PARİTESİ (2026-07-03): çıkışta havuz tercihi zaten vardı, girişte YOKTU.
    # giris_jenerik (yazı-var + dedup'lu, footage'sız) doluysa onu ver — VL daha temiz girdi görür,
    # halüsinasyon tetikleyicisi azalır. Havuz BOŞSA ham frames/giris'e düşülür (çıkıştaki katı
    # kuralın tersi, BİLİNÇLİ: giriş havuzu recall-öncelikli ama OneOCR-körü stilize fontta havuz
    # boş kalabilir; VL'nin değeri tam da o durumda — ham kareler son şans olarak kalmalı).
    if os.environ.get("MITAS_VL_USE_GIRIS_POOL", "1").strip().lower() not in ("0", "false", "off", "no"):
        gj = os.path.join(clip, "frames", "giris_jenerik")
        if os.path.isdir(gj) and glob.glob(os.path.join(gj, "*.png")):
            g = gj
    if os.environ.get("MITAS_VL_USE_JENERIK_POOL", "1").strip().lower() not in ("0", "false", "off", "no"):
        if os.path.isdir(cj):
            c = cj
        elif not os.path.isdir(c or ""):
            cand = glob.glob(os.path.join(clip, "**", "cikis_jenerik"), recursive=True)
            c = cand[0] if cand else c
    if not os.path.isdir(c or ""):
        cand = glob.glob(os.path.join(clip, "**", "cikis"), recursive=True)
        c = cand[0] if cand else None
    return (g if g and os.path.isdir(g) else None), (c if c and os.path.isdir(c) else None)


def _load_raw_ocr(clip, ocr_job=""):
    """Jenerik karelerinin HAM OCR metni (ocr_raw_all + ocr_ham + kunye) → VL hayalet-kalkanı korpusu.
    VL pikselden okur; HAM OCR aynı kareleri işledi → gerçek isim ham OCR'da bulunur, yoksa = uydurma
    (2026-06-20 forensik: FOTOĞRAF VL 'JEFF TOWLES' uydurdu, ham OCR'da YOK → kalkan düşürür).
    Katlanmış boş-olmayan SATIR listesi döndürür (adjacency-aware kalkan için: bütün-isim TEK satırda olmalı).

    A1 RUN-SCOPE (2026-07-03): ocr_job verildiyse yalnız O koşunun job klasörleri okunur — prefix-glob
    '{ocr_job}*' aynı koşunun '-fb' (sabit-pencere re-OCR) kardeşini de KAPSAR (meşru zenginleştirme,
    dışlanmamalı). Eski koşuların artıkları korpusa sızmaz. Kapsam hiç dosya bulamazsa TÜM işlere geri
    düşülür (fail-safe: daraltma boş korpus üretip kalkanı yanlışlıkla devre-dışı bırakmasın).

    A1 MANİFEST KORPUSU (2026-07-03): frames/giris_jenerik_manifest.json 'frames[].credit_lines'
    satırları korpusa ADDITIVE eklenir. Havuz taraması TÜM giriş karelerini OneOCR ile okur; ana-OCR'ın
    CLIP-seçiminde elediği karelerdeki GERÇEK piksel-okumaları VL doğrulamasında kaybolmasın
    (İHTİRAS/Norton kaybı: 'DIRECTED BY Bill L. Norton' kartı CLIP-run filtresine takılmıştı —
    havuz okumuştu ama korpus onu hiç görmüyordu). İnvariant korunur: korpustaki her satır hâlâ
    bir OCR motorunun GERÇEK pikselden okuduğu metindir (uydurma kaynağı eklenmez)."""
    # RUNSCOPE kill-switch (inceleme 2026-07-03): MITAS_VL_CORPUS_RUNSCOPE=0 → ocr_job yok sayılır
    # ("scoped-ama-fakir" korpus şüphesinde koda dokunmadan eski tüm-işler davranışına dönüş).
    if os.environ.get("MITAS_VL_CORPUS_RUNSCOPE", "1").strip().lower() in ("0", "false", "off", "no"):
        ocr_job = ""
    _clip_esc = glob.escape(clip)        # inceleme 2026-07-03: yol içi [/] glob-metakarakter kaçışı
    def _collect(job_prefix):
        found = []
        for pat in ("ocr_raw_all.txt", "ocr_ham.txt", "kunye.txt"):
            if job_prefix:
                found += glob.glob(os.path.join(_clip_esc, "ocr", glob.escape(job_prefix) + "*", "**", pat), recursive=True)
            else:
                found += glob.glob(os.path.join(_clip_esc, "ocr", "**", pat), recursive=True)
        return found
    files = _collect(ocr_job) if ocr_job else _collect("")
    if ocr_job and not files:            # fail-safe: scoped korpus boş → eski (tüm-işler) davranışa dön
        files = _collect("")
    parts = []
    for fp in files:
        try:
            parts.append(open(fp, encoding="utf-8", errors="ignore").read())
        except Exception:  # noqa: BLE001
            pass
    lines = []
    for blob in parts:
        for ln in blob.splitlines():
            f = _fold(ln)
            if f:
                lines.append(f)
        lines.append(_CORPUS_SENTINEL)   # dosya sınırı: yapay bitişikliği kes
    if os.environ.get("MITAS_VL_CORPUS_MANIFEST", "1").strip().lower() not in ("0", "false", "off", "no"):
        try:
            mp = os.path.join(clip, "frames", "giris_jenerik_manifest.json")
            if os.path.isfile(mp):
                mj = json.load(open(mp, encoding="utf-8", errors="ignore"))
                for row in (mj.get("frames") or []):
                    got = False
                    for t in (row.get("credit_lines") or []):
                        f = _fold(t)
                        if f:
                            lines.append(f)
                            got = True
                    if got:
                        lines.append(_CORPUS_SENTINEL)   # kare sınırı: kareler-arası yapay bitişiklik yok
        except Exception:  # noqa: BLE001 — manifest bozuksa korpus eski haliyle kalır (fail-safe)
            pass
    return lines


def _in_raw(name, raw_lines):
    """Geriye-uyum sarıcı: bkz. _in_raw_detail (True/False)."""
    return _in_raw_detail(name, raw_lines)[0]


def _in_raw_detail(name, raw_lines):
    """İsim HAM OCR korpusunda geçiyor mu — Frankenstein kalkanı. Döner: (hit, method, kanit_satiri).
    method ∈ {'exact','fuzzy','crossline','crossline+fuzzy','skip', None}.

    KÖK (MANASLU 2026-06-22): eski `all(t in blob)` token'ları AYRI/substring arıyordu → 'HANS-PETER STAUBER'
    + 'HANNELORE EBNER' ayrı satırlardan 'Hans Ebner' uydurması geçiyordu. Birincil yol hâlâ: tüm isim TEK
    satırda, sıralı, word-boundary ('exact'). raw yoksa kalkan atlanır (FAIL-SAFE, method='skip').
    Eski substring davranışı (≥4/≥3 token subset, blob) MITAS_VL_RAW_ADJACENCY=0 ile geri gelir.

    A1 FUZZY (2026-07-03, inceleme-koşullu): OCR-yazım/translit toleransı (CAZCI Chakhnazarov↔Shakhnazarov,
    NANCY Schneider↔Schaineder canlı kanıt). ASİMETRİK eşik (Opus F-1 koşulu): pencerenin İLK kelimesi
    ön-adla EXACT eşleşiyorsa eşik=MITAS_VL_RAW_FUZZY_RATIO (0.87), değilse 0.92 — 'atif↔arif yilmaz'
    (0.909) ve 'steven↔steve spielberg' (0.903) tipi FARKLI-kişi çiftleri bloklanır, gerçek soyad-OCR
    -bozulması kurtulmaya devam eder. Kısa isim (<8 harf) fuzzy'ye girmez.

    A1-b SATIR-AŞIRI (2026-07-03): dikey kart yerleşimi (CAZCI: 'directed by'/'karen'/'chakhnazarov'
    üst üste) — ismin sıralı parçaları ARDIŞIK satırların HER BİRİNİN TAMAMINA denk gelmeli; sentinel
    satırlar dosya/kare sınırında yapay bitişikliği keser."""
    real_any = any(l != _CORPUS_SENTINEL for l in (raw_lines or []))
    if not real_any:
        return True, "skip", None
    toks = _fold(name).split()
    if not toks:
        return False, None, None
    if os.environ.get("MITAS_VL_RAW_ADJACENCY", "1").strip().lower() in ("0", "false", "off", "no"):
        blob = " ".join(raw_lines)               # ESKİ DAVRANIŞ: ≥4/≥3 token subset, tüm metinde AYRI/substring
        sub = [t for t in toks if len(t) >= 4] or [t for t in toks if len(t) >= 3]
        hit = bool(sub) and all(t in blob for t in sub)
        return hit, ("exact" if hit else None), None
    pat = re.compile(r"\b" + r"\s+".join(re.escape(t) for t in toks) + r"\b")   # tüm isim BİTİŞİK + word-boundary
    for line in raw_lines:
        if pat.search(line):
            return True, "exact", line
    try:
        rmin = float(os.environ.get("MITAS_VL_RAW_FUZZY_RATIO", "0.87") or 0.87)
    except ValueError:
        rmin = 0.87
    fuzzy_on = os.environ.get("MITAS_VL_RAW_FUZZY", "1").strip().lower() not in ("0", "false", "off", "no")
    name_f = " ".join(toks)
    if fuzzy_on and len(name_f) >= 8:
        for line in raw_lines:
            if line == _CORPUS_SENTINEL:
                continue
            if _fuzzy_line_hit(toks, name_f, line, rmin):
                return True, "fuzzy", line
    # crossline, fuzzy kill-switch'inden BAĞIMSIZ çalışır (inceleme bulgusu: bağlaşma istenmiyor);
    # fuzzy kapalıysa parça-eşleşmesi yalnız EXACT olur.
    if os.environ.get("MITAS_VL_RAW_CROSSLINE", "1").strip().lower() in ("0", "false", "off", "no"):
        return False, None, None
    hit, used_fuzzy, ev = _cross_line_hit(toks, raw_lines, rmin, fuzzy_on)
    if hit:
        return True, ("crossline+fuzzy" if used_fuzzy else "crossline"), ev
    return False, None, None


def _cross_line_hit(toks, raw_lines, rmin, fuzzy_on):
    """İsmi 2-3 sıralı parçaya böl; her parça ardışık bir korpus satırının TAMAMIYLA (exact; fuzzy_on ise
    fuzzy≥rmin, uzunluk ön-filtreli) eşleşmeli. Döner: (hit, fuzzy_kullanildi, kanit). Yalnız ≥2 token (A1-b)."""
    n = len(toks)
    if n < 2:
        return False, False, None
    splits = []
    for c1 in range(1, n):                           # 2 parça
        splits.append((" ".join(toks[:c1]), " ".join(toks[c1:])))
    if n >= 3:
        for c1 in range(1, n - 1):                   # 3 parça
            for c2 in range(c1 + 1, n):
                splits.append((" ".join(toks[:c1]), " ".join(toks[c1:c2]), " ".join(toks[c2:])))
    def _chunk_eq(chunk, line):
        if line == _CORPUS_SENTINEL:
            return None
        if line == chunk:
            return "exact"
        if not fuzzy_on:
            return None
        if abs(len(line) - len(chunk)) > max(2, int(0.25 * len(chunk))):
            return None
        if difflib.SequenceMatcher(None, chunk, line).ratio() >= rmin:
            return "fuzzy"
        return None
    for chunks in splits:
        k = len(chunks)
        for i in range(len(raw_lines) - k + 1):
            kinds = [_chunk_eq(chunks[j], raw_lines[i + j]) for j in range(k)]
            if all(kinds):
                ev = " / ".join(raw_lines[i:i + k])
                return True, any(x == "fuzzy" for x in kinds), ev
    return False, False, None


def _fuzzy_line_hit(toks, name, line, rmin):
    """Tek satır içinde, isim-token-sayısı kadar ardışık kelime penceresini isimle fuzzy karşılaştır (A1).
    Uzunluk ön-filtresi (±%30) gereksiz SequenceMatcher çağrılarını keser. ASİMETRİK eşik: pencere
    ön-adla exact başlamıyorsa bar max(rmin, 0.92)'ye çıkar (farklı-kişi çiftlerine karşı — Opus F-1)."""
    words = line.split()
    n = len(toks)
    if n == 0 or len(words) < n:
        return False
    for i in range(len(words) - n + 1):
        win = " ".join(words[i:i + n])
        if abs(len(win) - len(name)) > max(3, int(0.3 * len(name))):
            continue
        bar = rmin if words[i] == toks[0] else max(rmin, 0.92)
        if difflib.SequenceMatcher(None, name, win).ratio() >= bar:
            return True
    return False


def _vl_one(cv, ctr, giris, cikis, model, kb):
    """Bir VL modeli: yön+cast; yönetmenden O MODELİN cast'inde geçeni at (self-consistency) + KESİN KURAL."""
    res = cv.read_credits(giris, cikis, models=[model], kb=kb) or {}
    yon = res.get("yonetmen") or []
    cast = res.get("cast") or []
    cf = {_fold(x) for x in cast}
    yon = ctr._only_persons([y for y in yon if _fold(y) not in cf])
    return yon, ctr._only_persons(cast)


def _tiebreak(q, g, all_cast_fold, kb):
    """a) mutabakat  b) cross-cast  c) KB-onay  d) PES."""
    agree = [y for y in q if any(_fold(y) == _fold(x) for x in g)]
    if agree:
        return [agree[0]], "mutabakat"
    cands = []
    for y in q + g:
        if not any(_fold(y) == _fold(x) for x in cands):
            cands.append(y)
    cands = [y for y in cands if _fold(y) not in all_cast_fold]   # cross-cast: başrol ele
    if not cands:
        return [], "pes(cross-cast)"
    # KB-tiebreak YALNIZ gerçek çelişkide (≥2 aday) — çelişkiyi ÇÖZ. Tek aday (tek model okudu,
    # diğeri abstain) → KB-genel-onay YETMEZ (Kar Kraliçesi→"Chris Randall" sızıntısı buydu):
    # mutabakat yok + tek-model → Kontrol. "yanlış > boş".
    if len(cands) >= 2:
        kb_ok = [y for y in cands if kb.verify(y, "director") == "ONAY"]
        if len(kb_ok) == 1:
            return kb_ok, "kb-tiebreak"
        return [], "pes(coklu-kb/belirsiz)"
    return [], "pes(tek-model, mutabakat yok)"


def vl_fallback(clip, title, text_credits, profile="film", fill_cast=False, ocr_job="",
                original="", year=""):
    """Metnin boş yönetmenini/eksik cast'ini gemma4 VL ile doldur. Her hata → text_credits AYNEN.

    fill_cast=True (QC1-RED yolundan çağrılınca): cast<3 ise gemma4'ün cast'ini de ekle.
    fill_cast=False (eski yol): MITAS_VL_CAST=1 env yoksa sadece yönetmen doldurulur.
    ocr_job (A1 2026-07-03): aktif OCR koşusunun job-id'si → hayalet-kalkanı korpusu run-scoped olur.
    original/year (A2 2026-07-03): ÇAPA-1 KB film-kimlik kilidi için orijinal ad + TRT katalog yılı.
    """
    out = dict(text_credits or {})
    out.setdefault("yonetmen", [])
    out.setdefault("yapimci", [])
    out.setdefault("cast", [])
    started = time.perf_counter()
    before = {"yonetmen": list(out.get("yonetmen") or []),
              "cast": list(out.get("cast") or []),
              "yapimci": list(out.get("yapimci") or [])}
    try:
        import credit_video_read as cv
        import credit_text_read as ctr
        cv.NUM_CTX = 40960
        cv.PROMPT = _VL_PROMPT
        giris, cikis = _find_frames(clip)
        if not giris:
            out["vl"] = "kare-yok"
            dbg.emit("vl_fallback", "fallback_triggered", status="warn",
                     duration_ms=(time.perf_counter() - started) * 1000,
                     subject={"field": "frames", "before": before, "after": out,
                              "reason": "VL fallback skipped because no frames were found"},
                     evidence={"clip": clip, "title": title},
                     source={"module": "scripts/_pipe_credit_vl.py", "input_paths": [clip]})
            return out
        kb = cv.KB()
        yon, vl_cast = _vl_one(cv, ctr, giris, cikis, VL_MODELS[0], kb)
        tcast = out.get("cast") or []
        all_cast_fold = {_fold(x) for x in (tcast + vl_cast)}
        raw_lines = _load_raw_ocr(clip, ocr_job)   # HAYALET-KALKANI korpusu (run-scoped + manifest, A1)
        # YÖNETMEN: yalnız BOŞSA doldur (metni EZME), cross-cast filtresi
        if not out.get("yonetmen"):
            yon_clean = [y for y in yon if _fold(y) not in all_cast_fold]
            yon_persons = ctr._only_persons(yon_clean)
            # DoP-DIŞLAMA (2026-07-03): metin-yolundaki deterministik yönetmen-dışı-rol süzgeci VL
            # yoluna da bağlandı — VL prompt'u DoP'yi dışla dese de model yönetmen bulamayınca görüntü
            # yönetmenini önerebiliyor; ham-OCR bağlam kontrolü (etiket ±1 satır) bunu keser.
            try:
                _real_lines = [l for l in raw_lines if l != _CORPUS_SENTINEL]
                yon_persons, _dop_dropped = ctr._drop_dubbing_directors(yon_persons, _real_lines)
                if _dop_dropped:
                    out["vl_yon_dop_dropped"] = _dop_dropped
                    dbg.emit("vl_fallback", "candidate_dropped", status="warn",
                             subject={"field": "yonetmen", "before": yon_persons + _dop_dropped,
                                      "after": yon_persons,
                                      "reason": "VL director matched a non-director role label context"},
                             evidence={"dropped": _dop_dropped},
                             source={"module": "scripts/_pipe_credit_vl.py", "input_paths": [clip]})
            except Exception:  # noqa: BLE001 — süzgeç hatası doldurmayı bozmasın (fail-safe)
                pass
            # PRODUCTION-KARTI DIŞLAMA (117-film taraması 2026-07-03, APOLLO 11 kanıtı): VL
            # "A JAMES MANOS PRODUCTION" yapım-şirketi kartını yönetmen sandı. Deterministik:
            # ham korpusta "<isim> production(s)" bitişik deseni varsa aday yapım-şirketidir → DÜŞ.
            try:
                _prod_keep = []
                for y in yon_persons:
                    _ptoks = _fold(y).split()
                    if _ptoks:
                        _pre = re.compile(r"\b" + r"\s+".join(re.escape(t) for t in _ptoks) + r"\s+productions?\b")
                        if any(_pre.search(l) for l in raw_lines if l != _CORPUS_SENTINEL):
                            out.setdefault("vl_yon_prod_dropped", []).append(y)
                            continue
                    _prod_keep.append(y)
                yon_persons = _prod_keep
            except Exception:  # noqa: BLE001
                pass
            # HAYALET-KALKANI: VL pikselden UYDURMUŞ olabilir → ham OCR'da geçmeyen yönetmeni DÜŞÜR
            # (okunamadı > yanlış; yönetmen=kimlik çapası). FOTOĞRAF 'JEFF TOWLES' tipi uydurma kesilir.
            # İnceleme-koşulu (2026-07-03): eşleşme YÖNTEMİ kaydedilir — fuzzy/crossline yoluyla dolan
            # yönetmen exact'ten AYIRT EDİLİR; pipeline fuzzy-dolumu KONTROL'e işaretler (sessiz-ONAYLI yok).
            _yon_corr, _yon_methods = [], {}
            for y in yon_persons:
                _hit, _method, _ev = _in_raw_detail(y, raw_lines)
                if _hit:
                    _yon_corr.append(y)
                    _yon_methods[y] = {"method": _method, "kanit": (_ev or "")[:160]}
            # A2 ÇAPA-1 (2026-07-03): korpus TAMAMEN kör kaldıysa (hiç teyit yok) son şans —
            # KB film-kimlik kilidi: VL adayı + başlık(TR/orijinal)+yıl → KB'de bu yönetmenin
            # bu filmi VAR mı (credit_qc_gates.web_identity ÇAPA-1; method=='director' ŞART —
            # ÇAPA-2/tmdb title+year kilidi versiyon-teyitsizdir, ASLA kabul edilmez).
            # Genel-KB-onay ("bu isim bir yönetmen") YETMEZ (Kar Kraliçesi dersi); burada
            # film-özgül eşleşme aranır. Kabul edilen dolum pipeline'da yine KONTROL'e işaretlenir
            # (shadow-dönemi: sessiz-ONAYLI yok). Kill-switch: MITAS_VL_KB_ANCHOR=0.
            _uncorr = [y for y in yon_persons if y not in _yon_corr]
            if (_uncorr and not _yon_corr
                    and os.environ.get("MITAS_VL_KB_ANCHOR", "1").strip().lower() not in ("0", "false", "off", "no")):
                try:
                    import credit_qc_gates as qcg
                    import credit_crosscheck as cc2
                    _ckb = cc2.CreditKB()
                    for y in _uncorr:
                        wi = qcg.web_identity(title or "", original or "", year or "", y, "", _ckb) or {}
                        if wi.get("locked") and wi.get("method") == "director":
                            _yon_corr = [y]
                            _yon_methods[y] = {"method": "kb-anchor",
                                               "kanit": str(wi.get("kaynak_izi") or "")[:200]}
                            dbg.emit("vl_fallback", "candidate_dropped", status="ok",
                                     subject={"field": "yonetmen", "before": _uncorr, "after": [y],
                                              "reason": "VL director corroborated via KB film-identity anchor"},
                                     evidence={"kaynak_izi": wi.get("kaynak_izi"),
                                               "imdb_id": wi.get("imdb_id")},
                                     source={"module": "scripts/_pipe_credit_vl.py", "input_paths": [clip]})
                            break
                except Exception:  # noqa: BLE001 — KB yoksa/ağ koptuysa ÇAPA-1 sessizce atlanır
                    pass
            if _yon_corr != yon_persons:
                out["vl_yon_hallucinated"] = [y for y in yon_persons if y not in _yon_corr]
                dbg.emit("vl_fallback", "candidate_dropped", status="warn",
                         subject={"field": "yonetmen", "before": yon_persons, "after": _yon_corr,
                                  "reason": "VL director not found in raw OCR corpus"},
                         evidence={"raw_context_lines": len(raw_lines)},
                         source={"module": "scripts/_pipe_credit_vl.py", "input_paths": [clip]})
            if _yon_corr:
                out["yonetmen"] = _yon_corr
                _mset = {m["method"] for m in _yon_methods.values() if m.get("method")}
                _suffix = ""
                if "kb-anchor" in _mset:
                    _suffix = "+kb-anchor"
                elif any("fuzzy" in m for m in _mset):
                    _suffix = "+fuzzy"
                elif "crossline" in _mset:
                    _suffix = "+crossline"
                out["vl_yon_kaynak"] = "gemma4" + _suffix
                out["vl_yon_eslesme"] = _yon_methods
        # CAST-supplement: fill_cast=True (QC1-RED) veya MITAS_VL_CAST=1 env.
        # QC1-RED yolunda metin-OCR cast<3 zaten doğrulandı → gemma4 cast dene.
        _fill = fill_cast or os.environ.get("MITAS_VL_CAST", "0").strip().lower() in ("1", "true", "on", "yes")
        if _fill and len(tcast) < 3:
            add = []
            for nm in vl_cast:
                if not any(_fold(nm) == _fold(x) for x in tcast + add):
                    add.append(nm)
            # HAYALET-KALKANI: ham OCR'da geçmeyen VL-cast uydurmasını DÜŞÜR
            _add_corr = [nm for nm in add if _in_raw(nm, raw_lines)]
            if len(_add_corr) != len(add):
                out["vl_cast_hallucinated"] = len(add) - len(_add_corr)
                # A0 (2026-07-03): düşen cast adaylarının İSİMLERİ de kaydedilir (insan-yüzeyleme;
                # sayı tek başına denetçiye hiçbir şey söylemiyordu). Additive — eski alan korunur.
                out["vl_cast_hallucinated_names"] = [nm for nm in add if nm not in _add_corr]
                dbg.emit("vl_fallback", "candidate_dropped", status="warn",
                         subject={"field": "cast", "before": add, "after": _add_corr,
                                  "reason": "VL cast candidate not found in raw OCR corpus"},
                         evidence={"raw_context_lines": len(raw_lines)},
                         source={"module": "scripts/_pipe_credit_vl.py", "input_paths": [clip]})
            add = _add_corr
            if add:
                out["cast"] = ctr._only_persons(tcast + add)
                out["vl_cast_supplement"] = len(add)
        out["vl"] = "kostu"
        dbg.emit("vl_fallback", "fallback_triggered",
                 duration_ms=(time.perf_counter() - started) * 1000,
                 subject={"field": "credits", "before": before, "after": out,
                          "reason": "VL fallback completed"},
                 evidence={"model": VL_MODELS[0], "fill_cast": fill_cast,
                           "raw_context_lines": len(raw_lines),
                           "vl_yon_hallucinated": out.get("vl_yon_hallucinated"),
                           "vl_cast_hallucinated": out.get("vl_cast_hallucinated"),
                           "vl_cast_supplement": out.get("vl_cast_supplement")},
                 source={"module": "scripts/_pipe_credit_vl.py", "input_paths": [clip]})
    except Exception as e:  # noqa: BLE001 — FAIL-SAFE: pipeline'ı ASLA bozma
        out["vl"] = f"hata:{type(e).__name__}"
        dbg.emit("vl_fallback", "fallback_triggered", status="error",
                 duration_ms=(time.perf_counter() - started) * 1000,
                 subject={"field": "credits", "before": before, "after": out,
                          "reason": "VL fallback failed"},
                 evidence={"model": VL_MODELS[0], "fill_cast": fill_cast},
                 error=str(e),
                 source={"module": "scripts/_pipe_credit_vl.py", "input_paths": [clip]})
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--profile", default="film")
    ap.add_argument("--text-credits", default="{}", help="metin künye-okuma JSON (qwen3 sonucu)")
    ap.add_argument("--fill-cast", action="store_true", help="QC1-RED yolu: cast<3 ise gemma4 cast'ini de ekle")
    ap.add_argument("--ocr-job", default="", help="aktif OCR job-id (A1: kalkan korpusunu bu koşuya sınırla; boş=eski davranış)")
    ap.add_argument("--original", default="", help="orijinal (yabancı) film adı — A2 ÇAPA-1 KB araması için")
    ap.add_argument("--year", default="", help="TRT katalog yılı — A2 ÇAPA-1 yıl toleransı (±3) için")
    a = ap.parse_args()
    try:
        tc = json.loads(a.text_credits)
    except Exception:
        tc = {}
    res = vl_fallback(a.clip, a.title, tc, a.profile, fill_cast=a.fill_cast, ocr_job=a.ocr_job,
                      original=a.original, year=a.year)
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
