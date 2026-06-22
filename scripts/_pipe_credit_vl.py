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
import glob
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# VL prompt: yönetmen-etiket kalıpları + KESİN KURAL (metin tarafıyla aynı mantık)
_VL_PROMPT = (
    "Bunlar bir film jeneriğinin ARDIŞIK kareleri (video). Kareler boyunca görünen yazıları "
    "birleştir. SADECE karelerde AÇIKÇA YAZAN isimleri kullan, UYDURMA; yoksa 'yok'.\n"
    "YÖNETMEN: şu kalıpların YANINDAKİ/ALTINDAKİ KİŞİ adı: 'DIRECTED BY', 'A <İSİM> FILM' "
    "(ör. 'A JOHN McTIERNAN FILM' -> John McTiernan), 'A FILM BY', 'YÖNETMEN', 'YÖNETEN', "
    "'REJİSÖR', 'UN FILM DE', 'EIN FILM VON', 'REGIE', 'RÉALISÉ PAR'. "
    "'ASSISTANT DIRECTOR / DIRECTOR OF PHOTOGRAPHY / ART DIRECTOR / MUSIC' YÖNETMEN DEĞİLDİR. Net değilse 'yok'.\n"
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
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()


def _find_frames(clip):
    """clip/frames/giris + cikis (ya da clip altında ilk giris/cikis)."""
    g = os.path.join(clip, "frames", "giris")
    c = os.path.join(clip, "frames", "cikis")
    if not os.path.isdir(g):
        cand = glob.glob(os.path.join(clip, "**", "giris"), recursive=True)
        g = cand[0] if cand else None
    if not os.path.isdir(c or ""):
        cand = glob.glob(os.path.join(clip, "**", "cikis"), recursive=True)
        c = cand[0] if cand else None
    return (g if g and os.path.isdir(g) else None), (c if c and os.path.isdir(c) else None)


def _load_raw_ocr(clip):
    """Jenerik karelerinin HAM OCR metni (ocr_raw_all + ocr_ham + kunye) → VL hayalet-kalkanı korpusu.
    VL pikselden okur; HAM OCR aynı kareleri işledi → gerçek isim ham OCR'da bulunur, yoksa = uydurma
    (2026-06-20 forensik: FOTOĞRAF VL 'JEFF TOWLES' uydurdu, ham OCR'da YOK → kalkan düşürür).
    Katlanmış boş-olmayan SATIR listesi döndürür (adjacency-aware kalkan için: bütün-isim TEK satırda olmalı)."""
    parts = []
    for pat in ("ocr_raw_all.txt", "ocr_ham.txt", "kunye.txt"):
        for fp in glob.glob(os.path.join(clip, "ocr", "**", pat), recursive=True):
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
    return lines


def _in_raw(name, raw_lines):
    """İsmin TÜM token'ları HAM OCR'da BİTİŞİK + TAM-KELİME (tek satırda, sırayla) geçiyor mu — Frankenstein kalkanı.
    KÖK (MANASLU 2026-06-22): eski `all(t in blob)` token'ları AYRI/substring arıyordu → 'HANS-PETER STAUBER'
    + 'HANNELORE EBNER' ayrı satırlardan 'Hans Ebner' uydurması geçiyordu. Artık tüm isim TEK satırda, sıralı,
    word-boundary ile aranır (credit_text_read._name_hit_in_raw deseni): bu hem satır-AYRI'yı hem 'hans'∈'hanseatic'
    substring kaçağını hem stitch-birleşik-satır Frankenstein'ini kapatır. raw yoksa kalkanı atla (FAIL-SAFE).
    Eski substring davranışı (≥4/≥3 token subset, blob) MITAS_VL_RAW_ADJACENCY=0 ile geri gelir."""
    if not raw_lines:
        return True
    toks = _fold(name).split()
    if not toks:
        return False
    if os.environ.get("MITAS_VL_RAW_ADJACENCY", "1").strip().lower() in ("0", "false", "off", "no"):
        blob = " ".join(raw_lines)               # ESKİ DAVRANIŞ: ≥4/≥3 token subset, tüm metinde AYRI/substring
        sub = [t for t in toks if len(t) >= 4] or [t for t in toks if len(t) >= 3]
        return bool(sub) and all(t in blob for t in sub)
    pat = re.compile(r"\b" + r"\s+".join(re.escape(t) for t in toks) + r"\b")   # tüm isim BİTİŞİK + word-boundary
    return any(pat.search(line) for line in raw_lines)


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


def vl_fallback(clip, title, text_credits, profile="film", fill_cast=False):
    """Metnin boş yönetmenini/eksik cast'ini gemma4 VL ile doldur. Her hata → text_credits AYNEN.

    fill_cast=True (QC1-RED yolundan çağrılınca): cast<3 ise gemma4'ün cast'ini de ekle.
    fill_cast=False (eski yol): MITAS_VL_CAST=1 env yoksa sadece yönetmen doldurulur.
    """
    out = dict(text_credits or {})
    out.setdefault("yonetmen", [])
    out.setdefault("yapimci", [])
    out.setdefault("cast", [])
    try:
        import credit_video_read as cv
        import credit_text_read as ctr
        cv.NUM_CTX = 40960
        cv.PROMPT = _VL_PROMPT
        giris, cikis = _find_frames(clip)
        if not giris:
            out["vl"] = "kare-yok"
            return out
        kb = cv.KB()
        yon, vl_cast = _vl_one(cv, ctr, giris, cikis, VL_MODELS[0], kb)
        tcast = out.get("cast") or []
        all_cast_fold = {_fold(x) for x in (tcast + vl_cast)}
        raw_lines = _load_raw_ocr(clip)   # HAYALET-KALKANI korpusu (ham OCR satır listesi)
        # YÖNETMEN: yalnız BOŞSA doldur (metni EZME), cross-cast filtresi
        if not out.get("yonetmen"):
            yon_clean = [y for y in yon if _fold(y) not in all_cast_fold]
            yon_persons = ctr._only_persons(yon_clean)
            # HAYALET-KALKANI: VL pikselden UYDURMUŞ olabilir → ham OCR'da geçmeyen yönetmeni DÜŞÜR
            # (okunamadı > yanlış; yönetmen=kimlik çapası). FOTOĞRAF 'JEFF TOWLES' tipi uydurma kesilir.
            _yon_corr = [y for y in yon_persons if _in_raw(y, raw_lines)]
            if _yon_corr != yon_persons:
                out["vl_yon_hallucinated"] = [y for y in yon_persons if y not in _yon_corr]
            if _yon_corr:
                out["yonetmen"] = _yon_corr
                out["vl_yon_kaynak"] = "gemma4"
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
            add = _add_corr
            if add:
                out["cast"] = ctr._only_persons(tcast + add)
                out["vl_cast_supplement"] = len(add)
        out["vl"] = "kostu"
    except Exception as e:  # noqa: BLE001 — FAIL-SAFE: pipeline'ı ASLA bozma
        out["vl"] = f"hata:{type(e).__name__}"
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--profile", default="film")
    ap.add_argument("--text-credits", default="{}", help="metin künye-okuma JSON (qwen3 sonucu)")
    ap.add_argument("--fill-cast", action="store_true", help="QC1-RED yolu: cast<3 ise gemma4 cast'ini de ekle")
    a = ap.parse_args()
    try:
        tc = json.loads(a.text_credits)
    except Exception:
        tc = {}
    res = vl_fallback(a.clip, a.title, tc, a.profile, fill_cast=a.fill_cast)
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
